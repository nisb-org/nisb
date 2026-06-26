from __future__ import annotations

import html
import json
import os
import re
from typing import Any, Dict, Optional
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .room_mcp_provider_i18n import mcp_provider_error_response
from .room_packet_builder import _empty_evidence_result, _ensure_formal_packet
from .room_request_bridge import _safe_dict, _safe_list, _safe_str


_FREESOUND_RISK_NOTE = (
    "Freesound licenses vary by sound. Free preview/download does not automatically mean commercial or YouTube-safe use."
)

_AUDIO_EXTENSIONS = (".mp3", ".ogg", ".wav", ".aac", ".flac")


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


def _safe_float(v: Any, default: Optional[float] = None) -> Optional[float]:
    if v in (None, ""):
        return default
    try:
        return float(v)
    except Exception:
        return default


def _resolve_param_value(params: Dict[str, Any], key: str, fallback: Any = "") -> Any:
    value = params.get(key, fallback)
    if isinstance(value, str) and value.strip() == "{{user_query}}":
        return fallback
    return value


def _clean_text(text: Any) -> str:
    return " ".join(_safe_str(text).split())


def _clean_search_query(text: Any) -> str:
    q = _clean_text(text)
    if not q:
        return ""

    prefixes = [
        "搜索",
        "搜",
        "查找",
        "查",
        "找",
        "找一下",
        "帮我找",
        "帮我搜索",
        "search",
        "find",
        "look up",
    ]

    lowered = q.lower().strip()
    for prefix in prefixes:
        p = prefix.lower()
        if lowered == p:
            return ""
        if lowered.startswith(p + " "):
            return q[len(prefix):].strip()
        if lowered.startswith(p + "："):
            return q[len(prefix):].strip(" ：:")
        if lowered.startswith(p + ":"):
            return q[len(prefix):].strip(" ：:")

    return q


def _sanitize_error(error: Any, *secrets: str) -> str:
    out = _safe_str(error)
    for secret in secrets:
        if secret:
            out = out.replace(secret, "<redacted>")
    return out


def _html_attr(value: Any) -> str:
    return html.escape(_safe_str(value), quote=True)


def _html_text(value: Any) -> str:
    return html.escape(_safe_str(value), quote=False)


def _safe_download_filename(value: Any, fallback: str = "freesound_preview.mp3") -> str:
    raw = _clean_text(value) or fallback
    raw = raw.replace("/", "_").replace("\\", "_").replace("\x00", "")
    raw = re.sub(r"\s+", " ", raw).strip()
    raw = re.sub(r'[<>:"|?*]+', "_", raw)
    raw = raw[:160].strip(" ._") or fallback

    lower = raw.lower()
    if not lower.endswith(_AUDIO_EXTENSIONS):
        raw = f"{raw}.mp3"
    return raw


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
        evidence_tools=["freesound_api"],
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
        or "search_sounds"
    )
    if tool_name in {"search", "sound_search", "search_audio"}:
        return "search_sounds"
    if tool_name in {"detail", "sound_detail"}:
        return "get_sound_detail"
    return tool_name


def _request_json(url: str, api_key: str) -> Dict[str, Any]:
    request = Request(
        url,
        headers={
            "Authorization": f"Token {api_key}",
            "Accept": "application/json",
            "User-Agent": "NISB-Room-FreesoundProvider/1.0",
        },
    )
    try:
        with urlopen(request, timeout=25) as response:
            return json.loads(response.read().decode("utf-8", errors="replace"))
    except HTTPError as ex:
        body = ex.read().decode("utf-8", errors="replace")[:500]
        raise RuntimeError(f"HTTPError:{ex.code}: {_sanitize_error(body, api_key)}") from ex


def _license_filter_value(value: str) -> str:
    s = _safe_str(value).lower()
    if s in {"cc0", "creative commons 0", "creative commons zero"}:
        return 'license:"Creative Commons 0"'
    if s in {"attribution", "by", "cc-by", "cc by"}:
        return 'license:"Attribution"'
    if s in {"noncommercial", "non-commercial", "attribution noncommercial", "cc-by-nc"}:
        return 'license:"Attribution NonCommercial"'
    return ""


def _build_filter(params: Dict[str, Any]) -> str:
    parts = []
    user_filter = _safe_str(params.get("filter"))
    if user_filter:
        parts.append(user_filter)

    duration_min = _safe_float(params.get("duration_min"))
    duration_max = _safe_float(params.get("duration_max"))
    if duration_min is not None or duration_max is not None:
        start = "*" if duration_min is None else str(duration_min)
        end = "*" if duration_max is None else str(duration_max)
        parts.append(f"duration:[{start} TO {end}]")

    license_value = _license_filter_value(_safe_str(params.get("license")))
    if license_value:
        parts.append(license_value)

    return " ".join(parts).strip()


def _preview_url(previews: Dict[str, Any]) -> str:
    previews_obj = _safe_dict(previews)
    for key in ("preview-hq-mp3", "preview-lq-mp3", "preview-hq-ogg", "preview-lq-ogg"):
        value = _safe_str(previews_obj.get(key))
        if value:
            return value
    return ""


def _attribution_required(license_name: str) -> bool:
    s = _safe_str(license_name).lower()
    if "creative commons 0" in s or s == "cc0":
        return False
    return "attribution" in s or bool(s)


def _risk_note(license_name: str) -> str:
    s = _safe_str(license_name).lower()
    if not s:
        return "License is missing or unclear; verify the Freesound page before use."
    if "noncommercial" in s or "non-commercial" in s:
        return "License appears to restrict commercial use; avoid monetized YouTube use unless you have permission."
    if "creative commons 0" in s or s == "cc0":
        return "CC0 is usually simplest, but still verify the Freesound page and avoid trademark/privacy issues."
    if "attribution" in s:
        return "Attribution is likely required; include creator and license credit in the video description."
    return _FREESOUND_RISK_NOTE


def _normalize_sound_item(item: Dict[str, Any]) -> Dict[str, Any]:
    license_name = _safe_str(item.get("license"))
    previews = _safe_dict(item.get("previews"))
    return {
        "id": item.get("id"),
        "name": _clean_text(item.get("name")),
        "url": _safe_str(item.get("url")),
        "preview_url": _preview_url(previews),
        "duration": item.get("duration"),
        "license": license_name,
        "username": _safe_str(item.get("username")),
        "creator": _safe_str(item.get("username")),
        "tags": _safe_list(item.get("tags")),
        "description": _clean_text(item.get("description")),
        "asset_type": "sound",
        "attribution_required": _attribution_required(license_name),
        "risk_note": _risk_note(license_name),
        "metadata": {
            "type": item.get("type"),
            "created": item.get("created"),
            "num_downloads": item.get("num_downloads"),
            "avg_rating": item.get("avg_rating"),
            "previews": previews,
            "images": _safe_dict(item.get("images")),
            "raw": item,
        },
    }


def _render_audio_controls(preview_url: str, filename: str, label: str = "下载音频 / Download audio") -> str:
    url = _safe_str(preview_url)
    if not url:
        return ""

    name = _safe_download_filename(filename)
    link_label = _safe_str(label) or "下载音频 / Download audio"

    return "\n".join(
        [
            f'<audio controls src="{_html_attr(url)}" style="width:100%;max-width:520px;display:block;margin:8px 0"></audio>',
            f'<a href="{_html_attr(url)}" download="{_html_attr(name)}">{_html_text(link_label)}</a>',
        ]
    )


def _render_response(tool_name: str, query: str, items: list[Dict[str, Any]]) -> str:
    if not items:
        return f"Freesound: no sound results found for `{query}`."

    lines = [f"Freesound: found {len(items)} sound candidate(s) for `{query}`.", ""]
    for index, item in enumerate(items, start=1):
        title = _safe_str(item.get("name") or f"Sound {index}")
        preview_url = _safe_str(item.get("preview_url"))
        filename = _safe_download_filename(title)

        lines.append(f"### {index}. {_html_text(title)}")

        if preview_url:
            lines.append(_render_audio_controls(preview_url, filename, "下载音频 / Download audio"))

        if _safe_str(item.get("url")):
            lines.append(f"- Page: {_safe_str(item.get('url'))}")
        if preview_url:
            lines.append(f"- Preview URL: {_safe_str(preview_url)}")
        if item.get("duration") not in (None, ""):
            lines.append(f"- Duration: {item.get('duration')} sec")
        if _safe_str(item.get("license")):
            lines.append(f"- License: {_safe_str(item.get('license'))}")
        if _safe_str(item.get("creator")):
            lines.append(f"- Creator: {_safe_str(item.get('creator'))}")
        lines.append(f"- Attribution required: {bool(item.get('attribution_required'))}")
        lines.append(f"- Risk note: {_safe_str(item.get('risk_note'))}")
        lines.append("")
    return "\n".join(lines).strip()


def execute_room_mcp_provider_freesound(
    *,
    room_id: str,
    request_id: str,
    question: str,
    requested_mode: str,
    mcp_overrides: Dict[str, Any],
    request_args: Dict[str, Any],
    role: Dict[str, Any],
) -> Dict[str, Any]:
    api_key = _safe_str(os.getenv("FREESOUND_API_KEY"))
    if not api_key:
        return _provider_error_packet(
            room_id=room_id,
            request_id=request_id,
            requested_mode=requested_mode,
            mcp_overrides=mcp_overrides,
            question=question,
            role=role,
            provider_id="freesound",
            error="missing_env:FREESOUND_API_KEY",
            request_args=request_args,
        )

    mcp_binding = _safe_dict(request_args.get("mcp_binding"))
    params = _safe_dict(mcp_binding.get("params"))
    role_id = _safe_str(role.get("role_id"))
    role_name = _safe_str(role.get("name") or role.get("slug") or role_id)
    tool_name = _selected_tool_name(request_args)

    fields = ",".join(
        [
            "id",
            "url",
            "name",
            "tags",
            "description",
            "license",
            "type",
            "duration",
            "username",
            "previews",
            "images",
            "created",
            "num_downloads",
            "avg_rating",
        ]
    )

    try:
        if tool_name == "search_sounds":
            query = _clean_search_query(_resolve_param_value(params, "query", question) or question)
            limit = _safe_int(params.get("limit", params.get("page_size", 8)), default=8, minimum=1, maximum=30)
            page = _safe_int(params.get("page", 1), default=1, minimum=1)
            sort = _safe_str(params.get("sort"), "score")
            if sort not in {
                "score",
                "duration_desc",
                "duration_asc",
                "created_desc",
                "created_asc",
                "downloads_desc",
                "downloads_asc",
                "rating_desc",
                "rating_asc",
            }:
                sort = "score"

            request_params: Dict[str, Any] = {
                "query": query,
                "page": page,
                "page_size": limit,
                "sort": sort,
                "fields": fields,
            }
            filter_value = _build_filter(params)
            if filter_value:
                request_params["filter"] = filter_value

            request_url = "https://freesound.org/apiv2/search/text/?" + urlencode(request_params)
            payload = _request_json(request_url, api_key)
            results = _safe_list(payload.get("results"))
            items = [_normalize_sound_item(_safe_dict(row)) for row in results]
            response_text = _render_response(tool_name, query, items)

            evidence_query = query
            public_request_url = request_url
            count = len(items)

        elif tool_name == "get_sound_detail":
            sound_id = _safe_str(params.get("sound_id") or params.get("id"))
            if not sound_id:
                return _provider_error_packet(
                    room_id=room_id,
                    request_id=request_id,
                    requested_mode=requested_mode,
                    mcp_overrides=mcp_overrides,
                    question=question,
                    role=role,
                    provider_id="freesound",
                    error="missing_param:sound_id",
                    request_args=request_args,
                )

            request_params = {"fields": fields}
            request_url = f"https://freesound.org/apiv2/sounds/{sound_id}/?" + urlencode(request_params)
            payload = _request_json(request_url, api_key)
            items = [_normalize_sound_item(_safe_dict(payload))]
            response_text = _render_response(tool_name, sound_id, items)

            evidence_query = sound_id
            public_request_url = request_url
            count = len(items)

        else:
            return _provider_error_packet(
                room_id=room_id,
                request_id=request_id,
                requested_mode=requested_mode,
                mcp_overrides=mcp_overrides,
                question=question,
                role=role,
                provider_id="freesound",
                error=f"unsupported_tool:{tool_name}",
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
            message=f"room mcp provider freesound {tool_name} completed",
            citations=[],
            rss_evidence=[],
            market_evidence=[],
            evidence_query=evidence_query,
            evidence_tools=["freesound_api"],
            evidence_result={
                **_empty_evidence_result(evidence_query),
                "provider_id": "freesound",
                "tool_name": tool_name,
                "request_url": public_request_url,
                "count": count,
            },
            tool_calls=[],
            tool_results=[
                {
                    "type": "room_mcp_provider",
                    "role_id": role_id,
                    "role_name": role_name,
                    "provider_id": "freesound",
                    "tool_name": tool_name,
                    "status": "success",
                    "query": evidence_query,
                    "request_url": public_request_url,
                    "count": count,
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
            question=question,
            role=role,
            provider_id="freesound",
            error=_sanitize_error(f"{type(ex).__name__}: {ex}", api_key),
            request_args=request_args,
        )


__all__ = ["execute_room_mcp_provider_freesound"]
