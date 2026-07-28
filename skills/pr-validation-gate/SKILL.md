---
name: pr-validation-gate
description: |
  Reviews and validates pull requests before merge. Reads PR metadata, diff,
  checks, linked work items, and validation evidence; runs a risk-based review
  workflow; optionally posts review comments, approves, or requests changes.

  Use when the user says: "review this PR", "validate this PR", "can this PR
  be approved?", "check PR readiness", "post review comments", "approve this
  PR", or "request changes on this PR".

  Do NOT use for: reviewing only local uncommitted changes without a PR,
  release deployment approval, generic code review without PR context, or
  bypassing human approval policies.
license: MIT
argument-hint: "<PR-url-or-number> [--platform github|ado] [--dry-run] [--comment] [--approve] [--request-changes]"
---
# PR validation gate

This skill is a top-level pull request validation workflow. It orchestrates
review, evidence validation, specialized checks, and optional PR review actions.
It does **not** embed every domain-specific checklist; it routes to specialized
skills or agents when risk signals are present.

## Default behavior

Default to read-only dry-run mode.

| Flag | Default | Meaning |
|---|---|---|
| `--dry-run` | `true` | Produce a recommendation without posting comments or reviews. |
| `--platform` | `auto` | Detect GitHub or Azure DevOps from the PR URL/context. |
| `--comment` | `false` | Post summary and inline/general comments only when explicitly requested. |
| `--approve` | `false` | Approve only when explicitly requested and the decision is `APPROVE`. |
| `--request-changes` | `false` | Request changes only when explicitly requested and blockers exist. |
| `--second-pass` | `auto` | Required before write actions; optional for low-risk dry-runs. |

Never approve, request changes, or post comments unless the user explicitly
passes the matching flag or directly asks for that action.

## When to use

Use this skill when the user asks to:

- Review a GitHub or Azure DevOps PR.
- Validate whether a PR is ready to merge.
- Check PR evidence against linked issue/work item acceptance criteria.
- Decide whether to approve, comment, or request changes.
- Create review comments from findings.
- Re-check a PR after fixes.

Do not use this skill when:

- There is no PR context and the user only wants local diff review.
- The user wants release/deployment approval rather than PR validation.
- The repository policy requires a specific human reviewer and the user asks to
  bypass that policy.
- Tool access is unavailable and the user asks for a real approval action.

## Workflow

1. **Resolve the PR.** Detect platform and fetch PR title, description, author,
   source/target branches, commits, changed files, diff, comments, requested
   reviewers, labels, status checks, and linked issues/work items.
2. **Classify change type.** Tag the PR as one or more of: docs-only, tests,
   application code, API contract, data/model, metadata/lineage, infra, CI/CD,
   auth/security, observability, agent/LLM/eval, migration, or deployment.
3. **Check repository policy.** Identify branch policies, required checks,
   reviewer requirements, linked work item rules, and merge restrictions when
   tools allow it. If policy cannot be checked, report that as a validation gap.
4. **Run baseline review.** Evaluate correctness, security, error handling,
   type safety, performance, tests, observability, maintainability, docs, and
   backward compatibility. Focus only on issues that can affect correctness,
   safety, supportability, or merge readiness.
5. **Invoke specialized checks by trigger.** Use relevant skills or agents when
   the PR touches a domain they cover:
   - `code-review` for general diff review.
   - `security-review` for auth, secrets, permissions, data access, network, or
     dependency risk.
   - `release-readiness` or equivalent checklist for deployable/runtime changes.
   - `observability-readiness` for logging, metrics, tracing, dashboards, or
     telemetry changes.
   - `eval-quality-gate` or `agentic-eval` for LLM, agent, prompt, or eval
     changes.
   - `metadata-lineage-map` for StarBase metadata or lineage changes.
   - `azure-devops-specialist` for Azure DevOps PR, Boards, or pipeline-specific
     policy checks.
6. **Validate evidence.** Confirm that required checks passed, relevant tests
   were run, acceptance criteria are covered, docs/screenshots/reports are
   present when needed, migrations/rollback are documented, and no unresolved
   blocking comments remain.
7. **Draft decision.** Produce one of:
   - `APPROVE`: no blockers and required evidence is present.
   - `COMMENT`: no blockers, but non-blocking questions or suggestions remain.
   - `REQUEST_CHANGES`: blocking findings exist.
   - `BLOCKED`: cannot validate because access, checks, evidence, or tools are
     missing.
8. **Run second-agent validation when required.** Before any write action, ask an
   independent reviewer agent to challenge the decision, findings, missing
   findings, and evidence. Use `rubber-duck`, `code-review`, or
   `security-review` depending on risk. Do not post or approve until this pass is
   complete.
9. **Prepare review output.** Normalize all findings into a concise review with
   decision, blocking findings, non-blocking comments, evidence, missing
   evidence, and suggested PR action.
10. **Act only when explicitly requested.** If `--comment`, `--approve`, or
   `--request-changes` is requested, perform only the action supported by the
   final decision and platform tools.

## Second-agent validation policy

Second-agent validation is optional for low-risk read-only dry-runs, but
mandatory before posting an approval, request-changes review, or authoritative
merge-readiness comment.

Require a second pass when:

- `--approve`, `--request-changes`, or `--comment` is requested.
- The PR touches auth, secrets, permissions, infra, data, migrations,
  observability, agents, prompts, evals, or lineage.
- The PR is large, cross-cutting, or has unclear ownership.
- The primary review finds blockers.
- CI/check status conflicts with the apparent code state.

The second reviewer must answer:

```markdown
## Validation reviewer result

- Agreement: agree | partially agree | disagree
- Missed blockers:
- False positives:
- Evidence gaps:
- Recommended final decision:
```

## Decision rules

Use these rules after the primary and validation passes:

| Condition | Decision |
|---|---|
| Blocking bug, security risk, broken required check, missing required evidence, or unresolved policy failure | `REQUEST_CHANGES` |
| Missing access, missing diff/check data, ambiguous target, or unavailable required tools | `BLOCKED` |
| No blockers but useful non-blocking suggestions/questions | `COMMENT` |
| No blockers, required checks pass, evidence is sufficient, and validation reviewer agrees | `APPROVE` |

Never convert `BLOCKED` into `APPROVE`. If approval was requested but the final
decision is not `APPROVE`, explain why approval was not posted.

## Evidence checklist

Validate evidence appropriate to the change:

- Required CI/status checks are green or explicitly explained.
- Unit/integration/e2e/eval tests match the changed surface.
- Linked issue/work item acceptance criteria are satisfied.
- Docs or user-facing guidance are updated when behavior changes.
- Observability is present for new runtime behavior.
- Security-sensitive changes have explicit review notes.
- Data/metadata changes include lineage, migration, or rollback notes when
  relevant.
- Screenshots/reports/logs are included for UI, generated report, or portal
  validation tasks.

## Review output contract

Always produce this summary before any write action:

```markdown
# PR validation: <PR title or number>

## Decision

APPROVE | COMMENT | REQUEST_CHANGES | BLOCKED

## Summary

<one-paragraph review summary>

## Blocking findings

<findings with file/line, impact, and remediation>

## Non-blocking comments

<suggestions/questions>

## Evidence checked

<CI, tests, linked work items, docs, screenshots, reports, telemetry, policies>

## Missing evidence

<what could not be verified>

## Second-pass validation

<required/optional, agent used, agreement, final adjustment>

## Proposed PR action

dry-run only | post comment | approve | request changes
```

## Posting rules

When posting comments or reviews:

- Prefer concise comments tied to actionable findings.
- Do not post style-only comments unless they affect maintainability or project
  standards.
- Do not duplicate existing unresolved comments.
- Do not approve if required checks are failing or unknown.
- Do not request changes for non-blocking preferences.
- Include a short summary of evidence checked.

For GitHub PRs, prefer `gh` CLI when available:

```bash
gh pr view <pr> --json title,body,author,baseRefName,headRefName,commits,files,reviews,comments,statusCheckRollup
gh pr diff <pr>
gh pr checks <pr>
gh pr review <pr> --comment --body-file <review-body>
gh pr review <pr> --approve --body-file <review-body>
gh pr review <pr> --request-changes --body-file <review-body>
```

For Azure DevOps PRs, prefer the configured Azure DevOps MCP tools, `az repos`
commands, or REST API helpers already available in the environment. If no write
tool is available, stop at the dry-run recommendation.

## Anti-patterns

- Do not approve by default.
- Do not let the same primary reasoning serve as the independent validation
  pass.
- Do not embed full release, security, observability, or eval checklists; route
  to specialized skills/agents instead.
- Do not claim a PR is ready when required checks or linked work item evidence
  could not be read.
- Do not post broad review comments that are not tied to concrete evidence.
- Do not use review actions to bypass branch protection or team policy.

## See also

- `code-review` for local or PR diff review.
- `simplify` for over-engineering and cleanup review.
- `agentic-eval` for LLM/agent evaluation changes.
- `metadata-lineage-map` for StarBase metadata lineage changes.
- `azure-devops-task` for creating Azure Boards tasks from follow-up work.
