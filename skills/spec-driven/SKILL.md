---
name: spec-driven
description: |
  Captures a feature specification before implementation begins. Walks
  through user need, behavior, edge cases, success criteria, and
  non-goals. Output is a markdown spec saved to docs/specs/. Used as
  input by /make-plan to decompose into phases. SDD-lite — pragmatic,
  not enterprise.

  Use when the user says: "spec out X", "write a spec for this feature",
  "before we plan, capture the requirements", "what should X do exactly?",
  "RFC for this feature".

  Do NOT use for: small bug fixes, prototypes / spikes, infrastructure
  refactors with no user-facing change.
license: MIT
---

# Spec-Driven Development (SDD-lite)

Captures the WHAT and WHY of a feature before any code is written.
Different from a plan (HOW) — a spec describes the desired behavior,
edge cases, and what success looks like. Output feeds `make-plan`.

## When to use

YES:
- New feature with multi-stakeholder input
- Feature where the team disagrees on what "done" means
- Pre-RFC capture (before broader review)
- API design — agreeing on endpoints / contracts before implementing
- Anything where ambiguity in the spec would cause rework

NO:
- Small fixes / refactors with no behavior change
- Prototypes — by design, you don't know what you're making
- Decisions about technology (use `ultrathink` + `adr-write`)

## The 8 spec sections

Every spec has these 8 sections IN ORDER. Skipping a section means
cutting a corner.

### 1. Problem / motivation

Why does this feature need to exist?

```markdown
## Problem

<2-3 paragraphs.>

What's the user pain or business need? What evidence do we have
(metrics, support tickets, sales feedback)? Why now?

This section answers "if we do nothing, what's the cost?"
```

If you can't answer "why now" → either you don't understand the urgency
or there isn't any. Say so.

### 2. Users / personas

Who is this for?

```markdown
## Users

| Persona | Use case | Frequency |
|---|---|---|
| Sales rep at SMB customer | Generate weekly forecast | Weekly |
| Account manager | Review forecasts, override | Weekly |
| Data analyst | Audit forecast accuracy retroactively | Monthly |

**Primary persona:** Sales rep. Optimize for them; the others are accommodated.
```

Multiple personas with conflicting needs? Make the priority explicit.

### 3. Behavior — what the feature does

This is the largest section. Describe the BEHAVIOR, not the
implementation.

```markdown
## Behavior

### User flow (happy path)

1. User navigates to /forecasts
2. System shows the 4 most recent forecasts (creator, date, status)
3. User clicks "New forecast"
4. System opens a form with prefilled defaults from last forecast
5. User adjusts inputs and clicks "Generate"
6. System runs the forecast (~10s) and shows the result
7. User can: save, share via link, or discard

### Inputs

| Input | Type | Required | Default | Validation |
|---|---|---|---|---|
| Time horizon | enum | yes | 30 days | one of: 7, 30, 90, 365 days |
| Region | string | yes | (user's home region) | one of the registered regions |
| Confidence | float | no | 0.85 | 0.5–0.99 |

### Outputs

The forecast result contains:
- A predicted value (numeric)
- A confidence interval (low + high)
- Top 3 contributing factors with weights
- Last-refresh timestamp
```

### 4. Edge cases

The most-skipped section. Walk through:

```markdown
## Edge cases

### Empty / minimal input
- User submits with no data → show defaults inline; never compute on empty
- User has zero historical forecasts → show empty state with "create your first"

### Concurrency
- User has 2 tabs open, generates in both → second submission gets a
  conflict warning; user picks which to keep

### Failure modes
- Backend returns 5xx → show retry banner, not blank page
- Forecast takes > 30s → show "still working" message, not silent loading
- Result is empty (no historical data to forecast from) → explain why,
  link to data import

### Permissions
- User without forecast-create role → button hidden, direct URL → 403
- User in read-only mode → can view, can't generate

### Large input
- User pastes 10MB of data → reject at the API boundary with clear error
- Forecast over 1000 dimensions → degrade gracefully, show top 100

### Localization
- All labels translatable
- Numeric formats per user locale
- Date formats per user locale
```

If the feature touches an LLM, ALSO add:

```markdown
### LLM-specific

- Out-of-scope query (user asks weather forecast vs sales forecast) →
  refuse politely
- Injection attempt ("ignore instructions") → refuse, log
- Empty response from LLM → retry once, then surface error
- Token cap exceeded → truncate input with warning
- Cost per request → bounded (max $X), abort if exceeded
```

### 5. Success criteria

How do we know it works?

```markdown
## Success criteria

### Quantitative
- p95 generation latency < 5 seconds
- 99% availability
- Forecast accuracy MAPE < 15% on historical backtest
- < 5% of users abandon the form mid-flow (analytics)

### Qualitative
- A new user can generate their first forecast in < 60 seconds
- Sales reps in user testing rate the result as "actionable" 4/5+
- No critical bugs reported in the first 2 weeks of GA

### Non-goals (explicit)
- We do NOT support multi-region forecasts in V1
- We do NOT integrate with external CRM in V1
- We do NOT provide an API for headless forecast generation in V1
```

The "non-goals" section is critical. It prevents scope creep and tells
reviewers what they SHOULDN'T expect.

### 6. Open questions

Things that need to be answered before / during implementation.

```markdown
## Open questions

- [ ] Do we cache results per (user, horizon, region) tuple? (TTL?)
- [ ] What happens to in-flight forecasts during a deploy?
- [ ] Should "share via link" be public-link or only-authenticated?

(Resolve top 2 BEFORE starting Phase 1 of make-plan.)
```

A spec with no open questions is suspect — almost every spec has them.
Listing them is honest, not a weakness.

### 7. Risks

```markdown
## Risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Forecast accuracy < 70% in beta | Medium | High | Run 2-week shadow mode against historical data first |
| LLM cost exceeds $X/month | Low | Medium | Cost guard at request level + monthly budget |
| User overload (too many forecasts) | Low | Low | Rate limit per user; track usage |
```

### 8. Rollout

```markdown
## Rollout

- Phase A (week 1-2): Internal alpha — staff only
- Phase B (week 3-4): Beta — 10% of users with feature flag
- Phase C (week 5+): GA

### Rollback

If we need to disable post-GA:
- Feature flag turns it off without redeploy
- Old `/forecasts` endpoint preserved for 30 days
- Data written to new DB tables remains (no destructive change)

### Telemetry

- Track: form abandonment rate, generation latency, error rate, daily
  usage
- Dashboard: linked here once built
- Alerts: page on-call if error rate > 5% for 5 min
```

## Workflow

### Step 1 — Confirm scope

Before writing:
- What's the feature, in one sentence?
- Who's the primary user?
- What does "done" look like?
- Is anything decided already (tech, UI shape)?

If 2+ unanswered, return BLOCKED. Don't invent.

### Step 2 — Walk the 8 sections in order

Use `assets/spec-template.md`. Don't reorder — the order encodes thinking.

### Step 3 — Be specific in edge cases

Most spec failures are missing edge cases. Force yourself to imagine:
- What's the smallest valid input?
- What's the largest?
- What if two users do conflicting things?
- What if the network breaks?
- What if the user has no permission?
- What if the LLM (if used) returns nothing?

Each gets a sentence.

### Step 4 — Get the non-goals right

Ask the user explicitly: "what's NOT in this feature?" Capture verbatim.
Non-goals are how you make the scope shippable.

### Step 5 — Save and link

Save to `docs/specs/<feature-name>.md`. Update `docs/specs/README.md` (or
create) with an index entry. Output to chat:

- Full spec markdown
- File location
- Recommended next step: "Run `/make-plan` to decompose into phases"

## Configuration

| Parameter | Default | Effect |
|---|---|---|
| `output` | `docs/specs/<feature>.md` | Where to save |
| `format` | `sdd-lite` | Currently only one supported |

## Anti-patterns to flag (in YOUR specs)

1. **Spec describes implementation, not behavior** — "use Redis to cache"
   → that's HOW. Spec is WHAT and WHY. Redis goes in the plan or ADR.
2. **Edge cases section is empty / "TBD"** → not a spec, a wish
3. **No non-goals** → scope creep guaranteed
4. **Success criteria are vague ("works well")** → can't verify
5. **No rollout plan** → ship-and-pray
6. **Personas are abstract ("the user")** → can't optimize for "the user"
7. **Hidden assumptions** ("obviously we'll need an API") → make
   explicit; add to the spec or open question
8. **Spec written after implementation started** → too late; either
   discard or re-spec from current reality

## Spec vs Plan vs ADR — clear roles

| Doc | Captures | When |
|---|---|---|
| **Spec** (this skill) | WHAT + WHY (behavior, success criteria) | Before planning |
| **Plan** (`make-plan`) | HOW (phases, files, order) | After spec |
| **ADR** (`adr-write`) | Technology / pattern decision + tradeoffs | When choosing |

Often: spec → ultrathink (decide on approach) → adr → make-plan → build.

## See also

- `assets/spec-template.md` — the template this skill writes
- `make-plan` skill — to decompose the spec into phases
- `ultrathink` skill — for resolving the open questions
- `adr-write` skill — for capturing the technical decision
