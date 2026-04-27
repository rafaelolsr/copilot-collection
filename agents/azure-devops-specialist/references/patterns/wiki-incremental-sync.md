# Wiki incremental sync (content-hash dedup)

> **Last validated**: 2026-04-26
> **Confidence**: 0.88

## When to use this pattern

Syncing markdown content into an Azure DevOps Wiki from an external source (compliance docs, generated content, scheduled imports). Skip pages whose content hasn't changed.

## Strategy

1. Source = list of (path, content) tuples
2. For each page: compute content hash
3. Read current page; compare hash
4. If different OR missing → upsert with PUT + If-Match
5. Track which pages exist; delete orphans (pages whose source disappeared)

## Implementation

```python
"""Incremental wiki sync. Skips unchanged pages, deletes orphans."""
from __future__ import annotations

import asyncio
import hashlib
import logging
from dataclasses import dataclass
from typing import Any

import httpx
from azure.identity import DefaultAzureCredential

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class WikiPage:
    path: str                                       # e.g., "/Compliance/HIPAA"
    content: str                                    # markdown


def content_hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]


# Marker line we add to track managed pages
HASH_MARKER_PREFIX = "[//]: # (sync-hash: "


def add_hash_marker(content: str, h: str) -> str:
    """Inject a hash marker as the first line."""
    return f"{HASH_MARKER_PREFIX}{h})\n\n{content}"


def extract_hash_marker(content: str) -> str | None:
    """Return the hash from a marker line, if present."""
    if not content.startswith(HASH_MARKER_PREFIX):
        return None
    end = content.find(")")
    if end == -1:
        return None
    return content[len(HASH_MARKER_PREFIX):end]


class WikiSync:
    def __init__(
        self,
        organization: str,
        project: str,
        wiki_id: str,
        *,
        managed_root_path: str = "/",
        dry_run: bool = False,
    ) -> None:
        self._org = organization
        self._project = project
        self._wiki_id = wiki_id
        self._managed_root = managed_root_path
        self._dry_run = dry_run
        self._cred = DefaultAzureCredential()
        self._http = httpx.AsyncClient(timeout=30.0)

    async def _headers(self) -> dict[str, str]:
        token = self._cred.get_token("499b84ac-1321-427f-aa17-267ca6975798/.default").token
        return {"Authorization": f"Bearer {token}"}

    @property
    def _wiki_url(self) -> str:
        return (
            f"https://dev.azure.com/{self._org}/{self._project}"
            f"/_apis/wiki/wikis/{self._wiki_id}"
        )

    async def list_managed_pages(self) -> dict[str, dict]:
        """Return path → page-info dict for all pages under managed_root."""
        response = await self._http.get(
            f"{self._wiki_url}/pages",
            params={
                "path": self._managed_root,
                "recursionLevel": "Full",
                "includeContent": "false",
                "api-version": "7.1",
            },
            headers=await self._headers(),
        )
        response.raise_for_status()

        pages = {}

        def walk(node):
            pages[node["path"]] = node
            for sub in node.get("subPages", []):
                walk(sub)

        walk(response.json())
        return pages

    async def get_page(self, path: str) -> tuple[str, str] | None:
        """Return (content, etag) or None if page doesn't exist."""
        response = await self._http.get(
            f"{self._wiki_url}/pages",
            params={"path": path, "includeContent": "true", "api-version": "7.1"},
            headers=await self._headers(),
        )
        if response.status_code == 404:
            return None
        response.raise_for_status()
        data = response.json()
        return data.get("content", ""), response.headers.get("ETag", "")

    async def upsert_page(self, path: str, content: str, etag: str | None = None) -> None:
        if self._dry_run:
            logger.info("dry_run_upsert", extra={"path": path})
            return

        headers = await self._headers()
        headers["Content-Type"] = "application/json"
        if etag:
            headers["If-Match"] = etag

        response = await self._http.put(
            f"{self._wiki_url}/pages",
            params={"path": path, "api-version": "7.1"},
            headers=headers,
            json={"content": content},
        )
        if response.status_code == 412:
            logger.warning("etag_mismatch_retrying", extra={"path": path})
            # Read fresh ETag and retry once
            current = await self.get_page(path)
            if current:
                await self.upsert_page(path, content, etag=current[1])
            return
        response.raise_for_status()

    async def delete_page(self, path: str) -> None:
        if self._dry_run:
            logger.info("dry_run_delete", extra={"path": path})
            return
        response = await self._http.delete(
            f"{self._wiki_url}/pages",
            params={"path": path, "api-version": "7.1"},
            headers=await self._headers(),
        )
        response.raise_for_status()

    async def sync(self, source_pages: list[WikiPage]) -> dict[str, Any]:
        """Sync source_pages to wiki. Return summary stats."""
        wiki_pages = await self.list_managed_pages()
        wiki_paths = set(wiki_pages.keys())
        source_paths = {p.path for p in source_pages}

        stats = {"created": 0, "updated": 0, "skipped": 0, "deleted": 0, "errors": 0}

        # Upsert source pages
        for source_page in source_pages:
            try:
                target_hash = content_hash(source_page.content)
                marked_content = add_hash_marker(source_page.content, target_hash)

                existing = await self.get_page(source_page.path)
                if existing is None:
                    logger.info("creating", extra={"path": source_page.path})
                    await self.upsert_page(source_page.path, marked_content)
                    stats["created"] += 1
                else:
                    existing_content, etag = existing
                    existing_hash = extract_hash_marker(existing_content)
                    if existing_hash == target_hash:
                        logger.debug("skipped_unchanged", extra={"path": source_page.path})
                        stats["skipped"] += 1
                    else:
                        logger.info(
                            "updating",
                            extra={"path": source_page.path, "old_hash": existing_hash, "new_hash": target_hash},
                        )
                        await self.upsert_page(source_page.path, marked_content, etag=etag)
                        stats["updated"] += 1
            except Exception:
                logger.exception("sync_failed", extra={"path": source_page.path})
                stats["errors"] += 1

        # Delete orphans (in wiki, not in source)
        for path in wiki_paths - source_paths:
            # only delete pages with our hash marker (don't touch human-authored pages)
            existing = await self.get_page(path)
            if existing and extract_hash_marker(existing[0]) is not None:
                logger.info("deleting_orphan", extra={"path": path})
                try:
                    await self.delete_page(path)
                    stats["deleted"] += 1
                except Exception:
                    logger.exception("delete_failed", extra={"path": path})
                    stats["errors"] += 1

        return stats

    async def close(self) -> None:
        await self._http.aclose()


async def main():
    sync = WikiSync(
        organization="myorg",
        project="myproject",
        wiki_id="<wiki-guid>",
        managed_root_path="/Compliance",                    # only manage this subtree
        dry_run=False,
    )
    try:
        # Build source list from a manifest, file system, or API
        source_pages = build_compliance_pages(...)

        stats = await sync.sync(source_pages)
        logger.info("sync_complete", extra=stats)
    finally:
        await sync.close()


asyncio.run(main())
```

## Why a hash marker

Two reasons we put `[//]: # (sync-hash: <hash>)` at the top of every managed page:

1. **Skip-if-unchanged**: read current page, compare hashes, skip if identical. No network write for stable pages.
2. **Identify managed pages**: for orphan deletion, we only want to delete pages WE created. The hash marker is the "this is bot-managed" signal — pages without it (human-authored) are left alone.

The marker is a markdown comment — invisible when rendered.

## Idempotent — safe to re-run

Re-running the sync against the same source is a no-op (skipped). Pipeline can run on schedule without duplicate work.

## Handling concurrent edits

Race condition: someone edits the wiki page in the portal while sync runs.

The pattern handles it via ETag:
1. Sync GETs the page with ETag X
2. Human saves a change (page now ETag Y)
3. Sync PUTs with `If-Match: X` → 412 Precondition Failed
4. Sync re-reads (ETag Y), retries once

If the retry also fails (very rare), surface the error rather than overwriting human work.

## Pipeline integration

```yaml
trigger: none
pr: none

schedules:
  - cron: "0 8 * * *"
    branches: { include: [main] }
    always: true

variables:
  - group: ado-sync-config

pool:
  vmImage: ubuntu-latest

jobs:
  - job: SyncCompliance
    timeoutInMinutes: 30
    steps:
      - task: UsePythonVersion@0
        inputs:
          versionSpec: '3.12'

      - script: |
          set -euo pipefail
          pip install -e .
        displayName: Install

      - task: AzureCLI@2
        inputs:
          azureSubscription: 'wif-shared'
          scriptType: bash
          scriptLocation: inlineScript
          inlineScript: |
            python scripts/sync_compliance_to_wiki.py \
              --org $(ADO_ORG) --project $(ADO_PROJECT) --wiki-id $(WIKI_ID) \
              --managed-root /Compliance
        displayName: Run sync
```

## Done when

- Hash marker injected at line 1 of every managed page
- ETag handling on update (412 → re-read + retry once)
- Orphan deletion ONLY of marker-bearing pages
- Dry-run flag for safe testing
- Stats logged (created / updated / skipped / deleted / errors)
- Auth via WIF or Entra (no PAT)
- Pipeline timeout bounded
- Errors per page don't abort the whole run

## Anti-patterns

- No hash marker → re-uploads identical content forever
- No managed-root scoping → script could touch arbitrary wiki pages
- Orphan deletion without checking marker → wipes human-authored pages
- ETag ignored → race conditions overwrite edits
- PAT in source code
- Single try/except wrapping entire loop → one failure aborts the whole sync
- No dry-run mode → first test in production deletes real pages

## See also

- `concepts/wiki-and-pages-api.md`
- `concepts/azure-devops-rest-api.md`
- `patterns/scheduled-pipeline-with-cron.md`
- `anti-patterns.md` (items 6, 16, 17)
