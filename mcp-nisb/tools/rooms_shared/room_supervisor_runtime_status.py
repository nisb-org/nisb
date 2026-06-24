from __future__ import annotations

from typing import Any, Dict

from .room_contracts import as_bool


def _safe_str(v: Any, default: str = "") -> str:
    if v is None:
        return default
    s = str(v).strip()
    return s if s else default


def _safe_list(v: Any):
    return v if isinstance(v, list) else []


def _safe_dict(v: Any) -> Dict[str, Any]:
    return v if isinstance(v, dict) else {}


def _safe_non_negative_int(value: Any, fallback: int = 0) -> int:
    try:
        return max(0, int(value))
    except Exception:
        try:
            return max(0, int(fallback))
        except Exception:
            return 0


def _normalize_fs_read_scope(value: Any, fallback: str = "minimal") -> str:
    s = _safe_str(value).lower()
    if s in {"minimal", "user_ro"}:
        return s
    return fallback if fallback in {"minimal", "user_ro"} else "minimal"


def _normalize_rel_path(value: Any) -> str:
    raw = _safe_str(value).replace("\\", "/")
    while "//" in raw:
        raw = raw.replace("//", "/")
    raw = raw.strip("/")
    if not raw:
        return ""
    parts = [p.strip() for p in raw.split("/") if p and p not in {".", ".."}]
    return "/".join(parts)


def _normalize_filename(value: Any, fallback: str = "supervisor.md") -> str:
    raw = _safe_str(value).replace("\\", "/").strip()
    if not raw:
        return fallback
    base = raw.split("/")[-1].strip()
    if not base or base in {".", ".."}:
        return fallback
    if not base.lower().endswith(".md"):
        base = f"{base}.md"
    return base


def _pick_recorded_at(row: Dict[str, Any]) -> str:
    src = _safe_dict(row)
    return _safe_str(
        src.get("recorded_at")
        or src.get("updated_at")
        or src.get("at")
        or src.get("ts")
    )


def _continuation_row(request_row: Dict[str, Any]) -> Dict[str, Any]:
    row = _safe_dict(request_row)
    continuation = dict(_safe_dict(row.get("continuation")))
    for key in (
        "continuation_mode",
        "continuation_status",
        "pause_requested",
        "pause_reason",
        "pause_requested_at",
        "paused_at",
        "pause_effective_at",
        "resume_from_checkpoint",
        "resume_checkpoint_ref",
        "resume_ready",
        "resume_token",
        "resume_reason",
        "error_blocking_resume",
        "resumed_from_run_id",
        "resumed_from_event_id",
        "resumed_from_stage",
        "last_completed_step",
        "skipped_effects",
        "effect_dispositions",
        "interruption_reason",
    ):
        if key in row and key not in continuation:
            continuation[key] = row.get(key)
    return continuation


def _normalize_continuation_mode(value: Any, fallback: str = "fresh") -> str:
    s = _safe_str(value).lower()
    if s in {"fresh", "resumed"}:
        return s
    return fallback if fallback in {"fresh", "resumed"} else "fresh"


def _normalize_continuation_status(value: Any, fallback: str = "running") -> str:
    s = _safe_str(value).lower()
    if s in {
        "running",
        "pause_requested",
        "interrupted",
        "resumed",
        "completed",
        "completed_after_resume",
    }:
        return s
    return fallback if fallback in {
        "running",
        "pause_requested",
        "interrupted",
        "resumed",
        "completed",
        "completed_after_resume",
    } else "running"


def _normalize_runtime_state(value: Any, fallback: str = "idle") -> str:
    s = _safe_str(value).lower()
    if s in {
        "idle",
        "running",
        "pause_requested",
        "interrupted",
        "resuming",
        "completed",
        "completed_after_resume",
        "failed",
    }:
        return s
    return fallback if fallback in {
        "idle",
        "running",
        "pause_requested",
        "interrupted",
        "resuming",
        "completed",
        "completed_after_resume",
        "failed",
    } else "idle"


def _normalize_runtime_phase(value: Any, fallback: str = "idle") -> str:
    s = _safe_str(value).lower()
    if not s:
        return fallback
    return s


def _resolve_runtime_status_fields(
    *,
    prev_state: Dict[str, Any],
    request_row: Dict[str, Any],
    step_budget_total: int = 0,
    step_budget_used: int = 0,
    step_budget_remaining: int = 0,
    budget_status: str = "",
    budget_exhausted: bool = False,
    checkpoint_stage: str = "",
    checkpoint_summary: str = "",
    interruption_reason: str = "",
) -> Dict[str, Any]:
    extra_runtime_fields_provided = any(
        [
            bool(step_budget_total),
            bool(step_budget_used),
            bool(step_budget_remaining),
            bool(_safe_str(budget_status)),
            bool(budget_exhausted),
            bool(_safe_str(checkpoint_stage)),
            bool(_safe_str(checkpoint_summary)),
            bool(_safe_str(interruption_reason)),
        ]
    )

    if extra_runtime_fields_provided:
        resolved_step_budget_total = _safe_non_negative_int(step_budget_total, 0)
        resolved_step_budget_used = _safe_non_negative_int(step_budget_used, 0)
        resolved_step_budget_remaining = _safe_non_negative_int(step_budget_remaining, 0)
        resolved_budget_status = _safe_str(budget_status)
        resolved_budget_exhausted = bool(budget_exhausted)
        resolved_checkpoint_stage = _safe_str(checkpoint_stage)
        resolved_checkpoint_summary = _safe_str(checkpoint_summary)
        resolved_interruption_reason = _safe_str(interruption_reason)
    else:
        resolved_step_budget_total = _safe_non_negative_int(
            request_row.get("supervisor_step_budget_total"),
            _safe_non_negative_int(prev_state.get("step_budget_total"), 0),
        )
        resolved_step_budget_used = _safe_non_negative_int(
            request_row.get("supervisor_step_budget_used"),
            _safe_non_negative_int(prev_state.get("step_budget_used"), 0),
        )
        resolved_step_budget_remaining = _safe_non_negative_int(
            request_row.get("supervisor_step_budget_remaining"),
            _safe_non_negative_int(prev_state.get("step_budget_remaining"), 0),
        )
        resolved_budget_status = _safe_str(
            request_row.get("supervisor_budget_status"),
            _safe_str(prev_state.get("budget_status")),
        )
        resolved_budget_exhausted = as_bool(
            request_row.get("supervisor_budget_exhausted"),
            as_bool(prev_state.get("budget_exhausted"), False),
        )
        resolved_checkpoint_stage = _safe_str(
            request_row.get("checkpoint_stage"),
            _safe_str(prev_state.get("checkpoint_stage")),
        )
        resolved_checkpoint_summary = _safe_str(
            request_row.get("checkpoint_summary"),
            _safe_str(prev_state.get("checkpoint_summary")),
        )
        resolved_interruption_reason = _safe_str(
            request_row.get("interruption_reason"),
            _safe_str(prev_state.get("interruption_reason")),
        )

    if resolved_budget_status not in {"", "running", "exhausted", "unlimited"}:
        resolved_budget_status = _safe_str(prev_state.get("budget_status"))

    if resolved_budget_exhausted and not resolved_interruption_reason:
        resolved_interruption_reason = "step_budget_exhausted"

    return {
        "step_budget_total": resolved_step_budget_total,
        "step_budget_used": resolved_step_budget_used,
        "step_budget_remaining": resolved_step_budget_remaining,
        "budget_status": resolved_budget_status,
        "budget_exhausted": resolved_budget_exhausted,
        "checkpoint_stage": resolved_checkpoint_stage,
        "checkpoint_summary": resolved_checkpoint_summary,
        "interruption_reason": resolved_interruption_reason,
    }


def _resolve_continuation_status_fields(
    *,
    prev_state: Dict[str, Any],
    request_row: Dict[str, Any],
    phase: str = "",
    status: str = "",
    finished: bool = False,
    checkpoint_stage: str = "",
    interruption_reason: str = "",
) -> Dict[str, Any]:
    continuation = _continuation_row(request_row)

    resumed_from_run_id = _safe_str(
        continuation.get("resumed_from_run_id")
        or prev_state.get("resumed_from_run_id")
        or prev_state.get("last_supervisor_resumed_from_run_id")
    )
    resumed_from_event_id = _safe_str(
        continuation.get("resumed_from_event_id")
        or prev_state.get("resumed_from_event_id")
        or prev_state.get("last_supervisor_resumed_from_event_id")
    )
    resumed_from_stage = _safe_str(
        continuation.get("resumed_from_stage")
        or prev_state.get("resumed_from_stage")
        or prev_state.get("last_supervisor_resumed_from_stage")
    )

    inferred_mode = "resumed" if (
        as_bool(continuation.get("resume_from_checkpoint"), False)
        or _safe_str(continuation.get("resume_checkpoint_ref"))
        or resumed_from_run_id
        or resumed_from_event_id
        or resumed_from_stage
    ) else "fresh"

    continuation_mode = _normalize_continuation_mode(
        continuation.get("continuation_mode")
        or prev_state.get("continuation_mode")
        or prev_state.get("last_supervisor_continuation_mode"),
        inferred_mode,
    )

    pause_requested = as_bool(
        continuation.get("pause_requested"),
        as_bool(
            prev_state.get("pause_requested"),
            as_bool(prev_state.get("last_supervisor_pause_requested"), False),
        ),
    )
    if _safe_str(interruption_reason) == "pause_requested":
        pause_requested = True

    pause_reason = _safe_str(
        continuation.get("pause_reason")
        or prev_state.get("pause_reason")
        or prev_state.get("last_supervisor_pause_reason")
    )
    paused_at = _safe_str(
        continuation.get("paused_at")
        or prev_state.get("paused_at")
        or prev_state.get("last_supervisor_paused_at")
    )

    resume_from_checkpoint = as_bool(
        continuation.get("resume_from_checkpoint"),
        as_bool(
            prev_state.get("resume_from_checkpoint"),
            as_bool(prev_state.get("last_supervisor_resume_from_checkpoint"), False),
        ),
    )
    if finished and _safe_str(status) == "interrupted":
        resume_from_checkpoint = True
    elif finished and _safe_str(status) in {"success", "completed"}:
        resume_from_checkpoint = False

    resume_checkpoint_ref = _safe_str(
        continuation.get("resume_checkpoint_ref")
        or prev_state.get("resume_checkpoint_ref")
        or prev_state.get("last_supervisor_resume_checkpoint_ref")
    )

    last_completed_step = _safe_str(
        continuation.get("last_completed_step")
        or prev_state.get("last_completed_step")
        or prev_state.get("last_supervisor_last_completed_step")
    )
    if finished and _safe_str(status) in {"success", "completed"}:
        last_completed_step = "completed"
    elif checkpoint_stage and not last_completed_step:
        last_completed_step = checkpoint_stage
    elif _safe_str(phase) and not last_completed_step:
        last_completed_step = _safe_str(phase)

    skipped_effects = _safe_list(
        continuation.get("skipped_effects")
        or prev_state.get("skipped_effects")
        or prev_state.get("last_supervisor_skipped_effects")
    )
    effect_dispositions = _safe_list(
        continuation.get("effect_dispositions")
        or prev_state.get("effect_dispositions")
        or prev_state.get("last_supervisor_effect_dispositions")
    )

    if finished and _safe_str(status) == "interrupted":
        inferred_status = "interrupted"
    elif finished and _safe_str(status) in {"success", "completed"}:
        inferred_status = "completed_after_resume" if continuation_mode == "resumed" else "completed"
    elif pause_requested:
        inferred_status = "pause_requested"
    elif continuation_mode == "resumed" and _safe_str(status) == "running":
        inferred_status = "resumed"
    else:
        inferred_status = "running"

    continuation_status = _normalize_continuation_status(
        continuation.get("continuation_status")
        or prev_state.get("continuation_status")
        or prev_state.get("last_supervisor_continuation_status"),
        inferred_status,
    )

    return {
        "continuation_mode": continuation_mode,
        "continuation_status": continuation_status,
        "pause_requested": pause_requested,
        "pause_reason": pause_reason,
        "resume_from_checkpoint": resume_from_checkpoint,
        "resume_checkpoint_ref": resume_checkpoint_ref,
        "resumed_from_run_id": resumed_from_run_id,
        "resumed_from_event_id": resumed_from_event_id,
        "resumed_from_stage": resumed_from_stage,
        "last_completed_step": last_completed_step,
        "skipped_effects": skipped_effects,
        "effect_dispositions": effect_dispositions,
        "paused_at": paused_at,
    }


def _build_runtime_control_snapshot(
    *,
    prev_state: Dict[str, Any],
    request_row: Dict[str, Any],
    phase: str = "",
    status: str = "",
    finished: bool = False,
    memory_resume_row: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    prev = _safe_dict(prev_state)
    req = _safe_dict(request_row)
    mem = _safe_dict(memory_resume_row)

    runtime_fields = _resolve_runtime_status_fields(
        prev_state=prev,
        request_row=req,
    )

    continuation_fields = _resolve_continuation_status_fields(
        prev_state=prev,
        request_row=req,
        phase=phase,
        status=status,
        finished=finished,
        checkpoint_stage=_safe_str(runtime_fields.get("checkpoint_stage")),
        interruption_reason=_safe_str(runtime_fields.get("interruption_reason")),
    )

    continuation = _continuation_row(req)

    run_id = _safe_str(
        req.get("current_run_id")
        or prev.get("runtime_control_run_id")
        or prev.get("current_run_id")
    )
    request_id = _safe_str(
        req.get("current_request_id")
        or prev.get("current_request_id")
    )
    room_id = _safe_str(
        req.get("room_id")
        or prev.get("room_id")
    )

    current_status = _safe_str(
        status
        or req.get("current_run_status")
        or prev.get("current_run_status")
    ).lower()

    phase_value = _normalize_runtime_phase(
        phase
        or req.get("last_supervisor_phase")
        or req.get("runtime_phase_hint")
        or prev.get("last_supervisor_phase")
        or prev.get("runtime_phase_hint"),
        "idle" if not run_id else "running",
    )

    snapshot_version = _safe_non_negative_int(
        req.get("runtime_control_version"),
        _safe_non_negative_int(
            prev.get("runtime_control_version"),
            _safe_non_negative_int(prev.get("runtime_version"), 0),
        ),
    )

    pause_requested = as_bool(continuation_fields.get("pause_requested"), False)
    pause_reason = _safe_str(continuation_fields.get("pause_reason"))
    pause_requested_at = _safe_str(
        continuation.get("pause_requested_at")
        or prev.get("pause_requested_at")
        or prev.get("last_supervisor_pause_requested_at")
    )
    paused_at = _safe_str(
        continuation.get("paused_at")
        or continuation_fields.get("paused_at")
        or prev.get("paused_at")
        or prev.get("last_supervisor_paused_at")
    )
    pause_effective_at = _safe_str(
        continuation.get("pause_effective_at")
        or prev.get("pause_effective_at")
        or paused_at
    )

    interruption_reason = _safe_str(
        runtime_fields.get("interruption_reason")
        or continuation.get("interruption_reason")
        or prev.get("interruption_reason")
    )

    resume_from_checkpoint = as_bool(continuation_fields.get("resume_from_checkpoint"), False)
    resume_checkpoint_ref = _safe_str(continuation_fields.get("resume_checkpoint_ref"))

    resume_token = _safe_str(
        continuation.get("resume_token")
        or mem.get("resume_token")
        or prev.get("resume_token")
    )
    resume_reason = _safe_str(
        continuation.get("resume_reason")
        or mem.get("resume_reason")
        or prev.get("resume_reason")
    )
    error_blocking_resume = as_bool(
        continuation.get("error_blocking_resume"),
        as_bool(prev.get("error_blocking_resume"), False),
    )
    resume_ready = as_bool(
        continuation.get("resume_ready"),
        as_bool(
            mem.get("resume_ready"),
            as_bool(prev.get("resume_ready"), False),
        ),
    )

    if (
        not resume_ready
        and not error_blocking_resume
        and (
            resume_from_checkpoint
            or bool(resume_checkpoint_ref)
            or bool(resume_token)
        )
        and (
            current_status == "interrupted"
            or _safe_str(continuation_fields.get("continuation_status")) == "interrupted"
            or bool(paused_at)
        )
    ):
        resume_ready = True

    pause_effective = bool(
        paused_at
        or pause_effective_at
        or current_status == "interrupted"
        or _safe_str(continuation_fields.get("continuation_status")) == "interrupted"
    )
    pause_request_accepted = bool(pause_requested and not pause_effective)

    continuation_mode = _safe_str(continuation_fields.get("continuation_mode"), "fresh") or "fresh"
    continuation_status = _safe_str(continuation_fields.get("continuation_status"), "running") or "running"

    if current_status in {"error", "failed"}:
        runtime_state = "failed"
    elif current_status in {"success", "completed"} or (
        finished and continuation_status in {"completed", "completed_after_resume"}
    ):
        runtime_state = "completed_after_resume" if continuation_status == "completed_after_resume" else "completed"
    elif pause_effective:
        runtime_state = "interrupted"
    elif pause_request_accepted:
        runtime_state = "pause_requested"
    elif continuation_mode == "resumed" and current_status == "running":
        runtime_state = "resuming"
    elif run_id and current_status == "running":
        runtime_state = "running"
    else:
        runtime_state = "idle"

    runtime_state = _normalize_runtime_state(runtime_state)

    if runtime_state == "idle":
        runtime_phase = "idle"
    elif runtime_state in {"completed", "completed_after_resume", "failed"}:
        runtime_phase = "finalize"
    elif runtime_state == "pause_requested":
        runtime_phase = "waiting_checkpoint"
    elif runtime_state == "interrupted":
        runtime_phase = _normalize_runtime_phase(
            _safe_str(runtime_fields.get("checkpoint_stage")) or phase_value,
            "interrupted",
        )
    else:
        runtime_phase = phase_value

    if runtime_state in {"idle", "completed", "completed_after_resume", "failed"}:
        can_accept_new_prompt = True
        control_block_reason = ""
    elif runtime_state == "running":
        can_accept_new_prompt = False
        control_block_reason = "run_running"
    elif runtime_state == "pause_requested":
        can_accept_new_prompt = False
        control_block_reason = "pause_requested_pending_checkpoint"
    elif runtime_state == "interrupted":
        can_accept_new_prompt = False
        if error_blocking_resume:
            control_block_reason = "resume_blocked_by_error"
        elif as_bool(runtime_fields.get("budget_exhausted"), False):
            control_block_reason = "budget_exhausted"
        elif resume_ready:
            control_block_reason = "resume_ready"
        else:
            control_block_reason = "interrupted_not_resume_ready"
    else:
        can_accept_new_prompt = False
        control_block_reason = "resume_in_progress"

    resumed_from_run_id = _safe_str(continuation_fields.get("resumed_from_run_id"))
    resumed_from_event_id = _safe_str(continuation_fields.get("resumed_from_event_id"))
    resumed_from_stage = _safe_str(continuation_fields.get("resumed_from_stage"))
    last_completed_step = _safe_str(continuation_fields.get("last_completed_step"))

    checkpoint_stage = _safe_str(runtime_fields.get("checkpoint_stage"))
    checkpoint_summary = _safe_str(runtime_fields.get("checkpoint_summary"))

    skipped_effects = _safe_list(continuation_fields.get("skipped_effects"))
    effect_dispositions = _safe_list(continuation_fields.get("effect_dispositions"))

    return {
        "room_id": room_id,
        "run_id": run_id,
        "request_id": request_id,
        "snapshot_version": snapshot_version,
        "recorded_at": _pick_recorded_at(req) or _pick_recorded_at(prev),

        "runtime_state": runtime_state,
        "runtime_phase": runtime_phase,
        "current_run_status": current_status,
        "can_accept_new_prompt": can_accept_new_prompt,
        "control_block_reason": control_block_reason,

        "pause_requested": pause_requested,
        "pause_request_accepted": pause_request_accepted,
        "pause_reason": pause_reason,
        "pause_requested_at": pause_requested_at,
        "pause_effective": pause_effective,
        "paused_at": paused_at,
        "pause_effective_at": pause_effective_at,

        "resume_ready": resume_ready,
        "resume_from_checkpoint": resume_from_checkpoint,
        "resume_checkpoint_ref": resume_checkpoint_ref,
        "resume_token": resume_token,
        "resume_reason": resume_reason,
        "error_blocking_resume": error_blocking_resume,

        "continuation_mode": continuation_mode,
        "continuation_status": continuation_status,
        "resumed_from_run_id": resumed_from_run_id,
        "resumed_from_event_id": resumed_from_event_id,
        "resumed_from_stage": resumed_from_stage,

        "checkpoint_stage": checkpoint_stage,
        "checkpoint_summary": checkpoint_summary,
        "interruption_reason": interruption_reason,
        "last_completed_step": last_completed_step,

        "skipped_effects": skipped_effects,
        "effect_dispositions": effect_dispositions,

        "step_budget_total": _safe_non_negative_int(runtime_fields.get("step_budget_total"), 0),
        "step_budget_used": _safe_non_negative_int(runtime_fields.get("step_budget_used"), 0),
        "step_budget_remaining": _safe_non_negative_int(runtime_fields.get("step_budget_remaining"), 0),
        "budget_status": _safe_str(runtime_fields.get("budget_status")),
        "budget_exhausted": as_bool(runtime_fields.get("budget_exhausted"), False),

        "can_pause_current": runtime_state in {"running", "resuming"},
        "can_resume": runtime_state == "interrupted" and resume_ready,
    }


__all__ = [
    "_build_runtime_control_snapshot",
    "_continuation_row",
    "_normalize_continuation_mode",
    "_normalize_continuation_status",
    "_normalize_filename",
    "_normalize_fs_read_scope",
    "_normalize_rel_path",
    "_pick_recorded_at",
    "_resolve_continuation_status_fields",
    "_resolve_runtime_status_fields",
    "_safe_dict",
    "_safe_list",
    "_safe_non_negative_int",
    "_safe_str",
]

