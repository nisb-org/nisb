#!/usr/bin/env python3
"""
Directory move and rename tool.

Only agent_files/ scope is allowed. User-visible tool envelope text is localized
by UI locale, while paths, protocol fields, and audit metadata remain unchanged.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any, Dict

from tools.i18n.backend_i18n import i18n_text, normalize_backend_locale

from .backup import create_backup, should_backup
from .config import get_base_path
from .security import validate_path_safety


_SLASH_RE = re.compile(r"/+")
_AGENT_SCOPE_PREFIX = "agent_files"


def _safe_args(args: Dict[str, Any] | None) -> Dict[str, Any]:
    return args if isinstance(args, dict) else {}


def _locale(args: Dict[str, Any] | None) -> str:
    return normalize_backend_locale(_safe_args(args).get("locale"))


def _txt(args: Dict[str, Any] | None, en: str, zh: str) -> str:
    return i18n_text(_locale(args), {"en": en, "zh-CN": zh}, en)


def _fmt(args: Dict[str, Any] | None, en: str, zh: str, **kwargs: Any) -> str:
    return _txt(args, en, zh).format(**kwargs)


def _tool_entry(kind: str, data: Dict[str, Any]) -> Dict[str, Any]:
    return {"kind": kind, "data": data or {}}


def _ok(
    args: Dict[str, Any],
    message: str,
    *,
    tool_data: Dict[str, Any] | None = None,
    **fields: Any,
) -> Dict[str, Any]:
    kind = "nisb_dir_move_path"
    out = {
        "success": True,
        "status": "success",
        "message": message,
        "response": message,
        "tool_results": [_tool_entry(kind, tool_data or {})],
    }
    out.update(fields)
    return out


def _err(
    args: Dict[str, Any],
    message: str,
    *,
    tool_data: Dict[str, Any] | None = None,
    **fields: Any,
) -> Dict[str, Any]:
    kind = "nisb_dir_move_path"
    out = {
        "success": False,
        "status": "error",
        "message": message,
        "response": message,
        "tool_results": [_tool_entry(kind, tool_data or {})],
    }
    out.update(fields)
    return out


def _normalize_rel_path(p: str) -> str:
    s = str(p or "").strip().replace("\\", "/")
    s = _SLASH_RE.sub("/", s).lstrip("/")
    if not s:
        return ""
    parts = [x for x in s.split("/") if x not in ("", ".")]
    if any(x == ".." for x in parts):
        return ""
    return "/".join(parts)


def _require_agent_files_scope(rel_path: str) -> str:
    rp = _normalize_rel_path(rel_path)
    if not rp:
        raise ValueError("unsafe_path")
    if not (rp == _AGENT_SCOPE_PREFIX or rp.startswith(_AGENT_SCOPE_PREFIX + "/")):
        raise ValueError("DIR_MOVE_DENIED")
    return rp


def _validation_message(args: Dict[str, Any], reason: Any) -> str:
    reason_text = str(reason or "")
    mapping = {
        "unsafe_path": {
            "en": "❌ Unsafe path",
            "zh-CN": "❌ 路径不安全",
        },
        "DIR_MOVE_DENIED": {
            "en": "❌ Directory move denied: only agent_files/ scope is allowed",
            "zh-CN": "❌ 目录移动被拒绝：仅允许 agent_files/ scope",
        },
    }
    if reason_text in mapping:
        return i18n_text(_locale(args), mapping[reason_text], reason_text)
    return reason_text


def nisb_dir_move_path(args: Dict[str, Any]) -> Dict[str, Any]:
    args = _safe_args(args)
    user_id = args.get("user_id", "user_001")
    email = args.get("_librechat_email") or args.get("email")
    name = args.get("_librechat_name") or args.get("name")

    old_path_raw = args.get("old_path")
    new_path_raw = args.get("new_path")

    if not old_path_raw or not new_path_raw:
        return _err(
            args,
            _txt(args, "❌ Missing arguments: old_path and new_path are required", "❌ 参数缺失：old_path 和 new_path 必须提供"),
            tool_data={"old_path": old_path_raw, "new_path": new_path_raw, "reason": "missing_paths"},
        )

    try:
        old_rel = _require_agent_files_scope(str(old_path_raw))
        new_rel = _require_agent_files_scope(str(new_path_raw))

        if old_rel == new_rel:
            return _ok(
                args,
                _txt(args, "No changes needed", "无需移动"),
                tool_data={"old_path": old_rel, "new_path": new_rel, "reason": "no_op"},
                old_path=old_rel,
                new_path=new_rel,
            )

        base_path = get_base_path(user_id, email, name)
        old_abs = Path(base_path) / old_rel
        new_abs = Path(base_path) / new_rel

        if not old_abs.exists():
            return _err(
                args,
                _fmt(args, "❌ old_path does not exist: {path}", "❌ old_path 不存在：{path}", path=old_rel),
                tool_data={"old_path": old_rel, "new_path": new_rel, "reason": "old_path_not_exists"},
                old_path=old_rel,
                new_path=new_rel,
            )

        if not old_abs.is_dir():
            return _err(
                args,
                _fmt(args, "❌ old_path is not a directory: {path}", "❌ old_path 不是目录：{path}", path=old_rel),
                tool_data={"old_path": old_rel, "new_path": new_rel, "reason": "old_path_not_directory"},
                old_path=old_rel,
                new_path=new_rel,
            )

        if new_abs.exists():
            return _err(
                args,
                _fmt(args, "❌ new_path already exists: {path}", "❌ new_path 已存在：{path}", path=new_rel),
                tool_data={"old_path": old_rel, "new_path": new_rel, "reason": "new_path_exists"},
                old_path=old_rel,
                new_path=new_rel,
            )

        ok1, err1, _ = validate_path_safety(str(old_abs), user_id, email, name)
        if not ok1:
            return _err(
                args,
                _validation_message(args, err1),
                tool_data={"old_path": old_rel, "new_path": new_rel, "validation_error": err1},
                old_path=old_rel,
                new_path=new_rel,
            )

        ok2, err2, _ = validate_path_safety(str(new_abs), user_id, email, name)
        if not ok2:
            return _err(
                args,
                _validation_message(args, err2),
                tool_data={"old_path": old_rel, "new_path": new_rel, "validation_error": err2},
                old_path=old_rel,
                new_path=new_rel,
            )

        old_prefix = str(old_abs.resolve()) + os.sep
        if str(new_abs.resolve()).startswith(old_prefix):
            return _err(
                args,
                _txt(args, "❌ Cannot move a directory into its own subdirectory", "❌ 不能把目录移动到自身子目录下"),
                tool_data={"old_path": old_rel, "new_path": new_rel, "reason": "target_inside_source"},
                old_path=old_rel,
                new_path=new_rel,
            )

        backup_applied = False
        try:
            if should_backup(str(old_abs), user_id, email, name):
                backup_result = create_backup(
                    user_id=user_id,
                    email=email,
                    name=name,
                    operation="dir_move_path",
                    affected_files=[],
                    metadata={"old_path": old_rel, "new_path": new_rel},
                )
                backup_applied = bool(backup_result.get("success"))
        except Exception:
            pass

        new_abs.parent.mkdir(parents=True, exist_ok=True)
        os.replace(str(old_abs), str(new_abs))

        message = _fmt(args, "✅ Directory moved: {old_path} -> {new_path}", "✅ 已移动目录：{old_path} → {new_path}", old_path=old_rel, new_path=new_rel)
        return _ok(
            args,
            message,
            tool_data={
                "old_path": old_rel,
                "new_path": new_rel,
                "backup_applied": backup_applied,
            },
            old_path=old_rel,
            new_path=new_rel,
            backup_applied=backup_applied,
        )

    except Exception as e:
        return _err(
            args,
            _fmt(args, "❌ dir_move_path failed: {error}", "❌ dir_move_path 失败：{error}", error=_validation_message(args, e)),
            tool_data={
                "old_path": old_path_raw,
                "new_path": new_path_raw,
                "error": str(e),
            },
        )
