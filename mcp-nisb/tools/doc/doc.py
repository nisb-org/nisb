#!/usr/bin/env python3
"""NISB Doc unified exports for the SQLite-backed document toolchain."""

from __future__ import annotations

import json
import shutil
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from tools.libraries import (
    nisb_library_create,
    nisb_library_list,
    nisb_library_delete,
    nisb_library_stats,
    nisb_library_get_info,
)
from tools.doc.lib_upload import nisb_doc_upload_to_library
from tools.doc.core.search_sqlite import (
    nisb_doc_search,
    nisb_doc_search_hybrid,
    nisb_doc_search_with_filter,
)
from tools.doc.core.upload_sqlite import (
    nisb_doc_upload,
    nisb_doc_embedding,
    nisb_doc_stats,
)
from tools.doc.core.context import (
    nisb_doc_expand_enhanced,
    nisb_doc_bookmark,
    nisb_doc_recall,
    nisb_doc_annotate,
    nisb_doc_network,
)
from tools.doc.doc_evidence import nisb_library_doc_evidence
from tools.doc.analysis.doc_qa import nisb_doc_qa_ask, nisb_doc_qa_list
from tools.doc.analysis.outline import nisb_doc_generate_outline
from tools.doc.analysis.summary import nisb_doc_generate_summary
from tools.doc.analysis.concepts import nisb_doc_analyze_concepts
from tools.doc.library_reading import (
    nisb_library_continuous_read,
    nisb_library_translate_span,
)
from tools.doc.doc_db_sqlite import (
    DocDBSQLite as DocDB,
    get_doc_db_sqlite as get_doc_db,
)
from tools.doc.core.path_resolver import PathResolver, StorageMode
from tools.doc.doc_parser import parse_document, get_supported_formats, validate_extracted_content
from tools.doc.helpers import (
    EMBEDDING_MODEL,
    EMBEDDING_DIM,
    EMBEDDING_BATCH_SIZE,
    BATCH_DELAY_SECONDS,
    CHUNK_SIZE,
    CHUNK_OVERLAP,
    MAX_RESULTS,
    MAX_FILE_SIZE,
    _limit_resources,
    _chunk_text,
    SimpleBM25,
    reciprocal_rank_fusion,
)
from tools.doc.core.dod_guard import (
    require_safe_id,
    safe_child_dir,
    normalize_doc_ids,
    chunk_list,
)
from tools.doc.core.dod_events import append_doc_event
from tools.doc.core.dod_sqlite import connect_doc_db_budgeted
from tools.doc.analysis.outline_tree import nisb_doc_outline_get, nisb_doc_outline_expand, nisb_doc_outline_translate
from tools.filesystem.formal_response import ensure_formal_response
from tools.i18n.backend_i18n import i18n_text, normalize_backend_locale
from core.user_context import auto_user_context, get_user_ctx

MAX_BATCH_DOCS = 2000
SQLITE_DELETE_GROUP_SIZE = 200
SQLITE_BUSY_TIMEOUT_MS = 10_000


def _safe_args(args: Dict[str, Any] | None) -> Dict[str, Any]:
    return args if isinstance(args, dict) else {}


def _locale(args: Dict[str, Any] | None) -> str:
    return normalize_backend_locale(_safe_args(args).get("locale"))


def _txt(args: Dict[str, Any] | None, en: str, zh: str) -> str:
    return i18n_text(_locale(args), {"en": en, "zh-CN": zh}, en)


def _fmt(args: Dict[str, Any] | None, en: str, zh: str, **kwargs: Any) -> str:
    return _txt(args, en, zh).format(**kwargs)


def _log_kv(event: str, **kwargs: Any) -> None:
    parts = [f"[{event}]"]
    for k, v in kwargs.items():
        parts.append(f"{k}={v}")
    print(" ".join(parts))


def _get_request_id(args: Dict[str, Any]) -> str:
    rid = str(args.get("request_id") or "").strip()
    return rid if rid else uuid.uuid4().hex[:10]


def _doc_result(args: Dict[str, Any], payload: Dict[str, Any], kind: str) -> Dict[str, Any]:
    return ensure_formal_response(
        args,
        payload,
        default_kind=kind,
        keep_compat_fields=True,
    )


def _read_doc_display_name(doc_dir: Path, doc_id: str) -> str:
    meta_file = doc_dir / "metadata.json"
    if not meta_file.exists():
        return doc_id
    try:
        with open(meta_file, "r", encoding="utf-8") as f:
            meta = json.load(f)
        if not isinstance(meta, dict):
            return doc_id
        return meta.get("title") or meta.get("filename") or meta.get("name") or doc_id
    except Exception:
        return doc_id


def _sanitize_filename(name: str) -> str:
    n = str(name or "").strip()
    if not n:
        return ""
    if "/" in n or "\\" in n:
        return ""
    if ".." in n:
        return ""
    if len(n) > 200:
        return ""
    return n


def _message_missing_library_id(args: Dict[str, Any]) -> str:
    return _txt(args, "❌ library_id cannot be empty", "❌ library_id 不能为空")


def _message_missing_doc_id(args: Dict[str, Any]) -> str:
    return _txt(args, "❌ doc_id cannot be empty", "❌ doc_id 不能为空")


def _message_invalid_params(args: Dict[str, Any], error: Any) -> str:
    return _fmt(args, "❌ Invalid parameters: {error}", "❌ 参数非法：{error}", error=error)


def _message_unsafe_path(args: Dict[str, Any], error: Any) -> str:
    return _fmt(args, "❌ Unsafe path: {error}", "❌ 不安全路径：{error}", error=error)


def _message_library_not_found(args: Dict[str, Any], library_id: str) -> str:
    return _fmt(args, "❌ Library does not exist: {library_id}", "❌ 库不存在：{library_id}", library_id=library_id)


def _message_doc_not_found(args: Dict[str, Any], doc_id: str) -> str:
    return _fmt(args, "❌ Document does not exist: {doc_id}", "❌ 文档不存在：{doc_id}", doc_id=doc_id)


@auto_user_context
def nisb_library_doc_delete(args: Dict[str, Any]) -> Dict[str, Any]:
    args = _safe_args(args)
    request_id = _get_request_id(args)

    library_id_raw = str(args.get("library_id") or "").strip()
    doc_id_raw = str(args.get("doc_id") or "").strip()

    if not library_id_raw:
        return _doc_result(
            args,
            {"status": "error", "message": _message_missing_library_id(args), "request_id": request_id},
            "library_doc_delete",
        )
    if not doc_id_raw:
        return _doc_result(
            args,
            {"status": "error", "message": _message_missing_doc_id(args), "request_id": request_id},
            "library_doc_delete",
        )

    try:
        library_id = require_safe_id("library_id", library_id_raw)
        doc_id = require_safe_id("doc_id", doc_id_raw)
    except Exception as e:
        return _doc_result(
            args,
            {"status": "error", "message": _message_invalid_params(args, e), "request_id": request_id},
            "library_doc_delete",
        )

    user_base = Path(get_user_ctx().base)
    t0 = time.perf_counter()

    _log_kv(
        "doc_delete_start",
        request_id=request_id,
        user_base=str(user_base),
        library_id=library_id,
        doc_id=doc_id,
    )

    library_path = user_base / "libraries" / library_id
    docs_root = library_path / "docs"

    try:
        doc_dir = safe_child_dir(docs_root, doc_id)
    except Exception as e:
        append_doc_event(
            user_base=user_base,
            request_id=request_id,
            action="doc_delete",
            library_id=library_id,
            doc_ids=[doc_id],
            status="error",
            payload={"error": f"unsafe_path: {e}"},
        )
        return _doc_result(
            args,
            {"status": "error", "message": _message_unsafe_path(args, e), "request_id": request_id},
            "library_doc_delete",
        )

    if not library_path.exists():
        append_doc_event(
            user_base=user_base,
            request_id=request_id,
            action="doc_delete",
            library_id=library_id,
            doc_ids=[doc_id],
            status="error",
            payload={"error": "library_not_found", "library_path": str(library_path)},
        )
        return _doc_result(
            args,
            {
                "status": "error",
                "message": _message_library_not_found(args, library_id),
                "request_id": request_id,
                "debug": {"user_base": str(user_base), "library_path": str(library_path)},
            },
            "library_doc_delete",
        )

    display_name = _read_doc_display_name(doc_dir, doc_id)

    deleted_dir = False
    dir_error = None
    try:
        if doc_dir.exists():
            shutil.rmtree(doc_dir)
            deleted_dir = True
    except Exception as e:
        dir_error = str(e)

    deleted_db = False
    db_deleted = None
    db_error = None
    try:
        db = get_doc_db(str(user_base), library_id=library_id)
        db_deleted = db.delete_document(doc_id)
        deleted_db = bool(db_deleted.get("ok")) and (
            (db_deleted.get("deleted_embeddings", 0) > 0)
            or (db_deleted.get("deleted_chunks", 0) > 0)
            or (db_deleted.get("deleted_documents", 0) > 0)
        )
        if not db_deleted.get("ok", True):
            db_error = db_deleted.get("error") or "unknown db error"
    except Exception as e:
        db_error = str(e)

    elapsed_ms = int((time.perf_counter() - t0) * 1000)
    op_status = "error" if (dir_error and db_error) else "success"

    _log_kv(
        "doc_delete_end",
        request_id=request_id,
        library_id=library_id,
        doc_id=doc_id,
        status=op_status,
        elapsed_ms=elapsed_ms,
        deleted_dir=deleted_dir,
        deleted_db=deleted_db,
        dir_error="none" if not dir_error else dir_error,
        db_error="none" if not db_error else db_error,
    )

    if dir_error and db_error:
        append_doc_event(
            user_base=user_base,
            request_id=request_id,
            action="doc_delete",
            library_id=library_id,
            doc_ids=[doc_id],
            status="error",
            payload={
                "display_name": display_name,
                "deleted_dir": deleted_dir,
                "deleted_db": deleted_db,
                "dir_error": dir_error,
                "db_error": db_error,
                "elapsed_ms": elapsed_ms,
            },
        )
        return _doc_result(
            args,
            {
                "status": "error",
                "message": _fmt(
                    args,
                    "❌ Delete failed because both directory deletion and index cleanup failed: dir={dir_error}; db={db_error}",
                    "❌ 删除失败（目录与索引均失败）：dir={dir_error}; db={db_error}",
                    dir_error=dir_error,
                    db_error=db_error,
                ),
                "request_id": request_id,
                "library_id": library_id,
                "doc_id": doc_id,
                "deleted_dir": False,
                "deleted_db": False,
                "db_deleted": db_deleted,
            },
            "library_doc_delete",
        )

    if (not deleted_dir) and (not deleted_db) and (not doc_dir.exists()):
        append_doc_event(
            user_base=user_base,
            request_id=request_id,
            action="doc_delete_noop",
            library_id=library_id,
            doc_ids=[doc_id],
            status="success",
            payload={
                "display_name": display_name,
                "deleted_dir": False,
                "deleted_db": False,
                "dir_error": dir_error,
                "db_error": db_error,
                "elapsed_ms": elapsed_ms,
            },
        )
        return _doc_result(
            args,
            {
                "status": "success",
                "message": _fmt(
                    args,
                    "✅ Document already does not exist; no deletion needed: {display_name}",
                    "✅ 文档已不存在（无需重复删除）：{display_name}",
                    display_name=display_name,
                ),
                "request_id": request_id,
                "library_id": library_id,
                "doc_id": doc_id,
                "deleted_dir": False,
                "deleted_db": False,
                "db_deleted": db_deleted,
            },
            "library_doc_delete",
        )

    msg_parts = [
        _fmt(args, "✅ Deleted document: {display_name}", "✅ 已删除文档：{display_name}", display_name=display_name)
    ]
    if dir_error:
        msg_parts.append(
            _fmt(
                args,
                "(Directory deletion failed, but the operation continued: {error})",
                "（目录删除失败但已继续：{error}）",
                error=dir_error,
            )
        )
    if db_error:
        msg_parts.append(
            _fmt(
                args,
                "(Index cleanup failed, but the operation continued: {error})",
                "（索引清理失败但已继续：{error}）",
                error=db_error,
            )
        )

    append_doc_event(
        user_base=user_base,
        request_id=request_id,
        action="doc_delete",
        library_id=library_id,
        doc_ids=[doc_id],
        status="success",
        payload={
            "display_name": display_name,
            "deleted_dir": deleted_dir,
            "deleted_db": deleted_db,
            "dir_error": dir_error,
            "db_error": db_error,
            "elapsed_ms": elapsed_ms,
        },
    )

    return _doc_result(
        args,
        {
            "status": "success",
            "message": " ".join(msg_parts),
            "request_id": request_id,
            "library_id": library_id,
            "doc_id": doc_id,
            "deleted_dir": deleted_dir,
            "deleted_db": deleted_db,
            "db_deleted": db_deleted,
        },
        "library_doc_delete",
    )


@auto_user_context
def nisb_library_doc_delete_batch(args: Dict[str, Any]) -> Dict[str, Any]:
    args = _safe_args(args)
    request_id = _get_request_id(args)

    library_id_raw = str(args.get("library_id") or "").strip()
    doc_ids_raw = normalize_doc_ids(args.get("doc_ids") or args.get("docs") or args.get("doc_id_list"))

    dry_run = bool(args.get("dry_run", False))
    delete_dir = bool(args.get("delete_dir", True))
    continue_on_error = bool(args.get("continue_on_error", True))
    ignore_missing = bool(args.get("ignore_missing", True))

    if not library_id_raw:
        return _doc_result(
            args,
            {"status": "error", "message": _message_missing_library_id(args), "request_id": request_id},
            "library_doc_delete_batch",
        )
    if not doc_ids_raw:
        return _doc_result(
            args,
            {
                "status": "error",
                "message": _txt(
                    args,
                    "❌ doc_ids cannot be empty; provide a list or a comma/newline-separated string",
                    "❌ doc_ids 不能为空（list 或 逗号/换行分隔字符串）",
                ),
                "request_id": request_id,
            },
            "library_doc_delete_batch",
        )

    if len(doc_ids_raw) > MAX_BATCH_DOCS:
        return _doc_result(
            args,
            {
                "status": "error",
                "message": _fmt(
                    args,
                    "❌ doc_ids exceeds the limit: {count} > {max_items}",
                    "❌ doc_ids 数量超上限：{count} > {max_items}",
                    count=len(doc_ids_raw),
                    max_items=MAX_BATCH_DOCS,
                ),
                "request_id": request_id,
                "library_id": library_id_raw,
                "raw": {"requested": len(doc_ids_raw), "max_items": MAX_BATCH_DOCS},
            },
            "library_doc_delete_batch",
        )

    try:
        library_id = require_safe_id("library_id", library_id_raw)
        doc_ids = [require_safe_id("doc_id", d) for d in doc_ids_raw]
    except Exception as e:
        return _doc_result(
            args,
            {"status": "error", "message": _message_invalid_params(args, e), "request_id": request_id},
            "library_doc_delete_batch",
        )

    user_base = Path(get_user_ctx().base)
    t0 = time.perf_counter()

    library_path = user_base / "libraries" / library_id
    docs_root = library_path / "docs"

    if not library_path.exists():
        if not dry_run:
            append_doc_event(
                user_base=user_base,
                request_id=request_id,
                action="doc_delete_batch",
                library_id=library_id,
                doc_ids=doc_ids,
                status="error",
                payload={"error": "library_not_found", "library_path": str(library_path)},
            )
        return _doc_result(
            args,
            {
                "status": "error",
                "message": _message_library_not_found(args, library_id),
                "request_id": request_id,
                "debug": {"user_base": str(user_base), "library_path": str(library_path)},
            },
            "library_doc_delete_batch",
        )

    db = get_doc_db(str(user_base), library_id=library_id)

    results: List[Dict[str, Any]] = []
    db_deleted_total = {"embeddings": 0, "chunks": 0, "documents": 0}
    db_error: Optional[str] = None

    if not dry_run:
        try:
            with db._lock:
                conn = connect_doc_db_budgeted(
                    db.db_path,
                    readonly=False,
                    busy_timeout_ms=SQLITE_BUSY_TIMEOUT_MS,
                )
                cur = None
                try:
                    cur = conn.cursor()
                    cur.execute("BEGIN IMMEDIATE;")

                    for group in chunk_list(doc_ids, SQLITE_DELETE_GROUP_SIZE):
                        placeholders = ",".join(["?"] * len(group))
                        cur.execute(f"DELETE FROM embeddings WHERE doc_id IN ({placeholders})", group)
                        db_deleted_total["embeddings"] += int(cur.rowcount or 0)

                        cur.execute(f"DELETE FROM chunks WHERE doc_id IN ({placeholders})", group)
                        db_deleted_total["chunks"] += int(cur.rowcount or 0)

                        cur.execute(f"DELETE FROM documents WHERE doc_id IN ({placeholders})", group)
                        db_deleted_total["documents"] += int(cur.rowcount or 0)

                    cur.execute("COMMIT;")
                except Exception:
                    try:
                        if cur is not None:
                            cur.execute("ROLLBACK;")
                    except Exception:
                        pass
                    raise
                finally:
                    conn.close()
        except Exception as e:
            db_error = str(e)
            if not continue_on_error:
                elapsed_ms = int((time.perf_counter() - t0) * 1000)
                append_doc_event(
                    user_base=user_base,
                    request_id=request_id,
                    action="doc_delete_batch",
                    library_id=library_id,
                    doc_ids=doc_ids,
                    status="error",
                    payload={
                        "dry_run": dry_run,
                        "delete_dir": delete_dir,
                        "continue_on_error": continue_on_error,
                        "ignore_missing": ignore_missing,
                        "error": f"sqlite_error: {db_error}",
                        "db_deleted_total": db_deleted_total,
                        "elapsed_ms": elapsed_ms,
                    },
                )
                return _doc_result(
                    args,
                    {
                        "status": "error",
                        "message": _fmt(
                            args,
                            "❌ Batch delete failed during SQLite cleanup: {error}",
                            "❌ 批量删除失败（SQLite 清理失败）：{error}",
                            error=db_error,
                        ),
                        "request_id": request_id,
                        "library_id": library_id,
                        "doc_ids": doc_ids,
                        "db_deleted_total": db_deleted_total,
                    },
                    "library_doc_delete_batch",
                )

    dir_deleted_count = 0
    dir_failed_count = 0
    missing_count = 0

    for doc_id in doc_ids:
        try:
            doc_dir = safe_child_dir(docs_root, doc_id)
        except Exception as e:
            item = {
                "doc_id": doc_id,
                "display_name": doc_id,
                "dir_existed": False,
                "dir_deleted": False,
                "dir_error": f"unsafe doc path: {e}",
            }
            dir_failed_count += 1
            results.append(item)
            if not continue_on_error:
                break
            continue

        display_name = _read_doc_display_name(doc_dir, doc_id)

        item = {
            "doc_id": doc_id,
            "display_name": display_name,
            "dir_existed": doc_dir.exists(),
            "dir_deleted": False,
            "dir_error": None,
        }

        if not doc_dir.exists():
            missing_count += 1
            results.append(item)
            continue

        if (not delete_dir) or dry_run:
            results.append(item)
            continue

        try:
            shutil.rmtree(doc_dir)
            item["dir_deleted"] = True
            dir_deleted_count += 1
        except Exception as e:
            item["dir_error"] = str(e)
            dir_failed_count += 1
            if not continue_on_error:
                results.append(item)
                break

        results.append(item)

    msg_parts = [
        _fmt(
            args,
            "✅ Batch delete completed: requested={count}",
            "✅ 批量删除完成：请求={count}",
            count=len(doc_ids),
        ),
        _fmt(
            args,
            "SQLite cleanup(documents/chunks/embeddings)={documents}/{chunks}/{embeddings}",
            "SQLite清理(documents/chunks/embeddings)={documents}/{chunks}/{embeddings}",
            documents=db_deleted_total["documents"],
            chunks=db_deleted_total["chunks"],
            embeddings=db_deleted_total["embeddings"],
        ),
    ]
    if delete_dir and (not dry_run):
        msg_parts.append(
            _fmt(
                args,
                "Directory deletion: success={success} failed={failed} missing={missing}",
                "目录删除：成功={success} 失败={failed} 不存在={missing}",
                success=dir_deleted_count,
                failed=dir_failed_count,
                missing=missing_count,
            )
        )
    if db_error:
        msg_parts.append(
            _fmt(
                args,
                "(SQLite cleanup failed, but the operation continued: {error})",
                "（SQLite 清理失败但已继续：{error}）",
                error=db_error,
            )
        )

    elapsed_ms = int((time.perf_counter() - t0) * 1000)

    if (not ignore_missing) and missing_count > 0:
        if not dry_run:
            append_doc_event(
                user_base=user_base,
                request_id=request_id,
                action="doc_delete_batch",
                library_id=library_id,
                doc_ids=doc_ids,
                status="error",
                payload={
                    "dry_run": dry_run,
                    "delete_dir": delete_dir,
                    "continue_on_error": continue_on_error,
                    "ignore_missing": ignore_missing,
                    "error": "ignore_missing=false and some docs missing",
                    "dir_deleted": dir_deleted_count,
                    "dir_failed": dir_failed_count,
                    "missing": missing_count,
                    "db_deleted_total": db_deleted_total,
                    "db_error": db_error,
                    "elapsed_ms": elapsed_ms,
                },
            )
        return _doc_result(
            args,
            {
                "status": "error",
                "message": _txt(
                    args,
                    "❌ Some documents are missing and ignore_missing=false; ",
                    "❌ 部分文档不存在，且 ignore_missing=false；",
                )
                + " ".join(msg_parts),
                "request_id": request_id,
                "library_id": library_id,
                "doc_ids": doc_ids,
                "db_error": db_error,
                "db_deleted_total": db_deleted_total,
                "results": results,
            },
            "library_doc_delete_batch",
        )

    if (not continue_on_error) and (dir_failed_count > 0 or (db_error is not None)):
        if not dry_run:
            append_doc_event(
                user_base=user_base,
                request_id=request_id,
                action="doc_delete_batch",
                library_id=library_id,
                doc_ids=doc_ids,
                status="error",
                payload={
                    "dry_run": dry_run,
                    "delete_dir": delete_dir,
                    "continue_on_error": continue_on_error,
                    "ignore_missing": ignore_missing,
                    "error": "continue_on_error=false and some failures occurred",
                    "dir_deleted": dir_deleted_count,
                    "dir_failed": dir_failed_count,
                    "missing": missing_count,
                    "db_deleted_total": db_deleted_total,
                    "db_error": db_error,
                    "elapsed_ms": elapsed_ms,
                },
            )
        return _doc_result(
            args,
            {
                "status": "error",
                "message": _txt(
                    args,
                    "❌ Batch delete did not fully succeed because continue_on_error=false; ",
                    "❌ 批量删除未完整成功（continue_on_error=false）；",
                )
                + " ".join(msg_parts),
                "request_id": request_id,
                "library_id": library_id,
                "doc_ids": doc_ids,
                "db_error": db_error,
                "db_deleted_total": db_deleted_total,
                "results": results,
            },
            "library_doc_delete_batch",
        )

    if not dry_run:
        append_doc_event(
            user_base=user_base,
            request_id=request_id,
            action="doc_delete_batch",
            library_id=library_id,
            doc_ids=doc_ids,
            status="success",
            payload={
                "dry_run": dry_run,
                "delete_dir": delete_dir,
                "continue_on_error": continue_on_error,
                "ignore_missing": ignore_missing,
                "dir_deleted": dir_deleted_count,
                "dir_failed": dir_failed_count,
                "missing": missing_count,
                "db_deleted_total": db_deleted_total,
                "db_error": db_error,
                "elapsed_ms": elapsed_ms,
            },
        )

    return _doc_result(
        args,
        {
            "status": "success",
            "message": " ".join(msg_parts),
            "request_id": request_id,
            "library_id": library_id,
            "doc_ids": doc_ids,
            "dry_run": dry_run,
            "delete_dir": delete_dir,
            "continue_on_error": continue_on_error,
            "ignore_missing": ignore_missing,
            "db_error": db_error,
            "db_deleted_total": db_deleted_total,
            "results": results,
            "raw": {
                "requested": len(doc_ids),
                "max_items": MAX_BATCH_DOCS,
                "sqlite_group_size": SQLITE_DELETE_GROUP_SIZE,
                "sqlite_busy_timeout_ms": SQLITE_BUSY_TIMEOUT_MS,
                "dir_deleted": dir_deleted_count,
                "dir_failed": dir_failed_count,
                "missing": missing_count,
                "db_deleted_total": db_deleted_total,
                "elapsed_ms": elapsed_ms,
            },
        },
        "library_doc_delete_batch",
    )


@auto_user_context
def nisb_library_doc_rename(args: Dict[str, Any]) -> Dict[str, Any]:
    args = _safe_args(args)
    request_id = _get_request_id(args)

    library_id_raw = str(args.get("library_id") or "").strip()
    doc_id_raw = str(args.get("doc_id") or "").strip()
    new_filename_raw = args.get("new_filename") or args.get("filename") or ""
    new_filename = _sanitize_filename(str(new_filename_raw))

    if not library_id_raw:
        return _doc_result(
            args,
            {"status": "error", "message": _message_missing_library_id(args), "request_id": request_id},
            "library_doc_rename",
        )
    if not doc_id_raw:
        return _doc_result(
            args,
            {"status": "error", "message": _message_missing_doc_id(args), "request_id": request_id},
            "library_doc_rename",
        )
    if not new_filename:
        return _doc_result(
            args,
            {
                "status": "error",
                "message": _txt(
                    args,
                    "❌ new_filename is invalid; it cannot be empty and cannot contain /, \\, or ..",
                    "❌ new_filename 非法（不能为空，且不能包含 /、\\\\ 或 ..）",
                ),
                "request_id": request_id,
            },
            "library_doc_rename",
        )

    try:
        library_id = require_safe_id("library_id", library_id_raw)
        doc_id = require_safe_id("doc_id", doc_id_raw)
    except Exception as e:
        return _doc_result(
            args,
            {"status": "error", "message": _message_invalid_params(args, e), "request_id": request_id},
            "library_doc_rename",
        )

    user_base = Path(get_user_ctx().base)
    t0 = time.perf_counter()

    library_path = user_base / "libraries" / library_id
    docs_root = library_path / "docs"

    try:
        doc_dir = safe_child_dir(docs_root, doc_id)
    except Exception as e:
        append_doc_event(
            user_base=user_base,
            request_id=request_id,
            action="doc_rename",
            library_id=library_id,
            doc_ids=[doc_id],
            status="error",
            payload={"error": f"unsafe_path: {e}", "new_filename": new_filename},
        )
        return _doc_result(
            args,
            {"status": "error", "message": _message_unsafe_path(args, e), "request_id": request_id},
            "library_doc_rename",
        )

    if not library_path.exists():
        append_doc_event(
            user_base=user_base,
            request_id=request_id,
            action="doc_rename",
            library_id=library_id,
            doc_ids=[doc_id],
            status="error",
            payload={"error": "library_not_found", "library_path": str(library_path), "new_filename": new_filename},
        )
        return _doc_result(
            args,
            {
                "status": "error",
                "message": _message_library_not_found(args, library_id),
                "request_id": request_id,
                "debug": {"user_base": str(user_base), "library_path": str(library_path)},
            },
            "library_doc_rename",
        )

    if not doc_dir.exists():
        append_doc_event(
            user_base=user_base,
            request_id=request_id,
            action="doc_rename",
            library_id=library_id,
            doc_ids=[doc_id],
            status="error",
            payload={"error": "doc_not_found", "new_filename": new_filename},
        )
        return _doc_result(
            args,
            {
                "status": "error",
                "message": _message_doc_not_found(args, doc_id),
                "request_id": request_id,
                "library_id": library_id,
                "doc_id": doc_id,
            },
            "library_doc_rename",
        )

    meta_file = doc_dir / "metadata.json"
    meta_updated = False
    meta_error = None
    try:
        if meta_file.exists():
            with open(meta_file, "r", encoding="utf-8") as f:
                meta = json.load(f)
            if not isinstance(meta, dict):
                meta = {}

            old_filename = str(meta.get("filename") or "").strip()
            old_title = str(meta.get("title") or "").strip()

            meta["filename"] = new_filename
            if (not old_title) or (old_title == old_filename):
                meta["title"] = new_filename

            with open(meta_file, "w", encoding="utf-8") as f:
                json.dump(meta, f, ensure_ascii=False, indent=2)

            meta_updated = True
    except Exception as e:
        meta_error = str(e)

    db_updated = False
    db_result = None
    db_error = None
    try:
        db = get_doc_db(str(user_base), library_id=library_id)
        db_result = db.rename_document(doc_id, new_filename)
        if not db_result.get("ok", True):
            db_error = db_result.get("error") or "unknown db error"
        else:
            db_updated = db_result.get("updated_documents", 0) > 0
    except Exception as e:
        db_error = str(e)

    elapsed_ms = int((time.perf_counter() - t0) * 1000)

    if meta_error and db_error:
        append_doc_event(
            user_base=user_base,
            request_id=request_id,
            action="doc_rename",
            library_id=library_id,
            doc_ids=[doc_id],
            status="error",
            payload={
                "new_filename": new_filename,
                "meta_updated": meta_updated,
                "db_updated": db_updated,
                "meta_error": meta_error,
                "db_error": db_error,
                "elapsed_ms": elapsed_ms,
            },
        )
        return _doc_result(
            args,
            {
                "status": "error",
                "message": _fmt(
                    args,
                    "❌ Rename failed because both metadata and index update failed: meta={meta_error}; db={db_error}",
                    "❌ 重命名失败（metadata 与索引均失败）：meta={meta_error}; db={db_error}",
                    meta_error=meta_error,
                    db_error=db_error,
                ),
                "request_id": request_id,
                "library_id": library_id,
                "doc_id": doc_id,
                "new_filename": new_filename,
            },
            "library_doc_rename",
        )

    msg = _fmt(args, "✅ Renamed: {new_filename}", "✅ 已重命名：{new_filename}", new_filename=new_filename)
    if meta_error:
        msg += _fmt(
            args,
            "(metadata update failed, but the operation continued: {error})",
            "（metadata 更新失败但已继续：{error}）",
            error=meta_error,
        )
    if db_error:
        msg += _fmt(
            args,
            "(Index update failed, but the operation continued: {error})",
            "（索引更新失败但已继续：{error}）",
            error=db_error,
        )

    append_doc_event(
        user_base=user_base,
        request_id=request_id,
        action="doc_rename",
        library_id=library_id,
        doc_ids=[doc_id],
        status="success",
        payload={
            "new_filename": new_filename,
            "meta_updated": meta_updated,
            "db_updated": db_updated,
            "meta_error": meta_error,
            "db_error": db_error,
            "elapsed_ms": elapsed_ms,
        },
    )

    return _doc_result(
        args,
        {
            "status": "success",
            "message": msg,
            "request_id": request_id,
            "library_id": library_id,
            "doc_id": doc_id,
            "new_filename": new_filename,
            "meta_updated": meta_updated,
            "db_updated": db_updated,
            "db_result": db_result,
        },
        "library_doc_rename",
    )


__all__ = [
    "nisb_library_create",
    "nisb_library_list",
    "nisb_library_delete",
    "nisb_library_stats",
    "nisb_library_get_info",
    "nisb_library_doc_delete",
    "nisb_library_doc_delete_batch",
    "nisb_library_doc_rename",
    "nisb_doc_upload_to_library",
    "nisb_library_doc_evidence",
    "nisb_doc_outline_get",
    "nisb_doc_outline_expand",
    "nisb_doc_outline_translate",
    "nisb_doc_upload",
    "nisb_doc_embedding",
    "nisb_doc_search",
    "nisb_doc_bookmark",
    "nisb_doc_recall",
    "nisb_doc_annotate",
    "nisb_doc_network",
    "nisb_doc_stats",
    "nisb_doc_search_hybrid",
    "nisb_doc_search_with_filter",
    "nisb_doc_expand_enhanced",
    "nisb_doc_generate_outline",
    "nisb_doc_generate_summary",
    "nisb_doc_analyze_concepts",
    "nisb_library_continuous_read",
    "nisb_library_translate_span",
    "nisb_doc_qa_ask",
    "nisb_doc_qa_list",
    "DocDB",
    "get_doc_db",
    "PathResolver",
    "StorageMode",
    "parse_document",
    "get_supported_formats",
    "validate_extracted_content",
    "EMBEDDING_MODEL",
    "EMBEDDING_DIM",
    "EMBEDDING_BATCH_SIZE",
    "BATCH_DELAY_SECONDS",
    "CHUNK_SIZE",
    "CHUNK_OVERLAP",
    "MAX_RESULTS",
    "MAX_FILE_SIZE",
    "_limit_resources",
    "_chunk_text",
    "SimpleBM25",
    "reciprocal_rank_fusion",
]
