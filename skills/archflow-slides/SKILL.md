---
name: archflow-slides
description: |
  Generates an architecture slide deck for a codebase — a scroll-snap
  HTML presentation with the animated architecture diagram as a hero
  slide, plus supporting slides for components, data flow, external
  services, and insights. Navigate with arrow keys, Page Up/Down, or
  swipe gestures.

  Use when the user says: "create a slide deck", "architecture slides",
  "presentation of the architecture", "scroll-snap presentation", "make
  slides explaining this codebase", "deck for the architecture", or
  "slide-style architecture overview".

  Do NOT use for: full architecture reports (use the `archflow` skill),
  diagram-only output (use `archflow-diagram`), static dependency graphs,
  or editing source code.
license: MIT
---

# Archflow — slide-deck mode

This is a thin **dispatcher** skill. It exists to route the user's
slide-deck intent to the main `archflow` workflow with the mode
locked to `SLIDES`.

## Workflow

1. Read the sibling skill `../archflow/SKILL.md` and execute its
   7-stage pipeline (ANALYZE → PLAN → BUILD → DELIVER → REVIEW → FIX
   → PRESENT) end-to-end.

2. Force the mode to **SLIDES** for every stage. Ignore the
   "REPORT MODE" and "DIAGRAM MODE" branches.

3. Honor every constraint from the main skill's SLIDE MODE rules:
   - Output file: `./architecture-slides.html`
   - External deps allowed: Google Fonts CDN
   - **Chunked generation with per-chunk review** in STAGE 3 (BUILD):
     5–7 slides per chunk, BUILD → REVIEW → FIX per chunk, then
     assemble + FINAL REVIEW for cross-chunk issues
   - Scroll-snap navigation, arrow keys, Page Up/Down, swipe
   - Animated architecture diagram is the hero slide

4. Use the same reference docs as the main skill — they live in
   `../archflow/references/`. Read them on demand:
   - `analysis.md`, `layouts.md` in STAGE 1
   - `design-system.md`, `libraries.md`, `design-qa.md`,
     `animation.md`, `slide-patterns.md` in STAGE 2
   - `svg-exemplar.md` in STAGE 3 as needed
   - `reviewer-agent.md` in STAGE 5

5. Skip report-only references (`report-sections.md`, `navigation.md`).

## Output contract

A single `./architecture-slides.html` file in the current working
directory. After writing, print the absolute path so the user can
open it in a browser. Confirm the slide count matches the
navigation dots.

## Maintenance note

This shim contains **no workflow logic**. All pipeline, design
heuristics, animation, slide patterns, and review rules live in
`../archflow/`. To update the slide-deck workflow, edit the main
`archflow` skill or the slide-specific reference
(`../archflow/references/slide-patterns.md`) — never copy logic
into this file.

## See also

- `archflow` — main skill, full architecture report (default mode)
- `archflow-diagram` — sibling shim, diagram-only mode
