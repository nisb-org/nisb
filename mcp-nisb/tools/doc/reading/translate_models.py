#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import os
from typing import Tuple, List

from core.openai_utils import call_llm

try:
  from tools.chat.models.anthropic import AnthropicModel  # type: ignore
except Exception:
  AnthropicModel = None  # type: ignore

from .translate_guard import (
  _protect_nisb_uris,
  _restore_nisb_uris,
  _repair_nisb_uris_by_source,
  _split_text_for_translation_preserve_nisb,
)

MODEL_MAP = {
  "mini": "gpt-4o-mini",
  "gpt-4o-mini": "gpt-4o-mini",
  "gpt-4o": "gpt-4o",
  "o1-mini": "o1-mini",
  "haiku": "claude-3-5-haiku-20241022",
  "claude-3-5-haiku": "claude-3-5-haiku-20241022",
  "claude-3-5-haiku-20241022": "claude-3-5-haiku-20241022",
  "haiku-4-5": "claude-haiku-4-5-20251001",
  "claude-haiku-4-5": "claude-haiku-4-5-20251001",
  "claude-haiku-4-5-20251001": "claude-haiku-4-5-20251001",
}


def _call_translate_model(
  backend: str,
  target_language: str,
  span_text: str,
) -> Tuple[str, str, str]:
  system_prompt = (
    f"你是一个严谨的翻译助手。请将用户提供的文本完整、准确地翻译为 {target_language}，"
    "保持原有段落结构，不要添加解释或额外说明。\n"
    "重要约束：\n"
    "1) 保留所有 Markdown/HTML 结构。\n"
    "2) 不要改写任何链接/URI（尤其是 nisb://...）。\n"
    "3) 文本中若出现形如 __NISB_URI_0000__ 的占位符，必须原样输出，不得翻译、拆分或改动。\n"
  )

  b = (backend or "mini").strip()
  model = os.environ.get("NISB_TRANSLATE_MODEL") or MODEL_MAP.get(b, "gpt-4o-mini")

  max_tokens = 8192
  if b in ("haiku-4-5", "claude-haiku-4-5", "claude-haiku-4-5-20251001"):
    max_tokens = 64000

  is_anthropic = b.startswith("haiku") or b.startswith("claude-")

  chunk_size = 8000
  chunks = _split_text_for_translation_preserve_nisb(span_text, chunk_size=chunk_size)
  translated_chunks: List[str] = []

  for chunk in chunks:
    protected_chunk, mapping = _protect_nisb_uris(chunk)
    user_prompt = f"请翻译为 {target_language}：\n\n{protected_chunk}"

    if is_anthropic:
      if AnthropicModel is None:
        raise Exception("AnthropicModel not available (missing ANTHROPIC deps/config)")
      m = AnthropicModel(model=model)
      out = m.chat(
        messages=[
          {"role": "system", "content": system_prompt},
          {"role": "user", "content": user_prompt},
        ],
        temperature=0.2,
        max_tokens=max_tokens,
        tools=None,
      )
      if isinstance(out, str):
        part = (out or "").strip()
      else:
        part = (getattr(out, "content", "") or "").strip()
    else:
      out = call_llm(
        model,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        response_format="text",
      )
      part = (out or "").strip()

    restored = _restore_nisb_uris(part, mapping)
    repaired = _repair_nisb_uris_by_source(chunk, restored)
    translated_chunks.append(repaired)

  provider = "anthropic" if is_anthropic else "openai"
  return "\n".join(translated_chunks), provider, model

