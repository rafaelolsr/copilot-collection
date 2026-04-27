---
name: adr-write
description: |
  Authors an Architectural Decision Record (ADR) for a technical decision.
  Walks through context, considered options, decision, consequences, and
  references in a numbered, immutable record. Output goes to docs/adr/
  (configurable). Forces explicit tradeoff analysis and "what would change
  this decision" criteria.

  Use when the user says: "write an ADR for this", "document this
  decision", "we chose X over Y, capture it", "ADR for the database
  switch", "record why we picked Lakehouse".

  Do NOT use for: brainstorming options (use ultrathink instead),
  documenting code patterns (use a regular doc), recording per-PR
  rationale (use the PR description).
license: MIT
---

# ADR Write

Captures architectural decisions in a permanent, numbered record. ADRs
are immutable (don't edit; supersede with a new ADR). They explain WHY
a decision was made, not just what was decided.

## When to write an ADR

YES:
- Choosing between technologies (Lakehouse vs Warehouse, Postgres vs
  MongoDB, REST vs GraphQL)
- Architectural patterns (microservices vs monolith, event-driven vs
  request-response)
- Cross-cutting policy (auth strategy, retry policy, logging format)
- Reversible decisions worth documenting because the alternatives are
  worth remembering
- Decisions that future contributors will look at and ask "why?"

NO:
- Coding style (use linter / instructions instead)
- Per-PR rationale (use PR description)
- Brainstorming alternatives (use `ultrathink` skill first; capture in
  ADR after deciding)
- Trivial reversible decisions (file naming, log level)

The bar: would a new team member, looking at the codebase 1 year from
now, ask "why did they do it this way?" If yes → ADR.

## Format — MADR-lite

This skill uses a stripped-down MADR (Markdown Architectural Decision
Records) format:

```markdown
# ADR-NNNN — <decision title>

- Status: <proposed | accepted | superseded by ADR-NNNN | deprecated>
- Date: YYYY-MM-DD
- Deciders: @name1, @name2
- Tags: <comma, separated, tags>

## Context

<1-3 paragraphs: what problem are we solving? what constraints? what's
the bigger picture this decision sits in?>

## Considered options

1. **Option A — <one-line label>**
   <one paragraph: what it is, key tradeoffs>

2. **Option B — <one-line label>**
   <one paragraph>

3. **Option C — <one-line label>**
   <one paragraph>

## Decision

We chose **Option <X>** because <3-sentence justification>.

## Consequences

### Positive
- <what gets better>

### Negative
- <what we accept as cost>

### Neutral
- <what doesn't change but is worth noting>

## What would change this decision

<specific evidence / condition that would prompt revisit. If you can't
name one, the decision is preference, not analysis.>

## References

- <link to discussion thread, RFC, prototype, benchmark>
- <link to related ADRs>
```

## Workflow

### Step 1 — Find the next ADR number

```bash
ls docs/adr/ 2>/dev/null | grep -oE 'ADR-[0-9]+' | sort -V | tail -1
# Increment by 1; pad to 4 digits → ADR-0001, ADR-0042, ADR-1234
```

If `docs/adr/` doesn't exist, the user hasn't started yet. Create it
and start with `ADR-0001`.

### Step 2 — Confirm scope with the user

Before writing:
- What's the decision?
- What are the options being considered?
- Has it already been made (you're documenting), or is this proposed?
- Who decided / who's deciding?

If not all answered, return BLOCKED and ask. Don't invent options.

### Step 3 — If options haven't been deliberated yet, route to ultrathink

If the user is still deciding (not yet decided): suggest:

> "This sounds like a decision you're still making. The `/ultrathink`
> skill is designed for that — it walks tradeoff analysis. Once you've
> decided, come back here to record it as an ADR."

ADRs are for RECORDING decisions. Use `ultrathink` to MAKE them.

### Step 4 — Read the template

Read `assets/adr-template.md` and fill in based on user-provided context.

### Step 5 — Be honest in "Considered options"

The "Considered options" section often gets sanitized — only the chosen
one looks reasonable. Don't do this. The point of an ADR is to remember
WHY the rejected options were rejected.

For each option, write:
- What it actually is
- Real tradeoffs (cost, complexity, risk, lock-in)
- Concrete reason it wasn't chosen — not "less elegant"

### Step 6 — Write a meaningful "What would change this decision"

This section is the most-skipped and most valuable. Describe:
- A specific metric crossing a threshold (e.g., "if our daily query
  volume exceeds 1M, revisit Lakehouse vs Warehouse")
- A new technology becoming GA
- A change in team / org constraints
- A failure mode of the chosen option that would prompt a switch

If you can't name one, the decision wasn't actually made on analysis.

### Step 7 — Save and link

Save to `docs/adr/ADR-NNNN-<kebab-case-title>.md`. Update
`docs/adr/README.md` (or create) with an index entry.

## Configuration

Parameters from the user prompt:

| Parameter | Default | Effect |
|---|---|---|
| `path` | `docs/adr/` | Where to save |
| `template` | `assets/adr-template.md` | Override template |
| `format` | `madr-lite` | Currently only one supported |
| `status` | `accepted` | One of: proposed, accepted, superseded, deprecated |

Example invocation:

```
/adr-write title="Use Microsoft Foundry instead of raw Azure OpenAI" \
           status="accepted" \
           path="docs/adr/"
```

## Output template structure

After running, deliver:

1. **The ADR file**: `docs/adr/ADR-NNNN-<title>.md`
2. **Index entry** in `docs/adr/README.md` (created if needed)
3. **Brief summary** in chat: number, title, key tradeoff, where to find it

## Anti-patterns to flag (in YOUR ADRs)

1. **One-option ADR** — "we considered the chosen option and it was good"
   → not an analysis; you didn't think
2. **Sanitized rejected options** — every alternative is described as
   weak so the chosen one wins by default → biased history
3. **No "what would change this"** → you can't tell future-you when to
   revisit
4. **Vague consequences** — "improved scalability" → state the metric
   that improves, by how much
5. **Editing existing ADRs** — ADRs are immutable. To change a decision:
   create a NEW ADR with status "supersedes ADR-NNNN" and update the old
   one's status to "superseded by ADR-MMMM"
6. **Tagging "proposed" forever** — proposed ADRs that don't move to
   accepted within ~2 weeks should be either accepted or rejected
7. **Missing date** — ADRs without dates are hard to chronologize
8. **Code in the ADR** — code goes in implementation; ADR is rationale.
   At most: a 5-line snippet showing the key API decision

## See also

- `assets/adr-template.md` — the template this skill writes
- `references/adr-examples.md` — sample ADRs for inspiration
- `ultrathink` skill — for DECIDING (this skill is for RECORDING)
- [MADR spec](https://adr.github.io/madr/) — the format we lite-ify
- [Documenting Architecture Decisions](https://cognitect.com/blog/2011/11/15/documenting-architecture-decisions) — Michael Nygard's original essay
