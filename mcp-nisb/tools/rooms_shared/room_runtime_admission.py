from __future__ import annotations

from typing import Any, Dict, List, Optional

from .room_packet_builder import (
    _empty_evidence_result,
    _ensure_formal_packet,
)
from .room_mcp_runtime_context import (
    _rt_safe_dict,
    _rt_safe_str,
)
from .room_runtime_admission_grant import (
    _rt_extract_provider_bridge_origin,
    _rt_provider_bridge_uses_external_grant_context,
    _rt_extract_provider_bridge_share_ref,
    _rt_extract_provider_bridge_grant_meta,
    _rt_is_capability_bridge_invoke,
    _rt_is_link_grant_backed_capability_invoke,
    _rt_has_resolvable_grant_reference,
    _rt_validate_provider_bridge_grant,
)


def _rt_build_provider_bridge_deny_tool_result(
    *,
    room_id: str,
    provider_info: Optional[Dict[str, Any]],
    runtime_ctx: Dict[str, Any],
    reason_code: str,
    deny_stage: str,
    grant_validation: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    info = _rt_safe_dict(provider_info)
    room_source = _rt_safe_dict(info.get("room_source"))
    validation = _rt_safe_dict(grant_validation)
    grant_meta = _rt_safe_dict(validation.get("grant_meta"))
    runtime = _rt_safe_dict(runtime_ctx)

    return {
        "type": "room_mcp_provider_deny",
        "provider_id": _rt_safe_str(info.get("provider_id")),
        "provider_type": _rt_safe_str(info.get("provider_type")),
        "provider_origin": _rt_safe_str(info.get("provider_origin")),
        "source_room_id": _rt_safe_str(room_source.get("room_id") or room_id),
        "consumer_room_id": _rt_safe_str(
            runtime.get("consumer_room_id")
            or runtime.get("_room_mcp_consumer_room_id")
        ),
        "actor_user_id": _rt_safe_str(
            runtime.get("execution_user_id")
            or runtime.get("actor_user_id")
        ),
        "grant_id": _rt_safe_str(grant_meta.get("grant_id")),
        "artifact_id": _rt_safe_str(grant_meta.get("artifact_id")),
        "share_ref": _rt_safe_str(validation.get("share_ref")),
        "grant_checked": bool(validation.get("checked")),
        "grant_allowed": bool(validation.get("allowed", True)),
        "reason_code": reason_code,
        "deny_stage": deny_stage,
    }


def _rt_build_provider_bridge_deny_packet(
    *,
    room_id: str,
    rid: str,
    rag_mode: str,
    mcp_overrides: Dict[str, Any],
    content: str,
    provider_info: Optional[Dict[str, Any]],
    runtime_ctx: Dict[str, Any],
    reason_code: str,
    deny_stage: str,
    route_state_result: Optional[Dict[str, Any]] = None,
    provider_bridge_result: Optional[Dict[str, Any]] = None,
    grant_validation: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    info = _rt_safe_dict(provider_info)
    room_source = _rt_safe_dict(info.get("room_source"))
    validation = _rt_safe_dict(grant_validation)
    grant_meta = _rt_safe_dict(validation.get("grant_meta"))

    tool_results: List[Dict[str, Any]] = []
    if route_state_result:
        tool_results.append(route_state_result)
    if provider_bridge_result:
        tool_results.append(provider_bridge_result)

    tool_results.append(
        _rt_build_provider_bridge_deny_tool_result(
            room_id=room_id,
            provider_info=info,
            runtime_ctx=runtime_ctx,
            reason_code=reason_code,
            deny_stage=deny_stage,
            grant_validation=validation,
        )
    )

    return _ensure_formal_packet(
        conv_id=room_id,
        request_id=rid,
        rag_mode=rag_mode,
        mcp_overrides=mcp_overrides,
        mode_used=rag_mode,
        response=f"room provider invoke denied: {reason_code}",
        status="error",
        message=f"room provider invoke denied: {reason_code}",
        evidence_query=content,
        evidence_tools=[],
        evidence_result={
            **_empty_evidence_result(content),
            "provider_id": _rt_safe_str(info.get("provider_id")),
            "provider_origin": _rt_safe_str(info.get("provider_origin")),
            "source_room_id": _rt_safe_str(room_source.get("room_id") or room_id),
            "grant_id": _rt_safe_str(grant_meta.get("grant_id")),
            "artifact_id": _rt_safe_str(grant_meta.get("artifact_id")),
            "share_ref": _rt_safe_str(validation.get("share_ref")),
            "grant_checked": bool(validation.get("checked")),
            "grant_allowed": bool(validation.get("allowed", True)),
            "deny_reason": reason_code,
            "deny_stage": deny_stage,
        },
        tool_calls=[],
        tool_results=tool_results,
    )


__all__ = [
    "_rt_extract_provider_bridge_origin",
    "_rt_provider_bridge_uses_external_grant_context",
    "_rt_extract_provider_bridge_share_ref",
    "_rt_extract_provider_bridge_grant_meta",
    "_rt_is_capability_bridge_invoke",
    "_rt_is_link_grant_backed_capability_invoke",
    "_rt_has_resolvable_grant_reference",
    "_rt_validate_provider_bridge_grant",
    "_rt_build_provider_bridge_deny_packet",
]
