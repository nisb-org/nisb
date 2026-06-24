#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import re
from typing import List, Tuple, Optional

_NISB_URI_RE = re.compile(r"nisb://[^\s)<>\]\"']+", flags=re.IGNORECASE)
_NISB_URI_ENC_RE = re.compile(r"nisb%3a%2f%2f[0-9a-zA-Z%._~!$&'()*+,;=:@/?\-]+", flags=re.IGNORECASE)


def _is_refusal_text(text: str) -> bool:
  t = (text or "").strip()
  if not t:
    return False

  low = t.lower()

  if len(t) > 200:
    return False

  patterns = [
    r"^对不起[，,]?\s*我(无法|不能).*(请求|帮助|处理|完成)",
    r"^抱歉[，,]?\s*我(无法|不能).*(请求|帮助|处理|完成)",
    r"无法完成这个请求",
    r"无法处理该请求",
    r"无法完成该请求",
    r"我无法帮助",
    r"我不能帮助",
    r"i['’]m\s*sorry",
    r"i\s*can['’]t\s*(assist|help)",
    r"i\s*cannot\s*(assist|help)",
    r"i\s*can\s*not\s*(assist|help)",
    r"can['’]t\s*(assist|help)\s*with\s*that\s*request",
    r"cannot\s*(assist|help)\s*with\s*that\s*request",
  ]
  for p in patterns:
    try:
      if re.search(p, t, flags=re.IGNORECASE):
        return True
    except Exception:
      continue

  if len(t) <= 60:
    if (("对不起" in t) or ("抱歉" in t) or ("sorry" in low)) and (("无法" in t) or ("不能" in t) or ("can't" in low) or ("cannot" in low)):
      return True

  return False


def _collect_nisb_uris(text: str) -> List[str]:
  src = str(text or "")
  out: List[str] = []
  for m in _NISB_URI_RE.finditer(src):
    u = (m.group(0) or "").strip()
    if u:
      out.append(u)
  for m in _NISB_URI_ENC_RE.finditer(src):
    u = (m.group(0) or "").strip()
    if u:
      out.append(u)
  return out


def _protect_nisb_uris(text: str) -> Tuple[str, List[Tuple[str, str]]]:
  src = str(text or "")
  mapping: List[Tuple[str, str]] = []
  idx = 0

  def _repl(m: re.Match) -> str:
    nonlocal idx, mapping
    raw = (m.group(0) or "").strip()
    token = f"__NISB_URI_{idx:04d}__"
    idx += 1
    mapping.append((token, raw))
    return token

  protected = _NISB_URI_RE.sub(_repl, src)
  protected = _NISB_URI_ENC_RE.sub(_repl, protected)
  return protected, mapping


def _restore_nisb_uris(text: str, mapping: List[Tuple[str, str]]) -> str:
  out = str(text or "")
  if not mapping:
    return out
  for token, uri in mapping:
    if token and uri:
      out = out.replace(token, uri)
  return out


def _repair_nisb_uris_by_source(source_text: str, translated_text: str) -> str:
  src_uris = _collect_nisb_uris(source_text)
  if not src_uris:
    return str(translated_text or "")

  out = str(translated_text or "")
  i = 0

  def _next_uri() -> Optional[str]:
    nonlocal i
    if i >= len(src_uris):
      return None
    u = src_uris[i]
    i += 1
    return u

  def _repl_any(m: re.Match) -> str:
    u = _next_uri()
    return u if u else (m.group(0) or "")

  out = _NISB_URI_RE.sub(_repl_any, out)
  out = _NISB_URI_ENC_RE.sub(_repl_any, out)
  return out


def _split_text_for_translation_preserve_nisb(text: str, chunk_size: int = 8000) -> List[str]:
  s = str(text or "")
  if not s:
    return []
  n = len(s)
  if chunk_size <= 0 or n <= chunk_size:
    return [s]

  chunks: List[str] = []
  i = 0

  while i < n:
    end = min(i + chunk_size, n)
    window = s[i:end]

    last_start = window.lower().rfind("nisb://")
    if last_start != -1:
      abs_start = i + last_start
      m = _NISB_URI_RE.match(s[abs_start:])
      if m:
        uri_end = abs_start + len(m.group(0))
        if uri_end > end and (uri_end - abs_start) < chunk_size and abs_start > i:
          end = abs_start

    if end == i:
      end = min(i + chunk_size, n)

    chunks.append(s[i:end])
    i = end

  return chunks

