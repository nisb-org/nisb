from __future__ import annotations


import json
import os
import re
import time
from typing import Any, Dict, List, Optional, Tuple


from core.storage import append_jsonl, load_json, load_jsonl
from core.user_context import get_user_ctx


from .room_contracts import default_room_state, require_safe_id, utc_iso


SHARED_ROOT = "/data/shared/rooms"



def get_basepath(args: Dict[str, Any]) -> str:
    bp = args.get("basepath") or args.get("base_path") or args.get("basePath")
    bp = str(bp or "").strip()
    if not bp:
        raise ValueError("missing injected base_path")
    return bp



def uid_from_ctx_or_basepath(basepath: str, args: Optional[Dict[str, Any]] = None) -> str:
    if args:
        uid = args.get("user_id") or args.get("uid")
        if uid:
            return str(uid).strip()


    try:
        ctx = get_user_ctx()
        for k in ("uid", "user_id", "username"):
            v = getattr(ctx, k, None)
            if v:
                return str(v)
        b = getattr(ctx, "base", None)
        if isinstance(b, str) and b:
            m = re.search(r"/users/([^/]+)/?", b)
            if m:
                return m.group(1)
    except Exception:
        pass


    m = re.search(r"/users/([^/]+)/?", str(basepath or ""))
    if m:
        return m.group(1)


    return "unknown"



def ensure_dir(p: str) -> None:
    os.makedirs(p, exist_ok=True)



def atomic_write_json(path: str, data: Dict[str, Any]) -> None:
    ensure_dir(os.path.dirname(path))
    tmp = f"{path}.tmp.{int(time.time()*1000)}"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)



def room_dir(room_id: str) -> str:
    room_id = require_safe_id("room_id", room_id)
    return os.path.join(SHARED_ROOT, room_id)



def room_meta_path(room_id: str) -> str:
    return os.path.join(room_dir(room_id), "meta.json")



def room_events_path(room_id: str) -> str:
    return os.path.join(room_dir(room_id), "events.jsonl")



def room_roles_path(room_id: str) -> str:
    return os.path.join(room_dir(room_id), "roles.json")



def room_state_path(room_id: str) -> str:
    return os.path.join(room_dir(room_id), "state.json")



def ensure_room_paths(room_id: str) -> None:
    ensure_dir(room_dir(room_id))
    if not os.path.exists(room_roles_path(room_id)):
        save_roles_doc(room_id, {"roles": []})
    if not os.path.exists(room_state_path(room_id)):
        save_state_doc(room_id, default_room_state())



def load_meta(room_id: str) -> Dict[str, Any]:
    data = load_json(room_meta_path(room_id))
    return data if isinstance(data, dict) else {}



def save_meta(room_id: str, data: Dict[str, Any]) -> None:
    atomic_write_json(room_meta_path(room_id), data or {})



def touch_room_updated_at(room_id: str) -> Dict[str, Any]:
    meta = load_meta(room_id)
    if not meta:
        return {}
    meta["updated_at"] = utc_iso()
    save_meta(room_id, meta)
    return meta



def load_roles_doc(room_id: str) -> Dict[str, Any]:
    data = load_json(room_roles_path(room_id))
    if isinstance(data, dict):
        roles = data.get("roles")
        if not isinstance(roles, list):
            data["roles"] = []
        return data
    return {"roles": []}



def save_roles_doc(room_id: str, data: Dict[str, Any]) -> None:
    atomic_write_json(room_roles_path(room_id), data if isinstance(data, dict) else {"roles": []})



def load_state_doc(room_id: str) -> Dict[str, Any]:
    data = load_json(room_state_path(room_id))
    if not isinstance(data, dict):
        data = default_room_state()
    base = default_room_state()
    base.update(data)
    return base



def save_state_doc(room_id: str, data: Dict[str, Any]) -> None:
    base = default_room_state()
    if isinstance(data, dict):
        base.update(data)
    base["updated_at"] = utc_iso()
    atomic_write_json(room_state_path(room_id), base)



def append_room_event(room_id: str, row: Dict[str, Any]) -> None:
    append_jsonl(room_events_path(room_id), row)



def load_room_events(room_id: str) -> List[Dict[str, Any]]:
    rows = load_jsonl(room_events_path(room_id))
    return [r for r in rows if isinstance(r, dict)]



def _safe_str(v: Any, default: str = "") -> str:
    if v is None:
        return default
    s = str(v).strip()
    return s if s else default



def _safe_int(v: Any, default: int = 0) -> int:
    try:
        return int(v)
    except Exception:
        return default



def _clamp_int(v: Any, low: int, high: int, default: int) -> int:
    n = _safe_int(v, default)
    if n < low:
        return low
    if n > high:
        return high
    return n



def _event_sort_key(row: Dict[str, Any]) -> Tuple[str, str]:
    return (_safe_str(row.get("ts")), _safe_str(row.get("id")))



def _payload_of_event(evt: Dict[str, Any]) -> Dict[str, Any]:
    payload = evt.get("payload")
    return payload if isinstance(payload, dict) else {}



def _parse_recent_cursor(cursor: Any) -> Dict[str, Any]:
    if isinstance(cursor, dict):
        return dict(cursor)
    if isinstance(cursor, str):
        raw = cursor.strip()
        if not raw:
            return {}
        try:
            data = json.loads(raw)
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}
    return {}



def _strip_recent_internal_meta(row: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(row, dict):
        return {}
    out = dict(row)
    out.pop("_line_start", None)
    out.pop("_line_end", None)
    return out



def _read_jsonl_window_once(path: str, end_offset: int, byte_budget: int) -> Tuple[List[Dict[str, Any]], int, int, int]:
    if not os.path.exists(path):
        return [], 0, 0, 0


    file_size = os.path.getsize(path)
    end = max(0, min(_safe_int(end_offset, file_size), file_size))
    start = max(0, end - max(1, byte_budget))


    if end <= 0:
        return [], 0, 0, file_size


    with open(path, "rb") as f:
        f.seek(start)
        raw = f.read(end - start)


    adjusted_start = start
    if start > 0:
        nl = raw.find(b"\n")
        if nl >= 0:
            adjusted_start = start + nl + 1
            raw = raw[nl + 1 :]
        else:
            return [], adjusted_start, end, file_size


    rows: List[Dict[str, Any]] = []
    offset = adjusted_start
    for chunk in raw.splitlines(keepends=True):
        line_start = offset
        line_end = offset + len(chunk)
        offset = line_end


        line = chunk.strip()
        if not line:
            continue


        try:
            obj = json.loads(line.decode("utf-8", errors="ignore"))
        except Exception:
            continue


        if isinstance(obj, dict):
            row = dict(obj)
            row["_line_start"] = line_start
            row["_line_end"] = line_end
            rows.append(row)


    return rows, adjusted_start, end, file_size



def _read_jsonl_tail_window(
    path: str,
    *,
    end_offset: Optional[int] = None,
    byte_budget: int = 524288,
    max_scan_bytes: int = 4194304,
) -> Tuple[List[Dict[str, Any]], int, int, int]:
    if not os.path.exists(path):
        return [], 0, 0, 0


    file_size = os.path.getsize(path)
    end = file_size if end_offset is None else max(0, min(_safe_int(end_offset, file_size), file_size))
    if end <= 0:
        return [], 0, 0, file_size


    budget = _clamp_int(byte_budget, 65536, max_scan_bytes, 524288)


    while True:
        rows, start, window_end, actual_size = _read_jsonl_window_once(path, end, budget)
        if rows or start <= 0 or budget >= max_scan_bytes:
            return rows, start, window_end, actual_size
        budget = min(max_scan_bytes, budget * 2)



def _collect_relation_keys(row: Dict[str, Any]) -> Dict[str, str]:
    payload = _payload_of_event(row)
    return {
        "id": _safe_str(row.get("id")),
        "request_id": _safe_str(row.get("request_id")),
        "run_id": _safe_str(row.get("run_id")),
        "trigger_event_id": _safe_str(row.get("trigger_event_id")),
        "source_event_id": _safe_str(payload.get("source_event_id")),
    }



def _expand_related_rows(
    rows: List[Dict[str, Any]],
    seed_rows: List[Dict[str, Any]],
    *,
    hard_cap: int = 600,
) -> List[Dict[str, Any]]:
    if not rows or not seed_rows:
        return list(seed_rows)


    event_ids = set()
    request_ids = set()
    run_ids = set()
    referenced_event_ids = set()
    included_line_starts = set()


    def absorb(row: Dict[str, Any]) -> None:
        keys = _collect_relation_keys(row)
        if keys["id"]:
            event_ids.add(keys["id"])
        if keys["request_id"]:
            request_ids.add(keys["request_id"])
        if keys["run_id"]:
            run_ids.add(keys["run_id"])
        if keys["trigger_event_id"]:
            referenced_event_ids.add(keys["trigger_event_id"])
        if keys["source_event_id"]:
            referenced_event_ids.add(keys["source_event_id"])
        included_line_starts.add(_safe_int(row.get("_line_start"), -1))


    for row in seed_rows:
        absorb(row)


    selected = list(seed_rows)
    changed = True


    while changed and len(selected) < hard_cap:
        changed = False
        for row in rows:
            line_start = _safe_int(row.get("_line_start"), -1)
            if line_start in included_line_starts:
                continue


            keys = _collect_relation_keys(row)
            is_related = False


            if keys["id"] and keys["id"] in referenced_event_ids:
                is_related = True
            elif keys["trigger_event_id"] and keys["trigger_event_id"] in event_ids:
                is_related = True
            elif keys["source_event_id"] and keys["source_event_id"] in event_ids:
                is_related = True
            elif keys["request_id"] and keys["request_id"] in request_ids:
                is_related = True
            elif keys["run_id"] and keys["run_id"] in run_ids:
                is_related = True


            if not is_related:
                continue


            selected.append(row)
            absorb(row)
            changed = True


            if len(selected) >= hard_cap:
                break


    selected.sort(key=_event_sort_key)
    return selected



def load_recent_room_events(
    room_id: str,
    *,
    limit: int = 80,
    order: str = "asc",
    before_event_id: str = "",
    cursor: Any = None,
    byte_budget: int = 524288,
    relation_expand: bool = True,
) -> Dict[str, Any]:
    room_id = require_safe_id("room_id", room_id)
    path = room_events_path(room_id)


    limit = _clamp_int(limit, 1, 200, 80)
    order_token = "asc" if _safe_str(order).lower() == "asc" else "desc"
    byte_budget = _clamp_int(byte_budget, 65536, 2097152, 524288)
    before_event_id = _safe_str(before_event_id)
    cursor_data = _parse_recent_cursor(cursor)


    if not os.path.exists(path):
        return {
            "items": [],
            "returned_count": 0,
            "limit": limit,
            "order": order_token,
            "source": "tail_window",
            "byte_budget": byte_budget,
            "file_size": 0,
            "window_start_offset": 0,
            "window_end_offset": 0,
            "has_more": False,
            "next_cursor": {},
            "relation_expand": bool(relation_expand),
            "before_event_id": before_event_id,
        }


    file_size = os.path.getsize(path)
    end_offset = file_size


    cursor_before_offset = _safe_int(cursor_data.get("before_offset"), 0)
    if cursor_before_offset > 0:
        end_offset = min(cursor_before_offset, file_size)


    rows, window_start_offset, window_end_offset, file_size = _read_jsonl_tail_window(
        path,
        end_offset=end_offset,
        byte_budget=byte_budget,
    )
    rows.sort(key=_event_sort_key)


    if before_event_id and cursor_before_offset <= 0:
        anchor = next((r for r in rows if _safe_str(r.get("id")) == before_event_id), None)
        if anchor is not None:
            anchor_offset = _safe_int(anchor.get("_line_start"), end_offset)
            rows = [r for r in rows if _safe_int(r.get("_line_start"), 0) < anchor_offset]
            window_end_offset = min(window_end_offset, anchor_offset)


    if not rows:
        return {
            "items": [],
            "returned_count": 0,
            "limit": limit,
            "order": order_token,
            "source": "tail_window",
            "byte_budget": byte_budget,
            "file_size": file_size,
            "window_start_offset": window_start_offset,
            "window_end_offset": window_end_offset,
            "has_more": window_start_offset > 0,
            "next_cursor": {
                "before_offset": window_start_offset,
                "before_event_id": "",
            } if window_start_offset > 0 else {},
            "relation_expand": bool(relation_expand),
            "before_event_id": before_event_id,
        }


    seed_rows = rows[-limit:]
    selected_rows = seed_rows


    if relation_expand:
        hard_cap = min(600, max(limit * 3, limit + 40))
        selected_rows = _expand_related_rows(rows, seed_rows, hard_cap=hard_cap)


    selected_rows.sort(key=_event_sort_key)


    oldest_line_start = _safe_int(selected_rows[0].get("_line_start"), 0) if selected_rows else 0
    newest_line_end = _safe_int(selected_rows[-1].get("_line_end"), window_end_offset) if selected_rows else window_end_offset


    has_more = oldest_line_start > 0
    next_cursor = {
        "before_offset": oldest_line_start,
        "before_event_id": _safe_str(selected_rows[0].get("id")),
    } if has_more else {}


    items = [_strip_recent_internal_meta(row) for row in selected_rows]
    if order_token == "desc":
        items = list(reversed(items))


    return {
        "items": items,
        "returned_count": len(items),
        "limit": limit,
        "order": order_token,
        "source": "tail_window",
        "byte_budget": byte_budget,
        "file_size": file_size,
        "window_start_offset": window_start_offset,
        "window_end_offset": window_end_offset,
        "selected_oldest_offset": oldest_line_start,
        "selected_newest_offset": newest_line_end,
        "has_more": has_more,
        "next_cursor": next_cursor,
        "relation_expand": bool(relation_expand),
        "before_event_id": before_event_id,
    }



def ensure_room_exists(room_id: str) -> Dict[str, Any]:
    room_id = require_safe_id("room_id", room_id)
    meta = load_meta(room_id)
    if not meta:
        raise ValueError("room not found")
    ensure_room_paths(room_id)
    return meta


def _participants_of(meta: Dict[str, Any]) -> List[str]:
    if not isinstance(meta, dict):
        return []


    ps = meta.get("participants")
    if not isinstance(ps, list):
        return []


    out: List[str] = []
    seen = set()
    for item in ps:
        s = str(item or "").strip()
        if not s or s in seen:
            continue
        seen.add(s)
        out.append(s)
    return out



def _is_federated_participant_uid(uid: Any) -> bool:
    return _safe_str(uid).startswith("fed__")



def _normalize_federated_member_access(raw: Any) -> Dict[str, Dict[str, str]]:
    src = raw if isinstance(raw, dict) else {}
    out: Dict[str, Dict[str, str]] = {}

    for participant_uid, row in src.items():
        uid = _safe_str(participant_uid)
        if not uid or not _is_federated_participant_uid(uid):
            continue

        item = row if isinstance(row, dict) else {}
        status = _safe_str(item.get("status")).lower() or "active"
        status = "revoked" if status == "revoked" else "active"

        out[uid] = {
            "participant_uid": uid,
            "status": status,
            "revoked_at": _safe_str(item.get("revoked_at")),
            "revoked_by": _safe_str(item.get("revoked_by")),
            "updated_at": _safe_str(item.get("updated_at")),
        }

    return out



def get_federated_member_access_status(meta: Dict[str, Any], uid: Any) -> str:
    participant_uid = _safe_str(uid)
    if not _is_federated_participant_uid(participant_uid):
        return "active"

    access = _normalize_federated_member_access(
        meta.get("federated_member_access") if isinstance(meta, dict) else {}
    )
    row = access.get(participant_uid) or {}
    return "revoked" if _safe_str(row.get("status")) == "revoked" else "active"



def is_federated_member_access_revoked(uid: Any, meta: Dict[str, Any]) -> bool:
    return get_federated_member_access_status(meta, uid) == "revoked"



def get_room_owner_user_id(meta: Dict[str, Any]) -> str:
    if not isinstance(meta, dict):
        return ""


    owner_user_id = str(meta.get("owner_user_id") or "").strip()
    if owner_user_id:
        return owner_user_id


    participants = _participants_of(meta)
    if participants:
        return participants[0]


    return ""



def is_room_owner(uid: str, meta: Dict[str, Any]) -> bool:
    uid = str(uid or "").strip()
    if not uid:
        return False
    return uid == get_room_owner_user_id(meta)



def can_edit_room_info(uid: str, meta: Dict[str, Any]) -> bool:
    return is_room_owner(uid, meta)



def can_edit_room_state(uid: str, meta: Dict[str, Any]) -> bool:
    return is_room_owner(uid, meta)



def can_manage_room_roles(uid: str, meta: Dict[str, Any]) -> bool:
    return is_room_owner(uid, meta)



def is_participant(uid: str, meta: Dict[str, Any]) -> bool:
    uid = str(uid or "").strip()
    if not uid:
        return False

    if _is_federated_participant_uid(uid) and is_federated_member_access_revoked(uid, meta):
        return False


    ps = meta.get("participants")
    if not isinstance(ps, list):
        owner_user_id = get_room_owner_user_id(meta)
        return bool(owner_user_id) and uid == owner_user_id


    participants = _participants_of(meta)
    if not participants:
        owner_user_id = get_room_owner_user_id(meta)
        return bool(owner_user_id) and uid == owner_user_id


    return uid in participants



def list_room_metas_for_uid(uid: str) -> List[Dict[str, Any]]:
    ensure_dir(SHARED_ROOT)
    rooms: List[Dict[str, Any]] = []
    for name in os.listdir(SHARED_ROOT):
        rid = str(name or "").strip()
        if not rid:
            continue
        p = room_dir(rid)
        if not os.path.isdir(p):
            continue
        meta = load_meta(rid)
        if not meta:
            continue
        if not is_participant(uid, meta):
            continue
        rooms.append(meta)
    rooms.sort(key=lambda x: str(x.get("updated_at") or x.get("created_at") or ""), reverse=True)
    return rooms
