from __future__ import annotations

import os
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from core.storage import load_json, save_json
from .tools import nisb_rss_fetch


def _utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_iso_ts(s: str) -> Optional[float]:
    ss = str(s or "").strip()
    if not ss:
        return None
    try:
        dt = datetime.fromisoformat(ss.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.timestamp()
    except Exception:
        return None


def _get_basepath(args: Dict[str, Any]) -> str:
    bp = (
        args.get("basepath")
        or args.get("base_path")
        or args.get("_base_path")
        or args.get("basePath")
        or args.get("_basePath")
    )
    bp = str(bp or "").strip()
    if bp:
        return bp
    return "/data/users/unknown"


def _feeds_json_path(basepath: str) -> str:
    return os.path.join(basepath, "rss", "feeds.json")


def _load_feeds_doc(basepath: str) -> Dict[str, Any]:
    path = _feeds_json_path(basepath)
    if not os.path.exists(path):
        return {"feeds": []}
    doc = load_json(path)
    if not isinstance(doc, dict):
        return {"feeds": []}
    if not isinstance(doc.get("feeds"), list):
        doc["feeds"] = []
    return doc


def _save_feeds_doc(basepath: str, doc: Dict[str, Any]) -> bool:
    path = _feeds_json_path(basepath)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if not isinstance(doc, dict):
        doc = {"feeds": []}
    if not isinstance(doc.get("feeds"), list):
        doc["feeds"] = []
    return save_json(path, doc)


def _interval_minutes_for_feed(feed: Dict[str, Any], default_interval_minutes: int) -> int:
    v = (
        feed.get("fetch_interval_minutes")
        or feed.get("fetchintervalminutes")
        or feed.get("fetchIntervalMinutes")
    )
    try:
        if v is None or v == "":
            return int(default_interval_minutes or 0)
        return int(v)
    except Exception:
        return int(default_interval_minutes or 0)


def _is_due(feed: Dict[str, Any], interval_minutes: int, now_ts: float) -> bool:
    if interval_minutes <= 0:
        return False

    last = (
        feed.get("last_fetch_at")
        or feed.get("last_fetch_due_at")
        or feed.get("lastfetchat")
        or feed.get("lastfetchdueat")
        or ""
    )
    last_ts = _parse_iso_ts(str(last))
    if last_ts is None:
        return True

    return (now_ts - last_ts) >= (interval_minutes * 60)


def _is_enabled(feed: Dict[str, Any]) -> bool:
    v = feed.get("enabled")
    if v is None:
        return True
    return bool(v)


def nisb_rss_fetch_due(args: Dict[str, Any]) -> Dict[str, Any]:
    basepath = _get_basepath(args)

    try:
        default_interval_minutes = int(args.get("default_interval_minutes") or args.get("defaultintervalminutes") or 0)
    except Exception:
        default_interval_minutes = 0

    try:
        limit_entries = int(args.get("limit_entries") or args.get("limitentries") or 50)
    except Exception:
        limit_entries = 50
    limit_entries = max(1, min(200, limit_entries))

    now_ts = args.get("now_ts") or args.get("nowts")
    try:
        now_ts = float(now_ts) if now_ts is not None else time.time()
    except Exception:
        now_ts = time.time()

    force = bool(args.get("force") or args.get("force_all") or args.get("forceall") or args.get("force_fetch") or False)

    doc = _load_feeds_doc(basepath)
    feeds: List[Dict[str, Any]] = list(doc.get("feeds") or [])

    due_feed_ids: List[str] = []
    total_feeds = 0
    enabled_feeds = 0

    for f in feeds:
        if not isinstance(f, dict):
            continue
        total_feeds += 1

        feed_id = str(f.get("feed_id") or f.get("feedid") or "").strip()
        if not feed_id:
            continue

        if _is_enabled(f):
            enabled_feeds += 1
        else:
            continue

        if force:
            due_feed_ids.append(feed_id)
            continue

        interval_minutes = _interval_minutes_for_feed(f, default_interval_minutes)
        if _is_due(f, interval_minutes, now_ts):
            due_feed_ids.append(feed_id)

    fetched = 0
    failed = 0
    total_new = 0

    for feed_id in due_feed_ids:
        try:
            rr = nisb_rss_fetch({
                "basepath": basepath,
                "base_path": basepath,
                "_base_path": basepath,
                "feed_id": feed_id,
                "feedid": feed_id,
                "limit_entries": limit_entries,
                "limitentries": limit_entries,
            })
            ok = bool(rr.get("success", False))
            if ok:
                fetched += 1
            else:
                failed += 1

            stats = rr.get("stats") if isinstance(rr, dict) else None
            if isinstance(stats, dict):
                total_new += int(stats.get("new") or stats.get("new_entries") or stats.get("total_new") or 0)

        except Exception:
            failed += 1

    if due_feed_ids:
        latest = _load_feeds_doc(basepath)
        latest_feeds = latest.get("feeds") or []
        now_iso = _utc_iso()

        due_set = set(due_feed_ids)
        for f in latest_feeds:
            if not isinstance(f, dict):
                continue
            fid = str(f.get("feed_id") or f.get("feedid") or "").strip()
            if fid and fid in due_set:
                f["last_fetch_due_at"] = now_iso

        latest["feeds"] = latest_feeds
        _save_feeds_doc(basepath, latest)

    if not due_feed_ids:
        status = "skipped"
    elif failed > 0:
        status = "partial_failure"
    else:
        status = "ok"

    return {
        "success": True,
        "status": status,
        "had_failures": bool(failed > 0),
        "stats": {
            "total_feeds": total_feeds,
            "enabled_feeds": enabled_feeds,
            "due": len(due_feed_ids),
            "fetched": fetched,
            "failed": failed,
            "total_new": total_new,
            "default_interval_minutes": int(default_interval_minutes or 0),
            "limit_entries": int(limit_entries or 0),
            "force": force,
        },
        "due_feed_ids": due_feed_ids,
        "now_ts": now_ts,
    }
