from __future__ import annotations

from typing import Any, Dict, List, Optional

from .room_packet_builder import _empty_evidence_result
from .room_result_envelope import (
    _build_tool_result_item,
    _error_envelope,
    _formal_envelope,
    _missing_args,
    _permission_denied,
    _status_from_success,
)
from .room_state_normalizer import (
    _safe_dict,
    _safe_list,
    _safe_str,
)


def _payload_of_event(evt: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not isinstance(evt, dict):
        return {}
    payload = evt.get("payload")
    return payload if isinstance(payload, dict) else {}


def _post_response_from_event(evt: Optional[Dict[str, Any]], fallback: str = "") -> str:
    payload = _payload_of_event(evt)
    return _safe_str(
        payload.get("final_response")
        or payload.get("response")
        or payload.get("content")
        or fallback
    )


def _post_meta_from_event(evt: Optional[Dict[str, Any]], default_mode: str, default_query: str) -> Dict[str, Any]:
    payload = _payload_of_event(evt)
    return {
        "mode_used": _safe_str(payload.get("mode_used"), default_mode),
        "citations": _safe_list(payload.get("citations")),
        "rss_evidence": _safe_list(payload.get("rss_evidence")),
        "market_evidence": _safe_list(payload.get("market_evidence")),
        "evidence_query": _safe_str(payload.get("evidence_query"), default_query),
        "evidence_tools": _safe_list(payload.get("evidence_tools")),
        "evidence_result": payload.get("evidence_result") or _empty_evidence_result(default_query),
        "result_state": _safe_str(payload.get("result_state")),
        "summary": _safe_str(payload.get("summary")),
        "final_response": _safe_str(
            payload.get("final_response")
            or payload.get("response")
            or payload.get("content")
        ),
        "error_code": _safe_str(payload.get("error_code")),
        "result_view": _safe_str(payload.get("result_view"), "full_result"),
        "visibility_source": _safe_str(payload.get("visibility_source")),
        "source_observation_allowed": bool(payload.get("source_observation_allowed")),
        "replay_recoverable": bool(payload.get("replay_recoverable")),
        "remote_execution_may_have_completed": bool(payload.get("remote_execution_may_have_completed")),
        "provider_trace": _safe_dict(payload.get("provider_trace")),
        "grant_trace": _safe_dict(payload.get("grant_trace")),
        "network_trace": _safe_dict(payload.get("network_trace")),
        "consume_trace": _safe_dict(payload.get("consume_trace")),
        "runtime_control_snapshot": _safe_dict(payload.get("runtime_control_snapshot")),
    }


def _post_ok(
    *,
    rid: str,
    room_id: str,
    response: str,
    message: str,
    rag_mode: str,
    mode_used: str,
    mcp_overrides: Optional[Dict[str, Any]] = None,
    citations: Optional[List[Any]] = None,
    rss_evidence: Optional[List[Any]] = None,
    market_evidence: Optional[List[Any]] = None,
    evidence_query: str = "",
    evidence_tools: Optional[List[Any]] = None,
    evidence_result: Optional[Dict[str, Any]] = None,
    tool_results: Optional[List[Any]] = None,
    runtime_control_snapshot: Optional[Dict[str, Any]] = None,
    result_state: str = "success",
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
) -> Dict[str, Any]:
    return _formal_envelope(
        request_id=rid,
        conv_id=room_id,
        rag_mode=rag_mode,
        mcp_overrides=mcp_overrides,
        mode_used=mode_used,
        response=response,
        status="success",
        result_state=result_state,
        summary=summary,
        final_response=final_response,
        error_code=error_code,
        result_view=result_view,
        visibility_source=visibility_source,
        source_observation_allowed=source_observation_allowed,
        replay_recoverable=replay_recoverable,
        remote_execution_may_have_completed=remote_execution_may_have_completed,
        provider_trace=provider_trace,
        grant_trace=grant_trace,
        network_trace=network_trace,
        consume_trace=consume_trace,
        message=message,
        citations=citations,
        tool_calls=[],
        tool_results=tool_results,
        rss_evidence=_safe_list(rss_evidence),
        market_evidence=_safe_list(market_evidence),
        evidence_query=_safe_str(evidence_query),
        evidence_tools=_safe_list(evidence_tools),
        evidence_result=evidence_result or _empty_evidence_result(evidence_query),
        runtime_control_snapshot=runtime_control_snapshot,
    )


__all__ = [
    "_build_tool_result_item",
    "_error_envelope",
    "_formal_envelope",
    "_missing_args",
    "_payload_of_event",
    "_permission_denied",
    "_post_meta_from_event",
    "_post_ok",
    "_post_response_from_event",
    "_status_from_success",
]
