# Pattern: OpenTelemetry Tracing Setup

> Production agents MUST have OTel tracing.

## Setup with Azure Monitor

```python
import os
from azure.identity import DefaultAzureCredential
from azure.monitor.opentelemetry import configure_azure_monitor
from opentelemetry import trace

credential = DefaultAzureCredential()

# Configure Azure Monitor as the OTel exporter
configure_azure_monitor(
    credential=credential,
    connection_string=os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING"),
)

tracer = trace.get_tracer(__name__)
```

## Tracing an Agent Run

```python
async def run_agent_with_tracing(
    client, agent_id: str, thread_id: str, user_message: str
) -> str:
    with tracer.start_as_current_span("agent_interaction") as span:
        span.set_attribute("agent_id", agent_id)
        span.set_attribute("thread_id", thread_id)
        span.set_attribute("message_preview", user_message[:50])  # truncated, no PII

        # Add message
        client.agents.create_message(
            thread_id=thread_id, role="user", content=user_message
        )

        # Run with tracing
        with tracer.start_as_current_span("agent_run") as run_span:
            run = client.agents.create_run(
                thread_id=thread_id, assistant_id=agent_id
            )
            run_span.set_attribute("run_id", run.id)

            try:
                run = client.agents.wait_for_run_completion(
                    thread_id=thread_id, run_id=run.id, timeout=300
                )
                run_span.set_attribute("status", run.status)
                run_span.set_attribute("total_tokens", run.usage.total_tokens)
            except TimeoutError:
                run_span.set_attribute("status", "timeout")
                client.agents.cancel_run(thread_id=thread_id, run_id=run.id)
                raise

        # Extract response
        messages = client.agents.list_messages(thread_id=thread_id)
        response_text = ""
        for msg in messages.data:
            if msg.role == "assistant":
                for content in msg.content:
                    if content.type == "text":
                        response_text = content.text.value
                        break
                break

        span.set_attribute("response_length", len(response_text))
        return response_text
```

## What to Trace / What NOT to Log

### ✅ Trace These
- Agent run start/end timestamps
- Run status (completed, failed, timeout)
- Token usage (input, output, total)
- Tool invocations and tool names
- Error conditions and error types
- Latency per step

### ❌ Never Log These
- Full prompts or system instructions
- Full user input (PII risk)
- Raw agent messages without scrubbing
- API keys, credentials, connection strings
- Full Foundry payloads
- DAX filter values (may contain PII)

## Dependencies

```bash
pip install azure-monitor-opentelemetry opentelemetry-api
```

## Checklist

- [ ] `configure_azure_monitor()` called at startup
- [ ] `APPLICATIONINSIGHTS_CONNECTION_STRING` in env vars
- [ ] Spans for agent runs, tool calls, error paths
- [ ] No PII in span attributes (truncate/hash)
- [ ] Token usage recorded
- [ ] Timeout status traced
