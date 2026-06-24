from __future__ import annotations

import base64
import json
from pathlib import Path
from typing import Any, Dict, List

from .room_contracts import new_id, utc_iso
from .room_mcp_provider_contract import build_room_shared_mcp_provider_contract
from .room_store import SHARED_ROOT


ROOM_MCP_GRANT_ARTIFACT_PREFIX = "room-mcp-grant:"
ROOM_MCP_GRANTS_FILENAME = "room_mcp_grants.json"


def _safe_dict(v: Any) -> Dict[str, Any]:
    return v if isinstance(v, dict) else {}


def _safe_list(v: Any) -> List[Any]:
    return list(v) if isinstance(v, list) else []


def _safe_str(v: Any, default: str = "") -> str:
    if v is None:
        return default
    s = str(v).strip()
    return s if s else default


def _pick_first_str(*values: Any) -> str:
    for value in values:
        s = _safe_str(value)
        if s:
            return s
    return ""


def _room_dir(room_id: str) -> Path:
    return Path(SHARED_ROOT) / room_id


def _grants_doc_path(room_id: str) -> Path:
    return _room_dir(room_id) / ROOM_MCP_GRANTS_FILENAME


def _b64encode_json(payload: Dict[str, Any]) -> str:
    raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _b64decode_json(encoded: str) -> Dict[str, Any]:
    text = _safe_str(encoded)
    if not text:
        return {}
    padded = text + ("=" * ((4 - len(text) % 4) % 4))
    try:
        raw = base64.urlsafe_b64decode(padded.encode("ascii")).decode("utf-8")
        obj = json.loads(raw)
        return obj if isinstance(obj, dict) else {}
    except Exception:
        return {}


def _normalize_scope(raw: Any) -> Dict[str, Any]:
    src = raw if isinstance(raw, dict) else {}
    result_view = _safe_str(src.get("result_view"), "final_result_only") or "final_result_only"
    if result_view not in {"final_result_only", "full_result"}:
        result_view = "final_result_only"

    return {
        "result_view": result_view,
        "bind_as_worker": bool(src.get("bind_as_worker", True)),
        "observe_source_room": bool(src.get("observe_source_room", False)),
    }


def _normalize_audience_type(src: Dict[str, Any]) -> str:
    raw_type = _safe_str(src.get("type")).lower()
    if raw_type:
        return raw_type

    if _pick_first_str(src.get("consumer_room_id")):
        return "consumer_room"

    if _pick_first_str(
        src.get("peer_id"),
        src.get("remote_peer_id"),
        src.get("target_peer_id"),
        src.get("federation_peer_id"),
    ):
        return "peer_consumer"

    if _pick_first_str(src.get("remote_user_id")):
        return "remote_user"

    if _pick_first_str(
        src.get("uid"),
        src.get("user_id"),
        src.get("target_user_id"),
    ):
        return "target_user"

    return "share_ref_bearer"


def _normalize_audience(raw: Any) -> Dict[str, Any]:
    src = raw if isinstance(raw, dict) else {}

    peer_id = _safe_str(
        src.get("peer_id")
        or src.get("remote_peer_id")
        or src.get("target_peer_id")
        or src.get("federation_peer_id")
    )
    target_user_id = _pick_first_str(
        src.get("uid"),
        src.get("user_id"),
        src.get("target_user_id"),
    )
    audience_type = _normalize_audience_type(
        {
            **src,
            "peer_id": peer_id,
            "target_user_id": target_user_id,
        }
    )

    return {
        "type": audience_type,
        "peer_id": peer_id,
        "remote_peer_id": _safe_str(src.get("remote_peer_id") or peer_id),
        "target_peer_id": _safe_str(src.get("target_peer_id") or peer_id),
        "source_peer_id": _safe_str(src.get("source_peer_id")),
        "federation_peer_id": _safe_str(src.get("federation_peer_id") or peer_id),
        "remote_user_id": _safe_str(src.get("remote_user_id")),
        "consumer_room_id": _safe_str(src.get("consumer_room_id")),
        "uid": target_user_id,
        "remote_label": _safe_str(src.get("remote_label") or src.get("label")),
        "note": _safe_str(src.get("note")),
    }


def _extract_issue_audience(args: Dict[str, Any]) -> Dict[str, Any]:
    raw = _safe_dict(args.get("audience"))
    if raw:
        return _normalize_audience(raw)

    return _normalize_audience(
        {
            "type": args.get("audience_type"),
            "peer_id": args.get("peer_id"),
            "remote_peer_id": args.get("remote_peer_id"),
            "target_peer_id": args.get("target_peer_id"),
            "source_peer_id": args.get("source_peer_id"),
            "federation_peer_id": args.get("federation_peer_id"),
            "remote_user_id": args.get("remote_user_id"),
            "consumer_room_id": args.get("consumer_room_id"),
            "uid": args.get("uid") or args.get("user_id") or args.get("target_user_id"),
            "remote_label": args.get("remote_label"),
            "note": args.get("note"),
        }
    )


def _build_grant_route_fields(audience: Any) -> Dict[str, Any]:
    aud = _normalize_audience(audience)
    peer_id = _safe_str(
        aud.get("peer_id")
        or aud.get("remote_peer_id")
        or aud.get("target_peer_id")
        or aud.get("federation_peer_id")
    )

    return {
        "peer_id": peer_id,
        "remote_peer_id": _safe_str(aud.get("remote_peer_id") or peer_id),
        "target_peer_id": _safe_str(aud.get("target_peer_id") or peer_id),
        "source_peer_id": _safe_str(aud.get("source_peer_id")),
        "federation_peer_id": _safe_str(aud.get("federation_peer_id") or peer_id),
        "remote_user_id": _safe_str(aud.get("remote_user_id")),
        "consumer_room_id": _safe_str(aud.get("consumer_room_id")),
        "uid": _safe_str(aud.get("uid")),
        "remote_label": _safe_str(aud.get("remote_label")),
    }


def _normalize_grant_mode(value: Any) -> str:
    mode = _safe_str(value, "share_artifact").lower() or "share_artifact"
    if mode in {
        "share_artifact",
        "directed_grant",
        "peer_consumer_grant",
        "consumer_room_grant",
    }:
        return mode
    return "share_artifact"


def _normalize_grant_state(value: Any, expires_at: str = "", revoked_at: str = "") -> str:
    if revoked_at:
        return "revoked"
    if expires_at and expires_at <= utc_iso():
        return "expired"

    s = _safe_str(value, "active").lower() or "active"
    if s in {
        "active",
        "revoked",
        "expired",
        "resolved",
        "consumed",
        "denied",
    }:
        return s
    return "active"


def _normalize_publication_record(meta: Dict[str, Any], state: Dict[str, Any]) -> Dict[str, Any]:
    provider = build_room_shared_mcp_provider_contract(meta, state)
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
        "provider_id": _safe_str(raw.get("provider_id")) or _safe_str(provider.get("provider_id")) or f"room_provider__{room_id}",
        "source_room_id": _safe_str(raw.get("source_room_id")) or room_id,
        "publish_enabled": enabled,
        "publish_label": _safe_str(raw.get("publish_label")) or _safe_str(meta.get("room_mcp_provider_name")) or _safe_str(provider.get("label")),
        "publish_summary": _safe_str(raw.get("publish_summary")) or _safe_str(meta.get("room_mcp_provider_summary")) or _safe_str(provider.get("description")),
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


def _build_publication_record(meta: Dict[str, Any], state: Dict[str, Any]) -> Dict[str, Any]:
    return _normalize_publication_record(meta, state)


def _normalize_grant_row(raw: Any) -> Dict[str, Any]:
    src = raw if isinstance(raw, dict) else {}
    expires_at = _safe_str(src.get("expires_at"))
    revoked_at = _safe_str(src.get("revoked_at"))
    grant_state = _normalize_grant_state(src.get("grant_state"), expires_at=expires_at, revoked_at=revoked_at)
    scope = _normalize_scope(src.get("scope"))
    audience = _normalize_audience(src.get("audience"))
    route = _build_grant_route_fields(audience)

    return {
        "grant_id": _safe_str(src.get("grant_id")),
        "artifact_id": _safe_str(src.get("artifact_id")),
        "provider_id": _safe_str(src.get("provider_id")),
        "source_room_id": _safe_str(src.get("source_room_id")),
        "grant_mode": _normalize_grant_mode(src.get("grant_mode")),
        "discovery_mode": _safe_str(src.get("discovery_mode"), "granted_visible") or "granted_visible",
        "grant_state": grant_state,
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
        "external_result_view": _safe_str(src.get("external_result_view") or scope.get("result_view"), "final_result_only") or "final_result_only",
        "source_observation_allowed": bool(src.get("source_observation_allowed", scope.get("observe_source_room", False))),
        "route_identity": {
            "peer_id": _safe_str(src.get("peer_id") or route.get("peer_id")),
            "remote_peer_id": _safe_str(src.get("remote_peer_id") or route.get("remote_peer_id")),
            "target_peer_id": _safe_str(src.get("target_peer_id") or route.get("target_peer_id")),
            "source_peer_id": _safe_str(src.get("source_peer_id") or route.get("source_peer_id")),
            "federation_peer_id": _safe_str(src.get("federation_peer_id") or route.get("federation_peer_id")),
            "remote_user_id": _safe_str(src.get("remote_user_id") or route.get("remote_user_id")),
            "consumer_room_id": _safe_str(src.get("consumer_room_id") or route.get("consumer_room_id")),
            "uid": _safe_str(src.get("uid") or route.get("uid")),
            "remote_label": _safe_str(src.get("remote_label") or route.get("remote_label")),
        },
    }


def _load_grants_doc(room_id: str) -> Dict[str, Any]:
    path = _grants_doc_path(room_id)
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

    grants = [_normalize_grant_row(item) for item in _safe_list(_safe_dict(obj).get("grants"))]
    return {
        "version": 1,
        "room_id": room_id,
        "grants": grants,
        "updated_at": _safe_str(_safe_dict(obj).get("updated_at")),
    }


def _save_grants_doc(room_id: str, doc: Dict[str, Any]) -> Dict[str, Any]:
    room_dir = _room_dir(room_id)
    room_dir.mkdir(parents=True, exist_ok=True)
    path = _grants_doc_path(room_id)

    payload = {
        "version": 1,
        "room_id": room_id,
        "grants": [_normalize_grant_row(item) for item in _safe_list(_safe_dict(doc).get("grants"))],
        "updated_at": utc_iso(),
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


def _find_grant_row(
    room_id: str,
    *,
    grant_id: str = "",
    artifact_id: str = "",
) -> Dict[str, Any]:
    doc = _load_grants_doc(room_id)
    for row in _safe_list(doc.get("grants")):
        item = _normalize_grant_row(row)
        if grant_id and _safe_str(item.get("grant_id")) == grant_id:
            return item
        if artifact_id and _safe_str(item.get("artifact_id")) == artifact_id:
            return item
    return {}


def get_room_mcp_grant_by_id(
    *,
    source_room_id: Any,
    grant_id: Any = "",
    artifact_id: Any = "",
) -> Dict[str, Any]:
    room_id = _safe_str(source_room_id)
    if not room_id:
        return {}
    return _find_grant_row(
        room_id,
        grant_id=_safe_str(grant_id),
        artifact_id=_safe_str(artifact_id),
    )


def _encode_grant_artifact(payload: Dict[str, Any]) -> str:
    return f"{ROOM_MCP_GRANT_ARTIFACT_PREFIX}{_b64encode_json(payload)}"


def _build_grant_artifact_payload(
    *,
    grant: Dict[str, Any],
    room_id: str,
    legacy_share_ref: str,
) -> Dict[str, Any]:
    return {
        "artifact_kind": "room_mcp_grant",
        "artifact_version": 1,
        "grant_id": _safe_str(grant.get("grant_id")),
        "artifact_id": _safe_str(grant.get("artifact_id")),
        "provider_id": _safe_str(grant.get("provider_id")),
        "source_room_id": room_id,
        "issued_at": _safe_str(grant.get("issued_at")),
        "expires_at": _safe_str(grant.get("expires_at")),
        "grant_mode": _safe_str(grant.get("grant_mode")),
        "grant_state": _safe_str(grant.get("grant_state")),
        "discovery_mode": _safe_str(grant.get("discovery_mode")),
        "scope": _safe_dict(grant.get("scope")),
        "audience": _safe_dict(grant.get("audience")),
        "boundary_hint": _safe_str(grant.get("boundary_hint")),
        "share_ref": legacy_share_ref,
        "resolution_source": _safe_str(grant.get("resolution_source"), "grant_artifact"),
        "external_result_view": _safe_str(grant.get("external_result_view"), "final_result_only"),
        "source_observation_allowed": bool(grant.get("source_observation_allowed")),
    }


def parse_room_mcp_grant_artifact(value: Any) -> Dict[str, Any]:
    text = _safe_str(value)
    if not text.startswith(ROOM_MCP_GRANT_ARTIFACT_PREFIX):
        return {}

    encoded = text[len(ROOM_MCP_GRANT_ARTIFACT_PREFIX):].strip()
    obj = _b64decode_json(encoded)
    if not obj:
        return {}

    scope = _normalize_scope(obj.get("scope"))
    audience = _normalize_audience(obj.get("audience"))
    payload = {
        "artifact_kind": _safe_str(obj.get("artifact_kind"), "room_mcp_grant") or "room_mcp_grant",
        "artifact_version": int(obj.get("artifact_version") or 1),
        "grant_id": _safe_str(obj.get("grant_id")),
        "artifact_id": _safe_str(obj.get("artifact_id")),
        "provider_id": _safe_str(obj.get("provider_id")),
        "source_room_id": _safe_str(obj.get("source_room_id")),
        "issued_at": _safe_str(obj.get("issued_at")),
        "expires_at": _safe_str(obj.get("expires_at")),
        "grant_mode": _normalize_grant_mode(obj.get("grant_mode")),
        "grant_state": _normalize_grant_state(obj.get("grant_state"), _safe_str(obj.get("expires_at")), _safe_str(obj.get("revoked_at"))),
        "discovery_mode": _safe_str(obj.get("discovery_mode"), "granted_visible") or "granted_visible",
        "scope": scope,
        "audience": audience,
        "boundary_hint": _safe_str(obj.get("boundary_hint")),
        "share_ref": _safe_str(obj.get("share_ref")),
        "resolution_source": _safe_str(obj.get("resolution_source"), "grant_artifact") or "grant_artifact",
        "external_result_view": _safe_str(obj.get("external_result_view") or scope.get("result_view"), "final_result_only") or "final_result_only",
        "source_observation_allowed": bool(obj.get("source_observation_allowed", scope.get("observe_source_room", False))),
        "route_identity": _build_grant_route_fields(audience),
    }
    if not payload["grant_id"] or not payload["artifact_id"] or not payload["provider_id"] or not payload["source_room_id"]:
        return {}
    return payload


def _build_issue_event(
    *,
    uid: str,
    room_id: str,
    request_id: str,
    grant: Dict[str, Any],
) -> Dict[str, Any]:
    scope = _safe_dict(grant.get("scope"))
    audience = _safe_dict(grant.get("audience"))
    route_identity = _safe_dict(grant.get("route_identity"))

    return {
        "id": new_id("evt"),
        "ts": utc_iso(),
        "type": "room.mcp_grant_issued",
        "room_id": room_id,
        "request_id": request_id,
        "payload": {
            "sender": uid,
            "grant_id": _safe_str(grant.get("grant_id")),
            "artifact_id": _safe_str(grant.get("artifact_id")),
            "provider_id": _safe_str(grant.get("provider_id")),
            "grant_mode": _safe_str(grant.get("grant_mode")),
            "grant_state": _safe_str(grant.get("grant_state")),
            "scope": scope,
            "result_view": _safe_str(scope.get("result_view"), "final_result_only"),
            "observe_source_room": bool(scope.get("observe_source_room", False)),
            "discovery_mode": _safe_str(grant.get("discovery_mode")),
            "audience": audience,
            "route_identity": route_identity,
        },
    }


def _build_revoke_event(
    *,
    uid: str,
    room_id: str,
    request_id: str,
    grant: Dict[str, Any],
) -> Dict[str, Any]:
    return {
        "id": new_id("evt"),
        "ts": utc_iso(),
        "type": "room.mcp_grant_revoked",
        "room_id": room_id,
        "request_id": request_id,
        "payload": {
            "sender": uid,
            "grant_id": _safe_str(grant.get("grant_id")),
            "artifact_id": _safe_str(grant.get("artifact_id")),
            "provider_id": _safe_str(grant.get("provider_id")),
            "grant_state": _safe_str(grant.get("grant_state")),
            "grant_mode": _safe_str(grant.get("grant_mode")),
            "revoked_at": _safe_str(grant.get("revoked_at")),
            "audience": _safe_dict(grant.get("audience")),
            "route_identity": _safe_dict(grant.get("route_identity")),
        },
    }


__all__ = [
    "ROOM_MCP_GRANT_ARTIFACT_PREFIX",
    "ROOM_MCP_GRANTS_FILENAME",
    "_build_grant_artifact_payload",
    "_build_grant_route_fields",
    "_build_issue_event",
    "_build_publication_record",
    "_build_revoke_event",
    "_encode_grant_artifact",
    "_extract_issue_audience",
    "_find_grant_row",
    "_load_grants_doc",
    "_normalize_audience",
    "_normalize_grant_mode",
    "_normalize_grant_row",
    "_normalize_grant_state",
    "_normalize_publication_record",
    "_normalize_scope",
    "_save_grants_doc",
    "get_room_mcp_grant_by_id",
    "parse_room_mcp_grant_artifact",
]
