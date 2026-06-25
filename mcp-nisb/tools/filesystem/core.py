"""
Core filesystem operations.

This module returns localized user-visible tool responses while preserving
protocol fields, file identifiers, paths, metadata, and evidence payloads.
"""

from __future__ import annotations

import json
import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

from .backup import create_backup, should_backup
from .config import (
    detect_category,
    ensure_directories,
    get_agent_files_path,
    get_base_path,
    get_log_path,
)
from .formal_response import ensure_formal_response
from .security import validate_filename, validate_path_safety
from .utils import (
    analyze_file,
    find_metadata_by_filename,
    generate_file_id,
    load_metadata,
    save_history,
    save_metadata,
)
from tools.i18n.backend_i18n import i18n_text, normalize_backend_locale
from tools.timeline import _append_timeline_activity


def _safe_args(args: dict | None) -> Dict[str, Any]:
    return args if isinstance(args, dict) else {}


def _locale(args: Dict[str, Any] | None) -> str:
    return normalize_backend_locale(_safe_args(args).get("locale"))


def _is_zh(args: Dict[str, Any] | None) -> bool:
    return _locale(args) == "zh-CN"


def _txt(args: Dict[str, Any] | None, en: str, zh: str) -> str:
    return i18n_text(_locale(args), {"en": en, "zh-CN": zh}, en)


def _fmt(args: Dict[str, Any] | None, en: str, zh: str, **kwargs: Any) -> str:
    return _txt(args, en, zh).format(**kwargs)


def _user_fields(args: Dict[str, Any]) -> tuple[str, Any, Any]:
    return (
        args.get("user_id", "user_001"),
        args.get("_librechat_email"),
        args.get("_librechat_name"),
    )


def _tool_entry(kind: str, data: Dict[str, Any]) -> Dict[str, Any]:
    return {"kind": kind, "data": data or {}}


def _normalize_payload(
    args: Dict[str, Any],
    payload: Dict[str, Any],
    default_success_response: str,
) -> Dict[str, Any]:
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
            response = message or _txt(args, "⚠️ Operation completed with warnings", "⚠️ 操作完成，但存在警告")
        else:
            response = message or _txt(args, "❌ Operation failed", "❌ 操作失败")

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


def _result(args: Dict[str, Any], payload: Dict[str, Any], kind: str, default_success_response: str) -> Dict[str, Any]:
    args = _safe_args(args)
    normalized = _normalize_payload(args, payload, default_success_response=default_success_response)
    return ensure_formal_response(
        args,
        normalized,
        default_kind=kind,
        keep_compat_fields=True,
    )


def _error(
    args: Dict[str, Any],
    kind: str,
    message: str,
    *,
    response: str = "",
    tool_data: Dict[str, Any] | None = None,
    **compat_fields: Any,
) -> Dict[str, Any]:
    args = _safe_args(args)
    payload = {
        "success": False,
        "status": "error",
        "message": message,
        "response": response or message,
        "tool_results": [_tool_entry(kind, tool_data or {})],
    }
    payload.update(compat_fields)
    return _result(
        args,
        payload,
        kind,
        default_success_response=_txt(args, "❌ Operation failed", "❌ 操作失败"),
    )


def _success(
    args: Dict[str, Any],
    kind: str,
    response: str,
    *,
    message: str = "",
    tool_data: Dict[str, Any] | None = None,
    **compat_fields: Any,
) -> Dict[str, Any]:
    args = _safe_args(args)
    payload = {
        "success": True,
        "status": "success",
        "message": message or response,
        "response": response,
        "tool_results": [_tool_entry(kind, tool_data or {})],
    }
    payload.update(compat_fields)
    return _result(args, payload, kind, default_success_response=response)


def _invalid_filename_message(args: Dict[str, Any], filename: Any) -> str:
    return _fmt(
        args,
        "❌ Invalid filename: {filename}",
        "❌ 文件名无效：{filename}",
        filename=filename or "",
    )


def _unsafe_path_message(args: Dict[str, Any], path: Any) -> str:
    return _fmt(
        args,
        "❌ Unsafe path: {path}",
        "❌ 路径不安全：{path}",
        path=path or "",
    )


def _backup_line(args: Dict[str, Any], storage_only: bool = True) -> str:
    if storage_only:
        return _txt(args, "🛡️ Automatic backup created (storage directory)", "🛡️ 已自动备份（storage目录）")
    return _txt(args, "🛡️ Automatic backup created", "🛡️ 已自动备份")


def _invalidate_search_hint_cache_after_write(base_path, filename: str) -> None:
    """文件写入成功后调用，清除搜索 hint cache，保证下次搜索能扫到新文件。"""
    try:
        from tools.search.index_sync_fs import invalidate_hint_cache_for_module
        from tools.search.index_sync import open_index
        from pathlib import Path

        bp = Path(str(base_path))
        conn, _ = open_index(bp)
        fn = str(filename or "").replace("\\", "/")
        if "documents/" in fn or fn.startswith("documents"):
            invalidate_hint_cache_for_module(conn, "doc")
        else:
            invalidate_hint_cache_for_module(conn, "files")
        conn.close()
    except Exception:
        pass  # 不阻塞文件写入，静默失败


def nisb_file_create(args: dict) -> Dict[str, Any]:
    args = _safe_args(args)
    user_id, email, name = _user_fields(args)

    try:
        from core.storage import ensure_user_directory

        ensure_user_directory(user_id, email, name)

        filename = args.get("filename")
        content = args.get("content", "")
        description = args.get("description", "")
        tags = args.get("tags", [])
        auto_categorize = args.get("auto_categorize", True)

        if content is None:
            content = ""
        if not isinstance(content, str):
            content = str(content)

        is_valid, error_msg = validate_filename(filename)
        if not is_valid:
            return _error(
                args,
                "nisb_file_create",
                _invalid_filename_message(args, filename),
                tool_data={"filename": filename, "validation_error": error_msg},
            )

        ensure_directories(user_id, email, name)
        base_path = get_base_path(user_id, email, name)
        file_id = generate_file_id(filename)

        if filename.startswith("storage/"):
            file_path = os.path.join(base_path, filename)
            category = "storage"
            print(f"[CREATE] Storage file: {filename}")
        elif filename.startswith("agent_files/"):
            file_path = os.path.join(base_path, filename)
            category = "agent_files"
            print(f"[CREATE] Agent file with full path: {filename}")
        else:
            agent_base = get_agent_files_path(user_id, email, name)
            if auto_categorize:
                category = detect_category(filename)
                file_path = os.path.join(agent_base, category, filename)
            else:
                category = "root"
                file_path = os.path.join(agent_base, filename)
            print(f"[CREATE] Agent file with auto category: {filename} -> {file_path}")

        is_safe, error_msg, _needs_protection = validate_path_safety(file_path, user_id, email, name)
        if not is_safe:
            return _error(
                args,
                "nisb_file_create",
                _unsafe_path_message(args, file_path),
                tool_data={"filename": filename, "file_path": file_path, "validation_error": error_msg},
            )

        backup_applied = False
        if should_backup(file_path, user_id, email, name):
            backup_result = create_backup(
                user_id,
                email,
                name,
                operation="file_create",
                affected_files=[file_path] if os.path.exists(file_path) else [],
                metadata={"filename": filename, "category": category},
            )
            backup_applied = bool(backup_result.get("success"))
            if backup_applied:
                print(f"[BACKUP] Before create: {backup_result.get('backup_id')}")

        if os.path.exists(file_path):
            return _error(
                args,
                "nisb_file_create",
                _fmt(
                    args,
                    "❌ File already exists: {filename}\n\n💡 Use nisb_file_update to update the file",
                    "❌ 文件已存在：{filename}\n\n💡 使用 nisb_file_update 更新文件",
                    filename=filename,
                ),
                tool_data={"filename": filename, "file_path": file_path},
            )

        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)

        print(f"[CREATE] File created: {file_path}")
        _invalidate_search_hint_cache_after_write(base_path, filename)

        _log_operation(
            user_id,
            email,
            name,
            "file_create",
            {
                "filename": filename,
                "file_id": file_id,
                "category": category,
                "size": len(content),
                "is_storage": should_backup(file_path, user_id, email, name),
            },
        )

        file_info = analyze_file(content, filename)
        now_iso = datetime.now().isoformat()
        metadata = {
            "file_id": file_id,
            "filename": filename,
            "file_path": file_path,
            "file_type": file_info["type"],
            "category": category,
            "description": description,
            "tags": tags,
            "created_at": now_iso,
            "updated_at": now_iso,
            "size_bytes": len(content.encode("utf-8")),
            "line_count": content.count("\n") + 1,
            "char_count": len(content),
            "analysis": file_info,
        }

        save_metadata(user_id, file_id, metadata, email, name)

        try:
            _append_timeline_activity(
                base_path=base_path,
                event={
                    "type": "document",
                    "date": metadata["created_at"],
                    "title": filename,
                    "path": filename,
                    "extra": {"action": "create", "category": category},
                },
            )
        except Exception:
            pass

        response = _fmt(
            args,
            "✅ File created successfully: {filename}",
            "✅ 文件创建成功：{filename}",
            filename=filename,
        )

        if _is_zh(args):
            message_lines = [
                "✅ 文件创建成功\n",
                f"📁 {filename}",
                f"📂 分类：{category}",
                f"📏 大小：{metadata['char_count']} 字符，{metadata['line_count']} 行",
                f"🆔 文件ID：{file_id}",
            ]
        else:
            message_lines = [
                "✅ File created successfully\n",
                f"📁 {filename}",
                f"📂 Category: {category}",
                f"📏 Size: {metadata['char_count']} characters, {metadata['line_count']} lines",
                f"🆔 File ID: {file_id}",
            ]

        if should_backup(file_path, user_id, email, name):
            message_lines.append(_backup_line(args, storage_only=True))

        message_lines.append("")

        if file_info.get("functions"):
            funcs = ", ".join(file_info["functions"][:5])
            message_lines.append(_fmt(args, "📦 Functions: {items}", "📦 函数：{items}", items=funcs))

        if file_info.get("imports"):
            imps = ", ".join(file_info["imports"][:5])
            message_lines.append(_fmt(args, "🔗 Dependencies: {items}", "🔗 依赖：{items}", items=imps))

        message_lines.append(
            _fmt(
                args,
                "\n💡 Read: nisb_file_read(file_id='{file_id}')",
                "\n💡 读取：nisb_file_read(file_id='{file_id}')",
                file_id=file_id,
            )
        )
        message = "\n".join(message_lines)

        return _success(
            args,
            "nisb_file_create",
            response,
            message=message,
            tool_data={
                "file_id": file_id,
                "filename": filename,
                "file_path": file_path,
                "category": category,
                "metadata": metadata,
                "backup_applied": backup_applied,
            },
            file_id=file_id,
            file_path=file_path,
        )

    except Exception as e:
        import traceback

        _log_operation(
            user_id,
            email,
            name,
            "file_create",
            {"error": str(e)},
            success=False,
        )
        return _error(
            args,
            "nisb_file_create",
            _fmt(
                args,
                "❌ Create failed: {error}\n\n{trace}",
                "❌ 创建失败：{error}\n\n{trace}",
                error=str(e),
                trace=traceback.format_exc(),
            ),
            response=_fmt(args, "❌ Create failed: {error}", "❌ 创建失败：{error}", error=str(e)),
            tool_data={"error": str(e)},
        )


def nisb_file_read(args: dict) -> Dict[str, Any]:
    args = _safe_args(args)
    user_id, email, name = _user_fields(args)

    try:
        file_id = args.get("file_id")
        filename = args.get("filename")

        import base64
        import mimetypes

        def is_image(filepath: str) -> bool:
            return str(filepath).lower().endswith((".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp", ".svg"))

        def is_pdf(filepath: str) -> bool:
            return str(filepath).lower().endswith(".pdf")

        def guess_mime(filepath: str) -> str:
            m, _ = mimetypes.guess_type(str(filepath))
            return m or "application/octet-stream"

        def read_base64(abs_path: str) -> str:
            with open(abs_path, "rb") as f:
                return base64.b64encode(f.read()).decode("ascii")

        if not file_id and not filename:
            return _error(
                args,
                "nisb_file_read",
                _txt(args, "❌ file_id or filename is required", "❌ 必须提供 file_id 或 filename"),
                tool_data={"file_id": file_id, "filename": filename},
            )

        metadata = None
        file_path = None

        if file_id:
            metadata = load_metadata(user_id, file_id, email, name)
            if not metadata:
                return _error(
                    args,
                    "nisb_file_read",
                    _fmt(args, "❌ File ID does not exist: {file_id}", "❌ 文件ID不存在：{file_id}", file_id=file_id),
                    tool_data={"file_id": file_id},
                )
            file_path = metadata.get("file_path")

        if not file_path and filename:
            base_path = get_base_path(user_id, email, name)
            direct_file_path = Path(base_path) / filename

            if direct_file_path.exists():
                file_path = str(direct_file_path)
                if not metadata:
                    metadata = {
                        "filename": filename,
                        "file_path": file_path,
                        "source": "direct",
                    }
            else:
                metadata = find_metadata_by_filename(user_id, filename, email, name)
                if not metadata:
                    return _error(
                        args,
                        "nisb_file_read",
                        _fmt(
                            args,
                            "❌ File does not exist: {filename}\n\n💡 To access the storage directory, use: storage/path/to/file",
                            "❌ 文件不存在：{filename}\n\n💡 如果要访问storage目录，请使用：storage/path/to/file",
                            filename=filename,
                        ),
                        tool_data={"filename": filename},
                    )
                file_path = metadata.get("file_path")

        if not file_path:
            return _error(
                args,
                "nisb_file_read",
                _txt(args, "❌ File path is empty because metadata is missing or arguments are invalid", "❌ 文件路径为空（元数据缺失或参数错误）"),
                tool_data={"file_id": file_id, "filename": filename},
            )

        is_safe, error_msg, _ = validate_path_safety(file_path, user_id, email, name)
        if not is_safe:
            return _error(
                args,
                "nisb_file_read",
                _unsafe_path_message(args, file_path),
                tool_data={"file_path": file_path, "validation_error": error_msg},
            )

        if not os.path.exists(file_path) or not os.path.isfile(file_path):
            return _error(
                args,
                "nisb_file_read",
                _fmt(args, "❌ File path does not exist: {file_path}", "❌ 文件路径不存在：{file_path}", file_path=file_path),
                tool_data={"file_path": file_path},
            )

        if is_image(file_path):
            try:
                image_data = read_base64(file_path)
                ext = Path(file_path).suffix.lower()
                out_metadata = {
                    **(metadata or {}),
                    "type": "image",
                    "mime_type": f"image/{ext[1:]}" if ext else "image/*",
                    "path": file_path,
                }
                fname = (metadata or {}).get("filename", filename)
                response = _fmt(args, "🖼️ Image file read: {filename}", "🖼️ 已读取图片文件：{filename}", filename=fname)
                return _success(
                    args,
                    "nisb_file_read",
                    response,
                    message=response,
                    tool_data={"content": image_data, "metadata": out_metadata},
                    content=image_data,
                    metadata=out_metadata,
                )
            except Exception as e:
                return _error(
                    args,
                    "nisb_file_read",
                    _fmt(args, "❌ Failed to read image: {error}", "❌ 读取图片失败：{error}", error=str(e)),
                    tool_data={"file_path": file_path, "error": str(e)},
                )

        if is_pdf(file_path):
            try:
                pdf_data = read_base64(file_path)
                out_metadata = {
                    **(metadata or {}),
                    "type": "pdf",
                    "mime_type": "application/pdf",
                    "path": file_path,
                }
                fname = (metadata or {}).get("filename", filename)
                response = _fmt(args, "📕 PDF file read: {filename}", "📕 已读取 PDF 文件：{filename}", filename=fname)
                return _success(
                    args,
                    "nisb_file_read",
                    response,
                    message=response,
                    tool_data={"content": pdf_data, "metadata": out_metadata},
                    content=pdf_data,
                    metadata=out_metadata,
                )
            except Exception as e:
                return _error(
                    args,
                    "nisb_file_read",
                    _fmt(args, "❌ Failed to read PDF: {error}", "❌ 读取 PDF 失败：{error}", error=str(e)),
                    tool_data={"file_path": file_path, "error": str(e)},
                )

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
        except UnicodeDecodeError:
            fname = (metadata or {}).get("filename", filename)
            msg = _fmt(
                args,
                "❌ Cannot read as UTF-8 text: {filename}\n💡 This file may be binary, such as PDF, EPUB, or ZIP. Use: nisb_file_read_base64",
                "❌ 无法以 UTF-8 文本读取：{filename}\n💡 该文件可能是二进制（例如 PDF/EPUB/ZIP）。请使用：nisb_file_read_base64",
                filename=fname,
            )
            return _error(
                args,
                "nisb_file_read",
                msg,
                response=_txt(args, "❌ Read failed: file is not UTF-8 text", "❌ 读取失败：文件不是 UTF-8 文本"),
                tool_data={"file_path": file_path, "reason": "not_utf8_text"},
            )

        try:
            _log_operation(
                user_id,
                email,
                name,
                "file_read",
                {
                    "file_id": (metadata or {}).get("file_id"),
                    "filename": (metadata or {}).get("filename", filename),
                    "source": (metadata or {}).get("source", "agent_files"),
                },
            )
        except Exception:
            pass

        fname = (metadata or {}).get("filename", filename) or ""
        out_metadata = {
            **(metadata or {}),
            "type": "text",
            "mime_type": guess_mime(file_path) or "text/plain",
            "path": file_path,
        }

        if _is_zh(args):
            message = "\n".join(
                [
                    f"📄 {fname}",
                    f"📏 {len(content)} 字符，{content.count(chr(10)) + 1} 行",
                ]
            )
        else:
            message = "\n".join(
                [
                    f"📄 {fname}",
                    f"📏 {len(content)} characters, {content.count(chr(10)) + 1} lines",
                ]
            )

        response = _fmt(args, "📄 File read: {filename}", "📄 已读取文件：{filename}", filename=fname)

        return _success(
            args,
            "nisb_file_read",
            response,
            message=message,
            tool_data={"content": content, "metadata": out_metadata},
            content=content,
            metadata=out_metadata,
        )

    except Exception as e:
        import traceback

        return _error(
            args,
            "nisb_file_read",
            _fmt(
                args,
                "❌ Read failed: {error}\n\n{trace}",
                "❌ 读取失败：{error}\n\n{trace}",
                error=str(e),
                trace=traceback.format_exc(),
            ),
            response=_fmt(args, "❌ Read failed: {error}", "❌ 读取失败：{error}", error=str(e)),
            tool_data={"error": str(e)},
        )


def nisb_file_update(args: dict) -> Dict[str, Any]:
    args = _safe_args(args)
    user_id, email, name = _user_fields(args)

    try:
        file_id = args.get("file_id")
        filename = args.get("filename")
        content = args.get("content")
        description = args.get("description")
        tags = args.get("tags")

        if file_id:
            metadata = load_metadata(user_id, file_id, email, name)
        elif filename:
            base_path = get_base_path(user_id, email, name)
            direct_file_path = Path(base_path) / filename
            if direct_file_path.exists():
                try:
                    backup_applied = False
                    if should_backup(str(direct_file_path), user_id, email, name):
                        backup_result = create_backup(
                            user_id,
                            email,
                            name,
                            operation="file_update",
                            affected_files=[str(direct_file_path)],
                            metadata={"filename": filename},
                        )
                        backup_applied = bool(backup_result.get("success"))

                    with open(direct_file_path, "w", encoding="utf-8") as f:
                        f.write("" if content is None else str(content))

                    print(f"[UPDATE] Direct update: {filename}")
                    _invalidate_search_hint_cache_after_write(base_path, filename)  # ← 新增

                    try:
                        _append_timeline_activity(
                            base_path=base_path,
                            event={
                                "type": "document",
                                "date": datetime.now().isoformat(),
                                "title": filename,
                                "path": filename,
                                "extra": {"action": "update"},
                            },
                        )
                    except Exception:
                        pass

                    response = _fmt(args, "✅ File updated: {filename}", "✅ 文件已更新：{filename}", filename=filename)
                    message = _fmt(args, "✅ File updated\n\n📁 {filename}", "✅ 文件已更新\n\n📁 {filename}", filename=filename)

                    return _success(
                        args,
                        "nisb_file_update",
                        response,
                        message=message,
                        tool_data={
                            "filename": filename,
                            "file_path": str(direct_file_path),
                            "updated_fields": {"content": True, "description": False, "tags": False},
                            "backup_applied": backup_applied,
                            "source": "direct",
                        },
                    )
                except Exception as e:
                    return _error(
                        args,
                        "nisb_file_update",
                        _fmt(args, "❌ Update failed: {error}", "❌ 更新失败：{error}", error=str(e)),
                        tool_data={"filename": filename, "error": str(e)},
                    )
            metadata = find_metadata_by_filename(user_id, filename, email, name)
        else:
            return _error(
                args,
                "nisb_file_update",
                _txt(args, "❌ file_id or filename is required", "❌ 必须提供 file_id 或 filename"),
                tool_data={"file_id": file_id, "filename": filename},
            )

        if not metadata:
            return _error(
                args,
                "nisb_file_update",
                _txt(args, "❌ File does not exist", "❌ 文件不存在"),
                tool_data={"file_id": file_id, "filename": filename},
            )

        file_path = metadata["file_path"]
        is_safe, error_msg, _needs_protection = validate_path_safety(file_path, user_id, email, name)
        if not is_safe:
            return _error(
                args,
                "nisb_file_update",
                _unsafe_path_message(args, file_path),
                tool_data={"file_path": file_path, "validation_error": error_msg},
            )

        backup_applied = False
        if should_backup(file_path, user_id, email, name) and os.path.exists(file_path):
            backup_result = create_backup(
                user_id,
                email,
                name,
                operation="file_update",
                affected_files=[file_path],
                metadata={
                    "filename": metadata["filename"],
                    "file_id": metadata["file_id"],
                },
            )
            backup_applied = bool(backup_result.get("success"))
            if backup_applied:
                print(f"[BACKUP] Before update: {backup_result.get('backup_id')}")

        if content is not None:
            with open(file_path, "r", encoding="utf-8") as f:
                old_content = f.read()
            save_history(user_id, metadata["file_id"], old_content, email, name)
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(str(content))
            _invalidate_search_hint_cache_after_write(  # ← 新增
                get_base_path(user_id, email, name), metadata["filename"]
            )
            metadata["size_bytes"] = len(str(content).encode("utf-8"))
            metadata["line_count"] = str(content).count("\n") + 1
            metadata["char_count"] = len(str(content))
            metadata["analysis"] = analyze_file(str(content), metadata["filename"])

        if description is not None:
            metadata["description"] = description
        if tags is not None:
            metadata["tags"] = tags

        metadata["updated_at"] = datetime.now().isoformat()
        save_metadata(user_id, metadata["file_id"], metadata, email, name)

        updated_fields = {
            "content": content is not None,
            "description": description is not None,
            "tags": tags is not None,
        }

        _log_operation(
            user_id,
            email,
            name,
            "file_update",
            {
                "file_id": metadata["file_id"],
                "filename": metadata["filename"],
                "updated_fields": updated_fields,
                "is_storage": should_backup(file_path, user_id, email, name),
            },
        )

        try:
            _append_timeline_activity(
                base_path=get_base_path(user_id, email, name),
                event={
                    "type": "document",
                    "date": metadata["updated_at"],
                    "title": metadata["filename"],
                    "path": metadata["filename"],
                    "extra": {"action": "update"},
                },
            )
        except Exception:
            pass

        if _is_zh(args):
            message = f"✅ 文件更新成功\n\n📁 {metadata['filename']}\n"
            if content is not None:
                message += f"📏 新大小：{metadata['char_count']} 字符\n"
        else:
            message = f"✅ File updated successfully\n\n📁 {metadata['filename']}\n"
            if content is not None:
                message += f"📏 New size: {metadata['char_count']} characters\n"

        if should_backup(file_path, user_id, email, name):
            message += _backup_line(args, storage_only=True) + "\n"

        response = _fmt(args, "✅ File updated: {filename}", "✅ 文件已更新：{filename}", filename=metadata["filename"])
        return _success(
            args,
            "nisb_file_update",
            response,
            message=message,
            tool_data={
                "file_id": metadata["file_id"],
                "filename": metadata["filename"],
                "file_path": file_path,
                "updated_fields": updated_fields,
                "metadata": metadata,
                "backup_applied": backup_applied,
            },
        )

    except Exception as e:
        return _error(
            args,
            "nisb_file_update",
            _fmt(args, "❌ Update failed: {error}", "❌ 更新失败：{error}", error=str(e)),
            tool_data={"error": str(e)},
        )


def nisb_file_delete(args: dict) -> Dict[str, Any]:
    args = _safe_args(args)
    user_id, email, name = _user_fields(args)

    try:
        file_id = args.get("file_id")
        filename = args.get("filename")
        permanent = args.get("permanent", False)
        skip_backup = args.get("_skip_backup", False)

        if file_id:
            metadata = load_metadata(user_id, file_id, email, name)
        elif filename:
            metadata = find_metadata_by_filename(user_id, filename, email, name)
        else:
            return _error(
                args,
                "nisb_file_delete",
                _txt(args, "❌ file_id or filename is required", "❌ 必须提供 file_id 或 filename"),
                tool_data={"file_id": file_id, "filename": filename},
            )

        if not metadata:
            base_path = get_base_path(user_id, email, name)
            file_path = os.path.join(base_path, filename or "")

            if os.path.exists(file_path):
                try:
                    backup_applied = False
                    if not skip_backup and should_backup(file_path, user_id, email, name):
                        backup_result = create_backup(
                            user_id,
                            email,
                            name,
                            operation="file_delete",
                            affected_files=[file_path],
                            metadata={
                                "filename": filename,
                                "permanent": permanent,
                                "no_metadata": True,
                            },
                        )
                        backup_applied = bool(backup_result.get("success"))

                    os.remove(file_path)
                    print(f"[DELETE] Direct delete without metadata: {filename}")

                    _log_operation(
                        user_id,
                        email,
                        name,
                        "file_delete",
                        {
                            "filename": filename,
                            "permanent": True,
                            "no_metadata": True,
                        },
                    )

                    try:
                        _append_timeline_activity(
                            base_path=base_path,
                            event={
                                "type": "document",
                                "date": datetime.now().isoformat(),
                                "title": filename,
                                "path": filename,
                                "extra": {
                                    "action": "delete",
                                    "permanent": True,
                                    "no_metadata": True,
                                },
                            },
                        )
                    except Exception:
                        pass

                    response = _fmt(args, "✅ File deleted: {filename}", "✅ 文件已删除：{filename}", filename=filename)
                    message = _fmt(
                        args,
                        "✅ File deleted without metadata\n\n📁 {filename}",
                        "✅ 文件已删除（无元数据）\n\n📁 {filename}",
                        filename=filename,
                    )

                    return _success(
                        args,
                        "nisb_file_delete",
                        response,
                        message=message,
                        tool_data={
                            "filename": filename,
                            "file_path": file_path,
                            "permanent": True,
                            "no_metadata": True,
                            "backup_applied": backup_applied,
                        },
                    )

                except Exception as e:
                    return _error(
                        args,
                        "nisb_file_delete",
                        _fmt(args, "❌ Delete failed: {error}", "❌ 删除失败：{error}", error=str(e)),
                        tool_data={"filename": filename, "file_path": file_path, "error": str(e)},
                    )

            return _error(
                args,
                "nisb_file_delete",
                _fmt(args, "❌ File does not exist: {filename}", "❌ 文件不存在：{filename}", filename=filename),
                tool_data={"filename": filename},
            )

        file_path = metadata["file_path"]

        backup_applied = False
        if (
            not skip_backup
            and should_backup(file_path, user_id, email, name)
            and os.path.exists(file_path)
        ):
            backup_result = create_backup(
                user_id,
                email,
                name,
                operation="file_delete",
                affected_files=[file_path],
                metadata={
                    "filename": metadata["filename"],
                    "file_id": metadata["file_id"],
                    "permanent": permanent,
                },
            )
            backup_applied = bool(backup_result.get("success"))
            if backup_applied:
                print(f"[BACKUP] Before delete: {backup_result.get('backup_id')}")

        if os.path.exists(file_path):
            os.remove(file_path)

        _log_operation(
            user_id,
            email,
            name,
            "file_delete",
            {
                "file_id": metadata["file_id"],
                "filename": metadata["filename"],
                "permanent": permanent,
                "is_storage": should_backup(file_path, user_id, email, name),
                "skip_backup": skip_backup,
            },
        )

        deleted_at = datetime.now().isoformat()

        if permanent:
            base_agent_path = get_agent_files_path(user_id, email, name)
            meta_path = f"{base_agent_path}/.metadata/{metadata['file_id']}.json"
            if os.path.exists(meta_path):
                os.remove(meta_path)
            message = _fmt(
                args,
                "✅ File permanently deleted\n\n📁 {filename}",
                "✅ 文件已永久删除\n\n📁 {filename}",
                filename=metadata["filename"],
            )
        else:
            metadata["deleted_at"] = deleted_at
            metadata["deleted"] = True
            save_metadata(user_id, metadata["file_id"], metadata, email, name)
            message = _fmt(
                args,
                "✅ File deleted and can be restored\n\n📁 {filename}",
                "✅ 文件已删除（可恢复）\n\n📁 {filename}",
                filename=metadata["filename"],
            )

        if not skip_backup and should_backup(file_path, user_id, email, name):
            message += "\n" + _backup_line(args, storage_only=True)

        try:
            _append_timeline_activity(
                base_path=get_base_path(user_id, email, name),
                event={
                    "type": "document",
                    "date": deleted_at,
                    "title": metadata["filename"],
                    "path": metadata["filename"],
                    "extra": {
                        "action": "delete",
                        "permanent": permanent,
                    },
                },
            )
        except Exception:
            pass

        response = _fmt(args, "✅ File deleted: {filename}", "✅ 文件已删除：{filename}", filename=metadata["filename"])
        return _success(
            args,
            "nisb_file_delete",
            response,
            message=message,
            tool_data={
                "file_id": metadata["file_id"],
                "filename": metadata["filename"],
                "file_path": file_path,
                "permanent": permanent,
                "skip_backup": skip_backup,
                "backup_applied": backup_applied,
                "deleted_at": deleted_at,
            },
        )

    except Exception as e:
        return _error(
            args,
            "nisb_file_delete",
            _fmt(args, "❌ Delete failed: {error}", "❌ 删除失败：{error}", error=str(e)),
            tool_data={"error": str(e)},
        )


def nisb_file_move(args: dict) -> Dict[str, Any]:
    args = _safe_args(args)
    user_id, email, name = _user_fields(args)

    try:
        file_id = args.get("file_id")
        new_category = args.get("new_category")

        metadata = load_metadata(user_id, file_id, email, name)
        if not metadata:
            return _error(
                args,
                "nisb_file_move",
                _fmt(args, "❌ File ID does not exist: {file_id}", "❌ 文件ID不存在：{file_id}", file_id=file_id),
                tool_data={"file_id": file_id, "new_category": new_category},
            )

        old_path = metadata["file_path"]
        old_category = metadata.get("category")
        base_path = get_agent_files_path(user_id, email, name)
        new_path = os.path.join(base_path, new_category, metadata["filename"])

        backup_applied = False
        if should_backup(old_path, user_id, email, name):
            backup_result = create_backup(
                user_id,
                email,
                name,
                operation="file_move",
                affected_files=[old_path],
                metadata={
                    "filename": metadata["filename"],
                    "old_category": old_category,
                    "new_category": new_category,
                },
            )
            backup_applied = bool(backup_result.get("success"))
            if backup_applied:
                print(f"[BACKUP] Before move: {backup_result.get('backup_id')}")

        os.makedirs(os.path.dirname(new_path), exist_ok=True)
        shutil.move(old_path, new_path)

        metadata["file_path"] = new_path
        metadata["category"] = new_category
        metadata["updated_at"] = datetime.now().isoformat()
        save_metadata(user_id, file_id, metadata, email, name)

        _log_operation(
            user_id,
            email,
            name,
            "file_move",
            {
                "file_id": file_id,
                "filename": metadata["filename"],
                "old_category": old_category,
                "new_category": new_category,
            },
        )

        if _is_zh(args):
            message = f"✅ 文件已移动\n\n📁 {metadata['filename']}\n到：{new_category}"
        else:
            message = f"✅ File moved\n\n📁 {metadata['filename']}\nTo: {new_category}"

        if should_backup(new_path, user_id, email, name):
            message += "\n" + _backup_line(args, storage_only=False)

        response = _fmt(args, "✅ File moved: {filename}", "✅ 文件已移动：{filename}", filename=metadata["filename"])
        return _success(
            args,
            "nisb_file_move",
            response,
            message=message,
            tool_data={
                "file_id": file_id,
                "filename": metadata["filename"],
                "old_path": old_path,
                "new_path": new_path,
                "old_category": old_category,
                "new_category": new_category,
                "backup_applied": backup_applied,
            },
        )

    except Exception as e:
        return _error(
            args,
            "nisb_file_move",
            _fmt(args, "❌ Move failed: {error}", "❌ 移动失败：{error}", error=str(e)),
            tool_data={"error": str(e)},
        )


def nisb_file_move_path(args: dict) -> Dict[str, Any]:
    args = _safe_args(args)
    user_id, email, name = _user_fields(args)

    try:
        old_path_rel = args.get("old_path")
        new_path_rel = args.get("new_path")
        if not old_path_rel or not new_path_rel:
            return _error(
                args,
                "nisb_file_move_path",
                _txt(args, "❌ Missing arguments: old_path and new_path are required", "❌ 参数缺失：old_path 和 new_path 必须提供"),
                tool_data={"old_path": old_path_rel, "new_path": new_path_rel},
            )

        base_path = get_base_path(user_id, email, name)
        src_abs = os.path.join(base_path, old_path_rel)
        dst_abs = os.path.join(base_path, new_path_rel)

        if not os.path.exists(src_abs):
            return _error(
                args,
                "nisb_file_move_path",
                _fmt(args, "❌ Source path does not exist: {path}", "❌ 源路径不存在：{path}", path=old_path_rel),
                tool_data={"old_path": old_path_rel, "new_path": new_path_rel},
            )

        is_safe1, err1, _ = validate_path_safety(src_abs, user_id, email, name)
        if not is_safe1:
            return _error(
                args,
                "nisb_file_move_path",
                _unsafe_path_message(args, old_path_rel),
                tool_data={"old_path": old_path_rel, "new_path": new_path_rel, "validation_error": err1},
            )

        is_safe2, err2, _ = validate_path_safety(dst_abs, user_id, email, name)
        if not is_safe2:
            return _error(
                args,
                "nisb_file_move_path",
                _unsafe_path_message(args, new_path_rel),
                tool_data={"old_path": old_path_rel, "new_path": new_path_rel, "validation_error": err2},
            )

        os.makedirs(os.path.dirname(dst_abs), exist_ok=True)

        backup_applied = False
        if should_backup(src_abs, user_id, email, name):
            backup_result = create_backup(
                user_id,
                email,
                name,
                operation="file_move_path",
                affected_files=[src_abs],
                metadata={
                    "old_path": old_path_rel,
                    "new_path": new_path_rel,
                },
            )
            backup_applied = bool(backup_result.get("success"))
            if backup_applied:
                print(f"[BACKUP] Before path move: {backup_result.get('backup_id')}")

        shutil.move(src_abs, dst_abs)

        filename_leaf = os.path.basename(old_path_rel)
        meta = find_metadata_by_filename(user_id, filename_leaf, email, name)
        if meta:
            meta["file_path"] = dst_abs
            meta["updated_at"] = datetime.now().isoformat()
            save_metadata(user_id, meta["file_id"], meta, email, name)

        _log_operation(
            user_id,
            email,
            name,
            "file_move_path",
            {"old_path": old_path_rel, "new_path": new_path_rel},
        )

        response = _fmt(
            args,
            "✅ Moved: {old_path} -> {new_path}",
            "✅ 已移动：{old_path} → {new_path}",
            old_path=old_path_rel,
            new_path=new_path_rel,
        )
        return _success(
            args,
            "nisb_file_move_path",
            response,
            message=response,
            tool_data={
                "old_path": old_path_rel,
                "new_path": new_path_rel,
                "backup_applied": backup_applied,
            },
            old_path=old_path_rel,
            new_path=new_path_rel,
        )

    except Exception as e:
        return _error(
            args,
            "nisb_file_move_path",
            _fmt(args, "❌ Move failed: {error}", "❌ 移动失败：{error}", error=str(e)),
            tool_data={"error": str(e)},
        )


def nisb_file_copy(args: dict) -> Dict[str, Any]:
    args = _safe_args(args)
    user_id, email, name = _user_fields(args)

    try:
        file_id = args.get("file_id")
        new_filename = args.get("new_filename")

        metadata = load_metadata(user_id, file_id, email, name)
        if not metadata:
            return _error(
                args,
                "nisb_file_copy",
                _fmt(args, "❌ Source file does not exist: {file_id}", "❌ 源文件不存在：{file_id}", file_id=file_id),
                tool_data={"source_file_id": file_id, "new_filename": new_filename},
            )

        with open(metadata["file_path"], "r", encoding="utf-8") as f:
            content = f.read()

        create_args = {
            "user_id": user_id,
            "_librechat_email": email,
            "_librechat_name": name,
            "locale": _locale(args),
            "filename": new_filename,
            "content": content,
            "description": _fmt(
                args,
                "Copied from: {filename}",
                "复制自：{filename}",
                filename=metadata["filename"],
            ),
            "tags": metadata.get("tags", []),
        }

        create_res = nisb_file_create(create_args)
        ok = create_res.get("status") == "success" or create_res.get("success") is True
        if not ok:
            return _result(
                args,
                {
                    **create_res,
                    "tool_results": [
                        _tool_entry(
                            "nisb_file_copy",
                            {
                                "source_file_id": file_id,
                                "source_filename": metadata["filename"],
                                "new_filename": new_filename,
                                "create_result_status": create_res.get("status"),
                            },
                        )
                    ],
                },
                "nisb_file_copy",
                default_success_response=_txt(args, "✅ File copied", "✅ 文件已复制"),
            )

        if _is_zh(args):
            msg = f"✅ 文件已复制\n\n源：{metadata['filename']}\n新：{new_filename}"
        else:
            msg = f"✅ File copied\n\nSource: {metadata['filename']}\nNew: {new_filename}"

        _log_operation(
            user_id,
            email,
            name,
            "file_copy",
            {
                "source_file_id": file_id,
                "source_filename": metadata["filename"],
                "new_filename": new_filename,
                "new_file_id": create_res.get("file_id"),
            },
        )

        return _success(
            args,
            "nisb_file_copy",
            _fmt(args, "✅ File copied: {filename}", "✅ 文件已复制：{filename}", filename=new_filename),
            message=msg,
            tool_data={
                "source_file_id": file_id,
                "source_filename": metadata["filename"],
                "new_filename": new_filename,
                "new_file_id": create_res.get("file_id"),
                "new_file_path": create_res.get("file_path"),
            },
            file_id=create_res.get("file_id"),
            file_path=create_res.get("file_path"),
        )

    except Exception as e:
        return _error(
            args,
            "nisb_file_copy",
            _fmt(args, "❌ Copy failed: {error}", "❌ 复制失败：{error}", error=str(e)),
            tool_data={"error": str(e)},
        )


def nisb_file_rename(args: dict) -> Dict[str, Any]:
    args = _safe_args(args)
    user_id, email, name = _user_fields(args)

    try:
        old_path = args.get("old_path")
        new_name = args.get("new_name")

        if not old_path or not new_name:
            return _error(
                args,
                "nisb_file_rename",
                _txt(args, "❌ old_path and new_name are required", "❌ 必须提供 old_path 和 new_name"),
                tool_data={"old_path": old_path, "new_name": new_name},
            )

        is_valid, error_msg = validate_filename(new_name)
        if not is_valid:
            return _error(
                args,
                "nisb_file_rename",
                _invalid_filename_message(args, new_name),
                tool_data={"old_path": old_path, "new_name": new_name, "validation_error": error_msg},
            )

        base_path = get_base_path(user_id, email, name)
        old_full_path = Path(base_path) / old_path
        new_full_path = old_full_path.parent / new_name

        if not old_full_path.exists():
            return _error(
                args,
                "nisb_file_rename",
                _fmt(args, "❌ File does not exist: {path}", "❌ 文件不存在：{path}", path=old_path),
                tool_data={"old_path": old_path, "new_name": new_name},
            )

        if new_full_path.exists():
            return _error(
                args,
                "nisb_file_rename",
                _fmt(args, "❌ Filename already exists: {name}", "❌ 文件名已存在：{name}", name=new_name),
                tool_data={"old_path": old_path, "new_name": new_name},
            )

        is_safe1, error_msg1, _ = validate_path_safety(str(old_full_path), user_id, email, name)
        is_safe2, error_msg2, _ = validate_path_safety(str(new_full_path), user_id, email, name)

        if not is_safe1:
            return _error(
                args,
                "nisb_file_rename",
                _unsafe_path_message(args, old_path),
                tool_data={"old_path": old_path, "new_name": new_name, "validation_error": error_msg1},
            )
        if not is_safe2:
            return _error(
                args,
                "nisb_file_rename",
                _unsafe_path_message(args, new_name),
                tool_data={"old_path": old_path, "new_name": new_name, "validation_error": error_msg2},
            )

        backup_applied = False
        if should_backup(str(old_full_path), user_id, email, name):
            backup_result = create_backup(
                user_id,
                email,
                name,
                operation="file_rename",
                affected_files=[str(old_full_path)],
                metadata={
                    "old_name": old_full_path.name,
                    "new_name": new_name,
                },
            )
            backup_applied = bool(backup_result.get("success"))

        old_full_path.rename(new_full_path)
        print(f"[RENAME] {old_path} -> {new_name}")

        new_rel_path = str(new_full_path.relative_to(base_path))

        _log_operation(
            user_id,
            email,
            name,
            "file_rename",
            {
                "old_path": old_path,
                "new_name": new_name,
                "new_path": new_rel_path,
            },
        )

        try:
            _append_timeline_activity(
                base_path=base_path,
                event={
                    "type": "document",
                    "date": datetime.now().isoformat(),
                    "title": new_name,
                    "path": new_rel_path,
                    "extra": {"action": "rename", "old_path": old_path},
                },
            )
        except Exception:
            pass

        if _is_zh(args):
            msg = f"✅ 文件已重命名\n\n{old_full_path.name} → {new_name}"
        else:
            msg = f"✅ File renamed\n\n{old_full_path.name} -> {new_name}"

        return _success(
            args,
            "nisb_file_rename",
            _fmt(args, "✅ File renamed: {name}", "✅ 文件已重命名：{name}", name=new_name),
            message=msg,
            tool_data={
                "old_path": old_path,
                "new_name": new_name,
                "new_path": new_rel_path,
                "backup_applied": backup_applied,
            },
            new_path=new_rel_path,
        )

    except Exception as e:
        import traceback

        return _error(
            args,
            "nisb_file_rename",
            _fmt(
                args,
                "❌ Rename failed: {error}\n\n{trace}",
                "❌ 重命名失败：{error}\n\n{trace}",
                error=str(e),
                trace=traceback.format_exc(),
            ),
            response=_fmt(args, "❌ Rename failed: {error}", "❌ 重命名失败：{error}", error=str(e)),
            tool_data={"error": str(e)},
        )


def nisb_dir_delete(args: dict) -> Dict[str, Any]:
    args = _safe_args(args)
    user_id, email, name = _user_fields(args)

    try:
        path_rel = args.get("path")
        recursive = bool(args.get("recursive", False))

        if not path_rel:
            return _error(
                args,
                "nisb_dir_delete",
                _txt(args, "❌ Missing argument: path is required", "❌ 参数缺失：path 必须提供"),
                tool_data={"path": path_rel, "recursive": recursive},
            )

        base_path = get_base_path(user_id, email, name)
        dir_abs = os.path.join(base_path, path_rel)

        if not os.path.exists(dir_abs):
            return _error(
                args,
                "nisb_dir_delete",
                _fmt(args, "❌ Directory does not exist: {path}", "❌ 目录不存在：{path}", path=path_rel),
                tool_data={"path": path_rel, "recursive": recursive},
            )

        if not os.path.isdir(dir_abs):
            return _error(
                args,
                "nisb_dir_delete",
                _fmt(args, "❌ Not a directory: {path}", "❌ 不是目录：{path}", path=path_rel),
                tool_data={"path": path_rel, "recursive": recursive},
            )

        is_safe, err, _ = validate_path_safety(dir_abs, user_id, email, name)
        if not is_safe:
            return _error(
                args,
                "nisb_dir_delete",
                _unsafe_path_message(args, path_rel),
                tool_data={"path": path_rel, "recursive": recursive, "validation_error": err},
            )

        if not recursive:
            children = os.listdir(dir_abs)
            if children:
                return _result(
                    args,
                    {
                        "success": False,
                        "status": "error",
                        "message": "DIRECTORY_NOT_EMPTY",
                        "response": _fmt(
                            args,
                            "❌ Directory is not empty and cannot be deleted directly: {path}",
                            "❌ 目录非空，不能直接删除：{path}",
                            path=path_rel,
                        ),
                        "tool_results": [
                            _tool_entry(
                                "nisb_dir_delete",
                                {"path": path_rel, "recursive": False, "reason": "DIRECTORY_NOT_EMPTY"},
                            )
                        ],
                    },
                    "nisb_dir_delete",
                    default_success_response=_txt(args, "✅ Directory deleted", "✅ 目录已删除"),
                )
            os.rmdir(dir_abs)
        else:
            shutil.rmtree(dir_abs)

        _log_operation(
            user_id,
            email,
            name,
            "dir_delete",
            {"path": path_rel, "recursive": recursive},
        )

        response = _fmt(args, "✅ Directory deleted: {path}", "✅ 已删除目录：{path}", path=path_rel)
        return _success(
            args,
            "nisb_dir_delete",
            response,
            message=response,
            tool_data={"path": path_rel, "recursive": recursive},
            path=path_rel,
        )

    except Exception as e:
        return _error(
            args,
            "nisb_dir_delete",
            _fmt(args, "❌ Directory delete failed: {error}", "❌ 删除目录失败：{error}", error=str(e)),
            tool_data={"error": str(e)},
        )


def _log_operation(
    user_id: str,
    email: str,
    name: str,
    operation: str,
    data: dict,
    success: bool = True,
):
    try:
        log_path = get_log_path(user_id, email, name)
        os.makedirs(log_path, exist_ok=True)
        today = datetime.now().strftime("%Y-%m-%d")
        log_file = f"{log_path}/{today}.jsonl"
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "operation": operation,
            "user_id": user_id,
            "data": data,
            "status": "success" if success else "failed",
        }
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")
    except Exception as e:
        print(f"[WARN] Failed to write operation log: {str(e)}")

