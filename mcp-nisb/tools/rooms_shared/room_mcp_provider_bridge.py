from __future__ import annotations

from typing import Any, Dict, List

from .room_request_bridge import (
    _safe_dict,
    _safe_str,
)
from .room_mcp_bridge_grant_context import (
    _build_bridge_mcp_binding,
    _extract_basepath,
    _extract_bridge_actor_user_id,
    _extract_bridge_grant_meta,
    _extract_imported_remote_peer_id,
    _extract_imported_remote_target_identity,
    _extract_provider_origin,
    _extract_share_ref,
    _resolve_imported_remote_peer_via_federation,
    _resolve_imported_remote_timeout_ms,
)
from .room_mcp_provider_result_packet import (
    _federated_provider_error_packet,
    _normalize_room_shared_provider_result_packet,
    _packet_has_terminal_deny,
    _provider_error_packet,
)

_LOCAL_ROOM_SHARED_ORIGIN = "local_room_shared"
_IMPORTED_REMOTE_ORIGIN_PREFIX = "imported_remote"

_LOCAL_ROOM_SHARED_ORIGIN_ALIASES = {
    "",
    "local",
    "local_registry",
    "registry_local",
    "local_provider",
    "local_room",
    "local_room_shared",
}

def _safe_list(v: Any) -> List[Any]:
    return list(v) if isinstance(v, list) else []


def _safe_query_str(value: Any) -> str:
    s = _safe_str(value)
    if s == "{{user_query}}":
        return ""
    return s


def _normalize_question(*, question: str, request_args: Dict[str, Any]) -> str:
    req = _safe_dict(request_args)
    mcp_binding = _safe_dict(req.get("mcp_binding"))
    params = _safe_dict(mcp_binding.get("params"))

    for candidate in (
        question,
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
        value = _safe_query_str(candidate)
        if value:
            return value
    return ""


def _apply_question_aliases(payload: Dict[str, Any], question: str) -> Dict[str, Any]:
    out = dict(_safe_dict(payload))
    resolved_question = _safe_str(question)
    if not resolved_question:
        return out

    out["question"] = resolved_question
    out["content"] = resolved_question
    out["prompt"] = resolved_question
    out["message"] = resolved_question
    out["_user_question"] = resolved_question
    return out


def _apply_mcp_binding_question_aliases(mcp_binding: Dict[str, Any], question: str) -> Dict[str, Any]:
    binding = dict(_safe_dict(mcp_binding))
    params = dict(_safe_dict(binding.get("params")))
    resolved_question = _safe_str(question)

    if resolved_question:
        params["question"] = resolved_question
        params["content"] = resolved_question
        params["prompt"] = resolved_question
        params["message"] = resolved_question

    binding["params"] = params
    return binding

def _is_room_shared_provider_meta(provider_meta: Dict[str, Any], provider_id: str = "") -> bool:
    meta = _safe_dict(provider_meta)
    kind = _safe_str(meta.get("provider_kind") or meta.get("provider_type")).lower()
    pid = _safe_str(provider_id or meta.get("provider_id"))
    return kind == "room_shared_capability" or pid.startswith("room_provider__")


def _pick_packet_final_text(packet: Dict[str, Any]) -> str:
    pkt = _safe_dict(packet)
    for key in (
        "final_response",
        "response",
        "content",
        "message",
        "summary",
        "text",
    ):
        value = _safe_str(pkt.get(key))
        if value:
            return value

    evidence_result = _safe_dict(pkt.get("evidence_result"))
    for key in (
        "final_response",
        "response",
        "content",
        "message",
        "summary",
        "text",
    ):
        value = _safe_str(evidence_result.get(key))
        if value:
            return value

    return ""


def _append_room_mcp_final_result_view(
    *,
    packet: Dict[str, Any],
    provider_meta: Dict[str, Any],
    provider_id: str,
    requested_mode: str,
    role: Dict[str, Any],
    consumer_room_id: str = "",
    actor_user_id: str = "",
) -> Dict[str, Any]:
    out = dict(packet or {})
    if not _is_room_shared_provider_meta(provider_meta, provider_id):
        return out

    tool_results = _safe_list(out.get("tool_results"))
    pid = _safe_str(provider_id or _safe_dict(provider_meta).get("provider_id"))
    room_source = _safe_dict(_safe_dict(provider_meta).get("room_source"))
    source_room_id = _safe_str(room_source.get("room_id"))
    status = _safe_str(out.get("status")) or ("success" if _safe_str(out.get("response") or out.get("content")) else "")
    final_response = _pick_packet_final_text(out)

    for item in tool_results:
        row = _safe_dict(item)
        if (
            _safe_str(row.get("type")) == "room_mcp_final_result_view"
            and _safe_str(row.get("provider_id")) == pid
            and _safe_str(row.get("source_room_id")) == source_room_id
            and _safe_str(row.get("consumer_room_id")) == _safe_str(consumer_room_id)
        ):
            return out

    role_id = _safe_str(_safe_dict(role).get("role_id"))
    role_name = _safe_str(_safe_dict(role).get("name") or _safe_dict(role).get("slug") or role_id)

    result_state = "success" if status.lower() in {"success", "ok"} else ("error" if status else "")
    provider_origin = _safe_str(_safe_dict(provider_meta).get("provider_origin"))
    shared_boundary = _safe_dict(room_source.get("shared_boundary"))

    tool_results.append(
        {
            "type": "room_mcp_final_result_view",
            "role_id": role_id,
            "role_name": role_name,
            "provider_id": pid,
            "provider_type": _safe_str(
                _safe_dict(provider_meta).get("provider_type")
                or _safe_dict(provider_meta).get("provider_kind"),
                "room_shared_capability",
            ),
            "provider_origin": provider_origin,
            "provider_label": _safe_str(_safe_dict(provider_meta).get("label")),
            "requested_mode": requested_mode,
            "status": status,
            "result_state": result_state,
            "consumer_room_id": _safe_str(consumer_room_id),
            "source_room_id": source_room_id,
            "actor_user_id": _safe_str(actor_user_id),
            "reply_mode": _safe_str(room_source.get("reply_mode")),
            "shared_room_config_enabled": bool(room_source.get("shared_room_config_enabled")),
            "shared_supervisor_enabled": bool(room_source.get("shared_supervisor_enabled")),
            "owner_private_scope_exposed": bool(shared_boundary.get("owner_private_scope_exposed")),
            "final_response": final_response,
            "content": final_response,
        }
    )
    out["tool_results"] = tool_results

    if final_response and not _safe_str(out.get("response")):
        out["response"] = final_response
    if final_response and not _safe_str(out.get("content")):
        out["content"] = final_response

    return out

def _append_execution_fact(
    *,
    packet: Dict[str, Any],
    provider_meta: Dict[str, Any],
    provider_id: str,
    requested_mode: str,
    role: Dict[str, Any],
    consumer_room_id: str = "",
    actor_user_id: str = "",
) -> Dict[str, Any]:
    out = dict(packet or {})
    auth_state = _safe_dict(provider_meta.get("auth_state"))
    availability = _safe_dict(provider_meta.get("availability"))
    room_source = _safe_dict(provider_meta.get("room_source"))
    shared_boundary = _safe_dict(room_source.get("shared_boundary"))
    role_id = _safe_str(role.get("role_id"))
    role_name = _safe_str(role.get("name") or role.get("slug") or role_id)
    pid = _safe_str(provider_id or provider_meta.get("provider_id"))

    out = _append_room_mcp_final_result_view(
        packet=out,
        provider_meta=provider_meta,
        provider_id=pid,
        requested_mode=requested_mode,
        role=role,
        consumer_room_id=consumer_room_id,
        actor_user_id=actor_user_id,
    )

    tool_results = _safe_list(out.get("tool_results"))
    source_room_id = _safe_str(room_source.get("room_id"))
    already_has_execution = False
    for item in tool_results:
        row = _safe_dict(item)
        if (
            _safe_str(row.get("type")) == "room_mcp_provider_execution"
            and _safe_str(row.get("provider_id")) == pid
            and _safe_str(row.get("consumer_room_id")) == _safe_str(consumer_room_id)
            and _safe_str(row.get("source_room_id")) == source_room_id
        ):
            already_has_execution = True
            break

    if not already_has_execution:
        tool_results.append(
            {
                "type": "room_mcp_provider_execution",
                "role_id": role_id,
                "role_name": role_name,
                "provider_id": pid,
                "provider_type": _safe_str(provider_meta.get("provider_type"), "preset"),
                "provider_origin": _safe_str(provider_meta.get("provider_origin")),
                "provider_label": _safe_str(provider_meta.get("label")),
                "requested_mode": requested_mode,
                "status": _safe_str(out.get("status")),
                "auth_type": _safe_str(auth_state.get("type")),
                "auth_required": bool(auth_state.get("required")),
                "auth_configured": bool(auth_state.get("configured")),
                "availability_reason": _safe_str(availability.get("reason")),
                "consumer_room_id": _safe_str(consumer_room_id),
                "source_room_id": source_room_id,
                "actor_user_id": _safe_str(actor_user_id),
                "shared_room_config_enabled": bool(room_source.get("shared_room_config_enabled")),
                "shared_supervisor_enabled": bool(room_source.get("shared_supervisor_enabled")),
                "reply_mode": _safe_str(room_source.get("reply_mode")),
                "owner_private_scope_exposed": bool(shared_boundary.get("owner_private_scope_exposed")),
            }
        )

    out["tool_results"] = tool_results

    if not _safe_str(out.get("response")):
        out["response"] = _safe_str(out.get("message") or out.get("content"))

    return out


def _is_local_room_shared_origin(origin: Any) -> bool:
    aliases = globals().get("_LOCAL_ROOM_SHARED_ORIGIN_ALIASES")
    if not isinstance(aliases, set):
        aliases = {
            "",
            "local",
            "local_registry",
            "registry_local",
            "local_provider",
            "local_room",
            "local_room_shared",
        }
    return _safe_str(origin).lower() in aliases


def _stamp_local_room_shared_origin(value: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(_safe_dict(value))
    if not out:
        return {}

    out["provider_origin"] = _LOCAL_ROOM_SHARED_ORIGIN

    source_ref = _safe_dict(out.get("source_ref"))
    if source_ref:
        source_ref["origin"] = _LOCAL_ROOM_SHARED_ORIGIN
        out["source_ref"] = source_ref

    invoke_contract = _safe_dict(out.get("invoke_contract"))
    if invoke_contract:
        out["invoke_contract"] = invoke_contract

    room_source = _safe_dict(out.get("room_source"))
    if room_source:
        out["room_source"] = room_source

    return out


def _resolve_room_shared_bridge_origin(
    *,
    provider_meta: Dict[str, Any],
    request_args: Dict[str, Any],
) -> str:
    meta = _safe_dict(provider_meta)

    direct_origin = _safe_str(meta.get("provider_origin")).lower()
    source_ref_origin = _safe_str(_safe_dict(meta.get("source_ref")).get("origin")).lower()
    origin_meta = _safe_dict(meta.get("provider_origin_meta"))
    adapter_dispatch = _safe_str(origin_meta.get("adapter_dispatch")).lower()

    if (
        _is_local_room_shared_origin(direct_origin)
        or _is_local_room_shared_origin(source_ref_origin)
        or adapter_dispatch == _LOCAL_ROOM_SHARED_ORIGIN
    ):
        return _LOCAL_ROOM_SHARED_ORIGIN

    extracted = _safe_str(_extract_provider_origin(meta, request_args)).lower()
    if _is_local_room_shared_origin(extracted):
        return _LOCAL_ROOM_SHARED_ORIGIN

    if extracted:
        return extracted
    if direct_origin:
        return direct_origin
    if source_ref_origin:
        return source_ref_origin

    return _LOCAL_ROOM_SHARED_ORIGIN

def _provider_meta_with_bridge_grant_meta(
    provider_meta: Dict[str, Any],
    grant_meta: Dict[str, Any],
    *,
    share_ref: str = "",
) -> Dict[str, Any]:
    out = dict(_safe_dict(provider_meta))
    grant = dict(_safe_dict(grant_meta))
    if not grant:
        return out

    if share_ref and not _safe_str(grant.get("share_ref")):
        grant["share_ref"] = share_ref

    out["_grant_meta"] = grant
    out["grant_meta"] = grant
    out["grant"] = grant
    out["grant_id"] = _safe_str(grant.get("grant_id"))
    out["artifact_id"] = _safe_str(grant.get("artifact_id"))
    out["grant_state"] = _safe_str(grant.get("grant_state"))
    out["grant_mode"] = _safe_str(grant.get("grant_mode"))
    out["discovery_mode"] = _safe_str(grant.get("discovery_mode"))
    out["resolution_source"] = _safe_str(grant.get("resolution_source"))
    out["external_result_view"] = _safe_str(grant.get("external_result_view"))
    if share_ref:
        out["share_ref"] = share_ref

    room_source = dict(_safe_dict(out.get("room_source")))
    if room_source:
        if share_ref and not _safe_str(room_source.get("share_ref")):
            room_source["share_ref"] = share_ref
        out["room_source"] = room_source

    return out

def _bridge_extract_any_share_ref(
    *,
    provider_meta: Dict[str, Any],
    request_args: Dict[str, Any],
) -> str:
    meta = _safe_dict(provider_meta)
    req = _safe_dict(request_args)
    mcp_binding = _safe_dict(req.get("mcp_binding"))
    params = _safe_dict(mcp_binding.get("params"))
    room_source = _safe_dict(meta.get("room_source"))

    provider_snapshot = _safe_dict(
        req.get("mcp_provider_snapshot")
        or req.get("provider_snapshot")
        or mcp_binding.get("provider_snapshot")
        or meta.get("provider_snapshot")
    )
    imported_provider = _safe_dict(
        req.get("imported_provider")
        or mcp_binding.get("imported_provider")
        or meta.get("imported_provider")
    )

    containers = (
        req,
        mcp_binding,
        params,
        meta,
        room_source,
        provider_snapshot,
        imported_provider,
        _safe_dict(meta.get("_grant_meta")),
        _safe_dict(meta.get("grant_meta")),
        _safe_dict(meta.get("grant")),
        _safe_dict(req.get("_room_mcp_grant")),
        _safe_dict(req.get("grant_meta")),
        _safe_dict(req.get("grant")),
        _safe_dict(mcp_binding.get("grant_meta")),
        _safe_dict(mcp_binding.get("grant")),
        _safe_dict(provider_snapshot.get("_grant_meta")),
        _safe_dict(provider_snapshot.get("grant_meta")),
        _safe_dict(provider_snapshot.get("grant")),
        _safe_dict(imported_provider.get("_grant_meta")),
        _safe_dict(imported_provider.get("grant_meta")),
        _safe_dict(imported_provider.get("grant")),
    )

    for row in containers:
        obj = _safe_dict(row)
        for key in (
            "mcp_share_ref",
            "share_ref",
            "descriptor_ref",
            "grant_ref",
            "room_mcp_grant_ref",
        ):
            value = _safe_str(obj.get(key))
            if value:
                return value

    return ""


def _bridge_merge_grant_locator(
    *,
    provider_meta: Dict[str, Any],
    request_args: Dict[str, Any],
    grant_meta: Dict[str, Any],
    share_ref: str,
    source_room_id: str,
    provider_id: str,
) -> Dict[str, Any]:
    merged: Dict[str, Any] = {}

    if share_ref:
        try:
            from .room_tools_mcp_providers import parse_room_mcp_grant_artifact

            parsed = _safe_dict(parse_room_mcp_grant_artifact(share_ref))
            if parsed:
                merged.update(parsed)
        except Exception:
            pass

    base_grant = _safe_dict(grant_meta)
    if base_grant:
        merged.update(base_grant)

    meta = _safe_dict(provider_meta)
    req = _safe_dict(request_args)
    mcp_binding = _safe_dict(req.get("mcp_binding"))
    room_source = _safe_dict(meta.get("room_source"))
    provider_snapshot = _safe_dict(
        req.get("mcp_provider_snapshot")
        or req.get("provider_snapshot")
        or mcp_binding.get("provider_snapshot")
        or meta.get("provider_snapshot")
    )
    imported_provider = _safe_dict(
        req.get("imported_provider")
        or mcp_binding.get("imported_provider")
        or meta.get("imported_provider")
    )

    containers = (
        req,
        mcp_binding,
        meta,
        room_source,
        provider_snapshot,
        imported_provider,
        _safe_dict(meta.get("_grant_meta")),
        _safe_dict(meta.get("grant_meta")),
        _safe_dict(meta.get("grant")),
        _safe_dict(req.get("_room_mcp_grant")),
        _safe_dict(req.get("grant_meta")),
        _safe_dict(req.get("grant")),
        _safe_dict(mcp_binding.get("grant_meta")),
        _safe_dict(mcp_binding.get("grant")),
        _safe_dict(provider_snapshot.get("_grant_meta")),
        _safe_dict(provider_snapshot.get("grant_meta")),
        _safe_dict(provider_snapshot.get("grant")),
        _safe_dict(imported_provider.get("_grant_meta")),
        _safe_dict(imported_provider.get("grant_meta")),
        _safe_dict(imported_provider.get("grant")),
    )

    scalar_keys = (
        "grant_id",
        "artifact_id",
        "provider_id",
        "source_room_id",
        "grant_state",
        "grant_mode",
        "discovery_mode",
        "resolution_source",
        "external_result_view",
        "result_view",
        "revoked_at",
        "revoked_by",
        "expires_at",
        "issued_at",
    )

    for row in containers:
        obj = _safe_dict(row)
        for key in scalar_keys:
            if not _safe_str(merged.get(key)):
                value = _safe_str(obj.get(key))
                if value:
                    merged[key] = value

        if "source_observation_allowed" not in merged and "source_observation_allowed" in obj:
            merged["source_observation_allowed"] = bool(obj.get("source_observation_allowed"))
        if "audience" not in merged and isinstance(obj.get("audience"), dict):
            merged["audience"] = _safe_dict(obj.get("audience"))
        if "scope" not in merged and isinstance(obj.get("scope"), dict):
            merged["scope"] = _safe_dict(obj.get("scope"))
        if "route_identity" not in merged and isinstance(obj.get("route_identity"), dict):
            merged["route_identity"] = _safe_dict(obj.get("route_identity"))

    if share_ref:
        if not _safe_str(merged.get("share_ref")):
            merged["share_ref"] = share_ref
        if not _safe_str(merged.get("descriptor_ref")):
            merged["descriptor_ref"] = share_ref

    if source_room_id and not _safe_str(merged.get("source_room_id")):
        merged["source_room_id"] = source_room_id
    if provider_id and not _safe_str(merged.get("provider_id")):
        merged["provider_id"] = provider_id

    has_locator = bool(
        _safe_str(merged.get("grant_id"))
        or _safe_str(merged.get("artifact_id"))
        or _safe_str(merged.get("share_ref")).startswith("room-mcp-grant:")
        or _safe_str(merged.get("descriptor_ref")).startswith("room-mcp-grant:")
    )

    return merged if has_locator else {}

def _imported_grant_state_error(grant_meta: Dict[str, Any]) -> str:
    grant_state = _safe_str(_safe_dict(grant_meta).get("grant_state")).lower()
    if not grant_state or grant_state == "active":
        return ""
    if grant_state == "revoked":
        return "grant_revoked"
    if grant_state == "expired":
        return "grant_expired"
    return f"grant_{grant_state}"


def _build_imported_grant_state_deny_packet(
    *,
    provider_meta: Dict[str, Any],
    room_id: str,
    request_id: str,
    question: str,
    requested_mode: str,
    mcp_overrides: Dict[str, Any],
    role: Dict[str, Any],
    grant_meta: Dict[str, Any],
    share_ref: str = "",
) -> Dict[str, Any]:
    grant = _safe_dict(grant_meta)
    error = _imported_grant_state_error(grant)
    if not error:
        return {}

    enriched_meta = _provider_meta_with_bridge_grant_meta(
        provider_meta,
        grant,
        share_ref=share_ref,
    )

    provider_id = _safe_str(enriched_meta.get("provider_id"))
    room_source = _safe_dict(enriched_meta.get("room_source"))
    source_room_id = _safe_str(
        grant.get("source_room_id")
        or room_source.get("room_id")
    )
    grant_state = _safe_str(grant.get("grant_state")).lower()
    deny_reason_code = error.upper()

    packet = _provider_error_packet(
        room_id=room_id,
        request_id=request_id,
        requested_mode=requested_mode,
        mcp_overrides=mcp_overrides,
        question=question,
        role=role,
        provider_id=provider_id,
        error=error,
        provider_meta=enriched_meta,
    )

    packet["status"] = "error"
    packet["result_state"] = "error"
    packet["error"] = error
    packet["message"] = _safe_str(packet.get("message")) or f"room provider invoke denied: {deny_reason_code}"
    packet["content"] = _safe_str(packet.get("content")) or packet["message"]
    packet["response"] = _safe_str(packet.get("response")) or packet["message"]

    packet["grant_trace"] = {
        "status": "denied",
        "deny_stage": "imported_remote_bridge_pre_federation_call",
        "deny_reason_code": deny_reason_code,
        "provider_id": provider_id,
        "provider_origin": "imported_remote",
        "source_room_id": source_room_id,
        "consumer_room_id": _safe_str(room_id),
        "grant_id": _safe_str(grant.get("grant_id")),
        "artifact_id": _safe_str(grant.get("artifact_id")),
        "grant_state": grant_state,
        "live_grant_state": _safe_str(grant.get("live_grant_state")),
        "grant_state_snapshot": _safe_str(grant.get("grant_state_snapshot")),
        "live_grant_resolved": bool(grant.get("_live_grant_resolved")),
        "live_grant_missing": bool(grant.get("_live_grant_missing")),
        "resolution_source": _safe_str(grant.get("resolution_source")),
    }
    packet["consume_trace"] = {
        "status": "denied",
        "deny_reason_code": deny_reason_code,
        "grant_id": _safe_str(grant.get("grant_id")),
        "artifact_id": _safe_str(grant.get("artifact_id")),
        "grant_state": grant_state,
    }

    tool_results = _safe_list(packet.get("tool_results"))
    tool_results.append(
        {
            "type": "room_mcp_grant_live_check",
            "provider_id": provider_id,
            "provider_origin": "imported_remote",
            "status": "denied",
            "deny_stage": "imported_remote_bridge_pre_federation_call",
            "deny_reason_code": deny_reason_code,
            "consumer_room_id": _safe_str(room_id),
            "source_room_id": source_room_id,
            "grant_id": _safe_str(grant.get("grant_id")),
            "artifact_id": _safe_str(grant.get("artifact_id")),
            "grant_state": grant_state,
            "live_grant_state": _safe_str(grant.get("live_grant_state")),
            "grant_state_snapshot": _safe_str(grant.get("grant_state_snapshot")),
            "live_grant_resolved": bool(grant.get("_live_grant_resolved")),
            "live_grant_missing": bool(grant.get("_live_grant_missing")),
            "resolution_source": _safe_str(grant.get("resolution_source")),
        }
    )
    packet["tool_results"] = tool_results

    return packet

def _dispatch_imported_remote_room_shared_provider(
    *,
    provider_meta: Dict[str, Any],
    room_id: str,
    request_id: str,
    question: str,
    requested_mode: str,
    mcp_overrides: Dict[str, Any],
    request_args: Dict[str, Any],
    role: Dict[str, Any],
) -> Dict[str, Any]:
    from ..federation.tools import nisb_fed_call

    room_source = _safe_dict(provider_meta.get("room_source"))
    source_room_id = _safe_str(room_source.get("room_id"))
    provider_id = _safe_str(provider_meta.get("provider_id"))
    provider_type = _safe_str(provider_meta.get("provider_type"), "room_shared_capability")

    if not source_room_id:
        return _provider_error_packet(
            room_id=room_id,
            request_id=request_id,
            requested_mode=requested_mode,
            mcp_overrides=mcp_overrides,
            question=question,
            role=role,
            provider_id=provider_id,
            error="missing_room_source",
            provider_meta=provider_meta,
        )

    basepath = _extract_basepath(request_args)
    if not basepath:
        return _federated_provider_error_packet(
            room_id=room_id,
            request_id=request_id,
            requested_mode=requested_mode,
            mcp_overrides=mcp_overrides,
            question=question,
            role=role,
            provider_meta=provider_meta,
            error="missing_basepath",
        )

    raw_grant_meta = _extract_bridge_grant_meta(
        provider_meta=provider_meta,
        request_args=request_args,
    )
    share_ref = _extract_share_ref(provider_meta, request_args)
    if not share_ref:
        share_ref = _bridge_extract_any_share_ref(
            provider_meta=provider_meta,
            request_args=request_args,
        )

    grant_meta = _bridge_merge_grant_locator(
        provider_meta=provider_meta,
        request_args=request_args,
        grant_meta=raw_grant_meta,
        share_ref=share_ref,
        source_room_id=source_room_id,
        provider_id=provider_id,
    )
    if not share_ref:
        share_ref = _safe_str(
            grant_meta.get("share_ref")
            or grant_meta.get("descriptor_ref")
        )

    grant_audience = _safe_dict(grant_meta.get("audience"))

    provider_meta_for_call = provider_meta
    if grant_meta:
        provider_meta_for_call = _provider_meta_with_bridge_grant_meta(
            provider_meta,
            grant_meta,
            share_ref=share_ref,
        )

    grant_deny_packet = _build_imported_grant_state_deny_packet(
        provider_meta=provider_meta_for_call,
        room_id=room_id,
        request_id=request_id,
        question=question,
        requested_mode=requested_mode,
        mcp_overrides=mcp_overrides,
        role=role,
        grant_meta=grant_meta,
        share_ref=share_ref,
    )
    if grant_deny_packet:
        return grant_deny_packet

    peer_resolve: Dict[str, Any] = {}
    remote_peer_id = _extract_imported_remote_peer_id(
        provider_meta=provider_meta_for_call,
        request_args=request_args,
        basepath=basepath,
    )

    if not remote_peer_id:
        peer_resolve = _resolve_imported_remote_peer_via_federation(
            basepath=basepath,
            provider_meta=provider_meta_for_call,
            request_args=request_args,
        )
        remote_peer_id = _safe_str(_safe_dict(peer_resolve).get("peer_id"))

    if not remote_peer_id:
        target_identity = _extract_imported_remote_target_identity(
            provider_meta=provider_meta_for_call,
            request_args=request_args,
        )
        return _federated_provider_error_packet(
            room_id=room_id,
            request_id=request_id,
            requested_mode=requested_mode,
            mcp_overrides=mcp_overrides,
            question=question,
            role=role,
            provider_meta=provider_meta_for_call,
            error=_safe_str(_safe_dict(peer_resolve).get("error_code")) or "missing_remote_peer_id",
            upstream={
                **_safe_dict(peer_resolve),
                "target_identity": target_identity,
            },
        )

    mcp_binding = _safe_dict(request_args.get("mcp_binding"))
    target_question = _normalize_question(question=question, request_args=request_args)
    target_question = _safe_str(target_question) or question

    actor_user_id = _extract_bridge_actor_user_id(request_args)

    provider_snapshot = _safe_dict(
        request_args.get("mcp_provider_snapshot")
        or request_args.get("provider_snapshot")
        or mcp_binding.get("provider_snapshot")
    )
    imported_provider = _safe_dict(
        request_args.get("imported_provider")
        or mcp_binding.get("imported_provider")
    )

    bridge_mcp_binding = _build_bridge_mcp_binding(
        provider_meta=provider_meta_for_call,
        provider_origin="imported_remote",
        question=target_question,
        share_ref=share_ref,
        provider_snapshot=provider_snapshot,
        imported_provider=imported_provider,
        grant_meta=grant_meta,
        base_binding=mcp_binding,
        apply_mcp_binding_question_aliases=_apply_mcp_binding_question_aliases,
    )

    if share_ref:
        bridge_mcp_binding["share_ref"] = share_ref
        bridge_mcp_binding["mcp_share_ref"] = share_ref
        bridge_mcp_binding["descriptor_ref"] = share_ref

    if grant_meta:
        bridge_mcp_binding["_room_mcp_grant"] = dict(grant_meta)
        bridge_mcp_binding["grant_meta"] = dict(grant_meta)
        bridge_mcp_binding["grant"] = dict(grant_meta)

        for key in (
            "grant_id",
            "artifact_id",
            "grant_state",
            "grant_mode",
            "discovery_mode",
            "resolution_source",
            "external_result_view",
            "source_room_id",
            "provider_id",
        ):
            value = grant_meta.get(key)
            if value not in (None, ""):
                bridge_mcp_binding[key] = value

    requested_timeout_ms = _resolve_imported_remote_timeout_ms(request_args)
    effective_timeout_ms = requested_timeout_ms

    remote_provider_meta = {
        "provider_id": provider_id,
        "provider_type": provider_type,
        "provider_origin": "imported_remote",
        "label": _safe_str(provider_meta_for_call.get("label")),
        "share_ref": share_ref,
        "mcp_share_ref": share_ref,
        "descriptor_ref": share_ref,
        "grant_id": _safe_str(grant_meta.get("grant_id")),
        "artifact_id": _safe_str(grant_meta.get("artifact_id")),
        "grant_state": _safe_str(grant_meta.get("grant_state")),
        "grant_mode": _safe_str(grant_meta.get("grant_mode")),
        "discovery_mode": _safe_str(grant_meta.get("discovery_mode")),
        "resolution_source": _safe_str(grant_meta.get("resolution_source")),
        "external_result_view": _safe_str(grant_meta.get("external_result_view")),
        "source_observation_allowed": bool(grant_meta.get("source_observation_allowed")),
        "grant_audience": grant_audience,
        "share_ref_payload": _safe_dict(grant_meta),
        "room_source": {
            **_safe_dict(provider_meta_for_call.get("room_source")),
            "room_id": source_room_id,
            "share_ref": share_ref,
            "descriptor_ref": share_ref,
        },
    }
    if provider_snapshot:
        remote_provider_meta["provider_snapshot"] = dict(provider_snapshot)
    if imported_provider:
        remote_provider_meta["imported_provider"] = dict(imported_provider)
    if grant_meta:
        remote_provider_meta["_grant_meta"] = dict(grant_meta)
        remote_provider_meta["grant_meta"] = dict(grant_meta)
        remote_provider_meta["grant"] = dict(grant_meta)

    remote_tool_args: Dict[str, Any] = _apply_question_aliases(
        {
            "room_id": source_room_id,
            "mcp_binding": bridge_mcp_binding,
            "_room_mcp_provider_call": True,
            "_room_mcp_provider_id": provider_id,
            "_room_mcp_provider_type": provider_type,
            "_room_mcp_provider_origin": "imported_remote",
            "_room_mcp_source_room_id": source_room_id,
            "_room_mcp_consumer_room_id": room_id,
            "_room_mcp_actor_user_id": actor_user_id,
            "_room_mcp_requested_mode": requested_mode,
            "_room_mcp_bridge": "imported_remote_room_shared_capability",
            "_room_mcp_timeout_ms_requested": requested_timeout_ms,
            "_room_mcp_timeout_ms_effective": effective_timeout_ms,
            "_room_mcp_provider_meta": remote_provider_meta,
            "_room_mcp_grant_locator_present": bool(grant_meta),
            "provider_meta": remote_provider_meta,
        },
        target_question,
    )

    if actor_user_id:
        remote_tool_args["actor_user_id"] = actor_user_id
        remote_tool_args["user_id"] = actor_user_id
        remote_tool_args["sender_user_id"] = actor_user_id
        remote_tool_args["sender"] = actor_user_id

    for src_key, dst_key in (
        ("_federation_peer_id", "_federation_peer_id"),
        ("_federation_remote_user_id", "_federation_remote_user_id"),
        ("_federation_remote_label", "_federation_remote_label"),
        ("federation_peer_id", "_federation_peer_id"),
        ("federation_remote_user_id", "_federation_remote_user_id"),
        ("federation_remote_label", "_federation_remote_label"),
    ):
        value = _safe_str(request_args.get(src_key))
        if value:
            remote_tool_args[dst_key] = value

    if share_ref:
        remote_tool_args["mcp_share_ref"] = share_ref
        remote_tool_args["share_ref"] = share_ref
        remote_tool_args["descriptor_ref"] = share_ref

    if provider_snapshot:
        remote_tool_args["mcp_provider_snapshot"] = provider_snapshot
    if imported_provider:
        remote_tool_args["imported_provider"] = imported_provider

    if grant_meta:
        remote_tool_args["_room_mcp_grant"] = dict(grant_meta)
        remote_tool_args["grant_meta"] = dict(grant_meta)
        remote_tool_args["grant"] = dict(grant_meta)

        for key in (
            "grant_id",
            "artifact_id",
            "grant_state",
            "grant_mode",
            "discovery_mode",
            "resolution_source",
            "external_result_view",
            "source_room_id",
            "provider_id",
        ):
            value = grant_meta.get(key)
            if value not in (None, ""):
                remote_tool_args[key] = value
                remote_tool_args["mcp_binding"][key] = value

        if share_ref:
            remote_tool_args["mcp_binding"]["share_ref"] = share_ref
            remote_tool_args["mcp_binding"]["mcp_share_ref"] = share_ref
            remote_tool_args["mcp_binding"]["descriptor_ref"] = share_ref

    if peer_resolve:
        remote_tool_args["_room_mcp_peer_resolve"] = peer_resolve

    fed_args = dict(request_args or {})
    fed_args["basepath"] = basepath
    fed_args["peer_id"] = remote_peer_id
    fed_args["tool"] = "nisb_room_shared_provider_post"
    fed_args["tool_args"] = remote_tool_args
    fed_args["timeout_ms"] = effective_timeout_ms

    try:
        remote = nisb_fed_call(fed_args)
    except Exception as e:
        return _federated_provider_error_packet(
            room_id=room_id,
            request_id=request_id,
            requested_mode=requested_mode,
            mcp_overrides=mcp_overrides,
            question=question,
            role=role,
            provider_meta=provider_meta_for_call,
            error="imported_remote_federated_bridge_exception",
            remote_peer_id=remote_peer_id,
            upstream={
                "message": str(e),
                "error_code": "imported_remote_federated_bridge_exception",
                "error_kind": "bridge",
                "timeout_ms_requested": requested_timeout_ms,
                "timeout_ms_effective": effective_timeout_ms,
            },
        )

    if not bool(remote.get("success")):
        upstream = dict(_safe_dict(remote))
        upstream.setdefault("timeout_ms_requested", requested_timeout_ms)
        upstream.setdefault("timeout_ms_effective", effective_timeout_ms)
        return _federated_provider_error_packet(
            room_id=room_id,
            request_id=request_id,
            requested_mode=requested_mode,
            mcp_overrides=mcp_overrides,
            question=question,
            role=role,
            provider_meta=provider_meta_for_call,
            error=_safe_str(remote.get("error_code")) or "imported_remote_federated_call_failed",
            remote_peer_id=remote_peer_id,
            upstream=upstream,
        )

    packet = _safe_dict(remote.get("result"))
    if not packet:
        return _federated_provider_error_packet(
            room_id=room_id,
            request_id=request_id,
            requested_mode=requested_mode,
            mcp_overrides=mcp_overrides,
            question=question,
            role=role,
            provider_meta=provider_meta_for_call,
            error="invalid_remote_result",
            remote_peer_id=remote_peer_id,
            upstream={
                "message": "remote tool returned empty result",
                "error_code": "invalid_remote_result",
                "error_kind": "remote_result",
                "timeout_ms_requested": requested_timeout_ms,
                "timeout_ms_effective": effective_timeout_ms,
            },
        )

    packet = _normalize_room_shared_provider_result_packet(
        packet=packet,
        room_id=room_id,
        request_id=request_id,
        requested_mode=requested_mode,
        mcp_overrides=mcp_overrides,
        question=question,
        role=role,
        provider_meta=provider_meta_for_call,
        remote_peer_id=remote_peer_id,
    )

    tool_results = _safe_list(packet.get("tool_results"))
    tool_results.append(
        {
            "type": "imported_remote_timeout_trace",
            "provider_id": provider_id,
            "provider_origin": "imported_remote",
            "remote_peer_id": remote_peer_id,
            "grant_locator_present": bool(grant_meta),
            "grant_id": _safe_str(grant_meta.get("grant_id")),
            "artifact_id": _safe_str(grant_meta.get("artifact_id")),
            "share_ref_present": bool(share_ref),
            "timeout_ms_requested": requested_timeout_ms,
            "timeout_ms_effective": effective_timeout_ms,
            "federation_timeout_ms": remote.get("timeout_ms"),
            "federation_timeout_sec": remote.get("timeout_sec"),
            "status_code": remote.get("status_code"),
            "url": remote.get("url"),
            "exception_type": _safe_str(remote.get("exception_type")),
        }
    )
    packet["tool_results"] = tool_results

    return packet


def _dispatch_room_shared_provider(
    *,
    provider_meta: Dict[str, Any],
    room_id: str,
    request_id: str,
    question: str,
    requested_mode: str,
    mcp_overrides: Dict[str, Any],
    request_args: Dict[str, Any],
    role: Dict[str, Any],
) -> Dict[str, Any]:
    from .room_tools_runtime import _dispatch_room_shared_provider_post

    provider_origin = _resolve_room_shared_bridge_origin(
        provider_meta=provider_meta,
        request_args=request_args,
    )

    if provider_origin.startswith(_IMPORTED_REMOTE_ORIGIN_PREFIX):
        packet = _dispatch_imported_remote_room_shared_provider(
            provider_meta=provider_meta,
            room_id=room_id,
            request_id=request_id,
            question=question,
            requested_mode=requested_mode,
            mcp_overrides=mcp_overrides,
            request_args=request_args,
            role=role,
        )
        return _append_execution_fact(
            packet=packet,
            provider_meta=provider_meta,
            provider_id=_safe_str(provider_meta.get("provider_id")),
            requested_mode=requested_mode,
            role=role,
            consumer_room_id=room_id,
            actor_user_id=_extract_bridge_actor_user_id(request_args),
        )

    provider_meta = _stamp_local_room_shared_origin(provider_meta)

    grant_meta = _safe_dict(provider_meta.get("_grant_meta"))
    grant_state = _safe_str(grant_meta.get("grant_state"))
    if grant_state == "revoked":
        return _provider_error_packet(
            room_id=room_id,
            request_id=request_id,
            requested_mode=requested_mode,
            mcp_overrides=mcp_overrides,
            question=question,
            role=role,
            provider_id=_safe_str(provider_meta.get("provider_id")),
            error="grant_revoked",
            provider_meta=provider_meta,
        )
    if grant_state == "expired":
        return _provider_error_packet(
            room_id=room_id,
            request_id=request_id,
            requested_mode=requested_mode,
            mcp_overrides=mcp_overrides,
            question=question,
            role=role,
            provider_id=_safe_str(provider_meta.get("provider_id")),
            error="grant_expired",
            provider_meta=provider_meta,
        )
    if grant_state and grant_state != "active":
        return _provider_error_packet(
            room_id=room_id,
            request_id=request_id,
            requested_mode=requested_mode,
            mcp_overrides=mcp_overrides,
            question=question,
            role=role,
            provider_id=_safe_str(provider_meta.get("provider_id")),
            error=f"grant_{grant_state}",
            provider_meta=provider_meta,
        )

    room_source = _safe_dict(provider_meta.get("room_source"))
    target_room_id = _safe_str(room_source.get("room_id"))
    if not target_room_id:
        return _provider_error_packet(
            room_id=room_id,
            request_id=request_id,
            requested_mode=requested_mode,
            mcp_overrides=mcp_overrides,
            question=question,
            role=role,
            provider_id=_safe_str(provider_meta.get("provider_id")),
            error="missing_room_source",
            provider_meta=provider_meta,
        )

    mcp_binding = _safe_dict(request_args.get("mcp_binding"))
    target_question = _normalize_question(question=question, request_args=request_args)
    target_question = _safe_str(target_question) or question

    bridge_request_args = dict(request_args or {})
    actor_user_id = _extract_bridge_actor_user_id(bridge_request_args)
    share_ref = _extract_share_ref(provider_meta, request_args)
    grant_meta = _extract_bridge_grant_meta(
        provider_meta=provider_meta,
        request_args=request_args,
    )

    provider_snapshot = _safe_dict(
        request_args.get("mcp_provider_snapshot")
        or request_args.get("provider_snapshot")
        or mcp_binding.get("provider_snapshot")
    )
    imported_provider = _safe_dict(
        request_args.get("imported_provider")
        or mcp_binding.get("imported_provider")
    )

    if provider_snapshot:
        provider_snapshot = _stamp_local_room_shared_origin(provider_snapshot)
    if imported_provider:
        imported_provider = _stamp_local_room_shared_origin(imported_provider)

    bridge_request_args["mcp_binding"] = _build_bridge_mcp_binding(
        provider_meta=provider_meta,
        provider_origin=_LOCAL_ROOM_SHARED_ORIGIN,
        question=target_question,
        share_ref=share_ref,
        provider_snapshot=provider_snapshot,
        imported_provider=imported_provider,
        grant_meta=grant_meta,
        base_binding=mcp_binding,
        apply_mcp_binding_question_aliases=_apply_mcp_binding_question_aliases,
    )

    bridge_request_args = _apply_question_aliases(bridge_request_args, target_question)
    bridge_request_args["_room_mcp_provider_call"] = True
    bridge_request_args["_room_mcp_consumer_room_id"] = room_id
    bridge_request_args["_room_mcp_actor_user_id"] = actor_user_id
    bridge_request_args["_room_mcp_provider_id"] = _safe_str(provider_meta.get("provider_id"))
    bridge_request_args["_room_mcp_provider_type"] = _safe_str(provider_meta.get("provider_type"))
    bridge_request_args["_room_mcp_provider_origin"] = _LOCAL_ROOM_SHARED_ORIGIN
    bridge_request_args["_room_mcp_source_room_id"] = target_room_id
    bridge_request_args["_room_mcp_requested_mode"] = requested_mode
    bridge_request_args["_room_mcp_bridge"] = "room_shared_capability"
    bridge_request_args["_room_mcp_provider_meta"] = provider_meta
    bridge_request_args["provider_meta"] = provider_meta

    if share_ref:
        bridge_request_args["mcp_share_ref"] = share_ref
        bridge_request_args["share_ref"] = share_ref

    if provider_snapshot:
        bridge_request_args["mcp_provider_snapshot"] = provider_snapshot
        bridge_request_args["provider_snapshot"] = provider_snapshot
    if imported_provider:
        bridge_request_args["imported_provider"] = imported_provider
    if grant_meta:
        bridge_request_args["_room_mcp_grant"] = grant_meta
        bridge_request_args["grant_meta"] = grant_meta
        bridge_request_args["grant"] = grant_meta

        grant_id = _safe_str(grant_meta.get("grant_id"))
        artifact_id = _safe_str(grant_meta.get("artifact_id"))
        resolution_source = _safe_str(grant_meta.get("resolution_source"))

        if grant_id:
            bridge_request_args["grant_id"] = grant_id
            bridge_request_args["mcp_binding"]["grant_id"] = grant_id
        if artifact_id:
            bridge_request_args["artifact_id"] = artifact_id
            bridge_request_args["mcp_binding"]["artifact_id"] = artifact_id
        if resolution_source:
            bridge_request_args["resolution_source"] = resolution_source
            bridge_request_args["mcp_binding"]["resolution_source"] = resolution_source

    packet = _dispatch_room_shared_provider_post(
        source_room_id=target_room_id,
        question=target_question,
        request_args=bridge_request_args,
        provider_meta=provider_meta,
    )

    packet = _normalize_room_shared_provider_result_packet(
        packet=packet,
        room_id=room_id,
        request_id=request_id,
        requested_mode=requested_mode,
        mcp_overrides=mcp_overrides,
        question=question,
        role=role,
        provider_meta=provider_meta,
    )

    return _append_execution_fact(
        packet=packet,
        provider_meta=provider_meta,
        provider_id=_safe_str(provider_meta.get("provider_id")),
        requested_mode=requested_mode,
        role=role,
        consumer_room_id=room_id,
        actor_user_id=actor_user_id,
    )

__all__ = [
    "_append_execution_fact",
    "_apply_mcp_binding_question_aliases",
    "_apply_question_aliases",
    "_build_imported_grant_state_deny_packet",
    "_dispatch_imported_remote_room_shared_provider",
    "_dispatch_room_shared_provider",
    "_federated_provider_error_packet",
    "_imported_grant_state_error",
    "_normalize_question",
    "_packet_has_terminal_deny",
    "_provider_error_packet",
    "_provider_meta_with_bridge_grant_meta",
    "_safe_list",
    "_safe_query_str",
]

