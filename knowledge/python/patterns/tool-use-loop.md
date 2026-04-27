# Tool-use loop with bounded iterations

> **Last validated**: 2026-04-26
> **Confidence**: 0.92
> **Source**: https://platform.claude.com/docs/en/docs/build-with-claude/tool-use

## When to use this pattern

Any agent that lets the LLM call tools (functions, APIs) and iterate based on results. Bounded loop prevents runaway costs and hangs.

## Implementation

```python
"""Bounded tool-use loop with per-tool error handling."""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Awaitable, Callable

import anthropic

logger = logging.getLogger(__name__)

# Tool dispatch table: name → async handler
ToolHandler = Callable[[dict[str, Any]], Awaitable[str]]


async def run_agent(
    client: anthropic.AsyncAnthropic,
    *,
    model: str,
    system: str,
    user_message: str,
    tools: list[dict[str, Any]],
    handlers: dict[str, ToolHandler],
    max_iterations: int = 10,
    max_tokens: int = 4096,
) -> tuple[str, list[dict[str, Any]]]:
    """Run an agentic loop until end_turn or max_iterations.

    Returns (final_text, message_history).
    """
    messages: list[dict[str, Any]] = [
        {"role": "user", "content": user_message},
    ]

    for iteration in range(max_iterations):
        response = await client.messages.create(
            model=model,
            max_tokens=max_tokens,
            system=system,
            tools=tools,
            messages=messages,
        )

        # Append assistant turn to history
        messages.append({"role": "assistant", "content": response.content})

        if response.stop_reason == "end_turn":
            text = _extract_text(response.content)
            logger.info(
                "agent_complete",
                extra={"iteration": iteration, "stop_reason": "end_turn"},
            )
            return text, messages

        if response.stop_reason != "tool_use":
            logger.warning(
                "agent_unexpected_stop",
                extra={"iteration": iteration, "stop_reason": response.stop_reason},
            )
            text = _extract_text(response.content)
            return text, messages

        # Run all tool calls (parallel where independent)
        tool_results = await _run_tools(response.content, handlers)
        messages.append({"role": "user", "content": tool_results})

    # Hit max_iterations — soft failure
    logger.warning(
        "agent_max_iterations",
        extra={"max_iterations": max_iterations},
    )
    text = _extract_text(messages[-1]["content"]) if messages else ""
    return text, messages


def _extract_text(content: list[Any]) -> str:
    """Pull plain-text blocks from a content list."""
    parts = []
    for block in content:
        if hasattr(block, "type") and block.type == "text":
            parts.append(block.text)
        elif isinstance(block, dict) and block.get("type") == "text":
            parts.append(block["text"])
    return "\n".join(parts)


async def _run_tools(
    content: list[Any],
    handlers: dict[str, ToolHandler],
) -> list[dict[str, Any]]:
    """Dispatch tool_use blocks to handlers in parallel. Errors per tool."""

    async def _run_one(tool_use: Any) -> dict[str, Any]:
        name = tool_use.name
        handler = handlers.get(name)
        if handler is None:
            return {
                "type": "tool_result",
                "tool_use_id": tool_use.id,
                "content": f"ERROR: tool '{name}' not registered",
                "is_error": True,
            }

        try:
            result = await handler(tool_use.input)
            return {
                "type": "tool_result",
                "tool_use_id": tool_use.id,
                "content": result,
            }
        except Exception as exc:
            logger.exception("tool_failed", extra={"tool": name})
            return {
                "type": "tool_result",
                "tool_use_id": tool_use.id,
                "content": f"ERROR: {type(exc).__name__}: {exc}",
                "is_error": True,
            }

    tool_uses = [b for b in content if hasattr(b, "type") and b.type == "tool_use"]
    return await asyncio.gather(*(_run_one(t) for t in tool_uses))
```

## Tool definition

```python
TOOLS = [
    {
        "name": "get_weather",
        "description": "Get current weather for a city.",
        "input_schema": {
            "type": "object",
            "properties": {
                "city": {"type": "string"},
            },
            "required": ["city"],
        },
    },
]

async def get_weather(args: dict[str, Any]) -> str:
    city = args["city"]
    # call weather API
    return json.dumps({"city": city, "temp_c": 22})

HANDLERS = {"get_weather": get_weather}
```

## Example usage

```python
client = anthropic.AsyncAnthropic()
final_text, history = await run_agent(
    client,
    model="claude-sonnet-4-5",
    system="You help users with weather questions.",
    user_message="What's the weather in Tokyo and Paris?",
    tools=TOOLS,
    handlers=HANDLERS,
    max_iterations=5,
)
print(final_text)
```

## Configuration

| Argument | Default | When to override |
|---|---|---|
| `max_iterations` | `10` | Lower to 5 for simple agents; raise to 20 for research/exploratory |
| `max_tokens` | `4096` | Match your output budget |

## Done when

- Loop terminates on `end_turn` OR `max_iterations` (never unbounded)
- Every `tool_use` produces a matching `tool_result` (Anthropic API requirement)
- Tools are dispatched by name with typed args
- Tool errors are caught per-tool, returned to the model as `is_error: true`
- `stop_reason` other than `end_turn` / `tool_use` is logged but not crashed on

## Anti-patterns

- `while True:` loop without iteration cap
- Bare `except:` around tool calls (swallows tracebacks)
- Tool errors crash the whole loop instead of being reported back to the model
- Sequential tool dispatch when independent tools could run in parallel (use `asyncio.gather`)
- Mutating `messages` from inside a tool handler (handlers should be pure)

## See also

- `patterns/anthropic-client-async-wrapper.md` — pair with the wrapper for retries
- `concepts/async-await-fundamentals.md` — `asyncio.gather` semantics
- `anti-patterns.md` (items 12, 13)
