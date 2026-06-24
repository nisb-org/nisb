from __future__ import annotations

import secrets
from typing import Any, Dict, List

from .room_contracts import (
    as_bool,
    default_room_state,
    ensure_request_id,
    new_id,
    require_safe_id,
    utc_iso,
)
from .room_state_normalizer import (
    _derive_reply_mode_from_state,
    _normalize_enabled_supervisor_skill_ids,
    _normalize_room_float,
    _normalize_room_int,
    _normalize_room_mcp_overrides,
    _normalize_room_state_for_output,
    _normalize_reply_mode,
    _normalize_supervisor_provider,
    _normalize_supervisor_skill_strategy,
    _safe_dict,
    _safe_str,
)
from .room_store import (
    SHARED_ROOT,
    append_room_event,
    can_edit_room_info,
    can_edit_room_state,
    ensure_dir,
    ensure_room_exists,
    ensure_room_paths,
    get_basepath,
    get_room_owner_user_id,
    is_participant,
    list_room_metas_for_uid,
    load_room_events,
    load_state_doc,
    save_meta,
    save_state_doc,
    touch_room_updated_at,
    uid_from_ctx_or_basepath,
)
from .room_tool_common import (
    _build_tool_result_item,
    _formal_envelope,
    _missing_args,
    _permission_denied,
)


def _federated_participant_uid(peer_id: Any, remote_user_id: Any) -> str:
    p = _safe_str(peer_id)
    u = _safe_str(remote_user_id)
    if not p or not u:
        return ""
    return f"fed__{p}__{u}"


def _parse_federated_participant_uid(uid: Any) -> Dict[str, str]:
    s = _safe_str(uid)
    if not s.startswith("fed__"):
        return {
            "participant_uid": s,
            "type": "local",
            "peer_id": "",
            "remote_user_id": "",
        }

    parts = s.split("__", 2)
    if len(parts) != 3:
        return {
            "participant_uid": s,
            "type": "federated",
            "peer_id": "",
            "remote_user_id": "",
        }

    return {
        "participant_uid": s,
        "type": "federated",
        "peer_id": _safe_str(parts[1]),
        "remote_user_id": _safe_str(parts[2]),
    }


def _is_federated_participant_uid(uid: Any) -> bool:
    return _safe_str(uid).startswith("fed__")


def _resolve_room_actor_uid(
    basepath: str,
    args: Dict[str, Any],
    *,
    allow_federation: bool = True,
) -> str:
    local_uid = uid_from_ctx_or_basepath(basepath, args)
    if not allow_federation:
        return local_uid

    peer_id = _safe_str(
        args.get("_federation_peer_id")
        or args.get("federation_peer_id")
        or args.get("remote_peer_id")
    )
    remote_user_id = _safe_str(
        args.get("_federation_remote_user_id")
        or args.get("federation_remote_user_id")
        or args.get("remote_user_id")
    )

    fed_uid = _federated_participant_uid(peer_id, remote_user_id)
    return fed_uid or local_uid


def _normalize_federated_member_access(raw: Any) -> Dict[str, Dict[str, str]]:
    src = raw if isinstance(raw, dict) else {}
    out: Dict[str, Dict[str, str]] = {}

    for participant_uid, row in src.items():
        uid = _safe_str(participant_uid)
        if not uid or not _is_federated_participant_uid(uid):
            continue

        item = row if isinstance(row, dict) else {}
        status = _safe_str(item.get("status")).lower() or "active"
        status = "revoked" if status == "revoked" else "active"

        out[uid] = {
            "participant_uid": uid,
            "status": status,
            "revoked_at": _safe_str(item.get("revoked_at")),
            "revoked_by": _safe_str(item.get("revoked_by")),
            "updated_at": _safe_str(item.get("updated_at")),
        }

    return out


def _get_federated_member_access(meta: Dict[str, Any], participant_uid: Any) -> Dict[str, str]:
    uid = _safe_str(participant_uid)
    if not uid:
        return {}
    access = _normalize_federated_member_access(meta.get("federated_member_access"))
    return access.get(uid) or {}


def _get_federated_member_access_status(meta: Dict[str, Any], participant_uid: Any) -> str:
    uid = _safe_str(participant_uid)
    if not _is_federated_participant_uid(uid):
        return "active"
    row = _get_federated_member_access(meta, uid)
    return "revoked" if _safe_str(row.get("status")) == "revoked" else "active"


def _is_federated_member_access_revoked(meta: Dict[str, Any], participant_uid: Any) -> bool:
    return _get_federated_member_access_status(meta, participant_uid) == "revoked"


def _is_room_owner_actor(meta: Dict[str, Any], actor_uid: Any) -> bool:
    uid = _safe_str(actor_uid)
    owner_user_id = _safe_str(get_room_owner_user_id(meta))
    if not uid or not owner_user_id:
        return False
    if _is_federated_participant_uid(uid):
        return False
    return uid == owner_user_id


def _room_access_revoked(
    request_id: str,
    room_id: str,
    participant_uid: str,
) -> Dict[str, Any]:
    user_message = "Federated member access has been revoked for this room."
    return {
        "success": False,
        "status": "error",
        "request_id": request_id,
        "conv_id": room_id,
        "room_id": room_id,
        "message": user_message,
        "user_message": user_message,
        "error": user_message,
        "detail": user_message,
        "error_code": "room_access_revoked",
        "error_kind": "room_access_revoked",
        "retryable": False,
        "tool_calls": [],
        "tool_results": [
            _build_tool_result_item(
                "room_access",
                room_id=room_id,
                participant_uid=participant_uid,
                access_status="revoked",
            )
        ],
    }


def _reject_if_revoked_federated_member(
    request_id: str,
    room_id: str,
    meta: Dict[str, Any],
    participant_uid: str,
) -> Dict[str, Any] | None:
    uid = _safe_str(participant_uid)
    if not _is_federated_participant_uid(uid):
        return None
    if not _is_federated_member_access_revoked(meta, uid):
        return None
    return _room_access_revoked(request_id, room_id, uid)


def _normalize_shared_role_ids_for_state(value: Any) -> List[str]:
    out: List[str] = []
    seen = set()
    if not isinstance(value, list):
        return out

    for item in value:
        s = str(item or "").strip()
        if not s:
            continue
        sid = require_safe_id("shared_role_ids_item", s)
        if sid in seen:
            continue
        seen.add(sid)
        out.append(sid)
    return out


ROOM_PROVIDER_PREFIX = "room_provider__"


def _normalize_room_mcp_publication(
    raw: Any,
    *,
    room_id: str = "",
    fallback_enabled: bool = False,
    fallback_name: str = "",
    fallback_summary: str = "",
    updated_at: str = "",
    created_at: str = "",
) -> Dict[str, Any]:
    src = raw if isinstance(raw, dict) else {}

    publish_enabled = as_bool(src.get("publish_enabled"), fallback_enabled)
    publish_label = (
        _safe_str(src.get("publish_label"))
        if "publish_label" in src
        else _safe_str(fallback_name)
    )
    publish_summary = (
        _safe_str(src.get("publish_summary"))
        if "publish_summary" in src
        else _safe_str(fallback_summary)
    )
    boundary_hint = _safe_str(
        src.get("boundary_hint"),
        "room-configured shared capability only; owner private scope exposed=false",
    ) or "room-configured shared capability only; owner private scope exposed=false"
    visibility_mode = _safe_str(
        src.get("visibility_mode"),
        "room_visible_and_grant_capable",
    ) or "room_visible_and_grant_capable"

    publication_state = _safe_str(
        src.get("publication_state"),
        "active" if publish_enabled else "disabled",
    ).lower() or ("active" if publish_enabled else "disabled")
    if publication_state not in {"active", "disabled"}:
        publication_state = "active" if publish_enabled else "disabled"

    published_at = _safe_str(src.get("published_at"))
    if not published_at and publish_enabled:
        published_at = _safe_str(created_at) or _safe_str(updated_at)

    return {
        "provider_id": _safe_str(src.get("provider_id")) or (f"{ROOM_PROVIDER_PREFIX}{room_id}" if room_id else ""),
        "source_room_id": _safe_str(src.get("source_room_id")) or room_id,
        "publish_enabled": publish_enabled,
        "publish_label": publish_label,
        "publish_summary": publish_summary,
        "boundary_hint": boundary_hint,
        "visibility_mode": visibility_mode,
        "publication_state": publication_state,
        "published_at": published_at,
        "updated_at": _safe_str(src.get("updated_at")) or _safe_str(updated_at),
    }


def _build_room_mcp_publication(
    meta: Dict[str, Any],
    state: Dict[str, Any] | None = None,
    *,
    patch: Dict[str, Any] | None = None,
    current: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    meta_obj = meta if isinstance(meta, dict) else {}
    patch_obj = patch if isinstance(patch, dict) else {}

    room_id = _safe_str(meta_obj.get("room_id"))
    current_row = _normalize_room_mcp_publication(
        current if isinstance(current, dict) else meta_obj.get("room_mcp_publication"),
        room_id=room_id,
        fallback_enabled=as_bool(meta_obj.get("room_mcp_provider_enabled"), False),
        fallback_name=_safe_str(meta_obj.get("room_mcp_provider_name")),
        fallback_summary=_safe_str(meta_obj.get("room_mcp_provider_summary")),
        updated_at=_safe_str(meta_obj.get("updated_at")),
        created_at=_safe_str(meta_obj.get("created_at")),
    )

    publish_enabled = (
        as_bool(patch_obj.get("publish_enabled"), as_bool(meta_obj.get("room_mcp_provider_enabled"), False))
        if "publish_enabled" in patch_obj
        else as_bool(meta_obj.get("room_mcp_provider_enabled"), False)
    )

    publish_label = (
        _safe_str(patch_obj.get("publish_label"))
        if "publish_label" in patch_obj
        else _safe_str(meta_obj.get("room_mcp_provider_name"))
    )

    publish_summary = (
        _safe_str(patch_obj.get("publish_summary"))
        if "publish_summary" in patch_obj
        else _safe_str(meta_obj.get("room_mcp_provider_summary"))
    )

    boundary_hint = (
        _safe_str(patch_obj.get("boundary_hint"))
        if "boundary_hint" in patch_obj
        else _safe_str(current_row.get("boundary_hint"))
    ) or "room-configured shared capability only; owner private scope exposed=false"

    visibility_mode = (
        _safe_str(patch_obj.get("visibility_mode"))
        if "visibility_mode" in patch_obj
        else _safe_str(current_row.get("visibility_mode"))
    ) or "room_visible_and_grant_capable"

    publication_state = (
        _safe_str(patch_obj.get("publication_state"))
        if "publication_state" in patch_obj
        else ("active" if publish_enabled else "disabled")
    ).lower() or ("active" if publish_enabled else "disabled")
    if publication_state not in {"active", "disabled"}:
        publication_state = "active" if publish_enabled else "disabled"

    published_at = _safe_str(current_row.get("published_at"))
    if not published_at and publish_enabled:
        published_at = _safe_str(meta_obj.get("created_at")) or _safe_str(meta_obj.get("updated_at")) or utc_iso()

    return _normalize_room_mcp_publication(
        {
            "provider_id": f"{ROOM_PROVIDER_PREFIX}{room_id}" if room_id else "",
            "source_room_id": room_id,
            "publish_enabled": publish_enabled,
            "publish_label": publish_label,
            "publish_summary": publish_summary,
            "boundary_hint": boundary_hint,
            "visibility_mode": visibility_mode,
            "publication_state": publication_state,
            "published_at": published_at,
            "updated_at": _safe_str(meta_obj.get("updated_at")),
        },
        room_id=room_id,
        fallback_enabled=publish_enabled,
        fallback_name=publish_label,
        fallback_summary=publish_summary,
        updated_at=_safe_str(meta_obj.get("updated_at")),
        created_at=_safe_str(meta_obj.get("created_at")),
    )


def _publication_fingerprint(raw: Any) -> Dict[str, Any]:
    row = _safe_dict(raw)
    return {
        "provider_id": _safe_str(row.get("provider_id")),
        "source_room_id": _safe_str(row.get("source_room_id")),
        "publish_enabled": as_bool(row.get("publish_enabled"), False),
        "publish_label": _safe_str(row.get("publish_label")),
        "publish_summary": _safe_str(row.get("publish_summary")),
        "boundary_hint": _safe_str(row.get("boundary_hint")),
        "visibility_mode": _safe_str(row.get("visibility_mode")),
        "publication_state": _safe_str(row.get("publication_state")),
        "published_at": _safe_str(row.get("published_at")),
    }


def _normalize_room_meta_for_output(meta: Dict[str, Any]) -> Dict[str, Any]:
    src = meta if isinstance(meta, dict) else {}
    out = dict(src)

    participants = out.get("participants")
    if not isinstance(participants, list):
        participants = []

    normalized_participants = []
    seen = set()
    for item in participants:
        s = str(item or "").strip()
        if not s or s in seen:
            continue
        seen.add(s)
        normalized_participants.append(s)

    out["participants"] = normalized_participants
    out["owner_user_id"] = get_room_owner_user_id(out)

    out["shared_role_ids"] = _normalize_shared_role_ids_for_state(out.get("shared_role_ids"))
    out["shared_supervisor_enabled"] = as_bool(out.get("shared_supervisor_enabled"), False)
    out["shared_room_config_enabled"] = as_bool(out.get("shared_room_config_enabled"), False)
    out["room_mcp_provider_enabled"] = as_bool(out.get("room_mcp_provider_enabled"), False)
    out["room_mcp_provider_name"] = _safe_str(out.get("room_mcp_provider_name"))
    out["room_mcp_provider_summary"] = _safe_str(out.get("room_mcp_provider_summary"))
    out["federated_member_access"] = _normalize_federated_member_access(
        out.get("federated_member_access")
    )
    out["room_mcp_publication"] = _normalize_room_mcp_publication(
        out.get("room_mcp_publication"),
        room_id=_safe_str(out.get("room_id")),
        fallback_enabled=as_bool(out.get("room_mcp_provider_enabled"), False),
        fallback_name=_safe_str(out.get("room_mcp_provider_name")),
        fallback_summary=_safe_str(out.get("room_mcp_provider_summary")),
        updated_at=_safe_str(out.get("updated_at")),
        created_at=_safe_str(out.get("created_at")),
    )

    return out


def _derive_shared_supervisor_enabled(
    *,
    shared_room_config_enabled: Any,
    reply_mode: Any,
    supervisor_enabled: Any,
    explicit_shared_supervisor_enabled: Any = None,
) -> bool:
    shared_enabled = as_bool(shared_room_config_enabled, False)
    mode = _normalize_reply_mode(reply_mode, fallback="manual") or "manual"
    supervisor_on = as_bool(supervisor_enabled, False)

    if not shared_enabled:
        return False

    if mode in {"supervisor", "supervisor_direct"}:
        return True

    if supervisor_on:
        return True

    if explicit_shared_supervisor_enabled is not None:
        return as_bool(explicit_shared_supervisor_enabled, False)

    return False


def _resolve_shared_room_fields(
    *,
    meta: Dict[str, Any],
    state: Dict[str, Any] | None,
    args: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    meta_obj = _normalize_room_meta_for_output(meta)
    state_obj = _normalize_room_state_for_output(state if isinstance(state, dict) else {})
    arg_obj = _safe_dict(args)

    next_shared_room_config_enabled = as_bool(
        arg_obj.get("shared_room_config_enabled")
        if "shared_room_config_enabled" in arg_obj
        else meta_obj.get("shared_room_config_enabled"),
        as_bool(meta_obj.get("shared_room_config_enabled"), False),
    )

    next_shared_role_ids = (
        _normalize_shared_role_ids_for_state(arg_obj.get("shared_role_ids"))
        if "shared_role_ids" in arg_obj
        else _normalize_shared_role_ids_for_state(meta_obj.get("shared_role_ids"))
    )

    explicit_shared_supervisor_enabled = (
        arg_obj.get("shared_supervisor_enabled")
        if "shared_supervisor_enabled" in arg_obj
        else meta_obj.get("shared_supervisor_enabled")
    )

    next_shared_supervisor_enabled = _derive_shared_supervisor_enabled(
        shared_room_config_enabled=next_shared_room_config_enabled,
        reply_mode=state_obj.get("reply_mode"),
        supervisor_enabled=state_obj.get("supervisor_enabled"),
        explicit_shared_supervisor_enabled=explicit_shared_supervisor_enabled,
    )

    return {
        "shared_room_config_enabled": next_shared_room_config_enabled,
        "shared_role_ids": next_shared_role_ids,
        "shared_supervisor_enabled": next_shared_supervisor_enabled,
    }


def _sync_shared_fields_from_meta_to_state(
    meta: Dict[str, Any],
    state: Dict[str, Any] | None,
) -> Dict[str, Any]:
    resolved = _resolve_shared_room_fields(
        meta=meta,
        state=state,
        args={},
    )

    out = dict(state if isinstance(state, dict) else {})
    out["shared_room_config_enabled"] = as_bool(
        resolved.get("shared_room_config_enabled"),
        False,
    )
    out["shared_role_ids"] = _normalize_shared_role_ids_for_state(
        resolved.get("shared_role_ids")
    )
    out["shared_supervisor_enabled"] = as_bool(
        resolved.get("shared_supervisor_enabled"),
        False,
    )
    return out


def _sync_shared_fields_from_state_to_meta(
    meta: Dict[str, Any],
    state: Dict[str, Any] | None,
) -> tuple[Dict[str, Any], Dict[str, Any]]:
    meta_obj = _normalize_room_meta_for_output(meta)
    state_obj = state if isinstance(state, dict) else {}

    shared_args: Dict[str, Any] = {}
    for key in (
        "shared_room_config_enabled",
        "shared_role_ids",
        "shared_supervisor_enabled",
    ):
        if key in state_obj:
            shared_args[key] = state_obj.get(key)

    resolved = _resolve_shared_room_fields(
        meta=meta_obj,
        state=state_obj,
        args=shared_args,
    )

    changed: Dict[str, Any] = {}

    next_shared_room_config_enabled = as_bool(
        resolved.get("shared_room_config_enabled"),
        False,
    )
    next_shared_role_ids = _normalize_shared_role_ids_for_state(
        resolved.get("shared_role_ids")
    )
    next_shared_supervisor_enabled = as_bool(
        resolved.get("shared_supervisor_enabled"),
        False,
    )

    if next_shared_room_config_enabled != as_bool(meta_obj.get("shared_room_config_enabled"), False):
        meta_obj["shared_room_config_enabled"] = next_shared_room_config_enabled
        changed["shared_room_config_enabled"] = next_shared_room_config_enabled

    if next_shared_role_ids != _normalize_shared_role_ids_for_state(meta_obj.get("shared_role_ids")):
        meta_obj["shared_role_ids"] = next_shared_role_ids
        changed["shared_role_ids"] = next_shared_role_ids

    if next_shared_supervisor_enabled != as_bool(meta_obj.get("shared_supervisor_enabled"), False):
        meta_obj["shared_supervisor_enabled"] = next_shared_supervisor_enabled
        changed["shared_supervisor_enabled"] = next_shared_supervisor_enabled

    meta_obj["room_mcp_publication"] = _build_room_mcp_publication(
        meta_obj,
        state_obj,
        current=meta_obj.get("room_mcp_publication"),
    )

    return _normalize_room_meta_for_output(meta_obj), changed


def nisb_room_shared_whoami(args: Dict[str, Any]) -> Dict[str, Any]:
    basepath = get_basepath(args)
    uid = _resolve_room_actor_uid(basepath, args)
    rid = ensure_request_id(args)
    return _formal_envelope(
        request_id=rid,
        response=uid or "unknown",
        status="success",
        message="whoami ok",
        tool_calls=[],
        tool_results=[_build_tool_result_item("whoami", uid=uid, basepath=basepath)],
    )


def _event_payload(evt: Dict[str, Any]) -> Dict[str, Any]:
    payload = evt.get("payload")
    return payload if isinstance(payload, dict) else {}


def _event_sender_uid(evt: Dict[str, Any]) -> str:
    payload = _event_payload(evt)
    return _safe_str(payload.get("sender") or evt.get("sender"))


def _build_joined_members(
    room_id: str,
    meta: Dict[str, Any],
    *,
    actor_uid: str = "",
) -> List[Dict[str, Any]]:
    participants = meta.get("participants")
    if not isinstance(participants, list):
        participants = []

    normalized_participants = []
    seen = set()
    for item in participants:
        s = _safe_str(item)
        if not s or s in seen:
            continue
        seen.add(s)
        normalized_participants.append(s)

    owner_user_id = get_room_owner_user_id(meta)
    actor_can_manage_federation = _is_room_owner_actor(meta, actor_uid)
    events = load_room_events(room_id)

    member_facts: Dict[str, Dict[str, str]] = {}

    for evt in events:
        if not isinstance(evt, dict):
            continue

        evt_type = _safe_str(evt.get("type"))
        ts = _safe_str(evt.get("ts"))
        payload = _event_payload(evt)
        sender = _event_sender_uid(evt)
        if not sender:
            continue

        facts = member_facts.setdefault(
            sender,
            {
                "joined_at": "",
                "last_seen": "",
                "peer_id": "",
                "remote_user_id": "",
            },
        )

        if ts and (not facts["last_seen"] or ts > facts["last_seen"]):
            facts["last_seen"] = ts

        if evt_type == "room.join" and ts and not facts["joined_at"]:
            facts["joined_at"] = ts

        if not facts["peer_id"]:
            facts["peer_id"] = _safe_str(payload.get("federation_peer_id"))

        if not facts["remote_user_id"]:
            facts["remote_user_id"] = _safe_str(payload.get("federation_remote_user_id"))

    rows: List[Dict[str, Any]] = []

    for participant_uid in normalized_participants:
        parsed = _parse_federated_participant_uid(participant_uid)
        facts = member_facts.get(participant_uid) or {}

        peer_id = _safe_str(facts.get("peer_id")) or parsed.get("peer_id") or ""
        remote_user_id = _safe_str(facts.get("remote_user_id")) or parsed.get("remote_user_id") or ""
        access_status = _get_federated_member_access_status(meta, participant_uid)
        is_federated = parsed.get("type") == "federated"

        rows.append(
            {
                "participant_uid": participant_uid,
                "uid": participant_uid,
                "type": parsed.get("type") or "local",
                "peer_id": peer_id,
                "remote_user_id": remote_user_id,
                "joined_at": _safe_str(facts.get("joined_at")),
                "last_seen": _safe_str(facts.get("last_seen")),
                "is_owner": participant_uid == owner_user_id,
                "access_status": access_status,
                "can_revoke_access": bool(
                    actor_can_manage_federation
                    and is_federated
                    and participant_uid != owner_user_id
                    and access_status == "active"
                ),
                "is_access_revoked": access_status == "revoked",
            }
        )

    rows.sort(
        key=lambda row: (
            0 if row.get("is_owner") else 1,
            0 if row.get("type") == "local" else 1,
            _safe_str(row.get("participant_uid")),
        )
    )
    return rows


def nisb_room_shared_create(args: Dict[str, Any]) -> Dict[str, Any]:
    basepath = get_basepath(args)
    uid = _resolve_room_actor_uid(basepath, args, allow_federation=False)
    rid = ensure_request_id(args)

    title = str(args.get("title") or "New Room").strip() or "New Room"
    participants = args.get("participants") if isinstance(args.get("participants"), list) else []
    participants = [str(x).strip() for x in participants if str(x).strip()]
    if uid and uid not in participants:
        participants.append(uid)

    ensure_dir(SHARED_ROOT)
    room_id = new_id("room")
    ensure_room_paths(room_id)

    join_key = secrets.token_hex(8)
    meta = {
        "room_id": room_id,
        "title": title,
        "participants": participants,
        "owner_user_id": uid,
        "shared_role_ids": [],
        "shared_supervisor_enabled": False,
        "shared_room_config_enabled": False,
        "room_mcp_provider_enabled": False,
        "room_mcp_provider_name": "",
        "room_mcp_provider_summary": "",
        "join_key": join_key,
        "created_at": utc_iso(),
        "updated_at": utc_iso(),
        "visibility": "shared_local",
        "federated_member_access": {},
    }
    raw_state = _sync_shared_fields_from_meta_to_state(meta, default_room_state())
    state = _normalize_room_state_for_output(raw_state)
    meta["room_mcp_publication"] = _build_room_mcp_publication(meta, state)
    meta = _normalize_room_meta_for_output(meta)

    save_meta(room_id, meta)
    save_state_doc(room_id, state)

    create_evt = {
        "id": new_id("evt"),
        "ts": utc_iso(),
        "type": "room.create",
        "room_id": room_id,
        "request_id": rid,
        "payload": meta,
    }
    append_room_event(room_id, create_evt)

    return _formal_envelope(
        request_id=rid,
        conv_id=room_id,
        mcp_overrides=state.get("mcp_overrides"),
        response=f"Room created: {title}",
        status="success",
        message="room created",
        tool_calls=[],
        tool_results=[
            _build_tool_result_item("room_info", room=meta, roles=[], state=state),
            _build_tool_result_item("room_event", event=create_evt),
        ],
    )


def nisb_room_shared_list(args: Dict[str, Any]) -> Dict[str, Any]:
    basepath = get_basepath(args)
    uid = _resolve_room_actor_uid(basepath, args)
    rid = ensure_request_id(args)

    rooms = [_normalize_room_meta_for_output(x) for x in list_room_metas_for_uid(uid)]
    return _formal_envelope(
        request_id=rid,
        response=f"Loaded {len(rooms)} rooms.",
        status="success",
        message="room list loaded",
        tool_calls=[],
        tool_results=[_build_tool_result_item("room_list", rooms=rooms)],
    )


def nisb_room_get_info(args: Dict[str, Any]) -> Dict[str, Any]:
    basepath = get_basepath(args)
    uid = _resolve_room_actor_uid(basepath, args)
    rid = ensure_request_id(args)

    room_id = require_safe_id("room_id", args.get("room_id"))
    meta = _normalize_room_meta_for_output(ensure_room_exists(room_id))

    revoked = _reject_if_revoked_federated_member(rid, room_id, meta, uid)
    if revoked:
        return revoked

    if meta and not is_participant(uid, meta):
        return _permission_denied(rid, room_id)

    from .room_roles import list_roles

    roles = list_roles(room_id)
    state = _normalize_room_state_for_output(load_state_doc(room_id))
    joined_members = _build_joined_members(room_id, meta, actor_uid=uid)

    room_output = dict(meta)
    room_output["joined_members"] = joined_members
    room_output["joined_members_count"] = len(joined_members)

    return _formal_envelope(
        request_id=rid,
        conv_id=room_id,
        mcp_overrides=state.get("mcp_overrides"),
        response=f"Loaded room info for {meta.get('title') or room_id}.",
        status="success",
        message="room info loaded",
        tool_calls=[],
        tool_results=[
            _build_tool_result_item(
                "room_info",
                room=room_output,
                roles=roles,
                state=state,
                roles_count=len(roles),
                participants_count=len(meta.get("participants") or []),
                joined_members=joined_members,
                joined_members_count=len(joined_members),
            )
        ],
    )


def nisb_room_update_info(args: Dict[str, Any]) -> Dict[str, Any]:
    basepath = get_basepath(args)
    uid = _resolve_room_actor_uid(basepath, args)
    rid = ensure_request_id(args)

    room_id = require_safe_id("room_id", args.get("room_id"))
    meta = _normalize_room_meta_for_output(ensure_room_exists(room_id))

    revoked = _reject_if_revoked_federated_member(rid, room_id, meta, uid)
    if revoked:
        return revoked

    if meta and not can_edit_room_info(uid, meta):
        return _permission_denied(rid, room_id)

    changed: Dict[str, Any] = {}

    current_publication = _normalize_room_mcp_publication(
        meta.get("room_mcp_publication"),
        room_id=room_id,
        fallback_enabled=as_bool(meta.get("room_mcp_provider_enabled"), False),
        fallback_name=_safe_str(meta.get("room_mcp_provider_name")),
        fallback_summary=_safe_str(meta.get("room_mcp_provider_summary")),
        updated_at=_safe_str(meta.get("updated_at")),
        created_at=_safe_str(meta.get("created_at")),
    )

    title = str(args.get("title") or meta.get("title") or "New Room").strip() or "New Room"
    if title != _safe_str(meta.get("title")):
        meta["title"] = title
        changed["title"] = title

    if "room_mcp_provider_enabled" in args:
        v = as_bool(args.get("room_mcp_provider_enabled"), False)
        if v != as_bool(meta.get("room_mcp_provider_enabled"), False):
            meta["room_mcp_provider_enabled"] = v
            changed["room_mcp_provider_enabled"] = v

    if "room_mcp_provider_name" in args:
        v = _safe_str(args.get("room_mcp_provider_name"))
        if v != _safe_str(meta.get("room_mcp_provider_name")):
            meta["room_mcp_provider_name"] = v
            changed["room_mcp_provider_name"] = v

    if "room_mcp_provider_summary" in args:
        v = _safe_str(args.get("room_mcp_provider_summary"))
        if v != _safe_str(meta.get("room_mcp_provider_summary")):
            meta["room_mcp_provider_summary"] = v
            changed["room_mcp_provider_summary"] = v

    raw_state = load_state_doc(room_id)
    resolved_shared = _resolve_shared_room_fields(
        meta=meta,
        state=raw_state,
        args=args,
    )

    next_shared_room_config_enabled = as_bool(
        resolved_shared.get("shared_room_config_enabled"),
        False,
    )
    next_shared_role_ids = _normalize_shared_role_ids_for_state(
        resolved_shared.get("shared_role_ids")
    )
    next_shared_supervisor_enabled = as_bool(
        resolved_shared.get("shared_supervisor_enabled"),
        False,
    )

    if next_shared_room_config_enabled != as_bool(meta.get("shared_room_config_enabled"), False):
        meta["shared_room_config_enabled"] = next_shared_room_config_enabled
        changed["shared_room_config_enabled"] = next_shared_room_config_enabled

    if next_shared_role_ids != _normalize_shared_role_ids_for_state(meta.get("shared_role_ids")):
        meta["shared_role_ids"] = next_shared_role_ids
        changed["shared_role_ids"] = next_shared_role_ids

    if next_shared_supervisor_enabled != as_bool(meta.get("shared_supervisor_enabled"), False):
        meta["shared_supervisor_enabled"] = next_shared_supervisor_enabled
        changed["shared_supervisor_enabled"] = next_shared_supervisor_enabled

    publication_patch = _safe_dict(args.get("room_mcp_publication_patch"))
    meta["updated_at"] = utc_iso()

    next_publication = _build_room_mcp_publication(
        meta,
        raw_state,
        patch=publication_patch,
        current=current_publication,
    )
    publication_changed = _publication_fingerprint(next_publication) != _publication_fingerprint(current_publication)
    meta["room_mcp_publication"] = next_publication
    if publication_changed:
        changed["room_mcp_publication"] = next_publication

    meta = _normalize_room_meta_for_output(meta)
    save_meta(room_id, meta)
    touch_room_updated_at(room_id)

    shared_keys = {
        "shared_room_config_enabled",
        "shared_role_ids",
        "shared_supervisor_enabled",
    }

    if any(k in changed for k in shared_keys):
        raw_state = _sync_shared_fields_from_meta_to_state(meta, raw_state)
        raw_state["updated_at"] = utc_iso()
        save_state_doc(room_id, raw_state)
        touch_room_updated_at(room_id)
        state = _normalize_room_state_for_output(raw_state)
    else:
        state = _normalize_room_state_for_output(load_state_doc(room_id))

    evt = {
        "id": new_id("evt"),
        "ts": utc_iso(),
        "type": "room.settings_update",
        "room_id": room_id,
        "request_id": rid,
        "payload": {
            "sender": uid,
            "changed": changed,
        },
    }
    append_room_event(room_id, evt)

    tool_results = [
        _build_tool_result_item("room_info", room=meta),
        _build_tool_result_item("room_event", event=evt),
    ]

    if publication_changed:
        pub_evt = {
            "id": new_id("evt"),
            "ts": utc_iso(),
            "type": "room.mcp_publication_update",
            "room_id": room_id,
            "request_id": rid,
            "payload": {
                "sender": uid,
                "provider_id": _safe_str(next_publication.get("provider_id")),
                "source_room_id": room_id,
                "publication_state": _safe_str(next_publication.get("publication_state")),
                "visibility_mode": _safe_str(next_publication.get("visibility_mode")),
                "changed": {
                    "room_mcp_publication": next_publication,
                },
            },
        }
        append_room_event(room_id, pub_evt)
        tool_results.append(_build_tool_result_item("room_event", event=pub_evt))

    return _formal_envelope(
        request_id=rid,
        conv_id=room_id,
        mcp_overrides=state.get("mcp_overrides"),
        response=f"Room info updated for {meta.get('title') or room_id}.",
        status="success",
        message="room info updated",
        tool_calls=[],
        tool_results=tool_results,
    )


def nisb_room_get_state(args: Dict[str, Any]) -> Dict[str, Any]:
    basepath = get_basepath(args)
    uid = _resolve_room_actor_uid(basepath, args)
    rid = ensure_request_id(args)

    room_id = require_safe_id("room_id", args.get("room_id"))
    meta = _normalize_room_meta_for_output(ensure_room_exists(room_id))

    revoked = _reject_if_revoked_federated_member(rid, room_id, meta, uid)
    if revoked:
        return revoked

    if meta and not is_participant(uid, meta):
        return _permission_denied(rid, room_id)

    state = _normalize_room_state_for_output(load_state_doc(room_id))
    return _formal_envelope(
        request_id=rid,
        conv_id=room_id,
        mcp_overrides=state.get("mcp_overrides"),
        response="room state loaded",
        status="success",
        message="room state loaded",
        tool_calls=[],
        tool_results=[_build_tool_result_item("room_state", room_id=room_id, state=state)],
    )


def nisb_room_update_state(args: Dict[str, Any]) -> Dict[str, Any]:
    basepath = get_basepath(args)
    uid = _resolve_room_actor_uid(basepath, args)
    rid = ensure_request_id(args)

    room_id = require_safe_id("room_id", args.get("room_id"))
    meta = _normalize_room_meta_for_output(ensure_room_exists(room_id))

    revoked = _reject_if_revoked_federated_member(rid, room_id, meta, uid)
    if revoked:
        return revoked

    if meta and not can_edit_room_state(uid, meta):
        return _permission_denied(rid, room_id)

    raw_state = load_state_doc(room_id)
    prev_state = _normalize_room_state_for_output(raw_state)
    state = dict(prev_state)

    allowed = {
        "summary",
        "scratchpad",
        "active_roles",
        "enabled_supervisor_skill_ids",
        "supervisor_skill_strategy",
        "inherit_workspace_context",
        "inherit_focus_root",
        "default_reply_role_id",
        "supervisor_enabled",
        "reply_mode",
        "max_worker_concurrency",
        "shared_room_config_enabled",
        "shared_role_ids",
        "shared_supervisor_enabled",
        "supervisor_provider",
        "supervisor_model",
        "supervisor_temperature",
        "supervisor_max_tokens",
        "supervisor_step_budget_total",
        "mcp_overrides",
        "current_run_id",
        "current_run_status",
        "current_run_roles",
        "current_delegate_role_id",
        "current_delegate_role_name",
        "current_delegate_index",
        "current_delegate_total",
        "last_plan_summary",
        "last_plan_at",
        "last_run_finished_at",
        "last_message_id",
    }

    changed: Dict[str, Any] = {}
    for k in allowed:
        if k not in args:
            continue

        v = args.get(k)

        if k in (
            "inherit_workspace_context",
            "inherit_focus_root",
            "supervisor_enabled",
            "shared_room_config_enabled",
            "shared_supervisor_enabled",
        ):
            v = as_bool(v, state.get(k, False))
        elif k in ("active_roles", "shared_role_ids"):
            vv = []
            if isinstance(v, list):
                for item in v:
                    s = str(item or "").strip()
                    if not s:
                        continue
                    sid = require_safe_id(f"{k}_item", s)
                    if sid not in vv:
                        vv.append(sid)
            v = vv
        elif k == "enabled_supervisor_skill_ids":
            v = _normalize_enabled_supervisor_skill_ids(v, fallback=state.get("enabled_supervisor_skill_ids"))
        elif k == "supervisor_skill_strategy":
            v = _normalize_supervisor_skill_strategy(
                v,
                fallback=_safe_str(state.get("supervisor_skill_strategy"), "builtin_plus_custom"),
            )
        elif k in ("default_reply_role_id", "current_run_id", "current_delegate_role_id", "last_message_id"):
            s = str(v or "").strip()
            v = require_safe_id(k, s) if s else ""
        elif k == "reply_mode":
            current_reply_mode = _normalize_reply_mode(state.get("reply_mode"), fallback="manual") or "manual"
            v = _normalize_reply_mode(v, fallback=current_reply_mode) or current_reply_mode
        elif k == "supervisor_provider":
            v = _normalize_supervisor_provider(v, fallback=_safe_str(state.get("supervisor_provider"), "openai"))
        elif k == "supervisor_model":
            v = str(v or "").strip()
        elif k == "supervisor_temperature":
            parsed = _normalize_room_float(v, None)
            v = parsed if parsed is not None else ""
        elif k == "supervisor_max_tokens":
            parsed = _normalize_room_int(v, None)
            v = parsed if parsed is not None else ""
        elif k == "supervisor_step_budget_total":
            parsed = _normalize_room_int(v, 0)
            v = max(0, parsed or 0)
        elif k == "mcp_overrides":
            v = _normalize_room_mcp_overrides(v, fallback=state.get("mcp_overrides"))
        elif k == "current_run_roles":
            vv = []
            if isinstance(v, list):
                for item in v:
                    s = str(item or "").strip()
                    if not s:
                        continue
                    vv.append(require_safe_id("current_run_roles_item", s))
            v = vv
        elif k in ("current_delegate_index", "current_delegate_total"):
            try:
                v = max(0, int(v))
            except Exception:
                v = 0
        else:
            v = str(v or "").strip()

        state[k] = v
        changed[k] = v

    state["reply_mode"] = _normalize_reply_mode(state.get("reply_mode")) or _derive_reply_mode_from_state(state) or "manual"

    try:
        state["max_worker_concurrency"] = int(float(state.get("max_worker_concurrency") or 2))
    except Exception:
        state["max_worker_concurrency"] = 2
    state["max_worker_concurrency"] = max(1, min(4, state["max_worker_concurrency"]))

    if state["reply_mode"] in {"supervisor", "supervisor_direct"}:
        state["supervisor_enabled"] = True
    else:
        state["supervisor_enabled"] = as_bool(state.get("supervisor_enabled"), False)

    resolved_shared = _resolve_shared_room_fields(
        meta=meta,
        state=state,
        args=args,
    )

    next_shared_room_config_enabled = as_bool(
        resolved_shared.get("shared_room_config_enabled"),
        False,
    )
    next_shared_role_ids = _normalize_shared_role_ids_for_state(
        resolved_shared.get("shared_role_ids")
    )
    next_shared_supervisor_enabled = as_bool(
        resolved_shared.get("shared_supervisor_enabled"),
        False,
    )

    if next_shared_room_config_enabled != as_bool(prev_state.get("shared_room_config_enabled"), False):
        changed["shared_room_config_enabled"] = next_shared_room_config_enabled
    if next_shared_role_ids != _normalize_shared_role_ids_for_state(prev_state.get("shared_role_ids")):
        changed["shared_role_ids"] = next_shared_role_ids
    if next_shared_supervisor_enabled != as_bool(prev_state.get("shared_supervisor_enabled"), False):
        changed["shared_supervisor_enabled"] = next_shared_supervisor_enabled

    if state["supervisor_enabled"] != as_bool(prev_state.get("supervisor_enabled"), False):
        changed["supervisor_enabled"] = state["supervisor_enabled"]

    state["shared_room_config_enabled"] = next_shared_room_config_enabled
    state["shared_role_ids"] = next_shared_role_ids
    state["shared_supervisor_enabled"] = next_shared_supervisor_enabled

    state["supervisor_provider"] = _normalize_supervisor_provider(state.get("supervisor_provider"), "openai")
    state["supervisor_model"] = _safe_str(state.get("supervisor_model"))
    state["enabled_supervisor_skill_ids"] = _normalize_enabled_supervisor_skill_ids(
        state.get("enabled_supervisor_skill_ids"),
        fallback=[],
    )
    state["supervisor_skill_strategy"] = _normalize_supervisor_skill_strategy(
        state.get("supervisor_skill_strategy"),
        "builtin_plus_custom",
    )
    state["supervisor_step_budget_total"] = max(
        0,
        _normalize_room_int(state.get("supervisor_step_budget_total"), 0) or 0,
    )
    state["mcp_overrides"] = _normalize_room_mcp_overrides(state.get("mcp_overrides"))
    state["updated_at"] = utc_iso()

    meta_before_sync = _normalize_room_meta_for_output(meta)
    publication_before_sync = _normalize_room_mcp_publication(
        meta_before_sync.get("room_mcp_publication"),
        room_id=room_id,
        fallback_enabled=as_bool(meta_before_sync.get("room_mcp_provider_enabled"), False),
        fallback_name=_safe_str(meta_before_sync.get("room_mcp_provider_name")),
        fallback_summary=_safe_str(meta_before_sync.get("room_mcp_provider_summary")),
        updated_at=_safe_str(meta_before_sync.get("updated_at")),
        created_at=_safe_str(meta_before_sync.get("created_at")),
    )

    meta_after_sync, meta_shared_changed = _sync_shared_fields_from_state_to_meta(meta, state)
    publication_after_sync = _normalize_room_mcp_publication(
        meta_after_sync.get("room_mcp_publication"),
        room_id=room_id,
        fallback_enabled=as_bool(meta_after_sync.get("room_mcp_provider_enabled"), False),
        fallback_name=_safe_str(meta_after_sync.get("room_mcp_provider_name")),
        fallback_summary=_safe_str(meta_after_sync.get("room_mcp_provider_summary")),
        updated_at=_safe_str(meta_after_sync.get("updated_at")),
        created_at=_safe_str(meta_after_sync.get("created_at")),
    )

    publication_changed = _publication_fingerprint(publication_before_sync) != _publication_fingerprint(publication_after_sync)

    if meta_shared_changed or publication_changed:
        meta_after_sync["updated_at"] = utc_iso()
        meta_after_sync["room_mcp_publication"] = _build_room_mcp_publication(
            meta_after_sync,
            state,
            current=publication_after_sync,
        )
        meta_after_sync = _normalize_room_meta_for_output(meta_after_sync)
        save_meta(room_id, meta_after_sync)
        meta = meta_after_sync
    else:
        meta = _normalize_room_meta_for_output(meta)

    save_state_doc(room_id, state)
    touch_room_updated_at(room_id)

    normalized_state = _normalize_room_state_for_output(state)

    evt = {
        "id": new_id("evt"),
        "ts": utc_iso(),
        "type": "room.state_update",
        "room_id": room_id,
        "request_id": rid,
        "payload": {
            "sender": uid,
            "changed": changed,
        },
    }
    append_room_event(room_id, evt)

    tool_results = [
        _build_tool_result_item("room_state", room_id=room_id, state=normalized_state),
        _build_tool_result_item("room_event", event=evt),
    ]

    if publication_changed:
        next_publication = _normalize_room_mcp_publication(
            meta.get("room_mcp_publication"),
            room_id=room_id,
            fallback_enabled=as_bool(meta.get("room_mcp_provider_enabled"), False),
            fallback_name=_safe_str(meta.get("room_mcp_provider_name")),
            fallback_summary=_safe_str(meta.get("room_mcp_provider_summary")),
            updated_at=_safe_str(meta.get("updated_at")),
            created_at=_safe_str(meta.get("created_at")),
        )
        pub_evt = {
            "id": new_id("evt"),
            "ts": utc_iso(),
            "type": "room.mcp_publication_update",
            "room_id": room_id,
            "request_id": rid,
            "payload": {
                "sender": uid,
                "provider_id": _safe_str(next_publication.get("provider_id")),
                "source_room_id": room_id,
                "publication_state": _safe_str(next_publication.get("publication_state")),
                "visibility_mode": _safe_str(next_publication.get("visibility_mode")),
                "changed": {
                    "room_mcp_publication": next_publication,
                },
            },
        }
        append_room_event(room_id, pub_evt)
        tool_results.append(_build_tool_result_item("room_event", event=pub_evt))

    return _formal_envelope(
        request_id=rid,
        conv_id=room_id,
        mcp_overrides=normalized_state.get("mcp_overrides"),
        response="room state updated",
        status="success",
        message="room state updated",
        tool_calls=[],
        tool_results=tool_results,
    )


def nisb_room_revoke_federated_member_access(args: Dict[str, Any]) -> Dict[str, Any]:
    basepath = get_basepath(args)
    actor_uid = _resolve_room_actor_uid(basepath, args, allow_federation=True)
    rid = ensure_request_id(args)

    room_id = require_safe_id("room_id", args.get("room_id"))
    participant_uid = _safe_str(args.get("participant_uid") or args.get("uid"))
    if not participant_uid:
        return _missing_args(rid, room_id, "missing participant_uid")

    meta = _normalize_room_meta_for_output(ensure_room_exists(room_id))

    if not _is_room_owner_actor(meta, actor_uid):
        return _permission_denied(rid, room_id)

    owner_user_id = _safe_str(get_room_owner_user_id(meta))

    if not _is_federated_participant_uid(participant_uid):
        return {
            "success": False,
            "status": "error",
            "request_id": rid,
            "conv_id": room_id,
            "room_id": room_id,
            "message": "participant is not a federated member",
            "user_message": "participant is not a federated member",
            "error_code": "invalid_federated_participant",
            "error_kind": "invalid_federated_participant",
            "retryable": False,
            "tool_calls": [],
            "tool_results": [
                _build_tool_result_item(
                    "room_access",
                    room_id=room_id,
                    participant_uid=participant_uid,
                    access_status="active",
                )
            ],
        }

    participants = meta.get("participants")
    if not isinstance(participants, list):
        participants = []

    normalized_participants = [_safe_str(item) for item in participants if _safe_str(item)]
    if participant_uid not in normalized_participants:
        return {
            "success": False,
            "status": "error",
            "request_id": rid,
            "conv_id": room_id,
            "room_id": room_id,
            "message": "participant not found",
            "user_message": "participant not found",
            "error_code": "participant_not_found",
            "error_kind": "participant_not_found",
            "retryable": False,
            "tool_calls": [],
            "tool_results": [
                _build_tool_result_item(
                    "room_access",
                    room_id=room_id,
                    participant_uid=participant_uid,
                    access_status="active",
                )
            ],
        }

    access = _normalize_federated_member_access(meta.get("federated_member_access"))
    current = access.get(participant_uid) or {}
    already_revoked = _safe_str(current.get("status")) == "revoked"

    access[participant_uid] = {
        "participant_uid": participant_uid,
        "status": "revoked",
        "revoked_at": _safe_str(current.get("revoked_at")) or utc_iso(),
        "revoked_by": _safe_str(current.get("revoked_by")) or owner_user_id,
        "updated_at": utc_iso(),
    }

    meta["federated_member_access"] = access
    meta["updated_at"] = utc_iso()
    meta = _normalize_room_meta_for_output(meta)
    save_meta(room_id, meta)

    parsed = _parse_federated_participant_uid(participant_uid)
    evt = {
        "id": new_id("evt"),
        "ts": utc_iso(),
        "type": "room.member_access_revoked",
        "room_id": room_id,
        "request_id": rid,
        "payload": {
            "sender": owner_user_id,
            "participant_uid": participant_uid,
            "access_status": "revoked",
            "federation_peer_id": parsed.get("peer_id") or "",
            "federation_remote_user_id": parsed.get("remote_user_id") or "",
        },
    }
    append_room_event(room_id, evt)

    state = _normalize_room_state_for_output(load_state_doc(room_id))
    joined_members = _build_joined_members(room_id, meta, actor_uid=owner_user_id)

    room_output = dict(meta)
    room_output["joined_members"] = joined_members
    room_output["joined_members_count"] = len(joined_members)

    response = "Federated member access revoked."
    if already_revoked:
        response = "Federated member access already revoked."

    return _formal_envelope(
        request_id=rid,
        conv_id=room_id,
        mcp_overrides=state.get("mcp_overrides"),
        response=response,
        status="success",
        message="federated member access revoked",
        tool_calls=[],
        tool_results=[
            _build_tool_result_item(
                "room_access",
                room_id=room_id,
                participant_uid=participant_uid,
                access_status="revoked",
                revoked_by=owner_user_id,
                already_revoked=already_revoked,
            ),
            _build_tool_result_item(
                "room_info",
                room=room_output,
                state=state,
                joined_members=joined_members,
                joined_members_count=len(joined_members),
            ),
            _build_tool_result_item("room_event", event=evt),
        ],
    )


def nisb_room_shared_join(args: Dict[str, Any]) -> Dict[str, Any]:
    basepath = get_basepath(args)

    federation_peer_id = str(args.get("_federation_peer_id") or "").strip()
    federation_remote_user_id = str(args.get("_federation_remote_user_id") or "").strip()
    federation_remote_label = str(args.get("_federation_remote_label") or "").strip()

    uid = _resolve_room_actor_uid(basepath, args)
    if federation_peer_id and federation_remote_user_id:
        uid = f"fed__{federation_peer_id}__{federation_remote_user_id}"

    rid = ensure_request_id(args)

    room_id = require_safe_id("room_id", args.get("room_id"))
    key = str(args.get("join_key") or "").strip()
    if not key:
        return _missing_args(rid, room_id, "missing room_id/join_key")

    meta = _normalize_room_meta_for_output(ensure_room_exists(room_id))
    if str(meta.get("join_key") or "") != key:
        return {
            "success": False,
            "status": "error",
            "request_id": rid,
            "conv_id": room_id,
            "room_id": room_id,
            "message": "invalid join_key",
            "user_message": "invalid join_key",
            "error_code": "invalid_join_key",
            "error_kind": "invalid_join_key",
            "retryable": False,
            "tool_calls": [],
            "tool_results": [],
        }

    revoked = _reject_if_revoked_federated_member(rid, room_id, meta, uid)
    if revoked:
        return revoked

    ps = meta.get("participants")
    if not isinstance(ps, list):
        ps = []
    ps = [str(x).strip() for x in ps if str(x).strip()]
    if uid and uid not in ps:
        ps.append(uid)

    meta["participants"] = ps
    meta["updated_at"] = utc_iso()
    meta = _normalize_room_meta_for_output(meta)
    save_meta(room_id, meta)

    evt_payload = {"sender": uid}
    if federation_peer_id:
        evt_payload["federation_peer_id"] = federation_peer_id
    if federation_remote_user_id:
        evt_payload["federation_remote_user_id"] = federation_remote_user_id
    if federation_remote_label:
        evt_payload["federation_remote_label"] = federation_remote_label

    evt = {
        "id": new_id("evt"),
        "ts": utc_iso(),
        "type": "room.join",
        "room_id": room_id,
        "request_id": rid,
        "payload": evt_payload,
    }
    append_room_event(room_id, evt)

    state = _normalize_room_state_for_output(load_state_doc(room_id))

    return _formal_envelope(
        request_id=rid,
        conv_id=room_id,
        mcp_overrides=state.get("mcp_overrides"),
        response=f"Joined room {meta.get('title') or room_id}.",
        status="success",
        message="room joined",
        tool_calls=[],
        tool_results=[
            _build_tool_result_item("room_info", room=meta),
            _build_tool_result_item("room_event", event=evt),
        ],
    )


__all__ = [
    "_federated_participant_uid",
    "_normalize_room_meta_for_output",
    "_normalize_room_mcp_publication",
    "_resolve_room_actor_uid",
    "nisb_room_shared_whoami",
    "nisb_room_shared_create",
    "nisb_room_shared_list",
    "nisb_room_get_info",
    "nisb_room_update_info",
    "nisb_room_get_state",
    "nisb_room_update_state",
    "nisb_room_revoke_federated_member_access",
    "nisb_room_shared_join",
]

