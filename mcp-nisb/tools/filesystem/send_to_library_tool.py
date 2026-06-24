#!/usr/bin/env python3
"""
MCP 工具适配器：文件空间 -> 文档库 发送 & 入库状态查询
"""

import sys
import os
import time
import tempfile
import unicodedata

sys.path.insert(0, "/srv")

from core.user_context import auto_user_context, get_user_ctx
from .send_to_library_core import (
    fs_send_to_library_core,
    fs_send_dir_to_library_core,
)
from .fs_library_index_core import get_paths_library_status_batch
from .formal_response import ensure_formal_response


def _tool_result(args: dict, payload: dict, kind: str) -> dict:
    return ensure_formal_response(
        args,
        payload,
        default_kind=kind,
        keep_compat_fields=True,
    )


def _ensure_safe_rel_dir(rel_dir: str) -> str:
    rel_dir = (rel_dir or "").strip().strip("/")
    if not rel_dir:
        raise ValueError("target_dir 不能为空")
    if rel_dir.startswith("/") or ".." in rel_dir.split("/"):
        raise ValueError("target_dir 非法（不能包含 / 开头或 ..）")
    if any(seg.strip() == "" for seg in rel_dir.split("/")):
        raise ValueError("target_dir 非法（存在空目录段）")
    return rel_dir


def _sanitize_filename_visual(name: str) -> str:
    name = (name or "").strip()
    if not name:
        return "untitled.txt"

    name = unicodedata.normalize("NFKC", name)
    name = "".join(ch for ch in name if (ord(ch) >= 32 and ch != "\x7f"))

    trans = {
        "<": "‹",
        ">": "›",
        '"': "ˮ",
        "/": "∕",
        "\\": "＼",
        "|": "⏐",
        "?": "？",
        "*": "⁎",
        ":": "꞉",
    }
    for k, v in trans.items():
        name = name.replace(k, v)

    name = name.rstrip(" .")
    if not name:
        name = "untitled.txt"

    if len(name) > 200:
        root, ext = os.path.splitext(name)
        ext = ext[:16]
        name = root[: (200 - len(ext))] + ext

    return name


def _pick_unique_abs_path(abs_dir: str, filename: str) -> str:
    base, ext = os.path.splitext(filename)
    candidate = os.path.join(abs_dir, filename)
    if not os.path.exists(candidate):
        return candidate
    for i in range(1, 1000):
        fn = f"{base} ({i}){ext}"
        candidate = os.path.join(abs_dir, fn)
        if not os.path.exists(candidate):
            return candidate
    ts = int(time.time())
    return os.path.join(abs_dir, f"{base} ({ts}){ext}")


def _write_text_atomic(abs_dir: str, filename: str, content: str) -> str:
    os.makedirs(abs_dir, exist_ok=True)
    abs_target = _pick_unique_abs_path(abs_dir, filename)

    fd, tmp_path = tempfile.mkstemp(prefix=".tmp_upload_", dir=abs_dir)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
        os.replace(tmp_path, abs_target)
    except Exception:
        try:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        except Exception:
            pass
        raise

    return abs_target


@auto_user_context
def nisb_fs_send_to_library(args: dict) -> dict:
    user_ctx = get_user_ctx()
    base_path = user_ctx.base
    user_id = user_ctx.user_id

    request_id = str(args.get("request_id") or "").strip()
    source_path = (args.get("source_path") or "").strip()
    library_id = (args.get("library_id") or "").strip()
    mode = (args.get("mode") or "copy").strip().lower() or "copy"

    if not library_id:
        return _tool_result(args, {"status": "error", "message": "❌ library_id 不能为空"}, "fs_send_to_library")

    if source_path:
        return fs_send_to_library_core(
            base_path=base_path,
            user_id=user_id,
            source_path=source_path,
            library_id=library_id,
            mode=mode,
            request_id=request_id,
        )

    filename = (args.get("filename") or "").strip()
    content = args.get("content", None)
    target_dir = (args.get("target_dir") or "uploads/web").strip()

    if content is None:
        return _tool_result(
            args,
            {"status": "error", "message": "❌ 参数缺失：需要 source_path，或 filename+content"},
            "fs_send_to_library",
        )
    if not isinstance(content, str):
        return _tool_result(args, {"status": "error", "message": "❌ content 必须是字符串"}, "fs_send_to_library")
    if not filename:
        return _tool_result(args, {"status": "error", "message": "❌ filename 不能为空"}, "fs_send_to_library")

    if len(content.encode("utf-8", errors="ignore")) > 50 * 1024 * 1024:
        return _tool_result(args, {"status": "error", "message": "❌ 内容过大（限制 50MB）"}, "fs_send_to_library")

    try:
        rel_dir = _ensure_safe_rel_dir(target_dir)
    except Exception as e:
        return _tool_result(args, {"status": "error", "message": f"❌ target_dir 非法：{e}"}, "fs_send_to_library")

    safe_name = _sanitize_filename_visual(filename)

    abs_dir = os.path.join(base_path, rel_dir)
    abs_dir_real = os.path.realpath(abs_dir)
    base_real = os.path.realpath(base_path)
    if not abs_dir_real.startswith(base_real + os.sep) and abs_dir_real != base_real:
        return _tool_result(args, {"status": "error", "message": "❌ target_dir 越界（不在用户根目录内）"}, "fs_send_to_library")

    try:
        abs_written = _write_text_atomic(abs_dir_real, safe_name, content)
    except Exception as e:
        return _tool_result(args, {"status": "error", "message": f"❌ 写入临时文件失败：{e}"}, "fs_send_to_library")

    stored_filename = os.path.basename(abs_written)
    source_path2 = f"{rel_dir}/{stored_filename}"

    return fs_send_to_library_core(
        base_path=base_path,
        user_id=user_id,
        source_path=source_path2,
        library_id=library_id,
        mode=mode,
        request_id=request_id,
    )


@auto_user_context
def nisb_fs_send_dir_to_library(args: dict) -> dict:
    user_ctx = get_user_ctx()
    base_path = user_ctx.base
    user_id = user_ctx.user_id

    source_dir = (args.get("source_dir") or "").strip()
    library_id = (args.get("library_id") or "").strip()
    mode = (args.get("mode") or "copy").strip().lower() or "copy"

    return fs_send_dir_to_library_core(
        base_path=base_path,
        user_id=user_id,
        source_dir=source_dir,
        library_id=library_id,
        mode=mode,
        request_id=str(args.get("request_id") or "").strip(),
    )


@auto_user_context
def nisb_fs_library_status_batch(args: dict) -> dict:
    user_ctx = get_user_ctx()
    base_path = user_ctx.base

    paths = args.get("paths") or []
    if not isinstance(paths, list):
        return _tool_result(
            args,
            {"status": "error", "message": "❌ paths 参数必须是数组", "items": []},
            "fs_library_status_batch",
        )

    raw = get_paths_library_status_batch(
        base_path=base_path,
        paths=paths,
    )
    return _tool_result(args, raw, "fs_library_status_batch")

