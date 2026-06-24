# Room Runtime Contract

## 1. 文档目标

本文档定义 NISB Room runtime 的后端正式契约，用于约束 Room 对外返回字段、SSE 不变式、Room 与 Workspace 边界、Supervisor 审计表达，以及后续扩展时的禁止事项。

本文档是 Room runtime 的正式口径文档。后续新增能力、测试和修复，应优先遵循本文档，而不是临时扩展新字段或新事件协议。

## 2. 适用范围

适用于以下后端路径：

- `/opt/mcp-gateway/mcp-nisb/tools/rooms_shared/`
- Room runtime 对外工具返回
- Room recent runtime 读取
- Room replay 读取
- Room formal packet 构造
- Room Supervisor 审计相关输出

不直接覆盖：

- 全站所有 chat 工具
- 全量 doc / workspace / qa 业务细节
- 所有内部 timeline 存储格式

## 3. Room 对外正式字段

Room 对外正式返回只能使用以下顶层字段：

- `conv_id`
- `request_id`
- `rag_mode`
- `mcp_overrides`
- `mode_used`
- `rss_evidence`
- `market_evidence`
- `evidence_query`
- `evidence_tools`
- `evidence_result`
- `qa_id`
- `group_id`
- `citations`
- `response`
- `status`
- `message`
- `tool_calls`
- `tool_results`

约束如下：

- `response` 是正式正文。
- `message` 是状态语、补充语或失败提示。
- `tool_results` 是唯一正式结构化业务结果承载位置。
- `tool_calls` 用于保留正式工具调用活动。
- `citations / rss_evidence / market_evidence / evidence_query / evidence_tools / evidence_result` 是正式证据字段。
- `status` 是正式成功失败判断入口。

以下规则必须始终成立：

- 禁止新增正式顶层 `result`。
- 禁止把结构化业务结果上浮为新的正式顶层字段。
- 禁止把内部调试字段当作正式对外协议。
- legacy `success` 仅保留兼容，不再作为正式成功态核心判断依据。

## 4. formal-first 规则

Room runtime 的 formal-first 规则如下：

1. 前后端都应优先读取 `status`。
2. 前后端都应优先读取 `response` 作为正式正文。
3. 结构化业务结果统一从 `tool_results` 读取。
4. 兼容期才允许回退 legacy 字段。
5. 新增能力必须先思考如何放入现有正式字段，而不是新增第二套顶层协议。

成功态必须满足：

- `status` 为 `success` 或兼容等价值时，必须有非空 `response`。
- 如果调用链路未直接给出 `response`，允许在 packet builder 内以 `message` 兜底生成非空 `response`。
- 成功态不得返回空正文加“只有结构化结果”的正式包。

失败态必须满足：

- `status` 为 `error` 时，`response` 也必须非空。
- `message` 应提供可读错误信息。
- 工具级结构化失败信息仍统一进入 `tool_results`。

## 5. tool_results 规则

`tool_results` 是 Room runtime 唯一正式结构化业务结果出口。

允许进入 `tool_results` 的内容包括：

- `room_items`
- `room_runtime_events`
- `room_run_replay`
- `room_event`
- `route_event`
- `generated_event`
- `generated_events`
- `plan_event`
- `delegate_events`
- `final_event`
- `room_runtime_run`
- `supervisor_direct_runtime`
- `room_chat_bridge`
- `room_qascope_bridge`
- 审计与运行状态相关结构化结果

不允许的做法包括：

- 新增顶层 `result`
- 新增顶层 `runtime`
- 新增顶层 `replay`
- 将 Room 内部 UI 状态直接外露为正式顶层字段
- 把 Workspace 内部控制状态直接上浮为 Room 正式协议

## 6. SSE 不变式

Room 对外 SSE 只能使用以下正式事件名：

- `meta`
- `delta`
- `tool_call`
- `tool_result`
- `final`
- `error`
- `done`

相关规则如下：

- `status` 只能存在于 payload 内，不能作为 SSE 事件名。
- Room / Workspace / QA / RAG / filesystem / doc 不允许各自发明新的 SSE 正式事件标准。
- Room 内部 timeline 事件，如 `room.plan / room.delegate / room.message / room.supervisor / room.final / room.aborted`，可以存在于 Room 内部状态和回放体系中，但它们不是新的对外 SSE 正式协议。
- 若 future feature 需要更多阶段表达，应优先进入 Room 内部 timeline event，而不是扩展 SSE 事件名。

## 7. Room 与 Workspace 边界

Room 是 NISB 的主运行容器，但 Workspace 不是 Room 的附庸。

必须遵守以下边界：

- Room 可以受控继承 Workspace 上下文，但不能吞掉 Workspace 边界控制权。
- `inherit_workspace_context` 必须用户显式可控。
- `inherit_focus_root` 必须用户显式可控。
- `focus_root` 是 agent 可用上下文边界，不是无限授权。
- `mcp_overrides` 与 `tool_policy` 必须继续受显式边界约束。
- Room 不得借 Supervisor 或 MCP 工具把文件能力无边界放大。

禁止事项：

- 禁止把 Workspace 继承做成默认隐式越权。
- 禁止把 `focus_root` 解释为无限文件系统授权。
- 禁止让 MCP 工具层替代 Room runtime 的边界判断职责。

## 8. Supervisor 审计契约

Room Supervisor 审计用于表达 Supervisor 在受控边界内的工具活动与最终合成关系。

审计约束如下：

- 审计信息可以通过 replay / state snapshot / relation 方式表达。
- 审计关系应尽量围绕同一 `room_id + run_id + supervisor_event_id + final_event_id` 组织。
- 审计应能关联 `fs_read`、`notebook_write` 等受控能力。
- 审计不应破坏 formal-first 顶层协议。
- 审计结构化结果如需对外暴露，仍进入 `tool_results` 或 replay payload 内部结构。

推荐保留的审计标识包括：

- `room_id`
- `request_id`
- `run_id`
- `plan_event_id`
- `supervisor_event_id`
- `final_event_id`
- `trigger_event_id`
- `recorded_at`

## 9. packet builder 职责

`room_packet_builder.py` 的职责是：

- 统一 formal packet 输出
- 统一 `status / response / message` 归一化
- 统一 evidence 字段填充
- 统一 `tool_calls / tool_results` 命名与补齐
- 把非 formal 结果桥接成 formal 包

不应让 packet builder 承担的职责：

- 新业务编排主逻辑
- Room runtime 状态机
- Workspace 权限决策主逻辑
- 前端展示层状态结构

## 10. recent runtime 与 replay 的契约位置

Room runtime 对外有两类只读读取：

- recent runtime：面向当前或最近一次 run 的增量/近实时读取
- replay：面向某个 run 的历史只读回放读取

两者都属于 Room runtime 读模型，但职责不同：

- recent runtime 负责当前运行期跟随与增量读取
- replay 负责历史 run 复盘与只读展示
- 两者共享 run 事实链，但不得互相污染状态语义

## 11. 扩展原则

后续新增 Room runtime 能力时，应优先沿以下链路扩展：

1. 先确认 formal-first 顶层字段是否足够承载。
2. 若需要结构化信息，优先进入 `tool_results`。
3. 若需要阶段信息，优先进入 Room 内部 timeline event。
4. 若需要读取能力，优先复用 runtime reader / replay builder。
5. 若需要前端展示，优先复用 protocol / normalizer / extractor / room.js 主状态链。

禁止的扩展方向：

- 另起第二套正式返回协议
- 另起第二套 Room runtime store
- 在组件内部散落协议解析逻辑
- 把 replay 变成 current 的副本状态
- 把审计字段直接外溢为新的正式顶层字段

## 12. 回归检查清单

每次 Room runtime 改动后，至少检查以下事项：

- 成功态是否仍有非空 `response`
- `tool_results` 是否仍是唯一正式结构化出口
- 是否新增了顶层 `result`
- SSE 是否仍只使用 7 个正式事件名
- Room / Workspace 边界是否仍显式可控
- `focus_root` 是否仍被当作边界而非无限授权
- recent runtime 与 replay 是否仍保持职责分离
- Supervisor 审计是否仍与 run 关系链一致

## 13. 结论

Room runtime 的生产稳定性，不靠新增更多临时字段来实现，而靠统一正式字段、统一 SSE、统一边界、统一读模型来实现。

后续任何 Room runtime 改动，只要触及 formal packet、recent runtime、replay、Supervisor 审计或 Workspace 继承，都应先回看本文档，再修改实现与测试。
