#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Corpus智能推荐工具
基于主题推荐最佳模板组合
"""

from .semantic_search import nisb_corpus_semantic_search


def nisb_corpus_recommend(args: dict) -> dict:
    """
    基于主题智能推荐模板组合
    
    Args:
        brain_id: 大脑ID（必填）
        topic: 主题描述（必填，如："气候变化与环境危机"）
        structure: 文章结构（可选，默认"full"）
          - full: 完整结构（开场+转折+修辞+解释）
          - opening: 只推荐开场
          - body: 只推荐主体（转折+修辞）
          - closing: 只推荐收尾
        top_k: 每个类型返回数量（默认3）
        min_similarity: 最低相似度（默认0.7）
    
    Returns:
        {
          "status": "success",
          "topic": "气候变化",
          "structure": "full",
          "recommendations": {
            "opening_hooks": [...],
            "transition_phrases": [...],
            "rhetorical_devices": [...],
            "explanation_patterns": [...]
          },
          "combination_score": 0.88,
          "usage_guide": "...",
          "message": "..."
        }
    """
    brain_id = args.get("brain_id")
    topic = args.get("topic")
    structure = args.get("structure", "full")
    top_k = args.get("top_k", 3)
    min_similarity = args.get("min_similarity", 0.3)
    
    if not brain_id or not topic:
        return {"status": "error", "message": "❌ brain_id和topic不能为空"}
    
    # ========== 根据structure决定查询哪些类型 ==========
    pattern_types = {
        "full": ["opening_hooks", "transition_phrases", "rhetorical_devices", "explanation_patterns"],
        "opening": ["opening_hooks"],
        "body": ["transition_phrases", "rhetorical_devices", "explanation_patterns"],
        "closing": ["transition_phrases", "rhetorical_devices"]
    }
    
    types_to_query = pattern_types.get(structure, pattern_types["full"])
    
    # ========== 为每个类型执行语义搜索 ==========
    recommendations = {}
    all_scores = []
    
    for pattern_type in types_to_query:
        result = nisb_corpus_semantic_search({
            "brain_id": brain_id,
            "query": topic,
            "pattern_type": pattern_type,
            "top_k": top_k,
            "min_similarity": min_similarity
        })
        
        if result.get("status") == "success":
            matches = result.get("matches", [])
            recommendations[pattern_type] = matches
            
            # 收集相似度评分
            all_scores.extend([m.get("similarity", 0) for m in matches])
    
    # ========== 计算组合评分 ==========
    combination_score = sum(all_scores) / len(all_scores) if all_scores else 0
    
    # ========== 生成使用指南 ==========
    usage_guide = _generate_usage_guide(recommendations, topic)
    
    # ========== 构建返回消息 ==========
    message_lines = [
        f"🎯 主题推荐：{topic}",
        f"   结构：{structure}",
        f"   组合评分：{combination_score:.2f}",
        ""
    ]
    
    for ptype, items in recommendations.items():
        if items:
            message_lines.append(f"✅ {ptype}：{len(items)}个")
            # 显示第一个推荐
            first = items[0]
            message_lines.append(f"   TOP 1 (相似度 {first.get('similarity', 0):.2f})：")
            message_lines.append(f"   {first.get('text', first.get('example', 'N/A'))[:80]}...")
            message_lines.append("")
    
    message_lines.append(f"💡 使用建议：\n{usage_guide}")
    
    return {
        "status": "success",
        "brain_id": brain_id,
        "topic": topic,
        "structure": structure,
        "recommendations": recommendations,
        "combination_score": round(combination_score, 2),
        "usage_guide": usage_guide,
        "message": "\n".join(message_lines)
    }


def _generate_usage_guide(recommendations: dict, topic: str) -> str:
    """生成使用指南"""
    guide_lines = []
    
    if "opening_hooks" in recommendations and recommendations["opening_hooks"]:
        hook = recommendations["opening_hooks"][0]
        guide_lines.append(f"1. 开场：使用Episode {hook.get('episode')}的钩子（评分{hook.get('effectiveness_score', 0):.2f}）")
    
    if "transition_phrases" in recommendations and recommendations["transition_phrases"]:
        phrase = recommendations["transition_phrases"][0]
        guide_lines.append(f"2. 转折：在论述{topic}的观点后，使用Episode {phrase.get('episode')}的转折句引入对立面")
    
    if "rhetorical_devices" in recommendations and recommendations["rhetorical_devices"]:
        device = recommendations["rhetorical_devices"][0]
        guide_lines.append(f"3. 修辞：适当穿插{device.get('type', '修辞手法')}（参考Episode {device.get('episode')}）")
    
    if "explanation_patterns" in recommendations and recommendations["explanation_patterns"]:
        exp = recommendations["explanation_patterns"][0]
        guide_lines.append(f"4. 解释：简化专业概念时，参考Episode {exp.get('episode')}的方式")
    
    return "\n".join(guide_lines) if guide_lines else "暂无使用建议"


__all__ = ['nisb_corpus_recommend']

