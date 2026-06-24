from __future__ import annotations

from typing import Any, Dict

from .room_contracts import ensure_request_id, require_safe_id
from .room_mcp_provider_contract import normalize_room_role_mcp_contract
from .room_roles import create_role, delete_role, list_roles, update_role
from .room_store import (
    can_manage_room_roles,
    ensure_room_exists,
    get_basepath,
    is_participant,
    uid_from_ctx_or_basepath,
)
from .room_tool_common import _build_tool_result_item, _formal_envelope, _permission_denied
from .room_tools_mcp_providers import (
    nisb_room_mcp_provider_call,
    nisb_room_mcp_provider_list,
    nisb_room_mcp_provider_share_ref_resolve,
    nisb_room_mcp_share_ref_issue,
)


def _safe_dict(v: Any) -> Dict[str, Any]:
    return v if isinstance(v, dict) else {}


def _safe_str(v: Any, default: str = "") -> str:
    if v is None:
        return default
    s = str(v).strip()
    return s if s else default


def _normalize_role_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(payload or {})
    role_obj = dict(payload or {})
    tool_policy = _safe_dict(role_obj.get("tool_policy"))
    contract = normalize_room_role_mcp_contract(role_obj, tool_policy)

    out["mcp_binding"] = _safe_dict(contract.get("mcp_binding"))
    out["mcp_provider_ids"] = contract.get("mcp_provider_ids") or []
    out["mcp_provider_snapshot"] = _safe_dict(contract.get("mcp_provider_snapshot"))
    out["mcp_share_ref"] = _safe_str(contract.get("mcp_share_ref"))

    return out


def nisb_room_role_list(args: Dict[str, Any]) -> Dict[str, Any]:
    basepath = get_basepath(args)
    uid = uid_from_ctx_or_basepath(basepath, args)
    rid = ensure_request_id(args)

    room_id = require_safe_id("room_id", args.get("room_id"))
    meta = ensure_room_exists(room_id)
    if meta and not is_participant(uid, meta):
        return _permission_denied(rid, room_id)

    roles = list_roles(room_id)
    return _formal_envelope(
        request_id=rid,
        conv_id=room_id,
        response=f"Loaded {len(roles)} roles.",
        status="success",
        message="room roles loaded",
        tool_calls=[],
        tool_results=[_build_tool_result_item("room_roles", room_id=room_id, roles=roles)],
    )


def nisb_room_role_create(args: Dict[str, Any]) -> Dict[str, Any]:
    basepath = get_basepath(args)
    uid = uid_from_ctx_or_basepath(basepath, args)
    rid = ensure_request_id(args)

    room_id = require_safe_id("room_id", args.get("room_id"))
    meta = ensure_room_exists(room_id)
    if meta and not can_manage_room_roles(uid, meta):
        return _permission_denied(rid, room_id)

    payload = _normalize_role_payload(args)
    role = create_role(room_id=room_id, payload=payload, actor_uid=uid, request_id=rid)
    return _formal_envelope(
        request_id=rid,
        conv_id=room_id,
        response=f"Role created: {role.get('name') or role.get('role_id') or 'role'}.",
        status="success",
        message="room role created",
        tool_calls=[],
        tool_results=[_build_tool_result_item("room_role", room_id=room_id, role=role)],
    )


def nisb_room_role_update(args: Dict[str, Any]) -> Dict[str, Any]:
    basepath = get_basepath(args)
    uid = uid_from_ctx_or_basepath(basepath, args)
    rid = ensure_request_id(args)

    room_id = require_safe_id("room_id", args.get("room_id"))
    role_id = require_safe_id("role_id", args.get("role_id"))
    meta = ensure_room_exists(room_id)
    if meta and not can_manage_room_roles(uid, meta):
        return _permission_denied(rid, room_id)

    payload = _normalize_role_payload(args)
    role = update_role(room_id=room_id, role_id=role_id, payload=payload, actor_uid=uid, request_id=rid)
    return _formal_envelope(
        request_id=rid,
        conv_id=room_id,
        response=f"Role updated: {role.get('name') or role_id}.",
        status="success",
        message="room role updated",
        tool_calls=[],
        tool_results=[_build_tool_result_item("room_role", room_id=room_id, role=role)],
    )


def nisb_room_role_delete(args: Dict[str, Any]) -> Dict[str, Any]:
    basepath = get_basepath(args)
    uid = uid_from_ctx_or_basepath(basepath, args)
    rid = ensure_request_id(args)

    room_id = require_safe_id("room_id", args.get("room_id"))
    role_id = require_safe_id("role_id", args.get("role_id"))
    meta = ensure_room_exists(room_id)
    if meta and not can_manage_room_roles(uid, meta):
        return _permission_denied(rid, room_id)

    role = delete_role(room_id=room_id, role_id=role_id, actor_uid=uid, request_id=rid)
    return _formal_envelope(
        request_id=rid,
        conv_id=room_id,
        response=f"Role deleted: {role.get('name') or role_id}.",
        status="success",
        message="room role deleted",
        tool_calls=[],
        tool_results=[_build_tool_result_item("room_role", room_id=room_id, role=role)],
    )


__all__ = [
    "nisb_room_role_list",
    "nisb_room_role_create",
    "nisb_room_role_update",
    "nisb_room_role_delete",
    "nisb_room_mcp_provider_list",
    "nisb_room_mcp_share_ref_issue",
    "nisb_room_mcp_provider_share_ref_resolve",
    "nisb_room_mcp_provider_call",
]
