---
name: pr-review
description: >-
  Review someone else's pull request with a fast, high-signal pass, especially
  for DevOps and infrastructure changes such as Terraform, Bicep, Kubernetes,
  Helm, Azure DevOps or GitHub pipelines, Dockerfiles, Ansible, and shell
  automation. Use whenever the user asks to review, inspect, check, approve, or
  give feedback on a PR, branch, diff, PR number, or PR URL, even when they do
  not explicitly say "review". Produces a postable summary explaining the
  change, review coverage, how deeply a human should read it, and only actionable
  blockers or questions. Preview is the default; add --post to create or update
  the summary and inline Azure DevOps PR threads.
argument-hint: >-
  A PR number, Azure DevOps PR URL, or source branch. Add --post to publish the
  generated summary and inline threads; otherwise the skill only previews them.
allowed-tools:
  - view
  - grep
  - glob
  - shell(git:*)
  - shell(az:*)
  - shell(python:*)
user-invocable: true
disable-model-invocation: false
---

# PR Review

Perform one focused review pass over a colleague's change. The product is
signal, not volume: explain what the PR changes, state exactly how much was
inspected, recommend how deeply the human should read it, and raise only issues
that affect security, state, availability, reproducibility, or operational
intent.

An empty review is useful. Never manufacture feedback to appear thorough.

## Contract

| Item | Rule |
|---|---|
| Input | PR number, Azure DevOps PR URL, or source branch |
| Default mode | `preview` — read-only, no PR comments |
| Posting mode | `--post` — update one summary thread and create missing inline threads |
| Analysis passes | One; do not repeatedly reinterpret the diff |
| Questions to user | None; unresolved intent becomes a `QUESTION` |
| Summary size | Target 30 lines, hard maximum 40 |
| Findings | Maximum 5 blockers and 3 questions |
| Web/docs lookup | None |
| Secret handling | Identify the location and risk; never reproduce the value |

`--post` is explicit permission to publish. Do not ask for confirmation after it
is supplied. Without `--post`, never mutate the PR.

## 1. Resolve the PR

This repository is hosted in Azure DevOps. Prefer the current `origin` URL to
derive organization, project, and repository. The expected form is:

```text
https://<org>.visualstudio.com/<project>/_git/<repository>
```

Accept:

- A numeric PR ID.
- A URL containing `pullrequest/<id>`.
- A branch name. Resolve it with:

```powershell
az repos pr list --status active --source-branch "<branch>" `
  --organization "<org-url>" --project "<project>" `
  --repository "<repository>" --output json
```

When a branch maps to zero or multiple active PRs, stop with a concise error
listing the candidates. Do not guess.

If Azure CLI authentication fails, tell the user to run `az login` and stop.
Never request or expose a PAT.

## 2. Gather once

Run the metadata, policy/check, commit, and diff commands as one batch. Do not
iterate unless a command failed.

```powershell
az repos pr show --id <pr-id> --organization "<org-url>" `
  --output json

az repos pr policy list --id <pr-id> --organization "<org-url>" `
  --output json

git fetch origin <source-ref> <target-ref>

git diff --stat origin/<target>...origin/<source>
git diff --numstat origin/<target>...origin/<source>
git diff --find-renames --find-copies `
  origin/<target>...origin/<source>
```

Gather:

- Title, description, author, draft status, source and target refs.
- Changed files, additions, deletions, and total changed lines.
- Required policy/check status and names of failed or pending checks.
- The complete diff or the risk-focused subset allowed by the budget below.

Use the three-dot diff so review scope matches changes introduced by the source
branch relative to the target merge base.

### Input budget

| Changed lines | Coverage |
|---|---|
| Under 800 | Read the entire diff |
| 800–3000 | Read all high-risk files and enough adjacent context to understand them |
| Over 3000 | Mark `too-large`; inspect the file list and highest-risk seams only |

Context files are a soft budget of five. Open more only when required to verify
a potential blocker. Do not browse unrelated code.

If the diff cannot be fetched, stop: there is nothing reliable to review.

Red CI is not a reason to stop. Report the failing required check, continue the
review, and never return `approve` while a required check is failing. Do not
repeat pipeline diagnostics as review findings.

## 3. Establish change intent

Derive intent from the PR title, description, changed-file structure, and diff.
The summary must answer:

1. Why does this PR exist?
2. What behavior, infrastructure, permissions, or deployment flow changes?
3. What is created, replaced, removed, widened, or exposed?
4. Does the implementation match the stated intent?

Use one of these confidence labels:

- `CHANGE INTENT` — title/body and diff agree.
- `CHANGE INTENT — PARTIALLY CONFIRMED` — the implementation is understandable,
  but important purpose or operational context is absent.
- `INTENT MISMATCH` — the diff materially exceeds or contradicts the PR body.

Never claim a surface is unchanged merely because it is absent from the diff.
Use wording such as: `No API changes are visible in the inspected diff`.

## 4. Choose review coverage and reading guidance

Coverage must be explicit:

```text
COVERAGE: FULL — 14/14 files, 786/786 changed lines
COVERAGE: RISK-FOCUSED — 8/31 files, 1120/2840 changed lines
COVERAGE: SEAM-ONLY — 6/74 files, diff exceeds 3000 lines
```

Choose exactly one reading recommendation:

| Reading | Use when |
|---|---|
| `READ FULL PR` | Partial coverage, security/IAM/secrets, destructive state, production availability, intent mismatch, or a too-large diff |
| `READ FINDINGS` | Full coverage with localized blockers/questions; inspect those lines and skim the remainder |
| `SUMMARY FIRST` | Full coverage, green required checks, low-risk scope, and no actionable findings; normal approval policy still applies |

The recommendation guides attention; it never overrides required human approval
or repository policy.

## 5. Triage only risk-bearing files

Files without a relevant risk lens receive no comment.

| File class | Lens |
|---|---|
| `*.tf`, `*.tfvars`, `*.bicep` | Irreversibility, state, IAM, exposure |
| `k8s/**`, `helm/**`, `*deployment*.yml`, `*deployment*.yaml` | Rollout and availability |
| `.github/workflows/**`, `azure-pipelines*.yml`, `*pipeline*.yml` | Supply chain, identity, secrets |
| `Dockerfile`, `*.dockerfile` | Provenance, privilege, secret persistence |
| `ansible/**`, `*.sh`, `Makefile` | Idempotency, quoting, blast radius |

### Terraform and Bicep

- Destroy or replacement implied but not disclosed in the PR body.
- `prevent_destroy` removed or weakened.
- Provider or module version floating/unpinned.
- Backend, workspace, subscription, or state key changed.
- IAM wildcard in actions or resources.
- Public ingress widened to `0.0.0.0/0` or `::/0`.
- Credential or secret committed in variables.
- Stateful migration has no snapshot, rollback, or maintenance plan.

### Kubernetes and Helm

- Floating or `latest` image tag.
- Missing resource requests or limits on a production workload.
- Missing readiness probe where traffic can reach a cold pod.
- One replica on a production path without stated intent.
- Privileged execution, `hostNetwork`, host mounts, or root user.
- ConfigMap or Secret changes without a rollout trigger.
- Selector, service port, or probe changes that prevent traffic routing.

### CI pipelines

- Third-party action/task pinned to a mutable tag rather than an immutable SHA or
  approved versioning mechanism.
- Untrusted pull-request code runs with target-branch credentials.
- Permissions are absent, write-all, or wider than required.
- A secret is passed to a command likely to print arguments or environment.
- A self-hosted runner is reachable from fork- or public-triggered events.
- Deployment environment, service connection, or condition broadens production
  execution unexpectedly.

### Docker

- Floating base image.
- Runtime process remains root without justification.
- Secret passed through `ARG`, `ENV`, or a copied credentials file.
- Build and runtime stages unintentionally include compilers, credentials, or
  privileged tooling.

### Ansible, shell, and Make

- Non-idempotent action makes reruns destructive.
- Missing quoting or unsafe expansion changes the target set.
- Recursive deletion, broad wildcard, or environment fallback widens blast
  radius.
- Failure is ignored or converted into success.
- A production command lacks an explicit environment or subscription guard.

## 6. Classify findings

Use only:

- `BLOCKER` — a concrete change is required before approval because the diff
  introduces security widening, irreversible/stateful risk, unreproducible
  deployment, or availability impact.
- `QUESTION` — intent or operational context is missing and cannot be proven
  from the PR. A question may become a blocker after the answer.

Do not use notes, praise, style feedback, naming feedback, or generic best
practices.

Every finding follows:

```text
path:line
  → consequence: what can break in production
  → action: one concrete correction or decision required
```

Consequence comes before opinion. If the only observation restates the diff,
drop it.

When findings exceed the cap, retain the highest-blast-radius items and add:
`N lower-impact findings omitted from this summary.`

## 7. Select the verdict

| Verdict | Rule |
|---|---|
| `request-changes` | Any blocker or failing required check |
| `approve` | Full review, required checks green, and no blocker |
| `too-large` | Diff exceeds 3000 changed lines; identify a practical split seam |

Questions alone do not automatically require `request-changes` unless the
unknown concerns security, destructive state, or production availability.

Draft PRs may be reviewed, but label the state and do not present `approve` as a
merge recommendation.

## 8. Produce exactly one preview block

Return one block with nothing before or after it:

```text
🔴 VERDICT: REQUEST CHANGES
📖 READING: READ FULL PR
🔍 COVERAGE: FULL — 14/14 files, 786/786 changed lines
⚙️ CI: 1 REQUIRED CHECK FAILING — terraform-plan

🎯 CHANGE INTENT — PARTIALLY CONFIRMED
Creates a dedicated database and updates deployment configuration.
The migration and rollback strategy is not described.

💥 EXPECTED IMPACT
Replaces one stateful resource and changes application startup behavior.

⚠️ INTENT MISMATCH
The PR body describes monitoring only, but production ingress also changes.

🚫 BLOCKERS (2)
1. modules/rds/main.tf:41
   → consequence: replacement can discard production data.
   → action: require a snapshot and documented migration window.

❓ QUESTIONS (1)
1. helm/api/values.yaml:8
   → consequence: one replica removes rollout redundancy.
   → action: confirm this is intentional for the target environment.

💬 INLINE THREADS: 3 proposed
```

For an approval with no findings:

```text
🟢 VERDICT: APPROVE
📖 READING: SUMMARY FIRST
🔍 COVERAGE: FULL — 4/4 files, 126/126 changed lines
⚙️ CI: PASSING

🎯 CHANGE INTENT
Pins deployment dependencies and narrows pipeline permissions.

💥 EXPECTED IMPACT
Builds become reproducible; deployment behavior is otherwise unchanged in the
inspected diff.

No blocking findings.
```

For a too-large PR, identify a split seam:

```text
🟣 VERDICT: TOO LARGE
📖 READING: READ FULL PR
🔍 COVERAGE: SEAM-ONLY — 6/74 files, diff exceeds 3000 lines
⚙️ CI: PASSING

🎯 CHANGE INTENT — PARTIALLY CONFIRMED
Combines an infrastructure migration, pipeline rewrite, and Helm rollout.

Split first by infrastructure provisioning, then pipeline wiring, then workload
rollout. These seams have independent failure and rollback paths.
```

## 9. Post only with `--post`

Publishing creates:

1. One top-level summary thread containing the preview block.
2. One inline thread per blocker or question when the changed line can be
   anchored reliably.

Do not duplicate complete findings in the summary and inline comments. In
posting mode, the summary may list the numbered finding titles while the inline
threads contain consequence and action.

### Idempotency

Add hidden markers:

```html
<!-- pr-review:summary:v1 -->
<!-- pr-review:finding:<stable-id>:v1 -->
```

Create `<stable-id>` from the normalized finding type, path, changed-side line,
and consequence. Before posting, list existing PR threads and search all comment
bodies for these markers:

```powershell
az devops invoke --area git --resource pullRequestThreads `
  --route-parameters project="<project>" repositoryId="<repo-id>" `
    pullRequestId=<pr-id> `
  --organization "<org-url>" --api-version 7.1 --output json
```

- If the summary marker exists, update that comment rather than creating a new
  thread.
- If an active finding marker exists, do not create it again.
- Do not resolve or delete human-authored threads.
- If reliable deduplication or line anchoring is unavailable, post/update only
  the summary and report the inline comments as `proposed`.

Use Azure DevOps pull request thread APIs through `az devops invoke` for create
and update operations. Inline thread context must use the changed-side path and
line from the current PR iteration. Never anchor to a guessed line.

After posting, replace the preview footer with:

```text
💬 INLINE THREADS: 3 created, 1 existing, 0 unanchored
```

If posting partially fails, report the exact counts and error. Never claim the
review was posted when only the preview was generated.

## Hard rules

- Review the change, never the author.
- Never restate the diff.
- Never comment on formatting, naming, or style.
- Never praise; approval is sufficient.
- Never echo credentials, keys, tokens, connection strings, or secret values.
- Never assert that an uninspected area is safe or unchanged.
- Never speculate when the PR body already explains the decision.
- Never ask the user a review question; put the gap under `QUESTIONS`.
- Never post without `--post`.
- Never duplicate generated threads on reruns.
- If nothing clears the risk bar, approve concisely and stop.
