# OpenTelemetry instrumentation for Python services

> **Last validated**: 2026-04-26
> **Confidence**: 0.93
> **Source**: https://learn.microsoft.com/en-us/azure/azure-monitor/app/opentelemetry-enable

## When to use this pattern

Adding OTel-based telemetry to a Python service so it emits traces, metrics, and logs to Azure Monitor / Application Insights. The Azure Monitor distro handles 90% of the setup; this pattern documents the 10% you tune.

## Install

```bash
uv pip install azure-monitor-opentelemetry
# or
pip install azure-monitor-opentelemetry
```

The distro pulls in `opentelemetry-api`, `opentelemetry-sdk`, and instrumentation packages for common libraries (requests, httpx, FastAPI, Flask, Django, psycopg, redis, urllib3, etc.).

## Minimal setup

```python
"""telemetry.py — call init_telemetry() exactly once at process startup."""
from __future__ import annotations

import logging
import os
from azure.monitor.opentelemetry import configure_azure_monitor

_INITIALIZED = False


def init_telemetry(*, logger_name: str = "my_service") -> None:
    """Initialize OTel + Azure Monitor. Idempotent."""
    global _INITIALIZED
    if _INITIALIZED:
        return

    connection_string = os.environ.get("APPLICATIONINSIGHTS_CONNECTION_STRING")
    if not connection_string:
        logging.warning("telemetry_disabled — APPLICATIONINSIGHTS_CONNECTION_STRING not set")
        _INITIALIZED = True
        return

    configure_azure_monitor(
        connection_string=connection_string,
        logger_name=logger_name,  # capture logs from this logger and children
        # resource attributes — set service.name etc. via OTEL_RESOURCE_ATTRIBUTES env var
    )
    _INITIALIZED = True
```

## Required environment variables

```bash
# Connection string from Application Insights resource Overview blade
APPLICATIONINSIGHTS_CONNECTION_STRING="InstrumentationKey=...;IngestionEndpoint=https://..."

# Critical for the App Map and per-service filtering
OTEL_RESOURCE_ATTRIBUTES="service.name=starbase-chainlit-prod,service.version=2026.4.1.0,deployment.environment=production"

# Optional: sampling
OTEL_TRACES_SAMPLER=traceidratio
OTEL_TRACES_SAMPLER_ARG=0.25  # 25% sampling
```

`OTEL_RESOURCE_ATTRIBUTES` is the simplest way to set resource attributes — works for any OTel-compatible app. The distro also accepts a `resource` argument programmatically.

## Wire into FastAPI

```python
"""main.py"""
from fastapi import FastAPI
from .telemetry import init_telemetry

# Init BEFORE creating FastAPI — auto-instrumentation hooks during import
init_telemetry(logger_name="my_service")

app = FastAPI()

# FastAPI is auto-instrumented if opentelemetry-instrumentation-fastapi is installed
# (included in the Azure Monitor distro).

@app.get("/health")
def health():
    return {"status": "ok"}
```

For libraries the distro doesn't auto-instrument (or to opt-in selectively):

```python
from opentelemetry.instrumentation.requests import RequestsInstrumentor
RequestsInstrumentor().instrument()
```

## Manual span creation

```python
from opentelemetry import trace

tracer = trace.get_tracer(__name__)

async def process_invoice(invoice_id: str) -> Invoice:
    with tracer.start_as_current_span("process_invoice") as span:
        span.set_attribute("invoice.id", invoice_id)
        invoice = await fetch_invoice(invoice_id)
        span.set_attribute("invoice.total", invoice.total)
        await charge(invoice)
        return invoice
```

Use `tracer.start_as_current_span()` (context-manager) for synchronous and async code. Auto-instrumented libraries inside the `with` block become children of this span.

## Manual error recording

```python
from opentelemetry.trace import Status, StatusCode

async def call_external_api():
    with tracer.start_as_current_span("call_external") as span:
        try:
            response = await client.get(...)
            response.raise_for_status()
            return response
        except httpx.HTTPError as exc:
            span.set_status(Status(StatusCode.ERROR, str(exc)))
            span.record_exception(exc)
            raise
```

`record_exception` adds an `exception` event to the span; in App Insights it becomes an `exceptions` table row correlated by `operation_Id`.

## Custom metrics

```python
from opentelemetry import metrics

meter = metrics.get_meter(__name__)

requests_counter = meter.create_counter(
    name="agent.requests",
    description="Number of requests handled by this agent",
    unit="1",
)

duration_histogram = meter.create_histogram(
    name="agent.request_duration",
    description="Request duration",
    unit="ms",
)

# In handler:
async def handle(request):
    requests_counter.add(1, {"agent_name": "advisor", "outcome": "success"})
    duration_histogram.record(elapsed_ms, {"agent_name": "advisor"})
```

LIMIT yourself to low-cardinality attributes on metrics. `agent_name` (10 values) is fine; `user_id` is not.

## Logging integration

When you initialize the distro with `logger_name="my_service"`, every `logging.getLogger("my_service")` and its children gets its records exported to App Insights as `traces`:

```python
import logging
logger = logging.getLogger("my_service.workflow")

logger.info("workflow_started", extra={"workflow": "advisor", "user_id_bucket": "internal"})
logger.warning("retry_attempt", extra={"attempt": 2, "operation": "fetch_metadata"})
```

`extra=` becomes `customDimensions` in the `traces` table.

## Sampling configuration

Best done via env var (`OTEL_TRACES_SAMPLER=traceidratio`, `OTEL_TRACES_SAMPLER_ARG=0.25`).

To always-sample errors:

```python
from opentelemetry.sdk.trace.sampling import ParentBased, TraceIdRatioBased
# Custom samplers exist for "always sample if error attribute set" — see OTel docs
```

Most teams find env-var-based sampling adequate.

## Done when

- `service.name` is set (verify by checking the App Map shows your service as a separate node)
- Requests appear in the `requests` table with non-empty `operation_Id`
- Dependencies (HTTP calls, DB queries) appear in `dependencies`
- Logs emitted via the configured `logger_name` appear in `traces`
- Exceptions appear in `exceptions` correlated by `operation_Id`
- Sample rate is set (don't run 100% in production beyond a small service)
- Daily cap is set on the App Insights resource (cost safety)

## Anti-patterns

- `service.name` not set (services collapse on App Map)
- Initialization in module body of multiple files (re-initializes, duplicates spans)
- Manual span creation that wraps already-instrumented libraries (double spans)
- Logging via `print()` instead of `logging` (escapes the OTel pipeline)
- Setting status `OK` on every span explicitly (just leave it `UNSET`)
- 100% sampling in production
- High-cardinality attributes on metrics

## See also

- `concepts/opentelemetry-semantic-conv.md` — attribute naming
- `concepts/sampling-strategies.md` — sampling configuration
- `concepts/correlation-and-tracing.md` — context propagation
- `patterns/otel-dotnet-instrumentation.md` — same pattern in .NET
- `anti-patterns.md` (items 11, 12, 13, 14, 15)
