from __future__ import annotations

from typing import Any, Dict, List, Optional

from .room_mcp_provider_contract import normalize_room_role_mcp_contract
from .room_role_runtime_common import (
    _normalize_id_list,
    _normalize_requested_mode,
    _safe_bool,
    _safe_dict,
    _safe_list,
    _safe_str,
)
from .room_role_runtime_mcp_binding import (
    _apply_mcp_contract_to_request_args,
    _merge_role_mcp_binding,
)
from .room_role_runtime_policy import (
    _extract_base_agent_config,
    _extract_role_knowledge_binding,
    _extract_role_tool_policy,
    _merge_role_mcp_overrides,
    _resolve_role_rag_mode,
)
from .room_store import get_room_owner_user_id, load_meta

def _sanitize_room_worker_request_args(
    request_args: Optional[Dict[str, Any]],
    room_id: str,
) -> Dict[str, Any]:
    local_request_args = dict(request_args or {})
    room_id_str = _safe_str(room_id)
    if not room_id_str:
        return local_request_args

    for key in ("conv_id", "chat_conv_id", "worker_chat_conv_id", "room_chat_conv_id"):
        if _safe_str(local_request_args.get(key)) == room_id_str:
            local_request_args.pop(key, None)

    for key in ("_room_id", "runtime_room_id", "worker_room_id", "execution_room_id"):
        inherited_room_id = _safe_str(local_request_args.get(key))
        if inherited_room_id and inherited_room_id != room_id_str:
            local_request_args[f"_outer_{key}"] = inherited_room_id

    local_request_args["room_id"] = room_id_str
    local_request_args["_room_id"] = room_id_str
    local_request_args["runtime_room_id"] = room_id_str
    local_request_args["worker_room_id"] = room_id_str
    local_request_args["execution_room_id"] = room_id_str

    return local_request_args


def _blank_room_shared_binding() -> Dict[str, Any]:
    return {
        "library_id": "",
        "doc_id": "",
        "group_id": "",
        "store_scope": "global",
        "evidence_scope": "global",
        "time_filter_days": "",
        "time_start": "",
        "time_end": "",
    }


def _extract_room_execution_context(
    *,
    room_id: str,
    request_args: Dict[str, Any],
    role: Dict[str, Any],
) -> Dict[str, Any]:
    req = _safe_dict(request_args)
    role_obj = _safe_dict(role)
    meta = _safe_dict(load_meta(room_id))

    actor_user_id = _safe_str(
        req.get("actor_user_id")
        or req.get("uid")
        or req.get("user_id")
        or req.get("sender")
        or req.get("sender_user_id")
    )

    room_owner_user_id = _safe_str(
        req.get("room_owner_user_id")
        or req.get("owner_user_id")
        or req.get("room_owner_id")
    ) or _safe_str(get_room_owner_user_id(meta))

    role_id = _safe_str(role_obj.get("role_id") or req.get("role_id"))
    role_name = _safe_str(role_obj.get("name") or role_obj.get("slug") or req.get("role_name") or role_id)
    role_owner_user_id = _safe_str(
        role_obj.get("owner_user_id")
        or req.get("role_owner_user_id")
    ) or room_owner_user_id

    if "shared_role_ids_snapshot" in req:
        shared_role_ids = _normalize_id_list(req.get("shared_role_ids_snapshot"))
    elif "shared_role_ids" in req:
        shared_role_ids = _normalize_id_list(req.get("shared_role_ids"))
    else:
        shared_role_ids = _normalize_id_list(meta.get("shared_role_ids"))

    if "shared_supervisor_enabled_snapshot" in req:
        shared_supervisor_enabled = _safe_bool(req.get("shared_supervisor_enabled_snapshot"), False)
    elif "shared_supervisor_enabled" in req:
        shared_supervisor_enabled = _safe_bool(req.get("shared_supervisor_enabled"), False)
    else:
        shared_supervisor_enabled = _safe_bool(meta.get("shared_supervisor_enabled"), False)

    if "shared_room_config_enabled_snapshot" in req:
        shared_room_config_enabled = _safe_bool(req.get("shared_room_config_enabled_snapshot"), False)
    elif "shared_room_config_enabled" in req:
        shared_room_config_enabled = _safe_bool(req.get("shared_room_config_enabled"), False)
    else:
        shared_room_config_enabled = _safe_bool(meta.get("shared_room_config_enabled"), False)

    is_supervisor = role_id == "supervisor" or role_name.lower() == "supervisor"
    actor_is_room_owner = bool(actor_user_id) and bool(room_owner_user_id) and actor_user_id == room_owner_user_id
    actor_is_role_owner = bool(actor_user_id) and bool(role_owner_user_id) and actor_user_id == role_owner_user_id
    role_shared_to_room = bool(role_id) and role_id in shared_role_ids
    supervisor_shared_to_room = bool(shared_supervisor_enabled)

    effective_execution_scope = _safe_str(req.get("effective_execution_scope"))
    if effective_execution_scope not in {"owner_private", "room_shared"}:
        if actor_is_room_owner or actor_is_role_owner:
            effective_execution_scope = "owner_private"
        elif (is_supervisor and supervisor_shared_to_room) or (not is_supervisor and role_shared_to_room):
            effective_execution_scope = "room_shared"
        else:
            effective_execution_scope = ""

    return {
        "actor_user_id": actor_user_id,
        "room_owner_user_id": room_owner_user_id,
        "role_owner_user_id": role_owner_user_id,
        "role_id": role_id,
        "role_name": role_name,
        "shared_role_ids": shared_role_ids,
        "shared_supervisor_enabled": shared_supervisor_enabled,
        "shared_room_config_enabled": shared_room_config_enabled,
        "role_shared_to_room": role_shared_to_room,
        "supervisor_shared_to_room": supervisor_shared_to_room,
        "actor_is_room_owner": actor_is_room_owner,
        "actor_is_role_owner": actor_is_role_owner,
        "effective_execution_scope": effective_execution_scope,
        "is_supervisor": is_supervisor,
    }


def _apply_room_share_runtime_policy(
    *,
    local_request_args: Dict[str, Any],
    role: Dict[str, Any],
    room_state: Dict[str, Any],
    execution_ctx: Dict[str, Any],
) -> Dict[str, Any]:
    out = dict(local_request_args or {})
    role_obj = _safe_dict(role)
    room_state_obj = _safe_dict(room_state)
    ctx = _safe_dict(execution_ctx)

    out["actor_user_id"] = _safe_str(ctx.get("actor_user_id"))
    out["room_owner_user_id"] = _safe_str(ctx.get("room_owner_user_id"))
    out["role_owner_user_id"] = _safe_str(ctx.get("role_owner_user_id"))
    out["actor_is_room_owner"] = _safe_bool(ctx.get("actor_is_room_owner"), False)
    out["shared_role_ids_snapshot"] = _normalize_id_list(ctx.get("shared_role_ids"))
    out["shared_supervisor_enabled_snapshot"] = _safe_bool(ctx.get("shared_supervisor_enabled"), False)
    out["shared_room_config_enabled_snapshot"] = _safe_bool(ctx.get("shared_room_config_enabled"), False)
    out["role_shared_to_room"] = _safe_bool(ctx.get("role_shared_to_room"), False)
    out["supervisor_shared_to_room"] = _safe_bool(ctx.get("supervisor_shared_to_room"), False)
    out["is_owner_actor"] = _safe_bool(ctx.get("actor_is_room_owner"), False)
    out["effective_execution_scope"] = _safe_str(ctx.get("effective_execution_scope"))
    out["runtime_scope_stripped"] = False
    out["stripped_fields"] = []

    owner_private = _safe_str(ctx.get("effective_execution_scope")) == "owner_private"
    if owner_private:
        return out

    stripped_fields: List[str] = []

    def _mark_stripped(field: str) -> None:
        if field not in stripped_fields:
            stripped_fields.append(field)

    out.pop("workspace_context", None)
    _mark_stripped("workspace_context")
    out["workspace_id"] = ""
    _mark_stripped("workspace_id")
    out["workspace_name"] = ""
    _mark_stripped("workspace_name")
    out["focus_root"] = ""
    _mark_stripped("focus_root")
    out["focus_label"] = ""
    _mark_stripped("focus_label")
    out["inherit_workspace_context"] = False
    _mark_stripped("inherit_workspace_context")
    out["inherit_focus_root"] = False
    _mark_stripped("inherit_focus_root")

    blank_binding = _blank_room_shared_binding()
    out["role_binding"] = dict(blank_binding)
    out["knowledge_binding"] = dict(blank_binding)
    out["binding"] = dict(blank_binding)
    out["binding_ready"] = False
    _mark_stripped("role_binding")
    _mark_stripped("knowledge_binding")
    _mark_stripped("binding")
    _mark_stripped("binding_ready")

    out["library_id"] = ""
    out["doc_id"] = ""
    out["group_id"] = ""
    out["store_scope"] = "global"
    out["evidence_scope"] = "global"
    out["time_filter_days"] = ""
    out["time_start"] = ""
    out["time_end"] = ""
    out["rag_store_scope"] = "global"
    out["rag_evidence_scope"] = "global"
    out["rag_context"] = {
        "libraryId": None,
        "docId": None,
        "group_id": None,
    }
    _mark_stripped("library_id")
    _mark_stripped("doc_id")
    _mark_stripped("group_id")
    _mark_stripped("store_scope")
    _mark_stripped("evidence_scope")
    _mark_stripped("time_filter_days")
    _mark_stripped("time_start")
    _mark_stripped("time_end")
    _mark_stripped("rag_store_scope")
    _mark_stripped("rag_evidence_scope")
    _mark_stripped("rag_context")

    mcp_overrides = dict(_safe_dict(out.get("mcp_overrides")))
    mcp_overrides["fsReadScope"] = "minimal"
    mcp_overrides["fsWriteScope"] = "none"
    mcp_overrides["fsDangerousEnabled"] = False
    out["mcp_overrides"] = mcp_overrides
    _mark_stripped("mcp_overrides.fsReadScope")
    _mark_stripped("mcp_overrides.fsWriteScope")
    _mark_stripped("mcp_overrides.fsDangerousEnabled")

    for key in (
        "memory_sidecar",
        "memory_sidecar_enabled",
        "memory_resume",
        "memory_resume_enabled",
        "notebook_context",
        "notebook_read_result",
        "notebook_enabled",
        "custom_supervisor_skills",
        "supervisor_skills",
        "workspace_context_snapshot",
        "focus_context",
    ):
        if key in out:
            out.pop(key, None)
            _mark_stripped(key)

    room_state_obj.pop("workspace_context", None)
    room_state_obj["workspace_id"] = ""
    room_state_obj["workspace_name"] = ""
    room_state_obj["focus_root"] = ""
    room_state_obj["focus_label"] = ""
    room_state_obj["inherit_workspace_context"] = False
    room_state_obj["inherit_focus_root"] = False

    role_obj.setdefault("owner_user_id", _safe_str(ctx.get("role_owner_user_id")))
    out["runtime_scope_stripped"] = bool(stripped_fields)
    out["stripped_fields"] = stripped_fields
    return out


def _build_role_runtime_request_args(
    *,
    request_args: Optional[Dict[str, Any]],
    role: Optional[Dict[str, Any]],
    room_state: Optional[Dict[str, Any]] = None,
    room_id: str = "",
) -> Dict[str, Any]:
    local_request_args = dict(request_args or {})
    role_obj = _safe_dict(role)
    room_state_obj = _safe_dict(room_state)

    tool_policy = _extract_role_tool_policy(role_obj)
    knowledge_binding = _extract_role_knowledge_binding(role_obj)

    mcp_contract = normalize_room_role_mcp_contract(role_obj, tool_policy)
    normalized_mcp_binding = _safe_dict(mcp_contract.get("mcp_binding"))
    mcp_provider_ids = _safe_list(mcp_contract.get("mcp_provider_ids"))
    mcp_provider_snapshot = _safe_dict(mcp_contract.get("mcp_provider_snapshot"))
    mcp_share_ref = _safe_str(mcp_contract.get("mcp_share_ref"))

    existing_mcp_binding = _safe_dict(local_request_args.get("mcp_binding"))
    mcp_binding = _merge_role_mcp_binding(
        normalized_binding=normalized_mcp_binding,
        existing_binding=existing_mcp_binding,
        request_args=local_request_args,
        contract_snapshot=mcp_provider_snapshot,
        contract_share_ref=mcp_share_ref,
    )

    requested_mode = _normalize_requested_mode(
        local_request_args.get("requested_mode")
        or local_request_args.get("rag_mode")
        or local_request_args.get("mode_used"),
        "off",
    )
    rag_mode = _resolve_role_rag_mode(
        request_args=local_request_args,
        tool_policy=tool_policy,
    )
    mcp_overrides = _merge_role_mcp_overrides(
        base_overrides=local_request_args.get("mcp_overrides"),
        tool_policy=tool_policy,
        mcp_binding=mcp_binding,
    )
    agent_config = _extract_base_agent_config(local_request_args)

    has_knowledge_binding = bool(
        knowledge_binding.get("library_id")
        or knowledge_binding.get("doc_id")
        or knowledge_binding.get("group_id")
    )
    role_rag_mode_for_agent_boundary = _safe_str(rag_mode or requested_mode).lower()
    retrieval_role_active = (
        role_rag_mode_for_agent_boundary in {"cite", "ground", "auto"}
        and has_knowledge_binding
        and not tool_policy.get("web")
        and not tool_policy.get("mcp")
        and not tool_policy.get("code")
    )

    if retrieval_role_active:
        agent_config["enabled"] = False
        agent_config["answerUsePlanner"] = False
    elif tool_policy.get("web") or tool_policy.get("mcp") or tool_policy.get("code"):
        agent_config["enabled"] = True

    enabled_role_tools = [key for key, enabled in tool_policy.items() if enabled]

    workspace_context = _safe_dict(room_state_obj.get("workspace_context"))
    if workspace_context:
        local_request_args.setdefault("workspace_context", workspace_context)

    for key in (
        "workspace_id",
        "workspace_name",
        "focus_root",
        "focus_label",
        "inherit_workspace_context",
        "inherit_focus_root",
    ):
        if key not in local_request_args and key in workspace_context:
            local_request_args[key] = workspace_context.get(key)
        if key not in local_request_args and key in room_state_obj:
            local_request_args[key] = room_state_obj.get(key)

    local_request_args["requested_mode"] = requested_mode
    local_request_args["rag_mode"] = rag_mode
    local_request_args["role_tools"] = enabled_role_tools
    local_request_args["role_tool_policy"] = tool_policy
    local_request_args["tool_policy"] = tool_policy

    local_request_args["role_binding"] = knowledge_binding
    local_request_args["knowledge_binding"] = knowledge_binding
    local_request_args["binding"] = knowledge_binding
    local_request_args["binding_ready"] = bool(
        knowledge_binding.get("library_id")
        or knowledge_binding.get("doc_id")
        or knowledge_binding.get("group_id")
        or _safe_str(mcp_binding.get("provider_id"))
        or _safe_str(mcp_binding.get("share_ref"))
    )

    local_request_args["library_id"] = knowledge_binding.get("library_id") or ""
    local_request_args["doc_id"] = knowledge_binding.get("doc_id") or ""
    local_request_args["group_id"] = knowledge_binding.get("group_id") or ""
    local_request_args["store_scope"] = knowledge_binding.get("store_scope") or "global"
    local_request_args["evidence_scope"] = knowledge_binding.get("evidence_scope") or "global"

    local_request_args["time_filter_days"] = knowledge_binding.get("time_filter_days") or ""
    local_request_args["time_start"] = knowledge_binding.get("time_start") or ""
    local_request_args["time_end"] = knowledge_binding.get("time_end") or ""

    local_request_args["rag_store_scope"] = knowledge_binding.get("store_scope") or "global"
    local_request_args["rag_evidence_scope"] = knowledge_binding.get("evidence_scope") or "global"
    local_request_args["rag_context"] = {
        "libraryId": knowledge_binding.get("library_id") or None,
        "docId": knowledge_binding.get("doc_id") or None,
        "group_id": knowledge_binding.get("group_id") or None,
    }

    local_request_args = _apply_mcp_contract_to_request_args(
        local_request_args=local_request_args,
        mcp_binding=mcp_binding,
        mcp_provider_ids=mcp_provider_ids,
        mcp_provider_snapshot=mcp_provider_snapshot,
        mcp_share_ref=mcp_share_ref,
    )

    local_request_args["mcp_overrides"] = mcp_overrides
    local_request_args["agent_config"] = agent_config
    local_request_args["agent_enabled"] = _safe_bool(agent_config.get("enabled"), False)
    local_request_args["planner_model"] = _safe_str(agent_config.get("plannerModel"), "gpt-4o-mini") or "gpt-4o-mini"
    local_request_args["planner_provider"] = _safe_str(agent_config.get("plannerProvider"), "openai") or "openai"
    local_request_args["max_steps"] = int(agent_config.get("maxSteps") or 0)
    local_request_args["agent_debug"] = _safe_bool(agent_config.get("debug"), False)
    local_request_args["answer_use_planner"] = _safe_bool(agent_config.get("answerUsePlanner"), False)

    if room_id:
        execution_ctx = _extract_room_execution_context(
            room_id=room_id,
            request_args=local_request_args,
            role=role_obj,
        )
        local_request_args = _apply_room_share_runtime_policy(
            local_request_args=local_request_args,
            role=role_obj,
            room_state=room_state_obj,
            execution_ctx=execution_ctx,
        )
        local_request_args = _sanitize_room_worker_request_args(
            local_request_args,
            room_id,
        )

    return local_request_args


__all__ = [
    "_sanitize_room_worker_request_args",
    "_blank_room_shared_binding",
    "_extract_room_execution_context",
    "_apply_room_share_runtime_policy",
    "_build_role_runtime_request_args",
]
