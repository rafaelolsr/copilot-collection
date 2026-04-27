# Build validation branch policy

> **Last validated**: 2026-04-26
> **Confidence**: 0.89

## When to use this pattern

Setting up a required CI pipeline that gates merges to a protected branch. The combination of `pr:` trigger in the pipeline + a "Build validation" branch policy is what makes CI non-bypassable.

## Two pieces required

1. **Pipeline** has `pr:` trigger targeting the protected branch
2. **Branch policy** "Build validation" references that pipeline as required

If only one is present:
- Only `pr:` block: pipeline runs but doesn't block merge
- Only branch policy: nothing triggers the pipeline; merge blocks indefinitely

## The pipeline (CI side)

```yaml
# azure-pipelines-ci.yml
trigger:
  branches:
    include: [main]
  paths:
    include: ['src/**', 'tests/**']

pr:
  branches:
    include: [main]                    # PR validation
  paths:
    include: ['src/**', 'tests/**']
  drafts: false                         # don't run on draft PRs
  autoCancel: true                      # cancel previous run on new push to PR

pool:
  vmImage: ubuntu-latest

variables:
  - name: pythonVersion
    value: '3.12'

jobs:
  - job: Validate
    displayName: Lint, type-check, test
    steps:
      - task: UsePythonVersion@0
        inputs:
          versionSpec: $(pythonVersion)

      - script: |
          set -euo pipefail
          pip install -e ".[dev]"
        displayName: Install

      - script: ruff check
        displayName: Lint (ruff)

      - script: ruff format --check
        displayName: Format check (ruff)

      - script: mypy src/
        displayName: Type check (mypy)

      - script: pytest -m "not eval and not integration"
        displayName: Unit tests
```

This pipeline:
- Triggers on PR to `main` (within `src/**` or `tests/**` paths)
- Doesn't run on draft PRs (saves CU)
- Auto-cancels previous PR runs on new pushes
- Runs lint + type-check + unit tests in one job

## The branch policy

UI: Repos → Branches → main → ⋯ → Branch policies → Build validation → +.

```
Build pipeline:        CI-Validate-Pipeline
Trigger:               Automatic
Path filter:           src/**;tests/**
Build expiration:      12 hours
Required:              Required (blocks merge)
Display name:          Build & Test
```

Or via REST API:

```python
async def add_build_validation(client, repo_id: str, pipeline_id: int, branch: str = "main"):
    body = {
        "isEnabled": True,
        "isBlocking": True,
        "type": {
            "id": "0609b952-1397-4640-95ec-e00a01b2c241",   # Build validation policy type
        },
        "settings": {
            "buildDefinitionId": pipeline_id,
            "queueOnSourceUpdateOnly": True,
            "manualQueueOnly": False,
            "displayName": "Build & Test",
            "validDuration": 720,                              # 12 hours
            "scope": [
                {
                    "repositoryId": repo_id,
                    "refName": f"refs/heads/{branch}",
                    "matchKind": "Exact",
                }
            ],
        },
    }
    await client._request(
        "POST",
        f"/policy/configurations?api-version=7.1",
        json=body,
    )
```

`buildDefinitionId` is the integer pipeline ID (Pipelines → your pipeline → URL contains `/_build?definitionId=N`).

## Multiple required pipelines

A protected branch can require multiple pipelines:
- `CI-Validate` — lint + tests
- `CI-Security-Scan` — vulnerability scan
- `CI-Eval-Smoke` — smoke evals if prompts changed

Add each as a separate Build validation policy. All must pass for merge.

For OPTIONAL pipelines (informational, not blocking):
```python
"isBlocking": False                                            # informational only
```

## Path filters in the policy

The branch policy has its OWN path filter (separate from the pipeline's `pr:` paths). They serve different purposes:

| Filter | Purpose |
|---|---|
| Pipeline `pr.paths` | Whether the pipeline triggers at all |
| Policy `paths` | Whether the policy applies to a given PR |

Common pitfall:
- Pipeline `pr.paths.include: ['src/**']`
- Policy paths: `src/**`
- PR touches only `docs/**` → pipeline doesn't run → policy doesn't trigger → policy passes vacuously → merge allowed

This is usually correct behavior (no code changed → no CI needed). But if you want CI required on EVERY PR regardless of path: remove the policy path filter and let the pipeline's path filter decide whether tests are meaningful.

## Build expiration

```
Build expiration: 12 hours
```

After 12 hours, the build is considered stale. New push to the PR re-runs CI.

Trade-off:
- Short expiration (1-3 hours): catches drift faster; more CU usage on slow PRs
- Long expiration (24+ hours): saves CU; allows merging old "approved" CI

12 hours is a good default for most projects. Critical / high-velocity branches: 4-6 hours.

## Status policies (alternative for external CI)

For CI tools OUTSIDE Azure DevOps (custom validators, third-party scanners), use status policies instead:

```python
# After your external check completes, post status to the PR
await client._request(
    "POST",
    f"/git/repositories/{repo_id}/pullRequests/{pr_id}/statuses",
    json={
        "state": "succeeded",                                  # or 'pending' / 'failed' / 'error'
        "description": "Security scan passed",
        "context": {
            "name": "security-scan",                            # name + genre = unique
            "genre": "external-ci",
        },
        "targetUrl": "https://my-scanner.example.com/run/abc",
    },
)
```

Then add a status policy:

```
Branch policy → + Add status policy
   Status to check: external-ci/security-scan
   Type: Required
```

Now merges block until the external system posts `succeeded`.

## Bypass for emergencies

Configure a "bypass policies" permission on the branch:

UI: Repos → Permissions → Branch → set "Bypass policies when pushing" to specific identities.

Grant SPARINGLY:
- On-call / SRE for production hotfixes
- Maybe release manager
- NEVER "All Users"
- NEVER service accounts that don't NEED to bypass

Audit log records every bypass — review monthly.

## Required reviewer interaction

```
Branch policies on main:
- Build validation: CI-Validate (required)
- Required reviewers: 2
- Required reviewers (specific): @security-team for src/auth/**
```

ALL must pass:
- 2 reviewers approve
- Security team approves changes to auth code (if applicable)
- CI-Validate passes

## Common bugs

- Pipeline has `pr:` but path filter excludes the changed paths → CI doesn't trigger → policy passes vacuously
- Branch policy required but pipeline has `pr: none` → merges block forever
- "Required reviewers" set to 1 + author can self-approve → effectively no review
- Build expiration too short for slow CI → constant re-runs on stale PRs
- Status policy name + genre case-sensitive (must match what's posted)
- Path filter on POLICY but not PIPELINE (or vice versa) → confusing skip behavior
- Bypass granted to a service principal that legitimately runs CI (over-broad permission)

## Done when

- Pipeline has explicit `pr:` block targeting protected branch
- Pipeline path filter matches what the policy expects
- Branch policy "Build validation" references the pipeline by ID
- "Required" checkbox on (not informational)
- Build expiration set (12h default)
- Tested by opening a PR and verifying CI must pass before merge enables
- Bypass permissions audited

## Anti-patterns

- Pipeline + policy added separately, never tested together (the canonical "merge blocks forever" failure)
- Build expiration left at default 999 hours (CI never re-runs on long-lived PRs)
- Status policy with mismatched name/genre between posting and policy (silent block)
- Required reviewers count exceeds team size (impossible to merge)
- Allowing self-approval on protected branches (defeats review)

## See also

- `concepts/branch-policies.md`
- `concepts/triggers-and-schedules.md` — `pr:` block details
- `concepts/azure-devops-rest-api.md` — policy type IDs
- `anti-patterns.md` (items 11, 14)
