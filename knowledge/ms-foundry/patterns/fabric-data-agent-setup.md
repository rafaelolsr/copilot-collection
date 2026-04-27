# Pattern: Fabric Data Agent Setup

> Create, configure, and publish a Fabric Data Agent programmatically.

## In-Fabric Creation (Notebook SDK)

The `fabric-data-agent-sdk` runs **inside Microsoft Fabric notebooks only**.

```python
# Install SDK in Fabric notebook
%pip install -U fabric-data-agent-sdk

from fabric.dataagent.client import create_data_agent, delete_data_agent

# 1. Create agent
agent = create_data_agent("product_analytics_agent")

# 2. Add data source (Lakehouse)
agent.add_datasource("SalesLakehouse", type="lakehouse")

# 3. Select specific tables (limit scope for accuracy)
datasource = agent.get_datasources()[0]
for table in ["factorders", "dimcustomer", "dimproduct", "dimdate"]:
    datasource.select("dbo", table)

# 4. Set instructions (domain-specific)
agent.set_instructions("""
Answer questions about product orders and customer trends.
Use factorders for revenue and order metrics.
Use dimcustomer for customer segmentation.
Use dimdate for time-based analysis.
When asked about "top products," rank by total revenue from factorders.
""")

# 5. Set user-facing description
agent.set_user_description("Product and customer analytics assistant")

# 6. Publish
agent.publish()
```

## External Consumption (Outside Fabric)

```python
# Install SDK
# pip install fabric-data-agent-sdk
# Or clone: https://github.com/microsoft/fabric_data_agent_client

import os
os.environ["TENANT_ID"] = "<your-tenant-id>"
os.environ["DATA_AGENT_URL"] = "<your-agent-url>"

from fabric_data_agent_client import FabricDataAgentClient

# Uses InteractiveBrowserCredential (Microsoft Entra ID)
client = FabricDataAgentClient()

# Ask questions
result = client.ask("What were total sales in Q1 2026?")
print(result)

# Follow-up (multi-turn)
result = client.ask("Break that down by product category")
print(result)
```

## Ontology-Based Agent

```python
# In a Fabric notebook
# 1. Create ontology (define entities, relationships, data bindings)
# 2. Create agent with ontology as source

agent = create_data_agent("healthcare_agent")
agent.add_datasource("HospitalOntology", type="ontology")

agent.set_instructions("""
Provide hospital staff with occupancy and patient analytics.
Map "ICU bed availability" to count of unoccupied beds in ICU rooms.
Map "department" to the Department entity.
When asked about equipment, query the MedicalEquipment entity.
""")

agent.set_user_description("Hospital operations analytics")
agent.publish()
```

## Configuration Best Practices

### Instructions Template

```
Purpose: [What this agent does]
Data relationships: [Key table joins and relationships]
Domain terminology:
  - "[Business term]" → [Table.Column]
  - "[Business term]" → [Entity in ontology]
Example queries:
  - Q: "[Sample question]" → Use [table/entity] with [filter]
```

### Table Selection

- **≤25 tables per source** — fewer tables = more precise queries
- Only include tables the agent needs
- Use descriptive table/column names (rename cryptic columns)

## Cleanup

```python
from fabric.dataagent.client import delete_data_agent
delete_data_agent("product_analytics_agent")
```

## Checklist

- [ ] Agent has specific, focused purpose (not generic)
- [ ] Instructions include domain terminology and examples
- [ ] Tables limited to relevant subset (≤25)
- [ ] Tested with real-world questions before publishing
- [ ] Security boundaries verified (workspace permissions)
- [ ] User description set for discoverability
