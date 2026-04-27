# ADR examples

> Real-world patterns showing what makes an ADR useful. The titles are
> illustrative — adapt to your context. Read these before writing your
> own to internalize the format.

---

## Example 1 — Choosing a database

### ADR-0042 — Use PostgreSQL for the main transactional store

- **Status:** accepted
- **Date:** 2026-03-15
- **Deciders:** @alice, @bob, @carol
- **Tags:** database, persistence, transactions

#### Context

We're building a multi-tenant SaaS platform. The transactional store
needs to handle:
- 1k-10k writes/sec at peak
- Complex joins for the reporting layer
- Strong consistency for billing and auth
- Per-tenant data isolation
- 5-year retention with periodic archival

The team has ~3 engineers familiar with Postgres in production. We don't
have a dedicated DBA. Hosted vs self-managed isn't decided yet (that's a
follow-up ADR).

Success: handle 5x current load without sharding for 18 months.

#### Considered options

##### 1. PostgreSQL

Mature, ACID, excellent tooling. Joins, transactions, extensions
(pgvector, PostGIS, etc.). Operational maturity well-documented. Risk:
single-node ceiling at our projected scale; would need read replicas
plus eventual sharding by year 3.

##### 2. CockroachDB

Postgres-compatible wire protocol; horizontally scalable from day 1.
Strong consistency. But: licensing recently changed (BSL); newer
operationally; team has zero hands-on. Risk: licensing surprise + slower
to debug failure modes.

##### 3. MongoDB

Schema flexibility; horizontal scale. But: weak consistency by default
(strengthens are configurable but expensive); poor fit for our heavy
join workload in reports; team has limited Mongo experience.

##### 4. Stay on the existing MySQL

Zero migration cost. But: missing extensions we need (full-text search
plus vector embeddings for the recommendation feature). Continued
investment in MySQL would block the product roadmap.

#### Decision

We chose **PostgreSQL**.

It best matches our team's experience and the workload (joins-heavy
reporting plus transactional core). The horizontal-scale ceiling is
real but not blocking for 18 months — read replicas plus per-tenant
schemas buy us time to evaluate Citus / Spanner if we hit it.

#### Consequences

##### Positive
- Mature ecosystem; postgrest, pgvector, PostGIS available off-the-shelf
- Team can be productive in week one
- Strong community on debugging (Stack Overflow, official IRC)
- Well-understood failure modes; tooling (pgbouncer, repmgr) is stable

##### Negative
- We accept that horizontal scale beyond ~50k tx/sec needs a future
  ADR (Citus extension, Spanner, or shard manually)
- Read-heavy spikes need replica fan-out; we'll need pgbouncer before
  the team grows past 5 backend engineers

##### Neutral
- We commit to the wire protocol — future tooling decisions assume Postgres
- Our backups + restore drills become the team's responsibility (no DBA)

#### What would change this decision

- Sustained tx/sec exceeds 50k for two consecutive months → revisit
  with Citus or sharding ADR
- More than 2 incidents per quarter root-caused to single-node ceiling
  → revisit immediately
- Team hires a DBA and projects > 100k tx/sec within 12 months → consider
  Spanner / CockroachDB upgrade path

#### References

- [Benchmark spike — postgres vs cockroach (Jan 2026)](https://internal-wiki/spike-db)
- ADR-0010 — Original MySQL choice (superseded by this ADR)
- [pgvector docs](https://github.com/pgvector/pgvector)

---

## Example 2 — Choosing an auth strategy

### ADR-0017 — Use Microsoft Entra (Azure AD) workload identity federation for all CI / production auth

- **Status:** accepted
- **Date:** 2026-04-02
- **Deciders:** @alice, @security-team
- **Tags:** auth, security, ci-cd

#### Context

We currently authenticate from CI (Azure Pipelines) to Azure resources
using service principal secrets stored in Variable Groups. Three issues:

1. Secrets must be rotated every 90 days; rotation has been skipped twice
2. Per-environment secrets multiply (dev / test / prod × every project)
3. Recent security audit flagged it as elevated risk

Microsoft's workload identity federation (WIF) issues short-lived OIDC
tokens; no secret to rotate or leak.

Constraint: must work in Azure DevOps Pipelines and (eventually) GitHub
Actions. Must not require Tenant Admin to roll out per-project.

#### Considered options

##### 1. Workload Identity Federation (WIF)

Federated credentials map a CI run to an Entra app. No secret stored.
Per-project setup is self-service (project admin can configure). Audit
log captures token issuance.

##### 2. Service principal with secret rotation automation

Keep SP secrets but automate rotation via Key Vault + Azure Function
that triggers on expiry. Secrets still exist; rotation surface still
exists.

##### 3. Managed Identity (self-hosted agents)

Self-host CI agents on Azure VMs with managed identity. No tokens at
all in CI config. But: operational cost (VMs, scaling, patching)
significant. Self-hosted ≠ free.

##### 4. Stay on SP secrets with stricter rotation

Lower-effort path: improve process around rotation, no architectural
change. Rejected because audit risk doesn't go away.

#### Decision

We chose **Workload Identity Federation**.

Removes the secret entirely (zero rotation burden), it's the modern
Microsoft-recommended path, and rollout can be incremental (per
project / per environment). Cost: ~30 min setup per project + minor
documentation update.

#### Consequences

##### Positive
- Zero secrets in pipeline YAML or Variable Groups
- Audit trail in Entra of every token issuance
- Faster onboarding for new pipelines (no "wait for secret to be added")
- Per-project blast radius (one app per project, not org-wide)

##### Negative
- We accept that workload identity is supported in Azure Pipelines but
  has caveats in older versions; we may need a fallback path for one
  legacy project
- Initial rollout requires per-project Entra app creation; ~30 min × 12
  projects ≈ 6 person-hours

##### Neutral
- Documentation effort: update internal pipeline-template repo
- New pipelines created from this date onwards default to WIF

#### What would change this decision

- Microsoft deprecates / changes WIF significantly → revisit
- We migrate primary CI from Azure DevOps to a system that doesn't
  support WIF → revisit
- We hit 100+ projects and per-project app management becomes burdensome
  → consider centralized identity broker

#### References

- [Workload Identity Federation — Microsoft docs](https://learn.microsoft.com/en-us/entra/workload-id/workload-identity-federation)
- Internal: 2026-Q1 security audit findings (#sec-audit-26q1)

---

## Example 3 — Choosing a frontend framework (recording a less-obvious decision)

### ADR-0023 — Adopt server-side rendering with Next.js for the main app

- **Status:** accepted
- **Date:** 2026-02-20
- **Tags:** frontend, performance

#### Context

The current SPA (React + Vite + client-side routing) has good DX but
serves users on slow mobile connections in emerging markets. Lighthouse
mobile scores are sub-50. SEO is weak because metadata loads after JS.

Considered options for improving:

1. SSR with Next.js (App Router)
2. Astro for content + island components
3. Stay with SPA, optimize bundles + add prerendering

#### Decision

We chose **Next.js with App Router**.

It's the most direct path to SSR/SSG with our existing React component
library. The team can ramp incrementally. Astro was attractive but our
content is highly interactive (not a docs site). SPA optimization
plateaus before reaching our Lighthouse targets.

#### Consequences

##### Positive
- Lighthouse mobile target (75+) is reachable
- Better SEO via real HTML on first paint
- Edge-rendered routes available via Vercel / our hosting

##### Negative
- We accept Next.js as the framework boundary; lock-in to the App
  Router conventions
- Build complexity increases (server-side concerns appear in code)
- Some current 3rd-party React libs need replacement (those that ssr-render
  poorly)

##### Neutral
- Hiring may slightly favor Next.js experience
- Existing component library port is ~3 weeks of work

#### What would change this decision

- A version of our backend latency story emerges where edge functions
  add unacceptable RTT → revisit (consider keep-spa-and-cdn-everything)
- Vercel pricing changes punitively → revisit hosting (not framework)
- A successor to Next.js becomes obviously better in our stack → review
  in 18 months

#### References

- Lighthouse mobile metrics, Q4 2025
- [Next.js App Router docs](https://nextjs.org/docs/app)

---

## Patterns these examples show

1. **Real options, not strawmen** — each rejected option has a specific
   reason; nothing is "less elegant" or "out of fashion"
2. **"What would change this decision" is concrete** — metric crossings,
   versioning events, team changes
3. **Consequences split into positive / negative / neutral** — readers
   know what we ACCEPTED, not just what we got
4. **Date and deciders are visible** — chronology matters; ownership
   matters
5. **Tags help navigation** — `database`, `auth`, `frontend` are
   searchable
6. **References point to evidence** — benchmarks, audits, threads —
   not just docs
7. **Status is honest** — proposed != accepted; supersession is recorded
   on both old and new ADR
