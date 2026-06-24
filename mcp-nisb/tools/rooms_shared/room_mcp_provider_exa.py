from __future__ import annotations

import json
import os
import re
import socket
import time
from typing import Any, Dict, List, Optional
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from .room_mcp_provider_i18n import (
    mcp_provider_error_response,
    mcp_text,
)
from .room_packet_builder import (
    _empty_evidence_result,
    _ensure_formal_packet,
)
from .room_request_bridge import (
    _safe_dict,
    _safe_list,
    _safe_str,
)


_ALLOWED_SEARCH_TYPES = {"auto", "neural", "fast", "deep-lite", "deep", "deep-reasoning", "instant"}
_ALLOWED_CATEGORIES = {"", "research paper", "news", "company", "people", "personal site", "financial report"}


def _safe_int(v: Any, default: int = 0, minimum: Optional[int] = None, maximum: Optional[int] = None) -> int:
    try:
        out = int(v)
    except Exception:
        out = int(default)
    if minimum is not None and out < minimum:
        out = minimum
    if maximum is not None and out > maximum:
        out = maximum
    return out


def _resolve_param_value(params: Dict[str, Any], key: str, fallback: Any = "") -> Any:
    value = params.get(key, fallback)
    if isinstance(value, str) and value.strip() == "{{user_query}}":
        return fallback
    return value


def _clean_text(text: Any) -> str:
    return " ".join(_safe_str(text).split())


def _truncate_text(text: Any, limit: int = 220) -> str:
    raw = _clean_text(text)
    if len(raw) <= limit:
        return raw
    return raw[: max(0, limit - 1)].rstrip() + "…"


def _safe_string_list(v: Any) -> List[str]:
    if not isinstance(v, list):
        return []
    out: List[str] = []
    for item in v:
        s = _safe_str(item)
        if s:
            out.append(s)
    return out


def _normalize_domain(value: Any) -> str:
    raw = _safe_str(value).lower()
    if not raw:
        return ""
    if "://" not in raw:
        raw = f"https://{raw}"
    try:
        parsed = urlparse(raw)
        host = (parsed.netloc or parsed.path or "").strip().lower()
    except Exception:
        host = _safe_str(value).strip().lower()
    host = host.split("/")[0].split("?")[0].split("#")[0].strip()
    if host.startswith("www."):
        host = host[4:]
    host = host.strip(" ,;|")
    return host


def _safe_domain_list(v: Any) -> List[str]:
    raw_items: List[str] = []
    if isinstance(v, list):
        raw_items = [_safe_str(item) for item in v]
    else:
        text = _safe_str(v)
        if text:
            raw_items = re.split(r"[\n,，;；|\t ]+", text)

    seen = set()
    out: List[str] = []
    for item in raw_items:
        domain = _normalize_domain(item)
        if not domain or "." not in domain:
            continue
        if domain in seen:
            continue
        seen.add(domain)
        out.append(domain)
        if len(out) >= 50:
            break
    return out


def _timeout_for_search_type(search_type: str) -> int:
    if search_type == "instant":
        return 8
    if search_type == "fast":
        return 10
    if search_type in {"auto", "neural"}:
        return 15
    if search_type == "deep-lite":
        return 25
    if search_type == "deep":
        return 40
    if search_type == "deep-reasoning":
        return 50
    return 15


def _provider_error_packet(
    *,
    room_id: str,
    request_id: str,
    requested_mode: str,
    mcp_overrides: Dict[str, Any],
    question: str,
    role: Dict[str, Any],
    provider_id: str,
    error: str,
    request_args: Optional[Dict[str, Any]] = None,
    query: str = "",
    request_url: str = "",
    latency_ms: int = 0,
    search_type: str = "",
    category: str = "",
    include_domains: Optional[List[str]] = None,
) -> Dict[str, Any]:
    role_id = _safe_str(role.get("role_id"))
    role_name = _safe_str(role.get("name") or role.get("slug") or role_id)
    normalized_query = _safe_str(query or question)
    domains = list(include_domains or [])
    visible_error = mcp_provider_error_response(
        question,
        provider_id,
        error,
        request_args=request_args,
    )
    return _ensure_formal_packet(
        conv_id=room_id,
        request_id=request_id,
        rag_mode=requested_mode,
        mcp_overrides=mcp_overrides,
        mode_used="mcp",
        response=visible_error,
        status="error",
        message=f"room mcp provider {error}",
        evidence_query=normalized_query,
        evidence_tools=["exa_search_api"],
        evidence_result={
            **_empty_evidence_result(normalized_query),
            "provider_id": provider_id,
            "request_url": request_url,
            "error": error,
            "latency_ms": latency_ms,
            "search_type": _safe_str(search_type),
            "category": _safe_str(category),
            "include_domains": domains,
        },
        tool_calls=[],
        tool_results=[
            {
                "type": "room_mcp_provider_error",
                "role_id": role_id,
                "role_name": role_name,
                "provider_id": provider_id,
                "tool_name": "search",
                "status": "error",
                "query": normalized_query,
                "request_url": request_url,
                "error": error,
                "latency_ms": latency_ms,
                "search_type": _safe_str(search_type),
                "category": _safe_str(category),
                "include_domains": domains,
            }
        ],
    )


def _render_exa_response(
    question: str,
    query: str,
    items: List[Dict[str, Any]],
    request_args: Optional[Dict[str, Any]] = None,
) -> str:
    if not items:
        return mcp_text(question, "exa_empty", request_args=request_args, query=query)

    lines = [mcp_text(question, "exa_found", request_args=request_args, count=len(items), query=query)]
    for index, item in enumerate(items, start=1):
        title = _safe_str(item.get("title"), "Untitled")
        url = _safe_str(item.get("url"))
        published = _safe_str(item.get("published_date"))[:10]
        author = _safe_str(item.get("author"))
        snippet = _truncate_text(item.get("snippet"), 180)

        meta_bits = [x for x in [published, author] if x]
        meta = "; ".join(meta_bits)
        if meta:
            lines.append(f"{index}. {title} ({meta})")
        else:
            lines.append(f"{index}. {title}")

        if snippet:
            lines.append(f"   {mcp_text(question, 'summary', request_args=request_args)}: {snippet}")
        if url:
            lines.append(f"   {mcp_text(question, 'link', request_args=request_args)}: {url}")
    return "\n".join(lines)


def execute_room_mcp_provider_exa(
    *,
    room_id: str,
    request_id: str,
    question: str,
    requested_mode: str,
    mcp_overrides: Dict[str, Any],
    request_args: Dict[str, Any],
    role: Dict[str, Any],
) -> Dict[str, Any]:
    api_key = _safe_str(os.getenv("EXA_API_KEY"))
    if not api_key:
        return _provider_error_packet(
            room_id=room_id,
            request_id=request_id,
            requested_mode=requested_mode,
            mcp_overrides=mcp_overrides,
            question=question,
            role=role,
            provider_id="exa",
            error="missing_env:EXA_API_KEY",
            request_args=request_args,
        )

    mcp_binding = _safe_dict(request_args.get("mcp_binding"))
    params = _safe_dict(mcp_binding.get("params"))
    role_id = _safe_str(role.get("role_id"))
    role_name = _safe_str(role.get("name") or role.get("slug") or role_id)

    query = _safe_str(_resolve_param_value(params, "query", question) or question)
    num_results = _safe_int(params.get("num_results", 5), default=5, minimum=1, maximum=10)

    raw_search_type = _safe_str(params.get("search_type"), "auto")
    search_type = raw_search_type if raw_search_type in _ALLOWED_SEARCH_TYPES else "auto"

    raw_category = _safe_str(params.get("category"))
    category = raw_category if raw_category in _ALLOWED_CATEGORIES else ""

    include_domains = _safe_domain_list(params.get("include_domains"))
    if category == "people" and include_domains:
        invalid_domains = [d for d in include_domains if d != "linkedin.com" and not d.endswith(".linkedin.com")]
        if invalid_domains:
            return _provider_error_packet(
                room_id=room_id,
                request_id=request_id,
                requested_mode=requested_mode,
                mcp_overrides=mcp_overrides,
                question=question,
                role=role,
                provider_id="exa",
                error="invalid_params:category:people:include_domains:linkedin_only",
                request_args=request_args,
                query=query,
                search_type=search_type,
                category=category,
                include_domains=include_domains,
            )

    body: Dict[str, Any] = {
        "query": query,
        "numResults": num_results,
        "type": search_type,
        "contents": {
            "highlights": {
                "maxCharacters": 240,
            }
        },
    }
    if category:
        body["category"] = category
    if include_domains:
        body["includeDomains"] = include_domains

    request_url = "https://api.exa.ai/search"
    timeout_seconds = _timeout_for_search_type(search_type)
    request = Request(
        request_url,
        data=json.dumps(body).encode("utf-8"),
        headers={
            "x-api-key": api_key,
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "NISB-Room-ExaProvider/1.0",
        },
        method="POST",
    )

    started = time.monotonic()
    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            payload = json.loads(response.read().decode("utf-8", errors="replace"))
        latency_ms = int((time.monotonic() - started) * 1000)

        results = _safe_list(payload.get("results"))
        upstream_request_id = _safe_str(payload.get("requestId"))
        actual_search_type = _safe_str(payload.get("searchType") or search_type)

        items: List[Dict[str, Any]] = []
        for result in results:
            obj = _safe_dict(result)
            highlights = _safe_string_list(obj.get("highlights"))
            snippet = _safe_str(obj.get("summary"))
            if not snippet and highlights:
                snippet = highlights[0]
            if not snippet:
                snippet = _safe_str(obj.get("text"))

            items.append(
                {
                    "id": _safe_str(obj.get("id")),
                    "title": _clean_text(obj.get("title")),
                    "url": _safe_str(obj.get("url")),
                    "published_date": _safe_str(obj.get("publishedDate")),
                    "author": _safe_str(obj.get("author")),
                    "search_type": actual_search_type,
                    "snippet": snippet,
                    "highlights": highlights,
                }
            )

        response_text = _render_exa_response(
            question,
            query,
            items,
            request_args=request_args,
        )
        return _ensure_formal_packet(
            conv_id=room_id,
            request_id=request_id,
            rag_mode=requested_mode,
            mcp_overrides=mcp_overrides,
            mode_used="mcp",
            response=response_text,
            status="success",
            message="room mcp provider exa search completed",
            citations=[],
            rss_evidence=[],
            market_evidence=[],
            evidence_query=query,
            evidence_tools=["exa_search_api"],
            evidence_result={
                **_empty_evidence_result(query),
                "provider_id": "exa",
                "request_url": request_url,
                "count": len(items),
                "search_type": actual_search_type,
                "category": category,
                "include_domains": include_domains,
                "request_id_upstream": upstream_request_id,
                "latency_ms": latency_ms,
                "timeout_seconds": timeout_seconds,
            },
            tool_calls=[],
            tool_results=[
                {
                    "type": "room_mcp_provider",
                    "role_id": role_id,
                    "role_name": role_name,
                    "provider_id": "exa",
                    "tool_name": "search",
                    "status": "success",
                    "query": query,
                    "request_url": request_url,
                    "count": len(items),
                    "search_type": actual_search_type,
                    "category": category,
                    "include_domains": include_domains,
                    "request_id_upstream": upstream_request_id,
                    "latency_ms": latency_ms,
                    "timeout_seconds": timeout_seconds,
                    "items": items,
                }
            ],
        )
    except HTTPError as ex:
        latency_ms = int((time.monotonic() - started) * 1000)
        try:
            detail = ex.read().decode("utf-8", errors="replace").strip()
        except Exception:
            detail = ""
        status_reason = f"upstream_{int(getattr(ex, 'code', 0) or 0)}"
        error = status_reason if not detail else f"{status_reason}:{detail}"
        return _provider_error_packet(
            room_id=room_id,
            request_id=request_id,
            requested_mode=requested_mode,
            mcp_overrides=mcp_overrides,
            question=question,
            role=role,
            provider_id="exa",
            error=error,
            request_args=request_args,
            query=query,
            request_url=request_url,
            latency_ms=latency_ms,
            search_type=search_type,
            category=category,
            include_domains=include_domains,
        )
    except (socket.timeout, TimeoutError):
        latency_ms = int((time.monotonic() - started) * 1000)
        return _provider_error_packet(
            room_id=room_id,
            request_id=request_id,
            requested_mode=requested_mode,
            mcp_overrides=mcp_overrides,
            question=question,
            role=role,
            provider_id="exa",
            error="network_error:timeout",
            request_args=request_args,
            query=query,
            request_url=request_url,
            latency_ms=latency_ms,
            search_type=search_type,
            category=category,
            include_domains=include_domains,
        )
    except URLError as ex:
        latency_ms = int((time.monotonic() - started) * 1000)
        return _provider_error_packet(
            room_id=room_id,
            request_id=request_id,
            requested_mode=requested_mode,
            mcp_overrides=mcp_overrides,
            question=question,
            role=role,
            provider_id="exa",
            error=f"network_error:{_safe_str(getattr(ex, 'reason', ex))}",
            request_args=request_args,
            query=query,
            request_url=request_url,
            latency_ms=latency_ms,
            search_type=search_type,
            category=category,
            include_domains=include_domains,
        )
    except Exception as ex:
        latency_ms = int((time.monotonic() - started) * 1000)
        return _provider_error_packet(
            room_id=room_id,
            request_id=request_id,
            requested_mode=requested_mode,
            mcp_overrides=mcp_overrides,
            question=question,
            role=role,
            provider_id="exa",
            error=f"{type(ex).__name__}: {ex}",
            request_args=request_args,
            query=query,
            request_url=request_url,
            latency_ms=latency_ms,
            search_type=search_type,
            category=category,
            include_domains=include_domains,
        )


__all__ = [
    "execute_room_mcp_provider_exa",
]
