from __future__ import annotations


from typing import Any, Dict, List, Optional


from .room_contracts import new_id, utc_iso
from .room_packet_builder import _build_room_message_payload, _empty_evidence_result
from .room_store import (
    append_room_event,
    load_room_events,
    load_state_doc,
    save_state_doc,
    touch_room_updated_at,
)



def _safe_str(v: Any, default: str = "") -> str:
    if v is None:
        return default
    s = str(v).strip()
    return s if s else default



def _safe_list(v: Any) -> List[Any]:
    return v if isinstance(v, list) else []



def _safe_dict(v: Any) -> Dict[str, Any]:
    return v if isinstance(v, dict) else {}



def _safe_int(v: Any, default: int = 0) -> int:
    try:
        return int(v)
    except Exception:
        return default



def _safe_bool(v: Any, default: bool = False) -> bool:
    if isinstance(v, bool):
        return v
    s = _safe_str(v).lower()
    if not s:
        return default
    if s in {"true", "1", "yes", "on"}:
        return True
    if s in {"false", "0", "no", "off"}:
        return False
    return default



def _build_run_id() -> str:
    return new_id("run")



def _load_room_state(room_id: str) -> Dict[str, Any]:
    return _safe_dict(load_state_doc(room_id))



def _save_room_state(room_id: str, state: Dict[str, Any]) -> Dict[str, Any]:
    out = _safe_dict(state)
    out["updated_at"] = utc_iso()
    save_state_doc(room_id, out)
    touch_room_updated_at(room_id)
    return out



def _set_room_state_patch(room_id: str, patch: Dict[str, Any]) -> Dict[str, Any]:
    rid = _safe_str(room_id)
    pp = _safe_dict(patch)
    if not rid or not pp:
        return pp


    state = _load_room_state(rid)
    state.update(pp)
    _save_room_state(rid, state)
    return pp



def _clear_run_state(room_id: str) -> Dict[str, Any]:
    return _set_room_state_patch(
        room_id,
        {
            "current_run_id": "",
            "current_run_status": "",
            "current_run_roles": [],
            "current_delegate_role_id": "",
            "current_delegate_role_name": "",
            "current_delegate_index": 0,
            "current_delegate_total": 0,
            "last_run_finished_at": utc_iso(),
        },
    )



def _update_room_last_message(room_id: str, event_or_id: Any) -> Dict[str, Any]:
    evt: Dict[str, Any] = {}


    if isinstance(event_or_id, dict):
        evt = _safe_dict(event_or_id)
    else:
        message_id = _safe_str(event_or_id)
        if not message_id:
            return {}


        rows = load_room_events(room_id)
        for row in reversed(_safe_list(rows)):
            item = _safe_dict(row)
            if _safe_str(item.get("id")) == message_id:
                evt = item
                break


        if not evt:
            return _set_room_state_patch(
                room_id,
                {
                    "last_message_id": message_id,
                    "last_message_at": utc_iso(),
                },
            )


    payload = _safe_dict(evt.get("payload"))
    content = _safe_str(
        payload.get("content")
        or payload.get("response")
        or payload.get("message")
    )
    sender = _safe_str(
        payload.get("sender")
        or payload.get("role_name")
        or payload.get("sender_name")
    )
    sender_type = _safe_str(payload.get("sender_type"))
    status = _safe_str(payload.get("status"))


    evt_type = _safe_str(evt.get("type"))
    if evt_type == "room.final":
        if not sender:
            sender = "Supervisor"
        if not sender_type:
            sender_type = "assistant"
        if not status:
            status = "success"
    elif evt_type == "room.supervisor":
        if not sender:
            sender = "Supervisor"
        if not sender_type:
            sender_type = "assistant"


    patch = {
        "last_message_id": _safe_str(evt.get("id")),
        "last_message_at": _safe_str(evt.get("ts"), utc_iso()),
        "last_message": content,
        "last_message_sender": sender,
        "last_message_sender_type": sender_type,
        "last_message_status": status,
    }
    return _set_room_state_patch(room_id, patch)



def _append_room_event(
    room_id: str,
    event_type: str,
    payload: Dict[str, Any],
    *,
    request_id: str = "",
    run_id: str = "",
    trigger_event_id: str = "",
) -> Dict[str, Any]:
    evt = {
        "id": new_id("evt"),
        "ts": utc_iso(),
        "type": _safe_str(event_type),
        "room_id": _safe_str(room_id),
        "request_id": _safe_str(request_id),
        "run_id": _safe_str(run_id),
        "trigger_event_id": _safe_str(trigger_event_id),
        "payload": _safe_dict(payload),
    }
    append_room_event(room_id, evt)
    touch_room_updated_at(room_id)
    return evt



def _build_dialog_lines(room_id: str, limit: int = 30) -> List[str]:
    rows = load_room_events(room_id)
    rows = [r for r in rows if isinstance(r, dict) and r.get("type") in {"room.message", "room.final"}]
    rows.sort(key=lambda x: str(x.get("ts") or ""))
    rows = rows[-max(1, int(limit)):]


    dialog: List[str] = []
    for e in rows:
        p = _safe_dict(e.get("payload"))
        sender = _safe_str(
            p.get("role_name")
            or p.get("sender")
            or p.get("sender_name")
            or e.get("type")
            or "unknown"
        )
        content = _safe_str(p.get("content") or p.get("response"))
        if not content:
            continue
        dialog.append(f"{sender}: {content}")
    return dialog



def _append_aborted_event(
    *,
    room_id: str,
    request_id: str = "",
    trigger_event_id: str = "",
    sender: str = "system",
    sender_type: str = "system",
    role_id: str = "",
    role_name: str = "",
    reason: str = "",
    model: str = "",
    mode_used: str = "",
    run_id: str = "",
) -> Dict[str, Any]:
    reason_code = _safe_str(reason, "aborted")

    visible_message = "reply aborted"
    visible_evidence_query = ""

    if reason_code.startswith("exception:"):
        visible_message = reason_code
    elif reason_code in {
        "provider_echo_response",
        "role_reply_error",
        "empty_role_reply",
        "aborted",
    }:
        visible_message = "reply aborted"

    payload = _build_room_message_payload(
        sender=sender,
        sender_type=sender_type,
        content=visible_message,
        model=model,
        mode_used=mode_used,
        role_id=role_id,
        role_name=role_name,
        status="error",
        message=visible_message,
        evidence_query=visible_evidence_query,
        evidence_tools=[],
        evidence_result=_empty_evidence_result(visible_evidence_query),
        citations=[],
        rss_evidence=[],
        market_evidence=[],
        tool_calls=[],
        tool_results=[
            {
                "type": "aborted_reason",
                "reason_code": reason_code,
            }
        ],
    )
    payload["response"] = visible_message
    payload["aborted"] = True
    payload["aborted_reason_code"] = reason_code

    evt = _append_room_event(
        room_id,
        "room.message",
        payload,
        request_id=request_id,
        run_id=run_id,
        trigger_event_id=trigger_event_id,
    )
    _update_room_last_message(room_id, evt)
    return evt



def _iter_tool_payload_candidates(value: Any) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    if isinstance(value, dict):
        out.append(value)
        for key in ("data", "result", "payload", "value"):
            inner = value.get(key)
            if isinstance(inner, dict):
                out.append(inner)
    return out



def _extract_tool_name(tool_calls: Any, tool_results: Any) -> str:
    for row in _safe_list(tool_calls):
        item = _safe_dict(row)
        name = _safe_str(item.get("tool_name") or item.get("name"))
        if name:
            return name
        fn = _safe_dict(item.get("function"))
        fn_name = _safe_str(fn.get("name"))
        if fn_name:
            return fn_name


    for row in _safe_list(tool_results):
        for candidate in _iter_tool_payload_candidates(row):
            name = _safe_str(candidate.get("tool_name") or candidate.get("name"))
            if name:
                return name


    return ""



def _extract_first_int(tool_results: Any, keys: List[str], default: int = 0) -> int:
    for row in _safe_list(tool_results):
        for candidate in _iter_tool_payload_candidates(row):
            for key in keys:
                if key in candidate:
                    return _safe_int(candidate.get(key), default)
    return default



def _extract_first_str(tool_results: Any, keys: List[str], default: str = "") -> str:
    for row in _safe_list(tool_results):
        for candidate in _iter_tool_payload_candidates(row):
            for key in keys:
                value = _safe_str(candidate.get(key))
                if value:
                    return value
    return default



def _extract_first_bool(tool_results: Any, keys: List[str], default: bool = False) -> bool:
    for row in _safe_list(tool_results):
        for candidate in _iter_tool_payload_candidates(row):
            for key in keys:
                if key not in candidate:
                    continue
                value = candidate.get(key)
                if isinstance(value, bool):
                    return value
                token = _safe_str(value).lower()
                if token in {"true", "1", "yes", "on"}:
                    return True
                if token in {"false", "0", "no", "off"}:
                    return False
    return default



def _entry_has_any(entry: Dict[str, Any]) -> bool:
    src = _safe_dict(entry)
    return bool(
        src.get("enabled")
        or _safe_str(src.get("status"))
        or _safe_str(src.get("reason"))
        or _safe_str(src.get("decision"))
        or _safe_str(src.get("focus_root"))
        or _safe_str(src.get("scope"))
        or _safe_str(src.get("message"))
        or _safe_str(src.get("relative_path"))
        or _safe_str(src.get("source_kind"))
        or _safe_int(src.get("version"), 0)
        or _safe_str(src.get("checkpoint_stage"))
        or _safe_str(src.get("checkpoint_summary"))
        or _safe_str(src.get("resume_reason"))
        or _safe_str(src.get("tool_name"))
        or _safe_list(src.get("tool_calls"))
        or _safe_list(src.get("tool_results"))
        or _safe_int(src.get("entries_count"), 0)
        or _safe_int(src.get("bytes_written"), 0)
        or _safe_str(src.get("at"))
    )



def _normalize_supervisor_audit_entry(
    value: Any,
    *,
    kind: str = "",
) -> Dict[str, Any]:
    src = _safe_dict(value)
    tool_calls = _safe_list(src.get("tool_calls"))
    tool_results = _safe_list(src.get("tool_results"))


    reason = _safe_str(src.get("reason") or src.get("reason_code"))
    if not reason:
        reason = _extract_first_str(tool_results, ["reason", "reason_code"])


    relative_path = _safe_str(src.get("relative_path"))
    if not relative_path:
        relative_path = _extract_first_str(tool_results, ["relative_path", "path", "filename"])


    actor_type = _safe_str(src.get("actor_type"))
    if not actor_type:
        actor_type = _extract_first_str(tool_results, ["actor_type"])


    actor_id = _safe_str(src.get("actor_id"))
    if not actor_id:
        actor_id = _extract_first_str(tool_results, ["actor_id"])


    skill_id = _safe_str(src.get("skill_id"))
    if not skill_id:
        skill_id = _extract_first_str(tool_results, ["skill_id"])


    delegated_from = _safe_str(src.get("delegated_from"))
    if not delegated_from:
        delegated_from = _extract_first_str(tool_results, ["delegated_from"])


    policy_status = _safe_str(src.get("policy_status"))
    if not policy_status:
        policy_status = _extract_first_str(tool_results, ["policy_status"])


    policy_reason_code = _safe_str(src.get("policy_reason_code"))
    if not policy_reason_code:
        policy_reason_code = _extract_first_str(tool_results, ["policy_reason_code", "reason_code"])


    policy_message = _safe_str(src.get("policy_message"))
    if not policy_message:
        policy_message = _extract_first_str(tool_results, ["policy_message"])


    policy_allowed = _safe_bool(src.get("policy_allowed"), False)
    if "policy_allowed" not in src:
        policy_allowed = _extract_first_bool(tool_results, ["policy_allowed", "allowed"], False)


    return {
        "kind": _safe_str(kind),
        "enabled": _safe_bool(src.get("enabled"), False),
        "status": _safe_str(src.get("status")),
        "reason": reason,
        "message": _safe_str(src.get("message")),
        "decision": _safe_str(src.get("decision")),
        "resume_ready": _safe_bool(src.get("resume_ready"), False),
        "focus_root": _safe_str(src.get("focus_root")),
        "scope": _safe_str(src.get("scope"), "minimal") if kind == "fs_read" else _safe_str(src.get("scope")),
        "relative_path": relative_path,
        "source_kind": _safe_str(src.get("source_kind")) or _extract_first_str(tool_results, ["source_kind"]),
        "version": _safe_int(src.get("version"), _extract_first_int(tool_results, ["version"], 0)),
        "checkpoint_stage": _safe_str(src.get("checkpoint_stage")),
        "checkpoint_summary": _safe_str(src.get("checkpoint_summary")),
        "recovery_hint": _safe_str(src.get("recovery_hint")),
        "resume_reason": _safe_str(src.get("resume_reason")),
        "resume_decision": _safe_str(src.get("resume_decision")),
        "tool_name": _safe_str(src.get("tool_name")) or _extract_tool_name(tool_calls, tool_results),
        "tool_calls": tool_calls,
        "tool_results": tool_results,
        "entries_count": _safe_int(
            src.get("entries_count"),
            _extract_first_int(tool_results, ["entries_count", "entry_count", "count"], 0),
        ),
        "bytes_written": _safe_int(
            src.get("bytes_written"),
            _extract_first_int(tool_results, ["bytes_written", "written_bytes", "bytes"], 0),
        ),
        "bytes_appended": _safe_int(
            src.get("bytes_appended"),
            _extract_first_int(tool_results, ["bytes_appended", "appended_bytes"], 0),
        ),
        "documents_count": _safe_int(
            src.get("documents_count"),
            _extract_first_int(tool_results, ["documents_count", "document_count", "count"], 0),
        ),
        "actor_type": actor_type,
        "actor_id": actor_id,
        "skill_id": skill_id,
        "delegated_from": delegated_from,
        "policy_allowed": policy_allowed,
        "policy_status": policy_status,
        "policy_reason_code": policy_reason_code,
        "policy_message": policy_message,
        "at": _safe_str(src.get("at") or src.get("recorded_at")),
    }



def _normalize_supervisor_memory_read_entry(value: Any) -> Dict[str, Any]:
    src = _safe_dict(value)
    checkpoint = _safe_dict(src.get("checkpoint"))
    resume = _safe_dict(src.get("resume"))
    base = _normalize_supervisor_audit_entry(src, kind="memory_read")
    base["reason"] = _safe_str(base.get("reason") or src.get("reason_code"))
    base["version"] = _safe_int(src.get("version"), _safe_int(base.get("version"), 0))
    base["checkpoint"] = {
        "stage": _safe_str(checkpoint.get("stage")),
        "summary": _safe_str(checkpoint.get("summary")),
        "last_step": _safe_str(checkpoint.get("last_step")),
        "recovery_hint": _safe_str(checkpoint.get("recovery_hint")),
    }
    base["resume"] = {
        "resume_ready": _safe_bool(resume.get("resume_ready"), _safe_bool(src.get("resume_ready"), False)),
        "resume_reason": _safe_str(resume.get("resume_reason") or src.get("resume_reason")),
        "invalidated_by": _safe_str(resume.get("invalidated_by")),
    }
    if not _safe_str(base.get("checkpoint_stage")):
        base["checkpoint_stage"] = _safe_str(checkpoint.get("stage"))
    if not _safe_str(base.get("checkpoint_summary")):
        base["checkpoint_summary"] = _safe_str(checkpoint.get("summary"))
    if not _safe_str(base.get("recovery_hint")):
        base["recovery_hint"] = _safe_str(checkpoint.get("recovery_hint"))
    if not _safe_bool(base.get("resume_ready"), False):
        base["resume_ready"] = _safe_bool(resume.get("resume_ready"), False)
    if not _safe_str(base.get("resume_reason")):
        base["resume_reason"] = _safe_str(resume.get("resume_reason"))
    return base


def _normalize_supervisor_memory_resume_entry(
    value: Any,
    *,
    fallback_read: Any = None,
    fallback_write: Any = None,
    fallback_recorded_at: str = "",
) -> Dict[str, Any]:
    src = _safe_dict(value)
    read_row = _safe_dict(fallback_read)
    write_row = _safe_dict(fallback_write)

    base = _normalize_supervisor_audit_entry(src, kind="memory_resume")

    decision = _safe_str(src.get("decision") or base.get("decision"))
    status = _safe_str(src.get("status") or base.get("status"))
    reason = _safe_str(src.get("reason") or base.get("reason"))
    resume_reason = _safe_str(src.get("resume_reason") or base.get("resume_reason") or reason)
    resume_ready = _safe_bool(src.get("resume_ready"), _safe_bool(base.get("resume_ready"), False))

    relative_path = _safe_str(src.get("relative_path") or base.get("relative_path"))
    if not relative_path:
        relative_path = _safe_str(read_row.get("relative_path") or write_row.get("relative_path"))

    checkpoint_stage = _safe_str(src.get("checkpoint_stage") or base.get("checkpoint_stage"))
    checkpoint_summary = _safe_str(src.get("checkpoint_summary") or base.get("checkpoint_summary"))
    recovery_hint = _safe_str(src.get("recovery_hint") or base.get("recovery_hint"))

    enabled = src.get("enabled")
    if isinstance(enabled, bool):
        enabled_value = enabled
    else:
        enabled_value = bool(
            status or decision or relative_path or checkpoint_stage or checkpoint_summary
        )

    source_kind = _safe_str(src.get("source_kind") or base.get("source_kind"))
    if not source_kind:
        source_kind = _safe_str(read_row.get("source_kind") or write_row.get("source_kind"))

    version = _safe_int(src.get("version"), 0)
    if version <= 0:
        version = _safe_int(read_row.get("version"), 0)
    if version <= 0:
        version = _safe_int(write_row.get("version"), 0)

    at_value = _safe_str(src.get("at") or src.get("recorded_at") or base.get("at"))
    if not at_value:
        at_value = _safe_str(fallback_recorded_at)
    if not at_value:
        at_value = _safe_str(read_row.get("at"))
    if not at_value:
        at_value = _safe_str(write_row.get("at"))

    return {
        **base,
        "enabled": enabled_value,
        "status": status,
        "decision": decision,
        "reason": reason,
        "resume_reason": resume_reason,
        "resume_ready": resume_ready,
        "relative_path": relative_path,
        "source_kind": source_kind,
        "version": version,
        "checkpoint_stage": checkpoint_stage,
        "checkpoint_summary": checkpoint_summary,
        "recovery_hint": recovery_hint,
        "at": at_value,
    }

def _normalize_supervisor_memory_write_entry(
    value: Any,
    *,
    fallback_read: Any = None,
) -> Dict[str, Any]:
    src = _safe_dict(value)
    read_row = _safe_dict(fallback_read)


    base = _normalize_supervisor_audit_entry(src, kind="memory_write")
    base["reason"] = _safe_str(base.get("reason") or src.get("reason_code"))
    base["checkpoint_stage"] = _safe_str(src.get("checkpoint_stage") or base.get("checkpoint_stage"))
    base["checkpoint_summary"] = _safe_str(src.get("checkpoint_summary") or base.get("checkpoint_summary"))
    base["resume_decision"] = _safe_str(src.get("resume_decision") or base.get("resume_decision"))
    base["resume_reason"] = _safe_str(src.get("resume_reason") or base.get("resume_reason"))
    base["source_kind"] = _safe_str(src.get("source_kind") or base.get("source_kind"))


    version = _safe_int(src.get("version"), _safe_int(base.get("version"), 0))
    if version <= 0:
        version = _safe_int(read_row.get("version"), 0)
    base["version"] = version


    return base


def _normalize_supervisor_synthesis_audit(value: Any) -> Dict[str, Any]:
    src = _safe_dict(value)
    return {
        "model": _safe_str(src.get("model")),
        "delegate_packets_total": _safe_int(src.get("delegate_packets_total"), 0),
        "delegate_packets_non_empty": _safe_int(src.get("delegate_packets_non_empty"), 0),
        "delegate_role_names": _safe_list(src.get("delegate_role_names")),
        "grounded_points_count": _safe_int(src.get("grounded_points_count"), 0),
        "fs_context_text_len": _safe_int(src.get("fs_context_text_len"), 0),
        "fs_context_prompt_text_len": _safe_int(src.get("fs_context_prompt_text_len"), 0),
        "documents_count": _safe_int(src.get("documents_count"), 0),
        "target_paths": _safe_list(src.get("target_paths")),
        "content_status": _safe_str(src.get("content_status")),
        "synthesis_prompt_len": _safe_int(src.get("synthesis_prompt_len"), 0),
        "supervisor_skill_strategy": _safe_str(src.get("supervisor_skill_strategy")),
        "supervisor_skills_status": _safe_str(src.get("supervisor_skills_status")),
        "supervisor_skills_enabled_ids": _safe_list(src.get("supervisor_skills_enabled_ids")),
        "supervisor_skills_applied_ids": _safe_list(src.get("supervisor_skills_applied_ids")),
        "supervisor_skills_builtin_ids": _safe_list(src.get("supervisor_skills_builtin_ids")),
        "supervisor_skills_custom_ids": _safe_list(src.get("supervisor_skills_custom_ids")),
        "supervisor_skills_applied_builtin_ids": _safe_list(src.get("supervisor_skills_applied_builtin_ids")),
        "supervisor_skills_applied_custom_ids": _safe_list(src.get("supervisor_skills_applied_custom_ids")),
        "supervisor_skills_prompt_len": _safe_int(src.get("supervisor_skills_prompt_len"), 0),
        "supervisor_skills_step_count": _safe_int(src.get("supervisor_skills_step_count"), 0),
        "supervisor_skills_resolved_items_count": _safe_int(src.get("supervisor_skills_resolved_items_count"), 0),
        "supervisor_skills_applied_prompt_ids": _safe_list(src.get("supervisor_skills_applied_prompt_ids")),
        "memory_read_status": _safe_str(src.get("memory_read_status")),
        "memory_resume_decision": _safe_str(src.get("memory_resume_decision")),
        "memory_resume_reason": _safe_str(src.get("memory_resume_reason")),
        "memory_checkpoint_stage": _safe_str(src.get("memory_checkpoint_stage")),
        "repair_attempted": _safe_bool(src.get("repair_attempted"), False),
        "repair_succeeded": _safe_bool(src.get("repair_succeeded"), False),
        "fallback_used": _safe_bool(src.get("fallback_used"), False),
        "novelty_guard": _safe_dict(src.get("novelty_guard")),
        "novelty_coverage": _safe_dict(src.get("novelty_coverage")),
        "attribution": _safe_dict(src.get("attribution")),
        "at": _safe_str(src.get("at")),
    }



def _synthesis_has_any(entry: Dict[str, Any]) -> bool:
    src = _safe_dict(entry)
    return bool(
        _safe_str(src.get("model"))
        or _safe_int(src.get("delegate_packets_total"), 0)
        or _safe_int(src.get("delegate_packets_non_empty"), 0)
        or _safe_int(src.get("fs_context_text_len"), 0)
        or _safe_int(src.get("fs_context_prompt_text_len"), 0)
        or _safe_int(src.get("synthesis_prompt_len"), 0)
        or _safe_str(src.get("memory_read_status"))
        or _safe_str(src.get("memory_resume_decision"))
        or _safe_str(src.get("memory_resume_reason"))
        or _safe_str(src.get("memory_checkpoint_stage"))
        or _safe_str(src.get("at"))
    )



def _relation_key(value: Any) -> str:
    src = _safe_dict(value)
    return "|".join(
        [
            _safe_str(src.get("run_id")),
            _safe_str(src.get("supervisor_event_id")),
            _safe_str(src.get("final_event_id")),
        ]
    )

def _normalize_supervisor_audit_relation(value: Any) -> Dict[str, Any]:
    src = _safe_dict(value)
    fs_read = _normalize_supervisor_audit_entry(src.get("fs_read"), kind="fs_read")
    notebook_read = _normalize_supervisor_audit_entry(src.get("notebook_read"), kind="notebook_read")
    notebook_write = _normalize_supervisor_audit_entry(src.get("notebook_write"), kind="notebook_write")
    memory_read = _normalize_supervisor_memory_read_entry(src.get("memory_read"))
    memory_write = _normalize_supervisor_memory_write_entry(
        src.get("memory_write"),
        fallback_read=memory_read,
    )
    memory_resume = _normalize_supervisor_memory_resume_entry(
        src.get("memory_resume"),
        fallback_read=memory_read,
        fallback_write=memory_write,
        fallback_recorded_at=_safe_str(src.get("recorded_at")),
    )
    synthesis = _normalize_supervisor_synthesis_audit(src.get("synthesis"))

    has_any = bool(
        _entry_has_any(fs_read)
        or _entry_has_any(notebook_read)
        or _entry_has_any(notebook_write)
        or _entry_has_any(memory_read)
        or _entry_has_any(memory_resume)
        or _entry_has_any(memory_write)
        or _synthesis_has_any(synthesis)
        or _safe_str(src.get("supervisor_event_id"))
        or _safe_str(src.get("final_event_id"))
    )

    recorded_at = _safe_str(src.get("recorded_at"), utc_iso())

    room_state_snapshot = {
        "type": "room_supervisor_audit_relation",
        "source": "state_snapshot",
        "has_any": has_any,
        "run_id": _safe_str(src.get("run_id")),
        "supervisor_event_id": _safe_str(src.get("supervisor_event_id")),
        "final_event_id": _safe_str(src.get("final_event_id")),
        "recorded_at": recorded_at,
        "fs_read": dict(fs_read),
        "notebook_read": dict(notebook_read),
        "notebook_write": dict(notebook_write),
        "memory_read": dict(memory_read),
        "memory_resume": dict(memory_resume),
        "memory_write": dict(memory_write),
        "supervisor_memory_read": dict(memory_read),
        "supervisor_memory_resume": dict(memory_resume),
        "supervisor_memory_write": dict(memory_write),
        "supervisor_memory_read_status": _safe_str(memory_read.get("status")),
        "supervisor_memory_resume_decision": _safe_str(memory_resume.get("decision")),
        "supervisor_memory_write_status": _safe_str(memory_write.get("status")),
        "synthesis": dict(synthesis),
    }

    return {
        "type": "room_supervisor_audit_relation",
        "source": "relation",
        "has_any": has_any,
        "room_id": _safe_str(src.get("room_id")),
        "request_id": _safe_str(src.get("request_id")),
        "run_id": _safe_str(src.get("run_id")),
        "plan_event_id": _safe_str(src.get("plan_event_id")),
        "supervisor_event_id": _safe_str(src.get("supervisor_event_id")),
        "final_event_id": _safe_str(src.get("final_event_id")),
        "trigger_event_id": _safe_str(src.get("trigger_event_id")),
        "recorded_at": recorded_at,
        "fs_read": fs_read,
        "notebook_read": notebook_read,
        "notebook_write": notebook_write,
        "memory_read": memory_read,
        "memory_resume": memory_resume,
        "memory_write": memory_write,
        "room_state_snapshot": room_state_snapshot,
        "synthesis": synthesis,
    }

def _list_supervisor_audit_relations(room_id: str, run_id: str = "") -> List[Dict[str, Any]]:
    state = _load_room_state(room_id)
    rows = [_normalize_supervisor_audit_relation(x) for x in _safe_list(state.get("supervisor_audit_relations"))]
    rows = [x for x in rows if _safe_str(x.get("room_id")) in {"", _safe_str(room_id)}]


    if run_id:
        rows = [x for x in rows if _safe_str(x.get("run_id")) == _safe_str(run_id)]


    rows.sort(
        key=lambda x: (
            _safe_str(x.get("recorded_at")),
            _safe_str(x.get("run_id")),
            _safe_str(x.get("supervisor_event_id")),
            _safe_str(x.get("final_event_id")),
        )
    )
    return rows



def _find_supervisor_audit_relation(
    room_id: str,
    *,
    run_id: str = "",
    supervisor_event_id: str = "",
    final_event_id: str = "",
) -> Optional[Dict[str, Any]]:
    rows = _list_supervisor_audit_relations(room_id, run_id=run_id)


    if final_event_id:
        for item in reversed(rows):
            if _safe_str(item.get("final_event_id")) == _safe_str(final_event_id):
                return item


    if supervisor_event_id:
        for item in reversed(rows):
            if _safe_str(item.get("supervisor_event_id")) == _safe_str(supervisor_event_id):
                return item


    if run_id:
        for item in reversed(rows):
            if _safe_str(item.get("run_id")) == _safe_str(run_id):
                return item


    return rows[-1] if rows else None



def _append_supervisor_audit_relation(
    room_id: str,
    relation: Dict[str, Any],
) -> Dict[str, Any]:
    rid = _safe_str(room_id)
    src = _safe_dict(relation)

    normalized = _normalize_supervisor_audit_relation(
        {
            **src,
            "room_id": rid or _safe_str(src.get("room_id")),
            "recorded_at": _safe_str(src.get("recorded_at"), utc_iso()),
        }
    )

    if not rid:
        return normalized

    relation_row = {
        "room_id": rid,
        "request_id": _safe_str(normalized.get("request_id")),
        "run_id": _safe_str(normalized.get("run_id")),
        "plan_event_id": _safe_str(normalized.get("plan_event_id")),
        "supervisor_event_id": _safe_str(normalized.get("supervisor_event_id")),
        "final_event_id": _safe_str(normalized.get("final_event_id")),
        "trigger_event_id": _safe_str(normalized.get("trigger_event_id")),
        "recorded_at": _safe_str(normalized.get("recorded_at"), utc_iso()),
        "fs_read": _safe_dict(normalized.get("fs_read")),
        "notebook_read": _safe_dict(normalized.get("notebook_read")),
        "notebook_write": _safe_dict(normalized.get("notebook_write")),
        "memory_read": _safe_dict(normalized.get("memory_read")),
        "memory_resume": _safe_dict(normalized.get("memory_resume")),
        "memory_write": _safe_dict(normalized.get("memory_write")),
        "synthesis": _safe_dict(normalized.get("synthesis")),
    }

    state = _load_room_state(rid)
    rows = _safe_list(state.get("supervisor_audit_relations"))

    new_key = _relation_key(relation_row)
    next_rows: List[Dict[str, Any]] = []
    replaced = False

    for item in rows:
        row = _safe_dict(item)
        if new_key and _relation_key(row) == new_key:
            if not replaced:
                next_rows.append(relation_row)
                replaced = True
            continue
        next_rows.append(row)

    if not replaced:
        next_rows.append(relation_row)

    next_rows.sort(
        key=lambda x: (
            _safe_str(x.get("recorded_at")),
            _safe_str(x.get("run_id")),
            _safe_str(x.get("supervisor_event_id")),
            _safe_str(x.get("final_event_id")),
        )
    )

    state["supervisor_audit_relations"] = next_rows

    room_state_snapshot = _safe_dict(normalized.get("room_state_snapshot"))
    if room_state_snapshot:
        state["supervisor_audit_relation"] = room_state_snapshot
        state["supervisor_memory_read"] = _safe_dict(room_state_snapshot.get("supervisor_memory_read"))
        state["supervisor_memory_resume"] = _safe_dict(room_state_snapshot.get("supervisor_memory_resume"))
        state["supervisor_memory_write"] = _safe_dict(room_state_snapshot.get("supervisor_memory_write"))
        state["supervisor_memory_read_status"] = _safe_str(
            room_state_snapshot.get("supervisor_memory_read_status")
        )
        state["supervisor_memory_resume_decision"] = _safe_str(
            room_state_snapshot.get("supervisor_memory_resume_decision")
        )
        state["supervisor_memory_write_status"] = _safe_str(
            room_state_snapshot.get("supervisor_memory_write_status")
        )

    _save_room_state(rid, state)
    return normalized

def _build_state_supervisor_audit_snapshot(
    *,
    state: Dict[str, Any],
    run_id: str = "",
    supervisor_event: Optional[Dict[str, Any]] = None,
    final_event: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    src = _safe_dict(state)
    supervisor_evt = _safe_dict(supervisor_event)
    final_evt = _safe_dict(final_event)

    snapshot_recorded_at = _safe_str(
        src.get("last_supervisor_synthesis_at")
        or src.get("last_run_finished_at")
        or utc_iso()
    )

    fs_read = _normalize_supervisor_audit_entry(
        {
            "at": _safe_str(src.get("last_supervisor_fs_read_at")),
            "enabled": _safe_bool(src.get("last_supervisor_fs_read_enabled"), False),
            "status": _safe_str(src.get("last_supervisor_fs_read_status")),
            "reason": _safe_str(src.get("last_supervisor_fs_read_reason")),
            "focus_root": _safe_str(src.get("last_supervisor_fs_read_focus_root")),
            "scope": _safe_str(src.get("last_supervisor_fs_read_scope"), "minimal"),
            "tool_calls": _safe_list(src.get("last_supervisor_tool_calls")),
            "tool_results": _safe_list(src.get("last_supervisor_tool_results")),
        },
        kind="fs_read",
    )

    notebook_read = _normalize_supervisor_audit_entry(
        {
            "at": _safe_str(src.get("last_supervisor_notebook_read_at")),
            "enabled": _safe_bool(src.get("last_supervisor_notebook_read_enabled"), False),
            "status": _safe_str(src.get("last_supervisor_notebook_read_status")),
            "message": _safe_str(src.get("last_supervisor_notebook_read_message")),
            "relative_path": _safe_str(src.get("last_supervisor_notebook_read_relative_path")),
            "source_kind": _safe_str(src.get("last_supervisor_notebook_read_source_kind")),
            "documents_count": _safe_int(src.get("last_supervisor_notebook_read_documents_count"), 0),
            "tool_calls": _safe_list(src.get("last_supervisor_notebook_read_tool_calls")),
            "tool_results": _safe_list(src.get("last_supervisor_notebook_read_tool_results")),
        },
        kind="notebook_read",
    )

    notebook_write = _normalize_supervisor_audit_entry(
        {
            "at": _safe_str(src.get("last_supervisor_notebook_write_at")),
            "enabled": True,
            "status": _safe_str(src.get("last_supervisor_notebook_write_status")),
            "reason": _safe_str(
                src.get("last_supervisor_notebook_reason")
                or src.get("last_supervisor_notebook_policy_reason_code")
            ),
            "message": _safe_str(
                src.get("last_supervisor_notebook_write_message")
                or src.get("last_supervisor_notebook_policy_message")
            ),
            "focus_root": _safe_str(src.get("last_supervisor_notebook_focus_root")),
            "relative_path": _safe_str(src.get("last_supervisor_notebook_relative_path")),
            "bytes_written": _safe_int(src.get("last_supervisor_notebook_bytes_written"), 0),
            "bytes_appended": _safe_int(src.get("last_supervisor_notebook_bytes_appended"), 0),
            "actor_type": _safe_str(src.get("last_supervisor_notebook_actor_type")),
            "actor_id": _safe_str(src.get("last_supervisor_notebook_actor_id")),
            "skill_id": _safe_str(src.get("last_supervisor_notebook_skill_id")),
            "delegated_from": _safe_str(src.get("last_supervisor_notebook_delegated_from")),
            "policy_allowed": _safe_bool(src.get("last_supervisor_notebook_policy_allowed"), False),
            "policy_status": _safe_str(src.get("last_supervisor_notebook_policy_status")),
            "policy_reason_code": _safe_str(src.get("last_supervisor_notebook_policy_reason_code")),
            "policy_message": _safe_str(src.get("last_supervisor_notebook_policy_message")),
            "tool_calls": _safe_list(src.get("last_supervisor_notebook_tool_calls")),
            "tool_results": _safe_list(src.get("last_supervisor_notebook_tool_results")),
        },
        kind="notebook_write",
    )

    memory_read = _normalize_supervisor_memory_read_entry(
        {
            "at": _safe_str(src.get("last_supervisor_memory_read_at")),
            "enabled": _safe_bool(src.get("last_supervisor_memory_read_enabled"), False),
            "status": _safe_str(src.get("last_supervisor_memory_read_status")),
            "message": _safe_str(src.get("last_supervisor_memory_read_message")),
            "reason_code": _safe_str(src.get("last_supervisor_memory_read_reason_code")),
            "relative_path": _safe_str(src.get("last_supervisor_memory_read_relative_path")),
            "source_kind": _safe_str(src.get("last_supervisor_memory_read_source_kind")),
            "version": _safe_int(src.get("last_supervisor_memory_read_version"), 0),
            "checkpoint_stage": _safe_str(src.get("last_supervisor_memory_checkpoint_stage")),
            "checkpoint_summary": _safe_str(src.get("last_supervisor_memory_checkpoint_summary")),
            "recovery_hint": _safe_str(src.get("last_supervisor_memory_recovery_hint")),
            "resume_ready": _safe_bool(src.get("last_supervisor_memory_resume_ready"), False),
            "resume_reason": _safe_str(src.get("last_supervisor_memory_resume_reason")),
            "tool_calls": _safe_list(src.get("last_supervisor_memory_read_tool_calls")),
            "tool_results": _safe_list(src.get("last_supervisor_memory_read_tool_results")),
            "checkpoint": {
                "stage": _safe_str(src.get("last_supervisor_memory_checkpoint_stage")),
                "summary": _safe_str(src.get("last_supervisor_memory_checkpoint_summary")),
                "last_step": _safe_str(src.get("last_supervisor_memory_last_step")),
                "recovery_hint": _safe_str(src.get("last_supervisor_memory_recovery_hint")),
            },
            "resume": {
                "resume_ready": _safe_bool(src.get("last_supervisor_memory_resume_ready"), False),
                "resume_reason": _safe_str(src.get("last_supervisor_memory_resume_reason")),
                "invalidated_by": _safe_str(src.get("last_supervisor_memory_invalidated_by")),
            },
        }
    )

    memory_write = _normalize_supervisor_memory_write_entry(
        {
            "at": _safe_str(src.get("last_supervisor_memory_write_at")),
            "enabled": _safe_bool(src.get("last_supervisor_memory_write_enabled"), False),
            "status": _safe_str(src.get("last_supervisor_memory_write_status")),
            "message": _safe_str(src.get("last_supervisor_memory_write_message")),
            "reason_code": _safe_str(src.get("last_supervisor_memory_write_reason_code")),
            "relative_path": _safe_str(src.get("last_supervisor_memory_write_relative_path")),
            "version": _safe_int(src.get("last_supervisor_memory_write_version"), 0),
            "bytes_written": _safe_int(src.get("last_supervisor_memory_write_bytes_written"), 0),
            "checkpoint_stage": _safe_str(src.get("last_supervisor_memory_write_checkpoint_stage")),
            "checkpoint_summary": _safe_str(src.get("last_supervisor_memory_write_checkpoint_summary")),
            "resume_decision": _safe_str(src.get("last_supervisor_memory_write_resume_decision")),
            "resume_reason": _safe_str(src.get("last_supervisor_memory_write_resume_reason")),
            "source_kind": _safe_str(src.get("last_supervisor_memory_write_source_kind")),
            "tool_calls": _safe_list(src.get("last_supervisor_memory_write_tool_calls")),
            "tool_results": _safe_list(src.get("last_supervisor_memory_write_tool_results")),
        },
        fallback_read=memory_read,
    )

    memory_resume = _normalize_supervisor_memory_resume_entry(
        {
            "at": _safe_str(src.get("last_supervisor_memory_resume_at")),
            "enabled": src.get("last_supervisor_memory_resume_enabled"),
            "status": _safe_str(src.get("last_supervisor_memory_resume_status")),
            "decision": _safe_str(src.get("last_supervisor_memory_resume_decision")),
            "reason": _safe_str(src.get("last_supervisor_memory_resume_reason")),
            "resume_reason": _safe_str(
                src.get("last_supervisor_memory_resume_resume_reason")
                or src.get("last_supervisor_memory_resume_reason")
            ),
            "resume_ready": _safe_bool(src.get("last_supervisor_memory_resume_ready"), False),
            "relative_path": _safe_str(src.get("last_supervisor_memory_resume_relative_path")),
            "source_kind": _safe_str(src.get("last_supervisor_memory_resume_source_kind")),
            "version": _safe_int(src.get("last_supervisor_memory_resume_version"), 0),
            "checkpoint_stage": _safe_str(src.get("last_supervisor_memory_resume_checkpoint_stage")),
            "checkpoint_summary": _safe_str(src.get("last_supervisor_memory_resume_checkpoint_summary")),
            "recovery_hint": _safe_str(src.get("last_supervisor_memory_resume_recovery_hint")),
            "tool_calls": _safe_list(src.get("last_supervisor_memory_resume_tool_calls")),
            "tool_results": _safe_list(src.get("last_supervisor_memory_resume_tool_results")),
        },
        fallback_read=memory_read,
        fallback_write=memory_write,
        fallback_recorded_at=snapshot_recorded_at,
    )

    synthesis = _normalize_supervisor_synthesis_audit(
        {
            "model": _safe_str(src.get("last_supervisor_synthesis_model")),
            "delegate_packets_total": _safe_int(src.get("last_supervisor_delegate_packets_total"), 0),
            "delegate_packets_non_empty": _safe_int(src.get("last_supervisor_delegate_packets_non_empty"), 0),
            "fs_context_text_len": _safe_int(src.get("last_supervisor_fs_context_text_len"), 0),
            "fs_context_prompt_text_len": _safe_int(src.get("last_supervisor_fs_context_prompt_text_len"), 0),
            "synthesis_prompt_len": _safe_int(src.get("last_supervisor_synthesis_prompt_len"), 0),
            "memory_read_status": _safe_str(src.get("last_supervisor_memory_read_status")),
            "memory_resume_decision": _safe_str(src.get("last_supervisor_memory_resume_decision")),
            "memory_resume_reason": _safe_str(src.get("last_supervisor_memory_resume_reason")),
            "memory_checkpoint_stage": _safe_str(src.get("last_supervisor_memory_checkpoint_stage")),
            "at": _safe_str(src.get("last_supervisor_synthesis_at")),
        }
    )

    has_any = bool(
        _entry_has_any(fs_read)
        or _entry_has_any(notebook_read)
        or _entry_has_any(notebook_write)
        or _entry_has_any(memory_read)
        or _entry_has_any(memory_resume)
        or _entry_has_any(memory_write)
        or _synthesis_has_any(synthesis)
    )

    return {
        "type": "room_supervisor_audit_relation",
        "source": "state_snapshot",
        "has_any": has_any,
        "run_id": _safe_str(run_id),
        "supervisor_event_id": _safe_str(supervisor_evt.get("id")),
        "final_event_id": _safe_str(final_evt.get("id")),
        "recorded_at": snapshot_recorded_at,
        "fs_read": fs_read,
        "notebook_read": notebook_read,
        "notebook_write": notebook_write,
        "memory_read": memory_read,
        "memory_resume": memory_resume,
        "memory_write": memory_write,
        "supervisor_memory_read": memory_read,
        "supervisor_memory_resume": memory_resume,
        "supervisor_memory_write": memory_write,
        "supervisor_memory_read_status": _safe_str(memory_read.get("status")),
        "supervisor_memory_resume_decision": _safe_str(memory_resume.get("decision")),
        "supervisor_memory_write_status": _safe_str(memory_write.get("status")),
        "synthesis": synthesis,
    }

__all__ = [
    "_append_aborted_event",
    "_append_room_event",
    "_append_supervisor_audit_relation",
    "_build_dialog_lines",
    "_build_run_id",
    "_build_state_supervisor_audit_snapshot",
    "_clear_run_state",
    "_find_supervisor_audit_relation",
    "_list_supervisor_audit_relations",
    "_load_room_state",
    "_normalize_supervisor_audit_relation",
    "_set_room_state_patch",
    "_update_room_last_message",
]

