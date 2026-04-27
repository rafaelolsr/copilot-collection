# Pipeline template via `extends:`

> **Last validated**: 2026-04-26
> **Confidence**: 0.91

## When to use this pattern

Multiple pipelines share the same overall shape (build → test → deploy) with parametrized differences (which app, which environments). `extends:` gives you a single source of truth for the shape.

For just a few shared steps, use a steps template (`template: file.yml`). For the whole pipeline structure, use `extends:`.

## Example: deploy template for any service

`templates/pipelines/standard-app.yml`:

```yaml
parameters:
  - name: serviceName
    type: string
  - name: appType
    type: string
    default: 'webapp'
    values: ['webapp', 'function', 'container']
  - name: deployStages
    type: object
    default: []
  - name: enableEvalSmoke
    type: boolean
    default: true
  - name: pythonVersion
    type: string
    default: '3.12'

variables:
  - name: serviceConnection
    value: 'wif-shared'

stages:
  - stage: Build
    displayName: Build & Test
    jobs:
      - job: BuildJob
        displayName: Build ${{ parameters.serviceName }}
        pool:
          vmImage: ubuntu-latest
        steps:
          - task: UsePythonVersion@0
            inputs:
              versionSpec: ${{ parameters.pythonVersion }}
            displayName: Use Python ${{ parameters.pythonVersion }}

          - script: |
              set -euo pipefail
              pip install -e ".[dev]"
              ruff check
              mypy src/
              pytest -m "not eval"
            displayName: Lint, type-check, test

          - ${{ if eq(parameters.enableEvalSmoke, true) }}:
            - script: |
                set -euo pipefail
                pytest -m "eval and smoke"
              displayName: Eval smoke test

          - publish: $(Build.SourcesDirectory)/dist
            artifact: ${{ parameters.serviceName }}-build

  - ${{ each stage in parameters.deployStages }}:
    - stage: Deploy_${{ stage.name }}
      displayName: Deploy to ${{ stage.environment }}
      dependsOn: Build
      condition: |
        and(
          succeeded(),
          eq(variables['Build.SourceBranch'], 'refs/heads/main')
        )
      jobs:
        - deployment: Deploy_${{ stage.name }}
          displayName: Deploy ${{ parameters.serviceName }} to ${{ stage.environment }}
          environment: ${{ stage.environment }}
          pool:
            vmImage: ubuntu-latest
          strategy:
            runOnce:
              deploy:
                steps:
                  - download: current
                    artifact: ${{ parameters.serviceName }}-build

                  - ${{ if eq(parameters.appType, 'webapp') }}:
                    - task: AzureWebApp@1
                      inputs:
                        azureSubscription: $(serviceConnection)
                        appName: ${{ stage.appName }}
                        package: $(Pipeline.Workspace)/${{ parameters.serviceName }}-build/*.zip
                      displayName: Deploy webapp

                  - ${{ if eq(parameters.appType, 'function') }}:
                    - task: AzureFunctionApp@2
                      inputs:
                        azureSubscription: $(serviceConnection)
                        appName: ${{ stage.appName }}
                        package: $(Pipeline.Workspace)/${{ parameters.serviceName }}-build/*.zip
                      displayName: Deploy function app

                  - ${{ if eq(parameters.appType, 'container') }}:
                    - task: AzureCLI@2
                      inputs:
                        azureSubscription: $(serviceConnection)
                        scriptType: bash
                        scriptLocation: inlineScript
                        inlineScript: |
                          az containerapp update \
                            --name ${{ stage.appName }} \
                            --resource-group ${{ stage.resourceGroup }} \
                            --image ${{ stage.containerImage }}
                      displayName: Deploy container app
```

## Consuming the template

Pipeline file in a service repo:

```yaml
# api-service/azure-pipelines.yml
trigger:
  branches:
    include: [main]

resources:
  repositories:
    - repository: pipeline-templates
      type: git
      name: 'platform/pipeline-templates'        # project/repo
      ref: refs/heads/main

extends:
  template: templates/pipelines/standard-app.yml@pipeline-templates
  parameters:
    serviceName: api-service
    appType: webapp
    enableEvalSmoke: true
    pythonVersion: '3.12'
    deployStages:
      - { name: dev, environment: dev, appName: api-service-dev }
      - { name: staging, environment: staging, appName: api-service-staging }
      - { name: prod, environment: production, appName: api-service-prod }
```

For another service:

```yaml
# function-service/azure-pipelines.yml
extends:
  template: templates/pipelines/standard-app.yml@pipeline-templates
  parameters:
    serviceName: notification-function
    appType: function
    enableEvalSmoke: false                      # this one has no LLM evals
    deployStages:
      - { name: dev, environment: dev, appName: notification-fn-dev }
      - { name: prod, environment: production, appName: notification-fn-prod }
```

Both pipelines now share build / test / deploy logic. Updates to the template propagate to all consumers.

## Cross-repo template referencing

Templates can live in a separate repo (recommended for shared platform):

```yaml
resources:
  repositories:
    - repository: <alias>
      type: git
      name: <project>/<repo-name>
      ref: refs/heads/main                       # or a tag for stability

extends:
  template: <path/to/template.yml>@<alias>
```

Pin to a tag for stability:

```yaml
resources:
  repositories:
    - repository: pipeline-templates
      type: git
      name: 'platform/pipeline-templates'
      ref: refs/tags/v1.5.0                      # pinned version
```

When the template repo updates, only consumers explicitly bumping the tag see changes. Avoids "I changed the template and 10 pipelines broke at midnight".

## Conditional inserts (`${{ if ... }}`)

Compile-time conditions (not runtime). Resolved when the pipeline is parsed.

```yaml
steps:
  - ${{ if eq(parameters.enableEvalSmoke, true) }}:
    - script: pytest -m eval
      displayName: Eval smoke
```

The step is INCLUDED in the resulting YAML only if the condition is true. If false, the step doesn't exist at runtime.

For RUNTIME conditions (variable values), use `condition:`:

```yaml
- script: pytest -m eval
  condition: eq(variables['Build.Reason'], 'Schedule')
```

Both have their place. Compile-time = "is this step relevant for this pipeline at all?". Runtime = "should this step execute on this run?".

## Loops with `${{ each ... }}`

```yaml
- ${{ each stage in parameters.deployStages }}:
  - stage: Deploy_${{ stage.name }}
    ...
```

The template generates one stage per item in the parameter object. Useful for multi-environment deploys without duplicating the stage block.

## Steps templates (alternative to extends)

For just shared steps, use a smaller `template: file.yml` reference:

`templates/steps/python-test.yml`:
```yaml
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

Use:
```yaml
steps:
  - template: templates/steps/python-test.yml
    parameters:
      pythonVersion: '3.13'
```

`extends:` for the WHOLE pipeline shape; `template:` for inserted block. Both are valid for different scopes.

## Done when

- One template per logical pipeline shape (build/test/deploy app, scheduled sync, library publish, etc.)
- Templates pinned by tag for production
- Parameters documented with `type:` and `default:`
- Compile-time `if` for relevance; runtime `condition` for execution
- Templates committed to a dedicated `pipeline-templates` repo
- Consumers reviewed when template breaks (subscribe to template repo)

## Anti-patterns

- Inline pipelines that duplicate 80%+ of another pipeline (refactor to template)
- Templates that take 20+ parameters (signal it's too generic; split into specific templates)
- Templates referencing `refs/heads/main` in production (drift on every template change)
- Templates with no `displayName` on steps (hard to debug consumers)
- Using `extends:` for tiny shared steps (overkill — use `template:`)
- Hardcoded `serviceConnection` in template (use parameter or pinned variable group)

## See also

- `concepts/pipeline-yaml-structure.md`
- `patterns/pipeline-with-wif.md`
- `patterns/scheduled-pipeline-with-cron.md`
- `anti-patterns.md` (item 7)
