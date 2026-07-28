# Fabric governance control rubric

The control set this skill scores against. Each control has:

- **id** — stable kebab-case key.
- **requirement** — the documented "should".
- **evidence_key** — where to find the live value in the evidence JSON
  (dot/bracket path, e.g. `items[].sensitivityLabel`).
- **learn_terms** — query passed to the Microsoft Learn MCP
  `microsoft_docs_search` tool to ground the requirement and capture a citation.
- **scope** — `workspace` (evaluable from a workspace role via
  `fetch_workspace_rest.py`) or `tenant` (needs the Fabric Admin Scanner API via
  `fetch_workspace_evidence.py`). Use `validate_governance.py --scope workspace`
  to score only the workspace-evaluable subset.
- **severity** — `high` / `medium` / `low`, used to order gaps in the report.

Controls are intentionally editable. Add, remove, or retune them per tenant
policy. The scorer in `scripts/validate_governance.py` loads the same set from
`scripts/_controls.py`; keep the two in sync when you change a control.

## Access and identity

| id | severity | requirement | evidence_key | learn_terms |
|---|---|---|---|---|
| `workspace-admin-count` | high | At least 2 and no more than 5 workspace Admins (avoid single-owner and over-grant). | `roles.admin_count` | "Microsoft Fabric workspace roles least privilege admin" |
| `least-privilege-roles` | high | No user holds a broader role than needed; Viewer/Member preferred over Admin for non-owners. | `roles.assignments` | "Microsoft Fabric workspace roles Member Contributor Viewer" |
| `no-guest-access` | high | No external / guest (B2B) users hold workspace roles unless explicitly approved. | `roles.guest_count` | "Microsoft Fabric external guest user access governance" |
| `service-principal-control` | medium | Service principals with workspace access are inventoried and scoped. | `roles.service_principal_count` | "Microsoft Fabric service principal workspace access" |
| `object-ownership` | high | Every item has an identifiable owner — no orphaned objects (Scanner-only / `tenant` scope). | `items[].owner` | "Microsoft Fabric item ownership take over orphaned dataset owner" |

## Information protection

| id | severity | requirement | evidence_key | learn_terms |
|---|---|---|---|---|
| `sensitivity-labels` | high | Every item carries a Microsoft Purview sensitivity label. | `items[].sensitivityLabel` | "Microsoft Fabric sensitivity labels Purview information protection" |
| `dlp-coverage` | medium | Data loss prevention policies apply to the workspace's semantic models. | `workspace.dlpEnabled` | "Microsoft Fabric data loss prevention policy Power BI" |

## Organization and discoverability

| id | severity | requirement | evidence_key | learn_terms |
|---|---|---|---|---|
| `domain-assignment` | medium | The workspace is assigned to a Fabric domain (data mesh). | `workspace.domainId` | "Microsoft Fabric domains data mesh assign workspace" |
| `endorsement` | medium | Production semantic models / reports are Promoted or Certified. | `items[].endorsement` | "Microsoft Fabric endorsement certified promoted content" |
| `workspace-metadata` | low | Workspace has a description and a designated contact. | `workspace.description` | "Microsoft Fabric workspace settings description contact" |

## Lifecycle and change control

| id | severity | requirement | evidence_key | learn_terms |
|---|---|---|---|---|
| `deployment-pipeline` | high | The workspace participates in a dev/test/prod deployment pipeline. | `workspace.deploymentPipelineId` | "Microsoft Fabric deployment pipelines lifecycle management" |
| `git-integration` | medium | The workspace is connected to Git source control. | `workspace.gitConnected` | "Microsoft Fabric Git integration source control workspace" |

## Capacity and monitoring

| id | severity | requirement | evidence_key | learn_terms |
|---|---|---|---|---|
| `capacity-assignment` | high | The workspace is on a dedicated Fabric capacity (not shared/Pro-only for production). | `workspace.capacityId` | "Microsoft Fabric capacity assign workspace governance" |

## Operational health

Populated by `fetch_item_health.py` (Power BI REST API). Workspace-scoped.

| id | severity | requirement | evidence_key | learn_terms |
|---|---|---|---|---|
| `refresh-health` | high | No semantic model's last scheduled/manual refresh ended in failure. | `semantic_models[].lastRefresh.status` | "Power BI semantic model refresh failure troubleshoot" |
| `refresh-recency` | medium | Every refreshable semantic model refreshed within the recency window (default 1 day). | `semantic_models[].lastRefresh.endTime` | "Power BI dataset scheduled refresh frequency governance" |

## Scoring rules

- `pass` — evidence present and meets the requirement.
- `fail` — evidence present and violates the requirement.
- `unknown` — evidence key absent or null. Never treat absence as pass.
- Overall score = count(`pass`) / count(all controls). Report verdict counts
  separately so `unknown` is never hidden inside the denominator narrative.
- Order the gaps section by `severity` (high first), then by control id.

## Citations

Citations come only from the Learn MCP `microsoft_docs_search` response for each
control's `learn_terms`. If the search returns nothing, mark the citation
`unverified` — never fabricate a URL.
