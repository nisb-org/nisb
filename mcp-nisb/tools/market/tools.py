from __future__ import annotations

import os
import time
import secrets
from datetime import datetime, timezone
from typing import Any, Dict, List

from core.storage import append_jsonl, load_jsonl


def _utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

def _get_basepath(args: Dict[str, Any]) -> str:
    bp = args.get("basepath") or args.get("base_path") or args.get("basePath")
    bp = str(bp or "").strip()
    if not bp:
        raise ValueError("missing injected basepath in tool args")
    return bp

def _ensure_dir(p: str) -> None:
    os.makedirs(p, exist_ok=True)

def _market_root(basepath: str) -> str:
    return os.path.join(basepath, "market")

def _listings_jsonl(basepath: str) -> str:
    return os.path.join(_market_root(basepath), "listings.jsonl")

def _events_jsonl(basepath: str) -> str:
    return os.path.join(_market_root(basepath), "market_events.jsonl")

def _new_id(prefix: str) -> str:
    return f"{prefix}_{int(time.time()*1000)}_{secrets.token_hex(4)}"

def _norm_tags(v: Any) -> List[str]:
    if not isinstance(v, list):
        return []
    out: List[str] = []
    for x in v:
        s = str(x or "").strip()
        if s:
            out.append(s)
    return out

def _kw_match(text: str, q: str) -> bool:
    if not q:
        return True
    return q.lower() in (text or "").lower()

def nisb_market_publish(args: Dict[str, Any]) -> Dict[str, Any]:
    basepath = _get_basepath(args)
    _ensure_dir(_market_root(basepath))

    object_ref = str(args.get("object_ref") or "").strip()
    if not object_ref:
        return {"success": False, "message": "missing object_ref"}

    listing_id = _new_id("listing")
    rec = {
        "id": listing_id,
        "ts": _utc_iso(),
        "object_ref": object_ref,
        "title": str(args.get("title") or "").strip(),
        "tags": _norm_tags(args.get("tags")),
        "visibility": str(args.get("visibility") or "private").strip().lower(),
        "payload": args.get("payload") if isinstance(args.get("payload"), dict) else {},
        "tombstone": False,
        "source": "local",
    }
    append_jsonl(_listings_jsonl(basepath), rec)

    append_jsonl(_events_jsonl(basepath), {
        "id": _new_id("evt"),
        "ts": _utc_iso(),
        "action": "publish",
        "listing_id": listing_id,
        "object_ref": object_ref,
        "actor": "user",
        "payload": {"title": rec["title"], "visibility": rec["visibility"], "tags": rec["tags"]},
    })
    return {"success": True, "listing_id": listing_id, "listing": rec}

def nisb_market_search(args: Dict[str, Any]) -> Dict[str, Any]:
    basepath = _get_basepath(args)
    _ensure_dir(_market_root(basepath))

    query = str(args.get("query") or "").strip()
    limit = args.get("limit", 50)
    try:
        limit = int(limit)
    except Exception:
        limit = 50
    limit = max(1, min(200, limit))

    tags = _norm_tags(args.get("tags"))
    visibility = str(args.get("visibility") or "").strip().lower()

    rows = load_jsonl(_listings_jsonl(basepath))
    latest: Dict[str, Dict[str, Any]] = {}
    for r in rows:
        if not isinstance(r, dict):
            continue
        rid = str(r.get("id") or "").strip()
        if rid:
            latest[rid] = r

    out: List[Dict[str, Any]] = []
    for r in latest.values():
        if r.get("tombstone") is True:
            continue
        if visibility and str(r.get("visibility") or "").lower() != visibility:
            continue
        if tags:
            rt = [str(x) for x in (r.get("tags") or [])]
            if not all(t in rt for t in tags):
                continue

        blob = " ".join([
            str(r.get("title") or ""),
            str(r.get("object_ref") or ""),
            " ".join([str(x) for x in (r.get("tags") or [])]),
        ])
        if not _kw_match(blob, query):
            continue
        out.append(r)

    out.sort(key=lambda x: str(x.get("ts") or ""), reverse=True)
    return {"success": True, "items": out[:limit]}

def nisb_market_get(args: Dict[str, Any]) -> Dict[str, Any]:
    basepath = _get_basepath(args)
    listing_id = str(args.get("listing_id") or "").strip()
    if not listing_id:
        return {"success": False, "message": "missing listing_id"}

    rows = load_jsonl(_listings_jsonl(basepath))
    for r in reversed(rows):
        if isinstance(r, dict) and str(r.get("id") or "") == listing_id:
            return {"success": True, "listing": r}
    return {"success": False, "message": "listing not found"}

def nisb_market_event(args: Dict[str, Any]) -> Dict[str, Any]:
    basepath = _get_basepath(args)
    _ensure_dir(_market_root(basepath))

    action = str(args.get("action") or "").strip()
    if not action:
        return {"success": False, "message": "missing action"}

    evt = {
        "id": _new_id("evt"),
        "ts": _utc_iso(),
        "action": action,
        "listing_id": str(args.get("listing_id") or "").strip() or None,
        "object_ref": str(args.get("object_ref") or "").strip() or None,
        "actor": str(args.get("actor") or "user").strip(),
        "payload": args.get("payload") if isinstance(args.get("payload"), dict) else {},
    }
    append_jsonl(_events_jsonl(basepath), evt)
    return {"success": True, "event": evt}

