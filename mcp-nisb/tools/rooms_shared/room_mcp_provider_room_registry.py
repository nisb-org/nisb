from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from .room_contracts import utc_iso
from .room_mcp_provider_contract import (
    ROOM_SHARED_PROVIDER_TYPE,
    build_room_shared_mcp_provider_contract,
)
from .room_state_normalizer import _normalize_room_state_for_output
from .room_store import (
    SHARED_ROOT,
    ensure_room_exists,
    get_basepath,
    list_room_metas_for_uid,
    load_state_doc,
    uid_from_ctx_or_basepath,
)
from .room_tools_meta import _normalize_room_meta_for_output


ROOM_PROVIDER_PREFIX = "room_provider__"
ROOM_MCP_GRANTS_FILENAME = "room_mcp_grants.json"


def _safe_str(v: Any, default: str = "") -> str:
    if v is None:
        return default
    s = str(v).strip()
    return s if s else default


def _safe_dict(v: Any) -> Dict[str, Any]:
    return dict(v) if isinstance(v, dict) else {}


def _safe_list(v: Any) -> List[Any]:
    return list(v) if isinstance(v, list) else []


def _pick_first_str(*values: Any) -> str:
    for value in values:
        s = _safe_str(value)
        if s:
            return s
    return ""


def is_room_provider_id(provider_id: Any) -> bool:
    return _safe_str(provider_id).lower().startswith(ROOM_PROVIDER_PREFIX)


def parse_room_provider_id(provider_id: Any) -> str:
    key = _safe_str(provider_id).lower()
    if not key.startswith(ROOM_PROVIDER_PREFIX):
        return ""
    return key[len(ROOM_PROVIDER_PREFIX):].strip()


def _room_dir(room_id: str) -> Path:
    return Path(SHARED_ROOT) / room_id


def _grant_doc_path(room_id: str) -> Path:
    return _room_dir(room_id) / ROOM_MCP_GRANTS_FILENAME


def _all_room_ids() -> List[str]:
    root = Path(SHARED_ROOT)
    if not root.exists():
        return []

    out: List[str] = []
    for child in root.iterdir():
        if not child.is_dir():
            continue
        room_id = _safe_str(child.name)
        if not room_id:
            continue
        out.append(room_id)
    out.sort()
    return out


def _load_grants_doc(room_id: str) -> Dict[str, Any]:
    path = _grant_doc_path(room_id)
    if not path.exists():
        return {
            "version": 1,
            "room_id": room_id,
            "grants": [],
            "updated_at": "",
        }

    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        obj = {}

    return {
        "version": 1,
        "room_id": room_id,
        "grants": _safe_list(_safe_dict(obj).get("grants")),
        "updated_at": _safe_str(_safe_dict(obj).get("updated_at")),
    }


def _normalize_publication(meta: Dict[str, Any], state: Dict[str, Any]) -> Dict[str, Any]:
    raw = _safe_dict(meta.get("room_mcp_publication"))
    room_id = _safe_str(meta.get("room_id"))
    enabled = bool(
        raw.get("publish_enabled")
        if "publish_enabled" in raw
        else meta.get("room_mcp_provider_enabled") or state.get("room_mcp_provider_enabled")
    )

    publication_state = _safe_str(
        raw.get("publication_state"),
        "active" if enabled else "disabled",
    ).lower() or ("active" if enabled else "disabled")
    if publication_state not in {"active", "disabled"}:
        publication_state = "active" if enabled else "disabled"

    return {
        "provider_id": _safe_str(raw.get("provider_id")) or f"{ROOM_PROVIDER_PREFIX}{room_id}",
        "source_room_id": _safe_str(raw.get("source_room_id")) or room_id,
        "publish_enabled": enabled,
        "publish_label": _safe_str(raw.get("publish_label")) or _safe_str(meta.get("room_mcp_provider_name")),
        "publish_summary": _safe_str(raw.get("publish_summary")) or _safe_str(meta.get("room_mcp_provider_summary")),
        "boundary_hint": _safe_str(
            raw.get("boundary_hint"),
            "room-configured shared capability only; owner private scope exposed=false",
        ) or "room-configured shared capability only; owner private scope exposed=false",
        "visibility_mode": _safe_str(
            raw.get("visibility_mode"),
            "room_visible_and_grant_capable",
        ) or "room_visible_and_grant_capable",
        "publication_state": publication_state,
        "published_at": _safe_str(raw.get("published_at")) or _safe_str(meta.get("created_at")),
        "updated_at": _safe_str(raw.get("updated_at")) or _safe_str(meta.get("updated_at")),
    }


def _is_publication_enabled(meta: Dict[str, Any], state: Dict[str, Any]) -> bool:
    publication = _normalize_publication(meta, state)
    return bool(publication.get("publish_enabled")) and _safe_str(publication.get("publication_state")) == "active"


def _normalize_grant_scope(raw: Any) -> Dict[str, Any]:
    src = _safe_dict(raw)
    result_view = _safe_str(src.get("result_view"), "final_result_only") or "final_result_only"
    if result_view not in {"final_result_only", "full_result"}:
        result_view = "final_result_only"

    return {
        "result_view": result_view,
        "bind_as_worker": bool(src.get("bind_as_worker", True)),
        "observe_source_room": bool(src.get("observe_source_room", False)),
    }


def _normalize_grant_audience(raw: Any) -> Dict[str, Any]:
    src = _safe_dict(raw)

    peer_id = _pick_first_str(
        src.get("peer_id"),
        src.get("remote_peer_id"),
        src.get("target_peer_id"),
        src.get("federation_peer_id"),
    )
    uid = _pick_first_str(
        src.get("uid"),
        src.get("user_id"),
        src.get("target_user_id"),
    )

    audience_type = _safe_str(src.get("type")).lower()
    if not audience_type:
        if _safe_str(src.get("consumer_room_id")):
            audience_type = "consumer_room"
        elif peer_id:
            audience_type = "peer_consumer"
        elif _safe_str(src.get("remote_user_id")):
            audience_type = "remote_user"
        elif uid:
            audience_type = "target_user"
        else:
            audience_type = "share_ref_bearer"

    return {
        "type": audience_type,
        "peer_id": peer_id,
        "remote_peer_id": _safe_str(src.get("remote_peer_id") or peer_id),
        "target_peer_id": _safe_str(src.get("target_peer_id") or peer_id),
        "source_peer_id": _safe_str(src.get("source_peer_id")),
        "federation_peer_id": _safe_str(src.get("federation_peer_id") or peer_id),
        "remote_user_id": _safe_str(src.get("remote_user_id")),
        "consumer_room_id": _safe_str(src.get("consumer_room_id")),
        "uid": uid,
        "remote_label": _safe_str(src.get("remote_label") or src.get("label")),
        "note": _safe_str(src.get("note")),
    }


def _normalize_grant_state(value: Any, *, expires_at: str = "", revoked_at: str = "") -> str:
    if revoked_at:
        return "revoked"
    if expires_at and expires_at <= utc_iso():
        return "expired"

    state = _safe_str(value, "active").lower() or "active"
    if state in {"active", "revoked", "expired", "resolved", "consumed", "denied"}:
        return state
    return "active"


def _build_grant_route_identity(audience: Dict[str, Any], raw: Dict[str, Any] | None = None) -> Dict[str, Any]:
    src = _safe_dict(raw)
    aud = _normalize_grant_audience(audience)
    peer_id = _pick_first_str(
        src.get("peer_id"),
        src.get("remote_peer_id"),
        src.get("target_peer_id"),
        src.get("federation_peer_id"),
        aud.get("peer_id"),
    )

    return {
        "peer_id": peer_id,
        "remote_peer_id": _safe_str(src.get("remote_peer_id") or aud.get("remote_peer_id") or peer_id),
        "target_peer_id": _safe_str(src.get("target_peer_id") or aud.get("target_peer_id") or peer_id),
        "source_peer_id": _safe_str(src.get("source_peer_id") or aud.get("source_peer_id")),
        "federation_peer_id": _safe_str(src.get("federation_peer_id") or aud.get("federation_peer_id") or peer_id),
        "remote_user_id": _safe_str(src.get("remote_user_id") or aud.get("remote_user_id")),
        "consumer_room_id": _safe_str(src.get("consumer_room_id") or aud.get("consumer_room_id")),
        "uid": _safe_str(src.get("uid") or aud.get("uid")),
        "remote_label": _safe_str(src.get("remote_label") or aud.get("remote_label")),
    }


def _normalize_grant_row(raw: Any) -> Dict[str, Any]:
    src = _safe_dict(raw)
    audience = _normalize_grant_audience(src.get("audience"))
    scope = _normalize_grant_scope(src.get("scope"))
    expires_at = _safe_str(src.get("expires_at"))
    revoked_at = _safe_str(src.get("revoked_at"))
    route_identity = _build_grant_route_identity(audience, src)

    return {
        "grant_id": _safe_str(src.get("grant_id")),
        "artifact_id": _safe_str(src.get("artifact_id")),
        "provider_id": _safe_str(src.get("provider_id")),
        "source_room_id": _safe_str(src.get("source_room_id")),
        "grant_mode": _safe_str(src.get("grant_mode"), "share_artifact") or "share_artifact",
        "discovery_mode": _safe_str(src.get("discovery_mode"), "granted_visible") or "granted_visible",
        "grant_state": _normalize_grant_state(src.get("grant_state"), expires_at=expires_at, revoked_at=revoked_at),
        "audience": audience,
        "scope": scope,
        "issued_at": _safe_str(src.get("issued_at")),
        "expires_at": expires_at,
        "revocable": bool(src.get("revocable", True)),
        "revoked_at": revoked_at,
        "revoked_by": _safe_str(src.get("revoked_by")),
        "descriptor_ref": _safe_str(src.get("descriptor_ref")),
        "boundary_hint": _safe_str(src.get("boundary_hint")),
        "resolution_source": _safe_str(src.get("resolution_source"), "grant_artifact") or "grant_artifact",
        "last_resolved_at": _safe_str(src.get("last_resolved_at")),
        "last_consumed_at": _safe_str(src.get("last_consumed_at")),
        "external_result_view": _safe_str(
            src.get("external_result_view") or scope.get("result_view"),
            "final_result_only",
        ) or "final_result_only",
        "source_observation_allowed": bool(
            src.get("source_observation_allowed", scope.get("observe_source_room", False))
        ),
        "route_identity": route_identity,
    }


def _is_active_grant(grant: Dict[str, Any]) -> bool:
    row = _normalize_grant_row(grant)
    return _safe_str(row.get("grant_state"), "active") == "active"

def _with_local_room_shared_origin(schema: Dict[str, Any], room_id: str) -> Dict[str, Any]:
    src = _safe_dict(schema)
    if not src:
        return {}

    provider_id = _safe_str(src.get("provider_id")) or f"{ROOM_PROVIDER_PREFIX}{room_id}"
    room_source = _safe_dict(src.get("room_source"))
    source_room_id = _safe_str(room_source.get("room_id") or src.get("source_room_id") or room_id)

    out = dict(src)
    out["provider_id"] = provider_id
    out["provider_kind"] = _safe_str(out.get("provider_kind"), ROOM_SHARED_PROVIDER_TYPE) or ROOM_SHARED_PROVIDER_TYPE
    out["provider_type"] = _safe_str(out.get("provider_type"), ROOM_SHARED_PROVIDER_TYPE) or ROOM_SHARED_PROVIDER_TYPE
    out["provider_origin"] = "local_room_shared"
    out["source_room_id"] = source_room_id

    out["room_source"] = {
        **room_source,
        "room_id": source_room_id,
    }

    out["source_ref"] = {
        **_safe_dict(out.get("source_ref")),
        "kind": ROOM_SHARED_PROVIDER_TYPE,
        "origin": "local_room_shared",
        "provider_id": provider_id,
        "room_id": source_room_id,
    }

    return out

def build_room_provider_schema(room_id: str) -> Dict[str, Any]:
    if not room_id:
        return {}

    meta = _normalize_room_meta_for_output(ensure_room_exists(room_id))
    state = _normalize_room_state_for_output(load_state_doc(room_id))
    schema = build_room_shared_mcp_provider_contract(meta, state)
    if not isinstance(schema, dict):
        return {}

    schema = _with_local_room_shared_origin(schema, room_id)
    publication = _normalize_publication(meta, state)
    room_source = {
        **_safe_dict(schema.get("room_source")),
        "room_id": _safe_str(_safe_dict(schema.get("room_source")).get("room_id")) or room_id,
        "visibility_source": "room_visible",
    }

    return {
        **schema,
        "room_source": room_source,
        "publication": publication,
        "visibility_source": "room_visible",
    }


def get_dynamic_room_mcp_provider(provider_id: Any) -> Dict[str, Any]:
    room_id = parse_room_provider_id(provider_id)
    if not room_id:
        return {}
    try:
        return dict(build_room_provider_schema(room_id) or {})
    except Exception:
        return {}


def _resolve_uid_from_args(args: Dict[str, Any] | None = None) -> str:
    safe_args = _safe_dict(args)
    try:
        basepath = get_basepath(safe_args)
    except Exception:
        basepath = _safe_str(
            safe_args.get("base_path")
            or safe_args.get("basepath")
            or safe_args.get("basePath")
        )
    return _safe_str(uid_from_ctx_or_basepath(basepath, safe_args))


def _resolve_actor_context(args: Dict[str, Any] | None = None) -> Dict[str, str]:
    safe_args = _safe_dict(args)
    return {
        "uid": _resolve_uid_from_args(safe_args),
        "consumer_room_id": _safe_str(safe_args.get("room_id")),
        "peer_id": _pick_first_str(
            safe_args.get("peer_id"),
            safe_args.get("_federation_peer_id"),
            safe_args.get("federation_peer_id"),
            safe_args.get("remote_peer_id"),
            safe_args.get("target_peer_id"),
        ),
        "remote_peer_id": _pick_first_str(
            safe_args.get("remote_peer_id"),
            safe_args.get("_federation_peer_id"),
            safe_args.get("federation_peer_id"),
            safe_args.get("peer_id"),
        ),
        "target_peer_id": _pick_first_str(
            safe_args.get("target_peer_id"),
            safe_args.get("remote_peer_id"),
            safe_args.get("_federation_peer_id"),
            safe_args.get("federation_peer_id"),
            safe_args.get("peer_id"),
        ),
        "remote_user_id": _pick_first_str(
            safe_args.get("_federation_remote_user_id"),
            safe_args.get("federation_remote_user_id"),
            safe_args.get("remote_user_id"),
        ),
    }


def _matches_grant_audience(grant: Dict[str, Any], actor: Dict[str, str]) -> bool:
    row = _normalize_grant_row(grant)
    if not _is_active_grant(row):
        return False

    audience = _safe_dict(row.get("audience"))
    audience_type = _safe_str(audience.get("type"), "share_ref_bearer") or "share_ref_bearer"

    actor_uid = _safe_str(actor.get("uid"))
    actor_consumer_room_id = _safe_str(actor.get("consumer_room_id"))
    actor_peer_id = _pick_first_str(actor.get("peer_id"), actor.get("remote_peer_id"), actor.get("target_peer_id"))
    actor_remote_user_id = _safe_str(actor.get("remote_user_id"))

    target_consumer_room_id = _safe_str(audience.get("consumer_room_id"))
    target_peer_id = _pick_first_str(
        audience.get("peer_id"),
        audience.get("remote_peer_id"),
        audience.get("target_peer_id"),
        audience.get("federation_peer_id"),
    )
    target_remote_user_id = _safe_str(audience.get("remote_user_id"))
    target_uid = _safe_str(audience.get("uid"))

    if target_consumer_room_id and actor_consumer_room_id == target_consumer_room_id:
        return True

    if audience_type in {"consumer_room", "consumer_room_id"}:
        return bool(target_consumer_room_id and actor_consumer_room_id == target_consumer_room_id)

    if audience_type in {"peer_consumer", "peer"}:
        return bool(target_peer_id and actor_peer_id == target_peer_id)

    if audience_type in {"remote_user", "federated_remote_user"}:
        if target_peer_id and target_remote_user_id:
            return actor_peer_id == target_peer_id and actor_remote_user_id == target_remote_user_id
        if target_remote_user_id:
            return actor_remote_user_id == target_remote_user_id
        return False

    if audience_type in {"local_user", "user", "target_user"}:
        if target_uid:
            return actor_uid == target_uid
        if target_remote_user_id:
            return actor_uid == target_remote_user_id
        return False

    # 当前默认不把 anonymous bearer grant 作为 granted-visible 的成立条件。
    # 只有在带显式 target 信息时，share_ref_bearer 才可能退化匹配到上面的提前返回。
    return False


def _build_published_schema(
    *,
    meta: Dict[str, Any],
    state: Dict[str, Any],
    room_id: str,
    visibility_source: str,
    grant: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    if not _is_publication_enabled(meta, state):
        return {}

    publication = _normalize_publication(meta, state)

    try:
        schema = build_room_shared_mcp_provider_contract(meta, state)
    except Exception:
        return {}

    if not isinstance(schema, dict):
        return {}

    provider_id = _safe_str(
        schema.get("provider_id")
        or publication.get("provider_id")
        or f"{ROOM_PROVIDER_PREFIX}{room_id}"
    )
    if not provider_id:
        return {}

    provider_type = _safe_str(
        schema.get("provider_type")
        or schema.get("provider_kind")
        or ROOM_SHARED_PROVIDER_TYPE
    )

    room_source = _safe_dict(schema.get("room_source"))
    source_room_id = _safe_str(
        room_source.get("room_id")
        or schema.get("source_room_id")
        or publication.get("source_room_id")
        or room_id
    )

    if provider_type != ROOM_SHARED_PROVIDER_TYPE:
        return {}
    if source_room_id != room_id:
        return {}

    schema = {
        **schema,
        "provider_id": provider_id,
        "provider_type": ROOM_SHARED_PROVIDER_TYPE,
        "provider_kind": ROOM_SHARED_PROVIDER_TYPE,
        "source_room_id": source_room_id,
        "room_source": {
            **room_source,
            "room_id": source_room_id,
        },
    }

    out = _with_local_room_shared_origin(schema, room_id)
    if not out:
        return {}

    out["publication"] = publication
    out["visibility_source"] = visibility_source
    out["room_source"] = {
        **_safe_dict(out.get("room_source")),
        "room_id": source_room_id,
        "visibility_source": visibility_source,
    }
    out["source_ref"] = {
        **_safe_dict(out.get("source_ref")),
        "kind": ROOM_SHARED_PROVIDER_TYPE,
        "origin": "local_room_shared",
        "provider_id": provider_id,
        "room_id": source_room_id,
    }

    if visibility_source == "room_visible":
        return out

    grant_obj = _normalize_grant_row(grant)
    grant_scope = _safe_dict(grant_obj.get("scope"))
    grant_audience = _safe_dict(grant_obj.get("audience"))
    route_identity = _safe_dict(grant_obj.get("route_identity"))
    boundary_hint = {
        **_safe_dict(out.get("boundary_hint")),
        "result_view": _safe_str(grant_obj.get("external_result_view"), "final_result_only"),
        "observe_source_room": bool(grant_obj.get("source_observation_allowed")),
        "visibility_source": "granted_visible",
        "grant_state": _safe_str(grant_obj.get("grant_state"), "active"),
        "grant_mode": _safe_str(grant_obj.get("grant_mode"), "share_artifact"),
        "resolution_source": _safe_str(grant_obj.get("resolution_source"), "grant_artifact"),
    }

    out["grant_id"] = _safe_str(grant_obj.get("grant_id"))
    out["artifact_id"] = _safe_str(grant_obj.get("artifact_id"))
    out["grant_state"] = _safe_str(grant_obj.get("grant_state"), "active") or "active"
    out["grant_mode"] = _safe_str(grant_obj.get("grant_mode"), "share_artifact") or "share_artifact"
    out["discovery_mode"] = _safe_str(grant_obj.get("discovery_mode"), "granted_visible") or "granted_visible"
    out["grant_scope"] = grant_scope
    out["grant_audience"] = grant_audience
    out["resolution_source"] = _safe_str(grant_obj.get("resolution_source"), "grant_artifact") or "grant_artifact"
    out["external_result_view"] = _safe_str(grant_obj.get("external_result_view"), "final_result_only") or "final_result_only"
    out["result_view"] = _safe_str(grant_obj.get("external_result_view"), "final_result_only") or "final_result_only"
    out["source_observation_allowed"] = bool(grant_obj.get("source_observation_allowed"))
    out["boundary_hint"] = boundary_hint
    out["peer_id"] = _safe_str(route_identity.get("peer_id"))
    out["remote_peer_id"] = _safe_str(route_identity.get("remote_peer_id"))
    out["target_peer_id"] = _safe_str(route_identity.get("target_peer_id"))
    out["source_peer_id"] = _safe_str(route_identity.get("source_peer_id"))
    out["federation_peer_id"] = _safe_str(route_identity.get("federation_peer_id"))
    out["remote_user_id"] = _safe_str(route_identity.get("remote_user_id"))
    out["consumer_room_id"] = _safe_str(route_identity.get("consumer_room_id"))
    out["route_identity"] = route_identity
    out["provider_origin_meta"] = {
        **_safe_dict(out.get("provider_origin_meta")),
        "peer_id": _safe_str(route_identity.get("peer_id")),
        "remote_peer_id": _safe_str(route_identity.get("remote_peer_id")),
        "target_peer_id": _safe_str(route_identity.get("target_peer_id")),
        "source_peer_id": _safe_str(route_identity.get("source_peer_id")),
        "remote_user_id": _safe_str(route_identity.get("remote_user_id")),
    }
    out["federation"] = {
        **_safe_dict(out.get("federation")),
        "peer_id": _safe_str(route_identity.get("federation_peer_id") or route_identity.get("peer_id")),
        "remote_peer_id": _safe_str(route_identity.get("remote_peer_id") or route_identity.get("peer_id")),
        "target_peer_id": _safe_str(route_identity.get("target_peer_id") or route_identity.get("peer_id")),
        "remote_user_id": _safe_str(route_identity.get("remote_user_id")),
        "remote_label": _safe_str(route_identity.get("remote_label")),
    }

    return out


def list_room_visible_published_room_provider_schemas(args: Dict[str, Any] | None = None) -> List[Dict[str, Any]]:
    uid = _resolve_uid_from_args(args)
    if not uid:
        return []

    out: List[Dict[str, Any]] = []

    try:
        visible_rooms = list_room_metas_for_uid(uid)
    except Exception:
        return []

    for raw_meta in visible_rooms:
        meta = _normalize_room_meta_for_output(raw_meta)
        room_id = _safe_str(meta.get("room_id"))
        if not room_id:
            continue

        try:
            state = _normalize_room_state_for_output(load_state_doc(room_id))
        except Exception:
            continue

        schema = _build_published_schema(
            meta=meta,
            state=state,
            room_id=room_id,
            visibility_source="room_visible",
        )
        if not schema:
            continue

        out.append(schema)

    out.sort(
        key=lambda item: (
            _safe_str(item.get("label")).lower(),
            _safe_str(item.get("provider_id")).lower(),
        )
    )
    return out


def list_granted_room_provider_schemas(args: Dict[str, Any] | None = None) -> List[Dict[str, Any]]:
    actor = _resolve_actor_context(args)
    if not any(
        (
            _safe_str(actor.get("uid")),
            _safe_str(actor.get("consumer_room_id")),
            _safe_str(actor.get("peer_id")),
            _safe_str(actor.get("remote_user_id")),
        )
    ):
        return []

    out: List[Dict[str, Any]] = []

    for room_id in _all_room_ids():
        try:
            meta = _normalize_room_meta_for_output(ensure_room_exists(room_id))
            state = _normalize_room_state_for_output(load_state_doc(room_id))
        except Exception:
            continue

        if not _is_publication_enabled(meta, state):
            continue

        grants_doc = _load_grants_doc(room_id)
        grants = _safe_list(grants_doc.get("grants"))
        if not grants:
            continue

        try:
            base_schema = build_room_shared_mcp_provider_contract(meta, state)
        except Exception:
            continue

        if not isinstance(base_schema, dict):
            continue

        provider_id = _safe_str(base_schema.get("provider_id"))
        if not provider_id:
            continue

        matched_grant: Dict[str, Any] = {}
        for raw_grant in grants:
            grant = _normalize_grant_row(raw_grant)
            if _safe_str(grant.get("provider_id")) != provider_id:
                continue
            if not _matches_grant_audience(grant, actor):
                continue

            current_issued_at = _safe_str(matched_grant.get("issued_at"))
            next_issued_at = _safe_str(grant.get("issued_at"))
            if not matched_grant or next_issued_at >= current_issued_at:
                matched_grant = grant

        if not matched_grant:
            continue

        schema = _build_published_schema(
            meta=meta,
            state=state,
            room_id=room_id,
            visibility_source="granted_visible",
            grant=matched_grant,
        )
        if not schema:
            continue

        out.append(schema)

    out.sort(
        key=lambda item: (
            _safe_str(item.get("label")).lower(),
            _safe_str(item.get("provider_id")).lower(),
        )
    )
    return out


def list_all_visible_room_provider_schemas(args: Dict[str, Any] | None = None) -> List[Dict[str, Any]]:
    room_visible = list_room_visible_published_room_provider_schemas(args)
    granted_visible = list_granted_room_provider_schemas(args)

    merged: Dict[str, Dict[str, Any]] = {}

    for item in room_visible:
        provider_id = _safe_str(item.get("provider_id"))
        if not provider_id:
            continue
        merged[provider_id] = dict(item)

    for item in granted_visible:
        provider_id = _safe_str(item.get("provider_id"))
        if not provider_id:
            continue

        if provider_id in merged:
            existing = merged[provider_id]
            existing["granted_visible"] = True

            for key in (
                "grant_id",
                "artifact_id",
                "grant_state",
                "grant_mode",
                "discovery_mode",
                "resolution_source",
                "grant_scope",
                "grant_audience",
                "external_result_view",
                "result_view",
                "peer_id",
                "remote_peer_id",
                "target_peer_id",
                "source_peer_id",
                "federation_peer_id",
                "remote_user_id",
                "consumer_room_id",
                "route_identity",
            ):
                if item.get(key) and not existing.get(key):
                    existing[key] = item.get(key)

            if "source_observation_allowed" not in existing:
                existing["source_observation_allowed"] = item.get("source_observation_allowed")

            existing["boundary_hint"] = {
                **_safe_dict(existing.get("boundary_hint")),
                **_safe_dict(item.get("boundary_hint")),
            }
            existing["provider_origin_meta"] = {
                **_safe_dict(existing.get("provider_origin_meta")),
                **_safe_dict(item.get("provider_origin_meta")),
            }
            existing["federation"] = {
                **_safe_dict(existing.get("federation")),
                **_safe_dict(item.get("federation")),
            }
            continue

        merged[provider_id] = dict(item)

    out = list(merged.values())
    out.sort(
        key=lambda item: (
            _safe_str(item.get("label")).lower(),
            _safe_str(item.get("provider_id")).lower(),
        )
    )
    return out


def list_published_room_provider_schemas(args: Dict[str, Any] | None = None) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []

    for room_id in _all_room_ids():
        try:
            meta = _normalize_room_meta_for_output(ensure_room_exists(room_id))
            state = _normalize_room_state_for_output(load_state_doc(room_id))
        except Exception:
            continue

        schema = _build_published_schema(
            meta=meta,
            state=state,
            room_id=room_id,
            visibility_source="room_visible",
        )
        if not schema:
            continue

        out.append(schema)

    out.sort(
        key=lambda item: (
            _safe_str(item.get("label")).lower(),
            _safe_str(item.get("provider_id")).lower(),
        )
    )
    return out


__all__ = [
    "ROOM_PROVIDER_PREFIX",
    "build_room_provider_schema",
    "get_dynamic_room_mcp_provider",
    "is_room_provider_id",
    "list_all_visible_room_provider_schemas",
    "list_granted_room_provider_schemas",
    "list_published_room_provider_schemas",
    "list_room_visible_published_room_provider_schemas",
    "parse_room_provider_id",
]

