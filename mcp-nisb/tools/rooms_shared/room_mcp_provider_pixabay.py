from __future__ import annotations

import json
import os
from typing import Any, Dict, Optional
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .room_mcp_provider_i18n import mcp_provider_error_response
from .room_packet_builder import _empty_evidence_result, _ensure_formal_packet
from .room_request_bridge import _safe_dict, _safe_list, _safe_str


_PIXABAY_LICENSE_NOTE = (
    "Pixabay assets are provided under Pixabay's content/license terms. "
    "Review the asset page before commercial, brand, or YouTube use; do not assume every asset is risk-free."
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


def _safe_bool(v: Any, default: bool = False) -> bool:
    if isinstance(v, bool):
        return v
    if v is None or v == "":
        return default
    s = _safe_str(v).lower()
    if s in {"1", "true", "yes", "on", "y"}:
        return True
    if s in {"0", "false", "no", "off", "n"}:
        return False
    return default


def _resolve_param_value(params: Dict[str, Any], key: str, fallback: Any = "") -> Any:
    value = params.get(key, fallback)
    if isinstance(value, str) and value.strip() == "{{user_query}}":
        return fallback
    return value


def _clean_text(text: Any) -> str:
    return " ".join(_safe_str(text).split())


def _sanitize_error(error: Any, *secrets: str) -> str:
    out = _safe_str(error)
    for secret in secrets:
        if secret:
            out = out.replace(secret, "<redacted>")
    return out


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
        evidence_tools=["pixabay_api"],
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


def _selected_tool_name(request_args: Dict[str, Any]) -> str:
    mcp_binding = _safe_dict(request_args.get("mcp_binding"))
    tool_name = _safe_str(
        request_args.get("tool_name")
        or mcp_binding.get("tool_name")
        or mcp_binding.get("name")
        or "search_images"
    )
    if tool_name in {"search", "image_search"}:
        return "search_images"
    if tool_name in {"video_search"}:
        return "search_videos"
    if tool_name in {"music_search", "audio_search"}:
        return "search_music"
    return tool_name


def _request_json(url: str, api_key: str) -> Dict[str, Any]:
    request = Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "NISB-Room-PixabayProvider/1.0",
        },
    )
    try:
        with urlopen(request, timeout=25) as response:
            return json.loads(response.read().decode("utf-8", errors="replace"))
    except HTTPError as ex:
        body = ex.read().decode("utf-8", errors="replace")[:500]
        raise RuntimeError(f"HTTPError:{ex.code}: {_sanitize_error(body, api_key)}") from ex


def _public_request_url(endpoint: str, params: Dict[str, Any]) -> str:
    safe_params = {k: v for k, v in params.items() if k != "key"}
    return endpoint + "?" + urlencode(safe_params)


def _pick_video_url(videos: Dict[str, Any]) -> str:
    videos_obj = _safe_dict(videos)
    for key in ("large", "medium", "small", "tiny"):
        row = _safe_dict(videos_obj.get(key))
        value = _safe_str(row.get("url"))
        if value:
            return value
    return ""


def _pick_video_thumbnail(videos: Dict[str, Any], item: Dict[str, Any]) -> str:
    videos_obj = _safe_dict(videos)
    for key in ("large", "medium", "small", "tiny"):
        row = _safe_dict(videos_obj.get(key))
        value = _safe_str(row.get("thumbnail") or row.get("poster"))
        if value:
            return value
    return _safe_str(item.get("picture_url") or item.get("previewURL") or item.get("webformatURL"))


def _normalize_image_item(item: Dict[str, Any]) -> Dict[str, Any]:
    tags = _clean_text(item.get("tags"))
    title = tags or f"Pixabay image {item.get('id')}"
    return {
        "id": item.get("id"),
        "title": title,
        "description": title,
        "url": _safe_str(item.get("pageURL")),
        "asset_url": _safe_str(item.get("largeImageURL") or item.get("webformatURL") or item.get("previewURL")),
        "preview_url": _safe_str(item.get("previewURL") or item.get("webformatURL")),
        "thumbnail_url": _safe_str(item.get("webformatURL") or item.get("previewURL")),
        "source": "pixabay",
        "creator": _safe_str(item.get("user")),
        "creator_url": _safe_str(item.get("userImageURL")),
        "license_note": _PIXABAY_LICENSE_NOTE,
        "risk_note": "Check the Pixabay asset page for current license restrictions, model/property releases, and brand-safe usage.",
        "asset_type": "image",
        "duration": None,
        "tags": [x.strip() for x in tags.split(",") if x.strip()],
        "metadata": {
            "width": item.get("imageWidth"),
            "height": item.get("imageHeight"),
            "likes": item.get("likes"),
            "downloads": item.get("downloads"),
            "views": item.get("views"),
            "raw": item,
        },
    }


def _normalize_video_item(item: Dict[str, Any]) -> Dict[str, Any]:
    tags = _clean_text(item.get("tags"))
    title = tags or f"Pixabay video {item.get('id')}"
    videos = _safe_dict(item.get("videos"))
    return {
        "id": item.get("id"),
        "title": title,
        "description": title,
        "url": _safe_str(item.get("pageURL")),
        "asset_url": _pick_video_url(videos),
        "preview_url": _pick_video_thumbnail(videos, item),
        "thumbnail_url": _pick_video_thumbnail(videos, item),
        "source": "pixabay",
        "creator": _safe_str(item.get("user")),
        "creator_url": _safe_str(item.get("userImageURL")),
        "license_note": _PIXABAY_LICENSE_NOTE,
        "risk_note": "Use the page URL to verify license, releases, and YouTube-safe usage before publishing.",
        "asset_type": "video",
        "duration": item.get("duration"),
        "tags": [x.strip() for x in tags.split(",") if x.strip()],
        "metadata": {
            "picture_id": item.get("picture_id"),
            "likes": item.get("likes"),
            "downloads": item.get("downloads"),
            "views": item.get("views"),
            "raw": item,
        },
    }


def _normalize_music_item(item: Dict[str, Any]) -> Dict[str, Any]:
    title = _clean_text(item.get("title") or item.get("name") or item.get("tags") or f"Pixabay music {item.get('id')}")
    tags = _clean_text(item.get("tags"))
    return {
        "id": item.get("id"),
        "title": title,
        "description": _clean_text(item.get("description") or title),
        "url": _safe_str(item.get("pageURL") or item.get("url")),
        "asset_url": _safe_str(item.get("audio") or item.get("download_url") or item.get("previewURL")),
        "preview_url": _safe_str(item.get("previewURL") or item.get("audio")),
        "thumbnail_url": _safe_str(item.get("image") or item.get("artwork") or item.get("previewURL")),
        "source": "pixabay",
        "creator": _safe_str(item.get("user") or item.get("artist") or item.get("author")),
        "creator_url": _safe_str(item.get("userImageURL") or item.get("artist_url")),
        "license_note": _PIXABAY_LICENSE_NOTE,
        "risk_note": "Music usage can have platform-specific risks. Verify the Pixabay page and YouTube copyright status before publishing.",
        "asset_type": "music",
        "duration": item.get("duration"),
        "tags": [x.strip() for x in tags.split(",") if x.strip()],
        "metadata": {"raw": item},
    }


def _render_response(tool_name: str, query: str, items: list[Dict[str, Any]]) -> str:
    label = {
        "search_images": "Pixabay image candidates",
        "search_videos": "Pixabay video candidates",
        "search_music": "Pixabay music candidates",
    }.get(tool_name, "Pixabay candidates")

    if not items:
        return f"{label}: no results found for `{query}`."

    lines = [f"{label}: found {len(items)} result(s) for `{query}`.", ""]
    for index, item in enumerate(items, start=1):
        title = _safe_str(item.get("title") or item.get("description") or f"Result {index}")
        lines.append(f"### {index}. {title}")
        if _safe_str(item.get("thumbnail_url")) and item.get("asset_type") == "image":
            lines.append(f"![{title}]({_safe_str(item.get('thumbnail_url'))})")
        if _safe_str(item.get("url")):
            lines.append(f"- Page: {_safe_str(item.get('url'))}")
        if _safe_str(item.get("preview_url")):
            lines.append(f"- Preview: {_safe_str(item.get('preview_url'))}")
        if _safe_str(item.get("creator")):
            lines.append(f"- Creator: {_safe_str(item.get('creator'))}")
        if item.get("duration") not in (None, ""):
            lines.append(f"- Duration: {item.get('duration')}")
        lines.append(f"- License note: {_safe_str(item.get('license_note'))}")
        lines.append(f"- Risk note: {_safe_str(item.get('risk_note'))}")
        lines.append("")
    return "\n".join(lines).strip()


def execute_room_mcp_provider_pixabay(
    *,
    room_id: str,
    request_id: str,
    question: str,
    requested_mode: str,
    mcp_overrides: Dict[str, Any],
    request_args: Dict[str, Any],
    role: Dict[str, Any],
) -> Dict[str, Any]:
    api_key = _safe_str(os.getenv("PIXABAY_API_KEY"))
    if not api_key:
        return _provider_error_packet(
            room_id=room_id,
            request_id=request_id,
            requested_mode=requested_mode,
            mcp_overrides=mcp_overrides,
            question=question,
            role=role,
            provider_id="pixabay",
            error="missing_env:PIXABAY_API_KEY",
            request_args=request_args,
        )

    mcp_binding = _safe_dict(request_args.get("mcp_binding"))
    params = _safe_dict(mcp_binding.get("params"))
    role_id = _safe_str(role.get("role_id"))
    role_name = _safe_str(role.get("name") or role.get("slug") or role_id)
    tool_name = _selected_tool_name(request_args)

    endpoint_by_tool = {
        "search_images": "https://pixabay.com/api/",
        "search_videos": "https://pixabay.com/api/videos/",
        "search_music": "https://pixabay.com/api/music/",
    }
    endpoint = endpoint_by_tool.get(tool_name)
    if not endpoint:
        return _provider_error_packet(
            room_id=room_id,
            request_id=request_id,
            requested_mode=requested_mode,
            mcp_overrides=mcp_overrides,
            question=question,
            role=role,
            provider_id="pixabay",
            error=f"unsupported_tool:{tool_name}",
            request_args=request_args,
        )

    query = _safe_str(_resolve_param_value(params, "query", question) or question)
    per_page = _safe_int(params.get("per_page", params.get("limit", 6)), default=6, minimum=1, maximum=20)
    page = _safe_int(params.get("page", 1), default=1, minimum=1)
    safe_search = _safe_bool(params.get("safe_search", params.get("safesearch", True)), default=True)
    lang = _safe_str(params.get("lang") or params.get("language"))
    category = _safe_str(params.get("category"))

    request_params: Dict[str, Any] = {
        "key": api_key,
        "q": query,
        "per_page": per_page,
        "page": page,
        "safesearch": "true" if safe_search else "false",
    }
    if lang:
        request_params["lang"] = lang
    if category:
        request_params["category"] = category

    request_url = endpoint + "?" + urlencode(request_params)
    public_request_url = _public_request_url(endpoint, request_params)

    try:
        payload = _request_json(request_url, api_key)
        hits = _safe_list(payload.get("hits"))
        if tool_name == "search_images":
            items = [_normalize_image_item(_safe_dict(hit)) for hit in hits]
            evidence_tool = "pixabay_images_api"
        elif tool_name == "search_videos":
            items = [_normalize_video_item(_safe_dict(hit)) for hit in hits]
            evidence_tool = "pixabay_videos_api"
        else:
            items = [_normalize_music_item(_safe_dict(hit)) for hit in hits]
            evidence_tool = "pixabay_music_api"

        response_text = _render_response(tool_name, query, items)
        return _ensure_formal_packet(
            conv_id=room_id,
            request_id=request_id,
            rag_mode=requested_mode,
            mcp_overrides=mcp_overrides,
            mode_used="mcp",
            response=response_text,
            status="success",
            message=f"room mcp provider pixabay {tool_name} completed",
            citations=[],
            rss_evidence=[],
            market_evidence=[],
            evidence_query=query,
            evidence_tools=[evidence_tool],
            evidence_result={
                **_empty_evidence_result(query),
                "provider_id": "pixabay",
                "tool_name": tool_name,
                "request_url": public_request_url,
                "count": len(items),
            },
            tool_calls=[],
            tool_results=[
                {
                    "type": "room_mcp_provider",
                    "role_id": role_id,
                    "role_name": role_name,
                    "provider_id": "pixabay",
                    "tool_name": tool_name,
                    "status": "success",
                    "query": query,
                    "request_url": public_request_url,
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
            provider_id="pixabay",
            error=_sanitize_error(f"{type(ex).__name__}: {ex}", api_key),
            request_args=request_args,
        )


__all__ = ["execute_room_mcp_provider_pixabay"]
