"""
自动备份模块 - 简化版（生产级）
操作storage/目录前自动创建备份
符合NISB多用户规范

设计理念：
- 轻量级：只备份受影响的文件
- 可追溯：完整的备份元数据
- 安全性：Agent无法删除备份
- 性能优化：增量备份，避免重复
"""

import os
import json
import shutil
import re
from datetime import datetime
from typing import List, Dict, Any

from .config import get_backup_path, get_base_path
from .audit_log import append_fs_audit_event


_SLASH_RE = re.compile(r"/+")


def _norm_rel(p: str) -> str:
    s = str(p or "").strip().replace("\\", "/")
    s = _SLASH_RE.sub("/", s).lstrip("/")
    if not s:
        return ""
    parts = [x for x in s.split("/") if x not in ("", ".")]
    if any(x == ".." for x in parts):
        return ""
    return "/".join(parts)


def _audit_paths_from_metadata(metadata: Dict[str, Any]) -> List[str]:
    md = metadata or {}
    out: List[str] = []

    # ✅ 优先：显式提供
    if isinstance(md.get("audit_paths"), list):
        out.extend([str(x) for x in md.get("audit_paths") if str(x or "").strip()])
    if isinstance(md.get("paths"), list):
        out.extend([str(x) for x in md.get("paths") if str(x or "").strip()])

    # ✅ 常见字段兜底：dir_move_path / file_move_path / file_delete 等
    for k in ("old_path", "filename", "path", "src"):
        v = md.get(k)
        if isinstance(v, str) and v.strip():
            out.append(v.strip())

    # normalize + 去重
    seen = set()
    cleaned: List[str] = []
    for x in out:
        rp = _norm_rel(x)
        if not rp:
            continue
        if rp in seen:
            continue
        seen.add(rp)
        cleaned.append(rp)

    return cleaned


def create_backup(
    user_id: str,
    email: str,
    name: str,
    operation: str,
    affected_files: List[str],
    metadata: Dict[str, Any] = None
) -> Dict[str, Any]:
    """
    创建备份（操作前调用）

    Args:
        user_id: 用户ID
        email: 邮箱
        name: 用户名
        operation: 操作名称（file_create/update/delete等）
        affected_files: 受影响的文件路径列表（通常是绝对路径；目录场景可能为空）
        metadata: 额外元数据（可选）

    Returns:
        备份信息字典
    """
    try:
        backup_path = get_backup_path(user_id, email, name)
        os.makedirs(backup_path, exist_ok=True)

        # 生成备份ID
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_id = f"{timestamp}_{operation}"
        backup_dir = f"{backup_path}/{backup_id}"

        # 创建备份目录
        os.makedirs(backup_dir, exist_ok=True)

        # 备份文件（仅对真实文件 copy2；目录会被自动跳过）
        backed_up_files = []
        for file_path in affected_files:
            try:
                if os.path.exists(file_path) and os.path.isfile(file_path):
                    base_path = get_base_path(user_id, email, name)
                    rel_path = os.path.relpath(file_path, base_path)
                    backup_file_path = os.path.join(backup_dir, rel_path)

                    os.makedirs(os.path.dirname(backup_file_path), exist_ok=True)
                    shutil.copy2(file_path, backup_file_path)
                    backed_up_files.append({
                        "original": file_path,
                        "backup": backup_file_path,
                        "size": os.path.getsize(file_path)
                    })
            except Exception:
                # 单个文件备份失败不阻断（与原逻辑一致）
                continue

        # 创建备份元数据
        backup_metadata = {
            "backup_id": backup_id,
            "timestamp": datetime.now().isoformat(),
            "operation": operation,
            "user_id": user_id,
            "files_count": len(backed_up_files),
            "files": backed_up_files,
            "metadata": metadata or {},
            "restorable": True
        }

        # 保存元数据
        meta_file = f"{backup_dir}/backup_metadata.json"
        with open(meta_file, 'w', encoding='utf-8') as f:
            json.dump(backup_metadata, f, ensure_ascii=False, indent=2)

        # ✅ 审计 paths 生成：优先来自备份文件；若为空则从 metadata 推导（解决 dir_move_path paths=[]）
        base_path = get_base_path(user_id, email, name)
        audit_paths = []
        if backed_up_files:
            audit_paths = [
                os.path.relpath(x["original"], base_path).replace("\\", "/")
                for x in backed_up_files
                if x.get("original")
            ]
            audit_paths = [_norm_rel(p) for p in audit_paths]
            audit_paths = [p for p in audit_paths if p]
        else:
            audit_paths = _audit_paths_from_metadata(metadata or {})

        append_fs_audit_event(
            user_id=user_id,
            email=email,
            name=name,
            event={
                "event": "backup_created",
                "operation": operation,
                "backup_id": backup_id,
                "files_count": len(backed_up_files),
                "paths": audit_paths,
                "metadata": metadata or {},
            },
        )

        print(f"[BACKUP] 创建备份成功: {backup_id}, {len(backed_up_files)} 文件")

        return {
            "success": True,
            "backup_id": backup_id,
            "backup_path": backup_dir,
            "files_count": len(backed_up_files)
        }

    except Exception as e:
        print(f"[BACKUP] 备份失败: {str(e)}")
        return {"success": False, "error": str(e)}


def list_backups(
    user_id: str,
    email: str,
    name: str,
    limit: int = 20
) -> List[Dict[str, Any]]:
    try:
        backup_path = get_backup_path(user_id, email, name)
        if not os.path.exists(backup_path):
            return []

        backups = []
        for backup_id in sorted(os.listdir(backup_path), reverse=True):
            backup_dir = f"{backup_path}/{backup_id}"
            meta_file = f"{backup_dir}/backup_metadata.json"
            if os.path.exists(meta_file):
                with open(meta_file, 'r', encoding='utf-8') as f:
                    metadata = json.load(f)
                    backups.append(metadata)
            if len(backups) >= limit:
                break
        return backups
    except Exception as e:
        print(f"[BACKUP] 列出备份失败: {str(e)}")
        return []


def restore_backup(
    user_id: str,
    email: str,
    name: str,
    backup_id: str
) -> Dict[str, Any]:
    try:
        backup_path = get_backup_path(user_id, email, name)
        backup_dir = f"{backup_path}/{backup_id}"
        meta_file = f"{backup_dir}/backup_metadata.json"

        if not os.path.exists(meta_file):
            return {"success": False, "message": f"备份不存在: {backup_id}"}

        with open(meta_file, 'r', encoding='utf-8') as f:
            metadata = json.load(f)

        if not metadata.get('restorable'):
            return {"success": False, "message": "该备份不可恢复"}

        restored_count = 0
        for file_info in metadata.get('files', []):
            backup_file = file_info.get('backup')
            original_file = file_info.get('original')
            if backup_file and original_file and os.path.exists(backup_file):
                os.makedirs(os.path.dirname(original_file), exist_ok=True)
                shutil.copy2(backup_file, original_file)
                restored_count += 1

        return {
            "success": True,
            "message": f"恢复成功: {restored_count}/{len(metadata.get('files', []))} 文件",
            "backup_id": backup_id,
            "restored_count": restored_count
        }

    except Exception as e:
        return {"success": False, "message": f"恢复失败: {str(e)}"}


def should_backup(file_path: str, user_id: str, email: str, name: str) -> bool:
    """
    判断文件是否需要备份（对齐 agent-native）：

    ✅ agent_files/：需要备份（写/删/改都可回滚）
    ✅ storage/：需要备份
    """
    base_path = get_base_path(user_id, email, name)

    try:
        p = os.path.normpath(os.path.abspath(file_path))
        b = os.path.normpath(os.path.abspath(base_path))
    except Exception:
        return True

    if not (p.startswith(b + os.sep) or p == b):
        return True

    agent_prefix = os.path.normpath(os.path.join(b, "agent_files"))
    if p.startswith(agent_prefix + os.sep) or p == agent_prefix:
        return True

    storage_prefix = os.path.normpath(os.path.join(b, "storage"))
    if p.startswith(storage_prefix + os.sep) or p == storage_prefix:
        return True

    return False

