#!/usr/bin/env python3
"""
批注获取和格式化显示
Phase 6.0 修复：多用户隔离完善
"""

import os
import json
import sys
sys.path.insert(0, '/srv')


def get_target_annotations(base_path: str, target_id: str) -> list:
    """
    获取某个目标的所有批注
    
    参数：
        base_path: 数据目录（用户隔离路径）
        target_id: 目标ID
    
    返回：
        批注列表（按时间排序，不包含已删除）
    """
    from .index import load_index
    
    try:
        # 从索引获取批注ID列表
        by_target = load_index(base_path, "by_target")
        annotation_ids = by_target.get(target_id, [])
        
        if not annotation_ids:
            return []
        
        # 从annotations文件读取完整批注
        annotations = []
        anno_dir = f"{base_path}/storage/annotations/by_date"
        
        if not os.path.exists(anno_dir):
            return []
        
        for year_month in os.listdir(anno_dir):
            anno_file = f"{anno_dir}/{year_month}/annotations.jsonl"
            if os.path.exists(anno_file):
                with open(anno_file, 'r', encoding='utf-8') as f:
                    for line in f:
                        if line.strip():
                            anno = json.loads(line)
                            # 跳过已删除的批注
                            if anno.get("deleted", False):
                                continue
                            if anno["annotation_id"] in annotation_ids:
                                annotations.append(anno)
        
        # 按时间排序
        annotations.sort(key=lambda x: x["timestamp"])
        
        return annotations
        
    except Exception as e:
        print(f"[ERROR] 获取批注失败: {e}", file=sys.stderr)
        return []


def format_annotations(annotations: list) -> str:
    """格式化批注为可读文本（完整版，包含元批注和修改历史）"""
    if not annotations:
        return ""
    
    lines = [f"\n\n💭 你的批注（{len(annotations)}条，按时间排序）："]
    lines.append("━" * 60)
    
    mood_icons = {
        "担忧": "😟", "质疑": "🤔", "顿悟": "💡", "困惑": "😕",
        "兴奋": "😊", "中性": "📝", "新洞察": "⭐", "验证": "✅", 
        "预测": "🔮", "自我反思": "🔄"
    }
    
    for i, anno in enumerate(annotations, 1):
        timestamp = anno.get("timestamp", "")[:16]
        content = anno.get("content", "")
        mood = anno.get("mood", "中性")
        mood_icon = mood_icons.get(mood, "📝")
        tags = anno.get("tags", [])
        context = anno.get("context", "")
        concepts = anno.get("concepts", [])
        meta_annotations = anno.get("meta_annotations", [])
        edit_history = anno.get("edit_history", [])
        
        # 计算时间间隔
        time_gap = ""
        if i > 1:
            from datetime import datetime as dt
            prev_time = dt.fromisoformat(annotations[i-2].get("timestamp", ""))
            curr_time = dt.fromisoformat(anno.get("timestamp", ""))
            days = (curr_time - prev_time).days
            if days > 0:
                if days < 30:
                    time_gap = f"（{days}天后）"
                elif days < 365:
                    months = days // 30
                    time_gap = f"（{months}个月后）"
                else:
                    years = days // 365
                    time_gap = f"（{years}年后）"
        
        # 特殊标记
        special_mark = ""
        if mood in ["新洞察", "顿悟"]:
            special_mark = " ⭐"
        elif mood == "验证":
            special_mark = " ✅"
        
        # 修改标记
        if edit_history:
            special_mark += f" ✏️已修改{len(edit_history)}次"
        
        lines.append(f"\n📌 批注{i}（{timestamp}{time_gap}）{special_mark}")
        if context:
            lines.append(f"场景：{context}")
        lines.append(f"\"{content}\"")
        lines.append(f"情绪：{mood_icon} {mood}")
        
        # 显示关联概念
        if concepts:
            lines.append(f"关联概念：{', '.join(concepts)}")
        
        if tags:
            lines.append(f"标签：{' '.join([f'#{t}' for t in tags])}")
        
        # ⭐ 显示修改历史
        if edit_history:
            lines.append(f"\n  📝 修改历史（{len(edit_history)}次）：")
            for j, edit in enumerate(edit_history, 1):
                edit_time = edit.get("edit_timestamp", "")[:16]
                old_content = edit.get("old_content", "")[:50]
                lines.append(f"     {j}. [{edit_time}] 原内容：\"{old_content}...\"")
        
        # ⭐ 显示元批注
        if meta_annotations:
            lines.append(f"\n  💬 元批注（{len(meta_annotations)}条后续反思）：")
            for j, meta in enumerate(meta_annotations, 1):
                meta_time = meta.get("timestamp", "")[:16]
                meta_content = meta.get("content", "")
                meta_mood = meta.get("mood", "")
                meta_mood_icon = mood_icons.get(meta_mood, "🔄")
                
                # 计算元批注距离原批注的时间
                from datetime import datetime as dt
                orig_time = dt.fromisoformat(anno["timestamp"])
                meta_dt = dt.fromisoformat(meta["timestamp"])
                days_diff = (meta_dt - orig_time).days
                
                if days_diff < 30:
                    time_since = f"{days_diff}天后"
                elif days_diff < 365:
                    time_since = f"{days_diff // 30}个月后"
                else:
                    time_since = f"{days_diff // 365}年后"
                
                lines.append(f"     {j}. [{meta_time}] {meta_mood_icon} {time_since}")
                lines.append(f"        \"{meta_content}\"")
    
    lines.append("\n" + "━" * 60)
    
    # 思想演化轨迹
    if len(annotations) >= 3:
        moods = [anno.get("mood", "中性") for anno in annotations]
        lines.append(f"\n💡 思想演化轨迹：")
        lines.append(" → ".join(moods))
        
        # 计算时间跨度
        from datetime import datetime as dt
        first_time = dt.fromisoformat(annotations[0]["timestamp"])
        last_time = dt.fromisoformat(annotations[-1]["timestamp"])
        days = (last_time - first_time).days
        if days < 30:
            span = f"{days}天"
        elif days < 365:
            span = f"{days // 30}个月"
        else:
            span = f"{days // 365}年{(days % 365) // 30}个月"
        
        lines.append(f"时间跨度：{span}")
        
        # 关键转折点
        turning_points = []
        for i in range(1, len(annotations)):
            if annotations[i]["mood"] != annotations[i-1]["mood"]:
                date = annotations[i]["timestamp"][:10]
                from_mood = annotations[i-1]["mood"]
                to_mood = annotations[i]["mood"]
                turning_points.append(f"{date}：从{from_mood}到{to_mood}")
        
        if turning_points:
            lines.append(f"\n🎯 关键转折点：")
            for tp in turning_points:
                lines.append(f"  {tp}")
        
        # 元认知统计
        total_meta = sum(len(a.get("meta_annotations", [])) for a in annotations)
        if total_meta > 0:
            lines.append(f"\n🔄 元认知活动：共{total_meta}次反思")
        
        # 修改统计
        total_edits = sum(len(a.get("edit_history", [])) for a in annotations)
        if total_edits > 0:
            lines.append(f"✏️  修改活动：共{total_edits}次修改")
    
    return "\n".join(lines)

