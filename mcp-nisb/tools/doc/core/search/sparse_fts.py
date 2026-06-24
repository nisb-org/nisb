from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List, Optional, Tuple

from tools.doc.doc_db_sqlite import connect_doc_db, get_doc_db_sqlite

from .bundle_cache import _lookup_chunk_from_bundle, _span_fields_from_char_start
from .common import (
    _T21_SPARSE_GLOBAL_CAP_FACTOR,
    _T21_SPARSE_PER_LIBRARY_LIMIT_FACTOR,
    _T21_SPARSE_PER_LIBRARY_LIMIT_MIN,
    _int_or_none,
    _result_key,
)


def _build_fts5_match_query(query: str) -> str:
    raw = str(query or "").strip()
    if not raw:
        return ""

    tokens = [t.strip() for t in re.findall(r"\\w+", raw, flags=re.UNICODE) if str(t).strip()]
    dedup: List[str] = []
    seen = set()

    for token in tokens:
        if token in seen:
            continue
        seen.add(token)
        dedup.append(token)

    if not dedup:
        safe = raw.replace('"', '""')
        return f'"{safe}"'

    if len(dedup) == 1:
        safe = dedup[0].replace('"', '""')
        return f'"{safe}"'

    safe_terms = [f'"{t.replace(chr(34), chr(34) * 2)}"' for t in dedup[:12]]
    return " OR ".join(safe_terms)


def _batched(items: Iterable[str], size: int) -> Iterable[List[str]]:
    batch: List[str] = []
    for item in items:
        batch.append(item)
        if len(batch) >= size:
            yield batch
            batch = []
    if batch:
        yield batch


def _candidate_doc_ids_by_library(candidate_docs: List[Dict[str, Any]]) -> Dict[str, List[str]]:
    grouped: Dict[str, List[str]] = {}
    for item in candidate_docs:
        library_id = str(item.get("library_id") or "").strip()
        doc_id = str(item.get("doc_id") or "").strip()
        if not library_id or not doc_id:
            continue
        grouped.setdefault(library_id, []).append(doc_id)

    out: Dict[str, List[str]] = {}
    for library_id, doc_ids in grouped.items():
        seen = set()
        ordered = []
        for doc_id in doc_ids:
            if doc_id in seen:
                continue
            seen.add(doc_id)
            ordered.append(doc_id)
        out[library_id] = ordered
    return out


def _fts_sparse_search_library(
    *,
    base_path: str,
    library_id: str,
    query: str,
    doc_ids: Optional[List[str]],
    limit: int,
) -> List[Dict[str, Any]]:
    match_query = _build_fts5_match_query(query)
    if not match_query:
        return []

    db = get_doc_db_sqlite(base_path, library_id)
    conn = connect_doc_db(str(db.db_path), readonly=True)
    rows_out: List[Dict[str, Any]] = []

    try:
        cur = conn.cursor()

        base_sql = """
            SELECT
                chunks_fts.doc_id AS doc_id,
                CAST(chunks_fts.chunk_id AS INTEGER) AS chunk_id,
                COALESCE(c.text, chunks_fts.text) AS text,
                c.char_start AS char_start,
                c.char_end AS char_end,
                bm25(chunks_fts) AS bm25_score
            FROM chunks_fts
            JOIN documents d
              ON d.doc_id = chunks_fts.doc_id
            LEFT JOIN chunks c
              ON c.doc_id = chunks_fts.doc_id
             AND c.chunk_id = CAST(chunks_fts.chunk_id AS INTEGER)
            WHERE d.library_id = ?
              AND chunks_fts MATCH ?
        """

        if doc_ids:
            for batch in _batched(doc_ids, 400):
                placeholders = ",".join(["?"] * len(batch))
                sql = f"""
                    {base_sql}
                    AND chunks_fts.doc_id IN ({placeholders})
                    ORDER BY bm25_score ASC
                    LIMIT ?
                """
                params: List[Any] = [library_id, match_query, *batch, int(limit)]
                cur.execute(sql, params)
                for row in cur.fetchall():
                    rows_out.append(
                        {
                            "doc_id": str(row["doc_id"] or ""),
                            "chunk_id": int(row["chunk_id"]),
                            "text": str(row["text"] or ""),
                            "char_start": _int_or_none(row["char_start"]),
                            "char_end": _int_or_none(row["char_end"]),
                            "bm25_score": float(row["bm25_score"]),
                        }
                    )
        else:
            sql = f"""
                {base_sql}
                ORDER BY bm25_score ASC
                LIMIT ?
            """
            cur.execute(sql, [library_id, match_query, int(limit)])
            for row in cur.fetchall():
                rows_out.append(
                    {
                        "doc_id": str(row["doc_id"] or ""),
                        "chunk_id": int(row["chunk_id"]),
                        "text": str(row["text"] or ""),
                        "char_start": _int_or_none(row["char_start"]),
                        "char_end": _int_or_none(row["char_end"]),
                        "bm25_score": float(row["bm25_score"]),
                    }
                )
    except Exception as e:
        print(f"[HYBRID_DEBUG] fts sparse search failed library_id={library_id}: {e}")
        return []
    finally:
        conn.close()

    rows_out.sort(key=lambda x: float(x.get("bm25_score", 0.0)))
    return rows_out[:limit]


def _fts_sparse_search(
    *,
    base_path: str,
    candidate_docs: List[Dict[str, Any]],
    query: str,
    top_k: int,
    sparse_w: float,
    profile: Dict[str, Any],
) -> Tuple[List[Tuple[str, float]], Dict[str, Dict[str, Any]]]:
    if sparse_w <= 0 or not candidate_docs:
        return [], {}

    grouped_doc_ids = _candidate_doc_ids_by_library(candidate_docs)
    if not grouped_doc_ids:
        return [], {}

    per_library_limit = max(
        int(profile.get("sparse_per_library_limit_min", _T21_SPARSE_PER_LIBRARY_LIMIT_MIN)),
        top_k * int(profile.get("sparse_per_library_limit_factor", _T21_SPARSE_PER_LIBRARY_LIMIT_FACTOR)),
    )

    raw_rows: List[Dict[str, Any]] = []

    for library_id, doc_ids in grouped_doc_ids.items():
        rows = _fts_sparse_search_library(
            base_path=base_path,
            library_id=library_id,
            query=query,
            doc_ids=doc_ids,
            limit=per_library_limit,
        )
        if rows:
            for row in rows:
                row["library_id"] = library_id
                raw_rows.append(row)

    if not raw_rows:
        return [], {}

    raw_rows.sort(key=lambda x: float(x.get("bm25_score", 0.0)))
    raw_rows = raw_rows[: max(18, top_k * int(profile.get("sparse_global_cap_factor", _T21_SPARSE_GLOBAL_CAP_FACTOR)))]

    bm25_values = [float(r.get("bm25_score", 0.0)) for r in raw_rows]
    min_v = min(bm25_values)
    max_v = max(bm25_values)

    sparse_scores: List[Tuple[str, float]] = []
    sparse_chunks: Dict[str, Dict[str, Any]] = {}

    for row in raw_rows:
        library_id = str(row.get("library_id") or "")
        doc_id = str(row.get("doc_id") or "")
        chunk_id = int(row.get("chunk_id"))
        char_start = _int_or_none(row.get("char_start"))
        char_end = _int_or_none(row.get("char_end"))
        text = str(row.get("text") or "")
        span_index = None
        span_start = None
        span_end = None

        if char_start is None or not text:
            bundle_chunk = _lookup_chunk_from_bundle(base_path, library_id, doc_id, chunk_id)
            if bundle_chunk:
                text = str(bundle_chunk.get("text") or text)
                char_start = _int_or_none(bundle_chunk.get("char_start"))
                char_end = _int_or_none(bundle_chunk.get("char_end"))
                span_index = bundle_chunk.get("span_index")
                span_start = bundle_chunk.get("span_start")
                span_end = bundle_chunk.get("span_end")

        if span_index is None:
            span_meta = _span_fields_from_char_start(char_start, None)
            span_index = span_meta["span_index"]
            span_start = span_meta["span_start"]
            span_end = span_meta["span_end"]

        ck = _result_key(library_id, doc_id, chunk_id)

        if max_v == min_v:
            norm = 1.0
        else:
            norm = (max_v - float(row.get("bm25_score", 0.0))) / (max_v - min_v)
            if norm <= 0:
                norm = 0.01

        sparse_scores.append((ck, float(norm) * sparse_w))
        sparse_chunks[ck] = {
            "doc_id": doc_id,
            "library_id": library_id,
            "chunk_id": chunk_id,
            "text": text,
            "char_start": char_start,
            "char_end": char_end,
            "span_index": span_index,
            "span_start": span_start,
            "span_end": span_end,
        }

    return sparse_scores, sparse_chunks
