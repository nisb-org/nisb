#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
NISB Corpus Query Tool
Phase 3.8优化：添加下一步操作建议
"""

import os
import json
from glob import glob


def nisb_corpus_query(args: dict) -> dict:
    """
    Corpus模板查询（Phase 3.8优化版）
    
    Phase 3.8优化：
    - ✅ 添加下一步操作建议
    - ✅ 优化message格式
    - ✅ 显示示例模板
    
    Args:
        brain_id: 大脑ID（必填）
        pattern_type: 模式类型（可选）
          - opening_hooks: 开场钩子
          - transition_phrases: 转折短语
          - rhetorical_devices: 修辞手法
          - explanation_patterns: 解释模式
          - all: 所有类型（默认）
        concept: 相关概念（可选）
        min_score: 最低效果评分（可选，默认0.7）
        limit: 返回数量限制（可选，默认20）
    
    Returns:
        {status, brain_id, episode_count, patterns, message}
    """
    from core.storage import get_corpus_base_path, get_corpus_meta
    
    # ========== 1. 参数解析 ==========
    brain_id = args.get("brain_id")
    pattern_type = args.get("pattern_type", "all")
    concept = args.get("concept")
    min_score = args.get("min_score", 0.7)
    limit = args.get("limit", 20)
    
    if not brain_id:
        return {
            "status": "error",
            "message": "❌ brain_id不能为空"
        }
    
    # ========== 2. 验证brain存在 ==========
    try:
        meta = get_corpus_meta(brain_id)
        base_path = get_corpus_base_path(brain_id)
    except FileNotFoundError:
        return {
            "status": "error",
            "message": f"❌ 大脑不存在：{brain_id}"
        }
    
    # ========== 3. 读取所有pattern文件 ==========
    patterns_dir = f"{base_path}/storage/entities/patterns/by_id"
    
    if not os.path.exists(patterns_dir):
        return {
            "status": "success",
            "brain_id": brain_id,
            "episode_count": 0,
            "patterns": {},
            "message": f"✅ {meta['display_name']}：暂无数据\n💡 使用nisb_corpus_ingest()导入字幕"
        }
    
    pattern_files = sorted(glob(f"{patterns_dir}/pattern_ep*.json"))
    
    if not pattern_files:
        return {
            "status": "success",
            "brain_id": brain_id,
            "episode_count": 0,
            "patterns": {},
            "message": f"✅ {meta['display_name']}：暂无数据\n💡 使用nisb_corpus_ingest()导入字幕"
        }
    
    # ========== 4. 提取所有模板 ==========
    all_patterns = {
        "opening_hooks": [],
        "transition_phrases": [],
        "rhetorical_devices": [],
        "explanation_patterns": []
    }
    
    for pattern_file in pattern_files:
        with open(pattern_file, 'r', encoding='utf-8') as f:
            pattern_data = json.load(f)
        
        episode_num = pattern_data.get("episode_number", 0)
        
        # 提取opening_hooks
        for hook in pattern_data.get("opening_hooks", []):
            score = hook.get("effectiveness_score", 0)
            if score >= min_score:
                all_patterns["opening_hooks"].append({
                    "episode": episode_num,
                    "text": hook.get("text", ""),
                    "timestamp": hook.get("timestamp", ""),
                    "effectiveness_score": score,
                    "context": hook.get("context", ""),
                    "semantic_tags": hook.get("semantic_tags", {})
                })
        
        # 提取transition_phrases
        for phrase in pattern_data.get("transition_phrases", []):
            score = phrase.get("effectiveness_score", 0)
            if score >= min_score:
                all_patterns["transition_phrases"].append({
                    "episode": episode_num,
                    "text": phrase.get("text", ""),
                    "timestamp": phrase.get("timestamp", ""),
                    "effectiveness_score": score,
                    "context": phrase.get("context", ""),
                    "semantic_tags": phrase.get("semantic_tags", {})
                })
        
        # 提取rhetorical_devices
        for device in pattern_data.get("rhetorical_devices", []):
            score = device.get("effectiveness_score", 0)
            if score >= min_score:
                all_patterns["rhetorical_devices"].append({
                    "episode": episode_num,
                    "type": device.get("type", ""),
                    "example": device.get("example", ""),
                    "timestamp": device.get("timestamp", ""),
                    "effectiveness_score": score,
                    "context": device.get("context", ""),
                    "semantic_tags": device.get("semantic_tags", {})
                })
        
        # 提取explanation_patterns
        for pattern in pattern_data.get("explanation_patterns", []):
            all_patterns["explanation_patterns"].append({
                "episode": episode_num,
                "concept": pattern.get("concept", ""),
                "simple_explanation": pattern.get("simple_explanation", ""),
                "timestamp": pattern.get("timestamp", ""),
                "semantic_tags": pattern.get("semantic_tags", {})
            })
    
    # ========== 5. 按pattern_type过滤 ==========
    if pattern_type != "all" and pattern_type in all_patterns:
        all_patterns = {pattern_type: all_patterns[pattern_type]}
    
    # ========== 6. 按effectiveness_score排序并限制数量 ==========
    for key in all_patterns:
        if key != "explanation_patterns":
            all_patterns[key] = sorted(
                all_patterns[key],
                key=lambda x: x.get("effectiveness_score", 0),
                reverse=True
            )[:limit]
        else:
            all_patterns[key] = all_patterns[key][:limit]
    
    # ========== 7. 统计 ==========
    total_patterns = sum(len(v) for v in all_patterns.values())
    
    # ========== 8. 构建返回消息（优化版）==========
    message_lines = [f"✅ 查询成功：{meta['display_name']}"]
    message_lines.append(f"   📁 Episodes：{len(pattern_files)}个")
    message_lines.append(f"   📊 模板总数：{total_patterns}个")
    
    if pattern_type != "all":
        message_lines.append(f"   🔍 筛选类型：{pattern_type}")
    
    if min_score > 0:
        message_lines.append(f"   ⭐ 最低评分：{min_score}")
    
    message_lines.append("")
    
    # 按类型展示数量和示例
    for ptype, items in all_patterns.items():
        if items:
            message_lines.append(f"【{ptype}】{len(items)}个")
            
            # 展示第1个高分示例
            top_item = items[0]
            if ptype == "opening_hooks":
                preview = top_item.get("text", "")[:60]
                message_lines.append(f"  ⭐ 高分示例: {preview}...")
                message_lines.append(f"     评分: {top_item.get('effectiveness_score', 0):.2f} | Episode {top_item['episode']}")
            
            elif ptype == "rhetorical_devices":
                preview = top_item.get("example", "")[:60]
                device_type = top_item.get("type", "")
                message_lines.append(f"  ⭐ 高分示例: [{device_type}] {preview}...")
                message_lines.append(f"     评分: {top_item.get('effectiveness_score', 0):.2f} | Episode {top_item['episode']}")
            
            message_lines.append("")
    
    # ⭐⭐⭐ 核心优化：添加下一步操作建议 ⭐⭐⭐
    message_lines.append("💡 下一步操作：")
    message_lines.append("  1. 语义搜索：nisb_corpus_semantic_search(query='如何吸引注意力')")
    message_lines.append("  2. 查看统计：nisb_corpus_stats()")
    message_lines.append("  3. 生成图表：nisb_execute_code(code='...')  # 可视化模式分布")
    message_lines.append("  4. 健康检查：nisb_corpus_doctor()  # 检测数据质量")
    
    # ========== 9. 返回结果 ==========
    return {
        "status": "success",
        "brain_id": brain_id,
        "display_name": meta["display_name"],
        "episode_count": len(pattern_files),
        "patterns": all_patterns,
        "total_patterns": total_patterns,
        "message": "\n".join(message_lines)
    }


# 导出函数
__all__ = ['nisb_corpus_query']

