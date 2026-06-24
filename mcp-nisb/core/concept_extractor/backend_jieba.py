#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Jieba-based Concept Extractor (中文)
复用 core.storage._extract_concepts_from_text
"""

import sys
from typing import List
sys.path.insert(0, '/srv')

from .base import ConceptExtractor
from core.storage import _extract_concepts_from_text


class JiebaConceptExtractor(ConceptExtractor):
    """中文：基于 jieba 的轻量概念抽取实现"""

    def extract(self, text: str, top_k: int = 10) -> List[str]:
        return _extract_concepts_from_text(text, top_k=top_k, base_path=self.base_path)
