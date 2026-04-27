# Instructions

Coding standards applied automatically by file pattern. When Copilot is
working on a file matching the pattern, the instruction loads into context
without explicit invocation.

## Directory layout

```
instructions/
├── python.instructions.md
├── tmdl.instructions.md
└── ...
```

Each instruction is a single `.instructions.md` file with frontmatter.

## Frontmatter schema

```yaml
---
name: <name>
description: |
  Coding standards for <language/format>. Auto-applied when Copilot
  works on files matching the pattern.
applyTo: "**/*.py,pyproject.toml"   # glob pattern(s), comma-separated
---
```

Required fields:
- `name` — kebab-case identifier
- `description` — one-line summary
- `applyTo` — file pattern(s) where this loads

## When instructions vs skills?

| Use instruction when... | Use skill when... |
|---|---|
| The advice is universal for that file type | The advice is task-specific |
| It should apply automatically (not on user request) | User explicitly invokes |
| Body is short (<500 lines) | Body needs scripts, multiple references |
| It's about HOW to write code | It's about a WORKFLOW or PROCEDURE |

Examples:
- ✅ Instruction: "Python uses uv, ruff strict, Pydantic v2 for boundaries"
  (applies to every Python file always)
- ✅ Skill: "Simplify recently-changed code"
  (user invokes when they want simplification)

You can have both — `python.instructions.md` keeps Copilot following Python
conventions; `simplify` skill triggers on demand for refactoring passes.

## Body structure

Effective instructions have:

1. **Tooling baseline** — exact tools, version pins
2. **Structural rules** — type hints, layout, naming
3. **Forbidden patterns** — anti-patterns specific to the language
4. **Examples** — short before/after for tricky rules
5. **See-also** — links to relevant skills / agents

## Instructions in this collection

| Instruction | Applies to | Purpose |
|---|---|---|
| `python.instructions.md` | `**/*.py`, `pyproject.toml`, `uv.lock` | uv + ruff + mypy strict + async-first + Pydantic v2 |

## Creating a new instruction

1. Create `instructions/<name>.instructions.md`
2. Set frontmatter with `applyTo` glob
3. Write standards as enforceable rules (not opinions)
4. Add to `instructions/README.md` (this file)

## Multi-language project

A project can have many instructions. They stack:
- `python.instructions.md` for `**/*.py`
- `tmdl.instructions.md` for `**/*.tmdl`
- `pipeline-yaml.instructions.md` for `azure-pipelines*.yml`

Copilot loads ALL matching instructions. Keep them non-conflicting (each
file matches at most one — by design).

## Anti-patterns when writing instructions

- **Subjective preferences as rules** ("I prefer single quotes") — either
  enforce via formatter (objective) or don't enforce
- **Long prose** — rules should be checkable, not philosophical
- **Conflicting with the formatter** — if `ruff format` does it, the
  instruction shouldn't override
- **Restating the language docs** — instructions encode YOUR project's
  choices, not Python language basics
- **Stale tool versions** — if you pin `ruff>=0.6.0`, update the file when
  you bump

## See also

- `instructions/python.instructions.md` — example
- `agents/python-specialist.agent.md` — for deeper Python questions
- `skills/code-review/SKILL.md` — for explicit review (uses these standards)
