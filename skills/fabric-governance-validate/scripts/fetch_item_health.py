#!/usr/bin/env python3
"""Collect semantic-model health (refresh + ownership) via the Power BI REST API.

Purpose:
    Adds per-semantic-model operational evidence to the governance run:
    publisher (``configuredBy``), creation date, and the most recent refresh
    (status, end time, error). Feeds the ``refresh-health`` and
    ``refresh-recency`` controls plus the "Semantic model health" inventory.

Usage:
    python fetch_item_health.py <workspace-id> [--out health.json] [--merge evidence.json]

Auth:
    ``DefaultAzureCredential``. Token scope:
    https://analysis.windows.net/powerbi/api/.default
    Callable by a workspace Admin/Member. Exit codes: 0 ok · 3 unauthorized.

Output:
    Writes ``{"semantic_models": [...], "provenance": {...}}``. With ``--merge``
    the keys are merged into an existing evidence JSON so a single file feeds
    the scorer.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path
from typing import Any

import httpx
from azure.core.credentials import AccessToken
from azure.core.exceptions import ClientAuthenticationError
from azure.identity import DefaultAzureCredential

logger = logging.getLogger("fabric_governance.fetch_health")

PBI_SCOPE = "https://analysis.windows.net/powerbi/api/.default"
PBI_BASE = "https://api.powerbi.com/v1.0/myorg"
HTTP_TIMEOUT = 30.0


async def _get_token(credential: DefaultAzureCredential) -> str:
    token: AccessToken = await asyncio.to_thread(credential.get_token, PBI_SCOPE)
    return token.token


def _extract_error(refresh: dict[str, Any]) -> str | None:
    """Pull a short error message out of a failed refresh record."""
    raw = refresh.get("serviceExceptionJson")
    if not raw:
        return None
    try:
        parsed = json.loads(raw)
        return str(parsed.get("errorCode") or parsed.get("errorDescription") or raw)[:200]
    except (json.JSONDecodeError, TypeError):
        return str(raw)[:200]


async def _last_refresh(
    client: httpx.AsyncClient, ws: str, dataset_id: str
) -> dict[str, Any] | None:
    """Return the most recent refresh record, or None when unavailable."""
    resp = await client.get(
        f"{PBI_BASE}/groups/{ws}/datasets/{dataset_id}/refreshes", params={"$top": "1"}
    )
    if resp.status_code != 200:
        return None
    history = resp.json().get("value", [])
    if not history:
        return None
    r = history[0]
    return {
        "status": r.get("status"),
        "startTime": r.get("startTime"),
        "endTime": r.get("endTime") or r.get("startTime"),
        "refreshType": r.get("refreshType"),
        "error": _extract_error(r) if r.get("status") == "Failed" else None,
    }


async def collect(workspace_id: str) -> dict[str, Any]:
    """Collect semantic-model health. Raises on auth failure."""
    credential = DefaultAzureCredential()
    token = await _get_token(credential)
    headers = {"Authorization": f"Bearer {token}"}
    async with httpx.AsyncClient(headers=headers, timeout=HTTP_TIMEOUT) as client:
        resp = await client.get(f"{PBI_BASE}/groups/{workspace_id}/datasets")
        resp.raise_for_status()
        datasets = resp.json().get("value", [])

        models: list[dict[str, Any]] = []
        for d in datasets:
            refresh = None
            if d.get("isRefreshable"):
                refresh = await _last_refresh(client, workspace_id, d["id"])
            models.append(
                {
                    "name": d.get("name"),
                    "id": d.get("id"),
                    "publisher": d.get("configuredBy"),
                    "createdDate": d.get("createdDate"),
                    "isRefreshable": bool(d.get("isRefreshable")),
                    "lastRefresh": refresh,
                }
            )

    return {
        "semantic_models": models,
        "provenance": {
            "source": "powerbi-rest",
            "note": (
                "Report authors and true last-published timestamps require the "
                "tenant Admin Scanner API and are not collected here."
            ),
        },
    }


async def _main() -> int:
    parser = argparse.ArgumentParser(description="Collect Power BI semantic-model health evidence.")
    parser.add_argument("workspace_id", help="Workspace id (GUID)")
    parser.add_argument("--out", default="-", help="Output path, or '-' for stdout")
    parser.add_argument("--merge", help="Merge into this existing evidence JSON file")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")

    try:
        health = await collect(args.workspace_id.strip())
    except ClientAuthenticationError as exc:
        logger.error("Authorization error: %s", type(exc).__name__)
        return 3
    except httpx.HTTPStatusError as exc:
        logger.error("API error: %s", exc.response.status_code)
        return 3

    if args.merge:
        merge_path = Path(args.merge)
        try:
            base: dict[str, Any] = json.loads(merge_path.read_text("utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            logger.error("Cannot read --merge file: %s", type(exc).__name__)
            return 4
        base["semantic_models"] = health["semantic_models"]
        await asyncio.to_thread(merge_path.write_text, json.dumps(base, indent=2), "utf-8")
        logger.info("Merged %d models into %s", len(health["semantic_models"]), args.merge)
        return 0

    text = json.dumps(health, indent=2)
    if args.out == "-":
        print(text)
    else:
        await asyncio.to_thread(Path(args.out).write_text, text, "utf-8")
        logger.info("Wrote health evidence to %s", args.out)
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(_main()))
