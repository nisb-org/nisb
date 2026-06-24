#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Corpus统计工具
Phase 3.8优化：新增nisb_corpus_doctor健康检查
"""

import os
import json
from glob import glob
from core.storage import get_corpus_base_path, get_corpus_meta, load_corpus_embeddings


def nisb_corpus_stats(args: dict) -> dict:
    """
    查看corpus统计信息（原功能保持不变）
    
    Args:
        brain_id: 大脑ID（必填）
    
    Returns:
        {status, brain_id, display_name, episodes_count, patterns_count, ...}
    """
    brain_id = args.get("brain_id")
    
    if not brain_id:
        return {"status": "error", "message": "❌ brain_id不能为空"}
    
    # ========== 获取meta信息 ==========
    try:
        meta = get_corpus_meta(brain_id)
        base_path = get_corpus_base_path(brain_id)
    except FileNotFoundError:
        return {"status": "error", "message": f"❌ 大脑不存在：{brain_id}"}
    
    # ========== 读取所有pattern文件 ==========
    patterns_dir = f"{base_path}/storage/entities/patterns/by_id"
    
    if not os.path.exists(patterns_dir):
        return {
            "status": "success",
            "brain_id": brain_id,
            "display_name": meta["display_name"],
            "episodes_count": 0,
            "message": f"✅ {meta['display_name']}：暂无数据"
        }
    
    pattern_files = sorted(glob(f"{patterns_dir}/pattern_ep*.json"))
    
    # ========== 统计各类型模板数量 ==========
    patterns_count = {
        "opening_hooks": 0,
        "transition_phrases": 0,
        "rhetorical_devices": 0,
        "explanation_patterns": 0
    }
    
    all_scores = []
    all_semantic_tags = {}
    
    for pattern_file in pattern_files:
        with open(pattern_file, 'r', encoding='utf-8') as f:
            pattern_data = json.load(f)
        
        # 统计opening_hooks
        hooks = pattern_data.get("opening_hooks", [])
        patterns_count["opening_hooks"] += len(hooks)
        for hook in hooks:
            if "effectiveness_score" in hook:
                all_scores.append(hook["effectiveness_score"])
            tags = hook.get("semantic_tags", {})
            for key, values in tags.items():
                if key not in all_semantic_tags:
                    all_semantic_tags[key] = {}
                if isinstance(values, list):
                    for v in values:
                        all_semantic_tags[key][v] = all_semantic_tags[key].get(v, 0) + 1
        
        # 统计其他类型（代码同原版）
        phrases = pattern_data.get("transition_phrases", [])
        patterns_count["transition_phrases"] += len(phrases)
        for phrase in phrases:
            if "effectiveness_score" in phrase:
                all_scores.append(phrase["effectiveness_score"])
        
        devices = pattern_data.get("rhetorical_devices", [])
        patterns_count["rhetorical_devices"] += len(devices)
        for device in devices:
            if "effectiveness_score" in device:
                all_scores.append(device["effectiveness_score"])
        
        explanations = pattern_data.get("explanation_patterns", [])
        patterns_count["explanation_patterns"] += len(explanations)
    
    patterns_count["total"] = sum(patterns_count.values())
    
    # ========== 检查embeddings状态 ==========
    embeddings, _ = load_corpus_embeddings(brain_id)
    embeddings_status = "已生成" if embeddings is not None else "未生成"
    
    # ========== 平均效果评分 ==========
    avg_score = sum(all_scores) / len(all_scores) if all_scores else 0
    
    # ========== TOP语义标签 ==========
    top_tags = {}
    for tag_type, tag_values in all_semantic_tags.items():
        sorted_tags = sorted(tag_values.items(), key=lambda x: x[1], reverse=True)[:3]
        top_tags[tag_type] = [{"tag": k, "count": v} for k, v in sorted_tags]
    
    # ========== 构建返回消息 ==========
    message = f"""📊 {meta['display_name']} 统计信息

Episodes：{len(pattern_files)}个
模板总数：{patterns_count['total']}个
  - 开场钩子：{patterns_count['opening_hooks']}个
  - 转折短语：{patterns_count['transition_phrases']}个
  - 修辞手法：{patterns_count['rhetorical_devices']}个
  - 解释模式：{patterns_count['explanation_patterns']}个

平均效果评分：{avg_score:.2f}
Embeddings状态：{embeddings_status}

TOP语义标签：
"""
    
    for tag_type, tags in list(top_tags.items())[:3]:
        message += f"  {tag_type}：{', '.join([t['tag'] for t in tags])}\n"
    
    return {
        "status": "success",
        "brain_id": brain_id,
        "display_name": meta["display_name"],
        "episodes_count": len(pattern_files),
        "patterns_count": patterns_count,
        "embeddings_status": embeddings_status,
        "avg_effectiveness_score": round(avg_score, 2),
        "top_semantic_tags": top_tags,
        "message": message.strip()
    }


def nisb_corpus_doctor(args: dict) -> dict:
    """
    ⭐⭐⭐ Phase 3.8新增：Corpus健康检查
    
    检查内容：
    1. effectiveness_score分布（是否虚高/过于集中）
    2. semantic_tags完整性（是否缺失维度）
    3. Embeddings生成状态
    4. 数据格式规范性
    5. 字段缺失问题
    
    Args:
        brain_id: 大脑ID（必填）
    
    Returns:
        {
          "status": "success" or "warning",
          "issues": [...],
          "suggestions": [...],
          "message": "诊断报告"
        }
    """
    brain_id = args.get("brain_id")
    
    if not brain_id:
        return {"status": "error", "message": "❌ brain_id不能为空"}
    
    # 复用stats的逻辑获取基础信息
    stats_result = nisb_corpus_stats({"brain_id": brain_id})
    if stats_result["status"] != "success":
        return stats_result
    
    # 开始健康检查
    issues = []
    suggestions = []
    
    base_path = get_corpus_base_path(brain_id)
    patterns_dir = f"{base_path}/storage/entities/patterns/by_id"
    
    if not os.path.exists(patterns_dir):
        return {
            "status": "error",
            "message": "❌ patterns目录不存在，无数据可检查"
        }
    
    pattern_files = sorted(glob(f"{patterns_dir}/pattern_ep*.json"))
    
    # ========== 检查1：effectiveness_score分布 ==========
    all_scores = []
    for pattern_file in pattern_files:
        with open(pattern_file, 'r') as f:
            data = json.load(f)
        for key in ["opening_hooks", "transition_phrases", "rhetorical_devices"]:
            for item in data.get(key, []):
                if "effectiveness_score" in item:
                    all_scores.append(item["effectiveness_score"])
    
    if all_scores:
        avg = sum(all_scores) / len(all_scores)
        max_score = max(all_scores)
        min_score = min(all_scores)
        
        if avg > 0.90:
            issues.append("⚠️ 平均评分过高(0.90+)，可能存在评分虚高")
            suggestions.append("建议：人工复核部分高分模板，确保评分客观")
        
        if max_score - min_score < 0.15:
            issues.append("⚠️ 评分分布过于集中（范围<0.15），缺乏区分度")
            suggestions.append("建议：调整评分标准，拉开优秀/普通模板的差距")
    
    # ========== 检查2：semantic_tags完整性 ==========
    missing_tags_count = 0
    sample_episodes = []
    
    for pattern_file in pattern_files[:5]:  # 抽样5个文件
        with open(pattern_file, 'r') as f:
            data = json.load(f)
        
        episode_num = data.get("episode_number", 0)
        
        for hook in data.get("opening_hooks", []):
            tags = hook.get("semantic_tags", {})
            required_dims = ["主题关键词", "适用主题", "叙事模式"]
            missing = [d for d in required_dims if d not in tags or not tags.get(d)]
            
            if missing:
                missing_tags_count += 1
                if episode_num not in sample_episodes:
                    sample_episodes.append(episode_num)
    
    if missing_tags_count > 0:
        issues.append(f"⚠️ {missing_tags_count}个模板的semantic_tags不完整（缺少关键维度）")
        suggestions.append(f"建议：检查Episode {sample_episodes[0] if sample_episodes else 'N/A'}，补全semantic_tags")
    
    # ========== 检查3：Embeddings状态 ==========
    if stats_result["embeddings_status"] == "未生成":
        issues.append("❌ Embeddings未生成，无法进行语义搜索")
        suggestions.append(f"修复：nisb_corpus_enrich(brain_id=\"{brain_id}\")")
    
    # ========== 检查4：数据格式规范性 ==========
    format_issues = 0
    for pattern_file in pattern_files[:3]:
        with open(pattern_file, 'r') as f:
            data = json.load(f)
        
        # 检查timestamp格式
        for hook in data.get("opening_hooks", []):
            ts = hook.get("timestamp", "")
            if ts and ts != "N/A":
                # 简单格式检查（应该是MM:SS或HH:MM:SS）
                if ":" not in ts:
                    format_issues += 1
    
    if format_issues > 0:
        issues.append(f"⚠️ {format_issues}个timestamp格式异常（缺少冒号分隔符）")
        suggestions.append("建议：运行数据清洗脚本，统一timestamp格式")
    
    # ========== 检查5：必需字段完整性 ==========
    required_fields = ["id", "brain_id", "episode_number", "extracted_at"]
    missing_fields_files = []
    
    for pattern_file in pattern_files[:5]:
        with open(pattern_file, 'r') as f:
            data = json.load(f)
        
        missing = [f for f in required_fields if f not in data]
        if missing:
            missing_fields_files.append(os.path.basename(pattern_file))
    
    if missing_fields_files:
        issues.append(f"⚠️ {len(missing_fields_files)}个文件缺少必需字段")
        suggestions.append(f"建议：检查文件 {missing_fields_files[0]}，补全缺失字段")
    
    # ========== 生成诊断报告 ==========
    if not issues:
        return {
            "status": "success",
            "issues": [],
            "suggestions": [],
            "message": f"""🏥 {stats_result['display_name']} 健康检查

✅ 所有检查通过，数据质量良好！

📊 数据概览：
  - Episodes：{stats_result['episodes_count']}个
  - 模板总数：{stats_result['patterns_count']['total']}个
  - 平均评分：{stats_result['avg_effectiveness_score']:.2f}
  - Embeddings：{stats_result['embeddings_status']}

💡 建议：继续保持数据规范，定期运行健康检查"""
        }
    else:
        report_lines = [f"🏥 {stats_result['display_name']} 健康检查"]
        report_lines.append(f"\n🔍 发现{len(issues)}个问题：\n")
        
        for i, issue in enumerate(issues, 1):
            report_lines.append(f"{i}. {issue}")
        
        report_lines.append("\n💡 修复建议：\n")
        for i, suggestion in enumerate(suggestions, 1):
            report_lines.append(f"{i}. {suggestion}")
        
        report_lines.append("\n📊 数据概览：")
        report_lines.append(f"  - Episodes：{stats_result['episodes_count']}个")
        report_lines.append(f"  - 模板总数：{stats_result['patterns_count']['total']}个")
        
        return {
            "status": "warning",
            "issues": issues,
            "suggestions": suggestions,
            "message": "\n".join(report_lines)
        }


# 导出
__all__ = ['nisb_corpus_stats', 'nisb_corpus_doctor']

