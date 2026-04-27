# KQL fundamentals

> **Last validated**: 2026-04-26
> **Confidence**: 0.95
> **Source**: https://learn.microsoft.com/en-us/kusto/query/

## Mental model

KQL queries flow left-to-right through pipe operators. Each operator transforms the table:

```kusto
TableName
| where <filter>           // narrow rows
| project <columns>        // narrow columns
| summarize <aggregations> // collapse rows into groups
| order by <column> desc   // sort
| take 10                  // limit
```

The order matters: `take 10 | where x > 5` returns at most 10 rows then filters; `where x > 5 | take 10` filters first then limits. Almost always you want filter-first.

## Time filters — always required

Every production query MUST have a time filter on an indexed time column. Without it the query scans all retained data — slow and expensive.

```kusto
requests
| where timestamp > ago(1h)
```

`ago()` is short for "now minus". `between(...)` for absolute ranges:

```kusto
requests
| where timestamp between (datetime(2026-04-25) .. datetime(2026-04-26))
```

The `timestamp` column is the indexed default in Application Insights tables. Custom tables may use a different name — check the schema.

## Selecting columns

```kusto
requests
| where timestamp > ago(1h)
| project timestamp, name, duration, resultCode, success
```

`project` returns only the listed columns. `extend` adds columns without removing existing ones:

```kusto
requests
| extend duration_seconds = duration / 1000
```

Use `project-away` to drop specific columns and keep the rest.

## Aggregation: `summarize`

```kusto
requests
| where timestamp > ago(24h)
| summarize count() by name
| order by count_ desc
| take 10
```

The grouping is `by <column1>, <column2>`. Without `by`, you collapse to a single row.

Common aggregation functions:
- `count()` — number of rows
- `countif(<predicate>)` — conditional count
- `sum(col)` / `avg(col)` / `min(col)` / `max(col)`
- `dcount(col)` — distinct count (approximate, fast)
- `percentile(col, 95)` — single percentile
- `percentiles(col, 50, 95, 99)` — multiple percentiles

## Time-series with `bin()`

For time-series charts, group by a time bucket:

```kusto
requests
| where timestamp > ago(24h)
| summarize
    p50 = percentile(duration, 50),
    p95 = percentile(duration, 95),
    p99 = percentile(duration, 99)
    by bin(timestamp, 5m)
| render timechart
```

`bin(timestamp, 5m)` rounds each timestamp down to the nearest 5-minute boundary. `render timechart` produces a time-series chart in the portal.

## Joins

Use `join kind=` explicitly. Default is `innerunique`, often surprising:

```kusto
requests
| where timestamp > ago(1h)
| join kind=inner (
    dependencies
    | where timestamp > ago(1h)
) on operation_Id
```

`kind` options:
- `inner` — only matching rows from both
- `leftouter` — all from left, nulls for non-matches
- `rightouter` / `fullouter`
- `leftsemi` — left rows where a match exists in right
- `leftanti` — left rows where NO match exists in right (useful for "what failed without a successful retry?")

Always filter both sides before joining — joining unfiltered tables is slow.

## Variables with `let`

```kusto
let lookback = 24h;
let slow_threshold_ms = 1000;
requests
| where timestamp > ago(lookback)
| where duration > slow_threshold_ms
| count
```

`let` makes queries readable and parameterizable. Place them at the top.

## Conditional aggregations: `countif`

```kusto
requests
| where timestamp > ago(1h)
| summarize
    total = count(),
    failed = countif(success == false),
    error_rate = round(100.0 * countif(success == false) / count(), 2)
    by name
| where total > 100
| order by error_rate desc
```

## Top-N

```kusto
requests
| where timestamp > ago(24h)
| top 10 by duration desc
```

`top N by col` is shorthand for `order by col | take N`. Faster than the explicit form.

## Common pitfalls

- **Missing `where timestamp >` filter** → scans all retained data, slow + costly
- **`summarize ... by user_id`** with millions of users → unbounded cardinality, query times out
- **Joining unfiltered tables** → cross-join blowup
- **`order by` without `take`** → tries to sort the whole result set in memory
- **`distinct` on high-cardinality columns** → use `dcount` (approximate) when exact count not needed
- **Nested subqueries when `let` would do** → harder to read and optimize

## See also

- `concepts/application-insights-schema.md` — what columns exist in each table
- `concepts/cost-and-cardinality.md` — why cardinality matters
- `patterns/kql-latency-percentiles.md` — production-ready percentile query
- `anti-patterns.md` (items 3, 9, 10, 17)
