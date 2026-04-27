# OneLake shortcut to ADLS Gen2

> **Last validated**: 2026-04-26
> **Confidence**: 0.87

## When to use this pattern

Existing data lives in Azure Data Lake Storage Gen2 (Delta tables, parquet files, CSVs). You want to query it from Fabric without copying — either for an existing data lake migration or to consume external data.

## Prerequisites

- ADLS Gen2 storage account with the data
- Fabric workspace with Contributor access for the user creating the shortcut
- The consumer identity (workspace member, service principal) must have Storage Blob Data Reader (or higher) on the ADLS account / container

## Option 1 — Fabric portal (interactive)

1. Open the target Lakehouse
2. Navigate to **Tables** (for Delta-formatted shortcuts) or **Files** (for non-Delta)
3. Right-click → **New shortcut**
4. Select **Azure Data Lake Storage Gen2**
5. Connection details:
   - URL: `https://<account>.dfs.core.windows.net`
   - Authentication: **Organizational account** (recommended) or **Service principal**
   - Subpath: `/<container>/<path>/`
6. Configure:
   - Shortcut name (becomes table / folder name in Lakehouse)
   - Path to expose (sub-folder inside container)

For Delta tables: the shortcut path must point at the table folder (the one containing `_delta_log/`).

## Option 2 — Fabric REST API

```python
import asyncio
from FabricClient import FabricClient                          # see fabric-rest-client-managed-identity.md

async def create_adls_shortcut(
    client: FabricClient,
    *,
    workspace_id: str,
    lakehouse_id: str,
    shortcut_name: str,
    path: str,                                                  # "Tables" or "Files"
    storage_account: str,                                       # https://<account>.dfs.core.windows.net
    container: str,
    subpath: str,
    connection_id: str,
) -> dict:
    """Create a shortcut to ADLS Gen2."""
    return await client.post(
        f"/workspaces/{workspace_id}/items/{lakehouse_id}/shortcuts",
        json={
            "name": shortcut_name,
            "path": path,
            "target": {
                "adlsGen2": {
                    "location": f"{storage_account}",
                    "subpath": f"/{container}{subpath}",
                    "connectionId": connection_id,
                }
            },
        },
    )


async def main():
    async with FabricClient(
        scope="https://api.fabric.microsoft.com/.default",
        base_url="https://api.fabric.microsoft.com/v1",
    ) as client:
        await create_adls_shortcut(
            client,
            workspace_id="...",
            lakehouse_id="...",
            shortcut_name="external_orders",
            path="Tables",
            storage_account="https://contosostorage.dfs.core.windows.net",
            container="raw",
            subpath="/orders/",
            connection_id="<your-fabric-connection-id>",
        )

asyncio.run(main())
```

`connection_id` references a Fabric-managed connection. Create one once via:
- Fabric portal → Settings → Manage connections → New connection → ADLS Gen2 → managed identity
- Note the GUID; reuse for all shortcuts to the same account

## Option 3 — From a Spark notebook (one-off)

```python
mssparkutils.fs.createOrUpdateOneLakeShortcut(
    name="external_orders",
    target="https://contosostorage.dfs.core.windows.net/raw/orders",
    connection_name="adls-prod-conn",                            # connection name (not GUID)
    path="Tables",
)
```

## Authentication options

| Option | When to use |
|---|---|
| Organizational account (user) | Interactive use, dev workspaces |
| Service principal | Automation, CI / pipelines |
| Managed identity | Fabric workspace identity has Storage Blob Data Reader |
| SAS token | Temporary access, third-party shares |
| Storage account key | NEVER (not even for testing — leaks happen) |

For production: managed identity. Set up the workspace's identity once with RBAC on the storage account.

## Verifying the shortcut

After creation, query as if it were a native table:

```sql
-- via Fabric SQL endpoint
SELECT * FROM external_orders LIMIT 10;
```

```python
# via deltalake Python (if shortcut is to a Delta table)
from deltalake import DeltaTable
dt = DeltaTable(
    "abfss://Sales-Prod@onelake.dfs.fabric.microsoft.com/SalesLakehouse.Lakehouse/Tables/external_orders",
    storage_options=storage_options,
)
df = dt.to_pandas()
```

If the query returns 0 rows AND no error: usually a permissions issue — the consumer identity doesn't have read access to the underlying ADLS path.

## Performance considerations

- **Same region**: low latency, free egress
- **Cross-region**: latency cost per query; cheap egress within Azure
- **Cross-cloud (Azure → AWS S3)**: high latency, egress charges
- **High-frequency reads** of slow source: consider copying to a same-region Lakehouse and refreshing periodically

For BI dashboards: prefer DirectLake against a same-region copy, not a cross-region shortcut.

## ACL inheritance

The shortcut respects source ACLs. If user A has access to `/raw/orders/` in ADLS but not `/raw/customers/`, A's queries through the shortcut return only the rows visible to A.

For consistent behavior:
- Standardize on managed identity at the workspace level
- Apply RBAC at the storage account / container level
- Test with multiple identities to confirm the security model

## Updating a shortcut

Shortcuts are immutable beyond name; update by deleting + recreating:

```python
await client.delete(
    f"/workspaces/{workspace_id}/items/{lakehouse_id}/shortcuts/{shortcut_name}"
)
await create_adls_shortcut(client, ...)                         # with new params
```

## Common bugs

- Storage account key in the connection (security audit failure)
- Subpath has trailing slash issue (some configs need `/raw/orders/`, others `/raw/orders`)
- Shortcut to a non-Delta path placed in `Tables/` (queries fail with format error)
- Cross-region shortcut to high-traffic source (latency complaints)
- Missing storage RBAC on the consumer identity (silent empty results)
- Shortcut to a path the source-side ACL changes — queries break weeks later
- Connection ID hardcoded in code (should be config / env var)

## Done when

- Connection uses managed identity or service principal (not keys)
- Consumer identity has Storage Blob Data Reader on the ADLS path
- Shortcut tested with a representative query
- Connection ID in config, not hardcoded
- Same-region (or documented cross-region tradeoff)

## See also

- `concepts/onelake-and-shortcuts.md` — fundamentals
- `concepts/fabric-permissions-model.md` — ACL inheritance
- `patterns/fabric-rest-client-managed-identity.md` — the underlying client
- `anti-patterns.md` (items 1, 3, 10, 17)
