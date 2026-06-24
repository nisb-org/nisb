#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Corpus基准对比工具
对比Phase 2.9.6 vs Phase 3.0的创作效果
"""

import os
import json
from glob import glob
from core.storage import get_corpus_base_path


def nisb_corpus_compare_baseline(args: dict) -> dict:
    """
    对比不同Phase的创作基准
    
    Args:
        brain_id: 大脑ID（必填）
        baseline_id_1: 基准1的test_id（可选，默认最新的2.9.6基准）
        baseline_id_2: 基准2的test_id（可选，默认最新的3.0基准）
    
    Returns:
        {
          "status": "success",
          "comparison": {
            "baseline_1": {...},
            "baseline_2": {...},
            "score_diff": {...},
            "winner": "3.0"
          },
          "message": "..."
        }
    """
    brain_id = args.get("brain_id")
    baseline_id_1 = args.get("baseline_id_1")
    baseline_id_2 = args.get("baseline_id_2")
    
    if not brain_id:
        return {"status": "error", "message": "❌ brain_id不能为空"}
    
    # ========== 获取baselines目录 ==========
    base_path = get_corpus_base_path(brain_id)
    baseline_dir = f"{base_path}/storage/baselines"
    
    if not os.path.exists(baseline_dir):
        return {
            "status": "error",
            "message": "❌ 未找到基准数据\n   请先运行 nisb_corpus_test_creation"
        }
    
    # ========== 读取所有基准文件 ==========
    baseline_files = sorted(glob(f"{baseline_dir}/test_*.json"), reverse=True)
    
    if len(baseline_files) < 2:
        return {
            "status": "error",
            "message": f"❌ 基准数据不足（需要至少2个，当前{len(baseline_files)}个）\n"
                       f"   请先运行2次 nisb_corpus_test_creation"
        }
    
    # ========== 确定对比的2个基准 ==========
    baseline_1_data = None
    baseline_2_data = None
    
    if baseline_id_1:
        # 指定基准1
        for bf in baseline_files:
            with open(bf, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if data.get("test_id") == baseline_id_1:
                    baseline_1_data = data
                    break
    else:
        # 自动选择最新的2.9.6基准
        for bf in baseline_files:
            with open(bf, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if data.get("phase") == "2.9.6":
                    baseline_1_data = data
                    break
    
    if baseline_id_2:
        # 指定基准2
        for bf in baseline_files:
            with open(bf, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if data.get("test_id") == baseline_id_2:
                    baseline_2_data = data
                    break
    else:
        # 自动选择最新的3.0基准
        for bf in baseline_files:
            with open(bf, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if data.get("phase") == "3.0":
                    baseline_2_data = data
                    break
    
    if not baseline_1_data:
        return {"status": "error", "message": "❌ 未找到基准1（Phase 2.9.6）"}
    
    if not baseline_2_data:
        # 如果还没有3.0基准，返回提示
        return {
            "status": "success",
            "message": f"✅ Phase 2.9.6基准已保存\n"
                       f"   测试ID：{baseline_1_data['test_id']}\n"
                       f"   整体质量：{baseline_1_data['scores']['overall_quality']:.1f}/10\n\n"
                       f"⏳ 等待Phase 3.0实施后，再次测试同一主题进行对比"
        }
    
    # ========== 计算评分差异 ==========
    score_diff = {}
    for key in baseline_1_data["scores"]:
        diff = baseline_2_data["scores"][key] - baseline_1_data["scores"][key]
        score_diff[key] = {
            "phase_2.9.6": baseline_1_data["scores"][key],
            "phase_3.0": baseline_2_data["scores"][key],
            "diff": diff,
            "improvement": diff > 0
        }
    
    # ========== 判断胜者 ==========
    overall_diff = score_diff["overall_quality"]["diff"]
    winner = "3.0" if overall_diff > 0 else "2.9.6" if overall_diff < 0 else "平局"
    
    # ========== 构建返回消息 ==========
    message = f"""📊 Phase对比结果

主题：{baseline_1_data['topic']}

┌─────────────────────────────────────┐
│  评分对比（满分10分）                │
├─────────────────────────────────────┤
│  维度           2.9.6   3.0   提升   │
├─────────────────────────────────────┤
│  开场吸引力     {baseline_1_data['scores']['opening_appeal']:.1f}    {baseline_2_data['scores']['opening_appeal']:.1f}   {score_diff['opening_appeal']['diff']:+.1f}   │
│  逻辑连贯性     {baseline_1_data['scores']['logic_coherence']:.1f}    {baseline_2_data['scores']['logic_coherence']:.1f}   {score_diff['logic_coherence']['diff']:+.1f}   │
│  修辞效果       {baseline_1_data['scores']['rhetoric_effect']:.1f}    {baseline_2_data['scores']['rhetoric_effect']:.1f}   {score_diff['rhetoric_effect']['diff']:+.1f}   │
│  整体质量       {baseline_1_data['scores']['overall_quality']:.1f}    {baseline_2_data['scores']['overall_quality']:.1f}   {score_diff['overall_quality']['diff']:+.1f}   │
└─────────────────────────────────────┘

🏆 胜者：Phase {winner}

💡 分析：
"""
    
    if overall_diff > 0:
        message += f"Phase 3.0的神经网络机制显著提升了创作质量（+{overall_diff:.1f}分）\n"
        message += "主要改进："
        for key, val in score_diff.items():
            if val["improvement"] and val["diff"] > 0.5:
                message += f"\n  - {key}提升了{val['diff']:.1f}分"
    elif overall_diff < 0:
        message += f"Phase 2.9.6表现更好（-{abs(overall_diff):.1f}分）\n"
        message += "需要优化Phase 3.0的参数设置"
    else:
        message += "两个版本表现相当"
    
    return {
        "status": "success",
        "brain_id": brain_id,
        "baseline_1": baseline_1_data,
        "baseline_2": baseline_2_data,
        "score_diff": score_diff,
        "winner": winner,
        "message": message.strip()
    }


__all__ = ['nisb_corpus_compare_baseline']

