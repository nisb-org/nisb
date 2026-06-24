#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
NISB Relations Management Tools - Phase 3.0
关系手动管理工具：创建、查询、删除、统计
"""

import sys
sys.path.insert(0, '/srv')

from core.relations import (
    RELATION_TYPES,
    create_relation,
    get_relations_by_concept,
    delete_relation,
    load_relations_index
)
from core.storage import get_user_base_path, ensure_user_directory, load_concepts_index
from core.user_context import auto_user_context, get_user_ctx

@auto_user_context
def nisb_relation_create(args: dict) -> dict:
    """
    手动创建概念关系
    
    参数:
        from_concept: string (必填，源概念名称或ID)
        to_concept: string (必填，目标概念名称或ID)
        relation_type: string (必填，semantic/causal/temporal/contradictory)
        strength: float (可选，初始强度0.0-1.0，默认使用类型默认值)
        bidirectional: boolean (可选，是否双向，默认False)
        user_id: string (自动注入)
    
    返回:
        {status, relation_id, from_concept, to_concept, type, strength, message}
    
    示例:
        nisb_relation_create({
            "from_concept": "康德",
            "to_concept": "先验",
            "relation_type": "semantic",
            "strength": 0.8,
            "bidirectional": True
        })
    """
    
    # 参数解析
    from_concept = args.get("from_concept", "").strip()
    to_concept = args.get("to_concept", "").strip()
    relation_type = args.get("relation_type", "").strip().lower()
    strength = args.get("strength")
    bidirectional = args.get("bidirectional", False)
    
    # 参数验证
    if not from_concept or not to_concept:
        return {
            "status": "error",
            "message": "❌ from_concept和to_concept不能为空"
        }
    
    if relation_type not in RELATION_TYPES:
        return {
            "status": "error",
            "message": f"❌ 不支持的关系类型：{relation_type}\n支持的类型：{', '.join(RELATION_TYPES.keys())}"
        }
    
    if strength is not None:
        try:
            strength = float(strength)
            if not (0.0 <= strength <= 1.0):
                return {"status": "error", "message": "❌ strength必须在0.0-1.0之间"}
        except ValueError:
            return {"status": "error", "message": "❌ strength必须是数字"}
    
    # 查找概念ID（支持名称或ID）
    concepts_index = load_concepts_index(base_path)
    concepts = concepts_index.get("concepts", {})
    
    from_id = _find_concept_id(from_concept, concepts)
    to_id = _find_concept_id(to_concept, concepts)
    
    if not from_id:
        return {"status": "error", "message": f"❌ 找不到源概念：{from_concept}"}
    if not to_id:
        return {"status": "error", "message": f"❌ 找不到目标概念：{to_concept}"}
    
    # 创建关系
    result = create_relation(base_path, from_id, to_id, relation_type, strength, bidirectional)
    
    if result["status"] == "error":
        return result
    
    # 格式化输出
    from_name = concepts[from_id]["name_zh"] or concepts[from_id]["name"]
    to_name = concepts[to_id]["name_zh"] or concepts[to_id]["name"]
    
    rel_type_info = RELATION_TYPES[relation_type]
    
    message = f"✅ 已创建关系\n\n"
    message += f"源概念：{from_name}\n"
    message += f"目标概念：{to_name}\n"
    message += f"关系类型：{rel_type_info['name']} ({relation_type})\n"
    message += f"初始强度：{result['strength']:.2f}\n"
    
    if bidirectional:
        message += f"双向关系：是（同时创建了反向关系）\n"
    
    message += f"\n关系ID：{result['relation_id']}"
    
    return {
        "status": "success",
        "relation_id": result["relation_id"],
        "from_concept": from_name,
        "to_concept": to_name,
        "type": relation_type,
        "strength": result["strength"],
        "bidirectional": bidirectional,
        "message": message
    }

@auto_user_context
def nisb_relation_query(args: dict) -> dict:
    """
    查询概念的所有关系
    
    参数:
        concept: string (必填，概念名称或ID)
        relation_type: string (可选，过滤关系类型)
        min_strength: float (可选，最低强度阈值，默认0.0)
        limit: integer (可选，返回数量，默认20)
        user_id: string (自动注入)
    
    返回:
        {status, concept_name, relations: [...], total, message}
    
    示例:
        nisb_relation_query({
            "concept": "康德",
            "relation_type": "semantic",
            "min_strength": 0.5
        })
    """
    
    # 参数解析
    concept = args.get("concept", "").strip()
    relation_type = args.get("relation_type", "").strip().lower() if args.get("relation_type") else None
    min_strength = float(args.get("min_strength", 0.0))
    limit = int(args.get("limit", 20))
    
    if not concept:
        return {"status": "error", "message": "❌ concept不能为空"}
    
    if relation_type and relation_type not in RELATION_TYPES:
        return {"status": "error", "message": f"❌ 不支持的关系类型：{relation_type}"}
    
    # 查找概念ID
    concepts_index = load_concepts_index(base_path)
    concepts = concepts_index.get("concepts", {})
    
    concept_id = _find_concept_id(concept, concepts)
    if not concept_id:
        return {"status": "error", "message": f"❌ 找不到概念：{concept}"}
    
    concept_name = concepts[concept_id]["name_zh"] or concepts[concept_id]["name"]
    
    # 查询关系
    relations = get_relations_by_concept(base_path, concept_id, relation_type, min_strength)
    
    if not relations:
        filter_info = ""
        if relation_type:
            filter_info += f"（类型：{RELATION_TYPES[relation_type]['name']}）"
        if min_strength > 0:
            filter_info += f"（最低强度：{min_strength}）"
        
        return {
            "status": "success",
            "concept_name": concept_name,
            "relations": [],
            "total": 0,
            "message": f"📊 概念「{concept_name}」暂无关系{filter_info}"
        }
    
    # 限制返回数量
    relations = relations[:limit]
    
    # 格式化输出
    lines = [f"📊 概念「{concept_name}」的关系网络\n"]
    
    if relation_type:
        lines.append(f"关系类型：{RELATION_TYPES[relation_type]['name']}")
    lines.append(f"总关系数：{len(relations)}条\n")
    
    # 按关系类型分组
    by_type = {}
    for rel in relations:
        rel_type = rel["type"]
        if rel_type not in by_type:
            by_type[rel_type] = []
        by_type[rel_type].append(rel)
    
    for rel_type, rels in by_type.items():
        rel_type_info = RELATION_TYPES[rel_type]
        lines.append(f"\n【{rel_type_info['name']}】({len(rels)}条)")
        
        for i, rel in enumerate(rels[:10], 1):  # 每种类型最多显示10条
            to_concept = concepts.get(rel["to_id"], {})
            to_name = to_concept.get("name_zh") or to_concept.get("name", "未知")
            
            strength_bar = "█" * int(rel["strength"] * 10)
            lines.append(f"  {i}. → {to_name}")
            lines.append(f"      强度：{strength_bar} {rel['strength']:.2f}")
            
            if rel.get("co_activation_count", 0) > 0:
                lines.append(f"      共同激活：{rel['co_activation_count']}次")
        
        if len(rels) > 10:
            lines.append(f"  ... 还有{len(rels) - 10}条关系（使用limit参数查看更多）")
    
    message = "\n".join(lines)
    
    # 构建返回数据
    relations_data = []
    for rel in relations:
        to_concept = concepts.get(rel["to_id"], {})
        relations_data.append({
            "relation_id": rel["relation_id"],
            "to_concept_id": rel["to_id"],
            "to_concept_name": to_concept.get("name_zh") or to_concept.get("name"),
            "type": rel["type"],
            "strength": rel["strength"],
            "co_activation_count": rel.get("co_activation_count", 0),
            "last_activated": rel.get("last_activated")
        })
    
    return {
        "status": "success",
        "concept_name": concept_name,
        "concept_id": concept_id,
        "relations": relations_data,
        "total": len(relations),
        "by_type": {k: len(v) for k, v in by_type.items()},
        "message": message
    }

@auto_user_context
def nisb_relation_delete(args: dict) -> dict:
    """
    删除关系
    
    参数:
        relation_id: string (必填，关系ID)
        user_id: string (自动注入)
    
    返回:
        {status, relation_id, message}
    """
    
    relation_id = args.get("relation_id", "").strip()
    
    if not relation_id:
        return {"status": "error", "message": "❌ relation_id不能为空"}
    
    # 删除关系
    result = delete_relation(base_path, relation_id)
    
    if result["status"] == "error":
        return result
    
    return {
        "status": "success",
        "relation_id": relation_id,
        "message": f"✅ 关系已删除：{relation_id}"
    }

@auto_user_context
def nisb_relation_stats(args: dict) -> dict:
    """
    关系网络统计
    
    参数:
        user_id: string (自动注入)
    
    返回:
        {status, total, by_type, top_concepts, message}
    """
    
    # 加载索引
    index = load_relations_index(base_path)
    
    total = index.get("total", 0)
    by_type = index.get("by_type", {})
    adjacency = index.get("adjacency", {})
    
    if total == 0:
        return {
            "status": "success",
            "total": 0,
            "message": "📊 暂无关系数据\n\n💡 提示：\n- 使用 nisb_relation_create 手动创建关系\n- 使用 nisb_discover_relations 自动发现关系"
        }
    
    # 统计概念连接度（出度）
    concept_degrees = []
    concepts_index = load_concepts_index(base_path)
    concepts = concepts_index.get("concepts", {})
    
    for concept_id, rel_ids in adjacency.items():
        concept_name = concepts.get(concept_id, {}).get("name_zh") or concepts.get(concept_id, {}).get("name", "未知")
        concept_degrees.append((concept_name, len(rel_ids)))
    
    concept_degrees.sort(key=lambda x: x[1], reverse=True)
    top_concepts = concept_degrees[:10]
    
    # 格式化输出
    lines = ["📊 关系网络统计\n"]
    lines.append(f"总关系数：{total}条\n")
    
    lines.append("按类型分布：")
    for rel_type, count in by_type.items():
        rel_type_info = RELATION_TYPES[rel_type]
        percentage = (count / total * 100) if total > 0 else 0
        lines.append(f"  {rel_type_info['name']}：{count}条（{percentage:.1f}%）")
    
    lines.append(f"\n连接度TOP 10（出度）：")
    for i, (concept_name, degree) in enumerate(top_concepts, 1):
        lines.append(f"  {i}. {concept_name}：{degree}条关系")
    
    # 网络密度
    num_concepts = len(adjacency)
    if num_concepts > 1:
        max_edges = num_concepts * (num_concepts - 1)
        density = total / max_edges if max_edges > 0 else 0
        lines.append(f"\n网络密度：{density:.4f}（{total}/{max_edges}）")
    
    message = "\n".join(lines)
    
    return {
        "status": "success",
        "total": total,
        "by_type": by_type,
        "top_concepts": [{"concept": name, "degree": deg} for name, deg in top_concepts],
        "num_concepts": num_concepts,
        "message": message
    }


# =====================================================================
# 辅助函数
# =====================================================================

def _find_concept_id(name_or_id: str, concepts: dict) -> str:
    """
    查找概念ID（支持名称或ID）
    
    Args:
        name_or_id: 概念名称（中文/英文）或概念ID
        concepts: 概念索引字典
    
    Returns:
        概念ID，如果找不到返回None
    """
    # 如果是ID格式，直接返回
    if name_or_id.startswith("concept_") and name_or_id in concepts:
        return name_or_id
    
    # 按名称查找（支持中英文）
    name_lower = name_or_id.lower()
    
    for concept_id, concept_data in concepts.items():
        name = concept_data.get("name", "").lower()
        name_zh = concept_data.get("name_zh", "").lower()
        
        if name == name_lower or name_zh == name_lower:
            return concept_id
        
        # 部分匹配（如果精确匹配失败）
        if name_lower in name or name_lower in name_zh:
            return concept_id
    
    return None


# =====================================================================
# 导出
# =====================================================================

__all__ = [
    'nisb_relation_create',
    'nisb_relation_query',
    'nisb_relation_delete',
    'nisb_relation_stats'
]

