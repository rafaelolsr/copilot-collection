# OneLake and shortcuts

> **Last validated**: 2026-04-26
> **Confidence**: 0.91

## OneLake

The single, tenant-wide data lake powering all Fabric items. Everything stored in Fabric (Lakehouse Delta tables, Warehouse Delta tables, semantic-model files, even shortcuts) lives here.

URL pattern (ABFSS, Azure Data Lake Storage Gen2):
```
abfss://<workspace-name>@onelake.dfs.fabric.microsoft.com/<item-name>.<item-type>/<path>
```

Examples:
```
# Lakehouse table
abfss://Sales-Prod@onelake.dfs.fabric.microsoft.com/SalesLakehouse.Lakehouse/Tables/orders/

# Lakehouse files
abfss://Sales-Prod@onelake.dfs.fabric.microsoft.com/SalesLakehouse.Lakehouse/Files/raw/

# Warehouse table
abfss://Sales-Prod@onelake.dfs.fabric.microsoft.com/SalesWarehouse.Warehouse/Tables/dbo/orders/
```

Workspace name uses dashes; item name uses underscore-or-dash convention; both are URL-encoded if they contain spaces.

## Shortcuts — what they are

A shortcut is a virtual reference to data living elsewhere. The shortcut behaves like a normal Delta table / folder, but the underlying bytes are NOT stored in OneLake — they're read from the source on demand.

```
SalesLakehouse.Lakehouse/
├── Tables/
│   ├── orders/                              # native Delta table (in OneLake)
│   └── customers/                           # SHORTCUT to ADLS — same query interface
└── Files/
    └── external_csv/                        # SHORTCUT to S3 bucket
```

## Shortcut sources

| Source | What it links to |
|---|---|
| OneLake (cross-workspace) | Another workspace's Lakehouse / Warehouse |
| ADLS Gen2 | Existing data lake on Azure storage |
| Amazon S3 | S3 buckets |
| Google Cloud Storage | GCS buckets |
| Dataverse | Power Platform / Dynamics tables |

For OneLake-to-OneLake (within same tenant), shortcuts are zero-copy and zero-egress. For S3 / GCS / non-Microsoft sources, queries pay egress fees on the source side.

## When to use a shortcut

YES:
- Data already exists in another store (don't duplicate)
- You want a Lakehouse view over an external source without ETL
- Multi-workspace scenarios (one team owns the data; others consume via shortcut)
- "Mirror" pattern: read existing ADLS, transform via Spark in another workspace

NO:
- You need to transform data on ingestion (use a copy + bronze layer)
- The source is unreliable / has poor SLA (cache via copy)
- High-frequency queries against a slow / charged source (cache via copy to control cost)

## ACL inheritance

A shortcut inherits ACLs from the source. You don't get to "expose" data the user doesn't have access to.

- **Source ADLS** with managed identity / RBAC → consumer needs identity-based read access
- **Cross-workspace OneLake** → consumer needs Viewer (or higher) on the source workspace
- **S3** → consumer's identity must have IAM access (via mounted AWS IAM Role)

Common bug: shortcut created by an admin; analyst queries it; query returns 0 rows or AuthZ error. The shortcut isn't a permission elevator.

## Creating shortcuts

### Via Fabric portal
1. Lakehouse → Tables / Files → "..." menu → New shortcut
2. Pick source (ADLS / S3 / OneLake / etc.)
3. Configure connection (managed identity preferred over keys)
4. Set the path

### Via the Fabric REST API

```python
import requests

response = requests.post(
    f"https://api.fabric.microsoft.com/v1/workspaces/{workspace_id}/items/{lakehouse_id}/shortcuts",
    headers={"Authorization": f"Bearer {token}"},
    json={
        "name": "external_orders",
        "path": "Tables",
        "target": {
            "adlsGen2": {
                "location": "https://contosostorage.dfs.core.windows.net",
                "subpath": "/raw/orders/",
                "connectionId": "<connection-id>",
            }
        },
    },
)
```

`connectionId` is a Fabric-managed connection (set up in Settings → Manage connections). Stores the credential / managed identity reference.

### Via Spark (one-off shortcut from a notebook)

```python
mssparkutils.fs.createOrUpdateOneLakeShortcut(
    name="external_orders",
    target="https://contosostorage.dfs.core.windows.net/raw/orders",
    connection_name="adls-prod-conn",
    path="Tables",
)
```

## Path conventions

For Tables, shortcuts MUST follow the Delta table layout:
```
Tables/
└── <shortcut-name>/                         # this is the table
    ├── _delta_log/                           # delta protocol
    └── *.parquet
```

If your source isn't Delta-formatted, it can't shortcut as a Table — shortcut into Files instead and read with PySpark / handle parquet directly.

For Files, anything goes — CSV, JSON, parquet folders, mixed.

## Cross-region considerations

Shortcuts are **cross-region**:
- Workspace in West US, shortcut to ADLS in East US — works, but adds latency per query
- Cross-cloud (Azure → AWS) — works, but egress costs and latency
- Best for archival / occasional access; bad for high-throughput dashboards

For high-traffic dashboards, copy hot data into a same-region Lakehouse.

## Refresh semantics

Shortcuts are live — every query reads the source as-of-now. No "refresh" step.

Caveat: Delta tables behind shortcuts have their own versioning (delta_log). Time travel works if the source is Delta. For non-Delta sources (raw CSV / JSON), you get latest only.

## Anti-patterns

- Shortcut to a source you don't have read access on (silent failures at query time)
- Copying when a shortcut would do (storage waste + drift)
- Shortcut into a source with high egress cost + frequent queries (bill surprise)
- Cross-region shortcut for a hot dashboard (latency)
- Storing connection keys in shortcut config (use managed-identity-backed connections)
- Pointing a shortcut at a non-Delta path expecting Table behavior — shortcut into Files instead

## See also

- `concepts/lakehouse-vs-warehouse.md`
- `concepts/delta-table-fundamentals.md`
- `concepts/fabric-permissions-model.md`
- `patterns/onelake-shortcut-to-adls.md`
- `anti-patterns.md` (items 3, 10, 17)
