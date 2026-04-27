#!/usr/bin/env bash
# Bidirectional sync between this collection and a private project repo
# (e.g., your Foundry project workspace).
#
# Usage:
#   sync.sh pull <project-path> <agent-name>
#     Copy agent + KB FROM the private project INTO this collection.
#
#   sync.sh push <project-path> <agent-name>
#     Copy agent + KB FROM this collection INTO the private project.
#
#   sync.sh diff <project-path> <agent-name>
#     Show what differs between the two locations (no changes).
#
# Example:
#   scripts/sync.sh pull /Users/rafael/Github/foundry-project ms-foundry-specialist
#   scripts/sync.sh push /Users/rafael/Github/foundry-project ms-foundry-specialist
#
# Sync is INTENTIONALLY MANUAL. Always review the diff before committing.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COLLECTION_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

usage() {
    sed -n '2,18p' "$0" | sed 's/^# \?//'
    exit 1
}

red()    { printf "\033[31m%s\033[0m\n" "$*"; }
green()  { printf "\033[32m%s\033[0m\n" "$*"; }
yellow() { printf "\033[33m%s\033[0m\n" "$*"; }
blue()   { printf "\033[34m%s\033[0m\n" "$*"; }

[[ $# -lt 3 ]] && usage

DIRECTION="$1"
PROJECT_ROOT="$2"
AGENT_NAME="$3"

# Resolve and validate paths
if [[ ! -d "$PROJECT_ROOT" ]]; then
    red "ERROR: project path does not exist: $PROJECT_ROOT"
    exit 1
fi

# Determine domain from agent file (assumes agent name == domain when not separate)
COLLECTION_AGENT="$COLLECTION_ROOT/agents/${AGENT_NAME}.agent.md"
PROJECT_AGENT="$PROJECT_ROOT/.github/agents/${AGENT_NAME}.agent.md"

# Discover the KB domain from the agent file. Supports both layouts:
#   - .github/agents/kb/<domain>/ (Foundry project layout — preferred)
#   - knowledge/<domain>/ (legacy layout)
discover_domain() {
    local agent_file="$1"
    if [[ -f "$agent_file" ]]; then
        # Try the .github/agents/kb/<domain>/ pattern first
        local d
        d=$(grep -oE '\.github/agents/kb/[a-z0-9-]+' "$agent_file" 2>/dev/null | head -1 | sed 's|.github/agents/kb/||')
        if [[ -n "$d" ]]; then
            echo "$d"
            return
        fi
        # Fallback: legacy knowledge/<domain>/ pattern
        grep -oE 'knowledge/[a-z0-9-]+' "$agent_file" 2>/dev/null | head -1 | sed 's|knowledge/||'
    fi
}

DOMAIN=""
if [[ -f "$COLLECTION_AGENT" ]]; then
    DOMAIN=$(discover_domain "$COLLECTION_AGENT")
fi
if [[ -z "$DOMAIN" && -f "$PROJECT_AGENT" ]]; then
    DOMAIN=$(discover_domain "$PROJECT_AGENT")
fi
if [[ -z "$DOMAIN" ]]; then
    yellow "Could not auto-detect KB domain from agent file."
    yellow "Defaulting to agent name: $AGENT_NAME"
    DOMAIN="$AGENT_NAME"
fi

# In the collection: KB lives under knowledge/<domain>/ (flat layout)
# In the project:     KB lives under .github/agents/kb/<domain>/ (nested layout)
COLLECTION_KB="$COLLECTION_ROOT/knowledge/$DOMAIN"
PROJECT_KB="$PROJECT_ROOT/.github/agents/kb/$DOMAIN"
COLLECTION_PLUGIN="$COLLECTION_ROOT/plugins/$AGENT_NAME"

blue "Collection root: $COLLECTION_ROOT"
blue "Project root:    $PROJECT_ROOT"
blue "Agent:           $AGENT_NAME"
blue "Domain:          $DOMAIN"
echo

# ----------------------------------------------------------------
# diff
# ----------------------------------------------------------------
do_diff() {
    blue "=== Agent file ==="
    if [[ -f "$COLLECTION_AGENT" && -f "$PROJECT_AGENT" ]]; then
        diff -u "$PROJECT_AGENT" "$COLLECTION_AGENT" || true
    elif [[ -f "$COLLECTION_AGENT" ]]; then
        yellow "Only in collection: $COLLECTION_AGENT"
    elif [[ -f "$PROJECT_AGENT" ]]; then
        yellow "Only in project: $PROJECT_AGENT"
    else
        red "Agent file missing in BOTH locations."
    fi

    echo
    blue "=== KB ==="
    if [[ -d "$COLLECTION_KB" && -d "$PROJECT_KB" ]]; then
        diff -ruq "$PROJECT_KB" "$COLLECTION_KB" || true
    elif [[ -d "$COLLECTION_KB" ]]; then
        yellow "Only in collection: $COLLECTION_KB"
    elif [[ -d "$PROJECT_KB" ]]; then
        yellow "Only in project: $PROJECT_KB"
    else
        red "KB missing in BOTH locations."
    fi
}

# ----------------------------------------------------------------
# pull: project → collection
# ----------------------------------------------------------------
do_pull() {
    if [[ ! -f "$PROJECT_AGENT" ]]; then
        red "Source agent file not found: $PROJECT_AGENT"
        exit 1
    fi

    yellow "Pulling FROM private project INTO collection."
    yellow "Targets:"
    echo "  $COLLECTION_AGENT"
    echo "  $COLLECTION_KB/"
    read -r -p "Continue? [y/N] " confirm
    [[ "$confirm" =~ ^[Yy]$ ]] || { yellow "Aborted."; exit 0; }

    mkdir -p "$(dirname "$COLLECTION_AGENT")"
    cp -v "$PROJECT_AGENT" "$COLLECTION_AGENT"

    if [[ -d "$PROJECT_KB" ]]; then
        mkdir -p "$COLLECTION_ROOT/knowledge"
        rsync -av --delete "$PROJECT_KB/" "$COLLECTION_KB/"
    fi

    green "Pull complete. Run scripts/validate.sh before committing."
}

# ----------------------------------------------------------------
# push: collection → project
# ----------------------------------------------------------------
do_push() {
    if [[ ! -f "$COLLECTION_AGENT" ]]; then
        red "Source agent file not found: $COLLECTION_AGENT"
        exit 1
    fi

    yellow "Pushing FROM collection INTO private project."
    yellow "Targets:"
    echo "  $PROJECT_AGENT"
    echo "  $PROJECT_KB/"
    read -r -p "Continue? [y/N] " confirm
    [[ "$confirm" =~ ^[Yy]$ ]] || { yellow "Aborted."; exit 0; }

    mkdir -p "$(dirname "$PROJECT_AGENT")"
    cp -v "$COLLECTION_AGENT" "$PROJECT_AGENT"

    if [[ -d "$COLLECTION_KB" ]]; then
        mkdir -p "$PROJECT_ROOT/knowledge"
        rsync -av --delete "$COLLECTION_KB/" "$PROJECT_KB/"
    fi

    green "Push complete. Review changes in the project repo before committing."
}

case "$DIRECTION" in
    pull) do_pull ;;
    push) do_push ;;
    diff) do_diff ;;
    *) red "Unknown direction: $DIRECTION"; usage ;;
esac
