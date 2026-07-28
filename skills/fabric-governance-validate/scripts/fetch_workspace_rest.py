#!/usr/bin/env python3
"""Collect Fabric workspace governance evidence via workspace-scoped REST APIs.

Purpose:
    A non-tenant-admin alternative to ``fetch_workspace_evidence.py``. Uses the
    workspace-scoped Fabric REST endpoints (``/v1/workspaces/{id}``,
    ``/roleAssignments``, ``/items``, ``/git/connection``) that a workspace
    Admin/Member can call without the tenant Fabric Administrator role required
    by the Admin Scanner API.

Coverage:
    Provides real evidence for roles, capacity, description, Git, and sensitivity
    labels. Fields only the Admin Scanner exposes (guest UPNs, endorsement,
    domain, DLP, deployment pipeline) are left absent so the scorer marks those
    controls ``unknown`` rather than guessing.

Usage:
    python fetch_workspace_rest.py <workspace-id> [--out evidence.json]

Auth:
    ``DefaultAzureCredential``. Token scope: https://api.fabric.microsoft.com/.default
    Caller must have a workspace role (Admin/Member/Contributor). Exit codes:
    0 ok · 2 workspace not found · 3 unauthorized/credential error.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from typing import Any

import httpx
from azure.core.credentials import AccessToken
from azure.core.exceptions import ClientAuthenticationError
from azure.identity import DefaultAzureCredential

logger = logging.getLogger("fabric_governance.fetch_rest")

FABRIC_SCOPE = "https://api.fabric.microsoft.com/.default"
REST_BASE = "https://api.fabric.microsoft.com/v1"
HTTP_TIMEOUT = 30.0


async def _get_token(credential: DefaultAzureCredential) -> str:
    """Acquire a Fabric access token off the event loop (SDK call is sync)."""
    token: AccessToken = await asyncio.to_thread(credential.get_token, FABRIC_SCOPE)
    return token.token


async def _get_json(client: httpx.AsyncClient, path: str) -> dict[str, Any]:
    resp = await client.get(f"{REST_BASE}/{path}")
    resp.raise_for_status()
    data: dict[str, Any] = resp.json()
    return data


async def _find_deployment_pipeline(client: httpx.AsyncClient, workspace_id: str) -> str | None:
    """Return a deployment pipeline id this workspace is assigned to, if any.

    Uses the workspace-accessible ``/deploymentPipelines`` endpoints. Returns
    None when the workspace is in no pipeline or the API is not accessible.
    """
    try:
        pipelines = (await _get_json(client, "deploymentPipelines")).get("value", [])
    except httpx.HTTPStatusError:
        return None
    for pipeline in pipelines:
        pid = pipeline.get("id")
        if not pid:
            continue
        try:
            stages = (await _get_json(client, f"deploymentPipelines/{pid}/stages")).get("value", [])
        except httpx.HTTPStatusError:
            continue
        if any(s.get("workspaceId") == workspace_id for s in stages):
            return str(pid)
    return None


def _summarize_roles(assignments: list[dict[str, Any]]) -> dict[str, Any]:
    admin = sum(1 for a in assignments if a.get("role") == "Admin")
    sp = sum(1 for a in assignments if a.get("principal", {}).get("type") == "ServicePrincipal")
    return {
        "admin_count": admin,
        "service_principal_count": sp,
        # guest detection needs UPNs, which the workspace-scoped API does not
        # expose — omit so the scorer reports `unknown`, never a false pass.
        "guest_count": None,
        "assignments": [
            {"principal": a.get("principal", {}).get("displayName"), "role": a.get("role")}
            for a in assignments
        ],
    }


async def collect(workspace_id: str) -> dict[str, Any]:
    """Collect workspace-scoped evidence. Raises on auth/not-found failure."""
    credential = DefaultAzureCredential()
    token = await _get_token(credential)
    headers = {"Authorization": f"Bearer {token}"}
    async with httpx.AsyncClient(headers=headers, timeout=HTTP_TIMEOUT) as client:
        ws = await _get_json(client, f"workspaces/{workspace_id}")
        roles = (await _get_json(client, f"workspaces/{workspace_id}/roleAssignments")).get(
            "value", []
        )
        items = (await _get_json(client, f"workspaces/{workspace_id}/items")).get("value", [])

        git_connected: bool | None = None
        try:
            git = await _get_json(client, f"workspaces/{workspace_id}/git/connection")
            git_connected = git.get("gitConnectionState") == "ConnectedAndInitialized"
        except httpx.HTTPStatusError:
            git_connected = None  # endpoint not available to this caller

        pipeline_id = await _find_deployment_pipeline(client, workspace_id)

    return {
        "workspace": {
            "id": ws.get("id"),
            "name": ws.get("displayName"),
            "description": ws.get("description"),
            "capacityId": ws.get("capacityId"),
            "gitConnected": git_connected,
            # Scanner-only fields: leave absent -> scorer marks `unknown`.
            "domainId": None,
            "deploymentPipelineId": pipeline_id,
            "dlpEnabled": None,
        },
        "roles": _summarize_roles(roles),
        "items": [
            {
                "name": it.get("displayName"),
                "type": it.get("type"),
                "sensitivityLabel": (it.get("sensitivityLabel") or {}).get("id"),
                # owner / direct grants are Scanner-only -> absent -> `unknown`.
                "owner": None,
                "directAccessCount": None,
                # endorsement is Scanner-only -> absent -> `unknown`.
                "endorsement": None,
            }
            for it in items
        ],
        "provenance": {
            "source": "workspace-rest",
            "coverage_note": (
                "Tenant/Scanner-only controls (no-guest-access, endorsement, "
                "domain-assignment, dlp-coverage) are unknown via the "
                "workspace-scoped API. Run with --scope workspace to hide them."
            ),
        },
    }


async def _main() -> int:
    parser = argparse.ArgumentParser(
        description="Collect workspace-scoped Fabric governance evidence."
    )
    parser.add_argument("workspace_id", help="Workspace id (GUID)")
    parser.add_argument("--out", default="-", help="Output path, or '-' for stdout")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")

    try:
        evidence = await collect(args.workspace_id.strip())
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 404:
            logger.error("Workspace not found: %s", args.workspace_id)
            return 2
        logger.error("API error: %s", exc.response.status_code)
        return 3
    except ClientAuthenticationError as exc:
        logger.error("Authorization error: %s", type(exc).__name__)
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
