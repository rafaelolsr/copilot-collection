# Lakehouse vs Warehouse

> **Last validated**: 2026-04-26
> **Confidence**: 0.91

## TL;DR decision

| Need | Choose |
|---|---|
| ML, ETL, data engineering | Lakehouse |
| BI dashboards, reporting | Warehouse |
| Both ML + BI | Lakehouse (use SQL endpoint for BI) |
| T-SQL-only team, no Python/Spark | Warehouse |
| Schema-on-write, strict typing | Warehouse |
| Schema-on-read, flexible | Lakehouse |
| Existing Synapse Dedicated SQL workload | Warehouse |
| Greenfield, mixed workload | Lakehouse |

For most projects: **Lakehouse**. Read-side queries via the SQL endpoint cover BI use; the lakehouse adds Spark / Python / Notebooks for everything else.

## What they share

Both are backed by Delta tables in OneLake. Both queryable via T-SQL. Both support DirectLake. Storage is fundamentally the same.

The differences are in **write methods**, **schema enforcement**, and **transactional guarantees**.

## Lakehouse — the long version

```
Lakehouse
├── Tables/                          # Delta tables, queryable via SQL endpoint
│   ├── customers/
│   └── orders/
└── Files/                           # raw files, accessed via Spark / Python
    ├── raw_csv/
    └── staging_parquet/
```

### Write methods
- **PySpark** in a notebook: full programmatic ETL, MERGE, schema evolution
- **`deltalake` Python**: lightweight Delta writes from any Python service
- **Spark SQL** in a notebook: `CREATE TABLE`, `INSERT INTO`, `MERGE INTO`
- **Pipelines (Copy Activity)**: bulk loads from external sources
- **Dataflow Gen2** (M / Power Query): UI-friendly transforms
- **COPY INTO** (T-SQL): bulk load CSV / Parquet from URLs

### Read methods
- **PySpark / Spark SQL** for transformations
- **SQL endpoint** for read-only T-SQL (auto-generated, read-only)
- **DirectLake** for semantic models
- **DirectQuery** (rare; usually DirectLake instead)
- **deltalake** for Python reads

### Schema
- Schema enforced per-Delta-table (when explicitly defined)
- `mergeSchema=true` allows new columns to flow through (good for bronze ingestion)
- Files/ area is schemaless (raw landing zone)

### Best for
- ML pipelines (read raw → train → write predictions back)
- ETL with complex transformations
- Notebook-driven exploration
- Multi-source ingestion (CSV / JSON / Parquet / Avro into Delta)

## Warehouse — the long version

```
Warehouse
└── Schemas/
    ├── dbo/
    │   ├── customers/                # Delta-backed; T-SQL primary interface
    │   └── orders/
    └── analytics/
        └── ...
```

### Write methods
- **T-SQL** only: `INSERT`, `UPDATE`, `MERGE`, `CTAS`, `COPY INTO`
- No Spark / Python at write
- Procedures, views, functions like a traditional SQL warehouse

### Read methods
- **T-SQL** (full)
- **DirectLake / DirectQuery** for semantic models
- **Spark** (read-only)

### Schema
- Strict — `CREATE TABLE` with explicit columns and types
- `ALTER TABLE` for schema evolution
- No `mergeSchema` equivalent

### Best for
- BI / reporting workloads
- Teams that know SQL and prefer it
- Migrations from Synapse Dedicated SQL Pool / SQL Server / Snowflake
- Auditable schema changes (every change is a DDL statement)

## Side-by-side examples

### Bronze ingestion of CSV → Delta

**Lakehouse / PySpark:**
```python
df = spark.read.csv("Files/raw_csv/orders/2026/04/26/*.csv", header=True, inferSchema=True)
df.write.format("delta").mode("append").saveAsTable("orders_bronze")
```

**Warehouse / T-SQL (COPY INTO):**
```sql
COPY INTO orders_bronze
FROM 'https://account.dfs.core.windows.net/raw/orders/2026/04/26/'
WITH (
    FILE_TYPE = 'CSV',
    FIRSTROW = 2
);
```

### Daily aggregation for a dashboard

**Lakehouse / Spark SQL or T-SQL endpoint:**
```sql
INSERT INTO orders_daily
SELECT order_date, region, SUM(amount) AS total
FROM orders_silver
GROUP BY order_date, region;
```

**Warehouse / T-SQL:**
```sql
MERGE INTO orders_daily t
USING (
    SELECT order_date, region, SUM(amount) AS total
    FROM orders_silver
    WHERE order_date = CAST(GETDATE() AS DATE)
    GROUP BY order_date, region
) s ON t.order_date = s.order_date AND t.region = s.region
WHEN MATCHED THEN UPDATE SET total = s.total
WHEN NOT MATCHED THEN INSERT (order_date, region, total) VALUES (s.order_date, s.region, s.total);
```

## Cross-shopping data

Lakehouse and Warehouse in the same workspace can query each other:
- Warehouse can query Lakehouse tables via 3-part name `<lakehouse>.dbo.<table>`
- Lakehouse SQL endpoint can query Warehouse tables similarly

Cross-references work because both ultimately store Delta in OneLake.

## When NOT to use a Warehouse

- You don't have T-SQL skills on the team
- You need Python / Spark transformations during ingestion
- You need flexible schema evolution
- Your team prefers notebooks over scripts

When NOT to use a Lakehouse:
- You're migrating from a strict-schema legacy SQL warehouse and don't want flexibility
- You have a BI-only workload with simple SQL needs
- Your team is allergic to Spark cluster startup latency

## Common confusions

- "Lakehouse SQL endpoint" is read-only. To write, use Spark or deltalake. Use Warehouse for write-via-SQL.
- DirectLake works against both — the semantic model doesn't care whether it's Lakehouse or Warehouse Delta.
- "Schema enforcement" in Lakehouse is per-table — once you create a Delta table with explicit columns, writes that don't match fail. The flexibility is at table-creation time and the "Files/" area.
- Warehouse "Tables" still live in OneLake as Delta — there's no separate storage layer.

## See also

- `concepts/onelake-and-shortcuts.md`
- `concepts/delta-table-fundamentals.md`
- `concepts/fabric-sql-endpoint.md`
- `patterns/medallion-bronze-silver-gold.md`
