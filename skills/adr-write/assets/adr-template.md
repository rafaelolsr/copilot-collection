# ADR-NNNN — <decision title>

- **Status:** <proposed | accepted | superseded by ADR-NNNN | deprecated>
- **Date:** YYYY-MM-DD
- **Deciders:** @name1, @name2
- **Tags:** <comma, separated, tags>

## Context

<1–3 paragraphs.>

What problem are we solving? What constraints (technical, organizational,
budget, time) bound our choice? What's the bigger picture this decision
sits in? What was tried before, if anything?

State what success looks like — the criteria the chosen option must satisfy.

## Considered options

List 3+ genuine alternatives. The "do nothing" option goes here when
defensible. Don't merge variants — keep them distinct.

### 1. Option A — <one-line label>

<one paragraph>

What it is. What it costs. What it gives. Real failure mode.

### 2. Option B — <one-line label>

<one paragraph>

### 3. Option C — <one-line label>

<one paragraph>

## Decision

We chose **Option <X>**.

<3-sentence justification.>

The first sentence states what we chose. The second sentence states the
key reason. The third sentence states the most important tradeoff we
accepted to make this work.

## Consequences

### Positive
- <what gets better; specific outcomes>

### Negative
- <what we accept as cost; concrete>

### Neutral
- <what doesn't change but is worth recording for future readers>

## What would change this decision

Specific evidence or condition that would prompt revisit. Concrete:
- A metric crossing a threshold (e.g., "if daily ingestion exceeds 1M
  rows, revisit Lakehouse vs Warehouse")
- A new technology becoming GA (e.g., "if Foundry IQ ships GA, revisit
  this PREVIEW caveat")
- A change in team / org constraints (e.g., "if we hire a dedicated SRE,
  revisit self-hosted vs managed")
- A failure mode of the chosen option (e.g., "if we hit > 5 prod
  incidents/quarter from this layer, revisit the architecture")

If you can't name one, the decision wasn't analysis-based. Either: keep
deliberating, or admit the decision is preference and document that.

## References

- <link to RFC / discussion thread / Slack thread>
- <link to benchmark / prototype / spike>
- <link to related ADRs that this supersedes / depends on / influences>
- <link to external docs that informed the choice>
