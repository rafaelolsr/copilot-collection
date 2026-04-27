#!/usr/bin/env bash
# secrets-scanner hook
# Triggered: sessionEnd
# Effect:    scans files modified during the Copilot session for known
#            secret patterns. Prints findings to stderr; exits 0 even if
#            findings exist (informational; CI / pre-commit should hard-fail).
#
# Configuration (env vars):
#   SECRETS_SCAN_BASE_REF      git ref to diff against (default: origin/main)
#   SECRETS_SCAN_QUIET         if "1", silent unless findings (default 1)
#   SECRETS_SCAN_INCLUDE       additional include glob (default: all changed)
#   SECRETS_SCAN_EXCLUDE       exclude glob (default: vendor/test fixtures)
#
# Patterns scanned:
#   - Anthropic API keys (sk-ant-*)
#   - OpenAI API keys (sk-proj-*, sk-* legacy)
#   - GitHub PATs (ghp_*, gho_*, ghu_*, ghs_*, ghr_*)
#   - AWS access keys (AKIA*, ASIA*) + secret access keys
#   - Azure connection strings, storage account keys
#   - Generic high-entropy tokens (best-effort)
#   - Bearer tokens, basic auth, hardcoded passwords

set -euo pipefail

BASE_REF="${SECRETS_SCAN_BASE_REF:-origin/main}"
QUIET="${SECRETS_SCAN_QUIET:-1}"
EXCLUDE="${SECRETS_SCAN_EXCLUDE:-vendor/|node_modules/|\.venv/|\.git/|\.copilot-mem/|tests/fixtures/}"

# Find changed files (best-effort; falls back to working tree if not a git repo)
get_changed_files() {
    if git rev-parse --git-dir &>/dev/null; then
        # Files changed vs base ref + any working tree changes
        {
            git diff --name-only --diff-filter=ACMRT "$BASE_REF" 2>/dev/null || true
            git diff --name-only --diff-filter=ACMRT 2>/dev/null || true
            git diff --cached --name-only --diff-filter=ACMRT 2>/dev/null || true
        } | sort -u | grep -v -E "$EXCLUDE" || true
    else
        # Not a git repo — scan everything except excludes
        find . -type f -not -path '*/\.*' | grep -v -E "$EXCLUDE" || true
    fi
}

# Patterns: regex | description | severity
PATTERNS=(
    'sk-ant-[a-zA-Z0-9_-]{40,}|Anthropic API key|CRITICAL'
    'sk-proj-[a-zA-Z0-9_-]{40,}|OpenAI project API key|CRITICAL'
    '(^|[^a-zA-Z0-9])sk-[a-zA-Z0-9]{40,}|Possible OpenAI legacy key|HIGH'
    'ghp_[a-zA-Z0-9]{36,}|GitHub Personal Access Token (classic)|CRITICAL'
    'gho_[a-zA-Z0-9]{36,}|GitHub OAuth token|CRITICAL'
    'ghu_[a-zA-Z0-9]{36,}|GitHub user-to-server token|CRITICAL'
    'ghs_[a-zA-Z0-9]{36,}|GitHub server-to-server token|CRITICAL'
    'ghr_[a-zA-Z0-9]{36,}|GitHub refresh token|CRITICAL'
    'github_pat_[a-zA-Z0-9_]{82}|GitHub fine-grained PAT|CRITICAL'
    '(^|[^a-zA-Z0-9])AKIA[A-Z0-9]{16}|AWS Access Key ID|CRITICAL'
    '(^|[^a-zA-Z0-9])ASIA[A-Z0-9]{16}|AWS Temporary Access Key|HIGH'
    'aws_secret_access_key\s*=\s*[A-Za-z0-9/+=]{40}|AWS Secret Access Key|CRITICAL'
    'AccountKey=[A-Za-z0-9+/=]{60,}|Azure Storage Account Key|CRITICAL'
    'DefaultEndpointsProtocol=https;AccountName=|Azure Storage Connection String|HIGH'
    'SharedAccessKey=[A-Za-z0-9+/=]{40,}|Azure Service Bus / Event Hub key|CRITICAL'
    'mongodb(\+srv)?://[^/[:space:]]+:[^@[:space:]]+@|MongoDB connection string with credentials|CRITICAL'
    'postgres(ql)?://[^/[:space:]]+:[^@[:space:]]+@|Postgres connection string with credentials|CRITICAL'
    'mysql://[^/[:space:]]+:[^@[:space:]]+@|MySQL connection string with credentials|CRITICAL'
    'eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}|JWT (verify intent — may be public)|MEDIUM'
    '-----BEGIN (RSA |EC |DSA |OPENSSH |PRIVATE) KEY-----|Private key|CRITICAL'
    '(api[_-]?key|password|passwd|pwd|secret|token)["\x27[:space:]]*[:=][[:space:]]*["\x27][^"\x27[:space:]]{12,}|Hardcoded credential|HIGH'
    'Authorization:\s*Bearer\s+[A-Za-z0-9._-]{20,}|Hardcoded Bearer token|HIGH'
    'Authorization:\s*Basic\s+[A-Za-z0-9+/=]{20,}|Hardcoded Basic auth|HIGH'
)

red()    { printf "\033[31m%s\033[0m" "$*"; }
yellow() { printf "\033[33m%s\033[0m" "$*"; }
muted()  { printf "\033[2m%s\033[0m" "$*"; }

found_count=0
critical_count=0

scan_file() {
    local file="$1"
    [[ ! -f "$file" ]] && return 0

    # Skip binary files
    if file -b --mime "$file" 2>/dev/null | grep -q binary; then
        return 0
    fi

    for pattern_entry in "${PATTERNS[@]}"; do
        IFS='|' read -r pattern desc severity <<< "$pattern_entry"

        # grep returns 0 on match
        if matches=$(grep -nE "$pattern" "$file" 2>/dev/null); then
            while IFS= read -r match; do
                [[ -z "$match" ]] && continue
                found_count=$((found_count + 1))
                [[ "$severity" == "CRITICAL" ]] && critical_count=$((critical_count + 1))

                local line_no=${match%%:*}
                local content=${match#*:}
                # Truncate the matched line for output
                local snippet="${content:0:100}"
                [[ ${#content} -gt 100 ]] && snippet="${snippet}..."

                {
                    case "$severity" in
                        CRITICAL) red "  [$severity]" ;;
                        HIGH)     yellow "  [$severity]" ;;
                        *)        printf "  [%s]" "$severity" ;;
                    esac
                    printf " %s\n" "$desc"
                    printf "      %s:%s\n" "$file" "$line_no"
                    muted "      $snippet"
                    printf "\n\n"
                } >&2
            done <<< "$matches"
        fi
    done
}

# Main
files=$(get_changed_files)

if [[ -z "$files" ]]; then
    [[ "$QUIET" == "1" ]] || echo "secrets-scanner: no files to scan" >&2
    exit 0
fi

while IFS= read -r f; do
    [[ -z "$f" ]] && continue
    scan_file "$f"
done <<< "$files"

if [[ "$found_count" -eq 0 ]]; then
    [[ "$QUIET" == "1" ]] || echo "✓ secrets-scanner: clean ($(echo "$files" | wc -l | tr -d ' ') files scanned)" >&2
    exit 0
fi

# Summary
{
    echo
    if [[ "$critical_count" -gt 0 ]]; then
        red "⚠️  SECRETS SCAN: $found_count finding(s), $critical_count CRITICAL"
        printf "\n"
    else
        yellow "⚠️  SECRETS SCAN: $found_count finding(s)"
        printf "\n"
    fi
    echo "    Review the matches above. If a credential leaked:"
    echo "      1. Revoke it at the provider"
    echo "      2. Remove from git history (\`git filter-repo\` or BFG)"
    echo "      3. Rotate any dependent systems"
    echo
    echo "    To suppress false positives: pre-commit hook with detect-secrets baseline"
    echo "    See: https://github.com/Yelp/detect-secrets"
    echo
} >&2

# Hook is non-blocking — exit 0 so the session ends normally.
# Users will see the stderr output. For hard-blocking, configure a
# pre-commit hook with detect-secrets / gitleaks instead.
exit 0
