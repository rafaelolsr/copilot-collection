# Multi-currency conversion in DAX

> **Last validated**: 2026-04-26
> **Confidence**: 0.88

## When to use this pattern

Multi-currency reports where:
- Sales / amounts are stored in transaction currency
- A currency-rate table provides exchange rates per date (or month)
- The user picks a target currency at runtime

Common in finance, SaaS billing, e-commerce.

## Schema

```
Sales
| OrderID | OrderDate  | TransactionCurrency | Amount |
| 1       | 2026-01-15 | USD                 | 100.00 |
| 2       | 2026-01-15 | EUR                 |  85.00 |

CurrencyRates
| Date       | FromCurrency | ToCurrency | Rate    |
| 2026-01-15 | USD          | USD        | 1.0     |
| 2026-01-15 | USD          | EUR        | 0.92    |
| 2026-01-15 | USD          | BRL        | 5.45    |
| 2026-01-15 | EUR          | USD        | 1.087   |
| 2026-01-15 | EUR          | EUR        | 1.0     |
| 2026-01-15 | EUR          | BRL        | 5.92    |
| ...

TargetCurrency (disconnected single-column slicer table)
| Currency |
| USD      |
| EUR      |
| BRL      |
```

`TargetCurrency` is a disconnected table — the user picks one value, but it has no relationship to Sales (no row context propagation).

## The measure

```dax
Sales Converted =
    VAR TargetCcy =
        SELECTEDVALUE(TargetCurrency[Currency], "USD")
    VAR Result =
        SUMX(
            Sales,
            VAR FromCcy = Sales[TransactionCurrency]
            VAR OrderDate = Sales[OrderDate]
            VAR Rate =
                CALCULATE(
                    SELECTEDVALUE(CurrencyRates[Rate]),
                    CurrencyRates[Date] = OrderDate,
                    CurrencyRates[FromCurrency] = FromCcy,
                    CurrencyRates[ToCurrency] = TargetCcy
                )
            RETURN
                Sales[Amount] * Rate
        )
    RETURN Result
```

How it works:
1. `TargetCcy` reads the user's slicer selection (default USD if nothing selected)
2. `SUMX` iterates Sales row-by-row
3. Per row, look up the rate matching that row's date + from-currency + the target currency
4. Multiply amount by rate, accumulate

## Performance considerations

This measure iterates sales row-by-row and does a lookup per row. For large fact tables, this is slow.

Mitigations:
1. **Pre-compute rate at refresh** — add a `RateUSD` column to Sales via Power Query (look up rate per row, multiply by amount, store the result). Then a measure becomes `SUM(Sales[AmountUSD]) * <target currency rate today>`.
2. **Use month-end rates instead of daily** — for low-precision reporting; the rate table has 12 rows/year/pair instead of 365
3. **Pre-aggregate** — if the report only shows monthly totals, aggregate first then convert
4. **DirectLake / DirectQuery** — push the conversion to the source database

For most BI cases (dashboards updating nightly), the simple measure is fine. Pre-compute when you hit performance limits.

## Handling missing rates

What if a date has no matching rate?

```dax
VAR Rate =
    CALCULATE(
        SELECTEDVALUE(CurrencyRates[Rate]),
        CurrencyRates[Date] = OrderDate,
        CurrencyRates[FromCurrency] = FromCcy,
        CurrencyRates[ToCurrency] = TargetCcy
    )
VAR SafeRate = COALESCE(Rate, 0)   -- or default to last known rate
```

Better: pre-fill missing dates with the previous trading day's rate during ingestion.

## Cross-currency = same currency optimization

If transaction currency = target currency, skip the lookup:

```dax
VAR Rate =
    IF(
        FromCcy = TargetCcy,
        1.0,
        CALCULATE(
            SELECTEDVALUE(CurrencyRates[Rate]),
            CurrencyRates[Date] = OrderDate,
            CurrencyRates[FromCurrency] = FromCcy,
            CurrencyRates[ToCurrency] = TargetCcy
        )
    )
```

## Reporting on the conversion

Add a label measure for visuals:

```dax
Currency Label =
    "Amounts shown in " & SELECTEDVALUE(TargetCurrency[Currency], "USD")
```

Place it in a card or a title bar so users always know the unit.

## Anti-patterns

- Storing all amounts in a "base currency" column without preserving the transaction currency (loses information)
- Using a SINGLE rate per currency (no date dimension) — wrong for historical reports
- Using `RELATED` to walk to CurrencyRates without a relationship — won't work
- A relationship between Sales and CurrencyRates on date column — creates ambiguity since Sales already has a date relationship

## See also

- `concepts/dax-evaluation-context.md` — VAR, SUMX, CALCULATE
- `patterns/dax-divide-and-coalesce.md` — for when rate is 0
- `concepts/relationships-and-cardinality.md` — disconnected tables
