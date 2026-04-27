# Workflows

Agentic workflows — markdown files with frontmatter that describe automated
actions running on GitHub triggers (PRs, schedules, issues). Copilot
interprets the markdown body as task instructions; safe-outputs constrain
what the workflow can do.

## Directory layout

```
workflows/
├── eval-regression.md
├── kb-staleness-check.md
└── ...
```

Each workflow is a single `.md` file with YAML frontmatter.

## Frontmatter schema

```yaml
---
name: "<Display Name>"
description: "<one-line summary>"
on:
  pull_request:
    paths:
      - "src/**"
  # OR
  schedule: daily on weekdays
  # OR
  issues:
    types: [opened]
permissions:
  contents: read
  pull-requests: write
  issues: read
safe-outputs:
  add-pr-comment:
    label: "<label-name>"
  add-pr-status:
    context: "<status-name>"
  create-issue:
    title-prefix: "[bot] "
    labels: [automation]
---
```

## Differences from standard GitHub Actions

| Aspect | GitHub Actions YAML | Agentic Workflow |
|---|---|---|
| Format | Imperative steps | Markdown body with task description |
| Schedule | cron syntax | Natural language allowed |
| Body | shell commands | Instructions for Copilot to execute |
| Outputs | Free | Constrained via `safe-outputs` |
| Determinism | High | Variable (LLM in the loop) |

Use agentic workflow when:
- Task requires reasoning (analyzing a diff, summarizing CHANGELOG)
- Output is conversational (PR comment, issue body)
- Specifications change frequently

Use standard GitHub Actions when:
- Task is deterministic (lint, test, deploy)
- Speed matters
- You want full control of every step

Both can co-exist in the same repo.

## safe-outputs

Constraints on what the workflow can produce. Without these, the LLM could
do arbitrary things. Some common safe-outputs:

| Safe-output | Use |
|---|---|
| `add-pr-comment` | Post a comment on the PR |
| `add-pr-status` | Set a PR status check |
| `create-issue` | Open a new issue with constraints |
| `add-issue-comment` | Post on existing issue |
| `apply-pr-review-comment` | Post inline review comments |

Each takes config like `label`, `title-prefix`, `labels` to bound the output.

## Body structure

Effective workflow bodies have:

1. **What to do** — high-level intent
2. **Steps** — numbered, each is something the agent should accomplish
3. **Output format** — exact structure of comment / issue body
4. **Failure mode** — what happens if the workflow can't complete
5. **Cost guard** — how to abort if expensive

Example:

```markdown
## What to do

When a PR is opened, summarize the changes for reviewers.

### Steps

1. Get the diff: `gh pr diff $PR_NUMBER`
2. Identify the categories of change (feature / refactor / fix / docs)
3. Write a 3-bullet summary
4. Post as PR comment

### Output

Comment format:
**Summary**:
- <bullet 1>
- <bullet 2>
- <bullet 3>

### Failure
If diff is too large (>5000 lines), post:
"Diff too large for automated summary. Please summarize manually."
Don't fail the workflow — just document.
```

## Workflows in this collection

| Workflow | Trigger | Effect |
|---|---|---|
| `eval-regression.md` | PR touching prompts/agents/tools | Run smoke evals, compare to baseline, post comment, set status |

## Creating a new workflow

1. Create `workflows/<your-workflow>.md`
2. Define the YAML frontmatter (event, permissions, safe-outputs)
3. Write the body in plain English with steps
4. Test in a sandbox repo before enabling on production
5. Add a sample comment / issue body in the markdown to set expectations

## Cost considerations

Each workflow run consumes Copilot tokens. Cap aggressively:
- Eval workflows: budget per run, abort if exceeded
- Daily reports: time-box (≤2 minutes per run)
- PR-frequent workflows: skip on draft PRs (`drafts: false`)

Track monthly cost; surprise bills happen when a workflow loops.

## Anti-patterns

- Schedule "every minute" — almost never the right cadence
- Workflow that opens 10 issues per run (no batching)
- Output that exceeds GitHub comment size (truncate gracefully)
- No cost guard — cron + bug = surprise bill
- Triggering on every commit including draft PRs
- Workflow that requires a human to approve mid-run (hangs)

## See also

- `eval-regression.md` — example: PR-time eval check
- Standard GitHub Actions docs for the underlying mechanism
