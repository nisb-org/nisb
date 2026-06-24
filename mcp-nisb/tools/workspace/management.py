#!/usr/bin/env python3
from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any, Dict, List

from .common import (
    DEFAULT_WORKSPACES,
    _DEFAULT_WORKSPACE_IDS,
    auto_user_context,
    get_user_ctx,
    _now_iso_utc,
    _get_workspace_path,
    _get_workspace_meta_file,
    _get_workspace_root_dir,
    _require_workspace_id,
    _atomic_write_json,
    _load_workspace_file_or_create,
    _load_workspace_file_strict,
    _ensure_files_state_schema,
    _slugify_workspace_name,
    _pick_unique_workspace_id,
)


def _legacy_workspace_id_from_name(name: str) -> str:
    return f"workspace_{name.lower().replace(' ', '_').replace('💼', 'work').replace('📚', 'study').replace('🎨', 'creative')}"


def _safe_text(value: Any, default: str = "") -> str:
    return str(value if value is not None else default).strip()


def _safe_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _workspace_state_summary(ws: Dict[str, Any]) -> Dict[str, int]:
    state = _safe_dict(ws.get("state"))
    libraries = state.get("libraries") if isinstance(state.get("libraries"), list) else []
    conversations = state.get("conversations") if isinstance(state.get("conversations"), list) else []
    files = state.get("files") if isinstance(state.get("files"), list) else []

    return {
        "libraries_count": len(libraries),
        "conversations_count": len(conversations),
        "files_count": len(files),
        "item_count": len(libraries) + len(conversations) + len(files),
    }


def _workspace_brief(ws: Dict[str, Any]) -> Dict[str, Any]:
    meta = _safe_dict(ws.get("meta"))
    base = {
        "id": _safe_text(ws.get("id")),
        "name": _safe_text(ws.get("name")),
        "description": _safe_text(ws.get("description")),
        "is_default": bool(ws.get("is_default", False)),
        "created_at": _safe_text(ws.get("created_at")),
        "last_updated": _safe_text(ws.get("last_updated")),
        "icon": _safe_text(meta.get("icon")),
    }
    base.update(_workspace_state_summary(ws))
    return base


def _workspace_info_row(ws: Dict[str, Any], include_state: bool = True) -> Dict[str, Any]:
    row: Dict[str, Any] = {
        "type": "workspace_info",
        "workspace": _workspace_brief(ws),
    }
    if include_state:
        row["state"] = _safe_dict(ws.get("state"))
    return row


def _workspace_list_row(workspaces: List[Dict[str, Any]]) -> Dict[str, Any]:
    return {
        "type": "workspace_list",
        "workspaces": workspaces,
        "total": len(workspaces),
    }


def _workspace_delete_row(
    workspace_id: str,
    trashed_meta_to: str,
    trashed_dir_to: str,
) -> Dict[str, Any]:
    return {
        "type": "workspace_delete",
        "workspace_id": workspace_id,
        "trashed_meta_to": trashed_meta_to,
        "trashed_dir_to": trashed_dir_to,
        "deleted": True,
    }


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
def nisb_workspace_save(args: dict) -> dict:
    user_ctx = get_user_ctx()

    name = _safe_text(args.get("name"))
    state = args.get("state", {})

    if not name:
        return _err("❌ name 不能为空")

    workspace_id = _legacy_workspace_id_from_name(name)
    workspace_file = _get_workspace_meta_file(user_ctx, workspace_id)
    _get_workspace_root_dir(user_ctx, workspace_id, create=True)

    now = _now_iso_utc()
    workspace_data = {
        "id": workspace_id,
        "name": name,
        "state": state if isinstance(state, dict) else {},
        "created_at": now if not workspace_file.exists() else None,
        "last_updated": now,
        "is_default": False,
    }

    if workspace_file.exists():
        try:
            _, old_data = _load_workspace_file_or_create(user_ctx, workspace_id)
            workspace_data["created_at"] = old_data.get("created_at")
            workspace_data["is_default"] = old_data.get("is_default", False)
            workspace_data["description"] = old_data.get("description", "")
            workspace_data["meta"] = old_data.get("meta", {})
        except Exception:
            pass

    _ensure_files_state_schema(workspace_data)
    _atomic_write_json(workspace_file, workspace_data)

    return _ok(
        f"工作空间已保存：{name}",
        message=f"✅ 工作空间已保存：{name}",
        tool_results=[_workspace_info_row(workspace_data, include_state=True)],
        workspace_id=workspace_id,
    )


@auto_user_context
def nisb_workspace_load(args: dict) -> dict:
    user_ctx = get_user_ctx()

    name = _safe_text(args.get("name"))
    if not name:
        return _err("❌ name 不能为空")

    workspace_id = _legacy_workspace_id_from_name(name)
    workspace_file = _get_workspace_meta_file(user_ctx, workspace_id)

    if not workspace_file.exists():
        return _err(f"❌ 工作空间不存在：{name}")

    _, workspace_data = _load_workspace_file_strict(user_ctx, workspace_id)
    _ensure_files_state_schema(workspace_data)

    return _ok(
        f"已加载工作空间：{_safe_text(workspace_data.get('name')) or workspace_id}",
        message=f"已加载工作空间：{_safe_text(workspace_data.get('name')) or workspace_id}",
        tool_results=[_workspace_info_row(workspace_data, include_state=True)],
        workspace_id=workspace_id,
        name=workspace_data.get("name"),
        state=workspace_data.get("state", {}),
        last_updated=workspace_data.get("last_updated"),
    )


@auto_user_context
def nisb_workspace_list(args: dict) -> dict:
    user_ctx = get_user_ctx()

    workspace_dir = _get_workspace_path(user_ctx)
    workspaces: List[Dict[str, Any]] = []

    for default_ws in DEFAULT_WORKSPACES:
        workspace_id = default_ws["id"]
        workspace_file = workspace_dir / f"{workspace_id}.json"

        if not workspace_file.exists():
            now = _now_iso_utc()
            workspace_data = {
                **default_ws,
                "created_at": now,
                "last_updated": now,
                "state": {
                    "libraries": [],
                    "conversations": [],
                    "files": [],
                    "files_state": {},
                },
            }
            _ensure_files_state_schema(workspace_data)
            _atomic_write_json(workspace_file, workspace_data)

        _get_workspace_root_dir(user_ctx, workspace_id, create=True)

        try:
            _, ws = _load_workspace_file_or_create(user_ctx, workspace_id)
            _ensure_files_state_schema(ws)
            workspaces.append(_workspace_brief(ws))
        except Exception:
            continue

    for workspace_file in workspace_dir.glob("workspace_*.json"):
        if workspace_file.stem in ["workspace_work", "workspace_study", "workspace_creative"]:
            continue

        try:
            wid = workspace_file.stem
            _get_workspace_root_dir(user_ctx, wid, create=True)
            _, ws = _load_workspace_file_or_create(user_ctx, wid)
            _ensure_files_state_schema(ws)
            workspaces.append(_workspace_brief(ws))
        except Exception:
            continue

    workspaces.sort(key=lambda x: _safe_text(x.get("last_updated")), reverse=True)

    return _ok(
        f"已获取工作空间列表，共 {len(workspaces)} 个",
        message=f"已获取工作空间列表，共 {len(workspaces)} 个",
        tool_results=[_workspace_list_row(workspaces)],
        workspaces=workspaces,
        total=len(workspaces),
    )


@auto_user_context
def nisb_workspace_create(args: dict) -> dict:
    user_ctx = get_user_ctx()
    workspace_name = _safe_text(args.get("workspace_name"))
    icon = _safe_text(args.get("icon"))
    description = _safe_text(args.get("description"))

    if not workspace_name:
        return _err("workspace_name is required")

    display_name = f"{icon} {workspace_name}".strip() if icon else workspace_name

    workspace_dir = _get_workspace_path(user_ctx)
    slug = _slugify_workspace_name(workspace_name)
    workspace_id = _pick_unique_workspace_id(workspace_dir, slug)

    ws_path = workspace_dir / f"{workspace_id}.json"
    now = _now_iso_utc()

    ws = {
        "id": workspace_id,
        "name": display_name,
        "description": description,
        "is_default": False,
        "created_at": now,
        "last_updated": now,
        "state": {
            "libraries": [],
            "conversations": [],
            "files": [],
            "files_state": {},
        },
        "meta": {
            "icon": icon,
        },
    }

    _ensure_files_state_schema(ws)
    _atomic_write_json(ws_path, ws)
    _get_workspace_root_dir(user_ctx, workspace_id, create=True)

    workspace_brief = _workspace_brief(ws)

    return _ok(
        f"已创建工作空间：{workspace_brief.get('name') or workspace_id}",
        message="✅ workspace created",
        tool_results=[_workspace_info_row(ws, include_state=True)],
        workspace_id=workspace_id,
        workspace=workspace_brief,
    )


@auto_user_context
def nisb_workspace_rename(args: dict) -> dict:
    user_ctx = get_user_ctx()
    workspace_id = _safe_text(args.get("workspace_id"))
    new_workspace_name = _safe_text(args.get("new_workspace_name"))
    icon = _safe_text(args.get("icon"))
    description = args.get("description", None)

    if not new_workspace_name:
        return _err("new_workspace_name is required")

    try:
        wid = _require_workspace_id(workspace_id)
        ws_path, ws = _load_workspace_file_strict(user_ctx, wid)

        meta = ws.get("meta") if isinstance(ws.get("meta"), dict) else {}
        old_icon = _safe_text(meta.get("icon"))

        eff_icon = icon if icon else old_icon
        display_name = f"{eff_icon} {new_workspace_name}".strip() if eff_icon else new_workspace_name

        ws["name"] = display_name
        if description is not None:
            ws["description"] = _safe_text(description)

        if "meta" not in ws or not isinstance(ws.get("meta"), dict):
            ws["meta"] = {}
        ws["meta"]["icon"] = eff_icon

        ws["last_updated"] = _now_iso_utc()
        _ensure_files_state_schema(ws)
        _atomic_write_json(ws_path, ws)

        return _ok(
            f"已重命名工作空间：{_safe_text(ws.get('name')) or wid}",
            message="✅ workspace renamed",
            tool_results=[_workspace_info_row(ws, include_state=True)],
            workspace_id=wid,
            name=ws.get("name", ""),
        )
    except Exception as e:
        return _err(f"rename workspace failed: {e}")


@auto_user_context
def nisb_workspace_delete(args: dict) -> dict:
    user_ctx = get_user_ctx()
    workspace_id = _safe_text(args.get("workspace_id"))

    try:
        wid = _require_workspace_id(workspace_id)

        if wid in _DEFAULT_WORKSPACE_IDS:
            return _err("cannot delete default workspace")

        ws_path, ws = _load_workspace_file_strict(user_ctx, wid)
        if bool(ws.get("is_default", False)):
            return _err("cannot delete default workspace")

        workspace_dir = _get_workspace_path(user_ctx)
        trash_dir = workspace_dir / ".trash"
        trash_dir.mkdir(parents=True, exist_ok=True)

        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

        meta_dest = trash_dir / f"{wid}__deleted__{ts}.json"
        if meta_dest.exists():
            for i in range(2, 200):
                cand = trash_dir / f"{wid}__deleted__{ts}__{i}.json"
                if not cand.exists():
                    meta_dest = cand
                    break

        os.replace(str(ws_path), str(meta_dest))

        workspace_root = _get_workspace_root_dir(user_ctx, wid, create=False)
        dir_dest = None
        if workspace_root.exists():
            dir_dest = trash_dir / f"{wid}__deleted__{ts}"
            if dir_dest.exists():
                for i in range(2, 200):
                    cand = trash_dir / f"{wid}__deleted__{ts}__{i}"
                    if not cand.exists():
                        dir_dest = cand
                        break
            os.replace(str(workspace_root), str(dir_dest))

        return _ok(
            f"已删除工作空间：{wid}",
            message="✅ workspace deleted (moved to trash)",
            tool_results=[
                _workspace_delete_row(
                    workspace_id=wid,
                    trashed_meta_to=str(meta_dest),
                    trashed_dir_to=str(dir_dest) if dir_dest else "",
                )
            ],
            workspace_id=wid,
            trashed_meta_to=str(meta_dest),
            trashed_dir_to=str(dir_dest) if dir_dest else "",
        )
    except Exception as e:
        return _err(f"delete workspace failed: {e}")

