#!/usr/bin/env bash
# Find KB files with `last_validated` older than N days.
#
# Usage:
#   find_stale_kb_files.sh [--threshold-days N] [--root PATH]
#
# Output: tab-separated stdout, one line per stale file:
#   <days_old>\t<last_validated_date>\t<file_path>
#
# Sorted oldest-first. Designed to feed into the kb-revalidate skill workflow.

set -euo pipefail

THRESHOLD_DAYS="${THRESHOLD_DAYS:-90}"
ROOT="${ROOT:-.}"

while [[ $# -gt 0 ]]; do
    case "$1" in
        --threshold-days) THRESHOLD_DAYS="$2"; shift 2 ;;
        --root)           ROOT="$2";           shift 2 ;;
        --help|-h)
            sed -n '2,11p' "$0" | sed 's/^# \?//'
            exit 0
            ;;
        *) echo "unknown arg: $1" >&2; exit 1 ;;
    esac
done

# Cross-platform "now in epoch seconds"
NOW_EPOCH=$(date +%s)

# Cross-platform date parser (macOS BSD vs GNU)
to_epoch() {
    local d="$1"
    # macOS / BSD
    if date -j -f '%Y-%m-%d' "$d" +%s 2>/dev/null; then
        return
    fi
    # GNU
    date -d "$d" +%s
}

# Find all KB files (markdown + YAML) in any knowledge/ or references/ dir
find "$ROOT" \
    \( -path '*/knowledge/*' -o -path '*/references/*' \) \
    -type f \( -name '*.md' -o -name '*.yaml' -o -name '*.yml' \) \
    -not -path '*/.git/*' \
    -not -path '*/node_modules/*' \
    | while IFS= read -r f; do

    # Extract last_validated date — supports both markdown and YAML formats:
    #   markdown:  > **Last validated**: 2026-04-26
    #   yaml:      last_validated: "2026-04-26"
    date=$(grep -oE '[Ll]ast[ _-]?[Vv]alidated["[:space:]:*]*["]?[0-9]{4}-[0-9]{2}-[0-9]{2}' "$f" \
        | head -1 \
        | grep -oE '[0-9]{4}-[0-9]{2}-[0-9]{2}' || true)

    [[ -z "$date" ]] && continue

    epoch=$(to_epoch "$date")
    days_old=$(( (NOW_EPOCH - epoch) / 86400 ))

    if [[ "$days_old" -gt "$THRESHOLD_DAYS" ]]; then
        printf '%d\t%s\t%s\n' "$days_old" "$date" "$f"
    fi
done | sort -rn
