from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Tuple


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
    max_len = max(0, int(limit or 0))
    if not text or max_len <= 0:
        return text[:max_len] if max_len > 0 else ""
    if len(text) <= max_len:
        return text
    if max_len == 1:
        return "…"
    return f"{text[: max_len - 1].rstrip()}…"


def _normalize_non_negative_int(value: Any, fallback: int = 0) -> int:
    try:
        return max(0, int(value))
    except Exception:
        return max(0, int(fallback))


def _as_bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        text = value.strip().lower()
        if text in {"1", "true", "yes", "on"}:
            return True
        if text in {"0", "false", "no", "off"}:
            return False
    return default


def _coalesce_str(*values: Any, default: str = "") -> str:
    for value in values:
        text = _safe_str(value)
        if text:
            return text
    return default


def _coalesce_list(*values: Any) -> List[Any]:
    for value in values:
        if isinstance(value, list):
            return value
    return []


def _coalesce_bool(*values: Any, default: bool = False) -> bool:
    for value in values:
        if value is None:
            continue
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return bool(value)
        if isinstance(value, str):
            text = value.strip().lower()
            if text in {"1", "true", "yes", "on"}:
                return True
            if text in {"0", "false", "no", "off"}:
                return False
    return default


def _build_step_budget_state(
    room_state: Dict[str, Any],
    request_args: Dict[str, Any],
) -> Dict[str, Any]:
    request_row = _safe_dict(request_args)
    state_row = _safe_dict(room_state)

    state_total = _normalize_non_negative_int(
        state_row.get("supervisor_step_budget_total"),
        _normalize_non_negative_int(state_row.get("step_budget_total"), 0),
    )
    total = _normalize_non_negative_int(
        request_row.get("supervisor_step_budget_total"),
        state_total,
    )
    used = _normalize_non_negative_int(
        request_row.get("supervisor_step_budget_used"),
        _normalize_non_negative_int(state_row.get("step_budget_used"), 0),
    )
    used = min(used, total) if total > 0 else max(0, used)
    remaining = max(0, total - used) if total > 0 else 0

    if total <= 0:
        budget_status = "unlimited"
    elif remaining <= 0:
        budget_status = "exhausted"
    else:
        budget_status = "running"

    return {
        "step_budget_total": total,
        "step_budget_used": used,
        "step_budget_remaining": remaining,
        "budget_status": budget_status,
        "budget_exhausted": bool(total > 0 and remaining <= 0),
    }


def _consume_step_budget(
    budget: Dict[str, Any],
    steps: int = 1,
) -> Dict[str, Any]:
    row = _safe_dict(budget)
    total = _normalize_non_negative_int(row.get("step_budget_total"), 0)
    used = _normalize_non_negative_int(row.get("step_budget_used"), 0)
    step_count = max(0, int(steps or 0))

    if total <= 0:
        return {
            "step_budget_total": 0,
            "step_budget_used": used + step_count,
            "step_budget_remaining": 0,
            "budget_status": "unlimited",
            "budget_exhausted": False,
        }

    next_used = min(total, used + step_count)
    remaining = max(0, total - next_used)
    return {
        "step_budget_total": total,
        "step_budget_used": next_used,
        "step_budget_remaining": remaining,
        "budget_status": "exhausted" if remaining <= 0 else "running",
        "budget_exhausted": remaining <= 0,
    }


def _budget_patch(budget: Dict[str, Any]) -> Dict[str, Any]:
    row = _safe_dict(budget)
    return {
        "step_budget_total": _normalize_non_negative_int(row.get("step_budget_total"), 0),
        "step_budget_used": _normalize_non_negative_int(row.get("step_budget_used"), 0),
        "step_budget_remaining": _normalize_non_negative_int(row.get("step_budget_remaining"), 0),
        "budget_status": _safe_str(row.get("budget_status")),
        "budget_exhausted": bool(row.get("budget_exhausted")),
    }


def _resolve_continuation_mode(
    *,
    continuation_mode: str = "",
    resumed_from_run_id: str = "",
    resumed_from_event_id: str = "",
    resumed_from_stage: str = "",
) -> str:
    mode = _safe_str(continuation_mode).lower()
    if mode in {"fresh", "resumed"}:
        return mode
    if (
        _safe_str(resumed_from_run_id)
        or _safe_str(resumed_from_event_id)
        or _safe_str(resumed_from_stage)
    ):
        return "resumed"
    return "fresh"

def _build_resume_token(
    *,
    run_id: str,
    checkpoint_ref: str = "",
    issued_at: str = "",
) -> str:
    anchor = _safe_str(checkpoint_ref) or _safe_str(issued_at)
    base = _safe_str(run_id)
    if not base and not anchor:
        return ""
    if not base:
        return anchor
    if not anchor:
        return base
    return f"{base}:{anchor}"

def _read_continuation_context(
    room_state: Dict[str, Any],
    request_args: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    state_row = _safe_dict(room_state)
    request_row = _safe_dict(request_args)
    continuation_row = _safe_dict(request_row.get("continuation"))

    resumed_from_run_id = _coalesce_str(
        continuation_row.get("resumed_from_run_id"),
        request_row.get("resumed_from_run_id"),
        state_row.get("resumed_from_run_id"),
    )
    resumed_from_event_id = _coalesce_str(
        continuation_row.get("resumed_from_event_id"),
        request_row.get("resumed_from_event_id"),
        state_row.get("resumed_from_event_id"),
        state_row.get("final_event_id"),
        state_row.get("checkpoint_event_id"),
    )
    resumed_from_stage = _coalesce_str(
        continuation_row.get("resumed_from_stage"),
        request_row.get("resumed_from_stage"),
        state_row.get("resumed_from_stage"),
        state_row.get("checkpoint_stage"),
    )

    continuation_mode = _resolve_continuation_mode(
        continuation_mode=_coalesce_str(
            continuation_row.get("continuation_mode"),
            request_row.get("continuation_mode"),
            state_row.get("continuation_mode"),
        ),
        resumed_from_run_id=resumed_from_run_id,
        resumed_from_event_id=resumed_from_event_id,
        resumed_from_stage=resumed_from_stage,
    )

    pause_requested = _coalesce_bool(
        continuation_row.get("pause_requested"),
        request_row.get("pause_requested"),
        state_row.get("pause_requested"),
        default=False,
    )

    pause_reason = _coalesce_str(
        continuation_row.get("pause_reason"),
        request_row.get("pause_reason"),
        state_row.get("pause_reason"),
    )

    pause_requested_at = _coalesce_str(
        continuation_row.get("pause_requested_at"),
        request_row.get("pause_requested_at"),
        state_row.get("pause_requested_at"),
    )

    paused_at = _coalesce_str(
        continuation_row.get("paused_at"),
        request_row.get("paused_at"),
        state_row.get("paused_at"),
    )
    pause_effective_at = _coalesce_str(
        continuation_row.get("pause_effective_at"),
        request_row.get("pause_effective_at"),
        state_row.get("pause_effective_at"),
        paused_at,
    )

    interruption_reason = _coalesce_str(
        continuation_row.get("interruption_reason"),
        request_row.get("interruption_reason"),
        state_row.get("interruption_reason"),
    )

    current_run_status = _coalesce_str(
        request_row.get("current_run_status"),
        state_row.get("current_run_status"),
    ).lower()

    resume_from_checkpoint = _coalesce_bool(
        continuation_row.get("resume_from_checkpoint"),
        request_row.get("resume_from_checkpoint"),
        state_row.get("resume_from_checkpoint"),
        default=False,
    )

    resume_checkpoint_ref = _coalesce_str(
        continuation_row.get("resume_checkpoint_ref"),
        request_row.get("resume_checkpoint_ref"),
        request_row.get("resumable_checkpoint_ref"),
        state_row.get("resume_checkpoint_ref"),
        state_row.get("resumable_checkpoint_ref"),
    )
    if resume_checkpoint_ref:
        resume_from_checkpoint = True

    resume_ready = _coalesce_bool(
        continuation_row.get("resume_ready"),
        request_row.get("resume_ready"),
        state_row.get("resume_ready"),
        default=False,
    )
    if current_run_status == "interrupted" and resume_checkpoint_ref:
        resume_ready = True

    resume_token = _coalesce_str(
        continuation_row.get("resume_token"),
        request_row.get("resume_token"),
        state_row.get("resume_token"),
    )
    resume_reason = _coalesce_str(
        continuation_row.get("resume_reason"),
        request_row.get("resume_reason"),
        state_row.get("resume_reason"),
    )

    error_blocking_resume = _coalesce_bool(
        continuation_row.get("error_blocking_resume"),
        request_row.get("error_blocking_resume"),
        state_row.get("error_blocking_resume"),
        default=False,
    )

    continuation_status = _coalesce_str(
        continuation_row.get("continuation_status"),
        request_row.get("continuation_status"),
        state_row.get("continuation_status"),
    )

    if not continuation_status:
        if current_run_status == "interrupted":
            continuation_status = "interrupted"
        elif current_run_status == "completed":
            continuation_status = "completed_after_resume" if continuation_mode == "resumed" else "completed"
        elif pause_requested:
            continuation_status = "pause_requested"
        elif continuation_mode == "resumed" and current_run_status == "running":
            continuation_status = "resumed"
        elif continuation_mode or resume_from_checkpoint:
            continuation_status = "running"
        else:
            continuation_status = ""

    last_completed_step = _coalesce_str(
        continuation_row.get("last_completed_step"),
        request_row.get("last_completed_step"),
        state_row.get("last_completed_step"),
        state_row.get("checkpoint_stage"),
    )

    skipped_effects = _coalesce_list(
        continuation_row.get("skipped_effects"),
        request_row.get("skipped_effects"),
        state_row.get("skipped_effects"),
    )
    effect_dispositions = _coalesce_list(
        continuation_row.get("effect_dispositions"),
        request_row.get("effect_dispositions"),
        state_row.get("effect_dispositions"),
    )

    if not resume_from_checkpoint:
        continuation_mode = ""
        continuation_status = ""
        resume_ready = False
        resume_token = ""
        resume_reason = ""
        error_blocking_resume = False
        resumed_from_run_id = ""
        resumed_from_event_id = ""
        resumed_from_stage = ""
        last_completed_step = ""
        skipped_effects = []
        effect_dispositions = []

    return {
        "continuation_mode": continuation_mode,
        "continuation_status": continuation_status,
        "pause_requested": pause_requested,
        "pause_reason": pause_reason,
        "pause_requested_at": pause_requested_at,
        "paused_at": paused_at,
        "pause_effective_at": pause_effective_at,
        "interruption_reason": interruption_reason,
        "resume_from_checkpoint": resume_from_checkpoint,
        "resume_checkpoint_ref": resume_checkpoint_ref,
        "resume_ready": resume_ready,
        "resume_token": resume_token,
        "resume_reason": resume_reason,
        "error_blocking_resume": error_blocking_resume,
        "resumed_from_run_id": resumed_from_run_id,
        "resumed_from_event_id": resumed_from_event_id,
        "resumed_from_stage": resumed_from_stage,
        "last_completed_step": last_completed_step,
        "skipped_effects": skipped_effects,
        "effect_dispositions": effect_dispositions,
        "current_run_status": current_run_status,
    }

def _continuation_pause_requested(
    room_state: Dict[str, Any],
    request_args: Optional[Dict[str, Any]] = None,
) -> bool:
    ctx = _read_continuation_context(room_state, request_args=request_args)
    status = _safe_str(ctx.get("continuation_status")).lower()
    if status == "interrupted":
        return False
    return bool(ctx.get("pause_requested") or status == "pause_requested")


def _continuation_pause_reason(
    room_state: Dict[str, Any],
    request_args: Optional[Dict[str, Any]] = None,
    checkpoint_stage: str = "",
) -> str:
    ctx = _read_continuation_context(room_state, request_args=request_args)
    reason = _safe_str(ctx.get("pause_reason"))
    if reason:
        return reason
    checkpoint = _safe_str(checkpoint_stage, "checkpoint")
    return f"pause requested at {checkpoint}"

def _build_resumed_lineage_patch(
    room_state: Dict[str, Any],
    request_args: Optional[Dict[str, Any]] = None,
    continuation_status: str = "running",
) -> Dict[str, Any]:
    ctx = _read_continuation_context(room_state, request_args=request_args)
    return _build_continuation_patch(
        continuation_mode=ctx.get("continuation_mode") or "resumed",
        continuation_status=_safe_str(continuation_status, "running"),
        pause_requested=False,
        pause_reason="",
        pause_requested_at="",
        paused_at="",
        pause_effective_at="",
        interruption_reason="",
        resume_from_checkpoint=bool(
            ctx.get("resume_from_checkpoint") or _safe_str(ctx.get("resume_checkpoint_ref"))
        ),
        resume_checkpoint_ref=_safe_str(ctx.get("resume_checkpoint_ref")),
        resume_ready=False,
        resume_token="",
        resume_reason="",
        error_blocking_resume=False,
        resumed_from_run_id=_safe_str(ctx.get("resumed_from_run_id")),
        resumed_from_event_id=_safe_str(ctx.get("resumed_from_event_id")),
        resumed_from_stage=_safe_str(ctx.get("resumed_from_stage")),
        last_completed_step=_safe_str(ctx.get("last_completed_step")),
        skipped_effects=_safe_list(ctx.get("skipped_effects")),
        effect_dispositions=_safe_list(ctx.get("effect_dispositions")),
    )

def _build_continuation_patch(
    *,
    continuation_mode: str = "",
    continuation_status: str = "",
    pause_requested: bool = False,
    pause_reason: str = "",
    pause_requested_at: str = "",
    paused_at: str = "",
    pause_effective_at: str = "",
    interruption_reason: str = "",
    resume_from_checkpoint: bool = False,
    resume_checkpoint_ref: str = "",
    resume_ready: bool = False,
    resume_token: str = "",
    resume_reason: str = "",
    error_blocking_resume: bool = False,
    resumed_from_run_id: str = "",
    resumed_from_event_id: str = "",
    resumed_from_stage: str = "",
    last_completed_step: str = "",
    skipped_effects: Optional[List[Dict[str, Any]]] = None,
    effect_dispositions: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    return {
        "continuation_mode": _resolve_continuation_mode(
            continuation_mode=continuation_mode,
            resumed_from_run_id=resumed_from_run_id,
            resumed_from_event_id=resumed_from_event_id,
            resumed_from_stage=resumed_from_stage,
        ),
        "continuation_status": _safe_str(continuation_status, "running"),
        "pause_requested": bool(pause_requested),
        "pause_reason": _safe_str(pause_reason),
        "pause_requested_at": _safe_str(pause_requested_at),
        "paused_at": _safe_str(paused_at),
        "pause_effective_at": _safe_str(pause_effective_at or paused_at),
        "interruption_reason": _safe_str(interruption_reason),
        "resume_from_checkpoint": bool(resume_from_checkpoint),
        "resume_checkpoint_ref": _safe_str(resume_checkpoint_ref),
        "resume_ready": bool(resume_ready),
        "resume_token": _safe_str(resume_token),
        "resume_reason": _safe_str(resume_reason),
        "error_blocking_resume": bool(error_blocking_resume),
        "resumed_from_run_id": _safe_str(resumed_from_run_id),
        "resumed_from_event_id": _safe_str(resumed_from_event_id),
        "resumed_from_stage": _safe_str(resumed_from_stage),
        "last_completed_step": _safe_str(last_completed_step),
        "skipped_effects": _safe_list(skipped_effects),
        "effect_dispositions": _safe_list(effect_dispositions),
    }

def _interrupt_message_from_reason(interruption_reason: str) -> str:
    reason = _safe_str(interruption_reason, "step_budget_exhausted")
    if reason == "pause_requested":
        return "supervisor run interrupted: pause requested"
    if reason == "step_budget_exhausted":
        return "supervisor run interrupted: step budget exhausted"
    return f"supervisor run interrupted: {reason.replace('_', ' ')}"


def _build_interrupted_final_event(
    *,
    event_id: str,
    event_ts: str,
    room_id: str,
    rid: str,
    run_id: str,
    trigger_event_id: str,
    question: str,
    phase: str,
    plan_summary: str,
    message: str,
    checkpoint_summary: str,
    budget: Dict[str, Any],
    mode_used: str,
    continuation_patch: Dict[str, Any],
) -> Dict[str, Any]:
    return {
        "id": event_id,
        "ts": event_ts,
        "type": "room.final",
        "room_id": room_id,
        "request_id": rid,
        "run_id": run_id,
        "trigger_event_id": trigger_event_id,
        "payload": {
            "response": "",
            "content": "",
            "status": "interrupted",
            "message": message,
            "mode_used": mode_used,
            "question": question,
            "plan_summary": plan_summary,
            "checkpoint_stage": phase,
            "checkpoint_summary": _truncate_text(checkpoint_summary, 280),
            **continuation_patch,
            **_budget_patch(budget),
            "tool_calls": [],
            "tool_results": [],
        },
    }


def _interrupt_supervisor_run(
    *,
    room_id: str,
    rid: str,
    run_id: str,
    trigger_event_id: str,
    question: str,
    phase: str,
    plan_summary: str,
    checkpoint_summary: str,
    supervisor_request_args: Dict[str, Any],
    fs_context: Optional[Dict[str, Any]],
    notebook_read_info: Optional[Dict[str, Any]],
    memory_read_info: Optional[Dict[str, Any]],
    memory_resume_info: Optional[Dict[str, Any]],
    budget: Dict[str, Any],
    mode_used: str,
    interruption_reason: str = "step_budget_exhausted",
    pause_requested: bool = False,
    pause_reason: str = "",
    pause_requested_at: str = "",
    continuation_mode: str = "",
    resumed_from_run_id: str = "",
    resumed_from_event_id: str = "",
    resumed_from_stage: str = "",
    last_completed_step: str = "",
    skipped_effects: Optional[List[Dict[str, Any]]] = None,
    effect_dispositions: Optional[List[Dict[str, Any]]] = None,
    append_room_event_fn: Callable[[str, Dict[str, Any]], Any] = lambda *_args, **_kwargs: None,
    touch_room_updated_at_fn: Callable[[str], Any] = lambda *_args, **_kwargs: None,
    update_room_last_message_fn: Callable[[str, str], Any] = lambda *_args, **_kwargs: None,
    set_room_state_patch_fn: Callable[[str, Dict[str, Any]], Any] = lambda *_args, **_kwargs: None,
    patch_supervisor_runtime_state_fn: Callable[..., Any] = lambda **_kwargs: None,
    clear_run_state_fn: Callable[[str], Any] = lambda *_args, **_kwargs: None,
    new_id_fn: Callable[[str], str] = lambda prefix: prefix,
    utc_iso_fn: Callable[[], str] = lambda: "",
) -> Tuple[Dict[str, Any], List[Dict[str, Any]], Dict[str, Any]]:
    resolved_interruption_reason = _safe_str(interruption_reason, "step_budget_exhausted")
    interrupted_event_id = new_id_fn("evt")
    interrupted_at = utc_iso_fn()

    resolved_pause_requested_at = _safe_str(pause_requested_at)
    if bool(pause_requested or resolved_interruption_reason == "pause_requested") and not resolved_pause_requested_at:
        resolved_pause_requested_at = interrupted_at

    resume_token = _build_resume_token(
        run_id=run_id,
        checkpoint_ref=interrupted_event_id,
        issued_at=interrupted_at,
    )
    resume_reason = "checkpoint_ready"
    if resolved_interruption_reason == "step_budget_exhausted":
        resume_reason = "budget_checkpoint_ready"

    continuation_patch = _build_continuation_patch(
        continuation_mode=continuation_mode,
        continuation_status="interrupted",
        pause_requested=bool(pause_requested or resolved_interruption_reason == "pause_requested"),
        pause_reason=pause_reason,
        pause_requested_at=resolved_pause_requested_at,
        paused_at=interrupted_at,
        pause_effective_at=interrupted_at,
        interruption_reason=resolved_interruption_reason,
        resume_from_checkpoint=True,
        resume_checkpoint_ref=interrupted_event_id,
        resume_ready=True,
        resume_token=resume_token,
        resume_reason=resume_reason,
        error_blocking_resume=False,
        resumed_from_run_id=resumed_from_run_id,
        resumed_from_event_id=resumed_from_event_id,
        resumed_from_stage=resumed_from_stage,
        last_completed_step=last_completed_step or phase,
        skipped_effects=skipped_effects,
        effect_dispositions=effect_dispositions,
    )

    final_evt = _build_interrupted_final_event(
        event_id=interrupted_event_id,
        event_ts=interrupted_at,
        room_id=room_id,
        rid=rid,
        run_id=run_id,
        trigger_event_id=trigger_event_id,
        question=question,
        phase=phase,
        plan_summary=plan_summary,
        message=_interrupt_message_from_reason(resolved_interruption_reason),
        checkpoint_summary=checkpoint_summary,
        budget=budget,
        mode_used=mode_used,
        continuation_patch=continuation_patch,
    )

    append_room_event_fn(room_id, final_evt)
    touch_room_updated_at_fn(room_id)
    update_room_last_message_fn(room_id, final_evt["id"])

    interrupted_state_patch = {
        "current_run_id": run_id,
        "current_run_status": "interrupted",
        "runtime_control_run_id": run_id,
        "runtime_state_hint": "budget_exhausted" if resolved_interruption_reason == "step_budget_exhausted" else "interrupted",
        "runtime_phase_hint": _safe_str(phase, "idle"),
        "last_run_finished_at": interrupted_at,
        "last_supervisor_phase": phase,
        "last_supervisor_status": "interrupted",
        "checkpoint_event_id": interrupted_event_id,
        "checkpoint_stage": phase,
        "checkpoint_summary": _truncate_text(checkpoint_summary, 280),
        "pause_requested_at": resolved_pause_requested_at,
        "paused_at": interrupted_at,
        "pause_effective_at": interrupted_at,
        "resume_ready": True,
        "resume_token": resume_token,
        "resume_reason": resume_reason,
        "current_delegate_role_id": "",
        "current_delegate_role_name": "",
        "current_delegate_index": 0,
        "current_delegate_total": 0,
        **continuation_patch,
        **_budget_patch(budget),
    }
    set_room_state_patch_fn(room_id, interrupted_state_patch)

    runtime_request_args = dict(_safe_dict(supervisor_request_args))
    runtime_request_args["continuation"] = {
        **_safe_dict(runtime_request_args.get("continuation")),
        **continuation_patch,
    }
    runtime_request_args["pause_requested_at"] = resolved_pause_requested_at
    runtime_request_args["pause_effective_at"] = interrupted_at
    runtime_request_args["resume_ready"] = True
    runtime_request_args["resume_token"] = resume_token
    runtime_request_args["resume_reason"] = resume_reason

    patch_supervisor_runtime_state_fn(
        room_id,
        phase=phase,
        status="interrupted",
        plan_summary=plan_summary,
        fs_context=fs_context or {},
        notebook_read_result=notebook_read_info or {},
        memory_read_result=memory_read_info or {},
        memory_resume_result=memory_resume_info or {},
        request_args=runtime_request_args,
        run_id=run_id,
        finished=True,
        step_budget_total=_normalize_non_negative_int(budget.get("step_budget_total"), 0),
        step_budget_used=_normalize_non_negative_int(budget.get("step_budget_used"), 0),
        step_budget_remaining=_normalize_non_negative_int(budget.get("step_budget_remaining"), 0),
        budget_status=_safe_str(budget.get("budget_status")),
        budget_exhausted=bool(budget.get("budget_exhausted")),
        checkpoint_stage=phase,
        checkpoint_summary=_truncate_text(checkpoint_summary, 280),
        interruption_reason=resolved_interruption_reason,
    )

    return {}, [], final_evt


def _maybe_interrupt_at_boundary(
    *,
    checkpoint_stage: str,
    room_state: Dict[str, Any],
    room_id: str,
    question: str,
    mode_used: str,
    run_id: str,
    trigger_event_id: str,
    rid: str,
    plan_summary: str,
    checkpoint_summary: str,
    supervisor_request_args: Dict[str, Any],
    fs_context: Optional[Dict[str, Any]],
    notebook_read_info: Optional[Dict[str, Any]],
    memory_read_info: Optional[Dict[str, Any]],
    memory_resume_info: Optional[Dict[str, Any]],
    budget: Dict[str, Any],
    skipped_effects: Optional[List[Dict[str, Any]]] = None,
    effect_dispositions: Optional[List[Dict[str, Any]]] = None,
    append_room_event_fn: Callable[[str, Dict[str, Any]], Any] = lambda *_args, **_kwargs: None,
    touch_room_updated_at_fn: Callable[[str], Any] = lambda *_args, **_kwargs: None,
    update_room_last_message_fn: Callable[[str, str], Any] = lambda *_args, **_kwargs: None,
    set_room_state_patch_fn: Callable[[str, Dict[str, Any]], Any] = lambda *_args, **_kwargs: None,
    patch_supervisor_runtime_state_fn: Callable[..., Any] = lambda **_kwargs: None,
    clear_run_state_fn: Callable[[str], Any] = lambda *_args, **_kwargs: None,
    new_id_fn: Callable[[str], str] = lambda prefix: prefix,
    utc_iso_fn: Callable[[], str] = lambda: "",
) -> Optional[Tuple[Dict[str, Any], List[Dict[str, Any]], Dict[str, Any]]]:
    if not _continuation_pause_requested(room_state, request_args=supervisor_request_args):
        return None

    ctx = _read_continuation_context(room_state, request_args=supervisor_request_args)

    return _interrupt_supervisor_run(
        room_id=room_id,
        rid=rid,
        run_id=run_id,
        trigger_event_id=trigger_event_id,
        question=question,
        phase=checkpoint_stage,
        plan_summary=plan_summary,
        checkpoint_summary=_truncate_text(checkpoint_summary, 280),
        supervisor_request_args=supervisor_request_args,
        fs_context=fs_context or {},
        notebook_read_info=notebook_read_info or {},
        memory_read_info=memory_read_info or {},
        memory_resume_info=memory_resume_info or {},
        budget=budget,
        mode_used=mode_used,
        interruption_reason="pause_requested",
        pause_requested=True,
        pause_reason=_continuation_pause_reason(
            room_state,
            request_args=supervisor_request_args,
            checkpoint_stage=checkpoint_stage,
        ),
        pause_requested_at=_safe_str(ctx.get("pause_requested_at")),
        continuation_mode=_safe_str(ctx.get("continuation_mode")),
        resumed_from_run_id=_safe_str(ctx.get("resumed_from_run_id")),
        resumed_from_event_id=_safe_str(ctx.get("resumed_from_event_id")),
        resumed_from_stage=_safe_str(ctx.get("resumed_from_stage")),
        last_completed_step=_safe_str(ctx.get("last_completed_step") or checkpoint_stage),
        skipped_effects=_safe_list(skipped_effects) or _safe_list(ctx.get("skipped_effects")),
        effect_dispositions=_safe_list(effect_dispositions) or _safe_list(ctx.get("effect_dispositions")),
        append_room_event_fn=append_room_event_fn,
        touch_room_updated_at_fn=touch_room_updated_at_fn,
        update_room_last_message_fn=update_room_last_message_fn,
        set_room_state_patch_fn=set_room_state_patch_fn,
        patch_supervisor_runtime_state_fn=patch_supervisor_runtime_state_fn,
        clear_run_state_fn=clear_run_state_fn,
        new_id_fn=new_id_fn,
        utc_iso_fn=utc_iso_fn,
    )


__all__ = [
    "_build_continuation_patch",
    "_build_resumed_lineage_patch",
    "_build_step_budget_state",
    "_budget_patch",
    "_consume_step_budget",
    "_continuation_pause_reason",
    "_continuation_pause_requested",
    "_interrupt_supervisor_run",
    "_maybe_interrupt_at_boundary",
    "_read_continuation_context",
    "_resolve_continuation_mode",
    "_build_resume_token",
]

