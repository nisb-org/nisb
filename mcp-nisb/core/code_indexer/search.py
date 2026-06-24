#!/usr/bin/env python3
"""
基于 embedding 的代码检索：
- search_code_by_text(query): 文本 → 文件/符号列表
- search_code_by_symbol(name): 名称 → 符号列表
"""

from pathlib import Path
from typing import List, Dict, Any
import math

from core.openai_utils import get_embedding
from .index_store import get_code_index_dir, read_jsonl


def cosine_sim(a: list, b: list) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def search_code_by_text(query: str, top_k: int = 8) -> Dict[str, Any]:
    """
    在文件级 + 符号级索引中检索与 query 最相关的若干条记录
    """
    index_dir = get_code_index_dir()
    file_index_path = index_dir / "code_index_files.jsonl"
    symbol_index_path = index_dir / "code_index_symbols.jsonl"

    file_records = read_jsonl(file_index_path)
    symbol_records = read_jsonl(symbol_index_path)

    if not file_records and not symbol_records:
        return {
            "status": "error",
            "message": f"代码索引不存在，请先运行 nisb_code_build_index",
            "files": [],
            "symbols": [],
        }

    q_emb = get_embedding(query)

    # 文件级
    file_scores = []
    for rec in file_records:
        sim = cosine_sim(q_emb, rec.get("embedding") or [])
        file_scores.append((sim, rec))
    file_scores.sort(key=lambda x: x[0], reverse=True)
    top_files = [
        {
            "path": r["path"],
            "summary": r.get("summary", ""),
            "score": float(s),
        }
        for s, r in file_scores[:top_k]
    ]

    # 符号级
    symbol_scores = []
    for rec in symbol_records:
        sim = cosine_sim(q_emb, rec.get("embedding") or [])
        symbol_scores.append((sim, rec))
    symbol_scores.sort(key=lambda x: x[0], reverse=True)
    top_symbols = [
        {
            "path": r["path"],
            "kind": r.get("kind"),
            "name": r.get("name"),
            "signature": r.get("signature"),
            "summary": r.get("summary", ""),
            "start_line": r.get("start_line"),
            "end_line": r.get("end_line"),
            "score": float(s),
        }
        for s, r in symbol_scores[:top_k]
    ]

    return {
        "status": "success",
        "message": "代码搜索完成",
        "files": top_files,
        "symbols": top_symbols,
    }


def search_code_by_symbol(name: str, top_k: int = 8) -> Dict[str, Any]:
    """
    仅按符号名称简单匹配（非 embedding）
    """
    index_dir = get_code_index_dir()
    symbol_index_path = index_dir / "code_index_symbols.jsonl"
    symbol_records = read_jsonl(symbol_index_path)

    if not symbol_records:
        return {
            "status": "error",
            "message": "符号索引不存在，请先运行 nisb_code_build_index",
            "symbols": [],
        }

    name_lower = name.lower()
    matches = []
    for rec in symbol_records:
        sym_name = (rec.get("name") or "").lower()
        if name_lower in sym_name:
            matches.append(rec)

    matches = matches[:top_k]

    return {
        "status": "success",
        "message": "符号搜索完成",
        "symbols": matches,
    }

