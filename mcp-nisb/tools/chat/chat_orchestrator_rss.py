#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from core.openai_utils import call_llm
from core.storage import load_json
from tools.rss import nisb_rss_semantic_search
from .chat_orchestrator_mode import coerce_bool


_WORD_RE = re.compile(r"[A-Za-z0-9_]{3,}")
_ZH_RE = re.compile(r"[\u4e00-\u9fff]")


def is_non_english(query: str) -> bool:
    q = (query or "").strip()
    if not q:
        return False
    non_english_re = re.compile(r"[\u4e00-\u9fff\u3040-\u30ff\uac00-\ud7af\u0600-\u06ff\u0400-\u04ff]")
    return bool(non_english_re.search(q))


def translate_to_english_for_search(query: str) -> str:
    q = (query or "").strip()
    if not q:
        return ""
    try:
        en = call_llm(
            model="gpt-4o-mini",
            system_prompt=(
                "You are a search query translator for news/RSS retrieval.\n"
                "Translate the user's query into a concise English search query.\n"
                "Rules:\n"
                "- Keep named entities (people, places, organizations)\n"
                "- Use keywords, not full sentences\n"
                "- Do NOT add explanations or extra words\n"
                "- Output English only\n"
            ),
            user_prompt=q,
        )
        en = str(en or "").strip()
        if len(en) < 3 or is_non_english(en):
            return ""
        print(f"[RSS_TRANSLATE] '{q}' -> '{en}'", file=sys.stderr)
        return en
    except Exception as e:
        print(f"[RSS_TRANSLATE_ERR] {e}", file=sys.stderr)
        return ""


def rrf_fuse_by_url(list_a: List[Dict[str, Any]], list_b: List[Dict[str, Any]], k: int = 60) -> List[Dict[str, Any]]:
    scores: Dict[str, float] = {}
    items: Dict[str, Dict[str, Any]] = {}

    def add_list(lst: List[Dict[str, Any]]) -> None:
        for rank, it in enumerate(lst or [], start=1):
            if not isinstance(it, dict):
                continue
            url = str(it.get("url") or "").strip()
            if not url:
                continue
            scores[url] = scores.get(url, 0.0) + 1.0 / (k + rank)
            if url not in items:
                items[url] = it

    add_list(list_a)
    add_list(list_b)

    sorted_urls = sorted(scores.keys(), key=lambda u: scores[u], reverse=True)
    return [items[u] for u in sorted_urls]


def rss_feeds_json(user_base: str) -> Path:
    return Path(user_base) / "rss" / "feeds.json"


def rss_pick_default_feed_ids(user_base: str, max_n: int = 1) -> List[str]:
    try:
        doc = load_json(str(rss_feeds_json(user_base)))
        feeds = (doc or {}).get("feeds") or []
        if not isinstance(feeds, list):
            return []

        enabled = [f for f in feeds if isinstance(f, dict) and bool(f.get("enabled", True)) is True]
        enabled.sort(key=lambda x: str(x.get("added_at") or ""), reverse=True)

        out: List[str] = []
        for f in enabled[: max(0, int(max_n))]:
            fid = str(f.get("feed_id") or "").strip()
            if fid:
                out.append(fid)
        return out
    except Exception:
        return []


def uid_from_user_base(user_base: str) -> str:
    ub = str(user_base or "").rstrip("/")
    return ub.split("/")[-1] if ub else ""


def query_terms(q: str) -> List[str]:
    s = (q or "").strip().lower()
    if not s:
        return []

    out: List[str] = []
    out.extend(_WORD_RE.findall(s))
    out.extend(_ZH_RE.findall(s))

    seen = set()
    result: List[str] = []
    for t in out:
        if t in seen:
            continue
        seen.add(t)
        result.append(t)
    return result[:24]

def _merge_terms(*groups: List[str]) -> List[str]:
    out: List[str] = []
    seen = set()
    for group in groups:
        for t in (group or []):
            s = str(t or "").strip().lower()
            if not s or s in seen:
                continue
            seen.add(s)
            out.append(s)
    return out

def passes_lexical_gate(title: str, snippet: str, terms: List[str]) -> bool:
    if not terms:
        return True
    hay = f"{title}\n{snippet}".lower()
    return any(t.lower() in hay for t in terms if t)


def parse_iso_dt_rss(s: str) -> Optional[datetime]:
    try:
        x = str(s or "").strip()
        if not x:
            return None
        x = x.replace("Z", "+00:00")
        dt = datetime.fromisoformat(x)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


def _parse_date_floor_utc(s: str) -> Optional[datetime]:
    x = str(s or "").strip()
    if not x:
        return None
    try:
        dt = datetime.strptime(x[:10], "%Y-%m-%d")
        return dt.replace(tzinfo=timezone.utc)
    except Exception:
        pass
    try:
        dt = datetime.fromisoformat(x.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        dt = dt.astimezone(timezone.utc)
        return dt.replace(hour=0, minute=0, second=0, microsecond=0)
    except Exception:
        return None


def _parse_date_ceil_utc(s: str) -> Optional[datetime]:
    lo = _parse_date_floor_utc(s)
    if lo is None:
        return None
    return lo + timedelta(days=1) - timedelta(microseconds=1)


def _parse_item_published_dt(it: Dict[str, Any]) -> Optional[datetime]:
    if not isinstance(it, dict):
        return None
    return parse_iso_dt_rss(str(it.get("published_at") or it.get("published") or it.get("pubDate") or ""))


def _normalize_time_window(
    *,
    days: int,
    start_date: str,
    end_date: str,
) -> Tuple[int, str, str, Optional[datetime], Optional[datetime]]:
    start_dt = _parse_date_floor_utc(start_date) if start_date else None
    end_dt = _parse_date_ceil_utc(end_date) if end_date else None

    if start_dt and end_dt and start_dt > end_dt:
        start_dt, end_dt = end_dt, start_dt
        start_date, end_date = end_date, start_date

    explicit = start_dt is not None or end_dt is not None
    normalized_days = 0 if explicit else max(0, int(days or 0))
    return normalized_days, str(start_date or ""), str(end_date or ""), start_dt, end_dt


def rss_within_days(published_at: Optional[datetime], days: int) -> bool:
    if days <= 0:
        return True
    if published_at is None:
        return False
    now = datetime.now(timezone.utc)
    start = now - timedelta(days=int(days))
    return start <= published_at <= now


def rss_filter_items_by_days(items: List[Dict[str, Any]], days: int) -> List[Dict[str, Any]]:
    d = int(days or 0)
    if d <= 0:
        return items or []

    out: List[Dict[str, Any]] = []
    for it in (items or []):
        if not isinstance(it, dict):
            continue
        dt = _parse_item_published_dt(it)
        if rss_within_days(dt, d):
            out.append(it)
    return out


def rss_filter_items_by_time(
    items: List[Dict[str, Any]],
    *,
    days: int = 0,
    start_date: str = "",
    end_date: str = "",
) -> List[Dict[str, Any]]:
    normalized_days, _, _, start_dt, end_dt = _normalize_time_window(
        days=int(days or 0),
        start_date=start_date,
        end_date=end_date,
    )

    out: List[Dict[str, Any]] = []
    for it in (items or []):
        if not isinstance(it, dict):
            continue
        dt = _parse_item_published_dt(it)
        if start_dt is not None:
            if dt is None or dt < start_dt:
                continue
        if end_dt is not None:
            if dt is None or dt > end_dt:
                continue
        if normalized_days > 0 and not rss_within_days(dt, normalized_days):
            continue
        out.append(it)
    return out


def _read_rss_dict(payload: Dict[str, Any]) -> Dict[str, Any]:
    rss = payload.get("rss") if isinstance(payload, dict) else None
    return dict(rss) if isinstance(rss, dict) else {}


def pick_rss_opts(payload: Dict[str, Any]) -> Dict[str, Any]:
    rss = _read_rss_dict(payload)
    if not rss:
        return {
            "enabled": True,
            "days": 7,
            "limit": 8,
            "minscore": 0.08,
            "strict_lexical": True,
            "start_date": "",
            "end_date": "",
        }

    try:
        days = int(rss.get("days", 7) or 0)
    except Exception:
        days = 0
    try:
        limit = int(rss.get("limit", 8) or 8)
    except Exception:
        limit = 8
    try:
        minscore = float(rss.get("minscore", 0.08) or 0.0)
    except Exception:
        minscore = 0.08

    start_date = str(
        rss.get("start_date")
        or rss.get("date_from")
        or ""
    ).strip()
    end_date = str(
        rss.get("end_date")
        or rss.get("date_to")
        or ""
    ).strip()

    return {
        "enabled": bool(rss.get("enabled", True)),
        "days": days,
        "limit": limit,
        "minscore": minscore,
        "strict_lexical": bool(rss.get("strict_lexical", True)),
        "start_date": start_date,
        "end_date": end_date,
    }


def rss_semantic_search_once(
    *,
    user_base: str,
    uid: str,
    query: str,
    limit: int,
    days: int,
    feed_ids: Optional[List[str]] = None,
    start_date: str = "",
    end_date: str = "",
) -> List[Dict[str, Any]]:
    q = str(query or "").strip()
    if not q:
        return []

    try:
        k = int(limit or 8)
    except Exception:
        k = 8
    k = max(1, min(200, k))

    normalized_days, start_date, end_date, start_dt, end_dt = _normalize_time_window(
        days=int(days or 0),
        start_date=start_date,
        end_date=end_date,
    )

    try:
        res = nisb_rss_semantic_search(
            {
                "basepath": user_base,
                "uid": uid,
                "query": q,
                "limit": k,
                "days": normalized_days,
                "feed_ids": [str(x).strip() for x in (feed_ids or []) if str(x).strip()],
                "start_ts": float(start_dt.timestamp()) if start_dt is not None else None,
                "end_ts": float(end_dt.timestamp()) if end_dt is not None else None,
            }
        )
    except Exception as e:
        print(f"[RSS_ERR] semantic_search failed: {e}", file=sys.stderr)
        return []

    if not isinstance(res, dict):
        return []
    items = res.get("items")
    if not isinstance(items, list):
        return []

    items2 = rss_filter_items_by_time(
        items,
        days=normalized_days,
        start_date=start_date,
        end_date=end_date,
    )
    return items2[:k]


def _dedupe_hits_by_url(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    seen = set()
    for it in (items or []):
        if not isinstance(it, dict):
            continue
        url = str(it.get("url") or "").strip()
        if not url or url in seen:
            continue
        seen.add(url)
        out.append(it)
    return out


def _effective_output_limit(raw_limit: int, opts_limit: int, max_cap: int) -> int:
    try:
        requested = int(raw_limit or 0)
    except Exception:
        requested = 0
    requested = max(1, requested)
    try:
        rss_limit = int(opts_limit or 0)
    except Exception:
        rss_limit = 0
    if rss_limit > 0:
        requested = min(requested, rss_limit)
    return max(1, min(max_cap, requested))


def _rss_candidate_fetch_limit(limit_total: int, opts: Dict[str, Any]) -> int:
    final_limit = _effective_output_limit(limit_total, int(opts.get("limit") or 0), 20)

    start_date = str(opts.get("start_date") or "").strip()
    end_date = str(opts.get("end_date") or "").strip()
    has_explicit_window = bool(start_date or end_date)

    try:
        days = int(opts.get("days") or 0)
    except Exception:
        days = 0

    if has_explicit_window or days == 0:
        return max(240, final_limit * 30)
    if days <= 1:
        return max(36, final_limit * 6)
    if days <= 3:
        return max(60, final_limit * 10)
    if days <= 7:
        return max(96, final_limit * 14)
    if days <= 30:
        return max(180, final_limit * 24)
    return max(240, final_limit * 30)


def collect_rss_search_hits(
    *,
    user_base: str,
    feed_ids: List[str],
    query_text: str,
    limit_total: int,
    payload: Dict[str, Any],
) -> List[Dict[str, Any]]:
    query = str(query_text or "").strip()
    if not query:
        return []

    uid = uid_from_user_base(user_base)
    if not uid:
        return []

    opts = pick_rss_opts(payload)
    if not opts["enabled"]:
        return []

    shared_limit = _effective_output_limit(limit_total, int(opts.get("limit") or 0), 20)
    candidate_limit = _rss_candidate_fetch_limit(limit_total, opts)

    query_en = ""
    terms_native = query_terms(query)
    terms_en: List[str] = []

    items_a = rss_semantic_search_once(
        user_base=user_base,
        uid=uid,
        query=query,
        limit=candidate_limit,
        days=int(opts["days"] or 0),
        feed_ids=feed_ids,
        start_date=str(opts.get("start_date") or ""),
        end_date=str(opts.get("end_date") or ""),
    )

    items_b: List[Dict[str, Any]] = []
    if is_non_english(query):
        query_en = translate_to_english_for_search(query)
        if query_en:
            terms_en = query_terms(query_en)
            items_b = rss_semantic_search_once(
                user_base=user_base,
                uid=uid,
                query=query_en,
                limit=candidate_limit,
                days=int(opts["days"] or 0),
                feed_ids=feed_ids,
                start_date=str(opts.get("start_date") or ""),
                end_date=str(opts.get("end_date") or ""),
            )

    if items_b:
        fused = rrf_fuse_by_url(items_b, items_a, k=60)
    else:
        fused = list(items_a)

    fused = _dedupe_hits_by_url(fused)

    lexical_terms = _merge_terms(terms_native, terms_en)

    score_filtered = 0
    lexical_filtered = 0
    kept = 0

    out: List[Dict[str, Any]] = []
    score_fallback_pool: List[Dict[str, Any]] = []

    score_filtered = 0
    lexical_filtered = 0
    kept = 0

    minscore = float(opts.get("minscore", 0.0) or 0.0)
    strict_lexical = bool(opts.get("strict_lexical", True))

    for it in fused:
        if not isinstance(it, dict):
            continue

        url = str(it.get("url") or "").strip()
        if not url:
            continue

        title = str(it.get("title") or "").strip()
        quote = str(it.get("snippet") or "").strip()
        feed_id = str(it.get("feed_id") or "").strip()
        article_id = str(it.get("id") or it.get("article_id") or "").strip()
        try:
            score = float(it.get("score") or it.get("relevance") or 0.0)
        except Exception:
            score = 0.0

        obj_ref = f"rss:{feed_id}/{article_id}" if (feed_id and article_id) else ""

        candidate = {
            "id": article_id,
            "article_id": article_id,
            "url": url,
            "title": title,
            "snippet": quote,
            "quote": quote,
            "source": "rss",
            "feed_id": feed_id,
            "object_ref": obj_ref,
            "published_at": it.get("published_at") or "",
            "score": score,
            "relevance": score,
        }

        lexical_ok = True
        if strict_lexical and lexical_terms:
            lexical_ok = passes_lexical_gate(title, quote, lexical_terms)

        if not lexical_ok:
            lexical_filtered += 1
            continue

        if score < minscore:
            score_filtered += 1
            score_fallback_pool.append(candidate)
            continue

        if len(out) < shared_limit:
            out.append(candidate)
            kept += 1

    if not out and score_fallback_pool:
        score_fallback_pool.sort(
            key=lambda x: (
                float(x.get("relevance") or 0.0),
                str(x.get("published_at") or ""),
            ),
            reverse=True,
        )
        out = score_fallback_pool[:shared_limit]
        kept = len(out)

    print(
        f"[RSS_HITS_DEBUG] query='{query}' query_en='{query_en}' "
        f"items_a={len(items_a)} items_b={len(items_b)} fused={len(fused)} "
        f"score_filtered={score_filtered} lexical_filtered={lexical_filtered} kept={kept} "
        f"strict_lexical={strict_lexical} minscore={minscore}",
        file=sys.stderr,
    )

    return out


def build_rss_web_citations(
    *,
    user_base: str,
    feed_ids: List[str],
    query_text: str,
    limit_total: int,
    payload: Dict[str, Any],
    items: Optional[List[Dict[str, Any]]] = None,
) -> List[Dict[str, Any]]:
    opts = pick_rss_opts(payload)
    limit_final = _effective_output_limit(limit_total, int(opts.get("limit") or 0), 12)

    if items is None:
        items = collect_rss_search_hits(
            user_base=user_base,
            feed_ids=feed_ids,
            query_text=query_text,
            limit_total=limit_final,
            payload=payload,
        )

    out: List[Dict[str, Any]] = []
    for it in (items or []):
        if len(out) >= limit_final:
            break
        if not isinstance(it, dict):
            continue

        url = str(it.get("url") or "").strip()
        if not url:
            continue

        title = str(it.get("title") or "").strip()
        quote = str(it.get("quote") or it.get("snippet") or "").strip()
        feed_id = str(it.get("feed_id") or "").strip()
        article_id = str(it.get("article_id") or it.get("id") or "").strip()
        obj_ref = str(it.get("object_ref") or "").strip()
        try:
            score = float(it.get("score") or it.get("relevance") or 0.0)
        except Exception:
            score = 0.0

        if not obj_ref and feed_id and article_id:
            obj_ref = f"rss:{feed_id}/{article_id}"

        out.append(
            {
                "url": url,
                "title": title,
                "quote": quote,
                "source": "rss",
                "feed_id": feed_id,
                "article_id": article_id,
                "object_ref": obj_ref,
                "published_at": it.get("published_at") or "",
                "relevance": score,
            }
        )

    return out


def build_rss_evidence_items(
    *,
    user_base: str,
    feed_ids: List[str],
    query_text: str,
    limit_total: int,
    payload: Dict[str, Any],
    items: Optional[List[Dict[str, Any]]] = None,
) -> List[Dict[str, Any]]:
    opts = pick_rss_opts(payload)
    limit_final = _effective_output_limit(limit_total, int(opts.get("limit") or 0), 20)
    terms = query_terms(query_text)

    if items is None:
        items = collect_rss_search_hits(
            user_base=user_base,
            feed_ids=feed_ids,
            query_text=query_text,
            limit_total=limit_final,
            payload=payload,
        )

    out: List[Dict[str, Any]] = []
    for it in (items or []):
        if len(out) >= limit_final:
            break
        if not isinstance(it, dict):
            continue

        url = str(it.get("url") or "").strip()
        if not url:
            continue

        feed_id = str(it.get("feed_id") or "").strip()
        article_id = str(it.get("article_id") or it.get("id") or "").strip()
        title = str(it.get("title") or "").strip()
        excerpt = str(it.get("snippet") or it.get("quote") or "").strip()
        try:
            score = float(it.get("score") or it.get("relevance") or 0.0)
        except Exception:
            score = 0.0

        obj_ref = str(it.get("object_ref") or "").strip()
        if not obj_ref and feed_id and article_id:
            obj_ref = f"rss:{feed_id}/{article_id}"

        out.append(
            {
                "source": "rss",
                "relevance": score,
                "excerpt": excerpt,
                "quote": excerpt,
                "charstart": 0,
                "charend": len(excerpt),
                "spanid": obj_ref,
                "spanchars": len(excerpt),
                "object_ref": obj_ref,
                "title": title,
                "url": url,
                "matched": True,
                "matched_terms": terms,
                "published_at": it.get("published_at") or "",
                "feed_id": feed_id,
                "article_id": article_id,
            }
        )

    return out


def build_rss_outputs(
    *,
    user_base: str,
    feed_ids: List[str],
    query_text: str,
    citations_limit_total: int,
    evidence_limit_total: int,
    payload: Dict[str, Any],
) -> Dict[str, List[Dict[str, Any]]]:
    shared_limit = max(1, int(max(citations_limit_total or 0, evidence_limit_total or 0)))
    items = collect_rss_search_hits(
        user_base=user_base,
        feed_ids=feed_ids,
        query_text=query_text,
        limit_total=shared_limit,
        payload=payload,
    )
    return {
        "citations": build_rss_web_citations(
            user_base=user_base,
            feed_ids=feed_ids,
            query_text=query_text,
            limit_total=citations_limit_total,
            payload=payload,
            items=items,
        ),
        "rss_evidence": build_rss_evidence_items(
            user_base=user_base,
            feed_ids=feed_ids,
            query_text=query_text,
            limit_total=evidence_limit_total,
            payload=payload,
            items=items,
        ),
    }


def resolve_rss_settings(*, args: Dict[str, Any], effective_mode: str, user_base: str) -> Tuple[bool, List[str], int]:
    rss_dict = _read_rss_dict(args)

    if "rss_enabled" in args:
        enabled = coerce_bool(args.get("rss_enabled"), default=False)
    elif "enabled" in rss_dict:
        enabled = coerce_bool(rss_dict.get("enabled"), default=True)
    else:
        enabled = effective_mode in ("cite", "ground") and bool(rss_pick_default_feed_ids(user_base, max_n=8))

    max_citations = args.get("rss_max_citations", 6)
    try:
        max_citations = int(max_citations)
    except Exception:
        max_citations = 6
    max_citations = max(1, min(12, max_citations))

    feed_ids_raw = args.get("rss_feed_ids")
    if not isinstance(feed_ids_raw, list):
        feed_ids_raw = rss_dict.get("feed_ids") if isinstance(rss_dict.get("feed_ids"), list) else []

    feed_ids: List[str] = []
    if isinstance(feed_ids_raw, list):
        feed_ids = [str(x).strip() for x in feed_ids_raw if str(x).strip()]
    if not feed_ids:
        feed_ids = rss_pick_default_feed_ids(user_base, max_n=8)

    print(f"[RSS_DEBUG] enabled={enabled} feed_ids={feed_ids} max={max_citations}", file=sys.stderr)
    return enabled, feed_ids, max_citations

