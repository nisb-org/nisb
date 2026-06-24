#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import inspect
import json
import os
import sys
import uuid
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Set, Tuple

from core.user_context import auto_user_context, get_user_ctx
from tools.doc.core.dod_guard import require_safe_id
from tools.doc.core.search_sqlite import _hybrid_search_internal
from tools.doc.core.span_constants import SPAN_CHARS
from tools.doc.doc_db_sqlite import connect_doc_db, get_doc_db_sqlite
from tools.library_groups.group_store import resolve_group_filter

try:
    from tools.timeline import _append_timeline_activity  # type: ignore
except Exception:
    _append_timeline_activity = None


def _append_timeline_safe(base_path: str, event: Dict[str, Any]) -> None:
    if _append_timeline_activity:
        try:
            _append_timeline_activity(base_path, event)
            return
        except Exception:
            pass
    try:
        timeline_dir = os.path.join(base_path, "timeline")
        os.makedirs(timeline_dir, exist_ok=True)
        fp = os.path.join(timeline_dir, "activities.jsonl")
        with open(fp, "a", encoding="utf-8") as f:
            f.write(json.dumps(event, ensure_ascii=False) + "\n")
    except Exception:
        pass


def _parse_iso_dt(s: str) -> Optional[datetime]:
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


def _iso_or_none(dt: Optional[datetime]) -> Optional[str]:
    if dt is None:
        return None
    x = dt.astimezone(timezone.utc).isoformat()
    if x.endswith("+00:00"):
        x = x[:-6] + "Z"
    return x


def _time_window_from_args(args: Dict[str, Any]) -> Tuple[Optional[datetime], Optional[datetime], Optional[int]]:
    time_start = _parse_iso_dt(str(args.get("time_start") or "").strip())
    time_end = _parse_iso_dt(str(args.get("time_end") or "").strip())
    if time_start or time_end:
        return time_start, time_end, None

    tfd = args.get("time_filter_days", None)
    if tfd is None:
        return None, None, None
    try:
        days = int(tfd)
    except Exception:
        days = None
    if days is None or days <= 0:
        return None, None, 0

    now = datetime.now(timezone.utc)
    return now - timedelta(days=days), now, days


def _doc_dir(base_path: str, library_id: str, doc_id: str) -> str:
    return os.path.join(base_path, "libraries", library_id, "docs", doc_id)


def _doc_exists(base_path: str, library_id: str, doc_id: str) -> bool:
    return os.path.isdir(_doc_dir(base_path, library_id, doc_id))


def _read_doc_metadata(base_path: str, library_id: str, doc_id: str) -> Dict[str, Any]:
    meta_fp = os.path.join(_doc_dir(base_path, library_id, doc_id), "metadata.json")
    try:
        if os.path.exists(meta_fp):
            with open(meta_fp, "r", encoding="utf-8") as f:
                meta = json.load(f)
            if isinstance(meta, dict):
                return meta
    except Exception:
        return {}
    return {}


def _read_doc_title(base_path: str, library_id: str, doc_id: str) -> Optional[str]:
    meta = _read_doc_metadata(base_path, library_id, doc_id)
    title = str(meta.get("filename") or meta.get("title") or "").strip()
    return title or None


def _read_full_text(base_path: str, library_id: str, doc_id: str) -> str:
    d = _doc_dir(base_path, library_id, doc_id)
    for name in ("content.txt", "full_text.txt"):
        fp = os.path.join(d, name)
        try:
            if os.path.exists(fp):
                with open(fp, "r", encoding="utf-8", errors="ignore") as f:
                    t = f.read()
                if isinstance(t, str) and t.strip():
                    return t
        except Exception:
            pass
    return ""


def _read_published_at_from_metadata(base_path: str, library_id: str, doc_id: str) -> Optional[datetime]:
    meta = _read_doc_metadata(base_path, library_id, doc_id)
    return _parse_iso_dt(str(meta.get("published_at") or "").strip())


def _read_published_at_consistent(base_path: str, library_id: str, doc_id: str) -> Optional[datetime]:
    published_at, _ = _read_published_at_consistent_with_source(base_path, library_id, doc_id)
    return published_at


def _read_published_at_consistent_with_source(
    base_path: str,
    library_id: str,
    doc_id: str,
) -> Tuple[Optional[datetime], str]:
    try:
        db = get_doc_db_sqlite(base_path, library_id)
        conn = connect_doc_db(str(db.db_path), readonly=True)
        try:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT published_at
                FROM documents
                WHERE library_id = ? AND doc_id = ?
                LIMIT 1
                """,
                (library_id, doc_id),
            )
            row = cur.fetchone()
            if row is not None:
                published_at = _parse_iso_dt(str(row["published_at"] or "").strip())
                if published_at is not None:
                    return published_at, "sqlite.documents.published_at"
        finally:
            conn.close()
    except Exception:
        pass

    meta_dt = _read_published_at_from_metadata(base_path, library_id, doc_id)
    if meta_dt is not None:
        return meta_dt, "metadata.json.published_at"

    return None, ""


def _doc_in_window_by_published_at(
    published_at: Optional[datetime],
    start_dt: Optional[datetime],
    end_dt: Optional[datetime],
) -> bool:
    if start_dt is None and end_dt is None:
        return True
    if published_at is None:
        return False
    if start_dt is not None and published_at < start_dt:
        return False
    if end_dt is not None and published_at > end_dt:
        return False
    return True


def _build_chunk_map(base_path: str, library_id: str, doc_id: str) -> Dict[int, Dict[str, Any]]:
    db = get_doc_db_sqlite(base_path, library_id)
    chunks = db.get_chunks(doc_id) or []
    mp: Dict[int, Dict[str, Any]] = {}
    for c in chunks:
        try:
            cid = int(c.get("chunk_id"))
        except Exception:
            continue
        mp[cid] = c
    return mp


def _find_offset_in_fulltext(full_text: str, chunk_text: str) -> Optional[int]:
    if not full_text or not chunk_text:
        return None
    t = " ".join(chunk_text.strip().split())
    if not t:
        return None

    needle = t[:160]
    if len(needle) < 30:
        needle = t[:80]
    if len(needle) < 20:
        return None

    pos = full_text.find(needle)
    if pos >= 0:
        return pos

    ft2 = " ".join(full_text.split())
    pos2 = ft2.find(needle)
    if pos2 >= 0:
        return pos2
    return None


def _int_or_none(v: Any) -> Optional[int]:
    if v is None:
        return None
    if isinstance(v, bool):
        return int(v)
    s = str(v).strip()
    if not s:
        return None
    try:
        return int(s)
    except Exception:
        return None


def _float_or_none(v: Any) -> Optional[float]:
    if v is None:
        return None
    s = str(v).strip()
    if not s:
        return None
    try:
        return float(s)
    except Exception:
        return None


def _bool_or_none(v: Any) -> Optional[bool]:
    if isinstance(v, bool):
        return v
    if v is None:
        return None
    s = str(v).strip().lower()
    if not s:
        return None
    if s in ("1", "true", "yes", "on"):
        return True
    if s in ("0", "false", "no", "off"):
        return False
    return None


def _extract_hits_and_search_debug(search_res: Any) -> Tuple[List[Dict[str, Any]], Dict[str, Any], str]:
    if isinstance(search_res, list):
        return [x for x in search_res if isinstance(x, dict)], {}, "list"

    if isinstance(search_res, tuple) and len(search_res) == 2:
        a, b = search_res
        if isinstance(a, list) and isinstance(b, dict):
            return [x for x in a if isinstance(x, dict)], b, "tuple(list,dict)"
        if isinstance(a, dict) and isinstance(b, list):
            return [x for x in b if isinstance(x, dict)], a, "tuple(dict,list)"

    if isinstance(search_res, dict):
        hits: List[Dict[str, Any]] = []
        for key in ("hits", "items", "results", "rows"):
            val = search_res.get(key)
            if isinstance(val, list):
                hits = [x for x in val if isinstance(x, dict)]
                break

        search_debug: Dict[str, Any] = {}
        for key in (
            "debug",
            "search_debug",
            "hybrid_search_debug",
            "hybrid_debug",
            "time_scope",
            "time_scope_debug",
        ):
            val = search_res.get(key)
            if isinstance(val, dict):
                search_debug = val
                break

        return hits, search_debug, "dict"

    return [], {}, type(search_res).__name__


def _summarize_search_time_debug(search_debug: Dict[str, Any]) -> Dict[str, Any]:
    out: Dict[str, Any] = {
        "time_filter_applied": False,
        "time_window_on": False,
        "candidate_docs_before_time": None,
        "candidate_docs_after_time": None,
        "published_at_coverage": None,
        "profile_name": "",
    }
    if not isinstance(search_debug, dict):
        return out

    candidates: List[Dict[str, Any]] = [search_debug]
    for key in (
        "time_scope",
        "time_scope_debug",
        "search_debug",
        "hybrid_search_debug",
        "hybrid_debug",
        "debug",
    ):
        val = search_debug.get(key)
        if isinstance(val, dict):
            candidates.append(val)

    def pick_bool(*keys: str) -> Optional[bool]:
        for obj in candidates:
            for k in keys:
                val = _bool_or_none(obj.get(k))
                if val is not None:
                    return val
        return None

    def pick_int(*keys: str) -> Optional[int]:
        for obj in candidates:
            for k in keys:
                val = _int_or_none(obj.get(k))
                if val is not None:
                    return val
        return None

    def pick_float(*keys: str) -> Optional[float]:
        for obj in candidates:
            for k in keys:
                val = _float_or_none(obj.get(k))
                if val is not None:
                    return val
        return None

    def pick_str(*keys: str) -> str:
        for obj in candidates:
            for k in keys:
                val = str(obj.get(k) or "").strip()
                if val:
                    return val
        return ""

    time_filter_applied = pick_bool(
        "time_filter_applied",
        "time_filter_effective",
        "time_window_applied",
        "time_window_on",
    )
    time_window_on = pick_bool(
        "time_window_on",
        "time_filter_effective",
        "time_window_applied",
    )
    before_count = pick_int(
        "candidate_docs_before_time",
        "time_candidates_before",
        "before_time_count",
    )
    after_count = pick_int(
        "candidate_docs_after_time",
        "candidate_docs_count",
        "time_candidates_after",
        "after_time_count",
    )
    coverage = pick_float("published_at_coverage")
    profile_name = pick_str("profile_name", "profile", "name")

    if time_filter_applied is None:
        time_filter_applied = False
    if time_window_on is None:
        time_window_on = bool(time_filter_applied)

    out["time_filter_applied"] = bool(time_filter_applied)
    out["time_window_on"] = bool(time_window_on)
    out["candidate_docs_before_time"] = before_count
    out["candidate_docs_after_time"] = after_count
    out["published_at_coverage"] = coverage
    out["profile_name"] = profile_name
    return out


def _call_hybrid_search_with_optional_debug(
    *,
    base_path: str,
    user_ctx: Any,
    query: str,
    doc_id: Optional[str],
    library_id: Optional[str],
    top_k: int,
    weights: Any,
    time_filter_days: Optional[int],
    time_start: Optional[str],
    time_end: Optional[str],
    allowed_libraries: Optional[Set[str]],
    allowed_pairs: Optional[Set[Tuple[str, str]]],
) -> Tuple[List[Dict[str, Any]], Dict[str, Any], Dict[str, Any]]:
    kwargs: Dict[str, Any] = {
        "base_path": base_path,
        "user_ctx": user_ctx,
        "query": query,
        "doc_id": doc_id,
        "library_id": library_id,
        "top_k": top_k,
        "weights": weights,
        "time_filter_days": time_filter_days,
        "time_start": time_start,
        "time_end": time_end,
        "allowed_libraries": allowed_libraries,
        "allowed_pairs": allowed_pairs,
    }

    debug_flag = ""
    signature_error = ""

    try:
        sig = inspect.signature(_hybrid_search_internal)
        for name in ("return_debug", "with_debug", "include_debug", "debug"):
            if name in sig.parameters:
                kwargs[name] = True
                debug_flag = name
                break
    except Exception as e:
        signature_error = str(e)

    try:
        search_res = _hybrid_search_internal(**kwargs)
    except TypeError:
        if debug_flag:
            kwargs.pop(debug_flag, None)
            search_res = _hybrid_search_internal(**kwargs)
            debug_flag = ""
        else:
            raise

    hits, search_debug, result_shape = _extract_hits_and_search_debug(search_res)

    call_dbg = {
        "search_result_shape": result_shape,
        "search_debug_requested": bool(debug_flag),
        "search_debug_flag": debug_flag,
        "search_debug_available": bool(search_debug),
    }
    if signature_error:
        call_dbg["search_signature_error"] = signature_error

    return hits, search_debug, call_dbg


def _span_bounds_from_hit(
    *,
    span_index: Optional[int],
    span_start: Optional[int],
    span_end: Optional[int],
    char_start: Optional[int],
    char_end: Optional[int],
) -> Tuple[Optional[int], Optional[int], Optional[int]]:
    resolved_span_index = span_index
    resolved_span_start = span_start
    resolved_span_end = span_end

    if resolved_span_index is None and char_start is not None:
        resolved_span_index = int(char_start) // int(SPAN_CHARS)

    if resolved_span_start is None and resolved_span_index is not None:
        resolved_span_start = int(resolved_span_index) * int(SPAN_CHARS)

    if resolved_span_end is None and resolved_span_start is not None:
        resolved_span_end = int(resolved_span_start) + int(SPAN_CHARS)

    if resolved_span_start is None and char_start is not None:
        resolved_span_start = int(char_start) - (int(char_start) % int(SPAN_CHARS))

    if resolved_span_end is None and resolved_span_start is not None:
        resolved_span_end = int(resolved_span_start) + int(SPAN_CHARS)

    if resolved_span_index is None and resolved_span_start is not None:
        resolved_span_index = int(resolved_span_start) // int(SPAN_CHARS)

    if resolved_span_end is not None and char_end is not None:
        resolved_span_end = max(int(resolved_span_end), int(char_end))

    return resolved_span_index, resolved_span_start, resolved_span_end


def _build_item_fast(
    *,
    base_path: str,
    scope: str,
    library_id: str,
    doc_id: str,
    hit: Dict[str, Any],
    max_chars: int,
    include_text: bool,
) -> Optional[Dict[str, Any]]:
    chunk_text = str(hit.get("text") or "").strip()
    if not chunk_text:
        return None

    cid = _int_or_none(hit.get("chunk_id"))
    char_start = _int_or_none(hit.get("char_start"))
    char_end = _int_or_none(hit.get("char_end"))
    span_index = _int_or_none(hit.get("span_index"))
    span_start = _int_or_none(hit.get("span_start"))
    span_end = _int_or_none(hit.get("span_end"))

    span_index, span_start, span_end = _span_bounds_from_hit(
        span_index=span_index,
        span_start=span_start,
        span_end=span_end,
        char_start=char_start,
        char_end=char_end,
    )

    if span_index is None and char_start is None:
        return None

    excerpt = chunk_text[: min(900, max_chars)]

    evidence_id = (
        f"library_doc:{library_id}/{doc_id}#span:{int(span_index) if span_index is not None else -1}"
        f"#chunk:{int(cid) if cid is not None else -1}"
    )

    item: Dict[str, Any] = {
        "source_type": "library_doc",
        "evidence_id": evidence_id,
        "id": uuid.uuid4().hex[:12],
        "scope": scope,
        "library_id": library_id,
        "doc_id": doc_id,
        "doc_title": _read_doc_title(base_path, library_id, doc_id),
        "chunk_id": cid,
        "relevance": float(hit.get("relevance", 0.0) or 0.0),
        "char_start": char_start,
        "char_end": char_end,
        "span_index": span_index,
        "span_start": span_start,
        "span_end": span_end,
        "span_chars": int(SPAN_CHARS),
        "max_chars": int(max_chars),
        "excerpt": excerpt,
        "quote": excerpt,
        "text": excerpt,
    }
    if include_text:
        item["chunk_text"] = chunk_text
    return item


def _item_from_hit_fallback(
    base_path: str,
    scope: str,
    library_id: str,
    doc_id: str,
    hit: Dict[str, Any],
    chunk_map: Dict[int, Dict[str, Any]],
    full_text: str,
    *,
    max_chars: int,
    include_text: bool,
    dbg: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    try:
        cid = int(hit.get("chunk_id"))
    except Exception:
        cid = None

    meta = chunk_map.get(cid) if cid is not None else None
    chunk_text = str((meta or {}).get("text") or hit.get("text") or "").strip()
    if not chunk_text:
        return None

    char_start = None
    if meta and meta.get("char_start") is not None:
        try:
            char_start = int(meta.get("char_start"))
        except Exception:
            char_start = None

    if char_start is None and hit.get("char_start") is not None:
        try:
            char_start = int(hit.get("char_start"))
        except Exception:
            char_start = None

    if char_start is None:
        pos = _find_offset_in_fulltext(full_text, chunk_text)
        if pos is not None:
            char_start = int(pos)
            dbg["offset_found_by_fulltext"] += 1
        else:
            dbg["dropped_no_offset"] += 1
            return None

    char_end = None
    if meta and meta.get("char_end") is not None:
        try:
            char_end = int(meta.get("char_end"))
        except Exception:
            char_end = None

    if char_end is None and hit.get("char_end") is not None:
        try:
            char_end = int(hit.get("char_end"))
        except Exception:
            char_end = None

    if char_end is None and char_start is not None:
        char_end = int(char_start) + len(chunk_text)

    span_index = _int_or_none(hit.get("span_index"))
    span_start = _int_or_none(hit.get("span_start"))
    span_end = _int_or_none(hit.get("span_end"))

    span_index, span_start, span_end = _span_bounds_from_hit(
        span_index=span_index,
        span_start=span_start,
        span_end=span_end,
        char_start=char_start,
        char_end=char_end,
    )

    excerpt = chunk_text[: min(900, max_chars)]

    evidence_id = (
        f"library_doc:{library_id}/{doc_id}#span:{int(span_index) if span_index is not None else -1}"
        f"#chunk:{int(cid) if cid is not None else -1}"
    )

    item: Dict[str, Any] = {
        "source_type": "library_doc",
        "evidence_id": evidence_id,
        "id": uuid.uuid4().hex[:12],
        "scope": scope,
        "library_id": library_id,
        "doc_id": doc_id,
        "doc_title": _read_doc_title(base_path, library_id, doc_id),
        "chunk_id": cid,
        "relevance": float(hit.get("relevance", 0.0) or 0.0),
        "char_start": char_start,
        "char_end": char_end,
        "span_index": span_index,
        "span_start": span_start,
        "span_end": span_end,
        "span_chars": int(SPAN_CHARS),
        "max_chars": int(max_chars),
        "excerpt": excerpt,
        "quote": excerpt,
        "text": excerpt,
    }
    if include_text:
        item["chunk_text"] = chunk_text
    return item


def _doc_key_from_item(item: Dict[str, Any]) -> str:
    return f"{str(item.get('library_id') or '').strip()}::{str(item.get('doc_id') or '').strip()}"


def _select_items_for_citation_semantics(
    filtered: List[Dict[str, Any]],
    *,
    top_k: int,
    doc_diversity_min: int,
    per_doc_soft_cap: int,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    if top_k <= 0 or not filtered:
        return [], {
            "selection_mode": "doc_diversity_two_phase",
            "doc_diversity_min": doc_diversity_min,
            "per_doc_soft_cap": per_doc_soft_cap,
            "unique_docs_before_select": 0,
            "unique_docs_after_select": 0,
            "phase1_selected": 0,
            "phase2_selected": 0,
            "phase3_selected": 0,
            "selection_backfill_used": False,
        }

    selected: List[Dict[str, Any]] = []
    selected_keys: Set[str] = set()
    per_doc_count: Dict[str, int] = {}
    unique_docs_before = len({_doc_key_from_item(x) for x in filtered if _doc_key_from_item(x)})

    phase1_target = max(1, min(doc_diversity_min, top_k, unique_docs_before if unique_docs_before > 0 else top_k))

    for it in filtered:
        if len(selected) >= phase1_target:
            break
        dk = _doc_key_from_item(it)
        ek = str(it.get("evidence_id") or it.get("id") or "")
        if not dk or not ek:
            continue
        if dk in per_doc_count:
            continue
        selected.append(it)
        selected_keys.add(ek)
        per_doc_count[dk] = 1

    phase1_selected = len(selected)

    for it in filtered:
        if len(selected) >= top_k:
            break
        dk = _doc_key_from_item(it)
        ek = str(it.get("evidence_id") or it.get("id") or "")
        if not dk or not ek or ek in selected_keys:
            continue
        if per_doc_count.get(dk, 0) >= per_doc_soft_cap:
            continue
        selected.append(it)
        selected_keys.add(ek)
        per_doc_count[dk] = per_doc_count.get(dk, 0) + 1

    phase2_selected = len(selected) - phase1_selected

    backfill_used = False
    for it in filtered:
        if len(selected) >= top_k:
            break
        dk = _doc_key_from_item(it)
        ek = str(it.get("evidence_id") or it.get("id") or "")
        if not dk or not ek or ek in selected_keys:
            continue
        selected.append(it)
        selected_keys.add(ek)
        per_doc_count[dk] = per_doc_count.get(dk, 0) + 1
        backfill_used = True

    phase3_selected = len(selected) - phase1_selected - phase2_selected
    unique_docs_after = len({_doc_key_from_item(x) for x in selected if _doc_key_from_item(x)})

    return selected[:top_k], {
        "selection_mode": "doc_diversity_two_phase",
        "doc_diversity_min": doc_diversity_min,
        "per_doc_soft_cap": per_doc_soft_cap,
        "unique_docs_before_select": unique_docs_before,
        "unique_docs_after_select": unique_docs_after,
        "phase1_selected": phase1_selected,
        "phase2_selected": phase2_selected,
        "phase3_selected": phase3_selected,
        "selection_backfill_used": bool(backfill_used),
    }


@auto_user_context
def nisb_doc_evidence_scope(args: Dict[str, Any]) -> Dict[str, Any]:
    user_ctx = get_user_ctx()
    base_path = user_ctx.base

    query = str(args.get("query", "") or "").strip()
    scope = str(args.get("scope", "doc") or "doc").strip().lower()

    library_id_in = str(args.get("library_id", "") or "").strip() or None
    doc_id_in = str(args.get("doc_id", "") or "").strip() or None
    group_id_in = str(args.get("group_id", "") or "").strip() or None

    if group_id_in and scope in ("library", "global"):
        print(f"[INFO doc_evidence_scope] scope={scope} group_id={group_id_in}", file=sys.stderr)

    if not query:
        return {"status": "error", "message": "query 不能为空"}
    if scope not in ("doc", "library", "global"):
        return {"status": "error", "message": "scope 必须是 doc/library/global"}
    if scope == "doc" and not (library_id_in and doc_id_in):
        return {"status": "error", "message": "scope=doc 时必须提供 library_id + doc_id"}
    if scope == "library" and not library_id_in:
        return {"status": "error", "message": "scope=library 时必须提供 library_id"}

    if library_id_in:
        try:
            library_id_in = require_safe_id("library_id", library_id_in)
        except Exception as e:
            return {"status": "error", "message": str(e)}
    if doc_id_in:
        try:
            doc_id_in = require_safe_id("doc_id", doc_id_in)
        except Exception as e:
            return {"status": "error", "message": str(e)}

    allowed_libraries: Optional[Set[str]] = None
    allowed_pairs: Optional[Set[Tuple[str, str]]] = None

    if scope in ("library", "global") and group_id_in:
        try:
            group_id_in = require_safe_id("group_id", group_id_in)
            allowed_libraries, allowed_pairs = resolve_group_filter(base_path, group_id_in)
        except Exception as e:
            return {"status": "error", "message": str(e)}

    top_k = int(args.get("top_k", 12) or 12)
    top_k = max(1, min(top_k, 80))

    max_chars = int(args.get("max_chars", SPAN_CHARS) or SPAN_CHARS)
    max_chars = max(1000, min(max_chars, 20000))

    include_text_arg = _bool_or_none(args.get("include_text"))
    include_text = True if include_text_arg is None else bool(include_text_arg)

    weights = args.get("weights") or {"dense": 0.7, "sparse": 0.3}

    doc_diversity_min = _int_or_none(args.get("doc_diversity_min"))
    if doc_diversity_min is None:
        doc_diversity_min = min(6, top_k)
    doc_diversity_min = max(1, min(doc_diversity_min, top_k))

    per_doc_soft_cap = _int_or_none(args.get("per_doc_soft_cap"))
    if per_doc_soft_cap is None:
        per_doc_soft_cap = 2
    per_doc_soft_cap = max(1, min(per_doc_soft_cap, top_k))

    time_assert_strict_arg = _bool_or_none(args.get("time_assert_strict"))
    time_assert_strict = bool(time_assert_strict_arg) if time_assert_strict_arg is not None else False

    start_dt, end_dt, days = _time_window_from_args(args)

    raw_hits, search_debug, search_call_dbg = _call_hybrid_search_with_optional_debug(
        base_path=base_path,
        user_ctx=user_ctx,
        query=query,
        doc_id=(doc_id_in if scope == "doc" else None),
        library_id=(library_id_in if scope in ("doc", "library") else None),
        top_k=top_k,
        weights=weights,
        time_filter_days=days,
        time_start=(str(args.get("time_start") or "").strip() or None),
        time_end=(str(args.get("time_end") or "").strip() or None),
        allowed_libraries=allowed_libraries,
        allowed_pairs=allowed_pairs,
    )

    search_time_dbg = _summarize_search_time_debug(search_debug)
    search_time_applied = bool(search_time_dbg.get("time_filter_applied"))

    filtered: List[Dict[str, Any]] = []
    dropped_deleted = 0
    dropped_time = 0
    dropped_group = 0
    time_assert_mismatch = 0

    dbg: Dict[str, Any] = {
        "scope": scope,
        "group_id": group_id_in,
        "raw_hits": len(raw_hits),
        "kept": 0,
        "dropped_deleted": 0,
        "dropped_time": 0,
        "dropped_group": 0,
        "dropped_no_offset": 0,
        "offset_found_by_fulltext": 0,
        "fast_path_hits": 0,
        "fallback_hits": 0,
        "time_filter_days": days,
        "time_start": (str(args.get("time_start") or "").strip() or None),
        "time_end": (str(args.get("time_end") or "").strip() or None),
        "time_filter_field": "documents.published_at(primary)+metadata.published_at(fallback)",
        "group_filter_applied": bool(group_id_in and scope in ("library", "global")),
        "allowed_libraries_count": (len(allowed_libraries) if isinstance(allowed_libraries, set) else 0),
        "allowed_pairs_count": (len(allowed_pairs) if isinstance(allowed_pairs, set) else 0),
        "search_debug": search_debug if isinstance(search_debug, dict) else {},
        "search_call_debug": search_call_dbg,
        "time_filter_applied": bool(search_time_dbg.get("time_filter_applied")),
        "time_window_on": bool(search_time_dbg.get("time_window_on")),
        "candidate_docs_before_time": search_time_dbg.get("candidate_docs_before_time"),
        "candidate_docs_after_time": search_time_dbg.get("candidate_docs_after_time"),
        "published_at_coverage": search_time_dbg.get("published_at_coverage"),
        "profile_name": search_time_dbg.get("profile_name") or "",
        "time_assert_strict": bool(time_assert_strict),
        "time_assert_only": bool(search_time_applied and not time_assert_strict),
        "time_assert_mismatch": 0,
        "selection_mode": "doc_diversity_two_phase",
        "doc_diversity_min": doc_diversity_min,
        "per_doc_soft_cap": per_doc_soft_cap,
        "unique_docs_before_select": 0,
        "unique_docs_after_select": 0,
        "selection_backfill_used": False,
    }

    per_doc_cache: Dict[str, Dict[str, Any]] = {}
    seen: Set[str] = set()
    published_at_cache: Dict[str, Tuple[Optional[datetime], str]] = {}

    for raw_rank, h in enumerate(raw_hits, start=1):
        lib_id = str(h.get("library_id") or "").strip()
        did = str(h.get("doc_id") or "").strip()
        if not lib_id or not did:
            continue

        if allowed_libraries is not None and allowed_pairs is not None and group_id_in:
            if (lib_id not in allowed_libraries) and ((lib_id, did) not in allowed_pairs):
                dropped_group += 1
                continue

        if not _doc_exists(base_path, lib_id, did):
            dropped_deleted += 1
            continue

        pub_key = f"{lib_id}::{did}"
        if pub_key not in published_at_cache:
            published_at_cache[pub_key] = _read_published_at_consistent_with_source(base_path, lib_id, did)
        published_at, published_at_source = published_at_cache[pub_key]

        if scope in ("library", "global"):
            in_window = _doc_in_window_by_published_at(published_at, start_dt, end_dt)
            if not in_window:
                if search_time_applied and not time_assert_strict:
                    time_assert_mismatch += 1
                else:
                    dropped_time += 1
                    continue

        item = _build_item_fast(
            base_path=base_path,
            scope=scope,
            library_id=lib_id,
            doc_id=did,
            hit=h,
            max_chars=max_chars,
            include_text=include_text,
        )

        if item:
            dbg["fast_path_hits"] += 1
        else:
            cache_key = f"{lib_id}::{did}"
            if cache_key not in per_doc_cache:
                per_doc_cache[cache_key] = {
                    "chunk_map": _build_chunk_map(base_path, lib_id, did),
                    "full_text": _read_full_text(base_path, lib_id, did),
                }

            item = _item_from_hit_fallback(
                base_path=base_path,
                scope=scope,
                library_id=lib_id,
                doc_id=did,
                hit=h,
                chunk_map=per_doc_cache[cache_key]["chunk_map"],
                full_text=per_doc_cache[cache_key]["full_text"],
                max_chars=max_chars,
                include_text=include_text,
                dbg=dbg,
            )
            if item:
                dbg["fallback_hits"] += 1

        if not item:
            continue

        item["published_at"] = _iso_or_none(published_at)
        item["published_at_source"] = published_at_source or ""
        item["citation_doc_key"] = pub_key
        item["retrieval_rank"] = raw_rank

        dedup_key = (
            f"{item.get('library_id')}::{item.get('doc_id')}::span::{item.get('span_index')}::chunk::{item.get('chunk_id')}"
        )
        if dedup_key in seen:
            continue
        seen.add(dedup_key)

        filtered.append(item)

    dbg["dropped_deleted"] = dropped_deleted
    dbg["dropped_time"] = dropped_time
    dbg["dropped_group"] = dropped_group
    dbg["time_assert_mismatch"] = time_assert_mismatch
    dbg["kept"] = len(filtered)

    filtered.sort(
        key=lambda x: (
            float(x.get("relevance", 0.0) or 0.0),
            -int(x.get("retrieval_rank", 10**9) or 10**9),
        ),
        reverse=True,
    )

    items, select_dbg = _select_items_for_citation_semantics(
        filtered,
        top_k=top_k,
        doc_diversity_min=doc_diversity_min,
        per_doc_soft_cap=per_doc_soft_cap,
    )

    dbg["selection_mode"] = select_dbg.get("selection_mode")
    dbg["doc_diversity_min"] = select_dbg.get("doc_diversity_min")
    dbg["per_doc_soft_cap"] = select_dbg.get("per_doc_soft_cap")
    dbg["unique_docs_before_select"] = select_dbg.get("unique_docs_before_select")
    dbg["unique_docs_after_select"] = select_dbg.get("unique_docs_after_select")
    dbg["phase1_selected"] = select_dbg.get("phase1_selected")
    dbg["phase2_selected"] = select_dbg.get("phase2_selected")
    dbg["phase3_selected"] = select_dbg.get("phase3_selected")
    dbg["selection_backfill_used"] = bool(select_dbg.get("selection_backfill_used"))

    try:
        _append_timeline_safe(
            base_path,
            {
                "type": "doc_evidence_scope_search",
                "created_at": datetime.now(timezone.utc).isoformat(),
                "query": query,
                "scope": scope,
                "library_id": library_id_in,
                "doc_id": doc_id_in,
                "group_id": group_id_in,
                "top_k": top_k,
                "time_filter_days": days,
                "time_start": dbg.get("time_start"),
                "time_end": dbg.get("time_end"),
                "result_count": len(items),
                "unique_docs_after_select": dbg.get("unique_docs_after_select"),
            },
        )
    except Exception:
        pass

    return {
        "status": "success",
        "query": query,
        "scope": scope,
        "library_id": library_id_in,
        "doc_id": doc_id_in,
        "group_id": group_id_in,
        "top_k": top_k,
        "max_chars": max_chars,
        "items": items,
        "debug": dbg,
    }
