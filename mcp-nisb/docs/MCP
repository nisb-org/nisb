# MCP Standardization Imported Remote Regression Baseline

Date: 2026-06-08

## 1. Purpose

This document records the regression baseline for Room MCP standardization after several high-risk regressions were fixed.

The tested path is federation-backed imported_remote Room MCP.

This means the remote VPS invocation depends on the existing NISB federation link and imported_remote adapter.

This document must not be used as proof that pure non-federated cross-VPS standard MCP export is complete.

## 2. Critical Boundary

There are two different layers that must not be confused.

### Federation-backed imported_remote

Expected markers:

```text
provider_origin=imported_remote
remote_peer_id=<remote peer, e.g. vps-a>
url=https://<source-host>/api/mcp/call
grant_id=<grant id>
artifact_id=<artifact id>
source_room_id=<source room id>
result_view=final_result_only
source_observation_allowed=false
```

This layer depends on NISB federation connectivity.

### Same-VPS external MCP export P0

Expected markers:

```text
provider_origin=local_room_shared
same VPS / same store
external MCP tools/call
published room provider registry
no federation/imported_remote participation
```

Both layers are valid.

They prove different things.

Do not use one to claim the other.

## 3. Confirmed Regression Coverage

This baseline confirms that MCP standardization did not break:

- Cross-VPS imported_remote Room MCP invocation
- Federation-backed remote provider call
- Active grant consumption
- Source-side revoke enforcement
- New grant restores availability
- Consumer-side formal deny after revoke
- final_result_only external result view
- Source room supervisor orchestration
- Source room builtin MCP worker
- Source room RAG worker
- Source room nested room MCP worker
- Source workspace / skills / memory / fs behavior
- No local fallback after remote grant denial

## 4. Regression Context

Three bugs were fixed during MCP standardization:

```text
1. Revoked grant was not enforced correctly
2. RAG worker was incorrectly routed into MCP provider dispatch
3. Source room with an internal room MCP worker failed during remote invocation
```

The fixes must preserve both the new standardization work and old room capabilities.

MCP standardization exposes room capability as a provider.

It must not rewrite how source room workers execute internally.

## 5. Core Runtime Principle

Outer MCP invocation is not inner worker policy.

Outer request may be:

```text
requested_mode=mcp
_room_mcp_provider_call=true
provider_origin=imported_remote
```

But inside the source room:

```text
RAG worker -> RAG / knowledge path
builtin MCP worker -> builtin external provider path
room MCP worker -> room provider path
plain worker -> LLM path
supervisor -> supervisor orchestration
workspace / skill / fs / notebook -> their own source room policies
```

Do not collapse these paths into one generic MCP provider dispatch.

## 6. Scenario A: Remote Consumer Calls Source Room

### Setup

A remote consumer room invokes a source room provider through imported_remote Room MCP.

Example outer provider:

```text
provider_id=room_provider__room_1767655102696_2ecd0b
provider_type=room_shared_capability
provider_origin=imported_remote
source_room_id=room_1767655102696_2ecd0b
grant_mode=share_artifact
discovery_mode=granted_visible
resolution_source=grant_artifact
```

Consumer view must be final-only:

```text
result_view=final_result_only
external_result_view=final_result_only
source_observation_allowed=false
```

### Consumer-side Success Evidence

Expected final result view:

```text
type=room_mcp_final_result_view
status=success
message=room orchestration finished
provider_id=room_provider__room_1767655102696_2ecd0b
provider_type=room_shared_capability
provider_origin=imported_remote
source_room_id=room_1767655102696_2ecd0b
grant_id=<active grant id>
artifact_id=<active artifact id>
grant_state=active
grant_mode=share_artifact
discovery_mode=granted_visible
resolution_source=grant_artifact
visibility_source=granted_visible
result_view=final_result_only
source_observation_allowed=false
```

Expected role runtime fact:

```text
requested_mode=mcp
tool_policy.mcp=true
provider_id=room_provider__room_1767655102696_2ecd0b
provider_status=success
status=success
binding_ready=true
```

### Interpretation

The imported_remote provider is usable while the grant is active.

The consumer receives only the final result.

The consumer does not observe source private scope.

## 7. Scenario B: Source Builtin MCP Worker

### Setup

The source room has a builtin MCP worker.

Example worker:

```text
role_name=美图 / 美图助手
provider_id=pexels
provider_label=Pexels Images
```

### Expected Evidence

Builtin MCP provider execution:

```text
type=room_mcp_provider_execution
provider_id=pexels
provider_type=preset
provider_origin=builtin_external
provider_label=Pexels Images
requested_mode=mcp
status=success
auth_type=api_key
auth_required=true
auth_configured=true
```

Provider tool result:

```text
type=room_mcp_provider
provider_id=pexels
tool_name=search
status=success
count=6
```

Role runtime fact:

```text
tool_policy.mcp=true
tool_policy.rag=false
provider_id=pexels
provider_status=success
status=success
evidence_tools includes pexels_api
```

### Interpretation

Builtin external MCP providers must continue to work inside a source room invoked through imported_remote.

The builtin MCP worker should not be mistaken for a room provider worker.

The builtin MCP worker should not be blocked by imported_remote grant context.

## 8. Scenario C: Source RAG Worker

### Setup

The source room has a RAG worker.

Example RAG worker:

```text
role_name=xinlixue_agent
group_id=xinlixue
```

### Expected RAG Evidence

RAG debug evidence should include:

```text
qa_debug.evidence_count > 0
evidence_scope_args.group_id=xinlixue
evidence_scope_debug.group_filter_applied=true
evidence_scope_debug.raw_hits > 0
evidence_scope_debug.kept > 0
citation_assembly.citations_after_normalize > 0
citations_count > 0 when evidence supports citations
```

Observed acceptable RAG shape from the test:

```text
group_id=xinlixue
raw_hits=12
kept=12
evidence_count=10
citations_count=2
candidate_docs_before_time=23
candidate_docs_after_time=23
published_at_coverage=1.0
```

### Required Runtime Shape

Expected role runtime fact shape:

```text
tool_policy.rag=true
tool_policy.mcp=false
provider_id=""
knowledge_scope.group_id=xinlixue
status=success
```

Evidence tools should include the RAG tool when surfaced at role fact level:

```text
evidence_tools includes nisb_qa_scope_ask
```

### Forbidden Failure

This must never happen for a RAG worker:

```text
provider_id=""
tool_policy.rag=true
knowledge_scope.group_id non-empty
=> room_mcp_provider_error missing_provider_id
```

### Interpretation

The RAG worker remained on the RAG / knowledge path.

Outer `requested_mode=mcp` did not force it into provider dispatch.

RAG group identity must never be converted into provider_id.

## 9. Scenario D: Source Nested Room MCP Worker

### Setup

The source room has an internal worker bound to another room MCP provider.

Example inner worker:

```text
role_name=6.4-01-mcp
provider_id=room_provider__room_1780576710178_8d254b
provider_label=6.4-01
```

### Source-side Inner Provider Evidence

Observed inner provider execution:

```text
type=room_mcp_provider_execution
role_name=6.4-01-mcp
provider_id=room_provider__room_1780576710178_8d254b
provider_type=room_shared_capability
provider_origin=local_room_shared
provider_label=6.4-01
requested_mode=mcp
status=success
auth_type=room_server_gate
auth_required=false
auth_configured=true
consumer_room_id=room_1767655102696_2ecd0b
source_room_id=room_1780576710178_8d254b
owner_private_scope_exposed=false
```

Observed inner role runtime fact:

```text
type=room_role_runtime_fact
role_name=6.4-01-mcp
requested_mode=mcp
status=success
tool_policy.mcp=true
tool_policy.rag=false
provider_id=room_provider__room_1780576710178_8d254b
provider_status=success
effective_execution_scope=room_shared
runtime_scope_stripped=true
```

### Required Identity Rule

For any room provider:

```text
provider_id=room_provider__<room_id>
source_room_id=<room_id>
room_source.room_id=<room_id>
```

In this test:

```text
provider_id=room_provider__room_1780576710178_8d254b
source_room_id=room_1780576710178_8d254b
```

### Required Context Isolation

The inner local room provider must not inherit the outer imported_remote grant context.

Forbidden inheritance:

```text
inner provider_origin=local_room_shared
inner grant_id=<outer imported_remote grant>
inner artifact_id=<outer imported_remote artifact>
inner source_room_id=<outer source room>
```

Expected inner local provider:

```text
provider_origin=local_room_shared
consumer_room_id=<current source room>
source_room_id=<inner provider room>
no GRANT_PROVIDER_MISMATCH caused by outer context
```

### Interpretation

Nested room MCP execution is preserved.

The source room can be invoked remotely through imported_remote, while still invoking another local room provider internally.

The inner provider identity is normalized correctly.

## 10. Scenario E: Source Supervisor and Room Capabilities

Source room supervisor must continue to behave as a source room supervisor.

Expected source-side evidence:

```text
delegate_count >= 1
delegate_non_empty_count >= 1
phase=completed
status=success
result_state=success
summary=room supervisor direct reply
```

If enabled by source room policy, these may remain active:

```text
supervisor_fs_read.status=success
supervisor_memory_read.status=success
supervisor_memory_resume.decision=restart_fresh
supervisor_skills.status=success
supervisor_skill_strategy=custom_only
supervisor_notebook_write.status=success
```

Outer imported_remote invocation must not strip legitimate source-side supervisor capabilities.

Consumer still receives only final-only output.

## 11. Scenario F: Source Revokes Grant

### Revoke Operation

Source side revokes the active grant:

```text
tool=nisb_room_mcp_grant_revoke
room_id=room_1767655102696_2ecd0b
grant_id=grant_1780949026424_c9b0b9
artifact_id=artifact_1780949026424_f59d80
provider_id=room_provider__room_1767655102696_2ecd0b
```

Expected revoke result:

```text
status=success
result_state=success
final_response=room mcp grant revoked
```

Expected grant state:

```text
grant_state=revoked
revoked_at=<timestamp>
revoked_by=<source owner user id>
scope.result_view=final_result_only
scope.bind_as_worker=true
scope.observe_source_room=false
```

### Interpretation

Revoke is source-side authority.

A revoked grant must not remain usable because the consumer has cached provider metadata.

## 12. Scenario G: Consumer Calls Again After Revoke

### Expected Deny

After revoke, the same consumer calls the same provider again.

Expected consumer response:

```text
content=room provider invoke denied: GRANT_REVOKED
response=room provider invoke denied: GRANT_REVOKED
status=error
message=room provider invoke denied: GRANT_REVOKED
result_state=error
```

Expected evidence result:

```text
provider_id=room_provider__room_1767655102696_2ecd0b
provider_origin=imported_remote
source_room_id=room_1767655102696_2ecd0b
remote_peer_id=vps-a
grant_id=grant_1780949026424_c9b0b9
artifact_id=artifact_1780949026424_f59d80
error=grant_revoked
error_code=grant_revoked
error_kind=remote_error
status_code=200
url=https://nisb.me/api/mcp/call
```

Expected final result view:

```text
type=room_mcp_final_result_view
status=error
final_response=room provider invoke denied: GRANT_REVOKED
provider_id=room_provider__room_1767655102696_2ecd0b
provider_origin=imported_remote
source_room_id=room_1767655102696_2ecd0b
grant_id=grant_1780949026424_c9b0b9
artifact_id=artifact_1780949026424_f59d80
result_view=final_result_only
source_observation_allowed=false
```

Expected role runtime fact:

```text
tool_policy.mcp=true
provider_id=room_provider__room_1767655102696_2ecd0b
provider_status=error
status=error
response_preview=room provider invoke denied: GRANT_REVOKED
```

### Interpretation

The revoked grant is enforced remotely.

The consumer receives a formal deny.

The runtime does not fallback to local direct_role or local LLM answer.

The error remains visible through final result view and role runtime fact.

## 13. Scenario H: New Grant Restores Availability

After revoke, a new grant may be issued.

Expected new active grant success:

```text
grant_id=<new grant id>
artifact_id=<new artifact id>
grant_state=active
provider_origin=imported_remote
source_room_id=room_1767655102696_2ecd0b
status=success
result_state=success
```

Observed shape:

```text
grant_id=grant_1780950297041_a4d023
artifact_id=artifact_1780950297041_318287
provider_id=room_provider__room_1767655102696_2ecd0b
provider_origin=imported_remote
source_room_id=room_1767655102696_2ecd0b
status=success
result_view=final_result_only
source_observation_allowed=false
```

Interpretation:

```text
old grant revoked -> denied
new grant active -> usable
```

This confirms revoke semantics are grant-specific and recoverable through a new active grant.

## 14. Required Invariants

### Imported Remote Invariant

For cross-VPS imported_remote Room MCP:

```text
provider_origin=imported_remote
source_room_id=<remote source room>
grant_id=<share grant>
artifact_id=<grant artifact>
remote_peer_id present or resolvable
```

### Local Nested Provider Invariant

For source-side nested local room provider:

```text
provider_origin=local_room_shared
provider_id=room_provider__<inner_room_id>
source_room_id=<inner_room_id>
consumer_room_id=<current source room>
```

### Revoke Invariant

After source-side revoke:

```text
same grant_id + artifact_id
=> GRANT_REVOKED
=> status=error
=> result_state=error
=> no fallback
```

### Final-only Invariant

For imported_remote consumer view:

```text
result_view=final_result_only
external_result_view=final_result_only
source_observation_allowed=false
owner_private_scope_exposed=false
```

### Worker Policy Invariant

Outer MCP invocation must not override inner worker policy:

```text
RAG worker -> RAG path
builtin MCP worker -> builtin external provider path
room MCP worker -> room provider path
plain worker -> LLM path
supervisor -> supervisor orchestration
```

### Provider Identity Invariant

For room providers:

```text
provider_id=room_provider__<room_id>
source_room_id=<room_id>
room_source.room_id=<room_id>
```

Outer source_room_id must not overwrite inner provider source identity.

## 15. Anti-Regressions

Future changes must not cause:

- Revoked grants to fallback to local model answers
- imported_remote to be silently converted to local_room_shared across VPS
- local_room_shared inner provider to inherit outer imported_remote grant_id
- source_room_id to become consumer_room_id
- final_result_only to leak source private execution details
- RAG workers to enter MCP provider dispatch
- RAG workers to fail with missing_provider_id
- RAG group_id to be converted into provider_id
- builtin external MCP workers to lose provider_origin=builtin_external
- nested room MCP workers to fail with GRANT_PROVIDER_MISMATCH due to outer context
- admission to be loosened to hide grant/provider mismatch
- remote errors to be washed into status=success
- source revoke deny to be hidden from consumer runtime facts

## 16. High-risk Files

Watch these files during future refactors:

```text
mcp-nisb/tools/rooms_shared/room_role_runtime_request.py
mcp-nisb/tools/rooms_shared/room_worker_execution.py
mcp-nisb/tools/rooms_shared/room_runtime_execution.py
mcp-nisb/tools/rooms_shared/room_tools_runtime.py
mcp-nisb/tools/rooms_shared/room_mcp_adapter_provider_context.py
mcp-nisb/tools/rooms_shared/room_mcp_provider_adapter.py
mcp-nisb/tools/rooms_shared/room_mcp_provider_bridge.py
mcp-nisb/tools/rooms_shared/room_mcp_bridge_grant_context.py
mcp-nisb/tools/rooms_shared/room_mcp_grant_service.py
```

Do not first fix these regressions in frontend role binding files unless backend logs prove frontend schema loss.

Frontend files that should not be first-line fixes:

```text
RoomRoleProviderBindingPanel.vue
RoomRolesDrawerProviderSection.vue
use_room_roles_drawer_provider_catalog.js
use_room_settings_room_mcp.js
```

## 17. Relation to Other Baselines

### Revoked Grant Pipeline Baseline

The revoked grant pipeline confirms:

```text
active grant -> usable
source revoke -> unavailable
new grant -> usable again
```

This document confirms that the same semantics hold through imported_remote federation-backed invocation.

### External MCP Export P0 Baseline

External MCP Export P0 confirms:

```text
same VPS / same store
external MCP tools/call
provider_origin=local_room_shared
no federation/imported_remote participation
```

This document confirms:

```text
cross VPS
NISB federation-backed invocation
provider_origin=imported_remote
remote peer / grant artifact involved
source revoke enforced remotely
source internal workers preserved
```

They are both important.

They are not the same proof.

## 18. Minimal Regression Checklist

Run this checklist after changes to provider adapter, provider context, grant context, role runtime, worker execution, or result view.

### A. Active imported_remote grant

Expected:

```text
provider_origin=imported_remote
status=success
result_state=success
result_view=final_result_only
source_observation_allowed=false
```

### B. Builtin MCP worker inside source

Expected:

```text
provider_id=pexels
provider_type=preset
provider_origin=builtin_external
status=success
evidence_tools includes pexels_api
```

### C. RAG worker inside source

Expected:

```text
tool_policy.rag=true
provider_id=""
knowledge_scope.group_id non-empty
group_filter_applied=true
evidence_count > 0
no missing_provider_id
```

### D. Nested room MCP worker inside source

Expected:

```text
inner provider_origin=local_room_shared
inner provider_id=room_provider__<inner_room_id>
inner source_room_id=<inner_room_id>
no outer grant_id inherited for local provider
no GRANT_PROVIDER_MISMATCH caused by outer context
```

### E. Source revoke

Expected:

```text
grant_state=revoked
final_response=room mcp grant revoked
```

### F. Consumer after revoke

Expected:

```text
status=error
result_state=error
final_response=room provider invoke denied: GRANT_REVOKED
no fallback
```

### G. New grant

Expected:

```text
new grant_id
new artifact_id
grant_state=active
status=success
```

## 19. Documentation Rule

When documenting this test, always include this sentence:

```text
This cross-VPS Room MCP regression test depends on the existing NISB federation/imported_remote chain. It is not proof of pure non-federated cross-VPS standard MCP export.
```

## 20. Final Position

The standardization target is a cleaner provider interface.

It is not a rewrite of source room runtime.

A source room invoked through MCP remains a room.

Its internal workers remain independent runtime units:

```text
RAG remains RAG
builtin MCP remains builtin MCP
nested room MCP remains room MCP
plain role remains LLM
supervisor remains supervisor
workspace / skill / fs / notebook remain governed by source policy
```
