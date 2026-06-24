from __future__ import annotations

from typing import Any, Dict

from .room_mcp_share_artifact import (
    ROOM_MCP_SHARE_REF_VERSION,
    ROOM_SHARED_PROVIDER_ORIGIN_IMPORTED,
    ROOM_SHARED_PROVIDER_TYPE,
    _default_auth_state,
    _default_availability,
    _default_boundary_hint,
    _default_params_defaults,
    _default_params_schema,
    _default_tool_template,
    _normalize_boundary_hint,
    _normalize_provider_id,
    _normalize_room_source,
    _safe_bool,
    _safe_dict,
    _safe_json_dict,
    _safe_list,
    _safe_str,
    encode_room_shared_mcp_share_ref,
    parse_room_shared_mcp_share_ref,
)


def _build_imported_room_provider_base(source_obj: Dict[str, Any], share_ref_text: str = "") -> Dict[str, Any]:
    room_source = _normalize_room_source(
        source_obj.get("room_source") or source_obj.get("source_room")
    )
    room_id = _safe_str(room_source.get("room_id"))
    if not room_id:
        return {}

    provider_id = _normalize_provider_id(
        source_obj.get("provider_id") or f"room_provider__{room_id}"
    )
    if not provider_id:
        return {}

    tool_templates = _safe_list(source_obj.get("tool_templates"))
    if not tool_templates:
        tool_templates = [_default_tool_template()]

    params_schema = _safe_dict(source_obj.get("params_schema")) or _default_params_schema()
    params_defaults = _safe_dict(source_obj.get("params_defaults")) or _default_params_defaults()
    auth_state = _safe_dict(source_obj.get("auth_state")) or _default_auth_state()
    availability = _safe_dict(source_obj.get("availability")) or _default_availability()
    boundary_hint = _normalize_boundary_hint(source_obj.get("boundary_hint") or _default_boundary_hint())

    label = _safe_str(
        source_obj.get("provider_label")
        or source_obj.get("label")
        or room_id
        or "Imported Room MCP Provider"
    )

    return {
        "provider_id": provider_id,
        "provider_type": _safe_str(source_obj.get("provider_type"), ROOM_SHARED_PROVIDER_TYPE),
        "provider_origin": ROOM_SHARED_PROVIDER_ORIGIN_IMPORTED,
        "descriptor_version": _safe_str(
            source_obj.get("descriptor_version") or source_obj.get("version"),
            ROOM_MCP_SHARE_REF_VERSION,
        ),
        "label": label,
        "description": _safe_str(source_obj.get("description")),
        "tool_templates": tool_templates,
        "params_schema": params_schema,
        "params_defaults": params_defaults,
        "auth_state": auth_state,
        "availability": availability,
        "boundary_hint": boundary_hint,
        "capabilities": {
            "web": False,
            "mcp": True,
            "code": False,
            "fs_read": False,
            "fs_write": False,
        },
        "room_source": room_source,
        "share_ref": share_ref_text,
    }


def build_imported_room_mcp_provider_contract(source: Any) -> Dict[str, Any]:
    raw = _safe_dict(source)
    if not raw:
        raw = _safe_json_dict(source)

    share_ref_value = (
        raw.get("share_ref")
        or raw.get("shareRef")
        or raw.get("mcp_share_ref")
        or source
    )
    share_ref_obj = parse_room_shared_mcp_share_ref(share_ref_value)

    provider_snapshot = _safe_dict(
        raw.get("provider_snapshot")
        or raw.get("providerSnapshot")
        or raw.get("mcp_provider_snapshot")
    )
    imported_provider = _safe_dict(
        raw.get("imported_provider")
        or raw.get("importedProvider")
    )

    source_obj = {}
    share_ref_text = ""

    if share_ref_obj:
        source_obj = share_ref_obj
        if isinstance(share_ref_value, str):
            share_ref_text = _safe_str(share_ref_value)
        else:
            share_ref_text = encode_room_shared_mcp_share_ref(share_ref_obj)
    elif provider_snapshot:
        source_obj = provider_snapshot
        share_ref_text = _safe_str(
            provider_snapshot.get("share_ref") or provider_snapshot.get("mcp_share_ref")
        )
    elif imported_provider:
        source_obj = imported_provider
        share_ref_text = _safe_str(imported_provider.get("share_ref"))
    elif raw.get("provider_type") == ROOM_SHARED_PROVIDER_TYPE and (
        _safe_dict(raw.get("room_source")) or _safe_dict(raw.get("source_room"))
    ):
        source_obj = raw
        share_ref_text = _safe_str(raw.get("share_ref"))

    provider = _build_imported_room_provider_base(source_obj, share_ref_text=share_ref_text)
    if not provider:
        return {}

    provider_type = _safe_str(provider.get("provider_type"))
    if provider_type != ROOM_SHARED_PROVIDER_TYPE:
        return {}

    room_source = _safe_dict(provider.get("room_source"))
    boundary = _safe_dict(room_source.get("shared_boundary"))
    if _safe_bool(boundary.get("owner_private_scope_exposed"), False):
        return {}

    return provider


__all__ = [
    "build_imported_room_mcp_provider_contract",
]
