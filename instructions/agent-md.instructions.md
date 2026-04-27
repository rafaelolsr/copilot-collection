---
name: agent-md
description: |
  Standards for GitHub Copilot custom agent files (.agent.md). Auto-applied
  when editing agent definitions. Enforces the official Copilot CLI spec:
  required frontmatter fields, allowlist of optional fields, body size cap
  (30,000 chars), description length (≤1,400 chars), no auto-link
  corruption, valid tool names.
applyTo: "**/*.agent.md,**/agents/**/*.md"
---

# Custom agent file standards

When generating or modifying `.agent.md` files, follow the official
[Copilot CLI custom-agents specification](https://docs.github.com/en/copilot/reference/custom-agents-configuration).

## File location

Agents live at one of these paths:

| Scope | Path |
|---|---|
| Repository | `.github/agents/<name>.agent.md` OR `agents/<name>/<name>.agent.md` |
| User | `~/.copilot/agents/<name>.agent.md` |

The file extension MUST be `.agent.md` — not `.md`.

## Frontmatter — allowed fields only

```yaml
---
name: <kebab-case-name>             # optional; defaults to filename
description: <text>                 # REQUIRED; drives auto-routing
target: <vscode | github-copilot>   # optional; defaults to both
tools: [<allowed names>]            # optional; defaults to all
disallowedTools: [<names>]          # optional
maxTurns: <int>                     # optional
effort: <low|medium|high|xhigh|max> # optional
background: <bool>                  # optional
permissionMode: <string>            # optional
skills: [<skill names>]             # optional; preload these
mcpServers: {<config>}              # optional
metadata: {<key>: <value>}          # optional; cosmetic
color: <purple|teal|coral|amber|blue>  # optional; cosmetic
---
```

**FAIL ON SIGHT:** any frontmatter field NOT in this allowlist. Custom
fields (`kb_path`, `last_validated`, `confidence_threshold`) are silently
ignored by Copilot — put them in the prompt body's METADATA section
instead.

## Description rules (drives routing)

- **Required.** Without it, no auto-routing.
- **Hard length cap:** 1,536 chars (combined description + when_to_use).
- **Soft target:** ≤1,400 chars to leave headroom.
- 3–5 sentences:
  1. What the agent does + domain
  2. Specific task types it handles
  3. "Use PROACTIVELY when..." trigger conditions
  4. "Do NOT use when..." explicit exclusions
- Include concrete trigger phrases users would type.
- Be specific. Vague descriptions ("Code reviewer") cause missed routing.
- If a same-named skill exists, descriptions MUST DIFFER:
  - Subagent: "when to spawn a fresh isolated context"
  - Skill: "when to load this knowledge inline"

## Tools — exact names only

Allowed values for `tools:`:

| Native tools | Aliases (DON'T use) |
|---|---|
| `read` | `Read`, `read_file`, `NotebookRead` |
| `edit` | `Edit`, `Write`, `MultiEdit`, `write_file` |
| `search` | `Grep`, `Glob` |
| `execute` | `Bash`, `shell`, `run_shell` |
| `web` | `WebSearch`, `WebFetch`, `web_fetch` |
| `todo` | (VS Code only) |
| `agent` | `Task`, `custom-agent` |

MCP tools: `<server>/<tool>` or `<server>/*` — no wildcards on native tools.

```yaml
# CORRECT
tools: ["read", "edit", "search", "execute", "web"]
tools: ["read", "github/*", "playwright/browser_navigate"]

# WRONG
tools: read, edit                                # comma-separated string
tools: ["read_file", "write_file"]               # invented names
tools: ["mcp__Context7__*"]                      # wildcards on individual tools
tools: ["Agent"]                                 # NEVER — subagents can't spawn subagents
```

## Body — hard cap 30,000 characters

After the closing `---` of frontmatter, the markdown body is capped at
30,000 chars. Beyond that, Copilot ignores the trailing content.

If approaching the cap:
- Move detail into a `references/` directory next to the agent file
- Body says: "Read `references/<file>.md` when..."
- Agent uses `read` tool to load on demand

## Body — recommended sections (in order)

1. **IDENTITY** — one paragraph: role, scope, what it never does.
   Include: "You do NOT inherit the calling conversation's history. Every
   invocation is a fresh context."

2. **METADATA** (informational; Copilot ignores)
   ```
   - kb_path:              references/
   - kb_index:             references/index.md
   - confidence_threshold: 0.90
   - last_validated:       YYYY-MM-DD
   - re_validate_after:    90 days
   - domain:               <domain-key>
   ```

3. **KNOWLEDGE BASE PROTOCOL** — instructions for loading references on
   demand (read index.md first, then concepts/patterns as needed).

4. **EXECUTION RULES** — confidence gating, no Agent tool, return BLOCKED
   on missing context.

5. **SKILLS / CAPABILITIES** — one block per skill the agent advertises.

6. **DELEGATION PROMPT TEMPLATE** — what callers must pass when invoking.

7. **ANTI_PATTERNS** — flagged on sight; reference `anti-patterns.md`.

8. **OUTPUT CONTRACT** — structured output emitted at end of every run.

## No auto-link corruption

A common bug: chat editors auto-linkify identifiers. Check for these
patterns in code blocks (they break syntax):

```python
# WRONG (auto-linkified)
from [azure.ai](http://azure.ai).projects import AIProjectClient

# CORRECT
from azure.ai.projects import AIProjectClient
```

Run before commit:
```bash
grep -nE '\]\(http' your-agent.agent.md
# Inside code blocks, this should return zero matches.
```

## Anti-patterns to flag

| Pattern | Severity |
|---|---|
| Custom frontmatter field not in spec allowlist | CRITICAL — silently ignored |
| `description` over 1,400 chars | WARN — will be truncated |
| Body over 30,000 chars | CRITICAL — content beyond cap is ignored |
| Auto-linkified code (`[ident](http://ident)` in code blocks) | CRITICAL — broken code |
| `Agent` in tools list | CRITICAL — subagents can't spawn subagents |
| `tools:` as comma-separated string instead of YAML list | WARN — invalid YAML |
| Wildcards on native tool names (`read*`, `*-tool`) | WARN — invalid spec |
| Description without "Use when" + "Do NOT use" | WARN — routing will misfire |
| Same description as a sibling skill | WARN — invocation ambiguous |

## Validation

```bash
# Check frontmatter
head -25 path/to/file.agent.md

# Check body size
wc -c path/to/file.agent.md   # body should be well under 30,000

# Check for auto-link corruption in code blocks
awk '/^```/ { in_code = !in_code; next } in_code && /\]\(http/ { print NR ": " $0 }' path/to/file.agent.md
# Should print nothing
```

## See also

- [Custom agents configuration — GitHub Docs](https://docs.github.com/en/copilot/reference/custom-agents-configuration)
- `instructions/skill-md.instructions.md` — for `SKILL.md` files
- `instructions/markdown.instructions.md` — base markdown rules
