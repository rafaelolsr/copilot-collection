# Microsoft Foundry Knowledge Base — Index

> **Last validated**: 2026-04-26
> **Confidence**: 0.90
> **Scope**: Foundry Agent Service, Foundry IQ, azure-ai-projects SDK, Microsoft Agent Framework, Fabric Data Agents, tools, threads, runs, evals, tracing.

## KB Structure

### Concepts

| File | Topic | Status |
|---|---|---|
| `concepts/foundry-agent-service.md` | Foundry Agent Service (GA) — agents, threads, runs, lifecycle | Validated |
| `concepts/foundry-iq.md` | Foundry IQ — agentic retrieval, knowledge bases, ACLs, citations | Validated |
| `concepts/azure-ai-projects-sdk.md` | azure-ai-projects Python SDK (2.1.0+) — client init, auth, versioning | Validated |
| `concepts/microsoft-agent-framework.md` | Microsoft Agent Framework — executors, workflows, state, events | Validated |
| `concepts/fabric-data-agent.md` | Microsoft Fabric Data Agent — NL-to-SQL/DAX, ontologies, SDK, external clients | Validated |
| `concepts/tools-and-integration.md` | Tool types — function, file_search, code_interpreter, MCP, connected agents | Validated |
| `concepts/evaluation-and-tracing.md` | Evaluations (coherence, relevance, groundedness, safety) + OpenTelemetry tracing | Validated |

### Patterns

| File | Topic |
|---|---|
| `patterns/agent-lifecycle.md` | Create agent → create thread → run → poll → extract messages |
| `patterns/foundry-iq-setup.md` | Wire Foundry IQ KB with sources (SharePoint, Blob, AI Search, Web) |
| `patterns/connected-agents.md` | Multi-agent communication ≤2 levels deep |
| `patterns/mcp-tool-integration.md` | MCP tool registration with approval policies |
| `patterns/otel-tracing-setup.md` | OpenTelemetry + Azure Monitor for production agents |
| `patterns/fabric-data-agent-setup.md` | Create, configure, publish a Fabric Data Agent with SDK |

### Reference

| File | Topic |
|---|---|
| `anti-patterns.md` | 20 anti-patterns to flag on sight |

## Reading Protocol

1. Start here (`index.md`) to identify relevant files.
2. Read matching concept files for background.
3. Read matching pattern files for code templates.
4. Check `anti-patterns.md` when reviewing code.
5. If any file has `last_validated` older than 90 days, use `web` tool to re-validate against https://learn.microsoft.com/en-us/azure/foundry/.
