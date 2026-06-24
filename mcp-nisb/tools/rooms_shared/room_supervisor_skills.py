from __future__ import annotations

import re
from typing import Any, Dict, Iterator, List, Set

from .room_contracts import ensure_request_id, require_safe_id, utc_iso
from .room_filesystem_bridge import room_supervisor_skills_probe
from .room_state_normalizer import _normalize_enabled_supervisor_skill_ids
from .room_store import (
    ensure_room_exists,
    get_basepath,
    is_participant,
    load_state_doc,
    uid_from_ctx_or_basepath,
)
from .room_workspace import resolve_room_supervisor_fs_boundary


_SKILLS_DIRNAME = "_room_supervisor_skills"
_MISSING_REASON_CODES = {
    "NOT_FOUND",
    "PATH_NOT_FOUND",
    "FS_PATH_NOT_FOUND",
    "ENTRY_NOT_FOUND",
    "DIRECTORY_NOT_FOUND",
}
_MAX_SUPERVISOR_SKILL_CHARS = 1800
_MAX_SUPERVISOR_SKILLS_TOTAL_CHARS = 6000


def _safe_str(value: Any, default: str = "") -> str:
    if value is None:
        return default
    text = str(value).strip()
    return text if text else default


def _safe_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _safe_list(value: Any) -> List[Any]:
    return value if isinstance(value, list) else []


def _safe_bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    text = _safe_str(value).lower()
    if text in {"1", "true", "yes", "y", "on"}:
        return True
    if text in {"0", "false", "no", "n", "off"}:
        return False
    return default


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


def _normalize_logical_path(value: Any) -> str:
    raw = _safe_str(value).replace("\\", "/")
    while "//" in raw:
        raw = raw.replace("//", "/")
    if raw in {".", "./"}:
        return "."
    raw = raw.strip("/")
    if not raw:
        return ""
    parts = [part.strip() for part in raw.split("/") if part and part not in {".", ".."}]
    return "/".join(parts)


def _join_path(*parts: Any) -> str:
    normalized: List[str] = []
    for part in parts:
        value = _normalize_logical_path(part)
        if value:
            normalized.append(value)
    return "/".join(normalized).strip("/")


def _basename(path: Any) -> str:
    normalized = _normalize_logical_path(path)
    if not normalized:
        return ""
    return normalized.rsplit("/", 1)[-1]


def _strip_md_suffix(path: Any) -> str:
    value = _normalize_logical_path(path)
    if value.lower().endswith(".md"):
        return value[:-3]
    return value


def _strip_skills_root_prefix(path: Any, *, skills_root: str) -> str:
    normalized = _normalize_logical_path(path)
    if not normalized:
        return ""

    normalized_skills_root = _normalize_logical_path(skills_root)

    prefixes = [normalized_skills_root, _SKILLS_DIRNAME]
    for prefix in prefixes:
        prefix = _normalize_logical_path(prefix)
        if not prefix:
            continue
        if normalized == prefix:
            return ""
        if normalized.startswith(prefix + "/"):
            return normalized[len(prefix) + 1 :]

    return normalized


def _entry_is_dir(entry: Dict[str, Any]) -> bool:
    row = _safe_dict(entry)
    if _safe_bool(row.get("is_dir")):
        return True
    if _safe_bool(row.get("isDir")):
        return True
    kind = _safe_str(row.get("type")).lower()
    return kind in {"dir", "directory", "folder"}


def _entry_path_under_skills_root(entry: Dict[str, Any], *, skills_root: str) -> str:
    row = _safe_dict(entry)

    for key in (
        "relative_path",
        "relativePath",
        "path",
        "logical_path",
        "logicalPath",
        "full_path",
        "fullPath",
        "name",
        "filename",
        "file_name",
        "fileName",
    ):
        value = _normalize_logical_path(row.get(key))
        if not value:
            continue

        stripped = _strip_skills_root_prefix(value, skills_root=skills_root)
        if stripped:
            return stripped

    return ""


def _entry_text(entry: Dict[str, Any]) -> str:
    row = _safe_dict(entry)
    for key in (
        "content",
        "text",
        "response",
        "body",
        "file_content",
        "fileContent",
        "preview",
        "markdown",
        "raw_text",
        "rawText",
        "full_text",
        "fullText",
    ):
        value = _safe_str(row.get(key))
        if value:
            return value
    return ""


def _extract_markdown_title(text: str, fallback: str) -> str:
    raw = _safe_str(text)
    if raw:
        match = re.search(r"(?m)^#\s+(.+?)\s*$", raw)
        if match:
            title = _safe_str(match.group(1))
            if title:
                return title
    return _safe_str(fallback)


def _entry_size(entry: Dict[str, Any]) -> int:
    row = _safe_dict(entry)
    for key in ("size", "bytes", "content_length", "contentLength"):
        value = row.get(key)
        try:
            return int(value or 0)
        except Exception:
            continue
    return 0


def _entry_updated_at(entry: Dict[str, Any]) -> str:
    row = _safe_dict(entry)
    for key in ("updated_at", "updatedAt", "modified_at", "modifiedAt", "mtime"):
        value = _safe_str(row.get(key))
        if value:
            return value
    return ""


def _nested_rows(value: Any) -> List[Dict[str, Any]]:
    rows = _safe_list(value)
    return [row for row in rows if isinstance(row, dict)]


def _iter_tree_rows(rows: List[Any]) -> Iterator[Dict[str, Any]]:
    for row in _safe_list(rows):
        obj = _safe_dict(row)
        if not obj:
            continue

        yield obj

        for key in ("children", "entries", "items", "files", "documents"):
            nested = _nested_rows(obj.get(key))
            if nested:
                yield from _iter_tree_rows(nested)


def _build_preview_title_map(previews: List[Any], *, skills_root: str) -> Dict[str, str]:
    out: Dict[str, str] = {}
    for obj in _iter_tree_rows(previews):
        rel_path = _entry_path_under_skills_root(obj, skills_root=skills_root)
        if not rel_path or not rel_path.lower().endswith(".md"):
            continue
        title = _extract_markdown_title(_entry_text(obj), "")
        if title:
            out[_normalize_logical_path(rel_path)] = title
    return out

def _content_source_rank(source_kind: Any) -> int:
    kind = _safe_str(source_kind).lower()
    if kind in {"file_read", "preview_read", "skill_file_read"}:
        return 300
    if kind in {"entry", "snapshot_entry", "fs_entry"}:
        return 200
    if kind in {"snapshot_preview", "preview", "fs_preview"}:
        return 100
    if kind == "fallback":
        return 10
    return 0


def _prefer_content_record(current: Any, candidate: Any) -> Dict[str, Any]:
    cur = _safe_dict(current)
    cand = _safe_dict(candidate)

    if not cand:
        return cur
    if not cur:
        return cand

    cur_text = _safe_str(cur.get("text"))
    cand_text = _safe_str(cand.get("text"))

    cur_score = (
        _content_source_rank(cur.get("source_kind")),
        1 if cur_text else 0,
        len(cur_text),
    )
    cand_score = (
        _content_source_rank(cand.get("source_kind")),
        1 if cand_text else 0,
        len(cand_text),
    )

    return cand if cand_score > cur_score else cur

def _build_preview_content_map(rows: List[Any], *, skills_root: str) -> Dict[str, Dict[str, Any]]:
    out: Dict[str, Dict[str, Any]] = {}

    for obj in _iter_tree_rows(rows):
        rel_path = _entry_path_under_skills_root(obj, skills_root=skills_root)
        if not rel_path:
            continue

        text = _entry_text(obj)
        if not text:
            continue

        normalized_rel = _normalize_logical_path(rel_path)
        source_kind = _safe_str(
            _safe_dict(obj).get("content_source_kind")
            or _safe_dict(obj).get("preview_source_kind")
            or _safe_dict(obj).get("source_kind"),
            "preview",
        ).lower()

        record = {
            "text": text,
            "source_kind": source_kind,
            "relative_path": normalized_rel,
            "origin_path": _normalize_logical_path(
                _safe_dict(obj).get("path")
                or _safe_dict(obj).get("relative_path")
                or _safe_dict(obj).get("filename")
            ),
        }

        candidate_keys = [
            normalized_rel,
            _strip_md_suffix(normalized_rel),
            _basename(normalized_rel),
            _strip_md_suffix(_basename(normalized_rel)),
        ]

        for key in candidate_keys:
            normalized_key = _normalize_logical_path(key)
            if not normalized_key:
                continue
            out[normalized_key] = _prefer_content_record(out.get(normalized_key), record)

    return out

def _build_skill_items(
    entries: List[Any],
    previews: List[Any],
    *,
    skills_root: str,
    enabled_skill_ids: Set[str],
) -> List[Dict[str, Any]]:
    preview_titles = _build_preview_title_map(previews, skills_root=skills_root)
    out: List[Dict[str, Any]] = []
    seen = set()

    for row in _iter_tree_rows(entries):
        if not row or _entry_is_dir(row):
            continue

        rel_path = _entry_path_under_skills_root(row, skills_root=skills_root)
        if not rel_path or not rel_path.lower().endswith(".md"):
            continue

        normalized_rel = _normalize_logical_path(rel_path)
        if not normalized_rel or normalized_rel in seen:
            continue
        seen.add(normalized_rel)

        filename = _basename(normalized_rel)
        skill_name = _basename(_strip_md_suffix(normalized_rel))
        skill_id = _strip_md_suffix(normalized_rel)

        fallback_title = skill_name or filename or normalized_rel
        title = (
            preview_titles.get(normalized_rel)
            or _extract_markdown_title(_entry_text(row), fallback_title)
            or fallback_title
        )

        out.append(
            {
                "skill_id": skill_id,
                "name": skill_name or _strip_md_suffix(filename),
                "filename": filename,
                "relative_path": _join_path(_SKILLS_DIRNAME, normalized_rel),
                "title": title,
                "enabled_by_room": skill_id in enabled_skill_ids,
                "size": _entry_size(row),
                "updated_at": _entry_updated_at(row),
            }
        )

    out.sort(
        key=lambda item: (
            _safe_str(item.get("relative_path")).lower(),
            _safe_str(item.get("title")).lower(),
        )
    )
    return out


def _empty_result(
    *,
    room_id: str,
    request_id: str,
    boundary: Dict[str, Any],
    status: str,
    reason_code: str,
    message: str,
) -> Dict[str, Any]:
    effective_focus_root = _normalize_logical_path(boundary.get("effective_focus_root"))
    return {
        "success": True,
        "enabled": False,
        "status": _safe_str(status),
        "message": _safe_str(message),
        "reason_code": _safe_str(reason_code),
        "room_id": _safe_str(room_id),
        "request_id": _safe_str(request_id),
        "workspace_id": _safe_str(boundary.get("workspace_id")),
        "workspace_name": _safe_str(boundary.get("workspace_name")),
        "focus_root": effective_focus_root,
        "skills_root": _join_path(effective_focus_root, _SKILLS_DIRNAME),
        "skills_root_relative": _SKILLS_DIRNAME,
        "strategy": "builtin_plus_custom",
        "supervisor_skill_strategy": "builtin_plus_custom",
        "builtin_skill_ids": [],
        "custom_skill_ids": [],
        "enabled_skill_ids": [],
        "applied_skill_ids": [],
        "applied_prompt_skill_ids": [],
        "applied_builtin_skill_ids": [],
        "applied_custom_skill_ids": [],
        "items_count": 0,
        "items": [],
        "resolved_items": [],
        "step_rows": [],
        "tool_calls": [],
        "tool_results": [],
        "boundary": boundary,
        "recorded_at": utc_iso(),
    }


def _truncate_text(value: Any, limit: int) -> str:
    raw = _safe_str(value)
    if not raw or limit <= 0:
        return ""
    if len(raw) <= limit:
        return raw
    clipped = raw[: max(0, limit - 16)].rstrip()
    if not clipped:
        return ""
    return f"{clipped}\n\n[truncated]"


def _append_unique(values: List[str], seen: Set[str], candidate: Any) -> None:
    normalized = _normalize_logical_path(candidate)
    if not normalized or normalized in seen:
        return
    seen.add(normalized)
    values.append(normalized)


def _candidate_content_keys(*, skill_id: str, relative_path: str, skills_root: str) -> List[str]:
    out: List[str] = []
    seen: Set[str] = set()

    normalized_skill_id = _strip_md_suffix(skill_id)
    normalized_relative_path = _normalize_logical_path(relative_path)
    relative_under_root = _strip_skills_root_prefix(normalized_relative_path, skills_root=skills_root)
    skill_md = f"{normalized_skill_id}.md" if normalized_skill_id else ""

    for candidate in (
        skill_md,
        normalized_skill_id,
        relative_under_root,
        _strip_md_suffix(relative_under_root),
        normalized_relative_path,
        _strip_md_suffix(normalized_relative_path),
        _join_path(_SKILLS_DIRNAME, relative_under_root),
        _join_path(skills_root, relative_under_root),
        _basename(relative_under_root),
        _strip_md_suffix(_basename(relative_under_root)),
        _basename(normalized_relative_path),
        _strip_md_suffix(_basename(normalized_relative_path)),
    ):
        _append_unique(out, seen, candidate)

    return out

def _resolve_skill_raw_content(
    *,
    content_map: Dict[str, Dict[str, Any]],
    skill_id: str,
    relative_path: str,
    skills_root: str,
) -> Dict[str, Any]:
    for key in _candidate_content_keys(
        skill_id=skill_id,
        relative_path=relative_path,
        skills_root=skills_root,
    ):
        record = _safe_dict(content_map.get(key))
        text = _safe_str(record.get("text"))
        if text:
            return {
                "text": text,
                "matched_key": key,
                "source_kind": _safe_str(record.get("source_kind")),
                "relative_path": _safe_str(record.get("relative_path")),
            }

    target_md = _normalize_logical_path(f"{_strip_md_suffix(skill_id)}.md")
    target_base = _basename(target_md)

    for key, record_value in content_map.items():
        record = _safe_dict(record_value)
        text = _safe_str(record.get("text"))
        if not text:
            continue

        normalized_key = _normalize_logical_path(key)
        if not normalized_key:
            continue

        if normalized_key == target_md:
            return {
                "text": text,
                "matched_key": normalized_key,
                "source_kind": _safe_str(record.get("source_kind"), "fallback"),
                "relative_path": _safe_str(record.get("relative_path")),
            }
        if target_md and normalized_key.endswith("/" + target_md):
            return {
                "text": text,
                "matched_key": normalized_key,
                "source_kind": _safe_str(record.get("source_kind"), "fallback"),
                "relative_path": _safe_str(record.get("relative_path")),
            }
        if target_base and _basename(normalized_key) == target_base:
            return {
                "text": text,
                "matched_key": normalized_key,
                "source_kind": _safe_str(record.get("source_kind"), "fallback"),
                "relative_path": _safe_str(record.get("relative_path")),
            }

    return {
        "text": "",
        "matched_key": "",
        "source_kind": "",
        "relative_path": "",
    }

def _resolve_skill_raw_text(
    *,
    content_map: Dict[str, Dict[str, Any]],
    skill_id: str,
    relative_path: str,
    skills_root: str,
) -> str:
    resolved = _resolve_skill_raw_content(
        content_map=content_map,
        skill_id=skill_id,
        relative_path=relative_path,
        skills_root=skills_root,
    )
    return _safe_str(resolved.get("text"))


def _make_supervisor_skill_step_row(
    *,
    item: Dict[str, Any] | None = None,
    skill_id: Any = "",
    enabled_skill_ids: Set[str] | None = None,
    status: str = "",
    message: str = "",
    source: str = "custom",
    content_chars: int = 0,
    prompt_chars: int = 0,
    truncated: bool = False,
) -> Dict[str, Any]:
    row = _safe_dict(item)
    normalized_skill_id = _safe_str(row.get("skill_id") or skill_id)
    enabled_ids = enabled_skill_ids or set()

    return {
        "skill_id": normalized_skill_id,
        "title": _safe_str(row.get("title") or row.get("name") or normalized_skill_id, normalized_skill_id),
        "relative_path": _safe_str(row.get("relative_path")),
        "enabled_by_room": normalized_skill_id in enabled_ids,
        "source": _safe_str(source, "custom"),
        "status": _safe_str(status),
        "message": _safe_str(message),
        "content_chars": int(content_chars or 0),
        "prompt_chars": int(prompt_chars or 0),
        "truncated": bool(truncated),
    }


def build_supervisor_skills_payload(skills_info: Dict[str, Any]) -> Dict[str, Any]:
    info = _safe_dict(skills_info)
    resolved_items = [
        row for row in _safe_list(info.get("resolved_items"))
        if isinstance(row, dict)
    ]
    step_rows = [
        row for row in _safe_list(info.get("step_rows"))
        if isinstance(row, dict)
    ]
    applied_prompt_skill_ids = _safe_list(
        info.get("applied_prompt_skill_ids") or info.get("applied_skill_ids")
    )

    return {
        "strategy": _safe_str(
            info.get("strategy") or info.get("supervisor_skill_strategy"),
            "builtin_plus_custom",
        ),
        "status": _safe_str(info.get("status"), "disabled"),
        "message": _safe_str(info.get("message")),
        "workspace_id": _safe_str(info.get("workspace_id")),
        "workspace_name": _safe_str(info.get("workspace_name")),
        "focus_root": _safe_str(info.get("focus_root")),
        "skills_root": _safe_str(info.get("skills_root")),
        "enabled_skill_ids": _safe_list(info.get("enabled_skill_ids")),
        "applied_skill_ids": list(applied_prompt_skill_ids),
        "applied_prompt_skill_ids": list(applied_prompt_skill_ids),
        "builtin_skill_ids": _safe_list(info.get("builtin_skill_ids")),
        "custom_skill_ids": _safe_list(info.get("custom_skill_ids")),
        "applied_builtin_skill_ids": _safe_list(info.get("applied_builtin_skill_ids")),
        "applied_custom_skill_ids": _safe_list(info.get("applied_custom_skill_ids")),
        "items": _safe_list(info.get("items")),
        "resolved_items_count": len(resolved_items),
        "resolved_items": resolved_items,
        "step_count": len(step_rows),
        "step_rows": step_rows,
        "prompt_block_chars": len(_safe_str(info.get("prompt_block"))),
    }

def build_enabled_supervisor_skills_prompt_block(
    *,
    room_id: str,
    state: Dict[str, Any] | None = None,
    request_args: Dict[str, Any] | None = None,
    enabled_skill_ids: List[str] | None = None,
    strategy: str = "builtin_plus_custom",
    max_chars_per_skill: int = _MAX_SUPERVISOR_SKILL_CHARS,
    max_total_chars: int = _MAX_SUPERVISOR_SKILLS_TOTAL_CHARS,
) -> Dict[str, Any]:
    room_state = _safe_dict(state) or _safe_dict(load_state_doc(_safe_str(room_id)))
    normalized_enabled_ids = _normalize_enabled_supervisor_skill_ids(
        enabled_skill_ids if enabled_skill_ids is not None else room_state.get("enabled_supervisor_skill_ids")
    )
    normalized_enabled_set = set(normalized_enabled_ids)
    normalized_strategy = _normalize_supervisor_skill_strategy(
        strategy or room_state.get("supervisor_skill_strategy"),
        "builtin_plus_custom",
    )

    result: Dict[str, Any] = {
        "status": "disabled",
        "message": "no enabled supervisor skills",
        "room_id": _safe_str(room_id),
        "workspace_id": "",
        "workspace_name": "",
        "focus_root": "",
        "skills_root": "",
        "strategy": normalized_strategy,
        "supervisor_skill_strategy": normalized_strategy,
        "builtin_skill_ids": [],
        "custom_skill_ids": [],
        "enabled_skill_ids": list(normalized_enabled_ids),
        "applied_skill_ids": [],
        "applied_prompt_skill_ids": [],
        "applied_builtin_skill_ids": [],
        "applied_custom_skill_ids": [],
        "resolved_items": [],
        "items": [],
        "step_rows": [],
        "prompt_block": "",
        "tool_calls": [],
        "tool_results": [],
        "recorded_at": utc_iso(),
    }

    if normalized_strategy != "builtin_only" and not normalized_enabled_ids:
        return result

    if normalized_strategy == "builtin_only" and not normalized_enabled_ids:
        result["status"] = "success"
        result["message"] = "builtin_only; workspace custom skills not applied"
        return result

    boundary = resolve_room_supervisor_fs_boundary(
        room_id=room_id,
        request_args=_safe_dict(request_args),
        mode="read",
        require_focus_root=True,
    )
    effective_focus_root = _normalize_logical_path(boundary.get("effective_focus_root"))
    resolved_skills_root = _join_path(effective_focus_root, _SKILLS_DIRNAME)

    result["workspace_id"] = _safe_str(boundary.get("workspace_id"))
    result["workspace_name"] = _safe_str(boundary.get("workspace_name"))
    result["focus_root"] = effective_focus_root
    result["skills_root"] = resolved_skills_root

    if not _safe_bool(boundary.get("allowed")):
        result["status"] = _safe_str(boundary.get("status"), "denied")
        result["message"] = _safe_str(boundary.get("message")) or "room workspace boundary denied"
        return result

    probe_args = dict(_safe_dict(request_args))
    probe_args["workspace_id"] = _safe_str(boundary.get("workspace_id"))
    probe_args["workspace_name"] = _safe_str(boundary.get("workspace_name"))
    probe_args["focus_root"] = effective_focus_root
    probe_args["focused_root_path"] = effective_focus_root

    probe_result = room_supervisor_skills_probe(
        room_id=room_id,
        request_args=probe_args,
        skills_dirname=_SKILLS_DIRNAME,
        run_id="",
        supervisor_event_id="",
        final_event_id="",
    )

    result["tool_calls"] = _safe_list(probe_result.get("tool_calls"))
    result["tool_results"] = _safe_list(probe_result.get("tool_results"))

    status = _safe_str(probe_result.get("status"), "success")
    reason_code = _safe_str(probe_result.get("reason_code"))
    message = _safe_str(probe_result.get("message"))

    if reason_code in _MISSING_REASON_CODES or "not found" in message.lower():
        step_rows: List[Dict[str, Any]] = []
        for skill_id in normalized_enabled_ids:
            step_rows.append(
                _make_supervisor_skill_step_row(
                    skill_id=skill_id,
                    enabled_skill_ids=normalized_enabled_set,
                    status="missing",
                    message="enabled skill not found under current workspace boundary",
                )
            )
        result["step_rows"] = step_rows
        result["status"] = "success"
        result["message"] = (
            "builtin_only; workspace custom skills not applied"
            if normalized_strategy == "builtin_only"
            else "skills directory not found; treated as empty"
        )
        return result

    if status not in {"success", "ok"}:
        result["status"] = status or "error"
        result["message"] = message or "failed to probe skills directory"
        return result

    entries = _safe_list(probe_result.get("entries"))
    previews = _safe_list(probe_result.get("previews"))

    resolved_items = _build_skill_items(
        entries,
        previews,
        skills_root=resolved_skills_root,
        enabled_skill_ids=normalized_enabled_set,
    )
    result["resolved_items"] = resolved_items

    item_map = {
        _safe_str(item.get("skill_id")): item
        for item in resolved_items
        if _safe_str(item.get("skill_id"))
    }
    result["custom_skill_ids"] = list(item_map.keys())

    content_map = _build_preview_content_map(previews, skills_root=resolved_skills_root)
    entry_content_map = _build_preview_content_map(entries, skills_root=resolved_skills_root)
    for key, value in entry_content_map.items():
        content_map[key] = _prefer_content_record(content_map.get(key), value)

    step_rows: List[Dict[str, Any]] = []
    step_row_map: Dict[str, Dict[str, Any]] = {}

    for item in resolved_items:
        skill_id = _safe_str(item.get("skill_id"))
        row = _make_supervisor_skill_step_row(
            item=item,
            enabled_skill_ids=normalized_enabled_set,
            status="available_not_enabled" if skill_id not in normalized_enabled_set else "pending",
            message="" if skill_id not in normalized_enabled_set else "enabled skill pending prompt resolution",
        )
        step_rows.append(row)
        if skill_id:
            step_row_map[skill_id] = row

    if normalized_strategy == "builtin_only":
        item_rows: List[Dict[str, Any]] = []
        for row in step_rows:
            row["status"] = "available_ignored_by_strategy"
            row["message"] = "workspace custom skills disabled by builtin_only strategy"

        for skill_id in normalized_enabled_ids:
            item = _safe_dict(item_map.get(skill_id))
            title = _safe_str(item.get("title") or item.get("name") or skill_id, skill_id)
            relative_path = _safe_str(item.get("relative_path"))

            if skill_id not in step_row_map:
                step_rows.append(
                    _make_supervisor_skill_step_row(
                        skill_id=skill_id,
                        enabled_skill_ids=normalized_enabled_set,
                        status="skipped_strategy",
                        message="workspace custom skills disabled by builtin_only strategy",
                    )
                )

            item_rows.append(
                {
                    "skill_id": skill_id,
                    "title": title,
                    "relative_path": relative_path,
                    "status": "skipped_strategy",
                    "message": "workspace custom skills disabled by builtin_only strategy",
                    "content_chars": 0,
                    "prompt_chars": 0,
                }
            )

        result["items"] = item_rows
        result["step_rows"] = step_rows
        result["status"] = "success"
        result["message"] = "builtin_only; workspace custom skills not applied"
        return result

    applied_skill_ids: List[str] = []
    prompt_parts: List[str] = []
    item_rows: List[Dict[str, Any]] = []
    remaining_total = max(0, int(max_total_chars or 0))

    for skill_id in normalized_enabled_ids:
        item = _safe_dict(item_map.get(skill_id))
        step_row = step_row_map.get(skill_id)

        if not item:
            missing_row = _make_supervisor_skill_step_row(
                skill_id=skill_id,
                enabled_skill_ids=normalized_enabled_set,
                status="missing",
                message="enabled skill not found under current workspace boundary",
            )
            step_rows.append(missing_row)
            item_rows.append(
                {
                    "skill_id": skill_id,
                    "status": "missing",
                    "message": "enabled skill not found under current workspace boundary",
                }
            )
            continue

        relative_path = _safe_str(item.get("relative_path"))
        title = _safe_str(item.get("title") or item.get("name") or skill_id, skill_id)

        resolved_content = _resolve_skill_raw_content(
            content_map=content_map,
            skill_id=skill_id,
            relative_path=relative_path,
            skills_root=resolved_skills_root,
        )
        raw_text = _safe_str(resolved_content.get("text"))
        resolved_source_kind = _safe_str(resolved_content.get("source_kind"))
        resolved_content_key = _safe_str(resolved_content.get("matched_key"))
        resolved_content_preview = raw_text[:120]

        if not raw_text:
            if step_row is not None:
                step_row["status"] = "missing_content"
                step_row["message"] = "skill markdown content unavailable"
                step_row["resolved_source_kind"] = resolved_source_kind
                step_row["resolved_content_key"] = resolved_content_key
                step_row["resolved_content_preview"] = resolved_content_preview

            item_rows.append(
                {
                    "skill_id": skill_id,
                    "title": title,
                    "relative_path": relative_path,
                    "status": "missing_content",
                    "message": "skill markdown content unavailable",
                }
            )
            continue

        local_limit = min(max(1, int(max_chars_per_skill or 1)), remaining_total) if remaining_total > 0 else 0
        if local_limit <= 0:
            if step_row is not None:
                step_row["status"] = "skipped_budget"
                step_row["message"] = "prompt budget exhausted"
                step_row["content_chars"] = len(raw_text)
                step_row["prompt_chars"] = 0
                step_row["resolved_source_kind"] = resolved_source_kind
                step_row["resolved_content_key"] = resolved_content_key
                step_row["resolved_content_preview"] = resolved_content_preview

            item_rows.append(
                {
                    "skill_id": skill_id,
                    "title": title,
                    "relative_path": relative_path,
                    "status": "skipped_budget",
                    "message": "prompt budget exhausted",
                    "content_chars": len(raw_text),
                    "prompt_chars": 0,
                }
            )
            continue

        prompt_text = _truncate_text(raw_text, local_limit)
        if not prompt_text:
            if step_row is not None:
                step_row["status"] = "skipped_empty"
                step_row["message"] = "skill content empty after normalization"
                step_row["content_chars"] = len(raw_text)
                step_row["prompt_chars"] = 0
                step_row["resolved_source_kind"] = resolved_source_kind
                step_row["resolved_content_key"] = resolved_content_key
                step_row["resolved_content_preview"] = resolved_content_preview

            item_rows.append(
                {
                    "skill_id": skill_id,
                    "title": title,
                    "relative_path": relative_path,
                    "status": "skipped_empty",
                    "message": "skill content empty after normalization",
                    "content_chars": len(raw_text),
                    "prompt_chars": 0,
                }
            )
            continue

        prompt_piece = "\n".join(
            [
                f"### {title}",
                f"- skill_id: {skill_id}",
                f"- relative_path: {relative_path}",
                "",
                prompt_text,
            ]
        ).strip()

        piece_len = len(prompt_piece)
        if piece_len > remaining_total and remaining_total > 0:
            prompt_text = _truncate_text(raw_text, max(1, remaining_total - 120))
            prompt_piece = "\n".join(
                [
                    f"### {title}",
                    f"- skill_id: {skill_id}",
                    f"- relative_path: {relative_path}",
                    "",
                    prompt_text,
                ]
            ).strip()
            piece_len = len(prompt_piece)

        if not prompt_piece or piece_len <= 0 or piece_len > remaining_total:
            if step_row is not None:
                step_row["status"] = "skipped_budget"
                step_row["message"] = "prompt budget exhausted"
                step_row["content_chars"] = len(raw_text)
                step_row["prompt_chars"] = 0
                step_row["resolved_source_kind"] = resolved_source_kind
                step_row["resolved_content_key"] = resolved_content_key
                step_row["resolved_content_preview"] = resolved_content_preview

            item_rows.append(
                {
                    "skill_id": skill_id,
                    "title": title,
                    "relative_path": relative_path,
                    "status": "skipped_budget",
                    "message": "prompt budget exhausted",
                    "content_chars": len(raw_text),
                    "prompt_chars": 0,
                }
            )
            continue

        prompt_parts.append(prompt_piece)
        applied_skill_ids.append(skill_id)
        remaining_total = max(0, remaining_total - piece_len)

        truncated = len(prompt_text) < len(raw_text)
        if step_row is not None:
            step_row["status"] = "applied_prompt"
            step_row["message"] = "skill content appended to supervisor prompt"
            step_row["content_chars"] = len(raw_text)
            step_row["prompt_chars"] = piece_len
            step_row["truncated"] = truncated
            step_row["resolved_source_kind"] = resolved_source_kind
            step_row["resolved_content_key"] = resolved_content_key
            step_row["resolved_content_preview"] = resolved_content_preview

        item_rows.append(
            {
                "skill_id": skill_id,
                "title": title,
                "relative_path": relative_path,
                "status": "applied",
                "content_chars": len(raw_text),
                "prompt_chars": piece_len,
                "truncated": truncated,
            }
        )

    result["items"] = item_rows
    result["step_rows"] = step_rows
    result["applied_skill_ids"] = list(applied_skill_ids)
    result["applied_prompt_skill_ids"] = list(applied_skill_ids)
    result["applied_custom_skill_ids"] = list(applied_skill_ids)
    result["applied_builtin_skill_ids"] = []
    result["prompt_block"] = "\n\n".join(prompt_parts).strip()

    if applied_skill_ids:
        result["status"] = "success"
        result["message"] = "ok"
    elif normalized_enabled_ids:
        result["status"] = "success"
        result["message"] = "no enabled skills resolved to prompt content"
    else:
        result["status"] = "disabled"
        result["message"] = "no enabled supervisor skills"

    return result

def append_supervisor_skills_prompt_block(
    base_prompt: str,
    skills_info: Dict[str, Any],
    *,
    heading: str = "Workspace supervisor skills",
) -> str:
    prompt = _safe_str(base_prompt)
    block = _safe_str(_safe_dict(skills_info).get("prompt_block"))
    if not block:
        return prompt
    suffix = f"{heading}:\n{block}".strip()
    if not prompt:
        return suffix
    return f"{prompt.rstrip()}\n\n{suffix}\n".strip()


def build_supervisor_skills_tool_result(skills_info: Dict[str, Any]) -> Dict[str, Any]:
    info = _safe_dict(skills_info)
    payload = build_supervisor_skills_payload(info)

    return {
        "type": "supervisor_skills",
        "status": _safe_str(payload.get("status"), "disabled"),
        "message": _safe_str(payload.get("message")),
        "strategy": _safe_str(payload.get("strategy"), "builtin_plus_custom"),
        "workspace_id": _safe_str(payload.get("workspace_id")),
        "workspace_name": _safe_str(payload.get("workspace_name")),
        "focus_root": _safe_str(payload.get("focus_root")),
        "skills_root": _safe_str(payload.get("skills_root")),
        "builtin_skill_ids": _safe_list(payload.get("builtin_skill_ids")),
        "custom_skill_ids": _safe_list(payload.get("custom_skill_ids")),
        "enabled_skill_ids": _safe_list(payload.get("enabled_skill_ids")),
        "applied_skill_ids": _safe_list(payload.get("applied_skill_ids")),
        "applied_prompt_skill_ids": _safe_list(payload.get("applied_prompt_skill_ids")),
        "applied_builtin_skill_ids": _safe_list(payload.get("applied_builtin_skill_ids")),
        "applied_custom_skill_ids": _safe_list(payload.get("applied_custom_skill_ids")),
        "items": _safe_list(payload.get("items")),
        "resolved_items_count": int(payload.get("resolved_items_count") or 0),
        "resolved_items": _safe_list(payload.get("resolved_items")),
        "step_count": int(payload.get("step_count") or 0),
        "step_rows": _safe_list(payload.get("step_rows")),
        "prompt_block_chars": int(payload.get("prompt_block_chars") or 0),
    }


def nisb_room_supervisor_skills_list(args: Dict[str, Any]) -> Dict[str, Any]:
    basepath = get_basepath(args)
    uid = uid_from_ctx_or_basepath(basepath, args)
    request_id = ensure_request_id(args)

    room_id = require_safe_id("room_id", args.get("room_id"))
    meta = ensure_room_exists(room_id)
    if meta and not is_participant(uid, meta):
        return {"success": False, "message": "permission denied", "request_id": request_id}

    room_state = load_state_doc(room_id)
    enabled_skill_ids = set(
        _normalize_enabled_supervisor_skill_ids(room_state.get("enabled_supervisor_skill_ids"))
    )
    enabled_skill_ids_list = list(enabled_skill_ids)
    skill_strategy = _normalize_supervisor_skill_strategy(
        room_state.get("supervisor_skill_strategy"),
        "builtin_plus_custom",
    )

    boundary = resolve_room_supervisor_fs_boundary(
        room_id=room_id,
        request_args=args,
        mode="read",
        require_focus_root=True,
    )

    if not _safe_bool(boundary.get("allowed")):
        result = _empty_result(
            room_id=room_id,
            request_id=request_id,
            boundary=boundary,
            status=_safe_str(boundary.get("status"), "denied"),
            reason_code=_safe_str(boundary.get("reason_code")),
            message=_safe_str(boundary.get("message")) or "room workspace boundary denied",
        )
        result["strategy"] = skill_strategy
        result["supervisor_skill_strategy"] = skill_strategy
        payload = build_supervisor_skills_payload(result)
        result.update(
            {
                "applied_prompt_skill_ids": _safe_list(payload.get("applied_prompt_skill_ids")),
                "resolved_items_count": int(payload.get("resolved_items_count") or 0),
                "resolved_items": _safe_list(payload.get("resolved_items")),
                "step_count": int(payload.get("step_count") or 0),
                "step_rows": _safe_list(payload.get("step_rows")),
                "prompt_block_chars": int(payload.get("prompt_block_chars") or 0),
            }
        )
        return result

    effective_focus_root = _normalize_logical_path(boundary.get("effective_focus_root"))
    resolved_skills_root = _join_path(effective_focus_root, _SKILLS_DIRNAME)

    probe_args = dict(args or {})
    probe_args["workspace_id"] = _safe_str(boundary.get("workspace_id"))
    probe_args["workspace_name"] = _safe_str(boundary.get("workspace_name"))
    probe_args["focus_root"] = effective_focus_root
    probe_args["focused_root_path"] = effective_focus_root

    probe_result = room_supervisor_skills_probe(
        room_id=room_id,
        request_args=probe_args,
        skills_dirname=_SKILLS_DIRNAME,
        run_id="",
        supervisor_event_id="",
        final_event_id="",
    )

    status = _safe_str(probe_result.get("status"), "success")
    reason_code = _safe_str(probe_result.get("reason_code"))
    message = _safe_str(probe_result.get("message"))

    if reason_code in _MISSING_REASON_CODES or "not found" in message.lower():
        result = {
            "success": True,
            "enabled": True,
            "status": "success",
            "message": (
                "builtin_only; workspace custom skills not applied"
                if skill_strategy == "builtin_only"
                else "skills directory not found; treated as empty"
            ),
            "reason_code": "",
            "room_id": room_id,
            "request_id": request_id,
            "workspace_id": _safe_str(boundary.get("workspace_id")),
            "workspace_name": _safe_str(boundary.get("workspace_name")),
            "focus_root": effective_focus_root,
            "skills_root": resolved_skills_root,
            "skills_root_relative": _SKILLS_DIRNAME,
            "strategy": skill_strategy,
            "supervisor_skill_strategy": skill_strategy,
            "builtin_skill_ids": [],
            "custom_skill_ids": [],
            "enabled_skill_ids": enabled_skill_ids_list,
            "applied_skill_ids": [],
            "applied_prompt_skill_ids": [],
            "applied_builtin_skill_ids": [],
            "applied_custom_skill_ids": [],
            "items_count": 0,
            "items": [],
            "resolved_items": [],
            "step_rows": [
                _make_supervisor_skill_step_row(
                    skill_id=skill_id,
                    enabled_skill_ids=enabled_skill_ids,
                    status="missing",
                    message="enabled skill not found under current workspace boundary",
                )
                for skill_id in enabled_skill_ids_list
            ],
            "tool_calls": _safe_list(probe_result.get("tool_calls")),
            "tool_results": _safe_list(probe_result.get("tool_results")),
            "boundary": boundary,
            "recorded_at": utc_iso(),
        }
        payload = build_supervisor_skills_payload(result)
        result.update(
            {
                "resolved_items_count": int(payload.get("resolved_items_count") or 0),
                "step_count": int(payload.get("step_count") or 0),
                "prompt_block_chars": int(payload.get("prompt_block_chars") or 0),
            }
        )
        return result

    if status not in {"success", "ok"}:
        result = {
            "success": True,
            "enabled": False,
            "status": status or "error",
            "message": message or "failed to probe skills directory",
            "reason_code": reason_code,
            "room_id": room_id,
            "request_id": request_id,
            "workspace_id": _safe_str(boundary.get("workspace_id")),
            "workspace_name": _safe_str(boundary.get("workspace_name")),
            "focus_root": effective_focus_root,
            "skills_root": resolved_skills_root,
            "skills_root_relative": _SKILLS_DIRNAME,
            "strategy": skill_strategy,
            "supervisor_skill_strategy": skill_strategy,
            "builtin_skill_ids": [],
            "custom_skill_ids": [],
            "enabled_skill_ids": enabled_skill_ids_list,
            "applied_skill_ids": [],
            "applied_prompt_skill_ids": [],
            "applied_builtin_skill_ids": [],
            "applied_custom_skill_ids": [],
            "items_count": 0,
            "items": [],
            "resolved_items": [],
            "step_rows": [],
            "tool_calls": _safe_list(probe_result.get("tool_calls")),
            "tool_results": _safe_list(probe_result.get("tool_results")),
            "boundary": boundary,
            "recorded_at": utc_iso(),
        }
        payload = build_supervisor_skills_payload(result)
        result.update(
            {
                "resolved_items_count": int(payload.get("resolved_items_count") or 0),
                "step_count": int(payload.get("step_count") or 0),
                "prompt_block_chars": int(payload.get("prompt_block_chars") or 0),
            }
        )
        return result

    items = _build_skill_items(
        _safe_list(probe_result.get("entries")),
        _safe_list(probe_result.get("previews")),
        skills_root=resolved_skills_root,
        enabled_skill_ids=enabled_skill_ids,
    )

    step_rows = [
        _make_supervisor_skill_step_row(
            item=item,
            enabled_skill_ids=enabled_skill_ids,
            status="available_enabled" if _safe_str(item.get("skill_id")) in enabled_skill_ids else "available_not_enabled",
            message="" if _safe_str(item.get("skill_id")) not in enabled_skill_ids else "enabled by room",
        )
        for item in items
    ]

    result = {
        "success": True,
        "enabled": True,
        "status": "success",
        "message": "ok",
        "reason_code": "",
        "room_id": room_id,
        "request_id": request_id,
        "workspace_id": _safe_str(boundary.get("workspace_id")),
        "workspace_name": _safe_str(boundary.get("workspace_name")),
        "focus_root": effective_focus_root,
        "skills_root": resolved_skills_root,
        "skills_root_relative": _SKILLS_DIRNAME,
        "strategy": skill_strategy,
        "supervisor_skill_strategy": skill_strategy,
        "builtin_skill_ids": [],
        "custom_skill_ids": [_safe_str(item.get("skill_id")) for item in items if _safe_str(item.get("skill_id"))],
        "enabled_skill_ids": enabled_skill_ids_list,
        "applied_skill_ids": [],
        "applied_prompt_skill_ids": [],
        "applied_builtin_skill_ids": [],
        "applied_custom_skill_ids": [],
        "items_count": len(items),
        "items": items,
        "resolved_items": items,
        "step_rows": step_rows,
        "tool_calls": _safe_list(probe_result.get("tool_calls")),
        "tool_results": _safe_list(probe_result.get("tool_results")),
        "boundary": boundary,
        "recorded_at": utc_iso(),
    }

    payload = build_supervisor_skills_payload(result)
    result.update(
        {
            "applied_prompt_skill_ids": _safe_list(payload.get("applied_prompt_skill_ids")),
            "resolved_items_count": int(payload.get("resolved_items_count") or 0),
            "resolved_items": _safe_list(payload.get("resolved_items")),
            "step_count": int(payload.get("step_count") or 0),
            "step_rows": _safe_list(payload.get("step_rows")),
            "prompt_block_chars": int(payload.get("prompt_block_chars") or 0),
        }
    )
    return result

__all__ = [
    "append_supervisor_skills_prompt_block",
    "build_enabled_supervisor_skills_prompt_block",
    "build_supervisor_skills_payload",
    "build_supervisor_skills_tool_result",
    "nisb_room_supervisor_skills_list",
]

