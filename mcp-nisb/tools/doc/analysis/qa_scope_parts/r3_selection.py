from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from tools.doc.core.span_constants import SPAN_CHARS
from .common import parse_iso_dt_any
from .evidence import ev_doc_key, ev_span_key, normalize_evidence_items
from .published_at import attach_evidence_published_at


def r3_min_from_args(args: Dict[str, Any]) -> Dict[str, Any]:
    raw_dedupe = (
        args.get("dedupe_by_doc_id")
        if args.get("dedupe_by_doc_id") not in (None, "")
        else args.get("dedupeByDocId")
    )

    dedupe_by_doc_id: Optional[bool] = None
    if isinstance(raw_dedupe, bool):
        dedupe_by_doc_id = raw_dedupe
    elif raw_dedupe not in (None, ""):
        s = str(raw_dedupe).strip().lower()
        if s in ("true", "1", "yes", "on"):
            dedupe_by_doc_id = True
        elif s in ("false", "0", "no", "off"):
            dedupe_by_doc_id = False

    if dedupe_by_doc_id is None:
        dedupe_by_doc_id = False

    time_bucket_mode = str(
        args.get("time_bucket_mode")
        if args.get("time_bucket_mode") not in (None, "")
        else (args.get("timeBucketMode") or "")
    ).strip().lower()

    if time_bucket_mode not in ("", "off", "two_phase"):
        time_bucket_mode = "off"
    if not time_bucket_mode:
        time_bucket_mode = "off"

    return {
        "enabled": bool(dedupe_by_doc_id or time_bucket_mode == "two_phase"),
        "dedupe_by_doc_id": bool(dedupe_by_doc_id),
        "time_bucket_mode": time_bucket_mode,
    }


def resolve_r3_window_bounds(
    *,
    days: int,
    start_dt: Optional[datetime],
    end_dt: Optional[datetime],
    now_dt: Optional[datetime] = None,
) -> Tuple[Optional[datetime], Optional[datetime], str]:
    now_ref = now_dt.astimezone(timezone.utc) if now_dt is not None else datetime.now(timezone.utc)

    s = start_dt.astimezone(timezone.utc) if start_dt is not None else None
    e = end_dt.astimezone(timezone.utc) if end_dt is not None else None

    if s is not None and e is not None:
        if s <= e:
            return s, e, "explicit_start_end"
        return e, s, "explicit_start_end_swapped"

    if s is not None:
        if s <= now_ref:
            return s, now_ref, "start_plus_now"
        return now_ref, s, "start_plus_now_swapped"

    if e is not None:
        if int(days or 0) > 0:
            return e - timedelta(days=int(days or 0)), e, "end_plus_days"
        return None, None, ""

    if int(days or 0) > 0:
        return now_ref - timedelta(days=int(days or 0)), now_ref, "days_window"

    return None, None, ""


def pick_r3_boundary(
    *,
    days: int,
    start_dt: Optional[datetime],
    end_dt: Optional[datetime],
    mode: str,
) -> Tuple[Optional[datetime], str, Optional[datetime], Optional[datetime]]:
    if mode != "two_phase":
        return None, "", None, None

    win_start, win_end, source = resolve_r3_window_bounds(
        days=int(days or 0),
        start_dt=start_dt,
        end_dt=end_dt,
    )
    if win_start is None or win_end is None:
        return None, "", win_start, win_end
    if win_start >= win_end:
        return None, source, win_start, win_end

    boundary = win_start + (win_end - win_start) / 2
    return boundary, source, win_start, win_end


def merge_evidence_lists(
    primary: List[Dict[str, Any]],
    extra: List[Dict[str, Any]],
    *,
    limit: int,
) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    seen: Set[Tuple[str, str, int]] = set()

    for src in (primary or []), (extra or []):
        for ev in src:
            if not isinstance(ev, dict):
                continue
            sk = ev_span_key(ev)
            if sk in seen:
                continue
            seen.add(sk)
            out.append(ev)
            if limit > 0 and len(out) >= limit:
                return out

    return out


def needs_two_phase_backfill(
    *,
    r3_min_cfg: Dict[str, Any],
    doc_time_scope: Dict[str, Any],
    r3_selection_dbg: Dict[str, Any],
    single_doc_bypass: bool,
) -> bool:
    if single_doc_bypass:
        return False
    if not bool(r3_min_cfg.get("enabled")):
        return False
    if str(r3_min_cfg.get("time_bucket_mode") or "off") != "two_phase":
        return False
    if not bool(doc_time_scope.get("enabled")):
        return False
    if int(r3_selection_dbg.get("older_candidates") or 0) > 0:
        return False
    return True


def build_two_phase_half_windows(
    *,
    days: int,
    start_dt: Optional[datetime],
    end_dt: Optional[datetime],
) -> Dict[str, Any]:
    boundary, boundary_source, window_start, window_end = pick_r3_boundary(
        days=days,
        start_dt=start_dt,
        end_dt=end_dt,
        mode="two_phase",
    )
    return {
        "boundary": boundary,
        "boundary_source": boundary_source,
        "window_start": window_start,
        "window_end": window_end,
        "older_start": window_start,
        "older_end": boundary,
        "newer_start": boundary,
        "newer_end": window_end,
    }


def fetch_half_window_evidence(
    *,
    evidence_tool,
    base_args: Dict[str, Any],
    half_start: Optional[datetime],
    half_end: Optional[datetime],
    user_base: Path,
    fetch_limit: int,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    dbg: Dict[str, Any] = {
        "called": False,
        "time_start": "",
        "time_end": "",
        "items": 0,
    }

    if half_start is None or half_end is None:
        dbg["reason"] = "missing_half_window"
        return [], dbg

    if half_start >= half_end:
        dbg["reason"] = "invalid_half_window"
        return [], dbg

    ev_args = dict(base_args)
    ev_args.pop("time_filter_days", None)
    ev_args["time_start"] = half_start.isoformat()
    ev_args["time_end"] = half_end.isoformat()
    ev_args["top_k"] = max(1, min(int(fetch_limit or 6), 24))
    ev_args["max_chars"] = int(SPAN_CHARS)
    ev_args["include_text"] = True

    dbg["called"] = True
    dbg["time_start"] = ev_args["time_start"]
    dbg["time_end"] = ev_args["time_end"]
    dbg["top_k"] = ev_args["top_k"]

    ev_res = evidence_tool(ev_args)
    raw_debug = ev_res.get("debug") if isinstance(ev_res, dict) and isinstance(ev_res.get("debug"), dict) else {}

    items = normalize_evidence_items(ev_res if isinstance(ev_res, dict) else {}, max_evidence=ev_args["top_k"])
    items, pub_dbg = attach_evidence_published_at(items, user_base=user_base)

    dbg["items"] = len(items)
    dbg["evidence_scope_debug"] = raw_debug
    dbg["evidence_published_at"] = pub_dbg
    return items, dbg


def time_bucket_evidence(
    evidence: List[Dict[str, Any]],
    *,
    max_evidence: int,
    dedupe_by_doc_id: bool,
    time_bucket_mode: str,
    days: int,
    start_dt: Optional[datetime],
    end_dt: Optional[datetime],
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    ranked = sorted(
        [x for x in evidence if isinstance(x, dict)],
        key=lambda x: float(x.get("relevance") or 0.0),
        reverse=True,
    )

    boundary, boundary_source, win_start, win_end = pick_r3_boundary(
        days=int(days or 0),
        start_dt=start_dt,
        end_dt=end_dt,
        mode=time_bucket_mode,
    )

    older: List[Dict[str, Any]] = []
    newer: List[Dict[str, Any]] = []
    unknown: List[Dict[str, Any]] = []

    for ev in ranked:
        if boundary is None:
            newer.append(ev)
            continue

        dt = parse_iso_dt_any(ev.get("published_at"))
        if dt is None:
            unknown.append(ev)
        elif dt < boundary:
            older.append(ev)
        else:
            newer.append(ev)

    def _dedupe_bucket(bucket: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        seen_spans: Set[Tuple[str, str, int]] = set()
        seen_docs: Set[Tuple[str, str]] = set()

        for ev in bucket:
            sk = ev_span_key(ev)
            dk = ev_doc_key(ev)
            if sk in seen_spans:
                continue
            if dedupe_by_doc_id and dk in seen_docs:
                continue
            seen_spans.add(sk)
            seen_docs.add(dk)
            out.append(ev)
        return out

    older_d = _dedupe_bucket(older)
    newer_d = _dedupe_bucket(newer)
    unknown_d = _dedupe_bucket(unknown)

    selected: List[Dict[str, Any]] = []
    selected_spans: Set[Tuple[str, str, int]] = set()
    selected_docs: Set[Tuple[str, str]] = set()

    def push(ev: Dict[str, Any], *, allow_same_doc: bool = False) -> bool:
        sk = ev_span_key(ev)
        dk = ev_doc_key(ev)

        if sk in selected_spans:
            return False
        if dedupe_by_doc_id and (not allow_same_doc) and dk in selected_docs:
            return False

        selected_spans.add(sk)
        selected_docs.add(dk)
        selected.append(ev)
        return True

    guaranteed_older = 0
    guaranteed_newer = 0

    if boundary is not None:
        for ev in older_d:
            if push(ev):
                guaranteed_older += 1
                break

        for ev in newer_d:
            if push(ev):
                guaranteed_newer += 1
                break

    mixed_tail: List[Dict[str, Any]] = []
    max_len = max(len(older_d), len(newer_d))
    for i in range(max_len):
        if i < len(older_d):
            mixed_tail.append(older_d[i])
        if i < len(newer_d):
            mixed_tail.append(newer_d[i])
    mixed_tail.extend(unknown_d)

    for ev in mixed_tail:
        if len(selected) >= max_evidence:
            break
        push(ev)

    relaxed_same_doc_fill = 0
    if len(selected) < max_evidence and dedupe_by_doc_id:
        for ev in ranked:
            if len(selected) >= max_evidence:
                break
            if push(ev, allow_same_doc=True):
                relaxed_same_doc_fill += 1

    selected_older = 0
    selected_newer = 0
    selected_unknown = 0
    if boundary is not None:
        for ev in selected:
            dt = parse_iso_dt_any(ev.get("published_at"))
            if dt is None:
                selected_unknown += 1
            elif dt < boundary:
                selected_older += 1
            else:
                selected_newer += 1

    dbg = {
        "enabled": bool(dedupe_by_doc_id or time_bucket_mode == "two_phase"),
        "dedupe_by_doc_id": bool(dedupe_by_doc_id),
        "time_bucket_mode": time_bucket_mode,
        "boundary": boundary.isoformat() if boundary else "",
        "boundary_source": boundary_source,
        "window_start": win_start.isoformat() if win_start else "",
        "window_end": win_end.isoformat() if win_end else "",
        "bucket_a": "older" if boundary else "",
        "bucket_b": "newer" if boundary else "",
        "older_candidates": len(older),
        "newer_candidates": len(newer),
        "unknown_candidates": len(unknown),
        "older_candidates_after_bucket_dedupe": len(older_d),
        "newer_candidates_after_bucket_dedupe": len(newer_d),
        "unknown_candidates_after_bucket_dedupe": len(unknown_d),
        "guaranteed_older": guaranteed_older,
        "guaranteed_newer": guaranteed_newer,
        "selected_older": selected_older,
        "selected_newer": selected_newer,
        "selected_unknown": selected_unknown,
        "relaxed_same_doc_fill": relaxed_same_doc_fill,
        "selected_docs": len({ev_doc_key(x) for x in selected}),
        "selected_items": len(selected),
    }
    return selected[:max_evidence], dbg


def annotate_evidence_time_bucket(
    evidence: List[Dict[str, Any]],
    *,
    days: int,
    start_dt: Optional[datetime],
    end_dt: Optional[datetime],
    mode: str,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    boundary, boundary_source, win_start, win_end = pick_r3_boundary(
        days=int(days or 0),
        start_dt=start_dt,
        end_dt=end_dt,
        mode=mode,
    )

    out: List[Dict[str, Any]] = []
    older_count = 0
    newer_count = 0
    unknown_count = 0

    for ev in evidence or []:
        if not isinstance(ev, dict):
            continue

        ev2 = dict(ev)
        ev2["time_bucket_boundary"] = boundary.isoformat() if boundary else ""

        if boundary is None:
            ev2["time_bucket"] = "all"
            newer_count += 1
            out.append(ev2)
            continue

        dt = parse_iso_dt_any(ev.get("published_at"))
        if dt is None:
            ev2["time_bucket"] = "unknown"
            unknown_count += 1
        elif dt < boundary:
            ev2["time_bucket"] = "older"
            older_count += 1
        else:
            ev2["time_bucket"] = "newer"
            newer_count += 1

        out.append(ev2)

    dbg = {
        "boundary": boundary.isoformat() if boundary else "",
        "boundary_source": boundary_source,
        "window_start": win_start.isoformat() if win_start else "",
        "window_end": win_end.isoformat() if win_end else "",
        "older_count": older_count,
        "newer_count": newer_count,
        "unknown_count": unknown_count,
    }
    return out, dbg


def pick_doc_time_fetch_params(
    top_k: int,
    max_evidence: int,
    *,
    time_filter_enabled: bool,
    r3_min_enabled: bool = False,
) -> Tuple[int, int]:
    try:
        tk = int(top_k)
    except Exception:
        tk = 18

    try:
        me = int(max_evidence)
    except Exception:
        me = 14

    tk = max(1, min(tk, 80))
    me = max(1, min(me, 200))

    if r3_min_enabled:
        fetch_k = max(tk, min(80, max(me * 3, 24)))
        fetch_evidence = max(me, min(80, max(me * 3, 24)))
        return fetch_k, fetch_evidence

    return tk, me
