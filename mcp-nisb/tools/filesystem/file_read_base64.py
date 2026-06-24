# /opt/mcp-gateway/mcp-nisb/tools/filesystem/file_read_base64.py
"""
二进制安全读取文件：返回 base64 + mime + sha256
- filename: 相对 /data/users/{uid}/ 的相对路径（例：agent_files/books/传播学/mkdf.pdf）
- uid: 用户 id（字符串）
- max_bytes: 上限（默认 25MB）
"""

import os
import re
import base64
import hashlib
import mimetypes
from typing import Dict, Any, Union


USER_ROOT = "/data/users"


def _safe_uid(uid: str) -> str:
    s = str(uid or "").strip()
    if not s:
        return "nisb_default_user"
    # 仅允许安全字符，避免路径穿越
    if not re.fullmatch(r"[A-Za-z0-9_\-]{1,64}", s):
        return "nisb_default_user"
    return s


def _safe_rel_path(p: str) -> str:
    s = str(p or "").strip().replace("\\", "/")
    s = s.lstrip("/")  # 必须是相对路径

    if not s:
        raise ValueError("filename is required")

    # 禁止路径穿越
    parts = [x for x in s.split("/") if x not in ("", ".")]
    if any(x == ".." for x in parts):
        raise ValueError("invalid path: contains ..")

    rel = "/".join(parts)

    # 可选：限制必须在这些前缀下（更安全）。如果你确实需要放开，删掉这一段即可。
    allowed_prefixes = (
        "agent_files/",
        "storage/",
        "libraries/",
        "bookmarks/",
        "annotations/",
    )
    if not any(rel.startswith(px) for px in allowed_prefixes):
        raise ValueError(f"invalid path: must start with one of {allowed_prefixes}")

    return rel


def _resolve_under_user(uid: str, rel: str) -> str:
    base = os.path.join(USER_ROOT, uid)
    abs_path = os.path.normpath(os.path.join(base, rel))

    # 保障 abs_path 仍在 base 内
    base_norm = os.path.normpath(base) + os.sep
    abs_norm = os.path.normpath(abs_path)
    if not abs_norm.startswith(base_norm):
        raise ValueError("path escapes user root")

    return abs_norm


def _guess_mime(rel: str) -> str:
    # 常见修正
    low = str(rel or "").lower()
    if low.endswith(".pdf"):
        return "application/pdf"
    if low.endswith(".md"):
        return "text/markdown"
    if low.endswith(".jsonl"):
        return "application/json"
    if low.endswith(".txt"):
        return "text/plain"

    m, _ = mimetypes.guess_type(rel)
    return m or "application/octet-stream"


def nisb_file_read_base64(
    filename: Union[str, Dict[str, Any]],
    uid: str = "",
    max_bytes: int = 25 * 1024 * 1024
) -> Dict[str, Any]:
    """
    二进制安全读取文件：返回 base64 + mime + sha256
    - filename: 相对 /data/users/{uid}/ 的相对路径（例：agent_files/books/传播学/mkdf.pdf）
    - max_bytes: 上限（默认 25MB）
    """
    try:
        # ✅ 兼容 MCP：arguments dict 可能被作为第一个位置参数传入
        if isinstance(filename, dict):
            args = filename
            filename = args.get("filename", "")
            uid = args.get("uid", uid) or uid
            try:
                if "max_bytes" in args:
                    max_bytes = int(args.get("max_bytes"))
            except Exception:
                pass

        uid = _safe_uid(uid)
        rel = _safe_rel_path(str(filename or ""))
        abs_path = _resolve_under_user(uid, rel)

        if not os.path.exists(abs_path) or not os.path.isfile(abs_path):
            return {"success": False, "message": f"File not found: {rel}", "uid": uid, "path": rel}

        size = int(os.path.getsize(abs_path))
        if int(max_bytes or 0) > 0 and size > int(max_bytes):
            return {
                "success": False,
                "message": f"File too large: {size} bytes (max_bytes={int(max_bytes)})",
                "uid": uid,
                "path": rel,
                "bytes": size
            }

        with open(abs_path, "rb") as f:
            data = f.read()

        return {
            "success": True,
            "message": "File read.",
            "uid": uid,
            "path": rel,
            "bytes": len(data),
            "sha256": hashlib.sha256(data).hexdigest(),
            "mime": _guess_mime(rel),
            "data_base64": base64.b64encode(data).decode("ascii")
        }
    except Exception as e:
        return {"success": False, "message": f"read failed: {str(e)}"}

