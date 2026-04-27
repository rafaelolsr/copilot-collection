# Python Knowledge Base — Index

> **Last validated**: 2026-04-26
> **Confidence**: 0.92
> **Scope**: Modern Python 3.12+ for AI/LLM systems — async clients, structured output, retry patterns, tool-use loops, evals, type safety, project setup.

## KB Structure

### Concepts

| File | Topic | Status |
|---|---|---|
| `concepts/async-await-fundamentals.md` | asyncio, coroutines, blocking-in-async pitfalls | Validated |
| `concepts/pydantic-v2-structured-output.md` | BaseModel, Field constraints, validators, repair loops | Validated |
| `concepts/retry-patterns-llm.md` | tenacity, transient vs permanent errors, 429/529 handling | Validated |
| `concepts/type-safety-python.md` | mypy --strict, Protocols, TypedDict, generics, overloads | Validated |
| `concepts/testing-llm-code.md` | deterministic mocks vs stochastic evals, golden datasets | Validated |
| `concepts/cost-tracking-tokens.md` | token accounting, budget guards, prompt caching economics | Validated |
| `concepts/secrets-and-key-rotation.md` | env vars, key handling, never-hardcode rules | Validated |

### Patterns

| File | Topic |
|---|---|
| `patterns/llm-client-async-wrapper.md` | Vendor-neutral async LLM client + retry + timeout + cost hook |
| `patterns/tool-use-loop.md` | Bounded dispatch loop with max_iterations + per-tool error handling |
| `patterns/instructor-structured-extraction.md` | instructor + Pydantic + repair-on-validation-error |
| `patterns/streaming-responses.md` | Stream consumer with backpressure + cancellation |
| `patterns/eval-with-pytest.md` | pytest + parametrize + fixtures + mock LLM |
| `patterns/project-setup-uv.md` | pyproject.toml + uv + ruff + mypy + pytest skeleton |
| `patterns/code-review-checklist.md` | Systematic LLM code review (auth, retry, async, types, costs) |

### Reference

| File | Topic |
|---|---|
| `anti-patterns.md` | 22 Python + AI-specific anti-patterns to flag on sight |

## Reading Protocol

1. Start here (`index.md`) to identify relevant files for the task.
2. For task type → file map:
   - "write/refactor LLM client code" → `concepts/async-await-fundamentals.md` + `patterns/llm-client-async-wrapper.md`
   - "structured extraction" → `concepts/pydantic-v2-structured-output.md` + `patterns/instructor-structured-extraction.md`
   - "agent loop with tools" → `patterns/tool-use-loop.md`
   - "streaming output" → `patterns/streaming-responses.md`
   - "tests / evals" → `concepts/testing-llm-code.md` + `patterns/eval-with-pytest.md`
   - "new project setup" → `patterns/project-setup-uv.md`
   - "review existing code" → `anti-patterns.md` + `patterns/code-review-checklist.md`
   - "cost / budget" → `concepts/cost-tracking-tokens.md`
3. If any file has `last_validated` older than 90 days, use `web` tool to re-validate against:
   - https://docs.python.org/3/
   - https://docs.pydantic.dev/latest/
   - https://www.python-httpx.org/
   - https://tenacity.readthedocs.io/
   - https://python.useinstructor.com/
   - https://docs.astral.sh/uv/
4. Check `anti-patterns.md` whenever reviewing user-provided code.
