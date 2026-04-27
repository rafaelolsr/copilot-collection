# Regression tracking

> **Last validated**: 2026-04-26
> **Confidence**: 0.91

## Why

Your evals score 4.2/5 average today. Tomorrow you change a prompt — they score 4.0/5. Did it regress? Or is it noise? Without tracked runs, you don't know.

Regression tracking = persisting eval results so you can compare runs over time, attribute changes to specific commits, and detect drift before users do.

## What every run must record

Mandatory fields:

| Field | Why |
|---|---|
| `run_id` | Unique key (UUID, or commit-sha + timestamp) |
| `started_at` / `ended_at` | When |
| `dataset_name` | Which dataset |
| `dataset_hash` | Catches "we updated the dataset and didn't realize" |
| `dataset_version` | Human-readable label (`v3`) |
| `agent_or_target` | What was evaluated |
| `prompt_hash` | Hash of the prompt(s) tested |
| `prompt_version` | Human label (`v2.1`) |
| `model_under_test` | `claude-sonnet-4-5`, etc. |
| `judge_model` | Which judge (if AI-assisted) |
| `git_sha` | Source code commit |
| `cost_usd` | What this run cost |
| `metrics` | Aggregate scores |
| `per_case_results` | Details (or path to detail file) |

Without these, comparing runs is guesswork.

## Aggregate metrics format

```json
{
  "metrics": {
    "groundedness_avg": 4.32,
    "groundedness_pass_rate": 0.87,
    "relevance_avg": 4.51,
    "tool_call_accuracy": 0.93,
    "deterministic_pass_rate": 1.00,
    "total_cases": 100,
    "failed_cases": 13,
    "skipped_cases": 0
  }
}
```

Aggregate AND breakdown. The aggregate is for dashboards; the per-case is for drill-in when something regresses.

## Per-case results

```jsonl
{"case_id":"qa-001","run_id":"r-2026-04-26-abc","groundedness":5,"relevance":5,"tool_call_accuracy":1.0,"actual_answer":"...","passed":true}
{"case_id":"qa-002","run_id":"r-2026-04-26-abc","groundedness":3,"relevance":4,"tool_call_accuracy":0.5,"actual_answer":"...","passed":false,"reason":"missed citation"}
```

Stored in same format whether backend is JSONL, Delta, or SQL.

## Storage backends

### Local JSONL (dev)

```
evals/runs/
├── 2026-04-26_advisor_v2.1_run-abc.jsonl       # per-case
├── 2026-04-26_advisor_v2.1_run-abc.summary.json
└── ...
```

Fast to write, easy to inspect. Use for local iteration.

### Fabric Delta tables (production)

Schema:

```sql
CREATE TABLE eval_runs (
    run_id           STRING,
    started_at       TIMESTAMP,
    ended_at         TIMESTAMP,
    dataset_name     STRING,
    dataset_hash     STRING,
    dataset_version  STRING,
    agent_target     STRING,
    prompt_hash      STRING,
    prompt_version   STRING,
    model_under_test STRING,
    judge_model      STRING,
    git_sha          STRING,
    cost_usd         DOUBLE,
    metrics_json     STRING                        -- json blob
)

CREATE TABLE eval_case_results (
    run_id           STRING,
    case_id          STRING,
    metric_name      STRING,
    metric_value     DOUBLE,
    metric_reason    STRING,
    actual_answer    STRING,
    passed           BOOLEAN
)
```

Use `deltalake` Python library to write (see `patterns/fabric-delta-results-writer.md`).

Query benefits:
- "Show me groundedness over time" — easy SQL / KQL
- Compare runs: "diff scores between two runs by case_id"
- Detect regressions: alert if rolling-avg drops by X%

### Both

Common: write JSONL locally for fast iteration AND push to Fabric for archival on every run that uploads.

## Comparing runs

The fundamental query: are scores in run B significantly worse than run A?

```python
def compare_runs(run_a: RunResult, run_b: RunResult) -> Comparison:
    comparison = {}
    for metric in run_a.metrics:
        a_val = run_a.metrics[metric]
        b_val = run_b.metrics.get(metric)
        if b_val is None:
            continue
        delta = b_val - a_val
        rel_change = delta / a_val if a_val else 0
        comparison[metric] = {
            "a": a_val,
            "b": b_val,
            "delta": delta,
            "rel_change": rel_change,
            "regressed": rel_change < -0.05,    # 5% drop = regression
        }
    return comparison
```

For per-case detail: which cases passed in A but fail in B? That's the actionable diff.

```sql
SELECT a.case_id, a.metric_value AS old_score, b.metric_value AS new_score
FROM eval_case_results a
JOIN eval_case_results b ON a.case_id = b.case_id AND a.metric_name = b.metric_name
WHERE a.run_id = '<old>' AND b.run_id = '<new>'
  AND a.passed = TRUE AND b.passed = FALSE
ORDER BY a.metric_value - b.metric_value DESC
LIMIT 20
```

The 20 cases that regressed most → start of triage.

## Detecting drift

Aggregate scores naturally fluctuate (judge non-determinism). Use rolling average:

```python
last_5_runs = get_last_n_runs(metric="groundedness_avg", n=5)
rolling_avg = sum(r.value for r in last_5_runs) / 5
current = get_latest_run().metrics["groundedness_avg"]
if current < rolling_avg * 0.95:
    alert("Groundedness regression detected")
```

Wider windows = stabler signal. 1-run-vs-1-run is too noisy for AI-assisted metrics.

## Statistical significance

For "did prompt v2 actually beat v1?" run pairwise comparison (see `concepts/llm-as-judge.md`) on the same dataset. Count wins/losses/ties. A confidence interval requires N >= 50–100 cases.

For absolute scores: difference of means with bootstrap or t-test. Most teams skip the formal test and use ≥5% rel-change threshold — pragmatic.

## What to alert on

| Signal | Action |
|---|---|
| Aggregate metric drops >10% vs rolling avg | Page someone |
| Aggregate metric drops 5-10% | Slack channel |
| Specific case starts failing after passing for N runs | Slack channel |
| Eval run cost > 2× rolling avg | Slack (something's wrong with the suite) |
| Eval run takes >2× rolling avg duration | Slack |

Don't alert on every metric drop — judge noise will spam the channel.

## Anti-patterns

- No `run_id` (can't reference a run)
- No `dataset_hash` (silent dataset drift)
- No `prompt_hash` (can't tell what was tested)
- Only aggregates stored, no per-case (can't triage)
- Storing scores from different judge models in the same metric column (apples to oranges)
- No regression alerts (drift detected post-mortem)
- Comparing single runs (judge noise dominates)

## See also

- `concepts/golden-dataset-design.md` — version-tag the dataset
- `concepts/eval-cost-and-cadence.md` — when runs happen
- `patterns/fabric-delta-results-writer.md` — Fabric storage
- `patterns/pytest-eval-runner.md` — how runs are triggered
- `anti-patterns.md` (items 5, 19)
