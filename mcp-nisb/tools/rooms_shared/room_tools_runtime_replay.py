from __future__ import annotations

from typing import Any, Dict

from .room_contracts import as_bool, ensure_request_id, require_safe_id
from .room_replay_builder import _build_room_run_replay
from .room_replay_projection import _build_runtime_events_result
from .room_runtime_reader import (
    _RUNTIME_EVENT_TYPES,
    _derive_latest_runtime_run_id,
    _event_id,
    _filter_runtime_items,
    _slice_after_event_id,
)
from .room_state_normalizer import (
    _normalize_room_state_for_output,
    _safe_dict,
    _safe_list,
    _safe_str,
)
from .room_store import (
    ensure_room_exists,
    get_basepath,
    is_participant,
    load_recent_room_events,
    load_room_events,
    load_state_doc,
    uid_from_ctx_or_basepath,
)
from .room_tool_common import (
    _build_tool_result_item,
    _formal_envelope,
    _permission_denied,
)
from .room_tools_runtime_current import _get_runtime_control_snapshot


def nisb_room_shared_recent(args: Dict[str, Any]) -> Dict[str, Any]:
    basepath = get_basepath(args)
    uid = uid_from_ctx_or_basepath(basepath, args)
    rid = ensure_request_id(args)

    room_id = require_safe_id("room_id", args.get("room_id"))
    limit = args.get("limit", 80)
    order = str(args.get("order") or "desc").strip().lower()
    before_event_id = _safe_str(args.get("before_event_id"))
    cursor = args.get("cursor")
    byte_budget = args.get("byte_budget", 524288)
    relation_expand = args.get("relation_expand", True)

    try:
        limit = int(limit)
    except Exception:
        limit = 80
    limit = max(1, min(200, limit))

    try:
        byte_budget = int(byte_budget)
    except Exception:
        byte_budget = 524288
    byte_budget = max(65536, min(2097152, byte_budget))

    order = "asc" if order == "asc" else "desc"
    relation_expand = as_bool(relation_expand, True)

    meta = ensure_room_exists(room_id)
    if meta and not is_participant(uid, meta):
        return _permission_denied(rid, room_id)

    recent = load_recent_room_events(
        room_id,
        limit=limit,
        order=order,
        before_event_id=before_event_id,
        cursor=cursor,
        byte_budget=byte_budget,
        relation_expand=relation_expand,
    )
    items = _safe_list(recent.get("items"))

    state = _normalize_room_state_for_output(load_state_doc(room_id))

    return _formal_envelope(
        request_id=rid,
        conv_id=room_id,
        mcp_overrides=state.get("mcp_overrides"),
        response=f"Loaded {len(items)} room events.",
        status="success",
        message="room events loaded",
        tool_calls=[],
        tool_results=[
            _build_tool_result_item(
                "room_items",
                items=items,
                limit=limit,
                order=order,
                returned_count=len(items),
                has_more=bool(recent.get("has_more")),
                next_cursor=_safe_dict(recent.get("next_cursor")),
                source=_safe_str(recent.get("source"), "tail_window"),
                byte_budget=byte_budget,
                relation_expand=relation_expand,
                before_event_id=before_event_id,
                file_size=recent.get("file_size", 0),
                window_start_offset=recent.get("window_start_offset", 0),
                window_end_offset=recent.get("window_end_offset", 0),
                selected_oldest_offset=recent.get("selected_oldest_offset", 0),
                selected_newest_offset=recent.get("selected_newest_offset", 0),
            )
        ],
    )


def nisb_room_events_recent(args: Dict[str, Any]) -> Dict[str, Any]:
    basepath = get_basepath(args)
    uid = uid_from_ctx_or_basepath(basepath, args)
    rid = ensure_request_id(args)

    room_id = require_safe_id("room_id", args.get("room_id"))
    requested_run_id = _safe_str(args.get("run_id"))
    after_event_id = _safe_str(args.get("after_event_id"))
    order = _safe_str(args.get("order"), "asc").lower()
    include_all_runs = as_bool(args.get("include_all_runs"), False)

    try:
        limit = int(args.get("limit", 120))
    except Exception:
        limit = 120
    limit = max(1, min(400, limit))

    order = "desc" if order == "desc" else "asc"

    meta = ensure_room_exists(room_id)
    if meta and not is_participant(uid, meta):
        return _permission_denied(rid, room_id)

    rows = _safe_list(load_room_events(room_id))
    raw_state = _safe_dict(load_state_doc(room_id))
    state = _normalize_room_state_for_output(raw_state)

    derived_run_id = _derive_latest_runtime_run_id(rows)
    state_current_run_id = _safe_str(raw_state.get("current_run_id") or state.get("current_run_id"))
    state_current_run_status = _safe_str(raw_state.get("current_run_status") or state.get("current_run_status"))
    preferred_run_id = requested_run_id or state_current_run_id or derived_run_id

    effective_run_id = "" if include_all_runs else preferred_run_id

    runtime_items = _filter_runtime_items(rows, run_id=effective_run_id)
    latest_evt = runtime_items[-1] if runtime_items else None
    latest_event_id = _event_id(latest_evt)

    if after_event_id and latest_event_id and after_event_id == latest_event_id:
        sliced_info = {"items": [], "after_event_found": True}
    else:
        sliced_info = _slice_after_event_id(runtime_items, after_event_id=after_event_id)

    remaining_items = _safe_list(sliced_info.get("items"))
    after_event_found = bool(sliced_info.get("after_event_found"))

    if order == "desc":
        remaining_items = list(reversed(remaining_items))

    has_more = len(remaining_items) > limit
    items = remaining_items[:limit]

    runtime_snapshot = _get_runtime_control_snapshot(room_id=room_id, state=raw_state)
    runtime_result = _build_runtime_events_result(
        room_id=room_id,
        runtime_items=runtime_items,
        items=items,
        run_id=effective_run_id,
        requested_run_id=requested_run_id,
        derived_run_id=derived_run_id,
        state_current_run_id=state_current_run_id,
        state_current_run_status=state_current_run_status,
        include_all_runs=include_all_runs,
        after_event_id=after_event_id,
        after_event_found=after_event_found,
        latest_event_id=latest_event_id,
        limit=limit,
        order=order,
        has_more=has_more,
        event_types=sorted(list(_RUNTIME_EVENT_TYPES)),
    )

    return _formal_envelope(
        request_id=rid,
        conv_id=room_id,
        mcp_overrides=state.get("mcp_overrides"),
        response=f"Loaded {len(items)} room runtime events.",
        status="success",
        message="room runtime events loaded",
        tool_calls=[],
        runtime_control_snapshot=runtime_snapshot,
        tool_results=[
            _build_tool_result_item("runtime_control_snapshot", **runtime_snapshot),
            _build_tool_result_item("room_runtime_events", **runtime_result),
        ],
    )


def nisb_room_events_replay(args: Dict[str, Any]) -> Dict[str, Any]:
    basepath = get_basepath(args)
    uid = uid_from_ctx_or_basepath(basepath, args)
    rid = ensure_request_id(args)

    room_id = require_safe_id("room_id", args.get("room_id"))
    requested_run_id = _safe_str(args.get("run_id"))
    include_tool_activity = as_bool(args.get("include_tool_activity"), True)
    include_evidence = as_bool(args.get("include_evidence"), True)

    meta = ensure_room_exists(room_id)
    if meta and not is_participant(uid, meta):
        return _permission_denied(rid, room_id)

    rows = _safe_list(load_room_events(room_id))
    raw_state = _safe_dict(load_state_doc(room_id))
    state = _normalize_room_state_for_output(raw_state)
    runtime_snapshot = _get_runtime_control_snapshot(room_id=room_id, state=raw_state)

    replay = _build_room_run_replay(
        room_id=room_id,
        rows=rows,
        state=state,
        requested_run_id=requested_run_id,
        include_tool_activity=include_tool_activity,
        include_evidence=include_evidence,
    )

    effective_run_id = _safe_str(replay.get("run_id"))
    event_count = len(_safe_list(replay.get("events")))
    response = (
        f"Loaded room replay for run {effective_run_id} with {event_count} runtime events."
        if effective_run_id
        else f"Loaded room replay with {event_count} runtime events."
    )

    return _formal_envelope(
        request_id=rid,
        conv_id=room_id,
        mcp_overrides=state.get("mcp_overrides"),
        response=response,
        status="success",
        message="room replay loaded",
        tool_calls=[],
        runtime_control_snapshot=runtime_snapshot,
        tool_results=[
            _build_tool_result_item("runtime_control_snapshot", **runtime_snapshot),
            _build_tool_result_item("room_run_replay", **replay),
        ],
    )


__all__ = [
    "nisb_room_shared_recent",
    "nisb_room_events_recent",
    "nisb_room_events_replay",
]
