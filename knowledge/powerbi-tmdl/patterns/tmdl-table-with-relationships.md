# TMDL: table file + relationships

> **Last validated**: 2026-04-26
> **Confidence**: 0.92

## When to use this pattern

Adding a new table to a PBIP semantic model, with proper TMDL formatting that Tabular Editor and Power BI Desktop both accept.

## Sales.tmdl (full example)

```tmdl
table Sales
    lineageTag: 8b3f2d4e-1234-5678-90ab-cdef12345678

    column SalesId
        dataType: int64
        isHidden: true
        sourceColumn: SalesId
        summarizeBy: none
        lineageTag: 1a2b3c4d-1234-5678-90ab-cdef12345678

    column OrderDate
        dataType: dateTime
        formatString: yyyy-mm-dd
        sourceColumn: OrderDate
        summarizeBy: none

    column ShipDate
        dataType: dateTime
        formatString: yyyy-mm-dd
        sourceColumn: ShipDate
        summarizeBy: none

    column CustomerId
        dataType: int64
        isHidden: true
        sourceColumn: CustomerId
        summarizeBy: none

    column ProductId
        dataType: int64
        isHidden: true
        sourceColumn: ProductId
        summarizeBy: none

    column Quantity
        dataType: int64
        sourceColumn: Quantity
        summarizeBy: sum

    column UnitPrice
        dataType: decimal
        formatString: "$#,##0.00"
        sourceColumn: UnitPrice
        summarizeBy: average

    column Amount
        dataType: decimal
        formatString: "$#,##0.00"
        sourceColumn: Amount
        summarizeBy: sum

    measure 'Total Sales' = SUM(Sales[Amount])
        formatString: "$#,##0"

    measure 'Total Quantity' = SUM(Sales[Quantity])
        formatString: "#,##0"

    measure 'Avg Unit Price' = DIVIDE([Total Sales], [Total Quantity])
        formatString: "$#,##0.00"

    measure 'Sales LY' =
            CALCULATE(
                [Total Sales],
                SAMEPERIODLASTYEAR(DateTable[Date])
            )
        formatString: "$#,##0"

    measure 'Sales YoY %' =
            DIVIDE(
                [Total Sales] - [Sales LY],
                [Sales LY]
            )
        formatString: "0.00%;-0.00%;0.00%"

    partition Sales = m
        mode: import
        source = ```
            let
                Source = Sql.Database("server.database.windows.net", "AnalyticsDb"),
                Sales_Table = Source{[Schema="dbo", Item="Sales"]}[Data]
            in
                Sales_Table
        ```
```

## DateTable.tmdl

```tmdl
table DateTable
    dataCategory: Time
    lineageTag: cd-of-date-table-uuid

    column Date
        dataType: dateTime
        isKey: true
        formatString: yyyy-mm-dd
        sourceColumn: Date
        dataCategory: PaddedDateTableDates
        summarizeBy: none

    column Year
        dataType: int64
        sourceColumn: Year
        summarizeBy: none

    column Quarter
        dataType: string
        sourceColumn: Quarter
        summarizeBy: none

    column Month
        dataType: string
        sourceColumn: Month
        summarizeBy: none

    column MonthNumber
        dataType: int64
        sourceColumn: MonthNumber
        summarizeBy: none

    sortByColumn Month = MonthNumber

    hierarchy Calendar
        level Year
            column: Year
        level Quarter
            column: Quarter
        level Month
            column: Month
        level Date
            column: Date

    partition DateTable = m
        mode: import
        source = ```
            let
                Source = #date(2020, 1, 1),
                EndDate = #date(2030, 12, 31),
                DayCount = Duration.Days(EndDate - Source) + 1,
                Dates = List.Dates(Source, DayCount, #duration(1, 0, 0, 0)),
                DatesTable = Table.FromList(Dates, Splitter.SplitByNothing(), {"Date"}),
                Typed = Table.TransformColumnTypes(DatesTable, {{"Date", type date}}),
                WithYear = Table.AddColumn(Typed, "Year", each Date.Year([Date]), Int64.Type),
                WithQuarter = Table.AddColumn(WithYear, "Quarter", each "Q" & Text.From(Date.QuarterOfYear([Date])), type text),
                WithMonth = Table.AddColumn(WithQuarter, "Month", each Date.ToText([Date], "MMM"), type text),
                WithMonthNumber = Table.AddColumn(WithMonth, "MonthNumber", each Date.Month([Date]), Int64.Type)
            in
                WithMonthNumber
        ```
```

`dataCategory: Time` + `dataCategory: PaddedDateTableDates` on the key column = Power BI / TMDL recognizes this as the model's date table.

## relationships.tmdl

```tmdl
relationship Sales_OrderDate_DateTable
    fromTable: Sales
    fromColumn: OrderDate
    toTable: DateTable
    toColumn: Date
    # cardinality: many-to-one (default: Sales is many, DateTable is one)
    # crossFilteringBehavior: oneDirection (default)
    # isActive: true (default)

relationship Sales_ShipDate_DateTable
    fromTable: Sales
    fromColumn: ShipDate
    toTable: DateTable
    toColumn: Date
    isActive: false
    # Use via USERELATIONSHIP in measures that report by ship date

relationship Sales_Customer
    fromTable: Sales
    fromColumn: CustomerId
    toTable: Customer
    toColumn: CustomerId

relationship Sales_Product
    fromTable: Sales
    fromColumn: ProductId
    toTable: Product
    toColumn: ProductId
```

## TMDL formatting checklist

When writing or reviewing TMDL:

1. ✅ 4 spaces, no tabs
2. ✅ LF line endings (not CRLF)
3. ✅ No BOM at file start
4. ✅ No trailing whitespace
5. ✅ Multi-line DAX uses indented continuation (NOT backslash)
6. ✅ Multi-line M (Power Query) wrapped in triple backticks
7. ✅ Names with spaces / special chars use single quotes (`'Total Sales'`)
8. ✅ Every measure has `formatString:` line
9. ✅ Every column has `summarizeBy:` line (`none` for keys/IDs)
10. ✅ Every IsKey column or hidden column explicit (`isHidden: true`, `isKey: true`)
11. ✅ Date table has `dataCategory: Time` and key column has `dataCategory: PaddedDateTableDates`
12. ✅ Inactive relationships explicit (`isActive: false`)

## Lineage tags

`lineageTag: <uuid>` is auto-generated by Power BI / Tabular Editor on first save. It identifies an object across rename / move operations. Don't hand-edit; let the tool manage them.

If you copy-paste a TMDL block to create a new table, REMOVE the lineageTag — let the tool regenerate. Otherwise you'll have two tables claiming the same lineage.

## See also

- `concepts/tmdl-syntax.md` — full syntax reference
- `concepts/relationships-and-cardinality.md` — relationship semantics
- `concepts/pbip-project-structure.md` — where this file lives
- `anti-patterns.md` (items 17, 20)
