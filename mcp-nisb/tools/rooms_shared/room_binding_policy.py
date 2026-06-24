from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

from .room_contracts import as_bool, require_safe_id
from .room_roles import get_role_by_id, list_roles
from .room_store import load_state_doc

_ALLOWED_MODE_USED = {"off", "cite", "ground", "web", "auto"}


def _safe_str(v: Any, default: str = "") -> str:
    if v is None:
        return default
    s = str(v).strip()
    return s if s else default


def _safe_list(v: Any) -> List[Any]:
    return v if isinstance(v, list) else []


def _safe_dict(v: Any) -> Dict[str, Any]:
    return v if isinstance(v, dict) else {}


def _normalize_mode_used(value: Any, fallback: str = "off") -> str:
    s = _safe_str(value).lower()
    if s in _ALLOWED_MODE_USED:
        return s
    fb = _safe_str(fallback).lower()
    return fb if fb in _ALLOWED_MODE_USED else "off"


def _normalize_scope(v: Any, default: str = "library") -> str:
    s = _safe_str(v, default).lower()
    if s not in {"doc", "library", "global"}:
        s = default
    return s


def _safe_optional_id(field: str, value: Any) -> str:
    s = _safe_str(value)
    if not s:
        return ""
    return require_safe_id(field, s)


def _normalize_positive_int(value: Any) -> int:
    try:
        if value is None or value == "":
            return 0
        return max(0, int(float(value)))
    except Exception:
        return 0


def _normalize_time_fields(source: Dict[str, Any]) -> Dict[str, Any]:
    row = _safe_dict(source)

    raw_days = row.get("time_filter_days")
    if raw_days in (None, ""):
        raw_days = row.get("timeFilterDays")

    time_filter_days = _normalize_positive_int(raw_days)
    time_start = _safe_str(row.get("time_start") or row.get("timeStart"))
    time_end = _safe_str(row.get("time_end") or row.get("timeEnd"))

    if time_filter_days > 0:
        return {
            "time_filter_days": time_filter_days,
            "time_start": "",
            "time_end": "",
        }

    return {
        "time_filter_days": "",
        "time_start": time_start,
        "time_end": time_end,
    }


def _merge_time_fields(primary: Dict[str, Any], fallback: Dict[str, Any]) -> Dict[str, Any]:
    p = _normalize_time_fields(primary)
    f = _normalize_time_fields(fallback)

    if p.get("time_filter_days"):
        return p

    if p.get("time_start") or p.get("time_end"):
        return p

    return f


def _role_tool_policy(role: Dict[str, Any]) -> Dict[str, Any]:
    tp = role.get("tool_policy")
    if isinstance(tp, dict):
        return tp
    return {}


def _role_kb(role: Dict[str, Any]) -> Dict[str, Any]:
    kb = role.get("knowledge_binding")
    if isinstance(kb, dict):
        return kb
    binding = role.get("binding")
    if isinstance(binding, dict):
        return binding
    bindings = role.get("bindings")
    if isinstance(bindings, dict):
        return bindings
    return {}


def _room_context_binding(args: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "library_id": _safe_optional_id("library_id", args.get("library_id") or args.get("libraryid")),
        "group_id": _safe_optional_id("group_id", args.get("group_id") or args.get("groupid")),
        "doc_id": _safe_optional_id("doc_id", args.get("doc_id") or args.get("docid")),
        "store_scope": _normalize_scope(
            args.get("store_scope") or args.get("qastorescope") or args.get("qa_store_scope") or "library",
            "library",
        ),
        "evidence_scope": _normalize_scope(
            args.get("evidence_scope") or args.get("qaevidencescope") or args.get("qa_evidence_scope") or "library",
            "library",
        ),
        "time_filter_days": _normalize_time_fields(args).get("time_filter_days") or "",
        "time_start": _normalize_time_fields(args).get("time_start") or "",
        "time_end": _normalize_time_fields(args).get("time_end") or "",
    }


def _blank_inherited_binding() -> Dict[str, Any]:
    return {
        "library_id": "",
        "group_id": "",
        "doc_id": "",
        "store_scope": "library",
        "evidence_scope": "library",
        "time_filter_days": "",
        "time_start": "",
        "time_end": "",
    }


def _resolve_effective_binding(role: Dict[str, Any], room_state: Dict[str, Any], args: Dict[str, Any]) -> Dict[str, Any]:
    kb = _role_kb(role)

    # 从请求参数中解析 execution scope
    req = _safe_dict(args)
    effective_execution_scope = _safe_str(req.get("effective_execution_scope")).lower()

    # 仅当房间允许继承，且 execution_scope 不是 room_shared 时，才允许继承房间上下文
    allow_inherited_room_context = (
        as_bool(room_state.get("inherit_workspace_context"), True)
        and effective_execution_scope != "room_shared"
    )

    if allow_inherited_room_context:
        inherited = _room_context_binding(req)
    else:
        inherited = _blank_inherited_binding()

    library_id = _safe_optional_id("library_id", kb.get("library_id") or kb.get("libraryid") or inherited.get("library_id"))
    group_id = _safe_optional_id("group_id", kb.get("group_id") or kb.get("groupid") or inherited.get("group_id"))
    doc_id = _safe_optional_id("doc_id", kb.get("doc_id") or kb.get("docid") or inherited.get("doc_id"))

    store_scope = _normalize_scope(
        kb.get("store_scope") or kb.get("storescope") or inherited.get("store_scope") or "library",
        "library",
    )
    evidence_scope = _normalize_scope(
        kb.get("evidence_scope") or kb.get("evidencescope") or inherited.get("evidence_scope") or store_scope,
        store_scope,
    )

    merged_time = _merge_time_fields(kb, inherited)

    return {
        "library_id": library_id,
        "group_id": group_id,
        "doc_id": doc_id,
        "store_scope": store_scope,
        "evidence_scope": evidence_scope,
        "time_filter_days": merged_time.get("time_filter_days") or "",
        "time_start": merged_time.get("time_start") or "",
        "time_end": merged_time.get("time_end") or "",
    }


def _binding_has_target(binding: Dict[str, Any]) -> bool:
    return bool(
        _safe_str(binding.get("library_id"))
        or _safe_str(binding.get("group_id"))
        or _safe_str(binding.get("doc_id"))
    )


def _normalize_role_text_marker(value: Any) -> str:
    s = _safe_str(value).lower()
    s = re.sub(r"\\s+", "", s)
    return s


def _strip_mention_prefix(text: str, role: Dict[str, Any]) -> str:
    raw = _safe_str(text)
    if not raw:
        return ""

    candidates: List[str] = []
    for key in ("role_id", "slug", "name"):
        val = _safe_str(role.get(key))
        if val:
            candidates.append(val)

    for candidate in candidates:
        escaped = re.escape(candidate)
        patterns = [
            rf"^\\s*@{escaped}\\s*[:,，：]?\\s*",
            rf"^\\s*@{escaped.lower()}\\s*[:,，：]?\\s*",
        ]
        for pattern in patterns:
            new_text = re.sub(pattern, "", raw, flags=re.IGNORECASE)
            if new_text != raw:
                raw = new_text
                break

    return raw.strip() or _safe_str(text).strip()


def _find_role_by_id(roles: List[Dict[str, Any]], role_id: str) -> Optional[Dict[str, Any]]:
    target = _safe_str(role_id)
    if not target:
        return None
    for role in roles:
        if _safe_str(role.get("role_id")) == target:
            return role
    return None


def _enabled_roles(roles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [r for r in roles if r.get("enabled") is not False]


def _get_active_role_objects(room_id: str, state: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    all_roles = _safe_list(list_roles(room_id))
    if not all_roles:
        return []

    state_obj = _safe_dict(state) if isinstance(state, dict) else _safe_dict(load_state_doc(room_id))
    active_role_ids = [str(x).strip() for x in _safe_list(state_obj.get("active_roles")) if str(x).strip()]
    enabled = _enabled_roles(all_roles)

    if active_role_ids:
        picked: List[Dict[str, Any]] = []
        for role_id in active_role_ids:
            role = _find_role_by_id(enabled or all_roles, role_id)
            if role is not None:
                picked.append(role)
        if picked:
            return picked

    if enabled:
        return enabled
    return all_roles


def _resolve_default_reply_role(
    room_id: str,
    content: str = "",
    state: Optional[Dict[str, Any]] = None,
) -> Tuple[Optional[Dict[str, Any]], str]:
    state_obj = _safe_dict(state) if isinstance(state, dict) else _safe_dict(load_state_doc(room_id))
    all_roles = _safe_list(list_roles(room_id))
    enabled = _enabled_roles(all_roles)

    default_role_id = _safe_str(state_obj.get("default_reply_role_id"))
    if default_role_id:
        role = get_role_by_id(room_id, default_role_id)
        if isinstance(role, dict) and role.get("enabled") is not False:
            return role, _safe_str(content)
        role = _find_role_by_id(enabled or all_roles, default_role_id)
        if role is not None:
            return role, _safe_str(content)

    active_roles = _get_active_role_objects(room_id, state_obj)
    if active_roles:
        return active_roles[0], _safe_str(content)

    if enabled:
        return enabled[0], _safe_str(content)

    if all_roles:
        return all_roles[0], _safe_str(content)

    return None, _safe_str(content)


def resolve_role_for_content(
    room_id: str,
    content: str,
    state: Optional[Dict[str, Any]] = None,
) -> Tuple[Optional[Dict[str, Any]], str]:
    roles = _get_active_role_objects(room_id, state)
    text = _safe_str(content)
    if not text or not roles:
        return None, text

    normalized_text = _normalize_role_text_marker(text)

    for role in roles:
        markers: List[str] = []
        for key in ("role_id", "slug", "name"):
            val = _safe_str(role.get(key))
            if val:
                markers.append("@" + _normalize_role_text_marker(val))

        for marker in markers:
            if marker and marker in normalized_text:
                return role, _strip_mention_prefix(text, role)

    return None, text


__all__ = [
    "_binding_has_target",
    "_get_active_role_objects",
    "_normalize_mode_used",
    "_resolve_default_reply_role",
    "_resolve_effective_binding",
    "_role_kb",
    "_role_tool_policy",
    "resolve_role_for_content",
]
