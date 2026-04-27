# Python (AI/LLM) — Anti-Patterns

> **Last validated**: 2026-04-26
> **Confidence**: 0.93
> Wrong / Correct pairs for every anti-pattern the agent flags on sight.

---

## 1. Hardcoded API keys

Wrong:
```python
client = llm_client.AsyncLLMClient(api_key="sk-ant-abc123...")
```

Why: keys leak into git, logs, and Slack messages. Once leaked, they must be revoked — and 12-factor apps don't deploy keys via code.

Correct:
```python
import os
client = llm_client.AsyncLLMClient(api_key=os.environ["LLM_API_KEY"])
```

Related: `concepts/secrets-and-key-rotation.md`

---

## 2. Default fallback for required keys

Wrong:
```python
api_key = os.getenv("LLM_API_KEY", "sk-ant-fallback-key")
```

Why: fallback survives leaks. `os.environ[KEY]` fails fast at startup.

Correct:
```python
api_key = os.environ["LLM_API_KEY"]  # KeyError if missing
```

---

## 3. Mutable default arguments

Wrong:
```python
def append_item(item, items=[]):
    items.append(item)
    return items
```

Why: list is shared across all calls. Classic Python gotcha.

Correct:
```python
def append_item(item, items=None):
    if items is None:
        items = []
    items.append(item)
    return items
```

---

## 4. Bare `except:`

Wrong:
```python
try:
    response = await client.messages.create(...)
except:
    return None
```

Why: catches `KeyboardInterrupt`, `SystemExit`, `MemoryError`. Hides bugs.

Correct:
```python
except (httpx.HTTPStatusError, httpx.HTTPError) as exc:
    logger.exception("llm_failed")
    raise
```

---

## 5. `except Exception: pass`

Wrong:
```python
try:
    parsed = Invoice.model_validate_json(raw)
except Exception:
    pass
```

Why: silently discards every failure mode. Bug-hiding par excellence.

Correct: Either re-raise after logging, or catch specifically:
```python
try:
    parsed = Invoice.model_validate_json(raw)
except ValidationError as exc:
    logger.warning("invalid_invoice", extra={"errors": exc.errors()})
    raise InvalidInvoiceError(str(exc)) from exc
```

---

## 6. `time.sleep()` in async code

Wrong:
```python
async def poll():
    while not done():
        time.sleep(1)  # BLOCKS the event loop
```

Correct:
```python
async def poll():
    while not done():
        await asyncio.sleep(1)
```

Related: `concepts/async-await-fundamentals.md`

---

## 7. Sync SDK in async function

Wrong:
```python
async def call_llm(prompt: str) -> str:
    client = llm_client.LLMClient()  # sync client
    response = client.messages.create(...)  # blocks event loop
    return response.content[0].text
```

Correct:
```python
async def call_llm(prompt: str) -> str:
    client = llm_client.AsyncLLMClient()
    response = await client.messages.create(...)
    return response.content[0].text
```

---

## 8. Swallowing `CancelledError`

Wrong:
```python
async def long_task():
    try:
        await something_slow()
    except asyncio.CancelledError:
        pass  # breaks structured concurrency
```

Correct:
```python
async def long_task():
    try:
        await something_slow()
    except asyncio.CancelledError:
        await cleanup()
        raise
```

---

## 9. Retrying on 4xx errors

Wrong:
```python
@retry(stop=stop_after_attempt(5), retry=retry_if_exception_type(Exception))
async def call_llm():
    return await client.messages.create(...)  # retries even 400, 401, 403
```

Why: 4xx errors won't fix themselves on retry — wastes tokens and money.

Correct:
```python
def is_transient(exc):
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.status_code in {429, 500, 502, 503, 504, 529}
    return isinstance(exc, (httpx.TimeoutException, httpx.ConnectError))

@retry(stop=stop_after_attempt(5), retry=retry_if_exception(is_transient))
async def call_llm(): ...
```

Related: `concepts/retry-patterns-llm.md`

---

## 10. No timeout on LLM calls

Wrong:
```python
client = llm_client.AsyncLLMClient()
response = await client.messages.create(...)  # could hang indefinitely
```

Correct:
```python
client = llm_client.AsyncLLMClient(timeout=30.0)
# or per-call:
async with asyncio.timeout(30):
    response = await client.messages.create(...)
```

---

## 11. Logging full prompts/responses

Wrong:
```python
logger.info(f"Calling LLM with prompt: {full_prompt}")
logger.info(f"Response: {response.content}")
```

Why: PII leak, log size explosion, security review failure.

Correct:
```python
logger.info(
    "llm_call",
    extra={
        "model": model,
        "prompt_tokens": usage.input_tokens,
        "response_tokens": usage.output_tokens,
        "first_50_chars": full_prompt[:50],
    },
)
```

---

## 12. Unbounded tool-use loop

Wrong:
```python
while True:
    response = await client.messages.create(...)
    if response.stop_reason == "end_turn":
        break
    # tool dispatch...
```

Why: a confused model can keep calling tools forever. Cost and latency disaster.

Correct:
```python
for iteration in range(max_iterations):
    response = await client.messages.create(...)
    if response.stop_reason == "end_turn":
        return ...
    # tool dispatch...
logger.warning("max_iterations_reached")
```

Related: `patterns/tool-use-loop.md`

---

## 13. Tool errors that crash the loop

Wrong:
```python
for tool_use in response.content:
    result = tool_handlers[tool_use.name](tool_use.input)  # raises → loop dies
```

Correct:
```python
for tool_use in response.content:
    try:
        result = await tool_handlers[tool_use.name](tool_use.input)
        results.append({"type": "tool_result", "tool_use_id": tool_use.id, "content": result})
    except Exception as exc:
        results.append({
            "type": "tool_result",
            "tool_use_id": tool_use.id,
            "content": f"ERROR: {exc}",
            "is_error": True,
        })
```

---

## 14. `dict[str, Any]` from LLM call

Wrong:
```python
async def extract(text: str) -> dict[str, Any]:
    response = await client.messages.create(...)
    return json.loads(response.content[0].text)  # KeyError land
```

Correct:
```python
async def extract(text: str) -> Invoice:  # Pydantic model
    extractor = StructuredExtractor()
    return await extractor.extract(text, response_model=Invoice)
```

Related: `concepts/pydantic-v2-structured-output.md`

---

## 15. `json.loads` with no validation

Wrong:
```python
data = json.loads(response.content[0].text)
amount = data["amount"]  # might not exist, might be a string
```

Correct: use a Pydantic model. See item 14.

---

## 16. Missing type hints in new code

Wrong:
```python
def process(items, max_items=10):
    return [run(i) for i in items[:max_items]]
```

Correct:
```python
def process(items: list[str], max_items: int = 10) -> list[Result]:
    return [run(i) for i in items[:max_items]]
```

Related: `concepts/type-safety-python.md`

---

## 17. No cost / token logging on production calls

Wrong:
```python
response = await client.messages.create(...)
return response.content[0].text  # cost? we'll never know
```

Correct:
```python
response = await client.messages.create(...)
logger.info(
    "llm_call",
    extra={
        "model": model,
        "input_tokens": response.usage.input_tokens,
        "output_tokens": response.usage.output_tokens,
        "cost_usd": calc_cost(model, response.usage),
    },
)
return response.content[0].text
```

Related: `concepts/cost-tracking-tokens.md`

---

## 18. Tests hit real API by default

Wrong:
```python
async def test_extract():
    client = llm_client.AsyncLLMClient()  # real client, real cost
    result = await extract(client, "test")
    assert result.amount > 0
```

Correct:
```python
@pytest.mark.eval  # opt-in marker, excluded from default runs
async def test_extract_eval(real_llm_client):
    result = await extract(real_llm_client, "test")
    assert result.amount > 0

# fast unit version with mock:
async def test_extract_unit(mock_llm_client):
    result = await extract(mock_llm_client, "test")
    assert mock_llm_client.messages.create.called
```

Related: `concepts/testing-llm-code.md`

---

## 19. Strict equality on stochastic LLM output

Wrong:
```python
assert summary == "expected exact summary text"
```

Correct: use a tolerance band, similarity score, or LLM-judge.
```python
assert similarity_score(summary, expected) > 0.85
# or:
assert await llm_judge(summary, criteria) >= 4
```

---

## 20. `print()` for production logging

Wrong:
```python
print(f"Processing {item}")
```

Correct:
```python
import logging
logger = logging.getLogger(__name__)
logger.info("processing", extra={"item": item})
```

---

## 21. `os.path` in new Python code

Wrong:
```python
import os
path = os.path.join(os.path.dirname(__file__), "data", "input.json")
with open(path) as f:
    data = json.load(f)
```

Correct:
```python
from pathlib import Path
path = Path(__file__).parent / "data" / "input.json"
data = json.loads(path.read_text())
```

---

## 22. `from module import *`

Wrong:
```python
from my_lib import *
```

Why: pollutes namespace, breaks linters, hides where things came from.

Correct:
```python
from my_lib import specific_thing, OtherThing
```

---

## See also

- `index.md` — KB navigation
- `patterns/code-review-checklist.md` — how to apply this list during reviews
