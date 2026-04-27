# DAX time intelligence

> **Last validated**: 2026-04-26
> **Confidence**: 0.94
> **Source**: https://learn.microsoft.com/en-us/dax/time-intelligence-functions-dax

## Prerequisite — a marked date table

Time-intelligence functions (`DATEADD`, `SAMEPERIODLASTYEAR`, `TOTALYTD`, etc.) silently return wrong results without a properly built and **marked** date table. This is the #1 source of "my YoY measure is broken" tickets.

Requirements for a date table:

1. **Continuous** — every day from min(date) to max(date) of fact data, with NO gaps
2. **One row per day** — no duplicates
3. **Date column is `date` type** — not `datetime`, not `string`
4. **Marked as date table** — Tabular Editor: Table → Mark as Date Table → pick the date column. In TMDL: `dataCategory: Time` and the column has `isKey: true` plus `dataCategory: PaddedDateTableDates`.
5. **Relationship to fact tables on the date column** — single direction (date → fact)

```dax
-- Date table generated in DAX:
DateTable =
ADDCOLUMNS(
    CALENDAR(DATE(2020, 1, 1), DATE(2030, 12, 31)),
    "Year", YEAR([Date]),
    "Quarter", "Q" & FORMAT([Date], "Q"),
    "Month", FORMAT([Date], "mmm"),
    "MonthNumber", MONTH([Date]),
    "YearMonth", FORMAT([Date], "yyyy-mm"),
    "DayOfWeek", FORMAT([Date], "dddd")
)
```

In Power Query (preferred for production):

```m
let
    Source = #date(2020, 1, 1),
    EndDate = #date(2030, 12, 31),
    DayCount = Duration.Days(EndDate - Source) + 1,
    Dates = List.Dates(Source, DayCount, #duration(1, 0, 0, 0)),
    DatesTable = Table.FromList(Dates, Splitter.SplitByNothing(), {"Date"}),
    Typed = Table.TransformColumnTypes(DatesTable, {{"Date", type date}}),
    WithYear = Table.AddColumn(Typed, "Year", each Date.Year([Date]), Int64.Type),
    WithMonth = Table.AddColumn(WithYear, "MonthNumber", each Date.Month([Date]), Int64.Type)
in
    WithMonth
```

In TMDL (excerpt):

```tmdl
table DateTable
    dataCategory: Time

    column Date
        dataType: dateTime
        isKey: true
        formatString: yyyy-mm-dd
        dataCategory: PaddedDateTableDates

    column Year
        dataType: int64

    column MonthNumber
        dataType: int64

    sortByColumn Month = MonthNumber

    partition DateTable = m
        source = ```
            // Power Query expression here
        ```
```

## The core time-intelligence functions

### Year-over-Year

```dax
Sales LY =
    CALCULATE(
        [Total Sales],
        SAMEPERIODLASTYEAR(DateTable[Date])
    )

Sales YoY % =
    DIVIDE(
        [Total Sales] - [Sales LY],
        [Sales LY]
    )
```

`SAMEPERIODLASTYEAR` shifts the date filter back 365 (or 366) days. If today's filter is "Q2 2026", it becomes "Q2 2025".

### Year-to-Date

```dax
Sales YTD = TOTALYTD([Total Sales], DateTable[Date])

-- Equivalent (more flexible):
Sales YTD V2 =
    CALCULATE(
        [Total Sales],
        DATESYTD(DateTable[Date])
    )
```

### Month-to-Date / Quarter-to-Date

```dax
Sales MTD = TOTALMTD([Total Sales], DateTable[Date])
Sales QTD = TOTALQTD([Total Sales], DateTable[Date])
```

### Rolling 12 months

```dax
Sales Rolling 12M =
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

### Previous period generic (DATEADD)

```dax
Sales Previous Month =
    CALCULATE(
        [Total Sales],
        DATEADD(DateTable[Date], -1, MONTH)
    )

Sales 7 Days Ago =
    CALCULATE(
        [Total Sales],
        DATEADD(DateTable[Date], -7, DAY)
    )
```

`DATEADD` is the most flexible — shift by N units (DAY/MONTH/QUARTER/YEAR). Use it instead of `SAMEPERIODLASTYEAR` when you want explicit control.

## Custom calendars (fiscal year, 4-4-5)

The built-in time-intelligence functions assume a Gregorian calendar starting January 1. For fiscal years ending other than Dec 31, use the parameter:

```dax
Sales FYTD =
    CALCULATE(
        [Total Sales],
        DATESYTD(DateTable[Date], "06-30")  -- fiscal year ends June 30
    )
```

For 4-4-5 / ISO weeks / lunar calendars, **don't use built-in time intelligence**. Roll your own:

```dax
Sales FY 4-4-5 LY =
    VAR CurrentFY = SELECTEDVALUE(DateTable[FiscalYear])
    VAR CurrentFW = SELECTEDVALUE(DateTable[FiscalWeek])
    RETURN
        CALCULATE(
            [Total Sales],
            ALL(DateTable),
            DateTable[FiscalYear] = CurrentFY - 1,
            DateTable[FiscalWeek] = CurrentFW
        )
```

## Common bugs

### Bug: time intelligence returns blank or wrong totals

Cause: date table not marked, or the relationship goes through the wrong column, or fact table has dates that don't exist in the date table (extends out of range).

Fix:
1. Mark the date table.
2. Verify the relationship uses the date column.
3. Extend the date table to cover all fact dates.

### Bug: YoY for partial current year

`SAMEPERIODLASTYEAR` returns the FULL last year. If you're in mid-July 2026, the last-year measure returns Jan-Dec 2025. For "year so far comparison":

```dax
Sales LY YTD =
    CALCULATE(
        [Total Sales],
        SAMEPERIODLASTYEAR(DATESYTD(DateTable[Date]))
    )
```

### Bug: filter on date table column AND date column

If you filter both, the engine ANDs them, often returning empty. Filter only the date table; let relationships propagate.

## See also

- `concepts/dax-evaluation-context.md` — CALCULATE and filter manipulation
- `patterns/dax-time-intelligence-measure.md` — production templates
- `anti-patterns.md` (items 5, 20)
