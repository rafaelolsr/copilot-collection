---
name: agentic-eval
description: |
  Adds evaluation capability to an existing agent or pipeline. Walks through
  designing the eval suite (deterministic + AI-assisted + agentic metrics),
  building the golden dataset, wiring the runner, and setting up regression
  tracking. Specific to the eval-framework patterns used in this collection
  (pytest markers, Fabric Delta backend, Azure AI Evaluation SDK).

  Use when the user says: "add evals to this agent", "design an eval suite
  for X", "how do I evaluate this prompt change?", "set up regression
  tracking for the agent", "I need golden data for this".

  Do NOT use for: writing the agent's prompts (different skill), training a
  model (out of scope), running existing evals (just `pytest -m eval`).
license: MIT
---

# Agentic Eval

Pragmatic walk-through for adding eval coverage to an LLM-based feature.
Built on the patterns this collection's `eval-framework-specialist` agent
already maintains — pytest harness + golden datasets + Fabric Delta
regression tracking + Azure AI Evaluation SDK for built-in metrics.

This skill is the GUIDED workflow. The agent is the deep specialist. Skill
gets you 80% of the way; agent handles the deep cases.

## When to use

YES:
- New agent / pipeline going to production
- Existing prompt about to change in a way you can't manually verify
- "We've never evaluated this; let's start"
- Migrating from ad-hoc eyeballing to systematic regression tracking

NO:
- Tuning a model (different problem; needs training-data work)
- Writing the prompts themselves (different skill)
- Just running existing evals (no new design needed)

## The 5-step design walk

### Step 1 — Define what "good" means

Before building anything, answer:

1. **What's the unit of evaluation?** A single response? A multi-turn convo?
   A whole agent run with tool calls?
2. **What signal would tell you this got worse?** Specific behaviors that
   matter — not just "quality dropped".
3. **What's measurable?** Outcome match? Format compliance? Tool sequence?
   Subjective rating?
4. **What threshold means "ship it"?** "≥85% pass on golden", "avg
   groundedness ≥4/5", "tool accuracy ≥95%"?

If you can't answer these in one sentence each, the eval will be theatre.
Stop and clarify with the user before continuing.

### Step 2 — Pick metric types

Use the cheapest possible metric that captures the signal:

| Signal | Metric type | Cost / case |
|---|---|---|
| Returns valid JSON matching schema | Deterministic (Pydantic validate) | $0 |
| Contains required entity / number | Deterministic (regex / substring) | $0 |
| Calls expected tool | Deterministic (introspect trace) | $0 |
| Refuses out-of-scope input | Deterministic (regex on refusal phrases) | $0 |
| Answer is grounded in context | AI-assisted (groundedness judge) | ~$0.005 |
| Answer is relevant | AI-assisted (relevance judge) | ~$0.005 |
| Answer is "helpful" | AI-assisted (LLM-as-judge) | ~$0.005 |
| Conversation is coherent | Agentic (whole-transcript judge) | ~$0.01 |

**Order**: deterministic gates first (cheap, fast), AI-assisted second
(when criterion is genuinely fuzzy), agentic last (when unit is multi-step).

### Step 3 — Build the golden dataset

Format: JSONL, one case per line. Required fields:

```jsonl
{"id":"qa-001","input":"...","expected":"...","tags":["happy-path","quantitative"]}
```

Sizing:
- **Smoke (PR validation)**: 20-30 cases
- **Standard (nightly)**: 100-300 cases
- **Comprehensive (release)**: 500-2000 cases

Distribution rule of thumb:
- ~70% happy-path cases (typical user inputs)
- ~20% ambiguous / multi-step cases
- ~10% failure-mode cases (out-of-scope, adversarial, malformed)

Sourcing in priority order:
1. **Manual** — start here. 30 cases hand-written from real user requests.
2. **Production logs** (anonymized) — adds realistic distribution
3. **Failure modes from incidents** — every prod incident becomes a case
4. **LLM-generated adversarial** — for breadth (curate by hand)

Read `references/dataset-templates.md` for shapes per agent type.

### Step 4 — Wire pytest harness

Use the project's existing pytest setup. Add markers if not present:

```toml
# pyproject.toml
[tool.pytest.ini_options]
markers = [
    "eval: stochastic evals (slow, costs $)",
    "smoke: smoke-test eval subset (~30 cases)",
    "full: full eval suite (~200 cases)",
]
```

Skill template for a new eval test:

```python
import pytest
from .conftest import smoke_cases, real_judge_client
from src.agents.<agent_name> import run

@pytest.mark.eval
@pytest.mark.smoke
@pytest.mark.asyncio
@pytest.mark.parametrize("case", smoke_cases, ids=lambda c: c["id"])
async def test_smoke(case, real_judge_client, results_writer, run_metadata):
    answer = await run(case["input"])

    # Deterministic gate
    assert answer.is_valid_json, f"{case['id']}: invalid JSON"

    # AI-assisted score
    score = await groundedness_judge(
        question=case["input"],
        answer=answer.text,
        context=answer.retrieved_context,
        client=real_judge_client,
    )

    results_writer.record(
        run_id=run_metadata["run_id"],
        case_id=case["id"],
        metric="groundedness",
        value=score,
    )

    assert score >= 3, (
        f"{case['id']}: groundedness {score}/5 < 3.\n"
        f"  Question: {case['input']}\n"
        f"  Answer: {answer.text[:300]}"
    )
```

Run with:
```bash
pytest -m "eval and smoke"           # smoke evals (PR-time)
pytest -m "eval and full"            # full evals (nightly)
```

See the `eval-framework-specialist` agent's `patterns/pytest-eval-runner.md`
for a full conftest.

### Step 5 — Add regression tracking

Two options for storage:

**Option A — Local JSONL (start here)**

```python
# evals/conftest.py
@pytest.fixture(scope="session")
def results_writer(run_metadata):
    path = Path(f"evals/runs/{run_metadata['run_id']}.jsonl")
    return JsonlResultsWriter(path)
```

Fast, no infra. Each run produces a JSONL file. Compare runs manually.

**Option B — Fabric Delta (production)**

For team visibility + time-series in Power BI:

```python
@pytest.fixture(scope="session")
def results_writer(run_metadata):
    return FabricDeltaResultsWriter(
        runs_table_path=os.environ["EVAL_FABRIC_RUNS_TABLE_PATH"],
        case_results_table_path=os.environ["EVAL_FABRIC_CASES_TABLE_PATH"],
        storage_options=fabric_storage_options(),
    )
```

See the `eval-framework-specialist` agent's
`patterns/fabric-delta-results-writer.md` for the schema.

## Output of this skill

When you finish walking through, deliver:

1. **`evals/dataset/<agent>_golden.jsonl`** — golden cases
2. **`evals/test_<agent>_eval.py`** — pytest test
3. **`evals/conftest.py`** (or addition to existing) — fixtures
4. **`evals/scorers.py`** (or addition to existing) — judge functions
5. **README addendum**: how to run evals, expected pass rate, who to ping if breaking

## Decision: Azure AI Evaluation SDK or roll-your-own?

Use **Azure AI Evaluation SDK** when:
- You want built-in evaluators (groundedness, relevance, coherence, content-safety)
- You want Foundry portal integration
- The metrics fit standard rubrics

Roll-your-own when:
- Domain-specific scoring (e.g., "is this DAX valid AND idiomatic?")
- Tight integration with custom infra
- Avoiding the SDK dependency

Most projects: **mix both**. Built-ins for groundedness/relevance + custom
for domain quality.

## Cost guard

Add a per-run cost cap before running anything against a real API:

```python
class CostGuard:
    def __init__(self, limit_usd: float):
        self.limit = limit_usd
        self.spent = 0.0

    def add(self, cost: float):
        self.spent += cost
        if self.spent > self.limit:
            raise BudgetExceeded(f"Eval run exceeded ${self.limit}")
```

Default: $5/run for smoke, $20/run for nightly. Adjust to project budget.

## Common mistakes when designing evals

1. **No tolerance band** — `assert score == 5` fails 30% of runs even on
   good code. Use ≥4 with pass-rate threshold.
2. **Same model judging itself** — built-in self-bias. Use a different model
   tier (Opus judging Sonnet output, etc.).
3. **All happy-path cases** — passes 100%, reveals nothing. Need failure
   modes.
4. **No regression baseline** — first run is just noise. Need 3+ runs to
   establish baseline before scoring "regression".
5. **Running on every commit** — 1000-case eval × 50 commits/day = $$$. Use
   marker-gated cadence (smoke on PR, full nightly).
6. **Tracking only aggregates** — when scores drop, you need PER-CASE data
   to triage. Always store per-case.

## Cadence rule of thumb

| Tier | Trigger | Suite | Cost / run |
|---|---|---|---|
| Per-commit | Every push | Deterministic only | $0 |
| PR | PR touching prompts/agents | Smoke (30 cases, AI-assisted) | $0.50-1 |
| Nightly | Cron | Standard (200 cases) | $5-15 |
| Release | Pre-deploy | Comprehensive (500+ cases) | $20-50 |

## See also

- `eval-framework-specialist` agent — for deep design / debugging
- `references/dataset-templates.md` — golden dataset shapes per agent type
- `scripts/seed_failure_modes.py` — generate adversarial cases
