#!/usr/bin/env python3
"""
NISB Code Indexer v0.1
阶段 1：只读索引 + 代码搜索（基于代码镜像目录）
"""

from .scanner import build_code_index
from .search import search_code_by_text, search_code_by_symbol

