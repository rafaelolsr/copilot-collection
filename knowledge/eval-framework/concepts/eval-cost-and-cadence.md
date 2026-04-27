# Eval cost & cadence

> **Last validated**: 2026-04-26
> **Confidence**: 0.92

## The cost problem

A 1000-case eval suite with 2 AI-assisted scorers per case costs:
- 2000 LLM calls
- ~$0.005/call (Sonnet) → $10/run
- Runtime: 5–20 minutes

Run on every commit (50/day) = $500/day = $15k/month. Run nightly = $300/month. Same suite, 50× cost difference.

The lever is cadence — match the cost of running to the cost of NOT detecting a regression.

## Cadence tiers

| Tier | Trigger | Suite | Why |
|---|---|---|---|
| Per-commit | Every push | Deterministic only | Free, fast, catches obvious breaks |
| PR validation | PRs touching prompts/agents/tools | Smoke (10–30 cases, AI-assisted) | Block obviously-bad changes |
| Nightly | Cron | Standard (100–300 cases, all evaluators) | Catches gradual drift |
| Release | Manual / pre-deploy | Comprehensive (500+ cases) | Pre-prod gate |
| Production canary | Continuous | Live traffic samples | Real-world drift detection |

## Per-commit (deterministic)

```python
@pytest.mark.parametrize("case", load_cases("smoke.jsonl"))
def test_smoke_deterministic(case):
    answer = run_target(case.input)
    assert is_valid_json(answer, ResponseSchema), f"{case.id}: invalid JSON"
    assert case.expected_id in extract_id(answer), f"{case.id}: missing expected ID"
```

Runs in seconds. Free. Catches: schema changes, broken integrations, obvious prompt errors. Should pass 100%.

## PR validation (smoke AI-assisted)

```python
@pytest.mark.eval
@pytest.mark.smoke
@pytest.mark.parametrize("case", load_cases("smoke_eval.jsonl"))      # 30 cases
async def test_smoke_eval(case, real_judge_client):
    answer = await run_target(case.input)
    score = await groundedness_judge(case.input, answer, case.context, judge=real_judge_client)
    assert score >= 3, f"{case.id}: groundedness {score}/5 < 3"
```

Cost: 30 cases × 1 judge = ~$0.15/run. Runtime: ~1 min. Aggregate threshold optional but useful: ≥80% of cases score ≥4.

## Nightly (full suite)

```python
@pytest.mark.eval
@pytest.mark.full
@pytest.mark.parametrize("case", load_cases("regression.jsonl"))      # 200 cases
async def test_regression(case, real_judge_client):
    answer = await run_target(case.input)
    metrics = await score_all_evaluators(case, answer, judge=real_judge_client)
    write_to_fabric(metrics)
    assert metrics["groundedness"] >= 3, ...
```

Cost: 200 cases × 3 judges = ~$3/run × 30 nights = $90/month. Acceptable for production app.

## Release / pre-deploy

```bash
pytest -m "eval and full" --regression-suite=comprehensive
# Compares to last 5 nightly runs
# Fails if rolling avg drops > 10%
# Outputs comparison report as artifact
```

Cost: ~$10/run, 1–2× per release. Cheap insurance.

## Production canary

Sample N% of real production calls, run an AI-assisted scorer on them async (don't block the user response). Different storage path:

```python
async def production_call(query):
    response = await agent.run(query)
    if random.random() < 0.01:                            # 1% sampling
        asyncio.create_task(score_async(query, response))
    return response

async def score_async(query, response):
    score = await groundedness_judge(query, response.text, response.context)
    await write_to_canary_table(query, response, score)
```

Catches drift that synthetic eval data misses. Use cautiously: sample 1% not 100%.

## Cost guards

Per-run dollar cap:

```python
class CostGuard:
    def __init__(self, limit_usd: float):
        self.limit = limit_usd
        self.spent = 0.0

    def add(self, cost: float):
        self.spent += cost
        if self.spent > self.limit:
            raise BudgetExceeded(f"Eval run exceeded ${self.limit:.2f} budget")

guard = CostGuard(limit_usd=10.0)
# inject into evaluator wrappers; abort if budget exceeded
```

Per-suite weekly cap:

```python
weekly_total = query_fabric_for_eval_costs(last_n_days=7)
if weekly_total > 200:
    skip_eval_run(reason="Weekly budget exceeded")
```

## When to NOT run an eval

- Doc-only changes (no code change)
- README / changelog updates
- Build configuration changes (let CI deal with it)
- Lint / formatting auto-fixes

Use path filters in CI:

```yaml
# GitHub Actions
- uses: dorny/paths-filter@v3
  id: changes
  with:
    filters: |
      eval-relevant:
        - 'src/agents/**'
        - 'src/workflows/modules/*/prompts/**'
        - 'src/tools/**'

- if: steps.changes.outputs.eval-relevant == 'true'
  run: pytest -m "eval and smoke"
```

## Sampling strategies

For a 1000-case dataset, you can:

1. **Run all 1000** every nightly: comprehensive, expensive
2. **Run 100 sampled** every nightly + full 1000 weekly: covers most drift
3. **Run 100 sampled, stratified by tag** (ensure every tag is represented): better than random

Stratified sampling:

```python
def stratified_sample(cases: list, n: int) -> list:
    by_tag = defaultdict(list)
    for case in cases:
        for tag in case.tags:
            by_tag[tag].append(case)
    per_tag = max(1, n // len(by_tag))
    sampled = []
    for tag, tag_cases in by_tag.items():
        sampled.extend(random.sample(tag_cases, min(per_tag, len(tag_cases))))
    return sampled[:n]
```

Pin the random seed to the run date so the same cases run every nightly within a window — comparisons across nights are like-for-like.

## Anti-patterns

- Running full eval suite on every push (cost runaway)
- No cost guards (single bug in a loop = surprise bill)
- No path filters (eval runs on README changes)
- 100% sampling of production for canary (privacy + cost issue)
- Different sampling per run (can't compare runs)
- Skipping evals "because they're slow" without alternative (quality regression goes undetected)

## See also

- `concepts/regression-tracking.md` — what to do with the results
- `patterns/pytest-eval-runner.md` — how markers are wired
- `patterns/fabric-delta-results-writer.md` — where results land
- `anti-patterns.md` (items 4, 11, 16)
