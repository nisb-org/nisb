from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from openai import OpenAI

from tools.doc.helpers import EMBEDDING_MODEL, EMBEDDING_DIM

_T21_CANDIDATE_DOC_CAP = 96
_T21_DENSE_DOC_CAP = 24
_T21_SPARSE_PER_LIBRARY_LIMIT_MIN = 12
_T21_SPARSE_PER_LIBRARY_LIMIT_FACTOR = 4
_T21_SPARSE_GLOBAL_CAP_FACTOR = 6
_T21_DENSE_MAX_WORKERS = 4

_T21S_EXPERIMENTAL_RECALL = str(os.environ.get("NISB_DOC_EXPERIMENTAL_RECALL", "")).strip().lower() in {"1", "true", "yes", "on"}
_T21S_ENABLE_NEIGHBOR_EXPANSION = str(os.environ.get("NISB_DOC_NEIGHBOR_EXPANSION", "")).strip().lower() in {"1", "true", "yes", "on"}
_T21S_NEIGHBOR_MAX_RESULTS = 2
_T21S_NEIGHBOR_WINDOW = 1
_T21S_SMALL_CANDIDATE_THRESHOLD = 8
_T21S_EXPERIMENTAL_DENSE_CAP = 32
_T21S_EXPERIMENTAL_SPARSE_FACTOR = 5
_T21S_EXPERIMENTAL_SPARSE_GLOBAL_FACTOR = 7
_T21S_MAX_PER_DOC_RESULTS = 2

_T21_DEBUG = str(os.environ.get("NISB_DOC_SEARCH_DEBUG", "")).strip().lower() in {"1", "true", "yes", "on"}


def _debug_perf(label: str, metrics: Dict[str, Any]) -> None:
    if not _T21_DEBUG:
        return
    try:
        ordered = []
        for k in (
            "profile",
            "time_window_on",
            "published_at_coverage",
            "candidate_docs",
            "dense_docs",
            "sparse_rows",
            "unique_docs",
            "unique_chunks",
            "candidate_s",
            "embed_s",
            "sparse_s",
            "dense_s",
            "merge_s",
            "total_s",
        ):
            if k in metrics:
                ordered.append(f"{k}={metrics[k]}")
        if ordered:
            print(f"[HYBRID_PERF] {label} " + " ".join(ordered))
    except Exception:
        return


def _cosine_similarity(query_embedding: np.ndarray, doc_embeddings: np.ndarray) -> np.ndarray:
    query = query_embedding.flatten()
    query_norm = np.linalg.norm(query)
    if query_norm == 0:
        return np.zeros(len(doc_embeddings), dtype=np.float32)

    doc_norms = np.linalg.norm(doc_embeddings, axis=1, keepdims=True)
    doc_norms[doc_norms == 0] = 1.0
    sims = np.dot(doc_embeddings, query) / (query_norm * doc_norms.flatten())
    return sims.astype(np.float32)


def _embed_query(text: str) -> np.ndarray:
    client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
    resp = client.embeddings.create(model=EMBEDDING_MODEL, input=text, dimensions=EMBEDDING_DIM)
    return np.array(resp.data[0].embedding, dtype=np.float32)


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


def _result_key(library_id: str, doc_id: str, chunk_id: Any) -> str:
    return f"{library_id}::{doc_id}::chunk::{chunk_id}"


def _top_indices_desc(scores: np.ndarray, limit: int) -> np.ndarray:
    if limit <= 0 or scores.size == 0:
        return np.array([], dtype=int)

    limit = min(limit, scores.size)
    if limit >= scores.size:
        return np.argsort(scores)[::-1]

    idx = np.argpartition(scores, -limit)[-limit:]
    return idx[np.argsort(scores[idx])[::-1]]


def _build_result_item(meta: Dict[str, Any], score: float) -> Dict[str, Any]:
    return {
        "doc_id": meta.get("doc_id"),
        "library_id": meta.get("library_id"),
        "chunk_id": meta.get("chunk_id"),
        "text": meta.get("text"),
        "relevance": float(score),
        "char_start": meta.get("char_start"),
        "char_end": meta.get("char_end"),
        "span_index": meta.get("span_index"),
        "span_start": meta.get("span_start"),
        "span_end": meta.get("span_end"),
    }


def _collect_result_metrics(results: List[Dict[str, Any]]) -> Dict[str, int]:
    unique_docs = len(
        {
            (str(r.get("library_id") or ""), str(r.get("doc_id") or ""))
            for r in results
            if str(r.get("doc_id") or "").strip()
        }
    )
    unique_chunks = len(
        {
            (
                str(r.get("library_id") or ""),
                str(r.get("doc_id") or ""),
                int(r.get("chunk_id")),
            )
            for r in results
            if r.get("chunk_id") is not None and str(r.get("doc_id") or "").strip()
        }
    )
    return {
        "unique_docs": int(unique_docs),
        "unique_chunks": int(unique_chunks),
    }
