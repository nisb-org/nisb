from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .common import (
    clean_id,
    parse_iso_dt_any,
    safe_bool_or_none,
    safe_float_or_none,
    safe_int_or_none,
)
from .published_at import read_doc_published_at_with_source


def within_last_days(dt: Optional[datetime], days: int) -> bool:
    d = int(days or 0)
    if d <= 0:
        return True
    if dt is None:
        return False

    now = datetime.now(timezone.utc)
    start = now - timedelta(days=d)
    return start <= dt <= now


def extract_search_time_scope_debug(ev_debug: Dict[str, Any]) -> Dict[str, Any]:
    out: Dict[str, Any] = {
        "time_filter_applied": False,
        "time_window_on": False,
        "candidate_docs_before_time": None,
        "candidate_docs_after_time": None,
        "published_at_coverage": None,
        "profile_name": "",
    }

    if not isinstance(ev_debug, dict):
        return out

    candidates: List[Dict[str, Any]] = [ev_debug]
    for key in (
        "time_scope",
        "time_scope_debug",
        "search_debug",
        "hybrid_search_debug",
        "hybrid_debug",
        "debug",
    ):
        val = ev_debug.get(key)
        if isinstance(val, dict):
            candidates.append(val)

    def pick_bool(*keys: str) -> Optional[bool]:
        for obj in candidates:
            for k in keys:
                v = safe_bool_or_none(obj.get(k))
                if v is not None:
                    return v
        return None

    def pick_int(*keys: str) -> Optional[int]:
        for obj in candidates:
            for k in keys:
                v = safe_int_or_none(obj.get(k))
                if v is not None:
                    return v
        return None

    def pick_float(*keys: str) -> Optional[float]:
        for obj in candidates:
            for k in keys:
                v = safe_float_or_none(obj.get(k))
                if v is not None:
                    return v
        return None

    def pick_str(*keys: str) -> str:
        for obj in candidates:
            for k in keys:
                v = str(obj.get(k) or "").strip()
                if v:
                    return v
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
        time_filter_applied = bool(before_count is not None and after_count is not None)
    if time_window_on is None:
        time_window_on = bool(time_filter_applied)

    out["time_filter_applied"] = bool(time_filter_applied)
    out["time_window_on"] = bool(time_window_on)
    out["candidate_docs_before_time"] = before_count
    out["candidate_docs_after_time"] = after_count
    out["published_at_coverage"] = coverage
    out["profile_name"] = profile_name
    return out


def doc_time_scope_from_args(args: Dict[str, Any]) -> Dict[str, Any]:
    raw_days = (
        args.get("time_filter_days")
        if args.get("time_filter_days") not in (None, "")
        else args.get("timeFilterDays")
    )
    raw_start = args.get("time_start") if args.get("time_start") not in (None, "") else args.get("timeStart")
    raw_end = args.get("time_end") if args.get("time_end") not in (None, "") else args.get("timeEnd")

    try:
        days = int(raw_days) if raw_days not in (None, "") else 0
    except Exception:
        days = 0

    days = max(0, min(3650, int(days or 0)))

    start_raw = str(raw_start or "").strip()
    end_raw = str(raw_end or "").strip()

    start_dt = parse_iso_dt_any(start_raw)
    end_dt = parse_iso_dt_any(end_raw)

    if start_dt is not None and end_dt is not None and start_dt > end_dt:
        start_dt, end_dt = end_dt, start_dt
        start_raw, end_raw = end_raw, start_raw

    enabled = bool(days > 0 or start_dt is not None or end_dt is not None)

    return {
        "enabled": enabled,
        "days": days,
        "time_start": start_raw,
        "time_end": end_raw,
        "start_dt": start_dt,
        "end_dt": end_dt,
    }


def within_doc_time_scope(
    dt: Optional[datetime],
    *,
    days: int,
    start_dt: Optional[datetime],
    end_dt: Optional[datetime],
) -> bool:
    if int(days or 0) <= 0 and start_dt is None and end_dt is None:
        return True
    if dt is None:
        return False

    if int(days or 0) > 0 and not within_last_days(dt, int(days or 0)):
        return False
    if start_dt is not None and dt < start_dt:
        return False
    if end_dt is not None and dt > end_dt:
        return False

    return True


def filter_evidence_by_doc_time_scope(
    evidence: List[Dict[str, Any]],
    *,
    user_base: Path,
    days: int,
    start_dt: Optional[datetime],
    end_dt: Optional[datetime],
    fallback_filter: bool = False,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    dbg: Dict[str, Any] = {
        "enabled": bool(int(days or 0) > 0 or start_dt is not None or end_dt is not None),
        "days": int(days or 0),
        "time_start": start_dt.isoformat() if start_dt else "",
        "time_end": end_dt.isoformat() if end_dt else "",
        "before": len(evidence),
        "after": 0,
        "dropped": 0,
        "window_mismatch_count": 0,
        "mode": "qa_scope_fallback_filter" if fallback_filter else "assert_only",
        "published_at_source_counts": {},
    }

    if not dbg["enabled"]:
        return evidence, dbg

    cache: Dict[Tuple[str, str], Tuple[Optional[datetime], str]] = {}
    source_counts: Dict[str, int] = {}
    out: List[Dict[str, Any]] = []
    mismatched = 0

    for ev in evidence or []:
        if not isinstance(ev, dict):
            continue

        lib_id = clean_id(ev.get("library_id"))
        doc_id = clean_id(ev.get("doc_id"))
        if not lib_id or not doc_id:
            continue

        key = (lib_id, doc_id)
        if key not in cache:
            dt0 = parse_iso_dt_any(ev.get("published_at"))
            src0 = clean_id(ev.get("published_at_source")) or "evidence"
            if dt0 is not None:
                cache[key] = (dt0, src0)
            else:
                cache[key] = read_doc_published_at_with_source(user_base, lib_id, doc_id)

        published_at, src = cache[key]
        source_counts[src] = int(source_counts.get(src, 0)) + 1

        ok = within_doc_time_scope(
            published_at,
            days=int(days or 0),
            start_dt=start_dt,
            end_dt=end_dt,
        )

        if ok:
            out.append(ev)
            continue

        mismatched += 1
        if not fallback_filter:
            out.append(ev)

    dbg["published_at_source_counts"] = source_counts
    dbg["window_mismatch_count"] = mismatched
    dbg["after"] = len(out)
    dbg["dropped"] = max(0, dbg["before"] - dbg["after"]) if fallback_filter else 0
    return out, dbg

