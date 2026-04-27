# Fabric REST client with managed identity

> **Last validated**: 2026-04-26
> **Confidence**: 0.89

## When to use this pattern

A reusable async HTTP client for Fabric / Power BI REST APIs. Auth via `DefaultAzureCredential`. Built-in retry on 429 / 503. Pagination helper.

## Implementation

```python
"""Fabric / Power BI REST client with managed identity auth and 429-aware retry."""
from __future__ import annotations

import asyncio
import logging
from typing import Any, AsyncIterator

import httpx
from azure.identity import DefaultAzureCredential
from tenacity import (
    AsyncRetrying,
    retry_if_exception,
    stop_after_attempt,
    wait_random_exponential,
    before_sleep_log,
)

logger = logging.getLogger(__name__)

POWER_BI_SCOPE = "https://analysis.windows.net/powerbi/api/.default"
FABRIC_SCOPE = "https://api.fabric.microsoft.com/.default"

POWER_BI_BASE = "https://api.powerbi.com/v1.0/myorg"
FABRIC_BASE = "https://api.fabric.microsoft.com/v1"


def _is_retryable(exc: BaseException) -> bool:
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code in {429, 500, 502, 503, 504}
    return isinstance(exc, (httpx.TimeoutException, httpx.ConnectError))


class FabricClient:
    """Async client for Fabric / Power BI REST APIs."""

    def __init__(
        self,
        *,
        scope: str = POWER_BI_SCOPE,
        base_url: str = POWER_BI_BASE,
        timeout: float = 30.0,
    ) -> None:
        self._cred = DefaultAzureCredential()
        self._scope = scope
        self._base = base_url.rstrip("/")
        self._http = httpx.AsyncClient(timeout=timeout)
        self._token: str | None = None
        self._token_expires_at: float = 0.0

    async def _get_token(self) -> str:
        import time
        if self._token and time.time() < self._token_expires_at - 60:    # 60s buffer
            return self._token
        token_obj = await asyncio.to_thread(
            self._cred.get_token, self._scope
        )
        self._token = token_obj.token
        self._token_expires_at = token_obj.expires_on
        return self._token

    async def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {await self._get_token()}",
            "Content-Type": "application/json",
        }

    async def _request_with_throttle(
        self, method: str, path: str, **kwargs: Any
    ) -> httpx.Response:
        url = f"{self._base}{path}" if path.startswith("/") else path

        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(5),
            wait=wait_random_exponential(min=2, max=60),
            retry=retry_if_exception(_is_retryable),
            before_sleep=before_sleep_log(logger, logging.WARNING),
            reraise=True,
        ):
            with attempt:
                response = await self._http.request(
                    method, url, headers=await self._headers(), **kwargs
                )
                if response.status_code == 429:
                    wait_seconds = int(response.headers.get("Retry-After", "10"))
                    logger.warning(
                        "fabric_throttled",
                        extra={"wait_s": wait_seconds, "path": path},
                    )
                    await asyncio.sleep(wait_seconds)
                    response.raise_for_status()                          # triggers tenacity retry
                response.raise_for_status()
                return response

        raise RuntimeError("unreachable")

    async def get(self, path: str, **kwargs: Any) -> Any:
        response = await self._request_with_throttle("GET", path, **kwargs)
        return response.json() if response.content else None

    async def post(self, path: str, *, json: Any = None, **kwargs: Any) -> Any:
        response = await self._request_with_throttle("POST", path, json=json, **kwargs)
        return response.json() if response.content else None

    async def put(self, path: str, *, json: Any = None, **kwargs: Any) -> Any:
        response = await self._request_with_throttle("PUT", path, json=json, **kwargs)
        return response.json() if response.content else None

    async def delete(self, path: str, **kwargs: Any) -> None:
        await self._request_with_throttle("DELETE", path, **kwargs)

    async def paginate(self, path: str, **kwargs: Any) -> AsyncIterator[dict[str, Any]]:
        """Yield items across all pages."""
        url = path
        while url:
            data = await self.get(url, **kwargs)
            for item in data.get("value", []):
                yield item
            url = data.get("@odata.nextLink", "")

    async def close(self) -> None:
        await self._http.aclose()

    async def __aenter__(self) -> "FabricClient":
        return self

    async def __aexit__(self, *exc) -> None:
        await self.close()
```

## Usage

```python
import asyncio

async def main():
    async with FabricClient() as client:
        # List datasets in a workspace
        async for dataset in client.paginate(f"/groups/{workspace_id}/datasets"):
            print(dataset["name"])

        # Trigger refresh
        await client.post(
            f"/groups/{workspace_id}/datasets/{dataset_id}/refreshes",
            json={"notifyOption": "MailOnFailure"},
        )

        # Update parameters
        await client.post(
            f"/groups/{workspace_id}/datasets/{dataset_id}/Default.UpdateParameters",
            json={
                "updateDetails": [
                    {"name": "Source", "newValue": "https://newserver.example.com"},
                ]
            },
        )

asyncio.run(main())
```

## Switching to Fabric REST

For Fabric items (Lakehouse, Warehouse, etc.) instead of Power BI APIs:

```python
async with FabricClient(
    scope=FABRIC_SCOPE,
    base_url=FABRIC_BASE,
) as client:
    # Create a Lakehouse
    await client.post(
        f"/workspaces/{workspace_id}/lakehouses",
        json={"displayName": "MyLakehouse"},
    )

    # List items
    async for item in client.paginate(f"/workspaces/{workspace_id}/items"):
        print(f"{item['type']}: {item['displayName']}")
```

## Long-running operations

Some endpoints return 202 + a `Location` header pointing to status:

```python
async def wait_for_lro(self, location_url: str, timeout: float = 600) -> dict:
    deadline = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < deadline:
        response = await self._request_with_throttle("GET", location_url)
        data = response.json()
        status = data.get("status")
        if status in ("Succeeded", "Failed"):
            return data
        await asyncio.sleep(5)
    raise TimeoutError(f"LRO didn't complete in {timeout}s")
```

For deployments, refresh status, etc.

## Rate-limit awareness

The client retries on 429 + honors `Retry-After`. For very high-throughput callers (>10 reqs/sec): use a Semaphore to bound concurrency:

```python
semaphore = asyncio.Semaphore(5)

async def bounded_call(client, path):
    async with semaphore:
        return await client.get(path)

results = await asyncio.gather(*(bounded_call(client, p) for p in many_paths))
```

## Done when

- `DefaultAzureCredential` for auth (no API keys)
- Token caching with refresh-before-expiry
- Retry on 429 / 5xx with exponential backoff + Retry-After
- Pagination helper for `value[]`-style responses
- Timeouts set on the HTTP client
- LRO helper for 202-pattern endpoints

## Anti-patterns

- API key auth instead of AAD
- New `DefaultAzureCredential` per request (token caching wasted)
- No retry on 429 (request fails on first throttle)
- Tight loop over many paths without semaphore (throttles immediately)
- Token never refreshed in long-running scripts (auth expires mid-flow)
- LRO not awaited (caller thinks the operation is done when it's still running)

## See also

- `concepts/semantic-model-rest-api.md` — what endpoints exist
- `concepts/fabric-permissions-model.md` — what role / scopes the SP needs
- `patterns/semantic-model-refresh-via-api.md` — using this client for refresh
- `anti-patterns.md` (items 1, 2, 12)
