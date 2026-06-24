from __future__ import annotations

import os
import shutil
from datetime import datetime
from typing import Any, Dict

from .config import get_base_path
from .backup import create_backup, should_backup


def _ctx(args: Dict[str, Any]) -> Dict[str, str]:
    return {
        "user_id": args.get("user_id"),
        "email": args.get("_librechat_email") or args.get("email") or "",
        "name": args.get("_librechat_name") or args.get("name") or "",
    }


def _is_dangerous_enabled(args: Dict[str, Any]) -> bool:
    v = args.get("fs_dangerous_enabled")
    if isinstance(v, bool):
        return v
    if isinstance(v, str):
        return v.strip().lower() in ("1", "true", "yes", "y", "on")
    # 兼容“显式确认词”
    confirm = str(args.get("confirm") or "").strip().upper()
    if confirm in ("DELETE", "YES_DELETE", "I_UNDERSTAND_DELETE"):
        return True
    return False


def _enforce_write_scope(rel_path: str, args: Dict[str, Any]) -> bool:
    scope = str(args.get("fs_write_scope") or "agent_files").strip().rstrip("/")
    rel_path = rel_path.lstrip("/")

    # 最保守：只允许 agent_files/ 下删除
    if scope == "agent_files":
        return rel_path == "agent_files" or rel_path.startswith("agent_files/")
    if scope in ("all", "*"):
        return True
    # 其它 scope：按前缀约束
    return rel_path == scope or rel_path.startswith(scope + "/")

def nisb_file_delete(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    删除文件：
    - dangerous=false：软删除 -> 移动到 agent_files/.trash/<ts>/原路径
    - dangerous=true ：硬删除 -> 直接 unlink（仅在危险开关允许时）
    返回：
    - mode: soft/hard
    - trash_rel/trash_path（soft 时）
    """
    ctx = _ctx(args)
    user_id = ctx["user_id"]
    email = ctx["email"]
    name = ctx["name"]

    filename = str(args.get("filename") or "").strip().lstrip("/").replace("\\", "/")
    if not filename:
        return {"success": False, "message": "缺少参数：filename"}

    # 删除属于写操作：必须受 fs_write_scope 限制
    if not _enforce_write_scope(filename, args):
        return {"success": False, "message": f"DELETE_DENIED: 超出写入范围 fs_write_scope ({args.get('fs_write_scope')})"}

    base_path = get_base_path(user_id, email, name)

    # 目标绝对路径（落在用户根下）
    target = os.path.normpath(os.path.join(base_path, filename))
    base_norm = os.path.normpath(base_path)
    if not (target == base_norm or target.startswith(base_norm + os.sep)):
        return {"success": False, "message": "DELETE_DENIED: 非法路径（疑似路径穿越）"}

    if not os.path.isfile(target):
        return {"success": False, "message": f"文件不存在：{filename}"}

    # 操作前备份（不阻断主流程）
    try:
        if should_backup(target, user_id, email, name):
            create_backup(
                user_id=user_id,
                email=email,
                name=name,
                operation="file_delete",
                affected_files=[target],
                metadata={
                    "filename": filename,
                    "file_id": args.get("file_id"),
                    "permanent": bool(args.get("permanent", True)),
                },
            )
    except Exception as e:
        print(f"[BACKUP] pre-delete backup failed: {e}")

    dangerous = _is_dangerous_enabled(args)

    # 硬删除：仅危险开关允许
    if dangerous:
        os.remove(target)
        return {
            "success": True,
            "message": f"✅ 已硬删除：{filename}",
            "mode": "hard",
            "deleted_rel": filename,
            "deleted_path": target,
        }

    # 软删除：移动到回收站
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    trash_bucket_abs = os.path.join(base_path, "agent_files", ".trash", ts)

    # 注意：这里把“原始相对路径”整体放进回收站 bucket 内，便于推导 original_rel
    dst_abs = os.path.normpath(os.path.join(trash_bucket_abs, filename))

    dst_parent = os.path.dirname(dst_abs)
    os.makedirs(dst_parent, exist_ok=True)

    # 同盘内移动：os.replace 更原子（比 shutil.move 更可控）
    os.replace(target, dst_abs)

    trash_rel = os.path.relpath(dst_abs, base_path).replace("\\", "/")

    return {
        "success": True,
        "message": f"✅ 已移入回收站：{filename}",
        "mode": "soft",
        # ✅ 两个都给：前端可显示 rel，后端/排障可用 abs
        "trash_rel": trash_rel,
        "trash_path": dst_abs,
        "original_rel": filename,
    }


