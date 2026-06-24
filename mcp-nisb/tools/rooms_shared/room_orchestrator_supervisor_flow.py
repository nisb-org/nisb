from __future__ import annotations

from typing import Any, Callable, Dict, List, Tuple

from .room_orchestrator_continuation import _maybe_interrupt_at_boundary
from .room_orchestrator_supervisor_finalize import _run_supervisor_finalize_stage
from .room_orchestrator_supervisor_persistence import _run_supervisor_persistence_stage
from .room_orchestrator_supervisor_synthesis import _run_supervisor_synthesis_stage


def _safe_str(value: Any, default: str = "") -> str:
    if value is None:
        return default
    text = str(value).strip()
    return text if text else default


def _safe_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _safe_list(value: Any) -> List[Any]:
    return value if isinstance(value, list) else []


def _truncate_text(value: Any, limit: int = 280) -> str:
    text = _safe_str(value)
    if not text:
        return ""
    if len(text) <= max(0, int(limit or 0)):
        return text
    clipped = max(0, int(limit or 0) - 1)
    return f"{text[:clipped].rstrip()}…"


def _checkpoint_summary_from_stage(
    *,
    synthesis_stage: Dict[str, Any],
    fallback: str = "",
) -> str:
    stage_row = _safe_dict(synthesis_stage)
    supervisor_evt = _safe_dict(stage_row.get("supervisor_evt"))
    supervisor_payload = _safe_dict(supervisor_evt.get("payload"))

    return _truncate_text(
        supervisor_payload.get("summary")
        or stage_row.get("final_text")
        or fallback,
        280,
    )


def _runtime_stop_requested(
    *,
    room_id: str,
    run_id: str,
    load_state_doc_fn: Callable[[str], Dict[str, Any]],
) -> bool:
    target_run_id = _safe_str(run_id)
    if not target_run_id:
        return False

    try:
        row = _safe_dict(load_state_doc_fn(room_id))
    except Exception:
        row = {}

    current_run_id = _safe_str(row.get("current_run_id"))
    runtime_control_run_id = _safe_str(row.get("runtime_control_run_id"))

    def _truthy_stop(value: Any) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return value != 0
        text = _safe_str(value).strip().lower()
        return text in {
            "1",
            "true",
            "yes",
            "y",
            "on",
            "stop",
            "stopped",
            "abort",
            "aborted",
            "cancel",
            "cancelled",
            "canceled",
        }

    explicit_stop_requested = any(
        _truthy_stop(row.get(key))
        for key in (
            "stop_requested",
            "abort_requested",
            "cancel_requested",
            "runtime_stop_requested",
            "runtime_abort_requested",
            "runtime_cancel_requested",
        )
    )

    control_action = _safe_str(
        row.get("runtime_control_action")
        or row.get("runtime_control_command")
        or row.get("runtime_action")
        or row.get("control_action")
    ).strip().lower()

    if control_action in {"stop", "stopped", "abort", "aborted", "cancel", "cancelled", "canceled"}:
        explicit_stop_requested = True

    stop_run_id = _safe_str(
        row.get("stop_run_id")
        or row.get("abort_run_id")
        or row.get("cancel_run_id")
        or row.get("runtime_stop_run_id")
        or row.get("runtime_abort_run_id")
        or row.get("runtime_cancel_run_id")
        or runtime_control_run_id
    )

    if current_run_id and current_run_id != target_run_id:
        return True

    if not explicit_stop_requested:
        return False

    if stop_run_id and stop_run_id != target_run_id:
        return False

    if current_run_id == target_run_id:
        return True

    if stop_run_id == target_run_id:
        return True

    return False


def _mark_runtime_stop_observed(
    *,
    room_id: str,
    run_id: str,
    set_room_state_patch_fn: Callable[[str, Dict[str, Any]], Any],
    utc_iso_fn: Callable[[], str],
) -> None:
    try:
        set_room_state_patch_fn(
            room_id,
            {
                "current_run_id": "",
                "current_request_id": "",
                "current_run_status": "aborted",
                "current_delegate_role_id": "",
                "current_delegate_role_name": "",
                "current_delegate_index": 0,
                "current_delegate_total": 0,
                "runtime_control_run_id": _safe_str(run_id),
                "runtime_state_hint": "idle",
                "runtime_phase_hint": "idle",
                "continuation_status": "aborted",
                "last_run_finished_at": utc_iso_fn(),
            },
        )
    except Exception:
        pass


def _build_runtime_stopped_result(
    *,
    run_id: str,
    step_budget: Dict[str, Any],
) -> Tuple[Dict[str, Any], List[Dict[str, Any]], Dict[str, Any]]:
    packet = {
        "status": "aborted",
        "message": "room runtime stopped",
        "run_id": run_id,
        "response": "",
        "final_response": "",
        "result_state": "aborted",
        "tool_calls": [],
        "tool_results": [],
    }
    return packet, [], step_budget


def _run_supervisor_synthesis_flow(
    *,
    room_id: str,
    question: str,
    model_name: str,
    mode_used: str,
    run_id: str,
    trigger_event_id: str,
    rid: str,
    plan_evt: Dict[str, Any],
    total: int,
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
    step_budget: Dict[str, Any],
    supervisor_skill_strategy: str,
    supervisor_skills_info: Dict[str, Any],
    supervisor_skills_payload: Dict[str, Any],
    supervisor_notebook_read_payload: Dict[str, Any],
    supervisor_memory_read_payload: Dict[str, Any],
    supervisor_memory_resume_payload: Dict[str, Any],
    consume_step_budget_fn: Callable[[Dict[str, Any], int], Dict[str, Any]],
    budget_patch_fn: Callable[[Dict[str, Any]], Dict[str, Any]],
    interrupt_supervisor_run_fn: Callable[..., Tuple[Dict[str, Any], List[Dict[str, Any]], Dict[str, Any]]],
    set_room_state_patch_fn: Callable[[str, Dict[str, Any]], Any],
    append_room_event_fn: Callable[[str, Dict[str, Any]], Any],
    touch_room_updated_at_fn: Callable[[str], Any],
    update_room_last_message_fn: Callable[[str, str], Any],
    clear_run_state_fn: Callable[[str], Any],
    load_state_doc_fn: Callable[[str], Dict[str, Any]],
    new_id_fn: Callable[[str], str],
    utc_iso_fn: Callable[[], str],
) -> Tuple[Dict[str, Any], List[Dict[str, Any]], Dict[str, Any]]:
    if _runtime_stop_requested(
        room_id=room_id,
        run_id=run_id,
        load_state_doc_fn=load_state_doc_fn,
    ):
        _mark_runtime_stop_observed(
            room_id=room_id,
            run_id=run_id,
            set_room_state_patch_fn=set_room_state_patch_fn,
            utc_iso_fn=utc_iso_fn,
        )
        return _build_runtime_stopped_result(run_id=run_id, step_budget=step_budget)

    synthesis_stage = _run_supervisor_synthesis_stage(
        room_id=room_id,
        question=question,
        model_name=model_name,
        mode_used=mode_used,
        run_id=run_id,
        rid=rid,
        plan_evt=plan_evt,
        total=total,
        fs_context=fs_context,
        notebook_read_info=notebook_read_info,
        memory_read_info=memory_read_info,
        memory_resume_info=memory_resume_info,
        supervisor_request_args=supervisor_request_args,
        delegate_events=delegate_events,
        delegate_packets=delegate_packets,
        plan_summary=plan_summary,
        step_budget=step_budget,
        supervisor_skill_strategy=supervisor_skill_strategy,
        supervisor_skills_info=supervisor_skills_info,
        supervisor_skills_payload=supervisor_skills_payload,
        supervisor_notebook_read_payload=supervisor_notebook_read_payload,
        supervisor_memory_read_payload=supervisor_memory_read_payload,
        supervisor_memory_resume_payload=supervisor_memory_resume_payload,
        consume_step_budget_fn=consume_step_budget_fn,
        budget_patch_fn=budget_patch_fn,
        interrupt_supervisor_run_fn=interrupt_supervisor_run_fn,
        append_room_event_fn=append_room_event_fn,
        touch_room_updated_at_fn=touch_room_updated_at_fn,
        update_room_last_message_fn=update_room_last_message_fn,
        set_room_state_patch_fn=set_room_state_patch_fn,
        clear_run_state_fn=clear_run_state_fn,
        new_id_fn=new_id_fn,
        utc_iso_fn=utc_iso_fn,
    )
    if synthesis_stage.get("interrupted"):
        return synthesis_stage["result"]

    if _runtime_stop_requested(
        room_id=room_id,
        run_id=run_id,
        load_state_doc_fn=load_state_doc_fn,
    ):
        _mark_runtime_stop_observed(
            room_id=room_id,
            run_id=run_id,
            set_room_state_patch_fn=set_room_state_patch_fn,
            utc_iso_fn=utc_iso_fn,
        )
        return _build_runtime_stopped_result(run_id=run_id, step_budget=step_budget)

    synthesis_checkpoint_summary = _checkpoint_summary_from_stage(
        synthesis_stage=synthesis_stage,
        fallback=plan_summary,
    )

    synthesis_boundary_interrupt = _maybe_interrupt_at_boundary(
        checkpoint_stage="supervisor_synthesis",
        room_state=_safe_dict(load_state_doc_fn(room_id)),
        room_id=room_id,
        question=question,
        mode_used=mode_used,
        run_id=run_id,
        trigger_event_id=trigger_event_id,
        rid=rid,
        plan_summary=plan_summary,
        checkpoint_summary=synthesis_checkpoint_summary,
        supervisor_request_args=supervisor_request_args,
        fs_context=fs_context,
        notebook_read_info=notebook_read_info,
        memory_read_info=memory_read_info,
        memory_resume_info=memory_resume_info,
        budget=_safe_dict(synthesis_stage.get("step_budget")) or _safe_dict(step_budget),
        append_room_event_fn=append_room_event_fn,
        touch_room_updated_at_fn=touch_room_updated_at_fn,
        update_room_last_message_fn=update_room_last_message_fn,
        set_room_state_patch_fn=set_room_state_patch_fn,
        clear_run_state_fn=clear_run_state_fn,
        new_id_fn=new_id_fn,
        utc_iso_fn=utc_iso_fn,
    )
    if synthesis_boundary_interrupt is not None:
        return synthesis_boundary_interrupt

    persistence_stage = _run_supervisor_persistence_stage(
        room_id=room_id,
        question=question,
        run_id=run_id,
        mcp=mcp,
        fs_context=fs_context,
        notebook_read_info=notebook_read_info,
        memory_read_info=memory_read_info,
        memory_resume_info=memory_resume_info,
        supervisor_request_args=supervisor_request_args,
        delegate_events=delegate_events,
        role_message_events=role_message_events,
        delegate_packets=delegate_packets,
        plan_summary=plan_summary,
        prompt_delegate_packets=synthesis_stage["prompt_delegate_packets"],
        audit_delegate_packets=synthesis_stage["audit_delegate_packets"],
        supervisor_evt=synthesis_stage["supervisor_evt"],
        supervisor_packet=synthesis_stage["supervisor_packet"],
        final_text=synthesis_stage["final_text"],
        novelty_guard=synthesis_stage["novelty_guard"],
        attribution_result=synthesis_stage["attribution_result"],
        supervisor_skills_info=supervisor_skills_info,
        supervisor_skills_payload=supervisor_skills_payload,
        utc_iso_fn=utc_iso_fn,
    )

    persistence_boundary_interrupt = _maybe_interrupt_at_boundary(
        checkpoint_stage="supervisor_persistence",
        room_state=_safe_dict(load_state_doc_fn(room_id)),
        room_id=room_id,
        question=question,
        mode_used=mode_used,
        run_id=run_id,
        trigger_event_id=trigger_event_id,
        rid=rid,
        plan_summary=plan_summary,
        checkpoint_summary=synthesis_checkpoint_summary,
        supervisor_request_args=supervisor_request_args,
        fs_context=fs_context,
        notebook_read_info=notebook_read_info,
        memory_read_info=memory_read_info,
        memory_resume_info=memory_resume_info,
        budget=_safe_dict(synthesis_stage.get("step_budget")) or _safe_dict(step_budget),
        skipped_effects=_safe_list(persistence_stage.get("skipped_effects")),
        effect_dispositions=_safe_list(persistence_stage.get("effect_dispositions")),
        append_room_event_fn=append_room_event_fn,
        touch_room_updated_at_fn=touch_room_updated_at_fn,
        update_room_last_message_fn=update_room_last_message_fn,
        set_room_state_patch_fn=set_room_state_patch_fn,
        clear_run_state_fn=clear_run_state_fn,
        new_id_fn=new_id_fn,
        utc_iso_fn=utc_iso_fn,
    )
    if persistence_boundary_interrupt is not None:
        return persistence_boundary_interrupt

    return _run_supervisor_finalize_stage(
        room_id=room_id,
        question=question,
        mode_used=mode_used,
        run_id=run_id,
        trigger_event_id=trigger_event_id,
        rid=rid,
        plan_evt=plan_evt,
        mcp=mcp,
        fs_context=fs_context,
        notebook_read_info=notebook_read_info,
        memory_read_info=memory_read_info,
        memory_resume_info=memory_resume_info,
        supervisor_request_args=supervisor_request_args,
        delegate_events=delegate_events,
        delegate_packets=delegate_packets,
        plan_summary=plan_summary,
        step_budget=synthesis_stage["step_budget"],
        supervisor_skill_strategy=supervisor_skill_strategy,
        supervisor_skills_info=supervisor_skills_info,
        supervisor_skills_payload=supervisor_skills_payload,
        supervisor_notebook_read_payload=supervisor_notebook_read_payload,
        supervisor_memory_read_payload=supervisor_memory_read_payload,
        supervisor_memory_resume_payload=supervisor_memory_resume_payload,
        supervisor_evt=synthesis_stage["supervisor_evt"],
        supervisor_model=synthesis_stage["supervisor_model"],
        supervisor_packet=synthesis_stage["supervisor_packet"],
        final_text=synthesis_stage["final_text"],
        synthesis_audit=synthesis_stage["synthesis_audit"],
        prompt_delegate_packets=synthesis_stage["prompt_delegate_packets"],
        persistence_stage=persistence_stage,
        budget_patch_fn=budget_patch_fn,
        set_room_state_patch_fn=set_room_state_patch_fn,
        append_room_event_fn=append_room_event_fn,
        touch_room_updated_at_fn=touch_room_updated_at_fn,
        update_room_last_message_fn=update_room_last_message_fn,
        clear_run_state_fn=clear_run_state_fn,
        new_id_fn=new_id_fn,
        utc_iso_fn=utc_iso_fn,
    )


__all__ = [
    "_run_supervisor_synthesis_flow",
]

