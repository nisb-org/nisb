# NISB

**NISB is a self-hosted AI workspace for notes, files, documents, RSS, evidence, Rooms, and MCP capabilities.**

**Demo:** [https://youtu.be/8cEAmJpn0EY](https://youtu.be/8cEAmJpn0EY)

**Support / Remote Install:** [https://ko-fi.com/nisbdev](https://ko-fi.com/nisbdev)

It is also a workspace where Rooms can become callable, shareable, revocable, and composable MCP capabilities.

NISB combines a daily Markdown/file workspace, long-lived knowledge libraries, RSS-to-RAG workflows, evidence-based search, supervisor/worker Rooms, MCP publishing, NISB-to-NISB federation, and a small-VPS deployment model.

NISB is not just a chat UI. Its core abstraction is the Room: a workspace-aware agent runtime that can bind workspace context, knowledge sources, workers, MCP providers, RAG/RSS workflows, and external access policies.

A Room can be used locally, published as a standard MCP capability for external clients such as LibreChat or MCP Inspector, shared across federated NISB nodes, revoked by the owner, and composed into other Rooms as a worker capability.

---

## What NISB is

NISB is built around several connected ideas:

- A self-hosted AI workspace.
- A daily Markdown and file workspace.
- A workspace control center for projects, directories, files, notes, evidence, and Rooms.
- Four-source search across chat, directories, files, and libraries.
- RAG libraries and evidence-based answers.
- RSS subscriptions and RSS-to-RAG workflows.
- Room-based AI workflows with supervisor and workers.
- MCP provider bindings.
- Room publishing as an external MCP capability.
- NISB-to-NISB federation and imported remote capabilities.
- Composable Room capabilities that can be reused as workers inside other Rooms.
- A practical single-VPS deployment model using Docker Compose and Caddy.

The goal of NISB V1 is to provide a usable, stable, self-hosted foundation rather than a toy demo.

---

## Why Rooms matter

Most AI tools treat a chat thread as the main unit of interaction.

NISB treats a Room as the main unit of work.

A Room can:

- Bind a workspace and focus root.
- Use a supervisor/worker runtime.
- Bind RAG or RSS-RAG knowledge sources.
- Bind MCP providers.
- Use local files, notes, evidence, side-memory, and notebooks.
- Keep workspace context.
- Produce final answers for external clients.
- Be published as an MCP capability.
- Be shared across NISB nodes through federation.
- Be revoked or expired by the owner.
- Be composed into other Rooms as a worker capability.

This makes a Room more than a conversation. It becomes a reusable, controlled, evidence-aware, and potentially federated capability.

---

## Key features

### Workspace

- Self-hosted web workspace.
- Daily Markdown notes and file workflows.
- Workspace-oriented UI with files, libraries, feeds, notes, evidence, and Rooms.
- Workspace control center for managing, switching, and focusing directories.
- Focus snapshot support.
- Favorites, pinned/common items, internal links, preview refresh, and workspace state save/clear.
- File and directory focus.
- Document outline/navigation workflows.
- Persistent runtime data directory.
- Designed for long-term personal use and migration.

### Documents and libraries

- Document/library workflows.
- Local knowledge organization.
- RAG-oriented document usage.
- Evidence-based interaction.
- Support for Markdown, EPUB, Office documents, text files, and document ingestion workflows.
- Foundation for reading, research, and long-running knowledge workflows.

### Search

- Four-source search across chat, directories, files, and libraries.
- Aggregated search results with jump/focus workflows.
- Local workspace search designed for fast daily use on small VPS deployments.
- Evidence-oriented search across documents, libraries, and global workspace context.

### RSS and RAG

- RSS subscriptions.
- RSS-to-RAG workflows.
- RSS gate with timed cleanup and timed ingestion into designated libraries for fresher RAG workflows.
- RAG libraries and groups.
- Document, library, and cross-library search for evidence-based workflows.
- Citation, source, and span navigation where supported.
- Library home with bookmark and annotation overview.
- Evidence-oriented answers.
- Room workers can be connected to RAG or RSS-RAG sources.

### Rooms

- Room-based AI workflows.
- Workspace-aware Room runtime.
- Supervisor and worker orchestration.
- Role configuration.
- Provider binding.
- Workspace binding.
- Evidence binding.
- MCP binding.
- Runtime visibility.
- Side-memory continuity for Room workflows.
- Room notebook support.
- Shared Auto Reply at the Room level.
- Four reply modes: silent, supervisor plus workers, direct worker, and direct supervisor.

### MCP

- MCP provider binding.
- Room publishing as a standard external MCP capability.
- Compatible with MCP clients such as LibreChat and MCP Inspector.
- Bearer-token based access.
- Token lifecycle controls such as expiry, revoke/regenerate, max calls, used count, and last used time.
- Final-only external replies for published Rooms.
- Room-scoped capability publishing without exposing the owner's private workspace, private filesystem, or private memory.

### Federation

- NISB-to-NISB federation.
- Imported remote capabilities.
- Federated MCP / federated Room workflows.
- Owner-managed room grants.
- Grant states such as active, revoked, and expired.
- Token expiry, max calls, used count, client label, and endpoint tracking.
- Immediate loss of access after revoke.
- A foundation for sharing Room capabilities across nodes without opening the entire workspace.

### Composable capabilities

- A federated member can import an owner-published Room MCP capability.
- A member Room can use that imported capability as an MCP worker.
- A member Room can combine remote Room capabilities with local RAG, local workers, MCP tools, supervisor logic, and workspace context.
- A composed Room can be published again as another Room capability.
- This is the beginning of a capability graph and capability runtime, not just a standalone MCP server.

---

## What NISB is not

NISB is not intended to be just another ChatGPT-style interface.

It is also not positioned as a direct replacement for tools such as LibreChat, Dify, Open WebUI, AnythingLLM, Obsidian, Logseq, Notion, or other AI and PKM platforms.

A better way to understand the difference:

- LibreChat is a strong MCP-capable chat client and AI conversation platform.
- Obsidian and Logseq are note-first PKM tools.
- Dify is a strong workflow and application builder.
- NISB focuses on a self-hosted AI workspace with an evidence layer, workspace-aware Rooms, MCP publishing, federation, and composable capability sharing.

NISB can work alongside existing tools. For example, a NISB Room can be published as MCP and called from LibreChat.

---

## Deployment model

NISB is designed to run reliably on a small VPS.

The recommended deployment model is:

- One Ubuntu VPS.
- Docker Compose for service orchestration.
- Caddy for reverse proxy and HTTPS.
- Project source under `/opt/mcp-gateway/nisb`.
- Persistent runtime data under `/opt/nisb-data`.

This model is optimized for:

- Stability.
- Easy rollback.
- Low operational complexity.
- Reproducible installation.
- Clean migration from one VPS to another.

---

## Quick start

> For assisted setup, Remote Install is available: [https://ko-fi.com/nisbdev/commissions](https://ko-fi.com/nisbdev/commissions)

A typical manual deployment flow is:

1. Prepare a fresh Ubuntu 24.04 VPS.
2. Configure DNS, for example through Cloudflare.
3. Install Docker Engine and Docker Compose v2.
4. Clone the project to `/opt/mcp-gateway/nisb`.
5. Prepare persistent data under `/opt/nisb-data`.
6. Copy and edit the environment file.
7. Build and start the services.

Before building, copy the example environment file and edit it:

```bash
cd /opt/mcp-gateway/nisb
cp .env.example .env
# Edit .env with your domain, API keys, provider settings, and deployment options
```

Build and start:

```bash
cd /opt/mcp-gateway/nisb
docker compose build nisb-web mcp-nisb mcp-kb
docker compose up -d
```

After startup, verify the deployment with:

```bash
docker compose ps
```

Then open the configured domain in your browser.

For production use, review environment variables, Caddy/HTTPS settings, persistent storage, backup strategy, and secret handling before exposing an instance publicly.

---

## Runtime layout

```text
/opt/mcp-gateway/nisb   # source code and deployment configuration
/opt/nisb-data          # persistent user data
```

Do not store user data only inside containers.

---

## Standard maintenance commands

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

## Documentation

Recommended root documents:

- `README.md` — English overview.
- `README.zh-CN.md` — Chinese overview.
- `ROADMAP.md` — roadmap and future direction.
- `SECURITY.md` — security policy.
- `SUPPORT.md` — support policy.
- `CONTRIBUTING.md` — contribution guide.
- `DUAL-LICENSE.md` — licensing model.
- `COMMERCIAL-LICENSE.md` — commercial license information.
- `COMMERCIAL-THIRD-PARTY-DEPENDENCIES.md` — third-party dependency notes for commercial use.
- `THIRD_PARTY_NOTICES.md` — third-party notices.
- `ACKNOWLEDGEMENTS.md` — acknowledgements.
- `RELEASE_CHECKLIST.md` — release checklist.
- `NOTICE` — project notice.

Engineering and Room runtime documents may include:

- `nisb-web/docs/room-runtime-frontend-pipeline.md` — Room runtime frontend pipeline.
- `nisb-web/docs/NISB-Room-Settings-State-Wiring.en.md` — end-to-end Room settings state wiring guide.
- `nisb-web/docs/NISB-Room-Settings-State-Wiring.zh-CN.md` — Chinese version of the Room settings state wiring guide.
- `mcp-nisb/docs/room-runtime-contract.md` — Room runtime contract.
- `mcp-nisb/docs/room-runtime-replay.md` — Room runtime replay documentation.
- `mcp-nisb/docs/room-worker-side-memory/pipeline.en.md` — Room worker-side memory pipeline.
- `mcp-nisb/docs/room-worker-side-memory/release-checklist.en.md` — Room worker-side memory release checklist.
- `mcp-nisb/docs/room-worker-concurrency/pipeline.en.md` — Room worker concurrency runtime engineering guide.
- `mcp-nisb/docs/room-worker-concurrency/pipeline.zh-CN.md` — Chinese version of the Room worker concurrency runtime engineering guide.
- `mcp-nisb/docs/room-mcp-external-publish/pipeline.en.md` — external Room MCP publish pipeline.
- `mcp-nisb/docs/room-mcp-external-publish/user-and-integration-guide.en.md` — external Room MCP user and integration guide.

---

## Support and services

If NISB helps you, you can support continued development on Ko-fi:

- Support NISB: https://ko-fi.com/nisbdev
- Remote Install: https://ko-fi.com/nisbdev/commissions
- Commercial License: license@nisb.me
- Remote Install email: install@nisb.me
- General contact: contact@nisb.me
- Security issues: security@nisb.me

Remote Install is an assisted setup service for one self-hosted deployment. It does not include commercial licensing, closed-source integration rights, hosted/SaaS rights, private redistribution rights, custom feature development, long-term managed hosting, or production SLA.

Commercial licensing, closed-source integration, hosted/SaaS use, private redistribution, enterprise/team customization, partnership, and investment inquiries should use `license@nisb.me`.

---

## Licensing and commercial use

NISB uses a dual licensing model:

- Open-source license: GNU Affero General Public License v3.0 (AGPLv3).
- Commercial license: available for users and organizations that need terms different from AGPLv3.

NISB can be used in commercial settings under AGPLv3 if AGPLv3 obligations are met.

A commercial license may be appropriate for:

- Closed-source integration.
- Proprietary products based on NISB.
- Hosted or SaaS services based on modified NISB code without using AGPLv3 terms.
- Private redistribution under custom terms.
- Embedded commercial products.
- Enterprise/team customization.
- Partnership, investment, or custom integration.

Paid services are separate from software licensing. Paying for installation help, migration support, consulting, or priority support does not automatically grant a commercial software license.

For details, review:

- `LICENSE`
- `DUAL-LICENSE.md`
- `COMMERCIAL-LICENSE.md`
- `COMMERCIAL-THIRD-PARTY-DEPENDENCIES.md`
- `THIRD_PARTY_NOTICES.md`

For commercial licensing, contact:

```text
license@nisb.me
```

---

## Third-party dependencies

NISB depends on third-party software, packages, APIs, and services.

Third-party dependencies remain governed by their own licenses and terms.

A NISB commercial license does not automatically grant commercial, proprietary, hosted, SaaS, embedded, or redistribution rights for third-party dependencies.

Special attention may be required for document-processing dependencies such as PyMuPDF / MuPDF / pymupdf4llm in commercial, proprietary, hosted, embedded, or redistributed deployments.

See:

- `THIRD_PARTY_NOTICES.md`
- `COMMERCIAL-THIRD-PARTY-DEPENDENCIES.md`

---

## Release direction

The recommended release path is:

1. Validate manual installation.
2. Stabilize documentation.
3. Confirm data migration and rollback.
4. Verify workspace, notes, files, search, RAG, RSS, Rooms, MCP publish, and federation workflows.
5. Prepare demo videos.
6. Convert the stable manual process into a safer bootstrap script.

The first public release should prioritize reliability and clarity over aggressive automation.

---

## Project status

NISB V1 is focused on a stable self-hosted release.

The current release work is primarily about:

- Bug fixes.
- UI polish.
- i18n completion.
- Backend message cleanup.
- Documentation.
- Release checklist verification.
- Demo preparation.
- Install flow verification.
- Public launch assets.

Future work may include stronger memory, continuous work, artifact management, worker filesystem controls, code interpreter support, hosted registry/directory services, and marketplace-style capability distribution.

See `ROADMAP.md` for details.

---

## Suggested tagline

```text
NISB is a self-hosted AI workspace where Rooms can become federated MCP capabilities.
```
