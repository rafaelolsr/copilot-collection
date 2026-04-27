# Fabric Delta results writer

> **Last validated**: 2026-04-26
> **Confidence**: 0.86
> **Source**: https://delta.io/, https://learn.microsoft.com/en-us/fabric/onelake/

## When to use this pattern

You want eval results in a Fabric Lakehouse for cross-team visibility, time-series analysis in Power BI / KQL, and historical archival. Replaces local JSONL files (or runs alongside them).

## Schema

Two tables — runs (one row per run) and case-results (many rows per run):

### `eval_runs` table

| Column | Type | Notes |
|---|---|---|
| `run_id` | string | Primary key |
| `started_at` | timestamp | UTC |
| `ended_at` | timestamp | UTC |
| `dataset_name` | string | e.g., `advisor_qa_smoke` |
| `dataset_hash` | string | sha256[:12] |
| `dataset_version` | string | Human label |
| `agent_target` | string | e.g., `advisor-v2` |
| `prompt_hash` | string | sha256[:12] of the prompt content |
| `prompt_version` | string | e.g., `v2.1` |
| `model_under_test` | string | e.g., `claude-sonnet-4-5` |
| `judge_model` | string | e.g., `claude-opus-4-1` |
| `git_sha` | string | Source commit |
| `cost_usd` | double | Total dollars spent |
| `total_cases` | long | |
| `passed_cases` | long | |
| `failed_cases` | long | |
| `metrics_json` | string | JSON blob — all aggregate metrics |

### `eval_case_results` table

| Column | Type |
|---|---|
| `run_id` | string |
| `case_id` | string |
| `metric_name` | string |
| `metric_value` | double |
| `metric_reason` | string |
| `passed` | boolean |
| `recorded_at` | timestamp |

Long-format (one row per metric per case) makes querying easy:
- "groundedness over time": filter `metric_name='groundedness'`, group by `run_id`
- "cases that regressed": pivot/join two `run_id`s

## Writer implementation

```python
"""Fabric Delta writer for eval results."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pyarrow as pa
from deltalake import write_deltalake


class FabricDeltaResultsWriter:
    """Append-only writer to Fabric Lakehouse Delta tables."""

    def __init__(
        self,
        *,
        runs_table_path: str,                                # abfss:// or file://
        case_results_table_path: str,
        storage_options: dict[str, str] | None = None,
    ) -> None:
        self._runs_path = runs_table_path
        self._cases_path = case_results_table_path
        self._storage_options = storage_options or {}
        self._buffered_cases: list[dict[str, Any]] = []
        self._run_started_at = datetime.now(timezone.utc)

    def record_case(
        self,
        *,
        run_id: str,
        case_id: str,
        metric_name: str,
        metric_value: float,
        metric_reason: str = "",
        passed: bool = True,
    ) -> None:
        self._buffered_cases.append({
            "run_id": run_id,
            "case_id": case_id,
            "metric_name": metric_name,
            "metric_value": float(metric_value),
            "metric_reason": metric_reason or "",
            "passed": bool(passed),
            "recorded_at": datetime.now(timezone.utc),
        })

    def finalize_run(
        self,
        *,
        run_id: str,
        dataset_name: str,
        dataset_hash: str,
        dataset_version: str,
        agent_target: str,
        prompt_hash: str,
        prompt_version: str,
        model_under_test: str,
        judge_model: str | None,
        git_sha: str,
        cost_usd: float,
        total_cases: int,
        passed_cases: int,
        failed_cases: int,
        metrics: dict[str, Any],
    ) -> None:
        # Flush case results
        if self._buffered_cases:
            cases_table = pa.Table.from_pylist(self._buffered_cases)
            write_deltalake(
                self._cases_path,
                cases_table,
                mode="append",
                storage_options=self._storage_options,
            )
            self._buffered_cases.clear()

        # Write run row
        run_row = {
            "run_id": run_id,
            "started_at": self._run_started_at,
            "ended_at": datetime.now(timezone.utc),
            "dataset_name": dataset_name,
            "dataset_hash": dataset_hash,
            "dataset_version": dataset_version,
            "agent_target": agent_target,
            "prompt_hash": prompt_hash,
            "prompt_version": prompt_version,
            "model_under_test": model_under_test,
            "judge_model": judge_model or "",
            "git_sha": git_sha,
            "cost_usd": float(cost_usd),
            "total_cases": int(total_cases),
            "passed_cases": int(passed_cases),
            "failed_cases": int(failed_cases),
            "metrics_json": json.dumps(metrics),
        }
        runs_table = pa.Table.from_pylist([run_row])
        write_deltalake(
            self._runs_path,
            runs_table,
            mode="append",
            storage_options=self._storage_options,
        )
```

## Authentication to Fabric Lakehouse

Use managed identity / `DefaultAzureCredential`. The `deltalake` library accepts storage options:

```python
from azure.identity import DefaultAzureCredential

cred = DefaultAzureCredential()
token = cred.get_token("https://storage.azure.com/.default").token

storage_options = {
    "bearer_token": token,
    "use_fabric_endpoint": "true",
}

writer = FabricDeltaResultsWriter(
    runs_table_path="abfss://workspace@onelake.dfs.fabric.microsoft.com/lakehouse.Lakehouse/Tables/eval_runs",
    case_results_table_path="abfss://workspace@onelake.dfs.fabric.microsoft.com/lakehouse.Lakehouse/Tables/eval_case_results",
    storage_options=storage_options,
)
```

For tokens that may expire mid-run, refresh between calls:

```python
def fresh_storage_options() -> dict[str, str]:
    token = cred.get_token("https://storage.azure.com/.default").token
    return {"bearer_token": token, "use_fabric_endpoint": "true"}

writer._storage_options = fresh_storage_options()           # before each write
```

## Wiring to pytest

```python
# evals/conftest.py
@pytest.fixture(scope="session")
def fabric_results_writer(run_metadata):
    use_fabric = os.getenv("EVAL_FABRIC_ENABLED") == "1"
    if not use_fabric:
        return JsonlResultsWriter(Path(f"evals/runs/{run_metadata['run_id']}.jsonl"))

    cred = DefaultAzureCredential()
    storage_options = {
        "bearer_token": cred.get_token("https://storage.azure.com/.default").token,
        "use_fabric_endpoint": "true",
    }
    writer = FabricDeltaResultsWriter(
        runs_table_path=os.environ["EVAL_FABRIC_RUNS_TABLE_PATH"],
        case_results_table_path=os.environ["EVAL_FABRIC_CASES_TABLE_PATH"],
        storage_options=storage_options,
    )
    yield writer
    # Finalize at end of session — pytest_sessionfinish hook is also an option
```

`record_case` is called per case during tests; `finalize_run` is called once at session end (use `pytest_sessionfinish` in `conftest.py` or a session-scoped fixture finalizer).

## Querying for trends

In Fabric SQL endpoint:

```sql
-- Groundedness over time
SELECT
    started_at::date as run_date,
    AVG(JSON_VALUE(metrics_json, '$.groundedness_avg')) as groundedness
FROM eval_runs
WHERE dataset_name = 'advisor_qa'
  AND started_at > DATEADD(day, -30, GETDATE())
GROUP BY started_at::date
ORDER BY run_date DESC;
```

```sql
-- Cases that regressed between two runs
WITH old AS (
    SELECT case_id, AVG(metric_value) as old_score
    FROM eval_case_results
    WHERE run_id = '<previous>' AND metric_name = 'groundedness'
    GROUP BY case_id
),
new AS (
    SELECT case_id, AVG(metric_value) as new_score
    FROM eval_case_results
    WHERE run_id = '<current>' AND metric_name = 'groundedness'
    GROUP BY case_id
)
SELECT old.case_id, old.old_score, new.new_score, (new.new_score - old.old_score) as delta
FROM old JOIN new USING (case_id)
WHERE new.new_score < old.old_score - 1
ORDER BY delta;
```

## Optimization tips

- `OPTIMIZE` the Delta tables periodically (compacts small files)
- `VACUUM` to remove old versions (default 7 days retention)
- Partition by `dataset_name` if you run many independent eval suites
- Z-ORDER by `run_id` for fast filter

```sql
OPTIMIZE eval_case_results ZORDER BY (run_id, case_id);
VACUUM eval_runs RETAIN 168 HOURS;
```

## Anti-patterns

- Writing per-case in append mode without batching (small files explode)
- Not refreshing the bearer token on long runs (auth expires)
- Storing `metrics_json` as actual nested struct (less query-friendly than JSON-in-string)
- No `dataset_hash` (can't tell when dataset changed)
- Mixing test data and prod data in the same Lakehouse without separation
- Schema evolution without migration plan (new column → break readers)

## See also

- `concepts/regression-tracking.md` — what to record + why
- `patterns/pytest-eval-runner.md` — how the writer is wired
- `concepts/eval-cost-and-cadence.md` — when runs happen
- `anti-patterns.md` (items 5, 19)
