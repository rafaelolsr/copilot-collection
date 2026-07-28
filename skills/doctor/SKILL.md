---
name: doctor
description: |
  Runs a health check on the local GitHub Copilot CLI install and prints a
  pass/warn/fail report with copy-paste fixes — the Copilot equivalent of
  Claude Code's /doctor. Checks CLI version & updates, install location,
  auth, config/MCP/permissions JSON validity, loaded skills & agents,
  instruction resolution, and ~/.copilot disk hygiene.

  Use when the user says: "run doctor", "copilot doctor", "health check",
  "diagnose copilot", "is my copilot install healthy", "why is copilot
  broken", "check my copilot setup", "what's wrong with copilot".

  Do NOT use for: debugging your own application code, repo-level test/lint
  failures (use code-review or the project's test runner), MCP server
  authoring (use /mcp), or anything that is not about the Copilot CLI
  installation itself.
license: MIT
allowed-tools: [shell]
argument-hint: "[apply_fixes=false] [scope=all]"
---

# Doctor

A read-only health check for the **GitHub Copilot CLI** installation and its
`~/.copilot` environment. Replicates the spirit of Claude Code's `/doctor`:
run a battery of diagnostics, classify each as PASS / WARN / FAIL, and emit a
report with concrete remediation commands.

By default this skill **does not change anything** — it inspects and reports.
It only applies a fix when the user explicitly sets `apply_fixes=true`, and
even then only for the safe fixes listed in Step 3.

## When to use

- The CLI is misbehaving (auth errors, MCP servers not loading, skills not
  appearing, slow startup) and you want a single triage report.
- After updating, reinstalling, or moving the `~/.copilot` config.
- As a periodic hygiene check (config drift, log/db bloat).

When NOT to use:
- For application/code bugs in the user's repo (that's normal dev work).
- For authoring MCP servers, skills, or agents (use the relevant skill).
- For GitHub-side or org policy issues that aren't visible locally.

## Conventions

- Treat every check as **non-destructive**. Never delete, truncate, or
  rewrite a file unless `apply_fixes=true` AND the fix is on the safe list.
- Resolve the config directory from `$COPILOT_HOME` if set, else
  `~/.copilot`. Resolve the logs dir from `--log-dir` precedent, else
  `<config>/logs`.
- The CLI binary is whatever `command -v copilot` resolves to. Do not assume
  Homebrew vs npm — detect it.
- If a command is unavailable or a path is missing, that is a finding
  (usually WARN), not a reason to abort. Run every check, then report.
- Redact secrets. Never print token values, only whether a token is present.

## Workflow

### Step 1 — Collect environment facts

Run these read-only probes. Capture output; do not fail the whole run if one
errors (record the error as the finding for that check).

```bash
# Identity & version
command -v copilot; type -a copilot 2>/dev/null
copilot --version 2>&1
copilot update --help >/dev/null 2>&1 && echo "update-subcommand: ok"

# Runtime context
uname -srm; node --version 2>/dev/null || echo "node: not on PATH"

# Config directory
CFG="${COPILOT_HOME:-$HOME/.copilot}"
ls -la "$CFG" 2>&1

# Auth
gh auth status 2>&1 | sed 's/gho_[A-Za-z0-9_]*/gho_***REDACTED***/g'

# MCP / plugins (CLI subcommands, non-interactive)
copilot mcp --help >/dev/null 2>&1 && copilot mcp list 2>&1 | head -40
copilot plugin --help >/dev/null 2>&1 && copilot plugin list 2>&1 | head -40
```

### Step 2 — Run the check battery

Evaluate each check below. For each, assign a **status**, a one-line
**finding**, and (if WARN/FAIL) a **fix** command. Run all checks even if
earlier ones fail.

Status legend: `PASS` ✅ · `WARN` ⚠️ · `FAIL` ❌ · `INFO` ℹ️

1. **CLI version & updates**
   - PASS if `copilot --version` prints and reports no newer version.
   - WARN if a newer version is available, or the version string can't be
     read. Fix: `copilot update`.

2. **Install location & duplicates**
   - PASS if exactly one `copilot` on PATH.
   - WARN if `type -a copilot` shows multiple entries (shadowing risk).
     Report all paths so the user can remove the stale one.

3. **Authentication**
   - PASS if `gh auth status` shows a logged-in account with a token, OR the
     Copilot CLI itself reports an active login.
   - FAIL if not logged in. Fix: `copilot login` (and/or `gh auth login`).
   - Always redact the token.

4. **Config JSON validity** — for each of `config.json`, `settings.json`,
   `permissions-config.json`, `mcp-config.json` under `<config>`:
   - PASS if the file parses. NOTE: these are **JSONC** — Copilot writes
     `//` comments and trailing commas (especially in the auto-managed
     `config.json`). Do NOT use a strict parser like `python -m json.tool`;
     it produces false positives. Strip comments/trailing commas first.
   - FAIL only if it still won't parse after that. Fix: restore from a
     sibling `*.bak.<timestamp>` if one exists, else hand-repair.
   - INFO if absent (some are optional).
   - Validate with this JSONC-tolerant check:
     ```bash
     for f in config.json settings.json permissions-config.json mcp-config.json; do
       p="$CFG/$f"
       [ -f "$p" ] || { echo "$f: absent"; continue; }
       python3 - "$p" <<'PY'
import json, re, sys, os
s = open(sys.argv[1]).read()
s = re.sub(r'/\*.*?\*/', '', s, flags=re.S)   # block comments
s = re.sub(r'(^|\s)//[^\n]*', '', s)          # line comments
s = re.sub(r',(\s*[}\]])', r'\1', s)          # trailing commas
name = os.path.basename(sys.argv[1])
try:
    json.loads(s); print(f"{name}: valid")
except Exception as e:
    print(f"{name}: INVALID JSON -> {e}")
PY
     done
     ```

5. **MCP servers**
   - PASS if `mcp-config.json` is valid and `copilot mcp list` shows the
     configured servers without errors.
   - WARN if a configured server fails to start / is unreachable, or if the
     config references a command not found on PATH. Report each server.

6. **Permissions sanity**
   - INFO/WARN: inspect `permissions-config.json`. WARN if it grants
     blanket access (e.g. allow-all tools/paths/urls) so the user is aware of
     the attack surface. Never auto-narrow it.

7. **Skills loaded**
   - List `<config>/skills/`. PASS if entries resolve.
   - WARN for any **broken symlink** (target missing). Report the dangling
     link. Fix: re-create or remove the link.
   - INFO: also note repo-level `.github/skills/` if inside a git repo.

8. **Agents loaded**
   - List `<config>/agents/`. Same broken-symlink check as skills.

9. **Instruction resolution**
   - INFO: report which instruction sources exist and would load:
     `AGENTS.md` (git root & cwd), `.github/instructions/**/*.instructions.md`,
     `.github/copilot-instructions.md`, `<config>/copilot-instructions.md`,
     `<config>/instructions/**`. WARN only on an unreadable/permission-denied
     file.

10. **Disk hygiene**
    - Measure sizes of `<config>/logs/`, `session-store.db` (+ `-wal`/`-shm`),
      `embedding-cache.db` (+ `-wal`/`-shm`).
    - WARN if `logs/` is large (e.g. > ~200 MB) or a `*-wal` file is large
      (e.g. > ~256 MB), which usually means a WAL that never checkpointed.
    - Report sizes with:
      ```bash
      du -sh "$CFG/logs" 2>/dev/null
      ls -lh "$CFG"/*.db "$CFG"/*.db-wal "$CFG"/*.db-shm 2>/dev/null
      ```

11. **Terminal multiline**
    - INFO: note whether multiline input (shift+enter) is configured. If the
      user reports newline issues, suggest `/terminal-setup`.

### Step 3 — Apply fixes (only if `apply_fixes=true`)

Default is `apply_fixes=false` → report only. When the user opts in, you may
run ONLY these safe fixes, and only for checks that actually failed/warned.
Confirm each before running.

| Finding | Safe fix |
|---|---|
| Newer CLI version available | `copilot update` |
| Logged out | `copilot login` |
| Broken skill/agent symlink | remove the dangling link (`rm` the symlink only) |
| Oversized DB WAL | checkpoint the WAL: `sqlite3 "$CFG/session-store.db" 'PRAGMA wal_checkpoint(TRUNCATE);'` (only if `sqlite3` is available and the CLI is **not running**) |
| Old logs | offer to archive/remove logs older than N days under `<config>/logs/` |

Never auto-edit `config.json`, `settings.json`, `permissions-config.json`, or
`mcp-config.json`. Malformed config is reported with a manual-repair pointer
(and a note about any existing `*.bak.*` sibling).

### Step 4 — Emit the report

Print exactly this shape (fill in real values; omit a row only if a check was
out of `scope`):

```
COPILOT DOCTOR
==============
cli:        <version>  (<up-to-date | update available: vX.Y.Z>)
binary:     <path>     (<single | N installs — shadowing>)
runtime:    <uname>  node <version|absent>
config dir: <path>

CHECKS
  [✅] version & updates    <finding>
  [✅] install location     <finding>
  [❌] authentication       <finding>
  [✅] config json          config.json ok · settings.json ok · ...
  [⚠️] mcp servers          <finding>
  [ℹ️] permissions          <finding>
  [⚠️] skills               <finding> (e.g. "12 ok, 1 broken: <name>")
  [✅] agents               <finding>
  [ℹ️] instructions         <finding>
  [⚠️] disk hygiene         logs <size> · session-store.db <size> · wal <size>
  [ℹ️] terminal multiline   <finding>

SUMMARY
  pass: <n>   warn: <n>   fail: <n>

SUGGESTED FIXES
  - <check>: <copy-paste command>
  - <check>: <copy-paste command>

(run with apply_fixes=true to apply the safe fixes above)
```

## Anti-patterns to avoid (in YOUR diagnostic work)

1. **Mutating config by default** — doctor is read-only unless the user opts
   in. Never "helpfully" rewrite JSON or trim files without consent.
2. **Printing secrets** — always redact tokens (`gho_***`), never echo full
   `config.json`/auth contents.
3. **Aborting on first failure** — a missing file is a finding; keep going and
   produce the full report.
4. **Assuming the install method** — detect Homebrew vs npm vs other from the
   resolved path; don't hardcode `brew upgrade`.
5. **Checkpointing a live DB** — never run a WAL checkpoint while the CLI is
   actively using the DB; warn instead.
6. **Inventing checks that need network/org access** — keep checks local;
   GitHub-side policy state isn't observable here.

## Configuration parameters

| Parameter | Default | Effect |
|---|---|---|
| `apply_fixes` | `false` | If `true`, run the safe fixes in Step 3 (with confirmation). |
| `scope` | `all` | Limit checks, e.g. `scope=auth,mcp,disk`. |

Example invocations:

```
run doctor
run doctor apply_fixes=true
run doctor scope=auth,mcp
```

## See also

- Copilot CLI interactive commands that overlap with individual checks:
  `/env` (loaded skills/agents/MCP/instructions), `/version`, `/update`,
  `/mcp`, `/lsp`, `/usage`, `/settings show`, `/terminal-setup`.
- `kb-revalidate` skill — periodic freshness checks for a different surface.
