#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Serper API Client（生产可用版）

目标：
- 每次调用时动态读取环境变量，避免 import 时缓存旧 key
- 兼容 search/news
- 同时返回 raw / items / results / organic / news / markdown / meta
- 出错信息足够明确，便于直接定位是 key、网络、还是 HTTP 状态码问题
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict, List

import requests


class SerperError(Exception):
    pass


def _maybe_load_dotenv() -> None:
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except Exception:
        pass


def _env_text(*keys: str, default: str = "") -> str:
    for key in keys:
        value = os.getenv(key, "")
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return str(default or "").strip()


def _get_api_key() -> str:
    _maybe_load_dotenv()
    api_key = _env_text("SERPER_API_KEY", "SERPERDEV_API_KEY")
    if not api_key:
        raise SerperError(
            "SERPER_API_KEY 未配置。请检查 .env / systemd / docker 环境变量，并确认已重启 mcp-nisb 进程。"
        )
    return api_key


def _get_base_url(search_type: str) -> str:
    _maybe_load_dotenv()
    st = str(search_type or "search").strip().lower()
    if st == "news":
        return _env_text("SERPER_NEWS_URL", default="https://google.serper.dev/news")
    return _env_text("SERPER_BASE_URL", default="https://google.serper.dev/search")


def _pick_candidates(data: Dict[str, Any], search_type: str) -> List[Dict[str, Any]]:
    st = str(search_type or "search").strip().lower()

    if st == "news":
        for key in ("news", "results", "organic"):
            value = data.get(key)
            if isinstance(value, list) and value:
                return [x for x in value if isinstance(x, dict)]
        return []

    for key in ("organic", "results", "news"):
        value = data.get(key)
        if isinstance(value, list) and value:
            return [x for x in value if isinstance(x, dict)]
    return []


def _normalize_items(candidates: List[Dict[str, Any]], limit: int) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []

    for item in candidates[:limit]:
        if not isinstance(item, dict):
            continue

        title = str(item.get("title") or item.get("name") or "").strip()
        snippet = str(item.get("snippet") or item.get("description") or item.get("summary") or "").strip()
        url = str(item.get("link") or item.get("url") or item.get("source") or "").strip()

        if not url:
            continue

        items.append(
            {
                "title": title,
                "snippet": snippet,
                "url": url,
                "link": url,
            }
        )

    return items


def _build_markdown(query: str, items: List[Dict[str, Any]], search_type: str, gl: str, hl: str) -> str:
    lines: List[str] = []

    if not items:
        lines.append("未从 Serper 检索到相关网页结果。")
        lines.append(f"（query={query}, search_type={search_type}, gl={gl}, hl={hl}）")
        lines.append("注意：如果这是意外情况，请检查 API key、网络连通性和 Serper 配额。")
        return "\n".join(lines)

    lines.append(f"Serper 为查询「{query}」返回了以下网页结果（{len(items)} 条）：")
    for idx, it in enumerate(items, start=1):
        title = it.get("title") or "(无标题)"
        snippet = it.get("snippet") or "(无摘要)"
        url = it.get("url") or "(无链接)"
        lines.append(f"{idx}. {title}")
        lines.append(f"   - 摘要：{snippet}")
        lines.append(f"   - 链接：{url}")

    lines.append("")
    lines.append("要求：回答时只允许引用以上列出的真实链接，不要编造链接。")
    return "\n".join(lines)


def serper_search(
    query: str,
    num: int = 5,
    *,
    gl: str = "us",
    hl: str = "en",
    search_type: str = "search",
    **extra: Any,
) -> Dict[str, Any]:
    """
    返回：
      - raw: 原始 JSON
      - items: 标准化结果列表（title/snippet/url/link）
      - results: items 别名
      - organic/news: 兼容上层格式化器
      - markdown: 供 LLM 使用的文本
      - meta: 调试信息
    """
    q = str(query or "").strip()
    if not q:
        raise SerperError("查询内容不能为空。")

    st = str(search_type or "search").strip().lower()
    if st not in ("search", "news"):
        st = "search"

    try:
        n = int(num or 5)
    except Exception:
        n = 5
    n = max(1, min(n, 10))

    api_key = _get_api_key()
    base_url = _get_base_url(st)

    headers = {
        "X-API-KEY": api_key,
        "Content-Type": "application/json",
    }

    payload: Dict[str, Any] = {
        "q": q,
        "num": n,
        "gl": gl,
        "hl": hl,
    }
    if isinstance(extra, dict) and extra:
        payload.update(extra)

    try:
        resp = requests.post(
            base_url,
            headers=headers,
            json=payload,
            timeout=20,
        )
    except requests.RequestException as e:
        raise SerperError(f"Serper 网络请求失败：{e}") from e

    text_preview = (resp.text or "")[:500]

    if resp.status_code >= 400:
        raise SerperError(
            f"Serper HTTP {resp.status_code}，url={base_url}，body={text_preview}"
        )

    try:
        data = resp.json()
    except Exception as e:
        raise SerperError(f"Serper 返回非 JSON：{text_preview}") from e

    if not isinstance(data, dict):
        raise SerperError("Serper 返回格式异常：顶层不是 JSON object。")

    candidates = _pick_candidates(data, st)
    items = _normalize_items(candidates, n)
    markdown = _build_markdown(q, items, st, gl, hl)

    out: Dict[str, Any] = {
        "raw": data,
        "items": items,
        "results": items,
        "markdown": markdown,
        "meta": {
            "num_requested": n,
            "num_returned": len(items),
            "search_type": st,
            "gl": gl,
            "hl": hl,
            "base_url": base_url,
        },
    }

    if st == "news":
        out["news"] = items
        out["organic"] = []
    else:
        out["organic"] = items
        out["news"] = []

    return out

