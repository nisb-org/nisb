from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from .room_runtime_reader import (
    _build_recent_runtime_summary,
    _event_id,
    _event_runtime_stage,
    _event_type,
    _extract_event_result_state,
    _extract_event_status,
    _extract_supervisor_audit_sections,
    _filter_runtime_items,
    _flatten_supervisor_nested_tool_activity,
    _payload_of_event,
)
from .room_state_normalizer import _safe_dict, _safe_list, _safe_str


def _first_event_of_type(items: List[Dict[str, Any]], event_type: str) -> Optional[Dict[str, Any]]:
    for item in items:
        if _event_type(item) == event_type:
            return item
    return None


def _last_event_of_type(items: List[Dict[str, Any]], event_type: str) -> Optional[Dict[str, Any]]:
    for item in reversed(items):
        if _event_type(item) == event_type:
            return item
    return None


def _phase_from_event(evt: Optional[Dict[str, Any]]) -> str:
    return _event_runtime_stage(evt) or "runtime"


def _title_from_phase(phase: str, actor_label: str = "") -> str:
    if phase == "planning":
        return "Planning"
    if phase == "delegate":
        return f"Delegate · {actor_label}" if actor_label else "Delegate"
    if phase == "route":
        return f"Route · {actor_label}" if actor_label else "Route"
    if phase == "worker":
        return actor_label or "Worker"
    if phase == "grounding":
        return "Grounding"
    if phase == "synthesizing":
        return "Supervisor"
    if phase == "writeback":
        return "Writeback"
    if phase == "completed":
        return "Completed"
    if phase == "final":
        return "Final"
    if phase == "abort":
        return "Abort"
    if phase == "error":
        return "Error"
    return "Runtime"


def _actor_from_event(evt: Optional[Dict[str, Any]]) -> str:
    payload = _payload_of_event(evt)
    evt_type = _event_type(evt)

    role_name = _safe_str(payload.get("role_name"))
    target_role_name = _safe_str(payload.get("target_role_name"))
    sender = _safe_str(payload.get("sender"))
    sender_name = _safe_str(payload.get("sender_name"))

    if evt_type == "room.plan":
        return "Supervisor"
    if evt_type == "room.delegate":
        return target_role_name or role_name or "Delegate"
    if evt_type == "room.route":
        return target_role_name or role_name or "Router"
    if evt_type == "room.supervisor":
        return role_name or "Supervisor"
    if evt_type == "room.final":
        return role_name or sender_name or sender or "Supervisor"
    if evt_type in {"room.abort", "room.aborted", "room.error"}:
        return role_name or sender_name or sender or "System"
    return role_name or sender_name or sender or "Worker"


def _summary_from_event(evt: Optional[Dict[str, Any]]) -> str:
    payload = _payload_of_event(evt)
    evt_type = _event_type(evt)
    phase = _phase_from_event(evt)

    if evt_type == "room.plan":
        return _safe_str(
            payload.get("plan_summary")
            or payload.get("summary")
            or payload.get("content")
            or payload.get("response")
            or payload.get("message")
        )

    if evt_type == "room.delegate":
        target_name = _safe_str(payload.get("target_role_name") or payload.get("role_name"))
        idx = _safe_str(payload.get("delegate_index"))
        total = _safe_str(payload.get("delegate_total"))
        if target_name and idx and total:
            return f"{target_name} ({idx}/{total})"
        if target_name:
            return target_name
        return _safe_str(payload.get("message") or payload.get("summary"))

    if evt_type == "room.route":
        return _safe_str(
            payload.get("target_role_name")
            or payload.get("target_role_id")
            or payload.get("route_mode")
            or payload.get("reply_mode")
        )

    if evt_type == "room.supervisor":
        notebook_read = _safe_dict(payload.get("supervisor_notebook_read"))

        if phase == "writeback":
            notebook = _safe_dict(payload.get("supervisor_notebook_write"))
            return _safe_str(
                notebook.get("message")
                or payload.get("summary")
                or payload.get("message")
                or "Supervisor 正在写入 notebook"
            )

        if notebook_read:
            return _safe_str(
                notebook_read.get("message")
                or notebook_read.get("reason")
                or payload.get("summary")
                or payload.get("message")
                or "Supervisor 正在读取 notebook"
            )

        if phase == "grounding":
            fs_read = _safe_dict(payload.get("supervisor_fs_read"))
            return _safe_str(
                fs_read.get("message")
                or fs_read.get("reason")
                or payload.get("summary")
                or payload.get("message")
                or "Supervisor 正在读取目录上下文"
            )

        return _safe_str(
            payload.get("summary")
            or payload.get("plan_summary")
            or payload.get("content")
            or payload.get("response")
            or payload.get("message")
        )

    if evt_type == "room.final":
        return _safe_str(
            payload.get("final_response")
            or payload.get("response")
            or payload.get("content")
            or payload.get("summary")
            or payload.get("message")
        )

    return _safe_str(
        payload.get("content")
        or payload.get("response")
        or payload.get("summary")
        or payload.get("message")
    )


def _event_status(evt: Optional[Dict[str, Any]]) -> str:
    return _extract_event_status(evt)


def _normalize_trace_doc(value: Any) -> Dict[str, Any]:
    src = _safe_dict(value)
    if not src:
        return {}
    out: Dict[str, Any] = {}
    for key, raw in src.items():
        if raw is None:
            continue
        if isinstance(raw, (str, int, float, bool)):
            out[key] = raw
        elif isinstance(raw, list):
            out[key] = list(raw)
        elif isinstance(raw, dict):
            out[key] = dict(raw)
    return out


def _extract_result_source(payload: Dict[str, Any]) -> Dict[str, Any]:
    result_doc = _safe_dict(payload.get("result"))
    if result_doc:
        return {
            **payload,
            **result_doc,
        }
    return payload


def _build_event_trace(evt: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    src = _safe_dict(evt)
    return {
        "event_id": _safe_str(src.get("id")),
        "trigger_event_id": _safe_str(src.get("trigger_event_id")),
        "run_id": _safe_str(src.get("run_id")),
        "ts": _safe_str(src.get("ts")),
        "type": _event_type(src),
        "phase": _phase_from_event(src),
        "status": _event_status(src),
        "result_state": _extract_event_result_state(src),
    }


def _meta_chips_from_event(evt: Optional[Dict[str, Any]]) -> List[str]:
    payload = _payload_of_event(evt)
    chips: List[str] = []

    status = _safe_str(payload.get("status"))
    if status:
        chips.append(status)

    result_state = _extract_event_result_state(evt)
    if result_state:
        chips.append(result_state)

    phase = _phase_from_event(evt)
    if phase:
        chips.append(phase)

    role_name = _safe_str(payload.get("role_name") or payload.get("target_role_name"))
    if role_name:
        chips.append(role_name)

    delegate_index = _safe_str(payload.get("delegate_index"))
    delegate_total = _safe_str(payload.get("delegate_total"))
    if delegate_index and delegate_total:
        chips.append(f"{delegate_index}/{delegate_total}")

    sender_type = _safe_str(payload.get("sender_type"))
    if sender_type:
        chips.append(sender_type)

    evt_type = _event_type(evt)
    if evt_type:
        chips.append(evt_type)

    out: List[str] = []
    seen = set()
    for chip in chips:
        value = _safe_str(chip)
        if not value or value in seen:
            continue
        seen.add(value)
        out.append(value)
    return out


def _tool_identity(row: Dict[str, Any]) -> Tuple[str, str, str]:
    obj = _safe_dict(row)
    return (
        _safe_str(obj.get("tool_call_id") or obj.get("call_id") or obj.get("request_id")),
        _safe_str(obj.get("tool_name") or obj.get("name") or obj.get("type")),
        _safe_str(obj.get("type") or obj.get("status")),
    )


def _merge_unique_dict_rows(*parts: Any) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    seen = set()
    for part in parts:
        for row in _safe_list(part):
            if not isinstance(row, dict):
                continue
            ident = _tool_identity(row)
            fallback = str(sorted(row.items()))
            key = ident if any(ident) else ("", "", fallback)
            if key in seen:
                continue
            seen.add(key)
            out.append(row)
    return out


def _result_state_from_event(evt: Optional[Dict[str, Any]]) -> str:
    return _extract_event_result_state(evt)


def _result_view_from_event(evt: Optional[Dict[str, Any]]) -> str:
    payload = _payload_of_event(evt)
    source = _extract_result_source(payload)
    explicit = _safe_str(source.get("result_view") or payload.get("result_view"))
    if explicit:
        return explicit
    if _extract_event_result_state(evt):
        return "replay"
    return ""


def _trace_doc_from_event(evt: Optional[Dict[str, Any]], key: str) -> Dict[str, Any]:
    payload = _payload_of_event(evt)
    source = _extract_result_source(payload)
    return _normalize_trace_doc(source.get(key) or payload.get(key))


def _bool_flag_from_event(evt: Optional[Dict[str, Any]], key: str) -> bool:
    payload = _payload_of_event(evt)
    source = _extract_result_source(payload)
    return bool(source.get(key) or payload.get(key))


def _build_result_projection(evt: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    payload = _payload_of_event(evt)
    source = _extract_result_source(payload)
    result_state = _extract_event_result_state(evt)
    result_view = _result_view_from_event(evt)
    final_response = _safe_str(
        source.get("final_response")
        or payload.get("final_response")
        or source.get("response")
        or payload.get("response")
        or source.get("content")
        or payload.get("content")
    )
    summary = _safe_str(
        source.get("summary")
        or payload.get("summary")
        or payload.get("message")
        or final_response
    )

    return {
        "result_state": result_state,
        "result_view": result_view,
        "final_response": final_response,
        "summary": summary,
        "provider_trace": _trace_doc_from_event(evt, "provider_trace"),
        "grant_trace": _trace_doc_from_event(evt, "grant_trace"),
        "network_trace": _trace_doc_from_event(evt, "network_trace"),
        "consume_trace": _trace_doc_from_event(evt, "consume_trace"),
        "replay_recoverable": _bool_flag_from_event(evt, "replay_recoverable"),
        "remote_execution_may_have_completed": _bool_flag_from_event(
            evt,
            "remote_execution_may_have_completed",
        ),
    }


def _latest_result_event(items: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    for item in reversed(items):
        if _extract_event_result_state(item):
            return item
    return None


def _run_result_state_from_items(items: List[Dict[str, Any]]) -> str:
    latest = _latest_result_event(items)
    return _extract_event_result_state(latest)


def _latest_supervisor_sections_from_event(evt: Optional[Dict[str, Any]]) -> Dict[str, Dict[str, Any] | List[Any]]:
    payload = _payload_of_event(evt)
    sections = _extract_supervisor_audit_sections(evt)

    return {
        "supervisor_fs_read": _safe_dict(
            sections.get("supervisor_fs_read") or payload.get("supervisor_fs_read")
        ),
        "supervisor_notebook_read": _safe_dict(
            sections.get("supervisor_notebook_read") or payload.get("supervisor_notebook_read")
        ),
        "supervisor_notebook_write": _safe_dict(
            sections.get("supervisor_notebook_write") or payload.get("supervisor_notebook_write")
        ),
        "supervisor_memory_read": _safe_dict(
            sections.get("supervisor_memory_read") or payload.get("supervisor_memory_read")
        ),
        "supervisor_memory_resume": _safe_dict(
            sections.get("supervisor_memory_resume") or payload.get("supervisor_memory_resume")
        ),
        "supervisor_memory_write": _safe_dict(
            sections.get("supervisor_memory_write") or payload.get("supervisor_memory_write")
        ),
        "supervisor_fs_actions": _safe_list(sections.get("supervisor_fs_actions")),
    }


def _latest_supervisor_sections_from_items(items: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any] | List[Any]]:
    last_evt = items[-1] if items else None
    return _latest_supervisor_sections_from_event(last_evt)


def _collect_delegate_roles(items: List[Dict[str, Any]]) -> List[str]:
    out: List[str] = []
    seen = set()
    for evt in items:
        if _event_type(evt) != "room.delegate":
            continue
        payload = _payload_of_event(evt)
        name = _safe_str(payload.get("target_role_name") or payload.get("role_name"))
        if not name or name in seen:
            continue
        seen.add(name)
        out.append(name)
    return out


def _build_run_summary_core(items: List[Dict[str, Any]], *, run_id: str = "") -> Dict[str, Any]:
    latest_summary = _build_recent_runtime_summary(items, run_id=run_id) if items else {}
    latest_result_evt = _latest_result_event(items)
    latest_result_projection = _build_result_projection(latest_result_evt)
    latest_sections = _latest_supervisor_sections_from_items(items)

    latest_fs_read = _safe_dict(latest_sections.get("supervisor_fs_read"))
    latest_notebook_read = _safe_dict(latest_sections.get("supervisor_notebook_read"))
    latest_notebook_write = _safe_dict(latest_sections.get("supervisor_notebook_write"))
    latest_memory_read = _safe_dict(latest_sections.get("supervisor_memory_read"))
    latest_memory_resume = _safe_dict(latest_sections.get("supervisor_memory_resume"))
    latest_memory_write = _safe_dict(latest_sections.get("supervisor_memory_write"))

    return {
        "status": _run_status_from_items(items),
        "result_state": _run_result_state_from_items(items),
        "result_view": _safe_str(latest_result_projection.get("result_view")),
        "final_response": _safe_str(latest_result_projection.get("final_response")),
        "provider_trace": _safe_dict(latest_result_projection.get("provider_trace")),
        "grant_trace": _safe_dict(latest_result_projection.get("grant_trace")),
        "network_trace": _safe_dict(latest_result_projection.get("network_trace")),
        "consume_trace": _safe_dict(latest_result_projection.get("consume_trace")),
        "replay_recoverable": bool(latest_result_projection.get("replay_recoverable")),
        "remote_execution_may_have_completed": bool(
            latest_result_projection.get("remote_execution_may_have_completed")
        ),
        "current_phase": _safe_str(latest_summary.get("current_stage")),
        "supervisor_phase": _safe_str(latest_summary.get("supervisor_phase")),
        "supervisor_fs_read_status": _safe_str(latest_fs_read.get("status")),
        "supervisor_notebook_read_status": _safe_str(latest_notebook_read.get("status")),
        "supervisor_notebook_write_status": _safe_str(latest_notebook_write.get("status")),
        "supervisor_memory_read_status": _safe_str(latest_memory_read.get("status")),
        "supervisor_memory_resume_decision": _safe_str(latest_memory_resume.get("decision")),
        "supervisor_memory_write_status": _safe_str(latest_memory_write.get("status")),
    }


def _normalize_phase_item(
    evt: Dict[str, Any],
    *,
    include_tool_activity: bool,
    include_evidence: bool,
) -> Dict[str, Any]:
    payload = _payload_of_event(evt)
    phase = _phase_from_event(evt)
    actor_label = _actor_from_event(evt)
    result_projection = _build_result_projection(evt)

    citations = _safe_list(payload.get("citations")) if include_evidence else []
    evidence_tools = _safe_list(payload.get("evidence_tools")) if include_evidence else []
    evidence_result = _safe_dict(payload.get("evidence_result")) if include_evidence else {}
    evidence_query = _safe_str(payload.get("evidence_query")) if include_evidence else ""

    top_level_tool_calls = _safe_list(payload.get("tool_calls")) if include_tool_activity else []
    top_level_tool_results = _safe_list(payload.get("tool_results")) if include_tool_activity else []

    nested_activity = (
        _flatten_supervisor_nested_tool_activity(evt)
        if include_tool_activity
        else {"tool_calls": [], "tool_results": []}
    )
    merged_tool_calls = _merge_unique_dict_rows(top_level_tool_calls, nested_activity.get("tool_calls"))
    merged_tool_results = _merge_unique_dict_rows(top_level_tool_results, nested_activity.get("tool_results"))

    supervisor_sections = _latest_supervisor_sections_from_event(evt)
    supervisor_fs_read = _safe_dict(supervisor_sections.get("supervisor_fs_read"))
    supervisor_notebook_read = _safe_dict(supervisor_sections.get("supervisor_notebook_read"))
    supervisor_notebook_write = _safe_dict(supervisor_sections.get("supervisor_notebook_write"))
    supervisor_memory_read = _safe_dict(supervisor_sections.get("supervisor_memory_read"))
    supervisor_memory_resume = _safe_dict(supervisor_sections.get("supervisor_memory_resume"))
    supervisor_memory_write = _safe_dict(supervisor_sections.get("supervisor_memory_write"))
    supervisor_fs_actions = _safe_list(supervisor_sections.get("supervisor_fs_actions"))

    trace = _build_event_trace(evt)

    return {
        "event_id": trace["event_id"],
        "trigger_event_id": trace["trigger_event_id"],
        "run_id": trace["run_id"],
        "ts": trace["ts"],
        "type": trace["type"],
        "phase": trace["phase"],
        "visible": phase != "route",
        "title": _title_from_phase(phase, actor_label),
        "actor_label": actor_label,
        "role_id": _safe_str(payload.get("role_id") or payload.get("target_role_id")),
        "role_name": _safe_str(payload.get("role_name") or payload.get("target_role_name")),
        "sender": _safe_str(payload.get("sender")),
        "sender_type": _safe_str(payload.get("sender_type")),
        "status": trace["status"],
        "summary": _summary_from_event(evt),
        "message": _safe_str(payload.get("message")),
        "meta_chips": _meta_chips_from_event(evt),
        "trace": trace,
        "tool_calls": merged_tool_calls,
        "tool_results": merged_tool_results,
        "top_level_tool_calls": top_level_tool_calls,
        "top_level_tool_results": top_level_tool_results,
        "nested_tool_calls": _safe_list(nested_activity.get("tool_calls")),
        "nested_tool_results": _safe_list(nested_activity.get("tool_results")),
        "has_tool_activity": bool(merged_tool_calls or merged_tool_results),
        "supervisor_fs_read": supervisor_fs_read,
        "supervisor_notebook_read": supervisor_notebook_read,
        "supervisor_notebook_write": supervisor_notebook_write,
        "supervisor_fs_actions": supervisor_fs_actions,
        "has_supervisor_audit": bool(
            supervisor_fs_read
            or supervisor_notebook_read
            or supervisor_notebook_write
            or supervisor_memory_read
            or supervisor_memory_resume
            or supervisor_memory_write
            or supervisor_fs_actions
        ),
        "citations": citations,
        "evidence_query": evidence_query,
        "evidence_tools": evidence_tools,
        "evidence_result": evidence_result,
        "has_evidence": bool(citations or evidence_tools or evidence_result or evidence_query),
        "aborted": bool(payload.get("aborted")),
        "is_result_event": bool(result_projection.get("result_state")) or phase in {"final", "abort", "error"},
        "result_state": _safe_str(result_projection.get("result_state")),
        "result_view": _safe_str(result_projection.get("result_view")),
        "final_response": _safe_str(result_projection.get("final_response")),
        "provider_trace": _safe_dict(result_projection.get("provider_trace")),
        "grant_trace": _safe_dict(result_projection.get("grant_trace")),
        "network_trace": _safe_dict(result_projection.get("network_trace")),
        "consume_trace": _safe_dict(result_projection.get("consume_trace")),
        "replay_recoverable": bool(result_projection.get("replay_recoverable")),
        "remote_execution_may_have_completed": bool(
            result_projection.get("remote_execution_may_have_completed")
        ),
        "supervisor_memory_read": supervisor_memory_read,
        "supervisor_memory_resume": supervisor_memory_resume,
        "supervisor_memory_write": supervisor_memory_write,
    }


def _build_tool_activity(phases: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for phase in phases:
        tool_calls = _safe_list(phase.get("tool_calls"))
        tool_results = _safe_list(phase.get("tool_results"))
        supervisor_fs_read = _safe_dict(phase.get("supervisor_fs_read"))
        supervisor_notebook_read = _safe_dict(phase.get("supervisor_notebook_read"))
        supervisor_notebook_write = _safe_dict(phase.get("supervisor_notebook_write"))
        supervisor_memory_read = _safe_dict(phase.get("supervisor_memory_read"))
        supervisor_memory_resume = _safe_dict(phase.get("supervisor_memory_resume"))
        supervisor_memory_write = _safe_dict(phase.get("supervisor_memory_write"))
        supervisor_fs_actions = _safe_list(phase.get("supervisor_fs_actions"))

        if (
            not tool_calls
            and not tool_results
            and not supervisor_fs_read
            and not supervisor_notebook_read
            and not supervisor_notebook_write
            and not supervisor_memory_read
            and not supervisor_memory_resume
            and not supervisor_memory_write
            and not supervisor_fs_actions
        ):
            continue

        out.append(
            {
                "event_id": _safe_str(phase.get("event_id")),
                "phase": _safe_str(phase.get("phase")),
                "actor_label": _safe_str(phase.get("actor_label")),
                "trace": _safe_dict(phase.get("trace")),
                "tool_calls": tool_calls,
                "tool_results": tool_results,
                "supervisor_fs_read": supervisor_fs_read,
                "supervisor_notebook_read": supervisor_notebook_read,
                "supervisor_notebook_write": supervisor_notebook_write,
                "supervisor_fs_actions": supervisor_fs_actions,
                "supervisor_memory_read": supervisor_memory_read,
                "supervisor_memory_resume": supervisor_memory_resume,
                "supervisor_memory_write": supervisor_memory_write,
            }
        )
    return out


def _build_evidence_items(phases: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for phase in phases:
        if not phase.get("has_evidence"):
            continue
        out.append(
            {
                "event_id": _safe_str(phase.get("event_id")),
                "phase": _safe_str(phase.get("phase")),
                "actor_label": _safe_str(phase.get("actor_label")),
                "trace": _safe_dict(phase.get("trace")),
                "evidence_query": _safe_str(phase.get("evidence_query")),
                "evidence_tools": _safe_list(phase.get("evidence_tools")),
                "evidence_result": _safe_dict(phase.get("evidence_result")),
                "citations": _safe_list(phase.get("citations")),
            }
        )
    return out


def _run_status_from_items(items: List[Dict[str, Any]]) -> str:
    if not items:
        return "empty"

    last = items[-1]
    last_phase = _phase_from_event(last)

    if last_phase == "final":
        return "finished"
    if last_phase == "abort":
        return "aborted"
    if last_phase == "error":
        return "error"

    if _last_event_of_type(items, "room.final"):
        return "finished"

    return "running"


def _build_relations(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for item in items:
        trigger_event_id = _safe_str(item.get("trigger_event_id"))
        if not trigger_event_id:
            continue
        out.append(
            {
                "event_id": _event_id(item),
                "trigger_event_id": trigger_event_id,
                "type": _event_type(item),
                "phase": _phase_from_event(item),
            }
        )
    return out


def _build_run_trace(run_id: str, items: List[Dict[str, Any]]) -> Dict[str, Any]:
    first_evt = items[0] if items else None
    last_evt = items[-1] if items else None
    latest_result_evt = _latest_result_event(items)
    latest_result_projection = _build_result_projection(latest_result_evt)

    return {
        "run_id": _safe_str(run_id),
        "status": _run_status_from_items(items),
        "result_state": _run_result_state_from_items(items),
        "result_view": _safe_str(latest_result_projection.get("result_view")),
        "started_at": _safe_str(_safe_dict(first_evt).get("ts")),
        "finished_at": _safe_str(_safe_dict(last_evt).get("ts")),
        "latest_event_id": _event_id(last_evt),
        "result_event_id": _event_id(latest_result_evt),
        "event_count": len(items),
        "final_response": _safe_str(latest_result_projection.get("final_response")),
        "provider_trace": _safe_dict(latest_result_projection.get("provider_trace")),
        "grant_trace": _safe_dict(latest_result_projection.get("grant_trace")),
        "network_trace": _safe_dict(latest_result_projection.get("network_trace")),
        "consume_trace": _safe_dict(latest_result_projection.get("consume_trace")),
        "replay_recoverable": bool(latest_result_projection.get("replay_recoverable")),
        "remote_execution_may_have_completed": bool(
            latest_result_projection.get("remote_execution_may_have_completed")
        ),
    }


def _build_run_overview(rows: List[Dict[str, Any]], run_id: str) -> Dict[str, Any]:
    items = _filter_runtime_items(rows, run_id=run_id)

    plan_evt = _first_event_of_type(items, "room.plan")
    supervisor_evt = _last_event_of_type(items, "room.supervisor")
    final_evt = _last_event_of_type(items, "room.final")
    latest_result_evt = _latest_result_event(items)
    summary_core = _build_run_summary_core(items, run_id=run_id)

    delegate_evts = [x for x in items if _event_type(x) == "room.delegate"]
    delegate_roles = _collect_delegate_roles(items)

    first_evt = items[0] if items else None
    last_evt = items[-1] if items else None

    return {
        "run_id": _safe_str(run_id),
        "status": _safe_str(summary_core.get("status")),
        "result_state": _safe_str(summary_core.get("result_state")),
        "result_view": _safe_str(summary_core.get("result_view")),
        "started_at": _safe_str(_safe_dict(first_evt).get("ts")),
        "finished_at": _safe_str(_safe_dict(final_evt or last_evt).get("ts")),
        "latest_event_id": _event_id(last_evt),
        "result_event_id": _event_id(latest_result_evt),
        "event_count": len(items),
        "plan_event_id": _event_id(plan_evt),
        "supervisor_event_id": _event_id(supervisor_evt),
        "final_event_id": _event_id(final_evt),
        "delegate_total": len(delegate_evts),
        "delegate_roles": delegate_roles,
        "plan_summary": _summary_from_event(plan_evt),
        "final_summary": _summary_from_event(final_evt),
        "final_response": _safe_str(summary_core.get("final_response")),
        "current_phase": _safe_str(summary_core.get("current_phase")),
        "supervisor_phase": _safe_str(summary_core.get("supervisor_phase")),
        "supervisor_fs_read_status": _safe_str(summary_core.get("supervisor_fs_read_status")),
        "supervisor_notebook_read_status": _safe_str(summary_core.get("supervisor_notebook_read_status")),
        "supervisor_notebook_write_status": _safe_str(summary_core.get("supervisor_notebook_write_status")),
        "supervisor_memory_read_status": _safe_str(summary_core.get("supervisor_memory_read_status")),
        "supervisor_memory_resume_decision": _safe_str(summary_core.get("supervisor_memory_resume_decision")),
        "supervisor_memory_write_status": _safe_str(summary_core.get("supervisor_memory_write_status")),
        "provider_trace": _safe_dict(summary_core.get("provider_trace")),
        "grant_trace": _safe_dict(summary_core.get("grant_trace")),
        "network_trace": _safe_dict(summary_core.get("network_trace")),
        "consume_trace": _safe_dict(summary_core.get("consume_trace")),
        "replay_recoverable": bool(summary_core.get("replay_recoverable")),
        "remote_execution_may_have_completed": bool(
            summary_core.get("remote_execution_may_have_completed")
        ),
        "trace": _build_run_trace(run_id, items),
    }


def _build_runtime_events_result(
    *,
    room_id: str,
    runtime_items: List[Dict[str, Any]],
    items: List[Dict[str, Any]],
    run_id: str,
    requested_run_id: str,
    derived_run_id: str,
    state_current_run_id: str,
    state_current_run_status: str,
    include_all_runs: bool,
    after_event_id: str,
    after_event_found: bool,
    latest_event_id: str,
    limit: int,
    order: str,
    has_more: bool,
    event_types: List[str],
) -> Dict[str, Any]:
    summary_core = _build_run_summary_core(runtime_items, run_id=run_id)
    delegate_roles = _collect_delegate_roles(runtime_items)

    return {
        "room_id": room_id,
        "run_id": run_id,
        "requested_run_id": requested_run_id,
        "derived_run_id": derived_run_id,
        "state_current_run_id": state_current_run_id,
        "state_current_run_status": state_current_run_status,
        "include_all_runs": include_all_runs,
        "after_event_id": after_event_id,
        "after_event_found": after_event_found,
        "latest_event_id": latest_event_id,
        "limit": limit,
        "order": order,
        "returned_count": len(items),
        "has_more": has_more,
        "event_types": event_types,
        "status": _safe_str(summary_core.get("status")),
        "result_state": _safe_str(summary_core.get("result_state")),
        "result_view": _safe_str(summary_core.get("result_view")),
        "final_response": _safe_str(summary_core.get("final_response")),
        "provider_trace": _safe_dict(summary_core.get("provider_trace")),
        "grant_trace": _safe_dict(summary_core.get("grant_trace")),
        "network_trace": _safe_dict(summary_core.get("network_trace")),
        "consume_trace": _safe_dict(summary_core.get("consume_trace")),
        "replay_recoverable": bool(summary_core.get("replay_recoverable")),
        "remote_execution_may_have_completed": bool(
            summary_core.get("remote_execution_may_have_completed")
        ),
        "items": items,
        "trace": _build_run_trace(run_id, runtime_items),
        "summary": {
            "run_status": _safe_str(summary_core.get("status")),
            "result_state": _safe_str(summary_core.get("result_state")),
            "current_phase": _safe_str(summary_core.get("current_phase")),
            "supervisor_phase": _safe_str(summary_core.get("supervisor_phase")),
            "delegate_roles": delegate_roles,
            "delegate_total": len([x for x in runtime_items if _event_type(x) == "room.delegate"]),
            "final_response": _safe_str(summary_core.get("final_response")),
        },
    }


__all__ = [
    "_actor_from_event",
    "_build_evidence_items",
    "_build_event_trace",
    "_build_relations",
    "_build_result_projection",
    "_build_run_overview",
    "_build_run_summary_core",
    "_build_run_trace",
    "_build_runtime_events_result",
    "_build_tool_activity",
    "_collect_delegate_roles",
    "_event_status",
    "_first_event_of_type",
    "_last_event_of_type",
    "_latest_result_event",
    "_latest_supervisor_sections_from_items",
    "_merge_unique_dict_rows",
    "_meta_chips_from_event",
    "_normalize_phase_item",
    "_phase_from_event",
    "_result_state_from_event",
    "_run_result_state_from_items",
    "_run_status_from_items",
    "_summary_from_event",
    "_title_from_phase",
]
