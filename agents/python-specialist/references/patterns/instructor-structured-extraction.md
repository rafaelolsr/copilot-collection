# Structured extraction with `instructor` + Pydantic

> **Last validated**: 2026-04-27
> **Confidence**: 0.91
> **Source**: https://python.useinstructor.com/

## When to use this pattern

You need an LLM to return data conforming to a Pydantic schema, with automatic repair on validation failure. Saves the boilerplate of manual JSON parsing + retry loops.

## Implementation

```python
"""Extract structured data from LLM with auto-repair on ValidationError."""
from __future__ import annotations

import logging
from typing import TypeVar

from my_app import llm_client  # vendor-neutral wrapper
import instructor
from pydantic import BaseModel, Field, ValidationError

logger = logging.getLogger(__name__)
T = TypeVar("T", bound=BaseModel)


# ---------- Example schema ----------

class LineItem(BaseModel):
    description: str = Field(..., min_length=1, max_length=500)
    quantity: int = Field(..., gt=0)
    unit_price: float = Field(..., ge=0)


class Invoice(BaseModel):
    invoice_number: str = Field(..., pattern=r"^[A-Z]{2,4}-\d{4,8}$")
    issued_at: str = Field(..., description="ISO 8601 date, YYYY-MM-DD")
    vendor: str = Field(..., min_length=1)
    total: float = Field(..., gt=0)
    line_items: list[LineItem] = Field(default_factory=list, max_length=200)


# ---------- Extractor ----------

class StructuredExtractor:
    """Extract Pydantic-validated data from text via the configured LLM."""

    def __init__(
        self,
        client: llm_client.AsyncLLMClient | None = None,
        *,
        model: str = "<provider>-balanced",
        max_retries: int = 3,
    ) -> None:
        raw = client or llm_client.AsyncLLMClient()
        # instructor.from_openai returns an instrumented client that
        # accepts response_model= and handles repair loops internally.
        self._client = instructor.from_openai(raw, mode=instructor.Mode.TOOLS)
        self._model = model
        self._max_retries = max_retries

    async def extract(
        self,
        text: str,
        response_model: type[T],
        *,
        system: str | None = None,
    ) -> T:
        return await self._client.messages.create(
            model=self._model,
            max_tokens=2048,
            max_retries=self._max_retries,
            system=system or "Extract structured data from the user's text.",
            messages=[{"role": "user", "content": text}],
            response_model=response_model,
        )
```

## Example usage

```python
import asyncio

async def main() -> None:
    extractor = StructuredExtractor()
    invoice = await extractor.extract(
        text="Invoice INV-12345 issued 2026-04-15 from Acme Corp. "
             "Total: $99.99. 1× Widget @ $99.99.",
        response_model=Invoice,
    )
    print(invoice.invoice_number)  # "INV-12345"
    print(invoice.line_items[0].quantity)  # 1

asyncio.run(main())
```

## How the repair loop works

`instructor` wraps `client.messages.create` and:

1. Generates a tool definition from your Pydantic schema
2. Asks the model to call that tool
3. If the response fails validation → re-prompts with the validation error appended
4. Up to `max_retries` times, then raises `instructor.exceptions.InstructorRetryException`

You don't write the repair loop manually.

## Why a `response_model` is better than `json.loads`

```python
# WRONG — fragile
raw = await client.messages.create(...)
data = json.loads(raw.content[0].text)  # KeyError, ValueError, anything goes
amount = data["amount"]  # might be missing, might be a string

# CORRECT — validated
invoice = await extractor.extract(text, response_model=Invoice)
amount: float = invoice.total  # statically and runtime-typed
```

## Configuration

| Argument | Default | When to override |
|---|---|---|
| `model` | `<provider>-balanced` | Use opus for complex schemas; haiku for simple |
| `max_retries` | `3` | Raise to 5 for high-stakes extraction; lower to 1 if you'd rather fail fast |
| `mode` | `TOOLS` | Use `JSON` if you don't want tool-shaped output |

## Validators help the repair loop

Field-level validators give the LLM precise feedback on failure:

```python
from pydantic import field_validator

class Invoice(BaseModel):
    issued_at: str

    @field_validator("issued_at")
    @classmethod
    def must_be_iso(cls, v: str) -> str:
        from datetime import date
        try:
            date.fromisoformat(v)
        except ValueError:
            raise ValueError(f"'{v}' is not a valid ISO date (YYYY-MM-DD)")
        return v
```

When the LLM returns `"April 15, 2026"`, the error message tells it exactly what format to use.

## Done when

- Pydantic model has Field constraints, not bare types
- Validators catch missing/extra fields
- `max_retries` set explicitly
- Final failure raises a typed exception (not silent `None`)
- Test exists with a malformed response that exercises the repair loop

## Anti-patterns

- Schema is `dict[str, Any]` (no validation; defeats the purpose)
- Catching `ValidationError` and returning `None` (bug-hiding)
- Schemas with no `description` on fields (LLM has nothing to ground on)
- `max_retries=10` (waste of money — if 3 retries fail, the prompt is wrong)
- Mixing `instructor` and manual `json.loads` in the same codebase

## See also

- `concepts/pydantic-v2-structured-output.md` — schema design fundamentals
- `patterns/llm-client-async-wrapper.md` — pair with the wrapper for cost tracking
- `anti-patterns.md` (items 14, 15)
