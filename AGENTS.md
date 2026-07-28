# AGENTS.md

Guidance for AI coding agents (GitHub Copilot CLI, and other agentic tools)
working in this repository. The same always-on behavioral guidelines are
mirrored for VS Code Copilot in
[`.github/copilot-instructions.md`](.github/copilot-instructions.md).

## About this repository

`copilot-collection` is a curated set of GitHub Copilot **agents**, **skills**,
**instructions**, **hooks**, and **workflows**. When editing it:

- Artifact authoring rules are file-scoped in [`instructions/`](instructions/) —
  e.g. [`agent-md`](instructions/agent-md.instructions.md),
  [`skill-md`](instructions/skill-md.instructions.md),
  [`markdown`](instructions/markdown.instructions.md). They auto-apply by file
  pattern; follow them.
- New agents and skills must pass CI validation (see [`scripts/`](scripts/) and
  [`.github/workflows/`](.github/workflows/)). Scaffold from
  [`_templates/`](_templates/).
- Knowledge-base files follow the 90-day re-validation protocol in
  [`docs/`](docs/).

## Behavioral guidelines

These four principles apply to every task, in any language or domain. They
counter the most common LLM coding failures: silent wrong assumptions,
overcomplication, touching code outside the task, and coding without verifiable
goals. Use judgment on trivial work — the rigor targets non-trivial changes.

### 1. Think before coding

Don't assume. Don't hide confusion. Surface tradeoffs.

- State assumptions explicitly; ask when a requirement is ambiguous instead of
  guessing.
- Present multiple interpretations when more than one is reasonable.
- Push back when a simpler or safer approach exists.
- Stop and name what's unclear rather than papering over it.

Escalate with [`/explore`](skills/explore/),
[`/spec-driven`](skills/spec-driven/), [`/ultrathink`](skills/ultrathink/), or
[`/make-plan`](skills/make-plan/).

### 2. Simplicity first

Write the minimum code that solves the problem. Nothing speculative.

- No features beyond what was asked; no abstractions for single-use code.
- No unrequested flexibility; no error handling for impossible scenarios.
- If 200 lines could be 50, write the 50.

Would a senior engineer call it overcomplicated? If yes, simplify. Run a focused
pass with [`/simplify`](skills/simplify/).

### 3. Surgical changes

Touch only what you must. Clean up only your own mess.

- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken; match existing style.
- Mention unrelated dead code — don't delete it.
- Remove only the orphans *your* change created.

Every changed line should trace directly to the user's request.

### 4. Goal-driven execution

Define success criteria, then loop until verified.

| Instead of...    | Do this                                                |
| ---------------- | ------------------------------------------------------ |
| "Add validation" | "Write tests for invalid inputs, then make them pass"  |
| "Fix the bug"    | "Write a test that reproduces it, then make it pass"   |
| "Refactor X"     | "Confirm tests pass before and after"                  |

For multi-step work, state a plan with a verification per step:

```
1. [step] → verify: [check]
2. [step] → verify: [check]
```

Use [`/make-plan`](skills/make-plan/) for full plans;
[`/code-review`](skills/code-review/) and
[`/pr-validation-gate`](skills/pr-validation-gate/) before a PR.

## Signals these are working

- Diffs contain only requested changes.
- Clarifying questions arrive before implementation.
- Solutions are simple on the first pass.
- PRs are small and every line maps to the task.
