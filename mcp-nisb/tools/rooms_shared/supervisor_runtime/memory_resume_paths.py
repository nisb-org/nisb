from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from ..room_contracts import as_bool, utc_iso
from ..room_store import load_state_doc
from .memory_resume_common import (
    _normalize_rel_path,
    _safe_dict,
    _safe_int,
    _safe_list,
    _safe_str,
)


def normalize_memory_filename(value: Any, fallback: str = "supervisor.memory.json") -> str:
    raw = _safe_str(value).replace("\\", "/").strip()
    if not raw:
        return fallback
    base = raw.split("/")[-1].strip()
    if not base or base in {".", ".."}:
        return fallback
    if not base.lower().endswith(".json"):
        base = f"{base}.json"
    return base


def normalize_memory_checkpoint(value: Any) -> Dict[str, Any]:
    src = _safe_dict(value)
    return {
        "stage": _safe_str(src.get("stage")),
        "last_step": _safe_str(src.get("last_step")),
        "summary": _safe_str(src.get("summary")),
        "open_questions": [item for item in _safe_list(src.get("open_questions")) if _safe_str(item)],
        "next_actions": [item for item in _safe_list(src.get("next_actions")) if _safe_str(item)],
        "recovery_hint": _safe_str(src.get("recovery_hint")),
        "evidence_refs": [item for item in _safe_list(src.get("evidence_refs")) if _safe_str(item)],
        "question": _safe_str(src.get("question")),
        "plan_summary": _safe_str(src.get("plan_summary")),
        "topic_anchor": _safe_str(src.get("topic_anchor")),
    }


def normalize_memory_resume(value: Any) -> Dict[str, Any]:
    src = _safe_dict(value)
    return {
        "resume_token": _safe_str(src.get("resume_token")),
        "resume_ready": as_bool(src.get("resume_ready"), False),
        "resume_reason": _safe_str(src.get("resume_reason")),
        "invalidated_by": _safe_str(src.get("invalidated_by")),
    }


def build_supervisor_memory_relative_path(mcp: Dict[str, Any]) -> str:
    notebook_dir = _normalize_rel_path(mcp.get("notebook_dir")) or "_room_supervisor_notebooks"
    memory_filename = normalize_memory_filename(mcp.get("memory_filename"), "supervisor.memory.json")
    return f"{notebook_dir}/{memory_filename}".strip("/")


def _workspace_focus_root_from_room_state(room_id: str) -> str:
    state = _safe_dict(load_state_doc(room_id))
    return _normalize_rel_path(
        state.get("focus_root")
        or state.get("focusRoot")
        or state.get("focusroot")
    )


def _candidate_user_base_roots() -> List[Path]:
    env_names = [
        "NISB_USER_BASE",
        "NISB_BASEPATH",
        "NISB_USER_ROOT",
        "NISB_DATA_USER_BASE",
        "NISB_DATA_BASEPATH",
    ]
    out: List[Path] = []
    seen = set()

    for name in env_names:
        value = _safe_str(os.environ.get(name))
        if not value:
            continue
        path = Path(value).expanduser()
        key = str(path)
        if key in seen:
            continue
        seen.add(key)
        out.append(path)

    users_root = Path("/opt/nisb-data/users")
    if users_root.exists():
        for child in sorted(users_root.iterdir()):
            if not child.is_dir():
                continue
            key = str(child)
            if key in seen:
                continue
            seen.add(key)
            out.append(child)

    return out


def _candidate_room_roots() -> List[Path]:
    env_names = [
        "NISB_SHARED_ROOMS_ROOT",
        "NISB_ROOMS_ROOT",
        "NISB_ROOMS_DIR",
        "NISB_ROOM_DATA_ROOT",
        "ROOMS_DATA_ROOT",
    ]
    out: List[Path] = []
    seen = set()

    for name in env_names:
        value = _safe_str(os.environ.get(name))
        if not value:
            continue
        path = Path(value).expanduser()
        key = str(path)
        if key in seen:
            continue
        seen.add(key)
        out.append(path)

    for raw in [
        "/opt/nisb-data/shared/rooms",
        "/opt/mcp-gateway/nisb-data/shared/rooms",
        "/data/shared/rooms",
    ]:
        path = Path(raw)
        key = str(path)
        if key in seen:
            continue
        seen.add(key)
        out.append(path)

    return out


def resolve_room_root(room_id: str) -> Optional[Path]:
    rid = _safe_str(room_id)
    if not rid:
        return None

    existing_base: Optional[Path] = None
    for base in _candidate_room_roots():
        try:
            room_path = base / rid
            if room_path.exists():
                return room_path
            if existing_base is None and base.exists():
                existing_base = base
        except Exception:
            continue

    if existing_base is not None:
        return existing_base / rid
    return None


def _resolve_workspace_memory_path(
    *,
    room_id: str,
    mcp: Dict[str, Any],
) -> Tuple[Optional[Path], str, str]:
    focus_root = _workspace_focus_root_from_room_state(room_id)
    if not focus_root:
        return None, "", "workspace_notebook_root"

    memory_rel = build_supervisor_memory_relative_path(mcp)
    logical_relative_path = _normalize_rel_path(f"{focus_root}/{memory_rel}")

    for user_base in _candidate_user_base_roots():
        try:
            focus_abs = user_base / focus_root
            memory_abs = user_base / logical_relative_path

            if memory_abs.exists():
                return memory_abs, logical_relative_path, "workspace_notebook_root"
            if memory_abs.parent.exists():
                return memory_abs, logical_relative_path, "workspace_notebook_root"
            if focus_abs.exists():
                return memory_abs, logical_relative_path, "workspace_notebook_root"
        except Exception:
            continue

    return None, logical_relative_path, "workspace_notebook_root"


def _resolve_room_sidecar_memory_path(
    *,
    room_id: str,
    mcp: Dict[str, Any],
) -> Tuple[Optional[Path], str, str]:
    relative_path = build_supervisor_memory_relative_path(mcp)
    room_root = resolve_room_root(room_id)
    if room_root is None:
        return None, relative_path, "room_sidecar"
    return room_root / relative_path, relative_path, "room_sidecar"


def resolve_supervisor_memory_path(
    *,
    room_id: str,
    mcp: Dict[str, Any],
) -> Tuple[Optional[Path], str, str]:
    room_path, room_rel, room_kind = _resolve_room_sidecar_memory_path(
        room_id=room_id,
        mcp=mcp,
    )
    if room_path is not None:
        return room_path, room_rel, room_kind

    workspace_path, workspace_rel, workspace_kind = _resolve_workspace_memory_path(
        room_id=room_id,
        mcp=mcp,
    )
    if workspace_path is not None:
        return workspace_path, workspace_rel, workspace_kind

    return room_path, room_rel or workspace_rel, room_kind or workspace_kind


def disabled_memory_result(message: str = "memory write skipped") -> Dict[str, Any]:
    return {
        "enabled": False,
        "status": "disabled",
        "message": _safe_str(message),
        "reason_code": "MEMORY_WRITE_SKIPPED",
        "relative_path": "",
        "bytes_written": 0,
        "tool_calls": [],
        "tool_results": [],
        "recorded_at": utc_iso(),
        "checkpoint_stage": "",
        "checkpoint_summary": "",
        "checkpoint_question": "",
        "topic_anchor": "",
        "resume_decision": "none",
        "resume_reason": "",
    }


def load_supervisor_memory_sidecar(
    *,
    room_id: str,
    mcp: Dict[str, Any],
) -> Dict[str, Any]:
    memory_path, relative_path, source_kind = resolve_supervisor_memory_path(
        room_id=room_id,
        mcp=mcp,
    )

    if memory_path is None:
        return {
            "enabled": True,
            "status": "missing",
            "message": "supervisor memory sidecar path not resolved",
            "reason_code": "MEMORY_PATH_NOT_RESOLVED",
            "relative_path": relative_path,
            "tool_calls": [],
            "tool_results": [],
            "recorded_at": utc_iso(),
            "source_kind": source_kind,
            "checkpoint": {},
            "resume": {},
            "version": 1,
        }

    if not memory_path.exists():
        return {
            "enabled": True,
            "status": "missing",
            "message": "supervisor memory sidecar not found",
            "reason_code": "MEMORY_NOT_FOUND",
            "relative_path": relative_path,
            "tool_calls": [],
            "tool_results": [],
            "recorded_at": utc_iso(),
            "source_kind": source_kind,
            "checkpoint": {},
            "resume": {},
            "version": 1,
        }

    try:
        raw = memory_path.read_text(encoding="utf-8")
    except Exception as ex:
        return {
            "enabled": True,
            "status": "invalid",
            "message": f"failed to read supervisor memory sidecar: {type(ex).__name__}",
            "reason_code": "MEMORY_READ_ERROR",
            "relative_path": relative_path,
            "tool_calls": [],
            "tool_results": [],
            "recorded_at": utc_iso(),
            "source_kind": source_kind,
            "checkpoint": {},
            "resume": {},
            "version": 1,
        }

    try:
        parsed = json.loads(raw)
    except Exception as ex:
        return {
            "enabled": True,
            "status": "invalid",
            "message": f"invalid supervisor memory json: {type(ex).__name__}",
            "reason_code": "MEMORY_INVALID_JSON",
            "relative_path": relative_path,
            "tool_calls": [],
            "tool_results": [],
            "recorded_at": utc_iso(),
            "source_kind": source_kind,
            "checkpoint": {},
            "resume": {},
            "version": 1,
        }

    doc = _safe_dict(parsed)
    checkpoint = normalize_memory_checkpoint(doc.get("checkpoint"))
    resume = normalize_memory_resume(doc.get("resume"))
    version = _safe_int(doc.get("version"), 1)

    return {
        "enabled": True,
        "status": "success",
        "message": "supervisor memory sidecar loaded",
        "reason_code": "MEMORY_LOADED",
        "relative_path": relative_path,
        "tool_calls": [],
        "tool_results": [],
        "recorded_at": _safe_str(doc.get("updated_at"), utc_iso()),
        "source_kind": source_kind,
        "version": version if version > 0 else 1,
        "checkpoint": checkpoint,
        "resume": resume,
        "last_run_id": _safe_str(doc.get("last_run_id")),
        "last_supervisor_event_id": _safe_str(doc.get("last_supervisor_event_id")),
        "status_value": _safe_str(doc.get("status"), "active"),
        "raw_doc": doc,
    }


__all__ = [
    "_candidate_room_roots",
    "_candidate_user_base_roots",
    "_resolve_room_sidecar_memory_path",
    "_resolve_workspace_memory_path",
    "_workspace_focus_root_from_room_state",
    "build_supervisor_memory_relative_path",
    "disabled_memory_result",
    "load_supervisor_memory_sidecar",
    "normalize_memory_checkpoint",
    "normalize_memory_filename",
    "normalize_memory_resume",
    "resolve_room_root",
    "resolve_supervisor_memory_path",
]
