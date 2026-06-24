#!/usr/bin/env python3
"""
NISB Recall - 笔记回溯
Phase 2.9.7 多用户版本
从 tools/sense.py 拆分

⭐ Phase 2.9新增：集成批注显示
Phase 6.0 修复：多用户隔离完善
"""

from datetime import datetime
import sys
from core.user_context import auto_user_context, get_user_ctx
sys.path.insert(0, '/srv')

from core.storage import recall_note, get_user_base_path, ensure_user_directory

@auto_user_context
def nisb_sense_recall_note(args: dict) -> dict:
    """
    L1工具：回溯笔记完整内容（类似nisb_kb_recall）
    
    参数：
        note_id: string（笔记ID）
        user_id: string（系统注入）
        _librechat_email: string（可选）
        _librechat_name: string（可选）
        _base_path: string（系统注入）
    
    返回：
        {status, note: {id, timestamp, content, tags}, message}
    
    ⭐ Phase 2.9新增：自动显示批注
    ⭐ Phase 2.9.7新增：多用户支持
    ⭐ Phase 6.0新增：完整user_context获取
    """
    
    # ✅ Phase 6.0修复：从context获取user数据
    user_ctx = get_user_ctx()
    base_path = user_ctx.base
    
    note_id = args.get("note_id", "")
    
    if not note_id:
        return {
            "status": "error",
            "message": "❌ 缺少note_id参数"
        }
    
    try:
        note = recall_note(base_path, note_id)
        
        if not note:
            return {
                "status": "error",
                "message": f"❌ 找不到笔记：{note_id}\n"
                           f"💡 使用 nisb_sense_list_notes 查看所有笔记"
            }
        
        # 格式化输出
        timestamp = note.get("timestamp", "")
        content = note.get("content", "")
        tags = note.get("tags", [])
        
        message = (
            f"📝 笔记详情\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"📅 时间：{timestamp}\n"
            f"🔗 ID：{note_id}\n"
            f"🏷️ 标签：{', '.join([f'#{t}' for t in tags]) if tags else '无'}\n\n"
            f"📖 内容：\n{content}\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"（内容长度：{len(content)}字符）"
        )
        
        # ⭐⭐⭐ Phase 2.9新增：显示批注（如果有）
        try:
            from tools.annotate.get_annotations import get_target_annotations, format_annotations
            
            annotations = get_target_annotations(base_path, note_id)
            if annotations:
                message += format_annotations(annotations)
        except Exception as e:
            print(f"[WARN] 获取批注失败: {e}", file=sys.stderr)
        
        return {
            "status": "success",
            "note": note,
            "message": message
        }
        
    except Exception as e:
        return {
            "status": "error",
            "message": f"❌ 回溯失败：{str(e)}"
        }

