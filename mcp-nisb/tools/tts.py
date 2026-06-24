#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TTS tools for NISB (MCP)
- nisb_tts_speak: text -> base64 audio (mp3 by default)
"""

from __future__ import annotations

import base64
import os
from typing import Any, Dict

from openai import OpenAI

_DEFAULT_MODEL = os.environ.get("NISB_TTS_MODEL", "gpt-4o-mini-tts")
_DEFAULT_VOICE = os.environ.get("NISB_TTS_VOICE", "alloy")
_DEFAULT_FORMAT = os.environ.get("NISB_TTS_FORMAT", "mp3")


def _get_str(args: Dict[str, Any], key: str, default: str = "") -> str:
  v = args.get(key)
  if v is None:
    return default
  s = str(v).strip()
  return s if s else default


def nisb_tts_speak(args: Dict[str, Any]) -> Dict[str, Any]:
  text = _get_str(args, "text", "")
  if not text:
    return {"status": "error", "message": "text is required"}

  voice = _get_str(args, "voice", _DEFAULT_VOICE)
  model = _get_str(args, "model", _DEFAULT_MODEL)
  fmt = _get_str(args, "format", _DEFAULT_FORMAT)

  max_chars = int(args.get("max_chars", 1500) or 1500)
  if len(text) > max_chars:
    text = text[:max_chars]

  try:
    client = OpenAI()
    resp = client.audio.speech.create(
      model=model,
      voice=voice,
      input=text,
      response_format=fmt,
    )
    audio_bytes = resp.read() if hasattr(resp, "read") else bytes(resp)
    audio_b64 = base64.b64encode(audio_bytes).decode("utf-8")

    return {
      "status": "success",
      "format": fmt,
      "voice": voice,
      "model": model,
      "audio_base64": audio_b64,
    }
  except Exception as e:
    return {"status": "error", "message": f"TTS failed: {e!r}"}

