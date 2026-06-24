#!/usr/bin/env python3
"""
NISB Query - 智能统一搜索
Phase 2.9.7 多用户版本
Phase 6.0 修复：多用户隔离完善
"""

import os
import sys
sys.path.insert(0, '/srv')

from core.storage import load_jsonl
from core.user_context import auto_user_context, get_user_ctx

@auto_user_context
def nisb_smart_search(args):
    """智能搜索 - 自动搜索L1+L2+KB所有层"""
    
    # ✅ Phase 6.0修复：从context获取user数据
    user_ctx = get_user_ctx()
    base_path = user_ctx.base
       
    query = args.get("query", "")
    limit = args.get("limit", 10)

    if not query:
        return {"message": "❌ 请提供查询关键词"}

    results = {
        "kb_bookmarks": [],
        "sense_records": [],
        "total": 0
    }

    # 1. 搜索KB书签
    bookmarks_file = f"{base_path}/storage/kb_bookmarks/bookmarks.jsonl"
    if os.path.exists(bookmarks_file):
        bookmarks = load_jsonl(bookmarks_file)
        
        for bm in bookmarks:
            tags = bm.get("tags", [])
            matched = False
            for tag in tags:
                if query in tag or tag in query:
                    matched = True
                    break
            
            if matched and len(results["kb_bookmarks"]) < limit:
                results["kb_bookmarks"].append({
                    "type": "bookmark",
                    "id": bm["id"],
                    "kbname": bm.get("kbname"),
                    "filename": bm.get("filename"),
                    "snippet": bm.get("snippet", "")[:200]
                })

    # 2. 搜索L1+L2层笔记
    quick_notes_dir = f"{base_path}/storage/raw/quick_notes"
    if os.path.exists(quick_notes_dir):
        for filename in os.listdir(quick_notes_dir):
            if filename.endswith('.jsonl'):
                notes = load_jsonl(f"{quick_notes_dir}/{filename}")
                for note in notes:
                    content = note.get("content", "")
                    if query in content or query.lower() in content.lower():
                        results["sense_records"].append({
                            "type": "note",
                            "id": note["id"],
                            "content": content[:200],
                            "timestamp": note.get("timestamp")
                        })
        
        results["sense_records"] = results["sense_records"][:limit]

    # 3. 计算总数
    results["total"] = len(results["kb_bookmarks"]) + len(results["sense_records"])

    # 4. 格式化输出
    if results["total"] == 0:
        return {
            "message": f"🔍 未找到关于「{query}」的积累\n\n💡 提示：\n- 试试其他关键词\n- 或者先用KB查询并保存书签\n- 或者记录一次讨论"
        }

    text = f"🔍 找到 {results['total']} 条关于「{query}」的积累\n\n"

    # KB书签
    if results["kb_bookmarks"]:
        text += f"【📚 KB书签】({len(results['kb_bookmarks'])}个)\n\n"
        for i, bm in enumerate(results["kb_bookmarks"][:5], 1):
            bookmark_id = bm.get('id', bm.get('bookmark_id', 'unknown'))
            filename = bm.get('filename', 'Unknown')
            
            text += f"{i}. 书签ID: {bookmark_id}\n"
            text += f"   文件: {filename[:80]}{'...' if len(filename) > 80 else ''}\n"
            
            tags = bm.get('tags', [])
            if tags:
                text += f"   标签: {', '.join(tags[:5])}\n"
            
            query_text = bm.get('query', '')
            if query_text:
                text += f"   查询: {query_text}\n"
            
            text += f"   💡 回溯：nisb_kb_recall(bookmark_id='{bookmark_id}')\n\n"

    # L1+L2对话记录
    if results["sense_records"]:
        text += f"【💬 对话记录】({len(results['sense_records'])}条)\n\n"
        for i, rec in enumerate(results["sense_records"][:3], 1):
            note_id = rec.get('id', 'unknown')
            content = rec.get('content', '')
            text += f"{i}. 笔记ID: {note_id}\n"
            text += f"   内容: {content[:50]}...\n"

            timestamp = rec.get('timestamp', '')
            if timestamp:
                text += f"   时间: {timestamp[:10]}\n"

            text += "\n"

    # 智能建议
    text += "\n💡 智能建议:\n"
    if results["kb_bookmarks"] and not results["sense_records"]:
        text += "- 试试用「记录」保存今天的讨论\n"
    elif not results["kb_bookmarks"] and results["sense_records"]:
        text += f"- 试试在KB中搜索「{query}」并保存书签\n"
    elif results["kb_bookmarks"] and results["sense_records"]:
        text += f"- 用「{query}的网络」查看跨学科关联\n"

    return {
        "message": text,
        "raw": results
    }

