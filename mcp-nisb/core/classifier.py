#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
NISB Relations vs Synapses 分类引擎 - Phase 3.0
根据关系特征自动判断应该存储为静态Relations还是动态Synapses

核心逻辑：
1. 静态Relations：事实性、高确定性、无需学习（70%）
2. 动态Synapses：关联性、低确定性、需要学习（30%）

基于神经科学：
- Relations = 陈述性记忆（静态突触，LTP长期增强）
- Synapses = 程序性记忆（动态突触，Hebbian学习）
"""

# =====================================================================
# 静态关系类型（高确定性、无需学习）
# =====================================================================

STATIC_RELATION_TYPES = [
    # 分类关系
    "is_a",           # "康德 → 哲学家"
    "instance_of",    # "纯粹理性批判 → 康德著作"
    
    # 组成关系
    "part_of",        # "柏林 → 德国"
    "contains",       # "德国 → 柏林"
    
    # 属性关系
    "has_property",   # "康德 → 1724年出生"
    "defined_as",     # "先验 → 先于经验的认识"
    
    # 事实关系
    "born_in",        # 出生地
    "died_in",        # 去世地
    "authored_by",    # 作者
    "published_in",   # 出版年份
    "located_in",     # 地理位置
    "founded_in",     # 创立时间
    "discovered_by",  # 发现者
    
    # 定义关系
    "equivalent_to",  # 等价于
    "synonym_of",     # 同义词
]

# =====================================================================
# 动态关系类型（低确定性、需要学习）
# =====================================================================

DYNAMIC_RELATION_TYPES = [
    # 关联关系
    "associated_with",  # "康德 → 先验"（思维路径）
    "semantic",         # 语义关联（默认动态）
    
    # 影响关系
    "influences",       # "康德 → 黑格尔"
    "inspired_by",      # 受到启发
    
    # 对比关系
    "contrasts_with",   # "康德 → 休谟"
    "similar_to",       # 相似于
    "different_from",   # 不同于
    
    # 场景关系
    "used_in_context",  # "先验 → 认识论"
    "applied_to",       # 应用于
    
    # 时序关系
    "temporal",         # 时间顺序
    "precedes",         # 先于
    "follows",          # 后于
    
    # 其他
    "reminds_of",       # 联想
    "contradictory",    # 矛盾（可能是动态的）
]

# =====================================================================
# 静态来源（权威知识库）
# =====================================================================

STATIC_SOURCES = [
    "kb",            # 知识库
    "corpus",        # 语料库
    "wikipedia",     # 维基百科
    "book",          # 书籍
    "encyclopedia",  # 百科全书
    "textbook",      # 教科书
    "dictionary",    # 词典
    "database",      # 数据库
    "official",      # 官方来源
]

# 权威关键词（用于证据判断）
AUTHORITY_KEYWORDS = [
    "wikipedia", "encyclopedia", "textbook", "定义", "事实", "根据",
    "百科", "词典", "官方", "数据库", "文献", "论文", "研究"
]


# =====================================================================
# 核心分类函数
# =====================================================================

def classify_relation(concept_a: str, concept_b: str, relation_type: str,
                     source: str = None, evidence: str = None, 
                     user_preference: str = None) -> str:
    """
    自动分类：Relations（静态）vs Synapses（动态）
    
    决策树：
    1. 用户偏好优先（如果用户明确指定）
    2. 关系类型判断（最高优先级）
    3. 来源判断（权威来源优先静态）
    4. 证据判断（有权威证据优先静态）
    5. 默认策略（保守 → 动态）
    
    参数:
        concept_a: 概念A名称
        concept_b: 概念B名称
        relation_type: 关系类型
        source: 来源（用于判断）
        evidence: 证据（用于判断）
        user_preference: 用户偏好（"relation" 或 "synapse"）
    
    返回:
        "relation" 或 "synapse"
    
    示例:
        classify_relation("康德", "哲学家", "is_a")
        → "relation"（静态，事实性关系）
        
        classify_relation("康德", "先验", "associated_with")
        → "synapse"（动态，思维路径）
    """
    
    # 步骤1：用户偏好优先（最高优先级）
    if user_preference in ["relation", "synapse"]:
        return user_preference
    
    # 步骤2：关系类型判断（核心逻辑）
    if relation_type in STATIC_RELATION_TYPES:
        return "relation"  # 静态关系
    
    if relation_type in DYNAMIC_RELATION_TYPES:
        return "synapse"   # 动态关系
    
    # 步骤3：来源判断
    if source and source.lower() in STATIC_SOURCES:
        return "relation"
    
    # 步骤4：证据判断（检查权威关键词）
    if evidence:
        if any(keyword in evidence.lower() for keyword in AUTHORITY_KEYWORDS):
            return "relation"
    
    # 步骤5：默认策略（保守 → 动态）
    # 原因：不确定的关系优先使用Synapses，可以学习
    return "synapse"


def get_default_strength(storage_type: str, relation_type: str) -> float:
    """
    根据存储类型返回默认强度
    
    设计理念：
    - Relations（静态）：高强度（0.95），表示确定性事实
    - Synapses（动态）：中等强度（0.70），表示需要学习
    
    参数:
        storage_type: "relation" 或 "synapse"
        relation_type: 关系类型
    
    返回:
        默认强度（0.0-1.0）
    
    示例:
        get_default_strength("relation", "is_a") → 0.95
        get_default_strength("synapse", "associated_with") → 0.70
    """
    if storage_type == "relation":
        # 静态关系：高强度（确定性事实）
        return 0.95
    else:
        # 动态关系：中等强度（需要学习）
        # 不同类型的初始强度可以不同
        if relation_type == "semantic":
            return 0.70  # 语义关联
        elif relation_type == "temporal":
            return 0.65  # 时序关系
        elif relation_type == "influences":
            return 0.75  # 影响关系
        else:
            return 0.70  # 默认


def should_be_bidirectional(relation_type: str) -> bool:
    """
    判断关系是否应该双向
    
    设计理念：
    - 双向关系：语义关联、关联关系等（对称）
    - 单向关系：分类关系、影响关系等（非对称）
    
    参数:
        relation_type: 关系类型
    
    返回:
        True（双向）或 False（单向）
    
    示例:
        should_be_bidirectional("semantic") → True
        should_be_bidirectional("is_a") → False
    """
    # 双向关系类型
    bidirectional_types = [
        "semantic",         # 语义关联（对称）
        "associated_with",  # 关联关系（对称）
        "used_in_context",  # 场景关系（对称）
        "reminds_of",       # 联想（对称）
        "similar_to",       # 相似（对称）
        "contrasts_with",   # 对比（对称）
        "contradictory",    # 矛盾（对称）
        "equivalent_to",    # 等价（对称）
        "synonym_of",       # 同义（对称）
    ]
    
    return relation_type in bidirectional_types


def get_classification_reason(storage_type: str, relation_type: str, 
                              source: str = None) -> str:
    """
    返回分类理由（用于日志和调试）
    
    参数:
        storage_type: "relation" 或 "synapse"
        relation_type: 关系类型
        source: 来源
    
    返回:
        分类理由（字符串）
    
    示例:
        get_classification_reason("relation", "is_a")
        → "静态关系类型（is_a）→ 确定性事实"
    """
    if storage_type == "relation":
        if relation_type in STATIC_RELATION_TYPES:
            return f"静态关系类型（{relation_type}）→ 确定性事实"
        elif source and source.lower() in STATIC_SOURCES:
            return f"权威来源（{source}）→ 事实性知识"
        else:
            return "用户指定为静态关系"
    else:
        if relation_type in DYNAMIC_RELATION_TYPES:
            return f"动态关系类型（{relation_type}）→ 思维路径"
        else:
            return "默认为动态关系（保守策略）"


# =====================================================================
# 批量分类（用于数据迁移）
# =====================================================================

def batch_classify_relations(relations: list) -> dict:
    """
    批量分类现有关系（用于从旧版本迁移）
    
    参数:
        relations: 关系列表
        [
          {"from_id": "...", "to_id": "...", "type": "...", ...},
          ...
        ]
    
    返回:
        {
          "total": 总数,
          "static": 静态关系数,
          "dynamic": 动态关系数,
          "classifications": [
            {"relation_id": "...", "storage_type": "relation/synapse", "reason": "..."},
            ...
          ]
        }
    """
    classifications = []
    static_count = 0
    dynamic_count = 0
    
    for rel in relations:
        storage_type = classify_relation(
            concept_a=rel.get("from_name", ""),
            concept_b=rel.get("to_name", ""),
            relation_type=rel.get("type", "semantic"),
            source=rel.get("source"),
            evidence=rel.get("evidence")
        )
        
        reason = get_classification_reason(
            storage_type=storage_type,
            relation_type=rel.get("type", "semantic"),
            source=rel.get("source")
        )
        
        classifications.append({
            "relation_id": rel.get("relation_id"),
            "from_id": rel.get("from_id"),
            "to_id": rel.get("to_id"),
            "type": rel.get("type"),
            "storage_type": storage_type,
            "reason": reason
        })
        
        if storage_type == "relation":
            static_count += 1
        else:
            dynamic_count += 1
    
    return {
        "total": len(relations),
        "static": static_count,
        "dynamic": dynamic_count,
        "static_percentage": (static_count / len(relations)) * 100 if relations else 0,
        "dynamic_percentage": (dynamic_count / len(relations)) * 100 if relations else 0,
        "classifications": classifications
    }


# =====================================================================
# 导出（供其他模块使用）
# =====================================================================

__all__ = [
    'classify_relation',
    'get_default_strength',
    'should_be_bidirectional',
    'get_classification_reason',
    'batch_classify_relations',
    'STATIC_RELATION_TYPES',
    'DYNAMIC_RELATION_TYPES'
]
