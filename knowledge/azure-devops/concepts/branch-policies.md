# Branch policies

> **Last validated**: 2026-04-26
> **Confidence**: 0.91

## What branch policies do

Constraints applied to a branch (or branch pattern) that gate WHAT can merge into it. Configured in: Repos → Branches → branch → Branch policies.

For protected branches (typically `main` and `releases/*`), enable:
- Required reviewers
- Build validation (CI must pass)
- Linked work items
- Comment resolution
- Limit merge types

## The 6 typical policies

### 1. Minimum number of reviewers

```
Require a minimum number of reviewers: 2
[ ] Allow requestors to approve their own changes
[X] Reset code reviewer votes when there are new changes
[X] When new changes are pushed: reset votes
```

For solo / very small teams: 1 reviewer.
For real production code: 2.

Don't allow self-approval on `main` — reduces accidental merges.

### 2. Check for linked work items

```
[X] Require associated work items
    Type: required
```

Useful in projects using Azure Boards. Forces traceability.

### 3. Check for comment resolution

```
[X] Require comments to be resolved before completion
    Type: required
```

Prevents merging with unresolved review comments.

### 4. Limit merge types

```
[X] Squash merge
[ ] Merge (no fast-forward)
[ ] Rebase and fast-forward
[ ] Rebase with merge commit
[ ] Semi-linear merge
```

Squash is usually the cleanest. One PR = one commit on main.

### 5. Build validation

The most important policy:

```
+ Add build policy
   Build pipeline: Main-CI
   Trigger: Automatic
   Build expiration: 12 hours
   Required: Required (blocks merge)
   Filter path: src/**;tests/**
   Display name: Build & Test
```

The pipeline must pass before merge. Without this, anyone can merge without CI.

Configure ALL relevant CI pipelines as required: build, lint, security scans, eval-smoke (if used).

### 6. Required reviewers

Specific identities or groups must review:

```
+ Add automatic reviewer
   Reviewers: '@security-team' (when files match: 'src/auth/**')
   Type: required
   Activity: minimum number of reviewers from the group: 1
```

Use for:
- Security-sensitive code paths
- Cross-team dependencies
- Compliance-required reviews

## Configuration via API

For consistent policies across repos, automate via REST API:

```bash
# Set required reviewers count
curl -X POST \
  "https://dev.azure.com/$ORG/$PROJECT/_apis/policy/configurations?api-version=7.1" \
  -H "Authorization: Basic $AUTH" \
  -H "Content-Type: application/json" \
  -d '{
    "isEnabled": true,
    "isBlocking": true,
    "type": { "id": "fa4e907d-c16b-4a4c-9dfa-4906e5d171dd" },
    "settings": {
      "minimumApproverCount": 2,
      "creatorVoteCounts": false,
      "scope": [
        {
          "repositoryId": "<repo-id>",
          "refName": "refs/heads/main",
          "matchKind": "Exact"
        }
      ]
    }
  }'
```

Common policy `type` IDs:
- Required reviewers: `fa4e907d-c16b-4a4c-9dfa-4906e5d171dd`
- Build validation: `0609b952-1397-4640-95ec-e00a01b2c241`
- Comment resolution: `c6a1889d-b943-4856-b76f-9e46bb6b0df2`
- Work item linking: `40e92b44-2fe1-4dd6-b3d8-74a9c21d0c6e`

## Branch protection patterns

### Pattern A: GitHub-flow

```
main (protected)
   ↑
   └── feature/* (no protection)
       └── PR → main
```

Anyone pushes to feature branches. Merging to main requires PR + 2 reviewers + CI.

### Pattern B: Trunk-based with releases

```
main (protected — strict)
releases/* (protected — extra strict, requires release manager)
hotfix/* (protected — fast-track, fewer reviewers)
feature/* (no protection)
```

Different policies per branch pattern.

### Pattern C: GitFlow (legacy)

```
main (protected — only release manager)
develop (protected)
release/* (protected)
feature/* (no protection)
```

Heavier weight. Most teams move away from GitFlow.

## Policies on branch patterns

Apply policies to all branches matching a pattern:

```
Branch: refs/heads/releases/*
Policies:
  - Require 2 reviewers
  - Build: ReleaseValidation pipeline
  - Required reviewers: @release-team
```

## Bypass permissions

Sometimes branch protection blocks legitimate ops (urgent hotfix, emergency rollback). Configure bypass:

```
Repos → Permissions → set on branch:
  - Bypass policies when pushing: only specific identities
```

Granted to: release managers, on-call engineers. Audit logs track every bypass.

NEVER grant bypass to "everyone" or "build service" — defeats the policy.

## Pipeline-level vs policy-level

Confusing point: a YAML pipeline's `pr:` trigger and a branch policy "build validation" are different.

- Pipeline `pr:` block — pipeline runs on PRs targeting these branches
- Policy "build validation" — pipeline result blocks the merge

For required-CI-on-main:
1. Pipeline must have `pr: { branches: { include: [main] } }`
2. Branch policy must reference that pipeline as required

If only #1: pipeline runs, but merge can happen even on failure.
If only #2: build validation can't trigger, so merge blocks forever.

Both are needed.

## Status checks via REST

For external CI / custom validators, post status to PRs:

```python
import httpx

async def post_pr_status(client, repo_id, pr_id, status: str, description: str):
    """status: 'pending' | 'succeeded' | 'failed' | 'error'"""
    await client.post(
        f"/git/repositories/{repo_id}/pullRequests/{pr_id}/statuses",
        json={
            "state": status,
            "description": description,
            "context": {"name": "external-validator", "genre": "ci"},
            "targetUrl": "https://my-validator.example.com/run/123",
        },
    )
```

External status checks can also be required policies — same UI, "+ Add status policy" → context name + genre.

## Common bugs

- Build validation pipeline doesn't have `pr:` → never runs → merge blocks
- "Build validation" added without setting "Required" → CI runs, but doesn't block
- Path filter on build validation excludes the changed paths → CI doesn't trigger → policy passes vacuously
- Self-approval allowed on main + 1 reviewer min → author becomes their own reviewer
- Bypass granted to a service principal that should never bypass
- Branch pattern wrong (`refs/heads/main` vs `main` — context-sensitive)
- Comment resolution required + auto-mark "resolved" by bot → policy is theatre

## See also

- `concepts/pipeline-yaml-structure.md` — `pr:` triggers
- `concepts/triggers-and-schedules.md`
- `patterns/build-validation-policy.md`
- `anti-patterns.md` (items 11, 14)
