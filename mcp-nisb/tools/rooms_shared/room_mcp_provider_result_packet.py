from __future__ import annotations

from typing import Any, Dict, List

from .room_packet_builder import (
    _empty_evidence_result,
    _ensure_formal_packet,
)
from .room_request_bridge import (
    _safe_dict,
    _safe_str,
)


def _safe_list(v: Any) -> List[Any]:
    return list(v) if isinstance(v, list) else []


def _packet_tool_result_types(packet: Dict[str, Any]) -> List[str]:
    types: List[str] = []
    for item in _safe_list(_safe_dict(packet).get("tool_results")):
        type_name = _safe_str(_safe_dict(item).get("type"))
        if type_name:
            types.append(type_name)
    return types


def _packet_has_terminal_deny(packet: Dict[str, Any]) -> bool:
    src = _safe_dict(packet)
    tool_types = {t.lower() for t in _packet_tool_result_types(src)}
    if tool_types.intersection(
        {
            "room_mcp_provider_deny",
            "room_provider_deny",
            "room_mcp_bridge_deny",
        }
    ):
        return True

    upstream_message = _safe_str(
        src.get("upstream_message")
        or src.get("upstream_response")
    ).lower()
    if upstream_message and ("denied" in upstream_message or "blocked" in upstream_message):
        return True

    message = _safe_str(src.get("message")).lower()
    response = _safe_str(src.get("response")).lower()
    if "invoke denied" in message or "invoke denied" in response:
        return True
    if "runtime_blocked" in message or "runtime_blocked" in response:
        return True

    return False


def _room_shared_provider_success_has_final_signal(packet: Dict[str, Any]) -> bool:
    src = _safe_dict(packet)
    tool_types = {t.lower() for t in _packet_tool_result_types(src)}
    if tool_types.intersection(
        {
            "generated_event",
            "generated_events",
            "final_event",
            "room_mcp_final_result_view",
        }
    ):
        return True

    if _packet_has_terminal_deny(src):
        return True

    message = _safe_str(src.get("message"))
    if message in {
        "room post processed",
        "room orchestration finished",
        "room supervisor direct reply finished",
    }:
        return True

    return False


def _provider_error_packet(
    *,
    room_id: str,
    request_id: str,
    requested_mode: str,
    mcp_overrides: Dict[str, Any],
    question: str,
    role: Dict[str, Any],
    provider_id: str,
    error: str,
    provider_meta: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    role_id = _safe_str(role.get("role_id"))
    role_name = _safe_str(role.get("name") or role.get("slug") or role_id)
    meta = _safe_dict(provider_meta)
    auth_state = _safe_dict(meta.get("auth_state"))
    availability = _safe_dict(meta.get("availability"))
    room_source = _safe_dict(meta.get("room_source"))
    shared_boundary = _safe_dict(room_source.get("shared_boundary"))

    return _ensure_formal_packet(
        conv_id=room_id,
        request_id=request_id,
        rag_mode=requested_mode,
        mcp_overrides=mcp_overrides,
        mode_used="mcp",
        response=f"room mcp provider {error}",
        status="error",
        message=f"room mcp provider {error}",
        evidence_query=question,
        evidence_tools=[],
        evidence_result={
            **_empty_evidence_result(question),
            "provider_id": provider_id,
            "error": error,
            "auth_type": _safe_str(auth_state.get("type")),
            "availability_reason": _safe_str(availability.get("reason")),
            "source_room_id": _safe_str(room_source.get("room_id")),
        },
        tool_calls=[],
        tool_results=[
            {
                "type": "room_mcp_provider_error",
                "role_id": role_id,
                "role_name": role_name,
                "provider_id": provider_id,
                "provider_type": _safe_str(meta.get("provider_type"), "preset"),
                "provider_label": _safe_str(meta.get("label")),
                "auth_type": _safe_str(auth_state.get("type")),
                "auth_required": bool(auth_state.get("required")),
                "auth_configured": bool(auth_state.get("configured")),
                "availability_reason": _safe_str(availability.get("reason")),
                "source_room_id": _safe_str(room_source.get("room_id")),
                "shared_room_config_enabled": bool(room_source.get("shared_room_config_enabled")),
                "shared_supervisor_enabled": bool(room_source.get("shared_supervisor_enabled")),
                "owner_private_scope_exposed": bool(shared_boundary.get("owner_private_scope_exposed")),
                "error": error,
            }
        ],
    )


def _federated_provider_error_packet(
    *,
    room_id: str,
    request_id: str,
    requested_mode: str,
    mcp_overrides: Dict[str, Any],
    question: str,
    role: Dict[str, Any],
    provider_meta: Dict[str, Any],
    error: str,
    remote_peer_id: str = "",
    upstream: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    meta = _safe_dict(provider_meta)
    room_source = _safe_dict(meta.get("room_source"))
    shared_boundary = _safe_dict(room_source.get("shared_boundary"))
    role_id = _safe_str(role.get("role_id"))
    role_name = _safe_str(role.get("name") or role.get("slug") or role_id)
    up = _safe_dict(upstream)
    grant_meta = _safe_dict(meta.get("_grant_meta"))
    grant_audience = _safe_dict(
        grant_meta.get("audience")
        or meta.get("grant_audience")
    )
    target_identity = _safe_dict(up.get("target_identity"))

    message = (
        _safe_str(up.get("user_message"))
        or _safe_str(up.get("message"))
        or error
    )

    return _ensure_formal_packet(
        conv_id=room_id,
        request_id=request_id,
        rag_mode=requested_mode,
        mcp_overrides=mcp_overrides,
        mode_used="mcp",
        response=message,
        status="error",
        message=message,
        evidence_query=question,
        evidence_tools=[],
        evidence_result={
            **_empty_evidence_result(question),
            "provider_id": _safe_str(meta.get("provider_id")),
            "error": error,
            "provider_origin": _safe_str(meta.get("provider_origin")),
            "source_room_id": _safe_str(room_source.get("room_id")),
            "remote_peer_id": remote_peer_id,
            "grant_id": _safe_str(grant_meta.get("grant_id")),
            "artifact_id": _safe_str(grant_meta.get("artifact_id")),
            "grant_peer_id": _safe_str(
                grant_audience.get("peer_id")
                or grant_audience.get("remote_peer_id")
                or grant_audience.get("target_peer_id")
                or grant_audience.get("federation_peer_id")
                or target_identity.get("peer_id")
            ),
            "grant_remote_user_id": _safe_str(
                grant_audience.get("remote_user_id")
                or target_identity.get("remote_user_id")
            ),
            "target_source_room_id": _safe_str(target_identity.get("source_room_id")),
            "error_code": _safe_str(up.get("error_code")),
            "error_kind": _safe_str(up.get("error_kind")),
            "timeout_ms_requested": up.get("timeout_ms_requested"),
            "timeout_ms_effective": up.get("timeout_ms_effective"),
            "timeout_ms": up.get("timeout_ms"),
            "timeout_sec": up.get("timeout_sec"),
            "status_code": up.get("status_code"),
            "url": up.get("url"),
            "exception_type": _safe_str(up.get("exception_type")),
        },
        tool_calls=[],
        tool_results=[
            {
                "type": "room_mcp_provider_error",
                "role_id": role_id,
                "role_name": role_name,
                "provider_id": _safe_str(meta.get("provider_id")),
                "provider_type": _safe_str(meta.get("provider_type"), "room_shared_capability"),
                "provider_origin": _safe_str(meta.get("provider_origin")),
                "provider_label": _safe_str(meta.get("label")),
                "source_room_id": _safe_str(room_source.get("room_id")),
                "remote_peer_id": remote_peer_id,
                "grant_id": _safe_str(grant_meta.get("grant_id")),
                "artifact_id": _safe_str(grant_meta.get("artifact_id")),
                "grant_peer_id": _safe_str(
                    grant_audience.get("peer_id")
                    or grant_audience.get("remote_peer_id")
                    or grant_audience.get("target_peer_id")
                    or grant_audience.get("federation_peer_id")
                    or target_identity.get("peer_id")
                ),
                "grant_remote_user_id": _safe_str(
                    grant_audience.get("remote_user_id")
                    or target_identity.get("remote_user_id")
                ),
                "target_source_room_id": _safe_str(target_identity.get("source_room_id")),
                "shared_room_config_enabled": bool(room_source.get("shared_room_config_enabled")),
                "shared_supervisor_enabled": bool(room_source.get("shared_supervisor_enabled")),
                "owner_private_scope_exposed": bool(shared_boundary.get("owner_private_scope_exposed")),
                "error": error,
                "error_code": _safe_str(up.get("error_code")),
                "error_kind": _safe_str(up.get("error_kind")),
                "user_message": _safe_str(up.get("user_message") or up.get("message")),
                "retryable": bool(up.get("retryable")),
                "timeout_ms_requested": up.get("timeout_ms_requested"),
                "timeout_ms_effective": up.get("timeout_ms_effective"),
                "timeout_ms": up.get("timeout_ms"),
                "timeout_sec": up.get("timeout_sec"),
                "status_code": up.get("status_code"),
                "url": up.get("url"),
                "exception_type": _safe_str(up.get("exception_type")),
            }
        ],
    )


def _nonfinal_room_shared_provider_packet(
    *,
    room_id: str,
    request_id: str,
    requested_mode: str,
    mcp_overrides: Dict[str, Any],
    question: str,
    role: Dict[str, Any],
    provider_meta: Dict[str, Any],
    upstream_packet: Dict[str, Any] | None = None,
    remote_peer_id: str = "",
) -> Dict[str, Any]:
    meta = _safe_dict(provider_meta)
    up = _safe_dict(upstream_packet)
    room_source = _safe_dict(meta.get("room_source"))
    shared_boundary = _safe_dict(room_source.get("shared_boundary"))
    grant_meta = _safe_dict(meta.get("_grant_meta"))
    role_id = _safe_str(role.get("role_id"))
    role_name = _safe_str(role.get("name") or role.get("slug") or role_id)
    provider_id = _safe_str(meta.get("provider_id"))
    provider_type = _safe_str(meta.get("provider_type"), "room_shared_capability")
    provider_origin = _safe_str(meta.get("provider_origin"))

    upstream_message = _safe_str(up.get("message"))
    upstream_response = _safe_str(up.get("response"))
    upstream_status = _safe_str(up.get("status"), "success") or "success"
    upstream_tool_types = _packet_tool_result_types(up)

    user_message = "room mcp provider did not return a final response"

    return _ensure_formal_packet(
        conv_id=room_id,
        request_id=request_id,
        rag_mode=requested_mode,
        mcp_overrides=mcp_overrides,
        mode_used="mcp",
        response=user_message,
        status="error",
        message=user_message,
        evidence_query=question,
        evidence_tools=[],
        evidence_result={
            **_empty_evidence_result(question),
            "provider_id": provider_id,
            "provider_type": provider_type,
            "provider_origin": provider_origin,
            "source_room_id": _safe_str(room_source.get("room_id")),
            "grant_id": _safe_str(grant_meta.get("grant_id")),
            "artifact_id": _safe_str(grant_meta.get("artifact_id")),
            "error": "provider_nonfinal_result",
            "remote_peer_id": remote_peer_id,
            "upstream_status": upstream_status,
            "upstream_message": upstream_message,
            "upstream_response": upstream_response,
            "upstream_tool_result_types": upstream_tool_types,
        },
        tool_calls=[],
        tool_results=[
            {
                "type": "room_mcp_provider_error",
                "role_id": role_id,
                "role_name": role_name,
                "provider_id": provider_id,
                "provider_type": provider_type,
                "provider_origin": provider_origin,
                "provider_label": _safe_str(meta.get("label")),
                "source_room_id": _safe_str(room_source.get("room_id")),
                "remote_peer_id": remote_peer_id,
                "grant_id": _safe_str(grant_meta.get("grant_id")),
                "artifact_id": _safe_str(grant_meta.get("artifact_id")),
                "shared_room_config_enabled": bool(room_source.get("shared_room_config_enabled")),
                "shared_supervisor_enabled": bool(room_source.get("shared_supervisor_enabled")),
                "owner_private_scope_exposed": bool(shared_boundary.get("owner_private_scope_exposed")),
                "error": "provider_nonfinal_result",
                "user_message": user_message,
                "upstream_status": upstream_status,
                "upstream_message": upstream_message,
                "upstream_response": upstream_response,
                "upstream_tool_result_types": upstream_tool_types,
            }
        ],
    )


def _normalize_room_shared_provider_result_packet(
    *,
    packet: Dict[str, Any],
    room_id: str,
    request_id: str,
    requested_mode: str,
    mcp_overrides: Dict[str, Any],
    question: str,
    role: Dict[str, Any],
    provider_meta: Dict[str, Any],
    remote_peer_id: str = "",
) -> Dict[str, Any]:
    src = _safe_dict(packet)
    if not src:
        return _nonfinal_room_shared_provider_packet(
            room_id=room_id,
            request_id=request_id,
            requested_mode=requested_mode,
            mcp_overrides=mcp_overrides,
            question=question,
            role=role,
            provider_meta=provider_meta,
            upstream_packet={},
            remote_peer_id=remote_peer_id,
        )

    if _packet_has_terminal_deny(src):
        return src

    status = _safe_str(src.get("status"), "success").lower()
    if status not in {"success", "ok"}:
        return src

    if _room_shared_provider_success_has_final_signal(src):
        return src

    return _nonfinal_room_shared_provider_packet(
        room_id=room_id,
        request_id=request_id,
        requested_mode=requested_mode,
        mcp_overrides=mcp_overrides,
        question=question,
        role=role,
        provider_meta=provider_meta,
        upstream_packet=src,
        remote_peer_id=remote_peer_id,
    )


__all__ = [
    "_federated_provider_error_packet",
    "_nonfinal_room_shared_provider_packet",
    "_normalize_room_shared_provider_result_packet",
    "_packet_has_terminal_deny",
    "_packet_tool_result_types",
    "_provider_error_packet",
    "_room_shared_provider_success_has_final_signal",
]
