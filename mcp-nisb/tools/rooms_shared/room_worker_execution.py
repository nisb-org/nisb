from __future__ import annotations

from typing import Any, Dict, List, Optional

from .room_audit_helpers import _build_dialog_lines, _load_room_state
from .room_binding_policy import (
    _binding_has_target,
    _resolve_effective_binding,
    _role_kb,
    _role_tool_policy,
)
from .room_contracts import as_bool
from .room_packet_builder import (
    _bridge_chat_result,
    _empty_evidence_result,
    _ensure_formal_packet,
    _normalize_qascope_packet,
)
from .room_request_bridge import (
    _build_orchestrate_args,
    _call_model_text_with_runtime,
    _normalize_room_mode,
    _safe_dict,
    _safe_list,
    _safe_str,
    _supervisor_runtime_request,
)
from .room_mcp_provider_adapter import dispatch_room_mcp_provider
from .supervisor_runtime.prompt_input import (
    _build_effective_room_question,
    _extract_user_question,
)
from .room_worker_memory_runtime import (
    append_worker_memory_runtime_fact,
    resolve_provider_safe_worker_question,
    resolve_rag_safe_worker_question,
    resolve_worker_supervisor_memory_context,
    stamp_worker_memory_request_args,
)
from .room_worker_rag_runtime import call_room_rag_qascope_packet

ROOM_ROLE_NOT_SHARED = "ROOM_ROLE_NOT_SHARED"
ROOM_SUPERVISOR_NOT_SHARED = "ROOM_SUPERVISOR_NOT_SHARED"
ROOM_RUNTIME_OWNER_SCOPE_REQUIRED = "ROOM_RUNTIME_OWNER_SCOPE_REQUIRED"
ROOM_RUNTIME_SCOPE_STRIPPED = "ROOM_RUNTIME_SCOPE_STRIPPED"


def _call_room_plain_reply(room_id: str, question: str, model_name: str) -> str:
    dialog = _build_dialog_lines(room_id, limit=30)
    prompt = "你在一个多人房间里协作。\\\\n请基于下面对话给出简洁、可执行的回复。\\\\n\\\\n" + "\\\\n".join(dialog) + f"\\\\n\\\\n用户对你说：{question}"
    text, _ = _call_model_text_with_runtime(model_name=model_name, user_prompt=prompt)
    return _safe_str(text)


def _call_role_reply_with_runtime(room_id: str, question: str, role: Dict[str, Any], model_name: str) -> Dict[str, Any]:
    dialog = _build_dialog_lines(room_id, limit=30)
    role_name = _safe_str(role.get("name"), "assistant")
    role_prompt = _safe_str(role.get("system_prompt"))
    kb = _role_kb(role)
    kb_time_filter_days = _safe_str(kb.get("time_filter_days") or kb.get("timeFilterDays"))
    kb_time_start = _safe_str(kb.get("time_start") or kb.get("timeStart"))
    kb_time_end = _safe_str(kb.get("time_end") or kb.get("timeEnd"))
    prompt = (
        f"你在 NISB 的 room 中扮演角色：{role_name}。\\\\n"
        f"角色设定：{role_prompt or '请保持稳定、清晰、可执行。'}\\\\n"
        f"知识绑定：library_id={_safe_str(kb.get('library_id') or kb.get('libraryid'))}, "
        f"group_id={_safe_str(kb.get('group_id') or kb.get('groupid'))}, "
        f"doc_id={_safe_str(kb.get('doc_id') or kb.get('docid'))}, "
        f"store_scope={_safe_str(kb.get('store_scope') or kb.get('storescope') or 'library')}, "
        f"evidence_scope={_safe_str(kb.get('evidence_scope') or kb.get('evidencescope') or 'library')}, "
        f"time_filter_days={kb_time_filter_days}, "
        f"time_start={kb_time_start}, "
        f"time_end={kb_time_end}。\\\\n"
        "请根据最近对话，用该角色身份给出简洁、自然、可执行的回复；不要复述系统说明。\\\\n\\\\n"
        "最近对话：\\\\n" + "\\\\n".join(dialog) + f"\\\\n\\\\n当前对你说：{question}"
    )
    text, runtime = _call_model_text_with_runtime(model_name=model_name, user_prompt=prompt)
    return {"content": _safe_str(text), "runtime": _safe_dict(runtime)}


def _call_role_reply(room_id: str, question: str, role: Dict[str, Any], model_name: str) -> str:
    return _safe_str((_call_role_reply_with_runtime(room_id=room_id, question=question, role=role, model_name=model_name) or {}).get("content"))


def _normalize_positive_int(value: Any) -> int:
    try:
        if value is None or value == "":
            return 0
        return max(0, int(float(value)))
    except Exception:
        return 0


def _pick_time_value(*values: Any) -> Any:
    for value in values:
        if value is None:
            continue
        if isinstance(value, str):
            if value.strip():
                return value.strip()
            continue
        if value != "":
            return value
    return ""


def _normalize_bool_or_none(value: Any) -> Optional[bool]:
    if isinstance(value, bool):
        return value
    if value is None or value == "":
        return None
    s = str(value).strip().lower()
    if s in ("true", "1", "yes", "on"):
        return True
    if s in ("false", "0", "no", "off"):
        return False
    return None


def _normalize_id_list(value: Any) -> List[str]:
    out: List[str] = []
    seen = set()
    if not isinstance(value, list):
        return out
    for item in value:
        s = _safe_str(item)
        if not s or s in seen:
            continue
        seen.add(s)
        out.append(s)
    return out


def _is_owner_actor(actor_user_id: str, room_owner_user_id: str) -> bool:
    return bool(actor_user_id) and bool(room_owner_user_id) and actor_user_id == room_owner_user_id


def _sanitize_outer_room_mcp_context(request_args: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    req = dict(request_args or {})

    outer_mcp_binding = _safe_dict(req.get("mcp_binding"))
    outer_provider_snapshot = _safe_dict(
        req.get("mcp_provider_snapshot")
        or req.get("provider_snapshot")
        or outer_mcp_binding.get("provider_snapshot")
    )
    outer_imported_provider = _safe_dict(
        req.get("imported_provider")
        or outer_mcp_binding.get("imported_provider")
    )
    outer_provider_origin = _safe_str(
        req.get("_room_mcp_provider_origin")
        or outer_mcp_binding.get("provider_origin")
        or outer_provider_snapshot.get("provider_origin")
        or outer_imported_provider.get("provider_origin")
    ).lower()
    outer_bridge = _safe_str(req.get("_room_mcp_bridge"))
    outer_provider_call = as_bool(req.get("_room_mcp_provider_call"), False)

    should_strip = bool(
        outer_provider_call
        or outer_bridge in ("imported_remote_room_shared_capability", "room_shared_capability")
        or outer_provider_origin == "imported_remote"
    )
    if not should_strip:
        return req

    req["_outer_room_mcp_bridge"] = outer_bridge
    req["_outer_room_mcp_provider_origin"] = outer_provider_origin
    req["_outer_room_mcp_provider_id"] = _safe_str(
        req.get("_room_mcp_provider_id") or outer_mcp_binding.get("provider_id")
    )
    req["_outer_room_mcp_provider_type"] = _safe_str(
        req.get("_room_mcp_provider_type") or outer_mcp_binding.get("provider_type")
    )
    req["_outer_room_mcp_share_ref"] = _safe_str(
        req.get("mcp_share_ref")
        or req.get("share_ref")
        or outer_mcp_binding.get("share_ref")
    )

    if outer_mcp_binding:
        req["_outer_room_mcp_binding"] = dict(outer_mcp_binding)
    if outer_provider_snapshot:
        req["_outer_room_mcp_provider_snapshot"] = dict(outer_provider_snapshot)
    if outer_imported_provider:
        req["_outer_room_mcp_imported_provider"] = dict(outer_imported_provider)

    outer_room_source = _safe_dict(
        outer_mcp_binding.get("room_source")
        or outer_provider_snapshot.get("room_source")
        or outer_imported_provider.get("room_source")
    )
    if outer_room_source:
        req["_outer_room_mcp_room_source"] = dict(outer_room_source)

    outer_boundary_hint = _safe_dict(
        outer_mcp_binding.get("boundary_hint")
        or outer_provider_snapshot.get("boundary_hint")
        or outer_imported_provider.get("boundary_hint")
    )
    if outer_boundary_hint:
        req["_outer_room_mcp_boundary_hint"] = dict(outer_boundary_hint)

    for key in (
        "mcp_binding",
        "mcp_provider_snapshot",
        "provider_snapshot",
        "mcp_share_ref",
        "share_ref",
        "imported_provider",
        "_room_mcp_provider_call",
        "_room_mcp_provider_id",
        "_room_mcp_provider_type",
        "_room_mcp_provider_origin",
        "_room_mcp_bridge",
    ):
        req.pop(key, None)

    return req

def _merge_role_mcp_binding(
    existing_binding: Dict[str, Any],
    role_binding: Dict[str, Any],
) -> Dict[str, Any]:
    existing = _safe_dict(existing_binding)
    role_obj = _safe_dict(role_binding)
    if not role_obj:
        return dict(existing)

    merged = dict(existing)
    merged.update(role_obj)

    merged_params = dict(_safe_dict(role_obj.get("params")))
    merged_params.update(_safe_dict(existing.get("params")))
    if merged_params:
        merged["params"] = merged_params

    provider_snapshot = _safe_dict(
        role_obj.get("provider_snapshot")
        or existing.get("provider_snapshot")
    )
    if provider_snapshot:
        merged["provider_snapshot"] = provider_snapshot

    imported_provider = _safe_dict(
        role_obj.get("imported_provider")
        or existing.get("imported_provider")
    )
    if imported_provider:
        merged["imported_provider"] = imported_provider

    share_ref = _safe_str(
        role_obj.get("share_ref")
        or existing.get("share_ref")
    )
    if share_ref:
        merged["share_ref"] = share_ref

    return merged


def _resolve_room_execution_context(
    request_args: Dict[str, Any],
    role: Dict[str, Any],
    is_supervisor: bool,
) -> Dict[str, Any]:
    req = _safe_dict(request_args)
    role_obj = _safe_dict(role)

    fed_peer_id = _safe_str(
        req.get("_federation_peer_id")
        or req.get("federation_peer_id")
        or req.get("remote_peer_id")
    )
    fed_remote_user_id = _safe_str(
        req.get("_federation_remote_user_id")
        or req.get("federation_remote_user_id")
        or req.get("remote_user_id")
    )

    if fed_peer_id and fed_remote_user_id:
        actor_user_id = f"fed__{fed_peer_id}__{fed_remote_user_id}"
    else:
        actor_user_id = _safe_str(
            req.get("actor_user_id")
            or req.get("uid")
            or req.get("user_id")
            or req.get("sender")
            or req.get("sender_user_id")
        )

    room_owner_user_id = _safe_str(
        req.get("room_owner_user_id")
        or req.get("owner_user_id")
        or req.get("room_owner_id")
    )

    role_id = _safe_str(role_obj.get("role_id") or req.get("role_id"))
    role_owner_user_id = _safe_str(
        role_obj.get("owner_user_id")
        or req.get("role_owner_user_id")
        or req.get("owner_user_id")
    )

    shared_role_ids = _normalize_id_list(
        req.get("shared_role_ids_snapshot")
        if "shared_role_ids_snapshot" in req
        else req.get("shared_role_ids")
    )
    shared_supervisor_enabled = as_bool(
        req.get("shared_supervisor_enabled_snapshot")
        if "shared_supervisor_enabled_snapshot" in req
        else req.get("shared_supervisor_enabled"),
        False,
    )

    role_shared_to_room = bool(role_id) and role_id in shared_role_ids
    supervisor_shared_to_room = bool(shared_supervisor_enabled)

    actor_is_room_owner = _is_owner_actor(actor_user_id, room_owner_user_id)
    actor_is_role_owner = bool(actor_user_id) and bool(role_owner_user_id) and actor_user_id == role_owner_user_id

    role_gate_ready = bool(actor_user_id) and bool(role_obj) and not is_supervisor and bool(role_owner_user_id or shared_role_ids)
    supervisor_gate_ready = bool(actor_user_id) and is_supervisor and bool(
        room_owner_user_id or "shared_supervisor_enabled_snapshot" in req or "shared_supervisor_enabled" in req
    )

    effective_execution_scope = _safe_str(req.get("effective_execution_scope"))
    if not effective_execution_scope:
        if actor_is_room_owner or actor_is_role_owner:
            effective_execution_scope = "owner_private"
        elif role_shared_to_room or supervisor_shared_to_room:
            effective_execution_scope = "room_shared"

    return {
        "actor_user_id": actor_user_id,
        "room_owner_user_id": room_owner_user_id,
        "role_id": role_id,
        "role_owner_user_id": role_owner_user_id,
        "shared_role_ids": shared_role_ids,
        "shared_supervisor_enabled": shared_supervisor_enabled,
        "role_shared_to_room": role_shared_to_room,
        "supervisor_shared_to_room": supervisor_shared_to_room,
        "actor_is_room_owner": actor_is_room_owner,
        "actor_is_role_owner": actor_is_role_owner,
        "role_gate_ready": role_gate_ready,
        "supervisor_gate_ready": supervisor_gate_ready,
        "effective_execution_scope": effective_execution_scope,
    }


def _build_room_execution_denied_packet(
    *,
    room_id: str,
    request_id: str,
    requested_mode: str,
    mcp_overrides: Dict[str, Any],
    question: str,
    reason_code: str,
    actor_user_id: str,
    room_owner_user_id: str,
    role_id: str = "",
    role_owner_user_id: str = "",
    shared_role_ids: Optional[List[str]] = None,
    shared_supervisor_enabled: bool = False,
) -> Dict[str, Any]:
    msg = f"room execution denied: {reason_code}"
    return _ensure_formal_packet(
        conv_id=room_id,
        request_id=request_id,
        rag_mode=requested_mode,
        mcp_overrides=mcp_overrides,
        mode_used=requested_mode,
        response=msg,
        status="error",
        message=msg,
        citations=[],
        rss_evidence=[],
        market_evidence=[],
        evidence_query=_safe_str(question),
        evidence_tools=[],
        evidence_result={**_empty_evidence_result(_safe_str(question)), "error": reason_code},
        tool_calls=[],
        tool_results=[
            {
                "type": "room_execution_denied",
                "reason_code": reason_code,
                "actor_user_id": _safe_str(actor_user_id),
                "room_owner_user_id": _safe_str(room_owner_user_id),
                "actor_is_room_owner": _is_owner_actor(actor_user_id, room_owner_user_id),
                "role_id": _safe_str(role_id),
                "role_owner_user_id": _safe_str(role_owner_user_id),
                "shared_role_ids": list(shared_role_ids or []),
                "shared_supervisor_enabled": bool(shared_supervisor_enabled),
            }
        ],
    )


def _enforce_room_execution_gate(
    *,
    room_id: str,
    request_id: str,
    requested_mode: str,
    mcp_overrides: Dict[str, Any],
    question: str,
    request_args: Dict[str, Any],
    role: Dict[str, Any],
    is_supervisor: bool,
) -> Optional[Dict[str, Any]]:
    ctx = _resolve_room_execution_context(request_args, role, is_supervisor)

    request_args["actor_user_id"] = ctx["actor_user_id"]
    request_args["room_owner_user_id"] = ctx["room_owner_user_id"]
    request_args["role_owner_user_id"] = ctx["role_owner_user_id"]
    request_args["shared_role_ids_snapshot"] = list(ctx["shared_role_ids"])
    request_args["shared_supervisor_enabled_snapshot"] = bool(ctx["shared_supervisor_enabled"])
    request_args["role_shared_to_room"] = bool(ctx["role_shared_to_room"])
    request_args["supervisor_shared_to_room"] = bool(ctx["supervisor_shared_to_room"])
    request_args["is_owner_actor"] = bool(ctx["actor_is_room_owner"])
    request_args["actor_is_room_owner"] = bool(ctx["actor_is_room_owner"])
    request_args["effective_execution_scope"] = _safe_str(ctx["effective_execution_scope"])

    if not role:
        return None

    if is_supervisor:
        if ctx["actor_is_room_owner"]:
            request_args["effective_execution_scope"] = "owner_private"
            return None
        if ctx["supervisor_shared_to_room"]:
            request_args["effective_execution_scope"] = "room_shared"
            return None
        if ctx["supervisor_gate_ready"]:
            return _build_room_execution_denied_packet(
                room_id=room_id,
                request_id=request_id,
                requested_mode=requested_mode,
                mcp_overrides=mcp_overrides,
                question=question,
                reason_code=ROOM_SUPERVISOR_NOT_SHARED,
                actor_user_id=ctx["actor_user_id"],
                room_owner_user_id=ctx["room_owner_user_id"],
                role_id=ctx["role_id"],
                role_owner_user_id=ctx["role_owner_user_id"],
                shared_role_ids=ctx["shared_role_ids"],
                shared_supervisor_enabled=ctx["shared_supervisor_enabled"],
            )
        return None

    if ctx["actor_is_room_owner"] or ctx["actor_is_role_owner"]:
        request_args["effective_execution_scope"] = "owner_private"
        return None
    if ctx["role_shared_to_room"]:
        request_args["effective_execution_scope"] = "room_shared"
        return None
    if ctx["role_gate_ready"]:
        return _build_room_execution_denied_packet(
            room_id=room_id,
            request_id=request_id,
            requested_mode=requested_mode,
            mcp_overrides=mcp_overrides,
            question=question,
            reason_code=ROOM_ROLE_NOT_SHARED,
            actor_user_id=ctx["actor_user_id"],
            room_owner_user_id=ctx["room_owner_user_id"],
            role_id=ctx["role_id"],
            role_owner_user_id=ctx["role_owner_user_id"],
            shared_role_ids=ctx["shared_role_ids"],
            shared_supervisor_enabled=ctx["shared_supervisor_enabled"],
        )

    return None


def _merge_binding_time_fields(binding: Dict[str, Any], request_args: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(binding or {})
    req = _safe_dict(request_args)

    raw_days = _pick_time_value(
        req.get("time_filter_days"),
        req.get("timeFilterDays"),
        out.get("time_filter_days"),
        out.get("timeFilterDays"),
    )
    raw_start = _pick_time_value(
        req.get("time_start"),
        req.get("timeStart"),
        out.get("time_start"),
        out.get("timeStart"),
    )
    raw_end = _pick_time_value(
        req.get("time_end"),
        req.get("timeEnd"),
        out.get("time_end"),
        out.get("timeEnd"),
    )

    time_filter_days = _normalize_positive_int(raw_days)
    time_start = _safe_str(raw_start)
    time_end = _safe_str(raw_end)

    if time_filter_days > 0:
        out["time_filter_days"] = time_filter_days
        out["time_start"] = ""
        out["time_end"] = ""
    else:
        out["time_filter_days"] = ""
        out["time_start"] = time_start
        out["time_end"] = time_end

    return out


def _apply_room_r3_defaults(request_args: Dict[str, Any], binding: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(request_args or {})
    b = _safe_dict(binding)

    time_filter_days = _normalize_positive_int(
        out.get("time_filter_days")
        if out.get("time_filter_days") not in (None, "")
        else b.get("time_filter_days")
    )
    time_start = _safe_str(
        out.get("time_start")
        if out.get("time_start") not in (None, "")
        else b.get("time_start")
    )
    time_end = _safe_str(
        out.get("time_end")
        if out.get("time_end") not in (None, "")
        else b.get("time_end")
    )

    time_enabled = bool(time_filter_days > 0 or time_start or time_end)
    if not time_enabled:
        return out

    dedupe_val = out.get("dedupe_by_doc_id")
    if dedupe_val in (None, ""):
        dedupe_val = out.get("dedupeByDocId")
    dedupe_bool = _normalize_bool_or_none(dedupe_val)
    if dedupe_bool is None:
        out["dedupe_by_doc_id"] = True
        out["dedupeByDocId"] = True

    bucket_mode = _safe_str(
        out.get("time_bucket_mode")
        if out.get("time_bucket_mode") not in (None, "")
        else out.get("timeBucketMode")
    ).lower()
    if bucket_mode not in ("off", "two_phase"):
        bucket_mode = ""
    if not bucket_mode:
        out["time_bucket_mode"] = "two_phase"
        out["timeBucketMode"] = "two_phase"

    return out


def _build_direct_room_reply_packet(
    *,
    room_id: str,
    request_id: str,
    requested_mode: str,
    mcp_overrides: Dict[str, Any],
    question: str,
    model_name: str,
    provider_name: str = "",
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
    role: Optional[Dict[str, Any]] = None,
    success_message: str = "room direct reply",
    result_type: str = "room_direct_model_reply",
    user_prompt_override: str = "",
    evidence_query: str = "",
) -> Dict[str, Any]:
    role_obj = _safe_dict(role)
    role_id = _safe_str(role_obj.get("role_id"))
    role_name = _safe_str(role_obj.get("name") or role_obj.get("slug") or role_id)
    resolved_evidence_query = _safe_str(evidence_query or question)
    resolved_user_prompt = _safe_str(user_prompt_override or question)

    try:
        text, runtime = _call_model_text_with_runtime(
            model_name=model_name,
            provider_name=provider_name,
            user_prompt=resolved_user_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        final_text = _safe_str(text)
        if final_text:
            return _ensure_formal_packet(
                conv_id=room_id,
                request_id=request_id,
                rag_mode=requested_mode,
                mcp_overrides=mcp_overrides,
                mode_used=requested_mode,
                response=final_text,
                status="success",
                message=success_message,
                citations=[],
                rss_evidence=[],
                market_evidence=[],
                evidence_query=resolved_evidence_query,
                evidence_tools=[],
                evidence_result=_empty_evidence_result(resolved_evidence_query),
                tool_calls=[],
                tool_results=[
                    {
                        "type": result_type,
                        "role_id": role_id,
                        "role_name": role_name,
                        "requested_provider": _safe_str(runtime.get("requested_provider")),
                        "requested_model": _safe_str(runtime.get("requested_model")),
                        "applied_provider": _safe_str(runtime.get("applied_provider")),
                        "applied_model": _safe_str(runtime.get("applied_model"), model_name),
                        "fallback_reason": _safe_str(runtime.get("fallback_reason")),
                    }
                ],
            )
    except Exception as ex:
        return _ensure_formal_packet(
            conv_id=room_id,
            request_id=request_id,
            rag_mode=requested_mode,
            mcp_overrides=mcp_overrides,
            mode_used=requested_mode,
            response=f"room direct reply failed: {type(ex).__name__}: {ex}",
            status="error",
            message=f"room direct reply failed: {type(ex).__name__}: {ex}",
            evidence_query=resolved_evidence_query,
            evidence_tools=[],
            evidence_result={**_empty_evidence_result(resolved_evidence_query), "error": f"{type(ex).__name__}: {ex}"},
            tool_calls=[],
            tool_results=[
                {
                    "type": "room_direct_model_error",
                    "role_id": role_id,
                    "role_name": role_name,
                    "error": f"{type(ex).__name__}: {ex}",
                }
            ],
        )

    return _ensure_formal_packet(
        conv_id=room_id,
        request_id=request_id,
        rag_mode=requested_mode,
        mcp_overrides=mcp_overrides,
        mode_used=requested_mode,
        response="",
        status="error",
        message="room direct reply returned empty content",
        evidence_query=resolved_evidence_query,
        evidence_tools=[],
        evidence_result={**_empty_evidence_result(resolved_evidence_query), "error": "empty_content"},
        tool_calls=[],
        tool_results=[
            {
                "type": "room_direct_model_error",
                "role_id": role_id,
                "role_name": role_name,
                "error": "empty_content",
            }
        ],
    )

def _resolve_provider_safe_worker_question(
    *,
    question: str,
    worker_memory_context: Dict[str, Any],
    role: Dict[str, Any],
    model_name: str,
) -> Dict[str, Any]:
    return resolve_provider_safe_worker_question(
        question=question,
        worker_memory_context=worker_memory_context,
        max_chars=160,
    )


def _call_room_mcp_provider(
    *,
    room_id: str,
    request_id: str,
    question: str,
    requested_mode: str,
    mcp_overrides: Dict[str, Any],
    request_args: Dict[str, Any],
    role: Dict[str, Any],
) -> Dict[str, Any]:
    return dispatch_room_mcp_provider(
        room_id=room_id,
        request_id=request_id,
        question=question,
        requested_mode=requested_mode,
        mcp_overrides=mcp_overrides,
        request_args=request_args,
        role=role,
    )


def _compose_worker_memory_prompt(question: str, worker_memory_context: Dict[str, Any]) -> str:
    context_text = _safe_str(_safe_dict(worker_memory_context).get("context_text"))
    base_question = _safe_str(question)
    if not context_text:
        return base_question
    return f"{context_text}\n\nCurrent worker task:\n{base_question}".strip()


def _append_worker_memory_runtime_fact(
    packet: Dict[str, Any],
    worker_memory_context: Dict[str, Any],
    *,
    text_injected: bool,
    context_used: Optional[bool] = None,
    provider_question_resolved: bool = False,
    provider_question: str = "",
    provider_question_reason: str = "",
    rag_question_resolved: bool = False,
    rag_question: str = "",
    rag_question_reason: str = "",
    original_question: str = "",
) -> Dict[str, Any]:
    return append_worker_memory_runtime_fact(
        packet,
        worker_memory_context,
        text_injected=text_injected,
        context_used=context_used,
        provider_question_resolved=provider_question_resolved,
        provider_question=provider_question,
        provider_question_reason=provider_question_reason,
        rag_question_resolved=rag_question_resolved,
        rag_question=rag_question,
        rag_question_reason=rag_question_reason,
        original_question=original_question,
    )


def _execute_room_worker_packet(
    *,
    room_id: str,
    question: str,
    model_name: str,
    request_args: Optional[Dict[str, Any]] = None,
    role: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    local_request_args = _sanitize_outer_room_mcp_context(request_args)
    role_obj = _safe_dict(role)

    if role_obj:
        local_request_args.setdefault("role_id", _safe_str(role_obj.get("role_id")))
        local_request_args.setdefault("role_name", _safe_str(role_obj.get("name") or role_obj.get("slug")))
        local_request_args.setdefault("role_slug", _safe_str(role_obj.get("slug")))
        local_request_args.setdefault("role_tools", _safe_list(role_obj.get("tools")))
        local_request_args.setdefault(
            "role_binding",
            _safe_dict(role_obj.get("binding") or role_obj.get("bindings") or role_obj.get("knowledge_binding")),
        )

        role_mcp_binding = _safe_dict(role_obj.get("mcp_binding"))
        role_mcp_provider_snapshot = _safe_dict(
            role_obj.get("mcp_provider_snapshot")
            or role_mcp_binding.get("provider_snapshot")
        )
        role_mcp_share_ref = _safe_str(
            role_obj.get("mcp_share_ref")
            or role_mcp_binding.get("share_ref")
        )
        role_imported_provider = _safe_dict(
            role_obj.get("imported_provider")
            or role_mcp_binding.get("imported_provider")
        )

        if role_mcp_binding:
            existing_mcp_binding = _safe_dict(local_request_args.get("mcp_binding"))
            local_request_args["mcp_binding"] = _merge_role_mcp_binding(
                existing_binding=existing_mcp_binding,
                role_binding=role_mcp_binding,
            )

        if role_mcp_provider_snapshot:
            local_request_args["mcp_provider_snapshot"] = role_mcp_provider_snapshot
            local_request_args["provider_snapshot"] = role_mcp_provider_snapshot

            mcp_binding_obj = _safe_dict(local_request_args.get("mcp_binding"))
            if mcp_binding_obj:
                mcp_binding_obj["provider_snapshot"] = role_mcp_provider_snapshot
                local_request_args["mcp_binding"] = mcp_binding_obj

        if role_mcp_share_ref:
            local_request_args["mcp_share_ref"] = role_mcp_share_ref
            local_request_args["share_ref"] = role_mcp_share_ref

            mcp_binding_obj = _safe_dict(local_request_args.get("mcp_binding"))
            if mcp_binding_obj:
                mcp_binding_obj["share_ref"] = role_mcp_share_ref
                local_request_args["mcp_binding"] = mcp_binding_obj

        if role_imported_provider:
            local_request_args["imported_provider"] = role_imported_provider

            mcp_binding_obj = _safe_dict(local_request_args.get("mcp_binding"))
            if mcp_binding_obj and not _safe_dict(mcp_binding_obj.get("imported_provider")):
                mcp_binding_obj["imported_provider"] = role_imported_provider
                local_request_args["mcp_binding"] = mcp_binding_obj

        provider_origin = _safe_str(
            role_obj.get("provider_origin")
            or role_mcp_binding.get("provider_origin")
            or role_mcp_provider_snapshot.get("provider_origin")
            or role_imported_provider.get("provider_origin")
        )
        if provider_origin:
            mcp_binding_obj = _safe_dict(local_request_args.get("mcp_binding"))
            if mcp_binding_obj:
                mcp_binding_obj["provider_origin"] = provider_origin
                local_request_args["mcp_binding"] = mcp_binding_obj

    state = _load_room_state(room_id)
    mcp_overrides = _safe_dict(local_request_args.get("mcp_overrides")) or _safe_dict(state.get("mcp_overrides"))
    requested_mode = _normalize_room_mode(
        local_request_args.get("requested_mode")
        or local_request_args.get("rag_mode")
        or local_request_args.get("mode_used")
        or mcp_overrides.get("rag_mode")
        or "off"
    )
    request_id = _safe_str(local_request_args.get("request_id"))
    raw_question = _safe_str(question)
    user_question = _extract_user_question(raw_question, local_request_args)
    base_worker_question = _safe_str(user_question or raw_question)

    if not raw_question:
        return _ensure_formal_packet(
            conv_id=room_id,
            request_id=request_id,
            rag_mode=requested_mode,
            mcp_overrides=mcp_overrides,
            mode_used=requested_mode,
            response="",
            status="error",
            message="room worker question is empty",
            evidence_query="",
            evidence_tools=[],
            evidence_result={**_empty_evidence_result(""), "error": "empty_question"},
            tool_calls=[],
            tool_results=[{"type": "room_worker_error", "reason": "empty_question"}],
        )

    role_id = _safe_str(role_obj.get("role_id"))
    role_name = _safe_str(role_obj.get("name") or role_obj.get("slug") or role_id)
    is_supervisor = role_id == "supervisor" or role_name.lower() == "supervisor"

    deny_packet = _enforce_room_execution_gate(
        room_id=room_id,
        request_id=request_id,
        requested_mode=requested_mode,
        mcp_overrides=mcp_overrides,
        question=base_worker_question,
        request_args=local_request_args,
        role=role_obj,
        is_supervisor=is_supervisor,
    )
    if deny_packet:
        return deny_packet

    worker_memory_context: Dict[str, Any] = resolve_worker_supervisor_memory_context(
        room_id=room_id,
        question=base_worker_question,
        mcp_overrides=mcp_overrides,
        role=role_obj,
        is_supervisor=is_supervisor,
    )
    if worker_memory_context:
        local_request_args = stamp_worker_memory_request_args(
            local_request_args,
            worker_memory_context,
        )

    binding = _resolve_effective_binding(role_obj, state, local_request_args) if role_obj else {}
    binding = _merge_binding_time_fields(binding, local_request_args) if role_obj else {}

    if role_obj:
        local_request_args["time_filter_days"] = binding.get("time_filter_days") or ""
        local_request_args["time_start"] = binding.get("time_start") or ""
        local_request_args["time_end"] = binding.get("time_end") or ""
        local_request_args["binding"] = binding
        local_request_args["role_binding"] = binding
        local_request_args["knowledge_binding"] = binding
        local_request_args = _apply_room_r3_defaults(local_request_args, binding)

    binding_ready = _binding_has_target(binding)
    role_tool_policy = _safe_dict(local_request_args.get("role_tool_policy")) or _safe_dict(_role_tool_policy(role_obj))
    rag_enabled = as_bool(role_tool_policy.get("rag"), True) if role_obj else False
    web_requested = requested_mode == "web" or as_bool(role_tool_policy.get("web"), False)
    mcp_binding = _safe_dict(local_request_args.get("mcp_binding"))
    mcp_requested = as_bool(role_tool_policy.get("mcp"), False) and as_bool(mcp_binding.get("enabled"), False)
    effective_role_rag_mode = requested_mode if requested_mode in {"cite", "ground"} else "cite"

    if is_supervisor:
        rt_request = _supervisor_runtime_request(state, model_name)
        is_direct_answer = as_bool(local_request_args.get("_supervisor_direct_answer"), False)

        if is_direct_answer:
            effective_question = _build_effective_room_question(
                question=raw_question,
                request_args=local_request_args,
                include_direct_prompt=True,
            )
        else:
            effective_question = raw_question

        return _build_direct_room_reply_packet(
            room_id=room_id,
            request_id=request_id,
            requested_mode=requested_mode,
            mcp_overrides=mcp_overrides,
            question=base_worker_question,
            model_name=_safe_str(rt_request.get("model_name"), model_name) or model_name,
            provider_name=_safe_str(rt_request.get("provider_name")).lower(),
            temperature=rt_request.get("temperature"),
            max_tokens=rt_request.get("max_tokens"),
            role=role_obj,
            success_message="room supervisor direct reply",
            result_type="room_supervisor_direct_model",
            user_prompt_override=effective_question,
            evidence_query=base_worker_question,
        )

    if role_obj and not is_supervisor and mcp_requested:
        provider_question_resolution = _resolve_provider_safe_worker_question(
            question=base_worker_question,
            worker_memory_context=worker_memory_context,
            role=role_obj,
            model_name=model_name,
        )
        provider_question = _safe_str(provider_question_resolution.get("question")) or base_worker_question

        local_request_args["worker_memory_provider_question_resolved"] = bool(provider_question_resolution.get("resolved"))
        local_request_args["worker_memory_provider_question"] = provider_question
        local_request_args["worker_memory_provider_question_reason"] = _safe_str(provider_question_resolution.get("reason"))

        provider_packet = _call_room_mcp_provider(
            room_id=room_id,
            request_id=request_id,
            question=provider_question,
            requested_mode=requested_mode,
            mcp_overrides=mcp_overrides,
            request_args=local_request_args,
            role=role_obj,
        )
        return _append_worker_memory_runtime_fact(
            provider_packet,
            worker_memory_context,
            text_injected=False,
            context_used=bool(provider_question_resolution.get("resolved")),
            provider_question_resolved=bool(provider_question_resolution.get("resolved")),
            provider_question=provider_question,
            provider_question_reason=_safe_str(provider_question_resolution.get("reason")),
            original_question=base_worker_question,
        )

    if role_obj and not is_supervisor and not web_requested and rag_enabled and binding_ready:
        rag_task_resolution = resolve_rag_safe_worker_question(
            question=base_worker_question,
            worker_memory_context=worker_memory_context,
            max_chars=220,
        )
        rag_question = _safe_str(rag_task_resolution.get("question")) or base_worker_question

        local_request_args["worker_memory_rag_task_resolved"] = bool(rag_task_resolution.get("resolved"))
        local_request_args["worker_memory_rag_task"] = rag_question
        local_request_args["worker_memory_rag_task_reason"] = _safe_str(rag_task_resolution.get("reason"))
        local_request_args["worker_memory_context_used"] = bool(
            worker_memory_context.get("used") and rag_task_resolution.get("resolved")
        )

        try:
            qascope_packet = call_room_rag_qascope_packet(
                room_id=room_id,
                request_id=request_id,
                rag_mode=effective_role_rag_mode,
                mcp_overrides=mcp_overrides,
                base_args=local_request_args,
                question=rag_question,
                binding=binding,
                model_name=model_name,
            )
            if _safe_str(qascope_packet.get("content") or qascope_packet.get("response")):
                return _append_worker_memory_runtime_fact(
                    qascope_packet,
                    worker_memory_context,
                    text_injected=False,
                    context_used=bool(rag_task_resolution.get("resolved")),
                    rag_question_resolved=bool(rag_task_resolution.get("resolved")),
                    rag_question=rag_question,
                    rag_question_reason=_safe_str(rag_task_resolution.get("reason")),
                    original_question=base_worker_question,
                )
        except Exception as ex:
            local_request_args["worker_memory_rag_error"] = f"{type(ex).__name__}: {ex}"

    try:
        from tools.chat.chat_orchestrator import nisb_chat_orchestrate

        should_inject_worker_memory_into_chat = bool(
            worker_memory_context.get("used")
            and role_obj
            and not is_supervisor
            and not web_requested
            and not mcp_requested
            and not (rag_enabled and binding_ready)
            and requested_mode not in {"cite", "ground", "web"}
        )
        chat_question = (
            _compose_worker_memory_prompt(raw_question, worker_memory_context)
            if should_inject_worker_memory_into_chat
            else raw_question
        )

        chat_args = _build_orchestrate_args(
            room_id=room_id,
            question=chat_question,
            model_name=model_name,
            request_args=local_request_args,
            role=role_obj,
        )

        chat_args["time_filter_days"] = local_request_args.get("time_filter_days") or binding.get("time_filter_days") or ""
        chat_args["time_start"] = local_request_args.get("time_start") or binding.get("time_start") or ""
        chat_args["time_end"] = local_request_args.get("time_end") or binding.get("time_end") or ""
        chat_args["dedupe_by_doc_id"] = local_request_args.get("dedupe_by_doc_id")
        chat_args["dedupeByDocId"] = local_request_args.get("dedupeByDocId")
        chat_args["time_bucket_mode"] = local_request_args.get("time_bucket_mode") or ""
        chat_args["timeBucketMode"] = local_request_args.get("timeBucketMode") or ""

        kb_for_chat = _safe_dict(chat_args.get("knowledge_binding"))
        if kb_for_chat:
            kb_for_chat["time_filter_days"] = chat_args["time_filter_days"]
            kb_for_chat["time_start"] = chat_args["time_start"]
            kb_for_chat["time_end"] = chat_args["time_end"]
            chat_args["knowledge_binding"] = kb_for_chat

        binding_for_chat = _safe_dict(chat_args.get("binding"))
        if binding_for_chat:
            binding_for_chat["time_filter_days"] = chat_args["time_filter_days"]
            binding_for_chat["time_start"] = chat_args["time_start"]
            binding_for_chat["time_end"] = chat_args["time_end"]
            chat_args["binding"] = binding_for_chat

        chat_args["_room_origin"] = True
        chat_args["_room_id"] = room_id
        chat_args["_room_no_conversation_persist"] = True
        chat_args["_room_history_visibility"] = "hidden"
        chat_args["worker_memory_context_available"] = bool(worker_memory_context.get("used"))
        chat_args["worker_memory_context_used"] = bool(should_inject_worker_memory_into_chat)
        chat_args["worker_memory_decision"] = _safe_str(worker_memory_context.get("decision"), "none")
        chat_args["worker_memory_reason"] = _safe_str(worker_memory_context.get("reason"))
        chat_args["worker_memory_resume_confidence"] = worker_memory_context.get("resume_confidence")
        chat_args["worker_memory_resume_relation"] = _safe_str(worker_memory_context.get("resume_relation"))
        chat_args["worker_memory_resume_context_dependent"] = bool(worker_memory_context.get("resume_context_dependent"))

        chat_res = nisb_chat_orchestrate(chat_args)
        chat_packet = _bridge_chat_result(
            room_id=room_id,
            question=base_worker_question,
            request_id=request_id,
            fallback_mode=requested_mode,
            mcp_overrides=mcp_overrides,
            chat_res=chat_res,
        )
        return _append_worker_memory_runtime_fact(
            chat_packet,
            worker_memory_context,
            text_injected=should_inject_worker_memory_into_chat,
        )
    except Exception as ex:
        if role_obj and not is_supervisor:
            try:
                fallback_question = _build_effective_room_question(
                    question=base_worker_question,
                    request_args=local_request_args,
                    include_direct_prompt=False,
                )
                should_inject_worker_memory_into_fallback = bool(worker_memory_context.get("used"))
                if should_inject_worker_memory_into_fallback:
                    fallback_question = _compose_worker_memory_prompt(
                        fallback_question,
                        worker_memory_context,
                    )

                role_reply = _call_role_reply_with_runtime(
                    room_id=room_id,
                    question=fallback_question,
                    role=role_obj,
                    model_name=model_name,
                )
                role_text = _safe_str(role_reply.get("content"))
                runtime = _safe_dict(role_reply.get("runtime"))
                if role_text:
                    fallback_mode = requested_mode if (not binding_ready and not web_requested) else "off"
                    fallback_packet = _ensure_formal_packet(
                        conv_id=room_id,
                        request_id=request_id,
                        rag_mode=fallback_mode,
                        mcp_overrides=mcp_overrides,
                        mode_used=fallback_mode,
                        response=role_text,
                        status="success",
                        message="room worker fallback role reply",
                        citations=[],
                        rss_evidence=[],
                        market_evidence=[],
                        evidence_query=base_worker_question,
                        evidence_tools=[],
                        evidence_result=_empty_evidence_result(base_worker_question),
                        tool_calls=[],
                        tool_results=[
                            {
                                "type": "room_runtime_fallback",
                                "requested_provider": _safe_str(runtime.get("requested_provider")),
                                "requested_model": _safe_str(runtime.get("requested_model")),
                                "applied_provider": _safe_str(runtime.get("applied_provider")),
                                "applied_model": _safe_str(runtime.get("applied_model"), model_name),
                                "fallback_reason": _safe_str(runtime.get("fallback_reason")),
                                "source_error": f"{type(ex).__name__}: {ex}",
                            }
                        ],
                    )
                    return _append_worker_memory_runtime_fact(
                        fallback_packet,
                        worker_memory_context,
                        text_injected=should_inject_worker_memory_into_fallback,
                    )
            except Exception:
                pass

        error_packet = _ensure_formal_packet(
            conv_id=room_id,
            request_id=request_id,
            rag_mode=requested_mode,
            mcp_overrides=mcp_overrides,
            mode_used=requested_mode,
            response=f"room worker reply failed: {type(ex).__name__}: {ex}",
            status="error",
            message=f"room worker reply failed: {type(ex).__name__}: {ex}",
            evidence_query=base_worker_question,
            evidence_tools=["nisb_chat_orchestrate"],
            evidence_result={**_empty_evidence_result(base_worker_question), "error": f"{type(ex).__name__}: {ex}"},
            tool_calls=[],
            tool_results=[
                {
                    "type": "room_worker_error",
                    "bridge": "nisb_chat_orchestrate",
                    "error": f"{type(ex).__name__}: {ex}",
                }
            ],
        )
        return _append_worker_memory_runtime_fact(
            error_packet,
            worker_memory_context,
            text_injected=False,
        )


def _execute_room_worker_text(
    *,
    room_id: str,
    question: str,
    model_name: str,
    request_args: Optional[Dict[str, Any]] = None,
    role: Optional[Dict[str, Any]] = None,
) -> str:
    packet = _execute_room_worker_packet(
        room_id=room_id,
        question=question,
        model_name=model_name,
        request_args=request_args,
        role=role,
    )
    return _safe_str(packet.get("response") or packet.get("message"))


__all__ = [
    "_build_direct_room_reply_packet",
    "_call_role_reply",
    "_call_role_reply_with_runtime",
    "_call_room_mcp_provider",
    "_call_room_plain_reply",
    "_execute_room_worker_packet",
    "_execute_room_worker_text",
]

