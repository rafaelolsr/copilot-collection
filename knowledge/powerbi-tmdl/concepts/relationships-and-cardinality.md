# Relationships and cardinality

> **Last validated**: 2026-04-26
> **Confidence**: 0.92

## The 4 relationship dimensions

Every relationship has 4 properties:

| Property | Options | Default |
|---|---|---|
| Cardinality | one-to-one, one-to-many, many-to-many | one-to-many |
| Cross-filter direction | single, both | single |
| Active | true, false | true |
| Referential integrity assumption | true, false | false |

## Cardinality

### One-to-many (default, recommended)

The "many" side has many rows for one row on the "one" side. Filters propagate from the one side to the many side.

```
Customer (one)  →  Sales (many)
[CustomerID]       [CustomerID]
```

Filter "Customer = Acme" → only Sales rows for Acme.

In TMDL:
```tmdl
relationship Sales_to_Customer
    fromTable: Sales
    fromColumn: CustomerID
    toTable: Customer
    toColumn: CustomerID
    # cardinality is implicit: many (Sales) to one (Customer)
```

### One-to-one

Both sides unique. Rare in fact/dim modeling. Used for:
- Splitting a wide table for security
- Linking a "details" table to a "header"

### Many-to-many

Both sides have duplicate values. Power BI handles this internally with a hidden bridge table; the model semantics are ambiguous unless you set `crossFilteringBehavior` and consider a real bridge.

When you NEED many-to-many: prefer modeling with an explicit bridge table.

```
Sales  →  SalesProductBridge  ←  Product
```

## Cross-filter direction

### Single direction (default)

Filter flows ONE WAY: typically from the dimension (one side) to the fact (many side).

```
Customer (one)  →  Sales (many)
        filter flows this way ↓
```

Predictable. Works with RLS. Use unless you have a specific reason not to.

### Bidirectional ("both")

Filters propagate in BOTH directions.

```
Customer (one)  ↔  Sales (many)
```

Use cases (rare):
- Many-to-many through a bridge where you need filters to traverse the bridge
- Specific aggregation patterns

Pitfalls:
- Creates ambiguity when multiple paths exist between two tables → "ambiguous relationship" error or unexpected behavior
- Breaks RLS unless the role explicitly allows it (`securityFilteringBehavior: bothDirections`)
- Performance cost on large models

In TMDL:
```tmdl
relationship Sales_to_Date_Bidirectional
    fromTable: Sales
    fromColumn: OrderDate
    toTable: DateTable
    toColumn: Date
    crossFilteringBehavior: bothDirections
```

Default to single. Switch to bidirectional only when a specific measure requires it AND you've considered RLS implications.

## Active vs inactive relationships

A model can have multiple relationships between the same two tables, but only ONE can be active at a time. Inactive relationships exist but don't propagate filters by default.

Example: Sales has both `OrderDate` and `ShipDate`. You want to analyze by both.

```tmdl
relationship Sales_OrderDate_to_DateTable
    fromTable: Sales
    fromColumn: OrderDate
    toTable: DateTable
    toColumn: Date
    isActive: true                  # default

relationship Sales_ShipDate_to_DateTable
    fromTable: Sales
    fromColumn: ShipDate
    toTable: DateTable
    toColumn: Date
    isActive: false                 # inactive
```

Activate the inactive one for a specific measure:

```dax
Sales by Ship Date =
    CALCULATE(
        [Total Sales],
        USERELATIONSHIP(Sales[ShipDate], DateTable[Date])
    )
```

`USERELATIONSHIP` activates the named relationship for the duration of `CALCULATE`.

## Referential integrity assumption

Promises that every "many" side row has a match on the "one" side (no orphans). Lets the engine optimize joins:
- Faster query plans
- INNER JOIN instead of LEFT JOIN under the hood

If the assumption is wrong (orphans exist), some rows silently disappear from results. Set this to `true` only if data quality is guaranteed.

In TMDL:
```tmdl
relationship Sales_to_Customer
    ...
    relyOnReferentialIntegrity: true
```

## Ambiguous relationship paths

When multiple paths exist between two tables, Power BI either:
- Picks one arbitrarily (Import mode, sometimes)
- Refuses to evaluate ("ambiguous relationship" error)
- Returns wrong results silently (DirectQuery, sometimes)

```
Customer ──┬── Sales ── DateTable
           │              │
           └── Returns ───┘
```

Filter "Customer = Acme" → does it propagate via Sales or Returns? Both? Result: ambiguous.

Resolutions:
1. Make one path active, the other inactive
2. Use a bridge table to centralize relationships
3. Remove the redundant relationship; use measure-level joins via `RELATEDTABLE`

## Star schema vs snowflake

**Star schema**: dimension tables connect directly to a fact table. Recommended.

```
Customer ──┐
Product   ──┼── Sales (fact)
DateTable ──┘
```

**Snowflake**: dimensions normalized further (DimProduct → DimProductCategory).

```
ProductCategory ── Product ── Sales
```

Star wins for query performance and DAX simplicity. Snowflake adds joins and ambiguity risk. Denormalize unless storage cost forbids it.

## Common bugs

- Bidirectional relationship + multiple paths → "ambiguous"
- RLS on a table that has bidirectional relationships → role filter doesn't apply as expected
- Inactive relationship "doesn't work" — must be activated via `USERELATIONSHIP`
- Many-to-many without a bridge → wrong totals
- Snowflake with bidirectional relationships → ambiguous + slow

## See also

- `concepts/dax-evaluation-context.md` — how filters propagate through relationships
- `concepts/row-level-security.md` — RLS interaction with relationships
- `anti-patterns.md` (items 4, 11)
