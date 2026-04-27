# Custom AI-assisted evaluator

> **Last validated**: 2026-04-26
> **Confidence**: 0.91

## When to use this pattern

Quality criteria too fuzzy for code: relevance, groundedness, tone, idiomatic-ness. The eval makes one or more LLM calls per case to assign a score.

## The protocol

Async callable returning a dict with score + reasoning + cost:

```python
from dataclasses import dataclass
from typing import Any
import json

import anthropic
from pydantic import BaseModel, Field, ValidationError


class JudgeResponse(BaseModel):
    score: int = Field(..., ge=1, le=5)
    reasoning: str


class GroundednessEvaluator:
    """LLM-as-judge for groundedness against provided context."""

    PROMPT_TEMPLATE = """You are evaluating how well an answer is grounded in provided context.

Question: {question}

Provided context:
{context}

Candidate answer:
{answer}

Rubric:
1 = answer contains claims NOT supported by context (hallucinated)
2 = answer mostly supported but has 1+ unsupported claims
3 = answer fully supported by context but vague
4 = answer fully supported AND uses specific evidence from context
5 = answer fully supported, uses evidence, AND quotes / cites specific sections

Examples:
  Context: "Q3 revenue: $4.2M"
  Answer: "Q3 revenue was $4.2M"
  Score: 5

  Context: "Q3 revenue: $4.2M"
  Answer: "Sales were strong in Q3"
  Score: 3 (vague but not contradicted)

  Context: "Q3 revenue: $4.2M"
  Answer: "Q3 revenue was $5M"
  Score: 1 (hallucinated)

Respond ONLY with this JSON:
{{"score": <int 1-5>, "reasoning": "<one sentence>"}}
"""

    def __init__(
        self,
        judge_client: anthropic.AsyncAnthropic,
        *,
        judge_model: str = "claude-opus-4-1",
        max_retries: int = 1,
    ) -> None:
        self._client = judge_client
        self._model = judge_model
        self._max_retries = max_retries

    async def __call__(
        self,
        *,
        question: str,
        answer: str,
        context: str,
        **kwargs: Any,
    ) -> dict[str, Any]:
        prompt = self.PROMPT_TEMPLATE.format(question=question, context=context, answer=answer)

        last_error = None
        for attempt in range(self._max_retries + 1):
            response = await self._client.messages.create(
                model=self._model,
                max_tokens=200,
                temperature=0,
                messages=[{"role": "user", "content": prompt}],
            )
            text = response.content[0].text.strip()
            try:
                parsed = JudgeResponse.model_validate_json(text)
                return {
                    "groundedness": float(parsed.score),
                    "groundedness_reason": parsed.reasoning,
                    "groundedness_judge_tokens": (
                        response.usage.input_tokens + response.usage.output_tokens
                    ),
                }
            except ValidationError as e:
                last_error = e

        return {
            "groundedness": 0.0,
            "groundedness_reason": f"Judge failed to return valid JSON: {last_error}",
            "groundedness_judge_tokens": 0,
        }
```

Key choices:
- `temperature=0` for stability
- Strong judge model (`claude-opus-4-1`)
- Pydantic validation on judge output
- Returns `groundedness_judge_tokens` for cost tracking
- Bounded retry on parse failure (1 retry max — beyond that the prompt is wrong)

## Pairwise preference evaluator

```python
class PairwisePreferenceEvaluator:
    """Compare two candidate answers; return which is better."""

    def __init__(self, judge_client, judge_model: str = "claude-opus-4-1"):
        self._client = judge_client
        self._model = judge_model

    async def __call__(
        self,
        *,
        question: str,
        answer_a: str,
        answer_b: str,
        **kwargs: Any,
    ) -> dict[str, Any]:
        result_ab = await self._compare(question, answer_a, answer_b)
        result_ba = await self._compare(question, answer_b, answer_a)

        if result_ab == "A" and result_ba == "B":
            winner = "answer_a"
        elif result_ab == "B" and result_ba == "A":
            winner = "answer_b"
        else:
            winner = "tie"

        return {
            "preference_winner": winner,
            "preference_ab": result_ab,
            "preference_ba": result_ba,
        }

    async def _compare(self, question: str, a: str, b: str) -> str:
        prompt = f"""
Question: {question}

Candidate A: {a}

Candidate B: {b}

Which answer is better? Respond with exactly one of: "A", "B", "TIE".
"""
        response = await self._client.messages.create(
            model=self._model,
            max_tokens=5,
            temperature=0,
            messages=[{"role": "user", "content": prompt}],
        )
        out = response.content[0].text.strip().upper()
        if out in ("A", "B", "TIE"):
            return out
        return "TIE"
```

Position-bias mitigated by running both orders.

## Multi-criterion evaluator (one judge, several scores)

When judge cost matters and you trust the judge, ask for multiple scores in one call:

```python
class MultiCriterionEvaluator:
    PROMPT = """Score the candidate on 3 criteria, 1-5 each.

Question: {question}
Candidate: {answer}

Criteria:
- accuracy: factually correct
- relevance: addresses the question
- clarity: clearly written

Respond ONLY with JSON: {{"accuracy": <int>, "relevance": <int>, "clarity": <int>, "reasoning": "<text>"}}
"""

    class Result(BaseModel):
        accuracy: int = Field(..., ge=1, le=5)
        relevance: int = Field(..., ge=1, le=5)
        clarity: int = Field(..., ge=1, le=5)
        reasoning: str

    # ... __call__ similar to GroundednessEvaluator,
    # parsing into Result, returning all 3 scores in dict
```

Tradeoff: cheaper but lower-quality scores per criterion. The judge tries to balance — its accuracy score is a bit influenced by its clarity assessment. For high-stakes scoring, use one call per criterion.

## Median-of-N to reduce noise

```python
import asyncio
import statistics

async def score_with_median(evaluator, n: int = 3, **kwargs) -> dict[str, Any]:
    """Run the evaluator N times, return median for each numeric metric."""
    runs = await asyncio.gather(*(evaluator(**kwargs) for _ in range(n)))

    keys = runs[0].keys()
    out = {}
    for k in keys:
        if not all(isinstance(r[k], (int, float)) for r in runs):
            out[k] = runs[0][k]                                   # non-numeric: take first
            continue
        out[k] = statistics.median(r[k] for r in runs)
    return out

# Usage:
result = await score_with_median(groundedness_evaluator, n=3,
                                  question=q, answer=a, context=c)
```

Cost is N× higher; noise reduces by ~√N. For high-stakes evals, worth it.

## Cost tracking

Every AI evaluator should report tokens (and ideally dollars) so the run-level total can be summed:

```python
return {
    "groundedness": float(score),
    "groundedness_reason": reasoning,
    "groundedness_judge_tokens": total_tokens,
    "groundedness_judge_cost_usd": total_tokens * PRICING_PER_TOKEN[judge_model],
}
```

Aggregated at run end → "this eval cost $4.32" appears in run metadata.

## Done when

- Judge prompt has explicit rubric (1-5 with descriptions)
- 2-3 calibration examples in prompt
- Structured JSON output (Pydantic-validated)
- Temperature 0 (or very low) on judge
- Bounded retry on parse failure
- Returns numeric score (not bool) and a reason
- Reports judge tokens / cost
- Uses a different model than the candidate

## Anti-patterns

- Free-prose output (parse fails)
- No rubric — judge invents its own scale
- Same model judging itself
- High temperature on judge (flaky)
- Multi-criterion in one call when stakes are high (use single-criterion)
- No examples in prompt (calibration drift)
- Bare `Exception` swallow on parse failure (silent zero scores)
- No cost tracking (eval bill is a surprise)

## See also

- `concepts/llm-as-judge.md` — design principles
- `concepts/azure-ai-evaluation-sdk.md` — built-in alternatives
- `patterns/custom-deterministic-evaluator.md` — cheap counterparts
- `anti-patterns.md` (items 2, 8, 10, 11)
