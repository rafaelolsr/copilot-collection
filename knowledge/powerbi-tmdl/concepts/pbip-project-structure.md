# PBIP project structure

> **Last validated**: 2026-04-26
> **Confidence**: 0.91
> **Source**: https://learn.microsoft.com/en-us/power-bi/developer/projects/

## Why PBIP over PBIX

PBIX is a binary zip. PBIP is a folder of TMDL + JSON. Diff-friendly, source-controllable, scriptable, mergeable. For any project under git, use PBIP.

PBIX is still fine for: ad-hoc analyst reports, one-off dashboards, prototypes never deployed.

## Folder structure

```
my-report/
├── my-report.pbip                              # workspace marker; minimal
├── .gitignore
├── my-report.SemanticModel/
│   ├── definition.pbism                        # model marker
│   ├── definition/
│   │   ├── model.tmdl
│   │   ├── database.tmdl
│   │   ├── relationships.tmdl
│   │   ├── cultures/
│   │   │   └── en-US.tmdl
│   │   └── tables/
│   │       ├── Sales.tmdl
│   │       ├── Customer.tmdl
│   │       └── DateTable.tmdl
│   └── .pbi/
│       └── localSettings.json                  # NOT committed (per-user state)
└── my-report.Report/
    ├── definition.pbir                         # report marker
    ├── definition/
    │   ├── report.json                         # report-level settings
    │   └── pages/
    │       ├── pages.json                      # page order
    │       ├── ReportSection_<guid>/
    │       │   ├── page.json
    │       │   └── visuals/
    │       │       └── <visual_guid>.json
    └── StaticResources/
        └── SharedResources/
            └── BaseThemes/
                └── theme.json
```

## The marker files

### `my-report.pbip` (project root)
```json
{
  "version": "1.0",
  "artifacts": [
    { "report": { "path": "my-report.Report" } }
  ],
  "settings": {
    "enableAutoRecovery": true
  }
}
```

### `my-report.SemanticModel/definition.pbism`
```json
{ "version": "4.0" }
```

### `my-report.Report/definition.pbir`
```json
{
  "version": "1.0",
  "datasetReference": {
    "byPath": { "path": "../my-report.SemanticModel" }
  }
}
```

`byPath` references the local SemanticModel folder. For thin reports against a deployed semantic model, use `byConnection` instead.

## .gitignore

```
# PBIP per-user settings (DO NOT commit)
**/.pbi/localSettings.json
**/.pbi/cache/

# Power BI Desktop temp files
~$*.pbix

# Editor
.vscode/
.idea/
*.swp

# OS
.DS_Store
Thumbs.db
```

`localSettings.json` contains per-user info (last-opened state, server URL caches). Committing it creates merge conflicts every save.

## Connecting to deployed semantic models (thin reports)

Thin reports separate the model from the report. Multiple reports share one model:

```
shared-models/
└── sales-model.SemanticModel/
    └── ...

reports/
├── monthly-sales.Report/
│   └── definition.pbir   # byConnection → sales-model
└── exec-dashboard.Report/
    └── definition.pbir   # byConnection → sales-model
```

In `definition.pbir`:
```json
{
  "version": "1.0",
  "datasetReference": {
    "byConnection": {
      "connectionString": "Data Source=powerbi://api.powerbi.com/v1.0/myorg/<workspace>;Initial Catalog=<dataset name>;",
      "pbiServiceModelId": null,
      "pbiModelVirtualServerName": "sobe_wowvirtualserver",
      "pbiModelDatabaseName": "...",
      "name": "EntityDataSource",
      "connectionType": "pbiServiceXmlaPbiModel"
    }
  }
}
```

Get the connection details from the Power BI Service → Workspace → Settings → Premium → XMLA endpoint.

## Conversion workflow (PBIX → PBIP)

1. Open PBIX in Power BI Desktop
2. **File → Save As → Power BI Project (.pbip)**
3. Commit the resulting folder structure
4. Continue editing in Desktop OR Tabular Editor (model) and Desktop (report)

For models authored in Tabular Editor, edit TMDL files directly. Power BI Desktop and Tabular Editor share the file format.

## Multi-developer workflow

Common pattern for a team:

1. Each developer works on a feature branch
2. Model changes: edit TMDL files in Tabular Editor or VS Code
3. Report changes: edit visuals in Power BI Desktop
4. PR review: TMDL diffs are readable; report JSON diffs are noisier but inspectable
5. Merge to main; CI deploys via XMLA / REST API

Conflicts in TMDL: usually mergeable. Conflicts in `report.json` or visual JSONs: rebuild the affected page (last-writer-wins is the pragmatic strategy).

## What CAN'T be in PBIP yet

Some Power BI Desktop features still serialize to PBIX-only blobs:
- Some custom visuals' state
- Embedded thumbnails
- Some R/Python visuals
- Live-connect cached metadata

Always test the round-trip (PBIP → open → save → diff) before relying on a feature.

## Common bugs

- Committing `.pbi/localSettings.json` → merge conflicts on every save → add to .gitignore
- Mixing PBIX and PBIP files for the same project → confusion
- Editing TMDL while PBIP is open in Desktop → conflicting writes; close one
- Renaming `.SemanticModel/` folder without updating `definition.pbir` reference
- Using `byPath` for production deployments (expects local folder; production uses `byConnection`)

## See also

- `concepts/tmdl-syntax.md` — what's inside `.tmdl` files
- `patterns/pbip-project-skeleton.md` — minimum-viable PBIP
- `patterns/xmla-deployment-via-tabular-editor.md` — deploying PBIP
- `anti-patterns.md` (items 16, 18)
