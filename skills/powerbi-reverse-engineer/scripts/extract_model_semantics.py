#!/usr/bin/env python3
"""Extract the semantic layer (measures, relationships, RLS) from a TMDL folder.

Purpose
    Complements extract_query_registry.py. The registry captures the *physical*
    query logic (partitions, source M/SQL, columns); this script captures the
    *semantic* layer an engineer must preserve when consolidating into Fabric:
    DAX measures (and which table they live on), model relationships (the star
    schema to keep), and any row-level-security roles. This data backs the
    Measures, Dimensional-model and Risk sections of the engineer report
    (see references/report-sections.md).

Usage
    python extract_model_semantics.py <tmdl-dir> [--json OUT.json]

    <tmdl-dir>  Path to a TMDL folder (the `.../definition` exported via the MCP
                database_operations export). Searches recursively.

Output
    JSON (stdout by default, or --json PATH):
        {
          "measures":      [{"name", "table", "file", "expression"}],
          "relationships": [{"fromTable","fromColumn","toTable","toColumn"}],
          "roles":         [{"name","file"}],
          "counts": {"measures","relationships","roles","measureTables"}
        }
    Also prints a one-line summary to stderr.

Exit codes
    0 success (even if zero found), 2 on bad input path.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path

_TABLE_HDR_RE = re.compile(r"^[ \t]*table\s+(?P<name>.+?)\s*$")
_MEASURE_RE = re.compile(r"^(?P<indent>[ \t]*)measure\s+(?P<name>.+?)\s*=\s*(?P<inline>.*)$")
_ROLE_RE = re.compile(r"^[ \t]*role\s+(?P<name>.+?)\s*$")
_REL_REF_RE = re.compile(r"^[ \t]*(?P<dir>from|to)Column:\s*(?P<ref>.+?)\s*$")


@dataclass
class Measure:
    name: str
    table: str
    file: str
    expression: str


@dataclass
class Relationship:
    fromTable: str = ""
    fromColumn: str = ""
    toTable: str = ""
    toColumn: str = ""


@dataclass
class Role:
    name: str
    file: str


@dataclass
class Semantics:
    measures: list[Measure] = field(default_factory=list)
    relationships: list[Relationship] = field(default_factory=list)
    roles: list[Role] = field(default_factory=list)


def _indent(line: str) -> int:
    return len(line) - len(line.lstrip(" \t"))


def _unquote(name: str) -> str:
    name = name.strip()
    if len(name) >= 2 and name[0] == name[-1] and name[0] in {"'", '"'}:
        return name[1:-1]
    return name


def _split_ref(ref: str) -> tuple[str, str]:
    """Split a 'Table'.Column or Table.'Column' reference into (table, column)."""
    ref = ref.strip()
    if ref.startswith("'"):
        end = ref.find("'", 1)
        if end != -1:
            table = ref[1:end]
            column = ref[end + 1:].lstrip(".")
            return table, _unquote(column)
    table, _, column = ref.partition(".")
    return _unquote(table), _unquote(column)


def _table_name(lines: list[str], fallback: str) -> str:
    for line in lines:
        hdr = _TABLE_HDR_RE.match(line)
        if hdr:
            return _unquote(hdr.group("name"))
    return fallback


def _parse_measures(lines: list[str], table: str, rel: str) -> list[Measure]:
    measures: list[Measure] = []
    i = 0
    while i < len(lines):
        m = _MEASURE_RE.match(lines[i])
        if not m:
            i += 1
            continue
        inline = m.group("inline").strip()
        # TMDL wraps multi-line DAX in a triple-backtick "boxed" fence that opens
        # inline after '=' and closes on its own line; strip it so it does not
        # leak into the expression text.
        expr_lines = [] if inline == "```" else [inline]
        base_indent = _indent(lines[i])
        i += 1
        # Continuation lines are indented deeper than the measure and are not
        # property assignments (formatString:, lineageTag:, etc.).
        while i < len(lines):
            nxt = lines[i]
            if nxt.strip() == "":
                i += 1
                continue
            if _indent(nxt) <= base_indent:
                break
            if re.match(r"^[ \t]*(formatString|lineageTag|displayFolder|"
                        r"changedProperty|annotation|isHidden|description|"
                        r"formatStringDefinition):", nxt):
                i += 1
                continue
            if nxt.lstrip().startswith(("```", "/// ")):
                i += 1
                continue
            expr_lines.append(nxt.strip())
            i += 1
        expression = " ".join(p for p in expr_lines if p).strip()
        measures.append(Measure(name=_unquote(m.group("name")), table=table,
                                file=rel, expression=expression))
    return measures


def _parse_relationships(lines: list[str]) -> list[Relationship]:
    rels: list[Relationship] = []
    current: Relationship | None = None
    for line in lines:
        if re.match(r"^[ \t]*relationship\b", line):
            current = Relationship()
            rels.append(current)
            continue
        ref_m = _REL_REF_RE.match(line)
        if ref_m and current is not None:
            table, column = _split_ref(ref_m.group("ref"))
            if ref_m.group("dir") == "from":
                current.fromTable, current.fromColumn = table, column
            else:
                current.toTable, current.toColumn = table, column
    return [r for r in rels if r.fromColumn or r.toColumn]


def build_semantics(tmdl_dir: Path) -> Semantics:
    sem = Semantics()
    for path in sorted(tmdl_dir.rglob("*.tmdl")):
        rel = str(path.relative_to(tmdl_dir)).replace("\\", "/")
        lines = path.read_text(encoding="utf-8").splitlines()
        if path.parent.name == "tables" or _TABLE_HDR_RE.search("\n".join(lines[:3])):
            sem.measures.extend(_parse_measures(lines, _table_name(lines, path.stem), rel))
        if path.name == "relationships.tmdl" or any(
            re.match(r"^[ \t]*relationship\b", ln) for ln in lines
        ):
            sem.relationships.extend(_parse_relationships(lines))
        for line in lines:
            role_m = _ROLE_RE.match(line)
            if role_m:
                sem.roles.append(Role(name=_unquote(role_m.group("name")), file=rel))
    return sem


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Extract measures, relationships, RLS from TMDL.")
    parser.add_argument("tmdl_dir", type=Path)
    parser.add_argument("--json", type=Path, default=None)
    args = parser.parse_args(argv)

    if not args.tmdl_dir.is_dir():
        print(f"error: not a directory: {args.tmdl_dir}", file=sys.stderr)
        return 2

    sem = build_semantics(args.tmdl_dir)
    measure_tables = sorted({m.table for m in sem.measures})
    payload = {
        "measures": [asdict(m) for m in sem.measures],
        "relationships": [asdict(r) for r in sem.relationships],
        "roles": [asdict(r) for r in sem.roles],
        "counts": {
            "measures": len(sem.measures),
            "relationships": len(sem.relationships),
            "roles": len(sem.roles),
            "measureTables": len(measure_tables),
        },
    }
    text = json.dumps(payload, indent=2)
    if args.json:
        args.json.write_text(text + "\n", encoding="utf-8")
    else:
        print(text)

    print(
        f"# {len(sem.measures)} measures on {len(measure_tables)} table(s), "
        f"{len(sem.relationships)} relationships, {len(sem.roles)} RLS role(s)",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
