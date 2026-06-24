from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict

from .room_mcp_share_artifact import (
    ROOM_MCP_SHARE_REF_KIND,
    ROOM_MCP_SHARE_REF_VERSION,
    ROOM_SHARED_PROVIDER_ORIGIN_LOCAL,
    ROOM_SHARED_PROVIDER_TYPE,
    _default_boundary_hint,
    _default_params_defaults,
    _default_params_schema,
    _default_tool_template,
    _normalize_boundary_hint,
    _normalize_room_source,
    _safe_bool,
    _safe_dict,
    _safe_list,
    _safe_str,
    encode_room_shared_mcp_share_ref,
)


def _first_tool_template(provider: Dict[str, Any]) -> Dict[str, Any]:
    tools = _safe_list(provider.get("tool_templates"))
    for item in tools:
        row = _safe_dict(item)
        if row:
            return row
    return {}


def build_room_shared_mcp_provider_contract(
    meta: Dict[str, Any],
    state: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    meta_obj = _safe_dict(meta)
    state_obj = _safe_dict(state)

    room_id = _safe_str(meta_obj.get("room_id"))
    title = _safe_str(meta_obj.get("title"))
    provider_name = _safe_str(meta_obj.get("room_mcp_provider_name"))
    provider_summary = _safe_str(meta_obj.get("room_mcp_provider_summary"))
    published = _safe_bool(meta_obj.get("room_mcp_provider_enabled"), False)

    provider_id = f"room_provider__{room_id}" if room_id else ""
    label = provider_name or title or room_id or "Room MCP Provider"

    active_roles = []
    for item in _safe_list(state_obj.get("active_roles")):
        sid = _safe_str(item)
        if sid and sid not in active_roles:
            active_roles.append(sid)

    shared_role_ids = []
    for item in _safe_list(state_obj.get("shared_role_ids") or meta_obj.get("shared_role_ids")):
        sid = _safe_str(item)
        if sid and sid not in shared_role_ids:
            shared_role_ids.append(sid)

    enabled_supervisor_skill_ids = []
    for item in _safe_list(state_obj.get("enabled_supervisor_skill_ids")):
        sid = _safe_str(item)
        if sid and sid not in enabled_supervisor_skill_ids:
            enabled_supervisor_skill_ids.append(sid)

    availability_message = "provider 可用。" if published else "该 room 尚未发布为 MCP provider。"

    room_source = {
        "room_id": room_id,
        "owner_user_id": _safe_str(meta_obj.get("owner_user_id")),
        "shared_room_config_enabled": _safe_bool(
            state_obj.get("shared_room_config_enabled"),
            _safe_bool(meta_obj.get("shared_room_config_enabled"), False),
        ),
        "reply_mode": _safe_str(state_obj.get("reply_mode")),
        "default_reply_role_id": _safe_str(state_obj.get("default_reply_role_id")),
        "active_roles": active_roles,
        "shared_role_ids": shared_role_ids,
        "shared_supervisor_enabled": _safe_bool(
            state_obj.get("shared_supervisor_enabled"),
            _safe_bool(meta_obj.get("shared_supervisor_enabled"), False),
        ),
        "enabled_supervisor_skill_ids": enabled_supervisor_skill_ids,
        "supervisor_skill_strategy": _safe_str(state_obj.get("supervisor_skill_strategy")),
        "supervisor_provider": _safe_str(state_obj.get("supervisor_provider")),
        "supervisor_model": _safe_str(state_obj.get("supervisor_model")),
        "supervisor_temperature": state_obj.get("supervisor_temperature"),
        "supervisor_max_tokens": state_obj.get("supervisor_max_tokens"),
        "inherit_workspace_context": _safe_bool(state_obj.get("inherit_workspace_context"), False),
        "inherit_focus_root": _safe_bool(state_obj.get("inherit_focus_root"), False),
        "mcp_overrides": _safe_dict(state_obj.get("mcp_overrides")),
        "shared_boundary": {
            "owner_private_scope_exposed": False,
        },
    }

    return {
        "provider_id": provider_id,
        "provider_type": ROOM_SHARED_PROVIDER_TYPE,
        "provider_origin": ROOM_SHARED_PROVIDER_ORIGIN_LOCAL,
        "descriptor_version": ROOM_MCP_SHARE_REF_VERSION,
        "label": label,
        "description": provider_summary,
        "tool_templates": [
            _default_tool_template(),
        ],
        "params_schema": _default_params_schema(),
        "params_defaults": _default_params_defaults(),
        "auth_state": {
            "type": "room_server_gate",
            "required": False,
            "configured": True,
            "message": "由服务端按 room provider 发布状态与共享边界裁决。",
        },
        "availability": {
            "available": published,
            "reason": "" if published else "room_provider_not_published",
            "message": availability_message,
        },
        "boundary_hint": _default_boundary_hint(),
        "capabilities": {
            "web": False,
            "mcp": True,
            "code": False,
            "fs_read": False,
            "fs_write": False,
        },
        "room_source": room_source,
    }


def build_room_shared_mcp_share_ref(
    meta: Dict[str, Any],
    state: Dict[str, Any] | None = None,
    *,
    encoded: bool = False,
) -> Any:
    provider = build_room_shared_mcp_provider_contract(meta, state)
    tool_template = _first_tool_template(provider)

    share_ref = {
        "version": ROOM_MCP_SHARE_REF_VERSION,
        "kind": ROOM_MCP_SHARE_REF_KIND,
        "provider_id": _safe_str(provider.get("provider_id")),
        "provider_type": _safe_str(provider.get("provider_type"), ROOM_SHARED_PROVIDER_TYPE),
        "provider_label": _safe_str(provider.get("label")),
        "description": _safe_str(provider.get("description")),
        "server_tool": "nisb_room_mcp_provider_call",
        "tool_name": _safe_str(tool_template.get("tool_name"), "ask_room_shared_reply"),
        "requested_mode": _safe_str(tool_template.get("requested_mode"), "mcp"),
        "room_source": _normalize_room_source(provider.get("room_source")),
        "boundary_hint": _normalize_boundary_hint(provider.get("boundary_hint")),
        "availability": _safe_dict(provider.get("availability")),
        "auth_state": _safe_dict(provider.get("auth_state")),
        "issued_at": datetime.now(timezone.utc).isoformat(),
    }

    return encode_room_shared_mcp_share_ref(share_ref) if encoded else share_ref


__all__ = [
    "build_room_shared_mcp_provider_contract",
    "build_room_shared_mcp_share_ref",
]
