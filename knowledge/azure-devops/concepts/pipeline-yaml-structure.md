# Pipeline YAML structure

> **Last validated**: 2026-04-26
> **Confidence**: 0.92
> **Source**: https://learn.microsoft.com/en-us/azure/devops/pipelines/yaml-schema/

## The hierarchy

```
pipeline (the file)
├── stages
│   └── jobs
│       └── steps
│           ├── script / pwsh / task
│           └── ...
```

Top-level: pipeline. Pipelines have stages. Stages have jobs. Jobs have steps. Each level adds isolation (separate agents, separate variable scopes).

For simple pipelines, you can skip stages and even jobs:

```yaml
# Minimal — implicit single stage and job
trigger: [main]

pool:
  vmImage: ubuntu-latest

steps:
  - script: echo "hello"
    displayName: Greet
```

## Full structure with all levels

```yaml
trigger:
  branches:
    include: [main]
  paths:
    include: ['src/**']

pr:
  branches:
    include: [main]
  paths:
    include: ['src/**']

variables:
  - name: pythonVersion
    value: '3.12'
  - group: shared-secrets                         # Variable Group (Key Vault linked)

pool:
  vmImage: ubuntu-latest

stages:
  - stage: Build
    displayName: Build & Test
    jobs:
      - job: BuildJob
        displayName: Build
        steps:
          - task: UsePythonVersion@0
            inputs:
              versionSpec: $(pythonVersion)
            displayName: Use Python $(pythonVersion)

          - script: |
              pip install -e ".[dev]"
              pytest -m "not eval"
            displayName: Install & Test

          - publish: dist/
            artifact: build-output

  - stage: Deploy
    dependsOn: Build
    condition: and(succeeded(), eq(variables['Build.SourceBranch'], 'refs/heads/main'))
    jobs:
      - deployment: DeployToProd
        displayName: Deploy to Production
        environment: production           # ← gates approvals here
        strategy:
          runOnce:
            deploy:
              steps:
                - download: current
                  artifact: build-output

                - task: AzureCLI@2
                  inputs:
                    azureSubscription: 'wif-prod'
                    scriptType: bash
                    scriptLocation: inlineScript
                    inlineScript: |
                      az webapp deploy --name prod-app --src-path build-output
                  displayName: Deploy to Web App
```

## Stages

Use stages when:
- Different jobs need to run in different orders / on different conditions
- You want approval gates between phases
- You want to parallelize subset of work

```yaml
stages:
  - stage: A
  - stage: B
    dependsOn: A                          # explicit dependency
  - stage: C
    dependsOn: A                          # parallel to B
  - stage: D
    dependsOn: [B, C]                     # waits for both
```

## Jobs

Jobs run on agents. A job is the unit of agent allocation — each job gets a fresh agent (unless `dependsOn` + `condition` chain into the same agent via job ordering).

```yaml
jobs:
  - job: Linux
    pool:
      vmImage: ubuntu-latest
    steps:
      - script: echo "Linux job"

  - job: Windows
    pool:
      vmImage: windows-latest
    steps:
      - script: echo "Windows job"

  # These two run in parallel by default
```

To force serial:
```yaml
jobs:
  - job: First
    steps: [...]
  - job: Second
    dependsOn: First
    steps: [...]
```

## Deployment jobs

Special job type for deploys — supports environments + approvals:

```yaml
- deployment: DeployToProd
  environment: production
  strategy:
    runOnce:
      deploy:
        steps: [...]
```

Strategies:
- `runOnce` — single deploy
- `rolling` — rolling across instances
- `canary` — canary deploys with progressive rollout

## Steps

Within a job, steps run in order on the same agent:

```yaml
steps:
  - script: echo "step 1"               # bash on linux, batch on windows
    displayName: Step 1
    name: step1                          # for output references

  - pwsh: Write-Host "step 2"           # PowerShell Core (cross-platform)
    displayName: Step 2

  - bash: echo "step 3"                  # explicit bash
    displayName: Step 3

  - task: AzureCLI@2                     # built-in task
    inputs:
      azureSubscription: 'service-connection'
      scriptType: bash
      scriptLocation: inlineScript
      inlineScript: az account show
    displayName: Verify Azure auth

  - checkout: self                       # check out repo
  - download: current                    # download artifact
  - publish: $(System.DefaultWorkingDirectory)/dist
    artifact: build-output
```

`displayName` is mandatory for clarity. Without it, the UI shows the raw task ref ("Run script@0") which tells nobody anything.

## Variables

Three sources, in increasing precedence:

```yaml
variables:
  # Inline
  - name: stage
    value: dev

  # Variable group (linked to Key Vault for secrets)
  - group: shared-prod-secrets

  # Set per-template
  - template: vars.yml
```

Reference: `$(VariableName)` in scripts; `variables.VariableName` or `variables['Variable.Name']` in conditions.

```yaml
- script: echo $(stage)                  # use in script
  condition: eq(variables['Build.SourceBranch'], 'refs/heads/main')
```

Predefined variables: `$(Build.SourceBranch)`, `$(Build.Reason)`, `$(System.AccessToken)`, `$(Agent.OS)`, etc.

## Conditions

Steps and stages skip if their condition is false:

```yaml
- script: echo "main only"
  condition: eq(variables['Build.SourceBranch'], 'refs/heads/main')

- script: echo "even if previous failed"
  condition: always()

- script: echo "only on PR"
  condition: eq(variables['Build.Reason'], 'PullRequest')

- script: echo "complex"
  condition: |
    and(
      succeeded(),
      eq(variables['Build.Reason'], 'Schedule'),
      ne(variables['stage'], 'dev')
    )
```

Common condition functions: `succeeded()`, `failed()`, `always()`, `eq()`, `ne()`, `and()`, `or()`, `not()`, `contains()`, `startsWith()`.

## Templates

Two kinds:

### Steps template

```yaml
# templates/steps/test.yml
parameters:
  - name: pythonVersion
    type: string
    default: '3.12'

steps:
  - task: UsePythonVersion@0
    inputs:
      versionSpec: ${{ parameters.pythonVersion }}

  - script: |
      pip install -e ".[dev]"
      pytest -m "not eval"
    displayName: Install & Test
```

```yaml
# main pipeline
steps:
  - template: templates/steps/test.yml
    parameters:
      pythonVersion: '3.13'
```

### Extends template (whole pipeline shape)

```yaml
# templates/pipelines/standard.yml
parameters:
  - name: serviceName
    type: string
  - name: deployStages
    type: object
    default: []

stages:
  - stage: Build
    jobs:
      - job: BuildJob
        steps:
          - script: echo "Build ${{ parameters.serviceName }}"

  - ${{ each stage in parameters.deployStages }}:
      - stage: Deploy_${{ stage.name }}
        dependsOn: Build
        jobs:
          - deployment: Deploy
            environment: ${{ stage.environment }}
            strategy:
              runOnce:
                deploy:
                  steps:
                    - script: echo "Deploying to ${{ stage.environment }}"
```

```yaml
# main pipeline
extends:
  template: templates/pipelines/standard.yml
  parameters:
    serviceName: my-app
    deployStages:
      - { name: dev, environment: dev }
      - { name: prod, environment: production }
```

`extends:` is for the "shape" of the whole pipeline. `template: file.yml` for inserted blocks.

## Pools

```yaml
pool:
  vmImage: ubuntu-latest                  # Microsoft-hosted

# OR
pool:
  name: 'self-hosted-pool'                # self-hosted

# OR per-job
jobs:
  - job: A
    pool: ubuntu-latest
  - job: B
    pool:
      name: 'self-hosted'
      demands:
        - Agent.OS -equals Linux
```

Use Microsoft-hosted unless: needs proxy access, custom tooling, large VM, or compliance requires self-hosted.

## Common bugs

- Steps without `displayName` (UI is opaque)
- `dependsOn:` referencing a non-existent stage / job (caught by validation)
- Variable used before definition
- Trying to share a working directory across jobs (each job = fresh agent; use artifacts)
- `condition` evaluating in unintended context (variable not set yet)
- Templates with too many parameters (becomes harder to maintain than direct YAML)
- `extends:` template with steps directly (use jobs/stages structure)

## See also

- `concepts/triggers-and-schedules.md`
- `concepts/auth-and-service-connections.md`
- `patterns/pipeline-template-extends.md`
- `anti-patterns.md` (items 3, 4, 12)
