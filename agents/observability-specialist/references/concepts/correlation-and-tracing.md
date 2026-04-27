# Correlation & distributed tracing

> **Last validated**: 2026-04-26
> **Confidence**: 0.93
> **Source**: https://www.w3.org/TR/trace-context/, https://learn.microsoft.com/azure/azure-monitor/app/correlation

## The problem

A user request enters the front-end, calls 3 microservices, each calls the database, one calls Claude. When something fails, you need to know:

1. Which user request was this?
2. Which downstream call failed?
3. What logs were emitted during this request?

That's correlation. Without it, you have isolated events with no thread connecting them.

## W3C Trace Context — the standard

OpenTelemetry uses W3C Trace Context. Each request has:

- **Trace ID** — 32 hex chars. One per end-to-end user activity. Same across every service the request touches.
- **Span ID** — 16 hex chars. One per operation within a service (request, DB call, LLM call).
- **Parent Span ID** — span ID of whatever triggered this span.
- **Trace Flags** — sampling decision propagation.

These travel between services via the `traceparent` HTTP header:

```
traceparent: 00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01
            ^^ ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^ ^^^^^^^^^^^^^^^^ ^^
            |  trace-id                          parent-id        flags
            version
```

OTel HTTP instrumentation reads/writes this header automatically — IF you instrument both sides.

## In Application Insights

Application Insights translates W3C Trace Context to its own column names:

| W3C / OTel | App Insights column |
|---|---|
| Trace ID | `operation_Id` |
| Parent Span ID | `operation_ParentId` |
| Top-level operation name | `operation_Name` |

Every row in every AI table has these. That's what makes correlation queries possible:

```kusto
let target_operation = "<some operation_Id>";
union requests, dependencies, exceptions, traces
| where timestamp > ago(1h)
| where operation_Id == target_operation
| order by timestamp asc
| project timestamp, itemType, name, message, severityLevel, duration, success
```

This is the canonical "follow one request through everything" query.

## Cross-service propagation

The propagation only works if every service is instrumented. One un-instrumented service in the middle BREAKS the chain — you get two separate traces with no link.

For Azure Monitor distro (Python):

```python
from azure.monitor.opentelemetry import configure_azure_monitor

configure_azure_monitor(
    logger_name="my_app",
)
# All HTTP libraries (requests, httpx, urllib) auto-instrument and
# propagate traceparent. Same for psycopg, asyncpg, redis, etc.
```

The distro auto-instruments common libraries. For an SDK or framework not covered, instrument it manually using the OTel API.

## Manual span creation

```python
from opentelemetry import trace

tracer = trace.get_tracer(__name__)

async def process_order(order_id: str) -> Order:
    with tracer.start_as_current_span("process_order") as span:
        span.set_attribute("order.id", order_id)
        order = await fetch_order(order_id)
        span.set_attribute("order.status", order.status)
        await charge_card(order)
        await send_email(order)
        return order
```

Inside `process_order`, any other span (HTTP call, DB query, child function) becomes a child of `process_order` automatically.

## Async context propagation

OTel context follows asyncio task boundaries IF you don't break them:

```python
# WORKS — context inherited
async def parent():
    async with tracer.start_as_current_span("parent"):
        await child()  # span inside child is a child of "parent"

# BREAKS — context lost
async def parent():
    async with tracer.start_as_current_span("parent"):
        asyncio.create_task(child())  # different task, new context
```

For `create_task`, capture the context explicitly:

```python
import contextvars

async def parent():
    async with tracer.start_as_current_span("parent"):
        ctx = contextvars.copy_context()
        asyncio.create_task(ctx.run(asyncio.ensure_future, child()))
```

Or simpler: use `asyncio.gather()` instead of fire-and-forget `create_task` — gather preserves context.

## Custom correlation IDs

Sometimes you want a logical ID separate from the trace ID — a session ID, request ID from your own framework, conversation ID for a chatbot.

Add it as a span attribute AND propagate it through the request body / your own headers:

```python
async def handle_chat_message(session_id: str, message: str):
    with tracer.start_as_current_span("chat") as span:
        span.set_attribute("chat.session_id", session_id)
        # session_id now appears in customDimensions on this and all children
```

In KQL:

```kusto
union requests, dependencies, exceptions, traces
| where timestamp > ago(1h)
| where tostring(customDimensions["chat.session_id"]) == "abc-123"
| order by timestamp asc
```

## Anti-patterns

- One service un-instrumented in the middle of a chain (correlation breaks)
- Re-using `operation_Id` across actually-different requests (logs collide)
- Logging without including the trace context (logs orphaned from spans)
- `create_task` without context propagation (orphan child spans)
- Custom correlation ID that doesn't propagate to downstream services
- Manual span ID generation (use the SDK; non-W3C-compatible IDs break correlation)

## See also

- `concepts/opentelemetry-semantic-conv.md` — span naming and attributes
- `concepts/application-insights-schema.md` — the columns where correlation lands
- `patterns/kql-dependency-failure.md` — joining tables on operation_Id
- `anti-patterns.md` (items 11, 12)
