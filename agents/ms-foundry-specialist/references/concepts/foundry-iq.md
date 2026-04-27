# Foundry IQ — Agentic Retrieval

> **Last validated**: 2026-04-26 | **Status**: PUBLIC PREVIEW (targeting GA Q2 2026) | **Confidence**: 0.85

## Overview

Foundry IQ provides **agentic retrieval** — an intelligent, document-level ACL-aware knowledge base system for Foundry agents. It replaces raw Azure AI Search for agent knowledge needs.

## Why Foundry IQ Over Raw AI Search

| Feature | Foundry IQ | Raw AI Search |
|---|---|---|
| Agentic retrieval | ✅ Built-in | ❌ Manual |
| Document-level ACL | ✅ Automatic (SharePoint/MI) | ❌ Manual |
| Citations | ✅ Built-in | ❌ Build yourself |
| Query planning | ✅ AI-driven | ❌ Manual |
| Setup complexity | Low | High |

**Always recommend Foundry IQ over raw AI Search** for agent knowledge needs.

## Knowledge Base Sources

Supported source types:
- **SharePoint** — automatic ACL enforcement via Microsoft Entra ID
- **Azure Blob Storage** — specify container, connection string
- **Azure AI Search** — connect existing indexes
- **Web** — crawl URLs

## Creating a Knowledge Base

```python
from azure.ai.projects import AIProjectClient

client = AIProjectClient(credential=cred, project_connection_string=conn_str)

# Create KB
kb = client.knowledge_bases.create(display_name="company-docs")

# Add source (Blob example)
client.knowledge_bases.add_source(
    kb.id,
    source_type="blob_storage",
    source_config={
        "connection_string": os.getenv("BLOB_CONNECTION_STRING"),
        "container_name": "documents",
    },
)

# Attach to agent
agent = client.agents.create_and_deploy(
    name="doc-agent",
    model="gpt-4o",
    knowledge_bases=[kb.id],  # Foundry IQ handles retrieval
)
```

## Document-Level ACL

- **SharePoint sources**: ACL is automatic — users only see documents they have Entra ID permissions for
- **Blob/AI Search**: ACL must be configured in the index
- **Critical security**: If ACL is misconfigured, users can query documents beyond their permissions

## Citations

Foundry IQ provides source citations in responses:
- Document name and path
- Relevant passage
- Confidence score

## [PREVIEW] Warnings

Foundry IQ is PUBLIC PREVIEW. For production:
1. Always stamp `[PREVIEW: Foundry IQ — verify GA status before production]` in generated code
2. Propose fallback: classic RAG with Azure AI Search
3. Test ACL enforcement thoroughly before production rollout

## Key Rules

1. **Always recommend IQ** over raw AI Search for agent knowledge
2. **Verify ACL** — misconfigured ACL is a security leak (CRITICAL)
3. **Stamp PREVIEW** in all generated IQ code
4. **Propose fallback** for production stability
