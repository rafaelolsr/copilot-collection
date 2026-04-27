# Application Insights schema

> **Last validated**: 2026-04-26
> **Confidence**: 0.93
> **Source**: https://learn.microsoft.com/en-us/azure/azure-monitor/app/data-model-complete

## The 7 tables

Application Insights stores telemetry across 7 tables. Knowing which goes where determines whether your query works at all.

| Table | What it holds | Common columns |
|---|---|---|
| `requests` | Server-handled HTTP requests / RPC calls | `name`, `url`, `duration`, `resultCode`, `success`, `operation_Id` |
| `dependencies` | Outbound calls (HTTP, DB, queue, other service) | `name`, `target`, `data`, `type`, `duration`, `resultCode`, `success`, `operation_Id` |
| `exceptions` | Caught and uncaught exceptions | `type`, `method`, `outerMessage`, `details`, `severityLevel`, `operation_Id` |
| `traces` | Application logs (any severity) | `message`, `severityLevel`, `customDimensions`, `operation_Id` |
| `customEvents` | App-emitted business events | `name`, `customDimensions`, `customMeasurements` |
| `customMetrics` | App-emitted scalar metrics | `name`, `value`, `valueCount`, `valueSum`, `valueMin`, `valueMax` |
| `pageViews` | Browser page views (client telemetry) | `name`, `url`, `duration`, `customDimensions` |
| `availabilityResults` | Synthetic availability tests | `name`, `location`, `success`, `duration` |

## Cross-table columns (critical for correlation)

These appear in EVERY table and are how you join across telemetry types:

| Column | Purpose |
|---|---|
| `timestamp` | When the telemetry was emitted (indexed) |
| `operation_Id` | End-to-end correlation across one user request / activity |
| `operation_ParentId` | The span that triggered this one (parent in the trace tree) |
| `operation_Name` | Logical operation (usually = top-level request name) |
| `cloud_RoleName` | Service / app name (set via OTel `service.name`) |
| `cloud_RoleInstance` | Specific instance (host / pod) |
| `appName` | Application Insights resource name |
| `customDimensions` | Dynamic dict of string → string (your custom tags) |

Use `operation_Id` to follow a single user request through:
1. The web request (`requests`)
2. The downstream service / DB calls it made (`dependencies`)
3. Any exceptions raised during the request (`exceptions`)
4. Logs from inside the request (`traces`)

## Custom dimensions

`customDimensions` is a `dynamic` (JSON-shaped) column. Access fields with bracket notation:

```kusto
requests
| where timestamp > ago(1h)
| extend tenant_id = tostring(customDimensions["tenant_id"])
| where tenant_id == "acme-corp"
| summarize count() by name
```

`tostring()` converts the dynamic value to a string. Other functions:
- `toint()` / `tolong()` for numbers
- `todatetime()` for timestamps
- `parse_json()` if the value is itself JSON-encoded

## resultCode vs success

`resultCode` is a string (HTTP status, exception type name, custom code). `success` is a bool computed by the SDK based on `resultCode` (200-399 → true; 400-599 → false; usually).

For strict failure analysis prefer `success == false`:

```kusto
requests
| where timestamp > ago(1h)
| where success == false
```

For specific HTTP status codes filter on `resultCode`:

```kusto
requests
| where resultCode startswith "5"
```

Note: `resultCode` is a string, so `resultCode == 500` (int) won't match. Use `resultCode == "500"` or `tolong(resultCode) == 500`.

## Severity levels in traces

```
0 = Verbose
1 = Information
2 = Warning
3 = Error
4 = Critical
```

```kusto
traces
| where timestamp > ago(1h)
| where severityLevel >= 3  // Error and Critical
| summarize count() by message
| order by count_ desc
```

## Sampled telemetry

If sampling is enabled (and it should be in production), some rows are dropped. The `itemCount` column tells you how many "real" events each stored row represents:

```kusto
requests
| where timestamp > ago(1h)
| summarize total_requests = sum(itemCount), distinct_stored_rows = count()
```

Without `itemCount`, you under-count. For percentiles, the SDK's percentile calculation accounts for this; just call `percentile(duration, 95)` normally.

## Performance tips per table

- **requests / dependencies**: usually high-volume. Sample aggressively. Always filter by `timestamp` and `operation_Name`.
- **exceptions**: lower volume; safer to query without sampling adjustments.
- **traces**: HIGHEST volume. Severity filter is usually the right first step.
- **customEvents / customMetrics**: depends entirely on what you emit. If you emit per-user events, cardinality can explode.

## See also

- `concepts/kql-fundamentals.md` — query syntax
- `concepts/correlation-and-tracing.md` — operation_Id deep dive
- `patterns/kql-latency-percentiles.md` — percentile queries on `requests`
- `patterns/kql-dependency-failure.md` — joining `requests` and `dependencies`
- `anti-patterns.md` (items 5, 10)
