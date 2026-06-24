from __future__ import annotations

from typing import Any, Dict, List, Optional

from .room_contracts import as_bool, ensure_request_id, require_safe_id
from .room_state_normalizer import _normalize_room_state_for_output, _safe_dict, _safe_list, _safe_str
from .room_store import (
    ensure_room_exists,
    get_basepath,
    is_participant,
    load_state_doc,
    uid_from_ctx_or_basepath,
)
from .room_supervisor_runtime_status import _build_runtime_control_snapshot
from .room_tool_common import (
    _build_tool_result_item,
    _formal_envelope,
    _permission_denied,
)


def _continuation_payload_from_state(state: Dict[str, Any]) -> Dict[str, Any]:
    row = _safe_dict(state)
    return {
        "continuation_mode": _safe_str(row.get("continuation_mode")),
        "continuation_status": _safe_str(row.get("continuation_status")),
        "pause_requested": as_bool(row.get("pause_requested"), False),
        "pause_reason": _safe_str(row.get("pause_reason")),
        "pause_requested_at": _safe_str(row.get("pause_requested_at")),
        "paused_at": _safe_str(row.get("paused_at")),
        "pause_effective_at": _safe_str(row.get("pause_effective_at")),
        "interruption_reason": _safe_str(row.get("interruption_reason")),
        "resume_from_checkpoint": as_bool(row.get("resume_from_checkpoint"), False),
        "resume_checkpoint_ref": _safe_str(row.get("resume_checkpoint_ref")),
        "resume_ready": as_bool(row.get("resume_ready"), False),
        "resume_token": _safe_str(row.get("resume_token")),
        "resume_reason": _safe_str(row.get("resume_reason")),
        "error_blocking_resume": as_bool(row.get("error_blocking_resume"), False),
        "resumed_from_run_id": _safe_str(row.get("resumed_from_run_id")),
        "resumed_from_event_id": _safe_str(row.get("resumed_from_event_id")),
        "resumed_from_stage": _safe_str(row.get("resumed_from_stage")),
        "last_completed_step": _safe_str(row.get("last_completed_step")),
        "skipped_effects": _safe_list(row.get("skipped_effects")),
        "effect_dispositions": _safe_list(row.get("effect_dispositions")),
    }


def _get_runtime_control_snapshot(
    *,
    room_id: str,
    state: Optional[Dict[str, Any]] = None,
    request_row: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    raw_state = _safe_dict(state if isinstance(state, dict) else load_state_doc(room_id))
    req = dict(_safe_dict(request_row))
    req.setdefault("room_id", room_id)
    req.setdefault("current_run_id", _safe_str(raw_state.get("current_run_id")))
    req.setdefault("current_run_status", _safe_str(raw_state.get("current_run_status")))
    req.setdefault("last_supervisor_phase", _safe_str(raw_state.get("last_supervisor_phase")))

    merged_continuation = {
        **_continuation_payload_from_state(raw_state),
        **_safe_dict(req.get("continuation")),
    }
    req["continuation"] = merged_continuation

    memory_resume_row = {
        "resume_ready": as_bool(raw_state.get("resume_ready"), False),
        "resume_token": _safe_str(raw_state.get("resume_token")),
        "resume_reason": _safe_str(raw_state.get("resume_reason")),
    }

    current_status = _safe_str(
        req.get("current_run_status") or raw_state.get("current_run_status")
    ).lower()

    return _build_runtime_control_snapshot(
        prev_state=raw_state,
        request_row=req,
        phase=_safe_str(req.get("last_supervisor_phase") or raw_state.get("last_supervisor_phase")),
        status=current_status,
        finished=current_status in {"completed", "failed", "error", "interrupted", "success"},
        memory_resume_row=memory_resume_row,
    )


def _build_running_runtime_result(
    *,
    room_id: str,
    run_id: str,
    request_id: str,
    reply_mode: str,
    active_role_objs: List[Dict[str, Any]],
    model_name: str,
    status: str = "running",
    runtime_control_snapshot: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    return _build_tool_result_item(
        "room_runtime_run",
        room_id=room_id,
        run_id=run_id,
        request_id=request_id,
        reply_mode=reply_mode,
        status=status,
        role_ids=[str(r.get("role_id") or "").strip() for r in active_role_objs],
        runtime_model=model_name,
        runtime_control_snapshot=_safe_dict(runtime_control_snapshot),
    )


def _runtime_snapshot_tool_result_from_runtime_row(runtime_row: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    row = _safe_dict(runtime_row)
    snapshot = _safe_dict(row.get("runtime_control_snapshot"))
    if not snapshot:
        return None
    return _build_tool_result_item("runtime_control_snapshot", **snapshot)


def nisb_room_runtime_control_snapshot(args: Dict[str, Any]) -> Dict[str, Any]:
    basepath = get_basepath(args)
    uid = uid_from_ctx_or_basepath(basepath, args)
    rid = ensure_request_id(args)

    room_id = require_safe_id("room_id", args.get("room_id"))

    meta = ensure_room_exists(room_id)
    if meta and not is_participant(uid, meta):
        return _permission_denied(rid, room_id)

    raw_state = _safe_dict(load_state_doc(room_id))
    state = _normalize_room_state_for_output(raw_state)
    snapshot = _get_runtime_control_snapshot(room_id=room_id, state=raw_state, request_row=args)

    return _formal_envelope(
        request_id=rid,
        conv_id=room_id,
        mcp_overrides=state.get("mcp_overrides"),
        response="runtime control snapshot loaded",
        status="success",
        message="runtime control snapshot loaded",
        tool_calls=[],
        runtime_control_snapshot=snapshot,
        tool_results=[
            _build_tool_result_item("runtime_control_snapshot", **snapshot),
        ],
    )


__all__ = [
    "_get_runtime_control_snapshot",
    "_build_running_runtime_result",
    "_runtime_snapshot_tool_result_from_runtime_row",
    "nisb_room_runtime_control_snapshot",
]
