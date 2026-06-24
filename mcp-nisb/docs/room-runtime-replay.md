# Room Runtime Replay

## 1. 文档目标

本文档定义 Room runtime 的 recent runtime 与 replay 读取语义，明确 run 选择逻辑、current 与 replay 的隔离关系、result 事件读取方式、relations 与 audit 的表达，以及常见排障方法。

本文档服务于以下目标：

- 保证 current runtime 与 replay 使用同一条 run 事实链。
- 保证 replay 是只读观察态，而不是第二套运行态。
- 保证 recent runtime 的增量读取语义稳定。
- 保证后续前后端都围绕同一 replay bundle 理解数据。

## 2. 概念区分

### 2.1 recent runtime

recent runtime 指针对某个 room 最近一次或指定 run 的运行阶段事件读取，主要用于：

- 当前 run 的实时跟随
- 刷新按钮后的当前增量更新
- 左侧栏与中栏对当前运行期阶段的展示

典型特征：

- 读取目标偏向“当前”或“最近一次”
- 支持 `after_event_id` 增量切片
- 可根据请求 run 与最新 run 之间的关系自动纠偏
- 适合 live polling

### 2.2 replay

replay 指针对某个 run 的历史只读回放读取，主要用于：

- 历史复盘
- 已完成 run 的阶段与结果阅读
- Supervisor 合成链、relations 和 audit 的查看

典型特征：

- 是某个 run 的完整只读视图
- 不应参与 current runtime 的 live 推进
- 不应覆盖当前运行态
- 可携带 phases、result_event、audit、relations 等聚合结果

## 3. run 选择逻辑

### 3.1 recent runtime 的 run 选择

recent runtime 的 run 选择遵循以下逻辑：

1. 从 room 事件集中推导最近一个 runtime run_id。
2. 若请求方未显式指定 `run_id`，则读取推导出的最新 run。
3. 若请求方指定的 `run_id` 已落后于最新 runtime run，则 recent runtime 应自动切换到最新 run。
4. 若 recent runtime 因 run 自动切换而进入新 run，则旧 `after_event_id` 不再可靠，应清空增量锚点再重新读取。
5. 若请求方显式要求 `include_all_runs=true`，则 recent runtime 可返回跨 run runtime 事件，但这不是默认路径。

这套逻辑的目标是：前端在 plan / delegate / worker / supervisor / final 阶段都能自动跟到当前 run，而不是停留在旧 run 上。

### 3.2 replay 的 run 选择

replay 的 run 选择遵循以下逻辑：

1. 如果显式传入 `requested_run_id` 且该 run 存在，则回放该 run。
2. 如果显式传入 `requested_run_id` 但该 run 不存在，则回退到 derived latest runtime run。
3. replay payload 中应同时保留：
   - `requested_run_id`
   - `requested_run_found`
   - `derived_run_id`
   - `run_id`（最终实际使用的 run）

这样做的目的是让前端明确知道：用户请求的是哪个 run，后端最终回放的是哪个 run，以及是否发生了自动回退。

## 4. current 与 replay 隔离

current runtime 与 replay 必须共用同一 run 事实链，但保持不同的使用语义。

### 4.1 current runtime

current runtime 只负责：

- 当前 run 的阶段推进
- 增量读取
- live polling
- 当前结果自动跟随

current runtime 不应：

- 被历史 replay 覆盖
- 被历史 run 的 result_event 污染
- 因切到 replay 而丢失当前 run 事实

### 4.2 replay

replay 只负责：

- 历史 run 只读回放
- 对单个 run 的阶段解释
- result / relations / audit 的聚合展示

replay 不应：

- 推动当前 runtime
- 改写 current run 状态
- 成为新的正式顶层协议
- 替代 recent runtime 的增量读取职责

## 5. replay bundle 结构

一个稳定的 replay bundle 应至少表达以下信息：

- `type`
- `room_id`
- `requested_run_id`
- `requested_run_found`
- `derived_run_id`
- `run_id`
- `status`
- `started_at`
- `finished_at`
- `latest_event_id`
- `event_count`
- `event_types`
- `available_runs`
- `plan_event_id`
- `supervisor_event_id`
- `final_event_id`
- `delegate_total`
- `delegate_roles`
- `plan_summary`
- `final_summary`
- `final_response`
- `events`
- `phases`
- `relations`
- `tool_activity`
- `evidence`
- `audit`
- `room_state_snapshot`

其中：

- `events` 是该 run 的原始 runtime 事件集合。
- `phases` 是面向 UI 的阶段化视图。
- `relations` 表达事件之间的触发关系。
- `tool_activity` 是从阶段事件中抽出的工具活动视图。
- `evidence` 是从阶段事件中抽出的证据视图。
- `audit` 是 Supervisor 审计聚合结果。
- `room_state_snapshot` 是与本次 replay 相关的关键 state 快照。

## 6. phase 语义

Room replay 内部 phase 建议统一为以下类别：

- `plan`
- `delegate`
- `route`
- `worker`
- `supervisor`
- `final`
- `abort`
- `error`
- `runtime`（仅作为兜底）

说明如下：

- `room.plan` -> `plan`
- `room.delegate` -> `delegate`
- `room.route` -> `route`
- `room.message`（非 user）-> `worker`
- `room.supervisor` -> `supervisor`
- `room.final` -> `final`
- `room.abort / room.aborted` -> `abort`
- `room.error` -> `error`

补充规则：

- `route` 可以保留在 replay phases 中，但可标记为 `visible=false`，避免成为主展示阶段噪音。
- `worker` phase 的 actor 优先从 role_name / sender_name / sender 推导。
- `final` phase 是默认 result 事件候选。

## 7. result_event / result_payload / result_text

前端和后端围绕 replay 应统一以下 result 语义：

- `result_event`：最终结果事件对象，优先取 `room.final`。
- `result_payload`：结果事件 payload，若显式提供则优先使用显式值。
- `result_text`：最终展示文本，优先顺序应围绕显式 result 文本、正式 `response`、`content`、`message` 读取。

推荐优先级：

1. 显式 `result_text`
2. replay 顶层 `response / content`
3. `result_payload.response`
4. `result_payload.content`
5. `result_payload.message`

目标是保证 replay 在 UI 中总能稳定读取到一份正式结果文本，而不是依赖组件侧猜测。

## 8. relations 与 audit

### 8.1 relations

relations 用于表达事件之间的依赖关系，常见字段包括：

- `event_id`
- `trigger_event_id`
- `type`
- `phase`

relations 的主要用途：

- 还原 delegate -> worker -> supervisor -> final 的链式关系
- 让 timeline / replay 能准确定位“某条结果由哪条触发”
- 为后续审计和回放排障提供关系基础

### 8.2 audit

audit 优先表达 Supervisor 的受控工具活动与结果归属。

推荐来源顺序：

1. 优先读取显式 supervisor audit relation。
2. 若未找到 relation，再基于 state 构造 snapshot 审计结果。
3. replay 返回的 audit 应尽量稳定，不依赖前端猜测。

audit 主要用于：

- 展示 `fs_read` / `notebook_write` 等受控能力
- 对齐 `run_id / supervisor_event_id / final_event_id`
- 保证 Room 与 Workspace 边界审计可回放

## 9. recent runtime 返回结构

recent runtime bundle 应至少表达：

- `type`
- `items`
- `limit`
- `returned_count`
- `order`
- `run_id`
- `latest_event_id`
- `include_all_runs`
- `after_event_found`
- `message`
- `loaded_at`

recent runtime 的重点不是“聚合解释”，而是“当前 run 的稳定增量读取”。

因此：

- recent runtime 允许更轻量
- replay 允许更聚合
- 但两者必须基于同一 runtime 事件事实链

## 10. 常见排障

### 10.1 sidebar 显示 0 条新增事件

若 recent runtime 返回：

- `after_event_id` 等于 `latest_event_id`
- `after_event_found=true`
- `returned_count=0`

通常表示：

- 当前增量锚点已经追到了尾部
- runtime 没有丢
- 当前只是“暂无新事件”

这属于正常现象，不应误判为 Room runtime 丢失。

### 10.2 requested_run_id 与 derived_run_id 不一致

这通常表示：

- 前端仍持有旧 run_id
- 后端已经推导出更新的 runtime run
- recent runtime 自动纠偏到了最新 run

此时前端应更新 current run 视图，不应继续把旧 replay 状态当作 current。

### 10.3 replay 有结果但 current 无更新

优先检查：

1. current runtime polling 是否仍在运行
2. current 视图是否误停留在 replay 模式
3. `after_event_id` 是否卡在旧 run
4. reader 是否在 room 切换时正确 reset 当前 lane

### 10.4 replay 正常但 UI 阶段顺序异常

优先检查：

1. runtime event 排序是否按 `ts + id` 升序
2. route 是否被错误当成可见主阶段
3. result_event 是否优先取了 `room.final`
4. controller / presenter 是否绕过统一 extractor / normalizer

## 11. 扩展原则

后续扩展 replay 能力时，应遵守以下原则：

- 优先增强 replay builder，而不是组件内临时拼装
- 优先增强 phases / relations / audit 的稳定表达
- 不把 replay 变成第二套 current runtime store
- 不让 replay 结果污染 current runtime lane
- 不在前端组件里散落 result 事件猜测逻辑

## 12. 结论

recent runtime 与 replay 是同一条 Room runtime 事实链的两种只读读取方式。

recent runtime 面向 current 跟随，replay 面向历史复盘。两者必须统一 run 事实、统一字段口径、统一排序规则，同时严格保持职责隔离。
