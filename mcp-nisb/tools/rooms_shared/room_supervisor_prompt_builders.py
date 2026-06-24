from __future__ import annotations

from typing import Any, Dict, List, Optional


try:
    from tools.lang.answer_language import language_name, resolve_answer_lang
except Exception:
    language_name = None
    resolve_answer_lang = None


from .room_contracts import utc_iso
from .room_supervisor_builtin_skills import get_builtin_supervisor_skill_text


def _safe_str(v: Any, default: str = "") -> str:
    if v is None:
        return default
    s = str(v).strip()
    return s if s else default


def _safe_dict(v: Any) -> Dict[str, Any]:
    return v if isinstance(v, dict) else {}


def _safe_list(v: Any) -> List[Any]:
    return v if isinstance(v, list) else []


def _build_answer_language_instruction_for_current_question(
    question: str,
    request_args: Optional[Dict[str, Any]] = None,
) -> str:
    q = _safe_str(question)
    args = _safe_dict(request_args)

    resolved_lang = _safe_str(args.get("_answer_lang"))
    resolved_name = _safe_str(args.get("_answer_lang_name"))

    if not resolved_lang and callable(resolve_answer_lang):
        try:
            resolved_lang, _dbg = resolve_answer_lang(
                question=q,
                args={},
                default_lang="en",
            )
        except Exception:
            resolved_lang = ""

    if not resolved_name and resolved_lang and callable(language_name):
        try:
            resolved_name = _safe_str(language_name(resolved_lang))
        except Exception:
            resolved_name = ""

    if not resolved_name:
        resolved_name = "English"

    return (
        f"Answer in {resolved_name}. "
        "Keep source titles, URLs, code, tool names, and protocol fields unchanged."
    )


def _normalize_supervisor_skill_strategy(value: Any, fallback: str = "builtin_plus_custom") -> str:
    raw = _safe_str(value).strip().lower()
    if raw in {"builtin_plus_custom", "custom_only", "builtin_only"}:
        return raw
    if raw in {"builtin+custom", "default", "all"}:
        return "builtin_plus_custom"
    if raw == "custom":
        return "custom_only"
    if raw == "builtin":
        return "builtin_only"

    fb = _safe_str(fallback).strip().lower()
    if fb in {"builtin_plus_custom", "custom_only", "builtin_only"}:
        return fb
    return "builtin_plus_custom"


def get_builtin_supervisor_skill_ids_for_prompt(
    prompt_kind: str,
    supervisor_skill_strategy: Any = "builtin_plus_custom",
) -> List[str]:
    strategy = _normalize_supervisor_skill_strategy(
        supervisor_skill_strategy,
        "builtin_plus_custom",
    )
    if strategy == "custom_only":
        return []

    kind = _safe_str(prompt_kind).lower()
    mapping = {
        "direct": ["supervisor_direct_default"],
        "synthesis": ["supervisor_orchestration_default"],
        "repair": ["supervisor_repair_default"],
    }

    out: List[str] = []
    for skill_id in mapping.get(kind, []):
        if _safe_str(get_builtin_supervisor_skill_text(skill_id)):
            out.append(skill_id)
    return out


def _get_builtin_supervisor_skill_text_for_prompt(
    prompt_kind: str,
    supervisor_skill_strategy: Any = "builtin_plus_custom",
) -> str:
    blocks: List[str] = []
    for skill_id in get_builtin_supervisor_skill_ids_for_prompt(
        prompt_kind,
        supervisor_skill_strategy,
    ):
        text = _safe_str(get_builtin_supervisor_skill_text(skill_id))
        if text:
            blocks.append(text)
    return "\n\n".join(blocks).strip()


def _normalize_rel_path(value: Any) -> str:
    raw = _safe_str(value).replace("\\\\", "/")
    while "//" in raw:
        raw = raw.replace("//", "/")
    raw = raw.strip("/")
    if not raw:
        return ""
    parts = [p.strip() for p in raw.split("/") if p and p not in {".", ".."}]
    return "/".join(parts)


def _truncate_text(value: Any, limit: int = 1200) -> str:
    text = _safe_str(value)
    if limit <= 0 or len(text) <= limit:
        return text
    return text[:limit].rstrip() + "…"


def _clean_multiline_text(value: Any) -> str:
    text = _safe_str(value).replace("\r", "\n")
    lines = [line.strip() for line in text.split("\n") if line.strip()]
    return "\n".join(lines).strip()


def _extract_prompt_ready_role_content(value: Any, limit: int = 1800) -> str:
    text = _safe_str(value).replace("\r", "\n")
    lines: List[str] = []

    for raw_line in text.split("\n"):
        line = raw_line.strip()
        if not line:
            continue

        lowered = line.lower()
        if lowered.startswith("evidence_query:"):
            continue
        if lowered.startswith("citations_count:"):
            continue
        if lowered.startswith("tool_activity:"):
            continue
        if lowered.startswith("tool_calls_count:"):
            continue
        if lowered.startswith("tool_results_count:"):
            continue
        if lowered.startswith("evidence_tools_count:"):
            continue

        lines.append(line)

    merged = "\n".join(lines).strip()
    return _truncate_text(merged, limit)


def _looks_like_heading_line(text: Any) -> bool:
    value = _safe_str(text)
    if not value:
        return False

    if value.startswith("#"):
        return True
    if len(value) <= 28 and value.endswith("："):
        return True

    numerals = "一二三四五六七八九十"
    if len(value) >= 2 and value[0] in numerals and value[1] in {"、", "."}:
        return True

    if value[0].isdigit():
        if len(value) >= 2 and value[1] in {"、", "."} and len(value) <= 28:
            return True

    return False


def _split_natural_sentences(value: Any, limit: int = 12) -> List[str]:
    text = _safe_str(value).replace("\r", "\n")
    if not text:
        return []

    out: List[str] = []

    for raw_line in text.split("\n"):
        line = raw_line.strip()
        if not line:
            continue

        if _looks_like_heading_line(line):
            out.append(line)
            if len(out) >= limit:
                return out[:limit]
            continue

        current = ""
        for ch in line:
            current += ch
            if ch in "。！？；!?;":
                piece = current.strip()
                if piece:
                    out.append(piece)
                current = ""
                if len(out) >= limit:
                    return out[:limit]

        tail = current.strip()
        if tail:
            out.append(tail)
            if len(out) >= limit:
                return out[:limit]

    return out[:limit]


def _build_delegate_novelty_block(delegate_packets: List[Dict[str, Any]]) -> str:
    rows: List[str] = []

    for item in _safe_list(delegate_packets)[:6]:
        row = _safe_dict(item)
        role_name = _safe_str(row.get("role_name"), "role")

        points: List[str] = []
        for point in _safe_list(row.get("primary_points"))[:2]:
            point_text = _safe_str(point)
            if point_text:
                points.append(_truncate_text(point_text, 160))

        if not points:
            content = _safe_str(row.get("content") or row.get("source_excerpt"))
            for sentence in _split_natural_sentences(content, limit=2):
                if sentence and not _looks_like_heading_line(sentence):
                    points.append(_truncate_text(sentence, 160))

        if not points:
            continue

        merged = " ; ".join(points[:2])
        rows.append(f"- {role_name}: {merged}")

    return "\n".join(rows).strip()


def _build_supervisor_plan_summary(
    *,
    question: str,
    active_roles: List[Dict[str, Any]],
    fs_context: Dict[str, Any],
) -> str:
    role_names = [str(r.get("name") or r.get("slug") or r.get("role_id") or "role") for r in active_roles]
    role_names = [x for x in role_names if x]
    role_text = ", ".join(role_names) if role_names else "no active roles"

    fs_status = _safe_str(fs_context.get("status"))
    focus_root = _safe_str(fs_context.get("focus_root"))
    scope = _safe_str(fs_context.get("scope"))

    lines: List[str] = []
    lines.append(f"User question: {question}")
    if fs_status == "success" and focus_root:
        lines.append(f"Read focus_root={focus_root} first to obtain directory context. scope={scope}.")
    elif fs_status in {"denied", "error"} and focus_root:
        lines.append(f"Attempted to read focus_root={focus_root}, but it failed. Continue with conversation and role context only.")
    else:
        lines.append("No extra directory read is used in this round.")
    lines.append(f"Delegate to these roles in order: {role_text}.")
    lines.append("Supervisor will synthesize the role results into one final answer.")
    return "\n".join(lines).strip()


def _build_supervisor_direct_plan_summary(
    *,
    question: str,
    fs_context: Dict[str, Any],
) -> str:
    fs_status = _safe_str(fs_context.get("status"))
    focus_root = _safe_str(fs_context.get("focus_root"))
    scope = _safe_str(fs_context.get("scope"))

    lines: List[str] = []
    lines.append(f"User question: {question}")
    if fs_status == "success" and focus_root:
        lines.append(f"Read focus_root={focus_root} first to obtain directory context. scope={scope}.")
    elif fs_status in {"denied", "error"} and focus_root:
        lines.append(f"Attempted to read focus_root={focus_root}, but it failed. Answer directly with conversation context only.")
    else:
        lines.append("No extra directory read is used in this round.")
    lines.append("No role delegation is used in this round. Supervisor answers directly.")
    return "\n".join(lines).strip()


def _build_role_question(
    *,
    room_id: str,
    question: str,
    role: Dict[str, Any],
    request_args: Dict[str, Any],
    room_state: Dict[str, Any],
) -> str:
    state = _safe_dict(room_state)
    room_summary = _safe_str(state.get("summary"))
    room_scratchpad = _safe_str(state.get("scratchpad"))
    focus_root = _normalize_rel_path(state.get("focus_root"))

    role_name = _safe_str(role.get("name") or role.get("slug") or role.get("role_id"), "role")
    role_prompt = _safe_str(role.get("system_prompt"))
    fs_context_text = _safe_str(request_args.get("_supervisor_fs_read_text"))

    lines: List[str] = []
    lines.append(f"You are acting as this room role: {role_name}")
    if role_prompt:
        lines.append("")
        lines.append("Role instructions:")
        lines.append(role_prompt)

    if room_summary:
        lines.append("")
        lines.append("Room summary:")
        lines.append(room_summary)

    if room_scratchpad:
        lines.append("")
        lines.append("Room scratchpad:")
        lines.append(room_scratchpad)

    if focus_root:
        lines.append("")
        lines.append(f"Current room focus_root: {focus_root}")

    if fs_context_text:
        lines.append("")
        lines.append("Read-only directory context provided by Supervisor:")
        lines.append(fs_context_text)

    language_instruction = _build_answer_language_instruction_for_current_question(
        question,
        request_args=request_args,
    )
    if language_instruction:
        lines.append("")
        lines.append("Answer language instruction:")
        lines.append(language_instruction)

    lines.append("")
    lines.append("Answer the user question using the context above. If information is insufficient, state assumptions clearly and do not invent file contents.")
    lines.append("Provide role-specific judgment, evidence, risks, and recommendations instead of only repeating the user question.")
    lines.append("")
    lines.append("User question:")
    lines.append(question)

    return "\n".join(lines).strip()


def _build_supervisor_synthesis_prompt(
    *,
    question: str,
    plan_summary: str,
    fs_context: Dict[str, Any],
    delegate_packets: List[Dict[str, Any]],
    supervisor_skill_strategy: str = "builtin_plus_custom",
    request_args: Optional[Dict[str, Any]] = None,
) -> str:
    lines: List[str] = []

    builtin_skill = _get_builtin_supervisor_skill_text_for_prompt(
        "synthesis",
        supervisor_skill_strategy,
    )
    if builtin_skill:
        lines.append(builtin_skill)

    language_instruction = _build_answer_language_instruction_for_current_question(
        question,
        request_args=request_args,
    )
    if language_instruction:
        lines.append("")
        lines.append("Answer language instruction:")
        lines.append(language_instruction)

    lines.append("")
    lines.append("User question:")
    lines.append(question)

    lines.append("")
    lines.append("Plan summary:")
    lines.append(plan_summary)

    if _safe_str(fs_context.get("text")):
        lines.append("")
        lines.append("Read-only directory context:")
        lines.append(_safe_str(fs_context.get("text")))

    if delegate_packets:
        lines.append("")
        lines.append("Role replies:")
        for item in delegate_packets:
            role_name = _safe_str(item.get("role_name"), "role")
            content = _safe_str(item.get("content"))
            lines.append(f"## {role_name}")
            lines.append(content or "(empty)")
            lines.append("")

    lines.append("Output only the final answer body.")
    return "\n".join(lines).strip()


def _build_supervisor_repair_prompt(
    *,
    question: str,
    draft_answer: str,
    plan_summary: str,
    fs_context: Dict[str, Any],
    delegate_packets: List[Dict[str, Any]],
    supervisor_skill_strategy: str = "builtin_plus_custom",
    request_args: Optional[Dict[str, Any]] = None,
) -> str:
    base_prompt = _build_supervisor_synthesis_prompt(
        question=question,
        plan_summary=plan_summary,
        fs_context=fs_context,
        delegate_packets=delegate_packets,
        supervisor_skill_strategy=supervisor_skill_strategy,
        request_args=request_args,
    )
    novelty_block = _build_delegate_novelty_block(delegate_packets)

    lines: List[str] = []

    builtin_skill = _get_builtin_supervisor_skill_text_for_prompt(
        "repair",
        supervisor_skill_strategy,
    )
    if builtin_skill:
        lines.append(builtin_skill)

    language_instruction = _build_answer_language_instruction_for_current_question(
        question,
        request_args=request_args,
    )
    if language_instruction:
        lines.append("")
        lines.append("Answer language instruction:")
        lines.append(language_instruction)

    if novelty_block:
        lines.append("")
        lines.append("Role-specific points to preserve in this round:")
        lines.append(novelty_block)

    lines.append("")
    lines.append("Draft answer to repair:")
    lines.append(_clean_multiline_text(draft_answer) or "(empty)")
    lines.append("")
    lines.append("Original synthesis task material:")
    lines.append(base_prompt)

    return "\n".join(lines).strip()


def _build_supervisor_continuation_block(continuation_context: Any) -> str:
    row = _safe_dict(continuation_context)
    if not row:
        return ""

    enabled = row.get("enabled")
    if enabled is False:
        return ""

    decision = _safe_str(row.get("decision"))
    reason = _safe_str(row.get("reason"))
    topic_anchor = _safe_str(row.get("topic_anchor"))
    checkpoint_question = _safe_str(row.get("checkpoint_question"))
    checkpoint_summary = _safe_str(row.get("checkpoint_summary"))

    if not any([decision, reason, topic_anchor, checkpoint_question, checkpoint_summary]):
        return ""

    lines: List[str] = []
    lines.append("Continuation context:")
    lines.append(f"- decision: {decision or 'unknown'}")
    lines.append(f"- reason: {reason or 'unknown'}")
    lines.append(f"- topic_anchor: {topic_anchor or '—'}")
    lines.append(f"- checkpoint_question: {checkpoint_question or '—'}")
    lines.append(f"- checkpoint_summary: {checkpoint_summary or '—'}")
    lines.append(
        "If the user uses ellipsis, pronouns, or continuation phrases, interpret them through topic_anchor unless the user clearly switches topics."
    )
    return "\n".join(lines).strip()


def _build_supervisor_direct_answer_prompt(
    *,
    question: str,
    room_state: Dict[str, Any],
    fs_context: Dict[str, Any],
    supervisor_skill_strategy: str = "builtin_plus_custom",
    memory_read_result: Dict[str, Any] = None,
    memory_resume_result: Dict[str, Any] = None,
    continuation_context: Dict[str, Any] = None,
    request_args: Optional[Dict[str, Any]] = None,
) -> str:
    state = _safe_dict(room_state)
    room_summary = _safe_str(state.get("summary"))
    room_scratchpad = _safe_str(state.get("scratchpad"))
    focus_root = _normalize_rel_path(state.get("focus_root"))
    fs_text = _safe_str(fs_context.get("text"))
    fs_status = _safe_str(fs_context.get("status"))
    fs_reason = _safe_str(fs_context.get("reason"))

    continuation_row = _safe_dict(continuation_context)
    if not continuation_row:
        memory_resume_row = _safe_dict(memory_resume_result)
        memory_read_row = _safe_dict(memory_read_result)
        checkpoint = _safe_dict(memory_read_row.get("checkpoint"))
        continuation_row = {
            "enabled": _safe_str(memory_resume_row.get("decision")) in {
                "continue_from_checkpoint",
                "resume_from_checkpoint",
                "continue",
                "resume",
            },
            "decision": _safe_str(memory_resume_row.get("decision")),
            "reason": _safe_str(memory_resume_row.get("reason")),
            "checkpoint_question": _safe_str(
                memory_resume_row.get("checkpoint_question") or checkpoint.get("question")
            ),
            "checkpoint_summary": _safe_str(
                memory_resume_row.get("checkpoint_summary") or checkpoint.get("summary")
            ),
            "topic_anchor": _safe_str(
                memory_resume_row.get("topic_anchor") or checkpoint.get("topic_anchor")
            ),
        }

    lines: List[str] = []

    builtin_skill = _get_builtin_supervisor_skill_text_for_prompt(
        "direct",
        supervisor_skill_strategy,
    )
    if builtin_skill:
        lines.append(builtin_skill)

    language_instruction = _build_answer_language_instruction_for_current_question(
        question,
        request_args=request_args,
    )
    if language_instruction:
        lines.append("")
        lines.append("Answer language instruction:")
        lines.append(language_instruction)

    if room_summary:
        lines.append("")
        lines.append("Room summary:")
        lines.append(room_summary)

    if room_scratchpad:
        lines.append("")
        lines.append("Room scratchpad:")
        lines.append(room_scratchpad)

    if focus_root:
        lines.append("")
        lines.append(f"Current room focus_root: {focus_root}")

    if fs_status:
        lines.append("")
        lines.append("Read-only directory context status:")
        lines.append(f"- status: {fs_status}")
        lines.append(f"- reason: {fs_reason or '—'}")
        lines.append(f"- focus_root: {focus_root or '—'}")

    if fs_text:
        lines.append("")
        lines.append("Read-only directory context:")
        lines.append(fs_text)

    continuation_block = _build_supervisor_continuation_block(continuation_row)
    if continuation_block:
        lines.append("")
        lines.append(continuation_block)

    lines.append("")
    lines.append("User question:")
    lines.append(question)

    return "\n".join(lines).strip()


def _build_supervisor_notebook_block(
    *,
    notebook_title: str,
    notebook_section_title: str,
    question: str,
    plan_summary: str,
    fs_context: Dict[str, Any],
    delegate_packets: List[Dict[str, Any]],
    final_text: str,
) -> str:
    ts = utc_iso()
    lines: List[str] = []

    lines.append(f"# {notebook_title}")
    lines.append("")
    lines.append(f"## {notebook_section_title} - {ts}")
    lines.append("")
    lines.append("### User question")
    lines.append(question)
    lines.append("")
    lines.append("### Plan")
    lines.append(plan_summary)
    lines.append("")

    fs_status = _safe_str(fs_context.get("status"))
    if fs_status:
        lines.append("### FS audit")
        lines.append(f"- status: {fs_status}")
        lines.append(f"- reason: {_safe_str(fs_context.get('reason')) or '—'}")
        lines.append(f"- focus_root: {_safe_str(fs_context.get('focus_root')) or '—'}")
        lines.append(f"- scope: {_safe_str(fs_context.get('scope')) or 'minimal'}")
        lines.append("")

    if delegate_packets:
        lines.append("### Role summaries")
        for item in delegate_packets:
            row = _safe_dict(item)
            role_name = _safe_str(row.get("role_name"), "role")
            content = _safe_str(row.get("content"))
            brief = content[:1200].rstrip()
            if len(content) > 1200:
                brief += "\n...[truncated]"
            lines.append(f"#### {role_name}")
            lines.append(brief or "(empty)")

            primary_points = _safe_list(row.get("primary_points"))
            if primary_points:
                lines.append("")
                lines.append("Key points:")
                for point in primary_points[:3]:
                    lines.append(f"- {_safe_str(point)}")
            lines.append("")

    lines.append("### Final answer")
    lines.append(final_text)
    lines.append("")
    lines.append("---")
    lines.append("")
    return "\n".join(lines)


__all__ = [
    "get_builtin_supervisor_skill_ids_for_prompt",
    "_build_answer_language_instruction_for_current_question",
    "_build_role_question",
    "_build_supervisor_direct_answer_prompt",
    "_build_supervisor_direct_plan_summary",
    "_build_supervisor_notebook_block",
    "_build_supervisor_plan_summary",
    "_build_supervisor_repair_prompt",
    "_build_supervisor_synthesis_prompt",
]
