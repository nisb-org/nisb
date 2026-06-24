from __future__ import annotations

from typing import Any, Dict, Optional

from .room_request_bridge import _safe_dict, _safe_list, _safe_str
from .supervisor_runtime.memory_resume import (
    build_worker_standalone_task_from_memory,
    build_worker_supervisor_memory_context,
)


def resolve_worker_supervisor_memory_context(
    *,
    room_id: str,
    question: str,
    mcp_overrides: Dict[str, Any],
    role: Dict[str, Any],
    is_supervisor: bool,
) -> Dict[str, Any]:
    role_obj = _safe_dict(role)
    if not role_obj or is_supervisor:
        return {}

    return build_worker_supervisor_memory_context(
        room_id=room_id,
        question=_safe_str(question),
        mcp=_safe_dict(mcp_overrides),
    )


def stamp_worker_memory_request_args(
    request_args: Dict[str, Any],
    worker_memory_context: Dict[str, Any],
) -> Dict[str, Any]:
    req = request_args if isinstance(request_args, dict) else {}
    ctx = _safe_dict(worker_memory_context)

    req["worker_memory_context_available"] = bool(ctx.get("used"))
    req["worker_memory_decision"] = _safe_str(ctx.get("decision"), "none")
    req["worker_memory_reason"] = _safe_str(ctx.get("reason"))
    req["worker_memory_source"] = _safe_str(ctx.get("relative_path"))
    req["worker_memory_source_kind"] = _safe_str(ctx.get("source_kind"))
    req["worker_memory_resume_confidence"] = ctx.get("resume_confidence")
    req["worker_memory_resume_relation"] = _safe_str(ctx.get("resume_relation"))
    req["worker_memory_resume_context_dependent"] = bool(ctx.get("resume_context_dependent"))
    return req


def resolve_provider_safe_worker_question(
    *,
    question: str,
    worker_memory_context: Dict[str, Any],
    max_chars: int = 160,
) -> Dict[str, Any]:
    resolution = build_worker_standalone_task_from_memory(
        question=_safe_str(question),
        worker_memory_context=_safe_dict(worker_memory_context),
        for_provider=True,
        max_chars=max_chars,
    )
    resolved_question = _safe_str(resolution.get("query") or resolution.get("task") or question)

    return {
        "question": resolved_question,
        "resolved": bool(resolution.get("resolved")),
        "reason": _safe_str(resolution.get("reason")),
    }


def resolve_rag_safe_worker_question(
    *,
    question: str,
    worker_memory_context: Dict[str, Any],
    max_chars: int = 220,
) -> Dict[str, Any]:
    resolution = build_worker_standalone_task_from_memory(
        question=_safe_str(question),
        worker_memory_context=_safe_dict(worker_memory_context),
        for_provider=True,
        max_chars=max_chars,
    )
    resolved_question = _safe_str(resolution.get("query") or resolution.get("task") or question)

    return {
        "question": resolved_question,
        "task": resolved_question,
        "query": resolved_question,
        "resolved": bool(resolution.get("resolved")),
        "reason": _safe_str(resolution.get("reason")),
    }


def append_worker_memory_runtime_fact(
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
    out = _safe_dict(packet)
    ctx = _safe_dict(worker_memory_context)
    if not ctx:
        return out

    available = bool(ctx.get("used"))
    injected = bool(text_injected and available)
    explicit_used = context_used if context_used is not None else injected
    used = bool(available and explicit_used)

    fact = {
        "type": "room_worker_memory_context",
        "worker_memory_context_available": available,
        "worker_memory_context_used": used,
        "worker_memory_text_injected": injected,
        "worker_memory_original_question": _safe_str(original_question),
        "worker_memory_provider_question_resolved": bool(provider_question_resolved),
        "worker_memory_provider_question": _safe_str(provider_question) if provider_question_resolved else "",
        "worker_memory_provider_question_reason": _safe_str(provider_question_reason),
        "worker_memory_rag_question_resolved": bool(rag_question_resolved),
        "worker_memory_rag_question": _safe_str(rag_question) if rag_question_resolved else "",
        "worker_memory_rag_question_reason": _safe_str(rag_question_reason),
        "worker_memory_decision": _safe_str(ctx.get("decision"), "none"),
        "worker_memory_reason": _safe_str(ctx.get("reason")),
        "worker_memory_source": _safe_str(ctx.get("relative_path")),
        "worker_memory_source_kind": _safe_str(ctx.get("source_kind")),
        "worker_memory_topic_anchor": _safe_str(ctx.get("topic_anchor")) if used else "",
        "worker_memory_resume_confidence": ctx.get("resume_confidence"),
        "worker_memory_resume_relation": _safe_str(ctx.get("resume_relation")),
        "worker_memory_resume_context_dependent": bool(ctx.get("resume_context_dependent")),
    }

    tool_results = _safe_list(out.get("tool_results"))
    out["tool_results"] = tool_results + [fact]
    return out
