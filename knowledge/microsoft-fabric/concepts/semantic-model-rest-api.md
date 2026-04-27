# Semantic model REST API

> **Last validated**: 2026-04-26
> **Confidence**: 0.89
> **Sources**: https://learn.microsoft.com/en-us/rest/api/power-bi/, https://learn.microsoft.com/en-us/rest/api/fabric/

## What's available

Two overlapping APIs:

| API | Base URL | Best for |
|---|---|---|
| Power BI REST | `https://api.powerbi.com/v1.0/myorg` | Datasets, dataflows, refresh, RLS, deployment pipelines |
| Fabric REST | `https://api.fabric.microsoft.com/v1` | Workspaces, items (Lakehouse, Warehouse, Notebook), shortcuts, jobs |

For semantic models: most ops still go through the Power BI REST API. Fabric REST is for workspace + item lifecycle.

## Authentication

`DefaultAzureCredential` from `azure-identity`. Never API keys.

```python
from azure.identity import DefaultAzureCredential

cred = DefaultAzureCredential()
token = cred.get_token("https://analysis.windows.net/powerbi/api/.default").token
# scope for Fabric REST: "https://api.fabric.microsoft.com/.default"
```

For service principal (in a CI / pipeline):
- App registration in Microsoft Entra
- Workspace → Settings → Access → add the SP as Member or Admin
- Power BI tenant settings: "Allow service principals to use Power BI APIs" must be enabled
- Cred picks up via `AZURE_CLIENT_ID` / `AZURE_CLIENT_SECRET` / `AZURE_TENANT_ID` env vars OR managed identity

## Common operations

### List datasets in a workspace

```python
import httpx

async def list_datasets(workspace_id: str, token: str) -> list[dict]:
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"https://api.powerbi.com/v1.0/myorg/groups/{workspace_id}/datasets",
            headers={"Authorization": f"Bearer {token}"},
        )
        response.raise_for_status()
        return response.json()["value"]
```

### Trigger a refresh

```python
async def trigger_refresh(workspace_id: str, dataset_id: str, token: str) -> str:
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"https://api.powerbi.com/v1.0/myorg/groups/{workspace_id}/datasets/{dataset_id}/refreshes",
            headers={"Authorization": f"Bearer {token}"},
            json={"notifyOption": "MailOnFailure"},
        )
        response.raise_for_status()
        return response.headers.get("requestid", "")          # tracking ID
```

POST returns 202 Accepted. Refresh is asynchronous.

### Poll refresh status

```python
async def get_refresh_history(workspace_id, dataset_id, token, top: int = 1) -> list[dict]:
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"https://api.powerbi.com/v1.0/myorg/groups/{workspace_id}/datasets/{dataset_id}/refreshes",
            headers={"Authorization": f"Bearer {token}"},
            params={"$top": top},
        )
        response.raise_for_status()
        return response.json()["value"]
        # each: { "status": "Completed" | "Failed" | "Unknown" | "InProgress" | "Disabled", ... }
```

Poll every 30-60s until status changes from "Unknown" / "InProgress".

### Update parameters

```python
async def update_parameters(workspace_id, dataset_id, token, params: dict[str, str]):
    body = {
        "updateDetails": [
            {"name": k, "newValue": v} for k, v in params.items()
        ]
    }
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"https://api.powerbi.com/v1.0/myorg/groups/{workspace_id}/datasets/{dataset_id}/Default.UpdateParameters",
            headers={"Authorization": f"Bearer {token}"},
            json=body,
        )
        response.raise_for_status()
```

### Take over a dataset (run as service principal)

When a dataset was published by user X but you want to refresh it as a service principal:

```python
await client.post(
    f"https://api.powerbi.com/v1.0/myorg/groups/{workspace_id}/datasets/{dataset_id}/Default.TakeOver",
    headers={"Authorization": f"Bearer {token}"},
)
```

After takeover, the SP is the owner and can refresh.

## Rate limits and 429s

Power BI REST: 200 requests per user per minute (varies). Fabric REST: similar.

On 429, the response includes `Retry-After` (seconds). Honor it:

```python
import httpx
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

def is_throttled(exc):
    return isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code == 429

@retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential(min=2, max=60),
    retry=retry_if_exception(is_throttled),
)
async def call_with_throttle_retry(url, headers, **kwargs):
    response = await httpx.AsyncClient().get(url, headers=headers, **kwargs)
    response.raise_for_status()
    return response
```

Better: check `Retry-After` header explicitly:

```python
async def smart_get(url, headers):
    async with httpx.AsyncClient() as client:
        for attempt in range(5):
            response = await client.get(url, headers=headers)
            if response.status_code == 429:
                wait_seconds = int(response.headers.get("Retry-After", "10"))
                await asyncio.sleep(wait_seconds)
                continue
            response.raise_for_status()
            return response
        raise RuntimeError("Throttled too many times")
```

## Pagination

Most LIST operations return paginated results with `@odata.nextLink`:

```python
async def list_all_datasets(workspace_id, token):
    url = f"https://api.powerbi.com/v1.0/myorg/groups/{workspace_id}/datasets"
    items = []
    while url:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers={"Authorization": f"Bearer {token}"})
            response.raise_for_status()
            data = response.json()
            items.extend(data.get("value", []))
            url = data.get("@odata.nextLink")
    return items
```

## RLS via API

Setting up RLS roles is via XMLA / Tabular Editor. Adding USERS to roles is via REST:

```python
async def add_user_to_role(workspace_id, dataset_id, role: str, user: dict, token):
    body = {
        "roles": [
            {"name": role, "members": [user]},
        ]
    }
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"https://api.powerbi.com/v1.0/myorg/groups/{workspace_id}/datasets/{dataset_id}/Default.UpdateUser",
            headers={"Authorization": f"Bearer {token}"},
            json={"identifier": user["identifier"], "principalType": "User", "datasetUserAccessRight": "ReadReshare", **body},
        )
        response.raise_for_status()
```

## Items API (Fabric)

For non-Power-BI items (Lakehouse, Warehouse, Notebook):

```python
async def create_lakehouse(workspace_id, name, token):
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"https://api.fabric.microsoft.com/v1/workspaces/{workspace_id}/lakehouses",
            headers={"Authorization": f"Bearer {token}"},
            json={"displayName": name},
        )
        response.raise_for_status()
        return response.json()
```

Fabric REST endpoints follow `/v1/workspaces/{id}/<itemtype>` pattern. Itemtypes: `lakehouses`, `warehouses`, `notebooks`, `dataPipelines`, `dataflows`, `kqlDatabases`, etc.

## Long-running operations

Some endpoints return 202 + a `Location` header pointing to an operation-status URL:

```python
async def wait_for_operation(operation_url, token, timeout: float = 600):
    deadline = time.time() + timeout
    async with httpx.AsyncClient() as client:
        while time.time() < deadline:
            response = await client.get(operation_url, headers={"Authorization": f"Bearer {token}"})
            response.raise_for_status()
            data = response.json()
            status = data.get("status")
            if status in ("Succeeded", "Failed"):
                return data
            await asyncio.sleep(5)
        raise TimeoutError(f"Operation didn't complete in {timeout}s")
```

## Common bugs

- API key auth → forbidden (Power BI requires AAD bearer token)
- Service principal not in workspace → 401
- Tenant setting "Service principals can use Power BI APIs" disabled → 403
- Refresh triggered but never polled → user thinks it failed
- Pagination ignored → only first 100 items returned
- 429 not handled → request fails after one attempt
- Fabric REST URL used for Power BI ops or vice versa
- Connection / token expires mid-operation — refresh inside long-running flows

## See also

- `patterns/fabric-rest-client-managed-identity.md` — full client implementation
- `patterns/semantic-model-refresh-via-api.md` — refresh + poll pattern
- `concepts/fabric-permissions-model.md` — what permissions an SP needs
- `anti-patterns.md` (items 1, 2, 12)
