# Anthropic async client wrapper — production-grade

> **Last validated**: 2026-04-27
> **Confidence**: 0.93

## When to use this pattern

Any production code that calls Claude. Wraps `AsyncAnthropic` with: timeout, retry on transient errors, cost tracking, structured logging, and dependency-injection friendliness.

## Implementation

```python
"""Production-grade async wrapper around the Anthropic SDK."""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Any, Protocol

import anthropic
import httpx
from tenacity import (
    AsyncRetrying,
    retry_if_exception,
    stop_after_attempt,
    wait_random_exponential,
    before_sleep_log,
)

logger = logging.getLogger(__name__)


# ---------- Pricing (update when Anthropic changes prices) ----------

@dataclass(frozen=True)
class ModelPricing:
    input_per_mtok: float
    output_per_mtok: float
    cache_read_per_mtok: float
    cache_write_per_mtok: float


PRICING: dict[str, ModelPricing] = {
    # Pricing per million tokens. Source: https://platform.claude.com/docs/en/about-claude/pricing
    # Last verified: 2026-04-27
    "claude-opus-4-7":   ModelPricing(input_per_mtok=5.0,  output_per_mtok=25.0, cache_read_per_mtok=0.50, cache_write_per_mtok=6.25),
    "claude-sonnet-4-6": ModelPricing(input_per_mtok=3.0,  output_per_mtok=15.0, cache_read_per_mtok=0.30, cache_write_per_mtok=3.75),
    "claude-haiku-4-5":  ModelPricing(input_per_mtok=1.0,  output_per_mtok=5.0,  cache_read_per_mtok=0.10, cache_write_per_mtok=1.25),
}


# ---------- Retry policy ----------

def _is_transient(exc: BaseException) -> bool:
    """Retry only on transient errors. 4xx other than 429 are NOT retryable."""
    if isinstance(exc, anthropic.APIStatusError):
        return exc.status_code in {429, 500, 502, 503, 504, 529}
    if isinstance(exc, (anthropic.APITimeoutError, anthropic.APIConnectionError)):
        return True
    if isinstance(exc, (httpx.TimeoutException, httpx.ConnectError)):
        return True
    return False


# ---------- Protocol for testability ----------

class CostHook(Protocol):
    def __call__(self, *, model: str, input_tokens: int, output_tokens: int,
                 cached_read: int, cached_write: int, cost_usd: float) -> None: ...


# ---------- Wrapper ----------

class ClaudeClient:
    """Async Claude client with retry, timeout, and cost tracking.

    Inject this into business logic. In tests, replace with a mock that
    matches the same `messages_create` signature.
    """

    def __init__(
        self,
        *,
        api_key: str | None = None,
        timeout: float = 30.0,
        max_retries: int = 4,
        cost_hook: CostHook | None = None,
    ) -> None:
        self._client = anthropic.AsyncAnthropic(
            api_key=api_key or os.environ["ANTHROPIC_API_KEY"],
            timeout=timeout,
            max_retries=0,  # we handle retries via tenacity
        )
        self._max_retries = max_retries
        self._cost_hook = cost_hook or _log_cost

    async def messages_create(self, **kwargs: Any) -> anthropic.types.Message:
        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(self._max_retries),
            wait=wait_random_exponential(min=2, max=60),
            retry=retry_if_exception(_is_transient),
            before_sleep=before_sleep_log(logger, logging.WARNING),
            reraise=True,
        ):
            with attempt:
                response = await self._client.messages.create(**kwargs)

        self._track(kwargs["model"], response.usage)
        return response

    def _track(self, model: str, usage: Any) -> None:
        p = PRICING.get(model)
        if p is None:
            logger.warning("unknown_model_for_pricing", extra={"model": model})
            return

        cached_read = getattr(usage, "cache_read_input_tokens", 0) or 0
        cached_write = getattr(usage, "cache_creation_input_tokens", 0) or 0

        cost = (
            usage.input_tokens * p.input_per_mtok / 1_000_000
            + usage.output_tokens * p.output_per_mtok / 1_000_000
            + cached_read * p.cache_read_per_mtok / 1_000_000
            + cached_write * p.cache_write_per_mtok / 1_000_000
        )

        self._cost_hook(
            model=model,
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            cached_read=cached_read,
            cached_write=cached_write,
            cost_usd=cost,
        )


def _log_cost(*, model: str, input_tokens: int, output_tokens: int,
              cached_read: int, cached_write: int, cost_usd: float) -> None:
    logger.info(
        "llm_call",
        extra={
            "model": model,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cached_read": cached_read,
            "cached_write": cached_write,
            "cost_usd": round(cost_usd, 6),
        },
    )
```

## Configuration

| Argument | Default | When to override |
|---|---|---|
| `api_key` | `$ANTHROPIC_API_KEY` | Multi-tenant apps with per-request keys |
| `timeout` | `30.0` | Long-running tool use (set 120) or strict SLOs (set 10) |
| `max_retries` | `4` | High-traffic services (lower to 2) or critical batch jobs (raise to 6) |
| `cost_hook` | logs to stdlib logger | Push to Application Insights / Prometheus |

## Example usage

```python
import asyncio

async def main() -> None:
    client = ClaudeClient(
        cost_hook=lambda **kw: print(f"${kw['cost_usd']:.4f}", kw["model"]),
    )
    response = await client.messages_create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        messages=[{"role": "user", "content": "Hello"}],
    )
    print(response.content[0].text)

asyncio.run(main())
```

## Testing

```python
import pytest
from unittest.mock import AsyncMock, MagicMock

@pytest.fixture
def fake_claude():
    fake = AsyncMock()
    fake.messages_create.return_value = MagicMock(
        content=[MagicMock(text="mocked reply")],
        usage=MagicMock(input_tokens=10, output_tokens=5),
    )
    return fake

@pytest.mark.asyncio
async def test_business_logic(fake_claude):
    result = await my_feature(client=fake_claude)
    assert "mocked" in result
```

## Done when

- mypy --strict passes
- ruff check passes
- Unit test exists and runs without network
- Logs emit `llm_call` events with cost on every successful call
- Retries don't fire on 400/401/403/404 (verify with a unit test that raises `APIStatusError(400)`)

## See also

- `concepts/retry-patterns-llm.md` — why this retry policy
- `concepts/cost-tracking-tokens.md` — cost calculation details
- `concepts/async-await-fundamentals.md` — async/await foundations
