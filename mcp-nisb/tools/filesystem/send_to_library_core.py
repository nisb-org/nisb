#!/usr/bin/env python3
"""
文件空间 -> 文档库 发送核心逻辑
正式字段优先 + legacy 兼容版
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, Any, List

from tools.doc.lib_upload import _upload_to_library_core
from tools.doc.core.upload_sqlite import _embedding_core

from .fs_library_index_core import record_fs_send_event
from .formal_response import ensure_formal_response


def _tool_entry(kind: str, data: Dict[str, Any]) -> Dict[str, Any]:
    return {"kind": kind, "data": data or {}}


def _normalize_payload(payload: Dict[str, Any], default_success_response: str) -> Dict[str, Any]:
    data = dict(payload or {})
    status = str(data.get("status") or "").strip().lower()
    if not status:
        if data.get("success") is True:
            status = "success"
        elif data.get("success") is False:
            status = "error"
        else:
            status = "success"

    response = str(data.get("response") or "").strip()
    message = str(data.get("message") or "").strip()

    if not response:
        if status == "success":
            response = message or default_success_response
        elif status == "warning":
            response = message or "⚠️ 操作完成，但存在警告"
        else:
            response = message or "❌ 操作失败"

    if not message:
        message = response

    tool_calls = data.get("tool_calls")
    if not isinstance(tool_calls, list):
        tool_calls = []

    tool_results = data.get("tool_results")
    if not isinstance(tool_results, list):
        tool_results = []

    data["status"] = status
    data["response"] = response
    data["message"] = message
    data["tool_calls"] = tool_calls
    data["tool_results"] = tool_results
    return data


def _result(request_id: str, payload: Dict[str, Any], kind: str, default_success_response: str) -> Dict[str, Any]:
    normalized = _normalize_payload(payload, default_success_response=default_success_response)
    return ensure_formal_response(
        {"request_id": request_id},
        normalized,
        default_kind=kind,
        keep_compat_fields=True,
    )


def _error(
    request_id: str,
    kind: str,
    message: str,
    *,
    tool_data: Dict[str, Any] | None = None,
    **compat: Any,
) -> Dict[str, Any]:
    payload = {
        "success": False,
        "status": "error",
        "response": str(message or "").strip(),
        "message": str(message or "").strip(),
        "tool_calls": [],
        "tool_results": [_tool_entry(kind, tool_data or {})],
    }
    payload.update(compat)
    return _result(request_id, payload, kind, default_success_response="❌ 操作失败")


def _warning(
    request_id: str,
    kind: str,
    response: str,
    *,
    message: str = "",
    tool_data: Dict[str, Any] | None = None,
    **compat: Any,
) -> Dict[str, Any]:
    payload = {
        "success": False,
        "status": "warning",
        "response": str(response or message or "").strip(),
        "message": str(message or response or "").strip(),
        "tool_calls": [],
        "tool_results": [_tool_entry(kind, tool_data or {})],
    }
    payload.update(compat)
    return _result(request_id, payload, kind, default_success_response=str(response or message or "⚠️ 操作完成"))


def _success(
    request_id: str,
    kind: str,
    response: str,
    *,
    message: str = "",
    tool_data: Dict[str, Any] | None = None,
    **compat: Any,
) -> Dict[str, Any]:
    payload = {
        "success": True,
        "status": "success",
        "response": str(response or message or "").strip(),
        "message": str(message or response or "").strip(),
        "tool_calls": [],
        "tool_results": [_tool_entry(kind, tool_data or {})],
    }
    payload.update(compat)
    return _result(request_id, payload, kind, default_success_response=str(response or message or "✅ 操作成功"))


def _resolve_source_file(base_path: str, source_path: str) -> Path | None:
    src = (source_path or "").strip()
    if not src:
        return None

    base = Path(base_path or "/data")
    cand_storage = base / "storage" / src
    cand_flat = base / src

    if cand_storage.exists() and cand_storage.is_file():
        return cand_storage
    if cand_flat.exists() and cand_flat.is_file():
        return cand_flat

    return None


def _resolve_source_dir(base_path: str, source_dir: str) -> Path | None:
    src = (source_dir or "").strip()
    if not src:
        return None

    base = Path(base_path or "/data")
    cand_storage = base / "storage" / src
    cand_flat = base / src

    if cand_storage.exists() and cand_storage.is_dir():
        return cand_storage
    if cand_flat.exists() and cand_flat.is_dir():
        return cand_flat

    return None


def _rel_path_under_base(base_path: str, abs_file: Path) -> str | None:
    base = Path(base_path or "/data")
    root_storage = base / "storage"
    root_flat = base

    try:
        if abs_file.is_relative_to(root_storage):
            return abs_file.relative_to(root_storage).as_posix()
        if abs_file.is_relative_to(root_flat):
            return abs_file.relative_to(root_flat).as_posix()
    except Exception:
        try:
            return abs_file.relative_to(root_storage).as_posix()
        except Exception:
            try:
                return abs_file.relative_to(root_flat).as_posix()
            except Exception:
                return None
    return None


def fs_send_to_library_core(
    base_path: str,
    user_id: str,
    source_path: str,
    library_id: str,
    mode: str = "copy",
    request_id: str = "",
) -> Dict[str, Any]:
    source_path = (source_path or "").strip()
    library_id = (library_id or "").strip()
    mode = (mode or "copy").strip().lower() or "copy"

    if not source_path:
        return _error(
            request_id,
            "fs_send_to_library",
            "❌ source_path 必填",
            tool_data={"source_path": source_path, "library_id": library_id, "mode": mode},
        )

    if not library_id:
        return _error(
            request_id,
            "fs_send_to_library",
            "❌ library_id 必填",
            tool_data={"source_path": source_path, "library_id": library_id, "mode": mode},
        )

    abs_file = _resolve_source_file(base_path, source_path)
    if abs_file is None:
        base = Path(base_path or "/data")
        cand_storage = str(base / "storage" / source_path)
        cand_flat = str(base / source_path)
        return _error(
            request_id,
            "fs_send_to_library",
            "❌ 源文件不存在：\n" f"  - {cand_storage}\n" f"  - {cand_flat}",
            tool_data={
                "source_path": source_path,
                "library_id": library_id,
                "mode": mode,
                "candidates": [cand_storage, cand_flat],
            },
        )

    if abs_file.is_dir():
        return _error(
            request_id,
            "fs_send_to_library",
            "❌ 暂不支持直接发送目录，请选择单个文件",
            tool_data={"source_path": source_path, "library_id": library_id, "mode": mode},
        )

    suffix = abs_file.suffix.lower().lstrip(".")
    filetype = suffix or "txt"

    upload_res = _upload_to_library_core(
        user_id=user_id,
        base_path=base_path,
        file_path=str(abs_file),
        library_id=library_id,
        filetype=filetype,
        tags=[],
    )

    if upload_res.get("status") != "success":
        return _error(
            request_id,
            "fs_send_to_library",
            str(upload_res.get("message") or "❌ 上传到库失败"),
            tool_data={
                "source_path": source_path,
                "library_id": library_id,
                "mode": mode,
                "upload_status": upload_res.get("status"),
            },
        )

    raw = upload_res.get("raw", {}) or {}
    doc_id = raw.get("doc_id")
    chunks = raw.get("chunks", 0)

    if not doc_id:
        return _error(
            request_id,
            "fs_send_to_library",
            "❌ 上传成功但未返回 doc_id",
            tool_data={
                "source_path": source_path,
                "library_id": library_id,
                "mode": mode,
                "chunks": chunks,
            },
        )

    emb_res = _embedding_core(
        user_base_path=base_path,
        doc_id=doc_id,
        library_id=library_id,
    )

    delete_warning = None
    if mode == "move":
        try:
            os.remove(abs_file)
        except Exception as e:
            delete_warning = f"但删除源文件失败：{e}"

    try:
        record_fs_send_event(
            base_path=base_path,
            user_id=user_id,
            source_path=source_path,
            library_id=library_id,
            doc_id=doc_id,
            mode=mode,
        )
    except Exception:
        pass

    result_data = {
        "doc_id": doc_id,
        "library_id": library_id,
        "chunks": chunks,
        "mode": mode,
        "source_path": source_path,
        "filetype": filetype,
        "embedding_status": emb_res.get("status"),
        "delete_warning": delete_warning,
    }

    if emb_res.get("status") != "success":
        response = f"⚠️ 文档已发送到库，但索引未完全完成：{library_id}"
        msg = (
            f"✅ 文档已发送到库：{library_id}\n\n"
            f"📋 文档ID: {doc_id}\n"
            f"分块数: {chunks}\n\n"
            f"⚠️ 但向量化失败：{emb_res.get('message')}"
        )
        if delete_warning:
            msg += f"\n⚠️ {delete_warning}"
        return _warning(
            request_id,
            "fs_send_to_library",
            response,
            message=msg,
            tool_data=result_data,
        )

    response = f"✅ 文档已上传并完成索引：{library_id}"
    msg = (
        f"✅ 文档已上传并完成索引：{library_id}\n\n"
        f"📋 文档ID: {doc_id}\n"
        f"分块数: {chunks}\n\n"
        f"🔎 现在可以在该库内使用搜索和分析命中此文档内容"
    )
    if delete_warning:
        msg += f"\n⚠️ {delete_warning}"

    return _success(
        request_id,
        "fs_send_to_library",
        response,
        message=msg,
        tool_data=result_data,
    )


def fs_send_dir_to_library_core(
    base_path: str,
    user_id: str,
    source_dir: str,
    library_id: str,
    mode: str = "copy",
    request_id: str = "",
) -> Dict[str, Any]:
    source_dir = (source_dir or "").strip()
    library_id = (library_id or "").strip()
    mode = (mode or "copy").strip().lower() or "copy"

    if not source_dir:
        return _error(
            request_id,
            "fs_send_dir_to_library",
            "❌ source_dir 必填",
            tool_data={"source_dir": source_dir, "library_id": library_id, "mode": mode},
        )

    if not library_id:
        return _error(
            request_id,
            "fs_send_dir_to_library",
            "❌ library_id 必填",
            tool_data={"source_dir": source_dir, "library_id": library_id, "mode": mode},
        )

    abs_dir = _resolve_source_dir(base_path, source_dir)
    if abs_dir is None:
        base = Path(base_path or "/data")
        cand_storage = str(base / "storage" / source_dir)
        cand_flat = str(base / source_dir)
        return _error(
            request_id,
            "fs_send_dir_to_library",
            "❌ 源目录不存在：\n" f"  - {cand_storage}\n" f"  - {cand_flat}",
            tool_data={
                "source_dir": source_dir,
                "library_id": library_id,
                "mode": mode,
                "candidates": [cand_storage, cand_flat],
            },
        )

    if not abs_dir.is_dir():
        return _error(
            request_id,
            "fs_send_dir_to_library",
            "❌ 目标不是目录，请选择目录后再重试",
            tool_data={"source_dir": source_dir, "library_id": library_id, "mode": mode},
        )

    total_files = 0
    success_count = 0
    failed_count = 0
    warning_count = 0
    errors: List[str] = []
    docs: List[Dict[str, Any]] = []

    for root, _dirs, files in os.walk(abs_dir):
        for name in files:
            total_files += 1
            abs_file = Path(root) / name
            rel_path = _rel_path_under_base(base_path, abs_file)

            if not rel_path:
                failed_count += 1
                errors.append(f"无法解析相对路径: {abs_file}")
                continue

            try:
                res = fs_send_to_library_core(
                    base_path=base_path,
                    user_id=user_id,
                    source_path=rel_path,
                    library_id=library_id,
                    mode=mode,
                    request_id=request_id,
                )
                status = str(res.get("status") or "").strip().lower()
                tool_results = res.get("tool_results") or []
                first_data = {}
                if isinstance(tool_results, list) and tool_results:
                    first = tool_results[0] or {}
                    if isinstance(first, dict):
                        first_data = first.get("data") or {}

                if status == "success":
                    success_count += 1
                    docs.append(
                        {
                            "source_path": rel_path,
                            "doc_id": first_data.get("doc_id"),
                            "chunks": first_data.get("chunks"),
                            "embedding_status": first_data.get("embedding_status"),
                        }
                    )
                elif status == "warning":
                    warning_count += 1
                    docs.append(
                        {
                            "source_path": rel_path,
                            "doc_id": first_data.get("doc_id"),
                            "chunks": first_data.get("chunks"),
                            "embedding_status": first_data.get("embedding_status"),
                        }
                    )
                    errors.append(f"{rel_path}: {res.get('message')}")
                else:
                    failed_count += 1
                    errors.append(f"{rel_path}: {res.get('message')}")
            except Exception as e:
                failed_count += 1
                errors.append(f"{rel_path}: {e}")

    result_data = {
        "total_files": total_files,
        "success": success_count,
        "warning": warning_count,
        "failed": failed_count,
        "mode": mode,
        "source_dir": source_dir,
        "library_id": library_id,
        "errors_preview": errors[:10],
        "docs": docs[:50],
    }

    if total_files == 0:
        return _error(
            request_id,
            "fs_send_dir_to_library",
            "❌ 目录下没有可发送的文件",
            tool_data=result_data,
        )

    if failed_count == 0 and warning_count == 0:
        response = f"✅ 目录发送完成：{source_dir}"
        msg = (
            f"✅ 目录发送完成：{source_dir}\n\n"
            f"总文件数：{total_files}\n"
            f"成功：{success_count}\n"
            f"模式：{mode}"
        )
        return _success(
            request_id,
            "fs_send_dir_to_library",
            response,
            message=msg,
            tool_data=result_data,
        )

    if success_count == 0 and warning_count == 0:
        response = f"❌ 目录发送失败：{source_dir}"
        msg = (
            f"❌ 目录发送失败：{source_dir}\n\n"
            f"总文件数：{total_files}\n"
            f"全部失败，请检查错误信息。"
        )
        if errors:
            msg += f"\n\n部分错误示例：\n{chr(10).join(errors[:10])}"
        return _error(
            request_id,
            "fs_send_dir_to_library",
            msg,
            tool_data=result_data,
        )

    response = f"⚠️ 目录发送部分成功：{source_dir}"
    msg = (
        f"⚠️ 目录发送部分成功：{source_dir}\n\n"
        f"总文件数：{total_files}\n"
        f"成功：{success_count}\n"
        f"警告：{warning_count}\n"
        f"失败：{failed_count}\n"
        f"模式：{mode}"
    )
    if errors:
        msg += f"\n\n部分错误示例：\n{chr(10).join(errors[:10])}"

    return _warning(
        request_id,
        "fs_send_dir_to_library",
        response,
        message=msg,
        tool_data=result_data,
    )

