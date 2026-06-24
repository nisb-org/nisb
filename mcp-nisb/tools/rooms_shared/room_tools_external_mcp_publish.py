from __future__ import annotations

from typing import Any, Dict

from .room_contracts import ensure_request_id, require_safe_id
from .room_mcp_external_publish_service import (
    enable_external_mcp_publish,
    get_external_mcp_publish_status,
    regenerate_external_mcp_publish,
    revoke_external_mcp_publish,
)
from .room_store import (
    can_edit_room_info,
    ensure_room_exists,
    uid_from_ctx_or_basepath,
)
from .room_tool_common import (
    _build_tool_result_item,
    _formal_envelope,
    _missing_args,
    _permission_denied,
)


def _safe_str(value: Any, default: str = "") -> str:
    if value is None:
        return default
    text = str(value).strip()
    return text if text else default


def _safe_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _resolve_basepath(args: Dict[str, Any]) -> str:
    return _safe_str(
        args.get("basepath")
        or args.get("base_path")
        or args.get("basePath")
        or args.get("_base_path")
        or "/data"
    )


def _resolve_actor_uid(args: Dict[str, Any]) -> str:
    basepath = _resolve_basepath(args)
    return _safe_str(
        args.get("actor_uid")
        or args.get("user_id")
        or args.get("uid")
        or uid_from_ctx_or_basepath(basepath, args)
    )


def _load_owner_room_or_error(args: Dict[str, Any], request_id: str) -> tuple[str, Dict[str, Any], str, Dict[str, Any] | None]:
    room_id_raw = args.get("room_id")
    if not _safe_str(room_id_raw):
        return "", {}, "", _missing_args(request_id, "", "missing room_id")

    room_id = require_safe_id("room_id", room_id_raw)
    actor_uid = _resolve_actor_uid(args)
    meta = ensure_room_exists(room_id)

    if not can_edit_room_info(actor_uid, meta):
        return room_id, meta, actor_uid, _permission_denied(request_id, room_id)

    return room_id, meta, actor_uid, None


def _token_once_text(payload: Dict[str, Any]) -> str:
    publish = _safe_dict(payload.get("publish"))
    config = _safe_dict(payload.get("config"))

    lines = [
        payload.get("message") or "external MCP publish updated",
        "",
        "Status:",
        f"- status: {publish.get('status') or ''}",
        f"- provider_id: {publish.get('provider_id') or ''}",
        f"- source_room_id: {publish.get('source_room_id') or ''}",
        f"- expires_at: {publish.get('expires_at') or ''}",
        "",
        "Plaintext token is shown once:",
        _safe_str(payload.get("plaintext_token")),
        "",
        "Generic MCP config:",
        _safe_str(config.get("generic_mcp_config_json")),
        "",
        "LibreChat config:",
        _safe_str(config.get("librechat_config_yaml")),
    ]

    return "\n".join(lines).strip()


def _status_text(payload: Dict[str, Any]) -> str:
    publish = _safe_dict(payload.get("publish") or payload)
    lines = [
        "Room MCP external publish status:",
        f"- status: {publish.get('status') or 'unpublished'}",
        f"- provider_id: {publish.get('provider_id') or ''}",
        f"- source_room_id: {publish.get('source_room_id') or ''}",
        f"- expires_at: {publish.get('expires_at') or ''}",
        f"- revoked_at: {publish.get('revoked_at') or ''}",
        f"- used_count: {publish.get('used_count') or 0}",
        f"- last_used_at: {publish.get('last_used_at') or ''}",
        f"- has_token: {bool(publish.get('has_token'))}",
        "- plaintext_token_available: false",
    ]
    return "\n".join(lines)


def nisb_room_mcp_external_publish_get(args: Dict[str, Any]) -> Dict[str, Any]:
    args = _safe_dict(args).copy()
    request_id = ensure_request_id(args)

    room_id, meta, actor_uid, error = _load_owner_room_or_error(args, request_id)
    if error:
        return error

    status = get_external_mcp_publish_status(room_id)
    text = _status_text(status)

    return _formal_envelope(
        request_id=request_id,
        conv_id=room_id,
        response=text,
        status="success",
        message=text,
        tool_calls=[],
        tool_results=[
            _build_tool_result_item(
                "external_mcp_publish",
                room_id=room_id,
                publish=status,
                plaintext_token_available=False,
            )
        ],
    )


def nisb_room_mcp_external_publish_enable(args: Dict[str, Any]) -> Dict[str, Any]:
    args = _safe_dict(args).copy()
    request_id = ensure_request_id(args)

    room_id, meta, actor_uid, error = _load_owner_room_or_error(args, request_id)
    if error:
        return error

    payload = enable_external_mcp_publish(
        room_id,
        actor_uid=actor_uid,
        request_id=request_id,
        args=args,
    )

    text = _token_once_text(payload) if payload.get("plaintext_token") else _status_text(payload)

    return _formal_envelope(
        request_id=request_id,
        conv_id=room_id,
        response=text,
        status="success",
        message=text,
        tool_calls=[],
        tool_results=[
            _build_tool_result_item(
                "external_mcp_publish",
                room_id=room_id,
                publish=payload.get("publish"),
                config=payload.get("config"),
                plaintext_token=payload.get("plaintext_token"),
                plaintext_token_available=bool(payload.get("plaintext_token")),
                already_active=bool(payload.get("already_active")),
            )
        ],
    )


def nisb_room_mcp_external_publish_revoke(args: Dict[str, Any]) -> Dict[str, Any]:
    args = _safe_dict(args).copy()
    request_id = ensure_request_id(args)

    room_id, meta, actor_uid, error = _load_owner_room_or_error(args, request_id)
    if error:
        return error

    payload = revoke_external_mcp_publish(
        room_id,
        actor_uid=actor_uid,
        request_id=request_id,
    )
    text = _status_text(payload)

    return _formal_envelope(
        request_id=request_id,
        conv_id=room_id,
        response=text,
        status="success",
        message=text,
        tool_calls=[],
        tool_results=[
            _build_tool_result_item(
                "external_mcp_publish",
                room_id=room_id,
                publish=payload.get("publish"),
                already_revoked=bool(payload.get("already_revoked")),
                plaintext_token_available=False,
            )
        ],
    )


def nisb_room_mcp_external_publish_regenerate(args: Dict[str, Any]) -> Dict[str, Any]:
    args = _safe_dict(args).copy()
    request_id = ensure_request_id(args)

    room_id, meta, actor_uid, error = _load_owner_room_or_error(args, request_id)
    if error:
        return error

    payload = regenerate_external_mcp_publish(
        room_id,
        actor_uid=actor_uid,
        request_id=request_id,
        args=args,
    )
    text = _token_once_text(payload)

    return _formal_envelope(
        request_id=request_id,
        conv_id=room_id,
        response=text,
        status="success",
        message=text,
        tool_calls=[],
        tool_results=[
            _build_tool_result_item(
                "external_mcp_publish",
                room_id=room_id,
                publish=payload.get("publish"),
                config=payload.get("config"),
                plaintext_token=payload.get("plaintext_token"),
                plaintext_token_available=True,
            )
        ],
    )


__all__ = [
    "nisb_room_mcp_external_publish_get",
    "nisb_room_mcp_external_publish_enable",
    "nisb_room_mcp_external_publish_revoke",
    "nisb_room_mcp_external_publish_regenerate",
]
