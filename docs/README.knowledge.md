# Knowledge bases (KBs)

> **Note**: This is an extension specific to this collection, not part of
> the standard agent-skill-instruction-hook-workflow taxonomy. KBs are
> per-agent reference content, structured for the 90-day re-validation
> cycle.

## What KBs are

Each agent in this collection owns a `references/` directory inside its
`agents/<name>/` folder, containing:

- **index.md** — navigation map; reading protocol for the agent
- **anti-patterns.md** — patterns the agent flags on sight (Wrong/Correct pairs)
- **\_manifest.yaml** — registry of every concept/pattern with confidence + dates
- **quick-reference.md** — decision matrices, common pitfalls
- **concepts/** — domain concepts the agent loads on demand
- **patterns/** — production code templates the agent uses verbatim

KBs differ from skills' `references/`:
- KBs serve ONE specific agent
- KBs follow the validation/staleness protocol
- KBs are large (10-20+ files); skill references are usually 1-3

## Why KBs exist (vs putting everything inline)

Two reasons:

1. **Body size limits** — agent body capped at 30K chars; KB content easily
   exceeds that. Splitting lets the agent load only what's relevant per task.
2. **Re-validation discipline** — KB files have `last_validated:` dates;
   the `kb-revalidate` skill + `kb-staleness-warning` hook enforce the
   90-day cycle. Inline content has nothing to validate against.

## Layout (post-migration)

```
agents/<agent-name>/
├── <agent-name>.agent.md          # the agent file (frontmatter + body)
└── references/
    ├── index.md
    ├── anti-patterns.md
    ├── _manifest.yaml
    ├── quick-reference.md
    ├── concepts/
    │   ├── concept-1.md
    │   └── concept-2.md
    └── patterns/
        ├── pattern-1.md
        └── pattern-2.md
```

The agent body references files by relative path:

```markdown
On every invocation, read `references/index.md` first. For each concept
relevant to the task, read `references/concepts/<name>.md`. For patterns,
read `references/patterns/<name>.md`. Check `references/anti-patterns.md`
when reviewing user code.
```

## Required files per KB

| File | Purpose |
|---|---|
| `index.md` | Navigation table linking all concepts/patterns; reading protocol with source URLs |
| `anti-patterns.md` | One section per anti-pattern with Wrong/Correct code blocks |
| `_manifest.yaml` | Machine-readable registry: every file with confidence + last_validated |
| `quick-reference.md` | Cheat-sheet: decision matrices, common pitfalls table |
| `concepts/*.md` | Foundational ideas (≤150 lines each) |
| `patterns/*.md` | Production templates (≤200 lines each) |

## Validation protocol

Every KB file has a header:

```markdown
> **Last validated**: 2026-04-26
> **Confidence**: 0.92
> **Source**: https://learn.microsoft.com/en-us/azure/foundry/
```

The 90-day rule:
- After 90 days: file is stale → run `kb-revalidate` skill
- Sources used during re-validation come from `index.md`'s "Reading Protocol"
- Date update mandatory; confidence may drop if disagreement found

The `kb-staleness-warning` hook fires at session start to nag.

## Creating a new KB

When adding a new specialist agent, follow the
`_templates/AGENT_CREATION_PROMPT_COPILOT.md` template — it includes the KB
generation step.

For agents in this collection, KBs were generated using the agent generator
with the 7 required files + 6-8 concepts + 6-8 patterns each.

## Sync with private projects

Agents originate in private projects (e.g., the Foundry project) where they
prove their value. The `scripts/sync.sh` script syncs agents (with their
KBs) between the private project and this public collection.

```bash
# Pull latest from private into collection (after the agent has matured)
scripts/sync.sh pull /path/to/private-project ms-foundry-specialist

# Push collection updates back to private
scripts/sync.sh push /path/to/private-project ms-foundry-specialist
```

Before this collection migrated to the agents/<name>/references/ layout,
KBs lived at top-level `knowledge/<domain>/`. The script handles both
layouts during sync.

## Anti-patterns when writing KBs

- **Stale dates without re-reading** — `last_validated` bumped without
  actually checking the source. Defeats the protocol.
- **Concepts > 150 lines** — split into multiple files.
- **Patterns > 200 lines** — same.
- **Anti-patterns without Wrong/Correct pairs** — be concrete; readers
  shouldn't infer the fix.
- **Cross-references to nonexistent files** — `validate.sh` catches this.
- **Generic content (random LLM SDK examples in a Foundry KB)** — substitution
  kills the KB's value. Domain-specific or omit.
- **Confidence inflation** — claim 0.99 confidence on PREVIEW features.
  Be honest; lower confidence = signal for re-validation priority.

## Confidence calibration

| Confidence | Meaning |
|---|---|
| 0.95+ | GA features, recently validated against authoritative source |
| 0.85-0.95 | GA features, not recently validated |
| 0.75-0.85 | PREVIEW features, validated |
| 0.50-0.75 | Inferred / partial source verification |
| <0.50 | `[NEEDS REVIEW: ...]` flag in the file |

## See also

- `skills/kb-revalidate/SKILL.md` — the re-validation procedure
- `hooks/kb-staleness-warning/` — the nag mechanism
- `_templates/AGENT_CREATION_PROMPT_COPILOT.md` — generate new agents+KBs
- `scripts/validate.sh` — checks KB structure (cross-refs, placeholders, etc.)
