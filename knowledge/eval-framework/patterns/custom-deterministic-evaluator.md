# Custom deterministic evaluator

> **Last validated**: 2026-04-26
> **Confidence**: 0.94

## When to use this pattern

Any quality check expressible as code: schema validation, regex, set membership, exact match, length / format constraints. Free, fast — run on every commit.

## The protocol

A deterministic evaluator is a callable returning a dict of metrics. Compatible with `azure-ai-evaluation`'s `evaluate()` runner OR plain pytest:

```python
from typing import Any

class HasCitationEvaluator:
    """Did the answer cite at least one source as [N]?"""

    def __call__(self, *, answer: str, **kwargs: Any) -> dict[str, Any]:
        import re
        match = re.search(r'\[\d+\]', answer)
        return {
            "has_citation": 1.0 if match else 0.0,
            "has_citation_reason": "Found citation marker" if match else "No citation",
        }
```

Score uses 0.0 / 1.0 (not bool) — keeps the contract uniform with AI-assisted evaluators returning floats.

## Common deterministic evaluators

### Schema validation

```python
from pydantic import BaseModel, ValidationError

class ResponseSchema(BaseModel):
    intent: str
    confidence: float
    answer: str

class SchemaValidEvaluator:
    def __init__(self, schema: type[BaseModel]):
        self._schema = schema

    def __call__(self, *, answer: str, **kwargs) -> dict[str, Any]:
        try:
            self._schema.model_validate_json(answer)
            return {"schema_valid": 1.0, "schema_reason": "Valid"}
        except ValidationError as e:
            return {
                "schema_valid": 0.0,
                "schema_reason": f"{len(e.errors())} validation errors",
            }
```

### Required entities

```python
class RequiredEntitiesEvaluator:
    """Score by fraction of expected entities present in answer."""

    def __call__(self, *, answer: str, expected_entities: list[str], **kwargs) -> dict[str, Any]:
        if not expected_entities:
            return {"entity_coverage": 1.0, "entity_reason": "No expected entities"}
        answer_lower = answer.lower()
        found = [e for e in expected_entities if e.lower() in answer_lower]
        coverage = len(found) / len(expected_entities)
        return {
            "entity_coverage": coverage,
            "entity_found": found,
            "entity_missing": [e for e in expected_entities if e not in found],
            "entity_reason": f"{len(found)}/{len(expected_entities)} entities present",
        }
```

### Forbidden content

```python
class ForbiddenContentEvaluator:
    """1.0 if answer does NOT contain any forbidden phrase."""

    def __init__(self, forbidden: list[str]):
        self._forbidden = [f.lower() for f in forbidden]

    def __call__(self, *, answer: str, **kwargs) -> dict[str, Any]:
        answer_lower = answer.lower()
        hits = [f for f in self._forbidden if f in answer_lower]
        return {
            "forbidden_clean": 0.0 if hits else 1.0,
            "forbidden_hits": hits,
        }
```

### Refusal detection

```python
class RefusalDetectorEvaluator:
    """For failure-mode cases — did the agent properly refuse?"""

    REFUSAL_PHRASES = (
        "I can't", "I cannot", "I'm not able to",
        "Sorry, but", "I won't", "I'm unable to",
        "outside my scope", "I don't have", "I'm not permitted",
    )

    def __call__(self, *, answer: str, **kwargs) -> dict[str, Any]:
        ans_lower = answer.lower().lstrip()
        is_refusal = any(p.lower() in ans_lower[:200] for p in self.REFUSAL_PHRASES)
        return {
            "refused": 1.0 if is_refusal else 0.0,
            "refused_reason": "Refusal phrase detected" if is_refusal else "No refusal",
        }
```

### Numeric tolerance

```python
import re

class NumericMatchEvaluator:
    """Extract first number from answer, compare to expected with tolerance."""

    def __init__(self, tolerance: float = 0.01):
        self._tol = tolerance

    def __call__(self, *, answer: str, expected_value: float, **kwargs) -> dict[str, Any]:
        match = re.search(r'-?\d+(?:\.\d+)?', answer)
        if not match:
            return {"numeric_match": 0.0, "numeric_reason": "No number found"}
        actual = float(match.group())
        diff = abs(actual - expected_value)
        passed = diff <= self._tol * abs(expected_value) + 1e-9
        return {
            "numeric_match": 1.0 if passed else 0.0,
            "numeric_actual": actual,
            "numeric_diff": diff,
            "numeric_reason": f"|{actual} - {expected_value}| = {diff:.4f}",
        }
```

### Length constraints

```python
class LengthEvaluator:
    """Check answer length is within bounds."""

    def __init__(self, min_chars: int = 0, max_chars: int = 100_000):
        self._min = min_chars
        self._max = max_chars

    def __call__(self, *, answer: str, **kwargs) -> dict[str, Any]:
        n = len(answer)
        in_bounds = self._min <= n <= self._max
        return {
            "length_ok": 1.0 if in_bounds else 0.0,
            "length_chars": n,
            "length_reason": f"{n} chars (min {self._min}, max {self._max})",
        }
```

### Tool sequence match

```python
class ToolCallAccuracyEvaluator:
    """Did the agent call the expected tools (regardless of order)?"""

    def __call__(self, *, actual_tool_calls: list[str], expected_tool_calls: list[str], **kwargs) -> dict[str, Any]:
        actual_set = set(actual_tool_calls)
        expected_set = set(expected_tool_calls)
        if not expected_set:
            return {"tool_accuracy": 1.0, "tool_reason": "No expected tools"}
        matched = actual_set & expected_set
        accuracy = len(matched) / len(expected_set)
        return {
            "tool_accuracy": accuracy,
            "tool_matched": sorted(matched),
            "tool_missing": sorted(expected_set - actual_set),
            "tool_extra": sorted(actual_set - expected_set),
        }
```

## Composite evaluator

Combine many for one pass:

```python
class CompositeEvaluator:
    def __init__(self, evaluators: list):
        self._evals = evaluators

    def __call__(self, **kwargs) -> dict[str, Any]:
        out = {}
        for ev in self._evals:
            out.update(ev(**kwargs))
        return out

evaluator = CompositeEvaluator([
    SchemaValidEvaluator(ResponseSchema),
    HasCitationEvaluator(),
    LengthEvaluator(max_chars=2000),
])

result = evaluator(answer=agent_answer)
# => all metrics in one dict
```

## Wiring into pytest

```python
@pytest.fixture
def deterministic_eval():
    return CompositeEvaluator([
        SchemaValidEvaluator(ResponseSchema),
        HasCitationEvaluator(),
        LengthEvaluator(max_chars=2000),
    ])

@pytest.mark.parametrize("case", smoke_cases, ids=lambda c: c["id"])
def test_deterministic_smoke(case, mock_target_client, deterministic_eval):
    answer = run_target(client=mock_target_client, question=case["input"])
    metrics = deterministic_eval(answer=answer)
    assert metrics["schema_valid"] == 1.0, f"{case['id']}: invalid schema"
    assert metrics["has_citation"] == 1.0, f"{case['id']}: no citation"
```

These can run with `mock_target_client` — they don't need the real LLM. Free, fast, every commit.

## Done when

- Returns a dict with explicit metric keys (no bare bool)
- Returns a `_reason` field for debugging
- Handles missing arguments gracefully (use kwargs default)
- Composable with other evaluators
- Deterministic (same input → same output)

## Anti-patterns

- Returning bare `True` / `False` (loses score granularity for aggregation)
- Hardcoded constants when the threshold should be configurable
- Mutating input arguments
- Calling external services (network, files) — defeats deterministic-ness
- Per-case evaluator instances (use one shared instance + parametrize)
- `try: ... except Exception: pass` (silently scores 0 instead of failing)

## See also

- `concepts/eval-types.md` — when to use deterministic vs AI-assisted
- `patterns/custom-ai-assisted-evaluator.md` — for the AI counterparts
- `patterns/pytest-eval-runner.md` — wiring
- `anti-patterns.md` (items 1, 14)
