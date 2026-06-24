# NISB Room Worker Concurrency

## 1. Overview

NISB Room worker concurrency is a runtime orchestration setting that controls how many Room workers may run at the same time during one Room execution.

The setting field is:

```text
max_worker_concurrency
```

Valid range:

```text
1..4
```

Backward-compatible default:

```text
1
```

Recommended pre-release baseline:

```text
2
```

Advanced / experimental values:

```text
3 or 4
```

Current field testing shows that, with LibreChat connected to NISB Room through MCP, a Room run using `max_worker_concurrency=4` with `7 RAG workers + supervisor` returned an answer in about 84 seconds. During the test, VPS CPU spikes observed in `htop` were mild and did not look significantly higher than concurrency 2.

This indicates that the current RAG-heavy Room workload is mostly external API / embedding / LLM / MCP I/O waiting, not sustained local CPU computation on the VPS.

## 2. Design Goals

Worker concurrency is not a Room runtime rewrite. It is a bounded concurrency enhancement that allows multiple worker packets to run in parallel while preserving single-worker compatibility and existing protocols.

The following must remain unchanged:

- Do not change the supervisor plan protocol.
- Do not change the worker packet shape.
- Do not change the worker result envelope.
- Do not change the RAG rewritten query.
- Do not change provider queries.
- Do not change memory rewrite queries.
- Do not change the Room MCP payload.
- Do not change the external Room MCP publish payload.
- Do not change imported_remote / consumer-facing result views.
- Do not run final synthesis concurrently.
- Do not expose source Room internal worker execution details to external consumers.
- Do not break LibreChat access through Room MCP.
- Do not break worker-side memory.
- Do not break runtime replay / projection.

## 3. Field Definition

### 3.1 Primary Field

```text
max_worker_concurrency
```

Meaning:

```text
Maximum number of workers allowed to run at the same time in one Room runtime execution.
```

Type:

```text
integer
```

Valid range:

```text
1..4
```

Fallback behavior:

```text
Missing configuration, legacy Room data, empty values, invalid values, values below 1, and values above the server cap must be normalized by the backend.
```

Default:

```text
1
```

### 3.2 Server Cap

Optional environment variable:

```bash
NISB_ROOM_MAX_WORKER_CONCURRENCY_CAP=4
```

If the environment variable is not implemented, the cap may be hardcoded first:

```text
cap = 4
```

Effective concurrency:

```text
effective_worker_concurrency = min(normalized_room_value, server_cap)
```

If a user sets 4 while the server cap is 2, the runtime should use 2.

Effective concurrency may be recorded in internal trace / debug logs, but it must not be exposed in external Room MCP consumer payloads.

## 4. Recommended Values

| Value | Usage | Recommendation |
|---|---|---|
| 1 | Safest compatibility mode for 1c1g, legacy Rooms, conservative deployments, and debugging | Default compatibility value |
| 2 | Recommended baseline for RAG-heavy Rooms, suitable for 2c2g pre-release production | Recommended |
| 3 | API-bound workflows, larger VPS instances, and users who can tolerate more external request concurrency | Advanced |
| 4 | Many RAG workers, clearly API-bound workloads, and Rooms that have been tested under load | Experimental / advanced |

Do not use 3 or 4 as a strong global default.

Recommended policy:

```text
Legacy Rooms default to 1.
The UI recommends 2.
Advanced users may manually select 3 or 4.
The server cap may remain 4.
```

## 5. Why CPU Did Not Increase Much

In the current NISB Room RAG workload, worker latency is usually not dominated by sustained local CPU computation on the VPS. It is more often dominated by:

- OpenAI embedding / API calls.
- LLM response latency.
- RAG retrieval I/O.
- MCP provider HTTP request latency.
- JSON payload assembly and network I/O.
- Supervisor final synthesis after all worker results are available.

Therefore, raising concurrency from 2 to 4 mainly increases the number of pending async tasks, HTTP requests, result objects, and event-loop scheduling work. It does not directly multiply local CPU computation by 2.

This explains the observed behavior:

```text
7 RAG workers + supervisor
max_worker_concurrency=4
LibreChat connected through MCP
Answer returned in about 84 seconds
CPU spikes were mild
Concurrency 4 did not look much heavier than concurrency 2 in htop
```

This is expected for an API-bound / I/O-bound workflow.

## 6. Backend Implementation Requirements

### 6.1 Normalize Function

The backend must provide a function similar to:

```python
def normalize_worker_concurrency(value, default=1, cap=4):
    try:
        n = int(value)
    except Exception:
        return default

    if n < 1:
        return default

    if n > cap:
        return cap

    return n
```

Requirements:

- Missing field returns 1.
- Non-numeric values return 1.
- Values below 1 return 1.
- Values above cap return cap.
- Default cap is 4.
- Do not trust frontend normalization alone.

### 6.2 Read Sources

The backend may read the value from whichever source best matches the existing project structure:

```text
room settings
orchestration settings
runtime_control_snapshot
request payload
```

Preferred field name:

```text
max_worker_concurrency
```

For compatibility, the backend may also read:

```text
worker_concurrency
```

However, the primary saved field and UI field should be:

```text
max_worker_concurrency
```

### 6.3 Bounded Concurrency

Worker packet execution should use bounded concurrency.

Recommended pattern:

```python
semaphore = asyncio.Semaphore(max_worker_concurrency)

async def run_one_worker(index, packet):
    async with semaphore:
        return await execute_worker_packet(index, packet)

tasks = [
    asyncio.create_task(run_one_worker(index, packet))
    for index, packet in enumerate(worker_packets)
]

results = await asyncio.gather(*tasks)
results = sorted(results, key=lambda item: item.get("index", 0))
```

Key requirements:

- Use `asyncio.Semaphore` to limit the number of concurrently running workers.
- Use `asyncio.create_task` to schedule worker execution.
- Either `gather` or `as_completed` may be used, but final results must be sorted by the original plan index.
- Each worker result must preserve the original index.
- Each worker result must preserve role_id.
- Each worker result must preserve role_name.
- Each worker result must preserve packet_id.
- Final synthesis must not run concurrently; it must run serially after all worker results are complete.

### 6.4 Error Handling

Concurrency must not allow one worker error to unexpectedly crash the entire runtime unless that was already the original behavior.

Requirements:

- If the original code converts worker errors into warning/error results, keep that behavior.
- If the original code is intentionally fail-fast, preserving fail-fast is acceptable.
- Do not swallow `asyncio.CancelledError`.
- stop / abort must continue to work.
- Worker exceptions should retain index / role_id / role_name / packet_id for final synthesis and debugging.
- Do not discard other completed worker results because one worker failed, unless the existing protocol already requires that.

### 6.5 Result Ordering

Concurrent execution makes worker completion order unstable, so final output must not be based on completion order.

Required sorting:

```text
worker_results.sort(key=lambda result: result.original_index)
```

Goal:

```text
The final projection / replay / final synthesis structure should remain as close as possible to the previous serial execution structure.
```

## 7. Frontend Requirements

Settings location:

```text
Room Settings → Orchestration
```

UI field:

```text
Worker concurrency
```

Options:

```text
1 · safest
2 · recommended
3 · faster
4 · experimental
```

Frontend behavior:

- Legacy Rooms without the field should show 1.
- User selection should write to `form.max_worker_concurrency`.
- The save patch should write `max_worker_concurrency` into the Room orchestration settings.
- Do not add a separate store.
- Do not change the rest of the Room Settings payload structure.
- Do not hardcode Chinese strings.
- 3/4 should be marked as advanced or experimental, not strongly recommended.

Recommended copy:

```text
Controls how many room workers may run at the same time. Use 1 for the safest low-resource mode; 2 is recommended for RAG-heavy rooms.
```

## 8. Locale

### 8.1 English

```js
workerConcurrencyTitle: 'Worker concurrency',
workerConcurrencyHint: 'Controls how many room workers may run at the same time. Use 1 for the safest low-resource mode; 2 is recommended for RAG-heavy rooms.',
workerConcurrencyOption1: '1 · safest',
workerConcurrencyOption2: '2 · recommended',
workerConcurrencyOption3: '3 · faster',
workerConcurrencyOption4: '4 · experimental',
```

If stored under `room.settingsOrchestrationCard.fields`, use:

```js
workerConcurrency: {
  label: 'Worker concurrency',
  hint: 'Controls how many room workers may run at the same time. Use 1 for the safest low-resource mode; 2 is recommended for RAG-heavy rooms.',
  options: {
    option1: '1 · safest',
    option2: '2 · recommended',
    option3: '3 · faster',
    option4: '4 · experimental',
  },
},
workerConcurrencySummary: {
  label: 'Worker concurrency summary',
  safest: '{value} worker at a time. Safest for low-resource VPS instances.',
  recommended: '{value} workers at a time. Recommended for RAG-heavy rooms.',
  faster: '{value} workers at a time. Faster for API-bound workflows.',
  experimental: '{value} workers at a time. Experimental; use on higher-resource machines.',
},
```

### 8.2 Simplified Chinese

```js
workerConcurrencyTitle: 'Worker 并发数',
workerConcurrencyHint: '控制同一轮 Room 中最多同时运行多少个 worker。低配机器选 1 最稳；RAG 较多的房间推荐 2。',
workerConcurrencyOption1: '1 · 最稳',
workerConcurrencyOption2: '2 · 推荐',
workerConcurrencyOption3: '3 · 更快',
workerConcurrencyOption4: '4 · 实验',
```

If stored under `room.settingsOrchestrationCard.fields`, use:

```js
workerConcurrency: {
  label: 'Worker 并发数',
  hint: '控制同一轮 Room 中最多同时运行多少个 worker。低配机器选 1 最稳；RAG 较多的房间推荐 2。',
  options: {
    option1: '1 · 最稳',
    option2: '2 · 推荐',
    option3: '3 · 更快',
    option4: '4 · 实验',
  },
},
workerConcurrencySummary: {
  label: 'Worker 并发摘要',
  safest: '每次最多 {value} 个 worker。最适合低配 VPS。',
  recommended: '每次最多 {value} 个 worker。推荐用于 RAG 较多的房间。',
  faster: '每次最多 {value} 个 worker。更适合 API-bound 工作流。',
  experimental: '每次最多 {value} 个 worker。实验选项，建议在更高配置机器上使用。',
},
```

## 9. Validation Commands

### 9.1 Frontend grep

```bash
grep -RIn "max_worker_concurrency\|workerConcurrency\|Worker concurrency\|Worker 并发" \
  /opt/mcp-gateway/nisb-web/src/components/Editor/Room \
  /opt/mcp-gateway/nisb-web/src/composables/editor/room \
  /opt/mcp-gateway/nisb-web/src/locales
```

### 9.2 Backend grep

```bash
grep -RIn "max_worker_concurrency\|worker_concurrency\|Semaphore\|create_task\|gather\|as_completed" \
  /opt/mcp-gateway/mcp-nisb/tools/rooms_shared
```

### 9.3 stop / abort check

```bash
grep -RIn "CancelledError\|abort\|stop\|cancel" \
  /opt/mcp-gateway/mcp-nisb/tools/rooms_shared
```

### 9.4 external consumer check

```bash
grep -RIn "external.*publish\|imported_remote\|result_view\|consumer\|public" \
  /opt/mcp-gateway/mcp-nisb/tools/rooms_shared/room_runtime_result_view.py \
  /opt/mcp-gateway/mcp-nisb/tools/rooms_shared/room_role_runtime_packets.py \
  /opt/mcp-gateway/mcp-nisb/tools/rooms_shared/room_contracts.py
```

### 9.5 Frontend build

```bash
cd /opt/mcp-gateway/nisb-web
npm run build
```

### 9.6 Backend syntax check

```bash
cd /opt/mcp-gateway/mcp-nisb
python -m py_compile \
  tools/rooms_shared/room_worker_execution.py \
  tools/rooms_shared/room_runtime_execution.py \
  tools/rooms_shared/room_orchestrator_supervisor_flow.py
```

## 10. UI Acceptance Checklist

- Opening a legacy Room shows Worker concurrency as 1.
- Selecting 2, saving, and reopening still shows 2.
- Selecting 4, saving, and reopening still shows 4.
- Only 1 / 2 / 3 / 4 are available.
- Copy clearly states that 1 is safest, 2 is recommended, and 3/4 are advanced or experimental.
- English UI contains no hardcoded Chinese.
- Chinese UI contains no unresolved translation keys.
- The orchestration summary or chip shows the current worker concurrency value.
- Other Room Settings fields continue to save normally.
- Room MCP publish / external publish settings are unaffected.

## 11. Runtime Acceptance Checklist

### 11.1 Compatibility Mode

Setting:

```text
max_worker_concurrency=1
```

Expected:

- Behavior is close to the previous serial execution.
- 1c1g / 2c1g instances remain usable.
- Worker result order is stable.
- Replay / projection structure remains unchanged.

### 11.2 Recommended Mode

Setting:

```text
max_worker_concurrency=2
```

Expected:

- RAG-heavy Rooms on 2c2g can benefit from overlapping wait time.
- CPU usage mainly appears as short spikes.
- LibreChat MCP access still returns normally.
- Final synthesis still runs serially.

### 11.3 Advanced Mode

Setting:

```text
max_worker_concurrency=4
```

Test scenario:

```text
7 RAG workers + supervisor
LibreChat connected to NISB Room through MCP
```

Observed result:

```text
Answer returned in about 84 seconds
htop CPU spikes were mild
Concurrency 4 did not look significantly heavier than concurrency 2
```

Expected explanation:

```text
The workload is mainly API-bound / I/O-bound, not local CPU-bound.
```

### 11.4 stop / abort

Expected:

- Stopping during execution should cancel the run normally.
- `CancelledError` should not be swallowed.
- No long-running orphan worker task should remain.
- The next run should not be polluted by the previous aborted run.

### 11.5 Worker Errors

Expected:

- A single worker failure should follow the existing warning/error result behavior.
- Other worker results should not be discarded without reason.
- Final synthesis should see available successful results and error hints.
- If the original implementation is fail-fast, fail-fast semantics may be preserved.

### 11.6 External Consumer

Expected:

- External Room MCP consumers do not see internal worker concurrency details.
- imported_remote result view remains unchanged.
- Room MCP publish payload remains unchanged.
- Worker internal trace does not enter consumer-facing payloads.

## 12. Risks

### 12.1 CPU Is Not the Only Risk

Even when CPU stays mild at concurrency 4, risk may move to:

- Memory peaks.
- HTTP socket count.
- Provider rate limits.
- OpenAI / embedding API 429s.
- LLM API tail latency.
- Reverse proxy timeout.
- Cloudflare / upstream timeout.
- MCP client waiting window.
- Number of pending Python event-loop tasks.
- Memory used by large result envelopes.

### 12.2 Do Not Default to 4

The current test shows that 4 works for a specific RAG-heavy / API-bound Room. It does not prove that all Rooms should default to 4.

Not recommended:

```text
Set 4 as the global default.
```

Recommended:

```text
Default compatibility remains 1.
Product recommendation remains 2.
Advanced users may manually select 3/4.
```

### 12.3 Local CPU-Bound Workers

If future workers perform local CPU-heavy work, such as:

- Local OCR.
- Local embedding.
- Large local parsing.
- Large-document synchronous processing.
- Local reranking.
- Compression / decompression / file scanning.

Then concurrency 4 may significantly increase CPU and memory pressure.

Such workers should be evaluated separately before sharing the same worker concurrency pool, or a more detailed resource scheduler may be needed.

## 13. Release Recommendation

For NISB V1 pre-release:

```text
Backend supports 1..4.
Server cap defaults to 4.
Legacy Rooms without the field fall back to 1.
UI default display is 1.
UI copy recommends 2 for RAG-heavy Rooms.
3/4 are marked advanced / experimental.
```

Production guidance:

```text
1c1g: use 1.
2c1g: use 1 or 2.
2c2g: recommend 2; use 4 only for tested RAG-heavy Rooms.
8c16g: use 3 or 4 if appropriate.
```

Current project guidance:

```text
Use 2 as the production recommendation.
For the tested 7-RAG-worker Room, manually setting 4 is acceptable.
```

## 14. Troubleshooting

### 14.1 CPU Is Low but Runtime Is Slow

Possible causes:

- External API latency.
- Slow-tail RAG worker.
- Slow final synthesis.
- Provider rate limits.
- MCP response wait.
- Reverse proxy buffering.

Check:

```bash
docker logs --tail=300 -f mcp-nisb
```

### 14.2 Concurrency 4 Is Not Faster Than 2

Possible causes:

- Critical path is the slowest worker.
- Final synthesis dominates runtime.
- External API rate limits.
- HTTP connection pool limits.
- Provider queues concurrent requests.
- RAG worker still contains internal serial segments.

Action:

```text
Keep 4 as an advanced option.
Do not strongly promote it.
Add worker start/end/duration debug traces.
Identify slow-tail workers.
```

### 14.3 CPU Spikes Too High

Possible causes:

- Synchronous blocking code inside workers.
- Local CPU-heavy tasks entering the shared worker pool.
- Concurrent large-document processing.
- JSON / markdown / sanitizer / parser overhead.

Action:

```text
Lower concurrency to 2 or 1.
Check for synchronous blocking functions.
Wrap blocking functions with asyncio.to_thread if needed.
```

### 14.4 LibreChat Timeout

Possible causes:

- Room runtime exceeds the MCP client / reverse proxy waiting window.
- Final synthesis is too slow.
- One of the 7 workers has long-tail latency.
- Provider response is slow.

Action:

```text
Test max_worker_concurrency=4 first.
Reduce worker count if needed.
Reduce RAG top-k / context size if needed.
Check Nginx / Cloudflare / LibreChat MCP timeout settings.
```

## 15. Minimal Rollback

If concurrency causes issues, rollback does not require deleting code.

Set the Room to:

```text
max_worker_concurrency=1
```

Or force the server cap:

```bash
NISB_ROOM_MAX_WORKER_CONCURRENCY_CAP=1
```

Expected result:

```text
Worker execution returns to behavior close to the previous serial mode.
```

## 16. Future Improvements

Possible future work, but not recommended before V1:

- Per-worker-type concurrency.
- Separate pools for RAG workers and MCP workers.
- Adaptive provider rate-limit handling.
- Slow-tail partial synthesis.
- Worker duration trace UI.
- Queue-depth debug panel.
- Room runtime profile export.

These should be deferred because the V1 priority is stable protocols, stable LibreChat MCP access, and stable external consumer result views.
