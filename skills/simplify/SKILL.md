---
name: simplify
description: |
  Reviews recently changed code for reuse, clarity, and over-engineering.
  Identifies and proposes fixes for: duplicated logic (DRY violations),
  dead code, unnecessary indirection, premature generalization, magic
  numbers, unclear names, deep nesting.

  Use when the user says: "simplify this", "clean up", "review my changes
  for simplification", "is this over-engineered?", "DRY check", "remove
  the cruft", "what can I delete here?".

  Do NOT use for: full architectural review (use code-review skill),
  security audit, performance optimization, designing a new feature.
license: MIT
allowed-tools: [shell]
---

# Simplify

A focused refactoring pass on recently changed code. Strips over-engineering,
removes duplication, flattens unnecessary structure. Preserves behavior.

## When to use

- After implementing a feature, before opening a PR
- During code review, when something "feels" too complex
- When refactoring legacy modules touched by a change

When NOT to use:
- For brand-new green-field design (use code-review or system-design)
- For performance optimization (different criteria — clarity loses to speed
  sometimes)
- For security review (different criteria — defense in depth often
  intentionally redundant)

## Workflow

### Step 1 — Scope the diff

Run `git diff` (or equivalent) to identify the files changed since the
last clean commit. Limit analysis to those files plus their immediate
dependencies.

```bash
git diff --name-only HEAD~1                 # last commit
git diff --name-only main...HEAD            # whole branch
```

Do not propose changes to files NOT in the diff unless they have an obvious
duplicated pattern with a changed file (in which case, mention but don't
modify them in the same pass — flag for follow-up).

### Step 2 — Read the canon checklist

For each changed file, read `references/code-smells.md` and walk through
the categories:

1. **Duplication** — same logic appearing 2+ times
2. **Dead code** — unreachable branches, unused params, never-called functions
3. **Premature abstraction** — interface/class with one implementation
4. **Magic numbers / strings** — literals that should be named constants
5. **Deep nesting** — 4+ levels of indentation
6. **Long parameter lists** — 5+ params, especially when most go together
7. **Unclear naming** — names that require comments to understand
8. **Mixed levels of abstraction** — one function doing high-level + low-level work
9. **Over-defensive code** — `if x is None or x == "" or len(x) == 0` redundancy
10. **Comment cruft** — comments explaining what code already says clearly

### Step 3 — Categorize findings

Each finding goes in one of three buckets:

- **`fix`** — obvious improvement, low risk, ready to apply
- **`propose`** — improvement requires judgment; show before/after, ask user
- **`flag`** — pattern is suspect but might be intentional; document, don't fix

Don't bulk-apply. Most simplifications are judgment calls.

### Step 4 — Apply the safe ones

For each `fix`:
1. Show the diff snippet
2. Apply the edit
3. Move to next finding

For each `propose`:
1. Show before/after side by side
2. Explain the tradeoff (what gets simpler, what might be lost)
3. Wait for user confirmation

For each `flag`:
1. Add a `# NOTE:` comment with what's suspicious
2. Don't modify code

### Step 5 — Verify behavior preserved

After applying fixes, run the test suite (or at least lint + type-check).
If any test breaks, REVERT the offending change and re-flag it as `propose`.

```bash
# Adapt to project — check pyproject.toml / package.json for actual command
pytest -m "not eval"
ruff check
mypy src/
```

If tests don't exist for the touched code: emit a finding flagging this AS
the highest-priority simplification (untested code resists refactoring).

### Step 6 — Emit summary

```
SIMPLIFY REPORT
================
files_touched:
  - path/to/file.py:  3 fixes, 1 propose, 0 flags
  - path/to/other.py: 0 fixes, 2 proposes, 1 flag

deletions:    -47 lines
additions:    +18 lines
net:          -29 lines

categories_hit:
  - duplication: 2
  - magic-numbers: 1
  - premature-abstraction: 1

needs_review:
  - <propose-1 description>
  - <propose-2 description>

flagged_for_followup:
  - <flag description>

tests_pass: yes
```

## Anti-patterns to avoid (in YOUR simplification work)

The skill itself can over-simplify. Watch for:

1. **Inlining a thing that's about to be reused** — Rule of Three. Inline only if currently single-use AND no plausible second use in 1-month horizon.
2. **Removing comments that explain WHY** — comments documenting reasoning, business rules, or quirks are NOT cruft. Remove only comments restating WHAT the code does.
3. **Flattening a guard clause that has explanatory power** — sometimes the early return IS the documentation.
4. **Replacing a clear name with a shorter unclear one** — `for_each_active_user` is better than `feau`, even if longer.
5. **DRY-ing two superficially-similar things that aren't really duplication** — same shape, different reasons. Keep separate.
6. **Removing abstraction that isolates change** — sometimes a thin wrapper exists to absorb future API drift. Document and keep.

## Configuration parameters

The skill accepts these from the user prompt:

| Parameter | Default | Effect |
|---|---|---|
| `scope` | "diff vs main" | What to analyze. Options: "diff vs HEAD~1", "diff vs main", "specific file paths" |
| `aggressive` | false | If true, applies `propose` items without asking |
| `categories` | "all" | Limit to specific smell categories |
| `max_changes_per_file` | 5 | Cap so reviews don't get unwieldy |

Example invocation:
```
/simplify scope="diff vs main" categories="duplication,magic-numbers"
```

## See also

- `references/code-smells.md` — full smell catalog
- `scripts/find_duplicates.py` — helper to identify duplication mechanically
- `code-review` skill — for full PR review (broader scope)
