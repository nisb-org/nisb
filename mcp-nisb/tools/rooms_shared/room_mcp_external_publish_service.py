from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from .room_contracts import new_id, require_safe_id, utc_iso
from .room_mcp_external_config_builder import build_external_mcp_config_bundle
from .room_mcp_external_publish_store import (
    load_external_mcp_publish_doc,
    save_external_mcp_publish_doc,
)
from .room_store import (
    append_room_event,
    ensure_room_exists,
    get_room_owner_user_id,
    touch_room_updated_at,
)


ROOM_PROVIDER_PREFIX = "room_provider__"
DEFAULT_ALLOWED_MODE = "mcp"
DEFAULT_RESULT_VIEW = "final_result_only"

DEFAULT_EXPIRES_IN_DAYS = 30.0
MIN_EXPIRES_IN_DAYS = 1.0 / 24.0
MAX_EXPIRES_IN_DAYS = 30.0


def _safe_str(value: Any, default: str = "") -> str:
    if value is None:
        return default
    text = str(value).strip()
    return text if text else default


def _safe_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        if value in (None, ""):
            return default
        return int(float(value))
    except Exception:
        return default


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value in (None, ""):
            return default
        return float(value)
    except Exception:
        return default
    

def _safe_non_negative_int(value: Any, default: int = 0) -> int:
    return max(0, _safe_int(value, default))


def _has_non_empty_arg(args: Dict[str, Any], *names: str) -> bool:
    for name in names:
        if name in args and _safe_str(args.get(name)):
            return True
    return False


def _resolve_max_calls(args: Dict[str, Any], current: Dict[str, Any] | None = None) -> int:
    current = current if isinstance(current, dict) else {}

    if "max_calls" not in args:
        return _safe_non_negative_int(current.get("max_calls"), 0)

    text = _safe_str(args.get("max_calls"))
    if not text:
        return 0

    try:
        n_float = float(text)
    except Exception as ex:
        raise ValueError("max_calls must be a positive integer or empty") from ex

    if not n_float.is_integer():
        raise ValueError("max_calls must be a positive integer or empty")

    n = int(n_float)
    if n <= 0:
        raise ValueError("max_calls must be a positive integer or empty")

    return n


def _parse_iso_datetime(value: Any) -> Optional[datetime]:
    text = _safe_str(value)
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


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _iso_from_dt(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _resolve_expires_at(args: Dict[str, Any], current: Dict[str, Any] | None = None) -> str:
    current = current if isinstance(current, dict) else {}
    now = _now_utc()

    explicit = _safe_str(args.get("expires_at"))
    if explicit:
        parsed = _parse_iso_datetime(explicit)
        if parsed is None:
            raise ValueError("expires_at must be a valid ISO datetime")

        delta = parsed - now
        if delta < timedelta(days=MIN_EXPIRES_IN_DAYS):
            raise ValueError("expires_at must be at least 1 hour in the future")
        if delta > timedelta(days=MAX_EXPIRES_IN_DAYS):
            raise ValueError("expires_at must be no more than 30 days in the future")

        return _iso_from_dt(parsed)

    raw_days = (
        args.get("expires_in_days")
        if "expires_in_days" in args
        else args.get("validity_days")
        if "validity_days" in args
        else args.get("ttl_days")
        if "ttl_days" in args
        else None
    )

    if _safe_str(raw_days):
        days = _safe_float(raw_days, 0.0)
    else:
        days = DEFAULT_EXPIRES_IN_DAYS

    if days < MIN_EXPIRES_IN_DAYS:
        raise ValueError("expires_in_days must be at least 0.0417 days, about 1 hour")
    if days > MAX_EXPIRES_IN_DAYS:
        raise ValueError("expires_in_days must be no more than 30 days")

    return _iso_from_dt(now + timedelta(days=days))


def _external_token() -> str:
    return "nisb_ext_" + secrets.token_urlsafe(32)


def hash_external_mcp_publish_token(token: str) -> str:
    text = _safe_str(token)
    if not text:
        return ""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _provider_id_for_room(room_id: str) -> str:
    return f"{ROOM_PROVIDER_PREFIX}{room_id}"


def _publication_status(row: Dict[str, Any]) -> str:
    if not row or not _safe_str(row.get("token_hash")):
        return "unpublished"

    if _safe_str(row.get("revoked_at")):
        return "revoked"

    expires_at = _safe_str(row.get("expires_at"))
    if expires_at:
        dt = _parse_iso_datetime(expires_at)
        if dt is not None and dt <= _now_utc():
            return "expired"

    return "active"


def _normalize_publish_record(row: Dict[str, Any], *, room_id: str, owner_user_id: str = "") -> Dict[str, Any]:
    src = _safe_dict(row)
    source_room_id = _safe_str(src.get("source_room_id")) or room_id
    provider_id = _safe_str(src.get("provider_id")) or _provider_id_for_room(source_room_id)

    return {
        "publish_id": _safe_str(src.get("publish_id")) or new_id("external_mcp_publish"),
        "token_hash": _safe_str(src.get("token_hash")),
        "source_room_id": source_room_id,
        "provider_id": provider_id,
        "owner_user_id": _safe_str(src.get("owner_user_id")) or owner_user_id,
        "created_at": _safe_str(src.get("created_at")) or utc_iso(),
        "expires_at": _safe_str(src.get("expires_at")),
        "revoked_at": _safe_str(src.get("revoked_at")),
        "allowed_mode": _safe_str(src.get("allowed_mode"), DEFAULT_ALLOWED_MODE) or DEFAULT_ALLOWED_MODE,
        "result_view": DEFAULT_RESULT_VIEW,
        "source_observation_allowed": False,
        "owner_private_scope_exposed": False,
        "max_calls": _safe_non_negative_int(src.get("max_calls"), 0),
        "daily_call_limit": _safe_non_negative_int(src.get("daily_call_limit"), 0),
        "used_count": _safe_non_negative_int(src.get("used_count"), 0),
        "last_used_at": _safe_str(src.get("last_used_at")),
        "client_label": _safe_str(src.get("client_label")),
        "updated_at": _safe_str(src.get("updated_at")) or utc_iso(),
    }


def _public_status(row: Dict[str, Any]) -> Dict[str, Any]:
    src = _safe_dict(row)
    status = _publication_status(src)

    return {
        "publish_id": _safe_str(src.get("publish_id")),
        "source_room_id": _safe_str(src.get("source_room_id")),
        "provider_id": _safe_str(src.get("provider_id")),
        "owner_user_id": _safe_str(src.get("owner_user_id")),
        "created_at": _safe_str(src.get("created_at")),
        "expires_at": _safe_str(src.get("expires_at")),
        "revoked_at": _safe_str(src.get("revoked_at")),
        "allowed_mode": _safe_str(src.get("allowed_mode"), DEFAULT_ALLOWED_MODE),
        "result_view": DEFAULT_RESULT_VIEW,
        "source_observation_allowed": False,
        "owner_private_scope_exposed": False,
        "max_calls": _safe_non_negative_int(src.get("max_calls"), 0),
        "daily_call_limit": _safe_non_negative_int(src.get("daily_call_limit"), 0),
        "used_count": _safe_non_negative_int(src.get("used_count"), 0),
        "last_used_at": _safe_str(src.get("last_used_at")),
        "client_label": _safe_str(src.get("client_label")),
        "updated_at": _safe_str(src.get("updated_at")),
        "status": status,
        "publish_enabled": status == "active",
        "has_token": bool(_safe_str(src.get("token_hash"))),
        "plaintext_token_available": False,
    }


def _append_external_publish_event(
    *,
    room_id: str,
    request_id: str,
    actor_uid: str,
    event_type: str,
    publish: Dict[str, Any],
    extra: Dict[str, Any] | None = None,
) -> None:
    payload = {
        "sender": _safe_str(actor_uid),
        "publish_id": _safe_str(publish.get("publish_id")),
        "source_room_id": _safe_str(publish.get("source_room_id")),
        "provider_id": _safe_str(publish.get("provider_id")),
        "status": _publication_status(publish),
        "expires_at": _safe_str(publish.get("expires_at")),
        "revoked_at": _safe_str(publish.get("revoked_at")),
        "client_label": _safe_str(publish.get("client_label")),
    }

    if isinstance(extra, dict):
        payload.update(extra)

    append_room_event(
        room_id,
        {
            "id": new_id("evt"),
            "ts": utc_iso(),
            "type": event_type,
            "room_id": room_id,
            "request_id": _safe_str(request_id),
            "payload": payload,
        },
    )


def get_external_mcp_publish_status(room_id: str) -> Dict[str, Any]:
    room_id = require_safe_id("room_id", room_id)
    meta = ensure_room_exists(room_id)
    owner_user_id = _safe_str(get_room_owner_user_id(meta))
    raw = load_external_mcp_publish_doc(room_id)

    if not raw:
        return {
            "status": "unpublished",
            "publish_enabled": False,
            "source_room_id": room_id,
            "provider_id": _provider_id_for_room(room_id),
            "owner_user_id": owner_user_id,
            "has_token": False,
            "plaintext_token_available": False,
            "result_view": DEFAULT_RESULT_VIEW,
            "source_observation_allowed": False,
            "owner_private_scope_exposed": False,
        }

    normalized = _normalize_publish_record(raw, room_id=room_id, owner_user_id=owner_user_id)
    if normalized != raw:
        save_external_mcp_publish_doc(room_id, normalized)

    return _public_status(normalized)


def enable_external_mcp_publish(
    room_id: str,
    *,
    actor_uid: str = "",
    request_id: str = "",
    args: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    room_id = require_safe_id("room_id", room_id)
    arg_obj = _safe_dict(args)
    meta = ensure_room_exists(room_id)
    owner_user_id = _safe_str(get_room_owner_user_id(meta))

    current_raw = load_external_mcp_publish_doc(room_id)
    current = _normalize_publish_record(current_raw, room_id=room_id, owner_user_id=owner_user_id) if current_raw else {}

    if current and _publication_status(current) == "active":
        return {
            "ok": True,
            "already_active": True,
            "publish": _public_status(current),
            "plaintext_token": "",
            "plaintext_token_available": False,
            "message": "external MCP publish is already active; use regenerate to create a new token",
        }

    token = _external_token()
    now = utc_iso()

    record = {
        "publish_id": _safe_str(current.get("publish_id")) or new_id("external_mcp_publish"),
        "token_hash": hash_external_mcp_publish_token(token),
        "source_room_id": room_id,
        "provider_id": _provider_id_for_room(room_id),
        "owner_user_id": owner_user_id,
        "created_at": _safe_str(current.get("created_at")) or now,
        "expires_at": _resolve_expires_at(arg_obj, current),
        "revoked_at": "",
        "allowed_mode": _safe_str(arg_obj.get("allowed_mode"), DEFAULT_ALLOWED_MODE) or DEFAULT_ALLOWED_MODE,
        "result_view": DEFAULT_RESULT_VIEW,
        "source_observation_allowed": False,
        "owner_private_scope_exposed": False,
        "max_calls": _resolve_max_calls(arg_obj, current),
        "daily_call_limit": _safe_non_negative_int(arg_obj.get("daily_call_limit"), _safe_non_negative_int(current.get("daily_call_limit"), 0)),
        "used_count": 0,
        "last_used_at": "",
        "client_label": _safe_str(arg_obj.get("client_label"), _safe_str(current.get("client_label"))),
        "updated_at": now,
    }

    record = _normalize_publish_record(record, room_id=room_id, owner_user_id=owner_user_id)
    save_external_mcp_publish_doc(room_id, record)
    touch_room_updated_at(room_id)

    _append_external_publish_event(
        room_id=room_id,
        request_id=request_id,
        actor_uid=actor_uid or owner_user_id,
        event_type="room.external_mcp_publish_enable",
        publish=record,
    )

    config_bundle = build_external_mcp_config_bundle(
        publish=record,
        plaintext_token=token,
        endpoint_url=_safe_str(arg_obj.get("endpoint_url")),
        server_name=_safe_str(arg_obj.get("server_name"), "nisb_room"),
    )

    public = _public_status(record)
    public["plaintext_token_available"] = True

    return {
        "ok": True,
        "publish": public,
        "plaintext_token": token,
        "plaintext_token_available": True,
        "config": config_bundle,
        "message": "external MCP publish enabled; plaintext token is shown once",
    }


def revoke_external_mcp_publish(
    room_id: str,
    *,
    actor_uid: str = "",
    request_id: str = "",
) -> Dict[str, Any]:
    room_id = require_safe_id("room_id", room_id)
    meta = ensure_room_exists(room_id)
    owner_user_id = _safe_str(get_room_owner_user_id(meta))

    current_raw = load_external_mcp_publish_doc(room_id)
    if not current_raw:
        status = get_external_mcp_publish_status(room_id)
        return {
            "ok": True,
            "already_revoked": False,
            "publish": status,
            "message": "external MCP publish is not enabled",
        }

    record = _normalize_publish_record(current_raw, room_id=room_id, owner_user_id=owner_user_id)
    already_revoked = bool(_safe_str(record.get("revoked_at")))

    if not already_revoked:
        record["revoked_at"] = utc_iso()
        record["updated_at"] = utc_iso()
        save_external_mcp_publish_doc(room_id, record)
        touch_room_updated_at(room_id)

        _append_external_publish_event(
            room_id=room_id,
            request_id=request_id,
            actor_uid=actor_uid or owner_user_id,
            event_type="room.external_mcp_publish_revoke",
            publish=record,
        )

    return {
        "ok": True,
        "already_revoked": already_revoked,
        "publish": _public_status(record),
        "message": "external MCP publish revoked" if not already_revoked else "external MCP publish already revoked",
    }


def regenerate_external_mcp_publish(
    room_id: str,
    *,
    actor_uid: str = "",
    request_id: str = "",
    args: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    room_id = require_safe_id("room_id", room_id)
    arg_obj = _safe_dict(args)
    meta = ensure_room_exists(room_id)
    owner_user_id = _safe_str(get_room_owner_user_id(meta))

    current_raw = load_external_mcp_publish_doc(room_id)
    current = _normalize_publish_record(current_raw, room_id=room_id, owner_user_id=owner_user_id) if current_raw else {}

    token = _external_token()
    now = utc_iso()

    record = {
        "publish_id": _safe_str(current.get("publish_id")) or new_id("external_mcp_publish"),
        "token_hash": hash_external_mcp_publish_token(token),
        "source_room_id": room_id,
        "provider_id": _provider_id_for_room(room_id),
        "owner_user_id": owner_user_id,
        "created_at": _safe_str(current.get("created_at")) or now,
        "expires_at": _resolve_expires_at(arg_obj, current),
        "revoked_at": "",
        "allowed_mode": _safe_str(arg_obj.get("allowed_mode"), _safe_str(current.get("allowed_mode"), DEFAULT_ALLOWED_MODE)) or DEFAULT_ALLOWED_MODE,
        "result_view": DEFAULT_RESULT_VIEW,
        "source_observation_allowed": False,
        "owner_private_scope_exposed": False,
        "max_calls": _resolve_max_calls(arg_obj, current),
        "daily_call_limit": _safe_non_negative_int(arg_obj.get("daily_call_limit"), _safe_non_negative_int(current.get("daily_call_limit"), 0)),
        "used_count": 0,
        "last_used_at": "",
        "client_label": _safe_str(arg_obj.get("client_label"), _safe_str(current.get("client_label"))),
        "updated_at": now,
    }

    record = _normalize_publish_record(record, room_id=room_id, owner_user_id=owner_user_id)
    save_external_mcp_publish_doc(room_id, record)
    touch_room_updated_at(room_id)

    _append_external_publish_event(
        room_id=room_id,
        request_id=request_id,
        actor_uid=actor_uid or owner_user_id,
        event_type="room.external_mcp_publish_regenerate",
        publish=record,
    )

    config_bundle = build_external_mcp_config_bundle(
        publish=record,
        plaintext_token=token,
        endpoint_url=_safe_str(arg_obj.get("endpoint_url")),
        server_name=_safe_str(arg_obj.get("server_name"), "nisb_room"),
    )

    public = _public_status(record)
    public["plaintext_token_available"] = True

    return {
        "ok": True,
        "publish": public,
        "plaintext_token": token,
        "plaintext_token_available": True,
        "config": config_bundle,
        "message": "external MCP publish token regenerated; plaintext token is shown once",
    }


__all__ = [
    "ROOM_PROVIDER_PREFIX",
    "DEFAULT_ALLOWED_MODE",
    "DEFAULT_RESULT_VIEW",
    "hash_external_mcp_publish_token",
    "get_external_mcp_publish_status",
    "enable_external_mcp_publish",
    "revoke_external_mcp_publish",
    "regenerate_external_mcp_publish",
]

