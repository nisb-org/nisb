from __future__ import annotations


from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


from .room_contracts import (
    as_bool,
    default_tool_policy,
    default_trigger_policy,
    new_id,
    normalize_role_slug,
    require_safe_id,
    utc_iso,
)
from .room_store import (
    append_room_event,
    ensure_room_exists,
    get_room_owner_user_id,
    load_meta,
    load_roles_doc,
    load_state_doc,
    save_meta,
    save_roles_doc,
    save_state_doc,
    touch_room_updated_at,
)


def _normalize_scope(value: Any, default: str = "library") -> str:
    s = str(value or default).strip().lower()
    if s not in ("doc", "library", "global"):
        s = default
    return s



def _safe_text(value: Any, default: str = "") -> str:
    return str(value if value is not None else default).strip()



def _safe_dict(value: Any) -> Dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}



def _safe_positive_int(value: Any) -> int:
    try:
        if value in (None, ""):
            return 0
        return max(0, int(float(value)))
    except Exception:
        return 0



def _parse_iso_datetime(value: Any) -> Optional[datetime]:
    text = _safe_text(value)
    if not text:
        return None
    try:
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        dt = datetime.fromisoformat(text)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None



def _validate_knowledge_binding_time(binding: Dict[str, Any]) -> None:
    kb = binding if isinstance(binding, dict) else {}


    days = _safe_positive_int(kb.get("time_filter_days"))
    time_start = _safe_text(kb.get("time_start"))
    time_end = _safe_text(kb.get("time_end"))


    if days > 0:
        if time_start or time_end:
            raise ValueError("time_filter_days 和 time_start/time_end 不能同时存在")
        return


    if not time_start and not time_end:
        return


    if not time_start or not time_end:
        raise ValueError("区间模式必须同时提供 time_start 和 time_end")


    start_dt = _parse_iso_datetime(time_start)
    end_dt = _parse_iso_datetime(time_end)


    if start_dt is None or end_dt is None:
        raise ValueError("time_start / time_end 必须是合法 ISO 时间")


    if start_dt > end_dt:
        raise ValueError("time_start 不能晚于 time_end")



def _safe_list_of_text(value: Any) -> List[str]:
    if not isinstance(value, list):
        return []
    out: List[str] = []
    seen = set()
    for item in value:
        s = str(item or "").strip()
        if not s or s in seen:
            continue
        seen.add(s)
        out.append(s)
    return out



def _normalize_slug(value: Any, fallback_name: str = "assistant") -> str:
    raw = _safe_text(value)
    if raw:
        slug = normalize_role_slug(raw)
        return slug or normalize_role_slug(fallback_name) or "assistant"
    return normalize_role_slug(fallback_name) or "assistant"



def _slug_set(roles: List[Dict[str, Any]], exclude_role_id: str = "") -> set:
    used = set()
    for role in roles:
        if not isinstance(role, dict):
            continue
        rid = _safe_text(role.get("role_id"))
        if exclude_role_id and rid == exclude_role_id:
            continue
        slug = _safe_text(role.get("slug")).lower()
        if slug:
            used.add(slug)
    return used



def _ensure_unique_slug(base_slug: str, roles: List[Dict[str, Any]], exclude_role_id: str = "") -> str:
    base = _normalize_slug(base_slug, "assistant")
    used = _slug_set(roles, exclude_role_id=exclude_role_id)
    if base not in used:
        return base


    idx = 2
    while True:
        candidate = f"{base}-{idx}"
        if candidate not in used:
            return candidate
        idx += 1



def _pick_explicit_value(
    src: Dict[str, Any],
    payload: Dict[str, Any],
    cur: Dict[str, Any],
    key: str,
    default: Any = "",
) -> Any:
    if isinstance(src, dict) and key in src:
        return src.get(key)
    if key in payload:
        return payload.get(key)
    if isinstance(cur, dict) and key in cur:
        return cur.get(key)
    return default



def _pick_from_dicts(src: Dict[str, Any], cur: Dict[str, Any], key: str, default: Any = "") -> Any:
    if isinstance(src, dict) and key in src:
        return src.get(key)
    if isinstance(cur, dict) and key in cur:
        return cur.get(key)
    return default



def _coerce_knowledge_binding(payload: Dict[str, Any], current: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    src = payload.get("knowledge_binding")
    if not isinstance(src, dict):
        src = {}


    cur = current if isinstance(current, dict) else {}


    library_id = _pick_explicit_value(src, payload, cur, "library_id", "")
    group_id = _pick_explicit_value(src, payload, cur, "group_id", "")
    doc_id = _pick_explicit_value(src, payload, cur, "doc_id", "")
    store_scope = _pick_explicit_value(src, payload, cur, "store_scope", cur.get("store_scope", "library"))
    evidence_scope = _pick_explicit_value(src, payload, cur, "evidence_scope", cur.get("evidence_scope", "library"))


    raw_time_filter_days = _pick_explicit_value(src, payload, cur, "time_filter_days", "")
    time_filter_days = _safe_positive_int(raw_time_filter_days)


    time_start = _safe_text(_pick_explicit_value(src, payload, cur, "time_start", ""))
    time_end = _safe_text(_pick_explicit_value(src, payload, cur, "time_end", ""))


    if time_filter_days > 0:
        time_start = ""
        time_end = ""
    else:
        time_filter_days = ""


    return {
        "library_id": _safe_text(library_id),
        "group_id": _safe_text(group_id),
        "doc_id": _safe_text(doc_id),
        "store_scope": _normalize_scope(store_scope, cur.get("store_scope", "library") or "library"),
        "evidence_scope": _normalize_scope(evidence_scope, cur.get("evidence_scope", "library") or "library"),
        "time_filter_days": time_filter_days,
        "time_start": time_start,
        "time_end": time_end,
    }



def _coerce_tool_policy(payload: Dict[str, Any], current: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    src = payload.get("tool_policy")
    cur = current if isinstance(current, dict) else {}
    base = default_tool_policy()


    for k in list(base.keys()):
        if k in cur:
            base[k] = as_bool(cur.get(k), base[k])


    if isinstance(src, dict):
        for k in list(base.keys()):
            if k in src:
                base[k] = as_bool(src.get(k), base[k])


    return base



def _coerce_trigger_policy(
    payload: Dict[str, Any],
    name: str,
    slug: str,
    current: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    src = payload.get("trigger_policy")
    cur = current if isinstance(current, dict) else {}
    base = default_trigger_policy(name=name, slug=slug)


    if isinstance(cur, dict):
        cur_mentions = _safe_list_of_text(cur.get("mention_names"))
        if cur_mentions:
            base["mention_names"] = cur_mentions
        if "respond_on_plain_message" in cur:
            base["respond_on_plain_message"] = as_bool(cur.get("respond_on_plain_message"), base["respond_on_plain_message"])
        if "participate_in_orchestration" in cur:
            base["participate_in_orchestration"] = as_bool(
                cur.get("participate_in_orchestration"),
                base["participate_in_orchestration"],
            )


    if isinstance(src, dict):
        if "mention_names" in src:
            mentions = _safe_list_of_text(src.get("mention_names"))
            base["mention_names"] = mentions if mentions else default_trigger_policy(name=name, slug=slug)["mention_names"]


        if "respond_on_plain_message" in src:
            base["respond_on_plain_message"] = as_bool(src.get("respond_on_plain_message"), base["respond_on_plain_message"])


        if "participate_in_orchestration" in src:
            base["participate_in_orchestration"] = as_bool(
                src.get("participate_in_orchestration"),
                base["participate_in_orchestration"],
            )


    return base



def _coerce_mcp_binding(payload: Dict[str, Any], current: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    src = payload.get("mcp_binding")
    cur = current if isinstance(current, dict) else {}
    src = src if isinstance(src, dict) else {}


    enabled = src.get("enabled")
    if enabled is None:
        enabled = cur.get("enabled", False)


    provider_id = src.get("provider_id")
    if provider_id in (None, ""):
        provider_id = cur.get("provider_id", "")


    provider_type = src.get("provider_type")
    if provider_type in (None, ""):
        provider_type = cur.get("provider_type", "")


    provider_origin = src.get("provider_origin")
    if provider_origin in (None, ""):
        provider_origin = cur.get("provider_origin", "")


    server_tool = src.get("server_tool")
    if server_tool in (None, ""):
        server_tool = cur.get("server_tool", "nisb_room_mcp_provider_call")


    tool_name = src.get("tool_name")
    if tool_name in (None, ""):
        tool_name = cur.get("tool_name", "")


    requested_mode = src.get("requested_mode")
    if requested_mode in (None, ""):
        requested_mode = cur.get("requested_mode", "mcp")


    params = src.get("params")
    if params is None:
        params = cur.get("params", {})
    params = _safe_dict(params)


    inherit_workspace_context = src.get("inherit_workspace_context")
    if inherit_workspace_context is None:
        inherit_workspace_context = cur.get("inherit_workspace_context", False)


    inherit_focus_root = src.get("inherit_focus_root")
    if inherit_focus_root is None:
        inherit_focus_root = cur.get("inherit_focus_root", False)


    return {
        "enabled": as_bool(enabled, False),
        "provider_id": _safe_text(provider_id),
        "provider_type": _safe_text(provider_type),
        "provider_origin": _safe_text(provider_origin),
        "server_tool": _safe_text(server_tool, "nisb_room_mcp_provider_call"),
        "tool_name": _safe_text(tool_name),
        "requested_mode": _safe_text(requested_mode, "mcp"),
        "params": params,
        "inherit_workspace_context": as_bool(inherit_workspace_context, False),
        "inherit_focus_root": as_bool(inherit_focus_root, False),
    }



def _coerce_mcp_provider_ids(payload: Dict[str, Any], current: Any = None) -> List[str]:
    incoming = payload.get("mcp_provider_ids")
    if isinstance(incoming, list):
        return _safe_list_of_text(incoming)
    return _safe_list_of_text(current)



def _coerce_room_source_snapshot(value: Any, current: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    src = value if isinstance(value, dict) else {}
    cur = current if isinstance(current, dict) else {}

    shared_boundary_src = src.get("shared_boundary") if isinstance(src.get("shared_boundary"), dict) else {}
    shared_boundary_cur = cur.get("shared_boundary") if isinstance(cur.get("shared_boundary"), dict) else {}

    return {
        "room_id": _safe_text(_pick_from_dicts(src, cur, "room_id", "")),
        "owner_user_id": _safe_text(_pick_from_dicts(src, cur, "owner_user_id", "")),
        "shared_room_config_enabled": as_bool(
            _pick_from_dicts(src, cur, "shared_room_config_enabled", False),
            False,
        ),
        "reply_mode": _safe_text(_pick_from_dicts(src, cur, "reply_mode", "")),
        "default_reply_role_id": _safe_text(_pick_from_dicts(src, cur, "default_reply_role_id", "")),
        "active_roles": (
            _safe_list_of_text(src.get("active_roles"))
            if "active_roles" in src
            else _safe_list_of_text(cur.get("active_roles"))
        ),
        "shared_role_ids": (
            _safe_list_of_text(src.get("shared_role_ids"))
            if "shared_role_ids" in src
            else _safe_list_of_text(cur.get("shared_role_ids"))
        ),
        "shared_supervisor_enabled": as_bool(
            _pick_from_dicts(src, cur, "shared_supervisor_enabled", False),
            False,
        ),
        "enabled_supervisor_skill_ids": (
            _safe_list_of_text(src.get("enabled_supervisor_skill_ids"))
            if "enabled_supervisor_skill_ids" in src
            else _safe_list_of_text(cur.get("enabled_supervisor_skill_ids"))
        ),
        "supervisor_skill_strategy": _safe_text(_pick_from_dicts(src, cur, "supervisor_skill_strategy", "")),
        "supervisor_provider": _safe_text(_pick_from_dicts(src, cur, "supervisor_provider", "")),
        "supervisor_model": _safe_text(_pick_from_dicts(src, cur, "supervisor_model", "")),
        "supervisor_temperature": _pick_from_dicts(src, cur, "supervisor_temperature", None),
        "supervisor_max_tokens": _pick_from_dicts(src, cur, "supervisor_max_tokens", None),
        "inherit_workspace_context": as_bool(
            _pick_from_dicts(src, cur, "inherit_workspace_context", False),
            False,
        ),
        "inherit_focus_root": as_bool(
            _pick_from_dicts(src, cur, "inherit_focus_root", False),
            False,
        ),
        "mcp_overrides": _safe_dict(_pick_from_dicts(src, cur, "mcp_overrides", {})),
        "shared_boundary": {
            "owner_private_scope_exposed": as_bool(
                _pick_from_dicts(shared_boundary_src, shared_boundary_cur, "owner_private_scope_exposed", False),
                False,
            ),
        },
    }



def _coerce_boundary_hint(value: Any, current: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    src = value if isinstance(value, dict) else {}
    cur = current if isinstance(current, dict) else {}
    return {
        "supports_workspace_context": as_bool(
            _pick_from_dicts(src, cur, "supports_workspace_context", False),
            False,
        ),
        "supports_focus_root": as_bool(
            _pick_from_dicts(src, cur, "supports_focus_root", False),
            False,
        ),
        "default_inherit_workspace_context": as_bool(
            _pick_from_dicts(src, cur, "default_inherit_workspace_context", False),
            False,
        ),
        "default_inherit_focus_root": as_bool(
            _pick_from_dicts(src, cur, "default_inherit_focus_root", False),
            False,
        ),
        "message": _safe_text(_pick_from_dicts(src, cur, "message", "")),
    }



def _coerce_mcp_provider_snapshot(payload: Dict[str, Any], current: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    src = payload.get("mcp_provider_snapshot")
    src = src if isinstance(src, dict) else {}
    cur = current if isinstance(current, dict) else {}

    share_ref = _safe_text(
        payload.get("mcp_share_ref")
        if "mcp_share_ref" in payload
        else _pick_from_dicts(src, cur, "share_ref", "")
    )

    room_source_value = src.get("room_source")
    if not isinstance(room_source_value, dict):
        room_source_value = src.get("source_room")
    room_source_current = cur.get("room_source")
    if not isinstance(room_source_current, dict):
        room_source_current = cur.get("source_room")

    snapshot = {
        "provider_id": _safe_text(_pick_from_dicts(src, cur, "provider_id", "")),
        "provider_type": _safe_text(_pick_from_dicts(src, cur, "provider_type", "")),
        "provider_origin": _safe_text(_pick_from_dicts(src, cur, "provider_origin", "")),
        "provider_label": _safe_text(_pick_from_dicts(src, cur, "provider_label", "")),
        "description": _safe_text(_pick_from_dicts(src, cur, "description", "")),
        "descriptor_version": _safe_text(_pick_from_dicts(src, cur, "descriptor_version", "")),
        "server_tool": _safe_text(_pick_from_dicts(src, cur, "server_tool", "nisb_room_mcp_provider_call")),
        "tool_name": _safe_text(_pick_from_dicts(src, cur, "tool_name", "")),
        "requested_mode": _safe_text(_pick_from_dicts(src, cur, "requested_mode", "mcp")),
        "params": _safe_dict(_pick_from_dicts(src, cur, "params", {})),
        "params_schema": _safe_dict(_pick_from_dicts(src, cur, "params_schema", {})),
        "params_defaults": _safe_dict(_pick_from_dicts(src, cur, "params_defaults", {})),
        "inherit_workspace_context": as_bool(
            _pick_from_dicts(src, cur, "inherit_workspace_context", False),
            False,
        ),
        "inherit_focus_root": as_bool(
            _pick_from_dicts(src, cur, "inherit_focus_root", False),
            False,
        ),
        "room_source": _coerce_room_source_snapshot(room_source_value, current=room_source_current),
        "boundary_hint": _coerce_boundary_hint(
            _pick_from_dicts(src, cur, "boundary_hint", {}),
            current=_safe_dict(cur.get("boundary_hint")),
        ),
        "availability": _safe_dict(_pick_from_dicts(src, cur, "availability", {})),
        "auth_state": _safe_dict(_pick_from_dicts(src, cur, "auth_state", {})),
        "share_ref": share_ref,
    }

    if not snapshot["provider_id"]:
        return {}

    return snapshot



def _coerce_mcp_share_ref(payload: Dict[str, Any], current: Any = None) -> str:
    if "mcp_share_ref" in payload:
        return _safe_text(payload.get("mcp_share_ref"))
    if isinstance(current, str):
        return _safe_text(current)
    if isinstance(current, dict):
        return _safe_text(current.get("share_ref"))
    return ""



def _room_owner_user_id(room_id: str) -> str:
    meta = ensure_room_exists(room_id)
    return _safe_text(get_room_owner_user_id(meta))



def _normalize_role_owner_user_id(role: Dict[str, Any], room_owner_user_id: str) -> str:
    if not isinstance(role, dict):
        return room_owner_user_id
    return _safe_text(role.get("owner_user_id")) or room_owner_user_id



def _normalize_role_record(role: Dict[str, Any], room_owner_user_id: str) -> Dict[str, Any]:
    if not isinstance(role, dict):
        return {}
    out = dict(role)
    out["owner_user_id"] = _normalize_role_owner_user_id(out, room_owner_user_id)
    out["mcp_binding"] = _coerce_mcp_binding({"mcp_binding": out.get("mcp_binding")}, current=out.get("mcp_binding"))
    out["mcp_provider_ids"] = _coerce_mcp_provider_ids({"mcp_provider_ids": out.get("mcp_provider_ids")}, current=out.get("mcp_provider_ids"))
    out["mcp_provider_snapshot"] = _coerce_mcp_provider_snapshot(
        {
            "mcp_provider_snapshot": out.get("mcp_provider_snapshot"),
            "mcp_share_ref": out.get("mcp_share_ref"),
        },
        current=out.get("mcp_provider_snapshot"),
    )
    out["mcp_share_ref"] = _coerce_mcp_share_ref(
        {"mcp_share_ref": out.get("mcp_share_ref")},
        current=out.get("mcp_provider_snapshot"),
    )

    if isinstance(out.get("mcp_provider_snapshot"), dict) and out["mcp_provider_snapshot"]:
        if not out["mcp_share_ref"]:
            out["mcp_share_ref"] = _safe_text(out["mcp_provider_snapshot"].get("share_ref"))
        elif not _safe_text(out["mcp_provider_snapshot"].get("share_ref")):
            out["mcp_provider_snapshot"]["share_ref"] = out["mcp_share_ref"]

    return out



def _cleanup_room_meta_after_role_delete(room_id: str, role_id: str) -> None:
    meta = load_meta(room_id)
    if not isinstance(meta, dict) or not meta:
        return


    shared_role_ids = meta.get("shared_role_ids")
    if not isinstance(shared_role_ids, list):
        return


    next_shared_role_ids = []
    for item in shared_role_ids:
        s = _safe_text(item)
        if not s or s == role_id:
            continue
        next_shared_role_ids.append(s)


    if next_shared_role_ids == shared_role_ids:
        return


    meta["shared_role_ids"] = next_shared_role_ids
    meta["updated_at"] = utc_iso()
    save_meta(room_id, meta)


def _load_roles(room_id: str) -> List[Dict[str, Any]]:
    room_owner_user_id = _room_owner_user_id(room_id)
    doc = load_roles_doc(room_id)
    roles = doc.get("roles")
    if not isinstance(roles, list):
        return []


    out: List[Dict[str, Any]] = []
    for role in roles:
        if not isinstance(role, dict):
            continue
        out.append(_normalize_role_record(role, room_owner_user_id))
    return out


def _save_roles(room_id: str, roles: List[Dict[str, Any]]) -> None:
    save_roles_doc(room_id, {"roles": roles})
    touch_room_updated_at(room_id)



def _cleanup_room_state_after_role_delete(room_id: str, role_id: str) -> None:
    state = load_state_doc(room_id)
    changed = False


    active_roles = state.get("active_roles")
    if isinstance(active_roles, list):
        next_active = [str(x).strip() for x in active_roles if str(x).strip() and str(x).strip() != role_id]
        if next_active != active_roles:
            state["active_roles"] = next_active
            changed = True


    if _safe_text(state.get("default_reply_role_id")) == role_id:
        fallback_active = state.get("active_roles")
        fallback_role_id = ""
        if isinstance(fallback_active, list) and fallback_active:
            fallback_role_id = _safe_text(fallback_active[0])
        state["default_reply_role_id"] = fallback_role_id
        changed = True


    current_run_roles = state.get("current_run_roles")
    if isinstance(current_run_roles, list):
        next_run_roles = [str(x).strip() for x in current_run_roles if str(x).strip() and str(x).strip() != role_id]
        if next_run_roles != current_run_roles:
            state["current_run_roles"] = next_run_roles
            changed = True


    if _safe_text(state.get("current_delegate_role_id")) == role_id:
        state["current_delegate_role_id"] = ""
        state["current_delegate_role_name"] = ""
        changed = True


    if changed:
        state["updated_at"] = utc_iso()
        save_state_doc(room_id, state)
        touch_room_updated_at(room_id)



def list_roles(room_id: str) -> List[Dict[str, Any]]:
    room_id = require_safe_id("room_id", room_id)
    return _load_roles(room_id)



def get_role_by_id(room_id: str, role_id: str) -> Optional[Dict[str, Any]]:
    room_id = require_safe_id("room_id", room_id)
    role_id = require_safe_id("role_id", role_id)


    for role in _load_roles(room_id):
        if not isinstance(role, dict):
            continue
        if str(role.get("role_id") or "") == role_id:
            return role
    return None



def get_role_by_slug(room_id: str, slug: str) -> Optional[Dict[str, Any]]:
    room_id = require_safe_id("room_id", room_id)
    slug = _safe_text(slug).lower()
    if not slug:
        return None


    for role in _load_roles(room_id):
        if not isinstance(role, dict):
            continue
        if _safe_text(role.get("slug")).lower() == slug:
            return role
    return None


def create_role(room_id: str, payload: Dict[str, Any], actor_uid: str, request_id: str) -> Dict[str, Any]:
    room_id = require_safe_id("room_id", room_id)
    ensure_room_exists(room_id)


    roles = _load_roles(room_id)
    room_owner_user_id = _room_owner_user_id(room_id)


    name = _safe_text(payload.get("name")) or "assistant"
    requested_slug = _safe_text(payload.get("slug"))
    slug = _ensure_unique_slug(requested_slug or name, roles)
    avatar = _safe_text(payload.get("avatar"), "🤖") or "🤖"
    enabled = as_bool(payload.get("enabled"), True)
    system_prompt = _safe_text(payload.get("system_prompt"))


    knowledge_binding = _coerce_knowledge_binding(payload)
    _validate_knowledge_binding_time(knowledge_binding)

    mcp_binding = _coerce_mcp_binding(payload)
    mcp_provider_ids = _coerce_mcp_provider_ids(payload)
    mcp_provider_snapshot = _coerce_mcp_provider_snapshot(payload)
    mcp_share_ref = _coerce_mcp_share_ref(payload, current=mcp_provider_snapshot)

    if mcp_provider_snapshot and mcp_share_ref and not _safe_text(mcp_provider_snapshot.get("share_ref")):
        mcp_provider_snapshot["share_ref"] = mcp_share_ref
    elif mcp_provider_snapshot and not mcp_share_ref:
        mcp_share_ref = _safe_text(mcp_provider_snapshot.get("share_ref"))


    role = {
        "role_id": new_id("role"),
        "owner_user_id": _safe_text(actor_uid) or room_owner_user_id,
        "name": name,
        "slug": slug,
        "avatar": avatar,
        "enabled": enabled,
        "system_prompt": system_prompt,
        "knowledge_binding": knowledge_binding,
        "tool_policy": _coerce_tool_policy(payload),
        "mcp_binding": mcp_binding,
        "mcp_provider_ids": mcp_provider_ids,
        "mcp_provider_snapshot": mcp_provider_snapshot,
        "mcp_share_ref": mcp_share_ref,
        "trigger_policy": _coerce_trigger_policy(payload, name=name, slug=slug),
        "created_at": utc_iso(),
        "updated_at": utc_iso(),
    }


    roles.append(role)
    _save_roles(room_id, roles)


    append_room_event(
        room_id,
        {
            "id": new_id("evt"),
            "ts": utc_iso(),
            "type": "room.role_create",
            "room_id": room_id,
            "request_id": request_id,
            "payload": {
                "sender": _safe_text(actor_uid),
                "role": role,
            },
        },
    )
    return role


def update_role(room_id: str, role_id: str, payload: Dict[str, Any], actor_uid: str, request_id: str) -> Dict[str, Any]:
    room_id = require_safe_id("room_id", room_id)
    role_id = require_safe_id("role_id", role_id)
    ensure_room_exists(room_id)


    roles = _load_roles(room_id)
    room_owner_user_id = _room_owner_user_id(room_id)


    idx = -1
    current: Dict[str, Any] = {}
    for i, role in enumerate(roles):
        if isinstance(role, dict) and str(role.get("role_id") or "") == role_id:
            idx = i
            current = dict(role)
            break


    if idx < 0:
        raise ValueError("role not found")


    name = _safe_text(payload.get("name"), current.get("name") or "assistant") or "assistant"


    if "slug" in payload:
        requested_slug = _safe_text(payload.get("slug")) or name
    else:
        requested_slug = _safe_text(current.get("slug")) or name


    slug = _ensure_unique_slug(requested_slug, roles, exclude_role_id=role_id)
    avatar = _safe_text(payload.get("avatar"), current.get("avatar") or "🤖") or "🤖"
    enabled = as_bool(payload.get("enabled"), as_bool(current.get("enabled"), True))


    if "system_prompt" in payload:
        system_prompt = _safe_text(payload.get("system_prompt"))
    else:
        system_prompt = _safe_text(current.get("system_prompt"))


    knowledge_binding = _coerce_knowledge_binding(payload, current=current.get("knowledge_binding"))
    _validate_knowledge_binding_time(knowledge_binding)

    mcp_binding = _coerce_mcp_binding(payload, current=current.get("mcp_binding"))
    mcp_provider_ids = _coerce_mcp_provider_ids(payload, current=current.get("mcp_provider_ids"))
    mcp_provider_snapshot = _coerce_mcp_provider_snapshot(payload, current=current.get("mcp_provider_snapshot"))
    mcp_share_ref = _coerce_mcp_share_ref(
        payload,
        current=current.get("mcp_share_ref") or current.get("mcp_provider_snapshot"),
    )

    if mcp_provider_snapshot and mcp_share_ref and not _safe_text(mcp_provider_snapshot.get("share_ref")):
        mcp_provider_snapshot["share_ref"] = mcp_share_ref
    elif mcp_provider_snapshot and not mcp_share_ref:
        mcp_share_ref = _safe_text(mcp_provider_snapshot.get("share_ref"))


    merged = {
        **current,
        "role_id": role_id,
        "owner_user_id": _safe_text(current.get("owner_user_id")) or room_owner_user_id,
        "name": name,
        "slug": slug,
        "avatar": avatar,
        "enabled": enabled,
        "system_prompt": system_prompt,
        "knowledge_binding": knowledge_binding,
        "tool_policy": _coerce_tool_policy(payload, current=current.get("tool_policy")),
        "mcp_binding": mcp_binding,
        "mcp_provider_ids": mcp_provider_ids,
        "mcp_provider_snapshot": mcp_provider_snapshot,
        "mcp_share_ref": mcp_share_ref,
        "trigger_policy": _coerce_trigger_policy(
            payload,
            name=name,
            slug=slug,
            current=current.get("trigger_policy"),
        ),
        "created_at": _safe_text(current.get("created_at")) or utc_iso(),
        "updated_at": utc_iso(),
    }


    roles[idx] = merged
    _save_roles(room_id, roles)


    append_room_event(
        room_id,
        {
            "id": new_id("evt"),
            "ts": utc_iso(),
            "type": "room.role_update",
            "room_id": room_id,
            "request_id": request_id,
            "payload": {
                "sender": _safe_text(actor_uid),
                "role_id": role_id,
                "role": merged,
            },
        },
    )
    return merged


def delete_role(room_id: str, role_id: str, actor_uid: str, request_id: str) -> Dict[str, Any]:
    room_id = require_safe_id("room_id", room_id)
    role_id = require_safe_id("role_id", role_id)
    ensure_room_exists(room_id)


    roles = _load_roles(room_id)


    idx = -1
    current: Dict[str, Any] = {}
    for i, role in enumerate(roles):
        if isinstance(role, dict) and str(role.get("role_id") or "") == role_id:
            idx = i
            current = dict(role)
            break


    if idx < 0:
        raise ValueError("role not found")


    removed = roles.pop(idx)
    removed_role = removed if isinstance(removed, dict) else current
    _save_roles(room_id, roles)
    _cleanup_room_state_after_role_delete(room_id, role_id)
    _cleanup_room_meta_after_role_delete(room_id, role_id)


    append_room_event(
        room_id,
        {
            "id": new_id("evt"),
            "ts": utc_iso(),
            "type": "room.role_delete",
            "room_id": room_id,
            "request_id": request_id,
            "payload": {
                "sender": _safe_text(actor_uid),
                "role_id": role_id,
                "role": removed_role,
            },
        },
    )


    return {
        **removed_role,
        "role_id": role_id,
        "deleted": True,
    }


def replace_roles(room_id: str, roles_payload: List[Dict[str, Any]], actor_uid: str, request_id: str) -> List[Dict[str, Any]]:
    room_id = require_safe_id("room_id", room_id)
    ensure_room_exists(room_id)


    if not isinstance(roles_payload, list):
        raise ValueError("roles_payload must be a list")


    room_owner_user_id = _room_owner_user_id(room_id)
    current_roles = _load_roles(room_id)
    current_map: Dict[str, Dict[str, Any]] = {}
    for role in current_roles:
        if not isinstance(role, dict):
            continue
        rid = _safe_text(role.get("role_id"))
        if rid:
            current_map[rid] = dict(role)


    next_roles: List[Dict[str, Any]] = []
    seen_ids = set()
    seen_slugs = set()


    for raw in roles_payload:
        if not isinstance(raw, dict):
            continue


        raw_role_id = _safe_text(raw.get("role_id"))
        if raw_role_id:
            require_safe_id("role_id", raw_role_id)


        current = current_map.get(raw_role_id, {}) if raw_role_id else {}


        role_id = raw_role_id or new_id("role")
        if role_id in seen_ids:
            raise ValueError("duplicate role_id in roles_payload")
        seen_ids.add(role_id)


        name = _safe_text(raw.get("name"), current.get("name") or "assistant") or "assistant"


        if "slug" in raw:
            requested_slug = _safe_text(raw.get("slug")) or name
        else:
            requested_slug = _safe_text(current.get("slug")) or name


        base_slug = _normalize_slug(requested_slug, name)
        slug = base_slug
        if slug in seen_slugs:
            idx = 2
            while f"{base_slug}-{idx}" in seen_slugs:
                idx += 1
            slug = f"{base_slug}-{idx}"
        seen_slugs.add(slug)


        if "system_prompt" in raw:
            system_prompt = _safe_text(raw.get("system_prompt"))
        else:
            system_prompt = _safe_text(current.get("system_prompt"))


        knowledge_binding = _coerce_knowledge_binding(raw, current=current.get("knowledge_binding"))
        _validate_knowledge_binding_time(knowledge_binding)

        mcp_binding = _coerce_mcp_binding(raw, current=current.get("mcp_binding"))
        mcp_provider_ids = _coerce_mcp_provider_ids(raw, current=current.get("mcp_provider_ids"))
        mcp_provider_snapshot = _coerce_mcp_provider_snapshot(raw, current=current.get("mcp_provider_snapshot"))
        mcp_share_ref = _coerce_mcp_share_ref(
            raw,
            current=current.get("mcp_share_ref") or current.get("mcp_provider_snapshot"),
        )

        if mcp_provider_snapshot and mcp_share_ref and not _safe_text(mcp_provider_snapshot.get("share_ref")):
            mcp_provider_snapshot["share_ref"] = mcp_share_ref
        elif mcp_provider_snapshot and not mcp_share_ref:
            mcp_share_ref = _safe_text(mcp_provider_snapshot.get("share_ref"))


        role = {
            "role_id": role_id,
            "owner_user_id": _safe_text(current.get("owner_user_id")) or _safe_text(actor_uid) or room_owner_user_id,
            "name": name,
            "slug": slug,
            "avatar": _safe_text(raw.get("avatar"), current.get("avatar") or "🤖") or "🤖",
            "enabled": as_bool(raw.get("enabled"), as_bool(current.get("enabled"), True)),
            "system_prompt": system_prompt,
            "knowledge_binding": knowledge_binding,
            "tool_policy": _coerce_tool_policy(raw, current=current.get("tool_policy")),
            "mcp_binding": mcp_binding,
            "mcp_provider_ids": mcp_provider_ids,
            "mcp_provider_snapshot": mcp_provider_snapshot,
            "mcp_share_ref": mcp_share_ref,
            "trigger_policy": _coerce_trigger_policy(
                raw,
                name=name,
                slug=slug,
                current=current.get("trigger_policy"),
            ),
            "created_at": _safe_text(current.get("created_at")) or utc_iso(),
            "updated_at": utc_iso(),
        }
        next_roles.append(role)


    _save_roles(room_id, next_roles)


    append_room_event(
        room_id,
        {
            "id": new_id("evt"),
            "ts": utc_iso(),
            "type": "room.role_replace",
            "room_id": room_id,
            "request_id": request_id,
            "payload": {
                "sender": _safe_text(actor_uid),
                "roles": next_roles,
            },
        },
    )


    return next_roles


__all__ = [
    "list_roles",
    "get_role_by_id",
    "get_role_by_slug",
    "create_role",
    "update_role",
    "delete_role",
    "replace_roles",
]

