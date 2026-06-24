#!/usr/bin/env python3
from __future__ import annotations

import copy
from datetime import datetime, timezone
from typing import Any, Dict, List

from .common import (
    auto_user_context,
    get_user_ctx,
    _now_iso_utc,
    _require_workspace_id,
    _load_workspace_file_or_create,
    _ensure_files_state_schema,
    _parse_iso8601_any,
    _normalize_rel_path,
    _is_in_scope_agent_files,
    _load_fs_audit_events_between,
    _apply_path_events_to_path,
    _map_favorites_from_saved_with_audit,
    _atomic_write_json,
)


def _safe_text(value: Any, default: str = "") -> str:
    return str(value if value is not None else default).strip()


def _safe_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _safe_list(value: Any) -> List[Any]:
    return value if isinstance(value, list) else []


def _normalized_files_state_payload(fs: Dict[str, Any]) -> Dict[str, Any]:
    saved = _safe_dict(fs.get("saved"))
    current = _safe_dict(fs.get("current"))

    return {
        "saved": {
            "focused_root_path": _safe_text(saved.get("focused_root_path")),
            "favorites": _safe_list(saved.get("favorites")),
        },
        "current": {
            "focused_root_path": _safe_text(current.get("focused_root_path")),
            "favorites": _safe_list(current.get("favorites")),
        },
        "saved_at": _safe_text(fs.get("saved_at")),
    }


def _files_state_row(
    workspace_id: str,
    fs: Dict[str, Any],
    *,
    last_updated: str = "",
    migrate_stats: Dict[str, Any] | None = None,
    action: str = "",
) -> Dict[str, Any]:
    row: Dict[str, Any] = {
        "type": "workspace_files_state",
        "workspace_id": workspace_id,
        "files_state": _normalized_files_state_payload(fs),
        "last_updated": _safe_text(last_updated),
    }
    if migrate_stats is not None:
        row["migrate_stats"] = migrate_stats if isinstance(migrate_stats, dict) else {}
    if action:
        row["action"] = action
    return row


def _ok(
    response: str,
    *,
    message: str = "",
    tool_results: List[Dict[str, Any]] | None = None,
    **compat: Any,
) -> Dict[str, Any]:
    return {
        "status": "success",
        "response": _safe_text(response) or _safe_text(message) or "操作完成",
        "message": _safe_text(message) or _safe_text(response) or "操作完成",
        "citations": [],
        "tool_calls": [],
        "tool_results": tool_results or [],
        "success": True,
        **compat,
    }


def _err(message: str, *, response: str = "", **compat: Any) -> Dict[str, Any]:
    return {
        "status": "error",
        "response": _safe_text(response),
        "message": _safe_text(message) or "操作失败",
        "citations": [],
        "tool_calls": [],
        "tool_results": [],
        "success": False,
        **compat,
    }


@auto_user_context
def nisb_workspace_files_state_get(args: dict) -> dict:
    user_ctx = get_user_ctx()
    workspace_id = _safe_text(args.get("workspace_id"))

    try:
        wid = _require_workspace_id(workspace_id)
        _, ws = _load_workspace_file_or_create(user_ctx, wid)
        fs = _ensure_files_state_schema(ws)
        files_state = _normalized_files_state_payload(fs)
        last_updated = _safe_text(ws.get("last_updated"))

        return _ok(
            f"已获取工作空间文件状态：{wid}",
            message=f"已获取工作空间文件状态：{wid}",
            tool_results=[
                _files_state_row(
                    workspace_id=wid,
                    fs=fs,
                    last_updated=last_updated,
                    action="get",
                )
            ],
            workspace_id=wid,
            files_state=files_state,
            last_updated=last_updated,
        )
    except Exception as e:
        return _err(f"get files_state failed: {e}")


@auto_user_context
def nisb_workspace_files_state_set(args: dict) -> dict:
    user_ctx = get_user_ctx()
    workspace_id = _safe_text(args.get("workspace_id"))
    focused_root_path = _safe_text(args.get("focused_root_path")).lstrip("/")

    try:
        wid = _require_workspace_id(workspace_id)
        ws_path, ws = _load_workspace_file_or_create(user_ctx, wid)
        fs = _ensure_files_state_schema(ws)

        cur = _safe_dict(fs.get("current"))
        cur["focused_root_path"] = focused_root_path
        if "favorites" not in cur or not isinstance(cur.get("favorites"), list):
            cur["favorites"] = []
        fs["current"] = cur

        ws["last_updated"] = _now_iso_utc()
        _atomic_write_json(ws_path, ws)

        files_state = _normalized_files_state_payload(fs)
        last_updated = _safe_text(ws.get("last_updated"))

        return _ok(
            f"已更新工作空间当前文件状态：{wid}",
            message="✅ 已更新当前文件状态",
            tool_results=[
                _files_state_row(
                    workspace_id=wid,
                    fs=fs,
                    last_updated=last_updated,
                    action="set",
                )
            ],
            workspace_id=wid,
            files_state=files_state,
            last_updated=last_updated,
        )
    except Exception as e:
        return _err(f"set files_state failed: {e}")


@auto_user_context
def nisb_workspace_files_state_save(args: dict) -> dict:
    user_ctx = get_user_ctx()
    workspace_id = _safe_text(args.get("workspace_id"))

    try:
        wid = _require_workspace_id(workspace_id)
        ws_path, ws = _load_workspace_file_or_create(user_ctx, wid)
        fs = _ensure_files_state_schema(ws)

        cur = _safe_dict(fs.get("current"))
        if "focused_root_path" not in cur:
            cur["focused_root_path"] = ""
        if "favorites" not in cur or not isinstance(cur.get("favorites"), list):
            cur["favorites"] = []

        fs["saved"] = copy.deepcopy(cur)
        fs["saved_at"] = _now_iso_utc()

        ws["last_updated"] = _now_iso_utc()
        _atomic_write_json(ws_path, ws)

        files_state = _normalized_files_state_payload(fs)
        last_updated = _safe_text(ws.get("last_updated"))

        return _ok(
            f"已保存工作空间快照：{wid}",
            message="✅ 已保存为工作空间快照",
            tool_results=[
                _files_state_row(
                    workspace_id=wid,
                    fs=fs,
                    last_updated=last_updated,
                    action="save",
                )
            ],
            workspace_id=wid,
            files_state=files_state,
            last_updated=last_updated,
        )
    except Exception as e:
        return _err(f"save files_state failed: {e}")


@auto_user_context
def nisb_workspace_files_state_apply(args: dict) -> dict:
    user_ctx = get_user_ctx()
    workspace_id = _safe_text(args.get("workspace_id"))

    try:
        wid = _require_workspace_id(workspace_id)
        ws_path, ws = _load_workspace_file_or_create(user_ctx, wid)
        fs = _ensure_files_state_schema(ws)

        saved = _safe_dict(fs.get("saved"))
        saved_at = _safe_text(fs.get("saved_at"))

        cur = copy.deepcopy(saved)

        focused0 = _normalize_rel_path(cur.get("focused_root_path", ""))
        if focused0 and _is_in_scope_agent_files(focused0):
            start_dt = _parse_iso8601_any(saved_at)
            now_dt = datetime.now(timezone.utc)
            events = _load_fs_audit_events_between(user_ctx, start_dt, now_dt)
            focused1, _ = _apply_path_events_to_path(focused0, events)
            cur["focused_root_path"] = focused1 if (focused1 and _is_in_scope_agent_files(focused1)) else ""
        else:
            cur["focused_root_path"] = ""

        favs0 = cur.get("favorites", [])
        mapped_favs, stats = _map_favorites_from_saved_with_audit(user_ctx, favs0, saved_at)
        cur["favorites"] = mapped_favs

        fs["current"] = cur
        ws["last_updated"] = _now_iso_utc()
        _atomic_write_json(ws_path, ws)

        files_state = _normalized_files_state_payload(fs)
        last_updated = _safe_text(ws.get("last_updated"))

        return _ok(
            f"已恢复工作空间快照：{wid}",
            message="✅ 已恢复到工作空间快照（favorites 已按审计自动迁移）",
            tool_results=[
                _files_state_row(
                    workspace_id=wid,
                    fs=fs,
                    last_updated=last_updated,
                    migrate_stats=stats if isinstance(stats, dict) else {},
                    action="apply",
                )
            ],
            workspace_id=wid,
            files_state=files_state,
            last_updated=last_updated,
            migrate_stats=stats,
        )
    except Exception as e:
        return _err(f"apply files_state failed: {e}")


@auto_user_context
def nisb_workspace_files_state_clear(args: dict) -> dict:
    user_ctx = get_user_ctx()
    workspace_id = _safe_text(args.get("workspace_id"))

    try:
        wid = _require_workspace_id(workspace_id)
        ws_path, ws = _load_workspace_file_or_create(user_ctx, wid)
        fs = _ensure_files_state_schema(ws)

        empty = {"focused_root_path": "", "favorites": []}
        fs["saved"] = copy.deepcopy(empty)
        fs["current"] = copy.deepcopy(empty)
        fs["saved_at"] = _now_iso_utc()
        fs["legacy_favorites_migrated"] = True

        ws["last_updated"] = _now_iso_utc()
        _atomic_write_json(ws_path, ws)

        files_state = _normalized_files_state_payload(fs)
        last_updated = _safe_text(ws.get("last_updated"))

        return _ok(
            f"已清空工作空间文件快照与当前态：{wid}",
            message="✅ 已清空工作空间文件快照与当前态",
            tool_results=[
                _files_state_row(
                    workspace_id=wid,
                    fs=fs,
                    last_updated=last_updated,
                    action="clear",
                )
            ],
            workspace_id=wid,
            files_state=files_state,
            last_updated=last_updated,
        )
    except Exception as e:
        return _err(f"clear files_state failed: {e}")

