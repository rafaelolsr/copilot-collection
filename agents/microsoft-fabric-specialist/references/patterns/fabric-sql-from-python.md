# Fabric SQL endpoint from Python

> **Last validated**: 2026-04-26
> **Confidence**: 0.88

## When to use this pattern

Reading from a Fabric Lakehouse / Warehouse via T-SQL from a Python service or script. Useful for:
- Small-to-medium reads (<1M rows) where Spark cluster startup is overkill
- Calling stored procedures (Warehouse only)
- Generating reports / extracts without standing up Spark

For large reads (>10M rows), prefer `deltalake` Python directly (skips the SQL endpoint roundtrip) — see `patterns/delta-write-with-deltalake-python.md` for read examples.

## Install

```bash
uv pip install pyodbc azure-identity
```

System dependency: ODBC Driver 18 for SQL Server (or 17 minimum).

```bash
# macOS
brew tap microsoft/mssql-release https://github.com/microsoft/homebrew-mssql-release
brew install msodbcsql18

# Ubuntu / Debian
curl https://packages.microsoft.com/keys/microsoft.asc | sudo apt-key add -
curl https://packages.microsoft.com/config/ubuntu/22.04/prod.list | sudo tee /etc/apt/sources.list.d/mssql-release.list
sudo apt-get update
sudo apt-get install -y msodbcsql18

# Windows
# Download from https://learn.microsoft.com/sql/connect/odbc/download-odbc-driver-for-sql-server
```

## Connection — managed identity / Entra

```python
import pyodbc
import struct
from azure.identity import DefaultAzureCredential


def fabric_sql_connection(
    *,
    endpoint: str,                                              # e.g., "myworkspace-abcd.datawarehouse.fabric.microsoft.com"
    database: str,                                              # Lakehouse or Warehouse name
) -> pyodbc.Connection:
    cred = DefaultAzureCredential()
    token_obj = cred.get_token("https://database.windows.net/.default")

    # Encode token for ODBC's SQL_COPT_SS_ACCESS_TOKEN (1256)
    encoded = bytes(token_obj.token, "utf-16-le")
    token_struct = struct.pack(f"<I{len(encoded)}s", len(encoded), encoded)

    conn_str = (
        "Driver={ODBC Driver 18 for SQL Server};"
        f"Server={endpoint},1433;"
        f"Database={database};"
        "Encrypt=yes;"
        "TrustServerCertificate=no;"
        "Connection Timeout=30;"
    )

    return pyodbc.connect(conn_str, attrs_before={1256: token_struct})
```

## Basic query

```python
def list_recent_orders(conn: pyodbc.Connection, days: int = 7) -> list[dict]:
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT order_id, customer_id, amount, order_date
        FROM dbo.orders
        WHERE order_date >= DATEADD(day, -?, GETDATE())
        ORDER BY order_date DESC;
        """,
        days,
    )
    columns = [c[0] for c in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]
```

## Parameterized always

```python
# CORRECT
cursor.execute(
    "SELECT * FROM dbo.orders WHERE region = ? AND order_date BETWEEN ? AND ?",
    region, start_date, end_date,
)

# WRONG — SQL injection
cursor.execute(
    f"SELECT * FROM dbo.orders WHERE region = '{region}'"
)
```

## Streaming reads (large result sets)

```python
def stream_orders(conn, predicate: str, *params, batch_size: int = 10_000):
    cursor = conn.cursor()
    cursor.execute(f"SELECT * FROM dbo.orders WHERE {predicate}", *params)
    columns = [c[0] for c in cursor.description]
    while True:
        rows = cursor.fetchmany(batch_size)
        if not rows:
            break
        yield [dict(zip(columns, r)) for r in rows]


for batch in stream_orders(conn, "order_date >= ?", "2026-01-01"):
    process(batch)
```

`fetchmany` lets you process in chunks without loading everything into memory.

## Pandas / pyarrow integration

```python
import pandas as pd

def query_to_pandas(conn, sql: str, *params) -> pd.DataFrame:
    return pd.read_sql(sql, conn, params=params)


df = query_to_pandas(
    conn,
    "SELECT order_date, region, SUM(amount) AS total FROM dbo.orders GROUP BY order_date, region",
)
```

For larger results, prefer pyarrow's chunked reader + Arrow writer to Delta directly.

## Stored procedure call (Warehouse)

```python
cursor = conn.cursor()
cursor.execute(
    "EXEC dbo.refresh_aggregations @start_date = ?, @end_date = ?",
    start_date, end_date,
)
conn.commit()                                                   # required for procs that modify
```

Catching procedure errors:

```python
try:
    cursor.execute("EXEC dbo.tricky_proc")
    conn.commit()
except pyodbc.ProgrammingError as e:
    # SQL-level error from inside the proc
    logger.exception("proc_failed", extra={"error": str(e)})
    conn.rollback()
    raise
```

## Token refresh (long-running scripts)

Tokens expire ~1 hour. For a service that runs longer:

```python
import time

class FabricSqlPool:
    def __init__(self, endpoint: str, database: str):
        self._endpoint = endpoint
        self._database = database
        self._cred = DefaultAzureCredential()
        self._conn: pyodbc.Connection | None = None
        self._token_expires_at: float = 0.0

    def get_connection(self) -> pyodbc.Connection:
        if self._conn and time.time() < self._token_expires_at - 60:
            return self._conn
        # Refresh — close old, open new
        if self._conn:
            self._conn.close()
        self._conn = fabric_sql_connection(
            endpoint=self._endpoint,
            database=self._database,
        )
        self._token_expires_at = time.time() + 3500             # ~1 hour
        return self._conn
```

For very high-throughput services, use a real connection pool library (e.g., `sqlalchemy` with custom token-injecting events).

## Read-only Lakehouse vs writable Warehouse

| Operation | Lakehouse SQL endpoint | Warehouse |
|---|---|---|
| `SELECT` | YES | YES |
| `INSERT` / `UPDATE` / `DELETE` / `MERGE` | NO | YES |
| `CREATE VIEW` | YES | YES |
| `CREATE TABLE` | NO | YES |
| `EXEC <stored_proc>` | NO (no proc creation) | YES |

Trying to write to Lakehouse SQL endpoint silently fails or errors depending on driver. Use `deltalake` Python or PySpark to write to a Lakehouse.

## Error handling

```python
import pyodbc
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(min=2, max=30),
    retry=retry_if_exception_type((pyodbc.OperationalError, pyodbc.InterfaceError)),
    reraise=True,
)
def query_with_retry(conn, sql, *params):
    cursor = conn.cursor()
    cursor.execute(sql, *params)
    return cursor.fetchall()
```

Retry only on transient (network / connection) errors. Don't retry `pyodbc.ProgrammingError` (that's your SQL being wrong).

## Common bugs

- Old ODBC driver (< 18) — TLS / AAD failures
- `Trusted_Connection=yes` (Windows-style integrated auth — won't work)
- Token cached too long → 401 mid-script
- `cursor.fetchall()` on a 10M-row result → OOM
- String interpolation for params → SQL injection
- Forgot `Encrypt=yes` → connection refused
- Wrong database name (use the Lakehouse / Warehouse name, NOT a SQL Server "Initial Catalog" alias)
- Cross-workspace 3-part name (won't resolve)

## Done when

- AAD token-based auth (no SQL auth, no integrated)
- Parameterized queries (no string interpolation)
- Streaming for large reads (`fetchmany` not `fetchall`)
- Connection pool / token refresh for long-running services
- Retry on transient errors only
- Errors logged with the SQL that failed (sanitize params first)

## See also

- `concepts/fabric-sql-endpoint.md` — what's supported
- `concepts/lakehouse-vs-warehouse.md` — read-only vs writable
- `patterns/delta-write-with-deltalake-python.md` — for writes (Lakehouse)
- `anti-patterns.md` (items 1, 14, 18)
