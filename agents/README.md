# Agents

Custom Copilot agents — one `.agent.md` file per specialist.

## Available

| Agent | Domain | Description |
|-------|--------|-------------|
| [ms-foundry-specialist](ms-foundry-specialist.agent.md) | Microsoft Foundry | Foundry Agent Service, Foundry IQ, azure-ai-projects SDKs, Microsoft Agent Framework |
| [python-specialist](python-specialist.agent.md) | Python for AI systems | Async clients, structured output (Pydantic + instructor), retry, tool-use loops, evals |
| [observability-specialist](observability-specialist.agent.md) | Observability / Telemetry | KQL, Application Insights, OpenTelemetry, sampling, dashboards |
| [powerbi-tmdl-specialist](powerbi-tmdl-specialist.agent.md) | Power BI / TMDL / DAX | PBIP projects, DAX evaluation context, time intelligence, RLS, XMLA deployment |
| [eval-framework-specialist](eval-framework-specialist.agent.md) | Eval framework for AI | Deterministic / AI-assisted / agentic metrics, golden datasets, regression tracking |
| [microsoft-fabric-specialist](microsoft-fabric-specialist.agent.md) | Microsoft Fabric | Lakehouse, Warehouse, OneLake, Delta, semantic model REST API, Fabric SQL endpoint |
| [azure-devops-specialist](azure-devops-specialist.agent.md) | Azure DevOps | Pipeline YAML, REST API, branch policies, workload identity federation, PR automation |

## Format

Each file is a [Copilot CLI custom agent](https://docs.github.com/en/copilot/reference/custom-agents-configuration):

- File extension: `.agent.md` (not `.md`)
- YAML frontmatter with `name`, `description`, and optionally `tools`, `model`, `target`, etc.
- Markdown body capped at 30,000 characters

See [CONTRIBUTING.md](../CONTRIBUTING.md) for adding new agents.

## Installation

### Marketplace plugin

```bash
copilot plugin install <agent-name>@copilot-collection
```

### Manual

```bash
# Copy the agent file
cp agents/<agent-name>.agent.md your-repo/.github/agents/

# Copy the matching KB
cp -r knowledge/<domain>/ your-repo/knowledge/
```

The KB directory is required — agents read from it at runtime.

## Invoking

```bash
# Auto-routing (Copilot picks based on description)
copilot --prompt "your task here"

# Explicit
copilot --agent=<agent-name> --prompt "your task here"

# Slash command (interactive mode)
/agents
```
