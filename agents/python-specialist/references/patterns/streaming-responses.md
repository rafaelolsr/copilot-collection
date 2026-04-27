# Streaming responses with backpressure & cancellation

> **Last validated**: 2026-04-27
> **Confidence**: 0.90
> **Source**: https://platform.claude.com/docs/en/docs/build-with-claude/streaming

## When to use this pattern

You're building a UI that shows tokens as they arrive (Chainlit, FastAPI SSE, web sockets), or processing a long response and want to start work before it finishes. Otherwise: don't stream — non-streaming is simpler and the SDK handles backoff better.

## Implementation

```python
"""Stream tokens from Claude with cancellation and backpressure."""
from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import anthropic

logger = logging.getLogger(__name__)


async def stream_response(
    client: anthropic.AsyncAnthropic,
    *,
    model: str,
    system: str,
    user_message: str,
    max_tokens: int = 4096,
    timeout: float = 120.0,
) -> AsyncIterator[str]:
    """Yield text deltas as they arrive. Cancellation- and timeout-safe."""

    async with asyncio.timeout(timeout):
        async with client.messages.stream(
            model=model,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": user_message}],
        ) as stream:
            try:
                async for text in stream.text_stream:
                    yield text
            except asyncio.CancelledError:
                logger.info("stream_cancelled")
                # The async-context-manager will close the underlying connection.
                raise

    # After the context manager exits, the final message is available
    # via stream.get_final_message() if you need usage stats.
```

## Consumer with backpressure

If your consumer is slower than the LLM (UI rendering, downstream API), use a bounded queue:

```python
async def stream_to_queue(
    upstream: AsyncIterator[str],
    queue: asyncio.Queue[str | None],
) -> None:
    """Producer: push tokens into a bounded queue. Drops if consumer can't keep up."""
    try:
        async for token in upstream:
            try:
                queue.put_nowait(token)
            except asyncio.QueueFull:
                # Backpressure: wait for consumer.
                # If you'd rather drop tokens, replace this with a log line.
                await queue.put(token)
    finally:
        await queue.put(None)  # sentinel = stream done


async def consume(queue: asyncio.Queue[str | None]) -> str:
    parts: list[str] = []
    while True:
        token = await queue.get()
        if token is None:
            break
        parts.append(token)
        await render_to_ui(token)  # slow consumer
    return "".join(parts)


async def main() -> None:
    client = anthropic.AsyncAnthropic()
    queue: asyncio.Queue[str | None] = asyncio.Queue(maxsize=64)

    producer = asyncio.create_task(
        stream_to_queue(
            stream_response(
                client,
                model="claude-sonnet-4-6",
                system="You are concise.",
                user_message="Tell me a story",
            ),
            queue,
        )
    )

    full_text = await consume(queue)
    await producer  # ensure cleanup

    print(full_text)
```

## Cancellation

Streaming responses must respond to user cancellation (browser tab closed, `Ctrl+C`):

```python
async def with_cancellation(consumer_signal: asyncio.Event) -> None:
    client = anthropic.AsyncAnthropic()

    async def watch_for_cancel() -> None:
        await consumer_signal.wait()
        raise asyncio.CancelledError("user cancelled")

    stream_task = asyncio.create_task(
        _stream_and_render(client),
    )
    cancel_task = asyncio.create_task(watch_for_cancel())

    try:
        done, pending = await asyncio.wait(
            {stream_task, cancel_task},
            return_when=asyncio.FIRST_COMPLETED,
        )
        for t in pending:
            t.cancel()
    except asyncio.CancelledError:
        stream_task.cancel()
        await asyncio.gather(stream_task, return_exceptions=True)
        raise
```

## Tool use during streaming

When the model decides to call a tool mid-stream, the stream emits an `input_json` event for the tool call. Don't try to render that as text:

```python
async with client.messages.stream(...) as stream:
    async for event in stream:
        if event.type == "content_block_delta" and event.delta.type == "text_delta":
            yield event.delta.text
        elif event.type == "content_block_start" and event.content_block.type == "tool_use":
            logger.info("tool_call_started", extra={"tool": event.content_block.name})
            # Handle tool use (collect args, dispatch, append tool_result, restart stream)
```

For agentic + streaming, simplest pattern: stream until `stop_reason=tool_use`, run tools, then start a new stream with the tool results in `messages`. Don't try to interleave.

## Configuration

| Argument | Default | When to override |
|---|---|---|
| `timeout` | `120.0` | Tight UI SLO → 30; long-form generation → 300 |
| `queue maxsize` | `64` | Slow UI → 32; high-throughput batch → 256 |

## Done when

- Stream terminates cleanly on cancellation (no leaked connection)
- Timeout wraps the entire stream context
- Queue (if used) has a bounded size
- Consumer logs the final usage / cost from `stream.get_final_message()`
- Errors during streaming surface to the UI (not swallowed)

## Anti-patterns

- No timeout — stream can hang indefinitely
- Unbounded queue (memory growth on slow consumer)
- Catching `asyncio.CancelledError` and not re-raising
- Mutating shared state from the producer task without a lock
- `print()`-ing tokens in production (use a proper renderer or structured logger)
- Using streaming for batch jobs where you don't need incremental output (waste of complexity)

## See also

- `concepts/async-await-fundamentals.md` — task / cancellation semantics
- `patterns/anthropic-client-async-wrapper.md` — non-streaming alternative
- `anti-patterns.md` (items 7, 25, 26)
