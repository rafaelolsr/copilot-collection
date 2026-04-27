# OpenTelemetry semantic conventions

> **Last validated**: 2026-04-26
> **Confidence**: 0.93
> **Source**: https://opentelemetry.io/docs/specs/semconv/

## Why conventions matter

OpenTelemetry's semantic conventions define standard attribute names for spans and resources. Following them means:

- Backends (Azure Monitor, Datadog, Honeycomb) recognize and visualize your data correctly
- Cross-language tracing works (Python service → .NET service → Java service all use `http.request.method`)
- Dashboards built on standard names survive instrumentation changes
- AI tools that read traces can reason about what each span means

The single biggest mistake in handcrafted instrumentation: making up your own attribute names. Use the spec.

## Resource attributes — set once per service

Resource attributes describe the running process / service. They're attached to every span automatically.

| Attribute | Required? | Example |
|---|---|---|
| `service.name` | YES | `starbase-chainlit-prod` |
| `service.version` | recommended | `2026.4.1.0` |
| `deployment.environment` | recommended | `production` / `staging` / `dev` |
| `service.instance.id` | recommended | hostname or pod name |
| `cloud.provider` | recommended | `azure` |
| `cloud.region` | recommended | `eastus` |

In Application Insights:
- `service.name` → `cloud_RoleName`
- `service.instance.id` → `cloud_RoleInstance`
- `deployment.environment` → custom dimension

Setting `service.name` is what makes your service appear as a separate node on the Application Map. Multiple services emitting to the same Application Insights resource without setting `service.name` will collapse into one node — useless.

## Common span attributes

### HTTP

```
http.request.method        = "POST"
http.response.status_code  = 200
url.path                   = "/api/v1/agents"
url.scheme                 = "https"
server.address             = "api.example.com"
server.port                = 443
http.route                 = "/api/v1/agents/{agent_id}"  # template, not interpolated
```

`http.route` is critical for cardinality control — bucketing all `/api/v1/agents/123`, `/api/v1/agents/456`, etc. under one operation. Without it, every distinct ID becomes a different operation in dashboards.

### Database

```
db.system        = "postgresql"
db.namespace     = "production"
db.operation     = "SELECT"
db.statement     = "SELECT * FROM users WHERE id = $1"  # parameterized, not concrete
db.collection.name = "users"
```

NEVER put concrete parameter values in `db.statement` — that explodes cardinality and leaks PII.

### Messaging (queues, topics)

```
messaging.system           = "azureservicebus"
messaging.operation         = "publish" / "receive"
messaging.destination.name  = "orders-topic"
```

### GenAI / LLM

OTel has GenAI semantic conventions (currently experimental, stabilizing through 2026):

```
gen_ai.system              = "anthropic"
gen_ai.request.model       = "claude-sonnet-4-5"
gen_ai.usage.input_tokens  = 1024
gen_ai.usage.output_tokens = 256
gen_ai.response.finish_reasons = ["end_turn"]
```

Use these for any LLM call. Not yet GA but supported by most observability backends.

## Custom attributes

When the spec doesn't cover something, use your service prefix:

```
starbase.workflow.module = "advisor"
starbase.workflow.step = "field_mapper"
starbase.user.tenant_id = "acme-corp"
```

NOT `module = "advisor"` (collides with other libs) or `tenantId` (ignores the convention prefix).

## Span names

| Activity | Span name format | Example |
|---|---|---|
| HTTP server | `{HTTP method} {http.route}` | `GET /api/v1/agents/{id}` |
| HTTP client | `{HTTP method}` | `POST` (with `server.address` attribute) |
| Database | `{db.operation} {db.collection.name}` | `SELECT users` |
| Messaging | `{messaging.destination.name} {operation}` | `orders-topic publish` |
| Function | `{ClassName}.{method_name}` | `WorkflowRouter.route` |

The point: span name is for low-cardinality grouping. Specific values go in attributes.

## Span kinds

```
SpanKind.SERVER     # incoming request (web server)
SpanKind.CLIENT     # outgoing request (HTTP client, DB call)
SpanKind.PRODUCER   # publishing to a queue
SpanKind.CONSUMER   # processing from a queue
SpanKind.INTERNAL   # internal computation
```

`INTERNAL` is the default. Set explicitly when crossing a process boundary — backends use this to draw the trace tree correctly.

## Status codes

```
Status.OK    # success
Status.ERROR # failed
Status.UNSET # default — DO NOT change unless something failed
```

Setting `Status.OK` on every span is a common mistake. Leave it as `UNSET` for normal operation. Set `ERROR` only on actual failures. The Application Insights backend treats `UNSET` and `OK` the same way.

```python
from opentelemetry.trace import Status, StatusCode

with tracer.start_as_current_span("call_external_api") as span:
    try:
        response = await call(...)
    except Exception as exc:
        span.set_status(Status(StatusCode.ERROR, str(exc)))
        span.record_exception(exc)
        raise
```

## Anti-patterns

- Custom attribute names that duplicate spec attributes (`http_method` instead of `http.request.method`)
- Concrete URLs / IDs in span names (high cardinality)
- Concrete parameter values in `db.statement` (PII + cardinality)
- `service.name` not set (services collapse on the App Map)
- Setting `Status.OK` on every span
- Custom prefix that doesn't include the service name
- Ignoring resource attributes — they save you from setting things 100 times

## See also

- `concepts/cost-and-cardinality.md` — cardinality discipline
- `concepts/correlation-and-tracing.md` — trace context propagation
- `patterns/otel-python-instrumentation.md` — putting it all together
- `anti-patterns.md` (items 12, 13, 14, 15)
