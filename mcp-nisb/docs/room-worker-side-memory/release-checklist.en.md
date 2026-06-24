# NISB Room Worker Side Memory Release Checklist

Date: 2026-06-11  
Scope: Supervisor side memory, MCP provider workers, RAG workers

## Required Checks

- [ ] `supervisor.memory.json` is written by supervisor persistence.
- [ ] Worker does not write `supervisor.memory.json`.
- [ ] Worker reads compact memory only.
- [ ] Provider does not read memory sidecar.
- [ ] RAG/QAScope does not read memory sidecar.
- [ ] Provider receives rewritten standalone query only.
- [ ] RAG receives rewritten standalone query only.
- [ ] Raw memory JSON is not sent to provider.
- [ ] Raw memory JSON is not sent to RAG.
- [ ] `continue_from_checkpoint` can reuse `topic_anchor`.
- [ ] `restart_fresh` does not reuse old `topic_anchor`.
- [ ] `ignore_stale_checkpoint` does not reuse old `topic_anchor`.
- [ ] Missing checkpoint does not fabricate topic anchor.
- [ ] Invalid checkpoint does not fabricate topic anchor.
- [ ] Notebook write denial does not block worker read-only memory.
- [ ] MCP provider path still works.
- [ ] RAG/QAScope path still works.
- [ ] Regular worker fallback still works.
- [ ] External MCP publish remains unchanged.
- [ ] Imported remote provider behavior remains unchanged.
- [ ] Provider registry remains unchanged.
- [ ] Provider presets remain unchanged.

## MCP Provider Validation

### Pexels / Country

Input:

```text
First: Introduce the Philippines
Second: Continue introducing this country's transportation
```

Expected:

```text
provider query = Philippines introduce transportation
worker_memory_provider_question_resolved = true
```

### Exa / Company

Input:

```text
First: Introduce OpenAI
Second: Continue checking this company's competitors
```

Expected:

```text
provider query = OpenAI competitors
worker_memory_provider_question_resolved = true
```

## RAG Validation

### Geopolitics

Input:

```text
First: Introduce United States and Iran dynamics
Second: Reasons why future developments still need close attention
```

Expected:

```text
mode_used = cite
evidence_tools = ["nisb_qascope_ask"]
citations = non-empty
evidence_query = United States Iran dynamics future developments still need close attention reasons
worker_memory_rag_question_resolved = true
```

### Project

Input:

```text
First: Introduce NISB Room runtime
Second: Continue analyzing this project's risks
```

Expected:

```text
RAG query = NISB Room runtime risks
```

## Negative Validation

### New Topic

Input:

```text
First: Introduce Dali
Second: Introduce Bangkok food
```

Expected:

```text
decision = restart_fresh
old topic_anchor is not inherited
```

### Missing Checkpoint

Input:

```text
Continue introducing this country's transportation
```

Precondition:

```text
supervisor.memory.json missing
```

Expected:

```text
worker_memory_context_used = false
no fabricated country/topic
```

## Observability

- [ ] `room_worker_memory_context` appears in role event.
- [ ] MCP path uses `worker_memory_provider_question_*` fields.
- [ ] RAG path uses `worker_memory_rag_question_*` fields.
- [ ] `evidence_query` equals rewritten query when RAG is used.
- [ ] Provider result query equals rewritten query when MCP provider is used.
- [ ] QAScope failures are visible in trace.
