from __future__ import annotations

from typing import Any, Dict, List, Optional

from .room_tool_common import _build_tool_result_item


def _rt_safe_str(value: Any, default: str = "") -> str:
    if value is None:
        return default
    try:
        s = str(value).strip()
        return s if s else default
    except Exception:
        return default


def _rt_safe_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _rt_safe_list(value: Any) -> List[Any]:
    return value if isinstance(value, list) else []


def _rt_safe_bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    if isinstance(value, (int, float)):
        return bool(value)
    s = _rt_safe_str(value).lower()
    if s in ("1", "true", "yes", "on", "y"):
        return True
    if s in ("0", "false", "no", "off", "n"):
        return False
    return default


def _rt_safe_query_str(value: Any, default: str = "") -> str:
    s = _rt_safe_str(value, default)
    if s == "{{user_query}}":
        return default
    return s


def _rt_normalize_id_list(value: Any) -> List[str]:
    out: List[str] = []
    seen = set()
    for item in _rt_safe_list(value):
        s = _rt_safe_str(item)
        if not s or s in seen:
            continue
        seen.add(s)
        out.append(s)
    return out


def _rt_resolve_request_question(args: Dict[str, Any], fallback: str = "") -> str:
    req = _rt_safe_dict(args)
    mcp_binding = _rt_safe_dict(req.get("mcp_binding"))
    params = _rt_safe_dict(mcp_binding.get("params"))

    for candidate in (
        fallback,
        req.get("question"),
        req.get("content"),
        req.get("prompt"),
        req.get("message"),
        req.get("_user_question"),
        params.get("question"),
        params.get("content"),
        params.get("prompt"),
        params.get("message"),
    ):
        value = _rt_safe_query_str(candidate)
        if value:
            return value
    return ""


def _rt_apply_question_aliases(args: Dict[str, Any], question: str) -> Dict[str, Any]:
    req = dict(_rt_safe_dict(args))
    resolved_question = _rt_safe_str(question)
    if not resolved_question:
        return req

    req["question"] = resolved_question
    req["content"] = resolved_question
    req["prompt"] = resolved_question
    req["message"] = resolved_question
    req["_user_question"] = resolved_question
    return req


def _rt_apply_mcp_binding_question_aliases(
    mcp_binding: Dict[str, Any],
    *,
    question: str,
    provider_id: str = "",
    provider_type: str = "",
    provider_origin: str = "",
) -> Dict[str, Any]:
    binding = dict(_rt_safe_dict(mcp_binding))
    params = dict(_rt_safe_dict(binding.get("params")))
    resolved_question = _rt_safe_str(question)

    if resolved_question:
        params["question"] = resolved_question
        params["content"] = resolved_question
        params["prompt"] = resolved_question
        params["message"] = resolved_question

    if provider_id and not _rt_safe_str(binding.get("provider_id")):
        binding["provider_id"] = _rt_safe_str(provider_id)

    if provider_type and not _rt_safe_str(binding.get("provider_type")):
        binding["provider_type"] = _rt_safe_str(provider_type)

    if provider_origin and not _rt_safe_str(binding.get("provider_origin")):
        binding["provider_origin"] = _rt_safe_str(provider_origin)

    binding["params"] = params
    return binding

def _rt_extract_provider_bridge_share_ref(
    args: Dict[str, Any],
    provider_info: Optional[Dict[str, Any]] = None,
) -> str:
    req = _rt_safe_dict(args)
    info = _rt_safe_dict(provider_info)
    mcp_binding = _rt_safe_dict(req.get("mcp_binding"))
    provider_snapshot = _rt_safe_dict(
        req.get("mcp_provider_snapshot")
        or req.get("provider_snapshot")
        or mcp_binding.get("provider_snapshot")
    )
    imported_provider = _rt_safe_dict(
        req.get("imported_provider")
        or mcp_binding.get("imported_provider")
    )
    room_source = _rt_safe_dict(info.get("room_source"))

    return _rt_safe_str(
        req.get("mcp_share_ref")
        or req.get("share_ref")
        or mcp_binding.get("share_ref")
        or provider_snapshot.get("share_ref")
        or imported_provider.get("share_ref")
        or room_source.get("share_ref")
        or info.get("share_ref")
    )


def _rt_extract_provider_bridge_grant_meta(
    args: Dict[str, Any],
    provider_info: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    req = _rt_safe_dict(args)
    info = _rt_safe_dict(provider_info)
    if _rt_safe_dict(info.get("_grant_meta")):
        return _rt_safe_dict(info.get("_grant_meta"))

    mcp_binding = _rt_safe_dict(req.get("mcp_binding"))
    provider_snapshot = _rt_safe_dict(
        req.get("mcp_provider_snapshot")
        or req.get("provider_snapshot")
        or mcp_binding.get("provider_snapshot")
    )
    imported_provider = _rt_safe_dict(
        req.get("imported_provider")
        or mcp_binding.get("imported_provider")
    )

    for candidate in (
        req.get("_room_mcp_grant"),
        req.get("grant_meta"),
        req.get("grant"),
        mcp_binding.get("grant_meta"),
        mcp_binding.get("grant"),
        provider_snapshot.get("grant_meta"),
        provider_snapshot.get("grant"),
        imported_provider.get("grant_meta"),
        imported_provider.get("grant"),
    ):
        obj = _rt_safe_dict(candidate)
        if obj:
            return obj

    return {}

def _rt_is_owner_actor(actor_user_id: str, room_owner_user_id: str) -> bool:
    return bool(actor_user_id) and bool(room_owner_user_id) and actor_user_id == room_owner_user_id


def _rt_extract_actor_user_id(request_args: Dict[str, Any], payload: Optional[Dict[str, Any]] = None) -> str:
    req = _rt_safe_dict(request_args)
    body = _rt_safe_dict(payload)

    peer_id = _rt_safe_str(
        req.get("_federation_peer_id")
        or body.get("_federation_peer_id")
        or req.get("federation_peer_id")
        or body.get("federation_peer_id")
        or req.get("remote_peer_id")
        or body.get("remote_peer_id")
    )
    remote_user_id = _rt_safe_str(
        req.get("_federation_remote_user_id")
        or body.get("_federation_remote_user_id")
        or req.get("federation_remote_user_id")
        or body.get("federation_remote_user_id")
        or req.get("remote_user_id")
        or body.get("remote_user_id")
    )

    if peer_id and remote_user_id:
        return f"fed__{peer_id}__{remote_user_id}"

    for key in (
        "actor_user_id",
        "uid",
        "user_id",
        "sender_user_id",
        "sender",
        "current_user_id",
        "session_user_id",
        "_room_mcp_actor_user_id",
    ):
        val = _rt_safe_str(req.get(key) or body.get(key))
        if val:
            return val
    return ""


def _rt_extract_room_owner_user_id(meta: Dict[str, Any], room_state: Dict[str, Any]) -> str:
    meta_obj = _rt_safe_dict(meta)
    state = _rt_safe_dict(room_state)
    return _rt_safe_str(
        state.get("owner_user_id")
        or state.get("room_owner_user_id")
        or meta_obj.get("owner_user_id")
    )


def _rt_extract_shared_role_ids_snapshot(meta: Dict[str, Any], room_state: Dict[str, Any]) -> List[str]:
    meta_obj = _rt_safe_dict(meta)
    state = _rt_safe_dict(room_state)

    meta_ids = _rt_normalize_id_list(meta_obj.get("shared_role_ids"))
    if meta_ids:
        return meta_ids

    return _rt_normalize_id_list(state.get("shared_role_ids"))


def _rt_extract_shared_supervisor_enabled_snapshot(meta: Dict[str, Any], room_state: Dict[str, Any]) -> bool:
    meta_obj = _rt_safe_dict(meta)
    state = _rt_safe_dict(room_state)

    if "shared_supervisor_enabled" in meta_obj:
        return _rt_safe_bool(meta_obj.get("shared_supervisor_enabled"), False)

    return _rt_safe_bool(state.get("shared_supervisor_enabled"), False)


def _rt_extract_shared_room_config_enabled_snapshot(meta: Dict[str, Any], room_state: Dict[str, Any]) -> bool:
    meta_obj = _rt_safe_dict(meta)
    state = _rt_safe_dict(room_state)

    if "shared_room_config_enabled" in meta_obj:
        return _rt_safe_bool(meta_obj.get("shared_room_config_enabled"), False)

    return _rt_safe_bool(state.get("shared_room_config_enabled"), False)


def _rt_build_execution_context(
    *,
    request_args: Dict[str, Any],
    meta: Dict[str, Any],
    room_state: Dict[str, Any],
    payload: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    meta_obj = _rt_safe_dict(meta)
    state_obj = _rt_safe_dict(room_state)

    actor_user_id = _rt_extract_actor_user_id(request_args, payload)
    room_owner_user_id = _rt_extract_room_owner_user_id(meta_obj, state_obj)
    shared_role_ids_snapshot = _rt_extract_shared_role_ids_snapshot(meta_obj, state_obj)
    shared_supervisor_enabled_snapshot = _rt_extract_shared_supervisor_enabled_snapshot(meta_obj, state_obj)
    shared_room_config_enabled_snapshot = _rt_extract_shared_room_config_enabled_snapshot(meta_obj, state_obj)
    actor_is_room_owner = _rt_is_owner_actor(actor_user_id, room_owner_user_id)

    effective_execution_scope = "owner_private" if actor_is_room_owner else "room_shared"

    execution_user_id = actor_user_id
    if (
        not actor_is_room_owner
        and shared_room_config_enabled_snapshot
        and room_owner_user_id
    ):
        execution_user_id = room_owner_user_id

    return {
        "actor_user_id": actor_user_id,
        "room_owner_user_id": room_owner_user_id,
        "actor_is_room_owner": actor_is_room_owner,
        "shared_role_ids_snapshot": shared_role_ids_snapshot,
        "shared_supervisor_enabled_snapshot": shared_supervisor_enabled_snapshot,
        "shared_room_config_enabled_snapshot": shared_room_config_enabled_snapshot,
        "shared_role_ids_meta": _rt_normalize_id_list(meta_obj.get("shared_role_ids")),
        "shared_role_ids_state": _rt_normalize_id_list(state_obj.get("shared_role_ids")),
        "shared_supervisor_enabled_meta": _rt_safe_bool(meta_obj.get("shared_supervisor_enabled"), False),
        "shared_supervisor_enabled_state": _rt_safe_bool(state_obj.get("shared_supervisor_enabled"), False),
        "shared_room_config_enabled_meta": _rt_safe_bool(meta_obj.get("shared_room_config_enabled"), False),
        "shared_room_config_enabled_state": _rt_safe_bool(state_obj.get("shared_room_config_enabled"), False),
        "effective_execution_scope": effective_execution_scope,
        "execution_user_id": execution_user_id,
        "fs_owner_user_id": room_owner_user_id if room_owner_user_id else execution_user_id,
    }


def _rt_inject_execution_context(request_args: Dict[str, Any], ctx: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(request_args or {})

    actor_user_id = _rt_safe_str(ctx.get("actor_user_id"))
    room_owner_user_id = _rt_safe_str(ctx.get("room_owner_user_id"))
    actor_is_room_owner = _rt_safe_bool(ctx.get("actor_is_room_owner"), False)
    effective_execution_scope = _rt_safe_str(ctx.get("effective_execution_scope"))
    execution_user_id = _rt_safe_str(ctx.get("execution_user_id")) or actor_user_id

    out["actor_user_id"] = actor_user_id
    out["room_owner_user_id"] = room_owner_user_id
    out["actor_is_room_owner"] = actor_is_room_owner
    out["is_owner_actor"] = actor_is_room_owner
    out["shared_role_ids_snapshot"] = list(_rt_safe_list(ctx.get("shared_role_ids_snapshot")))
    out["shared_supervisor_enabled_snapshot"] = _rt_safe_bool(ctx.get("shared_supervisor_enabled_snapshot"), False)
    out["shared_room_config_enabled_snapshot"] = _rt_safe_bool(ctx.get("shared_room_config_enabled_snapshot"), False)
    out["shared_role_ids_meta"] = list(_rt_safe_list(ctx.get("shared_role_ids_meta")))
    out["shared_role_ids_state"] = list(_rt_safe_list(ctx.get("shared_role_ids_state")))
    out["shared_supervisor_enabled_meta"] = _rt_safe_bool(ctx.get("shared_supervisor_enabled_meta"), False)
    out["shared_supervisor_enabled_state"] = _rt_safe_bool(ctx.get("shared_supervisor_enabled_state"), False)
    out["shared_room_config_enabled_meta"] = _rt_safe_bool(ctx.get("shared_room_config_enabled_meta"), False)
    out["shared_room_config_enabled_state"] = _rt_safe_bool(ctx.get("shared_room_config_enabled_state"), False)
    out["effective_execution_scope"] = effective_execution_scope

    out["execution_user_id"] = execution_user_id
    out["fs_owner_user_id"] = _rt_safe_str(ctx.get("fs_owner_user_id")) or room_owner_user_id or execution_user_id
    out["user_id"] = execution_user_id

    if execution_user_id and execution_user_id != actor_user_id:
        if "_librechat_email" in out:
            out["_room_actor__librechat_email"] = out.get("_librechat_email")
            out.pop("_librechat_email", None)
        if "_librechat_name" in out:
            out["_room_actor__librechat_name"] = out.get("_librechat_name")
            out.pop("_librechat_name", None)
        if "email" in out:
            out["_room_actor_email"] = out.get("email")
            out.pop("email", None)
        if "name" in out:
            out["_room_actor_name"] = out.get("name")
            out.pop("name", None)

    return out


def _rt_shared_auto_reply_enabled_for_actor(ctx: Dict[str, Any]) -> bool:
    if _rt_safe_bool(ctx.get("actor_is_room_owner"), False):
        return True
    return _rt_safe_bool(ctx.get("shared_room_config_enabled_snapshot"), False)


def _rt_role_allowed_for_actor(role_obj: Dict[str, Any], ctx: Dict[str, Any]) -> bool:
    role = _rt_safe_dict(role_obj)
    role_id = _rt_safe_str(role.get("role_id"))
    role_owner_user_id = _rt_safe_str(role.get("owner_user_id") or ctx.get("room_owner_user_id"))
    actor_user_id = _rt_safe_str(ctx.get("actor_user_id"))

    if _rt_safe_bool(ctx.get("actor_is_room_owner"), False):
        return True
    if actor_user_id and role_owner_user_id and actor_user_id == role_owner_user_id:
        return True
    return bool(role_id) and role_id in _rt_normalize_id_list(ctx.get("shared_role_ids_snapshot"))


def _rt_supervisor_allowed_for_actor(ctx: Dict[str, Any]) -> bool:
    if _rt_safe_bool(ctx.get("actor_is_room_owner"), False):
        return True
    return _rt_safe_bool(ctx.get("shared_supervisor_enabled_snapshot"), False)


def _rt_filter_active_role_objects_for_actor(active_role_objs: Any, ctx: Dict[str, Any]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for item in _rt_safe_list(active_role_objs):
        role_obj = _rt_safe_dict(item)
        if not role_obj:
            continue
        if _rt_role_allowed_for_actor(role_obj, ctx):
            out.append(role_obj)
    return out


def _rt_append_tool_result(result_obj: Dict[str, Any], tool_result: Dict[str, Any]) -> Dict[str, Any]:
    root = dict(result_obj or {})
    rows = _rt_safe_list(root.get("tool_results"))
    rows.append(tool_result)
    root["tool_results"] = rows
    return root


def _rt_build_runtime_skip_result(
    *,
    reason_code: str,
    path: str,
    ctx: Dict[str, Any],
    role_obj: Optional[Dict[str, Any]] = None,
    active_role_objs: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    role = _rt_safe_dict(role_obj)
    return {
        "type": "room.runtime_skipped",
        "reason_code": _rt_safe_str(reason_code),
        "path": _rt_safe_str(path),
        "actor_user_id": _rt_safe_str(ctx.get("actor_user_id")),
        "room_owner_user_id": _rt_safe_str(ctx.get("room_owner_user_id")),
        "actor_is_room_owner": _rt_safe_bool(ctx.get("actor_is_room_owner"), False),
        "effective_execution_scope": _rt_safe_str(ctx.get("effective_execution_scope")),
        "execution_user_id": _rt_safe_str(ctx.get("execution_user_id")),
        "fs_owner_user_id": _rt_safe_str(ctx.get("fs_owner_user_id")),
        "role_id": _rt_safe_str(role.get("role_id")),
        "role_name": _rt_safe_str(role.get("name") or role.get("slug")),
        "shared_role_ids_snapshot": list(_rt_safe_list(ctx.get("shared_role_ids_snapshot"))),
        "shared_supervisor_enabled_snapshot": _rt_safe_bool(ctx.get("shared_supervisor_enabled_snapshot"), False),
        "shared_room_config_enabled_snapshot": _rt_safe_bool(ctx.get("shared_room_config_enabled_snapshot"), False),
        "shared_role_ids_meta": list(_rt_safe_list(ctx.get("shared_role_ids_meta"))),
        "shared_role_ids_state": list(_rt_safe_list(ctx.get("shared_role_ids_state"))),
        "shared_supervisor_enabled_meta": _rt_safe_bool(ctx.get("shared_supervisor_enabled_meta"), False),
        "shared_supervisor_enabled_state": _rt_safe_bool(ctx.get("shared_supervisor_enabled_state"), False),
        "shared_room_config_enabled_meta": _rt_safe_bool(ctx.get("shared_room_config_enabled_meta"), False),
        "shared_room_config_enabled_state": _rt_safe_bool(ctx.get("shared_room_config_enabled_state"), False),
        "active_role_ids_considered": [
            _rt_safe_str(_rt_safe_dict(x).get("role_id")) for x in _rt_safe_list(active_role_objs)
        ],
    }


def _rt_is_provider_bridge_call(
    args: Dict[str, Any],
    provider_info: Optional[Dict[str, Any]] = None,
) -> bool:
    arg_obj = _rt_safe_dict(args)
    if _rt_safe_bool(arg_obj.get("_room_mcp_provider_call"), False):
        return True
    return bool(_rt_safe_dict(provider_info))


def _patch_provider_bridge_mcp_binding_args(
    args: Dict[str, Any],
    *,
    provider_info: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    req = dict(_rt_safe_dict(args))

    provider_bridge_call = _rt_is_provider_bridge_call(req, provider_info)
    if not provider_bridge_call:
        return req

    question = _rt_resolve_request_question(req)
    if question:
        req = _rt_apply_question_aliases(req, question)

    provider_meta = _rt_safe_dict(provider_info)
    provider_origin = _rt_safe_str(
        req.get("_room_mcp_provider_origin")
        or provider_meta.get("provider_origin")
        or _rt_safe_dict(provider_meta.get("room_source")).get("provider_origin")
    )

    share_ref = _rt_extract_provider_bridge_share_ref(req, provider_info)
    grant_meta = _rt_extract_provider_bridge_grant_meta(req, provider_info)

    binding = _rt_apply_mcp_binding_question_aliases(
        _rt_safe_dict(req.get("mcp_binding")),
        question=question,
        provider_id=_rt_safe_str(req.get("_room_mcp_provider_id")),
        provider_type=_rt_safe_str(req.get("_room_mcp_provider_type")),
        provider_origin=provider_origin,
    )

    if share_ref:
        if not _rt_safe_str(req.get("mcp_share_ref")):
            req["mcp_share_ref"] = share_ref
        if not _rt_safe_str(req.get("share_ref")):
            req["share_ref"] = share_ref
        if not _rt_safe_str(binding.get("share_ref")):
            binding["share_ref"] = share_ref

    if grant_meta:
        resolved_grant = dict(grant_meta)
        grant_id = _rt_safe_str(resolved_grant.get("grant_id"))
        artifact_id = _rt_safe_str(resolved_grant.get("artifact_id"))
        resolution_source = _rt_safe_str(resolved_grant.get("resolution_source"))

        if not _rt_safe_dict(req.get("_room_mcp_grant")):
            req["_room_mcp_grant"] = resolved_grant
        if not _rt_safe_dict(req.get("grant_meta")):
            req["grant_meta"] = resolved_grant
        if not _rt_safe_dict(req.get("grant")):
            req["grant"] = resolved_grant

        if grant_id and not _rt_safe_str(req.get("grant_id")):
            req["grant_id"] = grant_id
        if artifact_id and not _rt_safe_str(req.get("artifact_id")):
            req["artifact_id"] = artifact_id
        if resolution_source and not _rt_safe_str(req.get("resolution_source")):
            req["resolution_source"] = resolution_source

        if not _rt_safe_dict(binding.get("grant_meta")):
            binding["grant_meta"] = dict(resolved_grant)
        if not _rt_safe_dict(binding.get("grant")):
            binding["grant"] = dict(resolved_grant)
        if grant_id and not _rt_safe_str(binding.get("grant_id")):
            binding["grant_id"] = grant_id
        if artifact_id and not _rt_safe_str(binding.get("artifact_id")):
            binding["artifact_id"] = artifact_id
        if resolution_source and not _rt_safe_str(binding.get("resolution_source")):
            binding["resolution_source"] = resolution_source

    req["mcp_binding"] = binding
    return req


def _rt_build_provider_bridge_tool_result(
    *,
    room_id: str,
    args: Dict[str, Any],
    provider_info: Optional[Dict[str, Any]],
    ctx: Dict[str, Any],
    reply_mode: str,
    source_participant: bool,
) -> Dict[str, Any]:
    provider_meta = _rt_safe_dict(provider_info)
    room_source = _rt_safe_dict(provider_meta.get("room_source"))
    shared_boundary = _rt_safe_dict(room_source.get("shared_boundary"))

    return _build_tool_result_item(
        "room_mcp_provider_bridge",
        provider_id=_rt_safe_str(provider_meta.get("provider_id") or args.get("_room_mcp_provider_id")),
        provider_type=_rt_safe_str(provider_meta.get("provider_type") or args.get("_room_mcp_provider_type")),
        provider_label=_rt_safe_str(provider_meta.get("label")),
        provider_call=_rt_is_provider_bridge_call(args, provider_info),
        source_room_id=_rt_safe_str(room_source.get("room_id") or args.get("_room_mcp_source_room_id") or room_id),
        consumer_room_id=_rt_safe_str(args.get("_room_mcp_consumer_room_id")),
        actor_user_id=_rt_safe_str(ctx.get("actor_user_id") or args.get("_room_mcp_actor_user_id")),
        actor_is_room_owner=_rt_safe_bool(ctx.get("actor_is_room_owner"), False),
        actor_participant_in_source_room=bool(source_participant),
        effective_execution_scope=_rt_safe_str(ctx.get("effective_execution_scope")),
        execution_user_id=_rt_safe_str(ctx.get("execution_user_id")),
        fs_owner_user_id=_rt_safe_str(ctx.get("fs_owner_user_id")),
        reply_mode=_rt_safe_str(reply_mode),
        shared_room_config_enabled_snapshot=_rt_safe_bool(ctx.get("shared_room_config_enabled_snapshot"), False),
        shared_supervisor_enabled_snapshot=_rt_safe_bool(ctx.get("shared_supervisor_enabled_snapshot"), False),
        shared_role_ids_snapshot=list(_rt_safe_list(ctx.get("shared_role_ids_snapshot"))),
        owner_private_scope_exposed=_rt_safe_bool(shared_boundary.get("owner_private_scope_exposed"), False),
        shared_boundary=shared_boundary,
    )


__all__ = [
    "_patch_provider_bridge_mcp_binding_args",
    "_rt_append_tool_result",
    "_rt_apply_mcp_binding_question_aliases",
    "_rt_apply_question_aliases",
    "_rt_build_execution_context",
    "_rt_build_provider_bridge_tool_result",
    "_rt_build_runtime_skip_result",
    "_rt_filter_active_role_objects_for_actor",
    "_rt_inject_execution_context",
    "_rt_is_provider_bridge_call",
    "_rt_resolve_request_question",
    "_rt_role_allowed_for_actor",
    "_rt_safe_bool",
    "_rt_safe_dict",
    "_rt_safe_list",
    "_rt_safe_str",
    "_rt_shared_auto_reply_enabled_for_actor",
    "_rt_supervisor_allowed_for_actor",
]

