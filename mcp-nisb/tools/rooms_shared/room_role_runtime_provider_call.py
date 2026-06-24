from __future__ import annotations

from typing import Any, Dict, Tuple

from .room_packet_builder import _empty_evidence_result
from .room_role_runtime_common import (
    _safe_dict,
    _safe_list,
    _safe_str,
)
from .room_role_runtime_packets import _normalize_reply_packet
from .supervisor_runtime.memory_resume import (
    build_worker_standalone_task_from_memory,
    build_worker_supervisor_memory_context,
)


def _resolve_role_provider_memory_question(
    *,
    room_id: str,
    question: str,
    request_args: Dict[str, Any],
) -> Tuple[str, Dict[str, Any], Dict[str, Any]]:
    base_question = _safe_str(question)
    provider_request_args = _safe_dict(request_args)
    mcp_overrides = _safe_dict(provider_request_args.get("mcp_overrides"))

    if not base_question:
        return "", {}, {
            "resolved": False,
            "reason": "empty_question",
            "query": "",
            "task": "",
        }

    try:
        worker_memory_context = build_worker_supervisor_memory_context(
            room_id=room_id,
            question=base_question,
            mcp=mcp_overrides,
        )
    except Exception as ex:
        worker_memory_context = {
            "enabled": True,
            "used": False,
            "decision": "none",
            "reason": f"provider_memory_context_error:{type(ex).__name__}",
            "relative_path": "",
            "source_kind": "",
            "topic_anchor": "",
            "context_text": "",
        }

    try:
        task_resolution = build_worker_standalone_task_from_memory(
            question=base_question,
            worker_memory_context=worker_memory_context,
            for_provider=True,
            max_chars=160,
        )
    except Exception as ex:
        task_resolution = {
            "resolved": False,
            "reason": f"provider_standalone_rewrite_error:{type(ex).__name__}",
            "query": base_question,
            "task": base_question,
        }

    provider_question = _safe_str(
        _safe_dict(task_resolution).get("query")
        or _safe_dict(task_resolution).get("task")
        or base_question
    )

    if not provider_question:
        provider_question = base_question

    return provider_question, _safe_dict(worker_memory_context), _safe_dict(task_resolution)


def _append_role_provider_memory_fact(
    packet: Dict[str, Any],
    *,
    original_question: str,
    provider_question: str,
    worker_memory_context: Dict[str, Any],
    task_resolution: Dict[str, Any],
) -> Dict[str, Any]:
    out = _safe_dict(packet)
    ctx = _safe_dict(worker_memory_context)
    resolution = _safe_dict(task_resolution)

    if not ctx and not resolution:
        return out

    context_available = bool(ctx.get("used"))
    question_resolved = bool(resolution.get("resolved"))
    context_used = bool(context_available and question_resolved)

    fact = {
        "type": "room_worker_memory_context",
        "worker_memory_context_available": context_available,
        "worker_memory_context_used": context_used,
        "worker_memory_text_injected": False,
        "worker_memory_provider_question_resolved": question_resolved,
        "worker_memory_provider_question": _safe_str(provider_question) if question_resolved else "",
        "worker_memory_provider_question_reason": _safe_str(resolution.get("reason")),
        "worker_memory_original_question": _safe_str(original_question),
        "worker_memory_decision": _safe_str(ctx.get("decision"), "none"),
        "worker_memory_reason": _safe_str(ctx.get("reason")),
        "worker_memory_source": _safe_str(ctx.get("relative_path")),
        "worker_memory_source_kind": _safe_str(ctx.get("source_kind")),
        "worker_memory_topic_anchor": _safe_str(ctx.get("topic_anchor")) if context_used else "",
        "worker_memory_resume_confidence": ctx.get("resume_confidence"),
        "worker_memory_resume_relation": _safe_str(ctx.get("resume_relation")),
        "worker_memory_resume_context_dependent": bool(ctx.get("resume_context_dependent")),
    }

    tool_results = _safe_list(out.get("tool_results"))
    out["tool_results"] = tool_results + [fact]
    return out


def _call_role_room_mcp_provider_packet(
    *,
    room_id: str,
    question: str,
    role: Dict[str, Any],
    request_args: Dict[str, Any],
    default_mode: str,
) -> Dict[str, Any]:
    from uuid import uuid4
    from .room_worker_execution import _call_room_mcp_provider

    provider_request_args = dict(request_args or {})
    request_id = _safe_str(provider_request_args.get("request_id")) or f"role_mcp_{uuid4()}"
    requested_mode = _safe_str(
        provider_request_args.get("rag_mode")
        or provider_request_args.get("requested_mode"),
        "mcp",
    )
    if requested_mode == "off":
        requested_mode = "mcp"

    original_question = _safe_str(question)
    provider_question, worker_memory_context, task_resolution = _resolve_role_provider_memory_question(
        room_id=room_id,
        question=original_question,
        request_args=provider_request_args,
    )

    provider_request_args["worker_memory_context_available"] = bool(worker_memory_context.get("used"))
    provider_request_args["worker_memory_context_used"] = bool(task_resolution.get("resolved"))
    provider_request_args["worker_memory_decision"] = _safe_str(worker_memory_context.get("decision"), "none")
    provider_request_args["worker_memory_reason"] = _safe_str(worker_memory_context.get("reason"))
    provider_request_args["worker_memory_source"] = _safe_str(worker_memory_context.get("relative_path"))
    provider_request_args["worker_memory_source_kind"] = _safe_str(worker_memory_context.get("source_kind"))
    provider_request_args["worker_memory_provider_question_resolved"] = bool(task_resolution.get("resolved"))
    provider_request_args["worker_memory_provider_question"] = provider_question
    provider_request_args["worker_memory_provider_question_reason"] = _safe_str(task_resolution.get("reason"))
    provider_request_args["worker_memory_original_question"] = original_question

    raw_packet = _call_room_mcp_provider(
        room_id=room_id,
        request_id=request_id,
        question=provider_question,
        requested_mode=requested_mode,
        mcp_overrides=_safe_dict(provider_request_args.get("mcp_overrides")),
        request_args=provider_request_args,
        role=role,
    )

    packet = _normalize_reply_packet(
        raw_packet,
        default_question=provider_question,
        default_mode=requested_mode or default_mode or "mcp",
    )
    packet["mode_used"] = _safe_str(packet.get("mode_used"), requested_mode or default_mode or "mcp")
    packet["evidence_query"] = _safe_str(packet.get("evidence_query"), provider_question) or provider_question
    packet["evidence_result"] = packet.get("evidence_result") or _empty_evidence_result(packet["evidence_query"])
    packet["tool_calls"] = _safe_list(packet.get("tool_calls"))
    packet["tool_results"] = _safe_list(packet.get("tool_results"))

    return _append_role_provider_memory_fact(
        packet,
        original_question=original_question,
        provider_question=provider_question,
        worker_memory_context=worker_memory_context,
        task_resolution=task_resolution,
    )


__all__ = [
    "_call_role_room_mcp_provider_packet",
]
