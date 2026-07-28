---
name: metadata-lineage-map
description: |
  Traces table lineage in the SCHIE365 StarBase metadata repository. Builds a
  metadata graph from StarBase records (`id`, `entityId`, `sources[].entityId`,
  jobs, entities, publish metadata, schedules, and state), then produces a
  table-by-table lineage summary and Archflow-style report.

  Use when the user says: "trace this metadata table", "show lineage for
  <table>", "map this semantic table back to bronze", "generate an Archflow
  lineage report", or asks to inspect the StarBase metadata repository.

  Do NOT use for: arbitrary medallion repositories outside SCHIE365 StarBase,
  runtime data validation, Power BI model lineage, or SQL-only dependency
  checks unless the user explicitly passes SQL-only mode.
license: MIT
argument-hint: "<table-name> [--mode graph|hybrid|sql-only] [--metadata-root PATH] [--depth N] [--format html|markdown|json]"
---
# Metadata lineage map

This skill traces lineage for tables in the SCHIE365 StarBase metadata
repository. It is intentionally **repo-only for now**: support the StarBase
metadata shape first, then generalize later only if requested.

## When to use

Use this skill when the user asks to:

- Find lineage for a StarBase semantic, gold, silver, bronze, Kusto, SQL, ADO,
  or ADLS metadata table.
- Reverse-engineer a table from semantic back to upstream sources.
- Validate the metadata repository structure before tracing lineage.
- Produce an Archflow-style lineage report for a metadata table.
- Compare metadata graph lineage against SQL references.

Do not use this skill for:

- Generic medallion repositories that do not use the StarBase metadata shape.
- Live data freshness checks or runtime job execution.
- Power BI / TMDL semantic model relationships.
- SQL-only lineage unless explicitly requested with `--mode sql-only`.

## Configuration

Default flags:

| Flag | Default | Meaning |
|---|---|---|
| `--mode` | `graph` | Build lineage from StarBase metadata records. |
| `--metadata-root` | `StarBaseAIAssistant/.cache/starbase/metadata_repo/main` | Root to scan for metadata records. |
| `--depth` | `all` | Trace until no producer job/source is found. |
| `--format` | `html` | Produce an Archflow-style HTML report plus a concise summary. |
| `--include-sql` | `true` | Include SQL transform snippets as supporting evidence. |
| `--dedupe` | `enabled-first` | Prefer enabled jobs/entities when duplicate IDs exist. |

Supported modes:

| Mode | Behavior |
|---|---|
| `graph` | Use `id`, `entityId`, `sources[].entityId`, jobs, entities, publish metadata, state, and schedules as the canonical lineage. |
| `hybrid` | Use graph lineage as canonical, then cross-check SQL `FROM`/`JOIN` references and flag mismatches. |
| `sql-only` | Trace SQL references only. Warn that job state, schedules, publish metadata, and ingestion sources may be incomplete. |

## StarBase metadata model

Parse each metadata file as one of these logical record types:

| Record type | Signals |
|---|---|
| Entity | Has `id`, `entityType`, `partitionKey`; no `jobType`. |
| Job | Has `id`, `entityId`, `jobType`, `state`, optional `trigger`, optional `sources`. |
| Source entity | Entity IDs with source prefixes like `KUSTO_`, `AZSQL_`, `ADO_`, or `ADLS_`. |
| Published semantic table | Semantic entity with `publish.workspaceSchema` and `publish.tableName`. |
| SQL transform | File content starts with or contains SQL such as `SELECT`, `WITH`, `FROM`, or `JOIN`. |

Known StarBase layers and source prefixes:

- `Semantic`
- `Gold`
- `Silver`
- `Bronze`
- `KUSTO`
- `AZSQL`
- `ADO`
- `ADLS`
- `NRT`

## Workflow

1. **Resolve the metadata root.** Use `--metadata-root` if provided. Otherwise
   use `StarBaseAIAssistant/.cache/starbase/metadata_repo/main`. If the root is
   missing, stop and report the expected path.
2. **Validate repository structure.** Count records by layer, jobs, entities,
   records with sources, semantic entities, published semantic entities,
   duplicate IDs/entities, and missing source references.
3. **Parse records.** Extract `id`, `entityId`, `partitionKey`, `entityType`,
   `jobType`, `state`, `trigger.cronExpression`, `sources[].entityId`,
   `publish.workspaceSchema`, `publish.tableName`, source connection metadata,
   descriptions, and internal notes.
4. **Build indexes.** Create indexes by `id`, by produced `entityId`, by
   producer job, and by SQL reference.
5. **Resolve the target table.** Match in this order:
   1. Exact `id`.
   2. Exact `entityId`.
   3. Published name in `workspaceSchema.tableName` form.
   4. Published `tableName`.
   5. Case-insensitive suffix match, only if unambiguous.
6. **Trace upstream lineage.** Starting at the resolved target entity, find
   producer jobs and recursively follow `sources[].entityId` until a raw source
   or source-without-producer is reached.
7. **Apply dedupe.** When duplicate IDs or producer jobs exist, prefer enabled
   records, then records with explicit sources, then records with publish
   metadata, then the most complete record. Report duplicates that affect the
   chosen path.
8. **Attach SQL evidence.** In `graph` mode, include SQL snippets that support
   each edge. In `hybrid` mode, also flag SQL references missing from metadata
   and metadata sources missing from SQL.
9. **Generate the report.** Emit a concise CLI summary and, when `--format html`
   is active, create an Archflow-style HTML lineage report.

## Output contract

Always include these sections:

```markdown
# Metadata lineage: <resolved table>

## Repository structure

<counts and structure validation>

## Target resolution

<input table, resolved entity, published name, matched files>

## Lineage path

<semantic -> gold -> silver -> bronze/source path>

## Evidence

<job metadata, entity metadata, SQL snippets, source details>

## Quality notes

<duplicates, missing metadata, SQL/graph mismatches, ambiguity>

## Next step

<smallest useful next action>
```

For HTML output, create a single self-contained file with:

- A left-to-right lineage diagram grouped by layer.
- Nodes for entities and jobs.
- Edges labeled with source relationships.
- A details panel for schedules, state, job type, source system, SQL snippets,
  and metadata file paths.
- A summary section that matches the CLI output.

## Lineage node shape

Represent each node with these fields when available:

```json
{
  "id": "Semantic_MBR_RecycledContent",
  "kind": "entity",
  "layer": "Semantic",
  "published_as": "MBR.RecycledContent",
  "state": "Enabled",
  "job_type": "SparkSqlTransformJob",
  "schedule": "0 0 11 * * ?",
  "sources": ["Gold_MBR_RecycledContent"],
  "metadata_path": "StarBaseAIAssistant/.cache/starbase/metadata_repo/main/...",
  "sql_evidence": "SELECT * FROM Gold_MBR_RecycledContent"
}
```

## Dedupe rules

Use this priority when duplicate IDs/entities exist:

1. Enabled over disabled.
2. Records with explicit `sources` over records without sources.
3. Records with `publish` metadata for semantic targets.
4. Records with complete `jobType`, `state`, and `trigger`.
5. If still tied, keep all candidates and report ambiguity instead of guessing.

## Anti-patterns

- Do not assume physical folders represent layers. The current metadata cache is
  content-addressed; layer is encoded in IDs and metadata fields.
- Do not treat SQL-only lineage as complete unless `--mode sql-only` was
  explicitly requested.
- Do not hide duplicate IDs/entities; include quality notes.
- Do not stop at the semantic job. Trace to raw source or a source without a
  producer job.
- Do not claim runtime freshness, row counts, or successful execution from
  metadata alone.

## Example

Input:

```text
/metadata-lineage-map Semantic_MBR_RecycledContent
```

Expected graph:

```text
KUSTO_chiereldataexplorer_RecycledContent
  -> Bronze_Job_KUSTO_chiereldataexplorer_RecycledContent
  -> Silver_Job_KUSTO_chiereldataexplorer_RecycledContent
  -> Silver_KUSTO_chiereldataexplorer_RecycledContent
  -> Gold_Job_MBR_RecycledContent
  -> Gold_MBR_RecycledContent
  -> Semantic_Job_MBR_RecycledContent
  -> Semantic_MBR_RecycledContent
```

## See also

- `archflow` for architecture-style HTML visualization patterns.
- `ultrathink` for deciding whether to broaden this StarBase-only skill into a
  generic medallion lineage skill later.
