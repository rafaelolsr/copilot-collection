# DAX time-intelligence measures (production templates)

> **Last validated**: 2026-04-26
> **Confidence**: 0.94

## Prerequisites

- Date table exists, marked as date table
- Single relationship between fact and date table on the date column
- Fact-table dates exist within date-table range

If any of these is missing, NONE of these measures will work. Fix the date table first.

## Year-over-Year (YoY)

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

Format strings:
- `Sales LY`, `Sales YoY $`: `"$#,##0"`
- `Sales YoY %`: `"0.00%;-0.00%;0.00%"`

## YoY for partial period

If you're mid-year and want "this year so far vs same window last year":

```dax
Sales YTD = TOTALYTD([Total Sales], DateTable[Date])

Sales LY YTD =
    CALCULATE(
        [Total Sales],
        SAMEPERIODLASTYEAR(DATESYTD(DateTable[Date]))
    )

Sales YTD YoY % =
    DIVIDE(
        [Sales YTD] - [Sales LY YTD],
        [Sales LY YTD]
    )
```

## Year-to-Date / Month-to-Date / Quarter-to-Date

```dax
Sales YTD = TOTALYTD([Total Sales], DateTable[Date])

Sales MTD = TOTALMTD([Total Sales], DateTable[Date])

Sales QTD = TOTALQTD([Total Sales], DateTable[Date])
```

For fiscal years (year ends June 30):

```dax
Sales FYTD = TOTALYTD([Total Sales], DateTable[Date], "06-30")
```

## Rolling 12 months (R12M)

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

`DATESINPERIOD(<dates>, <end_date>, <offset>, <interval>)` returns the contiguous date range. `-12 MONTH` = 12 months ending at the current period.

## Rolling 7 days (for daily metrics)

```dax
Sales R7D =
    CALCULATE(
        [Total Sales],
        DATESINPERIOD(
            DateTable[Date],
            LASTDATE(DateTable[Date]),
            -7,
            DAY
        )
    )
```

## Previous period (configurable)

```dax
Sales Prev Month =
    CALCULATE(
        [Total Sales],
        DATEADD(DateTable[Date], -1, MONTH)
    )

Sales Prev Quarter =
    CALCULATE(
        [Total Sales],
        DATEADD(DateTable[Date], -1, QUARTER)
    )

Sales Prev Year =
    CALCULATE(
        [Total Sales],
        DATEADD(DateTable[Date], -1, YEAR)
    )
```

`DATEADD` is more flexible than `SAMEPERIODLASTYEAR` because the offset is parameterizable.

## Cumulative running total (within visible filter)

```dax
Sales Running Total =
    CALCULATE(
        [Total Sales],
        FILTER(
            ALLSELECTED(DateTable[Date]),
            DateTable[Date] <= MAX(DateTable[Date])
        )
    )
```

`ALLSELECTED` respects outer slicer filters but ignores the visual-axis filter (the row context), so the running total accumulates across the visible range.

## Period-to-date that adapts to the visual

When the user might choose Year, Quarter, or Month at runtime:

```dax
Sales PTD =
    SWITCH(
        TRUE(),
        ISFILTERED(DateTable[MonthNumber]), TOTALMTD([Total Sales], DateTable[Date]),
        ISFILTERED(DateTable[Quarter]),     TOTALQTD([Total Sales], DateTable[Date]),
        ISFILTERED(DateTable[Year]),        TOTALYTD([Total Sales], DateTable[Date]),
        [Total Sales]
    )
```

## Anti-patterns inside time intelligence

- Using `SUM` instead of the existing measure (e.g., `SUM(Sales[Amount])` inside `CALCULATE` instead of `[Total Sales]`)
- Filtering BOTH the date table AND a date column on the fact (over-filters, returns empty)
- `SAMEPERIODLASTYEAR` for partial-year comparison (returns the FULL last year — usually wrong)
- Time intelligence in DirectQuery without an Import-mode date table
- Hardcoding date values (`"2024-01-01"` literal in measure)
- Using `EARLIER` to navigate dates (only works in calculated columns; for measures use `CALCULATE` + filter)

## Validation

After writing any time-intelligence measure:
1. Test in a matrix with Year on rows. Each row's value should be the whole year.
2. Test with a date slicer narrowing to one quarter — measure should reflect.
3. Test the YoY measure on January — it should compare to last January, not all of last year.
4. Check the total row — for percentages, total should NOT just be the sum of the percentage column.

## See also

- `concepts/dax-time-intelligence.md` — fundamentals
- `concepts/dax-evaluation-context.md` — why CALCULATE is doing what it does
- `patterns/dax-divide-and-coalesce.md` — pair with DIVIDE for safe ratios
- `anti-patterns.md` (items 5, 7, 13)
