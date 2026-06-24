#!/usr/bin/env python3
"""
nisb_llm_call
- 用于前端翻译 Gate（把 system_prompt + user_prompt 交给 OpenAI 模型执行）
- 生产保护：并发闸门（避免小 VPS 被翻译请求压垮导致 502）
返回：
  - success: {"status":"success","response":"...","model":"gpt-4o-mini"}
  - error:   {"status":"error","message":"..."}
"""

from __future__ import annotations

import sys
import threading
from typing import Any, Dict

sys.path.insert(0, "/srv")

from core.user_context import auto_user_context
from tools.chat.models.openai import OpenAIModel

# 小 VPS 建议：翻译最多同时跑 2 个（你可按 CPU/内存调成 1）
_LLM_TRANSLATE_SEM = threading.BoundedSemaphore(2)


def _as_str(x: Any) -> str:
    try:
        return str(x) if x is not None else ""
    except Exception:
        return ""


def _clamp_int(x: Any, default: int, lo: int, hi: int) -> int:
    try:
        v = int(x)
    except Exception:
        v = int(default)
    if v < lo:
        return lo
    if v > hi:
        return hi
    return v


@auto_user_context
def nisb_llm_call(args: dict) -> dict:
    """
    入参（与前端 ChatPanel.vue 对齐）：
      - model: str，默认 gpt-4o-mini
      - system_prompt: str（必填）
      - user_prompt: str（必填）
      - max_tokens: int，默认 256（翻译建议不要太大）
      - temperature: float，默认 0.2（翻译建议偏低）
    出参：
      - response: str
    """
    if not isinstance(args, dict):
        return {"status": "error", "message": "args 必须是 object"}

    model = _as_str(args.get("model") or "gpt-4o-mini").strip() or "gpt-4o-mini"
    system_prompt = _as_str(args.get("system_prompt")).strip()
    user_prompt = _as_str(args.get("user_prompt")).strip()

    if not system_prompt:
        return {"status": "error", "message": "system_prompt 不能为空"}
    if not user_prompt:
        return {"status": "error", "message": "user_prompt 不能为空"}

    max_tokens = _clamp_int(args.get("max_tokens"), default=256, lo=16, hi=4096)

    try:
        temperature = float(args.get("temperature", 0.2))
    except Exception:
        temperature = 0.2
    if temperature < 0:
        temperature = 0.0
    if temperature > 1.5:
        temperature = 1.5

    acquired = _LLM_TRANSLATE_SEM.acquire(timeout=20)
    if not acquired:
        return {
            "status": "error",
            "message": "系统繁忙：翻译并发已满，请稍后重试",
        }

    try:
        ai_model = OpenAIModel(model=model)

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        out = ai_model.chat(messages, temperature=temperature, max_tokens=max_tokens)

        response_text = out if isinstance(out, str) else _as_str(out)
        response_text = response_text.strip()

        if not response_text:
            return {"status": "error", "message": "LLM 返回空响应"}

        return {"status": "success", "response": response_text, "model": model}

    except Exception as e:
        return {"status": "error", "message": f"LLM 调用失败: {e}"}

    finally:
        try:
            _LLM_TRANSLATE_SEM.release()
        except Exception:
            pass


__all__ = ["nisb_llm_call"]

