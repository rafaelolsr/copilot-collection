# XMLA deployment via Tabular Editor CLI

> **Last validated**: 2026-04-26
> **Confidence**: 0.88
> **Source**: https://docs.tabulareditor.com/te2/Command-line-Options.html

## When to use this pattern

CI/CD deployment of a PBIP semantic model to a Power BI workspace via XMLA endpoint. Replaces manual "publish from Desktop" with a scriptable pipeline.

## Prerequisites

1. **Premium / Fabric capacity** — XMLA endpoint requires it (Pro doesn't have it)
2. **XMLA endpoint enabled** — Workspace → Settings → Premium → "XMLA Endpoint: Read Write"
3. **Service principal or managed identity** with Build / Write access to the workspace
4. **Tabular Editor 2 (free) or 3 (paid)** — both have CLI

## CLI command

```bash
TabularEditor.exe \
    "<path to .SemanticModel folder>" \
    -D "<XMLA connection string>" \
    "<dataset name>" \
    -O \                           # overwrite existing
    -W \                           # warnings as errors
    -V \                           # validate before deploy
    -E \                           # rebuild dependency tree
    -G                             # generate documentation
```

For Tabular Editor 2 (free):

```bash
"%LOCALAPPDATA%\TabularEditor\TabularEditor.exe" \
    "myproject.SemanticModel" \
    -D "Provider=MSOLAP;Data Source=powerbi://api.powerbi.com/v1.0/myorg/MyWorkspace" \
    "MyDataset" \
    -O \
    -V
```

For Tabular Editor 3 (CLI subcommand):

```bash
"C:\Program Files\Tabular Editor 3\TabularEditor3.exe" \
    --deploy "myproject.SemanticModel" \
    --connection "powerbi://api.powerbi.com/v1.0/myorg/MyWorkspace" \
    --dataset "MyDataset"
```

## Service principal authentication

Don't use a personal account in CI. Create a service principal:

1. Azure Portal → Microsoft Entra → App registrations → New registration
2. API permissions: `Power BI Service` → `Tenant.Read.All` (or workspace-scoped)
3. Workspace → Access → add the SP as Member or Admin
4. Generate a client secret

Connection string with SP:

```
Provider=MSOLAP;
Data Source=powerbi://api.powerbi.com/v1.0/myorg/MyWorkspace;
User ID=app:<client-id>@<tenant-id>;
Password=<client-secret>;
```

For managed identity (in Azure DevOps / GitHub Actions runner):

```
Provider=MSOLAP;
Data Source=powerbi://api.powerbi.com/v1.0/myorg/MyWorkspace;
Integrated Security=ClaimsToken;
```

(With workload identity federation set up upstream — preferred over secrets.)

## Backup before deploy

Always export the existing model as TMDL before overwriting:

```bash
# Backup (export the deployed model to a folder)
TabularEditor.exe \
    -D "Provider=MSOLAP;Data Source=...;" "MyDataset" \
    -B "backup-$(date +%Y%m%d-%H%M%S).bim"

# Then deploy
TabularEditor.exe "myproject.SemanticModel" -D "..." "MyDataset" -O -V
```

If deploy fails, restore the backup.

## Azure DevOps pipeline

```yaml
trigger:
  branches:
    include: [main]
  paths:
    include: ['SemanticModels/**']

pool:
  vmImage: windows-latest

variables:
  - group: pbi-deploy-secrets   # contains PBI_CLIENT_ID, PBI_CLIENT_SECRET, PBI_TENANT_ID

steps:
  - checkout: self

  - powershell: |
      Invoke-WebRequest `
        -Uri 'https://github.com/TabularEditor/TabularEditor/releases/latest/download/TabularEditor.Portable.zip' `
        -OutFile 'tabular.zip'
      Expand-Archive -Path 'tabular.zip' -DestinationPath 'TabularEditor'
    displayName: Install Tabular Editor

  - powershell: |
      $conn = "Provider=MSOLAP;Data Source=powerbi://api.powerbi.com/v1.0/myorg/$(WORKSPACE_NAME);User ID=app:$(PBI_CLIENT_ID)@$(PBI_TENANT_ID);Password=$(PBI_CLIENT_SECRET);"
      .\TabularEditor\TabularEditor.exe `
        "SemanticModels\sales-model.SemanticModel" `
        -D $conn `
        "Sales Model" `
        -O -V -W
    displayName: Deploy to Power BI
    env:
      PBI_CLIENT_ID: $(PBI_CLIENT_ID)
      PBI_CLIENT_SECRET: $(PBI_CLIENT_SECRET)
      PBI_TENANT_ID: $(PBI_TENANT_ID)
      WORKSPACE_NAME: 'Sales-Production'
```

## What `-O`, `-V`, `-W` mean

- `-O` (Overwrite) — replaces the existing dataset. Without this, deploy fails if the dataset name exists.
- `-V` (Validate) — checks for errors before deploying. Without this, broken models can deploy.
- `-W` (Warnings as Errors) — best-effort lint. Pair with `-V`.
- `-D` (Deploy) — combined with the connection + dataset name, this is what triggers the deploy.

## Refreshing after deploy

Deployment doesn't refresh data. Schedule the refresh separately:

```bash
# Trigger refresh via Power BI REST API
curl -X POST \
  "https://api.powerbi.com/v1.0/myorg/groups/$WORKSPACE_ID/datasets/$DATASET_ID/refreshes" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{}'
```

Or in pipeline YAML:

```yaml
  - powershell: |
      $body = @{ notifyOption = "MailOnFailure" } | ConvertTo-Json
      $headers = @{
        Authorization = "Bearer $env:PBI_TOKEN"
        'Content-Type' = 'application/json'
      }
      Invoke-RestMethod `
        -Uri "https://api.powerbi.com/v1.0/myorg/groups/$env:WORKSPACE_ID/datasets/$env:DATASET_ID/refreshes" `
        -Method POST `
        -Headers $headers `
        -Body $body
    displayName: Trigger refresh
```

## Verification after deploy

```bash
# Check deployment landed
TabularEditor.exe \
    -D "Provider=MSOLAP;Data Source=...;" "MyDataset" \
    -S "Model.Tables.Count"          # script: prints number of tables
```

Or query a known measure via the XMLA endpoint:

```dax
EVALUATE { [Total Sales] }
```

## Anti-patterns

- Deploying without `-V` — broken models silently overwrite working ones
- No backup before deploy → no rollback path
- Hardcoded `WorkspaceName` / `DatasetName` in deploy script (use variables)
- Service principal with Tenant Admin rights (over-privileged; scope to workspaces)
- Storing client secret in plaintext (use Azure Key Vault / pipeline secret store)
- Triggering refresh BEFORE deploy completes (causes refresh against the old model)
- Deploying directly to production — always go dev → test → prod

## See also

- `concepts/pbip-project-structure.md` — what to deploy
- `anti-patterns.md` (items 18, 19)
