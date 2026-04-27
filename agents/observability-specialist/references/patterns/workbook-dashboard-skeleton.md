# Workbook dashboard skeleton (RED)

> **Last validated**: 2026-04-26
> **Confidence**: 0.88
> **Source**: https://learn.microsoft.com/en-us/azure/azure-monitor/visualize/workbooks-overview

## When to use this pattern

Building a service dashboard following the **RED** methodology — Rate, Errors, Duration. Standard for any user-facing service.

(For infrastructure: USE = Utilization / Saturation / Errors. Different methodology, similar Workbook structure.)

## Workbook layout

```
┌─────────────────────────────────────────────────┐
│  Header — service name, environment, time range │
├─────────────────────────────────────────────────┤
│  KPI tiles: req/sec | error rate | p95 latency  │
├─────────────────┬───────────────────────────────┤
│  Rate           │  Error rate                    │
│  (timechart)    │  (timechart)                   │
├─────────────────┴───────────────────────────────┤
│  Latency p50/p95/p99                             │
│  (timechart)                                     │
├─────────────────────────────────────────────────┤
│  Top operations by request count                 │
│  (table)                                         │
├─────────────────────────────────────────────────┤
│  Top failing operations                          │
│  (table)                                         │
├─────────────────────────────────────────────────┤
│  Top exceptions                                  │
│  (table)                                         │
└─────────────────────────────────────────────────┘
```

## Time-range parameter

Every Workbook needs a `TimeRange` parameter. Set as a parameter at the top — every query uses it:

```kusto
requests
| where timestamp {TimeRange}    // workbook syntax
| where cloud_RoleName == "{ServiceName}"
| ...
```

## KPI tile queries

### Request rate (req/sec)

```kusto
requests
| where timestamp {TimeRange}
| where cloud_RoleName == "{ServiceName}"
| summarize total = sum(itemCount)
| extend req_per_sec = round(total / (totimespan({TimeRange}) / 1s), 2)
| project req_per_sec
```

### Error rate (%)

```kusto
requests
| where timestamp {TimeRange}
| where cloud_RoleName == "{ServiceName}"
| summarize
    total = sum(itemCount),
    failed = sumif(itemCount, success == false)
| extend error_rate = round(100.0 * failed / total, 2)
| project error_rate
```

### p95 latency (ms)

```kusto
requests
| where timestamp {TimeRange}
| where cloud_RoleName == "{ServiceName}"
| summarize p95 = percentile(duration, 95)
| project p95
```

## Time-series panel queries

### Rate over time

```kusto
requests
| where timestamp {TimeRange}
| where cloud_RoleName == "{ServiceName}"
| summarize requests = sum(itemCount) by bin(timestamp, 5m)
| order by timestamp asc
| render timechart
```

### Error rate over time

```kusto
requests
| where timestamp {TimeRange}
| where cloud_RoleName == "{ServiceName}"
| summarize
    total = sum(itemCount),
    failed = sumif(itemCount, success == false)
    by bin(timestamp, 5m)
| extend error_rate = round(100.0 * failed / total, 2)
| project timestamp, error_rate
| order by timestamp asc
| render timechart
```

### Latency percentiles over time

```kusto
requests
| where timestamp {TimeRange}
| where cloud_RoleName == "{ServiceName}"
| summarize
    p50 = percentile(duration, 50),
    p95 = percentile(duration, 95),
    p99 = percentile(duration, 99)
    by bin(timestamp, 5m)
| order by timestamp asc
| render timechart
```

## Table panels

### Top operations

```kusto
requests
| where timestamp {TimeRange}
| where cloud_RoleName == "{ServiceName}"
| summarize
    requests = sum(itemCount),
    p95_ms   = round(percentile(duration, 95), 0),
    error_rate = round(100.0 * sumif(itemCount, success == false) / sum(itemCount), 2)
    by name
| top 20 by requests desc
```

### Top failing operations

```kusto
requests
| where timestamp {TimeRange}
| where cloud_RoleName == "{ServiceName}"
| summarize
    total      = sum(itemCount),
    failed     = sumif(itemCount, success == false),
    error_rate = round(100.0 * sumif(itemCount, success == false) / sum(itemCount), 2)
    by name
| where total > 50
| top 20 by error_rate desc
```

### Top exceptions

```kusto
exceptions
| where timestamp {TimeRange}
| where cloud_RoleName == "{ServiceName}"
| summarize
    occurrences = sum(itemCount),
    sample      = any(outerMessage)
    by problemId, type
| top 20 by occurrences desc
```

## Workbook JSON skeleton

A Workbook is JSON. The structure (simplified):

```json
{
  "version": "Notebook/1.0",
  "items": [
    {
      "type": 9,
      "content": {
        "version": "KqlParameterItem/1.0",
        "parameters": [
          { "id": "TimeRange", "type": 4, "value": { "durationMs": 3600000 } },
          { "id": "ServiceName", "type": 1, "value": "starbase-prod" }
        ]
      }
    },
    {
      "type": 1,
      "content": { "json": "## Service Health — {ServiceName}" }
    },
    {
      "type": 3,
      "content": {
        "version": "KqlItem/1.0",
        "query": "requests | where timestamp {TimeRange} | where cloud_RoleName == \"{ServiceName}\" | summarize total = sum(itemCount) | project total",
        "size": 4,
        "queryType": 0,
        "resourceType": "microsoft.insights/components",
        "visualization": "tiles"
      }
    }
  ]
}
```

You don't write this by hand — build the Workbook in the portal, then **Edit → Advanced Editor** to export the JSON. Commit the JSON to source control alongside the service code.

## Done when

- Workbook has `TimeRange` and `ServiceName` parameters
- Every panel filters by both
- 3 KPI tiles (rate, error rate, p95)
- 3 time-series panels (rate, error rate, percentiles)
- 3 tables (top ops, top failing, top exceptions)
- JSON exported to source control
- Documented `cloud_RoleName` is the env-prod service identifier

## Anti-patterns

- Workbook with no `TimeRange` parameter (every panel hardcoded to a window)
- Hardcoded subscription / resource IDs in the JSON (breaks when promoted)
- Mixing services in the same Workbook without a service filter
- Using `count()` instead of `sum(itemCount)` — undercounts with sampling
- 1-second `bin()` over 24 hours → 86,400 buckets, slow render
- Workbook never committed to source control (lost on accidental delete)

## See also

- `patterns/kql-latency-percentiles.md` — the panel queries explained
- `patterns/kql-error-rate-by-operation.md` — same
- `patterns/kql-dependency-failure.md` — drill-down panels
- `concepts/cost-and-cardinality.md` — keep dashboard queries cheap
