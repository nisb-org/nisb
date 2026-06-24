#!/usr/bin/env python3
"""
Document context tools.

This module provides context expansion, recall, bookmark compatibility,
annotation compatibility, and reserved network tool responses.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from core.user_context import auto_user_context, get_user_ctx
from tools.doc.doc_db_sqlite import get_doc_db_sqlite
from tools.doc.i18n import doc_message, get_ui_locale


def _to_int(value: Any, default: int | None = None) -> int | None:
    try:
        if value is None:
            return default
        return int(value)
    except Exception:
        return default


def _positive_int(value: Any, default: int) -> int:
    parsed = _to_int(value, default)
    if parsed is None:
        return default
    return max(0, parsed)


def _context_header(args: dict, chunk_id: int, start: int, end: int) -> str:
    title = doc_message(args, "context_expand_title")
    center = doc_message(args, "context_center_label")
    range_label = doc_message(args, "context_range_label")
    return f"{title}\n\n{center}: {chunk_id}\n{range_label}: [{start}, {end})"


@auto_user_context
def nisb_doc_expand_enhanced(args: dict) -> dict:
    """Expand context around a document chunk."""
    args = args or {}
    user_ctx = get_user_ctx()
    base_path = user_ctx.base
    doc_id = str(args.get("doc_id", "")).strip()
    library_id = str(args.get("library_id", "")).strip()
    chunk_id = _to_int(args.get("chunk_id"))
    window = _positive_int(args.get("window", 8), 8)

    if not doc_id or chunk_id is None:
        return {"status": "error", "message": doc_message(args, "doc_and_chunk_required")}

    if not library_id:
        return {"status": "error", "message": doc_message(args, "library_id_required")}

    try:
        db = get_doc_db_sqlite(base_path, library_id)
        chunks = db.get_chunks(doc_id)

        if not chunks:
            return {"status": "error", "message": doc_message(args, "doc_chunks_not_found")}

        if chunk_id >= len(chunks) or chunk_id < 0:
            return {"status": "error", "message": doc_message(args, "chunk_not_found")}

        start = max(0, chunk_id - window)
        end = min(len(chunks), chunk_id + window + 1)
        content = "\n\n---\n\n".join([str(c.get("text", "")) for c in chunks[start:end]])
        header = _context_header(args, chunk_id, start, end)

        return {
            "status": "success",
            "text": f"{header}\n\n{content[:500]}...",
            "raw": {"doc_id": doc_id, "content": content},
        }

    except Exception as exc:
        return {
            "status": "error",
            "message": doc_message(args, "context_expand_failed", error=str(exc)),
        }


@auto_user_context
def nisb_doc_bookmark(args: dict) -> dict:
    """Create a compatibility bookmark response."""
    args = args or {}
    doc_id = str(args.get("doc_id", "")).strip()
    library_id = str(args.get("library_id", "")).strip()
    chunk_id = _to_int(args.get("chunk_id"))

    if not doc_id or chunk_id is None:
        return {"status": "error", "message": doc_message(args, "doc_and_chunk_required")}

    if not library_id:
        return {"status": "error", "message": doc_message(args, "library_id_required")}

    try:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        bookmark_id = f"doc_bookmark_{timestamp[:20]}"

        bookmark_meta = {
            "bookmark_id": bookmark_id,
            "doc_id": doc_id,
            "library_id": library_id,
            "chunk_id": chunk_id,
            "created_at": datetime.now().isoformat(),
        }

        print(f"[DEBUG] Bookmark created: {bookmark_meta}")

        return {
            "status": "success",
            "text": doc_message(args, "bookmark_added", chunk_id=chunk_id),
            "raw": {"bookmark_id": bookmark_id, "chunk_id": chunk_id},
        }

    except Exception as exc:
        return {
            "status": "error",
            "message": doc_message(args, "bookmark_failed", error=str(exc)),
        }


@auto_user_context
def nisb_doc_recall(args: dict) -> dict:
    """Recall surrounding document chunks."""
    args = args or {}
    user_ctx = get_user_ctx()
    base_path = user_ctx.base
    doc_id = str(args.get("doc_id", "")).strip()
    library_id = str(args.get("library_id", "")).strip()
    chunk_id = _to_int(args.get("chunk_id"))
    window = _positive_int(args.get("window", 8), 8)

    if not doc_id or chunk_id is None:
        return {"status": "error", "message": doc_message(args, "doc_and_chunk_required")}

    if not library_id:
        return {"status": "error", "message": doc_message(args, "library_id_required")}

    try:
        db = get_doc_db_sqlite(base_path, library_id)
        chunks = db.get_chunks(doc_id)

        if not chunks:
            return {"status": "error", "message": doc_message(args, "doc_chunks_not_found")}

        if chunk_id >= len(chunks) or chunk_id < 0:
            return {
                "status": "error",
                "text": doc_message(
                    args,
                    "chunk_out_of_range",
                    chunk_id=chunk_id,
                    max_chunk=max(len(chunks) - 1, 0),
                ),
                "raw": {},
            }

        start = max(0, chunk_id - window)
        end = min(len(chunks), chunk_id + window + 1)
        content = "\n\n---\n\n".join([str(c.get("text", "")) for c in chunks[start:end]])

        return {
            "status": "success",
            "text": content,
            "raw": {"content": content, "chunk_id": chunk_id, "range": [start, end]},
        }

    except Exception as exc:
        return {
            "status": "error",
            "message": doc_message(args, "context_expand_failed", error=str(exc)),
        }


@auto_user_context
def nisb_doc_annotate(args: dict) -> dict:
    """Compatibility annotation entry that writes to the library annotation source."""
    args = args or {}
    doc_id = str(args.get("doc_id", "")).strip()
    library_id = str(args.get("library_id", "")).strip()
    chunk_id = _to_int(args.get("chunk_id"))

    content = args.get("content") or args.get("annotation") or ""
    content = str(content).strip()

    if not doc_id or chunk_id is None:
        return {"status": "error", "message": doc_message(args, "doc_and_chunk_required")}

    if not library_id:
        return {"status": "error", "message": doc_message(args, "library_id_required")}

    if not content:
        return {"status": "error", "message": doc_message(args, "annotation_empty")}

    try:
        from tools.annotations.library_annotations import nisb_library_annotation_add

        res = nisb_library_annotation_add(
            {
                **args,
                "library_id": library_id,
                "doc_id": doc_id,
                "chunk_id": chunk_id,
                "content": content,
            }
        )

        if isinstance(res, dict) and res.get("status") == "success":
            ann = res.get("annotation") or {}
            ann_chunk_id = ann.get("chunk_id")
            ann_content = ann.get("content")
            return {
                "status": "success",
                "text": doc_message(
                    args,
                    "annotation_added",
                    chunk_id=ann_chunk_id,
                    content=ann_content,
                ),
                "raw": {
                    "annotation_id": ann.get("annotation_id"),
                    "chunk_id": ann_chunk_id,
                    "content": ann_content,
                },
            }

        if isinstance(res, dict):
            return res

        return {
            "status": "error",
            "message": doc_message(
                args,
                "annotation_failed",
                error=doc_message(args, "unknown_error"),
            ),
        }

    except Exception as exc:
        return {
            "status": "error",
            "message": doc_message(args, "annotation_failed", error=str(exc)),
        }


@auto_user_context
def nisb_doc_network(args: dict) -> dict:
    """Return a reserved network feature response."""
    args = args or {}
    _ = get_ui_locale(args)
    return {"status": "success", "text": doc_message(args, "network_reserved"), "raw": {}}
