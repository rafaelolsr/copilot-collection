# Code review checklist for LLM-integrated Python

> **Last validated**: 2026-04-26
> **Confidence**: 0.93

## When to use this pattern

Reviewing user-submitted Python that calls LLMs. Use this as a structured walkthrough — every item is grounded in a real anti-pattern, in roughly the order things matter.

## The checklist

Run through these in order. Stop reviewing if a `CRITICAL` is found and report immediately.

### 1. Secrets — CRITICAL

```bash
grep -nE 'api_key\s*=\s*["\']' <files>           # hardcoded keys
grep -nE 'sk-[a-zA-Z0-9_-]{20,}' <files>          # leaked keys
grep -nE 'os\.getenv\([^)]+,\s*["\'][^"\']' <files>  # default fallbacks
```

Findings:
- Any literal API key in source → `CRITICAL`, stop, advise revocation
- `os.getenv("KEY", "fallback-value")` with a non-empty fallback → `WARN`
- Logging that includes secrets / `print(settings)` → `WARN`

→ See `concepts/secrets-and-key-rotation.md`

### 2. Async correctness — HIGH

For each `async def` function:
- Does it call `time.sleep()`? → `WARN`, replace with `await asyncio.sleep()`
- Does it call a sync SDK (`Anthropic()` not `AsyncAnthropic()`)? → `WARN`, fix or wrap with `asyncio.to_thread`
- Does it `except asyncio.CancelledError: pass` or swallow? → `WARN`, must re-raise
- Does it have an unbounded `asyncio.gather(...)` over user input? → `WARN`, bound with semaphore

→ See `concepts/async-await-fundamentals.md`

### 3. Retry policy — HIGH

For each `@retry(...)` or call to `client.messages.create`:
- Is `stop_after_attempt(N)` set? Bare `retry()` (infinite) → `WARN`
- Is `retry_if_exception_type` narrow? Bare `Exception` → `WARN`
- Does it retry on 4xx other than 429? → `WARN`, wastes tokens
- Is `wait_exponential` or `wait_random_exponential` used? Fixed wait → `INFO`

→ See `concepts/retry-patterns-llm.md`

### 4. Timeouts — HIGH

For each LLM client construction:
- Is `timeout=` set? Default (no timeout) → `WARN`
- For streaming: is the stream wrapped in `asyncio.timeout(...)`? → `WARN` if not

→ See `patterns/anthropic-client-async-wrapper.md`, `patterns/streaming-responses.md`

### 5. Tool-use loops — HIGH

For each agentic loop (a call to `messages.create` followed by inspection of `tool_use`):
- Is there a `max_iterations` guard? `while True:` → `WARN`
- Does every `tool_use` get a matching `tool_result`? → API requirement
- Are tool errors caught per-tool (returned as `is_error: true`) or do they crash the loop? → `WARN` if crashes
- Does the loop stop on `stop_reason == "end_turn"`? Other stop reasons handled? → `INFO`

→ See `patterns/tool-use-loop.md`

### 6. Structured output validation — MEDIUM

Where the code parses LLM output:
- Is there a Pydantic model? `json.loads()` alone → `WARN`
- Does the model have `Field(...)` constraints? Bare types → `INFO`
- On `ValidationError`, is there a repair loop or typed exception? `except: return None` → `WARN`
- Schema is `dict[str, Any]`? → `WARN`

→ See `concepts/pydantic-v2-structured-output.md`, `patterns/instructor-structured-extraction.md`

### 7. Cost tracking — MEDIUM

For each LLM call site:
- Is `usage` from the response logged? → `WARN` if missing
- For repeated calls with the same system prompt: is prompt caching used? → `INFO`, opportunity
- Is there a budget guard for user input that goes into the prompt? → `INFO`

→ See `concepts/cost-tracking-tokens.md`

### 8. Type safety — MEDIUM

```bash
uv run mypy --strict src/
```

- Any errors in new code? → `WARN`
- `# type: ignore` without an error code? → `WARN`
- `def f(x):` (no hints) in production code? → `WARN`
- `Any` in return types of public APIs? → `INFO`

→ See `concepts/type-safety-python.md`

### 9. Testing — MEDIUM

- Is there at least one test for every public function in changed files?
- Do tests call the real API by default (no `pytest.mark.eval` gate)? → `WARN`
- Are LLM mocks returning realistic SDK objects, or raw dicts? → `INFO`
- Float comparisons use `pytest.approx` or tolerance? → `INFO`

→ See `concepts/testing-llm-code.md`, `patterns/eval-with-pytest.md`

### 10. General Python hygiene — LOW

- `except:` or `except Exception: pass` → `WARN`
- Mutable default arguments (`def f(x=[])`) → `WARN`
- `%` or `.format()` instead of f-strings (in new code) → `INFO`
- `os.path` instead of `pathlib` in new code → `INFO`
- `print()` for logging in non-CLI code → `INFO`

→ See `anti-patterns.md`

## Output format

Report findings as:

```
findings:
  - severity: CRITICAL
    target: src/agent/client.py:42
    rule: hardcoded-api-key
    message: API key literal in source. Replace with os.environ["..."].
    fix: |
      - api_key = "sk-ant-..."
      + api_key = os.environ["ANTHROPIC_API_KEY"]
    related: concepts/secrets-and-key-rotation.md

  - severity: WARN
    target: src/agent/loop.py:18
    rule: unbounded-tool-loop
    message: while True without max_iterations cap. Risk of runaway cost.
    fix: |
      Add max_iterations=10 (or task-appropriate value), break when reached,
      log the early termination.
    related: patterns/tool-use-loop.md
```

## Severity guide

| Severity | Meaning | Examples |
|---|---|---|
| `CRITICAL` | Security risk or guaranteed failure mode | Hardcoded keys, secrets in logs, ACL bypass |
| `WARN` | High likelihood of bugs / cost in production | Missing retries, bare except, unbounded loops, no timeout |
| `INFO` | Style / opportunity, not a bug | Could use prompt caching, could be more typed |

## When to BLOCK

If the user asks "review this" with no file paths, return BLOCKED:

```
status: BLOCKED
reason: No target files specified. Provide one or more .py file paths.
```

If the file fails to parse as Python:

```
status: BLOCKED
reason: SyntaxError at <file>:<line>: <message>
```

## Done when

- Every checklist section was applied
- Each finding has a target (file:line) and a fix suggestion
- Findings are sorted by severity
- A summary line states the count by severity
- For each finding, a related KB file is linked

## Anti-patterns when reviewing

- Repeating findings — group duplicates as "found in N places"
- "Looks good" with no walk-through — show what you checked
- Subjective style preferences flagged as `WARN` (use `INFO`)
- Skipping the security checks — those are non-negotiable

## See also

- `anti-patterns.md` — the full reference list
- All `concepts/*.md` and `patterns/*.md` for the referenced rules
