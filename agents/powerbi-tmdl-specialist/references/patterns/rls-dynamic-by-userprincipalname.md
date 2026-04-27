# Dynamic RLS via USERPRINCIPALNAME

> **Last validated**: 2026-04-26
> **Confidence**: 0.91

## When to use this pattern

Production RLS where the rules differ per user and you don't want to maintain N roles for N users. Single role, dynamic filter based on a security mapping table.

## Schema

```
SecurityMapping (security table)
| UserEmail       | Region   | Department |
| --------------- | -------- | ---------- |
| alice@corp.com  | North    | Sales      |
| alice@corp.com  | South    | Sales      |   ← multi-region
| bob@corp.com    | West     | Marketing  |
| ceo@corp.com    | (all)    | (all)      |   ← needs special handling

Sales (fact)
| OrderID | Region | Amount | ... |

Customer (dim)
| CustomerID | Region | ... |
```

## TMDL — the role

```tmdl
role 'All Users — Dynamic RLS'
    modelPermission: read

    tablePermission SecurityMapping
        filterExpression = SecurityMapping[UserEmail] = USERPRINCIPALNAME()

    tablePermission Sales
        filterExpression =
            VAR UserRegions = VALUES(SecurityMapping[Region])
            RETURN
                Sales[Region] IN UserRegions

    tablePermission Customer
        filterExpression =
            VAR UserRegions = VALUES(SecurityMapping[Region])
            RETURN
                Customer[Region] IN UserRegions
```

## How it works

1. The role's `tablePermission SecurityMapping` filters that table to the logged-in user's rows
2. `Sales` and `Customer` filters reference `VALUES(SecurityMapping[Region])` — which now returns only the regions the user can see
3. Sales / Customer rows are filtered to those regions
4. The user sees only their authorized data

The relationship between SecurityMapping and other tables is NOT required for this pattern. The filter is computed in DAX, not via relationships.

## Handling "all access" (admin / executive)

For a user who should see everything, special-case it. Two options:

### Option A — sentinel value

```
SecurityMapping
| UserEmail       | Region |
| ceo@corp.com    | *      |   ← sentinel

Role expression:
filterExpression =
    VAR UserRegions = VALUES(SecurityMapping[Region])
    RETURN
        IF(
            "*" IN UserRegions,
            TRUE(),
            Sales[Region] IN UserRegions
        )
```

### Option B — separate admin role

```tmdl
role 'Administrators'
    modelPermission: read
    # no tablePermission filters → user sees everything
```

Assign admin users to this role; everyone else to the dynamic role. Cleaner and audit-friendly.

## Multi-attribute RLS

Filter on two dimensions (region AND department):

```tmdl
tablePermission Sales
    filterExpression =
        VAR Mapping =
            CALCULATETABLE(
                SecurityMapping,
                SecurityMapping[UserEmail] = USERPRINCIPALNAME()
            )
        RETURN
            CONTAINSROW(
                Mapping,
                SecurityMapping[Region], Sales[Region],
                SecurityMapping[Department], Sales[Department]
            )
```

`CONTAINSROW` checks whether the (Region, Department) pair from Sales appears in the user's Mapping rows.

## Hierarchical RLS (e.g., regions roll up)

Often you want "user has access to North America" → can see USA + Canada + Mexico. Schema:

```
RegionHierarchy
| Region | ParentRegion |
| World  | NULL         |
| NA     | World        |
| USA    | NA           |
| Canada | NA           |
| EU     | World        |
| ...
```

Use `PATH` and `PATHCONTAINS`:

```tmdl
column RegionPath
    expression = PATH(RegionHierarchy[Region], RegionHierarchy[ParentRegion])
    summarizeBy: none

# Then:
tablePermission Sales
    filterExpression =
        VAR UserRegion = LOOKUPVALUE(SecurityMapping[Region], SecurityMapping[UserEmail], USERPRINCIPALNAME())
        RETURN
            PATHCONTAINS(RELATED(RegionHierarchy[RegionPath]), UserRegion)
```

## Testing

In Power BI Desktop:
1. Modeling → Manage Roles → select the role
2. Modeling → View as → check "Other user" → enter test email
3. Browse the report — should see only that user's data

In Service:
1. Dataset → Security → role → Test as role → email
2. Same browse

Test cases (mandatory):
1. User with single-row mapping → sees one region only
2. User with multi-row mapping → sees multiple regions
3. User NOT in mapping → empty visuals (NOT an error; just no data)
4. Admin (special case) → full access

## What WON'T work in RLS

These will cause Power BI to reject the model on save / deploy:

- **Measure references** — `[Total Sales] > 1000` in a role expression
- **Aggregations across the table** — `COUNTROWS(Sales) > 0`
- **Time-intelligence functions** — `DATESYTD(...)`
- **`SUMX` over the same table** — `SUMX(Sales, ...)`

These all violate the requirement that filter expressions evaluate per-row in row context.

## Performance considerations

- Each RLS expression is evaluated for every row at query time
- Complex `CONTAINSROW` over large fact tables = slow
- Pre-aggregating high-cardinality dimensions (use a Region key, not Region name string) helps
- For massive datasets, consider RLS at the source (DirectQuery + database row-level security)

## Common bugs

- Forgot to add the user to the role in Power BI Service (works in Desktop, fails in Service)
- Used `USERNAME()` (returns DOMAIN\user on-prem) instead of `USERPRINCIPALNAME()` (returns email)
- Bidirectional relationship between SecurityMapping and another table breaks the filter
- Test forgot the "no mapping" user → empty visuals look like a bug to end-users; document expected behavior
- Two roles assigned to the same user → filters UNION (more permissive) — almost always wrong

## See also

- `concepts/row-level-security.md` — full RLS concepts
- `concepts/relationships-and-cardinality.md` — RLS + relationships
- `anti-patterns.md` (item 15)
