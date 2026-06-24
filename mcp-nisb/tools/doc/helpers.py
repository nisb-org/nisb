#!/usr/bin/env python3
"""工具函数"""
import os
import psutil
import numpy as np
from collections import defaultdict, Counter
from typing import Dict, List, Tuple, Any

# 统一配置：文档分析使用的 LLM 模型
# 默认使用 gpt-4o-mini，可通过环境变量 NISB_DOC_LLM_MODEL 覆盖
DOC_LLM_MODEL = os.environ.get("NISB_DOC_LLM_MODEL", "gpt-4o-mini")

EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIM = 1536
EMBEDDING_BATCH_SIZE = 100
BATCH_DELAY_SECONDS = 0.2
CHUNK_SIZE = 400
CHUNK_OVERLAP = 100
MAX_RESULTS = 50
MAX_FILE_SIZE = 100 * 1024 * 1024


def _limit_resources():
    try:
        p = psutil.Process()
        p.cpu_affinity([0])
        p.nice(10)
    except Exception:
        pass


def _chunk_text_with_ranges(
    text: str,
    chunk_size: int = CHUNK_SIZE,
    overlap: int = CHUNK_OVERLAP
) -> List[Dict[str, Any]]:
    if not text or len(text.strip()) < 10:
        t = str(text or "").strip()
        if not t:
            return []
        start = str(text or "").find(t)
        if start < 0:
            start = 0
        return [{
            "text": t,
            "char_start": start,
            "char_end": start + len(t),
        }]

    if chunk_size <= 0 or overlap < 0:
        chunk_size, overlap = 400, 100
    if overlap >= chunk_size:
        overlap = chunk_size // 4

    chunks: List[Dict[str, Any]] = []
    start = 0
    text_len = len(text)

    while start < text_len:
        end = min(start + chunk_size, text_len)

        if end < text_len and end - start > 20:
            for i in range(min(end - 1, text_len - 1), max(start + 10, end - 50), -1):
                if i < text_len and text[i] in '.!?。！？\n':
                    end = i + 1
                    break

        if start < end:
            raw = text[start:end]
            chunk = raw.strip()
            if chunk:
                left_trim = len(raw) - len(raw.lstrip())
                right_trim = len(raw) - len(raw.rstrip())

                char_start = start + left_trim
                char_end = end - right_trim

                if char_end <= char_start:
                    char_start = start
                    char_end = min(end, start + len(chunk))

                chunks.append({
                    "text": chunk,
                    "char_start": int(char_start),
                    "char_end": int(char_end),
                })

        new_start = end - overlap
        if new_start <= start:
            new_start = start + max(1, chunk_size // 2)
        start = new_start

    if chunks:
        return chunks

    t = str(text or "").strip()
    if not t:
        return []
    s = str(text or "").find(t)
    if s < 0:
        s = 0
    return [{
        "text": t,
        "char_start": s,
        "char_end": s + len(t),
    }]


def _chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> List[str]:
    return [str(item.get("text") or "") for item in _chunk_text_with_ranges(text, chunk_size, overlap)]


class SimpleBM25:
    def __init__(self, corpus: List[str], k1: float = 1.5, b: float = 0.75):
        self.k1, self.b, self.corpus = k1, b, corpus
        self.corpus_size = len(corpus)
        self.avgdl = sum(len(doc.split()) for doc in corpus) / self.corpus_size if self.corpus_size > 0 else 0
        self.idf = self._compute_idf()

    def _compute_idf(self) -> Dict[str, float]:
        df = defaultdict(int)
        for doc in self.corpus:
            for word in set(doc.lower().split()):
                df[word] += 1
        return {word: np.log((self.corpus_size - freq + 0.5) / (freq + 0.5) + 1.0) for word, freq in df.items()}

    def get_scores(self, query: str) -> List[float]:
        query_words = query.lower().split()
        scores = []
        for doc in self.corpus:
            doc_words = doc.lower().split()
            doc_len, score = len(doc_words), 0.0
            word_freqs = Counter(doc_words)
            for word in query_words:
                if word in self.idf:
                    freq, idf = word_freqs.get(word, 0), self.idf[word]
                    score += idf * (freq * (self.k1 + 1)) / (freq + self.k1 * (1 - self.b + self.b * doc_len / self.avgdl))
            scores.append(score)
        return scores


def reciprocal_rank_fusion(rankings: List[List], k: int = 60) -> List[Tuple]:
    rrf_scores = defaultdict(float)
    for ranking in rankings:
        for rank, doc_idx in enumerate(ranking, start=1):
            rrf_scores[doc_idx] += 1.0 / (k + rank)
    return sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)

