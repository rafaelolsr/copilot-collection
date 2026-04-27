# Microsoft Agent Framework

> **Last validated**: 2026-04-26 | **Status**: GA | **Confidence**: 0.90

## Overview

Microsoft Agent Framework is the **recommended orchestrator** for building multi-agent systems on Foundry. It replaces Semantic Kernel for greenfield agent development.

## Core Components

### Executors

Follow the **Template Method Pattern** with lifecycle hooks:

```
_on_start() → _on_process() → _on_complete() → _on_error()
```

Two types:
- **BaseExecutor** — deterministic logic, no LLM
- **LLMExecutor** — calls a Foundry agent, paired with RefinementGate

### Workflows

Built with `WorkflowBuilder`:

```python
from agent_framework import WorkflowBuilder

workflow = WorkflowBuilder(
    start_executor=my_executor,
    checkpoint_storage=storage,
)
result = await workflow.run(messages, stream=True)
```

### State Management

Sync API — no `await`:
```python
ctx.get_state(key)      # sync
ctx.set_state(key, val)  # sync
```

### Events

Use `emit_async()` in executors:
```python
await self.emit_async("event_name", data)
```

## SDK Imports

```python
# Correct
from agent_framework import WorkflowBuilder, BaseExecutor
from agent_framework_azure_ai import AzureAIClient

# Correct client init
client = AzureAIClient(
    agent_name="MyAgent",
    project_endpoint="https://<name>.services.ai.azure.com",
    use_latest_version=True,
)
```

### Common API Gotchas

| Pitfall | Correct Usage |
|---|---|
| `Role.USER` | `Role("user")` — Role is NewType, not enum |
| `Message.content` as str | `Message.contents` is `list[Content]` — extract `.text` |
| `await ctx.get_state()` | Sync: `ctx.get_state(key)` |
| `workflow.run_stream()` | Removed — use `workflow.run(messages, stream=True)` |
| `emit()` | Use `emit_async()` |
| Setter methods on WorkflowBuilder | Use constructor params |

## Semantic Kernel vs Agent Framework

| | Agent Framework | Semantic Kernel |
|---|---|---|
| Status | Primary, recommended | Legacy, supported |
| New projects | ✅ Use this | ❌ Avoid |
| Existing SK code | Migrate when practical | Maintain |

**Always recommend Agent Framework for greenfield.** Flag Semantic Kernel in new code.

## Deploy Order

Child agents must be deployed **before** orchestrators — `ConnectedAgentTool` needs children deployed first.
