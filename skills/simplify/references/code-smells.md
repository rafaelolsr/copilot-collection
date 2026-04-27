# Code smells reference

> Detailed catalog of patterns the `simplify` skill flags. Each entry has
> shape, why-it's-suspicious, and the typical fix.

## 1. Duplication

### Shape
Identical (or near-identical) blocks of code in 2+ places. Includes:
- Copy-paste with minor variable rename
- Same algorithm with different magic numbers
- Same shape of error handling repeated

### Why suspicious
Future change has to be made N times. Drift is inevitable — the copies stop
being identical, behavior diverges silently.

### Fix
Extract a function. **Apply the rule of three**: don't extract on first
duplication; extract on third. Two might be coincidence.

### Counter-pattern
If the duplication is **structural** (same shape) but **semantic** (different
meaning), keep them separate. Example: validating a user email vs. validating
an admin email — same regex, different error messages, different logging,
different downstream effects. Coupling them makes future changes harder, not
easier.

## 2. Dead code

### Shape
- Functions never called
- Branches with conditions that can't be true
- Unused parameters
- Imports never used
- Variables assigned but never read

### Why suspicious
Dead code looks like live code. Readers waste effort understanding it.
Refactors must keep it working "just in case", which constrains them.

### Fix
Delete it. If you're scared to delete (production code, no tests), git
history preserves it. The "just in case" cost compounds; the cost of
recovering is one git command.

### Counter-pattern
Code that LOOKS dead but is invoked dynamically (reflection, DI containers,
plugin systems, decorators registering by import). Verify before deleting.

## 3. Premature abstraction

### Shape
- Interface with one implementation
- Abstract base class with one subclass
- Generic type parameter that's only ever instantiated with one concrete type
- Strategy pattern with one strategy
- Configuration / DI for things never configured

### Why suspicious
The abstraction was added "in case we need it later". Adding indirection
without a current need makes code harder to read NOW for hypothetical
flexibility LATER.

### Fix
Inline. If the second case appears, re-extract. The cost of re-extracting
is low; the cost of carrying speculative abstraction is paid every time
someone reads the code.

### Counter-pattern
Boundaries you can't cross. Database access, HTTP clients, anything you'd
want to mock in tests — keep the interface. The benefit (testability) is
real and current.

## 4. Magic numbers and strings

### Shape
- `if status == 3:` (what is 3?)
- `time.sleep(0.05)` (why 50ms?)
- `users[:25]` (why 25?)
- `if user.role == "admin":` (string literal scattered)

### Why suspicious
Reader has to guess meaning. Updates require finding all instances.

### Fix
Named constant near top of module:
```python
TOP_N_FOR_DASHBOARD = 25
RETRY_BACKOFF_SECONDS = 0.05
ROLE_ADMIN = "admin"

users = all_users[:TOP_N_FOR_DASHBOARD]
```

### Counter-pattern
Truly local, obvious values: `range(10)` for a test loop, `pi = 3.14159`,
`x // 2` for halving. Extracting a constant for these adds noise.

## 5. Deep nesting

### Shape
4+ levels of indentation in a single function:

```python
def process(items):
    for item in items:
        if item.active:
            if item.user:
                if item.user.is_verified:
                    if item.user.region == "US":
                        handle(item)
```

### Why suspicious
Reader has to hold all the conditions in mind. Adding a 5th condition makes
the function unreadable.

### Fix
Guard clauses (early returns):

```python
def process(items):
    for item in items:
        if not item.active:
            continue
        if not item.user:
            continue
        if not item.user.is_verified:
            continue
        if item.user.region != "US":
            continue
        handle(item)
```

Or extract:

```python
def process(items):
    for item in items:
        if _eligible_for_processing(item):
            handle(item)

def _eligible_for_processing(item) -> bool:
    return item.active and item.user and item.user.is_verified and item.user.region == "US"
```

## 6. Long parameter lists

### Shape
Function takes 5+ parameters, especially when subsets cluster:

```python
def create_order(
    customer_id, customer_name, customer_email, customer_address,
    product_id, product_name, product_price,
    shipping_method, shipping_address, ...
):
```

### Why suspicious
Most callers pass the same group together. Function signature changes ripple.
Easy to swap argument order silently.

### Fix
Group cohesive parameters into a dataclass / Pydantic model:

```python
def create_order(customer: Customer, product: Product, shipping: ShippingDetails):
```

### Counter-pattern
Parameters that genuinely don't cluster. Three independent flags with no
relationship don't need a wrapper class. Use `*,` for keyword-only to avoid
order bugs.

## 7. Unclear naming

### Shape
- Single-letter variable names outside very short loops (`x`, `t`, `m`)
- Boolean names that don't read as predicates: `is_admin` good, `admin` ambiguous
- Function names that hide side effects: `get_user()` that also creates if missing
- Abbreviations that don't have one obvious expansion: `proc`, `util`, `mgr`

### Why suspicious
Reader has to deduce meaning from context, slowing comprehension.

### Fix
- Predicates with `is_`, `has_`, `should_`, `can_`
- Side-effecting functions with verbs: `get_or_create_user`, `fetch_or_compute`
- Avoid abbreviation unless it's universally known in the domain

### Counter-pattern
Domain conventions. In math/physics code, `x`, `y`, `t` are clearer than
`horizontal_position`, `vertical_position`, `time_elapsed`. Match the
domain's literacy.

## 8. Mixed levels of abstraction

### Shape
A function that mixes high-level orchestration with low-level details:

```python
def process_invoice(invoice):
    customer = db.execute("SELECT * FROM customers WHERE id = ?", invoice.customer_id).fetchone()
    if customer:
        send_email(customer.email, generate_invoice_pdf(invoice))
```

### Why suspicious
Reader switches mental level constantly. Hard to skim.

### Fix
One level per function:

```python
def process_invoice(invoice):
    customer = _load_customer(invoice.customer_id)
    if customer:
        _send_invoice_to_customer(customer, invoice)

def _load_customer(customer_id):
    return db.execute("SELECT * FROM customers WHERE id = ?", customer_id).fetchone()

def _send_invoice_to_customer(customer, invoice):
    pdf = generate_invoice_pdf(invoice)
    send_email(customer.email, pdf)
```

## 9. Over-defensive code

### Shape
Multiple redundant guards for the same condition:
```python
if x is not None and x != "" and len(x) > 0 and x.strip():
```

### Why suspicious
Distrust of upstream contract leaks into every consumer. Every redundant
check has to be re-evaluated when the contract changes.

### Fix
Trust the contract OR validate at the boundary:
```python
# At the boundary (e.g., API ingress):
if not x:                                   # truthy check covers None, "", []
    raise ValidationError("x required")

# Inside, x is guaranteed truthy:
process(x)
```

### Counter-pattern
Defense in depth where it matters: security boundaries, data corruption
risks, hardware-touching code. There the redundancy is intentional.

## 10. Comment cruft

### Shape
Comments restating what code does:

```python
# Increment counter by one
counter += 1

# Loop through all users
for user in users:
    ...

# Check if user is admin
if user.is_admin:
    ...
```

### Why suspicious
Adds noise without information. Comments drift from code; outdated comments
mislead.

### Fix
Delete. Code is the truth.

### Counter-pattern
Comments explaining WHY:

```python
# Sleep 50ms — empirically the minimum that avoids the rate limiter
time.sleep(0.05)

# This loop runs in reverse because items mutate during iteration
for i in range(len(items) - 1, -1, -1):
    ...

# CRITICAL: must complete before midnight UTC for compliance reporting
schedule_eod_job(...)
```

These are **load-bearing comments** — keep, even if they look like prose.

## Summary table

| Smell | Fix | Cost of false-positive |
|---|---|---|
| Duplication | Extract function | Coupling unrelated things |
| Dead code | Delete | Removing dynamically-invoked code |
| Premature abstraction | Inline | Removing useful boundary |
| Magic numbers | Named constant | Adding noise for trivial values |
| Deep nesting | Guard clauses | Hiding logical structure |
| Long params | Group into dataclass | Coupling independent things |
| Unclear names | Rename | Renaming domain-standard terms |
| Mixed abstraction | Extract by level | Over-decomposing |
| Over-defensive | Trust contract | Removing intentional defense in depth |
| Comment cruft | Delete | Removing load-bearing comments |
