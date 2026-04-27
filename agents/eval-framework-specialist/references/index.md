# Eval Framework Knowledge Base — Index

> **Last validated**: 2026-04-26
> **Confidence**: 0.92
> **Scope**: LLM eval design — deterministic / AI-assisted / agentic metrics, golden datasets, LLM-as-judge, regression tracking, Azure AI Evaluation SDK, Fabric Delta backends.

## KB Structure

### Concepts

| File | Topic | Status |
|---|---|---|
| `concepts/eval-types.md` | Deterministic vs AI-assisted vs agentic — when each fits | Validated |
| `concepts/golden-dataset-design.md` | Single-turn, multi-turn, failure-modes; JSONL format | Validated |
| `concepts/llm-as-judge.md` | Rubrics, scales, tie-breaking, judge selection | Validated |
| `concepts/azure-ai-evaluation-sdk.md` | Built-in evaluators, custom evaluators, batch runs | Validated |
| `concepts/regression-tracking.md` | Run IDs, version pinning, cross-run comparison | Validated |
| `concepts/eval-cost-and-cadence.md` | Per-commit / per-PR / nightly tradeoffs; cost guards | Validated |

### Patterns

| File | Topic |
|---|---|
| `patterns/pytest-eval-runner.md` | `@pytest.mark.eval` + parametrize + fixtures pattern |
| `patterns/custom-deterministic-evaluator.md` | Rule-based scorer (entity-grounding, schema-validation) |
| `patterns/custom-ai-assisted-evaluator.md` | LLM-call returning typed score with rationale |
| `patterns/agentic-evaluator.md` | tool-call-accuracy, intent-match, conversation-quality |
| `patterns/fabric-delta-results-writer.md` | Write eval results to Fabric Delta with deltalake |
| `patterns/failure-modes-dataset-generator.md` | Adversarial / edge-case dataset generation |

### Reference

| File | Topic |
|---|---|
| `anti-patterns.md` | 20 eval-framework anti-patterns to flag on sight |

## Reading Protocol

1. Start here (`index.md`) to identify relevant files for the task.
2. For task type → file map:
   - "design an eval suite" → `concepts/eval-types.md` + `concepts/golden-dataset-design.md`
   - "build an LLM-as-judge" → `concepts/llm-as-judge.md` + `patterns/custom-ai-assisted-evaluator.md`
   - "use built-in evaluators" → `concepts/azure-ai-evaluation-sdk.md`
   - "track results over time" → `concepts/regression-tracking.md` + `patterns/fabric-delta-results-writer.md`
   - "test agent tool use" → `patterns/agentic-evaluator.md`
   - "generate failure-mode cases" → `patterns/failure-modes-dataset-generator.md`
   - "wire into pytest" → `patterns/pytest-eval-runner.md`
   - "decide eval cadence / cost" → `concepts/eval-cost-and-cadence.md`
3. If any file has `last_validated` older than 90 days, use `web` tool to re-validate against:
   - https://learn.microsoft.com/en-us/azure/ai-foundry/concepts/evaluation-approach-gen-ai
   - https://learn.microsoft.com/en-us/python/api/azure-ai-evaluation/
   - https://pypi.org/project/azure-ai-evaluation/
   - https://docs.pytest.org/en/stable/
4. Check `anti-patterns.md` whenever reviewing user-provided eval code or results.
