# Decision frameworks

> Reusable frameworks for common decision types. Pick the matching one,
> apply it within the ultrathink protocol.

## 1. Build vs Buy vs Borrow

When deciding whether to build something in-house, buy a vendor solution, or
adopt an open-source library.

| Dimension | Build | Buy | Borrow (OSS) |
|---|---|---|---|
| Upfront cost | High (engineering time) | Medium (licensing) | Low (pip install) |
| Ongoing cost | Maintenance forever | Subscription | Update churn |
| Customization | Total | Vendor-allowed | Fork if needed |
| Bus factor | Yours | Vendor's | Community's |
| Lock-in | Zero | High | Medium (API surface) |
| Time to value | Slow | Medium | Fast |

**Default heuristic**: borrow if a credible OSS option exists, buy if it's a
solved commodity, build only when it's a competitive differentiator.

## 2. Library / framework selection

When picking between competing libraries doing the same job.

Score each candidate 1-5 on:

| Criterion | Notes |
|---|---|
| Maturity | First commit > 3 years, actively maintained, stable API |
| Ecosystem | Plugin / extension / type-stub availability |
| Community | Stars, contributors, active issues, Stack Overflow presence |
| Docs | Beginner getting-started + reference + examples |
| Performance | Benchmarks for your specific workload (not synthetic) |
| Licensing | Compatible with your project's license + your distribution |
| Team familiarity | Onboarding cost for your team |

Weight by what matters most. Sum. Whoever wins by >2 points wins. Ties go to
whichever has the most permissive license + best docs (those are easy to
verify upfront, hard to add later).

## 3. Refactor now vs defer

When deciding whether to refactor a piece of code now or live with it.

Refactor NOW if:
- You're already touching the code for a feature change
- The cruft is actively slowing the current task
- The code's blast radius (callers) is small and bounded
- You have tests that verify behavior

Defer if:
- You're adjacent but not touching this code
- The feature change is urgent and the refactor is a yak shave
- The code has many callers and migration is its own project
- You don't have tests (refactor without tests = fingers crossed)

**The rule**: refactor opportunistically when adjacent + safe. Don't open
"refactor seasons" decoupled from feature work — they tend to bikeshed.

## 4. Database schema migration

When adding / changing a column / table.

Categories of change, ordered by risk:

| Risk | Change | Strategy |
|---|---|---|
| Low | Add nullable column | Online add, backfill in batches |
| Low | Add new table | Just create it |
| Medium | Add NOT NULL column | Add nullable first, backfill, then constrain |
| Medium | Rename column | Add new, dual-write, migrate readers, drop old |
| High | Drop column | Mark deprecated, monitor for callers, drop after window |
| High | Change type | Add new column, dual-write, migrate, swap, drop |
| Highest | Drop table | Multi-month deprecation; archive first |

The mistake: doing a "high" risk change in one migration. Always split into
multiple deploys: write in both old + new shape, migrate readers, then
remove old.

## 5. API design — parameter vs configuration vs separate function

When adding an option to existing behavior.

| If the option... | Choose |
|---|---|
| Affects every call differently | Parameter |
| Is set once per process / session | Module-level config |
| Has 5+ values | Probably split into separate functions |
| Is mutually exclusive with another option | Probably split |
| Is rarely used (<10% of calls) | Keyword-only parameter with default |
| Changes the return type | DEFINITELY separate function |

The smell: a function with a `mode` parameter that branches on type — that's
two functions wearing one signature.

## 6. Sync vs Async vs Batch vs Stream

When deciding the processing model.

| Workload | Latency need | Volume | Choose |
|---|---|---|---|
| User-facing request | <1s | Low | Sync (or async if I/O-bound) |
| Background job | seconds | Medium | Async with retry |
| Bulk processing | minutes | High | Batch |
| Continuous events | <1s per event | High | Stream |

Don't pick the most-flexible default. Streaming is overkill for a daily
report. Sync is wrong for anything that calls 5 LLMs.

## 7. Testing strategy — unit vs integration vs e2e vs eval

| Layer | Cost | Speed | Catches | Use for |
|---|---|---|---|---|
| Unit | $ | ms | Logic bugs | Pure functions, business rules |
| Integration | $$ | seconds | Wiring bugs | DB / cache / API integration |
| E2E | $$$ | minutes | UX bugs | Critical user journeys (5-10 max) |
| Eval | $$$$ | minutes | Quality regression | LLM output quality |

Pyramid: lots of unit, some integration, few e2e, eval where applicable.

The anti-pattern: e2e tests for everything because "they catch the most".
They do, but they're slow and flaky. Reserve for irreplaceable journeys.

## 8. Storage backend choice (Lakehouse vs Warehouse vs OLTP vs Cache)

| Workload | Best |
|---|---|
| Analytics on big data | Lakehouse |
| BI on curated data | Warehouse |
| User reads / writes | OLTP (Postgres / SQL Server) |
| <10ms reads, ephemeral | Cache (Redis) |
| Document-shaped | Document DB (CosmosDB, MongoDB) |
| Time-series | Time-series DB (or Delta partitioned by date) |
| Graph queries | Graph DB |

Real systems have multiple. Don't try to do all jobs with one tool. The
mistake is using OLTP for analytics ("we'll just add an index") or Lakehouse
for a high-frequency app ("we'll cache it").

## 9. Microservices vs Modular monolith

When deciding service boundaries.

Microservices if:
- Different scaling needs per component
- Different teams owning different components
- Different release cadences
- Different language / runtime needs

Monolith (modular) if:
- Single small team
- Single product
- Same scaling profile across modules
- Don't have the operational maturity for distributed systems

The default is monolith. Microservices solve org problems, not technical
problems. If you don't have the org problem, don't pay the technical cost.

## 10. Where to put a feature (which service / module)

When code could plausibly live in 2+ places.

Prefer the option where:
- The data already lives (avoid network calls)
- The team owning that code is the team owning the feature's outcome
- Tests for the feature already exist
- The feature's failure mode is bounded by that service's failure mode

The anti-pattern: "let's put it in the shared service" — shared services
become god services. Local-first; share when 3rd consumer arrives.

---

## Meta: when frameworks disagree

These frameworks are heuristics. Sometimes two say different things for the
same decision. When that happens:

1. State the conflict explicitly in your TRADEOFFS section
2. Pick the framework most aligned with your actual constraints (cost,
   risk, time, team)
3. Document the choice in WHAT-WE'RE-NOT-SAYING ("I'm using framework X
   because Y; under different assumptions framework Z would prefer...")

Frameworks accelerate thinking. They don't replace it.
