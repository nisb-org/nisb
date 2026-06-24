#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Universal translate tool for NISB (MCP)
- nisb_util_translate: translate arbitrary text to target_language (default zh-CN)
"""

from __future__ import annotations

import os
from typing import Any, Dict

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


def nisb_util_translate(args: Dict[str, Any]) -> Dict[str, Any]:
  text = _get_str(args, "text", "")
  if not text:
    return {"status": "error", "message": "text is required"}

  target_language = _get_str(args, "target_language", "zh-CN")
  backend = _get_str(args, "backend", "mini")
  mode = _get_str(args, "mode", "plain")  # plain | dictionary

  max_chars = int(args.get("max_chars", 2000) or 2000)
  if len(text) > max_chars:
    text = text[:max_chars]

  env_model = os.environ.get("NISB_TRANSLATE_MODEL")
  model = env_model if env_model else MODEL_MAP.get(backend, "gpt-4o-mini")

  # ============ plain 模式：保持原行为 ============
  if mode != "dictionary":
    system_prompt = (
      f"你是一个严谨的翻译助手。请将用户提供的文本完整、准确地翻译为 {target_language}，"
      "保持原有段落结构，不要添加解释或额外说明。"
    )
    user_prompt = f"请翻译为 {target_language}：\n\n{text}"

    try:
      translated = call_llm(
        model=model,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        response_format="text",
      )
      return {
        "status": "success",
        "target_language": target_language,
        "backend": backend,
        "model": model,
        "translated_text": (translated or "").strip(),
      }
    except Exception as e:
      return {"status": "error", "message": f"translate failed: {e!r}"}

  # ============ dictionary 模式：结构化输出 ============
  # ✅ 用三引号多行字符串，避免引号/转义错误 [web:178]
  system_prompt = f"""你是一个双语词典编辑。用户会提供一小段文本（可以是单词、短语、句子）。
请以 JSON 格式输出一个字典风格的解释，用于界面展示，不要包含额外字段：
{{
  "main": "核心通俗释义（使用目标语言）",
  "examples": [
    {{ "src": "原文例句", "trans": "例句译文（目标语言）" }}
  ],
  "notes": "补充说明（可选，目标语言，可为空字符串）"
}}
要求：
1. 所有解释和译文都使用目标语言 {target_language}。
2. 如果输入是一整句，可以把整句作为 main 的释义，并给出 1-2 个简短例句即可。
3. 一定要返回合法 JSON，不能包含注释或多余文本，不要使用 Markdown 代码块。
"""

  user_prompt = f"请以 JSON 格式给出上述结构：\n\n{text}"

  try:
    data = call_llm(
      model=model,
      system_prompt=system_prompt,
      user_prompt=user_prompt,
      response_format="json",
    )

    # data 可能是 dict 或 str（解析失败时），做兜底
    if not isinstance(data, dict):
      return {
        "status": "success",
        "target_language": target_language,
        "backend": backend,
        "model": model,
        "translated_text": (str(data) or "").strip(),
        "dict": None,
      }

    main = str(data.get("main") or "").strip()
    notes = str(data.get("notes") or "").strip()
    examples_raw = data.get("examples") or []
    examples = []
    if isinstance(examples_raw, list):
      for ex in examples_raw:
        if not isinstance(ex, dict):
          continue
        src = str(ex.get("src") or "").strip()
        trans = str(ex.get("trans") or "").strip()
        if src or trans:
          examples.append({"src": src, "trans": trans})

    translated_text = main or ""
    return {
      "status": "success",
      "target_language": target_language,
      "backend": backend,
      "model": model,
      "translated_text": translated_text,
      "dict": {
        "main": main,
        "examples": examples,
        "notes": notes,
      },
    }

  except Exception as e:
    return {"status": "error", "message": f"translate_dict failed: {e!r}"}

