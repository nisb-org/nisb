# NISB Room Worker 并发

## 1. 概述

NISB Room worker 并发是一个 runtime orchestration 设置，用于控制一次 Room 执行中最多允许多少个 Room worker 同时运行。

设置字段为：

```text
max_worker_concurrency
```

有效范围：

```text
1..4
```

向后兼容默认值：

```text
1
```

发布前推荐基准：

```text
2
```

高级 / 实验值：

```text
3 或 4
```

当前实测结果显示，在 LibreChat 通过 MCP 接入 NISB Room 的场景下，使用 `max_worker_concurrency=4`，并运行 `7 RAG workers + supervisor`，Room 能在约 84 秒返回答案。测试期间，通过 `htop` 观察到的 VPS CPU 尖峰较温和，和并发 2 相比没有明显更高。

这表明当前 RAG-heavy Room 工作负载主要是外部 API / embedding / LLM / MCP I/O 等待，而不是 VPS 本地持续 CPU 计算。

## 2. 设计目标

Worker 并发不是 Room runtime 重写，而是一个 bounded concurrency 增强。它允许多个 worker packet 并行运行，同时保持单 worker 兼容性和既有协议稳定。

以下内容必须保持不变：

- 不改变 supervisor plan 协议。
- 不改变 worker packet shape。
- 不改变 worker result envelope。
- 不改变 RAG rewritten query。
- 不改变 provider query。
- 不改变 memory rewrite query。
- 不改变 Room MCP payload。
- 不改变 external Room MCP publish payload。
- 不改变 imported_remote / consumer-facing result view。
- 不并发 final synthesis。
- 不向 external consumer 暴露 source Room 内部 worker 执行细节。
- 不破坏 LibreChat 通过 Room MCP 接入。
- 不破坏 worker-side memory。
- 不破坏 runtime replay / projection。

## 3. 字段定义

### 3.1 主字段

```text
max_worker_concurrency
```

含义：

```text
一次 Room runtime 执行中允许同时运行的最大 worker 数。
```

类型：

```text
integer
```

有效范围：

```text
1..4
```

fallback 行为：

```text
缺失配置、旧 Room 数据、空值、非法值、小于 1 的值、超过服务端 cap 的值，都必须由后端归一化。
```

默认值：

```text
1
```

### 3.2 服务端 cap

可选环境变量：

```bash
NISB_ROOM_MAX_WORKER_CONCURRENCY_CAP=4
```

如果暂未实现环境变量，可以先硬编码 cap：

```text
cap = 4
```

最终生效并发数：

```text
effective_worker_concurrency = min(normalized_room_value, server_cap)
```

如果用户设置 4，但服务端 cap 是 2，runtime 应使用 2。

effective concurrency 可以记录在内部 trace / debug 日志中，但不能暴露到 external Room MCP consumer payload。

## 4. 推荐值

| 值 | 用途 | 建议 |
|---|---|---|
| 1 | 1c1g、旧 Room、保守部署、调试场景的最稳兼容模式 | 默认兼容值 |
| 2 | RAG-heavy Room 推荐基准，适合 2c2g 发布前生产测试 | 推荐 |
| 3 | API-bound 工作流、更高配置 VPS、能接受更多外部请求并发的用户 | 高级 |
| 4 | 多 RAG worker、明确 API-bound、已经压测过的 Room | 实验 / 高级 |

不要把 3 或 4 作为强全局默认值。

推荐策略：

```text
旧 Room 默认 1。
UI 推荐 2。
高级用户可手动选择 3 或 4。
服务端 cap 可以保持 4。
```

## 5. 为什么 CPU 没有明显升高

在当前 NISB Room RAG 工作负载中，worker 延迟通常不是由 VPS 本地持续 CPU 计算主导，而更常由以下因素主导：

- OpenAI embedding / API 调用。
- LLM 响应延迟。
- RAG 检索 I/O。
- MCP provider HTTP 请求延迟。
- JSON payload 组装和网络 I/O。
- 所有 worker 结果完成后的 supervisor final synthesis。

因此，并发从 2 提高到 4，主要增加的是 pending async task、HTTP 请求、结果对象和 event-loop 调度工作，并不会直接让本地 CPU 计算量乘以 2。

这解释了以下观测结果：

```text
7 RAG workers + supervisor
max_worker_concurrency=4
LibreChat 通过 MCP 接入
约 84 秒返回答案
CPU 尖峰较温和
htop 中并发 4 看起来不比并发 2 重很多
```

这符合 API-bound / I/O-bound 工作流的预期。

## 6. 后端实现要求

### 6.1 归一化函数

后端必须提供类似函数：

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

要求：

- 缺字段返回 1。
- 非数字返回 1。
- 小于 1 返回 1。
- 大于 cap 返回 cap。
- 默认 cap 是 4。
- 不能只信任前端归一化。

### 6.2 读取来源

后端可以根据现有项目结构，从以下来源读取：

```text
room settings
orchestration settings
runtime_control_snapshot
request payload
```

优先字段名：

```text
max_worker_concurrency
```

为了兼容，也可以读取：

```text
worker_concurrency
```

但主要保存字段和 UI 字段应使用：

```text
max_worker_concurrency
```

### 6.3 Bounded Concurrency

Worker packet 执行应使用 bounded concurrency。

推荐模式：

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

关键要求：

- 使用 `asyncio.Semaphore` 限制同时运行的 worker 数。
- 使用 `asyncio.create_task` 调度 worker 执行。
- 可以使用 `gather` 或 `as_completed`，但最终结果必须按原始 plan index 排序。
- 每个 worker result 必须保留原始 index。
- 每个 worker result 必须保留 role_id。
- 每个 worker result 必须保留 role_name。
- 每个 worker result 必须保留 packet_id。
- final synthesis 不得并发，必须在全部 worker result 完成后串行运行。

### 6.4 错误处理

并发不应导致单个 worker 错误意外击穿整个 runtime，除非原始实现本来就是 fail-fast。

要求：

- 如果原代码把 worker 错误转换为 warning/error result，应保持该行为。
- 如果原代码有意 fail-fast，可以保持 fail-fast 语义。
- 不要吞掉 `asyncio.CancelledError`。
- stop / abort 必须继续工作。
- worker exception 应保留 index / role_id / role_name / packet_id，便于 final synthesis 和调试。
- 不要因为一个 worker 失败就无理由丢弃其他已完成 worker 结果，除非既有协议要求这样做。

### 6.5 结果排序

并发执行会导致 worker 完成顺序不稳定，所以最终输出不能依赖完成顺序。

必须排序：

```text
worker_results.sort(key=lambda result: result.original_index)
```

目标：

```text
final projection / replay / final synthesis 结构应尽可能接近此前串行执行结构。
```

## 7. 前端要求

设置位置：

```text
Room Settings → Orchestration
```

UI 字段：

```text
Worker concurrency
```

选项：

```text
1 · safest
2 · recommended
3 · faster
4 · experimental
```

前端行为：

- 缺字段的旧 Room 显示 1。
- 用户选择写入 `form.max_worker_concurrency`。
- 保存 patch 将 `max_worker_concurrency` 写入 Room orchestration settings。
- 不新增独立 store。
- 不改变其他 Room Settings payload 结构。
- 不硬编码中文字符串。
- 3/4 应标记为高级或实验，不应强推荐。

推荐文案：

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

如果存放在 `room.settingsOrchestrationCard.fields` 下，使用：

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

### 8.2 简体中文

```js
workerConcurrencyTitle: 'Worker 并发数',
workerConcurrencyHint: '控制同一轮 Room 中最多同时运行多少个 worker。低配机器选 1 最稳；RAG 较多的房间推荐 2。',
workerConcurrencyOption1: '1 · 最稳',
workerConcurrencyOption2: '2 · 推荐',
workerConcurrencyOption3: '3 · 更快',
workerConcurrencyOption4: '4 · 实验',
```

如果存放在 `room.settingsOrchestrationCard.fields` 下，使用：

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

## 9. 验收命令

### 9.1 前端 grep

```bash
grep -RIn "max_worker_concurrency\|workerConcurrency\|Worker concurrency\|Worker 并发" \
  /opt/mcp-gateway/nisb-web/src/components/Editor/Room \
  /opt/mcp-gateway/nisb-web/src/composables/editor/room \
  /opt/mcp-gateway/nisb-web/src/locales
```

### 9.2 后端 grep

```bash
grep -RIn "max_worker_concurrency\|worker_concurrency\|Semaphore\|create_task\|gather\|as_completed" \
  /opt/mcp-gateway/mcp-nisb/tools/rooms_shared
```

### 9.3 stop / abort 检查

```bash
grep -RIn "CancelledError\|abort\|stop\|cancel" \
  /opt/mcp-gateway/mcp-nisb/tools/rooms_shared
```

### 9.4 external consumer 检查

```bash
grep -RIn "external.*publish\|imported_remote\|result_view\|consumer\|public" \
  /opt/mcp-gateway/mcp-nisb/tools/rooms_shared/room_runtime_result_view.py \
  /opt/mcp-gateway/mcp-nisb/tools/rooms_shared/room_role_runtime_packets.py \
  /opt/mcp-gateway/mcp-nisb/tools/rooms_shared/room_contracts.py
```

### 9.5 前端构建

```bash
cd /opt/mcp-gateway/nisb-web
npm run build
```

### 9.6 后端语法检查

```bash
cd /opt/mcp-gateway/mcp-nisb
python -m py_compile \
  tools/rooms_shared/room_worker_execution.py \
  tools/rooms_shared/room_runtime_execution.py \
  tools/rooms_shared/room_orchestrator_supervisor_flow.py
```

## 10. UI 验收清单

- 打开缺字段旧 Room 时，Worker concurrency 显示为 1。
- 选择 2，保存，再次打开仍显示 2。
- 选择 4，保存，再次打开仍显示 4。
- 只有 1 / 2 / 3 / 4 四个选项。
- 文案明确说明 1 最稳、2 推荐、3/4 是高级或实验。
- 英文 UI 不包含硬编码中文。
- 中文 UI 不包含未解析翻译 key。
- orchestration summary 或 chip 显示当前 worker concurrency 值。
- 其他 Room Settings 字段继续正常保存。
- Room MCP publish / external publish settings 不受影响。

## 11. Runtime 验收清单

### 11.1 兼容模式

设置：

```text
max_worker_concurrency=1
```

预期：

- 行为接近此前串行执行。
- 1c1g / 2c1g 实例仍可用。
- worker result 顺序稳定。
- replay / projection 结构不变。

### 11.2 推荐模式

设置：

```text
max_worker_concurrency=2
```

预期：

- 2c2g 上的 RAG-heavy Room 可以通过重叠等待时间获得收益。
- CPU 使用主要表现为短尖峰。
- LibreChat MCP 接入仍正常返回。
- final synthesis 仍串行执行。

### 11.3 高级模式

设置：

```text
max_worker_concurrency=4
```

测试场景：

```text
7 RAG workers + supervisor
LibreChat connected to NISB Room through MCP
```

观测结果：

```text
约 84 秒返回答案
htop CPU 尖峰较温和
并发 4 看起来不比并发 2 明显更重
```

预期解释：

```text
该工作负载主要是 API-bound / I/O-bound，不是本地 CPU-bound。
```

### 11.4 stop / abort

预期：

- 执行中停止应正常 cancel 当前 run。
- `CancelledError` 不应被吞掉。
- 不应留下长时间运行的 orphan worker task。
- 下一次 run 不应被前一次 aborted run 污染。

### 11.5 Worker Errors

预期：

- 单个 worker 失败时，应遵循既有 warning/error result 行为。
- 其他 worker result 不应被无理由丢弃。
- final synthesis 应能看到成功结果和错误提示。
- 如果原始实现是 fail-fast，可以保持 fail-fast 语义。

### 11.6 External Consumer

预期：

- External Room MCP consumer 看不到内部 worker concurrency 细节。
- imported_remote result view 保持不变。
- Room MCP publish payload 保持不变。
- worker internal trace 不进入 consumer-facing payload。

## 12. 风险

### 12.1 CPU 不是唯一风险

即使并发 4 时 CPU 仍然温和，风险也可能转移到：

- 内存峰值。
- HTTP socket 数量。
- provider rate limit。
- OpenAI / embedding API 429。
- LLM API tail latency。
- 反向代理 timeout。
- Cloudflare / upstream timeout。
- MCP client waiting window。
- Python event-loop pending task 数量。
- 大 result envelope 占用的内存。

### 12.2 不要默认 4

当前测试说明并发 4 对某个 RAG-heavy / API-bound Room 有效，但不能证明所有 Room 都应默认 4。

不推荐：

```text
Set 4 as the global default.
```

推荐：

```text
Default compatibility remains 1.
Product recommendation remains 2.
Advanced users may manually select 3/4.
```

### 12.3 本地 CPU-bound worker

如果未来 worker 执行本地 CPU-heavy 工作，例如：

- 本地 OCR。
- 本地 embedding。
- 大型本地解析。
- 大文档同步处理。
- 本地 reranking。
- 压缩 / 解压 / 文件扫描。

那么并发 4 可能显著增加 CPU 和内存压力。

这类 worker 在进入同一个 worker concurrency pool 前应单独评估，或者需要更细粒度的资源调度器。

## 13. 发布建议

NISB V1 pre-release：

```text
后端支持 1..4。
服务端 cap 默认 4。
缺字段旧 Room fallback 到 1。
UI 默认显示 1。
UI 文案推荐 RAG-heavy Room 使用 2。
3/4 标记为高级 / 实验。
```

生产指导：

```text
1c1g: use 1.
2c1g: use 1 or 2.
2c2g: recommend 2; use 4 only for tested RAG-heavy Rooms.
8c16g: use 3 or 4 if appropriate.
```

当前项目指导：

```text
Use 2 as the production recommendation.
For the tested 7-RAG-worker Room, manually setting 4 is acceptable.
```

## 14. 故障排查

### 14.1 CPU 很低但 runtime 很慢

可能原因：

- 外部 API 延迟。
- 慢尾 RAG worker。
- final synthesis 慢。
- provider rate limit。
- MCP response wait。
- 反向代理 buffering。

检查：

```bash
docker logs --tail=300 -f mcp-nisb
```

### 14.2 并发 4 不比并发 2 快

可能原因：

- critical path 是最慢 worker。
- final synthesis 主导总耗时。
- 外部 API rate limit。
- HTTP connection pool 限制。
- provider 对并发请求排队。
- RAG worker 内部仍有串行段。

处理：

```text
保持 4 为高级选项。
不要强推广 4。
增加 worker start/end/duration debug trace。
识别 slow-tail worker。
```

### 14.3 CPU 尖峰过高

可能原因：

- worker 内部存在同步阻塞代码。
- 本地 CPU-heavy task 进入共享 worker pool。
- 并发处理大文档。
- JSON / markdown / sanitizer / parser 开销。

处理：

```text
降低并发到 2 或 1。
检查同步阻塞函数。
必要时使用 asyncio.to_thread 包装 blocking function。
```

### 14.4 LibreChat Timeout

可能原因：

- Room runtime 超过 MCP client / reverse proxy waiting window。
- final synthesis 过慢。
- 7 个 workers 中存在长尾 worker。
- provider 响应慢。

处理：

```text
先测试 max_worker_concurrency=4。
必要时减少 worker 数。
必要时降低 RAG top-k / context size。
检查 Nginx / Cloudflare / LibreChat MCP timeout settings。
```

## 15. 最小回滚

如果并发导致问题，回滚不需要删除代码。

将 Room 设置为：

```text
max_worker_concurrency=1
```

或强制服务端 cap：

```bash
NISB_ROOM_MAX_WORKER_CONCURRENCY_CAP=1
```

预期结果：

```text
Worker execution returns to behavior close to the previous serial mode.
```

## 16. 未来改进

以下是可能的未来工作，但不建议在 V1 前实施：

- 按 worker 类型拆分并发。
- RAG worker 和 MCP worker 使用独立 pool。
- 自适应 provider rate-limit handling。
- slow-tail partial synthesis。
- worker duration trace UI。
- queue-depth debug panel。
- Room runtime profile export。

这些应推迟，因为 V1 优先级是稳定协议、稳定 LibreChat MCP 接入、稳定 external consumer result view。
