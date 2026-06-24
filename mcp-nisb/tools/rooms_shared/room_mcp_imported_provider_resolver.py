from __future__ import annotations

from typing import Any, Dict, Iterable, List

from .room_mcp_provider_contract import (
    ROOM_SHARED_PROVIDER_ORIGIN_IMPORTED,
    ROOM_SHARED_PROVIDER_TYPE,
    build_imported_room_mcp_provider_contract,
)
from .room_mcp_provider_invoke_contract import (
    hydrate_provider_invoke_contract,
)

_DESCRIPTOR_VERSION_FALLBACK = "v1"
_SERVER_TOOL_FALLBACK = "nisb_room_mcp_provider_call"
_REQUESTED_MODE_FALLBACK = "mcp"


def _safe_str(v: Any, default: str = "") -> str:
    if v is None:
        return default
    s = str(v).strip()
    return s if s else default


def _safe_dict(v: Any) -> Dict[str, Any]:
    return dict(v) if isinstance(v, dict) else {}


def _safe_list(v: Any) -> List[Any]:
    return list(v) if isinstance(v, list) else []


def _pick_non_empty(*values: Any, default: str = "") -> str:
    for item in values:
        s = _safe_str(item)
        if s:
            return s
    return default


def _pick_dict(*values: Any) -> Dict[str, Any]:
    for item in values:
        if isinstance(item, dict) and item:
            return dict(item)
    return {}


def _pick_list(*values: Any) -> List[Any]:
    for item in values:
        if isinstance(item, list) and item:
            return list(item)
    return []


def _normalize_provider_origin(value: Any) -> str:
    return _safe_str(value).lower()


def _is_imported_remote_origin(value: Any) -> bool:
    return _normalize_provider_origin(value).startswith("imported_remote")


def _normalize_publication(
    publication: Dict[str, Any],
    *,
    source_room_id: str = "",
) -> Dict[str, Any]:
    pub = dict(_safe_dict(publication))
    resolved_source_room_id = _pick_non_empty(
        source_room_id,
        pub.get("source_room_id"),
    )
    if resolved_source_room_id:
        pub["source_room_id"] = resolved_source_room_id
    return pub


def _normalize_room_source(
    room_source: Dict[str, Any],
    *,
    source_room_id: str = "",
    publication: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    out = dict(_safe_dict(room_source))
    pub = _safe_dict(publication)

    resolved_source_room_id = _pick_non_empty(
        source_room_id,
        out.get("room_id"),
        pub.get("source_room_id"),
    )
    if resolved_source_room_id:
        out["room_id"] = resolved_source_room_id

    return out


def _extract_source_room_id(
    *,
    source: Dict[str, Any],
    root: Dict[str, Any],
    room_source: Dict[str, Any],
    publication: Dict[str, Any],
) -> str:
    return _pick_non_empty(
        source.get("source_room_id"),
        root.get("source_room_id"),
        publication.get("source_room_id"),
        room_source.get("room_id"),
    )


def _has_explicit_imported_wrapper(root: Dict[str, Any]) -> bool:
    return bool(_safe_dict(root.get("imported_provider")))


def _has_imported_adapter_markers(
    *,
    share_ref: str,
    provider_origin: str,
    share_ref_payload: Dict[str, Any],
    federation: Dict[str, Any],
    root: Dict[str, Any],
) -> bool:
    return bool(
        share_ref
        or _is_imported_remote_origin(provider_origin)
        or share_ref_payload
        or federation
        or _has_explicit_imported_wrapper(root)
    )


def _hydrate_imported_provider_invoke_contract(meta: Dict[str, Any]) -> Dict[str, Any]:
    hydrated = hydrate_provider_invoke_contract(
        meta,
        descriptor_version_fallback=_DESCRIPTOR_VERSION_FALLBACK,
        server_tool_fallback=_SERVER_TOOL_FALLBACK,
        requested_mode_fallback=_REQUESTED_MODE_FALLBACK,
        provider_kind_fallback=ROOM_SHARED_PROVIDER_TYPE,
    )
    if not hydrated:
        return {}

    if not _safe_str(hydrated.get("provider_type")):
        hydrated["provider_type"] = ROOM_SHARED_PROVIDER_TYPE

    if not _safe_str(hydrated.get("provider_kind")):
        hydrated["provider_kind"] = _safe_str(
            hydrated.get("provider_type"),
            ROOM_SHARED_PROVIDER_TYPE,
        )

    if not _safe_str(hydrated.get("provider_origin")):
        hydrated["provider_origin"] = ROOM_SHARED_PROVIDER_ORIGIN_IMPORTED

    return hydrated


def _has_imported_shape(
    *,
    source: Dict[str, Any],
    root: Dict[str, Any],
    share_ref: str,
    provider_origin: str,
    share_ref_payload: Dict[str, Any],
    federation: Dict[str, Any],
) -> bool:
    grant_scope = _pick_dict(
        source.get("grant_scope"),
        root.get("grant_scope"),
        source.get("scope"),
        root.get("scope"),
    )
    grant_audience = _pick_dict(
        source.get("grant_audience"),
        root.get("grant_audience"),
    )
    grant_id = _pick_non_empty(source.get("grant_id"), root.get("grant_id"))
    artifact_id = _pick_non_empty(source.get("artifact_id"), root.get("artifact_id"))
    grant_state = _pick_non_empty(source.get("grant_state"), root.get("grant_state"))

    adapter_markers = _has_imported_adapter_markers(
        share_ref=share_ref,
        provider_origin=provider_origin,
        share_ref_payload=share_ref_payload,
        federation=federation,
        root=root,
    )

    grant_markers = bool(
        grant_scope
        or grant_audience
        or grant_id
        or artifact_id
        or grant_state
    )

    return adapter_markers or (grant_markers and _is_imported_remote_origin(provider_origin))


def _normalize_imported_room_provider_candidate(value: Any) -> Dict[str, Any]:
    root = _safe_dict(value)
    source = _safe_dict(
        root.get("provider_snapshot")
        or root.get("imported_provider")
        or root.get("provider")
        or root.get("provider_descriptor")
        or root
    )

    provider_id = _pick_non_empty(
        source.get("provider_id"),
        root.get("provider_id"),
    ).lower()

    provider_origin = _pick_non_empty(
        source.get("provider_origin"),
        root.get("provider_origin"),
    )
    share_ref = _pick_non_empty(
        source.get("share_ref"),
        root.get("share_ref"),
    )

    publication = _pick_dict(
        source.get("publication"),
        root.get("publication"),
    )
    room_source_raw = _pick_dict(
        source.get("room_source"),
        source.get("source_room"),
        root.get("room_source"),
        root.get("source_room"),
    )
    share_ref_payload = _pick_dict(
        source.get("share_ref_payload"),
        root.get("share_ref_payload"),
    )
    federation = _pick_dict(
        source.get("federation"),
        root.get("federation"),
    )

    source_room_id = _extract_source_room_id(
        source=source,
        root=root,
        room_source=room_source_raw,
        publication=publication,
    )
    publication = _normalize_publication(
        publication,
        source_room_id=source_room_id,
    )
    room_source = _normalize_room_source(
        room_source_raw,
        source_room_id=source_room_id,
        publication=publication,
    )

    imported_shape = _has_imported_shape(
        source=source,
        root=root,
        share_ref=share_ref,
        provider_origin=provider_origin,
        share_ref_payload=share_ref_payload,
        federation=federation,
    )

    provider_type = _pick_non_empty(
        source.get("provider_type"),
        root.get("provider_type"),
    )
    if provider_type != ROOM_SHARED_PROVIDER_TYPE and imported_shape and (provider_id or share_ref):
        provider_type = ROOM_SHARED_PROVIDER_TYPE

    if provider_type != ROOM_SHARED_PROVIDER_TYPE:
        return {}

    if not provider_id and not share_ref:
        return {}

    provider_kind = _pick_non_empty(
        source.get("provider_kind"),
        root.get("provider_kind"),
        provider_type,
    )

    source_invoke = _safe_dict(source.get("invoke_contract"))
    root_invoke = _safe_dict(root.get("invoke_contract"))

    params_schema = _pick_dict(
        source.get("params_schema"),
        root.get("params_schema"),
    )
    params_defaults = _pick_dict(
        source.get("params_defaults"),
        root.get("params_defaults"),
        source.get("params"),
        root.get("params"),
    )
    auth_state = _pick_dict(
        source.get("auth_state"),
        root.get("auth_state"),
    )
    availability = _pick_dict(
        source.get("availability"),
        root.get("availability"),
    )
    boundary_hint = _pick_dict(
        source.get("boundary_hint"),
        root.get("boundary_hint"),
    )
    grant_scope = _pick_dict(
        source.get("grant_scope"),
        root.get("grant_scope"),
        source.get("scope"),
        root.get("scope"),
    )
    grant_audience = _pick_dict(
        source.get("grant_audience"),
        root.get("grant_audience"),
    )
    provider_origin_meta = _pick_dict(
        source.get("provider_origin_meta"),
        root.get("provider_origin_meta"),
    )

    out = dict(source)
    out["provider_id"] = provider_id
    out["provider_type"] = provider_type
    out["provider_kind"] = provider_kind
    out["provider_origin"] = _normalize_provider_origin(
        provider_origin or ROOM_SHARED_PROVIDER_ORIGIN_IMPORTED
    )
    out["label"] = _pick_non_empty(
        source.get("label"),
        source.get("provider_label"),
        root.get("label"),
        root.get("provider_label"),
        publication.get("publish_label"),
        room_source.get("title"),
        provider_id,
    )
    out["description"] = _pick_non_empty(
        source.get("description"),
        root.get("description"),
        publication.get("publish_summary"),
    )
    out["tool_templates"] = _pick_list(
        source.get("tool_templates"),
        root.get("tool_templates"),
    )

    tool_name = _pick_non_empty(
        source.get("tool_name"),
        root.get("tool_name"),
        source_invoke.get("tool_name"),
        root_invoke.get("tool_name"),
    )
    requested_mode = _pick_non_empty(
        source.get("requested_mode"),
        root.get("requested_mode"),
        source_invoke.get("requested_mode"),
        root_invoke.get("requested_mode"),
    )
    server_tool = _pick_non_empty(
        source.get("server_tool"),
        root.get("server_tool"),
        source_invoke.get("server_tool"),
        root_invoke.get("server_tool"),
    )

    if tool_name:
        out["tool_name"] = tool_name
    if requested_mode:
        out["requested_mode"] = requested_mode
    if server_tool:
        out["server_tool"] = server_tool

    invoke_contract = _pick_dict(
        source_invoke,
        root_invoke,
    )
    if invoke_contract:
        out["invoke_contract"] = invoke_contract

    out["params_schema"] = params_schema
    out["params_defaults"] = params_defaults
    out["auth_state"] = auth_state
    out["availability"] = availability
    out["boundary_hint"] = boundary_hint
    out["room_source"] = room_source
    out["share_ref"] = share_ref
    out["descriptor_version"] = _pick_non_empty(
        source.get("descriptor_version"),
        root.get("descriptor_version"),
        source.get("version"),
        root.get("version"),
        _DESCRIPTOR_VERSION_FALLBACK,
    )

    if source_room_id:
        out["source_room_id"] = source_room_id
    if publication:
        out["publication"] = publication
    if grant_scope:
        out["grant_scope"] = grant_scope
    if grant_audience:
        out["grant_audience"] = grant_audience
    if provider_origin_meta:
        out["provider_origin_meta"] = provider_origin_meta
    if federation:
        out["federation"] = federation
    if share_ref_payload:
        out["share_ref_payload"] = share_ref_payload

    for key in (
        "grant_id",
        "artifact_id",
        "grant_state",
        "discovery_mode",
        "external_result_view",
        "peer_id",
        "remote_peer_id",
        "target_peer_id",
        "source_peer_id",
        "federation_peer_id",
        "remote_user_id",
        "grant_peer_id",
        "grant_remote_user_id",
        "consumer_room_id",
    ):
        value = _pick_non_empty(source.get(key), root.get(key))
        if value:
            out[key] = value

    if "source_observation_allowed" in source or "source_observation_allowed" in root:
        out["source_observation_allowed"] = bool(
            source.get("source_observation_allowed", root.get("source_observation_allowed"))
        )

    return _hydrate_imported_provider_invoke_contract(out)


def _merge_imported_resolution_fields(
    resolved: Dict[str, Any],
    candidate: Dict[str, Any],
) -> Dict[str, Any]:
    if not resolved:
        return dict(candidate or {})
    if not candidate:
        return dict(resolved or {})

    out = dict(resolved)
    incoming = dict(candidate)

    for key in (
        "provider_id",
        "provider_type",
        "provider_kind",
        "provider_origin",
        "label",
        "description",
        "share_ref",
        "descriptor_version",
        "grant_id",
        "artifact_id",
        "grant_state",
        "discovery_mode",
        "external_result_view",
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
        "tool_name",
        "requested_mode",
    ):
        if _safe_str(incoming.get(key)):
            out[key] = incoming.get(key)

    for key in (
        "room_source",
        "publication",
        "grant_scope",
        "grant_audience",
        "provider_origin_meta",
        "federation",
        "share_ref_payload",
        "invoke_contract",
    ):
        value = incoming.get(key)
        if value:
            out[key] = value

    for key in (
        "tool_templates",
        "params_schema",
        "params_defaults",
        "auth_state",
        "availability",
        "boundary_hint",
    ):
        current = out.get(key)
        incoming_value = incoming.get(key)
        if (not current) and incoming_value:
            out[key] = incoming_value

    if "source_observation_allowed" in incoming:
        out["source_observation_allowed"] = bool(incoming.get("source_observation_allowed"))

    room_source = _safe_dict(out.get("room_source"))
    source_room_id = _pick_non_empty(
        out.get("source_room_id"),
        room_source.get("room_id"),
        _safe_dict(out.get("publication")).get("source_room_id"),
    )
    if source_room_id:
        out["source_room_id"] = source_room_id
        room_source = _normalize_room_source(
            room_source,
            source_room_id=source_room_id,
            publication=_safe_dict(out.get("publication")),
        )
        if room_source:
            out["room_source"] = room_source

    if not _safe_str(out.get("provider_origin")):
        out["provider_origin"] = ROOM_SHARED_PROVIDER_ORIGIN_IMPORTED

    if not _safe_str(out.get("provider_type")):
        out["provider_type"] = ROOM_SHARED_PROVIDER_TYPE

    if not _safe_str(out.get("provider_kind")):
        out["provider_kind"] = _safe_str(out.get("provider_type"), ROOM_SHARED_PROVIDER_TYPE)

    if not _safe_str(out.get("descriptor_version")):
        out["descriptor_version"] = _DESCRIPTOR_VERSION_FALLBACK

    return _hydrate_imported_provider_invoke_contract(out)


def resolve_imported_room_mcp_provider(value: Any) -> Dict[str, Any]:
    candidate = _normalize_imported_room_provider_candidate(value)

    try:
        provider = build_imported_room_mcp_provider_contract(value)
    except Exception:
        provider = {}

    normalized_provider = _normalize_imported_room_provider_candidate(provider)

    if normalized_provider:
        return _merge_imported_resolution_fields(normalized_provider, candidate)

    if candidate:
        return dict(candidate)

    return {}


def _has_imported_provider_signal(
    *,
    share_ref: Any,
    raw: Dict[str, Any],
    provider_snapshot: Dict[str, Any],
    imported_provider: Dict[str, Any],
) -> bool:
    raw_share_ref_payload = _safe_dict(raw.get("share_ref_payload"))
    snapshot_share_ref_payload = _safe_dict(provider_snapshot.get("share_ref_payload"))
    imported_share_ref_payload = _safe_dict(imported_provider.get("share_ref_payload"))

    raw_federation = _safe_dict(raw.get("federation"))
    snapshot_federation = _safe_dict(provider_snapshot.get("federation"))
    imported_federation = _safe_dict(imported_provider.get("federation"))

    return bool(
        _safe_str(share_ref)
        or _safe_str(raw.get("share_ref"))
        or _safe_str(provider_snapshot.get("share_ref"))
        or _safe_str(imported_provider.get("share_ref"))
        or _is_imported_remote_origin(raw.get("provider_origin"))
        or _is_imported_remote_origin(provider_snapshot.get("provider_origin"))
        or _is_imported_remote_origin(imported_provider.get("provider_origin"))
        or raw_share_ref_payload
        or snapshot_share_ref_payload
        or imported_share_ref_payload
        or raw_federation
        or snapshot_federation
        or imported_federation
        or _has_explicit_imported_wrapper(raw)
    )


def _iter_imported_resolution_candidates(
    *,
    share_ref: Any,
    provider_snapshot: Any,
    imported_provider: Any,
    raw: Dict[str, Any],
) -> Iterable[Any]:
    raw_obj = _safe_dict(raw)

    if raw_obj:
        yield raw_obj

    if share_ref is not None:
        yield {"share_ref": share_ref}
    if provider_snapshot is not None:
        yield {"provider_snapshot": provider_snapshot}
    if imported_provider is not None:
        yield {"imported_provider": imported_provider}

    if share_ref is not None:
        yield share_ref
    if provider_snapshot is not None:
        yield provider_snapshot
    if imported_provider is not None:
        yield imported_provider


def _resolve_first_imported_candidate(
    *,
    share_ref: Any,
    provider_snapshot: Any,
    imported_provider: Any,
    raw: Dict[str, Any],
) -> Dict[str, Any]:
    for item in _iter_imported_resolution_candidates(
        share_ref=share_ref,
        provider_snapshot=provider_snapshot,
        imported_provider=imported_provider,
        raw=raw,
    ):
        try:
            resolved = resolve_imported_room_mcp_provider(item)
        except Exception:
            resolved = {}
        if resolved:
            return dict(resolved)

    return {}


def _build_imported_fallback_resolution(
    *,
    provider_id: Any,
    share_ref: Any,
    provider_snapshot: Any,
    imported_provider: Any,
    raw: Dict[str, Any],
) -> Dict[str, Any]:
    aggregate = dict(_safe_dict(raw))

    if share_ref is not None and not _safe_str(aggregate.get("share_ref")):
        aggregate["share_ref"] = share_ref

    if provider_snapshot is not None and not _safe_dict(aggregate.get("provider_snapshot")):
        aggregate["provider_snapshot"] = provider_snapshot

    if imported_provider is not None and not _safe_dict(aggregate.get("imported_provider")):
        aggregate["imported_provider"] = imported_provider

    if not _safe_str(aggregate.get("provider_id")) and _safe_str(provider_id):
        aggregate["provider_id"] = _safe_str(provider_id).lower()

    resolved = _normalize_imported_room_provider_candidate(aggregate)
    if resolved:
        return resolved

    key = _safe_str(provider_id).lower()
    if not key and not _safe_str(share_ref):
        return {}

    raw_obj = _safe_dict(raw)
    snapshot_obj = _safe_dict(provider_snapshot)
    imported_obj = _safe_dict(imported_provider)

    source = _pick_dict(
        imported_obj.get("room_source"),
        snapshot_obj.get("room_source"),
        raw_obj.get("room_source"),
    )
    publication = _pick_dict(
        imported_obj.get("publication"),
        snapshot_obj.get("publication"),
        raw_obj.get("publication"),
    )
    source_room_id = _pick_non_empty(
        imported_obj.get("source_room_id"),
        snapshot_obj.get("source_room_id"),
        raw_obj.get("source_room_id"),
        source.get("room_id"),
        publication.get("source_room_id"),
    )
    publication = _normalize_publication(publication, source_room_id=source_room_id)
    room_source = _normalize_room_source(
        source,
        source_room_id=source_room_id,
        publication=publication,
    )

    raw_invoke = _safe_dict(raw_obj.get("invoke_contract"))
    snapshot_invoke = _safe_dict(snapshot_obj.get("invoke_contract"))
    imported_invoke = _safe_dict(imported_obj.get("invoke_contract"))

    out: Dict[str, Any] = {
        "provider_id": key,
        "provider_type": ROOM_SHARED_PROVIDER_TYPE,
        "provider_kind": ROOM_SHARED_PROVIDER_TYPE,
        "provider_origin": ROOM_SHARED_PROVIDER_ORIGIN_IMPORTED,
        "label": _pick_non_empty(
            imported_obj.get("label"),
            imported_obj.get("provider_label"),
            snapshot_obj.get("label"),
            snapshot_obj.get("provider_label"),
            raw_obj.get("label"),
            raw_obj.get("provider_label"),
            publication.get("publish_label"),
            room_source.get("title"),
            key,
        ),
        "description": _pick_non_empty(
            imported_obj.get("description"),
            snapshot_obj.get("description"),
            raw_obj.get("description"),
            publication.get("publish_summary"),
        ),
        "share_ref": _pick_non_empty(
            share_ref,
            raw_obj.get("share_ref"),
            snapshot_obj.get("share_ref"),
            imported_obj.get("share_ref"),
        ),
        "descriptor_version": _pick_non_empty(
            imported_obj.get("descriptor_version"),
            snapshot_obj.get("descriptor_version"),
            raw_obj.get("descriptor_version"),
            _DESCRIPTOR_VERSION_FALLBACK,
        ),
        "room_source": room_source,
        "tool_templates": _pick_list(
            raw_obj.get("tool_templates"),
            snapshot_obj.get("tool_templates"),
            imported_obj.get("tool_templates"),
        ),
    }

    tool_name = _pick_non_empty(
        raw_obj.get("tool_name"),
        snapshot_obj.get("tool_name"),
        imported_obj.get("tool_name"),
        raw_invoke.get("tool_name"),
        snapshot_invoke.get("tool_name"),
        imported_invoke.get("tool_name"),
    )
    requested_mode = _pick_non_empty(
        raw_obj.get("requested_mode"),
        snapshot_obj.get("requested_mode"),
        imported_obj.get("requested_mode"),
        raw_invoke.get("requested_mode"),
        snapshot_invoke.get("requested_mode"),
        imported_invoke.get("requested_mode"),
    )
    server_tool = _pick_non_empty(
        raw_obj.get("server_tool"),
        snapshot_obj.get("server_tool"),
        imported_obj.get("server_tool"),
        raw_invoke.get("server_tool"),
        snapshot_invoke.get("server_tool"),
        imported_invoke.get("server_tool"),
    )

    if tool_name:
        out["tool_name"] = tool_name
    if requested_mode:
        out["requested_mode"] = requested_mode
    if server_tool:
        out["server_tool"] = server_tool

    invoke_contract = _pick_dict(
        raw_invoke,
        snapshot_invoke,
        imported_invoke,
    )
    if invoke_contract:
        out["invoke_contract"] = invoke_contract

    if source_room_id:
        out["source_room_id"] = source_room_id
    if publication:
        out["publication"] = publication

    for key_name in (
        "grant_id",
        "artifact_id",
        "grant_state",
        "discovery_mode",
        "external_result_view",
        "peer_id",
        "remote_peer_id",
        "target_peer_id",
        "source_peer_id",
        "federation_peer_id",
        "remote_user_id",
        "grant_peer_id",
        "grant_remote_user_id",
        "consumer_room_id",
    ):
        value = _pick_non_empty(
            raw_obj.get(key_name),
            snapshot_obj.get(key_name),
            imported_obj.get(key_name),
        )
        if value:
            out[key_name] = value

    for key_name in (
        "auth_state",
        "availability",
        "boundary_hint",
        "grant_scope",
        "grant_audience",
        "provider_origin_meta",
        "federation",
        "share_ref_payload",
        "params_schema",
        "params_defaults",
    ):
        value = _pick_dict(
            raw_obj.get(key_name),
            snapshot_obj.get(key_name),
            imported_obj.get(key_name),
        )
        if value:
            out[key_name] = value

    if "source_observation_allowed" in raw_obj or "source_observation_allowed" in snapshot_obj or "source_observation_allowed" in imported_obj:
        out["source_observation_allowed"] = bool(
            raw_obj.get(
                "source_observation_allowed",
                snapshot_obj.get(
                    "source_observation_allowed",
                    imported_obj.get("source_observation_allowed"),
                ),
            )
        )

    return _hydrate_imported_provider_invoke_contract(out)


def resolve_room_mcp_provider(
    provider_id: Any = None,
    *,
    share_ref: Any = None,
    provider_snapshot: Any = None,
    imported_provider: Any = None,
    raw: Dict[str, Any] | None = None,
    get_room_mcp_provider_fn=None,
) -> Dict[str, Any]:
    key = _safe_str(provider_id).lower()
    raw_obj = _safe_dict(raw)
    snapshot_obj = _safe_dict(provider_snapshot)
    imported_obj = _safe_dict(imported_provider)

    imported_signal = _has_imported_provider_signal(
        share_ref=share_ref,
        raw=raw_obj,
        provider_snapshot=snapshot_obj,
        imported_provider=imported_obj,
    )

    if imported_signal:
        resolved = _resolve_first_imported_candidate(
            share_ref=share_ref,
            provider_snapshot=provider_snapshot,
            imported_provider=imported_provider,
            raw=raw_obj,
        )
        if resolved:
            return dict(resolved)

        fallback_imported = _build_imported_fallback_resolution(
            provider_id=provider_id,
            share_ref=share_ref,
            provider_snapshot=provider_snapshot,
            imported_provider=imported_provider,
            raw=raw_obj,
        )
        if fallback_imported:
            return dict(fallback_imported)

        return {}

    if key and callable(get_room_mcp_provider_fn):
        resolved = get_room_mcp_provider_fn(key)
        if resolved:
            return dict(resolved)

    return {}
        

__all__ = [
    "_build_imported_fallback_resolution",
    "_has_imported_provider_signal",
    "_merge_imported_resolution_fields",
    "_normalize_imported_room_provider_candidate",
    "resolve_imported_room_mcp_provider",
    "resolve_room_mcp_provider",
]
