#!/usr/bin/env python3
"""
NISB Recall - 案例回溯
Phase 2.9.7 多用户版本
Phase 6.0 修复：多用户隔离完善
"""

import os
import json
from datetime import datetime
import sys
sys.path.insert(0, '/srv')

from core.storage import load_json, load_jsonl
from core.user_context import auto_user_context, get_user_ctx

@auto_user_context
def nisb_case_recall(args: dict) -> dict:
    """通过案例ID回溯案例完整内容"""
    
    # ✅ Phase 6.0修复：从context获取user数据
    user_ctx = get_user_ctx()
    base_path = user_ctx.base
    
    case_id = args.get("case_id", "")
    
    if not case_id:
        return {
            "status": "error",
            "message": "❌ 缺少案例ID"
        }
    
    index_file = f"{base_path}/storage/cases/index/cases.index.json"
    index = load_json(index_file)
    
    if not index or case_id not in index.get("cases", {}):
        return {
            "status": "error",
            "message": f"❌ 未找到案例: {case_id}"
        }
    
    case_meta = index["cases"][case_id]
    
    timestamp = case_meta.get("created_at") or case_meta.get("published_at", "")
    if not timestamp:
        return {
            "status": "error",
            "message": f"❌ 案例元数据损坏（缺少时间戳字段）"
        }
    
    date_part = timestamp[:10]
    year_month = date_part[:7]
    
    case_file = f"{base_path}/storage/cases/by_date/{year_month}/cases_{date_part.replace('-', '')}.jsonl"
    
    if not os.path.exists(case_file):
        return {
            "status": "error",
            "message": f"❌ 案例文件不存在: {case_file}"
        }
    
    case_full = None
    cases = load_jsonl(case_file)
    for c in cases:
        if c.get("id") == case_id:
            case_full = c
            break
    
    if not case_full:
        return {
            "status": "error",
            "message": f"❌ 案例数据不完整"
        }
    
    title = case_full.get("title", "Untitled")
    url = case_full.get("url", "")
    source = case_full.get("source_name", "Unknown")
    published = case_full.get("published_at", "")[:10] if case_full.get("published_at") else "未知"
    quality = case_full.get("quality_score", 0)
    
    mapped_concepts = case_full.get("mapped_concepts", [])
    if isinstance(mapped_concepts, list) and len(mapped_concepts) > 0:
        concepts = []
        for c in mapped_concepts:
            if isinstance(c, dict):
                concept_name = c.get("concept_name", "")
                if concept_name:
                    concepts.append(concept_name)
            else:
                concepts.append(str(c))
    else:
        concepts = []
    
    concepts_str = ", ".join(concepts) if concepts else "（无）"
    
    related_bookmarks = case_full.get("related_bookmarks", [])
    related_notes = case_full.get("related_notes", [])
    
    full_text = case_full.get("full_text", "")
    text_length = len(full_text)
    
    if text_length > 0:
        if text_length > 500:
            text_preview = full_text[:500] + "..."
            text_info = f"（正文长度：{text_length}字符，以下是前500字）\n\n{text_preview}"
        else:
            text_info = full_text
    else:
        text_info = "（无正文）"
    
    lines = [
        f"📄 案例详情\n",
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        f"",
        f"📌 标题：{title}",
        f"🔗 链接：{url}",
        f"📰 来源：{source}",
        f"📅 发布：{published}",
        f"⭐ 质量：{quality:.2f}",
        f"",
        f"🏷️ 概念：{concepts_str}",
        f"",
        f"🔗 关联：",
        f"  - 书签：{len(related_bookmarks)}个",
        f"  - 笔记：{len(related_notes)}个",
        f"",
        f"📝 正文：",
        text_info
    ]
    
    message = "\n".join(lines)
    
    try:
        from tools.annotate.get_annotations import get_target_annotations, format_annotations
        
        annotations = get_target_annotations(base_path, case_id)
        if annotations:
            message += format_annotations(annotations)
    except Exception as e:
        print(f"[WARN] 获取批注失败: {e}", file=sys.stderr)
    
    return {
        "status": "success",
        "case": case_full,
        "message": message
    }

