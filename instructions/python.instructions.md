---
name: python
description: |
  Coding standards for Python in this project. Auto-applied when Copilot
  is working on Python files. Enforces uv (not pip), ruff (lint+format),
  mypy --strict, pytest with markers, async-first for I/O, Pydantic v2
  for structured data, no PATs / hardcoded secrets.
applyTo: "**/*.py,pyproject.toml,uv.lock"
---

# Python coding standards

When generating, modifying, or reviewing Python code in this project, follow
these standards. They reflect the choices already in place — deviating from
them creates inconsistency the team will have to clean up.

## Tooling baseline

| Concern | Tool | Version pin |
|---|---|---|
| Package manager | **uv** (not pip directly) | latest |
| Linter | **ruff** (replaces flake8 + isort + pyupgrade) | >=0.6.0 |
| Formatter | **ruff format** (replaces black) | >=0.6.0 |
| Type checker | **mypy** with `strict = true` | >=1.11.0 |
| Test runner | **pytest** with `asyncio_mode = "auto"` | >=8.0.0 |
| Build backend | **hatchling** | latest |
| Python version | 3.12 minimum, 3.13 preferred | — |

Commands you run from the project root:

```bash
uv sync                                  # install dependencies
uv run pytest -m "not eval"              # fast tests
uv run pytest -m "eval and smoke"        # smoke evals
uv run ruff check                        # lint
uv run ruff format                       # format
uv run mypy src/                         # type check
```

NEVER run `pip install`, `pipenv`, `poetry add` in this project. uv is the
single source of truth.

## Type hints — required on public APIs

Every public function (one not prefixed `_`) MUST have:
- Type hints on every parameter
- Return type annotation
- mypy --strict passes

Modern syntax (Python 3.10+):
```python
# CORRECT
def find(name: str) -> User | None: ...
def process(items: list[str], max_items: int = 10) -> dict[str, int]: ...

# WRONG (legacy 3.9 style — don't use)
from typing import Optional, List, Dict
def find(name: str) -> Optional[User]: ...
def process(items: List[str], max_items: int = 10) -> Dict[str, int]: ...
```

`# type: ignore` requires:
1. Specific error code: `# type: ignore[no-untyped-call]`
2. Comment explaining WHY: `# legacy lib has no stubs`

`# type: ignore` alone (no code, no reason) fails review.

## async-first for I/O

Any function that does network / DB / file I/O MUST be async. No exceptions
in services intended to handle concurrent requests.

```python
# CORRECT
async def fetch_user(user_id: str) -> User:
    async with httpx.AsyncClient() as client:
        response = await client.get(f"/users/{user_id}")
    return User.model_validate_json(response.text)

# WRONG (blocks event loop)
def fetch_user(user_id: str) -> User:
    response = requests.get(f"/users/{user_id}")
    return User.model_validate_json(response.text)
```

Inside `async def`:
- ❌ `time.sleep(N)` — use `await asyncio.sleep(N)`
- ❌ `requests.get(...)` — use `httpx.AsyncClient`
- ❌ `client.messages.create(...)` (sync LLM SDK) — use the SDK's async variant
- ❌ blocking file I/O without `asyncio.to_thread`

## Structured data — Pydantic v2

For any data crossing a boundary (API request/response, LLM output, config,
inter-service messages):

```python
from pydantic import BaseModel, Field

class Invoice(BaseModel):
    invoice_number: str = Field(..., pattern=r"^INV-\d{6}$")
    amount: float = Field(..., gt=0)
    issued_at: str  # ISO 8601 date
```

Internal-only data structures: `@dataclass` with `slots=True` is fine.

NEVER:
- `dict[str, Any]` from external sources without validation
- `json.loads()` on LLM output without a Pydantic model
- Pydantic v1 syntax (`@validator`, `class Config:`)

## Retries — narrow and exponential

```python
from tenacity import (
    retry, stop_after_attempt, wait_exponential, retry_if_exception_type,
)
import httpx

@retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=1, min=2, max=60),
    retry=retry_if_exception_type((
        httpx.HTTPStatusError,
        httpx.TimeoutException,
        httpx.ConnectError,
    )),
    reraise=True,
)
async def call_api(...): ...
```

Rules:
- **Always** `stop_after_attempt(N)` — never unbounded retries
- **Never** `retry_if_exception_type(Exception)` — too broad
- **Never** retry 4xx errors other than 429 (wastes tokens / quota)
- Always exponential backoff with jitter (`wait_random_exponential`)

## Error handling

```python
# CORRECT — narrow, log context, re-raise
try:
    response = await llm_client.create(...)
except (httpx.HTTPStatusError, httpx.TimeoutException) as exc:
    logger.exception(
        "llm_call_failed",
        extra={"operation_id": op_id, "model": model_name},
    )
    raise

# WRONG — bare except, swallows
try:
    response = await llm_client.create(...)
except:
    return None
```

Forbidden patterns:
- `except:` (bare)
- `except Exception: pass` (silent swallow)
- Catching `KeyboardInterrupt`, `SystemExit`, `MemoryError` accidentally
- Logging error then returning None (caller can't tell something failed)

## Logging

Use `logging`, never `print()` in non-CLI code.

```python
import logging
logger = logging.getLogger(__name__)

# CORRECT
logger.info(
    "llm_call",
    extra={
        "model": model_name,
        "input_tokens": usage.input_tokens,
        "output_tokens": usage.output_tokens,
        "cost_usd": round(cost, 6),
    },
)

# WRONG
print(f"Calling LLM with model={model_name}")
logger.info(f"LLM call: prompt={full_prompt}")  # PII risk + log volume
```

Never log:
- Full prompts / responses (PII + volume)
- API keys, connection strings, tokens
- User PII (emails, names, IDs without redaction)

## Testing

```toml
# pyproject.toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
markers = [
    "eval: stochastic evals (slow, costs $)",
    "smoke: smoke-test eval subset",
    "full: full eval suite",
]
```

Test layout:
```
tests/
├── unit/                           # no network, no real API
└── eval/                           # @pytest.mark.eval — opt-in only
```

Tests that hit real APIs MUST be marker-gated:
```python
@pytest.mark.eval
@pytest.mark.smoke
async def test_real_extraction(real_llm_client):
    ...
```

Default `pytest` runs only unit. CI runs evals only with `-m eval`.

## Secrets

Never in source code:
```python
# WRONG
client = LLMClient(api_key="sk-live-...")
api_key = os.getenv("KEY", "sk-default-fallback")  # fallback survives leaks

# CORRECT
client = AsyncLLMClient(
    api_key=os.environ["LLM_API_KEY"],  # raises if missing — fail fast
)
```

For Azure: use `DefaultAzureCredential` over API keys / connection strings:

```python
from azure.identity import DefaultAzureCredential
from azure.ai.projects import AIProjectClient

cred = DefaultAzureCredential()
client = AIProjectClient(
    credential=cred,
    project_connection_string=os.environ["AZURE_AI_PROJECT_CONNECTION_STRING"],
)
```

## Common anti-patterns to flag

When reviewing Python in this project, flag immediately:

| Pattern | Severity |
|---|---|
| Hardcoded API key / secret | CRITICAL |
| Sync SDK call in `async def` | WARN |
| Mutable default argument (`def f(x=[])`) | WARN |
| Bare `except:` or `except Exception: pass` | WARN |
| `time.sleep()` in async | WARN |
| Missing timeout on LLM call | WARN |
| Retrying on 4xx (other than 429) | WARN |
| `dict[str, Any]` from LLM output (no validation) | WARN |
| Real API call in test without `@pytest.mark.eval` | WARN |
| `print()` for production logging | INFO |
| Missing type hints on public API | INFO |
| `os.path` instead of `pathlib` | INFO |
| `from module import *` at module level | INFO |
| %-formatting / `.format()` (use f-strings) | INFO |

## Module organization

`src/` layout (NOT flat):

```
my_project/
├── pyproject.toml
├── src/
│   └── my_project/
│       ├── __init__.py
│       ├── client.py
│       ├── handlers.py
│       └── ...
└── tests/
    ├── unit/
    └── eval/
```

`pyproject.toml` references `src/`:

```toml
[tool.hatch.build.targets.wheel]
packages = ["src/my_project"]
```

Why: prevents accidental imports of test code; enforces editable installs
to behave like real packages.

## See also

- `python-specialist` agent — for deeper Python design questions
- `code-review` skill — for systematic review including these standards
- `simplify` skill — for refactoring existing code
