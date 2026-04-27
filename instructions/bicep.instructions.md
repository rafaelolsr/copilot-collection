---
name: bicep
description: |
  Standards for Bicep infrastructure-as-code. Auto-applied to .bicep files.
  Enforces parameter / variable / output structure, modular design,
  managed identity over secrets, mandatory tags, diagnostic settings,
  no hardcoded resource IDs, what-if validation before deploy.
applyTo: "**/*.bicep,**/*.bicepparam"
---

# Bicep standards

When generating or modifying Bicep, follow these rules. Bicep transpiles
to ARM but is much cleaner — most ARM standards apply, plus Bicep-specific
idioms below.

## File structure

```bicep
// Top: target scope (when not resourceGroup)
targetScope = 'resourceGroup'

// Parameters
@description('Name of the app service')
@minLength(3)
@maxLength(60)
param appName string

@description('Azure region')
param location string = resourceGroup().location

@description('App Service SKU')
@allowed(['B1', 'B2', 'S1', 'P1V2'])
param skuName string = 'B1'

@description('Tags applied to all resources')
param tags object = {
  environment: 'dev'
  application: appName
}

// Variables
var appServicePlanName = 'asp-${appName}'

// Resources
resource appServicePlan 'Microsoft.Web/serverfarms@2024-04-01' = {
  name: appServicePlanName
  location: location
  tags: tags
  sku: { name: skuName }
  properties: {}
}

// Outputs
output appServiceUrl string = 'https://${appService.properties.defaultHostName}'
```

## Parameter rules

### Decorators

Use decorators for constraints — clearer than ARM's nested syntax:

```bicep
@description('SQL admin username')
@minLength(3)
@maxLength(20)
param sqlAdminUser string

@description('SKU')
@allowed(['Free', 'Basic', 'Standard'])
param sku string = 'Basic'

@description('SQL admin password — passed via parameter file or KV reference')
@secure()
param sqlAdminPassword string
```

`@secure()` is mandatory for any password / secret. Without it, the value
is logged in deployment history.

### Defaults

- Use `defaultValue` for any parameter that has a sensible default
- For required-no-default parameters: don't set defaultValue

### Parameter file syntax (.bicepparam)

```bicep
// dev.bicepparam
using 'main.bicep'

param appName = 'myapp-dev'
param location = 'eastus'
param skuName = 'B1'
param sqlAdminPassword = readEnvironmentVariable('SQL_ADMIN_PASSWORD')
```

`.bicepparam` is preferred over the legacy `parameters.json` for new code.

## Resource declarations

### apiVersion — pinned, recent

```bicep
resource appService 'Microsoft.Web/sites@2024-04-01' = {
  // ...
}
```

Use a known-tested API version. Bump intentionally. Don't use a 5-year-old
version "because it works".

### Tags — required

Every taggable resource gets `tags`:

```bicep
resource appService 'Microsoft.Web/sites@2024-04-01' = {
  name: appName
  location: location
  tags: tags                   // pass through from param
  identity: { type: 'SystemAssigned' }
  properties: { ... }
}
```

Standard tags: `environment`, `application`, `owner`, `costCenter`.

### Managed identity over secrets

```bicep
resource appService 'Microsoft.Web/sites@2024-04-01' = {
  name: appName
  location: location
  identity: { type: 'SystemAssigned' }
  // ...
}

// Grant the identity access to a storage account
resource storageRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: storageAccount
  name: guid(storageAccount.id, appService.id, 'Storage Blob Data Contributor')
  properties: {
    roleDefinitionId: '/providers/Microsoft.Authorization/roleDefinitions/ba92f5b4-2d11-453d-a403-e96b0029c9fe'
    principalId: appService.identity.principalId
    principalType: 'ServicePrincipal'
  }
}
```

`guid(...)` produces a deterministic role-assignment name — idempotent.

### Diagnostic settings — required for prod

```bicep
resource diagnosticSettings 'Microsoft.Insights/diagnosticSettings@2021-05-01-preview' = {
  scope: appService
  name: 'diag-settings'
  properties: {
    workspaceId: logAnalyticsWorkspaceId
    logs: [
      {
        categoryGroup: 'allLogs'
        enabled: true
      }
    ]
    metrics: [
      {
        category: 'AllMetrics'
        enabled: true
      }
    ]
  }
}
```

## Modules

For anything > 100 lines, modularize:

```
infra/
├── main.bicep                       # entry point; parameters + module orchestration
├── modules/
│   ├── app-service.bicep
│   ├── storage-account.bicep
│   ├── private-endpoint.bicep
│   └── role-assignments.bicep
└── parameters/
    ├── dev.bicepparam
    ├── staging.bicepparam
    └── prod.bicepparam
```

Module call:

```bicep
module appServiceModule './modules/app-service.bicep' = {
  name: 'appServiceDeployment'
  params: {
    appName: appName
    location: location
    skuName: skuName
    tags: tags
  }
}
```

Module outputs available as `appServiceModule.outputs.appServiceUrl`.

## Conditional and loop deployment

```bicep
// Conditional
resource publicIp 'Microsoft.Network/publicIPAddresses@2023-09-01' = if (!useStaticIp) {
  // ...
}

// Loop
resource queue 'Microsoft.Storage/storageAccounts/queueServices/queues@2023-04-01' = [for queueName in queueNames: {
  name: '${storageAccount.name}/default/${queueName}'
}]
```

For complex iteration: prefer `for-in` over `range()`.

## Use Azure Verified Modules (AVM)

For common patterns, use Microsoft's [Azure Verified Modules](https://aka.ms/avm):

```bicep
module storageAccount 'br/public:avm/res/storage/storage-account:0.18.0' = {
  name: 'storageDeployment'
  params: {
    name: storageAccountName
    location: location
    skuName: 'Standard_LRS'
    tags: tags
    managedIdentities: { systemAssigned: true }
  }
}
```

AVMs are tested, follow best practices, and reduce boilerplate. Use them
unless you have a specific reason not to.

## Anti-patterns to flag

| Pattern | Severity |
|---|---|
| Plaintext password as `param ... string` (missing `@secure()`) | CRITICAL |
| Hardcoded subscription / resource IDs | WARN |
| Resource without tags | INFO |
| Resource without diagnostic settings (prod) | WARN |
| API version > 2 years old | INFO — review |
| API version that's preview when GA exists | WARN |
| Connection string parameter where managed identity would work | WARN |
| Single 500-line .bicep file | WARN — modularize |
| Modules referenced by relative path with `..` going up | INFO — flat structure preferred |
| Non-idempotent role assignment names | CRITICAL — re-deploy fails |
| `dependsOn:` (Bicep auto-detects in most cases) | INFO — usually unnecessary |
| Missing `@description` on parameters | WARN |
| `targetScope` not declared on cross-scope deployments | CRITICAL |

## Linting

Bicep has built-in linting (config in `bicepconfig.json`):

```json
{
  "analyzers": {
    "core": {
      "rules": {
        "no-hardcoded-env-urls": { "level": "error" },
        "no-unused-params": { "level": "error" },
        "no-unused-vars": { "level": "error" },
        "use-recent-api-versions": { "level": "warning" },
        "secure-parameter-default": { "level": "error" }
      }
    }
  }
}
```

## Validation

```bash
# Build to ARM JSON (catches syntax errors)
bicep build main.bicep

# Validate against Azure (with parameters)
az deployment group validate \
  --resource-group <rg> \
  --template-file main.bicep \
  --parameters dev.bicepparam

# Preview changes
az deployment group what-if \
  --resource-group <rg> \
  --template-file main.bicep \
  --parameters dev.bicepparam
```

CI check (GitHub Actions / Azure Pipelines): build + validate + what-if
on every PR touching `infra/**.bicep`.

## See also

- `instructions/arm-template.instructions.md` — for legacy ARM JSON
- `agents/azure-devops-specialist/` — for pipeline patterns
- [Bicep documentation](https://learn.microsoft.com/en-us/azure/azure-resource-manager/bicep/)
- [Azure Verified Modules](https://aka.ms/avm)
