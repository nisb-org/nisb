from __future__ import annotations

import os
import shutil
from typing import Any, Dict, List, Optional, Tuple

from .config import get_backup_path, get_base_path
from .audit_log import append_fs_audit_event


def _ctx(args: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "user_id": args.get("user_id"),
        "_librechat_email": args.get("_librechat_email") or args.get("email"),
        "_librechat_name": args.get("_librechat_name") or args.get("name"),
        "email": args.get("email"),
        "name": args.get("name"),
    }


def _safe_norm_abs(p: str) -> str:
    try:
        return os.path.normpath(os.path.abspath(p))
    except Exception:
        return ""


def _dir_size_bytes(root: str) -> int:
    total = 0
    try:
        for r, _, files in os.walk(root):
            for fn in files:
                fp = os.path.join(r, fn)
                try:
                    if os.path.islink(fp):
                        continue
                    total += int(os.path.getsize(fp))
                except Exception:
                    continue
    except Exception:
        return total
    return total


def _list_backup_dirs(backup_root: str) -> List[str]:
    if not os.path.isdir(backup_root):
        return []
    out: List[str] = []
    try:
        for name in os.listdir(backup_root):
            p = os.path.join(backup_root, name)
            if os.path.isdir(p) and (not os.path.islink(p)):
                out.append(name)
    except Exception:
        return []
    out.sort(reverse=True)
    return out


def nisb_fs_backups_stats(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    统计可恢复备份（.backups）占用情况。

    输出：
      - backups_root
      - backups_count
      - size_bytes
    """
    ctx = _ctx(args)
    user_id = ctx.get("user_id")
    email = ctx.get("_librechat_email") or ctx.get("email")
    name = ctx.get("_librechat_name") or ctx.get("name")

    if not user_id:
        return {"success": False, "message": "缺少参数：user_id"}

    base_path = get_base_path(user_id, email, name)
    backup_root = get_backup_path(user_id, email, name)

    base_abs = _safe_norm_abs(base_path)
    backup_abs = _safe_norm_abs(backup_root)
    expected_abs = _safe_norm_abs(os.path.join(base_path, ".backups"))
    if not backup_abs or backup_abs != expected_abs or not backup_abs.startswith(base_abs + os.sep):
        return {"success": False, "message": "BACKUPS_ROOT_INVALID: 备份根目录校验失败"}

    if not os.path.isdir(backup_root):
        return {
            "success": True,
            "backups_root": backup_root,
            "backups_count": 0,
            "size_bytes": 0,
            "message": "no backups dir",
        }

    backup_ids = _list_backup_dirs(backup_root)
    size_bytes = 0
    for bid in backup_ids:
        bdir = os.path.join(backup_root, bid)
        size_bytes += _dir_size_bytes(bdir)

    return {
        "success": True,
        "backups_root": backup_root,
        "backups_count": len(backup_ids),
        "size_bytes": int(size_bytes),
    }


def nisb_fs_backups_purge_all(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    永久清空可恢复备份：删除 /data/users/{uid}/.backups 下所有备份目录（不可恢复）。
    需要 confirm_token：必须输入 delete 或 删除（大小写不敏感）。
    """
    ctx = _ctx(args)
    user_id = ctx.get("user_id")
    email = ctx.get("_librechat_email") or ctx.get("email")
    name = ctx.get("_librechat_name") or ctx.get("name")

    if not user_id:
        return {"success": False, "message": "缺少参数：user_id"}

    token = str(args.get("confirm_token") or "").strip().lower()
    if token not in ("delete", "删除"):
        return {"success": False, "message": "CONFIRM_REQUIRED: 请输入 delete（或 删除）以确认清空可恢复备份"}

    base_path = get_base_path(user_id, email, name)
    backup_root = get_backup_path(user_id, email, name)

    base_abs = _safe_norm_abs(base_path)
    backup_abs = _safe_norm_abs(backup_root)
    expected_abs = _safe_norm_abs(os.path.join(base_path, ".backups"))
    if not backup_abs or backup_abs != expected_abs or not backup_abs.startswith(base_abs + os.sep):
        return {"success": False, "message": "BACKUPS_ROOT_INVALID: 备份根目录校验失败"}

    if not os.path.isdir(backup_root):
        return {"success": True, "purged": 0, "size_bytes": 0, "failed": [], "message": "无可清理备份（.backups 不存在）"}

    purged = 0
    size_bytes = 0
    failed: List[str] = []

    backup_ids = _list_backup_dirs(backup_root)
    for bid in backup_ids:
        bdir = os.path.join(backup_root, bid)
        try:
            if os.path.islink(bdir):
                failed.append(f"{bid}: skipped symlink")
                continue
            size_bytes += _dir_size_bytes(bdir)
            shutil.rmtree(bdir, ignore_errors=False)
            purged += 1
        except Exception as e:
            failed.append(f"{bid}: {e}")

    try:
        append_fs_audit_event(
            user_id=user_id,
            email=email,
            name=name,
            event={
                "event": "backups_purge_all",
                "operation": "backups_purge_all",
                "batch_id": None,
                "paths": [],
                "metadata": {"purged": purged, "size_bytes": int(size_bytes), "failed": failed[:50]},
            },
        )
    except Exception as e:
        print(f"[WARN] audit backups_purge_all failed: {e}")

    msg = f"🧹 已清空可恢复备份：删除 {purged} 个备份目录"
    if failed:
        msg += f"（失败 {len(failed)} 个）"

    return {
        "success": True,
        "purged": purged,
        "size_bytes": int(size_bytes),
        "failed": failed,
        "message": msg,
    }

