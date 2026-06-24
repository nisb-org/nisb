from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional

from .room_packet_builder import _normalize_tool_activity_lists
from .room_role_runtime_request import _safe_dict, _safe_list, _safe_str
from .room_supervisor_runtime import _run_supervisor_notebook_write
from .room_supervisor_skills import build_supervisor_skills_tool_result
from .room_supervisor_synthesis import (
    _build_delegate_summary_tool_result,
    _merge_tool_activity_groups,
)
from .supervisor_runtime.memory_resume import write_supervisor_memory_sidecar


def _build_supervisor_memory_write_payload_from_info(info: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "enabled": bool(info.get("enabled")),
        "status": _safe_str(info.get("status")),
        "message": _safe_str(info.get("message")),
        "reason_code": _safe_str(info.get("reason_code")),
        "relative_path": _safe_str(info.get("relative_path")),
        "bytes_written": int(info.get("bytes_written") or 0),
        "checkpoint_stage": _safe_str(info.get("checkpoint_stage")),
        "checkpoint_summary": _safe_str(info.get("checkpoint_summary")),
        "resume_decision": _safe_str(info.get("resume_decision")),
        "resume_reason": _safe_str(info.get("resume_reason")),
        "source_kind": _safe_str(info.get("source_kind")),
        "effect_disposition": _safe_str(info.get("effect_disposition")),
        "effect_key": _safe_str(info.get("effect_key")),
        "tool_calls": _safe_list(info.get("tool_calls")),
        "tool_results": _safe_list(info.get("tool_results")),
    }


def _build_supervisor_memory_write_tool_result_from_info(info: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "type": "supervisor_memory_write",
        "status": _safe_str(info.get("status")),
        "message": _safe_str(info.get("message")),
        "reason_code": _safe_str(info.get("reason_code")),
        "relative_path": _safe_str(info.get("relative_path")),
        "bytes_written": int(info.get("bytes_written") or 0),
        "checkpoint_stage": _safe_str(info.get("checkpoint_stage")),
        "checkpoint_summary": _safe_str(info.get("checkpoint_summary")),
        "resume_decision": _safe_str(info.get("resume_decision")),
        "resume_reason": _safe_str(info.get("resume_reason")),
        "source_kind": _safe_str(info.get("source_kind")),
        "effect_disposition": _safe_str(info.get("effect_disposition")),
        "effect_key": _safe_str(info.get("effect_key")),
    }


def _build_supervisor_event_tool_results(
    *,
    flattened_tool_results: List[Dict[str, Any]],
    notebook_read_tool_result: Optional[Dict[str, Any]],
    memory_read_tool_result: Dict[str, Any],
    memory_resume_tool_result: Dict[str, Any],
    memory_write_result: Dict[str, Any],
    delegate_summary_result: Dict[str, Any],
    novelty_guard: Dict[str, Any],
    attribution_result: Dict[str, Any],
    supervisor_skills_result: Dict[str, Any],
) -> List[Dict[str, Any]]:
    results = list(flattened_tool_results)
    if notebook_read_tool_result:
        results.append(notebook_read_tool_result)
    results.append(memory_read_tool_result)
    results.append(memory_resume_tool_result)
    results.append(memory_write_result)
    results.append(delegate_summary_result)
    results.append(novelty_guard)
    results.append(attribution_result)
    results.append(supervisor_skills_result)
    return results


def _safe_bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    text = _safe_str(value).lower()
    if text in {"1", "true", "yes", "on"}:
        return True
    if text in {"0", "false", "no", "off"}:
        return False
    return default


def _normalize_rel_path(value: Any) -> str:
    raw = _safe_str(value).replace("\\", "/")
    while "//" in raw:
        raw = raw.replace("//", "/")
    raw = raw.strip("/")
    if not raw:
        return ""
    parts = [part.strip() for part in raw.split("/") if part and part not in {".", ".."}]
    return "/".join(parts)


def _join_rel_path(*parts: Any) -> str:
    out: List[str] = []
    for part in parts:
        text = _normalize_rel_path(part)
        if text:
            out.append(text)
    return "/".join(out)


def _continuation_row(request_args: Dict[str, Any]) -> Dict[str, Any]:
    row = _safe_dict(request_args)
    continuation = _safe_dict(row.get("continuation"))
    merged = dict(continuation)
    for key in (
        "effect_dispositions",
        "skipped_effects",
        "resume_projection_repair_effect_types",
        "resume_skip_effect_types",
        "continuation_mode",
        "resume_from_checkpoint",
        "resume_checkpoint_ref",
    ):
        if key in row and key not in merged:
            merged[key] = row.get(key)
    return merged


def _build_effect_key(run_id: str, effect_type: str, checkpoint_stage: str = "supervisor_persistence") -> str:
    return ":".join(
        part
        for part in (
            _safe_str(run_id),
            _safe_str(checkpoint_stage, "supervisor_persistence"),
            _safe_str(effect_type),
        )
        if part
    )


def _match_effect_record(record: Any, effect_type: str) -> bool:
    if isinstance(record, str):
        return _safe_str(record) == effect_type
    row = _safe_dict(record)
    if not row:
        return False
    if _safe_str(row.get("effect_type")) == effect_type:
        return True
    if _safe_str(row.get("type")) == effect_type:
        return True
    effect_key = _safe_str(row.get("effect_key"))
    return effect_key.endswith(f":{effect_type}") or effect_key == effect_type


def _resolve_effect_disposition(
    *,
    effect_type: str,
    run_id: str,
    request_args: Dict[str, Any],
) -> Dict[str, Any]:
    continuation = _continuation_row(request_args)
    checkpoint_stage = "supervisor_persistence"
    effect_key = _build_effect_key(run_id, effect_type, checkpoint_stage)

    for source in (
        _safe_list(continuation.get("effect_dispositions")),
        _safe_list(request_args.get("effect_dispositions")),
    ):
        for item in source:
            if not _match_effect_record(item, effect_type):
                continue
            row = _safe_dict(item)
            disposition = _safe_str(row.get("disposition"), "execute").lower()
            if disposition not in {"execute", "skip", "projection_repair"}:
                disposition = "execute"
            return {
                "effect_type": effect_type,
                "effect_key": _safe_str(row.get("effect_key"), effect_key),
                "checkpoint_stage": checkpoint_stage,
                "disposition": disposition,
                "reason": _safe_str(row.get("reason"), "resume_effect_disposition"),
                "produced_ref": _safe_str(row.get("produced_ref")),
            }

    for source in (
        _safe_list(continuation.get("skipped_effects")),
        _safe_list(request_args.get("skipped_effects")),
        _safe_list(continuation.get("resume_skip_effect_types")),
        _safe_list(request_args.get("resume_skip_effect_types")),
    ):
        for item in source:
            if _match_effect_record(item, effect_type):
                return {
                    "effect_type": effect_type,
                    "effect_key": effect_key,
                    "checkpoint_stage": checkpoint_stage,
                    "disposition": "skip",
                    "reason": "effect_already_committed",
                    "produced_ref": "",
                }

    for source in (
        _safe_list(continuation.get("resume_projection_repair_effect_types")),
        _safe_list(request_args.get("resume_projection_repair_effect_types")),
    ):
        for item in source:
            if _match_effect_record(item, effect_type):
                return {
                    "effect_type": effect_type,
                    "effect_key": effect_key,
                    "checkpoint_stage": checkpoint_stage,
                    "disposition": "projection_repair",
                    "reason": "repair_projection_only",
                    "produced_ref": "",
                }

    return {
        "effect_type": effect_type,
        "effect_key": effect_key,
        "checkpoint_stage": checkpoint_stage,
        "disposition": "execute",
        "reason": "",
        "produced_ref": "",
    }


def _derive_notebook_relative_path(
    supervisor_request_args: Dict[str, Any],
    notebook_read_info: Dict[str, Any],
) -> str:
    read_path = _normalize_rel_path(notebook_read_info.get("relative_path"))
    if read_path:
        return read_path

    mcp_overrides = _safe_dict(supervisor_request_args.get("mcp_overrides"))
    notebook_dir = _normalize_rel_path(mcp_overrides.get("notebook_dir")) or "_room_supervisor_notebooks"
    notebook_filename = _safe_str(mcp_overrides.get("notebook_filename"), "supervisor.md")
    return _join_rel_path(notebook_dir, notebook_filename)


def _derive_memory_relative_path(
    supervisor_request_args: Dict[str, Any],
    memory_read_info: Dict[str, Any],
) -> str:
    read_path = _normalize_rel_path(memory_read_info.get("relative_path"))
    if read_path:
        return read_path

    mcp_overrides = _safe_dict(supervisor_request_args.get("mcp_overrides"))
    return _normalize_rel_path(mcp_overrides.get("memory_filename"))


def _build_skipped_notebook_info(
    *,
    supervisor_request_args: Dict[str, Any],
    notebook_read_info: Dict[str, Any],
    disposition_row: Dict[str, Any],
    utc_iso_fn: Callable[[], str],
) -> Dict[str, Any]:
    return {
        "enabled": _safe_bool(
            _safe_dict(supervisor_request_args.get("mcp_overrides")).get("notebook_write_enabled"),
            False,
        ),
        "status": "skipped",
        "message": "supervisor notebook write skipped: already committed before resume",
        "reason_code": "SUPERVISOR_NOTEBOOK_WRITE_SKIPPED",
        "relative_path": _derive_notebook_relative_path(supervisor_request_args, notebook_read_info),
        "bytes_written": 0,
        "tool_calls": [],
        "tool_results": [],
        "recorded_at": utc_iso_fn(),
        "effect_disposition": "skip",
        "effect_key": _safe_str(disposition_row.get("effect_key")),
        "checkpoint_stage": _safe_str(disposition_row.get("checkpoint_stage")),
    }


def _build_projection_repair_notebook_info(
    *,
    supervisor_request_args: Dict[str, Any],
    notebook_read_info: Dict[str, Any],
    disposition_row: Dict[str, Any],
    utc_iso_fn: Callable[[], str],
) -> Dict[str, Any]:
    return {
        "enabled": _safe_bool(
            _safe_dict(supervisor_request_args.get("mcp_overrides")).get("notebook_write_enabled"),
            False,
        ),
        "status": "repaired",
        "message": "supervisor notebook write projection repaired without repeating write",
        "reason_code": "SUPERVISOR_NOTEBOOK_WRITE_REPAIRED",
        "relative_path": _derive_notebook_relative_path(supervisor_request_args, notebook_read_info),
        "bytes_written": 0,
        "tool_calls": [],
        "tool_results": [],
        "recorded_at": utc_iso_fn(),
        "effect_disposition": "projection_repair",
        "effect_key": _safe_str(disposition_row.get("effect_key")),
        "checkpoint_stage": _safe_str(disposition_row.get("checkpoint_stage")),
    }


def _build_skipped_memory_write_info(
    *,
    mcp: Dict[str, Any],
    supervisor_request_args: Dict[str, Any],
    memory_read_info: Dict[str, Any],
    memory_resume_info: Dict[str, Any],
    disposition_row: Dict[str, Any],
    utc_iso_fn: Callable[[], str],
) -> Dict[str, Any]:
    return {
        "enabled": _safe_bool(mcp.get("memory_write_enabled"), False),
        "status": "skipped",
        "message": "supervisor memory write skipped: already committed before resume",
        "reason_code": "SUPERVISOR_MEMORY_WRITE_SKIPPED",
        "relative_path": _derive_memory_relative_path(supervisor_request_args, memory_read_info),
        "bytes_written": 0,
        "checkpoint_stage": _safe_str(disposition_row.get("checkpoint_stage")),
        "checkpoint_summary": "",
        "resume_decision": _safe_str(memory_resume_info.get("decision")),
        "resume_reason": _safe_str(memory_resume_info.get("reason")),
        "source_kind": "sidecar",
        "tool_calls": [],
        "tool_results": [],
        "recorded_at": utc_iso_fn(),
        "effect_disposition": "skip",
        "effect_key": _safe_str(disposition_row.get("effect_key")),
    }


def _build_projection_repair_memory_write_info(
    *,
    mcp: Dict[str, Any],
    supervisor_request_args: Dict[str, Any],
    memory_read_info: Dict[str, Any],
    memory_resume_info: Dict[str, Any],
    disposition_row: Dict[str, Any],
    utc_iso_fn: Callable[[], str],
) -> Dict[str, Any]:
    return {
        "enabled": _safe_bool(mcp.get("memory_write_enabled"), False),
        "status": "repaired",
        "message": "supervisor memory write projection repaired without repeating write",
        "reason_code": "SUPERVISOR_MEMORY_WRITE_REPAIRED",
        "relative_path": _derive_memory_relative_path(supervisor_request_args, memory_read_info),
        "bytes_written": 0,
        "checkpoint_stage": _safe_str(disposition_row.get("checkpoint_stage")),
        "checkpoint_summary": "",
        "resume_decision": _safe_str(memory_resume_info.get("decision")),
        "resume_reason": _safe_str(memory_resume_info.get("reason")),
        "source_kind": "sidecar",
        "tool_calls": [],
        "tool_results": [],
        "recorded_at": utc_iso_fn(),
        "effect_disposition": "projection_repair",
        "effect_key": _safe_str(disposition_row.get("effect_key")),
    }


def _run_supervisor_persistence_stage(
    *,
    room_id: str,
    question: str,
    run_id: str,
    mcp: Dict[str, Any],
    fs_context: Dict[str, Any],
    notebook_read_info: Dict[str, Any],
    memory_read_info: Dict[str, Any],
    memory_resume_info: Dict[str, Any],
    supervisor_request_args: Dict[str, Any],
    delegate_events: List[Dict[str, Any]],
    role_message_events: List[Dict[str, Any]],
    delegate_packets: List[Dict[str, Any]],
    plan_summary: str,
    prompt_delegate_packets: List[Dict[str, Any]],
    audit_delegate_packets: List[Dict[str, Any]],
    supervisor_evt: Dict[str, Any],
    supervisor_packet: Dict[str, Any],
    final_text: str,
    novelty_guard: Dict[str, Any],
    attribution_result: Dict[str, Any],
    supervisor_skills_info: Dict[str, Any],
    supervisor_skills_payload: Dict[str, Any],
    utc_iso_fn: Callable[[], str],
) -> Dict[str, Any]:
    notebook_effect = _resolve_effect_disposition(
        effect_type="notebook_write",
        run_id=run_id,
        request_args=supervisor_request_args,
    )
    memory_effect = _resolve_effect_disposition(
        effect_type="memory_write",
        run_id=run_id,
        request_args=supervisor_request_args,
    )

    if notebook_effect["disposition"] == "skip":
        notebook_info = _build_skipped_notebook_info(
            supervisor_request_args=supervisor_request_args,
            notebook_read_info=notebook_read_info,
            disposition_row=notebook_effect,
            utc_iso_fn=utc_iso_fn,
        )
    elif notebook_effect["disposition"] == "projection_repair":
        notebook_info = _build_projection_repair_notebook_info(
            supervisor_request_args=supervisor_request_args,
            notebook_read_info=notebook_read_info,
            disposition_row=notebook_effect,
            utc_iso_fn=utc_iso_fn,
        )
    else:
        notebook_info = _run_supervisor_notebook_write(
            room_id=room_id,
            request_args=supervisor_request_args,
            question=question,
            plan_summary=plan_summary,
            fs_context=fs_context,
            notebook_read_result=notebook_read_info,
            delegate_packets=prompt_delegate_packets or delegate_packets,
            final_text=final_text,
            run_id=run_id,
            supervisor_event_id=supervisor_evt["id"],
        )
        notebook_info = dict(_safe_dict(notebook_info))
        notebook_info["effect_disposition"] = "execute"
        notebook_info["effect_key"] = _safe_str(notebook_effect.get("effect_key"))

    if memory_effect["disposition"] == "skip":
        memory_write_info = _build_skipped_memory_write_info(
            mcp=mcp,
            supervisor_request_args=supervisor_request_args,
            memory_read_info=memory_read_info,
            memory_resume_info=memory_resume_info,
            disposition_row=memory_effect,
            utc_iso_fn=utc_iso_fn,
        )
    elif memory_effect["disposition"] == "projection_repair":
        memory_write_info = _build_projection_repair_memory_write_info(
            mcp=mcp,
            supervisor_request_args=supervisor_request_args,
            memory_read_info=memory_read_info,
            memory_resume_info=memory_resume_info,
            disposition_row=memory_effect,
            utc_iso_fn=utc_iso_fn,
        )
    else:
        try:
            memory_write_info = write_supervisor_memory_sidecar(
                room_id=room_id,
                mcp=mcp,
                question=question,
                plan_summary=plan_summary,
                fs_context=fs_context,
                memory_read_result=memory_read_info,
                memory_resume_result=memory_resume_info,
                delegate_packets=prompt_delegate_packets or delegate_packets,
                final_text=final_text,
                run_id=run_id,
                supervisor_event_id=supervisor_evt["id"],
                final_event_id="",
            )
        except Exception as ex:
            memory_write_info = {
                "enabled": bool(mcp.get("memory_write_enabled")),
                "status": "error",
                "message": f"supervisor memory write failed: {type(ex).__name__}",
                "reason_code": "SUPERVISOR_MEMORY_WRITE_EXCEPTION",
                "relative_path": "",
                "bytes_written": 0,
                "checkpoint_stage": "",
                "checkpoint_summary": "",
                "resume_decision": _safe_str(memory_resume_info.get("decision")),
                "resume_reason": _safe_str(memory_resume_info.get("reason")),
                "source_kind": "sidecar",
                "tool_calls": [],
                "tool_results": [],
                "recorded_at": utc_iso_fn(),
            }
        memory_write_info = dict(_safe_dict(memory_write_info))
        memory_write_info["effect_disposition"] = "execute"
        memory_write_info["effect_key"] = _safe_str(memory_effect.get("effect_key"))

    memory_write_info_initial = dict(_safe_dict(memory_write_info))
    supervisor_memory_write_payload = _build_supervisor_memory_write_payload_from_info(memory_write_info)

    notebook_read_tool_result = (
        {
            "type": "supervisor_notebook_read",
            "status": _safe_str(notebook_read_info.get("status") or "success"),
            "relative_path": _safe_str(notebook_read_info.get("relative_path")),
            "documents_count": int(notebook_read_info.get("documents_count") or 0),
            "source_kind": _safe_str(notebook_read_info.get("source_kind") or "fs_read"),
        }
        if notebook_read_info
        else None
    )

    memory_checkpoint = _safe_dict(memory_read_info.get("checkpoint"))
    memory_resume_from_read = _safe_dict(memory_read_info.get("resume"))

    memory_read_tool_result = {
        "type": "supervisor_memory_read",
        "status": _safe_str(memory_read_info.get("status")),
        "message": _safe_str(memory_read_info.get("message")),
        "reason_code": _safe_str(memory_read_info.get("reason_code")),
        "relative_path": _safe_str(memory_read_info.get("relative_path")),
        "source_kind": _safe_str(memory_read_info.get("source_kind")),
        "version": int(memory_read_info.get("version") or 0),
        "checkpoint_stage": _safe_str(memory_checkpoint.get("stage")),
        "checkpoint_summary": _safe_str(memory_checkpoint.get("summary")),
        "recovery_hint": _safe_str(memory_checkpoint.get("recovery_hint")),
        "resume_ready": bool(memory_resume_from_read.get("resume_ready")),
    }

    memory_resume_tool_result = {
        "type": "supervisor_memory_resume",
        "status": _safe_str(memory_resume_info.get("status")),
        "decision": _safe_str(memory_resume_info.get("decision")),
        "reason": _safe_str(memory_resume_info.get("reason")),
        "resume_ready": bool(memory_resume_info.get("resume_ready")),
        "relative_path": _safe_str(memory_resume_info.get("relative_path")),
        "checkpoint_stage": _safe_str(memory_resume_info.get("checkpoint_stage")),
        "checkpoint_summary": _safe_str(memory_resume_info.get("checkpoint_summary")),
        "recovery_hint": _safe_str(memory_resume_info.get("recovery_hint")),
    }

    supervisor_tool_calls, supervisor_tool_results = _normalize_tool_activity_lists(
        supervisor_packet.get("tool_calls"),
        supervisor_packet.get("tool_results"),
    )
    fs_tool_calls, fs_tool_results = _normalize_tool_activity_lists(
        fs_context.get("tool_calls"),
        fs_context.get("tool_results"),
    )
    notebook_tool_calls, notebook_tool_results = _normalize_tool_activity_lists(
        notebook_info.get("tool_calls"),
        notebook_info.get("tool_results"),
    )

    flattened_tool_calls, flattened_tool_results = _merge_tool_activity_groups(
        (supervisor_tool_calls, supervisor_tool_results),
        (fs_tool_calls, fs_tool_results),
        (notebook_tool_calls, notebook_tool_results),
    )

    delegate_summary_result = _build_delegate_summary_tool_result(
        question=question,
        plan_summary=plan_summary,
        delegate_packets=audit_delegate_packets or prompt_delegate_packets or delegate_packets,
        delegate_events=delegate_events,
        role_message_events=role_message_events,
    )
    supervisor_skills_result = build_supervisor_skills_tool_result(supervisor_skills_info)

    effect_dispositions = [dict(notebook_effect), dict(memory_effect)]
    skipped_effects = [
        dict(item) for item in effect_dispositions if _safe_str(item.get("disposition")) == "skip"
    ]
    repair_effects = [
        dict(item) for item in effect_dispositions if _safe_str(item.get("disposition")) == "projection_repair"
    ]
    executed_effects = [
        dict(item) for item in effect_dispositions if _safe_str(item.get("disposition")) == "execute"
    ]

    return {
        "notebook_info": notebook_info,
        "memory_write_info": memory_write_info,
        "memory_write_info_initial": memory_write_info_initial,
        "supervisor_memory_write_payload": supervisor_memory_write_payload,
        "notebook_read_tool_result": notebook_read_tool_result,
        "memory_read_tool_result": memory_read_tool_result,
        "memory_resume_tool_result": memory_resume_tool_result,
        "flattened_tool_calls": flattened_tool_calls,
        "flattened_tool_results": flattened_tool_results,
        "delegate_summary_result": delegate_summary_result,
        "supervisor_skills_result": supervisor_skills_result,
        "fs_tool_calls": fs_tool_calls,
        "fs_tool_results": fs_tool_results,
        "notebook_tool_calls": notebook_tool_calls,
        "notebook_tool_results": notebook_tool_results,
        "novelty_guard": novelty_guard,
        "attribution_result": attribution_result,
        "supervisor_skills_payload": dict(supervisor_skills_payload),
        "effect_dispositions": effect_dispositions,
        "skipped_effects": skipped_effects,
        "executed_effects": executed_effects,
        "repair_effects": repair_effects,
    }


__all__ = [
    "_build_supervisor_event_tool_results",
    "_build_supervisor_memory_write_payload_from_info",
    "_build_supervisor_memory_write_tool_result_from_info",
    "_run_supervisor_persistence_stage",
]
