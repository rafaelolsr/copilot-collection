# LLM-as-judge

> **Last validated**: 2026-04-26
> **Confidence**: 0.91

## What it is

Using an LLM to score the output of another LLM. Replaces "manual reviewer reads 1000 outputs" with "judge LLM scores 1000 outputs in 5 minutes for $5".

Trade-off: judges have biases. Tuning judges is its own discipline.

## When to use

YES:
- Subjective qualities (helpfulness, tone, clarity)
- Groundedness (does the answer derive from provided context?)
- Coherence (multi-turn flow makes sense)
- Comparing two candidate answers (preference)

NO (use deterministic):
- Exact-match against ground truth
- Schema validation
- Length / format constraints
- Refusal detection (regex on starting phrases)

## Anatomy of a good judge prompt

```
You are evaluating <thing>.

[Context — what the candidate was given]
{question}

[Reference answer or context for grounding]
{expected}

[Candidate to score]
{candidate}

[Rubric — explicit scale]
1 = <what 1 looks like>
2 = <what 2 looks like>
3 = <what 3 looks like>
4 = <what 4 looks like>
5 = <what 5 looks like>

[Examples — calibration]
Example A:
  Candidate: "<example>"
  Score: 4
  Reasoning: "..."

[Output format]
Respond ONLY with a JSON object: {"score": <int>, "reasoning": "<one sentence>"}
```

The 4 critical pieces:
1. **Explicit scale** — "5-point" alone isn't enough; describe each point
2. **Calibration examples** — at least one per score level the judge will use
3. **Structured output** — JSON or single integer; never free prose (parse-fail risk)
4. **Single criterion per call** — don't ask one judge call to score "groundedness AND tone AND length"

## Model selection

Use a DIFFERENT model than the candidate. If you're evaluating <provider>-balanced, judge with Opus or with GPT-4. Same-model judging gives bias toward your candidate's failure modes.

| Candidate model | Recommended judge |
|---|---|
| <provider>-balanced | <provider>-flagship OR GPT-4.1 |
| <provider>-flagship | <provider>-balanced (faster) OR GPT-4.1 |
| GPT-4o | <provider>-flagship |
| <provider>-fast | <provider>-balanced |

Use a stronger model than the candidate when feasible — the judge's job is harder.

## Tie-breaking

Judges aren't deterministic. Score 4 today might be score 3 tomorrow.

Mitigations:
1. **Lower temperature** on judge calls (`temperature=0` or close)
2. **Multiple judges**, take median:
   ```python
   scores = await asyncio.gather(*[judge_call(...) for _ in range(3)])
   return statistics.median(scores)
   ```
3. **Two-judge with tiebreaker**: judges A and B disagree → judge C decides
4. **Score bucketing**: treat 4 vs 5 as both "good"; only flag drops to 1–3

## Pairwise preference (no absolute scale)

Often more reliable than absolute scoring:

```python
async def prefer(question: str, a: str, b: str) -> str:
    judge_prompt = f"""
Compare two candidate answers to the same question. Which is better?

Question: {question}

Candidate A: {a}
Candidate B: {b}

Respond with exactly "A", "B", or "TIE".
"""
    response = await judge_client.messages.create(
        model="<provider>-flagship",
        max_tokens=2,
        messages=[{"role": "user", "content": judge_prompt}],
        temperature=0,
    )
    return response.content[0].text.strip()
```

For comparing prompt versions: have the judge pick A vs B for each case, count wins. Significantly more sensitive than "absolute score for V1 vs absolute score for V2".

Beware position bias: judges sometimes prefer "A" regardless of content. Run each pair both ways:

```python
result_ab = await prefer(q, a=v1_answer, b=v2_answer)
result_ba = await prefer(q, a=v2_answer, b=v1_answer)
# v1 wins if result_ab == "A" AND result_ba == "B"
# v2 wins if result_ab == "B" AND result_ba == "A"
# else: tie / unclear
```

## Common biases to watch for

| Bias | What it does | Mitigation |
|---|---|---|
| **Verbosity bias** | Judges prefer longer answers | Score concision separately; add "concise" to rubric |
| **Position bias** | Judges prefer the first option | Randomize order; run both orders |
| **Self-bias** | Judges favor outputs from same model | Use different model |
| **Format bias** | Judges prefer markdown / structured output | Match candidate format requirements |
| **Sycophancy** | Judges agree with whatever they're told | Don't tell the judge which answer is "from the new prompt" |

## Ground truth vs no ground truth

When you have ground truth (golden dataset with expected answers):

```python
async def score_with_ground_truth(question, candidate, expected) -> int:
    prompt = f"""
Question: {question}
Reference answer: {expected}
Candidate answer: {candidate}

Score how well the candidate matches the reference, 1-5.
[rubric...]
"""
```

When you don't (open-ended):

```python
async def score_without_ground_truth(question, candidate, context) -> int:
    prompt = f"""
Question: {question}
Reference context: {context}

Candidate answer: {candidate}

Score the candidate's groundedness in the context, 1-5.
[rubric...]
"""
```

The Azure AI Evaluation SDK's `GroundednessEvaluator` does the second case out-of-the-box.

## Cost considerations

Per case: ~$0.001–0.01 depending on judge model and prompt length. For 1000 cases × 2 judge calls (groundedness + relevance) = $2–20.

Budget guards (see `concepts/eval-cost-and-cadence.md`):
- Cap dollars per eval run
- Sample N cases for AI-assisted (not all)
- Tier: deterministic on every commit; AI-assisted on PRs touching prompts; full on nightly

## Anti-patterns

- Free-prose output (no JSON) → parse failures
- No rubric, just "score 1-5" → judge invents its own scale
- No examples → calibration drift
- Same model judging itself
- Multi-criterion in one call ("rate accuracy AND tone AND length") → judge averages, you lose signal
- High temperature on judge → flaky scores
- Comparing scores across runs without using the SAME judge model — version drift
- No tie-breaking on pairwise comparisons

## See also

- `concepts/eval-types.md` — when AI-assisted is the right tool
- `patterns/custom-ai-assisted-evaluator.md` — production-ready judge code
- `concepts/eval-cost-and-cadence.md` — cost guards
- `anti-patterns.md` (items 2, 8, 10, 18)
