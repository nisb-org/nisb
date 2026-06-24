#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Chunked faithful translation tool for NISB (MCP)
- nisb_util_translate_chunks: split long text into chunks and translate faithfully
"""

from __future__ import annotations

import os
import re
from typing import Any, Dict, List

from core.openai_utils import call_llm

MODEL_MAP = {
    "mini": "gpt-4o-mini",
    "gpt-4o-mini": "gpt-4o-mini",
    "gpt-4o": "gpt-4o",
    "o1-mini": "o1-mini",
}


def _get_str(args: Dict[str, Any], key: str, default: str = "") -> str:
    v = args.get(key)
    if v is None:
        return default
    s = str(v).strip()
    return s if s else default


def _split_paragraphs(text: str) -> List[str]:
    t = (text or "").replace("\r\n", "\n").strip()
    t = re.sub(r"\n{3,}", "\n\n", t)
    if not t:
        return []
    parts = [p.strip() for p in t.split("\n\n")]
    return [p for p in parts if p]


def _chunk_by_char(paragraphs: List[str], chunk_chars: int) -> List[str]:
    chunks: List[str] = []
    buf: List[str] = []
    size = 0

    for p in paragraphs:
        # +2 for the \n\n joiner
        add = len(p) + (2 if buf else 0)
        if buf and size + add > chunk_chars:
            chunks.append("\n\n".join(buf).strip())
            buf = [p]
            size = len(p)
        else:
            buf.append(p)
            size += add

    if buf:
        chunks.append("\n\n".join(buf).strip())
    return [c for c in chunks if c]


def nisb_util_translate_chunks(args: Dict[str, Any]) -> Dict[str, Any]:
    text = _get_str(args, "text", "")
    if not text:
        return {"status": "error", "message": "text is required"}

    target_language = _get_str(args, "target_language", "zh-CN")
    backend = _get_str(args, "backend", "mini")

    # 前端默认：chunk_chars=900 左右会更稳
    chunk_chars = int(args.get("chunk_chars", 900) or 900)
    max_chars = int(args.get("max_chars", 12000) or 12000)

    if len(text) > max_chars:
        text = text[:max_chars]

    env_model = os.environ.get("NISB_TRANSLATE_MODEL")
    model = env_model if env_model else MODEL_MAP.get(backend, "gpt-4o-mini")

    paragraphs = _split_paragraphs(text)
    chunks = _chunk_by_char(paragraphs, max(200, chunk_chars))

    system_prompt = (
        f"你是一个严谨的翻译助手。请将用户提供的文本完整、准确地翻译为 {target_language}。\n"
        "要求：\n"
        "1) 不要总结、不要改写、不要省略任何句子。\n"
        "2) 保持原有段落结构。\n"
        "3) 不要添加任何解释或额外说明。\n"
        "4) 只输出译文。\n"
    )

    translated_chunks: List[str] = []
    try:
        for idx, c in enumerate(chunks):
            user_prompt = f"（第 {idx+1}/{len(chunks)} 段）请翻译为 {target_language}：\n\n{c}"
            out = call_llm(
                model=model,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                response_format="text",
            )
            translated_chunks.append((out or "").strip())
    except Exception as e:
        return {"status": "error", "message": f"translate_chunks failed: {e!r}"}

    full = "\n\n".join([x for x in translated_chunks if x]).strip()

    return {
        "status": "success",
        "target_language": target_language,
        "backend": backend,
        "model": model,
        "chunk_chars": chunk_chars,
        "translated_text": full,
        "chunks": [{"index": i, "text": chunks[i]} for i in range(len(chunks))],
    }

