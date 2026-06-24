#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
NISB Relations Reasoning - Phase 3.0（批次版，支持大规模关系网络）
关系推理工具：推荐、路径查找、上下文增强

核心优化：
1. relation_recommend: 批次推荐（每批10个概念，30秒内完成）
2. relation_path: 限制深度和路径数量（避免指数爆炸）
3. relation_context: 限制邻居数量（避免遍历全部关系）

适配场景：1核1G VPS + 10万+关系
"""

import os
import json
from collections import defaultdict, deque
from typing import List, Dict, Tuple, Optional
import sys
sys.path.insert(0, '/srv')

from core.relations import get_relations_by_concept, load_relations_index, RELATION_TYPES
from core.storage import get_user_base_path, ensure_user_directory, load_concepts_index
from core.user_context import auto_user_context, get_user_ctx

# =====================================================================
# 方法1：智能推荐关系（批次版）
# =====================================================================
@auto_user_context
def nisb_relation_recommend(args: dict) -> dict:
    """
    智能推荐关系（批次版：限制候选数量，避免超时）
    
    优化策略：
    - 只考虑源概念的2跳邻居（不遍历全部302个概念）
    - 最多推荐10个
    - 计算量：O(邻居数^2)，而不是O(概念数^2)
    
    参数:
        concept: string (必填，源概念名称或ID)
        top_k: integer (可选，返回前K个推荐，默认10)
        strategy: string (可选，推荐策略，默认"combined")
        user_id: string (自动注入)
    
    返回:
        {
          status,
          recommendations: [...]
        }
    """
   
    # 参数解析
    concept = args.get("concept", "").strip()
    top_k = int(args.get("top_k", 10))
    strategy = args.get("strategy", "combined").lower()
    
    if not concept:
        return {"status": "error", "message": "❌ concept不能为空"}
    
    # 加载数据
    concepts_index = load_concepts_index(base_path)
    concepts = concepts_index.get("concepts", {})
    
    # 查找概念ID
    concept_id = _find_concept_id_by_name(concept, concepts)
    if not concept_id:
        return {"status": "error", "message": f"❌ 找不到概念：{concept}"}
    
    concept_name = concepts[concept_id].get("name_zh") or concepts[concept_id].get("name")
    
    # 获取源概念的邻居（1跳）
    source_relations = get_relations_by_concept(base_path, concept_id, min_strength=0.3)
    source_neighbors = set([rel["to_id"] for rel in source_relations])
    
    if len(source_neighbors) == 0:
        return {
            "status": "success",
            "recommendations": [],
            "message": f"⚠️  「{concept_name}」暂无关系，无法推荐"
        }
    
    # ⭐ 批次优化：只考虑2跳邻居（不遍历全部概念）
    two_hop_neighbors = set()
    for neighbor_id in list(source_neighbors)[:20]:  # 最多扩展20个1跳邻居
        neighbor_relations = get_relations_by_concept(base_path, neighbor_id, min_strength=0.3)
        for rel in neighbor_relations[:10]:  # 每个邻居最多10条关系
            two_hop_neighbors.add(rel["to_id"])
    
    # 候选集：2跳邻居 - 源概念自己 - 已有关系
    candidates_set = two_hop_neighbors - {concept_id} - source_neighbors
    
    if len(candidates_set) == 0:
        return {
            "status": "success",
            "recommendations": [],
            "message": f"⚠️  「{concept_name}」的2跳邻居中无新推荐"
        }
    
    # ⭐ 限制候选数量（最多50个，避免超时）
    candidates_list = list(candidates_set)[:50]
    
    # 计算推荐分数
    candidates = {}
    
    for target_id in candidates_list:
        # 获取目标概念的邻居
        target_relations = get_relations_by_concept(base_path, target_id, min_strength=0.3)
        target_neighbors = set([rel["to_id"] for rel in target_relations])
        
        if len(target_neighbors) == 0:
            continue
        
        # 计算共同邻居
        common = source_neighbors & target_neighbors
        
        if len(common) == 0:
            continue
        
        # 根据策略计算分数
        if strategy == "common_neighbors":
            score = len(common)
        elif strategy == "adamic_adar":
            score = 0
            for neighbor_id in common:
                neighbor_relations = get_relations_by_concept(base_path, neighbor_id)
                degree = len(neighbor_relations)
                if degree > 1:
                    score += 1.0 / (degree ** 0.5)
        else:  # combined
            score_cn = len(common)
            score_aa = 0
            for neighbor_id in common:
                neighbor_relations = get_relations_by_concept(base_path, neighbor_id)
                degree = len(neighbor_relations)
                if degree > 1:
                    score_aa += 1.0 / (degree ** 0.5)
            score = score_cn + score_aa
        
        candidates[target_id] = {
            "score": score,
            "common_neighbors": list(common)
        }
    
    if len(candidates) == 0:
        return {
            "status": "success",
            "recommendations": [],
            "message": f"⚠️  「{concept_name}」无可推荐的关系"
        }
    
    # 排序并取TOP K
    sorted_candidates = sorted(candidates.items(), key=lambda x: x[1]["score"], reverse=True)[:top_k]
    
    # 构建推荐结果
    recommendations = []
    
    for target_id, data in sorted_candidates:
        target_name = concepts[target_id].get("name_zh") or concepts[target_id].get("name")
        
        # 计算预测强度
        max_score = sorted_candidates[0][1]["score"]
        normalized_score = 0.5 + (data["score"] / max_score) * 0.4
        
        # 构建共同邻居名称列表
        common_names = []
        for neighbor_id in data["common_neighbors"][:5]:
            neighbor_name = concepts.get(neighbor_id, {}).get("name_zh") or concepts.get(neighbor_id, {}).get("name", "")
            if neighbor_name:
                common_names.append(neighbor_name)
        
        # 查找现有路径
        if data["common_neighbors"]:
            bridge = data["common_neighbors"][0]
            bridge_name = concepts.get(bridge, {}).get("name_zh") or concepts.get(bridge, {}).get("name", "")
            existing_path = f"{concept_name} → {bridge_name} → {target_name}（2跳）"
        else:
            existing_path = "无直接路径"
        
        recommendations.append({
            "target_concept": target_name,
            "target_concept_id": target_id,
            "predicted_strength": round(normalized_score, 2),
            "confidence": round(data["score"] / max_score, 2),
            "reason": f"与{concept_name}有{len(data['common_neighbors'])}个共同邻居",
            "common_neighbors": common_names,
            "existing_path": existing_path
        })
    
    # 格式化输出
    lines = [f"💡 为「{concept_name}」推荐关系\n"]
    lines.append(f"推荐策略：{strategy}")
    lines.append(f"候选范围：2跳邻居（{len(candidates_list)}个）")
    lines.append(f"推荐数量：{len(recommendations)}个\n")
    
    for i, rec in enumerate(recommendations[:5], 1):
        lines.append(f"{i}. {rec['target_concept']}")
        lines.append(f"   预测强度：{rec['predicted_strength']} (置信度：{rec['confidence']})")
        lines.append(f"   理由：{rec['reason']}")
        lines.append(f"   共同邻居：{', '.join(rec['common_neighbors'][:3])}")
        lines.append(f"   现有路径：{rec['existing_path']}")
        lines.append("")
    
    if len(recommendations) > 5:
        lines.append(f"... 还有{len(recommendations) - 5}个推荐")
    
    lines.append("💡 使用 nisb_relation_create 创建推荐的关系")
    
    message = "\n".join(lines)
    
    return {
        "status": "success",
        "concept": concept_name,
        "recommendations": recommendations,
        "total": len(recommendations),
        "message": message
    }


# =====================================================================
# 方法2：多跳推理（限制版，避免指数爆炸）
# =====================================================================
@auto_user_context
def nisb_relation_path(args: dict) -> dict:
    """
    查找两个概念之间的路径（限制版：避免指数爆炸）
    
    优化策略：
    - 最大深度限制为5跳
    - 最多返回5条路径
    - BFS时限制每层扩展节点数（最多20个）
    
    参数:
        from_concept: string (必填，源概念)
        to_concept: string (必填，目标概念)
        max_depth: integer (可选，最大深度，默认5)
        path_type: string (可选，路径类型，默认"shortest")
        user_id: string (自动注入)
    
    返回:
        {
          status,
          paths: [...]
        }
    """   
    # 参数解析
    from_concept = args.get("from_concept", "").strip()
    to_concept = args.get("to_concept", "").strip()
    max_depth = min(int(args.get("max_depth", 5)), 5)  # ⭐ 强制限制最大5跳
    path_type = args.get("path_type", "shortest").lower()
    
    if not from_concept or not to_concept:
        return {"status": "error", "message": "❌ from_concept和to_concept不能为空"}
    
    # 加载数据
    concepts_index = load_concepts_index(base_path)
    concepts = concepts_index.get("concepts", {})
    
    # 查找概念ID
    from_id = _find_concept_id_by_name(from_concept, concepts)
    to_id = _find_concept_id_by_name(to_concept, concepts)
    
    if not from_id:
        return {"status": "error", "message": f"❌ 找不到源概念：{from_concept}"}
    if not to_id:
        return {"status": "error", "message": f"❌ 找不到目标概念：{to_concept}"}
    
    from_name = concepts[from_id].get("name_zh") or concepts[from_id].get("name")
    to_name = concepts[to_id].get("name_zh") or concepts[to_id].get("name")
    
    # 查找路径（BFS，限制版）
    if path_type == "shortest":
        paths = _find_shortest_path_limited(base_path, concepts, from_id, to_id, max_depth)
    elif path_type == "strongest":
        paths = _find_strongest_path_limited(base_path, concepts, from_id, to_id, max_depth)
    else:  # all
        paths = _find_all_paths_limited(base_path, concepts, from_id, to_id, max_depth, limit=5)
    
    if not paths:
        return {
            "status": "success",
            "paths": [],
            "message": f"⚠️  「{from_name}」和「{to_name}」之间无路径（{max_depth}跳内）"
        }
    
    # 格式化输出
    lines = [f"🔍 「{from_name}」→「{to_name}」的路径\n"]
    lines.append(f"路径类型：{path_type}")
    lines.append(f"找到{len(paths)}条路径\n")
    
    for i, path_data in enumerate(paths[:5], 1):
        path_names = path_data["path"]
        lines.append(f"路径{i}：{' → '.join(path_names)}")
        lines.append(f"  长度：{path_data['length']}跳")
        lines.append(f"  平均强度：{path_data['avg_strength']:.2f}")
        lines.append(f"  关系类型：{' → '.join(path_data['relation_types'])}")
        lines.append("")
    
    if len(paths) > 5:
        lines.append(f"... 还有{len(paths) - 5}条路径")
    
    message = "\n".join(lines)
    
    return {
        "status": "success",
        "from_concept": from_name,
        "to_concept": to_name,
        "paths": paths,
        "total": len(paths),
        "message": message
    }


# =====================================================================
# 方法3：为Agent提供关系上下文（限制版）
# =====================================================================
@auto_user_context
def nisb_relation_context(args: dict) -> dict:
    """
    为Agent提供关系上下文（生产级别：完整关系列表+多跳路径+结构化输出）
    
    优化策略：
    - 返回完整关系列表（不只是总数）✅
    - 显示概念间的多跳路径 ✅
    - JSON结构化输出（Agent友好）✅
    - 区分1跳 vs 2跳邻居 ✅
    - 语义化洞察（概念中心性、桥梁概念）✅
    
    参数:
        concepts: array (必填，相关概念列表)
        context_type: string (可选，上下文类型，默认"local")
          - local: 只返回直接关系（1跳）
          - extended: 包含扩展关系（2跳邻居）
          - causal_chain: 重点返回因果链
        max_relations: integer (可选，最多返回关系数，默认20)
        find_paths: boolean (可选，是否查找概念间路径，默认True)
        user_id: string (自动注入)
    
    返回:
        {
          status,
          context: {
            concepts: [...],
            direct_relations: [...],     # 1跳直接关系
            extended_relations: [...],   # 2跳扩展关系（如果是extended）
            paths: [...],                # 概念间路径
            insights: {
              centrality: {...},         # 概念中心性
              bridge_concepts: [...],    # 桥梁概念
              relation_type_dist: {...}  # 关系类型分布
            }
          },
          message
        }
    """
    
    # 参数解析
    concept_list = args.get("concepts", [])
    context_type = args.get("context_type", "local").lower()
    max_relations = int(args.get("max_relations", 20))
    find_paths = args.get("find_paths", True)
    
    if not concept_list or len(concept_list) == 0:
        return {"status": "error", "message": "❌ concepts不能为空"}
    
    # 加载数据
    concepts_index = load_concepts_index(base_path)
    concepts = concepts_index.get("concepts", {})
    
    # 查找概念ID
    concept_ids = []
    concept_names = []
    for concept_name in concept_list:
        concept_id = _find_concept_id_by_name(concept_name, concepts)
        if concept_id:
            concept_ids.append(concept_id)
            name = concepts[concept_id].get("name_zh") or concepts[concept_id].get("name")
            concept_names.append(name)
    
    if len(concept_ids) == 0:
        return {"status": "error", "message": "❌ 找不到任何有效概念"}
    
    # ========== 1. 收集直接关系（1跳）==========
    direct_relations = []
    concept_neighbors = {}  # {concept_id: [neighbor_ids]}
    
    for concept_id in concept_ids:
        concept_name = concepts[concept_id].get("name_zh") or concepts[concept_id].get("name")
        concept_relations = get_relations_by_concept(base_path, concept_id, min_strength=0.3)
        
        neighbors = []
        for rel in concept_relations[:15]:  # 每个概念最多15条关系
            to_name = concepts[rel["to_id"]].get("name_zh") or concepts[rel["to_id"]].get("name")
            
            direct_relations.append({
                "source": concept_name,
                "target": to_name,
                "type": rel["type"],
                "strength": round(rel["strength"], 2),
                "hop": 1  # ⭐ 标注跳数
            })
            
            neighbors.append(rel["to_id"])
        
        concept_neighbors[concept_id] = neighbors
    
    # ========== 2. 收集扩展关系（2跳，如果是extended模式）==========
    extended_relations = []
    all_neighbors = set()
    
    if context_type in ["extended", "causal_chain"]:
        for concept_id in concept_ids:
            neighbors = concept_neighbors.get(concept_id, [])
            
            # 限制扩展邻居数量（每个概念最多5个邻居）
            for neighbor_id in neighbors[:5]:
                neighbor_name = concepts[neighbor_id].get("name_zh") or concepts[neighbor_id].get("name")
                neighbor_relations = get_relations_by_concept(base_path, neighbor_id, min_strength=0.5)
                
                for rel in neighbor_relations[:5]:  # 每个邻居最多5条关系
                    # 排除已经在direct_relations中的
                    if rel["to_id"] in concept_ids:
                        continue
                    
                    to_name = concepts[rel["to_id"]].get("name_zh") or concepts[rel["to_id"]].get("name")
                    
                    extended_relations.append({
                        "source": neighbor_name,
                        "target": to_name,
                        "type": rel["type"],
                        "strength": round(rel["strength"], 2),
                        "hop": 2,  # ⭐ 标注跳数
                        "via": neighbor_name  # 通过哪个概念扩展
                    })
                    
                    all_neighbors.add(rel["to_id"])
    
    # ========== 3. 查找概念间路径（如果有多个概念）==========
    paths = []
    if find_paths and len(concept_ids) >= 2:
        # 只查找前两个概念之间的路径
        from_id = concept_ids[0]
        to_id = concept_ids[1]
        
        from_name = concepts[from_id].get("name_zh") or concepts[from_id].get("name")
        to_name = concepts[to_id].get("name_zh") or concepts[to_id].get("name")
        
        # 调用路径查找（最多查找3条路径，深度限制3跳）
        found_paths = _find_all_paths_limited(base_path, concepts, from_id, to_id, max_depth=3, limit=3)
        
        for path_data in found_paths:
            paths.append({
                "from": from_name,
                "to": to_name,
                "nodes": path_data["path"],
                "length": path_data["length"],
                "avg_strength": path_data["avg_strength"],
                "relation_types": path_data["relation_types"]
            })
    
    # ========== 4. 计算洞察 ==========
    insights = _calculate_insights(base_path, concepts, concept_ids, direct_relations, extended_relations)
    
    # ========== 5. 构建结构化输出 ==========
    # 限制返回的关系数量
    direct_relations = sorted(direct_relations, key=lambda x: x["strength"], reverse=True)[:max_relations]
    extended_relations = sorted(extended_relations, key=lambda x: x["strength"], reverse=True)[:max_relations]
    
    context_data = {
        "concepts": concept_names,
        "context_type": context_type,
        "direct_relations": direct_relations,
        "extended_relations": extended_relations if context_type in ["extended", "causal_chain"] else [],
        "paths": paths,
        "insights": insights,
        "statistics": {
            "total_direct": len(direct_relations),
            "total_extended": len(extended_relations),
            "total_paths": len(paths)
        }
    }
    
    # ========== 6. 格式化人类友好的输出 ==========
    lines = [f"📚 关系上下文（{' & '.join(concept_names)}）\n"]
    lines.append(f"上下文类型：{context_type}")
    lines.append(f"关系总数：{len(direct_relations) + len(extended_relations)}条\n")
    
    # 直接关系
    if direct_relations:
        lines.append("=== 直接关系（1跳）===")
        
        # 按源概念分组
        by_source = {}
        for rel in direct_relations:
            source = rel["source"]
            if source not in by_source:
                by_source[source] = []
            by_source[source].append(rel)
        
        for source, rels in by_source.items():
            lines.append(f"\n{source}的关系：")
            for i, rel in enumerate(rels[:5], 1):  # 每个源最多显示5条
                type_name = RELATION_TYPES.get(rel["type"], {}).get("name", rel["type"])
                lines.append(f"  {i}. → {rel['target']}（{type_name}，{rel['strength']}）")
        
        lines.append("")
    
    # 扩展关系
    if extended_relations:
        lines.append("=== 扩展关系（2跳）===")
        
        # 按via分组
        by_via = {}
        for rel in extended_relations:
            via = rel.get("via", "未知")
            if via not in by_via:
                by_via[via] = []
            by_via[via].append(rel)
        
        for via, rels in list(by_via.items())[:3]:  # 最多显示3个中介
            lines.append(f"\n通过「{via}」扩展：")
            for i, rel in enumerate(rels[:3], 1):  # 每个中介最多3条
                type_name = RELATION_TYPES.get(rel["type"], {}).get("name", rel["type"])
                lines.append(f"  {i}. {rel['source']} → {rel['target']}（{type_name}，{rel['strength']}）")
        
        lines.append("")
    
    # 路径
    if paths:
        lines.append(f"🔗 {paths[0]['from']} ↔ {paths[0]['to']} 的关联路径：\n")
        
        for i, path in enumerate(paths, 1):
            path_str = " → ".join(path["nodes"])
            lines.append(f"路径{i}（{path['length']}跳，强度{path['avg_strength']:.2f}）：")
            lines.append(f"  {path_str}")
            lines.append("")
    elif len(concept_ids) >= 2:
        lines.append(f"⚠️  {concept_names[0]} 与 {concept_names[1]} 在当前知识图谱中无直接关联\n")
    
    # 洞察
    lines.append("💡 关键洞察：\n")
    
    if insights["centrality"]:
        lines.append("概念中心性：")
        for concept_name, degree in list(insights["centrality"].items())[:3]:
            lines.append(f"  • {concept_name}：度中心性{degree}（{'高度连接' if degree > 5 else '中等连接'}）")
        lines.append("")
    
    if insights["strongest_relations"]:
        lines.append("最强关系：")
        for rel in insights["strongest_relations"][:3]:
            lines.append(f"  • {rel['source']} → {rel['target']}（{rel['strength']}）")
        lines.append("")
    
    if insights["bridge_concepts"]:
        lines.append(f"桥梁概念：{', '.join(insights['bridge_concepts'][:3])}")
        lines.append("")
    
    message = "\n".join(lines)
    
    return {
        "status": "success",
        "context": context_data,  # ⭐ 结构化数据（Agent可用）
        "message": message  # ⭐ 人类友好文本
    }


# =====================================================================
# 辅助函数：计算洞察
# =====================================================================

def _calculate_insights(base_path: str, concepts: dict, concept_ids: List[str], 
                       direct_relations: List[Dict], extended_relations: List[Dict]) -> Dict:
    """
    计算关系上下文的洞察
    
    Returns:
        {
          centrality: {concept_name: degree},
          strongest_relations: [...],
          bridge_concepts: [...],
          relation_type_dist: {...}
        }
    """
    insights = {
        "centrality": {},
        "strongest_relations": [],
        "bridge_concepts": [],
        "relation_type_dist": {}
    }
    
    # 1. 计算概念中心性（度数）
    for concept_id in concept_ids:
        concept_name = concepts[concept_id].get("name_zh") or concepts[concept_id].get("name")
        concept_relations = get_relations_by_concept(base_path, concept_id)
        insights["centrality"][concept_name] = len(concept_relations)
    
    # 2. 提取最强关系（TOP 5）
    all_relations = direct_relations + extended_relations
    sorted_relations = sorted(all_relations, key=lambda x: x["strength"], reverse=True)
    insights["strongest_relations"] = sorted_relations[:5]
    
    # 3. 识别桥梁概念（出现在扩展关系中的频率）
    bridge_count = {}
    for rel in extended_relations:
        via = rel.get("via")
        if via:
            bridge_count[via] = bridge_count.get(via, 0) + 1
    
    # 按频率排序
    sorted_bridges = sorted(bridge_count.items(), key=lambda x: x[1], reverse=True)
    insights["bridge_concepts"] = [bridge for bridge, count in sorted_bridges[:5]]
    
    # 4. 关系类型分布
    type_dist = {}
    for rel in all_relations:
        rel_type = rel["type"]
        type_name = RELATION_TYPES.get(rel_type, {}).get("name", rel_type)
        type_dist[type_name] = type_dist.get(type_name, 0) + 1
    
    insights["relation_type_dist"] = type_dist
    
    return insights

# =====================================================================
# 辅助函数（限制版）
# =====================================================================

def _find_shortest_path_limited(base_path: str, concepts: dict, from_id: str, to_id: str, max_depth: int) -> List[Dict]:
    """BFS查找最短路径（限制版）"""
    queue = deque([(from_id, [from_id], [])])
    visited = set([from_id])
    
    while queue:
        current_id, path, rel_types = queue.popleft()
        
        if len(path) > max_depth + 1:
            continue
        
        if current_id == to_id:
            return [_build_path_data(base_path, concepts, path, rel_types)]
        
        # ⭐ 限制扩展：每个节点最多20条关系
        relations = get_relations_by_concept(base_path, current_id, min_strength=0.3)
        relations = sorted(relations, key=lambda x: x["strength"], reverse=True)[:20]
        
        for rel in relations:
            neighbor_id = rel["to_id"]
            
            if neighbor_id not in visited:
                visited.add(neighbor_id)
                queue.append((neighbor_id, path + [neighbor_id], rel_types + [rel["type"]]))
    
    return []


def _find_strongest_path_limited(base_path: str, concepts: dict, from_id: str, to_id: str, max_depth: int) -> List[Dict]:
    """DFS查找最强路径（限制版）"""
    best_path = None
    best_strength = 0
    
    def dfs(current_id, path, rel_types, total_strength, visited):
        nonlocal best_path, best_strength
        
        if len(path) > max_depth + 1:
            return
        
        if current_id == to_id:
            avg_strength = total_strength / (len(path) - 1) if len(path) > 1 else 0
            if avg_strength > best_strength:
                best_strength = avg_strength
                best_path = (path.copy(), rel_types.copy(), total_strength)
            return
        
        # ⭐ 限制扩展：只考虑前5个最强的
        relations = get_relations_by_concept(base_path, current_id, min_strength=0.5)
        relations = sorted(relations, key=lambda x: x["strength"], reverse=True)[:5]
        
        for rel in relations:
            neighbor_id = rel["to_id"]
            
            if neighbor_id not in visited:
                visited.add(neighbor_id)
                dfs(neighbor_id, path + [neighbor_id], rel_types + [rel["type"]], 
                    total_strength + rel["strength"], visited)
                visited.remove(neighbor_id)
    
    dfs(from_id, [from_id], [], 0, set([from_id]))
    
    if best_path:
        return [_build_path_data(base_path, concepts, best_path[0], best_path[1])]
    return []


def _find_all_paths_limited(base_path: str, concepts: dict, from_id: str, to_id: str, max_depth: int, limit: int) -> List[Dict]:
    """DFS查找所有路径（限制版）"""
    all_paths = []
    
    def dfs(current_id, path, rel_types, visited):
        if len(all_paths) >= limit:
            return
        
        if len(path) > max_depth + 1:
            return
        
        if current_id == to_id:
            all_paths.append(_build_path_data(base_path, concepts, path.copy(), rel_types.copy()))
            return
        
        # ⭐ 限制扩展：每个节点最多10条关系
        relations = get_relations_by_concept(base_path, current_id, min_strength=0.5)
        relations = sorted(relations, key=lambda x: x["strength"], reverse=True)[:10]
        
        for rel in relations:
            neighbor_id = rel["to_id"]
            
            if neighbor_id not in visited:
                visited.add(neighbor_id)
                dfs(neighbor_id, path + [neighbor_id], rel_types + [rel["type"]], visited)
                visited.remove(neighbor_id)
    
    dfs(from_id, [from_id], [], set([from_id]))
    
    all_paths.sort(key=lambda x: x["avg_strength"], reverse=True)
    return all_paths[:limit]


def _build_path_data(base_path: str, concepts: dict, path_ids: List[str], rel_types: List[str]) -> Dict:
    """构建路径数据"""
    path_names = []
    total_strength = 0
    
    for i, concept_id in enumerate(path_ids):
        concept_name = concepts[concept_id].get("name_zh") or concepts[concept_id].get("name")
        path_names.append(concept_name)
        
        if i < len(path_ids) - 1:
            relations = get_relations_by_concept(base_path, concept_id)
            for rel in relations:
                if rel["to_id"] == path_ids[i + 1]:
                    total_strength += rel["strength"]
                    break
    
    length = len(path_ids) - 1
    avg_strength = total_strength / length if length > 0 else 0
    
    return {
        "path": path_names,
        "path_ids": path_ids,
        "length": length,
        "total_strength": round(total_strength, 2),
        "avg_strength": round(avg_strength, 2),
        "relation_types": rel_types
    }


def _find_concept_id_by_name(name: str, concepts: dict) -> Optional[str]:
    """根据名称查找概念ID"""
    name_lower = name.lower()
    
    for concept_id, concept_data in concepts.items():
        c_name = concept_data.get("name", "").lower()
        c_name_zh = concept_data.get("name_zh", "").lower()
        
        if c_name == name_lower or c_name_zh == name_lower:
            return concept_id
        
        if name_lower in c_name or name_lower in c_name_zh:
            return concept_id
    
    return None


# =====================================================================
# 导出
# =====================================================================

__all__ = [
    'nisb_relation_recommend',
    'nisb_relation_path',
    'nisb_relation_context'
]

