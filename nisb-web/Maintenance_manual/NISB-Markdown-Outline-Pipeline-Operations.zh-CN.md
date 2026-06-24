# NISB Markdown 大纲管线运维手册
版本：v2026-05-r2
范围：NISB 前端 note / chat / epub / 左侧栏 / timeline / workspace 中，与 Markdown 预览、大纲导航、快速切换、工作空间快照恢复相关的稳定性链路

## 1. 目的

本文用于说明 NISB 前端以下稳定性主链路的长期维护方式：

- Markdown 预览
- 右侧栏大纲生成
- LazyMarkdown
- 大纲跳转
- timeline 快速切换
- workspace 快照 apply / restore
- 文件树与 favorites 刷新稳定性
- Firefox 卡死概率治理

这是一份运维与维护手册，不是功能介绍。它的目标是帮助后续维护者在不破坏 note / chat / epub / library / workspace 五条主链路契约的前提下，做阈值微调、回归修复、同步阻塞治理与长期可维护改造。

---

## 2. 当前实践结论

### 2.1 Markdown 大纲结论

超长 Markdown 稳定链路已经在真实使用中被证明是快速、稳定、可靠的，包括非常长的 Markdown 文档。

当前真正的问题不是强链路慢，而是旧阈值过高，导致一批中大型 Markdown 文件仍停留在弱链路灰区，从而出现大纲不完整、首次打开不同步、跳转不稳定等问题。

### 2.2 推荐阈值

当前推荐的大纲稳定链路阈值为：

- **2000 行**

如果当前预览链路尚未完全同步到位，可以暂时先落在 3000 行，但长期推荐值仍然是 2000 行。

### 2.3 timeline / workspace 结论

在第二轮对左侧栏、文件树 controller、workspace 切换链路完成加固后，Firefox 压测下的实际稳定性有了非常明显的提升。

在人工高压测试中，连续快速切换 txt / epub / pdf / md，多次在文件空间与 timeline 之间来回切换，并穿插 workspace 切换，当前观察到的测试轮次里没有再复现此前的标签页卡死现象。

### 2.4 这意味着什么

这**不**代表系统在所有未来极限场景下都已经绝对安全。

它意味着当前实现大概率已经消除了一个或多个关键的同步阻塞放大点，后续重点应转向“极低概率的累积型卡死”排查，而不是回滚当前已经验证有效的加固方向。

---

## 3. 文档策略建议

**不要单独再起一份“第二轮手册”。**

第一轮与第二轮现在已经属于同一条稳定性主链：

- Markdown 大纲稳定性
- 快速切换正确性
- stale 任务失效保护
- workspace apply 编排
- file tree / favorites 刷新次序
- Firefox 阻塞风险治理

因此这份文档应继续作为唯一主手册，通过版本升级维护，而不是按轮次拆散。

---

## 4. 不可破坏的契约

### 4.1 唯一锚点契约

每个标题必须遵循：

- `base = slug(clean(heading_text))`
- `occ = 同 base 的出现序号，从 1 开始`
- `anchor_key = ${base}--${occ}`
- 若 `base` 为空：`anchor_key = h--${occ}`

这是稳定大纲跳转的根契约。

### 4.2 预览 DOM 契约

预览 DOM 中每个 heading 必须同时具备：

- `id="heading-${anchor_key}"`
- `data-heading-key="${anchor_key}"`
- `data-heading-anchor="${base}"`

右侧栏点击跳转、hover 预跳转、同名标题去重命中、LazyMarkdown 渐进加载都依赖这些属性。

### 4.3 右侧栏事件契约

以下事件名必须保持兼容：

- `nisb-outline-context`
- `nisb-outline-jump`
- `nisb-outline-mode-changed`
- `nisb-chat-outline-update`
- `nisb-epub-outline-update`
- `nisb-outline-hover-enabled-changed`

### 4.4 `NoteOutlinePanel` 多源契约

`NoteOutlinePanel.vue` 同时服务：

- note
- chat
- epub

任何 note 侧修复都不能静默覆盖 chat 或 epub 的来源状态。

### 4.5 LazyMarkdown 契约

`LazyMarkdown.vue` 必须继续支持：

- chunk 懒加载
- heading anchor 索引
- `jumpTo({ anchor_key, base_anchor, occ, text })` 或等价接口
- 向未渲染区域推进加载
- 必要时升级为全文内容与索引重建

### 4.6 Workspace `files_state v3` 契约

workspace 状态必须继续区分：

- `saved`
- `current`

语义要求：

- 切 workspace 必须 apply：`saved -> current`
- 只有 workspace 保存动作允许改写 `saved`
- favorites 仍由 favorites 工具负责
- `focused_root_path` 的前端持久化只能更新 `current`

### 4.7 localStorage 契约

以下 localStorage key 只能是辅助态：

- `nisb_current_workspace_id`
- `nisb_fs_focus_root_{workspace_id}`
- `nisb_fs_state_{workspace_id}`

它们只是便捷缓存，不是真源。

---

## 5. 稳定性规则

### 5.1 全链路 latest-only

所有高频路径都必须按 latest-only 路径处理：

- file open
- file read
- markdown parse
- outline full-read
- outline cache 落地
- timeline 文档切换
- workspace apply
- favorites refresh
- file tree refresh
- focus-root restore
- preview jump 执行

统一规则：

- 每次新操作都创建新的 `seq` 或 `runId`
- 在每个关键阶段检查
- 在 UI 落地前再检查一次

### 5.2 宁可 stale，不可错误落地

在快速切换压力下，允许短暂 stale。

不允许旧大纲、旧文件树状态、旧 workspace 状态错误落到新目标上。

### 5.3 不要把重工作堆进同一轮事件链

以下工作不要堆在同一轮同步事件链中：

- workspace apply
- `nisb_file_focus_root` / clear
- favorites refresh
- file tree refresh
- timeline 打开链路
- 大量 localStorage 写入

可拆开的必须拆成分 tick 落地。

### 5.4 idle 任务必须带 timeout

所有低优先级 idle 写任务都必须带 timeout 保护。

这尤其适用于辅助缓存和 UI 状态持久化。

### 5.5 localStorage / sessionStorage 使用规则

storage 必须始终保持：

- 小体积
- 低频
- 可丢弃
- 可再生

绝不能扩张成高频、大体积、权威态链路。

---

## 6. 关键文件

### 6.1 Markdown / 大纲主文件

- `/src/components/RightSidebar/NoteOutlinePanel.vue`
- `/src/components/LazyMarkdown.vue`
- `/src/composables/editor/useEditorController.js`
- `/src/composables/editor/modules/useEditorOutlineBridge.js`
- `/src/composables/editor/modules/useEditorMarkdownPreview.js`
- `/src/composables/editor/modules/useEditorNavigationEvents.js`
- `/src/components/Editor/NotePane.vue`
- `/src/utils/storage_safe.js`

### 6.2 左侧栏 / workspace 主文件

- `/src/components/LeftSidebar.vue`
- `/src/components/LeftSidebar/TimelineView.vue`
- `/src/components/LeftSidebar/FileBrowser.vue`
- `/src/composables/left_sidebar/file_browser/use_file_browser_controller.js`
- `/src/composables/left_sidebar/use_left_sidebar_workspaces.js`

### 6.3 必要时涉及的后端文件

- `/tools/workspace/__init__.py`
- 后端 favorites 工具实现文件

---

## 7. 第二轮后的当前基线

### 7.1 大纲链路基线

Markdown 大纲稳定链路应更早接管，中长期推荐值以 2000 行为中心。

之所以优先走强链路，是因为它已经被证明比让中大型 Markdown 停留在普通弱链路灰区更稳定、更可靠。

### 7.2 左侧栏基线

左侧栏加固后，应继续保持以下工程方向：

- load / refresh latest-only
- 减少同步事件堆叠
- 合理延迟或拆分 refresh 发射
- 不再进行高频同步 storage 写入
- 将 workspace 切换视为有状态编排过程，而不是单个点击事件

### 7.3 workspace 切换基线

workspace apply 必须理解为多阶段编排，而不是一个前端同步 tick：

1. apply 当前 workspace 快照
2. 恢复 focused root
3. 刷新 favorites
4. 刷新 file tree
5. 更新辅助 current-workspace 缓存
6. 持久化后端 current workspace

这些步骤必须避免旧任务落地，也要避免同 tick 重工作叠加。

### 7.4 Firefox 基线

从当前实践测试看，在高强度人工切换下，系统已经接近生产可用。

后续加固重点应放在低概率累积型边界问题，而不是回退当前这条已验证有效的稳定化方向。

---

## 8. 调优原则

### 8.1 什么时候优先降阈值

如果出现以下情况，应先降阈值：

- 2000–5000 行 Markdown 仍停留在弱链路
- 大纲不完整
- 首次打开不同步
- 同一批文件在强链路稳定、在弱链路不稳定
- 已知强链路本身足够快

### 8.2 什么时候阈值不是主因

以下情况不要优先怪阈值：

- 大纲已生成，但点击跳不到
- 同名标题跳错
- chat / epub 被 note 覆盖
- Firefox 在 workspace 与 timeline 联动时卡死
- file tree 与 workspace 状态互相串态

这些通常是 latest-only、DOM 契约、jump bridge、同步阻塞或编排问题。

### 8.3 推荐调优顺序

若后续还需继续调优，建议顺序为：

1. `NoteOutlinePanel.vue`
2. `useEditorController.js` / `useEditorOutlineBridge.js`
3. `LazyMarkdown.vue` / `useEditorMarkdownPreview.js`
4. `FileBrowser.vue`
5. `use_file_browser_controller.js`
6. `use_left_sidebar_workspaces.js`
7. `LeftSidebar.vue`
8. 若前端 apply 语义仍与真源不一致，再查后端 workspace 工具

---

## 9. 最短排障路径

### 9.1 现象：首次打开显示上一个文件的大纲

按顺序检查：

1. `nisb-outline-context` 是否带了 `content_text`
2. Vue flush 边界后是否仍有 re-emit
3. `NoteOutlinePanel.vue` 是否优先使用传入内容
4. 是否错误回退到旧 cache
5. 右侧栏与预览区是否仍指向同一文档

### 9.2 现象：大纲有了，但跳转失败

按顺序检查：

1. `anchor_key = base--occ`
2. 预览 DOM 属性是否完整
3. `nisb-outline-jump` 负载是否完整
4. LazyMarkdown `jumpTo()` 是否还正常
5. 普通预览 fallback 查找链路是否仍守约

### 9.3 现象：反复切换后越来越慢

按顺序检查：

1. 是否仍有同步 localStorage 写入
2. 是否仍有 stale 任务落地
3. 是否有重复全文 parse 尖峰
4. 是否有 refresh 循环
5. idle 任务是否缺 timeout
6. timeline 与 workspace refresh 是否互相放大

### 9.4 现象：Firefox 标签页完全失去响应

按顺序检查：

1. 同步 storage 写入
2. latest-only 失效
3. 重工作堆进同一轮同步事件链
4. workspace apply 与 timeline open 重叠且缺失失效保护
5. 旧 file tree 或 favorites refresh 在新切换后仍落地
6. 是否意外退回 eager 全量渲染

---

## 10. i18n 要求

当前子系统处于中英双语切换阶段。

规则如下：

- 新 UI 文案优先走 i18n key
- 不要继续散落新增硬编码文案
- 纯功能修复不要求立刻重构旧字符串
- 但新增状态提示、警告、降级提示、调试提示必须同时进中英文 locale

---

## 11. 最低回归清单

### 11.1 Note 普通 Markdown

- 1000 行以下仍正确生成大纲
- 首次打开同步
- 不残留上一个文件的大纲

### 11.2 Note 中大型 Markdown

- 2000–3000 行必须进入稳定链路
- 3000–7000 行保持稳定
- click / hover 跳转正确

### 11.3 超长 Markdown

- 7 万行链路不回退
- 大纲仍完整
- 同名标题仍能唯一命中

### 11.4 chat / epub

- chat 大纲来源正确
- epub 大纲来源正确
- 两者都不被 note 逻辑覆盖

### 11.5 timeline / workspace 压测

- txt / epub / pdf / md 快速切换
- timeline 与文件空间反复来回
- 在快速切文档中穿插 workspace 切换
- 不出现明显 stale 错落地
- 不出现明显累积变慢
- Firefox 标签页在正常高压操作下不应长时间失去响应

### 11.6 左侧栏

- workspace apply 正确恢复 `saved -> current`
- favorites refresh 正确
- file tree refresh 正确
- focus-root restore 正确
- 不出现 workspace 串态

### 11.7 顶部控制

- 全部折叠 / 展开可用
- hover 开关可用
- stale 状态必要时能暂时阻断交互，并在 ready 后恢复

---

## 12. 运维结论

当前阶段的实际结论是：

1. 超长 Markdown 稳定链路应覆盖更多文件，而不是更少
2. 2000 行是更适合当前生产实践的阈值
3. 第二轮左侧栏 / workspace 加固在 Firefox 压测中带来了非常明显的实际改善
4. 当前方向应继续巩固，而不是回滚
5. 后续加固应优先关注低概率累积型边界问题与契约纪律

---

## 13. 给维护者的一句话规则

优先让中大型 Markdown 进入稳定链路，而不是留在普通灰区；宁可短暂 stale，也不要错误落地；优先 latest-only；优先保守缓存与调度策略，避免重新引入同步阻塞风险。
