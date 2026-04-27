#!/usr/bin/env bash
# Validates every .agent.md against the Copilot CLI custom-agents spec.
# Run locally before pushing; CI runs the same checks.
#
# Usage: scripts/validate.sh [path/to/agent.agent.md]
#        scripts/validate.sh             # validates all agents/

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Spec constants
MAX_BODY_CHARS=30000
MAX_DESC_CHARS=1400
ALLOWED_FRONTMATTER=(name description target tools model disable-model-invocation user-invocable mcp-servers metadata)
ALLOWED_TOOLS=(execute read edit search web todo agent "*")
FORBIDDEN_TOKENS=(anthropic openai tenacity instructor langchain llama-index)

red()    { printf "\033[31m%s\033[0m\n" "$*"; }
green()  { printf "\033[32m%s\033[0m\n" "$*"; }
yellow() { printf "\033[33m%s\033[0m\n" "$*"; }
blue()   { printf "\033[34m%s\033[0m\n" "$*"; }

errors=0
warnings=0

fail()  { red   "  FAIL: $*"; errors=$((errors+1)); }
warn()  { yellow "  WARN: $*"; warnings=$((warnings+1)); }
pass()  { green "  PASS: $*"; }
info()  { blue  "  $*"; }

# ----------------------------------------------------------------
# Validate one agent file
# ----------------------------------------------------------------
validate_agent() {
    local agent_file="$1"
    local rel_path="${agent_file#$REPO_ROOT/}"
    echo
    echo "=== $rel_path ==="

    # Test 1: extension
    if [[ "$agent_file" != *.agent.md ]]; then
        fail "extension must be .agent.md (got: $(basename "$agent_file"))"
        return
    fi
    pass "extension is .agent.md"

    # Test 2: file is non-empty
    if [[ ! -s "$agent_file" ]]; then
        fail "file is empty"
        return
    fi

    # Test 3: frontmatter delimiters
    if ! head -1 "$agent_file" | grep -q '^---$'; then
        fail "missing opening --- frontmatter delimiter"
        return
    fi
    local close_line
    close_line=$(awk '/^---$/{count++; if(count==2){print NR; exit}}' "$agent_file")
    if [[ -z "$close_line" ]]; then
        fail "missing closing --- frontmatter delimiter"
        return
    fi
    pass "frontmatter delimiters present (closes at line $close_line)"

    # Extract frontmatter & body
    local frontmatter body
    frontmatter=$(sed -n "2,$((close_line-1))p" "$agent_file")
    body=$(sed -n "$((close_line+1)),\$p" "$agent_file")

    # Test 4: frontmatter fields are in allowlist
    local field
    while IFS= read -r line; do
        # only top-level keys (no leading whitespace)
        if [[ "$line" =~ ^[a-zA-Z_-]+: ]]; then
            field="${line%%:*}"
            local found=0
            for allowed in "${ALLOWED_FRONTMATTER[@]}"; do
                if [[ "$field" == "$allowed" ]]; then
                    found=1
                    break
                fi
            done
            if [[ $found -eq 0 ]]; then
                fail "frontmatter field '$field' not in spec allowlist"
            fi
        fi
    done <<< "$frontmatter"
    pass "frontmatter fields checked against allowlist"

    # Test 5: description present
    if ! echo "$frontmatter" | grep -qE '^description:'; then
        fail "frontmatter missing required 'description' field"
    else
        pass "description field present"
    fi

    # Test 6: description length (rough — counts everything between description: and next top-level key)
    local desc_block
    desc_block=$(echo "$frontmatter" | awk '
        /^description:/{flag=1; sub(/^description:[[:space:]]*\|?[[:space:]]*/,""); print; next}
        flag && /^[a-zA-Z_-]+:/{flag=0}
        flag{print}
    ')
    local desc_len=${#desc_block}
    if (( desc_len > MAX_DESC_CHARS )); then
        warn "description is $desc_len chars (soft cap $MAX_DESC_CHARS, hard truncation at 1536)"
    else
        pass "description is $desc_len chars"
    fi

    # Test 7: tools field uses allowlist names
    if echo "$frontmatter" | grep -qE '^tools:'; then
        local tools_line
        tools_line=$(echo "$frontmatter" | grep -E '^tools:' | head -1)
        # extract list contents
        local tools_content
        tools_content=$(echo "$tools_line" | sed 's/^tools:[[:space:]]*//' | tr -d '[]"' | tr ',' '\n')
        while IFS= read -r tool; do
            tool=$(echo "$tool" | tr -d ' ')
            [[ -z "$tool" ]] && continue
            # MCP server pattern: server/tool or server/*
            if [[ "$tool" == */* ]]; then
                continue
            fi
            local found=0
            for allowed in "${ALLOWED_TOOLS[@]}"; do
                if [[ "$tool" == "$allowed" ]]; then
                    found=1
                    break
                fi
            done
            if [[ $found -eq 0 ]]; then
                fail "tool '$tool' not in spec allowlist (use: ${ALLOWED_TOOLS[*]} or server/tool pattern)"
            fi
        done <<< "$tools_content"
        # Check for Agent / agent in dangerous spot
        if echo "$tools_content" | grep -qiE '^(Agent|Task)$'; then
            warn "agent tool present — only include if this agent should invoke other agents"
        fi
        pass "tools list checked"
    else
        warn "no tools field — agent will receive ALL tools (no least-privilege)"
    fi

    # Test 8: body size
    local body_len=${#body}
    if (( body_len > MAX_BODY_CHARS )); then
        fail "body is $body_len chars (max $MAX_BODY_CHARS)"
    else
        pass "body is $body_len / $MAX_BODY_CHARS chars"
    fi

    # Test 9: auto-link corruption check
    local autolinks
    autolinks=$(grep -cE '\]\(http' "$agent_file" || true)
    if (( autolinks > 0 )); then
        # filter: real markdown links to docs are OK, but inside code blocks they're corruption
        local bad_links
        bad_links=$(awk '
            /^```/ { in_code = !in_code; next }
            in_code && /\]\(http/ { print NR ": " $0 }
        ' "$agent_file" | head -5)
        if [[ -n "$bad_links" ]]; then
            fail "auto-link corruption inside code blocks:"
            echo "$bad_links" | sed 's/^/    /'
        else
            pass "no auto-link corruption in code blocks (markdown links in prose OK)"
        fi
    else
        pass "no auto-link patterns found"
    fi

    # Test 10: KB directory exists if referenced
    # Post-migration: agents reference references/ relative to their own folder.
    # Detect both new (references/) and legacy (knowledge/<x>/) patterns.
    local agent_dir kb_path
    agent_dir=$(dirname "$agent_file")

    if echo "$body" | grep -qE '(^|[^a-zA-Z0-9_])references/'; then
        kb_path="$agent_dir/references"
        if [[ ! -d "$kb_path" ]]; then
            warn "agent references 'references/' but $kb_path doesn't exist"
        else
            pass "KB directory exists: $kb_path"
            for required in index.md quick-reference.md _manifest.yaml anti-patterns.md; do
                if [[ ! -f "$kb_path/$required" ]]; then
                    warn "missing $kb_path/$required"
                fi
            done
        fi
    elif echo "$body" | grep -qE 'knowledge/[a-z0-9-]+/'; then
        # Legacy layout (knowledge/<domain>/ at repo root)
        local kb_domain
        kb_domain=$(echo "$body" | grep -oE 'knowledge/[a-z0-9-]+/' | head -1 | sed 's|knowledge/||;s|/$||')
        kb_path="$REPO_ROOT/knowledge/$kb_domain"
        if [[ ! -d "$kb_path" ]]; then
            warn "agent references legacy knowledge/$kb_domain/ but directory doesn't exist (migrate to references/)"
        else
            pass "legacy KB directory exists: knowledge/$kb_domain/"
        fi
    fi

    # Test 11: forbidden substitution tokens (only if KB is meant to be domain-specific)
    # Skip for the agent file itself — only checks KB files
    :
}

# ----------------------------------------------------------------
# Validate KB files for substitution
# ----------------------------------------------------------------
validate_kb() {
    local kb_dir="$1"
    local rel="${kb_dir#$REPO_ROOT/}"
    local domain
    domain=$(basename "$kb_dir")
    echo
    echo "=== $rel ==="

    # Required files
    for f in index.md quick-reference.md _manifest.yaml anti-patterns.md; do
        if [[ ! -f "$kb_dir/$f" ]]; then
            fail "missing required file: $f"
        else
            pass "exists: $f"
        fi
    done

    # Unfilled placeholders
    local unfilled
    unfilled=$(grep -rlE '\{\{[A-Z_]+\}\}' "$kb_dir" 2>/dev/null || true)
    if [[ -n "$unfilled" ]]; then
        fail "unfilled {{PLACEHOLDER}} tokens in:"
        echo "$unfilled" | sed 's/^/    /'
    else
        pass "no unfilled placeholders"
    fi

    # Substitution check — forbidden tokens (skip if domain matches the token)
    for token in "${FORBIDDEN_TOKENS[@]}"; do
        # If the domain is itself one of these tokens, the agent is supposed to know it
        if [[ "$domain" == *"$token"* ]]; then
            continue
        fi
        local matches
        matches=$(grep -rli "$token" "$kb_dir" 2>/dev/null | head -3 || true)
        if [[ -n "$matches" ]]; then
            warn "possible substitution — '$token' appears in $domain KB:"
            echo "$matches" | sed 's/^/    /'
            echo "    (only flag this if '$token' is NOT supposed to be in this domain)"
        fi
    done
}

# ----------------------------------------------------------------
# Validate plugin manifests
# ----------------------------------------------------------------
validate_plugin() {
    local plugin_file="$1"
    local rel="${plugin_file#$REPO_ROOT/}"
    echo
    echo "=== $rel ==="

    for required in name version description agent; do
        if ! grep -qE "^$required:" "$plugin_file"; then
            fail "missing required field: $required"
        fi
    done

    # Check that referenced agent file exists
    local agent_ref
    agent_ref=$(grep -E '^agent:' "$plugin_file" | sed 's/^agent:[[:space:]]*//')
    local plugin_dir
    plugin_dir=$(dirname "$plugin_file")
    local resolved
    resolved=$(cd "$plugin_dir" && cd "$(dirname "$agent_ref")" && pwd)/$(basename "$agent_ref")
    if [[ ! -f "$resolved" ]]; then
        fail "agent file not found: $agent_ref → $resolved"
    else
        pass "agent reference resolves: $agent_ref"
    fi
}

# ----------------------------------------------------------------
# Main
# ----------------------------------------------------------------
echo "=== Copilot Collection Validator ==="
echo "Repo: $REPO_ROOT"

# Validate agents (post-migration: agents/<name>/<name>.agent.md)
if [[ $# -ge 1 ]]; then
    validate_agent "$1"
else
    while IFS= read -r f; do
        validate_agent "$f"
    done < <(find "$REPO_ROOT/agents" -mindepth 2 -maxdepth 3 -name '*.agent.md' 2>/dev/null)
fi

# Validate KBs (now nested as agents/<name>/references/)
while IFS= read -r d; do
    validate_kb "$d"
done < <(find "$REPO_ROOT/agents" -mindepth 2 -maxdepth 2 -type d -name 'references' 2>/dev/null)

# Validate skill SKILL.md files
validate_skill() {
    local skill_md="$1"
    local rel="${skill_md#$REPO_ROOT/}"
    echo
    echo "=== $rel ==="

    if [[ ! -s "$skill_md" ]]; then
        fail "SKILL.md is empty"
        return
    fi

    if ! head -1 "$skill_md" | grep -q '^---$'; then
        fail "missing YAML frontmatter"
        return
    fi

    local has_name has_desc
    has_name=$(grep -cE '^name:' "$skill_md" || true)
    has_desc=$(grep -cE '^description:' "$skill_md" || true)
    [[ "$has_name" -ge 1 ]] && pass "name field present" || fail "missing required 'name'"
    [[ "$has_desc" -ge 1 ]] && pass "description field present" || fail "missing required 'description'"
}

while IFS= read -r s; do
    validate_skill "$s"
done < <(find "$REPO_ROOT/skills" -mindepth 2 -maxdepth 2 -name 'SKILL.md' 2>/dev/null)

# Validate plugin manifests
while IFS= read -r p; do
    validate_plugin "$p"
done < <(find "$REPO_ROOT/plugins" -name 'plugin.yaml' -o -name 'plugin.yml' 2>/dev/null)

# Summary
echo
echo "=== Summary ==="
if (( errors > 0 )); then
    red "$errors error(s), $warnings warning(s)"
    exit 1
else
    green "0 errors, $warnings warning(s)"
    exit 0
fi
