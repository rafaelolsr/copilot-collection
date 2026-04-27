---
name: skill-md
description: |
  Standards for GitHub Copilot custom skill files (SKILL.md). Auto-applied
  when editing skills. Enforces the official agent-skills spec: required
  frontmatter (name, description), allowed file extensions, valid file
  paths, conditional reference loading, scripts directory conventions.
applyTo: "**/skills/**/SKILL.md,**/SKILL.md"
---

# Custom skill file standards

When generating or modifying `SKILL.md` files, follow the official
[Agent Skills specification](https://docs.github.com/en/copilot/how-tos/copilot-cli/customize-copilot/add-skills).

## Directory layout

```
skills/<skill-name>/
├── SKILL.md              # required — entry point
├── references/           # optional — markdown reference docs
├── scripts/              # optional — shell, Python helpers
└── assets/               # optional — templates, code samples
```

The skill folder name should be lowercase + hyphens. The file MUST be
named `SKILL.md` (uppercase) — not `skill.md`.

## Frontmatter — allowed fields

```yaml
---
name: <kebab-case-name>             # REQUIRED; max 64 chars
description: <text>                 # REQUIRED; max 1024 chars
license: MIT                        # optional
allowed-tools: [shell, ...]         # optional; pre-approved tools
argument-hint: <text>               # optional; UX hint
user-invocable: true                # optional, default true
disable-model-invocation: false     # optional, default false
---
```

Only these fields are documented in the spec. Don't add custom ones.

## Description rules (drives auto-routing)

- Max 1,024 chars (smaller than agent description).
- Be specific:
  1. What the skill DOES (one verb-led sentence)
  2. When to use ("Use when the user says: ..." with concrete trigger phrases)
  3. When NOT to use (explicit exclusions)
- If a same-named agent exists, descriptions MUST DIFFER:
  - Skill: "when to load this knowledge inline"
  - Agent: "when to spawn a fresh isolated context"

## Body structure

```markdown
# Skill name (H1)

## When to use / NOT to use
Explicit boundaries.

## Workflow
Numbered steps the model follows.

## Output template / contract
Exact shape of what the skill emits.

## Anti-patterns
What to avoid (including in the skill's own work).

## Configuration
Parameters the user can set in the prompt.

## See also
Links to related skills, agents, references.
```

## Conditional reference loading

In the body, instruct the model to load references on demand — don't
embed the entire reference inline:

```markdown
## Step 2 — Read the canon checklist

For each changed file, read `references/code-smells.md` and walk through...

```

This keeps the SKILL.md small. Heavy content goes in `references/`.

## Scripts directory

When a step is mechanical / scriptable, put it in `scripts/`:

```
skills/simplify/scripts/find_duplicates.py
```

Rules:
- Each script accepts a known input format (file paths, JSON, etc.)
- Each script prints structured output (JSON, exit codes)
- Add a docstring at the top: purpose, usage, expected output
- Make executable: `chmod +x script.sh` (CI does this automatically)
- Keep scripts < 200 lines; split if needed

## allowed-tools

If your skill needs shell access without per-command confirmation:

```yaml
allowed-tools: [shell]
```

Only include if genuinely needed. Most skills work fine without and the
user gets prompted per-command.

## Body length

No hard cap (unlike agents at 30K chars), but as a discipline:
- SKILL.md ≤ 500 lines
- references/* ≤ 200 lines each
- scripts/* ≤ 200 lines each

If the skill is growing past these limits, it's probably trying to do
too much — split into multiple skills.

## Anti-patterns to flag

| Pattern | Severity |
|---|---|
| File named `skill.md` (lowercase) | CRITICAL — Copilot won't recognize |
| Missing `name` or `description` frontmatter | CRITICAL — required fields |
| Description over 1,024 chars | WARN — will be truncated |
| Skill folder with non-kebab-case name (`MySkill`) | WARN — convention |
| Inline content that should be in `references/` (huge SKILL.md) | INFO — split |
| Scripts without shebang or docstring | INFO — clarity |
| Custom frontmatter field not in spec | WARN — silently ignored |
| Description duplicated with a same-named agent | WARN — routing ambiguous |
| `allowed-tools: [shell]` when not actually needed | INFO — reduce attack surface |

## Validation

```bash
# Frontmatter check
head -10 path/to/SKILL.md

# Required fields
grep -E '^name:|^description:' path/to/SKILL.md

# Body length sanity
wc -l path/to/SKILL.md            # ≤ 500 lines is healthy

# Spec compliance
ls -la path/to/SKILL.md           # must be exactly "SKILL.md", not skill.md
```

## See also

- [Adding agent skills — GitHub Docs](https://docs.github.com/en/copilot/how-tos/copilot-cli/customize-copilot/add-skills)
- `instructions/agent-md.instructions.md` — for `.agent.md` agent files
- `instructions/markdown.instructions.md` — base markdown rules
