# KQL: error rate by operation

> **Last validated**: 2026-04-26
> **Confidence**: 0.94

## When to use

You want to know which operations are failing at what rate. Pairs with the latency-percentiles query — together they're the RED dashboard core (Rate / Errors / Duration).

## Implementation

```kusto
let lookback = 1h;

requests
| where timestamp > ago(lookback)
| summarize
    total       = sum(itemCount),
    failed      = sumif(itemCount, success == false),
    error_rate  = round(100.0 * sumif(itemCount, success == false) / sum(itemCount), 2)
    by name
| where total > 100   // ignore noise
| order by error_rate desc
```

Key points:
- `sum(itemCount)` not `count()` — accounts for sampling correctly.
- `sumif(itemCount, success == false)` is the sampled-aware version of "count of failures".
- `where total > 100` removes operations called once that happened to fail (skews "100% error rate" theatre).

## Variations

### Time series of error rate

```kusto
let lookback = 24h;

requests
| where timestamp > ago(lookback)
| where name == "POST /api/v1/agents"
| summarize
    total = sum(itemCount),
    failed = sumif(itemCount, success == false)
    by bin(timestamp, 5m)
| extend error_rate = round(100.0 * failed / total, 2)
| project timestamp, error_rate, total
| order by timestamp asc
| render timechart
```

Plot `error_rate` (left axis) and `total` (right axis) — context for whether a spike is an outage or just low volume.

### Group failures by status code

```kusto
requests
| where timestamp > ago(1h)
| where success == false
| summarize count_ = sum(itemCount) by name, resultCode
| order by count_ desc
```

`resultCode` is a string. For HTTP, common values are `"500"`, `"502"`, `"503"`, `"504"`, `"timeout"`, `"connection refused"`. For non-HTTP, it's the SDK-specific string.

### Top exceptions during failures

```kusto
let recent_failures = requests
    | where timestamp > ago(1h)
    | where success == false
    | project operation_Id;

exceptions
| where timestamp > ago(1h)
| where operation_Id in (recent_failures)
| summarize count_ = sum(itemCount) by type, outerMessage
| order by count_ desc
| take 20
```

Joins failed requests to their exception records via `operation_Id`. Groups by exception type — fast triage for "what's actually breaking?"

### Per-customer / tenant error rate

```kusto
requests
| where timestamp > ago(1h)
| extend tenant = tostring(customDimensions["tenant_id"])
| where isnotempty(tenant)
| summarize
    total = sum(itemCount),
    failed = sumif(itemCount, success == false)
    by tenant
| where total > 50
| extend error_rate = round(100.0 * failed / total, 2)
| order by error_rate desc
```

Only valid if `tenant_id` cardinality is bounded — review the cost-and-cardinality concept.

## Configuration

| Variable | Default | When to change |
|---|---|---|
| `lookback` | `1h` | `5m` for active incident; `24h` for daily report |
| `total > 100` threshold | `100` | Lower for low-traffic services; higher for high-traffic |

## Done when

- Query uses `sum(itemCount)` and `sumif(itemCount, ...)` — sampling-aware
- A volume threshold (`where total > N`) excludes noise
- The output sorts by error_rate descending
- For time-series version, both error_rate AND total appear (volume context)

## Anti-patterns

- `count()` instead of `sum(itemCount)` (under-counts when sampling is on)
- No volume threshold — operations called once with one failure show "100% error rate"
- Using `resultCode == 500` (int) instead of `resultCode == "500"` (string)
- Reporting averages of error rates instead of recomputing across the larger window
- Joining `requests` to all of `exceptions` without first filtering `exceptions` by time

## See also

- `concepts/kql-fundamentals.md` — `sumif`, `summarize`
- `concepts/application-insights-schema.md` — `success` vs `resultCode`
- `concepts/sampling-strategies.md` — why `itemCount` matters
- `patterns/kql-latency-percentiles.md` — companion latency query
- `patterns/kql-dependency-failure.md` — drill from failed request into the failed dependency
- `anti-patterns.md` (items 6, 7)
