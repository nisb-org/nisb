from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from .bundle_cache import _get_doc_bundle_cached
from .common import (
    _T21_DENSE_DOC_CAP,
    _build_result_item,
    _collect_result_metrics,
    _cosine_similarity,
    _int_or_none,
    _result_key,
    _top_indices_desc,
)
from .time_scope import _has_time_window


def _process_doc_candidate_dense(
    *,
    base_path: str,
    library_id: str,
    doc_id: str,
    query_embedding: Optional[np.ndarray],
    top_k: int,
    dense_w: float,
) -> Tuple[List[Tuple[str, float]], Dict[str, Dict[str, Any]]]:
    if query_embedding is None or dense_w <= 0:
        return [], {}

    bundle = _get_doc_bundle_cached(base_path, library_id, doc_id)
    embeddings_matrix = bundle.get("embeddings_matrix")
    chunks = bundle.get("chunks") or []

    if embeddings_matrix is None or len(embeddings_matrix) == 0 or not chunks:
        return [], {}

    local_dense: List[Tuple[str, float]] = []
    local_chunks: Dict[str, Dict[str, Any]] = {}

    sims = _cosine_similarity(query_embedding, embeddings_matrix)
    dense_limit = min(max(top_k * 2, top_k), len(sims))
    top_indices = _top_indices_desc(sims, dense_limit)

    for idx in top_indices:
        if idx >= len(chunks):
            continue
        chunk = chunks[int(idx)]
        ck = _result_key(library_id, doc_id, chunk.get("chunk_id"))
        local_chunks[ck] = {
            "doc_id": doc_id,
            "library_id": library_id,
            "chunk_id": chunk.get("chunk_id"),
            "text": chunk.get("text"),
            "char_start": chunk.get("char_start"),
            "char_end": chunk.get("char_end"),
            "span_index": chunk.get("span_index"),
            "span_start": chunk.get("span_start"),
            "span_end": chunk.get("span_end"),
        }
        local_dense.append((ck, float(sims[int(idx)]) * dense_w))

    return local_dense, local_chunks


def _select_dense_candidate_docs(
    *,
    candidate_docs: List[Dict[str, Any]],
    sparse_chunks: Optional[Dict[str, Dict[str, Any]]],
    start_dt,
    end_dt,
    sparse_w: float,
    profile: Dict[str, Any],
) -> List[Dict[str, Any]]:
    if not candidate_docs:
        return []

    dense_cap = min(int(profile.get("dense_cap", _T21_DENSE_DOC_CAP)), len(candidate_docs))
    if dense_cap <= 0:
        return []

    if not _has_time_window(start_dt, end_dt) and sparse_w <= 0:
        return candidate_docs[:dense_cap]

    prioritized: List[Dict[str, Any]] = []
    seen = set()

    if sparse_chunks:
        sparse_doc_keys = {
            (str(v.get("library_id") or "").strip(), str(v.get("doc_id") or "").strip())
            for v in sparse_chunks.values()
            if str(v.get("library_id") or "").strip() and str(v.get("doc_id") or "").strip()
        }
        for item in candidate_docs:
            k = (str(item.get("library_id") or "").strip(), str(item.get("doc_id") or "").strip())
            if k in sparse_doc_keys and k not in seen:
                prioritized.append(item)
                seen.add(k)
                if len(prioritized) >= dense_cap:
                    return prioritized[:dense_cap]

    for item in candidate_docs:
        k = (str(item.get("library_id") or "").strip(), str(item.get("doc_id") or "").strip())
        if k in seen:
            continue
        prioritized.append(item)
        seen.add(k)
        if len(prioritized) >= dense_cap:
            break

    return prioritized[:dense_cap]


def _merge_ranked_results(
    *,
    combined: Dict[str, float],
    all_chunks: Dict[str, Dict[str, Any]],
    top_k: int,
    per_doc_max_chunks: int,
) -> List[Dict[str, Any]]:
    ranked = sorted(combined.items(), key=lambda x: x[1], reverse=True)

    results: List[Dict[str, Any]] = []
    doc_seen_counts: Dict[Tuple[str, str], int] = {}

    for ck, score in ranked:
        meta = all_chunks.get(ck)
        if not meta:
            continue

        doc_key = (str(meta.get("library_id") or ""), str(meta.get("doc_id") or ""))
        used = doc_seen_counts.get(doc_key, 0)
        if used >= per_doc_max_chunks:
            continue

        results.append(_build_result_item(meta, score))
        doc_seen_counts[doc_key] = used + 1

        if len(results) >= top_k:
            break

    return results


def _expand_neighbor_chunks(
    *,
    base_path: str,
    results: List[Dict[str, Any]],
    max_extra_results: int,
    neighbor_window: int,
) -> List[Dict[str, Any]]:
    if not results or max_extra_results <= 0 or neighbor_window <= 0:
        return results

    expanded = list(results)
    seen = {
        (
            str(r.get("library_id") or ""),
            str(r.get("doc_id") or ""),
            int(r.get("chunk_id")),
        )
        for r in results
        if r.get("chunk_id") is not None
    }

    extras_added = 0
    seed_results = list(results)

    for r in seed_results:
        if extras_added >= max_extra_results:
            break

        library_id = str(r.get("library_id") or "").strip()
        doc_id = str(r.get("doc_id") or "").strip()
        chunk_id = _int_or_none(r.get("chunk_id"))
        if not library_id or not doc_id or chunk_id is None:
            continue

        try:
            bundle = _get_doc_bundle_cached(base_path, library_id, doc_id)
            chunk_map = bundle.get("chunk_map") or {}
        except Exception:
            continue

        for delta in range(1, neighbor_window + 1):
            for neighbor_chunk_id in (chunk_id - delta, chunk_id + delta):
                key = (library_id, doc_id, int(neighbor_chunk_id))
                if neighbor_chunk_id < 0 or key in seen:
                    continue
                neighbor = chunk_map.get(int(neighbor_chunk_id))
                if not neighbor:
                    continue

                expanded.append(
                    {
                        "doc_id": doc_id,
                        "library_id": library_id,
                        "chunk_id": neighbor.get("chunk_id"),
                        "text": neighbor.get("text"),
                        "relevance": float(r.get("relevance", 0.0)) * 0.92,
                        "char_start": neighbor.get("char_start"),
                        "char_end": neighbor.get("char_end"),
                        "span_index": neighbor.get("span_index"),
                        "span_start": neighbor.get("span_start"),
                        "span_end": neighbor.get("span_end"),
                    }
                )
                seen.add(key)
                extras_added += 1
                if extras_added >= max_extra_results:
                    break
            if extras_added >= max_extra_results:
                break

    return expanded
