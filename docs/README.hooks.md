# Hooks

Hooks are automated actions triggered by Copilot session events. Used for:
- Pre-commit checks (secrets scan, lint)
- Session-start nudges (KB staleness warnings, env validation)
- Session-end cleanup (log flush, cache refresh)
- Tool guardian (block specific commands without confirmation)

## Directory layout

```
hooks/<hook-name>/
├── README.md              # human-readable overview
├── hooks.json             # required — registration + event binding
└── <command-script>.sh    # the actual action (or .py, etc.)
```

## hooks.json schema

```json
{
  "name": "<hook-name>",
  "description": "What this hook does",
  "events": ["sessionStart" | "sessionEnd" | "preCommit" | ...],
  "command": "./script.sh",
  "blocking": false,
  "throttle_seconds": 86400
}
```

| Field | Required | Notes |
|---|---|---|
| `name` | yes | Lowercase, kebab-case, matches directory |
| `description` | yes | One-line summary |
| `events` | yes | List of trigger events |
| `command` | yes | Relative path to executable |
| `blocking` | no | If true, non-zero exit blocks the session. Default false. |
| `throttle_seconds` | no | Minimum seconds between triggers (informational hooks) |

## Common events

| Event | When | Use case |
|---|---|---|
| `sessionStart` | Copilot session begins | Welcome, env check, staleness warning |
| `sessionEnd` | Session ends | Cleanup, log flush, secrets scan |
| `preCommit` | Before user-initiated commit | Secret scan, lint, test |
| `postCommit` | After commit | Notification, log |
| `preToolUse` | Before specific tool invocation | Approval gate (tool-guardian) |

(Exact events depend on Copilot CLI version — check the official docs for the
current list.)

## Hook patterns

### Informational (non-blocking)

Just emit a warning. Don't stop the session.

```json
{
  "blocking": false,
  "throttle_seconds": 86400
}
```

Script exits 0 silently when nothing's wrong; non-zero with stderr message
when warning emitted. Stderr shown to user; exit code ignored.

### Blocking gate

Stop the session if the check fails. Use sparingly — friction adds up.

```json
{
  "blocking": true
}
```

Script exits non-zero to block; zero to proceed. Stderr shown either way.

### Throttled

For sessionStart hooks that would nag too often. Hook tracks last-fired
state in a file (e.g., `~/.local/state/copilot-collection/<hook>-state`)
and skips if recently triggered.

## Hooks in this collection

| Hook | Event | Effect |
|---|---|---|
| `kb-staleness-warning` | sessionStart | Warns if any KB file >90 days old. Throttled 24h. Non-blocking. |

## Creating a new hook

1. Create `hooks/<your-hook>/`
2. Write `hooks.json` with event binding
3. Write the command script (shell, Python, etc.) — make it executable
4. Add `README.md` documenting the behavior
5. Test by simulating the event

## Best practices

- **Fail open by default** — informational hooks should never block
- **Throttle aggressively** — sessionStart fires constantly during dev
- **Print to stderr** — hooks share stdout with Copilot output; stderr is yours
- **Exit codes mean something** — 0 = silent success, nonzero = action taken
- **Don't reach the network** — hooks block session startup; keep them fast (<1s)
- **Document override** — every hook should be silenceable via env var

## Anti-patterns

- Hook that always prints something on every session (becomes wallpaper)
- Hook with no throttle (hammers user)
- Hook that fetches from the internet (slow startup)
- Hook that requires interactive input (can't run unattended)
- Hook that modifies files without consent
