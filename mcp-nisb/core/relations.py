#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
NISB Relations Layer - Phase 3.0
神经网络关系层：突触连接、激活扩散、Hebbian学习

功能：
1. Relations CRUD（创建、查询、更新、删除）
2. 关系类型管理（4种：semantic、causal、temporal、contradictory）
3. 突触强度管理（Hebbian学习、衰减）
4. 索引管理（邻接表、快速查询）
5. 多用户隔离
"""

import os
import json
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
import sys
sys.path.insert(0, '/srv')


# =====================================================================
# 关系类型定义（4种神经突触）
# =====================================================================

RELATION_TYPES = {
    "semantic": {
        "name": "语义关联",
        "description": "概念之间的语义相似性（如：康德-先验、AI-机器学习）",
        "initial_strength": 0.5,
        "decay_rate": 0.01,  # 每天衰减1%
        "color": "#3498db"   # 可视化颜色：蓝色
    },
    "causal": {
        "name": "因果关系",
        "description": "A导致B（如：认知偏差-决策失误）",
        "initial_strength": 0.6,
        "decay_rate": 0.005,  # 每天衰减0.5%（因果关系衰减慢）
        "color": "#e74c3c"    # 红色
    },
    "temporal": {
        "name": "时序关系",
        "description": "A先于B出现（如：学习-理解-应用）",
        "initial_strength": 0.4,
        "decay_rate": 0.02,   # 每天衰减2%（时序关系衰减快）
        "color": "#f39c12"    # 橙色
    },
    "contradictory": {
        "name": "矛盾关系",
        "description": "概念之间的冲突（如：自由意志-决定论）",
        "initial_strength": 0.3,
        "decay_rate": 0.005,  # 每天衰减0.5%（矛盾关系需要长期保留）
        "color": "#9b59b6"    # 紫色
    }
}


# =====================================================================
# 核心函数：Relations CRUD
# =====================================================================

def create_relation(base_path: str, from_id: str, to_id: str, 
                   relation_type: str, strength: float = None,
                   bidirectional: bool = False) -> Dict:
    """
    创建关系（突触连接）
    
    Args:
        base_path: 用户数据目录
        from_id: 源概念ID
        to_id: 目标概念ID
        relation_type: 关系类型（semantic/causal/temporal/contradictory）
        strength: 初始强度（None=使用默认值）
        bidirectional: 是否创建双向关系（semantic通常是双向）
    
    Returns:
        {"status": "success", "relation_id": "...", "strength": 0.5}
    """
    # 参数验证
    if relation_type not in RELATION_TYPES:
        return {"status": "error", "message": f"❌ 不支持的关系类型：{relation_type}"}
    
    if from_id == to_id:
        return {"status": "error", "message": "❌ 不能创建自己到自己的关系"}
    
    # 检查概念是否存在
    from core.storage import load_concepts_index
    index = load_concepts_index(base_path)
    concepts = index.get("concepts", {})
    
    if from_id not in concepts:
        return {"status": "error", "message": f"❌ 源概念不存在：{from_id}"}
    if to_id not in concepts:
        return {"status": "error", "message": f"❌ 目标概念不存在：{to_id}"}
    
    # 检查关系是否已存在
    existing = _find_relation(base_path, from_id, to_id, relation_type)
    if existing:
        return {"status": "error", "message": f"❌ 关系已存在：{existing['relation_id']}"}
    
    # 确定初始强度
    if strength is None:
        strength = RELATION_TYPES[relation_type]["initial_strength"]
    strength = max(0.0, min(1.0, strength))  # 限制在[0, 1]
    
    # 生成关系ID
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
    relation_id = f"rel_{timestamp}"
    
    # 创建关系对象
    relation = {
        "relation_id": relation_id,
        "from_id": from_id,
        "to_id": to_id,
        "type": relation_type,
        "strength": strength,
        "co_activation_count": 0,
        "last_activated": None,
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat()
    }
    
    # 保存到JSONL文件
    relations_dir = f"{base_path}/storage/entities/relations/by_type"
    os.makedirs(relations_dir, exist_ok=True)
    
    relation_file = f"{relations_dir}/{relation_type}.jsonl"
    with open(relation_file, 'a', encoding='utf-8') as f:
        f.write(json.dumps(relation, ensure_ascii=False) + '\n')
    
    # 更新索引
    _update_relations_index(base_path, relation, action="add")
    
    # 如果是双向关系（如semantic），创建反向关系
    if bidirectional:
        reverse_relation = relation.copy()
        reverse_relation["relation_id"] = f"rel_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}_rev"
        reverse_relation["from_id"] = to_id
        reverse_relation["to_id"] = from_id
        
        with open(relation_file, 'a', encoding='utf-8') as f:
            f.write(json.dumps(reverse_relation, ensure_ascii=False) + '\n')
        
        _update_relations_index(base_path, reverse_relation, action="add")
    
    return {
        "status": "success",
        "relation_id": relation_id,
        "from_concept": concepts[from_id]["name"],
        "to_concept": concepts[to_id]["name"],
        "type": relation_type,
        "strength": strength,
        "bidirectional": bidirectional
    }


def get_relations_by_concept(base_path: str, concept_id: str, 
                             relation_type: Optional[str] = None,
                             min_strength: float = 0.0) -> List[Dict]:
    """
    查询概念的所有关系（从该概念出发的边）
    
    Args:
        base_path: 用户数据目录
        concept_id: 概念ID
        relation_type: 关系类型（None=所有类型）
        min_strength: 最低强度阈值
    
    Returns:
        [{"relation_id": "...", "to_id": "...", "strength": 0.8, ...}, ...]
    """
    # 从索引加载
    index = load_relations_index(base_path)
    adjacency = index.get("adjacency", {})
    
    if concept_id not in adjacency:
        return []
    
    relations = []
    for rel_id in adjacency[concept_id]:
        rel = _load_relation_by_id(base_path, rel_id)
        if rel is None:
            continue
        
        # 过滤条件
        if relation_type and rel["type"] != relation_type:
            continue
        if rel["strength"] < min_strength:
            continue
        
        relations.append(rel)
    
    # 按强度排序（从高到低）
    relations.sort(key=lambda x: x["strength"], reverse=True)
    
    return relations


def strengthen_relation(base_path: str, from_id: str, to_id: str, 
                       delta: float = 0.01) -> Dict:
    """
    增强关系（Hebbian学习：共同激活 → 增强突触）
    
    Args:
        base_path: 用户数据目录
        from_id: 源概念ID
        to_id: 目标概念ID
        delta: 增强幅度（默认0.01，即1%）
    
    Returns:
        {"status": "success", "strength_old": 0.8, "strength_new": 0.81}
    """
    # 查找所有类型的关系
    relation = None
    for rel_type in RELATION_TYPES.keys():
        rel = _find_relation(base_path, from_id, to_id, rel_type)
        if rel:
            relation = rel
            break
    
    if not relation:
        return {"status": "error", "message": "❌ 关系不存在"}
    
    # 更新强度（上限1.0）
    old_strength = relation["strength"]
    new_strength = min(1.0, old_strength + delta)
    
    relation["strength"] = new_strength
    relation["co_activation_count"] += 1
    relation["last_activated"] = datetime.now().isoformat()
    relation["updated_at"] = datetime.now().isoformat()
    
    # 写回文件
    _update_relation_in_file(base_path, relation)
    
    # 更新索引
    _update_relations_index(base_path, relation, action="update")
    
    return {
        "status": "success",
        "relation_id": relation["relation_id"],
        "strength_old": old_strength,
        "strength_new": new_strength,
        "co_activation_count": relation["co_activation_count"]
    }


def weaken_relation(base_path: str, from_id: str, to_id: str, 
                   delta: float = 0.01) -> Dict:
    """
    削弱关系（突触衰减）
    
    Args:
        delta: 衰减幅度（默认0.01，即1%）
    """
    relation = None
    for rel_type in RELATION_TYPES.keys():
        rel = _find_relation(base_path, from_id, to_id, rel_type)
        if rel:
            relation = rel
            break
    
    if not relation:
        return {"status": "error", "message": "❌ 关系不存在"}
    
    old_strength = relation["strength"]
    new_strength = max(0.0, old_strength - delta)
    
    relation["strength"] = new_strength
    relation["updated_at"] = datetime.now().isoformat()
    
    # 如果强度降到0.1以下，自动删除
    if new_strength < 0.1:
        return delete_relation(base_path, relation["relation_id"])
    
    _update_relation_in_file(base_path, relation)
    _update_relations_index(base_path, relation, action="update")
    
    return {
        "status": "success",
        "relation_id": relation["relation_id"],
        "strength_old": old_strength,
        "strength_new": new_strength,
        "deleted": False
    }


def delete_relation(base_path: str, relation_id: str) -> Dict:
    """
    删除关系
    
    Args:
        relation_id: 关系ID
    
    Returns:
        {"status": "success"}
    """
    relation = _load_relation_by_id(base_path, relation_id)
    if not relation:
        return {"status": "error", "message": "❌ 关系不存在"}
    
    # 从文件中删除（标记删除，不物理删除）
    relation["deleted"] = True
    relation["deleted_at"] = datetime.now().isoformat()
    _update_relation_in_file(base_path, relation)
    
    # 从索引中移除
    _update_relations_index(base_path, relation, action="delete")
    
    return {
        "status": "success",
        "relation_id": relation_id,
        "message": "✅ 关系已删除"
    }


# =====================================================================
# 索引管理（邻接表，快速查询）
# =====================================================================

def load_relations_index(base_path: str) -> Dict:
    """
    加载Relations索引（邻接表）
    
    结构：
    {
      "version": "1.0",
      "total": 850,
      "last_updated": "2025-11-04T10:30:00Z",
      "adjacency": {
        "concept_c1": ["rel_1", "rel_2", "rel_3"],
        "concept_c2": ["rel_4", "rel_5"]
      },
      "by_type": {
        "semantic": 600,
        "causal": 120,
        "temporal": 80,
        "contradictory": 50
      }
    }
    """
    index_file = f"{base_path}/storage/entities/relations/index/relations.index.json"
    
    if not os.path.exists(index_file):
        # 初始化空索引
        index = {
            "version": "1.0",
            "total": 0,
            "last_updated": datetime.now().isoformat(),
            "adjacency": {},
            "by_type": {k: 0 for k in RELATION_TYPES.keys()}
        }
        os.makedirs(os.path.dirname(index_file), exist_ok=True)
        with open(index_file, 'w', encoding='utf-8') as f:
            json.dump(index, f, ensure_ascii=False, indent=2)
        return index
    
    with open(index_file, 'r', encoding='utf-8') as f:
        return json.load(f)


def save_relations_index(base_path: str, index: Dict):
    """保存索引"""
    index_file = f"{base_path}/storage/entities/relations/index/relations.index.json"
    os.makedirs(os.path.dirname(index_file), exist_ok=True)
    
    index["last_updated"] = datetime.now().isoformat()
    
    with open(index_file, 'w', encoding='utf-8') as f:
        json.dump(index, f, ensure_ascii=False, indent=2)


def rebuild_relations_index(base_path: str) -> Dict:
    """
    重建Relations索引（管理员工具，修复损坏的索引）
    
    Returns:
        {"status": "success", "total": 850, "by_type": {...}}
    """
    print("[INFO] 开始重建Relations索引...")
    
    index = {
        "version": "1.0",
        "total": 0,
        "last_updated": datetime.now().isoformat(),
        "adjacency": {},
        "by_type": {k: 0 for k in RELATION_TYPES.keys()}
    }
    
    relations_dir = f"{base_path}/storage/entities/relations/by_type"
    
    if not os.path.exists(relations_dir):
        save_relations_index(base_path, index)
        return {"status": "success", "total": 0, "message": "✅ 索引已初始化（无数据）"}
    
    # 扫描所有关系文件
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
                    
                    # 跳过已删除的关系
                    if rel.get("deleted", False):
                        continue
                    
                    # 更新邻接表
                    from_id = rel["from_id"]
                    if from_id not in index["adjacency"]:
                        index["adjacency"][from_id] = []
                    index["adjacency"][from_id].append(rel["relation_id"])
                    
                    # 更新类型统计
                    index["by_type"][rel["type"]] += 1
                    index["total"] += 1
                    
                except json.JSONDecodeError:
                    continue
    
    save_relations_index(base_path, index)
    
    print(f"[INFO] Relations索引重建完成：{index['total']}条关系")
    
    return {
        "status": "success",
        "total": index["total"],
        "by_type": index["by_type"],
        "message": f"✅ 索引重建完成：{index['total']}条关系"
    }


# =====================================================================
# 衰减管理（突触随时间衰减）
# =====================================================================

def decay_all_relations(base_path: str, days: int = 1) -> Dict:
    """
    对所有关系执行衰减（定时任务，每天凌晨执行）
    
    Args:
        base_path: 用户数据目录
        days: 衰减天数（默认1天）
    
    Returns:
        {"status": "success", "decayed": 850, "deleted": 12}
    """
    print(f"[INFO] 开始执行突触衰减（{days}天）...")
    
    decayed_count = 0
    deleted_count = 0
    
    relations_dir = f"{base_path}/storage/entities/relations/by_type"
    
    if not os.path.exists(relations_dir):
        return {"status": "success", "decayed": 0, "deleted": 0}
    
    # 遍历所有关系类型
    for rel_type in RELATION_TYPES.keys():
        rel_file = f"{relations_dir}/{rel_type}.jsonl"
        if not os.path.exists(rel_file):
            continue
        
        decay_rate = RELATION_TYPES[rel_type]["decay_rate"]
        
        # 读取所有关系
        relations = []
        with open(rel_file, 'r', encoding='utf-8') as f:
            for line in f:
                if not line.strip():
                    continue
                try:
                    relations.append(json.loads(line))
                except:
                    continue
        
        # 更新强度
        updated_relations = []
        for rel in relations:
            if rel.get("deleted", False):
                updated_relations.append(rel)
                continue
            
            # 计算衰减
            old_strength = rel["strength"]
            new_strength = max(0.0, old_strength - decay_rate * days)
            
            rel["strength"] = new_strength
            rel["updated_at"] = datetime.now().isoformat()
            
            # 如果强度降到0.1以下，标记删除
            if new_strength < 0.1:
                rel["deleted"] = True
                rel["deleted_at"] = datetime.now().isoformat()
                deleted_count += 1
            else:
                decayed_count += 1
            
            updated_relations.append(rel)
        
        # 写回文件
        with open(rel_file, 'w', encoding='utf-8') as f:
            for rel in updated_relations:
                f.write(json.dumps(rel, ensure_ascii=False) + '\n')
    
    # 重建索引
    rebuild_relations_index(base_path)
    
    print(f"[INFO] 突触衰减完成：衰减{decayed_count}条，删除{deleted_count}条")
    
    return {
        "status": "success",
        "decayed": decayed_count,
        "deleted": deleted_count,
        "message": f"✅ 突触衰减完成：衰减{decayed_count}条，删除{deleted_count}条"
    }


# =====================================================================
# 内部辅助函数
# =====================================================================

def _find_relation(base_path: str, from_id: str, to_id: str, 
                  relation_type: str) -> Optional[Dict]:
    """查找特定关系（内部函数）"""
    rel_file = f"{base_path}/storage/entities/relations/by_type/{relation_type}.jsonl"
    
    if not os.path.exists(rel_file):
        return None
    
    with open(rel_file, 'r', encoding='utf-8') as f:
        for line in f:
            if not line.strip():
                continue
            try:
                rel = json.loads(line)
                if (rel.get("from_id") == from_id and 
                    rel.get("to_id") == to_id and 
                    not rel.get("deleted", False)):
                    return rel
            except:
                continue
    
    return None


def _load_relation_by_id(base_path: str, relation_id: str) -> Optional[Dict]:
    """根据ID加载关系（内部函数）"""
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
                    if rel.get("relation_id") == relation_id:
                        return rel
                except:
                    continue
    
    return None


def _update_relation_in_file(base_path: str, relation: Dict):
    """更新文件中的关系（内部函数）"""
    rel_type = relation["type"]
    rel_file = f"{base_path}/storage/entities/relations/by_type/{rel_type}.jsonl"
    
    # 读取所有关系
    relations = []
    with open(rel_file, 'r', encoding='utf-8') as f:
        for line in f:
            if not line.strip():
                continue
            try:
                rel = json.loads(line)
                if rel["relation_id"] == relation["relation_id"]:
                    relations.append(relation)  # 替换
                else:
                    relations.append(rel)
            except:
                continue
    
    # 写回文件
    with open(rel_file, 'w', encoding='utf-8') as f:
        for rel in relations:
            f.write(json.dumps(rel, ensure_ascii=False) + '\n')


def _update_relations_index(base_path: str, relation: Dict, action: str):
    """更新索引（内部函数）"""
    index = load_relations_index(base_path)
    
    if action == "add":
        # 添加到邻接表
        from_id = relation["from_id"]
        if from_id not in index["adjacency"]:
            index["adjacency"][from_id] = []
        if relation["relation_id"] not in index["adjacency"][from_id]:
            index["adjacency"][from_id].append(relation["relation_id"])
        
        # 更新统计
        index["by_type"][relation["type"]] += 1
        index["total"] += 1
    
    elif action == "delete":
        # 从邻接表删除
        from_id = relation["from_id"]
        if from_id in index["adjacency"]:
            if relation["relation_id"] in index["adjacency"][from_id]:
                index["adjacency"][from_id].remove(relation["relation_id"])
        
        # 更新统计
        index["by_type"][relation["type"]] -= 1
        index["total"] -= 1
    
    elif action == "update":
        # 更新不需要改索引（只改强度）
        pass
    
    save_relations_index(base_path, index)

# =====================================================================
# ⭐ Phase 3.0 新增：统一创建接口（Relations + Synapses）
# =====================================================================

def create_relation_or_synapse(base_path: str, from_id: str, to_id: str,
                               relation_type: str, strength: float = None,
                               source: str = None, evidence: str = None,
                               strategy: str = None, user_preference: str = None,
                               bidirectional: bool = None) -> dict:
    """
    统一创建接口：根据分类标准自动创建Relations或Synapses
    
    这是Phase 3.0的核心接口，自动判断应该创建静态Relations还是动态Synapses
    
    参数:
        base_path: 用户数据根目录
        from_id: 源概念ID
        to_id: 目标概念ID
        relation_type: 关系类型
        strength: 强度（可选，自动推断）
        source: 来源（用于分类判断）
        evidence: 证据（用于分类判断）
        strategy: 发现策略（如果是Synapses）
        user_preference: 用户偏好（"relation" 或 "synapse"）
        bidirectional: 是否双向（可选，自动推断）
    
    返回:
        {
          status: "success",
          storage_type: "relation" 或 "synapse",
          relation_id/synapse_id: "...",
          message: "..."
        }
    
    示例:
        # 自动判断（推荐）
        create_relation_or_synapse(base_path, "c_kant", "c_philosopher", "is_a")
        → 创建Relations（静态关系）
        
        # 手动指定
        create_relation_or_synapse(base_path, "c_kant", "c_a_priori", "semantic",
                                  user_preference="synapse")
        → 创建Synapses（动态关系）
    """
    from core.classifier import (
        classify_relation, get_default_strength, should_be_bidirectional
    )
    from core.storage import load_concepts_index
    from core.synapses import create_synapse
    
    # 1. 加载概念（获取名称）
    concepts_index = load_concepts_index(base_path)
    concepts = concepts_index.get("concepts", {})
    
    if from_id not in concepts or to_id not in concepts:
        return {
            "status": "error",
            "message": f"❌ 概念不存在：{from_id} 或 {to_id}"
        }
    
    concept_a_name = concepts[from_id].get("name_zh") or concepts[from_id].get("name")
    concept_b_name = concepts[to_id].get("name_zh") or concepts[to_id].get("name")
    
    # 2. 自动分类（Relations vs Synapses）
    storage_type = classify_relation(
        concept_a=concept_a_name,
        concept_b=concept_b_name,
        relation_type=relation_type,
        source=source,
        evidence=evidence,
        user_preference=user_preference
    )
    
    # 3. 推断默认参数
    if strength is None:
        strength = get_default_strength(storage_type, relation_type)
    
    if bidirectional is None:
        bidirectional = should_be_bidirectional(relation_type)
    
    # 4. 根据分类创建对应类型
    if storage_type == "relation":
        # 创建静态Relations（使用现有函数）
        result = create_relation(
            base_path=base_path,
            from_id=from_id,
            to_id=to_id,
            relation_type=relation_type,
            strength=strength,
            bidirectional=bidirectional
        )
        
        # 添加存储类型信息
        result["storage_type"] = "relation"
        result["message"] = f"✅ 已创建静态关系（Relations）：{concept_a_name} → {concept_b_name}"
        
        return result
    
    else:
        # 创建动态Synapses
        result = create_synapse(
            base_path=base_path,
            from_id=from_id,
            to_id=to_id,
            relation_type=relation_type,
            strength=strength,
            strategy=strategy or "manual",
            evidence=evidence or "",
            bidirectional=bidirectional
        )
        
        # 添加存储类型信息
        result["storage_type"] = "synapse"
        result["message"] = f"✅ 已创建动态突触（Synapses）：{concept_a_name} → {concept_b_name}"
        
        return result


def query_static_relations(base_path: str, concept_id: str,
                          min_strength: float = 0.3) -> list:
    """
    查询静态Relations（无激活事件）
    
    与get_relations_by_concept的区别：
    - 不触发激活
    - 不更新activation_count
    - 查询速度更快（直接复用现有函数）
    
    返回:
        [
          {"relation_id": "...", "to_id": "...", "type": "...", "strength": 0.95},
          ...
        ]
    """
    # 直接调用现有函数
    return get_relations_by_concept(base_path, concept_id, min_strength=min_strength)

# =====================================================================
# 导出函数
# =====================================================================

__all__ = [
    'RELATION_TYPES',
    'create_relation',
    'get_relations_by_concept',
    'strengthen_relation',
    'weaken_relation',
    'delete_relation',
    'load_relations_index',
    'save_relations_index',
    'rebuild_relations_index',
    'decay_all_relations'
    # ⭐ Phase 3.0 新增
    'create_relation_or_synapse',
    'query_static_relations'
]
