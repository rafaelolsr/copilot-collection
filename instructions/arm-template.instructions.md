---
name: arm-template
description: |
  Standards for Azure Resource Manager (ARM) templates. Auto-applied to
  ARM JSON files. Enforces parameter file separation, managed identity
  over connection strings, no hardcoded resource IDs, idempotent
  deployments, modular templates, what-if validation before deploy,
  diagnostic settings on every resource.
applyTo: "**/azuredeploy*.json,**/*.arm.json,**/arm/templates/**/*.json,**/parameters/**/*.json"
---

# ARM template standards

When generating or modifying ARM templates, follow these rules. ARM is
verbose and easy to get wrong — the standards below prevent the most
common production issues.

## File structure

Every template has the standard 5 sections in this order:

```json
{
  "$schema": "https://schema.management.azure.com/schemas/2019-04-01/deploymentTemplate.json#",
  "contentVersion": "1.0.0.0",
  "parameters": { ... },
  "variables": { ... },
  "resources": [ ... ],
  "outputs": { ... }
}
```

Always include `contentVersion` even if you don't use it. Increment when
making breaking changes.

## Parameters

### Always declare type, defaults, and constraints

```json
"parameters": {
  "appName": {
    "type": "string",
    "metadata": {
      "description": "Name of the App Service"
    },
    "minLength": 3,
    "maxLength": 60
  },
  "skuName": {
    "type": "string",
    "defaultValue": "B1",
    "allowedValues": ["B1", "B2", "S1", "P1V2"],
    "metadata": {
      "description": "SKU for the App Service Plan"
    }
  },
  "location": {
    "type": "string",
    "defaultValue": "[resourceGroup().location]",
    "metadata": {
      "description": "Azure region"
    }
  }
}
```

Mandatory:
- `type` — always present
- `metadata.description` — every parameter explains itself
- `defaultValue` for non-secret parameters
- `allowedValues` when the value is a closed set
- `minLength` / `maxLength` / `minValue` / `maxValue` when applicable

### Secrets — secureString or Key Vault reference

```json
"sqlAdminPassword": {
  "type": "secureString",
  "metadata": {
    "description": "SQL admin password — pass via parameter file or KV reference"
  }
}
```

In the parameter file, reference Key Vault:

```json
"sqlAdminPassword": {
  "reference": {
    "keyVault": {
      "id": "/subscriptions/<sub>/resourceGroups/<rg>/providers/Microsoft.KeyVault/vaults/<vault>"
    },
    "secretName": "sql-admin-password"
  }
}
```

NEVER:
- Plain `string` for secrets (logged in deployment history)
- `defaultValue` for secrets

## Variables

Use variables for values referenced 2+ times or computed:

```json
"variables": {
  "appServicePlanName": "[concat('asp-', parameters('appName'))]",
  "tags": {
    "environment": "[parameters('environment')]",
    "deployedBy": "ARM"
  }
}
```

DON'T use variables for one-off literals — inline them.

## Resources — required properties

### Tags

Every taggable resource has tags:

```json
{
  "type": "Microsoft.Web/sites",
  "apiVersion": "2024-04-01",
  "name": "[parameters('appName')]",
  "location": "[parameters('location')]",
  "tags": "[variables('tags')]",
  "properties": { ... }
}
```

Recommended baseline tags: `environment`, `application`, `owner`, `costCenter`.

### Managed identity over connection strings

```json
{
  "type": "Microsoft.Web/sites",
  "apiVersion": "2024-04-01",
  "name": "[parameters('appName')]",
  "identity": {
    "type": "SystemAssigned"
  },
  "properties": { ... }
}
```

Then use role assignments to grant the identity access to other
resources, instead of passing connection strings.

### Diagnostic settings — required for prod

Every resource that supports diagnostics gets a child diagnostic
settings resource pointed at Log Analytics or Application Insights:

```json
{
  "type": "Microsoft.Insights/diagnosticSettings",
  "apiVersion": "2021-05-01-preview",
  "name": "diag-settings",
  "scope": "[resourceId('Microsoft.Web/sites', parameters('appName'))]",
  "properties": {
    "workspaceId": "[parameters('logAnalyticsWorkspaceId')]",
    "logs": [ ... ],
    "metrics": [ ... ]
  }
}
```

Without diagnostic settings, ops teams have nothing to debug with.

### apiVersion — be specific, not "latest"

```json
"apiVersion": "2024-04-01"
```

NEVER use `"latest"` (not a valid value, but some templates fake it).
Pin to a known-tested API version. Update intentionally.

## Outputs

Outputs let downstream templates / scripts consume your deployment:

```json
"outputs": {
  "appServiceUrl": {
    "type": "string",
    "value": "[concat('https://', reference(resourceId('Microsoft.Web/sites', parameters('appName'))).defaultHostName)]"
  },
  "principalId": {
    "type": "string",
    "value": "[reference(resourceId('Microsoft.Web/sites', parameters('appName')), '2024-04-01', 'full').identity.principalId]"
  }
}
```

Don't output secrets. Outputs land in deployment history (visible to
anyone with read access).

## Idempotency

ARM is mostly idempotent by design — re-running a deployment is safe.
But watch for:

- `[uniqueString(...)]` with non-deterministic input → name changes between runs
- Resources with auto-generated names that don't include `name` parameter → drift on re-deploy
- `dependsOn` on a resource that may not exist on first run

Always test with:
```bash
az deployment group what-if --template-file template.json --parameters @params.json
```

## Modular templates

For deployments > 200 lines, split into linked / nested templates:

```
infra/
├── main.json                    # entry point
├── modules/
│   ├── app-service.json
│   ├── storage-account.json
│   └── role-assignments.json
└── parameters/
    ├── dev.parameters.json
    ├── staging.parameters.json
    └── prod.parameters.json
```

Reference modules:
```json
{
  "type": "Microsoft.Resources/deployments",
  "apiVersion": "2024-03-01",
  "name": "appServiceModule",
  "properties": {
    "mode": "Incremental",
    "templateLink": {
      "uri": "[concat(parameters('templateBaseUri'), 'modules/app-service.json')]",
      "contentVersion": "1.0.0.0"
    },
    "parameters": { ... }
  }
}
```

## Anti-patterns to flag

| Pattern | Severity |
|---|---|
| Plaintext password / API key in template or parameter file | CRITICAL |
| `string` type for secrets (use `secureString`) | CRITICAL |
| `defaultValue` for secret parameters | CRITICAL |
| Hardcoded subscription / resource group IDs | WARN |
| Missing `metadata.description` on parameters | WARN |
| Resource without tags | INFO |
| Resource without diagnostic settings (prod) | WARN |
| `apiVersion: "latest"` (invalid) | CRITICAL |
| Old `apiVersion` (>2 years) | INFO — review |
| `connection string` parameter when managed identity would work | WARN |
| `[uniqueString(deployment().name)]` — different name each deploy | CRITICAL — drift |
| Single 1500-line template (no modularization) | WARN |
| No what-if validation in CI before deploy | WARN |
| Outputs containing secret values | CRITICAL |
| `dependsOn` references to nonexistent resource | CRITICAL — fails |

## Validation

```bash
# Schema + property validation
az deployment group validate \
  --resource-group <rg> \
  --template-file template.json \
  --parameters @parameters.json

# Preview changes
az deployment group what-if \
  --resource-group <rg> \
  --template-file template.json \
  --parameters @parameters.json

# Lint (community tool, optional)
arm-ttk -TemplatePath template.json
```

CI check (GitHub Actions or Azure Pipelines): validate + what-if on
every PR that touches `infra/**`.

## Migration to Bicep

ARM JSON is verbose. For new templates, consider Bicep:
- Same target (ARM)
- Decompiled JSON output
- Less syntax noise
- Modules are first-class

Use ARM JSON when:
- Existing templates already exist (don't migrate without reason)
- Tooling requires JSON
- You're consuming auto-generated templates

See `instructions/bicep.instructions.md` for greenfield infrastructure.

## See also

- `instructions/bicep.instructions.md` — for Bicep (preferred for new work)
- `agents/azure-devops-specialist/` — for pipeline patterns
- [ARM template best practices](https://learn.microsoft.com/en-us/azure/azure-resource-manager/templates/best-practices)
