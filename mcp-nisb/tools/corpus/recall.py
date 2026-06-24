#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Corpus快速回溯工具
类似nisb_kb_recall，快速查看特定episode的完整模板
⭐ Phase 3.0增强：支持L3_cases显示
"""

import os
import json
from core.storage import get_corpus_base_path, get_corpus_meta


def nisb_corpus_recall(args: dict) -> dict:
    """
    通过episode编号快速回溯完整模板（三层完整）
    
    Args:
        brain_id: 大脑ID（必填）
        episode_number: episode编号（必填）
        include_segments: bool - 是否包含L1字幕（默认False）
    
    Returns:
        {
          "status": "success",
          "brain_id": "brain_utopia",
          "episode": 304,
          "patterns": {...},
          "cases": [...],  # ⭐ 新增L3_cases
          "segments": [...],
          "message": "完整格式化的模板内容"
        }
    """
    brain_id = args.get("brain_id")
    episode_number = args.get("episode_number")
    include_segments = args.get("include_segments", False)
    
    if not brain_id or not episode_number:
        return {"status": "error", "message": "❌ brain_id和episode_number不能为空"}
    
    # ========== 获取meta信息 ==========
    try:
        meta = get_corpus_meta(brain_id)
        base_path = get_corpus_base_path(brain_id)
    except FileNotFoundError:
        return {"status": "error", "message": f"❌ 大脑不存在：{brain_id}"}
    
    # ========== 读取pattern文件 ==========
    pattern_file = f"{base_path}/storage/entities/patterns/by_id/pattern_ep{episode_number}.json"
    
    if not os.path.exists(pattern_file):
        # 尝试带前导零的格式
        pattern_file_alt = f"{base_path}/storage/entities/patterns/by_id/pattern_ep{episode_number:03d}.json"
        if os.path.exists(pattern_file_alt):
            pattern_file = pattern_file_alt
        else:
            return {
                "status": "error",
                "message": f"❌ Episode {episode_number} 不存在"
            }
    
    with open(pattern_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    patterns = data.get("L2_pattern", data)  # 兼容旧格式
    cases = data.get("L3_cases", [])  # ⭐ 提取L3_cases
    
    # ========== 读取L1字幕（如果需要） ==========
    segments = []
    if include_segments:
        segments_file = f"{base_path}/storage/raw/episodes/ep{episode_number}.jsonl"
        if not os.path.exists(segments_file):
            segments_file = f"{base_path}/storage/raw/episodes/ep{episode_number:03d}.jsonl"
        
        if os.path.exists(segments_file):
            with open(segments_file, 'r', encoding='utf-8') as f:
                segments = [json.loads(line) for line in f if line.strip()]
    
    # ========== 格式化输出消息 ==========
    message_lines = [
        f"📺 {meta['display_name']} - Episode {episode_number}",
        ""
    ]
    
    # Opening Hooks
    hooks = patterns.get("opening_hooks", [])
    if hooks:
        message_lines.append(f"🎣 开场钩子（{len(hooks)}个）：")
        message_lines.append("")
        for i, hook in enumerate(hooks, 1):
            message_lines.append(f"{i}. [{hook.get('timestamp', 'N/A')}] 评分：{hook.get('effectiveness_score', 0):.2f}")
            message_lines.append(f"   {hook.get('text', '')[:120]}...")
            message_lines.append("")
    
    # Transition Phrases
    phrases = patterns.get("transition_phrases", [])
    if phrases:
        message_lines.append(f"🔄 转折短语（{len(phrases)}个）：")
        message_lines.append("")
        for i, phrase in enumerate(phrases, 1):
            message_lines.append(f"{i}. [{phrase.get('timestamp', 'N/A')}] 评分：{phrase.get('effectiveness_score', 0):.2f}")
            message_lines.append(f"   {phrase.get('text', '')}")
            message_lines.append("")
    
    # Rhetorical Devices
    devices = patterns.get("rhetorical_devices", [])
    if devices:
        message_lines.append(f"🎭 修辞手法（{len(devices)}个）：")
        message_lines.append("")
        for i, device in enumerate(devices, 1):
            message_lines.append(f"{i}. {device.get('type', '未知')} [{device.get('timestamp', 'N/A')}] 评分：{device.get('effectiveness_score', 0):.2f}")
            message_lines.append(f"   {device.get('example', '')[:100]}...")
            message_lines.append("")
    
    # Explanation Patterns
    explanations = patterns.get("explanation_patterns", [])
    if explanations:
        message_lines.append(f"📖 解释模式（{len(explanations)}个）：")
        message_lines.append("")
        for i, exp in enumerate(explanations, 1):
            message_lines.append(f"{i}. {exp.get('concept', '')}：")
            message_lines.append(f"   {exp.get('simple_explanation', '')}")
            message_lines.append("")
    
    # ⭐⭐⭐ L3 Cases（新增）
    if cases:
        message_lines.append(f"📚 案例库（{len(cases)}个）：")
        message_lines.append("")
        for i, case in enumerate(cases, 1):
            message_lines.append(f"{i}. {case.get('title', '未命名案例')}")
            message_lines.append(f"   {case.get('summary', '')}")
            message_lines.append(f"   时间点：{case.get('timestamp', 'N/A')} | 类型：{case.get('type', '未分类')}")
            message_lines.append("")
    
    # L1字幕（如果包含）
    if include_segments and segments:
        message_lines.append(f"📝 字幕片段（前5条）：")
        message_lines.append("")
        for seg in segments[:5]:
            message_lines.append(f"[{seg.get('timestamp', 'N/A')}] {seg.get('text', '')[:80]}...")
    
    return {
        "status": "success",
        "brain_id": brain_id,
        "display_name": meta["display_name"],
        "episode": episode_number,
        "patterns": patterns,
        "cases": cases,  # ⭐ 返回L3_cases
        "segments": segments if include_segments else [],
        "message": "\n".join(message_lines)
    }


__all__ = ['nisb_corpus_recall']
