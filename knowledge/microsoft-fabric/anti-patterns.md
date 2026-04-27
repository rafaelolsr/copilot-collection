# Microsoft Fabric — Anti-Patterns

> **Last validated**: 2026-04-26
> **Confidence**: 0.91
> Wrong / Correct pairs for every anti-pattern the agent flags on sight.

---

## 1. Hardcoded storage account keys / SAS tokens

Wrong:
```python
storage_options = {
    "account_name": "contosostorage",
    "account_key": "abc123...",
}
```

Correct:
```python
from azure.identity import DefaultAzureCredential
cred = DefaultAzureCredential()
token = cred.get_token("https://storage.azure.com/.default").token
storage_options = {
    "bearer_token": token,
    "use_fabric_endpoint": "true",
}
```

---

## 2. Account-key auth instead of managed identity

Wrong: any code path using account keys, SAS tokens, or static credentials in production.

Correct: managed identity + RBAC. `Storage Blob Data Reader` / `Storage Blob Data Contributor` on the storage account.

---

## 3. Copying when a shortcut would do

Wrong: data already in ADLS Gen2 on the same Azure region; pipeline copies it into Lakehouse Bronze.

Correct: create a OneLake shortcut to the ADLS path. Zero copy, zero duplication, no drift risk.

---

## 4. No V-Order on Delta writes

Wrong:
```python
write_deltalake(path, table, mode="append", storage_options=...)
```

Correct:
```python
write_deltalake(
    path, table, mode="append",
    storage_options=...,
    configuration={"delta.parquet.vorder.default": "true"},
)
```

V-Order = 3-5× faster DirectLake / SQL endpoint reads for ~10% slower writes. Worth it.

---

## 5. No OPTIMIZE / VACUUM scheduled

Wrong: streaming writes piling small files for weeks. Queries slow to a crawl.

Correct: schedule OPTIMIZE (weekly+) and VACUUM (after OPTIMIZE) on streaming-fed tables.
```python
dt.optimize.compact()
dt.vacuum(retention_hours=168)
```

---

## 6. Blind append on streaming source (no idempotency)

Wrong:
```python
df.write.format("delta").mode("append").saveAsTable("orders")
# Re-running this duplicates rows
```

Correct: MERGE on a key.
```python
dt.merge(
    source=df,
    predicate="t.order_id = s.order_id",
    ...,
).when_matched_update_all().when_not_matched_insert_all().execute()
```

---

## 7. mergeSchema=true on silver/gold

Wrong:
```python
write_deltalake(silver_path, df, mode="append", schema_mode="merge", ...)
```

Why: silver / gold should have strict schema. Drift = bugs in production unnoticed.

Correct:
```python
# bronze: OK to merge schema
write_deltalake(bronze_path, df, mode="append", schema_mode="merge", ...)

# silver / gold: never
write_deltalake(silver_path, df, mode="append", ...)            # default = strict
```

---

## 8. DirectQuery for a model that fits Import / DirectLake

Wrong: 10MB model, 50 daily users, configured as DirectQuery — slow + load on source.

Correct: DirectLake (preferred on Fabric) or Import for small models.

---

## 9. DirectQuery without a fast underlying source

Wrong: DirectQuery semantic model pointed at a slow on-prem SQL server. Each visual = a round-trip; users see spinner.

Correct: ingest into Lakehouse → DirectLake.

---

## 10. Shortcut to source you don't have read access on

Wrong: admin creates a shortcut. Analyst queries it. Returns 0 rows. No error visible.

Correct: ensure the consumer identity has `Storage Blob Data Reader` (or equivalent) on the source. Test with the actual consumer identity, not the admin's.

---

## 11. Pipeline activity without retry config

Wrong: Copy Activity from external API. Network blip → activity fails. Pipeline fails. Re-run from scratch.

Correct: configure retry policy on activities (3 retries, exponential backoff). Idempotent activity design.

---

## 12. Power BI REST API call without 429 retry / wait

Wrong:
```python
response = await client.post(...)
# 429? Crash.
```

Correct: retry with exponential backoff + honor `Retry-After` header. See `patterns/fabric-rest-client-managed-identity.md`.

---

## 13. Partition columns with unbounded cardinality

Wrong:
```python
df.write.format("delta").partitionBy("customer_id").saveAsTable("orders")
# 5M customers = 5M partitions
```

Why: every operation slow. Metadata blows up. VACUUM takes hours.

Correct: partition by bounded column.
```python
df.write.format("delta").partitionBy("order_date").saveAsTable("orders")
# ~1825 partitions over 5 years — fine
```

---

## 14. T-SQL `SELECT *` on large Lakehouse SQL endpoint table

Wrong:
```sql
SELECT * FROM dbo.orders WHERE order_date > '2026-01-01';
```

Why: scans every column even if only 3 are needed. Bandwidth + CU cost.

Correct:
```sql
SELECT order_id, customer_id, amount FROM dbo.orders WHERE order_date > '2026-01-01';
```

---

## 15. Workspace shared with users having unnecessary admin roles

Wrong: every developer is workspace Admin.

Correct: Contributor for active editors, Member for team leads, Admin only for the workspace owner / DevOps. Audit periodically.

---

## 16. No Lakehouse schema enforcement

Wrong: every column STRING; CSV ingested with no typing. Downstream queries cast in every measure.

Correct: define explicit schema at the silver layer. Cast types once, store typed. Saves cost on every query.

---

## 17. Cross-region shortcuts without latency awareness

Wrong: workspace in West US, shortcut to ADLS in East US. Dashboards lag for users.

Correct: same-region. If the source must be cross-region, COPY into a same-region Lakehouse for hot data; shortcut for cold archival.

---

## 18. Spark `.collect()` on large Delta table

Wrong:
```python
data = spark.read.format("delta").load(path).collect()
# Driver OOM on large data
```

Correct:
```python
df = spark.read.format("delta").load(path)
df.write.format("delta").mode("append").saveAsTable("output")
# Or for analysis: df.toPandas() with .limit() on small subsets
```

---

## 19. Pipeline triggered on every file (instead of batch)

Wrong: file dropped every minute → pipeline runs every minute → 1440 runs/day × $0.X each = $$$.

Correct: batch trigger (every 15 min, every hour). Process all new files in one run. CU-friendly.

---

## 20. Reading Delta time-travel without bound

Wrong:
```sql
SELECT * FROM orders FOR VERSION AS OF 0;
-- Reads the very first version, often huge
```

Correct: time travel to a specific version close to a known event:
```sql
SELECT * FROM orders FOR TIMESTAMP AS OF '2026-04-25 09:00:00';
```

Or use `DESCRIBE HISTORY` first to find the relevant version:
```sql
DESCRIBE HISTORY orders LIMIT 10;
```

---

## See also

- `index.md`
- All `concepts/` and `patterns/`
