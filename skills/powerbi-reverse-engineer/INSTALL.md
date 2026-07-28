# Install — powerbi-reverse-engineer skill

This skill reverse-engineers Power BI semantic models (Import + DirectQuery) and
helps you move the data into a Microsoft Fabric Lakehouse. It is **read-only**
against your models.

## 1. Install the skill

Unzip so the `powerbi-reverse-engineer/` folder lands in a skills directory
Copilot scans.

**Personal (all repos) — recommended for sharing:**

- **Windows (PowerShell):**
  ```powershell
  Expand-Archive -Path "$HOME\Downloads\powerbi-reverse-engineer-skill.zip" `
    -DestinationPath "$HOME\.copilot\skills\" -Force
  ```
  Result: `C:\Users\<you>\.copilot\skills\powerbi-reverse-engineer\SKILL.md`

- **macOS / Linux:**
  ```bash
  unzip -o ~/Downloads/powerbi-reverse-engineer-skill.zip -d ~/.copilot/skills/
  ```

**Project (shared via a repo):** place the `powerbi-reverse-engineer/` folder
under the repo's `.github/skills/`. Anyone who clones the repo gets it.

Restart Copilot CLI, then run `/skills` (or `/env`) to confirm it is loaded.

## 2. Install the required MCP (`powerbi-modeling-mcp`)

Only one MCP is needed, and **only for live extraction** (exporting TMDL or
validating DirectQuery SQL/DAX). Most of the skill runs offline from an exported
TMDL folder.

### Prerequisite — Node.js (provides `npx`)

```powershell
winget install OpenJS.NodeJS.LTS
node -v   # confirm a version prints
```

The server is fetched by `npx` on first launch — no separate build.

### Register it in Copilot CLI

Run `/mcp` and add a **stdio** server (command `npx`, args
`-y @microsoft/powerbi-modeling-mcp@latest --start`), or add this block to
`%USERPROFILE%\.copilot\mcp-config.json` (`~/.copilot/mcp-config.json` on
macOS/Linux):

```jsonc
{
  "mcpServers": {
    "powerbi-modeling-mcp": {
      "type": "stdio",
      "command": "npx",
      "args": ["-y", "@microsoft/powerbi-modeling-mcp@latest", "--start"],
      "tools": ["*"]
    }
  }
}
```

> ⚠️ Add **only** this block. Do not copy a colleague's whole `mcp-config.json`
> — other entries may contain plaintext secrets.

### VS Code alternative

Install the **"Power BI Modeling MCP"** Marketplace extension; it registers the
server for Copilot in VS Code automatically.

### Verify

```powershell
npx -y @microsoft/powerbi-modeling-mcp@latest --help
```

Then connect to a model:

```text
Connect to '<file>' in Power BI Desktop                 # Windows-only (Desktop)
Connect to semantic model '<Model>' in Fabric Workspace '<WS>'
Open semantic model from PBIP folder '<path>/definition'
```

## 3. Read-only safety (important)

The MCP **can modify** models and has **no `--readonly` flag**. The skill keeps
models untouched through policy:

1. Prefer **offline extraction** from an exported TMDL copy.
2. **Never** start the MCP with `--skipconfirmation`; decline every write prompt.
3. **Prove it** — snapshot the TMDL before/after with
   `scripts/readonly_evidence.py` and assert the digest is unchanged.

## 4. Run it

Ask Copilot, e.g.:

> *Reverse engineer my Power BI dashboards in `<path>/definition` and design a
> Fabric one-big-table; show me the data-access & ingestion guide.*

The scripts are **stdlib-only Python 3** — run with `python` on Windows, no
`pip install` required.

## What's in the package

```
powerbi-reverse-engineer/
  SKILL.md                                   workflow (7 phases + read-only enforcement)
  references/
    mcp-extraction-playbook.md               per-case MCP prompts & tool calls
    consolidation-design.md                  grain / conformance / lineage rules
    data-access-and-ingestion.md             access map + bronze ingestion plan
    report-sections.md                       archflow report section contract
  scripts/
    extract_query_registry.py                TMDL → query registry (JSON/CSV)
    extract_model_semantics.py               TMDL → measures / relationships / RLS
    generate_access_ingestion_guide.py       registry → Markdown access/ingestion guide
    readonly_evidence.py                     before/after TMDL hash proof
```
