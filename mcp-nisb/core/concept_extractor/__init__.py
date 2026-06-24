#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Concept Extractor Subsystem - NISB Core

对外只暴露 get_concept_extractor()，内部可以挂接多个 backend：
- JiebaConceptExtractor：中文（jieba）
- LLMConceptExtractor：LLM（gpt-4o-mini 等）
未来可扩展：
- EnglishSpaCyConceptExtractor：英文
- SentencePieceConceptExtractor：多语言
"""

from .base import ConceptExtractor, get_concept_extractor

__all__ = ["ConceptExtractor", "get_concept_extractor"]
