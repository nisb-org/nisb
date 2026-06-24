"""
批量操作模块（符合NISB规范）
⭐⭐⭐ Phase 3.5.1.2: 修复批量备份问题
"""

import os
from typing import Dict, Any, List
from .core import nisb_file_read, nisb_file_delete, nisb_file_update
from .config import get_base_path
from .backup import create_backup, should_backup
from .utils import load_metadata


def nisb_file_read_multiple(args: dict) -> Dict[str, Any]:
    """
    批量读取文件（符合NISB规范）
    """
    try:
        # ⭐ 提取多用户参数
        user_id = args.get("user_id", "user_001")
        email = args.get("_librechat_email")
        name = args.get("_librechat_name")
        
        file_ids = args.get("file_ids", [])
        
        results = []
        for file_id in file_ids:
            read_args = {
                "user_id": user_id,
                "_librechat_email": email,
                "_librechat_name": name,
                "file_id": file_id
            }
            result = nisb_file_read(read_args)
            results.append(result)
        
        success_count = sum(1 for r in results if r.get('success'))
        
        return {
            "success": True,
            "message": f"✅ 批量读取完成\n\n成功：{success_count}/{len(file_ids)}",
            "files": results
        }
    
    except Exception as e:
        return {"success": False, "message": f"❌ 批量读取失败：{str(e)}"}


def nisb_file_batch_delete(args: dict) -> Dict[str, Any]:
    """
    批量删除文件（符合NISB规范）
    ⭐⭐⭐ Phase 3.5.1.2: 批量操作创建单个备份
    """
    try:
        # ⭐ 提取多用户参数
        user_id = args.get("user_id", "user_001")
        email = args.get("_librechat_email")
        name = args.get("_librechat_name")
        
        file_ids = args.get("file_ids", [])
        permanent = args.get("permanent", False)
        
        if not file_ids:
            return {"success": False, "message": "❌ 未提供file_ids参数"}
        
        # ⭐⭐⭐ 步骤1：收集所有要删除的文件路径
        files_to_delete = []
        valid_file_ids = []
        
        for file_id in file_ids:
            metadata = load_metadata(user_id, file_id, email, name)
            if metadata and os.path.exists(metadata['file_path']):
                files_to_delete.append(metadata['file_path'])
                valid_file_ids.append(file_id)
        
        if not files_to_delete:
            return {"success": False, "message": "❌ 没有找到有效的文件"}
        
        # ⭐⭐⭐ 步骤2：创建单个批量备份（包含所有文件）
        backup_created = False
        if should_backup(files_to_delete[0], user_id, email, name):
            backup_result = create_backup(
                user_id, email, name,
                operation="batch_delete",
                affected_files=files_to_delete,  # ⭐ 一次性传入所有文件
                metadata={
                    "file_ids": valid_file_ids,
                    "count": len(valid_file_ids),
                    "permanent": permanent
                }
            )
            backup_created = backup_result.get('success', False)
            if backup_created:
                print(f"[BACKUP] 批量删除前备份: {backup_result.get('backup_id')}, {len(files_to_delete)} 文件")
        
        # ⭐⭐⭐ 步骤3：删除文件（跳过单独的备份）
        results = []
        for file_id in valid_file_ids:
            delete_args = {
                "user_id": user_id,
                "_librechat_email": email,
                "_librechat_name": name,
                "file_id": file_id,
                "permanent": permanent,
                "_skip_backup": True  # ⭐ 跳过单独备份
            }
            result = nisb_file_delete(delete_args)
            results.append(result)
        
        success_count = sum(1 for r in results if r.get('success'))
        
        # 构建返回消息
        msg_lines = [
            "✅ 批量删除完成\n",
            f"成功：{success_count}/{len(valid_file_ids)}"
        ]
        
        if backup_created:
            msg_lines.append(f"🛡️ 已创建批量备份（{len(files_to_delete)} 个文件）")
        
        return {
            "success": True,
            "message": "\n".join(msg_lines),
            "results": results,
            "backup_created": backup_created
        }
    
    except Exception as e:
        import traceback
        return {
            "success": False,
            "message": f"❌ 批量删除失败：{str(e)}\n\n{traceback.format_exc()}"
        }


def nisb_file_batch_tag(args: dict) -> Dict[str, Any]:
    """
    批量打标签（符合NISB规范）
    """
    try:
        # ⭐ 提取多用户参数
        user_id = args.get("user_id", "user_001")
        email = args.get("_librechat_email")
        name = args.get("_librechat_name")
        
        file_ids = args.get("file_ids", [])
        tags = args.get("tags", [])
        
        results = []
        for file_id in file_ids:
            update_args = {
                "user_id": user_id,
                "_librechat_email": email,
                "_librechat_name": name,
                "file_id": file_id,
                "tags": tags
            }
            result = nisb_file_update(update_args)
            results.append(result)
        
        success_count = sum(1 for r in results if r.get('success'))
        
        return {
            "success": True,
            "message": f"✅ 批量打标签完成\n\n成功：{success_count}/{len(file_ids)}\n标签：{', '.join(tags)}",
            "results": results
        }
    
    except Exception as e:
        return {"success": False, "message": f"❌ 批量打标签失败：{str(e)}"}

