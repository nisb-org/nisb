#!/usr/bin/env python3
import os
import json
import re
import tempfile
from pathlib import Path
from datetime import datetime, timezone
from typing import Any, Dict

import sys
sys.path.insert(0, "/srv")

from core.user_context import auto_user_context, get_user_ctx


_WORKSPACE_ID_RE = re.compile(r"^workspace_[a-z0-9_]+$")
_DEFAULT_WORKSPACE_ID = "workspace_work"


def _now_iso_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _require_workspace_id(workspace_id: str) -> str:
    wid = str(workspace_id or "").strip()
    if not wid:
        raise ValueError("workspace_id is required")
    if not _WORKSPACE_ID_RE.match(wid):
        raise ValueError("invalid workspace_id")
    return wid


def _settings_path(user_ctx) -> Path:
    # ✅ 用户级真源：跨设备/隐私模式一致
    d = Path(user_ctx.base) / "storage" / "settings"
    d.mkdir(parents=True, exist_ok=True)
    return d / "user_workspace.json"


def _atomic_write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = tempfile.NamedTemporaryFile(mode="w", delete=False, encoding="utf-8", dir=str(path.parent))
    try:
        json.dump(data, tmp, ensure_ascii=False, indent=2)
        tmp.flush()
        os.fsync(tmp.fileno())
        tmp.close()
        os.replace(tmp.name, str(path))
    finally:
        try:
            if hasattr(tmp, "name") and tmp.name and os.path.exists(tmp.name):
                os.unlink(tmp.name)
        except Exception:
            pass


def _read_settings(user_ctx) -> dict:
    p = _settings_path(user_ctx)
    if not p.exists():
        return {}
    try:
        with open(p, "r", encoding="utf-8") as f:
            obj = json.load(f)
        return obj if isinstance(obj, dict) else {}
    except Exception:
        return {}


@auto_user_context
def nisb_user_workspace_get_current(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    获取用户“当前工作空间”（跨设备一致，后端真源）。
    返回：
      - current_workspace_id
      - updated_at
    """
    user_ctx = get_user_ctx()
    s = _read_settings(user_ctx)

    wid = str(s.get("current_workspace_id", "") or "").strip()
    if not wid or not _WORKSPACE_ID_RE.match(wid):
        wid = _DEFAULT_WORKSPACE_ID

    return {
        "success": True,
        "current_workspace_id": wid,
        "updated_at": str(s.get("updated_at", "") or ""),
        "source": "user_settings",
    }


@auto_user_context
def nisb_user_workspace_set_current(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    设置用户“当前工作空间”（跨设备一致，后端真源）。
    入参：
      - workspace_id: 如 workspace_work / workspace_study
    """
    user_ctx = get_user_ctx()

    try:
        wid = _require_workspace_id(args.get("workspace_id", ""))
    except Exception as e:
        return {"success": False, "message": str(e)}

    p = _settings_path(user_ctx)
    cur = _read_settings(user_ctx)

    cur["current_workspace_id"] = wid
    cur["updated_at"] = _now_iso_utc()

    _atomic_write_json(p, cur)

    return {
        "success": True,
        "message": "✅ current workspace saved",
        "current_workspace_id": wid,
        "updated_at": cur["updated_at"],
    }

