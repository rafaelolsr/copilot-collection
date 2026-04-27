# Skills

Skills are folders of instructions, scripts, and reference content that
Copilot loads when relevant. They differ from agents:

- **Agent**: a specialist invoked separately (`copilot --agent=name`),
  spawns its own context, owns a domain's knowledge base.
- **Skill**: a procedure / playbook loaded INTO the current context, often
  with bundled scripts and references.

Use skills for:
- Recurring workflows you want triggered with `/skill-name`
- Procedures with bundled scripts (e.g., scanners, generators)
- Reference content the agent should load on-demand

Use agents for:
- Deep specialists in a domain (Foundry, Python AI, observability...)
- Anything needing a 100+ file knowledge base
- Tasks where you want context isolation from the calling conversation

## Directory layout

```
skills/<skill-name>/
├── SKILL.md                    # required — entry point with frontmatter
├── references/                 # optional — markdown reference docs the skill loads
├── scripts/                    # optional — Python / bash / etc. helpers
└── assets/                     # optional — templates, images, code samples
```

## SKILL.md frontmatter spec

```yaml
---
name: <kebab-case-name>          # required, unique, lowercase + hyphens, max 64 chars
description: |                   # required, max 1024 chars; drives auto-routing
  What this skill does.
  Use when: ...
  Do NOT use for: ...
license: MIT                     # optional
allowed-tools: [shell]           # optional — pre-approved tools
argument-hint: <text>            # optional — UX hint for invocation
user-invokable: true             # optional, default true
disable-model-invocation: false  # optional, default false
---
```

## Body structure

The body is markdown. Effective skills have:

1. **One-paragraph overview** — what it does in one breath
2. **When to use / NOT use** — explicit boundaries
3. **Workflow** — numbered steps the model follows
4. **Output template** — what the skill emits at the end
5. **Anti-patterns** — what to avoid (including in the skill's own work)
6. **Configuration** — parameters the user can set in the prompt
7. **See also** — links to other skills / agents

## Skills in this collection

| Skill | Purpose |
|---|---|
| `simplify` | Refactor recently-changed code for clarity; remove cruft |
| `ultrathink` | Deep deliberation for hard architectural decisions |
| `code-review` | Systematic 8-category review of a diff / PR |
| `kb-revalidate` | Re-validate KB content against authoritative sources (90-day cycle) |
| `agentic-eval` | Add evaluation suite to an existing agent / pipeline |

Each has its own SKILL.md with full documentation.

## Invoking skills

```bash
# Slash command (preferred)
/simplify scope="diff vs main"
/ultrathink should we use Lakehouse or Warehouse for this 5GB model?
/code-review

# Auto-routing — Copilot picks based on description
copilot --prompt "review my changes for over-engineering"
# (matches simplify skill description)

# CLI management
/skills list
/skills info simplify
/skills reload
```

## Creating a new skill

1. Create `skills/<your-skill>/`
2. Write `SKILL.md` with required frontmatter
3. Add `references/` and `scripts/` if needed
4. Test invocation: `/your-skill`
5. Run `scripts/validate.sh` to check structure

See [CONTRIBUTING.md](../CONTRIBUTING.md) for the full flow.

## Skills vs agent KB

In this collection, agents have a `references/` directory (after the
migration from `knowledge/<domain>/`). This is the agent's OWN KB, not a
shared skill. Agents read their own references; skills read theirs.

Skills can reference agents in their body (e.g., "for deep analysis,
delegate to `code-reviewer` agent") but don't share KBs structurally.
