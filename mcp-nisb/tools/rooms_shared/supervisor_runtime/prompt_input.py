from __future__ import annotations

from typing import Any, Dict, List


def _safe_str(v: Any, default: str = "") -> str:
    if v is None:
        return default
    s = str(v).strip()
    return s if s else default


def _safe_list(v: Any) -> List[Any]:
    return v if isinstance(v, list) else []


def _safe_dict(v: Any) -> Dict[str, Any]:
    return v if isinstance(v, dict) else {}


def _truncate_text(value: Any, limit: int = 12000) -> str:
    text = _safe_str(value)
    if not text:
        return ""
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + "\n...[truncated]"


def _append_unique_block(blocks: List[str], seen: set, label: str, content: str) -> None:
    normalized_label = _safe_str(label)
    normalized_content = _truncate_text(content)
    if not normalized_content:
        return
    block = f"[{normalized_label}]\n{normalized_content}".strip() if normalized_label else normalized_content
    key = block.strip()
    if not key or key in seen:
        return
    seen.add(key)
    blocks.append(block)


def _extract_text_fields(obj: Dict[str, Any]) -> str:
    row = _safe_dict(obj)
    for key in ("content", "text", "response", "body", "file_content"):
        value = _safe_str(row.get(key))
        if value:
            return value
    return ""


def _candidate_request_context_objects(request_args: Dict[str, Any]) -> List[Dict[str, Any]]:
    root = _safe_dict(request_args)
    out: List[Dict[str, Any]] = []

    def push(value: Any) -> None:
        obj = _safe_dict(value)
        if obj:
            out.append(obj)

    push(root.get("fs_context"))
    push(root.get("supervisor_fs_context"))
    push(root.get("room_supervisor_fs_context"))
    push(root.get("last_supervisor_fs_context"))
    push(root.get("room_fs_context"))

    for key in ("tool_result", "last_supervisor_tool_result"):
        push(root.get(key))

    for key in (
        "tool_results",
        "last_supervisor_tool_results",
        "last_supervisor_fs_tool_results",
        "supervisor_tool_results",
        "supervisor_fs_tool_results",
    ):
        rows = root.get(key)
        if not isinstance(rows, list):
            continue
        for row in rows:
            push(row)
            row_obj = _safe_dict(row)
            push(row_obj.get("data"))
            push(row_obj.get("result"))
            push(row_obj.get("payload"))
            push(row_obj.get("value"))

    return out


def _extract_supervisor_direct_prompt(request_args: Dict[str, Any]) -> str:
    root = _safe_dict(request_args)
    for key in (
        "_supervisor_direct_prompt",
        "supervisor_direct_prompt",
        "_direct_prompt",
        "direct_prompt",
        "prompt_override",
    ):
        value = _safe_str(root.get(key))
        if value:
            return value
    return ""


def _extract_supervisor_fs_context_blocks(request_args: Dict[str, Any]) -> List[str]:
    root = _safe_dict(request_args)
    blocks: List[str] = []
    seen = set()

    for key in (
        "_supervisor_fs_read_text",
        "supervisor_fs_read_text",
        "last_supervisor_fs_read_text",
        "room_supervisor_fs_read_text",
        "fs_context_text",
    ):
        value = _safe_str(root.get(key))
        if value:
            _append_unique_block(blocks, seen, key, value)

    for key in (
        "documents",
        "fs_documents",
        "supervisor_fs_documents",
        "room_supervisor_fs_documents",
    ):
        rows = root.get(key)
        if not isinstance(rows, list):
            continue
        for row in rows:
            row_obj = _safe_dict(row)
            path = _safe_str(row_obj.get("path") or row_obj.get("relative_path") or row_obj.get("filename") or "document")
            content = _extract_text_fields(row_obj)
            if content:
                _append_unique_block(blocks, seen, path, content)

    for obj in _candidate_request_context_objects(root):
        obj_type = _safe_str(obj.get("type")).lower()

        if obj_type in {"room_supervisor_fs_read", "room_supervisor_fs_probe"}:
            text_value = _extract_text_fields(obj)
            if text_value:
                _append_unique_block(blocks, seen, _safe_str(obj.get("type"), "fs_context"), text_value)

        for key in ("documents", "files", "items"):
            rows = obj.get(key)
            if not isinstance(rows, list):
                continue
            for row in rows:
                row_obj = _safe_dict(row)
                path = _safe_str(row_obj.get("path") or row_obj.get("relative_path") or row_obj.get("filename") or "document")
                content = _extract_text_fields(row_obj)
                if content:
                    _append_unique_block(blocks, seen, path, content)

        if any(key in obj for key in ("documents", "files", "items", "entries", "previews")):
            text_value = _safe_str(obj.get("text") or obj.get("content") or obj.get("response"))
            if text_value and len(text_value) >= 32:
                _append_unique_block(blocks, seen, _safe_str(obj.get("type"), "fs_context"), text_value)

    return blocks


def _extract_user_question(question: str, request_args: Dict[str, Any]) -> str:
    direct = _safe_str(
        request_args.get("_user_question")
        or request_args.get("user_question")
        or request_args.get("original_question")
        or request_args.get("content")
        or request_args.get("question")
    )
    if direct:
        return direct

    text = _safe_str(question)
    markers = ["用户问题：", "用户问题:", "Question:", "question:"]
    for marker in markers:
        idx = text.rfind(marker)
        if idx < 0:
            continue
        candidate = text[idx + len(marker):].strip()
        if not candidate:
            continue
        for line in candidate.splitlines():
            cleaned = _safe_str(line)
            if cleaned:
                return cleaned
        if candidate:
            return candidate

    return text


def _build_effective_room_question(
    *,
    question: str,
    request_args: Dict[str, Any],
    include_direct_prompt: bool = False,
) -> str:
    raw_question = _safe_str(question)
    user_question = _extract_user_question(raw_question, request_args) or raw_question

    if include_direct_prompt:
        direct_prompt = _extract_supervisor_direct_prompt(request_args)
        if direct_prompt:
            return direct_prompt

    parts: List[str] = []

    fs_blocks = _extract_supervisor_fs_context_blocks(request_args)
    if fs_blocks:
        parts.append(
            "以下是当前 Room 已授权并且已经读取成功的文件正文。"
            "请优先基于这些内容直接回答用户；如果这些内容已经足够，就不要再说你无法读取文件。\n\n"
            + "\n\n".join(fs_blocks)
        )

    if user_question:
        parts.append(f"用户问题：\n{user_question}")
    elif raw_question:
        parts.append(raw_question)

    return "\n\n".join([part for part in parts if _safe_str(part)]).strip() or raw_question


__all__ = [
    "_build_effective_room_question",
    "_extract_supervisor_direct_prompt",
    "_extract_supervisor_fs_context_blocks",
    "_extract_user_question",
]
