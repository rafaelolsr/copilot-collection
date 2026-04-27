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

# Layout (post-migration in copilot-collection):
#   COLLECTION:  agents/<name>/<name>.agent.md
#                agents/<name>/references/...
#   PROJECT:     .github/agents/<name>.agent.md          (single-file layout)
#                .github/agents/kb/<domain>/...           (separate KB folder)
#
# So sync translates between layouts. Domain (project-side KB folder name)
# may differ from agent name; discover from the agent file body.

COLLECTION_AGENT="$COLLECTION_ROOT/agents/${AGENT_NAME}/${AGENT_NAME}.agent.md"
COLLECTION_KB="$COLLECTION_ROOT/agents/${AGENT_NAME}/references"
COLLECTION_PLUGIN="$COLLECTION_ROOT/plugins/$AGENT_NAME"

PROJECT_AGENT="$PROJECT_ROOT/.github/agents/${AGENT_NAME}.agent.md"

# Discover the KB domain (project-side folder name) from any available agent file.
discover_domain() {
    local agent_file="$1"
    if [[ -f "$agent_file" ]]; then
        # Project-side pattern: .github/agents/kb/<domain>/
        local d
        d=$(grep -oE '\.github/agents/kb/[a-z0-9-]+' "$agent_file" 2>/dev/null | head -1 | sed 's|.github/agents/kb/||')
        if [[ -n "$d" ]]; then
            echo "$d"
            return
        fi
        # Legacy collection-side pattern: knowledge/<domain>/
        d=$(grep -oE 'knowledge/[a-z0-9-]+' "$agent_file" 2>/dev/null | head -1 | sed 's|knowledge/||')
        if [[ -n "$d" ]]; then
            echo "$d"
            return
        fi
        # Post-migration collection-side: just "references/" — domain == agent name
    fi
}

DOMAIN=""
if [[ -f "$PROJECT_AGENT" ]]; then
    DOMAIN=$(discover_domain "$PROJECT_AGENT")
fi
if [[ -z "$DOMAIN" && -f "$COLLECTION_AGENT" ]]; then
    DOMAIN=$(discover_domain "$COLLECTION_AGENT")
fi
if [[ -z "$DOMAIN" ]]; then
    # Fallback: assume domain matches agent name minus "-specialist" suffix
    DOMAIN="${AGENT_NAME%-specialist}"
    yellow "Could not auto-detect domain from agent body. Using fallback: $DOMAIN"
fi

PROJECT_KB="$PROJECT_ROOT/.github/agents/kb/$DOMAIN"

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
    yellow "Path translation: .github/agents/kb/$DOMAIN/ → references/"
    read -r -p "Continue? [y/N] " confirm
    [[ "$confirm" =~ ^[Yy]$ ]] || { yellow "Aborted."; exit 0; }

    mkdir -p "$(dirname "$COLLECTION_AGENT")"
    cp -v "$PROJECT_AGENT" "$COLLECTION_AGENT"

    # Translate paths in the agent body: .github/agents/kb/<domain>/ → references/
    sed -i.bak \
        -e "s|.github/agents/kb/${DOMAIN}/|references/|g" \
        -e "s|knowledge/${DOMAIN}/|references/|g" \
        "$COLLECTION_AGENT"
    rm "${COLLECTION_AGENT}.bak"

    if [[ -d "$PROJECT_KB" ]]; then
        mkdir -p "$COLLECTION_KB"
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
    yellow "Path translation: references/ → .github/agents/kb/$DOMAIN/"
    read -r -p "Continue? [y/N] " confirm
    [[ "$confirm" =~ ^[Yy]$ ]] || { yellow "Aborted."; exit 0; }

    mkdir -p "$(dirname "$PROJECT_AGENT")"
    cp -v "$COLLECTION_AGENT" "$PROJECT_AGENT"

    # Translate paths back: references/ → .github/agents/kb/<domain>/
    sed -i.bak \
        -e "s|references/|.github/agents/kb/${DOMAIN}/|g" \
        "$PROJECT_AGENT"
    rm "${PROJECT_AGENT}.bak"

    if [[ -d "$COLLECTION_KB" ]]; then
        mkdir -p "$(dirname "$PROJECT_KB")"
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
