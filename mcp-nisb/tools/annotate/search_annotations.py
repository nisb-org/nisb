#!/usr/bin/env python3
"""
批注搜索功能（概念时间线查询）
Phase 2.9.7 多用户版本
Phase 6.0 修复：多用户隔离完善
"""

import os
import json
from datetime import datetime
import sys
from core.user_context import auto_user_context, get_user_ctx
sys.path.insert(0, '/srv')

@auto_user_context
def nisb_search_annotations(args: dict) -> dict:
    """搜索批注（通用搜索）"""
    
    # ✅ Phase 6.0修复：从context获取user数据
    user_ctx = get_user_ctx()
    base_path = user_ctx.base
    
    mood = args.get("mood", "")
    tag = args.get("tag", "")
    concept = args.get("concept", "")
    keyword = args.get("keyword", "")
    limit = args.get("limit", 10)
    include_deleted = args.get("include_deleted", False)
    
    try:
        from .index import load_index
        
        annotation_ids = set()
        
        if mood:
            by_mood = load_index(base_path, "by_mood")
            annotation_ids = set(by_mood.get(mood, []))
        elif tag:
            by_tag = load_index(base_path, "by_tag")
            annotation_ids = set(by_tag.get(tag, []))
        elif concept:
            by_concept = load_index(base_path, "by_concept")
            annotation_ids = set(by_concept.get(concept, []))
        elif keyword:
            annotation_ids = set()
        else:
            return {
                "status": "error",
                "message": "❌ 必须指定mood、tag、concept或keyword之一"
            }
        
        annotations = []
        anno_dir = f"{base_path}/storage/annotations/by_date"
        
        if not os.path.exists(anno_dir):
            return {
                "status": "success",
                "annotations": [],
                "message": "📊 批注目录不存在"
            }
        
        for year_month in os.listdir(anno_dir):
            anno_file = f"{anno_dir}/{year_month}/annotations.jsonl"
            if os.path.exists(anno_file):
                with open(anno_file, 'r', encoding='utf-8') as f:
                    for line in f:
                        if line.strip():
                            anno = json.loads(line)
                            
                            if anno.get("deleted", False) and not include_deleted:
                                continue
                            
                            if keyword:
                                if keyword.lower() in anno.get("content", "").lower():
                                    annotations.append(anno)
                            elif anno["annotation_id"] in annotation_ids:
                                annotations.append(anno)
        
        if not annotations:
            return {
                "status": "success",
                "annotations": [],
                "message": f"📊 未找到匹配的批注"
            }
        
        annotations.sort(key=lambda x: x["timestamp"], reverse=True)
        
        total_count = len(annotations)
        annotations = annotations[:limit]
        
        lines = [f"🔍 找到 {total_count} 条批注（显示最近{min(limit, total_count)}条）：\n"]
        
        mood_icons = {
            "担忧": "😟", "质疑": "🤔", "顿悟": "💡", "困惑": "😕",
            "兴奋": "😊", "中性": "📝", "新洞察": "⭐", "验证": "✅", "预测": "🔮"
        }
        
        for i, anno in enumerate(annotations, 1):
            timestamp = anno["timestamp"][:16]
            target_id = anno["target_id"]
            content = anno["content"][:100]
            anno_mood = anno["mood"]
            anno_mood_icon = mood_icons.get(anno_mood, "📝")
            anno_tags = anno.get("tags", [])
            anno_concepts = anno.get("concepts", [])
            meta_count = len(anno.get("meta_annotations", []))
            edit_count = len(anno.get("edit_history", []))
            
            lines.append(f"{i}. [{timestamp}] {anno_mood_icon} {anno_mood}")
            lines.append(f"   目标：{target_id}")
            lines.append(f"   内容：\"{content}{'...' if len(anno['content']) > 100 else ''}\"")
            
            if anno_concepts:
                lines.append(f"   概念：{', '.join(anno_concepts)}")
            if anno_tags:
                lines.append(f"   标签：{', '.join(anno_tags)}")
            
            extras = []
            if meta_count > 0:
                extras.append(f"💬 {meta_count}条元批注")
            if edit_count > 0:
                extras.append(f"✏️ 已修改{edit_count}次")
            if extras:
                lines.append(f"   {' | '.join(extras)}")
            
            lines.append("")
        
        return {
            "status": "success",
            "annotations": annotations,
            "total_count": total_count,
            "message": "\n".join(lines)
        }
        
    except Exception as e:
        import traceback
        return {
            "status": "error",
            "message": f"❌ 搜索失败：{str(e)}\n{traceback.format_exc()}"
        }

@auto_user_context
def nisb_concept_timeline(args: dict) -> dict:
    """概念时间线查询（⭐ Phase 2.9核心功能）"""
    
    # ✅ Phase 6.0修复：从context获取user数据
    user_ctx = get_user_ctx()
    base_path = user_ctx.base
    
    concept = args.get("concept", "")
    group_by = args.get("group_by", "month")
    
    if not concept:
        return {
            "status": "error",
            "message": "❌ 必须指定concept参数"
        }
    
    try:
        from .index import load_index
        from collections import defaultdict
        
        by_concept = load_index(base_path, "by_concept")
        annotation_ids = by_concept.get(concept, [])
        
        if not annotation_ids:
            return {
                "status": "success",
                "timeline": [],
                "message": f"📊 未找到关于「{concept}」的批注"
            }
        
        annotations = []
        anno_dir = f"{base_path}/storage/annotations/by_date"
        
        if not os.path.exists(anno_dir):
            return {
                "status": "success",
                "timeline": [],
                "message": "📊 批注目录不存在"
            }
        
        for year_month in os.listdir(anno_dir):
            anno_file = f"{anno_dir}/{year_month}/annotations.jsonl"
            if os.path.exists(anno_file):
                with open(anno_file, 'r', encoding='utf-8') as f:
                    for line in f:
                        if line.strip():
                            anno = json.loads(line)
                            if anno.get("deleted", False):
                                continue
                            if anno["annotation_id"] in annotation_ids:
                                annotations.append(anno)
        
        if not annotations:
            return {
                "status": "success",
                "timeline": [],
                "message": f"📊 未找到关于「{concept}」的有效批注（可能都已删除）"
            }
        
        annotations.sort(key=lambda x: x["timestamp"])
        
        timeline = defaultdict(list)
        
        for anno in annotations:
            timestamp = anno["timestamp"]
            dt = datetime.fromisoformat(timestamp)
            
            if group_by == "year":
                period = dt.strftime("%Y年")
            elif group_by == "quarter":
                quarter = (dt.month - 1) // 3 + 1
                period = f"{dt.year}年Q{quarter}"
            else:
                period = dt.strftime("%Y年%m月")
            
            timeline[period].append(anno)
        
        lines = [f"📊 关于「{concept}」的思想时间线\n"]
        lines.append(f"找到 {len(annotations)} 条批注，跨越 {len(timeline)} 个时间段\n")
        lines.append("━" * 60)
        
        mood_icons = {
            "担忧": "😟", "质疑": "🤔", "顿悟": "💡", "困惑": "😕",
            "兴奋": "😊", "中性": "📝", "新洞察": "⭐", "验证": "✅", 
            "预测": "🔮", "自我反思": "🔄"
        }
        
        for period in sorted(timeline.keys()):
            period_annos = timeline[period]
            lines.append(f"\n📅 {period}（{len(period_annos)}条批注）")
            
            moods = [a["mood"] for a in period_annos]
            mood_count = {}
            for m in moods:
                mood_count[m] = mood_count.get(m, 0) + 1
            dominant_mood = max(mood_count, key=mood_count.get)
            mood_icon = mood_icons.get(dominant_mood, "📝")
            
            lines.append(f"主要情绪：{mood_icon} {dominant_mood}")
            lines.append("")
            
            for i, anno in enumerate(period_annos, 1):
                date = anno["timestamp"][:10]
                content = anno["content"][:150]
                anno_mood = anno["mood"]
                anno_mood_icon = mood_icons.get(anno_mood, "📝")
                context = anno.get("context", "")
                meta_count = len(anno.get("meta_annotations", []))
                edit_count = len(anno.get("edit_history", []))
                
                lines.append(f"  {i}. [{date}] {anno_mood_icon} {anno_mood}")
                if context:
                    lines.append(f"     场景：{context}")
                lines.append(f"     观点：\"{content}{'...' if len(anno['content']) > 150 else ''}\"")
                
                if meta_count > 0:
                    lines.append(f"     💬 有{meta_count}条元批注（后续反思）")
                if edit_count > 0:
                    lines.append(f"     ✏️ 已修改{edit_count}次")
                
                lines.append("")
        
        lines.append("━" * 60)
        
        if len(timeline) >= 2:
            lines.append("\n💡 思想演化分析：\n")
            
            periods = sorted(timeline.keys())
            first_period = periods[0]
            last_period = periods[-1]
            
            first_moods = [a["mood"] for a in timeline[first_period]]
            last_moods = [a["mood"] for a in timeline[last_period]]
            
            first_dominant = max(set(first_moods), key=first_moods.count)
            last_dominant = max(set(last_moods), key=last_moods.count)
            
            lines.append(f"初期（{first_period}）：主要是 {first_dominant}")
            lines.append(f"近期（{last_period}）：主要是 {last_dominant}")
            
            if first_dominant != last_dominant:
                lines.append(f"\n演化路径：{first_dominant} → {last_dominant}")
                lines.append("说明你对这个概念的理解发生了质的变化。")
            else:
                lines.append(f"\n观点稳定：一直保持 {first_dominant} 的态度。")
            
            total_meta = sum(len(a.get("meta_annotations", [])) for a in annotations)
            if total_meta > 0:
                lines.append(f"\n🔄 元认知活动：共{total_meta}次反思")
                lines.append(f"说明你在不断回顾和反思对这个概念的理解。")
        
        message = "\n".join(lines)
        
        return {
            "status": "success",
            "concept": concept,
            "timeline": dict(timeline),
            "total_annotations": len(annotations),
            "time_span": len(timeline),
            "message": message
        }
        
    except Exception as e:
        import traceback
        return {
            "status": "error",
            "message": f"❌ 查询失败：{str(e)}\n{traceback.format_exc()}"
        }

