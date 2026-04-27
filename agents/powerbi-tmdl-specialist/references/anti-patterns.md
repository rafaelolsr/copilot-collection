# Power BI / TMDL / DAX — Anti-Patterns

> **Last validated**: 2026-04-26
> **Confidence**: 0.92
> Wrong / Correct pairs for every anti-pattern the agent flags on sight.

---

## 1. `/` instead of `DIVIDE()`

Wrong:
```dax
Margin % = SUM(Sales[Profit]) / SUM(Sales[Revenue])
```

Why: returns infinity (#NUM!) when revenue = 0.

Correct:
```dax
Margin % = DIVIDE(SUM(Sales[Profit]), SUM(Sales[Revenue]))
```

---

## 2. Calculated column where a measure would do

Wrong:
```dax
-- Calculated column on Sales
LineTotal = Sales[Quantity] * Sales[UnitPrice]
```

Why: stored at refresh — bloats the model. Re-computed on every refresh even if no aggregation needs it.

Correct:
```dax
-- Measure
Total Sales = SUMX(Sales, Sales[Quantity] * Sales[UnitPrice])
```

Calculated columns are valid when you need the value as a row-level slicing dimension, NOT when you just need an aggregation.

---

## 3. SUMX over a column already aggregated by SUM

Wrong:
```dax
Total = SUMX(Sales, Sales[Amount])
-- Equivalent to SUM but with iterator overhead
```

Correct:
```dax
Total = SUM(Sales[Amount])
```

`SUMX` is for `SUMX(table, expression that requires row context)`. Bare column reference doesn't need row context.

---

## 4. Bidirectional relationship without justification

Wrong:
```tmdl
relationship Sales_to_Customer
    crossFilteringBehavior: bothDirections
```

Why: creates ambiguity in multi-path scenarios; breaks RLS unless `securityFilteringBehavior` set; performance cost.

Correct: leave default (single direction). Switch to bidirectional only when:
1. A specific measure can't be expressed otherwise
2. AND you've considered RLS implications
3. AND you've documented WHY in a comment or wiki

---

## 5. Time intelligence without a marked date table

Wrong:
```dax
Sales LY = CALCULATE([Total Sales], SAMEPERIODLASTYEAR(Sales[OrderDate]))
-- OrderDate is a column on Sales, not a separate marked date table
```

Why: time-intelligence functions require a continuous, marked date table. They appear to work but return wrong totals on partial periods.

Correct:
```dax
-- 1. Have a DateTable marked as date table
-- 2. Relationship Sales[OrderDate] → DateTable[Date]
-- 3. Reference DateTable in time intelligence:
Sales LY = CALCULATE([Total Sales], SAMEPERIODLASTYEAR(DateTable[Date]))
```

---

## 6. DirectQuery + iterator over fact table

Wrong:
```dax
-- Sales is DirectQuery, 100M rows
Sales Adjusted = SUMX(Sales, Sales[Amount] * 1.1)
```

Why: every query iterates 100M rows in the SOURCE database. Times out or kills source performance.

Correct: pre-compute the adjustment in M (Power Query) or in the source view, then `SUM(Sales[AmountAdjusted])`.

---

## 7. FORMAT() in a measure used to "fix" totals

Wrong:
```dax
Sales Display = FORMAT([Total Sales], "$#,##0")
-- Returns text. Loses sortability, breaks numeric totals.
```

Correct: set the measure's `formatString` property (in TMDL or the measure properties pane).
```tmdl
measure 'Total Sales' = SUM(Sales[Amount])
    formatString: "$#,##0"
```

If you really need conditional formatting, use measure-level `formatString` expressions or visual-level conditional formatting — not `FORMAT()` in the calculation.

---

## 8. Missing format string on a measure

Wrong: measure has no `formatString:` line. Power BI uses a default that's usually wrong (general number; no thousands separator; no currency symbol).

Correct: every measure has an explicit format string.
```tmdl
measure 'Total Sales' = SUM(Sales[Amount])
    formatString: "$#,##0"
```

---

## 9. IF(ISBLANK(...)) instead of COALESCE or DIVIDE alt-result

Wrong:
```dax
Display Name =
    IF(
        ISBLANK(Customer[PreferredName]),
        Customer[FirstName],
        Customer[PreferredName]
    )
```

Correct:
```dax
Display Name = COALESCE(Customer[PreferredName], Customer[FirstName])
```

---

## 10. EARLIER in a measure

Wrong:
```dax
-- In a measure
Rank = COUNTROWS(FILTER(Sales, Sales[Amount] > EARLIER(Sales[Amount])))
```

Why: `EARLIER` is only valid in calculated columns (where there's an outer row context to refer to).

Correct in a measure: use `VAR` to capture the value, then filter:
```dax
Rank Sales =
    VAR CurrentAmount = SELECTEDVALUE(Sales[Amount])
    RETURN
        COUNTROWS(FILTER(Sales, Sales[Amount] > CurrentAmount))
```

---

## 11. RELATED across many-to-many without RELATEDTABLE

Wrong:
```dax
-- In a calc column on Customer (which has many-to-many to Region via bridge)
PrimaryRegion = RELATED(Region[Name])
-- Returns ambiguous result or error
```

Correct: use `RELATEDTABLE` and pick:
```dax
PrimaryRegion =
    VAR Regions = RELATEDTABLE(Region)
    RETURN
        IF(COUNTROWS(Regions) = 1, MAXX(Regions, Region[Name]), "Multiple")
```

---

## 12. ALL(table) when REMOVEFILTERS(table) is more explicit

Wrong:
```dax
Total Across All Years = CALCULATE([Total Sales], ALL(DateTable))
```

Both work. Better:
```dax
Total Across All Years = CALCULATE([Total Sales], REMOVEFILTERS(DateTable))
```

`REMOVEFILTERS` reads exactly like what it does. `ALL` does double duty (table function in iterators + filter modifier). Use `REMOVEFILTERS` when you mean "remove filter".

---

## 13. SUM([measure]) — measure inside an aggregation

Wrong:
```dax
Total Sales All Customers = SUM([Total Sales])
-- SYNTAX ERROR — can't aggregate a measure with SUM
```

Correct: measures are already aggregations. To aggregate across customers:
```dax
Total Across Customers =
    SUMX(VALUES(Customer[CustomerKey]), [Total Sales])
```

---

## 14. CALCULATE with measure inside row context — unintended context transition

Wrong:
```dax
-- In a calc column on Customer
Total LTV = CALCULATE([Total Sales])
-- Implicit context transition to current customer. WORKS but easy to mis-interpret.
-- Bug-prone if you intended a global value.
```

Pattern: when you reference a measure inside a row context (calc column or iterator), expect context transition. If you DON'T want it:

Correct (no transition):
```dax
Total LTV Global = SUM(Sales[Amount])
-- Aggregates over ALL Sales, ignoring current customer
```

Be explicit about which behavior you want.

---

## 15. RLS expression that references a measure

Wrong:
```tmdl
tablePermission Sales
    filterExpression = [Total Sales] > 1000
-- Power BI rejects model
```

Why: RLS evaluates per-row in row context. Measures evaluate in filter context. Mixing them → reject.

Correct: compute the predicate using columns and row-context-compatible functions.
```tmdl
tablePermission Sales
    filterExpression = Sales[Amount] > 1000
-- per-row predicate using the actual column
```

---

## 16. PBIX committed instead of PBIP for new projects

Wrong: committing `report.pbix` (binary zip) to git for an actively-edited project. No diffs; no merge; lock-step single-author.

Correct: convert to PBIP. File → Save As → Power BI Project. Commit the folder. Diffs become readable.

---

## 17. TMDL with mixed line endings or BOM

Wrong: `dos2unix` reveals CRLF on Linux/macOS-edited files. Tabular Editor warns / refuses to load.

Correct: enforce LF in `.gitattributes`:
```
*.tmdl text eol=lf
*.json text eol=lf
*.pbir text eol=lf
*.pbism text eol=lf
```

And in `.editorconfig`:
```
[*.tmdl]
end_of_line = lf
charset = utf-8
indent_style = space
indent_size = 4
trim_trailing_whitespace = true
```

---

## 18. Hardcoded workspace IDs in deployment scripts

Wrong:
```yaml
- powershell: |
    Deploy -workspace "9d58fce4-1234-5678-..." -dataset "Sales"
```

Correct: parameterize.
```yaml
variables:
  WORKSPACE_ID: $(WORKSPACE_ID)   # set per environment in pipeline variables
- powershell: |
    Deploy -workspace "$env:WORKSPACE_ID" -dataset "$env:DATASET_NAME"
```

---

## 19. XMLA deployment without backup

Wrong: deploy directly to production with `-O` (overwrite) — no backup.

Correct: export model first.
```bash
TabularEditor.exe -D "<conn>" "<dataset>" -B "backup-$(date +%Y%m%d).bim"
TabularEditor.exe "myproject.SemanticModel" -D "<conn>" "<dataset>" -O -V
```

---

## 20. Missing mark-as-date-table on the date table

Wrong: a DateTable exists, has continuous dates, has a relationship — but it's not marked as a date table. Time-intelligence functions silently return wrong results.

Correct in TMDL:
```tmdl
table DateTable
    dataCategory: Time

    column Date
        dataType: dateTime
        isKey: true
        dataCategory: PaddedDateTableDates
```

Or in Tabular Editor: right-click table → Mark as Date Table → pick the date column.

---

## See also

- `index.md`
- `concepts/dax-evaluation-context.md`
- `concepts/dax-time-intelligence.md`
- `concepts/tmdl-syntax.md`
- `patterns/dax-time-intelligence-measure.md`
- `patterns/rls-dynamic-by-userprincipalname.md`
