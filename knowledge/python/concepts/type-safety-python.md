# Type safety in Python — what mypy --strict catches

> **Last validated**: 2026-04-26
> **Confidence**: 0.94
> **Sources**: https://mypy.readthedocs.io/, https://typing.python.org/

## Why strict typing for AI code

LLM responses are the largest source of unexpected types in your program (the LLM might return `null`, an empty list, a string instead of a number). Strict typing catches mismatches at lint time instead of in production traces.

Target: `mypy --strict` passes on all new code.

## Type hints checklist

```python
# Functions: every parameter and return value
def process(items: list[str], max_items: int = 10) -> dict[str, int]: ...

# Async: same, plus the return is awaitable
async def fetch(url: str) -> bytes: ...

# Optional values: use `T | None`, not `Optional[T]` (3.10+)
def find(name: str) -> User | None: ...

# Constants
MAX_RETRIES: int = 5
DEFAULT_MODEL: Final[str] = "claude-sonnet-4-5"
```

## Protocols — duck typing with structure

When you want "anything with a `messages.create()` method", use `Protocol`:

```python
from typing import Protocol

class LLMClient(Protocol):
    async def create_message(self, prompt: str) -> str: ...

# Now any class with that method matches LLMClient,
# without inheritance
class AnthropicWrapper:
    async def create_message(self, prompt: str) -> str:
        ...

def use_client(client: LLMClient) -> None:
    ...

use_client(AnthropicWrapper())  # OK
```

This is how to write testable LLM code: depend on a `Protocol`, inject a real client in production and a mock in tests.

## TypedDict — typing dict-shaped data

Useful when interfacing with libraries that return dicts:

```python
from typing import TypedDict

class TokenUsage(TypedDict):
    input_tokens: int
    output_tokens: int
    cache_read_tokens: int

def track_cost(usage: TokenUsage) -> float:
    return usage["input_tokens"] * 0.000003 + usage["output_tokens"] * 0.000015
```

For new code prefer Pydantic or `@dataclass` — TypedDict is best for typing legacy/external dict APIs.

## Generics

```python
from typing import TypeVar

T = TypeVar("T")

async def with_retry(fn: Callable[..., Awaitable[T]], *args, **kwargs) -> T:
    for attempt in range(3):
        try:
            return await fn(*args, **kwargs)
        except TransientError:
            await asyncio.sleep(2 ** attempt)
    raise
```

`T` lets the function preserve its input/output type. Without it, you'd return `Any`.

## Overloads

When a function returns different types based on arguments:

```python
from typing import overload, Literal

@overload
def parse(text: str, *, raw: Literal[False] = False) -> ParsedDoc: ...

@overload
def parse(text: str, *, raw: Literal[True]) -> str: ...

def parse(text: str, *, raw: bool = False) -> ParsedDoc | str:
    if raw:
        return text
    return ParsedDoc.from_text(text)
```

Now `parse(t)` returns `ParsedDoc` and `parse(t, raw=True)` returns `str` — the type checker knows which.

## `# type: ignore` — narrowly

Allowed only with a specific error code and a comment explaining why:

```python
result = legacy_lib.thing()  # type: ignore[no-untyped-call]  # legacy lib has no stubs
```

Bare `# type: ignore` should fail review. So should `Any`-typed parameters in new code.

## `Final` and `Literal`

```python
from typing import Final, Literal

MAX_TOKENS: Final = 4096  # cannot be reassigned
Model = Literal["claude-sonnet-4-5", "claude-opus-4-1", "gpt-4.1"]

def call(model: Model, prompt: str) -> str: ...

call("claude-sonnet-4-5", "hi")  # OK
call("gpt-3.5", "hi")  # mypy error — not in Literal
```

`Literal` is your friend for model names, status enums, anything from a closed set.

## Strict mode flags worth knowing

In `pyproject.toml`:

```toml
[tool.mypy]
strict = true
warn_unused_ignores = true
warn_redundant_casts = true
disallow_any_generics = true
disallow_untyped_calls = true
disallow_untyped_defs = true
no_implicit_optional = true
```

`strict = true` is shorthand for most of these — but listing them documents intent for new contributors.

## Anti-patterns to flag

- `def f(x):` (no type hints) in new code
- `def f(x: Any) -> Any:` in production code
- `# type: ignore` without an error code or comment
- `from typing import Optional, List, Dict` (3.9 style) — use builtins (`list`, `dict`) and `T | None`
- TypedDict for data the program owns end-to-end (use Pydantic / dataclass)

## See also

- `concepts/pydantic-v2-structured-output.md` — for runtime validation
- `concepts/async-await-fundamentals.md` — async type signatures
- `anti-patterns.md` (item 16)
