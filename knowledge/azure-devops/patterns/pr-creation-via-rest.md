# PR creation via REST API

> **Last validated**: 2026-04-26
> **Confidence**: 0.89

## When to use this pattern

Programmatically creating a pull request — typically as the final step of an automated change pipeline (TMDL deploy, dependency update, scaffolded code, compliance fix).

## Implementation — full flow

```python
"""Create a branch, commit changes, open a PR. Bot-authored."""
from __future__ import annotations

import asyncio
import base64
import logging
from typing import Any

import httpx
from azure.identity import DefaultAzureCredential
from tenacity import (
    AsyncRetrying,
    retry_if_exception,
    stop_after_attempt,
    wait_random_exponential,
)

logger = logging.getLogger(__name__)


def _is_throttled(exc):
    return isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code in (429, 503)


class ADOClient:
    """Minimal Azure DevOps REST client with Entra auth."""

    def __init__(self, organization: str, project: str):
        self._org = organization
        self._project = project
        self._cred = DefaultAzureCredential()
        self._http = httpx.AsyncClient(timeout=30.0)

    async def _headers(self) -> dict[str, str]:
        token = self._cred.get_token("499b84ac-1321-427f-aa17-267ca6975798/.default").token
        return {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

    async def _request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        url = f"https://dev.azure.com/{self._org}/{self._project}/_apis{path}"
        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(5),
            wait=wait_random_exponential(min=2, max=60),
            retry=retry_if_exception(_is_throttled),
            reraise=True,
        ):
            with attempt:
                response = await self._http.request(method, url, headers=await self._headers(), **kwargs)
                if response.status_code == 429:
                    retry_after = int(response.headers.get("Retry-After", "10"))
                    await asyncio.sleep(retry_after)
                    response.raise_for_status()
                response.raise_for_status()
                return response
        raise RuntimeError("unreachable")

    # ---------- Repos ----------

    async def get_repository(self, repo_name: str) -> dict:
        response = await self._request(
            "GET",
            f"/git/repositories/{repo_name}?api-version=7.1",
        )
        return response.json()

    async def get_branch_head(self, repo_id: str, branch: str) -> str:
        """Return the latest commit SHA on a branch."""
        response = await self._request(
            "GET",
            f"/git/repositories/{repo_id}/refs?filter=heads/{branch}&api-version=7.1",
        )
        refs = response.json()["value"]
        if not refs:
            raise ValueError(f"Branch '{branch}' not found")
        return refs[0]["objectId"]

    async def push_changes(
        self,
        repo_id: str,
        *,
        new_branch: str,
        base_branch: str,
        files: dict[str, str],                    # path → content
        commit_message: str,
    ) -> str:
        """Create a new branch with the given file changes. Returns the commit SHA."""
        base_sha = await self.get_branch_head(repo_id, base_branch)

        # Construct change records
        changes = []
        for path, content in files.items():
            changes.append({
                "changeType": "edit",                # or "add" for new files; "edit" works for both as of API 7.1
                "item": {"path": path},
                "newContent": {
                    "content": base64.b64encode(content.encode()).decode(),
                    "contentType": "base64encoded",
                },
            })

        body = {
            "refUpdates": [
                {
                    "name": f"refs/heads/{new_branch}",
                    "oldObjectId": "0000000000000000000000000000000000000000",
                }
            ],
            "commits": [
                {
                    "comment": commit_message,
                    "changes": changes,
                }
            ],
        }
        # Update refUpdates: branch off base
        body["refUpdates"][0]["oldObjectId"] = base_sha

        response = await self._request(
            "POST",
            f"/git/repositories/{repo_id}/pushes?api-version=7.1",
            json=body,
        )
        return response.json()["commits"][0]["commitId"]

    # ---------- Pull Requests ----------

    async def create_pr(
        self,
        repo_id: str,
        *,
        source_branch: str,
        target_branch: str,
        title: str,
        description: str,
        reviewers: list[str] | None = None,        # Entra object IDs
        is_draft: bool = False,
    ) -> dict:
        body = {
            "sourceRefName": f"refs/heads/{source_branch}",
            "targetRefName": f"refs/heads/{target_branch}",
            "title": title,
            "description": description,
            "isDraft": is_draft,
        }
        if reviewers:
            body["reviewers"] = [{"id": r, "isRequired": False} for r in reviewers]

        response = await self._request(
            "POST",
            f"/git/repositories/{repo_id}/pullrequests?api-version=7.1",
            json=body,
        )
        return response.json()

    async def add_pr_comment(self, repo_id: str, pr_id: int, content: str) -> dict:
        body = {
            "comments": [{"parentCommentId": 0, "content": content, "commentType": 1}],
            "status": 1,                            # 1 = active
        }
        response = await self._request(
            "POST",
            f"/git/repositories/{repo_id}/pullRequests/{pr_id}/threads?api-version=7.1",
            json=body,
        )
        return response.json()

    async def close(self) -> None:
        await self._http.aclose()


async def main():
    client = ADOClient(organization="myorg", project="myproject")
    try:
        # 1. Find the repo
        repo = await client.get_repository("my-repo")
        repo_id = repo["id"]

        # 2. Push changes to a new branch
        commit_sha = await client.push_changes(
            repo_id,
            new_branch="bot/dependency-update-2026-04-26",
            base_branch="main",
            files={
                "pyproject.toml": new_pyproject_content,
                "uv.lock": new_lock_content,
            },
            commit_message="Bump dependencies (automated)",
        )
        logger.info("pushed", extra={"commit": commit_sha})

        # 3. Create the PR
        pr = await client.create_pr(
            repo_id,
            source_branch="bot/dependency-update-2026-04-26",
            target_branch="main",
            title="Bump dependencies — automated",
            description=(
                "## Summary\n\n"
                "- bump anthropic 0.39.0 → 0.40.1\n"
                "- bump pydantic 2.9.0 → 2.10.0\n"
                "\n"
                "## Verification\n\n"
                "- `uv sync` passes\n"
                "- `pytest -m \"not eval\"` passes\n"
            ),
            reviewers=["<entra-object-id-of-team>"],
        )
        logger.info("pr_created", extra={"pr_id": pr["pullRequestId"], "url": pr["url"]})

        # 4. Optional: post initial comment
        await client.add_pr_comment(
            repo_id,
            pr["pullRequestId"],
            content="Generated by dependency-update bot. CI will verify.",
        )
    finally:
        await client.close()


asyncio.run(main())
```

## Setting reviewers properly

Three reviewer types:

| Field | Effect |
|---|---|
| `id` (regular user/group) | Adds to the reviewer list |
| `isRequired: true` | Must approve before merge |
| `vote: 10` | Pre-approval (rare; for self-approve scenarios) |

For a bot PR, leave reviewers as `isRequired: false` unless your team policy demands required approval from a specific identity.

## Polling for completion

PR creation returns immediately. To wait until merged:

```python
async def wait_for_merge(client, repo_id, pr_id, timeout: float = 3600):
    deadline = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < deadline:
        response = await client._request(
            "GET",
            f"/git/repositories/{repo_id}/pullrequests/{pr_id}?api-version=7.1",
        )
        pr = response.json()
        if pr["status"] == "completed":
            return pr
        if pr["status"] == "abandoned":
            raise RuntimeError(f"PR {pr_id} was abandoned")
        await asyncio.sleep(30)
    raise TimeoutError(f"PR {pr_id} not completed in {timeout}s")
```

For automated flows: usually you DON'T wait — the PR is for human review. Wait only if the bot also needs to do follow-up after merge.

## Auto-complete (auto-merge once policies pass)

```python
async def set_auto_complete(client, repo_id, pr_id, *, completed_by_id: str, message: str):
    body = {
        "autoCompleteSetBy": {"id": completed_by_id},
        "completionOptions": {
            "deleteSourceBranch": True,
            "mergeCommitMessage": message,
            "squashMerge": True,
        },
    }
    response = await client._request(
        "PATCH",
        f"/git/repositories/{repo_id}/pullrequests/{pr_id}?api-version=7.1",
        json=body,
    )
    return response.json()
```

`completed_by_id` is the Entra object ID of the bot. Once policies pass (build, reviewers), the PR auto-merges.

Useful for: low-risk automated changes (dependency bumps, formatting fixes). Not for: anything touching prod code.

## Common bugs

- `oldObjectId` of `0000...` for refUpdates when branch already exists (need actual SHA)
- Base64 encoding wrong (string vs bytes confusion)
- Reviewers field uses display names instead of Entra GUIDs
- `commentType: 1` (active) vs `2` (text-only) — most bot comments should be `1`
- Tried to create PR before push completed (race; await push response)
- `targetRefName` includes `refs/heads/` prefix vs not — must include
- API version mismatch — some operations need preview versions

## Done when

- Auth via `DefaultAzureCredential` (no PAT)
- Branch name follows convention (`bot/<purpose>-<date>`)
- Commit message is meaningful (not "automated update")
- PR description has Summary + Verification sections
- 429 retries handled
- Errors log request ID for support
- Branch deleted on merge (`deleteSourceBranch: true`)

## Anti-patterns

- PAT in the code (use Entra)
- Branch named `bot-update` (not unique → conflicts on parallel runs)
- PR description empty or "automated"
- Auto-complete on production-touching code
- Reviewers hardcoded by display name (use Entra object ID)
- Missing 429 handling (fails on first throttle)
- Race: create PR before push commits land

## See also

- `concepts/azure-devops-rest-api.md`
- `concepts/branch-policies.md` — what auto-complete waits for
- `patterns/pipeline-with-wif.md` — auth context
- `anti-patterns.md` (items 1, 12, 15)
