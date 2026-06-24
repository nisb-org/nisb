"""
管理工具（增强版）
⭐⭐⭐ 添加备份恢复功能
"""

import os
import json
from datetime import datetime
from typing import Dict, Any
from tools.filesystem.config import get_backup_path, get_log_path
from tools.filesystem.backup import list_backups, restore_backup


def nisb_admin_list_backups(args: dict) -> Dict[str, Any]:
    """
    查看所有备份（符合NISB规范）
    ⭐⭐⭐ 新增功能
    """
    try:
        # ⭐ 提取多用户参数
        user_id = args.get("user_id", "user_001")
        email = args.get("_librechat_email")
        name = args.get("_librechat_name")
        limit = args.get("limit", 10)
        
        backups = list_backups(user_id, email, name, limit)
        
        if not backups:
            return {
                "success": True,
                "message": "📦 当前没有备份记录",
                "backups": []
            }
        
        # 构建消息
        msg = f"📦 备份列表（共{len(backups)}个）\n\n"
        for backup in backups:
            msg += f"🆔 {backup['backup_id']}\n"
            msg += f"   📅 时间：{backup['timestamp'][:19]}\n"
            msg += f"   📋 操作：{backup['operation']}\n"
            msg += f"   📁 文件数：{backup['files_count']}\n"
            
            # 显示文件名
            if backup.get('metadata', {}).get('filename'):
                msg += f"   📄 {backup['metadata']['filename']}\n"
            
            msg += f"   🔄 可恢复：{'是' if backup.get('restorable') else '否'}\n"
            msg += "\n"
        
        msg += f"💡 恢复备份：nisb_admin_rollback(backup_id='备份ID')"
        
        return {
            "success": True,
            "message": msg,
            "backups": backups
        }
    
    except Exception as e:
        return {"success": False, "message": f"❌ 获取失败：{str(e)}"}


def nisb_admin_rollback(args: dict) -> Dict[str, Any]:
    """
    恢复备份（符合NISB规范）
    ⭐⭐⭐ 新增功能
    """
    try:
        # ⭐ 提取多用户参数
        user_id = args.get("user_id", "user_001")
        email = args.get("_librechat_email")
        name = args.get("_librechat_name")
        backup_id = args.get("backup_id")
        
        if not backup_id:
            return {"success": False, "message": "❌ 必须提供 backup_id"}
        
        # 执行恢复
        result = restore_backup(user_id, email, name, backup_id)
        
        if result.get('success'):
            msg = f"✅ 备份恢复成功\n\n"
            msg += f"🆔 备份ID：{backup_id}\n"
            msg += f"📁 恢复文件：{result.get('restored_count')}\n"
            msg += f"\n💡 请刷新文件列表查看恢复的文件"
            
            return {
                "success": True,
                "message": msg,
                "backup_id": backup_id,
                "restored_count": result.get('restored_count')
            }
        else:
            return result
    
    except Exception as e:
        return {"success": False, "message": f"❌ 恢复失败：{str(e)}"}


def nisb_admin_view_logs(args: dict) -> Dict[str, Any]:
    """
    查看操作日志（符合NISB规范）
    """
    try:
        # ⭐ 提取多用户参数
        user_id = args.get("user_id", "user_001")
        email = args.get("_librechat_email")
        name = args.get("_librechat_name")
        
        date = args.get("date")
        limit = args.get("limit", 20)
        
        log_path = get_log_path(user_id, email, name)
        
        if not date:
            date = datetime.now().strftime('%Y-%m-%d')
        
        log_file = f"{log_path}/{date}.jsonl"
        
        if not os.path.exists(log_file):
            return {
                "success": True,
                "message": f"📅 {date} 无操作日志",
                "logs": []
            }
        
        # 读取日志
        logs = []
        with open(log_file, 'r', encoding='utf-8') as f:
            for line in f:
                logs.append(json.loads(line))
        
        logs = logs[-limit:]  # 最近N条
        
        # 构建消息
        msg = f"📋 操作日志（{date}）共{len(logs)}条\n\n"
        for log in logs:
            msg += f"• {log['timestamp'][11:19]} - {log['operation']}\n"
            msg += f"  状态：{log['status']}\n"
            
            # 显示文件名
            if log.get('data', {}).get('filename'):
                msg += f"  文件：{log['data']['filename']}\n"
            
            # ⭐ 显示是否自动备份
            if log.get('data', {}).get('is_storage'):
                msg += f"  🛡️ 已自动备份\n"
            
            if log.get('data', {}).get('file_id'):
                msg += f"  ID：{log['data']['file_id']}\n"
            
            msg += "\n"
        
        return {
            "success": True,
            "message": msg,
            "logs": logs
        }
    
    except Exception as e:
        import traceback
        return {"success": False, "message": f"❌ 获取失败：{str(e)}\n\n{traceback.format_exc()}"}

