# Delta table fundamentals (Fabric flavor)

> **Last validated**: 2026-04-26
> **Confidence**: 0.91
> **Source**: https://delta.io/, https://learn.microsoft.com/en-us/fabric/data-engineering/delta-optimization-and-v-order

## What Delta tables are

Parquet files + a transaction log (`_delta_log/`) that gives you ACID, time travel, schema evolution, MERGE, and concurrent writes — without a database.

Every Lakehouse and Warehouse table in Fabric is a Delta table. Same format, same tooling.

## Layout

```
Tables/orders/
├── _delta_log/
│   ├── 00000000000000000000.json            # transaction 0 (initial commit)
│   ├── 00000000000000000001.json            # transaction 1 (append)
│   ├── ...
│   └── _last_checkpoint                      # checkpoint pointer
├── part-00000-<uuid>.snappy.parquet
├── part-00001-<uuid>.snappy.parquet
└── ...
```

`_delta_log/*.json` is the source of truth. Parquet files are just data; the log says which are current, which are deleted, and what schema applies.

## V-Order — the Fabric optimization

V-Order is a Microsoft-specific Parquet write-time optimization that improves DirectLake / SQL endpoint scan performance. It reorganizes data WITHIN parquet files for column-store reads.

**Default in Fabric**: writes via Spark / pipelines / `deltalake` Python (with appropriate config) include V-Order.

To verify a table is V-Ordered:
```python
from deltalake import DeltaTable

dt = DeltaTable("abfss://...@onelake.dfs.fabric.microsoft.com/...Lakehouse/Tables/orders")
metadata = dt.metadata()
print(metadata.configuration)
# Look for: 'delta.parquet.vorder.default': 'true'
```

When writing without Spark (pure `deltalake`), V-Order isn't always applied automatically. Check the writer's docs / set the config.

V-Order trade-off: ~10% slower writes for ~3-5× faster DirectLake / SQL endpoint reads. Worth it for tables read frequently.

## OPTIMIZE

Compacts small files into larger ones. After many small writes (streaming, frequent appends), tables accumulate hundreds of small parquet files — slow to scan.

```sql
-- T-SQL on Fabric SQL endpoint
OPTIMIZE orders;

-- Spark SQL
OPTIMIZE 'abfss://...Tables/orders';

-- deltalake Python
from deltalake import DeltaTable
dt = DeltaTable("abfss://...Tables/orders")
dt.optimize.compact()
```

Schedule: weekly for low-write tables; daily for high-write. Skipping it = slow queries forever.

## Z-ORDER

Co-locates rows by one or more columns within parquet files — speeds up filter queries.

```sql
OPTIMIZE orders ZORDER BY (customer_id, order_date);
```

Choose Z-ORDER columns by what users filter on. Single-column Z-ORDER is most effective; multi-column has diminishing returns.

## VACUUM

Permanently deletes files no longer referenced by the Delta log. Without VACUUM, deleted / updated rows pile up forever as historical files.

```sql
VACUUM orders RETAIN 168 HOURS;          -- 7 days = default
```

Default retention: 7 days (lets time travel work for that window). Lower retention = less storage but breaks time travel.

```sql
VACUUM orders RETAIN 0 HOURS;            -- AGGRESSIVE — breaks time travel
SET spark.databricks.delta.retentionDurationCheck.enabled = false;  -- required for <168h
```

Don't go below 168 HOURS in production unless you have specific reasons (storage cost, regulatory).

## Partitioning

Partitions split a table into separate folders by column value:

```python
df.write.format("delta").partitionBy("year", "month").saveAsTable("orders")
```

```
Tables/orders/
├── year=2026/
│   ├── month=01/
│   ├── month=02/
│   └── month=03/
└── year=2025/
    └── ...
```

Query filters on partition columns skip irrelevant partitions = much faster.

**Cardinality matters**:
- Good: `year` (5-10 values), `month` (12), `region` (5-50)
- Bad: `customer_id` (millions), `transaction_id` (each unique)

Rule: keep partitions ≥ 1GB and ≤ 100GB each. Too small → metadata overhead. Too large → no pruning benefit.

## MERGE — the upsert operator

For idempotent / streaming writes, MERGE is the single most important operator:

```sql
MERGE INTO orders AS t
USING staging_orders AS s
ON t.order_id = s.order_id
WHEN MATCHED THEN UPDATE SET *
WHEN NOT MATCHED THEN INSERT *
```

In `deltalake` Python:

```python
from deltalake import DeltaTable
import pyarrow as pa

dt = DeltaTable("abfss://...Tables/orders")
dt.merge(
    source=pa.Table.from_pylist(staging_records),
    predicate="t.order_id = s.order_id",
    source_alias="s",
    target_alias="t",
).when_matched_update_all().when_not_matched_insert_all().execute()
```

Deletes:
```sql
MERGE INTO orders AS t
USING (SELECT order_id FROM tombstones) AS s
ON t.order_id = s.order_id
WHEN MATCHED THEN DELETE
```

## Time travel

Read an older version:

```sql
-- T-SQL on Fabric SQL endpoint (works on Lakehouse SQL endpoint, not always Warehouse)
SELECT * FROM orders FOR TIMESTAMP AS OF '2026-04-25 00:00:00';

-- Spark SQL
SELECT * FROM orders VERSION AS OF 42;
SELECT * FROM orders TIMESTAMP AS OF '2026-04-25';

-- deltalake Python
dt = DeltaTable("abfss://...Tables/orders")
dt.load_version(42)
df = dt.to_pyarrow_table()
```

Useful for: debugging "what did this look like yesterday?", point-in-time joins, recovering from bad updates.

Caveat: time travel only works back to the VACUUM retention window.

## Schema evolution

Add a column without rewriting data:

```python
df_with_new_col.write.format("delta").mode("append").option("mergeSchema", "true").saveAsTable("orders")
```

Drop / rename columns require column-mapping mode:

```sql
ALTER TABLE orders SET TBLPROPERTIES (
    'delta.minReaderVersion' = '2',
    'delta.minWriterVersion' = '5',
    'delta.columnMapping.mode' = 'name'
);

ALTER TABLE orders RENAME COLUMN old_name TO new_name;
```

For bronze (ingest layer): `mergeSchema=true` is OK. For silver / gold: NEVER `mergeSchema=true`. Schema drift in curated layers hides bugs.

## Concurrent writes

Delta supports optimistic concurrency. Two writers attempting to commit at the same instant:
- One wins, the other retries automatically (within the writer)
- If both touch overlapping files, the loser fails — handle with retry or use a queue

For high-concurrency writes (streaming + batch), MERGE on a primary key is safe. Blind APPENDs can race and produce duplicates.

## Common bugs

- No V-Order — DirectLake queries 5× slower than they should be
- No OPTIMIZE on a streaming-fed table — small-file blowup
- Partition by high-cardinality column (millions of partitions) — every operation slow
- VACUUM RETAIN 0 in production — broke time travel for users
- `mergeSchema=true` on silver layer — undetected new column with bad data
- Time travel beyond VACUUM window — error
- MERGE without a unique-key predicate — duplicates accumulate

## See also

- `concepts/lakehouse-vs-warehouse.md`
- `concepts/onelake-and-shortcuts.md`
- `patterns/delta-write-with-deltalake-python.md`
- `patterns/medallion-bronze-silver-gold.md`
- `anti-patterns.md` (items 4, 5, 13, 16, 20)
