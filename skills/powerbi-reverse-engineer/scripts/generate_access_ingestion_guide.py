#!/usr/bin/env python3
"""Emit a Markdown data-access & Lakehouse-ingestion guide to the CLI.

Purpose
    The query registry (extract_query_registry.py) tells you *what* each table
    queries; this tool answers *how the dashboard reaches its data* and *how to
    land that data in a Fabric Lakehouse*. It reads the registry, derives a
    data-access map (connector, server/db parameters, source object, native-SQL
    flag, storage mode) and prints a ready-to-act Markdown guide — access map,
    the REST/Scanner API calls the model cannot provide, an ingestion decision,
    bronze-landing code per source, an incremental watermark pattern, the
    medallion layout, orchestration, and an engineer checklist.

    Unlike the architecture report, this output is **Markdown for the terminal**,
    not an archflow HTML page. See references/data-access-and-ingestion.md.

Usage
    python generate_access_ingestion_guide.py <registry.json> [--out GUIDE.md]

Exit codes
    0 success, 2 on bad input path.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

_CONNECTORS = (
    "MySQL.Database", "Sql.Database", "PostgreSQL.Database", "Oracle.Database",
    "Odbc.DataSource", "Odbc.Query", "Value.NativeQuery", "Table.NestedJoin",
    "Table.FromRows", "DateTime.LocalNow", "CALENDAR",
)
_SQLDB_RE = re.compile(r"Sql\.Database\(\s*([^,\)]+?)\s*(?:,\s*([^,\)\[]+?)\s*)?[,\)]")
_FROM_RE = re.compile(r"\bFROM\s+([\[\]\w.\"`]+)", re.IGNORECASE)


@dataclass
class Access:
    table: str
    mode: str
    connector: str
    server: str
    database: str
    source_object: str
    native_sql: bool


def _decode_m(text: str) -> str:
    return text.replace("#(lf)", "\n").replace("#(tab)", "\t").replace("#(cr)", "")


def _connector(src: str) -> str:
    for name in _CONNECTORS:
        if name in src:
            return name
    return "—"


def _clean_object(raw: str) -> str:
    """Normalize a SQL object reference: drop brackets/quotes/backticks."""
    return re.sub(r'[\[\]"`]', "", raw).strip().strip(".")


def _source_object(src: str) -> str:
    decoded = _decode_m(src)
    nav = re.search(r'Item\s*=\s*"([^"]+)"', decoded) or re.search(r'Name\s*=\s*"([^"]+)"', decoded)
    if nav:
        return _clean_object(nav.group(1))
    frm = _FROM_RE.search(decoded)
    if frm:
        return _clean_object(frm.group(1))
    return ""


def _classify(records: list[dict[str, object]]) -> list[Access]:
    out: list[Access] = []
    for rec in records:
        table = str(rec.get("table", ""))
        parts = rec.get("partitions") or []
        if not isinstance(parts, list) or not parts:
            out.append(Access(table, "—", "—", "", "", "", False))
            continue
        part = parts[0]
        src = str(part.get("source", "")) if isinstance(part, dict) else ""
        mode = str(part.get("mode", "—")) if isinstance(part, dict) else "—"
        connector = _connector(src)
        db = _SQLDB_RE.search(src)
        server = db.group(1).strip() if db and db.group(1) else ""
        database = db.group(2).strip() if db and db.group(2) else ""
        native = "[Query=" in src or "Value.NativeQuery" in src
        out.append(Access(table, mode, connector, server, database,
                          _source_object(src), native))
    return out


def _md_table(rows: list[Access]) -> str:
    head = ("| Table | Mode | Connector | Server (param) | Database (param) "
            "| Source object | Native SQL |\n"
            "|---|---|---|---|---|---|:--:|\n")
    body = "\n".join(
        f"| {a.table} | {a.mode} | `{a.connector}` | {a.server or '—'} "
        f"| {a.database or '—'} | {a.source_object or '—'} | "
        f"{'✅' if a.native_sql else '—'} |"
        for a in rows
    )
    return head + body


def _source_systems(rows: list[Access]) -> list[tuple[str, str]]:
    seen: dict[str, str] = {}
    for a in rows:
        if a.server:
            seen.setdefault(a.server, a.database)
    return sorted(seen.items())


def build_guide(records: list[dict[str, object]]) -> str:
    rows = _classify(records)
    sql_rows = [a for a in rows if a.connector in {"Sql.Database", "MySQL.Database"}]
    systems = _source_systems(rows)
    dq = [a for a in rows if a.mode == "directQuery"]
    n_native = sum(1 for a in sql_rows if a.native_sql)

    md: list[str] = []
    md.append("# Data access & Lakehouse ingestion guide\n")
    md.append(
        f"Derived from the query registry: **{len(rows)} tables**, "
        f"**{len(sql_rows)} relational-source** tables across "
        f"**{len(systems)} source system(s)**, **{n_native}** using hand-written "
        f"native SQL, **{len(dq)}** DirectQuery.\n"
    )
    md.append("> This guide is the bronze **ingestion** plan that feeds the gold "
              "OBT build. Read it in the terminal and run the code shown.\n")

    md.append("## 1. Current data-access map\n")
    md.append(_md_table(rows) + "\n")

    md.append("## 2. Distinct source systems\n")
    if systems:
        md.append("Create one Fabric connection per system (gateway + Key Vault "
                  "credential — never inline secrets):\n")
        for server, database in systems:
            md.append(f"- **{server}** → database `{database or '?'}` "
                      f"— confirm engine (param name suggests MariaDB/MySQL; "
                      f"`Sql.Database` uses the SQL-Server protocol, so verify).")
        md.append("")
    else:
        md.append("_No relational source parameters detected._\n")

    md.append("## 3. Collect what the model cannot tell you (Power BI REST API)\n")
    md.append("Gateway, credentials, refresh cadence and volume are not in the "
              "modeling MCP. Fetch them, then complete the map above:\n")
    md.append(
        "```bash\n"
        "# gateway id + connection details per datasource\n"
        "GET https://api.powerbi.com/v1.0/myorg/datasets/{datasetId}/datasources\n\n"
        "# actual refresh cadence, durations, volume signal\n"
        "GET https://api.powerbi.com/v1.0/myorg/datasets/{datasetId}/refreshes?$top=20\n\n"
        "# configured schedule\n"
        "GET https://api.powerbi.com/v1.0/myorg/datasets/{datasetId}/refreshSchedule\n"
        "```\n"
    )
    md.append("Also run `SELECT COUNT(*)` and `MIN/MAX(<watermark>)` on each "
              "source object to size full-vs-incremental ingestion.\n")

    md.append("## 4. Ingestion method\n")
    md.append("| Method | Use when |\n|---|---|\n"
              "| OneLake shortcut | source already in OneLake / mirrored |\n"
              "| Database Mirroring | natively supported source (verify MySQL/MariaDB) |\n"
              "| **Data pipeline Copy** | relational source behind a gateway, push native SQL |\n"
              "| Dataflow Gen2 | low-code transforms / reuse existing M |\n"
              "| Notebook (Spark JDBC) | full control / large volumes |\n")
    if n_native:
        md.append(f"\n**Recommendation:** {n_native} tables push hand-written SQL "
                  "to the source. Land each query as a **bronze Delta table** via "
                  "a **Data pipeline Copy activity** (source = the harvested SQL) "
                  "or a **Spark JDBC notebook**.\n")

    md.append("## 5. Bronze landing — one table per source query\n")
    examples = [a for a in sql_rows if a.source_object][:2] or sql_rows[:1]
    md.append("```python\n"
              "from pyspark.sql.functions import current_timestamp\n\n"
              'host = mssparkutils.credentials.getSecret("kv-name", "mariadb-host")\n'
              'user = mssparkutils.credentials.getSecret("kv-name", "mariadb-user")\n'
              'pwd  = mssparkutils.credentials.getSecret("kv-name", "mariadb-pass")\n'
              'jdbc = f"jdbc:mysql://{host}:3306/<database>"\n')
    for a in examples:
        obj = a.source_object or a.table
        leaf = obj.split(".")[-1]
        bronze = "bronze_" + re.sub(r"\W+", "_", leaf.lower()).strip("_")
        md.append(
            f"\n# {a.table}  ←  {obj}\n"
            f"df = (spark.read.format('jdbc')\n"
            f"        .option('url', jdbc).option('driver', 'org.mariadb.jdbc.Driver')\n"
            f"        .option('query', \"<harvested SQL for {a.table}>\")\n"
            f"        .option('user', user).option('password', pwd).load())\n"
            f"(df.withColumn('_loaded_at', current_timestamp())\n"
            f"   .write.mode('overwrite').format('delta').saveAsTable('{bronze}'))"
        )
    md.append("```\n")

    md.append("## 6. Incremental watermark (replace full reloads)\n")
    md.append("```python\n"
              "from delta.tables import DeltaTable\n"
              'hwm = (spark.read.table("bronze_<object>")\n'
              '         .agg({"<watermark_col>": "max"}).collect()[0][0]) or "1900-01-01"\n'
              'sql = f"SELECT * FROM <source> WHERE <watermark_col> > \'{hwm}\'"\n'
              "new = spark.read.format('jdbc').option('query', sql)  # ...load()\n"
              '(DeltaTable.forName(spark, "bronze_<object>").alias("t")\n'
              '   .merge(new.alias("s"), "t.<key> = s.<key>")\n'
              "   .whenMatchedUpdateAll().whenNotMatchedInsertAll().execute())\n"
              "```\n")

    md.append("## 7. Medallion layout\n")
    md.append("```\n"
              "source (native SQL)\n"
              "   │ ingest (Copy / JDBC)\n"
              "   ▼\n"
              "bronze_<object>   raw 1:1 + _loaded_at\n"
              "   │ conform types & keys\n"
              "   ▼\n"
              "silver_<entity>   deduped, typed, conformed dims\n"
              "   │ build_obt_* (existing gold script)\n"
              "   ▼\n"
              "obt_<fact>        one big table + rollup views\n"
              "```\n")

    md.append("## 8. Orchestration\n")
    md.append("Drive bronze → silver → gold from a Fabric Data pipeline. Set the "
              "trigger cadence to the **refresh schedule from §3** — do not invent "
              "a frequency. Order: land all bronze → build silver → run "
              "`build_obt_*` → refresh the semantic model.\n")

    md.append("## 9. Engineer checklist\n")
    for item in (
        "Access map completed with gateway, auth, refresh, volume (from §3)",
        "Ingestion method chosen per source; Fabric connection created",
        "Secrets in Key Vault / workspace identity — none inline",
        "Bronze tables landing the raw source queries (§5)",
        "Incremental watermark decided per table (§6)",
        "Pipeline scheduled to match source refresh cadence (§8)",
        "gold OBT built from silver and validated (existing scripts)",
    ):
        md.append(f"- [ ] {item}")
    md.append("")
    return "\n".join(md)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Emit a Markdown data-access & ingestion guide.")
    parser.add_argument("registry", type=Path, help="registry.json from extract_query_registry.py")
    parser.add_argument("--out", type=Path, default=None, help="write to file instead of stdout")
    args = parser.parse_args(argv)

    if not args.registry.is_file():
        print(f"error: not a file: {args.registry}", file=sys.stderr)
        return 2

    records = json.loads(args.registry.read_text(encoding="utf-8"))
    if not isinstance(records, list):
        print("error: registry must be a JSON array of table records", file=sys.stderr)
        return 2

    guide = build_guide(records)
    if args.out:
        args.out.write_text(guide, encoding="utf-8")
        print(f"# wrote {args.out}", file=sys.stderr)
    else:
        print(guide)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
