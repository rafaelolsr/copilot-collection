# Sampling strategies

> **Last validated**: 2026-04-26
> **Confidence**: 0.91
> **Source**: https://learn.microsoft.com/en-us/azure/azure-monitor/app/sampling-classic-api

## Why sample

A web service handling 100 req/s emits ~8.6M requests per day. At ~1KB per telemetry item that's ~10GB. Application Insights ingestion charges by GB. Without sampling, telemetry costs more than the service.

Sampling drops a controlled fraction of telemetry while preserving analytical accuracy.

## The 3 sampling modes

| Mode | When the decision is made | Cost reduction | Loss |
|---|---|---|---|
| **Adaptive (head-based)** | At ingest, before any data is sent | Best (saves bandwidth + ingest cost) | Drops rows uniformly across operations |
| **Fixed-rate (head-based)** | At ingest, fixed % | Best | Same as adaptive but no auto-tuning |
| **Ingestion (server-side)** | After ingest, by AI service | Lower (you pay for ingest) | Less precision; configured in portal |

For Azure-Monitor-OpenTelemetry-Distro applications, **head-based sampling** at the OTel SDK level is preferred. It reduces both bandwidth and ingest cost.

## Head-based sampling (OTel)

OTel's `TraceIdRatioBased` sampler picks rows based on a hash of the trace ID:

```python
from opentelemetry.sdk.trace.sampling import TraceIdRatioBased
from azure.monitor.opentelemetry import configure_azure_monitor

configure_azure_monitor(
    sampling_ratio=0.1,  # keep 10% of traces
)
```

**Critical property:** the decision is made per-trace, not per-span. All spans in one trace either survive together or are dropped together. Without this, you'd get partial traces (request kept, child dependencies dropped) that are useless for diagnosis.

## itemCount and statistical correctness

When sampling is on, each stored row carries `itemCount` — how many "real" events that row represents. Most aggregations need to multiply by it:

```kusto
// WRONG with sampling — undercounts
requests
| where timestamp > ago(1h)
| count

// CORRECT with sampling
requests
| where timestamp > ago(1h)
| summarize total = sum(itemCount)
```

The Application Insights SDK percentile calculation already accounts for sampling — `percentile(duration, 95)` works without manual adjustment.

## Adaptive sampling

The Azure Monitor distro auto-tunes the sample rate to hit a target events-per-second:

```python
configure_azure_monitor(
    sampling_ratio=1.0,  # base rate
    # adaptive sampling settings — see distro docs
)
```

Adaptive raises the rate during quiet periods (capture more) and lowers it during spikes (cap cost). Best for highly variable traffic.

## Fixed-rate sampling

Simple and predictable:

```python
configure_azure_monitor(sampling_ratio=0.05)  # 5% always
```

Use for steady-state services with known volume.

## What NOT to sample

Some telemetry should NEVER be sampled:

| Type | Why |
|---|---|
| Exceptions | Always rare; sampling them away erases your debugging info |
| Errors (success=false) | Same logic — you want every failure |
| Custom events for business analytics | Sampling distorts counts |
| Availability results | Already low-volume; sampling makes results meaningless |

OTel offers `ParentBased` samplers that combine: "always sample errors AND apply ratio to everything else."

## Tail-based sampling

Decision made AFTER seeing the full trace. Allows rules like "always keep traces with errors". Requires a backend that can buffer the full trace before deciding (Azure Monitor doesn't do this natively — needs an OTel Collector in between).

For 95% of cases you don't need it. Use head-based + always-sample-errors.

## Sampling and percentiles

A common worry: "if I sample 10%, are my p95s wrong?"

No, if the SDK does it right. The percentile calculation uses `itemCount` to weight each stored row. The result is statistically equivalent to the unsampled population — assuming the sample is uniform.

What WILL break:
- p99.9 on a low-traffic operation (the rare slow event might not be sampled in)
- Exact counts (use `sum(itemCount)`)
- Min/max of a column (random — depends on which rows survived)

## Cost vs. fidelity tradeoff

| Sample rate | Cost | When to use |
|---|---|---|
| 100% | High | Dev / staging / low-traffic services |
| 25% | Medium | Default for most production services |
| 10% | Low | High-traffic services (>50 req/s) |
| 5% | Very low | Massive services + good error-always-sampled rule |
| 1% | Telemetry-as-billboard | When you only need rough trends |

Below 1% you lose statistical power for percentiles even with `itemCount` weighting.

## Anti-patterns

- 100% sampling in production on a high-traffic service (cost runaway)
- Sampling that drops errors uniformly with successes
- Per-span sampling instead of per-trace (broken trace trees)
- Aggregating without `itemCount` after enabling sampling
- Sampling adaptive AND fixed-rate at the same time (confusing)
- Forgetting to set the sample rate in code AND in the portal — config drift

## See also

- `concepts/cost-and-cardinality.md` — sampling is one half of cost control; cardinality is the other
- `patterns/otel-python-instrumentation.md` — sampling configuration in distro setup
- `anti-patterns.md` (items 2, 4)
