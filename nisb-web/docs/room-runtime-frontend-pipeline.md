# Room Runtime Frontend Pipeline

## 1. 文档目标

本文档定义 Room runtime 在前端的正式消费主链，明确 `room.js` 单一主状态源、protocol / normalizer / extractor 的职责、chat_panel Room controller 的接线职责，以及 LeftSidebar / RoomRuntimePanel 的消费边界。

本文档的核心目标是：

- 防止 Room runtime 在前端再长出第二套状态主链
- 防止协议解析逻辑散落回组件
- 保证 current / replay / sidebar / panel 围绕同一读模型工作
- 为后续 S5-P2 runtime 回归测试提供统一实现口径

## 2. 单一主状态源

Room 前端 formal-first 主状态单源是：

- `/opt/mcp-gateway/nisb-web/src/stores/room.js`

以及其拆分模块：

- `src/stores/room/room_protocol.js`
- `src/stores/room/room_normalizers.js`
- `src/stores/room/room_extractors.js`
- `src/stores/room/room_event_helpers.js`
- `src/stores/room/room_actions_*.js`
- `src/stores/room/room_state.js`

必须坚持以下原则：

- 所有 Room runtime 正式读取优先经过 room store 主链。
- 不在组件内部复制第二套正式 runtime store。
- 不在多个 composable 中各自维护一份正式协议解析逻辑。
- current / replay 的正式展示状态应尽量从 room store 派生，而不是临时拼装。

## 3. protocol / normalizer / extractor 职责分层

### 3.1 room_protocol.js

`room_protocol.js` 负责：

- formal-first 顶层返回解析
- `status` 归一化
- `tool_results` 归一化
- `assert_tool_success` 失败识别
- `unwrap_tool_result` 与 `pick_first_tool_result`

它解决的是“服务端返回长什么样”的问题。

原则：

- 优先读取正式字段；
- 兼容嵌套 `tool_results[].payload`；
- 兼容 legacy `success`；
- 但不能把 legacy 重新升格为主判断入口。

### 3.2 room_normalizers.js

`room_normalizers.js` 负责：

- state 归一化
- runtime bundle 归一化
- replay bundle 归一化
- path / filename / mcp_overrides / reply_mode 归一化
- current / replay 视图模式归一化

它解决的是“把数据变成稳定前端结构”的问题。

原则：

- 所有边界字段都在这里统一收口；
- 所有 current / replay 默认值都在这里稳定定义；
- 不把组件局部判断变成协议真相。

### 3.3 room_extractors.js

`room_extractors.js` 负责：

- 从 formal packet 的 `tool_results` 中提取 room info
- 提取 whoami
- 提取 room items bundle
- 提取 current runtime bundle
- 提取 replay bundle

它解决的是“从 formal packet 里把业务 payload 找出来”的问题。

原则：

- 优先识别显式 type
- 再识别结构标志
- 最后才回退 unwrap
- 不让组件自己扫原始 tool_results

## 4. room.js 的读模型职责

`room.js` 及其子模块应承担以下职责：

- 统一保存 room / roles / roomState / items / itemsPaging
- 统一保存 runtimeState
- 统一保存 currentRunId / currentRunStatus
- 统一保存 replay 视图状态
- 统一提供 recent runtime 与 replay 的正式读取结果
- 统一承接 Room 主链和 LeftSidebar / Panel 的共享读模型

不应让 `room.js` 承担的职责：

- UI 组件布局判断
- 散落的协议解析细节
- 组件本地私有展示状态
- 非 Room 正式主链的临时试验逻辑

## 5. chat_panel 接线职责

### 5.1 use_chat_panel_room_controller.js

`use_chat_panel_room_controller.js` 是 chat_panel 与 Room runtime 之间的主接线层。

它负责：

- 识别是否处于 Room mode
- 跟踪当前 `activeRoomId`
- 复用 `useRoomStore()`
- 读取 current / replay 相关派生状态
- 统一暴露 runtime 结果文本、结果事件、过程项、运行状态文本
- 委托 `use_chat_panel_room_runtime_reader.js` 处理 runtime 读取、切换、polling、replay 读取

它不应负责：

- 再写第二套 runtime store
- 在组件内部重新解析协议
- 越过 store 直接定义新的 formal payload 结构

### 5.2 use_chat_panel_controller.js

`use_chat_panel_controller.js` 负责 chat_panel 顶层模式接线。

它负责：

- 普通 chat 与 Room mode 切换
- `convId` 与本地对话加载
- Room mode 下的 runtime polling 接线
- Room 切换时的 runtime bootstrap
- 用户发言后对 current runtime 的 nudge
- 将 room controller 提供的 runtime 视图能力暴露给 UI

它不应负责：

- 重写 room runtime reader 的核心逻辑
- 在这里拼 replay 数据
- 依赖中栏 panel 是否渲染来决定 runtime 是否存在

## 6. runtime reader 职责

前端 runtime reader 的职责应集中在专门的 reader/composable 中，而不是分散到多个组件。

reader 应负责：

- current runtime recent 读取
- replay 读取
- room 切换时 reset runtime lane
- current 与 replay 视图切换
- polling 调度与停止
- latest run 自动跟随
- after_event_id / tail_event_id 等运行锚点维护

reader 不应负责：

- Room store 主结构定义
- 组件样式判断
- 协议顶层解析
- 手工推断 tool display name

## 7. sidebar 与 panel 的消费边界

LeftSidebar runtime 展示和 `RoomRuntimePanel.vue` 必须消费同一条 Room runtime 读模型，不得各自维护独立 mapper。

正确做法：

- sidebar / panel 都从统一 store / controller / presenter 读取
- current 与 replay 使用同一套 normalized bundle
- result_event / result_payload / result_text 使用统一 reader
- tool_activity / evidence / audit 使用统一 replay 语义

错误做法：

- sidebar 自己扫 room events 拼阶段
- panel 自己再扫一遍 runtime items
- 组件内定义第二套 phase 命名
- 为了 UI 临时效果改写 formal packet 解释规则

## 8. polling 与 replay 规则

### 8.1 current polling

current runtime polling 规则如下：

- 仅在 Room mode 且存在 activeRoomId 时启动
- 用户发送新消息后应立即 nudge current runtime
- room 切换后应立即对新 room 做 bootstrap 读取
- 当 reader 判断当前 room 应继续轮询时，controller 只负责调度，不重复定义判断逻辑
- current runtime 应优先跟随最新 run，而不是停留在历史 replay 选中项上

### 8.2 replay 模式

replay 规则如下：

- replay 是只读模式
- replay 不应被 current polling 覆盖
- replay 选中的 run_id 应与 current run lane 分离
- 切回 current 时，应恢复 current runtime lane 的正式读取
- replay 不应污染 `currentRunId / currentRunStatus`

## 9. formal-first 前端读取规则

前端读取 Room runtime 数据时，遵守以下顺序：

1. 先经 `room_protocol.js` 做 formal packet 级解析。
2. 再经 `room_extractors.js` 抽取业务 bundle。
3. 再经 `room_normalizers.js` 归一化 current / replay / state。
4. 最后由 store / controller / presenter 暴露给 sidebar / panel / chat_panel UI。

禁止的反模式：

- 组件直接扫原始 `tool_results`
- 组件直接依赖 legacy `success`
- 在多个 composable 内各写一份 room runtime payload 解析
- 用 UI 代码决定正式字段含义

## 10. 常见反模式

以下做法应明确禁止：

- 新长第二套 Room runtime store
- 在 `RoomRuntimePanel.vue` 内部散落协议解析
- 在 LeftSidebar 内部散落事件映射
- 为了兼容临时数据，在组件里新增特殊字段判定
- 让 panel 是否挂载决定 runtime 是否轮询
- replay 与 current 共用同一个“当前 run 可变对象”并互相覆盖
- 前端继续猜“未命名工具”，而不是优先让后端补齐 tool naming

## 11. 回归检查清单

每次前端改动 Room runtime 主链后，至少检查：

- Room mode 切入时 current runtime 是否正确 bootstrap
- Room 切换后 sidebar 是否自动切换且不串房
- 退出 room 后 runtime 是否自动消失
- 用户发言后 current runtime 是否立刻 nudge 并继续 polling
- replay 是否仍只读且不污染 current
- result_event / result_payload / result_text 是否仍由统一读模型给出
- `status / response / tool_results` formal-first 读取是否未破坏
- `assert_tool_success` 是否仍能识别嵌套失败信号
- 是否有新的协议解析逻辑散落回组件

## 12. 推荐扩展路径

后续若要继续增强 Room runtime 前端能力，推荐顺序如下：

1. 优先补 store / protocol / normalizer / extractor / controller 的测试
2. 再补 presenter 层
3. 再补 sidebar / panel 展示层
4. 最后才考虑更大 UI 调整

原因是：

- 先固化读模型，才能保证不同展示层共用一条主链
- 先固化 current / replay 语义，才能避免“功能增强”变成“再长第二套 runtime”
- 先固化 polling / lane reset，才能避免进入房间、切换房间、退出房间时回归

## 13. 结论

Room runtime 前端不是某个组件的局部功能，而是 Room 主运行容器在前端的正式读模型消费链。

只有坚持 `room.js` 单一主状态源、protocol / normalizer / extractor 分层、controller 只做接线、sidebar / panel 共用同一读模型，才能让 current / replay / audit / tool activity 在后续扩展中持续稳定。
