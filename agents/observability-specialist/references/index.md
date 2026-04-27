# Observability Knowledge Base — Index

> **Last validated**: 2026-04-26
> **Confidence**: 0.92
> **Scope**: Azure Monitor 2026, Application Insights (workspace-based), KQL, OpenTelemetry 1.x for Python/.NET, semantic conventions, sampling, dashboards.

## KB Structure

### Concepts

| File | Topic | Status |
|---|---|---|
| `concepts/kql-fundamentals.md` | KQL syntax, time filters, summarize, joins | Validated |
| `concepts/application-insights-schema.md` | requests, dependencies, exceptions, traces, customMetrics tables | Validated |
| `concepts/sampling-strategies.md` | Fixed-rate, adaptive, head-based vs tail-based | Validated |
| `concepts/opentelemetry-semantic-conv.md` | Span attributes, resource attributes, naming | Validated |
| `concepts/correlation-and-tracing.md` | operation_Id, traceparent, context propagation across services | Validated |
| `concepts/cost-and-cardinality.md` | Unbounded labels, GROUP BY traps, data caps, ingestion control | Validated |

### Patterns

| File | Topic |
|---|---|
| `patterns/kql-latency-percentiles.md` | p50/p95/p99 over time with summarize + bin |
| `patterns/kql-error-rate-by-operation.md` | Failure rates with countif and percentages |
| `patterns/kql-dependency-failure.md` | Root-cause analysis via operation_Id correlation |
| `patterns/otel-python-instrumentation.md` | azure-monitor-opentelemetry distro setup for FastAPI/Flask |
| `patterns/otel-dotnet-instrumentation.md` | OpenTelemetry SDK + Azure Monitor exporter for ASP.NET Core |
| `patterns/workbook-dashboard-skeleton.md` | RED dashboard JSON template for Application Insights |
| `patterns/log-based-alert-query.md` | Alert rule with time window + threshold + action group |

### Reference

| File | Topic |
|---|---|
| `anti-patterns.md` | 22 observability anti-patterns to flag on sight |

## Reading Protocol

1. Start here (`index.md`) to identify relevant files for the task.
2. For task type → file map:
   - "write a KQL query" → `concepts/kql-fundamentals.md` + matching `patterns/kql-*.md`
   - "instrument a service with OTel" → `concepts/opentelemetry-semantic-conv.md` + `patterns/otel-<lang>-instrumentation.md`
   - "diagnose performance" → `concepts/correlation-and-tracing.md` + `patterns/kql-dependency-failure.md`
   - "review telemetry config" → `anti-patterns.md` + `concepts/sampling-strategies.md` + `concepts/cost-and-cardinality.md`
   - "build a dashboard" → `patterns/workbook-dashboard-skeleton.md`
   - "set up alerts" → `patterns/log-based-alert-query.md`
3. If any file has `last_validated` older than 90 days, use `web` tool to re-validate against:
   - https://learn.microsoft.com/en-us/azure/azure-monitor/
   - https://learn.microsoft.com/en-us/kusto/query/
   - https://opentelemetry.io/docs/
   - https://opentelemetry.io/docs/specs/semconv/
4. Check `anti-patterns.md` whenever reviewing user-provided telemetry config or queries.
