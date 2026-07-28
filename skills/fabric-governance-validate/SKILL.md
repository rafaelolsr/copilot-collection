---
name: fabric-governance-validate
description: |
  Validates the governance posture of a Microsoft Fabric workspace by scoring
  live workspace evidence against an authoritative control rubric grounded in
  Microsoft Learn. Hybrid by design: it fetches governance guidance through the
  Microsoft Learn MCP server and collects live workspace state through the Fabric
  Admin Scanner / REST APIs, then emits a scored, cited compliance report.

  Use when the user says: "validate governance for this Fabric workspace", "check
  my workspace against Fabric governance best practices", "is this workspace
  compliant?", "audit sensitivity labels / workspace roles / endorsement /
  domains / deployment pipelines / object ownership", or "produce a Fabric governance report".

  Do NOT use for: changing tenant or workspace settings (read-only audit only),
  Power BI report / TMDL model design, data lineage tracing (use
  metadata-lineage-map), generic Azure governance outside Fabric, or any task
  requiring write access to the workspace.
license: MIT
allowed-tools: [shell]
argument-hint: "<workspace-id|workspace-name> [--mode hybrid|learn-only] [--evidence PATH] [--format markdown|json] [--controls PATH]"
---

# Fabric governance validate

This skill answers one question: **does a Microsoft Fabric workspace meet
documented governance best practices, and where are the gaps?**

It is **read-only**. It never changes tenant settings, workspace roles, labels,
or any item. It only reads evidence and compares it to a rubric.

## Boundary: what each source can and cannot do

| Source | Provides | Cannot provide |
|---|---|---|
| **Microsoft Learn MCP** (`https://learn.microsoft.com/api/mcp`) | The authoritative *rubric*: what each control requires and why, with citations | Any live state of your workspace |
| **Fabric Admin Scanner / REST API** | Live *evidence*: roles, labels, endorsement, domain, capacity, item inventory, item ownership | The "should": the documented requirement |

A governance verdict requires **both**. Learn MCP alone can only produce a
best-practice checklist; it cannot assert your workspace is compliant. The live
evidence alone has no rubric to score against. This skill joins them.

## When to use / NOT to use

Use when the user asks to validate, audit, or score the governance posture of a
named Fabric workspace, or to generate a governance compliance report.

Do not use to:

- Change any tenant or workspace configuration (this skill is read-only).
- Design Power BI reports or TMDL models.
- Trace data lineage (use `metadata-lineage-map`).
- Audit non-Fabric Azure resources.

## Configuration

| Flag | Default | Meaning |
|---|---|---|
| `--mode` | `hybrid` | `hybrid` joins live evidence with the Learn rubric; `learn-only` emits the cited checklist without live evidence. |
| `--scope` | `all` | `workspace` scores only controls evaluable from a workspace role; `tenant` only admin-scoped controls; `all` scores everything. Use `workspace` when you work inside a single workspace and lack tenant-admin rights. |
| `--evidence` | _(none)_ | Path to a pre-collected evidence JSON (e.g. a Scanner API export). When set, the fetch step is skipped. |
| `--controls` | `references/governance-controls.md` | The control rubric to score against. |
| `--format` | `markdown` | `markdown` (scored report) or `json` (machine-readable findings). |

Each control is tagged `workspace` or `tenant`:

| Scope | Controls | Collected by |
|---|---|---|
| `workspace` | workspace-admin-count, service-principal-control, sensitivity-labels, workspace-metadata, deployment-pipeline, git-integration, capacity-assignment | `fetch_workspace_rest.py` (workspace role) |
| `tenant` | no-guest-access, endorsement, domain-assignment, dlp-coverage, object-ownership | `fetch_workspace_evidence.py` (Fabric Admin) |

Modes:

| Mode | Behavior |
|---|---|
| `hybrid` | Collect live evidence (Scanner/REST API or `--evidence` file), fetch the Learn rubric, score each control, emit a verdict per control. Default. |
| `learn-only` | Skip evidence. Fetch the rubric from Learn and emit the cited checklist with every control marked `unknown` (no evidence). Useful as a best-practice advisor. |

## Authentication

The fetch step uses `azure-identity` `DefaultAzureCredential` — never a hardcoded
token or PAT. Two collectors with different privilege requirements:

- `fetch_workspace_evidence.py` needs the tenant **Fabric Administrator** role
  (Scanner API). Token scope `https://api.fabric.microsoft.com/.default`.
- `fetch_workspace_rest.py` needs only a **workspace role** (Admin/Member/
  Contributor) — same token scope, but workspace-scoped endpoints.
- `fetch_item_health.py` queries the **Power BI REST API**
  (`https://api.powerbi.com/v1.0/myorg`) with token scope
  `https://analysis.windows.net/powerbi/api/.default`; a workspace role is
  sufficient to read semantic-model metadata and refresh history.

If credentials are missing or unauthorized, the collector exits non-zero and the
skill falls back to `learn-only` mode, clearly labeling every control `unknown`.

## Workflow

1. **Resolve the target.** Take the workspace id or name. If a name is given,
   resolve it to an id via the REST API in the fetch step. If neither is
   resolvable, stop and report.
2. **Load the rubric.** Read `references/governance-controls.md`. Each control
   has an id, a requirement, an evidence key, and Learn search terms.
3. **Fetch the Learn guidance.** For each control (or the control set as a
   whole), call the Microsoft Learn MCP server `microsoft_docs_search` tool with
   the control's search terms to ground the requirement and capture a citation.
   Follow the existing client pattern in
   `src/workflows/modules/advisor/tools/learn.py` (streamable HTTP, no auth,
   short timeout, non-fatal on error).
4. **Collect live evidence** (`hybrid` mode only). Run
   `scripts/fetch_workspace_evidence.py <workspace>`; it calls the Fabric Admin
   Scanner API and workspace REST API and writes a normalized evidence JSON.
   When `--evidence PATH` is given, load that file instead and skip the call.
5. **Score each control.** Run `scripts/validate_governance.py` with the rubric
   and the evidence. For each control emit `pass` / `fail` / `unknown` with the
   observed value, the requirement, the Learn citation, and a remediation
   pointer. `unknown` whenever evidence for that control is absent.
6. **Emit the report.** Produce the markdown report (or JSON) using the output
   contract below. Always state the overall score and the count by verdict.

For `learn-only` mode, run steps 1–3 and 6 only; mark every control `unknown`.

## Scripts

| Script | Purpose |
|---|---|
| `scripts/fetch_workspace_evidence.py` | **Tenant-admin** collector. Calls the Admin Scanner API (`admin/workspaces/getInfo` with `getArtifactUsers=True`) for the fullest evidence (roles, labels, endorsement, domain, capacity, items, and per-item owner + direct grants). Requires the **Fabric Administrator** role. |
| `scripts/fetch_workspace_rest.py` | **Non-admin** collector. Uses workspace-scoped REST (`/v1/workspaces/{id}`, `/roleAssignments`, `/items`, `/git/connection`, `/deploymentPipelines`), callable by a workspace Admin/Member. Covers roles, capacity, description, Git, deployment pipeline, and sensitivity labels. |
| `scripts/fetch_item_health.py` | **Item health** collector (Power BI REST API). For each semantic model: publisher (`configuredBy`), creation date, and the last refresh (status, time, error). Use `--merge evidence.json` to fold it into an existing evidence file. Feeds `refresh-health`, `refresh-recency`, and the model-health inventory. |
| `scripts/validate_governance.py` | Pure scorer. Joins the control rubric with the evidence JSON and emits findings (markdown or JSON). No network access — deterministic and unit-testable. |

Use `fetch_workspace_evidence.py` when you have tenant-admin rights; otherwise
use `fetch_workspace_rest.py` for a partial-but-real run. Both emit the same
evidence shape, so the scorer is identical.

```bash
# Tenant admin — fullest evidence:
python .github/skills/fabric-governance-validate/scripts/fetch_workspace_evidence.py \
    <workspace-id-or-name> --out evidence.json

# Workspace Admin/Member (no tenant admin) — partial real evidence:
python .github/skills/fabric-governance-validate/scripts/fetch_workspace_rest.py \
    <workspace-id> --out evidence.json

# Score only the controls a workspace role can assess (recommended for non-admins):
python .github/skills/fabric-governance-validate/scripts/validate_governance.py \
    --evidence evidence.json --scope workspace --format markdown

# Add semantic-model refresh + ownership health (Power BI REST), then score:
python .github/skills/fabric-governance-validate/scripts/fetch_item_health.py \
    <workspace-id> --merge evidence.json
python .github/skills/fabric-governance-validate/scripts/validate_governance.py \
    --evidence evidence.json --scope workspace --format markdown

# Score either evidence file (no network):
python .github/skills/fabric-governance-validate/scripts/validate_governance.py \
    --evidence evidence.json --format markdown

# Learn-only checklist (no evidence, every control unknown):
python .github/skills/fabric-governance-validate/scripts/validate_governance.py \
    --learn-only
```

Exit codes: `0` ok · `2` workspace not resolved (or a name matched multiple
workspaces — the candidate ids are printed so you can re-run with a GUID) · `3`
unauthorized / missing credentials · `4` evidence file not found or invalid.

## Output contract

Always include these sections:

```markdown
# Fabric governance: <workspace name> (<workspace id>)

## Summary

Mode: <hybrid|learn-only> · Score: <pass>/<total> controls
Verdicts: <n> pass · <n> fail · <n> unknown

## Controls

| Control | Verdict | Observed | Requirement | Source |
|---|---|---|---|---|
| <id> | pass/fail/unknown | <observed value> | <one-line requirement> | <Learn citation> |

## Gaps and remediation

<for each fail/unknown: what is missing and the smallest fix, with the Learn link>

## Semantic model health

<present only when fetch_item_health evidence is merged; one row per semantic model>

| Model | Publisher | Last refresh | Status | Error |
|---|---|---|---|---|
| <name> | <configuredBy> | <endTime or —> | <✅/❌ status> | <error code or —> |

## Object ownership

<present only when Scanner evidence carries per-item owners; one row per item>

| Item | Type | Owner | Direct grants |
|---|---|---|---|
| <name> | <type> | <owner UPN or ⚠️ none> | <count of direct user grants> |

## Evidence provenance

<how evidence was collected: Scanner API timestamp, or "learn-only — no evidence">

## Next step

<smallest useful next action>
```

## Finding shape

```json
{
  "control_id": "sensitivity-labels",
  "verdict": "fail",
  "observed": "3 of 12 items labeled",
  "requirement": "All items carry a sensitivity label",
  "evidence_key": "items[].sensitivityLabel",
  "learn_citation": "https://learn.microsoft.com/fabric/governance/...",
  "remediation": "Apply default labels via tenant policy; label the 9 unlabeled items"
}
```

## Anti-patterns

- Do not assert compliance from the Learn rubric alone — without evidence every
  control is `unknown`, not `pass`.
- Do not hardcode a bearer token or PAT; use `DefaultAzureCredential` only.
- Do not treat a missing evidence key as `pass`. Absence of evidence is
  `unknown`, never a silent pass.
- Do not modify any tenant or workspace setting. This skill is read-only.
- Do not log raw tokens, full Scanner payloads, or user PII (emails, object ids)
  without redaction.
- Do not invent Learn citations. Only cite URLs returned by the Learn MCP call;
  if the search returns nothing, mark the citation `unverified`.

## See also

- `src/workflows/modules/advisor/tools/learn.py` — the canonical Learn MCP
  client pattern this skill reuses.
- `metadata-lineage-map` — for data lineage (a different governance concern).
- `references/governance-controls.md` — the editable control rubric.
- `.github/instructions/python.instructions.md` — standards the scripts follow.
