# NISB Room MCP External Publish Pipeline Document

Version: 2026-06-10 P1 Release Baseline  
Scope: room-scoped external MCP publish  
Audience: NISB maintainers, integrators, release reviewers, and future contributors

## 1. Purpose

This document records the implementation and release baseline for NISB Room MCP External Publish.

Its goals are to:

- Track which parts of room-scoped external MCP publish are complete.
- Define the boundary between NISB room federation and third-party external MCP access.
- Record the backend, MCP server, UI, and external client responsibilities.
- Preserve the real-world validation path from `nisb.me` to external MCP clients.
- Prevent future regressions in token lifecycle, single-room scope, final-only answers, and federation compatibility.
- Provide a durable reference for future debugging, file splitting, release documentation, and product expansion.

This document follows the earlier Room MCP standardization and imported remote regression documents.

## 2. Current Status

Current phase:

```text
room-scoped external MCP publish
```

Current release judgment:

```text
P1 minimum release loop has passed.
NISB Room MCP External Publish is ready to serve as the first public release baseline.
Future work should focus on documentation, schema polish, broader client compatibility, and deeper runtime worker regression coverage.
```

Validated capabilities:

```text
External publish owner lifecycle files exist.
Owner tools get / enable / revoke / regenerate are registered and usable.
Bearer token scope resolver is active.
Scoped room_mcp_external_export.py is active.
nisb_mcp.py Bearer routing is active.
nisb_mcp.py external alias facade is active.
Frontend external publish composable is active.
Frontend external publish card is active.
Room settings UI shows the external publish card.
Enable external publish works.
Regenerate token works.
Revoke external access works.
Plaintext token is shown once.
Copied config contains the real Bearer token.
external_mcp_publish.json is written.
external_mcp_publish.json stores token_hash, not the plaintext token.
Minimal Node MCP client has passed validation.
MCP Inspector local application test has passed.
LibreChat has passed real third-party MCP client validation.
Token revoke has passed validation.
Regenerated old token denial has passed validation.
Regenerated new token success has passed validation.
Token expiry has passed validation.
max_calls=1 has passed validation.
max_calls empty / max_calls=0 unlimited mode has passed validation.
used_count and last_used_at have passed validation.
The 30-day maximum validity limit has passed validation.
Expired UI state has passed validation.
direct_role reply mode works through external MCP access.
supervisor direct-answer mode works through external MCP access.
mcp_overrides.notebook_write_enabled side-memory scenario works through external MCP access.
Existing federation / imported_remote main flows still work.
Federation MCP revoked behavior still works.
```

What can be announced:

```text
NISB supports room-scoped external MCP publish as a P1 release baseline.
A room owner can publish a single room as an external MCP-accessible provider.
External MCP clients can connect with a Bearer token.
External clients see only room_provider_list and room_provider_call.
External clients can access only the single source room authorized by the token.
External clients receive final-only answers.
The owner can revoke, regenerate, expire, and limit tokens.
Old tokens, expired tokens, revoked tokens, and over-limit tokens fail.
Existing federation and imported_remote flows were not broken by external publish.
```

What should not be overclaimed:

```text
All MCP clients work without adaptation.
Claude Desktop has completed direct validation.
Every possible RAG / builtin MCP / nested room MCP worker combination has completed full matrix regression.
OAuth, marketplace, billing, and dynamic per-room tools are included.
External clients receive worker traces, source observations, or private execution details.
```

## 3. Three Distinct Paths

### 3.1 same-VPS local_room_shared

Purpose:

```text
Validate that a local room provider can be invoked through the MCP export facade.
Validate the P0 behavior of external provider list and external provider call.
Validate that the external_mcp_publish token scope can lock access to one source room.
```

Success markers:

```text
provider_origin=local_room_shared
provider_id=room_provider__<source_room_id>
source_room_id=<source_room_id>
tool=room_provider_call
result=real room final text
result_view=final_result_only
source_observation_allowed=false
owner_private_scope_exposed=false
```

Current status:

```text
Passed.
Validated through minimal Node MCP client, MCP Inspector, and LibreChat.
```

This does not prove:

```text
All cross-VPS imported_remote behavior.
All federation grant behavior.
All external clients require no adaptation.
```

### 3.2 cross-VPS imported_remote / federation

Purpose:

```text
Validate that existing NISB-to-NISB federation and imported_remote capabilities still work.
Validate active grant, revoke, and restored connection behavior.
Validate that external publish does not contaminate older Room MCP federation semantics.
```

Success markers:

```text
provider_origin=imported_remote
remote_peer_id=<remote peer>
grant_id=<grant id>
artifact_id=<artifact id>
source_room_id=<remote source room>
result_view=final_result_only
source_observation_allowed=false
owner_private_scope_exposed=false
```

Current status:

```text
Minimum regression passed.
vps-b can still join a room from vps-a.
Federation MCP revoked behavior works.
Other major federation MCP capabilities still work.
External publish did not break the imported_remote / federation main path.
```

Fixed note:

```text
This cross-VPS Room MCP regression depends on the existing NISB federation/imported_remote chain.
It is not proof of pure non-federated cross-VPS standard MCP export.
```

### 3.3 third-party external MCP publish

Purpose:

```text
This is the target path.
A room owner enables external MCP publish for one room.
NISB generates an external MCP config and token.
An external MCP client can ask only that one room.
The owner can revoke, expire, regenerate, and limit the token.
The external client receives only final-only results.
The external client does not receive a federation grant or a global provider catalog.
```

Success markers:

```text
Authorization: Bearer <external_mcp_publish_token>
external_mcp_publish_scope exists
provider_list count=1
provider_id=room_provider__<source_room_id>
source_room_id=<source_room_id>
provider_origin=local_room_shared
result_view=final_result_only
source_observation_allowed=false
owner_private_scope_exposed=false
```

Validated external-client behavior:

```text
initialize succeeded.
tools/list succeeded.
tools/call succeeded.
provider_list returned count=1.
provider_call returned real room text.
LibreChat UI ran room_provider_list.
LibreChat UI ran room_provider_call.
MCP Inspector local application test passed.
Minimal Node MCP client test passed.
```

MCP servers expose tools, clients discover them with `tools/list`, and clients invoke them through the MCP tool mechanism. 

## 4. Product Target

Target:

```text
A NISB room owner can enable external MCP publish for one room.
NISB generates a standard external MCP access config.
External MCP clients can connect through Streamable HTTP and Bearer authorization.
The external client can ask only the published room.
The answer follows the source room settings, validity rules, revoke state, and call limit.
The external client receives final-only output.
The external client does not see workers, source observations, or private execution traces.
```

Non-goals:

```text
This is not federation grant externalization.
This is not a global room provider catalog.
This is not dynamic per-room tools.
This is not marketplace or billing.
This is not OAuth 2.1 / PKCE for P1.
This does not give room-mcp-grant:<payload> to third-party clients.
This does not put external tokens into room_roles.py.
This does not put external tokens into federated_member_access.
This does not turn room_mcp_publication into a token lifecycle system.
```

Current completion:

```text
Owner enable external MCP publish: complete.
External MCP config generation: complete.
Bearer token access: complete.
Minimal Node client access: complete.
MCP Inspector local application test: complete.
LibreChat access: complete.
Single-room scope: complete.
Final-only text response: complete.
Revoke: complete.
Expiry: complete.
Regenerate: complete.
max_calls: complete.
used_count / last_used_at: complete.
direct_role reply mode: validated through external MCP call.
supervisor direct-answer mode: validated through external MCP call.
Side notebook write scenario: validated through external MCP call.
imported_remote / federation main flows: minimum regression passed.
```

## 5. Backend File Responsibilities

### 5.1 `room_mcp_external_publish_store.py`

Responsibilities:

```text
Store external_mcp_publish records.
Read and write external_mcp_publish.json.
Store token_hash, not plaintext tokens.
Store created_at, expires_at, revoked_at, used_count, and last_used_at.
Provide low-level data access for the service layer.
```

Must not handle:

```text
MCP HTTP request routing.
provider_list / provider_call.
UI config copy.
federation grant parsing.
source room runtime policy.
```

Current status:

```text
external_mcp_publish.json is written.
Plaintext token is not stored.
token_hash is stored.
regenerate overwrites token_hash.
revoke writes revoked_at.
expiry writes expires_at.
successful provider_call updates used_count.
successful provider_call updates last_used_at.
```

### 5.2 `room_mcp_external_config_builder.py`

Responsibilities:

```text
Build external MCP client configs.
Build generic MCP config.
Build vendor-specific example config.
Inject endpoint and Bearer token.
Ensure the token appears only in enable/regenerate responses.
```

Product wording note:

```text
The UI should not make one third-party platform the primary product label.
Use “Copy MCP client config” as the main action.
LibreChat, MCP Inspector, and Claude Desktop can appear as examples or validation targets.
```

Current status:

```text
Copied config contains the real Bearer token.
Generic config works with the minimal Node MCP client.
LibreChat config works with nisb.dev LibreChat.
```

### 5.3 `room_mcp_external_publish_service.py`

Responsibilities:

```text
Owner lifecycle service.
get / enable / revoke / regenerate.
Generate plaintext token.
Hash and store token_hash.
Immediately deny revoked tokens.
Invalidate old tokens after regenerate.
Persist expires_at.
Persist max_calls.
Default validity is 30 days.
Minimum validity is 1 hour.
Maximum validity is 30 days.
Empty max_calls means unlimited.
Positive integer max_calls means maximum successful question count.
```

Must not handle:

```text
Provider dispatch.
Runtime worker policy.
federation/imported_remote grants.
nisb_mcp.py HTTP context.
```

Current status:

```text
enable works.
regenerate works.
plaintext token is returned once.
expires_in_days=0.0417 creates an approximately 1-hour token.
expires_in_days=50 is rejected.
default / 30-day validity works.
max_calls=1 creates a one-successful-question token.
empty max_calls creates an unlimited token.
```

### 5.4 `room_tools_external_mcp_publish.py`

Responsibilities:

```text
Expose owner management tools.
Wrap the external publish service.
Return normalized MCP tool results.
```

Tools:

```text
nisb_room_mcp_external_publish_get
nisb_room_mcp_external_publish_enable
nisb_room_mcp_external_publish_revoke
nisb_room_mcp_external_publish_regenerate
```

Must not handle:

```text
Bearer token resolver.
External client provider_call.
Room runtime execution policy.
```

Current status:

```text
owner enable tool is registered and usable.
owner regenerate tool is registered and usable.
owner revoke tool is registered and usable.
owner get supports UI state refresh.
```

### 5.5 `room_mcp_external_grant_resolver.py`

Responsibilities:

```text
Resolve external_mcp_publish_scope from Authorization Bearer token.
Validate token_hash.
Validate revoked state.
Validate expired state.
Validate max_calls.
Record last_used and used_count.
Return a single-room scope.
```

Scope fields:

```text
publish_id
source_room_id
provider_id
owner_user_id
allowed_mode
result_view=final_result_only
source_observation_allowed=false
owner_private_scope_exposed=false
```

Errors:

```text
external_publish_token_missing
external_publish_token_invalid
external_publish_revoked
external_publish_expired
external_publish_provider_mismatch
external_publish_call_limit_exceeded
missing_question
```

Current status:

```text
Bearer token is recognized by nisb_mcp.py.
resolver produces external_mcp_publish_scope.
provider_list / provider_call logs show external scope enabled.
revoked token is denied.
expired token is denied.
old token after regenerate is denied.
over-limit token is denied.
used_count / last_used_at update after successful calls.
```

### 5.6 `room_mcp_external_export.py`

Responsibilities:

```text
External provider list facade.
External provider call facade.
Keep P0 behavior when no scope exists.
Enable single-room restriction when external_mcp_publish_scope exists.
provider_list returns only scope.provider_id.
provider_call may omit provider_id.
provider mismatch is denied immediately.
Return final-only result.
Do not expose source private observations.
Mark used_count / last_used_at after successful provider_call.
```

Scoped provider_list requirements:

```text
provider_list.count=1
Return only the room provider matching scope.provider_id.
Do not return imported_remote.
Do not return federation providers.
Do not return other local rooms.
Do not return builtin catalogs.
```

Scoped provider_call requirements:

```text
question is required.
provider_id is optional.
If provider_id is provided, it must equal scope.provider_id.
source_room_id must equal scope.source_room_id.
provider_origin defaults to local_room_shared.
result_view=final_result_only.
source_observation_allowed=false.
owner_private_scope_exposed=false.
```

Current status:

```text
provider_list count=1.
provider_id=room_provider__room_1780576710178_8d254b.
provider_call can omit provider_id and still return real room text.
LibreChat UI can call provider_list and provider_call.
used_count updates after successful provider_call.
last_used_at updates after successful provider_call.
```

Recommended future hardening:

```text
Do not count used_count when dispatch returns ok=false.
Record or surface usage_mark_error if mark_external_mcp_publish_used fails.
Add a negative test for wrong provider_id.
Add a negative test for source_room_id mismatch.
```

### 5.7 `nisb_mcp.py`

Responsibilities:

```text
Handwritten JSON-RPC HTTP MCP server.
Handle initialize / notifications/initialized / ping / tools/list / tools/call.
Maintain TOOLS dict.
Load schema.json.
Route Authorization Bearer token.
Inject external_mcp_publish_scope into external provider tools.
Expose short tool names to Bearer external clients.
Map external aliases back to internal canonical tools.
```

Must not handle:

```text
Token storage.
Token lifecycle business rules.
Provider runtime execution.
Federation grant service.
Source room internal worker policy.
```

Current status:

```text
bearer_mode=True.
path=/mcp.
external_mcp_publish_scope enabled.
tools/list exposes room_provider_list / room_provider_call.
tools/call accepts room_provider_list / room_provider_call.
alias normalization works.
```

External client-facing tools:

```text
room_provider_list
room_provider_call
```

Internal canonical tools:

```text
nisb_room_mcp_external_provider_list
nisb_room_mcp_external_provider_call
```

Alias mapping:

```text
room_provider_list -> nisb_room_mcp_external_provider_list
room_provider_call -> nisb_room_mcp_external_provider_call
```

Reason for aliasing:

```text
LibreChat may append _mcp_<serverName> to MCP tool names.
The earlier internal tool name already contained _mcp_.
This caused execution-time parsing problems.
Short aliases solved the compatibility issue without changing internal canonical tools.
```

Risk boundary:

```text
Bearer scope injection must affect only third-party external MCP publish.
It must not contaminate federation/imported_remote.
It must not contaminate nested MCP calls inside the source room.
It must not affect builtin external MCP providers.
Do not expose _mcp_ internal tool names to third-party clients.
```

## 6. Registration Path

New MCP tools must be synchronized across:

```text
mcp-nisb/tools/rooms_shared/__init__.py
mcp-nisb/tools/rooms_shared/tools.py
mcp-nisb/nisb_mcp.py
mcp-nisb/schema.json
```

Registration rules:

```text
The tool appears in __init__._EXPORTS.
The tool appears in tools.py imports and __all__.
The tool appears in nisb_mcp.py imports and TOOLS.
The tool appears in schema.json simplified/full entries.
```

Debug rules:

```text
tools/list shows the tool but tools/call cannot find it: check nisb_mcp.py TOOLS.
tools/call callable exists but tools/list does not show it: check schema.json.
nisb_mcp.py import fails: check __init__.py, tools.py, and tool file __all__.
LibreChat sees tools/list but UI call fails with not found: check whether the external tool name contains _mcp_ or is too long.
```

Owner tools:

```text
nisb_room_mcp_external_publish_get
nisb_room_mcp_external_publish_enable
nisb_room_mcp_external_publish_revoke
nisb_room_mcp_external_publish_regenerate
```

External provider canonical tools:

```text
nisb_room_mcp_external_provider_list
nisb_room_mcp_external_provider_call
```

Third-party client-facing tools:

```text
room_provider_list
room_provider_call
```

## 7. Frontend Responsibilities

### 7.1 `use_room_settings_external_mcp_publish.js`

Responsibilities:

```text
Maintain external publish state.
Call get / enable / revoke / regenerate.
Store loading and error states.
Store plaintext token for one-time display.
Copy MCP config.
Send expires_in_days.
Send max_calls.
Avoid mixing with old room_mcp_share_ref.
```

State fields:

```text
external_mcp_publish_status
external_mcp_publish_loading
external_mcp_publish_error
external_mcp_publish_plaintext_token
external_mcp_publish_enable_loading
external_mcp_publish_revoke_loading
external_mcp_publish_regenerate_loading
external_mcp_publish_copy_loading_kind
external_mcp_publish_expires_in_days
external_mcp_publish_max_calls
external_mcp_publish_client_label
external_mcp_publish_endpoint_url
```

Must not handle:

```text
Old federation grant list.
room_mcp_publication fallback.
Role binding catalog.
Runtime worker policy.
token_hash calculation.
Final token validity enforcement.
```

Current status:

```text
enable works.
regenerate works.
revoke works.
copied config contains the real Bearer token.
plaintext token is shown once.
expires_in_days supports decimal values.
max_calls supports positive integers.
empty max_calls clears the limit to unlimited.
status=expired is recognized by the UI.
```

### 7.2 `RoomSettingsExternalMcpPublishCard.vue`

Responsibilities:

```text
Display external publish UI.
Display unpublished / active / expired / revoked states.
Input validity period.
Input max successful question count.
Input client label.
Input endpoint.
Enable external publish.
Revoke external access.
Regenerate token.
Copy MCP client config.
Copy generic MCP config.
Show plaintext token once.
```

Product wording:

```text
Title: Room MCP External Publish
Description: Generate a room-scoped MCP access config for external MCP clients.
Button: Copy MCP client config
Button: Copy generic MCP config
Do not use “Copy LibreChat template” as the long-term primary product label.
LibreChat should appear as a validation target or compatibility example.
```

Current status:

```text
Card is visible.
State is visible.
Provider ID is visible.
Source Room ID is visible.
Result View is visible.
Validity period accepts 0.0417 to 30 days.
Max successful question count is visible.
Max successful question count can be empty.
Copy config works.
Expired state message is shown.
Invalid 50-day request produces backend error toast.
```

### 7.3 `RoomSettingsRoomMcpPanel.vue`

Responsibilities:

```text
Compose old room MCP publication UI.
Compose old grant artifact UI.
Insert the new external publish card.
Do not implement token lifecycle here.
Do not write external tokens into old grant UI.
```

Current status:

```text
external publish card is connected to room settings.
props pass-through issue is fixed.
```

### 7.4 `use_room_settings_form.js`

Responsibilities:

```text
Act as the room settings facade.
Import external publish composable.
Refresh external publish status when room settings open.
Refresh external publish status when room_id changes.
Refresh external publish status after save.
Return new states and handlers to the UI.
```

Must not handle:

```text
External publish business logic.
Config construction.
Token hash.
Runtime scope.
```

Current status:

```text
external publish composable is connected.
tool result envelope parsing is enhanced.
enable / regenerate / revoke / copy main path works.
```

## 8. Current UI Facts

UI elements:

```text
Room MCP External Publish
External publish status: unpublished / active / expired / revoked
Provider ID: room_provider__<source_room_id>
Source Room ID: <source_room_id>
Result View: final_result_only
Expires At
Last Used
Used Count
Client Label
Validity Period in Days
Max Successful Questions
Client Label input
MCP Endpoint
Regenerate token
Revoke external access
Copy MCP client config
Copy generic MCP config
Plaintext token is shown only once
```

Validated UI behavior:

```text
External publish card appears in Room Settings.
Refresh button responds.
Page reload works.
Normal room Q&A still works.
Enable external publish succeeds.
Regenerate token succeeds.
Revoke external access succeeds.
Plaintext token is displayed once.
Copied config contains the real token.
external_mcp_publish.json is created.
external_mcp_publish.json does not contain plaintext token.
external_mcp_publish.json contains token_hash.
State becomes active / published.
Expired token state becomes expired.
```

Expired UI message:

```text
The current external MCP publish has expired. External clients should no longer be able to use the old token. Please regenerate it.
```

Validated UI error:

```text
Validity period set to 50 days:
Tool execution failed: expires_in_days must be no more than 30 days.
```

Validated usage display:

```text
Last Used updates after successful external provider_call.
Used Count updates after successful external provider_call.
When max_calls=70, repeated successful calls increment used_count.
When max_calls=0, repeated successful calls are not blocked by call limit.
```

## 9. Key Maintenance Notes

The most important risk has shifted from:

```text
Does owner enable external MCP publish work?
```

to:

```text
How should P1 release wording be presented?
Should schema be minimized?
How should more external clients be adapted?
How much deeper should the runtime worker regression matrix go?
```

Enable path:

```text
owner clicks enable external MCP publish
=> frontend handler runs
=> call_room_tool invokes nisb_room_mcp_external_publish_enable
=> backend returns plaintext token
=> external_mcp_publish.json is written
=> UI state changes from unpublished to active
=> copied config contains real Bearer token
=> external client can connect
```

Token lifecycle path:

```text
max_calls=1: first call succeeds, second call fails with external_publish_call_limit_exceeded.
empty max_calls: backend stores max_calls=0, repeated calls are allowed.
expires_in_days=0.0417: token expires after about 1 hour.
expires_in_days=50: backend rejects the request.
revoke: old token fails.
regenerate: old token fails and new token succeeds.
used_count / last_used_at update only after successful provider_call.
```

If lifecycle behavior regresses, check:

```text
room_mcp_external_grant_resolver.py reads revoked_at.
room_mcp_external_grant_resolver.py reads expires_at.
room_mcp_external_grant_resolver.py checks token_hash.
room_mcp_external_grant_resolver.py rejects old tokens.
room_mcp_external_grant_resolver.py checks max_calls.
room_mcp_external_publish_store.py writes revoked_at correctly.
room_mcp_external_publish_store.py overwrites token_hash correctly.
used_count / last_used_at update only after valid successful calls.
nisb_mcp.py resolves Bearer token on each request.
External clients may cache sessions; use a minimal client to verify backend behavior.
```

Do not modify first unless logs prove runtime or federation was affected:

```text
room_roles.py
room_worker_execution.py
room_runtime_execution.py
room_tools_runtime.py
room_mcp_provider_adapter.py
room_mcp_provider_bridge.py
RoomRoleProviderBindingPanel.vue
RoomRolesDrawerProviderSection.vue
use_room_roles_drawer_provider_catalog.js
```

## 10. Endpoint Strategy

Validated endpoint:

```text
https://nisb.example.com/nisb/mcp
```

Recommended public endpoint:

```text
https://nisb.example.com/nisb/mcp
```

Future endpoint candidates:

```text
https://mcp.nisb.me/nisb/mcp
https://nisb.example.com/mcp
```

Authentication:

```text
Authorization: Bearer <external_mcp_publish_token>
```

Standard config:

```json
{
  "type": "streamable-http",
  "url": "https://nisb.example.com/nisb/mcp",
  "headers": {
    "Authorization": "Bearer <external_mcp_publish_token>"
  }
}
```

The MCP Streamable HTTP transport uses HTTP requests against an MCP endpoint, and the protocol defines Streamable HTTP as one of the standard transport mechanisms. [modelcontextprotocol](https://modelcontextprotocol.io/specification/2025-11-25/basic/transports)

LibreChat config:

```json
{
  "mcpServers": {
    "nisb": {
      "type": "streamable-http",
      "url": "https://nisb.example.com/nisb/mcp",
      "headers": {
        "Authorization": "Bearer ${NISB_ROOM_MCP_TOKEN}"
      },
      "chatMenu": true,
      "startup": true,
      "serverInstructions": false,
      "initTimeout": 60000,
      "timeout": 300000
    }
  }
}
```

LibreChat notes:

```text
Put only the token value in .env.
Do not include the word Bearer in the .env token value.
The Authorization header should contain Bearer ${NISB_ROOM_MCP_TOKEN}.
Use a short server key such as nisb.
Do not use server keys or tool names containing _mcp_.
Restart or rebuild the LibreChat API container after changing .env.
```

LibreChat supports MCP server configuration and can reference environment variables in headers for SSE and Streamable HTTP transports. [librechat](https://www.librechat.ai/docs/configuration/librechat_yaml/object_structure/mcp_servers)

Avoid:

```text
?grant_ref=room-mcp-grant:...
room-mcp-grant:<payload> given to third-party clients
```

Reason:

```text
room-mcp-grant belongs to federation/imported_remote.
URL query tokens can leak into logs, browser history, proxies, or analytics.
external publish needs independent revoke, expiry, audit, and limit behavior.
```

Caddy requirements:

```text
Caddy exposes /nisb/mcp publicly.
Caddy forwards /nisb/mcp to mcp-nisb /mcp.
Do not expose internal container URLs.
Do not route /nisb/mcp into the ordinary API gateway.
Do not rewrite the path so that nisb_mcp.py no longer receives /mcp.
```

Cloudflare requirements:

```text
Skip browser integrity checks for MCP path.
Do not enable HTML challenge for MCP JSON-RPC POST.
Use path-scoped rate limiting.
Use WAF logs for audit only.
Room-level authorization belongs to NISB external_mcp_publish.
```

## 11. Runtime Guardrails

External MCP invocation must not rewrite the source room runtime policy.

When a source room is called externally:

```text
RAG should still use the RAG / knowledge path.
builtin MCP should still use the builtin external provider path.
room MCP should still use the room provider path.
plain worker should still use the LLM path.
supervisor should still use supervisor orchestration.
workspace / skill / fs / notebook behavior should follow source room policy.
```

Forbidden regressions:

```text
RAG enters MCP provider dispatch.
RAG returns missing_provider_id.
nested room MCP inherits the outer external publish scope.
builtin MCP is misclassified as a room provider.
source supervisor loses its worker selection ability.
external publish scope rewrites source room internal worker policy.
external client sees source room private execution traces.
```

Minimum runtime regression status:

```text
LibreChat provider_call proves the source room can return final text.
When source room reply_mode=direct_role, LibreChat receives an answer matching that mode.
When source room supervisor answers directly, LibreChat receives a valid answer.
When mcp_overrides.notebook_write_enabled is enabled, consecutive LibreChat questions can use the source room side-memory behavior.
The owner room records the external caller message, currently displayed as unknown.
```

Observed owner room UI behavior:

```text
External LibreChat question appears in the owner room as:
👤 unknown

Example:
How is transportation in Dali?
```

Current judgment:

```text
This is not a P1 blocker.
It proves the external MCP client question reaches the source room conversation/execution chain.
Future UI polish can display External MCP Client, client_label, or External MCP: <client_label>.
```

Future runtime matrix:

```text
source RAG worker
source builtin MCP worker
source nested room MCP worker
source supervisor + multiple workers
workspace / notebook / focus_root
final-only answer
no worker / observation / private trace exposure
```

Release judgment:

```text
Minimum runtime guardrail passed.
Full worker matrix can be handled as post-P1 regression enhancement.
```

## 12. imported_remote Regression Baseline

External publish must not affect:

```text
provider_origin=imported_remote
remote_peer_id
grant_id
artifact_id
source_room_id
federation invoke
source revoke
imported deny
grant provider mismatch
nested self-bound room MCP
```

Required protection:

```text
active grant -> usable
source revoke -> GRANT_REVOKED
same old grant -> error/no fallback
new grant -> success
result_view=final_result_only
source_observation_allowed=false
owner_private_scope_exposed=false
```

Current status:

```text
Minimum regression passed.
vps-b joining a vps-a room works.
Federation MCP revoked behavior works.
Other major federation MCP functions work.
external_mcp_publish did not break imported_remote / federation.
```

Release judgment:

```text
Minimum imported_remote / federation regression passed.
Full archive matrix remains recommended as a post-release regression task.
```

## 13. Token Lifecycle Rules

P1 includes two limits:

```text
max_calls: maximum successful question count.
expires_at: token expiration time.
```

P1 does not include:

```text
daily quota.
hourly quota.
package quota.
billing.
OAuth scope.
marketplace.
```

max_calls rules:

```text
max_calls=0 means unlimited.
empty max_calls means the UI intends unlimited; backend stores 0.
max_calls=1 allows one successful question; the second room_provider_call fails.
max_calls=N allows N successful questions.
max_calls must be empty or a positive integer.
used_count counts only successful room_provider_call.
initialize / tools-list / room_provider_list do not consume max_calls.
Failed calls do not increase used_count.
Failed calls do not refresh last_used_at.
```

Expiration rules:

```text
Minimum validity: 1 hour.
Maximum validity: 30 days.
Default validity: 30 days.
Owner can enter a valid number of days.
0.0417 days is approximately 1 hour.
Backend converts days to expires_at.
Expired tokens fail.
Revoked tokens fail immediately.
Regenerate invalidates the old token and makes the new token work.
```

Validated cases:

```text
Validity: 0.0417 days, max_calls: 1
=> first call succeeds
=> used_count=1
=> last_used_at updates
=> second call fails with external_publish_call_limit_exceeded

Validity: 0.0417 days, max_calls empty
=> max_calls stored as 0
=> repeated calls are not blocked by call limit
=> token fails with external_publish_expired after about 1 hour

Validity: 50 days
=> backend rejects the request
=> error: expires_in_days must be no more than 30 days

Validity: 30 days or default
=> expires_at is about 30 days later
=> repeated calls are not blocked by expiry before that time
```

## 14. Next Release Work

Current work should move into release preparation.

### 14.1 Public wording

Recommended English wording:

```text
NISB now supports room-scoped external MCP publish.
A room owner can generate a revocable, expiring Bearer token/config for one room.
External MCP clients can ask that single room and receive final-only answers governed by the owner’s room settings.
```

Recommended Chinese wording:

```text
NISB 已支持 Room MCP 外部发布。
room owner 可以为单个 room 生成可撤销、可过期、可限制成功提问次数的 MCP 外部接入配置。
支持 MCP Streamable HTTP + Bearer header 的外部客户端可接入该 room，并只获得 final-only 最终回答。
```

Avoid:

```text
All MCP clients are supported.
OAuth marketplace is supported.
All clients work without configuration.
External clients can access all rooms.
External clients can browse the provider catalog.
External clients can export worker traces.
```

### 14.2 External tool schema polish

Recommended external schema:

```text
room_provider_list:
  debug optional

room_provider_call:
  question required
  provider_id optional
```

Do not expose unnecessary internal parameters to third-party clients:

```text
room_id
consumer_room_id
include_imported_remote
include_builtin
include_raw
allow_non_room_provider
```

Reason:

```text
These are internal compatibility and debug parameters.
external_mcp_publish_scope already determines the single room provider.
Exposing too many internal parameters increases misuse and confusion.
```

### 14.3 Source room sender display

Current behavior:

```text
External MCP client messages appear as unknown in the owner room UI.
```

Future improvement:

```text
Display as External MCP Client.
Display client_label.
Display External MCP: <client_label>.
```

Priority:

```text
Post-P1 polish.
Not a release blocker.
```

### 14.4 Runtime matrix expansion

Future tests:

```text
source RAG
source builtin MCP
source nested room MCP
source supervisor + workers
workspace / notebook / focus_root
final-only answer
no worker / observation / private trace exposure
```

### 14.5 More client adapters

Suggested order:

```text
Archive MCP Inspector screenshots/logs.
Evaluate Claude Desktop streamable-http / bridge path.
Evaluate stdio-only client bridge.
Keep OAuth-only clients for a later version.
```

## 15. Final Validation Matrix

P1 required:

```text
owner enables external MCP publish
external MCP config is generated
plaintext token is shown once
refresh no longer shows plaintext token
external_mcp_publish.json does not store plaintext token
external_mcp_publish.json stores token_hash
external client initialize succeeds
tools/list succeeds
provider_list count=1
tools/call returns real room text
external client cannot see other rooms
owner_private_scope_exposed=false
source_observation_allowed=false
revoked old token fails
expired token fails
regenerated old token fails
new token succeeds
max_calls=1 succeeds once and fails second time
empty max_calls means unlimited
used_count / last_used_at update only after successful call
source room reply_mode applies
same-VPS local_room_shared does not regress
cross-VPS imported_remote / federation does not regress
```

Completed:

```text
owner enable external MCP publish
owner regenerate external MCP publish
owner revoke external MCP publish
external MCP config generation
plaintext token shown once
external_mcp_publish.json stores no plaintext token
external_mcp_publish.json stores token_hash
copied MCP config contains real Bearer token
Caddy /nisb/mcp forwarding works
nisb_mcp.py Bearer mode works
external_mcp_publish_scope works
minimal Node client initialize / tools-list / provider-list / provider-call works
MCP Inspector local application test works
LibreChat initialize works
LibreChat tools/list works
LibreChat room_provider_list UI works
LibreChat room_provider_call UI works
provider_list count=1
provider_call returns real room text
owner_private_scope_exposed=false
source_observation_allowed=false
revoked old token fails
expired token fails
regenerated old token fails
regenerated new token succeeds
max_calls=1 first call succeeds and second call fails
empty max_calls / max_calls=0 allows repeated calls
used_count / last_used_at update
50-day invalid validity is rejected
expired UI state is shown
direct_role reply mode works
supervisor direct-answer mode works
notebook_write_enabled side-memory scenario works
existing federation/imported_remote main path does not regress
federation MCP revoked behavior works
```

P1 conclusion:

```text
Passed.
```

Post-P1 improvements:

```text
Formal Claude Desktop validation.
Minimal external schema.
External MCP Client sender display.
Full RAG / builtin MCP / nested room MCP worker matrix.
More client compatibility notes.
```

Do not claim:

```text
OAuth marketplace support.
All MCP clients work without adaptation.
External access to multiple rooms.
External access to provider catalog.
External worker trace visibility.
Billing / quota packages.
```

Release conclusion:

```text
NISB Room MCP External Publish P1 minimum release loop has passed.
Minimal MCP client works.
MCP Inspector local application test works.
LibreChat works as a real third-party MCP client.
Token lifecycle works.
Further external platform work is mostly client adaptation, not proof of core NISB external MCP server feasibility.
```

## 16. Expected File Tree

Backend new files:

```text
mcp-nisb/tools/rooms_shared/room_mcp_external_publish_store.py
mcp-nisb/tools/rooms_shared/room_mcp_external_config_builder.py
mcp-nisb/tools/rooms_shared/room_mcp_external_publish_service.py
mcp-nisb/tools/rooms_shared/room_tools_external_mcp_publish.py
mcp-nisb/tools/rooms_shared/room_mcp_external_grant_resolver.py
```

Backend modified/connected files:

```text
mcp-nisb/tools/rooms_shared/room_mcp_external_export.py
mcp-nisb/tools/rooms_shared/__init__.py
mcp-nisb/tools/rooms_shared/tools.py
mcp-nisb/nisb_mcp.py
mcp-nisb/schema.json
```

Frontend new files:

```text
nisb-web/src/composables/editor/room/use_room_settings_external_mcp_publish.js
nisb-web/src/components/Editor/Room/RoomSettingsExternalMcpPublishCard.vue
```

Frontend connected files:

```text
nisb-web/src/composables/editor/room/use_room_settings_form.js
nisb-web/src/components/Editor/Room/RoomSettingsRoomMcpPanel.vue
nisb-web/src/components/Editor/Room/RoomSettingsOrchestrationCard.vue
nisb-web/src/components/Editor/Room/RoomSettingsModal.vue
```

LibreChat-related files:

```text
/opt/librechat/librechat.yaml
docker-compose.yml
LibreChat-API container environment variable NISB_ROOM_MCP_TOKEN
LibreChat API logs
```

If `tree` does not show new files while UI does:

```text
Check whether tree points to an old directory.
Check whether container paths match host paths.
Check whether frontend build cache is stale.
Check whether new files live in another working directory.
```

## 17. Documentation Update Rules

### owner enable

Status:

```text
Complete.
```

Evidence:

```text
UI enable works.
Plaintext token is shown once.
external_mcp_publish.json stores token_hash.
Copied config contains Bearer token.
```

### minimal MCP client

Status:

```text
Complete.
```

Evidence:

```text
initialize works.
tools/list works.
room_provider_list works.
room_provider_call works.
provider_list count=1.
```

### MCP Inspector

Status:

```text
Local application test complete.
```

Evidence:

```text
endpoint connects.
Authorization Bearer works.
tools/list shows room_provider_list / room_provider_call.
```

### LibreChat

Status:

```text
Complete.
```

Evidence:

```text
LibreChat initialization works.
Tools: room_provider_list, room_provider_call.
room_provider_list works.
room_provider_call works.
real room text is returned.
```

### revoke / expiry / regenerate

Status:

```text
Complete.
```

Evidence:

```text
revoked old token fails.
regenerated old token fails.
regenerated new token succeeds.
expired token fails with external_publish_expired.
max_calls=1 second call fails with external_publish_call_limit_exceeded.
used_count / last_used_at update.
```

### runtime regression

Status:

```text
Minimum regression complete.
Full matrix remains post-P1 enhancement.
```

Evidence:

```text
direct_role reply mode works through external call.
supervisor direct-answer mode works through external call.
notebook_write_enabled side-memory scenario works.
external client receives final answer only.
```

### imported_remote / federation

Status:

```text
Minimum regression complete.
```

Evidence:

```text
vps-b joining a vps-a room works.
federation MCP revoked behavior works.
other major federation MCP functions work.
```

## 18. LibreChat Notes

This LibreChat integration is a major external MCP publish milestone.

Environment:

```text
https://nisb.example.com is the NISB publisher.
https://nisb.dev is the user-owned LibreChat instance.
LibreChat-API sends MCP HTTP requests to nisb.me.
librechat.yaml is the LibreChat MCP entry point.
```

Final config shape:

```yaml
mcpServers:
  nisb:
    type: streamable-http
    url: https://nisb.example.com/nisb/mcp
    headers:
      Authorization: Bearer ${NISB_ROOM_MCP_TOKEN}
    chatMenu: true
    startup: true
    serverInstructions: false
    initTimeout: 60000
    timeout: 300000
```

External tools:

```text
room_provider_list
room_provider_call
```

Internal mapping:

```text
room_provider_list -> nisb_room_mcp_external_provider_list
room_provider_call -> nisb_room_mcp_external_provider_call
```

Successful LibreChat log shape:

```text
[MCP][nisb] URL: https://nisb.example.com/nisb/mcp
[MCP][nisb] OAuth Required: false
[MCP][nisb] Capabilities: {"tools":{}}
[MCP][nisb] Tools: room_provider_list, room_provider_call
[MCP][nisb] Initialized in: <ms>
```

Successful UI result:

```text
NISB Room MCP external providers:
count=1
result_view=final_result_only
source_observation_allowed=false
owner_private_scope_exposed=false
- room_provider__room_1780576710178_8d254b | External MCP Client | origin=local_room_shared | source_room=room_1780576710178_8d254b
```

Provider call success:

```text
LibreChat runs room_provider_call.
NISB returns final text from the source room.
```

Historical failure:

```text
The old tool name nisb_room_mcp_external_provider_list contained _mcp_.
LibreChat generated nisb_room_mcp_external_provider_list_mcp_nisb.
LibreChat split the name incorrectly and could not find the tool.
```

Final fix:

```text
External tools were renamed to room_provider_list and room_provider_call.
External tool names no longer contain _mcp_.
nisb_mcp.py handles alias normalization.
Internal canonical tools remain unchanged.
```

Image boundary:

```text
Image rendering in LibreChat is not part of the P1 release criterion.
P1 targets final-only text answers.
```

## 19. Caddy / api_gateway.py / nisb_mcp.py

### 19.1 Caddy

Responsibilities:

```text
Expose https://nisb.example.com/nisb/mcp.
Forward external requests to mcp-nisb /mcp.
Hide internal container addresses and ports.
Keep the same endpoint for LibreChat, Node clients, and MCP Inspector.
```

Current status:

```text
LibreChat-API calls https://nisb.example.com/nisb/mcp.
mcp-nisb receives POST /mcp.
nisb_mcp.py logs path=/mcp.
```

Risks:

```text
Do not route /nisb/mcp into the ordinary api_gateway.py.
Do not break /mcp path rewriting.
Do not let Cloudflare HTML challenges block MCP JSON-RPC POST.
Do not expose internal URLs to third-party clients.
```

### 19.2 `api_gateway.py`

`api_gateway.py` is not the main execution entry for LibreChat MCP access.

Boundary:

```text
Keep ordinary HTTP API gateway responsibilities.
Do not make it the main streamable-http MCP entry point.
Do not make it the core Bearer external_mcp_publish_token router.
Do not route tools/list or tools/call through it for this path.
```

Conclusion:

```text
LibreChat success should be verified through nisb_mcp.py initialize / tools-list / tools-call, not ordinary api_gateway.py endpoints.
api_gateway.py does not need more changes for the LibreChat MCP path.
```

### 19.3 `nisb_mcp.py`

`nisb_mcp.py` is the core external MCP facade.

Responsibilities:

```text
Handle MCP initialize.
Handle notifications/initialized.
Handle ping.
Handle tools/list.
Handle tools/call.
Detect Authorization Bearer.
Resolve external_mcp_publish_scope.
Return short tool names to Bearer external clients.
Map short names back to canonical tools.
Inject external scope into provider_list / provider_call.
```

Key design:

```text
External client-facing names:
room_provider_list
room_provider_call

Internal canonical names:
nisb_room_mcp_external_provider_list
nisb_room_mcp_external_provider_call
```

Reason:

```text
Third-party clients do not need to see NISB internal naming.
Some clients rewrite or append tool names.
Short tool names reduce compatibility risk.
Internal canonical names stay unchanged.
```

Conclusion:

```text
nisb_mcp.py is the external MCP facade.
Runtime, provider adapters, and federation grant logic should not absorb external client naming workarounds.
```

## 20. External Platform Compatibility

Based on minimal Node client, MCP Inspector local application test, and LibreChat:

```text
NISB Room MCP External Publish has sufficient MCP infrastructure for external system access.
```

Reasonable client requirements:

```text
Supports MCP Streamable HTTP transport.
Can configure URL.
Can configure Authorization Bearer header.
Can run initialize.
Can run tools/list.
Can run tools/call.
Can receive text content results.
```

Not guaranteed:

```text
stdio-only clients.
OAuth-only clients.
Clients that cannot configure headers.
Clients that forcibly rewrite tool names in incompatible ways.
Marketplace-manifest-only clients.
Clients requiring special image/resource rendering.
```

Client tiers:

```text
Tier A: supports Streamable HTTP + Bearer header + tools/list + tools/call.
Expected result: should connect with normal configuration and validation.

Tier B: supports MCP but only through SSE / stdio / OAuth / special proxy.
Expected result: needs adaptation; this does not invalidate NISB infrastructure.

Tier C: cannot configure custom MCP servers or headers.
Expected result: not supported in P1.
```

Public compatibility statement:

```text
Any MCP client that supports Streamable HTTP, configurable Authorization Bearer headers, tools/list, and tools/call should be able to connect to one published NISB room through the external_mcp_publish config.
```

Boundary statement:

```text
Different clients may differ in tool name handling, header configuration, session caching, OAuth preference, or multimedia rendering.
These are client adaptation issues and do not invalidate the NISB Room MCP External Publish baseline.
```

## 21. Conclusion

This was not a rewrite of NISB room federation.

The existing federation and Room MCP work provided the foundation:

```text
room provider_id / source_room_id semantics
room provider/runtime invocation foundation
room_mcp_publication
room meta/state/events storage
owner / participant / revoke reference semantics
nisb_mcp.py static tool registration
room_mcp_external_export.py P0 facade
federation/imported_remote revoke experience
final_result_only boundary experience
```

This phase added:

```text
third-party external_mcp_publish token
Authorization Bearer external_mcp_publish_token
single-room scope
revoke / expiry / regenerate / max_calls / last_used / used_count
owner UI lifecycle
real external MCP client validation
LibreChat streamable-http integration
MCP Inspector local application test
client-facing short tool aliases
```

Milestones reached:

```text
owner enable external publish works
external_mcp_publish.json write works
Bearer token access works
minimal Node client works
MCP Inspector local application test works
LibreChat works
room_provider_list works
room_provider_call works
count=1 works
final-only text response works
revoke works
regenerate works
old token invalid works
expiry works
max_calls works
used_count / last_used_at works
direct_role reply mode works
supervisor direct-answer mode works
notebook_write_enabled side-memory scenario works
federation/imported_remote minimum regression works
```

Current next step:

```text
Move into NISB External MCP Publish P1 release preparation.
Polish UI wording.
Polish schema.
Improve external sender display.
Expand the runtime worker matrix.
Evaluate Claude Desktop / stdio bridge compatibility.
```

Final anchor:

```text
room-scoped external MCP publish
```

Final release judgment:

```text
NISB Room MCP External Publish P1 minimum release loop has passed.

A room owner can generate an external MCP access config for one room.
External MCP clients can connect through a Bearer token.
External clients see only room_provider_list and room_provider_call.
External clients can access only the authorized source room.
External clients receive final-only answers.
The owner can revoke, regenerate, expire, and limit access.
Old tokens, expired tokens, revoked tokens, and over-limit tokens fail.
Existing federation/imported_remote main paths remain intact.
Source room reply_mode applies to external MCP calls.

This phase is valid as the P1 release baseline for NISB external MCP access.
```
