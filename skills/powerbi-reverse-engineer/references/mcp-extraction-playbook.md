# MCP extraction playbook

Per-case prompts and tool-call sequences for harvesting query logic with the
`powerbi-modeling-mcp`. Load this when running Phase 1–2 of the skill.

All steps assume you have already connected to a model (see SKILL.md
Prerequisites) and taken a backup. Extraction is **read-only**.

## 0. Bulk export first (preferred for many models)

For more than a handful of tables, export the whole model to TMDL and parse it
statically — far cheaper than per-object MCP calls.

Prompt:

```
Export the connected semantic model to a TMDL folder at <path>.
```

Tool: `database_operations` (export TMDL). Then run
`scripts/extract_query_registry.py <path>` to get the registry, and use the MCP
only for the gaps below.

## 1. Import tables — Power Query (M) source

Each Import partition holds a `let … in` M expression. That expression *is* the
source query (folded SQL is generated from it at refresh time).

Prompt:

```
List the partitions for table '<Table>' and return the full M source
expression for each, including the data source and any applied steps.
```

Tools: `partition_operations` (list, then get). Capture:

- the complete `source = let … in …` block,
- the `mode` (import),
- any referenced shared expressions / parameters (resolve via step 3).

If the source folds to SQL and you need the literal SQL, run a representative
DAX/native query (step 4) or inspect the M `Value.NativeQuery` / `Sql.Database`
step.

## 2. DirectQuery tables — native SQL

DirectQuery partitions reference a live source. The storage mode is
`directQuery` (or `dual`).

Prompt:

```
For every table whose storage mode is DirectQuery or Dual, return the
partition source expression and the underlying SQL object (database, schema,
table or native query) it points to.
```

Tools: `partition_operations` (get), `table_operations` (get storage mode).

Note for the design phase: a DirectQuery source **cannot** remain live inside a
single materialized Fabric table. Record it as a batch-ingestion conversion.

## 3. Parameters and shared expressions

Data-source locations are usually parameterized (server, database, environment).

Prompt:

```
List all named expressions and Power Query parameters in the model and return
their current values and where they are referenced.
```

Tool: `named_expression_operations` (list, get). Record each parameter so the
Fabric build can re-parameterize instead of hardcoding.

## 4. Validate / resolve folded SQL

When the literal SQL behind a fold is unclear:

Prompt:

```
Execute this DAX query against the model and return the results so I can
confirm the grain and aggregates: <DAX>
```

Tool: `dax_query_operations` (execute, validate). Use the result to confirm grain
and to build Phase 6 parity checks. The first query triggers an elicitation
approval — expected.

## 5. Columns, types, measures (context)

Prompt:

```
List the columns and data types for table '<Table>', and list all measures
with their DAX so I can understand the grain and derived logic.
```

Tools: `column_operations` (list), `measure_operations` (list). Measures are not
ingested into the big table, but their DAX reveals grain, keys, and business
logic that informs conformance.

## Sensitivity

The MCP can surface data and metadata. Do not paste full result sets or
credentials into shared chat logs. Keep only the structural query logic needed
for the registry.
