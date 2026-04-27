# Auth and service connections

> **Last validated**: 2026-04-26
> **Confidence**: 0.91

## Authentication options ranked

| Option | When | Rotation | Risk |
|---|---|---|---|
| **Workload Identity Federation (WIF)** | Default for new pipelines accessing Azure | Never (no secret) | Lowest |
| **Managed Identity** (self-hosted agent on Azure VM) | Self-hosted runners | Never | Low |
| **Service Principal + Federated Credential** | When WIF unavailable | Never | Low |
| **Service Principal + Secret** | Legacy / where federation unavailable | Quarterly+ | Medium |
| **Personal Access Token (PAT)** | Ad-hoc scripts | 90 days | High |
| **System.AccessToken** (built-in) | Self-callbacks (push tags, etc.) | Per build | Low scope |

For new pipelines: **WIF**. For everything else, follow the order down only if the prior option doesn't work.

## Workload Identity Federation (WIF)

WIF lets a pipeline assume an Azure identity without a secret. Azure DevOps issues a short-lived OIDC token, Azure Entra exchanges it for an access token.

Setup:

1. **Create a Microsoft Entra app** (or use existing)
2. **Add federated credential**:
   - Issuer: `https://vstoken.dev.azure.com/<your-org-id>`
   - Subject: `sc://<your-org>/<project>/<service-connection-name>`
3. **Grant Azure RBAC** to the app (e.g., Contributor on a resource group)
4. **Create Azure Resource Manager service connection** in Azure DevOps:
   - Type: Workload identity federation (automatic OR manual)
   - Use the Entra app

Pipeline usage:

```yaml
- task: AzureCLI@2
  displayName: Deploy to Azure
  inputs:
    azureSubscription: 'wif-prod-connection'        # service connection name
    scriptType: bash
    scriptLocation: inlineScript
    inlineScript: |
      az webapp deploy --name myapp --src-path build/
```

No secret stored anywhere. The token is requested and exchanged automatically at task runtime.

## Service Principal (with secret)

When WIF isn't available (older Azure DevOps versions, specific edge cases):

1. Create Entra app
2. Generate client secret
3. Store secret in Azure Key Vault (NEVER in pipeline YAML)
4. Service connection: ARM with Service principal (manual)
   - Reference Key Vault secret OR enter directly (the secret is encrypted in DevOps backend)

Rotation: quarterly minimum. Ideally automated via Key Vault rotation policies.

Same pipeline usage:
```yaml
- task: AzureCLI@2
  inputs:
    azureSubscription: 'sp-prod-connection'
    scriptType: bash
    scriptLocation: inlineScript
    inlineScript: az account show
```

## System.AccessToken

The built-in pipeline identity. Used for actions ON Azure DevOps itself:
- Pushing tags / commits back to the source repo
- Calling Azure DevOps REST API
- Publishing pipeline artifacts

```yaml
- bash: |
    git config --global user.email "ci@example.com"
    git config --global user.name "CI"
    git tag "v$(Build.BuildNumber)"
    git push https://$(System.AccessToken)@dev.azure.com/<org>/<project>/_git/<repo> --tags
  env:
    SYSTEM_ACCESSTOKEN: $(System.AccessToken)         # exposes to script
  displayName: Push version tag
```

To use System.AccessToken:
1. The job must allow access — `checkout: self` with `persistCredentials: true`, OR explicit `env:` mapping
2. The Build Service identity needs Contribute permission on the repo (configurable per project)

Scope: limited to the project. Can't reach external resources.

## PAT (Personal Access Token)

Use ONLY for:
- Ad-hoc scripts you run locally
- Bootstrapping a service connection for the first time
- Tools that don't yet support WIF / SP

NEVER:
- In committed YAML
- In a Variable Group not linked to Key Vault
- Shared between people

If a PAT must be used in a pipeline, store in Key Vault, link via Variable Group, mark as secret.

PATs expire (90 days max default). Rotate before expiry.

## Variable groups + Key Vault

Centralize secrets:

1. Azure Key Vault holds the secret
2. Service principal / managed identity has Get + List permission on the vault
3. Azure DevOps **Variable Group** linked to the vault
4. Pipeline references the Variable Group

```yaml
variables:
  - group: shared-prod-secrets       # KV-linked

stages:
  - stage: Deploy
    jobs:
      - job: Deploy
        steps:
          - script: |
              echo "Deploying with key from KV"
            env:
              MY_API_KEY: $(MyApiKey)              # value from KV
```

Variable Groups can be:
- Plain (values stored in DevOps)
- Linked to Key Vault (values fetched from KV at run time)

For secrets, ALWAYS link to KV.

## Service connections by type

| Type | What it auths to |
|---|---|
| Azure Resource Manager | Azure subscriptions / resources |
| Docker Registry | ACR, Docker Hub, etc. |
| Generic | Custom REST API endpoints |
| GitHub | GitHub repos (not GitHub Actions) |
| Kubernetes | K8s clusters |
| npm / NuGet / Maven | Package feeds |

Service connection auth methods vary by type. ARM is the most common; supports WIF + SP.

## Tenant boundary

Service connection scope:
- Subscription-level: pipeline can access all resources in that subscription with the role granted
- Resource-group-level: scoped to a single RG (preferred — least privilege)
- Management-group-level: rare, for org-wide ops

Always scope to the smallest level the pipeline needs.

## Secrets in scripts

Once a secret is mapped to an env var, treat it carefully:

```yaml
- bash: |
    # SAFE — using the env var
    curl -H "Authorization: Bearer $API_TOKEN" https://api.example.com

    # UNSAFE — would expose in logs
    echo "Token: $API_TOKEN"

    # AZURE DEVOPS BLOCKS THIS — secrets are auto-redacted
    # but don't rely on redaction — write defensively
  env:
    API_TOKEN: $(MyApiToken)
```

Azure DevOps redacts known secret values from logs. But: if you base64-encode a secret, the encoded form isn't recognized → printed in logs. Write defensively.

## Common bugs

- PAT in pipeline YAML or sourcecode (top failure mode)
- Secret in Variable Group as plain value (not KV-linked)
- Service connection scope = subscription Owner (over-privileged)
- WIF subject pattern doesn't match — token exchange fails
- System.AccessToken not exposed via `env:` → scripts can't use it
- Secret printed via `echo` (works but redacted; sometimes redaction misses)
- API key passed via URL (logged by every proxy)

## Done when

- New pipelines use WIF (default ARM service connection in 2026)
- Existing pipelines migrating from PAT/SP-secret to WIF on next touch
- All secrets via KV-linked Variable Groups
- Service connections scoped to resource group (not subscription)
- No PATs in YAML
- System.AccessToken used for in-org operations only

## See also

- `concepts/pipeline-yaml-structure.md`
- `concepts/branch-policies.md` — protected branches need pipelines authenticated correctly
- `patterns/pipeline-with-wif.md`
- `anti-patterns.md` (items 1, 2, 9)
