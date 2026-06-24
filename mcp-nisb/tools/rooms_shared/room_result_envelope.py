from __future__ import annotations

from typing import Any, Dict, List, Optional

from .room_packet_observability import (
    _normalize_tool_activity_lists,
    _resolve_runtime_control_snapshot,
)
from .room_state_normalizer import (
    _normalize_room_mcp_overrides,
    _safe_dict,
    _safe_list,
    _safe_str,
)

_RESULT_STATE_SUCCESS = "success"
_RESULT_STATE_DENIED = "denied"
_RESULT_STATE_TIMEOUT = "timeout"
_RESULT_STATE_LATE_COMPLETE = "late_complete"
_RESULT_STATE_CONSUMED = "consumed"
_RESULT_STATE_ERROR = "error"

_ALLOWED_RESULT_STATES = {
    _RESULT_STATE_SUCCESS,
    _RESULT_STATE_DENIED,
    _RESULT_STATE_TIMEOUT,
    _RESULT_STATE_LATE_COMPLETE,
    _RESULT_STATE_CONSUMED,
    _RESULT_STATE_ERROR,
}


def _status_from_success(success: bool) -> str:
    return "success" if success else "error"


def _coerce_result_state_token(value: Any) -> str:
    raw = _safe_str(value).strip().lower().replace("-", "_")
    if raw in _ALLOWED_RESULT_STATES:
        return raw
    if raw in {"ok", "finished", "completed"}:
        return _RESULT_STATE_SUCCESS
    if raw in {"forbidden", "permission_denied"}:
        return _RESULT_STATE_DENIED
    if raw in {"timed_out"}:
        return _RESULT_STATE_TIMEOUT
    if raw in {"latecomplete"}:
        return _RESULT_STATE_LATE_COMPLETE
    if raw in {"failed", "failure"}:
        return _RESULT_STATE_ERROR
    if raw in {"abort", "aborted"}:
        return _RESULT_STATE_CONSUMED
    return ""


def _status_from_result_state(result_state: str) -> str:
    final_state = _normalize_result_state(result_state)
    if final_state in {
        _RESULT_STATE_SUCCESS,
        _RESULT_STATE_LATE_COMPLETE,
        _RESULT_STATE_CONSUMED,
    }:
        return "success"
    return "error"


def _build_tool_result_item(type_name: str, **payload: Any) -> Dict[str, Any]:
    row = {"type": type_name}
    row.update(payload)
    return row


def _normalize_formal_status(status: str) -> str:
    final_status = _safe_str(status, "success").lower()
    if final_status not in {"success", "error", "accepted"}:
        final_status = "success"
    return final_status


def _normalize_result_state(result_state: str, *, status: str = "") -> str:
    explicit = _coerce_result_state_token(result_state)
    if explicit:
        return explicit

    final_status = _normalize_formal_status(status)
    if final_status == "accepted":
        return _RESULT_STATE_CONSUMED
    if final_status == "error":
        return _RESULT_STATE_ERROR
    return _RESULT_STATE_SUCCESS


def _normalize_result_view(result_view: str, default: str = "full_result") -> str:
    return _safe_str(result_view, default) or default


def _normalize_trace_doc(value: Any) -> Dict[str, Any]:
    return dict(_safe_dict(value))


def _formal_envelope(
    *,
    request_id: str,
    conv_id: str = "",
    rag_mode: str = "",
    mcp_overrides: Optional[Dict[str, Any]] = None,
    mode_used: str = "",
    rss_evidence: Optional[List[Any]] = None,
    market_evidence: Optional[List[Any]] = None,
    evidence_query: str = "",
    evidence_tools: Optional[List[Any]] = None,
    evidence_result: Optional[Dict[str, Any]] = None,
    qa_id: str = "",
    group_id: str = "",
    citations: Optional[List[Any]] = None,
    response: str = "",
    status: str = "success",
    result_state: str = "",
    summary: str = "",
    final_response: str = "",
    error_code: str = "",
    result_view: str = "full_result",
    visibility_source: str = "",
    source_observation_allowed: bool = False,
    replay_recoverable: bool = False,
    remote_execution_may_have_completed: bool = False,
    provider_trace: Optional[Dict[str, Any]] = None,
    grant_trace: Optional[Dict[str, Any]] = None,
    network_trace: Optional[Dict[str, Any]] = None,
    consume_trace: Optional[Dict[str, Any]] = None,
    message: str = "",
    tool_calls: Optional[List[Any]] = None,
    tool_results: Optional[List[Any]] = None,
    runtime_control_snapshot: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    requested_status = _normalize_formal_status(status)
    final_result_state = _normalize_result_state(result_state, status=requested_status)
    final_status = (
        "accepted"
        if requested_status == "accepted" and final_result_state == _RESULT_STATE_CONSUMED
        else _status_from_result_state(final_result_state)
    )

    normalized_tool_calls, normalized_tool_results = _normalize_tool_activity_lists(
        tool_calls,
        tool_results,
    )

    resolved_runtime_control_snapshot = _resolve_runtime_control_snapshot(
        runtime_control_snapshot=runtime_control_snapshot,
        tool_results=normalized_tool_results,
    )

    safe_response = _safe_str(response)
    safe_final_response = _safe_str(final_response) or safe_response
    safe_summary = _safe_str(summary)
    raw_message = _safe_str(message)

    if not safe_response and final_status in {"success", "accepted"}:
        has_structured_context = bool(
            raw_message
            or normalized_tool_calls
            or normalized_tool_results
            or _safe_str(evidence_query)
            or _safe_list(evidence_tools)
            or _safe_dict(evidence_result)
        )
        if not has_structured_context:
            safe_response = "accepted" if final_status == "accepted" else "ok"

    if not safe_final_response:
        safe_final_response = safe_response

    if not safe_summary:
        if final_result_state in {
            _RESULT_STATE_ERROR,
            _RESULT_STATE_DENIED,
            _RESULT_STATE_TIMEOUT,
        }:
            safe_summary = raw_message or final_result_state
        else:
            safe_summary = raw_message or safe_final_response

    final_message_default = (
        "accepted"
        if final_status == "accepted"
        else "ok"
        if final_status == "success"
        else "error"
    )

    return {
        "conv_id": _safe_str(conv_id),
        "request_id": _safe_str(request_id),
        "rag_mode": _safe_str(rag_mode),
        "mcp_overrides": _normalize_room_mcp_overrides(mcp_overrides),
        "mode_used": _safe_str(mode_used),
        "rss_evidence": _safe_list(rss_evidence),
        "market_evidence": _safe_list(market_evidence),
        "evidence_query": _safe_str(evidence_query),
        "evidence_tools": _safe_list(evidence_tools),
        "evidence_result": _safe_dict(evidence_result),
        "qa_id": _safe_str(qa_id),
        "group_id": _safe_str(group_id),
        "citations": _safe_list(citations),
        "response": safe_response,
        "final_response": safe_final_response,
        "summary": safe_summary,
        "status": final_status,
        "result_state": final_result_state,
        "error_code": _safe_str(error_code),
        "result_view": _normalize_result_view(result_view),
        "visibility_source": _safe_str(visibility_source),
        "source_observation_allowed": bool(source_observation_allowed),
        "replay_recoverable": bool(replay_recoverable),
        "remote_execution_may_have_completed": bool(remote_execution_may_have_completed),
        "provider_trace": _normalize_trace_doc(provider_trace),
        "grant_trace": _normalize_trace_doc(grant_trace),
        "network_trace": _normalize_trace_doc(network_trace),
        "consume_trace": _normalize_trace_doc(consume_trace),
        "message": _safe_str(raw_message, final_message_default),
        "tool_calls": normalized_tool_calls,
        "tool_results": normalized_tool_results,
        "runtime_control_snapshot": resolved_runtime_control_snapshot,
    }


def _error_envelope(
    *,
    request_id: str,
    room_id: str = "",
    message: str,
    response: str = "",
    rag_mode: str = "",
    mode_used: str = "",
    result_state: str = _RESULT_STATE_ERROR,
    error_code: str = "",
    tool_results: Optional[List[Any]] = None,
    runtime_control_snapshot: Optional[Dict[str, Any]] = None,
    provider_trace: Optional[Dict[str, Any]] = None,
    grant_trace: Optional[Dict[str, Any]] = None,
    network_trace: Optional[Dict[str, Any]] = None,
    consume_trace: Optional[Dict[str, Any]] = None,
    replay_recoverable: bool = False,
    remote_execution_may_have_completed: bool = False,
) -> Dict[str, Any]:
    return _formal_envelope(
        request_id=request_id,
        conv_id=room_id,
        rag_mode=rag_mode,
        mode_used=mode_used,
        response=response,
        status="error",
        result_state=result_state,
        error_code=error_code,
        message=message,
        tool_calls=[],
        tool_results=tool_results,
        runtime_control_snapshot=runtime_control_snapshot,
        provider_trace=provider_trace,
        grant_trace=grant_trace,
        network_trace=network_trace,
        consume_trace=consume_trace,
        replay_recoverable=replay_recoverable,
        remote_execution_may_have_completed=remote_execution_may_have_completed,
    )


def _permission_denied(rid: str, room_id: str = "") -> Dict[str, Any]:
    return _error_envelope(
        request_id=rid,
        room_id=room_id,
        message="permission denied",
        result_state=_RESULT_STATE_DENIED,
        error_code="permission_denied",
    )


def _missing_args(rid: str, room_id: str, msg: str) -> Dict[str, Any]:
    return _error_envelope(
        request_id=rid,
        room_id=room_id,
        message=msg,
        result_state=_RESULT_STATE_ERROR,
        error_code="missing_args",
    )


__all__ = [
    "_build_tool_result_item",
    "_coerce_result_state_token",
    "_error_envelope",
    "_formal_envelope",
    "_missing_args",
    "_normalize_formal_status",
    "_normalize_result_state",
    "_permission_denied",
    "_status_from_result_state",
    "_status_from_success",
]
