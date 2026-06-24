#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Concept Extractor Base & Factory

统一抽象接口 + 工厂函数：
- ConceptExtractor: 基类
- get_concept_extractor(base_path, language, backend): 根据语言/策略选择 backend
"""

import sys
from typing import List

sys.path.insert(0, '/srv')


class ConceptExtractor:
    """抽象基类：所有概念抽取 backend 的统一接口"""

    def __init__(self, base_path: str):
        self.base_path = base_path

    def extract(self, text: str, top_k: int = 10) -> List[str]:
        """输入文本，输出候选概念列表"""
        raise NotImplementedError


def get_concept_extractor(
    base_path: str,                # ⭐ 修复：显式传入 base_path，不依赖 user_ctx
    language: str = "auto",        # "zh" | "en" | "multi" | "auto"
    backend: str  = "auto",        # "auto" | "jieba" | "llm_gpt4o_mini" | ...
) -> ConceptExtractor:
    """
    工厂方法：根据 base_path + language + backend 返回合适的 ConceptExtractor 实例。

    优先级：
    1. backend 显式指定时，按 backend 走
    2. backend="auto" 时，根据 language 做默认路由
    3. 都是 "auto" 时，默认用中文 jieba（向后兼容）
    """
    from .backend_jieba import JiebaConceptExtractor
    from .backend_llm import LLMConceptExtractor

    # 1. backend 显式指定
    if backend == "jieba":
        return JiebaConceptExtractor(base_path)
    
    if backend.startswith("llm_"):
        # 规范：llm_gpt4o_mini → 模型名 "gpt-4o-mini"
        model = "gpt-4o-mini" if backend == "llm_gpt4o_mini" else backend.split("llm_")[1]
        return LLMConceptExtractor(base_path, model=model)

    # 2. backend = "auto" 时，根据 language 路由
    if language == "zh":
        return JiebaConceptExtractor(base_path)
    # 未来：language=="en" → English backend
    # 未来：language=="multi" → SentencePiece backend

    # 3. 默认兜底：jieba（向后兼容）
    return JiebaConceptExtractor(base_path)
