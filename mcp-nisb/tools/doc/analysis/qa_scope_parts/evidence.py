from __future__ import annotations

from typing import Any, Dict, List, Set, Tuple

from .common import clean_id


def _clean_text(v: Any) -> str:
    if v is None:
        return ""
    return str(v).strip()


def ev_doc_key(ev: Dict[str, Any]) -> Tuple[str, str]:
    return (clean_id(ev.get("library_id")), clean_id(ev.get("doc_id")))


def ev_span_key(ev: Dict[str, Any]) -> Tuple[str, str, int]:
    lib_id = clean_id(ev.get("library_id"))
    doc_id = clean_id(ev.get("doc_id"))
    try:
        span_i = int(ev.get("span_index"))
    except Exception:
        span_i = -1
    return (lib_id, doc_id, span_i)


def _pick_excerpt(it: Dict[str, Any]) -> str:
    excerpt = it.get("quote")
    if not excerpt:
        excerpt = it.get("text") or it.get("excerpt") or ""
    return _clean_text(excerpt)


def normalize_evidence_items(ev_res: dict, max_evidence: int) -> List[Dict[str, Any]]:
    raw: List[Any] = []
    if isinstance(ev_res, dict) and ev_res.get("status") == "success":
        raw = list(ev_res.get("items") or [])

    out: List[Dict[str, Any]] = []
    for it in raw:
        if not isinstance(it, dict):
            continue

        lib_id = clean_id(it.get("library_id"))
        doc_id = clean_id(it.get("doc_id"))
        if not lib_id or not doc_id:
            continue

        span_raw = it.get("span_index")
        try:
            span_i = int(span_raw) if span_raw is not None else None
        except Exception:
            span_i = None
        if span_i is None:
            continue

        evidence_id = it.get("evidence_id") or it.get("id")
        offset = it.get("char_start")
        if offset is None:
            offset = it.get("offset")

        excerpt = _pick_excerpt(it)

        out.append(
            {
                "evidence_id": evidence_id,
                "library_id": lib_id,
                "doc_id": doc_id,
                "doc_title": _clean_text(it.get("doc_title")),
                "span_index": span_i,
                "relevance": it.get("relevance"),
                "offset": offset,
                "char_start": offset,
                "excerpt": excerpt,
                "quote": excerpt,
                "published_at": _clean_text(it.get("published_at")),
                "published_at_source": _clean_text(it.get("published_at_source")),
            }
        )

        if len(out) >= int(max_evidence or 0):
            break

    return out


def short_quote_from_evidence(ev: Dict[str, Any], *, max_chars: int = 220) -> str:
    txt = _clean_text(ev.get("quote") or ev.get("excerpt") or ev.get("text"))
    if not txt:
        return ""
    if len(txt) <= max_chars:
        return txt
    return txt[: max(1, int(max_chars) - 1)].rstrip() + "…"


def build_shared_citation_pool(
    evidence: List[Dict[str, Any]],
    *,
    max_pool: int,
    per_doc_soft_cap: int = 2,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    pool: List[Dict[str, Any]] = []
    seen_span: Set[Tuple[str, str, int]] = set()
    per_doc: Dict[Tuple[str, str], int] = {}
    candidate_total = 0

    for ev in evidence or []:
        if not isinstance(ev, dict):
            continue

        doc_key = ev_doc_key(ev)
        span_key = ev_span_key(ev)

        if not doc_key[1]:
            continue
        if span_key[2] < 0:
            continue

        candidate_total += 1

        if span_key in seen_span:
            continue

        used = int(per_doc.get(doc_key, 0))
        if used >= int(per_doc_soft_cap):
            continue

        quote = short_quote_from_evidence(ev, max_chars=220)
        if not quote:
            continue

        pool.append(
            {
                "library_id": doc_key[0],
                "doc_id": doc_key[1],
                "span_index": span_key[2],
                "quote": quote,
                "note": "shared_evidence_pool",
                "doc_title": ev.get("doc_title"),
                "published_at": ev.get("published_at"),
                "published_at_source": ev.get("published_at_source"),
                "time_bucket": ev.get("time_bucket"),
                "time_bucket_boundary": ev.get("time_bucket_boundary"),
                "relevance": ev.get("relevance"),
            }
        )
        seen_span.add(span_key)
        per_doc[doc_key] = used + 1

        if len(pool) >= int(max_pool):
            break

    dbg = {
        "candidate_total": candidate_total,
        "pool_count": len(pool),
        "pool_unique_docs": len({(x.get('library_id'), x.get('doc_id')) for x in pool}),
        "max_pool": int(max_pool),
        "per_doc_soft_cap": int(per_doc_soft_cap),
        "source": "final_evidence",
    }
    return pool, dbg


def build_public_evidence_items(evidence: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for x in evidence or []:
        if not isinstance(x, dict):
            continue
        out.append(
            {
                "library_id": x.get("library_id"),
                "doc_id": x.get("doc_id"),
                "span_index": x.get("span_index"),
                "relevance": x.get("relevance"),
                "published_at": x.get("published_at"),
                "published_at_source": x.get("published_at_source"),
                "doc_title": x.get("doc_title"),
                "time_bucket": x.get("time_bucket"),
                "time_bucket_boundary": x.get("time_bucket_boundary"),
            }
        )
    return out
