from __future__ import annotations

from typing import Any, Dict, Optional

from .room_tools_mcp_providers import (
    get_room_mcp_grant_by_id,
    parse_room_mcp_grant_artifact,
)
from .room_mcp_runtime_context import (
    _rt_safe_dict,
    _rt_safe_str,
)


def _rt_request_mcp_binding(args: Dict[str, Any]) -> Dict[str, Any]:
    return _rt_safe_dict(_rt_safe_dict(args).get("mcp_binding"))


def _rt_request_provider_snapshot(args: Dict[str, Any]) -> Dict[str, Any]:
    req = _rt_safe_dict(args)
    mcp_binding = _rt_request_mcp_binding(req)
    return _rt_safe_dict(
        req.get("mcp_provider_snapshot")
        or req.get("provider_snapshot")
        or mcp_binding.get("provider_snapshot")
    )


def _rt_request_imported_provider(args: Dict[str, Any]) -> Dict[str, Any]:
    req = _rt_safe_dict(args)
    mcp_binding = _rt_request_mcp_binding(req)
    return _rt_safe_dict(
        req.get("imported_provider")
        or mcp_binding.get("imported_provider")
    )


def _rt_extract_provider_bridge_origin(
    args: Dict[str, Any],
    *,
    provider_info: Optional[Dict[str, Any]] = None,
) -> str:
    req = _rt_safe_dict(args)
    info = _rt_safe_dict(provider_info)
    mcp_binding = _rt_request_mcp_binding(req)
    provider_snapshot = _rt_request_provider_snapshot(req)
    imported_provider = _rt_request_imported_provider(req)

    return _rt_safe_str(
        req.get("_room_mcp_provider_origin")
        or info.get("provider_origin")
        or mcp_binding.get("provider_origin")
        or provider_snapshot.get("provider_origin")
        or imported_provider.get("provider_origin")
    ).lower()


def _rt_provider_bridge_uses_external_grant_context(
    args: Dict[str, Any],
    *,
    provider_info: Optional[Dict[str, Any]] = None,
) -> bool:
    req = _rt_safe_dict(args)
    info = _rt_safe_dict(provider_info)
    mcp_binding = _rt_request_mcp_binding(req)
    provider_snapshot = _rt_request_provider_snapshot(req)
    imported_provider = _rt_request_imported_provider(req)

    origin = _rt_extract_provider_bridge_origin(
        req,
        provider_info=info,
    )
    if origin.startswith("imported_remote"):
        return True

    provider_bridge_call = bool(
        req.get("_room_mcp_provider_call")
        or req.get("_room_mcp_bridge")
        or req.get("_room_mcp_provider_id")
    )

    share_ref = _rt_safe_str(
        req.get("mcp_share_ref")
        or req.get("share_ref")
        or req.get("descriptor_ref")
        or mcp_binding.get("share_ref")
        or mcp_binding.get("descriptor_ref")
        or provider_snapshot.get("share_ref")
        or provider_snapshot.get("descriptor_ref")
        or imported_provider.get("share_ref")
        or imported_provider.get("descriptor_ref")
        or info.get("share_ref")
        or info.get("descriptor_ref")
        or _rt_safe_dict(info.get("room_source")).get("share_ref")
        or _rt_safe_dict(info.get("room_source")).get("descriptor_ref")
    )

    if share_ref.startswith("room-mcp-grant:"):
        return True

    if not provider_bridge_call:
        return False

    for obj in (
        req,
        mcp_binding,
        provider_snapshot,
        imported_provider,
        info,
        _rt_safe_dict(info.get("_grant_meta")),
        _rt_safe_dict(info.get("grant_meta")),
        _rt_safe_dict(info.get("grant")),
        _rt_safe_dict(req.get("_room_mcp_grant")),
        _rt_safe_dict(req.get("grant_meta")),
        _rt_safe_dict(req.get("grant")),
        _rt_safe_dict(mcp_binding.get("grant_meta")),
        _rt_safe_dict(mcp_binding.get("grant")),
    ):
        row = _rt_safe_dict(obj)
        if _rt_safe_str(row.get("grant_id")) or _rt_safe_str(row.get("artifact_id")):
            return True
        if _rt_safe_str(row.get("grant_mode")) == "share_artifact":
            return True
        if _rt_safe_str(row.get("discovery_mode")) == "granted_visible":
            return True
        if _rt_safe_str(row.get("resolution_source")) in {"grant_artifact", "grant_store"}:
            return True

    return False

def _rt_extract_provider_bridge_share_ref(
    args: Dict[str, Any],
    *,
    provider_info: Optional[Dict[str, Any]] = None,
) -> str:
    if not _rt_provider_bridge_uses_external_grant_context(
        args,
        provider_info=provider_info,
    ):
        return ""

    req = _rt_safe_dict(args)
    info = _rt_safe_dict(provider_info)
    mcp_binding = _rt_request_mcp_binding(req)
    provider_snapshot = _rt_request_provider_snapshot(req)
    imported_provider = _rt_request_imported_provider(req)
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
    *,
    provider_info: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    if not _rt_provider_bridge_uses_external_grant_context(
        args,
        provider_info=provider_info,
    ):
        return {}

    req = _rt_safe_dict(args)
    info = _rt_safe_dict(provider_info)
    mcp_binding = _rt_request_mcp_binding(req)
    provider_snapshot = _rt_request_provider_snapshot(req)
    imported_provider = _rt_request_imported_provider(req)

    share_ref = _rt_extract_provider_bridge_share_ref(
        req,
        provider_info=provider_info,
    )
    if not share_ref:
        share_ref = _rt_safe_str(
            req.get("descriptor_ref")
            or mcp_binding.get("descriptor_ref")
            or provider_snapshot.get("descriptor_ref")
            or imported_provider.get("descriptor_ref")
            or info.get("descriptor_ref")
            or _rt_safe_dict(info.get("room_source")).get("descriptor_ref")
        )

    artifact = {}
    if share_ref:
        artifact = _rt_safe_dict(parse_room_mcp_grant_artifact(share_ref))

    candidates = [
        info.get("_grant_meta"),
        info.get("grant_meta"),
        info.get("grant"),
        req.get("_room_mcp_grant"),
        req.get("grant_meta"),
        req.get("grant"),
        mcp_binding.get("grant_meta"),
        mcp_binding.get("grant"),
        provider_snapshot.get("_grant_meta"),
        provider_snapshot.get("grant_meta"),
        provider_snapshot.get("grant"),
        imported_provider.get("_grant_meta"),
        imported_provider.get("grant_meta"),
        imported_provider.get("grant"),
        artifact,
    ]

    merged: Dict[str, Any] = {}
    for candidate in candidates:
        obj = _rt_safe_dict(candidate)
        if obj:
            merged.update(obj)

    if not merged:
        direct_grant_id = _rt_safe_str(
            req.get("grant_id")
            or mcp_binding.get("grant_id")
            or provider_snapshot.get("grant_id")
            or imported_provider.get("grant_id")
            or info.get("grant_id")
        )
        direct_artifact_id = _rt_safe_str(
            req.get("artifact_id")
            or mcp_binding.get("artifact_id")
            or provider_snapshot.get("artifact_id")
            or imported_provider.get("artifact_id")
            or info.get("artifact_id")
        )
        direct_source_room_id = _rt_safe_str(
            req.get("_room_mcp_source_room_id")
            or req.get("source_room_id")
            or mcp_binding.get("source_room_id")
            or provider_snapshot.get("source_room_id")
            or imported_provider.get("source_room_id")
            or info.get("source_room_id")
            or _rt_safe_dict(info.get("room_source")).get("room_id")
        )
        direct_provider_id = _rt_safe_str(
            req.get("_room_mcp_provider_id")
            or req.get("provider_id")
            or mcp_binding.get("provider_id")
            or provider_snapshot.get("provider_id")
            or imported_provider.get("provider_id")
            or info.get("provider_id")
        )

        if direct_grant_id or direct_artifact_id:
            merged = {
                "grant_id": direct_grant_id,
                "artifact_id": direct_artifact_id,
                "source_room_id": direct_source_room_id,
                "provider_id": direct_provider_id,
            }

    if not merged:
        return {}

    if share_ref and not _rt_safe_str(merged.get("share_ref")):
        merged["share_ref"] = share_ref
    if share_ref and not _rt_safe_str(merged.get("descriptor_ref")):
        merged["descriptor_ref"] = share_ref

    if not _rt_safe_str(merged.get("source_room_id")):
        merged["source_room_id"] = _rt_safe_str(
            req.get("_room_mcp_source_room_id")
            or req.get("source_room_id")
            or mcp_binding.get("source_room_id")
            or provider_snapshot.get("source_room_id")
            or imported_provider.get("source_room_id")
            or info.get("source_room_id")
            or _rt_safe_dict(info.get("room_source")).get("room_id")
        )

    if not _rt_safe_str(merged.get("provider_id")):
        merged["provider_id"] = _rt_safe_str(
            req.get("_room_mcp_provider_id")
            or req.get("provider_id")
            or mcp_binding.get("provider_id")
            or provider_snapshot.get("provider_id")
            or imported_provider.get("provider_id")
            or info.get("provider_id")
        )

    return merged


def _rt_is_capability_bridge_invoke(
    *,
    args: Dict[str, Any],
    provider_bridge_call: bool,
    provider_info: Optional[Dict[str, Any]] = None,
) -> bool:
    if not provider_bridge_call:
        return False

    req = _rt_safe_dict(args)
    info = _rt_safe_dict(provider_info)
    mcp_binding = _rt_request_mcp_binding(req)

    if _rt_provider_bridge_uses_external_grant_context(
        args,
        provider_info=provider_info,
    ):
        return True

    provider_type = _rt_safe_str(
        req.get("_room_mcp_provider_type")
        or info.get("provider_type")
        or mcp_binding.get("provider_type")
    )
    provider_id = _rt_safe_str(
        req.get("_room_mcp_provider_id")
        or info.get("provider_id")
        or mcp_binding.get("provider_id")
    )

    return bool(provider_id) and provider_type == "room_shared_capability"


def _rt_is_link_grant_backed_capability_invoke(
    *,
    args: Dict[str, Any],
    provider_bridge_call: bool,
    provider_info: Optional[Dict[str, Any]] = None,
) -> bool:
    if not provider_bridge_call:
        return False

    if not _rt_provider_bridge_uses_external_grant_context(
        args,
        provider_info=provider_info,
    ):
        return False

    req = _rt_safe_dict(args)
    info = _rt_safe_dict(provider_info)

    mcp_binding = _rt_request_mcp_binding(req)
    provider_snapshot = _rt_request_provider_snapshot(req)
    imported_provider = _rt_request_imported_provider(req)

    resolution_source = _rt_safe_str(
        info.get("resolution_source")
        or provider_snapshot.get("resolution_source")
        or imported_provider.get("resolution_source")
    )
    discovery_mode = _rt_safe_str(
        info.get("discovery_mode")
        or provider_snapshot.get("discovery_mode")
        or imported_provider.get("discovery_mode")
    )

    share_ref = _rt_extract_provider_bridge_share_ref(
        req,
        provider_info=provider_info,
    )
    parsed_artifact = _rt_safe_dict(parse_room_mcp_grant_artifact(share_ref))
    grant_meta = _rt_extract_provider_bridge_grant_meta(
        req,
        provider_info=provider_info,
    )

    grant_id = _rt_safe_str(
        req.get("grant_id")
        or mcp_binding.get("grant_id")
        or info.get("grant_id")
        or grant_meta.get("grant_id")
        or parsed_artifact.get("grant_id")
    )
    artifact_id = _rt_safe_str(
        req.get("artifact_id")
        or mcp_binding.get("artifact_id")
        or info.get("artifact_id")
        or grant_meta.get("artifact_id")
        or parsed_artifact.get("artifact_id")
    )

    if parsed_artifact:
        return True
    if share_ref and share_ref.startswith("room-mcp-grant:"):
        return True
    if grant_id or artifact_id:
        return True
    if resolution_source in {"grant_artifact", "grant_store"}:
        return True
    if discovery_mode == "granted_visible":
        return True

    return False


def _rt_has_resolvable_grant_reference(
    *,
    args: Dict[str, Any],
    provider_info: Optional[Dict[str, Any]] = None,
) -> bool:
    if not _rt_provider_bridge_uses_external_grant_context(
        args,
        provider_info=provider_info,
    ):
        return False

    req = _rt_safe_dict(args)
    info = _rt_safe_dict(provider_info)

    mcp_binding = _rt_request_mcp_binding(req)
    share_ref = _rt_extract_provider_bridge_share_ref(
        req,
        provider_info=provider_info,
    )
    parsed_artifact = _rt_safe_dict(parse_room_mcp_grant_artifact(share_ref))
    grant_meta = _rt_extract_provider_bridge_grant_meta(
        req,
        provider_info=provider_info,
    )

    grant_id = _rt_safe_str(
        req.get("grant_id")
        or mcp_binding.get("grant_id")
        or info.get("grant_id")
        or grant_meta.get("grant_id")
        or parsed_artifact.get("grant_id")
    )
    artifact_id = _rt_safe_str(
        req.get("artifact_id")
        or mcp_binding.get("artifact_id")
        or info.get("artifact_id")
        or grant_meta.get("artifact_id")
        or parsed_artifact.get("artifact_id")
    )
    source_room_id = _rt_safe_str(
        req.get("_room_mcp_source_room_id")
        or info.get("source_room_id")
        or grant_meta.get("source_room_id")
        or parsed_artifact.get("source_room_id")
        or _rt_safe_dict(info.get("room_source")).get("room_id")
    )

    if parsed_artifact and (parsed_artifact.get("grant_id") or parsed_artifact.get("artifact_id")):
        return True
    if source_room_id and (grant_id or artifact_id):
        return True

    return False


def _rt_validate_provider_bridge_grant(
    *,
    room_id: str,
    args: Dict[str, Any],
    provider_info: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    if not _rt_provider_bridge_uses_external_grant_context(
        args,
        provider_info=provider_info,
    ):
        return {
            "checked": False,
            "allowed": True,
            "reason_code": "",
            "grant_meta": {},
            "share_ref": "",
        }

    info = _rt_safe_dict(provider_info)
    room_source = _rt_safe_dict(info.get("room_source"))

    share_ref = _rt_extract_provider_bridge_share_ref(
        args,
        provider_info=provider_info,
    )
    artifact = _rt_safe_dict(parse_room_mcp_grant_artifact(share_ref))
    grant_meta = _rt_extract_provider_bridge_grant_meta(
        args,
        provider_info=provider_info,
    )

    candidate = grant_meta or artifact
    if not candidate:
        return {
            "checked": False,
            "allowed": True,
            "reason_code": "",
            "grant_meta": {},
            "share_ref": share_ref,
        }

    source_room_id = _rt_safe_str(
        candidate.get("source_room_id")
        or info.get("source_room_id")
        or room_source.get("room_id")
        or room_id
    )
    provider_id = _rt_safe_str(
        info.get("provider_id")
        or candidate.get("provider_id")
    )
    grant_id = _rt_safe_str(candidate.get("grant_id"))
    artifact_id = _rt_safe_str(candidate.get("artifact_id"))

    if not source_room_id or (not grant_id and not artifact_id):
        return {
            "checked": False,
            "allowed": True,
            "reason_code": "",
            "grant_meta": candidate,
            "share_ref": share_ref,
        }

    row = get_room_mcp_grant_by_id(
        source_room_id=source_room_id,
        grant_id=grant_id,
        artifact_id=artifact_id,
    )
    if not row:
        return {
            "checked": True,
            "allowed": False,
            "reason_code": "grant_not_found",
            "grant_meta": candidate,
            "share_ref": share_ref,
        }

    row_provider_id = _rt_safe_str(row.get("provider_id"))
    grant_state = _rt_safe_str(row.get("grant_state"))

    merged_grant_meta = {
        **candidate,
        **_rt_safe_dict(row),
    }

    if row_provider_id and provider_id and row_provider_id != provider_id:
        return {
            "checked": True,
            "allowed": False,
            "reason_code": "grant_provider_mismatch",
            "grant_meta": merged_grant_meta,
            "share_ref": share_ref,
        }

    if grant_state == "revoked":
        return {
            "checked": True,
            "allowed": False,
            "reason_code": "grant_revoked",
            "grant_meta": merged_grant_meta,
            "share_ref": share_ref,
        }

    if grant_state == "expired":
        return {
            "checked": True,
            "allowed": False,
            "reason_code": "grant_expired",
            "grant_meta": merged_grant_meta,
            "share_ref": share_ref,
        }

    if grant_state and grant_state != "active":
        return {
            "checked": True,
            "allowed": False,
            "reason_code": f"grant_{grant_state}",
            "grant_meta": merged_grant_meta,
            "share_ref": share_ref,
        }

    return {
        "checked": True,
        "allowed": True,
        "reason_code": "",
        "grant_meta": merged_grant_meta,
        "share_ref": share_ref,
    }


__all__ = [
    "_rt_extract_provider_bridge_origin",
    "_rt_provider_bridge_uses_external_grant_context",
    "_rt_extract_provider_bridge_share_ref",
    "_rt_extract_provider_bridge_grant_meta",
    "_rt_is_capability_bridge_invoke",
    "_rt_is_link_grant_backed_capability_invoke",
    "_rt_has_resolvable_grant_reference",
    "_rt_validate_provider_bridge_grant",
]

