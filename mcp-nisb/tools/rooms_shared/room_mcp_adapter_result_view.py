from __future__ import annotations


from typing import Any, Dict


from .room_contracts import new_id, utc_iso
from .room_request_bridge import (
    _safe_dict,
    _safe_str,
)
from .room_store import append_room_event
from .room_tools_mcp_providers import (
    get_room_mcp_grant_by_id,
    parse_room_mcp_grant_artifact,
)
from .room_mcp_adapter_snapshot import (
    _collect_provider_request_context,
    _pick_first_str,
    _safe_list,
)



def _normalize_text(value: Any) -> str:
    return _safe_str(value).strip()



def _append_unique_text(target: list[str], seen: set[str], value: Any) -> None:
    text = _normalize_text(value)
    if not text or text in seen:
        return
    seen.add(text)
    target.append(text)



def _event_payload(event: Dict[str, Any]) -> Dict[str, Any]:
    return _safe_dict(_safe_dict(event).get("payload"))



def _extract_share_ref_from_request_args(
    request_args: Dict[str, Any],
    role: Dict[str, Any] | None = None,
) -> str:
    ctx = _collect_provider_request_context(
        request_args=request_args,
        role=role,
    )
    return _safe_str(ctx.get("share_ref"))

def _grant_matches_provider_identity(
    provider_meta: Dict[str, Any],
    grant_like: Dict[str, Any],
) -> bool:
    obj = _safe_dict(grant_like)
    if not obj:
        return False

    room_source = _safe_dict(provider_meta.get("room_source"))
    current_provider_id = _safe_str(provider_meta.get("provider_id"))
    current_source_room_id = _safe_str(
        provider_meta.get("source_room_id")
        or room_source.get("room_id")
    )

    candidate_provider_id = _safe_str(obj.get("provider_id"))
    candidate_source_room_id = _safe_str(
        obj.get("source_room_id")
        or _safe_dict(obj.get("room_source")).get("room_id")
    )

    if not candidate_provider_id and not candidate_source_room_id:
        return False

    if candidate_provider_id and current_provider_id and candidate_provider_id != current_provider_id:
        return False

    if (
        candidate_source_room_id
        and current_source_room_id
        and candidate_source_room_id != current_source_room_id
    ):
        return False

    return True


def _share_ref_matches_provider_identity(
    provider_meta: Dict[str, Any],
    share_ref: str,
) -> bool:
    ref = _safe_str(share_ref)
    if not ref:
        return False

    artifact = _safe_dict(parse_room_mcp_grant_artifact(ref))
    if not artifact:
        return True

    return _grant_matches_provider_identity(provider_meta, artifact)

def _extract_grant_locator_from_request_args(
    *,
    provider_meta: Dict[str, Any],
    request_args: Dict[str, Any],
    role: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    provider_origin = _safe_str(provider_meta.get("provider_origin")).lower()
    if not provider_origin.startswith("imported_remote"):
        return {}

    req = _safe_dict(request_args)
    role_obj = _safe_dict(role)

    mcp_binding = _safe_dict(req.get("mcp_binding"))
    role_mcp_binding = _safe_dict(role_obj.get("mcp_binding"))

    provider_snapshot = _safe_dict(
        req.get("mcp_provider_snapshot")
        or req.get("provider_snapshot")
        or mcp_binding.get("provider_snapshot")
        or role_obj.get("mcp_provider_snapshot")
        or role_mcp_binding.get("provider_snapshot")
    )
    imported_provider = _safe_dict(
        req.get("imported_provider")
        or mcp_binding.get("imported_provider")
        or role_obj.get("imported_provider")
        or role_mcp_binding.get("imported_provider")
    )

    room_source = _safe_dict(provider_meta.get("room_source"))
    embedded_grant = {}
    for candidate in (
        provider_meta.get("_grant_meta"),
        provider_meta.get("grant_meta"),
        provider_meta.get("grant"),
        req.get("_room_mcp_grant"),
        req.get("grant_meta"),
        req.get("grant"),
        mcp_binding.get("grant_meta"),
        mcp_binding.get("grant"),
        role_obj.get("grant_meta"),
        role_obj.get("grant"),
        role_mcp_binding.get("grant_meta"),
        role_mcp_binding.get("grant"),
        provider_snapshot.get("grant_meta"),
        provider_snapshot.get("grant"),
        imported_provider.get("grant_meta"),
        imported_provider.get("grant"),
    ):
        obj = _safe_dict(candidate)
        if obj:
            embedded_grant = obj
            break

    share_ref = _pick_first_str(
        req.get("mcp_share_ref"),
        req.get("share_ref"),
        mcp_binding.get("share_ref"),
        role_obj.get("share_ref"),
        role_mcp_binding.get("share_ref"),
        imported_provider.get("share_ref"),
        provider_snapshot.get("share_ref"),
        provider_meta.get("share_ref"),
        embedded_grant.get("descriptor_ref"),
    )

    artifact = _safe_dict(parse_room_mcp_grant_artifact(share_ref))

    source_room_id = _pick_first_str(
        embedded_grant.get("source_room_id"),
        artifact.get("source_room_id"),
        req.get("source_room_id"),
        req.get("_room_mcp_source_room_id"),
        mcp_binding.get("source_room_id"),
        provider_meta.get("source_room_id"),
        room_source.get("room_id"),
        imported_provider.get("source_room_id"),
        provider_snapshot.get("source_room_id"),
        _safe_dict(imported_provider.get("room_source")).get("room_id"),
        _safe_dict(provider_snapshot.get("room_source")).get("room_id"),
    )

    provider_id = _pick_first_str(
        embedded_grant.get("provider_id"),
        artifact.get("provider_id"),
        provider_meta.get("provider_id"),
        req.get("provider_id"),
        req.get("_room_mcp_provider_id"),
        mcp_binding.get("provider_id"),
        imported_provider.get("provider_id"),
        provider_snapshot.get("provider_id"),
    )

    grant_id = _pick_first_str(
        embedded_grant.get("grant_id"),
        artifact.get("grant_id"),
        req.get("grant_id"),
        mcp_binding.get("grant_id"),
        imported_provider.get("grant_id"),
        provider_snapshot.get("grant_id"),
    )

    artifact_id = _pick_first_str(
        embedded_grant.get("artifact_id"),
        artifact.get("artifact_id"),
        req.get("artifact_id"),
        mcp_binding.get("artifact_id"),
        imported_provider.get("artifact_id"),
        provider_snapshot.get("artifact_id"),
    )

    resolution_source = _pick_first_str(
        embedded_grant.get("resolution_source"),
        artifact.get("resolution_source"),
        req.get("resolution_source"),
        mcp_binding.get("resolution_source"),
        imported_provider.get("resolution_source"),
        provider_snapshot.get("resolution_source"),
        "grant_artifact" if share_ref else "",
    )

    grant_state = _pick_first_str(
        embedded_grant.get("grant_state"),
        req.get("grant_state"),
        mcp_binding.get("grant_state"),
        imported_provider.get("grant_state"),
        provider_snapshot.get("grant_state"),
    )

    grant_mode = _pick_first_str(
        embedded_grant.get("grant_mode"),
        artifact.get("grant_mode"),
        req.get("grant_mode"),
        mcp_binding.get("grant_mode"),
        imported_provider.get("grant_mode"),
        provider_snapshot.get("grant_mode"),
        "share_artifact",
    )

    discovery_mode = _pick_first_str(
        embedded_grant.get("discovery_mode"),
        artifact.get("discovery_mode"),
        req.get("discovery_mode"),
        mcp_binding.get("discovery_mode"),
        imported_provider.get("discovery_mode"),
        provider_snapshot.get("discovery_mode"),
        "granted_visible",
    )

    external_result_view = _pick_first_str(
        embedded_grant.get("external_result_view"),
        artifact.get("external_result_view"),
        _safe_dict(embedded_grant.get("scope")).get("result_view"),
        _safe_dict(artifact.get("scope")).get("result_view"),
        req.get("external_result_view"),
        req.get("result_view"),
        mcp_binding.get("external_result_view"),
        mcp_binding.get("result_view"),
        "final_result_only",
    )

    audience = _safe_dict(
        embedded_grant.get("audience")
        or artifact.get("audience")
    )
    scope = _safe_dict(
        embedded_grant.get("scope")
        or artifact.get("scope")
    )

    source_observation_allowed = bool(
        embedded_grant.get(
            "source_observation_allowed",
            artifact.get(
                "source_observation_allowed",
                scope.get("observe_source_room", False),
            ),
        )
    )

    return {
        **artifact,
        **embedded_grant,
        "descriptor_ref": share_ref,
        "share_ref": share_ref,
        "source_room_id": source_room_id,
        "provider_id": provider_id,
        "grant_id": grant_id,
        "artifact_id": artifact_id,
        "grant_state": grant_state,
        "grant_mode": grant_mode,
        "discovery_mode": discovery_mode,
        "resolution_source": resolution_source,
        "external_result_view": external_result_view or "final_result_only",
        "source_observation_allowed": source_observation_allowed,
        "scope": scope,
        "audience": audience,
    }

def _resolve_grant_meta(
    *,
    provider_meta: Dict[str, Any],
    request_args: Dict[str, Any],
    role: Dict[str, Any] | None = None,
) -> tuple[Dict[str, Any], str]:
    provider_origin = _safe_str(provider_meta.get("provider_origin")).lower()
    if not provider_origin.startswith("imported_remote"):
        return {}, ""

    locator = _extract_grant_locator_from_request_args(
        provider_meta=provider_meta,
        request_args=request_args,
        role=role,
    )

    share_ref = _safe_str(locator.get("share_ref") or locator.get("descriptor_ref"))
    room_source = _safe_dict(provider_meta.get("room_source"))

    source_room_id = _safe_str(
        locator.get("source_room_id")
        or room_source.get("room_id")
    )
    provider_id = _safe_str(
        locator.get("provider_id")
        or provider_meta.get("provider_id")
    )
    grant_id = _safe_str(locator.get("grant_id"))
    artifact_id = _safe_str(locator.get("artifact_id"))

    if not share_ref and not grant_id and not artifact_id:
        return {}, ""

    grant_meta = {
        **locator,
        "provider_id": provider_id,
        "source_room_id": source_room_id,
        "scope": _safe_dict(locator.get("scope")),
        "audience": _safe_dict(locator.get("audience")),
        "grant_mode": _safe_str(locator.get("grant_mode"), "share_artifact") or "share_artifact",
        "discovery_mode": _safe_str(locator.get("discovery_mode"), "granted_visible") or "granted_visible",
        "resolution_source": _safe_str(locator.get("resolution_source"), "grant_artifact") or "grant_artifact",
        "external_result_view": _safe_str(
            locator.get("external_result_view") or _safe_dict(locator.get("scope")).get("result_view"),
            "final_result_only",
        ) or "final_result_only",
        "source_observation_allowed": bool(
            locator.get(
                "source_observation_allowed",
                _safe_dict(locator.get("scope")).get("observe_source_room", False),
            )
        ),
        "_validated_local": False,
    }

    imported_state = _safe_str(locator.get("grant_state"))
    if imported_state == "revoked":
        return {**grant_meta, "grant_state": "revoked"}, "grant_revoked"
    if imported_state == "expired":
        return {**grant_meta, "grant_state": "expired"}, "grant_expired"
    if imported_state and imported_state not in {"active"}:
        return {**grant_meta, "grant_state": imported_state}, f"grant_{imported_state}"

    return grant_meta, ""


def _build_final_only_summary(response: str, message: str) -> str:
    text = _safe_str(response) or _safe_str(message)
    if len(text) <= 280:
        return text
    return f"{text[:277]}..."



def _collect_request_texts(packet: Dict[str, Any]) -> set[str]:
    src = _safe_dict(packet)
    seen: set[str] = set()
    texts: list[str] = []


    for candidate in (
        src.get("question"),
        src.get("request_question"),
        src.get("content_input"),
        src.get("input"),
        src.get("evidence_query"),
    ):
        _append_unique_text(texts, seen, candidate)


    for item in _safe_list(src.get("tool_results")):
        obj = _safe_dict(item)
        if _safe_str(obj.get("type")) != "room_event":
            continue
        payload = _event_payload(_safe_dict(obj.get("event")))
        _append_unique_text(texts, seen, payload.get("content"))
        _append_unique_text(texts, seen, payload.get("response"))


    return set(texts)



def _collect_response_candidates(packet: Dict[str, Any]) -> list[str]:
    src = _safe_dict(packet)
    seen: set[str] = set()
    candidates: list[str] = []


    for item in _safe_list(src.get("tool_results")):
        obj = _safe_dict(item)


        for field in (
            obj.get("final_response"),
            obj.get("response"),
            obj.get("content"),
        ):
            _append_unique_text(candidates, seen, field)


        event = _safe_dict(obj.get("event"))
        if event:
            payload = _event_payload(event)
            _append_unique_text(candidates, seen, payload.get("content"))
            _append_unique_text(candidates, seen, payload.get("response"))


        for nested_event in reversed(_safe_list(obj.get("events"))):
            payload = _event_payload(_safe_dict(nested_event))
            _append_unique_text(candidates, seen, payload.get("content"))
            _append_unique_text(candidates, seen, payload.get("response"))


    for field in (
        src.get("final_response"),
        src.get("response"),
        src.get("content"),
    ):
        _append_unique_text(candidates, seen, field)


    return candidates



def _resolve_final_response(packet: Dict[str, Any]) -> tuple[str, bool]:
    request_texts = _collect_request_texts(packet)
    response_candidates = _collect_response_candidates(packet)


    for candidate in response_candidates:
        if candidate not in request_texts:
            return candidate, False


    if response_candidates:
        return response_candidates[0], True


    return "", False



def _looks_like_meaningful_final_response(response: str) -> bool:
    text = _normalize_text(response)
    if not text:
        return False
    if len(text) >= 8:
        return True
    if any(ch in text for ch in ("，", "。", "：", "；", "\n", " ", "\t")):
        return True
    return False



def _should_flag_provider_echo(
    *,
    packet: Dict[str, Any],
    resolved_response: str,
    echoed_request: bool,
    provider_meta: Dict[str, Any],
    grant_meta: Dict[str, Any],
) -> bool:
    if not echoed_request:
        return False


    response_text = _normalize_text(resolved_response)
    if not response_text:
        return False


    provider_origin = _safe_str(provider_meta.get("provider_origin")).lower()
    result_view = _safe_str(
        grant_meta.get("external_result_view") or _safe_dict(grant_meta.get("scope")).get("result_view"),
        "final_result_only",
    ) or "final_result_only"


    if provider_origin.startswith("imported_remote") and result_view == "final_result_only":
        return False


    if _looks_like_meaningful_final_response(response_text):
        return False


    return True



def _extract_terminal_deny(packet: Dict[str, Any]) -> Dict[str, Any]:
    src = _safe_dict(packet)


    for item in _safe_list(src.get("tool_results")):
        obj = _safe_dict(item)
        item_type = _safe_str(obj.get("type")).lower()
        if item_type not in {
            "room_mcp_provider_deny",
            "room_provider_deny",
            "room_mcp_bridge_deny",
        }:
            continue


        deny_obj = _safe_dict(obj.get("deny"))
        bridge_obj = _safe_dict(obj.get("bridge_result"))


        reason_code = _pick_first_str(
            obj.get("reason_code"),
            deny_obj.get("reason_code"),
            bridge_obj.get("reason_code"),
            obj.get("deny_reason_code"),
            deny_obj.get("deny_reason_code"),
            bridge_obj.get("deny_reason_code"),
        )


        message = _pick_first_str(
            obj.get("message"),
            obj.get("summary"),
            obj.get("final_response"),
            obj.get("response"),
            obj.get("content"),
            deny_obj.get("message"),
            deny_obj.get("summary"),
            deny_obj.get("final_response"),
            deny_obj.get("response"),
            deny_obj.get("content"),
            bridge_obj.get("message"),
            bridge_obj.get("summary"),
            bridge_obj.get("final_response"),
            bridge_obj.get("response"),
            bridge_obj.get("content"),
            src.get("upstream_message"),
            src.get("upstream_response"),
        )


        final_response = _pick_first_str(
            obj.get("final_response"),
            obj.get("response"),
            obj.get("content"),
            deny_obj.get("final_response"),
            deny_obj.get("response"),
            deny_obj.get("content"),
            bridge_obj.get("final_response"),
            bridge_obj.get("response"),
            bridge_obj.get("content"),
            src.get("upstream_response"),
            src.get("upstream_message"),
            message,
        )


        status = _pick_first_str(
            obj.get("status"),
            deny_obj.get("status"),
            bridge_obj.get("status"),
            "error",
        ) or "error"


        return {
            "status": "error" if status in {"success", "ok"} else status,
            "message": message,
            "final_response": final_response,
            "reason_code": reason_code,
            "type": item_type,
        }


    upstream_message = _pick_first_str(
        src.get("upstream_message"),
        src.get("upstream_response"),
    )
    upstream_text = _safe_str(upstream_message).lower()
    if upstream_text and ("denied" in upstream_text or "blocked" in upstream_text):
        return {
            "status": "error",
            "message": upstream_message,
            "final_response": upstream_message,
            "reason_code": _pick_first_str(
                src.get("deny_reason_code"),
                src.get("reason_code"),
            ),
            "type": "upstream_deny",
        }


    return {}



def _apply_final_only_result_view(
    *,
    packet: Dict[str, Any],
    provider_meta: Dict[str, Any],
    grant_meta: Dict[str, Any],
) -> Dict[str, Any]:
    src = dict(_safe_dict(packet))
    status = _safe_str(src.get("status"), "success") or "success"
    message = _safe_str(src.get("message"), "provider result available")
    room_source = _safe_dict(provider_meta.get("room_source"))
    scope = _safe_dict(grant_meta.get("scope"))


    result_view = _safe_str(
        grant_meta.get("external_result_view") or scope.get("result_view"),
        "final_result_only",
    ) or "final_result_only"
    source_observation_allowed = bool(
        grant_meta.get("source_observation_allowed", scope.get("observe_source_room", False))
    )


    terminal_deny = _extract_terminal_deny(src)
    deny_reason_code = ""
    result_error = ""


    if terminal_deny:
        status = _safe_str(terminal_deny.get("status"), "error") or "error"
        message = _safe_str(terminal_deny.get("message")) or message
        resolved_response = _safe_str(terminal_deny.get("final_response")) or message
        echoed_request = False
        deny_reason_code = _safe_str(terminal_deny.get("reason_code"))
        result_error = "provider_denied"
    else:
        resolved_response, echoed_request = _resolve_final_response(src)


        if status in {"success", "ok"}:
            if not resolved_response:
                status = "error"
                result_error = "provider_empty_response"
                message = "room mcp provider returned empty final response"
            elif _should_flag_provider_echo(
                packet=src,
                resolved_response=resolved_response,
                echoed_request=echoed_request,
                provider_meta=provider_meta,
                grant_meta=grant_meta,
            ):
                status = "error"
                result_error = "provider_echo_response"
                message = "room mcp provider echoed request instead of final response"


    final_response = resolved_response or message


    provider_trace = {
        "provider_id": _safe_str(provider_meta.get("provider_id")),
        "provider_type": _safe_str(provider_meta.get("provider_type")),
        "provider_origin": _safe_str(provider_meta.get("provider_origin")),
        "source_room_id": _safe_str(grant_meta.get("source_room_id") or room_source.get("room_id")),
        "grant_id": _safe_str(grant_meta.get("grant_id")),
        "artifact_id": _safe_str(grant_meta.get("artifact_id")),
        "grant_state": _safe_str(grant_meta.get("grant_state"), "active") or "active",
        "grant_mode": _safe_str(grant_meta.get("grant_mode"), "share_artifact") or "share_artifact",
        "discovery_mode": _safe_str(grant_meta.get("discovery_mode"), "granted_visible") or "granted_visible",
        "resolution_source": _safe_str(grant_meta.get("resolution_source"), "grant_artifact") or "grant_artifact",
        "visibility_source": _safe_str(grant_meta.get("visibility_source"), "granted_visible") or "granted_visible",
        "result_view": result_view,
        "source_observation_allowed": source_observation_allowed,
    }


    final_item = {
        "type": "room_mcp_final_result_view",
        "status": status,
        "final_response": final_response,
        "summary": _build_final_only_summary(final_response, message),
        "message": message,
        "provider_trace": provider_trace,
        "provider_id": _safe_str(provider_meta.get("provider_id")),
        "source_room_id": _safe_str(provider_trace.get("source_room_id")),
        "grant_id": _safe_str(grant_meta.get("grant_id")),
        "artifact_id": _safe_str(grant_meta.get("artifact_id")),
        "grant_state": _safe_str(grant_meta.get("grant_state"), "active") or "active",
        "grant_mode": _safe_str(grant_meta.get("grant_mode"), "share_artifact") or "share_artifact",
        "discovery_mode": _safe_str(grant_meta.get("discovery_mode"), "granted_visible") or "granted_visible",
        "resolution_source": _safe_str(grant_meta.get("resolution_source"), "grant_artifact") or "grant_artifact",
        "result_view": result_view,
        "external_result_view": result_view,
        "source_observation_allowed": source_observation_allowed,
    }
    if result_error:
        final_item["error"] = result_error
    if deny_reason_code:
        final_item["deny_reason_code"] = deny_reason_code


    src["status"] = status
    src["response"] = final_response
    src["message"] = message
    if result_error:
        src["error"] = result_error
    else:
        src.pop("error", None)
    if deny_reason_code:
        src["deny_reason_code"] = deny_reason_code
    else:
        src.pop("deny_reason_code", None)


    src["tool_calls"] = []
    src["tool_results"] = [final_item]
    src["external_result_view"] = result_view
    src["source_observation_allowed"] = source_observation_allowed
    return src



def _record_grant_consumed_event(
    *,
    request_id: str,
    consumer_room_id: str,
    actor_user_id: str,
    provider_meta: Dict[str, Any],
    grant_meta: Dict[str, Any],
    packet_status: str = "",
) -> None:
    if not bool(grant_meta.get("_validated_local")):
        return


    normalized_status = _safe_str(packet_status, "success") or "success"
    if normalized_status not in {"success", "ok"}:
        return


    source_room_id = _safe_str(grant_meta.get("source_room_id"))
    if not source_room_id:
        return


    scope = _safe_dict(grant_meta.get("scope"))
    evt = {
        "id": new_id("evt"),
        "ts": utc_iso(),
        "type": "room.mcp_grant_consumed",
        "room_id": source_room_id,
        "request_id": request_id,
        "payload": {
            "sender": actor_user_id,
            "consumer_room_id": consumer_room_id,
            "provider_id": _safe_str(provider_meta.get("provider_id")),
            "grant_id": _safe_str(grant_meta.get("grant_id")),
            "artifact_id": _safe_str(grant_meta.get("artifact_id")),
            "grant_mode": _safe_str(grant_meta.get("grant_mode"), "share_artifact") or "share_artifact",
            "result_view": _safe_str(
                grant_meta.get("external_result_view") or scope.get("result_view"),
                "final_result_only",
            ) or "final_result_only",
            "response_status": normalized_status,
            "status": "consumed",
            "peer_id": _pick_first_str(
                grant_meta.get("peer_id"),
                _safe_dict(grant_meta.get("route_identity")).get("peer_id"),
            ),
            "remote_peer_id": _pick_first_str(
                grant_meta.get("remote_peer_id"),
                _safe_dict(grant_meta.get("route_identity")).get("remote_peer_id"),
            ),
            "remote_user_id": _pick_first_str(
                grant_meta.get("remote_user_id"),
                _safe_dict(grant_meta.get("route_identity")).get("remote_user_id"),
            ),
        },
    }
    try:
        append_room_event(source_room_id, evt)
    except Exception:
        return



__all__ = [
    "_apply_final_only_result_view",
    "_build_final_only_summary",
    "_extract_grant_locator_from_request_args",
    "_extract_share_ref_from_request_args",
    "_record_grant_consumed_event",
    "_resolve_grant_meta",
    "_should_flag_provider_echo",
]

