from __future__ import annotations

from typing import Any, Dict, Optional
from urllib.parse import urlencode
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET

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


def _clean_text(text: Any) -> str:
    raw = _safe_str(text)
    return " ".join(raw.split())


def _truncate_text(text: Any, limit: int = 220) -> str:
    raw = _clean_text(text)
    if len(raw) <= limit:
        return raw
    return raw[: max(0, limit - 1)].rstrip() + "…"


def _resolve_param_value(params: Dict[str, Any], key: str, fallback: Any = "") -> Any:
    value = params.get(key, fallback)
    if isinstance(value, str) and value.strip() == "{{user_query}}":
        return fallback
    return value


def _build_arxiv_search_query(query: str) -> str:
    q = _safe_str(query)
    if not q:
        return ""
    lowered = q.lower()
    known_prefixes = ("all:", "ti:", "au:", "abs:", "cat:", "rn:", "id:")
    if lowered.startswith(known_prefixes):
        return q
    return f"all:{q}"


def _fetch_arxiv_entries(
    *,
    query: str,
    max_results: int,
    sort_by: str,
    sort_order: str,
) -> Dict[str, Any]:
    search_query = _build_arxiv_search_query(query)
    if not search_query:
        return {
            "request_url": "",
            "entries": [],
        }

    params = {
        "search_query": search_query,
        "start": 0,
        "max_results": max_results,
        "sortBy": sort_by,
        "sortOrder": sort_order,
    }
    request_url = "https://export.arxiv.org/api/query?" + urlencode(params)
    request = Request(
        request_url,
        headers={
            "User-Agent": "NISB-Room-ArxivProvider/1.0",
            "Accept": "application/atom+xml, application/xml, text/xml;q=0.9, */*;q=0.8",
        },
    )

    with urlopen(request, timeout=20) as response:
        xml_text = response.read()

    root = ET.fromstring(xml_text)
    ns = {
        "atom": "http://www.w3.org/2005/Atom",
        "arxiv": "http://arxiv.org/schemas/atom",
    }

    entries = []
    for entry in root.findall("atom:entry", ns):
        title = _clean_text(entry.findtext("atom:title", default="", namespaces=ns))
        summary = _clean_text(entry.findtext("atom:summary", default="", namespaces=ns))
        entry_id = _clean_text(entry.findtext("atom:id", default="", namespaces=ns))
        published = _clean_text(entry.findtext("atom:published", default="", namespaces=ns))
        updated = _clean_text(entry.findtext("atom:updated", default="", namespaces=ns))

        authors = []
        for author in entry.findall("atom:author", ns):
            name = _clean_text(author.findtext("atom:name", default="", namespaces=ns))
            if name:
                authors.append(name)

        primary_category = ""
        primary_node = entry.find("arxiv:primary_category", ns)
        if primary_node is not None:
            primary_category = _clean_text(primary_node.attrib.get("term"))

        pdf_url = ""
        for link in entry.findall("atom:link", ns):
            title_attr = _clean_text(link.attrib.get("title"))
            type_attr = _clean_text(link.attrib.get("type"))
            href_attr = _clean_text(link.attrib.get("href"))
            if title_attr.lower() == "pdf" or type_attr.lower() == "application/pdf":
                pdf_url = href_attr
                break

        entries.append(
            {
                "title": title,
                "summary": summary,
                "id": entry_id,
                "published": published,
                "updated": updated,
                "authors": authors,
                "primary_category": primary_category,
                "pdf_url": pdf_url,
            }
        )

    return {
        "request_url": request_url,
        "entries": entries,
    }


def _render_arxiv_response(
    question: str,
    query: str,
    entries: list[Dict[str, Any]],
    request_args: Optional[Dict[str, Any]] = None,
) -> str:
    safe_query = _safe_str(query)
    if not entries:
        return mcp_text(question, "arxiv_empty", request_args=request_args, query=safe_query)

    lines = [mcp_text(question, "arxiv_found", request_args=request_args, count=len(entries), query=safe_query)]
    for index, item in enumerate(entries, start=1):
        title = _safe_str(item.get("title"), "Untitled")
        published = _safe_str(item.get("published"))[:10]
        authors = item.get("authors") if isinstance(item.get("authors"), list) else []
        author_text = ", ".join([_safe_str(x) for x in authors[:3] if _safe_str(x)])
        if len(authors) > 3:
            author_text = f"{author_text} {mcp_text(question, 'et_al', request_args=request_args)}".strip()
        summary = _truncate_text(item.get("summary"), 180)
        link = _safe_str(item.get("id") or item.get("pdf_url"))
        category = _safe_str(item.get("primary_category"))

        meta_bits = [x for x in [published, author_text, category] if x]
        meta = "; ".join(meta_bits)
        if meta:
            lines.append(f"{index}. {title} ({meta})")
        else:
            lines.append(f"{index}. {title}")

        if summary:
            lines.append(f"   {mcp_text(question, 'summary', request_args=request_args)}: {summary}")
        if link:
            lines.append(f"   {mcp_text(question, 'link', request_args=request_args)}: {link}")

    return "\n".join(lines)


def execute_room_mcp_provider_arxiv(
    *,
    room_id: str,
    request_id: str,
    question: str,
    requested_mode: str,
    mcp_overrides: Dict[str, Any],
    request_args: Dict[str, Any],
    role: Dict[str, Any],
) -> Dict[str, Any]:
    mcp_binding = _safe_dict(request_args.get("mcp_binding"))
    params = _safe_dict(mcp_binding.get("params"))
    role_id = _safe_str(role.get("role_id"))
    role_name = _safe_str(role.get("name") or role.get("slug") or role_id)

    query = _safe_str(_resolve_param_value(params, "query", question) or question)
    max_results = _safe_int(params.get("max_results", params.get("num", 5)), default=5, minimum=1, maximum=10)
    sort_by = _safe_str(params.get("sort_by"), "relevance")
    sort_order = _safe_str(params.get("sort_order"), "descending")

    if sort_by not in {"relevance", "lastUpdatedDate", "submittedDate"}:
        sort_by = "relevance"
    if sort_order not in {"ascending", "descending"}:
        sort_order = "descending"

    try:
        fetched = _fetch_arxiv_entries(
            query=query,
            max_results=max_results,
            sort_by=sort_by,
            sort_order=sort_order,
        )
        entries = _safe_list(fetched.get("entries"))
        request_url = _safe_str(fetched.get("request_url"))
        response_text = _render_arxiv_response(
            question,
            query,
            entries,
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
            message="room mcp provider arxiv search completed",
            citations=[],
            rss_evidence=[],
            market_evidence=[],
            evidence_query=query,
            evidence_tools=["arxiv_api"],
            evidence_result={
                **_empty_evidence_result(query),
                "provider_id": "arxiv",
                "request_url": request_url,
                "count": len(entries),
            },
            tool_calls=[],
            tool_results=[
                {
                    "type": "room_mcp_provider",
                    "role_id": role_id,
                    "role_name": role_name,
                    "provider_id": "arxiv",
                    "tool_name": "search",
                    "status": "success",
                    "query": query,
                    "request_url": request_url,
                    "count": len(entries),
                    "items": entries,
                }
            ],
        )
    except Exception as ex:
        error = f"{type(ex).__name__}: {ex}"
        return _ensure_formal_packet(
            conv_id=room_id,
            request_id=request_id,
            rag_mode=requested_mode,
            mcp_overrides=mcp_overrides,
            mode_used="mcp",
            response=mcp_provider_error_response(
                question,
                "arxiv",
                error,
                request_args=request_args,
            ),
            status="error",
            message=f"room mcp provider failed: {error}",
            evidence_query=query or question,
            evidence_tools=["arxiv_api"],
            evidence_result={**_empty_evidence_result(query or question), "error": error},
            tool_calls=[],
            tool_results=[
                {
                    "type": "room_mcp_provider_error",
                    "role_id": role_id,
                    "role_name": role_name,
                    "provider_id": "arxiv",
                    "error": error,
                }
            ],
        )


__all__ = [
    "execute_room_mcp_provider_arxiv",
]
