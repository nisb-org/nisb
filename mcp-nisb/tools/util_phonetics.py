#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Phonetics tool for NISB (MCP)
- nisb_util_phonetics: 给英文短语/句子生成国际音标风格的读音提示
"""

from __future__ import annotations

from typing import Any, Dict

from core.openai_utils import call_llm


def _get_str(args: Dict[str, Any], key: str, default: str = "") -> str:
    v = args.get(key)
    if v is None:
        return default
    s = str(v).strip()
    return s if s else default


def nisb_util_phonetics(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    输入一小段英文，返回简洁的音标/读音提示。
    仅用于划词场景，不追求严格词典级精确。
    """
    text = _get_str(args, "text", "")
    if not text:
        return {"status": "error", "message": "text is required"}

    max_chars = int(args.get("max_chars", 200) or 200)
    if len(text) > max_chars:
        text = text[:max_chars]

    # 只在主要由英文字母 + 常见符号构成时工作，避免对非英文乱出音标
    if not any(c.isalpha() for c in text):
        return {"status": "error", "message": "non_english_like_text"}

    # 直接复用你现有的 call_llm（默认 gpt-4o-mini）
    system_prompt = (
        "你是一个英语读音助手。用户会提供一小段英文单词或短句。"
        "请给出简洁的国际音标/读音提示，适合中级学习者。"
        "要求：\n"
        "1. 如果是一个或少数几个单词，按顺序列出，每个用 [word] /phonetic/ 格式。\n"
        "2. 如果是一小句，可以给出整句的大致音标或用空格分词后给出音标。\n"
        "3. 不要输出任何解释或中文翻译，只输出音标行本身。\n"
        "4. 不要使用 Markdown 代码块。\n"
    )
    user_prompt = f"英文文本：\n{text}\n\n请按上述要求输出音标提示。"

    try:
        phon = call_llm(
            model="gpt-4o-mini",
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            response_format="text",
        )
        return {
            "status": "success",
            "phonetics": (phon or "").strip(),
        }
    except Exception as e:
        return {"status": "error", "message": f"phonetics failed: {e!r}"}

