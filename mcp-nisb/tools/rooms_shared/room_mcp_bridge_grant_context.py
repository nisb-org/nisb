from __future__ import annotations

from typing import Any, Dict, List

from .room_request_bridge import (
    _safe_dict,
    _safe_str,
)


def _extract_provider_origin(provider_meta: Dict[str, Any], request_args: Dict[str, Any]) -> str:
    req = _safe_dict(request_args)
    mcp_binding = _safe_dict(req.get("mcp_binding"))
    provider_snapshot = _safe_dict(
        req.get("mcp_provider_snapshot")
        or req.get("provider_snapshot")
        or mcp_binding.get("provider_snapshot")
    )
    imported_provider = _safe_dict(
        req.get("imported_provider")
        or mcp_binding.get("imported_provider")
    )
    room_source = _safe_dict(provider_meta.get("room_source"))

    return _safe_str(
        provider_meta.get("provider_origin")
        or room_source.get("provider_origin")
        or mcp_binding.get("provider_origin")
        or provider_snapshot.get("provider_origin")
        or imported_provider.get("provider_origin")
    ).lower()

def _bridge_uses_external_grant_context(
    provider_meta: Dict[str, Any],
    request_args: Dict[str, Any],
) -> bool:
    origin = _extract_provider_origin(provider_meta, request_args)
    return origin.startswith("imported_remote")

def _current_provider_identity(provider_meta: Dict[str, Any]) -> Dict[str, str]:
    room_source = _safe_dict(provider_meta.get("room_source"))
    return {
        "provider_id": _safe_str(provider_meta.get("provider_id")),
        "source_room_id": _safe_str(
            provider_meta.get("source_room_id")
            or room_source.get("room_id")
        ),
    }


def _grant_matches_current_provider(
    provider_meta: Dict[str, Any],
    grant_like: Dict[str, Any],
) -> bool:
    obj = _safe_dict(grant_like)
    if not obj:
        return False

    current = _current_provider_identity(provider_meta)
    current_provider_id = _safe_str(current.get("provider_id"))
    current_source_room_id = _safe_str(current.get("source_room_id"))

    candidate_provider_id = _safe_str(obj.get("provider_id"))
    candidate_source_room_id = _safe_str(
        obj.get("source_room_id")
        or _safe_dict(obj.get("room_source")).get("room_id")
    )

    if not candidate_provider_id and not candidate_source_room_id:
        return False

    if candidate_provider_id and current_provider_id and candidate_provider_id != current_provider_id:
        return False

    if (
        candidate_source_room_id
        and current_source_room_id
        and candidate_source_room_id != current_source_room_id
    ):
        return False

    return True


def _share_ref_matches_current_provider(
    provider_meta: Dict[str, Any],
    share_ref: str,
) -> bool:
    ref = _safe_str(share_ref)
    if not ref:
        return False

    try:
        from .room_tools_mcp_providers import parse_room_mcp_grant_artifact

        artifact = _safe_dict(parse_room_mcp_grant_artifact(ref))
    except Exception:
        artifact = {}

    if not artifact:
        return True

    return _grant_matches_current_provider(provider_meta, artifact)

def _extract_share_ref(provider_meta: Dict[str, Any], request_args: Dict[str, Any]) -> str:
    if not _bridge_uses_external_grant_context(provider_meta, request_args):
        return ""


    req = _safe_dict(request_args)
    mcp_binding = _safe_dict(req.get("mcp_binding"))
    provider_snapshot = _safe_dict(
        req.get("mcp_provider_snapshot")
        or req.get("provider_snapshot")
        or mcp_binding.get("provider_snapshot")
    )
    imported_provider = _safe_dict(
        req.get("imported_provider")
        or mcp_binding.get("imported_provider")
    )
    room_source = _safe_dict(provider_meta.get("room_source"))


    for candidate in (
        provider_meta.get("share_ref"),
        room_source.get("share_ref"),
        mcp_binding.get("share_ref"),
        provider_snapshot.get("share_ref"),
        imported_provider.get("share_ref"),
        req.get("mcp_share_ref"),
        req.get("share_ref"),
    ):
        ref = _safe_str(candidate)
        if not ref:
            continue
        if _share_ref_matches_current_provider(provider_meta, ref):
            return ref


    return ""

def _resolve_live_bridge_grant_meta(
    *,
    provider_meta: Dict[str, Any],
    grant_like: Dict[str, Any],
    share_ref: str = "",
) -> Dict[str, Any]:
    seed = dict(_safe_dict(grant_like))
    ref = _safe_str(share_ref)
    artifact: Dict[str, Any] = {}

    if ref:
        try:
            from .room_mcp_grant_service import parse_room_mcp_grant_artifact

            artifact = _safe_dict(parse_room_mcp_grant_artifact(ref))
        except Exception:
            artifact = {}

    if artifact:
        merged_seed = dict(artifact)
        merged_seed.update(seed)
        seed = merged_seed

    if not seed:
        return {}

    current = _current_provider_identity(provider_meta)
    current_provider_id = _safe_str(current.get("provider_id"))
    current_source_room_id = _safe_str(current.get("source_room_id"))

    grant_id = _safe_str(seed.get("grant_id"))
    artifact_id = _safe_str(seed.get("artifact_id"))
    source_room_id = _safe_str(seed.get("source_room_id") or current_source_room_id)

    if ref and not _safe_str(seed.get("share_ref")):
        seed["share_ref"] = ref

    if (
        (current_provider_id or current_source_room_id)
        and (seed.get("provider_id") or seed.get("source_room_id"))
        and not _grant_matches_current_provider(provider_meta, seed)
    ):
        seed["_live_grant_resolved"] = False
        seed["_live_grant_skipped_reason"] = "grant_provider_mismatch"
        return seed

    if not source_room_id or (not grant_id and not artifact_id):
        seed["_live_grant_resolved"] = False
        seed["_live_grant_skipped_reason"] = "missing_live_grant_lookup_key"
        return seed

    try:
        from .room_mcp_grant_service import get_room_mcp_grant_by_id

        live = _safe_dict(
            get_room_mcp_grant_by_id(
                source_room_id=source_room_id,
                grant_id=grant_id,
                artifact_id=artifact_id,
            )
        )
    except Exception as exc:
        seed["_live_grant_resolved"] = False
        seed["_live_grant_error"] = str(exc)
        return seed

    if not live:
        seed["_live_grant_resolved"] = False
        seed["_live_grant_missing"] = True
        return seed

    snapshot_state = _safe_str(seed.get("grant_state"))
    live_state = _safe_str(live.get("grant_state"))

    merged = dict(seed)
    merged.update(live)
    merged["_live_grant_resolved"] = True
    merged["live_grant_state"] = live_state

    if snapshot_state and live_state and snapshot_state != live_state:
        merged["grant_state_snapshot"] = snapshot_state

    if ref and not _safe_str(merged.get("share_ref")):
        merged["share_ref"] = ref

    return merged


def _extract_bridge_grant_meta(
    *,
    provider_meta: Dict[str, Any],
    request_args: Dict[str, Any],
) -> Dict[str, Any]:
    if not _bridge_uses_external_grant_context(provider_meta, request_args):
        return {}


    req = _safe_dict(request_args)
    mcp_binding = _safe_dict(req.get("mcp_binding"))
    provider_snapshot = _safe_dict(
        req.get("mcp_provider_snapshot")
        or req.get("provider_snapshot")
        or mcp_binding.get("provider_snapshot")
    )
    imported_provider = _safe_dict(
        req.get("imported_provider")
        or mcp_binding.get("imported_provider")
    )


    share_ref = _extract_share_ref(provider_meta, request_args)


    direct_meta = _safe_dict(
        provider_meta.get("_grant_meta")
        or provider_meta.get("grant_meta")
        or provider_meta.get("grant")
    )
    if direct_meta:
        resolved = _resolve_live_bridge_grant_meta(
            provider_meta=provider_meta,
            grant_like=direct_meta,
            share_ref=share_ref,
        )
        if _safe_str(resolved.get("_live_grant_skipped_reason")) == "grant_provider_mismatch":
            return {}
        return resolved


    for candidate in (
        req.get("_room_mcp_grant"),
        req.get("grant"),
        req.get("grant_meta"),
        mcp_binding.get("grant"),
        mcp_binding.get("grant_meta"),
        provider_snapshot.get("_grant_meta"),
        provider_snapshot.get("grant"),
        provider_snapshot.get("grant_meta"),
        imported_provider.get("_grant_meta"),
        imported_provider.get("grant"),
        imported_provider.get("grant_meta"),
    ):
        obj = _safe_dict(candidate)
        if not obj:
            continue


        resolved = _resolve_live_bridge_grant_meta(
            provider_meta=provider_meta,
            grant_like=obj,
            share_ref=share_ref,
        )
        if _safe_str(resolved.get("_live_grant_skipped_reason")) == "grant_provider_mismatch":
            continue
        return resolved


    if not share_ref:
        return {}


    try:
        from .room_mcp_grant_service import parse_room_mcp_grant_artifact


        artifact = _safe_dict(parse_room_mcp_grant_artifact(share_ref))
    except Exception:
        artifact = {}


    if not artifact:
        return {}


    resolved = _resolve_live_bridge_grant_meta(
        provider_meta=provider_meta,
        grant_like=artifact,
        share_ref=share_ref,
    )
    if _safe_str(resolved.get("_live_grant_skipped_reason")) == "grant_provider_mismatch":
        return {}


    return resolved

def _extract_bridge_actor_user_id(request_args: Dict[str, Any]) -> str:
    req = _safe_dict(request_args)
    for key in (
        "_room_mcp_actor_user_id",
        "actor_user_id",
        "user_id",
        "sender_user_id",
        "sender",
    ):
        value = _safe_str(req.get(key))
        if value:
            return value
    return ""


def _extract_basepath(request_args: Dict[str, Any]) -> str:
    req = _safe_dict(request_args)
    return _safe_str(
        req.get("basepath")
        or req.get("base_path")
        or req.get("basePath")
    )


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        if value is None:
            return default
        if isinstance(value, bool):
            return int(value)
        return int(str(value).strip())
    except Exception:
        return default


def _resolve_imported_remote_timeout_ms(
    request_args: Dict[str, Any],
    *,
    default_timeout_ms: int = 180000,
) -> int:
    req = _safe_dict(request_args)
    mcp_binding = _safe_dict(req.get("mcp_binding"))
    params = _safe_dict(mcp_binding.get("params"))

    for candidate in (
        req.get("_room_mcp_timeout_ms_effective"),
        req.get("_room_mcp_timeout_ms_requested"),
        req.get("timeout_ms"),
        req.get("_timeout_ms"),
        req.get("request_timeout_ms"),
        req.get("bridge_timeout_ms"),
        mcp_binding.get("timeout_ms"),
        params.get("timeout_ms"),
    ):
        value = _safe_int(candidate, 0)
        if value > 0:
            return max(3000, min(180000, value))

    return max(3000, min(180000, default_timeout_ms))


def _build_bridge_mcp_binding(
    *,
    provider_meta: Dict[str, Any],
    provider_origin: str,
    question: str,
    share_ref: str = "",
    provider_snapshot: Dict[str, Any] | None = None,
    imported_provider: Dict[str, Any] | None = None,
    grant_meta: Dict[str, Any] | None = None,
    base_binding: Dict[str, Any] | None = None,
    apply_mcp_binding_question_aliases,
) -> Dict[str, Any]:
    binding = apply_mcp_binding_question_aliases(_safe_dict(base_binding), question)
    external_grant_context = _safe_str(provider_origin).lower().startswith("imported_remote")
    resolved_grant = _safe_dict(grant_meta) if external_grant_context else {}

    for key in (
        "provider_id",
        "provider_type",
        "provider_origin",
        "share_ref",
        "grant_id",
        "artifact_id",
        "grant_state",
        "grant_mode",
        "discovery_mode",
        "resolution_source",
        "external_result_view",
        "grant_meta",
        "grant",
        "provider_snapshot",
        "imported_provider",
    ):
        binding.pop(key, None)

    binding["provider_id"] = _safe_str(provider_meta.get("provider_id"))
    binding["provider_type"] = _safe_str(provider_meta.get("provider_type"))
    binding["provider_origin"] = _safe_str(provider_origin or provider_meta.get("provider_origin"))

    if not external_grant_context:
        return binding

    if share_ref:
        binding["share_ref"] = _safe_str(share_ref)

    if provider_snapshot:
        binding["provider_snapshot"] = dict(provider_snapshot)

    if imported_provider:
        binding["imported_provider"] = dict(imported_provider)

    if resolved_grant:
        grant_id = _safe_str(resolved_grant.get("grant_id"))
        artifact_id = _safe_str(resolved_grant.get("artifact_id"))
        resolution_source = _safe_str(resolved_grant.get("resolution_source"))
        grant_state = _safe_str(resolved_grant.get("grant_state"))
        grant_mode = _safe_str(resolved_grant.get("grant_mode"))
        discovery_mode = _safe_str(resolved_grant.get("discovery_mode"))
        external_result_view = _safe_str(resolved_grant.get("external_result_view"))

        if grant_id:
            binding["grant_id"] = grant_id
        if artifact_id:
            binding["artifact_id"] = artifact_id
        if resolution_source:
            binding["resolution_source"] = resolution_source
        if grant_state:
            binding["grant_state"] = grant_state
        if grant_mode:
            binding["grant_mode"] = grant_mode
        if discovery_mode:
            binding["discovery_mode"] = discovery_mode
        if external_result_view:
            binding["external_result_view"] = external_result_view

        binding["grant_meta"] = dict(resolved_grant)
        binding["grant"] = dict(resolved_grant)

    return binding


def _lookup_remote_peer_id_from_joined_rooms(
    *,
    basepath: str,
    source_room_id: str,
) -> str:
    basepath = _safe_str(basepath)
    source_room_id = _safe_str(source_room_id)
    if not basepath or not source_room_id:
        return ""

    try:
        from ..federation.tools import _load_joined_rooms
        doc = _load_joined_rooms(basepath)
    except Exception:
        return ""

    rooms = doc.get("rooms") if isinstance(doc, dict) else []
    if not isinstance(rooms, list):
        return ""

    owner_matches: List[Dict[str, Any]] = []
    room_matches: List[Dict[str, Any]] = []

    for row in rooms:
        if not isinstance(row, dict):
            continue

        peer_id = _safe_str(row.get("peer_id"))
        if not peer_id:
            continue

        owner_room_id = _safe_str(row.get("owner_room_id"))
        joined_room_id = _safe_str(row.get("room_id"))

        if owner_room_id and owner_room_id == source_room_id:
            owner_matches.append(row)
            continue

        if joined_room_id and joined_room_id == source_room_id:
            room_matches.append(row)

    for bucket in (owner_matches, room_matches):
        if not bucket:
            continue

        bucket.sort(
            key=lambda item: (
                _safe_str(item.get("last_entered_at")),
                _safe_str(item.get("updated_at")),
                _safe_str(item.get("joined_at")),
            ),
            reverse=True,
        )

        peer_id = _safe_str(bucket[0].get("peer_id"))
        if peer_id:
            return peer_id

    return ""


def _extract_imported_remote_target_identity(
    *,
    provider_meta: Dict[str, Any],
    request_args: Dict[str, Any],
) -> Dict[str, Any]:
    req = _safe_dict(request_args)
    mcp_binding = _safe_dict(req.get("mcp_binding"))
    provider_snapshot = _safe_dict(
        req.get("mcp_provider_snapshot")
        or req.get("provider_snapshot")
        or mcp_binding.get("provider_snapshot")
    )
    imported_provider = _safe_dict(
        req.get("imported_provider")
        or mcp_binding.get("imported_provider")
    )
    room_source = _safe_dict(provider_meta.get("room_source"))
    grant_meta = _extract_bridge_grant_meta(
        provider_meta=provider_meta,
        request_args=request_args,
    )
    grant_audience = _safe_dict(
        grant_meta.get("audience")
        or provider_meta.get("grant_audience")
        or provider_snapshot.get("grant_audience")
        or imported_provider.get("grant_audience")
    )

    return {
        "source_room_id": _safe_str(
            room_source.get("room_id")
            or grant_meta.get("source_room_id")
            or provider_snapshot.get("source_room_id")
            or imported_provider.get("source_room_id")
            or req.get("_room_mcp_source_room_id")
        ),
        "remote_user_id": _safe_str(
            grant_audience.get("remote_user_id")
            or req.get("remote_user_id")
            or req.get("_federation_remote_user_id")
            or provider_snapshot.get("remote_user_id")
            or imported_provider.get("remote_user_id")
            or room_source.get("owner_user_id")
        ),
        "peer_id": _safe_str(
            grant_audience.get("peer_id")
            or grant_audience.get("remote_peer_id")
            or grant_audience.get("target_peer_id")
            or grant_audience.get("federation_peer_id")
        ),
        "grant_id": _safe_str(grant_meta.get("grant_id")),
        "artifact_id": _safe_str(grant_meta.get("artifact_id")),
    }


def _resolve_imported_remote_peer_via_federation(
    *,
    basepath: str,
    provider_meta: Dict[str, Any],
    request_args: Dict[str, Any],
) -> Dict[str, Any]:
    target_identity = _extract_imported_remote_target_identity(
        provider_meta=provider_meta,
        request_args=request_args,
    )

    requested_peer_id = _safe_str(
        _safe_dict(request_args).get("peer_id")
        or _safe_dict(request_args).get("_federation_peer_id")
        or target_identity.get("peer_id")
    )

    try:
        from ..federation.tools import _resolve_peer_id_for_room_mcp_grant

        result = _resolve_peer_id_for_room_mcp_grant(
            basepath=basepath,
            source_room_id=_safe_str(target_identity.get("source_room_id")),
            remote_user_id=_safe_str(target_identity.get("remote_user_id")),
            target_peer_id=_safe_str(target_identity.get("peer_id")),
            requested_peer_id=requested_peer_id,
        )
        if isinstance(result, dict):
            result.setdefault("target_identity", target_identity)
            return result
    except Exception as e:
        return {
            "success": False,
            "peer_id": "",
            "error_code": "peer_resolve_exception",
            "error_kind": "peer_resolution",
            "message": str(e),
            "target_identity": target_identity,
        }

    return {
        "success": False,
        "peer_id": "",
        "error_code": "missing_remote_peer_id",
        "error_kind": "peer_resolution",
        "message": "peer resolve returned empty result",
        "target_identity": target_identity,
    }


def _extract_imported_remote_peer_id(
    *,
    provider_meta: Dict[str, Any],
    request_args: Dict[str, Any],
    basepath: str = "",
) -> str:
    req = _safe_dict(request_args)
    mcp_binding = _safe_dict(req.get("mcp_binding"))
    provider_snapshot = _safe_dict(
        req.get("mcp_provider_snapshot")
        or req.get("provider_snapshot")
        or mcp_binding.get("provider_snapshot")
    )
    imported_provider = _safe_dict(
        req.get("imported_provider")
        or mcp_binding.get("imported_provider")
    )
    room_source = _safe_dict(provider_meta.get("room_source"))

    provider_origin_meta = _safe_dict(provider_meta.get("provider_origin_meta"))
    provider_snapshot_origin_meta = _safe_dict(provider_snapshot.get("provider_origin_meta"))
    imported_origin_meta = _safe_dict(imported_provider.get("provider_origin_meta"))

    provider_meta_federation = _safe_dict(provider_meta.get("federation"))
    provider_snapshot_federation = _safe_dict(provider_snapshot.get("federation"))
    imported_provider_federation = _safe_dict(imported_provider.get("federation"))

    share_ref_payload = _safe_dict(
        provider_meta.get("share_ref_payload")
        or provider_snapshot.get("share_ref_payload")
        or imported_provider.get("share_ref_payload")
    )

    grant_meta = _extract_bridge_grant_meta(
        provider_meta=provider_meta,
        request_args=request_args,
    )
    grant_audience = _safe_dict(
        grant_meta.get("audience")
        or provider_meta.get("grant_audience")
        or provider_snapshot.get("grant_audience")
        or imported_provider.get("grant_audience")
    )
    grant_federation = _safe_dict(grant_meta.get("federation"))

    candidates = [
        req.get("_federation_peer_id"),
        req.get("federation_peer_id"),
        req.get("remote_peer_id"),
        req.get("peer_id"),
        req.get("target_peer_id"),
        req.get("source_peer_id"),
        req.get("provider_peer_id"),

        grant_audience.get("peer_id"),
        grant_audience.get("remote_peer_id"),
        grant_audience.get("target_peer_id"),
        grant_audience.get("federation_peer_id"),
        grant_meta.get("peer_id"),
        grant_meta.get("remote_peer_id"),
        grant_meta.get("target_peer_id"),
        grant_meta.get("federation_peer_id"),
        grant_federation.get("peer_id"),
        grant_federation.get("remote_peer_id"),
        grant_federation.get("target_peer_id"),

        req.get("_federation_remote_peer_id"),
        provider_meta.get("remote_peer_id"),
        provider_meta.get("peer_id"),
        provider_meta.get("target_peer_id"),
        provider_meta.get("source_peer_id"),
        provider_meta.get("provider_peer_id"),
        provider_meta.get("federation_peer_id"),
        provider_meta.get("_federation_peer_id"),
        room_source.get("remote_peer_id"),
        room_source.get("peer_id"),
        room_source.get("target_peer_id"),
        room_source.get("source_peer_id"),
        room_source.get("provider_peer_id"),
        room_source.get("federation_peer_id"),
        room_source.get("_federation_peer_id"),
        imported_provider.get("remote_peer_id"),
        imported_provider.get("peer_id"),
        imported_provider.get("target_peer_id"),
        imported_provider.get("source_peer_id"),
        imported_provider.get("provider_peer_id"),
        imported_provider.get("federation_peer_id"),
        imported_provider.get("_federation_peer_id"),
        provider_snapshot.get("remote_peer_id"),
        provider_snapshot.get("peer_id"),
        provider_snapshot.get("target_peer_id"),
        provider_snapshot.get("source_peer_id"),
        provider_snapshot.get("provider_peer_id"),
        provider_snapshot.get("federation_peer_id"),
        provider_snapshot.get("_federation_peer_id"),
        mcp_binding.get("remote_peer_id"),
        mcp_binding.get("peer_id"),
        mcp_binding.get("target_peer_id"),
        mcp_binding.get("source_peer_id"),
        mcp_binding.get("provider_peer_id"),
        mcp_binding.get("federation_peer_id"),
        mcp_binding.get("_federation_peer_id"),
        provider_origin_meta.get("remote_peer_id"),
        provider_origin_meta.get("peer_id"),
        provider_origin_meta.get("target_peer_id"),
        provider_origin_meta.get("source_peer_id"),
        provider_snapshot_origin_meta.get("remote_peer_id"),
        provider_snapshot_origin_meta.get("peer_id"),
        provider_snapshot_origin_meta.get("target_peer_id"),
        provider_snapshot_origin_meta.get("source_peer_id"),
        imported_origin_meta.get("remote_peer_id"),
        imported_origin_meta.get("peer_id"),
        imported_origin_meta.get("target_peer_id"),
        imported_origin_meta.get("source_peer_id"),
        provider_meta_federation.get("peer_id"),
        provider_meta_federation.get("remote_peer_id"),
        provider_meta_federation.get("target_peer_id"),
        provider_snapshot_federation.get("peer_id"),
        provider_snapshot_federation.get("remote_peer_id"),
        provider_snapshot_federation.get("target_peer_id"),
        imported_provider_federation.get("peer_id"),
        imported_provider_federation.get("remote_peer_id"),
        imported_provider_federation.get("target_peer_id"),
        share_ref_payload.get("peer_id"),
        share_ref_payload.get("remote_peer_id"),
        share_ref_payload.get("target_peer_id"),
        share_ref_payload.get("source_peer_id"),
    ]

    for value in candidates:
        s = _safe_str(value)
        if s:
            return s

    source_room_id = _safe_str(
        room_source.get("room_id")
        or grant_meta.get("source_room_id")
    )
    if basepath and source_room_id:
        peer_id = _lookup_remote_peer_id_from_joined_rooms(
            basepath=basepath,
            source_room_id=source_room_id,
        )
        if peer_id:
            return peer_id

    return ""


__all__ = [
    "_bridge_uses_external_grant_context",
    "_build_bridge_mcp_binding",
    "_extract_basepath",
    "_extract_bridge_actor_user_id",
    "_extract_bridge_grant_meta",
    "_extract_imported_remote_peer_id",
    "_extract_imported_remote_target_identity",
    "_extract_provider_origin",
    "_extract_share_ref",
    "_lookup_remote_peer_id_from_joined_rooms",
    "_resolve_imported_remote_peer_via_federation",
    "_resolve_imported_remote_timeout_ms",
    "_resolve_live_bridge_grant_meta",
    "_safe_int",
]
