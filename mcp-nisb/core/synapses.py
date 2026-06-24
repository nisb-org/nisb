#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
NISB Synapses 动态突触模块 - Phase 3.0
实现Hebbian学习、激活事件、突触衰减等神经仿生机制

核心机制：
1. Hebbian学习：越用越强（Fire together, wire together）
2. 激活事件：记录每次使用（追踪思维轨迹）
3. 突触衰减：长期不用则减弱（Use it or lose it）
4. 延迟写入：批量写入减少IO（性能优化）

神经科学基础：
- 基于Donald Hebb的突触可塑性理论（1949）
- 模拟程序性记忆（技能学习）
- 动态调整强度（0.3-1.0）
"""

import os
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional


# =====================================================================
# Synapses数据结构
# =====================================================================

class Synapse:
    """
    动态突触类
    
    属性:
        synapse_id: 突触ID
        from_id: 源概念ID
        to_id: 目标概念ID
        type: 关系类型
        strength: 突触强度（0.0-1.0，动态调整）
        activation_count: 激活次数
        co_activation_count: 共同激活次数
        last_activated: 最后激活时间
        activation_history: 激活历史（最近100次）
        created_at: 创建时间
        updated_at: 更新时间
    """
    
    def __init__(self, synapse_id: str, from_id: str, to_id: str,
                 relation_type: str, strength: float = 0.70):
        self.synapse_id = synapse_id
        self.from_id = from_id
        self.to_id = to_id
        self.type = relation_type
        self.strength = strength
        self.activation_count = 0
        self.co_activation_count = 0
        self.last_activated = None
        self.activation_history = []  # 最近100次
        self.created_at = datetime.now().isoformat()
        self.updated_at = datetime.now().isoformat()
        self.deleted = False
    
    def activate(self, event_type: str = "query", context: str = None):
        """
        激活突触（Hebbian学习）
        
        机制：
        1. 增加激活次数
        2. 增强突触强度（+0.01，最高1.0）
        3. 记录激活事件
        4. 更新最后激活时间
        
        参数:
            event_type: 激活类型（query/recommend/path/context等）
            context: 上下文信息
        """
        # 1. 增加激活次数
        self.activation_count += 1
        
        # 2. Hebbian学习：增强突触强度
        # 公式：strength += 0.01 * (1 - strength)（越接近1.0增长越慢）
        hebbian_increment = 0.01 * (1.0 - self.strength)
        self.strength = min(1.0, self.strength + hebbian_increment)
        
        # 3. 记录激活事件（采样记录，节省空间）
        if self._should_record_activation():
            activation_event = {
                "timestamp": datetime.now().isoformat(),
                "event_type": event_type,
                "context": context,
                "strength_after": round(self.strength, 3)
            }
            self.activation_history.append(activation_event)
            
            # 只保留最近100次（内存优化）
            if len(self.activation_history) > 100:
                self.activation_history = self.activation_history[-100:]
        
        # 4. 更新时间
        self.last_activated = datetime.now().isoformat()
        self.updated_at = datetime.now().isoformat()
    
    def _should_record_activation(self) -> bool:
        """
        判断是否应该记录本次激活（采样记录）
        
        策略：
        - 前100次：全部记录
        - 100-1000次：10%采样（每10次记录1次）
        - 1000次+：1%采样（每100次记录1次）
        
        目的：节省存储空间（1000次激活只记录约199条）
        """
        if self.activation_count <= 100:
            return True  # 前100次全记录
        elif self.activation_count <= 1000:
            return self.activation_count % 10 == 0  # 10%采样
        else:
            return self.activation_count % 100 == 0  # 1%采样
    
    def decay(self, days_since_last_activation: int):
        """
        突触衰减（Use it or lose it）
        
        机制：
        - 超过30天不用：强度 -0.01/天
        - 超过90天不用：强度 -0.02/天
        - 最低不低于初始强度的50%
        
        参数:
            days_since_last_activation: 距离上次激活的天数
        """
        if days_since_last_activation > 90:
            decay_rate = 0.02  # 快速衰减
        elif days_since_last_activation > 30:
            decay_rate = 0.01  # 慢速衰减
        else:
            return  # 30天内不衰减
        
        # 应用衰减（最低不低于0.35）
        self.strength = max(0.35, self.strength - decay_rate * (days_since_last_activation - 30))
        self.updated_at = datetime.now().isoformat()
    
    def to_dict(self) -> Dict:
        """转换为字典（用于存储）"""
        return {
            "synapse_id": self.synapse_id,
            "from_id": self.from_id,
            "to_id": self.to_id,
            "type": self.type,
            "strength": round(self.strength, 3),
            "activation_count": self.activation_count,
            "co_activation_count": self.co_activation_count,
            "last_activated": self.last_activated,
            "activation_history": self.activation_history,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "deleted": self.deleted
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'Synapse':
        """从字典创建Synapse对象"""
        synapse = cls(
            synapse_id=data["synapse_id"],
            from_id=data["from_id"],
            to_id=data["to_id"],
            relation_type=data["type"],
            strength=data.get("strength", 0.70)
        )
        synapse.activation_count = data.get("activation_count", 0)
        synapse.co_activation_count = data.get("co_activation_count", 0)
        synapse.last_activated = data.get("last_activated")
        synapse.activation_history = data.get("activation_history", [])
        synapse.created_at = data.get("created_at", datetime.now().isoformat())
        synapse.updated_at = data.get("updated_at", datetime.now().isoformat())
        synapse.deleted = data.get("deleted", False)
        return synapse


# =====================================================================
# Synapses CRUD操作
# =====================================================================

def create_synapse(base_path: str, from_id: str, to_id: str,
                  relation_type: str, strength: float = 0.70,
                  strategy: str = "manual", evidence: str = "",
                  bidirectional: bool = False) -> dict:
    """
    创建动态突触（Synapses）
    
    参数:
        base_path: 用户数据根目录
        from_id: 源概念ID
        to_id: 目标概念ID
        relation_type: 关系类型
        strength: 初始强度（默认0.70）
        strategy: 发现策略（manual/batch_discovery等）
        evidence: 证据
        bidirectional: 是否双向
    
    返回:
        {
          status: "success",
          synapse_id: "syn_xxx",
          message: "..."
        }
    """
    import os
    
    # 生成唯一ID
    synapse_id = f"syn_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{os.urandom(3).hex()}"
    
    # 创建Synapse对象
    synapse = Synapse(
        synapse_id=synapse_id,
        from_id=from_id,
        to_id=to_id,
        relation_type=relation_type,
        strength=strength
    )
    
    # 保存到文件
    synapses_dir = f"{base_path}/storage/entities/synapses/by_type"
    os.makedirs(synapses_dir, exist_ok=True)
    
    synapse_file = f"{synapses_dir}/{relation_type}.jsonl"
    
    synapse_data = synapse.to_dict()
    synapse_data["strategy"] = strategy
    synapse_data["evidence"] = evidence
    
    with open(synapse_file, 'a', encoding='utf-8') as f:
        f.write(json.dumps(synapse_data, ensure_ascii=False) + "\n")
    
    # 如果双向，创建反向突触
    if bidirectional:
        reverse_synapse_id = f"syn_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{os.urandom(3).hex()}"
        reverse_synapse = Synapse(
            synapse_id=reverse_synapse_id,
            from_id=to_id,
            to_id=from_id,
            relation_type=relation_type,
            strength=strength
        )
        
        reverse_data = reverse_synapse.to_dict()
        reverse_data["strategy"] = strategy
        reverse_data["evidence"] = evidence
        
        with open(synapse_file, 'a', encoding='utf-8') as f:
            f.write(json.dumps(reverse_data, ensure_ascii=False) + "\n")
    
    # 更新索引
    _update_synapses_index(base_path)
    
    return {
        "status": "success",
        "synapse_id": synapse_id,
        "message": f"✅ 已创建动态突触（Synapses）：{synapse_id}"
    }


def query_synapses(base_path: str, concept_id: str, 
                  min_strength: float = 0.3,
                  activate: bool = True) -> List[Dict]:
    """
    查询概念的所有Synapses（并触发激活）
    
    参数:
        base_path: 用户数据根目录
        concept_id: 概念ID
        min_strength: 最低强度阈值
        activate: 是否触发激活事件（默认True）
    
    返回:
        [
          {
            "synapse_id": "...",
            "to_id": "...",
            "type": "...",
            "strength": 0.78,
            "activation_count": 45,
            ...
          },
          ...
        ]
    """
    synapses = []
    synapses_dir = f"{base_path}/storage/entities/synapses/by_type"
    
    if not os.path.exists(synapses_dir):
        return synapses
    
    # 遍历所有类型文件
    for filename in os.listdir(synapses_dir):
        if not filename.endswith('.jsonl'):
            continue
        
        synapse_file = f"{synapses_dir}/{filename}"
        
        with open(synapse_file, 'r', encoding='utf-8') as f:
            for line in f:
                if not line.strip():
                    continue
                
                try:
                    synapse_data = json.loads(line)
                    
                    # 跳过已删除的
                    if synapse_data.get("deleted", False):
                        continue
                    
                    # 匹配概念ID
                    if synapse_data.get("from_id") == concept_id:
                        # 强度过滤
                        if synapse_data.get("strength", 0) >= min_strength:
                            # 如果需要激活，触发激活事件
                            if activate:
                                synapse = Synapse.from_dict(synapse_data)
                                synapse.activate(event_type="query", context="user_search")
                                synapse_data = synapse.to_dict()
                                
                                # 异步写回（延迟写入，性能优化）
                                _queue_synapse_update(base_path, synapse_data)
                            
                            synapses.append(synapse_data)
                
                except json.JSONDecodeError:
                    continue
    
    # 按强度排序
    synapses.sort(key=lambda x: x.get("strength", 0), reverse=True)
    
    return synapses


def update_synapse(base_path: str, synapse_id: str, 
                  updates: Dict) -> dict:
    """
    更新Synapse（用于批量写入）
    
    参数:
        base_path: 用户数据根目录
        synapse_id: 突触ID
        updates: 更新字段
    
    返回:
        {status: "success", message: "..."}
    """
    synapses_dir = f"{base_path}/storage/entities/synapses/by_type"
    
    # 遍历所有类型文件
    for filename in os.listdir(synapses_dir):
        if not filename.endswith('.jsonl'):
            continue
        
        synapse_file = f"{synapses_dir}/{filename}"
        temp_file = f"{synapse_file}.tmp"
        
        updated = False
        
        with open(synapse_file, 'r', encoding='utf-8') as f_in, \
             open(temp_file, 'w', encoding='utf-8') as f_out:
            
            for line in f_in:
                if not line.strip():
                    continue
                
                try:
                    synapse_data = json.loads(line)
                    
                    if synapse_data.get("synapse_id") == synapse_id:
                        # 应用更新
                        synapse_data.update(updates)
                        updated = True
                    
                    f_out.write(json.dumps(synapse_data, ensure_ascii=False) + "\n")
                
                except json.JSONDecodeError:
                    f_out.write(line)
        
        if updated:
            # 替换原文件
            os.replace(temp_file, synapse_file)
            return {
                "status": "success",
                "message": f"✅ 已更新突触：{synapse_id}"
            }
        else:
            # 删除临时文件
            if os.path.exists(temp_file):
                os.remove(temp_file)
    
    return {
        "status": "error",
        "message": f"❌ 找不到突触：{synapse_id}"
    }


def delete_synapse(base_path: str, synapse_id: str) -> dict:
    """
    删除Synapse（软删除）
    
    参数:
        base_path: 用户数据根目录
        synapse_id: 突触ID
    
    返回:
        {status: "success", message: "..."}
    """
    return update_synapse(base_path, synapse_id, {"deleted": True})


# =====================================================================
# 批量衰减（定期维护）
# =====================================================================

def batch_decay_synapses(base_path: str, days_threshold: int = 30) -> dict:
    """
    批量衰减长期未使用的突触
    
    参数:
        base_path: 用户数据根目录
        days_threshold: 天数阈值（超过此天数的突触会衰减）
    
    返回:
        {
          status: "success",
          total_synapses: 总数,
          decayed: 衰减数量,
          deleted: 删除数量（强度<0.3）
        }
    """
    synapses_dir = f"{base_path}/storage/entities/synapses/by_type"
    
    total_synapses = 0
    decayed_count = 0
    deleted_count = 0
    
    current_time = datetime.now()
    
    for filename in os.listdir(synapses_dir):
        if not filename.endswith('.jsonl'):
            continue
        
        synapse_file = f"{synapses_dir}/{filename}"
        temp_file = f"{synapse_file}.tmp"
        
        with open(synapse_file, 'r', encoding='utf-8') as f_in, \
             open(temp_file, 'w', encoding='utf-8') as f_out:
            
            for line in f_in:
                if not line.strip():
                    continue
                
                try:
                    synapse_data = json.loads(line)
                    total_synapses += 1
                    
                    if synapse_data.get("deleted", False):
                        f_out.write(line)
                        continue
                    
                    # 计算距离上次激活的天数
                    last_activated = synapse_data.get("last_activated")
                    if last_activated:
                        last_time = datetime.fromisoformat(last_activated)
                        days_since = (current_time - last_time).days
                        
                        if days_since > days_threshold:
                            # 创建Synapse对象并衰减
                            synapse = Synapse.from_dict(synapse_data)
                            old_strength = synapse.strength
                            synapse.decay(days_since)
                            
                            if synapse.strength < old_strength:
                                decayed_count += 1
                            
                            # 如果强度太低，软删除
                            if synapse.strength < 0.3:
                                synapse.deleted = True
                                deleted_count += 1
                            
                            synapse_data = synapse.to_dict()
                    
                    f_out.write(json.dumps(synapse_data, ensure_ascii=False) + "\n")
                
                except (json.JSONDecodeError, ValueError):
                    f_out.write(line)
        
        # 替换原文件
        os.replace(temp_file, synapse_file)
    
    return {
        "status": "success",
        "total_synapses": total_synapses,
        "decayed": decayed_count,
        "deleted": deleted_count,
        "message": f"✅ 衰减完成：{decayed_count}个突触衰减，{deleted_count}个突触删除"
    }


# =====================================================================
# 辅助函数
# =====================================================================

def _update_synapses_index(base_path: str):
    """更新Synapses索引（总索引、邻接表）"""
    # TODO: 实现索引更新逻辑（类似Relations）
    pass


def _queue_synapse_update(base_path: str, synapse_data: Dict):
    """
    将Synapse更新放入队列（延迟写入，性能优化）
    
    策略：
    - 激活事件暂存内存
    - 累计10次后批量写入
    - 或每5分钟自动写入
    
    TODO: 实现异步写入队列
    """
    pass


# =====================================================================
# 导出
# =====================================================================

__all__ = [
    'Synapse',
    'create_synapse',
    'query_synapses',
    'update_synapse',
    'delete_synapse',
    'batch_decay_synapses'
]

