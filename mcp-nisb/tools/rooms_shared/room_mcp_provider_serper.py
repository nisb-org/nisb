from __future__ import annotations

from typing import Any, Dict

from .room_mcp_provider_i18n import (
    mcp_provider_error_response,
    mcp_text,
)
from .room_packet_builder import (
    _bridge_chat_result,
    _empty_evidence_result,
    _ensure_formal_packet,
)
from .room_request_bridge import (
    _build_orchestrate_args,
    _safe_dict,
    _safe_list,
    _safe_str,
)


def execute_room_mcp_provider_serper(
    *,
    room_id: str,
    request_id: str,
    question: str,
    requested_mode: str,
    mcp_overrides: Dict[str, Any],
    request_args: Dict[str, Any],
    role: Dict[str, Any],
) -> Dict[str, Any]:
    role_id = _safe_str(role.get("role_id"))
    role_name = _safe_str(role.get("name") or role.get("slug") or role_id)

    try:
        from tools.chat.chat_orchestrator import nisb_chat_orchestrate

        chat_args = _build_orchestrate_args(
            room_id=room_id,
            question=question,
            model_name=_safe_str(
                request_args.get("model")
                or request_args.get("model_name")
                or "gpt-4o-mini"
            ),
            request_args=request_args,
            role=role,
        )
        chat_args["_room_origin"] = True
        chat_args["_room_id"] = room_id
        chat_args["_room_no_conversation_persist"] = True
        chat_args["_room_history_visibility"] = "hidden"
        chat_args["rag_mode"] = "web"

        if _safe_str(request_args.get("_answer_lang")):
            chat_args["_answer_lang"] = _safe_str(request_args.get("_answer_lang"))
        if _safe_str(request_args.get("_answer_lang_name")):
            chat_args["_answer_lang_name"] = _safe_str(request_args.get("_answer_lang_name"))
        if _safe_str(request_args.get("_answer_lang_source")):
            chat_args["_answer_lang_source"] = _safe_str(request_args.get("_answer_lang_source"))

        local_overrides = dict(_safe_dict(chat_args.get("mcp_overrides")))
        local_overrides["serperEnabled"] = True
        chat_args["mcp_overrides"] = local_overrides

        chat_res = nisb_chat_orchestrate(chat_args)
        packet = _bridge_chat_result(
            room_id=room_id,
            question=question,
            request_id=request_id,
            fallback_mode="mcp",
            mcp_overrides=local_overrides,
            chat_res=chat_res,
        )

        tool_results = _safe_list(packet.get("tool_results"))
        tool_results.append(
            {
                "type": "room_mcp_provider",
                "role_id": role_id,
                "role_name": role_name,
                "provider_id": "serper",
                "tool_name": "search",
                "status": "success",
            }
        )
        packet["tool_results"] = tool_results

        if not _safe_str(packet.get("response")):
            packet["response"] = mcp_text(
                question,
                "provider_completed",
                request_args=request_args,
                provider="Serper",
            )
        if not _safe_str(packet.get("final_response")):
            packet["final_response"] = _safe_str(packet.get("response"))
        if not _safe_str(packet.get("content")):
            packet["content"] = _safe_str(packet.get("final_response") or packet.get("response"))

        return packet

    except Exception as ex:
        error = f"{type(ex).__name__}: {ex}"
        return _ensure_formal_packet(
            conv_id=room_id,
            request_id=request_id,
            rag_mode=requested_mode,
            mcp_overrides=mcp_overrides,
            mode_used="mcp",
            response=mcp_provider_error_response(
                question,
                "serper",
                error,
                request_args=request_args,
            ),
            status="error",
            message=f"room mcp provider failed: {error}",
            evidence_query=question,
            evidence_tools=["nisb_chat_orchestrate"],
            evidence_result={
                **_empty_evidence_result(question),
                "error": error,
            },
            tool_calls=[],
            tool_results=[
                {
                    "type": "room_mcp_provider_error",
                    "role_id": role_id,
                    "role_name": role_name,
                    "provider_id": "serper",
                    "error": error,
                }
            ],
        )


__all__ = [
    "execute_room_mcp_provider_serper",
]
