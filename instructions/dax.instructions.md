---
name: dax
description: |
  Standards for DAX (Data Analysis Expressions) used in Power BI / Fabric
  semantic models. Auto-applied to .dax files and TMDL measures. Enforces
  DIVIDE over /, mandatory marked date table for time intelligence,
  measures over calculated columns, no hardcoded values, format strings
  via TMDL property (not FORMAT in expression), evaluation context
  awareness.
applyTo: "**/*.dax,**/*.tmdl"
---

# DAX standards

When writing or modifying DAX (in measures, calculated columns, RLS
expressions), follow these rules. DAX has subtle traps; these standards
prevent the most common ones.

## Mandatory rules

### Always DIVIDE, never `/`

```dax
# WRONG — returns infinity (#NUM!) when denominator = 0
Margin % = SUM(Sales[Profit]) / SUM(Sales[Revenue])

# CORRECT
Margin % = DIVIDE(SUM(Sales[Profit]), SUM(Sales[Revenue]))

# CORRECT with explicit alternate
Margin % = DIVIDE(SUM(Sales[Profit]), SUM(Sales[Revenue]), 0)
```

`DIVIDE(numerator, denominator, alternateResult)` — when denominator is
0 or blank, returns `alternateResult` (default: BLANK). Always BLANK for
ratios that should show "no data" rather than zero.

### Time intelligence requires a marked date table

```dax
# WRONG — column on the fact table; no marked date table
Sales LY = CALCULATE([Total Sales], SAMEPERIODLASTYEAR(Sales[OrderDate]))

# CORRECT
Sales LY = CALCULATE([Total Sales], SAMEPERIODLASTYEAR(DateTable[Date]))
```

Requirements (silent failures otherwise):
1. Continuous date table with NO gaps
2. One row per day
3. Date column is `date` type (not `datetime`, not string)
4. Marked as date table (`dataCategory: Time` + key column has
   `dataCategory: PaddedDateTableDates` in TMDL)
5. Single relationship from fact's date column to date table's date column

### Measure references in iterators trigger context transition

```dax
# Subtle — works but you should KNOW it's happening
Sales by Customer =
    SUMX(
        Customers,
        [Total Sales]                # implicit CALCULATE = context transition
    )
```

The bare `[Total Sales]` inside `SUMX` IS implicitly wrapped in `CALCULATE`,
which converts the row context into a filter context. This is usually
what you want. But if you want pure row-context iteration:

```dax
Sales by Customer (no transition) =
    SUMX(
        Customers,
        SUMX(RELATEDTABLE(Sales), Sales[Quantity] * Sales[UnitPrice])
    )
```

Document the choice when subtle.

### Format strings via TMDL, not FORMAT()

```dax
# WRONG — returns text, breaks sort and totals
Sales Display = FORMAT([Total Sales], "$#,##0")

# CORRECT — set formatString in TMDL
measure 'Total Sales' = SUM(Sales[Amount])
    formatString: "$#,##0"
```

`FORMAT()` returns text. Visuals can't sort, totals don't aggregate.
Reserve for cases where conditional formatting requires expression-based.

### Measures over calculated columns

```dax
# WRONG — calculated column; storage cost; refresh cost; per-row computation
Sales[LineTotal] = Sales[Quantity] * Sales[UnitPrice]

# CORRECT — measure; computed at query time
Total Sales = SUMX(Sales, Sales[Quantity] * Sales[UnitPrice])
```

Calculated columns are valid for: row-level slicing dimensions, fixed
values needed in relationships. NOT for: anything that's just an
aggregation.

## Common patterns

### Year-over-year

```dax
Sales LY =
    CALCULATE(
        [Total Sales],
        SAMEPERIODLASTYEAR(DateTable[Date])
    )

Sales YoY $ = [Total Sales] - [Sales LY]

Sales YoY % =
    DIVIDE(
        [Total Sales] - [Sales LY],
        [Sales LY]
    )
```

### Year-to-date

```dax
Sales YTD = TOTALYTD([Total Sales], DateTable[Date])

# For fiscal year ending June 30
Sales FYTD = TOTALYTD([Total Sales], DateTable[Date], "06-30")
```

### Rolling window

```dax
Sales R12M =
    CALCULATE(
        [Total Sales],
        DATESINPERIOD(
            DateTable[Date],
            LASTDATE(DateTable[Date]),
            -12,
            MONTH
        )
    )
```

### Conditional aggregation

```dax
# Use COALESCE / DIVIDE alt-result instead of IF(ISBLANK(...))
Display Price = COALESCE([Avg Price], 0)

# Status by threshold via SWITCH(TRUE())
Performance Status =
    SWITCH(
        TRUE(),
        [% of Target] >= 1.0, "On Target",
        [% of Target] >= 0.9, "Near Target",
        "Below"
    )
```

## Evaluation context — pitfalls

### EARLIER only in calc columns

```dax
# WRONG — EARLIER in a measure
Rank Sales = COUNTROWS(FILTER(Sales, Sales[Amount] > EARLIER(Sales[Amount])))

# CORRECT — VAR captures the value
Rank Sales =
    VAR CurrentAmount = SELECTEDVALUE(Sales[Amount])
    RETURN COUNTROWS(FILTER(Sales, Sales[Amount] > CurrentAmount))
```

### CALCULATE filters REPLACE by default

```dax
# This REPLACES any Region filter from outside
North Sales = CALCULATE([Total Sales], Sales[Region] = "North")

# This INTERSECTS with existing filter
North Sales Intersect = CALCULATE([Total Sales], KEEPFILTERS(Sales[Region] = "North"))
```

If outer context is "Region = West", `North Sales` returns North data;
`North Sales Intersect` returns BLANK (intersection is empty).

### Removing context: REMOVEFILTERS over ALL

```dax
# OK
Total = CALCULATE([Total Sales], ALL(DateTable))

# Better — name says what it does
Total = CALCULATE([Total Sales], REMOVEFILTERS(DateTable))
```

`ALL` is a table function (returns rows) AND a filter modifier. When you
mean "remove filter", `REMOVEFILTERS` reads more clearly.

## RLS — what works

Row-Level Security expressions evaluate per-row in row context. Allowed:
- Column references
- Constants
- Logical operators (`AND`, `OR`, `IN`)
- `RELATED` (one-to-many to "one" side)
- `LOOKUPVALUE`
- `USERPRINCIPALNAME()`, `USERNAME()`, `CUSTOMDATA()`

NOT allowed:
- Measure references
- Aggregations (`COUNTROWS`, `SUM`, etc.)
- Time-intelligence functions

```tmdl
role 'Sales Reps'
    modelPermission: read

    tablePermission Sales
        filterExpression =
            VAR UserRegions = VALUES(SecurityMapping[Region])
            RETURN Sales[Region] IN UserRegions

    tablePermission SecurityMapping
        filterExpression = SecurityMapping[UserEmail] = USERPRINCIPALNAME()
```

## Anti-patterns to flag

| Pattern | Severity |
|---|---|
| `/` instead of `DIVIDE()` | WARN — div-by-zero risk |
| Time intelligence without marked date table | CRITICAL — wrong results silently |
| `FORMAT()` in measure used to "fix" totals | WARN — returns text, breaks sort |
| Calculated column where a measure would do | INFO — storage waste |
| `EARLIER` inside a measure | CRITICAL — invalid; only in calc columns |
| `SUMX` over a column that's already aggregatable | INFO — eager evaluation |
| Bidirectional relationship without justification | WARN — ambiguity |
| Measure referenced in RLS expression | CRITICAL — model rejects |
| Hardcoded date / value in measure (`"2024-01-01"`) | WARN — parameterize |
| Missing `formatString` on measure (TMDL) | WARN |
| `FORMAT()` chains for display | INFO — use TMDL formatString |
| `IF(ISBLANK(...))` instead of COALESCE / DIVIDE alt-result | INFO |
| `RELATED` across many-to-many without `RELATEDTABLE` | WARN — ambiguous |
| `ALL` when `REMOVEFILTERS` is more explicit | INFO |

## Validation

Run DAX through Tabular Editor's "Best Practice Analyzer" — community
rules catch most of these. For one-off checks:

```bash
# Find bare division (in TMDL files)
grep -nE '[A-Za-z_][A-Za-z0-9_]*\s*/\s*[A-Za-z_]' **/*.tmdl | grep -v DIVIDE

# Find FORMAT() in measure expressions (likely a code smell)
grep -nE 'measure .*= FORMAT\(' **/*.tmdl
```

## See also

- `instructions/tmdl.instructions.md` — TMDL syntax this DAX lives in
- `agents/powerbi-tmdl-specialist/` — for deep questions
- [DAX guide](https://dax.guide/) — reference (community)
- [DAX official docs](https://learn.microsoft.com/en-us/dax/)
