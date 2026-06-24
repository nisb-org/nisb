#!/usr/bin/env python3

import json
from pathlib import Path
from typing import Any, Dict, List

import numpy as np

from core.user_context import auto_user_context, get_user_ctx
from core.openai_utils import get_embedding

from .common import (
    clamp_limit,
    cosine_similarity,
    error_response,
    ok_response,
    scan_dir_files,
    JSON_EXTENSIONS,
)


@auto_user_context
def nisb_search_semantic(args: dict) -> dict:
    user_ctx = get_user_ctx()
    query = str(args.get("query", "")).strip()
    top_k = clamp_limit(args.get("top_k", 5), default=5)
    search_type = str(args.get("search_type", "all")).strip() or "all"

    if not query:
        return error_response("❌ query 不能为空")

    try:
        query_embedding = np.array(get_embedding(query))
    except Exception as e:
        return error_response(f"❌ 向量化失败: {str(e)}")

    results: List[Dict[str, Any]] = []
    base_path = Path(user_ctx.base)

    if search_type in ["notes", "all"]:
        notes_dir = base_path / "storage/raw/quick_notes"
        if notes_dir.exists():
            for notes_file in notes_dir.glob("*.jsonl"):
                try:
                    with open(notes_file, "r", encoding="utf-8") as f:
                        for line in f:
                            try:
                                note = json.loads(line)
                                emb = note.get("embedding")
                                if not emb:
                                    continue
                                similarity = cosine_similarity(query_embedding, np.array(emb))
                                results.append({
                                    "type": "note",
                                    "id": note.get("id"),
                                    "content": str(note.get("content", ""))[:200],
                                    "timestamp": note.get("timestamp", ""),
                                    "similarity": round(float(similarity), 6),
                                    "score": round(float(similarity) * 100.0, 4)
                                })
                            except Exception:
                                continue
                except Exception:
                    continue

    if search_type in ["conversations", "all"]:
        conversations_root = base_path / "web_interactions" / "conversations"
        if conversations_root.exists():
            for year_dir in conversations_root.iterdir():
                if not year_dir.is_dir():
                    continue
                for month_dir in year_dir.iterdir():
                    if not month_dir.is_dir():
                        continue
                    for conv_dir in month_dir.iterdir():
                        if not conv_dir.is_dir() or not conv_dir.name.startswith("conv_"):
                            continue
                        turns_file = conv_dir / "turns.jsonl"
                        if not turns_file.exists():
                            continue
                        try:
                            with open(turns_file, "r", encoding="utf-8") as f:
                                for line in f:
                                    try:
                                        turn = json.loads(line)
                                        emb = turn.get("embedding")
                                        if not emb:
                                            continue
                                        similarity = cosine_similarity(query_embedding, np.array(emb))
                                        results.append({
                                            "type": "conversation",
                                            "conv_id": conv_dir.name,
                                            "role": turn.get("turn_type"),
                                            "content": str(turn.get("content", ""))[:200],
                                            "timestamp": turn.get("timestamp", ""),
                                            "similarity": round(float(similarity), 6),
                                            "score": round(float(similarity) * 100.0, 4)
                                        })
                                    except Exception:
                                        continue
                        except Exception:
                            continue

    if search_type in ["libraries", "all"]:
        libraries_root = base_path / "libraries"
        if libraries_root.exists():
            for lib_dir in libraries_root.iterdir():
                if not lib_dir.is_dir():
                    continue
                library_name = lib_dir.name
                meta_file = lib_dir / "library.json"
                if meta_file.exists():
                    try:
                        with open(meta_file, "r", encoding="utf-8") as f:
                            meta = json.load(f)
                        library_name = meta.get("library_name", lib_dir.name)
                    except Exception:
                        pass

                docs_dir = lib_dir / "docs"
                if docs_dir.exists():
                    for doc_file in scan_dir_files(docs_dir, recursive=True, suffixes=JSON_EXTENSIONS):
                        try:
                            with open(doc_file, "r", encoding="utf-8") as f:
                                doc = json.load(f)
                            emb = doc.get("embedding")
                            if not emb:
                                continue
                            similarity = cosine_similarity(query_embedding, np.array(emb))
                            results.append({
                                "type": "library_doc",
                                "library_id": lib_dir.name,
                                "library_name": library_name,
                                "doc_id": doc.get("id", doc_file.stem),
                                "title": doc.get("title", doc_file.stem),
                                "content": str(doc.get("content", ""))[:200],
                                "similarity": round(float(similarity), 6),
                                "score": round(float(similarity) * 100.0, 4)
                            })
                        except Exception:
                            continue

    results.sort(key=lambda x: x.get("similarity", 0.0), reverse=True)
    top_results = results[:top_k]
    response_text = f"🔍 语义搜索「{query}」，找到 {len(top_results)} 条结果。"
    data = {
        "query": query,
        "results": top_results,
        "total": len(top_results)
    }
    return ok_response(
        response_text=response_text,
        data=data,
        legacy_query=query,
        legacy_results=top_results,
        legacy_total=len(top_results)
    )

