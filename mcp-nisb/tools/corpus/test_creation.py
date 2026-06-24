#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Corpus创作测试工具
用于评估模板库的创作能力（Phase 2.9.6 vs Phase 3.0对比基准）
"""

import time
from datetime import datetime
from .recommend import nisb_corpus_recommend


def nisb_corpus_test_creation(args: dict) -> dict:
    """
    测试创作能力并生成评分基准
    
    Args:
        brain_id: 大脑ID（必填）
        topic: 创作主题（必填，如："AI焦虑与个人AGI"）
        target_length: 目标字数（可选，默认500）
        save_baseline: bool - 是否保存为基准（默认True）
    
    Returns:
        {
          "status": "success",
          "topic": "AI焦虑",
          "test_id": "test_20251020_155530",
          "draft": "生成的文案",
          "templates_used": [...],
          "scores": {
            "opening_appeal": 8.5,  # 开场吸引力 0-10
            "logic_coherence": 7.8,  # 逻辑连贯性 0-10
            "rhetoric_effect": 9.2,  # 修辞效果 0-10
            "overall_quality": 8.5   # 整体质量 0-10
          },
          "phase": "2.9.6",  # 或 "3.0"
          "timestamp": "2025-10-20T15:55:30",
          "message": "..."
        }
    """
    brain_id = args.get("brain_id")
    topic = args.get("topic")
    target_length = args.get("target_length", 500)
    save_baseline = args.get("save_baseline", True)
    
    if not brain_id or not topic:
        return {"status": "error", "message": "❌ brain_id和topic不能为空"}
    
    # ========== 1. 推荐模板组合 ==========
    print(f"⏳ 正在为主题「{topic}」推荐模板...")
    
    recommend_result = nisb_corpus_recommend({
        "brain_id": brain_id,
        "topic": topic,
        "structure": "full",
        "top_k": 3,
        "min_similarity": 0.3
    })
    
    if recommend_result.get("status") != "success":
        return {
            "status": "error",
            "message": f"❌ 模板推荐失败：{recommend_result.get('message')}"
        }
    
    recommendations = recommend_result.get("recommendations", {})
    
    # ========== 2. 组合生成文案 ==========
    print(f"⏳ 正在生成文案（目标{target_length}字）...")
    
    draft, templates_used = _generate_draft(topic, recommendations, target_length)
    
    # ========== 3. 自动评分 ==========
    print(f"⏳ 正在评分...")
    
    scores = _auto_score(draft, templates_used, topic)
    
    # ========== 4. 生成测试ID ==========
    test_id = f"test_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    timestamp = datetime.now().isoformat()
    
    # ========== 5. 保存基准（如果需要） ==========
    if save_baseline:
        from core.storage import get_corpus_base_path
        import os
        import json
        
        base_path = get_corpus_base_path(brain_id)
        baseline_dir = f"{base_path}/storage/baselines"
        os.makedirs(baseline_dir, exist_ok=True)
        
        baseline_file = f"{baseline_dir}/{test_id}.json"
        
        baseline_data = {
            "test_id": test_id,
            "timestamp": timestamp,
            "phase": "2.9.6",  # 当前版本
            "topic": topic,
            "draft": draft,
            "templates_used": templates_used,
            "scores": scores,
            "word_count": len(draft),
            "combination_score": recommend_result.get("combination_score", 0)
        }
        
        with open(baseline_file, 'w', encoding='utf-8') as f:
            json.dump(baseline_data, f, ensure_ascii=False, indent=2)
        
        print(f"✅ 基准已保存：{baseline_file}")
    
    # ========== 6. 构建返回消息 ==========
    message = f"""🎯 创作测试完成

主题：{topic}
测试ID：{test_id}
阶段：Phase 2.9.6

📊 评分：
  开场吸引力：{scores['opening_appeal']:.1f}/10
  逻辑连贯性：{scores['logic_coherence']:.1f}/10
  修辞效果：{scores['rhetoric_effect']:.1f}/10
  整体质量：{scores['overall_quality']:.1f}/10

📝 文案（{len(draft)}字）：
{draft[:200]}...

🔧 使用的模板：
{len(templates_used)}个（{', '.join(set(t['type'] for t in templates_used))}）

💡 改进建议：
{_generate_improvement_tips(scores)}
"""
    
    return {
        "status": "success",
        "test_id": test_id,
        "brain_id": brain_id,
        "topic": topic,
        "draft": draft,
        "templates_used": templates_used,
        "scores": scores,
        "phase": "2.9.6",
        "timestamp": timestamp,
        "baseline_saved": save_baseline,
        "message": message.strip()
    }


def _generate_draft(topic: str, recommendations: dict, target_length: int) -> tuple:
    """
    组合模板生成文案
    
    Returns:
        (draft_text, templates_used)
    """
    sections = []
    templates_used = []
    
    # ========== 开场（Opening Hook） ==========
    opening_hooks = recommendations.get("opening_hooks", [])
    if opening_hooks:
        hook = opening_hooks[0]  # 使用TOP 1
        sections.append(hook.get("text", ""))
        templates_used.append({
            "type": "opening_hooks",
            "episode": hook.get("episode"),
            "text": hook.get("text", "")[:50] + "...",
            "similarity": hook.get("similarity", 0)
        })
    else:
        sections.append(f"关于{topic}，我们需要深入思考。")
    
    # ========== 主体（Transition + Rhetoric） ==========
    transitions = recommendations.get("transition_phrases", [])
    devices = recommendations.get("rhetorical_devices", [])
    
    # 添加过渡
    if transitions:
        trans = transitions[0]
        sections.append(f"\n\n{trans.get('text', '')}")
        templates_used.append({
            "type": "transition_phrases",
            "episode": trans.get("episode"),
            "text": trans.get("text", "")[:50] + "...",
            "similarity": trans.get("similarity", 0)
        })
    
    # 添加修辞示例
    if devices:
        device = devices[0]
        sections.append(f"\n\n{device.get('text', device.get('example', ''))}")
        templates_used.append({
            "type": "rhetorical_devices",
            "episode": device.get("episode"),
            "text": device.get("text", device.get('example', ''))[:50] + "...",
            "similarity": device.get("similarity", 0)
        })
    
    # ========== 解释（Explanation Pattern） ==========
    explanations = recommendations.get("explanation_patterns", [])
    if explanations:
        exp = explanations[0]
        sections.append(f"\n\n{exp.get('simple_explanation', '')}")
        templates_used.append({
            "type": "explanation_patterns",
            "episode": exp.get("episode"),
            "concept": exp.get("concept", ""),
            "text": exp.get("simple_explanation", "")[:50] + "...",
            "similarity": exp.get("similarity", 0)
        })
    
    # ========== 组合成完整文案 ==========
    draft = "".join(sections)
    
    # 如果过长，截断；如果过短，补充过渡句
    if len(draft) > target_length:
        draft = draft[:target_length] + "..."
    elif len(draft) < target_length * 0.8:
        draft += f"\n\n这就是关于{topic}的思考。"
    
    return draft, templates_used


def _auto_score(draft: str, templates_used: list, topic: str) -> dict:
    """
    自动评分（简化版，基于规则）
    
    Phase 3.0可以用LLM优化评分逻辑
    """
    scores = {}
    
    # 1. 开场吸引力（基于是否使用高评分开场钩子）
    opening_templates = [t for t in templates_used if t["type"] == "opening_hooks"]
    if opening_templates:
        opening_score = opening_templates[0].get("similarity", 0.5) * 10
        scores["opening_appeal"] = min(10, opening_score)
    else:
        scores["opening_appeal"] = 5.0
    
    # 2. 逻辑连贯性（基于是否使用转折短语）
    transition_templates = [t for t in templates_used if t["type"] == "transition_phrases"]
    if transition_templates:
        scores["logic_coherence"] = 8.0
    else:
        scores["logic_coherence"] = 6.0
    
    # 3. 修辞效果（基于修辞手法数量）
    rhetoric_templates = [t for t in templates_used if t["type"] == "rhetorical_devices"]
    scores["rhetoric_effect"] = min(10, 6.0 + len(rhetoric_templates) * 2)
    
    # 4. 整体质量（平均值）
    scores["overall_quality"] = (
        scores["opening_appeal"] * 0.4 +
        scores["logic_coherence"] * 0.3 +
        scores["rhetoric_effect"] * 0.3
    )
    
    return scores


def _generate_improvement_tips(scores: dict) -> str:
    """生成改进建议"""
    tips = []
    
    if scores["opening_appeal"] < 7:
        tips.append("- 尝试使用效果评分更高的开场钩子")
    
    if scores["logic_coherence"] < 7:
        tips.append("- 增加转折短语，提升逻辑连贯性")
    
    if scores["rhetoric_effect"] < 7:
        tips.append("- 适当穿插修辞手法，增强感染力")
    
    if scores["overall_quality"] >= 8:
        tips.append("- 整体质量优秀，继续保持！")
    
    return "\n".join(tips) if tips else "- 整体表现良好"


__all__ = ['nisb_corpus_test_creation']

