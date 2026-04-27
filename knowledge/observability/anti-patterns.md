# Observability — Anti-Patterns

> **Last validated**: 2026-04-26
> **Confidence**: 0.92
> Wrong / Correct pairs for every anti-pattern the agent flags on sight.

---

## 1. Custom metric with unbounded label cardinality

Wrong:
```python
meter.create_counter("requests").add(1, {"user_id": user_id})
```

Why: every distinct `user_id` becomes a separate metric series. Storage explodes; backend silently drops new ones beyond limits.

Correct: put high-cardinality data in spans/logs, not metric labels.
```python
meter.create_counter("requests").add(1, {"tenant_tier": tier})  # bounded
span.set_attribute("user.id", user_id)
logger.info("request", extra={"user_id": user_id})
```

Related: `concepts/cost-and-cardinality.md`

---

## 2. 100% sampling in production

Wrong:
```python
configure_azure_monitor()  # default = no sampling
```

Why: cost runaway on any service > 10 req/s.

Correct:
```python
configure_azure_monitor(sampling_ratio=0.25)  # 25%
```

Related: `concepts/sampling-strategies.md`

---

## 3. KQL query without time filter

Wrong:
```kusto
requests
| summarize count() by name
```

Why: scans all retained data. Slow, expensive.

Correct:
```kusto
requests
| where timestamp > ago(1h)
| summarize count() by name
```

---

## 4. Aggregating without `itemCount` when sampling is on

Wrong:
```kusto
requests
| where timestamp > ago(1h)
| summarize total = count()
```

Correct:
```kusto
requests
| where timestamp > ago(1h)
| summarize total = sum(itemCount)
```

Related: `concepts/sampling-strategies.md`

---

## 5. `resultCode == 500` (int) instead of `resultCode == "500"` (string)

Wrong:
```kusto
requests | where resultCode == 500    // never matches
```

Why: `resultCode` is a string column.

Correct:
```kusto
requests | where resultCode == "500"
// or:
requests | where tolong(resultCode) == 500
```

Related: `concepts/application-insights-schema.md`

---

## 6. `count()` on rare error types — no volume threshold

Wrong:
```kusto
requests
| summarize total = count(), failures = countif(success == false)
| extend error_rate = 100.0 * failures / total
| order by error_rate desc
```

Why: an operation called 1× that failed 1× shows 100% error rate, drowning real problems.

Correct:
```kusto
requests
| summarize total = sum(itemCount), failures = sumif(itemCount, success == false)
| extend error_rate = 100.0 * failures / total
| where total > 100
| order by error_rate desc
```

---

## 7. `avg(duration)` instead of percentiles

Wrong:
```kusto
requests | summarize avg_duration = avg(duration) by name
```

Why: averages hide tail latency. p99 is what users feel.

Correct:
```kusto
requests
| summarize
    p50 = percentile(duration, 50),
    p95 = percentile(duration, 95),
    p99 = percentile(duration, 99)
    by name
```

Related: `patterns/kql-latency-percentiles.md`

---

## 8. `summarize ... by user_id` (unbounded cardinality)

Wrong:
```kusto
requests
| summarize count() by tostring(customDimensions["user_id"])
```

Why: with millions of users, query times out or returns truncated.

Correct: filter to a bounded scope, then aggregate.
```kusto
requests
| where tostring(customDimensions["tenant_id"]) == "acme-corp"
| summarize count() by name
```

---

## 9. Joining unfiltered tables

Wrong:
```kusto
requests | join kind=inner dependencies on operation_Id
```

Why: cross-product blowup before any filter applies.

Correct:
```kusto
requests
| where timestamp > ago(1h) and success == false
| join kind=inner (
    dependencies | where timestamp > ago(1h)
) on operation_Id
```

---

## 10. Missing time filter on long-running join

Wrong: as above — joining without filtering both sides.

Correct: always filter both sides by time before the join.

---

## 11. `service.name` not set

Wrong:
```bash
# no OTEL_RESOURCE_ATTRIBUTES
```

Why: services collapse into one node on the App Map; per-service filtering breaks.

Correct:
```bash
OTEL_RESOURCE_ATTRIBUTES="service.name=starbase-chainlit-prod,deployment.environment=production"
```

Related: `concepts/opentelemetry-semantic-conv.md`

---

## 12. Concrete IDs in span names

Wrong:
```python
with tracer.start_as_current_span(f"GET /users/{user_id}"):
    ...
```

Correct:
```python
with tracer.start_as_current_span("GET /users/{id}") as span:
    span.set_attribute("user.id", user_id)
```

Related: `concepts/opentelemetry-semantic-conv.md`

---

## 13. Concrete parameter values in `db.statement`

Wrong:
```python
span.set_attribute("db.statement", f"SELECT * FROM users WHERE id = {user_id}")
```

Why: cardinality explosion + PII leak.

Correct:
```python
span.set_attribute("db.statement", "SELECT * FROM users WHERE id = $1")
```

---

## 14. Custom attribute names that duplicate spec attributes

Wrong:
```python
span.set_attribute("http_method", "POST")
span.set_attribute("status", 200)
```

Correct (use OTel semantic conventions):
```python
span.set_attribute("http.request.method", "POST")
span.set_attribute("http.response.status_code", 200)
```

Related: `concepts/opentelemetry-semantic-conv.md`

---

## 15. Setting `Status.OK` on every span

Wrong:
```python
with tracer.start_as_current_span("op") as span:
    do_work()
    span.set_status(Status(StatusCode.OK))  # noise
```

Correct: leave status `UNSET` for normal operation; set `ERROR` only on actual failures.
```python
with tracer.start_as_current_span("op") as span:
    try:
        do_work()
    except Exception as exc:
        span.set_status(Status(StatusCode.ERROR, str(exc)))
        span.record_exception(exc)
        raise
```

---

## 16. `print()` instead of structured logging

Wrong:
```python
print(f"Processing {item}")
```

Why: bypasses the OTel pipeline; not correlated to traces; not exportable.

Correct:
```python
import logging
logger = logging.getLogger(__name__)
logger.info("processing", extra={"item_id": item.id})
```

---

## 17. `take 10 | where ...` (filter after limit)

Wrong:
```kusto
requests
| take 10
| where success == false  // filters AFTER taking 10 random rows
```

Correct:
```kusto
requests
| where timestamp > ago(1h) and success == false
| take 10
```

---

## 18. Alert query window doesn't match KQL `ago(...)`

Wrong: alert configured with Time window = 15 min, but query has `where timestamp > ago(5m)`.

Correct: `ago()` in the query MUST match the alert's Time window.

Related: `patterns/log-based-alert-query.md`

---

## 19. Per-request metrics labeled by request ID

Wrong:
```python
counter.add(1, {"request_id": request.id})
```

Why: every request creates a new metric series. Backend rejects beyond cardinality limit.

Correct:
```python
counter.add(1, {"endpoint": request.endpoint})
span.set_attribute("request.id", request.id)
```

---

## 20. Hardcoded connection string in Program.cs / main.py

Wrong:
```python
configure_azure_monitor(connection_string="InstrumentationKey=abc...")
```

Correct:
```python
configure_azure_monitor()  # reads from APPLICATIONINSIGHTS_CONNECTION_STRING env var
```

---

## 21. No daily ingestion cap on production workspaces

Wrong: leaving daily cap unset → single bug can produce a $50k bill.

Correct: set a daily cap (e.g., 10 GB/day) on the Application Insights resource. Alert when it's hit. Investigate and raise only if needed.

Related: `concepts/cost-and-cardinality.md`

---

## 22. Logging full request/response bodies without redaction

Wrong:
```python
logger.info(f"received: {full_request_body}")
logger.info(f"response: {full_response_body}")
```

Why: PII leak; log volume explosion.

Correct:
```python
logger.info(
    "request_received",
    extra={
        "endpoint": request.endpoint,
        "body_size": len(full_request_body),
        "user_tier": request.user.tier,
    },
)
```

---

## See also

- `index.md` — KB navigation
