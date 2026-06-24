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
ANNOTATIONS_FILENAME = "library_doc_annotations.jsonl"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _annotations_file(user_base) -> str:
    d = os.path.join(str(user_base), ANNOTATIONS_DIRNAME)
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, ANNOTATIONS_FILENAME)


def _safe_int(x, default: int = 0) -> int:
    try:
        return int(x)
    except Exception:
        return default


def nisb_library_annotation_add(args: Dict[str, Any]) -> Dict[str, Any]:
    user_base = resolve_user_base_from_args(args)

    library_id = require_safe_id("library_id", str(args.get("library_id", "")).strip())
    doc_id = require_safe_id("doc_id", str(args.get("doc_id", "")).strip())

    chunk_id = _safe_int(args.get("chunk_id", args.get("chunkId", -1)), -1)
    if chunk_id < 0:
        return {"status": "error", "message": "❌ chunk_id 必须为非负整数"}

    content = str(args.get("content") or "").strip()
    if not content:
        return {"status": "error", "message": "❌ 批注内容不能为空"}

    item: Dict[str, Any] = {
        "type": "library_doc_annotation",
        "annotation_id": uuid.uuid4().hex,
        "created_at": _now_iso(),
        "updated_at": _now_iso(),
        "library_id": library_id,
        "doc_id": doc_id,
        "chunk_id": chunk_id,
        "content": content,
        "tombstone": False,
    }

    path = _annotations_file(user_base)
    append_jsonl(path, item)

    return {"status": "success", "message": "✅ 已添加批注", "annotation": item}


def nisb_library_annotation_list(args: Dict[str, Any]) -> Dict[str, Any]:
    user_base = resolve_user_base_from_args(args)

    library_id = str(args.get("library_id") or "").strip()
    doc_id = str(args.get("doc_id") or "").strip()

    if library_id:
        library_id = require_safe_id("library_id", library_id)
    if doc_id:
        doc_id = require_safe_id("doc_id", doc_id)

    path = _annotations_file(user_base)
    rows = load_jsonl(path) if os.path.exists(path) else []
    if not isinstance(rows, list):
        rows = []

    # append-only 折叠：按 annotation_id 取最后状态，tombstone 覆盖
    state: Dict[str, Dict[str, Any]] = {}
    deleted_ids: set[str] = set()

    for it in rows:
        if not isinstance(it, dict):
            continue

        t = str(it.get("type") or "")
        aid = str(it.get("annotation_id") or "").strip()
        if not aid:
            continue

        if t == "library_doc_annotation_tombstone" or bool(it.get("tombstone")) is True:
            deleted_ids.add(aid)
            state.pop(aid, None)
            continue

        if t != "library_doc_annotation":
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
        out.append(it)

    out.sort(key=lambda x: str(x.get("updated_at") or x.get("created_at") or ""), reverse=True)
    return {"status": "success", "annotations": out, "total": len(out)}


def nisb_library_annotation_delete(args: Dict[str, Any]) -> Dict[str, Any]:
    user_base = resolve_user_base_from_args(args)

    annotation_id = str(args.get("annotation_id") or "").strip()
    if not annotation_id:
        return {"status": "error", "message": "❌ annotation_id 不能为空"}

    tomb = {
        "type": "library_doc_annotation_tombstone",
        "annotation_id": annotation_id,
        "tombstone": True,
        "created_at": _now_iso(),
        "updated_at": _now_iso(),
    }
    path = _annotations_file(user_base)
    append_jsonl(path, tomb)

    return {"status": "success", "message": "✅ 已移除批注", "annotation_id": annotation_id}


__all__ = [
    "nisb_library_annotation_add",
    "nisb_library_annotation_list",
    "nisb_library_annotation_delete",
]

