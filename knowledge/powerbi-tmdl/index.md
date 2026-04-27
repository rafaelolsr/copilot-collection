# Power BI / TMDL / DAX Knowledge Base — Index

> **Last validated**: 2026-04-26
> **Confidence**: 0.92
> **Scope**: TMDL syntax, DAX (measures, time intelligence, evaluation context), PBIP project structure, Power BI REST API, XMLA deployment, RLS.

## KB Structure

### Concepts

| File | Topic | Status |
|---|---|---|
| `concepts/dax-evaluation-context.md` | Row context, filter context, context transition | Validated |
| `concepts/dax-time-intelligence.md` | DATEADD, SAMEPERIODLASTYEAR, marked date tables | Validated |
| `concepts/tmdl-syntax.md` | TMDL file structure, indentation, references | Validated |
| `concepts/pbip-project-structure.md` | definition.pbir, .SemanticModel/, .Report/, source control | Validated |
| `concepts/storage-modes.md` | Import, DirectLake, DirectQuery — when each, what works | Validated |
| `concepts/relationships-and-cardinality.md` | One-to-many, many-to-many, single vs bidirectional, ambiguity | Validated |
| `concepts/row-level-security.md` | RLS expressions, USERPRINCIPALNAME, dynamic RLS, what breaks | Validated |

### Patterns

| File | Topic |
|---|---|
| `patterns/dax-time-intelligence-measure.md` | YoY / MTD / rolling 12 months — production templates |
| `patterns/dax-divide-and-coalesce.md` | DIVIDE with alt-result; COALESCE for null handling |
| `patterns/dax-currency-conversion.md` | Multi-currency reports with USERELATIONSHIP |
| `patterns/tmdl-table-with-relationships.md` | TMDL table file + relationship definitions |
| `patterns/pbip-project-skeleton.md` | Minimum-viable PBIP project for source control |
| `patterns/xmla-deployment-via-tabular-editor.md` | Tabular Editor CLI deployment with backup |
| `patterns/rls-dynamic-by-userprincipalname.md` | Dynamic RLS based on user identity |

### Reference

| File | Topic |
|---|---|
| `anti-patterns.md` | 20 DAX/TMDL anti-patterns to flag on sight |

## Reading Protocol

1. Start here (`index.md`) to identify relevant files for the task.
2. For task type → file map:
   - "write a DAX measure" → `concepts/dax-evaluation-context.md` + matching pattern
   - "time intelligence (YoY, MTD)" → `concepts/dax-time-intelligence.md` + `patterns/dax-time-intelligence-measure.md`
   - "fix a measure that returns blank" → `concepts/dax-evaluation-context.md` + `anti-patterns.md`
   - "review TMDL" → `concepts/tmdl-syntax.md` + `anti-patterns.md`
   - "set up RLS" → `concepts/row-level-security.md` + `patterns/rls-dynamic-by-userprincipalname.md`
   - "deploy a model" → `patterns/xmla-deployment-via-tabular-editor.md`
   - "convert PBIX to PBIP" → `concepts/pbip-project-structure.md` + `patterns/pbip-project-skeleton.md`
3. If any file has `last_validated` older than 90 days, use `web` tool to re-validate against:
   - https://learn.microsoft.com/en-us/dax/
   - https://learn.microsoft.com/en-us/analysis-services/tmdl/
   - https://learn.microsoft.com/en-us/power-bi/developer/projects/
   - https://learn.microsoft.com/en-us/rest/api/power-bi/
   - https://dax.guide/
4. Check `anti-patterns.md` whenever reviewing user DAX or TMDL.
