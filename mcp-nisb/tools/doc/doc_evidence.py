#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from core.user_context import auto_user_context, get_user_ctx
from tools.doc.core.path_resolver import PathResolver
from tools.doc.core.search_sqlite import _hybrid_search_internal
from tools.doc.core.span_constants import SPAN_CHARS
from tools.doc.doc_db_sqlite import get_doc_db_sqlite

try:
    from tools.timeline import _append_timeline_activity  # type: ignore
except Exception:
    _append_timeline_activity = None


def _append_timeline_safe(base_path: str, event: Dict[str, Any]) -> None:
    if _append_timeline_activity:
        try:
            _append_timeline_activity(base_path, event)
            return
        except Exception:
            pass

    try:
        timeline_dir = os.path.join(base_path, "timeline")
        os.makedirs(timeline_dir, exist_ok=True)
        fp = os.path.join(timeline_dir, "activities.jsonl")
        with open(fp, "a", encoding="utf-8") as f:
            f.write(json.dumps(event, ensure_ascii=False) + "\n")
    except Exception:
        pass


def _doc_dir(base_path: str, library_id: str, doc_id: str) -> str:
    return os.path.join(base_path, "libraries", library_id, "docs", doc_id)


def _read_text_file(path: str) -> Optional[str]:
    try:
        if not os.path.exists(path):
            return None
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            t = f.read()
        return t if isinstance(t, str) else None
    except Exception:
        return None


def _read_doc_text_file(base_path: str, library_id: str, doc_id: str) -> Optional[str]:
    d = _doc_dir(base_path, library_id, doc_id)
    for name in ("content.txt", "full_text.txt"):
        t = _read_text_file(os.path.join(d, name))
        if t is not None and t.strip():
            return t
    return None


def _build_excerpt(full_text: str, char_start: int, *, radius: int = 450) -> str:
    if not full_text:
        return ""
    n = len(full_text)
    s = max(0, int(char_start) - radius)
    e = min(n, int(char_start) + radius)
    prefix = "…" if s > 0 else ""
    suffix = "…" if e < n else ""
    return f"{prefix}{full_text[s:e]}{suffix}"


@auto_user_context
def nisb_library_doc_evidence(args: Dict[str, Any]) -> Dict[str, Any]:
    user_ctx = get_user_ctx()
    base_path = user_ctx.base

    query = str(args.get("query", "") or "").strip()
    library_id = str(args.get("library_id", "") or "").strip()
    doc_id = str(args.get("doc_id", "") or "").strip()

    if not query:
        return {"status": "error", "message": "query 不能为空"}
    if not library_id:
        return {"status": "error", "message": "library_id 不能为空"}
    if not doc_id:
        return {"status": "error", "message": "doc_id 不能为空"}

    top_k = int(args.get("top_k", 8) or 8)
    top_k = max(1, min(top_k, 50))

    # max_chars 仅用于“请求参数回显/上层兼容”，span 分桶永远用 SPAN_CHARS
    max_chars = int(args.get("max_chars", SPAN_CHARS) or SPAN_CHARS)
    max_chars = max(1000, min(max_chars, 20000))

    include_text = bool(args.get("include_text", True))
    weights = args.get("weights") or {"dense": 0.7, "sparse": 0.3}

    resolver = PathResolver(base_path, str(user_ctx.user_id))
    p = resolver.resolve_doc_path(doc_id, library_id=library_id)
    if p.get("status") != "found":
        return {"status": "error", "message": f"文档未找到：library_id={library_id} doc_id={doc_id}"}

    raw_hits = _hybrid_search_internal(
        base_path=base_path,
        user_ctx=user_ctx,
        query=query,
        doc_id=doc_id,
        library_id=library_id,
        top_k=top_k,
        weights=weights,
    )

    db = get_doc_db_sqlite(base_path, library_id)
    chunks_all = db.get_chunks(doc_id) or []
    chunk_map: Dict[int, Dict[str, Any]] = {}
    for c in chunks_all:
        try:
            cid = int(c.get("chunk_id"))
        except Exception:
            continue
        chunk_map[cid] = c

    full_text = _read_doc_text_file(base_path, library_id, doc_id) or ""

    items: List[Dict[str, Any]] = []
    for h in (raw_hits or []):
        try:
            cid = int(h.get("chunk_id"))
        except Exception:
            continue

        meta = chunk_map.get(cid) or {}
        char_start = meta.get("char_start")
        char_end = meta.get("char_end")

        span_index = None
        if char_start is not None:
            try:
                span_index = int(char_start) // int(SPAN_CHARS)
            except Exception:
                span_index = None

        chunk_text = str((meta.get("text") or h.get("text") or "")).strip()

        if span_index is None:
            continue

        excerpt = ""
        if full_text and char_start is not None:
            try:
                excerpt = _build_excerpt(full_text, int(char_start), radius=450)
            except Exception:
                excerpt = chunk_text[:480]
        else:
            excerpt = chunk_text[:480]

        evidence_id = f"library_doc:{library_id}/{doc_id}#span:{int(span_index)}#chunk:{int(cid)}"

        item: Dict[str, Any] = {
            "source_type": "library_doc",
            "evidence_id": evidence_id,

            "id": uuid.uuid4().hex[:12],
            "library_id": library_id,
            "doc_id": doc_id,
            "doc_title": str(args.get("doc_title") or "").strip() or None,

            "chunk_id": cid,
            "relevance": float(h.get("relevance", 0.0) or 0.0),

            "char_start": char_start,
            "char_end": char_end,

            "span_index": int(span_index),
            "span_chars": int(SPAN_CHARS),

            "max_chars": max_chars,
            "excerpt": excerpt,
            "quote": excerpt,
            "text": excerpt,
        }

        if include_text:
            item["chunk_text"] = chunk_text

        items.append(item)

    _append_timeline_safe(
        base_path,
        {
            "type": "document",
            "origin": "activity_log",
            "event_id": uuid.uuid4().hex,
            "date": datetime.now(timezone.utc).isoformat(),
            "title": (str(args.get("doc_title", "") or "").strip() or doc_id),
            "path": _doc_dir(base_path, library_id, doc_id),
            "library_id": library_id,
            "doc_id": doc_id,
            "extra": {
                "kind": "library_doc_evidence",
                "query": query[:2000],
                "top_k": top_k,
                "max_chars": max_chars,
                "span_chars": int(SPAN_CHARS),
                "count": len(items),
            },
        },
    )

    return {
        "status": "success",
        "query": query,
        "library_id": library_id,
        "doc_id": doc_id,
        "max_chars": max_chars,
        "span_chars": int(SPAN_CHARS),
        "items": items,
        "count": len(items),
    }

