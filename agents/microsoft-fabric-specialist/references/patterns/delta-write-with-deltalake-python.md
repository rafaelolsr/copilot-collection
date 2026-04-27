# Delta write with `deltalake` Python (Fabric)

> **Last validated**: 2026-04-26
> **Confidence**: 0.90

## When to use this pattern

Lightweight programmatic Delta writes from a Python service / script. No Spark cluster required. Best for: governance metadata writes, small/medium ETL, services that emit data continuously.

For large transformations (>1GB / batch), prefer PySpark in a notebook.

## Install

```bash
uv pip install "deltalake>=0.18.0" "pyarrow>=14.0.0"
```

The `deltalake` Python package wraps the Rust `delta-rs` library. Fast, no JVM.

## Auth — managed identity / Entra

```python
from azure.identity import DefaultAzureCredential

cred = DefaultAzureCredential()
token = cred.get_token("https://storage.azure.com/.default").token

storage_options = {
    "bearer_token": token,
    "use_fabric_endpoint": "true",
}
```

## Write — append

```python
import pyarrow as pa
from deltalake import write_deltalake

table_path = (
    "abfss://Sales-Prod@onelake.dfs.fabric.microsoft.com/"
    "SalesLakehouse.Lakehouse/Tables/orders"
)

records = [
    {"order_id": "O-001", "customer_id": "C-1", "amount": 99.99, "order_date": "2026-04-26"},
    {"order_id": "O-002", "customer_id": "C-2", "amount": 49.50, "order_date": "2026-04-26"},
]
table = pa.Table.from_pylist(records)

write_deltalake(
    table_path,
    table,
    mode="append",
    storage_options=storage_options,
    configuration={
        "delta.parquet.vorder.default": "true",                # V-Order!
    },
)
```

Mode options:
- `append` — add rows to existing or create if missing
- `overwrite` — replace all data (preserves schema by default)
- `error` — fail if table exists
- `ignore` — no-op if table exists

## Write — explicit schema

For non-bronze layers, ALWAYS provide an explicit schema. Auto-inference can drift.

```python
schema = pa.schema([
    pa.field("order_id", pa.string(), nullable=False),
    pa.field("customer_id", pa.string(), nullable=False),
    pa.field("amount", pa.decimal128(18, 2), nullable=False),
    pa.field("order_date", pa.date32(), nullable=False),
])

table = pa.Table.from_pylist(records, schema=schema)
```

## Idempotent upsert — MERGE

```python
from deltalake import DeltaTable
import pyarrow as pa

dt = DeltaTable(table_path, storage_options=storage_options)

new_data = pa.Table.from_pylist([
    {"order_id": "O-001", "customer_id": "C-1", "amount": 109.99, "order_date": "2026-04-26"},  # updated
    {"order_id": "O-003", "customer_id": "C-3", "amount": 29.99, "order_date": "2026-04-26"},   # new
])

(
    dt.merge(
        source=new_data,
        predicate="t.order_id = s.order_id",
        source_alias="s",
        target_alias="t",
    )
    .when_matched_update_all()
    .when_not_matched_insert_all()
    .execute()
)
```

The MERGE is idempotent: re-running on the same source produces the same result. Use this for any source that may be replayed.

## Partitioning

```python
write_deltalake(
    table_path,
    table,
    mode="append",
    partition_by=["order_date"],
    storage_options=storage_options,
    configuration={"delta.parquet.vorder.default": "true"},
)
```

Choose partition columns with bounded cardinality (≤ ~10,000 distinct values total). `order_date` over 5 years = ~1825 partitions, fine. `customer_id` = millions, NOT fine.

## Compaction (OPTIMIZE)

After many small writes:

```python
dt = DeltaTable(table_path, storage_options=storage_options)
dt.optimize.compact()
```

Z-order:

```python
dt.optimize.z_order(["customer_id"])
```

## VACUUM

```python
dt.vacuum(retention_hours=168)            # 7 days default
```

For aggressive cleanup (rarely needed):
```python
dt.vacuum(retention_hours=0, enforce_retention_duration=False)
```

## Time travel reads

```python
dt = DeltaTable(table_path, storage_options=storage_options, version=42)
df = dt.to_pandas()

# OR
dt = DeltaTable(table_path, storage_options=storage_options)
dt.load_with_datetime("2026-04-25T00:00:00Z")
df = dt.to_pandas()
```

## Reading with filters

```python
dt = DeltaTable(table_path, storage_options=storage_options)

# Pyarrow filter expression
df = dt.to_pandas(
    filters=[
        ("order_date", ">=", "2026-04-01"),
        ("order_date", "<", "2026-05-01"),
        ("customer_id", "in", ["C-1", "C-2", "C-3"]),
    ]
)
```

`deltalake` pushes filters down to parquet — efficient.

## Schema evolution (bronze layer only)

```python
write_deltalake(
    table_path,
    table_with_new_column,
    mode="append",
    schema_mode="merge",
    storage_options=storage_options,
)
```

NEVER use `schema_mode="merge"` on silver / gold. Schema drift in curated layers hides bugs.

## Token refresh for long-running scripts

Tokens from `DefaultAzureCredential` expire (~1 hour). Refresh before each write:

```python
def fresh_storage_options() -> dict[str, str]:
    token = cred.get_token("https://storage.azure.com/.default").token
    return {"bearer_token": token, "use_fabric_endpoint": "true"}

# Each write
write_deltalake(table_path, batch, mode="append",
                storage_options=fresh_storage_options())
```

For very long scripts, structure as a long-lived helper class with cached token + refresh.

## Done when

- V-Order enabled (`delta.parquet.vorder.default: true`)
- Schema is explicit (not inferred) for silver / gold
- Writes are idempotent (MERGE on a key, not blind APPEND)
- Partition columns have bounded cardinality
- Token refresh logic for long-running flows
- OPTIMIZE / VACUUM scheduled (separate cron / pipeline)

## Anti-patterns

- No V-Order (slow DirectLake reads)
- Schema inferred on silver / gold (drift hides bugs)
- Blind append on streaming source (duplicates accumulate)
- Partition by `customer_id` or other unbounded column
- VACUUM RETAIN 0 in production (breaks time travel)
- Account keys instead of managed identity in `storage_options`
- `to_pandas()` on a 100M-row table (driver OOM)

## See also

- `concepts/delta-table-fundamentals.md` — V-Order, OPTIMIZE, VACUUM details
- `concepts/onelake-and-shortcuts.md` — path conventions
- `patterns/medallion-bronze-silver-gold.md` — pipeline structure
- `anti-patterns.md` (items 1, 2, 4, 5, 6, 13)
