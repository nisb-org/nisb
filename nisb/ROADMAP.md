# Roadmap

This roadmap describes likely future directions for NISB.

It is not a promise, contract, SLA, or guarantee. Priorities may change based on security review, user feedback, maintenance capacity, and release stability.

---

## Current status

NISB V1 is focused on a stable self-hosted release.

The current release work is primarily about:

- Bug fixes.
- UI polish.
- Frontend i18n completion.
- Backend user-facing message cleanup.
- Documentation.
- Release checklist verification.
- Installation and migration validation.
- Demo preparation.

NISB V1 is intended to provide a usable self-hosted foundation rather than a toy demo.

---

## Product direction

NISB is a self-hosted AI workspace for documents, RSS, RAG, and agent Rooms.

The core abstraction is the **Room**.

A Room is intended to be a workspace-aware unit of work that can bind:

- Supervisor and workers.
- Documents and workspace context.
- RAG and RSS-RAG sources.
- MCP providers.
- Runtime configuration.
- External access policy.
- Federation/imported remote capability flows.

The long-term direction is to make Rooms useful as controlled, reusable, and potentially federated AI capabilities.

---

## V1 core

The V1 core focuses on:

- Self-hosted deployment.
- Single-VPS Docker Compose + Caddy architecture.
- Persistent runtime data.
- Web workspace UI.
- File and document workflows.
- Library and RAG workflows.
- RSS and RSS-to-RAG workflows.
- Room runtime with supervisor and workers.
- Room role and provider binding.
- MCP provider integration.
- Room publishing as an external MCP capability.
- LibreChat / MCP Inspector style external client usage.
- Bearer token access for published Rooms.
- Token lifecycle controls such as expiry, revoke/regenerate, max calls, used count, and last used time.
- Final-only external replies for published Rooms.
- Federation / imported remote capability flows.

V1 features should not be treated as temporary trial features that will be retroactively moved behind a paywall after release.

Commercial licensing, deployment help, technical support, priority support, private deployment, and future advanced features may be paid offerings.

---

## Near-term release goals

The near-term release goals are:

- Clean public repository.
- Safer installation documentation.
- Clear migration documentation.
- Release checklist completion.
- Better dependency and license reporting.
- Better frontend i18n coverage.
- Better backend user-facing message consistency.
- UI polish and layout consistency.
- More screenshots and demo videos.
- A clear Hacker News / GitHub / YouTube launch narrative.
- Manual deployment validation before installer automation.

The first release should prioritize reliability, clarity, and trust.

---

## Room and runtime polish

Near-term Room work may include:

- Better Room runtime visibility.
- Clearer supervisor / worker status display.
- Better tool result presentation.
- More consistent Room settings UI.
- Improved Room role configuration.
- Improved provider binding UI.
- Clearer external MCP publish state.
- Clearer federation/imported remote state.
- Better runtime event summaries.
- Better error and empty states.

The goal is to make Room workflows understandable without hiding important runtime information.

---

## Memory and continuation

Future memory work may include:

- Stronger Room memory continuity.
- Better supervisor side memory.
- Worker-side read-only memory context.
- Safer standalone task rewriting from memory.
- Better memory visibility in runtime traces.
- Memory governance UI.
- Memory inspector.
- Clear start-fresh / continue-from-checkpoint semantics.
- Better protection against stale memory inheritance.

Important boundary:

- Providers, RAG, and MCP provider calls should receive standalone rewritten queries/tasks, not full memory blocks.
- Worker-side memory should remain read-only unless explicitly redesigned.
- Memory should not pollute provider queries or RAG queries.

---

## Workspace and filesystem controls

Future workspace automation may include:

- Per-worker filesystem read controls.
- Per-worker filesystem write controls.
- Workspace/focus-root scoped access.
- Better file access audit.
- Safer path policy.
- Room workspace binding.
- Natural save workflows.
- Better user-visible filesystem activity.

Filesystem and code execution features require careful security boundaries and should not be rushed.

---

## Artifact plane

Future artifact work may include:

- Unified artifact management.
- Generated reports.
- Generated charts.
- Generated CSV/data outputs.
- Exportable work products.
- Artifact visibility policy.
- Room-linked artifacts.
- Artifact history and reuse.
- Better integration with Library and workspace views.

The goal is to make AI-generated outputs durable, discoverable, and usable beyond the chat message.

---

## Code interpreter

Future code execution work may include:

- Sandboxed code interpreter support.
- Python-based data analysis workflows.
- Chart generation.
- File-based analysis.
- Code execution audit.
- Per-worker code capability toggles.
- Network and filesystem policy.
- Safe artifact output.

Security is the primary concern for this area.

NISB should not claim full secure code execution until the sandboxing, permissions, and audit boundaries are implemented and reviewed.

---

## MCP and federation

NISB will continue improving MCP and federation workflows.

Future work may include:

- More standardized provider descriptors.
- More consistent provider registry validation.
- Unified provider resolve / invoke / result flow.
- Better Room-as-MCP capability cards.
- Better external MCP audit.
- Better token policy controls.
- Federation discovery improvements.
- Imported remote capability management.
- Better compatibility with MCP clients.
- Better examples for LibreChat, MCP Inspector, and other clients.

Important direction:

NISB should not position itself only as an MCP client or only as an MCP server. The stronger direction is:

```text
A self-hosted AI workspace where Rooms can become federated MCP capabilities.
```

---

## UI and i18n

Future UI and i18n work may include:

- Consistent modal, drawer, card, chip, and button systems.
- Better light/dark theme consistency.
- Better workspace-first layout polish.
- Better Room runtime panels.
- Better evidence panels.
- Better reading optimizer UI.
- Better empty/loading/error states.
- Frontend i18n completion for new features.
- Backend user-facing message i18n.
- Clear separation between user-visible messages and machine/protocol fields.

Important boundary:

- Do not translate protocol fields, event names, tool names, trace keys, provider queries, RAG queries, or memory rewrite tasks.
- Only user-visible messages should be localized.

---

## Deployment

Future deployment work may include:

- Safer bootstrap scripts.
- Health checks.
- Upgrade scripts.
- Backup and restore helpers.
- Migration helpers.
- Better environment validation.
- Better troubleshooting docs.
- More deployment examples.
- Optional managed setup paths.

The recommended release path is:

1. Validate manual installation.
2. Stabilize documentation.
3. Verify migration and rollback.
4. Automate only after the manual process is proven safe.

---

## Commercial and support direction

NISB V1 core functionality is intended to remain available in the self-hosted core.

Possible paid offerings may include:

- Commercial licensing.
- Private deployment help.
- Installation support.
- Migration support.
- Priority support.
- Custom deployment services.
- Future advanced Pro features.
- Future Team / Enterprise governance features.
- Future hosted Hub / Directory / Relay services.
- Future marketplace or capability distribution services.

The guiding principle is:

- Do not retroactively lock V1 core features.
- Keep the self-hosted core useful.
- Charge for commercial rights, support, deployment convenience, advanced governance, hosted network services, and future high-value capabilities.

---

## Possible future Hub / Directory

A future optional hosted layer may include:

- Node registration.
- Capability directory.
- Room capability cards.
- Public/private listings.
- Federation discovery.
- Relay services.
- Usage analytics.
- Verification badges.
- Hosted billing or settlement.
- Marketplace-style distribution.

This should be optional and should not be required for basic self-hosted use.

---

## Possible marketplace

A longer-term marketplace direction may include:

- Room templates.
- Workspace skills.
- MCP provider packs.
- RSS intelligence rooms.
- Research rooms.
- Reading and translation workflows.
- Data analysis workflows.
- Capability subscriptions.
- Revenue sharing for third-party creators.

This requires a larger user base, trust model, billing model, and security review.

It should be treated as a long-term possibility rather than a V1 commitment.

---

## Non-goals for V1

The following should not be claimed as fully completed V1 features unless they are actually implemented, tested, documented, and released:

- Full enterprise governance.
- Full secure code interpreter.
- Full artifact plane.
- Full marketplace.
- Full hosted control plane.
- Full team SaaS.
- Full memory governance UI.
- Full one-click production installer.
- Full security-reviewed filesystem write automation.

---

## Guiding principles

NISB development should prioritize:

- Self-hosted ownership.
- Reliable deployment.
- Clear data persistence.
- Room-based workflows.
- Evidence-based interaction.
- Safe MCP and federation boundaries.
- Honest documentation.
- No retroactive paywalling of V1 core features.
- Security before powerful execution features.
- Production usefulness over demo novelty.

---

## Suggested positioning

```text
NISB is a self-hosted AI workspace where Rooms can become federated MCP capabilities.
```
