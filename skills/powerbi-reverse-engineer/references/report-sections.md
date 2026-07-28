# Engineer report — mandatory sections

When the user asks for a report/visualization of the reverse-engineering
outcome, render it with the **archflow** skill (REPORT mode) and ensure it
contains the sections below. These exist because a query registry alone does not
tell an engineer how to safely rebuild the model in Fabric — the semantic layer,
the star schema, the ordered build, and the risks all matter.

Load this file during the report step. Every section must be backed by **real
harvested data** (from `extract_query_registry.py` and
`extract_model_semantics.py`), never invented.

## Required sections

| # | Section | Source data | Why engineers need it |
|---|---|---|---|
| 1 | **Header + KPIs** | registry + semantics counts | Tables, measures, relationships, DirectQuery count, params, consolidation ratio at a glance. |
| 2 | **Executive summary** | registry analysis | The decisive finding (e.g. N tables are one fact at different grains). |
| 3 | **Animated architecture diagram** | flow phases | The hero — connect → harvest → registry → consolidate → OBT → serve. |
| 4 | **Query registry** | `registry.json/csv` | Every table: storage mode, source object, role. |
| 5 | **Consolidation design** | `consolidation-design.md` | Target grain, source-to-target column map, preserved filters. |
| 6 | **Semantic layer (measures)** | `extract_model_semantics.py` | Measures do NOT migrate — they stay DAX. Show count, home tables, sample DAX, and which fact they reference (proves the OBT grain). |
| 7 | **Dimensional model (relationships)** | `extract_model_semantics.py` | The star to preserve: which dims each fact joins, on which keys. Flag any dimension built via Power Query join that must be materialized. |
| 8 | **Read-only evidence** | `evidence.md` | Before/after TMDL digest proving the source model was untouched. |
| 9 | **Migration runbook** | design + dependencies | Dependency-ordered steps: dims → OBT → views → DQ conversion → repoint measures → validate. |
| 10 | **Validation queries** | design Phase 6 | Concrete SQL + DAX parity checks to run before cutover. |
| 11 | **Risk register** | harvest gaps | Graded risks: missing incremental refresh, DirectQuery→batch, Power-Query-join dims, embedded business filters, hardcoded date ranges, out-of-scope facts. |
| 12 | **Build artifacts manifest** | output folder | Lists the notebook, T-SQL, design doc, registry, evidence files shipped alongside. |

Sections 1–5, 8 cover *what was extracted*. Sections 6, 7, 9–11 are what make the
report **actionable for an engineer** — never omit them when the data exists.

## Risk register — always check for these

- **No incremental refresh policy** → imports are full reloads; decide a watermark.
- **DirectQuery sources** → cannot stay live in one materialized table; schedule batch.
- **Power Query `Table.NestedJoin` dimensions** → must be materialized in Fabric.
- **Business filters embedded in M/SQL** (excludes, queue drops) → centralize in the OBT build.
- **Hardcoded date ranges** in DAX calendars → extend or make dynamic.
- **Different-grain facts** kept out of the OBT → confirm reports don't expect them unified.
- **RLS roles** → if present, must be re-implemented in the Fabric semantic model.

## Output

A single self-contained `architecture-report.html` plus the build-artifact
files, written to the user's chosen output folder. Run the archflow independent
review (Stage 5) and fix any CRITICAL/ERROR before presenting.
