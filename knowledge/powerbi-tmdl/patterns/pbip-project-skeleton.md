# PBIP project skeleton (minimum viable)

> **Last validated**: 2026-04-26
> **Confidence**: 0.90

## When to use this pattern

Starting a new PBIP project. Provides the minimum file set Power BI Desktop will accept, ready to commit to git.

## Bootstrap script (bash)

```bash
#!/usr/bin/env bash
set -euo pipefail

PROJECT_NAME="${1:?Usage: $0 <project-name>}"
ROOT="$PROJECT_NAME"

mkdir -p "$ROOT/$PROJECT_NAME.SemanticModel/definition/tables"
mkdir -p "$ROOT/$PROJECT_NAME.SemanticModel/definition/cultures"
mkdir -p "$ROOT/$PROJECT_NAME.Report/definition/pages"
mkdir -p "$ROOT/$PROJECT_NAME.Report/StaticResources/SharedResources/BaseThemes"

# Project root marker
cat > "$ROOT/$PROJECT_NAME.pbip" <<EOF
{
  "version": "1.0",
  "artifacts": [
    { "report": { "path": "$PROJECT_NAME.Report" } }
  ],
  "settings": {
    "enableAutoRecovery": true
  }
}
EOF

# Semantic Model marker
cat > "$ROOT/$PROJECT_NAME.SemanticModel/definition.pbism" <<'EOF'
{ "version": "4.0" }
EOF

# Model file
cat > "$ROOT/$PROJECT_NAME.SemanticModel/definition/model.tmdl" <<'EOF'
model Model
    culture: en-US
    defaultPowerBIDataSourceVersion: powerBI_V3
    sourceQueryCulture: en-US
    dataAccessOptions
        legacyRedirects
        returnErrorValuesAsNull
EOF

# Database file
cat > "$ROOT/$PROJECT_NAME.SemanticModel/definition/database.tmdl" <<'EOF'
database
    compatibilityLevel: 1567
EOF

# Empty relationships file
touch "$ROOT/$PROJECT_NAME.SemanticModel/definition/relationships.tmdl"

# Culture file
cat > "$ROOT/$PROJECT_NAME.SemanticModel/definition/cultures/en-US.tmdl" <<'EOF'
cultureInfo en-US

linguisticMetadata = ```
{
  "Version": "1.0.0",
  "Language": "en-US"
}
```
contentType: json
EOF

# Date table (every model should have one)
cat > "$ROOT/$PROJECT_NAME.SemanticModel/definition/tables/DateTable.tmdl" <<'EOF'
table DateTable
    dataCategory: Time

    column Date
        dataType: dateTime
        isKey: true
        formatString: yyyy-mm-dd
        sourceColumn: Date
        dataCategory: PaddedDateTableDates
        summarizeBy: none

    column Year
        dataType: int64
        sourceColumn: Year
        summarizeBy: none

    column Month
        dataType: string
        sourceColumn: Month
        summarizeBy: none

    column MonthNumber
        dataType: int64
        sourceColumn: MonthNumber
        summarizeBy: none

    sortByColumn Month = MonthNumber

    partition DateTable = m
        mode: import
        source = ```
            let
                Source = #date(2020, 1, 1),
                EndDate = #date(2030, 12, 31),
                DayCount = Duration.Days(EndDate - Source) + 1,
                Dates = List.Dates(Source, DayCount, #duration(1, 0, 0, 0)),
                DatesTable = Table.FromList(Dates, Splitter.SplitByNothing(), {"Date"}),
                Typed = Table.TransformColumnTypes(DatesTable, {{"Date", type date}}),
                WithYear = Table.AddColumn(Typed, "Year", each Date.Year([Date]), Int64.Type),
                WithMonth = Table.AddColumn(WithYear, "Month", each Date.ToText([Date], "MMM"), type text),
                WithMonthNumber = Table.AddColumn(WithMonth, "MonthNumber", each Date.Month([Date]), Int64.Type)
            in
                WithMonthNumber
        ```
EOF

# Report marker
cat > "$ROOT/$PROJECT_NAME.Report/definition.pbir" <<EOF
{
  "version": "1.0",
  "datasetReference": {
    "byPath": { "path": "../$PROJECT_NAME.SemanticModel" }
  }
}
EOF

# Empty report definition
cat > "$ROOT/$PROJECT_NAME.Report/definition/report.json" <<'EOF'
{
  "config": "{\"version\":\"5.43\",\"themeCollection\":{\"baseTheme\":{\"name\":\"BaseThemes/CY24SU02.json\"}}}"
}
EOF

cat > "$ROOT/$PROJECT_NAME.Report/definition/pages/pages.json" <<'EOF'
{
  "pageOrder": [],
  "activePageName": ""
}
EOF

# .gitignore
cat > "$ROOT/.gitignore" <<'EOF'
**/.pbi/localSettings.json
**/.pbi/cache/
~$*.pbix
.vscode/
.idea/
.DS_Store
Thumbs.db
EOF

echo "Created PBIP project at: $ROOT/"
echo "Open '$ROOT/$PROJECT_NAME.pbip' in Power BI Desktop."
```

Usage:

```bash
chmod +x bootstrap-pbip.sh
./bootstrap-pbip.sh sales-dashboard
cd sales-dashboard
git init
git add .
git commit -m "Initial PBIP scaffold"
```

## What this gives you

- A minimal but valid PBIP project that opens in Power BI Desktop
- A pre-built date table with year/month columns and a sort-by relationship
- Empty `relationships.tmdl` ready for additions
- A culture file (en-US — change to your locale if needed)
- A `.gitignore` excluding per-user state

## Adding a fact table

Once Power BI Desktop opens the project, use the UI to:
1. Get Data → connect to your source
2. Load the table
3. Save → Power BI Desktop writes a `Sales.tmdl` (or whatever you named it) under `definition/tables/`
4. Add the relationship in the Modeling view (it appends to `relationships.tmdl`)

Or write the TMDL directly (see `patterns/tmdl-table-with-relationships.md`) and reload the project.

## Verifying the project

After bootstrap:

```bash
# Open in Desktop — should not error
# In Tabular Editor (optional): Open → File → select definition.pbism

# Validate TMDL syntax (Tabular Editor CLI)
tabularEditor.cmd "$PROJECT_NAME.SemanticModel" -V

# Lint for whitespace / line endings
find "$PROJECT_NAME.SemanticModel" -name '*.tmdl' -exec file {} \;
# Should print "ASCII text" — if "with CRLF" appears, fix line endings:
find "$PROJECT_NAME.SemanticModel" -name '*.tmdl' -exec dos2unix {} \;
```

## Common bugs

- Forgot to escape `$` in heredoc → variable expansion broke literal `$` in JSON
- LF line endings missing on Windows-edited files
- `compatibilityLevel` too low for newer features — current default is 1567
- `byPath` path wrong (semantic model folder renamed but `definition.pbir` not updated)
- Committed `.pbi/localSettings.json` despite .gitignore (already tracked) — use `git rm --cached`

## See also

- `concepts/pbip-project-structure.md` — what each file does
- `concepts/tmdl-syntax.md` — TMDL formatting rules
- `patterns/tmdl-table-with-relationships.md` — adding fact tables
- `patterns/xmla-deployment-via-tabular-editor.md` — deploying this project
