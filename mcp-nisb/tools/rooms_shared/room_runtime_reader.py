from __future__ import annotations

from typing import Any, Dict, List, Optional

from .room_result_envelope import _coerce_result_state_token
from .room_state_normalizer import _safe_dict, _safe_list, _safe_str


_RUNTIME_EVENT_TYPES = {
    "room.plan",
    "room.delegate",
    "room.route",
    "room.supervisor",
    "room.message",
    "room.final",
    "room.abort",
    "room.aborted",
    "room.error",
}

_SUPERVISOR_PHASES = {
    "planning",
    "grounding",
    "synthesizing",
    "writeback",
    "completed",
}


def _payload_of_event(evt: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not isinstance(evt, dict):
        return {}

    for key in ("payload", "data", "result_payload"):
        value = evt.get(key)
        if isinstance(value, dict):
            return value

    return {}


def _event_id(evt: Optional[Dict[str, Any]]) -> str:
    return _safe_str(_safe_dict(evt).get("id"))


def _same_event(a: Optional[Dict[str, Any]], b: Optional[Dict[str, Any]]) -> bool:
    aid = _event_id(a)
    bid = _event_id(b)
    return bool(aid and bid and aid == bid)


def _event_type(evt: Optional[Dict[str, Any]]) -> str:
    src = _safe_dict(evt)
    payload = _payload_of_event(src)

    return _safe_str(
        src.get("type")
        or src.get("event_type")
        or src.get("item_type")
        or payload.get("type")
    )


def _event_run_id(evt: Optional[Dict[str, Any]]) -> str:
    src = _safe_dict(evt)
    payload = _payload_of_event(src)

    return _safe_str(
        src.get("run_id")
        or payload.get("run_id")
        or payload.get("runtime_run_id")
        or payload.get("current_run_id")
        or src.get("current_run_id")
    )


def _normalize_status_token(value: Any) -> str:
    token = _safe_str(value).strip().lower()
    if token in {"ok", "success", "succeeded"}:
        return "success"
    if token in {"warning", "partial_success", "partial_error"}:
        return "warning"
    if token in {"error", "failed", "fail"}:
        return "error"
    if token in {"aborted", "abort"}:
        return "aborted"
    if token in {"disabled", "denied", "running", "finished"}:
        return token
    return token


def _result_doc_of_event(evt: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    payload = _payload_of_event(evt)
    result_doc = _safe_dict(payload.get("result"))
    if result_doc:
        return {
            **payload,
            **result_doc,
        }
    return payload


def _extract_event_result_state(evt: Optional[Dict[str, Any]]) -> str:
    payload = _payload_of_event(evt)
    result_doc = _result_doc_of_event(evt)

    explicit = _coerce_result_state_token(
        result_doc.get("result_state") or payload.get("result_state")
    )
    if explicit:
        return explicit

    for candidate in (
        result_doc.get("status"),
        payload.get("status"),
        _safe_dict(evt).get("status"),
    ):
        normalized = _coerce_result_state_token(candidate)
        if normalized:
            return normalized

    evt_type = _event_type(evt)
    phase = _event_runtime_stage(evt)

    if evt_type == "room.final" or phase == "final":
        return "success"
    if evt_type in {"room.abort", "room.aborted"} or phase == "abort":
        return "consumed"
    if evt_type == "room.error" or phase == "error":
        return "error"
    return ""


def _is_runtime_event(evt: Optional[Dict[str, Any]]) -> bool:
    evt_type = _event_type(evt)
    if evt_type not in _RUNTIME_EVENT_TYPES:
        return False

    run_id = _event_run_id(evt)
    if not run_id:
        return False

    if evt_type == "room.message":
        payload = _payload_of_event(evt)
        sender_type = _safe_str(
            payload.get("sender_type") or payload.get("sender")
        ).lower()

        if sender_type == "user":
            return False

        return True

    return True


def _sort_events_asc(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    items = [row for row in rows if isinstance(row, dict)]
    items.sort(key=lambda x: (str(x.get("ts") or ""), str(x.get("id") or "")))
    return items


def _derive_latest_runtime_run_id(rows: List[Dict[str, Any]]) -> str:
    ordered = _sort_events_asc(rows)
    for row in reversed(ordered):
        if not _is_runtime_event(row):
            continue
        run_id = _event_run_id(row)
        if run_id:
            return run_id
    return ""


def _collect_runtime_run_ids(rows: List[Dict[str, Any]]) -> List[str]:
    ordered = _sort_events_asc(rows)
    seen = set()
    out: List[str] = []
    for row in reversed(ordered):
        if not _is_runtime_event(row):
            continue
        run_id = _event_run_id(row)
        if not run_id or run_id in seen:
            continue
        seen.add(run_id)
        out.append(run_id)
    return out


def _filter_runtime_items(
    rows: List[Dict[str, Any]],
    *,
    run_id: str = "",
) -> List[Dict[str, Any]]:
    selected: List[Dict[str, Any]] = []
    for row in _sort_events_asc(rows):
        if not _is_runtime_event(row):
            continue
        if run_id and _event_run_id(row) != run_id:
            continue
        selected.append(row)
    return selected


def _slice_after_event_id(
    rows: List[Dict[str, Any]],
    *,
    after_event_id: str = "",
) -> Dict[str, Any]:
    if not after_event_id:
        return {"items": rows, "after_event_found": True}

    start_idx = 0
    found = False
    for idx, row in enumerate(rows):
        if _event_id(row) == after_event_id:
            start_idx = idx + 1
            found = True
            break

    if found:
        return {"items": rows[start_idx:], "after_event_found": True}
    return {"items": rows, "after_event_found": False}


def _supervisor_phase_of_event(evt: Optional[Dict[str, Any]]) -> str:
    if _event_type(evt) != "room.supervisor":
        return ""
    payload = _payload_of_event(evt)
    phase = _safe_str(payload.get("phase")).lower()
    return phase if phase in _SUPERVISOR_PHASES else ""


def _event_runtime_stage(evt: Optional[Dict[str, Any]]) -> str:
    evt_type = _event_type(evt)
    payload = _payload_of_event(evt)

    if evt_type == "room.plan":
        return "planning"
    if evt_type == "room.delegate":
        return "delegate"
    if evt_type == "room.route":
        return "route"
    if evt_type == "room.supervisor":
        return _supervisor_phase_of_event(evt) or "supervisor"
    if evt_type == "room.final":
        return "final"
    if evt_type in {"room.abort", "room.aborted"}:
        return "abort"
    if evt_type == "room.error":
        return "error"
    if evt_type == "room.message":
        if payload.get("aborted"):
            return "abort"
        if _normalize_status_token(payload.get("status")) == "error":
            return "error"
        sender_type = _safe_str(payload.get("sender_type")).lower()
        if sender_type == "role":
            return "worker"
        if sender_type == "ai" and _safe_str(payload.get("role_name")).lower() == "supervisor":
            return "supervisor"
        return "message"
    return "runtime"


def _extract_supervisor_audit_sections(evt: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    payload = _payload_of_event(evt)
    fs_read = _safe_dict(payload.get("supervisor_fs_read"))
    notebook_read = _safe_dict(payload.get("supervisor_notebook_read"))
    notebook_write = _safe_dict(payload.get("supervisor_notebook_write"))
    memory_read = _safe_dict(payload.get("supervisor_memory_read"))
    memory_resume = _safe_dict(payload.get("supervisor_memory_resume"))
    memory_write = _safe_dict(payload.get("supervisor_memory_write"))

    extra_sections: List[Dict[str, Any]] = []
    for key in ("supervisor_fs_actions", "supervisor_file_actions", "supervisor_actions"):
        rows = payload.get(key)
        if isinstance(rows, list):
            extra_sections = [row for row in rows if isinstance(row, dict)]
            break

    return {
        "supervisor_fs_read": fs_read,
        "supervisor_notebook_read": notebook_read,
        "supervisor_notebook_write": notebook_write,
        "supervisor_memory_read": memory_read,
        "supervisor_memory_resume": memory_resume,
        "supervisor_memory_write": memory_write,
        "supervisor_fs_actions": extra_sections,
    }


def _flatten_supervisor_nested_tool_activity(evt: Optional[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    sections = _extract_supervisor_audit_sections(evt)
    tool_calls: List[Dict[str, Any]] = []
    tool_results: List[Dict[str, Any]] = []

    for key in (
        "supervisor_fs_read",
        "supervisor_notebook_read",
        "supervisor_notebook_write",
        "supervisor_memory_read",
        "supervisor_memory_resume",
        "supervisor_memory_write",
    ):
        section = _safe_dict(sections.get(key))
        for row in _safe_list(section.get("tool_calls")):
            if isinstance(row, dict):
                tool_calls.append(row)
        for row in _safe_list(section.get("tool_results")):
            if isinstance(row, dict):
                tool_results.append(row)

    for action in _safe_list(sections.get("supervisor_fs_actions")):
        action_obj = _safe_dict(action)
        for row in _safe_list(action_obj.get("tool_calls")):
            if isinstance(row, dict):
                tool_calls.append(row)
        for row in _safe_list(action_obj.get("tool_results")):
            if isinstance(row, dict):
                tool_results.append(row)

    return {"tool_calls": tool_calls, "tool_results": tool_results}


def _event_has_supervisor_nested_audit(evt: Optional[Dict[str, Any]]) -> bool:
    sections = _extract_supervisor_audit_sections(evt)
    if _safe_dict(sections.get("supervisor_fs_read")):
        return True
    if _safe_dict(sections.get("supervisor_notebook_read")):
        return True
    if _safe_dict(sections.get("supervisor_notebook_write")):
        return True
    if _safe_dict(sections.get("supervisor_memory_read")):
        return True
    if _safe_dict(sections.get("supervisor_memory_resume")):
        return True
    if _safe_dict(sections.get("supervisor_memory_write")):
        return True
    if _safe_list(sections.get("supervisor_fs_actions")):
        return True
    return False


def _extract_event_status(evt: Optional[Dict[str, Any]]) -> str:
    src = _safe_dict(evt)
    payload = _payload_of_event(src)

    explicit = _normalize_status_token(
        payload.get("status") or src.get("status")
    )
    if explicit:
        return explicit

    success_value = payload.get("success")
    if success_value is None:
        success_value = src.get("success")

    evt_type = _event_type(evt)
    if evt_type == "room.final":
        if success_value is False:
            return "error"
        return "success"
    if evt_type in {"room.abort", "room.aborted"}:
        return "aborted"
    if evt_type == "room.error":
        return "error"

    return ""


def _derive_latest_runtime_stage(
    rows: List[Dict[str, Any]],
    *,
    run_id: str = "",
) -> str:
    items = _filter_runtime_items(rows, run_id=run_id) if run_id else _filter_runtime_items(rows)
    for row in reversed(items):
        stage = _event_runtime_stage(row)
        if stage:
            return stage
    return ""


def _build_recent_runtime_summary(
    rows: List[Dict[str, Any]],
    *,
    run_id: str = "",
) -> Dict[str, Any]:
    effective_run_id = _safe_str(run_id) or _derive_latest_runtime_run_id(rows)
    items = _filter_runtime_items(rows, run_id=effective_run_id) if effective_run_id else []

    latest = items[-1] if items else None
    latest_payload = _payload_of_event(latest)

    final_evt = None
    for row in reversed(items):
        if _event_type(row) == "room.final":
            final_evt = row
            break

    supervisor_evt = None
    for row in reversed(items):
        if _event_type(row) == "room.supervisor":
            supervisor_evt = row
            break

    plan_evt = None
    for row in items:
        if _event_type(row) == "room.plan":
            plan_evt = row
            break

    final_payload = _payload_of_event(final_evt)
    supervisor_payload = _payload_of_event(supervisor_evt)
    plan_payload = _payload_of_event(plan_evt)
    sections = _extract_supervisor_audit_sections(final_evt or supervisor_evt or latest)

    fs_read = _safe_dict(sections.get("supervisor_fs_read"))
    notebook_read = _safe_dict(sections.get("supervisor_notebook_read"))
    notebook_write = _safe_dict(sections.get("supervisor_notebook_write"))
    memory_read = _safe_dict(sections.get("supervisor_memory_read"))
    memory_resume = _safe_dict(sections.get("supervisor_memory_resume"))
    memory_write = _safe_dict(sections.get("supervisor_memory_write"))

    delegate_events = [row for row in items if _event_type(row) == "room.delegate"]
    role_names: List[str] = []
    seen = set()
    for row in delegate_events:
        payload = _payload_of_event(row)
        name = _safe_str(
            payload.get("target_role_name")
            or payload.get("role_name")
            or payload.get("role_id")
        )
        if not name or name in seen:
            continue
        seen.add(name)
        role_names.append(name)

    result_evt = None
    for row in reversed(items):
        if _extract_event_result_state(row):
            result_evt = row
            break

    result_payload = _result_doc_of_event(result_evt)
    final_response = _safe_str(
        result_payload.get("final_response")
        or final_payload.get("final_response")
        or final_payload.get("response")
        or final_payload.get("content")
    )
    latest_message = _safe_str(
        final_response
        or supervisor_payload.get("response")
        or supervisor_payload.get("summary")
        or latest_payload.get("message")
        or latest_payload.get("response")
        or latest_payload.get("summary")
        or latest_payload.get("content")
    )

    return {
        "run_id": effective_run_id,
        "event_count": len(items),
        "latest_event_id": _event_id(latest),
        "latest_event_type": _event_type(latest),
        "current_stage": _event_runtime_stage(latest),
        "status": _extract_event_status(final_evt or latest),
        "result_state": _extract_event_result_state(result_evt),
        "supervisor_phase": _supervisor_phase_of_event(supervisor_evt),
        "delegate_count": len(delegate_events),
        "role_names": role_names,
        "final_event_id": _event_id(final_evt),
        "result_event_id": _event_id(result_evt),
        "supervisor_event_id": _event_id(supervisor_evt),
        "supervisor_fs_read_status": _safe_str(fs_read.get("status")),
        "supervisor_notebook_read_status": _safe_str(notebook_read.get("status")),
        "supervisor_notebook_write_status": _safe_str(notebook_write.get("status")),
        "supervisor_memory_read_status": _safe_str(memory_read.get("status")),
        "supervisor_memory_resume_decision": _safe_str(memory_resume.get("decision")),
        "supervisor_memory_write_status": _safe_str(memory_write.get("status")),
        "latest_message": latest_message,
        "final_response": final_response,
        "plan_summary": _safe_str(
            final_payload.get("plan_summary")
            or supervisor_payload.get("plan_summary")
            or plan_payload.get("plan_summary")
            or plan_payload.get("summary")
            or plan_payload.get("content")
            or plan_payload.get("response")
            or plan_payload.get("message")
        ),
    }


__all__ = [
    "_RUNTIME_EVENT_TYPES",
    "_build_recent_runtime_summary",
    "_collect_runtime_run_ids",
    "_derive_latest_runtime_run_id",
    "_derive_latest_runtime_stage",
    "_event_has_supervisor_nested_audit",
    "_event_id",
    "_event_run_id",
    "_event_runtime_stage",
    "_event_type",
    "_extract_event_result_state",
    "_extract_event_status",
    "_extract_supervisor_audit_sections",
    "_filter_runtime_items",
    "_flatten_supervisor_nested_tool_activity",
    "_is_runtime_event",
    "_payload_of_event",
    "_result_doc_of_event",
    "_same_event",
    "_slice_after_event_id",
    "_sort_events_asc",
    "_supervisor_phase_of_event",
]
