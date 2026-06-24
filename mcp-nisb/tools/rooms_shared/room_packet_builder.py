from __future__ import annotations

from typing import Any, Dict, List, Optional

from .room_packet_observability import (
    _build_supervisor_memory_payload,
    _build_supervisor_memory_tool_results,
    _extract_tool_call_identity,
    _extract_tool_call_ref,
    _extract_tool_index,
    _extract_tool_name,
    _find_runtime_control_snapshot,
    _merge_tool_results,
    _normalize_supervisor_memory_checkpoint,
    _normalize_supervisor_memory_read_result,
    _normalize_supervisor_memory_resume_doc,
    _normalize_supervisor_memory_resume_result,
    _normalize_supervisor_memory_write_result,
    _normalize_tool_activity_lists,
    _resolve_runtime_control_snapshot,
)

_ALLOWED_MODE_USED = {"off", "cite", "ground", "web", "auto"}
_ALLOWED_PACKET_STATUSES = {"success", "error", "accepted"}
_ALLOWED_RESULT_STATES = {
    "success",
    "denied",
    "timeout",
    "late_complete",
    "consumed",
    "error",
}


def _safe_str(v: Any, default: str = "") -> str:
    if v is None:
        return default
    s = str(v).strip()
    return s if s else default


def _safe_list(v: Any) -> List[Any]:
    return v if isinstance(v, list) else []


def _safe_dict(v: Any) -> Dict[str, Any]:
    return v if isinstance(v, dict) else {}


def _safe_int(v: Any, default: int = -1) -> int:
    try:
        return int(v)
    except Exception:
        return default


def _coerce_dict_list(v: Any) -> List[Dict[str, Any]]:
    if not isinstance(v, list):
        return []
    out: List[Dict[str, Any]] = []
    for item in v:
        if isinstance(item, dict):
            out.append(item)
    return out


def _coerce_str_list(v: Any) -> List[str]:
    if not isinstance(v, list):
        return []
    out: List[str] = []
    seen = set()
    for item in v:
        s = _safe_str(item)
        if not s or s in seen:
            continue
        seen.add(s)
        out.append(s)
    return out


def _normalize_mode_used(value: Any, fallback: str = "off") -> str:
    s = _safe_str(value).lower()
    if s in _ALLOWED_MODE_USED:
        return s
    fb = _safe_str(fallback).lower()
    return fb if fb in _ALLOWED_MODE_USED else "off"


def _normalize_packet_status(value: Any, fallback: str = "success") -> str:
    s = _safe_str(value, fallback).lower()
    if s in _ALLOWED_PACKET_STATUSES:
        return s
    fb = _safe_str(fallback, "success").lower()
    return fb if fb in _ALLOWED_PACKET_STATUSES else "success"


def _result_state_from_packet_status(status: str) -> str:
    final_status = _normalize_packet_status(status, "success")
    if final_status == "error":
        return "error"
    if final_status == "accepted":
        return "consumed"
    return "success"


def _normalize_result_state(value: Any, fallback: str = "success") -> str:
    raw = _safe_str(value).lower().replace("-", "_")
    if raw in _ALLOWED_RESULT_STATES:
        return raw
    if raw in {"ok", "finished", "completed"}:
        return "success"
    if raw in {"permission_denied", "forbidden"}:
        return "denied"
    if raw in {"timed_out"}:
        return "timeout"
    if raw in {"latecomplete"}:
        return "late_complete"
    if raw in {"failed", "failure"}:
        return "error"
    if raw in {"abort", "aborted"}:
        return "consumed"

    fb = _safe_str(fallback).lower().replace("-", "_")
    if fb in _ALLOWED_RESULT_STATES:
        return fb

    return "success"


def _normalize_result_view(value: Any, fallback: str = "") -> str:
    return _safe_str(value, fallback)


def _normalize_trace_doc(v: Any) -> Dict[str, Any]:
    src = _safe_dict(v)
    if not src:
        return {}

    out: Dict[str, Any] = {}
    for key, value in src.items():
        if value is None:
            continue
        if isinstance(value, (str, int, float, bool)):
            out[key] = value
        elif isinstance(value, list):
            out[key] = list(value)
        elif isinstance(value, dict):
            out[key] = dict(value)
    return out


def _empty_evidence_result(query: str = "") -> Dict[str, Any]:
    eq = _safe_str(query)
    return {
        "citations": [],
        "rss_evidence": [],
        "market_evidence": [],
        "evidence_query": eq,
        "evidence_tools": [],
    }


def _ensure_formal_packet(
    *,
    conv_id: str,
    request_id: str,
    rag_mode: str,
    mcp_overrides: Optional[Dict[str, Any]] = None,
    mode_used: str = "",
    response: str = "",
    status: str = "success",
    message: str = "",
    citations: Optional[List[Any]] = None,
    rss_evidence: Optional[List[Any]] = None,
    market_evidence: Optional[List[Any]] = None,
    evidence_query: str = "",
    evidence_tools: Optional[List[Any]] = None,
    evidence_result: Optional[Dict[str, Any]] = None,
    qa_id: str = "",
    group_id: str = "",
    tool_calls: Optional[List[Any]] = None,
    tool_results: Optional[List[Any]] = None,
    supervisor_memory_read: Optional[Dict[str, Any]] = None,
    supervisor_memory_resume: Optional[Dict[str, Any]] = None,
    supervisor_memory_write: Optional[Dict[str, Any]] = None,
    runtime_control_snapshot: Optional[Dict[str, Any]] = None,
    result_state: str = "",
    result_view: str = "",
    final_response: str = "",
    summary: str = "",
    provider_trace: Optional[Dict[str, Any]] = None,
    grant_trace: Optional[Dict[str, Any]] = None,
    network_trace: Optional[Dict[str, Any]] = None,
    consume_trace: Optional[Dict[str, Any]] = None,
    replay_recoverable: bool = False,
    remote_execution_may_have_completed: bool = False,
) -> Dict[str, Any]:
    final_status = _normalize_packet_status(status, "success")
    final_rag_mode = _normalize_mode_used(rag_mode, "off")
    final_mode_used = _normalize_mode_used(mode_used, final_rag_mode)
    final_response_text = _safe_str(response)

    default_message = (
        "ok"
        if final_status == "success"
        else "accepted"
        if final_status == "accepted"
        else "error"
    )
    final_message = _safe_str(message, default_message)

    if final_status in {"success", "accepted"} and not final_response_text:
        final_response_text = _safe_str(message, "ok" if final_status == "success" else "accepted")
    if final_status == "error" and not final_response_text:
        final_response_text = _safe_str(message, "error")

    eq = _safe_str(evidence_query)
    normalized_evidence_result = _safe_dict(evidence_result)
    if not normalized_evidence_result:
        normalized_evidence_result = _empty_evidence_result(eq)

    if not eq:
        eq = _safe_str(normalized_evidence_result.get("evidence_query"), final_response_text)

    final_citations = _safe_list(citations) or _safe_list(normalized_evidence_result.get("citations"))
    final_rss_evidence = _safe_list(rss_evidence) or _safe_list(normalized_evidence_result.get("rss_evidence"))
    final_market_evidence = _safe_list(market_evidence) or _safe_list(normalized_evidence_result.get("market_evidence"))
    final_evidence_tools = _safe_list(evidence_tools) or _safe_list(normalized_evidence_result.get("evidence_tools"))

    normalized_evidence_result["citations"] = final_citations
    normalized_evidence_result["rss_evidence"] = final_rss_evidence
    normalized_evidence_result["market_evidence"] = final_market_evidence
    normalized_evidence_result["evidence_query"] = eq
    normalized_evidence_result["evidence_tools"] = final_evidence_tools

    supervisor_memory_payload = _build_supervisor_memory_payload(
        supervisor_memory_read=supervisor_memory_read,
        supervisor_memory_resume=supervisor_memory_resume,
        supervisor_memory_write=supervisor_memory_write,
    )
    supervisor_memory_tool_results = _build_supervisor_memory_tool_results(
        supervisor_memory_read=supervisor_memory_read,
        supervisor_memory_resume=supervisor_memory_resume,
        supervisor_memory_write=supervisor_memory_write,
    )

    normalized_tool_calls, normalized_tool_results = _normalize_tool_activity_lists(
        tool_calls,
        _merge_tool_results(tool_results, supervisor_memory_tool_results),
    )

    resolved_runtime_control_snapshot = _resolve_runtime_control_snapshot(
        runtime_control_snapshot=runtime_control_snapshot,
        tool_results=normalized_tool_results,
    )

    final_result_state = _normalize_result_state(
        result_state,
        _result_state_from_packet_status(final_status),
    )
    final_result_view = _normalize_result_view(result_view)
    final_final_response = _safe_str(final_response) or final_response_text
    final_summary = _safe_str(summary) or final_message or final_final_response

    return {
        "conv_id": _safe_str(conv_id),
        "request_id": _safe_str(request_id),
        "rag_mode": final_rag_mode,
        "mcp_overrides": _safe_dict(mcp_overrides),
        "mode_used": final_mode_used,
        "rss_evidence": final_rss_evidence,
        "market_evidence": final_market_evidence,
        "evidence_query": eq,
        "evidence_tools": final_evidence_tools,
        "evidence_result": normalized_evidence_result,
        "qa_id": _safe_str(qa_id),
        "group_id": _safe_str(group_id),
        "citations": final_citations,
        "response": final_response_text,
        "status": final_status,
        "message": final_message,
        "tool_calls": normalized_tool_calls,
        "tool_results": normalized_tool_results,
        "supervisor_memory": supervisor_memory_payload,
        "supervisor_memory_read": _safe_dict(supervisor_memory_payload.get("read")),
        "supervisor_memory_resume": _safe_dict(supervisor_memory_payload.get("resume")),
        "supervisor_memory_write": _safe_dict(supervisor_memory_payload.get("write")),
        "runtime_control_snapshot": resolved_runtime_control_snapshot,
        "result_state": final_result_state,
        "result_view": final_result_view,
        "final_response": final_final_response,
        "summary": final_summary,
        "provider_trace": _normalize_trace_doc(provider_trace),
        "grant_trace": _normalize_trace_doc(grant_trace),
        "network_trace": _normalize_trace_doc(network_trace),
        "consume_trace": _normalize_trace_doc(consume_trace),
        "replay_recoverable": bool(replay_recoverable),
        "remote_execution_may_have_completed": bool(remote_execution_may_have_completed),
    }


def _normalize_qascope_packet(
    *,
    room_id: str,
    request_id: str,
    rag_mode: str,
    mcp_overrides: Dict[str, Any],
    binding: Dict[str, Any],
    question: str,
    extracted: Dict[str, Any],
) -> Dict[str, Any]:
    content = _safe_str(extracted.get("response") or extracted.get("content"))
    evidence_query = _safe_str(extracted.get("evidence_query"), question) or question
    citations = _coerce_dict_list(extracted.get("citations"))
    rss_evidence = _coerce_dict_list(extracted.get("rss_evidence"))
    market_evidence = _coerce_dict_list(extracted.get("market_evidence"))
    evidence_tools = _coerce_str_list(extracted.get("evidence_tools")) or ["nisb_qascope_ask"]

    raw_evidence_result = _safe_dict(extracted.get("evidence_result"))
    qa_meta = _safe_dict(raw_evidence_result.get("qa_meta")) or _safe_dict(extracted.get("qa_meta"))
    evidence_result = {
        **_empty_evidence_result(evidence_query),
        **raw_evidence_result,
        "citations": citations,
        "rss_evidence": rss_evidence,
        "market_evidence": market_evidence,
        "evidence_query": evidence_query,
        "evidence_tools": evidence_tools,
    }

    orchestrator_time_scope = _safe_dict(evidence_result.get("orchestrator_time_scope"))
    retrieval_time_scope = _safe_dict(evidence_result.get("retrieval_time_scope"))
    effective_source = _safe_str(evidence_result.get("effective_source"))

    tool_results = [
        {
            "type": "room_qascope_bridge",
            "qa_id": _safe_str(qa_meta.get("qa_id") or extracted.get("qa_id")),
            "group_id": _safe_str(binding.get("group_id")),
            "binding": {
                "library_id": _safe_str(binding.get("library_id")),
                "group_id": _safe_str(binding.get("group_id")),
                "doc_id": _safe_str(binding.get("doc_id")),
                "store_scope": _safe_str(binding.get("store_scope")),
                "evidence_scope": _safe_str(binding.get("evidence_scope")),
                "time_filter_days": binding.get("time_filter_days") or "",
                "time_start": _safe_str(binding.get("time_start")),
                "time_end": _safe_str(binding.get("time_end")),
            },
            "qa_meta": qa_meta,
            "orchestrator_time_scope": orchestrator_time_scope,
            "retrieval_time_scope": retrieval_time_scope,
            "effective_source": effective_source,
        }
    ]

    return _ensure_formal_packet(
        conv_id=room_id,
        request_id=request_id,
        rag_mode=_normalize_mode_used(rag_mode, "cite"),
        mcp_overrides=mcp_overrides,
        mode_used=_normalize_mode_used(rag_mode, "cite"),
        response=content,
        status="success",
        message="room worker bridged qascope reply",
        citations=citations,
        rss_evidence=rss_evidence,
        market_evidence=market_evidence,
        evidence_query=evidence_query,
        evidence_tools=evidence_tools,
        evidence_result=evidence_result,
        qa_id=_safe_str(qa_meta.get("qa_id") or extracted.get("qa_id")),
        group_id=_safe_str(binding.get("group_id")),
        tool_calls=[],
        tool_results=tool_results,
        runtime_control_snapshot=_safe_dict(extracted.get("runtime_control_snapshot")),
    )


def _bridge_chat_result(
    *,
    room_id: str,
    question: str,
    request_id: str,
    fallback_mode: str,
    mcp_overrides: Dict[str, Any],
    chat_res: Any,
) -> Dict[str, Any]:
    user_question = _safe_str(question)
    normalized_fallback_mode = _normalize_mode_used(fallback_mode, "off")

    if not isinstance(chat_res, dict):
        return _ensure_formal_packet(
            conv_id=room_id,
            request_id=request_id,
            rag_mode=normalized_fallback_mode,
            mcp_overrides=mcp_overrides,
            mode_used=normalized_fallback_mode,
            response=_safe_str(chat_res),
            status="success",
            message="room worker bridged non-dict result",
            evidence_query=user_question,
            evidence_tools=["nisb_chat_orchestrate"],
            evidence_result={
                **_empty_evidence_result(user_question),
                "bridge": "nisb_chat_orchestrate",
            },
            tool_calls=[],
            tool_results=[{"type": "room_chat_bridge", "bridge": "nisb_chat_orchestrate", "source": "non_dict"}],
        )

    evidence_result = _safe_dict(chat_res.get("evidence_result"))
    inner_conv_id = _safe_str(chat_res.get("conv_id"))
    if inner_conv_id and inner_conv_id != room_id:
        evidence_result["chat_conv_id"] = inner_conv_id

    bridge_tool_results = _safe_list(chat_res.get("tool_results"))
    bridge_tool_results.append(
        {
            "type": "room_chat_bridge",
            "bridge": "nisb_chat_orchestrate",
            "chat_conv_id": inner_conv_id,
        }
    )

    return _ensure_formal_packet(
        conv_id=room_id,
        request_id=_safe_str(chat_res.get("request_id") or request_id),
        rag_mode=_normalize_mode_used(chat_res.get("rag_mode"), normalized_fallback_mode),
        mcp_overrides=mcp_overrides if mcp_overrides else _safe_dict(chat_res.get("mcp_overrides")),
        mode_used=_normalize_mode_used(chat_res.get("mode_used"), normalized_fallback_mode),
        response=_safe_str(chat_res.get("response") or chat_res.get("content") or chat_res.get("message")),
        status=_safe_str(chat_res.get("status"), "success"),
        message=_safe_str(chat_res.get("message")),
        citations=_safe_list(chat_res.get("citations")),
        rss_evidence=_safe_list(chat_res.get("rss_evidence")),
        market_evidence=_safe_list(chat_res.get("market_evidence")),
        evidence_query=user_question,
        evidence_tools=_safe_list(chat_res.get("evidence_tools")) or ["nisb_chat_orchestrate"],
        evidence_result=evidence_result,
        qa_id=_safe_str(chat_res.get("qa_id")),
        group_id=_safe_str(chat_res.get("group_id")),
        tool_calls=_safe_list(chat_res.get("tool_calls")),
        tool_results=bridge_tool_results,
        supervisor_memory_read=_safe_dict(chat_res.get("supervisor_memory_read")),
        supervisor_memory_resume=_safe_dict(chat_res.get("supervisor_memory_resume")),
        supervisor_memory_write=_safe_dict(chat_res.get("supervisor_memory_write")),
        runtime_control_snapshot=_safe_dict(chat_res.get("runtime_control_snapshot")),
        result_state=_safe_str(chat_res.get("result_state")),
        result_view=_safe_str(chat_res.get("result_view")),
        final_response=_safe_str(chat_res.get("final_response")),
        summary=_safe_str(chat_res.get("summary")),
        provider_trace=_safe_dict(chat_res.get("provider_trace")),
        grant_trace=_safe_dict(chat_res.get("grant_trace")),
        network_trace=_safe_dict(chat_res.get("network_trace")),
        consume_trace=_safe_dict(chat_res.get("consume_trace")),
        replay_recoverable=bool(chat_res.get("replay_recoverable")),
        remote_execution_may_have_completed=bool(chat_res.get("remote_execution_may_have_completed")),
    )


def _build_room_message_payload(
    *,
    sender: str,
    sender_type: str,
    content: str,
    model: str = "",
    mode_used: str = "",
    role_id: str = "",
    role_name: str = "",
    avatar: str = "",
    citations: Optional[List[Any]] = None,
    rss_evidence: Optional[List[Any]] = None,
    market_evidence: Optional[List[Any]] = None,
    evidence_query: str = "",
    evidence_tools: Optional[List[Any]] = None,
    evidence_result: Optional[Dict[str, Any]] = None,
    qa_id: str = "",
    group_id: str = "",
    status: str = "success",
    message: str = "",
    tool_calls: Optional[List[Any]] = None,
    tool_results: Optional[List[Any]] = None,
    supervisor_memory_read: Optional[Dict[str, Any]] = None,
    supervisor_memory_resume: Optional[Dict[str, Any]] = None,
    supervisor_memory_write: Optional[Dict[str, Any]] = None,
    runtime_control_snapshot: Optional[Dict[str, Any]] = None,
    result_state: str = "",
    result_view: str = "",
    final_response: str = "",
    summary: str = "",
    provider_trace: Optional[Dict[str, Any]] = None,
    grant_trace: Optional[Dict[str, Any]] = None,
    network_trace: Optional[Dict[str, Any]] = None,
    consume_trace: Optional[Dict[str, Any]] = None,
    replay_recoverable: bool = False,
    remote_execution_may_have_completed: bool = False,
) -> Dict[str, Any]:
    final_content = _safe_str(content)
    eq = _safe_str(evidence_query, final_content)

    supervisor_memory_payload = _build_supervisor_memory_payload(
        supervisor_memory_read=supervisor_memory_read,
        supervisor_memory_resume=supervisor_memory_resume,
        supervisor_memory_write=supervisor_memory_write,
    )
    supervisor_memory_tool_results = _build_supervisor_memory_tool_results(
        supervisor_memory_read=supervisor_memory_read,
        supervisor_memory_resume=supervisor_memory_resume,
        supervisor_memory_write=supervisor_memory_write,
    )

    normalized_tool_calls, normalized_tool_results = _normalize_tool_activity_lists(
        tool_calls,
        _merge_tool_results(tool_results, supervisor_memory_tool_results),
    )

    final_status = _normalize_packet_status(status, "success")
    resolved_runtime_control_snapshot = _resolve_runtime_control_snapshot(
        runtime_control_snapshot=runtime_control_snapshot,
        tool_results=normalized_tool_results,
    )
    final_result_state = _normalize_result_state(
        result_state,
        _result_state_from_packet_status(final_status),
    )
    final_result_view = _normalize_result_view(result_view)
    final_final_response = _safe_str(final_response) or final_content or _safe_str(message)
    final_summary = _safe_str(summary) or _safe_str(message) or final_final_response

    return {
        "sender": _safe_str(sender),
        "sender_type": _safe_str(sender_type),
        "content": final_content,
        "response": final_content or _safe_str(message),
        "model": _safe_str(model),
        "mode_used": _normalize_mode_used(mode_used, "off"),
        "role_id": _safe_str(role_id),
        "role_name": _safe_str(role_name),
        "avatar": _safe_str(avatar),
        "citations": _safe_list(citations),
        "rss_evidence": _safe_list(rss_evidence),
        "market_evidence": _safe_list(market_evidence),
        "evidence_query": eq,
        "evidence_tools": _safe_list(evidence_tools),
        "evidence_result": _safe_dict(evidence_result) or _empty_evidence_result(eq),
        "qa_id": _safe_str(qa_id),
        "group_id": _safe_str(group_id),
        "status": final_status,
        "message": _safe_str(message),
        "tool_calls": normalized_tool_calls,
        "tool_results": normalized_tool_results,
        "supervisor_memory": supervisor_memory_payload,
        "supervisor_memory_read": _safe_dict(supervisor_memory_payload.get("read")),
        "supervisor_memory_resume": _safe_dict(supervisor_memory_payload.get("resume")),
        "supervisor_memory_write": _safe_dict(supervisor_memory_payload.get("write")),
        "runtime_control_snapshot": resolved_runtime_control_snapshot,
        "result_state": final_result_state,
        "result_view": final_result_view,
        "final_response": final_final_response,
        "summary": final_summary,
        "provider_trace": _normalize_trace_doc(provider_trace),
        "grant_trace": _normalize_trace_doc(grant_trace),
        "network_trace": _normalize_trace_doc(network_trace),
        "consume_trace": _normalize_trace_doc(consume_trace),
        "replay_recoverable": bool(replay_recoverable),
        "remote_execution_may_have_completed": bool(remote_execution_may_have_completed),
    }


__all__ = [
    "_bridge_chat_result",
    "_build_room_message_payload",
    "_build_supervisor_memory_payload",
    "_build_supervisor_memory_tool_results",
    "_coerce_dict_list",
    "_coerce_str_list",
    "_empty_evidence_result",
    "_ensure_formal_packet",
    "_extract_tool_call_identity",
    "_extract_tool_call_ref",
    "_extract_tool_index",
    "_extract_tool_name",
    "_find_runtime_control_snapshot",
    "_merge_tool_results",
    "_normalize_mode_used",
    "_normalize_packet_status",
    "_normalize_qascope_packet",
    "_normalize_result_state",
    "_normalize_supervisor_memory_checkpoint",
    "_normalize_supervisor_memory_read_result",
    "_normalize_supervisor_memory_resume_doc",
    "_normalize_supervisor_memory_resume_result",
    "_normalize_supervisor_memory_write_result",
    "_normalize_tool_activity_lists",
    "_resolve_runtime_control_snapshot",
    "_safe_dict",
    "_safe_list",
    "_safe_str",
]
