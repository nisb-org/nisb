from __future__ import annotations

from typing import Any, Dict, List, Optional

from .room_contracts import as_bool, utc_iso
from .room_filesystem_bridge import room_supervisor_fs_audit_payload
from .room_helpers import _set_room_state_patch
from .room_store import load_state_doc
from .room_supervisor_runtime_status import (
    _normalize_fs_read_scope,
    _normalize_rel_path,
    _pick_recorded_at,
    _resolve_runtime_status_fields,
    _safe_dict,
    _safe_list,
    _safe_str,
)


def _safe_bool(value: Any, default: bool = False) -> bool:
    return as_bool(value, default)


def _safe_non_negative_int(value: Any, fallback: int = 0) -> int:
    try:
        return max(0, int(value))
    except Exception:
        try:
            return max(0, int(fallback))
        except Exception:
            return 0


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
        "interruption_reason",
        "resume_from_checkpoint",
        "resume_checkpoint_ref",
        "resume_ready",
        "resume_token",
        "resume_reason",
        "resumed_from_run_id",
        "resumed_from_event_id",
        "resumed_from_stage",
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
    prev_state: Dict[str, Any],
    continuation_row: Dict[str, Any],
    memory_resume_row: Dict[str, Any],
) -> str:
    explicit_mode = _safe_str(
        continuation_row.get("continuation_mode")
        or prev_state.get("continuation_mode")
        or prev_state.get("last_supervisor_continuation_mode")
    ).lower()
    if explicit_mode in {"fresh", "resumed"}:
        return explicit_mode

    if _safe_bool(continuation_row.get("resume_from_checkpoint"), False):
        return "resumed"
    if _safe_str(continuation_row.get("resume_checkpoint_ref")):
        return "resumed"
    if _safe_str(continuation_row.get("resumed_from_run_id")):
        return "resumed"
    if _safe_str(continuation_row.get("resumed_from_event_id")):
        return "resumed"
    if _safe_str(continuation_row.get("resumed_from_stage")):
        return "resumed"

    if _safe_bool(prev_state.get("resume_from_checkpoint"), False):
        return "resumed"
    if _safe_str(prev_state.get("resume_checkpoint_ref")):
        return "resumed"
    if _safe_str(prev_state.get("resumed_from_run_id")):
        return "resumed"
    if _safe_str(prev_state.get("resumed_from_event_id")):
        return "resumed"
    if _safe_str(prev_state.get("resumed_from_stage")):
        return "resumed"

    resume_decision = _safe_str(memory_resume_row.get("decision")).lower()
    if resume_decision in {
        "continue_from_checkpoint",
        "resume_from_checkpoint",
        "resume",
        "continue",
    }:
        return "resumed"

    return "fresh"


def _derive_effect_dispositions_fallback(
    *,
    notebook_write_row: Dict[str, Any],
    memory_write_row: Dict[str, Any],
) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []

    notebook_disposition = _safe_str(notebook_write_row.get("effect_disposition"))
    if notebook_disposition:
        rows.append(
            {
                "effect_type": "notebook_write",
                "effect_key": _safe_str(notebook_write_row.get("effect_key")),
                "checkpoint_stage": _safe_str(
                    notebook_write_row.get("checkpoint_stage"),
                    "supervisor_persistence",
                ),
                "disposition": notebook_disposition,
            }
        )

    memory_disposition = _safe_str(memory_write_row.get("effect_disposition"))
    if memory_disposition:
        rows.append(
            {
                "effect_type": "memory_write",
                "effect_key": _safe_str(memory_write_row.get("effect_key")),
                "checkpoint_stage": _safe_str(
                    memory_write_row.get("checkpoint_stage"),
                    "supervisor_persistence",
                ),
                "disposition": memory_disposition,
            }
        )

    return rows


def _resolve_continuation_fields(
    *,
    prev_state: Dict[str, Any],
    request_row: Dict[str, Any],
    notebook_write_row: Dict[str, Any],
    memory_resume_row: Dict[str, Any],
    memory_write_row: Dict[str, Any],
    status: str,
    finished: bool,
    checkpoint_stage: str,
    interruption_reason: str,
) -> Dict[str, Any]:
    continuation = _continuation_row(request_row)
    continuation_mode = _resolve_continuation_mode(
        prev_state=prev_state,
        continuation_row=continuation,
        memory_resume_row=memory_resume_row,
    )

    pause_requested = _safe_bool(
        continuation.get("pause_requested"),
        _safe_bool(
            prev_state.get("pause_requested"),
            _safe_bool(prev_state.get("last_supervisor_pause_requested"), False),
        ),
    )
    if _safe_str(interruption_reason) == "pause_requested":
        pause_requested = True

    pause_reason = _safe_str(
        continuation.get("pause_reason")
        or prev_state.get("pause_reason")
        or prev_state.get("last_supervisor_pause_reason")
    )
    if pause_requested and not pause_reason:
        pause_reason = "pause requested"

    paused_at = _safe_str(
        continuation.get("paused_at")
        or prev_state.get("paused_at")
        or prev_state.get("last_supervisor_paused_at")
    )
    if finished and _safe_str(status) == "interrupted" and _safe_str(interruption_reason) == "pause_requested" and not paused_at:
        paused_at = utc_iso()

    resume_from_checkpoint = _safe_bool(
        continuation.get("resume_from_checkpoint"),
        _safe_bool(
            prev_state.get("resume_from_checkpoint"),
            _safe_bool(prev_state.get("last_supervisor_resume_from_checkpoint"), False),
        ),
    )
    if finished and _safe_str(status) == "interrupted":
        resume_from_checkpoint = True
    elif finished and _safe_str(status) == "success":
        resume_from_checkpoint = False

    resume_checkpoint_ref = _safe_str(
        continuation.get("resume_checkpoint_ref")
        or prev_state.get("resume_checkpoint_ref")
        or prev_state.get("last_supervisor_resume_checkpoint_ref")
    )
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
        or memory_resume_row.get("checkpoint_stage")
    )

    explicit_continuation_status = _safe_str(
        continuation.get("continuation_status")
        or prev_state.get("continuation_status")
        or prev_state.get("last_supervisor_continuation_status")
    )
    if finished and _safe_str(status) == "interrupted":
        continuation_status = "interrupted"
    elif finished and _safe_str(status) == "success":
        continuation_status = "completed_after_resume" if continuation_mode == "resumed" else "completed"
    elif _safe_str(status) == "running" and pause_requested:
        continuation_status = "pause_requested"
    else:
        continuation_status = explicit_continuation_status or "running"

    last_completed_step = _safe_str(
        continuation.get("last_completed_step")
        or prev_state.get("last_completed_step")
        or prev_state.get("last_supervisor_last_completed_step")
    )
    if finished and _safe_str(status) == "success":
        last_completed_step = "completed"
    elif checkpoint_stage and not last_completed_step:
        last_completed_step = checkpoint_stage

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
    if not effect_dispositions:
        effect_dispositions = _derive_effect_dispositions_fallback(
            notebook_write_row=notebook_write_row,
            memory_write_row=memory_write_row,
        )
    if not skipped_effects:
        skipped_effects = [
            dict(item)
            for item in effect_dispositions
            if _safe_str(_safe_dict(item).get("disposition")) == "skip"
        ]

    return {
        "continuation_mode": continuation_mode,
        "continuation_status": continuation_status,
        "pause_requested": pause_requested,
        "pause_reason": pause_reason,
        "paused_at": paused_at,
        "resume_from_checkpoint": resume_from_checkpoint,
        "resume_checkpoint_ref": resume_checkpoint_ref,
        "resumed_from_run_id": resumed_from_run_id,
        "resumed_from_event_id": resumed_from_event_id,
        "resumed_from_stage": resumed_from_stage,
        "last_completed_step": last_completed_step,
        "skipped_effects": skipped_effects,
        "effect_dispositions": effect_dispositions,
    }

def _next_runtime_control_version(
    *,
    prev_state: Dict[str, Any],
    candidate: Dict[str, Any],
) -> int:
    prev = _safe_non_negative_int(prev_state.get("runtime_control_version"), 0)
    watched_keys = (
        "runtime_control_run_id",
        "runtime_state_hint",
        "runtime_phase_hint",
        "pause_requested",
        "pause_requested_at",
        "pause_effective_at",
        "resume_ready",
        "resume_token",
        "resume_reason",
        "resume_checkpoint_ref",
        "current_run_status",
        "continuation_status",
        "interruption_reason",
    )
    changed = any(prev_state.get(k) != candidate.get(k) for k in watched_keys if k in candidate)
    return prev + 1 if changed else prev


def _compute_runtime_control_patch_fields(
    *,
    prev_state: Dict[str, Any],
    request_row: Dict[str, Any],
    continuation_fields: Dict[str, Any],
    runtime_fields: Dict[str, Any],
    memory_read_row: Dict[str, Any],
    memory_resume_row: Dict[str, Any],
    resolved_status: str,
    resolved_run_id: str,
    phase: str,
) -> Dict[str, Any]:
    continuation_row = _continuation_row(request_row)
    memory_resume_from_read = _safe_dict(memory_read_row.get("resume"))

    pause_requested_at = _safe_str(
        continuation_row.get("pause_requested_at")
        or prev_state.get("pause_requested_at")
        or prev_state.get("last_supervisor_pause_requested_at")
    )
    if continuation_fields.get("pause_requested") and not pause_requested_at:
        pause_requested_at = utc_iso()

    pause_effective_at = _safe_str(
        continuation_row.get("pause_effective_at")
        or continuation_row.get("paused_at")
        or prev_state.get("pause_effective_at")
        or prev_state.get("paused_at")
        or prev_state.get("last_supervisor_paused_at")
    )
    if (
        _safe_str(resolved_status).lower() == "interrupted"
        and _safe_str(runtime_fields.get("interruption_reason")) == "pause_requested"
        and not pause_effective_at
    ):
        pause_effective_at = _safe_str(continuation_fields.get("paused_at")) or utc_iso()

    resume_token = _safe_str(
        continuation_row.get("resume_token")
        or memory_resume_row.get("resume_token")
        or memory_resume_from_read.get("resume_token")
        or prev_state.get("resume_token")
    )
    if (
        continuation_fields.get("resume_from_checkpoint")
        and _safe_str(continuation_fields.get("resume_checkpoint_ref"))
        and not resume_token
    ):
        anchor = _safe_str(continuation_fields.get("resume_checkpoint_ref")) or _safe_str(pause_effective_at)
        resume_token = f"{_safe_str(resolved_run_id or prev_state.get('current_run_id'))}:{anchor}"

    resume_ready = _safe_bool(
        continuation_row.get("resume_ready"),
        _safe_bool(
            memory_resume_row.get("resume_ready"),
            _safe_bool(
                memory_resume_from_read.get("resume_ready"),
                _safe_bool(prev_state.get("resume_ready"), False),
            ),
        ),
    )
    if (
        _safe_str(resolved_status).lower() == "interrupted"
        and _safe_str(continuation_fields.get("resume_checkpoint_ref"))
    ):
        resume_ready = True
    if _safe_str(resolved_status).lower() == "running" and _safe_str(continuation_fields.get("continuation_mode")) == "resumed":
        resume_ready = False

    resume_reason = _safe_str(
        continuation_row.get("resume_reason")
        or memory_resume_row.get("reason")
        or memory_resume_from_read.get("resume_reason")
        or prev_state.get("resume_reason")
    )
    if resume_ready and not resume_reason:
        resume_reason = "checkpoint_ready"

    error_blocking_resume = _safe_bool(
        continuation_row.get("error_blocking_resume"),
        _safe_bool(prev_state.get("error_blocking_resume"), False),
    )

    runtime_control_run_id = _safe_str(prev_state.get("runtime_control_run_id"))
    if not runtime_control_run_id and resolved_run_id:
        runtime_control_run_id = resolved_run_id
    elif resolved_run_id and _safe_str(continuation_fields.get("continuation_mode")) == "resumed":
        runtime_control_run_id = resolved_run_id
    elif resolved_run_id and runtime_control_run_id == _safe_str(prev_state.get("current_run_id")):
        runtime_control_run_id = resolved_run_id

    status_lower = _safe_str(resolved_status).lower()
    if status_lower in {"error", "failed"}:
        runtime_state_hint = "failed"
    elif bool(runtime_fields.get("budget_exhausted")) and status_lower == "interrupted":
        runtime_state_hint = "budget_exhausted"
    elif _safe_str(continuation_fields.get("continuation_status")) == "pause_requested":
        runtime_state_hint = "pause_requested"
    elif status_lower == "interrupted":
        runtime_state_hint = "interrupted"
    elif _safe_str(continuation_fields.get("continuation_mode")) == "resumed" and status_lower == "running":
        runtime_state_hint = "resuming"
    elif status_lower in {"completed", "success"} or _safe_str(continuation_fields.get("continuation_status")) in {"completed", "completed_after_resume"}:
        runtime_state_hint = "completed"
    elif status_lower == "running":
        runtime_state_hint = "running"
    else:
        runtime_state_hint = _safe_str(prev_state.get("runtime_state_hint"), "idle")

    runtime_phase_hint = _safe_str(phase)
    if runtime_state_hint == "pause_requested":
        runtime_phase_hint = runtime_phase_hint or "waiting_checkpoint"
    elif runtime_state_hint in {"completed", "failed", "interrupted", "budget_exhausted"} and not runtime_phase_hint:
        runtime_phase_hint = "idle"

    candidate = {
        "pause_requested_at": pause_requested_at,
        "pause_effective_at": pause_effective_at,
        "resume_ready": resume_ready,
        "resume_token": resume_token,
        "resume_reason": resume_reason,
        "error_blocking_resume": error_blocking_resume,
        "runtime_control_run_id": runtime_control_run_id,
        "runtime_state_hint": runtime_state_hint,
        "runtime_phase_hint": runtime_phase_hint,
        "pause_requested": continuation_fields.get("pause_requested"),
        "continuation_status": continuation_fields.get("continuation_status"),
        "resume_checkpoint_ref": continuation_fields.get("resume_checkpoint_ref"),
        "current_run_status": resolved_status,
        "interruption_reason": runtime_fields.get("interruption_reason"),
    }
    candidate["runtime_control_version"] = _next_runtime_control_version(
        prev_state=prev_state,
        candidate=candidate,
    )
    return candidate

def _build_supervisor_runtime_patch_payload(
    *,
    room_id: str,
    phase: str,
    status: str,
    plan_summary: str = "",
    fs_context: Optional[Dict[str, Any]] = None,
    notebook_read_result: Optional[Dict[str, Any]] = None,
    notebook_result: Optional[Dict[str, Any]] = None,
    memory_read_result: Optional[Dict[str, Any]] = None,
    memory_resume_result: Optional[Dict[str, Any]] = None,
    memory_result: Optional[Dict[str, Any]] = None,
    request_args: Optional[Dict[str, Any]] = None,
    run_id: str = "",
    finished: bool = False,
    step_budget_total: int = 0,
    step_budget_used: int = 0,
    step_budget_remaining: int = 0,
    budget_status: str = "",
    budget_exhausted: bool = False,
    checkpoint_stage: str = "",
    checkpoint_summary: str = "",
    interruption_reason: str = "",
) -> Dict[str, Any]:
    fs_row = room_supervisor_fs_audit_payload(_safe_dict(fs_context)) if isinstance(fs_context, dict) else {}
    notebook_read_row = _safe_dict(notebook_read_result)
    notebook_write_row = _safe_dict(notebook_result)
    memory_read_row = _safe_dict(memory_read_result)
    memory_resume_row = _safe_dict(memory_resume_result)
    memory_write_row = _safe_dict(memory_result)

    prev_state = _safe_dict(load_state_doc(room_id))
    request_row = _safe_dict(request_args)
    actor_row = _safe_dict(request_row.get("room_actor_context"))

    memory_checkpoint_row = _safe_dict(memory_read_row.get("checkpoint"))
    memory_resume_row_from_read = _safe_dict(memory_read_row.get("resume"))

    resolved_status = _safe_str(status)
    resolved_run_id = _safe_str(run_id)
    notebook_write_relative_path = _normalize_rel_path(notebook_write_row.get("relative_path"))

    runtime_fields = _resolve_runtime_status_fields(
        prev_state=prev_state,
        request_row=request_row,
        step_budget_total=step_budget_total,
        step_budget_used=step_budget_used,
        step_budget_remaining=step_budget_remaining,
        budget_status=budget_status,
        budget_exhausted=budget_exhausted,
        checkpoint_stage=checkpoint_stage,
        checkpoint_summary=checkpoint_summary,
        interruption_reason=interruption_reason,
    )

    continuation_fields = _resolve_continuation_fields(
        prev_state=prev_state,
        request_row=request_row,
        notebook_write_row=notebook_write_row,
        memory_resume_row=memory_resume_row,
        memory_write_row=memory_write_row,
        status=resolved_status,
        finished=finished,
        checkpoint_stage=runtime_fields["checkpoint_stage"],
        interruption_reason=runtime_fields["interruption_reason"],
    )

    runtime_control_fields = _compute_runtime_control_patch_fields(
        prev_state=prev_state,
        request_row=request_row,
        continuation_fields=continuation_fields,
        runtime_fields=runtime_fields,
        memory_read_row=memory_read_row,
        memory_resume_row=memory_resume_row,
        resolved_status=resolved_status,
        resolved_run_id=resolved_run_id,
        phase=_safe_str(phase),
    )

    patch = {
        "last_supervisor_phase": _safe_str(phase),
        "last_supervisor_status": resolved_status,
        "last_supervisor_updated_at": utc_iso(),
        "last_plan_summary": _safe_str(plan_summary),
        "last_plan_at": utc_iso() if plan_summary else _safe_str(prev_state.get("last_plan_at")),
        "last_supervisor_actor_context": actor_row,
        "last_supervisor_actor_type": _safe_str(actor_row.get("actor_type"), "supervisor"),
        "last_supervisor_actor_id": _safe_str(actor_row.get("actor_id"), "supervisor"),
        "last_supervisor_skill_id": _safe_str(actor_row.get("skill_id")),
        "last_supervisor_delegated_from": _safe_str(actor_row.get("delegated_from")),
        "last_supervisor_fs_read_enabled": as_bool(fs_row.get("enabled"), bool(_safe_str(fs_row.get("status")))),
        "last_supervisor_fs_read_status": _safe_str(fs_row.get("status")),
        "last_supervisor_fs_read_reason": _safe_str(fs_row.get("reason_code") or fs_row.get("message")),
        "last_supervisor_fs_read_focus_root": _normalize_rel_path(fs_row.get("focus_root")),
        "last_supervisor_fs_read_scope": _normalize_fs_read_scope(fs_row.get("scope"), "minimal"),
        "last_supervisor_fs_read_entries_count": int(fs_row.get("entries_count") or 0),
        "last_supervisor_fs_read_at": _pick_recorded_at(fs_row),
        "last_supervisor_tool_calls": _safe_list(fs_row.get("tool_calls")),
        "last_supervisor_tool_results": _safe_list(fs_row.get("tool_results")),
        "last_supervisor_notebook_read_enabled": as_bool(
            notebook_read_row.get("enabled"),
            bool(_safe_str(notebook_read_row.get("status"))),
        ),
        "last_supervisor_notebook_read_status": _safe_str(notebook_read_row.get("status")),
        "last_supervisor_notebook_read_message": _safe_str(notebook_read_row.get("message")),
        "last_supervisor_notebook_read_relative_path": _normalize_rel_path(notebook_read_row.get("relative_path")),
        "last_supervisor_notebook_read_at": _pick_recorded_at(notebook_read_row),
        "last_supervisor_notebook_read_tool_calls": _safe_list(notebook_read_row.get("tool_calls")),
        "last_supervisor_notebook_read_tool_results": _safe_list(notebook_read_row.get("tool_results")),
        "last_supervisor_notebook_write_enabled": as_bool(
            notebook_write_row.get("enabled"),
            bool(_safe_str(notebook_write_row.get("status"))),
        ),
        "last_supervisor_notebook_write_status": _safe_str(notebook_write_row.get("status")),
        "last_supervisor_notebook_write_message": _safe_str(notebook_write_row.get("message")),
        "last_supervisor_notebook_write_relative_path": notebook_write_relative_path,
        "last_supervisor_notebook_relative_path": notebook_write_relative_path,
        "last_supervisor_notebook_write_at": _pick_recorded_at(notebook_write_row),
        "last_supervisor_notebook_bytes_written": int(notebook_write_row.get("bytes_written") or 0),
        "last_supervisor_notebook_tool_calls": _safe_list(notebook_write_row.get("tool_calls")),
        "last_supervisor_notebook_tool_results": _safe_list(notebook_write_row.get("tool_results")),
        "last_supervisor_notebook_policy_allowed": as_bool(
            notebook_write_row.get("policy_allowed"),
            False,
        ),
        "last_supervisor_notebook_policy_status": _safe_str(notebook_write_row.get("policy_status")),
        "last_supervisor_notebook_policy_reason": _safe_str(
            notebook_write_row.get("policy_reason_code") or notebook_write_row.get("reason_code")
        ),
        "last_supervisor_notebook_policy_message": _safe_str(
            notebook_write_row.get("policy_message") or notebook_write_row.get("message")
        ),
        "last_supervisor_notebook_write_effect_disposition": _safe_str(
            notebook_write_row.get("effect_disposition")
        ),
        "last_supervisor_notebook_write_effect_key": _safe_str(
            notebook_write_row.get("effect_key")
        ),
        "last_supervisor_memory_read_enabled": as_bool(
            memory_read_row.get("enabled"),
            bool(_safe_str(memory_read_row.get("status"))),
        ),
        "last_supervisor_memory_read_status": _safe_str(memory_read_row.get("status")),
        "last_supervisor_memory_read_message": _safe_str(memory_read_row.get("message")),
        "last_supervisor_memory_read_reason": _safe_str(memory_read_row.get("reason_code")),
        "last_supervisor_memory_read_relative_path": _normalize_rel_path(memory_read_row.get("relative_path")),
        "last_supervisor_memory_read_at": _pick_recorded_at(memory_read_row),
        "last_supervisor_memory_version": int(memory_read_row.get("version") or 0),
        "last_supervisor_memory_checkpoint_stage": _safe_str(memory_checkpoint_row.get("stage")),
        "last_supervisor_memory_checkpoint_summary": _safe_str(memory_checkpoint_row.get("summary")),
        "last_supervisor_memory_recovery_hint": _safe_str(memory_checkpoint_row.get("recovery_hint")),
        "last_supervisor_memory_resume_ready": as_bool(
            memory_resume_row_from_read.get("resume_ready"),
            False,
        ),
        "last_supervisor_memory_resume_decision": _safe_str(memory_resume_row.get("decision")),
        "last_supervisor_memory_resume_reason": _safe_str(memory_resume_row.get("reason")),
        "last_supervisor_memory_resume_ready_decision": as_bool(
            memory_resume_row.get("resume_ready"),
            False,
        ),
        "last_supervisor_memory_resume_relative_path": _normalize_rel_path(
            memory_resume_row.get("relative_path")
        ),
        "last_supervisor_memory_resume_checkpoint_stage": _safe_str(
            memory_resume_row.get("checkpoint_stage")
        ),
        "last_supervisor_memory_resume_checkpoint_summary": _safe_str(
            memory_resume_row.get("checkpoint_summary")
        ),
        "last_supervisor_memory_resume_recovery_hint": _safe_str(
            memory_resume_row.get("recovery_hint")
        ),
        "last_supervisor_memory_write_enabled": as_bool(
            memory_write_row.get("enabled"),
            bool(_safe_str(memory_write_row.get("status"))),
        ),
        "last_supervisor_memory_write_status": _safe_str(memory_write_row.get("status")),
        "last_supervisor_memory_write_message": _safe_str(memory_write_row.get("message")),
        "last_supervisor_memory_write_reason": _safe_str(memory_write_row.get("reason_code")),
        "last_supervisor_memory_write_relative_path": _normalize_rel_path(
            memory_write_row.get("relative_path")
        ),
        "last_supervisor_memory_write_at": _pick_recorded_at(memory_write_row),
        "last_supervisor_memory_bytes_written": int(memory_write_row.get("bytes_written") or 0),
        "last_supervisor_memory_write_checkpoint_stage": _safe_str(
            memory_write_row.get("checkpoint_stage")
        ),
        "last_supervisor_memory_write_checkpoint_summary": _safe_str(
            memory_write_row.get("checkpoint_summary")
        ),
        "last_supervisor_memory_write_resume_decision": _safe_str(
            memory_write_row.get("resume_decision")
        ),
        "last_supervisor_memory_write_resume_reason": _safe_str(
            memory_write_row.get("resume_reason")
        ),
        "last_supervisor_memory_write_effect_disposition": _safe_str(
            memory_write_row.get("effect_disposition")
        ),
        "last_supervisor_memory_write_effect_key": _safe_str(
            memory_write_row.get("effect_key")
        ),
        "last_supervisor_memory_relative_path": _normalize_rel_path(
            memory_write_row.get("relative_path") or memory_read_row.get("relative_path")
        ),
        "step_budget_total": runtime_fields["step_budget_total"],
        "step_budget_used": runtime_fields["step_budget_used"],
        "step_budget_remaining": runtime_fields["step_budget_remaining"],
        "budget_status": runtime_fields["budget_status"],
        "budget_exhausted": runtime_fields["budget_exhausted"],
        "checkpoint_stage": runtime_fields["checkpoint_stage"],
        "checkpoint_summary": runtime_fields["checkpoint_summary"],
        "interruption_reason": runtime_fields["interruption_reason"],
        "continuation_mode": continuation_fields["continuation_mode"],
        "continuation_status": continuation_fields["continuation_status"],
        "pause_requested_at": _safe_str(runtime_control_fields.get("pause_requested_at")),
        "pause_effective_at": _safe_str(runtime_control_fields.get("pause_effective_at")),
        "resume_ready": _safe_bool(runtime_control_fields.get("resume_ready"), False),
        "resume_token": _safe_str(runtime_control_fields.get("resume_token")),
        "resume_reason": _safe_str(runtime_control_fields.get("resume_reason")),
        "error_blocking_resume": _safe_bool(runtime_control_fields.get("error_blocking_resume"), False),
        "runtime_control_run_id": _safe_str(runtime_control_fields.get("runtime_control_run_id")),
        "runtime_state_hint": _safe_str(runtime_control_fields.get("runtime_state_hint")),
        "runtime_phase_hint": _safe_str(runtime_control_fields.get("runtime_phase_hint")),
        "runtime_control_version": _safe_non_negative_int(runtime_control_fields.get("runtime_control_version"), 0),

        "last_supervisor_pause_requested_at": _safe_str(runtime_control_fields.get("pause_requested_at")),
        "last_supervisor_pause_effective_at": _safe_str(runtime_control_fields.get("pause_effective_at")),
        "last_supervisor_resume_ready": _safe_bool(runtime_control_fields.get("resume_ready"), False),
        "last_supervisor_resume_token": _safe_str(runtime_control_fields.get("resume_token")),
        "last_supervisor_resume_reason": _safe_str(runtime_control_fields.get("resume_reason")),
        "pause_requested": continuation_fields["pause_requested"],
        "pause_reason": continuation_fields["pause_reason"],
        "paused_at": continuation_fields["paused_at"],
        "resume_from_checkpoint": continuation_fields["resume_from_checkpoint"],
        "resume_checkpoint_ref": continuation_fields["resume_checkpoint_ref"],
        "resumed_from_run_id": continuation_fields["resumed_from_run_id"],
        "resumed_from_event_id": continuation_fields["resumed_from_event_id"],
        "resumed_from_stage": continuation_fields["resumed_from_stage"],
        "last_completed_step": continuation_fields["last_completed_step"],
        "skipped_effects": _safe_list(continuation_fields["skipped_effects"]),
        "effect_dispositions": _safe_list(continuation_fields["effect_dispositions"]),
        "last_supervisor_continuation_mode": continuation_fields["continuation_mode"],
        "last_supervisor_continuation_status": continuation_fields["continuation_status"],
        "last_supervisor_pause_requested": continuation_fields["pause_requested"],
        "last_supervisor_pause_reason": continuation_fields["pause_reason"],
        "last_supervisor_paused_at": continuation_fields["paused_at"],
        "last_supervisor_resume_from_checkpoint": continuation_fields["resume_from_checkpoint"],
        "last_supervisor_resume_checkpoint_ref": continuation_fields["resume_checkpoint_ref"],
        "last_supervisor_resumed_from_run_id": continuation_fields["resumed_from_run_id"],
        "last_supervisor_resumed_from_event_id": continuation_fields["resumed_from_event_id"],
        "last_supervisor_resumed_from_stage": continuation_fields["resumed_from_stage"],
        "last_supervisor_last_completed_step": continuation_fields["last_completed_step"],
        "last_supervisor_skipped_effects": _safe_list(continuation_fields["skipped_effects"]),
        "last_supervisor_effect_dispositions": _safe_list(continuation_fields["effect_dispositions"]),
    }

    if resolved_run_id:
        patch["current_run_id"] = resolved_run_id

    if finished:
        if resolved_status:
            patch["current_run_status"] = resolved_status
        patch["last_run_finished_at"] = utc_iso()
    elif resolved_status in {"running", "interrupted"}:
        patch["current_run_status"] = resolved_status

    return patch


def _patch_supervisor_runtime_state(
    room_id: str,
    *,
    phase: str,
    status: str,
    plan_summary: str = "",
    fs_context: Optional[Dict[str, Any]] = None,
    notebook_read_result: Optional[Dict[str, Any]] = None,
    notebook_result: Optional[Dict[str, Any]] = None,
    memory_read_result: Optional[Dict[str, Any]] = None,
    memory_resume_result: Optional[Dict[str, Any]] = None,
    memory_result: Optional[Dict[str, Any]] = None,
    request_args: Optional[Dict[str, Any]] = None,
    run_id: str = "",
    finished: bool = False,
    step_budget_total: int = 0,
    step_budget_used: int = 0,
    step_budget_remaining: int = 0,
    budget_status: str = "",
    budget_exhausted: bool = False,
    checkpoint_stage: str = "",
    checkpoint_summary: str = "",
    interruption_reason: str = "",
) -> None:
    patch = _build_supervisor_runtime_patch_payload(
        room_id=room_id,
        phase=phase,
        status=status,
        plan_summary=plan_summary,
        fs_context=fs_context,
        notebook_read_result=notebook_read_result,
        notebook_result=notebook_result,
        memory_read_result=memory_read_result,
        memory_resume_result=memory_resume_result,
        memory_result=memory_result,
        request_args=request_args,
        run_id=run_id,
        finished=finished,
        step_budget_total=step_budget_total,
        step_budget_used=step_budget_used,
        step_budget_remaining=step_budget_remaining,
        budget_status=budget_status,
        budget_exhausted=budget_exhausted,
        checkpoint_stage=checkpoint_stage,
        checkpoint_summary=checkpoint_summary,
        interruption_reason=interruption_reason,
    )
    _set_room_state_patch(room_id, patch)


__all__ = [
    "_build_supervisor_runtime_patch_payload",
    "_patch_supervisor_runtime_state",
]

