#!/usr/bin/env bash
# kb-staleness-warning hook
# Triggered: sessionStart
# Effect:    prints a warning to stderr if any KB file is older than the
#            threshold. Does NOT block the session — informational only.
#
# Configuration (env vars):
#   KB_STALENESS_THRESHOLD_DAYS   default 90
#   KB_STALENESS_QUIET_HOURS      default 24 (skip if last warned in window)
#
# Output: 0 stale files = silent.
#         N stale files = stderr message + nonzero exit (still non-blocking).

set -euo pipefail

THRESHOLD_DAYS="${KB_STALENESS_THRESHOLD_DAYS:-90}"
QUIET_HOURS="${KB_STALENESS_QUIET_HOURS:-24}"
STATE_FILE="${XDG_STATE_HOME:-$HOME/.local/state}/copilot-collection/kb-staleness-last-warned"

# Throttle: don't warn more than once per QUIET_HOURS
if [[ -f "$STATE_FILE" ]]; then
    last_warn_epoch=$(cat "$STATE_FILE" 2>/dev/null || echo 0)
    now_epoch=$(date +%s)
    hours_since=$(( (now_epoch - last_warn_epoch) / 3600 ))
    if [[ "$hours_since" -lt "$QUIET_HOURS" ]]; then
        exit 0
    fi
fi

# Cross-platform date parser (BSD vs GNU)
to_epoch() {
    local d="$1"
    if date -j -f '%Y-%m-%d' "$d" +%s 2>/dev/null; then
        return
    fi
    date -d "$d" +%s
}

NOW_EPOCH=$(date +%s)
stale_count=0
oldest_days=0
oldest_path=""

# Search any KB-shaped directory
while IFS= read -r f; do
    date=$(grep -oE '[Ll]ast[ _-]?[Vv]alidated["[:space:]:*]*["]?[0-9]{4}-[0-9]{2}-[0-9]{2}' "$f" 2>/dev/null \
        | head -1 \
        | grep -oE '[0-9]{4}-[0-9]{2}-[0-9]{2}' || true)
    [[ -z "$date" ]] && continue

    epoch=$(to_epoch "$date" 2>/dev/null || echo 0)
    [[ "$epoch" -eq 0 ]] && continue

    days_old=$(( (NOW_EPOCH - epoch) / 86400 ))

    if [[ "$days_old" -gt "$THRESHOLD_DAYS" ]]; then
        stale_count=$((stale_count + 1))
        if [[ "$days_old" -gt "$oldest_days" ]]; then
            oldest_days="$days_old"
            oldest_path="$f"
        fi
    fi
done < <(find . \
    \( -path '*/knowledge/*' -o -path '*/references/*' \) \
    -type f \( -name '*.md' -o -name '*.yaml' -o -name '*.yml' \) \
    -not -path '*/.git/*' \
    -not -path '*/node_modules/*' \
    2>/dev/null)

if [[ "$stale_count" -eq 0 ]]; then
    exit 0
fi

# Update throttle state
mkdir -p "$(dirname "$STATE_FILE")"
echo "$NOW_EPOCH" > "$STATE_FILE"

# Emit warning
cat <<EOF >&2

⚠️  KB STALENESS WARNING
   $stale_count KB files older than $THRESHOLD_DAYS days.
   Oldest: $oldest_days days — $oldest_path

   Run: /kb-revalidate          (the skill)
   Or:  bash skills/kb-revalidate/scripts/find_stale_kb_files.sh
        for a full list.

   This warning is throttled — won't repeat for $QUIET_HOURS hours.

EOF

exit 0                                     # non-blocking, informational only
