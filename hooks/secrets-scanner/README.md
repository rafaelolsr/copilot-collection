# secrets-scanner hook

Triggers at `sessionEnd`. Scans files modified during the Copilot session
for known secret patterns. Prints findings to stderr.

## What it scans for

Currently 22 pattern categories, including:

| Category | Examples |
|---|---|
| Anthropic API keys | `sk-ant-*` (40+ char tail) |
| OpenAI API keys | `sk-proj-*`, legacy `sk-*` |
| GitHub tokens | `ghp_*`, `gho_*`, `ghu_*`, `ghs_*`, `ghr_*`, `github_pat_*` |
| AWS keys | `AKIA*`, `ASIA*`, `aws_secret_access_key=...` |
| Azure storage | `AccountKey=...`, `DefaultEndpointsProtocol=https;AccountName=...` |
| Azure messaging | `SharedAccessKey=...` |
| DB connection strings | `mongodb://`, `postgres://`, `mysql://` with embedded creds |
| JWTs | `eyJ...` 3-part tokens (often public, flagged for review) |
| Private keys | `-----BEGIN (RSA \| EC \| OPENSSH) PRIVATE KEY-----` |
| Generic credentials | `password = "..."`, `api_key: "..."`, `Authorization: Bearer ...` |

## Severity levels

- **CRITICAL** — confirmed secret format (`sk-ant-`, `ghp_`, `AKIA`, etc.)
- **HIGH** — high-confidence pattern but possibly false positive (legacy
  `sk-*`, generic `Authorization: Bearer`)
- **MEDIUM** — pattern that might be intentional public data (JWT)

## Files

```
hooks/secrets-scanner/
├── README.md           # this file
├── hooks.json          # event registration
└── scan-secrets.sh     # the scanner
```

## Configuration via env vars

| Variable | Default | Effect |
|---|---|---|
| `SECRETS_SCAN_BASE_REF` | `origin/main` | Git ref to diff against for "changed files" |
| `SECRETS_SCAN_QUIET` | `1` | If `1`, silent on clean scan; `0` to print "clean" message |
| `SECRETS_SCAN_EXCLUDE` | `vendor/\|node_modules/\|.venv/\|.git/\|.copilot-mem/\|tests/fixtures/` | Regex of paths to skip |

## Sample output (with findings)

```
  [CRITICAL] Anthropic API key
      src/agent/client.py:42
      api_key = "sk-ant-abc123def456..."

  [CRITICAL] GitHub Personal Access Token (classic)
      .env:5
      GITHUB_TOKEN=ghp_xyzABC123...

  [HIGH] Hardcoded credential
      config/secrets.yaml:8
      password: "hunter2-not-actually-a-secret"

⚠️  SECRETS SCAN: 3 finding(s), 2 CRITICAL
    Review the matches above. If a credential leaked:
      1. Revoke it at the provider
      2. Remove from git history (`git filter-repo` or BFG)
      3. Rotate any dependent systems

    To suppress false positives: pre-commit hook with detect-secrets baseline
    See: https://github.com/Yelp/detect-secrets
```

Exit code: always 0 (informational hook). To hard-block commits, use a
pre-commit hook (`detect-secrets` or `gitleaks`) instead.

## Why non-blocking

The hook fires at `sessionEnd` — after the user has decided what they
want to do. Hard-blocking at this point is bad UX. The right place for
hard blocks is:

1. **Pre-commit hook** — catches before `git commit`
2. **CI** — catches before merge to main
3. **GitHub Secret Scanning** — catches after push (last line of defense)

This hook is the **first line** that catches things during AI-assisted
edits, before they make it to commit.

## Running manually

```bash
# Default (scan changed files vs origin/main)
.github/hooks/secrets-scanner/scan-secrets.sh

# Scan everything (ignore git diff)
unset SECRETS_SCAN_BASE_REF
cd /tmp/somedir-not-a-git-repo
/path/to/scan-secrets.sh

# Verbose
SECRETS_SCAN_QUIET=0 .github/hooks/secrets-scanner/scan-secrets.sh
```

## Tuning patterns

Edit `scan-secrets.sh`, the `PATTERNS` array. Format:

```bash
'<regex>|<description>|<severity>'
```

Add patterns specific to your stack. For example, an internal API key
pattern:

```bash
'mycorp_[a-z0-9]{32}|MyCorp internal API key|CRITICAL'
```

Test the pattern locally:

```bash
echo "mycorp_$(openssl rand -hex 16)" | grep -E 'mycorp_[a-z0-9]{32}'
```

## False positives

This is a regex-based scanner, so false positives happen:

- Test fixtures with fake-but-real-shape keys (already excluded by default)
- Documentation showing a credential format
- Comments containing example tokens

Solution: use a `.secrets-baseline` (detect-secrets) for known false
positives, or move them to a path that matches the `EXCLUDE` regex.

For real production use, layer this hook with:
- `detect-secrets` (pre-commit) — semantic baseline tracking
- `gitleaks` (CI) — broader pattern catalog
- GitHub Secret Scanning (push) — provider-issued revocation

## Disabling

```bash
# Per session: set throttle to silently skip
export SECRETS_SCAN_QUIET=0    # at minimum, see "no files to scan"

# Permanently: remove or rename the hook directory
rm -rf .github/hooks/secrets-scanner
```

## See also

- [detect-secrets](https://github.com/Yelp/detect-secrets) — baseline-tracking pre-commit hook
- [gitleaks](https://github.com/gitleaks/gitleaks) — broad-spectrum CI scanner
- [GitHub Secret Scanning](https://docs.github.com/en/code-security/secret-scanning) — provider-side detection
- `instructions/agent-md.instructions.md` — flags hardcoded secrets in agent files
- `instructions/azure-pipeline-yaml.instructions.md` — flags hardcoded secrets in pipelines
