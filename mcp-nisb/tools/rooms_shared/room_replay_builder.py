from __future__ import annotations

from typing import Any, Dict, List

from .room_audit_helpers import (
    _build_state_supervisor_audit_snapshot,
    _find_supervisor_audit_relation,
    _load_room_state,
)
from .room_replay_projection import (
    _build_evidence_items,
    _build_relations,
    _build_run_overview,
    _build_run_summary_core,
    _build_run_trace,
    _build_tool_activity,
    _collect_delegate_roles,
    _first_event_of_type,
    _last_event_of_type,
    _latest_supervisor_sections_from_items,
    _normalize_phase_item,
    _summary_from_event,
)
from .room_runtime_reader import (
    _collect_runtime_run_ids,
    _derive_latest_runtime_run_id,
    _event_id,
    _event_type,
    _filter_runtime_items,
)
from .room_state_normalizer import _safe_dict, _safe_list, _safe_str


def _build_room_run_replay(
    *,
    room_id: str,
    rows: List[Dict[str, Any]],
    state: Dict[str, Any],
    requested_run_id: str = "",
    include_tool_activity: bool = True,
    include_evidence: bool = True,
) -> Dict[str, Any]:
    all_rows = _safe_list(rows)
    all_run_ids = _collect_runtime_run_ids(all_rows)
    derived_run_id = _derive_latest_runtime_run_id(all_rows)
    requested_run_id = _safe_str(requested_run_id)

    requested_run_found = True
    if requested_run_id:
        requested_run_found = requested_run_id in all_run_ids

    effective_run_id = requested_run_id if requested_run_found and requested_run_id else derived_run_id
    run_items = _filter_runtime_items(all_rows, run_id=effective_run_id) if effective_run_id else []

    phases = [
        _normalize_phase_item(
            evt,
            include_tool_activity=include_tool_activity,
            include_evidence=include_evidence,
        )
        for evt in run_items
    ]

    plan_evt = _first_event_of_type(run_items, "room.plan")
    supervisor_evt = _last_event_of_type(run_items, "room.supervisor")
    final_evt = _last_event_of_type(run_items, "room.final")
    first_evt = run_items[0] if run_items else None
    last_evt = run_items[-1] if run_items else None

    available_runs = [_build_run_overview(all_rows, rid) for rid in all_run_ids]
    tool_activity = _build_tool_activity(phases) if include_tool_activity else []
    evidence_items = _build_evidence_items(phases) if include_evidence else []
    relations = _build_relations(run_items)
    delegate_roles = _collect_delegate_roles(run_items)
    delegate_total = len([x for x in run_items if _event_type(x) == "room.delegate"])

    raw_state = _safe_dict(_load_room_state(room_id))
    input_state = _safe_dict(state)
    effective_state = {
        **input_state,
        **raw_state,
    }

    relation_audit = _find_supervisor_audit_relation(
        room_id=room_id,
        run_id=effective_run_id,
        supervisor_event_id=_event_id(supervisor_evt),
        final_event_id=_event_id(final_evt),
    )

    audit = relation_audit or _build_state_supervisor_audit_snapshot(
        state=effective_state,
        run_id=effective_run_id,
        supervisor_event=supervisor_evt,
        final_event=final_evt,
    )

    latest_sections = _latest_supervisor_sections_from_items(run_items)
    latest_fs_read = _safe_dict(latest_sections.get("supervisor_fs_read"))
    latest_notebook_read = _safe_dict(latest_sections.get("supervisor_notebook_read"))
    latest_notebook_write = _safe_dict(latest_sections.get("supervisor_notebook_write"))
    latest_memory_read = _safe_dict(latest_sections.get("supervisor_memory_read"))
    latest_memory_resume = _safe_dict(latest_sections.get("supervisor_memory_resume"))
    latest_memory_write = _safe_dict(latest_sections.get("supervisor_memory_write"))

    snapshot_state = _safe_dict(effective_state)

    room_state_snapshot = {
        "current_run_id": _safe_str(snapshot_state.get("current_run_id")),
        "current_run_status": _safe_str(snapshot_state.get("current_run_status")),
        "last_plan_at": _safe_str(snapshot_state.get("last_plan_at")),
        "last_run_finished_at": _safe_str(snapshot_state.get("last_run_finished_at")),
        "last_message_id": _safe_str(snapshot_state.get("last_message_id")),
        "last_message_at": _safe_str(snapshot_state.get("last_message_at")),
        "last_supervisor_phase": _safe_str(snapshot_state.get("last_supervisor_phase")),
        "last_supervisor_status": _safe_str(snapshot_state.get("last_supervisor_status")),
        "last_supervisor_fs_read_status": _safe_str(snapshot_state.get("last_supervisor_fs_read_status")),
        "last_supervisor_notebook_read_status": _safe_str(snapshot_state.get("last_supervisor_notebook_read_status")),
        "last_supervisor_notebook_write_status": _safe_str(snapshot_state.get("last_supervisor_notebook_write_status")),
        "supervisor_skill_strategy": _safe_str(snapshot_state.get("supervisor_skill_strategy")),
        "enabled_supervisor_skill_ids": [
            _safe_str(x) for x in _safe_list(snapshot_state.get("enabled_supervisor_skill_ids")) if _safe_str(x)
        ],
        "supervisor_audit_relations_count": len(_safe_list(snapshot_state.get("supervisor_audit_relations"))),
        "supervisor_memory_read_status": _safe_str(latest_memory_read.get("status")),
        "supervisor_memory_resume_decision": _safe_str(latest_memory_resume.get("decision")),
        "supervisor_memory_write_status": _safe_str(latest_memory_write.get("status")),
    }

    summary_core = _build_run_summary_core(run_items, run_id=effective_run_id)
    trace = _build_run_trace(effective_run_id, run_items)

    status = (
        _safe_str(summary_core.get("status"))
        or _safe_str(trace.get("status"))
        or "empty"
    )
    result_state = (
        _safe_str(summary_core.get("result_state"))
        or _safe_str(trace.get("result_state"))
    )
    final_response = (
        _safe_str(summary_core.get("final_response"))
        or _safe_str(trace.get("final_response"))
        or _summary_from_event(final_evt)
    )

    started_at = (
        _safe_str(trace.get("started_at"))
        or _safe_str(_safe_dict(first_evt).get("ts"))
    )
    finished_at = (
        _safe_str(trace.get("finished_at"))
        or _safe_str(_safe_dict(final_evt or last_evt).get("ts"))
    )
    latest_event_id = (
        _safe_str(trace.get("latest_event_id"))
        or _event_id(last_evt)
    )
    result_event_id = _safe_str(trace.get("result_event_id"))

    return {
        "type": "room_run_replay",
        "room_id": _safe_str(room_id),
        "requested_run_id": requested_run_id,
        "requested_run_found": requested_run_found,
        "derived_run_id": derived_run_id,
        "run_id": effective_run_id,
        "status": status,
        "result_state": result_state,
        "result_view": _safe_str(summary_core.get("result_view")) or _safe_str(trace.get("result_view")) or "replay",
        "started_at": started_at,
        "finished_at": finished_at,
        "latest_event_id": latest_event_id,
        "result_event_id": result_event_id,
        "event_count": len(run_items),
        "event_types": sorted(list({_event_type(x) for x in run_items if _event_type(x)})),
        "available_runs": available_runs,
        "plan_event_id": _event_id(plan_evt),
        "supervisor_event_id": _event_id(supervisor_evt),
        "final_event_id": _event_id(final_evt),
        "delegate_total": delegate_total,
        "delegate_roles": delegate_roles,
        "plan_summary": _summary_from_event(plan_evt),
        "final_summary": _summary_from_event(final_evt),
        "final_response": final_response,
        "current_phase": _safe_str(summary_core.get("current_phase")),
        "supervisor_phase": _safe_str(summary_core.get("supervisor_phase")),
        "supervisor_fs_read_status": _safe_str(latest_fs_read.get("status")),
        "supervisor_notebook_read_status": _safe_str(latest_notebook_read.get("status")),
        "supervisor_notebook_write_status": _safe_str(latest_notebook_write.get("status")),
        "provider_trace": _safe_dict(summary_core.get("provider_trace")),
        "grant_trace": _safe_dict(summary_core.get("grant_trace")),
        "network_trace": _safe_dict(summary_core.get("network_trace")),
        "consume_trace": _safe_dict(summary_core.get("consume_trace")),
        "replay_recoverable": bool(summary_core.get("replay_recoverable")),
        "remote_execution_may_have_completed": bool(
            summary_core.get("remote_execution_may_have_completed")
        ),
        "events": run_items,
        "phases": phases,
        "relations": relations,
        "tool_activity": tool_activity,
        "evidence": evidence_items,
        "audit": audit,
        "room_state_snapshot": room_state_snapshot,
        "trace": trace,
        "summary": {
            "run_id": effective_run_id,
            "status": status,
            "result_state": result_state,
            "current_phase": _safe_str(summary_core.get("current_phase")),
            "supervisor_phase": _safe_str(summary_core.get("supervisor_phase")),
            "plan_summary": _summary_from_event(plan_evt),
            "final_summary": _summary_from_event(final_evt),
            "final_response": final_response,
            "delegate_roles": delegate_roles,
            "delegate_total": delegate_total,
        },
    }


__all__ = [
    "_build_room_run_replay",
]
