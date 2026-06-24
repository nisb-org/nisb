from __future__ import annotations

from typing import Any, Dict, List

from tools.doc.analysis import doc_qa as dq  # type: ignore
from .common import clean_id
from .storage import (
    QA_LIST_MAX_SEGMENTS,
    analysis_dir,
    load_deleted_set_fast,
    list_segment_files_for_read,
    manifest_path,
    maybe_bootstrap_manifest,
    qa_path_for_doc,
    read_jsonl_lines,
    resolve_store_dir,
    store_scope_from_args,
)


def nisb_qa_scope_list(args: Dict[str, Any]) -> Dict[str, Any]:
    store_scope = store_scope_from_args(args)

    library_id = clean_id(args.get("library_id") or args.get("libraryid")) or None
    doc_id = clean_id(args.get("doc_id") or args.get("docid")) or None
    limit = int(args.get("limit") or 40)

    if store_scope == "doc" and not (library_id and doc_id):
        return dq._build_standard_result(
            args=args,
            status="error",
            message="store_scope=doc 时必须提供 library_id/doc_id",
            mode_used="qa_scope_list",
            response={"items": [], "count": 0, "limit": limit},
            rag_mode=store_scope,
        )

    if store_scope == "library" and not library_id:
        return dq._build_standard_result(
            args=args,
            status="error",
            message="store_scope=library 时必须提供 library_id",
            mode_used="qa_scope_list",
            response={"items": [], "count": 0, "limit": limit},
            rag_mode=store_scope,
        )

    store_dir, dbg = resolve_store_dir(
        args,
        store_scope=store_scope,
        library_id=library_id,
        doc_id=doc_id,
    )

    if store_scope == "doc":
        qa_path = qa_path_for_doc(store_dir)
        rows_all = dq._safe_read_jsonl(qa_path, max_rows=20000)
        qa_map = dq._build_qa_index(rows_all)
        deleted_set = dq._compute_deleted_set(rows_all, qa_map)

        items: List[dict] = []
        for qa_id_x, qa in qa_map.items():
            if qa_id_x in deleted_set:
                continue
            items.append(qa)

        items.sort(key=lambda x: str(x.get("created_at") or ""))
        if limit > 0 and len(items) > limit:
            items = items[-limit:]

        formal_items = [dq._qa_record_to_standard_item(x) for x in items]

        return dq._build_standard_result(
            args=args,
            status="success",
            message="success",
            mode_used="qa_scope_list",
            response={"items": formal_items, "count": len(formal_items), "limit": limit},
            rag_mode=store_scope,
            evidence_query=None,
            evidence_tools=[],
            evidence_result={
                "qa_path": str(qa_path),
                "records": items,
                "debug": {
                    **dbg,
                    "storage": "single_jsonl_doc",
                    "total_rows": len(rows_all),
                    "qa_count": len(qa_map),
                    "deleted_count": len(deleted_set),
                },
            },
            tool_calls=[],
            tool_results=[],
        )

    manifest = maybe_bootstrap_manifest(store_dir)

    req_max_segments = dq._get_int(args, "max_segments", "maxSegments", default=QA_LIST_MAX_SEGMENTS)
    req_max_segments = max(1, min(req_max_segments, 200))
    seg_paths = list_segment_files_for_read(store_dir, max_segments=req_max_segments)

    rows_loaded: List[dict] = []
    for p in seg_paths:
        rows_loaded.extend(read_jsonl_lines(p, max_rows=50000))

    deleted_fast = load_deleted_set_fast(store_dir)

    qa_map = dq._build_qa_index(rows_loaded)
    deleted_set = dq._compute_deleted_set(rows_loaded, qa_map)
    deleted_set = set(deleted_set) | set(deleted_fast)

    items: List[dict] = []
    for qa_id_x, qa in qa_map.items():
        if qa_id_x in deleted_set:
            continue
        items.append(qa)

    items.sort(key=lambda x: str(x.get("created_at") or ""))
    if limit > 0 and len(items) > limit:
        items = items[-limit:]

    seg_total = len(list(manifest.get("segments") or []))
    seg_scanned = len(seg_paths)
    has_more_segments = seg_total > seg_scanned
    formal_items = [dq._qa_record_to_standard_item(x) for x in items]

    return dq._build_standard_result(
        args=args,
        status="success",
        message="success",
        mode_used="qa_scope_list",
        response={"items": formal_items, "count": len(formal_items), "limit": limit},
        rag_mode=store_scope,
        evidence_query=None,
        evidence_tools=[],
        evidence_result={
            "qa_path": str(analysis_dir(store_dir) / str(manifest.get("active") or "")),
            "records": items,
            "has_more_segments": has_more_segments,
            "segments_total": seg_total,
            "segments_scanned": seg_scanned,
            "debug": {
                **dbg,
                "storage": "segmented_jsonl",
                "manifest": str(manifest_path(store_dir)),
                "segments_scanned_files": [str(x.name) for x in seg_paths],
                "rows_loaded": len(rows_loaded),
                "qa_count": len(qa_map),
                "deleted_count": len(deleted_set),
            },
        },
        tool_calls=[],
        tool_results=[],
    )

