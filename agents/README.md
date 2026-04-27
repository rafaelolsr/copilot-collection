# Agents

Custom Copilot agents — one folder per specialist. Each folder contains:

- `<name>.agent.md` — the agent file (frontmatter + body, ≤30K chars)
- `references/` — the agent's knowledge base (concepts, patterns, anti-patterns)

```
agents/<name>/
├── <name>.agent.md
└── references/
    ├── index.md
    ├── anti-patterns.md
    ├── _manifest.yaml
    ├── quick-reference.md
    ├── concepts/
    └── patterns/
```

## Available

| Agent | Domain | Description |
|-------|--------|-------------|
| [ms-foundry-specialist](ms-foundry-specialist/) | Microsoft Foundry | Foundry Agent Service, Foundry IQ, azure-ai-projects SDKs, Microsoft Agent Framework |
| [python-specialist](python-specialist/) | Python for AI systems | Async clients, Pydantic + instructor, retry, tool-use loops, evals |
| [observability-specialist](observability-specialist/) | Observability / Telemetry | KQL, Application Insights, OpenTelemetry, sampling, dashboards |
| [powerbi-tmdl-specialist](powerbi-tmdl-specialist/) | Power BI / TMDL / DAX | PBIP projects, DAX evaluation context, time intelligence, RLS, XMLA deployment |
| [eval-framework-specialist](eval-framework-specialist/) | Eval framework for AI | Deterministic / AI-assisted / agentic metrics, golden datasets, regression tracking |
| [microsoft-fabric-specialist](microsoft-fabric-specialist/) | Microsoft Fabric | Lakehouse, Warehouse, OneLake, Delta, semantic model REST API, Fabric SQL endpoint |
| [azure-devops-specialist](azure-devops-specialist/) | Azure DevOps | Pipeline YAML, REST API, branch policies, workload identity federation, PR automation |

## Format

Each `<name>.agent.md` is a [Copilot CLI custom agent](https://docs.github.com/en/copilot/reference/custom-agents-configuration):

- File extension: `.agent.md` (not `.md`)
- YAML frontmatter with `name`, `description`, and optionally `tools`, `model`, `target`, etc.
- Markdown body capped at 30,000 characters

See [CONTRIBUTING.md](../CONTRIBUTING.md) and [docs/README.knowledge.md](../docs/README.knowledge.md)
for adding new agents and the KB protocol.

## Installation

### Marketplace plugin

```bash
copilot plugin install <agent-name>@copilot-collection
```

### Manual

```bash
# Copy the agent folder (includes the .agent.md AND references/)
cp -r agents/<agent-name>/ your-repo/.github/agents/
```

The `references/` directory is required — agents read from it at runtime.

## Invoking

```bash
# Auto-routing (Copilot picks based on description)
copilot --prompt "your task here"

# Explicit
copilot --agent=<agent-name> --prompt "your task here"

# Slash command (interactive mode)
/agents
```

## Knowledge base protocol

Every agent has a 90-day re-validation cycle for its references. See:
- `docs/README.knowledge.md` — full protocol
- `skills/kb-revalidate/SKILL.md` — re-validate workflow
- `hooks/kb-staleness-warning/` — automated nudge
