# async/await fundamentals

> **Last validated**: 2026-04-26
> **Confidence**: 0.95
> **Source**: https://docs.python.org/3/library/asyncio.html

## When this applies

LLM applications are I/O-bound (waiting on network), so async is the default for production code. Sync clients work for scripts and notebooks but block the event loop in any web app, FastAPI service, or concurrent batch job.

## Core mental model

```python
import asyncio

async def fetch(url: str) -> str:
    # await yields control back to the event loop
    # so other coroutines can run while we wait for I/O
    await asyncio.sleep(0.1)
    return f"data from {url}"

async def main() -> None:
    # Run two fetches concurrently
    results = await asyncio.gather(
        fetch("https://a.example"),
        fetch("https://b.example"),
    )
    print(results)

asyncio.run(main())
```

`async def` defines a coroutine. `await` is the only way to consume one. `asyncio.gather()` runs coroutines concurrently. `asyncio.run()` is the entry point — call it exactly once at the top of your program.

## The blocking-in-async trap

The most expensive bug in async LLM code: calling a synchronous SDK or `time.sleep()` inside an `async def`. The coroutine blocks the event loop, freezing every other coroutine in the process.

```python
# WRONG — blocks the event loop
async def bad():
    response = anthropic.Anthropic().messages.create(...)  # sync client, sync call
    time.sleep(1)  # blocks every other coroutine
```

```python
# CORRECT — async client, async sleep
async def good():
    client = anthropic.AsyncAnthropic()
    response = await client.messages.create(...)
    await asyncio.sleep(1)
```

If you must call a sync function from async code, use `asyncio.to_thread()`:

```python
async def call_legacy_sync_lib():
    return await asyncio.to_thread(legacy_blocking_function, arg1, arg2)
```

## Cancellation

`asyncio.CancelledError` is raised when a task is cancelled (timeout, parent task fails). **Always re-raise it** — swallowing cancellation breaks structured concurrency.

```python
async def with_timeout():
    try:
        async with asyncio.timeout(10):
            return await long_operation()
    except asyncio.CancelledError:
        # cleanup if needed, then re-raise
        await cleanup()
        raise
```

## Timeouts

Two patterns. Prefer `asyncio.timeout()` (Python 3.11+) over `asyncio.wait_for()`:

```python
async with asyncio.timeout(30):
    result = await llm_call()
```

For SDKs that accept a timeout argument, prefer that — the SDK can clean up its own connection state:

```python
client = anthropic.AsyncAnthropic(timeout=30.0)
```

## Concurrent fan-out with bounded concurrency

Don't fire 1000 LLM calls at once — you'll hit rate limits. Use a `Semaphore`:

```python
async def process_batch(items: list[str], concurrency: int = 10) -> list[str]:
    sem = asyncio.Semaphore(concurrency)

    async def process_one(item: str) -> str:
        async with sem:
            return await llm_call(item)

    return await asyncio.gather(*(process_one(i) for i in items))
```

## Anti-patterns to flag

- `time.sleep()` inside `async def` → use `await asyncio.sleep()`
- Sync SDK call (`Anthropic().messages.create`) inside `async def` → use `AsyncAnthropic`
- `except asyncio.CancelledError: pass` → must re-raise
- Mixing sync and async clients for the same provider in one app
- No timeout on any LLM call
- Unbounded `asyncio.gather()` over user input → bound with semaphore

## See also

- `patterns/anthropic-client-async-wrapper.md` — production-grade async wrapper
- `concepts/retry-patterns-llm.md` — retry strategies for transient errors
- `anti-patterns.md` (items 6, 7, 8, 25, 26)
