#!/usr/bin/env python3
"""
NISB Query - 案例查询
Phase 2.9.7 多用户版本
Phase 6.0 修复：多用户隔离完善
"""

import os
import json
from datetime import datetime
import sys
sys.path.insert(0, '/srv')

from core.storage import load_json
from core.user_context import auto_user_context, get_user_ctx

@auto_user_context
def nisb_case_query(args: dict) -> dict:
    """查询案例库（Phase 2.5.1增强版：模糊匹配 + 智能排序）"""
    
    # ✅ Phase 6.0修复：从context获取user数据
    user_ctx = get_user_ctx()
    base_path = user_ctx.base
    
    concept_name = args.get("concept_name", "")
    date_range = args.get("date_range", None)
    min_relevance = float(args.get("min_relevance", 0.5))
    limit = int(args.get("limit", 10))
    
    index_file = f"{base_path}/storage/cases/index/cases.index.json"
    index = load_json(index_file)
    
    if not index or not index.get("cases"):
        return {
            "status": "success",
            "results": [],
            "total": 0,
            "message": "📭 案例库为空，使用 nisb_case_save 保存第一个案例"
        }
    
    results = []
    for case_id, case_info in index["cases"].items():
        relevance_score = 0.0
        matched_concepts = 0
        total_concepts = len(case_info.get("concepts", []))
        
        if concept_name:
            concept_words = concept_name.split()
            
            for concept in case_info.get("concepts", []):
                if concept_name == concept:
                    relevance_score += 1.0
                    matched_concepts += 1
                elif concept_name in concept or concept in concept_name:
                    relevance_score += 0.5
                    matched_concepts += 1
                else:
                    for word in concept_words:
                        if len(word) >= 2 and word in concept:
                            relevance_score += 0.3
                            matched_concepts += 1
                            break
        else:
            relevance_score = 1.0
            matched_concepts = total_concepts
        
        if matched_concepts == 0:
            continue
        
        quality = case_info.get("quality_score", 0)
        if quality < min_relevance:
            continue
        
        concept_match_score = relevance_score / max(total_concepts, 1) * 0.5
        quality_score = quality * 0.3
        
        related_count = len(case_info.get("related_bookmarks", [])) + \
                       len(case_info.get("related_notes", []))
        relation_score = min(related_count / 10, 1.0) * 0.1
        
        try:
            case_date = datetime.fromisoformat(case_info.get("created_at", "").replace('Z', ''))
            days_old = (datetime.now() - case_date).days
            freshness = 1.0 / (1 + days_old / 30)
            freshness_score = freshness * 0.1
        except:
            freshness_score = 0.05
        
        final_score = concept_match_score + quality_score + relation_score + freshness_score
        
        results.append({
            **case_info,
            "relevance": final_score,
            "matched_concepts": matched_concepts
        })
    
    results.sort(key=lambda x: x["relevance"], reverse=True)
    results = results[:limit]
    
    if not results:
        message = f"🔍 未找到匹配的案例\n"
        if concept_name:
            message += f"   概念：{concept_name}\n"
        message += f"   质量阈值：{min_relevance}"
    else:
        lines = [f"🔍 找到 {len(results)} 个匹配案例：\n"]
        for i, r in enumerate(results, 1):
            title = r.get('title', '').strip()
            summary = r.get('summary', '').strip()
            url = r.get('url', '')
            
            if title and len(title) > 3:
                title_display = title
            elif summary and len(summary) > 3:
                title_display = summary
            else:
                if url:
                    url_path = url.rstrip('/').split('/')[-1]
                    url_path = url_path.split('?')[0].split('#')[0]
                    if '.' in url_path:
                        url_path = url_path.rsplit('.', 1)[0]
                    title_display = url_path.replace('-', ' ').replace('_', ' ')
                    title_display = ' '.join(word.capitalize() for word in title_display.split())
                else:
                    title_display = "Untitled"
            
            if len(title_display) > 70:
                title_display = title_display[:67] + "..."
            
            if summary and summary != title:
                summary_display = summary
            elif title and len(title) > 20:
                summary_display = title
            else:
                summary_display = "（无概括）"
            
            if len(summary_display) > 150:
                summary_display = summary_display[:147] + "..."
            
            lines.append(
                f"{i}. {title_display}\n"
                f"   来源：{r['source_name']}\n"
                f"   链接：{url}\n"
                f"   日期：{r['published_at'][:10]}\n"
                f"   质量：{r['quality_score']:.2f}\n"
                f"   概念：{', '.join(r.get('concepts', [])[:5])}\n"
                f"   核心内容：{summary_display}"
            )
        message = "\n\n".join(lines)
    
    return {
        "status": "success",
        "results": results,
        "total": len(results),
        "message": message
    }

