# Cost and cardinality

> **Last validated**: 2026-04-26
> **Confidence**: 0.92

## The two cost drivers

1. **Volume** — how many telemetry items per second. Solved by sampling.
2. **Cardinality** — how many distinct values per attribute. Solved by discipline.

Sampling alone won't save you from a `customDimensions["user_id"]` field with 10M distinct values. The metric storage explodes regardless of sample rate.

## What cardinality means

Cardinality is the number of unique combinations of dimension values. For each unique combination, the storage backend allocates a separate metric stream.

| Dimension | Cardinality |
|---|---|
| `service.name` | ~10 (services in your fleet) |
| `http.route` | ~100 (templated routes) |
| `http.status_code` | ~10 (status codes you actually return) |
| `customer_tier` (free/pro/enterprise) | 3 |
| `tenant_id` | 1,000 — risky |
| `user_id` | millions — DON'T |
| `order_id` | unbounded — DON'T |
| `request_id` | every request — DON'T |

The product matters. `service.name × http.route × status_code` = ~10,000 streams. Add `tenant_id` (1,000) and you have 10M streams. Storage cost scales linearly with stream count.

## Where cardinality bites

| Place | Effect |
|---|---|
| Span attributes used in dashboards / alerts | Each unique value = separate metric series |
| `customDimensions` in KQL `summarize` | Query times out or returns truncated results |
| OTel meter labels / attributes | Backend rejects beyond a limit (Application Insights drops new ones) |
| Span names with concrete IDs | Each variant is a separate operation |

## Symptoms of a cardinality problem

- Dashboards take 30+ seconds to load
- KQL queries time out on `summarize ... by user_id`
- Application Insights bill grew 5× without traffic increase
- Alerts fire on metric series you don't recognize
- Some metrics "missing" — backend dropped high-cardinality series

## How to fix it

### 1. Use templates, not concrete values, in span names

```python
# WRONG
with tracer.start_as_current_span(f"GET /users/{user_id}"):
    ...

# CORRECT
with tracer.start_as_current_span("GET /users/{id}") as span:
    span.set_attribute("user.id", user_id)  # attribute, not name
```

### 2. Bucket high-cardinality values

```python
# Instead of recording exact request size:
span.set_attribute("http.request.body.size", 1_283_192)

# Record a bucket:
span.set_attribute("http.request.body.size_bucket", _bucket(1_283_192))
# returns "1KB-10KB" / "10KB-100KB" / "100KB-1MB" / "1MB+"
```

### 3. Move high-cardinality data to logs / traces, NOT metrics

```python
# WRONG — metric with unbounded labels
meter.create_counter("requests").add(1, {"user_id": user_id})

# CORRECT — span attribute + log
span.set_attribute("user.id", user_id)
logger.info("request_processed", extra={"user_id": user_id})
```

Spans and logs are searchable, not aggregated. They tolerate high cardinality because they're stored as rows, not pre-aggregated counters.

### 4. KQL `summarize`: never group by unbounded columns

```kusto
// WRONG — millions of users → query times out
requests
| summarize count() by tostring(customDimensions["user_id"])

// CORRECT — bucket or filter first
requests
| where tostring(customDimensions["tenant_id"]) == "acme-corp"
| summarize count() by name
```

If you need per-user analysis, filter to a window where cardinality is bounded (1 hour, 1 customer, 1 specific user_id).

## Daily cost cap

Set an ingestion cap on the workspace as a safety net:

```
Application Insights resource → Usage and estimated costs → Daily cap
```

Set to e.g. 10 GB/day. When hit, AI stops ingesting until midnight UTC. Better than an unbounded bill — you'll notice.

The cap doesn't prevent the underlying cause; it just limits the blast radius. Fix the cardinality problem after.

## Custom metric ingestion limits

Application Insights enforces a custom-metric cardinality limit per dimension (~100 unique values). Beyond that, metrics with new values are silently dropped. You won't see an error — you'll just notice metrics are missing.

If you need higher cardinality, switch from custom metrics to logs+queries:

```python
# Instead of:
meter.create_histogram("checkout_duration").record(123, {"product_id": pid})

# Do:
logger.info(
    "checkout_completed",
    extra={"duration_ms": 123, "product_id": pid},
)
# Then aggregate via KQL when needed
```

## Sampling vs. cardinality vs. log volume

| Lever | Effect | Cost | Loss |
|---|---|---|---|
| Sampling | Reduces row count uniformly | Big | Some traces dropped |
| Cardinality control | Reduces metric stream count | Big | None — same data, fewer dimensions |
| Log severity filter | Reduces log row count | Medium | Verbose / debug logs lost |
| Daily cap | Hard ingestion limit | Big | Telemetry blackout when hit |

Use them together: `sampling 25%` + cardinality discipline + `severity ≥ INFO` + daily cap.

## Anti-patterns

- `customDimensions["user_id"]` set on every request and used in `summarize`
- Concrete IDs in span names (`GET /users/12345`)
- Per-request metrics labeled by request ID
- Custom metrics with `request.path` as a label (use `http.route` template instead)
- No daily cap on production workspaces
- "Just add it as a metric, we'll see if it's a problem" — almost always a problem
- Unbounded label values from external sources (user-agent strings, query strings)

## See also

- `concepts/sampling-strategies.md` — the other half of cost control
- `concepts/opentelemetry-semantic-conv.md` — naming conventions reduce cardinality risk
- `anti-patterns.md` (items 1, 2, 8, 19)
