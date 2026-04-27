# Agentic evaluator

> **Last validated**: 2026-04-26
> **Confidence**: 0.89

## When to use this pattern

Evaluating agents that produce multi-step traces (tool calls, sub-agent invocations, conversation history). The unit is a trace, not a single completion.

## Tool-call accuracy

Did the agent call the right tools, in the right order, with the right args?

```python
from dataclasses import dataclass
from typing import Any

@dataclass(frozen=True)
class ToolCall:
    name: str
    args: dict[str, Any]


def normalize_args(args: dict[str, Any]) -> dict[str, Any]:
    """Drop irrelevant fields (timestamps, uuids) for comparison."""
    DROP = {"trace_id", "request_id", "timestamp"}
    return {k: v for k, v in args.items() if k not in DROP}


class ToolCallSequenceEvaluator:
    """Score how well actual tool calls match expected, in order."""

    def __init__(self, *, strict_order: bool = False, strict_args: bool = False):
        self._strict_order = strict_order
        self._strict_args = strict_args

    def __call__(
        self,
        *,
        actual_calls: list[ToolCall],
        expected_calls: list[ToolCall],
        **kwargs: Any,
    ) -> dict[str, Any]:
        if not expected_calls:
            unexpected = len(actual_calls)
            return {
                "tool_sequence_match": 1.0 if unexpected == 0 else 0.0,
                "tool_sequence_reason": f"Expected no tools; got {unexpected}",
            }

        # Match expected calls against actual
        matched_actual_indices: set[int] = set()
        match_count = 0
        for expected in expected_calls:
            for i, actual in enumerate(actual_calls):
                if i in matched_actual_indices:
                    continue
                if actual.name != expected.name:
                    continue
                if self._strict_args and normalize_args(actual.args) != normalize_args(expected.args):
                    continue
                matched_actual_indices.add(i)
                match_count += 1
                break

        accuracy = match_count / len(expected_calls)

        # Order check
        if self._strict_order and accuracy == 1.0:
            order_ok = sorted(matched_actual_indices) == [i for i in range(len(expected_calls))]
            if not order_ok:
                accuracy *= 0.5

        return {
            "tool_sequence_match": accuracy,
            "tool_sequence_reason": (
                f"Matched {match_count}/{len(expected_calls)} expected calls"
                + (", correct order" if self._strict_order and accuracy == 1.0 else "")
            ),
            "tool_sequence_actual": [c.name for c in actual_calls],
            "tool_sequence_expected": [c.name for c in expected_calls],
        }
```

`strict_order=False` is the default — measures whether the right tools were called, regardless of sequence. `strict_order=True` adds the order constraint.

## Intent classifier evaluator

For routers / classifiers — did the agent choose the right intent?

```python
class IntentMatchEvaluator:
    """Strict equality on a closed set of intents."""

    def __init__(self, valid_intents: set[str]):
        self._valid = valid_intents

    def __call__(
        self,
        *,
        predicted_intent: str,
        expected_intent: str,
        **kwargs: Any,
    ) -> dict[str, Any]:
        predicted_norm = predicted_intent.strip().lower()
        expected_norm = expected_intent.strip().lower()

        if predicted_norm not in {i.lower() for i in self._valid}:
            return {
                "intent_match": 0.0,
                "intent_reason": f"Predicted '{predicted_intent}' not in valid set",
            }

        match = predicted_norm == expected_norm
        return {
            "intent_match": 1.0 if match else 0.0,
            "intent_reason": (
                f"Match" if match
                else f"Predicted '{predicted_intent}' != expected '{expected_intent}'"
            ),
        }
```

For confusion-matrix-style analysis across the dataset, aggregate `predicted vs expected` pairs and report per-intent precision/recall.

## Conversation quality evaluator

LLM-as-judge over an entire conversation transcript:

```python
class ConversationQualityEvaluator:
    PROMPT = """You are evaluating a multi-turn conversation between a user and an AI assistant.

Transcript:
{transcript}

Rate on 1-5:
- coherence: turns connect logically; assistant tracks context
- helpfulness: assistant addresses user needs effectively
- consistency: assistant doesn't contradict itself across turns

Examples:
  Coherence 5: assistant remembers earlier user constraints throughout
  Coherence 1: assistant ignores prior turns; treats each turn as new

Respond ONLY with JSON: {{"coherence": <int>, "helpfulness": <int>, "consistency": <int>, "reason": "<text>"}}
"""

    def __init__(self, judge_client, judge_model: str = "claude-opus-4-1"):
        self._client = judge_client
        self._model = judge_model

    async def __call__(
        self,
        *,
        transcript: list[dict[str, str]],
        **kwargs: Any,
    ) -> dict[str, Any]:
        rendered = "\n\n".join(
            f"{turn['role'].upper()}: {turn['content']}" for turn in transcript
        )
        response = await self._client.messages.create(
            model=self._model,
            max_tokens=300,
            temperature=0,
            messages=[{"role": "user", "content": self.PROMPT.format(transcript=rendered)}],
        )
        text = response.content[0].text.strip()
        try:
            parsed = json.loads(text)
            return {
                "convo_coherence": float(parsed["coherence"]),
                "convo_helpfulness": float(parsed["helpfulness"]),
                "convo_consistency": float(parsed["consistency"]),
                "convo_reason": parsed["reason"],
            }
        except (json.JSONDecodeError, KeyError) as e:
            return {
                "convo_coherence": 0.0,
                "convo_helpfulness": 0.0,
                "convo_consistency": 0.0,
                "convo_reason": f"Judge parse failed: {e}",
            }
```

## Trace replay vs live invocation

Two ways to evaluate an agentic system:

### Live invocation
Run the actual agent against the eval input. Captures real behavior including timing, tool latency, etc.

```python
@pytest.mark.eval
@pytest.mark.full
async def test_advisor_live(case, real_advisor_client, evaluators):
    response = await advisor_run(client=real_advisor_client, query=case["input"])
    metrics = evaluators(actual_calls=response.tool_calls, ...)
```

### Trace replay
Use a pre-recorded trace (from production logs or earlier eval) and replay through the evaluator. Cheaper — no agent re-invocation.

```python
@pytest.mark.eval
async def test_advisor_replay(case, evaluators):
    trace = load_trace(case["trace_path"])
    metrics = evaluators(
        actual_calls=trace.tool_calls,
        actual_intent=trace.intent,
        transcript=trace.transcript,
    )
```

Use replay for: regression of evaluators themselves (did your scoring change?), historical analysis, fast iterations.
Use live for: validating actual agent changes; necessary at least once per release.

## Multi-step expected behavior

Some failure-mode cases want "agent should refuse OR ask for clarification":

```python
class FlexibleBehaviorEvaluator:
    """Match against a list of acceptable behaviors."""

    BEHAVIORS = {
        "refuse": lambda answer: starts_with_refusal(answer),
        "ask_clarification": lambda answer: "?" in answer and len(answer) < 200,
        "answer_correctly": lambda answer: True,                # validated by another scorer
    }

    def __call__(
        self,
        *,
        answer: str,
        expected_behavior: str | list[str],
        **kwargs,
    ) -> dict[str, Any]:
        expected = expected_behavior if isinstance(expected_behavior, list) else [expected_behavior]
        for b in expected:
            if b not in self.BEHAVIORS:
                continue
            if self.BEHAVIORS[b](answer):
                return {"behavior_match": 1.0, "behavior_matched": b}
        return {
            "behavior_match": 0.0,
            "behavior_matched": None,
            "behavior_reason": f"None of {expected} matched",
        }
```

## Done when

- Returns a dict with explicit metric keys + reason
- Async if it makes LLM calls (judge); sync if pure deterministic
- Handles missing arguments via kwargs default or skip
- Aggregatable across cases (numeric scores, not strings)
- Reports both score and human-readable rationale

## Anti-patterns

- Comparing tool calls with `==` on dicts containing timestamps / UUIDs (always fails) — normalize first
- Strict order requirement when the agent has legitimate parallel tool use
- Conversation evaluator that re-runs the agent (expensive when replay would do)
- "Behavior match" with no list of valid behaviors (binary instead of flexible)
- Tracking only one metric per case (lose nuance)
- Conversation transcript with only `role:content` (lose tool calls in trace)

## See also

- `concepts/eval-types.md` — when agentic vs other types
- `patterns/custom-ai-assisted-evaluator.md` — for the judge half
- `patterns/custom-deterministic-evaluator.md` — for tool-name comparison
- `anti-patterns.md` (items 1, 14, 15)
