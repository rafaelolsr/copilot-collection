# Microsoft Fabric Data Agent

> **Last validated**: 2026-04-26 | **Status**: GA | **Confidence**: 0.88

## Overview

Microsoft Fabric Data Agents are AI-powered assistants embedded in Microsoft Fabric that translate natural language questions into SQL, DAX, or KQL queries. They query Lakehouses, Warehouses, Power BI semantic models, and KQL databases to provide structured, secure, and governance-aware answers.

## Key Capabilities

- **Natural Language to SQL/DAX/KQL**: Users ask questions in plain English; the agent generates and executes queries
- **Multi-source Connectivity**: Up to 5 data sources per agent (Lakehouse, Warehouse, Power BI semantic model, KQL database)
- **Enterprise Security**: Honors Microsoft Purview DLP, access restrictions, and data governance
- **Ontology Support**: Ground agents in business-specific ontologies for richer entity relationships
- **No Azure OpenAI Key Required**: Authentication and LLM access are fully managed by Fabric
- **Conversational**: Multi-turn follow-up support with context awareness

## Prerequisites

- **Fabric capacity**: F2 or higher, or Power BI Premium Per Capacity (P1+)
- **Tenant settings**: Fabric Data Agent and Copilot tenant settings enabled
- **Data source**: At least one supported source (Lakehouse, Warehouse, semantic model, KQL DB)

## Creating a Data Agent (Portal)

1. Open Microsoft Fabric workspace at `https://app.fabric.microsoft.com`
2. Click **+ New** → **Data Agent** → assign a name
3. Select up to 5 data sources and specify accessible tables/columns
4. Add **Instructions**: describe the agent's purpose, key data relationships, domain terminology
5. Add **Example Questions**: sample queries with expected SQL/DAX to guide the model
6. Configure security/governance settings
7. Test interactively with real-world questions
8. **Publish** and share with colleagues or embed in Power BI

## Creating a Data Agent (Python SDK — Fabric Notebooks)

The `fabric-data-agent-sdk` runs **inside Fabric notebooks** (not local Python).

```python
# Install SDK
%pip install -U fabric-data-agent-sdk

from fabric.dataagent.client import create_data_agent

# Create agent
data_agent = create_data_agent("sales_insights_agent")

# Add data source (Lakehouse)
data_agent.add_datasource("SalesLakehouse", type="lakehouse")

# Select specific tables
datasource = data_agent.get_datasources()[0]
tables = ["dimcustomer", "dimdate", "dimproduct", "factinternetsales"]
for table in tables:
    datasource.select("dbo", table)

# Set instructions and description
data_agent.set_instructions(
    "Answer questions about sales performance. "
    "Use factinternetsales for revenue metrics, "
    "dimcustomer for customer segmentation."
)
data_agent.set_user_description("Sales analytics assistant")

# Publish
data_agent.publish()
```

### Delete a Data Agent

```python
from fabric.dataagent.client import delete_data_agent
delete_data_agent("sales_insights_agent")
```

## Consuming a Data Agent (External Python Client)

For consuming a published agent from **outside Fabric** (web apps, scripts):

```bash
pip install fabric-data-agent-sdk
# Or clone: https://github.com/microsoft/fabric_data_agent_client
```

```python
from fabric_data_agent_client import FabricDataAgentClient

# Uses InteractiveBrowserCredential (Microsoft Entra ID)
client = FabricDataAgentClient()
result = client.ask("What were total sales in Q1?")
print(result)
```

### Authentication for External Clients

- Uses `InteractiveBrowserCredential` from `azure-identity`
- Opens browser for Microsoft Entra ID sign-in
- Automatic token refresh
- Environment variables: `TENANT_ID`, `DATA_AGENT_URL`

```bash
export TENANT_ID=<your-azure-tenant-id>
export DATA_AGENT_URL=<your-fabric-data-agent-url>
```

> **Note**: Service Principal auth is not yet GA for external SDK usage. Interactive browser auth is the standard as of mid-2026.

## Ontology-Based Data Agents

Ontologies provide a **semantic layer** over raw data, mapping business concepts to tables/columns:

### Why Ontologies

- Richer entity relationships beyond flat tables
- Business-friendly terminology mapping
- More accurate query generation for domain-specific questions

### Configuration

1. Create ontology in a Fabric notebook (`setup-ontology.ipynb`)
2. Define entities, relationships, and data bindings
3. Create Data Agent with ontology as the data source
4. Add domain-specific instructions and terminology

### Example: Healthcare Ontology

**Entities**: Hospital, Department, Patient, Room, MedicalEquipment

**Agent instructions**:
```
Provide hospital staff with occupancy and patient analytics.
When asked "ICU bed availability," return the count of unoccupied beds
in entities tagged as ICU rooms.
Map "department" to the Department entity.
```

**Test question**: "How many open ICU beds are there in Cardiology?"

## Best Practices

### Data Source Configuration

1. **Limit scope** — only expose relevant tables/columns (≤25 tables per source recommended)
2. **Use descriptive names** — AI agents need meaningful table/column names for reliable query generation
3. **Document metadata** — describe every table and column in the semantic model

### Instructions

1. **Be specific** — describe the agent's purpose and key data relationships
2. **Use positive instructions** — "Show X" is better than "Don't show Y"
3. **Include example Q&A pairs** — guide the model for edge cases
4. **Define domain terminology** — map business terms to data entities

### Security

1. **Verify access restrictions** — agent respects Fabric workspace permissions
2. **Enable Purview DLP** if handling sensitive data
3. **Test with different user roles** to verify data access boundaries

### Agent Design

1. **Specialized agents** — one agent per domain/purpose, not generic catch-all
2. **Validate before rollout** — test typical + edge-case questions rigorously
3. **Involve business users** in UAT to capture real workflows

## Relationship to Foundry Agent Service

Fabric Data Agents and Foundry Agent Service are **complementary but separate**:

| | Fabric Data Agent | Foundry Agent Service |
|---|---|---|
| **Purpose** | NL-to-query over Fabric data | General-purpose AI agents |
| **Data sources** | Lakehouse, Warehouse, PBI, KQL | Any (via tools) |
| **Query types** | SQL, DAX, KQL | Free-form LLM output |
| **SDK** | `fabric-data-agent-sdk` | `azure-ai-projects` |
| **Auth** | Fabric workspace permissions | DefaultAzureCredential |
| **Hosting** | Microsoft Fabric | Foundry Agent Service |
| **Ontology** | ✅ Built-in | ❌ Not applicable |

## Anti-Patterns

1. **Generic agent for all data** — too broad, inaccurate results → specialize per domain
2. **No instructions or examples** — agent guesses query intent → always provide guidance
3. **Exposing all tables** — noise reduces accuracy → limit to relevant tables
4. **Skipping UAT** — untested agents produce wrong results → test with real questions
5. **Ignoring security boundaries** — data leakage risk → verify role-based access
6. **Using outside Fabric for creation** — SDK only works in Fabric notebooks for creation
