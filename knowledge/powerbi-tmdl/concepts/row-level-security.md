# Row-Level Security (RLS)

> **Last validated**: 2026-04-26
> **Confidence**: 0.91
> **Source**: https://learn.microsoft.com/en-us/power-bi/enterprise/service-admin-rls

## What RLS does

Restricts what rows a user can see in a semantic model based on their identity. Same report, different data per user.

Two flavors:
- **Static RLS** — role contains a hardcoded filter (`Region = "North"`). Assign users to roles.
- **Dynamic RLS** — role uses `USERPRINCIPALNAME()` or `USERNAME()` to filter by the calling user.

Dynamic is usually what you want for production — one role for everyone, filtered per user.

## Static RLS

```tmdl
role 'North Sales Reps'
    modelPermission: read

    tablePermission Sales
        filterExpression = Sales[Region] = "North"

    tablePermission Customer
        filterExpression = Customer[Region] = "North"
```

Assign users in the Power BI Service: Workspace → Dataset → Security → role → add users. Static is simple but doesn't scale: a role per region per role per ... → maintenance nightmare.

## Dynamic RLS

Define a security table that maps user emails to the entities they can see:

```
SecurityMapping
| UserEmail        | Region    |
| ---------------- | --------- |
| alice@corp.com   | North     |
| bob@corp.com     | South     |
| bob@corp.com     | East      |    ← bob has access to two regions
| ceo@corp.com     | (all)     |
```

The role:

```tmdl
role 'Sales by Region'
    modelPermission: read

    tablePermission SecurityMapping
        filterExpression = SecurityMapping[UserEmail] = USERPRINCIPALNAME()

    tablePermission Sales
        filterExpression = Sales[Region] IN VALUES(SecurityMapping[Region])
```

Two `tablePermission` clauses:
1. The security table is filtered to the current user's rows
2. Sales is filtered to regions in the now-filtered security table

For this to work, `SecurityMapping[Region]` must relate to `Sales[Region]` somehow (direct relationship or shared dimension).

## Helper functions for identity

| Function | Returns |
|---|---|
| `USERPRINCIPALNAME()` | UPN — `user@tenant.com`. Stable, recommended. |
| `USERNAME()` | DOMAIN\user (on-prem) or UPN (cloud). Older. |
| `CUSTOMDATA()` | Embedded scenarios (Power BI Embedded). |

Always use `USERPRINCIPALNAME()` for cloud Power BI.

## Bridge / fact-only RLS

For very large fact tables, filter the fact directly without a bridge:

```tmdl
role 'Sales Reps'
    modelPermission: read

    tablePermission Sales
        filterExpression = LOOKUPVALUE(SecurityMapping[Region], SecurityMapping[UserEmail], USERPRINCIPALNAME()) = Sales[Region]
```

`LOOKUPVALUE` returns a single value or BLANK. If multi-region access is needed, use the `IN VALUES()` pattern above.

## RLS + bidirectional relationships

Bidirectional relationships break RLS by default. To allow propagation across bidirectional relationships within a role:

```tmdl
role 'Sales Reps'
    modelPermission: read

    tablePermission Sales
        filterExpression = Sales[Region] = "North"

    relationships
        relationship Sales_to_Customer
            securityFilteringBehavior: bothDirections
```

Without `securityFilteringBehavior: bothDirections`, the role's filter on Sales doesn't propagate up to Customer through a bidirectional relationship.

## What CAN'T be in an RLS expression

1. **Measures** — RLS expressions evaluate per-row in a row context; measures evaluate in a filter context. Power BI rejects models that reference measures in RLS.
2. **`COUNTROWS` over the same table** — also row-context-incompatible
3. **Time-intelligence functions** — usually reject
4. **Aggregations** — same reason

What you CAN use:
- Column references (the row-context column on the table)
- Constants
- Logical operators (`AND`, `OR`, `IN`, `=`, `<>`, `>`, `<`, `>=`, `<=`)
- `RELATED` to walk one-to-many to "one" side and grab a column
- `LOOKUPVALUE`
- `USERPRINCIPALNAME()`, `USERNAME()`, `CUSTOMDATA()`

## Testing RLS

In Power BI Desktop: **Modeling → View as roles** → pick role + "Other user" with an email. Browse the report — see only what that user would see.

In the Service: **Dataset → Security → Test as role** → same.

Always test with at least 3 users:
1. A user in the role with a single mapping
2. A user in the role with multi-mapping (verify `IN VALUES()` works)
3. A user NOT in the role (should see nothing — empty visuals, not an error)

## Object-Level Security (OLS) — sibling concept

Hides entire tables / columns / measures from a role:

```tmdl
role 'Limited'
    modelPermission: read

    tablePermission ConfidentialTable
        metadataPermission: none
```

Users in 'Limited' don't see `ConfidentialTable` exists. Combine with RLS for full security: hide what shouldn't be seen, filter what's shown.

## Common bugs

- RLS expression references a measure → Power BI rejects model deploy
- User is in two roles → Power BI UNIONs the filters (more permissive). Often unexpected.
- Forgot to deploy RLS roles after model changes (roles only deploy if explicitly published)
- RLS works in Desktop but not Service → check the user is added to the role in the Service
- DirectQuery + dynamic RLS + complex filters → SQL translation may reject
- Bidirectional + RLS without `securityFilteringBehavior` → role filter doesn't propagate

## See also

- `concepts/relationships-and-cardinality.md` — RLS interaction
- `patterns/rls-dynamic-by-userprincipalname.md` — production template
- `anti-patterns.md` (item 15)
