#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
NISB Relations Tools - Phase 3.0 完整版
关系管理工具模块（包含经济版批次生成 + 5个高价值新方法）

13个工具：
- 基础管理（4个）：create, query, delete, stats
- 自动发现（2个）：discover, discover_batch
- 导出（1个）：export
- 推理增强（3个）：recommend, path, context ⭐ 新增
- 质量管理（2个）：analyze, evolve ⭐ 新增
"""

from .manage import (
    nisb_relation_create,
    nisb_relation_query,
    nisb_relation_delete,
    nisb_relation_stats
)

from .discover import (
    nisb_discover_relations,
    nisb_discover_relations_batch
)

from .export import nisb_export_relation_network

from .reasoning import (
    nisb_relation_recommend,
    nisb_relation_path,
    nisb_relation_context
)

from .quality import (
    nisb_relation_analyze,
    nisb_relation_evolve
)

__all__ = [
    # 基础管理
    'nisb_relation_create',
    'nisb_relation_query',
    'nisb_relation_delete',
    'nisb_relation_stats',
    
    # 自动发现
    'nisb_discover_relations',
    'nisb_discover_relations_batch',
    
    # 导出
    'nisb_export_relation_network',
    
    # 推理增强
    'nisb_relation_recommend',
    'nisb_relation_path',
    'nisb_relation_context',
    
    # 质量管理
    'nisb_relation_analyze',
    'nisb_relation_evolve'
]

