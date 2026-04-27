# OpenTelemetry instrumentation for ASP.NET Core

> **Last validated**: 2026-04-26
> **Confidence**: 0.92
> **Source**: https://learn.microsoft.com/en-us/azure/azure-monitor/app/opentelemetry-enable

## When to use this pattern

Adding OTel-based telemetry to an ASP.NET Core service so it emits traces, metrics, and logs to Azure Monitor / Application Insights.

## Install

```bash
dotnet add package Azure.Monitor.OpenTelemetry.AspNetCore
```

This pulls in `OpenTelemetry`, the AspNetCore instrumentation, and the Azure Monitor exporter.

## Minimal setup (Program.cs)

```csharp
using Azure.Monitor.OpenTelemetry.AspNetCore;

var builder = WebApplication.CreateBuilder(args);

builder.Services.AddOpenTelemetry().UseAzureMonitor(options =>
{
    options.ConnectionString = builder.Configuration["ApplicationInsights:ConnectionString"];
});

var app = builder.Build();

app.MapGet("/health", () => Results.Ok(new { status = "ok" }));

app.Run();
```

The connection string can come from:
- `appsettings.json` → `ApplicationInsights:ConnectionString`
- Environment variable `APPLICATIONINSIGHTS_CONNECTION_STRING`
- Direct assignment as above

## Required environment / config

```bash
APPLICATIONINSIGHTS_CONNECTION_STRING="InstrumentationKey=...;IngestionEndpoint=https://..."
OTEL_RESOURCE_ATTRIBUTES="service.name=starbase-api,service.version=2026.4.1.0,deployment.environment=production"
```

`OTEL_RESOURCE_ATTRIBUTES` is the simplest way to set resource attributes. ASP.NET Core also reads `service.name` from `AddOpenTelemetry().ConfigureResource(...)` but env var is easier for multi-environment deployment.

## Manual span creation

```csharp
using System.Diagnostics;

public class InvoiceService
{
    private static readonly ActivitySource ActivitySource = new("MyCompany.InvoiceService");

    public async Task<Invoice> ProcessAsync(string invoiceId)
    {
        using var activity = ActivitySource.StartActivity("ProcessInvoice");
        activity?.SetTag("invoice.id", invoiceId);

        var invoice = await FetchAsync(invoiceId);
        activity?.SetTag("invoice.total", invoice.Total);

        await ChargeAsync(invoice);
        return invoice;
    }
}
```

In .NET, OTel uses the existing `Activity` API. `ActivitySource` is the equivalent of OTel's `Tracer`. Tags = attributes.

Register the source so it's exported:

```csharp
builder.Services.AddOpenTelemetry()
    .WithTracing(tracing => tracing.AddSource("MyCompany.*"))
    .UseAzureMonitor();
```

`AddSource("MyCompany.*")` enables every source whose name starts with `MyCompany.`.

## Error recording

```csharp
using var activity = ActivitySource.StartActivity("CallExternalApi");

try
{
    var response = await _httpClient.GetAsync(url);
    response.EnsureSuccessStatusCode();
    return response;
}
catch (HttpRequestException ex)
{
    activity?.SetStatus(ActivityStatusCode.Error, ex.Message);
    activity?.RecordException(ex);
    throw;
}
```

`RecordException` requires the `OpenTelemetry.Api.ProviderBuilderExtensions` namespace and adds an exception event to the span.

## Custom metrics

```csharp
using System.Diagnostics.Metrics;

public class AgentMetrics
{
    private static readonly Meter Meter = new("MyCompany.AgentMetrics");
    private static readonly Counter<long> RequestsCounter =
        Meter.CreateCounter<long>("agent.requests", description: "Number of requests handled");
    private static readonly Histogram<double> DurationHistogram =
        Meter.CreateHistogram<double>("agent.request_duration", "ms", "Request duration");

    public void RecordRequest(string agentName, string outcome) =>
        RequestsCounter.Add(1, new("agent_name", agentName), new("outcome", outcome));

    public void RecordDuration(double ms, string agentName) =>
        DurationHistogram.Record(ms, new("agent_name", agentName));
}
```

Register the meter:

```csharp
builder.Services.AddOpenTelemetry()
    .WithMetrics(metrics => metrics.AddMeter("MyCompany.*"))
    .UseAzureMonitor();
```

## Sampling

```csharp
builder.Services.AddOpenTelemetry()
    .WithTracing(tracing =>
    {
        tracing.SetSampler(new TraceIdRatioBasedSampler(0.25));  // 25%
    })
    .UseAzureMonitor();
```

Or via env var `OTEL_TRACES_SAMPLER=traceidratio` + `OTEL_TRACES_SAMPLER_ARG=0.25`.

## Logging

ASP.NET Core's `ILogger<T>` is auto-wired into the OTel pipeline by `UseAzureMonitor()`. No extra setup:

```csharp
public class AdvisorController(ILogger<AdvisorController> logger) : ControllerBase
{
    public async Task<IActionResult> Ask(string question)
    {
        logger.LogInformation("advisor_question_received {QuestionLength}", question.Length);
        ...
    }
}
```

Structured property names (the `{...}` placeholders) become custom dimensions in App Insights `traces`.

## Custom dimensions on every span

```csharp
builder.Services.AddOpenTelemetry()
    .WithTracing(tracing => tracing
        .AddProcessor(new EnrichingActivityProcessor()))
    .UseAzureMonitor();

public class EnrichingActivityProcessor : BaseProcessor<Activity>
{
    public override void OnEnd(Activity activity)
    {
        activity.SetTag("deployment.region", Environment.GetEnvironmentVariable("REGION"));
    }
}
```

## Done when

- `service.name` resource attribute is set (verify on the App Map)
- Requests appear in `requests` table with `operation_Id`
- Outbound HTTP calls appear in `dependencies`
- Custom `Activity` spans appear under their parent
- Logs via `ILogger` appear in `traces`
- Sampling is configured (don't run 100% in production)
- Daily cap is set on the App Insights resource

## Anti-patterns

- Hardcoded connection string in `Program.cs` (use config / env var)
- Multiple `ActivitySource` instances with the same name (collide)
- Span tags with high-cardinality values (request IDs, user IDs)
- Forgetting `AddSource("MyCompany.*")` — your custom Activities never export
- Setting `Activity.Current.Status = OK` on every activity (leave `UNSET` for normal)
- Mixing the legacy `TelemetryClient` API with OpenTelemetry — pick one
- Not catching `HttpRequestException` distinctly from generic `Exception` — coarse error categorization

## See also

- `concepts/opentelemetry-semantic-conv.md` — attribute naming
- `concepts/sampling-strategies.md` — sampling configuration
- `concepts/correlation-and-tracing.md` — context propagation
- `patterns/otel-python-instrumentation.md` — same pattern in Python
- `anti-patterns.md` (items 11, 12, 13, 14, 15)
