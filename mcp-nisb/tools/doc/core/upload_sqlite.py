#!/usr/bin/env python3
"""
【改造】文档上传模块 - SQLite 版本
Phase 7.0+ SQLite 版本

稳定性增强（v8.5.4+）：
- 所有写 doc_db.sqlite 的路径统一走 DocDBSQLite（connect_doc_db: WAL + busy_timeout + foreign_keys）
- 上传：documents + chunks 使用单事务批量写（upsert_document_with_chunks）
- embedding：批量写 embeddings（add_embeddings_bulk），避免每条 commit 导致 database is locked
- stats：读取也使用统一连接工厂（readonly），减少与写冲突

T1.1 增量：
- published_at 正式下沉到 SQLite documents 表
- 普通文档若未显式传入 published_at，则回退为 uploaded_at

T2.x 兼容补丁：
- 旧库首次读取 stats 前，先对 documents 做懒迁移
- stats 统一复用 DocDBSQLite.list_documents() / get_statistics()
- library.json 缺少 stats 字段时自动补齐
- 兼容修正旧调用里 LibraryManager 参数顺序混用
"""

from __future__ import annotations

import gc
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

import numpy as np
from openai import OpenAI

from core.storage import save_json
from core.user_context import auto_user_context, get_user_ctx
from tools.doc.core.path_resolver import PathResolver
from tools.doc.doc_db_sqlite import get_doc_db_sqlite
from tools.doc.doc_parser import parse_document
from tools.doc.helpers import (
    BATCH_DELAY_SECONDS,
    CHUNK_OVERLAP,
    CHUNK_SIZE,
    EMBEDDING_BATCH_SIZE,
    EMBEDDING_DIM,
    EMBEDDING_MODEL,
    MAX_FILE_SIZE,
    _chunk_text_with_ranges,
    _limit_resources,
)
from tools.timeline import _append_timeline_activity


def _generate_doc_id() -> str:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    microsecond = datetime.now().microsecond
    return f"doc_{timestamp}_{microsecond:06d}"


def _normalize_iso_or_none(v: Optional[str]) -> Optional[str]:
    s = str(v or "").strip()
    if not s:
        return None
    try:
        x = s.replace("Z", "+00:00")
        dt = datetime.fromisoformat(x)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).isoformat()
    except Exception:
        return s


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ensure_library_meta_stats(meta: dict) -> dict:
    if not isinstance(meta, dict):
        meta = {}

    stats = meta.get("stats")
    if not isinstance(stats, dict):
        stats = {}

    stats.setdefault("doc_count", int(meta.get("doc_count", 0) or 0))
    stats.setdefault("total_chunks", 0)
    stats.setdefault("total_size_mb", 0)
    stats.setdefault("embedding_coverage", 0)

    meta["stats"] = stats
    meta.setdefault("doc_count", stats.get("doc_count", 0))
    meta.setdefault("concept_count", 0)
    meta.setdefault("relation_count", 0)
    return meta


def _upload_document_to_path(
    file_path: str,
    storage_path: str,
    filetype: str,
    tags: list,
    user_id: str,
    library_id: str,
    user_base_path: str,
    doc_id: str = None,
    published_at: str | None = None,
) -> dict:
    if not os.path.exists(file_path):
        return {"status": "error", "message": "❌ 文件不存在"}

    if os.path.getsize(file_path) > MAX_FILE_SIZE:
        return {"status": "error", "message": "❌ 文件过大（>100MB）"}

    try:
        if not doc_id:
            doc_id = _generate_doc_id()

        doc_dir = f"{storage_path}/{doc_id}"
        os.makedirs(doc_dir, exist_ok=True)

        print(f"[DEBUG] 上传到库: doc_id={doc_id}, library_id={library_id}, path={doc_dir}")

        parse_result = parse_document(file_path, filetype)
        content = parse_result.get("text", "")

        if not content or len(content.strip()) < 10:
            return {"status": "error", "message": "❌ 提取内容为空"}

        content_path = f"{doc_dir}/content.txt"
        with open(content_path, "w", encoding="utf-8") as f:
            f.write(content)

        print(f"[DEBUG] 内容已保存：{len(content)} 字符")

        chunk_items = _chunk_text_with_ranges(content, CHUNK_SIZE, CHUNK_OVERLAP)
        if not chunk_items:
            return {"status": "error", "message": "❌ 分块失败"}

        print(f"[DEBUG] 分块完成：{len(chunk_items)} 个块")

        uploaded_at = _utc_now_iso()
        normalized_published_at = _normalize_iso_or_none(published_at) or uploaded_at
        filename = os.path.basename(file_path)
        filesize = os.path.getsize(file_path)

        metadata = {
            "doc_id": doc_id,
            "filename": filename,
            "filetype": filetype,
            "uploaded_at": uploaded_at,
            "published_at": normalized_published_at,
            "total_chunks": len(chunk_items),
            "tags": tags if isinstance(tags, list) else [],
            "library_id": library_id,
        }
        save_json(f"{doc_dir}/metadata.json", metadata)

        db = get_doc_db_sqlite(user_base_path, library_id)
        db.upsert_document_with_chunks(
            doc_id=doc_id,
            library_id=library_id,
            filename=filename,
            filetype=filetype,
            file_size=filesize,
            chunk_texts=chunk_items,
            uploaded_at=uploaded_at,
            published_at=normalized_published_at,
            language="auto",
        )

        print("[DEBUG] SQLite 写入完成（documents + chunks + char ranges + published_at）")
        print(f"[DEBUG] 上传完成！doc_id={doc_id}")

        try:
            relative_path = f"libraries/{library_id}/docs/{doc_id}/content.txt"
            _append_timeline_activity(
                base_path=user_base_path,
                event={
                    "type": "document",
                    "date": uploaded_at,
                    "title": f"{metadata['filename']}（库：{library_id}）",
                    "path": relative_path,
                    "library_id": library_id,
                    "doc_id": doc_id,
                    "extra": {
                        "action": "upload",
                        "total_chunks": len(chunk_items),
                        "published_at": normalized_published_at,
                    },
                },
            )
        except Exception:
            import sys
            import traceback
            print("[WARN] timeline append failed in _upload_document_to_path", file=sys.stderr)
            traceback.print_exc()

        return {
            "status": "success",
            "message": (
                f"✅ 上传成功\n\n"
                f"📋 文档ID: {doc_id}\n"
                f"分块数: {len(chunk_items)}\n"
                f"发布时间: {normalized_published_at}\n\n"
                f"💡 下一步：使用 nisb_doc_embedding()"
            ),
            "raw": {
                "doc_id": doc_id,
                "chunks": len(chunk_items),
                "published_at": normalized_published_at,
            },
        }

    except Exception as e:
        import traceback
        print(f"[ERROR] 上传失败：{str(e)}")
        traceback.print_exc()
        return {"status": "error", "message": f"❌ 上传失败：{str(e)}"}


@auto_user_context
def nisb_doc_upload(args: dict) -> dict:
    user_ctx = get_user_ctx()
    base_path = user_ctx.base

    file_path = args.get("file_path", "").strip()
    filetype = args.get("filetype", "").strip().lower()
    tags = args.get("tags", [])
    library_id = args.get("library_id", "").strip()
    published_at = str(args.get("published_at", "") or "").strip() or None

    if not file_path or not filetype:
        return {"status": "error", "message": "❌ file_path 和 filetype 必填"}
    if not library_id:
        return {"status": "error", "message": "❌ library_id 必填"}

    from tools.libraries.manager import LibraryManager
    lib_manager = LibraryManager(base_path, user_ctx.user_id)
    lib_info = lib_manager.get_library_info(library_id)
    if lib_info["status"] != "success":
        return {"status": "error", "message": f"❌ 库不存在：{library_id}"}

    lib_path = f"{base_path}/libraries/{library_id}"
    doc_storage = f"{lib_path}/docs"
    os.makedirs(doc_storage, exist_ok=True)

    result = _upload_document_to_path(
        file_path=file_path,
        storage_path=doc_storage,
        filetype=filetype,
        tags=tags,
        user_id=user_ctx.user_id,
        library_id=library_id,
        user_base_path=base_path,
        published_at=published_at,
    )

    if result.get("status") == "success":
        lib_meta_file = f"{lib_path}/library.json"
        lib_meta = {}

        if os.path.exists(lib_meta_file):
            with open(lib_meta_file, "r", encoding="utf-8") as f:
                try:
                    lib_meta = json.load(f)
                except Exception:
                    lib_meta = {}

        lib_meta = _ensure_library_meta_stats(lib_meta)

        added_chunks = int(result.get("raw", {}).get("chunks", 0) or 0)
        lib_meta["stats"]["doc_count"] = int(lib_meta["stats"].get("doc_count", 0) or 0) + 1
        lib_meta["stats"]["total_chunks"] = int(lib_meta["stats"].get("total_chunks", 0) or 0) + added_chunks
        lib_meta["doc_count"] = lib_meta["stats"]["doc_count"]

        now_iso = _utc_now_iso()
        lib_meta["updated_at"] = now_iso
        lib_meta["last_updated"] = now_iso

        with open(lib_meta_file, "w", encoding="utf-8") as f:
            json.dump(lib_meta, f, indent=2, ensure_ascii=False)

        lib_manager._update_global_config()

    return result


def _embedding_core(
    *,
    user_base_path: str,
    doc_id: str,
    library_id: str | None = None,
) -> dict:
    try:
        _limit_resources()
        print(f"[DEBUG] 开始 embedding：doc_id={doc_id}, library_id={library_id}")

        if not library_id:
            return {"status": "error", "message": "❌ library_id 必填"}

        db = get_doc_db_sqlite(user_base_path, library_id)
        chunks = db.get_chunks(doc_id)
        if not chunks:
            return {"status": "error", "message": "❌ chunks 为空"}

        print(f"[DEBUG] 加载了 {len(chunks)} 个 chunks")

        client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
        total_batches = (len(chunks) + EMBEDDING_BATCH_SIZE - 1) // EMBEDDING_BATCH_SIZE

        for batch_num in range(total_batches):
            start = batch_num * EMBEDDING_BATCH_SIZE
            end = min((batch_num + 1) * EMBEDDING_BATCH_SIZE, len(chunks))
            texts = [c["text"] for c in chunks[start:end]]

            print(f"[DEBUG] 处理批次 {batch_num + 1}/{total_batches}")

            embeddings_response = client.embeddings.create(
                model=EMBEDDING_MODEL,
                input=texts,
                dimensions=EMBEDDING_DIM,
            )

            chunk_ids: List[int] = []
            embs: List[np.ndarray] = []
            for i, item in enumerate(embeddings_response.data):
                chunk_id = start + i
                chunk_ids.append(chunk_id)
                embs.append(np.array(item.embedding, dtype="float32"))

            db.add_embeddings_bulk(
                doc_id=doc_id,
                chunk_ids=chunk_ids,
                embeddings=embs,
                model=EMBEDDING_MODEL,
                dim=EMBEDDING_DIM,
            )

            del embeddings_response
            gc.collect()

            if batch_num < total_batches - 1:
                time.sleep(BATCH_DELAY_SECONDS)

        db.update_embedding_status(doc_id, "completed")

        resolver = PathResolver(user_base_path, None)
        paths = resolver.resolve_doc_path(doc_id, library_id)
        if paths["status"] == "found":
            doc_path = paths["doc_path"]
            save_json(
                f"{doc_path}/embeddings.json",
                {
                    "total_chunks": len(chunks),
                    "status": "completed",
                    "completed_at": _utc_now_iso(),
                    "storage": "sqlite",
                },
            )

        print("[DEBUG] embedding 完成！")

        return {
            "status": "success",
            "message": (
                f"✅ Embedding 完成\n\n"
                f"总 chunks: {len(chunks)}\n\n"
                f"💡 现在可以使用搜索功能了！"
            ),
            "raw": {"doc_id": doc_id, "chunks": len(chunks)},
        }

    except Exception as e:
        import traceback
        print(f"[ERROR] Embedding 失败：{str(e)}")
        traceback.print_exc()
        return {"status": "error", "message": f"❌ Embedding 失败：{str(e)}"}


@auto_user_context
def nisb_doc_embedding(args: dict) -> dict:
    user_ctx = get_user_ctx()
    base_path = user_ctx.base
    doc_id = args.get("doc_id", "").strip()
    library_id = args.get("library_id", "").strip() or None

    if not doc_id:
        return {"status": "error", "message": "❌ doc_id 不能为空"}
    if not library_id:
        return {"status": "error", "message": "❌ library_id 必填"}

    return _embedding_core(
        user_base_path=base_path,
        doc_id=doc_id,
        library_id=library_id,
    )


@auto_user_context
def nisb_doc_stats(args: dict) -> dict:
    user_ctx = get_user_ctx()
    base_path = user_ctx.base
    library_id = args.get("library_id", "").strip() or None

    try:
        if library_id:
            library_path = Path(base_path) / "libraries" / library_id
            if not library_path.exists():
                return {"status": "error", "message": f"❌ 库不存在：{library_id}"}

            db = get_doc_db_sqlite(base_path, library_id)
            compat = db.ensure_schema_compatible()
            documents = db.list_documents(library_id=library_id, order_by="uploaded_at_desc")
            db_stats = db.get_statistics()

            simplified_documents = [
                {
                    "doc_id": d["doc_id"],
                    "filename": d["filename"],
                    "filetype": d["filetype"],
                    "chunks": int(d["total_chunks"]),
                    "created_at": d["uploaded_at"],
                    "published_at": d["published_at"] or d["uploaded_at"],
                }
                for d in documents
            ]

            return {
                "status": "success",
                "message": f"✅ 库 {library_id} 统计信息",
                "documents": simplified_documents,
                "raw": {
                    "stats": {
                        "doc_count": int(db_stats.get("total_docs", 0) or 0),
                        "total_chunks": int(db_stats.get("total_chunks", 0) or 0),
                        "embedded_docs": int(db_stats.get("embedded_docs", 0) or 0),
                        "embedding_coverage": db_stats.get("embedding_coverage", "0/0"),
                        "embedding_pct": db_stats.get("embedding_pct", 0),
                    },
                    "documents": simplified_documents,
                    "compat": compat,
                },
            }

        libraries_root = Path(base_path) / "libraries"
        if not libraries_root.exists():
            return {
                "status": "success",
                "message": "📊 暂无库",
                "raw": {"total_libraries": 0, "total_docs": 0, "total_chunks": 0},
            }

        total_libs = 0
        total_docs = 0
        total_chunks = 0

        for lib_dir in libraries_root.iterdir():
            if not lib_dir.is_dir():
                continue

            total_libs += 1
            library_id_iter = lib_dir.name
            db_path = lib_dir / "docs" / "doc_db.sqlite"

            if db_path.exists():
                db = get_doc_db_sqlite(base_path, library_id_iter)
                db.ensure_schema_compatible()
                db_stats = db.get_statistics()
                total_docs += int(db_stats.get("total_docs", 0) or 0)
                total_chunks += int(db_stats.get("total_chunks", 0) or 0)
                continue

            docs_dir = lib_dir / "docs"
            if docs_dir.exists():
                total_docs += len(list(docs_dir.glob("doc_*")))

        return {
            "status": "success",
            "message": (
                f"📊 库系统统计\n\n"
                f"📚 库: {total_libs} 个\n"
                f"📁 文档: {total_docs} 个\n"
                f"📦 Chunks: {total_chunks} 个"
            ),
            "raw": {
                "total_libraries": total_libs,
                "total_docs": total_docs,
                "total_chunks": total_chunks,
            },
        }

    except Exception as e:
        import traceback
        return {
            "status": "error",
            "message": f"❌ 统计失败：{str(e)}",
            "traceback": traceback.format_exc(),
        }
