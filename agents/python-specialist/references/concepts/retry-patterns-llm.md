# Retry patterns for LLM calls

> **Last validated**: 2026-04-26
> **Confidence**: 0.93
> **Sources**: https://tenacity.readthedocs.io/, https://www.python-httpx.org/errors

## What to retry vs. what NOT to retry

| Status | Meaning | Retry? |
|---|---|---|
| 429 | Rate limit | YES — exponential backoff, respect `retry-after` header |
| 529 | LLM provider overload signal | YES — exponential backoff |
| 500/502/503/504 | Server / gateway errors | YES — exponential backoff |
| `httpx.ReadTimeout` / `ConnectTimeout` | Network issue | YES — limited retries |
| 400 | Bad request (schema, invalid params) | NO — wastes tokens, won't fix itself |
| 401 / 403 | Auth | NO — fix credentials |
| 404 | Not found (model deployment, etc.) | NO — fix config |
| 413 | Payload too large | NO — reduce input |
| `ValidationError` from Pydantic | LLM output malformed | YES with repair prompt — but a different mechanism (see structured-output) |

Retrying 4xx errors is the most common waste of tokens and money in production code.

## Tenacity — the standard library

```python
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
)
import logging
from my_app import llm_client  # vendor-neutral wrapper
import httpx

logger = logging.getLogger(__name__)

@retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=1, min=2, max=60),
    retry=retry_if_exception_type((
        httpx.HTTPStatusError,
        httpx.TimeoutException,
        httpx.HTTPStatusError,
        httpx.TimeoutException,
    )),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    reraise=True,
)
async def call_with_retry(client, **kwargs):
    return await client.messages.create(**kwargs)
```

Key flags:
- `stop_after_attempt(5)` — bounded; never `retry_forever()` in production
- `wait_exponential(min=2, max=60)` — respects backoff, capped
- `retry_if_exception_type(...)` — narrow whitelist; never bare `Exception`
- `before_sleep_log(...)` — visibility into retries (log to your structured logger)
- `reraise=True` — propagate the original exception, not `RetryError`

## Filter on status code, not just exception type

Many LLM SDKs raise an error class for any non-2xx — including 400. To retry only transient ones:

```python
def is_retryable(exc: BaseException) -> bool:
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.status_code in {429, 500, 502, 503, 504, 529}
    if isinstance(exc, (httpx.TimeoutException, httpx.ConnectError)):
        return True
    return False

@retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential(min=2, max=60),
    retry=retry_if_exception(is_retryable),
    reraise=True,
)
async def call_with_retry(client, **kwargs):
    return await client.messages.create(**kwargs)
```

## Honour `retry-after` headers

Servers tell you when to retry. Use `wait_random_exponential` as a fallback, but check `retry-after` first if the SDK exposes it:

```python
from tenacity import wait_random_exponential

# wait_random_exponential adds jitter — better for stampedes
wait=wait_random_exponential(min=2, max=60)
```

Some LLM SDKs, the SDK has built-in retry on transient errors. If you set `max_retries` on the client, you may not need tenacity at all:

```python
client = llm_client.AsyncLLMClient(max_retries=3, timeout=30.0)
```

Layer tenacity on top only if you need more control (logging, circuit breakers, custom backoff).

## Circuit breakers

For high-traffic services, retries alone aren't enough. After repeated failures, stop trying for a window. `pybreaker` is the standard:

```python
import pybreaker

breaker = pybreaker.CircuitBreaker(fail_max=5, reset_timeout=60)

@breaker
async def call_protected(client, **kwargs):
    return await call_with_retry(client, **kwargs)
```

After 5 consecutive failures the breaker opens for 60s, raising `CircuitBreakerError` immediately without hitting the API. Saves cost and latency during incidents.

## Anti-patterns to flag

- `retry=retry_if_exception_type(Exception)` — way too broad
- Retrying on 400/401/403/404
- `stop=stop_never` or no `stop=` — risks runaway retries
- Fixed `wait_fixed(5)` instead of exponential — thundering herd on recovery
- `time.sleep()` between retries inside async code (instead of letting tenacity handle it)
- Catching `RetryError` and ignoring the underlying exception
- Re-implementing retry inside business logic when the SDK already supports `max_retries`

## See also

- `patterns/llm-client-async-wrapper.md` — full client with retry baked in
- `concepts/async-await-fundamentals.md` — timeout handling
- `anti-patterns.md` (items 9, 10)
