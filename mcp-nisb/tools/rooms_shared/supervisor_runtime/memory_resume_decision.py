from __future__ import annotations

from typing import Any, Dict

from ..room_contracts import as_bool, utc_iso
from .memory_resume_common import (
    _safe_dict,
    _safe_str,
)
from .memory_resume_text import (
    _checkpoint_marked_stale,
    _classify_checkpoint_relation,
    _derive_topic_anchor,
    _extract_explicit_topic_tail,
    _is_generic_continue_tail,
    _looks_like_continue_intent,
    _looks_like_followup_without_continue,
    _looks_like_restart_intent,
    _strip_continue_lead_in,
    _strip_resume_test_annotation,
    classify_supervisor_memory_resume_context,
)


def _build_memory_resume_result(
    *,
    row: Dict[str, Any],
    decision: str,
    reason: str,
    resume_ready: bool,
    stage: str,
    summary: str,
    recovery_hint: str,
    checkpoint_question: str = "",
    topic_anchor: str = "",
    confidence: Any = None,
    relation: str = "",
    context_dependent: bool = False,
    self_contained_new_topic: bool = False,
) -> Dict[str, Any]:
    normalized_decision = _safe_str(decision, "none")
    safe_topic_anchor = _safe_str(topic_anchor) if normalized_decision == "continue_from_checkpoint" else ""

    return {
        "enabled": True,
        "status": "success",
        "decision": normalized_decision,
        "reason": _safe_str(reason),
        "resume_ready": bool(resume_ready),
        "relative_path": _safe_str(row.get("relative_path")),
        "checkpoint_stage": _safe_str(stage),
        "checkpoint_summary": _safe_str(summary),
        "checkpoint_question": _safe_str(checkpoint_question),
        "topic_anchor": safe_topic_anchor,
        "recovery_hint": _safe_str(recovery_hint),
        "confidence": confidence,
        "relation": _safe_str(relation),
        "context_dependent": bool(context_dependent),
        "self_contained_new_topic": bool(self_contained_new_topic),
        "tool_calls": [],
        "tool_results": [],
        "recorded_at": utc_iso(),
    }


def _result_from_classifier(
    *,
    row: Dict[str, Any],
    classifier_result: Dict[str, Any],
    resume_ready: bool,
    stage: str,
    summary: str,
    recovery_hint: str,
    checkpoint_question: str,
    topic_anchor: str,
) -> Dict[str, Any]:
    cls = _safe_dict(classifier_result)
    return _build_memory_resume_result(
        row=row,
        decision=_safe_str(cls.get("decision"), "none"),
        reason=_safe_str(cls.get("reason")),
        resume_ready=resume_ready,
        stage=stage,
        summary=summary,
        recovery_hint=recovery_hint,
        checkpoint_question=checkpoint_question,
        topic_anchor=topic_anchor,
        confidence=cls.get("confidence"),
        relation=_safe_str(cls.get("relation")),
        context_dependent=bool(cls.get("context_dependent")),
        self_contained_new_topic=bool(cls.get("self_contained_new_topic")),
    )


def decide_supervisor_memory_resume(
    *,
    question: str,
    memory_read_result: Dict[str, Any],
) -> Dict[str, Any]:
    row = _safe_dict(memory_read_result)
    checkpoint = _safe_dict(row.get("checkpoint"))
    resume = _safe_dict(row.get("resume"))
    status = _safe_str(row.get("status")).lower()

    checkpoint_question = _safe_str(checkpoint.get("question"))
    checkpoint_summary = _safe_str(checkpoint.get("summary"))

    if status == "missing":
        return _build_memory_resume_result(
            row=row,
            decision="none",
            reason="checkpoint_missing",
            resume_ready=False,
            stage="",
            summary="",
            recovery_hint="",
            checkpoint_question="",
            topic_anchor="",
            confidence=None,
            relation="",
        )

    if status == "invalid":
        return _build_memory_resume_result(
            row=row,
            decision="none",
            reason="checkpoint_invalid",
            resume_ready=False,
            stage="",
            summary="",
            recovery_hint="",
            checkpoint_question="",
            topic_anchor="",
            confidence=None,
            relation="",
        )

    explicit_topic_tail = _extract_explicit_topic_tail(question)
    topic_anchor = _derive_topic_anchor(
        checkpoint=checkpoint,
        question=question,
        explicit_topic_tail=explicit_topic_tail,
    )

    summary = checkpoint_summary
    stage = _safe_str(checkpoint.get("stage"))
    recovery_hint = _safe_str(checkpoint.get("recovery_hint"))
    resume_ready = as_bool(
        resume.get("resume_ready"),
        bool(
            summary
            or recovery_hint
            or stage
            or checkpoint_question
            or _safe_str(checkpoint.get("plan_summary"))
            or topic_anchor
        ),
    )

    if not resume_ready:
        return _build_memory_resume_result(
            row=row,
            decision="none",
            reason="checkpoint_not_ready",
            resume_ready=False,
            stage=stage,
            summary=summary,
            recovery_hint=recovery_hint,
            checkpoint_question=checkpoint_question,
            topic_anchor="",
            confidence=None,
            relation="",
        )

    stale_checkpoint, stale_reason = _checkpoint_marked_stale(row)
    if stale_checkpoint:
        return _build_memory_resume_result(
            row=row,
            decision="ignore_stale_checkpoint",
            reason=stale_reason or "stale_checkpoint",
            resume_ready=True,
            stage=stage,
            summary=summary,
            recovery_hint=recovery_hint,
            checkpoint_question=checkpoint_question,
            topic_anchor="",
            confidence=0.96,
            relation="stale",
        )

    continue_intent = _looks_like_continue_intent(question)
    restart_intent = _looks_like_restart_intent(question)
    followup_without_continue = _looks_like_followup_without_continue(question)

    stripped_tail = _strip_resume_test_annotation(_strip_continue_lead_in(question))
    generic_continue = _is_generic_continue_tail(stripped_tail)

    explicit_topic_tail = explicit_topic_tail or _extract_explicit_topic_tail(stripped_tail)
    context_probe = _strip_resume_test_annotation(explicit_topic_tail or stripped_tail or question)
    relation = _classify_checkpoint_relation(context_probe, checkpoint)

    classifier_result = classify_supervisor_memory_resume_context(
        question=question,
        checkpoint=checkpoint,
        relation=relation,
        continue_intent=continue_intent,
        restart_intent=restart_intent,
        followup_without_continue=followup_without_continue,
        generic_continue=generic_continue,
    )

    return _result_from_classifier(
        row=row,
        classifier_result=classifier_result,
        resume_ready=True,
        stage=stage,
        summary=summary,
        recovery_hint=recovery_hint,
        checkpoint_question=checkpoint_question,
        topic_anchor=topic_anchor,
    )


__all__ = [
    "_build_memory_resume_result",
    "decide_supervisor_memory_resume",
]
