from __future__ import annotations

from typing import Any, Dict, List, Tuple

from ..room_filesystem_bridge import room_supervisor_fs_read


def _safe_str(v: Any, default: str = "") -> str:
    if v is None:
        return default
    s = str(v).strip()
    return s if s else default


def _safe_list(v: Any) -> List[Any]:
    return v if isinstance(v, list) else []


def _safe_dict(v: Any) -> Dict[str, Any]:
    return v if isinstance(v, dict) else {}


def _merge_items(*parts: Any) -> List[Any]:
    out: List[Any] = []
    for part in parts:
        if isinstance(part, list):
            out.extend(part)
    return out


def _dedupe_records(rows: List[Any]) -> List[Any]:
    out: List[Any] = []
    seen = set()
    for idx, row in enumerate(_safe_list(rows)):
        if not isinstance(row, dict):
            out.append(row)
            continue
        key = (
            _safe_str(row.get("tool_call_id") or row.get("call_id") or row.get("id")),
            _safe_str(row.get("tool_name") or row.get("name") or row.get("type")),
            str(idx),
        )
        if key in seen:
            continue
        seen.add(key)
        out.append(row)
    return out


def _normalize_rel_path(value: Any) -> str:
    raw = _safe_str(value).replace("\\", "/")
    while "//" in raw:
        raw = raw.replace("//", "/")
    raw = raw.strip("/")
    if not raw:
        return ""
    parts = [p.strip() for p in raw.split("/") if p and p not in {".", ".."}]
    return "/".join(parts)


def _clip_text(value: Any, max_len: int = 2400) -> str:
    text = _safe_str(value)
    if not text:
        return ""
    if len(text) <= max_len:
        return text
    return text[:max_len].rstrip() + "\n...[truncated]"


def _looks_like_markdown_path(value: Any) -> bool:
    path = _normalize_rel_path(value).lower()
    return path.endswith(".md") or path.endswith(".markdown") or path.endswith(".mdx")


def _basename(path: Any) -> str:
    normalized = _normalize_rel_path(path)
    return normalized.split("/")[-1] if normalized else ""


def _question_requests_file_content(question: str) -> bool:
    q = _safe_str(question).lower()
    if not q:
        return False
    strong_tokens = [
        ".md",
        "md文件",
        "markdown",
        "读取",
        "读一下",
        "看看",
        "查看",
        "打开",
        "文件内容",
        "内容",
        "正文",
        "原文",
        "摘录",
        "片段",
        "首段",
        "反馈信息",
        "读取任何一个",
    ]
    return any(token in q for token in strong_tokens)


def _row_markdown_candidate_paths(row: Dict[str, Any], focus_root: str) -> List[str]:
    src = _safe_dict(row)
    focus_root = _normalize_rel_path(focus_root)
    out: List[str] = []

    is_dir = src.get("is_dir")
    kind = _safe_str(src.get("kind") or src.get("type")).lower()
    if is_dir is True or kind in {"dir", "directory", "folder"}:
        return []

    for key in ("path", "relative_path", "logical_path", "file_path", "filename"):
        candidate = _normalize_rel_path(src.get(key))
        if _looks_like_markdown_path(candidate):
            out.append(candidate)

    name = _safe_str(src.get("name"))
    if name and _looks_like_markdown_path(name):
        if "/" in name:
            out.append(_normalize_rel_path(name))
        elif focus_root:
            out.append(_normalize_rel_path(f"{focus_root}/{name}"))
        else:
            out.append(_normalize_rel_path(name))

    deduped: List[str] = []
    seen = set()
    for item in out:
        if not item or item in seen:
            continue
        seen.add(item)
        deduped.append(item)
    return deduped


def _score_markdown_candidate(path: str, question: str) -> Tuple[int, str]:
    normalized_path = _normalize_rel_path(path)
    base = _basename(normalized_path).lower()
    q = _safe_str(question).lower()

    stem = base
    for suffix in (".markdown", ".mdx", ".md"):
        if stem.endswith(suffix):
            stem = stem[:-len(suffix)].strip()
            break

    score = 0
    if base and base in q:
        score += 100
    if stem and stem in q:
        score += 100
    if ".md" in q or "markdown" in q or "md文件" in q:
        score += 20
    if any(token in q for token in ["读取", "查看", "打开", "内容", "正文", "原文", "摘录", "片段"]):
        score += 20
    if "反馈" in q and "反馈" in normalized_path:
        score += 30
    if "记录" in q and "记录" in normalized_path:
        score += 30
    if "supervisor" in q and "supervisor" in base:
        score += 20
    if "notebook" in q and "supervisor" in base:
        score += 20
    if "_room_supervisor_notebooks/" in normalized_path and "supervisor" not in q and "notebook" not in q:
        score -= 5

    return score, normalized_path


def _select_markdown_targets(question: str, fs_context: Dict[str, Any], limit: int = 1) -> List[str]:
    focus_root = _normalize_rel_path(fs_context.get("focus_root"))
    candidates: List[str] = []

    for row in _safe_list(fs_context.get("previews")):
        candidates.extend(_row_markdown_candidate_paths(_safe_dict(row), focus_root))

    for row in _safe_list(fs_context.get("entries")):
        candidates.extend(_row_markdown_candidate_paths(_safe_dict(row), focus_root))

    deduped: List[str] = []
    seen = set()
    for item in candidates:
        normalized = _normalize_rel_path(item)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        deduped.append(normalized)

    scored = sorted(
        deduped,
        key=lambda item: _score_markdown_candidate(item, question),
        reverse=True,
    )
    return scored[:max(int(limit or 1), 1)]


def _build_documents_text(documents: List[Dict[str, Any]]) -> str:
    rows = []
    for item in _safe_list(documents)[:3]:
        doc = _safe_dict(item)
        path = _normalize_rel_path(
            doc.get("path")
            or doc.get("relative_path")
            or doc.get("logical_path")
            or doc.get("filename")
        )
        content = _safe_str(
            doc.get("content")
            or doc.get("text")
            or doc.get("body")
            or doc.get("file_content")
            or doc.get("response")
        )
        if not path and not content:
            continue
        rows.append({
            "path": path or "unknown.md",
            "content": _clip_text(content, 2600),
        })

    if not rows:
        return ""

    lines: List[str] = []
    lines.append("以下是已读取的房间文件内容（受控范围内）：")
    for row in rows:
        lines.append("")
        lines.append(f"### 文件：{row['path']}")
        lines.append(row["content"] or "(empty)")
    return "\n".join(lines).strip()


def _augment_fs_context_with_file_read(
    *,
    fs_context: Dict[str, Any],
    file_read_result: Dict[str, Any],
) -> Dict[str, Any]:
    base = dict(_safe_dict(fs_context))
    read_row = _safe_dict(file_read_result)
    documents = _safe_list(read_row.get("documents"))
    documents_text = _build_documents_text(documents)

    existing_text = _safe_str(base.get("text"))
    merged_text_parts = [part for part in [existing_text, documents_text] if part]

    base["documents"] = documents
    base["documents_count"] = len(documents)
    base["target_paths"] = _safe_list(read_row.get("target_paths"))
    base["content_status"] = _safe_str(read_row.get("status"))
    base["content_message"] = _safe_str(read_row.get("message"))
    base["content_recorded_at"] = _safe_str(read_row.get("recorded_at"))
    base["documents_text"] = documents_text
    base["text"] = "\n\n".join(merged_text_parts).strip()
    base["tool_calls"] = _dedupe_records(
        _merge_items(base.get("tool_calls"), read_row.get("tool_calls"))
    )
    base["tool_results"] = _dedupe_records(
        _merge_items(base.get("tool_results"), read_row.get("tool_results"))
    )
    return base


def _maybe_run_supervisor_file_read(
    *,
    room_id: str,
    question: str,
    request_args: Dict[str, Any],
    fs_context: Dict[str, Any],
    run_id: str = "",
    supervisor_event_id: str = "",
    final_event_id: str = "",
) -> Dict[str, Any]:
    if _safe_str(fs_context.get("status")) not in {"success", "warning"}:
        return {}

    targets = _select_markdown_targets(question, fs_context, limit=1)
    if not targets:
        return {}

    top_score, _ = _score_markdown_candidate(targets[0], question)
    explicit_request = _question_requests_file_content(question)

    if not explicit_request and top_score < 100:
        return {}

    return room_supervisor_fs_read(
        room_id=room_id,
        request_args=request_args,
        target_paths=targets,
        run_id=run_id,
        supervisor_event_id=supervisor_event_id,
        final_event_id=final_event_id,
    )


__all__ = [
    "_augment_fs_context_with_file_read",
    "_maybe_run_supervisor_file_read",
    "_select_markdown_targets",
]
