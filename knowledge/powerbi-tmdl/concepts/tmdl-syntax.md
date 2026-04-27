# TMDL syntax

> **Last validated**: 2026-04-26
> **Confidence**: 0.92
> **Source**: https://learn.microsoft.com/en-us/analysis-services/tmdl/

## What TMDL is

TMDL (Tabular Model Definition Language) is a YAML-like, indentation-based, source-controllable format for tabular semantic models. It replaces JSON-based `.bim` files for new projects and is the format used by PBIP.

```
.SemanticModel/
├── definition/
│   ├── model.tmdl                  # model-level settings, culture, perspectives
│   ├── database.tmdl               # database-level metadata
│   ├── relationships.tmdl          # all relationships
│   └── tables/
│       ├── Sales.tmdl              # one file per table
│       ├── Customer.tmdl
│       └── DateTable.tmdl
└── definition.pbism                # PBIP semantic-model marker file
```

## Indentation rules

- 4 spaces, no tabs
- Properties of a parent object live indented one level deeper
- Multi-line strings use triple backticks ``` ` ` ` ```
- No trailing whitespace
- LF line endings (not CRLF) — Tabular Editor warns on CRLF on macOS/Linux

A trailing-whitespace bug or a tab in place of spaces breaks Tabular Editor parsing silently. Lint TMDL files in CI.

## Table definition

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

    measure 'Sales YTD' =
            CALCULATE(
                [Total Sales],
                DATESYTD(DateTable[Date])
            )
        formatString: "$#,##0"

    partition Sales = m
        source = ```
            let
                Source = Sql.Database("server", "db"),
                Sales = Source{[Schema="dbo", Item="Sales"]}[Data]
            in
                Sales
        ```
```

Notes:
- Measure names with spaces use `'single quotes'`
- Multi-line DAX uses indentation; the engine tolerates whitespace
- `sourceColumn:` is the column name in the SOURCE; `column SalesId` is the model-side name

## Relationships

In `relationships.tmdl`:

```tmdl
relationship Sales_to_DateTable
    fromTable: Sales
    fromColumn: OrderDate
    toTable: DateTable
    toColumn: Date

relationship Sales_to_Customer
    fromTable: Sales
    fromColumn: CustomerId
    toTable: Customer
    toColumn: CustomerId

relationship Sales_ShipDate_to_DateTable
    fromTable: Sales
    fromColumn: ShipDate
    toTable: DateTable
    toColumn: Date
    isActive: false                     # inactive — used via USERELATIONSHIP
    crossFilteringBehavior: oneDirection
```

Defaults:
- `isActive: true`
- `crossFilteringBehavior: oneDirection` (one-to-many, single-direction)
- `cardinality: manyToOne` (many-side first, then one-side)

## Calculated columns

```tmdl
column 'Full Name'
    dataType: string
    expression = Customer[FirstName] & " " & Customer[LastName]
    summarizeBy: none
```

Use `expression =` (with `=`) for calculated columns. Use `sourceColumn:` (no `=`) for columns from the data source.

## Hierarchies

```tmdl
hierarchy Calendar
    level Year
        column: Year

    level Quarter
        column: Quarter

    level Month
        column: Month

    level Date
        column: Date
```

Hierarchies enable drill-down in visuals.

## Perspectives

```tmdl
perspective Sales
    perspectiveTable Sales
        perspectiveColumn Amount
        perspectiveColumn OrderDate
        perspectiveMeasure 'Total Sales'

    perspectiveTable DateTable
        perspectiveColumn Date
        perspectiveColumn Year
```

Perspectives hide tables/columns/measures from specific user groups in Q&A and PivotTable views. They do NOT enforce security — for that, use RLS.

## Roles (RLS)

```tmdl
role 'Sales Reps'
    modelPermission: read

    tablePermission Sales
        filterExpression = Sales[Region] = USERPRINCIPALNAME()

    tablePermission Customer
        filterExpression = Customer[Region] = USERPRINCIPALNAME()
```

`tablePermission` filter expressions run in row context per row of the table — they're effectively row-context predicates. Reference columns directly; do NOT reference measures (Power BI will reject the model).

## Annotations and metadata

```tmdl
table Sales
    annotation PBI_Id = "9d58fce4-..."
    annotation PBI_NavigationStepName = "Navigation"

    column Amount
        dataType: decimal
        annotation Format = "<Format ...>"
```

Annotations are key-value pairs Power BI uses internally. Don't edit `PBI_Id` (it's the GUID). `Format` annotations control measure formatting beyond `formatString:`.

## Linting checklist

When reviewing TMDL:
1. 4-space indentation, no tabs
2. LF line endings only
3. No trailing whitespace
4. No BOM
5. Quoted names where needed (spaces, special chars)
6. Multi-line DAX in measures uses indentation (not backslash continuation)
7. Every relationship has explicit `crossFilteringBehavior` if not default
8. Every measure has a `formatString` line
9. Every table has at least one partition (or is calculated via `expression =`)
10. RLS expressions reference columns, not measures

## See also

- `concepts/relationships-and-cardinality.md`
- `concepts/row-level-security.md`
- `patterns/tmdl-table-with-relationships.md`
- `anti-patterns.md` (items 17, 20)
