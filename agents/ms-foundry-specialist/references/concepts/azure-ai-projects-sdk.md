# azure-ai-projects Python SDK

> **Last validated**: 2026-04-26 | **Status**: GA (2.1.0+) | **Confidence**: 0.90

## Overview

The `azure-ai-projects` Python SDK is the primary client for interacting with Foundry Agent Service. It works alongside `azure-ai-agents` (they are paired, not replacements).

## Installation

```bash
pip install azure-ai-projects>=2.1.0 azure-ai-agents azure-identity
```

## Client Initialization

```python
import os
from azure.identity import DefaultAzureCredential
from azure.ai.projects import AIProjectClient

credential = DefaultAzureCredential()
client = AIProjectClient(
    credential=credential,
    project_connection_string=os.getenv("AZURE_AI_PROJECT_CONNECTION_STRING"),
)
```

### Connection String Format (2.0+)

```
<endpoint>;<subscription-id>;<resource-group>;<project-name>
```

### Pre-2.0 Format (DEPRECATED — flag if seen)

```python
# WRONG — pre-2.0 endpoint
client = AIProjectClient(
    api_endpoint="https://myregion.api.cognitive.microsoft.com/...",
    credential=cred,
)
```

## Agent Operations

```python
# Create agent
agent = client.agents.create_agent(
    model=os.getenv("MODEL_DEPLOYMENT_NAME"),
    name="my-agent",
    instructions="You are a helpful assistant.",
    tools=[...],
)

# Create thread
thread = client.agents.create_thread()

# Add message
client.agents.create_message(
    thread_id=thread.id,
    role="user",
    content="Hello!",
)

# Run with timeout
run = client.agents.create_run(thread_id=thread.id, assistant_id=agent.id)
run = client.agents.wait_for_run_completion(
    thread_id=thread.id,
    run_id=run.id,
    timeout=300,  # ALWAYS set timeout
)

# Extract messages
messages = client.agents.list_messages(thread_id=thread.id)
```

## SDK Version Compatibility

| Version | Status | Notes |
|---|---|---|
| 2.1.0+ | GA (current) | Use this |
| 2.0.x | GA | Acceptable |
| <2.0 | Deprecated | Flag and migrate |

## Key Rules

1. **Always use 2.1.0+** — flag pre-2.0 code
2. **Connection string format** — not raw endpoint URLs
3. **DefaultAzureCredential** — never API keys
4. **Pair with azure-ai-agents** — they're complementary
5. **Environment variables** for connection strings and model names
