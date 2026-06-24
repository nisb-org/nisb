#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

from core.storage import load_jsonl, append_jsonl
from tools.doc.core.dod_guard import resolve_user_base_from_args, require_safe_id

ANNOTATIONS_DIRNAME = "annotations"
SPAN_ANNOTATIONS_FILENAME = "library_doc_span_annotations.jsonl"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _span_annotations_file(user_base) -> str:
    d = os.path.join(str(user_base), ANNOTATIONS_DIRNAME)
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, SPAN_ANNOTATIONS_FILENAME)


def _safe_int(x, default: int = 0) -> int:
    try:
        return int(x)
    except Exception:
        return default


def _safe_reader(v: Any) -> Optional[Dict[str, Any]]:
    if isinstance(v, dict):
        return dict(v)
    return None


def nisb_span_annotation_add(args: Dict[str, Any]) -> Dict[str, Any]:
    user_base = resolve_user_base_from_args(args)

    library_id = require_safe_id("library_id", str(args.get("library_id", "")).strip())
    doc_id = require_safe_id("doc_id", str(args.get("doc_id", "")).strip())

    span_index = _safe_int(args.get("span_index", args.get("spanIndex", -1)), -1)
    if span_index < 0:
        return {"status": "error", "message": "❌ span_index 必须为非负整数"}

    content = str(args.get("content") or args.get("annotation") or "").strip()
    if not content:
        return {"status": "error", "message": "❌ 批注内容不能为空"}

    reader = _safe_reader(args.get("reader"))

    item: Dict[str, Any] = {
        "type": "library_doc_span_annotation",
        "annotation_id": uuid.uuid4().hex,
        "created_at": _now_iso(),
        "updated_at": _now_iso(),
        "library_id": library_id,
        "doc_id": doc_id,
        "span_index": span_index,
        "content": content,
        "tombstone": False,
    }
    if reader is not None:
        item["reader"] = reader

    path = _span_annotations_file(user_base)
    append_jsonl(path, item)

    return {"status": "success", "message": "✅ 已添加批注", "annotation": item}


def nisb_span_annotation_list(args: Dict[str, Any]) -> Dict[str, Any]:
    user_base = resolve_user_base_from_args(args)

    library_id = str(args.get("library_id") or "").strip()
    doc_id = str(args.get("doc_id") or "").strip()
    span_index = args.get("span_index", args.get("spanIndex", None))

    if library_id:
        library_id = require_safe_id("library_id", library_id)
    if doc_id:
        doc_id = require_safe_id("doc_id", doc_id)

    span_index_i: Optional[int] = None
    if span_index is not None and str(span_index) != "":
        span_index_i = _safe_int(span_index, -1)
        if span_index_i < 0:
            return {"status": "error", "message": "❌ span_index 必须为非负整数"}

    path = _span_annotations_file(user_base)
    rows = load_jsonl(path) if os.path.exists(path) else []
    if not isinstance(rows, list):
        rows = []

    state: Dict[str, Dict[str, Any]] = {}
    deleted_ids: set[str] = set()

    for it in rows:
        if not isinstance(it, dict):
            continue
        t = str(it.get("type") or "")
        aid = str(it.get("annotation_id") or "").strip()
        if not aid:
            continue

        if t == "library_doc_span_annotation_tombstone" or bool(it.get("tombstone")) is True:
            deleted_ids.add(aid)
            state.pop(aid, None)
            continue

        if t != "library_doc_span_annotation":
            continue
        if aid in deleted_ids:
            continue

        state[aid] = it

    out: List[Dict[str, Any]] = []
    for it in state.values():
        if library_id and it.get("library_id") != library_id:
            continue
        if doc_id and it.get("doc_id") != doc_id:
            continue
        if span_index_i is not None and int(it.get("span_index", -1)) != span_index_i:
            continue
        out.append(it)

    out.sort(key=lambda x: str(x.get("updated_at") or x.get("created_at") or ""), reverse=True)
    return {"status": "success", "annotations": out, "total": len(out)}


def nisb_span_annotation_delete(args: Dict[str, Any]) -> Dict[str, Any]:
    user_base = resolve_user_base_from_args(args)

    annotation_id = str(args.get("annotation_id") or "").strip()
    if not annotation_id:
        return {"status": "error", "message": "❌ annotation_id 不能为空"}

    tomb = {
        "type": "library_doc_span_annotation_tombstone",
        "annotation_id": annotation_id,
        "tombstone": True,
        "created_at": _now_iso(),
        "updated_at": _now_iso(),
    }
    path = _span_annotations_file(user_base)
    append_jsonl(path, tomb)

    return {"status": "success", "message": "✅ 已移除批注", "annotation_id": annotation_id}


__all__ = ["nisb_span_annotation_add", "nisb_span_annotation_list", "nisb_span_annotation_delete"]

