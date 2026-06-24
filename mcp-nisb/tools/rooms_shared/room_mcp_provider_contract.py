from __future__ import annotations

from typing import Any, Dict

from .room_mcp_provider_descriptor_imported import (
    build_imported_room_mcp_provider_contract as _build_imported_room_mcp_provider_contract,
)
from .room_mcp_provider_descriptor_local import (
    build_room_shared_mcp_provider_contract as _build_room_shared_mcp_provider_contract,
    build_room_shared_mcp_share_ref as _build_room_shared_mcp_share_ref,
)
from .room_mcp_provider_invoke_contract import hydrate_provider_invoke_contract
from .room_mcp_role_binding_contract import normalize_room_role_mcp_contract
from .room_mcp_share_artifact import (
    ROOM_MCP_SHARE_REF_KIND,
    ROOM_MCP_SHARE_REF_PREFIX,
    ROOM_MCP_SHARE_REF_VERSION,
    ROOM_SHARED_PROVIDER_ORIGIN_IMPORTED,
    ROOM_SHARED_PROVIDER_ORIGIN_LOCAL,
    ROOM_SHARED_PROVIDER_TYPE,
    encode_room_shared_mcp_share_ref,
    parse_room_shared_mcp_share_ref,
)


_DESCRIPTOR_VERSION_FALLBACK = "v1"
_SERVER_TOOL_FALLBACK = "nisb_room_mcp_provider_call"
_REQUESTED_MODE_FALLBACK = "mcp"

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


def _is_room_shared_kind(value: Any) -> bool:
    return _safe_str(value) == ROOM_SHARED_PROVIDER_TYPE


def _canonical_provider_origin(
    *,
    provider_kind: str,
    provider_type: str,
    provider_origin: str,
    default_provider_origin: str,
) -> str:
    origin = _safe_str(provider_origin, default_provider_origin)

    if _is_room_shared_kind(provider_kind) or _is_room_shared_kind(provider_type):
        if origin in _LOCAL_ROOM_ORIGIN_ALIASES:
            return ROOM_SHARED_PROVIDER_ORIGIN_LOCAL
        return origin

    return origin


def _ensure_room_source_ref(out: Dict[str, Any]) -> Dict[str, Any]:
    provider_kind = _safe_str(out.get("provider_kind") or out.get("provider_type"))
    provider_type = _safe_str(out.get("provider_type") or provider_kind)

    if provider_kind != ROOM_SHARED_PROVIDER_TYPE and provider_type != ROOM_SHARED_PROVIDER_TYPE:
        return out

    provider_id = _safe_str(out.get("provider_id"))
    provider_origin = _canonical_provider_origin(
        provider_kind=provider_kind,
        provider_type=provider_type,
        provider_origin=_safe_str(out.get("provider_origin")),
        default_provider_origin=ROOM_SHARED_PROVIDER_ORIGIN_LOCAL,
    )

    if provider_origin:
        out["provider_origin"] = provider_origin

    room_source = _safe_dict(out.get("room_source"))
    source_room_id = _safe_str(
        out.get("source_room_id")
        or room_source.get("room_id")
        or out.get("room_id")
        or _safe_dict(out.get("source_ref")).get("room_id")
    )

    if not provider_id or not source_room_id:
        return out

    source_ref = _safe_dict(out.get("source_ref"))
    source_ref["kind"] = ROOM_SHARED_PROVIDER_TYPE
    source_ref["origin"] = provider_origin
    source_ref["provider_id"] = provider_id
    source_ref["room_id"] = source_room_id

    out["source_ref"] = source_ref
    out["source_room_id"] = source_room_id

    if room_source:
        out["room_source"] = {
            **room_source,
            "room_id": source_room_id,
        }

    return out


def normalize_room_mcp_provider_contract(
    raw: Dict[str, Any] | None = None,
    *,
    default_provider_type: str = "",
    default_provider_origin: str = "",
) -> Dict[str, Any]:
    schema = _safe_dict(raw)
    if not schema:
        return {}

    out = dict(schema)

    provider_type = _safe_str(
        out.get("provider_type"),
        default_provider_type,
    )
    provider_kind = _safe_str(
        out.get("provider_kind")
        or provider_type
        or default_provider_type
    )
    provider_origin = _canonical_provider_origin(
        provider_kind=provider_kind,
        provider_type=provider_type,
        provider_origin=_safe_str(out.get("provider_origin")),
        default_provider_origin=default_provider_origin,
    )

    if provider_type and not _safe_str(out.get("provider_type")):
        out["provider_type"] = provider_type
    if provider_kind and not _safe_str(out.get("provider_kind")):
        out["provider_kind"] = provider_kind
    if provider_origin:
        out["provider_origin"] = provider_origin

    room_source = _safe_dict(out.get("room_source"))
    if room_source:
        out["room_source"] = room_source

    publication = _safe_dict(out.get("publication"))
    if publication:
        out["publication"] = publication

    hydrated = hydrate_provider_invoke_contract(
        out,
        descriptor_version_fallback=_DESCRIPTOR_VERSION_FALLBACK,
        server_tool_fallback=_SERVER_TOOL_FALLBACK,
        requested_mode_fallback=_REQUESTED_MODE_FALLBACK,
        provider_kind_fallback=_safe_str(
            out.get("provider_kind")
            or out.get("provider_type")
            or default_provider_type
        ),
    )

    if not hydrated:
        return {}

    if not _safe_str(hydrated.get("provider_kind")):
        hydrated["provider_kind"] = _safe_str(
            hydrated.get("provider_type"),
            default_provider_type,
        )

    hydrated["provider_origin"] = _canonical_provider_origin(
        provider_kind=_safe_str(hydrated.get("provider_kind")),
        provider_type=_safe_str(hydrated.get("provider_type")),
        provider_origin=_safe_str(hydrated.get("provider_origin")),
        default_provider_origin=default_provider_origin,
    )

    return _ensure_room_source_ref(hydrated)


def build_room_shared_mcp_provider_contract(
    meta: Dict[str, Any],
    state: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    schema = _safe_dict(_build_room_shared_mcp_provider_contract(meta, state))
    if not schema:
        return {}

    room_source = {
        **_safe_dict(schema.get("room_source")),
        "room_id": _safe_str(_safe_dict(schema.get("room_source")).get("room_id"))
        or _safe_str(_safe_dict(meta).get("room_id")),
    }
    if room_source:
        schema["room_source"] = room_source
        schema["source_room_id"] = _safe_str(
            schema.get("source_room_id")
            or room_source.get("room_id")
        )

    publication = _safe_dict(_safe_dict(meta).get("room_mcp_publication"))
    if publication:
        schema["publication"] = publication

    if not _safe_str(schema.get("provider_type")):
        schema["provider_type"] = ROOM_SHARED_PROVIDER_TYPE

    if not _safe_str(schema.get("provider_kind")):
        schema["provider_kind"] = ROOM_SHARED_PROVIDER_TYPE

    schema["provider_origin"] = _canonical_provider_origin(
        provider_kind=_safe_str(schema.get("provider_kind")),
        provider_type=_safe_str(schema.get("provider_type")),
        provider_origin=_safe_str(schema.get("provider_origin")),
        default_provider_origin=ROOM_SHARED_PROVIDER_ORIGIN_LOCAL,
    )

    return normalize_room_mcp_provider_contract(
        schema,
        default_provider_type=ROOM_SHARED_PROVIDER_TYPE,
        default_provider_origin=ROOM_SHARED_PROVIDER_ORIGIN_LOCAL,
    )


def build_room_shared_mcp_share_ref(
    meta: Dict[str, Any],
    state: Dict[str, Any] | None = None,
    *,
    encoded: bool = True,
) -> Any:
    return _build_room_shared_mcp_share_ref(meta, state, encoded=encoded)


def build_imported_room_mcp_provider_contract(
    raw: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    schema = _safe_dict(_build_imported_room_mcp_provider_contract(raw))
    if not schema:
        return {}

    room_source = _safe_dict(schema.get("room_source"))
    if room_source:
        schema["room_source"] = room_source
        if not _safe_str(schema.get("source_room_id")):
            schema["source_room_id"] = _safe_str(room_source.get("room_id"))

    if not _safe_str(schema.get("provider_origin")):
        schema["provider_origin"] = ROOM_SHARED_PROVIDER_ORIGIN_IMPORTED

    if not _safe_str(schema.get("provider_type")):
        schema["provider_type"] = ROOM_SHARED_PROVIDER_TYPE

    if not _safe_str(schema.get("provider_kind")):
        schema["provider_kind"] = ROOM_SHARED_PROVIDER_TYPE

    return normalize_room_mcp_provider_contract(
        schema,
        default_provider_type=ROOM_SHARED_PROVIDER_TYPE,
        default_provider_origin=ROOM_SHARED_PROVIDER_ORIGIN_IMPORTED,
    )


__all__ = [
    "ROOM_SHARED_PROVIDER_TYPE",
    "ROOM_SHARED_PROVIDER_ORIGIN_LOCAL",
    "ROOM_SHARED_PROVIDER_ORIGIN_IMPORTED",
    "ROOM_MCP_SHARE_REF_KIND",
    "ROOM_MCP_SHARE_REF_VERSION",
    "ROOM_MCP_SHARE_REF_PREFIX",
    "build_room_shared_mcp_provider_contract",
    "build_room_shared_mcp_share_ref",
    "build_imported_room_mcp_provider_contract",
    "normalize_room_mcp_provider_contract",
    "parse_room_shared_mcp_share_ref",
    "encode_room_shared_mcp_share_ref",
    "normalize_room_role_mcp_contract",
]

