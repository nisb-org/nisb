from __future__ import annotations

from typing import Any, Dict, List, Optional

from .room_packet_builder import _empty_evidence_result
from .room_packet_observability import (
    _merge_tool_results,
    _resolve_runtime_control_snapshot,
)
from .room_state_normalizer import (
    _safe_dict,
    _safe_list,
    _safe_str,
)
from .room_tool_common import _post_ok


_ALLOWED_RESULT_STATES = {
    "success",
    "denied",
    "timeout",
    "late_complete",
    "consumed",
    "error",
}


def _rt_merge_tool_results(
    base_tool_results: List[Any],
    extra_tool_results: Optional[List[Dict[str, Any]]] = None,
) -> List[Any]:
    return _merge_tool_results(base_tool_results, extra_tool_results)


def _rt_normalize_result_state(value: Any, default: str = "success") -> str:
    token = _safe_str(value).lower().replace("-", "_")
    if token in _ALLOWED_RESULT_STATES:
        return token
    if token in {"ok", "finished", "completed"}:
        return "success"
    if token in {"permission_denied", "forbidden"}:
        return "denied"
    if token in {"timed_out"}:
        return "timeout"
    if token in {"latecomplete"}:
        return "late_complete"
    if token in {"failed", "failure"}:
        return "error"
    if token in {"abort", "aborted"}:
        return "consumed"
    return default


def _rt_normalize_trace_doc(value: Any) -> Dict[str, Any]:
    src = _safe_dict(value)
    if not src:
        return {}
    out: Dict[str, Any] = {}
    for key, raw in src.items():
        if raw is None:
            continue
        if isinstance(raw, (str, int, float, bool)):
            out[key] = raw
        elif isinstance(raw, list):
            out[key] = list(raw)
        elif isinstance(raw, dict):
            out[key] = dict(raw)
    return out


def _rt_merge_trace_docs(base: Any, extra: Any) -> Dict[str, Any]:
    return {
        **_rt_normalize_trace_doc(base),
        **_rt_normalize_trace_doc(extra),
    }


def _rt_build_aborted_event_result(aborted_event: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "type": "aborted_event",
        "event": aborted_event,
    }


def _rt_build_manual_mode_result(room_id: str, reply_mode: str) -> Dict[str, Any]:
    return {
        "type": "room_manual_mode",
        "room_id": room_id,
        "reply_mode": reply_mode,
        "auto_reply_triggered": False,
    }


def _rt_build_consume_trace(
    *,
    room_id: str,
    mode_used: str,
    decision: str,
    extra: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    trace = {
        "kind": "room_runtime",
        "room_id": _safe_str(room_id),
        "mode_used": _safe_str(mode_used),
        "decision": _safe_str(decision),
    }
    trace.update(_safe_dict(extra))
    return trace


def _rt_status_from_result_state(result_state: str) -> str:
    final_state = _rt_normalize_result_state(result_state, "success")
    if final_state in {"success", "late_complete", "consumed"}:
        return "success"
    return "error"


def _rt_finalize_passthrough_packet(
    *,
    packet: Dict[str, Any],
    response: str,
    result_state: str,
    result_view: str,
    consume_trace: Optional[Dict[str, Any]] = None,
    provider_trace: Optional[Dict[str, Any]] = None,
    grant_trace: Optional[Dict[str, Any]] = None,
    network_trace: Optional[Dict[str, Any]] = None,
    runtime_control_snapshot: Optional[Dict[str, Any]] = None,
    replay_recoverable: bool = False,
    remote_execution_may_have_completed: bool = False,
) -> Dict[str, Any]:
    out = dict(_safe_dict(packet))
    if not out:
        return {}

    final_result_state = _rt_normalize_result_state(result_state, "success")
    final_status = _rt_status_from_result_state(final_result_state)

    resolved_tool_results = _safe_list(out.get("tool_results"))
    resolved_runtime_snapshot = _resolve_runtime_control_snapshot(
        runtime_control_snapshot=runtime_control_snapshot,
        tool_results=resolved_tool_results,
    )

    merged_provider_trace = _rt_merge_trace_docs(out.get("provider_trace"), provider_trace)
    merged_grant_trace = _rt_merge_trace_docs(out.get("grant_trace"), grant_trace)
    merged_network_trace = _rt_merge_trace_docs(out.get("network_trace"), network_trace)
    merged_consume_trace = _rt_merge_trace_docs(out.get("consume_trace"), consume_trace)

    if not merged_network_trace and final_result_state in {"timeout", "late_complete"}:
        merged_network_trace = {
            "kind": "room_runtime",
            "status": final_result_state,
        }

    if not merged_consume_trace and final_result_state == "consumed":
        merged_consume_trace = {
            "kind": "room_runtime",
            "decision": "consumed",
        }

    out["status"] = _safe_str(out.get("status")) or final_status
    out["result_state"] = _safe_str(out.get("result_state")) or final_result_state
    out["result_view"] = _safe_str(out.get("result_view")) or _safe_str(result_view) or "full_result"
    out["final_response"] = (
        _safe_str(out.get("final_response"))
        or _safe_str(out.get("response"))
        or _safe_str(response)
    )
    out["summary"] = (
        _safe_str(out.get("summary"))
        or _safe_str(out.get("message"))
        or out["final_response"]
    )
    out["provider_trace"] = merged_provider_trace
    out["grant_trace"] = merged_grant_trace
    out["network_trace"] = merged_network_trace
    out["consume_trace"] = merged_consume_trace
    out["runtime_control_snapshot"] = resolved_runtime_snapshot
    out["replay_recoverable"] = bool(out.get("replay_recoverable")) or bool(replay_recoverable)
    out["remote_execution_may_have_completed"] = (
        bool(out.get("remote_execution_may_have_completed"))
        or bool(remote_execution_may_have_completed)
    )

    return out


def _rt_post_passthrough(
    *,
    rid: str,
    room_id: str,
    rag_mode: str,
    mcp_overrides: Dict[str, Any],
    response: str,
    message: str,
    mode_used: str,
    evidence_query: str,
    base_tool_results: List[Any],
    extra_tool_results: Optional[List[Dict[str, Any]]] = None,
    runtime_control_snapshot: Optional[Dict[str, Any]] = None,
    result_state: str = "success",
    result_view: str = "full_result",
    consume_trace: Optional[Dict[str, Any]] = None,
    provider_trace: Optional[Dict[str, Any]] = None,
    grant_trace: Optional[Dict[str, Any]] = None,
    network_trace: Optional[Dict[str, Any]] = None,
    replay_recoverable: bool = False,
    remote_execution_may_have_completed: bool = False,
) -> Dict[str, Any]:
    merged_tool_results = _rt_merge_tool_results(base_tool_results, extra_tool_results)

    kwargs: Dict[str, Any] = {
        "rid": rid,
        "room_id": room_id,
        "rag_mode": rag_mode,
        "mcp_overrides": mcp_overrides,
        "response": response,
        "message": message,
        "mode_used": mode_used,
        "evidence_query": evidence_query,
        "evidence_result": _empty_evidence_result(evidence_query),
        "tool_results": merged_tool_results,
    }
    if runtime_control_snapshot:
        kwargs["runtime_control_snapshot"] = runtime_control_snapshot

    packet = _post_ok(**kwargs)
    return _rt_finalize_passthrough_packet(
        packet=packet,
        response=response,
        result_state=result_state,
        result_view=result_view,
        consume_trace=consume_trace,
        provider_trace=provider_trace,
        grant_trace=grant_trace,
        network_trace=network_trace,
        runtime_control_snapshot=runtime_control_snapshot,
        replay_recoverable=replay_recoverable,
        remote_execution_may_have_completed=remote_execution_may_have_completed,
    )


def _rt_post_skip_result(
    *,
    rid: str,
    room_id: str,
    rag_mode: str,
    mcp_overrides: Dict[str, Any],
    mode_used: str,
    content: str,
    base_tool_results: List[Any],
    skip_result: Dict[str, Any],
    runtime_control_snapshot: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    return _rt_post_passthrough(
        rid=rid,
        room_id=room_id,
        rag_mode=rag_mode,
        mcp_overrides=mcp_overrides,
        response=content,
        message="room message posted",
        mode_used=mode_used,
        evidence_query=content,
        base_tool_results=base_tool_results,
        extra_tool_results=[skip_result],
        runtime_control_snapshot=runtime_control_snapshot,
        result_state="consumed",
        result_view="full_result",
        consume_trace=_rt_build_consume_trace(
            room_id=room_id,
            mode_used=mode_used,
            decision="skip",
            extra={
                "skip_result_type": _safe_str(_safe_dict(skip_result).get("type")),
            },
        ),
    )


def _rt_post_aborted_result(
    *,
    rid: str,
    room_id: str,
    rag_mode: str,
    mcp_overrides: Dict[str, Any],
    mode_used: str,
    content: str,
    message: str,
    base_tool_results: List[Any],
    aborted_event: Dict[str, Any],
    extra_tool_results: Optional[List[Dict[str, Any]]] = None,
    runtime_control_snapshot: Optional[Dict[str, Any]] = None,
    response: Optional[str] = None,
) -> Dict[str, Any]:
    return _rt_post_passthrough(
        rid=rid,
        room_id=room_id,
        rag_mode=rag_mode,
        mcp_overrides=mcp_overrides,
        response=content if response is None else response,
        message=message,
        mode_used=mode_used,
        evidence_query=content,
        base_tool_results=base_tool_results,
        extra_tool_results=_rt_merge_tool_results(
            extra_tool_results,
            [_rt_build_aborted_event_result(aborted_event)],
        ),
        runtime_control_snapshot=runtime_control_snapshot,
        result_state="consumed",
        result_view="full_result",
        consume_trace=_rt_build_consume_trace(
            room_id=room_id,
            mode_used=mode_used,
            decision="aborted",
            extra={
                "event_type": _safe_str(_safe_dict(aborted_event).get("type")),
            },
        ),
    )


def _rt_post_manual_result(
    *,
    rid: str,
    room_id: str,
    rag_mode: str,
    mcp_overrides: Dict[str, Any],
    mode_used: str,
    content: str,
    reply_mode: str,
    base_tool_results: List[Any],
) -> Dict[str, Any]:
    return _rt_post_passthrough(
        rid=rid,
        room_id=room_id,
        rag_mode=rag_mode,
        mcp_overrides=mcp_overrides,
        response=content,
        message="room message posted",
        mode_used=mode_used,
        evidence_query=content,
        base_tool_results=base_tool_results,
        extra_tool_results=[
            _rt_build_manual_mode_result(room_id, reply_mode),
        ],
        result_state="consumed",
        result_view="full_result",
        consume_trace=_rt_build_consume_trace(
            room_id=room_id,
            mode_used=mode_used,
            decision="manual",
            extra={
                "reply_mode": _safe_str(reply_mode),
                "auto_reply_triggered": False,
            },
        ),
    )


__all__ = [
    "_rt_post_aborted_result",
    "_rt_post_manual_result",
    "_rt_post_passthrough",
    "_rt_post_skip_result",
]
