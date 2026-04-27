# Wiki and pages API

> **Last validated**: 2026-04-26
> **Confidence**: 0.89
> **Source**: https://learn.microsoft.com/en-us/rest/api/azure/devops/wiki/

## Two wiki types

| Type | Storage | API support | Best for |
|---|---|---|---|
| **Project wiki** | Auto-created Git repo | Full | Project-level docs |
| **Code wiki** | Existing repo / branch | Full | Docs alongside source |

For programmatic sync (e.g., compliance docs from a YAML manifest): either works. Code wikis give you Git history + diffs.

## Wiki tree

A wiki is a folder of `.md` files where the folder structure = page hierarchy:

```
docs/                                    # wiki root
├── Home.md                              # landing page
├── Architecture/
│   ├── Architecture.md                  # parent page (folder name + .md)
│   ├── Data-Flow.md
│   └── Security.md
└── Operations/
    ├── Operations.md
    └── Runbooks/
        ├── Runbooks.md
        └── Production-Outage.md
```

A page with sub-pages = a folder. The page's content is `<folder>/<folder>.md`.

URL structure (for reading from the API):
```
/wiki/wikis/{wikiIdentifier}/pages?path=/Architecture/Data-Flow&recursionLevel=None
```

Slashes in path = folders. URL-encode special chars in page names.

## Read a page

```python
import httpx

async def get_page(client, org, project, wiki_id, page_path: str):
    response = await client.get(
        f"https://dev.azure.com/{org}/{project}/_apis/wiki/wikis/{wiki_id}/pages",
        params={
            "path": page_path,
            "includeContent": "true",
            "recursionLevel": "None",          # or "OneLevel" for children
            "api-version": "7.1",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    response.raise_for_status()
    return response.json()
```

Response includes:
- `content` — markdown text
- `path`
- `gitItemPath`
- `etag` (in `ETag` header) — REQUIRED for updates

## Update a page (with ETag)

Wiki updates require optimistic concurrency via ETag. Without it: race conditions, lost edits.

```python
async def update_page(client, org, project, wiki_id, page_path: str, content: str):
    # 1. Get current ETag
    response = await client.get(
        f"https://dev.azure.com/{org}/{project}/_apis/wiki/wikis/{wiki_id}/pages",
        params={"path": page_path, "api-version": "7.1"},
        headers={"Authorization": f"Bearer {token}"},
    )
    response.raise_for_status()
    etag = response.headers["ETag"]

    # 2. Update with If-Match
    update_response = await client.put(
        f"https://dev.azure.com/{org}/{project}/_apis/wiki/wikis/{wiki_id}/pages",
        params={"path": page_path, "api-version": "7.1"},
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "If-Match": etag,
        },
        json={"content": content},
    )

    if update_response.status_code == 412:        # Precondition Failed
        # ETag mismatch — page changed since we read it
        raise RuntimeError("Wiki page was modified by another process. Re-read and retry.")

    update_response.raise_for_status()
    return update_response.json()
```

The 412 response means the page changed underneath you. Read again, re-apply, retry — or surface to user.

## Create a page

PUT with no `If-Match` (or `If-Match: *` for "any version"):

```python
async def create_page(client, org, project, wiki_id, page_path: str, content: str):
    response = await client.put(
        f"https://dev.azure.com/{org}/{project}/_apis/wiki/wikis/{wiki_id}/pages",
        params={"path": page_path, "api-version": "7.1"},
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        json={"content": content},
    )
    response.raise_for_status()
    return response.json()
```

PUT is upsert — same call creates or updates. ETag matters for updates only.

## Delete a page

```python
async def delete_page(client, org, project, wiki_id, page_path: str):
    response = await client.delete(
        f"https://dev.azure.com/{org}/{project}/_apis/wiki/wikis/{wiki_id}/pages",
        params={"path": page_path, "api-version": "7.1"},
        headers={"Authorization": f"Bearer {token}"},
    )
    response.raise_for_status()
```

Deletes the page AND all sub-pages (the entire folder). Use with care.

## List all pages

```python
async def list_pages(client, org, project, wiki_id, root_path: str = "/"):
    """Return a flat list of all page paths under root_path."""
    response = await client.get(
        f"https://dev.azure.com/{org}/{project}/_apis/wiki/wikis/{wiki_id}/pages",
        params={
            "path": root_path,
            "recursionLevel": "Full",
            "includeContent": "false",
            "api-version": "7.1",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    response.raise_for_status()
    data = response.json()

    pages = []
    def walk(node):
        pages.append(node["path"])
        for sub in node.get("subPages", []):
            walk(sub)
    walk(data)
    return pages
```

`recursionLevel`:
- `None` — only this page
- `OneLevel` — page + immediate children
- `Full` — page + entire subtree

`includeContent: false` is faster for tree-only enumeration.

## Page move / rename

```python
async def rename_page(client, org, project, wiki_id, old_path: str, new_path: str):
    response = await client.patch(
        f"https://dev.azure.com/{org}/{project}/_apis/wiki/wikis/{wiki_id}/pagemoves",
        params={"api-version": "7.1"},
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        json={
            "newOrderId": 0,
            "newPath": new_path,
            "path": old_path,
        },
    )
    response.raise_for_status()
```

## Attachments

Wiki pages can embed images / files. Upload first, then reference in markdown:

```python
async def upload_attachment(client, org, project, wiki_id, name: str, content: bytes):
    response = await client.put(
        f"https://dev.azure.com/{org}/{project}/_apis/wiki/wikis/{wiki_id}/attachments",
        params={"name": name, "api-version": "7.1"},
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/octet-stream",
        },
        content=content,
    )
    response.raise_for_status()
    # Reference in markdown: ![](/.attachments/<name>)
```

## Markdown rendering

Azure DevOps wiki uses CommonMark + extensions:
- Tables, footnotes, fenced code blocks
- Mermaid diagrams (` ```mermaid `)
- Math (`$..$` and `$$..$$`)
- TOC: `[[_TOC_]]`
- Custom: `:::warning`, `:::note`, `:::danger` (admonition blocks)

Test rendering by previewing a page in the portal — not all extensions are universally supported.

## Page metadata in the file

The first line of a page can include front-matter-style markers:

```markdown
[//]: # (Status: Approved)
[//]: # (Owner: rafael@example.com)

# Page Title
```

Markdown comments. Stored but not rendered. Useful for sync metadata (status, owner, last-validated date).

## Common bugs

- PUT without ETag on existing page → race condition; can overwrite concurrent edit
- ETag mismatch (412) ignored → silent edit loss
- Path with `/` in page name (page itself, not subfolder) → escape as `%2F`
- `recursionLevel` not set when listing → only direct children returned
- Wrong `wikiIdentifier` (use the wiki GUID; the slug works in URLs but API often wants the GUID)
- Markdown syntax that works in GitHub fails in ADO wiki (e.g., GitHub-Flavored task lists)
- Image references with absolute URLs vs `/.attachments/...` relative

## See also

- `concepts/azure-devops-rest-api.md`
- `patterns/wiki-incremental-sync.md`
- `anti-patterns.md` (items 16, 17)
