# Azure AI Evaluation SDK

> **Last validated**: 2026-04-26
> **Confidence**: 0.89
> **Source**: https://learn.microsoft.com/en-us/python/api/azure-ai-evaluation/

## What it is

`azure-ai-evaluation` (Python) — Microsoft's eval SDK with built-in evaluators and a runner. Saves you from writing every judge from scratch.

```bash
pip install azure-ai-evaluation
```

## Built-in evaluators

| Evaluator | What it scores | Needs |
|---|---|---|
| `GroundednessEvaluator` | Is answer grounded in provided context? | question, answer, context |
| `RelevanceEvaluator` | Does answer address the question? | question, answer |
| `CoherenceEvaluator` | Multi-turn coherence | conversation transcript |
| `FluencyEvaluator` | Linguistic quality | answer |
| `SimilarityEvaluator` | Semantic match to reference | answer, expected |
| `ContentSafetyEvaluator` | Hate / violence / sexual / self-harm | answer |
| `ProtectedMaterialEvaluator` | Copyrighted content | answer |
| `IndirectAttackEvaluator` | Prompt injection detection | input, answer |
| `RetrievalEvaluator` | Quality of retrieved chunks | query, retrieved_docs |

Most return scores 1–5 (with reasoning); content-safety returns severity buckets.

## Single evaluator usage

```python
from azure.ai.evaluation import GroundednessEvaluator
from azure.identity import DefaultAzureCredential
import os

groundedness = GroundednessEvaluator(
    model_config={
        "azure_endpoint": os.environ["AZURE_OPENAI_ENDPOINT"],
        "api_key": None,                                       # use Entra
        "azure_deployment": "gpt-4-judge",
        "api_version": "2024-08-01-preview",
    }
)

result = groundedness(
    question="What's our Q3 revenue?",
    answer="Q3 revenue was $4.2M, up 15% from Q2.",
    context="Q3 financial summary: revenue $4.2M, expenses $3.1M, net $1.1M.",
)
# result = {"groundedness": 5.0, "groundedness_reason": "..."}
```

The judge model (`azure_deployment`) is what scores. Use a strong model — Sonnet, Opus, or GPT-4-class. Cheap models score noisily.

## Batch runs with `evaluate()`

```python
from azure.ai.evaluation import evaluate, GroundednessEvaluator, RelevanceEvaluator

result = evaluate(
    data="evals/dataset/qa.jsonl",
    evaluators={
        "groundedness": GroundednessEvaluator(model_config=judge_config),
        "relevance": RelevanceEvaluator(model_config=judge_config),
    },
    target=my_agent_function,                   # callable that produces answers
    output_path="evals/runs/run-{date}.json",
    azure_ai_project={
        "subscription_id": "...",
        "resource_group_name": "...",
        "project_name": "starbase",
    },
)

# result.metrics — aggregate scores
# result.rows — per-case scores
# result.studio_url — link to view in Foundry portal
```

The `target` is a function that takes inputs from the dataset and returns the answer to evaluate. The runner orchestrates: read dataset → call target → score each evaluator → aggregate → write results.

## Custom evaluators

Implement the protocol — a callable returning a dict:

```python
from typing import Any

class HasCitationEvaluator:
    """Deterministic — does the answer include at least one citation?"""

    def __call__(self, *, answer: str, **kwargs: Any) -> dict[str, Any]:
        import re
        match = re.search(r'\[\d+\]', answer)
        return {
            "has_citation": 1.0 if match else 0.0,
            "has_citation_reason": "Found citation marker" if match else "No citation marker",
        }
```

Plug in alongside built-ins:

```python
result = evaluate(
    data="...",
    evaluators={
        "groundedness": GroundednessEvaluator(...),
        "has_citation": HasCitationEvaluator(),  # deterministic, free
    },
    target=...,
)
```

## AI-assisted custom evaluator

For domain-specific scoring (e.g., "is this DAX measure syntactically valid AND idiomatic?"):

```python
class IdiomaticDaxEvaluator:
    def __init__(self, judge_client):
        self._judge = judge_client

    async def __call__(self, *, answer: str, **kwargs) -> dict[str, Any]:
        prompt = f"""
You are evaluating DAX code. Rate the candidate on:
- Syntactic validity (1-5)
- Use of idiomatic patterns (DIVIDE, DATEADD, etc.) (1-5)

Candidate: {answer}

Respond as JSON: {{"validity": <int>, "idiomatic": <int>, "reason": "<text>"}}
"""
        response = await self._judge.messages.create(...)
        parsed = json.loads(response.content[0].text)
        return {
            "dax_validity": parsed["validity"],
            "dax_idiomatic": parsed["idiomatic"],
            "dax_reason": parsed["reason"],
        }
```

## Eval against a real agent

`target` can be an async function calling a deployed agent:

```python
async def run_advisor(*, question: str, **kwargs) -> dict[str, Any]:
    response = await advisor_agent.ask(question)
    return {
        "answer": response.text,
        "context": response.retrieved_context,    # passed to GroundednessEvaluator
    }

result = evaluate(
    data="advisor_qa.jsonl",
    evaluators={
        "groundedness": GroundednessEvaluator(model_config=judge_config),
    },
    target=run_advisor,
)
```

## Foundry integration

When `azure_ai_project` is configured, results upload to the Foundry portal. UI features:
- Cross-run comparison
- Per-case drill-down
- Trace correlation (ties eval results to OTel spans)
- Dashboard widgets

For projects that already track production telemetry in Foundry, this is the easiest backend.

## Cost considerations

- Built-in evaluators issue 1 LLM call per case per evaluator
- 1000 cases × 4 evaluators = 4000 calls × ~$0.003 = ~$12
- Custom deterministic evaluators add zero cost
- Local-only runs (no Foundry upload) save the storage cost but lose visibility

## Limitations

- Built-in rubrics are fixed — for highly domain-specific quality, you'll write custom evaluators anyway
- The 1–5 scale doesn't fit binary metrics — wrap them in custom evaluators returning 0/1
- Multi-turn evaluation is supported but verbose — `ConversationCoherenceEvaluator` handles common cases

## Anti-patterns

- Built-in evaluator with judge model = candidate model
- Custom evaluator returning bare bool (loses score granularity) — return `0.0` / `1.0` and a reason
- Running `evaluate()` per case in a loop instead of batched (loses parallelism)
- Storing results only locally when team needs visibility (use Foundry / Fabric)
- Evaluator that mutates input arguments (breaks parallelization)

## See also

- `concepts/llm-as-judge.md` — judge design fundamentals
- `concepts/regression-tracking.md` — storing and comparing results
- `patterns/custom-ai-assisted-evaluator.md`
- `patterns/custom-deterministic-evaluator.md`
- `patterns/fabric-delta-results-writer.md`
- `anti-patterns.md` (items 2, 14)
