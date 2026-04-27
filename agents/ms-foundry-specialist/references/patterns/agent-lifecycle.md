# Pattern: Agent Lifecycle

> Create → Thread → Message → Run → Poll → Extract

## Full Example

```python
import os
from azure.identity import DefaultAzureCredential
from azure.ai.projects import AIProjectClient

credential = DefaultAzureCredential()
client = AIProjectClient(
    credential=credential,
    project_connection_string=os.getenv("AZURE_AI_PROJECT_CONNECTION_STRING"),
)

# 1. Create agent (or reuse existing agent ID)
agent = client.agents.create_agent(
    model=os.getenv("MODEL_DEPLOYMENT_NAME"),  # never hardcode
    name="research-assistant",
    instructions="You are a research assistant. Answer questions concisely.",
    tools=[],  # add tools as needed
)

# 2. Create thread (reuse for multi-turn)
thread = client.agents.create_thread()

# 3. Add user message
client.agents.create_message(
    thread_id=thread.id,
    role="user",
    content="What are the key trends in AI agent frameworks in 2026?",
)

# 4. Create and wait for run (ALWAYS with timeout)
run = client.agents.create_run(
    thread_id=thread.id,
    assistant_id=agent.id,
)

try:
    run = client.agents.wait_for_run_completion(
        thread_id=thread.id,
        run_id=run.id,
        timeout=300,  # 5-minute timeout
    )
except TimeoutError:
    client.agents.cancel_run(thread_id=thread.id, run_id=run.id)
    raise

# 5. Check run status
if run.status == "failed":
    raise RuntimeError(f"Run failed: {run.last_error}")

# 6. Extract assistant messages
messages = client.agents.list_messages(thread_id=thread.id)
for msg in messages.data:
    if msg.role == "assistant":
        for content in msg.content:
            if content.type == "text":
                print(content.text.value)
```

## Multi-Turn Conversation

```python
# Subsequent turns reuse the same thread and agent
client.agents.create_message(
    thread_id=thread.id,  # same thread
    role="user",
    content="Tell me more about the Microsoft Agent Framework specifically.",
)

run = client.agents.create_run(
    thread_id=thread.id,
    assistant_id=agent.id,  # same agent
)
run = client.agents.wait_for_run_completion(
    thread_id=thread.id, run_id=run.id, timeout=300
)
```

## With OpenTelemetry Tracing

```python
from opentelemetry import trace

tracer = trace.get_tracer(__name__)

with tracer.start_as_current_span("agent_run") as span:
    span.set_attribute("agent_id", agent.id)
    span.set_attribute("thread_id", thread.id)

    run = client.agents.create_run(thread_id=thread.id, assistant_id=agent.id)
    run = client.agents.wait_for_run_completion(
        thread_id=thread.id, run_id=run.id, timeout=300
    )
    span.set_attribute("run_status", run.status)
```

## Checklist

- [ ] Agent ID reused (not created per request)
- [ ] Thread reused for multi-turn
- [ ] Timeout set on `wait_for_run_completion`
- [ ] Cancellation on timeout
- [ ] Run status checked before extracting messages
- [ ] OTel tracing in production
- [ ] Model name from env var
