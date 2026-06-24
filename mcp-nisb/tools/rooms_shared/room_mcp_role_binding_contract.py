from __future__ import annotations

from typing import Any, Dict

from .room_mcp_share_artifact import (
    ROOM_MCP_SHARE_REF_VERSION,
    ROOM_SHARED_PROVIDER_ORIGIN_LOCAL,
    _normalize_boundary_hint,
    _normalize_provider_id,
    _normalize_room_source,
    _safe_bool,
    _safe_dict,
    _safe_list,
    _safe_str,
    parse_room_shared_mcp_share_ref,
)


_GRANT_META_KEYS = (
    "_room_mcp_grant",
    "grant_meta",
    "grantMeta",
    "grant",
    "share_ref_payload",
    "shareRefPayload",
    "artifact",
    "grant_artifact",
    "grantArtifact",
)

_SHARE_REF_KEYS = (
    "mcp_share_ref",
    "mcpShareRef",
    "share_ref",
    "shareRef",
    "descriptor_ref",
    "descriptorRef",
    "grant_ref",
    "grantRef",
    "room_mcp_grant_ref",
    "roomMcpGrantRef",
)

_GRANT_SCALAR_KEYS = (
    "grant_id",
    "grantId",
    "artifact_id",
    "artifactId",
    "provider_id",
    "providerId",
    "source_room_id",
    "sourceRoomId",
    "consumer_room_id",
    "consumerRoomId",
    "grant_state",
    "grantState",
    "grant_mode",
    "grantMode",
    "discovery_mode",
    "discoveryMode",
    "resolution_source",
    "resolutionSource",
    "external_result_view",
    "externalResultView",
    "result_view",
    "resultView",
    "source_observation_allowed",
    "sourceObservationAllowed",
    "remote_peer_id",
    "remotePeerId",
    "grant_peer_id",
    "grantPeerId",
    "grant_remote_user_id",
    "grantRemoteUserId",
    "peer_id",
    "peerId",
    "remote_user_id",
    "remoteUserId",
    "target_peer_id",
    "targetPeerId",
    "source_peer_id",
    "sourcePeerId",
    "federation_peer_id",
    "federationPeerId",
)


def _extract_role_mcp_input(role: Dict[str, Any]) -> Dict[str, Any]:
    candidates = [
        role.get("mcp"),
        role.get("mcp_binding"),
        role.get("provider_binding"),
    ]
    for item in candidates:
        row = _safe_dict(item)
        if row:
            return row
    return {}


def _first_tool_template(provider: Dict[str, Any]) -> Dict[str, Any]:
    tools = _safe_list(provider.get("tool_templates"))
    for item in tools:
        row = _safe_dict(item)
        if row:
            return row
    return {}


def _normalize_provider_params(value: Any, defaults: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(defaults or {})
    raw = _safe_dict(value)
    for key, val in raw.items():
        out[str(key)] = val
    return out


def _first_nonempty_str(*values: Any) -> str:
    for value in values:
        s = _safe_str(value)
        if s:
            return s
    return ""


def _first_safe_dict(*values: Any) -> Dict[str, Any]:
    for value in values:
        row = _safe_dict(value)
        if row:
            return row
    return {}


def _extract_share_ref_from_sources(*sources: Dict[str, Any]) -> str:
    for source in sources:
        row = _safe_dict(source)
        if not row:
            continue

        for key in _SHARE_REF_KEYS:
            value = _safe_str(row.get(key))
            if value:
                return value

        room_source = _safe_dict(row.get("room_source"))
        for key in _SHARE_REF_KEYS:
            value = _safe_str(room_source.get(key))
            if value:
                return value

        source_ref = _safe_dict(row.get("source_ref"))
        for key in _SHARE_REF_KEYS:
            value = _safe_str(source_ref.get(key))
            if value:
                return value

        for meta_key in _GRANT_META_KEYS:
            grant = _safe_dict(row.get(meta_key))
            for key in _SHARE_REF_KEYS:
                value = _safe_str(grant.get(key))
                if value:
                    return value

    return ""


def _extract_grant_meta_from_sources(*sources: Dict[str, Any]) -> Dict[str, Any]:
    for source in sources:
        row = _safe_dict(source)
        if not row:
            continue
        for key in _GRANT_META_KEYS:
            grant = _safe_dict(row.get(key))
            if grant:
                return dict(grant)
    return {}


def _parse_grant_ref_best_effort(share_ref: str) -> Dict[str, Any]:
    ref = _safe_str(share_ref)
    if not ref:
        return {}

    parsed = _safe_dict(parse_room_shared_mcp_share_ref(ref))
    if parsed:
        return parsed

    if ref.startswith("room-mcp-grant:"):
        try:
            from .room_tools_mcp_providers import parse_room_mcp_grant_artifact

            return _safe_dict(parse_room_mcp_grant_artifact(ref))
        except Exception:
            return {}

    return {}


def _canonical_grant_key(key: str) -> str:
    mapping = {
        "grantId": "grant_id",
        "artifactId": "artifact_id",
        "providerId": "provider_id",
        "sourceRoomId": "source_room_id",
        "consumerRoomId": "consumer_room_id",
        "grantState": "grant_state",
        "grantMode": "grant_mode",
        "discoveryMode": "discovery_mode",
        "resolutionSource": "resolution_source",
        "externalResultView": "external_result_view",
        "resultView": "result_view",
        "sourceObservationAllowed": "source_observation_allowed",
        "remotePeerId": "remote_peer_id",
        "grantPeerId": "grant_peer_id",
        "grantRemoteUserId": "grant_remote_user_id",
        "peerId": "peer_id",
        "remoteUserId": "remote_user_id",
        "targetPeerId": "target_peer_id",
        "sourcePeerId": "source_peer_id",
        "federationPeerId": "federation_peer_id",
    }
    return mapping.get(key, key)


def _merge_grant_locator(
    *,
    share_ref: str,
    role_obj: Dict[str, Any],
    raw: Dict[str, Any],
    provider: Dict[str, Any],
    provider_snapshot_input: Dict[str, Any],
    imported_provider_input: Dict[str, Any],
) -> Dict[str, Any]:
    sources = (
        raw,
        provider_snapshot_input,
        imported_provider_input,
        provider,
        role_obj,
        _safe_dict(provider.get("room_source")),
        _safe_dict(provider.get("source_ref")),
        _safe_dict(provider_snapshot_input.get("room_source")),
        _safe_dict(imported_provider_input.get("room_source")),
    )

    merged: Dict[str, Any] = {}

    parsed = _parse_grant_ref_best_effort(share_ref)
    if parsed:
        merged.update(parsed)

    grant_meta = _extract_grant_meta_from_sources(*sources)
    if grant_meta:
        merged.update(grant_meta)

    for source in sources:
        row = _safe_dict(source)
        if not row:
            continue

        for raw_key in _GRANT_SCALAR_KEYS:
            key = _canonical_grant_key(raw_key)
            if key in merged and merged.get(key) not in (None, "", {}, []):
                continue
            value = row.get(raw_key)
            if value not in (None, "", {}, []):
                merged[key] = value

        for meta_key in _GRANT_META_KEYS:
            grant = _safe_dict(row.get(meta_key))
            if not grant:
                continue
            for raw_key in _GRANT_SCALAR_KEYS:
                key = _canonical_grant_key(raw_key)
                if key in merged and merged.get(key) not in (None, "", {}, []):
                    continue
                value = grant.get(raw_key)
                if value not in (None, "", {}, []):
                    merged[key] = value

            if "audience" not in merged and isinstance(grant.get("audience"), dict):
                merged["audience"] = _safe_dict(grant.get("audience"))
            if "scope" not in merged and isinstance(grant.get("scope"), dict):
                merged["scope"] = _safe_dict(grant.get("scope"))
            if "route_identity" not in merged and isinstance(grant.get("route_identity"), dict):
                merged["route_identity"] = _safe_dict(grant.get("route_identity"))

        if "audience" not in merged and isinstance(row.get("audience"), dict):
            merged["audience"] = _safe_dict(row.get("audience"))
        if "scope" not in merged and isinstance(row.get("scope"), dict):
            merged["scope"] = _safe_dict(row.get("scope"))
        if "route_identity" not in merged and isinstance(row.get("route_identity"), dict):
            merged["route_identity"] = _safe_dict(row.get("route_identity"))

    if share_ref:
        merged.setdefault("share_ref", share_ref)
        merged.setdefault("mcp_share_ref", share_ref)
        merged.setdefault("descriptor_ref", share_ref)

    provider_id = _normalize_provider_id(
        merged.get("provider_id")
        or provider.get("provider_id")
        or raw.get("provider_id")
        or provider_snapshot_input.get("provider_id")
        or imported_provider_input.get("provider_id")
    )
    if provider_id:
        merged["provider_id"] = provider_id

    room_source = _safe_dict(
        provider.get("room_source")
        or provider_snapshot_input.get("room_source")
        or imported_provider_input.get("room_source")
    )
    source_room_id = _safe_str(
        merged.get("source_room_id")
        or room_source.get("room_id")
        or provider.get("source_room_id")
        or provider_snapshot_input.get("source_room_id")
        or imported_provider_input.get("source_room_id")
    )
    if source_room_id:
        merged["source_room_id"] = source_room_id

    has_locator = bool(
        _safe_str(merged.get("grant_id"))
        or _safe_str(merged.get("artifact_id"))
        or _safe_str(merged.get("share_ref"))
        or _safe_str(merged.get("descriptor_ref"))
        or _safe_str(merged.get("mcp_share_ref"))
    )

    return merged if has_locator else {}


def _apply_grant_locator_to_payload(payload: Dict[str, Any], locator: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(_safe_dict(payload))
    grant = dict(_safe_dict(locator))
    if not grant:
        return out

    share_ref = _safe_str(
        grant.get("share_ref")
        or grant.get("mcp_share_ref")
        or grant.get("descriptor_ref")
    )
    if share_ref:
        out["share_ref"] = share_ref
        out["mcp_share_ref"] = share_ref
        out["descriptor_ref"] = share_ref

    for key in (
        "grant_id",
        "artifact_id",
        "provider_id",
        "source_room_id",
        "consumer_room_id",
        "grant_state",
        "grant_mode",
        "discovery_mode",
        "resolution_source",
        "external_result_view",
        "result_view",
        "remote_peer_id",
        "grant_peer_id",
        "grant_remote_user_id",
        "peer_id",
        "remote_user_id",
        "target_peer_id",
        "source_peer_id",
        "federation_peer_id",
    ):
        value = grant.get(key)
        if value not in (None, "", {}, []):
            out[key] = value

    if "source_observation_allowed" in grant:
        out["source_observation_allowed"] = bool(grant.get("source_observation_allowed"))

    out["_room_mcp_grant"] = dict(grant)
    out["grant_meta"] = dict(grant)
    out["grant"] = dict(grant)

    room_source = dict(_safe_dict(out.get("room_source")))
    if room_source:
        if share_ref:
            room_source["share_ref"] = share_ref
            room_source["descriptor_ref"] = share_ref
        if _safe_str(grant.get("source_room_id")) and not _safe_str(room_source.get("room_id")):
            room_source["room_id"] = _safe_str(grant.get("source_room_id"))
        out["room_source"] = room_source

    return out


def _resolve_binding_tool_name(
    raw: Dict[str, Any],
    provider: Dict[str, Any],
    provider_snapshot_input: Dict[str, Any],
) -> str:
    tool_template = _first_tool_template(provider)
    return _safe_str(
        raw.get("tool_name")
        or raw.get("toolName")
        or provider_snapshot_input.get("tool_name")
        or provider.get("tool_name")
        or tool_template.get("tool_name"),
        "search",
    )


def _resolve_binding_server_tool(
    raw: Dict[str, Any],
    provider: Dict[str, Any],
    provider_snapshot_input: Dict[str, Any],
) -> str:
    return _safe_str(
        raw.get("server_tool")
        or raw.get("serverTool")
        or provider_snapshot_input.get("server_tool")
        or provider.get("server_tool"),
        "nisb_room_mcp_provider_call",
    )


def _resolve_requested_mode(
    raw: Dict[str, Any],
    provider: Dict[str, Any],
    provider_snapshot_input: Dict[str, Any],
) -> str:
    return _safe_str(
        raw.get("requested_mode")
        or raw.get("requestedMode")
        or provider_snapshot_input.get("requested_mode")
        or provider.get("requested_mode"),
        "mcp",
    )


def _build_role_provider_snapshot(
    provider: Dict[str, Any],
    *,
    server_tool: str,
    tool_name: str,
    requested_mode: str,
    params: Dict[str, Any],
    inherit_workspace_context: bool,
    inherit_focus_root: bool,
    share_ref: str,
    grant_locator: Dict[str, Any],
) -> Dict[str, Any]:
    provider_obj = _safe_dict(provider)
    if not provider_obj:
        return {}

    tool_template = _first_tool_template(provider_obj)
    provider_type = _safe_str(provider_obj.get("provider_type"), "preset")
    snapshot = {
        "provider_id": _normalize_provider_id(provider_obj.get("provider_id")),
        "provider_type": provider_type,
        "provider_kind": _safe_str(provider_obj.get("provider_kind"), provider_type),
        "provider_origin": _safe_str(
            provider_obj.get("provider_origin"),
            ROOM_SHARED_PROVIDER_ORIGIN_LOCAL,
        ),
        "provider_label": _safe_str(provider_obj.get("label")),
        "label": _safe_str(provider_obj.get("label")),
        "description": _safe_str(provider_obj.get("description")),
        "descriptor_version": _safe_str(
            provider_obj.get("descriptor_version"),
            ROOM_MCP_SHARE_REF_VERSION,
        ),
        "server_tool": server_tool,
        "tool_name": tool_name or _safe_str(tool_template.get("tool_name")),
        "requested_mode": requested_mode,
        "invoke_contract": {
            "server_tool": server_tool,
            "tool_name": tool_name or _safe_str(tool_template.get("tool_name")),
            "requested_mode": requested_mode,
        },
        "params": dict(params or {}),
        "params_schema": _safe_dict(provider_obj.get("params_schema")),
        "params_defaults": _safe_dict(provider_obj.get("params_defaults")),
        "inherit_workspace_context": bool(inherit_workspace_context),
        "inherit_focus_root": bool(inherit_focus_root),
        "room_source": _normalize_room_source(provider_obj.get("room_source")),
        "boundary_hint": _normalize_boundary_hint(provider_obj.get("boundary_hint")),
        "availability": _safe_dict(provider_obj.get("availability")),
        "auth_state": _safe_dict(provider_obj.get("auth_state")),
        "share_ref": _safe_str(share_ref or provider_obj.get("share_ref")),
    }

    return _apply_grant_locator_to_payload(snapshot, grant_locator)


def normalize_room_role_mcp_contract(role: Dict[str, Any], tool_policy: Dict[str, Any]) -> Dict[str, Any]:
    from .room_mcp_provider_registry import resolve_room_mcp_provider

    role_obj = _safe_dict(role)
    policy = _safe_dict(tool_policy)
    raw = _extract_role_mcp_input(role_obj)

    enabled = _safe_bool(policy.get("mcp"), False)

    provider_snapshot_input = _safe_dict(
        raw.get("provider_snapshot")
        or raw.get("providerSnapshot")
        or raw.get("mcp_provider_snapshot")
        or role_obj.get("mcp_provider_snapshot")
        or role_obj.get("provider_snapshot")
    )
    imported_provider_input = _safe_dict(
        raw.get("imported_provider")
        or raw.get("importedProvider")
        or role_obj.get("imported_provider")
    )

    share_ref_input = _extract_share_ref_from_sources(
        raw,
        provider_snapshot_input,
        imported_provider_input,
        role_obj,
    )

    hinted_share_ref = parse_room_shared_mcp_share_ref(share_ref_input)

    provider_id = _normalize_provider_id(
        raw.get("provider_id")
        or raw.get("providerId")
        or raw.get("id")
        or provider_snapshot_input.get("provider_id")
        or imported_provider_input.get("provider_id")
        or hinted_share_ref.get("provider_id")
        or (
            "serper"
            if enabled and _safe_bool((role_obj.get("mcp_overrides") or {}).get("serperEnabled"), False)
            else ""
        )
    )

    provider = resolve_room_mcp_provider(
        provider_id=provider_id,
        share_ref=share_ref_input,
        provider_snapshot=provider_snapshot_input,
        imported_provider=imported_provider_input,
        raw=raw,
    )

    share_ref = _extract_share_ref_from_sources(
        raw,
        provider_snapshot_input,
        imported_provider_input,
        provider,
        role_obj,
    )

    grant_locator = _merge_grant_locator(
        share_ref=share_ref,
        role_obj=role_obj,
        raw=raw,
        provider=provider,
        provider_snapshot_input=provider_snapshot_input,
        imported_provider_input=imported_provider_input,
    )

    if not share_ref:
        share_ref = _safe_str(
            grant_locator.get("share_ref")
            or grant_locator.get("mcp_share_ref")
            or grant_locator.get("descriptor_ref")
        )

    params_defaults = _safe_dict(
        provider.get("params_defaults") or provider.get("default_params")
    )
    params = _normalize_provider_params(raw.get("params"), params_defaults)

    tool_name = _resolve_binding_tool_name(raw, provider, provider_snapshot_input)
    server_tool = _resolve_binding_server_tool(raw, provider, provider_snapshot_input)
    requested_mode = _resolve_requested_mode(raw, provider, provider_snapshot_input)

    boundary_hint = _safe_dict(provider.get("boundary_hint"))
    inherit_workspace_context = (
        _safe_bool(raw.get("inherit_workspace_context"), False)
        if "inherit_workspace_context" in raw
        else _safe_bool(boundary_hint.get("default_inherit_workspace_context"), False)
    )
    inherit_focus_root = (
        _safe_bool(raw.get("inherit_focus_root"), False)
        if "inherit_focus_root" in raw
        else _safe_bool(boundary_hint.get("default_inherit_focus_root"), False)
    )

    availability = _safe_dict(provider.get("availability"))
    provider_available = _safe_bool(availability.get("available"), bool(provider))

    resolved_provider_id = _normalize_provider_id(provider.get("provider_id") or provider_id)
    resolved_provider_type = _safe_str(provider.get("provider_type"), "preset")
    resolved_provider_kind = _safe_str(provider.get("provider_kind"), resolved_provider_type)
    provider_origin = _safe_str(
        provider.get("provider_origin"),
        ROOM_SHARED_PROVIDER_ORIGIN_LOCAL if resolved_provider_type == "preset" else "",
    )

    binding_enabled = enabled and bool(resolved_provider_id and provider and provider_available)

    binding = {
        "enabled": binding_enabled,
        "provider_id": resolved_provider_id,
        "provider_type": resolved_provider_type,
        "provider_kind": resolved_provider_kind,
        "provider_origin": provider_origin,
        "server_tool": server_tool,
        "tool_name": tool_name,
        "requested_mode": requested_mode,
        "invoke_contract": {
            "server_tool": server_tool,
            "tool_name": tool_name,
            "requested_mode": requested_mode,
        },
        "params": params,
        "inherit_workspace_context": inherit_workspace_context,
        "inherit_focus_root": inherit_focus_root,
    }

    binding = _apply_grant_locator_to_payload(binding, grant_locator)

    provider_ids = []
    if resolved_provider_id:
        provider_ids.append(resolved_provider_id)

    for item in _safe_list(raw.get("provider_ids") or raw.get("providerIds")):
        pid = _normalize_provider_id(item)
        if pid and pid not in provider_ids:
            provider_ids.append(pid)

    snapshot = _build_role_provider_snapshot(
        provider,
        server_tool=server_tool,
        tool_name=tool_name,
        requested_mode=requested_mode,
        params=params,
        inherit_workspace_context=inherit_workspace_context,
        inherit_focus_root=inherit_focus_root,
        share_ref=share_ref,
        grant_locator=grant_locator,
    )

    imported_provider = _first_safe_dict(
        imported_provider_input,
        provider.get("imported_provider"),
        snapshot.get("imported_provider"),
    )
    if imported_provider:
        imported_provider = _apply_grant_locator_to_payload(imported_provider, grant_locator)
        binding["imported_provider"] = imported_provider

    if snapshot:
        binding["provider_snapshot"] = snapshot

    if share_ref:
        binding["share_ref"] = share_ref
        binding["mcp_share_ref"] = share_ref
        binding["descriptor_ref"] = share_ref

    mcp_share_ref = _safe_str(
        share_ref
        or snapshot.get("share_ref")
        or binding.get("share_ref")
        or binding.get("descriptor_ref")
    )

    return {
        "mcp_binding": binding,
        "mcp_provider_ids": provider_ids,
        "mcp_provider_snapshot": snapshot,
        "mcp_share_ref": mcp_share_ref,
    }


__all__ = [
    "normalize_room_role_mcp_contract",
]
