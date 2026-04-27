# Scheduled pipeline with cron

> **Last validated**: 2026-04-26
> **Confidence**: 0.92

## When to use this pattern

Pipelines that run on a schedule, not on commits. Common cases:
- Nightly evals
- Daily wiki / compliance KB sync
- Hourly health checks
- Weekly cleanup / reports

## Implementation

```yaml
# Disable normal CI / PR triggers — schedule only
trigger: none
pr: none

schedules:
  - cron: "0 8 * * *"                    # 08:00 UTC daily
    displayName: Daily compliance sync
    branches:
      include: [main]
    always: true                          # run even if no commits since last run

parameters:
  - name: dryRun
    displayName: Dry run (no writes)
    type: boolean
    default: false

variables:
  - name: pythonVersion
    value: '3.12'
  - group: shared-prod-secrets           # Key Vault linked

pool:
  vmImage: ubuntu-latest

jobs:
  - job: ComplianceSync
    timeoutInMinutes: 60                  # cap runtime; cron jobs that hang block the next run

    steps:
      - task: UsePythonVersion@0
        inputs:
          versionSpec: $(pythonVersion)
        displayName: Use Python $(pythonVersion)

      - script: |
          set -euo pipefail
          pip install -e ".[dev]"
        displayName: Install dependencies

      - task: AzureCLI@2
        displayName: Run sync
        inputs:
          azureSubscription: 'wif-prod-connection'
          scriptType: bash
          scriptLocation: inlineScript
          inlineScript: |
            set -euo pipefail
            python scripts/sync_compliance_knowledge.py \
              --dry-run=${{ parameters.dryRun }} \
              --workspace=$(WORKSPACE_NAME) \
              --batch-size=100

      - publish: $(System.DefaultWorkingDirectory)/sync-report.json
        artifact: sync-report
        displayName: Publish sync report
        condition: always()                # publish even on failure
```

## Cron syntax

```
* * * * *
| | | | |
| | | | └── day of week (0-6, Sun=0)
| | | └──── month (1-12)
| | └────── day of month (1-31)
| └──────── hour (0-23)
└────────── minute (0-59)
```

Common patterns:

| Cron | Meaning |
|---|---|
| `0 8 * * *` | Daily at 08:00 UTC |
| `0 8 * * 1-5` | 08:00 UTC weekdays only |
| `0 */4 * * *` | Every 4 hours |
| `0 0 * * 0` | Sunday midnight UTC |
| `0 0 1 * *` | First of every month, midnight |
| `30 22 * * 5` | Friday 22:30 UTC |

Test cron expressions at https://crontab.guru/ before committing.

## Time zones

Azure Pipelines cron is **UTC by default** — no timezone option in YAML. Convert your local time once:
- 02:00 EST = 07:00 UTC (winter) / 06:00 UTC (summer — DST shifts)
- 09:00 BRT (Brazil) = 12:00 UTC year-round (no DST since 2019)

Document the timezone in `displayName`:

```yaml
schedules:
  - cron: "0 12 * * *"
    displayName: Daily 09:00 BRT compliance sync
```

DST-affected zones: schedule for whichever UTC offset matters more (usually winter). Or split into two schedules — one for DST, one for not — using `branches.include` filters.

## `always: true` — when to use

```yaml
schedules:
  - cron: "0 8 * * *"
    branches:
      include: [main]
    always: true                          # ← run even if no new commits
```

Without `always: true`: schedule triggers only if `main` has commits since the last run. Useful if you want to skip "nothing changed" runs.

For most cron jobs (nightly evals, daily syncs against external sources): `always: true` is what you want — the job's purpose isn't tied to source code commits.

## Long-running schedules

For jobs that take >1 hour, set `timeoutInMinutes`:

```yaml
jobs:
  - job: NightlyEvalSuite
    timeoutInMinutes: 240                 # 4 hours
    steps: [...]
```

Default is 60 min (varies by org settings). If your job hangs / runs forever, the next scheduled run waits — backlog grows.

For very long jobs (>4 hours), consider:
- Breaking into stages
- Using a self-hosted agent (no time limit)
- Splitting the work across parallel jobs

## Conditional logic based on `Build.Reason`

Some pipelines run on multiple triggers — use `Build.Reason` to branch:

```yaml
trigger:
  branches:
    include: [main]

schedules:
  - cron: "0 8 * * *"
    branches: { include: [main] }
    always: true

steps:
  - script: ./run-fast-suite.sh
    condition: in(variables['Build.Reason'], 'IndividualCI', 'BatchedCI', 'PullRequest')
    displayName: Fast tests (CI)

  - script: ./run-full-suite.sh
    condition: eq(variables['Build.Reason'], 'Schedule')
    displayName: Full suite (nightly)
```

## Notification on schedule failure

Schedule failures often go unnoticed (no PR to comment on). Configure notifications:

1. Project Settings → Notifications → New subscription
2. Filter: "A run is completed" + "Status = Failed" + "Pipeline = <your-pipeline>"
3. Recipients: dist list / on-call

Or programmatically post to Slack / Teams from the pipeline:

```yaml
- task: AzureCLI@2
  displayName: Notify on failure
  condition: failed()
  inputs:
    azureSubscription: $(serviceConnection)
    scriptType: bash
    scriptLocation: inlineScript
    inlineScript: |
      curl -X POST -H 'Content-type: application/json' \
        --data "{
          \"text\": \"Scheduled run failed: $(Build.BuildNumber)\\nLink: $(Build.BuildUri)\"
        }" \
        "$WEBHOOK_URL"
  env:
    WEBHOOK_URL: $(SlackWebhookUrl)
```

## Manual override / on-demand runs

Even with `trigger: none`, the "Run pipeline" button always works. For a parametrized cron job, manual runs let you:
- Re-run a missed schedule
- Run with `dryRun: true` to test
- Run with overridden parameters

## Common bugs

- Cron in local time (forgot UTC offset) — runs at unexpected hour
- DST shift surprises (2 AM runs become 3 AM in summer)
- `always: true` missing → schedule skips when source unchanged
- `branches.include` typo — schedule never matches
- `timeoutInMinutes` not set + slow run + slow runs back up
- No notification → silent failures
- Pipeline triggered by both schedule AND commit → unexpected `Build.Reason` mix
- Resource cleanup not run on failure (`condition: always()` missing)

## Done when

- Cron expression verified at crontab.guru
- Timezone documented in displayName
- `always: true` if the job should run regardless of source changes
- `timeoutInMinutes` set
- Failure notification configured
- `condition: always()` on cleanup steps
- Manual override path documented (parameters)

## Anti-patterns

- Cron in non-UTC time without conversion
- Schedule on a pipeline that also has CI trigger without `Build.Reason` branching
- Default 60-min timeout on a 90-min job (silent failures)
- No artifact / log on failure
- Hardcoded schedule that's hard to override (move to parameter or config)

## See also

- `concepts/triggers-and-schedules.md`
- `concepts/pipeline-yaml-structure.md`
- `patterns/pipeline-with-wif.md` — pair with WIF for auth
- `patterns/wiki-incremental-sync.md` — common scheduled job
- `anti-patterns.md` (items 11, 18)
