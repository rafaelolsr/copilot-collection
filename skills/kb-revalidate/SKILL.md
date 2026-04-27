---
name: kb-revalidate
description: |
  Re-validates agent knowledge-base content (concepts, patterns, anti-patterns)
  against authoritative sources. Identifies stale files via `last_validated`
  date, fetches current docs, surfaces discrepancies, and updates files in
  place with new validation date. Designed for the 90-day re-validation
  cycle baked into every agent in this collection.

  Use when the user says: "re-validate the KB", "are the agents stale?",
  "check KB freshness", "update KB for <domain>", "run the 90-day check",
  "did azure-ai-projects change?".

  Do NOT use for: creating new KBs from scratch (use the agent creation
  prompt), reviewing KB structure (use code-review), generating new
  concepts/patterns (manual curation).
license: MIT
allowed-tools: [shell]
---

# KB Re-validate

Every KB file in this collection has a `last_validated:` field. The 90-day
window is the protocol — beyond that, content is suspect. This skill walks
the staleness check, fetches authoritative sources, surfaces discrepancies,
and updates dates.

## Why this exists

Agents in this collection ground their answers in KB content. KB content
goes stale:
- SDKs version-bump and break API
- Microsoft renames products (Azure AI Foundry → Microsoft Foundry, etc.)
- Best practices evolve (PAT → service principal → managed identity → WIF)
- Preview features hit GA (or get cancelled)

Without periodic revalidation, agents confidently quote stale information.
The skill is the operational mechanism that prevents drift.

## The 90-day rule

Every KB file (concept, pattern, anti-pattern, index) has a header:

```markdown
> **Last validated**: 2026-04-26
> **Confidence**: 0.92
```

Or in `_manifest.yaml`:

```yaml
last_validated: "2026-04-26"
```

If `today - last_validated > 90 days`: file is stale. Skill flags AND
re-validates against authoritative sources.

## Workflow

### Step 1 — Identify stale files

```bash
# Find all KB files with last_validated > 90 days ago
find . -path '*/knowledge/*' -type f \( -name '*.md' -o -name '*.yaml' \) | while read f; do
    date=$(grep -oE 'last[_-]validated[":[:space:]]+["]?[0-9]{4}-[0-9]{2}-[0-9]{2}' "$f" | head -1 | grep -oE '[0-9]{4}-[0-9]{2}-[0-9]{2}')
    [ -z "$date" ] && continue
    days_old=$(( ($(date +%s) - $(date -j -f '%Y-%m-%d' "$date" +%s 2>/dev/null || date -d "$date" +%s)) / 86400 ))
    [ "$days_old" -gt 90 ] && echo "$days_old days: $f"
done | sort -rn
```

The script outputs files sorted by staleness. Process oldest first.

### Step 2 — Group stale files by domain

KBs are organized by domain (`knowledge/ms-foundry/`, `knowledge/python/`,
etc.). Re-validate one domain at a time — sources are shared.

### Step 3 — For each domain, identify authoritative sources

Read `knowledge/<domain>/index.md` for the **Reading Protocol** section.
It lists the source URLs:

```markdown
3. If any file has `last_validated` older than 90 days, use `web` tool to
   re-validate against:
   - https://learn.microsoft.com/en-us/azure/foundry/
   - https://pypi.org/project/azure-ai-projects/
```

These are the URLs to fetch.

### Step 4 — Fetch and compare

For each stale file in the domain:
1. Use `web` tool to fetch the relevant authoritative URL(s)
2. Read the current KB file content
3. Spot-check 3-5 specific claims against the fresh source:
   - Version numbers (`azure-ai-projects 2.1.0+` — still current?)
   - Product names (still "Microsoft Foundry"? Renamed?)
   - API signatures (still `client.agents.create_and_deploy(...)`?)
   - Status flags (still PUBLIC PREVIEW? Now GA?)
   - Recommended patterns (Microsoft Agent Framework still recommended?)

### Step 5 — Categorize discrepancies

For each discrepancy found, classify:

| Category | Action |
|---|---|
| **Version bump** (e.g., `2.1.0+` → `2.2.0+`) | Update version reference, bump `last_validated` |
| **Renamed product** | Update name throughout, add `Note:` about rename |
| **Status change** (Preview → GA) | Update status flag, remove PREVIEW warnings |
| **API change** (signature different) | Update code examples, mark old signature deprecated |
| **Pattern obsolete** (new recommended approach) | Add new pattern, mark old as legacy |
| **No change** | Just bump `last_validated` date |

### Step 6 — Update files

For each file:
1. If no change: update `last_validated` date only
2. If change: edit content + update `last_validated` + adjust `confidence` if uncertain

```markdown
> **Last validated**: 2026-07-25     ← updated
> **Confidence**: 0.92
```

For files with significant changes, lower confidence:

```markdown
> **Last validated**: 2026-07-25
> **Confidence**: 0.80                ← lowered while changes settle
> **Note**: Updated 2026-07-25 — Foundry IQ moved from PREVIEW to GA.
> Previous patterns reference preview-era endpoints; verify against
> production endpoint shape.
```

### Step 7 — Update `_manifest.yaml`

Increment `last_validated` at the manifest level too. List any concepts
or patterns whose confidence changed.

### Step 8 — Emit re-validation report

```
KB RE-VALIDATION REPORT
=======================
domain:                ms-foundry
files_examined:        15
files_updated:         12
files_with_no_change:  3 (just date bump)
discrepancies_found:   5
  - version-bump:      2  (azure-ai-projects 2.1.0 → 2.2.1)
  - status-change:     1  (Foundry IQ → GA)
  - api-change:        1  (knowledge_bases.add_source signature)
  - pattern-obsolete:  1  (replaced legacy SK pattern)

confidence_summary:
  before:  avg 0.90
  after:   avg 0.87  (3 files lowered while updates settle)

next_steps:
  - Re-test ms-foundry-specialist agent against updated patterns
  - Run smoke evals to verify no regression
  - Sync changes to Foundry project via scripts/sync.sh
```

## Per-agent re-validation cadence

Different domains drift at different rates. Adjust expectations:

| Domain | Drift speed | Recommended cycle |
|---|---|---|
| `ms-foundry` | Fast (PREVIEW features, monthly SDK releases) | 60 days |
| `microsoft-fabric` | Fast (capacity changes, new features) | 60 days |
| `azure-devops` | Medium (stable platform, occasional features) | 90 days |
| `powerbi-tmdl` | Medium (DAX stable, TMDL evolving) | 90 days |
| `python` | Slow (language stable; SDK evolves) | 120 days |
| `observability` | Slow (KQL stable; OTel evolving) | 90 days |
| `eval-framework` | Slow (patterns stable) | 120 days |

Run this skill on a schedule (cron via `hooks/kb-staleness-warning` — see
that hook). Report fed to the team weekly.

## What NOT to revalidate

- **Anti-patterns** that are universal (mutable defaults, bare excepts) —
  these don't go stale; just bump the date
- **Pure-concept files** about evaluation context, async fundamentals —
  these change rarely; bump the date with a quick read-through
- **Code examples in patterns** — these MUST be tested if the SDK version
  bumped; don't just bump the date

## Anti-patterns of this skill itself

1. **Date-bumping without reading** — the whole point is to verify. Reading
   takes minutes; bumping takes seconds. Don't shortcut.
2. **Updating in place without commit boundary** — make one commit per
   domain, not one giant "re-validate everything" commit.
3. **Dropping confidence to 0.50 because "things might have changed"** —
   confidence is for verified disagreement, not paranoia.
4. **Re-validating only the index, not the concepts/patterns** — drift
   lives in details, not navigation.

## Configuration

| Parameter | Default | Effect |
|---|---|---|
| `domain` | "all stale" | Specific domain to revalidate, or "all" |
| `threshold_days` | 90 | Files older than this are stale |
| `dry_run` | false | If true, identify but don't modify |
| `fetch_timeout` | 30s | Per-source web fetch |

## See also

- `hooks/kb-staleness-warning/` — the hook that nags weekly
- The agents themselves — each agent's `index.md` lists authoritative sources
