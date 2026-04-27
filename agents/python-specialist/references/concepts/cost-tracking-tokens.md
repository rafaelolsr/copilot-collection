# Cost & token accounting for LLM calls

> **Last validated**: 2026-04-26
> **Confidence**: 0.90
> **Source**: https://platform.claude.com/docs/en/api/

## Why this matters

LLM costs scale linearly with tokens. A small change (verbose system prompt, accidentally including chat history, no caching) can 5–10× the bill before anyone notices. Production code MUST track per-call cost.

## Token accounting basics

Most providers charge differently for input vs. output tokens, plus a discounted rate for cached input:

| Component | Typical relative cost |
|---|---|
| Input tokens (uncached) | 1× |
| Cached input tokens (read) | ~0.1× |
| Cached input tokens (write — first time) | 1.25× |
| Output tokens | ~5× |

So if you have a 5,000-token system prompt + tools schema, caching it saves ~88% on every subsequent call.

## Where to get usage data

Every modern LLM SDK returns token counts on the response:

```python
response = await client.messages.create(...)

usage = response.usage
# usage.input_tokens
# usage.output_tokens
# usage.cache_creation_input_tokens   (Anthropic prompt caching)
# usage.cache_read_input_tokens       (Anthropic prompt caching)
```

For OpenAI:
```python
usage = response.usage
# usage.prompt_tokens
# usage.completion_tokens
# usage.prompt_tokens_details.cached_tokens
```

Always log this — never just the response text.

## Cost calculator

Hardcode current per-million-token prices in a Python module, not in business logic. Update when prices change.

```python
from dataclasses import dataclass
from typing import TypedDict

@dataclass(frozen=True)
class ModelPricing:
    input_per_mtok: float
    output_per_mtok: float
    cache_read_per_mtok: float
    cache_write_per_mtok: float

PRICING: dict[str, ModelPricing] = {
    "claude-sonnet-4-5": ModelPricing(3.0, 15.0, 0.30, 3.75),
    "claude-opus-4-1":   ModelPricing(15.0, 75.0, 1.50, 18.75),
    "claude-haiku-4-5":  ModelPricing(1.0, 5.0, 0.10, 1.25),
}

def calc_cost(model: str, usage) -> float:
    p = PRICING[model]
    return (
        usage.input_tokens * p.input_per_mtok / 1_000_000
        + usage.output_tokens * p.output_per_mtok / 1_000_000
        + getattr(usage, "cache_read_input_tokens", 0) * p.cache_read_per_mtok / 1_000_000
        + getattr(usage, "cache_creation_input_tokens", 0) * p.cache_write_per_mtok / 1_000_000
    )
```

## Tracking middleware pattern

Wrap the SDK call so cost tracking happens once, not at every call site:

```python
import logging
from contextlib import contextmanager

logger = logging.getLogger(__name__)

class TrackedClient:
    def __init__(self, raw_client, on_call=None):
        self._client = raw_client
        self._on_call = on_call or self._default_on_call

    async def messages_create(self, **kwargs):
        response = await self._client.messages.create(**kwargs)
        cost = calc_cost(kwargs["model"], response.usage)
        self._on_call(model=kwargs["model"], usage=response.usage, cost_usd=cost)
        return response

    def _default_on_call(self, model, usage, cost_usd):
        logger.info(
            "llm_call",
            extra={
                "model": model,
                "input_tokens": usage.input_tokens,
                "output_tokens": usage.output_tokens,
                "cost_usd": round(cost_usd, 6),
            },
        )
```

Inject `on_call` to push to App Insights, Prometheus, a billing system — wherever you aggregate.

## Token budget guards

For untrusted input (user-generated text, RAG context), guard against pathological cases:

```python
def estimate_tokens(text: str) -> int:
    # Rough rule: 1 token ≈ 4 chars for English. Use tiktoken for precision.
    return len(text) // 4

def check_budget(prompt: str, context: list[str], max_input_tokens: int = 100_000):
    total = estimate_tokens(prompt) + sum(estimate_tokens(c) for c in context)
    if total > max_input_tokens:
        raise BudgetExceededError(f"Estimated {total} tokens, limit {max_input_tokens}")
```

For exact counts, use `anthropic.Anthropic().beta.messages.count_tokens()` or `tiktoken` (OpenAI).

## Prompt caching — the easy 80% win

Anthropic's prompt caching: mark a section as cacheable, get ~10× cost reduction on repeated calls within 5 min:

```python
response = await client.messages.create(
    model="claude-sonnet-4-5",
    system=[
        {
            "type": "text",
            "text": LONG_SYSTEM_PROMPT,  # the bulk of your prompt
            "cache_control": {"type": "ephemeral"},
        },
    ],
    messages=[{"role": "user", "content": user_message}],
    max_tokens=1024,
)
```

Place the cache breakpoint **after** stable content, **before** variable content. Order: tools → system → conversation history. Don't cache the user message itself — it changes every call.

## Anti-patterns to flag

- No usage logging on production LLM calls
- Hardcoded cost per call (wrong as soon as prices change)
- Cost calculation duplicated in 5 places (extract to a single function)
- No prompt caching on a >2000-token system prompt that's reused
- No budget guard on user-uploaded text
- Logging full prompts/responses (PII risk + huge log volume) — log token counts only

## See also

- `patterns/anthropic-client-async-wrapper.md` — wrapper with built-in cost tracking
- `concepts/secrets-and-key-rotation.md` — billing API keys go in env vars too
- `anti-patterns.md` (item 17)
