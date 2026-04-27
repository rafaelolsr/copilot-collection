# Pattern: Foundry IQ Knowledge Base Setup

> Wire a Foundry IQ KB with data sources and attach to an agent.

## Blob Storage Source

```python
import os
from azure.identity import DefaultAzureCredential
from azure.ai.projects import AIProjectClient

credential = DefaultAzureCredential()
client = AIProjectClient(
    credential=credential,
    project_connection_string=os.getenv("AZURE_AI_PROJECT_CONNECTION_STRING"),
)

# Create knowledge base
kb = client.knowledge_bases.create(display_name="product-docs")

# Add Blob Storage source
client.knowledge_bases.add_source(
    kb.id,
    source_type="blob_storage",
    source_config={
        "connection_string": os.getenv("BLOB_CONNECTION_STRING"),
        "container_name": "documentation",
    },
)

# Create agent with KB
agent = client.agents.create_agent(
    model=os.getenv("MODEL_DEPLOYMENT_NAME"),
    name="doc-assistant",
    instructions="Answer questions using the product documentation.",
    knowledge_bases=[kb.id],  # [PREVIEW: Foundry IQ — verify GA status]
)
```

## SharePoint Source (Automatic ACL)

```python
client.knowledge_bases.add_source(
    kb.id,
    source_type="sharepoint",
    source_config={
        "site_url": "https://contoso.sharepoint.com/sites/engineering",
        "document_library": "Shared Documents",
    },
)
# ACL is automatic — users only see documents they have Entra ID permissions for
```

## Azure AI Search Source

```python
client.knowledge_bases.add_source(
    kb.id,
    source_type="ai_search",
    source_config={
        "endpoint": os.getenv("SEARCH_ENDPOINT"),
        "index_name": "product-index",
    },
)
```

## Web Source

```python
client.knowledge_bases.add_source(
    kb.id,
    source_type="web",
    source_config={
        "urls": [
            "https://docs.contoso.com/api-reference",
            "https://docs.contoso.com/getting-started",
        ],
    },
)
```

## Security Checklist

- [ ] SharePoint sources: ACL is automatic (verify permissions)
- [ ] Blob sources: configure document-level ACL in index
- [ ] AI Search sources: verify existing ACL configuration
- [ ] Test with different user roles to confirm access boundaries
- [ ] [PREVIEW] stamp added to all Foundry IQ code
- [ ] Fallback to classic RAG with AI Search documented
