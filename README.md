# copilot-collection

A curated collection of GitHub Copilot custom agents, skills, plugins, hooks,
and workflows — production-grade, knowledge-base-backed, and validated against
the official [Copilot CLI custom-agents specification](https://docs.github.com/en/copilot/reference/custom-agents-configuration).

Compatible with **GitHub Copilot CLI** and **VS Code Copilot**.

---

## What's in here

| Directory       | Purpose                                                              |
|-----------------|----------------------------------------------------------------------|
| `agents/`       | `.agent.md` custom agents — one per specialist                       |
| `knowledge/`    | KB markdown each agent reads at runtime (concepts, patterns, etc.)   |
| `plugins/`      | Plugin manifests — one plugin per agent for marketplace installation |
| `skills/`       | Reusable skills (reference content loaded inline)                    |
| `hooks/`        | Automated session hooks                                              |
| `workflows/`    | Agentic GitHub Actions workflows                                     |
| `_templates/`   | KB scaffolding templates (concept, pattern, spec, manifest, etc.)    |
| `scripts/`      | Validation, scaffolding, and sync utilities                          |

---

## Available Agents

| Agent | Domain |
|-------|--------|
| [ms-foundry-specialist](agents/ms-foundry-specialist.agent.md) | Microsoft Foundry (agents, IQ, SDKs) |
| [python-specialist](agents/python-specialist.agent.md) | Python for AI/LLM systems |
| [observability-specialist](agents/observability-specialist.agent.md) | KQL, App Insights, OpenTelemetry |
| [powerbi-tmdl-specialist](agents/powerbi-tmdl-specialist.agent.md) | Power BI, TMDL, DAX, PBIP, XMLA |
| [eval-framework-specialist](agents/eval-framework-specialist.agent.md) | LLM evaluation framework |
| [microsoft-fabric-specialist](agents/microsoft-fabric-specialist.agent.md) | Fabric Lakehouse / Warehouse / OneLake |
| [azure-devops-specialist](agents/azure-devops-specialist.agent.md) | Pipelines, REST API, branch policies |

See [agents/README.md](agents/README.md) for usage, frontmatter spec, and
contribution guidelines.

---

## Installation

### Option 1 — Marketplace plugin (recommended)

```bash
# Register this collection as a marketplace (one-time)
copilot plugin marketplace add RafaelOLSR/copilot-collection

# Install a single agent
copilot plugin install ms-foundry-specialist@copilot-collection
```

### Option 2 — Git clone & copy

```bash
git clone https://github.com/RafaelOLSR/copilot-collection.git
cp copilot-collection/agents/ms-foundry-specialist.agent.md \
   your-repo/.github/agents/
cp -r copilot-collection/knowledge/ms-foundry your-repo/knowledge/
```

The agent's KB protocol expects `knowledge/<domain>/` to exist alongside the
agent file. Always copy both.

---

## Invoking an agent

```bash
# Auto-routing — Copilot picks the right agent from the description
copilot --prompt "scaffold a Foundry agent in Python with a calculator tool"

# Explicit invocation
copilot --agent=ms-foundry-specialist --prompt "..."

# Slash command in interactive mode
/agents
```

---

## Creating a new agent

Use the generator prompt at [`_templates/AGENT_CREATION_PROMPT_COPILOT.md`](_templates/AGENT_CREATION_PROMPT_COPILOT.md).

Steps:

1. Copy `_templates/AGENT_CREATION_PROMPT_COPILOT.md` into a Copilot CLI session
2. Fill the DECLARATION block (name, role, domain, sources, concepts, patterns)
3. Run — the prompt generates the agent + KB + plugin manifest
4. Run `scripts/validate.sh` to verify everything passes CI checks
5. Open a PR

See [CONTRIBUTING.md](CONTRIBUTING.md) for the full flow.

---

## CI validation

Every PR runs `scripts/validate.sh` automatically via GitHub Actions:

- Frontmatter is parseable YAML and uses only spec-allowed fields
- `description` is present and under 1,400 chars
- Agent body is under 30,000 chars
- No auto-link corruption (`](http://...)` patterns in code blocks)
- Tool names match the official Copilot CLI tool spec
- Each agent's `knowledge/<domain>/` exists with required files
- KB cross-references resolve
- No unfilled `{{placeholders}}` in KB files
- Plugin manifests are valid

---

## Bidirectional sync with private projects

The `scripts/sync.sh` script syncs agents and KBs between this public
collection and a private project repo (e.g., your Foundry workspace).

```bash
# Pull from a private project into this collection
scripts/sync.sh pull /path/to/foundry-project ms-foundry-specialist

# Push from this collection into a private project
scripts/sync.sh push /path/to/foundry-project ms-foundry-specialist
```

Sync is manual by design — automated bidirectional sync invites merge
conflicts and accidental overwrites. Always review the diff before
committing.

---

## License

MIT — see [LICENSE](LICENSE).

---

## Standards & references

- [GitHub Copilot CLI custom agents](https://docs.github.com/en/copilot/reference/custom-agents-configuration)
- [Creating custom agents for Copilot CLI](https://docs.github.com/en/copilot/how-tos/copilot-cli/customize-copilot/create-custom-agents-for-cli)
- [github/awesome-copilot](https://github.com/github/awesome-copilot) — community collection
