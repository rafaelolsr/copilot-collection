# KQL: dependency failure root-cause analysis

> **Last validated**: 2026-04-26
> **Confidence**: 0.92

## When to use

A user request failed (or got slow). You want to know WHY. The pattern: starting from a failed `requests` row, find the failed `dependencies` and `exceptions` correlated via `operation_Id`.

## Implementation — full timeline of one operation

```kusto
let target_operation_id = "<paste operation_Id from the failed request>";
let window = 5m;

union requests, dependencies, exceptions, traces
| where timestamp between (
    todatetime(toscalar(
        union requests, dependencies, exceptions, traces
        | where operation_Id == target_operation_id
        | summarize min(timestamp)
    )) - window ..
    todatetime(toscalar(
        union requests, dependencies, exceptions, traces
        | where operation_Id == target_operation_id
        | summarize max(timestamp)
    )) + window
)
| where operation_Id == target_operation_id
| project
    timestamp,
    itemType,
    name = coalesce(name, type),
    duration,
    success,
    resultCode,
    message,
    severityLevel,
    target,
    outerMessage = case(itemType == "exception", outerMessage, "")
| order by timestamp asc
```

Returns one row per telemetry item that participated in the operation, in chronological order. Spot the failure point at a glance.

## Implementation — aggregate failures by dependency target

```kusto
let lookback = 1h;

let failed_requests = requests
    | where timestamp > ago(lookback)
    | where success == false
    | project request_op = operation_Id, request_name = name;

dependencies
| where timestamp > ago(lookback)
| where success == false
| join kind=inner failed_requests on $left.operation_Id == $right.request_op
| summarize
    failures = sum(itemCount),
    sample_request = any(request_name)
    by target, type, name
| order by failures desc
| take 20
```

Output: which downstream services / DBs / APIs are failing during failed user requests. Top of the list = your culprit.

## Implementation — slow dependency that's making requests slow

```kusto
let lookback = 1h;
let slow_request_threshold = 1000;  // ms

let slow_requests = requests
    | where timestamp > ago(lookback)
    | where duration > slow_request_threshold
    | project op = operation_Id, request_name = name, request_duration = duration;

dependencies
| where timestamp > ago(lookback)
| join kind=inner slow_requests on $left.operation_Id == $right.op
| summarize
    avg_dep_duration  = avg(duration),
    p95_dep_duration  = percentile(duration, 95),
    count_            = count()
    by target, type, name
| where count_ > 10
| order by p95_dep_duration desc
| take 20
```

Returns dependency calls that are slow within slow user requests. The dependency at the top is most likely the cause.

## Implementation — exception clusters

```kusto
let lookback = 1h;

exceptions
| where timestamp > ago(lookback)
| summarize
    count_ = sum(itemCount),
    sample_message = any(outerMessage),
    sample_op = any(operation_Id)
    by type, problemId
| order by count_ desc
| take 20
```

`problemId` is App Insights' grouping key — same exception across many requests has the same `problemId`. Use it to deduplicate when investigating.

For one specific exception, get a representative trace:

```kusto
exceptions
| where timestamp > ago(1h)
| where problemId == "<specific problem ID>"
| take 1
| project operation_Id, timestamp, type, outerMessage, details
```

Then take that `operation_Id` back to the full-timeline query above.

## Implementation — failure cascade visualization

```kusto
let lookback = 1h;

requests
| where timestamp > ago(lookback)
| where success == false
| join kind=inner (
    dependencies
    | where timestamp > ago(lookback)
    | where success == false
    | project operation_Id, dep_target = target, dep_type = type
) on operation_Id
| summarize cascade = sum(itemCount) by request_name = name, dep_target, dep_type
| order by cascade desc
```

Shows cascades like:
- `POST /checkout` → `sql-db.example.com` (timeout) — 145 occurrences
- `GET /products` → `inventory-svc` (502) — 98 occurrences

## Done when

- Query uses `union` + `where operation_Id ==` to follow one trace, OR
- Query joins `requests` to `dependencies` / `exceptions` on `operation_Id`
- Both sides of the join are time-filtered (joining unfiltered tables is slow)
- Output projects only the columns useful for triage (timestamp, name, success, message)
- For aggregate views, `sum(itemCount)` is used (sampling-aware)

## Anti-patterns

- Joining tables without filtering both sides by time first
- `union *` without limiting to specific tables (slow)
- Using `inner` join when you want to see un-joined rows (use `leftouter`)
- Forgetting that `dependencies` includes BOTH client and server side calls — filter by `type` if needed
- No time filter on the `target_operation_id` query — single query scans the full retention window

## See also

- `concepts/kql-fundamentals.md` — joins, `union`
- `concepts/correlation-and-tracing.md` — what `operation_Id` is and how it propagates
- `concepts/application-insights-schema.md` — schema reference for `dependencies`, `exceptions`
- `patterns/kql-error-rate-by-operation.md` — find which operations to drill into
