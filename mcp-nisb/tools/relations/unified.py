#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
NISB Relations统一查询接口 - Phase 3.0
同时查询Relations和Synapses，提供统一的数据视图

核心功能：
1. nisb_query_all：统一查询Relations+Synapses
2. nisb_create_unified：统一创建接口
3. nisb_migrate_to_hybrid：数据迁移工具

Phase 3.0.1 修复：
- 修复Hebbian学习Bug：显式激活和保存Synapses
"""

import sys
import os
import json
from pathlib import Path

sys.path.insert(0, '/srv')

from core.storage import get_user_base_path, ensure_user_directory, load_concepts_index
from core.relations import query_static_relations, create_relation_or_synapse
from core.synapses import query_synapses, Synapse  # 🔧 新增：导入Synapse类
from core.user_context import auto_user_context, get_user_ctx

def _update_synapse_in_file(filepath: str, updated_synapse: Synapse) -> bool:
    """
    🔧 新增函数：更新JSONL文件中的单个Synapse
    
    策略：
    1. 读取所有行到内存
    2. 找到匹配的synapse_id，替换为更新后的数据
    3. 写回文件
    
    参数：
        filepath: Synapse文件路径（如 synapses/by_type/associated_with.jsonl）
        updated_synapse: 更新后的Synapse对象
    
    返回：
        True: 更新成功
        False: 未找到匹配的Synapse
    """
    if not os.path.exists(filepath):
        return False
    
    # 读取所有Synapses
    all_synapses = []
    found = False
    
    with open(filepath, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            
            try:
                synapse_json = json.loads(line)
                
                # 如果是要更新的Synapse，替换为新数据
                if synapse_json.get('synapse_id') == updated_synapse.synapse_id:
                    all_synapses.append(updated_synapse.to_dict())
                    found = True
                else:
                    all_synapses.append(synapse_json)
            except json.JSONDecodeError:
                continue
    
    if not found:
        return False
    
    # 写回文件
    with open(filepath, 'w', encoding='utf-8') as f:
        for synapse_json in all_synapses:
            f.write(json.dumps(synapse_json, ensure_ascii=False) + '\n')
    
    return True

@auto_user_context
def nisb_query_all(args: dict) -> dict:
    """
    统一查询：同时查询Relations和Synapses
    
    Phase 3.0.1 修复：显式触发Synapses的Hebbian学习
    Phase 3.0.2 改进：
    - 支持模糊匹配（查询"媒介化"能匹配到"媒介"）
    - 查询失败时推荐相似概念
    
    参数:
        concept: string (必填，概念名称)
        min_strength: float (可选，最低强度，默认0.3)
        include_static: boolean (可选，是否包含静态Relations，默认True)
        include_dynamic: boolean (可选，是否包含动态Synapses，默认True)
        activate_synapses: boolean (可选，是否触发Synapses激活，默认True)
        user_id: string (自动注入)
    
    返回:
        {
          status,
          concept,
          relations: [...],
          synapses: [...],
          merged: [...],
          statistics: {...},
          message
        }
    """
  
    # 参数解析
    concept_name = args.get("concept")
    min_strength = float(args.get("min_strength", 0.3))
    include_static = args.get("include_static", True)
    include_dynamic = args.get("include_dynamic", True)
    activate_synapses = args.get("activate_synapses", True)
    
    if not concept_name:
        return {"status": "error", "message": "❌ concept不能为空"}
    
    # 查找概念ID
    concepts_index = load_concepts_index(base_path)
    concepts = concepts_index.get("concepts", {})
    
    # ⭐⭐⭐ Phase 3.0.2：支持模糊匹配 ⭐⭐⭐
    concept_id = None
    matched_concept_name = None
    similar_concepts = []  # 收集相似概念
    
    concept_lower = concept_name.lower()
    
    # 第一轮：精确匹配（优先）
    for cid, cdata in concepts.items():
        name = cdata.get("name", "")
        name_zh = cdata.get("name_zh", "")
        
        if name == concept_name or name_zh == concept_name:
            concept_id = cid
            matched_concept_name = name or name_zh
            break
    
    # 第二轮：模糊匹配（如果精确匹配失败）
    if not concept_id:
        for cid, cdata in concepts.items():
            name = cdata.get("name", "")
            name_zh = cdata.get("name_zh", "")
            name_lower = name.lower()
            
            # 部分匹配或包含关系
            if (concept_lower in name_lower or name_lower in concept_lower or
                concept_lower in name_zh or name_zh in concept_name):
                
                # 收集相似概念
                similar_concepts.append({
                    "id": cid,
                    "name": name or name_zh,
                    "match_type": "fuzzy"
                })
        
        # 如果找到相似概念，使用第一个
        if similar_concepts:
            concept_id = similar_concepts[0]["id"]
            matched_concept_name = similar_concepts[0]["name"]
            print(f"[INFO] 模糊匹配：'{concept_name}' → '{matched_concept_name}'", file=sys.stderr)
    
    # ⭐⭐⭐ Phase 3.0.2：查询失败时推荐相似概念 ⭐⭐⭐
    if not concept_id:
        error_msg = f"❌ 找不到概念：{concept_name}\n"
        
        if similar_concepts:
            error_msg += f"\n💡 您可能想查询：\n"
            for i, sc in enumerate(similar_concepts[:5], 1):
                error_msg += f"   {i}. {sc['name']}\n"
            error_msg += f"\n💬 建议：使用 nisb_query_all(concept='{similar_concepts[0]['name']}')"
        else:
            error_msg += f"\n💡 提示：\n"
            error_msg += f"   - 概念可能不存在，请使用 nisb_sense_quick_note 保存笔记时查看提取的概念\n"
            error_msg += f"   - 系统当前有 {len(concepts)} 个概念"
        
        return {
            "status": "error",
            "message": error_msg,
            "similar_concepts": [sc["name"] for sc in similar_concepts[:5]]
        }
    
    # 1. 查询静态Relations
    relations = []
    if include_static:
        relations = query_static_relations(base_path, concept_id, min_strength)
    
    # 2. 查询动态Synapses
    synapses = []
    if include_dynamic:
        # 🔧 修复：使用activate=False先查询，然后手动激活和保存
        synapses_raw = query_synapses(base_path, concept_id, min_strength, activate=False)
        
        # 🔧 修复：显式触发Hebbian学习
        if activate_synapses and synapses_raw:
            synapses_dir = Path(base_path) / "storage" / "entities" / "synapses" / "by_type"
            
            for synapse_dict in synapses_raw:
                try:
                    # 转换为Synapse对象
                    synapse = Synapse.from_dict(synapse_dict)
                    
                    # 触发激活（Hebbian学习）
                    synapse.activate(event_type="query", context=f"nisb_query_all({concept_name})")
                    
                    # 保存激活后的Synapse
                    synapse_file = synapses_dir / f"{synapse.type}.jsonl"
                    if synapse_file.exists():
                        success = _update_synapse_in_file(str(synapse_file), synapse)
                        if not success:
                            print(f"[WARN] 未找到Synapse: {synapse.synapse_id}", file=sys.stderr)
                    
                    # 使用激活后的数据
                    synapses.append(synapse.to_dict())
                    
                except Exception as e:
                    print(f"[ERROR] 激活Synapse失败: {e}", file=sys.stderr)
                    # 如果激活失败，使用原始数据
                    synapses.append(synapse_dict)
        else:
            # 如果不激活，直接使用原始数据
            synapses = synapses_raw
    
    # 3. 合并结果（标注来源）
    for rel in relations:
        rel["source_type"] = "relation"
    
    for syn in synapses:
        syn["source_type"] = "synapse"
    
    merged = relations + synapses
    merged.sort(key=lambda x: x.get("strength", 0), reverse=True)
    
    # 4. 统计信息
    total = len(merged)
    static_count = len(relations)
    dynamic_count = len(synapses)
    
    statistics = {
        "total": total,
        "static_count": static_count,
        "dynamic_count": dynamic_count,
        "static_percentage": (static_count / total * 100) if total > 0 else 0,
        "dynamic_percentage": (dynamic_count / total * 100) if total > 0 else 0
    }
    
    # 5. 格式化输出
    # ⭐ 如果是模糊匹配，显示匹配信息
    if matched_concept_name != concept_name:
        lines = [f"📊 「{concept_name}」→「{matched_concept_name}」的关系网络（模糊匹配）\n"]
    else:
        lines = [f"📊 「{concept_name}」的关系网络（统一视图）\n"]
    
    lines.append(f"总关系数：{total}条")
    lines.append(f"  ├─ 静态关系（Relations）：{static_count}条（{statistics['static_percentage']:.1f}%）")
    lines.append(f"  └─ 动态关系（Synapses）：{dynamic_count}条（{statistics['dynamic_percentage']:.1f}%）\n")
    
    if relations:
        lines.append("=== 静态关系（事实性）===")
        for i, rel in enumerate(relations[:5], 1):
            to_name = concepts[rel["to_id"]].get("name_zh") or concepts[rel["to_id"]].get("name")
            from core.relations import RELATION_TYPES
            type_name = RELATION_TYPES.get(rel["type"], {}).get("name", rel["type"])
            lines.append(f"  {i}. → {to_name}（{type_name}，{rel['strength']:.2f}）")
        lines.append("")
    
    if synapses:
        lines.append("=== 动态关系（思维路径）===")
        for i, syn in enumerate(synapses[:5], 1):
            to_name = concepts[syn["to_id"]].get("name_zh") or concepts[syn["to_id"]].get("name")
            from core.relations import RELATION_TYPES
            type_name = RELATION_TYPES.get(syn["type"], {}).get("name", syn["type"])
            lines.append(f"  {i}. → {to_name}（{type_name}，{syn['strength']:.2f}）")
            lines.append(f"      激活次数：{syn['activation_count']}")
        lines.append("")
    
    message = "\n".join(lines)
    
    return {
        "status": "success",
        "concept": concept_name,
        "matched_concept": matched_concept_name,  # ⭐ 新增字段
        "concept_id": concept_id,
        "relations": relations,
        "synapses": synapses,
        "merged": merged,
        "statistics": statistics,
        "message": message
    }

@auto_user_context
def nisb_create_unified(args: dict) -> dict:
    """
    统一创建接口：自动判断创建Relations或Synapses
    
    参数:
        from_concept: string (必填，源概念)
        to_concept: string (必填，目标概念)
        relation_type: string (必填，关系类型)
        strength: float (可选，强度，自动推断)
        source: string (可选，来源)
        evidence: string (可选，证据)
        user_preference: string (可选，"relation"或"synapse")
        user_id: string (自动注入)
    
    返回:
        {
          status,
          storage_type: "relation" 或 "synapse",
          relation_id/synapse_id,
          message
        }
    """
    
    # 参数解析
    from_concept = args.get("from_concept")
    to_concept = args.get("to_concept")
    relation_type = args.get("relation_type")
    strength = args.get("strength")
    source = args.get("source", "manual")
    evidence = args.get("evidence", "")
    user_preference = args.get("user_preference")
    
    if not all([from_concept, to_concept, relation_type]):
        return {"status": "error", "message": "❌ from_concept, to_concept, relation_type不能为空"}
    
    # 查找概念ID
    concepts_index = load_concepts_index(base_path)
    concepts = concepts_index.get("concepts", {})
    
    # ⭐⭐⭐ Phase 3.0 修复：更健壮的概念查找逻辑 ⭐⭐⭐
    from_id = None
    to_id = None
    
    # 转换为小写用于比较（支持忽略大小写）
    from_concept_lower = from_concept.lower() if from_concept else ""
    to_concept_lower = to_concept.lower() if to_concept else ""
    
    for cid, cdata in concepts.items():
        name = (cdata.get("name") or "").lower()
        name_zh = cdata.get("name_zh") or ""
        
        # 匹配from_concept（支持中英文、忽略大小写）
        if not from_id:
            if name and name == from_concept_lower:
                from_id = cid
            elif name_zh and name_zh == from_concept:
                from_id = cid
        
        # 匹配to_concept（支持中英文、忽略大小写）
        if not to_id:
            if name and name == to_concept_lower:
                to_id = cid
            elif name_zh and name_zh == to_concept:
                to_id = cid
        
        # 如果都找到了，提前退出
        if from_id and to_id:
            break
    
    # ⭐ 增强错误信息：显示可用概念
    if not from_id or not to_id:
        similar_concepts = []
        for cid, cdata in list(concepts.items())[:50]:
            name = cdata.get("name", "")
            name_zh = cdata.get("name_zh", "")
            display_name = name_zh if name_zh else name
            if display_name:
                similar_concepts.append(display_name)
        
        missing = []
        if not from_id:
            missing.append(from_concept)
        if not to_id:
            missing.append(to_concept)
        
        error_msg = f"❌ 找不到概念：{' 或 '.join(missing)}\n\n"
        error_msg += f"📋 系统中的部分概念（共{len(concepts)}个）：\n"
        error_msg += ", ".join(similar_concepts[:20])
        error_msg += "\n\n💡 提示：请使用完全匹配的概念名称（中英文均可）"
        
        return {"status": "error", "message": error_msg}
    
    # 调用统一创建接口
    result = create_relation_or_synapse(
        base_path=base_path,
        from_id=from_id,
        to_id=to_id,
        relation_type=relation_type,
        strength=float(strength) if strength else None,
        source=source,
        evidence=evidence,
        user_preference=user_preference
    )
    
    return result

@auto_user_context
def nisb_migrate_to_hybrid(args: dict) -> dict:
    """
    数据迁移工具：将现有Relations迁移为Relations+Synapses混合模式
    
    功能：
    1. 扫描现有的所有关系
    2. 根据分类标准自动分类
    3. 静态关系保留在Relations
    4. 动态关系迁移到Synapses
    
    参数:
        dry_run: boolean (可选，只分析不迁移，默认True)
        backup: boolean (可选，迁移前备份，默认True)
        user_id: string (自动注入)
    
    返回:
        {
          status,
          analysis: {
            total: 总数,
            static: 静态数,
            dynamic: 动态数,
            classifications: [...]
          },
          migrated: 迁移数量（如果dry_run=False）,
          message
        }
    """
    
    # 参数解析
    dry_run = args.get("dry_run", True)
    backup = args.get("backup", True)
    
    # 1. 加载所有现有关系
    from core.relations import load_all_relations
    
    existing_relations = load_all_relations(base_path)
    
    if len(existing_relations) == 0:
        return {
            "status": "success",
            "message": "⚠️  没有发现现有关系，无需迁移"
        }
    
    # 2. 批量分类
    concepts_index = load_concepts_index(base_path)
    concepts = concepts_index.get("concepts", {})
    
    # 添加概念名称
    for rel in existing_relations:
        rel["from_name"] = concepts.get(rel["from_id"], {}).get("name", "")
        rel["to_name"] = concepts.get(rel["to_id"], {}).get("name", "")
    
    from core.classifier import batch_classify_relations
    analysis_result = batch_classify_relations(existing_relations)
    
    # 3. 如果是dry_run，只返回分析结果
    if dry_run:
        lines = ["📊 数据迁移分析（干跑模式）\n"]
        lines.append(f"总关系数：{analysis_result['total']}条")
        lines.append(f"  ├─ 静态关系（保留在Relations）：{analysis_result['static']}条（{analysis_result['static_percentage']:.1f}%）")
        lines.append(f"  └─ 动态关系（迁移到Synapses）：{analysis_result['dynamic']}条（{analysis_result['dynamic_percentage']:.1f}%）\n")
        lines.append("示例分类：")
        
        for i, cls in enumerate(analysis_result['classifications'][:10], 1):
            lines.append(f"  {i}. {cls['from_name']} → {cls['to_name']}（{cls['type']}）")
            lines.append(f"      分类：{cls['storage_type']}，理由：{cls['reason']}")
        
        lines.append("\n💡 执行迁移请设置 dry_run=False")
        
        message = "\n".join(lines)
        
        return {
            "status": "success",
            "analysis": analysis_result,
            "migrated": 0,
            "message": message
        }
    
    # 4. 执行迁移（TODO：实现真实迁移逻辑）
    # 这里需要：
    # - 备份原数据
    # - 创建Synapses目录
    # - 将动态关系迁移到Synapses
    # - 更新索引
    
    return {
        "status": "success",
        "message": "⚠️  迁移功能开发中..."
    }


__all__ = ['nisb_query_all', 'nisb_create_unified', 'nisb_migrate_to_hybrid']

