---
name: powerbi-reverse-engineer
description: |
  Reverse-engineers existing Power BI semantic models (Import and DirectQuery)
  via the Microsoft powerbi-modeling-mcp server to harvest the query logic behind
  each table — Power Query (M), DirectQuery SQL, parameters, columns, measures —
  then catalogs them into a query registry and designs a consolidated "one big
  table" in Microsoft Fabric (Lakehouse or Warehouse) with idempotent build
  artifacts and a validation plan.

  Use when the user says: "reverse engineer my Power BI dashboards", "extract the
  queries / M / SQL from these models", "consolidate these models into one big
  table in Fabric", or "turn Import + DirectQuery models into a single Fabric
  table".

  Do NOT use for: authoring new measures or model changes (use the MCP directly),
  tracing StarBase lineage (use metadata-lineage-map), validating Fabric
  governance (use fabric-governance-validate), writing DAX/TMDL from a spec (use
  the powerbi-tmdl-specialist agent), or any task not starting from existing
  Power BI models.
license: MIT
allowed-tools: [shell]
argument-hint: "<model-or-pbip-or-workspace> [--target lakehouse|warehouse] [--tmdl-dir PATH] [--format markdown|json]"
---

# Power BI reverse-engineer → Fabric one-big-table

This skill answers one question: **what source queries sit behind a set of
existing Power BI models, and how do they consolidate into a single governed
table in Microsoft Fabric?**

It is **read-only against your Power BI models**. It harvests logic; it does not
modify the source models. The only things it creates are *new* artifacts: a query
registry, a consolidation design, and Fabric build scripts.

> ⚠️ **Read-only is enforced by this skill, not by the server.** The
> `powerbi-modeling-mcp` *can* write to models — the same `*_operations` tools
> that read also create/update/delete — and it has **no `--readonly` flag**. This
> skill keeps the model untouched through three controls, in order of strength:
>
> 1. **Extract offline.** Prefer harvesting from an exported TMDL copy
>    (`scripts/extract_query_registry.py`). The live published model is never
>    write-connected, so it physically cannot change.
> 2. **Never bypass the gate.** Do **not** pass `--skipconfirmation`. The MCP
>    elicits human approval before the first write — always decline writes.
> 3. **Prove it.** Snapshot the model's TMDL before and after any live session
>    and assert the digest is unchanged (`scripts/readonly_evidence.py`). Because
>    the MCP can only perform *modeling* operations, an identical TMDL digest is
>    evidence that nothing was modified.

## What the MCP can and cannot give you

| Source | Provides | Cannot provide |
|---|---|---|
| **powerbi-modeling-mcp** | The *logic*: M source expressions, DirectQuery SQL, parameters, table/column/measure metadata, TMDL export | The *data* itself, or a built Fabric table |
| **This skill + engineer** | A structured registry, a one-big-table design, idempotent Fabric build + validation artifacts | Production deployment approval (always a human gate) |

The MCP is the *extraction* engine. Building the consolidated table is a data
engineering step that consumes the harvested SQL/M. Keep that boundary explicit
when talking to the user.

## When to use / NOT to use

Use when the user has **existing** Power BI models and wants their query logic
extracted and/or consolidated into Fabric.

Do not use to:

- Author new measures, columns, or relationships (use the MCP directly, or the
  `powerbi-tmdl-specialist` agent).
- Trace StarBase metadata lineage (use `metadata-lineage-map`).
- Audit Fabric governance (use `fabric-governance-validate`).
- Deploy to production without an explicit human approval gate.

## Configuration

| Flag | Default | Meaning |
|---|---|---|
| `--target` | `lakehouse` | Consolidation target: `lakehouse` (Spark/Delta) or `warehouse` (T-SQL). |
| `--tmdl-dir` | _(none)_ | Path to an already-exported TMDL folder. When set, Phase 1–2 extraction runs offline from TMDL and the MCP is only needed for DirectQuery SQL/DAX validation. |
| `--format` | `markdown` | Output format for the registry and design report. |

## Prerequisites

1. **Install the MCP.** Easiest is the VS Code extension; or register via NPX:
   ```jsonc
   {
     "powerbi-modeling-mcp": {
       "type": "stdio",
       "command": "npx",
       "args": ["-y", "@microsoft/powerbi-modeling-mcp@latest", "--start"]
     }
   }
   ```
2. **Use a deep-reasoning model** (GPT-5 / Claude Sonnet 4.5+) for accurate M/SQL
   interpretation, per the MCP's own guidance.
3. **Back up every model before connecting** — an LLM + modeling tools can mutate
   a model. This skill is read-only, but enforce the backup gate anyway.
4. Connect to each model:
   - Desktop: `Connect to '[File]' in Power BI Desktop`
   - Fabric: `Connect to semantic model '[Model]' in Fabric Workspace '[WS]'`
   - PBIP: `Open semantic model from PBIP folder '[path to definition/TMDL]'`

## Workflow

Run the phases in order. Persist a plan to
`StarBaseAIAssistant/.copilot/plans/` if the job spans more than one model.

### Phase 0 — Scope and connect

Confirm the model list, the consolidation intent (union of like tables? join of
fact + dimensions? a single denormalized fact?), and the Fabric target. Connect
to the first model via the MCP. Establish the backup gate.

### Phase 0.5 — Read-only enforcement and evidence (required for live sessions)

Skip this only when extracting purely offline from a TMDL copy (no live MCP
connection). Otherwise, before any live MCP work:

1. Export the model's TMDL (read-only `database_operations` export) and snapshot
   it: `python scripts/readonly_evidence.py snapshot <tmdl-dir> -o before.json`.
2. Confirm the MCP was **not** started with `--skipconfirmation`; decline every
   modification/elicitation prompt.
3. After the session, re-export the TMDL and snapshot again
   (`-o after.json`), then
   `python scripts/readonly_evidence.py compare before.json after.json --report evidence.md`.
4. A non-zero exit (code 3) means the model changed — **stop and investigate**;
   restore the backup. Attach `evidence.md` to the run output.

Optionally narrow blast radius by denying write-heavy tool groups you never need
for extraction (e.g. `security_role_operations`, `calculation_group_operations`,
`perspective_operations`) in your MCP client's permission config.

### Phase 1 — Inventory

For each connected model, enumerate tables and partitions:

- `database_operations` → list databases / export TMDL folder (the durable
  artifact — prefer this for many models).
- `table_operations` (list) and `partition_operations` (list) → table set +
  storage mode per partition (Import vs DirectQuery vs Dual).

When `--tmdl-dir` is supplied, skip the live calls and read the TMDL folder.

### Phase 1.5 — Map current data access

The registry captures *what* each table queries; this phase captures *how the
dashboard reaches its data* and seeds the ingestion plan. Run
`scripts/generate_access_ingestion_guide.py <registry.json>` to derive a
**data-access map** (connector, server/database parameters, source object,
native-SQL flag, storage mode per table) and emit a Markdown guide **to the CLI**
(not the archflow report).

The model alone cannot reveal the **gateway, datasource credentials, refresh
schedule, or data volumes** — the `powerbi-modeling-mcp` only sees the model.
Collect those with the Power BI REST API (`/datasources`, `/refreshes`,
`/refreshSchedule`) and the Fabric Scanner API, plus `COUNT(*)` / `MIN`-`MAX`
watermark probes on each source object. Read
`references/data-access-and-ingestion.md` for the field list and exact calls.

### Phase 2 — Harvest query logic

Per table, extract the *source query* and shape:

| Storage mode | What to extract | MCP tool |
|---|---|---|
| Import | M `source =` expression in the partition (the full `let … in`) | `partition_operations` (get) |
| DirectQuery | native SQL / source query + storage mode | `partition_operations` (get) + `dax_query_operations` to validate |
| Any | data-source params & shared M | `named_expression_operations` (list/get) |
| Any | columns + data types, measures (DAX) for grain/context | `column_operations`, `measure_operations` |

Mechanize the bulk parse: run
`scripts/extract_query_registry.py <tmdl-dir>` against the exported TMDL folder
to produce a normalized JSON/CSV registry of every partition's mode, source
type, source expression, and columns. Then run
`scripts/extract_model_semantics.py <tmdl-dir> --json semantics.json` to harvest
the **semantic layer** — every DAX measure (with its home table), every model
relationship (the star schema), and any RLS roles. Measures and relationships do
not migrate into the OBT; they must be *preserved*, so the engineer needs them
catalogued. Use the MCP only to fill gaps the static parse cannot resolve (e.g.
DirectQuery SQL folded at runtime).

Read `references/mcp-extraction-playbook.md` for the exact prompts and
tool-call sequences for each extraction case.

### Phase 3 — Build the query registry

Consolidate the harvest into one registry keyed by `model.table`. Each row
records: storage mode, source system, source schema/object, the M or SQL, column
list + types, declared/observed grain, and any parameters it depends on. This is
the inventory the consolidation design is built from.

### Phase 4 — Design the one-big-table

Read `references/consolidation-design.md` and produce a source-to-target design:

- Decide the **grain** of the consolidated table and reconcile mismatched grains.
- Map each source column to a **conformed** target column (name, type, nullability).
- Define the consolidation operation: `UNION ALL` of like tables, a `JOIN`
  denormalization, or a staged fact+conform. Resolve dedup / SCD / lineage
  columns (`source_model`, `source_table`, `loaded_at`).
- Flag DirectQuery sources that must become scheduled ingestion (you cannot keep
  live DQ inside a single materialized Fabric table).

### Phase 5 — Generate Fabric build artifacts

Build in medallion order: **land raw to bronze first, then consolidate to gold.**
Do not ingest straight into the OBT.

#### Phase 5a — Land sources into the Lakehouse (bronze)

Using the access map and ingestion guide from Phase 1.5, land each source object
as a raw bronze Delta table. Choose the method per source from the decision
matrix in `references/data-access-and-ingestion.md`:

- **Data pipeline Copy activity** — relational source behind a gateway with
  hand-written native SQL (push the harvested SQL as the source query).
- **Spark JDBC notebook** — full control / large volumes.
- **OneLake shortcut / Mirroring** — when the source is already in OneLake or is
  a natively mirrored database.

Create the Fabric connection with a gateway + Key Vault credential — never inline
secrets. Decide a watermark per table to replace full reloads, and schedule the
pipeline to the **harvested refresh cadence** (Phase 1.5), not an invented one.

#### Phase 5b — Consolidate bronze/silver into the gold OBT

Emit idempotent build artifacts for `--target`:

- **Lakehouse**: a PySpark/Delta notebook that reads the landed (bronze/silver)
  sources, conforms, unions/joins, and `MERGE`/overwrites a single Delta table.
- **Warehouse**: idempotent T-SQL (`CREATE TABLE IF NOT EXISTS` + `MERGE` or
  `CREATE OR ALTER VIEW` + `INSERT`) that consolidates the harvested SQL.

Every artifact must be re-runnable without duplicating rows. Never embed
credentials or PATs — use workspace identity / parameters.

### Phase 6 — Validate

- Row-count and column-checksum parity between each source and its slice of the
  consolidated table.
- Re-run representative DAX queries (`dax_query_operations`) against the original
  model and compare aggregates to the Fabric table.
- Record residual gaps (RLS, dynamic params, runtime folding) the static
  consolidation cannot reproduce.

Gate production load behind explicit human approval.

### Phase 7 — Generate the engineer report (archflow)

Produce a single self-contained HTML report so engineers can act on the harvest
without re-reading raw TMDL. Render it with the **archflow** skill in REPORT
mode, and include every section in `references/report-sections.md`, each backed
by **real harvested data** (registry + `semantics.json` + evidence) — never
invented numbers.

The report must cover: header KPIs, executive summary, the animated
connect→harvest→registry→consolidate→OBT→serve diagram, the query registry, the
consolidation design, the **semantic layer (measures)**, the **dimensional model
(relationships)**, the read-only evidence, a dependency-ordered **migration
runbook**, **validation queries**, a graded **risk register**, and a build-
artifacts manifest. Run archflow's independent review (its Stage 5) and fix any
CRITICAL/ERROR before presenting. Write it alongside the build artifacts.

## Output contract

Emit, in `--format`:

1. **Query registry** — table of `model.table`, storage mode, source system,
   source object, grain, column count, parameter dependencies.
2. **Consolidation design** — target grain, source-to-target column map,
   consolidation operation per source, lineage columns.
3. **Fabric build artifacts** — the notebook or T-SQL, plus a one-line run
   command.
4. **Validation plan** — the parity checks and the residual-gap list.
5. **Open questions / risks** — grain conflicts, DQ-to-batch conversions,
   unresolved M, anything needing a human decision.
6. **Engineer report (HTML)** — an archflow REPORT-mode document with the
   sections from `references/report-sections.md` (measures, relationships,
   migration runbook, validation queries, risk register).
7. **Data-access & ingestion guide (Markdown, CLI)** — printed to the terminal
   from `generate_access_ingestion_guide.py`: access map, REST/Scanner API calls,
   ingestion decision, bronze-landing code, watermark pattern, orchestration.

## Anti-patterns

- **Don't** mutate the source models. Extraction is read-only — and prove it
  with `scripts/readonly_evidence.py` for any live session.
- **Don't** start the MCP with `--skipconfirmation`; that removes the write gate.
- **Don't** treat DirectQuery as if it can stay live inside one materialized
  table — call out the batch-ingestion conversion explicitly.
- **Don't** silently flatten different grains into one table; reconcile or split.
- **Don't** hardcode connection strings, keys, or PATs in build artifacts.
- **Don't** paste full model data into chat logs (the MCP can surface sensitive
  data — keep sessions clean).
- **Don't** skip the backup gate before connecting the MCP.
- **Don't** hand-parse hundreds of TMDL files — use the script, reserve the MCP
  for what static parsing cannot resolve.

## See also

- `references/mcp-extraction-playbook.md` — per-case MCP prompts & tool calls.
- `references/consolidation-design.md` — grain, conformance, SCD, lineage rules.
- `references/data-access-and-ingestion.md` — access map + bronze ingestion plan.
- `references/report-sections.md` — mandatory sections for the archflow report.
- `scripts/extract_query_registry.py` — TMDL → query registry (JSON/CSV).
- `scripts/extract_model_semantics.py` — TMDL → measures, relationships, RLS (JSON).
- `scripts/generate_access_ingestion_guide.py` — registry → Markdown access/ingestion guide (CLI).
- `scripts/readonly_evidence.py` — before/after TMDL hash proof of no model change.
- `fabric-governance-validate` skill — audit the target workspace afterwards.
- `powerbi-tmdl-specialist` agent — for authoring DAX/TMDL changes.
- powerbi-modeling-mcp: https://github.com/microsoft/powerbi-modeling-mcp
