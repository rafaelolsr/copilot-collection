# Pattern: MCP Tool Integration

> Register MCP tools with approval policies.

## Read-Only MCP Tool

```python
mcp_tool = {
    "type": "mcp",
    "name": "search_docs",
    "description": "Search the documentation repository",
    "server_url": "https://mcp.contoso.com/docs",
    "require_approval": "never",  # OK for read-only
}
```

## Destructive MCP Tool (MUST Have Approval)

```python
mcp_tool = {
    "type": "mcp",
    "name": "delete_record",
    "description": "Delete a record from the database",
    "server_url": "https://mcp.contoso.com/db",
    "require_approval": "always",  # CRITICAL — never "never" for destructive
}
```

## Approval Policy Rules

| Action Type | `require_approval` |
|---|---|
| Read, search, query | `"never"` (acceptable) |
| Create, write, insert | `"always"` (recommended) |
| Update, modify, patch | `"always"` (required) |
| Delete, remove, drop | `"always"` (CRITICAL) |

## Attaching MCP Tools to an Agent

```python
agent = client.agents.create_agent(
    model=os.getenv("MODEL_DEPLOYMENT_NAME"),
    name="data-manager",
    instructions="You manage data operations with approval for writes.",
    tools=[read_mcp_tool, write_mcp_tool],
)
```

## Anti-Patterns

1. `require_approval="never"` on destructive tools → **FLAG CRITICAL**
2. Missing `server_url` → tool won't connect
3. Vague tool descriptions → agent can't decide when to use it
4. No error handling for MCP server downtime
