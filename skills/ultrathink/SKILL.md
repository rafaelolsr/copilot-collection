---
name: ultrathink
description: |
  Deep deliberation skill for hard architectural decisions, ambiguous
  requirements, high-stakes refactors, and "why did this fail?" analysis.
  Forces explicit chain-of-reasoning, considers multiple options, weighs
  tradeoffs honestly, and emits structured output.

  Use when the user says: "think hard about this", "deep analysis on...",
  "compare these approaches", "why did this fail?", "what's the right
  abstraction?", "should we use X or Y?", "what are we missing?",
  "this decision matters — don't be glib".

  Do NOT use for: simple lookups, routine code generation, quick fixes,
  syntax questions. The deliberation overhead is wasted on easy problems.
license: MIT
---

# Ultrathink

For decisions that deserve more than a hot take. Forces structured
deliberation: restate, enumerate options, surface tradeoffs, recommend with
justification, name what you're NOT claiming, propose a smallest-step.

## When to use

YES:
- Architectural decisions ("Lakehouse vs Warehouse", "DirectLake vs Import")
- Hard tradeoffs (cost vs latency, simplicity vs flexibility, precision vs recall)
- Root-cause analysis on subtle bugs
- Decision frameworks for the team
- Picking between 3+ libraries / patterns / approaches
- Anything where "let me just do X" might be wrong

NO:
- "How do I import pandas" — just answer
- "Fix this typo" — just fix it
- "Write a function that does X" — just write it
- Anything where deliberation theater would slow down obvious work

The point isn't to LOOK thoughtful. It's to BE thoughtful when stakes warrant it.

## The protocol

For every invocation, emit reasoning in this exact structure. Each section is
load-bearing — skipping a section means cutting a corner.

### 1. RESTATE

Restate the problem in your own words. If the prompt was ambiguous, **stop
here and ask** for clarification before continuing. The wrong answer to the
right question beats the right answer to the wrong question.

What it should include:
- The actual decision being made (often hidden inside a how-to question)
- The constraints (explicit and implicit)
- What success looks like (what would make this decision "right")
- What's NOT being decided (scope boundaries)

If you can't fill all four, the prompt isn't ready. Ask.

### 2. OPTIONS

List **at least 3 distinct approaches**. Each gets a paragraph.

Rules:
- They must be GENUINELY distinct, not three variants of the same idea
- Include "do nothing / keep current state" as one option when it's defensible
- Include the contrarian / weird option even if you'll discard it — it
  surfaces assumptions in the others
- Don't merge options to make the analysis easier

Format:
```
**Option A — <one-line label>**
<paragraph: what it is, how it works, what it costs, what it gives>

**Option B — <one-line label>**
<paragraph>

**Option C — <one-line label>**
<paragraph>
```

If you only have 2 options, you haven't thought hard enough yet. Try
"do nothing" or invert one of the existing options.

### 3. TRADEOFFS

For each option, surface the tradeoffs in 5 dimensions:

| Dimension | What to capture |
|---|---|
| **Cost** | Time, money, complexity, ongoing maintenance |
| **Risk** | What could go wrong; blast radius if it does |
| **Reversibility** | How hard to undo; one-way door vs two-way door |
| **Who wins / who loses** | Different stakeholders weight differently |
| **Failure mode** | When (not if) this option fails, how does it fail |

Most analyses skip "failure mode" and "reversibility". They're the most
useful columns. Don't skip.

Read `references/tradeoff-matrices.md` for templated decision matrices.

### 4. RECOMMENDATION

Pick one option. Justify in 3 sentences max.

Then state: **"What would change my mind?"** — describe the evidence /
condition that would flip your recommendation. If you can't name one, your
recommendation isn't actually based on the analysis; it's a preference
dressed up.

Format:
```
**Recommend: Option B**

<3-sentence justification>

**What would change my mind:** <specific evidence/condition>
```

### 5. WHAT WE'RE NOT SAYING

List 3 things people might infer from your recommendation that you're NOT
claiming. This is the most-skipped section and the most valuable.

Examples:
- "I'm not saying Option A is bad — it's the right choice if X happens"
- "I'm not saying this is permanent — revisit in 6 months when Y is clearer"
- "I'm not saying the team should adopt this universally — narrow to <case>"
- "I'm not claiming benchmarks support this — it's an architectural argument"

Why this matters: recommendations get repeated as commandments. The "not
saying" list reminds future readers what was actually argued.

### 6. NEXT STEP

The smallest concrete action that moves the decision forward. Not the whole
solution. The smallest experiment / decision / artifact that unblocks
progress AND validates the recommendation.

Examples of good next steps:
- "Spike Option B for 2 days against the smallest realistic dataset; benchmark"
- "Open RFC asking team for objections; merge in 1 week if no blockers"
- "Build a 1-page ADR using template; circulate to architecture review"
- "Run Option A in shadow mode against 1% traffic for a week"

Bad next steps (avoid):
- "Decide" — too vague
- "Implement Option B" — too big
- "Ask the team" — what specifically?

## Workflow

1. User invokes `/ultrathink <prompt>`
2. Read `references/decision-frameworks.md` for relevant pre-built frameworks
3. Read `references/tradeoff-matrices.md` for the dimensions to consider
4. Walk through the protocol — sections 1 through 6 in order
5. If RESTATE reveals ambiguity, STOP and ask before continuing
6. Emit structured output — one section per heading, no shortcuts

## Output template

Use this exact structure when emitting:

```markdown
# Ultrathink: <topic>

## Restate

<what's being decided, constraints, success criteria, scope>

## Options

**Option A — <label>**
<paragraph>

**Option B — <label>**
<paragraph>

**Option C — <label>**
<paragraph>

## Tradeoffs

### Option A
- Cost:
- Risk:
- Reversibility:
- Winners / losers:
- Failure mode:

### Option B
<...>

### Option C
<...>

## Recommendation

**Recommend: Option <X>**

<3-sentence justification>

**What would change my mind:** <condition>

## What we're NOT saying

1. <not-claim 1>
2. <not-claim 2>
3. <not-claim 3>

## Next step

<smallest concrete action>
```

## When to abort the protocol

Sometimes deliberation reveals the question is wrong. If during RESTATE or
OPTIONS you realize:

- The decision doesn't actually matter (revisit-able cheaply, low blast radius)
- The decision is premature (need more data before committing)
- The decision is someone else's to make (escalate)

ABORT and say so. Don't fill in 6 sections of theatre to look rigorous.

## See also

- `references/decision-frameworks.md` — reusable frameworks (build vs buy, library selection, etc)
- `references/tradeoff-matrices.md` — dimensions worth considering for common decision types
- `simplify` skill — for refactoring (different mode of analysis)
- `code-review` skill — for PR review (different mode of analysis)
