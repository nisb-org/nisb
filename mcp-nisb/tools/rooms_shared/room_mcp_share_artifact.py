from __future__ import annotations

import base64
import json
from typing import Any, Dict, List

from tools.i18n.backend_i18n import (
    normalize_backend_locale,
    pick_i18n,
    text_i18n,
)

ROOM_SHARED_PROVIDER_TYPE = "room_shared_capability"
ROOM_SHARED_PROVIDER_ORIGIN_LOCAL = "local_registry"
ROOM_SHARED_PROVIDER_ORIGIN_IMPORTED = "imported_remote"

ROOM_MCP_SHARE_REF_KIND = "room_mcp_share_ref"
ROOM_MCP_SHARE_REF_VERSION = "v1"
ROOM_MCP_SHARE_REF_PREFIX = "room-mcp-share-ref://"


def _safe_str(v: Any, default: str = "") -> str:
    if v is None:
        return default
    s = str(v).strip()
    return s if s else default


def _safe_bool(v: Any, default: bool = False) -> bool:
    if isinstance(v, bool):
        return v
    if v is None:
        return default
    if isinstance(v, (int, float)):
        return bool(v)
    s = str(v).strip().lower()
    if not s:
        return default
    return s in {"1", "true", "yes", "on", "y"}


def _safe_dict(v: Any) -> Dict[str, Any]:
    return dict(v) if isinstance(v, dict) else {}


def _safe_list(v: Any) -> List[Any]:
    return list(v) if isinstance(v, list) else []


def _safe_json_dict(v: Any) -> Dict[str, Any]:
    if isinstance(v, dict):
        return dict(v)
    if not isinstance(v, str):
        return {}
    s = v.strip()
    if not s:
        return {}
    try:
        row = json.loads(s)
    except Exception:
        return {}
    return dict(row) if isinstance(row, dict) else {}


def _normalize_provider_id(value: Any) -> str:
    return _safe_str(value).lower()


def _message_i18n(row: Dict[str, Any], fallback: Dict[str, Any]) -> Dict[str, str]:
    src = _safe_dict(row.get("message_i18n"))
    if src:
        return {str(k): _safe_str(v) for k, v in src.items()}
    fallback_src = _safe_dict(fallback.get("message_i18n"))
    if fallback_src:
        return {str(k): _safe_str(v) for k, v in fallback_src.items()}
    return {}


def _title_i18n(row: Dict[str, Any], fallback: Dict[str, Any]) -> Dict[str, str]:
    src = _safe_dict(row.get("title_i18n"))
    if src:
        return {str(k): _safe_str(v) for k, v in src.items()}
    fallback_src = _safe_dict(fallback.get("title_i18n"))
    if fallback_src:
        return {str(k): _safe_str(v) for k, v in fallback_src.items()}
    return {}


def _label_i18n(row: Dict[str, Any], fallback: Dict[str, Any]) -> Dict[str, str]:
    src = _safe_dict(row.get("label_i18n"))
    if src:
        return {str(k): _safe_str(v) for k, v in src.items()}
    fallback_src = _safe_dict(fallback.get("label_i18n"))
    if fallback_src:
        return {str(k): _safe_str(v) for k, v in fallback_src.items()}
    return {}


def _description_i18n(row: Dict[str, Any], fallback: Dict[str, Any]) -> Dict[str, str]:
    src = _safe_dict(row.get("description_i18n"))
    if src:
        return {str(k): _safe_str(v) for k, v in src.items()}
    fallback_src = _safe_dict(fallback.get("description_i18n"))
    if fallback_src:
        return {str(k): _safe_str(v) for k, v in fallback_src.items()}
    return {}


def _resolve_message(row: Dict[str, Any], fallback: Dict[str, Any], locale: Any = None) -> str:
    i18n = _message_i18n(row, fallback)
    if i18n:
        return pick_i18n(i18n, locale)
    explicit = _safe_str(row.get("message"))
    if explicit:
        return explicit
    return _safe_str(fallback.get("message"))


def _resolve_label(row: Dict[str, Any], fallback: Dict[str, Any], locale: Any = None) -> str:
    i18n = _label_i18n(row, fallback)
    if i18n:
        return pick_i18n(i18n, locale)
    explicit = _safe_str(row.get("label"))
    if explicit:
        return explicit
    return _safe_str(fallback.get("label"))


def _resolve_description(row: Dict[str, Any], fallback: Dict[str, Any], locale: Any = None) -> str:
    i18n = _description_i18n(row, fallback)
    if i18n:
        return pick_i18n(i18n, locale)
    explicit = _safe_str(row.get("description"))
    if explicit:
        return explicit
    return _safe_str(fallback.get("description"))


def _default_tool_template(locale: Any = None) -> Dict[str, Any]:
    label_i18n = text_i18n("Room shared answer", "房间共享回答")
    description_i18n = text_i18n(
        "Send a shared answer request to this room using the owner room settings.",
        "向该 room 发起一次按 owner room settings 执行的共享回答请求。",
    )
    return {
        "tool_name": "ask_room_shared_reply",
        "label": pick_i18n(label_i18n, locale),
        "label_i18n": label_i18n,
        "description": pick_i18n(description_i18n, locale),
        "description_i18n": description_i18n,
        "requested_mode": "mcp",
    }


def _default_params_schema(locale: Any = None) -> Dict[str, Any]:
    title_i18n = text_i18n("Question", "问题")
    return {
        "type": "object",
        "properties": {
            "question": {
                "type": "string",
                "title": pick_i18n(title_i18n, locale),
                "title_i18n": title_i18n,
            }
        },
        "required": ["question"],
    }


def _default_params_defaults() -> Dict[str, Any]:
    return {
        "question": "{{user_query}}",
    }


def _default_auth_state(locale: Any = None) -> Dict[str, Any]:
    message_i18n = text_i18n(
        "The server decides access based on the source room publishing state, sharing boundary, and permissions.",
        "由服务端按 source room 发布状态、分享边界与访问权限裁决。",
    )
    return {
        "type": "room_server_gate",
        "required": False,
        "configured": True,
        "message": pick_i18n(message_i18n, locale),
        "message_i18n": message_i18n,
    }


def _default_availability(locale: Any = None) -> Dict[str, Any]:
    message_i18n = text_i18n(
        "Provider can be resolved. Final executability is still decided by the source room server.",
        "provider 可解析；最终可执行性仍由 source room 服务端裁决。",
    )
    return {
        "available": True,
        "reason": "",
        "message": pick_i18n(message_i18n, locale),
        "message_i18n": message_i18n,
    }


def _default_boundary_hint(locale: Any = None) -> Dict[str, Any]:
    message_i18n = text_i18n(
        "This exposes a room-configured shared capability and does not include the owner's ambient private scope.",
        "暴露的是 room-configured shared capability，不包含 owner ambient private scope。",
    )
    return {
        "supports_workspace_context": False,
        "supports_focus_root": False,
        "default_inherit_workspace_context": False,
        "default_inherit_focus_root": False,
        "message": pick_i18n(message_i18n, locale),
        "message_i18n": message_i18n,
    }


def _normalize_auth_state(value: Any, locale: Any = None) -> Dict[str, Any]:
    row = _safe_dict(value)
    out = _default_auth_state(locale)

    if not row:
        return out

    out["type"] = _safe_str(row.get("type"), out["type"])
    out["required"] = _safe_bool(row.get("required"), out["required"])
    out["configured"] = _safe_bool(row.get("configured"), out["configured"])
    out["config_key"] = _safe_str(row.get("config_key"), _safe_str(out.get("config_key")))
    out["auth_url"] = _safe_str(row.get("auth_url"), _safe_str(out.get("auth_url")))
    out["scopes"] = _safe_list(row.get("scopes")) or _safe_list(out.get("scopes"))

    i18n = _message_i18n(row, out)
    if i18n:
        out["message_i18n"] = i18n
        out["message"] = pick_i18n(i18n, locale)
    else:
        explicit = _safe_str(row.get("message"))
        if explicit:
            out["message"] = explicit

    return out


def _normalize_availability(value: Any, locale: Any = None) -> Dict[str, Any]:
    row = _safe_dict(value)
    out = _default_availability(locale)

    if not row:
        return out

    out["available"] = _safe_bool(row.get("available"), out["available"])
    out["reason"] = _safe_str(row.get("reason"), out["reason"])

    i18n = _message_i18n(row, out)
    if i18n:
        out["message_i18n"] = i18n
        out["message"] = pick_i18n(i18n, locale)
    else:
        explicit = _safe_str(row.get("message"))
        if explicit:
            out["message"] = explicit

    return out


def _normalize_boundary_hint(value: Any, locale: Any = None) -> Dict[str, Any]:
    row = _safe_dict(value)
    out = _default_boundary_hint(locale)

    if not row:
        return out

    out["supports_workspace_context"] = _safe_bool(
        row.get("supports_workspace_context"),
        out["supports_workspace_context"],
    )
    out["supports_focus_root"] = _safe_bool(
        row.get("supports_focus_root"),
        out["supports_focus_root"],
    )
    out["default_inherit_workspace_context"] = _safe_bool(
        row.get("default_inherit_workspace_context"),
        out["default_inherit_workspace_context"],
    )
    out["default_inherit_focus_root"] = _safe_bool(
        row.get("default_inherit_focus_root"),
        out["default_inherit_focus_root"],
    )

    i18n = _message_i18n(row, out)
    if i18n:
        out["message_i18n"] = i18n
        out["message"] = pick_i18n(i18n, locale)
    else:
        explicit = _safe_str(row.get("message"))
        if explicit:
            out["message"] = explicit

    return out


def _normalize_tool_template(value: Any, locale: Any = None) -> Dict[str, Any]:
    row = _safe_dict(value)
    out = _default_tool_template(locale)

    if not row:
        return out

    out["tool_name"] = _safe_str(row.get("tool_name") or row.get("name"), out["tool_name"])
    out["requested_mode"] = _safe_str(row.get("requested_mode"), out["requested_mode"])

    label_i18n = _label_i18n(row, out)
    if label_i18n:
        out["label_i18n"] = label_i18n
        out["label"] = pick_i18n(label_i18n, locale)
    else:
        explicit_label = _safe_str(row.get("label"))
        if explicit_label:
            out["label"] = explicit_label

    description_i18n = _description_i18n(row, out)
    if description_i18n:
        out["description_i18n"] = description_i18n
        out["description"] = pick_i18n(description_i18n, locale)
    else:
        explicit_description = _safe_str(row.get("description"))
        if explicit_description:
            out["description"] = explicit_description

    return out


def _normalize_params_schema(value: Any, locale: Any = None) -> Dict[str, Any]:
    row = _safe_dict(value)
    out = _default_params_schema(locale)

    if not row:
        return out

    normalized = dict(row)
    properties = _safe_dict(normalized.get("properties"))
    question = _safe_dict(properties.get("question"))

    if question:
        fallback_question = _safe_dict(
            _safe_dict(out.get("properties")).get("question")
        )
        title_i18n = _title_i18n(question, fallback_question)
        if title_i18n:
            question["title_i18n"] = title_i18n
            question["title"] = pick_i18n(title_i18n, locale)
        elif _safe_str(question.get("title")):
            question["title"] = _safe_str(question.get("title"))

        properties["question"] = question
        normalized["properties"] = properties

    return normalized


def _normalize_room_source(raw: Any) -> Dict[str, Any]:
    src = _safe_dict(raw)
    room_id = _safe_str(src.get("room_id"))
    owner_user_id = _safe_str(src.get("owner_user_id"))
    reply_mode = _safe_str(src.get("reply_mode"))
    default_reply_role_id = _safe_str(src.get("default_reply_role_id"))

    active_roles: List[str] = []
    for item in _safe_list(src.get("active_roles")):
        sid = _safe_str(item)
        if sid and sid not in active_roles:
            active_roles.append(sid)

    shared_role_ids: List[str] = []
    for item in _safe_list(src.get("shared_role_ids")):
        sid = _safe_str(item)
        if sid and sid not in shared_role_ids:
            shared_role_ids.append(sid)

    enabled_supervisor_skill_ids: List[str] = []
    for item in _safe_list(src.get("enabled_supervisor_skill_ids")):
        sid = _safe_str(item)
        if sid and sid not in enabled_supervisor_skill_ids:
            enabled_supervisor_skill_ids.append(sid)

    boundary = _safe_dict(src.get("shared_boundary"))
    owner_private_scope_exposed = _safe_bool(
        boundary.get("owner_private_scope_exposed"),
        False,
    )

    return {
        "room_id": room_id,
        "owner_user_id": owner_user_id,
        "shared_room_config_enabled": _safe_bool(src.get("shared_room_config_enabled"), False),
        "reply_mode": reply_mode,
        "default_reply_role_id": default_reply_role_id,
        "active_roles": active_roles,
        "shared_role_ids": shared_role_ids,
        "shared_supervisor_enabled": _safe_bool(src.get("shared_supervisor_enabled"), False),
        "enabled_supervisor_skill_ids": enabled_supervisor_skill_ids,
        "supervisor_skill_strategy": _safe_str(src.get("supervisor_skill_strategy")),
        "supervisor_provider": _safe_str(src.get("supervisor_provider")),
        "supervisor_model": _safe_str(src.get("supervisor_model")),
        "supervisor_temperature": src.get("supervisor_temperature"),
        "supervisor_max_tokens": src.get("supervisor_max_tokens"),
        "inherit_workspace_context": _safe_bool(src.get("inherit_workspace_context"), False),
        "inherit_focus_root": _safe_bool(src.get("inherit_focus_root"), False),
        "mcp_overrides": _safe_dict(src.get("mcp_overrides")),
        "shared_boundary": {
            "owner_private_scope_exposed": owner_private_scope_exposed,
        },
    }


def _normalize_share_ref_obj(raw: Any, locale: Any = None) -> Dict[str, Any]:
    selected_locale = normalize_backend_locale(locale)
    obj = _safe_dict(raw)
    if not obj:
        return {}

    kind = _safe_str(obj.get("kind"))
    version = _safe_str(obj.get("version"), ROOM_MCP_SHARE_REF_VERSION)

    room_source = _normalize_room_source(
        obj.get("room_source") or obj.get("source_room")
    )
    room_id = _safe_str(room_source.get("room_id"))

    provider_type = _safe_str(
        obj.get("provider_type"),
        ROOM_SHARED_PROVIDER_TYPE,
    )
    if provider_type != ROOM_SHARED_PROVIDER_TYPE:
        return {}

    if kind and kind != ROOM_MCP_SHARE_REF_KIND:
        return {}

    provider_id = _normalize_provider_id(
        obj.get("provider_id") or (f"room_provider__{room_id}" if room_id else "")
    )
    if not provider_id or not room_id:
        return {}

    tool_name = _safe_str(obj.get("tool_name"), "ask_room_shared_reply")
    requested_mode = _safe_str(obj.get("requested_mode"), "mcp")
    server_tool = _safe_str(obj.get("server_tool"), "nisb_room_mcp_provider_call")

    label_row = {
        "label": obj.get("provider_label") or obj.get("label"),
        "label_i18n": obj.get("provider_label_i18n") or obj.get("label_i18n"),
    }
    description_row = {
        "description": obj.get("description"),
        "description_i18n": obj.get("description_i18n"),
    }

    provider_label_i18n = _safe_dict(
        obj.get("provider_label_i18n") or obj.get("label_i18n")
    )
    description_i18n = _safe_dict(obj.get("description_i18n"))

    out = {
        "version": version,
        "kind": ROOM_MCP_SHARE_REF_KIND,
        "provider_id": provider_id,
        "provider_type": provider_type,
        "provider_label": _resolve_label(label_row, {}, selected_locale),
        "description": _resolve_description(description_row, {}, selected_locale),
        "server_tool": server_tool,
        "tool_name": tool_name,
        "requested_mode": requested_mode,
        "room_source": room_source,
        "boundary_hint": _normalize_boundary_hint(obj.get("boundary_hint"), selected_locale),
        "availability": _normalize_availability(obj.get("availability"), selected_locale),
        "auth_state": _normalize_auth_state(obj.get("auth_state"), selected_locale),
        "issued_at": _safe_str(obj.get("issued_at")),
    }

    if provider_label_i18n:
        out["provider_label_i18n"] = provider_label_i18n
    if description_i18n:
        out["description_i18n"] = description_i18n

    return out


def parse_room_shared_mcp_share_ref(value: Any, locale: Any = None) -> Dict[str, Any]:
    row = _normalize_share_ref_obj(value, locale=locale)
    if row:
        return row

    if not isinstance(value, str):
        return {}

    raw = value.strip()
    if not raw:
        return {}

    if raw.startswith(ROOM_MCP_SHARE_REF_PREFIX):
        payload = raw[len(ROOM_MCP_SHARE_REF_PREFIX):].strip()
        if not payload:
            return {}
        try:
            padding = "=" * (-len(payload) % 4)
            decoded = base64.urlsafe_b64decode(payload + padding).decode("utf-8")
        except Exception:
            return {}
        return _normalize_share_ref_obj(_safe_json_dict(decoded), locale=locale)

    return _normalize_share_ref_obj(_safe_json_dict(raw), locale=locale)


def encode_room_shared_mcp_share_ref(share_ref: Any, locale: Any = None) -> str:
    row = _normalize_share_ref_obj(share_ref, locale=locale)
    if not row:
        return ""
    payload = json.dumps(row, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    token = base64.urlsafe_b64encode(payload).decode("utf-8").rstrip("=")
    return f"{ROOM_MCP_SHARE_REF_PREFIX}{token}"


__all__ = [
    "ROOM_SHARED_PROVIDER_TYPE",
    "ROOM_SHARED_PROVIDER_ORIGIN_LOCAL",
    "ROOM_SHARED_PROVIDER_ORIGIN_IMPORTED",
    "ROOM_MCP_SHARE_REF_KIND",
    "ROOM_MCP_SHARE_REF_VERSION",
    "ROOM_MCP_SHARE_REF_PREFIX",
    "_safe_str",
    "_safe_bool",
    "_safe_dict",
    "_safe_list",
    "_safe_json_dict",
    "_normalize_provider_id",
    "_default_tool_template",
    "_default_params_schema",
    "_default_params_defaults",
    "_default_auth_state",
    "_default_availability",
    "_default_boundary_hint",
    "_normalize_auth_state",
    "_normalize_availability",
    "_normalize_boundary_hint",
    "_normalize_room_source",
    "parse_room_shared_mcp_share_ref",
    "encode_room_shared_mcp_share_ref",
]
