#!/usr/bin/env python3
"""Score Fabric workspace evidence against the governance control rubric.

Purpose:
    Pure, deterministic scorer. Joins ``_controls.CONTROLS`` with an evidence
    JSON file and emits per-control findings. No network access.

Usage:
    python validate_governance.py --evidence evidence.json [--format markdown|json]
    python validate_governance.py --learn-only [--format markdown|json]

Output:
    Markdown report (default) or JSON findings on stdout. Exit codes:
    0 ok · 4 evidence file not found or invalid.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Literal

from _controls import CONTROLS, Control
from pydantic import BaseModel, Field

Verdict = Literal["pass", "fail", "unknown"]
_MISSING = object()
SEVERITY_RANK: dict[str, int] = {"high": 0, "medium": 1, "low": 2}


class Finding(BaseModel):
    """One control's evaluation outcome."""

    control_id: str
    severity: str
    verdict: Verdict
    observed: str
    requirement: str
    evidence_key: str
    learn_citation: str = Field(default="unverified")
    remediation: str = Field(default="")


def _dig(node: Any, dotted: str) -> Any:
    """Follow a dotted path through nested dicts. _MISSING if absent."""
    for part in dotted.split("."):
        if not isinstance(node, dict) or part not in node:
            return _MISSING
        node = node[part]
    return node


def _resolve(evidence: dict[str, Any], key: str) -> Any:
    """Resolve a dotted evidence key. Supports one ``[]`` list projection,
    with an optional nested dotted path after it (e.g. ``a[].b.c``)."""
    if "[]" in key:
        head, tail = key.split("[].", 1)
        container = _resolve(evidence, head)
        if not isinstance(container, list):
            return _MISSING
        return [_dig(item, tail) for item in container]
    return _dig(evidence, key)


def _parse_iso(value: str) -> datetime | None:
    """Parse an ISO-8601 timestamp (with trailing Z) to an aware datetime."""
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None


def _evaluate(control: Control, value: Any, now: datetime) -> tuple[Verdict, str]:
    """Apply a control's check to a resolved value -> (verdict, observed)."""
    if control.check == "none_failed" and isinstance(value, list):
        statuses = [s for s in value if s not in (_MISSING, None, "")]
        if not statuses:
            return "unknown", "no refresh history"
        failed = sum(1 for s in statuses if s == "Failed")
        return ("fail" if failed else "pass"), f"{failed} failed of {len(statuses)}"
    if control.check == "all_recent_days" and isinstance(value, list):
        days = control.bounds[0] or 1
        times = [t for v in value if (t := _parse_iso(v)) is not None] if value else []
        if not times:
            return "unknown", "no refresh timestamps"
        cutoff = now - timedelta(days=days)
        stale = sum(1 for t in times if t < cutoff)
        return ("fail" if stale else "pass"), f"{stale} older than {days}d of {len(times)}"

    if value is _MISSING or value is None:
        return "unknown", "no evidence"

    lo, hi = control.bounds
    if control.check == "int_between" and isinstance(value, int):
        ok = (lo is None or value >= lo) and (hi is None or value <= hi)
        return ("pass" if ok else "fail"), f"{value}"
    if control.check == "int_min" and isinstance(value, int):
        return ("pass" if lo is None or value >= lo else "fail"), f"{value}"
    if control.check == "int_max" and isinstance(value, int):
        return ("pass" if hi is None or value <= hi else "fail"), f"{value}"
    if control.check == "is_true":
        return ("pass" if value is True else "fail"), f"{value}"
    if control.check == "present":
        present = bool(value)
        return ("pass" if present else "fail"), ("present" if present else "absent")
    if control.check == "all_items_truthy" and isinstance(value, list):
        total = len(value)
        if total == 0:
            return "unknown", "no items"
        populated = [v for v in value if v not in (_MISSING, None, "")]
        if not populated:
            # Attribute not populated on any item -> the source carries no
            # evidence for it. Report unknown, never a false fail.
            return "unknown", "attribute not populated"
        return ("pass" if len(populated) == total else "fail"), f"{len(populated)} of {total}"
    return "unknown", "uninterpretable evidence"


def score(
    evidence: dict[str, Any] | None,
    citations: dict[str, str],
    scope: str = "all",
) -> list[Finding]:
    """Produce a finding for every control. evidence=None -> all unknown.

    ``scope`` filters the control set: ``workspace`` keeps only controls
    evaluable from a workspace role, ``tenant`` keeps only admin-scoped ones,
    ``all`` (default) keeps every control.
    """
    findings: list[Finding] = []
    now = datetime.now(UTC)
    for control in CONTROLS:
        if scope != "all" and control.scope != scope:
            continue
        verdict: Verdict
        observed: str
        if evidence is None:
            verdict, observed = "unknown", "learn-only — no evidence"
        else:
            verdict, observed = _evaluate(control, _resolve(evidence, control.evidence_key), now)
        findings.append(
            Finding(
                control_id=control.id,
                severity=control.severity,
                verdict=verdict,
                observed=observed,
                requirement=control.requirement,
                evidence_key=control.evidence_key,
                learn_citation=citations.get(control.id, "unverified"),
            )
        )
    return findings


def _render_inventory(evidence: dict[str, Any] | None) -> list[str]:
    """Render the semantic-model health table, if that evidence is present."""
    models = (evidence or {}).get("semantic_models")
    if not models:
        return []
    lines = [
        "",
        "## Semantic model health",
        "",
        "| Model | Publisher | Last refresh | Status | Error |",
        "|---|---|---|---|---|",
    ]
    for m in models:
        r = m.get("lastRefresh") or {}
        status = r.get("status") or "—"
        flag = {"Completed": "✅", "Failed": "❌", "Unknown": "⏳"}.get(status, "")
        err = (r.get("error") or "").replace("|", "/")[:60] or "—"
        lines.append(
            f"| {m.get('name', '?')} | {m.get('publisher') or '—'} "
            f"| {r.get('endTime') or '—'} | {flag} {status} | {err} |"
        )
    return lines


def _render_ownership(evidence: dict[str, Any] | None) -> list[str]:
    """Render the object-ownership inventory, if item evidence carries owners."""
    items = (evidence or {}).get("items") or []
    # Only render when owner evidence is actually present (Scanner runs).
    if not any(it.get("owner") is not None for it in items):
        return []
    lines = [
        "",
        "## Object ownership",
        "",
        "| Item | Type | Owner | Direct grants |",
        "|---|---|---|---|",
    ]
    for it in sorted(items, key=lambda i: (i.get("owner") is not None, str(i.get("type")))):
        owner = it.get("owner") or "⚠️ none"
        grants = it.get("directAccessCount")
        grants_cell = "—" if grants is None else str(grants)
        lines.append(
            f"| {it.get('name', '?')} | {it.get('type', '?')} | {owner} | {grants_cell} |"
        )
    return lines


def _render_markdown(findings: list[Finding], evidence: dict[str, Any] | None) -> str:
    ws = (evidence or {}).get("workspace", {})
    name = ws.get("name", "unknown")
    ws_id = ws.get("id", "n/a")
    mode = "learn-only" if evidence is None else "hybrid"
    passes = sum(1 for f in findings if f.verdict == "pass")
    fails = sum(1 for f in findings if f.verdict == "fail")
    unknowns = sum(1 for f in findings if f.verdict == "unknown")
    total = len(findings)

    lines = [
        f"# Fabric governance: {name} ({ws_id})",
        "",
        "## Summary",
        "",
        f"Mode: {mode} · Score: {passes}/{total} controls",
        f"Verdicts: {passes} pass · {fails} fail · {unknowns} unknown",
        "",
        "## Controls",
        "",
        "| Control | Verdict | Observed | Requirement | Source |",
        "|---|---|---|---|---|",
    ]
    for f in findings:
        lines.append(
            f"| {f.control_id} | {f.verdict} | {f.observed} | {f.requirement} | {f.learn_citation} |"
        )

    gaps = sorted(
        (f for f in findings if f.verdict in ("fail", "unknown")),
        key=lambda f: (SEVERITY_RANK.get(f.severity, 9), f.control_id),
    )
    lines += ["", "## Gaps and remediation", ""]
    if not gaps:
        lines.append("No gaps — all controls pass.")
    for f in gaps:
        lines.append(
            f"- **{f.control_id}** ({f.severity}, {f.verdict}): {f.requirement} — observed {f.observed}. See {f.learn_citation}"
        )

    lines += _render_inventory(evidence)
    lines += _render_ownership(evidence)

    prov = (evidence or {}).get("provenance", {})
    lines += [
        "",
        "## Evidence provenance",
        "",
        (
            f"Source: {prov.get('source')} · scan: {prov.get('scan_id')}"
            if evidence
            else "learn-only — no evidence collected"
        ),
        "",
        "## Next step",
        "",
        (
            "Address the highest-severity gap above."
            if gaps
            else "Re-run after the next workspace change."
        ),
    ]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Score Fabric governance evidence.")
    parser.add_argument("--evidence", help="Path to evidence JSON")
    parser.add_argument(
        "--learn-only", action="store_true", help="No evidence; all controls unknown"
    )
    parser.add_argument("--format", choices=("markdown", "json"), default="markdown")
    parser.add_argument(
        "--scope",
        choices=("all", "workspace", "tenant"),
        default="all",
        help="Filter controls: 'workspace' = evaluable from a workspace role only.",
    )
    parser.add_argument("--citations", help="Optional JSON map control_id -> Learn URL")
    args = parser.parse_args()

    evidence: dict[str, Any] | None = None
    if not args.learn_only:
        if not args.evidence:
            parser.error("provide --evidence PATH or --learn-only")
        try:
            evidence = json.loads(Path(args.evidence).read_text("utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            print(f"error: cannot read evidence: {type(exc).__name__}", file=sys.stderr)
            return 4

    citations: dict[str, str] = {}
    if args.citations:
        try:
            citations = json.loads(Path(args.citations).read_text("utf-8"))
        except (OSError, json.JSONDecodeError):
            citations = {}

    findings = score(evidence, citations, scope=args.scope)
    if args.format == "json":
        print(json.dumps([f.model_dump() for f in findings], indent=2))
    else:
        print(_render_markdown(findings, evidence))
    return 0


if __name__ == "__main__":
    sys.exit(main())
