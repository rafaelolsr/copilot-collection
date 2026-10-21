---
name: archflow-walkthrough
description: |
  Generates a step-by-step, rule-by-rule data-flow walkthrough for a
  codebase — a self-contained HTML page that narrates ONE flow end to
  end: how data is ingested, then each pipeline stage block-by-block,
  with a sample record that morphs stage-by-stage and the exact
  transformation rules annotated inline (mask, cast, dedup, SCD2 merge,
  quarantine-on-fail). Silver-layer rules are shown in full, not
  summarized.

  Use when the user says: "walk me through the data flow", "explain how
  the data transforms", "step by step", "rule by rule", "show every
  pipeline step", "how does data move from source to the end base",
  "explain the ingestion and transformation rules", or "show what
  changes the data as it moves to the silver layer".

  Do NOT use for: full architecture reports (use the `archflow` skill),
  diagram-only output (use `archflow-diagram`), slide decks (use
  `archflow-slides`), static dependency graphs, or editing source code.
license: MIT
---

# Archflow — walkthrough mode

This is a thin **dispatcher** skill. It exists to route the user's
"walk me through the data flow" intent to the main `archflow` workflow
with the mode locked to `WALKTHROUGH`.

## Workflow

1. Read the sibling skill `../archflow/SKILL.md` and execute its
   7-stage pipeline (ANALYZE → PLAN → BUILD → DELIVER → REVIEW → FIX
   → PRESENT) end-to-end.

2. Force the mode to **WALKTHROUGH** for every stage. Ignore the
   "REPORT MODE", "DIAGRAM MODE", and "SLIDE MODE" branches.

3. Honor every constraint from the main skill's WALKTHROUGH MODE rules:
   - Output file: `./architecture-walkthrough.html`
   - External deps allowed: Google Fonts CDN
   - **STAGE 1 (ANALYZE):** also run analysis.md STEP 3c — extract the
     transformation rules per stage (type, stoplight status, before/
     after field, code_ref), the ingestion mechanism, and a sample
     record to morph through the pipeline. Code-first.
   - **STAGE 2 (PLAN):** plan the spine as the RECORD'S JOURNEY, not the
     subsystems. If STEP 3c produced a GAPS block, present it and PAUSE
     for the user before writing any HTML — this is the only mode that
     stops for input mid-pipeline.
   - **STAGE 3 (BUILD):** pinned SVG pipeline + a rule-annotated
     transition per stage (record morph + stoplight rule chips +
     collapsed engineer cards with code_ref), driven by BOTH autoplay
     and scroll. Silver rules shown in full; unknown rules become GAP
     chips, never dropped.

4. Use the same reference docs as the main skill — they live in
   `../archflow/references/`. Read them on demand:
   - `analysis.md` (incl. STEP 3c), `layouts.md` in STAGE 1
   - `walkthrough.md`, `design-system.md`, `libraries.md`,
     `design-qa.md`, `animation.md` in STAGE 2
   - `svg-exemplar.md` in STAGE 3 as needed
   - `reviewer-agent.md` in STAGE 5 (run the walkthrough-only checks)
   - Reference example: `../archflow/assets/templates/walkthrough-pipeline.html`

5. Skip report-only references (`report-sections.md`, `navigation.md`)
   and slide-only references (`slide-patterns.md`).

## Output contract

A single `./architecture-walkthrough.html` file in the current working
directory. After writing, print the absolute path so the user can open
it in a browser. Confirm: the ingestion mechanism is named, every stage
transition is present, and every extracted rule is rendered as a chip
with a code reference (no silent truncation).

## Maintenance note

This shim contains **no workflow logic**. All pipeline, design
heuristics, animation, the rule-annotated-transition primitive, and
review rules live in `../archflow/`. To update the walkthrough
workflow, edit the main `archflow` skill or the walkthrough-specific
reference (`../archflow/references/walkthrough.md`) — never copy logic
into this file.

## See also

- `archflow` — main skill, full architecture report (default mode)
- `archflow-diagram` — sibling shim, diagram-only mode
- `archflow-slides` — sibling shim, slide-deck mode
