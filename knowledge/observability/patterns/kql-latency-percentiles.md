# KQL: latency percentiles over time

> **Last validated**: 2026-04-26
> **Confidence**: 0.94

## When to use

You need p50/p95/p99 latency for a service or operation. Single most-used dashboard query in any observability system.

## Implementation

```kusto
let lookback = 24h;
let bucket   = 5m;
let target_op = "POST /api/v1/agents";  // or remove the filter for all ops

requests
| where timestamp > ago(lookback)
| where name == target_op
| summarize
    p50 = percentile(duration, 50),
    p90 = percentile(duration, 90),
    p95 = percentile(duration, 95),
    p99 = percentile(duration, 99),
    count_ = sum(itemCount)
    by bin(timestamp, bucket)
| order by timestamp asc
| render timechart
```

`render timechart` produces a multi-series chart in the Application Insights portal. In Workbooks or Grafana, drop the render line and let the panel handle visualization.

## Variations

### All operations, top 10 by p95

```kusto
requests
| where timestamp > ago(24h)
| summarize
    p95 = percentile(duration, 95),
    count_ = sum(itemCount)
    by name
| where count_ > 100  // ignore rarely-called ops
| top 10 by p95 desc
```

### Per-instance comparison (find a slow node)

```kusto
requests
| where timestamp > ago(1h)
| where name == "POST /api/v1/agents"
| summarize p95 = percentile(duration, 95) by cloud_RoleInstance, bin(timestamp, 1m)
| render timechart
```

### Compare to a baseline (last week vs this week)

```kusto
let now_data = requests
    | where timestamp > ago(7d)
    | where name == "POST /api/v1/agents"
    | summarize p95_now = percentile(duration, 95) by bin(timestamp, 1h)
    | extend hour = bin(timestamp, 1h)
    | project hour, p95_now;

let last_week = requests
    | where timestamp between (ago(14d) .. ago(7d))
    | where name == "POST /api/v1/agents"
    | summarize p95_last = percentile(duration, 95) by bin(timestamp, 1h)
    | extend hour = bin(timestamp, 1h) + 7d  // shift forward
    | project hour, p95_last;

now_data
| join kind=fullouter last_week on hour
| project hour, p95_now, p95_last
| order by hour asc
| render timechart
```

### Slow tails — what's slower than X ms?

```kusto
requests
| where timestamp > ago(1h)
| where duration > 1000  // 1 second
| project timestamp, name, duration, operation_Id, cloud_RoleInstance
| order by duration desc
| take 20
```

The `operation_Id` here is your handle to drill into `dependencies` and `traces` for that specific request.

## Configuration

| Variable | Default | When to change |
|---|---|---|
| `lookback` | `24h` | `1h` for incident response; `7d` for trend reports |
| `bucket` | `5m` | Smaller (`30s`) for incidents; larger (`1h`) for daily reports |
| `target_op` | (removed) | Set when investigating one operation; remove for fleet view |

## Done when

- Query has `where timestamp > ago(...)` filter
- `summarize ... by bin(timestamp, ...)` for time series
- `count_` (or equivalent) is in the output to spot low-volume buckets where percentiles are unreliable
- `order by timestamp asc` so the chart renders left-to-right correctly
- The query runs in <5s on a normal workspace

## Anti-patterns

- Missing time filter (scans all retained data)
- `summarize ... by user_id` (cardinality explosion)
- Asking for p99.9 on low-traffic operation (single outlier dominates)
- `percentile(duration, 50, 95, 99)` instead of `percentiles(...)` — wrong syntax, the multi-percentile function is plural
- `avg(duration)` instead of percentiles (averages hide tail latency)

## See also

- `concepts/kql-fundamentals.md` — KQL syntax basics
- `concepts/application-insights-schema.md` — what's in `requests`
- `patterns/kql-error-rate-by-operation.md` — companion query for failure rates
- `anti-patterns.md` (items 9, 10, 17)
