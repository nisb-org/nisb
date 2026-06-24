#!/usr/bin/env python3
"""
批注统计功能（基于索引，高性能）
Phase 2.9.7 多用户版本
Phase 6.0 修复：多用户隔离完善
"""

import os
import json
import sys
from core.user_context import auto_user_context, get_user_ctx
sys.path.insert(0, '/srv')

@auto_user_context
def nisb_annotation_stats(args: dict) -> dict:
    """查看批注统计（基于索引，O(1)查询）"""
    
    # ✅ Phase 6.0修复：从context获取user数据
    user_ctx = get_user_ctx()
    base_path = user_ctx.base
    
    try:
        from .index import load_index
        from collections import Counter
        
        by_target = load_index(base_path, "by_target")
        by_mood = load_index(base_path, "by_mood")
        by_tag = load_index(base_path, "by_tag")
        by_concept = load_index(base_path, "by_concept")
        
        total_annotations = sum(len(ids) for ids in by_target.values())
        
        if total_annotations == 0:
            return {
                "status": "success",
                "message": "📊 暂无批注记录"
            }
        
        annotations_by_type = {"bookmark": 0, "case": 0, "note": 0}
        for target_id in by_target.keys():
            if target_id.startswith("bookmark_"):
                annotations_by_type["bookmark"] += len(by_target[target_id])
            elif target_id.startswith("case_"):
                annotations_by_type["case"] += len(by_target[target_id])
            elif target_id.startswith("note_"):
                annotations_by_type["note"] += len(by_target[target_id])
        
        total_meta_annotations = 0
        total_edits = 0
        
        anno_dir = f"{base_path}/storage/annotations/by_date"
        if os.path.exists(anno_dir):
            for year_month in os.listdir(anno_dir):
                anno_file = f"{anno_dir}/{year_month}/annotations.jsonl"
                if os.path.exists(anno_file):
                    with open(anno_file, 'r', encoding='utf-8') as f:
                        for line in f:
                            if line.strip():
                                anno = json.loads(line)
                                if anno.get("deleted", False):
                                    continue
                                total_meta_annotations += len(anno.get("meta_annotations", []))
                                total_edits += len(anno.get("edit_history", []))
        
        targets_with_multiple = []
        for target_id, anno_ids in by_target.items():
            if len(anno_ids) >= 3:
                from .get_annotations import get_target_annotations
                annotations = get_target_annotations(base_path, target_id)
                
                if annotations:
                    moods = [a["mood"] for a in annotations]
                    
                    from datetime import datetime as dt
                    first_time = dt.fromisoformat(annotations[0]["timestamp"])
                    last_time = dt.fromisoformat(annotations[-1]["timestamp"])
                    days = (last_time - first_time).days
                    
                    targets_with_multiple.append({
                        "target_id": target_id,
                        "count": len(anno_ids),
                        "moods": moods,
                        "time_span_days": days
                    })
        
        targets_with_multiple.sort(key=lambda x: x["count"], reverse=True)
        
        lines = ["📊 批注统计\n"]
        lines.append(f"总批注数：{total_annotations}条")
        
        lines.append(f"\n按类型分布：")
        type_names = {"bookmark": "书签", "case": "案例", "note": "笔记"}
        for type_key, count in annotations_by_type.items():
            if count > 0:
                percentage = count / total_annotations * 100
                lines.append(f"  {type_names[type_key]}：{count}条（{percentage:.0f}%）")
        
        lines.append(f"\n按情绪分布：")
        mood_icons = {
            "顿悟": "💡", "质疑": "🤔", "担忧": "😟",
            "兴奋": "😊", "困惑": "😕", "中性": "📝",
            "新洞察": "⭐", "验证": "✅", "预测": "🔮", "自我反思": "🔄"
        }
        mood_counts = [(mood, len(ids)) for mood, ids in by_mood.items()]
        mood_counts.sort(key=lambda x: x[1], reverse=True)
        
        for mood, count in mood_counts[:8]:
            percentage = count / total_annotations * 100
            icon = mood_icons.get(mood, "📝")
            lines.append(f"  {icon} {mood}：{count}条（{percentage:.0f}%）")
        
        lines.append(f"\n按概念分布（TOP 10）：")
        concept_counts = [(concept, len(ids)) for concept, ids in by_concept.items()]
        concept_counts.sort(key=lambda x: x[1], reverse=True)
        
        for concept, count in concept_counts[:10]:
            percentage = count / total_annotations * 100
            lines.append(f"  {concept}：{count}条（{percentage:.0f}%）")
        
        if total_meta_annotations > 0 or total_edits > 0:
            lines.append(f"\n活动统计：")
            if total_meta_annotations > 0:
                lines.append(f"  💬 元批注（反思）：{total_meta_annotations}条")
            if total_edits > 0:
                lines.append(f"  ✏️  批注修改：{total_edits}次")
        
        if targets_with_multiple:
            lines.append(f"\n思想演化最明显的TOP 3：")
            for i, item in enumerate(targets_with_multiple[:3], 1):
                target_id = item["target_id"]
                count = item["count"]
                moods = item["moods"]
                days = item["time_span_days"]
                
                if days < 30:
                    span = f"{days}天"
                elif days < 365:
                    span = f"{days // 30}个月"
                else:
                    span = f"{days // 365}年{(days % 365) // 30}个月"
                
                lines.append(f"\n{i}. {target_id}")
                lines.append(f"   批注数：{count}条")
                lines.append(f"   演化：{' → '.join(moods)}")
                lines.append(f"   时间跨度：{span}")
        
        message = "\n".join(lines)
        
        return {
            "status": "success",
            "stats": {
                "total": total_annotations,
                "by_type": annotations_by_type,
                "by_mood": dict(by_mood),
                "by_tag": dict(by_tag),
                "by_concept": dict(by_concept),
                "meta_annotations": total_meta_annotations,
                "edits": total_edits,
                "evolution_tracks": targets_with_multiple
            },
            "message": message
        }
        
    except Exception as e:
        import traceback
        return {
            "status": "error",
            "message": f"❌ 统计失败：{str(e)}\n{traceback.format_exc()}"
        }

