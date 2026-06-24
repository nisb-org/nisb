from __future__ import annotations

import json
from typing import Any, Dict, List

from ..room_contracts import as_bool, utc_iso
from .memory_resume_common import (
    _safe_dict,
    _safe_list,
    _safe_str,
    _truncate_text,
)
from .memory_resume_paths import (
    disabled_memory_result,
    resolve_supervisor_memory_path,
)
from .memory_resume_text import (
    _extract_explicit_topic_tail,
    _looks_like_continue_intent,
    _looks_like_followup_without_continue,
)


def augment_plan_summary_with_memory_resume(
    plan_summary: str,
    memory_read_result: Dict[str, Any],
    memory_resume_result: Dict[str, Any],
) -> str:
    base = _safe_str(plan_summary)
    memory_row = _safe_dict(memory_read_result)
    resume_row = _safe_dict(memory_resume_result)

    if not memory_row and not resume_row:
        return base

    relative_path = _safe_str(resume_row.get("relative_path") or memory_row.get("relative_path"))
    decision = _safe_str(resume_row.get("decision")).lower()
    reason = _safe_str(resume_row.get("reason")).lower()
    stage = _safe_str(resume_row.get("checkpoint_stage") or _safe_dict(memory_row.get("checkpoint")).get("stage"))
    summary = _safe_str(
        resume_row.get("checkpoint_summary") or _safe_dict(memory_row.get("checkpoint")).get("summary")
    )
    recovery_hint = _safe_str(
        resume_row.get("recovery_hint") or _safe_dict(memory_row.get("checkpoint")).get("recovery_hint")
    )
    checkpoint_question = _safe_str(
        resume_row.get("checkpoint_question") or _safe_dict(memory_row.get("checkpoint")).get("question")
    )
    topic_anchor = _safe_str(
        resume_row.get("topic_anchor") or _safe_dict(memory_row.get("checkpoint")).get("topic_anchor")
    )

    if not relative_path:
        return base

    lines = [line.strip() for line in base.splitlines() if _safe_str(line)]
    dedupe_text = "\n".join(lines).lower()
    if relative_path.lower() in dedupe_text and "checkpoint" in dedupe_text:
        return base

    if decision == "continue_from_checkpoint":
        sentence = (
            f"Structured checkpoint loaded ({relative_path}). "
            f"Resume decision: continue_from_checkpoint. "
            f"Previous stage: {stage or 'unknown'}. "
            "Continue from the existing record first."
        )
    elif decision == "restart_fresh":
        sentence = (
            f"Structured checkpoint loaded ({relative_path}), "
            "but the current run is classified as restart_fresh. "
            f"Reason: {reason or 'user_intent_conflicts'}."
        )
    elif decision == "ignore_stale_checkpoint":
        sentence = (
            f"Structured checkpoint loaded ({relative_path}), "
            "but the previous checkpoint is ignored for this run. "
            f"Reason: {reason or 'stale_checkpoint'}."
        )
    elif reason == "checkpoint_missing":
        sentence = (
            f"No structured checkpoint was found ({relative_path}). "
            "Proceeding as a fresh run."
        )
    elif reason == "checkpoint_invalid":
        sentence = (
            f"The structured checkpoint is invalid ({relative_path}). "
            "Proceeding as a fresh run."
        )
    else:
        sentence = (
            f"Structured checkpoint checked ({relative_path}). "
            "No resume state is applied for this run."
        )

    if decision == "continue_from_checkpoint":
        if checkpoint_question:
            sentence = f"{sentence} Previous question: {_truncate_text(checkpoint_question, 80)}"
        if topic_anchor:
            sentence = f"{sentence} Topic anchor: {_truncate_text(topic_anchor, 80)}"
        if summary:
            sentence = f"{sentence} Recent summary: {_truncate_text(summary, 120)}"
        if recovery_hint:
            sentence = f"{sentence} Recovery hint: {_truncate_text(recovery_hint, 120)}"

    if not lines:
        return sentence

    insert_at = 2 if len(lines) >= 2 else len(lines)
    lines.insert(insert_at, sentence)
    return "\n".join(lines)


def _select_checkpoint_topic_anchor(
    *,
    question: str,
    final_text: str,
    previous_checkpoint: Dict[str, Any],
    memory_resume_result: Dict[str, Any],
) -> str:
    decision = _safe_str(memory_resume_result.get("decision")).lower()
    current_question = _safe_str(question)

    if decision == "continue_from_checkpoint":
        for candidate in [
            memory_resume_result.get("topic_anchor"),
            previous_checkpoint.get("topic_anchor"),
            _extract_explicit_topic_tail(current_question),
            current_question,
        ]:
            text = _safe_str(candidate)
            if text:
                return _truncate_text(text, 120)
        return ""

    question_is_contextual = bool(
        _looks_like_continue_intent(current_question)
        or _looks_like_followup_without_continue(current_question)
    )

    if not question_is_contextual:
        for candidate in [
            _extract_explicit_topic_tail(current_question),
            current_question,
            _extract_explicit_topic_tail(final_text),
            final_text,
        ]:
            text = _safe_str(candidate)
            if text:
                return _truncate_text(text, 120)
        return ""

    for candidate in [
        _extract_explicit_topic_tail(final_text),
        final_text,
    ]:
        text = _safe_str(candidate)
        if text:
            return _truncate_text(text, 120)

    return ""


def build_supervisor_memory_checkpoint(
    *,
    question: str,
    plan_summary: str,
    fs_context: Dict[str, Any],
    memory_read_result: Dict[str, Any],
    memory_resume_result: Dict[str, Any],
    final_text: str,
    delegate_packets: List[Dict[str, Any]],
    run_id: str = "",
    supervisor_event_id: str = "",
) -> Dict[str, Any]:
    previous_checkpoint = _safe_dict(memory_read_result.get("checkpoint"))
    target_paths = [path for path in _safe_list(_safe_dict(fs_context).get("target_paths")) if _safe_str(path)]
    summary = _truncate_text(final_text, 500)
    previous_open_questions = [item for item in _safe_list(previous_checkpoint.get("open_questions")) if _safe_str(item)]

    checkpoint_stage = "done" if summary else _safe_str(previous_checkpoint.get("stage"), "synthesis")
    last_step = "generated supervisor final answer and refreshed structured checkpoint"
    if _safe_list(delegate_packets):
        last_step = "synthesized delegate results and refreshed structured checkpoint"

    next_actions: List[str] = []
    if target_paths:
        next_actions.append("Before continuing, verify whether the current focus_root and target_paths are still valid.")
    if _safe_str(memory_resume_result.get("decision")) == "continue_from_checkpoint":
        next_actions.append("Continue from the recovery hint in the current checkpoint first.")
    else:
        next_actions.append("If continuation is needed, explicitly state which open issue should continue from this checkpoint.")

    recovery_hint = (
        "At the next run, read the current structured checkpoint first. "
        "If the user explicitly asks to continue from the previous state, prefer continue_from_checkpoint recovery."
    )
    if target_paths:
        recovery_hint = f"{recovery_hint} Also verify whether {len(target_paths)} target_paths are still available."

    evidence_refs = []
    for path in target_paths[:8]:
        evidence_refs.append(_safe_str(path))
    if _safe_str(run_id):
        evidence_refs.append(f"run:{_safe_str(run_id)}")
    if _safe_str(supervisor_event_id):
        evidence_refs.append(f"event:{_safe_str(supervisor_event_id)}")

    topic_anchor = _select_checkpoint_topic_anchor(
        question=question,
        final_text=final_text,
        previous_checkpoint=previous_checkpoint,
        memory_resume_result=memory_resume_result,
    )

    return {
        "stage": checkpoint_stage,
        "last_step": last_step,
        "summary": summary,
        "open_questions": previous_open_questions[:6],
        "next_actions": next_actions[:6],
        "recovery_hint": recovery_hint,
        "evidence_refs": evidence_refs[:12],
        "question": _truncate_text(question, 200),
        "plan_summary": _truncate_text(plan_summary, 400),
        "topic_anchor": _truncate_text(topic_anchor, 120),
    }


def write_supervisor_memory_sidecar(
    *,
    room_id: str,
    mcp: Dict[str, Any],
    question: str,
    plan_summary: str,
    fs_context: Dict[str, Any],
    memory_read_result: Dict[str, Any],
    memory_resume_result: Dict[str, Any],
    delegate_packets: List[Dict[str, Any]],
    final_text: str,
    run_id: str = "",
    supervisor_event_id: str = "",
    final_event_id: str = "",
) -> Dict[str, Any]:
    memory_path, relative_path, source_kind = resolve_supervisor_memory_path(
        room_id=room_id,
        mcp=mcp,
    )

    if not as_bool(mcp.get("memory_write_enabled"), as_bool(mcp.get("notebook_write_enabled"), False)):
        return disabled_memory_result("memory_write not enabled")

    if not _safe_str(final_text):
        return disabled_memory_result("missing final supervisor text")

    if memory_path is None:
        return {
            "enabled": True,
            "status": "error",
            "message": "memory write path not resolved",
            "reason_code": "MEMORY_PATH_NOT_RESOLVED",
            "relative_path": relative_path,
            "bytes_written": 0,
            "tool_calls": [],
            "tool_results": [],
            "recorded_at": utc_iso(),
            "checkpoint_stage": "",
            "checkpoint_summary": "",
            "checkpoint_question": "",
            "topic_anchor": "",
            "resume_decision": _safe_str(memory_resume_result.get("decision"), "none"),
            "resume_reason": _safe_str(memory_resume_result.get("reason")),
            "source_kind": source_kind,
        }

    checkpoint = build_supervisor_memory_checkpoint(
        question=question,
        plan_summary=plan_summary,
        fs_context=fs_context,
        memory_read_result=memory_read_result,
        memory_resume_result=memory_resume_result,
        final_text=final_text,
        delegate_packets=delegate_packets,
        run_id=run_id,
        supervisor_event_id=supervisor_event_id,
    )

    memory_doc = {
        "version": 1,
        "room_id": _safe_str(room_id),
        "updated_at": utc_iso(),
        "last_run_id": _safe_str(run_id),
        "last_supervisor_event_id": _safe_str(supervisor_event_id),
        "status": "active",
        "checkpoint": checkpoint,
        "resume": {
            "resume_token": f"{_safe_str(run_id)}:{utc_iso()}",
            "resume_ready": True,
            "resume_reason": "checkpoint_ready",
            "invalidated_by": "",
        },
        "source": {
            "final_event_id": _safe_str(final_event_id),
            "relative_path": relative_path,
            "source_kind": source_kind,
        },
    }

    try:
        memory_path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(memory_doc, ensure_ascii=False, indent=2) + "\n"
        memory_path.write_text(payload, encoding="utf-8")
        bytes_written = len(payload.encode("utf-8"))
        return {
            "enabled": True,
            "status": "success",
            "message": "supervisor memory sidecar written",
            "reason_code": "MEMORY_WRITTEN",
            "relative_path": relative_path,
            "bytes_written": bytes_written,
            "tool_calls": [],
            "tool_results": [],
            "recorded_at": utc_iso(),
            "checkpoint_stage": _safe_str(checkpoint.get("stage")),
            "checkpoint_summary": _safe_str(checkpoint.get("summary")),
            "checkpoint_question": _safe_str(checkpoint.get("question")),
            "topic_anchor": _safe_str(checkpoint.get("topic_anchor")),
            "resume_decision": _safe_str(memory_resume_result.get("decision"), "none"),
            "resume_reason": _safe_str(memory_resume_result.get("reason")),
            "memory_version": 1,
            "source_kind": source_kind,
        }
    except Exception as ex:
        return {
            "enabled": True,
            "status": "error",
            "message": f"failed to write supervisor memory sidecar: {type(ex).__name__}",
            "reason_code": "MEMORY_WRITE_ERROR",
            "relative_path": relative_path,
            "bytes_written": 0,
            "tool_calls": [],
            "tool_results": [],
            "recorded_at": utc_iso(),
            "checkpoint_stage": _safe_str(checkpoint.get("stage")),
            "checkpoint_summary": _safe_str(checkpoint.get("summary")),
            "checkpoint_question": _safe_str(checkpoint.get("question")),
            "topic_anchor": _safe_str(checkpoint.get("topic_anchor")),
            "resume_decision": _safe_str(memory_resume_result.get("decision"), "none"),
            "resume_reason": _safe_str(memory_resume_result.get("reason")),
            "memory_version": 1,
            "source_kind": source_kind,
        }


__all__ = [
    "augment_plan_summary_with_memory_resume",
    "build_supervisor_memory_checkpoint",
    "write_supervisor_memory_sidecar",
]
