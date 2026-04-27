# Microsoft Fabric Knowledge Base — Index

> **Last validated**: 2026-04-26
> **Confidence**: 0.91
> **Scope**: Lakehouse, Warehouse, OneLake, Delta tables (V-Order, OPTIMIZE, VACUUM), shortcuts, Fabric SQL endpoint, semantic model REST API, capacity SKUs, Fabric permissions.

## KB Structure

### Concepts

| File | Topic | Status |
|---|---|---|
| `concepts/fabric-workspace-and-capacity.md` | Workspaces, capacities (F2-F64+), what runs where | Validated |
| `concepts/lakehouse-vs-warehouse.md` | When to use each, schema, write methods | Validated |
| `concepts/onelake-and-shortcuts.md` | OneLake paths, shortcut types, ACL inheritance | Validated |
| `concepts/delta-table-fundamentals.md` | V-Order, OPTIMIZE, VACUUM, time travel, partitioning | Validated |
| `concepts/semantic-model-rest-api.md` | refresh, RLS, dataset / dataflow APIs | Validated |
| `concepts/fabric-sql-endpoint.md` | T-SQL on Lakehouse, what works, what doesn't | Validated |
| `concepts/fabric-permissions-model.md` | Workspace roles, item permissions, OneLake ACLs | Validated |

### Patterns

| File | Topic |
|---|---|
| `patterns/delta-write-with-deltalake-python.md` | `deltalake` library writes with V-Order, schema |
| `patterns/fabric-rest-client-managed-identity.md` | Auth, retry on 429, pagination |
| `patterns/medallion-bronze-silver-gold.md` | Pipeline pattern for ingestion → curated |
| `patterns/semantic-model-refresh-via-api.md` | Trigger refresh, wait, error handling |
| `patterns/fabric-sql-from-python.md` | pyodbc + Entra auth, parameterized queries |
| `patterns/onelake-shortcut-to-adls.md` | Connect external Delta without copy |

### Reference

| File | Topic |
|---|---|
| `anti-patterns.md` | 20 Fabric anti-patterns to flag on sight |

## Reading Protocol

1. Start here (`index.md`) to identify relevant files for the task.
2. For task type → file map:
   - "write a Delta table" → `concepts/delta-table-fundamentals.md` + `patterns/delta-write-with-deltalake-python.md`
   - "Lakehouse vs Warehouse?" → `concepts/lakehouse-vs-warehouse.md`
   - "set up a shortcut" → `concepts/onelake-and-shortcuts.md` + `patterns/onelake-shortcut-to-adls.md`
   - "refresh a dataset" → `patterns/semantic-model-refresh-via-api.md`
   - "query Fabric SQL from Python" → `patterns/fabric-sql-from-python.md`
   - "design a medallion pipeline" → `patterns/medallion-bronze-silver-gold.md`
   - "auth to Fabric API" → `patterns/fabric-rest-client-managed-identity.md`
   - "review my Fabric code" → `anti-patterns.md`
3. If any file has `last_validated` older than 90 days, use `web` tool to re-validate against:
   - https://learn.microsoft.com/en-us/fabric/
   - https://learn.microsoft.com/en-us/rest/api/fabric/
   - https://learn.microsoft.com/en-us/rest/api/power-bi/
   - https://delta.io/
4. Check `anti-patterns.md` whenever reviewing user Fabric code.
