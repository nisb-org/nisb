from __future__ import annotations

import json
import os
from typing import Any, Dict, Optional
from urllib.parse import urlencode
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
) -> Dict[str, Any]:
    role_id = _safe_str(role.get("role_id"))
    role_name = _safe_str(role.get("name") or role.get("slug") or role_id)
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
        evidence_query=question,
        evidence_tools=["pexels_api"],
        evidence_result={**_empty_evidence_result(question), "provider_id": provider_id, "error": error},
        tool_calls=[],
        tool_results=[
            {
                "type": "room_mcp_provider_error",
                "role_id": role_id,
                "role_name": role_name,
                "provider_id": provider_id,
                "error": error,
            }
        ],
    )


def _pick_image_url(src: Dict[str, Any]) -> str:
    src_obj = _safe_dict(src)
    for key in ("large2x", "large", "medium", "small", "tiny", "original"):
        value = _safe_str(src_obj.get(key))
        if value:
            return value
    return ""


def _render_pexels_response(
    question: str,
    query: str,
    items: list[Dict[str, Any]],
    request_args: Optional[Dict[str, Any]] = None,
) -> str:
    if not items:
        return mcp_text(question, "pexels_empty", request_args=request_args, query=query)

    lines = [mcp_text(question, "pexels_found", request_args=request_args, count=len(items), query=query), ""]
    for index, item in enumerate(items, start=1):
        photographer = _safe_str(item.get("photographer")) or "Pexels"
        title = _safe_str(item.get("alt")) or mcp_text(
            question,
            "pexels_image",
            request_args=request_args,
            index=index,
        )
        page_url = _safe_str(item.get("url"))
        image_url = _safe_str(item.get("image_url"))

        lines.append(f"### {index}. {title}")
        if image_url:
            lines.append(f"![{title}]({image_url})")
        if page_url:
            lines.append(f"[{mcp_text(question, 'pexels_page', request_args=request_args)}]({page_url})")
        lines.append(f"{mcp_text(question, 'photographer', request_args=request_args)}: {photographer}")
        lines.append("")

    return "\n".join(lines).strip()


def execute_room_mcp_provider_pexels(
    *,
    room_id: str,
    request_id: str,
    question: str,
    requested_mode: str,
    mcp_overrides: Dict[str, Any],
    request_args: Dict[str, Any],
    role: Dict[str, Any],
) -> Dict[str, Any]:
    api_key = _safe_str(os.getenv("PEXELS_API_KEY"))
    if not api_key:
        return _provider_error_packet(
            room_id=room_id,
            request_id=request_id,
            requested_mode=requested_mode,
            mcp_overrides=mcp_overrides,
            question=question,
            role=role,
            provider_id="pexels",
            error="missing_env:PEXELS_API_KEY",
            request_args=request_args,
        )

    mcp_binding = _safe_dict(request_args.get("mcp_binding"))
    params = _safe_dict(mcp_binding.get("params"))
    role_id = _safe_str(role.get("role_id"))
    role_name = _safe_str(role.get("name") or role.get("slug") or role_id)

    query = _safe_str(_resolve_param_value(params, "query", question) or question)
    per_page = _safe_int(params.get("per_page", 6), default=6, minimum=1, maximum=15)
    page = _safe_int(params.get("page", 1), default=1, minimum=1)
    orientation = _safe_str(params.get("orientation"))

    request_params = {
        "query": query,
        "per_page": per_page,
        "page": page,
    }
    if orientation in {"landscape", "portrait", "square"}:
        request_params["orientation"] = orientation

    request_url = "https://api.pexels.com/v1/search?" + urlencode(request_params)
    request = Request(
        request_url,
        headers={
            "Authorization": api_key,
            "Accept": "application/json",
            "User-Agent": "NISB-Room-PexelsProvider/1.0",
        },
    )

    try:
        with urlopen(request, timeout=20) as response:
            payload = json.loads(response.read().decode("utf-8", errors="replace"))

        photos = _safe_list(payload.get("photos"))
        items = []
        for photo in photos:
            photo_obj = _safe_dict(photo)
            src_obj = _safe_dict(photo_obj.get("src"))
            items.append(
                {
                    "id": photo_obj.get("id"),
                    "alt": _clean_text(photo_obj.get("alt")),
                    "url": _safe_str(photo_obj.get("url")),
                    "photographer": _safe_str(photo_obj.get("photographer")),
                    "photographer_url": _safe_str(photo_obj.get("photographer_url")),
                    "avg_color": _safe_str(photo_obj.get("avg_color")),
                    "width": photo_obj.get("width"),
                    "height": photo_obj.get("height"),
                    "image_url": _pick_image_url(src_obj),
                    "src": src_obj,
                }
            )

        response_text = _render_pexels_response(
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
            message="room mcp provider pexels search completed",
            citations=[],
            rss_evidence=[],
            market_evidence=[],
            evidence_query=query,
            evidence_tools=["pexels_api"],
            evidence_result={
                **_empty_evidence_result(query),
                "provider_id": "pexels",
                "request_url": request_url,
                "count": len(items),
            },
            tool_calls=[],
            tool_results=[
                {
                    "type": "room_mcp_provider",
                    "role_id": role_id,
                    "role_name": role_name,
                    "provider_id": "pexels",
                    "tool_name": "search",
                    "status": "success",
                    "query": query,
                    "request_url": request_url,
                    "count": len(items),
                    "items": items,
                }
            ],
        )
    except Exception as ex:
        return _provider_error_packet(
            room_id=room_id,
            request_id=request_id,
            requested_mode=requested_mode,
            mcp_overrides=mcp_overrides,
            question=query or question,
            role=role,
            provider_id="pexels",
            error=f"{type(ex).__name__}: {ex}",
            request_args=request_args,
        )


__all__ = [
    "execute_room_mcp_provider_pexels",
]
