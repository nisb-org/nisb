from __future__ import annotations

from typing import Any, Dict, Optional
from tools.lang.answer_language import language_name, resolve_answer_lang

from .room_role_runtime_common import (
    _collapse_inline_text,
    _normalize_requested_mode,
    _safe_bool,
    _safe_dict,
    _safe_list,
    _safe_str,
    _truncate_text,
)
from .room_role_runtime_policy import (
    _extract_role_knowledge_binding,
    _extract_role_tool_policy,
)
from .room_role_runtime_args import (
    _build_role_runtime_request_args,
    _sanitize_room_worker_request_args,
)
from .room_role_runtime_mcp_binding import (
    _apply_room_mcp_binding_fact_to_request_args,
    _extract_explicit_role_mcp_provider_id,
    _extract_room_mcp_binding_fact,
    _should_dispatch_role_room_mcp_provider,
)
from .room_role_runtime_packets import (
    _append_role_runtime_fact,
    _build_role_mcp_runtime_exception_packet,
    _normalize_reply_packet,
)
from .room_role_runtime_provider_call import _call_role_room_mcp_provider_packet
from .room_mcp_provider_contract import normalize_room_role_mcp_contract
from .room_packet_builder import _empty_evidence_result
from .room_store import load_state_doc
from .room_supervisor_prompt_builders import _build_role_question
from .room_worker_execution import _execute_room_worker_packet

def _ensure_answer_language_metadata(
    request_args: Optional[Dict[str, Any]],
    question: str,
) -> Dict[str, Any]:
    out = dict(_safe_dict(request_args))
    existing_lang = _safe_str(out.get("_answer_lang"))

    if existing_lang:
        out.setdefault("_answer_lang_name", language_name(existing_lang))
        out.setdefault("_answer_lang_source", "current_user_question")
        return out

    try:
        answer_lang, _dbg = resolve_answer_lang(
            question=question,
            args={},
            default_lang="en",
        )
    except Exception:
        answer_lang = "en"

    answer_lang = _safe_str(answer_lang, "en") or "en"
    out["_answer_lang"] = answer_lang
    out["_answer_lang_name"] = language_name(answer_lang)
    out["_answer_lang_source"] = "current_user_question"
    return out

def _call_room_ai_reply_packet(
    *,
    room_id: str,
    question: str,
    model_name: str,
    request_args: Optional[Dict[str, Any]] = None,
    role: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    default_mode = _normalize_requested_mode(
        _safe_dict(request_args).get("requested_mode")
        or _safe_dict(request_args).get("mode_used")
        or _safe_dict(request_args).get("rag_mode"),
        "off",
    )
    local_request_args = _sanitize_room_worker_request_args(request_args, room_id)
    local_request_args = _ensure_answer_language_metadata(local_request_args, question)
    role_obj = _safe_dict(role)

    if role_obj:
        room_state = _safe_dict(load_state_doc(room_id))
        local_request_args = _build_role_runtime_request_args(
            request_args=local_request_args,
            role=role_obj,
            room_state=room_state,
            room_id=room_id,
        )

        local_request_args = _ensure_answer_language_metadata(local_request_args, question)
        role_binding = _safe_dict(local_request_args.get("role_binding")) or _extract_role_knowledge_binding(role_obj)
        role_tool_policy = _safe_dict(local_request_args.get("role_tool_policy")) or _extract_role_tool_policy(role_obj)
        role_tools = [key for key, enabled in role_tool_policy.items() if enabled]
        mcp_contract = normalize_room_role_mcp_contract(role_obj, role_tool_policy)

        local_request_args.setdefault("role_id", _safe_str(role_obj.get("role_id")))
        local_request_args.setdefault("role_name", _safe_str(role_obj.get("name") or role_obj.get("slug")))
        local_request_args.setdefault("role_slug", _safe_str(role_obj.get("slug")))
        local_request_args.setdefault("role_tools", role_tools)
        local_request_args.setdefault("role_tool_policy", role_tool_policy)
        local_request_args.setdefault("role_binding", role_binding)
        local_request_args.setdefault("knowledge_binding", role_binding)
        local_request_args.setdefault("mcp_binding", _safe_dict(mcp_contract.get("mcp_binding")))
        local_request_args.setdefault("mcp_provider_ids", _safe_list(mcp_contract.get("mcp_provider_ids")))
        local_request_args.setdefault(
            "requested_mode",
            default_mode or local_request_args.get("requested_mode") or local_request_args.get("rag_mode") or "off",
        )

    raw = _execute_room_worker_packet(
        room_id=room_id,
        question=question,
        model_name=model_name,
        request_args=local_request_args,
        role=role_obj,
    )
    return _normalize_reply_packet(raw, default_question=question, default_mode=default_mode)


def _generate_role_reply_packet(
    *,
    room_id: str,
    question: str,
    role: Dict[str, Any],
    model_name: str,
    request_args: Dict[str, Any],
) -> Dict[str, Any]:
    request_args = _ensure_answer_language_metadata(request_args, question)
    role_name = _safe_str(role.get("name") or role.get("slug") or role.get("role_id"), "role")
    default_mode = _safe_str(request_args.get("mode_used"))



    if role.get("enabled") is False:
        packet = {
            "content": f"{role_name} 已禁用，跳过本轮回复。",
            "response": f"{role_name} 已禁用，跳过本轮回复。",
            "status": "success",
            "message": "role disabled",
            "mode_used": default_mode,
            "citations": [],
            "rss_evidence": [],
            "market_evidence": [],
            "evidence_query": question,
            "evidence_tools": [],
            "evidence_result": _empty_evidence_result(question),
            "tool_calls": [],
            "tool_results": [],
            "model": "",
        }
        return _append_role_runtime_fact(
            packet,
            role=role,
            request_args=request_args,
            original_question=question,
        )



    role_model = _safe_str(
        role.get("model")
        or role.get("model_name")
        or role.get("reply_model")
        or model_name,
        model_name,
    )



    try:
        room_state = _safe_dict(load_state_doc(room_id))
        role_request_args = _build_role_runtime_request_args(
            request_args=request_args,
            role=role,
            room_state=room_state,
            room_id=room_id,
        )
        role_request_args = _ensure_answer_language_metadata(role_request_args, question)
    except Exception as e:
        packet = _build_role_mcp_runtime_exception_packet(
            room_id=room_id,
            question=question,
            role=role,
            request_args=request_args,
            default_mode=default_mode or "mcp",
            phase="build_role_runtime_request_args",
            exc=e,
        )
        return _append_role_runtime_fact(
            packet,
            role=role,
            request_args=request_args,
            original_question=question,
        )



    try:
        binding_fact = _extract_room_mcp_binding_fact(role_request_args)
    except Exception as e:
        packet = _build_role_mcp_runtime_exception_packet(
            room_id=room_id,
            question=question,
            role=role,
            request_args=role_request_args,
            default_mode=default_mode or "mcp",
            phase="extract_room_mcp_binding_fact",
            exc=e,
        )
        return _append_role_runtime_fact(
            packet,
            role=role,
            request_args=role_request_args,
            original_question=question,
        )



    dispatch_role_room_mcp = _should_dispatch_role_room_mcp_provider(
        role=role,
        request_args=role_request_args,
        binding_fact=binding_fact,
    )



    if binding_fact and dispatch_role_room_mcp:
        provider_request_args = role_request_args
        try:
            provider_request_args = _apply_room_mcp_binding_fact_to_request_args(
                request_args=role_request_args,
                binding_fact=binding_fact,
            )
            packet = _call_role_room_mcp_provider_packet(
                room_id=room_id,
                question=question,
                role=role,
                request_args=provider_request_args,
                default_mode=default_mode or "mcp",
            )
        except Exception as e:
            packet = _build_role_mcp_runtime_exception_packet(
                room_id=room_id,
                question=question,
                role=role,
                request_args=provider_request_args,
                default_mode=default_mode or "mcp",
                phase="call_room_mcp_provider",
                exc=e,
            )


        packet_status = _safe_str(packet.get("status")).lower()
        packet["content"] = _safe_str(packet.get("content"))


        if packet_status and packet_status not in {"success", "ok"}:
            packet["response"] = _safe_str(packet.get("response") or packet.get("content"))
        else:
            packet["response"] = _safe_str(
                packet.get("response") or packet.get("content") or packet.get("message")
            )


        packet["status"] = _safe_str(packet.get("status"), "success" if packet["response"] else "")
        packet["message"] = _safe_str(packet.get("message"))
        packet["mode_used"] = _safe_str(packet.get("mode_used"), "mcp")
        packet["evidence_query"] = _safe_str(packet.get("evidence_query"), question) or question
        packet["evidence_result"] = packet.get("evidence_result") or _empty_evidence_result(packet["evidence_query"])
        packet["tool_calls"] = _safe_list(packet.get("tool_calls"))
        packet["tool_results"] = _safe_list(packet.get("tool_results"))


        return _append_role_runtime_fact(
            packet,
            role=role,
            request_args=provider_request_args,
            original_question=question,
        )



    role_question = _build_role_question(
        room_id=room_id,
        question=question,
        role=role,
        request_args=role_request_args,
        room_state=room_state,
    )



    packet = _call_room_ai_reply_packet(
        room_id=room_id,
        question=role_question,
        model_name=role_model,
        request_args=role_request_args,
        role=role,
    )



    packet_status = _safe_str(packet.get("status")).lower()
    packet["content"] = _safe_str(packet.get("content"))



    if packet_status and packet_status not in {"success", "ok"}:
        packet["response"] = _safe_str(packet.get("response") or packet.get("content"))
    else:
        packet["response"] = _safe_str(
            packet.get("response") or packet.get("content") or packet.get("message")
        )



    packet["status"] = _safe_str(packet.get("status"), "success" if packet["response"] else "")
    packet["message"] = _safe_str(packet.get("message"))
    packet["mode_used"] = _safe_str(packet.get("mode_used"), default_mode)
    packet["evidence_query"] = _safe_str(packet.get("evidence_query"), question) or question
    packet["evidence_result"] = packet.get("evidence_result") or _empty_evidence_result(packet["evidence_query"])
    packet["tool_calls"] = _safe_list(packet.get("tool_calls"))
    packet["tool_results"] = _safe_list(packet.get("tool_results"))



    return _append_role_runtime_fact(
        packet,
        role=role,
        request_args=role_request_args,
        original_question=question,
    )

__all__ = [
    "_safe_str",
    "_safe_list",
    "_safe_dict",
    "_safe_bool",
    "_truncate_text",
    "_collapse_inline_text",
    "_normalize_reply_packet",
    "_sanitize_room_worker_request_args",
    "_extract_role_tool_policy",
    "_extract_role_knowledge_binding",
    "_build_role_runtime_request_args",
    "_call_room_ai_reply_packet",
    "_generate_role_reply_packet",
    "_extract_explicit_role_mcp_provider_id",
    "_should_dispatch_role_room_mcp_provider",
    "_ensure_answer_language_metadata",
]

