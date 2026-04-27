# Log-based alert: query + threshold + action group

> **Last validated**: 2026-04-26
> **Confidence**: 0.90
> **Source**: https://learn.microsoft.com/en-us/azure/azure-monitor/alerts/alerts-create-log-alert-rule

## When to use this pattern

You want Azure Monitor to fire an alert when a KQL query crosses a threshold (error rate > 5%, p95 > 2s, exception count > 10). Pairs with on-call paging via action groups.

## The shape of a log-based alert

1. **Query** — KQL that returns numeric value(s) per time bucket
2. **Frequency** — how often the alert evaluates (every 5 min)
3. **Time window** — how much history each evaluation looks at (last 15 min)
4. **Threshold** — `> 5`, `< 100`, or "result rows > 0"
5. **Severity** — Sev 0 (critical) → Sev 4 (informational)
6. **Action group** — who gets paged / emailed / SMS-ed

## Query template — scalar threshold

The query must return a single numeric value (or one per time series for multi-resource alerts):

```kusto
requests
| where timestamp > ago(15m)
| where cloud_RoleName == "starbase-prod"
| summarize
    total = sum(itemCount),
    failed = sumif(itemCount, success == false)
| extend error_rate = round(100.0 * failed / total, 2)
| project error_rate
```

Alert config:
- Threshold: `error_rate > 5`
- Frequency: `5 min`
- Time window: `15 min` (matches `ago(15m)` in query)
- Severity: Sev 1 (high)

## Query template — row count threshold

For "fire if any row appears" (an exception type that should never happen, a specific log message):

```kusto
exceptions
| where timestamp > ago(15m)
| where cloud_RoleName == "starbase-prod"
| where type == "System.OutOfMemoryException"
| summarize count_ = sum(itemCount)
| where count_ > 0
```

Alert config:
- Threshold: "Number of results > 0"
- Frequency: `5 min`
- Time window: `15 min`
- Severity: Sev 0 (critical)

## Query template — multi-series alert (per operation)

```kusto
requests
| where timestamp > ago(15m)
| where cloud_RoleName == "starbase-prod"
| summarize
    p95 = percentile(duration, 95),
    total = sum(itemCount)
    by name
| where total > 50  // ignore noise
```

Alert config:
- Use **dynamic thresholds** if you want adaptive baselining
- Or static: `p95 > 2000` per operation
- Frequency: `5 min` / Time window: `15 min`
- Severity: Sev 2 (medium)

The alert fires once per operation that crosses the threshold. Action groups receive separate notifications per dimension combination.

## Query checklist

Before saving:

1. **Time filter matches alert window**: `where timestamp > ago(15m)` matches Time window = 15 min
2. **`sum(itemCount)` not `count()`**: sampling-aware
3. **Volume threshold**: `where total > 50` excludes spurious "100% error rate on one request"
4. **Service filter**: `where cloud_RoleName == "..."` to scope to the env you care about
5. **Returns numeric or row-counted**: Workbook-style time-series queries (with `bin(timestamp, ...)`) won't work for alerts — collapse to a single value

## Action groups

An action group defines what happens when an alert fires:
- Email a distribution list
- Page via Azure Mobile App / SMS / phone call
- Webhook to PagerDuty / Opsgenie / your own service
- Run an Azure Function / Logic App / Runbook

One action group can be reused across many alerts. Common pattern:
- `oncall-critical` (Sev 0–1) → page on-call
- `oncall-business-hours` (Sev 2) → email + Slack
- `info` (Sev 3–4) → Slack only

## Suppression and grouping

To prevent alert storm:
- Set `Auto-resolve alerts` so the alert closes when the condition clears.
- Use `Mute action for X minutes after firing` (e.g., 60 min) so a flapping condition doesn't page 12 times.
- For multi-series alerts, batch notifications with `Aggregate alerts` if your action group supports it.

## Severity guide

| Severity | Meaning | Example |
|---|---|---|
| Sev 0 | Critical, page now | OOM exception, 100% error rate, complete outage |
| Sev 1 | High, page during hours / next business day | Error rate > 10%, p95 > 5s |
| Sev 2 | Medium, ticket / email | Error rate 5–10%, p95 > 2s |
| Sev 3 | Low, info | Slow trend, capacity warning |
| Sev 4 | Information | Synthetic check passed, deployment completed |

Don't page Sev 3 / Sev 4. They're for tickets and dashboards.

## Bicep / ARM example (excerpt)

```bicep
resource alertRule 'Microsoft.Insights/scheduledQueryRules@2023-03-15-preview' = {
  name: 'starbase-error-rate-high'
  location: 'eastus'
  properties: {
    severity: 1
    enabled: true
    evaluationFrequency: 'PT5M'
    windowSize: 'PT15M'
    scopes: [appInsightsResourceId]
    criteria: {
      allOf: [
        {
          query: '''
            requests
            | where timestamp > ago(15m)
            | where cloud_RoleName == "starbase-prod"
            | summarize total = sum(itemCount), failed = sumif(itemCount, success == false)
            | extend error_rate = 100.0 * failed / total
            | project error_rate
          '''
          timeAggregation: 'Average'
          metricMeasureColumn: 'error_rate'
          operator: 'GreaterThan'
          threshold: 5
          failingPeriods: { numberOfEvaluationPeriods: 2, minFailingPeriodsToAlert: 2 }
        }
      ]
    }
    actions: { actionGroups: [oncallCriticalActionGroupId] }
    autoMitigate: true
  }
}
```

`failingPeriods` requires N consecutive evaluations to be failing — reduces flapping. 2-of-2 means error rate must be > 5% for 10 minutes (2 × 5min freq) before paging.

## Done when

- Query is bounded by `ago()` matching the alert's time window
- `sum(itemCount)` and volume threshold to avoid noise alerts
- Severity is appropriate (Sev 0 only for "wake someone up" cases)
- Action group exists and includes a contact path that's monitored
- Auto-resolve is enabled
- `failingPeriods` requires at least 2 consecutive evaluations
- Tested by manually triggering the condition (or by lowering threshold temporarily)

## Anti-patterns

- Time window in the alert UI doesn't match `ago(...)` in the query
- Sev 0 / Sev 1 with no action group attached (silent failure)
- No volume threshold → flaps on low-traffic operations
- Frequency = 1 min on expensive queries (rate-limit + cost)
- Alert query uses `bin(timestamp, ...)` for visualization (won't return scalar)
- No auto-resolve → manual close required after every incident
- Same action group paging on Sev 4 (alert fatigue)

## See also

- `patterns/kql-error-rate-by-operation.md` — the underlying error-rate query
- `patterns/kql-latency-percentiles.md` — the underlying latency query
- `concepts/cost-and-cardinality.md` — query cost matters when running every 5 min
