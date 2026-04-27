---
name: make-plan
description: |
  Creates a detailed phased implementation plan for a feature or task.
  Decomposes the work into ordered phases, each with concrete steps,
  files to touch, tests to write, and explicit definition-of-done.
  Output is a markdown plan that can be reviewed before execution and
  later consumed by an executor agent or human contributor.

  Use when the user says: "plan this feature", "make a plan for X",
  "break this down into phases", "what's the implementation plan?",
  "I want to refactor X — plan the work first".

  Do NOT use for: deciding whether to do something (use ultrathink),
  designing the architecture (use system-design skill / agent), one-off
  small fixes (just do them).
license: MIT
---

# Make Plan

Decomposes a feature, refactor, or migration into ordered phases with
concrete steps. Output is a markdown plan that's reviewable BEFORE any
code is written. Reduces the "I started coding and 3 days in I realized
this needs 5 more things" failure mode.

## When to use

YES:
- New feature spanning 3+ files
- Refactor that touches a module / package
- Migration with many small steps (DB schema, dependency upgrade, framework swap)
- Anything where you'd want a teammate to understand the order before merging

NO:
- One-line fixes
- Quick spike / experiment (just do the spike)
- Pure architecture decisions (use `ultrathink` or `adr-write`)
- Tasks where the steps are obvious and small (don't bureaucratize work)

## Workflow

### Step 1 — Understand the goal

Before planning, confirm:
- What is the desired end state?
- What's the current state?
- What constraints exist (deadlines, team availability, blast radius)?
- What's NOT in scope?

If the user gives a vague prompt ("plan the auth refactor"), STOP and
ask. Don't invent the goal.

### Step 2 — Discover the codebase

Use the `read` and `search` tools to understand:
- Files / modules currently implementing the related logic
- Tests that cover the area
- Dependencies on this code from elsewhere
- Configuration / env vars that need to change
- Documentation that references the current behavior

This is the most-skipped step. A plan without discovery is fiction.

### Step 3 — Identify phases

A phase is a chunk of work that:
- Has a clear definition-of-done
- Can be committed and merged independently (where possible)
- Doesn't break anything mid-phase if interrupted
- Builds on the previous phase

Typical phase shapes:

| Phase type | Purpose |
|---|---|
| **Setup / scaffolding** | New directories, dependencies, config files |
| **Add new code (parallel to old)** | Feature flag controlled; old code still works |
| **Migrate existing code** | Switch consumers from old to new |
| **Remove old code** | Cleanup once new path is proven |
| **Tests** | Often interleaved with code phases |
| **Documentation** | Final phase; updates README, ADRs, runbooks |

### Step 4 — For each phase, write

For every phase:

```markdown
## Phase N: <name>

**Goal:** <one sentence>

**Files to touch:**
- `path/to/file1.py` (modify)
- `path/to/file2.py` (create)
- `path/to/test_file.py` (create)

**Steps:**
1. <concrete action>
2. <concrete action>
3. <concrete action>

**Definition of done:**
- [ ] <verifiable check 1>
- [ ] <verifiable check 2>
- [ ] All existing tests still pass
- [ ] New tests added for new behavior

**Rollback:**
<one sentence on how to undo if this phase has issues>

**Risks:**
- <known risk + mitigation>

**Estimated time:** <small / medium / large> — be honest
```

### Step 5 — Verify the order

After drafting all phases, ask:

1. Could phase 3 fail in a way that breaks phase 1's deliverable? Reorder.
2. Is phase 2 actually two phases? Split.
3. Could phases 4 and 5 run in parallel? Note it.
4. Does any phase depend on something not in the plan? Add a "Phase 0:
   prerequisites" or call it out.

### Step 6 — Add the meta sections

The plan also needs:

```markdown
## Overview

**What we're building:** <2-3 sentences>
**Why:** <link to ADR / issue / RFC>
**Scope:** <in scope / out of scope>

## Open questions

- [ ] <question 1>
- [ ] <question 2>

(Anything that needs decision before / during execution. Resolve before
starting Phase 1 if possible.)

## Risks (cross-phase)

- <risk that spans phases + mitigation>

## Success criteria

How we know the WHOLE plan is done:
- <metric or behavior>
- <metric or behavior>
```

### Step 7 — Save and link

Save to `docs/plans/<feature-name>.md` (or wherever the project keeps
plans — check first). Output the plan to chat AND save the file. Include:

- The full plan markdown
- A summary line: total phases, estimated time, files touched
- Pointer to where it was saved

## Output format

```markdown
# Plan — <feature name>

## Overview

**What we're building:** ...
**Why:** ...
**Scope:** ...

## Open questions

- [ ] ...

## Phase 1: <name>
...

## Phase 2: <name>
...

## Phase N: <name>
...

## Risks (cross-phase)

- ...

## Success criteria

- ...
```

## Configuration

Parameters from the user prompt:

| Parameter | Default | Effect |
|---|---|---|
| `output` | `docs/plans/<feature>.md` | Where to save |
| `format` | `phased` | Currently only one supported |
| `discovery_depth` | `medium` | How thoroughly to explore the codebase first |

## Anti-patterns to flag (in YOUR plans)

1. **Plan without discovery** — listing "implement X" without ever
   reading the existing X. The plan is fiction.
2. **Phases that are too big** — "Phase 1: build the feature" → split.
   A phase you can't complete in one sitting is two phases.
3. **No definition-of-done per phase** → impossible to verify completion.
4. **No rollback note** → when phase 3 breaks, no path back.
5. **Open questions hidden in phases** → put them at the top so they
   block before work starts.
6. **Underestimating** — "small" for everything → reviewers stop trusting
   estimates. If a phase is large, say so.
7. **Skipping the cross-phase risks** — risks that ONLY emerge across
   phases (e.g., "the DB migration in Phase 2 makes the rollback in
   Phase 5 destructive") → call them out.
8. **Plan too detailed** — step-by-step keystrokes for each phase →
   becomes obsolete the moment requirements shift. Plan the SHAPE,
   not the keystrokes.

## When to abort planning

If discovery (Step 2) reveals:
- The current state is significantly different from what the user
  described
- Doing this is a bad idea (prerequisite missing, hidden cost)
- A simpler approach exists

ABORT and report. Don't plan around bad assumptions.

## See also

- `ultrathink` skill — for deciding WHETHER to do this (not how)
- `adr-write` skill — to record the decision once made
- `explore` skill — for discovery in unfamiliar codebases
- `spec-driven` skill — for capturing the full spec before planning
