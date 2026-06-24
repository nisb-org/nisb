# NISB

**NISB 是自托管 AI 工作区：把 Markdown 笔记、文件、RSS、证据检索和 Room 编排连接起来，并可发布为可复用的 MCP 能力。**

NISB 也是一个让 Room 成为可调用、可共享、可撤销、可组合 MCP capability 的自托管工作空间。

它把日常 Markdown / 文件工作区、长期知识库、RSS-to-RAG 工作流、证据型搜索、supervisor/worker Rooms、MCP 发布、NISB-to-NISB federation，以及小型 VPS 部署模型组合到一个系统里。

NISB 不只是一个聊天界面。它的核心抽象是 Room：一个感知 workspace 的智能体运行时，可以绑定 workspace context、知识源、workers、MCP providers、RAG/RSS 工作流和外部访问策略。

一个 Room 可以在本地使用，也可以发布为标准 MCP capability，被 LibreChat、MCP Inspector 等外部客户端调用；也可以通过 NISB federation 共享、被 owner 撤销，并作为 worker capability 组合进其它 Room。

---

## NISB 是什么

NISB 由几条能力线组成：

- 自托管 AI 工作区。
- 日常 Markdown 笔记与文件工作台。
- 用于管理项目、目录、文件、笔记、证据和 Room 的 workspace control center。
- 横跨 chat、directories、files、libraries 的四源搜索。
- RAG libraries 和基于证据的回答。
- RSS 订阅与 RSS-to-RAG 工作流。
- 基于 Room 的 AI 工作流，包含 supervisor 和 workers。
- MCP provider 绑定。
- Room 发布为外部 MCP capability。
- NISB-to-NISB federation 和 imported remote capabilities。
- 可组合的 Room capabilities，可作为 worker 被其它 Room 复用。
- 基于 Docker Compose + Caddy 的单 VPS 部署模型。

NISB V1 的目标不是玩具 demo，而是提供一个可日常使用、可长期运行、可迁移、可维护、可继续扩展的自托管基础系统。

---

## 为什么 Room 重要

大多数 AI 工具把聊天线程作为主要交互单位。

NISB 把 Room 作为主要工作单位。

一个 Room 可以：

- 绑定 workspace 和 focus root。
- 使用 supervisor/worker runtime。
- 绑定 RAG 或 RSS-RAG 知识源。
- 绑定 MCP providers。
- 使用本地文件、笔记、证据、side-memory 和 notebook。
- 保持 workspace context。
- 为外部客户端输出 final answer。
- 发布为 MCP capability。
- 通过 federation 被其它 NISB 节点共享或消费。
- 由 owner 撤销或设置过期。
- 被组合进其它 Room，作为 worker capability 使用。

所以 Room 不只是一次对话，而是一个可复用、可控制、证据感知、可联邦化的能力单元。

---

## 核心功能

### Workspace

- 自托管 Web 工作空间。
- 日常 Markdown notes 和文件工作流。
- Workspace-first UI，包含文件、libraries、feeds、notes、evidence 和 Rooms。
- Workspace control center，用于管理、切换、聚焦目录。
- Focus snapshot 支持。
- 收藏、置顶/常用、内部链接、预览刷新、workspace 状态保存/清空。
- 文件和目录 focus。
- 文档结构导航。
- 持久化运行数据目录。
- 面向长期个人使用和迁移。

### 文档与知识库

- Document / library 工作流。
- 本地知识组织。
- 面向 RAG 的文档使用。
- 基于证据的交互。
- 支持 Markdown、EPUB、Office documents、text files 和文档入库工作流。
- 面向阅读、研究和长期知识工作的基础能力。

### 搜索

- 横跨 chat、directories、files、libraries 的四源搜索。
- 聚合搜索结果，并支持跳转和 focus。
- 面向小型 VPS 日常使用的本地 workspace search。
- 面向 documents、libraries 和 global workspace context 的 evidence-oriented search。

### RSS 与 RAG

- RSS 订阅。
- RSS-to-RAG 工作流。
- RSS gate，支持定时清理和定时入库到指定 library，用于更新鲜的 RAG workflow。
- RAG libraries 和 groups。
- Doc / library / cross-library search，用于证据型工作流。
- 支持 citation、source、span navigation 的场景。
- Library home，包含 bookmark 和 annotation overview。
- 基于证据的回答。
- Room worker 可以连接 RAG 或 RSS-RAG sources。

### Rooms

- 基于 Room 的 AI 工作流。
- Workspace-aware Room runtime。
- Supervisor 和 worker orchestration。
- Role configuration。
- Provider binding。
- Workspace binding。
- Evidence binding。
- MCP binding。
- Runtime visibility。
- Room workflow 的 side-memory continuity。
- Room notebook 支持。
- Room 级 Shared Auto Reply。
- 四种 reply modes：silent、supervisor plus workers、direct worker、direct supervisor。

### MCP

- MCP provider binding。
- Room 可发布为标准外部 MCP capability。
- 可被 LibreChat、MCP Inspector 等 MCP client 调用。
- Bearer token 访问控制。
- Token 生命周期能力，包括 expiry、revoke/regenerate、max calls、used count、last used time。
- Published Room 可对外提供 final-only reply。
- Room-scoped capability publishing，不暴露 owner 的 private workspace、private filesystem 或 private memory。

### Federation

- NISB-to-NISB federation。
- Imported remote capabilities。
- Federated MCP / federated Room workflows。
- Owner-managed room grants。
- Grant 状态包括 active、revoked、expired。
- Token expiry、max calls、used count、client label、endpoint tracking。
- Revoke 后立即失权。
- 在不开放整个 workspace 的前提下跨节点共享 Room capability。

### 可组合能力

- Federation member 可以 import owner 发布的 Room MCP capability。
- Member Room 可以把 imported capability 当作 MCP worker 使用。
- Member Room 可以把 remote Room capabilities 与本地 RAG、本地 workers、MCP tools、supervisor logic、workspace context 叠加。
- 组合后的 Room 可以再次发布为新的 Room capability。
- 这是 capability graph 和 capability runtime 的雏形，不只是一个独立 MCP server。

---

## NISB 不是什么

NISB 不是又一个普通 ChatGPT-style 界面。

它也不应该被描述成 LibreChat、Dify、Open WebUI、AnythingLLM、Obsidian、Logseq、Notion 或其它 AI / PKM 平台的直接替代品。

更准确的理解方式是：

- LibreChat 是很强的 MCP-capable chat client 和 AI conversation platform。
- Obsidian 和 Logseq 是 note-first PKM tools。
- Dify 是很强的 workflow 和 application builder。
- NISB 关注的是 self-hosted AI workspace、evidence layer、workspace-aware Rooms、MCP publishing、federation 和 composable capability sharing。

NISB 可以和这些工具协同。例如，一个 NISB Room 可以发布为 MCP，然后被 LibreChat 调用。

---

## 部署模型

NISB 面向小型 VPS 的长期稳定运行。

推荐部署模型：

- 一台 Ubuntu VPS。
- Docker Compose 负责服务编排。
- Caddy 负责反向代理和 HTTPS。
- 项目源码放在 `/opt/mcp-gateway/nisb`。
- 持久化运行数据放在 `/opt/nisb-data`。

这个模型优化的是：

- 稳定性。
- 易回滚。
- 低运维复杂度。
- 可复现安装。
- 从旧 VPS 到新 VPS 的清晰迁移。

---

## 快速开始

典型手工部署流程：

1. 准备一台全新的 Ubuntu 24.04 VPS。
2. 配置 DNS，例如使用 Cloudflare。
3. 安装 Docker Engine 和 Docker Compose v2。
4. 上传或 clone 项目到 `/opt/mcp-gateway/nisb`。
5. 准备 `/opt/nisb-data` 持久化数据目录。
6. 复制并编辑环境变量文件。
7. 构建并启动服务。

构建前，先复制示例环境变量文件并编辑：

```bash
cd /opt/mcp-gateway/nisb
cp .env.example .env
# 编辑 .env，填入域名、API keys、provider settings 和部署选项
```

构建并启动：

```bash
cd /opt/mcp-gateway/nisb
docker compose build nisb-web mcp-nisb mcp-kb
docker compose up -d
```

启动后可通过以下命令检查：

```bash
docker compose ps
```

然后在浏览器中打开已配置的域名。

如果用于生产环境，请在公开暴露实例前检查环境变量、Caddy/HTTPS 设置、持久化存储、备份策略和 secret handling。

---

## 运行目录

```text
/opt/mcp-gateway/nisb   # 源码与部署配置
/opt/nisb-data          # 持久化用户数据
```

不要只把用户数据保存在容器内部。

---

## 标准维护命令

```bash
cd /opt/mcp-gateway/nisb

echo "==> Stop selected services"
docker compose stop mcp-nisb nisb-web || true

echo "==> Rebuild changed services"
docker compose build mcp-nisb nisb-web

echo "==> Start selected services"
docker compose up -d mcp-nisb nisb-web caddy
```

---

## 文档

推荐根目录文档：

- `README.md` — 英文概览。
- `README.zh-CN.md` — 中文概览。
- `ROADMAP.md` — 路线图。
- `SECURITY.md` — 安全策略。
- `SUPPORT.md` — 支持策略。
- `CONTRIBUTING.md` — 贡献指南。
- `DUAL-LICENSE.md` — 双许可证说明。
- `COMMERCIAL-LICENSE.md` — 商业许可证说明。
- `COMMERCIAL-THIRD-PARTY-DEPENDENCIES.md` — 商业使用中的第三方依赖说明。
- `THIRD_PARTY_NOTICES.md` — 第三方 notices。
- `ACKNOWLEDGEMENTS.md` — 致谢。
- `RELEASE_CHECKLIST.md` — 发布检查清单。
- `NOTICE` — 项目 notice。

工程与 Room runtime 文档可能包括：

- `nisb-web/docs/room-runtime-frontend-pipeline.md` — Room runtime 前端管线。
- `nisb-web/docs/NISB-Room-Settings-State-Wiring.en.md` — Room 设置状态接线英文指南。
- `nisb-web/docs/NISB-Room-Settings-State-Wiring.zh-CN.md` — Room 设置状态接线中文指南。
- `mcp-nisb/docs/room-runtime-contract.md` — Room runtime contract。
- `mcp-nisb/docs/room-runtime-replay.md` — Room runtime replay 文档。
- `mcp-nisb/docs/room-worker-side-memory/pipeline.en.md` — Room worker-side memory 管线。
- `mcp-nisb/docs/room-worker-side-memory/release-checklist.en.md` — Room worker-side memory 发布检查清单。
- `mcp-nisb/docs/room-worker-concurrency/pipeline.en.md` — Room worker concurrency runtime 工程英文指南。
- `mcp-nisb/docs/room-worker-concurrency/pipeline.zh-CN.md` — Room worker concurrency runtime 工程中文指南。
- `mcp-nisb/docs/room-mcp-external-publish/pipeline.en.md` — external Room MCP publish 管线。
- `mcp-nisb/docs/room-mcp-external-publish/user-and-integration-guide.en.md` — external Room MCP 用户与集成指南。

---

## 支持与服务

如果 NISB 对你有帮助，可以通过 Ko-fi 支持持续开发：

- 支持 NISB: https://ko-fi.com/nisbdev
- Remote Install: https://ko-fi.com/nisbdev/commissions
- 商业授权: license@nisb.me
- Remote Install 邮箱: install@nisb.me
- 通用联系: contact@nisb.me
- 安全问题: security@nisb.me

Remote Install 是针对一个自托管部署的远程安装协助服务。它不包含商业授权、闭源集成权利、托管/SaaS 权利、私有再分发权利、定制功能开发、长期托管运维或生产 SLA。

商业授权、闭源集成、托管/SaaS 使用、私有再分发、企业/团队定制、合作和投资相关问题，请联系 `license@nisb.me`。

---

## 安全注意事项

不要把 secrets 或运行数据发布到公开仓库。

不要发布：

- `.env`
- `*.env`
- `/opt/nisb-data/`
- 数据库
- 日志
- TLS 证书
- API keys
- Cloudflare credentials
- Bearer tokens
- 私有 MCP endpoints
- 用户上传文档
- 私有 RAG libraries
- 私有 Room histories
- 私有 workspace snapshots
- 私有 federation tokens

发布仓库前，请仔细检查部署文件、示例配置、日志、截图、demo data 和 generated artifacts。

---

## 许可证与商业使用

NISB 使用双许可证模型：

- 开源许可证：GNU Affero General Public License v3.0 (AGPLv3)。
- 商业许可证：提供给需要不同于 AGPLv3 条款的用户或组织。

如果满足 AGPLv3 义务，NISB 可以用于商业环境。

以下场景可能适合商业许可证：

- 闭源集成。
- 基于 NISB 的 proprietary products。
- 基于修改版 NISB code 的 hosted 或 SaaS services，并且不希望使用 AGPLv3 条款。
- 私有再分发并使用自定义条款。
- 嵌入商业产品。
- 企业/团队定制。
- 合作、投资或定制集成。

付费服务与软件授权是分开的。支付安装协助、迁移支持、咨询或优先支持，并不会自动获得商业软件许可证。

详情请阅读：

- `LICENSE`
- `DUAL-LICENSE.md`
- `COMMERCIAL-LICENSE.md`
- `COMMERCIAL-THIRD-PARTY-DEPENDENCIES.md`
- `THIRD_PARTY_NOTICES.md`

商业授权请联系：

```text
license@nisb.me
```

---

## 第三方依赖

NISB 依赖第三方软件、packages、APIs 和 services。

第三方依赖仍由其自身许可证和条款约束。

NISB commercial license 不会自动授予第三方依赖的商业、proprietary、hosted、SaaS、embedded 或 redistribution 权利。

商业、proprietary、hosted、embedded 或 redistributed deployments 中，如果使用 PyMuPDF / MuPDF / pymupdf4llm 等 document-processing dependencies，需要特别注意第三方许可证义务。

请阅读：

- `THIRD_PARTY_NOTICES.md`
- `COMMERCIAL-THIRD-PARTY-DEPENDENCIES.md`

---

## 发布方向

推荐发布路径：

1. 验证手工安装。
2. 稳定文档。
3. 确认数据迁移和回滚。
4. 验证 workspace、notes、files、search、RAG、RSS、Rooms、MCP publish 和 federation workflows。
5. 准备 demo 视频。
6. 把稳定的手工流程转成更安全的 bootstrap script。

首个公开版本应优先保证可靠性和清晰度，而不是激进自动化。

---

## 项目状态

NISB V1 关注稳定的自托管发布。

当前发布前工作主要包括：

- Bug 修复。
- UI polish。
- i18n 补齐。
- 后端 message 清理。
- 文档。
- Release checklist 验证。
- Demo 准备。
- Install flow 验证。
- Public launch assets。

未来可能包括更强记忆、持续工作、artifact 管理、worker 文件系统控制、code interpreter、hosted registry/directory 服务，以及 marketplace-style capability distribution。

详情见 `ROADMAP.md`。

---

## 推荐定位语

```text
NISB is a self-hosted AI workspace where Rooms can become federated MCP capabilities.
```
