from __future__ import annotations

from typing import Any, Callable, Dict, List, Tuple

from .room_audit_helpers import _append_supervisor_audit_relation
from .room_orchestrator_supervisor_persistence import (
    _build_supervisor_event_tool_results,
    _build_supervisor_memory_write_payload_from_info,
    _build_supervisor_memory_write_tool_result_from_info,
)
from .room_packet_builder import _empty_evidence_result
from .room_result_envelope import _formal_envelope
from .room_role_runtime_request import (
    _safe_dict,
    _safe_list,
    _safe_str,
    _truncate_text,
)
from .room_supervisor_runtime import _patch_supervisor_runtime_state
from .supervisor_runtime.memory_resume import write_supervisor_memory_sidecar


def _safe_non_negative_int(value: Any, fallback: int = 0) -> int:
    try:
        return max(0, int(value))
    except Exception:
        try:
            return max(0, int(fallback))
        except Exception:
            return 0


def _continuation_row(request_args: Dict[str, Any]) -> Dict[str, Any]:
    row = _safe_dict(request_args)
    continuation = dict(_safe_dict(row.get("continuation")))
    for key in (
        "continuation_mode",
        "continuation_status",
        "resume_from_checkpoint",
        "resume_checkpoint_ref",
        "resume_ready",
        "resume_token",
        "resume_reason",
        "resumed_from_run_id",
        "resumed_from_event_id",
        "resumed_from_stage",
        "pause_requested",
        "pause_reason",
        "pause_requested_at",
        "paused_at",
        "pause_effective_at",
        "interruption_reason",
        "last_completed_step",
        "skipped_effects",
        "effect_dispositions",
        "error_blocking_resume",
    ):
        if key in row and key not in continuation:
            continuation[key] = row.get(key)
    return continuation


def _resolve_continuation_mode(
    *,
    supervisor_request_args: Dict[str, Any],
    memory_resume_info: Dict[str, Any],
) -> str:
    continuation = _continuation_row(supervisor_request_args)
    explicit_mode = _safe_str(continuation.get("continuation_mode")).lower()
    if explicit_mode in {"fresh", "resumed"}:
        return explicit_mode

    if bool(continuation.get("resume_from_checkpoint")):
        return "resumed"
    if _safe_str(continuation.get("resume_checkpoint_ref")):
        return "resumed"
    if _safe_str(continuation.get("resumed_from_run_id")):
        return "resumed"
    if _safe_str(continuation.get("resumed_from_event_id")):
        return "resumed"
    if _safe_str(continuation.get("resumed_from_stage")):
        return "resumed"

    decision = _safe_str(memory_resume_info.get("decision")).lower()
    if decision in {
        "continue_from_checkpoint",
        "resume_from_checkpoint",
        "resume",
        "continue",
    }:
        return "resumed"

    return "fresh"


def _build_completion_continuation_payload(
    *,
    supervisor_request_args: Dict[str, Any],
    memory_resume_info: Dict[str, Any],
    skipped_effects: List[Dict[str, Any]],
    effect_dispositions: List[Dict[str, Any]],
) -> Dict[str, Any]:
    continuation = _continuation_row(supervisor_request_args)
    continuation_mode = _resolve_continuation_mode(
        supervisor_request_args=supervisor_request_args,
        memory_resume_info=memory_resume_info,
    )
    continuation_status = "completed_after_resume" if continuation_mode == "resumed" else "completed"

    resume_checkpoint_ref = _safe_str(continuation.get("resume_checkpoint_ref"))
    resumed_from_run_id = _safe_str(continuation.get("resumed_from_run_id"))
    resumed_from_event_id = _safe_str(continuation.get("resumed_from_event_id"))
    resumed_from_stage = _safe_str(
        continuation.get("resumed_from_stage") or memory_resume_info.get("checkpoint_stage")
    )
    resume_from_checkpoint = bool(
        continuation_mode == "resumed"
        or continuation.get("resume_from_checkpoint")
        or resume_checkpoint_ref
    )

    return {
        "continuation_mode": continuation_mode,
        "continuation_status": continuation_status,
        "pause_requested": False,
        "pause_reason": "",
        "pause_requested_at": "",
        "paused_at": "",
        "pause_effective_at": "",
        "interruption_reason": "",
        "resume_from_checkpoint": resume_from_checkpoint,
        "resume_checkpoint_ref": resume_checkpoint_ref,
        "resume_ready": False,
        "resume_token": "",
        "resume_reason": "",
        "resumed_from_run_id": resumed_from_run_id,
        "resumed_from_event_id": resumed_from_event_id,
        "resumed_from_stage": resumed_from_stage,
        "last_completed_step": "completed",
        "skipped_effects": _safe_list(skipped_effects),
        "effect_dispositions": _safe_list(effect_dispositions),
        "error_blocking_resume": False,
    }


def _build_supervisor_notebook_write_payload(
    *,
    notebook_info: Dict[str, Any],
    notebook_tool_calls: List[Dict[str, Any]],
    notebook_tool_results: List[Dict[str, Any]],
) -> Dict[str, Any]:
    return {
        "enabled": bool(notebook_info.get("enabled")),
        "status": _safe_str(notebook_info.get("status")),
        "message": _safe_str(notebook_info.get("message")),
        "reason_code": _safe_str(notebook_info.get("reason_code")),
        "relative_path": _safe_str(notebook_info.get("relative_path")),
        "effect_disposition": _safe_str(notebook_info.get("effect_disposition")),
        "effect_key": _safe_str(notebook_info.get("effect_key")),
        "tool_calls": notebook_tool_calls,
        "tool_results": notebook_tool_results,
    }


def _build_completed_runtime_state_patch(
    *,
    run_id: str,
    final_text: str,
    continuation_payload: Dict[str, Any],
    budget_patch_fn: Callable[[Dict[str, Any]], Dict[str, Any]],
    step_budget: Dict[str, Any],
    finished_at: str,
) -> Dict[str, Any]:
    continuation_mode = _safe_str(continuation_payload.get("continuation_mode"), "fresh")
    continuation_status = _safe_str(
        continuation_payload.get("continuation_status"),
        "completed_after_resume" if continuation_mode == "resumed" else "completed",
    )

    return {
        "current_run_id": run_id,
        "current_run_status": "completed",
        "runtime_control_run_id": run_id,
        "runtime_state_hint": "completed",
        "runtime_phase_hint": "idle",
        "last_run_finished_at": finished_at,
        "last_supervisor_phase": "completed",
        "last_supervisor_status": "success",
        "checkpoint_stage": "completed",
        "checkpoint_summary": _truncate_text(final_text, 280),
        "pause_requested": False,
        "pause_reason": "",
        "pause_requested_at": "",
        "paused_at": "",
        "pause_effective_at": "",
        "resume_ready": False,
        "resume_token": "",
        "resume_reason": "",
        "error_blocking_resume": False,
        "continuation_status": continuation_status,
        "current_delegate_role_id": "",
        "current_delegate_role_name": "",
        "current_delegate_index": 0,
        "current_delegate_total": 0,
        **continuation_payload,
        **budget_patch_fn(step_budget),
    }


def _build_finalize_runtime_request_args(
    *,
    supervisor_request_args: Dict[str, Any],
    continuation_payload: Dict[str, Any],
) -> Dict[str, Any]:
    req = dict(_safe_dict(supervisor_request_args))
    continuation = {
        **_safe_dict(req.get("continuation")),
        **dict(_safe_dict(continuation_payload)),
    }
    req["continuation"] = continuation

    for key in (
        "continuation_mode",
        "continuation_status",
        "resume_from_checkpoint",
        "resume_checkpoint_ref",
        "resume_ready",
        "resume_token",
        "resume_reason",
        "resumed_from_run_id",
        "resumed_from_event_id",
        "resumed_from_stage",
        "pause_requested",
        "pause_reason",
        "pause_requested_at",
        "paused_at",
        "pause_effective_at",
        "interruption_reason",
        "last_completed_step",
        "skipped_effects",
        "effect_dispositions",
        "error_blocking_resume",
    ):
        if key in continuation_payload:
            req[key] = continuation_payload.get(key)

    req["current_run_status"] = "completed"
    req["last_supervisor_phase"] = "completed"
    return req


def _build_supervisor_result_payload(
    *,
    rid: str,
    room_id: str,
    question: str,
    fallback_mode_used: str,
    fallback_response: str,
    fallback_message: str,
    supervisor_packet: Dict[str, Any],
    tool_calls: List[Dict[str, Any]],
    tool_results: List[Dict[str, Any]],
    default_result_view: str,
) -> Dict[str, Any]:
    packet = _safe_dict(supervisor_packet)

    envelope = _formal_envelope(
        request_id=rid,
        conv_id=room_id,
        rag_mode=_safe_str(packet.get("rag_mode")),
        mcp_overrides=_safe_dict(packet.get("mcp_overrides")),
        mode_used=_safe_str(packet.get("mode_used"), fallback_mode_used),
        rss_evidence=_safe_list(packet.get("rss_evidence")),
        market_evidence=_safe_list(packet.get("market_evidence")),
        evidence_query=_safe_str(packet.get("evidence_query"), question),
        evidence_tools=_safe_list(packet.get("evidence_tools")),
        evidence_result=packet.get("evidence_result") or _empty_evidence_result(question),
        qa_id=_safe_str(packet.get("qa_id")),
        group_id=_safe_str(packet.get("group_id")),
        citations=_safe_list(packet.get("citations")),
        response=_safe_str(packet.get("response"), fallback_response),
        status=_safe_str(packet.get("status"), "success"),
        result_state=_safe_str(packet.get("result_state"), "success"),
        summary=_safe_str(packet.get("summary")),
        final_response=_safe_str(packet.get("final_response"), fallback_response),
        error_code=_safe_str(packet.get("error_code")),
        result_view=_safe_str(packet.get("result_view"), default_result_view),
        visibility_source=_safe_str(packet.get("visibility_source")),
        source_observation_allowed=bool(packet.get("source_observation_allowed")),
        replay_recoverable=bool(packet.get("replay_recoverable")),
        remote_execution_may_have_completed=bool(packet.get("remote_execution_may_have_completed")),
        provider_trace=_safe_dict(packet.get("provider_trace")),
        grant_trace=_safe_dict(packet.get("grant_trace")),
        network_trace=_safe_dict(packet.get("network_trace")),
        consume_trace=_safe_dict(packet.get("consume_trace")),
        message=_safe_str(packet.get("message"), fallback_message),
        tool_calls=tool_calls,
        tool_results=tool_results,
        runtime_control_snapshot=_safe_dict(packet.get("runtime_control_snapshot")),
    )

    if not _safe_str(envelope.get("response")):
        envelope["response"] = _safe_str(fallback_response)
    if not _safe_str(envelope.get("final_response")):
        envelope["final_response"] = _safe_str(
            envelope.get("response"),
            _safe_str(fallback_response),
        )
    if not _safe_str(envelope.get("summary")):
        envelope["summary"] = _truncate_text(
            envelope.get("final_response") or fallback_response,
            500,
        )

    return envelope


def _build_supervisor_completed_event(
    *,
    room_id: str,
    rid: str,
    run_id: str,
    question: str,
    mode_used: str,
    plan_summary: str,
    delegate_events: List[Dict[str, Any]],
    delegate_packets: List[Dict[str, Any]],
    delegate_packets_non_empty: int,
    supervisor_model: str,
    supervisor_skill_strategy: str,
    supervisor_skills_info: Dict[str, Any],
    supervisor_packet: Dict[str, Any],
    synthesis_audit: Dict[str, Any],
    flattened_tool_calls: List[Dict[str, Any]],
    tool_results: List[Dict[str, Any]],
    fs_context: Dict[str, Any],
    fs_tool_calls: List[Dict[str, Any]],
    fs_tool_results: List[Dict[str, Any]],
    notebook_read_payload: Dict[str, Any],
    notebook_write_payload: Dict[str, Any],
    memory_read_payload: Dict[str, Any],
    memory_resume_payload: Dict[str, Any],
    memory_write_payload: Dict[str, Any],
    supervisor_skills_payload: Dict[str, Any],
    continuation_payload: Dict[str, Any],
    budget_patch_fn: Callable[[Dict[str, Any]], Dict[str, Any]],
    step_budget: Dict[str, Any],
    final_text: str,
    supervisor_evt: Dict[str, Any],
    new_id_fn: Callable[[str], str],
    utc_iso_fn: Callable[[], str],
) -> Dict[str, Any]:
    base_payload = _build_supervisor_result_payload(
        rid=rid,
        room_id=room_id,
        question=question,
        fallback_mode_used=mode_used,
        fallback_response=final_text,
        fallback_message="supervisor synthesis completed",
        supervisor_packet=supervisor_packet,
        tool_calls=flattened_tool_calls,
        tool_results=tool_results,
        default_result_view="full_result",
    )
    base_payload["summary"] = _truncate_text(
        _safe_str(base_payload.get("summary"), final_text),
        500,
    )

    return {
        "id": new_id_fn("evt"),
        "ts": utc_iso_fn(),
        "type": "room.supervisor",
        "room_id": room_id,
        "request_id": rid,
        "run_id": run_id,
        "trigger_event_id": supervisor_evt["id"],
        "payload": {
            **base_payload,
            "question": question,
            "plan_summary": plan_summary,
            "delegate_count": len(delegate_packets),
            "delegate_non_empty_count": delegate_packets_non_empty,
            "delegate_event_ids": [_safe_str(evt.get("id")) for evt in delegate_events],
            "role_ids": [_safe_str(item.get("role_id")) for item in delegate_packets],
            "role_names": [_safe_str(item.get("role_name")) for item in delegate_packets],
            "supervisor_model": supervisor_model,
            "phase": "completed",
            "supervisor_skill_strategy": _safe_str(
                supervisor_skills_info.get("strategy") or supervisor_skill_strategy,
                "builtin_plus_custom",
            ),
            "synthesis_audit": synthesis_audit,
            "supervisor_fs_read": {
                "enabled": bool(fs_context.get("enabled")),
                "status": _safe_str(fs_context.get("status")),
                "reason": _safe_str(fs_context.get("reason")),
                "focus_root": _safe_str(fs_context.get("focus_root")),
                "scope": _safe_str(fs_context.get("scope")),
                "documents_count": int(fs_context.get("documents_count") or 0),
                "target_paths": _safe_list(fs_context.get("target_paths")),
                "content_status": _safe_str(fs_context.get("content_status")),
                "tool_calls": fs_tool_calls,
                "tool_results": fs_tool_results,
            },
            "supervisor_notebook_read": dict(notebook_read_payload),
            "supervisor_notebook_write": dict(notebook_write_payload),
            "supervisor_memory_read": dict(memory_read_payload),
            "supervisor_memory_resume": dict(memory_resume_payload),
            "supervisor_memory_write": dict(memory_write_payload),
            "supervisor_skills": dict(supervisor_skills_payload),
            **continuation_payload,
            **budget_patch_fn(step_budget),
            "checkpoint_stage": "completed",
            "checkpoint_summary": _truncate_text(final_text, 280),
        },
    }


def _build_final_event(
    *,
    room_id: str,
    rid: str,
    run_id: str,
    question: str,
    mode_used: str,
    plan_summary: str,
    delegate_packets: List[Dict[str, Any]],
    supervisor_skill_strategy: str,
    supervisor_skills_info: Dict[str, Any],
    supervisor_packet: Dict[str, Any],
    flattened_tool_calls: List[Dict[str, Any]],
    tool_results: List[Dict[str, Any]],
    fs_context: Dict[str, Any],
    fs_tool_calls: List[Dict[str, Any]],
    fs_tool_results: List[Dict[str, Any]],
    notebook_read_payload: Dict[str, Any],
    notebook_write_payload: Dict[str, Any],
    memory_read_payload: Dict[str, Any],
    memory_resume_payload: Dict[str, Any],
    memory_write_payload: Dict[str, Any],
    supervisor_skills_payload: Dict[str, Any],
    continuation_payload: Dict[str, Any],
    budget_patch_fn: Callable[[Dict[str, Any]], Dict[str, Any]],
    step_budget: Dict[str, Any],
    final_text: str,
    trigger_event_id: str,
    new_id_fn: Callable[[str], str],
    utc_iso_fn: Callable[[], str],
) -> Dict[str, Any]:
    base_payload = _build_supervisor_result_payload(
        rid=rid,
        room_id=room_id,
        question=question,
        fallback_mode_used=mode_used,
        fallback_response=final_text,
        fallback_message="supervisor synthesis completed",
        supervisor_packet=supervisor_packet,
        tool_calls=flattened_tool_calls,
        tool_results=tool_results,
        default_result_view="final_only",
    )

    final_response = _safe_str(base_payload.get("final_response"), final_text) or final_text
    base_payload["response"] = _safe_str(base_payload.get("response"), final_response) or final_response
    base_payload["final_response"] = final_response
    base_payload["summary"] = _truncate_text(
        _safe_str(base_payload.get("summary"), final_response),
        500,
    )

    return {
        "id": new_id_fn("evt"),
        "ts": utc_iso_fn(),
        "type": "room.final",
        "room_id": room_id,
        "request_id": rid,
        "run_id": run_id,
        "trigger_event_id": trigger_event_id,
        "payload": {
            **base_payload,
            "content": final_response,
            "plan_summary": plan_summary,
            "delegate_count": len(delegate_packets),
            "supervisor_skill_strategy": _safe_str(
                supervisor_skills_info.get("strategy") or supervisor_skill_strategy,
                "builtin_plus_custom",
            ),
            "supervisor_fs_read": {
                "enabled": bool(fs_context.get("enabled")),
                "status": _safe_str(fs_context.get("status")),
                "reason": _safe_str(fs_context.get("reason")),
                "focus_root": _safe_str(fs_context.get("focus_root")),
                "scope": _safe_str(fs_context.get("scope")),
                "documents_count": int(fs_context.get("documents_count") or 0),
                "target_paths": _safe_list(fs_context.get("target_paths")),
                "content_status": _safe_str(fs_context.get("content_status")),
                "tool_calls": fs_tool_calls,
                "tool_results": fs_tool_results,
            },
            "supervisor_notebook_read": dict(notebook_read_payload),
            "supervisor_notebook_write": dict(notebook_write_payload),
            "supervisor_memory_read": dict(memory_read_payload),
            "supervisor_memory_resume": dict(memory_resume_payload),
            "supervisor_memory_write": dict(memory_write_payload),
            "supervisor_skills": dict(supervisor_skills_payload),
            **continuation_payload,
            **budget_patch_fn(step_budget),
            "checkpoint_stage": "completed",
            "checkpoint_summary": _truncate_text(final_text, 280),
        },
    }


def _run_supervisor_finalize_stage(
    *,
    room_id: str,
    question: str,
    mode_used: str,
    run_id: str,
    trigger_event_id: str,
    rid: str,
    plan_evt: Dict[str, Any],
    mcp: Dict[str, Any],
    fs_context: Dict[str, Any],
    notebook_read_info: Dict[str, Any],
    memory_read_info: Dict[str, Any],
    memory_resume_info: Dict[str, Any],
    supervisor_request_args: Dict[str, Any],
    delegate_events: List[Dict[str, Any]],
    delegate_packets: List[Dict[str, Any]],
    plan_summary: str,
    step_budget: Dict[str, Any],
    supervisor_skill_strategy: str,
    supervisor_skills_info: Dict[str, Any],
    supervisor_skills_payload: Dict[str, Any],
    supervisor_notebook_read_payload: Dict[str, Any],
    supervisor_memory_read_payload: Dict[str, Any],
    supervisor_memory_resume_payload: Dict[str, Any],
    supervisor_evt: Dict[str, Any],
    supervisor_model: str,
    supervisor_packet: Dict[str, Any],
    final_text: str,
    synthesis_audit: Dict[str, Any],
    prompt_delegate_packets: List[Dict[str, Any]],
    persistence_stage: Dict[str, Any],
    budget_patch_fn: Callable[[Dict[str, Any]], Dict[str, Any]],
    set_room_state_patch_fn: Callable[[str, Dict[str, Any]], Any],
    append_room_event_fn: Callable[[str, Dict[str, Any]], Any],
    touch_room_updated_at_fn: Callable[[str], Any],
    update_room_last_message_fn: Callable[[str, str], Any],
    clear_run_state_fn: Callable[[str], Any],
    new_id_fn: Callable[[str], str],
    utc_iso_fn: Callable[[], str],
) -> Tuple[Dict[str, Any], List[Dict[str, Any]], Dict[str, Any]]:
    notebook_info = _safe_dict(persistence_stage.get("notebook_info"))
    memory_write_info_initial = dict(_safe_dict(persistence_stage.get("memory_write_info_initial")))
    memory_write_info = dict(_safe_dict(persistence_stage.get("memory_write_info")))
    supervisor_memory_write_payload = dict(_safe_dict(persistence_stage.get("supervisor_memory_write_payload")))
    notebook_read_tool_result = persistence_stage.get("notebook_read_tool_result")
    memory_read_tool_result = _safe_dict(persistence_stage.get("memory_read_tool_result"))
    memory_resume_tool_result = _safe_dict(persistence_stage.get("memory_resume_tool_result"))
    flattened_tool_calls = _safe_list(persistence_stage.get("flattened_tool_calls"))
    flattened_tool_results = _safe_list(persistence_stage.get("flattened_tool_results"))
    delegate_summary_result = _safe_dict(persistence_stage.get("delegate_summary_result"))
    supervisor_skills_result = _safe_dict(persistence_stage.get("supervisor_skills_result"))
    fs_tool_calls = _safe_list(persistence_stage.get("fs_tool_calls"))
    fs_tool_results = _safe_list(persistence_stage.get("fs_tool_results"))
    notebook_tool_calls = _safe_list(persistence_stage.get("notebook_tool_calls"))
    notebook_tool_results = _safe_list(persistence_stage.get("notebook_tool_results"))
    novelty_guard = _safe_dict(persistence_stage.get("novelty_guard"))
    attribution_result = _safe_dict(persistence_stage.get("attribution_result"))
    effect_dispositions = _safe_list(persistence_stage.get("effect_dispositions"))
    skipped_effects = _safe_list(persistence_stage.get("skipped_effects"))

    memory_write_effect_disposition = _safe_str(memory_write_info.get("effect_disposition"))
    if not memory_write_effect_disposition:
        memory_write_effect_disposition = _safe_str(memory_write_info_initial.get("effect_disposition"))
        if memory_write_effect_disposition:
            memory_write_info["effect_disposition"] = memory_write_effect_disposition

    memory_write_effect_key = _safe_str(memory_write_info.get("effect_key"))
    if not memory_write_effect_key:
        memory_write_effect_key = _safe_str(memory_write_info_initial.get("effect_key"))
        if memory_write_effect_key:
            memory_write_info["effect_key"] = memory_write_effect_key

    if (
        _safe_str(memory_write_info_initial.get("status")) == "success"
        and _safe_str(
            memory_write_info_initial.get("effect_disposition"),
            memory_write_effect_disposition,
        ) == "execute"
    ):
        try:
            updated_memory_write_info = write_supervisor_memory_sidecar(
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
            updated_memory_write_info = dict(_safe_dict(updated_memory_write_info))
            if not _safe_str(updated_memory_write_info.get("effect_disposition")):
                updated_memory_write_info["effect_disposition"] = memory_write_effect_disposition or "execute"
            if not _safe_str(updated_memory_write_info.get("effect_key")):
                updated_memory_write_info["effect_key"] = memory_write_effect_key
            memory_write_info = updated_memory_write_info
        except Exception:
            memory_write_info = dict(memory_write_info_initial)
            if not _safe_str(memory_write_info.get("effect_disposition")):
                memory_write_info["effect_disposition"] = memory_write_effect_disposition or "execute"
            if not _safe_str(memory_write_info.get("effect_key")):
                memory_write_info["effect_key"] = memory_write_effect_key

    supervisor_memory_write_payload = _build_supervisor_memory_write_payload_from_info(memory_write_info)
    memory_write_tool_result = _build_supervisor_memory_write_tool_result_from_info(memory_write_info)

    completed_evt_tool_results = _build_supervisor_event_tool_results(
        flattened_tool_results=flattened_tool_results,
        notebook_read_tool_result=notebook_read_tool_result,
        memory_read_tool_result=memory_read_tool_result,
        memory_resume_tool_result=memory_resume_tool_result,
        memory_write_result=memory_write_tool_result,
        delegate_summary_result=delegate_summary_result,
        novelty_guard=novelty_guard,
        attribution_result=attribution_result,
        supervisor_skills_result=supervisor_skills_result,
    )

    final_evt_tool_results = _build_supervisor_event_tool_results(
        flattened_tool_results=flattened_tool_results,
        notebook_read_tool_result=notebook_read_tool_result,
        memory_read_tool_result=memory_read_tool_result,
        memory_resume_tool_result=memory_resume_tool_result,
        memory_write_result=memory_write_tool_result,
        delegate_summary_result=delegate_summary_result,
        novelty_guard=novelty_guard,
        attribution_result=attribution_result,
        supervisor_skills_result=supervisor_skills_result,
    )

    notebook_write_payload = _build_supervisor_notebook_write_payload(
        notebook_info=notebook_info,
        notebook_tool_calls=notebook_tool_calls,
        notebook_tool_results=notebook_tool_results,
    )
    continuation_payload = _build_completion_continuation_payload(
        supervisor_request_args=supervisor_request_args,
        memory_resume_info=memory_resume_info,
        skipped_effects=skipped_effects,
        effect_dispositions=effect_dispositions,
    )

    supervisor_completed_evt = _build_supervisor_completed_event(
        room_id=room_id,
        rid=rid,
        run_id=run_id,
        question=question,
        mode_used=mode_used,
        plan_summary=plan_summary,
        delegate_events=delegate_events,
        delegate_packets=delegate_packets,
        delegate_packets_non_empty=int(supervisor_evt["payload"].get("delegate_non_empty_count") or 0),
        supervisor_model=supervisor_model,
        supervisor_skill_strategy=supervisor_skill_strategy,
        supervisor_skills_info=supervisor_skills_info,
        supervisor_packet=supervisor_packet,
        synthesis_audit=synthesis_audit,
        flattened_tool_calls=flattened_tool_calls,
        tool_results=completed_evt_tool_results,
        fs_context=fs_context,
        fs_tool_calls=fs_tool_calls,
        fs_tool_results=fs_tool_results,
        notebook_read_payload=supervisor_notebook_read_payload,
        notebook_write_payload=notebook_write_payload,
        memory_read_payload=supervisor_memory_read_payload,
        memory_resume_payload=supervisor_memory_resume_payload,
        memory_write_payload=supervisor_memory_write_payload,
        supervisor_skills_payload=supervisor_skills_payload,
        continuation_payload=continuation_payload,
        budget_patch_fn=budget_patch_fn,
        step_budget=step_budget,
        final_text=final_text,
        supervisor_evt=supervisor_evt,
        new_id_fn=new_id_fn,
        utc_iso_fn=utc_iso_fn,
    )

    final_evt = _build_final_event(
        room_id=room_id,
        rid=rid,
        run_id=run_id,
        question=question,
        mode_used=mode_used,
        plan_summary=plan_summary,
        delegate_packets=delegate_packets,
        supervisor_skill_strategy=supervisor_skill_strategy,
        supervisor_skills_info=supervisor_skills_info,
        supervisor_packet=supervisor_packet,
        flattened_tool_calls=flattened_tool_calls,
        tool_results=final_evt_tool_results,
        fs_context=fs_context,
        fs_tool_calls=fs_tool_calls,
        fs_tool_results=fs_tool_results,
        notebook_read_payload=supervisor_notebook_read_payload,
        notebook_write_payload=notebook_write_payload,
        memory_read_payload=supervisor_memory_read_payload,
        memory_resume_payload=supervisor_memory_resume_payload,
        memory_write_payload=supervisor_memory_write_payload,
        supervisor_skills_payload=supervisor_skills_payload,
        continuation_payload=continuation_payload,
        budget_patch_fn=budget_patch_fn,
        step_budget=step_budget,
        final_text=final_text,
        trigger_event_id=supervisor_completed_evt["id"],
        new_id_fn=new_id_fn,
        utc_iso_fn=utc_iso_fn,
    )

    append_room_event_fn(room_id, supervisor_completed_evt)
    append_room_event_fn(room_id, final_evt)

    touch_room_updated_at_fn(room_id)
    update_room_last_message_fn(room_id, final_evt["id"])

    finished_at = utc_iso_fn()

    set_room_state_patch_fn(
        room_id,
        _build_completed_runtime_state_patch(
            run_id=run_id,
            final_text=final_text,
            continuation_payload=continuation_payload,
            budget_patch_fn=budget_patch_fn,
            step_budget=step_budget,
            finished_at=finished_at,
        ),
    )

    runtime_request_args = _build_finalize_runtime_request_args(
        supervisor_request_args=supervisor_request_args,
        continuation_payload=continuation_payload,
    )

    _patch_supervisor_runtime_state(
        room_id,
        phase="completed",
        status="success",
        plan_summary=plan_summary,
        fs_context=fs_context,
        notebook_read_result=notebook_read_info,
        notebook_result=notebook_info,
        memory_read_result=memory_read_info,
        memory_resume_result=memory_resume_info,
        memory_result=memory_write_info,
        request_args=runtime_request_args,
        run_id=run_id,
        finished=True,
        step_budget_total=_safe_non_negative_int(step_budget.get("step_budget_total"), 0),
        step_budget_used=_safe_non_negative_int(step_budget.get("step_budget_used"), 0),
        step_budget_remaining=_safe_non_negative_int(step_budget.get("step_budget_remaining"), 0),
        budget_status=_safe_str(step_budget.get("budget_status")),
        budget_exhausted=bool(step_budget.get("budget_exhausted")),
        checkpoint_stage="completed",
        checkpoint_summary=_truncate_text(final_text, 280),
        interruption_reason="",
    )

    memory_checkpoint = _safe_dict(memory_read_info.get("checkpoint"))
    memory_resume_from_read = _safe_dict(memory_read_info.get("resume"))

    _append_supervisor_audit_relation(
        room_id,
        {
            "room_id": room_id,
            "request_id": rid,
            "run_id": run_id,
            "plan_event_id": plan_evt["id"],
            "supervisor_event_id": supervisor_completed_evt["id"],
            "final_event_id": final_evt["id"],
            "trigger_event_id": trigger_event_id,
            "recorded_at": utc_iso_fn(),
            "continuation": dict(continuation_payload),
            "effect_dispositions": _safe_list(effect_dispositions),
            "skipped_effects": _safe_list(skipped_effects),
            "fs_read": {
                "enabled": bool(fs_context.get("enabled")),
                "status": _safe_str(fs_context.get("status")),
                "reason": _safe_str(fs_context.get("reason")),
                "focus_root": _safe_str(fs_context.get("focus_root")),
                "scope": _safe_str(fs_context.get("scope")),
                "documents_count": int(fs_context.get("documents_count") or 0),
                "target_paths": _safe_list(fs_context.get("target_paths")),
                "content_status": _safe_str(fs_context.get("content_status")),
                "tool_calls": fs_tool_calls,
                "tool_results": fs_tool_results,
                "at": _safe_str(fs_context.get("at")),
            },
            "notebook_read": {
                "enabled": bool(notebook_read_info.get("enabled")),
                "status": _safe_str(notebook_read_info.get("status")),
                "message": _safe_str(notebook_read_info.get("message")),
                "relative_path": _safe_str(notebook_read_info.get("relative_path")),
                "documents_count": int(notebook_read_info.get("documents_count") or 0),
                "source_kind": _safe_str(notebook_read_info.get("source_kind")),
                "tool_calls": _safe_list(notebook_read_info.get("tool_calls")),
                "tool_results": _safe_list(notebook_read_info.get("tool_results")),
                "at": _safe_str(notebook_read_info.get("recorded_at") or notebook_read_info.get("at")),
            },
            "notebook_write": {
                "enabled": bool(notebook_info.get("enabled")),
                "status": _safe_str(notebook_info.get("status")),
                "message": _safe_str(notebook_info.get("message")),
                "reason_code": _safe_str(notebook_info.get("reason_code")),
                "relative_path": _safe_str(notebook_info.get("relative_path")),
                "effect_disposition": _safe_str(notebook_info.get("effect_disposition")),
                "effect_key": _safe_str(notebook_info.get("effect_key")),
                "tool_calls": notebook_tool_calls,
                "tool_results": notebook_tool_results,
                "at": _safe_str(notebook_info.get("recorded_at") or notebook_info.get("at")),
            },
            "memory_read": {
                "enabled": bool(memory_read_info.get("enabled")),
                "status": _safe_str(memory_read_info.get("status")),
                "message": _safe_str(memory_read_info.get("message")),
                "reason_code": _safe_str(memory_read_info.get("reason_code")),
                "relative_path": _safe_str(memory_read_info.get("relative_path")),
                "source_kind": _safe_str(memory_read_info.get("source_kind")),
                "version": int(memory_read_info.get("version") or 0),
                "checkpoint": dict(memory_checkpoint),
                "resume": dict(memory_resume_from_read),
                "tool_calls": _safe_list(memory_read_info.get("tool_calls")),
                "tool_results": _safe_list(memory_read_info.get("tool_results")),
                "at": _safe_str(memory_read_info.get("recorded_at") or memory_read_info.get("at")),
            },
            "memory_resume": {
                "status": _safe_str(memory_resume_info.get("status")),
                "decision": _safe_str(memory_resume_info.get("decision")),
                "reason": _safe_str(memory_resume_info.get("reason")),
                "resume_ready": bool(memory_resume_info.get("resume_ready")),
                "relative_path": _safe_str(memory_resume_info.get("relative_path")),
                "checkpoint_stage": _safe_str(memory_resume_info.get("checkpoint_stage")),
                "checkpoint_summary": _safe_str(memory_resume_info.get("checkpoint_summary")),
                "recovery_hint": _safe_str(memory_resume_info.get("recovery_hint")),
            },
            "memory_write": {
                "enabled": bool(memory_write_info.get("enabled")),
                "status": _safe_str(memory_write_info.get("status")),
                "message": _safe_str(memory_write_info.get("message")),
                "reason_code": _safe_str(memory_write_info.get("reason_code")),
                "relative_path": _safe_str(memory_write_info.get("relative_path")),
                "bytes_written": int(memory_write_info.get("bytes_written") or 0),
                "checkpoint_stage": _safe_str(memory_write_info.get("checkpoint_stage")),
                "checkpoint_summary": _safe_str(memory_write_info.get("checkpoint_summary")),
                "resume_decision": _safe_str(memory_write_info.get("resume_decision")),
                "resume_reason": _safe_str(memory_write_info.get("resume_reason")),
                "source_kind": _safe_str(memory_write_info.get("source_kind")),
                "effect_disposition": _safe_str(memory_write_info.get("effect_disposition")),
                "effect_key": _safe_str(memory_write_info.get("effect_key")),
                "tool_calls": _safe_list(memory_write_info.get("tool_calls")),
                "tool_results": _safe_list(memory_write_info.get("tool_results")),
                "at": _safe_str(memory_write_info.get("recorded_at") or memory_write_info.get("at")),
            },
            "supervisor_skills": dict(supervisor_skills_payload),
            "synthesis": synthesis_audit,
        },
    )

    return plan_evt, delegate_events, final_evt


__all__ = [
    "_run_supervisor_finalize_stage",
]
