from __future__ import annotations

import os
import shutil
from typing import Any, Dict, List

from .audit_log import append_fs_audit_event


def _ctx(args: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "user_id": args.get("user_id"),
        "email": args.get("_librechat_email") or args.get("email"),
        "name": args.get("_librechat_name") or args.get("name"),
    }


def _base(args: Dict[str, Any]) -> str:
    base = args.get("base_path") or args.get("_base_path")
    if not base or not isinstance(base, str):
        raise ValueError("缺少 base_path/_base_path（网关应注入）")
    return base.rstrip("/")


def _trash_root_abs(base: str) -> str:
    return os.path.join(base, "agent_files", ".trash")


def nisb_fs_trash_purge_all(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    永久清空回收站：删除 agent_files/.trash 下所有批次目录（不可恢复）。
    需要 confirm_token：必须输入 delete 或 删除（大小写不敏感）。
    """
    ctx = _ctx(args)
    user_id = ctx.get("user_id")
    email = ctx.get("email")
    name = ctx.get("name")

    token = str(args.get("confirm_token") or "").strip().lower()
    if token not in ("delete", "删除"):
        return {"success": False, "message": "CONFIRM_REQUIRED: 请输入 delete（或 删除）以确认清空回收站"}

    base = _base(args)
    root = _trash_root_abs(base)
    if not os.path.isdir(root):
        return {"success": True, "purged": 0, "message": "回收站为空"}

    purged = 0
    failed: List[str] = []

    for entry in os.listdir(root):
        p = os.path.join(root, entry)
        if not os.path.isdir(p):
            continue
        try:
            # 递归删除批次目录（永久不可恢复）[web:686]
            shutil.rmtree(p, ignore_errors=False)
            purged += 1
        except Exception as e:
            failed.append(f"{entry}: {e}")

    try:
        append_fs_audit_event(
            user_id=user_id,
            email=email,
            name=name,
            event={
                "event": "trash_purge_all",
                "operation": "trash_purge_all",
                "batch_id": None,
                "paths": [],
                "metadata": {"purged": purged, "failed": failed[:50]},
            },
        )
    except Exception as e:
        print(f"[WARN] audit trash_purge_all failed: {e}")

    msg = f"🧹 已清空回收站：删除 {purged} 个批次"
    if failed:
        msg += f"（失败 {len(failed)} 个）"
    return {"success": True, "purged": purged, "failed": failed, "message": msg}

