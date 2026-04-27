# pytest eval runner

> **Last validated**: 2026-04-26
> **Confidence**: 0.93

## When to use this pattern

Wiring eval suites into pytest so that:
- Unit tests run on every commit (fast, no API calls)
- Smoke evals run on PRs touching prompts (~30 cases, AI-assisted)
- Full evals run nightly (~200 cases)
- All driven by markers (`-m "eval and smoke"`)

## pyproject.toml configuration

```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests", "evals"]
markers = [
    "eval: stochastic evals (slow, costs $)",
    "smoke: smoke-test eval subset (fast, ~30 cases)",
    "full: full eval suite (slow, ~200 cases)",
    "integration: requires Azure / external services",
]
addopts = "-v --strict-markers"
```

## Conftest with shared fixtures

```python
# evals/conftest.py
from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest


@pytest.fixture(scope="session")
def real_judge_client():
    """Live judge client. Skips test if API key missing."""
    import anthropic
    key = os.getenv("ANTHROPIC_JUDGE_API_KEY") or os.getenv("ANTHROPIC_API_KEY")
    if not key:
        pytest.skip("Judge API key not set; skipping live eval")
    return anthropic.AsyncAnthropic(api_key=key, timeout=60.0)


@pytest.fixture(scope="session")
def real_target_client():
    """Live client for the agent under test."""
    import anthropic
    key = os.getenv("ANTHROPIC_API_KEY")
    if not key:
        pytest.skip("Target API key not set")
    return anthropic.AsyncAnthropic(api_key=key, timeout=60.0)


@pytest.fixture
def mock_target_client():
    """Mock for unit tests."""
    client = AsyncMock()
    client.messages.create.return_value = MagicMock(
        content=[MagicMock(type="text", text="mocked")],
        usage=MagicMock(input_tokens=10, output_tokens=5),
    )
    return client


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip() and not line.strip().startswith("//")]


@pytest.fixture(scope="session")
def dataset_dir() -> Path:
    return Path(__file__).parent / "dataset"


@pytest.fixture(scope="session")
def smoke_cases(dataset_dir) -> list[dict[str, Any]]:
    return load_jsonl(dataset_dir / "smoke.jsonl")


@pytest.fixture(scope="session")
def regression_cases(dataset_dir) -> list[dict[str, Any]]:
    return load_jsonl(dataset_dir / "regression.jsonl")


def dataset_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:12]


@pytest.fixture(scope="session")
def run_metadata(dataset_dir) -> dict[str, Any]:
    """Metadata recorded with every run."""
    return {
        "run_id": f"r-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}-{os.urandom(3).hex()}",
        "started_at": datetime.now(timezone.utc).isoformat(),
        "git_sha": os.getenv("GITHUB_SHA") or os.getenv("BUILD_SOURCEVERSION") or "local",
        "dataset_smoke_hash": dataset_hash(dataset_dir / "smoke.jsonl"),
        "dataset_regression_hash": dataset_hash(dataset_dir / "regression.jsonl"),
    }
```

## Smoke eval test

```python
# evals/test_smoke_groundedness.py
import pytest
from src.agents.advisor import advisor_ask
from .scorers import groundedness_judge

@pytest.mark.eval
@pytest.mark.smoke
@pytest.mark.asyncio
@pytest.mark.parametrize("case", "smoke_cases", indirect=True, ids=lambda c: c["id"])
async def test_groundedness_smoke(case, real_target_client, real_judge_client, run_metadata, results_writer):
    answer_obj = await advisor_ask(client=real_target_client, question=case["input"])
    score = await groundedness_judge(
        question=case["input"],
        answer=answer_obj.text,
        context=answer_obj.retrieved_context,
        judge_client=real_judge_client,
    )
    results_writer.record(
        run_id=run_metadata["run_id"],
        case_id=case["id"],
        metric="groundedness",
        value=score,
    )
    assert score >= 3, (
        f"{case['id']}: groundedness {score}/5 < 3.\n"
        f"Question: {case['input']}\n"
        f"Answer: {answer_obj.text[:300]}"
    )
```

The `parametrize` indirect trick: pass the fixture name to fetch the dataset.

## Aggregate-threshold test

A separate test that runs after individual cases:

```python
@pytest.mark.eval
@pytest.mark.smoke
@pytest.mark.asyncio
async def test_smoke_aggregate_pass_rate(real_target_client, real_judge_client, smoke_cases, run_metadata):
    """≥80% of smoke cases score ≥4 on groundedness."""
    scores = []
    for case in smoke_cases:
        answer = await advisor_ask(client=real_target_client, question=case["input"])
        s = await groundedness_judge(
            question=case["input"],
            answer=answer.text,
            context=answer.retrieved_context,
            judge_client=real_judge_client,
        )
        scores.append(s)

    pass_rate = sum(1 for s in scores if s >= 4) / len(scores)
    assert pass_rate >= 0.80, (
        f"Aggregate groundedness pass rate {pass_rate:.2%} below 80% threshold "
        f"(scores: {scores})"
    )
```

## Results writer fixture

```python
# evals/conftest.py (continued)
import json
from pathlib import Path

class JsonlResultsWriter:
    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._fp = self.path.open("a")

    def record(self, **fields: Any) -> None:
        self._fp.write(json.dumps(fields) + "\n")
        self._fp.flush()

    def close(self):
        self._fp.close()


@pytest.fixture(scope="session")
def results_writer(run_metadata):
    path = Path("evals/runs") / f"{run_metadata['run_id']}.jsonl"
    writer = JsonlResultsWriter(path)
    yield writer
    writer.close()
```

For Fabric Delta: replace `JsonlResultsWriter` with `FabricDeltaResultsWriter` (see `patterns/fabric-delta-results-writer.md`).

## Run patterns

```bash
# Default CI: deterministic only — fast, no $
pytest -m "not eval and not integration"

# PR validation: smoke evals
pytest -m "eval and smoke"

# Nightly
pytest -m "eval and full"

# Release: everything
pytest -m "eval"

# Single case during debugging
pytest evals/test_smoke_groundedness.py -k "qa-042" -v
```

## Pipeline integration

GitHub Actions:

```yaml
# .github/workflows/eval-pr.yml
name: PR Eval Smoke

on:
  pull_request:
    paths:
      - 'src/agents/**'
      - 'src/workflows/modules/*/prompts/**'
      - 'src/tools/**'
      - 'evals/**'

jobs:
  smoke-eval:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v3
      - run: uv sync
      - run: uv run pytest -m "eval and smoke" --tb=short
        env:
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
          ANTHROPIC_JUDGE_API_KEY: ${{ secrets.ANTHROPIC_JUDGE_API_KEY }}
      - if: always()
        uses: actions/upload-artifact@v4
        with:
          name: eval-results
          path: evals/runs/
```

Azure DevOps equivalent in `.azuredevops/pr-eval.yml`.

## Common bugs

- Forgot to set `asyncio_mode = "auto"` → every test needs `@pytest.mark.asyncio`
- `parametrize` over a fixture without `indirect=True` (fixture not invoked)
- Real client used in unit tests (CI charges $) — use `mock_target_client`
- `results_writer` scoped per-test instead of session — file rewrites on every test
- Test ID not derived from case ID (`ids=lambda c: c["id"]`) → opaque test names
- `pytest -m eval` runs smoke + full — pre-decide which by adding `and smoke` / `and full`

## See also

- `concepts/eval-cost-and-cadence.md` — when to run which marker
- `concepts/regression-tracking.md` — what `results_writer` writes
- `patterns/custom-deterministic-evaluator.md` — for unit-tier evals
- `patterns/custom-ai-assisted-evaluator.md` — for the judge function
- `anti-patterns.md` (items 4, 5, 16)
