from __future__ import annotations

from datetime import datetime, timezone
from importlib import import_module
from typing import Any, Dict, List, Optional, Tuple
from uuid import uuid4

from .room_audit_helpers import (
    _set_room_state_patch as _audit_set_room_state_patch,
    _update_room_last_message as _audit_update_room_last_message,
)
from .room_role_runtime_request import (
    _call_room_ai_reply_packet,
    _generate_role_reply_packet,
    _normalize_reply_packet,
    _safe_dict,
    _safe_list,
    _safe_str,
    _sanitize_room_worker_request_args,
    _truncate_text,
)
from .room_state_normalizer import _normalize_supervisor_skill_strategy
from .room_supervisor_prompt_builders import (
    _build_supervisor_plan_summary,
    get_builtin_supervisor_skill_ids_for_prompt,
)
from .room_supervisor_runtime import (
    _augment_fs_context_with_file_read,
    _augment_plan_summary_with_notebook_read,
    _build_supervisor_runtime_request_args,
    _derive_supervisor_notebook_read_result,
    _maybe_run_supervisor_file_read,
    _normalize_room_mcp_overrides,
    _patch_supervisor_runtime_state,
    _run_supervisor_fs_read,
)
from .room_supervisor_skills import (
    build_enabled_supervisor_skills_prompt_block,
    build_supervisor_skills_payload,
)
from .supervisor_runtime.memory_resume import (
    augment_plan_summary_with_memory_resume,
    decide_supervisor_memory_resume,
    load_supervisor_memory_sidecar,
)

from .room_orchestrator_continuation import (
    _budget_patch,
    _build_step_budget_state,
    _consume_step_budget,
    _interrupt_supervisor_run,
)
from .room_orchestrator_delegate_flow import (
    _run_sequential_delegate_flow,
    _run_supervisor_delegate_flow,
)
from .room_orchestrator_supervisor_flow import _run_supervisor_synthesis_flow

ROOM_ROLE_NOT_SHARED = "ROOM_ROLE_NOT_SHARED"
ROOM_SUPERVISOR_NOT_SHARED = "ROOM_SUPERVISOR_NOT_SHARED"
ROOM_RUNTIME_OWNER_SCOPE_REQUIRED = "ROOM_RUNTIME_OWNER_SCOPE_REQUIRED"
ROOM_RUNTIME_SCOPE_STRIPPED = "ROOM_RUNTIME_SCOPE_STRIPPED"


def _load_module(relative_name: str):
    try:
        return import_module(relative_name, __package__)
    except Exception:
        return None


def _load_room_helpers_module():
    return _load_module(".room_helpers")


def _load_room_store_module():
    return _load_module(".room_store")


def _call_first_callable(module: Any, names: List[str], *args, **kwargs):
    if module is None:
        return None
    for name in names:
        fn = getattr(module, name, None)
        if callable(fn):
            return fn(*args, **kwargs)
    return None


def _orc_safe_bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    if isinstance(value, (int, float)):
        return bool(value)
    s = _safe_str(value).lower()
    if s in ("1", "true", "yes", "on", "y"):
        return True
    if s in ("0", "false", "no", "off", "n"):
        return False
    return default


def _orc_normalize_id_list(value: Any) -> List[str]:
    out: List[str] = []
    seen = set()
    for item in _safe_list(value):
        s = _safe_str(item)
        if not s or s in seen:
            continue
        seen.add(s)
        out.append(s)
    return out


def _orc_is_owner_actor(actor_user_id: str, room_owner_user_id: str) -> bool:
    return bool(actor_user_id) and bool(room_owner_user_id) and actor_user_id == room_owner_user_id


def _orc_extract_ctx(request_args: Dict[str, Any]) -> Dict[str, Any]:
    req = _safe_dict(request_args)
    actor_user_id = _safe_str(
        req.get("actor_user_id")
        or req.get("uid")
        or req.get("user_id")
        or req.get("sender_user_id")
        or req.get("sender")
        or req.get("current_user_id")
        or req.get("session_user_id")
    )
    room_owner_user_id = _safe_str(
        req.get("room_owner_user_id")
        or req.get("owner_user_id")
        or req.get("room_owner_id")
    )
    shared_role_ids_snapshot = _orc_normalize_id_list(
        req.get("shared_role_ids_snapshot")
        if "shared_role_ids_snapshot" in req
        else req.get("shared_role_ids")
    )
    shared_supervisor_enabled_snapshot = _orc_safe_bool(
        req.get("shared_supervisor_enabled_snapshot")
        if "shared_supervisor_enabled_snapshot" in req
        else req.get("shared_supervisor_enabled"),
        False,
    )
    actor_is_room_owner = _orc_safe_bool(
        req.get("actor_is_room_owner"),
        _orc_is_owner_actor(actor_user_id, room_owner_user_id),
    )
    return {
        "actor_user_id": actor_user_id,
        "room_owner_user_id": room_owner_user_id,
        "shared_role_ids_snapshot": shared_role_ids_snapshot,
        "shared_supervisor_enabled_snapshot": shared_supervisor_enabled_snapshot,
        "actor_is_room_owner": actor_is_room_owner,
        "effective_execution_scope": "owner_private" if actor_is_room_owner else "room_shared",
    }


def _orc_inject_ctx(request_args: Dict[str, Any], ctx: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(request_args or {})
    out["actor_user_id"] = _safe_str(ctx.get("actor_user_id"))
    out["room_owner_user_id"] = _safe_str(ctx.get("room_owner_user_id"))
    out["actor_is_room_owner"] = _orc_safe_bool(ctx.get("actor_is_room_owner"), False)
    out["is_owner_actor"] = _orc_safe_bool(ctx.get("actor_is_room_owner"), False)
    out["shared_role_ids_snapshot"] = list(_safe_list(ctx.get("shared_role_ids_snapshot")))
    out["shared_supervisor_enabled_snapshot"] = _orc_safe_bool(ctx.get("shared_supervisor_enabled_snapshot"), False)
    out["effective_execution_scope"] = _safe_str(ctx.get("effective_execution_scope"))
    return out


def _orc_role_allowed_for_actor(role_obj: Dict[str, Any], ctx: Dict[str, Any]) -> bool:
    role = _safe_dict(role_obj)
    role_id = _safe_str(role.get("role_id"))
    role_owner_user_id = _safe_str(role.get("owner_user_id") or ctx.get("room_owner_user_id"))
    actor_user_id = _safe_str(ctx.get("actor_user_id"))

    if _orc_safe_bool(ctx.get("actor_is_room_owner"), False):
        return True
    if actor_user_id and role_owner_user_id and actor_user_id == role_owner_user_id:
        return True
    return bool(role_id) and role_id in _orc_normalize_id_list(ctx.get("shared_role_ids_snapshot"))


def _orc_filter_active_roles_for_actor(active_roles: Any, ctx: Dict[str, Any]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for item in _safe_list(active_roles):
        role_obj = _safe_dict(item)
        if role_obj and _orc_role_allowed_for_actor(role_obj, ctx):
            out.append(role_obj)
    return out


def _orc_supervisor_allowed_for_actor(ctx: Dict[str, Any]) -> bool:
    if _orc_safe_bool(ctx.get("actor_is_room_owner"), False):
        return True
    return _orc_safe_bool(ctx.get("shared_supervisor_enabled_snapshot"), False)


def _orc_shared_room_supervisor_capability_enabled(
    *,
    ctx: Dict[str, Any],
    request_args: Dict[str, Any],
) -> bool:
    if _orc_safe_bool(ctx.get("actor_is_room_owner"), False):
        return True

    effective_scope = _safe_str(
        request_args.get("effective_execution_scope") or ctx.get("effective_execution_scope")
    )
    shared_room_config_enabled = _orc_safe_bool(
        request_args.get("shared_room_config_enabled_snapshot")
        or ctx.get("shared_room_config_enabled_snapshot"),
        False,
    )
    shared_supervisor_enabled = _orc_safe_bool(
        request_args.get("shared_supervisor_enabled_snapshot")
        or ctx.get("shared_supervisor_enabled_snapshot"),
        False,
    )

    return (
        effective_scope == "room_shared"
        and shared_room_config_enabled
        and shared_supervisor_enabled
    )


def _orc_strip_supervisor_private_scope(request_args: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(request_args or {})
    stripped_fields = list(_safe_list(out.get("stripped_fields")))

    def _mark(name: str) -> None:
        if name not in stripped_fields:
            stripped_fields.append(name)

    for key in (
        "knowledge_binding",
        "binding",
        "role_binding",
        "workspace_context_snapshot",
        "focus_context",
        "_supervisor_fs_read_text",
        "supervisor_fs_read_text",
        "notebook_context",
        "notebook_read_result",
        "memory_sidecar",
        "memory_resume",
    ):
        if key in out:
            out.pop(key, None)
            _mark(key)

    mcp_overrides = dict(_safe_dict(out.get("mcp_overrides")))
    mcp_overrides["fs_write_enabled"] = False
    mcp_overrides["fsWriteEnabled"] = False
    mcp_overrides["fsWriteScope"] = "none"
    mcp_overrides["fsDangerousEnabled"] = False
    out["mcp_overrides"] = mcp_overrides

    _mark("mcp_overrides.fs_write_enabled")
    _mark("mcp_overrides.fsWriteScope")
    _mark("mcp_overrides.fsDangerousEnabled")

    out["runtime_scope_stripped"] = bool(stripped_fields)
    out["stripped_fields"] = stripped_fields
    out["effective_execution_scope"] = "room_shared"
    return out


def _orc_strip_supervisor_private_room_state(room_state: Dict[str, Any]) -> Dict[str, Any]:
    state = dict(room_state or {})

    for key in (
        "notebook_context",
        "notebook_read_result",
        "memory_sidecar",
        "memory_resume",
    ):
        state.pop(key, None)

    mcp_overrides = dict(_safe_dict(state.get("mcp_overrides")))
    mcp_overrides["fs_write_enabled"] = False
    mcp_overrides["fsWriteEnabled"] = False
    mcp_overrides["fsWriteScope"] = "none"
    mcp_overrides["fsDangerousEnabled"] = False
    state["mcp_overrides"] = mcp_overrides
    return state


def _orc_mark_runtime_skipped(
    *,
    room_id: str,
    run_id: str,
    rid: str,
    reason_code: str,
) -> None:
    _set_room_state_patch(
        room_id,
        {
            "current_run_id": run_id,
            "current_request_id": rid,
            "current_run_status": "skipped",
            "runtime_control_run_id": run_id,
            "runtime_state_hint": "idle",
            "runtime_phase_hint": "idle",
            "current_delegate_role_id": "",
            "current_delegate_role_name": "",
            "current_delegate_index": 0,
            "current_delegate_total": 0,
            "last_run_finished_at": utc_iso(),
            "last_runtime_skip_reason": reason_code,
        },
    )


def _orc_disabled_fs_context(reason_code: str) -> Dict[str, Any]:
    return {
        "enabled": False,
        "status": "skipped",
        "reason": reason_code,
        "focus_root": "",
        "scope": "none",
        "documents_count": 0,
        "target_paths": [],
        "content_status": "disabled",
        "text": "",
        "tool_calls": [],
        "tool_results": [],
    }


def _orc_disabled_notebook_read_result(reason_code: str) -> Dict[str, Any]:
    return {
        "enabled": False,
        "status": "skipped",
        "message": reason_code,
        "relative_path": "",
        "documents_count": 0,
        "source_kind": "disabled",
        "tool_calls": [],
        "tool_results": [],
    }


def _orc_disabled_memory_read_result(reason_code: str) -> Dict[str, Any]:
    return {
        "enabled": False,
        "status": "skipped",
        "message": reason_code,
        "reason_code": reason_code,
        "relative_path": "",
        "source_kind": "disabled",
        "version": 0,
        "checkpoint": {},
        "resume": {},
        "tool_calls": [],
        "tool_results": [],
        "recorded_at": utc_iso(),
    }


def _orc_disabled_memory_resume_result(reason_code: str) -> Dict[str, Any]:
    return {
        "status": "skipped",
        "decision": "no_resume",
        "reason": reason_code,
        "resume_ready": False,
        "relative_path": "",
        "checkpoint_stage": "",
        "checkpoint_summary": "",
        "recovery_hint": "",
    }


def _orc_append_runtime_skipped_event(
    *,
    room_id: str,
    rid: str,
    run_id: str,
    trigger_event_id: str,
    question: str,
    path: str,
    reason_code: str,
    active_roles: List[Dict[str, Any]],
    request_args: Dict[str, Any],
) -> Dict[str, Any]:
    ctx = _orc_extract_ctx(request_args)
    evt = {
        "id": new_id("evt"),
        "ts": utc_iso(),
        "type": "room.runtime_skipped",
        "room_id": room_id,
        "request_id": rid,
        "run_id": run_id,
        "trigger_event_id": trigger_event_id,
        "payload": {
            "question": question,
            "path": path,
            "reason_code": reason_code,
            "actor_user_id": _safe_str(ctx.get("actor_user_id")),
            "room_owner_user_id": _safe_str(ctx.get("room_owner_user_id")),
            "actor_is_room_owner": _orc_safe_bool(ctx.get("actor_is_room_owner"), False),
            "shared_role_ids_snapshot": list(_safe_list(ctx.get("shared_role_ids_snapshot"))),
            "shared_supervisor_enabled_snapshot": _orc_safe_bool(
                ctx.get("shared_supervisor_enabled_snapshot"),
                False,
            ),
            "role_ids_considered": [_safe_str(_safe_dict(x).get("role_id")) for x in _safe_list(active_roles)],
        },
    }
    append_room_event(room_id, evt)
    touch_room_updated_at(room_id)
    _orc_mark_runtime_skipped(
        room_id=room_id,
        run_id=run_id,
        rid=rid,
        reason_code=reason_code,
    )
    return evt


def new_id(prefix: str = "id") -> str:
    helpers = _load_room_helpers_module()
    result = _call_first_callable(helpers, ["new_id", "_new_id"], prefix)
    if isinstance(result, str) and result.strip():
        return result

    prefix_text = _safe_str(prefix, "id") or "id"
    return f"{prefix_text}_{uuid4().hex[:12]}"


def utc_iso() -> str:
    helpers = _load_room_helpers_module()
    result = _call_first_callable(helpers, ["utc_iso", "_utc_iso"])
    if isinstance(result, str) and result.strip():
        return result

    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def load_state_doc(room_id: str) -> Dict[str, Any]:
    store = _load_room_store_module()
    result = _call_first_callable(store, ["load_state_doc", "get_state_doc"], room_id)
    return result if isinstance(result, dict) else {}


def append_room_event(room_id: str, event: Dict[str, Any]) -> Any:
    store = _load_room_store_module()
    return _call_first_callable(
        store,
        ["append_room_event", "append_event", "_append_room_event", "_append_event"],
        room_id,
        event,
    )


def touch_room_updated_at(room_id: str) -> Any:
    store = _load_room_store_module()
    return _call_first_callable(
        store,
        ["touch_room_updated_at", "_touch_room_updated_at", "touch_updated_at"],
        room_id,
    )


def _set_room_state_patch(room_id: str, patch: Dict[str, Any]) -> Any:
    store = _load_room_store_module()

    result = _call_first_callable(
        store,
        [
            "_set_room_state_patch",
            "set_room_state_patch",
            "_patch_room_state",
            "patch_room_state",
            "update_room_state_patch",
        ],
        room_id,
        patch,
    )
    if result is not None:
        return result

    result = _call_first_callable(
        store,
        [
            "update_state_doc",
            "_update_state_doc",
            "save_state_patch",
            "_save_state_patch",
        ],
        room_id,
        patch,
    )
    if result is not None:
        return result

    return _audit_set_room_state_patch(room_id, patch)


def _update_room_last_message(room_id: str, event_id: str) -> Any:
    store = _load_room_store_module()
    result = _call_first_callable(
        store,
        [
            "_update_room_last_message",
            "update_room_last_message",
            "set_room_last_message",
            "_set_room_last_message",
        ],
        room_id,
        event_id,
    )
    if result is not None:
        return result

    return _audit_update_room_last_message(room_id, event_id)


def _clear_run_state(room_id: str) -> Any:
    store = _load_room_store_module()

    result = _call_first_callable(
        store,
        [
            "_clear_run_state",
            "clear_run_state",
            "_reset_run_state",
            "reset_run_state",
        ],
        room_id,
    )
    if result is not None:
        return result

    return _set_room_state_patch(
        room_id,
        {
            "current_delegate_role_id": "",
            "current_delegate_role_name": "",
            "current_delegate_index": 0,
            "current_delegate_total": 0,
        },
    )


def _run_sequential_orchestration(
    *,
    room_id: str,
    question: str,
    active_roles: List[Dict[str, Any]],
    model_name: str,
    mode_used: str,
    run_id: str,
    trigger_event_id: str,
    rid: str,
    request_args: Dict[str, Any],
) -> List[Dict[str, Any]]:
    local_request_args = _orc_inject_ctx(request_args, _orc_extract_ctx(request_args))
    ctx = _orc_extract_ctx(local_request_args)

    authorized_active_roles = _orc_filter_active_roles_for_actor(active_roles, ctx)
    local_request_args["authorized_active_role_ids_snapshot"] = [
        _safe_str(_safe_dict(x).get("role_id")) for x in authorized_active_roles
    ]

    if not _orc_safe_bool(ctx.get("actor_is_room_owner"), False) and not authorized_active_roles:
        _orc_append_runtime_skipped_event(
            room_id=room_id,
            rid=rid,
            run_id=run_id,
            trigger_event_id=trigger_event_id,
            question=question,
            path="sequential_orchestration",
            reason_code=ROOM_ROLE_NOT_SHARED,
            active_roles=active_roles,
            request_args=local_request_args,
        )
        _clear_run_state(room_id)
        return []

    return _run_sequential_delegate_flow(
        room_id=room_id,
        question=question,
        active_roles=authorized_active_roles,
        model_name=model_name,
        mode_used=mode_used,
        run_id=run_id,
        trigger_event_id=trigger_event_id,
        rid=rid,
        request_args=local_request_args,
        set_room_state_patch_fn=_set_room_state_patch,
        append_room_event_fn=append_room_event,
        touch_room_updated_at_fn=touch_room_updated_at,
        update_room_last_message_fn=_update_room_last_message,
        clear_run_state_fn=_clear_run_state,
        new_id_fn=new_id,
        utc_iso_fn=utc_iso,
    )


def _run_supervisor_orchestration(
    *,
    room_id: str,
    question: str,
    active_roles: List[Dict[str, Any]],
    model_name: str,
    mode_used: str,
    run_id: str,
    trigger_event_id: str,
    rid: str,
    request_args: Dict[str, Any],
) -> Tuple[Dict[str, Any], List[Dict[str, Any]], Dict[str, Any]]:
    local_request_args = _orc_inject_ctx(request_args, _orc_extract_ctx(request_args))
    ctx = _orc_extract_ctx(local_request_args)

    authorized_active_roles = _orc_filter_active_roles_for_actor(active_roles, ctx)
    local_request_args["authorized_active_role_ids_snapshot"] = [
        _safe_str(_safe_dict(x).get("role_id")) for x in authorized_active_roles
    ]

    if not _orc_supervisor_allowed_for_actor(ctx):
        _orc_append_runtime_skipped_event(
            room_id=room_id,
            rid=rid,
            run_id=run_id,
            trigger_event_id=trigger_event_id,
            question=question,
            path="supervisor_orchestration",
            reason_code=ROOM_SUPERVISOR_NOT_SHARED,
            active_roles=active_roles,
            request_args=local_request_args,
        )
        _clear_run_state(room_id)
        return {}, [], {}

    if not _orc_safe_bool(ctx.get("actor_is_room_owner"), False) and not authorized_active_roles:
        _orc_append_runtime_skipped_event(
            room_id=room_id,
            rid=rid,
            run_id=run_id,
            trigger_event_id=trigger_event_id,
            question=question,
            path="supervisor_orchestration",
            reason_code=ROOM_ROLE_NOT_SHARED,
            active_roles=active_roles,
            request_args=local_request_args,
        )
        _clear_run_state(room_id)
        return {}, [], {}

    room_state = _safe_dict(load_state_doc(room_id))
    local_room_state = dict(room_state)

    actor_is_owner = _orc_safe_bool(ctx.get("actor_is_room_owner"), False)
    if not actor_is_owner:
        local_request_args = _orc_strip_supervisor_private_scope(local_request_args)
        local_room_state = _orc_strip_supervisor_private_room_state(local_room_state)

    worker_request_args = _sanitize_room_worker_request_args(local_request_args, room_id)
    supervisor_request_args = _build_supervisor_runtime_request_args(
        state=local_room_state,
        request_args=worker_request_args,
    )

    if not _safe_str(supervisor_request_args.get("effective_execution_scope")):
        supervisor_request_args["effective_execution_scope"] = _safe_str(
            local_request_args.get("effective_execution_scope") or ctx.get("effective_execution_scope"),
            "room_shared" if not actor_is_owner else "owner",
        )

    for key in (
        "shared_room_config_enabled_snapshot",
        "shared_supervisor_enabled_snapshot",
        "authorized_active_role_ids_snapshot",
    ):
        if key in local_request_args and key not in supervisor_request_args:
            supervisor_request_args[key] = local_request_args.get(key)

    total = len(authorized_active_roles)

    step_budget = _build_step_budget_state(local_room_state, supervisor_request_args)
    supervisor_request_args["supervisor_step_budget_total"] = step_budget["step_budget_total"]
    supervisor_request_args["supervisor_step_budget_used"] = step_budget["step_budget_used"]
    supervisor_request_args["supervisor_step_budget_remaining"] = step_budget["step_budget_remaining"]
    supervisor_request_args["supervisor_budget_status"] = step_budget["budget_status"]
    supervisor_request_args["supervisor_budget_exhausted"] = step_budget["budget_exhausted"]

    mcp = _normalize_room_mcp_overrides(
        supervisor_request_args.get("mcp_overrides") or local_room_state.get("mcp_overrides")
    )
    supervisor_request_args["mcp_overrides"] = dict(mcp)

    supervisor_skill_strategy = _normalize_supervisor_skill_strategy(
        supervisor_request_args.get("supervisor_skill_strategy")
        or local_room_state.get("supervisor_skill_strategy"),
        "builtin_plus_custom",
    )
    synthesis_builtin_skill_ids = get_builtin_supervisor_skill_ids_for_prompt(
        "synthesis",
        supervisor_skill_strategy,
    )

    _patch_supervisor_runtime_state(
        room_id,
        phase="planning",
        status="running",
        request_args=supervisor_request_args,
        run_id=run_id,
        step_budget_total=step_budget["step_budget_total"],
        step_budget_used=step_budget["step_budget_used"],
        step_budget_remaining=step_budget["step_budget_remaining"],
        budget_status=step_budget["budget_status"],
        budget_exhausted=step_budget["budget_exhausted"],
    )

    shared_supervisor_capability_enabled = _orc_shared_room_supervisor_capability_enabled(
        ctx=ctx,
        request_args=supervisor_request_args,
    )

    if shared_supervisor_capability_enabled:
        fs_context = _run_supervisor_fs_read(
            room_id=room_id,
            request_args=supervisor_request_args,
            run_id=run_id,
        )

        notebook_read_info: Dict[str, Any] = {}
        memory_read_info: Dict[str, Any] = {}
        memory_resume_info: Dict[str, Any] = {}

        file_read_result = _maybe_run_supervisor_file_read(
            room_id=room_id,
            question=question,
            request_args=supervisor_request_args,
            fs_context=fs_context,
            run_id=run_id,
        )
        if file_read_result:
            fs_context = _augment_fs_context_with_file_read(
                fs_context=fs_context,
                file_read_result=file_read_result,
            )
            notebook_read_info = _derive_supervisor_notebook_read_result(
                file_read_result=file_read_result,
                mcp=mcp,
            )

        try:
            memory_read_info = load_supervisor_memory_sidecar(
                room_id=room_id,
                mcp=mcp,
            )
            memory_resume_info = decide_supervisor_memory_resume(
                question=question,
                memory_read_result=memory_read_info,
            )
        except Exception as ex:
            memory_read_info = {
                "enabled": bool(
                    mcp.get("memory_write_enabled")
                    or mcp.get("memoryWriteEnabled")
                    or local_room_state.get("memory_sidecar_enabled")
                ),
                "status": "error",
                "message": f"supervisor memory read failed: {type(ex).__name__}",
                "reason_code": "SUPERVISOR_MEMORY_READ_EXCEPTION",
                "relative_path": "",
                "source_kind": "sidecar",
                "version": 0,
                "checkpoint": {},
                "resume": {},
                "tool_calls": [],
                "tool_results": [],
                "recorded_at": utc_iso(),
            }
            memory_resume_info = {
                "status": "skipped",
                "decision": "no_resume",
                "reason": "memory_read_error",
                "resume_ready": False,
                "relative_path": "",
                "checkpoint_stage": "",
                "checkpoint_summary": "",
                "recovery_hint": "",
            }
    else:
        fs_context = _orc_disabled_fs_context(ROOM_RUNTIME_SCOPE_STRIPPED)
        notebook_read_info = _orc_disabled_notebook_read_result(ROOM_RUNTIME_SCOPE_STRIPPED)
        memory_read_info = _orc_disabled_memory_read_result(ROOM_RUNTIME_SCOPE_STRIPPED)
        memory_resume_info = _orc_disabled_memory_resume_result(ROOM_RUNTIME_SCOPE_STRIPPED)

    fs_read_text = _safe_str(fs_context.get("text"))
    worker_request_args["_supervisor_fs_read_text"] = fs_read_text
    worker_request_args["supervisor_fs_read_text"] = fs_read_text
    supervisor_request_args["_supervisor_fs_read_text"] = fs_read_text
    supervisor_request_args["supervisor_fs_read_text"] = fs_read_text

    supervisor_request_args["supervisor_memory_read"] = dict(memory_read_info)
    supervisor_request_args["supervisor_memory_resume"] = dict(memory_resume_info)

    plan_summary = _build_supervisor_plan_summary(
        question=question,
        active_roles=authorized_active_roles,
        fs_context=fs_context,
    )
    plan_summary = _augment_plan_summary_with_notebook_read(
        plan_summary,
        notebook_read_info,
    )
    plan_summary = augment_plan_summary_with_memory_resume(
        plan_summary,
        memory_read_info,
        memory_resume_info,
    )

    supervisor_notebook_read_payload = {
        "enabled": bool(notebook_read_info.get("enabled")),
        "status": _safe_str(notebook_read_info.get("status")),
        "message": _safe_str(notebook_read_info.get("message")),
        "relative_path": _safe_str(notebook_read_info.get("relative_path")),
        "documents_count": int(notebook_read_info.get("documents_count") or 0),
        "source_kind": _safe_str(notebook_read_info.get("source_kind")),
        "tool_calls": _safe_list(notebook_read_info.get("tool_calls")),
        "tool_results": _safe_list(notebook_read_info.get("tool_results")),
    }

    memory_checkpoint = _safe_dict(memory_read_info.get("checkpoint"))
    memory_resume_from_read = _safe_dict(memory_read_info.get("resume"))

    supervisor_memory_read_payload = {
        "enabled": bool(memory_read_info.get("enabled")),
        "status": _safe_str(memory_read_info.get("status")),
        "message": _safe_str(memory_read_info.get("message")),
        "reason_code": _safe_str(memory_read_info.get("reason_code")),
        "relative_path": _safe_str(memory_read_info.get("relative_path")),
        "source_kind": _safe_str(memory_read_info.get("source_kind")),
        "version": int(memory_read_info.get("version") or 0),
        "checkpoint": {
            "stage": _safe_str(memory_checkpoint.get("stage")),
            "summary": _safe_str(memory_checkpoint.get("summary")),
            "last_step": _safe_str(memory_checkpoint.get("last_step")),
            "recovery_hint": _safe_str(memory_checkpoint.get("recovery_hint")),
        },
        "resume": {
            "resume_ready": bool(memory_resume_from_read.get("resume_ready")),
        },
        "tool_calls": _safe_list(memory_read_info.get("tool_calls")),
        "tool_results": _safe_list(memory_read_info.get("tool_results")),
    }

    supervisor_memory_resume_payload = {
        "status": _safe_str(memory_resume_info.get("status")),
        "decision": _safe_str(memory_resume_info.get("decision")),
        "reason": _safe_str(memory_resume_info.get("reason")),
        "resume_ready": bool(memory_resume_info.get("resume_ready")),
        "relative_path": _safe_str(memory_resume_info.get("relative_path")),
        "checkpoint_stage": _safe_str(memory_resume_info.get("checkpoint_stage")),
        "checkpoint_summary": _safe_str(memory_resume_info.get("checkpoint_summary")),
        "recovery_hint": _safe_str(memory_resume_info.get("recovery_hint")),
    }

    supervisor_skills_info = build_enabled_supervisor_skills_prompt_block(
        room_id=room_id,
        state=local_room_state,
        request_args=supervisor_request_args,
        enabled_skill_ids=local_room_state.get("enabled_supervisor_skill_ids"),
        strategy=supervisor_skill_strategy,
    )
    supervisor_skills_info = dict(_safe_dict(supervisor_skills_info))
    supervisor_skills_info["strategy"] = _safe_str(
        supervisor_skills_info.get("strategy") or supervisor_skill_strategy,
        "builtin_plus_custom",
    )
    supervisor_skills_info["supervisor_skill_strategy"] = supervisor_skills_info["strategy"]
    supervisor_skills_info["builtin_skill_ids"] = list(synthesis_builtin_skill_ids)
    supervisor_skills_info["applied_builtin_skill_ids"] = list(synthesis_builtin_skill_ids)
    supervisor_skills_info["custom_skill_ids"] = _safe_list(supervisor_skills_info.get("custom_skill_ids"))
    supervisor_skills_info["applied_custom_skill_ids"] = _safe_list(
        supervisor_skills_info.get("applied_custom_skill_ids")
        or supervisor_skills_info.get("applied_skill_ids")
    )
    supervisor_skills_info["applied_prompt_skill_ids"] = _safe_list(
        supervisor_skills_info.get("applied_prompt_skill_ids")
        or supervisor_skills_info.get("applied_skill_ids")
    )
    supervisor_skills_info["prompt_block_len_debug"] = len(
        _safe_str(supervisor_skills_info.get("prompt_block"))
    )
    supervisor_skills_payload = build_supervisor_skills_payload(supervisor_skills_info)

    _patch_supervisor_runtime_state(
        room_id,
        phase="grounding",
        status=_safe_str(fs_context.get("status"), "running"),
        plan_summary=plan_summary,
        fs_context=fs_context,
        notebook_read_result=notebook_read_info,
        memory_read_result=memory_read_info,
        memory_resume_result=memory_resume_info,
        request_args=supervisor_request_args,
        run_id=run_id,
        step_budget_total=step_budget["step_budget_total"],
        step_budget_used=step_budget["step_budget_used"],
        step_budget_remaining=step_budget["step_budget_remaining"],
        budget_status=step_budget["budget_status"],
        budget_exhausted=step_budget["budget_exhausted"],
    )

    _set_room_state_patch(
        room_id,
        {
            "current_run_id": run_id,
            "current_run_status": "running",
            "last_plan_summary": plan_summary,
            "last_plan_at": utc_iso(),
            "current_delegate_role_id": "",
            "current_delegate_role_name": "",
            "current_delegate_index": 0,
            "current_delegate_total": total,
            **_budget_patch(step_budget),
        },
    )

    plan_evt: Dict[str, Any] = {
        "id": new_id("evt"),
        "ts": utc_iso(),
        "type": "room.plan",
        "room_id": room_id,
        "request_id": rid,
        "run_id": run_id,
        "trigger_event_id": trigger_event_id,
        "payload": {
            "question": question,
            "plan_summary": plan_summary,
            "role_ids": [_safe_str(r.get("role_id")) for r in authorized_active_roles],
            "reply_mode": "supervisor",
            "supervisor_skill_strategy": _safe_str(
                supervisor_skills_info.get("strategy") or supervisor_skill_strategy,
                "builtin_plus_custom",
            ),
            "supervisor_fs_read": {
                "enabled": bool(fs_context.get("enabled")),
                "status": _safe_str(fs_context.get("status")),
                "reason": _safe_str(fs_context.get("reason")),
                "focus_root": _safe_str(fs_context.get("focus_root")),
                "scope": _safe_str(fs_context.get("scope")),
                "documents_count": int(fs_context.get("documents_count") or 0),
                "target_paths": _safe_list(fs_context.get("target_paths")),
                "content_status": _safe_str(fs_context.get("content_status")),
                "tool_calls": _safe_list(fs_context.get("tool_calls")),
                "tool_results": _safe_list(fs_context.get("tool_results")),
            },
            "supervisor_notebook_read": dict(supervisor_notebook_read_payload),
            "supervisor_memory_read": dict(supervisor_memory_read_payload),
            "supervisor_memory_resume": dict(supervisor_memory_resume_payload),
            "supervisor_skills": dict(supervisor_skills_payload),
        },
    }
    append_room_event(room_id, plan_evt)

    delegate_result = _run_supervisor_delegate_flow(
        room_id=room_id,
        question=question,
        active_roles=authorized_active_roles,
        model_name=model_name,
        mode_used=mode_used,
        run_id=run_id,
        plan_evt_id=plan_evt["id"],
        rid=rid,
        plan_summary=plan_summary,
        worker_request_args=worker_request_args,
        supervisor_request_args=supervisor_request_args,
        step_budget=step_budget,
        total=total,
        fs_context=fs_context,
        notebook_read_info=notebook_read_info,
        memory_read_info=memory_read_info,
        memory_resume_info=memory_resume_info,
        consume_step_budget_fn=_consume_step_budget,
        budget_patch_fn=_budget_patch,
        interrupt_supervisor_run_fn=_interrupt_supervisor_run,
        set_room_state_patch_fn=_set_room_state_patch,
        append_room_event_fn=append_room_event,
        touch_room_updated_at_fn=touch_room_updated_at,
        update_room_last_message_fn=_update_room_last_message,
        new_id_fn=new_id,
        utc_iso_fn=utc_iso,
    )
    if delegate_result.get("interrupted"):
        return delegate_result["result"]

    return _run_supervisor_synthesis_flow(
        room_id=room_id,
        question=question,
        model_name=model_name,
        mode_used=mode_used,
        run_id=run_id,
        trigger_event_id=trigger_event_id,
        rid=rid,
        plan_evt=plan_evt,
        total=total,
        mcp=mcp,
        fs_context=fs_context,
        notebook_read_info=notebook_read_info,
        memory_read_info=memory_read_info,
        memory_resume_info=memory_resume_info,
        supervisor_request_args=supervisor_request_args,
        delegate_events=delegate_result["delegate_events"],
        role_message_events=delegate_result["role_message_events"],
        delegate_packets=delegate_result["delegate_packets"],
        plan_summary=plan_summary,
        step_budget=delegate_result["step_budget"],
        supervisor_skill_strategy=supervisor_skill_strategy,
        supervisor_skills_info=supervisor_skills_info,
        supervisor_skills_payload=supervisor_skills_payload,
        supervisor_notebook_read_payload=supervisor_notebook_read_payload,
        supervisor_memory_read_payload=supervisor_memory_read_payload,
        supervisor_memory_resume_payload=supervisor_memory_resume_payload,
        consume_step_budget_fn=_consume_step_budget,
        budget_patch_fn=_budget_patch,
        interrupt_supervisor_run_fn=_interrupt_supervisor_run,
        set_room_state_patch_fn=_set_room_state_patch,
        append_room_event_fn=append_room_event,
        touch_room_updated_at_fn=touch_room_updated_at,
        update_room_last_message_fn=_update_room_last_message,
        clear_run_state_fn=_clear_run_state,
        load_state_doc_fn=load_state_doc,
        new_id_fn=new_id,
        utc_iso_fn=utc_iso,
    )


__all__ = [
    "_run_sequential_orchestration",
    "_run_supervisor_orchestration",
    "_generate_role_reply_packet",
    "_call_room_ai_reply_packet",
    "_normalize_reply_packet",
    "_sanitize_room_worker_request_args",
    "_safe_str",
    "_safe_list",
    "_safe_dict",
    "_truncate_text",
    "_set_room_state_patch",
    "_clear_run_state",
    "_update_room_last_message",
]
