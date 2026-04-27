# DAX evaluation context

> **Last validated**: 2026-04-26
> **Confidence**: 0.95
> **Source**: https://learn.microsoft.com/en-us/dax/, https://dax.guide/

## The single most important concept in DAX

DAX evaluates every expression in a context. Two contexts coexist: **row context** and **filter context**. Most "I don't understand why this measure returns blank" or "the total is wrong" trace back to confusion between them.

## Row context

Created automatically when you iterate row-by-row:
- Inside a calculated column on a table
- Inside an iterator function: `SUMX`, `AVERAGEX`, `FILTER`, `ADDCOLUMNS`, `SELECTCOLUMNS`

Row context lets you reference a column without aggregation:

```dax
Sales Calc Column = Sales[Quantity] * Sales[UnitPrice]
-- runs once per row of Sales

Total Sales = SUMX(Sales, Sales[Quantity] * Sales[UnitPrice])
-- iterates Sales row-by-row, multiplies, sums
```

Row context does NOT exist in a measure by default. Writing `Sales[Quantity]` directly in a measure → error: "A single value cannot be determined."

## Filter context

Created by:
- Visual filters (rows and columns of a matrix, slicers, page filters)
- `CALCULATE` filter arguments
- `CALCULATETABLE`
- Relationships propagating filters from one table to another

Filter context narrows the data the aggregation sees:

```dax
Total Sales = SUM(Sales[Amount])
-- in a matrix with Year on rows, evaluated per year
-- filter context = current year
```

## Context transition — the trap

`CALCULATE` performs **context transition**: it converts the current row context into a filter context. This is implicit when you reference a measure from inside a row context.

```dax
-- WRONG — looks innocent, returns wrong total
Sales by Customer Inflated =
    SUMX(
        Customers,
        [Total Sales]   -- ← measure reference inside SUMX = implicit CALCULATE = context transition
    )
-- For each customer row, [Total Sales] is filtered to that customer.
-- This DOES evaluate per-customer, sums the result. Often what you want.
-- But: the context transition can mask other filters in surprising ways.
```

```dax
-- vs:
Sales by Customer =
    SUMX(
        Customers,
        SUMX(
            RELATEDTABLE(Sales),
            Sales[Quantity] * Sales[UnitPrice]
        )
    )
-- Pure row-context iteration, no context transition. Predictable.
```

The rule: **referencing a measure from inside an iterator triggers context transition**. If that's what you want, fine. If not, expand the measure inline.

## CALCULATE — the workhorse

```dax
CALCULATE(<expression>, <filter1>, <filter2>, ...)
```

`CALCULATE`:
1. Evaluates each filter argument in the OUTER filter context
2. Applies the filter results to the filter context
3. Evaluates `<expression>` in the new filter context

Critical detail: filter arguments REPLACE existing filters on the same column by default. Use `KEEPFILTERS` to intersect instead:

```dax
-- This REPLACES any Region filter from outside:
North Sales = CALCULATE([Total Sales], Sales[Region] = "North")

-- This INTERSECTS — if outer filter was West, this returns blank:
North Sales Intersect = CALCULATE([Total Sales], KEEPFILTERS(Sales[Region] = "North"))
```

## ALL, REMOVEFILTERS, ALLEXCEPT

Removing filter context:

```dax
-- All sales regardless of any filter
Grand Total = CALCULATE([Total Sales], REMOVEFILTERS())

-- All sales for any region (but keep date filter)
Sales All Regions = CALCULATE([Total Sales], REMOVEFILTERS(Sales[Region]))

-- All sales except keep the customer filter
Sales Per Customer = CALCULATE([Total Sales], REMOVEFILTERS(Sales), VALUES(Sales[CustomerKey]))
```

`ALL` and `REMOVEFILTERS` are nearly synonyms. Prefer `REMOVEFILTERS` for clarity (its name says what it does); `ALL` returns a table that can be used in iterators too.

## Common bugs from misunderstanding context

### Bug: measure returns blank in totals

```dax
-- WRONG
Margin % = DIVIDE(SUM(Sales[Profit]), SUM(Sales[Revenue]))
-- This works for individual rows, BUT in totals:
-- SUM(Profit) and SUM(Revenue) are computed over all visible rows in the total
-- and DIVIDE returns the ratio of the totals — usually correct
```

But:

```dax
-- WRONG — wrong total
Avg Margin % = AVERAGEX(Sales, DIVIDE(Sales[Profit], Sales[Revenue]))
-- Per row, computes margin %. Then averages those margins.
-- Total = average of percentages, NOT total profit / total revenue.
-- For accurate totals: don't average percentages.
```

### Bug: CALCULATE with measure inside row context

```dax
-- WRONG (in a calculated column on Customers)
Customer Tier = IF([Total Sales] > 10000, "Gold", "Silver")
-- [Total Sales] in a calc column → context transition → filter context = current customer
-- This DOES work. But:
Customer Tier Bug = IF(SUM(Sales[Amount]) > 10000, "Gold", "Silver")
-- SUM(Sales[Amount]) here = sum across ALL sales for ALL customers in current filter
-- (no transition — SUM is not a measure, it's a function call)
-- Returns same tier for every customer. Bug.
```

The rule: in a calculated column, references to measures auto-transition; references to bare aggregation functions don't. Use measures in calc columns, NOT bare `SUM` / `COUNT`.

## Pitfalls to flag

- `EARLIER` used in a measure (only valid in calc columns)
- Bare `SUM(table[col])` in a calculated column where context transition was needed
- `IF` with a column reference in a measure → "single value cannot be determined"
- Iterator over an entire fact table without filter — slow
- `SUMX` over a column already aggregated — eager, wasteful

## See also

- `concepts/dax-time-intelligence.md` — context manipulation for time
- `patterns/dax-time-intelligence-measure.md`
- `patterns/dax-divide-and-coalesce.md`
- `anti-patterns.md` (items 3, 7, 10, 13, 14)
