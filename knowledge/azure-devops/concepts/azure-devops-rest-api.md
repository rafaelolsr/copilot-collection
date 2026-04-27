# Azure DevOps REST API

> **Last validated**: 2026-04-26
> **Confidence**: 0.91
> **Source**: https://learn.microsoft.com/en-us/rest/api/azure/devops/

## Base URL

```
https://dev.azure.com/{organization}/{project}/_apis/{area}/{resource}?api-version={version}
```

Newer endpoints (Wiki, some) use:
```
https://dev.azure.com/{organization}/{project}/_apis/wiki/wikis/...
```

`api-version` is mandatory on every request. Common: `7.1` (current).

## Authentication

| Auth | Header |
|---|---|
| PAT (interactive / scripts) | `Authorization: Basic <base64(user:pat)>` (use `:pat` — empty user + colon + PAT) |
| OAuth bearer (Entra) | `Authorization: Bearer <token>` |
| `System.AccessToken` (in pipelines) | `Authorization: Bearer $(System.AccessToken)` |

For PAT in Python:

```python
import base64
import httpx

pat = "<your-pat>"
auth = base64.b64encode(f":{pat}".encode()).decode()
headers = {"Authorization": f"Basic {auth}"}

async with httpx.AsyncClient() as client:
    response = await client.get(
        f"https://dev.azure.com/{org}/{project}/_apis/git/repositories?api-version=7.1",
        headers=headers,
    )
```

For Entra (preferred):

```python
from azure.identity import DefaultAzureCredential

cred = DefaultAzureCredential()
token = cred.get_token("499b84ac-1321-427f-aa17-267ca6975798/.default").token  # ADO scope
headers = {"Authorization": f"Bearer {token}"}
```

The magic GUID `499b84ac-1321-427f-aa17-267ca6975798` is the Azure DevOps API resource ID.

## Common areas + resources

| Area | Resource | Use |
|---|---|---|
| `git` | `repositories` | List / get repos |
| `git` | `pullrequests` | Create / get / update PRs |
| `git` | `pushes` | Push commits via API |
| `git` | `refs` | Create / delete branches and tags |
| `wiki/wikis` | `pages` | Wiki page CRUD |
| `pipelines` | `pipelines` | Pipeline metadata |
| `pipelines` | `runs` | Pipeline run history, queue runs |
| `build` | `builds` | Older builds API (still works) |
| `policy` | `configurations` | Branch policies |
| `wit` | `workitems` | Boards / work items |
| `release` | `releases` | Release pipelines (legacy) |

## Pagination

Most LIST responses paginate via `continuationToken` header (ADO style — different from OData):

```python
async def list_all(client, base_url, headers):
    items = []
    url = base_url
    while url:
        response = await client.get(url, headers=headers)
        response.raise_for_status()
        data = response.json()
        items.extend(data.get("value", []))
        token = response.headers.get("x-ms-continuationtoken")
        if not token:
            break
        url = f"{base_url}{'&' if '?' in base_url else '?'}continuationToken={token}"
    return items
```

Some endpoints use OData-style with `$top` + `$skip`:

```
?api-version=7.1&$top=100&$skip=200
```

Check the doc per endpoint — mixing the two patterns is a common bug.

## Rate limiting

Azure DevOps throttles aggressively per-user-per-endpoint. Limits aren't published precisely but trigger 429 responses.

On 429:
- Honor `Retry-After` header (seconds)
- Exponential backoff with jitter

```python
from tenacity import (
    AsyncRetrying,
    retry_if_exception,
    stop_after_attempt,
    wait_random_exponential,
)

def is_throttled(exc):
    return isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code in (429, 503)

async for attempt in AsyncRetrying(
    stop=stop_after_attempt(5),
    wait=wait_random_exponential(min=2, max=120),
    retry=retry_if_exception(is_throttled),
    reraise=True,
):
    with attempt:
        response = await client.get(url, headers=headers)
        if response.status_code == 429:
            retry_after = int(response.headers.get("Retry-After", "10"))
            await asyncio.sleep(retry_after)
        response.raise_for_status()
```

## Request IDs

Every request gets a unique ID in the `x-vss-e2eid` (or similar) response header. Log it on errors:

```python
try:
    response.raise_for_status()
except httpx.HTTPStatusError as exc:
    request_id = exc.response.headers.get("x-vss-e2eid", "unknown")
    logger.error(
        "ado_api_failed",
        extra={"status": exc.response.status_code, "request_id": request_id, "url": str(exc.request.url)},
    )
    raise
```

Microsoft support asks for the request ID when troubleshooting — capture and log every failure.

## API versioning

Azure DevOps versions APIs: `7.0`, `7.1`, `7.2-preview.X`. Behavior can differ.

- For stable endpoints: use the latest stable (`7.1` as of 2026)
- For new features: `*-preview.X` is required
- Mixing versions in one client: usually fine, but document why

NEVER omit `api-version` — endpoints reject the request.

## Error response format

```json
{
  "$id": "1",
  "innerException": null,
  "message": "TF400898: An Internal Error Occurred. Activity Id: 12345...",
  "typeName": "Microsoft.TeamFoundation.SourceControl.WebApi.GitForkSyncOperationStatus",
  "typeKey": "GitForkSyncOperationStatus",
  "errorCode": 0,
  "eventId": 0
}
```

Always log `message` AND `typeKey`. The `typeKey` is the most useful for matching error patterns.

## Long-running operations

Some endpoints return 202 Accepted with a `Location` header:

```python
response = await client.post(url, json=body, headers=headers)
if response.status_code == 202:
    operation_url = response.headers["Location"]
    # poll operation_url until status is Succeeded / Failed
```

Polling pattern same as Power BI / Fabric (see `microsoft-fabric-specialist`).

## Tip: use the official SDK first

For Python: `azure-devops` package (legacy but functional). For .NET: `Microsoft.TeamFoundationServer.Client`.

```bash
pip install azure-devops
```

```python
from azure.devops.connection import Connection
from msrest.authentication import BasicAuthentication

credentials = BasicAuthentication("", pat)
connection = Connection(base_url=f"https://dev.azure.com/{org}", creds=credentials)

git_client = connection.clients.get_git_client()
repos = git_client.get_repositories(project=project)
for r in repos:
    print(r.name)
```

The SDK handles auth, pagination, error translation. Use REST directly only when:
- The SDK doesn't cover the endpoint
- You need fine-grained HTTP control (custom headers, streaming)
- You're scripting outside Python / .NET

## Common bugs

- Missing `api-version` query param → 400
- PAT format wrong (need `:pat` not `pat:` — empty user FIRST)
- Continuation token loop never advances (forgot to update `url`)
- 429 not handled → fails on first throttle
- Request ID not logged → can't debug with Microsoft support
- Wrong host: `dev.azure.com` vs `<org>.visualstudio.com` (legacy)
- `https://` missing in URLs (some libs are strict)
- Mixing `_apis/` (older) vs `_api/` (typo, doesn't exist)

## See also

- `concepts/wiki-and-pages-api.md` — specific area
- `patterns/pr-creation-via-rest.md` — git/pullrequests
- `patterns/wiki-incremental-sync.md` — wiki/pages
- `anti-patterns.md` (items 12, 17)
