from __future__ import annotations

from typing import Any, Dict

from .room_request_bridge import (
    _safe_dict,
    _safe_str,
)
from .room_mcp_bridge_grant_context import (
    _build_bridge_mcp_binding,
    _extract_basepath,
    _extract_bridge_actor_user_id,
    _extract_imported_remote_peer_id,
    _extract_provider_origin,
    _extract_share_ref,
    _resolve_imported_remote_timeout_ms,
    _safe_int,
)
from .room_mcp_provider_bridge import (
    _append_execution_fact,
    _apply_mcp_binding_question_aliases,
    _apply_question_aliases,
    _dispatch_imported_remote_room_shared_provider,
    _dispatch_room_shared_provider,
    _normalize_question,
    _safe_query_str,
)
from .room_mcp_provider_result_packet import (
    _federated_provider_error_packet,
    _provider_error_packet,
)
from .room_mcp_provider_registry import (
    get_room_mcp_provider,
)
from .room_mcp_provider_invoke_contract import (
    hydrate_provider_invoke_contract,
)
from .room_mcp_adapter_snapshot import (
    ProviderExecutor,
    _build_provider_dispatch_request_args,
    _call_provider_executor_compat,
    _collect_provider_request_context,
    _context_prefers_imported_remote,
    _derive_provider_id_from_request_args,
    _executor_accepts_kwarg,
    _get_room_mcp_provider_executors,
    _merge_provider_meta_with_context,
    _normalize_provider_meta_shape,
    _normalize_provider_origin,
    _normalize_provider_request_args_for_validation,
    _pick_first_str,
    _resolve_param_value,
    _resolve_provider_meta_from_request_args,
    _safe_list,
    _validate_provider_params,
)
from .room_mcp_adapter_result_view import (
    _apply_final_only_result_view,
    _build_final_only_summary,
    _extract_grant_locator_from_request_args,
    _extract_share_ref_from_request_args,
    _record_grant_consumed_event,
    _resolve_grant_meta,
)

_DESCRIPTOR_VERSION_FALLBACK = "v1"
_SERVER_TOOL_FALLBACK = "nisb_room_mcp_provider_call"
_REQUESTED_MODE_FALLBACK = "mcp"
_ROOM_SHARED_PROVIDER_KIND = "room_shared_capability"
_BUILTIN_EXTERNAL_PROVIDER_KIND = "builtin_external_mcp"


def _resolve_effective_requested_mode(
    *,
    requested_mode: str,
    provider_meta: Dict[str, Any],
) -> str:
    return _safe_str(
        requested_mode,
        _safe_str(_safe_dict(provider_meta).get("requested_mode"), _REQUESTED_MODE_FALLBACK),
    ) or _REQUESTED_MODE_FALLBACK


def _provider_kind(provider_meta: Dict[str, Any]) -> str:
    meta = _safe_dict(provider_meta)
    return _safe_str(meta.get("provider_kind") or meta.get("provider_type")).lower()


def _uses_room_shared_dispatch(provider_meta: Dict[str, Any]) -> bool:
    return _provider_kind(provider_meta) == _ROOM_SHARED_PROVIDER_KIND


def _uses_builtin_external_dispatch(provider_meta: Dict[str, Any]) -> bool:
    return _provider_kind(provider_meta) == _BUILTIN_EXTERNAL_PROVIDER_KIND


def _precheck_provider(
    *,
    provider_id: str,
    question: str,
    request_args: Dict[str, Any],
    role: Dict[str, Any] | None = None,
) -> tuple[Dict[str, Any], str, Dict[str, Any], str]:
    normalized_request_args, resolved_question = _normalize_provider_request_args_for_validation(
        question=question,
        request_args=request_args,
    )

    provider_ctx = _collect_provider_request_context(
        request_args=normalized_request_args,
        role=role,
    )

    provider_meta = _resolve_provider_meta_from_request_args(
        provider_id=provider_id,
        request_args=normalized_request_args,
        role=role,
    )
    if not provider_meta:
        provider_meta = get_room_mcp_provider(provider_id)

    provider_meta = _merge_provider_meta_with_context(
        provider_meta=provider_meta,
        context=provider_ctx,
    )
    provider_meta = hydrate_provider_invoke_contract(
        _normalize_provider_meta_shape(provider_meta),
        descriptor_version_fallback=_DESCRIPTOR_VERSION_FALLBACK,
        server_tool_fallback=_SERVER_TOOL_FALLBACK,
        requested_mode_fallback=_REQUESTED_MODE_FALLBACK,
        provider_kind_fallback=_BUILTIN_EXTERNAL_PROVIDER_KIND,
    )

    if not provider_meta:
        return {}, f"unsupported_provider:{provider_id}", normalized_request_args, resolved_question

    availability = _safe_dict(provider_meta.get("availability"))
    auth_state = _safe_dict(provider_meta.get("auth_state"))

    if not bool(availability.get("available", True)):
        reason = _safe_str(availability.get("reason")) or "provider_unavailable"
        return provider_meta, reason, normalized_request_args, resolved_question

    if bool(auth_state.get("required")) and not bool(auth_state.get("configured")):
        reason = _safe_str(availability.get("reason")) or "auth_not_configured"
        return provider_meta, reason, normalized_request_args, resolved_question

    param_error = _validate_provider_params(provider_meta, normalized_request_args, resolved_question)
    if param_error:
        return provider_meta, param_error, normalized_request_args, resolved_question

    grant_meta, grant_error = _resolve_grant_meta(
        provider_meta=provider_meta,
        request_args=normalized_request_args,
        role=role,
    )
    if grant_meta:
        provider_meta = {
            **provider_meta,
            "_grant_meta": grant_meta,
        }
    if grant_error:
        return provider_meta, grant_error, normalized_request_args, resolved_question

    return provider_meta, "", normalized_request_args, resolved_question


def _apply_grant_result_view_if_needed(
    *,
    packet: Dict[str, Any],
    provider_meta: Dict[str, Any],
) -> Dict[str, Any]:
    grant_meta = _safe_dict(provider_meta.get("_grant_meta"))
    if not grant_meta:
        return packet

    result_view = _safe_str(
        grant_meta.get("external_result_view")
        or _safe_dict(grant_meta.get("scope")).get("result_view"),
        "final_result_only",
    ) or "final_result_only"
    if result_view != "final_result_only":
        return packet

    return _apply_final_only_result_view(
        packet=packet,
        provider_meta=provider_meta,
        grant_meta=grant_meta,
    )


def _dispatch_via_executor(
    *,
    executor: ProviderExecutor,
    room_id: str,
    request_id: str,
    question: str,
    effective_requested_mode: str,
    mcp_overrides: Dict[str, Any],
    dispatch_request_args: Dict[str, Any],
    role: Dict[str, Any],
    provider_meta: Dict[str, Any],
    resolved_provider_id: str,
) -> Dict[str, Any]:
    target_question = _normalize_question(question=question, request_args=dispatch_request_args)
    target_question = _safe_str(target_question) or question

    try:
        return _call_provider_executor_compat(
            executor=executor,
            room_id=room_id,
            request_id=request_id,
            question=target_question,
            requested_mode=effective_requested_mode,
            mcp_overrides=mcp_overrides,
            request_args=dispatch_request_args,
            role=role,
            provider_meta=provider_meta,
        )
    except Exception as ex:
        return _provider_error_packet(
            room_id=room_id,
            request_id=request_id,
            requested_mode=effective_requested_mode,
            mcp_overrides=mcp_overrides,
            question=target_question,
            role=role,
            provider_id=resolved_provider_id,
            error=f"provider_exception:{type(ex).__name__}",
            provider_meta=provider_meta,
        )


def _dispatch_provider_packet(
    *,
    room_id: str,
    request_id: str,
    question: str,
    requested_mode: str,
    mcp_overrides: Dict[str, Any],
    request_args: Dict[str, Any],
    role: Dict[str, Any],
    provider_meta: Dict[str, Any],
    resolved_input_provider_id: str,
) -> tuple[Dict[str, Any], str, Dict[str, Any]]:
    provider_meta = hydrate_provider_invoke_contract(
        provider_meta,
        descriptor_version_fallback=_DESCRIPTOR_VERSION_FALLBACK,
        server_tool_fallback=_SERVER_TOOL_FALLBACK,
        requested_mode_fallback=_REQUESTED_MODE_FALLBACK,
        provider_kind_fallback=_BUILTIN_EXTERNAL_PROVIDER_KIND,
    )
    resolved_provider_id = _safe_str(provider_meta.get("provider_id")) or resolved_input_provider_id
    provider_origin = _safe_str(provider_meta.get("provider_origin")).lower()
    effective_requested_mode = _resolve_effective_requested_mode(
        requested_mode=requested_mode,
        provider_meta=provider_meta,
    )

    dispatch_request_args = _build_provider_dispatch_request_args(
        request_args=request_args,
        provider_meta=provider_meta,
    )

    if _uses_room_shared_dispatch(provider_meta):
        if provider_origin.startswith("imported_remote"):
            packet = _dispatch_imported_remote_room_shared_provider(
                provider_meta=provider_meta,
                room_id=room_id,
                request_id=request_id,
                question=question,
                requested_mode=effective_requested_mode,
                mcp_overrides=mcp_overrides,
                request_args=dispatch_request_args,
                role=role,
            )
        else:
            packet = _dispatch_room_shared_provider(
                provider_meta=provider_meta,
                room_id=room_id,
                request_id=request_id,
                question=question,
                requested_mode=effective_requested_mode,
                mcp_overrides=mcp_overrides,
                request_args=dispatch_request_args,
                role=role,
            )
        return packet, resolved_provider_id, dispatch_request_args

    if _uses_builtin_external_dispatch(provider_meta):
        executors = _get_room_mcp_provider_executors()
        executor = executors.get(resolved_provider_id)
        if not executor:
            packet = _provider_error_packet(
                room_id=room_id,
                request_id=request_id,
                requested_mode=effective_requested_mode,
                mcp_overrides=mcp_overrides,
                question=question,
                role=role,
                provider_id=resolved_provider_id,
                error=f"unsupported_provider:{resolved_provider_id}",
                provider_meta=provider_meta,
            )
            return packet, resolved_provider_id, dispatch_request_args

        packet = _dispatch_via_executor(
            executor=executor,
            room_id=room_id,
            request_id=request_id,
            question=question,
            effective_requested_mode=effective_requested_mode,
            mcp_overrides=mcp_overrides,
            dispatch_request_args=dispatch_request_args,
            role=role,
            provider_meta=provider_meta,
            resolved_provider_id=resolved_provider_id,
        )
        return packet, resolved_provider_id, dispatch_request_args

    executors = _get_room_mcp_provider_executors()
    executor = executors.get(resolved_provider_id)
    if not executor:
        packet = _provider_error_packet(
            room_id=room_id,
            request_id=request_id,
            requested_mode=effective_requested_mode,
            mcp_overrides=mcp_overrides,
            question=question,
            role=role,
            provider_id=resolved_provider_id,
            error=f"unsupported_provider:{resolved_provider_id}",
            provider_meta=provider_meta,
        )
        return packet, resolved_provider_id, dispatch_request_args

    packet = _dispatch_via_executor(
        executor=executor,
        room_id=room_id,
        request_id=request_id,
        question=question,
        effective_requested_mode=effective_requested_mode,
        mcp_overrides=mcp_overrides,
        dispatch_request_args=dispatch_request_args,
        role=role,
        provider_meta=provider_meta,
        resolved_provider_id=resolved_provider_id,
    )
    return packet, resolved_provider_id, dispatch_request_args


def _finalize_provider_packet(
    *,
    packet: Dict[str, Any],
    provider_meta: Dict[str, Any],
    resolved_provider_id: str,
    requested_mode: str,
    role: Dict[str, Any],
    consumer_room_id: str,
    dispatch_request_args: Dict[str, Any],
    request_id: str,
) -> Dict[str, Any]:
    effective_requested_mode = _resolve_effective_requested_mode(
        requested_mode=requested_mode,
        provider_meta=provider_meta,
    )

    packet = _append_execution_fact(
        packet=packet,
        provider_meta=provider_meta,
        provider_id=resolved_provider_id,
        requested_mode=effective_requested_mode,
        role=role,
        consumer_room_id=consumer_room_id,
        actor_user_id=_extract_bridge_actor_user_id(dispatch_request_args),
    )

    packet = _apply_grant_result_view_if_needed(
        packet=packet,
        provider_meta=provider_meta,
    )

    grant_meta = _safe_dict(provider_meta.get("_grant_meta"))
    if grant_meta:
        _record_grant_consumed_event(
            request_id=request_id,
            consumer_room_id=consumer_room_id,
            actor_user_id=_extract_bridge_actor_user_id(dispatch_request_args),
            provider_meta=provider_meta,
            grant_meta=grant_meta,
            packet_status=_safe_str(_safe_dict(packet).get("status"), "success"),
        )

    return packet


def dispatch_room_mcp_provider(
    *,
    room_id: str,
    request_id: str,
    question: str,
    requested_mode: str,
    mcp_overrides: Dict[str, Any],
    request_args: Dict[str, Any],
    role: Dict[str, Any],
    provider_id: str = "",
) -> Dict[str, Any]:
    resolved_input_provider_id = _derive_provider_id_from_request_args(
        provider_id=provider_id,
        request_args=request_args,
        role=role,
    )
    if not resolved_input_provider_id:
        return _provider_error_packet(
            room_id=room_id,
            request_id=request_id,
            requested_mode=_safe_str(requested_mode, _REQUESTED_MODE_FALLBACK),
            mcp_overrides=mcp_overrides,
            question=question,
            role=role,
            provider_id="",
            error="missing_provider_id",
            provider_meta={},
        )

    provider_meta, error, normalized_request_args, normalized_question = _precheck_provider(
        provider_id=resolved_input_provider_id,
        question=question,
        request_args=request_args,
        role=role,
    )
    provider_meta = hydrate_provider_invoke_contract(
        provider_meta,
        descriptor_version_fallback=_DESCRIPTOR_VERSION_FALLBACK,
        server_tool_fallback=_SERVER_TOOL_FALLBACK,
        requested_mode_fallback=_REQUESTED_MODE_FALLBACK,
        provider_kind_fallback=_BUILTIN_EXTERNAL_PROVIDER_KIND,
    )

    effective_requested_mode = _resolve_effective_requested_mode(
        requested_mode=requested_mode,
        provider_meta=provider_meta,
    )

    if error:
        packet = _provider_error_packet(
            room_id=room_id,
            request_id=request_id,
            requested_mode=effective_requested_mode,
            mcp_overrides=mcp_overrides,
            question=normalized_question,
            role=role,
            provider_id=resolved_input_provider_id,
            error=error,
            provider_meta=provider_meta,
        )
        return _apply_grant_result_view_if_needed(
            packet=packet,
            provider_meta=provider_meta,
        )

    packet, resolved_provider_id, dispatch_request_args = _dispatch_provider_packet(
        room_id=room_id,
        request_id=request_id,
        question=normalized_question,
        requested_mode=effective_requested_mode,
        mcp_overrides=mcp_overrides,
        request_args=normalized_request_args,
        role=role,
        provider_meta=provider_meta,
        resolved_input_provider_id=resolved_input_provider_id,
    )

    return _finalize_provider_packet(
        packet=packet,
        provider_meta=provider_meta,
        resolved_provider_id=resolved_provider_id,
        requested_mode=effective_requested_mode,
        role=role,
        consumer_room_id=room_id,
        dispatch_request_args=dispatch_request_args,
        request_id=request_id,
    )


def invoke_room_mcp_provider(
    *,
    room_id: str,
    request_id: str,
    question: str,
    requested_mode: str,
    mcp_overrides: Dict[str, Any],
    request_args: Dict[str, Any],
    role: Dict[str, Any],
    provider_id: str = "",
) -> Dict[str, Any]:
    return dispatch_room_mcp_provider(
        room_id=room_id,
        request_id=request_id,
        question=question,
        requested_mode=requested_mode,
        mcp_overrides=mcp_overrides,
        request_args=request_args,
        role=role,
        provider_id=provider_id,
    )


__all__ = [
    "ProviderExecutor",
    "dispatch_room_mcp_provider",
    "invoke_room_mcp_provider",
    "_append_execution_fact",
    "_apply_mcp_binding_question_aliases",
    "_apply_question_aliases",
    "_apply_final_only_result_view",
    "_build_bridge_mcp_binding",
    "_build_final_only_summary",
    "_build_provider_dispatch_request_args",
    "_call_provider_executor_compat",
    "_collect_provider_request_context",
    "_context_prefers_imported_remote",
    "_derive_provider_id_from_request_args",
    "_dispatch_imported_remote_room_shared_provider",
    "_dispatch_room_shared_provider",
    "_executor_accepts_kwarg",
    "_extract_basepath",
    "_extract_bridge_actor_user_id",
    "_extract_grant_locator_from_request_args",
    "_extract_imported_remote_peer_id",
    "_extract_provider_origin",
    "_extract_share_ref",
    "_extract_share_ref_from_request_args",
    "_federated_provider_error_packet",
    "_get_room_mcp_provider_executors",
    "_merge_provider_meta_with_context",
    "_normalize_provider_meta_shape",
    "_normalize_provider_origin",
    "_normalize_provider_request_args_for_validation",
    "_normalize_question",
    "_pick_first_str",
    "_precheck_provider",
    "_provider_error_packet",
    "_record_grant_consumed_event",
    "_resolve_effective_requested_mode",
    "_resolve_grant_meta",
    "_resolve_imported_remote_timeout_ms",
    "_resolve_param_value",
    "_resolve_provider_meta_from_request_args",
    "_safe_int",
    "_safe_list",
    "_safe_query_str",
    "_uses_builtin_external_dispatch",
    "_uses_room_shared_dispatch",
    "_validate_provider_params",
]
