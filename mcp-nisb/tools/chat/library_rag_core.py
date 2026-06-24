#!/usr/bin/env python3
"""
库级 RAG 核心业务逻辑：

- retrieve_library_contexts: 基于库向量索引 + BM25 返回最相关的 chunk 上下文列表
- answer_with_library_context: 在上述基础上调用 LLM，生成回答
"""

from __future__ import annotations

import os
import sqlite3
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from tools.doc.doc_db_sqlite import get_doc_db_sqlite
from tools.doc.helpers import (
    SimpleBM25,
    reciprocal_rank_fusion,
    EMBEDDING_MODEL,
    EMBEDDING_DIM,
)
from core import openai_utils


@dataclass
class ContextItem:
    library_id: str
    doc_id: str
    filename: str
    chunk_id: int
    text: str
    score: float


def _load_chunks_with_embeddings(
    base_path: str,
    library_ids: List[str],
) -> Tuple[List[str], List[ContextItem], np.ndarray]:
    corpus_texts: List[str] = []
    context_meta: List[ContextItem] = []
    embeddings_list: List[np.ndarray] = []

    for lib_id in library_ids:
        db = get_doc_db_sqlite(user_base_path=base_path, library_id=lib_id)
        db_path = Path(db.db_path)
        if not db_path.exists():
            continue

        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT d.library_id, d.doc_id, d.filename,
                   c.chunk_id, c.text,
                   e.embedding, e.embedding_dim
            FROM chunks AS c
            JOIN documents AS d ON c.doc_id = d.doc_id
            JOIN embeddings AS e
              ON c.doc_id = e.doc_id AND c.chunk_id = e.chunk_id
            WHERE d.library_id = ?
            ORDER BY d.doc_id, c.chunk_id
            """,
            (lib_id,),
        )
        rows = cursor.fetchall()
        conn.close()

        for (library_id, doc_id, filename, chunk_id, text, embedding_blob, dim) in rows:
            if not text or not embedding_blob:
                continue
            vec = np.frombuffer(embedding_blob, dtype="float32")
            if vec.size != dim:
                continue

            corpus_texts.append(text)
            context_meta.append(
                ContextItem(
                    library_id=str(library_id),
                    doc_id=str(doc_id),
                    filename=str(filename),
                    chunk_id=int(chunk_id),
                    text=str(text),
                    score=0.0,
                )
            )
            embeddings_list.append(vec)

    if not embeddings_list:
        return [], [], np.zeros((0, EMBEDDING_DIM), dtype="float32")

    emb_matrix = np.vstack(embeddings_list).astype("float32")
    return corpus_texts, context_meta, emb_matrix


def _rank_with_bm25_and_vectors(query: str, corpus_texts: List[str], emb_matrix: np.ndarray) -> List[int]:
    n = len(corpus_texts)
    if n == 0:
        return []

    bm25 = SimpleBM25(corpus_texts)
    bm25_scores = bm25.get_scores(query)
    bm25_ranking = sorted(range(n), key=lambda i: bm25_scores[i], reverse=True)

    query_vecs = openai_utils.get_embeddings([query], model=EMBEDDING_MODEL)
    query_vec = np.array(query_vecs[0], dtype="float32")
    if query_vec.shape[0] != emb_matrix.shape[1]:
        return bm25_ranking

    doc_norms = np.linalg.norm(emb_matrix, axis=1) + 1e-8
    q_norm = float(np.linalg.norm(query_vec) + 1e-8)
    sims = (emb_matrix @ query_vec) / (doc_norms * q_norm)

    vec_ranking = sorted(range(n), key=lambda i: float(sims[i]), reverse=True)

    fused = reciprocal_rank_fusion(rankings=[bm25_ranking, vec_ranking], k=60)
    return [idx for idx, _score in fused]


def retrieve_library_contexts(
    base_path: str,
    library_ids: List[str],
    query: str,
    top_k: int = 8,
    max_chunk_chars: int = 800,
) -> List[Dict[str, Any]]:
    corpus_texts, context_meta, emb_matrix = _load_chunks_with_embeddings(
        base_path=base_path,
        library_ids=library_ids,
    )
    if not corpus_texts:
        return []

    ranked_indices = _rank_with_bm25_and_vectors(
        query=query,
        corpus_texts=corpus_texts,
        emb_matrix=emb_matrix,
    )

    results: List[Dict[str, Any]] = []
    for rank_pos, idx in enumerate(ranked_indices[:top_k]):
        meta = context_meta[idx]
        text = meta.text
        if len(text) > max_chunk_chars:
            text = text[: max_chunk_chars - 3] + "..."

        item = ContextItem(
            library_id=meta.library_id,
            doc_id=meta.doc_id,
            filename=meta.filename,
            chunk_id=meta.chunk_id,
            text=text,
            score=float(1.0 / (rank_pos + 1)),  # 越靠前分数越高（轻量可用）
        )
        results.append(asdict(item))

    return results


def answer_with_library_context(
    base_path: str,
    conversation_meta: Optional[Dict[str, Any]],
    user_message: str,
    library_ids: List[str],
    top_k: int = 8,
    model: Optional[str] = None,
) -> Dict[str, Any]:
    if model is None:
        model = os.environ.get("NISB_CHAT_MODEL", "gpt-4o-mini")

    contexts = retrieve_library_contexts(
        base_path=base_path,
        library_ids=library_ids,
        query=user_message,
        top_k=top_k,
    )

    context_blocks = []
    for idx, ctx in enumerate(contexts, start=1):
        block = (
            f"[{idx}] 库: {ctx['library_id']} | 文档: {ctx['filename']} "
            f"(doc_id={ctx['doc_id']}, chunk={ctx['chunk_id']})\n"
            f"{ctx['text']}\n"
        )
        context_blocks.append(block)

    joined_contexts = "\n\n".join(context_blocks) if context_blocks else "（当前没有可用的库上下文）"

    system_prompt = (
        "你是 NISB 的知识助手，回答用户问题时要优先参考用户知识库中的内容。\n"
        "下面是为本次问题在用户库中检索到的相关片段，每个片段前有编号 [n]：\n\n"
        f"{joined_contexts}\n\n"
        "回答规则：\n"
        "1. 尽量基于上述片段作答；片段没有明确答案时，可简要补充，但避免过度推测。\n"
        "2. 如出现矛盾，请指出矛盾来源。\n"
    )

    answer_text = openai_utils.chat_completion(
        model=model,
        system_prompt=system_prompt,
        user_message=user_message,
    )

    return {"answer": answer_text, "contexts": contexts, "model": model}

