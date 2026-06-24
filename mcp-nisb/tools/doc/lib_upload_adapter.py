#!/usr/bin/env python3
"""
库上传一键完成（上传→embedding）适配器
不改底层，仅做“content→临时文件→调用已有工具”的薄封装
"""
import os
import sys
import base64
import tempfile
from pathlib import Path

sys.path.insert(0, '/srv')

from core.user_context import auto_user_context, get_user_ctx  # 复用既有用户上下文装饰器与获取函数


def _doc_upload_to_library_impl(base_path: str, user_id: str, args: dict) -> dict:
    """
    实际的“上传→向量化”实现逻辑。

    参数：
      - base_path: 当前用户根目录（暂时未直接使用，预留给后续扩展）
      - user_id: 当前用户 ID（暂时未直接使用，预留）
      - args: 来自前端或其他调用方的参数 dict
    支持两种模式：
      A. file_path + library_id + filetype
      B. content + filename + library_id（自动落临时文件并推断 filetype）
    统一执行：
      1) nisb_doc_upload（入库与统计）
      2) nisb_doc_embedding（生成向量，库内搜索可用）
    """
    file_path = (args.get("file_path") or "").strip()
    content = args.get("content", "")
    filename = (args.get("filename") or "").strip()
    library_id = (args.get("library_id") or "").strip()
    filetype = (args.get("filetype") or "").strip().lower()

    if not library_id:
        return {"status": "error", "message": "❌ library_id 必填"}

    temp_file = None
    cleanup = []

    try:
        # 当未提供 file_path 时，兼容前端 content+filename 上送
        if not file_path:
            if not content or not filename:
                return {"status": "error", "message": "❌ 缺少 file_path 或 content+filename"}
            # 兼容 data: 前缀的 Base64 Data URL
            if content.startswith("data:"):
                try:
                    _, b64_data = content.split(",", 1)
                    content = base64.b64decode(b64_data).decode("utf-8", errors="ignore")
                except Exception as e:
                    return {"status": "error", "message": f"❌ Base64 解码失败：{str(e)}"}
            # 写临时文件（文本场景），确保底层仍走 file_path 流程
            suffix = "." + (filetype or (filename.split(".")[-1] if "." in filename else "txt"))
            fd, temp_file = tempfile.mkstemp(suffix=suffix)
            os.close(fd)
            with open(temp_file, "w", encoding="utf-8") as f:
                f.write(content)
            file_path = temp_file
            cleanup.append(temp_file)

        if not filetype:
            filetype = file_path.split(".")[-1].lower() if "." in file_path else "txt"

        # 延迟导入，避免与 tools/doc/doc.py 的相互引用导致循环导入
        from tools.doc.doc import nisb_doc_upload, nisb_doc_embedding

        # 1) 上传入库（SQLite 版）
        up_res = nisb_doc_upload({
            "file_path": file_path,
            "library_id": library_id,
            "filetype": filetype
        })
        if up_res.get("status") != "success":
            return up_res

        doc_id = up_res.get("raw", {}).get("doc_id") or up_res.get("doc_id")
        if not doc_id:
            return {"status": "error", "message": "❌ 上传成功但未返回 doc_id"}

        # 2) 向量化（使混合/语义检索立即可用）
        emb_res = nisb_doc_embedding({
            "doc_id": doc_id,
            "library_id": library_id
        })
        if emb_res.get("status") != "success":
            return {
                "status": "warning",
                "message": f"✅ 上传成功，但向量化失败：{emb_res.get('message')}",
                "raw": {"doc_id": doc_id, "library_id": library_id}
            }

        return {
            "status": "success",
            "message": (
                f"✅ 文档已上传并完成索引：{library_id}\n"
                f"📋 文档ID: {doc_id}\n"
                f"🔎 现在可在库内搜索到该文档内容"
            ),
            "raw": {"doc_id": doc_id, "library_id": library_id}
        }

    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"status": "error", "message": f"❌ 上传失败：{str(e)}"}

    finally:
        # 清理临时文件
        for p in cleanup:
            try:
                os.remove(p)
            except:
                pass


@auto_user_context
def nisb_doc_upload_to_library_v2(args: dict) -> dict:
    """
    HTTP API 模式入口：
    - 通过 auto_user_context + get_user_ctx() 拿到当前用户的 base_path / user_id
    - 然后委托给 _doc_upload_to_library_impl

    兼容原有逻辑，不影响已接好的 HTTP 网关。
    """
    user_ctx = get_user_ctx()
    base_path = user_ctx.base
    user_id = user_ctx.user_id

    # 目前实现里暂未直接使用 base_path/user_id，但预留传入，方便将来扩展
    return _doc_upload_to_library_impl(base_path, user_id, args)

