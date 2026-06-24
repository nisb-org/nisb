#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import os
import re
import urllib.parse
from typing import Dict, Any, List

_IMAGE_RE = re.compile(r'!\[([^\]]*)\]\(([^)]+)\)')


def _safe_join_under_base(base_path: str, rel_path: str) -> str:
    base_real = os.path.realpath(str(base_path or ""))
    rel_norm = str(rel_path or "").strip().replace("\\", "/").lstrip("/")

    if not base_real:
        return ""

    abs_path = os.path.realpath(os.path.join(base_real, rel_norm))
    if abs_path == base_real or abs_path.startswith(base_real + os.sep):
        return abs_path
    return ""


def resolve_nisb_file_url(base_path: str, url: str) -> str:
    s = str(url or "").strip()
    if not s.startswith("nisb://file"):
        return ""

    try:
        parsed = urllib.parse.urlparse(s)
        qs = urllib.parse.parse_qs(parsed.query)
        raw_path = str((qs.get("path") or [""])[0] or "").strip()
        if not raw_path:
            return ""

        rel_path = urllib.parse.unquote(raw_path).strip()
        abs_path = _safe_join_under_base(base_path, rel_path)
        if not abs_path:
            return ""
        if not os.path.isfile(abs_path):
            return ""
        return abs_path
    except Exception:
        return ""


def split_markdown_with_nisb_images(markdown_text: str, base_path: str) -> List[Dict[str, Any]]:
    text = str(markdown_text or "")
    if not text:
        return []

    out: List[Dict[str, Any]] = []
    cursor = 0

    for m in _IMAGE_RE.finditer(text):
        start, end = m.span()
        alt = str(m.group(1) or "")
        url = str(m.group(2) or "").strip()

        if start > cursor:
            before = text[cursor:start]
            if before:
                out.append({
                    "type": "text",
                    "content": before,
                })

        if url.startswith("nisb://file"):
            resolved_path = resolve_nisb_file_url(base_path, url)
            out.append({
                "type": "image",
                "alt": alt,
                "url": url,
                "resolved_path": resolved_path,
            })
        else:
            out.append({
                "type": "text",
                "content": m.group(0),
            })

        cursor = end

    if cursor < len(text):
        tail = text[cursor:]
        if tail:
            out.append({
                "type": "text",
                "content": tail,
            })

    return out


def strip_markdown_images(markdown_text: str) -> str:
    return _IMAGE_RE.sub("", str(markdown_text or ""))

