# Fabric permissions model

> **Last validated**: 2026-04-26
> **Confidence**: 0.88

## Three layers

Fabric permissions exist at three nested levels:

```
Tenant (Microsoft Entra)
  └── Workspace roles
       └── Item permissions (per-Lakehouse / per-Warehouse / per-Dataset)
            └── OneLake ACLs (folder/file level, optional)
```

Permissions cascade DOWN with override at each layer. A workspace Admin always sees the workspace's items. Per-item permissions can grant access to users who don't have workspace access.

## Workspace roles

| Role | Read | Write items | Manage members | Delete workspace |
|---|---|---|---|---|
| **Admin** | ✅ | ✅ | ✅ | ✅ |
| **Member** | ✅ | ✅ | ✅ | ❌ |
| **Contributor** | ✅ | ✅ (no share) | ❌ | ❌ |
| **Viewer** | ✅ | ❌ | ❌ | ❌ |

Most users should be **Contributor** for the workspaces they actively edit, **Viewer** for ones they consume from. Member adds sharing rights — useful for team leads.

Default for a service principal building agents / pipelines: **Contributor** + per-item **Build** permission on datasets it needs to refresh.

## Item-level permissions

Per-item permissions narrow workspace access. Common patterns:

### Lakehouse / Warehouse
| Permission | Capabilities |
|---|---|
| Read | Query SQL endpoint, read tables/files |
| ReadAll | Read + access OneLake files via the API directly |
| Write | Insert / update / delete (Warehouse) or write to Files area (Lakehouse) |
| Share | Grant the same permission level to others |

### Dataset (semantic model)
| Permission | Capabilities |
|---|---|
| Read | View reports based on it |
| Build | Create new reports / queries on top |
| Reshare | Grant Build / Read to others |
| Write | Modify the model |

For service principal refreshing a dataset:
- **Workspace**: Contributor (or Member)
- **Dataset**: Build (sometimes also Write if the SP modifies parameters)

## OneLake ACLs

Within a Lakehouse's `Files/` folder, you can set folder-level ACLs (POSIX-style: read / write / execute per identity).

```
Lakehouse/Files/
├── public/                    # everyone in workspace
├── finance/                   # only finance role + admins
└── confidential/              # only specific identities
```

Configured via:
- Fabric portal (right-click folder → Manage permissions)
- ABFSS API (programmatic)
- Spark `mssparkutils.fs.modifyAcl(...)`

ACLs add granularity beyond workspace roles. A Contributor of the workspace can be DENIED access to `confidential/` if ACL excludes them.

Caveat: Tables/ folder ACLs — Microsoft generally recommends managing security at table or row level (RLS), not file-level for tables.

## Service principal setup

For a CI / pipeline / agent service:

1. **App registration in Microsoft Entra**
   - Azure portal → Entra → App registrations → New
   - Note the Application (client) ID, Directory (tenant) ID
   - Generate a client secret OR use federated credentials (preferred — no secret to rotate)

2. **Tenant settings (admin)**
   - Power BI admin portal → Tenant settings → "Service principals can use Fabric APIs" → Enabled (specific security groups recommended)
   - "Allow service principals to use Fabric APIs" — same

3. **Workspace access**
   - Workspace → Manage access → Add → search by app name
   - Grant Contributor / Member as appropriate

4. **Item access**
   - On each item the SP needs: per-item permissions (Build on a dataset, etc.)

5. **OneLake access (optional, for direct ABFSS)**
   - Set ACL on the folder if SP needs file-level access beyond what workspace role grants

## Capacity-level admin

Capacity admins can:
- Resize SKU
- Pause / resume
- Set delegated admin
- Throttle / quota workspaces

Workspace admins can't override capacity admins.

## Domain governance (enterprise)

Domains add:
- Default domain for new workspaces
- Domain admin role (governs all workspaces in domain)
- Sensitivity label propagation
- Discoverability tagging

Used in larger orgs; small projects skip this.

## RLS / OLS (in semantic models)

RLS = Row-Level Security on a semantic model. Set up via TMDL roles + USERPRINCIPALNAME() / USERNAME() — see `powerbi-tmdl-specialist` KB.

For Fabric: same model. RLS enforces at query time regardless of how the user reaches the model (Power BI report, REST API, XMLA endpoint, SQL endpoint queries via `EVALUATE`).

OLS (Object-Level Security) hides entire tables / columns from a role. Combine with RLS for full security.

## Sharing patterns

### Pattern A: each team has its own workspace
- Workspace = team boundary
- Cross-team data sharing via shortcuts to other workspaces
- Permissions managed per workspace

Best for: clear team ownership, independent capacities.

### Pattern B: dev / test / prod workspaces per product
- Three workspaces: `MyApp-dev`, `MyApp-test`, `MyApp-prod`
- Service principal pipelines push to test → prod
- End users have Viewer on prod, Contributor on dev

Best for: software-engineering style data platforms.

### Pattern C: domain → many workspaces
- Sales domain has Sales-Forecasting, Sales-Pipeline, Sales-Reporting workspaces
- Domain admin governs all
- Cross-workspace shortcuts for shared dimensions

Best for: enterprise rollouts.

## Common bugs

- Tenant setting blocks service principals — tickets pile up
- Service principal added to workspace but missing per-dataset Build → refresh API returns 401
- User has workspace Viewer but tries to query SQL endpoint and write — fails (read-only role)
- Shortcut points to a source the consumer doesn't have access to — silent empty results
- ACLs on Lakehouse Tables/ folder cause inconsistent behavior — manage at table / RLS level instead
- Capacity scale change requires capacity admin (not workspace admin)
- "All Members" group has Admin role on a workspace — anyone who joins gets full control

## Audit and compliance

Fabric integrates with Microsoft Purview:
- Sensitivity labels propagate from source to consumer
- Lineage tracking across notebooks / pipelines / datasets
- Audit log: who accessed what, when

For compliance-sensitive deployments, enable Purview integration in the tenant settings.

## See also

- `concepts/fabric-workspace-and-capacity.md`
- `concepts/onelake-and-shortcuts.md` — ACL inheritance
- `concepts/semantic-model-rest-api.md` — auth for SPs
- `anti-patterns.md` (items 1, 2, 10, 15)
