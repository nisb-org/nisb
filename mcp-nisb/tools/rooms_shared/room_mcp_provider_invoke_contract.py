from __future__ import annotations

from typing import Any, Dict, List


_DESCRIPTOR_VERSION_FALLBACK = "v1"
_SERVER_TOOL_FALLBACK = "nisb_room_mcp_provider_call"
_REQUESTED_MODE_FALLBACK = "mcp"
_PROVIDER_KIND_FALLBACK = ""


def _safe_str(v: Any, default: str = "") -> str:
    if v is None:
        return default
    s = str(v).strip()
    return s if s else default


def _safe_dict(v: Any) -> Dict[str, Any]:
    return dict(v) if isinstance(v, dict) else {}


def _safe_list(v: Any) -> List[Any]:
    return list(v) if isinstance(v, list) else []


def _normalize_tool_templates(
    value: Any,
    *,
    fallback_tool_name: str = "",
    fallback_requested_mode: str = _REQUESTED_MODE_FALLBACK,
) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []

    for item in _safe_list(value):
        row = _safe_dict(item)
        if not row:
            continue

        normalized = dict(row)
        tool_name = _safe_str(
            row.get("tool_name")
            or row.get("name")
            or row.get("tool"),
            fallback_tool_name,
        )
        requested_mode = _safe_str(
            row.get("requested_mode"),
            fallback_requested_mode,
        ) or fallback_requested_mode

        if tool_name:
            normalized["tool_name"] = tool_name
        if requested_mode:
            normalized["requested_mode"] = requested_mode

        out.append(normalized)

    if out:
        return out

    if fallback_tool_name:
        return [
            {
                "tool_name": fallback_tool_name,
                "requested_mode": fallback_requested_mode,
            }
        ]

    return []


def _first_tool_name(tool_templates: List[Dict[str, Any]]) -> str:
    for item in tool_templates:
        row = _safe_dict(item)
        tool_name = _safe_str(
            row.get("tool_name")
            or row.get("name")
            or row.get("tool")
        )
        if tool_name:
            return tool_name
    return ""


def hydrate_provider_invoke_contract(
    provider_meta: Dict[str, Any] | None,
    *,
    descriptor_version_fallback: str = _DESCRIPTOR_VERSION_FALLBACK,
    server_tool_fallback: str = _SERVER_TOOL_FALLBACK,
    requested_mode_fallback: str = _REQUESTED_MODE_FALLBACK,
    provider_kind_fallback: str = _PROVIDER_KIND_FALLBACK,
) -> Dict[str, Any]:
    meta = dict(_safe_dict(provider_meta))
    if not meta:
        return {}

    raw_contract = _safe_dict(meta.get("invoke_contract"))

    provider_kind = _safe_str(
        meta.get("provider_kind")
        or meta.get("provider_type")
        or raw_contract.get("provider_kind")
        or raw_contract.get("provider_type"),
        provider_kind_fallback,
    )

    fallback_tool_name = _safe_str(
        raw_contract.get("tool_name")
        or meta.get("tool_name")
        or meta.get("name")
    )

    fallback_requested_mode = _safe_str(
        raw_contract.get("requested_mode")
        or meta.get("requested_mode"),
        requested_mode_fallback,
    ) or requested_mode_fallback

    raw_tool_templates = (
        raw_contract.get("tool_templates")
        if _safe_list(raw_contract.get("tool_templates"))
        else meta.get("tool_templates")
    )

    tool_templates = _normalize_tool_templates(
        raw_tool_templates,
        fallback_tool_name=fallback_tool_name,
        fallback_requested_mode=fallback_requested_mode,
    )

    tool_name = _safe_str(
        raw_contract.get("tool_name")
        or meta.get("tool_name")
        or _first_tool_name(tool_templates)
    )

    requested_mode = _safe_str(
        raw_contract.get("requested_mode")
        or meta.get("requested_mode")
        or (_safe_dict(tool_templates[0]).get("requested_mode") if tool_templates else ""),
        requested_mode_fallback,
    ) or requested_mode_fallback

    server_tool = _safe_str(
        raw_contract.get("server_tool")
        or meta.get("server_tool"),
        server_tool_fallback,
    ) or server_tool_fallback

    descriptor_version = _safe_str(
        raw_contract.get("descriptor_version")
        or meta.get("descriptor_version")
        or meta.get("version"),
        descriptor_version_fallback,
    ) or descriptor_version_fallback

    normalized_contract: Dict[str, Any] = dict(raw_contract)
    normalized_contract["descriptor_version"] = descriptor_version
    normalized_contract["server_tool"] = server_tool
    normalized_contract["requested_mode"] = requested_mode

    if provider_kind:
        normalized_contract["provider_kind"] = provider_kind
    if tool_templates:
        normalized_contract["tool_templates"] = tool_templates
    if tool_name:
        normalized_contract["tool_name"] = tool_name

    meta["descriptor_version"] = descriptor_version
    if provider_kind:
        meta["provider_kind"] = provider_kind
    if tool_templates:
        meta["tool_templates"] = tool_templates
    if tool_name:
        meta["tool_name"] = tool_name
    meta["requested_mode"] = requested_mode
    meta["server_tool"] = server_tool
    meta["invoke_contract"] = normalized_contract

    return meta


__all__ = [
    "hydrate_provider_invoke_contract",
]
