# Pydantic v2 — structured output for LLMs

> **Last validated**: 2026-04-26
> **Confidence**: 0.95
> **Source**: https://docs.pydantic.dev/latest/

## Why Pydantic for LLM output

LLMs return free-form text. To use that text reliably, you need a parser that:
1. Validates types and constraints
2. Catches missing/extra fields
3. Coerces obvious mismatches (str → int when unambiguous)
4. Surfaces precise errors that can be fed back to the model for repair

Pydantic v2 does all of this with ~10× the speed of v1 (rewritten in Rust).

## Basic model

```python
from pydantic import BaseModel, Field
from typing import Literal

class Invoice(BaseModel):
    invoice_number: str = Field(..., pattern=r"^INV-\d{6}$")
    amount: float = Field(..., gt=0, description="Total amount in USD")
    currency: Literal["USD", "EUR", "GBP"] = "USD"
    line_items: list[str] = Field(default_factory=list, max_length=100)
```

`Field(...)` makes a field required. Constraints (`pattern`, `gt`, `max_length`) are enforced at construction. `description` becomes the JSON schema description that the LLM sees.

## Validators

Use `@field_validator` for single-field rules and `@model_validator` for cross-field rules:

```python
from pydantic import BaseModel, field_validator, model_validator

class DateRange(BaseModel):
    start: str
    end: str

    @field_validator("start", "end")
    @classmethod
    def must_be_iso_date(cls, v: str) -> str:
        from datetime import date
        date.fromisoformat(v)  # raises ValueError if invalid
        return v

    @model_validator(mode="after")
    def end_after_start(self) -> "DateRange":
        if self.end < self.start:
            raise ValueError("end must be >= start")
        return self
```

## BaseModel vs dataclass vs TypedDict

| Use | When |
|---|---|
| `BaseModel` | LLM output, API request/response, anything coming from outside the program |
| `@dataclass` | Internal data structures with no validation needed |
| `TypedDict` | Typing existing dict-shaped data (legacy code, JSON imports) |

For LLM output: **always BaseModel**. The validation is the whole point.

## Strict mode

By default Pydantic coerces `"5"` → `5`. For LLM output where the model might emit a string when you wanted an int, this is usually fine. For higher-stakes validation, use strict types:

```python
from pydantic import BaseModel, StrictInt

class Config(BaseModel):
    count: StrictInt  # rejects "5" — must be actual int
```

## Repair loops

When LLM output fails validation, feed the error back to the model:

```python
from pydantic import ValidationError

def extract_with_repair(prompt: str, max_retries: int = 3) -> Invoice:
    error_context = ""
    for attempt in range(max_retries):
        raw = llm_call(prompt + error_context)
        try:
            return Invoice.model_validate_json(raw)
        except ValidationError as e:
            error_context = (
                f"\n\nPrevious attempt failed validation:\n{e}\n"
                f"Return valid JSON matching the Invoice schema."
            )
    raise RuntimeError(f"Validation failed after {max_retries} attempts")
```

The `instructor` library (see `patterns/instructor-structured-extraction.md`) automates this loop.

## JSON schema for the LLM

Most LLM SDKs accept a JSON schema for structured output. Generate it from your model:

```python
schema = Invoice.model_json_schema()
# Pass schema to the LLM (e.g., Anthropic tool, OpenAI response_format)
```

## Serialization

```python
inv = Invoice(invoice_number="INV-000001", amount=99.99)

inv.model_dump()           # dict
inv.model_dump_json()      # JSON string
inv.model_dump(mode="json") # dict with JSON-serializable values (datetime → str, etc.)
```

## Anti-patterns to flag

- `dict[str, Any]` as return type from an LLM call (no validation)
- `json.loads()` on LLM output without a Pydantic model
- Catching `ValidationError` and silently returning `None` (hides bugs)
- Pydantic v1 syntax (`@validator` instead of `@field_validator`, `class Config:` instead of `model_config = ConfigDict(...)`)
- Using `dict` or `Any` in model fields when a `Literal` or `Enum` would be tighter

## See also

- `patterns/instructor-structured-extraction.md` — production extraction with repair
- `anti-patterns.md` (items 14, 15)
