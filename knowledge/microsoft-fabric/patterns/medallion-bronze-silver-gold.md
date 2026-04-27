# Medallion architecture: bronze / silver / gold

> **Last validated**: 2026-04-26
> **Confidence**: 0.91

## What it is

Three-layer data architecture popularized by Databricks, fully applicable to Fabric Lakehouse:

```
[Source]
   ↓
Bronze (raw, append-only, schema-flexible)
   ↓
Silver (cleaned, typed, deduplicated, joined)
   ↓
Gold (aggregated, business-ready, served to BI / ML)
```

Each layer = one or more Delta tables. Layers don't have to be separate Lakehouses — a single Lakehouse can hold all three in different schemas (`bronze.orders`, `silver.orders`, `gold.daily_sales`).

## Bronze — raw landing

Goal: capture source data as-is, with minimal transformation. Fast, replayable.

Properties:
- Schema follows source (whatever it sends)
- Append-only — never UPDATE bronze rows
- Includes ingestion metadata (`_ingested_at`, `_source_file`, `_batch_id`)
- `mergeSchema=true` allowed (source schema may evolve)
- Partition by ingestion date for retention / pruning

Example bronze write:

```python
import pyarrow as pa
from datetime import datetime, timezone
from deltalake import write_deltalake

raw_records = read_source_csv(...)
df = pa.Table.from_pylist(raw_records)

# Add ingestion metadata
df = df.append_column("_ingested_at", pa.array([datetime.now(timezone.utc)] * len(df)))
df = df.append_column("_source_file", pa.array([source_file_name] * len(df)))
df = df.append_column("_batch_id", pa.array([batch_id] * len(df)))

write_deltalake(
    "abfss://...Lakehouse/Tables/bronze_orders",
    df,
    mode="append",
    partition_by=["_ingested_at_date"],   # date column derived above
    schema_mode="merge",                   # source schema may evolve
    storage_options=storage_options,
    configuration={"delta.parquet.vorder.default": "true"},
)
```

Bronze is your audit trail. Don't touch it after write.

## Silver — cleaned and typed

Goal: business-ready entities. Deduplicated, typed, joined to references.

Properties:
- Strict schema (no `mergeSchema`)
- Idempotent updates via MERGE
- Deduplication on natural keys
- Joined with reference data (e.g., add product name from a product dim)
- Partition by query-relevant column (e.g., `order_date`)

Example silver build (PySpark):

```python
from pyspark.sql import functions as F

bronze = spark.read.format("delta").load("abfss://.../Tables/bronze_orders")
products = spark.read.format("delta").load("abfss://.../Tables/silver_products")

silver = (
    bronze
    # Deduplicate (latest per order_id)
    .withColumn("rn", F.row_number().over(
        Window.partitionBy("order_id").orderBy(F.col("_ingested_at").desc())
    ))
    .filter("rn = 1")
    .drop("rn")
    # Typing
    .withColumn("amount", F.col("amount").cast("decimal(18,2)"))
    .withColumn("order_date", F.to_date("order_date"))
    # Enrich
    .join(products.select("product_id", "product_name", "category"), on="product_id", how="left")
    # Trim noise columns
    .select("order_id", "customer_id", "product_id", "product_name", "category",
            "amount", "order_date", "_ingested_at")
)

# MERGE into silver
silver_dt = DeltaTable.forPath(spark, "abfss://.../Tables/silver_orders")
(
    silver_dt.alias("t")
    .merge(silver.alias("s"), "t.order_id = s.order_id")
    .whenMatchedUpdateAll()
    .whenNotMatchedInsertAll()
    .execute()
)
```

Or with `deltalake` Python (no Spark) for smaller volumes:

```python
from deltalake import DeltaTable
silver_dt = DeltaTable("abfss://.../Tables/silver_orders", storage_options=storage_options)
silver_dt.merge(
    source=cleaned_table,
    predicate="t.order_id = s.order_id",
    source_alias="s",
    target_alias="t",
).when_matched_update_all().when_not_matched_insert_all().execute()
```

## Gold — aggregated business layer

Goal: ready-to-serve to dashboards / ML / consumers. Pre-aggregated where appropriate.

Properties:
- Tightly modeled (star / dimensional)
- Aggregations done up-front (so BI doesn't need expensive `summarize`)
- Often DirectLake-friendly (semantic model points here)
- Refreshed less frequently than silver (daily / hourly vs streaming)
- Per-customer / per-team views via ACLs or separate tables

Example gold build:

```sql
-- Spark SQL
CREATE OR REPLACE TABLE gold.daily_sales
USING DELTA
TBLPROPERTIES ('delta.parquet.vorder.default' = 'true')
AS SELECT
    order_date,
    region,
    category,
    SUM(amount) AS total_sales,
    COUNT(*) AS order_count,
    COUNT(DISTINCT customer_id) AS distinct_customers
FROM silver.orders
GROUP BY order_date, region, category;
```

For incremental gold builds, use MERGE on the aggregation key.

## Typical pipeline orchestration

```
Pipeline (Fabric Pipeline / Airflow / Pipelines API):
1. [Trigger] Schedule (every hour) OR Event (file dropped)
2. [Bronze] Copy Activity → write CSV to Files/raw/...
3. [Bronze] Notebook → parse CSV, append to bronze_orders
4. [Silver] Notebook → dedupe + join + write silver_orders
5. [Gold]   Notebook → aggregate + write gold_daily_sales
6. [Refresh] REST API call → refresh semantic model on gold
```

Each step idempotent. Failure mid-flow → re-run from the failed step.

## Layer separation patterns

### Same-Lakehouse, different schemas
```
SalesLakehouse/
└── Tables/
    ├── bronze.orders/
    ├── silver.orders/
    └── gold.daily_sales/
```

### Different Lakehouses per layer
```
Sales-Bronze.Lakehouse/Tables/orders/
Sales-Silver.Lakehouse/Tables/orders/
Sales-Gold.Lakehouse/Tables/daily_sales/
```

Use this when:
- Different teams own different layers
- Different retention / lifecycle policies needed
- Per-layer ACLs (gold restricted to BI team)

## Quality / observability

Each layer should emit:
- Row count after write
- Schema hash (detect drift)
- Quality metrics (% nulls in critical columns, dedup ratio)
- Pipeline run ID + timestamp

Store in a `pipeline_telemetry` table for dashboarding.

## Anti-patterns

- Bronze that updates / deletes rows (kills audit trail)
- Silver with `mergeSchema=true` (drift hides bugs)
- Gold built directly from bronze without silver (skips type / quality fixes)
- Gold tables with high-cardinality groupings (defeats pre-aggregation purpose)
- Pipeline that doesn't track per-step state (re-running from start re-processes everything)
- No partition on bronze (retention impossible without rewriting)
- Same partition strategy across layers without thought (silver / gold have different access patterns)

## See also

- `concepts/delta-table-fundamentals.md`
- `concepts/lakehouse-vs-warehouse.md`
- `patterns/delta-write-with-deltalake-python.md`
- `patterns/semantic-model-refresh-via-api.md`
- `anti-patterns.md` (items 4, 5, 7, 13, 16)
