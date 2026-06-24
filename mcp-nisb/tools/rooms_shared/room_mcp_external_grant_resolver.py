from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple


EXTERNAL_MCP_PUBLISH_FILENAME = "external_mcp_publish.json"


def _safe_dict(v: Any) -> Dict[str, Any]:
    return v if isinstance(v, dict) else {}


def _safe_list(v: Any) -> List[Any]:
    return v if isinstance(v, list) else []


def _safe_str(v: Any, default: str = "") -> str:
    if v is None:
        return default
    s = str(v).strip()
    return s if s else default


def _safe_int(v: Any, default: int = 0) -> int:
    try:
        if v is None or v == "":
            return default
        return int(v)
    except Exception:
        return default


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _iso_now() -> str:
    return _now_utc().isoformat()


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _parse_datetime(v: Any) -> Optional[datetime]:
    s = _safe_str(v)
    if not s:
        return None
    try:
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


def _load_json(path: Path) -> Any:
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def _atomic_write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(str(tmp), str(path))


def _header_get(headers: Any, name: str) -> str:
    try:
        value = headers.get(name)
        if value:
            return _safe_str(value)
    except Exception:
        pass

    try:
        lname = name.lower()
        for k, v in dict(headers).items():
            if str(k).lower() == lname:
                return _safe_str(v)
    except Exception:
        pass

    return ""


def extract_bearer_token(headers: Any) -> Tuple[str, bool]:
    auth = _header_get(headers, "Authorization")
    if not auth:
        return "", False

    parts = auth.split(None, 1)
    if len(parts) != 2:
        return "", False

    if parts[0].lower() != "bearer":
        return "", False

    token = _safe_str(parts[1])
    return token, True


def _candidate_room_roots(base_path: str = "") -> List[Path]:
    roots: List[Path] = []

    for env_name in (
        "NISB_SHARED_ROOMS_PATH",
        "NISB_ROOMS_BASE_PATH",
        "NISB_ROOM_STORE_PATH",
    ):
        value = _safe_str(os.environ.get(env_name))
        if value:
            roots.append(Path(value))

    roots.append(Path("/data/shared/rooms"))
    roots.append(Path("/data/rooms"))

    bp = _safe_str(base_path)
    if bp:
        p = Path(bp)
        roots.append(p / "shared" / "rooms")
        roots.append(p / "rooms")
        roots.append(p / "storage" / "rooms")

    deduped: List[Path] = []
    seen = set()
    for root in roots:
        key = str(root)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(root)

    return deduped


def _iter_publish_files(base_path: str = "") -> Iterable[Path]:
    for root in _candidate_room_roots(base_path):
        try:
            if not root.exists() or not root.is_dir():
                continue
            for child in root.iterdir():
                if not child.is_dir():
                    continue
                path = child / EXTERNAL_MCP_PUBLISH_FILENAME
                if path.exists() and path.is_file():
                    yield path
        except Exception:
            continue


def _publication_records(payload: Any) -> List[Dict[str, Any]]:
    if isinstance(payload, dict):
        if payload.get("token_hash") or payload.get("publish_id"):
            return [payload]

        for key in ("publications", "items", "records", "rows"):
            rows = [
                x for x in _safe_list(payload.get(key))
                if isinstance(x, dict)
            ]
            if rows:
                return rows

    if isinstance(payload, list):
        return [x for x in payload if isinstance(x, dict)]

    return []


def _provider_id_from_room(room_id: str) -> str:
    return f"room_provider__{room_id}" if room_id else ""


def _record_room_id(record: Dict[str, Any], path: Path) -> str:
    return _safe_str(
        record.get("source_room_id")
        or record.get("room_id")
        or record.get("target_room_id")
        or path.parent.name
    )


def _is_revoked(record: Dict[str, Any]) -> bool:
    status = _safe_str(record.get("status")).lower()
    if status in {"revoked", "disabled", "deleted"}:
        return True
    return bool(_safe_str(record.get("revoked_at")))


def _is_expired(record: Dict[str, Any]) -> bool:
    expires_at = _parse_datetime(record.get("expires_at"))
    if not expires_at:
        return False
    return expires_at <= _now_utc()


def _limit_error(record: Dict[str, Any]) -> str:
    max_calls = _safe_int(record.get("max_calls"), 0)
    used_count = _safe_int(record.get("used_count"), 0)
    if max_calls > 0 and used_count >= max_calls:
        return "external_publish_call_limit_exceeded"

    daily_limit = _safe_int(record.get("daily_call_limit"), 0)
    daily_used = _safe_int(record.get("daily_used_count"), 0)
    daily_date = _safe_str(record.get("daily_used_date"))
    today = _now_utc().date().isoformat()
    if daily_limit > 0 and daily_date == today and daily_used >= daily_limit:
        return "external_publish_call_limit_exceeded"

    return ""


def _scope_from_record(record: Dict[str, Any], path: Path) -> Dict[str, Any]:
    source_room_id = _record_room_id(record, path)
    provider_id = _safe_str(record.get("provider_id")) or _provider_id_from_room(source_room_id)

    return {
        "external_mcp_publish_scope": True,
        "publish_id": _safe_str(record.get("publish_id")),
        "source_room_id": source_room_id,
        "provider_id": provider_id,
        "owner_user_id": _safe_str(record.get("owner_user_id")),
        "client_label": _safe_str(record.get("client_label")),
        "allowed_mode": _safe_str(record.get("allowed_mode"), "ask"),
        "provider_origin": _safe_str(record.get("provider_origin"), "local_room_shared"),
        "result_view": "final_result_only",
        "source_observation_allowed": False,
        "owner_private_scope_exposed": False,
        "status": _safe_str(record.get("status"), "active"),
        "created_at": _safe_str(record.get("created_at")),
        "expires_at": _safe_str(record.get("expires_at")),
        "max_calls": record.get("max_calls"),
        "daily_call_limit": record.get("daily_call_limit"),
        "_store_path": str(path),
    }


def _error(error: str, message: str = "") -> Dict[str, Any]:
    return {
        "ok": False,
        "external": True,
        "error": error,
        "message": message or error,
    }


def resolve_external_mcp_publish_scope(
    headers: Any,
    *,
    path: str = "",
    base_path: str = "",
) -> Dict[str, Any]:
    token, has_bearer = extract_bearer_token(headers)
    if not has_bearer:
        return {"ok": True, "external": False, "scope": None}

    if not token:
        return _error("external_publish_token_missing")

    token_hash = _sha256(token)

    for publish_path in _iter_publish_files(base_path):
        payload = _load_json(publish_path)
        for record in _publication_records(payload):
            if _safe_str(record.get("token_hash")) != token_hash:
                continue

            if _is_revoked(record):
                return _error("external_publish_revoked")

            if _is_expired(record):
                return _error("external_publish_expired")

            limit_error = _limit_error(record)
            if limit_error:
                return _error(limit_error)

            scope = _scope_from_record(record, publish_path)
            return {
                "ok": True,
                "external": True,
                "scope": scope,
            }

    return _error("external_publish_token_invalid")


def _record_matches_scope(record: Dict[str, Any], scope: Dict[str, Any]) -> bool:
    publish_id = _safe_str(scope.get("publish_id"))
    if publish_id and _safe_str(record.get("publish_id")) == publish_id:
        return True

    source_room_id = _safe_str(scope.get("source_room_id"))
    provider_id = _safe_str(scope.get("provider_id"))
    return (
        source_room_id
        and _safe_str(record.get("source_room_id") or record.get("room_id")) == source_room_id
        and _safe_str(record.get("provider_id")) == provider_id
    )


def _touch_record(record: Dict[str, Any]) -> bool:
    today = _now_utc().date().isoformat()
    record["last_used_at"] = _iso_now()
    record["used_count"] = _safe_int(record.get("used_count"), 0) + 1

    if _safe_str(record.get("daily_used_date")) != today:
        record["daily_used_date"] = today
        record["daily_used_count"] = 1
    else:
        record["daily_used_count"] = _safe_int(record.get("daily_used_count"), 0) + 1

    return True


def mark_external_mcp_publish_used(scope: Dict[str, Any]) -> Dict[str, Any]:
    scope = _safe_dict(scope)
    path_text = _safe_str(scope.get("_store_path"))
    if not path_text:
        return {"ok": False, "error": "missing_store_path"}

    path = Path(path_text)
    payload = _load_json(path)
    changed = False

    if isinstance(payload, dict) and (payload.get("token_hash") or payload.get("publish_id")):
        if _record_matches_scope(payload, scope):
            changed = _touch_record(payload)

    elif isinstance(payload, dict):
        for key in ("publications", "items", "records", "rows"):
            rows = payload.get(key)
            if not isinstance(rows, list):
                continue
            for item in rows:
                if isinstance(item, dict) and _record_matches_scope(item, scope):
                    changed = _touch_record(item)
                    break
            if changed:
                break

    elif isinstance(payload, list):
        for item in payload:
            if isinstance(item, dict) and _record_matches_scope(item, scope):
                changed = _touch_record(item)
                break

    if not changed:
        return {"ok": False, "error": "record_not_found"}

    _atomic_write_json(path, payload)
    return {"ok": True}
