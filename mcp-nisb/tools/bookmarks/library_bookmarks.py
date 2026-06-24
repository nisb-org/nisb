#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

from core.storage import load_jsonl, append_jsonl
from tools.doc.core.dod_guard import resolve_user_base_from_args, require_safe_id

BOOKMARKS_DIRNAME = "bookmarks"
BOOKMARKS_FILENAME = "library_doc_bookmarks.jsonl"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _bookmarks_file(user_base) -> str:
    d = os.path.join(str(user_base), BOOKMARKS_DIRNAME)
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, BOOKMARKS_FILENAME)


def _safe_int(x, default: int = 0) -> int:
    try:
        return int(x)
    except Exception:
        return default


def _safe_reader(v: Any) -> Optional[Dict[str, Any]]:
    if isinstance(v, dict):
        # 只保留浅层 dict，避免写入不可序列化对象
        return dict(v)
    return None


def nisb_bookmark_add(args: Dict[str, Any]) -> Dict[str, Any]:
    user_base = resolve_user_base_from_args(args)

    library_id = require_safe_id("library_id", str(args.get("library_id", "")).strip())
    doc_id = require_safe_id("doc_id", str(args.get("doc_id", "")).strip())

    span_index = _safe_int(args.get("span_index", args.get("spanIndex", -1)), -1)
    if span_index < 0:
        return {"status": "error", "message": "❌ span_index 必须为非负整数"}

    title = str(args.get("title") or "").strip()
    note = str(args.get("note") or "").strip()
    reader = _safe_reader(args.get("reader"))

    item: Dict[str, Any] = {
        "type": "library_doc_bookmark",
        "bookmark_id": uuid.uuid4().hex,
        "created_at": _now_iso(),
        "updated_at": _now_iso(),
        "library_id": library_id,
        "doc_id": doc_id,
        "span_index": span_index,
        "title": title,
        "note": note,
        "tombstone": False,
    }
    if reader is not None:
        item["reader"] = reader

    path = _bookmarks_file(user_base)
    append_jsonl(path, item)

    return {"status": "success", "message": "✅ 已添加书签", "bookmark": item}


def nisb_bookmark_list(args: Dict[str, Any]) -> Dict[str, Any]:
    user_base = resolve_user_base_from_args(args)

    library_id = str(args.get("library_id") or "").strip()
    doc_id = str(args.get("doc_id") or "").strip()

    # 可选过滤：不传则列出全部
    if library_id:
        library_id = require_safe_id("library_id", library_id)
    if doc_id:
        doc_id = require_safe_id("doc_id", doc_id)

    path = _bookmarks_file(user_base)
    rows = load_jsonl(path) if os.path.exists(path) else []
    if not isinstance(rows, list):
        rows = []

    # ✅ 折叠 append-only 日志：按 bookmark_id 取最后状态（tombstone 覆盖原记录）
    state: Dict[str, Dict[str, Any]] = {}
    deleted_ids: set[str] = set()

    for it in rows:
        if not isinstance(it, dict):
            continue

        t = str(it.get("type") or "")
        bid = str(it.get("bookmark_id") or "").strip()
        if not bid:
            continue

        if t == "library_doc_bookmark_tombstone" or bool(it.get("tombstone")) is True:
            deleted_ids.add(bid)
            if bid in state:
                state.pop(bid, None)
            continue

        if t != "library_doc_bookmark":
            continue

        if bid in deleted_ids:
            continue

        # 新版本覆盖旧版本（为未来 update 留口）
        state[bid] = it

    out: List[Dict[str, Any]] = []
    for it in state.values():
        if library_id and it.get("library_id") != library_id:
            continue
        if doc_id and it.get("doc_id") != doc_id:
            continue
        out.append(it)

    # 最新在前
    out.sort(key=lambda x: str(x.get("updated_at") or x.get("created_at") or ""), reverse=True)

    return {"status": "success", "bookmarks": out, "total": len(out)}


def nisb_bookmark_delete(args: Dict[str, Any]) -> Dict[str, Any]:
    user_base = resolve_user_base_from_args(args)

    bookmark_id = str(args.get("bookmark_id") or "").strip()
    if not bookmark_id:
        return {"status": "error", "message": "❌ bookmark_id 不能为空"}

    tomb = {
        "type": "library_doc_bookmark_tombstone",
        "bookmark_id": bookmark_id,
        "tombstone": True,
        "created_at": _now_iso(),
        "updated_at": _now_iso(),
    }
    path = _bookmarks_file(user_base)
    append_jsonl(path, tomb)

    return {"status": "success", "message": "✅ 已移除书签", "bookmark_id": bookmark_id}


__all__ = ["nisb_bookmark_add", "nisb_bookmark_list", "nisb_bookmark_delete"]

