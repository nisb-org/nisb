from __future__ import annotations

from typing import Any, Dict, List

from .room_contracts import ensure_request_id, require_safe_id
from .room_mcp_grant_service import (
    ROOM_MCP_GRANT_ARTIFACT_PREFIX,
    ROOM_MCP_GRANTS_FILENAME,
    _build_grant_artifact_payload,
    _build_grant_route_fields,
    _build_issue_event,
    _build_publication_record,
    _build_revoke_event,
    _encode_grant_artifact,
    _extract_issue_audience,
    _load_grants_doc,
    _normalize_grant_mode,
    _normalize_grant_row,
    _normalize_scope,
    _save_grants_doc,
    get_room_mcp_grant_by_id,
    parse_room_mcp_grant_artifact,
)
from .room_mcp_provider_contract import (
    build_imported_room_mcp_provider_contract,
    build_room_shared_mcp_provider_contract,
    build_room_shared_mcp_share_ref,
    parse_room_shared_mcp_share_ref,
)
from .room_store import (
    append_room_event,
    can_edit_room_state,
    ensure_room_exists,
    get_basepath,
    load_state_doc,
    touch_room_updated_at,
    uid_from_ctx_or_basepath,
)
from .room_tool_common import _build_tool_result_item, _formal_envelope, _permission_denied


def _safe_dict(v: Any) -> Dict[str, Any]:
    return v if isinstance(v, dict) else {}


def _safe_list(v: Any) -> List[Any]:
    return list(v) if isinstance(v, list) else []


def _safe_str(v: Any, default: str = "") -> str:
    if v is None:
        return default
    s = str(v).strip()
    return s if s else default


def _provider_registry_summary(providers: List[Dict[str, Any]]) -> Dict[str, Any]:
    total = len(providers)
    available = 0
    unavailable = 0
    auth_required = 0
    auth_configured = 0
    auth_missing = 0

    for item in providers:
        row = item if isinstance(item, dict) else {}
        availability = row.get("availability") if isinstance(row.get("availability"), dict) else {}
        auth_state = row.get("auth_state") if isinstance(row.get("auth_state"), dict) else {}

        if availability.get("available", True):
            available += 1
        else:
            unavailable += 1

        if auth_state.get("required", False):
            auth_required += 1
            if auth_state.get("configured", False):
                auth_configured += 1
            else:
                auth_missing += 1

    return {
        "total": total,
        "available": available,
        "unavailable": unavailable,
        "auth_required": auth_required,
        "auth_configured": auth_configured,
        "auth_missing": auth_missing,
    }


def _publication_disabled_envelope(rid: str, room_id: str) -> Dict[str, Any]:
    return _formal_envelope(
        request_id=rid,
        conv_id=room_id,
        response="room mcp publication is disabled",
        status="error",
        message="room mcp publication disabled",
        tool_calls=[],
        tool_results=[
            _build_tool_result_item(
                "room_mcp_share_ref",
                room_id=room_id,
                share_ref="",
                provider={},
                error="room_mcp_publication_disabled",
            )
        ],
    )


def nisb_room_mcp_provider_list(args: Dict[str, Any]) -> Dict[str, Any]:
    from .room_mcp_provider_registry import list_room_mcp_providers

    rid = ensure_request_id(args)
    room_id = str(args.get("room_id") or "").strip()

    providers = list_room_mcp_providers(args)
    summary = _provider_registry_summary(providers)

    return _formal_envelope(
        request_id=rid,
        conv_id=room_id,
        response=(
            f"Loaded {summary.get('total', 0)} MCP providers, "
            f"{summary.get('available', 0)} available, "
            f"{summary.get('unavailable', 0)} unavailable."
        ),
        status="success",
        message="room mcp provider registry loaded",
        tool_calls=[],
        tool_results=[
            _build_tool_result_item(
                "room_mcp_provider_registry",
                room_id=room_id,
                providers=providers,
                summary=summary,
                total=summary.get("total", 0),
                available=summary.get("available", 0),
                unavailable=summary.get("unavailable", 0),
                auth_required=summary.get("auth_required", 0),
                auth_configured=summary.get("auth_configured", 0),
                auth_missing=summary.get("auth_missing", 0),
            )
        ],
    )


def nisb_room_mcp_publication_get(args: Dict[str, Any]) -> Dict[str, Any]:
    basepath = get_basepath(args)
    uid = uid_from_ctx_or_basepath(basepath, args)
    rid = ensure_request_id(args)

    room_id = require_safe_id("room_id", args.get("room_id"))
    meta = ensure_room_exists(room_id)
    if meta and not can_edit_room_state(uid, meta):
        return _permission_denied(rid, room_id)

    state = load_state_doc(room_id)
    publication = _build_publication_record(meta, state)

    return _formal_envelope(
        request_id=rid,
        conv_id=room_id,
        response="room mcp publication loaded",
        status="success",
        message="room mcp publication loaded",
        tool_calls=[],
        tool_results=[
            _build_tool_result_item(
                "room_mcp_publication",
                room_id=room_id,
                publication=publication,
                provider_id=_safe_str(publication.get("provider_id")),
                source_room_id=_safe_str(publication.get("source_room_id")),
                publication_state=_safe_str(publication.get("publication_state")),
                visibility_mode=_safe_str(publication.get("visibility_mode")),
            )
        ],
    )


def nisb_room_mcp_share_ref_issue(args: Dict[str, Any]) -> Dict[str, Any]:
    basepath = get_basepath(args)
    uid = uid_from_ctx_or_basepath(basepath, args)
    rid = ensure_request_id(args)

    room_id = require_safe_id("room_id", args.get("room_id"))
    meta = ensure_room_exists(room_id)
    if meta and not can_edit_room_state(uid, meta):
        return _permission_denied(rid, room_id)

    state = load_state_doc(room_id)
    publication = _build_publication_record(meta, state)
    if not bool(publication.get("publish_enabled")) or _safe_str(publication.get("publication_state")) != "active":
        return _publication_disabled_envelope(rid, room_id)

    provider = build_room_shared_mcp_provider_contract(meta, state)
    legacy_share_ref = build_room_shared_mcp_share_ref(meta, state, encoded=True)
    audience = _extract_issue_audience(args)
    route_identity = _build_grant_route_fields(audience)
    scope = _normalize_scope(args.get("scope"))
    grant_mode = _normalize_grant_mode(args.get("grant_mode"))

    grant = _normalize_grant_row(
        {
            "grant_id": args.get("grant_id") or "",
            "artifact_id": args.get("artifact_id") or "",
            "provider_id": _safe_str(provider.get("provider_id")),
            "source_room_id": room_id,
            "grant_mode": grant_mode,
            "discovery_mode": _safe_str(args.get("discovery_mode"), "granted_visible") or "granted_visible",
            "grant_state": "active",
            "audience": audience,
            "scope": scope,
            "issued_at": args.get("issued_at") or "",
            "expires_at": _safe_str(args.get("expires_at")),
            "revocable": bool(args.get("revocable", True)),
            "boundary_hint": _safe_str(publication.get("boundary_hint")),
            "resolution_source": "grant_artifact",
            "external_result_view": _safe_str(scope.get("result_view"), "final_result_only"),
            "source_observation_allowed": bool(scope.get("observe_source_room", False)),
            "peer_id": _safe_str(route_identity.get("peer_id")),
            "remote_peer_id": _safe_str(route_identity.get("remote_peer_id")),
            "target_peer_id": _safe_str(route_identity.get("target_peer_id")),
            "source_peer_id": _safe_str(route_identity.get("source_peer_id")),
            "federation_peer_id": _safe_str(route_identity.get("federation_peer_id")),
            "remote_user_id": _safe_str(route_identity.get("remote_user_id")),
            "consumer_room_id": _safe_str(route_identity.get("consumer_room_id")),
            "uid": _safe_str(route_identity.get("uid")),
            "remote_label": _safe_str(route_identity.get("remote_label")),
        }
    )

    if not _safe_str(grant.get("grant_id")):
        grant["grant_id"] = _safe_str(args.get("grant_id")) or ""
    if not _safe_str(grant.get("grant_id")):
        from .room_contracts import new_id, utc_iso
        grant["grant_id"] = new_id("grant")
        grant["issued_at"] = _safe_str(grant.get("issued_at")) or utc_iso()

    if not _safe_str(grant.get("artifact_id")):
        from .room_contracts import new_id
        grant["artifact_id"] = new_id("artifact")

    artifact_payload = _build_grant_artifact_payload(
        grant=grant,
        room_id=room_id,
        legacy_share_ref=legacy_share_ref,
    )
    artifact_ref = _encode_grant_artifact(artifact_payload)
    grant["descriptor_ref"] = artifact_ref

    doc = _load_grants_doc(room_id)
    grants = _safe_list(doc.get("grants"))
    grants.append(grant)
    saved_doc = _save_grants_doc(room_id, {"grants": grants})

    evt = _build_issue_event(uid=uid, room_id=room_id, request_id=rid, grant=grant)
    append_room_event(room_id, evt)
    touch_room_updated_at(room_id)

    return _formal_envelope(
        request_id=rid,
        conv_id=room_id,
        response="room mcp share ref issued",
        status="success",
        message="room mcp share ref issued",
        tool_calls=[],
        tool_results=[
            _build_tool_result_item(
                "room_mcp_share_ref",
                room_id=room_id,
                share_ref=artifact_ref,
                legacy_share_ref=legacy_share_ref,
                artifact=artifact_payload,
                grant=grant,
                provider=provider,
                publication=publication,
                provider_id=_safe_str(provider.get("provider_id")),
                provider_type=_safe_str(provider.get("provider_type")),
                provider_origin=_safe_str(provider.get("provider_origin")),
                availability=_safe_dict(provider.get("availability")),
                room_source=_safe_dict(provider.get("room_source")),
                audience=_safe_dict(grant.get("audience")),
                route_identity=_safe_dict(grant.get("route_identity")),
                external_result_view=_safe_str(grant.get("external_result_view"), "final_result_only"),
                grants_count=len(_safe_list(saved_doc.get("grants"))),
            )
        ],
    )


def nisb_room_mcp_grant_list(args: Dict[str, Any]) -> Dict[str, Any]:
    basepath = get_basepath(args)
    uid = uid_from_ctx_or_basepath(basepath, args)
    rid = ensure_request_id(args)

    room_id = require_safe_id("room_id", args.get("room_id"))
    meta = ensure_room_exists(room_id)
    if meta and not can_edit_room_state(uid, meta):
        return _permission_denied(rid, room_id)

    doc = _load_grants_doc(room_id)
    grants = [_normalize_grant_row(item) for item in _safe_list(doc.get("grants"))]

    active = 0
    revoked = 0
    expired = 0
    other = 0
    for row in grants:
        state = _safe_str(row.get("grant_state"))
        if state == "active":
            active += 1
        elif state == "revoked":
            revoked += 1
        elif state == "expired":
            expired += 1
        else:
            other += 1

    return _formal_envelope(
        request_id=rid,
        conv_id=room_id,
        response=f"Loaded {len(grants)} room mcp grants.",
        status="success",
        message="room mcp grants loaded",
        tool_calls=[],
        tool_results=[
            _build_tool_result_item(
                "room_mcp_grants",
                room_id=room_id,
                grants=grants,
                total=len(grants),
                active=active,
                revoked=revoked,
                expired=expired,
                other=other,
                updated_at=_safe_str(doc.get("updated_at")),
            )
        ],
    )


def nisb_room_mcp_grant_revoke(args: Dict[str, Any]) -> Dict[str, Any]:
    basepath = get_basepath(args)
    uid = uid_from_ctx_or_basepath(basepath, args)
    rid = ensure_request_id(args)

    room_id = require_safe_id("room_id", args.get("room_id"))
    meta = ensure_room_exists(room_id)
    if meta and not can_edit_room_state(uid, meta):
        return _permission_denied(rid, room_id)

    grant_id = _safe_str(args.get("grant_id"))
    artifact_id = _safe_str(args.get("artifact_id"))
    if not grant_id and not artifact_id:
        return _formal_envelope(
            request_id=rid,
            conv_id=room_id,
            response="grant_id or artifact_id is required",
            status="error",
            message="room mcp grant revoke missing id",
            tool_calls=[],
            tool_results=[
                _build_tool_result_item(
                    "room_mcp_grant_revoke",
                    room_id=room_id,
                    error="missing_grant_id",
                )
            ],
        )

    from .room_contracts import utc_iso

    doc = _load_grants_doc(room_id)
    grants = _safe_list(doc.get("grants"))
    changed = None
    next_rows = []

    for raw in grants:
        row = _normalize_grant_row(raw)
        hit = False
        if grant_id and _safe_str(row.get("grant_id")) == grant_id:
            hit = True
        if artifact_id and _safe_str(row.get("artifact_id")) == artifact_id:
            hit = True

        if hit:
            changed = dict(row)
            if _safe_str(row.get("grant_state")) != "revoked":
                row["grant_state"] = "revoked"
                row["revoked_at"] = utc_iso()
                row["revoked_by"] = uid
                changed = dict(row)

        next_rows.append(row)

    if not changed:
        return _formal_envelope(
            request_id=rid,
            conv_id=room_id,
            response="room mcp grant not found",
            status="error",
            message="room mcp grant not found",
            tool_calls=[],
            tool_results=[
                _build_tool_result_item(
                    "room_mcp_grant_revoke",
                    room_id=room_id,
                    grant_id=grant_id,
                    artifact_id=artifact_id,
                    error="grant_not_found",
                )
            ],
        )

    _save_grants_doc(room_id, {"grants": next_rows})
    if _safe_str(changed.get("grant_state")) == "revoked" and _safe_str(changed.get("revoked_by")) == uid:
        evt = _build_revoke_event(uid=uid, room_id=room_id, request_id=rid, grant=changed)
        append_room_event(room_id, evt)
        touch_room_updated_at(room_id)

    return _formal_envelope(
        request_id=rid,
        conv_id=room_id,
        response="room mcp grant revoked",
        status="success",
        message="room mcp grant revoked",
        tool_calls=[],
        tool_results=[
            _build_tool_result_item(
                "room_mcp_grant_revoke",
                room_id=room_id,
                grant=changed,
                grant_id=_safe_str(changed.get("grant_id")),
                artifact_id=_safe_str(changed.get("artifact_id")),
                provider_id=_safe_str(changed.get("provider_id")),
                grant_state=_safe_str(changed.get("grant_state")),
            )
        ],
    )


def nisb_room_mcp_provider_share_ref_resolve(args: Dict[str, Any]) -> Dict[str, Any]:
    rid = ensure_request_id(args)

    room_id = _safe_str(args.get("room_id"))
    share_ref = _safe_str(
        args.get("share_ref")
        or args.get("mcp_share_ref")
        or args.get("ref")
    )

    if not share_ref:
        return _formal_envelope(
            request_id=rid,
            conv_id=room_id,
            response="share ref is required",
            status="error",
            message="room mcp provider share ref missing",
            tool_calls=[],
            tool_results=[
                _build_tool_result_item(
                    "room_mcp_provider_share_ref_resolve",
                    room_id=room_id,
                    share_ref="",
                    provider={},
                    provider_snapshot={},
                    error="missing_share_ref",
                )
            ],
        )

    artifact = parse_room_mcp_grant_artifact(share_ref)
    raw_share_ref = _safe_str(artifact.get("share_ref")) if artifact else share_ref

    share_ref_obj = parse_room_shared_mcp_share_ref(raw_share_ref)
    provider = build_imported_room_mcp_provider_contract({"share_ref": raw_share_ref})

    if not share_ref_obj or not provider:
        return _formal_envelope(
            request_id=rid,
            conv_id=room_id,
            response="share ref is invalid",
            status="error",
            message="room mcp provider share ref invalid",
            tool_calls=[],
            tool_results=[
                _build_tool_result_item(
                    "room_mcp_provider_share_ref_resolve",
                    room_id=room_id,
                    share_ref=share_ref,
                    provider={},
                    provider_snapshot={},
                    error="invalid_share_ref",
                )
            ],
        )

    tool_templates = _safe_list(provider.get("tool_templates"))
    tool_template = _safe_dict(tool_templates[0]) if tool_templates else {}
    boundary_hint = _safe_dict(provider.get("boundary_hint"))
    provider_origin = _safe_str(provider.get("provider_origin"), "imported_remote") or "imported_remote"

    artifact_scope = _safe_dict(artifact.get("scope"))
    artifact_audience = _safe_dict(artifact.get("audience"))
    artifact_route = _safe_dict(artifact.get("route_identity"))

    room_source = _safe_dict(provider.get("room_source"))
    if artifact:
        room_source = {
            **room_source,
            "room_id": _safe_str(artifact.get("source_room_id")) or _safe_str(room_source.get("room_id")),
            "visibility_source": "granted_visible",
        }
    if room_id:
        room_source = {
            **room_source,
            "consumer_room_id": room_id,
        }

    resolved_grant = {}
    if artifact:
        resolved_grant = get_room_mcp_grant_by_id(
            source_room_id=artifact.get("source_room_id"),
            grant_id=artifact.get("grant_id"),
            artifact_id=artifact.get("artifact_id"),
        )

    effective_grant = _normalize_grant_row(
        {
            **_safe_dict(artifact),
            **_safe_dict(resolved_grant),
            "grant_id": _safe_str(resolved_grant.get("grant_id") or artifact.get("grant_id")),
            "artifact_id": _safe_str(resolved_grant.get("artifact_id") or artifact.get("artifact_id")),
            "provider_id": _safe_str(resolved_grant.get("provider_id") or artifact.get("provider_id") or provider.get("provider_id")),
            "source_room_id": _safe_str(resolved_grant.get("source_room_id") or artifact.get("source_room_id") or room_source.get("room_id")),
            "grant_mode": _normalize_grant_mode(resolved_grant.get("grant_mode") or artifact.get("grant_mode")),
            "discovery_mode": _safe_str(
                resolved_grant.get("discovery_mode") or artifact.get("discovery_mode"),
                "granted_visible",
            ) or "granted_visible",
            "grant_state": _safe_str(
                resolved_grant.get("grant_state") or artifact.get("grant_state") or "active",
                "active",
            ) or "active",
            "scope": _safe_dict(resolved_grant.get("scope") or artifact_scope),
            "audience": _safe_dict(resolved_grant.get("audience") or artifact_audience),
            "issued_at": _safe_str(resolved_grant.get("issued_at") or artifact.get("issued_at")),
            "expires_at": _safe_str(resolved_grant.get("expires_at") or artifact.get("expires_at")),
            "revocable": bool(_safe_dict(resolved_grant).get("revocable", True)),
            "revoked_at": _safe_str(resolved_grant.get("revoked_at")),
            "revoked_by": _safe_str(resolved_grant.get("revoked_by")),
            "descriptor_ref": _safe_str(resolved_grant.get("descriptor_ref") or share_ref),
            "boundary_hint": _safe_str(resolved_grant.get("boundary_hint") or artifact.get("boundary_hint")),
            "resolution_source": _safe_str(
                resolved_grant.get("resolution_source") or artifact.get("resolution_source"),
                "grant_artifact",
            ) or "grant_artifact",
            "external_result_view": _safe_str(
                resolved_grant.get("external_result_view")
                or artifact.get("external_result_view")
                or _safe_dict(resolved_grant.get("scope") or artifact_scope).get("result_view"),
                "final_result_only",
            ) or "final_result_only",
            "source_observation_allowed": bool(
                _safe_dict(resolved_grant).get(
                    "source_observation_allowed",
                    _safe_dict(resolved_grant.get("scope") or artifact_scope).get("observe_source_room", False),
                )
            ),
            "peer_id": _safe_str(
                _safe_dict(resolved_grant.get("route_identity")).get("peer_id")
                or artifact_route.get("peer_id")
            ),
            "remote_peer_id": _safe_str(
                _safe_dict(resolved_grant.get("route_identity")).get("remote_peer_id")
                or artifact_route.get("remote_peer_id")
            ),
            "target_peer_id": _safe_str(
                _safe_dict(resolved_grant.get("route_identity")).get("target_peer_id")
                or artifact_route.get("target_peer_id")
            ),
            "source_peer_id": _safe_str(
                _safe_dict(resolved_grant.get("route_identity")).get("source_peer_id")
                or artifact_route.get("source_peer_id")
            ),
            "federation_peer_id": _safe_str(
                _safe_dict(resolved_grant.get("route_identity")).get("federation_peer_id")
                or artifact_route.get("federation_peer_id")
            ),
            "remote_user_id": _safe_str(
                _safe_dict(resolved_grant.get("route_identity")).get("remote_user_id")
                or artifact_route.get("remote_user_id")
            ),
            "consumer_room_id": _safe_str(
                _safe_dict(resolved_grant.get("route_identity")).get("consumer_room_id")
                or artifact_route.get("consumer_room_id")
                or room_id
            ),
            "uid": _safe_str(
                _safe_dict(resolved_grant.get("route_identity")).get("uid")
                or artifact_route.get("uid")
            ),
            "remote_label": _safe_str(
                _safe_dict(resolved_grant.get("route_identity")).get("remote_label")
                or artifact_route.get("remote_label")
            ),
        }
    ) if artifact else {}

    resolved_scope = _safe_dict(effective_grant.get("scope"))
    grant_state = _safe_str(effective_grant.get("grant_state"), "active") or "active"
    grant_audience = _safe_dict(effective_grant.get("audience"))
    grant_route = _safe_dict(effective_grant.get("route_identity"))
    resolution_source = _safe_str(effective_grant.get("resolution_source"), "grant_artifact") or "grant_artifact"
    discovery_mode = _safe_str(effective_grant.get("discovery_mode"), "granted_visible") or "granted_visible"
    grant_mode = _normalize_grant_mode(effective_grant.get("grant_mode"))
    external_result_view = _safe_str(
        effective_grant.get("external_result_view") or resolved_scope.get("result_view"),
        "final_result_only",
    ) or "final_result_only"
    source_observation_allowed = bool(
        effective_grant.get("source_observation_allowed", resolved_scope.get("observe_source_room", False))
    )

    federation_meta = {
        "peer_id": _safe_str(grant_route.get("federation_peer_id") or grant_route.get("peer_id")),
        "remote_peer_id": _safe_str(grant_route.get("remote_peer_id") or grant_route.get("peer_id")),
        "target_peer_id": _safe_str(grant_route.get("target_peer_id") or grant_route.get("peer_id")),
        "remote_user_id": _safe_str(grant_route.get("remote_user_id")),
        "remote_label": _safe_str(grant_route.get("remote_label")),
    }
    provider_origin_meta = {
        "peer_id": _safe_str(grant_route.get("peer_id")),
        "remote_peer_id": _safe_str(grant_route.get("remote_peer_id")),
        "target_peer_id": _safe_str(grant_route.get("target_peer_id")),
        "source_peer_id": _safe_str(grant_route.get("source_peer_id")),
        "remote_user_id": _safe_str(grant_route.get("remote_user_id")),
    }

    if artifact:
        boundary_hint = {
            **boundary_hint,
            "result_view": external_result_view,
            "observe_source_room": source_observation_allowed,
            "visibility_source": "granted_visible",
            "grant_state": grant_state,
            "grant_mode": grant_mode,
            "resolution_source": resolution_source,
        }

    room_source = {
        **room_source,
        "share_ref": share_ref,
        "visibility_source": "granted_visible" if artifact else _safe_str(room_source.get("visibility_source")),
    }

    provider = {
        **provider,
        "provider_origin": provider_origin,
        "room_source": room_source,
        "grant_id": _safe_str(effective_grant.get("grant_id")),
        "artifact_id": _safe_str(effective_grant.get("artifact_id")),
        "grant_state": grant_state,
        "grant_mode": grant_mode,
        "discovery_mode": discovery_mode,
        "resolution_source": resolution_source,
        "external_result_view": external_result_view,
        "source_observation_allowed": source_observation_allowed,
        "grant_audience": grant_audience,
        "_grant_meta": effective_grant,
        "grant_meta": effective_grant,
        "grant": effective_grant,
        "share_ref": share_ref,
        "share_ref_payload": _safe_dict(artifact),
        "provider_origin_meta": {
            **_safe_dict(provider.get("provider_origin_meta")),
            **provider_origin_meta,
        },
        "federation": {
            **_safe_dict(provider.get("federation")),
            **federation_meta,
        },
        "peer_id": _safe_str(grant_route.get("peer_id")),
        "remote_peer_id": _safe_str(grant_route.get("remote_peer_id")),
        "target_peer_id": _safe_str(grant_route.get("target_peer_id")),
        "source_peer_id": _safe_str(grant_route.get("source_peer_id")),
        "federation_peer_id": _safe_str(grant_route.get("federation_peer_id")),
        "remote_user_id": _safe_str(grant_route.get("remote_user_id")),
        "consumer_room_id": _safe_str(grant_route.get("consumer_room_id") or room_id),
        "visibility_source": "granted_visible" if artifact else _safe_str(provider.get("visibility_source")),
    }

    provider_snapshot = {
        "provider_id": _safe_str(provider.get("provider_id")).lower(),
        "provider_type": _safe_str(provider.get("provider_type")),
        "provider_origin": provider_origin,
        "provider_label": _safe_str(provider.get("label")),
        "description": _safe_str(provider.get("description")),
        "descriptor_version": _safe_str(provider.get("descriptor_version")),
        "server_tool": "nisb_room_mcp_provider_call",
        "tool_name": _safe_str(tool_template.get("tool_name"), "ask_room_shared_reply"),
        "requested_mode": _safe_str(tool_template.get("requested_mode"), "mcp"),
        "params": {},
        "params_schema": _safe_dict(provider.get("params_schema")),
        "params_defaults": _safe_dict(provider.get("params_defaults")),
        "inherit_workspace_context": False,
        "inherit_focus_root": False,
        "room_source": room_source,
        "boundary_hint": boundary_hint,
        "availability": _safe_dict(provider.get("availability")),
        "auth_state": _safe_dict(provider.get("auth_state")),
        "share_ref": share_ref,
        "legacy_share_ref": raw_share_ref if artifact else "",
        "share_ref_payload": _safe_dict(artifact),
        "grant_id": _safe_str(effective_grant.get("grant_id")),
        "artifact_id": _safe_str(effective_grant.get("artifact_id")),
        "grant_state": grant_state,
        "grant_mode": grant_mode,
        "discovery_mode": discovery_mode,
        "resolution_source": resolution_source,
        "grant_audience": grant_audience,
        "_grant_meta": effective_grant,
        "grant_meta": effective_grant,
        "grant": effective_grant,
        "provider_origin_meta": provider_origin_meta,
        "federation": federation_meta,
        "peer_id": _safe_str(grant_route.get("peer_id")),
        "remote_peer_id": _safe_str(grant_route.get("remote_peer_id")),
        "target_peer_id": _safe_str(grant_route.get("target_peer_id")),
        "source_peer_id": _safe_str(grant_route.get("source_peer_id")),
        "federation_peer_id": _safe_str(grant_route.get("federation_peer_id")),
        "remote_user_id": _safe_str(grant_route.get("remote_user_id")),
        "consumer_room_id": _safe_str(grant_route.get("consumer_room_id") or room_id),
        "visibility_source": "granted_visible" if artifact else "",
        "result_view": external_result_view if artifact else "",
        "external_result_view": external_result_view if artifact else "",
        "source_observation_allowed": source_observation_allowed if artifact else False,
    }

    return _formal_envelope(
        request_id=rid,
        conv_id=room_id,
        response=f"Resolved MCP share ref: {provider.get('label') or provider.get('provider_id') or 'provider'}.",
        status="success",
        message="room mcp provider share ref resolved",
        tool_calls=[],
        tool_results=[
            _build_tool_result_item(
                "room_mcp_provider_share_ref_resolve",
                room_id=room_id,
                share_ref=share_ref,
                share_ref_obj=share_ref_obj,
                artifact=artifact,
                grant=effective_grant,
                provider=provider,
                provider_snapshot=provider_snapshot,
                provider_id=_safe_str(provider.get("provider_id")),
                provider_type=_safe_str(provider.get("provider_type")),
                provider_origin=provider_origin,
                room_source=room_source,
                boundary_hint=boundary_hint,
                availability=_safe_dict(provider.get("availability")),
                auth_state=_safe_dict(provider.get("auth_state")),
                grant_state=grant_state,
                grant_audience=grant_audience,
                grant_mode=grant_mode,
                discovery_mode=discovery_mode,
                resolution_source=resolution_source,
                external_result_view=external_result_view,
                source_observation_allowed=source_observation_allowed,
                federation=_safe_dict(provider_snapshot.get("federation")),
            )
        ],
    )


def nisb_room_mcp_provider_call(args: Dict[str, Any]) -> Dict[str, Any]:
    rid = ensure_request_id(args)
    room_id = require_safe_id("room_id", args.get("room_id"))
    return _formal_envelope(
        request_id=rid,
        conv_id=room_id,
        response="room mcp provider call is an internal adapter entrypoint",
        status="success",
        message="room mcp provider call entrypoint",
        tool_calls=[],
        tool_results=[_build_tool_result_item("room_mcp_provider_call", room_id=room_id)],
    )


__all__ = [
    "ROOM_MCP_GRANT_ARTIFACT_PREFIX",
    "ROOM_MCP_GRANTS_FILENAME",
    "get_room_mcp_grant_by_id",
    "nisb_room_mcp_grant_list",
    "nisb_room_mcp_grant_revoke",
    "nisb_room_mcp_provider_call",
    "nisb_room_mcp_provider_list",
    "nisb_room_mcp_provider_share_ref_resolve",
    "nisb_room_mcp_publication_get",
    "nisb_room_mcp_share_ref_issue",
    "parse_room_mcp_grant_artifact",
]
