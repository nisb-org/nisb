#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Corpus导出工具
导出模板库为Markdown/JSON/CSV格式
"""

import os
import json
import csv
from io import StringIO
from glob import glob
from core.storage import get_corpus_base_path, get_corpus_meta


def nisb_corpus_export(args: dict) -> dict:
    """
    导出模板库
    
    Args:
        brain_id: 大脑ID（必填）
        format: 导出格式（可选，默认"markdown"）
          - markdown: Markdown文档
          - json: JSON格式
          - csv: CSV表格
        pattern_type: 模板类型（可选，默认"all"）
        min_score: 最低效果评分（可选，默认0）
    
    Returns:
        {
          "status": "success",
          "format": "markdown",
          "content": "...",  # 导出的文本内容
          "message": "..."
        }
    """
    brain_id = args.get("brain_id")
    export_format = args.get("format", "markdown")
    pattern_type = args.get("pattern_type", "all")
    min_score = args.get("min_score", 0)
    
    if not brain_id:
        return {"status": "error", "message": "❌ brain_id不能为空"}
    
    if export_format not in ["markdown", "json", "csv"]:
        return {"status": "error", "message": "❌ format必须是markdown/json/csv"}
    
    # ========== 获取meta和数据 ==========
    try:
        meta = get_corpus_meta(brain_id)
        base_path = get_corpus_base_path(brain_id)
    except FileNotFoundError:
        return {"status": "error", "message": f"❌ 大脑不存在：{brain_id}"}
    
    patterns_dir = f"{base_path}/storage/entities/patterns/by_id"
    pattern_files = sorted(glob(f"{patterns_dir}/pattern_ep*.json"))
    
    # ========== 收集所有模板 ==========
    all_patterns = []
    
    for pattern_file in pattern_files:
        with open(pattern_file, 'r', encoding='utf-8') as f:
            pattern_data = json.load(f)
        
        episode_num = pattern_data.get("episode_number", 0)
        
        # 提取各类型模板
        for hook in pattern_data.get("opening_hooks", []):
            if hook.get("effectiveness_score", 0) >= min_score:
                all_patterns.append({
                    "type": "opening_hooks",
                    "episode": episode_num,
                    "text": hook.get("text", ""),
                    "score": hook.get("effectiveness_score", 0),
                    "timestamp": hook.get("timestamp", "")
                })
        
        for phrase in pattern_data.get("transition_phrases", []):
            if phrase.get("effectiveness_score", 0) >= min_score:
                all_patterns.append({
                    "type": "transition_phrases",
                    "episode": episode_num,
                    "text": phrase.get("text", ""),
                    "score": phrase.get("effectiveness_score", 0),
                    "timestamp": phrase.get("timestamp", "")
                })
        
        for device in pattern_data.get("rhetorical_devices", []):
            if device.get("effectiveness_score", 0) >= min_score:
                all_patterns.append({
                    "type": "rhetorical_devices",
                    "episode": episode_num,
                    "text": device.get("example", ""),
                    "score": device.get("effectiveness_score", 0),
                    "timestamp": device.get("timestamp", ""),
                    "device_type": device.get("type", "")
                })
    
    # ========== 按类型过滤 ==========
    if pattern_type != "all":
        all_patterns = [p for p in all_patterns if p["type"] == pattern_type]
    
    # ========== 根据format生成内容 ==========
    if export_format == "markdown":
        content = _export_markdown(meta, all_patterns)
    elif export_format == "json":
        content = json.dumps({
            "brain_id": brain_id,
            "display_name": meta["display_name"],
            "total_patterns": len(all_patterns),
            "patterns": all_patterns
        }, ensure_ascii=False, indent=2)
    elif export_format == "csv":
        content = _export_csv(all_patterns)
    
    return {
        "status": "success",
        "brain_id": brain_id,
        "format": export_format,
        "total_patterns": len(all_patterns),
        "content": content,
        "message": f"✅ 已导出{len(all_patterns)}个模板（{export_format}格式）"
    }


def _export_markdown(meta: dict, patterns: list) -> str:
    """生成Markdown格式"""
    lines = [
        f"# {meta['display_name']} 模板库",
        "",
        f"**总模板数**：{len(patterns)}个",
        "",
        "---",
        ""
    ]
    
    # 按类型分组
    by_type = {}
    for p in patterns:
        ptype = p["type"]
        if ptype not in by_type:
            by_type[ptype] = []
        by_type[ptype].append(p)
    
    type_names = {
        "opening_hooks": "开场钩子",
        "transition_phrases": "转折短语",
        "rhetorical_devices": "修辞手法"
    }
    
    for ptype, items in by_type.items():
        lines.append(f"## {type_names.get(ptype, ptype)} ({len(items)}个)")
        lines.append("")
        
        for i, item in enumerate(sorted(items, key=lambda x: x.get("score", 0), reverse=True), 1):
            lines.append(f"### {i}. Episode {item['episode']} [{item.get('timestamp', 'N/A')}]")
            lines.append(f"**评分**：{item.get('score', 0):.2f}")
            lines.append("")
            lines.append(f"{item['text']}")
            lines.append("")
            lines.append("---")
            lines.append("")
    
    return "\n".join(lines)


def _export_csv(patterns: list) -> str:
    """生成CSV格式"""
    output = StringIO()
    writer = csv.DictWriter(output, fieldnames=["type", "episode", "score", "timestamp", "text"])
    writer.writeheader()
    
    for p in patterns:
        writer.writerow({
            "type": p["type"],
            "episode": p["episode"],
            "score": p.get("score", 0),
            "timestamp": p.get("timestamp", ""),
            "text": p["text"][:200]  # 限制长度
        })
    
    return output.getvalue()


__all__ = ['nisb_corpus_export']

