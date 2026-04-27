# LLM async client wrapper — production-grade, vendor-neutral

> **Last validated**: 2026-04-27
> **Confidence**: 0.93
> **Sources**: https://www.python.org/, https://docs.pydantic.dev/, https://www.python-httpx.org/

## When to use

Any production code that calls a hosted LLM. This wrapper sits behind a
`LLMClient` Protocol so the rest of your code never imports a specific
vendor SDK — keeping providers swappable. The wrapper adds: timeout, retry
on transient errors, cost tracking, structured logging, and dependency-
injection friendliness.

## Pattern

```python
"""Production-grade async wrapper for any hosted LLM."""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Any, Protocol

import httpx
from tenacity import (
    AsyncRetrying, stop_after_attempt,
    wait_random_exponential, retry_if_exception,
)

logger = logging.getLogger(__name__)


# ---------- Pricing (update when your provider changes prices) ----------
@dataclass(frozen=True)
class ModelPricing:
    input_per_mtok: float
    output_per_mtok: float
    cache_read_per_mtok: float = 0.0
    cache_write_per_mtok: float = 0.0


# Per million tokens. Replace with your provider's published pricing.
PRICING: dict[str, ModelPricing] = {
    "<provider>-flagship": ModelPricing(input_per_mtok=5.0,  output_per_mtok=25.0, cache_read_per_mtok=0.50, cache_write_per_mtok=6.25),
    "<provider>-balanced": ModelPricing(input_per_mtok=3.0,  output_per_mtok=15.0, cache_read_per_mtok=0.30, cache_write_per_mtok=3.75),
    "<provider>-fast":     ModelPricing(input_per_mtok=1.0,  output_per_mtok=5.0,  cache_read_per_mtok=0.10, cache_write_per_mtok=1.25),
}


# ---------- Transient-error classification ----------
def is_transient(exc: BaseException) -> bool:
    """True for errors worth retrying (network, timeout, 429, 5xx)."""
    if isinstance(exc, (httpx.TimeoutException, httpx.ConnectError)):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        status = exc.response.status_code
        return status == 429 or 500 <= status < 600
    return False


# ---------- LLMClient Protocol — your code depends on this, not a vendor ----------
class LLMClient(Protocol):
    async def create(self, *, model: str, messages: list[dict[str, Any]], **kwargs: Any) -> dict[str, Any]: ...


# ---------- Concrete wrapper ----------
class AsyncLLMClient:
    """Async LLM client with retry, timeout, and cost tracking.

    Wraps an httpx.AsyncClient against any OpenAI-compatible /chat/completions
    endpoint. To use a vendor-specific SDK, swap `_post` with the SDK call —
    the rest of the wrapper (retry, cost, logging) is reusable.
    """

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str | None = None,
        timeout: float = 30.0,
        max_retries: int = 3,
        on_call: Any = None,  # Callable[[str, dict, float], None]
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key or os.environ["LLM_API_KEY"]
        self._timeout = timeout
        self._max_retries = max_retries
        self._on_call = on_call or self._default_on_call
        self._http = httpx.AsyncClient(timeout=timeout)

    async def aclose(self) -> None:
        await self._http.aclose()

    async def create(self, **kwargs: Any) -> dict[str, Any]:
        response: dict[str, Any] = {}
        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(self._max_retries),
            wait=wait_random_exponential(multiplier=1, min=2, max=30),
            retry=retry_if_exception(is_transient),
            reraise=True,
        ):
            with attempt:
                response = await self._post("/chat/completions", kwargs)
        cost = calc_cost(kwargs["model"], response.get("usage", {}))
        self._on_call(model=kwargs["model"], usage=response.get("usage", {}), cost_usd=cost)
        return response

    async def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        r = await self._http.post(
            f"{self._base_url}{path}",
            headers={"Authorization": f"Bearer {self._api_key}"},
            json=payload,
        )
        r.raise_for_status()
        return r.json()

    @staticmethod
    def _default_on_call(model: str, usage: dict[str, Any], cost_usd: float) -> None:
        logger.info(
            "llm_call",
            extra={
                "model": model,
                "input_tokens": usage.get("prompt_tokens", 0),
                "output_tokens": usage.get("completion_tokens", 0),
                "cost_usd": round(cost_usd, 6),
            },
        )


def calc_cost(model: str, usage: dict[str, Any]) -> float:
    p = PRICING.get(model)
    if p is None:
        return 0.0
    return (
        usage.get("prompt_tokens", 0) * p.input_per_mtok / 1_000_000
        + usage.get("completion_tokens", 0) * p.output_per_mtok / 1_000_000
        + usage.get("cache_read_tokens", 0) * p.cache_read_per_mtok / 1_000_000
        + usage.get("cache_write_tokens", 0) * p.cache_write_per_mtok / 1_000_000
    )
```

## Constructor parameters

| Parameter | Default | When to override |
|---|---|---|
| `base_url` | (required) | Provider's API endpoint, e.g. `https://api.<provider>.com/v1` |
| `api_key` | `$LLM_API_KEY` | Multi-tenant apps with per-request keys |
| `timeout` | `30.0` | Long-context calls; raise to `60.0` if seeing timeouts |
| `max_retries` | `3` | Latency-sensitive paths: `2`. Cost-sensitive: `5` |
| `on_call` | logger | Push to App Insights, Prometheus, or your billing system |

## Usage

```python
async def main() -> None:
    client = AsyncLLMClient(
        base_url="https://api.<provider>.com/v1",
        max_retries=4,
    )
    try:
        response = await client.create(
            model="<provider>-balanced",
            messages=[{"role": "user", "content": "Hello"}],
            max_tokens=1024,
        )
        print(response["choices"][0]["message"]["content"])
    finally:
        await client.aclose()
```

## Testability — depend on the Protocol

```python
import pytest
from unittest.mock import AsyncMock

@pytest.fixture
def fake_llm() -> LLMClient:
    """A drop-in LLMClient for unit tests."""
    fake = AsyncMock(spec=LLMClient)
    fake.create.return_value = {
        "choices": [{"message": {"role": "assistant", "content": "ok"}}],
        "usage": {"prompt_tokens": 10, "completion_tokens": 4},
    }
    return fake


@pytest.mark.asyncio
async def test_business_logic(fake_llm: LLMClient) -> None:
    result = await my_feature(client=fake_llm)
    assert result.text == "ok"
    fake_llm.create.assert_awaited_once()
```

Your business code accepts `LLMClient` (the Protocol). In tests inject a
fake; in production inject `AsyncLLMClient`. This is how production AI
code stays testable without touching the network.

## Anti-patterns to flag

- Importing a specific vendor SDK directly in business logic (couples to vendor)
- Using the wrapper without injecting `on_call` for cost tracking in production
- `max_retries` > 5 (likely masking a real failure)
- Catching `Exception` in retries (only retry transient errors)
- Hardcoding `api_key` in source

## See also

- `concepts/async-await-fundamentals.md` — why async, when to use it
- `concepts/retry-patterns-llm.md` — when retry helps, when it wastes tokens
- `concepts/cost-tracking-tokens.md` — cost calc deeper dive
