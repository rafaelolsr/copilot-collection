# Fabric workspaces and capacities

> **Last validated**: 2026-04-26
> **Confidence**: 0.90
> **Source**: https://learn.microsoft.com/en-us/fabric/enterprise/licenses

## The hierarchy

```
Tenant (Microsoft Entra)
└── Domain (optional, for governance — e.g., "Sales", "Finance")
    └── Workspace (collaboration unit, holds Fabric items)
        ├── Lakehouse(s)
        ├── Warehouse(s)
        ├── Semantic Model(s)
        ├── Notebook(s)
        ├── Pipeline(s)
        └── Reports
```

**Workspace** is where work happens. **Capacity** is what powers it.

## Capacity SKUs (F-tier)

Fabric capacities are pay-as-you-go SKUs — F2, F4, F8, F16, F32, F64, F128, F256, F512, F1024, F2048. Each = N "Capacity Units" (CU).

| SKU | Best for | Concurrent users |
|---|---|---|
| F2 | Dev, very small workloads | 1-2 |
| F4 | Small team, light usage | 5-10 |
| F8 | Departmental, moderate | 20-50 |
| F64 | Equivalent to old P1 (Power BI Premium) | 100s |
| F128+ | Enterprise scale | 1000+ |

Workloads consume CUs based on operation type. A single complex DAX query on F2 might exceed your capacity for several seconds; on F64 it's a blip.

## Smoothing and bursting

Fabric capacity throttling uses smoothing — you can burst over your CU rating for short periods, with a "carry forward" of the excess. If you sustain over the rating, queries throttle / fail.

Implication for code: don't write tight loops calling expensive operations. A loop hitting the SQL endpoint 1000× will throttle on F2; on F64 it'll work but burn CUs that delay other workloads.

## Workspace roles

| Role | Capabilities |
|---|---|
| Admin | Full control + delete workspace |
| Member | Add items, modify, share |
| Contributor | Edit items, no sharing |
| Viewer | Read-only |

For per-item ACLs (a specific Lakehouse), permissions cascade from workspace role then narrow further per item.

## What lives in a workspace

| Item type | What it is |
|---|---|
| Lakehouse | Delta tables + files in OneLake |
| Warehouse | T-SQL serverless + Delta tables |
| Notebook | Spark notebook (Python / Scala / R / SQL) |
| Pipeline | Orchestration (Copy Activity, etc.) |
| Dataflow Gen2 | Power Query / M transformations |
| Semantic Model | Tabular model |
| Report | Power BI report |
| KQL Database | Real-time intelligence (Kusto) |
| Eventstream | Streaming ingestion |

A workspace can contain any mix. Most teams: one workspace per environment (dev / test / prod) per logical product.

## Domain governance

Domains (in Fabric) group workspaces under a steward / governance policy. Useful for:
- Tagging data products by department
- Enforcing standards (naming, sensitivity labels)
- Discovery via the OneLake catalog

For a small project, domains are optional. For an enterprise rollout, mandatory.

## OneLake — the shared storage layer

Every workspace has a OneLake instance accessible at:
```
abfss://<workspace>@onelake.dfs.fabric.microsoft.com/
```

Inside, items appear as folders:
```
abfss://Sales-Prod@onelake.dfs.fabric.microsoft.com/
├── SalesLakehouse.Lakehouse/
│   ├── Tables/                              # Delta tables
│   │   └── orders/
│   │       └── _delta_log/
│   └── Files/                                # raw files (CSV, JSON, parquet)
└── SalesWarehouse.Warehouse/
    └── ...
```

Use this path with `deltalake` Python, PySpark, or any tool that speaks ADLS Gen2.

## Capacity-aware code

Watch for these capacity-sensitive operations:
- DirectLake fallback to DirectQuery (when DirectLake can't translate a query) — falls back hard, hits source
- Spark cluster start-up (~30s on smaller SKUs)
- T-SQL endpoint queries against very large tables — scan cost is real
- REST API throttling (per-user + per-capacity limits)

For a small SKU (F2-F8), prefer:
- Cached / pre-aggregated tables
- DirectLake for semantic models (avoids Spark startup)
- Batched API calls
- Smaller partition counts

## Common bugs

- Workspace assigned to no capacity (Fabric items appear but won't run)
- Trial capacity (F-trial) hit limits silently
- User added as Viewer of workspace expecting to query SQL endpoint — doesn't have build permission on the dataset
- Multiple workspaces sharing one capacity, one workspace's heavy job throttles all others
- Pipeline scheduled at the same time across workspaces on one capacity → all throttle

## See also

- `concepts/lakehouse-vs-warehouse.md`
- `concepts/onelake-and-shortcuts.md`
- `concepts/fabric-permissions-model.md`
- `anti-patterns.md` (item 19)
