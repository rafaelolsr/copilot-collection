# Evaluation and Tracing

> **Last validated**: 2026-04-26 | **Status**: GA (evals + OTel) | **Confidence**: 0.90

## Evaluation Framework

### Built-in Evaluators

| Evaluator | Measures |
|---|---|
| **Coherence** | Logical consistency of responses |
| **Relevance** | Whether response addresses the query |
| **Groundedness** | Whether response is grounded in provided context |
| **Safety** | Content safety (violence, self-harm, hate, sexual) |
| **Fluency** | Language quality |
| **Similarity** | Semantic similarity to reference answer |

### Running Evaluations

```python
from azure.ai.evaluation import evaluate

results = evaluate(
    data="eval_dataset.jsonl",
    evaluators={
        "coherence": coherence_evaluator,
        "relevance": relevance_evaluator,
        "groundedness": groundedness_evaluator,
    },
    azure_ai_project=project_config,
)
```

### Best Practices

1. **Golden dataset** — curate representative Q&A pairs
2. **Run repeatedly** — track regression, not one-time scores
3. **Set thresholds** — e.g., groundedness ≥ 0.8 for production
4. **Evaluate on real traffic** — sample production queries periodically
5. **Include safety evaluators** for user-facing agents

## OpenTelemetry Tracing

Production agents **MUST** have OTel tracing. Flag missing tracing in reviews.

### Setup with Azure Monitor

```python
from azure.monitor.opentelemetry import configure_azure_monitor
from opentelemetry import trace

configure_azure_monitor(
    credential=credential,
    connection_string=os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING"),
)

tracer = trace.get_tracer(__name__)
```

### Tracing Agent Runs

```python
with tracer.start_as_current_span(f"agent_run_{run.id}") as span:
    span.set_attribute("thread_id", thread_id)
    span.set_attribute("agent_id", agent.id)
    span.set_attribute("run_id", run.id)

    run = client.agents.wait_for_run_completion(
        thread_id=thread_id,
        run_id=run.id,
        timeout=300,
    )

    span.set_attribute("status", run.status)
    span.set_attribute("tokens_used", run.usage.total_tokens)
```

### What to Trace

- Agent run start/end
- Tool invocations and results
- Error conditions
- Token usage
- Latency per step

### What NOT to Log

- Full prompts or user input (PII risk)
- Raw agent messages without scrubbing
- API keys or credentials
- Full Foundry payloads

## Key Rules

1. **OTel is mandatory** for production — flag if missing
2. **Never log PII** — use hashed or truncated previews
3. **Run evals repeatedly** — track regression
4. **Safety evaluators** for user-facing agents
5. **Application Insights** as the default sink
