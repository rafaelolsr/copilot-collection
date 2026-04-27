# Eval types — deterministic vs AI-assisted vs agentic

> **Last validated**: 2026-04-26
> **Confidence**: 0.93

## The 3 categories

| Type | Cost | Speed | What it measures |
|---|---|---|---|
| **Deterministic** | $0 | <1ms | Exact-match, schema validation, regex, set-membership |
| **AI-assisted** | $0.001–0.01 per case | 1–5s | Subjective quality (relevance, groundedness, tone) |
| **Agentic** | $0–varies | varies | Tool-call sequences, intent classification, multi-turn coherence |

The economics: a 1000-case dataset evaluated only deterministically = free, fast. The same dataset with an AI judge per case = $5–10, 1–2 hours. Same dataset with full agentic replay = $50+. Choose carefully.

## Deterministic — what it can do

```python
def has_required_entities(answer: str, expected: list[str]) -> bool:
    return all(e.lower() in answer.lower() for e in expected)

def is_valid_json(text: str, schema: type[BaseModel]) -> bool:
    try:
        schema.model_validate_json(text)
        return True
    except ValidationError:
        return False

def numeric_within_tolerance(actual: float, expected: float, tol: float = 0.01) -> bool:
    return abs(actual - expected) <= tol

def matches_regex(text: str, pattern: str) -> bool:
    return bool(re.search(pattern, text))

def starts_with_refusal(answer: str) -> bool:
    refusal_starts = ("I can't", "I cannot", "I'm not able to", "Sorry, but")
    return any(answer.startswith(s) for s in refusal_starts)
```

Use these for:
- Structured output validation (JSON, dates, numbers)
- Required-entity checks (the answer must mention X)
- Forbidden-content checks (the answer must NOT contain Y)
- Format compliance (markdown, length, etc.)
- Refusal detection (for adversarial inputs)

If a check is expressible in code, write code. Don't pay an LLM to do it.

## AI-assisted — what it's for

When the rule is genuinely fuzzy:
- "Is the summary accurate?"
- "Does the answer actually address the question?"
- "Is the tone appropriate for the audience?"
- "Are the cited sources actually used in the answer?"
- "Is this response factually consistent with the provided context?"

These don't reduce to regex. An LLM-as-judge call returns a score (1–5, 0–1, or pass/fail) with rationale.

```python
async def groundedness_score(question: str, answer: str, context: str) -> int:
    judge_prompt = f"""
You will rate how groundedness an answer is against provided context.

Question: {question}

Provided context:
{context}

Candidate answer:
{answer}

Rubric:
1 = answer contains claims not supported by context (hallucinated)
2 = answer mostly supported but has 1+ unsupported claims
3 = answer fully supported by context
4 = answer fully supported AND uses specific evidence from context
5 = answer fully supported, uses evidence, AND quotes / cites sections

Respond with a single integer from 1-5.
"""
    response = await judge_client.messages.create(
        model="<provider>-flagship",
        max_tokens=5,
        messages=[{"role": "user", "content": judge_prompt}],
    )
    return int(response.content[0].text.strip())
```

The Azure AI Evaluation SDK provides built-in versions of common metrics — use those when they fit (`GroundednessEvaluator`, `RelevanceEvaluator`, etc.).

## Agentic — what it's for

Evaluating agents that do multi-step work:

### Tool-call accuracy

Did the agent call the right tools, in the right order, with the right arguments?

```python
def tool_call_accuracy(actual_calls: list[ToolCall], expected_calls: list[ToolCall]) -> float:
    """Returns fraction of expected calls that appear in actual."""
    matches = 0
    for expected in expected_calls:
        for actual in actual_calls:
            if (actual.name == expected.name
                    and _args_match(actual.args, expected.args)):
                matches += 1
                break
    return matches / len(expected_calls)
```

### Intent match

For routers / classifiers — did the system correctly identify what the user wanted?

```python
def intent_match(predicted: str, expected: str) -> bool:
    return predicted.lower().strip() == expected.lower().strip()
```

### Multi-turn coherence

Across N conversation turns, does the agent remember context, avoid contradictions, and stay on task?

Usually AI-assisted (LLM-as-judge over the whole transcript) but framed agentically because the unit of evaluation is a conversation, not a single turn.

## Combining types — typical eval suite

A real eval suite for a Q&A agent might run, per case:

1. Deterministic: did it return JSON matching the schema? (cheap gate)
2. Deterministic: does it cite at least one source? (cheap)
3. AI-assisted: groundedness score 1–5 (~$0.002)
4. AI-assisted: relevance score 1–5 (~$0.002)
5. Agentic: did it call the search tool before answering? (free, replays trace)

Aggregate threshold: ≥80% deterministic-pass AND avg groundedness ≥4.0 AND avg relevance ≥4.0 AND ≥95% used search tool.

Single threshold = single signal. Multi-metric = nuanced quality picture.

## When deterministic isn't enough — but you don't need AI

Sometimes a check is too complex for a regex but doesn't need an LLM:

```python
def numeric_close_enough(actual_str: str, expected: float) -> bool:
    """Extract first number from text, compare to expected."""
    match = re.search(r'-?\d+(\.\d+)?', actual_str)
    if not match:
        return False
    return abs(float(match.group()) - expected) <= 0.01
```

Deterministic tier — it's just code.

## Anti-patterns

- AI-assisted check where deterministic would suffice (waste)
- Single all-or-nothing pass/fail when multiple metrics give clearer signal
- Deterministic check on stochastic prose (e.g., `summary == "exact text"`) — wrong tool
- Agentic eval that re-runs the entire agent (expensive) when replay-from-trace would work
- Mixing eval types without a clear hierarchy (deterministic → AI-assisted → agentic)

## See also

- `concepts/golden-dataset-design.md` — what dataset feeds these
- `concepts/llm-as-judge.md` — how to write good AI-assisted scorers
- `concepts/eval-cost-and-cadence.md` — when to run which
- `patterns/custom-deterministic-evaluator.md`
- `patterns/custom-ai-assisted-evaluator.md`
- `anti-patterns.md` (items 1, 14)
