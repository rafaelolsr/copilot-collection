# Copilot behavioral guidelines

Always-on engineering principles for this repository. These apply to every task
regardless of language or domain, and complement the file-scoped standards in
[`instructions/`](../instructions/) and the procedural skills in
[`skills/`](../skills/).

They exist to counter four well-documented LLM coding failure modes: making
silent wrong assumptions, overcomplicating solutions, touching code outside the
task, and coding without verifiable success criteria.

For trivial work (typo fixes, obvious one-liners) use judgment — not every
change needs the full rigor. These rules bias toward caution over speed on
non-trivial work.

## 1. Think before coding

Don't assume. Don't hide confusion. Surface tradeoffs.

- State assumptions explicitly. If a requirement is ambiguous, ask rather than
  guess — use the `ask_user` form, not a silent decision.
- Present multiple interpretations when more than one is reasonable; don't pick
  one silently and run with it.
- Push back when a simpler or safer approach exists. Say so before implementing.
- Stop when confused. Name what's unclear instead of papering over it.

For deeper work, escalate to a skill: [`/explore`](../skills/explore/) to map
unfamiliar code, [`/spec-driven`](../skills/spec-driven/) to capture
requirements, [`/ultrathink`](../skills/ultrathink/) to reason through a hard
decision, [`/make-plan`](../skills/make-plan/) to decompose a multi-step task.

## 2. Simplicity first

Write the minimum code that solves the problem. Nothing speculative.

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or configurability that wasn't requested.
- No error handling for impossible scenarios.
- If 200 lines could be 50, write the 50.

The test: would a senior engineer call this overcomplicated? If yes, simplify.
After a change lands, [`/simplify`](../skills/simplify/) does a focused pass for
duplication, dead code, and premature abstraction.

## 3. Surgical changes

Touch only what you must. Clean up only your own mess.

- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match the existing style, even if you'd do it differently.
- If you notice unrelated dead code, mention it — don't delete it.

When your edits create orphans, remove the imports, variables, and functions
that *your* change made unused. Leave pre-existing dead code unless asked.

The test: every changed line traces directly to the user's request.

## 4. Goal-driven execution

Define success criteria, then loop until verified.

Transform imperative tasks into verifiable goals:

| Instead of...    | Do this                                                |
| ---------------- | ------------------------------------------------------ |
| "Add validation" | "Write tests for invalid inputs, then make them pass"  |
| "Fix the bug"    | "Write a test that reproduces it, then make it pass"   |
| "Refactor X"     | "Confirm tests pass before and after"                  |

For multi-step work, state a brief plan with a verification per step:

```
1. [step] → verify: [check]
2. [step] → verify: [check]
3. [step] → verify: [check]
```

Strong, checkable criteria let the loop run independently. For full plans use
[`/make-plan`](../skills/make-plan/); before opening a PR, run
[`/code-review`](../skills/code-review/) and
[`/pr-validation-gate`](../skills/pr-validation-gate/).

## Signals these are working

- Diffs contain only requested changes — no drive-by edits.
- Clarifying questions arrive before implementation, not after a mistake.
- Solutions are simple on the first pass instead of after a rewrite.
- PRs are small and every line maps to the task.
