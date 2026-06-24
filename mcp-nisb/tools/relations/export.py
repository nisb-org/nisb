#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
NISB Relations Export - Phase 3.0
导出关系网络（供前端可视化）

支持格式：
1. D3.js force graph
2. Cytoscape.js
3. 原始JSON
"""

import json
import sys
sys.path.insert(0, '/srv')

from core.relations import load_relations_index, get_relations_by_concept, RELATION_TYPES
from core.storage import get_user_base_path, ensure_user_directory, load_concepts_index
from core.user_context import auto_user_context, get_user_ctx

@auto_user_context
def nisb_export_relation_network(args: dict) -> dict:
    """
    导出关系网络（供前端可视化）
    
    参数:
        concept: string (可选，中心概念，导出以它为中心的子网络)
        depth: integer (可选，深度，默认2)
        format: string (可选，d3/cytoscape/raw，默认d3)
        min_strength: float (可选，最低强度阈值，默认0.3)
        user_id: string (自动注入)
    
    返回:
        {
          status,
          format,
          network: {
            nodes: [
              {id: "c1", name: "康德", activation: 0.8, status: "hot", group: 1},
              ...
            ],
            edges: [
              {source: "c1", target: "c2", type: "semantic", strength: 0.85, color: "#3498db"},
              ...
            ]
          },
          stats: {total_nodes, total_edges, avg_degree},
          message
        }
    
    示例:
        # 导出完整网络
        nisb_export_relation_network({})
        
        # 导出康德的2跳网络
        nisb_export_relation_network({
            "concept": "康德",
            "depth": 2
        })
    """
    
    # 参数解析
    center_concept = args.get("concept", "").strip()
    depth = int(args.get("depth", 2))
    export_format = args.get("format", "d3").lower()
    min_strength = float(args.get("min_strength", 0.3))
    
    if export_format not in ["d3", "cytoscape", "raw"]:
        return {"status": "error", "message": f"❌ 不支持的格式：{export_format}"}
    
    # 加载数据
    concepts_index = load_concepts_index(base_path)
    concepts = concepts_index.get("concepts", {})
    relations_index = load_relations_index(base_path)
    
    if relations_index.get("total", 0) == 0:
        return {
            "status": "success",
            "network": {"nodes": [], "edges": []},
            "message": "⚠️ 暂无关系数据"
        }
    
    # 如果指定了中心概念，导出子网络
    if center_concept:
        center_id = _find_concept_id_by_name(center_concept, concepts)
        if not center_id:
            return {"status": "error", "message": f"❌ 找不到概念：{center_concept}"}
        
        nodes, edges = _export_subnetwork(base_path, concepts, center_id, depth, min_strength)
    else:
        # 导出完整网络
        nodes, edges = _export_full_network(base_path, concepts, relations_index, min_strength)
    
    # 格式化输出
    if export_format == "d3":
        network = _format_d3(nodes, edges)
    elif export_format == "cytoscape":
        network = _format_cytoscape(nodes, edges)
    else:  # raw
        network = {"nodes": nodes, "edges": edges}
    
    # 统计信息
    stats = {
        "total_nodes": len(nodes),
        "total_edges": len(edges),
        "avg_degree": (len(edges) * 2 / len(nodes)) if len(nodes) > 0 else 0,
        "density": (len(edges) / (len(nodes) * (len(nodes) - 1))) if len(nodes) > 1 else 0
    }
    
    # 格式化消息
    lines = ["✅ 关系网络导出完成\n"]
    
    if center_concept:
        lines.append(f"中心概念：{center_concept}")
        lines.append(f"深度：{depth}跳")
    else:
        lines.append("导出类型：完整网络")
    
    lines.append(f"格式：{export_format}")
    lines.append(f"\n节点数：{stats['total_nodes']}")
    lines.append(f"边数：{stats['total_edges']}")
    lines.append(f"平均度：{stats['avg_degree']:.2f}")
    lines.append(f"网络密度：{stats['density']:.4f}")
    
    lines.append("\n💡 使用方式：")
    if export_format == "d3":
        lines.append("  - 复制network字段到D3.js force graph")
        lines.append("  - 示例：https://observablehq.com/@d3/force-directed-graph")
    elif export_format == "cytoscape":
        lines.append("  - 复制network字段到Cytoscape.js")
        lines.append("  - 示例：https://js.cytoscape.org/")
    
    message = "\n".join(lines)
    
    return {
        "status": "success",
        "format": export_format,
        "network": network,
        "stats": stats,
        "center_concept": center_concept if center_concept else None,
        "depth": depth if center_concept else None,
        "message": message
    }


# =====================================================================
# 子网络导出（以某概念为中心）
# =====================================================================

def _export_subnetwork(base_path: str, concepts: dict, center_id: str, 
                      depth: int, min_strength: float) -> tuple:
    """
    导出以center_id为中心的depth跳子网络
    
    Returns:
        (nodes, edges)
    """
    visited_nodes = set()
    all_edges = []
    
    # BFS遍历depth跳
    current_level = {center_id}
    visited_nodes.add(center_id)
    
    for d in range(depth):
        next_level = set()
        
        for concept_id in current_level:
            # 获取该概念的所有关系
            relations = get_relations_by_concept(base_path, concept_id, min_strength=min_strength)
            
            for rel in relations:
                target_id = rel["to_id"]
                
                # 添加边
                all_edges.append({
                    "source": concept_id,
                    "target": target_id,
                    "type": rel["type"],
                    "strength": rel["strength"],
                    "relation_id": rel["relation_id"]
                })
                
                # 如果目标节点未访问，加入下一层
                if target_id not in visited_nodes:
                    visited_nodes.add(target_id)
                    next_level.add(target_id)
        
        current_level = next_level
        
        if not current_level:
            break  # 没有更多节点
    
    # 构建节点列表
    nodes = []
    for concept_id in visited_nodes:
        if concept_id not in concepts:
            continue
        
        concept_data = concepts[concept_id]
        nodes.append({
            "id": concept_id,
            "name": concept_data.get("name_zh") or concept_data.get("name"),
            "activation": concept_data.get("activation_weight", 0.5),
            "status": concept_data.get("status", "warm"),
            "discussion_count": concept_data.get("discussion_count", 0),
            "is_center": (concept_id == center_id)
        })
    
    return nodes, all_edges


# =====================================================================
# 完整网络导出
# =====================================================================

def _export_full_network(base_path: str, concepts: dict, 
                        relations_index: dict, min_strength: float) -> tuple:
    """
    导出完整关系网络
    
    Returns:
        (nodes, edges)
    """
    # 收集所有节点（有关系的概念）
    adjacency = relations_index.get("adjacency", {})
    connected_concepts = set(adjacency.keys())
    
    # 收集所有边
    all_edges = []
    
    for concept_id in connected_concepts:
        relations = get_relations_by_concept(base_path, concept_id, min_strength=min_strength)
        
        for rel in relations:
            all_edges.append({
                "source": concept_id,
                "target": rel["to_id"],
                "type": rel["type"],
                "strength": rel["strength"],
                "relation_id": rel["relation_id"]
            })
            
            # 确保目标节点也在集合中
            connected_concepts.add(rel["to_id"])
    
    # 构建节点列表
    nodes = []
    for concept_id in connected_concepts:
        if concept_id not in concepts:
            continue
        
        concept_data = concepts[concept_id]
        nodes.append({
            "id": concept_id,
            "name": concept_data.get("name_zh") or concept_data.get("name"),
            "activation": concept_data.get("activation_weight", 0.5),
            "status": concept_data.get("status", "warm"),
            "discussion_count": concept_data.get("discussion_count", 0)
        })
    
    return nodes, all_edges


# =====================================================================
# 格式化函数
# =====================================================================

def _format_d3(nodes: list, edges: list) -> dict:
    """
    格式化为D3.js force graph格式
    
    D3格式：
    {
      "nodes": [{"id": "c1", "name": "康德", "group": 1, ...}],
      "links": [{"source": "c1", "target": "c2", "value": 0.8, ...}]
    }
    """
    # 为节点分配分组（按status）
    status_groups = {"hot": 1, "warm": 2, "cold": 3}
    
    d3_nodes = []
    for node in nodes:
        d3_nodes.append({
            "id": node["id"],
            "name": node["name"],
            "group": status_groups.get(node["status"], 2),
            "activation": node["activation"],
            "status": node["status"],
            "discussion_count": node["discussion_count"],
            "is_center": node.get("is_center", False)
        })
    
    d3_links = []
    for edge in edges:
        rel_type_info = RELATION_TYPES[edge["type"]]
        
        d3_links.append({
            "source": edge["source"],
            "target": edge["target"],
            "value": edge["strength"],  # D3使用value表示边的权重
            "type": edge["type"],
            "color": rel_type_info["color"],
            "relation_id": edge["relation_id"]
        })
    
    return {
        "nodes": d3_nodes,
        "links": d3_links
    }


def _format_cytoscape(nodes: list, edges: list) -> dict:
    """
    格式化为Cytoscape.js格式
    
    Cytoscape格式：
    {
      "elements": [
        {"data": {"id": "c1", "label": "康德", ...}},
        {"data": {"id": "e1", "source": "c1", "target": "c2", ...}}
      ]
    }
    """
    elements = []
    
    # 添加节点
    for node in nodes:
        elements.append({
            "data": {
                "id": node["id"],
                "label": node["name"],
                "activation": node["activation"],
                "status": node["status"],
                "discussion_count": node["discussion_count"],
                "is_center": node.get("is_center", False)
            },
            "classes": node["status"]  # 可用于CSS样式
        })
    
    # 添加边
    for edge in edges:
        rel_type_info = RELATION_TYPES[edge["type"]]
        
        elements.append({
            "data": {
                "id": edge["relation_id"],
                "source": edge["source"],
                "target": edge["target"],
                "strength": edge["strength"],
                "type": edge["type"],
                "color": rel_type_info["color"]
            },
            "classes": edge["type"]
        })
    
    return {
        "elements": elements
    }


# =====================================================================
# 辅助函数
# =====================================================================

def _find_concept_id_by_name(name: str, concepts: dict) -> str:
    """根据名称查找概念ID"""
    name_lower = name.lower()
    
    for concept_id, concept_data in concepts.items():
        c_name = concept_data.get("name", "").lower()
        c_name_zh = concept_data.get("name_zh", "").lower()
        
        if c_name == name_lower or c_name_zh == name_lower:
            return concept_id
        
        # 部分匹配
        if name_lower in c_name or name_lower in c_name_zh:
            return concept_id
    
    return None


# =====================================================================
# 导出
# =====================================================================

__all__ = ['nisb_export_relation_network']

