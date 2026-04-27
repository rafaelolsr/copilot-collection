# kb-staleness-warning hook

Triggers at `sessionStart`. Warns (to stderr) if any KB file has
`last_validated` older than the threshold (default 90 days). Throttled to
warn at most once per 24 hours per machine.

## What it does

1. Scans `knowledge/` and `agents/<name>/references/` directories
2. Reads `last_validated:` from each markdown / YAML file
3. Counts how many are older than the threshold
4. If any: prints stderr warning with count + oldest file
5. Throttles via state file (`~/.local/state/copilot-collection/kb-staleness-last-warned`)

Exit code is always 0 — it's informational, never blocks the session.

## Files

```
hooks/kb-staleness-warning/
├── README.md                  # this file
├── hooks.json                 # event registration
└── check-kb-staleness.sh      # the actual check
```

## Configuration

Environment variables override defaults:

| Variable | Default | Effect |
|---|---|---|
| `KB_STALENESS_THRESHOLD_DAYS` | 90 | Files older than this trigger warning |
| `KB_STALENESS_QUIET_HOURS` | 24 | Throttle window — minimum hours between warnings |

To check more aggressively (every Copilot session, no throttle):

```bash
export KB_STALENESS_QUIET_HOURS=0
```

To use a 60-day window for fast-moving domains (Foundry, Fabric):

```bash
export KB_STALENESS_THRESHOLD_DAYS=60
```

## Sample output

```
⚠️  KB STALENESS WARNING
   3 KB files older than 90 days.
   Oldest: 134 days — agents/ms-foundry-specialist/references/concepts/foundry-iq.md

   Run: /kb-revalidate          (the skill)
   Or:  bash skills/kb-revalidate/scripts/find_stale_kb_files.sh
        for a full list.

   This warning is throttled — won't repeat for 24 hours.
```

## Disabling

Either:
1. Remove `hooks/kb-staleness-warning/` from your active hooks list
2. Set `KB_STALENESS_QUIET_HOURS` to a very large number (e.g., 999999)

## Why this matters

Every agent in this collection has a 90-day KB re-validation protocol
documented in their bodies. Without an automated nudge, that protocol gets
ignored — agents quote stale info while looking confident.

This hook is the friction. Annoying enough to act on, throttled enough not
to be noise.

## Related

- `skills/kb-revalidate/SKILL.md` — what to do when warning fires
- `skills/kb-revalidate/scripts/find_stale_kb_files.sh` — list all stale files
