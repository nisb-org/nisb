from __future__ import annotations

from typing import Any, Dict, List, Optional

from .room_contracts import as_bool, default_room_state


def _safe_str(v: Any, default: str = "") -> str:
    if v is None:
        return default
    s = str(v).strip()
    return s if s else default


def _safe_list(v: Any) -> List[Any]:
    return v if isinstance(v, list) else []


def _safe_dict(v: Any) -> Dict[str, Any]:
    return v if isinstance(v, dict) else {}


def _dedupe_str_list(v: Any) -> List[str]:
    out: List[str] = []
    seen = set()
    for item in _safe_list(v):
        s = str(item).strip()
        if not s or s in seen:
            continue
        seen.add(s)
        out.append(s)
    return out


def _normalize_reply_mode(value: Any, fallback: str = "") -> str:
    s = _safe_str(value).lower()
    if s in {"manual", "direct_role", "supervisor", "supervisor_direct"}:
        return s
    fb = _safe_str(fallback).lower()
    return fb if fb in {"manual", "direct_role", "supervisor", "supervisor_direct"} else ""


def _normalize_supervisor_provider(value: Any, fallback: str = "") -> str:
    s = _safe_str(value).lower()
    if s in {"openai", "anthropic"}:
        return s
    fb = _safe_str(fallback).lower()
    return fb if fb in {"openai", "anthropic"} else "openai"


def _normalize_supervisor_skill_strategy(value: Any, fallback: str = "builtin_plus_custom") -> str:
    s = _safe_str(value).strip().lower()
    if s in {"builtin_plus_custom", "custom_only", "builtin_only"}:
        return s
    if s in {"builtin+custom", "default", "all"}:
        return "builtin_plus_custom"
    if s == "custom":
        return "custom_only"
    if s == "builtin":
        return "builtin_only"

    fb = _safe_str(fallback).strip().lower()
    if fb in {"builtin_plus_custom", "custom_only", "builtin_only"}:
        return fb
    return "builtin_plus_custom"


def _normalize_room_float(value: Any, fallback: Optional[float] = None) -> Optional[float]:
    s = _safe_str(value)
    if not s:
        return fallback
    try:
        return float(s)
    except Exception:
        return fallback


def _normalize_room_int(value: Any, fallback: Optional[int] = None) -> Optional[int]:
    s = _safe_str(value)
    if not s:
        return fallback
    try:
        return max(0, int(s))
    except Exception:
        return fallback


def _normalize_rel_path(value: Any) -> str:
    raw = _safe_str(value).replace("\\", "/")
    while "//" in raw:
        raw = raw.replace("//", "/")
    raw = raw.strip("/")
    if not raw:
        return ""
    parts = [p.strip() for p in raw.split("/") if p and p not in {".", ".."}]
    return "/".join(parts)


def _normalize_filename(value: Any, fallback: str = "supervisor.md") -> str:
    raw = _safe_str(value).replace("\\", "/").strip()
    if not raw:
        return fallback
    base = raw.split("/")[-1].strip()
    if not base or base in {".", ".."}:
        return fallback
    if not base.lower().endswith(".md"):
        base = f"{base}.md"
    return base


def _normalize_fs_read_scope(value: Any, fallback: str = "minimal") -> str:
    s = _safe_str(value).lower()
    if s in {"minimal", "user_ro"}:
        return s
    return fallback if fallback in {"minimal", "user_ro"} else "minimal"


def _normalize_skill_id(value: Any) -> str:
    raw = _normalize_rel_path(value)
    if not raw:
        return ""
    if raw == "_room_supervisor_skills":
        return ""
    if raw.startswith("_room_supervisor_skills/"):
        raw = raw[len("_room_supervisor_skills/") :]
    if raw.lower().endswith(".md"):
        raw = raw[:-3]
    return _normalize_rel_path(raw)


def _normalize_enabled_supervisor_skill_ids(
    value: Any,
    fallback: Any = None,
) -> List[str]:
    source = value if isinstance(value, list) else fallback

    out: List[str] = []
    seen = set()
    for item in _safe_list(source):
        skill_id = _normalize_skill_id(item)
        if not skill_id or skill_id in seen:
            continue
        seen.add(skill_id)
        out.append(skill_id)
    return out


def _normalize_room_mcp_overrides(
    value: Any,
    fallback: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    src = _safe_dict(value)
    base = _safe_dict(fallback)

    fs_read_enabled = as_bool(
        src.get("fs_read_enabled", base.get("fs_read_enabled", False)),
        as_bool(base.get("fs_read_enabled"), False),
    )
    fs_read_scope = _normalize_fs_read_scope(
        src.get("fs_read_scope", base.get("fs_read_scope", "minimal")),
        fallback=_normalize_fs_read_scope(base.get("fs_read_scope", "minimal")),
    )
    notebook_write_enabled = as_bool(
        src.get("notebook_write_enabled", base.get("notebook_write_enabled", False)),
        as_bool(base.get("notebook_write_enabled"), False),
    )
    notebook_dir = _normalize_rel_path(
        src.get("notebook_dir", base.get("notebook_dir", "_room_supervisor_notebooks"))
    ) or "_room_supervisor_notebooks"
    notebook_filename = _normalize_filename(
        src.get("notebook_filename", base.get("notebook_filename", "supervisor.md")),
        fallback=_normalize_filename(base.get("notebook_filename", "supervisor.md"), "supervisor.md"),
    )
    notebook_title = _safe_str(
        src.get("notebook_title", base.get("notebook_title", "Supervisor notebook")),
        "Supervisor notebook",
    )
    notebook_section_title = _safe_str(
        src.get("notebook_section_title", base.get("notebook_section_title", "latest")),
        "latest",
    )

    out: Dict[str, Any] = {
        "fs_read_enabled": fs_read_enabled,
        "fs_read_scope": fs_read_scope,
        "notebook_write_enabled": notebook_write_enabled,
        "notebook_dir": notebook_dir,
        "notebook_filename": notebook_filename,
        "notebook_title": notebook_title,
        "notebook_section_title": notebook_section_title,
    }

    for passthrough_key in ("fs_write_scope", "fs_dangerous_enabled"):
        if passthrough_key in src:
            out[passthrough_key] = src.get(passthrough_key)
        elif passthrough_key in base:
            out[passthrough_key] = base.get(passthrough_key)

    return out


def _derive_reply_mode_from_state(state: Dict[str, Any]) -> str:
    explicit = _normalize_reply_mode(state.get("reply_mode"))
    if explicit:
        return explicit
    if as_bool(state.get("supervisor_enabled"), False):
        return "supervisor"
    if _safe_str(state.get("default_reply_role_id")):
        return "direct_role"
    return "manual"


def _normalize_room_state_for_output(state: Dict[str, Any]) -> Dict[str, Any]:
    defaults = _safe_dict(default_room_state())
    out = dict(defaults)
    out.update(_safe_dict(state))

    reply_mode = _derive_reply_mode_from_state(out)
    out["reply_mode"] = reply_mode

    supervisor_enabled = as_bool(out.get("supervisor_enabled"), False)
    if reply_mode in {"supervisor", "supervisor_direct"}:
        supervisor_enabled = True
    out["supervisor_enabled"] = supervisor_enabled

    out["supervisor_provider"] = _normalize_supervisor_provider(
        out.get("supervisor_provider"),
        fallback=_safe_str(defaults.get("supervisor_provider"), "openai"),
    )
    out["supervisor_model"] = _safe_str(out.get("supervisor_model"))

    temperature = _normalize_room_float(out.get("supervisor_temperature"), None)
    max_tokens = _normalize_room_int(out.get("supervisor_max_tokens"), None)
    step_budget_total = _normalize_room_int(
        out.get("supervisor_step_budget_total", out.get("step_budget_total")),
        0,
    )
    step_budget_used = _normalize_room_int(
        out.get("supervisor_step_budget_used", out.get("step_budget_used")),
        0,
    )
    step_budget_remaining = _normalize_room_int(
        out.get("supervisor_step_budget_remaining", out.get("step_budget_remaining")),
        0,
    )

    out["supervisor_temperature"] = temperature if temperature is not None else ""
    out["supervisor_max_tokens"] = max_tokens if max_tokens is not None else ""
    out["supervisor_step_budget_total"] = max(0, step_budget_total or 0)
    out["supervisor_step_budget_used"] = max(0, step_budget_used or 0)
    out["supervisor_step_budget_remaining"] = max(0, step_budget_remaining or 0)

    out["summary"] = _safe_str(out.get("summary"))
    out["scratchpad"] = _safe_str(out.get("scratchpad"))
    out["active_roles"] = _dedupe_str_list(out.get("active_roles"))
    out["enabled_supervisor_skill_ids"] = _normalize_enabled_supervisor_skill_ids(
        out.get("enabled_supervisor_skill_ids"),
        fallback=defaults.get("enabled_supervisor_skill_ids", []),
    )
    out["supervisor_skill_strategy"] = _normalize_supervisor_skill_strategy(
        out.get("supervisor_skill_strategy"),
        fallback=_safe_str(defaults.get("supervisor_skill_strategy"), "builtin_plus_custom"),
    )
    out["inherit_workspace_context"] = as_bool(out.get("inherit_workspace_context"), True)
    out["inherit_focus_root"] = as_bool(out.get("inherit_focus_root"), True)
    out["default_reply_role_id"] = _safe_str(out.get("default_reply_role_id"))

    out["current_run_id"] = _safe_str(out.get("current_run_id"))
    out["current_request_id"] = _safe_str(out.get("current_request_id"))
    out["current_trigger_event_id"] = _safe_str(out.get("current_trigger_event_id"))
    out["current_run_status"] = _safe_str(out.get("current_run_status"))
    out["current_run_roles"] = _dedupe_str_list(out.get("current_run_roles"))
    out["current_delegate_role_id"] = _safe_str(out.get("current_delegate_role_id"))
    out["current_delegate_role_name"] = _safe_str(out.get("current_delegate_role_name"))
    out["current_delegate_index"] = _normalize_room_int(out.get("current_delegate_index"), 0) or 0
    out["current_delegate_total"] = _normalize_room_int(out.get("current_delegate_total"), 0) or 0

    out["last_plan_summary"] = _safe_str(out.get("last_plan_summary"))
    out["last_plan_at"] = _safe_str(out.get("last_plan_at"))
    out["last_run_finished_at"] = _safe_str(out.get("last_run_finished_at"))
    out["last_message_id"] = _safe_str(out.get("last_message_id"))
    out["last_message_at"] = _safe_str(out.get("last_message_at"))
    out["last_message"] = _safe_str(out.get("last_message"))
    out["last_message_sender"] = _safe_str(out.get("last_message_sender"))
    out["last_message_sender_type"] = _safe_str(out.get("last_message_sender_type"))
    out["last_message_status"] = _safe_str(out.get("last_message_status"))

    out["workspace_id"] = _safe_str(out.get("workspace_id"))
    out["workspace_name"] = _safe_str(out.get("workspace_name"))
    out["focus_root"] = _normalize_rel_path(out.get("focus_root"))
    out["focus_label"] = _safe_str(out.get("focus_label"))
    out["workspace_context_updated_at"] = _safe_str(out.get("workspace_context_updated_at"))
    out["updated_at"] = _safe_str(out.get("updated_at"))

    out["mcp_overrides"] = _normalize_room_mcp_overrides(
        out.get("mcp_overrides"),
        fallback=defaults.get("mcp_overrides"),
    )

    out["last_supervisor_fs_read_at"] = _safe_str(out.get("last_supervisor_fs_read_at"))
    out["last_supervisor_fs_read_enabled"] = as_bool(out.get("last_supervisor_fs_read_enabled"), False)
    out["last_supervisor_fs_read_status"] = _safe_str(out.get("last_supervisor_fs_read_status"))
    out["last_supervisor_fs_read_reason"] = _safe_str(out.get("last_supervisor_fs_read_reason"))
    out["last_supervisor_fs_read_focus_root"] = _normalize_rel_path(out.get("last_supervisor_fs_read_focus_root"))
    out["last_supervisor_fs_read_scope"] = _normalize_fs_read_scope(out.get("last_supervisor_fs_read_scope"), "minimal")
    out["last_supervisor_tool_calls"] = _safe_list(out.get("last_supervisor_tool_calls"))
    out["last_supervisor_tool_results"] = _safe_list(out.get("last_supervisor_tool_results"))
    out["last_supervisor_notebook_write_at"] = _safe_str(out.get("last_supervisor_notebook_write_at"))
    out["last_supervisor_notebook_write_status"] = _safe_str(out.get("last_supervisor_notebook_write_status"))
    out["last_supervisor_notebook_write_message"] = _safe_str(out.get("last_supervisor_notebook_write_message"))
    out["last_supervisor_notebook_relative_path"] = _normalize_rel_path(out.get("last_supervisor_notebook_relative_path"))
    out["last_supervisor_notebook_tool_calls"] = _safe_list(out.get("last_supervisor_notebook_tool_calls"))
    out["last_supervisor_notebook_tool_results"] = _safe_list(out.get("last_supervisor_notebook_tool_results"))

    out["runtime_control_run_id"] = _safe_str(out.get("runtime_control_run_id"), out["current_run_id"])
    out["runtime_control_version"] = _normalize_room_int(out.get("runtime_control_version"), 0) or 0
    out["runtime_version"] = _normalize_room_int(out.get("runtime_version"), 0) or 0
    out["runtime_state_hint"] = _safe_str(out.get("runtime_state_hint"))
    out["runtime_phase_hint"] = _safe_str(out.get("runtime_phase_hint"))

    out["continuation_mode"] = _safe_str(out.get("continuation_mode"))
    out["continuation_status"] = _safe_str(out.get("continuation_status"))

    out["pause_requested"] = as_bool(out.get("pause_requested"), False)
    out["pause_reason"] = _safe_str(out.get("pause_reason"))
    out["pause_requested_at"] = _safe_str(out.get("pause_requested_at"))
    out["paused_at"] = _safe_str(out.get("paused_at"))
    out["pause_effective_at"] = _safe_str(out.get("pause_effective_at"))

    out["resume_from_checkpoint"] = as_bool(out.get("resume_from_checkpoint"), False)
    out["resume_checkpoint_ref"] = _safe_str(out.get("resume_checkpoint_ref"))
    out["resume_ready"] = as_bool(out.get("resume_ready"), False)
    out["resume_token"] = _safe_str(out.get("resume_token"))
    out["resume_reason"] = _safe_str(out.get("resume_reason"))
    out["error_blocking_resume"] = as_bool(out.get("error_blocking_resume"), False)

    out["resumed_from_run_id"] = _safe_str(out.get("resumed_from_run_id"))
    out["resumed_from_event_id"] = _safe_str(out.get("resumed_from_event_id"))
    out["resumed_from_stage"] = _safe_str(out.get("resumed_from_stage"))
    out["last_completed_step"] = _safe_str(out.get("last_completed_step"))

    out["skipped_effects"] = _safe_list(out.get("skipped_effects"))
    out["effect_dispositions"] = _safe_list(out.get("effect_dispositions"))

    out["checkpoint_stage"] = _safe_str(out.get("checkpoint_stage"))
    out["checkpoint_summary"] = _safe_str(out.get("checkpoint_summary"))
    out["checkpoint_event_id"] = _safe_str(out.get("checkpoint_event_id"))
    out["resumable_checkpoint_ref"] = _safe_str(out.get("resumable_checkpoint_ref"))
    out["final_event_id"] = _safe_str(out.get("final_event_id"))
    out["interruption_reason"] = _safe_str(out.get("interruption_reason"))

    out["step_budget_total"] = _normalize_room_int(out.get("step_budget_total"), out["supervisor_step_budget_total"]) or 0
    out["step_budget_used"] = _normalize_room_int(out.get("step_budget_used"), out["supervisor_step_budget_used"]) or 0
    out["step_budget_remaining"] = _normalize_room_int(
        out.get("step_budget_remaining"),
        out["supervisor_step_budget_remaining"],
    ) or 0
    out["budget_status"] = _safe_str(out.get("budget_status"))
    out["budget_exhausted"] = as_bool(out.get("budget_exhausted"), False)

    out["last_supervisor_pause_requested"] = as_bool(out.get("last_supervisor_pause_requested"), False)
    out["last_supervisor_pause_reason"] = _safe_str(out.get("last_supervisor_pause_reason"))
    out["last_supervisor_pause_requested_at"] = _safe_str(out.get("last_supervisor_pause_requested_at"))
    out["last_supervisor_paused_at"] = _safe_str(out.get("last_supervisor_paused_at"))

    out["last_supervisor_resume_from_checkpoint"] = as_bool(
        out.get("last_supervisor_resume_from_checkpoint"),
        False,
    )
    out["last_supervisor_resume_checkpoint_ref"] = _safe_str(out.get("last_supervisor_resume_checkpoint_ref"))
    out["last_supervisor_continuation_mode"] = _safe_str(out.get("last_supervisor_continuation_mode"))
    out["last_supervisor_continuation_status"] = _safe_str(out.get("last_supervisor_continuation_status"))
    out["last_supervisor_resumed_from_run_id"] = _safe_str(out.get("last_supervisor_resumed_from_run_id"))
    out["last_supervisor_resumed_from_event_id"] = _safe_str(out.get("last_supervisor_resumed_from_event_id"))
    out["last_supervisor_resumed_from_stage"] = _safe_str(out.get("last_supervisor_resumed_from_stage"))
    out["last_supervisor_last_completed_step"] = _safe_str(out.get("last_supervisor_last_completed_step"))
    out["last_supervisor_skipped_effects"] = _safe_list(out.get("last_supervisor_skipped_effects"))
    out["last_supervisor_effect_dispositions"] = _safe_list(out.get("last_supervisor_effect_dispositions"))

    return out


__all__ = [
    "_derive_reply_mode_from_state",
    "_normalize_enabled_supervisor_skill_ids",
    "_normalize_filename",
    "_normalize_fs_read_scope",
    "_normalize_rel_path",
    "_normalize_reply_mode",
    "_normalize_room_float",
    "_normalize_room_int",
    "_normalize_room_mcp_overrides",
    "_normalize_room_state_for_output",
    "_normalize_supervisor_provider",
    "_normalize_supervisor_skill_strategy",
    "_safe_dict",
    "_safe_list",
    "_safe_str",
]
