# Eval harness with pytest + parametrize + mock LLM

> **Last validated**: 2026-04-26
> **Confidence**: 0.91

## When to use this pattern

You have an LLM-driven feature (extractor, agent, summarizer) and want to test:
- Wiring (does the feature call the LLM correctly?) — fast unit tests with mocks
- Quality (does the LLM produce acceptable output on real inputs?) — slower evals with real API

This pattern handles both with one fixture set, runnable independently via `pytest -m`.

## File layout

```
tests/
├── conftest.py                  # shared fixtures
├── unit/
│   └── test_extractor.py        # fast, mocked
└── eval/
    ├── golden_invoices.jsonl    # version-controlled dataset
    └── test_extractor_eval.py   # slow, real API
```

## conftest.py

```python
"""Shared pytest fixtures."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest


@pytest.fixture
def mock_anthropic_client() -> AsyncMock:
    """A drop-in replacement for AsyncAnthropic for unit tests."""
    client = AsyncMock()
    client.messages.create.return_value = MagicMock(
        id="msg_test",
        type="message",
        role="assistant",
        model="claude-sonnet-4-5",
        content=[MagicMock(type="text", text="mocked response")],
        stop_reason="end_turn",
        usage=MagicMock(
            input_tokens=10,
            output_tokens=5,
            cache_read_input_tokens=0,
            cache_creation_input_tokens=0,
        ),
    )
    return client


@pytest.fixture(scope="session")
def real_anthropic_client():
    """Real client for evals. Skips test if API key is missing."""
    import anthropic
    key = os.getenv("ANTHROPIC_API_KEY")
    if not key:
        pytest.skip("ANTHROPIC_API_KEY not set; skipping live eval")
    return anthropic.AsyncAnthropic(api_key=key, timeout=60.0)


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
```

## Unit test (fast, mocked)

```python
"""tests/unit/test_extractor.py"""
import pytest
from src.extractor import InvoiceExtractor

@pytest.mark.asyncio
async def test_extractor_calls_llm_once(mock_anthropic_client):
    extractor = InvoiceExtractor(client=mock_anthropic_client)
    await extractor.extract("Invoice INV-001 for $99")
    assert mock_anthropic_client.messages.create.call_count == 1


@pytest.mark.asyncio
async def test_extractor_passes_correct_model(mock_anthropic_client):
    extractor = InvoiceExtractor(client=mock_anthropic_client, model="claude-sonnet-4-5")
    await extractor.extract("test")
    call_kwargs = mock_anthropic_client.messages.create.call_args.kwargs
    assert call_kwargs["model"] == "claude-sonnet-4-5"


@pytest.mark.asyncio
async def test_extractor_handles_empty_text(mock_anthropic_client):
    extractor = InvoiceExtractor(client=mock_anthropic_client)
    with pytest.raises(ValueError, match="empty"):
        await extractor.extract("")
```

## Eval test (slow, real API, parametrized over golden cases)

```python
"""tests/eval/test_extractor_eval.py"""
from pathlib import Path
import pytest
from src.extractor import InvoiceExtractor
from tests.conftest import load_jsonl

CASES = load_jsonl(Path(__file__).parent / "golden_invoices.jsonl")


@pytest.mark.eval
@pytest.mark.asyncio
@pytest.mark.parametrize("case", CASES, ids=lambda c: c["id"])
async def test_extractor_eval(case, real_anthropic_client):
    extractor = InvoiceExtractor(client=real_anthropic_client)
    result = await extractor.extract(case["input"])

    expected = case["expected"]
    # Strict matches where deterministic
    assert result.invoice_number == expected["invoice_number"], (
        f"{case['id']}: got {result.invoice_number!r}, expected {expected['invoice_number']!r}"
    )
    # Tolerance for floats
    assert abs(result.total - expected["total"]) < 0.01, (
        f"{case['id']}: got {result.total}, expected {expected['total']}"
    )


@pytest.mark.eval
@pytest.mark.asyncio
async def test_extractor_eval_pass_rate(real_anthropic_client):
    """Aggregate metric: ≥85% pass on the dataset."""
    extractor = InvoiceExtractor(client=real_anthropic_client)
    total, passed = 0, 0
    for case in CASES:
        total += 1
        try:
            result = await extractor.extract(case["input"])
            if result.invoice_number == case["expected"]["invoice_number"]:
                passed += 1
        except Exception:
            pass
    pass_rate = passed / total
    assert pass_rate >= 0.85, f"Pass rate {pass_rate:.2%} below 85% threshold"
```

## Golden dataset format

```jsonl
{"id": "simple-1", "input": "Invoice INV-12345 from Acme for $99.99", "expected": {"invoice_number": "INV-12345", "vendor": "Acme", "total": 99.99}}
{"id": "multi-line", "input": "Invoice INV-99999 issued 2026-04-01...", "expected": {"invoice_number": "INV-99999", "total": 1500.00}}
{"id": "tricky-currency", "input": "Total: USD 1,500.00 on INV-77777", "expected": {"invoice_number": "INV-77777", "total": 1500.00}}
```

Keep it in version control. Add cases as you find production failures (regression tests).

## pyproject.toml configuration

```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
markers = [
    "eval: stochastic evals (slow, costs $)",
    "integration: requires Azure / external services",
]
addopts = "-v --strict-markers"
```

## Run patterns

```bash
# Default CI: fast unit tests only
pytest -m "not eval and not integration"

# Nightly eval CI
pytest -m eval --tb=short

# Single case during debugging
pytest tests/eval/test_extractor_eval.py -k "tricky-currency"
```

## LLM-as-judge for subjective output

For prose / summaries where exact match doesn't apply:

```python
from src.judge import score_with_judge  # uses a separate model to score

@pytest.mark.eval
@pytest.mark.asyncio
async def test_summary_quality(case, real_anthropic_client, judge_client):
    summary = await summarizer.summarize(case["text"], client=real_anthropic_client)
    score = await score_with_judge(
        client=judge_client,
        rubric="Rate 1-5 on accuracy and concision.",
        text=case["text"],
        candidate=summary,
    )
    assert score >= 4, f"Judge scored {score}/5 on {case['id']}"
```

## Done when

- Unit tests run in <5s with no network
- Evals run on demand (not by default in CI)
- Golden dataset is in version control
- Pass-rate threshold is explicit, not "100%"
- Failures print enough context to debug without re-running

## Anti-patterns

- Calling real API by default (running `pytest` charges money)
- `assert result == expected` on stochastic prose output
- No `id` on parametrized cases (test names become opaque)
- Test functions over 30 lines (split into fixtures)
- Sleep-and-poll instead of `pytest.fixture(scope="session")` for setup
- No tolerance on float comparisons (`==` on amounts)

## See also

- `concepts/testing-llm-code.md` — full taxonomy of test types
- `patterns/anthropic-client-async-wrapper.md` — injectable client to mock
- `anti-patterns.md` (items 18, 19)
