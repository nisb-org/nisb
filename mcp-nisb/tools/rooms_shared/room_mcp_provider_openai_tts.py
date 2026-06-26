from __future__ import annotations

import hashlib
import json
import os
import re
import time
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import Request, urlopen

from .room_mcp_provider_i18n import mcp_provider_error_response
from .room_packet_builder import _empty_evidence_result, _ensure_formal_packet
from .room_request_bridge import _safe_dict, _safe_list, _safe_str


_MAX_TTS_CHARS = 5000

_OPENAI_TTS_VOICES = [
    {"voice_id": "alloy", "name": "alloy", "category": "built_in", "labels": {"style": "balanced"}},
    {"voice_id": "ash", "name": "ash", "category": "built_in", "labels": {"style": "clear"}},
    {"voice_id": "ballad", "name": "ballad", "category": "built_in", "labels": {"style": "narrative"}},
    {"voice_id": "coral", "name": "coral", "category": "built_in", "labels": {"style": "warm"}},
    {"voice_id": "echo", "name": "echo", "category": "built_in", "labels": {"style": "steady"}},
    {"voice_id": "fable", "name": "fable", "category": "built_in", "labels": {"style": "storytelling"}},
]

_MIME_BY_FORMAT = {
    "mp3": "audio/mpeg",
    "opus": "audio/opus",
    "aac": "audio/aac",
    "flac": "audio/flac",
    "wav": "audio/wav",
    "pcm": "audio/pcm",
}


_AUDIO_EXTENSIONS = set(_MIME_BY_FORMAT.keys())
_SAFE_ROOM_ID_RE = re.compile(r"^[A-Za-z0-9_.-]{1,120}$")
_SAFE_FILENAME_RE = re.compile(r"^[A-Za-z0-9_.-]{1,180}$")


def _data_root() -> Path:
    return Path(os.getenv("NISB_BASE_PATH", "/data")).resolve()


def _safe_room_id(room_id: Any) -> str:
    rid = _safe_str(room_id).strip()
    if not rid or "/" in rid or "\\" in rid or ".." in rid or not _SAFE_ROOM_ID_RE.match(rid):
        raise RuntimeError("invalid_room_id")
    return rid


def _safe_audio_ext(response_format: Any) -> str:
    ext = _safe_str(response_format).lower().strip().lstrip(".")
    if ext not in _AUDIO_EXTENSIONS:
        ext = "mp3"
    return ext


def _safe_filename_part(value: Any, fallback: str = "audio") -> str:
    out = "".join(ch for ch in _safe_str(value).lower().strip() if ch.isalnum() or ch in {"-", "_"})
    return (out[:48] or fallback)


def _make_audio_filename(*, voice: str, response_format: str, text: str) -> str:
    ext = _safe_audio_ext(response_format)
    digest = hashlib.sha256(text.encode("utf-8", errors="ignore")).hexdigest()[:12]
    ts = time.strftime("%Y%m%d_%H%M%S", time.gmtime())
    safe_voice = _safe_filename_part(voice, "voice")
    return f"tts_{safe_voice}_{ts}_{digest}.{ext}"


def _room_audio_dir(room_id: str) -> Path:
    rid = _safe_room_id(room_id)
    root = _data_root()
    path = (root / "shared" / "rooms" / rid / "assets" / "audio").resolve()
    expected_parent = (root / "shared" / "rooms" / rid / "assets").resolve()
    if expected_parent not in path.parents:
        raise RuntimeError("invalid_room_audio_dir")
    return path


def _write_room_audio_file(room_id: str, audio_bytes: bytes, *, filename: str) -> Path:
    if not _SAFE_FILENAME_RE.match(filename) or "/" in filename or "\\" in filename or ".." in filename:
        raise RuntimeError("invalid_audio_filename")
    audio_dir = _room_audio_dir(room_id)
    audio_dir.mkdir(parents=True, exist_ok=True)
    path = (audio_dir / filename).resolve()
    if audio_dir.resolve() not in path.parents:
        raise RuntimeError("invalid_audio_output_path")
    path.write_bytes(audio_bytes)
    return path


def _room_audio_urls(room_id: str, filename: str) -> Dict[str, str]:
    rid = quote(_safe_room_id(room_id), safe="")
    name = quote(filename, safe="")
    base = f"/api/rooms/{rid}/assets/audio/{name}"
    return {
        "playback_url": f"{base}?disposition=inline",
        "download_url": f"{base}?disposition=attachment",
    }


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
        evidence_tools=["openai_audio_speech_api"],
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
    provider_meta = _safe_dict(request_args.get("_room_mcp_provider_meta"))

    provider_id = _safe_str(
        request_args.get("provider_id")
        or request_args.get("_room_mcp_provider_id")
        or mcp_binding.get("provider_id")
        or provider_meta.get("provider_id")
    )

    tool_name = _safe_str(
        request_args.get("tool_name")
        or request_args.get("tool")
        or mcp_binding.get("tool_name")
        or mcp_binding.get("tool")
        or mcp_binding.get("name")
        or "text_to_speech"
    ).strip().lower()

    if provider_id == "openai_tts" and tool_name in {"", "search", "default"}:
        return "text_to_speech"

    if tool_name in {"search", "tts", "speech", "generate_speech", "text_to_speech"}:
        return "text_to_speech"

    if tool_name in {"voices", "voice_list", "list", "list_voices"}:
        return "list_voices"

    return tool_name


def _request_bytes(api_key: str, payload: Dict[str, Any]) -> bytes:
    body = json.dumps(payload).encode("utf-8")
    request = Request(
        "https://api.openai.com/v1/audio/speech",
        data=body,
        method="POST",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Accept": "*/*",
            "Content-Type": "application/json",
            "User-Agent": "NISB-Room-OpenAITTSProvider/1.0",
        },
    )
    try:
        with urlopen(request, timeout=60) as response:
            return response.read()
    except HTTPError as ex:
        body_text = ex.read().decode("utf-8", errors="replace")[:700]
        raise RuntimeError(f"HTTPError:{ex.code}: {_sanitize_error(body_text, api_key)}") from ex


def _render_voices_response(items: list[Dict[str, Any]]) -> str:
    lines = [f"OpenAI TTS: built-in voice candidates ({len(items)}).", ""]
    for index, item in enumerate(items, start=1):
        voice_id = _safe_str(item.get("voice_id"))
        lines.append(f"### {index}. {voice_id}")
        lines.append(f"- voice_id: `{voice_id}`")
        lines.append(f"- category: {_safe_str(item.get('category'))}")
        labels = _safe_dict(item.get("labels"))
        if labels:
            lines.append(f"- labels: {json.dumps(labels, ensure_ascii=False)}")
        lines.append("")
    return "\n".join(lines).strip()


def _render_tts_response(result: Dict[str, Any]) -> str:
    audio = _safe_dict(result.get("audio"))
    playback_url = _safe_str(audio.get("playback_url"))
    download_url = _safe_str(audio.get("download_url"))
    filename = _safe_str(audio.get("filename") or "tts.mp3")
    mime_type = _safe_str(audio.get("mime_type") or "audio/mpeg")
    size_bytes = int(audio.get("size_bytes") or 0)

    voice = _safe_str(result.get("voice"))
    model = _safe_str(result.get("model"))
    response_format = _safe_str(result.get("response_format", "mp3"))
    character_count = result.get("character_count", 0)
    size_kb = max(1, size_bytes // 1024) if size_bytes else 0

    if playback_url and download_url:
        lines = [
            f'<audio controls src="{playback_url}" style="width:100%;max-width:520px;display:block;margin:8px 0"></audio>',
            "",
            f'<a href="{download_url}" download="{filename}">下载音频 / Download audio</a>',
            "",
            "<details><summary>详细信息 / Details</summary>",
            "",
            f"- filename: `{filename}`",
            f"- mime_type: `{mime_type}`",
            f"- size: {size_kb} KB",
            f"- voice: `{voice}`",
            f"- model: `{model}`",
            f"- format: `{response_format}`",
            f"- characters: {character_count}",
            "",
            "</details>",
        ]
    else:
        lines = [
            "OpenAI TTS: audio generated, but no playback URL is available.",
            f"- voice: `{voice}`",
            f"- model: `{model}`",
        ]

    return "\n".join(lines)


def execute_room_mcp_provider_openai_tts(
    *,
    room_id: str,
    request_id: str,
    question: str,
    requested_mode: str,
    mcp_overrides: Dict[str, Any],
    request_args: Dict[str, Any],
    role: Dict[str, Any],
) -> Dict[str, Any]:
    api_key = _safe_str(os.getenv("OPENAI_API_KEY"))
    if not api_key:
        return _provider_error_packet(
            room_id=room_id,
            request_id=request_id,
            requested_mode=requested_mode,
            mcp_overrides=mcp_overrides,
            question=question,
            role=role,
            provider_id="openai_tts",
            error="missing_env:OPENAI_API_KEY",
            request_args=request_args,
        )

    mcp_binding = _safe_dict(request_args.get("mcp_binding"))
    params = _safe_dict(mcp_binding.get("params"))
    role_id = _safe_str(role.get("role_id"))
    role_name = _safe_str(role.get("name") or role.get("slug") or role_id)
    tool_name = _selected_tool_name(request_args)

    try:
        if tool_name == "list_voices":
            items = [
                {
                    **row,
                    "preview_url": "",
                    "language": "",
                    "accent": "",
                    "metadata": {"source": "openai_builtin_voice_catalog"},
                }
                for row in _OPENAI_TTS_VOICES
            ]
            response_text = _render_voices_response(items)
            evidence_query = "list_voices"
            result_payload = {
                "items": items,
                "count": len(items),
                "request_url": "builtin:openai_tts_voice_catalog",
            }

        elif tool_name == "text_to_speech":
            text = _safe_str(_resolve_param_value(params, "text", question) or question)
            if not text:
                return _provider_error_packet(
                    room_id=room_id,
                    request_id=request_id,
                    requested_mode=requested_mode,
                    mcp_overrides=mcp_overrides,
                    question=question,
                    role=role,
                    provider_id="openai_tts",
                    error="missing_param:text",
                    request_args=request_args,
                )

            if len(text) > _MAX_TTS_CHARS:
                return _provider_error_packet(
                    room_id=room_id,
                    request_id=request_id,
                    requested_mode=requested_mode,
                    mcp_overrides=mcp_overrides,
                    question=question,
                    role=role,
                    provider_id="openai_tts",
                    error=f"text_too_long:max_chars:{_MAX_TTS_CHARS}",
                    request_args=request_args,
                )

            model = _safe_str(params.get("model") or params.get("model_id"), "gpt-4o-mini-tts")
            voice = _safe_str(params.get("voice") or params.get("voice_id") or os.getenv("OPENAI_TTS_DEFAULT_VOICE"), "alloy")
            response_format = _safe_str(params.get("response_format") or params.get("output_format"), "mp3")
            instructions = _safe_str(params.get("instructions") or params.get("style_prompt"))
            speed = _safe_float(params.get("speed"))

            payload: Dict[str, Any] = {
                "model": model,
                "input": text,
                "voice": voice,
                "response_format": response_format,
            }
            if instructions:
                payload["instructions"] = instructions
            if speed is not None:
                payload["speed"] = speed

            audio_bytes = _request_bytes(api_key, payload)
            audio_ext = _safe_audio_ext(response_format)
            audio_mime_type = _MIME_BY_FORMAT.get(audio_ext, "application/octet-stream")
            filename = _make_audio_filename(voice=voice, response_format=audio_ext, text=text)
            saved_path = _write_room_audio_file(room_id, audio_bytes, filename=filename)
            urls = _room_audio_urls(room_id, filename)

            audio_meta = {
                "scope": "room",
                "room_id": _safe_room_id(room_id),
                "relative_path": f"assets/audio/{filename}",
                "filename": filename,
                "mime_type": audio_mime_type,
                "playback_url": urls["playback_url"],
                "download_url": urls["download_url"],
                "size_bytes": len(audio_bytes),
                "duration_seconds": None,
            }

            result = {
                "result_type": "audio",
                "asset_type": "audio",
                "audio": audio_meta,
                "saved_file_path": str(saved_path),
                "audio_url": urls["playback_url"],
                "audio_mime_type": audio_mime_type,
                "duration": None,
                "voice": voice,
                "voice_id": voice,
                "model": model,
                "model_id": model,
                "response_format": audio_ext,
                "character_count": len(text),
                "usage_note": "Audio was saved as a room-scoped server file; Room events store only playback/download URLs and metadata.",
                "risk_note": "Confirm OpenAI usage terms, disclosure requirements, and YouTube monetization policy before publishing.",
            }

            response_text = _render_tts_response(result)
            evidence_query = _clean_text(text[:160])
            result_payload = {
                **result,
                "count": 1,
                "request_url": "https://api.openai.com/v1/audio/speech",
            }

        else:
            return _provider_error_packet(
                room_id=room_id,
                request_id=request_id,
                requested_mode=requested_mode,
                mcp_overrides=mcp_overrides,
                question=question,
                role=role,
                provider_id="openai_tts",
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
            message=f"room mcp provider openai_tts {tool_name} completed",
            citations=[],
            rss_evidence=[],
            market_evidence=[],
            evidence_query=evidence_query,
            evidence_tools=["openai_audio_speech_api"],
            evidence_result={
                **_empty_evidence_result(evidence_query),
                "provider_id": "openai_tts",
                "tool_name": tool_name,
                "count": result_payload.get("count", 0),
            },
            tool_calls=[],
            tool_results=[
                {
                    "type": "room_mcp_provider",
                    "role_id": role_id,
                    "role_name": role_name,
                    "provider_id": "openai_tts",
                    "tool_name": tool_name,
                    "status": "success",
                    **result_payload,
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
            provider_id="openai_tts",
            error=_sanitize_error(f"{type(ex).__name__}: {ex}", api_key),
            request_args=request_args,
        )


__all__ = ["execute_room_mcp_provider_openai_tts"]
