from __future__ import annotations

from typing import Any, Dict, Optional

from .room_role_runtime_common import (
    _max_scope,
    _normalize_fs_read_scope,
    _normalize_fs_write_scope,
    _normalize_positive_int,
    _normalize_requested_mode,
    _normalize_scope,
    _safe_bool,
    _safe_dict,
    _safe_str,
)


def _normalize_binding_time_fields(binding: Dict[str, Any]) -> Dict[str, Any]:
    raw_days = binding.get("time_filter_days") if isinstance(binding, dict) else None
    if raw_days in (None, ""):
        raw_days = binding.get("timeFilterDays") if isinstance(binding, dict) else None

    time_filter_days = _normalize_positive_int(raw_days)
    time_start = _safe_str(
        binding.get("time_start") or binding.get("timeStart")
        if isinstance(binding, dict)
        else ""
    )
    time_end = _safe_str(
        binding.get("time_end") or binding.get("timeEnd")
        if isinstance(binding, dict)
        else ""
    )

    if time_filter_days > 0:
        time_start = ""
        time_end = ""

    return {
        "time_filter_days": time_filter_days if time_filter_days > 0 else "",
        "time_start": time_start,
        "time_end": time_end,
    }


def _with_time_fields(base: Dict[str, Any], time_fields: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(base or {})
    out["time_filter_days"] = time_fields.get("time_filter_days", "")
    out["time_start"] = _safe_str(time_fields.get("time_start"))
    out["time_end"] = _safe_str(time_fields.get("time_end"))
    return out


def _default_tool_policy() -> Dict[str, bool]:
    return {
        "rag": False,
        "web": False,
        "mcp": False,
        "code": False,
        "fs_read": False,
        "fs_write": False,
    }


def _normalize_tool_alias_key(value: Any) -> str:
    s = _safe_str(value).lower()
    if not s:
        return ""
    aliases = {
        "rag": "rag",
        "web": "web",
        "browser": "web",
        "search": "web",
        "mcp": "mcp",
        "tool": "mcp",
        "tools": "mcp",
        "code": "code",
        "code_network": "code",
        "codenetwork": "code",
        "fs_read": "fs_read",
        "fsread": "fs_read",
        "fs-read": "fs_read",
        "filesystem_read": "fs_read",
        "file_read": "fs_read",
        "fileread": "fs_read",
        "fs_write": "fs_write",
        "fswrite": "fs_write",
        "fs-write": "fs_write",
        "filesystem_write": "fs_write",
        "file_write": "fs_write",
        "filewrite": "fs_write",
    }
    return aliases.get(s, "")


def _infer_scope_from_binding(
    *,
    library_id: str,
    doc_id: str,
    group_id: str,
) -> str:
    if library_id and doc_id:
        return "doc"
    if library_id:
        return "library"
    if group_id:
        return "global"
    return "global"


def _sanitize_knowledge_binding(binding: Dict[str, Any]) -> Dict[str, Any]:
    library_id = _safe_str(binding.get("library_id") or binding.get("libraryId"))
    doc_id = _safe_str(binding.get("doc_id") or binding.get("docId"))
    group_id = _safe_str(binding.get("group_id") or binding.get("groupId"))

    store_scope = _normalize_scope(binding.get("store_scope") or binding.get("storeScope"), "global")
    evidence_scope = _normalize_scope(binding.get("evidence_scope") or binding.get("evidenceScope"), "global")
    time_fields = _normalize_binding_time_fields(binding)

    requested_scope = _max_scope(store_scope, evidence_scope)

    if requested_scope == "doc":
        if library_id and doc_id:
            group_id = ""
            return _with_time_fields(
                {
                    "library_id": library_id,
                    "doc_id": doc_id,
                    "group_id": "",
                    "store_scope": store_scope,
                    "evidence_scope": evidence_scope,
                },
                time_fields,
            )

        fallback_scope = _infer_scope_from_binding(
            library_id=library_id,
            doc_id=doc_id,
            group_id=group_id,
        )
        if store_scope == "doc":
            store_scope = fallback_scope
        if evidence_scope == "doc":
            evidence_scope = fallback_scope

    if _max_scope(store_scope, evidence_scope) == "library":
        doc_id = ""
        if not library_id and not group_id:
            if store_scope == "library":
                store_scope = "global"
            if evidence_scope == "library":
                evidence_scope = "global"

        return _with_time_fields(
            {
                "library_id": library_id,
                "doc_id": "",
                "group_id": group_id,
                "store_scope": _normalize_scope(store_scope),
                "evidence_scope": _normalize_scope(evidence_scope),
            },
            time_fields,
        )

    return _with_time_fields(
        {
            "library_id": "",
            "doc_id": "",
            "group_id": group_id,
            "store_scope": _normalize_scope(store_scope),
            "evidence_scope": _normalize_scope(evidence_scope),
        },
        time_fields,
    )


def _extract_role_knowledge_binding(role: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    role_obj = _safe_dict(role)
    candidates = [
        role_obj.get("knowledge_binding"),
        role_obj.get("binding"),
        role_obj.get("bindings"),
    ]

    base: Dict[str, Any] = {}
    for candidate in candidates:
        row = _safe_dict(candidate)
        if row:
            base = dict(row)
            break

    if not _safe_str(base.get("library_id") or base.get("libraryId")):
        if _safe_str(role_obj.get("library_id") or role_obj.get("libraryId")):
            base["library_id"] = role_obj.get("library_id") or role_obj.get("libraryId")

    if not _safe_str(base.get("doc_id") or base.get("docId")):
        if _safe_str(role_obj.get("doc_id") or role_obj.get("docId")):
            base["doc_id"] = role_obj.get("doc_id") or role_obj.get("docId")

    if not _safe_str(base.get("group_id") or base.get("groupId")):
        if _safe_str(role_obj.get("group_id") or role_obj.get("groupId")):
            base["group_id"] = role_obj.get("group_id") or role_obj.get("groupId")

    if not _safe_str(base.get("store_scope") or base.get("storeScope")):
        if _safe_str(role_obj.get("store_scope") or role_obj.get("storeScope")):
            base["store_scope"] = role_obj.get("store_scope") or role_obj.get("storeScope")

    if not _safe_str(base.get("evidence_scope") or base.get("evidenceScope")):
        if _safe_str(role_obj.get("evidence_scope") or role_obj.get("evidenceScope")):
            base["evidence_scope"] = role_obj.get("evidence_scope") or role_obj.get("evidenceScope")

    base_days = _normalize_positive_int(base.get("time_filter_days") or base.get("timeFilterDays"))
    role_days = _normalize_positive_int(role_obj.get("time_filter_days") or role_obj.get("timeFilterDays"))
    if base_days <= 0 and role_days > 0:
        base["time_filter_days"] = role_days

    if not _safe_str(base.get("time_start") or base.get("timeStart")):
        if _safe_str(role_obj.get("time_start") or role_obj.get("timeStart")):
            base["time_start"] = role_obj.get("time_start") or role_obj.get("timeStart")

    if not _safe_str(base.get("time_end") or base.get("timeEnd")):
        if _safe_str(role_obj.get("time_end") or role_obj.get("timeEnd")):
            base["time_end"] = role_obj.get("time_end") or role_obj.get("timeEnd")

    return _sanitize_knowledge_binding(base)


def _extract_role_tool_policy(role: Optional[Dict[str, Any]]) -> Dict[str, bool]:
    role_obj = _safe_dict(role)
    binding = _extract_role_knowledge_binding(role_obj)

    policy = _default_tool_policy()

    raw_policy = _safe_dict(role_obj.get("tool_policy"))
    for key in list(policy.keys()):
        if key in raw_policy:
            policy[key] = _safe_bool(raw_policy.get(key), False)

    legacy_tools = role_obj.get("tools")
    if isinstance(legacy_tools, dict):
        for raw_key, raw_value in legacy_tools.items():
            key = _normalize_tool_alias_key(raw_key)
            if key:
                policy[key] = _safe_bool(raw_value, policy[key])
    elif isinstance(legacy_tools, list):
        for raw_key in legacy_tools:
            key = _normalize_tool_alias_key(raw_key)
            if key:
                policy[key] = True

    if not any(policy.values()):
        if binding.get("library_id") or binding.get("doc_id") or binding.get("group_id"):
            policy["rag"] = True

    if not policy.get("mcp"):
        policy["code"] = False
        policy["fs_read"] = False
        policy["fs_write"] = False

    return policy


def _extract_base_agent_config(request_args: Dict[str, Any]) -> Dict[str, Any]:
    base = _safe_dict(request_args.get("agent_config"))

    planner_model = _safe_str(
        base.get("plannerModel")
        or base.get("planner_model")
        or request_args.get("planner_model"),
        "gpt-4o-mini",
    ) or "gpt-4o-mini"

    planner_provider = _safe_str(
        base.get("plannerProvider")
        or base.get("planner_provider")
        or request_args.get("planner_provider"),
        "openai",
    ) or "openai"

    max_steps_raw = base.get("maxSteps")
    if max_steps_raw is None:
        max_steps_raw = base.get("max_steps")
    if max_steps_raw is None:
        max_steps_raw = request_args.get("max_steps")
    try:
        max_steps = int(max_steps_raw or 3)
    except Exception:
        max_steps = 3
    max_steps = max(0, min(max_steps, 8))

    enabled = _safe_bool(base.get("enabled"), False) or _safe_bool(request_args.get("agent_enabled"), False)
    debug = _safe_bool(base.get("debug"), False) or _safe_bool(request_args.get("agent_debug"), False)
    answer_use_planner = _safe_bool(
        base.get("answerUsePlanner"),
        _safe_bool(request_args.get("answer_use_planner"), False),
    )

    return {
        "enabled": enabled,
        "plannerModel": planner_model,
        "plannerProvider": planner_provider,
        "maxSteps": max_steps,
        "debug": debug,
        "answerUsePlanner": answer_use_planner,
    }


def _resolve_role_rag_mode(
    *,
    request_args: Dict[str, Any],
    tool_policy: Dict[str, bool],
) -> str:
    requested_mode = _normalize_requested_mode(
        request_args.get("requested_mode")
        or request_args.get("rag_mode")
        or request_args.get("mode_used"),
        "off",
    )

    if requested_mode == "web":
        return "web"

    if tool_policy.get("mcp"):
        return "mcp"

    if tool_policy.get("web"):
        return "web"

    if not tool_policy.get("rag"):
        return "off"

    if requested_mode in {"cite", "ground", "auto"}:
        return requested_mode

    return "cite"


def _merge_role_mcp_overrides(
    *,
    base_overrides: Any,
    tool_policy: Dict[str, bool],
    mcp_binding: Dict[str, Any],
) -> Dict[str, Any]:
    merged = dict(_safe_dict(base_overrides))

    mcp_enabled = _safe_bool(tool_policy.get("mcp"), False)
    code_enabled = _safe_bool(tool_policy.get("code"), False) if mcp_enabled else False
    fs_read_enabled = _safe_bool(tool_policy.get("fs_read"), False) if mcp_enabled else False
    fs_write_enabled = _safe_bool(tool_policy.get("fs_write"), False) if mcp_enabled else False
    web_enabled = _safe_bool(tool_policy.get("web"), False)
    provider_id = _safe_str(mcp_binding.get("provider_id")).lower()

    merged["serperEnabled"] = (
        web_enabled
        or provider_id == "serper"
        or _safe_bool(merged.get("serperEnabled"), False)
    )
    merged["codeNetworkEnabled"] = code_enabled if mcp_enabled else False
    merged["fsReadScope"] = (
        _normalize_fs_read_scope(merged.get("fsReadScope") or "user_ro")
        if fs_read_enabled
        else "minimal"
    )
    merged["fsWriteScope"] = (
        _normalize_fs_write_scope(merged.get("fsWriteScope") or "agent_files")
        if fs_write_enabled
        else "none"
    )
    merged["fsDangerousEnabled"] = (
        _safe_bool(merged.get("fsDangerousEnabled"), False)
        if fs_write_enabled and merged["fsWriteScope"] != "none"
        else False
    )
    merged["enabled"] = (
        web_enabled
        or _safe_bool(mcp_binding.get("enabled"), False)
        or _safe_bool(merged.get("serperEnabled"), False)
        or _safe_bool(merged.get("codeNetworkEnabled"), False)
    )

    return merged


__all__ = [
    "_normalize_binding_time_fields",
    "_with_time_fields",
    "_default_tool_policy",
    "_normalize_tool_alias_key",
    "_infer_scope_from_binding",
    "_sanitize_knowledge_binding",
    "_extract_role_knowledge_binding",
    "_extract_role_tool_policy",
    "_extract_base_agent_config",
    "_resolve_role_rag_mode",
    "_merge_role_mcp_overrides",
]
