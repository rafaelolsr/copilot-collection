# Pattern: Connected Agents

> Agent-to-agent communication ≤2 levels deep.

## Architecture

```
Orchestrator
├── Research Agent       (level 1)
├── Analysis Agent       (level 1)
│   └── Sub-Analyst      (level 2 — maximum depth)
└── Reporting Agent      (level 1)
```

**NEVER exceed 2 levels.** Deeper trees are:
- Hard to debug
- Expensive (token multiplication)
- Slow (sequential agent calls)

## Implementation

```python
# Deploy child agents FIRST
research_agent = client.agents.create_agent(
    model=os.getenv("MODEL_DEPLOYMENT_NAME"),
    name="ResearchAgent",
    instructions="You research topics and return summaries.",
)

analysis_agent = client.agents.create_agent(
    model=os.getenv("MODEL_DEPLOYMENT_NAME"),
    name="AnalysisAgent",
    instructions="You analyze data and provide insights.",
)

# Then deploy orchestrator with connected agent tools
from azure.ai.agents.models import ConnectedAgentTool

orchestrator = client.agents.create_agent(
    model=os.getenv("MODEL_DEPLOYMENT_NAME"),
    name="Orchestrator",
    instructions="You coordinate research and analysis tasks.",
    tools=[
        ConnectedAgentTool(agent_id=research_agent.id),
        ConnectedAgentTool(agent_id=analysis_agent.id),
    ],
)
```

## Deploy Order

**Children first, orchestrator last.** `ConnectedAgentTool` needs children deployed.

```
1. Deploy ResearchAgent
2. Deploy AnalysisAgent
3. Deploy Orchestrator (references 1 and 2)
```

## When to Use Connected Agents vs Function Tools

| Scenario | Choice |
|---|---|
| Simple computation | Function tool |
| Complex reasoning sub-task | Connected agent |
| External API call | Function tool (or MCP) |
| Multi-step investigation | Connected agent |

## Anti-Pattern: Deep Trees

```
❌ Orchestrator → Manager → Worker → Sub-Worker → Helper
   4 levels — impossible to debug, costs multiply

✅ Orchestrator → [Worker A, Worker B, Worker C]
   1 level — flat, debuggable, cost-controlled
```

## Checklist

- [ ] ≤2 levels of depth
- [ ] Children deployed before orchestrator
- [ ] Each agent has a focused, single responsibility
- [ ] Timeouts on all runs (including child agent runs)
- [ ] OTel tracing spans for each agent invocation
