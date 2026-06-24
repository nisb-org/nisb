from __future__ import annotations

from typing import Any, Dict, List, Optional

from .room_contracts import as_bool, ensure_request_id, new_id, require_safe_id, utc_iso
from .room_helpers import (
    _get_active_role_objects,
    _resolve_default_reply_role,
    resolve_role_for_content,
)
from .room_state_normalizer import (
    _normalize_room_state_for_output,
    _safe_dict,
    _safe_list,
    _safe_str,
)
from .room_store import (
    append_room_event,
    ensure_room_exists,
    get_basepath,
    is_participant,
    load_state_doc,
    touch_room_updated_at,
)
from .room_tool_common import (
    _build_tool_result_item,
    _missing_args,
    _permission_denied,
    _post_ok,
)
from .room_tools_meta import _resolve_room_actor_uid
from .room_packet_builder import (
    _build_room_message_payload,
    _empty_evidence_result,
    _normalize_mode_used,
)
from .room_runtime_admission import (
    _rt_build_provider_bridge_deny_packet,
)
from .room_runtime_admission_grant import (
    _rt_has_resolvable_grant_reference,
    _rt_is_capability_bridge_invoke,
    _rt_validate_provider_bridge_grant,
)
from .room_tools_runtime_control import (
    nisb_room_runtime_stop_current,
    nisb_room_runtime_pause_current,
    nisb_room_runtime_resume_from_checkpoint,
)
from .room_tools_runtime_current import (
    _build_running_runtime_result,
    _get_runtime_control_snapshot,
    nisb_room_runtime_control_snapshot,
)
from .room_tools_runtime_replay import (
    nisb_room_events_recent,
    nisb_room_events_replay,
    nisb_room_shared_recent,
)
from .room_runtime_execution import (
    _rt_handle_ai_mention_execution,
    _rt_handle_manual_mode,
    _rt_handle_orchestration_execution,
    _rt_handle_provider_bridge_skip,
    _rt_handle_role_execution,
    _rt_handle_shared_auto_disabled_gate,
    _rt_handle_supervisor_direct_execution,
)

from .room_mcp_runtime_context import (
    _patch_provider_bridge_mcp_binding_args,
    _rt_append_tool_result,
    _rt_apply_mcp_binding_question_aliases,
    _rt_apply_question_aliases,
    _rt_build_execution_context,
    _rt_build_provider_bridge_tool_result,
    _rt_filter_active_role_objects_for_actor,
    _rt_inject_execution_context,
    _rt_is_provider_bridge_call,
    _rt_resolve_request_question,
    _rt_role_allowed_for_actor,
    _rt_safe_bool,
    _rt_safe_dict,
    _rt_safe_list,
    _rt_safe_str,
    _rt_shared_auto_reply_enabled_for_actor,
    _rt_supervisor_allowed_for_actor,
)

ROOM_ROLE_NOT_SHARED = "ROOM_ROLE_NOT_SHARED"
ROOM_SUPERVISOR_NOT_SHARED = "ROOM_SUPERVISOR_NOT_SHARED"
ROOM_RUNTIME_OWNER_SCOPE_REQUIRED = "ROOM_RUNTIME_OWNER_SCOPE_REQUIRED"
ROOM_RUNTIME_SCOPE_STRIPPED = "ROOM_RUNTIME_SCOPE_STRIPPED"
ROOM_SHARED_AUTO_REPLY_DISABLED = "ROOM_SHARED_AUTO_REPLY_DISABLED"
ROOM_RUNTIME_BLOCKED = "ROOM_RUNTIME_BLOCKED"
ROOM_PROVIDER_NO_REPLY_GENERATED = "ROOM_PROVIDER_NO_REPLY_GENERATED"


def _rt_request_has_direct_grant_reference(
    *,
    args: Dict[str, Any],
    provider_info: Optional[Dict[str, Any]] = None,
) -> bool:
    req = _rt_safe_dict(args)
    info = _rt_safe_dict(provider_info)
    mcp_binding = _rt_safe_dict(req.get("mcp_binding"))
    provider_snapshot = _rt_safe_dict(
        req.get("mcp_provider_snapshot")
        or req.get("provider_snapshot")
        or mcp_binding.get("provider_snapshot")
    )
    imported_provider = _rt_safe_dict(
        req.get("imported_provider")
        or mcp_binding.get("imported_provider")
    )
    room_source = _rt_safe_dict(info.get("room_source"))

    for obj in (
        req,
        mcp_binding,
        provider_snapshot,
        imported_provider,
        info,
        room_source,
        _rt_safe_dict(info.get("_grant_meta")),
        _rt_safe_dict(info.get("grant_meta")),
        _rt_safe_dict(info.get("grant")),
        _rt_safe_dict(req.get("_room_mcp_grant")),
        _rt_safe_dict(req.get("grant_meta")),
        _rt_safe_dict(req.get("grant")),
        _rt_safe_dict(mcp_binding.get("grant_meta")),
        _rt_safe_dict(mcp_binding.get("grant")),
    ):
        row = _rt_safe_dict(obj)
        if _rt_safe_str(row.get("grant_id")):
            return True
        if _rt_safe_str(row.get("artifact_id")):
            return True
        share_ref = _rt_safe_str(
            row.get("mcp_share_ref")
            or row.get("share_ref")
            or row.get("descriptor_ref")
        )
        if share_ref.startswith("room-mcp-grant:"):
            return True

    return False


def _build_room_route_state_tool_result(
    *,
    room_id: str,
    room_state: Dict[str, Any],
    reply_mode: str,
    supervisor_provider: str,
    supervisor_model: str,
    supervisor_temperature: Any,
    supervisor_max_tokens: Any,
    mcp_overrides: Dict[str, Any],
    model_name: str,
) -> Dict[str, Any]:
    return _build_tool_result_item(
        "room_route_state",
        room_id=room_id,
        supervisor_enabled=as_bool(room_state.get("supervisor_enabled"), False),
        reply_mode=reply_mode,
        default_reply_role_id=_safe_str(room_state.get("default_reply_role_id")),
        supervisor_provider=supervisor_provider,
        supervisor_model=supervisor_model,
        supervisor_temperature=supervisor_temperature,
        supervisor_max_tokens=supervisor_max_tokens,
        mcp_overrides=mcp_overrides,
        runtime_model=model_name,
        runtime_model_applied=False,
    )


def _dispatch_room_shared_provider_post(
    *,
    source_room_id: str,
    question: str,
    request_args: Dict[str, Any],
    provider_meta: Dict[str, Any],
) -> Dict[str, Any]:
    info = _rt_safe_dict(provider_meta)
    provider_origin = _rt_safe_str(
        info.get("provider_origin")
        or _rt_safe_dict(info.get("room_source")).get("provider_origin")
        or _rt_safe_dict(_rt_safe_dict(request_args).get("mcp_binding")).get("provider_origin")
        or _rt_safe_dict(_rt_safe_dict(request_args).get("mcp_provider_snapshot")).get("provider_origin")
        or _rt_safe_dict(_rt_safe_dict(request_args).get("provider_snapshot")).get("provider_origin")
        or _rt_safe_dict(_rt_safe_dict(request_args).get("imported_provider")).get("provider_origin")
    ).lower()

    actor_user_id = _safe_str(
        request_args.get("_room_mcp_actor_user_id")
        or request_args.get("actor_user_id")
        or request_args.get("user_id")
        or request_args.get("sender_user_id")
        or request_args.get("sender")
    )
    consumer_room_id = _safe_str(
        request_args.get("_room_mcp_consumer_room_id")
        or request_args.get("_room_id")
        or request_args.get("room_id")
    )

    target_question = _rt_resolve_request_question(request_args, fallback=question)
    bridge_args = _rt_apply_question_aliases(dict(request_args or {}), target_question)
    bridge_args["room_id"] = source_room_id
    bridge_args["_room_mcp_provider_call"] = True
    bridge_args["_room_mcp_provider_id"] = _safe_str(info.get("provider_id"))
    bridge_args["_room_mcp_provider_type"] = _safe_str(
        info.get("provider_type"),
        "room_shared_capability",
    )
    bridge_args["_room_mcp_provider_origin"] = provider_origin or "room_shared_capability"
    bridge_args["_room_mcp_source_room_id"] = source_room_id
    bridge_args["_room_mcp_consumer_room_id"] = consumer_room_id
    bridge_args["_room_mcp_actor_user_id"] = actor_user_id
    bridge_args["_room_mcp_bridge"] = _safe_str(
        request_args.get("_room_mcp_bridge"),
        "room_shared_capability",
    ) or "room_shared_capability"

    bridge_args["_room_mcp_provider_meta"] = info
    bridge_args["provider_meta"] = info

    mcp_binding = _rt_apply_mcp_binding_question_aliases(
        _rt_safe_dict(bridge_args.get("mcp_binding")),
        question=target_question,
        provider_id=_safe_str(info.get("provider_id")),
        provider_type=_safe_str(info.get("provider_type"), "room_shared_capability"),
        provider_origin=provider_origin or "room_shared_capability",
    )

    grant_meta = _rt_safe_dict(
        info.get("_grant_meta")
        or bridge_args.get("_room_mcp_grant")
        or bridge_args.get("grant_meta")
        or bridge_args.get("grant")
        or mcp_binding.get("grant_meta")
        or mcp_binding.get("grant")
    )
    if grant_meta:
        bridge_args["_room_mcp_grant"] = grant_meta
        bridge_args["grant_meta"] = grant_meta
        bridge_args["grant"] = grant_meta

        grant_id = _rt_safe_str(grant_meta.get("grant_id"))
        artifact_id = _rt_safe_str(grant_meta.get("artifact_id"))
        resolution_source = _rt_safe_str(grant_meta.get("resolution_source"))
        grant_state = _rt_safe_str(grant_meta.get("grant_state"))

        if grant_id:
            bridge_args["grant_id"] = grant_id
            mcp_binding["grant_id"] = grant_id
        if artifact_id:
            bridge_args["artifact_id"] = artifact_id
            mcp_binding["artifact_id"] = artifact_id
        if resolution_source:
            bridge_args["resolution_source"] = resolution_source
            mcp_binding["resolution_source"] = resolution_source
        if grant_state:
            bridge_args["grant_state"] = grant_state
            mcp_binding["grant_state"] = grant_state

    bridge_args["mcp_binding"] = mcp_binding

    if actor_user_id:
        bridge_args["actor_user_id"] = actor_user_id
        bridge_args["user_id"] = actor_user_id
        bridge_args["sender_user_id"] = actor_user_id
        bridge_args["sender"] = actor_user_id

    try:
        grant_check = _rt_safe_dict(
            _rt_validate_provider_bridge_grant(
                room_id=source_room_id,
                args=bridge_args,
                provider_info=info,
            )
        )
    except Exception as exc:
        grant_check = {
            "checked": True,
            "allowed": False,
            "reason_code": "grant_validation_exception",
            "grant_meta": grant_meta,
            "share_ref": _safe_str(bridge_args.get("mcp_share_ref") or bridge_args.get("share_ref")),
            "exception": str(exc),
        }

    if grant_check.get("checked") and not bool(grant_check.get("allowed", True)):
        denied_grant = _rt_safe_dict(grant_check.get("grant_meta")) or grant_meta
        reason_code = _rt_safe_str(grant_check.get("reason_code"), "grant_denied") or "grant_denied"
        deny_reason_code = reason_code.upper()
        provider_id = _safe_str(info.get("provider_id") or bridge_args.get("_room_mcp_provider_id"))
        provider_type = _safe_str(info.get("provider_type"), "room_shared_capability") or "room_shared_capability"
        provider_label = _safe_str(info.get("label") or provider_id)
        grant_id = _rt_safe_str(denied_grant.get("grant_id"))
        artifact_id = _rt_safe_str(denied_grant.get("artifact_id"))
        grant_state = _rt_safe_str(denied_grant.get("grant_state"))
        live_grant_state = _rt_safe_str(denied_grant.get("live_grant_state") or grant_state)
        share_ref = _rt_safe_str(
            grant_check.get("share_ref")
            or bridge_args.get("mcp_share_ref")
            or bridge_args.get("share_ref")
        )
        message = f"room provider invoke denied: {deny_reason_code}"

        return {
            "content": message,
            "response": message,
            "message": message,
            "final_response": message,
            "status": "error",
            "result_state": "error",
            "error": reason_code,
            "error_code": reason_code,
            "deny_reason_code": deny_reason_code,
            "summary": message,
            "result_view": _rt_safe_str(
                denied_grant.get("external_result_view")
                or denied_grant.get("result_view"),
                "final_result_only",
            ) or "final_result_only",
            "visibility_source": _rt_safe_str(denied_grant.get("discovery_mode")),
            "source_observation_allowed": bool(denied_grant.get("source_observation_allowed")),
            "replay_recoverable": False,
            "remote_execution_may_have_completed": False,
            "citations": [],
            "rss_evidence": [],
            "market_evidence": [],
            "evidence_result": {
                "citations": [],
                "rss_evidence": [],
                "market_evidence": [],
                "evidence_query": target_question,
                "evidence_tools": [],
            },
            "provider_trace": {
                "status": "denied",
                "deny_stage": "source_runtime_provider_bridge_grant_admission",
                "deny_reason_code": deny_reason_code,
                "provider_id": provider_id,
                "provider_type": provider_type,
                "provider_origin": provider_origin or "imported_remote",
                "source_room_id": source_room_id,
                "consumer_room_id": consumer_room_id,
            },
            "grant_trace": {
                "status": "denied",
                "deny_stage": "source_runtime_provider_bridge_grant_admission",
                "deny_reason_code": deny_reason_code,
                "reason_code": reason_code,
                "provider_id": provider_id,
                "source_room_id": source_room_id,
                "consumer_room_id": consumer_room_id,
                "grant_id": grant_id,
                "artifact_id": artifact_id,
                "grant_state": grant_state,
                "live_grant_state": live_grant_state,
                "share_ref_present": bool(share_ref),
                "checked": bool(grant_check.get("checked")),
            },
            "network_trace": {},
            "consume_trace": {
                "status": "denied",
                "deny_reason_code": deny_reason_code,
                "grant_id": grant_id,
                "artifact_id": artifact_id,
                "grant_state": grant_state,
            },
            "tool_calls": [],
            "tool_results": [
                {
                    "type": "room_mcp_grant_live_check",
                    "name": "room_mcp_grant_live_check",
                    "tool_name": "room_mcp_grant_live_check",
                    "status": "denied",
                    "deny_stage": "source_runtime_provider_bridge_grant_admission",
                    "deny_reason_code": deny_reason_code,
                    "reason_code": reason_code,
                    "provider_id": provider_id,
                    "provider_type": provider_type,
                    "provider_origin": provider_origin or "imported_remote",
                    "provider_label": provider_label,
                    "source_room_id": source_room_id,
                    "consumer_room_id": consumer_room_id,
                    "grant_id": grant_id,
                    "artifact_id": artifact_id,
                    "grant_state": grant_state,
                    "live_grant_state": live_grant_state,
                    "share_ref_present": bool(share_ref),
                },
                {
                    "type": "room_mcp_provider_error",
                    "name": "room_mcp_provider_error",
                    "tool_name": "room_mcp_provider_error",
                    "status": "error",
                    "error": reason_code,
                    "error_code": reason_code,
                    "deny_reason_code": deny_reason_code,
                    "provider_id": provider_id,
                    "provider_type": provider_type,
                    "provider_origin": provider_origin or "imported_remote",
                    "provider_label": provider_label,
                    "source_room_id": source_room_id,
                    "consumer_room_id": consumer_room_id,
                    "grant_id": grant_id,
                    "artifact_id": artifact_id,
                    "grant_state": grant_state,
                    "message": message,
                },
            ],
        }

    return _nisb_room_shared_post_impl(
        bridge_args,
        allow_nonparticipant_actor=True,
        provider_info=info,
    )


def _nisb_room_shared_post_impl(
    args: Dict[str, Any],
    *,
    allow_nonparticipant_actor: bool = False,
    provider_info: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    basepath = get_basepath(args)
    uid = _safe_str(args.get("_room_mcp_actor_user_id")) if allow_nonparticipant_actor else ""
    if not uid:
        uid = _resolve_room_actor_uid(basepath, args)
    rid = ensure_request_id(args)

    room_id = require_safe_id("room_id", args.get("room_id"))

    args = _patch_provider_bridge_mcp_binding_args(
        args,
        provider_info=provider_info,
    )

    content = _rt_resolve_request_question(args)
    args = _rt_apply_question_aliases(args, content)
    if not content:
        return _missing_args(rid, room_id, "missing room_id/content")

    provider_bridge_call = _rt_is_provider_bridge_call(args, provider_info)

    meta = ensure_room_exists(room_id)
    source_participant = bool(meta and is_participant(uid, meta))
    if meta and not source_participant:
        if not allow_nonparticipant_actor or not provider_bridge_call:
            return _permission_denied(rid, room_id)

    model_name = str(args.get("model") or "gpt-4o-mini").strip() or "gpt-4o-mini"
    rag_mode = _normalize_mode_used(args.get("rag_mode") or args.get("mode_used") or "off")
    mode_used = rag_mode

    raw_room_state = _safe_dict(load_state_doc(room_id))
    room_state = _normalize_room_state_for_output(raw_room_state)
    reply_mode = _safe_str(room_state.get("reply_mode")) or "manual"
    supervisor_provider = _safe_str(room_state.get("supervisor_provider"))
    supervisor_model = _safe_str(room_state.get("supervisor_model"))
    supervisor_temperature = room_state.get("supervisor_temperature")
    supervisor_max_tokens = room_state.get("supervisor_max_tokens")
    mcp_overrides = _safe_dict(room_state.get("mcp_overrides"))

    request_args = _rt_apply_question_aliases(dict(args or {}), content)
    request_args["basepath"] = basepath
    request_args["request_id"] = rid

    outer_room_id = _safe_str(args.get("_room_id"))
    if outer_room_id and outer_room_id != room_id:
        request_args["_outer_room_id"] = outer_room_id

    request_args["room_id"] = room_id
    request_args["_room_id"] = room_id
    request_args["runtime_room_id"] = room_id
    request_args["worker_room_id"] = room_id

    request_args["model"] = model_name
    request_args["mode_used"] = mode_used
    request_args["rag_mode"] = rag_mode
    request_args["reply_mode"] = reply_mode
    request_args["supervisor_provider"] = supervisor_provider
    request_args["supervisor_model"] = supervisor_model
    request_args["supervisor_temperature"] = supervisor_temperature
    request_args["supervisor_max_tokens"] = supervisor_max_tokens
    request_args["mcp_overrides"] = mcp_overrides
    request_args["_user_question"] = content
    request_args["mcp_binding"] = _rt_apply_mcp_binding_question_aliases(
        _rt_safe_dict(request_args.get("mcp_binding")),
        question=content,
        provider_id=_rt_safe_str(request_args.get("_room_mcp_provider_id")),
        provider_type=_rt_safe_str(request_args.get("_room_mcp_provider_type")),
        provider_origin=_rt_safe_str(request_args.get("_room_mcp_provider_origin")),
    )

    actor_uid = _safe_str(args.get("_room_mcp_actor_user_id")) or _resolve_room_actor_uid(basepath, args)
    request_args["actor_user_id"] = actor_uid
    request_args["user_id"] = actor_uid
    request_args["sender_user_id"] = actor_uid
    request_args["sender"] = actor_uid

    for k in (
        "_federation_peer_id",
        "_federation_remote_user_id",
        "_federation_remote_label",
        "_room_mcp_provider_call",
        "_room_mcp_provider_id",
        "_room_mcp_provider_type",
        "_room_mcp_provider_origin",
        "_room_mcp_source_room_id",
        "_room_mcp_consumer_room_id",
        "_room_mcp_actor_user_id",
        "_room_mcp_bridge",
    ):
        v = args.get(k)
        if v not in (None, ""):
            request_args[k] = v

    runtime_ctx = _rt_build_execution_context(
        request_args=request_args,
        meta=_safe_dict(meta),
        room_state=raw_room_state,
        payload=args if isinstance(args, dict) else None,
    )
    request_args = _rt_inject_execution_context(request_args, runtime_ctx)
    request_args = _rt_apply_question_aliases(request_args, content)

    request_args["room_id"] = room_id
    request_args["_room_id"] = room_id
    request_args["runtime_room_id"] = room_id
    request_args["worker_room_id"] = room_id

    request_args["mcp_binding"] = _rt_apply_mcp_binding_question_aliases(
        _rt_safe_dict(request_args.get("mcp_binding")),
        question=content,
        provider_id=_rt_safe_str(request_args.get("_room_mcp_provider_id")),
        provider_type=_rt_safe_str(request_args.get("_room_mcp_provider_type")),
        provider_origin=_rt_safe_str(request_args.get("_room_mcp_provider_origin")),
    )

    execution_user_id = _rt_safe_str(runtime_ctx.get("execution_user_id"))
    if execution_user_id:
        request_args["user_id"] = execution_user_id

    txt = content.strip()
    role, question = resolve_role_for_content(room_id, txt)
    route_mode = "mention_role"

    if not role and reply_mode == "direct_role":
        role, question = _resolve_default_reply_role(room_id, txt)
        route_mode = "default_reply_role"

    route_state_result = _build_room_route_state_tool_result(
        room_id=room_id,
        room_state=room_state,
        reply_mode=reply_mode,
        supervisor_provider=supervisor_provider,
        supervisor_model=supervisor_model,
        supervisor_temperature=supervisor_temperature,
        supervisor_max_tokens=supervisor_max_tokens,
        mcp_overrides=mcp_overrides,
        model_name=model_name,
    )

    provider_bridge_result = None
    if provider_bridge_call:
        provider_bridge_result = _rt_build_provider_bridge_tool_result(
            room_id=room_id,
            args=args,
            provider_info=provider_info,
            ctx=runtime_ctx,
            reply_mode=reply_mode,
            source_participant=source_participant,
        )

    capability_bridge_invoke = _rt_is_capability_bridge_invoke(
        args=request_args,
        provider_bridge_call=provider_bridge_call,
        provider_info=provider_info,
    )

    grant_reference_present = (
        _rt_has_resolvable_grant_reference(
            args=request_args,
            provider_info=provider_info,
        )
        or _rt_request_has_direct_grant_reference(
            args=request_args,
            provider_info=provider_info,
        )
    )

    grant_backed_capability_invoke = (
        capability_bridge_invoke
        and grant_reference_present
    )

    grant_validation: Dict[str, Any] = {
        "checked": False,
        "allowed": True,
        "reason_code": "",
        "grant_meta": {},
        "share_ref": "",
    }

    if grant_backed_capability_invoke:
        grant_validation = _rt_validate_provider_bridge_grant(
            room_id=room_id,
            args=request_args,
            provider_info=provider_info,
        )
        if not _rt_safe_bool(grant_validation.get("allowed"), True):
            return _rt_build_provider_bridge_deny_packet(
                room_id=room_id,
                rid=rid,
                rag_mode=rag_mode,
                mcp_overrides=mcp_overrides,
                content=content,
                provider_info=provider_info,
                runtime_ctx=runtime_ctx,
                reason_code=_rt_safe_str(grant_validation.get("reason_code")) or "grant_denied",
                deny_stage="source_invoke_admission",
                route_state_result=route_state_result,
                provider_bridge_result=provider_bridge_result,
                grant_validation=grant_validation,
            )

    active_role_objs = _get_active_role_objects(room_id, room_state)
    filtered_active_role_objs = _rt_filter_active_role_objects_for_actor(active_role_objs, runtime_ctx)
    authorized_active_role_objs = (
        active_role_objs
        if _rt_safe_bool(runtime_ctx.get("actor_is_room_owner"), False)
        else filtered_active_role_objs
    )
    request_args["authorized_active_role_ids_snapshot"] = [
        _rt_safe_str(_rt_safe_dict(x).get("role_id")) for x in filtered_active_role_objs
    ]
    shared_auto_enabled = _rt_shared_auto_reply_enabled_for_actor(runtime_ctx)

    should_guard_orchestration = (
        shared_auto_enabled
        and not txt.lower().startswith("@ai")
        and not role
        and reply_mode != "manual"
        and reply_mode != "supervisor_direct"
        and bool(authorized_active_role_objs)
    )

    if should_guard_orchestration:
        raw_state = _safe_dict(load_state_doc(room_id))
        runtime_snapshot = _get_runtime_control_snapshot(room_id=room_id, state=raw_state)
        running_run_id = _safe_str(runtime_snapshot.get("run_id"))
        running_request_id = _safe_str(raw_state.get("current_request_id"))
        runtime_state = _safe_str(runtime_snapshot.get("runtime_state"))
        can_accept_new_prompt = as_bool(runtime_snapshot.get("can_accept_new_prompt"), False)

        if running_run_id and not can_accept_new_prompt:
            if capability_bridge_invoke:
                return _rt_build_provider_bridge_deny_packet(
                    room_id=room_id,
                    rid=rid,
                    rag_mode=rag_mode,
                    mcp_overrides=mcp_overrides,
                    content=content,
                    provider_info=provider_info,
                    runtime_ctx=runtime_ctx,
                    reason_code=ROOM_RUNTIME_BLOCKED,
                    deny_stage="source_invoke_runtime_gate",
                    route_state_result=route_state_result,
                    provider_bridge_result=provider_bridge_result,
                    grant_validation=grant_validation,
                )

            return _post_ok(
                rid=rid,
                room_id=room_id,
                rag_mode=rag_mode,
                mcp_overrides=mcp_overrides,
                response=content,
                message=f"room runtime blocked: {runtime_state or 'running'}",
                mode_used=mode_used,
                evidence_query=content,
                evidence_result=_empty_evidence_result(content),
                runtime_control_snapshot=runtime_snapshot,
                tool_results=[
                    route_state_result,
                    _build_tool_result_item("runtime_control_snapshot", **runtime_snapshot),
                    _build_running_runtime_result(
                        room_id=room_id,
                        run_id=running_run_id,
                        request_id=running_request_id,
                        reply_mode=reply_mode,
                        active_role_objs=authorized_active_role_objs,
                        model_name=model_name,
                        status=runtime_state or "running",
                        runtime_control_snapshot=runtime_snapshot,
                    ),
                ],
            )

    if capability_bridge_invoke:
        if not shared_auto_enabled:
            return _rt_build_provider_bridge_deny_packet(
                room_id=room_id,
                rid=rid,
                rag_mode=rag_mode,
                mcp_overrides=mcp_overrides,
                content=content,
                provider_info=provider_info,
                runtime_ctx=runtime_ctx,
                reason_code=ROOM_SHARED_AUTO_REPLY_DISABLED,
                deny_stage="source_invoke_admission",
                route_state_result=route_state_result,
                provider_bridge_result=provider_bridge_result,
                grant_validation=grant_validation,
            )

        if reply_mode == "manual":
            return _rt_build_provider_bridge_deny_packet(
                room_id=room_id,
                rid=rid,
                rag_mode=rag_mode,
                mcp_overrides=mcp_overrides,
                content=content,
                provider_info=provider_info,
                runtime_ctx=runtime_ctx,
                reason_code=ROOM_SHARED_AUTO_REPLY_DISABLED,
                deny_stage="source_invoke_admission",
                route_state_result=route_state_result,
                provider_bridge_result=provider_bridge_result,
                grant_validation=grant_validation,
            )

        if role and not _rt_role_allowed_for_actor(role, runtime_ctx):
            return _rt_build_provider_bridge_deny_packet(
                room_id=room_id,
                rid=rid,
                rag_mode=rag_mode,
                mcp_overrides=mcp_overrides,
                content=content,
                provider_info=provider_info,
                runtime_ctx=runtime_ctx,
                reason_code=ROOM_ROLE_NOT_SHARED,
                deny_stage="source_invoke_admission",
                route_state_result=route_state_result,
                provider_bridge_result=provider_bridge_result,
                grant_validation=grant_validation,
            )

        if reply_mode == "supervisor_direct" and not _rt_supervisor_allowed_for_actor(runtime_ctx):
            return _rt_build_provider_bridge_deny_packet(
                room_id=room_id,
                rid=rid,
                rag_mode=rag_mode,
                mcp_overrides=mcp_overrides,
                content=content,
                provider_info=provider_info,
                runtime_ctx=runtime_ctx,
                reason_code=ROOM_SUPERVISOR_NOT_SHARED,
                deny_stage="source_invoke_admission",
                route_state_result=route_state_result,
                provider_bridge_result=provider_bridge_result,
                grant_validation=grant_validation,
            )

        if active_role_objs and not authorized_active_role_objs:
            return _rt_build_provider_bridge_deny_packet(
                room_id=room_id,
                rid=rid,
                rag_mode=rag_mode,
                mcp_overrides=mcp_overrides,
                content=content,
                provider_info=provider_info,
                runtime_ctx=runtime_ctx,
                reason_code=ROOM_ROLE_NOT_SHARED,
                deny_stage="source_invoke_admission",
                route_state_result=route_state_result,
                provider_bridge_result=provider_bridge_result,
                grant_validation=grant_validation,
            )

    user_payload = _build_room_message_payload(
        sender=uid,
        sender_type="user",
        content=content,
        model=model_name,
        mode_used=mode_used,
        evidence_query=content,
        evidence_tools=[],
        evidence_result=_empty_evidence_result(content),
    )

    evt = {
        "id": new_id("evt"),
        "ts": utc_iso(),
        "type": "room.message",
        "room_id": room_id,
        "request_id": rid,
        "payload": user_payload,
    }
    append_room_event(room_id, evt)
    touch_room_updated_at(room_id)

    from .room_helpers import _update_room_last_message
    _update_room_last_message(room_id, evt["id"])

    base_results_obj: Dict[str, Any] = {
        "tool_results": [
            _build_tool_result_item("room_event", event=evt),
            route_state_result,
        ]
    }

    if provider_bridge_call and provider_bridge_result:
        base_results_obj = _rt_append_tool_result(
            base_results_obj,
            provider_bridge_result,
        )

    base_tool_results = _rt_safe_list(base_results_obj.get("tool_results"))

    execution_result = _rt_handle_ai_mention_execution(
        rid=rid,
        room_id=room_id,
        rag_mode=rag_mode,
        mcp_overrides=mcp_overrides,
        mode_used=mode_used,
        model_name=model_name,
        txt=txt,
        content=content,
        evt=evt,
        request_args=request_args,
        base_tool_results=base_tool_results,
    )
    if execution_result is not None:
        return execution_result

    execution_result = _rt_handle_provider_bridge_skip(
        rid=rid,
        room_id=room_id,
        rag_mode=rag_mode,
        mcp_overrides=mcp_overrides,
        mode_used=mode_used,
        content=content,
        provider_bridge_call=provider_bridge_call,
        shared_auto_enabled=shared_auto_enabled,
        runtime_ctx=runtime_ctx,
        role=role,
        active_role_objs=_rt_safe_list(active_role_objs),
        base_tool_results=base_tool_results,
        room_shared_auto_reply_disabled_reason=ROOM_SHARED_AUTO_REPLY_DISABLED,
    )
    if execution_result is not None:
        return execution_result

    execution_result = _rt_handle_shared_auto_disabled_gate(
        rid=rid,
        room_id=room_id,
        rag_mode=rag_mode,
        mcp_overrides=mcp_overrides,
        mode_used=mode_used,
        content=content,
        shared_auto_enabled=shared_auto_enabled,
        role=role,
        route_mode=route_mode,
        reply_mode=reply_mode,
        runtime_ctx=runtime_ctx,
        active_role_objs=_rt_safe_list(active_role_objs),
        base_tool_results=base_tool_results,
        room_shared_auto_reply_disabled_reason=ROOM_SHARED_AUTO_REPLY_DISABLED,
    )
    if execution_result is not None:
        return execution_result

    execution_result = _rt_handle_role_execution(
        rid=rid,
        room_id=room_id,
        rag_mode=rag_mode,
        mcp_overrides=mcp_overrides,
        mode_used=mode_used,
        model_name=model_name,
        content=content,
        evt=evt,
        role=role,
        question=question,
        route_mode=route_mode,
        reply_mode=reply_mode,
        runtime_ctx=runtime_ctx,
        request_args=request_args,
        base_tool_results=base_tool_results,
        room_role_not_shared_reason=ROOM_ROLE_NOT_SHARED,
    )
    if execution_result is not None:
        return execution_result

    execution_result = _rt_handle_manual_mode(
        rid=rid,
        room_id=room_id,
        rag_mode=rag_mode,
        mcp_overrides=mcp_overrides,
        mode_used=mode_used,
        content=content,
        reply_mode=reply_mode,
        base_tool_results=base_tool_results,
    )
    if execution_result is not None:
        return execution_result

    execution_result = _rt_handle_supervisor_direct_execution(
        rid=rid,
        room_id=room_id,
        rag_mode=rag_mode,
        mcp_overrides=mcp_overrides,
        mode_used=mode_used,
        model_name=model_name,
        supervisor_model=supervisor_model,
        content=content,
        txt=txt,
        evt=evt,
        reply_mode=reply_mode,
        runtime_ctx=runtime_ctx,
        request_args=request_args,
        base_tool_results=base_tool_results,
        room_supervisor_not_shared_reason=ROOM_SUPERVISOR_NOT_SHARED,
    )
    if execution_result is not None:
        return execution_result

    execution_result = _rt_handle_orchestration_execution(
        rid=rid,
        room_id=room_id,
        rag_mode=rag_mode,
        mcp_overrides=mcp_overrides,
        mode_used=mode_used,
        model_name=model_name,
        content=content,
        txt=txt,
        evt=evt,
        reply_mode=reply_mode,
        runtime_ctx=runtime_ctx,
        request_args=request_args,
        active_role_objs=_rt_safe_list(active_role_objs),
        authorized_active_role_objs=_rt_safe_list(authorized_active_role_objs),
        base_tool_results=base_tool_results,
        room_role_not_shared_reason=ROOM_ROLE_NOT_SHARED,
    )
    if execution_result is not None:
        return execution_result

    if provider_bridge_call:
        return _rt_build_provider_bridge_deny_packet(
            room_id=room_id,
            rid=rid,
            rag_mode=rag_mode,
            mcp_overrides=mcp_overrides,
            content=content,
            provider_info=provider_info,
            runtime_ctx=runtime_ctx,
            reason_code=ROOM_PROVIDER_NO_REPLY_GENERATED,
            deny_stage="source_invoke_execution_empty",
            route_state_result=route_state_result,
            provider_bridge_result=provider_bridge_result,
            grant_validation=grant_validation,
        )

    return _post_ok(
        rid=rid,
        room_id=room_id,
        rag_mode=rag_mode,
        mcp_overrides=mcp_overrides,
        response=content,
        message="room message posted",
        mode_used=mode_used,
        evidence_query=content,
        evidence_result=_empty_evidence_result(content),
        tool_results=base_tool_results,
    )


def nisb_room_shared_post(args: Dict[str, Any]) -> Dict[str, Any]:
    return _nisb_room_shared_post_impl(
        args,
        allow_nonparticipant_actor=False,
        provider_info=None,
    )


def nisb_room_shared_provider_post(args: Dict[str, Any]) -> Dict[str, Any]:
    args = dict(_safe_dict(args))
    source_room_id = require_safe_id("room_id", args.get("room_id"))
    question = _rt_resolve_request_question(args)

    provider_meta = _rt_safe_dict(
        args.get("_room_mcp_provider_meta")
        or args.get("provider_meta")
    )

    if not provider_meta:
        mcp_binding = _rt_safe_dict(args.get("mcp_binding"))
        provider_meta = {
            "provider_id": _rt_safe_str(
                args.get("_room_mcp_provider_id")
                or args.get("provider_id")
                or mcp_binding.get("provider_id")
            ),
            "provider_type": _rt_safe_str(
                args.get("_room_mcp_provider_type")
                or args.get("provider_type")
                or mcp_binding.get("provider_type"),
                "room_shared_capability",
            ) or "room_shared_capability",
            "provider_origin": _rt_safe_str(
                args.get("_room_mcp_provider_origin")
                or args.get("provider_origin")
                or mcp_binding.get("provider_origin"),
                "imported_remote",
            ) or "imported_remote",
            "share_ref": _rt_safe_str(
                args.get("mcp_share_ref")
                or args.get("share_ref")
                or mcp_binding.get("share_ref")
            ),
            "room_source": {
                "room_id": source_room_id,
            },
        }

        grant_meta = _rt_safe_dict(
            args.get("_room_mcp_grant")
            or args.get("grant_meta")
            or args.get("grant")
            or mcp_binding.get("grant_meta")
            or mcp_binding.get("grant")
        )
        if grant_meta:
            provider_meta["_grant_meta"] = grant_meta

    room_source = _rt_safe_dict(provider_meta.get("room_source"))
    room_source["room_id"] = source_room_id
    provider_meta["room_source"] = room_source

    return _dispatch_room_shared_provider_post(
        source_room_id=source_room_id,
        question=question,
        request_args=args,
        provider_meta=provider_meta,
    )


__all__ = [
    "nisb_room_shared_post",
    "nisb_room_shared_provider_post",
    "nisb_room_runtime_control_snapshot",
    "nisb_room_runtime_stop_current",
    "nisb_room_runtime_pause_current",
    "nisb_room_runtime_resume_from_checkpoint",
    "nisb_room_shared_recent",
    "nisb_room_events_recent",
    "nisb_room_events_replay",
]

