#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
NISB Relations Quality Management - Phase 3.0（批次版 + 泛化词配置化）
关系质量管理：分析、批次进化

核心优化：
1. relation_analyze: 只读分析，保持原样
2. relation_evolve: 批次删除（每批1000条关系，支持10万+）+ 泛化词配置化

适配场景：1核1G VPS + 10万+关系
"""

import os
import json
from datetime import datetime
from collections import defaultdict
from typing import List, Dict
import sys
sys.path.insert(0, '/srv')

from core.relations import (
    load_relations_index, 
    get_relations_by_concept,
    delete_relation,
    RELATION_TYPES
)
from core.storage import get_user_base_path, ensure_user_directory, load_concepts_index
from core.user_context import auto_user_context, get_user_ctx

# =====================================================================
# 泛化词加载（从配置文件）
# =====================================================================

def _load_generic_words_for_quality() -> List[str]:
    """
    从配置文件加载泛化词列表
    
    Returns:
        ["今天", "笔记", "系统", ...]（所有泛化词的合并列表）
    """
    config_file = "/srv/config/generic_words.json"
    
    if not os.path.exists(config_file):
        print("[WARN] 泛化词配置文件不存在，使用默认列表")
        return ["今天", "笔记", "系统", "用户", "工具", "功能"]
    
    try:
        with open(config_file, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        all_words = []
        
        categories = config.get("categories", {})
        for category_data in categories.values():
            all_words.extend(category_data.get("words", []))
        
        custom_words = config.get("custom", {}).get("words", [])
        all_words.extend(custom_words)
        
        all_words = [word.lower() for word in all_words]
        
        print(f"[INFO] ✅ 加载泛化词配置：{len(all_words)}个词")
        
        return all_words
    
    except Exception as e:
        print(f"[ERROR] 加载泛化词配置失败：{e}")
        return ["今天", "笔记", "系统", "用户", "工具", "功能"]


# =====================================================================
# 方法1：关系网络质量分析（保持原样，只读不超时）
# =====================================================================
@auto_user_context
def nisb_relation_analyze(args: dict) -> dict:
    """
    分析关系网络质量（诊断工具）
    
    参数:
        user_id: string (自动注入)
    
    返回:
        {
          status,
          quality_score: 0.75,
          metrics: {...},
          issues: [...],
          recommendations: [...]
        }
    """   
    # 加载数据
    concepts_index = load_concepts_index(base_path)
    concepts = concepts_index.get("concepts", {})
    relations_index = load_relations_index(base_path)
    
    total_relations = relations_index.get("total", 0)
    
    if total_relations == 0:
        return {
            "status": "success",
            "quality_score": 0,
            "message": "⚠️  暂无关系数据，无法分析"
        }
    
    # 计算指标
    num_concepts = len(concepts)
    adjacency = relations_index.get("adjacency", {})
    connected_concepts = len(adjacency)
    
    # 密度
    max_edges = num_concepts * (num_concepts - 1) if num_concepts > 1 else 1
    density = total_relations / max_edges
    
    # 平均度
    avg_degree = total_relations / connected_concepts if connected_concepts > 0 else 0
    
    # 孤立概念
    isolated_concepts = num_concepts - connected_concepts
    
    # 扫描所有关系，统计问题
    weak_relations = []
    generic_word_relations = []
    never_activated_relations = []
    
    # ⭐ 从配置文件加载泛化词
    generic_words = _load_generic_words_for_quality()
    
    # 扫描关系文件
    relations_dir = f"{base_path}/storage/entities/relations/by_type"
    
    for rel_type in RELATION_TYPES.keys():
        rel_file = f"{relations_dir}/{rel_type}.jsonl"
        if not os.path.exists(rel_file):
            continue
        
        with open(rel_file, 'r', encoding='utf-8') as f:
            for line in f:
                if not line.strip():
                    continue
                
                try:
                    rel = json.loads(line)
                    
                    if rel.get("deleted", False):
                        continue
                    
                    # 检查弱关系
                    if rel["strength"] < 0.3:
                        weak_relations.append(rel["relation_id"])
                    
                    # 检查泛化词
                    from_name = concepts.get(rel["from_id"], {}).get("name", "").lower()
                    to_name = concepts.get(rel["to_id"], {}).get("name", "").lower()
                    from_name_zh = concepts.get(rel["from_id"], {}).get("name_zh", "").lower()
                    to_name_zh = concepts.get(rel["to_id"], {}).get("name_zh", "").lower()
                    
                    for word in generic_words:
                        if (word in from_name or word in to_name or
                            word in from_name_zh or word in to_name_zh):
                            generic_word_relations.append(rel["relation_id"])
                            break
                    
                    # 检查从未激活的关系
                    if rel.get("co_activation_count", 0) == 0:
                        never_activated_relations.append(rel["relation_id"])
                
                except:
                    continue
    
    # 计算质量分数（0-1）
    quality_score = 1.0
    
    # 惩罚因素
    if density > 0.05:
        quality_score -= 0.2
    if avg_degree > 10:
        quality_score -= 0.2
    if isolated_concepts > num_concepts * 0.1:
        quality_score -= 0.1
    if len(weak_relations) > total_relations * 0.3:
        quality_score -= 0.3
    if len(generic_word_relations) > total_relations * 0.2:
        quality_score -= 0.2
    
    quality_score = max(0, quality_score)
    
    # 构建问题列表
    issues = []
    
    if isolated_concepts > 0:
        issues.append({
            "type": "isolated_concepts",
            "count": isolated_concepts,
            "severity": "medium",
            "suggestion": "使用 nisb_relation_recommend 为孤立概念创建关系"
        })
    
    if weak_relations:
        issues.append({
            "type": "weak_relations",
            "count": len(weak_relations),
            "threshold": 0.3,
            "severity": "high",
            "suggestion": "使用 nisb_relation_evolve 自动删除弱关系"
        })
    
    if generic_word_relations:
        issues.append({
            "type": "generic_word_pollution",
            "count": len(generic_word_relations),
            "severity": "high",
            "suggestion": "重建Relations，添加泛化词过滤"
        })
    
    if never_activated_relations:
        issues.append({
            "type": "never_activated",
            "count": len(never_activated_relations),
            "severity": "low",
            "suggestion": "这些关系可能不常用，考虑删除"
        })
    
    # 构建建议
    recommendations = []
    
    if quality_score < 0.5:
        recommendations.append("⚠️  网络质量较差，建议清空重建Relations")
    elif quality_score < 0.7:
        recommendations.append("建议使用 nisb_relation_evolve 优化网络")
    else:
        recommendations.append("✅ 网络质量良好")
    
    if isolated_concepts > 0:
        recommendations.append(f"建议为{isolated_concepts}个孤立概念创建关系")
    
    if weak_relations:
        recommendations.append(f"建议删除{len(weak_relations)}条弱关系")
    
    if generic_word_relations:
        recommendations.append(f"建议删除{len(generic_word_relations)}条泛化词关系")
    
    # 格式化输出
    lines = ["📊 关系网络质量分析\n"]
    lines.append(f"质量评分：{'⭐' * int(quality_score * 5)} {quality_score:.2f}/1.00\n")
    
    lines.append("网络指标：")
    lines.append(f"  总关系数：{total_relations}条")
    lines.append(f"  连接概念：{connected_concepts}/{num_concepts}个")
    lines.append(f"  网络密度：{density:.4f}（理想值：0.02-0.03）")
    lines.append(f"  平均度：{avg_degree:.2f}（理想值：2-3）")
    lines.append(f"  孤立概念：{isolated_concepts}个\n")
    
    if issues:
        lines.append("发现问题：")
        for i, issue in enumerate(issues, 1):
            severity_emoji = {"low": "🟢", "medium": "🟡", "high": "🔴"}
            lines.append(f"  {i}. {severity_emoji[issue['severity']]} {issue['type']}：{issue['count']}个")
            lines.append(f"      {issue['suggestion']}")
        lines.append("")
    
    lines.append("优化建议：")
    for rec in recommendations:
        lines.append(f"  • {rec}")
    
    message = "\n".join(lines)
    
    return {
        "status": "success",
        "quality_score": round(quality_score, 2),
        "metrics": {
            "density": round(density, 4),
            "avg_degree": round(avg_degree, 2),
            "isolated_concepts": isolated_concepts,
            "total_relations": total_relations,
            "connected_concepts": connected_concepts
        },
        "issues": issues,
        "recommendations": recommendations,
        "message": message
    }


# =====================================================================
# 方法2：关系网络批次进化（批次版：每批1000条）+ 泛化词配置化
# =====================================================================
@auto_user_context
def nisb_relation_evolve(args: dict) -> dict:
    """
    关系网络批次进化（批次版：分批删除，避免超时）
    
    设计理念：
    - 每批处理1000条关系，30秒内完成
    - 支持断点续传，已处理的批次不重复
    - 实时进度提示
    - 支持10万+关系
    - ⭐ 泛化词从配置文件加载（188个词）
    
    策略:
        1. 删除强度<0.3的弱关系
        2. 删除泛化词关系
        3. 删除从未激活的关系（可选）
    
    参数:
        batch_size: integer (可选，每批处理的关系数，默认1000)
        batch_index: integer (可选，处理第几批，从0开始，默认0)
          - 使用-1自动处理下一批（推荐）
        delete_weak: boolean (可选，是否删除弱关系，默认True)
        weak_threshold: float (可选，弱关系阈值，默认0.3)
        delete_generic: boolean (可选，是否删除泛化词关系，默认True)
        delete_never_activated: boolean (可选，是否删除从未激活的关系，默认False)
        user_id: string (自动注入)
    
    返回:
        {
          status,
          batch_index,
          batch_total,
          deleted_in_batch: 150,
          progress: "3/10 (30%)",
          next_batch: 4,
          is_complete: false,
          message
        }
    """
    
    # 参数解析
    batch_size = int(args.get("batch_size", 1000))
    batch_index = int(args.get("batch_index", 0))
    delete_weak = args.get("delete_weak", True)
    weak_threshold = float(args.get("weak_threshold", 0.3))
    delete_generic = args.get("delete_generic", True)
    delete_never_activated = args.get("delete_never_activated", False)
    
    # 加载数据
    concepts_index = load_concepts_index(base_path)
    concepts = concepts_index.get("concepts", {})
    relations_index = load_relations_index(base_path)
    total_relations = relations_index.get("total", 0)
    
    if total_relations == 0:
        return {
            "status": "success",
            "deleted": 0,
            "message": "⚠️  暂无关系数据"
        }
    
    # ⭐ 从配置文件加载泛化词（不再硬编码）
    generic_words = _load_generic_words_for_quality()
    
    # ⭐ 第一次调用：收集所有要删除的关系ID（存到临时文件）
    temp_file = f"{base_path}/storage/entities/relations/index/evolve_queue.json"
    
    if batch_index == 0 or not os.path.exists(temp_file):
        print("[INFO] 第一次调用，收集要删除的关系...")
        
        to_delete = []
        delete_reasons = defaultdict(int)
        
        # 扫描关系文件
        relations_dir = f"{base_path}/storage/entities/relations/by_type"
        
        for rel_type in RELATION_TYPES.keys():
            rel_file = f"{relations_dir}/{rel_type}.jsonl"
            if not os.path.exists(rel_file):
                continue
            
            with open(rel_file, 'r', encoding='utf-8') as f:
                for line in f:
                    if not line.strip():
                        continue
                    
                    try:
                        rel = json.loads(line)
                        
                        if rel.get("deleted", False):
                            continue
                        
                        relation_id = rel["relation_id"]
                        should_delete = False
                        reason = ""
                        
                        # 检查弱关系
                        if delete_weak and rel["strength"] < weak_threshold:
                            should_delete = True
                            reason = "weak"
                        
                        # 检查泛化词（⭐ 使用配置化的泛化词）
                        if delete_generic:
                            from_name = concepts.get(rel["from_id"], {}).get("name", "").lower()
                            to_name = concepts.get(rel["to_id"], {}).get("name", "").lower()
                            from_name_zh = concepts.get(rel["from_id"], {}).get("name_zh", "").lower()
                            to_name_zh = concepts.get(rel["to_id"], {}).get("name_zh", "").lower()
                            
                            for word in generic_words:
                                word_lower = word.lower()
                                if (word_lower in from_name or word_lower in to_name or
                                    word_lower in from_name_zh or word_lower in to_name_zh):
                                    should_delete = True
                                    reason = "generic"
                                    break
                        
                        # 检查从未激活
                        if delete_never_activated and rel.get("co_activation_count", 0) == 0:
                            if rel["strength"] < 0.5:
                                should_delete = True
                                reason = "never_activated"
                        
                        if should_delete:
                            to_delete.append({
                                "relation_id": relation_id,
                                "reason": reason
                            })
                            delete_reasons[reason] += 1
                    
                    except:
                        continue
        
        # 保存到临时文件
        os.makedirs(os.path.dirname(temp_file), exist_ok=True)
        with open(temp_file, 'w', encoding='utf-8') as f:
            json.dump({
                "to_delete": to_delete,
                "delete_reasons": dict(delete_reasons),
                "total": len(to_delete),
                "processed": 0
            }, f, ensure_ascii=False, indent=2)
        
        print(f"[INFO] 收集完成：需要删除{len(to_delete)}条关系（泛化词：{len(generic_words)}个）")
    
    # 读取临时文件
    with open(temp_file, 'r', encoding='utf-8') as f:
        evolve_data = json.load(f)
    
    to_delete = evolve_data["to_delete"]
    total_to_delete = len(to_delete)
    processed = evolve_data.get("processed", 0)
    
    if total_to_delete == 0:
        # 清理临时文件
        if os.path.exists(temp_file):
            os.remove(temp_file)
        
        return {
            "status": "success",
            "deleted": 0,
            "message": "✅ 无需删除任何关系"
        }
    
    # 计算总批次数
    total_batches = (total_to_delete + batch_size - 1) // batch_size
    
    # 自动模式：找到下一个未处理的批次
    if batch_index == -1:
        batch_index = processed // batch_size
    
    # 验证batch_index
    if batch_index < 0 or batch_index >= total_batches:
        return {
            "status": "error",
            "message": f"❌ batch_index超出范围（应该在0-{total_batches-1}之间）"
        }
    
    # 获取本批次的关系
    start_idx = batch_index * batch_size
    end_idx = min(start_idx + batch_size, total_to_delete)
    batch_to_delete = to_delete[start_idx:end_idx]
    
    print(f"[INFO] 批次{batch_index}/{total_batches-1}：删除关系{start_idx}-{end_idx-1}（共{len(batch_to_delete)}条）")
    
    # 执行删除
    deleted_count = 0
    for item in batch_to_delete:
        result = delete_relation(base_path, item["relation_id"])
        if result["status"] == "success":
            deleted_count += 1
    
    # 更新进度
    processed = end_idx
    evolve_data["processed"] = processed
    
    with open(temp_file, 'w', encoding='utf-8') as f:
        json.dump(evolve_data, f, ensure_ascii=False, indent=2)
    
    # 判断是否完成
    is_complete = (processed >= total_to_delete)
    next_batch = batch_index + 1 if not is_complete else None
    progress_pct = (processed / total_to_delete) * 100
    
    # 如果完成，清理临时文件
    if is_complete:
        if os.path.exists(temp_file):
            os.remove(temp_file)
    
    # 格式化输出
    lines = [f"✅ 批次{batch_index}完成（经济版）\n"]
    lines.append(f"进度：{processed}/{total_to_delete}条（{progress_pct:.1f}%）")
    lines.append(f"本批删除：{deleted_count}条")
    lines.append(f"泛化词过滤：{len(generic_words)}个词")
    
    if is_complete:
        delete_reasons = evolve_data.get("delete_reasons", {})
        lines.append("\n删除原因汇总：")
        reason_names = {
            "weak": "弱关系",
            "generic": "泛化词",
            "never_activated": "从未激活"
        }
        for reason, count in delete_reasons.items():
            lines.append(f"  {reason_names.get(reason, reason)}：{count}条")
        
        lines.append("\n🎉 所有批次已完成！")
        lines.append("💡 使用 nisb_relation_analyze 查看优化后的网络质量")
    else:
        lines.append(f"\n⏭️  下一批：batch_index={next_batch}")
        lines.append("💡 提示：使用 batch_index=-1 自动处理下一批")
    
    message = "\n".join(lines)
    
    return {
        "status": "success",
        "batch_index": batch_index,
        "batch_total": total_batches,
        "deleted_in_batch": deleted_count,
        "progress": f"{processed}/{total_to_delete} ({progress_pct:.1f}%)",
        "next_batch": next_batch,
        "is_complete": is_complete,
        "message": message
    }


# =====================================================================
# 导出
# =====================================================================

__all__ = [
    'nisb_relation_analyze',
    'nisb_relation_evolve'
]

