# Contributing

Thanks for adding to `copilot-collection`. This repo aims for production-grade,
verifiable agents, skills, instructions, hooks, and workflows — not
"looks plausible" AI output. The CI checks reject most of the common
failure modes; following this guide makes them pass on the first try.

---

## What goes where

| You're adding | Put it in | See doc |
|---|---|---|
| A domain specialist (deep, has its own KB) | `agents/<name>/` | `docs/README.knowledge.md` |
| A procedural workflow (e.g., `/simplify`) | `skills/<name>/` | `docs/README.skills.md` |
| Coding standards for a file type | `instructions/<name>.instructions.md` | `docs/README.instructions.md` |
| A check fired on session events | `hooks/<name>/` | `docs/README.hooks.md` |
| An agentic GitHub Action | `workflows/<name>.md` | `docs/README.workflows.md` |
| Marketplace plugin manifest | `plugins/<name>/plugin.yaml` | `agents/README.md` |
| End-to-end recipe / case study | `cookbook/<name>.md` | this file |

If your contribution is a generic procedure (review, simplify, deliberate)
→ skill. If it's a deep specialist needing 10+ reference files → agent.

---

## Adding a new agent

1. **Copy the generator prompt**
   ```bash
   cat _templates/AGENT_CREATION_PROMPT_COPILOT.md | pbcopy
   ```
   Paste it into a Copilot CLI session.

2. **Fill the DECLARATION block**
   - `name` is lowercase-hyphenated and becomes the filename
   - `description` is what Copilot uses for auto-routing — be specific
   - `tools` uses official Copilot tool names: `read`, `edit`, `search`,
     `execute`, `web`, `todo`, `agent` (or `server/tool` for MCP)
   - `sources` are the URLs the generator must fetch BEFORE writing any KB
     file (no shortcuts — substitution is the #1 failure mode)
   - `KB_DEPTH`: `minimal` for cheat-sheet agents, `standard` for typical,
     `full` for agents that produce structured output verified by tests

3. **Run the generator**
   The prompt produces:
   ```
   agents/<name>.agent.md
   knowledge/<domain>/index.md
   knowledge/<domain>/quick-reference.md
   knowledge/<domain>/_manifest.yaml
   knowledge/<domain>/anti-patterns.md
   knowledge/<domain>/concepts/*.md      (KB_DEPTH ≥ standard)
   knowledge/<domain>/patterns/*.md      (KB_DEPTH ≥ standard)
   knowledge/<domain>/specs/*.yaml       (KB_DEPTH = full)
   knowledge/<domain>/examples/tests/*.json  (KB_DEPTH = full)
   plugins/<name>/plugin.yaml
   ```

4. **Validate locally**
   ```bash
   scripts/validate.sh
   ```
   Fix any failures before opening a PR.

5. **Open a PR**
   - Title: `feat(agent): add <name>`
   - PR body: link to the source URLs that grounded the KB
   - The CI workflow runs `validate.sh` and posts results

---

## Frontmatter spec — what's allowed

Per the [official Copilot CLI spec](https://docs.github.com/en/copilot/reference/custom-agents-configuration):

| Field                      | Required | Notes |
|----------------------------|----------|-------|
| `name`                     | optional | Defaults to filename (without `.agent.md`) |
| `description`              | **required** | Max ~1,400 chars; drives auto-routing |
| `target`                   | optional | `vscode` \| `github-copilot` (default: both) |
| `tools`                    | optional | YAML list; default = all tools |
| `model`                    | optional | Model id; inherits default if unset |
| `disable-model-invocation` | optional | Default `false` |
| `user-invocable`           | optional | Default `true` |
| `mcp-servers`              | optional | MCP server configs (CLI only) |
| `metadata`                 | optional | Free-form name/value pairs |

**Do not add custom frontmatter fields.** Copilot ignores them silently. Move
metadata into the body's `## Metadata` section.

---

## Tool names — official allowlist

Use these EXACT names in `tools:`. No wildcards on native tools, no invented
names.

| Name      | Purpose            | Aliases (don't use these) |
|-----------|--------------------|---------------------------|
| `read`    | Read files         | `Read`, `read_file`, `NotebookRead` |
| `edit`    | Edit/write files   | `Edit`, `Write`, `MultiEdit`, `write_file` |
| `search`  | Grep/glob          | `Grep`, `Glob` |
| `execute` | Shell commands     | `Bash`, `shell`, `run_shell` |
| `web`     | URL/web search     | `WebSearch`, `WebFetch`, `web_fetch` |
| `todo`    | Task lists         | (VS Code only) |
| `agent`   | Invoke other agents | `Task`, `custom-agent` |

MCP servers use `server/tool` or `server/*`:

```yaml
tools: ["read", "edit", "github/*", "playwright/browser_navigate"]
```

---

## Body length

- Hard cap: **30,000 characters** (after frontmatter)
- Soft target: **15,000–20,000 characters**
- If you're approaching 25,000, move detail into `knowledge/<domain>/` files
  and have the agent body reference them via the `read` tool

---

## KB structure

Every agent owns a `knowledge/<domain>/` directory. Required files:

```
knowledge/<domain>/
├── index.md              # navigation table, key concepts, learning path
├── quick-reference.md    # decision matrix, common pitfalls
├── _manifest.yaml        # registry of all KB files with confidence scores
├── anti-patterns.md      # Wrong/Correct pairs for every flagged anti-pattern
├── concepts/             # one per concept (≤150 lines each)
└── patterns/             # one per pattern (≤200 lines each)
```

KB markdown is portable — same files work whether the agent is run by Copilot
CLI or VS Code Copilot.

---

## Anti-substitution rule (critical)

The generator MUST fetch every URL in `sources` BEFORE writing any KB file.
Generic Python/AI content (Anthropic SDK, tenacity, instructor, langchain)
must NOT appear in domain-specific KBs unless those names are explicitly in
`versions` or `sources`.

CI's `validate.sh` greps for forbidden tokens. PRs with substituted content
are rejected.

---

## Plugin manifest

Each agent gets a plugin manifest at `plugins/<name>/plugin.yaml`:

```yaml
name: <name>
version: 0.1.0
description: <one-line summary>
author: <your-handle>
license: MIT
agent: ../../agents/<name>.agent.md
knowledge: ../../knowledge/<domain>/
```

Plugin format mirrors the [github/awesome-copilot](https://github.com/github/awesome-copilot)
convention. One plugin per agent — keeps installs lean.

---

## Running CI locally before pushing

```bash
scripts/validate.sh
```

The script runs the same checks GitHub Actions runs. Fix all errors before
opening a PR.

---

## Style

- No emoji in agent bodies unless explicitly requested by the agent's domain
- No marketing language in descriptions ("powerful", "comprehensive",
  "blazing fast"). Be specific.
- Anti-patterns must include both Wrong AND Correct code blocks
- Code examples must be syntactically valid (CI runs language-specific
  syntax checks where possible)
