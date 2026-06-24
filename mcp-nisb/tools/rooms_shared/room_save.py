from __future__ import annotations

import re
from typing import Any, Dict, List, Tuple

from .room_contracts import (
    ensure_request_id,
    new_id,
    require_safe_id,
    utc_iso,
)
from .room_store import (
    append_room_event,
    ensure_room_exists,
    get_basepath,
    is_participant,
    load_state_doc,
    save_state_doc,
    touch_room_updated_at,
    uid_from_ctx_or_basepath,
)
from .room_helpers import (
    MissingLLMDependencyError,
    _build_dialog_lines,
    _call_llm_json,
)
from tools.workspace.agent_tools import (
    nisb_workspace_snapshot_get,
    nisb_workspace_write_entry,
)


def _ok(**kwargs) -> Dict[str, Any]:
    data = {"success": True, "status": "success"}
    data.update(kwargs)
    return data


def _err(message: str, **kwargs) -> Dict[str, Any]:
    data = {"success": False, "status": "error", "message": str(message or "").strip() or "error"}
    data.update(kwargs)
    return data


def _safe_str(v: Any, default: str = "") -> str:
    if v is None:
        return default
    return str(v).strip()


def _normalize_text(v: Any) -> str:
    return str(v or "").replace("\r\n", "\n").strip()


def _normalize_rel_path(path: Any) -> str:
    s = str(path or "").strip().replace("\\", "/")
    while s.startswith("/"):
        s = s[1:]
    s = re.sub(r"/+", "/", s)
    if not s or s in {".", "./"}:
        return ""
    parts = [p for p in s.split("/") if p]
    if any(p in {".", ".."} for p in parts):
        return ""
    return "/".join(parts)


def _safe_token(value: Any, fallback: str = "room") -> str:
    s = re.sub(r"[^A-Za-z0-9_-]+", "_", str(value or "").strip()).strip("_")
    return s or fallback


def _safe_agent_id(value: Any, fallback: str = "agent") -> str:
    s = _safe_token(value, fallback=fallback)
    try:
        return require_safe_id("agent_id", s)
    except Exception:
        return fallback


def _has_any(text: str, patterns: List[str], flags: int = re.I) -> bool:
    for pattern in patterns:
        if re.search(pattern, text, flags):
            return True
    return False


def _sanitize_target_kind(value: Any, default: str = "") -> str:
    s = str(value or "").strip().lower()
    if s in {"file", "room_note", "agent_notebook"}:
        return s
    return default


def _sanitize_mode(value: Any, default: str = "append") -> str:
    s = str(value or "").strip().lower()
    if s in {"append", "overwrite"}:
        return s
    return default


def _sanitize_content_source(value: Any, default: str = "mixed") -> str:
    s = str(value or "").strip().lower()
    if s in {"inline", "summary", "scratchpad", "last_plan", "recent_dialog", "mixed"}:
        return s
    return default


def _tool_success(result: Dict[str, Any]) -> bool:
    if not isinstance(result, dict):
        return False
    if result.get("success") is False:
        return False
    status = str(result.get("status") or "").strip().lower()
    if status and status != "success":
        return False
    return True


def _get_last_workspace_save(state: Dict[str, Any]) -> Dict[str, Any]:
    row = state.get("last_workspace_save")
    return row if isinstance(row, dict) else {}


def _extract_explicit_path(text: str) -> str:
    raw = _normalize_text(text)
    if not raw:
        return ""

    quoted_patterns = [
        r"`([^`\n]+\.(?:md|markdown|txt|json|jsonl))`",
        r'"([^"\n]+\.(?:md|markdown|txt|json|jsonl))"',
        r"'([^'\n]+\.(?:md|markdown|txt|json|jsonl))'",
        r"“([^”\n]+\.(?:md|markdown|txt|json|jsonl))”",
        r"‘([^’\n]+\.(?:md|markdown|txt|json|jsonl))’",
    ]
    for pattern in quoted_patterns:
        m = re.search(pattern, raw, re.I)
        if m:
            p = _normalize_rel_path(m.group(1))
            if p:
                return p

    bare_patterns = [
        r"((?:[\u4e00-\u9fffA-Za-z0-9_.-]+/)+[\u4e00-\u9fffA-Za-z0-9_.-]+\.(?:md|markdown|txt|json|jsonl))",
        r"\b([\u4e00-\u9fffA-Za-z0-9_.-]+\.(?:md|markdown|txt|json|jsonl))\b",
    ]
    for pattern in bare_patterns:
        m = re.search(pattern, raw, re.I)
        if m:
            p = _normalize_rel_path(m.group(1))
            if p:
                return p

    return ""


def _looks_like_read_or_analysis_intent(text: str) -> bool:
    raw = _normalize_text(text)
    if not raw:
        return False

    explicit_save_patterns = [
        r"帮我记下来",
        r"帮我记一下",
        r"记下刚才",
        r"保存这轮",
        r"保存一下",
        r"整理成纪要",
        r"整理成笔记",
        r"写进小本本",
        r"写到小本本",
        r"追加到刚才那个",
        r"记录到",
        r"记录进",
        r"写入",
        r"写到",
        r"写进",
        r"存到",
        r"存下",
        r"\bsave\b",
        r"\bappend\b",
        r"\bstore\b",
        r"\barchive\b",
        r"\bwrite down\b",
    ]
    if _has_any(raw, explicit_save_patterns):
        return False

    negative_save_patterns = [
        r"不要保存",
        r"别保存",
        r"禁止保存",
        r"无需保存",
        r"不是保存指令",
        r"仅执行读取",
        r"只读",
        r"do not save",
        r"don't save",
        r"not save",
        r"without saving",
        r"read only",
    ]
    if _has_any(raw, negative_save_patterns):
        return True

    read_verbs = [
        r"读取",
        r"先读取",
        r"先读",
        r"读一下",
        r"查看",
        r"看看",
        r"打开",
        r"浏览",
        r"\bread\b",
        r"\bopen\b",
        r"\bload\b",
    ]
    runtime_followups = [
        r"继续分析",
        r"继续回答",
        r"继续处理",
        r"再基于",
        r"基于已有",
        r"基于当前",
        r"根据.*继续",
        r"\banaly[sz]e\b",
        r"\bcontinue\b",
        r"\banswer\b",
    ]
    target_words = [
        r"supervisor\s+notebook",
        r"agent[_\s-]?notebook",
        r"\bnotebook\b",
        r"\bfile\b",
        r"\bmarkdown\b",
        r"\bmd\b",
        r"文件",
        r"纪要",
        r"笔记",
        r"小本本",
    ]

    mentions_target = _has_any(raw, target_words) or bool(_extract_explicit_path(raw))

    if _has_any(raw, read_verbs) and mentions_target:
        return True

    if (
        _has_any(raw, runtime_followups)
        and mentions_target
        and _has_any(raw, [r"已有记录", r"已有内容", r"当前内容", r"notebook", r"笔记", r"纪要"])
    ):
        return True

    return False


def _looks_like_notebook_redirect_intent(text: str, explicit_path: str, last_save: Dict[str, Any]) -> bool:
    raw = _normalize_text(text)
    if not raw:
        return False

    save_verbs = [
        r"帮我记下来",
        r"帮我记一下",
        r"记一下刚才",
        r"记下刚才",
        r"保存",
        r"保存一下",
        r"记录到",
        r"记录进",
        r"写入",
        r"写到",
        r"写进",
        r"存到",
        r"存下",
        r"整理成",
        r"追加",
        r"归档",
        r"\bsave\b",
        r"\bappend\b",
        r"\bstore\b",
        r"\barchive\b",
        r"\bwrite down\b",
    ]
    if not _has_any(raw, save_verbs) and not explicit_path:
        return False

    if explicit_path.startswith("_room_supervisor_notebooks/"):
        return True

    if explicit_path.startswith("_room_notebooks/"):
        return True

    notebook_words = [
        r"supervisor\s+notebook",
        r"supervisor[_\s-]?notebook",
        r"agent[_\s-]?notebook",
        r"\bnotebook\b",
        r"小本本",
    ]
    if _has_any(raw, notebook_words):
        return True

    refers_last = _has_any(raw, [r"刚才那个", r"上一个", r"上一条", r"上次", r"\blast\b", r"\bprevious\b"])
    if refers_last and _sanitize_target_kind(last_save.get("target_kind"), "") == "agent_notebook":
        return True

    return False


def _looks_like_possible_save_intent(text: str, explicit_path: str, last_save: Dict[str, Any]) -> bool:
    raw = _normalize_text(text)
    if not raw:
        return False

    if _looks_like_read_or_analysis_intent(raw):
        return False

    if explicit_path:
        return True

    possible_patterns = [
        r"保存",
        r"记下",
        r"记一下",
        r"写入",
        r"写到",
        r"写进",
        r"存到",
        r"存下",
        r"整理成",
        r"追加",
        r"归档",
        r"纪要",
        r"小本本",
        r"\bsave\b",
        r"\bappend\b",
        r"\bstore\b",
        r"\barchive\b",
        r"\bwrite down\b",
    ]

    refers_last = _has_any(raw, [r"刚才那个", r"上一个", r"上一条", r"上次", r"\blast\b", r"\bprevious\b"]) and bool(
        str(last_save.get("relative_path") or "").strip()
    )

    return _has_any(raw, possible_patterns) or refers_last


def _looks_like_save_intent(text: str, explicit_path: str, last_save: Dict[str, Any]) -> bool:
    raw = _normalize_text(text)
    if not raw:
        return False

    if _looks_like_read_or_analysis_intent(raw):
        return False

    if explicit_path:
        return True

    strong_patterns = [
        r"帮我记下来",
        r"帮我记一下",
        r"记一下刚才",
        r"记下刚才",
        r"保存这轮",
        r"保存一下",
        r"整理成纪要",
        r"\bsave this\b",
        r"\bnote this down\b",
        r"\bwrite this down\b",
        r"\bsave the (discussion|summary|note)\b",
        r"\bappend to (?:the )?(?:last|previous) (?:note|summary)\b",
    ]
    if _has_any(raw, strong_patterns):
        return True

    save_verbs = [
        r"保存",
        r"记下",
        r"记一下",
        r"记录到",
        r"记录进",
        r"写入",
        r"写到",
        r"写进",
        r"存到",
        r"存下",
        r"整理成",
        r"追加",
        r"归档",
        r"\bsave\b",
        r"\bappend\b",
        r"\bstore\b",
        r"\barchive\b",
        r"\bwrite down\b",
    ]
    target_words = [
        r"room[_\s-]?note",
        r"\bsummary\b",
        r"\bnote\b",
        r"\bfile\b",
        r"房间纪要",
        r"房间笔记",
        r"纪要",
        r"笔记",
        r"文件",
    ]
    refers_last = _has_any(raw, [r"刚才那个", r"上一个", r"上一条", r"上次", r"\blast\b", r"\bprevious\b"]) and bool(
        str(last_save.get("relative_path") or "").strip()
    )

    return _has_any(raw, save_verbs) and (_has_any(raw, target_words) or refers_last)


def _extract_inline_content(text: str) -> str:
    raw = _normalize_text(text)
    if not raw:
        return ""

    lines = raw.split("\n")
    if len(lines) >= 2:
        first_line = _normalize_text(lines[0])
        rest = "\n".join(lines[1:]).strip()
        if rest and _looks_like_possible_save_intent(first_line, _extract_explicit_path(first_line), {}):
            return rest

    colon_positions = [pos for pos in [raw.find("："), raw.find(":")] if pos >= 0]
    if colon_positions:
        pos = min(colon_positions)
        rest = raw[pos + 1:].strip()
        if rest and len(rest) >= 8:
            maybe_path = _extract_explicit_path(rest)
            if not maybe_path or len(rest) > len(maybe_path) + 8:
                return rest

    return ""


def _extract_title(text: str) -> str:
    raw = _normalize_text(text)
    patterns = [
        r"(?:title|标题)\s*(?:叫|为|是|=|:|：)?\s*[\"“'‘`]?([^\n\"”’`]{1,80})",
    ]
    for pattern in patterns:
        m = re.search(pattern, raw, re.I)
        if m:
            return _safe_str(m.group(1))[:80]
    return ""


def _extract_section_title(text: str) -> str:
    raw = _normalize_text(text)
    patterns = [
        r"(?:section_title|section|章节|小节)\s*(?:叫|为|是|=|:|：)?\s*[\"“'‘`]?([^\n\"”’`]{1,80})",
    ]
    for pattern in patterns:
        m = re.search(pattern, raw, re.I)
        if m:
            return _safe_str(m.group(1))[:80]
    return ""


def _resolve_default_agent_id(state: Dict[str, Any]) -> str:
    direct = _safe_str(state.get("default_reply_role_id"))
    if direct:
        return _safe_agent_id(direct, "agent")

    active_roles = state.get("active_roles")
    if isinstance(active_roles, list):
        for item in active_roles:
            s = _safe_str(item)
            if s:
                return _safe_agent_id(s, "agent")

    return "agent"


def _extract_agent_id(text: str, state: Dict[str, Any], last_save: Dict[str, Any], llm_hint: Dict[str, Any]) -> str:
    llm_agent_id = _safe_str(llm_hint.get("agent_id"))
    if llm_agent_id:
        return _safe_agent_id(llm_agent_id, _resolve_default_agent_id(state))

    raw = _normalize_text(text)
    patterns = [
        r"(?:agent_id|agent-id|agent)\s*[:：=]?\s*([A-Za-z0-9_-]{3,})",
        r"(?:role_id|role-id|role)\s*[:：=]?\s*([A-Za-z0-9_-]{3,})",
        r"@([A-Za-z0-9_-]{3,})",
    ]
    for pattern in patterns:
        m = re.search(pattern, raw, re.I)
        if m:
            return _safe_agent_id(m.group(1), _resolve_default_agent_id(state))

    last_agent_id = _safe_str(last_save.get("agent_id"))
    if last_agent_id:
        return _safe_agent_id(last_agent_id, _resolve_default_agent_id(state))

    return _resolve_default_agent_id(state)


def _resolve_mode(text: str, refers_last: bool, llm_hint: Dict[str, Any], target_kind: str) -> str:
    llm_mode = _sanitize_mode(llm_hint.get("mode"), "")
    if llm_mode:
        mode = llm_mode
    else:
        raw = _normalize_text(text)
        if _has_any(raw, [r"覆盖", r"重写", r"替换", r"\boverwrite\b", r"\breplace\b"]):
            mode = "overwrite"
        elif _has_any(raw, [r"追加", r"继续写", r"接着写", r"补充到", r"\bappend\b", r"\bcontinue\b"]):
            mode = "append"
        elif refers_last:
            mode = "append"
        else:
            mode = "append"

    if target_kind == "agent_notebook":
        return "append"
    return mode


def _resolve_target_kind(
    text: str,
    explicit_path: str,
    last_save: Dict[str, Any],
    llm_hint: Dict[str, Any],
) -> str:
    llm_target_kind = _sanitize_target_kind(llm_hint.get("target_kind"), "")
    if llm_target_kind and llm_target_kind != "agent_notebook":
        return llm_target_kind

    raw = _normalize_text(text)
    refers_last = _has_any(raw, [r"刚才那个", r"上一个", r"上一条", r"上次", r"\blast\b", r"\bprevious\b"])
    if refers_last:
        last_kind = _sanitize_target_kind(last_save.get("target_kind"), "")
        if last_kind and last_kind != "agent_notebook":
            return last_kind

    if explicit_path.startswith("_room_notes/"):
        return "room_note"
    if explicit_path.startswith("_room_notebooks/"):
        return "file"
    if explicit_path.startswith("_room_supervisor_notebooks/"):
        return "file"

    if _has_any(raw, [r"room[_\s-]?note", r"房间纪要", r"房间笔记"]):
        return "room_note"
    if explicit_path:
        return "file"
    if _has_any(raw, [r"\bfile\b", r"文件", r"\bmarkdown\b", r"\bmd\b"]):
        return "file"
    if _has_any(raw, [r"纪要", r"笔记", r"\bsummary\b", r"\bnote\b"]):
        return "room_note"

    return "room_note"


def _resolve_content_source(text: str, inline_content: str, llm_hint: Dict[str, Any]) -> str:
    if inline_content:
        return "inline"

    llm_source = _sanitize_content_source(llm_hint.get("content_source"), "")
    if llm_source:
        return llm_source

    raw = _normalize_text(text)
    if _has_any(raw, [r"摘要", r"\bsummary\b"]):
        return "summary"
    if _has_any(raw, [r"scratchpad", r"草稿", r"草稿板"]):
        return "scratchpad"
    if _has_any(raw, [r"计划", r"\bplan\b"]):
        return "last_plan"
    if _has_any(raw, [r"刚才讨论", r"刚刚讨论", r"最近对话", r"\bthis discussion\b", r"\blast discussion\b"]):
        return "recent_dialog"
    return "mixed"


def _recent_dialog_md(room_id: str, limit: int = 8) -> str:
    lines = _build_dialog_lines(room_id, limit=max(1, int(limit)))
    if not lines:
        return ""
    rows = lines[-max(1, int(limit)):]
    return "\n".join([f"- {line}" for line in rows]).strip()


def _build_content(state: Dict[str, Any], room_id: str, raw_text: str, inline_content: str, content_source: str) -> str:
    summary = _safe_str(state.get("summary"))
    scratchpad = _safe_str(state.get("scratchpad"))
    last_plan = _safe_str(state.get("last_plan_summary"))
    recent_dialog = _recent_dialog_md(room_id, limit=8)

    if inline_content:
        return inline_content

    if content_source == "summary" and summary:
        return summary
    if content_source == "scratchpad" and scratchpad:
        return scratchpad
    if content_source == "last_plan" and last_plan:
        return last_plan
    if content_source == "recent_dialog" and recent_dialog:
        return recent_dialog

    parts: List[str] = []
    if summary:
        parts.append(f"## 房间摘要\n\n{summary}")
    if last_plan:
        parts.append(f"## 最新计划\n\n{last_plan}")
    if scratchpad and not parts:
        parts.append(f"## Scratchpad\n\n{scratchpad}")
    if recent_dialog:
        parts.append(f"## 最近对话\n\n{recent_dialog}")

    parts.append(f"## 保存指令\n\n{_normalize_text(raw_text)}")
    return "\n\n".join([p for p in parts if _safe_str(p)]).strip()


def _resolve_section_title(text: str, target_kind: str, content_source: str, llm_hint: Dict[str, Any]) -> str:
    llm_section = _safe_str(llm_hint.get("section_title"))
    if llm_section:
        return llm_section[:80]

    extracted = _extract_section_title(text)
    if extracted:
        return extracted[:80]

    if content_source == "scratchpad":
        return "scratchpad"
    if content_source == "last_plan":
        return "latest_plan"
    if target_kind == "agent_notebook":
        return "阶段整理"
    if target_kind == "file":
        return "记录"
    return "本轮记录"


def _resolve_title(text: str, target_kind: str, agent_id: str, llm_hint: Dict[str, Any]) -> str:
    llm_title = _safe_str(llm_hint.get("title"))
    if llm_title:
        return llm_title[:120]

    extracted = _extract_title(text)
    if extracted:
        return extracted[:120]

    if target_kind == "agent_notebook":
        return f"{agent_id} notebook"
    if target_kind == "file":
        return "room export"
    return "room notes"


def _split_agent_notebook_save_as(save_as: str) -> Tuple[str, str]:
    rel = _normalize_rel_path(save_as)
    if not rel:
        return "", ""
    if "/" not in rel:
        return "", rel
    parts = rel.split("/")
    filename = parts.pop() if parts else ""
    return "/".join(parts), filename


def _default_file_path(room_id: str) -> str:
    return f"notes/{_safe_token(room_id, 'room')}.md"


def _resolve_relative_path(
    room_id: str,
    target_kind: str,
    explicit_path: str,
    refers_last: bool,
    last_save: Dict[str, Any],
    snapshot: Dict[str, Any],
    agent_id: str,
    llm_hint: Dict[str, Any],
) -> str:
    llm_rel = _normalize_rel_path(llm_hint.get("relative_path"))
    if llm_rel:
        return llm_rel

    if explicit_path:
        return explicit_path

    if refers_last:
        last_kind = _sanitize_target_kind(last_save.get("target_kind"), "")
        last_rel = _normalize_rel_path(last_save.get("relative_path"))
        if last_rel and (not last_kind or last_kind == target_kind):
            return last_rel

    if target_kind == "room_note":
        return _normalize_rel_path(snapshot.get("suggested_room_note_relative_path")) or f"_room_notes/{_safe_token(room_id, 'room')}.md"
    if target_kind == "agent_notebook":
        return _normalize_rel_path(snapshot.get("suggested_agent_notebook_relative_path")) or f"_room_notebooks/{_safe_token(agent_id, 'agent')}.md"
    return _default_file_path(room_id)


def _try_llm_intent_parse(text: str, last_save: Dict[str, Any], state: Dict[str, Any]) -> Dict[str, Any]:
    raw = _normalize_text(text)
    if not raw:
        return {}

    system_prompt = (
        "你是 NISB room 的自然语言保存意图解析器。\n"
        "请判断用户这句话是否在要求把当前 room 内容保存到 workspace。\n"
        "严格只输出 JSON，不要输出解释。\n"
        "JSON 结构："
        '{"handled":true|false,'
        '"target_kind":"room_note|agent_notebook|file|",'
        '"mode":"append|overwrite|",'
        '"content_source":"inline|summary|scratchpad|last_plan|recent_dialog|mixed|",'
        '"relative_path":"",'
        '"agent_id":"",'
        '"title":"",'
        '"section_title":"",'
        '"need_confirm":true|false}'
    )

    user_prompt = (
        f"用户输入：{raw}\n\n"
        f"最近一次保存：target_kind={_safe_str(last_save.get('target_kind'))}, "
        f"relative_path={_safe_str(last_save.get('relative_path'))}, "
        f"agent_id={_safe_str(last_save.get('agent_id'))}\n"
        f"room 摘要是否存在：{'yes' if _safe_str(state.get('summary')) else 'no'}\n"
        f"scratchpad 是否存在：{'yes' if _safe_str(state.get('scratchpad')) else 'no'}\n"
        f"latest_plan 是否存在：{'yes' if _safe_str(state.get('last_plan_summary')) else 'no'}"
    )

    try:
        data = _call_llm_json(model_name="gpt-4o-mini", user_prompt=user_prompt, system_prompt=system_prompt)
        if isinstance(data, dict):
            return data
    except MissingLLMDependencyError:
        return {}
    except Exception:
        return {}

    return {}


def _build_parse_result(args: Dict[str, Any], room_id: str, state: Dict[str, Any], text: str) -> Dict[str, Any]:
    raw = _normalize_text(text)
    last_save = _get_last_workspace_save(state)
    explicit_path = _extract_explicit_path(raw)

    if _looks_like_read_or_analysis_intent(raw):
        return _ok(
            room_id=room_id,
            handled=False,
            intent_type="chat",
            need_confirm=False,
            reason_code="read_or_analysis_intent",
            text=raw,
        )

    if _looks_like_notebook_redirect_intent(raw, explicit_path, last_save):
        return _ok(
            room_id=room_id,
            handled=False,
            intent_type="chat",
            need_confirm=False,
            reason_code="notebook_intent_redirect_to_supervisor",
            text=raw,
        )

    heuristic_possible = _looks_like_possible_save_intent(raw, explicit_path, last_save)
    heuristic_handled = _looks_like_save_intent(raw, explicit_path, last_save)
    llm_hint = _try_llm_intent_parse(raw, last_save, state) if heuristic_possible else {}

    if _sanitize_target_kind(llm_hint.get("target_kind"), "") == "agent_notebook":
        return _ok(
            room_id=room_id,
            handled=False,
            intent_type="chat",
            need_confirm=False,
            reason_code="llm_agent_notebook_redirect_to_supervisor",
            text=raw,
        )

    handled = heuristic_handled or bool(llm_hint.get("handled"))
    if not handled:
        return _ok(
            room_id=room_id,
            handled=False,
            intent_type="chat",
            need_confirm=False,
            reason_code="not_save_intent",
            text=raw,
        )

    workspace_id = _safe_str(state.get("workspace_id") or args.get("workspace_id"))
    focus_root = _safe_str(state.get("focus_root") or args.get("focus_root"))
    workspace_name = _safe_str(state.get("workspace_name"))
    focus_label = _safe_str(state.get("focus_label"))

    refers_last = _has_any(raw, [r"刚才那个", r"上一个", r"上一条", r"上次", r"\blast\b", r"\bprevious\b"]) and bool(
        _safe_str(last_save.get("relative_path"))
    )

    agent_id = _extract_agent_id(raw, state, last_save, llm_hint)
    snapshot: Dict[str, Any] = {}
    if workspace_id:
        snapshot = nisb_workspace_snapshot_get({
            **dict(args or {}),
            "room_id": room_id,
            "workspace_id": workspace_id,
            "focus_root": focus_root,
            "agent_id": agent_id,
        })
        if not isinstance(snapshot, dict):
            snapshot = {}

    target_kind = _resolve_target_kind(raw, explicit_path, last_save, llm_hint)
    if target_kind == "agent_notebook":
        return _ok(
            room_id=room_id,
            handled=False,
            intent_type="chat",
            need_confirm=False,
            reason_code="resolved_agent_notebook_redirect_to_supervisor",
            text=raw,
        )

    relative_path = _resolve_relative_path(
        room_id=room_id,
        target_kind=target_kind,
        explicit_path=explicit_path,
        refers_last=refers_last,
        last_save=last_save,
        snapshot=snapshot,
        agent_id=agent_id,
        llm_hint=llm_hint,
    )
    mode = _resolve_mode(raw, refers_last, llm_hint, target_kind)
    inline_content = _extract_inline_content(raw)
    content_source = _resolve_content_source(raw, inline_content, llm_hint)
    content = _build_content(state, room_id, raw, inline_content, content_source)
    title = _resolve_title(raw, target_kind, agent_id, llm_hint)
    section_title = _resolve_section_title(raw, target_kind, content_source, llm_hint)

    need_confirm = False
    reason_code = ""
    prompt_message = ""

    if not workspace_id:
        need_confirm = True
        reason_code = "missing_workspace"
        prompt_message = "当前 room 还没有绑定工作区，先绑定 workspace 后才能执行保存。"
    elif not _safe_str(content):
        need_confirm = True
        reason_code = "missing_content"
        prompt_message = "我知道你想保存，但当前 room 还没有足够可沉淀的内容，请补一句要保存的正文，或先产生摘要/计划。"

    return _ok(
        room_id=room_id,
        handled=True,
        intent_type="room_save",
        need_confirm=need_confirm,
        reason_code=reason_code,
        prompt_message=prompt_message,
        workspace_id=workspace_id,
        workspace_name=workspace_name,
        focus_root=focus_root,
        focus_label=focus_label,
        target_kind=target_kind,
        mode=mode,
        relative_path=relative_path,
        save_as=relative_path if target_kind == "room_note" else "",
        agent_id=agent_id,
        title=title,
        section_title=section_title,
        content_source=content_source,
        content=content,
        explicit_path=explicit_path,
        refers_last=refers_last,
        snapshot=snapshot if isinstance(snapshot, dict) else {},
        text=raw,
    )


def _record_last_workspace_save(
    room_id: str,
    uid: str,
    request_id: str,
    detail: Dict[str, Any],
    source_text: str,
) -> Dict[str, Any]:
    state = load_state_doc(room_id)
    payload = {
        "target_kind": _sanitize_target_kind(detail.get("target_kind"), "file"),
        "relative_path": _normalize_rel_path(detail.get("relative_path")),
        "scoped_path": _safe_str(detail.get("scoped_path")),
        "agent_id": _safe_agent_id(detail.get("agent_id"), "agent") if _safe_str(detail.get("agent_id")) else "",
        "mode": _sanitize_mode(detail.get("mode"), "append"),
        "title": _safe_str(detail.get("title")),
        "section_title": _safe_str(detail.get("section_title")),
        "saved_at": utc_iso(),
    }

    state["last_workspace_save"] = payload
    save_state_doc(room_id, state)
    touch_room_updated_at(room_id)

    evt = {
        "id": new_id("evt"),
        "ts": utc_iso(),
        "type": "room.workspace_save",
        "room_id": room_id,
        "request_id": request_id,
        "payload": {
            "sender": uid,
            "source_text": _normalize_text(source_text)[:500],
            **payload,
        },
    }
    append_room_event(room_id, evt)
    return payload


def nisb_room_save_intent_parse(args: Dict[str, Any]) -> Dict[str, Any]:
    basepath = get_basepath(args)
    uid = uid_from_ctx_or_basepath(basepath, args)
    rid = ensure_request_id(args)

    room_id = require_safe_id("room_id", args.get("room_id"))
    meta = ensure_room_exists(room_id)
    if meta and not is_participant(uid, meta):
        return _err("permission denied", request_id=rid)

    text = _normalize_text(args.get("text") or args.get("content"))
    if not text:
        return _err("missing room_id/text", request_id=rid)

    state = load_state_doc(room_id)
    result = _build_parse_result(args=args, room_id=room_id, state=state, text=text)
    result["request_id"] = rid
    return result


def nisb_room_save_from_text(args: Dict[str, Any]) -> Dict[str, Any]:
    basepath = get_basepath(args)
    uid = uid_from_ctx_or_basepath(basepath, args)
    rid = ensure_request_id(args)

    room_id = require_safe_id("room_id", args.get("room_id"))
    meta = ensure_room_exists(room_id)
    if meta and not is_participant(uid, meta):
        return _err("permission denied", request_id=rid)

    text = _normalize_text(args.get("text") or args.get("content"))
    if not text:
        return _err("missing room_id/text", request_id=rid)

    state = load_state_doc(room_id)
    parsed = _build_parse_result(args=args, room_id=room_id, state=state, text=text)
    if not parsed.get("handled"):
        return _ok(
            room_id=room_id,
            handled=False,
            request_id=rid,
            message="not save intent",
            reason_code=parsed.get("reason_code") or "",
        )

    if parsed.get("need_confirm"):
        return _ok(
            room_id=room_id,
            handled=True,
            need_confirm=True,
            reason_code=parsed.get("reason_code") or "",
            prompt_message=parsed.get("prompt_message") or "",
            request_id=rid,
        )

    target_kind = _sanitize_target_kind(parsed.get("target_kind"), "room_note")
    if target_kind == "agent_notebook":
        return _err(
            "room 内 legacy agent_notebook 保存已停用，请改用 Supervisor notebook 正式链",
            request_id=rid,
            reason_code="legacy_agent_notebook_disabled_in_room",
        )

    mode = _sanitize_mode(parsed.get("mode"), "append")
    workspace_id = _safe_str(parsed.get("workspace_id"))
    focus_root = _safe_str(parsed.get("focus_root"))
    relative_path = _normalize_rel_path(parsed.get("relative_path"))
    agent_id = _safe_agent_id(parsed.get("agent_id"), "agent")
    title = _safe_str(parsed.get("title"))
    section_title = _safe_str(parsed.get("section_title"))
    content = str(parsed.get("content") or "")
    rebuild_index = bool(args.get("rebuild_index", True))

    write_args = dict(args or {})
    write_args["room_id"] = room_id
    write_args["workspace_id"] = workspace_id
    write_args["focus_root"] = focus_root
    write_args["content"] = content
    write_args["mode"] = mode
    write_args["target_kind"] = target_kind
    write_args["title"] = title
    write_args["section_title"] = section_title
    write_args["rebuild_index"] = rebuild_index

    if target_kind == "room_note":
        write_args["save_as"] = relative_path
    else:
        write_args["relative_path"] = relative_path

    write_result = nisb_workspace_write_entry(write_args)
    if not _tool_success(write_result):
        return _err(write_result.get("message") or "workspace save failed", request_id=rid, raw=write_result)

    detail = {
        "room_id": room_id,
        "workspace_id": workspace_id,
        "focus_root": focus_root,
        "target_kind": _sanitize_target_kind(write_result.get("target_kind"), target_kind),
        "relative_path": _normalize_rel_path(write_result.get("relative_path") or relative_path),
        "scoped_path": _safe_str(write_result.get("scoped_path")),
        "agent_id": "",
        "mode": mode,
        "title": title,
        "section_title": _safe_str(write_result.get("section_title") or section_title),
        "content_source": _sanitize_content_source(parsed.get("content_source"), "mixed"),
        "message": _safe_str(write_result.get("message"), "写入成功"),
    }

    saved_state = _record_last_workspace_save(
        room_id=room_id,
        uid=uid,
        request_id=rid,
        detail=detail,
        source_text=text,
    )

    return _ok(
        handled=True,
        request_id=rid,
        **detail,
        last_workspace_save=saved_state,
    )


__all__ = [
    "nisb_room_save_intent_parse",
    "nisb_room_save_from_text",
]
