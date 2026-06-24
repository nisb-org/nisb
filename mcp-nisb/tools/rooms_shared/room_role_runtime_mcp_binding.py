from __future__ import annotations

from typing import Any, Dict, List

from .room_mcp_provider_contract import normalize_room_role_mcp_contract
from .room_role_runtime_common import (
    _first_non_empty_str,
    _safe_bool,
    _safe_dict,
    _safe_list,
    _safe_str,
)
from .room_role_runtime_policy import (
    _extract_role_knowledge_binding,
    _extract_role_tool_policy,
)
from .room_store import load_meta


def _merge_role_mcp_binding(
    *,
    normalized_binding: Dict[str, Any],
    existing_binding: Dict[str, Any],
    request_args: Dict[str, Any],
    contract_snapshot: Dict[str, Any],
    contract_share_ref: str,
) -> Dict[str, Any]:
    normalized = _safe_dict(normalized_binding)
    existing = _safe_dict(existing_binding)
    req = _safe_dict(request_args)
    contract_provider_snapshot = _safe_dict(contract_snapshot)

    provider_snapshot = _safe_dict(
        normalized.get("provider_snapshot")
        or contract_provider_snapshot
        or existing.get("provider_snapshot")
        or req.get("mcp_provider_snapshot")
        or req.get("provider_snapshot")
    )

    imported_provider = _safe_dict(
        normalized.get("imported_provider")
        or existing.get("imported_provider")
        or req.get("imported_provider")
    )

    share_ref = _safe_str(
        normalized.get("share_ref")
        or contract_share_ref
        or existing.get("share_ref")
        or req.get("mcp_share_ref")
        or req.get("share_ref")
        or req.get("_outer_room_mcp_share_ref")
    )

    merged = dict(existing)
    merged.update(normalized)

    if provider_snapshot:
        merged["provider_snapshot"] = dict(provider_snapshot)
    if imported_provider:
        merged["imported_provider"] = dict(imported_provider)
    if share_ref:
        merged["share_ref"] = share_ref

    for key in (
        "provider_id",
        "provider_type",
        "provider_origin",
        "provider_label",
        "source_room_id",
        "grant_id",
        "artifact_id",
        "remote_peer_id",
        "grant_peer_id",
        "grant_remote_user_id",
        "consumer_room_id",
        "peer_id",
        "remote_user_id",
        "target_peer_id",
        "source_peer_id",
        "federation_peer_id",
    ):
        value = (
            merged.get(key)
            or existing.get(key)
            or req.get(key)
            or provider_snapshot.get(key)
            or imported_provider.get(key)
        )
        if value not in (None, "", {}, []):
            merged[key] = value

    room_source = _safe_dict(
        merged.get("room_source")
        or provider_snapshot.get("room_source")
        or imported_provider.get("room_source")
    )
    if room_source:
        merged["room_source"] = dict(room_source)

    boundary_hint = _safe_dict(
        merged.get("boundary_hint")
        or provider_snapshot.get("boundary_hint")
        or imported_provider.get("boundary_hint")
    )
    if boundary_hint:
        merged["boundary_hint"] = dict(boundary_hint)

    availability = _safe_dict(
        merged.get("availability")
        or provider_snapshot.get("availability")
        or imported_provider.get("availability")
    )
    if availability:
        merged["availability"] = dict(availability)

    auth_state = _safe_dict(
        merged.get("auth_state")
        or provider_snapshot.get("auth_state")
        or imported_provider.get("auth_state")
    )
    if auth_state:
        merged["auth_state"] = dict(auth_state)

    if not _safe_str(merged.get("provider_origin")):
        merged["provider_origin"] = _safe_str(
            req.get("_outer_room_mcp_provider_origin")
            or provider_snapshot.get("provider_origin")
            or imported_provider.get("provider_origin")
        )

    return merged


def _apply_mcp_contract_to_request_args(
    *,
    local_request_args: Dict[str, Any],
    mcp_binding: Dict[str, Any],
    mcp_provider_ids: List[Any],
    mcp_provider_snapshot: Dict[str, Any],
    mcp_share_ref: str,
) -> Dict[str, Any]:
    out = dict(local_request_args or {})
    binding = _safe_dict(mcp_binding)
    provider_snapshot = _safe_dict(
        mcp_provider_snapshot
        or binding.get("provider_snapshot")
    )
    imported_provider = _safe_dict(binding.get("imported_provider"))
    share_ref = _safe_str(mcp_share_ref or binding.get("share_ref"))

    out["mcp_binding"] = binding
    out["mcp_provider_ids"] = _safe_list(mcp_provider_ids)

    if provider_snapshot:
        out["mcp_provider_snapshot"] = dict(provider_snapshot)
        out["provider_snapshot"] = dict(provider_snapshot)

    if imported_provider:
        out["imported_provider"] = dict(imported_provider)

    if share_ref:
        out["mcp_share_ref"] = share_ref
        out["share_ref"] = share_ref

    for key in (
        "provider_origin",
        "source_room_id",
        "grant_id",
        "artifact_id",
        "remote_peer_id",
        "grant_peer_id",
        "grant_remote_user_id",
        "consumer_room_id",
        "peer_id",
        "remote_user_id",
        "target_peer_id",
        "source_peer_id",
        "federation_peer_id",
    ):
        value = _safe_str(binding.get(key))
        if value:
            out[key] = value

    return out


def _room_id_from_room_provider_id(provider_id: Any) -> str:
    s = _safe_str(provider_id)
    prefix = "room_provider__"
    if s.startswith(prefix):
        return _safe_str(s[len(prefix):])
    return ""


def _is_room_provider_id(provider_id: Any) -> bool:
    return _safe_str(provider_id).startswith("room_provider__")


def _room_provider_source_exists_locally(source_room_id: Any) -> bool:
    room_id = _safe_str(source_room_id)
    if not room_id:
        return False
    try:
        meta = _safe_dict(load_meta(room_id))
        return bool(meta)
    except Exception:
        return False


def _normalize_room_provider_origin(
    *,
    provider_id: str,
    raw_origin: str,
    share_ref: str,
    imported_provider: Dict[str, Any],
    provider_snapshot: Dict[str, Any],
    source_room_id: str = "",
) -> str:
    origin = _safe_str(raw_origin).lower()
    local_source_exists = _room_provider_source_exists_locally(source_room_id)

    imported_origin = _safe_str(
        imported_provider.get("provider_origin")
        or _safe_dict(imported_provider.get("source_ref")).get("origin")
    ).lower()

    snapshot_origin = _safe_str(
        provider_snapshot.get("provider_origin")
        or _safe_dict(provider_snapshot.get("source_ref")).get("origin")
    ).lower()

    if local_source_exists:
        if _is_room_provider_id(provider_id):
            return "local_room_shared"
        if origin in {"local_room_shared", "local_registry", "registry_local", "local_provider", "local"}:
            return "local_room_shared"

    if imported_origin == "imported_remote":
        return "imported_remote"

    if snapshot_origin == "imported_remote":
        return "imported_remote"

    if origin == "imported_remote":
        return "imported_remote"

    if imported_provider and share_ref:
        return "imported_remote"

    if share_ref and not local_source_exists:
        return "imported_remote"

    if _is_room_provider_id(provider_id):
        if origin in {"", "local", "local_registry", "registry_local", "local_provider"}:
            return "local_room_shared" if local_source_exists else "imported_remote"
        return origin or ("local_room_shared" if local_source_exists else "imported_remote")

    return origin


def _extract_room_mcp_binding_fact(request_args: Dict[str, Any]) -> Dict[str, Any]:
    req = _safe_dict(request_args)
    binding = _safe_dict(req.get("mcp_binding"))

    provider_snapshot = _safe_dict(
        req.get("mcp_provider_snapshot")
        or req.get("provider_snapshot")
        or binding.get("provider_snapshot")
    )

    imported_provider = _safe_dict(
        req.get("imported_provider")
        or binding.get("imported_provider")
    )

    room_source = _safe_dict(
        binding.get("room_source")
        or provider_snapshot.get("room_source")
        or imported_provider.get("room_source")
    )

    source_ref = _safe_dict(
        binding.get("source_ref")
        or provider_snapshot.get("source_ref")
        or imported_provider.get("source_ref")
    )

    invoke_contract = _safe_dict(
        binding.get("invoke_contract")
        or provider_snapshot.get("invoke_contract")
        or imported_provider.get("invoke_contract")
    )

    provider_ids = _safe_list(req.get("mcp_provider_ids"))
    first_provider_id = ""
    for item in provider_ids:
        item_id = _safe_str(item)
        if item_id:
            first_provider_id = item_id
            break

    provider_id = _first_non_empty_str(
        binding.get("provider_id"),
        req.get("provider_id"),
        provider_snapshot.get("provider_id"),
        imported_provider.get("provider_id"),
        first_provider_id,
    )

    source_room_id = _first_non_empty_str(
        binding.get("source_room_id"),
        req.get("source_room_id"),
        room_source.get("room_id"),
        provider_snapshot.get("source_room_id"),
        imported_provider.get("source_room_id"),
        _room_id_from_room_provider_id(provider_id),
    )

    share_ref = _first_non_empty_str(
        binding.get("share_ref"),
        req.get("mcp_share_ref"),
        req.get("share_ref"),
        provider_snapshot.get("share_ref"),
        imported_provider.get("share_ref"),
    )

    raw_provider_type = _first_non_empty_str(
        binding.get("provider_type"),
        binding.get("provider_kind"),
        req.get("provider_type"),
        req.get("provider_kind"),
        provider_snapshot.get("provider_type"),
        provider_snapshot.get("provider_kind"),
        imported_provider.get("provider_type"),
        imported_provider.get("provider_kind"),
    )

    raw_provider_origin = _first_non_empty_str(
        binding.get("provider_origin"),
        req.get("provider_origin"),
        provider_snapshot.get("provider_origin"),
        imported_provider.get("provider_origin"),
        source_ref.get("origin"),
    )

    server_tool = _first_non_empty_str(
        binding.get("server_tool"),
        invoke_contract.get("server_tool"),
        provider_snapshot.get("server_tool"),
        imported_provider.get("server_tool"),
    )

    tool_name = _first_non_empty_str(
        binding.get("tool_name"),
        invoke_contract.get("tool_name"),
        provider_snapshot.get("tool_name"),
        imported_provider.get("tool_name"),
    )

    is_room_provider = (
        _is_room_provider_id(provider_id)
        or _safe_str(raw_provider_type).lower() in {"room_shared_capability", "room_provider", "room_mcp_provider"}
        or _safe_str(raw_provider_origin).lower() in {"local_room_shared", "imported_remote"}
        or _safe_str(server_tool).lower() == "nisb_room_mcp_provider_call"
        or _safe_str(tool_name).lower() == "ask_room_shared_reply"
        or bool(source_room_id and share_ref)
    )

    if not is_room_provider:
        return {}

    provider_type = "room_shared_capability" if _is_room_provider_id(provider_id) else (
        _safe_str(raw_provider_type) or "room_shared_capability"
    )

    provider_origin = _normalize_room_provider_origin(
        provider_id=provider_id,
        raw_origin=raw_provider_origin,
        share_ref=share_ref,
        imported_provider=imported_provider,
        provider_snapshot=provider_snapshot,
        source_room_id=source_room_id,
    )

    if not room_source and source_room_id:
        room_source = {"room_id": source_room_id}
    elif room_source and source_room_id and not _safe_str(room_source.get("room_id")):
        room_source = dict(room_source)
        room_source["room_id"] = source_room_id

    out = {
        "provider_id": provider_id,
        "provider_type": provider_type,
        "provider_origin": provider_origin,
        "server_tool": server_tool or "nisb_room_mcp_provider_call",
        "tool_name": tool_name or "ask_room_shared_reply",
        "source_room_id": source_room_id,
        "share_ref": share_ref,
        "room_source": dict(room_source) if room_source else {},
    }

    if binding:
        out["mcp_binding"] = dict(binding)
    if provider_snapshot:
        out["provider_snapshot"] = dict(provider_snapshot)
    if imported_provider:
        out["imported_provider"] = dict(imported_provider)

    return out


def _extract_explicit_role_mcp_provider_id(
    role: Dict[str, Any],
    tool_policy: Dict[str, Any],
) -> str:
    role_obj = _safe_dict(role)
    policy = _safe_dict(tool_policy)

    direct_binding = _safe_dict(
        role_obj.get("mcp_binding")
        or role_obj.get("provider_binding")
        or role_obj.get("room_mcp_binding")
    )

    direct_snapshot = _safe_dict(
        role_obj.get("mcp_provider_snapshot")
        or role_obj.get("provider_snapshot")
        or direct_binding.get("provider_snapshot")
    )

    direct_imported = _safe_dict(
        role_obj.get("imported_provider")
        or direct_binding.get("imported_provider")
    )

    provider_ids = _safe_list(
        role_obj.get("mcp_provider_ids")
        or role_obj.get("provider_ids")
    )

    first_provider_id = ""
    for item in provider_ids:
        item_id = _safe_str(item)
        if item_id:
            first_provider_id = item_id
            break

    provider_id = _first_non_empty_str(
        direct_binding.get("provider_id"),
        role_obj.get("provider_id"),
        direct_snapshot.get("provider_id"),
        direct_imported.get("provider_id"),
        first_provider_id,
    )

    if provider_id:
        return provider_id

    try:
        contract = _safe_dict(normalize_room_role_mcp_contract(role_obj, policy))
    except Exception:
        contract = {}

    contract_binding = _safe_dict(contract.get("mcp_binding"))
    contract_snapshot = _safe_dict(contract.get("mcp_provider_snapshot"))
    contract_ids = _safe_list(contract.get("mcp_provider_ids"))

    contract_first_provider_id = ""
    for item in contract_ids:
        item_id = _safe_str(item)
        if item_id:
            contract_first_provider_id = item_id
            break

    return _first_non_empty_str(
        contract_binding.get("provider_id"),
        contract_snapshot.get("provider_id"),
        contract_first_provider_id,
    )


def _should_dispatch_role_room_mcp_provider(
    *,
    role: Dict[str, Any],
    request_args: Dict[str, Any],
    binding_fact: Dict[str, Any],
) -> bool:
    role_obj = _safe_dict(role)
    fact = _safe_dict(binding_fact)
    req = _safe_dict(request_args)

    if not fact:
        return False

    provider_id = _safe_str(
        fact.get("provider_id")
        or _safe_dict(fact.get("mcp_binding")).get("provider_id")
        or _safe_dict(fact.get("provider_snapshot")).get("provider_id")
        or _safe_dict(fact.get("imported_provider")).get("provider_id")
    )

    if not provider_id:
        return False

    role_tool_policy = _extract_role_tool_policy(role_obj)
    explicit_role_provider_id = _extract_explicit_role_mcp_provider_id(
        role_obj,
        role_tool_policy,
    )

    role_mcp_enabled = _safe_bool(role_tool_policy.get("mcp"), False)
    role_explicitly_bound_to_provider = bool(explicit_role_provider_id)

    if explicit_role_provider_id and explicit_role_provider_id != provider_id:
        return False

    if role_mcp_enabled or role_explicitly_bound_to_provider:
        return True

    req_policy = _safe_dict(req.get("role_tool_policy") or req.get("tool_policy"))
    rag_enabled = _safe_bool(req_policy.get("rag"), False) or _safe_bool(role_tool_policy.get("rag"), False)
    knowledge_binding = _safe_dict(
        req.get("role_binding")
        or req.get("knowledge_binding")
        or req.get("binding")
        or _extract_role_knowledge_binding(role_obj)
    )
    has_knowledge_scope = bool(
        _safe_str(knowledge_binding.get("library_id"))
        or _safe_str(knowledge_binding.get("doc_id"))
        or _safe_str(knowledge_binding.get("group_id"))
    )

    if rag_enabled or has_knowledge_scope:
        return False

    return False


def _apply_room_mcp_binding_fact_to_request_args(
    *,
    request_args: Dict[str, Any],
    binding_fact: Dict[str, Any],
) -> Dict[str, Any]:
    out = dict(request_args or {})
    fact = _safe_dict(binding_fact)
    binding = dict(_safe_dict(out.get("mcp_binding")))

    provider_id = _safe_str(fact.get("provider_id"))
    provider_type = _safe_str(fact.get("provider_type"), "room_shared_capability")
    provider_origin = _safe_str(fact.get("provider_origin"))
    source_room_id = _safe_str(fact.get("source_room_id")) or _room_id_from_room_provider_id(provider_id)
    share_ref = _safe_str(fact.get("share_ref"))
    server_tool = _safe_str(fact.get("server_tool"), "nisb_room_mcp_provider_call")
    tool_name = _safe_str(fact.get("tool_name"), "ask_room_shared_reply")
    room_source = _safe_dict(fact.get("room_source"))

    if source_room_id and not room_source:
        room_source = {"room_id": source_room_id}

    if provider_id:
        binding["provider_id"] = provider_id
        out["provider_id"] = provider_id

    binding["provider_type"] = provider_type
    binding["provider_kind"] = provider_type
    out["provider_type"] = provider_type
    out["provider_kind"] = provider_type

    if provider_origin:
        binding["provider_origin"] = provider_origin
        out["provider_origin"] = provider_origin

    if source_room_id:
        binding["source_room_id"] = source_room_id
        out["source_room_id"] = source_room_id

    if share_ref:
        binding["share_ref"] = share_ref
        out["mcp_share_ref"] = share_ref
        out["share_ref"] = share_ref

    binding["server_tool"] = server_tool
    binding["tool_name"] = tool_name
    out["server_tool"] = server_tool
    out["tool_name"] = tool_name

    if room_source:
        binding["room_source"] = dict(room_source)

    provider_snapshot = dict(_safe_dict(fact.get("provider_snapshot")))
    imported_provider = dict(_safe_dict(fact.get("imported_provider")))

    if provider_snapshot:
        provider_snapshot["provider_id"] = provider_id or _safe_str(provider_snapshot.get("provider_id"))
        provider_snapshot["provider_type"] = provider_type
        provider_snapshot["provider_kind"] = provider_type
        if provider_origin:
            provider_snapshot["provider_origin"] = provider_origin
        if room_source:
            provider_snapshot["room_source"] = dict(room_source)
        if source_room_id:
            provider_snapshot["source_room_id"] = source_room_id

        out["mcp_provider_snapshot"] = dict(provider_snapshot)
        out["provider_snapshot"] = dict(provider_snapshot)
        binding["provider_snapshot"] = dict(provider_snapshot)

    if imported_provider:
        imported_provider["provider_id"] = provider_id or _safe_str(imported_provider.get("provider_id"))
        imported_provider["provider_type"] = provider_type
        imported_provider["provider_kind"] = provider_type
        if provider_origin:
            imported_provider["provider_origin"] = provider_origin
        if room_source:
            imported_provider["room_source"] = dict(room_source)
        if source_room_id:
            imported_provider["source_room_id"] = source_room_id

        out["imported_provider"] = dict(imported_provider)
        binding["imported_provider"] = dict(imported_provider)

    if not provider_snapshot and not imported_provider:
        synthetic_snapshot = {
            "provider_id": provider_id,
            "provider_type": provider_type,
            "provider_kind": provider_type,
            "provider_origin": provider_origin,
            "server_tool": server_tool,
            "tool_name": tool_name,
            "source_room_id": source_room_id,
            "room_source": dict(room_source) if room_source else {},
        }
        out["mcp_provider_snapshot"] = synthetic_snapshot
        out["provider_snapshot"] = synthetic_snapshot
        binding["provider_snapshot"] = synthetic_snapshot

    out["mcp_binding"] = binding
    out["mcp_provider_ids"] = _safe_list(out.get("mcp_provider_ids")) or ([provider_id] if provider_id else [])
    out["rag_mode"] = "mcp"
    out["requested_mode"] = "mcp"

    return out


__all__ = [
    "_merge_role_mcp_binding",
    "_apply_mcp_contract_to_request_args",
    "_room_id_from_room_provider_id",
    "_is_room_provider_id",
    "_room_provider_source_exists_locally",
    "_normalize_room_provider_origin",
    "_extract_room_mcp_binding_fact",
    "_extract_explicit_role_mcp_provider_id",
    "_should_dispatch_role_room_mcp_provider",
    "_apply_room_mcp_binding_fact_to_request_args",
]
