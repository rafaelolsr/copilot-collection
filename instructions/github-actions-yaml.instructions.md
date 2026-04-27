---
name: github-actions-yaml
description: |
  Standards for GitHub Actions workflow YAML. Auto-applied to
  .github/workflows/*.yml. Enforces explicit triggers, OIDC auth instead
  of long-lived secrets, action version pinning to commit SHAs, minimal
  permissions, no inline secrets, fail-fast scripts, concurrency control.
applyTo: ".github/workflows/*.yml,.github/workflows/*.yaml"
---

# GitHub Actions YAML standards

When generating or modifying GitHub Actions workflows, follow these rules.

## Authentication — order of preference

| Auth | When |
|---|---|
| **OIDC (federated identity)** to AWS / Azure / GCP | Default for cloud access |
| **GitHub App token** | When acting on the repo / org |
| **Fine-grained PAT** | Cross-repo scenarios; rotate quarterly |
| **Classic PAT** | Last resort; document expiry |

NEVER:
- Long-lived cloud credentials (AWS access keys, Azure SP secrets) in secrets
- PATs in env without `secrets:` reference
- `permissions: write-all` (over-broad)

## Required structure

```yaml
name: <Display Name>             # required; appears in UI

on:                              # explicit triggers — never empty
  pull_request:
    branches: [main]
    paths: ['src/**']
  push:
    branches: [main]
    paths: ['src/**']
  schedule:
    - cron: "0 8 * * *"          # UTC always
  workflow_dispatch:             # manual trigger
    inputs:
      env:
        type: choice
        options: [dev, staging, prod]

permissions:                      # minimal scope; default is read-all-write-all
  contents: read
  pull-requests: write           # only what the workflow needs

concurrency:                      # cancel in-progress on new push
  group: ${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: true

jobs:
  build:
    runs-on: ubuntu-latest        # explicit; never rely on default
    timeout-minutes: 15           # cap to prevent runaway costs
    steps: ...
```

## Action version pinning

Pin to a **full commit SHA** for security (tags can be moved):

```yaml
# CORRECT (SHA-pinned)
- uses: actions/checkout@b4ffde65f46336ab88eb53be808477a3936bae11  # v4.1.1

# OK (major version, less secure)
- uses: actions/checkout@v4

# WRONG (latest)
- uses: actions/checkout@main
- uses: actions/checkout@latest
```

Use `dependabot` to keep SHAs current:

```yaml
# .github/dependabot.yml
version: 2
updates:
  - package-ecosystem: github-actions
    directory: /
    schedule:
      interval: weekly
```

## Permissions — least privilege

Default to `read-all`; expand only what each job needs:

```yaml
permissions:
  contents: read

jobs:
  publish-release:
    permissions:                  # job-level overrides
      contents: write             # to create the release
      packages: write             # to publish to GHCR
```

Common minimal combos:
- Read-only CI: `{contents: read}`
- Posts PR comments: `{contents: read, pull-requests: write}`
- Creates releases: `{contents: write}`
- OIDC to cloud: `{id-token: write, contents: read}`

## Secrets

```yaml
# CORRECT — referenced from secrets
env:
  LLM_API_KEY: ${{ secrets.LLM_API_KEY }}

# WRONG — value embedded
env:
  LLM_API_KEY: sk-live-redacted-example
```

NEVER use `${{ secrets.X }}` in `run:` directly — pass via `env:` so it
doesn't appear in command history:

```yaml
# CORRECT
- env:
    API_KEY: ${{ secrets.API_KEY }}
  run: curl -H "Authorization: Bearer $API_KEY" ...

# WRONG (key visible in process listing)
- run: curl -H "Authorization: Bearer ${{ secrets.API_KEY }}" ...
```

## OIDC to Azure (no SP secret)

```yaml
permissions:
  id-token: write              # required for OIDC
  contents: read

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: azure/login@<sha>
        with:
          client-id: ${{ secrets.AZURE_CLIENT_ID }}
          tenant-id: ${{ secrets.AZURE_TENANT_ID }}
          subscription-id: ${{ secrets.AZURE_SUBSCRIPTION_ID }}
```

(The Entra app needs a federated credential pointing at this repo's
`refs/heads/main`.)

## Concurrency control

For deploy workflows:
```yaml
concurrency:
  group: deploy-${{ github.ref }}
  cancel-in-progress: false      # don't cancel mid-deploy
```

For PR validation:
```yaml
concurrency:
  group: pr-${{ github.head_ref }}
  cancel-in-progress: true       # new push cancels old run
```

## Fail-fast bash

```yaml
- name: Run tests
  shell: bash
  run: |
    set -euo pipefail
    pip install -e ".[dev]"
    pytest -m "not eval"
```

`set -euo pipefail` is mandatory in any non-trivial bash step:
- `e` exit on error
- `u` exit on unset variable
- `o pipefail` exit on pipe failure

## Step `name`

Every step has a human-readable `name`:

```yaml
# CORRECT
- name: Install dependencies
  run: pip install -e ".[dev]"

# WRONG (UI shows raw `run` command)
- run: pip install -e ".[dev]"
```

## Caching

```yaml
- uses: actions/setup-python@<sha>
  with:
    python-version: "3.12"
    cache: pip                    # caches pip dir automatically
```

For uv:
```yaml
- uses: astral-sh/setup-uv@<sha>
  with:
    enable-cache: true
```

## Anti-patterns to flag

| Pattern | Severity |
|---|---|
| Action pinned to `@main` or `@latest` | WARN — supply chain risk |
| Action pinned to a tag (`@v1`) on a security-sensitive workflow | INFO — prefer SHA |
| `permissions: write-all` or omitted | WARN — over-broad |
| Secret in `run:` instead of `env:` | WARN — visible in process listing |
| `${{ secrets.X }}` directly in script | WARN — same |
| Missing `timeout-minutes` on long jobs | WARN — runaway risk |
| No `concurrency:` on deploy / PR workflows | INFO |
| Cron without timezone comment | INFO |
| Step without `name:` | INFO — UI opacity |
| `set -e` in bash without `-uo pipefail` | INFO |
| Hardcoded subscription / resource IDs | WARN |
| Workflow file in `.github/workflows/` not auto-discoverable | INFO |
| OIDC for cloud auth not used (when available) | INFO |

## Validation

```bash
# Lint with actionlint
actionlint .github/workflows/*.yml

# Find unpinned actions
grep -E '@(main|master|latest)' .github/workflows/*.yml

# Find missing timeout-minutes
yq '.jobs[] | select(.["timeout-minutes"] == null) | .name' .github/workflows/*.yml
```

## See also

- `instructions/azure-pipeline-yaml.instructions.md` — for Azure DevOps
- [GitHub Actions security hardening](https://docs.github.com/en/actions/security-for-github-actions/security-guides/security-hardening-for-github-actions)
