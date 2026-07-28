#!/usr/bin/env python3
"""Prove a Power BI semantic model was not modified during reverse-engineering.

Purpose
    The powerbi-modeling-mcp can WRITE to models; this skill is read-only by
    policy, not by a server flag. This script produces tamper-evident proof of
    that policy by hashing the model's TMDL definition before and after a
    session and asserting they are identical. The MCP can only perform *modeling*
    operations, all of which surface in the TMDL definition, so an unchanged TMDL
    digest is sufficient evidence that no modeling change occurred.

Usage
    # 1. Before connecting the MCP, snapshot the exported TMDL folder:
    python readonly_evidence.py snapshot <tmdl-dir> -o before.json

    # 2. After the session, re-export the TMDL and snapshot again:
    python readonly_evidence.py snapshot <tmdl-dir> -o after.json

    # 3. Compare and emit an evidence report (exit 0 = unchanged, 3 = changed):
    python readonly_evidence.py compare before.json after.json \
        [--tool-log calls.jsonl] [--report evidence.md]

Tool-log scan (optional)
    If you capture MCP tool calls as JSON lines ({"tool": ..., "operation": ...}),
    pass --tool-log to additionally flag any mutating operation
    (create/update/delete/rename/move/deploy/import/refresh/commit/...).

Exit codes
    0 unchanged (and no mutating tool calls)  2 bad input  3 model changed or
    mutating tool call detected.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

_MUTATING = (
    "create",
    "update",
    "delete",
    "rename",
    "move",
    "deploy",
    "import",
    "refresh",
    "begin",
    "commit",
    "rollback",
    "activate",
    "deactivate",
    "reorder",
    "set",
)


def _hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


def snapshot(tmdl_dir: Path) -> dict[str, object]:
    files: dict[str, str] = {}
    for path in sorted(tmdl_dir.rglob("*.tmdl")):
        files[str(path.relative_to(tmdl_dir)).replace("\\", "/")] = _hash_file(path)
    combined = hashlib.sha256()
    for rel in sorted(files):
        combined.update(rel.encode("utf-8"))
        combined.update(files[rel].encode("utf-8"))
    return {"root": str(tmdl_dir), "fileCount": len(files), "files": files,
            "digest": combined.hexdigest()}


def _diff(before: dict[str, str], after: dict[str, str]) -> list[str]:
    findings: list[str] = []
    for rel in sorted(set(before) - set(after)):
        findings.append(f"removed: {rel}")
    for rel in sorted(set(after) - set(before)):
        findings.append(f"added: {rel}")
    for rel in sorted(set(before) & set(after)):
        if before[rel] != after[rel]:
            findings.append(f"modified: {rel}")
    return findings


def _scan_tool_log(path: Path) -> list[str]:
    flagged: list[str] = []
    for num, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        try:
            call = json.loads(line)
        except json.JSONDecodeError:
            continue
        op = str(call.get("operation") or call.get("action") or "").lower()
        tool = str(call.get("tool") or call.get("name") or "").lower()
        if any(op.startswith(verb) or f"_{verb}" in op for verb in _MUTATING):
            flagged.append(f"line {num}: mutating op '{op}' on '{tool}'")
    return flagged


def _render(passed: bool, before: dict[str, object], after: dict[str, object],
            findings: list[str], tool_flags: list[str]) -> str:
    lines = [
        "# Read-only evidence report",
        "",
        f"- Verdict: {'PASS — model unchanged' if passed else 'FAIL — change detected'}",
        f"- Before digest: `{before.get('digest')}`",
        f"- After digest:  `{after.get('digest')}`",
        f"- Files before/after: {before.get('fileCount')} / {after.get('fileCount')}",
        "",
    ]
    lines.append("## TMDL differences")
    lines.extend([f"- {f}" for f in findings] or ["- none"])
    lines.append("")
    lines.append("## Mutating tool calls")
    lines.extend([f"- {f}" for f in tool_flags] or ["- none scanned/found"])
    lines.append("")
    return "\n".join(lines)


def _cmd_snapshot(args: argparse.Namespace) -> int:
    if not args.tmdl_dir.is_dir():
        print(f"error: not a directory: {args.tmdl_dir}", file=sys.stderr)
        return 2
    snap = snapshot(args.tmdl_dir)
    text = json.dumps(snap, indent=2)
    if args.out:
        args.out.write_text(text + "\n", encoding="utf-8")
    else:
        print(text)
    print(f"# snapshot: {snap['fileCount']} files, digest {str(snap['digest'])[:12]}…",
          file=sys.stderr)
    return 0


def _cmd_compare(args: argparse.Namespace) -> int:
    for p in (args.before, args.after):
        if not p.is_file():
            print(f"error: not a file: {p}", file=sys.stderr)
            return 2
    before = json.loads(args.before.read_text(encoding="utf-8"))
    after = json.loads(args.after.read_text(encoding="utf-8"))
    findings = _diff(before.get("files", {}), after.get("files", {}))
    tool_flags = _scan_tool_log(args.tool_log) if args.tool_log else []
    passed = not findings and not tool_flags
    report = _render(passed, before, after, findings, tool_flags)
    if args.report:
        args.report.write_text(report + "\n", encoding="utf-8")
    print(report)
    return 0 if passed else 3


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Read-only evidence for PBI reverse-engineering.")
    sub = parser.add_subparsers(dest="cmd", required=True)

    snap = sub.add_parser("snapshot", help="Hash a TMDL folder into a snapshot.")
    snap.add_argument("tmdl_dir", type=Path)
    snap.add_argument("-o", "--out", type=Path, default=None)
    snap.set_defaults(func=_cmd_snapshot)

    comp = sub.add_parser("compare", help="Compare two snapshots and emit evidence.")
    comp.add_argument("before", type=Path)
    comp.add_argument("after", type=Path)
    comp.add_argument("--tool-log", type=Path, default=None)
    comp.add_argument("--report", type=Path, default=None)
    comp.set_defaults(func=_cmd_compare)

    args = parser.parse_args(argv)
    result: int = args.func(args)
    return result


if __name__ == "__main__":
    raise SystemExit(main())
