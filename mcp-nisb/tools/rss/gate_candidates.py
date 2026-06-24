from __future__ import annotations

import os
import time
import json
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple, Iterator, Set

from core.storage import load_jsonl

from .tools import (
    _get_basepath,
    _rss_root,
    _uid_from_basepath,
    _feeds_lock,
    _read_feeds_strict,
    _feed_articles_jsonl,
    _rss_query_terms,
    _rss_score_row,
    _article_content_md,
)
from .semantic_search import nisb_rss_semantic_search

_SPAM_CACHE: Dict[str, Dict[str, Any]] = {}

_WORD_RE = re.compile(r"[a-z0-9]{2,}", re.IGNORECASE)
_ZH_RE = re.compile(r"[\u4e00-\u9fff]{2,}")

_EN_STOPWORDS = {
    "what", "news", "there", "today", "yesterday", "this", "that",
    "in", "on", "at", "is", "are", "was", "were", "the", "a", "an",
    "of", "to", "for", "and", "or", "about", "from", "with",
    "latest", "recent", "update", "updates",
}


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


def _parse_date_floor_utc(s: str) -> Optional[float]:
    ss = str(s or "").strip()
    if not ss:
        return None
    try:
        dt = datetime.strptime(ss[:10], "%Y-%m-%d").replace(tzinfo=timezone.utc)
        return float(dt.timestamp())
    except Exception:
        pass
    try:
        dt = datetime.fromisoformat(ss.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        dt = dt.replace(hour=0, minute=0, second=0, microsecond=0)
        return float(dt.timestamp())
    except Exception:
        return None


def _parse_date_ceil_utc(s: str) -> Optional[float]:
    lo = _parse_date_floor_utc(s)
    if lo is None:
        return None
    return float(lo + 86399.999)


def _within_days(ts: Optional[float], days: int, *, now_ts: float) -> bool:
    if days <= 0:
        return True
    if not ts:
        return False
    return (now_ts - float(ts)) <= (days * 86400)


def _spam_path(basepath: str) -> str:
    return os.path.join(_rss_root(basepath), "rss_spam_blacklist.jsonl")


def _load_spam_active_cached(basepath: str) -> Dict[str, Dict[str, Any]]:
    path = _spam_path(basepath)
    try:
        mtime = os.path.getmtime(path) if os.path.exists(path) else 0.0
    except Exception:
        mtime = 0.0

    cached = _SPAM_CACHE.get(basepath)
    if isinstance(cached, dict) and float(cached.get("mtime") or 0.0) == float(mtime) and isinstance(cached.get("active"), dict):
        return cached["active"]

    rows = load_jsonl(path) or []
    latest: Dict[str, Dict[str, Any]] = {}
    for r in rows:
        if not isinstance(r, dict):
            continue
        rid = str(r.get("rule_id") or "").strip()
        if not rid:
            continue
        latest[rid] = r

    active: Dict[str, Dict[str, Any]] = {}
    for rid, r in latest.items():
        if bool(r.get("tombstone", False)) is True:
            continue
        if str(r.get("type") or "") != "rss_spam_rule":
            continue
        active[rid] = r

    _SPAM_CACHE[basepath] = {"mtime": float(mtime), "active": active}
    return active


def _norm_domain(url: str) -> str:
    u = str(url or "").strip()
    if not u:
        return ""
    try:
        if "://" in u:
            u2 = u.split("://", 1)[1]
        else:
            u2 = u
        host = u2.split("/", 1)[0].strip().lower()
        host = host.split("@", 1)[-1]
        host = host.split(":", 1)[0]
        return host
    except Exception:
        return ""


def _is_spam(active_rules: Dict[str, Dict[str, Any]], *, feed_id: str, article_id: str, url: str) -> bool:
    dom = _norm_domain(url)
    for r in active_rules.values():
        scope = str(r.get("scope") or "").strip().lower()
        if scope == "article":
            if url and str(r.get("url") or "").strip() == url:
                return True
            if article_id and str(r.get("article_id") or "").strip() == article_id:
                return True
        elif scope == "feed":
            if feed_id and str(r.get("feed_id") or "").strip() == feed_id:
                return True
        elif scope == "domain":
            if dom and str(r.get("domain") or "").strip().lower() == dom:
                return True
    return False


def _keyword_score_norm(raw: int, terms_len: int) -> float:
    if raw <= 0:
        return 0.0
    denom = max(6.0, 3.0 * float(max(1, terms_len)))
    return min(1.0, 0.6 + float(raw) / denom)


def _pick_list_arg(args: Dict[str, Any], key: str) -> List[str]:
    v = args.get(key)
    if not isinstance(v, list):
        return []
    out: List[str] = []
    for x in v:
        s = str(x or "").strip()
        if s:
            out.append(s)
    return out


def _query_groups(query: str) -> List[List[str]]:
    q = str(query or "").strip()
    if not q:
        return []

    groups: List[List[str]] = []
    seen: Set[str] = set()

    for w in _WORD_RE.findall(q.lower()):
        if w in _EN_STOPWORDS:
            continue
        key = f"en:{w}"
        if key in seen:
            continue
        seen.add(key)
        groups.append([w])

    for zh in _ZH_RE.findall(q):
        z = str(zh or "").strip()
        if not z:
            continue
        key = f"zh:{z}"
        if key in seen:
            continue
        seen.add(key)
        groups.append([z])

    return groups


def _match_groups_all(row: Dict[str, Any], groups: List[List[str]]) -> bool:
    if not groups:
        return True
    title = str(row.get("title") or "")
    excerpt = str(row.get("excerpt") or "")
    text = f"{title}\n{excerpt}".lower()

    for g in groups:
        ok = False
        for term in g:
            t = str(term or "").strip().lower()
            if t and t in text:
                ok = True
                break
        if not ok:
            return False
    return True


def _match_groups_any(row: Dict[str, Any], groups: List[List[str]]) -> bool:
    if not groups:
        return True
    title = str(row.get("title") or "")
    excerpt = str(row.get("excerpt") or "")
    text = f"{title}\n{excerpt}".lower()

    for g in groups:
        for term in g:
            t = str(term or "").strip().lower()
            if t and t in text:
                return True
    return False


def _iter_jsonl_stream(path: str) -> Iterator[Dict[str, Any]]:
    if not path or not os.path.exists(path):
        return
        yield  # pragma: no cover
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                s = line.strip()
                if not s:
                    continue
                try:
                    obj = json.loads(s)
                except Exception:
                    continue
                if isinstance(obj, dict):
                    yield obj
    except Exception:
        return


def _iter_lines_reverse_bytes(path: str, block_size: int = 1024 * 1024) -> Iterator[bytes]:
    if not path or not os.path.exists(path):
        return
        yield  # pragma: no cover
    try:
        with open(path, "rb") as f:
            f.seek(0, os.SEEK_END)
            pos = f.tell()
            buf = b""
            while pos > 0:
                n = block_size if pos >= block_size else pos
                pos -= n
                f.seek(pos, os.SEEK_SET)
                chunk = f.read(n)
                if not chunk:
                    break
                buf = chunk + buf
                parts = buf.split(b"\n")
                buf = parts[0]
                for line in reversed(parts[1:]):
                    if line:
                        yield line
            if buf:
                yield buf
    except Exception:
        return


def _iter_jsonl_reverse_until_ts(path: str, *, cutoff_ts: float) -> Iterator[Dict[str, Any]]:
    for bline in _iter_lines_reverse_bytes(path):
        try:
            s = bline.decode("utf-8", errors="ignore").strip()
        except Exception:
            continue
        if not s:
            continue
        try:
            obj = json.loads(s)
        except Exception:
            continue
        if not isinstance(obj, dict):
            continue

        rts = _parse_ts_any(obj.get("ts")) or _parse_ts_any(obj.get("fetched_at")) or _parse_ts_any(obj.get("published_at"))
        if rts is not None and float(rts) < float(cutoff_ts):
            break

        yield obj


def _scan_mode_name(use_reverse_scan: bool, fast_mode: bool) -> str:
    if use_reverse_scan and fast_mode:
        return "reverse_ts_fast"
    if use_reverse_scan:
        return "reverse_ts"
    if fast_mode:
        return "stream_fast"
    return "stream_full"


def _extract_items_from_tool_result(result: Dict[str, Any]) -> List[Dict[str, Any]]:
    if not isinstance(result, dict):
        return []

    tool_results = result.get("tool_results")
    if isinstance(tool_results, list):
        for row in tool_results:
            if not isinstance(row, dict):
                continue
            items = row.get("items")
            if isinstance(items, list):
                return items
            data = row.get("data")
            if isinstance(data, dict) and isinstance(data.get("items"), list):
                return data.get("items") or []

    items = result.get("items")
    if isinstance(items, list):
        return items

    data = result.get("data")
    if isinstance(data, dict) and isinstance(data.get("items"), list):
        return data.get("items") or []

    return []


def _empty_gate_data(
    *,
    query: str,
    sort_by: str,
    match_mode: str,
    groups_count: int,
    scan_mode: str,
    methods: List[str],
    took_ms: int,
    days: int,
    start_date: str,
    end_date: str,
    feed_ids: List[str],
    min_score: float,
    strict_lexical: bool,
    exclude_spam: bool,
    fast_mode: bool,
    scan_cap: int,
    candidate_cap: int,
    warnings: Optional[List[str]] = None,
) -> Dict[str, Any]:
    warnings = [str(x).strip() for x in (warnings or []) if str(x).strip()]
    return {
        "query": query,
        "items": [],
        "next_cursor": "",
        "total": 0,
        "sort_by": sort_by,
        "match_mode": match_mode,
        "groups_count": int(groups_count or 0),
        "scan_mode": scan_mode,
        "methods": list(methods or []),
        "source_stats": [],
        "partial": False,
        "took_ms": int(took_ms or 0),
        "warnings": warnings,
        "filters": {
            "days": int(days or 0),
            "start_date": start_date,
            "end_date": end_date,
            "feed_ids": list(feed_ids or []),
            "min_score": float(min_score or 0.0),
            "strict_lexical": bool(strict_lexical),
            "exclude_spam": bool(exclude_spam),
            "fast_mode": bool(fast_mode),
            "scan_cap": int(scan_cap or 0),
            "candidate_cap": int(candidate_cap or 0),
        },
    }


def _build_gate_success(
    *,
    page: List[Dict[str, Any]],
    total: int,
    next_cursor: str,
    sort_by: str,
    match_mode: str,
    groups_count: int,
    scan_mode: str,
    methods: List[str],
    query: str,
    days: int,
    start_date: str,
    end_date: str,
    feed_ids: List[str],
    min_score: float,
    strict_lexical: bool,
    exclude_spam: bool,
    fast_mode: bool,
    scan_cap: int,
    candidate_cap: int,
    took_ms: int,
    warnings: Optional[List[str]] = None,
) -> Dict[str, Any]:
    warnings = [str(x).strip() for x in (warnings or []) if str(x).strip()]
    source_name = "+".join(methods) if methods else "rss_gate"
    source_stats = [
        {
            "source": source_name,
            "status": "success",
            "count": len(page),
            "total": int(total or 0),
            "took_ms": int(took_ms or 0),
            "partial": False,
            "error": "",
            "warnings": warnings,
        }
    ]

    data = {
        "query": query,
        "items": page,
        "next_cursor": next_cursor,
        "total": int(total or 0),
        "sort_by": sort_by,
        "match_mode": match_mode,
        "groups_count": int(groups_count or 0),
        "scan_mode": scan_mode,
        "methods": list(methods or []),
        "source_stats": source_stats,
        "partial": False,
        "took_ms": int(took_ms or 0),
        "warnings": warnings,
        "filters": {
            "days": int(days or 0),
            "start_date": start_date,
            "end_date": end_date,
            "feed_ids": list(feed_ids or []),
            "min_score": float(min_score or 0.0),
            "strict_lexical": bool(strict_lexical),
            "exclude_spam": bool(exclude_spam),
            "fast_mode": bool(fast_mode),
            "scan_cap": int(scan_cap or 0),
            "candidate_cap": int(candidate_cap or 0),
        },
    }

    response = f"RSS Gate 搜索完成：当前页 {len(page)} 条，共 {int(total or 0)} 条"

    out = {
        "status": "success",
        "response": response,
        "message": "",
        "tool_calls": [],
        "tool_results": [
            {
                "type": "rss_gate_candidates",
                "response": response,
                "message": "",
                "items": page,
                "next_cursor": next_cursor,
                "total": int(total or 0),
                "sort_by": sort_by,
                "match_mode": match_mode,
                "groups_count": int(groups_count or 0),
                "scan_mode": scan_mode,
                "methods": list(methods or []),
                "source_stats": source_stats,
                "partial": False,
                "took_ms": int(took_ms or 0),
                "warnings": warnings,
                "data": data,
            }
        ],
        # legacy compatibility mirrors
        "success": True,
        "items": page,
        "next_cursor": next_cursor,
        "total": int(total or 0),
        "sort_by": sort_by,
        "match_mode": match_mode,
        "groups_count": int(groups_count or 0),
        "scan_mode": scan_mode,
        "methods": list(methods or []),
        "source_stats": source_stats,
        "partial": False,
        "took_ms": int(took_ms or 0),
    }
    return out


def _build_gate_error(message: str) -> Dict[str, Any]:
    text = str(message or "").strip() or "RSS Gate 搜索失败"
    data = _empty_gate_data(
        query="",
        sort_by="relevance",
        match_mode="any",
        groups_count=0,
        scan_mode="stream_full",
        methods=[],
        took_ms=0,
        days=30,
        start_date="",
        end_date="",
        feed_ids=[],
        min_score=0.35,
        strict_lexical=True,
        exclude_spam=True,
        fast_mode=False,
        scan_cap=0,
        candidate_cap=0,
        warnings=[],
    )
    return {
        "status": "error",
        "response": text,
        "message": text,
        "tool_calls": [],
        "tool_results": [
            {
                "type": "rss_gate_candidates",
                "response": text,
                "message": text,
                "items": [],
                "next_cursor": "",
                "total": 0,
                "sort_by": "relevance",
                "match_mode": "any",
                "groups_count": 0,
                "scan_mode": "stream_full",
                "methods": [],
                "source_stats": [],
                "partial": False,
                "took_ms": 0,
                "warnings": [],
                "data": data,
            }
        ],
        # legacy compatibility mirrors
        "success": False,
        "items": [],
        "next_cursor": "",
        "total": 0,
        "sort_by": "relevance",
        "match_mode": "any",
        "groups_count": 0,
        "scan_mode": "stream_full",
        "methods": [],
        "source_stats": [],
        "partial": False,
        "took_ms": 0,
    }


def nisb_rss_gate_candidates(args: Dict[str, Any]) -> Dict[str, Any]:
    started_at = time.time()

    basepath = _get_basepath(args)
    uid = _uid_from_basepath(basepath)
    if not uid:
        return _build_gate_error("Cannot resolve uid from basepath")

    query = str(args.get("query") or "").strip()

    try:
        days = int(args.get("days", 30) or 30)
    except Exception:
        days = 30

    start_date = str(args.get("start_date") or "").strip()
    end_date = str(args.get("end_date") or "").strip()
    start_ts = _parse_date_floor_utc(start_date) if start_date else None
    end_ts = _parse_date_ceil_utc(end_date) if end_date else None

    limit = int(args.get("limit", 50) or 50)
    limit = max(1, min(200, limit))

    cursor_raw = str(args.get("cursor") or "").strip()
    try:
        offset = int(cursor_raw) if cursor_raw else 0
    except Exception:
        offset = 0
    offset = max(0, offset)

    methods = args.get("methods")
    if isinstance(methods, str):
        methods = [methods]
    if not isinstance(methods, list) or not methods:
        methods = ["hybrid"]
    methods = [str(x).strip().lower() for x in methods if str(x).strip()]
    methods = [m for m in methods if m in ("keyword", "semantic", "hybrid")]
    if not methods:
        methods = ["hybrid"]

    try:
        min_score = float(args.get("min_score", 0.35))
    except Exception:
        min_score = 0.35
    min_score = max(0.0, min(1.0, min_score))

    strict_lexical = bool(args.get("strict_lexical", True))
    exclude_spam = bool(args.get("exclude_spam", True))
    fast_mode = bool(args.get("fast_mode", False))

    try:
        scan_cap = int(args.get("scan_cap", 0) or 0)
    except Exception:
        scan_cap = 0

    try:
        candidate_cap = int(args.get("candidate_cap", 0) or 0)
    except Exception:
        candidate_cap = 0

    if scan_cap <= 0:
        if fast_mode:
            scan_cap = max(800, limit * 40)
        else:
            scan_cap = 12000

    if candidate_cap <= 0:
        if fast_mode:
            candidate_cap = max(120, limit * 6)
        else:
            candidate_cap = 2000

    scan_cap = max(500, min(50000, scan_cap))
    candidate_cap = max(100, min(10000, candidate_cap))

    feed_ids = _pick_list_arg(args, "feed_ids")
    feed_ids = list(dict.fromkeys(feed_ids))

    groups = _query_groups(query)
    terms = _rss_query_terms(query)

    match_mode = str(args.get("match_mode") or "any").lower().strip() or "any"
    if match_mode not in ("any", "all"):
        match_mode = "any"
    if (args.get("match_mode") is None) and (len(groups) >= 2):
        match_mode = "all"

    sort_by = str(args.get("sort_by") or "relevance").lower().strip() or "relevance"
    if sort_by in ("published", "published_at", "newest", "recent"):
        sort_by = "published_at"
    if sort_by not in ("relevance", "published_at"):
        sort_by = "relevance"

    if not query:
        took_ms = int((time.time() - started_at) * 1000)
        return _build_gate_success(
            page=[],
            total=0,
            next_cursor="",
            sort_by=sort_by,
            match_mode=match_mode,
            groups_count=0,
            scan_mode=_scan_mode_name(False, fast_mode),
            methods=methods,
            query="",
            days=days,
            start_date=start_date,
            end_date=end_date,
            feed_ids=feed_ids,
            min_score=min_score,
            strict_lexical=strict_lexical,
            exclude_spam=exclude_spam,
            fast_mode=fast_mode,
            scan_cap=scan_cap,
            candidate_cap=candidate_cap,
            took_ms=took_ms,
            warnings=[],
        )

    if not feed_ids:
        try:
            with _feeds_lock(basepath):
                feeds_doc = _read_feeds_strict(basepath)
        except Exception as e:
            return _build_gate_error(f"feeds.json invalid/unreadable: {e}")

        for f in feeds_doc.get("feeds", []) or []:
            if not isinstance(f, dict):
                continue
            if bool(f.get("enabled", True)) is not True:
                continue
            fid = str(f.get("feed_id") or "").strip()
            if fid:
                feed_ids.append(fid)

    spam_active = _load_spam_active_cached(basepath) if exclude_spam else {}

    semantic_only = ("semantic" in methods) and ("keyword" not in methods) and ("hybrid" not in methods)
    lexical_prefilter_any = (not semantic_only) or bool(strict_lexical)

    now_ts = time.time()
    use_reverse_scan = (start_ts is None and end_ts is None and int(days or 0) > 0)
    cutoff_ts = float(now_ts - (int(days) * 86400)) if use_reverse_scan else 0.0

    local_rows: Dict[Tuple[str, str], Dict[str, Any]] = {}
    warnings: List[str] = []
    rows_examined = 0
    fast_collect_goal = max(limit * 4, 80) if fast_mode else 0
    stop_scan = False

    for fid in feed_ids:
        if stop_scan:
            break

        path = _feed_articles_jsonl(basepath, fid)
        row_iter = _iter_jsonl_reverse_until_ts(path, cutoff_ts=cutoff_ts) if use_reverse_scan else _iter_jsonl_stream(path)

        for r in row_iter:
            rows_examined += 1
            if scan_cap > 0 and rows_examined > scan_cap:
                warnings.append(f"scan_cap_reached:{scan_cap}")
                stop_scan = True
                break

            aid = str(r.get("article_id") or "").strip()
            if not aid:
                continue

            ts = (
                _parse_ts_any(r.get("published_at"))
                or _parse_ts_any(r.get("ts"))
                or _parse_ts_any(r.get("fetched_at"))
            )

            if start_ts is not None and (ts is None or ts < start_ts):
                continue
            if end_ts is not None and (ts is None or ts > end_ts):
                continue
            if not _within_days(ts, days, now_ts=now_ts):
                continue

            title = str(r.get("title") or "").strip()
            url = str(r.get("link") or r.get("url") or "").strip()
            excerpt = str(r.get("excerpt") or "").strip()
            published_at = str(r.get("published_at") or "").strip()

            if exclude_spam and _is_spam(spam_active, feed_id=fid, article_id=aid, url=url):
                continue

            row = {
                "feed_id": fid,
                "article_id": aid,
                "title": title,
                "url": url,
                "published_at": published_at,
                "excerpt": excerpt,
                "_ts": float(ts or 0.0),
            }

            if match_mode == "all":
                if not _match_groups_all(row, groups):
                    continue
            else:
                if lexical_prefilter_any and not _match_groups_any(row, groups):
                    continue

            md_path = _article_content_md(basepath, fid, aid)
            if not os.path.exists(md_path):
                continue

            key = (fid, aid)
            prev = local_rows.get(key)
            prev_ts = float(prev.get("_ts") or 0.0) if isinstance(prev, dict) else 0.0
            cur_ts = float(row.get("_ts") or 0.0)
            if prev is not None and cur_ts <= prev_ts:
                continue

            local_rows[key] = row

            if fast_mode and fast_collect_goal > 0 and len(local_rows) >= fast_collect_goal:
                warnings.append(f"fast_goal_reached:{fast_collect_goal}")
                stop_scan = True
                break

    if candidate_cap > 0 and len(local_rows) > candidate_cap:
        sorted_keys = sorted(
            local_rows.keys(),
            key=lambda k: float((local_rows.get(k) or {}).get("_ts") or 0.0),
            reverse=True,
        )
        keep = set(sorted_keys[:candidate_cap])
        local_rows = {k: local_rows[k] for k in sorted_keys if k in keep}
        warnings.append(f"candidate_cap_applied:{candidate_cap}")

    keyword_scores: Dict[Tuple[str, str], Dict[str, Any]] = {}
    if "keyword" in methods or "hybrid" in methods:
        for k, row in local_rows.items():
            raw = _rss_score_row(row.get("title", ""), row.get("excerpt", ""), terms)
            if raw <= 0:
                continue
            keyword_scores[k] = {
                "keyword_raw": raw,
                "keyword_score": _keyword_score_norm(raw, len(terms)),
            }

    semantic_scores: Dict[Tuple[str, str], Dict[str, Any]] = {}
    if "semantic" in methods or "hybrid" in methods:
        candidate_pairs = sorted(
            local_rows.items(),
            key=lambda kv: float((kv[1] or {}).get("_ts") or 0.0),
            reverse=True,
        )
        candidate_ids = [aid for ((_fid, aid), _row) in candidate_pairs[:candidate_cap]]

        try:
            semantic_cap = int(args.get("semantic_cap", 0) or 0)
        except Exception:
            semantic_cap = 0
        if semantic_cap <= 0:
            semantic_cap = min(candidate_cap, 300)
        semantic_cap = max(50, min(2000, semantic_cap))

        if len(candidate_ids) > semantic_cap:
            candidate_ids = candidate_ids[:semantic_cap]
            warnings.append(f"semantic_cap_applied:{semantic_cap}")

        try:
            sem = nisb_rss_semantic_search(
                {
                    "query": query,
                    "limit": max(50, min(max(limit * 3, limit), max(candidate_cap or 0, limit * 3))),
                    "uid": uid,
                    "feed_ids": feed_ids,
                    "days": int(days or 0),
                    "start_ts": start_ts,
                    "end_ts": end_ts,
                    "candidate_ids": candidate_ids,
                }
            )
            for it in _extract_items_from_tool_result(sem):
                if not isinstance(it, dict):
                    continue
                aid = str(it.get("id") or it.get("article_id") or "").strip()
                fid = str(it.get("feed_id") or "").strip()
                if not aid or not fid:
                    continue
                if (fid, aid) not in local_rows:
                    continue
                try:
                    score = float(it.get("score") or 0.0)
                except Exception:
                    score = 0.0
                semantic_scores[(fid, aid)] = {
                    "semantic_score": score,
                    "semantic_snippet": str(it.get("snippet") or "").strip(),
                }
        except Exception as e:
            warnings.append(f"semantic_search_error:{e}")

    merged: List[Dict[str, Any]] = []
    all_keys = set(local_rows.keys()) | set(semantic_scores.keys())

    for key in all_keys:
        fid, aid = key
        row = local_rows.get(key) or {
            "feed_id": fid,
            "article_id": aid,
            "title": "",
            "url": "",
            "published_at": "",
            "excerpt": "",
            "_ts": 0.0,
        }

        ks = keyword_scores.get(key, {})
        ss = semantic_scores.get(key, {})

        has_kw = "keyword_score" in ks
        has_sem = "semantic_score" in ss

        if strict_lexical and has_sem and not has_kw and ("semantic" in methods or "hybrid" in methods):
            continue

        kw_score = float(ks.get("keyword_score") or 0.0)
        sem_score = float(ss.get("semantic_score") or 0.0)

        if "hybrid" in methods:
            final = max(sem_score, kw_score, 0.7 * sem_score + 0.3 * kw_score)
        elif "semantic" in methods and "keyword" not in methods:
            final = sem_score
        else:
            final = kw_score

        if final < min_score:
            continue

        url = row.get("url") or ""
        if exclude_spam and _is_spam(spam_active, feed_id=fid, article_id=aid, url=url):
            continue

        snippet = row.get("excerpt") or ss.get("semantic_snippet") or ""
        title = row.get("title") or ""

        method_hit: List[str] = []
        if has_kw:
            method_hit.append("keyword")
        if has_sem:
            method_hit.append("semantic")

        published_ts = _parse_ts_any(row.get("published_at")) or float(row.get("_ts") or 0.0)

        merged.append(
            {
                "feed_id": fid,
                "article_id": aid,
                "url": url,
                "title": title,
                "published_at": row.get("published_at") or "",
                "score": float(final),
                "snippet": snippet,
                "method_hit": method_hit,
                "keyword_score": kw_score,
                "semantic_score": sem_score,
                "_published_ts": float(published_ts or 0.0),
            }
        )

    if sort_by == "published_at":
        merged.sort(
            key=lambda x: (float(x.get("_published_ts") or 0.0), float(x.get("score") or 0.0)),
            reverse=True,
        )
    else:
        merged.sort(
            key=lambda x: (float(x.get("score") or 0.0), float(x.get("_published_ts") or 0.0)),
            reverse=True,
        )

    page = merged[offset: offset + limit]
    next_cursor = str(offset + limit) if (offset + limit) < len(merged) else ""

    for it in page:
        if isinstance(it, dict) and "_published_ts" in it:
            del it["_published_ts"]

    warnings.append(f"rows_examined:{rows_examined}")
    warnings.append(f"local_rows:{len(local_rows)}")
    warnings.append(f"merged:{len(merged)}")

    took_ms = int((time.time() - started_at) * 1000)

    return _build_gate_success(
        page=page,
        total=len(merged),
        next_cursor=next_cursor,
        sort_by=sort_by,
        match_mode=match_mode,
        groups_count=len(groups),
        scan_mode=_scan_mode_name(use_reverse_scan, fast_mode),
        methods=methods,
        query=query,
        days=days,
        start_date=start_date,
        end_date=end_date,
        feed_ids=feed_ids,
        min_score=min_score,
        strict_lexical=strict_lexical,
        exclude_spam=exclude_spam,
        fast_mode=fast_mode,
        scan_cap=scan_cap,
        candidate_cap=candidate_cap,
        took_ms=took_ms,
        warnings=warnings,
    )

