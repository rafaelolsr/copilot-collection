# Triggers and schedules

> **Last validated**: 2026-04-26
> **Confidence**: 0.92

## The 4 trigger types

| Trigger | When |
|---|---|
| `trigger:` | Push / merge to specified branches (CI) |
| `pr:` | Pull request opened / updated against specified branches |
| `schedules:` | Cron-style scheduled |
| (Manual) | Always available; "Run pipeline" button |

A pipeline can have all four. Most have at least `trigger` + `pr`.

## CI trigger (`trigger:`)

```yaml
trigger:
  branches:
    include:
      - main
      - releases/*
    exclude:
      - releases/old-*
  paths:
    include:
      - src/**
      - tests/**
    exclude:
      - docs/**
      - '**/*.md'
  tags:
    include: ['v*']
```

Path filters are CRITICAL for monorepos — without them, every commit triggers every pipeline.

To DISABLE CI trigger entirely:
```yaml
trigger: none
```

This is correct for: scheduled-only pipelines, manual deploys, draft pipelines.

## PR trigger (`pr:`)

```yaml
pr:
  branches:
    include: [main]
  paths:
    include: ['src/**']
  drafts: false                      # don't run on draft PRs
  autoCancel: true                   # cancel previous run on new push
```

`pr:` is what gates merges via build validation policies. If a pipeline is required for PR validation (configured in branch policies) but `pr: none`, merges block forever.

## Schedules

```yaml
schedules:
  - cron: "0 8 * * *"                # 08:00 UTC daily
    displayName: Daily build
    branches:
      include: [main]
    always: true                     # run even if no code changes

  - cron: "0 0 * * 0"                # Sunday midnight UTC
    displayName: Weekly full eval
    branches:
      include: [main]
    always: true
```

Cron is in UTC by default. Specify timezone via comments / convention.

`always: true` runs even if no commits since last run. Without it, schedules can skip if nothing changed.

## Manual triggers (parameters)

```yaml
trigger: none
pr: none

parameters:
  - name: environment
    displayName: Target environment
    type: string
    default: dev
    values:
      - dev
      - staging
      - prod

  - name: dryRun
    displayName: Dry run
    type: boolean
    default: true

stages:
  - stage: Deploy
    jobs:
      - deployment: Deploy
        environment: ${{ parameters.environment }}
        strategy:
          runOnce:
            deploy:
              steps:
                - script: |
                    echo "Deploy to ${{ parameters.environment }}"
                    echo "Dry run: ${{ parameters.dryRun }}"
```

User clicks "Run pipeline" → parameter prompts → run with chosen values.

## Path filters in monorepos

```yaml
trigger:
  branches:
    include: [main]
  paths:
    include:
      - 'apps/api/**'
      - 'libs/shared/**'              # shared lib affects api
    exclude:
      - 'apps/api/README.md'

pr:
  branches:
    include: [main]
  paths:
    include:
      - 'apps/api/**'
      - 'libs/shared/**'
```

Pair every pipeline in a monorepo with path filters. Without them: every push to `main` triggers every pipeline = wasted CU + slow merges.

## Trigger overrides — `Build.Reason`

The variable `Build.Reason` tells you why the pipeline ran:
- `IndividualCI` — push triggered
- `BatchedCI` — multiple pushes batched
- `PullRequest` — PR triggered
- `Schedule` — cron triggered
- `Manual` — user clicked Run
- `ResourceTrigger` — another pipeline's completion triggered this

Use it to gate behavior:

```yaml
- script: ./run-full-suite.sh
  condition: in(variables['Build.Reason'], 'Schedule', 'Manual')
  displayName: Run full suite (nightly + manual only)
```

## Resource triggers

Trigger this pipeline when another pipeline / repo / package changes:

```yaml
resources:
  pipelines:
    - pipeline: upstream-build
      source: 'Upstream-CI'
      trigger:
        branches:
          include: [main]

trigger: none                          # disable normal CI
pr: none

# When upstream-build completes on main, this pipeline runs
```

Use for downstream-of-build flows: integration test triggered by build completion, deployment triggered by package publish.

## Auto-cancel on new push

```yaml
pr:
  branches:
    include: [main]
  autoCancel: true                     # default true; set false to keep running
```

`autoCancel: true` means: new push to a PR cancels the in-flight pipeline. Saves CU. Default in modern Azure DevOps.

## Path filter pitfalls

```yaml
paths:
  include: ['src']                    # NO — matches files literally named "src"
  include: ['src/**']                  # YES — recursive match
```

`**` is required for directory recursion. Without it, only the literal path matches.

```yaml
paths:
  exclude: ['**/*.md']                 # excludes all .md files
  include: ['src/**']                  # but include src/
```

Note: include + exclude — exclude wins for matched paths.

## Branch filter wildcards

```yaml
trigger:
  branches:
    include:
      - main
      - feature/*                       # any feature/X
      - 'releases/*'                    # quotes optional unless special chars
    exclude:
      - feature/dependabot-*            # exclude dependabot
```

`*` matches one segment; `**` doesn't typically apply to branches.

## Common bugs

- `trigger: '*'` — runs on every branch (rarely correct in production)
- Missing `trigger:` block → defaults to all branches (Azure DevOps Server) or main only (Azure DevOps Services); ALWAYS specify explicitly
- Schedule without `always: true` — skips when no commits
- Schedule cron with no timezone documented (UTC unless overridden; CET ≠ UTC)
- PR pipeline that ignores draft state but PR is still draft — wasted runs
- Path filter without `**` — most paths don't match
- Resource trigger pointing to wrong source pipeline name (case-sensitive!)

## See also

- `concepts/pipeline-yaml-structure.md`
- `patterns/scheduled-pipeline-with-cron.md`
- `anti-patterns.md` (items 4, 11, 18)
