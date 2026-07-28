#!/usr/bin/env python3
"""Extract a Power BI query registry from an exported TMDL folder.

Purpose
    Statically parse the TMDL definition of one or more semantic models and emit
    a normalized registry of every table partition: its storage mode, source
    type, the full M/SQL source expression, and its columns. This is the bulk,
    offline half of the powerbi-reverse-engineer skill; the MCP is reserved for
    gaps static parsing cannot resolve (e.g. runtime-folded DirectQuery SQL).

Usage
    python extract_query_registry.py <tmdl-dir> [--csv OUT.csv] [--json OUT.json]

    <tmdl-dir>  Path to a TMDL folder (the `.../definition` or `tables` folder
                exported via the MCP `database_operations` export). The script
                searches recursively for `*.tmdl` files containing tables.

Output
    JSON (stdout by default, or --json PATH): a list of table records, each:
        {
          "model": "<folder name>",
          "table": "<table>",
          "file": "<relative path>",
          "partitions": [
            {"name": ..., "sourceType": "m|query|calculated|entity|...",
             "mode": "import|directQuery|directLake|dual|null",
             "source": "<M/SQL expression, or entityName/schemaName for entity>"}
          ],
          "columns": [{"name": ..., "dataType": ...}]
        }
    CSV (--csv PATH): one row per partition with the same fields flattened.

Exit codes
    0 success (even if zero tables found), 2 on bad input path.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path

_PARTITION_RE = re.compile(r"^(?P<indent>[ \t]*)partition\s+(?P<name>.+?)\s*=\s*(?P<stype>\w+)\s*$")
_COLUMN_RE = re.compile(r"^(?P<indent>[ \t]*)column\s+(?P<name>.+?)\s*$")
_MODE_RE = re.compile(r"^[ \t]*mode:\s*(?P<mode>\w+)\s*$")
_DATATYPE_RE = re.compile(r"^[ \t]*dataType:\s*(?P<dt>\w+)\s*$")
_SOURCE_RE = re.compile(r"^[ \t]*source\s*=\s*(?P<inline>.*)$")
_SOURCE_BLOCK_RE = re.compile(r"^[ \t]*source\s*$")
_TABLE_HDR_RE = re.compile(r"^[ \t]*table\s+(?P<name>.+)$")


@dataclass
class Partition:
    name: str
    sourceType: str
    mode: str | None = None
    source: str = ""


@dataclass
class Column:
    name: str
    dataType: str | None = None


@dataclass
class TableRecord:
    model: str
    table: str
    file: str
    partitions: list[Partition] = field(default_factory=list)
    columns: list[Column] = field(default_factory=list)


def _indent_width(line: str) -> int:
    return len(line) - len(line.lstrip(" \t"))


def _strip_quotes(name: str) -> str:
    name = name.strip()
    if len(name) >= 2 and name[0] == name[-1] and name[0] in {"'", '"'}:
        return name[1:-1]
    return name


def _collect_block(lines: list[str], start: int, header_indent: int) -> tuple[list[str], int]:
    """Return the lines strictly more indented than header_indent, and next index."""
    block: list[str] = []
    i = start
    while i < len(lines):
        line = lines[i]
        if line.strip() == "":
            block.append(line)
            i += 1
            continue
        if _indent_width(line) <= header_indent:
            break
        block.append(line)
        i += 1
    while block and block[-1].strip() == "":
        block.pop()
    return block, i


def _parse_partition(block_lines: list[str], header: re.Match[str]) -> Partition:
    part = Partition(name=_strip_quotes(header.group("name")), sourceType=header.group("stype"))
    i = 0
    while i < len(block_lines):
        line = block_lines[i]
        mode_m = _MODE_RE.match(line)
        if mode_m:
            part.mode = mode_m.group("mode")
            i += 1
            continue
        src_m = _SOURCE_RE.match(line)
        if src_m:
            inline = src_m.group("inline").strip()
            src_indent = _indent_width(line)
            body, i = _collect_block(block_lines, i + 1, src_indent)
            if inline == "```":  # TMDL boxed expression: strip the fences
                inline = ""
                body = [b for b in body if b.strip() != "```"]
            text = inline + ("\n" if inline and body else "")
            text += "\n".join(b.rstrip() for b in body)
            part.source = text.strip()
            continue
        block_m = _SOURCE_BLOCK_RE.match(line)
        if block_m:
            # Block-form `source` with no `=` (e.g. directLake/entity partitions:
            # entityName/schemaName/expressionSource). Capture the indented child
            # lines as the source so the registry is non-empty for these tables.
            src_indent = _indent_width(line)
            body, i = _collect_block(block_lines, i + 1, src_indent)
            part.source = "\n".join(b.strip() for b in body if b.strip())
            continue
        i += 1
    return part


def _parse_table_file(path: Path, model: str, rel: str) -> list[TableRecord]:
    lines = path.read_text(encoding="utf-8").splitlines()
    table_name = path.stem
    for line in lines:
        hdr = _TABLE_HDR_RE.match(line)
        if hdr:
            table_name = _strip_quotes(hdr.group("name"))
            break

    record = TableRecord(model=model, table=table_name, file=rel)
    i = 0
    while i < len(lines):
        line = lines[i]
        p_hdr = _PARTITION_RE.match(line)
        if p_hdr:
            block, i = _collect_block(lines, i + 1, _indent_width(line))
            record.partitions.append(_parse_partition(block, p_hdr))
            continue
        c_hdr = _COLUMN_RE.match(line)
        if c_hdr:
            block, i = _collect_block(lines, i + 1, _indent_width(line))
            dtype = next(
                (m.group("dt") for m in (_DATATYPE_RE.match(b) for b in block) if m), None
            )
            record.columns.append(Column(name=_strip_quotes(c_hdr.group("name")), dataType=dtype))
            continue
        i += 1

    return [record] if (record.partitions or record.columns) else []


def build_registry(tmdl_dir: Path) -> list[TableRecord]:
    model = tmdl_dir.name
    records: list[TableRecord] = []
    for path in sorted(tmdl_dir.rglob("*.tmdl")):
        rel = str(path.relative_to(tmdl_dir))
        records.extend(_parse_table_file(path, model=model, rel=rel))
    return records


def _write_csv(records: list[TableRecord], out: Path) -> None:
    with out.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(
            ["model", "table", "file", "partition", "sourceType", "mode", "columnCount", "source"]
        )
        for rec in records:
            parts = rec.partitions or [Partition(name="", sourceType="")]
            for part in parts:
                writer.writerow(
                    [
                        rec.model,
                        rec.table,
                        rec.file,
                        part.name,
                        part.sourceType,
                        part.mode or "",
                        len(rec.columns),
                        part.source,
                    ]
                )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Extract a query registry from a TMDL folder.")
    parser.add_argument("tmdl_dir", type=Path, help="Path to the exported TMDL folder.")
    parser.add_argument("--csv", type=Path, default=None, help="Write a flattened CSV here.")
    parser.add_argument("--json", type=Path, default=None, help="Write JSON here (else stdout).")
    args = parser.parse_args(argv)

    if not args.tmdl_dir.is_dir():
        print(f"error: not a directory: {args.tmdl_dir}", file=sys.stderr)
        return 2

    records = build_registry(args.tmdl_dir)
    payload = [asdict(rec) for rec in records]

    if args.json:
        args.json.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    if args.csv:
        _write_csv(records, args.csv)
    if not args.json:
        print(json.dumps(payload, indent=2))

    dq = sum(
        1 for rec in records for part in rec.partitions if (part.mode or "").lower() == "directquery"
    )
    print(
        f"# {len(records)} tables, {dq} DirectQuery partition(s) parsed from {args.tmdl_dir}",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
