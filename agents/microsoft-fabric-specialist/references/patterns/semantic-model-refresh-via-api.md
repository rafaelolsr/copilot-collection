# Semantic model refresh via REST API

> **Last validated**: 2026-04-26
> **Confidence**: 0.90

## When to use this pattern

Triggering a Power BI semantic model refresh from a pipeline / service / CI job, then waiting for completion before downstream steps (e.g., before triggering reports).

## Implementation

Uses the `FabricClient` from `patterns/fabric-rest-client-managed-identity.md`.

```python
"""Trigger and wait for a semantic model refresh."""
from __future__ import annotations

import asyncio
import logging
from typing import Literal

logger = logging.getLogger(__name__)

RefreshStatus = Literal["Completed", "Failed", "Disabled", "Unknown", "InProgress"]


async def trigger_and_wait_refresh(
    client,                                                    # FabricClient
    *,
    workspace_id: str,
    dataset_id: str,
    poll_interval: float = 30.0,
    timeout: float = 3600.0,                                   # 1 hour
    notify_option: Literal["NoNotification", "MailOnFailure", "MailOnCompletion"] = "MailOnFailure",
) -> dict:
    """Trigger a refresh and wait until it succeeds or fails.

    Returns the final refresh-history record. Raises on Failed / timeout.
    """
    # Trigger
    logger.info("triggering_refresh", extra={"dataset_id": dataset_id})
    await client.post(
        f"/groups/{workspace_id}/datasets/{dataset_id}/refreshes",
        json={"notifyOption": notify_option},
    )

    # Get the request ID from the latest refresh
    refreshes = await client.get(
        f"/groups/{workspace_id}/datasets/{dataset_id}/refreshes?$top=1"
    )
    if not refreshes.get("value"):
        raise RuntimeError("No refresh record found after trigger")

    refresh_request_id = refreshes["value"][0].get("requestId")
    logger.info(
        "refresh_started",
        extra={"dataset_id": dataset_id, "request_id": refresh_request_id},
    )

    # Poll
    deadline = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < deadline:
        latest = await client.get(
            f"/groups/{workspace_id}/datasets/{dataset_id}/refreshes?$top=1"
        )
        record = latest["value"][0]
        status: RefreshStatus = record.get("status", "Unknown")

        if status == "Completed":
            logger.info(
                "refresh_completed",
                extra={
                    "dataset_id": dataset_id,
                    "request_id": refresh_request_id,
                    "duration_s": _duration(record),
                },
            )
            return record
        if status == "Failed":
            logger.error(
                "refresh_failed",
                extra={
                    "dataset_id": dataset_id,
                    "request_id": refresh_request_id,
                    "error": record.get("serviceExceptionJson", ""),
                },
            )
            raise RuntimeError(
                f"Refresh failed: {record.get('serviceExceptionJson', 'unknown')}"
            )
        if status == "Disabled":
            raise RuntimeError("Refresh is disabled for this dataset")

        # InProgress / Unknown — keep polling
        await asyncio.sleep(poll_interval)

    raise TimeoutError(f"Refresh did not complete in {timeout}s")


def _duration(record: dict) -> float | None:
    from datetime import datetime
    start = record.get("startTime")
    end = record.get("endTime")
    if not (start and end):
        return None
    return (datetime.fromisoformat(end.rstrip("Z")) - datetime.fromisoformat(start.rstrip("Z"))).total_seconds()
```

## Usage

```python
async def daily_pipeline():
    async with FabricClient() as client:
        # 1. Run gold layer build (Spark notebook / pipeline)
        ...

        # 2. Refresh semantic model
        refresh_result = await trigger_and_wait_refresh(
            client,
            workspace_id=settings.workspace_id,
            dataset_id=settings.dataset_id,
            timeout=1800,                                       # 30 min
        )

        # 3. Trigger downstream (e.g., email a report)
        await send_completion_notification(refresh_result)
```

## Take ownership before refresh (service principal)

If the dataset was published by a user but you're a service principal, take ownership first:

```python
async def take_over_dataset(client, workspace_id, dataset_id):
    await client.post(
        f"/groups/{workspace_id}/datasets/{dataset_id}/Default.TakeOver",
        json={},
    )

# Before first refresh
await take_over_dataset(client, workspace_id, dataset_id)
await trigger_and_wait_refresh(client, workspace_id=workspace_id, dataset_id=dataset_id)
```

## Update parameters before refresh

```python
async def update_and_refresh(client, workspace_id, dataset_id, params: dict[str, str]):
    if params:
        await client.post(
            f"/groups/{workspace_id}/datasets/{dataset_id}/Default.UpdateParameters",
            json={
                "updateDetails": [
                    {"name": k, "newValue": v} for k, v in params.items()
                ]
            },
        )
    return await trigger_and_wait_refresh(
        client, workspace_id=workspace_id, dataset_id=dataset_id
    )
```

## Enhanced refresh (selected tables / partitions)

For models with many tables, refresh only what's needed:

```python
async def refresh_specific_tables(client, workspace_id, dataset_id, tables: list[str]):
    body = {
        "type": "full",
        "commitMode": "transactional",
        "objects": [{"table": t} for t in tables],
        "applyRefreshPolicy": False,
        "maxParallelism": 4,
    }
    await client.post(
        f"/groups/{workspace_id}/datasets/{dataset_id}/refreshes",
        json=body,
    )
```

`refreshes` endpoint with a body = enhanced refresh API. Faster than refreshing the whole model.

## Refresh history query

For dashboards / observability:

```python
async def get_refresh_history(client, workspace_id, dataset_id, top: int = 50):
    history = await client.get(
        f"/groups/{workspace_id}/datasets/{dataset_id}/refreshes?$top={top}"
    )
    return [
        {
            "request_id": r.get("requestId"),
            "status": r.get("status"),
            "start": r.get("startTime"),
            "end": r.get("endTime"),
            "type": r.get("refreshType"),
            "error": r.get("serviceExceptionJson"),
        }
        for r in history.get("value", [])
    ]
```

Plot success rate / duration over time — basic SLO tracking.

## Common error patterns

| Error | Likely cause |
|---|---|
| 401 Unauthorized | SP missing dataset permissions, or tenant setting blocks SPs |
| 403 Forbidden | Workspace role too low (need Member or Build on dataset) |
| 404 Not Found | Wrong workspace_id or dataset_id |
| 400 InvalidOperation | Refresh already in progress (wait), or model doesn't support that refresh type |
| 429 Throttled | Honored by FabricClient automatically |
| Refresh fails with "DataSource.Error" | Source connection broken, or credentials expired |
| Refresh fails with "Tabular database error" | DAX / model-level issue; check Power BI portal logs |

## Done when

- Authenticated via `DefaultAzureCredential`
- Take-over called if needed (SP scenario)
- Polling with reasonable interval (30-60s)
- Timeout bounded (don't hang forever)
- Final status logged with duration
- 429s handled by client
- Errors propagate with the source-side error message

## Anti-patterns

- Trigger and don't wait (caller assumes done; downstream runs against stale data)
- Polling every 1s (rate-limit risk)
- No timeout (script hangs on stuck refresh)
- Catching error and continuing (skips broken state silently)
- Refresh on every code change (unnecessary; CU cost)
- Triggering refresh before silver / gold writes complete (refreshes against stale data)

## See also

- `concepts/semantic-model-rest-api.md` — endpoint reference
- `patterns/fabric-rest-client-managed-identity.md` — the underlying client
- `patterns/medallion-bronze-silver-gold.md` — pipeline integration
- `anti-patterns.md` (items 12, 19)
