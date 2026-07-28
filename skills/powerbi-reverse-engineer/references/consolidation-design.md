# Consolidation design

How to turn the harvested query registry into a single governed Fabric table.
Load this during Phase 4 of the skill.

## 1. Decide the grain first

Everything else follows from the grain of the consolidated table. State it as
one sentence: *"one row per `<entity>` per `<period/key>`"*.

- If the sources share a grain (e.g. many regional `Sales` tables) → the
  consolidation is a `UNION ALL`.
- If the sources are fact + dimensions at different grains → either join into a
  denormalized fact at the fact grain, or keep them as separate conformed tables
  and only denormalize what the report needs.
- If grains genuinely conflict and cannot reconcile → do **not** force one table.
  Recommend a small set of conformed tables and say so explicitly.

## 2. Conform the columns

Build a source-to-target column map. For each target column:

| Attribute | Rule |
|---|---|
| Name | One canonical name; map every source synonym to it. |
| Type | Widest safe common type; document any cast. |
| Nullability | Nullable if **any** source allows null. |
| Key | Mark business + surrogate keys; needed for `MERGE`. |

Resolve type and semantic mismatches here (e.g. `string` "Region" vs coded
`RegionId`) rather than in the build script.

## 3. Add lineage columns

Every consolidated row should carry provenance so the union is auditable:

- `source_model` — originating semantic model.
- `source_table` — originating table/partition.
- `source_system` — upstream system (from the M/SQL data source).
- `loaded_at` — load timestamp (UTC).

## 4. Choose the consolidation operation

| Pattern | When | Build shape |
|---|---|---|
| `UNION ALL` | Like tables, same grain | Stack, then dedup on business key |
| `JOIN` denormalize | Fact + dimensions | Join at fact grain, select conformed columns |
| Staged conform | Heterogeneous sources | Per-source staging view → conform → union |

## 5. DirectQuery → batch

DirectQuery sources are live; a single materialized table is not. For each DQ
source decide: scheduled copy/pipeline into the Lakehouse/Warehouse, or a OneLake
shortcut if the data is already in OneLake. Document the refresh cadence so the
consolidated table's freshness is explicit.

## 6. Dedup, SCD, and idempotency

- Dedup on the business key after union (keep latest by `loaded_at`).
- If history matters, decide SCD type (1 overwrite vs 2 versioned) before
  building — retrofitting SCD2 is expensive.
- The build must be **idempotent**: re-running produces no duplicates. Use
  `MERGE` on the business key (Delta or Warehouse) rather than blind `INSERT`.

## 7. Target choice: Lakehouse vs Warehouse

| Choose Lakehouse (Delta/Spark) when | Choose Warehouse (T-SQL) when |
|---|---|
| Sources are files / mixed / large-scale | Sources are relational and SQL-native |
| You want notebooks, `MERGE INTO` Delta | You want T-SQL `MERGE` / views |
| Downstream is Spark / ML | Downstream is BI / SQL analysts |

## 8. Validation contract (feeds Phase 6)

For each source slice, define:

- expected row count vs its slice in the target,
- a column checksum (sum/hash of a numeric or key column),
- one DAX aggregate from the original model vs the same aggregate on the target.

Record any value that cannot match (RLS-filtered rows, runtime-only params) as a
known residual gap rather than a defect.
