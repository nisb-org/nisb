# /opt/mcp-gateway/mcp-nisb/tools/bookmarks/bookmark_list_all.py
import json
import os
import re
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional


def require_safe_id(field: str, value: str) -> str:
    s = str(value or "").strip()
    if not s:
        raise ValueError(f"Missing {field}.")
    if not re.fullmatch(r"[A-Za-z0-9_\-\.]+", s):
        raise ValueError(f"Unsafe {field}.")
    return s


def _parse_iso(ts: str) -> Optional[datetime]:
    s = str(ts or "").strip()
    if not s:
        return None
    try:
        return datetime.fromisoformat(s)
    except Exception:
        return None


def _cutoff_utc(time_range: str) -> Optional[datetime]:
    tr = str(time_range or "7d").strip().lower()
    if tr == "all":
        return None
    if tr == "30d":
        return datetime.now(timezone.utc) - timedelta(days=30)
    return datetime.now(timezone.utc) - timedelta(days=7)


def _load_jsonl(path: str) -> List[Dict[str, Any]]:
    if not os.path.exists(path):
        return []
    out: List[Dict[str, Any]] = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
                if isinstance(obj, dict):
                    out.append(obj)
            except Exception:
                continue
    return out


def _resolve_user_base_from_args(args: Dict[str, Any]) -> str:
    base = str(args.get("base_path") or args.get("basepath") or "").strip()
    if base:
        return base
    uid = str(args.get("user_id") or args.get("userid") or args.get("userId") or "").strip()
    if uid:
        uid = require_safe_id("user_id", uid)
        p1 = f"/data/users/{uid}"
        if os.path.exists(p1):
            return p1
        p2 = f"/opt/nisb-data/users/{uid}"
        if os.path.exists(p2):
            return p2
        return p1
    return "/data/users/nisb_default_user"


def nisb_bookmark_list_all(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    跨库列出书签（支持：可选 library_id 过滤 + 时间范围 + limit）。
    读取：{user_base}/bookmarks/library_doc_bookmarks.jsonl
    返回：{status:'success', bookmarks:[...], total:int}
    """
    user_base = _resolve_user_base_from_args(args)

    library_id = args.get("library_id", args.get("libraryId", ""))
    library_id = str(library_id or "").strip()
    if library_id:
        library_id = require_safe_id("library_id", library_id)

    time_range = str(args.get("time_range", args.get("timeRange", "7d")) or "7d").strip().lower()
    if time_range not in ("7d", "30d", "all"):
        time_range = "7d"
    cutoff = _cutoff_utc(time_range)

    try:
        limit = int(args.get("limit", 50))
    except Exception:
        limit = 50
    limit = max(1, min(limit, 500))

    path = os.path.join(user_base, "bookmarks", "library_doc_bookmarks.jsonl")
    rows = _load_jsonl(path)

    state: Dict[str, Dict[str, Any]] = {}
    deleted: set[str] = set()

    for it in rows:
        t = str(it.get("type") or "")
        bid = str(it.get("bookmark_id") or "").strip()
        if not bid:
            continue

        if t == "library_doc_bookmark_tombstone" or bool(it.get("tombstone")):
            deleted.add(bid)
            state.pop(bid, None)
            continue

        if t != "library_doc_bookmark":
            continue

        if bid in deleted:
            continue

        if library_id and str(it.get("library_id") or "") != library_id:
            continue

        if cutoff is not None:
            ts = _parse_iso(str(it.get("created_at") or ""))
            if ts is None:
                continue
            ts_utc = ts.astimezone(timezone.utc) if ts.tzinfo else ts.replace(tzinfo=timezone.utc)
            if ts_utc < cutoff:
                continue

        state[bid] = it

    out = list(state.values())
    out.sort(key=lambda x: str(x.get("updated_at") or x.get("created_at") or ""), reverse=True)

    return {"status": "success", "bookmarks": out[:limit], "total": len(out)}

