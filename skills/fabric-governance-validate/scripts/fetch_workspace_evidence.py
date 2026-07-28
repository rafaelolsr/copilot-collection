#!/usr/bin/env python3
"""Collect live Microsoft Fabric workspace evidence for governance scoring.

Purpose:
    Resolve a Fabric workspace, run the Admin Scanner API, and normalize the
    result into the evidence JSON consumed by ``validate_governance.py``.

Usage:
    python fetch_workspace_evidence.py <workspace-id-or-name> [--out evidence.json]

Auth:
    Uses ``DefaultAzureCredential`` (no hardcoded token / PAT). The caller must
    be a Fabric Administrator. Token scope: https://api.fabric.microsoft.com/.default

Output:
    Writes normalized evidence JSON (see ``--out``, default stdout). Exit codes:
    0 ok · 2 workspace not resolved · 3 unauthorized/credential error.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
import uuid
from typing import Any

import httpx
from azure.core.credentials import AccessToken
from azure.core.exceptions import ClientAuthenticationError
from azure.identity import DefaultAzureCredential

logger = logging.getLogger("fabric_governance.fetch")

FABRIC_SCOPE = "https://api.fabric.microsoft.com/.default"
ADMIN_BASE = "https://api.fabric.microsoft.com/v1/admin"
SCAN_POLL_SECONDS = 2.0
SCAN_POLL_MAX_ATTEMPTS = 30
HTTP_TIMEOUT = 30.0


async def _get_token(credential: DefaultAzureCredential) -> str:
    """Acquire a Fabric access token off the event loop (SDK call is sync)."""
    token: AccessToken = await asyncio.to_thread(credential.get_token, FABRIC_SCOPE)
    return token.token


class AmbiguousWorkspaceError(LookupError):
    """Raised when a workspace name matches more than one workspace."""

    def __init__(self, name: str, candidates: list[tuple[str, str]]) -> None:
        self.name = name
        self.candidates = candidates
        super().__init__(name)


async def _resolve_workspace_id(client: httpx.AsyncClient, target: str) -> str | None:
    """Return the workspace id for a name or id. Returns None if unresolved.

    Raises ``AmbiguousWorkspaceError`` when a name matches multiple workspaces,
    so the caller can re-run with the unambiguous workspace id (GUID).
    """
    try:
        uuid.UUID(target)
        return target
    except ValueError:
        pass

    resp = await client.get(f"{ADMIN_BASE}/workspaces", params={"$top": "5000"})
    resp.raise_for_status()
    matches: list[tuple[str, str]] = [
        (str(ws.get("id")), str(ws.get("state", "")))
        for ws in resp.json().get("workspaces", [])
        if ws.get("name", "").casefold() == target.casefold() and ws.get("id")
    ]
    if not matches:
        return None
    if len(matches) > 1:
        raise AmbiguousWorkspaceError(target, matches)
    return matches[0][0]


async def _run_scan(client: httpx.AsyncClient, workspace_id: str) -> dict[str, Any]:
    """Run the Scanner API (getInfo -> poll scanStatus -> scanResult)."""
    init = await client.post(
        f"{ADMIN_BASE}/workspaces/getInfo",
        params={
            "lineage": "True",
            "datasourceDetails": "True",
            "getArtifactUsers": "True",
        },
        json={"workspaces": [workspace_id]},
    )
    init.raise_for_status()
    scan_id = init.json()["id"]

    for _ in range(SCAN_POLL_MAX_ATTEMPTS):
        status = await client.get(f"{ADMIN_BASE}/workspaces/scanStatus/{scan_id}")
        status.raise_for_status()
        if status.json().get("status") == "Succeeded":
            break
        await asyncio.sleep(SCAN_POLL_SECONDS)
    else:
        raise TimeoutError(f"Scan {scan_id} did not complete in time")

    result = await client.get(f"{ADMIN_BASE}/workspaces/scanResult/{scan_id}")
    result.raise_for_status()
    payload: dict[str, Any] = result.json()
    payload["_scan_id"] = scan_id
    return payload


def _normalize(scan: dict[str, Any]) -> dict[str, Any]:
    """Reduce a Scanner payload to the evidence shape the scorer expects."""
    workspaces = scan.get("workspaces", [])
    if not workspaces:
        return {"workspace": {}, "roles": {}, "items": []}
    ws = workspaces[0]

    users = ws.get("users", [])
    admin_count = sum(1 for u in users if u.get("groupUserAccessRight") == "Admin")
    guest_count = sum(
        1
        for u in users
        if u.get("principalType") == "User" and "#EXT#" in u.get("userPrincipalName", "")
    )
    sp_count = sum(1 for u in users if u.get("principalType") == "App")

    item_keys = ("reports", "datasets", "dataflows", "dashboards", "datamarts")
    items: list[dict[str, Any]] = []
    for key in item_keys:
        for it in ws.get(key, []):
            # Owner: datasets/dataflows/datamarts expose ``configuredBy``;
            # reports expose ``createdBy``. Absent on item types that carry no
            # owner (e.g. some dashboards) -> scored as a missing owner.
            owner = it.get("configuredBy") or it.get("createdBy")
            # Per-item direct grants, available because getArtifactUsers=True.
            artifact_users = it.get("users") or []
            items.append(
                {
                    "name": it.get("name"),
                    "type": key,
                    "owner": owner,
                    "directAccessCount": len(artifact_users),
                    "sensitivityLabel": (it.get("sensitivityLabel") or {}).get("labelId"),
                    "endorsement": (it.get("endorsementDetails") or {}).get("endorsement"),
                }
            )

    return {
        "workspace": {
            "id": ws.get("id"),
            "name": ws.get("name"),
            "description": ws.get("description"),
            "capacityId": ws.get("capacityId"),
            "domainId": ws.get("domainId"),
            "deploymentPipelineId": ws.get("pipelineId") or ws.get("deploymentPipelineId"),
            "gitConnected": bool(ws.get("hasGitConnection")),
            "dlpEnabled": ws.get("dlpEnabled"),
        },
        "roles": {
            "admin_count": admin_count,
            "guest_count": guest_count,
            "service_principal_count": sp_count,
            "assignments": [
                {"principal": u.get("displayName"), "role": u.get("groupUserAccessRight")}
                for u in users
            ],
        },
        "items": items,
        "provenance": {"source": "scanner-api", "scan_id": scan.get("_scan_id")},
    }


async def collect(target: str) -> dict[str, Any]:
    """Resolve, scan, and normalize. Raises on auth/resolution failure."""
    credential = DefaultAzureCredential()
    token = await _get_token(credential)
    headers = {"Authorization": f"Bearer {token}"}
    async with httpx.AsyncClient(headers=headers, timeout=HTTP_TIMEOUT) as client:
        workspace_id = await _resolve_workspace_id(client, target)
        if workspace_id is None:
            raise LookupError(target)
        scan = await _run_scan(client, workspace_id)
        return _normalize(scan)


async def _main() -> int:
    parser = argparse.ArgumentParser(description="Collect Fabric workspace governance evidence.")
    parser.add_argument("workspace", help="Workspace id or name")
    parser.add_argument("--out", default="-", help="Output path, or '-' for stdout")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")

    try:
        evidence = await collect(args.workspace)
    except AmbiguousWorkspaceError as exc:
        logger.error(
            "Workspace name %r matches %d workspaces. Re-run with the workspace id (GUID):",
            exc.name,
            len(exc.candidates),
        )
        for ws_id, state in exc.candidates:
            logger.error("  %s  (state=%s)", ws_id, state or "unknown")
        return 2
    except LookupError:
        logger.error("Workspace not resolved: %s", args.workspace)
        return 2
    except (ClientAuthenticationError, httpx.HTTPStatusError) as exc:
        logger.error("Authorization or API error: %s", type(exc).__name__)
        return 3

    text = json.dumps(evidence, indent=2)
    if args.out == "-":
        print(text)
    else:
        from pathlib import Path

        await asyncio.to_thread(Path(args.out).write_text, text, "utf-8")
        logger.info("Wrote evidence to %s", args.out)
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(_main()))
