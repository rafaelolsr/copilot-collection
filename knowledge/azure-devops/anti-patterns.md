# Azure DevOps — Anti-Patterns

> **Last validated**: 2026-04-26
> **Confidence**: 0.91
> Wrong / Correct pairs for every anti-pattern the agent flags on sight.

---

## 1. PAT in pipeline YAML or source code

Wrong:
```yaml
- script: |
    curl -H "Authorization: Basic $(echo :MY-PAT | base64)" \
      https://dev.azure.com/myorg/_apis/...
```

Correct: WIF + Entra bearer token.
```yaml
- task: AzureCLI@2
  inputs:
    azureSubscription: 'wif-prod'
    scriptType: bash
    scriptLocation: inlineScript
    inlineScript: |
      TOKEN=$(az account get-access-token --resource 499b84ac-1321-427f-aa17-267ca6975798 --query accessToken -o tsv)
      curl -H "Authorization: Bearer $TOKEN" https://dev.azure.com/myorg/_apis/...
```

Related: `concepts/auth-and-service-connections.md`

---

## 2. Service principal secret hardcoded

Wrong:
```yaml
variables:
  - name: AZURE_CLIENT_SECRET
    value: 'abc123...'
```

Correct: Variable Group linked to Key Vault.
```yaml
variables:
  - group: prod-secrets-kv
```

---

## 3. `displayName: Run script` (or missing displayName)

Wrong:
```yaml
- script: ./deploy.sh
```

Correct:
```yaml
- script: ./deploy.sh
  displayName: Deploy to production
```

Without displayName, the UI shows "Run a one-line script" and pipelines become opaque.

---

## 4. `trigger: '*'` (runs on every branch)

Wrong:
```yaml
trigger:
  - '*'
```

Why: every branch push triggers CI. Massive CU waste; noise in pipeline run history.

Correct:
```yaml
trigger:
  branches:
    include:
      - main
      - releases/*
```

Related: `concepts/triggers-and-schedules.md`

---

## 5. No `pool:` (uses default)

Wrong:
```yaml
jobs:
  - job: Build
    steps: [...]
```

Why: pipeline behavior depends on org default agent pool. Non-portable.

Correct:
```yaml
pool:
  vmImage: ubuntu-latest

jobs:
  - job: Build
    steps: [...]
```

---

## 6. `continueOnError: true` without explanation

Wrong:
```yaml
- script: ./flaky-test.sh
  continueOnError: true
```

Why: silently passes failed tests. Quality regression invisible.

Correct: only when truly desired AND documented.
```yaml
- script: ./scan-vulnerabilities.sh
  continueOnError: true
  displayName: 'Vulnerability scan (non-blocking — informational only)'
```

If a step is flaky, fix it or add retry. Don't paper over with `continueOnError`.

---

## 7. Hardcoded resource IDs / URLs

Wrong:
```yaml
- script: |
    az webapp deploy --name 'prod-app-eastus2-001' --resource-group 'rg-prod-eus2' ...
```

Correct: variables.
```yaml
variables:
  - name: appName
    value: 'prod-app-eastus2-001'
  - name: resourceGroup
    value: 'rg-prod-eus2'

- script: |
    az webapp deploy --name $(appName) --resource-group $(resourceGroup) ...
```

Or per-environment Variable Groups for promotion across dev/staging/prod.

---

## 8. `azureSubscription` named non-uniquely

Wrong:
```yaml
- task: AzureCLI@2
  inputs:
    azureSubscription: 'azure'                # which one???
```

Correct:
```yaml
- task: AzureCLI@2
  inputs:
    azureSubscription: 'wif-prod-rg-myapp'    # explicit purpose
```

Service connection names should encode auth type, environment, and scope.

---

## 9. Variable groups not linked to Key Vault

Wrong: Variable group with plaintext "secret" values.

Correct: Library → Variable groups → Link secrets from an Azure key vault as variables → select KV → pick secrets.

Then secrets refresh from KV at run time; rotating in KV is a no-op for the pipeline.

---

## 10. Self-hosted agent without resource cleanup

Wrong: pipeline downloads 5GB of build cache to a self-hosted agent every run, never cleans up. Disk fills.

Correct:
```yaml
- script: rm -rf /tmp/build-cache
  condition: always()
  displayName: Cleanup
```

Use `condition: always()` so cleanup runs even on failure.

---

## 11. Pipeline with no `pr:` block but expected to run on PRs

Wrong: pipeline has `trigger:` for `main`, used as a build-validation policy on `main`. Since no `pr:`, it runs on push to main but NOT on PR. Branch policy waits forever.

Correct:
```yaml
trigger:
  branches:
    include: [main]

pr:
  branches:
    include: [main]                            # MUST be present for build validation
```

Related: `patterns/build-validation-policy.md`

---

## 12. `pwsh:` / `script:` blocks > 50 lines

Wrong: 200-line bash script inline in YAML. Hard to test, hard to lint, no syntax highlighting in editors.

Correct: extract to a script file.
```yaml
- script: ./scripts/deploy.sh
  displayName: Deploy
```

```bash
# scripts/deploy.sh
#!/usr/bin/env bash
set -euo pipefail
# ... 200 lines ...
```

`shellcheck` runs on the file. Tests can call it locally.

---

## 13. No retry on flaky tasks

Wrong:
```yaml
- script: curl https://flaky-external-api.example.com/data
```

Correct:
```yaml
- task: AzureCLI@2
  retryCountOnTaskFailure: 3
  inputs: ...
```

Or for inline scripts, wrap in your own retry:
```bash
for i in 1 2 3; do
  curl ... && break || sleep $((i * 5))
done
```

---

## 14. Allowing requestor self-approval on `main`

Wrong: branch policy "Allow requestors to approve their own changes" = ON, minimum reviewers = 1.

Why: author opens PR, approves it, merges. No real review.

Correct: Self-approval OFF; minimum reviewers ≥ 2; or self-approval OFF + minimum 1 with required-from-team.

---

## 15. PR creation API without polling for completion

Wrong: bot creates PR, exits. Downstream automation assumes PR is merged.

Correct: either don't assume merge (let humans handle) OR poll `pullRequests/{id}` status until `completed`.

Related: `patterns/pr-creation-via-rest.md`

---

## 16. Wiki page POST without ETag handling

Wrong:
```python
await client.put(f"/wiki/.../pages?path={path}", json={"content": new_content})
# 412 → silently overwrites concurrent edit
```

Correct: read ETag, send `If-Match`, handle 412.
```python
existing = await get_page(...)
etag = existing[1]
response = await client.put(..., headers={"If-Match": etag}, json=...)
if response.status_code == 412:
    raise ConcurrentEditError(...)
```

Related: `concepts/wiki-and-pages-api.md`

---

## 17. `condition: succeeded()` everywhere

Wrong:
```yaml
- script: cleanup.sh
  condition: succeeded()
```

Why: cleanup never runs on failure. Resources leak.

Correct:
```yaml
- script: cleanup.sh
  condition: always()                         # explicit: even on failure
```

`succeeded()` is the default if condition is omitted. Set explicitly when:
- `always()` for cleanup / artifact upload on failure
- `failed()` for failure-only steps (notify on-call)
- `succeededOrFailed()` (rarely used)

---

## 18. Schedule cron with no timezone documented

Wrong:
```yaml
schedules:
  - cron: "0 8 * * *"
    displayName: Daily run
```

Correct:
```yaml
schedules:
  - cron: "0 8 * * *"
    displayName: Daily run (08:00 UTC = 04:00 EDT / 03:00 EST)
```

ADO cron is always UTC. Document the local-time interpretation in displayName.

---

## 19. `dependsOn` of a job that doesn't exist

Wrong:
```yaml
jobs:
  - job: B
    dependsOn: A                              # 'A' isn't defined anywhere
```

Caught by validation, but easy to write during refactors.

Correct: every `dependsOn` must match an actual `job:` / `stage:` / `deployment:` name in the same pipeline.

---

## 20. Pipeline pushes back to source repo without auth context

Wrong:
```yaml
- bash: |
    git tag "v$(Build.BuildNumber)"
    git push --tags
```

Why: default checkout doesn't persist credentials → push fails 401.

Correct:
```yaml
- checkout: self
  persistCredentials: true                     # required for push-back

- bash: |
    git config --global user.email "ci@example.com"
    git config --global user.name "CI Pipeline"
    git tag "v$(Build.BuildNumber)"
    git push --tags
  displayName: Push version tag
```

Or use System.AccessToken explicitly:
```yaml
- bash: |
    git remote set-url origin https://$SYSTEM_ACCESSTOKEN@dev.azure.com/<org>/<project>/_git/<repo>
    git push --tags
  env:
    SYSTEM_ACCESSTOKEN: $(System.AccessToken)
```

---

## See also

- `index.md`
- All `concepts/` and `patterns/`
