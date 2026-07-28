# Data access & Lakehouse ingestion

This reference covers the two questions the engineer report's query registry does
**not** answer on its own: *how does the dashboard physically reach its data
today*, and *how do we land that data in a Fabric Lakehouse*. The registry tells
you the query logic; this tells you the **access path** and the **ingestion
plan**.

Output of this phase is a **Markdown guide printed to the CLI** (not the archflow
HTML report), produced by `scripts/generate_access_ingestion_guide.py`. It is
meant to be read in the terminal and acted on directly — it shows the exact code
to run.

## 1. Current data-access map

For every source-backed table, capture the access path, not just the object:

| Field | Source | Notes |
|---|---|---|
| Connector | M expression | `Sql.Database`, `MySQL.Database`, `Value.NativeQuery`, `Odbc.*` … |
| Server / database | M parameters | usually shared parameters (e.g. `mariadb_server`) |
| Source object / native SQL | M `[Query=...]` or `NativeQuery` | hand-written SQL is pushed to the source |
| Storage mode | partition | Import vs DirectQuery |
| Query folding | M step analysis | does it fold, or pull then transform locally? |
| **On-prem data gateway** | Power BI REST | the model cannot tell you this |
| **Auth mode / credentials** | Power BI REST | Basic / OAuth2 / Key / Windows |
| **Refresh schedule & cadence** | Power BI REST | sets the Lakehouse pipeline trigger frequency |
| **Approx volume / row count** | source `COUNT(*)` | sizes full-vs-incremental |
| **Privacy / sensitivity** | Power BI REST + labels | governance |

The generator derives connector, server/db, source object, mode and native-SQL
flag from the TMDL registry. The bold rows require live APIs — see §2.

## 2. What the modeling MCP cannot give you (use the REST/Scanner API)

Gateway, datasource credentials, refresh schedule, and volumes are **not** in the
`powerbi-modeling-mcp` (it only sees the model). Collect them with the **Power BI
REST API** and the **Fabric Scanner API**:

```bash
# datasources behind the dataset (gateway id + connection details)
GET https://api.powerbi.com/v1.0/myorg/datasets/{datasetId}/datasources

# refresh history (actual cadence + durations + volume signal)
GET https://api.powerbi.com/v1.0/myorg/datasets/{datasetId}/refreshes?$top=20

# configured refresh schedule
GET https://api.powerbi.com/v1.0/myorg/datasets/{datasetId}/refreshSchedule

# gateway + datasource status
GET https://api.powerbi.com/v1.0/myorg/gateways/{gatewayId}/datasources
```

Run `COUNT(*)` (and `MIN/MAX` of the watermark column) against each source object
to size ingestion. Record these in the access map before choosing a method.

## 3. Ingestion decision matrix (source → Lakehouse bronze)

| Method | Best when | Trade-offs |
|---|---|---|
| **OneLake shortcut** | source already in OneLake / ADLS / mirrored DB | zero copy, but source must be reachable as a shortcut target |
| **Database Mirroring** | supported source (SQL DB/Azure SQL/Snowflake/Cosmos…) | near-real-time, low effort; check MariaDB/MySQL support |
| **Data pipeline — Copy activity** | relational source behind a **gateway**, native SQL to push | mature, schedulable; one activity per source query |
| **Dataflow Gen2** | low-code transforms, reuse of existing M | heavier runtime; good for citizen-dev parity |
| **Notebook (Spark JDBC)** | full control, custom partitioning, big volumes | you manage the driver + secrets |

**Rule of thumb for hand-written native SQL behind a gateway** (this model's
case): use a **Data pipeline Copy activity** (source = the harvested SQL) or a
**Spark JDBC notebook**, landing each source query as a **bronze Delta table**.

## 4. Medallion layering — land before you consolidate

Do not ingest straight into the gold OBT. Land raw first:

```
source (MariaDB native SQL)
        │  ingest (Copy / JDBC)
        ▼
bronze  bronze_<object>   ── raw, 1:1 with source query, + _loaded_at
        │  clean / conform types, keys
        ▼
silver  silver_<entity>   ── deduped, typed, conformed dims
        │  consolidate (the OBT build script)
        ▼
gold    obt_<fact>        ── one big table + rollup views
```

The existing `build_obt_*` scripts are the **gold** step. This guide adds the
**bronze landing** step that feeds them.

## 5. Bronze landing — code patterns

**Spark JDBC (notebook)** — one cell per source object, secret from Key Vault:

```python
server   = mssparkutils.credentials.getSecret("kv-name", "mariadb-host")
user     = mssparkutils.credentials.getSecret("kv-name", "mariadb-user")
password = mssparkutils.credentials.getSecret("kv-name", "mariadb-pass")
jdbc_url = f"jdbc:mysql://{server}:3306/<database>"

df = (spark.read.format("jdbc")
        .option("url", jdbc_url)
        .option("driver", "org.mariadb.jdbc.Driver")
        .option("query", "<the harvested native SQL>")
        .option("user", user).option("password", password)
        .load())

(df.withColumn("_loaded_at", current_timestamp())
   .write.mode("overwrite").format("delta")
   .saveAsTable("bronze_<object>"))
```

**Data pipeline Copy activity** — source = the harvested SQL, sink = Lakehouse
table; bind the connection to a gateway + Key Vault credential. Never inline
secrets.

## 6. Incremental ingestion — watermark pattern

Imports with no incremental policy are full reloads. Switch to a watermark:

```python
from delta.tables import DeltaTable

hwm = (spark.read.table("bronze_<object>")
         .agg({"<watermark_col>": "max"}).collect()[0][0]) or "1900-01-01"

delta_sql = f"SELECT * FROM <source> WHERE <watermark_col> > '{hwm}'"
new = spark.read.format("jdbc").option("query", delta_sql)...load()

(DeltaTable.forName(spark, "bronze_<object>").alias("t")
   .merge(new.alias("s"), "t.<key> = s.<key>")
   .whenMatchedUpdateAll().whenNotMatchedInsertAll().execute())
```

If the source exposes CDC / change tracking, prefer it over a timestamp watermark.

## 7. Orchestration & schedule

Drive bronze → silver → gold from a **Fabric Data pipeline** (or notebook
schedule). Set the trigger cadence to match the **harvested Power BI refresh
schedule** from §2 (do not invent a frequency). Order: land all bronze → build
silver → run `build_obt_*` → refresh the semantic model.

## 8. Engineer checklist

- [ ] Access map complete (incl. gateway, auth, refresh, volume from §2 APIs)
- [ ] Ingestion method chosen per source (§3) and connection created in Fabric
- [ ] Secrets in Key Vault / workspace identity — none inline
- [ ] Bronze tables landing the raw source queries (§5)
- [ ] Incremental watermark decided per table (§6)
- [ ] Pipeline scheduled to match source refresh cadence (§7)
- [ ] gold OBT built from silver, validated (existing build + validation scripts)
