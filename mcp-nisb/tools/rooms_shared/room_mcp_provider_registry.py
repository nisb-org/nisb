from __future__ import annotations

from typing import Any, Dict, List

from .room_mcp_imported_provider_resolver import (
    resolve_imported_room_mcp_provider,
    resolve_room_mcp_provider as _resolve_room_mcp_provider,
)
from .room_mcp_provider_contract import normalize_room_mcp_provider_contract
from .room_mcp_provider_presets import get_room_mcp_provider_registry
from .room_mcp_provider_room_registry import (
    ROOM_PROVIDER_PREFIX,
    get_dynamic_room_mcp_provider,
    is_room_provider_id,
    list_published_room_provider_schemas,
)

_DESCRIPTOR_VERSION_FALLBACK = "v1"
_PROVIDER_KIND_PRESET = "builtin_external_mcp"
_PROVIDER_KIND_ROOM_SHARED = "room_shared_capability"
_PROVIDER_ORIGIN_LOCAL_REGISTRY = "local_registry"
_PROVIDER_ORIGIN_IMPORTED_REMOTE = "imported_remote"
_PROVIDER_ORIGIN_LOCAL_ROOM_SHARED = "local_room_shared"

_LOCAL_ROOM_ORIGIN_ALIASES = {
    "",
    "local",
    "local_registry",
    "registry_local",
    "local_provider",
    "local_room",
    "local_room_shared",
}

def _safe_str(v: Any, default: str = "") -> str:
    if v is None:
        return default
    s = str(v).strip()
    return s if s else default


def _safe_dict(v: Any) -> Dict[str, Any]:
    return dict(v) if isinstance(v, dict) else {}


def _safe_list(v: Any) -> List[Any]:
    return list(v) if isinstance(v, list) else []


def _safe_bool(v: Any, default: bool = False) -> bool:
    if isinstance(v, bool):
        return v
    if v is None:
        return default
    s = _safe_str(v).lower()
    if s in {"1", "true", "yes", "on"}:
        return True
    if s in {"0", "false", "no", "off"}:
        return False
    return default


def _default_provider_kind(row: Dict[str, Any], provider_id: str, provider_origin: str) -> str:
    explicit = _safe_str(row.get("provider_kind"))
    if explicit:
        return explicit

    provider_type = _safe_str(row.get("provider_type"))
    if provider_type:
        return provider_type

    if provider_origin.startswith(_PROVIDER_ORIGIN_IMPORTED_REMOTE):
        return _PROVIDER_KIND_ROOM_SHARED

    if is_room_provider_id(provider_id):
        return _PROVIDER_KIND_ROOM_SHARED

    return _PROVIDER_KIND_PRESET


def _default_provider_origin(row: Dict[str, Any], provider_id: str) -> str:
    explicit = _safe_str(row.get("provider_origin"))
    if explicit:
        return explicit

    if is_room_provider_id(provider_id):
        return "local_room_shared"

    return _PROVIDER_ORIGIN_LOCAL_REGISTRY

def _is_room_shared_descriptor(
    *,
    provider_id: str,
    provider_kind: str,
    provider_type: str,
) -> bool:
    return (
        provider_kind == _PROVIDER_KIND_ROOM_SHARED
        or provider_type == _PROVIDER_KIND_ROOM_SHARED
        or is_room_provider_id(provider_id)
    )


def _canonical_provider_origin_for_row(
    row: Dict[str, Any],
    *,
    provider_id: str,
    provider_kind: str,
    provider_type: str,
    provider_origin: str,
) -> str:
    origin = _safe_str(provider_origin or row.get("provider_origin"))

    if _is_room_shared_descriptor(
        provider_id=provider_id,
        provider_kind=provider_kind,
        provider_type=provider_type,
    ):
        if origin in _LOCAL_ROOM_ORIGIN_ALIASES:
            return _PROVIDER_ORIGIN_LOCAL_ROOM_SHARED
        return origin or _PROVIDER_ORIGIN_LOCAL_ROOM_SHARED

    return origin or _PROVIDER_ORIGIN_LOCAL_REGISTRY

def _normalize_capabilities(row: Dict[str, Any], provider_kind: str) -> Dict[str, Any]:
    capabilities = _safe_dict(row.get("capabilities"))
    if capabilities:
        return capabilities

    return {
        "tools": True,
        "provider_kind": provider_kind,
    }


def _normalize_source_ref(
    row: Dict[str, Any],
    *,
    provider_id: str,
    provider_kind: str,
    provider_origin: str,
) -> Dict[str, Any]:
    explicit = _safe_dict(row.get("source_ref"))
    provider_type = _safe_str(row.get("provider_type") or provider_kind)
    room_source = _safe_dict(row.get("room_source"))
    share_ref = _safe_str(row.get("share_ref") or explicit.get("share_ref"))

    if _is_room_shared_descriptor(
        provider_id=provider_id,
        provider_kind=provider_kind,
        provider_type=provider_type,
    ):
        origin = _canonical_provider_origin_for_row(
            row,
            provider_id=provider_id,
            provider_kind=provider_kind,
            provider_type=provider_type,
            provider_origin=provider_origin or _safe_str(explicit.get("origin")),
        )
        room_id = _safe_str(
            row.get("source_room_id")
            or room_source.get("room_id")
            or row.get("room_id")
            or explicit.get("room_id")
        )

        out = dict(explicit)
        out["kind"] = _PROVIDER_KIND_ROOM_SHARED
        out["origin"] = origin
        out["provider_id"] = provider_id

        if room_id:
            out["room_id"] = room_id
        if share_ref:
            out["share_ref"] = share_ref

        return out

    if explicit:
        out = dict(explicit)
        if not _safe_str(out.get("kind")):
            out["kind"] = provider_kind
        if not _safe_str(out.get("origin")):
            out["origin"] = provider_origin
        if not _safe_str(out.get("provider_id")):
            out["provider_id"] = provider_id
        return out

    return {
        "kind": provider_kind,
        "origin": provider_origin,
        "provider_id": provider_id,
    }

def _normalize_provider_descriptor_row(row: Any) -> Dict[str, Any]:
    src = _safe_dict(row)
    if not src:
        return {}

    provider_id = _safe_str(src.get("provider_id")).lower()
    if not provider_id:
        return {}

    initial_origin = _default_provider_origin(src, provider_id)
    initial_kind = _default_provider_kind(src, provider_id, initial_origin)
    initial_type = _safe_str(src.get("provider_type"), initial_kind)
    initial_origin = _canonical_provider_origin_for_row(
        src,
        provider_id=provider_id,
        provider_kind=initial_kind,
        provider_type=initial_type,
        provider_origin=initial_origin,
    )

    base = normalize_room_mcp_provider_contract(
        {
            **src,
            "provider_id": provider_id,
            "provider_kind": initial_kind,
            "provider_type": initial_type,
            "provider_origin": initial_origin,
        },
        default_provider_type=initial_type,
        default_provider_origin=initial_origin,
    )

    out = dict(src)
    out.update(base)

    provider_kind = _safe_str(
        out.get("provider_kind")
        or out.get("provider_type"),
        initial_kind,
    )
    provider_type = _safe_str(
        out.get("provider_type")
        or provider_kind,
        provider_kind,
    )
    provider_origin = _canonical_provider_origin_for_row(
        out,
        provider_id=provider_id,
        provider_kind=provider_kind,
        provider_type=provider_type,
        provider_origin=_safe_str(out.get("provider_origin"), initial_origin),
    )

    out["provider_id"] = provider_id
    out["provider_kind"] = provider_kind
    out["provider_type"] = provider_type
    out["provider_origin"] = provider_origin
    out["descriptor_version"] = _safe_str(
        out.get("descriptor_version") or out.get("version"),
        _DESCRIPTOR_VERSION_FALLBACK,
    )
    out["label"] = _safe_str(out.get("label"))
    out["description"] = _safe_str(out.get("description"))
    out["params_defaults"] = _safe_dict(out.get("params_defaults") or out.get("default_params"))
    out["params_schema"] = _safe_dict(out.get("params_schema"))
    out["auth_state"] = _safe_dict(out.get("auth_state"))
    out["availability"] = {
        **_safe_dict(out.get("availability")),
        "available": _safe_bool(_safe_dict(out.get("availability")).get("available"), True),
    }
    out["boundary_hint"] = _safe_dict(out.get("boundary_hint"))
    out["room_source"] = _safe_dict(out.get("room_source"))
    out["capabilities"] = _normalize_capabilities(out, provider_kind)
    out["source_ref"] = _normalize_source_ref(
        out,
        provider_id=provider_id,
        provider_kind=provider_kind,
        provider_origin=provider_origin,
    )

    if (
        provider_kind == _PROVIDER_KIND_ROOM_SHARED
        or provider_type == _PROVIDER_KIND_ROOM_SHARED
        or is_room_provider_id(provider_id)
    ):
        source_ref = _safe_dict(out.get("source_ref"))
        source_room_id = _safe_str(
            out.get("source_room_id")
            or _safe_dict(out.get("room_source")).get("room_id")
            or source_ref.get("room_id")
        )
        if source_room_id:
            out["source_room_id"] = source_room_id
            if out.get("room_source"):
                out["room_source"] = {
                    **_safe_dict(out.get("room_source")),
                    "room_id": source_room_id,
                }

    return out


def get_room_mcp_provider(provider_id: Any) -> Dict[str, Any]:
    key = _safe_str(provider_id).lower()
    if not key:
        return {}

    if is_room_provider_id(key):
        return _normalize_provider_descriptor_row(get_dynamic_room_mcp_provider(key))

    return _normalize_provider_descriptor_row(get_room_mcp_provider_registry().get(key) or {})


def resolve_room_mcp_provider(
    provider_id: Any = None,
    *,
    share_ref: Any = None,
    provider_snapshot: Any = None,
    imported_provider: Any = None,
    raw: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    resolved = _resolve_room_mcp_provider(
        provider_id=provider_id,
        share_ref=share_ref,
        provider_snapshot=provider_snapshot,
        imported_provider=imported_provider,
        raw=raw,
        get_room_mcp_provider_fn=get_room_mcp_provider,
    )
    return _normalize_provider_descriptor_row(resolved)


def _merge_provider_rows(base: Dict[str, Any], incoming: Dict[str, Any]) -> Dict[str, Any]:
    if not base:
        return _normalize_provider_descriptor_row(incoming)
    if not incoming:
        return _normalize_provider_descriptor_row(base)

    out = dict(base)

    for key in (
        "provider_kind",
        "provider_type",
        "provider_origin",
        "label",
        "description",
        "descriptor_version",
        "visibility_source",
        "grant_id",
        "artifact_id",
        "grant_state",
        "discovery_mode",
        "external_result_view",
        "share_ref",
        "source_room_id",
        "peer_id",
        "remote_peer_id",
        "target_peer_id",
        "source_peer_id",
        "federation_peer_id",
        "remote_user_id",
        "grant_peer_id",
        "grant_remote_user_id",
        "consumer_room_id",
        "server_tool",
        "requested_mode",
        "tool_name",
    ):
        if _safe_str(incoming.get(key)):
            out[key] = incoming.get(key)

    for key in (
        "tool_templates",
        "params_defaults",
        "params_schema",
        "auth_state",
        "availability",
        "boundary_hint",
        "room_source",
        "publication",
        "grant_scope",
        "grant_audience",
        "provider_origin_meta",
        "federation",
        "share_ref_payload",
        "invoke_contract",
        "capabilities",
        "source_ref",
    ):
        value = incoming.get(key)
        if value:
            out[key] = value

    if "source_observation_allowed" in incoming:
        out["source_observation_allowed"] = bool(incoming.get("source_observation_allowed"))

    if "granted_visible" in incoming:
        out["granted_visible"] = bool(incoming.get("granted_visible"))

    return _normalize_provider_descriptor_row(out)


def list_room_mcp_providers(args: Dict[str, Any] | None = None) -> List[Dict[str, Any]]:
    preset = [
        _normalize_provider_descriptor_row(v)
        for _, v in sorted(
            get_room_mcp_provider_registry().items(),
            key=lambda item: item[0],
        )
    ]

    dynamic_rooms = [
        _normalize_provider_descriptor_row(v)
        for v in list_published_room_provider_schemas(args)
    ]

    merged: List[Dict[str, Any]] = []
    index_by_provider_id: Dict[str, int] = {}

    for item in preset + dynamic_rooms:
        provider_id = _safe_str(item.get("provider_id")).lower()
        if not provider_id:
            continue

        if provider_id in index_by_provider_id:
            idx = index_by_provider_id[provider_id]
            merged[idx] = _merge_provider_rows(merged[idx], item)
            continue

        index_by_provider_id[provider_id] = len(merged)
        merged.append(dict(item))

    return merged


__all__ = [
    "ROOM_PROVIDER_PREFIX",
    "get_room_mcp_provider_registry",
    "get_room_mcp_provider",
    "resolve_imported_room_mcp_provider",
    "resolve_room_mcp_provider",
    "list_room_mcp_providers",
]

