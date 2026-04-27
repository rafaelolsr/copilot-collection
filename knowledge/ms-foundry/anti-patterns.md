# Anti-Patterns — Flag on Sight

> **Last validated**: 2026-04-26

When reviewing code, flag every occurrence with severity and remediation.

## 1. Hardcoded API Keys or Connection Strings
**Severity**: CRITICAL
```python
# WRONG
client = AIProjectClient(api_key="sk-...")
# FIX: Use DefaultAzureCredential + env vars
```

## 2. Pre-2.0 Hub/Project Endpoint URL Format
**Severity**: HIGH
```python
# WRONG
client = AIProjectClient(api_endpoint="https://myregion.api.cognitive.microsoft.com/...")
# FIX: Use project_connection_string from env var
```

## 3. Bypassing Foundry IQ (Raw AI Search)
**Severity**: HIGH
```python
# WRONG — loses agentic retrieval + ACL
search_client = SearchClient(endpoint=..., index_name=...)
# FIX: Use Foundry IQ knowledge_bases
```

## 4. Semantic Kernel for Greenfield Agents
**Severity**: WARN
```python
# FLAG — SK is legacy for new projects
from semantic_kernel import Kernel
# FIX: Use Microsoft Agent Framework
```

## 5. `require_approval="never"` on Destructive MCP Tool
**Severity**: CRITICAL
```python
# WRONG
mcp_tool = {"name": "delete_file", "require_approval": "never"}
# FIX: require_approval="always" for destructive actions
```

## 6. Connected Agents >2 Levels Deep
**Severity**: HIGH
```
# WRONG: Orchestrator → Manager → Worker → Sub-Worker (3 levels)
# FIX: Flatten to Orchestrator → [Worker A, Worker B, Worker C]
```

## 7. Missing OpenTelemetry Tracing on Production Agents
**Severity**: HIGH
```python
# WRONG — no tracing
run = client.agents.wait_for_run_completion(thread_id, run.id)
# FIX: Wrap in OTel span, configure Azure Monitor
```

## 8. azure-ai-agents Treated as Replacement for azure-ai-projects
**Severity**: WARN
```
# WRONG — they are PAIRED, not replacements
# FIX: Install and use both azure-ai-projects + azure-ai-agents
```

## 9. PREVIEW Features in Production Without Fallback
**Severity**: HIGH
```python
# WRONG — Foundry IQ in production with no fallback
knowledge_bases=[kb.id]
# FIX: Add [PREVIEW] stamp + fallback to classic RAG
```

## 10. Pre-Rebrand Import Paths
**Severity**: LOW
```python
# FLAG — use current "Foundry" / "Microsoft Foundry" terminology
# Not "Azure AI Foundry" or "Azure AI Studio"
```

## 11. No Run Timeout/Cancellation
**Severity**: HIGH
```python
# WRONG — can hang indefinitely
run = client.agents.wait_for_run_completion(thread_id, run.id)
# FIX: Add timeout=300 + cancellation on timeout
```

## 12. Tool-Call Errors Swallowed
**Severity**: WARN
```python
# WRONG — hides failures
except Exception:
    pass
# FIX: Surface errors in traces, return error to agent
```

## 13. Hardcoded Model Deployment Names
**Severity**: WARN
```python
# WRONG
model="gpt-4o"
# FIX: model=os.getenv("MODEL_DEPLOYMENT_NAME")
```

## 14. Missing Content Safety on User-Facing Agents
**Severity**: HIGH
```
# FLAG if no safety evaluators or guardrails configured
```

## 15. Logging Full Agent Messages Without PII Scrubbing
**Severity**: HIGH
```python
# WRONG
logger.info(f"Agent response: {full_message}")
# FIX: Truncate, hash, or redact PII
```

## 16. New Thread Per Turn
**Severity**: WARN
```python
# WRONG — loses conversation continuity, increases cost
thread = client.agents.create_thread()  # called every turn
# FIX: Reuse thread across multi-turn conversation
```

## 17. New Agent Per Request
**Severity**: WARN
```python
# WRONG — wasteful (cost, latency, schema validation)
agent = client.agents.create_agent(...)  # called every request
# FIX: Create once, store agent.id, reuse
```

## 18. Ignoring Document-Level ACL on Foundry IQ
**Severity**: CRITICAL
```python
# WRONG — users may query docs beyond their permissions
kb = client.knowledge_bases.create(...)
# FIX: Verify ACL enforcement, especially with Blob/AI Search sources
```

## 19. Responses API Calls Without Idempotency Keys
**Severity**: WARN
```
# FLAG — duplicate runs on retry without idempotency
```

## 20. One-Time Evaluation Runs
**Severity**: WARN
```
# WRONG — running evals once provides no regression tracking
# FIX: Schedule repeated evals, track scores over time
```
