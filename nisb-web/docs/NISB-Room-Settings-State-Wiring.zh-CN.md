# NISB Room 设置状态接线指南

## 1. 这类接线是什么

NISB Room 设置状态接线，指的是新增一个 Room 设置项时，让它完整走通以下链路：

UI 控件
→ 前端表单状态
→ 设置摘要
→ 保存 payload builder
→ submit 提交
→ 后端可编辑 state 白名单
→ 后端归一化
→ 前端 store 归一化
→ 再次打开设置弹窗回显
→ runtime 读取使用

它不是单纯 UI 接线。
它也不是单纯 runtime 接线。
它是跨前端、后端保存、前端状态回显、runtime 使用的端到端状态接线。

本次 worker 并发数 `max_worker_concurrency` 就是这类接线的标准样例。

## 2. 参考案例

功能：

Room worker concurrency

状态字段：

max_worker_concurrency

允许值：

1, 2, 3, 4

产品含义：

1 = 最稳 / 单 worker 兼容模式
2 = RAG-heavy Room 推荐基准
3 = 高级
4 = 实验

runtime 行为：

- 缺字段时使用默认值。
- 非法值使用默认值。
- 值会被限制在 1..4。
- 服务端 cap 可以进一步限制最终生效值。
- final synthesis 不并发。
- external Room MCP consumer 不暴露内部 worker 调度细节。

## 3. 涉及文件

后端保存状态层：

mcp-nisb/tools/rooms_shared/room_tools_meta.py

前端 UI 层：

nisb-web/src/components/Editor/Room/RoomSettingsOrchestrationCard.vue

前端派生摘要层：

nisb-web/src/composables/editor/room/room_settings_form_derived.js

前端保存 payload 层：

nisb-web/src/composables/editor/room/room_settings_form_patch_builder.js

前端表单状态层：

nisb-web/src/composables/editor/room/use_room_settings_form.js

前端提交层：

nisb-web/src/composables/editor/room/use_room_settings_form_submit.js

前端 i18n 层：

nisb-web/src/locales/en/room.js
nisb-web/src/locales/zh-CN/room.js

前端 store 归一化层：

nisb-web/src/stores/room/room_normalizers.js

如果该设置影响 runtime，还涉及：

mcp-nisb/tools/rooms_shared/room_worker_concurrency.py
mcp-nisb/tools/rooms_shared/room_orchestrator_delegate_flow.py

## 4. 各层职责

### UI 组件

文件：

nisb-web/src/components/Editor/Room/RoomSettingsOrchestrationCard.vue

职责：

- 渲染设置项。
- 直接绑定共享 form 对象。
- 所有用户可见文案走 locale。
- 除非必要，不要维护独立 local state。
- 控件位置应靠近相关设置。

worker 并发数属于 Room orchestration，所以适合放在 reply mode / orchestration 相关区域附近。

### 表单 composable

文件：

nisb-web/src/composables/editor/room/use_room_settings_form.js

职责：

- 定义默认字段。
- 添加客户端归一化。
- 打开弹窗时从 room state 回填。
- 如有旧字段名，兼容读取 alias。
- 导出组件和摘要需要的值。
- 避免非法值长期留在 form 中。

worker 并发数规则：

- 产品默认值为 2。
- 合法值是 1..4。
- 优先使用 `max_worker_concurrency`。
- `worker_concurrency` 只作为兼容 alias 读取。

### 派生摘要

文件：

nisb-web/src/composables/editor/room/room_settings_form_derived.js

职责：

- 生成设置卡片摘要。
- 使用和 form 一致的归一化值。
- 不单独发明另一套校验规则。

worker 并发数应出现在摘要中，方便用户一眼确认当前配置。

### Payload builder

文件：

nisb-web/src/composables/editor/room/room_settings_form_patch_builder.js

职责：

- 把 form 转成后端保存 payload。
- 包含新增字段。
- 发送前归一化。
- 使用后端认可的 canonical field name。

worker 并发数必须写入：

max_worker_concurrency

如果这里漏掉字段，UI 可以显示，但保存不会生效。

### Submit composable

文件：

nisb-web/src/composables/editor/room/use_room_settings_form_submit.js

职责：

- 提交前做最终归一化。
- 把 normalizer 传给 patch builder。
- 确保保存 action 收到完整 state payload。
- 保留用户显式选择。

worker 并发数中，用户选择的 1、2、3、4 都必须在 submit 后保持原值。

### 后端保存 state metadata

文件：

mcp-nisb/tools/rooms_shared/room_tools_meta.py

职责：

- 把新增字段加入可编辑 state 白名单。
- 在后端做归一化。
- clamp 或校验值。
- 持久化到 Room state。
- 保存响应里返回归一化后的字段。

worker 并发数要求：

- 将 `max_worker_concurrency` 加入 editable state keys。
- 转成整数。
- 限制到 1..4。
- 缺失或非法时默认 2。

如果 UI 保存后短暂显示新值，然后被刷新回默认值，优先检查这个文件。

### 前端 store normalizer

文件：

nisb-web/src/stores/room/room_normalizers.js

职责：

- 保留后端返回的字段。
- 进入 Pinia store 前归一化。
- 必要时兼容旧 alias。
- 确保再次打开设置弹窗时能读到保存值。

worker 并发数中，`normalize_room_state()` 必须返回：

max_worker_concurrency

读取方式应支持：

src.max_worker_concurrency ?? src.worker_concurrency

如果后端 response 正确，但设置弹窗仍回默认值，优先检查这个文件。

### Locale 文件

文件：

nisb-web/src/locales/en/room.js
nisb-web/src/locales/zh-CN/room.js

职责：

- 提供所有用户可见文案。
- 提供 hint 和 option label。
- 保持 UI 双语。
- 避免在非 locale 源码里硬编码中文。

worker 并发数至少包含：

- 标题
- 说明
- 选项 1 文案
- 选项 2 文案
- 选项 3 文案
- 选项 4 文案

## 5. 实施 checklist

未来新增任何 Room setting，都按这个 checklist 走：

- 选择一个 canonical field name。
- 加到前端默认 form。
- 添加客户端 normalizer。
- 添加打开弹窗时的回填逻辑。
- 添加 UI 控件。
- 如有必要，添加设置摘要。
- 添加 locale 文案。
- 加到 patch builder。
- 添加 submit 前归一化。
- 加到后端 editable-state 白名单。
- 添加后端归一化。
- 加到前端 store normalizer。
- 确认保存 response 包含字段。
- 确认再次打开弹窗能回显。
- 确认浏览器刷新后仍能保留。
- 如果 runtime 使用该字段，确认 runtime 能读到。

## 6. 调试 checklist

### UI 不显示

检查：

- RoomSettingsOrchestrationCard.vue
- locale keys
- composable return values

### UI 能改，但保存 payload 没字段

检查：

- room_settings_form_patch_builder.js
- use_room_settings_form_submit.js

### 保存 payload 有字段，但 response 没字段

检查：

- room_tools_meta.py

### response 有字段，但 store 没字段

检查：

- room_normalizers.js

### store 有字段，但再次打开弹窗回默认值

检查：

- use_room_settings_form.js
- room opening / fill form logic

### 弹窗保存和回显都正常，但 runtime 不生效

检查：

- runtime reader
- runtime request args
- runtime state snapshot
- backend execution path

## 7. 参考 grep 命令

前端全链路 grep：

```bash
grep -RIn "max_worker_concurrency\\|worker_concurrency" \
  /opt/mcp-gateway/nisb-web/src/components/Editor/Room \
  /opt/mcp-gateway/nisb-web/src/composables/editor/room \
  /opt/mcp-gateway/nisb-web/src/stores/room \
  /opt/mcp-gateway/nisb-web/src/locales
```

后端保存 state grep：

```bash
grep -RIn "max_worker_concurrency\\|worker_concurrency" \
  /opt/mcp-gateway/mcp-nisb/tools/rooms_shared/room_tools_meta.py
```

后端 runtime grep：

```bash
grep -RIn "max_worker_concurrency\\|worker_concurrency" \
  /opt/mcp-gateway/mcp-nisb/tools/rooms_shared \
  --exclude-dir=__pycache__
```

## 8. 验收命令

前端构建：

```bash
cd /opt/mcp-gateway/nisb-web
npm run build
```

后端编译：

```bash
cd /opt/mcp-gateway/mcp-nisb
python3 -m py_compile tools/rooms_shared/room_tools_meta.py
```

如果改过 runtime 文件：

```bash
python3 -m py_compile tools/rooms_shared/room_worker_concurrency.py
python3 -m py_compile tools/rooms_shared/room_orchestrator_delegate_flow.py
```

查找服务名：

```bash
systemctl list-units --type=service | grep -Ei 'nisb|mcp|gateway'
```

然后重启实际部署使用的服务。

## 9. UI 验收

以 worker 并发数为例：

- 打开 Room settings modal。
- 确认默认值是 2。
- 改成 1 并保存。
- 再次打开，确认仍是 1。
- 改成 2 并保存。
- 再次打开，确认仍是 2。
- 改成 3 并保存。
- 再次打开，确认仍是 3。
- 改成 4 并保存。
- 再次打开，确认仍是 4。
- 刷新浏览器。
- 再次打开，确认最后保存值仍然存在。

## 10. Runtime 验收

以 worker 并发数为例：

- 保存 1，确认走串行 / 单 worker 行为。
- 保存 2，确认走 bounded concurrency 行为。
- 3 或 4 仅作为高级测试。
- 确认 final synthesis 仍然串行。
- 确认结果顺序稳定。
- 确认 LibreChat Room MCP 仍能收到最终答案。
- 确认 external consumer payload 不暴露内部 worker 调度细节。

## 11. 常见失败特征

### 短暂显示选择值，然后回默认值

含义：

后端或前端 store reload 覆盖了 optimistic form state。

按顺序检查：

1. 后端保存 response 是否包含字段。
2. room_tools_meta.py 是否允许保存字段。
3. room_normalizers.js 是否保留字段。

### 永远显示默认值

含义：

保存字段不存在于 room state，或打开弹窗时 form 无法读到。

检查：

1. 后端 response。
2. store state。
3. form composable 中的 `pick_*_from_state` 函数。

### runtime 忽略保存值

含义：

设置状态接线已经成功，但执行路径没有读取字段。

检查：

1. runtime request args。
2. runtime control snapshot。
3. runtime helper 中的字段归一化逻辑。

## 12. 未来 Room setting 规则

- 使用一个 canonical field name。
- alias 只做兼容读取，除非需要迁移。
- 前端和后端都要 normalize。
- 即使前端已经 clamp，后端也必须 clamp。
- 不要把内部 runtime 设置暴露给 external Room MCP consumer，除非明确设计。
- UI-only setting 不要改变 Room MCP payload shape。
- 源码注释和逻辑尽量使用英文。
- 用户可见文案进入 locale。
- 缺字段的旧 room 必须兼容。
- settings-state wiring 和 runtime protocol change 要分开处理。
