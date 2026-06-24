from __future__ import annotations

from typing import Any, Dict, List, Optional

from .room_contracts import as_bool, new_id, utc_iso
from .room_helpers import (
    _append_aborted_event,
    _call_room_ai_reply_packet,
    _update_room_last_message,
)
from .room_orchestrator import (
    _generate_role_reply_packet,
    _run_sequential_orchestration,
    _run_supervisor_orchestration,
)
from .room_runtime_reader import _same_event
from .room_runtime_result_view import (
    _rt_finalize_passthrough_packet,
    _rt_post_aborted_result,
    _rt_post_manual_result,
    _rt_post_passthrough,
    _rt_post_skip_result,
)
from .room_state_normalizer import (
    _safe_dict,
    _safe_list,
    _safe_str,
)
from .room_store import (
    append_room_event,
    load_state_doc,
    touch_room_updated_at,
)
from .room_supervisor_runtime import _run_supervisor_direct_answer
from .room_tool_common import (
    _build_tool_result_item,
    _payload_of_event,
    _post_meta_from_event,
    _post_ok,
    _post_response_from_event,
)
from .room_packet_builder import (
    _build_room_message_payload,
    _empty_evidence_result,
)
from .room_tools_runtime_control import (
    _finalize_runtime_dispatch,
    _find_last_generated_message_event,
    _mark_runtime_run_failed,
    _start_room_runtime_run,
)
from .room_tools_runtime_current import (
    _build_running_runtime_result,
    _get_runtime_control_snapshot,
)
from .room_mcp_runtime_context import (
    _rt_apply_mcp_binding_question_aliases,
    _rt_apply_question_aliases,
    _rt_build_runtime_skip_result,
    _rt_role_allowed_for_actor,
    _rt_safe_bool,
    _rt_safe_dict,
    _rt_safe_list,
    _rt_safe_str,
    _rt_supervisor_allowed_for_actor,
)


def _rt_extract_result_envelope(
    *,
    source_packet: Optional[Dict[str, Any]] = None,
    source_event: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    out: Dict[str, Any] = {}

    def _merge_source(raw: Dict[str, Any]) -> None:
        if not raw:
            return
        result_doc = _rt_safe_dict(raw.get("result"))
        source = {
            **raw,
            **result_doc,
        }
        if _rt_safe_str(source.get("result_state")):
            out["result_state"] = _rt_safe_str(source.get("result_state"))
        elif _rt_safe_str(source.get("status")):
            out["result_state"] = _rt_safe_str(source.get("status"))

        if _rt_safe_str(source.get("result_view")):
            out["result_view"] = _rt_safe_str(source.get("result_view"))
        if _rt_safe_str(source.get("final_response")):
            out["final_response"] = _rt_safe_str(source.get("final_response"))
        elif _rt_safe_str(source.get("response")):
            out["final_response"] = _rt_safe_str(source.get("response"))

        if _rt_safe_dict(source.get("provider_trace")):
            out["provider_trace"] = _rt_safe_dict(source.get("provider_trace"))
        if _rt_safe_dict(source.get("grant_trace")):
            out["grant_trace"] = _rt_safe_dict(source.get("grant_trace"))
        if _rt_safe_dict(source.get("network_trace")):
            out["network_trace"] = _rt_safe_dict(source.get("network_trace"))
        if _rt_safe_dict(source.get("consume_trace")):
            out["consume_trace"] = _rt_safe_dict(source.get("consume_trace"))
        if _rt_safe_dict(source.get("runtime_control_snapshot")):
            out["runtime_control_snapshot"] = _rt_safe_dict(source.get("runtime_control_snapshot"))

        if "replay_recoverable" in source:
            out["replay_recoverable"] = as_bool(source.get("replay_recoverable"), False)
        if "remote_execution_may_have_completed" in source:
            out["remote_execution_may_have_completed"] = as_bool(
                source.get("remote_execution_may_have_completed"),
                False,
            )

    _merge_source(_rt_safe_dict(source_packet))
    if source_event:
        _merge_source(_rt_safe_dict(_payload_of_event(source_event)))

    return out


def _rt_finalize_execution_packet(
    *,
    packet: Dict[str, Any],
    response: str,
    result_state: str = "success",
    result_view: str = "full_result",
    source_packet: Optional[Dict[str, Any]] = None,
    source_event: Optional[Dict[str, Any]] = None,
    runtime_control_snapshot: Optional[Dict[str, Any]] = None,
    consume_trace: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    envelope = _rt_extract_result_envelope(
        source_packet=source_packet,
        source_event=source_event,
    )

    resolved_runtime_snapshot = _rt_safe_dict(runtime_control_snapshot) or _rt_safe_dict(
        envelope.get("runtime_control_snapshot")
    )

    return _rt_finalize_passthrough_packet(
        packet=packet,
        response=_rt_safe_str(envelope.get("final_response")) or _rt_safe_str(response),
        result_state=_rt_safe_str(envelope.get("result_state")) or _rt_safe_str(result_state) or "success",
        result_view=_rt_safe_str(envelope.get("result_view")) or _rt_safe_str(result_view) or "full_result",
        consume_trace=_rt_safe_dict(consume_trace) or _rt_safe_dict(envelope.get("consume_trace")),
        provider_trace=_rt_safe_dict(envelope.get("provider_trace")),
        grant_trace=_rt_safe_dict(envelope.get("grant_trace")),
        network_trace=_rt_safe_dict(envelope.get("network_trace")),
        runtime_control_snapshot=resolved_runtime_snapshot,
        replay_recoverable=as_bool(envelope.get("replay_recoverable"), False),
        remote_execution_may_have_completed=as_bool(
            envelope.get("remote_execution_may_have_completed"),
            False,
        ),
    )


def _rt_handle_ai_mention_execution(
    *,
    rid: str,
    room_id: str,
    rag_mode: str,
    mcp_overrides: Dict[str, Any],
    mode_used: str,
    model_name: str,
    txt: str,
    content: str,
    evt: Dict[str, Any],
    request_args: Dict[str, Any],
    base_tool_results: List[Any],
) -> Optional[Dict[str, Any]]:
    if not txt.lower().startswith("@ai"):
        return None

    question = txt[3:].strip() or "请继续"
    try:
        ai_packet = _call_room_ai_reply_packet(
            room_id=room_id,
            question=question,
            model_name=model_name,
            request_args=request_args,
            role={"role_id": "ai", "name": "AI", "slug": "ai"},
        )
        ai_text = _safe_str(ai_packet.get("content") or ai_packet.get("response"))
        if ai_text:
            generated = {
                "id": new_id("evt"),
                "ts": utc_iso(),
                "type": "room.message",
                "room_id": room_id,
                "request_id": rid,
                "trigger_event_id": evt["id"],
                "payload": _build_room_message_payload(
                    sender="ai",
                    sender_type="ai",
                    content=ai_text,
                    model=_safe_str(ai_packet.get("model") or model_name, model_name),
                    mode_used=_safe_str(ai_packet.get("mode_used") or mode_used, mode_used),
                    citations=ai_packet.get("citations"),
                    rss_evidence=ai_packet.get("rss_evidence"),
                    market_evidence=ai_packet.get("market_evidence"),
                    evidence_query=_safe_str(ai_packet.get("evidence_query") or question, question),
                    evidence_tools=ai_packet.get("evidence_tools"),
                    evidence_result=ai_packet.get("evidence_result"),
                    tool_calls=ai_packet.get("tool_calls"),
                    tool_results=ai_packet.get("tool_results"),
                ),
            }
            append_room_event(room_id, generated)
            touch_room_updated_at(room_id)
            _update_room_last_message(room_id, generated["id"])

            meta_info = _post_meta_from_event(generated, mode_used, question)
            packet = _post_ok(
                rid=rid,
                room_id=room_id,
                rag_mode=rag_mode,
                mcp_overrides=mcp_overrides,
                response=_post_response_from_event(generated, ai_text),
                message="room post processed",
                mode_used=meta_info["mode_used"],
                citations=meta_info["citations"],
                rss_evidence=meta_info["rss_evidence"],
                market_evidence=meta_info["market_evidence"],
                evidence_query=meta_info["evidence_query"],
                evidence_tools=meta_info["evidence_tools"],
                evidence_result=meta_info["evidence_result"],
                tool_results=list(base_tool_results) + [
                    _build_tool_result_item("generated_event", event=generated),
                ],
            )
            return _rt_finalize_execution_packet(
                packet=packet,
                response=_post_response_from_event(generated, ai_text),
                result_state="success",
                result_view="full_result",
                source_packet=_safe_dict(ai_packet),
                source_event=generated,
            )
    except Exception as ex:
        aborted = _append_aborted_event(
            room_id=room_id,
            request_id=rid,
            trigger_event_id=evt["id"],
            sender="ai",
            reason=f"exception:{type(ex).__name__}",
        )
        return _rt_post_aborted_result(
            rid=rid,
            room_id=room_id,
            rag_mode=rag_mode,
            mcp_overrides=mcp_overrides,
            mode_used=mode_used,
            content=content,
            message="room post accepted, ai reply aborted",
            base_tool_results=base_tool_results,
            aborted_event=aborted,
        )

    return None


def _rt_handle_provider_bridge_skip(
    *,
    rid: str,
    room_id: str,
    rag_mode: str,
    mcp_overrides: Dict[str, Any],
    mode_used: str,
    content: str,
    provider_bridge_call: bool,
    shared_auto_enabled: bool,
    runtime_ctx: Dict[str, Any],
    role: Optional[Dict[str, Any]],
    active_role_objs: List[Any],
    base_tool_results: List[Any],
    room_shared_auto_reply_disabled_reason: str,
) -> Optional[Dict[str, Any]]:
    if not provider_bridge_call or shared_auto_enabled:
        return None

    return _rt_post_skip_result(
        rid=rid,
        room_id=room_id,
        rag_mode=rag_mode,
        mcp_overrides=mcp_overrides,
        mode_used=mode_used,
        content=content,
        base_tool_results=base_tool_results,
        skip_result=_rt_build_runtime_skip_result(
            reason_code=room_shared_auto_reply_disabled_reason,
            path="provider_call",
            ctx=runtime_ctx,
            role_obj=role,
            active_role_objs=_rt_safe_list(active_role_objs),
        ),
    )


def _rt_handle_shared_auto_disabled_gate(
    *,
    rid: str,
    room_id: str,
    rag_mode: str,
    mcp_overrides: Dict[str, Any],
    mode_used: str,
    content: str,
    shared_auto_enabled: bool,
    role: Optional[Dict[str, Any]],
    route_mode: str,
    reply_mode: str,
    runtime_ctx: Dict[str, Any],
    active_role_objs: List[Any],
    base_tool_results: List[Any],
    room_shared_auto_reply_disabled_reason: str,
) -> Optional[Dict[str, Any]]:
    if shared_auto_enabled:
        return None

    should_skip_shared_auto = False
    skip_path = ""

    if role:
        should_skip_shared_auto = True
        skip_path = route_mode
    elif reply_mode == "supervisor_direct":
        should_skip_shared_auto = True
        skip_path = "supervisor_direct"
    elif active_role_objs and reply_mode != "manual":
        should_skip_shared_auto = True
        skip_path = "orchestration"

    if not should_skip_shared_auto:
        return None

    return _rt_post_skip_result(
        rid=rid,
        room_id=room_id,
        rag_mode=rag_mode,
        mcp_overrides=mcp_overrides,
        mode_used=mode_used,
        content=content,
        base_tool_results=base_tool_results,
        skip_result=_rt_build_runtime_skip_result(
            reason_code=room_shared_auto_reply_disabled_reason,
            path=skip_path or "shared_auto_reply_gate",
            ctx=runtime_ctx,
            role_obj=role,
            active_role_objs=_rt_safe_list(active_role_objs),
        ),
    )


def _rt_has_provider_boundary_tool_results(tool_results: List[Any]) -> bool:
    for item in _rt_safe_list(tool_results):
        row = _rt_safe_dict(item)
        item_type = _rt_safe_str(row.get("type"))
        if item_type in {
            "room_mcp_final_result_view",
            "room_mcp_provider_deny",
            "room_mcp_provider_error",
        }:
            return True
    return False


def _rt_passthrough_runtime_packet(
    *,
    packet: Dict[str, Any],
    rid: str,
    room_id: str,
    rag_mode: str,
    mcp_overrides: Dict[str, Any],
    mode_used: str,
    fallback_query: str,
    fallback_response: str,
    base_tool_results: List[Any],
    extra_tool_results: List[Any],
    runtime_control_snapshot: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    out = dict(_rt_safe_dict(packet))
    existing_tool_results = _rt_safe_list(out.get("tool_results"))

    out["conv_id"] = _rt_safe_str(out.get("conv_id"), room_id) or room_id
    out["request_id"] = _rt_safe_str(out.get("request_id"), rid) or rid
    out["rag_mode"] = _rt_safe_str(out.get("rag_mode"), rag_mode) or rag_mode
    out["mcp_overrides"] = _rt_safe_dict(out.get("mcp_overrides")) or _rt_safe_dict(mcp_overrides)
    out["mode_used"] = _rt_safe_str(out.get("mode_used"), mode_used) or mode_used

    evidence_query = _rt_safe_str(out.get("evidence_query"), fallback_query) or fallback_query
    out["evidence_query"] = evidence_query
    out["evidence_result"] = _rt_safe_dict(out.get("evidence_result")) or _empty_evidence_result(evidence_query)

    out["response"] = _rt_safe_str(out.get("response") or out.get("message"), fallback_response) or fallback_response
    out["message"] = _rt_safe_str(out.get("message"), out["response"]) or out["response"]

    out["tool_calls"] = _rt_safe_list(out.get("tool_calls"))
    out["tool_results"] = list(base_tool_results) + list(extra_tool_results) + existing_tool_results

    if runtime_control_snapshot:
        out["runtime_control_snapshot"] = _rt_safe_dict(runtime_control_snapshot)

    return _rt_finalize_passthrough_packet(
        packet=out,
        response=out["response"],
        result_state=_rt_safe_str(out.get("result_state") or out.get("status") or "error"),
        result_view=_rt_safe_str(out.get("result_view") or "full_result"),
        runtime_control_snapshot=_rt_safe_dict(runtime_control_snapshot),
        replay_recoverable=as_bool(out.get("replay_recoverable"), False),
        remote_execution_may_have_completed=as_bool(
            out.get("remote_execution_may_have_completed"),
            False,
        ),
    )


def _rt_handle_role_execution(
    *,
    rid: str,
    room_id: str,
    rag_mode: str,
    mcp_overrides: Dict[str, Any],
    mode_used: str,
    model_name: str,
    content: str,
    evt: Dict[str, Any],
    role: Optional[Dict[str, Any]],
    question: str,
    route_mode: str,
    reply_mode: str,
    runtime_ctx: Dict[str, Any],
    request_args: Dict[str, Any],
    base_tool_results: List[Any],
    room_role_not_shared_reason: str,
) -> Optional[Dict[str, Any]]:
    if not role:
        return None

    if not _rt_role_allowed_for_actor(role, runtime_ctx):
        return _rt_post_skip_result(
            rid=rid,
            room_id=room_id,
            rag_mode=rag_mode,
            mcp_overrides=mcp_overrides,
            mode_used=mode_used,
            content=content,
            base_tool_results=base_tool_results,
            skip_result=_rt_build_runtime_skip_result(
                reason_code=room_role_not_shared_reason,
                path=route_mode,
                ctx=runtime_ctx,
                role_obj=role,
            ),
        )

    route_evt = {
        "id": new_id("evt"),
        "ts": utc_iso(),
        "type": "room.route",
        "room_id": room_id,
        "request_id": rid,
        "trigger_event_id": evt["id"],
        "payload": {
            "source_event_id": evt["id"],
            "route_mode": route_mode,
            "reply_mode": reply_mode,
            "target_role_id": str(role.get("role_id") or ""),
            "target_role_name": str(role.get("name") or ""),
        },
    }
    append_room_event(room_id, route_evt)

    try:
        reply_packet = _generate_role_reply_packet(
            room_id=room_id,
            question=question,
            role=role,
            model_name=model_name,
            request_args=request_args,
        )

        reply_status = _safe_str(reply_packet.get("status")).lower()
        reply_message = _safe_str(reply_packet.get("message"))
        role_text = _safe_str(reply_packet.get("content") or reply_packet.get("response")).strip()
        reply_tool_results = _rt_safe_list(reply_packet.get("tool_results"))

        final_view_status = ""
        final_view_error = ""
        runtime_fact_status = ""

        for item in reply_tool_results:
            row = _rt_safe_dict(item)
            item_type = _rt_safe_str(row.get("type"))

            if item_type == "room_mcp_final_result_view":
                final_view_status = _rt_safe_str(row.get("status")).lower()
                final_view_error = _rt_safe_str(row.get("error") or row.get("message"))
            elif item_type == "room_role_runtime_fact":
                runtime_fact_status = _rt_safe_str(row.get("status")).lower()

        has_reply_error = False
        if reply_status and reply_status not in {"success", "ok"}:
            has_reply_error = True
        if final_view_status and final_view_status not in {"success", "ok"}:
            has_reply_error = True
        if runtime_fact_status and runtime_fact_status not in {"success", "ok"}:
            has_reply_error = True

        if has_reply_error and _rt_has_provider_boundary_tool_results(reply_tool_results):
            return _rt_passthrough_runtime_packet(
                packet=reply_packet,
                rid=rid,
                room_id=room_id,
                rag_mode=rag_mode,
                mcp_overrides=mcp_overrides,
                mode_used=mode_used,
                fallback_query=question or content,
                fallback_response=final_view_error or reply_message or "role_reply_error",
                base_tool_results=base_tool_results,
                extra_tool_results=[
                    _build_tool_result_item("route_event", event=route_evt),
                ],
            )

        if has_reply_error:
            aborted = _append_aborted_event(
                room_id=room_id,
                request_id=rid,
                trigger_event_id=route_evt["id"],
                sender=str(role.get("slug") or "role"),
                role_id=str(role.get("role_id") or ""),
                reason=final_view_error or reply_message or reply_status or "role_reply_error",
            )
            return _rt_post_aborted_result(
                rid=rid,
                room_id=room_id,
                rag_mode=rag_mode,
                mcp_overrides=mcp_overrides,
                mode_used=mode_used,
                content=content,
                response="",
                message="room post accepted, role reply aborted",
                base_tool_results=base_tool_results,
                aborted_event=aborted,
                extra_tool_results=[
                    _build_tool_result_item("route_event", event=route_evt),
                    _build_tool_result_item(
                        "role_reply_packet",
                        status=_safe_str(reply_packet.get("status")),
                        message=reply_message,
                        error=final_view_error or _safe_str(reply_packet.get("error")),
                        tool_results=reply_tool_results,
                    ),
                ],
            )

        if role_text:
            generated = {
                "id": new_id("evt"),
                "ts": utc_iso(),
                "type": "room.message",
                "room_id": room_id,
                "request_id": rid,
                "trigger_event_id": route_evt["id"],
                "payload": _build_room_message_payload(
                    sender=str(role.get("slug") or role.get("name") or "role"),
                    sender_type="role",
                    content=role_text,
                    model=_safe_str(reply_packet.get("model") or role.get("model") or model_name, model_name),
                    mode_used=str(reply_packet.get("mode_used") or mode_used),
                    role_id=str(role.get("role_id") or ""),
                    role_name=str(role.get("name") or ""),
                    avatar=str(role.get("avatar") or "🤖"),
                    citations=reply_packet.get("citations"),
                    rss_evidence=reply_packet.get("rss_evidence"),
                    market_evidence=reply_packet.get("market_evidence"),
                    evidence_query=str(reply_packet.get("evidence_query") or question),
                    evidence_tools=reply_packet.get("evidence_tools"),
                    evidence_result=reply_packet.get("evidence_result"),
                    tool_calls=reply_packet.get("tool_calls"),
                    tool_results=reply_packet.get("tool_results"),
                ),
            }
            append_room_event(room_id, generated)
            touch_room_updated_at(room_id)
            _update_room_last_message(room_id, generated["id"])

            meta_info = _post_meta_from_event(generated, mode_used, question)
            packet = _post_ok(
                rid=rid,
                room_id=room_id,
                rag_mode=rag_mode,
                mcp_overrides=mcp_overrides,
                response=_post_response_from_event(generated, role_text),
                message="room post processed",
                mode_used=meta_info["mode_used"],
                citations=meta_info["citations"],
                rss_evidence=meta_info["rss_evidence"],
                market_evidence=meta_info["market_evidence"],
                evidence_query=meta_info["evidence_query"],
                evidence_tools=meta_info["evidence_tools"],
                evidence_result=meta_info["evidence_result"],
                tool_results=list(base_tool_results) + [
                    _build_tool_result_item("route_event", event=route_evt),
                    _build_tool_result_item("generated_event", event=generated),
                ],
            )
            return _rt_finalize_execution_packet(
                packet=packet,
                response=_post_response_from_event(generated, role_text),
                result_state="success",
                result_view="full_result",
                source_packet=_safe_dict(reply_packet),
                source_event=generated,
            )

        aborted = _append_aborted_event(
            room_id=room_id,
            request_id=rid,
            trigger_event_id=route_evt["id"],
            sender=str(role.get("slug") or "role"),
            role_id=str(role.get("role_id") or ""),
            reason="empty_role_reply",
        )
        return _rt_post_aborted_result(
            rid=rid,
            room_id=room_id,
            rag_mode=rag_mode,
            mcp_overrides=mcp_overrides,
            mode_used=mode_used,
            content=content,
            response="",
            message="room post accepted, role reply aborted",
            base_tool_results=base_tool_results,
            aborted_event=aborted,
            extra_tool_results=[
                _build_tool_result_item("route_event", event=route_evt),
            ],
        )

    except Exception as ex:
        aborted = _append_aborted_event(
            room_id=room_id,
            request_id=rid,
            trigger_event_id=route_evt["id"],
            sender=str(role.get("slug") or "role"),
            role_id=str(role.get("role_id") or ""),
            reason=f"exception:{type(ex).__name__}",
        )
        return _rt_post_aborted_result(
            rid=rid,
            room_id=room_id,
            rag_mode=rag_mode,
            mcp_overrides=mcp_overrides,
            mode_used=mode_used,
            content=content,
            message="room post accepted, role reply aborted",
            base_tool_results=base_tool_results,
            aborted_event=aborted,
            extra_tool_results=[
                _build_tool_result_item("route_event", event=route_evt),
            ],
        )

    return None


def _rt_handle_manual_mode(
    *,
    rid: str,
    room_id: str,
    rag_mode: str,
    mcp_overrides: Dict[str, Any],
    mode_used: str,
    content: str,
    reply_mode: str,
    base_tool_results: List[Any],
) -> Optional[Dict[str, Any]]:
    if reply_mode != "manual":
        return None

    return _rt_post_manual_result(
        rid=rid,
        room_id=room_id,
        rag_mode=rag_mode,
        mcp_overrides=mcp_overrides,
        mode_used=mode_used,
        content=content,
        reply_mode=reply_mode,
        base_tool_results=base_tool_results,
    )


def _rt_handle_supervisor_direct_execution(
    *,
    rid: str,
    room_id: str,
    rag_mode: str,
    mcp_overrides: Dict[str, Any],
    mode_used: str,
    model_name: str,
    supervisor_model: str,
    content: str,
    txt: str,
    evt: Dict[str, Any],
    reply_mode: str,
    runtime_ctx: Dict[str, Any],
    request_args: Dict[str, Any],
    base_tool_results: List[Any],
    room_supervisor_not_shared_reason: str,
) -> Optional[Dict[str, Any]]:
    if reply_mode != "supervisor_direct":
        return None

    if not _rt_supervisor_allowed_for_actor(runtime_ctx):
        return _rt_post_skip_result(
            rid=rid,
            room_id=room_id,
            rag_mode=rag_mode,
            mcp_overrides=mcp_overrides,
            mode_used=mode_used,
            content=content,
            base_tool_results=base_tool_results,
            skip_result=_rt_build_runtime_skip_result(
                reason_code=room_supervisor_not_shared_reason,
                path="supervisor_direct",
                ctx=runtime_ctx,
            ),
        )

    try:
        supervisor_packet = _safe_dict(
            _run_supervisor_direct_answer(
                room_id=room_id,
                question=txt,
                model_name=model_name,
                mode_used=mode_used,
                request_args=request_args,
            )
        )
        supervisor_text = _safe_str(supervisor_packet.get("content") or supervisor_packet.get("response"))
        supervisor_snapshot = _safe_dict(supervisor_packet.get("runtime_control_snapshot"))
        supervisor_tool_results = _rt_safe_list(supervisor_packet.get("tool_results"))
        supervisor_status = _safe_str(supervisor_packet.get("status")).lower()

        runtime_result_items: List[Dict[str, Any]] = []
        if supervisor_snapshot:
            runtime_result_items.append(
                _build_tool_result_item("runtime_control_snapshot", **supervisor_snapshot)
            )

        runtime_result = _build_tool_result_item(
            "supervisor_direct_runtime",
            room_id=room_id,
            reply_mode="supervisor_direct",
            status=_safe_str(supervisor_packet.get("status"), "error"),
            model=_safe_str(supervisor_packet.get("model") or supervisor_model or model_name, model_name),
            plan_summary=_safe_str(supervisor_packet.get("plan_summary")),
            fs_context=_safe_dict(supervisor_packet.get("fs_context")),
            notebook_result=_safe_dict(supervisor_packet.get("notebook_result")),
            tool_calls=_safe_list(supervisor_packet.get("tool_calls")),
            tool_results=supervisor_tool_results,
        )
        runtime_result_items.append(runtime_result)

        if supervisor_status in {"error", "denied"} and _rt_has_provider_boundary_tool_results(supervisor_tool_results):
            return _rt_passthrough_runtime_packet(
                packet=supervisor_packet,
                rid=rid,
                room_id=room_id,
                rag_mode=rag_mode,
                mcp_overrides=mcp_overrides,
                mode_used=mode_used,
                fallback_query=txt,
                fallback_response=_safe_str(supervisor_packet.get("message")) or "supervisor_direct_error",
                base_tool_results=base_tool_results,
                extra_tool_results=runtime_result_items,
                runtime_control_snapshot=supervisor_snapshot,
            )

        if supervisor_text:
            generated = {
                "id": new_id("evt"),
                "ts": utc_iso(),
                "type": "room.message",
                "room_id": room_id,
                "request_id": rid,
                "trigger_event_id": evt["id"],
                "payload": _build_room_message_payload(
                    sender="supervisor",
                    sender_type="ai",
                    content=supervisor_text,
                    model=_safe_str(supervisor_packet.get("model") or supervisor_model or model_name, model_name),
                    mode_used=_safe_str(supervisor_packet.get("mode_used") or mode_used, mode_used),
                    role_id="",
                    role_name="Supervisor",
                    avatar="🧭",
                    citations=supervisor_packet.get("citations"),
                    rss_evidence=supervisor_packet.get("rss_evidence"),
                    market_evidence=supervisor_packet.get("market_evidence"),
                    evidence_query=_safe_str(supervisor_packet.get("evidence_query") or txt, txt),
                    evidence_tools=supervisor_packet.get("evidence_tools"),
                    evidence_result=supervisor_packet.get("evidence_result"),
                    tool_calls=supervisor_packet.get("tool_calls"),
                    tool_results=supervisor_packet.get("tool_results"),
                    supervisor_memory_read=supervisor_packet.get("supervisor_memory_read"),
                    supervisor_memory_resume=supervisor_packet.get("supervisor_memory_resume"),
                    supervisor_memory_write=supervisor_packet.get("supervisor_memory_write"),
                    runtime_control_snapshot=supervisor_snapshot,
                ),
            }
            append_room_event(room_id, generated)
            touch_room_updated_at(room_id)
            _update_room_last_message(room_id, generated["id"])

            meta_info = _post_meta_from_event(generated, mode_used, txt)
            packet = _post_ok(
                rid=rid,
                room_id=room_id,
                rag_mode=rag_mode,
                mcp_overrides=mcp_overrides,
                response=_post_response_from_event(generated, supervisor_text),
                message="room supervisor direct reply finished",
                mode_used=meta_info["mode_used"],
                citations=meta_info["citations"],
                rss_evidence=meta_info["rss_evidence"],
                market_evidence=meta_info["market_evidence"],
                evidence_query=meta_info["evidence_query"],
                evidence_tools=meta_info["evidence_tools"],
                evidence_result=meta_info["evidence_result"],
                runtime_control_snapshot=supervisor_snapshot,
                tool_results=list(base_tool_results) + runtime_result_items + [
                    _build_tool_result_item("generated_event", event=generated),
                ],
            )
            return _rt_finalize_execution_packet(
                packet=packet,
                response=_post_response_from_event(generated, supervisor_text),
                result_state="success",
                result_view="full_result",
                source_packet=supervisor_packet,
                source_event=generated,
                runtime_control_snapshot=supervisor_snapshot,
            )

        aborted = _append_aborted_event(
            room_id=room_id,
            request_id=rid,
            trigger_event_id=evt["id"],
            sender="supervisor",
            reason="supervisor_direct_empty_response",
        )
        return _rt_post_aborted_result(
            rid=rid,
            room_id=room_id,
            rag_mode=rag_mode,
            mcp_overrides=mcp_overrides,
            mode_used=mode_used,
            content=content,
            message="room post accepted, supervisor direct reply aborted",
            base_tool_results=base_tool_results,
            aborted_event=aborted,
            extra_tool_results=runtime_result_items,
            runtime_control_snapshot=supervisor_snapshot,
        )
    except Exception as ex:
        aborted = _append_aborted_event(
            room_id=room_id,
            request_id=rid,
            trigger_event_id=evt["id"],
            sender="supervisor",
            reason=f"exception:{type(ex).__name__}",
        )
        return _rt_post_aborted_result(
            rid=rid,
            room_id=room_id,
            rag_mode=rag_mode,
            mcp_overrides=mcp_overrides,
            mode_used=mode_used,
            content=content,
            message="room post accepted, supervisor direct reply aborted",
            base_tool_results=base_tool_results,
            aborted_event=aborted,
            extra_tool_results=[
                _build_tool_result_item(
                    "supervisor_direct_runtime",
                    room_id=room_id,
                    reply_mode="supervisor_direct",
                    status="error",
                    model=_safe_str(supervisor_model or model_name, model_name),
                    error=f"{type(ex).__name__}: {ex}",
                ),
            ],
        )


def _rt_handle_orchestration_execution(
    *,
    rid: str,
    room_id: str,
    rag_mode: str,
    mcp_overrides: Dict[str, Any],
    mode_used: str,
    model_name: str,
    content: str,
    txt: str,
    evt: Dict[str, Any],
    reply_mode: str,
    runtime_ctx: Dict[str, Any],
    request_args: Dict[str, Any],
    active_role_objs: List[Any],
    authorized_active_role_objs: List[Any],
    base_tool_results: List[Any],
    room_role_not_shared_reason: str,
) -> Optional[Dict[str, Any]]:
    if not active_role_objs:
        return None

    if not _rt_safe_bool(runtime_ctx.get("actor_is_room_owner"), False) and not authorized_active_role_objs:
        return _rt_post_skip_result(
            rid=rid,
            room_id=room_id,
            rag_mode=rag_mode,
            mcp_overrides=mcp_overrides,
            mode_used=mode_used,
            content=content,
            base_tool_results=base_tool_results,
            skip_result=_rt_build_runtime_skip_result(
                reason_code=room_role_not_shared_reason,
                path="orchestration",
                ctx=runtime_ctx,
                active_role_objs=_rt_safe_list(active_role_objs),
            ),
        )

    raw_state = _safe_dict(load_state_doc(room_id))
    runtime_snapshot = _get_runtime_control_snapshot(room_id=room_id, state=raw_state)
    running_run_id = _safe_str(runtime_snapshot.get("run_id"))
    running_request_id = _safe_str(raw_state.get("current_request_id"))
    runtime_state = _safe_str(runtime_snapshot.get("runtime_state"))
    can_accept_new_prompt = as_bool(runtime_snapshot.get("can_accept_new_prompt"), False)

    if running_run_id and not can_accept_new_prompt:
        return _rt_post_passthrough(
            rid=rid,
            room_id=room_id,
            rag_mode=rag_mode,
            mcp_overrides=mcp_overrides,
            response=content,
            message=f"room runtime blocked: {runtime_state or 'running'}",
            mode_used=mode_used,
            evidence_query=content,
            base_tool_results=base_tool_results,
            extra_tool_results=[
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
            runtime_control_snapshot=runtime_snapshot,
            result_state="consumed",
            result_view="full_result",
            consume_trace={
                "kind": "room_runtime",
                "room_id": _safe_str(room_id),
                "mode_used": _safe_str(mode_used),
                "decision": "blocked_running",
                "run_id": _safe_str(running_run_id),
                "runtime_state": _safe_str(runtime_state),
            },
        )

    run_id = ""
    runtime_run_result: Dict[str, Any] = {}

    try:
        started = _start_room_runtime_run(
            room_id=room_id,
            rid=rid,
            raw_state=raw_state,
            reply_mode=reply_mode,
            active_role_objs=authorized_active_role_objs,
            model_name=model_name,
            trigger_event_id=evt["id"],
            request_args=request_args,
        )
        run_id = _safe_str(started.get("run_id"))
        runtime_run_result = _safe_dict(started.get("runtime_run_result"))
        request_args = dict(_safe_dict(started.get("request_args")))
        request_args = _rt_apply_question_aliases(request_args, txt)
        request_args["mcp_binding"] = _rt_apply_mcp_binding_question_aliases(
            _rt_safe_dict(request_args.get("mcp_binding")),
            question=txt,
            provider_id=_rt_safe_str(request_args.get("_room_mcp_provider_id")),
            provider_type=_rt_safe_str(request_args.get("_room_mcp_provider_type")),
            provider_origin=_rt_safe_str(request_args.get("_room_mcp_provider_origin")),
        )

        if reply_mode == "supervisor":
            orchestration_result = _run_supervisor_orchestration(
                room_id=room_id,
                question=txt,
                active_roles=authorized_active_role_objs,
                model_name=model_name,
                mode_used=mode_used,
                run_id=run_id,
                trigger_event_id=evt["id"],
                rid=rid,
                request_args=request_args,
            )

            if isinstance(orchestration_result, dict):
                plan_evt = _safe_dict(
                    orchestration_result.get("plan_evt")
                    or orchestration_result.get("plan_event")
                    or orchestration_result.get("plan")
                )
                delegate_evts = _rt_safe_list(
                    orchestration_result.get("delegate_evts")
                    or orchestration_result.get("delegate_events")
                    or orchestration_result.get("delegates")
                )
                final_evt = _safe_dict(
                    orchestration_result.get("final_evt")
                    or orchestration_result.get("final_event")
                    or orchestration_result.get("event")
                )
            elif isinstance(orchestration_result, (list, tuple)):
                orchestration_items = list(orchestration_result)
                if len(orchestration_items) < 3:
                    raise ValueError("invalid supervisor orchestration result")

                plan_evt = _safe_dict(orchestration_items[0])
                delegate_evts = _rt_safe_list(orchestration_items[1])

                final_evt = {}
                for item in reversed(orchestration_items[2:]):
                    candidate = _safe_dict(item)
                    if candidate and _safe_str(candidate.get("type")) == "room.message":
                        final_evt = candidate
                        break
                if not final_evt:
                    final_evt = _safe_dict(orchestration_items[-1])
            else:
                raise ValueError("invalid supervisor orchestration result type")

            preferred_evt = final_evt or _find_last_generated_message_event(
                room_id=room_id,
                run_id=run_id,
                trigger_event_id=evt["id"],
            )
            meta_info = _post_meta_from_event(preferred_evt, mode_used, txt)

            success_snapshot = _get_runtime_control_snapshot(
                room_id=room_id,
                state=_safe_dict(load_state_doc(room_id)),
            )

            extra_results: List[Dict[str, Any]] = [
                runtime_run_result,
                _build_tool_result_item("runtime_control_snapshot", **success_snapshot),
            ]

            if plan_evt:
                extra_results.append(_build_tool_result_item("plan_event", event=plan_evt))
            if delegate_evts:
                extra_results.append(_build_tool_result_item("delegate_events", events=delegate_evts))
            if final_evt:
                extra_results.append(_build_tool_result_item("final_event", event=final_evt))
                final_payload = _payload_of_event(final_evt)
                final_tool_results = _safe_list(final_payload.get("tool_results"))
                if final_tool_results:
                    extra_results.append(
                        _build_tool_result_item(
                            "runtime_summary",
                            room_id=room_id,
                            run_id=run_id,
                            tool_results=final_tool_results,
                        )
                    )
            if preferred_evt and not _same_event(preferred_evt, final_evt):
                extra_results.append(_build_tool_result_item("generated_event", event=preferred_evt))

            packet = _post_ok(
                rid=rid,
                room_id=room_id,
                rag_mode=rag_mode,
                mcp_overrides=mcp_overrides,
                response=_post_response_from_event(preferred_evt, content),
                message="room orchestration finished",
                mode_used=meta_info["mode_used"],
                citations=meta_info["citations"],
                rss_evidence=meta_info["rss_evidence"],
                market_evidence=meta_info["market_evidence"],
                evidence_query=meta_info["evidence_query"],
                evidence_tools=meta_info["evidence_tools"],
                evidence_result=meta_info["evidence_result"],
                runtime_control_snapshot=success_snapshot,
                tool_results=list(base_tool_results) + extra_results,
            )
            return _rt_finalize_execution_packet(
                packet=packet,
                response=_post_response_from_event(preferred_evt, content),
                result_state="success",
                result_view="full_result",
                source_event=final_evt or preferred_evt,
                runtime_control_snapshot=success_snapshot,
            )

        generated_events = _run_sequential_orchestration(
            room_id=room_id,
            question=txt,
            active_roles=authorized_active_role_objs,
            model_name=model_name,
            mode_used=mode_used,
            run_id=run_id,
            trigger_event_id=evt["id"],
            rid=rid,
            request_args=request_args,
        )
        preferred_evt = generated_events[-1] if generated_events else None
        meta_info = _post_meta_from_event(preferred_evt, mode_used, txt)

        success_snapshot = _get_runtime_control_snapshot(
            room_id=room_id,
            state=_safe_dict(load_state_doc(room_id)),
        )

        extra_results = [
            runtime_run_result,
            _build_tool_result_item("runtime_control_snapshot", **success_snapshot),
            _build_tool_result_item("generated_events", events=generated_events),
        ]

        if preferred_evt:
            extra_results.append(_build_tool_result_item("generated_event", event=preferred_evt))

        packet = _post_ok(
            rid=rid,
            room_id=room_id,
            rag_mode=rag_mode,
            mcp_overrides=mcp_overrides,
            response=_post_response_from_event(preferred_evt, content),
            message="room orchestration finished",
            mode_used=meta_info["mode_used"],
            citations=meta_info["citations"],
            rss_evidence=meta_info["rss_evidence"],
            market_evidence=meta_info["market_evidence"],
            evidence_query=meta_info["evidence_query"],
            evidence_tools=meta_info["evidence_tools"],
            evidence_result=meta_info["evidence_result"],
            runtime_control_snapshot=success_snapshot,
            tool_results=list(base_tool_results) + extra_results,
        )
        return _rt_finalize_execution_packet(
            packet=packet,
            response=_post_response_from_event(preferred_evt, content),
            result_state="success",
            result_view="full_result",
            source_event=preferred_evt,
            runtime_control_snapshot=success_snapshot,
        )
    except Exception as ex:
        import traceback
        from pathlib import Path
        from datetime import datetime, timezone

        error_traceback = traceback.format_exc()
        trace_text = (
            "\n\n=== nisb_room_runtime_exception ===\n"
            f"ts={datetime.now(timezone.utc).isoformat()}\n"
            f"room_id={room_id}\n"
            f"request_id={rid}\n"
            f"run_id={run_id}\n"
            f"exception_type={type(ex).__name__}\n"
            f"exception={str(ex)}\n"
            f"{error_traceback}\n"
        )

        try:
            trace_path = Path("/opt/nisb-data/shared/rooms") / str(room_id) / "runtime_exception_trace.log"
            trace_path.parent.mkdir(parents=True, exist_ok=True)
            with trace_path.open("a", encoding="utf-8") as fp:
                fp.write(trace_text[-12000:])
        except Exception:
            pass

        try:
            print("[nisb_room_runtime_exception]", trace_text[-8000:], flush=True)
        except Exception:
            pass

        if run_id:
            _mark_runtime_run_failed(room_id=room_id, run_id=run_id, rid=rid)

        aborted = _append_aborted_event(
            room_id=room_id,
            request_id=rid,
            trigger_event_id=evt["id"],
            sender="supervisor" if reply_mode == "supervisor" else "runtime",
            sender_type="system",
            reason=f"exception:{type(ex).__name__}",
            run_id=run_id,
            mode_used=mode_used,
        )

        error_snapshot = _get_runtime_control_snapshot(
            room_id=room_id,
            state=_safe_dict(load_state_doc(room_id)),
        )

        aborted_results = [
            runtime_run_result,
            _build_tool_result_item("runtime_control_snapshot", **error_snapshot),
            _build_tool_result_item("aborted_event", event=aborted),
        ]

        return _rt_post_aborted_result(
            rid=rid,
            room_id=room_id,
            rag_mode=rag_mode,
            mcp_overrides=mcp_overrides,
            mode_used=mode_used,
            content=content,
            message="room orchestration aborted",
            base_tool_results=base_tool_results,
            aborted_event=aborted,
            extra_tool_results=aborted_results,
            runtime_control_snapshot=error_snapshot,
        )
    finally:
        if run_id:
            _finalize_runtime_dispatch(room_id=room_id, run_id=run_id, rid=rid)


__all__ = [
    "_rt_handle_ai_mention_execution",
    "_rt_handle_manual_mode",
    "_rt_handle_orchestration_execution",
    "_rt_handle_provider_bridge_skip",
    "_rt_handle_role_execution",
    "_rt_handle_shared_auto_disabled_gate",
    "_rt_handle_supervisor_direct_execution",
]

