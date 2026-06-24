from __future__ import annotations

import re
import secrets
import time
from datetime import datetime, timezone
from typing import Any, Dict, List

SAFE_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")
ROLE_SLUG_RE = re.compile(r"[^a-z0-9_]+")


def utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_id(prefix: str) -> str:
    return f"{prefix}_{int(time.time()*1000)}_{secrets.token_hex(3)}"


def new_request_id() -> str:
    return f"req_{int(time.time()*1000)}_{secrets.token_hex(4)}"


def ensure_request_id(args: Dict[str, Any]) -> str:
    rid = str((args or {}).get("request_id") or "").strip()
    if not rid:
        rid = new_request_id()
        args["request_id"] = rid
    return rid


def require_safe_id(field: str, value: Any) -> str:
    s = str(value or "").strip()
    if not s:
        raise ValueError(f"{field} is required")
    if not SAFE_ID_RE.fullmatch(s):
        raise ValueError(f"{field} is unsafe")
    return s


def as_bool(v: Any, default: bool = False) -> bool:
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return bool(v)
    if isinstance(v, str):
        x = v.strip().lower()
        if x in ("1", "true", "yes", "on"):
            return True
        if x in ("0", "false", "no", "off"):
            return False
    return default


def normalize_role_slug(name: str) -> str:
    s = str(name or "").strip().lower()
    s = ROLE_SLUG_RE.sub("_", s)
    s = s.strip("_")
    return s or "role"


def normalize_focus_root(value: Any) -> str:
    s = str(value or "").strip()
    if not s:
        return ""

    s = s.replace("\\\\", "/").strip()
    while "//" in s:
        s = s.replace("//", "/")
    s = s.strip("/")

    parts: List[str] = []
    for item in s.split("/"):
        p = str(item or "").strip()
        if not p or p == ".":
            continue
        if p == "..":
            raise ValueError("focus_root is unsafe")
        parts.append(p)

    return "/".join(parts)


def default_tool_policy() -> Dict[str, Any]:
    return {
        "rag": True,
        "web": False,
        "mcp": False,
        "code": False,
        "fs_read": False,
        "fs_write": False,
    }


def default_trigger_policy(name: str = "", slug: str = "") -> Dict[str, Any]:
    mention_names: List[str] = []
    n = str(name or "").strip()
    s = str(slug or "").strip()

    if s:
        mention_names.append(f"@{s}")
    if n and f"@{n}" not in mention_names:
        mention_names.append(f"@{n}")

    return {
        "mention_names": mention_names,
        "respond_on_plain_message": False,
        "participate_in_orchestration": True,
    }


def default_room_mcp_overrides() -> Dict[str, Any]:
    return {
        "fs_read_enabled": False,
        "fs_read_scope": "minimal",
        "notebook_write_enabled": False,
        "notebook_dir": "_room_supervisor_notebooks",
        "notebook_filename": "supervisor.md",
        "notebook_title": "Supervisor notebook",
        "notebook_section_title": "latest",
    }


def default_room_state() -> Dict[str, Any]:
    return {
        "summary": "",
        "scratchpad": "",
        "active_roles": [],
        "enabled_supervisor_skill_ids": [],
        "supervisor_skill_strategy": "builtin_plus_custom",
        "inherit_workspace_context": True,
        "inherit_focus_root": True,
        "default_reply_role_id": "",
        "supervisor_enabled": False,
        "reply_mode": "manual",
        "supervisor_provider": "openai",
        "supervisor_model": "",
        "supervisor_temperature": "",
        "supervisor_max_tokens": "",
        "supervisor_step_budget_total": 0,
        "mcp_overrides": default_room_mcp_overrides(),
        "current_run_id": "",
        "current_request_id": "",
        "current_trigger_event_id": "",
        "current_run_status": "",
        "current_run_roles": [],
        "current_delegate_role_id": "",
        "current_delegate_role_name": "",
        "current_delegate_index": 0,
        "current_delegate_total": 0,
        "continuation_mode": "",
        "continuation_status": "",
        "pause_requested": False,
        "paused_at": "",
        "pause_reason": "",
        "interruption_reason": "",
        "resume_from_checkpoint": False,
        "resume_checkpoint_ref": "",
        "resumable_checkpoint_ref": "",
        "resumed_from_run_id": "",
        "resumed_from_event_id": "",
        "resumed_from_stage": "",
        "checkpoint_event_id": "",
        "checkpoint_stage": "",
        "checkpoint_summary": "",
        "last_completed_step": "",
        "final_event_id": "",
        "skipped_effects": [],
        "effect_dispositions": [],
        "budget_exhausted": False,
        "budget_status": "",
        "last_plan_summary": "",
        "last_plan_at": "",
        "last_run_finished_at": "",
        "last_message_id": "",
        "last_message_at": "",
        "last_message": "",
        "last_message_sender": "",
        "last_message_sender_type": "",
        "last_message_status": "",
        "workspace_id": "",
        "workspace_name": "",
        "focus_root": "",
        "focus_label": "",
        "workspace_context_updated_at": "",
        "last_supervisor_fs_read_at": "",
        "last_supervisor_fs_read_enabled": False,
        "last_supervisor_fs_read_status": "",
        "last_supervisor_fs_read_reason": "",
        "last_supervisor_fs_read_focus_root": "",
        "last_supervisor_fs_read_scope": "minimal",
        "last_supervisor_tool_calls": [],
        "last_supervisor_tool_results": [],
        "last_supervisor_notebook_write_at": "",
        "last_supervisor_notebook_write_status": "",
        "last_supervisor_notebook_write_message": "",
        "last_supervisor_notebook_relative_path": "",
        "last_supervisor_notebook_tool_calls": [],
        "last_supervisor_notebook_tool_results": [],
        "last_supervisor_pause_requested": False,
        "last_supervisor_pause_reason": "",
        "last_supervisor_resume_from_checkpoint": False,
        "last_supervisor_resume_checkpoint_ref": "",
        "last_supervisor_continuation_mode": "",
        "last_supervisor_continuation_status": "",
        "last_supervisor_resumed_from_run_id": "",
        "last_supervisor_resumed_from_event_id": "",
        "last_supervisor_resumed_from_stage": "",
        "last_supervisor_skipped_effects": [],
        "last_supervisor_effect_dispositions": [],
        "updated_at": utc_iso(),
    }
