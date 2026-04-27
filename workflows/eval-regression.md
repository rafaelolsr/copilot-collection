---
name: "Eval Regression Check"
description: "On PRs touching prompts, agents, or tools — runs smoke evals against the new code and posts a comparison vs the baseline run on main. Blocks merge if quality drops more than 5%."
on:
  pull_request:
    paths:
      - "src/agents/**"
      - "src/workflows/modules/*/prompts/**"
      - "src/tools/**"
      - "evals/**"
      - ".github/agents/**"
permissions:
  contents: read
  pull-requests: write
  actions: read
safe-outputs:
  add-pr-comment:
    label: "eval-regression"
  add-pr-status:
    context: "eval-regression"
---

# Eval Regression Check

When a PR changes prompts, agents, or tools, run smoke evals on the new
code and compare metrics to the most recent baseline run on `main`. Surface
the diff in a PR comment. Block merge if quality drops materially.

This is the automated equivalent of "did this prompt change make things
worse?" — answered before merge, not after.

## What to do

### 1. Determine baseline run
- Query the eval results store (Fabric Delta table or `evals/runs/` JSONL)
  for the most recent successful run on `main`
- Capture the run_id and aggregate metrics (groundedness avg, relevance
  avg, pass rate per metric)
- If no baseline exists (first run for this agent), proceed but note
  "baseline not available" in the PR comment

### 2. Run smoke evals on the PR head
- Check out the PR branch
- Install dependencies: `uv sync`
- Run: `uv run pytest -m "eval and smoke"` against the changed agent /
  pipeline
- Cap cost: budget $5 per PR run (fail fast if exceeded — surface as INFO)

### 3. Compare metrics
For each metric in the PR run:
- Compute relative change vs baseline: `(pr_avg - baseline_avg) / baseline_avg`
- Categorize:
  - `< -10%`: REGRESSION (BLOCKING)
  - `-10% to -5%`: WARNING (non-blocking, post comment)
  - `-5% to +5%`: NEUTRAL (no comment)
  - `> +5%`: IMPROVEMENT (post comment, celebrate)

### 4. Identify per-case regressions
- For cases that PASSED on baseline but FAILED on PR run, list them in the
  comment with: case_id, expected behavior, actual answer, judge reasoning
- Cap at 5 cases shown (more available in Actions logs)

### 5. Post PR comment

Use the `add-pr-comment` safe-output. Format:

```markdown
## 🔬 Eval Regression Check

**Baseline:** run-2026-04-25-abc123 on main (3 runs ago)
**PR run:**  run-2026-04-26-def456

| Metric | Baseline | PR | Δ | Status |
|---|---|---|---|---|
| groundedness avg | 4.32 | 4.18 | -3.2% | ✅ |
| relevance avg | 4.51 | 4.49 | -0.4% | ✅ |
| pass rate (≥4) | 0.87 | 0.81 | -6.9% | ⚠️ WARNING |
| tool_call_accuracy | 0.93 | 0.93 | 0.0% | ✅ |

**Cost of this run:** $1.24

### ⚠️ Per-case regressions (3)

- `qa-042`: passed baseline, failed PR
  - Question: "What is our Q3 revenue?"
  - PR answer: "Revenue figures are not available."
  - Judge: "Did not use retrieved context."
- ...

### Recommendation

Pass rate dropped 6.9%. **Reviewer should investigate before merging.**
Look at the new prompt's system message — possible over-restriction.

If the change is intentional (e.g., narrowing agent's scope), update the
golden dataset to reflect the new expected behavior, then re-run.
```

### 6. Set status check

Use `add-pr-status` to set the `eval-regression` status:
- BLOCKING regression: status = `failure`
- WARNING: status = `pending` (informational)
- Neutral / improvement: status = `success`

This integrates with the branch protection policy. Configure the policy to
require `eval-regression` for merges to `main` once you trust this workflow.

## Configuration

Customize per-project in the workflow frontmatter:

| Setting | Default | Where |
|---|---|---|
| Path triggers | `src/agents/**`, etc. | `on.pull_request.paths` |
| Regression threshold | -5% per metric | hardcode in body |
| Cost cap | $5 per run | hardcode in body |
| Cases shown in comment | 5 max | hardcode in body |
| Block vs warn | -10% blocks, -5% warns | hardcode in body |

## Failure modes

This workflow can produce false positives. Address by:

1. **Stochastic noise**: judge non-determinism causes ~2% jitter run-to-run.
   Threshold of 5% accommodates this. Don't lower.
2. **Bad baseline**: a previously-broken main run becomes the baseline.
   Solution: workflow uses MEDIAN of last 3 successful runs as baseline,
   not just the latest.
3. **Dataset drift**: someone adds easy cases. Check `dataset_hash` in
   metadata; if changed in the PR, comment "dataset changed too — interpret
   results with care".

## Cost guard

Maximum $5/run. If exceeded mid-run, abort and post a comment:

```
⚠️ Eval regression check aborted: cost cap of $5 hit.
Showing partial results from N/M cases. Re-run manually or raise the cap.
```

Never run unbounded — it's a cron away from a surprise bill.

## Setup checklist

To enable this workflow in a project:

- [ ] Pytest markers `eval` and `smoke` defined in `pyproject.toml`
- [ ] Smoke dataset exists at `evals/dataset/<agent>_smoke.jsonl` (≥20 cases)
- [ ] Eval results stored somewhere queryable (JSONL files OR Fabric Delta)
- [ ] LLM judge API key in repo secrets (`LLM_JUDGE_API_KEY` or vendor-specific)
- [ ] Branch protection rule (later) — once trusted, require `eval-regression` status

## Related

- `skills/agentic-eval/SKILL.md` — designing the eval suite this workflow consumes
- `agents/eval-framework-specialist.agent.md` — deep specialist for issues
