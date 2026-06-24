#!/usr/bin/env python3
"""
NISB Phase 5.0 实体管理系统
✅ 零外部依赖版本
✅ 仅使用Python标准库
"""

from .concept import (
    nisb_concept_create,
    nisb_concept_search,
    nisb_concept_annotate,
    nisb_concept_relate
)

from .book import (
    nisb_book_create,
    nisb_book_search
)

from .author import (
    nisb_author_create,
    nisb_author_search
)

from .topic import (
    nisb_topic_create,
    nisb_topic_search
)

from .search_engine import (
    nisb_entity_search,
    nisb_entity_network,
    nisb_entity_search_personalized
)

from .relationship_miner import (
    nisb_mine_implicit_relations,
    nisb_auto_link_entities
)

__all__ = [
    'nisb_concept_create',
    'nisb_concept_search',
    'nisb_concept_annotate',
    'nisb_concept_relate',
    'nisb_book_create',
    'nisb_book_search',
    'nisb_author_create',
    'nisb_author_search',
    'nisb_topic_create',
    'nisb_topic_search',
    'nisb_entity_search',
    'nisb_entity_network',
    'nisb_entity_search_personalized',
    'nisb_mine_implicit_relations',
    'nisb_auto_link_entities',
]

