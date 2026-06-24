from __future__ import annotations

from typing import Any, Dict, List, Optional

from .room_contracts import as_bool, utc_iso
from .room_state_normalizer import _normalize_supervisor_skill_strategy
from .supervisor_runtime.memory_resume import normalize_memory_filename
from .room_supervisor_runtime_status import (
    _normalize_filename,
    _normalize_fs_read_scope,
    _normalize_rel_path,
    _pick_recorded_at,
    _safe_dict,
    _safe_list,
    _safe_str,
    _build_runtime_control_snapshot,
)


def _normalize_room_mcp_overrides(value: Any) -> Dict[str, Any]:
    src = _safe_dict(value)
    notebook_write_enabled = as_bool(src.get("notebook_write_enabled"), False)
    return {
        "fs_read_enabled": as_bool(src.get("fs_read_enabled"), False),
        "fs_read_scope": _normalize_fs_read_scope(src.get("fs_read_scope"), "minimal"),
        "notebook_write_enabled": notebook_write_enabled,
        "notebook_dir": _normalize_rel_path(src.get("notebook_dir")) or "_room_supervisor_notebooks",
        "notebook_filename": _normalize_filename(src.get("notebook_filename"), "supervisor.md"),
        "notebook_title": _safe_str(src.get("notebook_title"), "Supervisor notebook"),
        "notebook_section_title": _safe_str(src.get("notebook_section_title"), "latest"),
        "memory_filename": normalize_memory_filename(
            src.get("memory_filename"),
            "supervisor.memory.json",
        ),
        "memory_write_enabled": as_bool(
            src.get("memory_write_enabled"),
            notebook_write_enabled,
        ),
    }


def _build_room_actor_context(
    *,
    actor_type: str = "supervisor",
    actor_id: str = "supervisor",
    skill_id: str = "",
    delegated_from: str = "",
) -> Dict[str, Any]:
    return {
        "actor_type": _safe_str(actor_type, "supervisor"),
        "actor_id": _safe_str(actor_id, "supervisor"),
        "skill_id": _safe_str(skill_id),
        "delegated_from": _safe_str(delegated_from),
    }


def _build_supervisor_runtime_request_args(
    state: Optional[Dict[str, Any]] = None,
    request_args: Optional[Dict[str, Any]] = None,
    *,
    room_state: Optional[Dict[str, Any]] = None,
    **_: Any,
) -> Dict[str, Any]:
    src_state = _safe_dict(state or room_state)
    base = dict(_safe_dict(request_args))
    capability_gate = dict(_safe_dict(base.get("capability_gate")))
    room_workspace_context = dict(_safe_dict(base.get("room_workspace_context")))
    room_supervisor_context = dict(_safe_dict(base.get("room_supervisor_context")))

    inherit_workspace_context = as_bool(src_state.get("inherit_workspace_context"), True)
    inherit_focus_root = as_bool(
        src_state.get("inherit_focus_root"),
        bool(_safe_str(src_state.get("focus_root"))),
    )

    workspace_id = _safe_str(src_state.get("workspace_id"))
    workspace_name = _safe_str(src_state.get("workspace_name"))
    focus_root = _normalize_rel_path(src_state.get("focus_root"))
    focus_label = _safe_str(src_state.get("focus_label"))
    supervisor_provider = _safe_str(src_state.get("supervisor_provider"))
    supervisor_model = _safe_str(src_state.get("supervisor_model"))
    supervisor_skill_strategy = _normalize_supervisor_skill_strategy(
        src_state.get("supervisor_skill_strategy"),
        "builtin_plus_custom",
    )

    normalized_state_mcp = _normalize_room_mcp_overrides(src_state.get("mcp_overrides"))
    merged_mcp = dict(normalized_state_mcp)
    merged_mcp.update(_safe_dict(base.get("mcp_overrides")))
    mcp_overrides = _normalize_room_mcp_overrides(merged_mcp)

    base.setdefault("inherit_workspace_context", inherit_workspace_context)
    base.setdefault("inherit_focus_root", inherit_focus_root)

    base["supervisor_skill_strategy"] = supervisor_skill_strategy
    base["supervisor_skills_strategy"] = supervisor_skill_strategy

    if inherit_workspace_context:
        if workspace_id and not _safe_str(base.get("workspace_id")):
            base["workspace_id"] = workspace_id
        if workspace_name and not _safe_str(base.get("workspace_name")):
            base["workspace_name"] = workspace_name

    if focus_label and not _safe_str(base.get("focus_label")):
        base["focus_label"] = focus_label

    if focus_root and (inherit_workspace_context or inherit_focus_root):
        if not _safe_str(base.get("focus_root")):
            base["focus_root"] = focus_root
        if not _safe_str(capability_gate.get("focus_root")):
            capability_gate["focus_root"] = focus_root

    if capability_gate:
        base["capability_gate"] = capability_gate

    if supervisor_provider and not _safe_str(base.get("supervisor_provider")):
        base["supervisor_provider"] = supervisor_provider
    if supervisor_model and not _safe_str(base.get("supervisor_model")):
        base["supervisor_model"] = supervisor_model

    base["mcp_overrides"] = dict(mcp_overrides)

    room_workspace_context.setdefault("workspace_id", workspace_id)
    room_workspace_context.setdefault("workspace_name", workspace_name)
    room_workspace_context.setdefault("focus_root", focus_root)
    room_workspace_context.setdefault("focus_label", focus_label)
    if room_workspace_context:
        base["room_workspace_context"] = room_workspace_context

    room_actor_context = dict(_safe_dict(base.get("room_actor_context")))
    if not room_actor_context:
        room_actor_context = _build_room_actor_context(
            actor_type="supervisor",
            actor_id="supervisor",
        )
    base["room_actor_context"] = room_actor_context

    room_supervisor_context.setdefault("workspace_id", workspace_id)
    room_supervisor_context.setdefault("workspace_name", workspace_name)
    room_supervisor_context.setdefault("focus_root", focus_root)
    room_supervisor_context.setdefault("focus_label", focus_label)
    room_supervisor_context.setdefault("inherit_workspace_context", inherit_workspace_context)
    room_supervisor_context.setdefault("inherit_focus_root", inherit_focus_root)
    room_supervisor_context["supervisor_skill_strategy"] = supervisor_skill_strategy
    room_supervisor_context["supervisor_skills_strategy"] = supervisor_skill_strategy
    room_supervisor_context.setdefault("mcp_overrides", dict(mcp_overrides))
    room_supervisor_context.setdefault("actor_type", _safe_str(room_actor_context.get("actor_type"), "supervisor"))
    room_supervisor_context.setdefault("actor_id", _safe_str(room_actor_context.get("actor_id"), "supervisor"))
    room_supervisor_context.setdefault("skill_id", _safe_str(room_actor_context.get("skill_id")))
    room_supervisor_context.setdefault("delegated_from", _safe_str(room_actor_context.get("delegated_from")))
    if room_supervisor_context:
        base["room_supervisor_context"] = room_supervisor_context

    return base


def _tool_result_item(type_name: str, **payload: Any) -> Dict[str, Any]:
    row = {"type": _safe_str(type_name)}
    row.update(payload)
    return row


def _merge_items(*parts: Any) -> List[Any]:
    out: List[Any] = []
    for part in parts:
        if isinstance(part, list):
            out.extend(part)
    return out


def _dedupe_records(rows: List[Any]) -> List[Any]:
    out: List[Any] = []
    seen = set()

    for row in _safe_list(rows):
        if not isinstance(row, dict):
            out.append(row)
            continue

        key = (
            _safe_str(row.get("tool_call_id") or row.get("call_id") or row.get("id")),
            _safe_str(row.get("tool_name") or row.get("name") or row.get("type")),
            _safe_str(row.get("relative_path")),
            _safe_str(row.get("status")),
        )

        if not any(key):
            try:
                key = ("fallback", repr(sorted(row.items())))
            except Exception:
                key = ("fallback", repr(row))

        if key in seen:
            continue

        seen.add(key)
        out.append(row)

    return out


def _build_supervisor_role(supervisor_model: str) -> Dict[str, Any]:
    model_name = _safe_str(supervisor_model)
    return {
        "role_id": "supervisor",
        "name": "Supervisor",
        "slug": "supervisor",
        "avatar": "🧠",
        "model": model_name,
        "system_prompt": "你是 Room Supervisor。",
    }


def _collect_read_candidate_paths(result: Dict[str, Any]) -> List[str]:
    src = _safe_dict(result)
    out: List[str] = []

    for value in _safe_list(src.get("target_paths")):
        path = _normalize_rel_path(value)
        if path:
            out.append(path)

    for doc in _safe_list(src.get("documents")):
        row = _safe_dict(doc)
        for key in ("relative_path", "path", "target_path", "scoped_path"):
            path = _normalize_rel_path(row.get(key))
            if path:
                out.append(path)

    deduped: List[str] = []
    seen = set()
    for path in out:
        if path in seen:
            continue
        seen.add(path)
        deduped.append(path)
    return deduped


def _match_supervisor_notebook_path(path: str, mcp: Dict[str, Any]) -> bool:
    rel = _normalize_rel_path(path)
    if not rel:
        return False

    notebook_dir = _normalize_rel_path(mcp.get("notebook_dir")) or "_room_supervisor_notebooks"
    notebook_filename = _normalize_filename(mcp.get("notebook_filename"), "supervisor.md")
    expected_suffix = f"{notebook_dir}/{notebook_filename}".strip("/")

    return rel == expected_suffix or rel.endswith(f"/{expected_suffix}")


def _derive_supervisor_notebook_read_result(
    *,
    file_read_result: Optional[Dict[str, Any]],
    mcp: Dict[str, Any],
) -> Dict[str, Any]:
    src = _safe_dict(file_read_result)
    if not src:
        return {}

    matched_path = ""
    for path in _collect_read_candidate_paths(src):
        if _match_supervisor_notebook_path(path, mcp):
            matched_path = path
            break

    if not matched_path:
        return {}

    status = _safe_str(src.get("status"), "success")
    message = _safe_str(src.get("message"))
    documents = _safe_list(src.get("documents"))

    return {
        "enabled": True,
        "status": status or "success",
        "message": message or "supervisor notebook read",
        "relative_path": matched_path,
        "documents_count": len(documents),
        "documents": documents,
        "tool_calls": _safe_list(src.get("tool_calls")),
        "tool_results": _safe_list(src.get("tool_results")),
        "recorded_at": _pick_recorded_at(src) or utc_iso(),
        "source_kind": "fs_read",
    }


def _augment_plan_summary_with_notebook_read(plan_summary: str, notebook_read_result: Dict[str, Any]) -> str:
    base = _safe_str(plan_summary)
    row = _safe_dict(notebook_read_result)
    if not row:
        return base

    relative_path = _normalize_rel_path(row.get("relative_path"))
    status = _safe_str(row.get("status")).lower()
    if not relative_path or status not in {"success", "ok", "succeeded"}:
        return base

    lines = [line.strip() for line in base.splitlines() if _safe_str(line)]
    dedupe_lines = list(lines)
    if dedupe_lines and dedupe_lines[0].startswith("问题："):
        dedupe_lines = dedupe_lines[1:]

    dedupe_text = "\n".join(dedupe_lines).lower()
    marker_patterns = [
        f"读取当前 supervisor notebook（{relative_path.lower()}）",
        "并将 notebook 当前内容纳入下一步 supervisor / skills 输入",
        relative_path.lower(),
    ]
    if any(token in dedupe_text for token in marker_patterns):
        return base

    sentence = (
        f"先读取当前 Supervisor notebook（{relative_path}）以获取已有阶段记录，"
        f"并将 notebook 当前内容纳入下一步 Supervisor / skills 输入。"
    )

    if not lines:
        return sentence

    insert_at = 1 if len(lines) >= 1 else 0
    lines.insert(insert_at, sentence)
    return "\n".join(lines)


def _build_supervisor_memory_read_tool_result(memory_read_result: Dict[str, Any]):
    row = _safe_dict(memory_read_result)
    if not row:
        return None
    checkpoint = _safe_dict(row.get("checkpoint"))
    resume = _safe_dict(row.get("resume"))
    return _tool_result_item(
        "supervisor_memory_read",
        status=_safe_str(row.get("status")),
        message=_safe_str(row.get("message")),
        reason_code=_safe_str(row.get("reason_code")),
        relative_path=_normalize_rel_path(row.get("relative_path")),
        source_kind=_safe_str(row.get("source_kind")),
        version=int(row.get("version") or 0),
        checkpoint_stage=_safe_str(checkpoint.get("stage")),
        checkpoint_summary=_safe_str(checkpoint.get("summary")),
        recovery_hint=_safe_str(checkpoint.get("recovery_hint")),
        resume_ready=as_bool(resume.get("resume_ready"), False),
    )


def _build_supervisor_memory_resume_tool_result(memory_resume_result: Dict[str, Any]):
    row = _safe_dict(memory_resume_result)
    if not row:
        return None
    return _tool_result_item(
        "supervisor_memory_resume",
        status=_safe_str(row.get("status")),
        decision=_safe_str(row.get("decision")),
        reason=_safe_str(row.get("reason")),
        resume_ready=as_bool(row.get("resume_ready"), False),
        relative_path=_normalize_rel_path(row.get("relative_path")),
        checkpoint_stage=_safe_str(row.get("checkpoint_stage")),
        checkpoint_summary=_safe_str(row.get("checkpoint_summary")),
        recovery_hint=_safe_str(row.get("recovery_hint")),
    )


def _build_supervisor_memory_write_tool_result(memory_result: Dict[str, Any]):
    row = _safe_dict(memory_result)
    if not row:
        return None
    return _tool_result_item(
        "supervisor_memory_write",
        status=_safe_str(row.get("status")),
        message=_safe_str(row.get("message")),
        reason_code=_safe_str(row.get("reason_code")),
        relative_path=_normalize_rel_path(row.get("relative_path")),
        bytes_written=int(row.get("bytes_written") or 0),
        checkpoint_stage=_safe_str(row.get("checkpoint_stage")),
        checkpoint_summary=_safe_str(row.get("checkpoint_summary")),
        resume_decision=_safe_str(row.get("resume_decision")),
        resume_reason=_safe_str(row.get("resume_reason")),
        source_kind=_safe_str(row.get("source_kind")),
    )

def _build_runtime_control_projection(
    *,
    state: Optional[Dict[str, Any]] = None,
    request_args: Optional[Dict[str, Any]] = None,
    phase: str = "",
    status: str = "",
    finished: bool = False,
    memory_resume_result: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    src_state = _safe_dict(state)
    req = _safe_dict(request_args)
    memory_resume_row = _safe_dict(memory_resume_result)

    return _build_runtime_control_snapshot(
        prev_state=src_state,
        request_row=req,
        phase=phase,
        status=status,
        finished=finished,
        memory_resume_row=memory_resume_row,
    )

__all__ = [
    "_augment_plan_summary_with_notebook_read",
    "_build_room_actor_context",
    "_build_supervisor_memory_read_tool_result",
    "_build_supervisor_memory_resume_tool_result",
    "_build_supervisor_memory_write_tool_result",
    "_build_supervisor_role",
    "_build_supervisor_runtime_request_args",
    "_dedupe_records",
    "_derive_supervisor_notebook_read_result",
    "_merge_items",
    "_normalize_room_mcp_overrides",
    "_tool_result_item",
    "_build_runtime_control_projection",
]


