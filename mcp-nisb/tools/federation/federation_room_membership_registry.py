from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from core.storage import load_json


def _utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_str(value: Any) -> str:
    return str(value or "").strip()


def _ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def _fed_root(basepath: str) -> str:
    return os.path.join(basepath, "federation")


def _fed_invites_json(basepath: str) -> str:
    return os.path.join(_fed_root(basepath), "room_invites.json")


def _fed_joined_rooms_json(basepath: str) -> str:
    return os.path.join(_fed_root(basepath), "joined_rooms.json")


def _atomic_save_json(path: str, data: Dict[str, Any]) -> None:
    _ensure_dir(os.path.dirname(path))
    tmp = f"{path}.tmp.{int(time.time() * 1000)}"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def _load_joined_rooms(basepath: str) -> Dict[str, Any]:
    doc = load_json(_fed_joined_rooms_json(basepath))
    if isinstance(doc, dict) and isinstance(doc.get("rooms"), list):
        return doc
    return {"version": 1, "updated_at": _utc_iso(), "rooms": []}


def _write_joined_rooms(basepath: str, doc: Dict[str, Any]) -> None:
    doc["updated_at"] = _utc_iso()
    _atomic_save_json(_fed_joined_rooms_json(basepath), doc)


def _upsert_joined_room(
    basepath: str,
    *,
    peer_id: str,
    room_id: str,
    owner_room_id: str,
    remote_user_id: str,
    remote_label: str,
    title: str = "",
    enabled: bool = True,
    target_peer_id: str = "",
    local_owner_user_id: str = "",
    owner_user_id: str = "",
) -> Dict[str, Any]:
    doc = _load_joined_rooms(basepath)
    rooms: List[Dict[str, Any]] = [row for row in (doc.get("rooms") or []) if isinstance(row, dict)]

    peer_id = _safe_str(peer_id)
    room_id = _safe_str(room_id)
    owner_room_id = _safe_str(owner_room_id) or room_id
    remote_user_id = _safe_str(remote_user_id)
    remote_label = _safe_str(remote_label)
    target_peer_id = _safe_str(target_peer_id)
    local_owner_user_id = _safe_str(local_owner_user_id)
    owner_user_id = _safe_str(owner_user_id) or local_owner_user_id

    found: Optional[Dict[str, Any]] = None
    for row in rooms:
        row_peer_id = _safe_str(row.get("peer_id"))
        row_room_id = _safe_str(row.get("room_id"))
        row_owner_room_id = _safe_str(row.get("owner_room_id"))

        if row_peer_id != peer_id:
            continue

        if (
            (room_id and row_room_id == room_id)
            or (owner_room_id and row_owner_room_id == owner_room_id)
        ):
            found = row
            break

    now = _utc_iso()

    if found is None:
        found = {
            "peer_id": peer_id,
            "room_id": room_id,
            "joined_at": now,
        }
        rooms.append(found)

    found.update(
        {
            "peer_id": peer_id,
            "target_peer_id": target_peer_id or _safe_str(found.get("target_peer_id")),
            "room_id": room_id or _safe_str(found.get("room_id")) or owner_room_id,
            "owner_room_id": owner_room_id or _safe_str(found.get("owner_room_id")) or room_id,
            "remote_user_id": remote_user_id or _safe_str(found.get("remote_user_id")),
            "local_owner_user_id": local_owner_user_id or _safe_str(found.get("local_owner_user_id")),
            "owner_user_id": owner_user_id or _safe_str(found.get("owner_user_id")) or local_owner_user_id,
            "remote_label": remote_label if remote_label != "" else _safe_str(found.get("remote_label")),
            "title": _safe_str(title) if _safe_str(title) != "" else _safe_str(found.get("title")),
            "enabled": bool(enabled),
            "last_entered_at": now,
            "updated_at": now,
        }
    )

    doc["rooms"] = rooms
    _write_joined_rooms(basepath, doc)
    return found


def _load_room_invites(basepath: str) -> Dict[str, Any]:
    doc = load_json(_fed_invites_json(basepath))
    if isinstance(doc, dict) and isinstance(doc.get("invites"), list):
        return doc
    return {"version": 1, "updated_at": _utc_iso(), "invites": []}


def _write_room_invites(basepath: str, doc: Dict[str, Any]) -> None:
    doc["updated_at"] = _utc_iso()
    _atomic_save_json(_fed_invites_json(basepath), doc)


__all__ = [
    "_atomic_save_json",
    "_ensure_dir",
    "_fed_invites_json",
    "_fed_joined_rooms_json",
    "_fed_root",
    "_load_joined_rooms",
    "_load_room_invites",
    "_upsert_joined_room",
    "_write_joined_rooms",
    "_write_room_invites",
]
