#!/usr/bin/env python3
"""Mechanical duplication finder. Used by the `simplify` skill.

Identifies blocks of N+ consecutive lines that appear identically (modulo
whitespace) in 2+ places in a set of files. Output is a starting point — a
human still decides whether each duplication is genuine or coincidental.

Usage:
    python find_duplicates.py [--min-lines N] [--ignore-whitespace] FILE [FILE ...]

Output format (JSON, one duplication per object):
    {
      "block": "<the duplicated content>",
      "lines": <number of lines in the block>,
      "occurrences": [
        {"file": "path/to/a.py", "start_line": 12, "end_line": 18},
        {"file": "path/to/b.py", "start_line": 45, "end_line": 51}
      ]
    }
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Iterable


def _normalize(line: str, ignore_whitespace: bool) -> str:
    if ignore_whitespace:
        return " ".join(line.split())
    return line.rstrip()


def _windows(lines: list[str], n: int) -> Iterable[tuple[int, list[str]]]:
    for i in range(len(lines) - n + 1):
        yield i, lines[i : i + n]


def find_duplicates(
    files: list[Path],
    *,
    min_lines: int = 6,
    ignore_whitespace: bool = True,
) -> list[dict]:
    occurrences: dict[str, list[tuple[Path, int]]] = defaultdict(list)
    contents: dict[Path, list[str]] = {}

    for path in files:
        try:
            raw = path.read_text(encoding="utf-8").splitlines()
        except (UnicodeDecodeError, OSError):
            continue
        contents[path] = raw
        normalized = [_normalize(l, ignore_whitespace) for l in raw]

        for start_idx, window in _windows(normalized, min_lines):
            if all(not l.strip() for l in window):
                continue                            # all-blank windows skip
            digest = hashlib.sha1("\n".join(window).encode()).hexdigest()
            occurrences[digest].append((path, start_idx))

    # Filter to digests that occur in 2+ distinct (file, start) positions
    results = []
    for digest, hits in occurrences.items():
        if len(hits) < 2:
            continue

        # Reconstruct the block content from the first hit
        first_path, first_start = hits[0]
        block_lines = contents[first_path][first_start : first_start + min_lines]
        block_text = "\n".join(block_lines)

        results.append({
            "block": block_text,
            "lines": min_lines,
            "occurrences": [
                {
                    "file": str(p),
                    "start_line": s + 1,                   # 1-indexed for humans
                    "end_line": s + min_lines,
                }
                for p, s in hits
            ],
        })

    # Sort by (number of occurrences DESC, line count DESC)
    results.sort(key=lambda r: (-len(r["occurrences"]), -r["lines"]))
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("files", nargs="+", type=Path, help="Files to scan")
    parser.add_argument(
        "--min-lines",
        type=int,
        default=6,
        help="Minimum block size (consecutive lines) to consider duplication",
    )
    parser.add_argument(
        "--ignore-whitespace",
        action="store_true",
        default=True,
        help="Normalize internal whitespace before comparison",
    )
    args = parser.parse_args()

    duplicates = find_duplicates(
        args.files,
        min_lines=args.min_lines,
        ignore_whitespace=args.ignore_whitespace,
    )

    if not duplicates:
        print(json.dumps({"duplicates": []}, indent=2))
        return 0

    print(json.dumps({"duplicates": duplicates}, indent=2))
    return 0 if not duplicates else 1                # nonzero exit when found


if __name__ == "__main__":
    sys.exit(main())
