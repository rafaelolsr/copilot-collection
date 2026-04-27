---
name: azure-pipeline-yaml
description: |
  Standards for Azure DevOps Pipeline YAML files. Auto-applied to
  azure-pipelines*.yml and pipeline templates. Enforces workload identity
  federation (no PATs / SP secrets), explicit triggers, displayName on
  every step, no hardcoded secrets, retry on flaky tasks, idempotent
  deployments.
applyTo: "azure-pipelines*.yml,azure-pipelines*.yaml,**/pipelines/**/*.yml,**/pipelines/**/*.yaml,**/.azuredevops/**/*.yml"
---

# Azure DevOps Pipeline YAML standards

When generating or modifying Azure Pipeline YAML, follow these rules.

## Authentication — order of preference

| Auth | When |
|---|---|
| **Workload Identity Federation (WIF)** | Default for new pipelines accessing Azure |
| **Managed Identity** (self-hosted agent on Azure VM) | Self-hosted runners |
| **Service Principal + Federated Credential** | When WIF unavailable |
| **Service Principal + Secret** | Legacy only; rotate quarterly |
| **Personal Access Token (PAT)** | NEVER in YAML |
| **System.AccessToken** | Self-callbacks within Azure DevOps only |

NEVER store a PAT or service-principal secret in pipeline YAML or in
Variable Groups not linked to Key Vault.

## Required frontmatter elements

Every pipeline file:

```yaml
trigger:                          # explicit; never default
  branches:
    include: [main]
  paths:
    include: ['src/**']           # path filters in monorepos

pr:                               # explicit; required for build validation
  branches:
    include: [main]
  drafts: false
  autoCancel: true

pool:                             # explicit; never rely on org default
  vmImage: ubuntu-latest

variables:                        # secrets via KV-linked Variable Groups
  - group: shared-prod-secrets
```

`trigger:` SHOULD be explicit even when you mean "default" — readers
shouldn't have to know defaults.

## Schedules

```yaml
schedules:
  - cron: "0 8 * * *"             # UTC always; document local-time interp
    displayName: Daily build (08:00 UTC = 04:00 EDT)
    branches: { include: [main] }
    always: true                  # run even when source unchanged
```

For schedule-only pipelines:
```yaml
trigger: none
pr: none
schedules: [...]
```

## Step rules

Every step has `displayName`:

```yaml
# CORRECT
- script: pytest -m "not eval"
  displayName: Run unit tests

# WRONG
- script: pytest -m "not eval"
# (UI shows "Run a one-line script" — opaque)
```

For tasks:
```yaml
- task: AzureCLI@2
  displayName: Deploy to staging
  inputs:
    azureSubscription: 'wif-staging-connection'
    scriptType: bash
    scriptLocation: inlineScript
    inlineScript: |
      set -euo pipefail
      az webapp deploy ...
```

Always `set -euo pipefail` at the top of inline bash to fail fast.

## Service connections

Service connections by name. NEVER hardcode subscription IDs:

```yaml
# CORRECT
- task: AzureCLI@2
  inputs:
    azureSubscription: 'wif-prod-rg-myapp'

# WRONG — hardcoded subscription
- task: AzureCLI@2
  inputs:
    azureSubscription: '12345678-1234-...'
```

Connection names should encode auth type + environment + scope:
- `wif-prod-rg-myapp` — workload identity federation, prod, my app's RG
- `sp-test-subscription` — service principal, test subscription

## Templates over duplication

Pipelines sharing 80%+ logic must use templates:

```yaml
# Repository reference
resources:
  repositories:
    - repository: pipeline-templates
      type: git
      name: 'platform/pipeline-templates'
      ref: refs/tags/v1.5.0       # pin to a tag

extends:
  template: templates/pipelines/standard-app.yml@pipeline-templates
  parameters:
    serviceName: my-app
    deployStages:
      - { name: dev, environment: dev }
      - { name: prod, environment: production }
```

## Conditions — explicit

```yaml
# Always explicit
- script: ./cleanup.sh
  condition: always()              # runs even on failure
  displayName: Cleanup

- script: ./deploy.sh
  condition: |
    and(
      succeeded(),
      eq(variables['Build.SourceBranch'], 'refs/heads/main')
    )
  displayName: Deploy to production
```

Don't omit `condition:` and assume `succeeded()` — be explicit.

## Retry on flaky tasks

```yaml
- task: AzureCLI@2
  retryCountOnTaskFailure: 3
  inputs: ...
```

Use sparingly — masks real flakiness. Retry on network-bound tasks
(HTTP fetches, transient API errors), not on tests or builds.

## Long inline scripts → external scripts

Inline `script:` blocks > 50 lines: extract to `scripts/<name>.sh` and
call via `script: ./scripts/<name>.sh`. Benefits:
- shellcheck can lint the file
- Tests can call it locally
- Diff is readable

## Pushing back to source repo

```yaml
- checkout: self
  persistCredentials: true        # required for push-back

- bash: |
    set -euo pipefail
    git config --global user.email "ci@example.com"
    git config --global user.name "CI Pipeline"
    git tag "v$(Build.BuildNumber)"
    git push --tags
  displayName: Push version tag
```

## Anti-patterns to flag

| Pattern | Severity |
|---|---|
| PAT in YAML or echoed in script | CRITICAL |
| Service principal secret hardcoded | CRITICAL |
| `trigger: '*'` (every branch) | WARN — wasteful |
| `trigger:` omitted (relies on default) | WARN — non-portable |
| No `pr:` block but used as build validation policy | CRITICAL — merge blocks forever |
| Step without `displayName` | INFO |
| Hardcoded subscription / resource IDs | WARN |
| `continueOnError: true` without comment | WARN — masks failures |
| Cron with no timezone documentation | INFO |
| Schedule without `always: true` (when needed) | INFO |
| Service connection name like `azure` (ambiguous) | INFO |
| Inline script > 50 lines | INFO — extract |
| No `set -euo pipefail` in bash | WARN — silent failures |
| Variable group with plain secrets (not KV-linked) | WARN |

## Validation

```bash
# Schema validation (Azure DevOps)
az pipelines run --debug --branch <branch> -y false  # dry-run

# Lint locally with yamllint
yamllint -d "{extends: relaxed}" azure-pipelines*.yml

# Find PATs / hardcoded secrets
grep -nE '(pat|password|secret|api.?key)\s*=\s*["\']' azure-pipelines*.yml
```

## See also

- `agents/azure-devops-specialist/` — for deep DevOps questions
- `instructions/github-actions-yaml.instructions.md` — for GitHub Actions
- [Azure Pipeline YAML schema](https://learn.microsoft.com/en-us/azure/devops/pipelines/yaml-schema/)
