from __future__ import annotations

import math
import os
import time
import heapq
from array import array
from collections import OrderedDict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from .semantic_index import (
    _read_jsonl,
    _tokenize,
    _hash_vec,
    rebuild_index,
    rss_index_path,
    get_uid_from_ctx,
)

# LRU cache (uid -> entry)
# entry = {"mtime": float, "loaded_at": float, "rows": List[Dict[str, Any]], "by_id": Dict[str, Dict[str, Any]], "idx_path": str}
_INDEX_CACHE: "OrderedDict[str, Dict[str, Any]]" = OrderedDict()

_SEMANTIC_CACHE_MAX_UIDS = int(os.getenv("NISB_RSS_SEMANTIC_CACHE_MAX_UIDS", "2") or 2)
_INDEX_RELOAD_MIN_INTERVAL_SECONDS = float(os.getenv("NISB_RSS_INDEX_RELOAD_MIN_INTERVAL_SECONDS", "30") or 30)


def _parse_ts_any(s: Any) -> Optional[float]:
    ss = str(s or "").strip()
    if not ss:
        return None
    try:
        dt = datetime.fromisoformat(ss.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return float(dt.timestamp())
    except Exception:
        pass
    try:
        v = float(ss)
        if v > 10_000_000_000:
            v = v / 1000.0
        return float(v)
    except Exception:
        return None


def _recency_boost(published_at: str, fetched_at: str, half_life_days: float = 7.0) -> float:
    now = time.time()
    ts = _parse_ts_any(published_at) or _parse_ts_any(fetched_at)
    if not ts:
        return 1.0
    age_days = max(0.0, (now - ts) / 86400.0)
    return 0.65 + 0.35 * math.exp(-age_days / max(0.1, half_life_days))


def _time_window_ok(
    row: Dict[str, Any],
    *,
    now_ts: float,
    days: int,
    start_ts: Optional[float],
    end_ts: Optional[float],
) -> bool:
    ts = _parse_ts_any(row.get("published_at")) or _parse_ts_any(row.get("fetched_at"))
    if start_ts is not None:
        if ts is None or ts < start_ts:
            return False
    if end_ts is not None:
        if ts is None or ts > end_ts:
            return False
    if days > 0:
        if ts is None:
            return False
        if (now_ts - ts) > (days * 86400):
            return False
    return True


def _cosine_f32(a: array, b: array) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    s = 0.0
    for x, y in zip(a, b):
        s += float(x) * float(y)
    return float(s)


def _cache_get(uid: str) -> Optional[Dict[str, Any]]:
    ent = _INDEX_CACHE.get(uid)
    if ent is None:
        return None
    try:
        _INDEX_CACHE.move_to_end(uid, last=True)
    except Exception:
        pass
    return ent


def _cache_set(uid: str, entry: Dict[str, Any]) -> None:
    _INDEX_CACHE[uid] = entry
    try:
        _INDEX_CACHE.move_to_end(uid, last=True)
    except Exception:
        pass

    max_uids = max(0, int(_SEMANTIC_CACHE_MAX_UIDS or 0))
    if max_uids <= 0:
        _INDEX_CACHE.clear()
        return

    while len(_INDEX_CACHE) > max_uids:
        try:
            _INDEX_CACHE.popitem(last=False)
        except Exception:
            break


def _load_index_rows_cached(uid: str, *, allow_rebuild: bool) -> Tuple[List[Dict[str, Any]], Dict[str, Dict[str, Any]], str]:
    idx_path = rss_index_path(uid)

    if not os.path.exists(idx_path):
        if allow_rebuild:
            try:
                rebuild_index(uid)
            except Exception:
                return ([], {}, idx_path)
        else:
            return ([], {}, idx_path)

    try:
        mtime = os.path.getmtime(idx_path)
    except Exception:
        mtime = 0.0

    now_ts = time.time()
    cached = _cache_get(uid)

    if isinstance(cached, dict) and float(cached.get("mtime") or 0.0) == float(mtime) and isinstance(cached.get("rows"), list) and isinstance(cached.get("by_id"), dict):
        return (cached["rows"], cached["by_id"], idx_path)

    # 冷却期：索引文件频繁 append 时，不要每次搜索都触发“全量重载”
    if isinstance(cached, dict) and isinstance(cached.get("rows"), list) and isinstance(cached.get("by_id"), dict):
        loaded_at = float(cached.get("loaded_at") or 0.0)
        if (now_ts - loaded_at) < max(0.0, float(_INDEX_RELOAD_MIN_INTERVAL_SECONDS or 0.0)):
            return (cached["rows"], cached["by_id"], idx_path)

    last_by_id: Dict[str, Dict[str, Any]] = {}
    for row in _read_jsonl(idx_path):
        if not isinstance(row, dict):
            continue
        rid = str(row.get("id") or "").strip()
        if not rid:
            continue
        last_by_id[rid] = row

    rows: List[Dict[str, Any]] = []
    by_id: Dict[str, Dict[str, Any]] = {}

    for rid, row in last_by_id.items():
        emb = row.get("embedding")
        if not isinstance(emb, list) or len(emb) != 512:
            continue
        url = str(row.get("url") or "").strip()
        if not url:
            continue

        try:
            emb_f32 = array("f", [float(x) for x in emb])
        except Exception:
            continue
        if len(emb_f32) != 512:
            continue

        text = str(row.get("text") or "")
        snippet_text = text[:360]

        item = {
            "id": rid,
            "feed_id": str(row.get("feed_id") or "").strip(),
            "title": row.get("title") or "",
            "url": url,
            "published_at": row.get("published_at") or "",
            "fetched_at": row.get("fetched_at") or "",
            "embedding": emb_f32,
            "snippet_text": snippet_text,
        }
        rows.append(item)
        by_id[rid] = item

    _cache_set(uid, {"mtime": float(mtime), "loaded_at": float(now_ts), "rows": rows, "by_id": by_id, "idx_path": idx_path})
    return (rows, by_id, idx_path)

def _semantic_search(
    ctx: Any,
    query: str,
    *,
    limit: int = 8,
    uid: Optional[str] = None,
    feed_ids: Optional[List[str]] = None,
    days: int = 0,
    start_ts: Optional[float] = None,
    end_ts: Optional[float] = None,
    candidate_ids: Optional[List[str]] = None,
) -> Dict[str, Any]:
    uid2 = get_uid_from_ctx(ctx, uid)

    q = str(query or "").strip()
    if not q:
        return {"success": True, "items": []}

    try:
        k = int(limit or 8)
    except Exception:
        k = 8
    k = max(1, min(200, k))

    feed_set = set([str(x).strip() for x in (feed_ids or []) if str(x).strip()])

    allow_rebuild = str(os.getenv("NISB_RSS_SEMANTIC_AUTO_REBUILD", "0")).strip() in ("1", "true", "True")
    rows, by_id, idx_path = _load_index_rows_cached(uid2, allow_rebuild=allow_rebuild)

    try:
        qvec = array("f", _hash_vec(_tokenize(q), dim=512))
    except Exception:
        qvec = array("f", [0.0] * 512)

    now_ts = time.time()

    # IMPORTANT: add tie-breaker to avoid dict-vs-dict compare when score ties
    heap: List[Tuple[float, int, Dict[str, Any]]] = []
    tie = 0

    cand = [str(x).strip() for x in (candidate_ids or []) if str(x).strip()]
    if cand:
        for rid in cand:
            row = by_id.get(rid)
            if not isinstance(row, dict):
                continue

            if feed_set:
                fid = str(row.get("feed_id") or "")
                if fid not in feed_set:
                    continue

            if not _time_window_ok(row, now_ts=now_ts, days=int(days or 0), start_ts=start_ts, end_ts=end_ts):
                continue

            emb = row.get("embedding")
            if not isinstance(emb, array) or len(emb) != 512:
                continue

            base = _cosine_f32(qvec, emb)
            boost = _recency_boost(str(row.get("published_at") or ""), str(row.get("fetched_at") or ""))
            score = float(base * boost)

            item = {
                "id": row.get("id") or "",
                "feed_id": row.get("feed_id") or "",
                "title": row.get("title") or "",
                "url": row.get("url") or "",
                "published_at": row.get("published_at") or "",
                "score": score,
                "snippet": str(row.get("snippet_text") or ""),
            }

            tie += 1
            if len(heap) < k:
                heapq.heappush(heap, (score, tie, item))
            else:
                if score > heap[0][0]:
                    heapq.heapreplace(heap, (score, tie, item))
    else:
        for row in rows:
            try:
                if feed_set:
                    fid = str(row.get("feed_id") or "")
                    if fid not in feed_set:
                        continue

                if not _time_window_ok(row, now_ts=now_ts, days=int(days or 0), start_ts=start_ts, end_ts=end_ts):
                    continue

                emb = row.get("embedding")
                if not isinstance(emb, array) or len(emb) != 512:
                    continue

                base = _cosine_f32(qvec, emb)
                boost = _recency_boost(str(row.get("published_at") or ""), str(row.get("fetched_at") or ""))
                score = float(base * boost)

                item = {
                    "id": row.get("id") or "",
                    "feed_id": row.get("feed_id") or "",
                    "title": row.get("title") or "",
                    "url": row.get("url") or "",
                    "published_at": row.get("published_at") or "",
                    "score": score,
                    "snippet": str(row.get("snippet_text") or ""),
                }

                tie += 1
                if len(heap) < k:
                    heapq.heappush(heap, (score, tie, item))
                else:
                    if score > heap[0][0]:
                        heapq.heapreplace(heap, (score, tie, item))
            except Exception:
                continue

    heap.sort(key=lambda x: x[0], reverse=True)
    out_items = [x[2] for x in heap]
    return {"success": True, "items": out_items, "index_path": idx_path, "candidate_mode": bool(cand)}

def nisb_rss_semantic_search(*args: Any, **kwargs: Any) -> Dict[str, Any]:
    """
    Gateway entry.

    Preferred style:
      nisb_rss_semantic_search({"query": "...", "limit": 8, "uid": "...", "feed_ids": [...], "days": 30, "start_ts": ..., "end_ts": ..., "candidate_ids": [...]})
    """
    if len(args) == 1 and isinstance(args[0], dict):
        d: Dict[str, Any] = dict(args[0] or {})
        if kwargs:
            d.update(kwargs)

        query = str(d.get("query") or "").strip()
        if not query:
            return {"success": True, "items": []}

        try:
            limit = int(d.get("limit", 8))
        except Exception:
            limit = 8

        uid = d.get("uid")
        uid = str(uid).strip() if uid is not None and str(uid).strip() else None

        ctx = d.get("ctx", d)

        feed_ids = d.get("feed_ids")
        if not isinstance(feed_ids, list):
            feed_ids = []
        feed_ids = [str(x).strip() for x in feed_ids if str(x).strip()]

        try:
            days = int(d.get("days") or 0)
        except Exception:
            days = 0

        start_ts = d.get("start_ts")
        end_ts = d.get("end_ts")
        try:
            start_ts = float(start_ts) if start_ts is not None else None
        except Exception:
            start_ts = None
        try:
            end_ts = float(end_ts) if end_ts is not None else None
        except Exception:
            end_ts = None

        candidate_ids = d.get("candidate_ids")
        if not isinstance(candidate_ids, list):
            candidate_ids = []
        candidate_ids = [str(x).strip() for x in candidate_ids if str(x).strip()]

        return _semantic_search(
            ctx=ctx,
            query=query,
            limit=limit,
            uid=uid,
            feed_ids=feed_ids,
            days=days,
            start_ts=start_ts,
            end_ts=end_ts,
            candidate_ids=candidate_ids,
        )

    # legacy call style kept (but prefer dict style)
    ctx = args[0] if len(args) >= 1 else kwargs.get("ctx")
    query = str(args[1] if len(args) >= 2 else kwargs.get("query") or "")
    limit_raw = args[2] if len(args) >= 3 else kwargs.get("limit", 8)
    try:
        limit = int(limit_raw)
    except Exception:
        limit = 8

    uid = kwargs.get("uid")
    uid = str(uid).strip() if uid is not None and str(uid).strip() else None

    feed_ids = kwargs.get("feed_ids")
    if not isinstance(feed_ids, list):
        feed_ids = []
    feed_ids = [str(x).strip() for x in feed_ids if str(x).strip()]

    try:
        days = int(kwargs.get("days") or 0)
    except Exception:
        days = 0

    start_ts = kwargs.get("start_ts")
    end_ts = kwargs.get("end_ts")
    try:
        start_ts = float(start_ts) if start_ts is not None else None
    except Exception:
        start_ts = None
    try:
        end_ts = float(end_ts) if end_ts is not None else None
    except Exception:
        end_ts = None

    candidate_ids = kwargs.get("candidate_ids")
    if not isinstance(candidate_ids, list):
        candidate_ids = []
    candidate_ids = [str(x).strip() for x in candidate_ids if str(x).strip()]

    return _semantic_search(
        ctx=ctx,
        query=query,
        limit=limit,
        uid=uid,
        feed_ids=feed_ids,
        days=days,
        start_ts=start_ts,
        end_ts=end_ts,
        candidate_ids=candidate_ids,
    )

