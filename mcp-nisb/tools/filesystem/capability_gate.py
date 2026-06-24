from __future__ import annotations

import os
from typing import Any, Dict, List, Tuple

from .audit_log import append_fs_audit_event


def _ctx(args: Dict[str, Any]) -> Tuple[str, str, str]:
    user_id = (args.get("user_id") or args.get("_user_id") or "").strip()
    email = (args.get("_librechat_email") or args.get("_email") or args.get("email") or "").strip()
    name = (args.get("_librechat_name") or args.get("_name") or args.get("name") or "").strip()
    return user_id, email, name


def _request_id(args: Dict[str, Any]) -> str:
    return str(args.get("request_id") or "").strip()


def _as_int(value: Any, default: int = 1) -> int:
    try:
        return int(value)
    except Exception:
        return default


def _as_bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    if isinstance(value, (int, float)):
        return bool(value)
    s = str(value).strip().lower()
    if not s:
        return default
    return s in {"1", "true", "yes", "on"}


def _normalize_fs_read_scope(value: Any) -> str:
    s = str(value or "user_ro").strip().lower()
    if s == "minimal":
        return "minimal"
    return "user_ro"


def _normalize_fs_write_scope(value: Any) -> str:
    s = str(value or "none").strip().lower()
    if s in {"agent_files", "agentfiles"}:
        return "agent_files"
    return "none"


def _gate(args: Dict[str, Any]) -> Dict[str, Any]:
    g = args.get("capability_gate")
    if not isinstance(g, dict):
        g = {}
    return {
        "policy_version": _as_int(g.get("policy_version"), 1),
        "workspace_id": str(g.get("workspace_id") or "").strip(),
        "focus_root": str(g.get("focus_root") or "").strip(),
        "fs_read_scope": _normalize_fs_read_scope(g.get("fs_read_scope")),
        "fs_write_scope": _normalize_fs_write_scope(g.get("fs_write_scope")),
        "fs_dangerous_enabled": _as_bool(g.get("fs_dangerous_enabled"), False),
    }


def _norm_rel(p: str) -> str:
    s = (p or "").strip().replace("\\", "/")
    while s.startswith("/"):
        s = s[1:]
    s = os.path.normpath(s).replace("\\", "/")
    return s


def _is_agent_rel(rel: str) -> bool:
    rel = _norm_rel(rel)
    return rel == "agent_files" or rel.startswith("agent_files/")


def _is_storage_rel(rel: str) -> bool:
    rel = _norm_rel(rel)
    return rel == "storage" or rel.startswith("storage/")


def _as_rel_for_ui_paths(p: str) -> str:
    """
    统一前端传入路径口径：
    - 已是 agent_files/... 或 storage/... 则保留
    - 其它（FileBrowser 常见：把 agent_files 当根展示）则补 agent_files/
    """
    rel = _norm_rel(p)
    if rel in ("", "."):
        raise ValueError("INVALID_PATH_EMPTY")
    if ".." in rel.split("/"):
        raise ValueError("INVALID_PATH_TRAVERSAL")
    if _is_agent_rel(rel) or _is_storage_rel(rel):
        return rel
    return f"agent_files/{rel}"


def _as_agent_rel_only(p: str) -> str:
    rel = _as_rel_for_ui_paths(p)
    if not _is_agent_rel(rel):
        raise ValueError("WRITE_OUTSIDE_AGENT_FILES")
    return rel


def _resolve_focus_root(raw_focus_root: str) -> str:
    raw = str(raw_focus_root or "").strip()
    if not raw:
        return ""
    try:
        return _as_agent_rel_only(raw)
    except Exception:
        return ""


def _resolve_ui_path_against_focus(p: str, focus_root: str) -> str:
    """
    统一前端路径口径，并在 focus_root 存在时优先按 focus_root 解析相对路径。

    规则：
    - 已是 agent_files/... 或 storage/...：直接保留
    - 非前缀路径：
      - 若存在 focus_root，则视为 focus_root 下的相对路径
      - 否则回退为 agent_files/ 下的相对路径
    """
    rel = _norm_rel(p)
    if rel in ("", "."):
        raise ValueError("INVALID_PATH_EMPTY")
    if ".." in rel.split("/"):
        raise ValueError("INVALID_PATH_TRAVERSAL")

    if _is_agent_rel(rel) or _is_storage_rel(rel):
        return rel

    focus = _norm_rel(focus_root)
    if focus and _is_agent_rel(focus):
        return _norm_rel(f"{focus}/{rel}")

    return f"agent_files/{rel}"


def _within(path_rel: str, root_rel: str) -> bool:
    pr = _norm_rel(path_rel)
    rr = _norm_rel(root_rel)
    if not rr:
        return True
    if pr == rr:
        return True
    return pr.startswith(rr.rstrip("/") + "/")


def _is_internal_editor_save(
    *,
    args: Dict[str, Any],
    operation: str,
    normalized_paths: List[str],
    is_write: bool,
    is_dangerous: bool,
) -> bool:
    if not is_write or is_dangerous:
        return False
    if operation not in {"nisb_file_create", "nisb_file_update"}:
        return False
    if not _as_bool(args.get("_internal_editor_save"), False):
        return False
    if not normalized_paths:
        return False

    for p in normalized_paths:
        if _is_storage_rel(p):
            return False
        if not _is_agent_rel(p):
            return False
    return True


def _audit_denied(
    *,
    args: Dict[str, Any],
    user_id: str,
    email: str,
    name: str,
    operation: str,
    reason_code: str,
    paths: List[str],
    gate_snapshot: Dict[str, Any],
) -> None:
    if not user_id:
        return
    try:
        append_fs_audit_event(
            user_id=user_id,
            email=email,
            name=name,
            event={
                "event": "capability_denied",
                "operation": operation,
                "reason_code": reason_code,
                "paths": paths,
                "gate_snapshot": gate_snapshot,
                "request_id": _request_id(args),
            },
        )
    except Exception:
        pass


def enforce_fs_capability_gate(
    *,
    args: Dict[str, Any],
    operation: str,
    paths: List[str],
    is_read: bool = False,
    is_write: bool = False,
    is_dangerous: bool = False,
) -> Tuple[bool, str, str, List[str]]:
    """
    返回：(allowed, message, reason_code, normalized_paths)

    规则（目录级为主 + 拒绝可回放）：
    - read_scope=minimal：只允许 agent_files/...
    - write_scope=agent_files：只允许写 agent_files/...
    - dangerous 操作：必须 fs_dangerous_enabled=true 且 focus_root 非空
    - focus_root 非空时：所有写操作必须在 focus_root 内；dangerous 更强制要求 focus_root

    例外：
    - 编辑器内建保存（_internal_editor_save=true）仅对 nisb_file_create / nisb_file_update 生效，
      且仍然必须写在 agent_files/... 内；该例外不放开 storage，也不放开危险操作。
    """
    user_id, email, name = _ctx(args)
    gate = _gate(args)

    fs_read_scope = gate.get("fs_read_scope") or "user_ro"
    fs_write_scope = gate.get("fs_write_scope") or "none"
    fs_dangerous_enabled = bool(gate.get("fs_dangerous_enabled") or False)

    focus_root_raw = str(gate.get("focus_root") or "").strip()
    focus_root = _resolve_focus_root(focus_root_raw)

    normalized: List[str] = []
    for p in (paths or []):
        s = str(p or "").strip()
        if not s:
            continue
        try:
            normalized.append(_resolve_ui_path_against_focus(s, focus_root))
        except Exception:
            normalized.append(_norm_rel(s))

    internal_editor_save = _is_internal_editor_save(
        args=args,
        operation=operation,
        normalized_paths=normalized,
        is_write=is_write,
        is_dangerous=is_dangerous,
    )

    if not user_id:
        reason = "MISSING_USER_ID"
        _audit_denied(
            args=args,
            user_id="",
            email=email,
            name=name,
            operation=operation,
            reason_code=reason,
            paths=normalized,
            gate_snapshot=gate,
        )
        return False, f"CAPABILITY_DENIED: {reason}", reason, normalized

    if is_read:
        if fs_read_scope == "minimal":
            for p in normalized:
                if not _is_agent_rel(p):
                    reason = "READ_SCOPE_DENIED"
                    _audit_denied(
                        args=args,
                        user_id=user_id,
                        email=email,
                        name=name,
                        operation=operation,
                        reason_code=reason,
                        paths=normalized,
                        gate_snapshot=gate,
                    )
                    return False, f"CAPABILITY_DENIED: {reason}", reason, normalized

    if is_write:
        if not internal_editor_save and fs_write_scope != "agent_files":
            reason = "WRITE_SCOPE_NONE" if fs_write_scope == "none" else "WRITE_SCOPE_DENIED"
            _audit_denied(
                args=args,
                user_id=user_id,
                email=email,
                name=name,
                operation=operation,
                reason_code=reason,
                paths=normalized,
                gate_snapshot=gate,
            )
            return False, f"CAPABILITY_DENIED: {reason}", reason, normalized

        for p in normalized:
            if _is_storage_rel(p):
                reason = "WRITE_TO_STORAGE_DENIED"
                _audit_denied(
                    args=args,
                    user_id=user_id,
                    email=email,
                    name=name,
                    operation=operation,
                    reason_code=reason,
                    paths=normalized,
                    gate_snapshot=gate,
                )
                return False, f"CAPABILITY_DENIED: {reason}", reason, normalized

            if not _is_agent_rel(p):
                reason = "WRITE_OUTSIDE_AGENT_FILES"
                _audit_denied(
                    args=args,
                    user_id=user_id,
                    email=email,
                    name=name,
                    operation=operation,
                    reason_code=reason,
                    paths=normalized,
                    gate_snapshot=gate,
                )
                return False, f"CAPABILITY_DENIED: {reason}", reason, normalized

        if is_dangerous:
            if not fs_dangerous_enabled:
                reason = "DANGEROUS_DISABLED"
                _audit_denied(
                    args=args,
                    user_id=user_id,
                    email=email,
                    name=name,
                    operation=operation,
                    reason_code=reason,
                    paths=normalized,
                    gate_snapshot=gate,
                )
                return False, f"CAPABILITY_DENIED: {reason}", reason, normalized

            if not focus_root:
                reason = "FOCUS_ROOT_REQUIRED"
                _audit_denied(
                    args=args,
                    user_id=user_id,
                    email=email,
                    name=name,
                    operation=operation,
                    reason_code=reason,
                    paths=normalized,
                    gate_snapshot=gate,
                )
                return False, f"CAPABILITY_DENIED: {reason}", reason, normalized

        if focus_root and not internal_editor_save:
            for p in normalized:
                if _is_agent_rel(p) and not _within(p, focus_root):
                    reason = "FOCUS_ROOT_MISMATCH"
                    _audit_denied(
                        args=args,
                        user_id=user_id,
                        email=email,
                        name=name,
                        operation=operation,
                        reason_code=reason,
                        paths=normalized,
                        gate_snapshot=gate,
                    )
                    return False, f"CAPABILITY_DENIED: {reason}", reason, normalized

    return True, "OK", "", normalized
