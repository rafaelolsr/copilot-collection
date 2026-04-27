# Fabric SQL endpoint

> **Last validated**: 2026-04-26
> **Confidence**: 0.89

## What it is

Every Lakehouse and Warehouse exposes a T-SQL endpoint reachable from any tool that speaks TDS / OLE DB:

- Power BI Desktop
- SSMS
- Azure Data Studio
- DBeaver
- pyodbc / pymssql Python
- Spark JDBC
- Fabric notebooks

Endpoint URL format:
```
<workspace>-<random>.datawarehouse.fabric.microsoft.com
```

Get from: Fabric portal → Lakehouse / Warehouse → Settings → SQL endpoint → Copy.

## Lakehouse SQL endpoint vs Warehouse

| Aspect | Lakehouse | Warehouse |
|---|---|---|
| Read | Yes | Yes |
| Write (INSERT, UPDATE, DELETE, MERGE) | NO | YES |
| CREATE / ALTER TABLE | NO | YES |
| Stored procedures, views | Views YES; procs NO | Both YES |
| Security (CLS, RLS) | Limited | Full |

Lakehouse SQL endpoint is read-only. To write, use Spark / `deltalake` Python / Pipelines / Dataflow Gen2.

## Auth

Microsoft Entra (Azure AD) only. Connection string with `Authentication=ActiveDirectoryDefault` + a credential resolved by `DefaultAzureCredential`-equivalent, or interactive AAD.

```python
import pyodbc
from azure.identity import DefaultAzureCredential

cred = DefaultAzureCredential()
token = cred.get_token("https://database.windows.net/.default").token
import struct
encoded_token = bytes(token, "utf-16-le")
token_struct = struct.pack(f"<I{len(encoded_token)}s", len(encoded_token), encoded_token)

conn = pyodbc.connect(
    "Driver={ODBC Driver 18 for SQL Server};"
    "Server=<endpoint>.datawarehouse.fabric.microsoft.com,1433;"
    "Database=<lakehouse-or-warehouse-name>;"
    "Encrypt=yes;",
    attrs_before={1256: token_struct},                         # SQL_COPT_SS_ACCESS_TOKEN
)
```

`1256` is the magic ODBC attribute key for AAD bearer token. Required because pyodbc doesn't natively support AAD; you inject the token at connect time.

## Query basics

Standard T-SQL:

```sql
SELECT order_date, region, SUM(amount) AS total
FROM dbo.orders
WHERE order_date BETWEEN '2026-04-01' AND '2026-04-30'
GROUP BY order_date, region
ORDER BY order_date;
```

Three-part names work across Lakehouses / Warehouses in the same workspace:

```sql
-- Query a Lakehouse table from a Warehouse
SELECT * FROM SalesLakehouse.dbo.orders;

-- Query a Warehouse table from a Lakehouse SQL endpoint
SELECT * FROM SalesWarehouse.dbo.customers;
```

Cross-workspace requires shortcuts (no direct cross-workspace 3-part references).

## What's supported / what isn't

**Supported in Lakehouse SQL endpoint (read-only)**:
- `SELECT`, `JOIN`, CTEs, window functions
- `CREATE VIEW`, `DROP VIEW`
- Most standard T-SQL functions
- `OPENROWSET` for ad-hoc parquet reads
- Variables, control-of-flow (in batch / procedure context — limited)

**NOT supported in Lakehouse SQL endpoint**:
- `INSERT`, `UPDATE`, `DELETE`, `MERGE`
- `CREATE TABLE` (read-only)
- `ALTER TABLE`
- Stored procedures (you can't create them; views OK)
- `BACKUP` / `RESTORE`

**Warehouse adds**:
- Full DML (`INSERT`, `UPDATE`, `DELETE`, `MERGE`, `COPY INTO`)
- `CREATE TABLE`, `ALTER TABLE`
- Stored procedures
- Views, functions
- TRUNCATE, transactions

## Performance considerations

The SQL endpoint scans Delta tables in OneLake. Performance depends on:
- **V-Order**: tables written without V-Order are 3-5× slower
- **OPTIMIZE / file size**: many small files = slow scans; OPTIMIZE compacts
- **Partition pruning**: filters on partition columns skip irrelevant folders
- **Statistics**: auto-collected; stale on rapidly-changing tables

For BI dashboards: prefer DirectLake over T-SQL endpoint. DirectLake serves the same data, optimized further for the analysis engine.

For ad-hoc analysis / non-BI tools: SQL endpoint is convenient.

## Parameterized queries from Python

```python
cursor = conn.cursor()
cursor.execute(
    "SELECT * FROM dbo.orders WHERE region = ? AND order_date BETWEEN ? AND ?",
    "North", "2026-04-01", "2026-04-30",
)
rows = cursor.fetchall()
```

Always parameterize. NEVER string-interpolate user input — SQL injection.

## Streaming reads (large tables)

```python
cursor.execute("SELECT * FROM dbo.orders WHERE order_date > ?", "2026-01-01")
while True:
    rows = cursor.fetchmany(10_000)
    if not rows:
        break
    process(rows)
```

Don't `cursor.fetchall()` on a 100M-row table — driver OOM.

For larger reads: use `deltalake` Python directly against OneLake (skips the SQL endpoint roundtrip):

```python
from deltalake import DeltaTable
dt = DeltaTable("abfss://...Tables/orders")
df = dt.to_pandas(filters=[("order_date", ">=", "2026-01-01")])
```

## Views as the API for the SQL endpoint

For complex queries reused across many consumers, define a view in the Lakehouse / Warehouse:

```sql
CREATE OR ALTER VIEW dbo.daily_sales AS
SELECT
    order_date,
    region,
    SUM(amount) AS total_sales,
    COUNT(*) AS order_count
FROM dbo.orders
GROUP BY order_date, region;
```

Power BI / clients hit the view; you change the underlying logic without breaking dependents.

## Common bugs

- `SELECT *` on a wide / large table — slow + bandwidth-heavy
- Trying to `INSERT` into a Lakehouse SQL endpoint (silent or error — depends on tool)
- Using SQL Server-style integrated auth (`Trusted_Connection=yes`) — won't work; need AAD
- Connection string missing `Encrypt=yes` — Fabric requires it
- `pyodbc` driver version too old (< 18) — TLS / AAD failures
- Cross-workspace 3-part name (won't resolve)
- Querying without time filter on a partitioned table (no pruning)

## See also

- `concepts/lakehouse-vs-warehouse.md`
- `concepts/delta-table-fundamentals.md` (V-Order, OPTIMIZE)
- `patterns/fabric-sql-from-python.md` — full client pattern
- `anti-patterns.md` (items 14, 18)
