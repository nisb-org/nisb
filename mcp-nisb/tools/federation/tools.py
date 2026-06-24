from __future__ import annotations

import os
import secrets
import time
from datetime import datetime, timezone
from importlib import import_module
from typing import Any, Dict, List, Optional

from core.storage import load_json

from ..rooms_shared.room_store import uid_from_ctx_or_basepath
from .federation_remote_mcp_client import (
    _error_result,
    _is_error_like_payload,
    _normalize_remote_error,
    _remote_mcp_call,
    _structured_remote_failure,
)
from .federation_room_membership_registry import (
    _atomic_save_json,
    _ensure_dir,
    _fed_invites_json,
    _fed_joined_rooms_json,
    _fed_root,
    _load_joined_rooms,
    _load_room_invites,
    _upsert_joined_room,
    _write_joined_rooms,
    _write_room_invites,
)


def _utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_str(value: Any) -> str:
    return str(value or "").strip()


def _safe_lower(value: Any) -> str:
    return _safe_str(value).lower()


def _get_basepath(args: Dict[str, Any]) -> str:
    bp = args.get("basepath") or args.get("base_path") or args.get("basePath")
    bp = _safe_str(bp)
    if not bp:
        raise ValueError("missing injected basepath in tool args")
    return bp


def _peers_json(basepath: str) -> str:
    return os.path.join(_fed_root(basepath), "peers.json")


def _load_peers(basepath: str) -> Dict[str, Any]:
    doc = load_json(_peers_json(basepath))
    if isinstance(doc, dict) and isinstance(doc.get("peers"), list):
        return doc
    return {"version": 1, "updated_at": _utc_iso(), "peers": []}


def _write_peers(basepath: str, doc: Dict[str, Any]) -> None:
    doc["updated_at"] = _utc_iso()
    _atomic_save_json(_peers_json(basepath), doc)


def _find_peer(basepath: str, peer_id: str) -> Optional[Dict[str, Any]]:
    doc = _load_peers(basepath)
    for peer in (doc.get("peers") or []):
        if isinstance(peer, dict) and _safe_str(peer.get("peer_id")) == _safe_str(peer_id):
            return peer
    return None

def _list_enabled_peers(basepath: str) -> List[Dict[str, Any]]:
    doc = _load_peers(basepath)
    peers: List[Dict[str, Any]] = []
    for row in (doc.get("peers") or []):
        if not isinstance(row, dict):
            continue
        if not bool(row.get("enabled", True)):
            continue
        peers.append(dict(row))

    peers.sort(
        key=lambda item: (
            _safe_str(item.get("updated_at")),
            _safe_str(item.get("created_at")),
            _safe_str(item.get("peer_id")),
        ),
        reverse=True,
    )
    return peers

def _pick_recent_joined_peer(
    basepath: str,
    rows: List[Dict[str, Any]],
) -> str:
    candidates: List[Dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        peer_id = _safe_str(row.get("peer_id"))
        if not peer_id:
            continue
        peer = _find_peer(basepath, peer_id)
        if not peer or not bool(peer.get("enabled", True)):
            continue
        candidates.append(row)

    candidates.sort(
        key=lambda item: (
            _safe_str(item.get("last_entered_at")),
            _safe_str(item.get("updated_at")),
            _safe_str(item.get("joined_at")),
        ),
        reverse=True,
    )

    if not candidates:
        return ""
    return _safe_str(candidates[0].get("peer_id"))

def _resolve_peer_id_for_room_mcp_grant(
    basepath: str,
    *,
    source_room_id: str = "",
    remote_user_id: str = "",
    target_peer_id: str = "",
    requested_peer_id: str = "",
) -> Dict[str, Any]:
    basepath = _safe_str(basepath)
    source_room_id = _safe_str(source_room_id)
    remote_user_id = _safe_str(remote_user_id)
    target_peer_id = _safe_str(target_peer_id)
    requested_peer_id = _safe_str(requested_peer_id)

    for candidate, resolve_mode in (
        (requested_peer_id, "requested_peer_id"),
        (target_peer_id, "target_peer_id"),
    ):
        if not candidate:
            continue
        peer = _find_peer(basepath, candidate)
        if peer and bool(peer.get("enabled", True)):
            return {
                "success": True,
                "peer_id": candidate,
                "resolve_mode": resolve_mode,
                "source_room_id": source_room_id,
                "remote_user_id": remote_user_id,
                "target_peer_id": target_peer_id,
                "requested_peer_id": requested_peer_id,
            }

    joined_doc = _load_joined_rooms(basepath)
    joined_rows = [row for row in (joined_doc.get("rooms") or []) if isinstance(row, dict)]

    source_matches: List[Dict[str, Any]] = []
    remote_user_matches: List[Dict[str, Any]] = []

    for row in joined_rows:
        owner_room_id = _safe_str(row.get("owner_room_id"))
        room_id = _safe_str(row.get("room_id"))
        row_remote_user_id = _safe_str(row.get("remote_user_id"))

        if source_room_id and (owner_room_id == source_room_id or room_id == source_room_id):
            source_matches.append(row)

        if remote_user_id and row_remote_user_id == remote_user_id:
            remote_user_matches.append(row)

    peer_id = _pick_recent_joined_peer(basepath, source_matches)
    if peer_id:
        return {
            "success": True,
            "peer_id": peer_id,
            "resolve_mode": "joined_room_by_source_room",
            "source_room_id": source_room_id,
            "remote_user_id": remote_user_id,
            "target_peer_id": target_peer_id,
            "requested_peer_id": requested_peer_id,
        }

    peer_id = _pick_recent_joined_peer(basepath, remote_user_matches)
    if peer_id:
        return {
            "success": True,
            "peer_id": peer_id,
            "resolve_mode": "joined_room_by_remote_user",
            "source_room_id": source_room_id,
            "remote_user_id": remote_user_id,
            "target_peer_id": target_peer_id,
            "requested_peer_id": requested_peer_id,
        }

    enabled_peers = _list_enabled_peers(basepath)
    if len(enabled_peers) == 1:
        only_peer_id = _safe_str(enabled_peers[0].get("peer_id"))
        return {
            "success": True,
            "peer_id": only_peer_id,
            "resolve_mode": "single_enabled_peer_fallback",
            "source_room_id": source_room_id,
            "remote_user_id": remote_user_id,
            "target_peer_id": target_peer_id,
            "requested_peer_id": requested_peer_id,
        }

    return {
        "success": False,
        "peer_id": "",
        "error_code": "missing_remote_peer_id" if len(enabled_peers) <= 1 else "ambiguous_remote_peer_id",
        "error_kind": "peer_resolution",
        "message": "unable to resolve remote peer id for granted imported provider",
        "source_room_id": source_room_id,
        "remote_user_id": remote_user_id,
        "target_peer_id": target_peer_id,
        "requested_peer_id": requested_peer_id,
        "enabled_peers_count": len(enabled_peers),
        "joined_source_matches": len(source_matches),
        "joined_remote_user_matches": len(remote_user_matches),
    }

def _get_room_shared_join():
    attr_name = "nisb_room_shared_join"
    errors: List[str] = []

    candidates: List[tuple[str, Optional[str]]] = []

    if __package__:
        candidates.extend(
            [
                ("..rooms_shared", __package__),
                ("..rooms_shared.room_tools_meta", __package__),
            ]
        )

    candidates.extend(
        [
            ("tools.rooms_shared", None),
            ("tools.rooms_shared.room_tools_meta", None),
        ]
    )

    for mod_name, package_name in candidates:
        try:
            mod = import_module(mod_name, package_name) if package_name else import_module(mod_name)
            fn = getattr(mod, attr_name, None)
            if callable(fn):
                return fn
            errors.append(f"{mod_name}: callable_not_found")
        except Exception as e:
            errors.append(f"{mod_name}: {e!r}")

    raise RuntimeError("room_shared_join_unavailable: " + " | ".join(errors))


def _join_result_ok(join_result: Any) -> bool:
    if not isinstance(join_result, dict):
        return False
    if bool(join_result.get("success")):
        return True
    return _safe_str(join_result.get("status")).lower() == "success"


def nisb_fed_add_peer(args: Dict[str, Any]) -> Dict[str, Any]:
    basepath = _get_basepath(args)
    _ensure_dir(_fed_root(basepath))

    peer_id = _safe_str(args.get("peer_id"))
    base_url = _safe_str(args.get("base_url")).rstrip("/")
    token = _safe_str(args.get("peer_token") or args.get("token"))
    enabled = bool(args.get("enabled", True))
    label = _safe_str(args.get("label"))

    if not peer_id or not base_url:
        return {"success": False, "message": "missing peer_id/base_url"}

    doc = _load_peers(basepath)
    peers: List[Dict[str, Any]] = [p for p in (doc.get("peers") or []) if isinstance(p, dict)]

    found: Optional[Dict[str, Any]] = None
    for peer in peers:
        if _safe_str(peer.get("peer_id")) == peer_id:
            found = peer
            break

    if found is None:
        found = {"peer_id": peer_id, "created_at": _utc_iso()}
        peers.append(found)

    found.update(
        {
            "peer_id": peer_id,
            "base_url": base_url,
            "token": token,
            "enabled": enabled,
            "label": label,
            "updated_at": _utc_iso(),
        }
    )

    doc["peers"] = peers
    _write_peers(basepath, doc)
    return {"success": True, "peer": found}


def nisb_fed_list_peers(args: Dict[str, Any]) -> Dict[str, Any]:
    basepath = _get_basepath(args)
    doc = _load_peers(basepath)

    peers = []
    for row in (doc.get("peers") or []):
        if not isinstance(row, dict):
            continue
        peer = dict(row)
        token = _safe_str(peer.get("token"))
        peer["token_present"] = bool(token)
        peer["token_preview"] = f"{token[:6]}...{token[-4:]}" if len(token) >= 12 else ("set" if token else "")
        peers.append(peer)

    peers.sort(key=lambda x: _safe_str(x.get("peer_id")))
    return {"success": True, "peers": peers, "updated_at": doc.get("updated_at")}


def nisb_fed_issue_room_invite(args: Dict[str, Any]) -> Dict[str, Any]:
    basepath = _get_basepath(args)
    _ensure_dir(_fed_root(basepath))

    room_id = _safe_str(args.get("room_id"))
    join_key = _safe_str(args.get("join_key"))
    target_peer_id = _safe_str(args.get("target_peer_id"))
    local_owner_user_id = _safe_str(args.get("local_owner_user_id") or args.get("user_id"))

    ttl_default_seconds = 86400
    ttl_max_seconds = 30 * 86400
    ttl_presets_seconds = {
        86400,
        3 * 86400,
        7 * 86400,
        30 * 86400,
    }

    expires_in_seconds = args.get("expires_in_seconds", ttl_default_seconds)

    try:
        expires_in_seconds = int(expires_in_seconds)
    except Exception:
        expires_in_seconds = ttl_default_seconds

    expires_in_seconds = max(300, min(ttl_max_seconds, expires_in_seconds))
    if expires_in_seconds not in ttl_presets_seconds:
        expires_in_seconds = ttl_default_seconds

    if not room_id or not join_key or not target_peer_id:
        return {"success": False, "message": "missing room_id/join_key/target_peer_id"}

    invite = {
        "invite_id": f"fedi_{secrets.token_hex(8)}",
        "invite_token": f"fedrt_{secrets.token_hex(16)}",
        "room_id": room_id,
        "join_key": join_key,
        "target_peer_id": target_peer_id,
        "local_owner_user_id": local_owner_user_id,
        "status": "active",
        "created_at": _utc_iso(),
        "expires_at": datetime.fromtimestamp(
            int(time.time()) + expires_in_seconds,
            timezone.utc,
        ).isoformat(),
        "expires_in_seconds": expires_in_seconds,
        "used_at": "",
        "used_by_remote_user_id": "",
    }

    doc = _load_room_invites(basepath)
    invites = [row for row in (doc.get("invites") or []) if isinstance(row, dict)]
    invites.append(invite)
    doc["invites"] = invites
    _write_room_invites(basepath, doc)

    return {"success": True, "invite": invite}


def nisb_fed_remote_room_join(args: Dict[str, Any]) -> Dict[str, Any]:
    basepath = _get_basepath(args)
    room_id = _safe_str(args.get("room_id"))
    invite_token = _safe_str(args.get("invite_token"))
    remote_peer_id = _safe_str(args.get("remote_peer_id"))
    remote_user_id = _safe_str(args.get("remote_user_id"))
    remote_label = _safe_str(args.get("remote_label"))

    if not room_id or not invite_token or not remote_user_id:
        return _error_result(
            message="missing room_id/invite_token/remote_user_id",
            error_code="bad_request",
            error_kind="request",
            user_message="缺少 room_id / invite_token / remote_user_id。",
        )

    doc = _load_room_invites(basepath)
    invites = [row for row in (doc.get("invites") or []) if isinstance(row, dict)]

    changed = False
    now = datetime.now(timezone.utc)

    def _persist_if_needed() -> None:
        nonlocal changed
        if changed:
            doc["invites"] = invites
            _write_room_invites(basepath, doc)
            changed = False

    def _refresh_expiry(row: Dict[str, Any]) -> None:
        nonlocal changed
        if _safe_str(row.get("status")) != "active":
            return
        expires_at = _safe_str(row.get("expires_at"))
        if not expires_at:
            return
        try:
            if datetime.fromisoformat(expires_at.replace("Z", "+00:00")) < now:
                row["status"] = "expired"
                changed = True
        except Exception:
            pass

    def _invite_state_error(row: Optional[Dict[str, Any]], *, mismatch: bool = False) -> Dict[str, Any]:
        item = row if isinstance(row, dict) else {}
        status = _safe_str(item.get("status")) or "active"
        target_peer_id = _safe_str(item.get("target_peer_id"))

        if mismatch:
            return _error_result(
                message="peer mismatch",
                error_code="peer_mismatch",
                error_kind="peer",
                user_message="invite 与当前 peer 不匹配，请核对 peer_id / target_peer_id。",
                room_id=room_id,
                remote_peer_id=remote_peer_id,
                target_peer_id=target_peer_id,
                invite_status=status,
            )

        if status == "expired":
            return _error_result(
                message="invite expired",
                error_code="invite_expired",
                error_kind="invite",
                user_message="invite 已过期，需要房主重新签发。",
                room_id=room_id,
                remote_peer_id=remote_peer_id,
                target_peer_id=target_peer_id,
            )

        if status == "used":
            return _error_result(
                message="invite used",
                error_code="invite_used",
                error_kind="invite",
                user_message="invite 已被使用，不可重复接受。",
                room_id=room_id,
                remote_peer_id=remote_peer_id,
                target_peer_id=target_peer_id,
                used_at=_safe_str(item.get("used_at")),
                used_by_remote_user_id=_safe_str(item.get("used_by_remote_user_id")),
            )

        if status == "revoked":
            return _error_result(
                message="invite revoked",
                error_code="invite_revoked",
                error_kind="invite",
                user_message="invite 已撤销，不可再接受。",
                room_id=room_id,
                remote_peer_id=remote_peer_id,
                target_peer_id=target_peer_id,
            )

        return _error_result(
            message="invite not active",
            error_code="invite_not_active",
            error_kind="invite",
            user_message="invite 当前不是 active 状态。",
            room_id=room_id,
            remote_peer_id=remote_peer_id,
            target_peer_id=target_peer_id,
        )

    token_room_candidates: List[Dict[str, Any]] = []
    exact_target: Optional[Dict[str, Any]] = None

    for row in invites:
        if (
            _safe_str(row.get("invite_token")) == invite_token
            and _safe_str(row.get("room_id")) == room_id
        ):
            _refresh_expiry(row)
            token_room_candidates.append(row)

            if (
                remote_peer_id
                and _safe_str(row.get("target_peer_id")) == remote_peer_id
            ):
                exact_target = row

    active_candidates = [
        row for row in token_room_candidates
        if _safe_str(row.get("status")) == "active"
    ]

    target: Optional[Dict[str, Any]] = exact_target
    match_mode = "exact_target_peer"

    if target is None:
        if remote_peer_id:
            if len(active_candidates) == 1:
                only = active_candidates[0]
                only_target_peer_id = _safe_str(only.get("target_peer_id"))
                if only_target_peer_id and only_target_peer_id != remote_peer_id:
                    _persist_if_needed()
                    return _invite_state_error(only, mismatch=True)
            elif len(active_candidates) > 1:
                _persist_if_needed()
                return _error_result(
                    message="invite ambiguous",
                    error_code="invite_ambiguous",
                    error_kind="invite",
                    user_message="存在多条可匹配 invite，请核对 peer_id / target_peer_id。",
                    room_id=room_id,
                    remote_peer_id=remote_peer_id,
                    matched_active_invites=len(active_candidates),
                )

        if not remote_peer_id:
            if len(active_candidates) == 1:
                target = active_candidates[0]
                match_mode = "unique_token_fallback"
            elif len(active_candidates) > 1:
                _persist_if_needed()
                return _error_result(
                    message="invite ambiguous",
                    error_code="invite_ambiguous",
                    error_kind="invite",
                    user_message="存在多条可匹配 invite，请核对 peer_id / target_peer_id。",
                    room_id=room_id,
                    remote_peer_id=remote_peer_id,
                    matched_active_invites=len(active_candidates),
                )

    if target is None:
        _persist_if_needed()

        if len(token_room_candidates) == 1:
            only = token_room_candidates[0]
            only_target_peer_id = _safe_str(only.get("target_peer_id"))
            if remote_peer_id and only_target_peer_id and only_target_peer_id != remote_peer_id:
                return _invite_state_error(only, mismatch=True)
            return _invite_state_error(only)

        if len(token_room_candidates) > 1:
            return _error_result(
                message="invite ambiguous",
                error_code="invite_ambiguous",
                error_kind="invite",
                user_message="存在多条可匹配 invite，请核对 peer_id / target_peer_id。",
                room_id=room_id,
                remote_peer_id=remote_peer_id,
                matched_invites=len(token_room_candidates),
            )

        return _error_result(
            message="invite not found",
            error_code="invite_not_found",
            error_kind="invite",
            user_message="invite 不存在，或当前 peer 与 invite 不匹配。",
            room_id=room_id,
            remote_peer_id=remote_peer_id,
        )

    if _safe_str(target.get("status")) != "active":
        _persist_if_needed()
        return _invite_state_error(target)

    resolved_federation_peer_id = remote_peer_id or _safe_str(target.get("target_peer_id"))
    if not resolved_federation_peer_id:
        return _error_result(
            message="peer mismatch",
            error_code="peer_mismatch",
            error_kind="peer",
            user_message="缺少 federation peer_id，无法建立 federated actor。",
            room_id=room_id,
            remote_peer_id=remote_peer_id,
            target_peer_id=_safe_str(target.get("target_peer_id")),
        )

    join_tool = _get_room_shared_join()
    join_result = join_tool(
        {
            "basepath": basepath,
            "room_id": room_id,
            "join_key": _safe_str(target.get("join_key")),
            "_federation_peer_id": resolved_federation_peer_id,
            "_federation_remote_user_id": remote_user_id,
            "_federation_remote_label": remote_label,
        }
    )

    if not _join_result_ok(join_result):
        structured = _structured_remote_failure(
            join_result if isinstance(join_result, dict) else {},
            fallback_message="room join failed",
            status_code=200,
            response_text="",
        )
        return {
            "success": False,
            "message": _safe_str((join_result or {}).get("message")) or "room join failed",
            **structured,
            "join_result": join_result,
            "match_mode": match_mode,
            "target_peer_id": _safe_str(target.get("target_peer_id")),
            "resolved_federation_peer_id": resolved_federation_peer_id,
        }

    target["status"] = "used"
    target["used_at"] = _utc_iso()
    target["used_by_remote_user_id"] = remote_user_id
    doc["invites"] = invites
    _write_room_invites(basepath, doc)

    owner_room_id = _safe_str(join_result.get("room_id") or room_id)
    local_owner_user_id = _safe_str(target.get("local_owner_user_id"))

    return {
        "success": True,
        "room_id": room_id,
        "owner_room_id": owner_room_id,
        "remote_peer_id": resolved_federation_peer_id,
        "remote_user_id": remote_user_id,
        "local_owner_user_id": local_owner_user_id,
        "owner_user_id": local_owner_user_id,
        "join_result": join_result,
        "room_member_role": "member",
        "effective_execution_scope": "room_shared",
        "match_mode": match_mode,
        "target_peer_id": _safe_str(target.get("target_peer_id")),
        "resolved_federation_peer_id": resolved_federation_peer_id,
        "title": _safe_str(join_result.get("title")),
    }


def nisb_fed_accept_room_invite(args: Dict[str, Any]) -> Dict[str, Any]:
    basepath = _get_basepath(args)
    peer_id = _safe_str(args.get("peer_id"))
    room_id = _safe_str(args.get("room_id"))
    invite_token = _safe_str(args.get("invite_token"))

    requested_remote_user_id = _safe_str(args.get("remote_user_id") or args.get("user_id"))
    ctx_remote_user_id = _safe_str(uid_from_ctx_or_basepath(basepath, args))
    remote_user_id = ctx_remote_user_id or requested_remote_user_id

    remote_label = _safe_str(args.get("remote_label"))

    target_peer_id = _safe_str(
        args.get("target_peer_id")
        or args.get("owner_target_peer_id")
        or args.get("invite_target_peer_id")
        or args.get("remote_peer_id")
    )

    if not peer_id or not room_id or not invite_token or not remote_user_id:
        return _error_result(
            message="missing peer_id/room_id/invite_token/remote_user_id",
            error_code="bad_request",
            error_kind="request",
            user_message="缺少 peer_id / room_id / invite_token / remote_user_id。",
        )

    peer = _find_peer(basepath, peer_id)
    if not peer or not peer.get("enabled", True):
        return _error_result(
            message="peer not found or disabled",
            error_code="peer_not_found",
            error_kind="peer",
            user_message="peer 不存在或已禁用。",
        )

    base_url = _safe_str(peer.get("base_url")).rstrip("/")
    token = _safe_str(peer.get("token"))

    remote_args = {
        "room_id": room_id,
        "invite_token": invite_token,
        "remote_user_id": remote_user_id,
        "remote_label": remote_label,
    }

    if target_peer_id:
        remote_args["remote_peer_id"] = target_peer_id

    remote = _remote_mcp_call(
        base_url=base_url,
        token=token,
        tool="nisb_fed_remote_room_join",
        arguments=remote_args,
        timeout_sec=10.0,
    )

    if not remote.get("success"):
        return {
            "success": False,
            "message": remote.get("message") or "remote room join request failed",
            "error_code": remote.get("error_code") or "remote_error",
            "error_kind": remote.get("error_kind") or "remote_error",
            "user_message": remote.get("user_message") or remote.get("message") or "远端调用失败。",
            "retryable": bool(remote.get("retryable")),
            "peer_id": peer_id,
            "target_peer_id": target_peer_id,
            "room_id": room_id,
            "remote_user_id": remote_user_id,
            "requested_remote_user_id": requested_remote_user_id,
            "upstream": remote,
        }

    result = remote.get("response_json") if isinstance(remote.get("response_json"), dict) else {}
    if not _join_result_ok(result):
        structured = _structured_remote_failure(
            result,
            fallback_message="remote room join failed",
            status_code=int(remote.get("status_code") or 200),
            response_text=_safe_str(remote.get("response_text_preview")),
        )
        return {
            "success": False,
            "message": _safe_str(result.get("message")) or "remote room join failed",
            **structured,
            "peer_id": peer_id,
            "target_peer_id": target_peer_id,
            "room_id": room_id,
            "remote_user_id": remote_user_id,
            "requested_remote_user_id": requested_remote_user_id,
            "result": result,
            "upstream": remote,
        }

    join_result = result.get("join_result") if isinstance(result.get("join_result"), dict) else {}
    owner_room_id = _safe_str(
        result.get("owner_room_id")
        or join_result.get("room_id")
        or result.get("room_id")
        or room_id
    )

    resolved_target_peer_id = _safe_str(
        result.get("target_peer_id")
        or join_result.get("target_peer_id")
        or target_peer_id
    )

    local_owner_user_id = _safe_str(
        result.get("local_owner_user_id")
        or join_result.get("local_owner_user_id")
        or result.get("owner_user_id")
        or join_result.get("owner_user_id")
    )

    joined_room = _upsert_joined_room(
        basepath,
        peer_id=peer_id,
        room_id=room_id,
        owner_room_id=owner_room_id,
        remote_user_id=remote_user_id,
        remote_label=remote_label,
        title=_safe_str(
            result.get("title")
            or join_result.get("title")
            or ""
        ),
        enabled=True,
        target_peer_id=resolved_target_peer_id,
        local_owner_user_id=local_owner_user_id,
        owner_user_id=local_owner_user_id,
    )

    return {
        "success": True,
        "peer_id": peer_id,
        "target_peer_id": resolved_target_peer_id,
        "room_id": room_id,
        "owner_room_id": owner_room_id,
        "remote_user_id": remote_user_id,
        "requested_remote_user_id": requested_remote_user_id,
        "local_owner_user_id": local_owner_user_id,
        "owner_user_id": local_owner_user_id,
        "status_code": remote.get("status_code"),
        "url": remote.get("url"),
        "result": result,
        "joined_room": joined_room,
    }


def nisb_fed_call(args: Dict[str, Any]) -> Dict[str, Any]:
    basepath = _get_basepath(args)
    peer_id = _safe_str(args.get("peer_id"))
    tool = _safe_str(args.get("tool"))
    tool_args = args.get("tool_args") if isinstance(args.get("tool_args"), dict) else {}

    timeout_ms_requested = args.get("timeout_ms", 8000)
    try:
        timeout_ms_requested = int(timeout_ms_requested)
    except Exception:
        timeout_ms_requested = 8000

    if tool in {"nisb_room_shared_post", "nisb_room_shared_provider_post"}:
        timeout_profile = "room_shared_runtime"
        timeout_ms_effective = max(3000, min(180000, timeout_ms_requested))
    else:
        timeout_profile = "default"
        timeout_ms_effective = max(1000, min(20000, timeout_ms_requested))

    if not peer_id or not tool:
        return _error_result(
            message="missing peer_id/tool",
            error_code="bad_request",
            error_kind="request",
            user_message="缺少 peer_id / tool。",
            timeout_ms_requested=timeout_ms_requested,
            timeout_ms_effective=timeout_ms_effective,
            timeout_profile=timeout_profile,
        )

    peer = _find_peer(basepath, peer_id)
    if not peer or not peer.get("enabled", True):
        return _error_result(
            message="peer not found or disabled",
            error_code="peer_not_found",
            error_kind="peer",
            user_message="peer 不存在或已禁用。",
            timeout_ms_requested=timeout_ms_requested,
            timeout_ms_effective=timeout_ms_effective,
            timeout_profile=timeout_profile,
        )

    base_url = _safe_str(peer.get("base_url")).rstrip("/")
    token = _safe_str(peer.get("token"))

    remote = _remote_mcp_call(
        base_url=base_url,
        token=token,
        tool=tool,
        arguments=tool_args,
        timeout_sec=timeout_ms_effective / 1000.0,
    )

    common = {
        "peer_id": peer_id,
        "tool": tool,
        "base_url": base_url,
        "timeout_profile": timeout_profile,
        "timeout_ms_requested": timeout_ms_requested,
        "timeout_ms_effective": timeout_ms_effective,
        "timeout_sec_effective": timeout_ms_effective / 1000.0,
        "timeout_connect_sec": remote.get("timeout_connect_sec"),
        "timeout_read_sec": remote.get("timeout_read_sec"),
        "timeout_write_sec": remote.get("timeout_write_sec"),
        "timeout_pool_sec": remote.get("timeout_pool_sec"),
        "timeout_stage": remote.get("timeout_stage"),
        "remote_execution_may_have_completed": remote.get("remote_execution_may_have_completed"),
        "timeout_sec": remote.get("timeout_sec"),
        "status_code": remote.get("status_code"),
        "url": remote.get("url"),
        "exception_type": remote.get("exception_type"),
    }

    if not remote.get("success"):
        return {
            "success": False,
            "message": remote.get("message") or "remote tool call failed",
            "error_code": remote.get("error_code") or "remote_error",
            "error_kind": remote.get("error_kind") or "remote_error",
            "user_message": remote.get("user_message") or remote.get("message") or "远端调用失败。",
            "retryable": bool(remote.get("retryable")),
            **common,
            "upstream": remote,
        }

    result = remote.get("response_json") if isinstance(remote.get("response_json"), dict) else {}
    if _is_error_like_payload(result):
        structured = _structured_remote_failure(
            result,
            fallback_message="remote tool call failed",
            status_code=int(remote.get("status_code") or 200),
            response_text=_safe_str(remote.get("response_text_preview")),
        )
        return {
            "success": False,
            "message": _safe_str(result.get("message")) or "remote tool call failed",
            **structured,
            **common,
            "result": result,
            "upstream": remote,
        }

    return {
        "success": True,
        **common,
        "result": result,
    }

def nisb_fed_list_joined_rooms(args: Dict[str, Any]) -> Dict[str, Any]:
    basepath = _get_basepath(args)
    doc = _load_joined_rooms(basepath)
    rooms = [row for row in (doc.get("rooms") or []) if isinstance(row, dict)]

    rooms.sort(
        key=lambda x: (
            _safe_str(x.get("last_entered_at")) or _safe_str(x.get("joined_at")),
            _safe_str(x.get("room_id")),
        ),
        reverse=True,
    )

    return {
        "success": True,
        "rooms": rooms,
        "updated_at": doc.get("updated_at"),
    }


def nisb_fed_peer_health_check(args: Dict[str, Any]) -> Dict[str, Any]:
    basepath = _get_basepath(args)
    peer_id = _safe_str(args.get("peer_id"))
    timeout_ms = args.get("timeout_ms", 5000)

    try:
        timeout_ms = int(timeout_ms)
    except Exception:
        timeout_ms = 5000
    timeout_ms = max(1000, min(15000, timeout_ms))

    if not peer_id:
        return _error_result(
            message="missing peer_id",
            error_code="bad_request",
            error_kind="request",
            user_message="缺少 peer_id。",
        )

    peer = _find_peer(basepath, peer_id)
    if not peer or not peer.get("enabled", True):
        return _error_result(
            message="peer not found or disabled",
            error_code="peer_not_found",
            error_kind="peer",
            user_message="peer 不存在或已禁用。",
        )

    base_url = _safe_str(peer.get("base_url")).rstrip("/")
    token = _safe_str(peer.get("token"))

    remote = _remote_mcp_call(
        base_url=base_url,
        token=token,
        tool="nisb_fed_list_peers",
        arguments={},
        timeout_sec=timeout_ms / 1000.0,
    )

    if not remote.get("success"):
        return {
            "success": False,
            "status": "error",
            "health_status": "error",
            "peer_id": peer_id,
            "base_url": base_url,
            "checked_tool": "nisb_fed_list_peers",
            "checked_at": _utc_iso(),
            "message": remote.get("message") or "peer health check failed",
            "error_code": remote.get("error_code") or "remote_error",
            "error_kind": remote.get("error_kind") or "remote_error",
            "user_message": remote.get("user_message") or remote.get("message") or "远端调用失败。",
            "retryable": bool(remote.get("retryable")),
            "upstream": remote,
        }

    result = remote.get("response_json") if isinstance(remote.get("response_json"), dict) else {}
    if isinstance(result, dict) and result.get("success") is False:
        norm = _normalize_remote_error(
            status_code=int(remote.get("status_code") or 200),
            response_json=result,
            response_text=_safe_str(remote.get("response_text_preview")),
            message=_safe_str(result.get("message")) or "peer health check failed",
        )
        return {
            "success": False,
            "status": "error",
            "health_status": "error",
            "peer_id": peer_id,
            "base_url": base_url,
            "checked_tool": "nisb_fed_list_peers",
            "checked_at": _utc_iso(),
            "message": _safe_str(result.get("message")) or "peer health check failed",
            **norm,
            "result": result,
            "upstream": remote,
        }

    return {
        "success": True,
        "status": "success",
        "health_status": "ok",
        "peer_id": peer_id,
        "base_url": base_url,
        "checked_tool": "nisb_fed_list_peers",
        "checked_at": _utc_iso(),
        "auth_mode": remote.get("auth_mode"),
        "status_code": remote.get("status_code"),
        "url": remote.get("url"),
    }


def nisb_fed_list_room_invites(args: Dict[str, Any]) -> Dict[str, Any]:
    basepath = _get_basepath(args)
    room_id = _safe_str(args.get("room_id"))
    target_peer_id = _safe_str(args.get("target_peer_id"))

    doc = _load_room_invites(basepath)
    invites = [row for row in (doc.get("invites") or []) if isinstance(row, dict)]

    changed = False
    now = datetime.now(timezone.utc)

    normalized: List[Dict[str, Any]] = []
    for row in invites:
        item = dict(row)

        expires_at = _safe_str(item.get("expires_at"))
        status = _safe_str(item.get("status")) or "active"

        if status == "active" and expires_at:
            try:
                expires_dt = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
                if expires_dt < now:
                    item["status"] = "expired"
                    status = "expired"
                    changed = True
            except Exception:
                pass

        if room_id and _safe_str(item.get("room_id")) != room_id:
            continue
        if target_peer_id and _safe_str(item.get("target_peer_id")) != target_peer_id:
            continue

        normalized.append(item)

    if changed:
        doc["invites"] = [
            next(
                (updated for updated in normalized if _safe_str(updated.get("invite_id")) == _safe_str(row.get("invite_id"))),
                row,
            )
            if isinstance(row, dict) else row
            for row in invites
        ]
        _write_room_invites(basepath, doc)

    normalized.sort(
        key=lambda x: (
            _safe_str(x.get("created_at")),
            _safe_str(x.get("invite_id")),
        ),
        reverse=True,
    )

    return {
        "success": True,
        "room_id": room_id,
        "target_peer_id": target_peer_id,
        "invites": normalized,
        "updated_at": doc.get("updated_at"),
    }


def nisb_fed_revoke_room_invite(args: Dict[str, Any]) -> Dict[str, Any]:
    basepath = _get_basepath(args)
    room_id = _safe_str(args.get("room_id"))
    invite_id = _safe_str(args.get("invite_id"))

    if not room_id or not invite_id:
        return {
            "success": False,
            "message": "missing room_id/invite_id",
        }

    doc = _load_room_invites(basepath)
    invites = [row for row in (doc.get("invites") or []) if isinstance(row, dict)]

    target: Optional[Dict[str, Any]] = None
    for row in invites:
        if (
            _safe_str(row.get("room_id")) == room_id
            and _safe_str(row.get("invite_id")) == invite_id
        ):
            target = row
            break

    if target is None:
        return {
            "success": False,
            "message": "invite not found",
            "room_id": room_id,
            "invite_id": invite_id,
        }

    status = _safe_str(target.get("status")) or "active"

    if status == "revoked":
        return {
            "success": True,
            "room_id": room_id,
            "invite": target,
            "already_revoked": True,
        }

    expires_at = _safe_str(target.get("expires_at"))
    if status == "active" and expires_at:
        try:
            if datetime.fromisoformat(expires_at.replace("Z", "+00:00")) < datetime.now(timezone.utc):
                target["status"] = "expired"
                doc["invites"] = invites
                _write_room_invites(basepath, doc)
                return {
                    "success": False,
                    "message": "invite expired",
                    "room_id": room_id,
                    "invite": target,
                }
        except Exception:
            pass

    if _safe_str(target.get("status")) != "active":
        return {
            "success": False,
            "message": "invite not active",
            "room_id": room_id,
            "invite": target,
        }

    target["status"] = "revoked"
    doc["invites"] = invites
    _write_room_invites(basepath, doc)

    return {
        "success": True,
        "room_id": room_id,
        "invite": target,
    }


def nisb_fed_extend_room_invite(args: Dict[str, Any]) -> Dict[str, Any]:
    basepath = _get_basepath(args)
    room_id = _safe_str(args.get("room_id"))
    invite_id = _safe_str(args.get("invite_id"))
    extend_seconds = args.get("extend_seconds", 0)

    if not room_id or not invite_id:
        return {
            "success": False,
            "message": "missing room_id/invite_id",
        }

    try:
        extend_seconds = int(extend_seconds)
    except Exception:
        extend_seconds = 0

    if extend_seconds not in {86400, 7 * 86400}:
        return {
            "success": False,
            "message": "invalid extend_seconds",
            "room_id": room_id,
            "invite_id": invite_id,
            "allowed_extend_seconds": [86400, 7 * 86400],
        }

    doc = _load_room_invites(basepath)
    invites = [row for row in (doc.get("invites") or []) if isinstance(row, dict)]

    target: Optional[Dict[str, Any]] = None
    for row in invites:
        if (
            _safe_str(row.get("room_id")) == room_id
            and _safe_str(row.get("invite_id")) == invite_id
        ):
            target = row
            break

    if target is None:
        return {
            "success": False,
            "message": "invite not found",
            "room_id": room_id,
            "invite_id": invite_id,
        }

    now = datetime.now(timezone.utc)
    status = _safe_str(target.get("status")) or "active"
    expires_at = _safe_str(target.get("expires_at"))

    if status == "active" and expires_at:
        try:
            expires_dt = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
            if expires_dt < now:
                target["status"] = "expired"
                doc["invites"] = invites
                _write_room_invites(basepath, doc)
                return {
                    "success": False,
                    "message": "invite expired",
                    "room_id": room_id,
                    "invite": target,
                }
        except Exception:
            pass

    status = _safe_str(target.get("status")) or "active"

    if status == "used":
        return {
            "success": False,
            "message": "invite used",
            "room_id": room_id,
            "invite": target,
        }

    if status == "revoked":
        return {
            "success": False,
            "message": "invite revoked",
            "room_id": room_id,
            "invite": target,
        }

    if status == "expired":
        return {
            "success": False,
            "message": "invite expired",
            "room_id": room_id,
            "invite": target,
        }

    if status != "active":
        return {
            "success": False,
            "message": "invite not active",
            "room_id": room_id,
            "invite": target,
        }

    try:
        base_expires_dt = datetime.fromisoformat(expires_at.replace("Z", "+00:00")) if expires_at else now
    except Exception:
        base_expires_dt = now

    new_expires_dt = datetime.fromtimestamp(
        int(base_expires_dt.timestamp()) + extend_seconds,
        timezone.utc,
    )

    try:
        extend_count = int(target.get("extend_count") or 0)
    except Exception:
        extend_count = 0

    target["expires_at"] = new_expires_dt.isoformat()
    target["expires_in_seconds"] = max(0, int(new_expires_dt.timestamp() - now.timestamp()))
    target["extended_at"] = _utc_iso()
    target["extend_count"] = extend_count + 1

    doc["invites"] = invites
    _write_room_invites(basepath, doc)

    return {
        "success": True,
        "room_id": room_id,
        "invite": target,
        "extend_seconds": extend_seconds,
    }


__all__ = [
    "nisb_fed_accept_room_invite",
    "nisb_fed_add_peer",
    "nisb_fed_call",
    "nisb_fed_extend_room_invite",
    "nisb_fed_issue_room_invite",
    "nisb_fed_list_joined_rooms",
    "nisb_fed_list_peers",
    "nisb_fed_list_room_invites",
    "nisb_fed_peer_health_check",
    "nisb_fed_remote_room_join",
    "nisb_fed_revoke_room_invite",
]

