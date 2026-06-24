#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import re
import secrets
import time
from typing import Any, Dict


_NEED_WEB_PATTERNS = [
    r"近日|最近|最新|刚刚|本周|本月|今天|昨天|这周|近况|动态|新闻|公告|发布|更新|路线图|rumor|辟谣",
    r"链接|来源|source|references?|cite|citation|url|网址|原文|原链接|真实链接",
    r"\brecent\b|\blatest\b|\bnews\b|\bupdate(s)?\b|\bannouncement(s)?\b|\brelease(d)?\b",
]
_need_web_re = re.compile("|".join(f"(?:{p})" for p in _NEED_WEB_PATTERNS), re.IGNORECASE)


def new_request_id() -> str:
    return f"req_{int(time.time() * 1000)}_{secrets.token_hex(4)}"


def ensure_request_id(args: Dict[str, Any]) -> str:
    rid = str((args or {}).get("request_id") or "").strip()
    if not rid:
        rid = new_request_id()
        args["request_id"] = rid
    return rid


def coerce_bool(v: Any, default: bool = False) -> bool:
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return bool(v)
    if isinstance(v, str):
        return v.strip().lower() in ("1", "true", "yes", "on")
    return default


def should_use_web(question: str) -> bool:
    q = (question or "").strip()
    if not q:
        return False
    return bool(_need_web_re.search(q))


def defaults_for_mode(rag_mode: str) -> Dict[str, int]:
    m = (rag_mode or "off").lower()
    if m == "cite":
        return {
            "top_k": 10,
            "max_evidence": 10,
            "min_citations": 1,
            "max_citations": 6,
            "max_output_tokens": 1800,
        }
    if m == "ground":
        return {
            "top_k": 18,
            "max_evidence": 14,
            "min_citations": 4,
            "max_citations": 12,
            "max_output_tokens": 2200,
        }
    return {}

