from __future__ import annotations

from typing import Any, Dict, List

from .room_packet_builder import _empty_evidence_result
from .room_role_runtime_common import (
    _collapse_inline_text,
    _safe_bool,
    _safe_dict,
    _safe_list,
    _safe_str,
    _truncate_text,
)
from .room_role_runtime_mcp_binding import _room_provider_source_exists_locally


def _tool_result_status(tool_results: Any, tool_type: str) -> str:
    for item in _safe_list(tool_results):
        obj = _safe_dict(item)
        if _safe_str(obj.get("type")) == tool_type:
            return _safe_str(obj.get("status"))
    return ""


def _tool_result_error(tool_results: Any, tool_type: str) -> str:
    for item in _safe_list(tool_results):
        obj = _safe_dict(item)
        if _safe_str(obj.get("type")) == tool_type:
            return _safe_str(obj.get("error"))
    return ""


def _reply_packet_has_provider_error(raw: Dict[str, Any]) -> bool:
    tool_results = _safe_list(raw.get("tool_results"))
    final_view_status = _tool_result_status(tool_results, "room_mcp_final_result_view").lower()
    runtime_fact_status = _tool_result_status(tool_results, "room_role_runtime_fact").lower()
    raw_status = _safe_str(raw.get("status")).lower()

    if final_view_status and final_view_status not in {"success", "ok"}:
        return True
    if runtime_fact_status and runtime_fact_status not in {"success", "ok"}:
        return True
    if raw_status and raw_status not in {"success", "ok"}:
        return True
    return False


def _is_success_status(value: Any) -> bool:
    return _safe_str(value).lower() in {"success", "ok"}


def _normalize_reply_packet(
    raw: Any,
    *,
    default_question: str,
    default_mode: str,
    default_content: str = "",
) -> Dict[str, Any]:
    if isinstance(raw, dict):
        raw_dict = dict(raw)
        tool_results = _safe_list(raw_dict.get("tool_results"))
        provider_error = _reply_packet_has_provider_error(raw_dict)

        preferred_content = _safe_str(raw_dict.get("content"))
        fallback_response = _safe_str(raw_dict.get("response"))
        fallback_text = _safe_str(raw_dict.get("text"))
        fallback_answer = _safe_str(raw_dict.get("answer"))

        if provider_error:
            content = preferred_content
        else:
            content = _safe_str(
                preferred_content
                or fallback_response
                or fallback_text
                or fallback_answer
                or default_content
            )

        raw_status = _safe_str(raw_dict.get("status"))
        message = _safe_str(raw_dict.get("message"))
        response = _safe_str(raw_dict.get("response") or content)

        if provider_error and not content:
            status = raw_status or "error"
            response = ""
            if not message:
                message = (
                    _tool_result_error(tool_results, "room_mcp_final_result_view")
                    or _tool_result_error(tool_results, "room_role_runtime_fact")
                    or "role reply packet contains provider error"
                )
        else:
            status = raw_status or ("success" if content else "")

        evidence_query = _safe_str(raw_dict.get("evidence_query"), default_question) or default_question
        return {
            "content": content,
            "response": response,
            "status": status,
            "message": message,
            "mode_used": _safe_str(raw_dict.get("mode_used"), default_mode),
            "citations": _safe_list(raw_dict.get("citations") or raw_dict.get("references")),
            "rss_evidence": _safe_list(raw_dict.get("rss_evidence")),
            "market_evidence": _safe_list(raw_dict.get("market_evidence")),
            "evidence_query": evidence_query,
            "evidence_tools": _safe_list(raw_dict.get("evidence_tools")),
            "evidence_result": raw_dict.get("evidence_result") or _empty_evidence_result(evidence_query),
            "tool_calls": _safe_list(raw_dict.get("tool_calls")),
            "tool_results": tool_results,
            "model": _safe_str(raw_dict.get("model")),
            "raw": raw,
        }

    content = _safe_str(raw, default_content)
    return {
        "content": content,
        "response": content,
        "status": "success" if content else "",
        "message": "",
        "mode_used": _safe_str(default_mode),
        "citations": [],
        "rss_evidence": [],
        "market_evidence": [],
        "evidence_query": default_question,
        "evidence_tools": [],
        "evidence_result": _empty_evidence_result(default_question),
        "tool_calls": [],
        "tool_results": [],
        "model": "",
        "raw": raw,
    }


def _extract_provider_fact(tool_results: List[Any]) -> Dict[str, Any]:
    provider_fact: Dict[str, Any] = {}
    rows = _safe_list(tool_results)

    for item in rows:
        row = _safe_dict(item)
        item_type = _safe_str(row.get("type"))
        if item_type in {
            "room_mcp_provider_execution",
            "room_mcp_provider_error",
            "room_mcp_final_result_view",
        }:
            provider_fact = row

    return provider_fact


def _append_role_runtime_fact(
    packet: Dict[str, Any],
    *,
    role: Dict[str, Any],
    request_args: Dict[str, Any],
    original_question: str,
) -> Dict[str, Any]:
    out = dict(packet or {})
    tool_results = _safe_list(out.get("tool_results"))
    provider_fact = _extract_provider_fact(tool_results)
    role_obj = _safe_dict(role)
    tool_policy = _safe_dict(request_args.get("role_tool_policy") or request_args.get("tool_policy"))
    knowledge_binding = _safe_dict(request_args.get("role_binding") or request_args.get("knowledge_binding"))

    role_id = _safe_str(role_obj.get("role_id"))
    role_name = _safe_str(role_obj.get("name") or role_obj.get("slug") or role_id)
    role_slug = _safe_str(role_obj.get("slug"))
    response = _safe_str(out.get("response") or out.get("content") or out.get("message"))
    status = _safe_str(out.get("status"), "success" if response else "")
    mode_used = _safe_str(out.get("mode_used") or request_args.get("rag_mode") or request_args.get("requested_mode"))
    requested_mode = _safe_str(request_args.get("requested_mode") or request_args.get("rag_mode"))
    evidence_query = _safe_str(out.get("evidence_query"), original_question) or original_question
    citations = _safe_list(out.get("citations"))
    has_citations = bool(citations)

    fact = {
        "type": "room_role_runtime_fact",
        "role_id": role_id,
        "role_name": role_name,
        "role_slug": role_slug,
        "actor_user_id": _safe_str(request_args.get("actor_user_id")),
        "room_owner_user_id": _safe_str(request_args.get("room_owner_user_id")),
        "actor_is_room_owner": _safe_bool(
            request_args.get("actor_is_room_owner"),
            _safe_bool(request_args.get("is_owner_actor"), False),
        ),
        "role_owner_user_id": _safe_str(request_args.get("role_owner_user_id") or role_obj.get("owner_user_id")),
        "role_shared_to_room": _safe_bool(request_args.get("role_shared_to_room"), False),
        "supervisor_shared_to_room": _safe_bool(request_args.get("supervisor_shared_to_room"), False),
        "shared_room_config_enabled": _safe_bool(request_args.get("shared_room_config_enabled_snapshot"), False),
        "effective_execution_scope": _safe_str(request_args.get("effective_execution_scope")),
        "runtime_scope_stripped": _safe_bool(request_args.get("runtime_scope_stripped"), False),
        "stripped_fields": _safe_list(request_args.get("stripped_fields")),
        "requested_mode": requested_mode,
        "mode_used": mode_used,
        "status": status,
        "binding_ready": _safe_bool(request_args.get("binding_ready"), False),
        "knowledge_scope": {
            "library_id": _safe_str(knowledge_binding.get("library_id")),
            "doc_id": _safe_str(knowledge_binding.get("doc_id")),
            "group_id": _safe_str(knowledge_binding.get("group_id")),
            "store_scope": _safe_str(knowledge_binding.get("store_scope"), "global"),
            "evidence_scope": _safe_str(knowledge_binding.get("evidence_scope"), "global"),
            "time_filter_days": knowledge_binding.get("time_filter_days") or "",
            "time_start": _safe_str(knowledge_binding.get("time_start")),
            "time_end": _safe_str(knowledge_binding.get("time_end")),
        },
        "tool_policy": {
            "rag": _safe_bool(tool_policy.get("rag"), False),
            "web": _safe_bool(tool_policy.get("web"), False),
            "mcp": _safe_bool(tool_policy.get("mcp"), False),
            "code": _safe_bool(tool_policy.get("code"), False),
            "fs_read": _safe_bool(tool_policy.get("fs_read"), False),
            "fs_write": _safe_bool(tool_policy.get("fs_write"), False),
        },
        "provider_id": _safe_str(
            provider_fact.get("provider_id")
            or _safe_dict(provider_fact.get("provider_trace")).get("provider_id")
        ),
        "provider_label": _safe_str(provider_fact.get("provider_label")),
        "provider_status": _safe_str(provider_fact.get("status")),
        "provider_error": _safe_str(provider_fact.get("error")),
        "auth_type": _safe_str(provider_fact.get("auth_type")),
        "auth_required": _safe_bool(provider_fact.get("auth_required"), False),
        "auth_configured": _safe_bool(provider_fact.get("auth_configured"), False),
        "availability_reason": _safe_str(provider_fact.get("availability_reason")),
        "has_citations": has_citations,
        "citations_count": len(citations),
        "response_preview": _truncate_text(_collapse_inline_text(response), 240),
        "evidence_query": evidence_query,
    }

    tool_results.append(fact)
    out["tool_results"] = tool_results
    out["status"] = status
    out["response"] = response or _safe_str(out.get("message"))
    out["content"] = _safe_str(out.get("content") or out.get("response"))
    return out


def _fallback_room_mcp_error_context(
    *,
    role: Dict[str, Any],
    request_args: Dict[str, Any],
) -> Dict[str, Any]:
    req = _safe_dict(request_args)
    role_obj = _safe_dict(role)
    binding = _safe_dict(req.get("mcp_binding"))
    provider_snapshot = _safe_dict(
        req.get("mcp_provider_snapshot")
        or req.get("provider_snapshot")
        or binding.get("provider_snapshot")
    )
    imported_provider = _safe_dict(
        req.get("imported_provider")
        or binding.get("imported_provider")
    )
    room_source = _safe_dict(
        binding.get("room_source")
        or provider_snapshot.get("room_source")
        or imported_provider.get("room_source")
    )

    provider_ids = _safe_list(req.get("mcp_provider_ids"))
    first_provider_id = ""
    for item in provider_ids:
        item_id = _safe_str(item)
        if item_id:
            first_provider_id = item_id
            break

    provider_id = _safe_str(
        binding.get("provider_id")
        or req.get("provider_id")
        or provider_snapshot.get("provider_id")
        or imported_provider.get("provider_id")
        or first_provider_id
    )

    source_room_id = _safe_str(
        binding.get("source_room_id")
        or req.get("source_room_id")
        or room_source.get("room_id")
        or provider_snapshot.get("source_room_id")
        or imported_provider.get("source_room_id")
    )

    if not source_room_id and provider_id.startswith("room_provider__"):
        source_room_id = _safe_str(provider_id[len("room_provider__"):])

    provider_type = _safe_str(
        binding.get("provider_type")
        or binding.get("provider_kind")
        or req.get("provider_type")
        or req.get("provider_kind")
        or provider_snapshot.get("provider_type")
        or provider_snapshot.get("provider_kind")
        or imported_provider.get("provider_type")
        or imported_provider.get("provider_kind")
    )

    if provider_id.startswith("room_provider__"):
        provider_type = "room_shared_capability"

    provider_origin = _safe_str(
        binding.get("provider_origin")
        or req.get("provider_origin")
        or provider_snapshot.get("provider_origin")
        or imported_provider.get("provider_origin")
    )

    if not provider_origin and imported_provider:
        provider_origin = "imported_remote"

    if not provider_origin and provider_id.startswith("room_provider__"):
        provider_origin = (
            "local_room_shared"
            if _room_provider_source_exists_locally(source_room_id)
            else "imported_remote"
        )

    if provider_origin in {"local", "local_registry", "registry_local", "local_provider"}:
        provider_origin = (
            "local_room_shared"
            if _room_provider_source_exists_locally(source_room_id)
            else "imported_remote"
        )

    return {
        "role_id": _safe_str(role_obj.get("role_id")),
        "role_name": _safe_str(role_obj.get("name") or role_obj.get("slug") or role_obj.get("role_id")),
        "provider_id": provider_id,
        "provider_type": provider_type or ("room_shared_capability" if provider_id.startswith("room_provider__") else ""),
        "provider_origin": provider_origin,
        "provider_label": _safe_str(
            binding.get("provider_label")
            or provider_snapshot.get("label")
            or provider_snapshot.get("provider_label")
            or imported_provider.get("label")
            or imported_provider.get("provider_label")
        ),
        "source_room_id": source_room_id,
    }


def _build_role_mcp_runtime_exception_packet(
    *,
    room_id: str,
    question: str,
    role: Dict[str, Any],
    request_args: Dict[str, Any],
    default_mode: str,
    phase: str,
    exc: Exception,
) -> Dict[str, Any]:
    ctx = _fallback_room_mcp_error_context(
        role=role,
        request_args=request_args,
    )

    error_type = type(exc).__name__
    error_message = _safe_str(str(exc))
    error_code = f"role_mcp_runtime_exception:{error_type}"
    message = f"{error_code}:{error_message}" if error_message else error_code

    provider_id = _safe_str(ctx.get("provider_id"))
    provider_type = _safe_str(ctx.get("provider_type"))
    provider_origin = _safe_str(ctx.get("provider_origin"))
    source_room_id = _safe_str(ctx.get("source_room_id"))

    tool_results = [
        {
            "type": "room_mcp_provider_error",
            "role_id": _safe_str(ctx.get("role_id")),
            "role_name": _safe_str(ctx.get("role_name")),
            "provider_id": provider_id,
            "provider_type": provider_type,
            "provider_origin": provider_origin,
            "provider_label": _safe_str(ctx.get("provider_label")),
            "source_room_id": source_room_id,
            "auth_type": "",
            "auth_required": False,
            "auth_configured": False,
            "availability_reason": "",
            "shared_room_config_enabled": False,
            "shared_supervisor_enabled": False,
            "owner_private_scope_exposed": False,
            "error": message,
            "phase": phase,
        },
        {
            "type": "room_mcp_provider_execution",
            "role_id": _safe_str(ctx.get("role_id")),
            "role_name": _safe_str(ctx.get("role_name")),
            "provider_id": provider_id,
            "provider_type": provider_type,
            "provider_origin": provider_origin,
            "provider_label": _safe_str(ctx.get("provider_label")),
            "requested_mode": "mcp",
            "status": "error",
            "auth_type": "",
            "auth_required": False,
            "auth_configured": False,
            "availability_reason": "",
            "consumer_room_id": room_id,
            "source_room_id": source_room_id,
            "actor_user_id": _safe_str(
                _safe_dict(request_args).get("actor_user_id")
                or _safe_dict(request_args).get("user_id")
                or _safe_dict(request_args).get("uid")
            ),
            "shared_room_config_enabled": False,
            "shared_supervisor_enabled": False,
            "reply_mode": "",
            "owner_private_scope_exposed": False,
            "phase": phase,
        },
        {
            "type": "room_mcp_runtime_exception_trace",
            "phase": phase,
            "error_type": error_type,
            "error_message": error_message,
            "error_code": error_code,
            "provider_id": provider_id,
            "provider_type": provider_type,
            "provider_origin": provider_origin,
            "source_room_id": source_room_id,
        },
    ]

    return {
        "content": message,
        "response": message,
        "status": "error",
        "message": message,
        "mode_used": default_mode or "mcp",
        "citations": [],
        "rss_evidence": [],
        "market_evidence": [],
        "evidence_query": question,
        "evidence_tools": [],
        "evidence_result": {
            **_empty_evidence_result(question),
            "provider_id": provider_id,
            "provider_type": provider_type,
            "provider_origin": provider_origin,
            "source_room_id": source_room_id,
            "error": message,
            "phase": phase,
        },
        "tool_calls": [],
        "tool_results": tool_results,
        "model": "",
    }


__all__ = [
    "_tool_result_status",
    "_tool_result_error",
    "_reply_packet_has_provider_error",
    "_is_success_status",
    "_normalize_reply_packet",
    "_extract_provider_fact",
    "_append_role_runtime_fact",
    "_fallback_room_mcp_error_context",
    "_build_role_mcp_runtime_exception_packet",
]
