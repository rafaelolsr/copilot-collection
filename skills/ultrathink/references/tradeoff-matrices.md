# Tradeoff matrices

> Templates for evaluating options across dimensions. Use within the ultrathink
> protocol's TRADEOFFS section. Pick the matrix that matches your decision shape.

## The 5 universal dimensions

Every decision should be evaluated on at least these 5:

| Dimension | Question to answer |
|---|---|
| Cost | What does this option cost — in time, money, complexity, ongoing maintenance? |
| Risk | What's the worst plausible outcome? What's the blast radius? |
| Reversibility | If we're wrong, how hard is undo? One-way door or two-way door? |
| Winners / losers | Who benefits? Who pays the cost? Are they the same people? |
| Failure mode | When this fails (not if), how does it fail — gracefully or catastrophically? |

Most analyses skip the last two. They're the most useful.

## Matrix 1 — Build vs Buy vs Adopt

```
                Build       Buy             Adopt (OSS)
Upfront cost    HIGH        MEDIUM          LOW
Ongoing cost    MAINT       SUBSCRIPTION    UPDATE CHURN
Customization   FULL        VENDOR-LIMITED  FORK IF NEEDED
Lock-in         NONE        HIGH            MEDIUM (API)
Bus factor      INTERNAL    VENDOR          COMMUNITY
Time to value   SLOW        MEDIUM          FAST
Differentiation HIGH        LOW             LOW
```

Use when: any "should we use a tool or build it" question.

## Matrix 2 — Sync vs Async vs Batch vs Stream

```
                Sync        Async           Batch           Stream
Latency         lowest      low             high            lowest per-event
Throughput      low         medium          highest         high
Complexity      lowest      medium          medium          highest
Failure recovery simple     retry           re-run job      checkpoint
Backpressure    blocks      queue grows     not applicable  watermark
Cost            scales w/   scales w/       cheap per-item  always-on infra
                requests    concurrency
```

Use when: deciding processing model.

## Matrix 3 — Refactor scope

```
                Inline fix      Local refactor  Module refactor   System refactor
Time            minutes         hours           days              weeks
Blast radius    one function    one file        one module        many modules
Test impact    none            local tests     module tests      integration
Reviewer load   small PR        medium PR       big PR            multi-PR project
When safe       always          when adjacent   feature-flag       deprecation cycle
                                                or release window
Drift risk      none            low             medium            high
```

Use when: "should we just refactor while we're here?"

## Matrix 4 — DB / storage choice

```
                OLTP            Lakehouse       Warehouse       Cache           Doc DB
Read latency    <10ms           seconds         seconds         <1ms            <50ms
Write latency   <50ms           batched         batched         <1ms            <50ms
Concurrency     high            low-medium      low-medium      very high       high
Schema          strict          flexible        strict          schemaless      flexible
Analytics       slow            optimized       optimized       N/A             limited
Cost / TB       $$$             $               $$              $$$$ (RAM)      $$$
Best for        user requests   ETL / ML        BI / reports    hot data        document-shaped
```

Use when: "where should this data live?"

## Matrix 5 — API change strategy

```
                Add new         Modify existing  Deprecate old   Remove old
Breaking?       no              maybe            no (warn)       yes
Effort          low             varies           low (warn)      cleanup
Migration       opt-in          forced           opt-in          mandatory
Reversibility   high            medium           high            low
Best when       new feature     bug / quality    superseded       all callers gone
```

Use when: changing a public API.

## Matrix 6 — Test layer choice

```
                Unit            Integration     E2E             Eval (LLM)
Cost / test     $               $$              $$$             $$$$
Speed           ms              seconds         minutes         minutes
What it catches logic bugs      wiring bugs     UX / journey    quality regression
Brittleness     low             medium          high            high
Maintenance     low             medium          high            high
Coverage target 80%+            critical paths  5-10 journeys   rubric / golden
```

Use when: designing a test strategy.

## Matrix 7 — Microservice vs Module

```
                Microservice    Module (in monolith)
Deployment      independent     coupled
Team ownership  exclusive       shared possible
Fault isolation strong          process-level
Latency         network hop     in-process
Operational     complex         simple
Data consistency eventually      transactional
Onboarding      service per dev one repo
Scaling         per-service     whole monolith
```

Use when: deciding service boundaries.

## Matrix 8 — Caching strategy

```
                None            Local memo      Redis           CDN
Cost            $0              $ (memory)      $$              $$$
Latency         varies          ns              <5ms            <10ms (edge)
Cache invalidation N/A         restart         pub/sub          TTL / purge
Multi-instance  consistent      INCONSISTENT    consistent       consistent
Best for        no repeat reads single process  shared hot data static / public
```

Use when: hitting a slow data source repeatedly.

## Matrix 9 — Auth strategy

```
                Session cookie  JWT             OAuth           API key         mTLS
User type       browser users   any             any (3rd party) machine         service-to-service
Revocation      easy            hard (until exp) tokens         rotate          cert revocation
Stateful?       yes (server)    no              partial          no              no
Rotation        easy            hard            medium           hard            very hard
Use case        web apps        APIs            social login     internal tools  high security
```

Use when: designing auth for a new system.

## Matrix 10 — LLM model selection

```
                Haiku-class     Sonnet-class    Opus-class
Cost / token    $               $$$ (5x)        $$$$$ (25x)
Latency         fastest         medium          slowest
Quality on hard tasks  low      good            best
Quality on easy tasks  good     excellent       overkill
Tool use        yes             yes             yes (most reliable)
Long context    8-32k           200k            200k+
Best for        classification, fanout, batches  complex agents, deliberation
                tagging, simple structured output
```

Use when: choosing model tier for a workload.

---

## Building your own matrix

For decisions not covered here, build a 4-step matrix:

1. **List options as columns.** At least 3.
2. **List 5-7 dimensions as rows.** Use the 5 universal + domain-specific.
3. **Fill the cells with concrete claims**, not adjectives. "$5/day" beats "expensive". "1 hour to undo" beats "reversible".
4. **Bold the cells that matter most for THIS decision.** Often 2 dimensions dominate; don't pretend all are equal.

Then: state which 2 dimensions dominated your call. That's the
WHAT-WOULD-CHANGE-MY-MIND content.
