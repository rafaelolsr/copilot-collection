# Storage modes — Import, DirectLake, DirectQuery

> **Last validated**: 2026-04-26
> **Confidence**: 0.91

## The 3 modes

| Mode | Where data lives | Refresh | DAX | When |
|---|---|---|---|---|
| **Import** | In-memory (compressed) in semantic model | Scheduled | Full | Small/medium models, complex transforms |
| **DirectLake** | Fabric Lakehouse Delta tables (OneLake) | Auto on Delta updates | Full | Fabric, large models, near-real-time |
| **DirectQuery** | Source database (translated to SQL/M each query) | Live | Limited | >10GB models, regulatory data residency, real-time |

Import is the historical default. DirectLake is the modern default for Fabric workloads. DirectQuery is a fallback for specific constraints.

## Import mode

- Data is loaded at refresh time, compressed via VertiPaq, kept in memory
- Refresh durations scale with row count and number of transforms
- DAX has full power — every function works
- Limit: model size cap (1GB on Pro, 10GB+ on Premium / Fabric capacity)

```tmdl
table Sales
    partition Sales = m
        mode: import       # default; can be omitted
        source = ```
            // Power Query
        ```
```

## DirectLake mode

Fabric-only. The semantic model points at Delta tables in OneLake. No copy, no refresh — when the Delta table updates, the model sees fresh data on the next query.

Caveats:
- Falls back to DirectQuery for unsupported operations (calculated columns, certain transforms)
- Best when the underlying Delta is V-Order optimized
- Only works against Fabric-hosted Delta (Lakehouse / Warehouse)

```tmdl
table Sales
    partition Sales = entity
        mode: directLake
        source
            entityName: Sales
            schemaName: dbo
            expressionSource: 'My Lakehouse'
```

DirectLake-on-OneLake (newer): supports cross-workspace and federated scenarios.

## DirectQuery mode

The semantic model translates each user query into SQL (or M) and runs it against the source. Data never leaves the source.

Caveats:
- DAX functions limited — `CALCULATE` works, but iterators and some functions either don't work or run slowly
- Performance depends entirely on source query speed
- Adds load to the source database
- Some Power BI features (Q&A, Smart Narrative, what-if parameters) limited

```tmdl
table Sales
    partition Sales = m
        mode: directQuery
        source = ```
            let
                Source = Sql.Database("server", "db"),
                Sales = Source{[Schema="dbo", Item="Sales"]}[Data]
            in
                Sales
        ```
```

## Composite models

Mix modes in one semantic model:

```tmdl
table Sales            # large fact — DirectQuery
    partition Sales = m
        mode: directQuery

table DateTable        # small dim — Import
    partition DateTable = m
        mode: import

table Customer         # also Import
    partition Customer = m
        mode: import
```

Composite is powerful but adds complexity:
- Cross-source joins happen in the model layer (slow if not careful)
- Aggregation tables can speed up DirectQuery (define summary Import tables that the engine uses for high-level queries)

## DAX behavior differences

Import / DirectLake (full DAX) supports everything. DirectQuery has limits:

- `EARLIER` — works
- `EARLIEST` — works
- `EVALUATE` queries — limited; some functions block translation
- `RANKX`, `TOPN` — work but slow
- `CALENDAR`, `CALENDARAUTO` — work but generated table is in-memory; not useful in DirectQuery model alone
- `USERPRINCIPALNAME()` — works for RLS
- Time-intelligence functions — work, but require Import-mode date table or the date table being DirectQuery against the same source

The agent's job: when reviewing DAX in a DirectQuery model, flag iterators and functions known to be slow. Suggest moving the table to Import or Composite.

## Migration cheatsheet

| Have | Want | Path |
|---|---|---|
| Import, growing past capacity | DirectLake | Move source to Fabric Lakehouse, switch mode |
| DirectQuery, slow | Composite (aggregations) | Add aggregation tables in Import mode |
| Import, need real-time | DirectQuery on the fact, Import dims | Composite |
| DirectLake | Import | Lose real-time, gain full DAX | Reverse |

## Common bugs

- DirectQuery + iterator over a large table → query times out
- Time intelligence in DirectQuery without an Import-mode date table → wrong results
- DirectLake silently falling back to DirectQuery for one calculated column → drag everything down
- Mixing case-sensitivity expectations (DirectQuery on Postgres vs Import — different defaults)
- `USERPRINCIPALNAME()` in DirectQuery RLS works only if the source supports the SQL translation

## See also

- `concepts/dax-evaluation-context.md`
- `concepts/relationships-and-cardinality.md`
- `anti-patterns.md` (items 6, 11)
