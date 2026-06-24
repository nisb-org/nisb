#!/usr/bin/env python3
"""
库级文档上传 - 支持上传到指定库
Phase 7.0 新增【修复】路径冗余问题

本文件包含两类工具：
1) nisb_doc_upload_to_library        —— 原有库上传工具（只负责上传+统计，不自动向量化）
2) nisb_doc_upload_to_library_web    —— 新增 Web 适配工具（上传 + 向量化 一步完成）
"""

import os
import json
import tempfile
import base64
from datetime import datetime
from typing import Dict, Any

from core.user_context import auto_user_context, get_user_ctx
from tools.doc.core.upload_sqlite import _upload_document_to_path, _embedding_core
from tools.doc.core.path_resolver import PathResolver


def _ensure_library_exists(base_path: str, library_id: str) -> Dict[str, Any]:
    """
    检查库是否存在：判断 {base_path}/libraries/{library_id}/library.json 是否存在
    
    当前统一路径模型：所有工具都通过 @auto_user_context 获得相同的 base_path
    """
    lib_path = os.path.join(base_path, "libraries", library_id)
    meta_file = os.path.join(lib_path, "library.json")

    if not os.path.exists(lib_path):
        return {
            "status": "error",
            "message": f"❌ 库不存在：{library_id}（路径：{lib_path}）",
        }
    if not os.path.exists(meta_file):
        return {
            "status": "error",
            "message": f"❌ 库元信息文件不存在：{meta_file}",
        }

    return {"status": "success", "lib_path": lib_path, "meta_file": meta_file}


def _upload_to_library_core(
    *,
    user_id: str,
    base_path: str,
    file_path: str,
    library_id: str,
    filetype: str,
    tags: list[str] | list,
) -> Dict[str, Any]:
    """
    实际的上传+更新库元数据逻辑（不带 auto_user_context，供两个入口复用）
    
    ⭐ 关键：确保传入 library_id 给 _upload_document_to_path，让它写入库级 SQLite
    """
    # 检查库目录与元信息是否存在
    check = _ensure_library_exists(base_path, library_id)
    if check["status"] != "success":
        return check

    lib_path = check["lib_path"]
    meta_file = check["meta_file"]

    # 正确的库路径
    doc_storage = os.path.join(lib_path, "docs")
    os.makedirs(doc_storage, exist_ok=True)

    # ⭐ 核心：上传到库（写入库级 SQLite + 文档目录）
    result = _upload_document_to_path(
        file_path=file_path,
        storage_path=doc_storage,
        filetype=filetype,
        tags=tags,
        user_id=user_id,
        library_id=library_id,          # ⭐ 必须传这个参数
        user_base_path=base_path,
    )

    if result.get("status") != "success":
        return result

    # 更新库元数据
    doc_id = result["raw"]["doc_id"]
    chunks = result["raw"].get("chunks", 0)

    with open(meta_file, "r", encoding="utf-8") as f:
        lib_meta = json.load(f)

    # 兼容 stats 字段与旧字段
    stats = lib_meta.get("stats", {})
    if not isinstance(stats, dict):
        stats = {}
    stats["doc_count"] = stats.get("doc_count", lib_meta.get("doc_count", 0)) + 1
    stats["total_chunks"] = stats.get("total_chunks", 0) + chunks
    lib_meta["stats"] = stats

    # 旧字段同步更新
    lib_meta["doc_count"] = stats["doc_count"]
    lib_meta["updated_at"] = datetime.now().isoformat()
    lib_meta["last_updated"] = lib_meta.get("last_updated", lib_meta["updated_at"])

    with open(meta_file, "w", encoding="utf-8") as f:
        json.dump(lib_meta, f, indent=2, ensure_ascii=False)

    return {
        "status": "success",
        "message": (
            f"✅ 文档已上传到库：{library_id}\n\n"
            f"📋 文档ID: {doc_id}\n"
            f"分块数: {chunks}\n\n"
            f"💡 下一步：使用 nisb_doc_embedding 对其向量化"
        ),
        "raw": {
            "doc_id": doc_id,
            "library_id": library_id,
            "chunks": chunks,
        },
    }


@auto_user_context
def nisb_doc_upload_to_library(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    上传文档到指定库（原有实现，仅上传 + 更新库统计，不自动向量化）

    参数：
    {
        "file_path": "/path/to/file.pdf",
        "library_id": "philosophy",
        "filetype": "pdf",
        "tags": ["idealism", "berkeley"]
    }
    """
    user_ctx = get_user_ctx()
    base_path = user_ctx.base
    
    file_path = (args.get("file_path") or "").strip()
    library_id = (args.get("library_id") or "").strip()
    filetype = (args.get("filetype") or "").strip().lower()
    tags = args.get("tags", [])
    
    if not library_id:
        return {"status": "error", "message": "❌ library_id 不能为空"}
    if not file_path:
        return {"status": "error", "message": "❌ file_path 不能为空"}
    
    try:
        return _upload_to_library_core(
            user_id=user_ctx.user_id,
            base_path=base_path,
            file_path=file_path,
            library_id=library_id,
            filetype=filetype,
            tags=tags,
        )
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"status": "error", "message": f"❌ 上传失败：{str(e)}"}


@auto_user_context
def nisb_doc_upload_to_library_web(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    【新增】Web 一键上传工具：上传 + 向量化 一步完成

    支持两种调用方式：
    A. 直接传 file_path（服务器已有文件）
       {
         "file_path": "/path/to/file.txt",
         "library_id": "li",
         "filetype": "txt",
         "tags": [...]
       }

    B. 前端上传内容（推荐 Web 使用）
       {
         "library_id": "li",
         "content": "文件内容...",
         "filename": "xxx.txt",
         "filetype": "txt"   # 可选，缺省时从 filename 推断
       }
    """
    user_ctx = get_user_ctx()
    base_path = user_ctx.base

    file_path = (args.get("file_path") or "").strip()
    content = args.get("content", "")
    filename = (args.get("filename") or "").strip()
    library_id = (args.get("library_id") or "").strip()
    filetype = (args.get("filetype") or "").strip().lower()
    tags = args.get("tags", [])

    if not library_id:
        return {"status": "error", "message": "❌ library_id 不能为空"}

    temp_files: list[str] = []

    try:
        # 处理 content → 临时文件
        if not file_path:
            if not content or not filename:
                return {"status": "error", "message": "❌ 缺少 file_path 或 content+filename"}

            # 如为 data:URL，先解码
            if isinstance(content, str) and content.startswith("data:"):
                try:
                    _, b64_data = content.split(",", 1)
                    content = base64.b64decode(b64_data).decode("utf-8", errors="ignore")
                except Exception as e:
                    return {"status": "error", "message": f"❌ Base64 解码失败：{str(e)}"}

            # 推断 filetype
            if not filetype:
                if "." in filename:
                    filetype = filename.rsplit(".", 1)[-1].lower()
                else:
                    filetype = "txt"

            # 写入系统临时文件目录
            fd, temp_path = tempfile.mkstemp(
                suffix=f".{filetype}",
                prefix="nisb_upload_",
            )
            os.close(fd)
            with open(temp_path, "w", encoding="utf-8") as f:
                f.write(content)
            file_path = temp_path
            temp_files.append(temp_path)

        # 若仍未提供 filetype，则从路径推断
        if not filetype:
            if "." in file_path:
                filetype = file_path.rsplit(".", 1)[-1].lower()
            else:
                filetype = "txt"

        # ⭐ 使用已经解析好的 user_ctx 调用核心上传逻辑
        upload_res = _upload_to_library_core(
            user_id=user_ctx.user_id,
            base_path=base_path,
            file_path=file_path,
            library_id=library_id,
            filetype=filetype,
            tags=tags,
        )

        if upload_res.get("status") != "success":
            return upload_res

        raw = upload_res.get("raw", {}) or {}
        doc_id = raw.get("doc_id")
        chunks = raw.get("chunks", 0)

        if not doc_id:
            return {
                "status": "error",
                "message": "❌ 上传成功但未返回 doc_id",
                "raw": raw,
            }

        # ⭐ 立刻执行向量化，使搜索可用（库级 SQLite）
        emb_res = _embedding_core(
            user_base_path=base_path,
            doc_id=doc_id,
            library_id=library_id,
        )

        if emb_res.get("status") != "success":
            # 向量化失败时，上传已成功，但需要提示用户
            return {
                "status": "warning",
                "message": (
                    f"✅ 文档已上传到库：{library_id}\n\n"
                    f"📋 文档ID: {doc_id}\n"
                    f"分块数: {chunks}\n\n"
                    f"⚠️ 但向量化失败：{emb_res.get('message')}"
                ),
                "raw": {
                    "doc_id": doc_id,
                    "library_id": library_id,
                    "chunks": chunks,
                },
            }

        # 一切顺利：上传 + 向量化都成功
        return {
            "status": "success",
            "message": (
                f"✅ 文档已上传并完成索引：{library_id}\n\n"
                f"📋 文档ID: {doc_id}\n"
                f"分块数: {chunks}\n\n"
                f"🔎 现在可以在该库内使用搜索命中此文档内容"
            ),
            "raw": {
                "doc_id": doc_id,
                "library_id": library_id,
                "chunks": chunks,
            },
        }

    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"status": "error", "message": f"❌ 上传失败：{str(e)}"}

    finally:
        # 清理临时文件
        for p in temp_files:
            try:
                os.remove(p)
            except Exception:
                pass


