#!/usr/bin/env python3
"""
NISB Query - 三层统一查询
Phase 2.9.7 多用户版本
Phase 6.0 修复：多用户隔离完善
"""

import os
import json
from datetime import datetime
import sys
sys.path.insert(0, '/srv')

from core.storage import load_jsonl

from .case_query import nisb_case_query
from core.user_context import auto_user_context, get_user_ctx

@auto_user_context
def nisb_unified_query(args: dict) -> dict:
    """三层统一查询：理论+个人+现实"""
    
    # ✅ Phase 6.0修复：从context获取user数据
    user_ctx = get_user_ctx()
    base_path = user_ctx.base
    user_id = user_ctx.user_id
   
    concept = args.get("concept", "")
    max_per_layer = int(args.get("max_results_per_layer", 5))
    min_relevance = float(args.get("min_relevance", 0.5))
    
    if not concept.strip():
        return {
            "status": "error",
            "message": "❌ 概念名称不能为空"
        }
    
    results = {
        "kb_bookmarks": [],
        "sense_records": [],
        "cases": [],
        "total": 0
    }
    
    # ===== 理论层：查询KB书签（模糊匹配）⭐ =====
    theory_results = []
    bookmarks_file = f"{base_path}/storage/kb_bookmarks/bookmarks.jsonl"
    if os.path.exists(bookmarks_file):
        bookmarks = load_jsonl(bookmarks_file)
        concept_words = concept.split()
        
        for bm in bookmarks:
            tags = bm.get("tags", [])
            matched = False
            for tag in tags:
                if concept == tag:
                    matched = True
                    break
                elif concept in tag or tag in concept:
                    matched = True
                    break
                else:
                    for word in concept_words:
                        if len(word) >= 2 and word in tag:
                            matched = True
                            break
                    if matched:
                        break
            
            if matched and len(theory_results) < max_per_layer:
                theory_results.append({
                    "type": "bookmark",
                    "id": bm["id"],
                    "kbname": bm.get("kbname"),
                    "filename": bm.get("filename"),
                    "snippet": bm.get("snippet", "")[:200]
                })
    
    # ===== 个人层：查询笔记（模糊匹配）⭐ =====
    personal_results = []
    quick_notes_dir = f"{base_path}/storage/raw/quick_notes"
    if os.path.exists(quick_notes_dir):
        concept_words = concept.split()
        
        for filename in os.listdir(quick_notes_dir):
            if filename.endswith('.jsonl'):
                notes = load_jsonl(f"{quick_notes_dir}/{filename}")
                for note in notes:
                    content = note.get("content", "")
                    matched = False
                    
                    if concept in content:
                        matched = True
                    elif concept.lower() in content.lower():
                        matched = True
                    else:
                        for word in concept_words:
                            if len(word) >= 2 and (word in content or word.lower() in content.lower()):
                                matched = True
                                break
                    
                    if matched:
                        personal_results.append({
                            "type": "note",
                            "id": note["id"],
                            "content": content[:200],
                            "timestamp": note.get("timestamp")
                        })
        
        personal_results = personal_results[:max_per_layer]
    
    # ===== 现实层：查询案例（智能评分 + 模糊匹配）⭐ =====
    case_query_result = nisb_case_query({
        "user_id": user_id,
        "_librechat_email": args.get("_librechat_email"),
        "_librechat_name": args.get("_librechat_name"),
        "concept_name": concept,
        "limit": max_per_layer,
        "min_relevance": min_relevance
    })
    cases_results = case_query_result.get("results", [])
    
    # ===== 综合摘要 =====
    synthesis = f"关于「{concept}」，找到：\n"
    synthesis += f"- 理论层（KB书签）：{len(theory_results)}个\n"
    synthesis += f"- 个人层（笔记）：{len(personal_results)}个\n"
    synthesis += f"- 现实层（案例）：{len(cases_results)}个\n\n"
    
    if theory_results:
        synthesis += "理论权威观点来自书库原文，"
    if personal_results:
        synthesis += "结合了您的个人思考，"
    if cases_results:
        synthesis += "并关联了真实案例验证。"
    
    lines = [f"🔍 「{concept}」三层知识查询结果\n"]
    
    lines.append("📚 理论层（KB书签）：")
    if theory_results:
        for i, t in enumerate(theory_results, 1):
            bookmark_id = t.get('id', 'unknown')
            lines.append(f"  {i}. {t['kbname']}/{t['filename'][:50]}...")
            lines.append(f"      📌 书签ID: {bookmark_id}")
            lines.append(f"      💡 回溯命令: nisb_kb_recall(bookmark_id='{bookmark_id}')")
    else:
        lines.append("  （暂无）")
    
    lines.append("\n💭 个人层（笔记）：")
    if personal_results:
        for i, p in enumerate(personal_results, 1):
            note_id = p.get('id', 'unknown')
            lines.append(f"  {i}. {p['content'][:50]}... ({p['timestamp'][:10]})")
            lines.append(f"      📌 笔记ID: {note_id}")
            lines.append(f"      💡 回溯命令: nisb_sense_recall_note(note_id='{note_id}')")
    else:
        lines.append("  （暂无）")
    
    lines.append("\n🌍 现实层（案例）：")
    if cases_results:
        for i, c in enumerate(cases_results, 1):
            case_id = c.get('id', 'unknown')
            title = c.get('title', 'Untitled')
            url = c.get('url', '')
            source = c['source_name']
            
            if len(title) > 60:
                title_display = title[:57] + "..."
            else:
                title_display = title
            
            lines.append(f"  {i}. {title_display} ({source})")
            lines.append(f"      🔗 链接: {url}")
            lines.append(f"      📌 案例ID: {case_id}")
            lines.append(f"      💡 回溯命令: nisb_case_recall(case_id='{case_id}')")
    else:
        lines.append("  （暂无）")
    
    lines.append(f"\n✨ 综合：\n{synthesis}")
    
    message = "\n".join(lines)
    
    return {
        "status": "success",
        "theory": theory_results,
        "personal": personal_results,
        "cases": cases_results,
        "synthesis": synthesis,
        "message": message
    }

