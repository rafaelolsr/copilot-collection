# Pipeline with workload identity federation (WIF)

> **Last validated**: 2026-04-26
> **Confidence**: 0.91

## When to use this pattern

Any new Azure-targeting pipeline. WIF removes the secret rotation burden and reduces the attack surface to zero (no secret in DevOps to leak).

## Setup once (per Entra app + service connection)

### Microsoft Entra app

1. Azure Portal → Microsoft Entra → App registrations → New registration
2. Note the Application (client) ID and Directory (tenant) ID
3. **DON'T** generate a client secret — WIF doesn't need one

### Federated credential

In the same app: Certificates & secrets → Federated credentials → Add credential

```
Federated credential scenario: Other issuer
Issuer:                       https://vstoken.dev.azure.com/<your-org-id>
Subject identifier:           sc://<your-org>/<project>/<service-connection-name>
Audience:                     api://AzureADTokenExchange
Name:                         ado-pipeline-wif
```

`<your-org-id>` is a GUID (Project Settings → About). The subject identifier MUST match the service connection you'll create — exact case + name.

### Azure RBAC

Grant the Entra app the role(s) it needs at the lowest scope:
- Single resource group: `Contributor` on RG
- Storage account: `Storage Blob Data Contributor`
- Key Vault: per-secret access

Avoid subscription-wide `Owner` — over-privileged.

### Service connection in Azure DevOps

Project Settings → Service connections → New → Azure Resource Manager → **Workload identity federation (manual)**:

```
Authentication method:        Workload identity federation
Subscription ID:              <azure-subscription>
Subscription name:            <name>
Service principal client ID:  <Entra app client ID>
Tenant ID:                    <Entra tenant ID>
Service connection name:      wif-prod-connection (matches federated credential subject)
```

After creating: open the connection → Manage Service Principal — copy the Issuer + Subject identifier shown. Verify they match what you configured in the federated credential.

## Pipeline YAML

```yaml
trigger:
  branches:
    include: [main]

pool:
  vmImage: ubuntu-latest

variables:
  - name: serviceConnection
    value: 'wif-prod-connection'
  - name: resourceGroup
    value: 'rg-prod'
  - name: appName
    value: 'my-app-prod'

stages:
  - stage: Deploy
    jobs:
      - deployment: DeployToProd
        environment: production               # for approval gates
        strategy:
          runOnce:
            deploy:
              steps:
                - task: AzureCLI@2
                  displayName: Verify Azure auth
                  inputs:
                    azureSubscription: $(serviceConnection)
                    scriptType: bash
                    scriptLocation: inlineScript
                    inlineScript: |
                      set -euo pipefail
                      az account show --query name -o tsv
                      az account show --query id -o tsv

                - task: AzureCLI@2
                  displayName: Deploy app
                  inputs:
                    azureSubscription: $(serviceConnection)
                    scriptType: bash
                    scriptLocation: inlineScript
                    inlineScript: |
                      set -euo pipefail
                      az webapp deploy \
                        --resource-group $(resourceGroup) \
                        --name $(appName) \
                        --src-path $(Pipeline.Workspace)/build/dist \
                        --type zip
```

The pipeline never sees a secret. Token exchange happens automatically when `AzureCLI@2` runs.

## Verifying WIF works

In a sandbox pipeline:

```yaml
- task: AzureCLI@2
  inputs:
    azureSubscription: 'wif-test-connection'
    scriptType: bash
    scriptLocation: inlineScript
    inlineScript: |
      az account show
      # Should print: subscription details, the SPN identity
      # If you see: "az login required" or "AADSTS...", WIF setup is wrong
```

Common failure: Subject identifier mismatch. Symptom: `AADSTS70021: No matching federated identity record found`. Fix: re-check `sc://<org>/<project>/<connection-name>` matches exactly (case-sensitive).

## Use from custom scripts (non-AzureCLI@2 tasks)

Sometimes you need the Azure access token directly:

```yaml
- task: AzureCLI@2
  inputs:
    azureSubscription: $(serviceConnection)
    scriptType: bash
    scriptLocation: inlineScript
    addSpnToEnvironment: true                  # exposes IDs to script
    inlineScript: |
      set -euo pipefail

      # Get an access token for a specific resource
      ACCESS_TOKEN=$(az account get-access-token \
        --resource https://storage.azure.com \
        --query accessToken -o tsv)

      # Use it
      curl -H "Authorization: Bearer $ACCESS_TOKEN" \
        "https://my-storage.blob.core.windows.net/container/file.json"
```

`addSpnToEnvironment: true` exposes `$servicePrincipalId`, `$servicePrincipalKey` (empty for WIF), `$tenantId`. Useful for SDKs that need them explicitly.

## Multiple environments

Create one Entra app + service connection PER environment:
- `wif-dev-connection` — federated credential subject `sc://<org>/<project>/wif-dev-connection`, RBAC on dev RG
- `wif-prod-connection` — separate Entra app, prod RG access

Don't share one Entra app across dev / prod — blast radius of a misconfig is contained.

## Deployment environment + approvals

```yaml
- deployment: DeployToProd
  environment: production
  strategy:
    runOnce:
      deploy:
        steps: [...]
```

In Azure DevOps: Pipelines → Environments → `production` → Approvals and checks → add reviewers. Production deployments now require approval before running.

Combined with WIF: secret-free auth + human approval gate on production deploys.

## Done when

- Service connection uses WIF (no secret)
- Federated credential subject matches `sc://<org>/<project>/<connection-name>` exactly
- Entra app RBAC at smallest viable scope
- Pipeline references service connection by name (variable)
- Production deploys gated by `environment:` + approvals
- Sandbox test verifies `az account show` works before going to prod

## Anti-patterns

- WIF + a fallback service principal secret on the same connection (defeats the purpose)
- Sharing an Entra app across environments
- Subject identifier with wrong case (Subject is case-sensitive)
- Granting Subscription Contributor instead of Resource Group Contributor
- No approval check on `environment: production`
- Service connection named ambiguously (e.g., `azure` — what subscription?)
- Pipeline that hardcodes subscription ID (use service connection)

## See also

- `concepts/auth-and-service-connections.md`
- `concepts/pipeline-yaml-structure.md` — environments + deployments
- `concepts/branch-policies.md` — combine with build validation
- `anti-patterns.md` (items 1, 2, 8, 9)
