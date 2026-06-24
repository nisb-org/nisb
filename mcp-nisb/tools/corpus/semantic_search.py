#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Corpus语义搜索（Phase 4.0增强版）
⭐⭐⭐ L2+L4融合创作方案 ⭐⭐⭐

新增功能：
- ✅ L4方法论自动检测
- ✅ L2+L4融合建议
- ✅ 完整创作方案生成
- ✅ 单工具完整返回（不新增MCP工具）
"""

import os
import json
import numpy as np
from typing import Dict, List, Optional, Tuple

from core.openai_utils import get_embedding
from core.storage import (
    get_corpus_base_path, 
    load_corpus_embeddings,
    load_json
)


# ============================================================
# L4方法论字典（硬编码，基于3集提取）
# ============================================================

L4_METHODS = {
    "L4-1": {
        "name": "悬念对比开场法",
        "description": "同一类目标不同结果对比制造悬念",
        "timing": "0-2分钟"
    },
    "L4-2": {
        "name": "故事驱动人物链",
        "description": "多个真实人物故事递进",
        "timing": "2-5分钟"
    },
    "L4-3": {
        "name": "感官记忆具象化三段式",
        "description": "日常比喻→机制→强化",
        "timing": "5-12分钟"
    },
    "L4-4": {
        "name": "权威链递进法",
        "description": "民间→历史→考古→官方",
        "timing": "2-4分钟"
    }
}


# ============================================================
# 主函数：增强的语义搜索
# ============================================================

def nisb_corpus_semantic_search(args: dict) -> dict:
    """
    基于语义相似度搜索最匹配的corpus模板（Phase 4.0增强版）
    
    ⭐ 新增：L4方法论检测 + L2+L4融合建议 + 完整创作方案
    
    Args:
        brain_id: UP主ID（如：brain_utopia）
        query: 自然语言查询
        pattern_type: 模板类型（opening_hooks/transition_phrases/rhetorical_devices/explanation_patterns/all）
        top_k: 返回数量（默认5）
        min_similarity: 最低相似度阈值（默认0.3）
    
    Returns:
        {
          "status": "success",
          "query": "查询文本",
          "total_searched": 800,
          "matches": [
            {
              "text": "模板文本",
              "episode": 302,
              "pattern_type": "opening_hooks",
              "similarity": 0.92,
              "effectiveness_score": 0.9,
              "timestamp": "00:05",
              "semantic_tags": {...},
              "usage_hint": "改写建议：..."
            },
            ...
          ],
          
          # ⭐⭐⭐ 新增L4层返回 ⭐⭐⭐
          "l4_context": {
            "L4-1": {"name": "悬念对比开场法", "episodes": [306, 309], "avg_confidence": 0.94},
            ...
          },
          "l4_recommendations": [
            {
              "l4_id": "L4-1",
              "l4_name": "悬念对比开场法",
              "episode": 302,
              "pattern_type": "opening_hooks",
              "strategy": "用Episode 302的开场钩子融入L4-1的悬念反问",
              "fit_score": 0.92
            },
            ...
          ],
          "creation_guide": "【主题】...\n【推荐L4流程】...\n【创作方案】...",
          
          "message": "..."
        }
    """
    # ========== 1. 参数解析 ==========
    brain_id = args.get("brain_id")
    query = args.get("query")
    pattern_type = args.get("pattern_type", "all")
    top_k = args.get("top_k", 5)
    min_similarity = args.get("min_similarity", 0.3)
    
    if not brain_id or not query:
        return {
            "status": "error",
            "message": "❌ brain_id和query不能为空"
        }
    
    # ========== 2. 检查embeddings是否存在 ==========
    embeddings, metadata = load_corpus_embeddings(brain_id)
    
    if embeddings is None:
        return {
            "status": "error",
            "message": f"❌ {brain_id}的embeddings未生成\n   请先执行：nisb_corpus_enrich(brain_id=\"{brain_id}\")"
        }
    
    # ========== 3. 生成query embedding ==========
    try:
        query_embedding = np.array(get_embedding(query))
    except Exception as e:
        return {
            "status": "error",
            "message": f"❌ Query embedding生成失败：{e}"
        }
    
    # ========== 4. 按pattern_type过滤 ==========
    if pattern_type != "all":
        filtered_indices = [i for i, m in enumerate(metadata) if m.get("pattern_type") == pattern_type]
        filtered_embeddings = embeddings[filtered_indices]
        filtered_metadata = [metadata[i] for i in filtered_indices]
    else:
        filtered_embeddings = embeddings
        filtered_metadata = metadata
    
    if len(filtered_embeddings) == 0:
        return {
            "status": "success",
            "query": query,
            "total_searched": 0,
            "matches": [],
            "l4_context": {},
            "l4_recommendations": [],
            "creation_guide": "",
            "message": f"⚠️  未找到{pattern_type}类型的模板\n💡 提示：尝试修改pattern_type参数或使用\"all\""
        }
    
    # ========== 5. 计算余弦相似度 ==========
    query_norm = query_embedding / np.linalg.norm(query_embedding)
    embeddings_norm = filtered_embeddings / np.linalg.norm(filtered_embeddings, axis=1, keepdims=True)
    similarities = np.dot(embeddings_norm, query_norm)
    
    # ========== 6. 排序并返回TOP K ==========
    top_indices = np.argsort(similarities)[-top_k:][::-1]
    
    matches = []
    episode_ids = set()
    
    for idx in top_indices:
        similarity = float(similarities[idx])
        
        if similarity < min_similarity:
            continue
        
        match = filtered_metadata[idx].copy()
        match["similarity"] = similarity
        
        # ⭐⭐⭐ 核心优化：添加使用提示 ⭐⭐⭐
        match["usage_hint"] = _generate_usage_hint(match)
        
        matches.append(match)
        episode_ids.add(match.get("episode"))
    
    # ========== 7. ⭐ 新增：L4层检测 ==========
    l4_context = _detect_l4_for_episodes(brain_id, episode_ids)
    
    # ========== 8. ⭐ 新增：L4+L2融合建议 ==========
    l4_recommendations = _generate_l4_recommendations(matches, l4_context)
    
    # ========== 9. ⭐ 新增：完整创作方案 ==========
    creation_guide = _generate_creation_guide(matches, l4_context, l4_recommendations, query)
    
    # ========== 10. 构建返回消息 ==========
    if not matches:
        message = f"""⚠️  未找到相似度≥{min_similarity}的模板

💡 优化建议：
  1. 降低min_similarity参数（当前{min_similarity}）
  2. 尝试更具体的查询词（如"反问句开场"而非"开场"）
  3. 检查数据：nisb_corpus_stats(brain_id="{brain_id}")"""
    else:
        message_lines = [
            f"✅ 找到{len(matches)}个匹配模板（相似度：{matches[0]['similarity']:.2f}-{matches[-1]['similarity']:.2f}）\n",
            "【L2内容】（传统模板）"
        ]
        
        for i, match in enumerate(matches[:3], 1):
            message_lines.append(f"  {i}. Episode {match['episode']} ({match['pattern_type']})")
            message_lines.append(f"     📊 相似度: {match['similarity']:.2f} | 效果评分: {match.get('effectiveness_score', 0):.2f}")
            message_lines.append(f"     📝 内容: {match['text'][:80]}...")
            message_lines.append(f"     💡 使用提示: {match['usage_hint']}")
            if match.get('timestamp'):
                message_lines.append(f"     ⏱️  时间点: {match['timestamp']}")
            message_lines.append("")
        
        if len(matches) > 3:
            message_lines.append(f"... 还有{len(matches)-3}个结果（通过matches字段获取）")
        
        # ⭐ 新增：L4方法论显示
        if l4_context:
            message_lines.append("")
            message_lines.append("【L4方法论】（新增）")
            for l4_id, info in l4_context.items():
                message_lines.append(f"  • {info['name']} (检测到{len(info['episodes'])}个episode)")
        
        # ⭐ 新增：融合建议显示
        if l4_recommendations:
            message_lines.append("")
            message_lines.append("【L2+L4融合建议】（创作方案）")
            for i, rec in enumerate(l4_recommendations[:3], 1):
                message_lines.append(f"  {i}. {rec['l4_name']} + Episode {rec['episode']}")
                message_lines.append(f"     方案: {rec['strategy'][:100]}...")
        
        # ⭐ 新增：完整创作指导
        message_lines.append("")
        message_lines.append("【完整创作指导】（立即可用）")
        message_lines.append(creation_guide[:300] + "...")
        
        message_lines.append("\n💡 下一步操作：")
        message_lines.append("  - 查看完整creation_guide字段获得详细方案")
        message_lines.append("  - 查看l4_recommendations获得L4+L2配对方案")
        
        message = "\n".join(message_lines)
    
    return {
        "status": "success",
        "query": query,
        "pattern_type": pattern_type,
        "total_searched": len(filtered_embeddings),
        "matches": matches,
        
        # ⭐⭐⭐ 新增返回字段（L4层） ⭐⭐⭐
        "l4_context": l4_context,
        "l4_recommendations": l4_recommendations,
        "creation_guide": creation_guide,
        
        "message": message
    }


# ============================================================
# 辅助函数1：生成使用提示（保留现有逻辑）
# ============================================================

def _generate_usage_hint(match: dict) -> str:
    """
    为Agent生成使用提示（规则引擎，0成本）
    
    基于模板类型和文本特征，自动生成改写建议
    """
    pattern_type = match.get("pattern_type", "")
    text = match.get("text", "")
    
    if pattern_type == "opening_hooks":
        if "？" in text or "?" in text:
            return "改写建议：保留反问结构，替换主题词即可"
        elif "有没有" in text or "是不是" in text:
            return "改写建议：通用开场模板，替换场景描述"
        elif text.startswith("公元") or text.startswith("在"):
            return "改写建议：时间/地点引入型，调整时空背景"
        elif "数据" in text or "%" in text:
            return "改写建议：数据驱动型开场，替换统计数据"
        else:
            return "改写建议：直接引用或微调语气词"
    
    elif pattern_type == "transition_phrases":
        if "但是" in text or "然而" in text:
            return "改写建议：转折型，在观点对比时使用"
        elif "那么" in text or "所以" in text:
            return "改写建议：递进型，在推理或总结时使用"
        elif "首先" in text or "其次" in text:
            return "改写建议：结构型，在多点论述时使用"
        else:
            return "改写建议：在需要过渡/衔接时原样使用"
    
    elif pattern_type == "rhetorical_devices":
        device_type = match.get("type", "修辞手法")
        if device_type == "类比":
            return f"改写建议：{device_type}手法，找对应对象替换"
        elif device_type == "反问":
            return f"改写建议：{device_type}手法，保留句式替换问题"
        elif device_type == "对比":
            return f"改写建议：{device_type}手法，替换对比事物"
        else:
            return f"改写建议：{device_type}手法，替换具体内容"
    
    elif pattern_type == "explanation_patterns":
        concept = match.get("concept", "")
        if concept:
            return f"改写建议：通俗解释模板，将'{concept}'替换为专业术语"
        else:
            return "改写建议：通俗化解释框架，替换概念和类比"
    
    else:
        return "改写建议：根据上下文调整措辞，保持核心结构"


# ============================================================
# ⭐⭐⭐ 辅助函数2：L4方法论检测（新增）
# ============================================================

def _detect_l4_for_episodes(brain_id: str, episode_ids: set) -> dict:
    """
    为检测到的episodes查找适用的L4方法论
    
    从L4 JSON文件中提取episode的L4信息
    
    返回：{
        "L4-1": {"name": "悬念对比开场法", "episodes": [306, 309], "avg_confidence": 0.92},
        "L4-2": {"name": "故事驱动人物链", "episodes": [307], "avg_confidence": 0.88},
        ...
    }
    """
    
    if not episode_ids:
        return {}
    
    base_path = get_corpus_base_path(brain_id)
    l4_by_episode_dir = f"{base_path}/storage/entities/l4_methods/by_episode"
    
    if not os.path.exists(l4_by_episode_dir):
        return {}
    
    l4_context = {}
    
    # 遍历每个episode，查找其L4信息
    for ep_id in episode_ids:
        l4_file = f"{l4_by_episode_dir}/ep{ep_id}_l4.json"
        
        if not os.path.exists(l4_file):
            continue
        
        try:
            l4_data = load_json(l4_file)
            if not l4_data:
                continue
            
            patterns = l4_data.get("l4_patterns_extracted", [])
            
            for pattern in patterns:
                l4_id = pattern.get("l4_id", "unknown")
                l4_name = pattern.get("l4_name", "未知")
                confidence = pattern.get("confidence", 0)
                
                if l4_id not in l4_context:
                    l4_context[l4_id] = {
                        "name": l4_name,
                        "episodes": [],
                        "confidences": [],
                        "avg_confidence": 0
                    }
                
                l4_context[l4_id]["episodes"].append(ep_id)
                l4_context[l4_id]["confidences"].append(confidence)
        
        except Exception as e:
            print(f"[WARN] 读取L4文件失败 {l4_file}: {e}")
            continue
    
    # 计算平均置信度
    for l4_id in l4_context:
        confidences = l4_context[l4_id]["confidences"]
        l4_context[l4_id]["avg_confidence"] = (
            sum(confidences) / len(confidences) if confidences else 0
        )
        del l4_context[l4_id]["confidences"]  # 删除临时数据
    
    return l4_context


# ============================================================
# ⭐⭐⭐ 辅助函数3：L4+L2融合建议（新增）
# ============================================================

def _generate_l4_recommendations(matches: list, l4_context: dict) -> list:
    """
    生成L4+L2的具体融合建议
    
    为每个match推荐最适合的L4方法论和融合策略
    
    返回：[
        {
            "l4_id": "L4-1",
            "l4_name": "悬念对比开场法",
            "episode": 306,
            "pattern_type": "opening_hooks",
            "strategy": "用Episode 306的开场钩子作为对比基础，融入L4-1的反问框架",
            "fit_score": 0.94
        },
        ...
    ]
    """
    
    recommendations = []
    
    # 为每个match分配最适合的L4
    for match in matches:
        episode = match["episode"]
        pattern_type = match["pattern_type"]
        similarity = match["similarity"]
        
        # 基于pattern_type推荐L4
        if pattern_type == "opening_hooks":
            best_l4 = "L4-1"
            strategy = f"用Episode {episode}的开场钩子作为对比基础，融入L4-1的悬念反问"
        
        elif pattern_type == "rhetorical_devices":
            best_l4 = "L4-3"
            strategy = f"用Episode {episode}的修辞手法来具象化L4-3的'比喻→机制→强化'三段式"
        
        elif pattern_type == "transition_phrases":
            best_l4 = "L4-2"
            strategy = f"用Episode {episode}的转折短语承接故事叙述，强化L4-2的递进效果"
        
        else:  # explanation_patterns
            best_l4 = "L4-3"
            strategy = f"用Episode {episode}的解释方式配合L4-3的具象化框架"
        
        recommendations.append({
            "l4_id": best_l4,
            "l4_name": L4_METHODS.get(best_l4, {}).get("name", best_l4),
            "episode": episode,
            "pattern_type": pattern_type,
            "strategy": strategy,
            "fit_score": round(similarity, 2)
        })
    
    return recommendations


# ============================================================
# ⭐⭐⭐ 辅助函数4：完整创作方案生成（新增）
# ============================================================

def _generate_creation_guide(
    matches: list, 
    l4_context: dict, 
    l4_recommendations: list,
    query: str
) -> str:
    """
    生成完整的创作指导（可直接用于创作）
    
    返回：结构化的创作方案文本
    """
    
    lines = [
        f"【创作主题】{query}",
        "=" * 60,
        ""
    ]
    
    # 推荐的L4顺序和时间分配
    l4_flow = ["L4-1", "L4-2", "L4-3", "L4-4"]
    time_allocation = {"L4-1": 2, "L4-2": 3, "L4-3": 5, "L4-4": 2}
    
    current_time = 0
    
    for l4_id in l4_flow:
        if l4_id not in l4_context:
            continue
        
        l4_info = L4_METHODS.get(l4_id, {})
        l4_name = l4_info.get("name", l4_id)
        duration = time_allocation.get(l4_id, 2)
        
        # 找到对应的recommendation
        matching_recs = [r for r in l4_recommendations if r["l4_id"] == l4_id]
        
        lines.append(f"【{current_time}-{current_time + duration}分钟】{l4_name}")
        lines.append(f"   规则: {l4_info.get('description', '')}")
        
        if matching_recs:
            for rec in matching_recs:
                lines.append(f"   ├─ 融入: Episode {rec['episode']}的{rec['pattern_type']}")
                lines.append(f"   ├─ 方案: {rec['strategy']}")
                lines.append(f"   └─ 相关度: {rec['fit_score']:.0%}")
        
        lines.append("")
        current_time += duration
    
    lines.append("【创作流程指导】")
    lines.append("1. 参考上述L4流程规划内容结构（0-15分钟）")
    lines.append("2. 在每个时间段使用对应的L2模板内容")
    lines.append("3. 用L4方法论框架组织语言逻辑")
    lines.append("4. 确保观众体验完整的叙述弧（开场悬念→人物故事→深度讲解→权威总结）")
    lines.append("")
    lines.append("【使用建议】")
    lines.append(f"• 总episodes参考: {len(l4_context)}个不同的L4方法")
    lines.append(f"• L2模板数量: {len(matches)}个（已按相似度排序）")
    lines.append("• 先按L4框架搭建结构，再填入L2的具体内容")
    lines.append("• 每个L4环节可多次使用不同的L2模板组合")
    
    return "\n".join(lines)


# ============================================================
# 导出
# ============================================================

__all__ = ['nisb_corpus_semantic_search']

