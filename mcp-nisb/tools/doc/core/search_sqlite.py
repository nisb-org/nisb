#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from time import perf_counter
from typing import Any, Dict, List, Optional, Tuple

from core.user_context import auto_user_context, get_user_ctx
from tools.doc.helpers import MAX_RESULTS
from tools.doc.core.path_resolver import PathResolver  # 兼容旧引用
from tools.doc.doc_db_sqlite import get_doc_db_sqlite
from tools.doc.core.dod_guard import require_safe_id
from tools.library_groups.group_store import resolve_group_filter

from tools.doc.core.search.common import (
    _T21_DENSE_MAX_WORKERS,
    _T21S_MAX_PER_DOC_RESULTS,
    _T21S_NEIGHBOR_MAX_RESULTS,
    _T21S_NEIGHBOR_WINDOW,
    _collect_result_metrics,
    _cosine_similarity,
    _debug_perf,
    _embed_query,
    _top_indices_desc,
)
from tools.doc.core.search.bundle_cache import (
    _get_doc_bundle_cached,
    _metadata_fp,
    _read_doc_metadata_cached,
)
from tools.doc.core.search.time_scope import (
    _apply_candidate_cap,
    _compute_published_at_coverage,
    _iter_library_ids,
    _list_candidate_docs,
    _resolve_retrieval_profile,
    _time_window_from_args,
)
from tools.doc.core.search.sparse_fts import _fts_sparse_search
from tools.doc.core.search.dense_merge import (
    _expand_neighbor_chunks,
    _merge_ranked_results,
    _process_doc_candidate_dense,
    _select_dense_candidate_docs,
)


def _candidate_time_stats(candidate_docs: List[Dict[str, Any]]) -> Dict[str, Any]:
    dated: List[str] = []
    missing = 0

    for item in candidate_docs or []:
        p = item.get("published_at")
        if hasattr(p, "isoformat"):
            try:
                dated.append(p.isoformat())
            except Exception:
                missing += 1
        else:
            missing += 1

    dated.sort()

    return {
        "candidate_docs_total": len(candidate_docs or []),
        "candidate_docs_with_published_at": len(dated),
        "candidate_docs_missing_published_at": missing,
        "candidate_oldest_published_at": dated[0] if dated else None,
        "candidate_newest_published_at": dated[-1] if dated else None,
    }


def _hybrid_search_internal(
    *,
    base_path: str,
    user_ctx: Any,
    query: str,
    doc_id: Optional[str] = None,
    library_id: Optional[str] = None,
    top_k: int = 10,
    weights: Optional[Dict[str, Any]] = None,
    time_filter_days: Optional[int] = None,
    time_start: Optional[str] = None,
    time_end: Optional[str] = None,
    allowed_libraries: Optional[set[str]] = None,
    allowed_pairs: Optional[set[tuple[str, str]]] = None,
    return_debug: bool = False,
) -> Any:
    if not str(query or "").strip():
        return []

    total_t0 = perf_counter()

    top_k = min(int(top_k or 10), MAX_RESULTS)
    weights = weights or {"dense": 0.7, "sparse": 0.3}
    dense_w = float(weights.get("dense", 0.7) or 0.0)
    sparse_w = float(weights.get("sparse", 0.3) or 0.0)

    start_dt, end_dt = _time_window_from_args(
        time_filter_days=time_filter_days,
        time_start=time_start,
        time_end=time_end,
    )

    time_window_on = bool(start_dt or end_dt)
    candidate_stats_before_time: Optional[Dict[str, Any]] = None

    if return_debug and time_window_on:
        candidate_docs_before_time = _list_candidate_docs(
            base_path=base_path,
            user_ctx=user_ctx,
            library_id=library_id,
            doc_id=doc_id,
            allowed_libraries=allowed_libraries,
            allowed_pairs=allowed_pairs,
            start_dt=None,
            end_dt=None,
        )
        candidate_stats_before_time = _candidate_time_stats(candidate_docs_before_time)

    t0 = perf_counter()
    candidate_docs_raw = _list_candidate_docs(
        base_path=base_path,
        user_ctx=user_ctx,
        library_id=library_id,
        doc_id=doc_id,
        allowed_libraries=allowed_libraries,
        allowed_pairs=allowed_pairs,
        start_dt=start_dt,
        end_dt=end_dt,
    )
    candidate_stats_raw = _candidate_time_stats(candidate_docs_raw)

    published_at_coverage = _compute_published_at_coverage(candidate_docs_raw)
    profile = _resolve_retrieval_profile(
        candidate_docs_count=len(candidate_docs_raw),
        start_dt=start_dt,
        end_dt=end_dt,
        published_at_coverage=published_at_coverage,
    )
    candidate_docs = _apply_candidate_cap(candidate_docs_raw, profile)
    candidate_stats_after_cap = _candidate_time_stats(candidate_docs)
    candidate_s = round(perf_counter() - t0, 4)

    def _ret(
        hits: List[Dict[str, Any]],
        *,
        stage: str,
        dense_docs_count: int = 0,
        sparse_rows_val: int = 0,
        embed_s_val: float = 0.0,
        sparse_s_val: float = 0.0,
        dense_s_val: float = 0.0,
        merge_s_val: float = 0.0,
    ) -> Any:
        if not return_debug:
            return hits

        before_stats = candidate_stats_before_time or candidate_stats_raw

        debug_payload = {
            "stage": stage,
            "profile_name": str(profile.get("name") or ""),
            "time_window_on": bool(time_window_on),
            "time_filter_applied": bool(time_window_on),
            "candidate_docs_before_time": before_stats.get("candidate_docs_total"),
            "candidate_docs_after_time": candidate_stats_raw.get("candidate_docs_total"),
            "candidate_docs_after_cap": candidate_stats_after_cap.get("candidate_docs_total"),
            "candidate_docs_with_published_at_before_time": before_stats.get("candidate_docs_with_published_at"),
            "candidate_docs_missing_published_at_before_time": before_stats.get("candidate_docs_missing_published_at"),
            "candidate_oldest_published_at_before_time": before_stats.get("candidate_oldest_published_at"),
            "candidate_newest_published_at_before_time": before_stats.get("candidate_newest_published_at"),
            "candidate_docs_with_published_at_after_time": candidate_stats_raw.get("candidate_docs_with_published_at"),
            "candidate_docs_missing_published_at_after_time": candidate_stats_raw.get("candidate_docs_missing_published_at"),
            "candidate_oldest_published_at_after_time": candidate_stats_raw.get("candidate_oldest_published_at"),
            "candidate_newest_published_at_after_time": candidate_stats_raw.get("candidate_newest_published_at"),
            "published_at_coverage": published_at_coverage,
            "dense_docs": int(dense_docs_count),
            "sparse_rows": int(sparse_rows_val),
            "candidate_s": candidate_s,
            "embed_s": embed_s_val,
            "sparse_s": sparse_s_val,
            "dense_s": dense_s_val,
            "merge_s": merge_s_val,
            "total_s": round(perf_counter() - total_t0, 4),
        }

        return {
            "hits": hits,
            "debug": debug_payload,
        }

    if not candidate_docs:
        _debug_perf(
            "hybrid_empty",
            {
                "profile": profile.get("name"),
                "time_window_on": int(bool(profile.get("time_window_on"))),
                "published_at_coverage": published_at_coverage,
                "candidate_docs": 0,
                "candidate_docs_before_cap": candidate_stats_raw["candidate_docs_total"],
                "candidate_docs_after_cap": candidate_stats_after_cap["candidate_docs_total"],
                "candidate_oldest_published_at_before_cap": candidate_stats_raw["candidate_oldest_published_at"],
                "candidate_newest_published_at_before_cap": candidate_stats_raw["candidate_newest_published_at"],
                "candidate_oldest_published_at_after_cap": candidate_stats_after_cap["candidate_oldest_published_at"],
                "candidate_newest_published_at_after_cap": candidate_stats_after_cap["candidate_newest_published_at"],
                "candidate_missing_published_at_before_cap": candidate_stats_raw["candidate_docs_missing_published_at"],
                "candidate_missing_published_at_after_cap": candidate_stats_after_cap["candidate_docs_missing_published_at"],
                "candidate_s": candidate_s,
                "total_s": round(perf_counter() - total_t0, 4),
            },
        )
        return _ret([], stage="empty")

    all_dense: List[Tuple[str, float]] = []
    all_sparse: List[Tuple[str, float]] = []
    all_chunks: Dict[str, Dict[str, Any]] = {}

    sparse_s = 0.0
    sparse_rows = 0
    local_sparse_chunks: Dict[str, Dict[str, Any]] = {}

    if sparse_w > 0:
        t0 = perf_counter()
        local_sparse, local_sparse_chunks = _fts_sparse_search(
            base_path=base_path,
            candidate_docs=candidate_docs,
            query=query,
            top_k=top_k,
            sparse_w=sparse_w,
            profile=profile,
        )
        sparse_s = round(perf_counter() - t0, 4)
        sparse_rows = len(local_sparse)

        all_sparse.extend(local_sparse)
        for k, v in local_sparse_chunks.items():
            if k not in all_chunks:
                all_chunks[k] = v

    dense_candidate_docs = _select_dense_candidate_docs(
        candidate_docs=candidate_docs,
        sparse_chunks=local_sparse_chunks,
        start_dt=start_dt,
        end_dt=end_dt,
        sparse_w=sparse_w,
        profile=profile,
    )

    embed_s = 0.0
    dense_s = 0.0

    if dense_w > 0:
        t0 = perf_counter()
        query_embedding = _embed_query(query)
        embed_s = round(perf_counter() - t0, 4)

        t0 = perf_counter()
        if len(dense_candidate_docs) == 1:
            di = dense_candidate_docs[0]
            local_dense, local_chunks = _process_doc_candidate_dense(
                base_path=base_path,
                library_id=str(di["library_id"]),
                doc_id=str(di["doc_id"]),
                query_embedding=query_embedding,
                top_k=top_k,
                dense_w=dense_w,
            )
            all_dense.extend(local_dense)
            all_chunks.update(local_chunks)
        elif dense_candidate_docs:
            max_workers = min(
                int(profile.get("dense_max_workers", _T21_DENSE_MAX_WORKERS)),
                max(1, len(dense_candidate_docs)),
            )
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = [
                    executor.submit(
                        _process_doc_candidate_dense,
                        base_path=base_path,
                        library_id=str(di["library_id"]),
                        doc_id=str(di["doc_id"]),
                        query_embedding=query_embedding,
                        top_k=top_k,
                        dense_w=dense_w,
                    )
                    for di in dense_candidate_docs
                ]
                for fut in as_completed(futures):
                    try:
                        local_dense, local_chunks = fut.result()
                    except Exception:
                        continue
                    all_dense.extend(local_dense)
                    all_chunks.update(local_chunks)
        dense_s = round(perf_counter() - t0, 4)

    if not all_dense and not all_sparse:
        _debug_perf(
            "hybrid_no_hits",
            {
                "profile": profile.get("name"),
                "time_window_on": int(bool(profile.get("time_window_on"))),
                "published_at_coverage": published_at_coverage,
                "candidate_docs": len(candidate_docs),
                "candidate_docs_before_cap": candidate_stats_raw["candidate_docs_total"],
                "candidate_docs_after_cap": candidate_stats_after_cap["candidate_docs_total"],
                "candidate_oldest_published_at_before_cap": candidate_stats_raw["candidate_oldest_published_at"],
                "candidate_newest_published_at_before_cap": candidate_stats_raw["candidate_newest_published_at"],
                "candidate_oldest_published_at_after_cap": candidate_stats_after_cap["candidate_oldest_published_at"],
                "candidate_newest_published_at_after_cap": candidate_stats_after_cap["candidate_newest_published_at"],
                "candidate_missing_published_at_before_cap": candidate_stats_raw["candidate_docs_missing_published_at"],
                "candidate_missing_published_at_after_cap": candidate_stats_after_cap["candidate_docs_missing_published_at"],
                "dense_docs": len(dense_candidate_docs),
                "sparse_rows": sparse_rows,
                "candidate_s": candidate_s,
                "embed_s": embed_s,
                "sparse_s": sparse_s,
                "dense_s": dense_s,
                "total_s": round(perf_counter() - total_t0, 4),
            },
        )
        return _ret(
            [],
            stage="no_hits",
            dense_docs_count=len(dense_candidate_docs),
            sparse_rows_val=sparse_rows,
            embed_s_val=embed_s,
            sparse_s_val=sparse_s,
            dense_s_val=dense_s,
        )

    t0 = perf_counter()
    combined: Dict[str, float] = {}
    for ck, s in all_dense:
        combined[ck] = combined.get(ck, 0.0) + s
    for ck, s in all_sparse:
        combined[ck] = combined.get(ck, 0.0) + s

    results = _merge_ranked_results(
        combined=combined,
        all_chunks=all_chunks,
        top_k=top_k,
        per_doc_max_chunks=int(profile.get("per_doc_max_chunks", _T21S_MAX_PER_DOC_RESULTS)),
    )

    if profile.get("neighbor_expansion"):
        results = _expand_neighbor_chunks(
            base_path=base_path,
            results=results,
            max_extra_results=_T21S_NEIGHBOR_MAX_RESULTS,
            neighbor_window=_T21S_NEIGHBOR_WINDOW,
        )
        results = results[:top_k]

    merge_s = round(perf_counter() - t0, 4)

    result_metrics = _collect_result_metrics(results)

    _debug_perf(
        "hybrid_done",
        {
            "profile": profile.get("name"),
            "time_window_on": int(bool(profile.get("time_window_on"))),
            "published_at_coverage": published_at_coverage,
            "candidate_docs": len(candidate_docs),
            "candidate_docs_before_cap": candidate_stats_raw["candidate_docs_total"],
            "candidate_docs_after_cap": candidate_stats_after_cap["candidate_docs_total"],
            "candidate_oldest_published_at_before_cap": candidate_stats_raw["candidate_oldest_published_at"],
            "candidate_newest_published_at_before_cap": candidate_stats_raw["candidate_newest_published_at"],
            "candidate_oldest_published_at_after_cap": candidate_stats_after_cap["candidate_oldest_published_at"],
            "candidate_newest_published_at_after_cap": candidate_stats_after_cap["candidate_newest_published_at"],
            "candidate_missing_published_at_before_cap": candidate_stats_raw["candidate_docs_missing_published_at"],
            "candidate_missing_published_at_after_cap": candidate_stats_after_cap["candidate_docs_missing_published_at"],
            "dense_docs": len(dense_candidate_docs),
            "sparse_rows": sparse_rows,
            "unique_docs": result_metrics["unique_docs"],
            "unique_chunks": result_metrics["unique_chunks"],
            "candidate_s": candidate_s,
            "embed_s": embed_s,
            "sparse_s": sparse_s,
            "dense_s": dense_s,
            "merge_s": merge_s,
            "total_s": round(perf_counter() - total_t0, 4),
        },
    )
    return _ret(
        results,
        stage="done",
        dense_docs_count=len(dense_candidate_docs),
        sparse_rows_val=sparse_rows,
        embed_s_val=embed_s,
        sparse_s_val=sparse_s,
        dense_s_val=dense_s,
        merge_s_val=merge_s,
    )


@auto_user_context
def nisb_doc_search(args: Dict[str, Any]) -> Dict[str, Any]:
    user_ctx = get_user_ctx()
    base_path = user_ctx.base

    query = str(args.get("query", "") or "").strip()
    doc_id = str(args.get("doc_id", "") or "").strip() or None
    library_id = str(args.get("library_id", "") or "").strip() or None
    top_k = min(int(args.get("top_k", 10) or 10), MAX_RESULTS)

    if not query:
        return {"status": "error", "message": "query 不能为空"}

    try:
        results = _hybrid_search_internal(
            base_path=base_path,
            user_ctx=user_ctx,
            query=query,
            doc_id=doc_id,
            library_id=library_id,
            top_k=top_k,
            weights={"dense": 1.0, "sparse": 0.0},
        )
        if not results:
            return {"status": "success", "message": "", "raw": {"results": []}}

        lines = [f"{len(results)} results"]
        for i, r in enumerate(results, 1):
            liblabel = f"[{r.get('library_id')}]" if r.get("library_id") else "[legacy]"
            span_label = r.get("span_index")
            span_txt = f" span={span_label}" if span_label is not None else ""
            lines.append(
                f"{i}. {r.get('relevance', 0.0) * 100:.1f} {liblabel}{span_txt} - {str(r.get('text') or '')[:300]}..."
            )
        return {"status": "success", "message": "\n".join(lines), "raw": {"results": results}}
    except Exception as e:
        return {"status": "error", "message": f"{e}"}


@auto_user_context
def nisb_doc_search_hybrid(args: Dict[str, Any]) -> Dict[str, Any]:
    user_ctx = get_user_ctx()
    base_path = user_ctx.base

    query = str(args.get("query", "") or "").strip()
    doc_id = str(args.get("doc_id", "") or "").strip() or None
    library_id = str(args.get("library_id", "") or "").strip() or None
    top_k = min(int(args.get("top_k", 10) or 10), MAX_RESULTS)
    weights = args.get("weights") or {"dense": 0.7, "sparse": 0.3}

    time_filter_days = args.get("time_filter_days", None)
    time_start = args.get("time_start", None)
    time_end = args.get("time_end", None)

    group_id = str(args.get("group_id", "") or "").strip() or None

    if not query:
        return {"status": "error", "message": "query 不能为空"}

    allowed_libraries = None
    allowed_pairs = None

    if group_id and not (doc_id and library_id):
        try:
            group_id = require_safe_id("group_id", group_id)
            allowed_libraries, allowed_pairs = resolve_group_filter(base_path, group_id)
        except Exception as e:
            return {"status": "error", "message": str(e)}

    try:
        results = _hybrid_search_internal(
            base_path=base_path,
            user_ctx=user_ctx,
            query=query,
            doc_id=doc_id,
            library_id=library_id,
            top_k=top_k,
            weights=weights,
            time_filter_days=(int(time_filter_days) if time_filter_days is not None else None),
            time_start=(str(time_start).strip() if time_start is not None else None),
            time_end=(str(time_end).strip() if time_end is not None else None),
            allowed_libraries=allowed_libraries,
            allowed_pairs=allowed_pairs,
        )
        if not results:
            return {"status": "success", "message": "", "raw": {"results": []}}

        lines = [f"{len(results)} results"]
        for i, r in enumerate(results, 1):
            liblabel = f"[{r.get('library_id')}]" if r.get("library_id") else "[legacy]"
            span_label = r.get("span_index")
            span_txt = f" span={span_label}" if span_label is not None else ""
            lines.append(
                f"{i}. {r.get('relevance', 0.0) * 100:.1f} {liblabel}{span_txt} - {str(r.get('text') or '')[:300]}..."
            )
        return {"status": "success", "message": "\n".join(lines), "raw": {"results": results}}
    except Exception as e:
        return {"status": "error", "message": f"{e}"}


@auto_user_context
def nisb_doc_search_with_filter(args: Dict[str, Any]) -> Dict[str, Any]:
    user_ctx = get_user_ctx()
    base_path = user_ctx.base

    query = str(args.get("query", "") or "").strip()
    where = args.get("where")
    library_id = str(args.get("library_id", "") or "").strip() or None
    top_k = min(int(args.get("top_k", 10) or 10), MAX_RESULTS)

    if not query:
        return {"status": "error", "message": "query 不能为空"}

    try:
        query_embedding = _embed_query(query)

        where_tags = None
        if isinstance(where, dict):
            if "tags" in where and isinstance(where.get("tags"), dict):
                where_tags = where["tags"].get("all", None)
            if "all" in where and "tags" not in where:
                where["tags"] = where.pop("all")
            if "tags" in where and not isinstance(where.get("tags"), (list, set)):
                where_tags = list(where.get("tags") or [])

        all_results: List[Dict[str, Any]] = []
        lib_ids = [library_id] if library_id else _iter_library_ids(base_path, None, None, None)

        for lib_id in lib_ids:
            db = get_doc_db_sqlite(base_path, lib_id)
            docs = db.list_documents(library_id=lib_id)

            for docinfo in docs:
                did = str(docinfo.get("doc_id") or "").strip()
                if not did:
                    continue

                metadata = _read_doc_metadata_cached(_metadata_fp(base_path, lib_id, did))
                if not metadata:
                    continue

                skip = False
                if isinstance(where, dict):
                    for key, value in where.items():
                        try:
                            if key == "filename":
                                if value:
                                    vv = value if isinstance(value, list) else [value]
                                    fn = str(metadata.get("filename") or "").lower()
                                    if not any(str(v).lower() in fn for v in vv):
                                        skip = True
                                        break
                            elif key == "tags":
                                if where_tags:
                                    doctags = set(metadata.get("tags") or [])
                                    filtertags = set(where_tags)
                                    if not doctags.issuperset(filtertags):
                                        skip = True
                                        break
                            elif key == "filetype":
                                if value and str(value).lower() != str(metadata.get("filetype") or "").lower():
                                    skip = True
                                    break
                        except Exception:
                            continue
                if skip:
                    continue

                bundle = _get_doc_bundle_cached(base_path, lib_id, did)
                embeddings_matrix = bundle.get("embeddings_matrix")
                chunks = bundle.get("chunks") or []
                if embeddings_matrix is None or len(embeddings_matrix) == 0 or not chunks:
                    continue

                sims = _cosine_similarity(query_embedding, embeddings_matrix)
                top_indices = _top_indices_desc(sims, min(top_k, len(sims)))
                for idx in top_indices:
                    if idx >= len(chunks):
                        continue
                    chunk = chunks[int(idx)]
                    all_results.append(
                        {
                            "doc_id": did,
                            "library_id": lib_id,
                            "filename": metadata.get("filename"),
                            "filetype": metadata.get("filetype"),
                            "chunk_id": chunk.get("chunk_id"),
                            "text": str(chunk.get("text") or "")[:300],
                            "relevance": float(sims[int(idx)]),
                        }
                    )

        all_results.sort(key=lambda x: x.get("relevance", 0.0), reverse=True)
        results = all_results[:top_k]
        if not results:
            return {"status": "success", "message": "", "raw": {"results": []}}

        lines = [f"{len(results)} results"]
        for i, r in enumerate(results, 1):
            liblabel = f"[{r.get('library_id')}]" if r.get("library_id") else "[legacy]"
            lines.append(
                f"{i}. {r.get('relevance', 0.0) * 100:.1f} {liblabel} - {r.get('filename')} {r.get('filetype')}"
            )
        return {"status": "success", "message": "\n".join(lines), "raw": {"results": results}}
    except Exception as e:
        return {"status": "error", "message": f"{e}"}
