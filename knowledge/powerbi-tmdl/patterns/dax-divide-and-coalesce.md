# DIVIDE and COALESCE patterns

> **Last validated**: 2026-04-26
> **Confidence**: 0.95

## Why these matter

`/` (regular division) returns infinity (#NUM!) on division by zero. `DIVIDE` is the safe alternative. `COALESCE` replaces a list of expressions until it finds the first non-blank.

These two functions show up in nearly every production measure. Use them.

## DIVIDE

```dax
DIVIDE(<numerator>, <denominator>, <alternateResult>)
```

- If `<denominator>` is 0 or blank, returns `<alternateResult>` (default: blank)
- Otherwise, performs division

```dax
-- WRONG
Margin % = SUM(Sales[Profit]) / SUM(Sales[Revenue])
-- Returns infinity when revenue = 0

-- CORRECT
Margin % = DIVIDE(SUM(Sales[Profit]), SUM(Sales[Revenue]))
-- Returns BLANK when revenue = 0

-- CORRECT with explicit zero
Margin % v2 = DIVIDE(SUM(Sales[Profit]), SUM(Sales[Revenue]), 0)
-- Returns 0 when revenue = 0
```

When to default to BLANK vs 0:
- BLANK (`DIVIDE(a, b)`) — visual treats it as no data; doesn't show 0 bars; correct for averages
- 0 (`DIVIDE(a, b, 0)`) — useful when you want chart to render a baseline

## COALESCE

```dax
COALESCE(<expr1>, <expr2>, ..., <exprN>)
```

Returns the first non-blank expression. Equivalent to `IF(ISBLANK(<expr1>), COALESCE(<expr2>...), <expr1>)` but cleaner.

```dax
-- WRONG (verbose)
Display Name =
    IF(
        ISBLANK(Customer[PreferredName]),
        IF(
            ISBLANK(Customer[FirstName]),
            "Anonymous",
            Customer[FirstName]
        ),
        Customer[PreferredName]
    )

-- CORRECT
Display Name = COALESCE(Customer[PreferredName], Customer[FirstName], "Anonymous")
```

## Patterns combining both

### Safe percentage with fallback

```dax
Conversion Rate =
    DIVIDE(
        [Conversions],
        [Sessions],
        BLANK()
    )
```

### Average with fallback

```dax
Avg Price =
    DIVIDE(
        SUM(Sales[Revenue]),
        SUM(Sales[Quantity])
    )
```

`AVERAGE(Sales[UnitPrice])` would be wrong — averages the per-row price ignoring quantity. Total revenue / total quantity is the correct weighted average.

### Default for a missing dim

```dax
Effective Region =
    COALESCE(
        SELECTEDVALUE(Customer[Region]),
        "All Regions"
    )
```

### Performance vs target

```dax
% of Target =
    DIVIDE([Total Sales], [Sales Target], 0)

Performance Status =
    SWITCH(
        TRUE(),
        [% of Target] >= 1.0, "On Target",
        [% of Target] >= 0.9, "Near Target",
        "Below"
    )
```

## DIVIDE vs IF(...=0, ..., ...)

```dax
-- BAD
Margin = IF(SUM(Sales[Revenue]) = 0, BLANK(), SUM(Sales[Profit]) / SUM(Sales[Revenue]))

-- GOOD
Margin = DIVIDE(SUM(Sales[Profit]), SUM(Sales[Revenue]))
```

`DIVIDE` is faster (the engine optimizes it specifically). Don't reimplement.

## Common mistakes

### Returning 0 vs BLANK in YoY calculations

```dax
-- WRONG — shows "0% growth" for periods with no data
YoY = DIVIDE([Sales] - [Sales LY], [Sales LY], 0)

-- CORRECT — shows BLANK for periods without comparable data
YoY = DIVIDE([Sales] - [Sales LY], [Sales LY])
```

For YoY, BLANK is usually right — it indicates "no comparable data" rather than "no growth".

### Using COALESCE for type coercion

```dax
-- WRONG (mixes types)
Display = COALESCE(NumberColumn, "—")

-- CORRECT (explicit conversion)
Display = COALESCE(FORMAT(NumberColumn, "#,##0"), "—")
```

`COALESCE` requires consistent types. Mixed types either error or return blank in unexpected ways.

## See also

- `patterns/dax-time-intelligence-measure.md` — every YoY example uses DIVIDE
- `concepts/dax-evaluation-context.md`
- `anti-patterns.md` (items 1, 9)
