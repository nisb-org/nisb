#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
NISB Relations Discovery - Phase 3.0（Relations + Synapses 混合模式）
自动关系发现：从现有数据中挖掘概念关系

⭐ Phase 3.0 新特性：
- 自动判断关系类型（Relations vs Synapses）
- 静态事实关系 → Relations
- 动态思维路径 → Synapses
- 泛化词配置化管理

优化目标：
- 生成600-800条高质量关系
- 适配1核1G VPS

策略：
1. 共同出现分析（Co-occurrence）：概念在同一文档中出现 → semantic关系
2. 批注情绪分析：批注情绪 → 关系类型推断
3. 案例映射分析：多个案例同时映射 → semantic关系
4. 时序分析：概念出现顺序 → temporal关系
"""

import os
import json
from datetime import datetime
from collections import defaultdict, Counter
from typing import List, Dict, Tuple
import sys
sys.path.insert(0, '/srv')

from core.relations import create_relation, RELATION_TYPES
from core.storage import (
    get_user_base_path, 
    ensure_user_directory,
    load_concepts_index,
    load_jsonl
)
from core.user_context import auto_user_context, get_user_ctx


# =====================================================================
# 泛化词管理（配置化）
# =====================================================================

def _load_generic_words() -> List[str]:
    """
    从配置文件加载泛化词列表
    
    配置文件位置：/srv/config/generic_words.json
    
    Returns:
        ["今天", "笔记", "系统", ...]（所有泛化词的合并列表）
    """
    config_file = "/srv/config/generic_words.json"
    
    # 如果配置文件不存在，使用默认列表
    if not os.path.exists(config_file):
        print("[WARN] 泛化词配置文件不存在，使用默认列表")
        return [
            "今天", "笔记", "系统", "用户", "工具", "功能",
            "方法", "问题", "内容", "信息", "数据", "文件"
        ]
    
    try:
        with open(config_file, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        # 合并所有分类的泛化词
        all_words = []
        
        # 从categories中提取
        categories = config.get("categories", {})
        for category_name, category_data in categories.items():
            words = category_data.get("words", [])
            all_words.extend(words)
        
        # 添加自定义泛化词
        custom_words = config.get("custom", {}).get("words", [])
        all_words.extend(custom_words)
        
        # 转为小写并去重
        all_words = list(set([word.lower() for word in all_words]))
        
        print(f"[INFO] ✅ 加载泛化词配置：{len(all_words)}个词（来自{len(categories)}个分类 + 自定义）")
        print(f"[INFO] 配置文件路径：{config_file}")
        
        return all_words
    
    except Exception as e:
        print(f"[ERROR] 加载泛化词配置失败：{e}，使用默认列表")
        return [
            "今天", "笔记", "系统", "用户", "工具", "功能",
            "方法", "问题", "内容", "信息", "数据", "文件"
        ]


# =====================================================================
# nisb_discover_relations（单次发现，保留但不推荐）
# =====================================================================
@auto_user_context
def nisb_discover_relations(args: dict) -> dict:
    """
    自动发现概念关系（高质量版，单次处理，不推荐大规模使用）
    
    ⚠️ 注意：如果概念数>100，请使用 nisb_discover_relations_batch
    
    参数:
        min_cooccurrence: integer (可选，最低共同出现次数，默认10)
        min_confidence: float (可选，最低置信度，默认0.6)
        force: boolean (可选，是否覆盖已有关系，默认False)
        user_id: string (自动注入)
    
    返回:
        {
          status, 
          relations_created, 
          by_storage: {relation: 200, synapse: 136},  # ⭐ Phase 3.0 新增
          by_type: {semantic: 600, causal: 120, ...},
          by_strategy: {cooccurrence: 500, annotation: 150, ...},
          top_relations: [...],
          message
        }
    """   
    # 参数解析
    min_cooccurrence = int(args.get("min_cooccurrence", 10))
    min_confidence = float(args.get("min_confidence", 0.6))
    force = args.get("force", False)
    
    print(f"[INFO] 开始自动发现关系（Phase 3.0：混合模式）（用户：{user_id}）...")
    print(f"[INFO] 参数：min_cooccurrence={min_cooccurrence}, min_confidence={min_confidence}")
    
    # 加载概念索引
    concepts_index = load_concepts_index(base_path)
    concepts = concepts_index.get("concepts", {})
    
    if len(concepts) < 2:
        return {
            "status": "success",
            "relations_created": 0,
            "message": "❌ 概念数量不足（至少需要2个概念）"
        }
    
    # 加载泛化词列表（从配置文件）
    generic_words = _load_generic_words()
    
    # 策略1：共同出现分析
    print("[INFO] 执行策略1：共同出现分析（高质量版）...")
    cooccurrence_relations = _analyze_cooccurrence(base_path, concepts, min_cooccurrence, generic_words)
    print(f"[INFO] 策略1完成：发现{len(cooccurrence_relations)}个候选关系")
    
    # 策略2：批注情绪分析
    print("[INFO] 执行策略2：批注情绪分析...")
    annotation_relations = _analyze_annotations(base_path, concepts)
    print(f"[INFO] 策略2完成：发现{len(annotation_relations)}个候选关系")
    
    # 策略3：案例映射分析
    print("[INFO] 执行策略3：案例映射分析...")
    case_relations = _analyze_cases(base_path, concepts, min_cooccurrence)
    print(f"[INFO] 策略3完成：发现{len(case_relations)}个候选关系")
    
    # 策略4：时序分析
    print("[INFO] 执行策略4：时序分析...")
    temporal_relations = _analyze_temporal(base_path, concepts)
    print(f"[INFO] 策略4完成：发现{len(temporal_relations)}个候选关系")
    
    # 合并所有关系
    print("[INFO] 合并关系...")
    all_relations = _merge_relations(
        cooccurrence_relations, 
        annotation_relations,
        case_relations,
        temporal_relations,
        min_confidence
    )
    
    print(f"[INFO] 合并后：{len(all_relations)}个关系（置信度≥{min_confidence}）")
    
    # ⭐ Phase 3.0 修改：使用统一创建接口（自动分类）
    print("[INFO] [Phase 3.0] 开始创建关系（自动分类：Relations vs Synapses）...")
    
    from core.relations import create_relation_or_synapse
    
    created_count = 0
    skipped_count = 0
    by_type = defaultdict(int)
    by_strategy = defaultdict(int)
    by_storage = {"relation": 0, "synapse": 0}  # ⭐ 新增：统计存储类型
    
    for rel in all_relations:
        # 调用统一创建接口（自动判断Relations vs Synapses）
        result = create_relation_or_synapse(
            base_path=base_path,
            from_id=rel["from_id"],
            to_id=rel["to_id"],
            relation_type=rel["type"],
            strength=rel["strength"],
            source="batch_discovery",
            evidence=rel.get("evidence", ""),
            strategy=rel.get("strategy", "batch_discovery"),
            bidirectional=(rel["type"] == "semantic")
        )
        
        if result["status"] == "success":
            created_count += 1
            by_type[rel["type"]] += 1
            by_strategy[rel["strategy"]] += 1
            
            # ⭐ 统计存储类型
            storage_type = result.get("storage_type", "synapse")
            by_storage[storage_type] += 1
        else:
            skipped_count += 1
    
    print(f"[INFO] 关系创建完成：创建{created_count}个，跳过{skipped_count}个")
    print(f"[INFO] [Phase 3.0] 存储分布：Relations={by_storage['relation']}，Synapses={by_storage['synapse']}")
    
    # TOP关系
    all_relations.sort(key=lambda x: x["strength"], reverse=True)
    top_relations = []
    
    for rel in all_relations[:20]:
        from_name = concepts[rel["from_id"]]["name_zh"] or concepts[rel["from_id"]]["name"]
        to_name = concepts[rel["to_id"]]["name_zh"] or concepts[rel["to_id"]]["name"]
        
        top_relations.append({
            "from_concept": from_name,
            "to_concept": to_name,
            "type": rel["type"],
            "strength": rel["strength"],
            "strategy": rel["strategy"]
        })
    
    # 格式化输出
    lines = ["✅ 自动关系发现完成（Phase 3.0：混合模式）\n"]
    lines.append(f"创建关系：{created_count}条")
    lines.append(f"  ├─ 静态关系（Relations）：{by_storage['relation']}条")
    lines.append(f"  └─ 动态关系（Synapses）：{by_storage['synapse']}条")
    lines.append(f"跳过（已存在）：{skipped_count}条")
    lines.append(f"泛化词过滤：{len(generic_words)}个词\n")
    
    lines.append("按类型分布：")
    for rel_type, count in sorted(by_type.items(), key=lambda x: x[1], reverse=True):
        rel_type_info = RELATION_TYPES[rel_type]
        lines.append(f"  {rel_type_info['name']}：{count}条")
    
    lines.append("\n按策略分布：")
    strategy_names = {
        "cooccurrence": "共同出现",
        "annotation": "批注情绪",
        "case": "案例映射",
        "temporal": "时序分析"
    }
    for strategy, count in sorted(by_strategy.items(), key=lambda x: x[1], reverse=True):
        lines.append(f"  {strategy_names.get(strategy, strategy)}：{count}条")
    
    lines.append("\nTOP 10关系（按强度）：")
    for i, rel in enumerate(top_relations[:10], 1):
        rel_type_info = RELATION_TYPES[rel["type"]]
        lines.append(f"  {i}. {rel['from_concept']} → {rel['to_concept']}")
        lines.append(f"      类型：{rel_type_info['name']}，强度：{rel['strength']:.2f}")
    
    message = "\n".join(lines)
    
    return {
        "status": "success",
        "relations_created": created_count,
        "skipped": skipped_count,
        "by_storage": by_storage,  # ⭐ Phase 3.0 新增
        "by_type": dict(by_type),
        "by_strategy": dict(by_strategy),
        "top_relations": top_relations[:20],
        "message": message
    }


# =====================================================================
# ⭐ Phase 3.0 核心：nisb_discover_relations_batch（批次发现+自动分类）
# =====================================================================
@auto_user_context
def nisb_discover_relations_batch(args: dict) -> dict:
    """
    批次自动发现关系（Phase 3.0：Relations + Synapses 混合模式）
    
    ⭐ Phase 3.0 新特性：
    - 自动判断关系类型（Relations vs Synapses）
    - 静态事实关系 → Relations（无激活历史，轻量级）
    - 动态思维路径 → Synapses（Hebbian学习，完整记录）
    - 泛化词配置化管理（188个词）
    
    参数:
        batch_index: integer (可选，批次索引，-1=自动查找下一批，默认0)
        batch_size: integer (可选，每批处理概念数，默认30)
        min_cooccurrence: integer (可选，最低共同出现次数，默认10)
        min_confidence: float (可选，最低置信度，默认0.6)
        user_id: string (自动注入)
    
    返回:
        {
          status,
          batch_index,
          batch_total,
          relations_created,
          by_storage: {relation: 20, synapse: 15},  # ⭐ Phase 3.0 新增
          by_type: {...},
          progress,
          next_batch,
          is_complete,
          message
        }
    """
    
    batch_size = int(args.get("batch_size", 30))
    batch_index = int(args.get("batch_index", 0))
    min_cooccurrence = int(args.get("min_cooccurrence", 10))
    min_confidence = float(args.get("min_confidence", 0.6))
    
    concepts_index = load_concepts_index(base_path)
    concepts = concepts_index.get("concepts", {})
    
    if len(concepts) < 2:
        return {
            "status": "success",
            "relations_created": 0,
            "message": "❌ 概念数量不足（至少需要2个概念）"
        }
    
    # 加载泛化词列表
    generic_words = _load_generic_words()
    
    total_concepts = len(concepts)
    total_batches = (total_concepts + batch_size - 1) // batch_size
    
    # 自动查找下一批
    if batch_index == -1:
        batch_index = _find_next_batch(base_path, total_batches)
        if batch_index is None:
            return {
                "status": "success",
                "is_complete": True,
                "message": "🎉 所有批次已完成！使用 nisb_query_all 查看完整统计（混合视图）"
            }
    
    if batch_index < 0 or batch_index >= total_batches:
        return {
            "status": "error",
            "message": f"❌ batch_index超出范围（应该在0-{total_batches-1}之间）"
        }
    
    # 检查是否已处理
    if _is_batch_processed(base_path, batch_index):
        next_batch = _find_next_batch(base_path, total_batches)
        return {
            "status": "success",
            "batch_index": batch_index,
            "batch_total": total_batches,
            "already_processed": True,
            "next_batch": next_batch,
            "message": f"⚠️  批次{batch_index}已处理过\n\n下一批：batch_index={next_batch}"
        }
    
    # 切分批次
    concepts_list = list(concepts.items())
    start_idx = batch_index * batch_size
    end_idx = min(start_idx + batch_size, total_concepts)
    batch_concepts = dict(concepts_list[start_idx:end_idx])
    
    print(f"[INFO] [Phase 3.0] 批次{batch_index}/{total_batches-1}：处理概念{start_idx}-{end_idx-1}")
    
    # 运行发现策略
    cooccurrence_relations = _analyze_cooccurrence(base_path, batch_concepts, min_cooccurrence, generic_words)
    annotation_relations = _analyze_annotations(base_path, batch_concepts)
    case_relations = _analyze_cases(base_path, batch_concepts, min_cooccurrence)
    temporal_relations = _analyze_temporal(base_path, batch_concepts)
    
    all_relations = _merge_relations(
        cooccurrence_relations,
        annotation_relations,
        case_relations,
        temporal_relations,
        min_confidence
    )
    
    # ⭐ Phase 3.0 核心：使用统一创建接口（自动分类）
    from core.relations import create_relation_or_synapse
    
    created_count = 0
    by_type = defaultdict(int)
    by_storage = {"relation": 0, "synapse": 0}  # ⭐ 新增：统计存储类型
    
    for rel in all_relations:
        # 判断来源（用于分类）
        source = "batch_discovery"
        evidence = rel.get("evidence", "")
        
        # ⭐ 调用统一创建接口（自动判断Relations vs Synapses）
        result = create_relation_or_synapse(
            base_path=base_path,
            from_id=rel["from_id"],
            to_id=rel["to_id"],
            relation_type=rel["type"],
            strength=rel["strength"],
            source=source,
            evidence=evidence,
            strategy=rel.get("strategy", "batch_discovery"),
            bidirectional=(rel["type"] == "semantic")
        )
        
        if result["status"] == "success":
            created_count += 1
            by_type[rel["type"]] += 1
            
            # ⭐ 统计存储类型
            storage_type = result.get("storage_type", "synapse")
            by_storage[storage_type] += 1
    
    # 标记批次已处理
    _mark_batch_processed(base_path, batch_index)
    
    # 计算进度
    processed_batches = _count_processed_batches(base_path, total_batches)
    progress_pct = (processed_batches / total_batches) * 100
    
    is_complete = (processed_batches == total_batches)
    next_batch = _find_next_batch(base_path, total_batches) if not is_complete else None
    
    # ⭐ Phase 3.0 修改：输出分类信息
    lines = [f"✅ 批次{batch_index}完成（Phase 3.0：混合模式）\n"]
    lines.append(f"进度：{processed_batches}/{total_batches}批（{progress_pct:.1f}%）")
    lines.append(f"本批处理：{len(batch_concepts)}个概念")
    lines.append(f"创建关系：{created_count}条")
    lines.append(f"  ├─ 静态关系（Relations）：{by_storage['relation']}条")
    lines.append(f"  └─ 动态关系（Synapses）：{by_storage['synapse']}条")
    lines.append(f"泛化词过滤：{len(generic_words)}个词")
    
    if by_type:
        lines.append("\n按类型分布：")
        for rel_type, count in sorted(by_type.items(), key=lambda x: x[1], reverse=True):
            rel_type_info = RELATION_TYPES[rel_type]
            lines.append(f"  {rel_type_info['name']}：{count}条")
    
    if is_complete:
        lines.append("\n🎉 所有批次已完成！")
        lines.append("使用 nisb_query_all 查看完整统计（混合视图）")
    else:
        lines.append(f"\n⏭️  下一批：batch_index={next_batch}")
    
    message = "\n".join(lines)
    
    return {
        "status": "success",
        "batch_index": batch_index,
        "batch_total": total_batches,
        "concepts_processed": len(batch_concepts),
        "relations_created": created_count,
        "by_storage": by_storage,  # ⭐ Phase 3.0 新增
        "by_type": dict(by_type),
        "progress": f"{processed_batches}/{total_batches} ({progress_pct:.1f}%)",
        "next_batch": next_batch,
        "is_complete": is_complete,
        "message": message
    }


# =====================================================================
# 策略1：共同出现分析（高质量版，使用配置化的泛化词）
# =====================================================================

def _analyze_cooccurrence(base_path: str, concepts: dict, min_count: int, generic_words: List[str]) -> List[Dict]:
    """
    分析概念共同出现（高质量版：严格过滤）
    
    Args:
        generic_words: 泛化词列表（从配置文件加载）
    """
    # 统计共同出现次数
    cooccurrence = defaultdict(int)
    concept_count = defaultdict(int)
    
    # 扫描笔记
    notes_dir = f"{base_path}/storage/raw/quick_notes"
    if os.path.exists(notes_dir):
        for filename in os.listdir(notes_dir):
            if not filename.endswith('.jsonl'):
                continue
            
            notes = load_jsonl(f"{notes_dir}/{filename}")
            for note in notes:
                note_concepts = _extract_concepts_from_text(note.get("content", ""), concepts)
                
                for c in note_concepts:
                    concept_count[c] += 1
                
                for i, c1 in enumerate(note_concepts):
                    for c2 in note_concepts[i+1:]:
                        if c1 < c2:
                            cooccurrence[(c1, c2)] += 1
                        else:
                            cooccurrence[(c2, c1)] += 1
    
    # 扫描对话
    daily_dir = f"{base_path}/storage/raw/daily"
    if os.path.exists(daily_dir):
        for date_folder in os.listdir(daily_dir):
            date_path = f"{daily_dir}/{date_folder}"
            if not os.path.isdir(date_path):
                continue
            
            for filename in os.listdir(date_path):
                if not filename.endswith('.json'):
                    continue
                
                try:
                    with open(f"{date_path}/{filename}", 'r', encoding='utf-8') as f:
                        record = json.load(f)
                    
                    conversation = record.get("conversation", [])
                    full_text = " ".join([msg.get("content", "") for msg in conversation])
                    
                    record_concepts = _extract_concepts_from_text(full_text, concepts)
                    
                    for c in record_concepts:
                        concept_count[c] += 1
                    
                    for i, c1 in enumerate(record_concepts):
                        for c2 in record_concepts[i+1:]:
                            if c1 < c2:
                                cooccurrence[(c1, c2)] += 1
                            else:
                                cooccurrence[(c2, c1)] += 1
                except:
                    continue
    
    # 高质量过滤
    relations = []
    
    for (c1, c2), count in cooccurrence.items():
        if count < min_count:
            continue
        
        c1_count = concept_count[c1]
        c2_count = concept_count[c2]
        
        if c1_count == 0 or c2_count == 0:
            continue
        
        max_possible = min(c1_count, c2_count)
        strength = 0.3 + (count / max_possible) * 0.6
        strength = min(0.9, strength)
        
        if strength < 0.4:
            continue
        
        if c1_count > 50 and c2_count > 50:
            if count < 20:
                continue
        
        # 排除泛化词
        c1_name = concepts[c1].get("name", "").lower()
        c2_name = concepts[c2].get("name", "").lower()
        c1_name_zh = concepts[c1].get("name_zh", "").lower()
        c2_name_zh = concepts[c2].get("name_zh", "").lower()
        
        skip = False
        for word in generic_words:
            if (word in c1_name or word in c1_name_zh or 
                word in c2_name or word in c2_name_zh):
                skip = True
                break
        
        if skip:
            continue
        
        relations.append({
            "from_id": c1,
            "to_id": c2,
            "type": "semantic",
            "strength": strength,
            "strategy": "cooccurrence",
            "evidence": f"共同出现{count}次，强度{strength:.2f}"
        })
    
    return relations


# =====================================================================
# 其他策略（保持不变）
# =====================================================================

def _analyze_annotations(base_path: str, concepts: dict) -> List[Dict]:
    """批注情绪分析"""
    relations = []
    
    annotations_dir = f"{base_path}/storage/annotations/by_date"
    if not os.path.exists(annotations_dir):
        return relations
    
    for year_month in os.listdir(annotations_dir):
        anno_file = f"{annotations_dir}/{year_month}/annotations.jsonl"
        if not os.path.exists(anno_file):
            continue
        
        with open(anno_file, 'r', encoding='utf-8') as f:
            for line in f:
                if not line.strip():
                    continue
                
                try:
                    anno = json.loads(line)
                    
                    if anno.get("deleted", False):
                        continue
                    
                    anno_concepts = anno.get("concepts", [])
                    if len(anno_concepts) < 2:
                        continue
                    
                    mood = anno.get("mood", "中性")
                    
                    if mood in ["顿悟", "新洞察", "验证"]:
                        relation_type = "semantic"
                        strength = 0.7
                    elif mood in ["质疑", "困惑"]:
                        relation_type = "contradictory"
                        strength = 0.5
                    else:
                        relation_type = "semantic"
                        strength = 0.5
                    
                    concept_ids = []
                    for concept_name in anno_concepts:
                        concept_id = _find_concept_id_by_name(concept_name, concepts)
                        if concept_id:
                            concept_ids.append(concept_id)
                    
                    for i, c1 in enumerate(concept_ids):
                        for c2 in concept_ids[i+1:]:
                            relations.append({
                                "from_id": c1 if c1 < c2 else c2,
                                "to_id": c2 if c1 < c2 else c1,
                                "type": relation_type,
                                "strength": strength,
                                "strategy": "annotation",
                                "evidence": f"批注情绪：{mood}"
                            })
                
                except:
                    continue
    
    return relations


def _analyze_cases(base_path: str, concepts: dict, min_count: int) -> List[Dict]:
    """案例映射分析"""
    relations = []
    concept_pairs = defaultdict(int)
    
    cases_dir = f"{base_path}/storage/cases/by_date"
    if not os.path.exists(cases_dir):
        return relations
    
    for year_month in os.listdir(cases_dir):
        month_dir = f"{cases_dir}/{year_month}"
        if not os.path.isdir(month_dir):
            continue
        
        for filename in os.listdir(month_dir):
            if not filename.startswith("cases_") or not filename.endswith(".jsonl"):
                continue
            
            cases = load_jsonl(f"{month_dir}/{filename}")
            
            for case in cases:
                mapped_concepts = case.get("mapped_concepts", [])
                
                case_concept_ids = []
                for mc in mapped_concepts:
                    if isinstance(mc, dict):
                        concept_name = mc.get("concept_name", "")
                    else:
                        concept_name = str(mc)
                    
                    concept_id = _find_concept_id_by_name(concept_name, concepts)
                    if concept_id:
                        case_concept_ids.append(concept_id)
                
                for i, c1 in enumerate(case_concept_ids):
                    for c2 in case_concept_ids[i+1:]:
                        if c1 < c2:
                            concept_pairs[(c1, c2)] += 1
                        else:
                            concept_pairs[(c2, c1)] += 1
    
    for (c1, c2), count in concept_pairs.items():
        if count < min_count:
            continue
        
        strength = 0.5 + (count / 10) * 0.4
        strength = min(0.9, strength)
        
        relations.append({
            "from_id": c1,
            "to_id": c2,
            "type": "semantic",
            "strength": strength,
            "strategy": "case",
            "evidence": f"{count}个案例同时映射"
        })
    
    return relations


def _analyze_temporal(base_path: str, concepts: dict) -> List[Dict]:
    """时序分析"""
    relations = []
    temporal_pairs = defaultdict(int)
    
    notes_dir = f"{base_path}/storage/raw/quick_notes"
    if not os.path.exists(notes_dir):
        return relations
    
    all_notes = []
    for filename in os.listdir(notes_dir):
        if not filename.endswith('.jsonl'):
            continue
        
        notes = load_jsonl(f"{notes_dir}/{filename}")
        all_notes.extend(notes)
    
    all_notes.sort(key=lambda x: x.get("timestamp", ""))
    
    concept_last_seen = {}
    
    for idx, note in enumerate(all_notes):
        note_concepts = _extract_concepts_from_text(note.get("content", ""), concepts)
        
        for concept_id in note_concepts:
            if concept_id in concept_last_seen:
                last_idx = concept_last_seen[concept_id]
                
                for other_concept_id in note_concepts:
                    if other_concept_id == concept_id:
                        continue
                    
                    if other_concept_id not in concept_last_seen or concept_last_seen[other_concept_id] > last_idx:
                        temporal_pairs[(concept_id, other_concept_id)] += 1
            
            concept_last_seen[concept_id] = idx
    
    for (c1, c2), count in temporal_pairs.items():
        if count < 3:
            continue
        
        strength = 0.3 + (count / 10) * 0.3
        strength = min(0.6, strength)
        
        relations.append({
            "from_id": c1,
            "to_id": c2,
            "type": "temporal",
            "strength": strength,
            "strategy": "temporal",
            "evidence": f"{c1}在{count}次笔记中先于{c2}出现"
        })
    
    return relations


# =====================================================================
# 辅助函数
# =====================================================================

def _merge_relations(cooccurrence_rels: List[Dict], 
                    annotation_rels: List[Dict],
                    case_rels: List[Dict],
                    temporal_rels: List[Dict],
                    min_confidence: float) -> List[Dict]:
    """合并所有策略的关系"""
    merged = {}
    
    all_relations = cooccurrence_rels + annotation_rels + case_rels + temporal_rels
    
    for rel in all_relations:
        if rel["strength"] < min_confidence:
            continue
        
        key = (rel["from_id"], rel["to_id"], rel["type"])
        
        if key not in merged:
            merged[key] = rel
        else:
            if rel["strength"] > merged[key]["strength"]:
                merged[key] = rel
    
    return list(merged.values())


def _extract_concepts_from_text(text: str, concepts: dict) -> List[str]:
    """从文本中提取概念ID"""
    text_lower = text.lower()
    found_concepts = []
    
    for concept_id, concept_data in concepts.items():
        name = concept_data.get("name", "").lower()
        name_zh = concept_data.get("name_zh", "").lower()
        
        if len(name) >= 2 and name in text_lower:
            found_concepts.append(concept_id)
        elif len(name_zh) >= 2 and name_zh in text_lower:
            found_concepts.append(concept_id)
    
    return list(set(found_concepts))


def _find_concept_id_by_name(name: str, concepts: dict) -> str:
    """根据名称查找概念ID"""
    name_lower = name.lower()
    
    for concept_id, concept_data in concepts.items():
        c_name = concept_data.get("name", "").lower()
        c_name_zh = concept_data.get("name_zh", "").lower()
        
        if c_name == name_lower or c_name_zh == name_lower:
            return concept_id
    
    return None


# 批次管理辅助函数

def _is_batch_processed(base_path: str, batch_index: int) -> bool:
    batch_file = f"{base_path}/storage/entities/relations/index/batches_processed.json"
    if not os.path.exists(batch_file):
        return False
    try:
        with open(batch_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return batch_index in data.get("processed", [])
    except:
        return False


def _mark_batch_processed(base_path: str, batch_index: int):
    batch_file = f"{base_path}/storage/entities/relations/index/batches_processed.json"
    os.makedirs(os.path.dirname(batch_file), exist_ok=True)
    
    if os.path.exists(batch_file):
        with open(batch_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
    else:
        data = {"processed": [], "last_updated": None, "mode": "phase3-hybrid"}  # ⭐ Phase 3.0
    
    if batch_index not in data["processed"]:
        data["processed"].append(batch_index)
        data["processed"].sort()
    
    data["last_updated"] = datetime.now().isoformat()
    
    with open(batch_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _count_processed_batches(base_path: str, total_batches: int) -> int:
    batch_file = f"{base_path}/storage/entities/relations/index/batches_processed.json"
    if not os.path.exists(batch_file):
        return 0
    try:
        with open(batch_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return len(data.get("processed", []))
    except:
        return 0


def _find_next_batch(base_path: str, total_batches: int) -> int:
    batch_file = f"{base_path}/storage/entities/relations/index/batches_processed.json"
    if not os.path.exists(batch_file):
        return 0
    try:
        with open(batch_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
            processed = set(data.get("processed", []))
        for i in range(total_batches):
            if i not in processed:
                return i
        return None
    except:
        return 0


__all__ = ['nisb_discover_relations', 'nisb_discover_relations_batch']

