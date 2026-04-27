# Testing LLM-integrated code

> **Last validated**: 2026-04-26
> **Confidence**: 0.92
> **Source**: https://docs.pytest.org/en/stable/

## Two distinct test types

LLM code needs both, and they answer different questions:

| Type | Question answered | Hits real LLM? | When to run |
|---|---|---|---|
| Deterministic / unit | "Does my code wire things correctly?" | NO — mock the LLM | Every commit, fast |
| Stochastic / eval | "Does the LLM give acceptable answers on real inputs?" | YES — expensive | PRs touching prompts, nightly |

If you only do unit tests, you can ship a broken prompt that passes CI. If you only do evals, every CI run costs $5 and takes 20 minutes. Both.

## Deterministic tests with mocks

Use `unittest.mock` or `pytest-mock` to replace the LLM client:

```python
import pytest
from unittest.mock import AsyncMock
from anthropic.types import Message

@pytest.fixture
def mock_anthropic_client() -> AsyncMock:
    client = AsyncMock()
    client.messages.create.return_value = Message(
        id="msg_test",
        type="message",
        role="assistant",
        model="claude-sonnet-4-5",
        content=[{"type": "text", "text": "mocked response"}],
        stop_reason="end_turn",
        usage={"input_tokens": 10, "output_tokens": 5},
    )
    return client

@pytest.mark.asyncio
async def test_extracts_invoice(mock_anthropic_client):
    extractor = InvoiceExtractor(client=mock_anthropic_client)
    result = await extractor.extract("some text")
    assert result.amount > 0
    mock_anthropic_client.messages.create.assert_called_once()
```

Key points:
- Use **dependency injection** so the client is replaceable. Code that calls `Anthropic()` inline is untestable.
- Return realistic mock objects (use the SDK's actual response types, not raw dicts) — catches type errors at test time.
- One assertion per behavior. If the test fails, the message tells you what broke.

## Cassettes — recording real API responses

For higher-fidelity testing without paying every run, record real responses once and replay them:

```python
# pytest-recording or vcrpy
@pytest.mark.vcr
@pytest.mark.asyncio
async def test_real_extraction():
    client = anthropic.AsyncAnthropic()
    extractor = InvoiceExtractor(client=client)
    result = await extractor.extract("invoice for $99.99")
    assert result.amount == 99.99
```

First run hits the API and records to a YAML file. Subsequent runs replay from the file — fast and free. Re-record when prompts change.

## Stochastic evals

For eval suites you need:

1. **A golden dataset** — input + expected output (or expected properties of output). Spreadsheet, JSONL, whatever — keep it in version control.
2. **A scorer** — exact match for closed-set, similarity score for prose, LLM-judge for subjective quality.
3. **A tolerance band** — "≥85% pass rate", not "100% match". Stochastic systems don't pass 100% reliably.

```python
@pytest.mark.eval  # custom marker, exclude from default test runs
@pytest.mark.parametrize("case", load_eval_cases("invoice_extraction.jsonl"))
@pytest.mark.asyncio
async def test_invoice_eval(case, real_client):
    result = await extractor.extract(case.input)
    assert result.amount == case.expected_amount, (
        f"Mismatch on case {case.id}: got {result.amount}, expected {case.expected_amount}"
    )
```

Run with: `pytest -m eval`. Track pass rate over time, not just per-run.

## LLM-as-judge

For subjective quality (clarity, helpfulness), use a separate LLM call to score:

```python
async def llm_judge(question: str, answer: str) -> int:
    judge_prompt = f"""
    Question: {question}
    Answer: {answer}
    Rate the answer 1-5 on accuracy and helpfulness. Return only the number.
    """
    response = await judge_client.messages.create(
        model="claude-opus-4-1",
        messages=[{"role": "user", "content": judge_prompt}],
        max_tokens=5,
    )
    return int(response.content[0].text.strip())
```

Use a different model than the one you're testing (avoid the "the judge is too kind to itself" effect). For tie-breaking, run 3 judges and take the median.

## Pytest tips

```python
# pytest.ini or pyproject.toml
[tool.pytest.ini_options]
asyncio_mode = "auto"             # no need to mark every async test
markers = [
    "eval: stochastic evals (slow, costs $)",
    "integration: requires Azure credentials",
]
```

Run patterns:

```bash
pytest                                 # fast unit tests only
pytest -m eval                         # only evals (CI nightly)
pytest -m "not eval and not integration"  # default CI
```

## Anti-patterns to flag

- Tests that hit the real paid API by default (no `-m eval` gate)
- 100% match assertions on stochastic LLM output
- Tests that depend on previous test state (shared mutable client)
- `time.sleep()` in tests — use `freezegun` or proper async waits
- Mocks that don't return realistic types (raw dicts instead of SDK objects)
- No fixtures — every test reconstructs its own setup
- Test functions over 30 lines (split into fixtures + assertion)

## See also

- `patterns/eval-with-pytest.md` — full eval harness
- `patterns/anthropic-client-async-wrapper.md` — injectable client
- `anti-patterns.md` (items 18, 19)
