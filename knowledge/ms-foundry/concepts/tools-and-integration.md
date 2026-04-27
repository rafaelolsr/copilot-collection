# Tools and Integration

> **Last validated**: 2026-04-26 | **Status**: GA | **Confidence**: 0.90

## Tool Types

### Function Tools
Simple deterministic operations — math, DB queries, API calls.

```python
tools = [
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "Get current weather for a city",
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {"type": "string", "description": "City name"},
                },
                "required": ["city"],
            },
        },
    }
]
```

### File Search
Built-in retrieval over uploaded files. Foundry IQ replaces this for KB use cases.

### Code Interpreter
Sandboxed Python execution for data analysis, chart generation, file processing.

### MCP (Model Context Protocol)
Integrate external tools/services that publish MCP specs.

**Approval Policies** (CRITICAL):
- **Destructive tools** (delete, update, write): `require_approval="always"` — NEVER `"never"`
- **Read-only tools**: approval optional

```python
mcp_tool = {
    "name": "delete_record",
    "description": "Delete a record from the database",
    "require_approval": "always",  # CRITICAL for destructive actions
}
```

### Connected Agents
Agent-to-agent communication. **≤2 levels deep** — deeper trees are hard to debug and costly.

```
✅ Orchestrator → [Agent A, Agent B, Agent C]  (1 level)
✅ Orchestrator → Agent A → Sub-Agent          (2 levels)
❌ Orchestrator → Agent A → Sub-Agent → Sub-Sub (3 levels — flag and flatten)
```

## Tool Selection Guide

| Scenario | Tool Type |
|---|---|
| Simple computation, API call | Function tool |
| Complex sub-task, reasoning | Connected agent |
| External service with MCP spec | MCP |
| Document retrieval | Foundry IQ (not file_search) |
| Data analysis, charting | Code interpreter |

## Key Rules

1. **Prefer function tools** for simplicity
2. **Connected agents ≤2 levels** — flag deeper trees
3. **MCP destructive actions need approval** — `require_approval="always"`
4. **Use Foundry IQ** for knowledge — not file_search for KB scenarios
5. **Idempotency keys** on Responses API calls
