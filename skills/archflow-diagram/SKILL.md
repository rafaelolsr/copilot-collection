---
name: archflow-diagram
description: |
  Generates ONLY the animated HTML architecture diagram for a codebase
  (no surrounding report, no slide deck) — a single self-contained file
  with zero external dependencies that opens directly in any browser.

  Use when the user says: "just the diagram", "diagram only", "animated
  diagram only", "generate an architecture diagram (no report)", "show
  me the data flow animation", "I only want the diagram", or
  "self-contained diagram".

  Do NOT use for: full architecture reports (use the `archflow` skill),
  slide decks (use `archflow-slides`), static dependency graphs, or
  editing source code.
license: MIT
---

# Archflow — diagram-only mode

This is a thin **dispatcher** skill. It exists to route the user's
diagram-only intent to the main `archflow` workflow with the mode
locked to `DIAGRAM`.

## Workflow

1. Read the sibling skill `../archflow/SKILL.md` and execute its
   7-stage pipeline (ANALYZE → PLAN → BUILD → DELIVER → REVIEW → FIX
   → PRESENT) end-to-end.

2. Force the mode to **DIAGRAM** for every stage. Ignore the
   "REPORT MODE" and "SLIDE MODE" branches.

3. Honor every constraint from the main skill's DIAGRAM-ONLY rules:
   - Output file: `./architecture-diagram.html`
   - Fully self-contained — **zero external dependencies**
   - Self-contained fonts only: `'JetBrains Mono', 'Fira Code', monospace`
   - No Google Fonts CDN, no Mermaid CDN
   - Reference layout examples in `../archflow/assets/templates/`
     (`horizontal-pipeline.html`, `multi-agent-hub.html`,
     `medallion-pipeline.html`) — patterns, not rigid templates

4. Use the same reference docs as the main skill — they live in
   `../archflow/references/`. Read them on demand:
   - `analysis.md`, `layouts.md` in STAGE 1
   - `design-system.md`, `libraries.md`, `design-qa.md`,
     `animation.md` in STAGE 2
   - `svg-exemplar.md` in STAGE 3 as needed
   - `reviewer-agent.md` in STAGE 5

5. Skip report-only references (`report-sections.md`, `navigation.md`)
   and slide-only references (`slide-patterns.md`).

## Output contract

A single `./architecture-diagram.html` file in the current working
directory. After writing, print the absolute path so the user can
open it in a browser.

## Maintenance note

This shim contains **no workflow logic**. All pipeline, design
heuristics, animation, and review rules live in `../archflow/`. To
update the diagram workflow, edit the main `archflow` skill — never
copy logic into this file.

## See also

- `archflow` — main skill, full architecture report (default mode)
- `archflow-slides` — sibling shim, slide-deck mode
