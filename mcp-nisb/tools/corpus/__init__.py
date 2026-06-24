#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Corpus工具模块
Phase 2.9.5: 基础入库+查询
Phase 2.9.6: Embeddings语义搜索
Phase 2.9.7: 批量入库+智能推荐+创作测试
Phase 3.8.0: 优化现有工具（usage_hint + doctor健康检查）
"""

# 原有4个工具
from .ingest import nisb_corpus_ingest
from .query import nisb_corpus_query
from .semantic_search import nisb_corpus_semantic_search
from .enrich import nisb_corpus_enrich

# Phase 2.9.7 新增7个工具
from .batch_ingest import nisb_corpus_batch_ingest
from .stats import nisb_corpus_stats, nisb_corpus_doctor  # ⭐⭐⭐ Phase 3.8新增doctor
from .recall import nisb_corpus_recall
from .recommend import nisb_corpus_recommend
from .export import nisb_corpus_export
from .test_creation import nisb_corpus_test_creation
from .compare_baseline import nisb_corpus_compare_baseline

__all__ = [
    # 原有4个
    'nisb_corpus_ingest',
    'nisb_corpus_query',
    'nisb_corpus_semantic_search',
    'nisb_corpus_enrich',
    
    # Phase 2.9.7 新增7个
    'nisb_corpus_batch_ingest',
    'nisb_corpus_stats',
    'nisb_corpus_recall',
    'nisb_corpus_recommend',
    'nisb_corpus_export',
    'nisb_corpus_test_creation',
    'nisb_corpus_compare_baseline',
    
    # ⭐⭐⭐ Phase 3.8 新增
    'nisb_corpus_doctor',
]

