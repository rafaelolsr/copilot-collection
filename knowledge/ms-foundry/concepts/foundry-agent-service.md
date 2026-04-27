# Foundry Agent Service

> **Last validated**: 2026-04-26 | **Status**: GA | **Confidence**: 0.90

## Overview

Foundry Agent Service (formerly Azure AI Foundry Agent Service) is the managed service for creating, deploying, and running AI agents. It provides an OpenAI-wire-compatible Responses API with Microsoft-managed infrastructure.

## Core Concepts

### Agent
A persistent resource with:
- **Name/ID**: Unique identifier reused across requests
- **Model**: Deployment name (e.g., "gpt-4o") — use env vars, never hardcode
- **Instructions**: System prompt defining agent behavior
- **Tools**: Function tools, file_search, code_interpreter, MCP, connected agents
- **Knowledge bases**: Foundry IQ KB IDs for agentic retrieval

### Thread
A conversation container holding messages. One thread per user session.
- **Reuse threads** for multi-turn conversations (don't create per-turn)
- Messages accumulate automatically
- Thread persists across runs

### Run
A single agent execution on a thread.
- **Always set timeout** — runs can hang indefinitely without one
- **Always handle cancellation** — if timeout fires, cancel the run explicitly
- Poll for completion or use streaming

### Message
Content within a thread. Roles: `user`, `assistant`.
- `Message.contents` is `list[Content]`, not `str`
- Extract `.text` from each Content object

## Authentication

**Always use DefaultAzureCredential. Never hardcode API keys.**

```python
from azure.identity import DefaultAzureCredential
from azure.ai.projects import AIProjectClient

credential = DefaultAzureCredential()
client = AIProjectClient(
    credential=credential,
    project_connection_string=os.getenv("AZURE_AI_PROJECT_CONNECTION_STRING"),
)
```

## Agent Lifecycle

```
Create Agent → Create Thread → Add Message → Create Run → Poll → Extract Messages
     ↑                                                              ↓
     └──────────── Reuse agent ID ─────── Reuse thread ────────────┘
```

## Key Rules

1. **Reuse agent IDs** — creating per request is wasteful
2. **Reuse threads** — creating per turn loses context
3. **Set timeouts** on all run completions
4. **Cancel hung runs** explicitly
5. **Use env vars** for model deployment names
6. **Use 2.0+ connection strings** — not pre-2.0 endpoint URLs
7. **Pair azure-ai-projects + azure-ai-agents** — they're complementary, not replacements
