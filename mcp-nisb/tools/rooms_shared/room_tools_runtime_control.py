from __future__ import annotations

from typing import Any, Dict, List, Optional

from .room_contracts import as_bool, ensure_request_id, new_id, require_safe_id, utc_iso
from .room_helpers import (
    _append_aborted_event,
    _build_run_id,
    _get_active_role_objects,
    _set_room_state_patch,
)
from .room_orchestrator import (
    _run_sequential_orchestration,
    _run_supervisor_orchestration,
)
from .room_packet_builder import _normalize_mode_used
from .room_runtime_reader import _same_event
from .room_state_normalizer import (
    _normalize_room_state_for_output,
    _safe_dict,
    _safe_list,
    _safe_str,
)
from .room_store import (
    append_room_event,
    ensure_room_exists,
    get_basepath,
    is_participant,
    load_room_events,
    load_state_doc,
    touch_room_updated_at,
    uid_from_ctx_or_basepath,
)
from .room_tool_common import (
    _build_tool_result_item,
    _formal_envelope,
    _payload_of_event,
    _permission_denied,
)
from .room_tools_runtime_current import _get_runtime_control_snapshot

_DEFAULT_RUNTIME_REFRESH_HINT = "dispatch_room_refresh -> recent events -> loadRoomMessages"


def _safe_non_negative_int(value: Any, fallback: int = 0) -> int:
    try:
        return max(0, int(value))
    except Exception:
        try:
            return max(0, int(fallback))
        except Exception:
            return 0


def _next_runtime_control_version(state: Dict[str, Any]) -> int:
    row = _safe_dict(state)
    return _safe_non_negative_int(
        row.get("runtime_control_version"),
        _safe_non_negative_int(row.get("runtime_version"), 0),
    ) + 1


def _runtime_command_error(
    *,
    rid: str,
    room_id: str,
    state: Dict[str, Any],
    command: str,
    error_code: str,
    message: str,
    run_id: str = "",
    extra: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    payload = {
        "room_id": room_id,
        "run_id": run_id,
        "command": command,
        "status": "error",
        "error_code": error_code,
        "message": message,
        "refresh_hint": _DEFAULT_RUNTIME_REFRESH_HINT,
    }
    if extra:
        payload.update(extra)

    return _formal_envelope(
        request_id=rid,
        conv_id=room_id,
        mcp_overrides=state.get("mcp_overrides"),
        response=message,
        status="error",
        message=message,
        tool_calls=[],
        tool_results=[_build_tool_result_item("room_runtime_command", **payload)],
    )


def _resolve_effective_run_id(
    *,
    state: Dict[str, Any],
    requested_run_id: str,
) -> str:
    state_run_id = _safe_str(state.get("current_run_id"))
    if requested_run_id:
        return requested_run_id
    return state_run_id


def _resolve_resume_checkpoint_ref(
    *,
    args: Dict[str, Any],
    state: Dict[str, Any],
) -> str:
    explicit_ref = _safe_str(args.get("resume_checkpoint_ref"))
    if explicit_ref:
        return explicit_ref

    candidates = [
        state.get("resume_checkpoint_ref"),
        state.get("resumable_checkpoint_ref"),
        state.get("checkpoint_event_id"),
        state.get("last_checkpoint_event_id"),
        state.get("final_event_id"),
        state.get("current_trigger_event_id"),
    ]
    for value in candidates:
        resolved = _safe_str(value)
        if resolved:
            return resolved
    return ""


def _append_runtime_command_event(
    *,
    room_id: str,
    rid: str,
    run_id: str,
    command: str,
    payload: Dict[str, Any],
) -> Dict[str, Any]:
    evt = {
        "id": new_id("evt"),
        "ts": utc_iso(),
        "type": "room.runtime.command",
        "room_id": room_id,
        "request_id": rid,
        "run_id": run_id,
        "payload": {
            "command": command,
            **_safe_dict(payload),
        },
    }
    append_room_event(room_id, evt)
    touch_room_updated_at(room_id)
    return evt


def _find_room_event_by_id(
    *,
    room_id: str,
    event_id: str,
) -> Optional[Dict[str, Any]]:
    target = _safe_str(event_id)
    if not target:
        return None

    rows = _safe_list(load_room_events(room_id))
    for row in rows:
        if not isinstance(row, dict):
            continue
        if _safe_str(row.get("id")) == target:
            return row
    return None


def _find_latest_user_message_before_event(
    *,
    room_id: str,
    before_event_id: str = "",
) -> Optional[Dict[str, Any]]:
    rows = _safe_list(load_room_events(room_id))
    target = _safe_str(before_event_id)

    cutoff = len(rows)
    if target:
        for idx, row in enumerate(rows):
            if not isinstance(row, dict):
                continue
            if _safe_str(row.get("id")) == target:
                cutoff = idx
                break

    for row in reversed(rows[:cutoff]):
        if not isinstance(row, dict):
            continue
        if _safe_str(row.get("type")) != "room.message":
            continue
        payload = _payload_of_event(row)
        if _safe_str(payload.get("sender_type")).lower() != "user":
            continue
        if _safe_str(payload.get("content")):
            return row
    return None


def _resolve_resume_launch_context(
    *,
    room_id: str,
    args: Dict[str, Any],
    state: Dict[str, Any],
    resume_checkpoint_ref: str,
    resumed_from_event_id: str,
) -> Dict[str, Any]:
    source_evt = (
        _find_room_event_by_id(room_id=room_id, event_id=resume_checkpoint_ref)
        or _find_room_event_by_id(room_id=room_id, event_id=resumed_from_event_id)
    )
    source_payload = _payload_of_event(source_evt or {})

    source_trigger_event_id = _safe_str((source_evt or {}).get("trigger_event_id"))
    source_trigger_evt = (
        _find_room_event_by_id(room_id=room_id, event_id=source_trigger_event_id)
        if source_trigger_event_id
        else None
    )
    source_trigger_payload = _payload_of_event(source_trigger_evt or {})

    fallback_user_evt = _find_latest_user_message_before_event(
        room_id=room_id,
        before_event_id=_safe_str((source_evt or {}).get("id")),
    )
    fallback_user_payload = _payload_of_event(fallback_user_evt or {})

    question = _safe_str(
        args.get("question")
        or args.get("content")
        or source_payload.get("question")
        or source_trigger_payload.get("content")
        or fallback_user_payload.get("content")
    )

    mode_used = _normalize_mode_used(
        args.get("mode_used")
        or args.get("rag_mode")
        or source_payload.get("mode_used")
        or source_trigger_payload.get("mode_used")
        or state.get("mode_used")
        or "off"
    )

    model_name = _safe_str(
        args.get("model")
        or source_payload.get("model")
        or state.get("supervisor_model")
        or "gpt-4o-mini",
        "gpt-4o-mini",
    ) or "gpt-4o-mini"

    reply_mode = _safe_str(state.get("reply_mode"), "manual") or "manual"
    active_role_objs = _get_active_role_objects(room_id, state)

    return {
        "question": question,
        "mode_used": mode_used,
        "model_name": model_name,
        "reply_mode": reply_mode,
        "active_role_objs": active_role_objs,
        "source_event_id": _safe_str((source_evt or {}).get("id")),
        "source_trigger_event_id": source_trigger_event_id,
        "source_user_event_id": _safe_str((fallback_user_evt or {}).get("id")),
    }


def _find_last_generated_message_event(
    *,
    room_id: str,
    run_id: str,
    trigger_event_id: str = "",
) -> Optional[Dict[str, Any]]:
    rows = load_room_events(room_id)
    matched: List[Dict[str, Any]] = []

    for row in rows:
        if not isinstance(row, dict):
            continue
        if str(row.get("type") or "").strip() != "room.message":
            continue
        if _safe_str(row.get("run_id")) != _safe_str(run_id):
            continue
        if trigger_event_id and _safe_str(row.get("trigger_event_id")) != _safe_str(trigger_event_id):
            continue

        payload = _payload_of_event(row)
        if _safe_str(payload.get("sender_type")) == "user":
            continue
        matched.append(row)

    matched.sort(key=lambda x: (str(x.get("ts") or ""), str(x.get("id") or "")))
    return matched[-1] if matched else None


def _extract_runtime_auth_snapshot(
    *,
    uid: str,
    meta: Dict[str, Any],
    state: Dict[str, Any],
    args: Dict[str, Any],
) -> Dict[str, Any]:
    room_meta = _safe_dict(meta)
    raw_state = _safe_dict(state)
    room_meta_meta = _safe_dict(room_meta.get("meta") or room_meta.get("metadata"))

    actor_user_id = _safe_str(args.get("actor_user_id") or uid)
    room_owner_user_id = _safe_str(
        room_meta.get("owner_user_id")
        or raw_state.get("owner_user_id")
        or room_meta_meta.get("owner_user_id")
        or raw_state.get("room_owner_user_id")
    )

    shared_role_ids: List[str] = []
    raw_shared_role_ids = (
        raw_state.get("shared_role_ids")
        if isinstance(raw_state.get("shared_role_ids"), list)
        else room_meta.get("shared_role_ids")
        if isinstance(room_meta.get("shared_role_ids"), list)
        else room_meta_meta.get("shared_role_ids")
    )
    if isinstance(raw_shared_role_ids, list):
        seen = set()
        for item in raw_shared_role_ids:
            value = _safe_str(item)
            if not value or value in seen:
                continue
            seen.add(value)
            shared_role_ids.append(value)

    if "shared_supervisor_enabled" in raw_state:
        shared_supervisor_enabled = as_bool(raw_state.get("shared_supervisor_enabled"), False)
    elif "shared_supervisor_enabled" in room_meta:
        shared_supervisor_enabled = as_bool(room_meta.get("shared_supervisor_enabled"), False)
    else:
        shared_supervisor_enabled = as_bool(room_meta_meta.get("shared_supervisor_enabled"), False)

    actor_is_room_owner = bool(actor_user_id) and bool(room_owner_user_id) and actor_user_id == room_owner_user_id

    return {
        "actor_user_id": actor_user_id,
        "room_owner_user_id": room_owner_user_id,
        "actor_is_room_owner": actor_is_room_owner,
        "shared_role_ids_snapshot": shared_role_ids,
        "shared_supervisor_enabled_snapshot": bool(shared_supervisor_enabled),
        "effective_execution_scope": "owner_private" if actor_is_room_owner else "room_shared",
    }


def _inject_runtime_auth_snapshot(
    request_args: Dict[str, Any],
    snapshot: Dict[str, Any],
) -> Dict[str, Any]:
    out = dict(request_args or {})
    snap = _safe_dict(snapshot)

    actor_user_id = _safe_str(snap.get("actor_user_id"))

    out["actor_user_id"] = actor_user_id
    out["room_owner_user_id"] = _safe_str(snap.get("room_owner_user_id"))
    out["actor_is_room_owner"] = as_bool(snap.get("actor_is_room_owner"), False)
    out["is_owner_actor"] = as_bool(snap.get("actor_is_room_owner"), False)
    out["shared_role_ids_snapshot"] = _safe_list(snap.get("shared_role_ids_snapshot"))
    out["shared_supervisor_enabled_snapshot"] = as_bool(snap.get("shared_supervisor_enabled_snapshot"), False)
    out["effective_execution_scope"] = _safe_str(snap.get("effective_execution_scope"))

    if actor_user_id:
        out["user_id"] = actor_user_id
        out["uid"] = actor_user_id

    return out


def _extract_runtime_skip_rows(value: Any) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []

    def _append_if_skip(item: Any) -> None:
        row = _safe_dict(item)
        row_type = _safe_str(row.get("type"))
        if row_type in {"room.runtime_skipped", "room_execution_denied"}:
            rows.append(row)

    if isinstance(value, dict):
        _append_if_skip(value)
        for row in _safe_list(value.get("tool_results")):
            _append_if_skip(row)
        return rows

    if isinstance(value, (list, tuple)):
        for row in value:
            if isinstance(row, dict):
                _append_if_skip(row)
                for nested in _safe_list(row.get("tool_results")):
                    _append_if_skip(nested)
        return rows

    return rows


def _is_runtime_skip_result(value: Any) -> bool:
    return len(_extract_runtime_skip_rows(value)) > 0


def _mark_runtime_run_failed(*, room_id: str, run_id: str, rid: str) -> None:
    _set_room_state_patch(
        room_id,
        {
            "current_run_id": run_id,
            "current_request_id": rid,
            "current_run_status": "error",
            "runtime_control_run_id": run_id,
            "runtime_state_hint": "failed",
            "runtime_phase_hint": "idle",
            "current_delegate_role_id": "",
            "current_delegate_role_name": "",
            "current_delegate_index": 0,
            "current_delegate_total": 0,
            "last_run_finished_at": utc_iso(),
            "runtime_control_version": _next_runtime_control_version(load_state_doc(room_id)),
        },
    )


def _mark_runtime_run_skipped(
    *,
    room_id: str,
    run_id: str,
    rid: str,
    reason_code: str,
) -> None:
    _set_room_state_patch(
        room_id,
        {
            "current_run_id": run_id,
            "current_request_id": rid,
            "current_run_status": "skipped",
            "runtime_control_run_id": run_id,
            "runtime_state_hint": "idle",
            "runtime_phase_hint": "idle",
            "current_delegate_role_id": "",
            "current_delegate_role_name": "",
            "current_delegate_index": 0,
            "current_delegate_total": 0,
            "last_run_finished_at": utc_iso(),
            "last_runtime_skip_reason": reason_code,
            "runtime_control_version": _next_runtime_control_version(load_state_doc(room_id)),
        },
    )


def _clear_runtime_delegate_fields(*, room_id: str) -> None:
    _set_room_state_patch(
        room_id,
        {
            "current_delegate_role_id": "",
            "current_delegate_role_name": "",
            "current_delegate_index": 0,
            "current_delegate_total": 0,
        },
    )


def _finalize_runtime_dispatch(*, room_id: str, run_id: str, rid: str) -> None:
    state_after = _safe_dict(load_state_doc(room_id))
    if _safe_str(state_after.get("current_run_id")) != _safe_str(run_id):
        return

    current_status = _safe_str(state_after.get("current_run_status")).lower()
    if current_status == "running":
        _mark_runtime_run_failed(room_id=room_id, run_id=run_id, rid=rid)
    elif current_status in {"success", "error", "paused", "interrupted", "skipped"}:
        _clear_runtime_delegate_fields(room_id=room_id)
    elif current_status:
        _clear_runtime_delegate_fields(room_id=room_id)


def _start_room_runtime_run(
    *,
    room_id: str,
    rid: str,
    raw_state: Dict[str, Any],
    reply_mode: str,
    active_role_objs: List[Dict[str, Any]],
    model_name: str,
    trigger_event_id: str,
    request_args: Dict[str, Any],
) -> Dict[str, Any]:
    run_id = _build_run_id()
    role_ids = [
        str(r.get("role_id") or "").strip()
        for r in active_role_objs
        if str(r.get("role_id") or "").strip()
    ]
    phase = "supervisor" if reply_mode == "supervisor" else "worker"

    patch = {
        "current_run_id": run_id,
        "current_request_id": rid,
        "current_run_status": "running",
        "current_run_roles": role_ids,
        "current_trigger_event_id": trigger_event_id,
        "current_delegate_role_id": "",
        "current_delegate_role_name": "",
        "current_delegate_index": 0,
        "current_delegate_total": len(role_ids),
        "pause_requested": False,
        "pause_reason": "",
        "pause_requested_at": "",
        "paused_at": "",
        "pause_effective_at": "",
        "interruption_reason": "",
        "resume_from_checkpoint": False,
        "resume_checkpoint_ref": "",
        "resume_ready": False,
        "resume_token": "",
        "resume_reason": "",
        "error_blocking_resume": False,
        "resumed_from_run_id": "",
        "resumed_from_event_id": "",
        "resumed_from_stage": "",
        "runtime_control_run_id": run_id,
        "runtime_state_hint": "running",
        "runtime_phase_hint": phase,
        "runtime_control_version": _next_runtime_control_version(raw_state),
    }
    _set_room_state_patch(room_id, patch)

    next_snapshot = _get_runtime_control_snapshot(
        room_id=room_id,
        state=_safe_dict(load_state_doc(room_id)),
        request_row={
            "room_id": room_id,
            "current_run_id": run_id,
            "current_run_status": "running",
            "last_supervisor_phase": phase,
        },
    )

    next_args = dict(request_args or {})
    next_args["current_run_id"] = run_id
    next_args["current_run_status"] = "running"
    next_args["current_trigger_event_id"] = trigger_event_id
    next_args["trigger_event_id"] = trigger_event_id

    runtime_run_result = _build_tool_result_item(
        "room_runtime_run",
        room_id=room_id,
        run_id=run_id,
        request_id=rid,
        reply_mode=reply_mode,
        status="running",
        role_ids=role_ids,
        runtime_model=model_name,
        runtime_control_snapshot=next_snapshot,
    )

    return {
        "run_id": run_id,
        "runtime_control_snapshot": next_snapshot,
        "runtime_run_result": runtime_run_result,
        "request_args": next_args,
    }


def nisb_room_runtime_stop_current(args: Dict[str, Any]) -> Dict[str, Any]:
    basepath = get_basepath(args)
    uid = uid_from_ctx_or_basepath(basepath, args)
    rid = ensure_request_id(args)

    room_id = require_safe_id("room_id", args.get("room_id"))
    requested_run_id = _safe_str(args.get("run_id"))
    reason = _safe_str(args.get("reason") or args.get("stop_reason"), "manual_stop") or "manual_stop"
    write_aborted_message = as_bool(args.get("write_aborted_message"), True)

    meta = ensure_room_exists(room_id)
    if meta and not is_participant(uid, meta):
        return _permission_denied(rid, room_id)

    raw_state = _safe_dict(load_state_doc(room_id))
    state = _normalize_room_state_for_output(raw_state)
    snapshot = _get_runtime_control_snapshot(room_id=room_id, state=raw_state, request_row=args)

    state_run_id = _safe_str(raw_state.get("current_run_id"))
    snapshot_run_id = _safe_str(snapshot.get("run_id"))
    runtime_control_run_id = _safe_str(raw_state.get("runtime_control_run_id"))
    effective_run_id = _safe_str(requested_run_id or state_run_id or snapshot_run_id or runtime_control_run_id)

    if requested_run_id:
        known_run_ids = {
            value
            for value in [state_run_id, snapshot_run_id, runtime_control_run_id]
            if _safe_str(value)
        }
        if known_run_ids and requested_run_id not in known_run_ids:
            return _runtime_command_error(
                rid=rid,
                room_id=room_id,
                state=state,
                command="stop_current",
                error_code="run_id_mismatch",
                message="requested run_id does not match current runtime run",
                run_id=requested_run_id,
                extra={
                    "runtime_state": _safe_str(snapshot.get("runtime_state")),
                    "snapshot_version": _safe_non_negative_int(snapshot.get("snapshot_version"), 0),
                },
            )

    now = utc_iso()
    next_version = _next_runtime_control_version(raw_state)

    command_evt = _append_runtime_command_event(
        room_id=room_id,
        rid=rid,
        run_id=effective_run_id,
        command="stop_current",
        payload={
            "accepted": True,
            "stopped": True,
            "stop_requested": True,
            "reason": reason,
            "stopped_at": now,
            "refresh_hint": _DEFAULT_RUNTIME_REFRESH_HINT,
        },
    )

    aborted_evt = None
    if effective_run_id and write_aborted_message:
        aborted_evt = _append_aborted_event(
            room_id=room_id,
            request_id=rid,
            sender="system",
            sender_type="system",
            reason=reason or "manual_stop",
            run_id=effective_run_id,
        )

    has_target_run = bool(effective_run_id)

    patch = {
        "current_run_id": "",
        "current_request_id": "",
        "current_trigger_event_id": "",
        "current_run_status": "aborted" if has_target_run else "",
        "current_run_roles": [],
        "current_delegate_role_id": "",
        "current_delegate_role_name": "",
        "current_delegate_index": 0,
        "current_delegate_total": 0,
        "runtime_control_run_id": effective_run_id,
        "runtime_control_action": "stop" if has_target_run else "",
        "runtime_control_command": "stop_current" if has_target_run else "",
        "stop_requested": has_target_run,
        "runtime_stop_requested": has_target_run,
        "stop_run_id": effective_run_id if has_target_run else "",
        "runtime_stop_run_id": effective_run_id if has_target_run else "",
        "runtime_stop_reason": reason if has_target_run else "",
        "runtime_stop_requested_at": now if has_target_run else "",
        "runtime_state_hint": "idle",
        "runtime_phase_hint": "idle",
        "interruption_reason": reason,
        "pause_requested": False,
        "pause_reason": "",
        "pause_requested_at": "",
        "paused_at": "",
        "pause_effective_at": "",
        "continuation_status": "aborted" if has_target_run else "",
        "last_run_finished_at": now,
        "runtime_control_version": next_version,
        "last_supervisor_status": "aborted" if has_target_run else _safe_str(raw_state.get("last_supervisor_status")),
        "last_supervisor_phase": "idle",
        "last_supervisor_updated_at": now,
    }
    _set_room_state_patch(room_id, patch)

    next_state = _safe_dict(load_state_doc(room_id))
    next_snapshot = _get_runtime_control_snapshot(
        room_id=room_id,
        state=next_state,
        request_row={
            "room_id": room_id,
            "current_run_id": "",
            "current_run_status": "aborted" if effective_run_id else "",
            "last_supervisor_phase": "idle",
        },
    )

    tool_results = [
        _build_tool_result_item("room_runtime_command_event", event=command_evt),
        _build_tool_result_item("runtime_control_snapshot", **next_snapshot),
        _build_tool_result_item(
            "room_runtime_stop",
            room_id=room_id,
            run_id=effective_run_id,
            command="stop_current",
            status="accepted",
            accepted=True,
            stopped=True,
            reason=reason,
            stopped_at=now,
            snapshot_version=_safe_non_negative_int(next_snapshot.get("snapshot_version"), next_version),
            refresh_hint=_DEFAULT_RUNTIME_REFRESH_HINT,
        ),
    ]
    if aborted_evt:
        tool_results.append(_build_tool_result_item("aborted_event", event=aborted_evt))

    return _formal_envelope(
        request_id=rid,
        conv_id=room_id,
        mcp_overrides=state.get("mcp_overrides"),
        response="Room runtime stop accepted.",
        status="accepted",
        message="room runtime stop accepted",
        tool_calls=[],
        runtime_control_snapshot=next_snapshot,
        tool_results=tool_results,
    )


def nisb_room_runtime_pause_current(args: Dict[str, Any]) -> Dict[str, Any]:
    basepath = get_basepath(args)
    uid = uid_from_ctx_or_basepath(basepath, args)
    rid = ensure_request_id(args)

    room_id = require_safe_id("room_id", args.get("room_id"))
    requested_run_id = _safe_str(args.get("run_id"))
    reason = _safe_str(args.get("reason") or args.get("pause_reason"), "manual_pause") or "manual_pause"

    meta = ensure_room_exists(room_id)
    if meta and not is_participant(uid, meta):
        return _permission_denied(rid, room_id)

    raw_state = _safe_dict(load_state_doc(room_id))
    state = _normalize_room_state_for_output(raw_state)
    snapshot = _get_runtime_control_snapshot(room_id=room_id, state=raw_state, request_row=args)

    effective_run_id = _safe_str(requested_run_id or snapshot.get("run_id") or raw_state.get("current_run_id"))
    runtime_state = _safe_str(snapshot.get("runtime_state"))
    snapshot_version = _safe_non_negative_int(snapshot.get("snapshot_version"), 0)
    pause_request_accepted = as_bool(snapshot.get("pause_request_accepted"), False)

    if not effective_run_id:
        return _runtime_command_error(
            rid=rid,
            room_id=room_id,
            state=state,
            command="pause_current",
            error_code="no_active_run",
            message="no active run to pause",
            extra={
                "runtime_state": runtime_state,
                "snapshot_version": snapshot_version,
            },
        )

    state_run_id = _safe_str(raw_state.get("current_run_id") or snapshot.get("run_id"))
    if requested_run_id and state_run_id and requested_run_id != state_run_id:
        return _runtime_command_error(
            rid=rid,
            room_id=room_id,
            state=state,
            command="pause_current",
            error_code="run_id_mismatch",
            message="requested run_id does not match current active run",
            run_id=effective_run_id,
            extra={
                "runtime_state": runtime_state,
                "snapshot_version": snapshot_version,
            },
        )

    if runtime_state == "pause_requested" or pause_request_accepted:
        next_snapshot = _get_runtime_control_snapshot(room_id=room_id, state=raw_state)
        return _formal_envelope(
            request_id=rid,
            conv_id=room_id,
            mcp_overrides=state.get("mcp_overrides"),
            response=f"Pause already requested for run {effective_run_id}.",
            status="accepted",
            message="pause already requested",
            tool_calls=[],
            runtime_control_snapshot=next_snapshot,
            tool_results=[
                _build_tool_result_item("runtime_control_snapshot", **next_snapshot),
                _build_tool_result_item(
                    "room_runtime_pause",
                    room_id=room_id,
                    run_id=effective_run_id,
                    command="pause_current",
                    status="accepted",
                    accepted=True,
                    pause_requested=True,
                    pause_request_accepted=True,
                    reason=reason or _safe_str(raw_state.get("pause_reason") or state.get("pause_reason")),
                    snapshot_version=_safe_non_negative_int(next_snapshot.get("snapshot_version"), snapshot_version),
                    refresh_hint=_DEFAULT_RUNTIME_REFRESH_HINT,
                )
            ],
        )

    if runtime_state not in {"running", "resuming"}:
        return _runtime_command_error(
            rid=rid,
            room_id=room_id,
            state=state,
            command="pause_current",
            error_code="not_pauseable",
            message=f"current runtime_state is {runtime_state or 'idle'}",
            run_id=effective_run_id,
            extra={
                "runtime_state": runtime_state,
                "snapshot_version": snapshot_version,
            },
        )

    now = utc_iso()
    patch = {
        "current_run_id": effective_run_id,
        "pause_requested": True,
        "pause_reason": reason,
        "pause_requested_at": now,
        "continuation_status": "pause_requested",
        "runtime_control_run_id": effective_run_id,
        "runtime_state_hint": "pause_requested",
        "runtime_phase_hint": _safe_str(snapshot.get("runtime_phase"), "waiting_checkpoint") or "waiting_checkpoint",
        "runtime_control_version": _next_runtime_control_version(raw_state),
        "last_supervisor_pause_requested": True,
        "last_supervisor_pause_reason": reason,
        "last_supervisor_pause_requested_at": now,
    }
    _set_room_state_patch(room_id, patch)

    command_evt = _append_runtime_command_event(
        room_id=room_id,
        rid=rid,
        run_id=effective_run_id,
        command="pause_current",
        payload={
            "accepted": True,
            "pause_requested": True,
            "pause_request_accepted": True,
            "reason": reason,
            "pause_requested_at": now,
            "refresh_hint": _DEFAULT_RUNTIME_REFRESH_HINT,
        },
    )

    next_snapshot = _get_runtime_control_snapshot(
        room_id=room_id,
        state=_safe_dict(load_state_doc(room_id)),
        request_row={
            "room_id": room_id,
            "current_run_id": effective_run_id,
            "current_run_status": _safe_str(raw_state.get("current_run_status"), "running") or "running",
            "continuation": {
                "pause_requested": True,
                "pause_reason": reason,
                "pause_requested_at": now,
                "continuation_status": "pause_requested",
            },
        },
    )

    return _formal_envelope(
        request_id=rid,
        conv_id=room_id,
        mcp_overrides=state.get("mcp_overrides"),
        response=f"Pause accepted for run {effective_run_id}.",
        status="accepted",
        message="pause accepted",
        tool_calls=[],
        runtime_control_snapshot=next_snapshot,
        tool_results=[
            _build_tool_result_item("room_runtime_command_event", event=command_evt),
            _build_tool_result_item("runtime_control_snapshot", **next_snapshot),
            _build_tool_result_item(
                "room_runtime_pause",
                room_id=room_id,
                run_id=effective_run_id,
                command="pause_current",
                status="accepted",
                accepted=True,
                pause_requested=True,
                pause_request_accepted=True,
                reason=reason,
                snapshot_version=_safe_non_negative_int(next_snapshot.get("snapshot_version"), snapshot_version),
                refresh_hint=_DEFAULT_RUNTIME_REFRESH_HINT,
            ),
        ],
    )


def nisb_room_runtime_resume_from_checkpoint(args: Dict[str, Any]) -> Dict[str, Any]:
    basepath = get_basepath(args)
    uid = uid_from_ctx_or_basepath(basepath, args)
    rid = ensure_request_id(args)

    room_id = require_safe_id("room_id", args.get("room_id"))
    requested_run_id = _safe_str(args.get("run_id"))
    explicit_checkpoint_ref = _safe_str(args.get("resume_checkpoint_ref"))
    explicit_resume_token = _safe_str(args.get("resume_token"))

    meta = ensure_room_exists(room_id)
    if meta and not is_participant(uid, meta):
        return _permission_denied(rid, room_id)

    raw_state = _safe_dict(load_state_doc(room_id))
    state = _normalize_room_state_for_output(raw_state)
    snapshot = _get_runtime_control_snapshot(room_id=room_id, state=raw_state, request_row=args)
    auth_snapshot = _extract_runtime_auth_snapshot(
        uid=uid,
        meta=_safe_dict(meta),
        state=raw_state,
        args=args,
    )

    runtime_state = _safe_str(snapshot.get("runtime_state"))
    resume_ready = as_bool(snapshot.get("resume_ready"), False)
    current_run_id = _safe_str(snapshot.get("run_id") or raw_state.get("current_run_id"))
    resumed_from_run_id = requested_run_id or current_run_id
    resume_checkpoint_ref = _safe_str(
        explicit_checkpoint_ref
        or snapshot.get("resume_checkpoint_ref")
        or _resolve_resume_checkpoint_ref(args=args, state=raw_state)
    )
    resume_token = _safe_str(explicit_resume_token or snapshot.get("resume_token"))
    checkpoint_stage = _safe_str(
        raw_state.get("checkpoint_stage")
        or state.get("checkpoint_stage")
        or snapshot.get("checkpoint_stage")
    )
    checkpoint_summary = _safe_str(
        raw_state.get("checkpoint_summary")
        or state.get("checkpoint_summary")
        or snapshot.get("checkpoint_summary")
    )
    resumed_from_stage = _safe_str(
        args.get("resumed_from_stage")
        or snapshot.get("resumed_from_stage")
        or raw_state.get("resumed_from_stage")
        or state.get("resumed_from_stage")
        or checkpoint_stage
    )
    snapshot_version = _safe_non_negative_int(snapshot.get("snapshot_version"), 0)

    budget_exhausted = as_bool(
        raw_state.get("budget_exhausted") or state.get("budget_exhausted"),
        False,
    )
    budget_status = _safe_str(raw_state.get("budget_status") or state.get("budget_status")).lower()
    allow_budget_exhausted_resume = as_bool(args.get("allow_budget_exhausted_resume"), False)

    if runtime_state != "interrupted" or not resume_ready:
        return _runtime_command_error(
            rid=rid,
            room_id=room_id,
            state=state,
            command="resume_from_checkpoint",
            error_code="resume_not_ready",
            message="current run is not resume-ready",
            run_id=resumed_from_run_id,
            extra={
                "runtime_state": runtime_state,
                "resume_ready": resume_ready,
                "snapshot_version": snapshot_version,
            },
        )

    if budget_exhausted and not allow_budget_exhausted_resume:
        return _runtime_command_error(
            rid=rid,
            room_id=room_id,
            state=state,
            command="resume_from_checkpoint",
            error_code="budget_blocked",
            message="budget exhausted; resume blocked until budget is updated or explicitly allowed",
            run_id=resumed_from_run_id,
            extra={
                "budget_exhausted": True,
                "budget_status": budget_status or "exhausted",
                "snapshot_version": snapshot_version,
            },
        )

    if not resume_checkpoint_ref and not resume_token:
        return _runtime_command_error(
            rid=rid,
            room_id=room_id,
            state=state,
            command="resume_from_checkpoint",
            error_code="checkpoint_required",
            message="no resumable checkpoint available",
            run_id=resumed_from_run_id,
            extra={"snapshot_version": snapshot_version},
        )

    resumed_run_id = _safe_str(args.get("resumed_run_id")) or _build_run_id()
    resumed_from_event_id = _safe_str(
        args.get("resumed_from_event_id")
        or snapshot.get("resumed_from_event_id")
        or raw_state.get("final_event_id")
        or raw_state.get("checkpoint_event_id")
        or raw_state.get("current_trigger_event_id")
        or resume_checkpoint_ref
    )

    skipped_effects = _safe_list(args.get("skipped_effects") or snapshot.get("skipped_effects"))
    effect_dispositions = _safe_list(args.get("effect_dispositions") or snapshot.get("effect_dispositions"))

    launch_ctx = _resolve_resume_launch_context(
        room_id=room_id,
        args=args,
        state=state,
        resume_checkpoint_ref=resume_checkpoint_ref,
        resumed_from_event_id=resumed_from_event_id,
    )

    question = _safe_str(launch_ctx.get("question"))
    mode_used = _safe_str(launch_ctx.get("mode_used"), "off") or "off"
    model_name = _safe_str(launch_ctx.get("model_name"), "gpt-4o-mini") or "gpt-4o-mini"
    reply_mode = _safe_str(launch_ctx.get("reply_mode"), "manual") or "manual"
    active_role_objs = _safe_list(launch_ctx.get("active_role_objs"))
    role_ids = [
        str(r.get("role_id") or "").strip()
        for r in active_role_objs
        if str(r.get("role_id") or "").strip()
    ]

    if not question:
        return _runtime_command_error(
            rid=rid,
            room_id=room_id,
            state=state,
            command="resume_from_checkpoint",
            error_code="resume_question_missing",
            message="unable to recover question from checkpoint context",
            run_id=resumed_run_id,
            extra={
                "resume_checkpoint_ref": resume_checkpoint_ref,
                "resumed_from_event_id": resumed_from_event_id,
                "snapshot_version": snapshot_version,
            },
        )

    if not active_role_objs:
        return _runtime_command_error(
            rid=rid,
            room_id=room_id,
            state=state,
            command="resume_from_checkpoint",
            error_code="no_active_roles",
            message="no active roles available for resumed orchestration",
            run_id=resumed_run_id,
            extra={
                "reply_mode": reply_mode,
                "snapshot_version": snapshot_version,
            },
        )

    patch = {
        "current_run_id": resumed_run_id,
        "current_request_id": rid,
        "current_run_status": "running",
        "current_run_roles": role_ids,
        "current_delegate_role_id": "",
        "current_delegate_role_name": "",
        "current_delegate_index": 0,
        "current_delegate_total": len(role_ids),
        "pause_requested": False,
        "pause_reason": "",
        "pause_requested_at": "",
        "paused_at": "",
        "pause_effective_at": "",
        "resume_ready": False,
        "resume_token": "",
        "resume_reason": "",
        "error_blocking_resume": False,
        "resume_from_checkpoint": True,
        "resume_checkpoint_ref": resume_checkpoint_ref,
        "continuation_mode": "resumed",
        "continuation_status": "resumed",
        "resumed_from_run_id": resumed_from_run_id,
        "resumed_from_event_id": resumed_from_event_id,
        "resumed_from_stage": resumed_from_stage,
        "checkpoint_stage": checkpoint_stage,
        "checkpoint_summary": checkpoint_summary,
        "runtime_control_run_id": resumed_run_id,
        "runtime_state_hint": "resuming",
        "runtime_phase_hint": "supervisor" if reply_mode == "supervisor" else "worker",
        "runtime_control_version": _next_runtime_control_version(raw_state),
        "last_supervisor_resume_from_checkpoint": True,
        "last_supervisor_resume_checkpoint_ref": resume_checkpoint_ref,
        "last_supervisor_continuation_mode": "resumed",
        "last_supervisor_continuation_status": "resumed",
        "last_supervisor_resumed_from_run_id": resumed_from_run_id,
        "last_supervisor_resumed_from_event_id": resumed_from_event_id,
        "last_supervisor_resumed_from_stage": resumed_from_stage,
    }

    if skipped_effects:
        patch["skipped_effects"] = skipped_effects
        patch["last_supervisor_skipped_effects"] = skipped_effects

    if effect_dispositions:
        patch["effect_dispositions"] = effect_dispositions
        patch["last_supervisor_effect_dispositions"] = effect_dispositions

    _set_room_state_patch(room_id, patch)

    command_evt = _append_runtime_command_event(
        room_id=room_id,
        rid=rid,
        run_id=resumed_run_id,
        command="resume_from_checkpoint",
        payload={
            "accepted": True,
            "resume_started": True,
            "resume_from_checkpoint": True,
            "resume_checkpoint_ref": resume_checkpoint_ref,
            "resume_token": resume_token,
            "resumed_from_run_id": resumed_from_run_id,
            "resumed_from_event_id": resumed_from_event_id,
            "resumed_from_stage": resumed_from_stage,
            "checkpoint_stage": checkpoint_stage,
            "checkpoint_summary": checkpoint_summary,
            "skipped_effects": skipped_effects,
            "effect_dispositions": effect_dispositions,
            "refresh_hint": _DEFAULT_RUNTIME_REFRESH_HINT,
        },
    )

    _set_room_state_patch(
        room_id,
        {
            "current_trigger_event_id": command_evt["id"],
        },
    )

    next_snapshot = _get_runtime_control_snapshot(
        room_id=room_id,
        state=_safe_dict(load_state_doc(room_id)),
        request_row={
            "room_id": room_id,
            "current_run_id": resumed_run_id,
            "current_run_status": "running",
            "last_supervisor_phase": "supervisor" if reply_mode == "supervisor" else "worker",
            "continuation": {
                "continuation_mode": "resumed",
                "continuation_status": "resumed",
                "pause_requested": False,
                "pause_reason": "",
                "resume_from_checkpoint": True,
                "resume_checkpoint_ref": resume_checkpoint_ref,
                "resume_ready": False,
                "resume_token": "",
                "resume_reason": "",
                "resumed_from_run_id": resumed_from_run_id,
                "resumed_from_event_id": resumed_from_event_id,
                "resumed_from_stage": resumed_from_stage,
                "last_completed_step": checkpoint_stage,
                "skipped_effects": skipped_effects,
                "effect_dispositions": effect_dispositions,
            },
        },
    )

    resume_runtime_result = _build_tool_result_item(
        "room_runtime_resume",
        room_id=room_id,
        command="resume_from_checkpoint",
        status="accepted",
        accepted=True,
        resume_started=True,
        run_id=resumed_run_id,
        resumed_run_id=resumed_run_id,
        resumed_from_run_id=resumed_from_run_id,
        resumed_from_event_id=resumed_from_event_id,
        resumed_from_stage=resumed_from_stage,
        resume_from_checkpoint=True,
        resume_checkpoint_ref=resume_checkpoint_ref,
        checkpoint_stage=checkpoint_stage,
        checkpoint_summary=checkpoint_summary,
        budget_exhausted=budget_exhausted,
        budget_status=budget_status,
        skipped_effects=skipped_effects,
        effect_dispositions=effect_dispositions,
        question=question,
        reply_mode=reply_mode,
        role_ids=role_ids,
        snapshot_version=_safe_non_negative_int(next_snapshot.get("snapshot_version"), snapshot_version),
        runtime_control_snapshot=next_snapshot,
        refresh_hint=_DEFAULT_RUNTIME_REFRESH_HINT,
    )

    resume_request_args = dict(args or {})
    resume_request_args["basepath"] = basepath
    resume_request_args["request_id"] = rid
    resume_request_args["room_id"] = room_id
    resume_request_args["model"] = model_name
    resume_request_args["mode_used"] = mode_used
    resume_request_args["rag_mode"] = mode_used
    resume_request_args["reply_mode"] = reply_mode
    resume_request_args["current_run_id"] = resumed_run_id
    resume_request_args["current_run_status"] = "running"
    resume_request_args["current_trigger_event_id"] = command_evt["id"]
    resume_request_args["trigger_event_id"] = command_evt["id"]
    resume_request_args["_user_question"] = question
    resume_request_args["question"] = question
    resume_request_args["resume_from_checkpoint"] = True
    resume_request_args["resume_checkpoint_ref"] = resume_checkpoint_ref
    resume_request_args["resume_token"] = resume_token
    resume_request_args["resumed_from_run_id"] = resumed_from_run_id
    resume_request_args["resumed_from_event_id"] = resumed_from_event_id
    resume_request_args["resumed_from_stage"] = resumed_from_stage
    resume_request_args["checkpoint_stage"] = checkpoint_stage
    resume_request_args["checkpoint_summary"] = checkpoint_summary
    resume_request_args["skipped_effects"] = skipped_effects
    resume_request_args["effect_dispositions"] = effect_dispositions
    resume_request_args["continuation"] = {
        "continuation_mode": "resumed",
        "continuation_status": "resumed",
        "pause_requested": False,
        "pause_reason": "",
        "resume_from_checkpoint": True,
        "resume_checkpoint_ref": resume_checkpoint_ref,
        "resume_ready": False,
        "resume_token": "",
        "resume_reason": "",
        "resumed_from_run_id": resumed_from_run_id,
        "resumed_from_event_id": resumed_from_event_id,
        "resumed_from_stage": resumed_from_stage,
        "last_completed_step": checkpoint_stage,
        "skipped_effects": skipped_effects,
        "effect_dispositions": effect_dispositions,
    }
    resume_request_args = _inject_runtime_auth_snapshot(resume_request_args, auth_snapshot)

    try:
        if reply_mode == "supervisor":
            supervisor_res = _run_supervisor_orchestration(
                room_id=room_id,
                question=question,
                active_roles=active_role_objs,
                model_name=model_name,
                mode_used=mode_used,
                run_id=resumed_run_id,
                trigger_event_id=command_evt["id"],
                rid=rid,
                request_args=resume_request_args,
            )

            if _is_runtime_skip_result(supervisor_res):
                skip_rows = _extract_runtime_skip_rows(supervisor_res)
                reason_code = _safe_str(
                    (_safe_dict(skip_rows[0]).get("reason_code") if skip_rows else ""),
                    "ROOM_ROLE_NOT_SHARED",
                ) or "ROOM_ROLE_NOT_SHARED"

                _mark_runtime_run_skipped(
                    room_id=room_id,
                    run_id=resumed_run_id,
                    rid=rid,
                    reason_code=reason_code,
                )

                skipped_snapshot = _get_runtime_control_snapshot(
                    room_id=room_id,
                    state=_safe_dict(load_state_doc(room_id)),
                )

                return _formal_envelope(
                    request_id=rid,
                    conv_id=room_id,
                    mcp_overrides=state.get("mcp_overrides"),
                    response=f"Resume accepted for room {room_id}, runtime skipped.",
                    status="accepted",
                    message="resume accepted; runtime skipped",
                    tool_calls=[],
                    runtime_control_snapshot=skipped_snapshot,
                    tool_results=[
                        _build_tool_result_item("room_runtime_command_event", event=command_evt),
                        _build_tool_result_item("runtime_control_snapshot", **skipped_snapshot),
                        resume_runtime_result,
                        *skip_rows,
                    ],
                )

            plan_evt, delegate_evts, final_evt = supervisor_res

            preferred_evt = final_evt or _find_last_generated_message_event(
                room_id=room_id,
                run_id=resumed_run_id,
                trigger_event_id=command_evt["id"],
            )

            tool_results = [
                _build_tool_result_item("room_runtime_command_event", event=command_evt),
                _build_tool_result_item("runtime_control_snapshot", **next_snapshot),
                resume_runtime_result,
            ]
            if plan_evt:
                tool_results.append(_build_tool_result_item("plan_event", event=plan_evt))
            if delegate_evts:
                tool_results.append(_build_tool_result_item("delegate_events", events=delegate_evts))
            if final_evt:
                tool_results.append(_build_tool_result_item("final_event", event=final_evt))
            if preferred_evt and not _same_event(preferred_evt, final_evt):
                tool_results.append(_build_tool_result_item("generated_event", event=preferred_evt))

            return _formal_envelope(
                request_id=rid,
                conv_id=room_id,
                mcp_overrides=state.get("mcp_overrides"),
                response=f"Resume accepted for room {room_id}.",
                status="accepted",
                message="resume accepted",
                tool_calls=[],
                runtime_control_snapshot=next_snapshot,
                tool_results=tool_results,
            )

        generated_events = _run_sequential_orchestration(
            room_id=room_id,
            question=question,
            active_roles=active_role_objs,
            model_name=model_name,
            mode_used=mode_used,
            run_id=resumed_run_id,
            trigger_event_id=command_evt["id"],
            rid=rid,
            request_args=resume_request_args,
        )

        if _is_runtime_skip_result(generated_events):
            skip_rows = _extract_runtime_skip_rows(generated_events)
            reason_code = _safe_str(
                (_safe_dict(skip_rows[0]).get("reason_code") if skip_rows else ""),
                "ROOM_ROLE_NOT_SHARED",
            ) or "ROOM_ROLE_NOT_SHARED"

            _mark_runtime_run_skipped(
                room_id=room_id,
                run_id=resumed_run_id,
                rid=rid,
                reason_code=reason_code,
            )

            skipped_snapshot = _get_runtime_control_snapshot(
                room_id=room_id,
                state=_safe_dict(load_state_doc(room_id)),
            )

            return _formal_envelope(
                request_id=rid,
                conv_id=room_id,
                mcp_overrides=state.get("mcp_overrides"),
                response=f"Resume accepted for room {room_id}, runtime skipped.",
                status="accepted",
                message="resume accepted; runtime skipped",
                tool_calls=[],
                runtime_control_snapshot=skipped_snapshot,
                tool_results=[
                    _build_tool_result_item("room_runtime_command_event", event=command_evt),
                    _build_tool_result_item("runtime_control_snapshot", **skipped_snapshot),
                    resume_runtime_result,
                    *skip_rows,
                ],
            )

        preferred_evt = generated_events[-1] if generated_events else None
        tool_results = [
            _build_tool_result_item("room_runtime_command_event", event=command_evt),
            _build_tool_result_item("runtime_control_snapshot", **next_snapshot),
            resume_runtime_result,
            _build_tool_result_item("generated_events", events=generated_events),
        ]
        if preferred_evt:
            tool_results.append(_build_tool_result_item("generated_event", event=preferred_evt))

        return _formal_envelope(
            request_id=rid,
            conv_id=room_id,
            mcp_overrides=state.get("mcp_overrides"),
            response=f"Resume accepted for room {room_id}.",
            status="accepted",
            message="resume accepted",
            tool_calls=[],
            runtime_control_snapshot=next_snapshot,
            tool_results=tool_results,
        )

    except Exception as ex:
        state_after_error = _safe_dict(load_state_doc(room_id))
        if _safe_str(state_after_error.get("current_run_id")) == resumed_run_id:
            if _safe_str(state_after_error.get("current_run_status")).lower() == "running":
                _mark_runtime_run_failed(room_id=room_id, run_id=resumed_run_id, rid=rid)

        aborted = _append_aborted_event(
            room_id=room_id,
            request_id=rid,
            trigger_event_id=command_evt["id"],
            sender="supervisor" if reply_mode == "supervisor" else "runtime",
            sender_type="system",
            reason=f"resume_dispatch_exception:{type(ex).__name__}",
            run_id=resumed_run_id,
            mode_used=mode_used,
        )

        error_snapshot = _get_runtime_control_snapshot(
            room_id=room_id,
            state=_safe_dict(load_state_doc(room_id)),
        )

        return _formal_envelope(
            request_id=rid,
            conv_id=room_id,
            mcp_overrides=state.get("mcp_overrides"),
            response=f"Resume dispatch failed for run {resumed_run_id}.",
            status="error",
            message="resume dispatch failed",
            tool_calls=[],
            tool_results=[
                _build_tool_result_item("room_runtime_command_event", event=command_evt),
                _build_tool_result_item("runtime_control_snapshot", **error_snapshot),
                resume_runtime_result,
                _build_tool_result_item("aborted_event", event=aborted),
                _build_tool_result_item(
                    "room_runtime_resume_error",
                    room_id=room_id,
                    run_id=resumed_run_id,
                    error=f"{type(ex).__name__}: {ex}",
                ),
            ],
        )

    finally:
        _finalize_runtime_dispatch(room_id=room_id, run_id=resumed_run_id, rid=rid)


__all__ = [
    "_safe_non_negative_int",
    "_next_runtime_control_version",
    "_find_last_generated_message_event",
    "_extract_runtime_auth_snapshot",
    "_inject_runtime_auth_snapshot",
    "_extract_runtime_skip_rows",
    "_is_runtime_skip_result",
    "_mark_runtime_run_failed",
    "_mark_runtime_run_skipped",
    "_finalize_runtime_dispatch",
    "_start_room_runtime_run",
    "nisb_room_runtime_stop_current",
    "nisb_room_runtime_pause_current",
    "nisb_room_runtime_resume_from_checkpoint",
]

