from __future__ import annotations

import re
from typing import Any, Dict, List, Set, Tuple

from .memory_resume_common import (
    _safe_dict,
    _safe_list,
    _safe_str,
    _truncate_text,
)
from .memory_resume_i18n_lexicon import (
    get_memory_resume_phrase_set,
    get_memory_resume_phrases,
)


_INTERNAL_LEAK_MARKERS = (
    "room side memory",
    "current worker task",
    "resume_token",
    "bearer ",
    "authorization",
    "auth_configured",
    "provider_snapshot",
    "mcp_binding",
    "grant_meta",
    "raw_doc",
    "supervisor.memory.json",
    "_room_supervisor_notebooks",
)


def _phrases(category: str) -> List[str]:
    return [_safe_str(item) for item in get_memory_resume_phrases(category) if _safe_str(item)]


def _phrase_set(category: str) -> Set[str]:
    return {_safe_str(item) for item in get_memory_resume_phrase_set(category) if _safe_str(item)}


def _looks_like_continue_intent(question: str) -> bool:
    text = _safe_str(question).lower()
    if not text:
        return False
    return any(token.lower() in text for token in _phrases("continue_intent"))


def _looks_like_restart_intent(question: str) -> bool:
    text = _safe_str(question).lower()
    if not text:
        return False
    return any(token.lower() in text for token in _phrases("restart_intent"))


def _normalize_compare_text(value: Any) -> str:
    text = _safe_str(value).lower()
    if not text:
        return ""

    out: List[str] = []
    for ch in text:
        if ch.isalnum() or ("\u4e00" <= ch <= "\u9fff"):
            out.append(ch)
        else:
            out.append(" ")

    return " ".join("".join(out).split())


def _compact_compare_text(value: Any) -> str:
    return _normalize_compare_text(value).replace(" ", "")


def _contains_phrase(text: str, phrases: Tuple[str, ...] | List[str] | Set[str]) -> bool:
    normalized = _normalize_compare_text(text)
    compact = _compact_compare_text(text)
    if not normalized and not compact:
        return False

    for phrase in phrases:
        p = _safe_str(phrase).lower()
        if not p:
            continue
        p_norm = _normalize_compare_text(p)
        p_compact = _compact_compare_text(p)
        if p_norm and p_norm in normalized:
            return True
        if p_compact and p_compact in compact:
            return True

    return False


def _contextual_reference_markers() -> Tuple[str, ...]:
    return tuple(_phrases("contextual_reference_markers"))


def _contextual_generic_heads() -> Tuple[str, ...]:
    return tuple(_phrases("contextual_generic_heads"))


def _looks_like_contextual_reference(value: Any) -> bool:
    text = _safe_str(value)
    if not text:
        return False
    return _contains_phrase(text, _contextual_reference_markers())


def _looks_like_followup_without_continue(question: str) -> bool:
    text = _normalize_compare_text(question)
    if not text:
        return False

    if any(_normalize_compare_text(token) in text for token in _phrases("followup_without_continue")):
        return True

    return bool(_looks_like_contextual_reference(question))


def _looks_like_context_dependent_task(question: str) -> bool:
    text = _safe_str(question)
    if not text:
        return False

    if _looks_like_contextual_reference(text):
        return True

    if _looks_like_continue_intent(text) and not _extract_explicit_topic_tail(text):
        return True

    stripped = _strip_continue_lead_in(text)
    if stripped and _contains_phrase(stripped, _contextual_generic_heads()):
        return True

    return False


def _char_ngrams(value: Any, n: int = 2) -> Set[str]:
    text = _compact_compare_text(value)
    if not text:
        return set()
    if len(text) <= n:
        return {text}
    return {text[i : i + n] for i in range(len(text) - n + 1)}


def _overlap_ratio(a: Any, b: Any) -> float:
    sa = _char_ngrams(a)
    sb = _char_ngrams(b)
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / float(min(len(sa), len(sb)) or 1)


def _strip_continue_lead_in(question: str) -> str:
    text = _safe_str(question).strip()
    if not text:
        return ""

    prefixes = sorted(_phrases("continue_strip_prefixes"), key=len, reverse=True)

    changed = True
    while changed and text:
        changed = False
        lowered = text.lower()
        for prefix in prefixes:
            p = prefix.lower()
            if lowered.startswith(p):
                text = text[len(prefix):].lstrip("，,。:：;；.!?？! \n\t")
                changed = True
                break

    return _normalize_compare_text(text)


def _strip_resume_test_annotation(value: Any) -> str:
    text = _normalize_compare_text(value)
    if not text:
        return ""

    lowered = text.lower()
    for marker in _phrases("resume_test_markers"):
        idx = lowered.find(marker.lower())
        if idx > 0:
            return text[:idx].strip()
    return text


def _looks_like_explicit_topic(value: Any) -> bool:
    text = _normalize_compare_text(value)
    if not text:
        return False

    if text in _phrase_set("generic_topic_tails"):
        return False

    if _looks_like_contextual_reference(text):
        return False

    compact = _compact_compare_text(text)
    if not compact:
        return False

    if len(compact) <= 1:
        return False

    if any(ch.isdigit() for ch in compact):
        return True

    cjk_count = sum(1 for ch in compact if "\u4e00" <= ch <= "\u9fff")
    latin_count = sum(1 for ch in compact if ch.isascii() and ch.isalpha())

    if cjk_count >= 2:
        return True
    if latin_count >= 2 and len(compact) >= 3:
        return True

    return False


def _extract_explicit_topic_tail(question: str) -> str:
    text = _normalize_compare_text(question)
    if not text:
        return ""

    markers = sorted(_phrases("explicit_topic_markers"), key=len, reverse=True)
    generic_heads = {_normalize_compare_text(item) for item in _contextual_generic_heads()}

    for marker in markers:
        marker_norm = _normalize_compare_text(marker)
        if not marker_norm:
            continue
        idx = text.rfind(marker_norm)
        if idx < 0:
            continue

        tail = _strip_resume_test_annotation(text[idx + len(marker_norm):].strip())
        if not tail:
            continue
        if _looks_like_contextual_reference(tail):
            continue
        if tail in _phrase_set("generic_topic_tails"):
            continue
        if tail in generic_heads:
            continue
        if _looks_like_explicit_topic(tail):
            return tail

    return ""


def _looks_like_topic_narrowing(question: str) -> bool:
    text = _normalize_compare_text(question)
    if not text:
        return False

    compact = _compact_compare_text(text)
    return any(_compact_compare_text(token) in compact for token in _phrases("topic_narrowing"))


def _is_generic_continue_tail(tail: str) -> bool:
    text = _strip_resume_test_annotation(tail)
    text = _normalize_compare_text(text)
    if not text:
        return True

    if _looks_like_contextual_reference(text):
        return False

    generic_phrases = _phrase_set("generic_continue_tails")
    if text in generic_phrases:
        return True

    for prefix in sorted(_phrases("generic_continue_prefixes"), key=len, reverse=True):
        p = _normalize_compare_text(prefix)
        if text.startswith(p):
            rest = text[len(p):].strip()
            if not rest or rest in generic_phrases:
                return True

    compact = _compact_compare_text(text)
    if len(compact) <= 3 and not _looks_like_explicit_topic(text):
        return True

    return False


def _checkpoint_reference_texts(checkpoint: Dict[str, Any]) -> List[str]:
    return [
        _safe_str(checkpoint.get("topic_anchor")),
        _safe_str(checkpoint.get("question")),
        _safe_str(checkpoint.get("summary")),
        _safe_str(checkpoint.get("plan_summary")),
        _safe_str(checkpoint.get("recovery_hint")),
    ]


def _classify_checkpoint_relation(question: str, checkpoint: Dict[str, Any]) -> str:
    query = _normalize_compare_text(question)
    if not query:
        return "unknown"

    refs = [item for item in _checkpoint_reference_texts(checkpoint) if _safe_str(item)]
    if not refs:
        return "unknown"

    for ref in refs:
        ref_text = _normalize_compare_text(ref)
        if not ref_text:
            continue
        if query == ref_text or query in ref_text or ref_text in query:
            return "strong_match"

    best = 0.0
    for ref in refs:
        best = max(best, _overlap_ratio(query, ref))

    if best >= 0.58:
        return "strong_match"
    if best >= 0.34:
        return "weak_related"

    if _looks_like_contextual_reference(query):
        return "unknown"

    if _looks_like_explicit_topic(query) and best < 0.18:
        return "conflict"

    return "unknown"


def _checkpoint_marked_stale(memory_read_result: Dict[str, Any]) -> Tuple[bool, str]:
    row = _safe_dict(memory_read_result)
    resume = _safe_dict(row.get("resume"))
    raw_doc = _safe_dict(row.get("raw_doc"))
    status_value = _safe_str(row.get("status_value") or raw_doc.get("status")).lower()
    invalidated_by = _safe_str(resume.get("invalidated_by"))

    if invalidated_by:
        return True, "checkpoint_invalidated"

    if status_value in {"stale", "invalidated", "superseded", "archived", "obsolete"}:
        return True, "stale_checkpoint"

    return False, ""


def _derive_topic_anchor(
    *,
    checkpoint: Dict[str, Any],
    question: str = "",
    explicit_topic_tail: str = "",
) -> str:
    checkpoint_row = _safe_dict(checkpoint)

    for candidate in [
        checkpoint_row.get("topic_anchor"),
        explicit_topic_tail,
        checkpoint_row.get("question"),
        checkpoint_row.get("summary"),
        checkpoint_row.get("plan_summary"),
        question,
    ]:
        text = _safe_str(candidate)
        if not text:
            continue

        if _looks_like_contextual_reference(text) and candidate in {explicit_topic_tail, question}:
            continue

        if candidate in {checkpoint_row.get("summary"), checkpoint_row.get("plan_summary")}:
            text = _truncate_text(text, 120)

        if _looks_like_explicit_topic(text) or candidate in {
            checkpoint_row.get("topic_anchor"),
            checkpoint_row.get("question"),
        }:
            return _truncate_text(text, 120)

    return ""


def _has_self_contained_new_topic(question: str) -> bool:
    explicit_tail = _extract_explicit_topic_tail(question)
    if not explicit_tail:
        return False
    if _looks_like_contextual_reference(explicit_tail):
        return False
    return _looks_like_explicit_topic(explicit_tail)


def _compact_checkpoint_for_resume_classifier(checkpoint: Dict[str, Any]) -> Dict[str, Any]:
    row = _safe_dict(checkpoint)
    return {
        "stage": _safe_str(row.get("stage")),
        "topic_anchor": _truncate_text(row.get("topic_anchor"), 120),
        "question": _truncate_text(row.get("question"), 180),
        "summary": _truncate_text(row.get("summary"), 280),
        "recovery_hint": _truncate_text(row.get("recovery_hint"), 180),
        "open_questions": [
            _truncate_text(item, 120)
            for item in _safe_list(row.get("open_questions"))
            if _safe_str(item)
        ][:4],
        "next_actions": [
            _truncate_text(item, 120)
            for item in _safe_list(row.get("next_actions"))
            if _safe_str(item)
        ][:4],
    }


def classify_supervisor_memory_resume_context(
    *,
    question: str,
    checkpoint: Dict[str, Any],
    relation: str = "unknown",
    continue_intent: bool = False,
    restart_intent: bool = False,
    followup_without_continue: bool = False,
    generic_continue: bool = False,
) -> Dict[str, Any]:
    current_question = _safe_str(question)
    checkpoint_obj = _safe_dict(checkpoint)
    normalized_relation = _safe_str(relation, "unknown") or "unknown"
    context_dependent = _looks_like_context_dependent_task(current_question)
    self_contained_new_topic = _has_self_contained_new_topic(current_question)

    if restart_intent:
        decision, reason, confidence = "restart_fresh", "explicit_restart_intent", 0.98
    elif continue_intent and generic_continue:
        decision, reason, confidence = "continue_from_checkpoint", "checkpoint_ready", 0.95
    elif continue_intent and normalized_relation == "strong_match":
        decision, reason, confidence = "continue_from_checkpoint", "checkpoint_context_match", 0.94
    elif continue_intent and (context_dependent or followup_without_continue):
        decision, reason, confidence = "continue_from_checkpoint", "checkpoint_contextual_followup", 0.88
    elif continue_intent and normalized_relation == "weak_related" and _looks_like_topic_narrowing(current_question):
        decision, reason, confidence = "continue_from_checkpoint", "checkpoint_subtopic_followup", 0.82
    elif continue_intent and normalized_relation == "weak_related":
        decision, reason, confidence = "ignore_stale_checkpoint", "checkpoint_context_ambiguous", 0.62
    elif continue_intent and normalized_relation == "conflict" and self_contained_new_topic:
        decision, reason, confidence = "restart_fresh", "user_intent_conflicts", 0.86
    elif continue_intent and _looks_like_topic_narrowing(current_question):
        decision, reason, confidence = "continue_from_checkpoint", "checkpoint_subtopic_followup", 0.76
    elif continue_intent:
        decision, reason, confidence = "continue_from_checkpoint", "explicit_continue_intent", 0.68
    elif (followup_without_continue or context_dependent) and normalized_relation in {"strong_match", "weak_related", "unknown"}:
        decision, reason, confidence = "continue_from_checkpoint", "implicit_contextual_followup", 0.74 if normalized_relation != "unknown" else 0.66
    elif normalized_relation == "strong_match":
        decision, reason, confidence = "ignore_stale_checkpoint", "no_explicit_continue_intent", 0.64
    elif normalized_relation == "weak_related":
        decision, reason, confidence = "ignore_stale_checkpoint", "related_but_not_same_task", 0.62
    elif normalized_relation == "conflict" or self_contained_new_topic:
        decision, reason, confidence = "restart_fresh", "new_topic_detected", 0.86
    else:
        decision, reason, confidence = "restart_fresh", "no_continue_intent", 0.72

    return {
        "decision": decision,
        "reason": reason,
        "confidence": confidence,
        "relation": normalized_relation,
        "context_dependent": context_dependent,
        "self_contained_new_topic": self_contained_new_topic,
        "checkpoint": _compact_checkpoint_for_resume_classifier(checkpoint_obj),
    }


def _remove_contextual_references_for_task(text: str) -> str:
    out = _safe_str(text)
    if not out:
        return ""

    markers = list(_contextual_reference_markers()) + list(_contextual_generic_heads())
    for marker in sorted(markers, key=len, reverse=True):
        if not marker:
            continue
        out = re.sub(re.escape(marker), " ", out, flags=re.IGNORECASE)

    for prefix in sorted(_phrases("generic_continue_prefixes"), key=len, reverse=True):
        if not prefix:
            continue
        pattern = r"^\s*" + re.escape(prefix) + r"\s*"
        out = re.sub(pattern, " ", out, flags=re.IGNORECASE)

    out = out.replace("的", " ")
    out = re.sub(r"\b(the|this|that|these|those|its|their|same)\b", " ", out, flags=re.IGNORECASE)
    out = " ".join(out.split())
    return out.strip("，,。:：;；.!?？! \n\t")


def sanitize_provider_standalone_query(value: Any, max_chars: int = 160) -> str:
    text = _safe_str(value)
    if not text:
        return ""

    text = " ".join(text.replace("\n", " ").replace("\r", " ").split())
    lowered = text.lower()

    if any(marker in lowered for marker in _INTERNAL_LEAK_MARKERS):
        return ""

    if text.startswith("{") or text.startswith("["):
        return ""

    return _truncate_text(text, max_chars).strip("，,。:：;；.!?？! \n\t")


def build_worker_standalone_task_from_memory(
    *,
    question: str,
    worker_memory_context: Dict[str, Any],
    for_provider: bool = False,
    max_chars: int = 160,
) -> Dict[str, Any]:
    base_question = _safe_str(question)
    ctx = _safe_dict(worker_memory_context)

    if not base_question:
        return {
            "task": "",
            "query": "",
            "resolved": False,
            "reason": "empty_question",
        }

    if not bool(ctx.get("used")):
        safe_base = sanitize_provider_standalone_query(base_question, max_chars) if for_provider else _truncate_text(base_question, max_chars)
        return {
            "task": safe_base,
            "query": safe_base,
            "resolved": False,
            "reason": "memory_context_not_available",
        }

    topic_anchor = _safe_str(ctx.get("topic_anchor"))
    if not topic_anchor:
        safe_base = sanitize_provider_standalone_query(base_question, max_chars) if for_provider else _truncate_text(base_question, max_chars)
        return {
            "task": safe_base,
            "query": safe_base,
            "resolved": False,
            "reason": "missing_topic_anchor",
        }

    stripped = _strip_resume_test_annotation(_strip_continue_lead_in(base_question))
    focus = _remove_contextual_references_for_task(stripped or base_question)
    focus = sanitize_provider_standalone_query(focus, max_chars=100)

    if not focus:
        focus = sanitize_provider_standalone_query(base_question, max_chars=100)

    topic = sanitize_provider_standalone_query(topic_anchor, max_chars=100)
    if not topic:
        safe_base = sanitize_provider_standalone_query(base_question, max_chars) if for_provider else _truncate_text(base_question, max_chars)
        return {
            "task": safe_base,
            "query": safe_base,
            "resolved": False,
            "reason": "unsafe_topic_anchor",
        }

    focus_compact = _compact_compare_text(focus)
    topic_compact = _compact_compare_text(topic)

    if focus and topic_compact and topic_compact not in focus_compact:
        resolved = f"{topic} {focus}".strip()
    else:
        resolved = focus or topic

    resolved = sanitize_provider_standalone_query(resolved, max_chars=max_chars)
    if not resolved:
        safe_base = sanitize_provider_standalone_query(base_question, max_chars) if for_provider else _truncate_text(base_question, max_chars)
        return {
            "task": safe_base,
            "query": safe_base,
            "resolved": False,
            "reason": "standalone_task_unsafe",
        }

    return {
        "task": resolved,
        "query": resolved,
        "resolved": resolved != base_question,
        "reason": "standalone_task_resolved" if resolved != base_question else "standalone_task_unchanged",
    }


def build_worker_supervisor_memory_context(
    *,
    room_id: str,
    question: str,
    mcp: Dict[str, Any],
    max_summary_chars: int = 260,
    max_hint_chars: int = 220,
    max_item_chars: int = 120,
    max_items: int = 4,
) -> Dict[str, Any]:
    try:
        from ..room_contracts import as_bool
        from .memory_resume_decision import decide_supervisor_memory_resume
        from .memory_resume_paths import load_supervisor_memory_sidecar

        mcp_obj = _safe_dict(mcp)
        if as_bool(mcp_obj.get("worker_memory_read_disabled"), False) or as_bool(mcp_obj.get("supervisor_memory_read_disabled"), False):
            return {
                "enabled": False,
                "used": False,
                "decision": "none",
                "reason": "worker_memory_read_disabled",
                "relative_path": "",
                "source_kind": "",
                "topic_anchor": "",
                "last_question": "",
                "recent_summary": "",
                "recovery_hint": "",
                "next_actions": [],
                "open_questions": [],
                "context_text": "",
            }

        memory_read_result = load_supervisor_memory_sidecar(room_id=room_id, mcp=mcp_obj)
        memory_resume_result = decide_supervisor_memory_resume(
            question=question,
            memory_read_result=memory_read_result,
        )

        decision = _safe_str(memory_resume_result.get("decision"), "none")
        reason = _safe_str(memory_resume_result.get("reason"))
        checkpoint = _safe_dict(memory_read_result.get("checkpoint"))

        if decision != "continue_from_checkpoint":
            return {
                "enabled": True,
                "used": False,
                "decision": decision,
                "reason": reason,
                "relative_path": _safe_str(memory_resume_result.get("relative_path") or memory_read_result.get("relative_path")),
                "source_kind": _safe_str(memory_read_result.get("source_kind")),
                "topic_anchor": "",
                "last_question": "",
                "recent_summary": "",
                "recovery_hint": "",
                "next_actions": [],
                "open_questions": [],
                "context_text": "",
                "resume_confidence": memory_resume_result.get("confidence"),
                "resume_relation": _safe_str(memory_resume_result.get("relation")),
                "resume_context_dependent": bool(memory_resume_result.get("context_dependent")),
            }

        topic_anchor = _safe_str(memory_resume_result.get("topic_anchor") or checkpoint.get("topic_anchor"))
        last_question = _safe_str(memory_resume_result.get("checkpoint_question") or checkpoint.get("question"))
        recent_summary = _truncate_text(
            memory_resume_result.get("checkpoint_summary") or checkpoint.get("summary"),
            max_summary_chars,
        )
        recovery_hint = _truncate_text(
            memory_resume_result.get("recovery_hint") or checkpoint.get("recovery_hint"),
            max_hint_chars,
        )
        next_actions = [
            _truncate_text(item, max_item_chars)
            for item in _safe_list(checkpoint.get("next_actions"))
            if _safe_str(item)
        ][:max_items]
        open_questions = [
            _truncate_text(item, max_item_chars)
            for item in _safe_list(checkpoint.get("open_questions"))
            if _safe_str(item)
        ][:max_items]

        lines: List[str] = [
            "Room side memory, read-only:",
            "Use this only to understand continuity. Do not treat it as a new user task.",
        ]
        if topic_anchor:
            lines.append(f"Topic anchor: {topic_anchor}")
        if last_question:
            lines.append(f"Last question: {_truncate_text(last_question, 120)}")
        if recent_summary:
            lines.append(f"Recent summary: {recent_summary}")
        if recovery_hint:
            lines.append(f"Recovery hint: {recovery_hint}")
        if next_actions:
            lines.append("Next actions:")
            for item in next_actions:
                lines.append(f"- {item}")
        if open_questions:
            lines.append("Open questions:")
            for item in open_questions:
                lines.append(f"- {item}")

        return {
            "enabled": True,
            "used": True,
            "decision": decision,
            "reason": reason or "checkpoint_ready",
            "relative_path": _safe_str(memory_resume_result.get("relative_path") or memory_read_result.get("relative_path")),
            "source_kind": _safe_str(memory_read_result.get("source_kind")),
            "topic_anchor": topic_anchor,
            "last_question": last_question,
            "recent_summary": recent_summary,
            "recovery_hint": recovery_hint,
            "next_actions": next_actions,
            "open_questions": open_questions,
            "context_text": "\n".join(lines).strip(),
            "resume_confidence": memory_resume_result.get("confidence"),
            "resume_relation": _safe_str(memory_resume_result.get("relation")),
            "resume_context_dependent": bool(memory_resume_result.get("context_dependent")),
        }
    except Exception as ex:
        return {
            "enabled": True,
            "used": False,
            "decision": "none",
            "reason": f"worker_memory_context_error:{type(ex).__name__}",
            "relative_path": "",
            "source_kind": "",
            "topic_anchor": "",
            "last_question": "",
            "recent_summary": "",
            "recovery_hint": "",
            "next_actions": [],
            "open_questions": [],
            "context_text": "",
        }


__all__ = [
    "_char_ngrams",
    "_checkpoint_marked_stale",
    "_checkpoint_reference_texts",
    "_classify_checkpoint_relation",
    "_compact_checkpoint_for_resume_classifier",
    "_compact_compare_text",
    "_contains_phrase",
    "_derive_topic_anchor",
    "_extract_explicit_topic_tail",
    "_is_generic_continue_tail",
    "_looks_like_continue_intent",
    "_looks_like_context_dependent_task",
    "_looks_like_contextual_reference",
    "_looks_like_explicit_topic",
    "_looks_like_followup_without_continue",
    "_looks_like_restart_intent",
    "_looks_like_topic_narrowing",
    "_normalize_compare_text",
    "_overlap_ratio",
    "_remove_contextual_references_for_task",
    "_strip_continue_lead_in",
    "_strip_resume_test_annotation",
    "build_worker_standalone_task_from_memory",
    "build_worker_supervisor_memory_context",
    "classify_supervisor_memory_resume_context",
    "sanitize_provider_standalone_query",
]
