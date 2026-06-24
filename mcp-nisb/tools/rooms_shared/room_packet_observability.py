from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from .room_contracts import as_bool


_GENERIC_TOOL_TYPES = {
    "tool_call",
    "tool_result",
    "call",
    "result",
    "function_call",
    "function_result",
}

_TOOL_NAME_ALIASES = {
    "supervisor_fs_read": "nisb_supervisor_fs_read",
    "supervisor_notebook_write": "nisb_supervisor_notebook_write",
    "room_supervisor_fs_read": "nisb_supervisor_fs_read",
    "room_supervisor_fs_probe": "nisb_supervisor_fs_read",
    "room_supervisor_notebook_write": "nisb_supervisor_notebook_write",
    "room_supervisor_fs_bridge": "nisb_supervisor_fs_read",
    "fs_read": "nisb_supervisor_fs_read",
    "notebook_write": "nisb_supervisor_notebook_write",
    "dir_tree": "nisb_dir_tree",
    "fs_snapshot": "nisb_fs_snapshot",
    "file_read": "nisb_file_read",
    "file_read_multiple": "nisb_file_read_multiple",
    "file_create": "nisb_file_create",
    "file_update": "nisb_file_update",
    "fs_audit_tail": "nisb_fs_audit_tail",
    "fs_restore_backup": "nisb_fs_restore_backup",
    "supervisor_memory_read": "nisb_supervisor_memory_read",
    "supervisor_memory_resume": "nisb_supervisor_memory_resume",
    "supervisor_memory_write": "nisb_supervisor_memory_write",
    "room_supervisor_memory_read": "nisb_supervisor_memory_read",
    "room_supervisor_memory_resume": "nisb_supervisor_memory_resume",
    "room_supervisor_memory_write": "nisb_supervisor_memory_write",
}

_ALLOWED_RESULT_STATES = {
    "success",
    "denied",
    "timeout",
    "late_complete",
    "consumed",
    "error",
}


def _safe_str(v: Any, default: str = "") -> str:
    if v is None:
        return default
    s = str(v).strip()
    return s if s else default


def _safe_list(v: Any) -> List[Any]:
    return v if isinstance(v, list) else []


def _safe_dict(v: Any) -> Dict[str, Any]:
    return v if isinstance(v, dict) else {}


def _safe_int(v: Any, default: int = -1) -> int:
    try:
        return int(v)
    except Exception:
        return default


def _normalize_tool_name_candidate(value: Any) -> str:
    raw = _safe_str(value)
    if not raw:
        return ""

    lower = raw.lower()
    if lower in _GENERIC_TOOL_TYPES:
        return ""
    if lower in _TOOL_NAME_ALIASES:
        return _TOOL_NAME_ALIASES[lower]
    return raw


def _collect_tool_candidate_objects(record: Any) -> List[Dict[str, Any]]:
    root = _safe_dict(record)
    if not root:
        return []

    out: List[Dict[str, Any]] = []

    def push(value: Any) -> None:
        obj = _safe_dict(value)
        if obj:
            out.append(obj)

    push(root)
    push(root.get("meta"))
    push(root.get("data"))
    push(root.get("payload"))
    push(root.get("result"))
    push(root.get("value"))
    push(root.get("request"))
    push(root.get("response"))
    push(root.get("function"))
    push(root.get("tool_call"))
    push(root.get("related_tool_call"))
    push(root.get("parent_tool_call"))

    meta_obj = _safe_dict(root.get("meta"))
    push(meta_obj.get("function"))
    push(meta_obj.get("tool_call"))

    payload_obj = _safe_dict(root.get("payload"))
    push(payload_obj.get("function"))
    push(payload_obj.get("tool_call"))
    push(payload_obj.get("related_tool_call"))
    push(payload_obj.get("parent_tool_call"))

    result_obj = _safe_dict(root.get("result"))
    push(result_obj.get("function"))
    push(result_obj.get("tool_call"))

    data_obj = _safe_dict(root.get("data"))
    push(data_obj.get("function"))
    push(data_obj.get("tool_call"))

    return out


def _extract_tool_name(record: Any) -> str:
    candidates = _collect_tool_candidate_objects(record)
    if not candidates:
        return ""

    for obj in candidates:
        for key in (
            "name",
            "tool_name",
            "toolName",
            "tool",
            "function_name",
            "functionName",
            "call_name",
            "callName",
            "source_tool_name",
            "sourceToolName",
        ):
            value = _normalize_tool_name_candidate(obj.get(key))
            if value:
                return value

        for key in ("type", "kind", "source_type", "sourceType"):
            value = _normalize_tool_name_candidate(obj.get(key))
            if value:
                return value

    return ""


def _extract_tool_call_ref(record: Any) -> str:
    candidates = _collect_tool_candidate_objects(record)
    if not candidates:
        return ""

    for obj in candidates:
        for key in (
            "tool_call_id",
            "toolCallId",
            "call_id",
            "callId",
            "tool_use_id",
            "toolUseId",
            "related_tool_call_id",
            "relatedToolCallId",
            "parent_tool_call_id",
            "parentToolCallId",
            "correlation_id",
            "correlationId",
            "trace_id",
            "traceId",
            "request_id",
            "requestId",
        ):
            value = _safe_str(obj.get(key))
            if value:
                return value

    return ""


def _extract_tool_call_identity(record: Any) -> str:
    candidates = _collect_tool_candidate_objects(record)
    if not candidates:
        return ""

    for obj in candidates:
        for key in (
            "tool_call_id",
            "toolCallId",
            "call_id",
            "callId",
            "tool_use_id",
            "toolUseId",
            "id",
            "correlation_id",
            "correlationId",
            "trace_id",
            "traceId",
            "request_id",
            "requestId",
        ):
            value = _safe_str(obj.get(key))
            if value:
                return value

    return ""


def _extract_tool_index(record: Any) -> int:
    candidates = _collect_tool_candidate_objects(record)
    if not candidates:
        return -1

    for obj in candidates:
        for key in ("index", "tool_index", "toolIndex", "tool_call_index", "toolCallIndex"):
            value = _safe_int(obj.get(key), -1)
            if value >= 0:
                return value

    return -1


def _normalize_tool_call_record(record: Any, index: int) -> Any:
    if not isinstance(record, dict):
        return record

    out = dict(record)
    name = _extract_tool_name(out)
    call_identity = _extract_tool_call_identity(out)
    item_index = _extract_tool_index(out)
    if item_index < 0:
        item_index = index

    if name:
        out["name"] = name
        out["tool_name"] = name
    if call_identity:
        out.setdefault("tool_call_id", call_identity)
    out.setdefault("index", item_index)
    return out


def _normalize_tool_result_record(
    record: Any,
    index: int,
    call_name_by_ref: Dict[str, str],
    call_name_by_index: Dict[int, str],
) -> Any:
    if not isinstance(record, dict):
        return record

    out = dict(record)
    explicit_name = _extract_tool_name(out)
    call_ref = _extract_tool_call_ref(out)
    item_index = _extract_tool_index(out)
    if item_index < 0:
        item_index = index

    linked_name = ""
    if call_ref and call_ref in call_name_by_ref:
        linked_name = _safe_str(call_name_by_ref.get(call_ref))
    if not linked_name and item_index in call_name_by_index:
        linked_name = _safe_str(call_name_by_index.get(item_index))

    final_name = linked_name or explicit_name
    if final_name:
        out["name"] = final_name
        out["tool_name"] = final_name
    if call_ref:
        out.setdefault("tool_call_id", call_ref)
    out.setdefault("index", item_index)
    return out


def _normalize_tool_activity_lists(
    tool_calls: Optional[List[Any]],
    tool_results: Optional[List[Any]],
) -> Tuple[List[Any], List[Any]]:
    raw_calls = _safe_list(tool_calls)
    raw_results = _safe_list(tool_results)

    normalized_calls: List[Any] = []
    call_name_by_ref: Dict[str, str] = {}
    call_name_by_index: Dict[int, str] = {}

    for idx, item in enumerate(raw_calls):
        normalized = _normalize_tool_call_record(item, idx)
        normalized_calls.append(normalized)
        if isinstance(normalized, dict):
            name = _safe_str(normalized.get("name") or normalized.get("tool_name"))
            ref = _safe_str(normalized.get("tool_call_id"))
            item_index = _safe_int(normalized.get("index"), -1)
            if ref and name:
                call_name_by_ref[ref] = name
            if item_index >= 0 and name:
                call_name_by_index[item_index] = name

    normalized_results: List[Any] = []
    for idx, item in enumerate(raw_results):
        normalized_results.append(
            _normalize_tool_result_record(
                item,
                idx,
                call_name_by_ref,
                call_name_by_index,
            )
        )

    return normalized_calls, normalized_results


def _normalize_supervisor_memory_checkpoint(value: Any) -> Dict[str, Any]:
    src = _safe_dict(value)
    return {
        "stage": _safe_str(src.get("stage")),
        "last_step": _safe_str(src.get("last_step")),
        "summary": _safe_str(src.get("summary")),
        "question": _safe_str(src.get("question")),
        "plan_summary": _safe_str(src.get("plan_summary")),
        "recovery_hint": _safe_str(src.get("recovery_hint")),
        "open_questions": [item for item in _safe_list(src.get("open_questions")) if _safe_str(item)],
        "next_actions": [item for item in _safe_list(src.get("next_actions")) if _safe_str(item)],
        "evidence_refs": [item for item in _safe_list(src.get("evidence_refs")) if _safe_str(item)],
    }


def _normalize_supervisor_memory_resume_doc(value: Any) -> Dict[str, Any]:
    src = _safe_dict(value)
    return {
        "resume_token": _safe_str(src.get("resume_token")),
        "resume_ready": as_bool(src.get("resume_ready"), False),
        "resume_reason": _safe_str(src.get("resume_reason")),
        "invalidated_by": _safe_str(src.get("invalidated_by")),
    }


def _normalize_supervisor_memory_read_result(value: Any) -> Dict[str, Any]:
    src = _safe_dict(value)
    if not src:
        return {}

    return {
        "enabled": as_bool(src.get("enabled"), True),
        "status": _safe_str(src.get("status")),
        "message": _safe_str(src.get("message")),
        "reason_code": _safe_str(src.get("reason_code")),
        "relative_path": _safe_str(src.get("relative_path")),
        "source_kind": _safe_str(src.get("source_kind")),
        "recorded_at": _safe_str(src.get("recorded_at")),
        "version": max(1, _safe_int(src.get("version"), 1)),
        "last_run_id": _safe_str(src.get("last_run_id")),
        "last_supervisor_event_id": _safe_str(src.get("last_supervisor_event_id")),
        "status_value": _safe_str(src.get("status_value")),
        "checkpoint": _normalize_supervisor_memory_checkpoint(src.get("checkpoint")),
        "resume": _normalize_supervisor_memory_resume_doc(src.get("resume")),
    }


def _normalize_supervisor_memory_resume_result(value: Any) -> Dict[str, Any]:
    src = _safe_dict(value)
    if not src:
        return {}

    return {
        "enabled": as_bool(src.get("enabled"), True),
        "status": _safe_str(src.get("status")),
        "decision": _safe_str(src.get("decision")),
        "reason": _safe_str(src.get("reason")),
        "resume_ready": as_bool(src.get("resume_ready"), False),
        "relative_path": _safe_str(src.get("relative_path")),
        "checkpoint_stage": _safe_str(src.get("checkpoint_stage")),
        "checkpoint_summary": _safe_str(src.get("checkpoint_summary")),
        "recovery_hint": _safe_str(src.get("recovery_hint")),
        "recorded_at": _safe_str(src.get("recorded_at")),
    }


def _normalize_supervisor_memory_write_result(value: Any) -> Dict[str, Any]:
    src = _safe_dict(value)
    if not src:
        return {}

    return {
        "enabled": as_bool(src.get("enabled"), True),
        "status": _safe_str(src.get("status")),
        "message": _safe_str(src.get("message")),
        "reason_code": _safe_str(src.get("reason_code")),
        "relative_path": _safe_str(src.get("relative_path")),
        "bytes_written": max(0, _safe_int(src.get("bytes_written"), 0)),
        "recorded_at": _safe_str(src.get("recorded_at")),
        "checkpoint_stage": _safe_str(src.get("checkpoint_stage")),
        "checkpoint_summary": _safe_str(src.get("checkpoint_summary")),
        "resume_decision": _safe_str(src.get("resume_decision")),
        "resume_reason": _safe_str(src.get("resume_reason")),
        "memory_version": max(1, _safe_int(src.get("memory_version"), 1)),
        "source_kind": _safe_str(src.get("source_kind")),
    }


def _build_supervisor_memory_payload(
    *,
    supervisor_memory_read: Optional[Dict[str, Any]] = None,
    supervisor_memory_resume: Optional[Dict[str, Any]] = None,
    supervisor_memory_write: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    read_row = _normalize_supervisor_memory_read_result(supervisor_memory_read)
    resume_row = _normalize_supervisor_memory_resume_result(supervisor_memory_resume)
    write_row = _normalize_supervisor_memory_write_result(supervisor_memory_write)

    payload: Dict[str, Any] = {}
    if read_row:
        payload["read"] = read_row
    if resume_row:
        payload["resume"] = resume_row
    if write_row:
        payload["write"] = write_row
    return payload


def _build_supervisor_memory_tool_results(
    *,
    supervisor_memory_read: Optional[Dict[str, Any]] = None,
    supervisor_memory_resume: Optional[Dict[str, Any]] = None,
    supervisor_memory_write: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []

    read_row = _normalize_supervisor_memory_read_result(supervisor_memory_read)
    if read_row:
        checkpoint = _safe_dict(read_row.get("checkpoint"))
        resume_doc = _safe_dict(read_row.get("resume"))
        out.append(
            {
                "type": "supervisor_memory_read",
                "name": "nisb_supervisor_memory_read",
                "tool_name": "nisb_supervisor_memory_read",
                "status": _safe_str(read_row.get("status")),
                "reason_code": _safe_str(read_row.get("reason_code")),
                "relative_path": _safe_str(read_row.get("relative_path")),
                "source_kind": _safe_str(read_row.get("source_kind")),
                "checkpoint_stage": _safe_str(checkpoint.get("stage")),
                "checkpoint_summary": _safe_str(checkpoint.get("summary")),
                "resume_ready": as_bool(resume_doc.get("resume_ready"), False),
                "resume_reason": _safe_str(resume_doc.get("resume_reason")),
                "recorded_at": _safe_str(read_row.get("recorded_at")),
            }
        )

    resume_row = _normalize_supervisor_memory_resume_result(supervisor_memory_resume)
    if resume_row:
        out.append(
            {
                "type": "supervisor_memory_resume",
                "name": "nisb_supervisor_memory_resume",
                "tool_name": "nisb_supervisor_memory_resume",
                "status": _safe_str(resume_row.get("status")),
                "decision": _safe_str(resume_row.get("decision")),
                "reason": _safe_str(resume_row.get("reason")),
                "relative_path": _safe_str(resume_row.get("relative_path")),
                "checkpoint_stage": _safe_str(resume_row.get("checkpoint_stage")),
                "checkpoint_summary": _safe_str(resume_row.get("checkpoint_summary")),
                "recovery_hint": _safe_str(resume_row.get("recovery_hint")),
                "recorded_at": _safe_str(resume_row.get("recorded_at")),
            }
        )

    write_row = _normalize_supervisor_memory_write_result(supervisor_memory_write)
    if write_row:
        out.append(
            {
                "type": "supervisor_memory_write",
                "name": "nisb_supervisor_memory_write",
                "tool_name": "nisb_supervisor_memory_write",
                "status": _safe_str(write_row.get("status")),
                "reason_code": _safe_str(write_row.get("reason_code")),
                "relative_path": _safe_str(write_row.get("relative_path")),
                "bytes_written": max(0, _safe_int(write_row.get("bytes_written"), 0)),
                "checkpoint_stage": _safe_str(write_row.get("checkpoint_stage")),
                "checkpoint_summary": _safe_str(write_row.get("checkpoint_summary")),
                "resume_decision": _safe_str(write_row.get("resume_decision")),
                "resume_reason": _safe_str(write_row.get("resume_reason")),
                "source_kind": _safe_str(write_row.get("source_kind")),
                "recorded_at": _safe_str(write_row.get("recorded_at")),
            }
        )

    return out


def _tool_result_signature(record: Any) -> Tuple[Any, ...]:
    obj = _safe_dict(record)
    if not obj:
        return ("__raw__", str(record))

    return (
        _safe_str(obj.get("type")),
        _safe_str(obj.get("name")),
        _safe_str(obj.get("tool_name")),
        _safe_str(obj.get("relative_path")),
        _safe_str(obj.get("status")),
        _safe_str(obj.get("reason_code")),
        _safe_str(obj.get("decision")),
        _safe_str(obj.get("reason")),
        _safe_str(obj.get("checkpoint_stage")),
        _safe_str(obj.get("resume_decision")),
        _safe_int(obj.get("bytes_written"), -1),
    )


def _merge_tool_results(
    base_results: Optional[List[Any]],
    extra_results: Optional[List[Any]],
) -> List[Any]:
    out: List[Any] = []
    seen = set()

    for item in _safe_list(base_results) + _safe_list(extra_results):
        if isinstance(item, dict):
            signature = _tool_result_signature(item)
            if signature in seen:
                continue
            seen.add(signature)
        out.append(item)

    return out


def _runtime_snapshot_payload_from_row(row: Dict[str, Any]) -> Dict[str, Any]:
    snapshot = dict(row)
    snapshot.pop("type", None)
    return _safe_dict(snapshot)


def _find_runtime_control_snapshot(value: Any) -> Dict[str, Any]:
    latest: Dict[str, Any] = {}

    def visit(node: Any) -> None:
        nonlocal latest

        if isinstance(node, dict):
            node_type = _safe_str(node.get("type")).lower()

            if node_type == "runtime_control_snapshot":
                candidate = _runtime_snapshot_payload_from_row(node)
                if candidate:
                    latest = candidate

            direct_snapshot = _safe_dict(node.get("runtime_control_snapshot"))
            if direct_snapshot:
                latest = direct_snapshot

            event_obj = _safe_dict(node.get("event"))
            if event_obj:
                visit(event_obj)

            payload_obj = _safe_dict(node.get("payload"))
            if payload_obj:
                payload_snapshot = _safe_dict(payload_obj.get("runtime_control_snapshot"))
                if payload_snapshot:
                    latest = payload_snapshot

                payload_tool_results = _safe_list(payload_obj.get("tool_results"))
                for item in payload_tool_results:
                    visit(item)

            for item in _safe_list(node.get("events")):
                visit(item)

            for item in _safe_list(node.get("tool_results")):
                visit(item)

        elif isinstance(node, list):
            for item in node:
                visit(item)

    visit(value)
    return latest


def _resolve_runtime_control_snapshot(
    *,
    runtime_control_snapshot: Optional[Dict[str, Any]] = None,
    tool_results: Optional[List[Any]] = None,
) -> Dict[str, Any]:
    explicit_snapshot = _safe_dict(runtime_control_snapshot)
    if explicit_snapshot:
        return explicit_snapshot
    return _find_runtime_control_snapshot(_safe_list(tool_results))


def _normalize_result_state(value: Any) -> str:
    token = _safe_str(value).lower().replace("-", "_")
    if token in _ALLOWED_RESULT_STATES:
        return token
    if token in {"ok", "finished", "completed"}:
        return "success"
    if token in {"permission_denied", "forbidden"}:
        return "denied"
    if token in {"timed_out"}:
        return "timeout"
    if token in {"latecomplete"}:
        return "late_complete"
    if token in {"failed", "failure"}:
        return "error"
    if token in {"abort", "aborted"}:
        return "consumed"
    return ""


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


def _extract_result_container(value: Any) -> Dict[str, Any]:
    root = _safe_dict(value)
    result_obj = _safe_dict(root.get("result"))
    if result_obj:
        return {
            **root,
            **result_obj,
        }
    return root


def _build_result_observability(
    value: Any,
    *,
    fallback_status: str = "",
    fallback_result_state: str = "",
) -> Dict[str, Any]:
    src = _extract_result_container(value)

    result_state = _normalize_result_state(
        src.get("result_state") or fallback_result_state or src.get("status") or fallback_status
    )
    status = _safe_str(src.get("status") or fallback_status)
    result_view = _safe_str(src.get("result_view")) or ("final_only" if result_state else "")
    final_response = _safe_str(
        src.get("final_response")
        or src.get("response")
        or src.get("content")
        or src.get("summary")
        or src.get("message")
    )

    provider_trace = _normalize_trace_doc(src.get("provider_trace"))
    grant_trace = _normalize_trace_doc(src.get("grant_trace"))
    network_trace = _normalize_trace_doc(src.get("network_trace"))
    consume_trace = _normalize_trace_doc(src.get("consume_trace"))

    replay_recoverable = as_bool(src.get("replay_recoverable"), False)
    remote_execution_may_have_completed = as_bool(
        src.get("remote_execution_may_have_completed"),
        False,
    )

    if not network_trace and result_state in {"timeout", "late_complete"}:
        network_trace = {
            "status": result_state,
        }

    if not consume_trace and result_state == "consumed":
        consume_trace = {
            "status": "consumed",
        }

    return {
        "status": status,
        "result_state": result_state,
        "result_view": result_view,
        "final_response": final_response,
        "provider_trace": provider_trace,
        "grant_trace": grant_trace,
        "network_trace": network_trace,
        "consume_trace": consume_trace,
        "replay_recoverable": replay_recoverable,
        "remote_execution_may_have_completed": remote_execution_may_have_completed,
    }


def _merge_observability_traces(*parts: Any) -> Dict[str, Any]:
    provider_trace: Dict[str, Any] = {}
    grant_trace: Dict[str, Any] = {}
    network_trace: Dict[str, Any] = {}
    consume_trace: Dict[str, Any] = {}
    status = ""
    result_state = ""
    result_view = ""
    final_response = ""
    replay_recoverable = False
    remote_execution_may_have_completed = False

    for part in parts:
        row = _safe_dict(part)
        if not row:
            continue

        if not status:
            status = _safe_str(row.get("status"))
        if not result_state:
            result_state = _normalize_result_state(row.get("result_state"))
        if not result_view:
            result_view = _safe_str(row.get("result_view"))
        if not final_response:
            final_response = _safe_str(row.get("final_response"))

        provider_trace = provider_trace or _normalize_trace_doc(row.get("provider_trace"))
        grant_trace = grant_trace or _normalize_trace_doc(row.get("grant_trace"))
        network_trace = network_trace or _normalize_trace_doc(row.get("network_trace"))
        consume_trace = consume_trace or _normalize_trace_doc(row.get("consume_trace"))

        replay_recoverable = replay_recoverable or as_bool(row.get("replay_recoverable"), False)
        remote_execution_may_have_completed = (
            remote_execution_may_have_completed
            or as_bool(row.get("remote_execution_may_have_completed"), False)
        )

    return {
        "status": status,
        "result_state": result_state,
        "result_view": result_view,
        "final_response": final_response,
        "provider_trace": provider_trace,
        "grant_trace": grant_trace,
        "network_trace": network_trace,
        "consume_trace": consume_trace,
        "replay_recoverable": replay_recoverable,
        "remote_execution_may_have_completed": remote_execution_may_have_completed,
    }


__all__ = [
    "_build_result_observability",
    "_build_supervisor_memory_payload",
    "_build_supervisor_memory_tool_results",
    "_collect_tool_candidate_objects",
    "_extract_tool_call_identity",
    "_extract_tool_call_ref",
    "_extract_tool_index",
    "_extract_tool_name",
    "_find_runtime_control_snapshot",
    "_merge_observability_traces",
    "_merge_tool_results",
    "_normalize_result_state",
    "_normalize_supervisor_memory_checkpoint",
    "_normalize_supervisor_memory_read_result",
    "_normalize_supervisor_memory_resume_doc",
    "_normalize_supervisor_memory_resume_result",
    "_normalize_supervisor_memory_write_result",
    "_normalize_tool_activity_lists",
    "_normalize_tool_call_record",
    "_normalize_tool_name_candidate",
    "_normalize_tool_result_record",
    "_normalize_trace_doc",
    "_resolve_runtime_control_snapshot",
]
