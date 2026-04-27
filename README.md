# copilot-collection

A curated collection of GitHub Copilot **agents, skills, instructions,
hooks, workflows, plugins, and recipes** — production-grade,
knowledge-base-backed, and validated against the official
[Copilot CLI custom-agents specification](https://docs.github.com/en/copilot/reference/custom-agents-configuration)
and [Agent Skills spec](https://docs.github.com/en/copilot/how-tos/copilot-cli/customize-copilot/add-skills).

Compatible with **GitHub Copilot CLI** and **VS Code Copilot**.

---

## What's in here

| Directory | Purpose | Format |
|-----------|---------|--------|
| `agents/` | Domain specialists invocable via `--agent=name` | `<name>/<name>.agent.md` + `references/` (KB) |
| `skills/` | Procedural playbooks invocable via `/skill-name` | `<name>/SKILL.md` + scripts/references |
| `instructions/` | Coding standards auto-applied by file pattern | `<name>.instructions.md` |
| `hooks/` | Automated actions on session events | `<name>/hooks.json` + scripts |
| `workflows/` | Agentic GitHub Actions | `<name>.md` with frontmatter |
| `plugins/` | Plugin manifests for marketplace install | `<name>/plugin.yaml` |
| `cookbook/` | Copy-paste end-to-end recipes | `<name>.md` walkthroughs |
| `docs/` | Reference docs per artifact type | `README.<type>.md` |
| `_templates/` | Templates for agent + KB generation | scaffolding |
| `scripts/` | Validation, sync, scaffolding utilities | shell |

---

## Available specialists (agents)

| Agent | Domain |
|-------|--------|
| [ms-foundry-specialist](agents/ms-foundry-specialist/) | Microsoft Foundry (agents, IQ, SDKs, Agent Framework) |
| [python-specialist](agents/python-specialist/) | Python for AI/LLM systems |
| [observability-specialist](agents/observability-specialist/) | KQL, App Insights, OpenTelemetry |
| [powerbi-tmdl-specialist](agents/powerbi-tmdl-specialist/) | Power BI, TMDL, DAX, PBIP, XMLA |
| [eval-framework-specialist](agents/eval-framework-specialist/) | LLM evaluation framework |
| [microsoft-fabric-specialist](agents/microsoft-fabric-specialist/) | Fabric Lakehouse / Warehouse / OneLake |
| [azure-devops-specialist](agents/azure-devops-specialist/) | Azure DevOps pipelines + REST API |

---

## Available skills

| Skill | Purpose |
|-------|---------|
| [simplify](skills/simplify/) | Refactor recently-changed code; remove cruft, DRY, dead code |
| [ultrathink](skills/ultrathink/) | Structured deliberation for hard architectural decisions |
| [code-review](skills/code-review/) | Systematic 8-category review of a diff / PR |
| [kb-revalidate](skills/kb-revalidate/) | Re-validate KB content against authoritative sources |
| [agentic-eval](skills/agentic-eval/) | Add evaluation suite (deterministic + AI-assisted + agentic) to an agent |

---

## Other artifacts

| Type | Items |
|------|-------|
| Instructions | [python](instructions/python.instructions.md) — uv + ruff + mypy + Pydantic v2 + async-first |
| Hooks | [kb-staleness-warning](hooks/kb-staleness-warning/) — sessionStart KB freshness warning |
| Workflows | [eval-regression](workflows/eval-regression.md) — PR-time eval regression check |
| Cookbook | [recipe-creating-a-foundry-agent](cookbook/recipe-creating-a-foundry-agent.md) — end-to-end Foundry agent walkthrough |

---

## Installation

### Option 1 — Marketplace plugin (recommended)

```bash
# Register this collection as a marketplace (one-time)
copilot plugin marketplace add RafaelOLSR/copilot-collection

# Install a single agent
copilot plugin install ms-foundry-specialist@copilot-collection
```

### Option 2 — Install a skill via gh

```bash
gh skill install RafaelOLSR/copilot-collection simplify
gh skill install RafaelOLSR/copilot-collection ultrathink
```

### Option 3 — Git clone & copy

```bash
git clone https://github.com/RafaelOLSR/copilot-collection.git

# Agents (folder includes the .agent.md AND references/ KB)
cp -r copilot-collection/agents/ms-foundry-specialist your-repo/.github/agents/

# Skills
cp -r copilot-collection/skills/simplify your-repo/.github/skills/

# Instructions
cp copilot-collection/instructions/python.instructions.md your-repo/.github/instructions/

# Hooks
cp -r copilot-collection/hooks/kb-staleness-warning your-repo/.github/hooks/
```

---

## Invoking

```bash
# Auto-routing (Copilot picks based on description)
copilot --prompt "scaffold a Foundry agent in Python with a calculator tool"

# Explicit agent
copilot --agent=ms-foundry-specialist --prompt "..."

# Explicit skill (slash command)
/simplify
/ultrathink should we use Lakehouse or Warehouse?
/code-review

# Slash management
/agents
/skills list
/skills info simplify
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

See [CONTRIBUTING.md](CONTRIBUTING.md) and [docs/](docs/) for the full flow.

---

## CI validation

Every PR runs `scripts/validate.sh` automatically via GitHub Actions:

- **Agent files**: frontmatter is parseable YAML using only spec-allowed fields,
  `description` under 1,400 chars, body under 30,000 chars, no auto-link
  corruption, tool names match official spec
- **KBs**: `references/` directory exists with required files; KB
  cross-references resolve; no unfilled `{{placeholders}}`
- **Skills**: `SKILL.md` has frontmatter with `name` + `description`
- **Plugins**: manifests valid; agent reference resolves

---

## Bidirectional sync with private projects

The `scripts/sync.sh` script syncs agents (with their KBs) between this
public collection and a private project repo (e.g., a Foundry workspace).

```bash
# Pull from a private project into this collection
scripts/sync.sh pull /path/to/private-project ms-foundry-specialist

# Push from this collection into a private project
scripts/sync.sh push /path/to/private-project ms-foundry-specialist
```

Sync handles path translation between the two layouts:
- **Collection**: `agents/<name>/<name>.agent.md` + `agents/<name>/references/`
- **Project**: `.github/agents/<name>.agent.md` + `.github/agents/kb/<domain>/`

Sync is manual by design — automated bidirectional sync invites merge
conflicts and accidental overwrites. Always review the diff before
committing.

---

## Knowledge base re-validation

Every agent's `references/` content has a `last_validated:` field.
After 90 days, content is suspect. The collection enforces this via:

1. **Hook**: `hooks/kb-staleness-warning/` warns at session start
2. **Skill**: `/kb-revalidate` walks the re-validation procedure
3. **Documentation**: `docs/README.knowledge.md` explains the protocol

---

## License

MIT — see [LICENSE](LICENSE).

---

## Standards & references

- [GitHub Copilot CLI custom agents](https://docs.github.com/en/copilot/reference/custom-agents-configuration)
- [Adding agent skills for GitHub Copilot CLI](https://docs.github.com/en/copilot/how-tos/copilot-cli/customize-copilot/add-skills)
- [Creating custom agents for Copilot CLI](https://docs.github.com/en/copilot/how-tos/copilot-cli/customize-copilot/create-custom-agents-for-cli)
