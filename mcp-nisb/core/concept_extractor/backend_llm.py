#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LLM-based Concept Extractor - Production Ready v3
并发优化 + 128K 上下文支持
"""

import sys
import json
from typing import List
from concurrent.futures import ThreadPoolExecutor, as_completed
sys.path.insert(0, '/srv')

from .base import ConceptExtractor


class LLMConceptExtractor(ConceptExtractor):
    """基于 LLM（如 gpt-4o-mini）的概念抽取 backend"""

    def __init__(self, base_path: str, model: str = "gpt-4o-mini"):
        super().__init__(base_path)
        self.model = model

    def _extract_chunks_parallel(self, chunks: List[str], top_k: int) -> List[str]:
        """并发提取多个文本块的概念"""
        all_concepts = []
        
        with ThreadPoolExecutor(max_workers=min(len(chunks), 6)) as executor:
            future_to_idx = {
                executor.submit(self._extract_chunk, chunk, top_k): i 
                for i, chunk in enumerate(chunks)
            }
            
            for future in as_completed(future_to_idx):
                idx = future_to_idx[future]
                try:
                    concepts = future.result()
                    print(f"[DEBUG concept_llm] 段 {idx+1}/{len(chunks)}: {len(concepts)} 个概念", file=sys.stderr)
                    all_concepts.extend(concepts)
                except Exception as e:
                    print(f"[ERROR concept_llm] 段 {idx+1} 失败: {e}", file=sys.stderr)
        
        return all_concepts

    def extract(self, text: str, top_k: int = 10) -> List[str]:
        """提取概念（并发优化 + 128K 上下文）"""
        from core.openai_utils import call_llm

        if not text or len(text.strip()) < 5:
            return []

        text_len = len(text)
        
        # 策略1：短文本
        if text_len <= 8000:
            return self._extract_chunk(text, top_k)
        
        # 策略2：中等文本，分段并发抽取
        elif text_len <= 64000:
            num_chunks = (text_len // 8000) + 1
            chunk_size = text_len // num_chunks
            print(f"[INFO concept_llm] 文本 {text_len} 字符，分 {num_chunks} 段并发抽取", file=sys.stderr)
            
            chunks = []
            for i in range(num_chunks):
                start = i * chunk_size
                end = start + chunk_size if i < num_chunks - 1 else text_len
                chunks.append(text[start:end])
            
            all_concepts = self._extract_chunks_parallel(chunks, top_k)
            return self._deduplicate(all_concepts, top_k)
        
        # 策略3：长文本，全文抽取
        elif text_len <= 192000:
            print(f"[INFO concept_llm] 文本 {text_len} 字符，使用全文抽取（128K 上下文）", file=sys.stderr)
            return self._extract_chunk(text, top_k)
        
        # 策略4：超长文本，首尾抽取
        else:
            print(f"[WARN concept_llm] 文本超长 {text_len} 字符，超出 128K 限制，使用首尾抽取", file=sys.stderr)
            head = text[:64000]
            tail = text[-64000:]
            concepts_head = self._extract_chunk(head, top_k // 2)
            concepts_tail = self._extract_chunk(tail, top_k // 2)
            return self._deduplicate(concepts_head + concepts_tail, top_k)

    def _extract_chunk(self, text: str, top_k: int) -> List[str]:
        """从单个文本块提取概念"""
        from core.openai_utils import call_llm
        
        prompt = """You are a knowledge graph builder for a personal second brain system (NISB).
Given the following text, extract at most """ + str(top_k) + """ key concepts that are useful for long-term knowledge organization.

Return ONLY a JSON object with a single field "concepts", which is a list of strings.
Each string is a short concept phrase in the original language.

Example:
{"concepts": ["Montessori education", "children's autonomy", "a priori synthetic judgment"]}

Text:
"""
        prompt += '"""'
        prompt += text
        prompt += '"""'
        
        try:
            raw = call_llm(self.model, prompt)
            return self._parse_concepts(raw, top_k)
        except Exception as e:
            print(f"[ERROR concept_llm] LLM 调用失败: {e}", file=sys.stderr)
            return []

    def _parse_concepts(self, raw: str, top_k: int) -> List[str]:
        """解析 LLM 返回的概念列表"""
        raw_cleaned = str(raw).strip()
        
        if not raw_cleaned:
            print(f"[WARN concept_llm] LLM 返回空响应", file=sys.stderr)
            return []
        
        backticks = '```'
        if raw_cleaned.startswith(backticks):
            lines = raw_cleaned.split("\n")
            if len(lines) >= 3:
                raw_cleaned = "\n".join(lines[1:-1])
        
        try:
            data = json.loads(raw_cleaned)
            concepts = data.get("concepts", [])
            return [c.strip() for c in concepts if isinstance(c, str) and len(c.strip()) >= 2][:top_k]
        except Exception as e:
            print(f"[WARN concept_llm] 解析失败: {e}", file=sys.stderr)
            print(f"[DEBUG concept_llm] 原始响应（前 300 字符）: {raw_cleaned[:300]}", file=sys.stderr)
            return []

    def _deduplicate(self, concepts: List[str], top_k: int) -> List[str]:
        """去重并保留 top-k"""
        seen = set()
        result = []
        for c in concepts:
            c_lower = c.lower()
            if c_lower not in seen:
                seen.add(c_lower)
                result.append(c)
        return result[:top_k]
