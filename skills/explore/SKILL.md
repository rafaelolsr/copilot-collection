---
name: explore
description: |
  Explores an unfamiliar codebase to build a mental model: identifies
  entry points, primary modules, build / test commands, dependencies,
  data flow, and conventions. Outputs a structured "codebase map"
  document. Designed for onboarding to a new repo, evaluating a fork
  before contributing, or auditing a repo before adopting it.

  Use when the user says: "explore this codebase", "I just cloned this
  repo, give me the overview", "what does this project do?", "onboard
  me to this code", "summarize the architecture", "is this fork still
  maintained?".

  Do NOT use for: writing code (this skill is read-only), reviewing
  changes (use code-review), or planning a feature in code you already
  understand.
license: MIT
allowed-tools: [shell]
---

# Explore

Read-only exploration of an unfamiliar codebase. Output is a structured
codebase map that helps a human (or another agent) get productive fast.

The skill does NOT modify code. It reads files, runs read-only commands
(`git log`, `find`, `grep`, dependency tree introspection), and produces
a markdown report.

## When to use

YES:
- New repo you've cloned and want to understand
- Open-source library you're considering adopting
- Codebase you'll be contributing to
- Auditing a fork to see if it diverged dangerously

NO:
- Codebase you already know well (waste of time)
- A single file (just read it)
- Building a project (use `make-plan` after exploring)

## Workflow

### Step 1 — Top-level survey

```bash
# Project root listing
ls -la

# Read the README first, always
cat README.md 2>/dev/null | head -100

# Top-level docs
ls docs/ 2>/dev/null
cat CONTRIBUTING.md 2>/dev/null | head -50

# License + governance
cat LICENSE 2>/dev/null | head -5
cat CODE_OF_CONDUCT.md 2>/dev/null | head -5
```

Capture:
- Project name + 1-line description
- License
- Last commit date (`git log -1 --format=%cd`)
- Whether the project looks active (recent commits) or stagnant

### Step 2 — Stack identification

Look for canonical files that identify the language / framework:

| File | Stack |
|---|---|
| `package.json` + `tsconfig.json` | TypeScript / Node |
| `package.json` + `next.config.js` | Next.js |
| `pyproject.toml` + `uv.lock` | Python (uv) |
| `pyproject.toml` + `poetry.lock` | Python (poetry) |
| `requirements.txt` | Python (pip) |
| `Cargo.toml` | Rust |
| `go.mod` | Go |
| `pom.xml` | Java (Maven) |
| `build.gradle` | Java/Kotlin (Gradle) |
| `Gemfile` | Ruby |
| `composer.json` | PHP |
| `*.csproj` / `*.sln` | C# / .NET |
| `azure-pipelines.yml` | Azure DevOps CI |
| `.github/workflows/*.yml` | GitHub Actions CI |
| `Dockerfile` | Containerized |
| `terraform/*` / `*.tf` | Infrastructure |
| `bicep/*` / `*.bicep` | Azure Bicep |
| `.tmdl` files | Power BI / Tabular |

Note multiple — most projects have several.

### Step 3 — Directory map

```bash
# Top 2 levels of structure (excluding noisy dirs)
find . -maxdepth 2 -type d \
  -not -path '*/\.*' \
  -not -path '*/node_modules*' \
  -not -path '*/__pycache__*' \
  -not -path '*/.venv*' \
  -not -path '*/dist*' \
  -not -path '*/build*' \
  | sort

# Count files per top-level dir (gives you sizing)
for d in */; do
    count=$(find "$d" -type f -not -path '*/\.*' | wc -l | tr -d ' ')
    printf "%6s  %s\n" "$count" "$d"
done | sort -rn
```

Capture the directory tree with one-line purpose annotations:

```
src/         # main application code
tests/       # pytest suite
infra/       # Azure ARM templates
scripts/     # utility scripts (deploy, sync)
docs/        # markdown documentation
```

### Step 4 — Entry points

Identify how the project is RUN:

```bash
# Python
grep -E '^(if __name__|def main)' **/*.py | head
grep -E '^\s*scripts\s*=\s*\{' pyproject.toml -A 5

# Node
cat package.json | jq '.scripts'

# Docker
cat Dockerfile | grep -E '^(CMD|ENTRYPOINT)'

# CLI tools / __main__
find . -name '__main__.py' -o -name 'cli.py' -o -name 'main.py' | head
```

Capture:
- How to run it (`uv run app`, `npm start`, `docker compose up`)
- How to test it (`pytest`, `npm test`)
- How to build it (`npm run build`, `cargo build --release`)

### Step 5 — Dependencies

```bash
# Python
grep -E '^[a-zA-Z]' pyproject.toml | grep -E '^\s*"' | head -20

# Node
cat package.json | jq '.dependencies | keys'
cat package.json | jq '.devDependencies | keys'

# Lockfile size hint (more deps = bigger surface)
wc -l package-lock.json yarn.lock pnpm-lock.yaml uv.lock 2>/dev/null
```

Capture key dependencies that signal the architecture:
- HTTP client (httpx, requests, axios)
- DB / ORM (sqlalchemy, prisma, mongoose, deltalake)
- Web framework (fastapi, express, next, django)
- LLM SDK (anthropic, openai, azure-ai-projects)
- Test runner (pytest, jest, vitest)
- Lint / format (ruff, eslint, prettier)

### Step 6 — Tests + CI

```bash
# Test layout
find . -type d -name 'test*' -not -path '*/\.*' | head
find . -name 'conftest.py' -o -name '*.test.ts' -o -name '*_test.go' | head

# CI configuration
ls .github/workflows/ 2>/dev/null
ls .azuredevops/ 2>/dev/null
ls .gitlab-ci* 2>/dev/null
```

Capture:
- Where tests live
- How CI runs (GitHub Actions, Azure Pipelines)
- Whether builds are passing (badges in README, last few CI runs)

### Step 7 — Conventions

Look for project-specific style:

```bash
# Linting + formatting
cat .editorconfig 2>/dev/null
cat pyproject.toml | grep -A 30 '\[tool.ruff' 2>/dev/null
cat .eslintrc* 2>/dev/null | head

# Pre-commit hooks
cat .pre-commit-config.yaml 2>/dev/null

# Git config
cat .gitattributes 2>/dev/null
```

Capture:
- Indent style (4 spaces, 2 spaces, tabs)
- Line endings (LF, CRLF)
- Naming conventions visible from the directory tree
- Commit message style (look at last 20 commits: `git log --oneline -20`)

### Step 8 — Health signals

```bash
# Activity
git log --since='6 months ago' --oneline | wc -l
git log --since='1 month ago' --oneline | wc -l

# Contributors
git shortlog -sne --all | head -10

# Open issues / PRs (if cloned with `gh`)
gh issue list --state open 2>/dev/null | head -5
gh pr list --state open 2>/dev/null | head -5
```

Capture:
- Commits / month (active vs stagnant)
- Bus factor (1 contributor or 10+?)
- Open PR / issue count (huge backlog = warning sign)

### Step 9 — Entry points for further exploration

End the report with "where to look next":
- For business logic: `src/<main_module>/`
- For data flow: `src/<pipeline_dir>/`
- For configuration: `<config_files>`
- For "how it's deployed": `infra/`, `Dockerfile`, `.github/workflows/`

## Output format

```markdown
# Codebase map: <project-name>

## TL;DR
<2-sentence summary: what it does, who's it for>

## Stack
- **Language(s):** Python 3.12, TypeScript
- **Framework(s):** FastAPI, Next.js
- **Build:** uv, npm
- **Test:** pytest, vitest
- **CI:** GitHub Actions
- **License:** MIT
- **Last commit:** 2026-04-25 (active — 47 commits last 30 days)

## Directory map
```
.
├── src/                # Python backend (FastAPI)
├── apps/web/           # Next.js frontend
├── infra/              # Bicep templates
├── tests/              # pytest suite
├── docs/               # docs site (Docusaurus)
└── scripts/            # CI helpers
```

## How to run

```bash
# Install
uv sync

# Run dev
uv run app

# Test
uv run pytest

# Build
npm run build
```

## Key dependencies
- `fastapi` 0.115 — web framework
- `anthropic` 0.40 — LLM SDK
- `pydantic` 2.10 — validation
- `pytest` 8.3 — tests

## Architecture (inferred)

<2-3 paragraphs describing how data flows from the user, through which
modules, to storage. Be honest about uncertainty.>

## Conventions

- 4-space Python indentation, ruff format on commit
- Conventional commits (`feat:`, `fix:`, ...)
- LF line endings (.gitattributes enforces)
- Strict mypy (`tool.mypy.strict = true` in pyproject)

## Health signals

| Signal | Value | Interpretation |
|---|---|---|
| Commits last 30 days | 47 | Active |
| Open issues | 23 | Manageable |
| Open PRs | 4 | Healthy |
| Bus factor (top contributor %) | 38% | OK |
| Last release | 2 weeks ago | Active releases |

## Entry points for deeper dives

- **Main business logic:** `src/agents/` — agent orchestration
- **Data flow:** `src/workflows/orchestrator.py`
- **API surface:** `src/api/main.py`
- **Tests for the above:** `tests/unit/test_orchestrator.py`

## Open questions / things to ask the team

- [ ] How is `src/legacy/` related to `src/agents/`? (Looks pre-refactor)
- [ ] Is the Lakehouse path in `infra/lakehouse.bicep` deployed?
- [ ] What's the actual prod model? README says GPT-4 but config has Claude.
```

## Anti-patterns to flag (in YOUR exploration)

1. **Skipping the README** — always read it FIRST, even if it's stale
2. **Not recording uncertainty** — if you don't know something, say so
3. **Inferring without evidence** — "this looks like a microservices
   architecture" without seeing service boundaries → say "appears to be
   X based on Y"
4. **Modifying anything** — this skill is READ-ONLY. If you need to run
   something, choose a non-mutating command.
5. **Not capturing health signals** — a beautifully-architected dead
   project is still dead

## Modes

- **Quick** (default) — 5-10 min scan, top-level only
- **Medium** — 20-30 min, drill into 2-3 key modules
- **Deep** — 1-2 hours, full architectural analysis (use `ultrathink`
  skill for the synthesis)

State which mode you're in at the top of the report.

## See also

- `make-plan` skill — once you understand the codebase, plan changes
- `ultrathink` skill — for synthesizing architectural insights
- `code-review` skill — for evaluating quality of specific files
- `agents/codebase-explorer` (community) — for AI-driven deep dives
