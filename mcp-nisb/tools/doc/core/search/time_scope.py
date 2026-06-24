from __future__ import annotations

import os
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Tuple

from tools.doc.doc_db_sqlite import connect_doc_db, get_doc_db_sqlite

from .common import (
    _T21_CANDIDATE_DOC_CAP,
    _T21_DENSE_DOC_CAP,
    _T21_DENSE_MAX_WORKERS,
    _T21_SPARSE_GLOBAL_CAP_FACTOR,
    _T21_SPARSE_PER_LIBRARY_LIMIT_FACTOR,
    _T21_SPARSE_PER_LIBRARY_LIMIT_MIN,
    _T21S_ENABLE_NEIGHBOR_EXPANSION,
    _T21S_EXPERIMENTAL_DENSE_CAP,
    _T21S_EXPERIMENTAL_RECALL,
    _T21S_EXPERIMENTAL_SPARSE_FACTOR,
    _T21S_EXPERIMENTAL_SPARSE_GLOBAL_FACTOR,
    _T21S_MAX_PER_DOC_RESULTS,
    _T21S_SMALL_CANDIDATE_THRESHOLD,
    _parse_iso_dt,
)
from .bundle_cache import _metadata_fp, _read_doc_published_at


def _time_window_from_args(
    *,
    time_filter_days: Optional[int],
    time_start: Optional[str],
    time_end: Optional[str],
) -> Tuple[Optional[datetime], Optional[datetime]]:
    start_dt = _parse_iso_dt(time_start or "")
    end_dt = _parse_iso_dt(time_end or "")

    if start_dt or end_dt:
        return start_dt, end_dt

    if time_filter_days is None:
        return None, None

    try:
        days = int(time_filter_days)
    except Exception:
        return None, None

    if days <= 0:
        return None, None

    now = datetime.now(timezone.utc)
    return now - timedelta(days=days), now


def _has_time_window(start_dt: Optional[datetime], end_dt: Optional[datetime]) -> bool:
    return start_dt is not None or end_dt is not None


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


def _estimate_time_window_days(
    start_dt: Optional[datetime],
    end_dt: Optional[datetime],
) -> int:
    if start_dt is None and end_dt is None:
        return 0

    if start_dt is not None:
        end_ref = end_dt or datetime.now(timezone.utc)
        if end_ref < start_dt:
            end_ref = start_dt
        seconds = max(0.0, (end_ref - start_dt).total_seconds())
        return max(1, int((seconds + 86399) // 86400))

    return 30


def _time_window_profile_name(window_days: int) -> str:
    if window_days <= 1:
        return "t21-time-window-1d"
    if window_days <= 3:
        return "t21-time-window-3d"
    if window_days <= 7:
        return "t21-time-window-7d"
    if window_days <= 30:
        return "t21-time-window-30d"
    return "t21-time-window-wide"


def _candidate_cap_for_time_window(
    *,
    base_cap: int,
    candidate_docs_count: int,
    window_days: int,
) -> int:
    base = max(1, int(base_cap or 1))

    if window_days <= 3:
        scale = 1
    elif window_days <= 7:
        scale = 2
    elif window_days <= 14:
        scale = 3
    elif window_days <= 30:
        scale = 4
    else:
        scale = 5

    cap = base * scale
    if candidate_docs_count > 0:
        cap = min(candidate_docs_count, cap)
    return max(base, cap)


def _iter_library_ids(
    base_path: str,
    library_id: Optional[str],
    allowed_libraries: Optional[set[str]],
    allowed_pairs: Optional[set[tuple[str, str]]],
) -> List[str]:
    if library_id:
        return [library_id]

    out = set()
    if allowed_libraries:
        out.update({str(x).strip() for x in allowed_libraries if str(x).strip()})
    if allowed_pairs:
        out.update({str(lib_id).strip() for lib_id, _doc_id in allowed_pairs if str(lib_id).strip()})

    if out:
        return sorted(out)

    libs_dir = os.path.join(base_path, "libraries")
    if not os.path.isdir(libs_dir):
        return []

    try:
        return sorted(
            [
                name
                for name in os.listdir(libs_dir)
                if os.path.isdir(os.path.join(libs_dir, name))
            ]
        )
    except Exception:
        return []


def _allowed_doc_scope_for_library(
    library_id: str,
    allowed_libraries: Optional[set[str]],
    allowed_pairs: Optional[set[tuple[str, str]]],
) -> Tuple[bool, Optional[set[str]]]:
    al = allowed_libraries or set()
    ap = allowed_pairs or set()

    if not al and not ap:
        return True, None

    if library_id in al:
        return True, None

    scoped_doc_ids = {
        str(doc_id).strip()
        for lib_id, doc_id in ap
        if str(lib_id).strip() == library_id and str(doc_id).strip()
    }
    if scoped_doc_ids:
        return True, scoped_doc_ids

    return False, None


def _fetch_docs_from_sqlite(
    *,
    base_path: str,
    library_id: str,
    allowed_libraries: Optional[set[str]],
    allowed_pairs: Optional[set[tuple[str, str]]],
    start_dt: Optional[datetime],
    end_dt: Optional[datetime],
) -> List[Dict[str, Any]]:
    is_allowed, allowed_doc_ids = _allowed_doc_scope_for_library(library_id, allowed_libraries, allowed_pairs)
    if not is_allowed:
        return []

    db = get_doc_db_sqlite(base_path, library_id)
    results: List[Dict[str, Any]] = []
    seen_doc_ids: set[str] = set()

    def _append_row(doc_id_val: Any, published_at_raw: Any) -> None:
        did = str(doc_id_val or "").strip()
        if not did or did in seen_doc_ids:
            return
        published_at = _parse_iso_dt(str(published_at_raw or "").strip())
        results.append(
            {
                "doc_id": did,
                "library_id": library_id,
                "published_at": published_at,
            }
        )
        seen_doc_ids.add(did)

    conn = connect_doc_db(str(db.db_path), readonly=True)
    try:
        cur = conn.cursor()

        sql = [
            "SELECT doc_id, published_at",
            "FROM documents",
            "WHERE library_id = ?",
        ]
        params: List[Any] = [library_id]

        if allowed_doc_ids:
            placeholders = ",".join(["?"] * len(allowed_doc_ids))
            sql.append(f"AND doc_id IN ({placeholders})")
            params.extend(sorted(allowed_doc_ids))

        if start_dt is not None or end_dt is not None:
            sql.append("AND published_at IS NOT NULL")
            if start_dt is not None:
                sql.append("AND published_at >= ?")
                params.append(start_dt.isoformat())
            if end_dt is not None:
                sql.append("AND published_at <= ?")
                params.append(end_dt.isoformat())

        sql.append("ORDER BY published_at DESC, doc_id DESC")
        cur.execute(" ".join(sql), params)
        for row in cur.fetchall():
            _append_row(row["doc_id"], row["published_at"])

        if start_dt is not None or end_dt is not None:
            sql_null = [
                "SELECT doc_id, published_at",
                "FROM documents",
                "WHERE library_id = ?",
                "AND published_at IS NULL",
            ]
            null_params: List[Any] = [library_id]

            if allowed_doc_ids:
                placeholders = ",".join(["?"] * len(allowed_doc_ids))
                sql_null.append(f"AND doc_id IN ({placeholders})")
                null_params.extend(sorted(allowed_doc_ids))

            cur.execute(" ".join(sql_null), null_params)
            for row in cur.fetchall():
                did = str(row["doc_id"] or "").strip()
                if not did or did in seen_doc_ids:
                    continue
                published_at = _read_doc_published_at(_metadata_fp(base_path, library_id, did))
                if not _doc_in_window_by_published_at(published_at, start_dt, end_dt):
                    continue
                results.append(
                    {
                        "doc_id": did,
                        "library_id": library_id,
                        "published_at": published_at,
                    }
                )
                seen_doc_ids.add(did)
    finally:
        conn.close()

    return results


def _compute_published_at_coverage(candidate_docs: List[Dict[str, Any]]) -> float:
    if not candidate_docs:
        return 1.0
    valid = 0
    for item in candidate_docs:
        if isinstance(item.get("published_at"), datetime):
            valid += 1
    return round(valid / max(1, len(candidate_docs)), 4)


def _resolve_retrieval_profile(
    *,
    candidate_docs_count: int,
    start_dt: Optional[datetime],
    end_dt: Optional[datetime],
    published_at_coverage: float,
) -> Dict[str, Any]:
    time_window_on = _has_time_window(start_dt, end_dt)
    window_days = _estimate_time_window_days(start_dt, end_dt)

    profile = {
        "name": "t21-default",
        "time_window_on": time_window_on,
        "time_window_days": window_days,
        "published_at_coverage": published_at_coverage,
        "candidate_cap": None,
        "dense_cap": _T21_DENSE_DOC_CAP,
        "sparse_per_library_limit_min": _T21_SPARSE_PER_LIBRARY_LIMIT_MIN,
        "sparse_per_library_limit_factor": _T21_SPARSE_PER_LIBRARY_LIMIT_FACTOR,
        "sparse_global_cap_factor": _T21_SPARSE_GLOBAL_CAP_FACTOR,
        "dense_max_workers": _T21_DENSE_MAX_WORKERS,
        "per_doc_max_chunks": _T21S_MAX_PER_DOC_RESULTS,
        "neighbor_expansion": False,
    }

    if time_window_on:
        profile["name"] = _time_window_profile_name(window_days)
        profile["candidate_cap"] = _candidate_cap_for_time_window(
            base_cap=_T21_CANDIDATE_DOC_CAP,
            candidate_docs_count=candidate_docs_count,
            window_days=window_days,
        )
        return profile

    if not _T21S_EXPERIMENTAL_RECALL:
        return profile

    if candidate_docs_count <= _T21S_SMALL_CANDIDATE_THRESHOLD and published_at_coverage >= 0.5:
        exp = dict(profile)
        exp["name"] = "t21-exp-small"
        exp["dense_cap"] = _T21S_EXPERIMENTAL_DENSE_CAP
        exp["sparse_per_library_limit_factor"] = _T21S_EXPERIMENTAL_SPARSE_FACTOR
        exp["sparse_global_cap_factor"] = _T21S_EXPERIMENTAL_SPARSE_GLOBAL_FACTOR
        exp["neighbor_expansion"] = _T21S_ENABLE_NEIGHBOR_EXPANSION
        return exp

    return profile


def _dedupe_candidate_docs(candidate_docs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()

    for item in candidate_docs:
        if not isinstance(item, dict):
            continue
        key = (
            str(item.get("library_id") or "").strip(),
            str(item.get("doc_id") or "").strip(),
        )
        if not key[1] or key in seen:
            continue
        seen.add(key)
        out.append(item)

    return out


def _spread_candidate_docs(candidate_docs: List[Dict[str, Any]], cap: int) -> List[Dict[str, Any]]:
    cap = max(1, int(cap or 1))
    if len(candidate_docs) <= cap:
        return candidate_docs

    head_keep = min(cap, max(12, cap // 4))
    out = list(candidate_docs[:head_keep])

    remaining = candidate_docs[head_keep:]
    tail_slots = cap - len(out)
    if tail_slots <= 0 or not remaining:
        return _dedupe_candidate_docs(out)[:cap]

    if len(remaining) <= tail_slots:
        out.extend(remaining)
        return _dedupe_candidate_docs(out)[:cap]

    sampled: List[Dict[str, Any]] = []
    last_index = len(remaining) - 1
    picked_indexes: set[int] = set()

    if tail_slots == 1:
        sampled.append(remaining[-1])
    else:
        for i in range(tail_slots):
            idx = int(round(i * last_index / max(1, tail_slots - 1)))
            if idx in picked_indexes:
                continue
            picked_indexes.add(idx)
            sampled.append(remaining[idx])

    if len(sampled) < tail_slots:
        seen_keys = {
            (
                str(x.get("library_id") or "").strip(),
                str(x.get("doc_id") or "").strip(),
            )
            for x in sampled
            if isinstance(x, dict)
        }
        for item in remaining:
            if len(sampled) >= tail_slots:
                break
            key = (
                str(item.get("library_id") or "").strip(),
                str(item.get("doc_id") or "").strip(),
            )
            if not key[1] or key in seen_keys:
                continue
            seen_keys.add(key)
            sampled.append(item)

    out.extend(sampled)
    return _dedupe_candidate_docs(out)[:cap]


def _apply_candidate_cap(candidate_docs: List[Dict[str, Any]], profile: Dict[str, Any]) -> List[Dict[str, Any]]:
    cap = profile.get("candidate_cap")
    if cap is None:
        return candidate_docs

    try:
        cap_int = int(cap)
    except Exception:
        return candidate_docs

    if cap_int <= 0 or len(candidate_docs) <= cap_int:
        return candidate_docs

    if bool(profile.get("time_window_on")):
        return _spread_candidate_docs(candidate_docs, cap_int)

    return candidate_docs[:cap_int]


def _list_candidate_docs(
    *,
    base_path: str,
    user_ctx: Any,
    library_id: Optional[str],
    doc_id: Optional[str],
    allowed_libraries: Optional[set[str]],
    allowed_pairs: Optional[set[tuple[str, str]]],
    start_dt: Optional[datetime],
    end_dt: Optional[datetime],
) -> List[Dict[str, Any]]:
    if doc_id and library_id:
        return [{"doc_id": doc_id, "library_id": library_id, "published_at": None}]

    candidates: List[Dict[str, Any]] = []
    lib_ids = _iter_library_ids(base_path, library_id, allowed_libraries, allowed_pairs)
    if not lib_ids:
        return []

    for lid in lib_ids:
        try:
            rows = _fetch_docs_from_sqlite(
                base_path=base_path,
                library_id=lid,
                allowed_libraries=allowed_libraries,
                allowed_pairs=allowed_pairs,
                start_dt=start_dt,
                end_dt=end_dt,
            )
            if rows:
                candidates.extend(rows)
        except Exception as e:
            print(f"[HYBRID_DEBUG] sqlite candidate fetch failed library_id={lid}: {e}")
            continue

    def _sort_key(x: Dict[str, Any]) -> Tuple[int, str, str]:
        p = x.get("published_at")
        if isinstance(p, datetime):
            return (1, p.isoformat(), str(x.get("doc_id") or ""))
        return (0, "", str(x.get("doc_id") or ""))

    candidates.sort(key=_sort_key, reverse=True)
    return candidates

