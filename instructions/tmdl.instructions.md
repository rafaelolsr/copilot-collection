---
name: tmdl
description: |
  Standards for TMDL (Tabular Model Definition Language) files. Auto-applied
  to .tmdl files in PBIP projects. Enforces 4-space indentation, LF line
  endings, no BOM, no trailing whitespace, mandatory format strings on
  measures, marked date table, no API keys.
applyTo: "**/*.tmdl"
---

# TMDL standards

When generating or modifying TMDL files, follow these rules. TMDL is the
indentation-based, source-controllable format for Power BI / Analysis
Services tabular models.

## File-level rules

- **Indentation:** 4 spaces, NO tabs. Tabular Editor and Power BI Desktop
  both reject tabs.
- **Line endings:** LF only (`\n`), never CRLF. Enforce in `.gitattributes`:
  ```
  *.tmdl text eol=lf
  *.pbism text eol=lf
  *.pbir text eol=lf
  ```
- **Encoding:** UTF-8 without BOM. Some editors add a BOM that breaks
  Tabular Editor on macOS/Linux.
- **No trailing whitespace.** Configure your editor to strip on save.
- **Final newline:** files end with a single `\n`.

## Table structure

```tmdl
table Sales

    column SalesId
        dataType: int64
        isHidden: true
        sourceColumn: SalesId
        summarizeBy: none

    column OrderDate
        dataType: dateTime
        formatString: yyyy-mm-dd
        sourceColumn: OrderDate
        summarizeBy: none

    column Amount
        dataType: decimal
        formatString: "$#,##0.00"
        sourceColumn: Amount
        summarizeBy: sum

    measure 'Total Sales' = SUM(Sales[Amount])
        formatString: "$#,##0"

    partition Sales = m
        mode: import
        source = ```
            // Power Query expression
            let
                Source = ...
            in
                Source
        ```
```

## Mandatory rules

### Every measure has `formatString`

```tmdl
# CORRECT
measure 'Total Sales' = SUM(Sales[Amount])
    formatString: "$#,##0"

# WRONG — defaults to general number; no thousands separator, no currency
measure 'Total Sales' = SUM(Sales[Amount])
```

Common format strings:

| Type | formatString |
|---|---|
| Whole currency | `"$#,##0"` |
| Currency w/ cents | `"$#,##0.00"` |
| Percentage | `"0.00%;-0.00%;0.00%"` |
| Count | `"#,##0"` |
| Decimal (2 places) | `"#,##0.00"` |
| Date | `yyyy-mm-dd` (no quotes for date format) |

### Every column has `summarizeBy`

```tmdl
# CORRECT
column Amount
    summarizeBy: sum

column SalesId
    summarizeBy: none

# WRONG — defaults to "default" which Power BI guesses; non-deterministic
column Amount
    sourceColumn: Amount
```

`summarizeBy: none` for IDs / keys; `sum` for numeric facts; `average` /
`max` / `min` rarely.

### Date table has dataCategory + isKey

```tmdl
table DateTable
    dataCategory: Time

    column Date
        dataType: dateTime
        isKey: true
        formatString: yyyy-mm-dd
        sourceColumn: Date
        dataCategory: PaddedDateTableDates
        summarizeBy: none
```

Without `dataCategory: Time` + `dataCategory: PaddedDateTableDates`,
time-intelligence DAX silently returns wrong values. This is the #1
TMDL bug.

### Quoted names

Names with spaces, special chars, or matching keywords use single quotes:

```tmdl
# CORRECT
measure 'Total Sales' = ...
measure 'YoY %' = ...

# WRONG — parser fails on space
measure Total Sales = ...
```

## Naming

- **Tables:** PascalCase, no spaces if avoidable: `Sales`, `Customer`,
  `DateTable`
- **Columns:** PascalCase, no spaces if avoidable: `OrderDate`,
  `CustomerName`
- **Measures:** Display-friendly, may have spaces: `'Total Sales'`,
  `'Sales YoY %'`
- **Hidden technical columns:** `isHidden: true`, often prefixed `_`:
  `_OrderKey`, `_RowHash`

## Relationships

In `relationships.tmdl`:

```tmdl
relationship Sales_to_DateTable
    fromTable: Sales
    fromColumn: OrderDate
    toTable: DateTable
    toColumn: Date

relationship Sales_ShipDate_to_DateTable
    fromTable: Sales
    fromColumn: ShipDate
    toTable: DateTable
    toColumn: Date
    isActive: false                     # use via USERELATIONSHIP
```

Defaults:
- `crossFilteringBehavior: oneDirection` (one-to-many, single-direction)
- `cardinality: manyToOne` (many side first)
- `isActive: true`

Override only with explicit reason. Bidirectional creates ambiguity and
breaks RLS.

## Multi-line DAX

DAX can span multiple lines using indentation (no backslash continuation):

```tmdl
measure 'Sales YTD' =
        CALCULATE(
            [Total Sales],
            DATESYTD(DateTable[Date])
        )
    formatString: "$#,##0"
```

The DAX continuation lines are indented one level deeper than `measure`.
The `formatString:` aligns at the same level as `=`.

## Power Query in partitions

```tmdl
partition Sales = m
    mode: import
    source = ```
        let
            Source = Sql.Database("server", "db"),
            Sales_Table = Source{[Schema="dbo", Item="Sales"]}[Data]
        in
            Sales_Table
    ```
```

The triple-backtick block contains literal M code. Don't interpret it
as TMDL.

## Annotations

Power BI auto-generates `lineageTag` (UUID) and `PBI_Id` annotations.
Don't hand-edit them.

When copying a table to create a new one: REMOVE the `lineageTag` so
the tool regenerates. Otherwise two tables share the same lineage.

## Anti-patterns to flag

| Pattern | Severity |
|---|---|
| Tabs instead of 4-space indent | CRITICAL — TE rejects |
| CRLF line endings | WARN — TE warns on macOS/Linux |
| BOM at file start | WARN — TE may fail |
| Trailing whitespace | INFO — diff noise |
| Date table without `dataCategory: Time` + key dataCategory | CRITICAL — time intelligence broken |
| Measure without `formatString` | WARN |
| Column without `summarizeBy` | WARN |
| Bidirectional relationship without justification | WARN |
| Hardcoded API keys / connection strings in partition source | CRITICAL — leaks via git |
| Names with spaces NOT in quotes | CRITICAL — parser fails |
| Calculated column where a measure would do | INFO — storage waste |
| `lineageTag` copied from another table | WARN — two tables claiming same lineage |
| Multi-line DAX with backslash continuation | CRITICAL — invalid DAX |

## Validation

```bash
# Find tabs (should be empty)
grep -rPn '\t' **/*.tmdl

# Find CRLF
file **/*.tmdl  # should not say "with CRLF"

# Fix CRLF if needed
find . -name '*.tmdl' -exec dos2unix {} \;

# Find BOM
hexdump -C file.tmdl | head -1
# bytes EF BB BF at start = BOM

# Find measures without formatString (line containing "measure" not followed
# in next 5 lines by formatString)
awk '/^[[:space:]]*measure /{m=NR} m && NR>m+5 && !/formatString/{m=0}' **/*.tmdl
```

## See also

- `instructions/dax.instructions.md` — DAX-specific rules (used inside measures)
- `agents/powerbi-tmdl-specialist/` — for deep questions
- [TMDL spec — Microsoft Learn](https://learn.microsoft.com/en-us/analysis-services/tmdl/)
