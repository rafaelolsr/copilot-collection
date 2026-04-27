# Eval framework — Anti-Patterns

> **Last validated**: 2026-04-26
> **Confidence**: 0.92
> Wrong / Correct pairs for every anti-pattern the agent flags on sight.

---

## 1. AI-assisted scorer where deterministic would do

Wrong:
```python
async def has_required_field(answer):
    response = await judge_client.messages.create(
        model="claude-opus-4-1",
        messages=[{"role": "user", "content": f"Does this answer mention 'revenue'? Answer YES or NO.\n\nAnswer: {answer}"}],
    )
    return "YES" in response.content[0].text
```

Why: $0.005 per case for what `"revenue" in answer.lower()` does for $0.

Correct:
```python
def has_required_field(answer: str) -> bool:
    return "revenue" in answer.lower()
```

Related: `concepts/eval-types.md`

---

## 2. Same model evaluating itself

Wrong:
```python
candidate_model = "claude-sonnet-4-5"
judge_model = "claude-sonnet-4-5"
```

Why: judge has self-bias. Underestimates failure modes the candidate model also has.

Correct: use a stronger or different family.
```python
candidate_model = "claude-sonnet-4-5"
judge_model = "claude-opus-4-1"   # stronger
# or
judge_model = "gpt-4.1"           # different family
```

Related: `concepts/llm-as-judge.md`

---

## 3. assert result == expected on stochastic prose

Wrong:
```python
async def test_summary():
    summary = await summarize(text)
    assert summary == "expected summary text"
```

Correct:
```python
async def test_summary():
    summary = await summarize(text)
    assert similarity(summary, expected) > 0.85
    # or
    assert await groundedness_judge(summary, source=text) >= 4
```

---

## 4. Tests hit real paid API by default in CI

Wrong:
```python
def test_summary():
    client = anthropic.AsyncAnthropic()              # real client
    summary = await summarize(client, text)
    assert summary  # passes; charges $$$ on every CI run
```

Correct:
```python
@pytest.mark.eval                                    # opt-in marker
async def test_summary_eval(real_anthropic_client):
    summary = await summarize(real_anthropic_client, text)
    assert summary
```

Run with `pytest -m eval` only when intended.

Related: `concepts/eval-cost-and-cadence.md`

---

## 5. Eval results with no run ID / no version pinning

Wrong:
```jsonl
{"case_id":"qa-001","groundedness":4.5}
```

Why: which run? Which dataset version? Which prompt? Useless for trend analysis.

Correct:
```jsonl
{"run_id":"r-2026-04-26-abc","case_id":"qa-001","groundedness":4.5,"dataset_hash":"a3f9","prompt_hash":"b21e","model":"claude-sonnet-4-5","judge_model":"claude-opus-4-1"}
```

Related: `concepts/regression-tracking.md`

---

## 6. Golden dataset committed but not version-tagged

Wrong: `evals/dataset.jsonl` with no version metadata. Edit + commit silently changes what runs evaluate.

Correct: include a metadata first-line:
```jsonl
{"_meta":{"version":"v3","name":"advisor_qa","hash_check":"a3f9c2d1e4..."}}
{"id":"qa-001","input":"...","expected":"..."}
```

Plus hash the file content per run, store in run metadata.

Related: `concepts/golden-dataset-design.md`

---

## 7. No tolerance band on aggregate metrics

Wrong:
```python
assert avg_groundedness == 5.0   # never passes; judge is stochastic
```

Correct:
```python
assert avg_groundedness >= 4.0
# AND
assert pass_rate(scores, threshold=4) >= 0.85
```

---

## 8. Evaluator with no rubric / criteria description

Wrong:
```python
prompt = f"Score this answer 1-5: {answer}"
```

Why: judge invents its own scale; runs aren't comparable across time or models.

Correct:
```python
prompt = f"""Score this answer on groundedness, 1-5.

Rubric:
1 = answer contains hallucinated claims
2 = answer mostly supported but has unsupported parts
3 = answer fully supported but vague
4 = answer fully supported AND uses specific evidence
5 = answer fully supported, uses evidence, AND cites sources

Answer: {answer}
"""
```

Related: `concepts/llm-as-judge.md`

---

## 9. Dataset with all happy-path cases

Wrong: 100 cases, all "what's our revenue?" or "show top 10 customers". Passes 100%, reveals nothing.

Correct: ~70% happy-path, ~20% ambiguous/multi-step, ~10% failure-mode (out-of-scope, injection, empty input).

Related: `concepts/golden-dataset-design.md`, `patterns/failure-modes-dataset-generator.md`

---

## 10. Judge prompt with no examples / no scale definition

Wrong:
```python
prompt = "Rate the quality of this answer 1-5. Answer: {answer}"
```

Correct: include 2-3 calibration examples per scale point:
```python
prompt = """Rate, 1-5.
Scale:
  1 = ...
  2 = ...
  ...

Examples:
  Answer: "Revenue was $4M"  -- given context "Q3: $4.2M"  -- Score: 3 (close but imprecise)
  Answer: "Q3 revenue was $4.2M" -- Score: 5

Now score this answer: {answer}
"""
```

---

## 11. Cost not tracked per eval run

Wrong: run an eval suite, get scores, no idea if it cost $0.50 or $50.

Correct: every AI-assisted evaluator returns `<metric>_judge_tokens`; aggregator sums into `cost_usd`; run metadata records it.

```python
return {
    "groundedness": score,
    "groundedness_reason": reason,
    "groundedness_judge_tokens": usage.input_tokens + usage.output_tokens,
}
```

Related: `concepts/eval-cost-and-cadence.md`

---

## 12. Failure output that doesn't show actual model response

Wrong:
```python
assert score >= 4, f"Case {case.id} failed"
```

Correct:
```python
assert score >= 4, (
    f"{case.id}: groundedness {score}/5 < 4\n"
    f"  Question: {case.input}\n"
    f"  Expected: {case.expected[:200]}\n"
    f"  Got: {actual_answer[:200]}\n"
    f"  Judge reasoning: {reason}"
)
```

---

## 13. Using production data without anonymization

Wrong: copying real user queries containing emails, names, IDs into the golden dataset.

Correct:
- Scrub PII before adding to dataset (regex on emails, names, phone numbers)
- Or use synthetic look-alikes
- Document the scrubbing in dataset notes

Critical: PII in a committed dataset = compliance issue.

---

## 14. Custom evaluator that returns just bool

Wrong:
```python
def has_citation(answer): return bool(re.search(r'\[\d+\]', answer))
```

Why: loses granularity. Can't compute "average citation rate". Doesn't fit the dict-of-metrics convention.

Correct:
```python
def has_citation(answer: str) -> dict[str, Any]:
    match = re.search(r'\[\d+\]', answer)
    return {
        "has_citation": 1.0 if match else 0.0,
        "has_citation_reason": "Citation marker found" if match else "Missing citation",
    }
```

---

## 15. Multi-turn eval re-evaluating each turn from scratch

Wrong: in a multi-turn dataset, run the agent fresh on each turn — loses conversation context.

Correct: maintain conversation state across turns:

```python
async def eval_multi_turn(case, agent_client):
    state = []
    for turn in case.turns:
        if turn.role == "user":
            state.append({"role": "user", "content": turn.content})
        elif turn.role == "assistant":
            response = await agent_client.continue_conversation(state)
            state.append({"role": "assistant", "content": response.text})
            yield (turn, response)
```

---

## 16. Eval marker missing on slow tests

Wrong: a test that calls real LLMs but isn't gated:
```python
async def test_extract_groundedness(real_judge_client):                # NO marker
    ...
```

Correct:
```python
@pytest.mark.eval
@pytest.mark.smoke
async def test_extract_groundedness(real_judge_client):
    ...
```

`pytest -m "not eval"` excludes; CI runs only opt-in evals.

---

## 17. Score thresholds hardcoded in test

Wrong:
```python
assert score >= 4
```

Per-test-file constants get inconsistent fast.

Correct: centralize in config / fixtures.
```python
THRESHOLDS = {"groundedness_min": 4, "relevance_min": 4, "pass_rate_min": 0.85}

@pytest.fixture
def thresholds():
    return THRESHOLDS

def test_smoke(thresholds, score):
    assert score >= thresholds["groundedness_min"]
```

---

## 18. Judge tied 50/50 with no tie-breaking

Wrong: pairwise prefers A vs B. A judge says "TIE" when one answer is clearly better. Result: false null.

Correct: at minimum:
- Run both orders (A vs B, then B vs A) — counts only as a win if both agree
- Or: 3 judge calls, take majority
- Or: 2 judges, with a 3rd as tiebreaker on disagreement

Related: `concepts/llm-as-judge.md`

---

## 19. Eval results not stored / not queryable

Wrong: print scores to stdout, never persist anywhere. Can't compare runs.

Correct: write to JSONL or Fabric Delta tables. Even local-only is better than nothing.

Related: `patterns/fabric-delta-results-writer.md`, `concepts/regression-tracking.md`

---

## 20. Failure-mode case with no expected behavior

Wrong:
```jsonl
{"id":"fm-01","input":"","expected":"???"}
```

Correct:
```jsonl
{"id":"fm-01","input":"","expected_behavior":"refuse","tags":["empty"]}
```

`expected_behavior` is on a closed set (refuse / ask_clarification / answer_correctly / refuse_injection / refuse_out_of_scope). Evaluator dispatches based on this field.

Related: `patterns/agentic-evaluator.md` `FlexibleBehaviorEvaluator`

---

## See also

- `index.md`
- All `concepts/` and `patterns/`
