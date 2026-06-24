from __future__ import annotations

from typing import Any, Dict, List

from .room_request_bridge import (
    _safe_dict,
    _safe_str,
)
from .room_mcp_provider_registry import (
    resolve_room_mcp_provider,
)


def _safe_list(v: Any) -> List[Any]:
    return list(v) if isinstance(v, list) else []


def _safe_query_str(value: Any) -> str:
    s = _safe_str(value)
    if s == "{{user_query}}":
        return ""
    return s


def _pick_first_str(*values: Any) -> str:
    for value in values:
        s = _safe_str(value)
        if s:
            return s
    return ""

_ROOM_PROVIDER_PREFIX = "room_provider__"


def _room_id_from_room_provider_id(provider_id: Any) -> str:
    value = _safe_str(provider_id)
    if value.startswith(_ROOM_PROVIDER_PREFIX):
        return _safe_str(value[len(_ROOM_PROVIDER_PREFIX):])
    return ""


def _origin_is_imported_remote(value: Any) -> bool:
    return _normalize_provider_origin(value).startswith("imported_remote")


def _origin_is_local_room_shared(value: Any) -> bool:
    return _normalize_provider_origin(value) in {
        "local_room_shared",
        "local_registry",
        "registry_local",
        "local_provider",
        "local",
    }


def _normalize_room_provider_source_identity(provider_meta: Dict[str, Any]) -> Dict[str, Any]:
    meta = dict(_safe_dict(provider_meta))
    provider_id = _safe_str(meta.get("provider_id"))
    derived_room_id = _room_id_from_room_provider_id(provider_id)


    if not derived_room_id:
        return meta


    meta["source_room_id"] = derived_room_id


    room_source = dict(_safe_dict(meta.get("room_source")))
    room_source["room_id"] = derived_room_id
    meta["room_source"] = room_source


    return meta


def _strip_external_grant_context_for_local_provider(provider_meta: Dict[str, Any]) -> Dict[str, Any]:
    meta = dict(_safe_dict(provider_meta))
    provider_origin = _safe_str(
        meta.get("provider_origin")
        or _safe_dict(meta.get("imported_provider")).get("provider_origin")
        or _safe_dict(meta.get("provider_snapshot")).get("provider_origin")
    )


    if _origin_is_imported_remote(provider_origin):
        return meta


    for key in (
        "share_ref",
        "mcp_share_ref",
        "descriptor_ref",
        "_grant_meta",
        "grant_meta",
        "grant",
        "_room_mcp_grant",
        "grant_id",
        "artifact_id",
        "grant_state",
        "grant_mode",
        "discovery_mode",
        "resolution_source",
        "visibility_source",
        "result_view",
        "external_result_view",
        "peer_id",
        "remote_peer_id",
        "target_peer_id",
        "source_peer_id",
        "federation_peer_id",
        "remote_user_id",
        "grant_peer_id",
        "grant_remote_user_id",
        "source_observation_allowed",
    ):
        meta.pop(key, None)


    return meta

def _normalize_provider_origin(value: Any) -> str:
    return _safe_str(value).lower()


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


def _context_prefers_imported_remote(context: Dict[str, Any] | None) -> bool:
    ctx = _safe_dict(context)
    provider_snapshot = _safe_dict(ctx.get("provider_snapshot"))
    imported_provider = _safe_dict(ctx.get("imported_provider"))

    for candidate in (
        ctx.get("provider_origin"),
        provider_snapshot.get("provider_origin"),
        imported_provider.get("provider_origin"),
    ):
        if _normalize_provider_origin(candidate).startswith("imported_remote"):
            return True
    return False


def _resolve_param_value(value: Any, fallback: Any) -> Any:
    if isinstance(value, str) and value.strip() == "{{user_query}}":
        return fallback
    return value


def _derive_provider_id_from_request_args(
    *,
    provider_id: str = "",
    request_args: Dict[str, Any] | None = None,
    role: Dict[str, Any] | None = None,
) -> str:
    req = _safe_dict(request_args)
    role_obj = _safe_dict(role)

    mcp_binding = _safe_dict(req.get("mcp_binding"))
    provider_snapshot = _safe_dict(
        req.get("mcp_provider_snapshot")
        or req.get("provider_snapshot")
        or mcp_binding.get("provider_snapshot")
    )
    imported_provider = _safe_dict(
        req.get("imported_provider")
        or mcp_binding.get("imported_provider")
    )

    role_mcp_binding = _safe_dict(role_obj.get("mcp_binding"))
    role_provider_snapshot = _safe_dict(
        role_obj.get("mcp_provider_snapshot")
        or role_mcp_binding.get("provider_snapshot")
    )
    role_imported_provider = _safe_dict(
        role_obj.get("imported_provider")
        or role_mcp_binding.get("imported_provider")
    )

    for candidate in (
        provider_id,
        req.get("provider_id"),
        req.get("mcp_provider_id"),
        req.get("_room_mcp_provider_id"),
        mcp_binding.get("provider_id"),
        provider_snapshot.get("provider_id"),
        imported_provider.get("provider_id"),
        role_obj.get("provider_id"),
        role_mcp_binding.get("provider_id"),
        role_provider_snapshot.get("provider_id"),
        role_imported_provider.get("provider_id"),
    ):
        value = _safe_str(candidate)
        if value:
            return value

    return ""


def _collect_provider_request_context(
    *,
    request_args: Dict[str, Any] | None = None,
    role: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    req = _safe_dict(request_args)
    role_obj = _safe_dict(role)

    mcp_binding = _safe_dict(req.get("mcp_binding"))
    role_mcp_binding = _safe_dict(role_obj.get("mcp_binding"))

    outer_mcp_binding = _safe_dict(req.get("_outer_room_mcp_binding"))
    outer_provider_snapshot = _safe_dict(req.get("_outer_room_mcp_provider_snapshot"))
    outer_imported_provider = _safe_dict(req.get("_outer_room_mcp_imported_provider"))
    outer_room_source = _safe_dict(req.get("_outer_room_mcp_room_source"))
    outer_boundary_hint = _safe_dict(req.get("_outer_room_mcp_boundary_hint"))

    provider_snapshot = _safe_dict(
        req.get("mcp_provider_snapshot")
        or req.get("provider_snapshot")
        or mcp_binding.get("provider_snapshot")
        or role_obj.get("mcp_provider_snapshot")
        or role_mcp_binding.get("provider_snapshot")
        or outer_provider_snapshot
        or outer_mcp_binding.get("provider_snapshot")
    )

    imported_provider = _safe_dict(
        req.get("imported_provider")
        or mcp_binding.get("imported_provider")
        or role_obj.get("imported_provider")
        or role_mcp_binding.get("imported_provider")
        or outer_imported_provider
        or outer_mcp_binding.get("imported_provider")
    )

    share_ref = _safe_str(
        req.get("mcp_share_ref")
        or req.get("share_ref")
        or mcp_binding.get("share_ref")
        or imported_provider.get("share_ref")
        or provider_snapshot.get("share_ref")
        or role_obj.get("share_ref")
        or role_mcp_binding.get("share_ref")
        or req.get("_outer_room_mcp_share_ref")
        or outer_mcp_binding.get("share_ref")
        or outer_imported_provider.get("share_ref")
        or outer_provider_snapshot.get("share_ref")
    )

    provider_origin = _safe_str(
        req.get("provider_origin")
        or mcp_binding.get("provider_origin")
        or imported_provider.get("provider_origin")
        or provider_snapshot.get("provider_origin")
        or role_obj.get("provider_origin")
        or role_mcp_binding.get("provider_origin")
        or req.get("_outer_room_mcp_provider_origin")
        or outer_mcp_binding.get("provider_origin")
        or outer_imported_provider.get("provider_origin")
        or outer_provider_snapshot.get("provider_origin")
    )

    direct_binding_hints: Dict[str, Any] = {}
    for key in (
        "provider_id",
        "provider_type",
        "provider_label",
        "source_room_id",
        "grant_id",
        "artifact_id",
        "grant_state",
        "grant_mode",
        "discovery_mode",
        "resolution_source",
        "visibility_source",
        "result_view",
        "external_result_view",
        "source_observation_allowed",
        "peer_id",
        "remote_peer_id",
        "target_peer_id",
        "source_peer_id",
        "federation_peer_id",
        "remote_user_id",
        "grant_peer_id",
        "grant_remote_user_id",
        "consumer_room_id",
    ):
        value = req.get(key)
        if value in (None, ""):
            value = mcp_binding.get(key)
        if value in (None, ""):
            value = imported_provider.get(key)
        if value in (None, ""):
            value = provider_snapshot.get(key)
        if value in (None, ""):
            value = role_obj.get(key)
        if value in (None, ""):
            value = role_mcp_binding.get(key)
        if value in (None, ""):
            value = outer_mcp_binding.get(key)
        if value in (None, ""):
            value = outer_imported_provider.get(key)
        if value in (None, ""):
            value = outer_provider_snapshot.get(key)

        if key == "source_observation_allowed":
            if isinstance(value, bool):
                direct_binding_hints[key] = value
            continue

        s = _safe_str(value)
        if s:
            direct_binding_hints[key] = s

    room_source = {
        **_safe_dict(outer_room_source),
        **_safe_dict(outer_mcp_binding.get("room_source")),
        **_safe_dict(outer_provider_snapshot.get("room_source")),
        **_safe_dict(outer_imported_provider.get("room_source")),
        **_safe_dict(provider_snapshot.get("room_source")),
        **_safe_dict(imported_provider.get("room_source")),
    }
    if room_source:
        direct_binding_hints["room_source"] = room_source

    boundary_hint = {
        **_safe_dict(outer_boundary_hint),
        **_safe_dict(outer_mcp_binding.get("boundary_hint")),
        **_safe_dict(outer_provider_snapshot.get("boundary_hint")),
        **_safe_dict(outer_imported_provider.get("boundary_hint")),
        **_safe_dict(provider_snapshot.get("boundary_hint")),
        **_safe_dict(imported_provider.get("boundary_hint")),
    }
    if boundary_hint:
        direct_binding_hints["boundary_hint"] = boundary_hint

    return {
        "mcp_binding": mcp_binding or outer_mcp_binding,
        "role_mcp_binding": role_mcp_binding,
        "provider_snapshot": provider_snapshot,
        "imported_provider": imported_provider,
        "share_ref": share_ref,
        "provider_origin": provider_origin,
        "direct_binding_hints": direct_binding_hints,
    }


def _merge_provider_meta_with_context(
    *,
    provider_meta: Dict[str, Any] | None,
    context: Dict[str, Any] | None,
) -> Dict[str, Any]:
    merged = dict(_safe_dict(provider_meta))
    ctx = _safe_dict(context)

    provider_snapshot = _safe_dict(ctx.get("provider_snapshot"))
    imported_provider = _safe_dict(ctx.get("imported_provider"))
    share_ref = _safe_str(ctx.get("share_ref"))
    provider_origin = _safe_str(ctx.get("provider_origin"))
    direct_binding_hints = _safe_dict(ctx.get("direct_binding_hints"))

    prefer_imported_remote = _context_prefers_imported_remote(ctx)

    ctx_room_source = {
        **_safe_dict(provider_snapshot.get("room_source")),
        **_safe_dict(imported_provider.get("room_source")),
        **_safe_dict(direct_binding_hints.get("room_source")),
    }

    ctx_boundary_hint = {
        **_safe_dict(provider_snapshot.get("boundary_hint")),
        **_safe_dict(imported_provider.get("boundary_hint")),
        **_safe_dict(direct_binding_hints.get("boundary_hint")),
    }

    if prefer_imported_remote:
        if share_ref:
            merged["share_ref"] = share_ref
        if provider_snapshot:
            merged["provider_snapshot"] = dict(provider_snapshot)
        if imported_provider:
            merged["imported_provider"] = dict(imported_provider)
        if provider_origin:
            merged["provider_origin"] = provider_origin
        elif not _safe_str(merged.get("provider_origin")):
            merged["provider_origin"] = "imported_remote"
    else:
        if share_ref and not _safe_str(merged.get("share_ref")):
            merged["share_ref"] = share_ref
        if provider_snapshot and not _safe_dict(merged.get("provider_snapshot")):
            merged["provider_snapshot"] = dict(provider_snapshot)
        if imported_provider and not _safe_dict(merged.get("imported_provider")):
            merged["imported_provider"] = dict(imported_provider)
        if provider_origin and not _safe_str(merged.get("provider_origin")):
            merged["provider_origin"] = provider_origin

    if prefer_imported_remote:
        room_source = {
            **_safe_dict(merged.get("room_source")),
            **ctx_room_source,
        }
    else:
        room_source = {
            **_safe_dict(provider_snapshot.get("room_source")),
            **_safe_dict(imported_provider.get("room_source")),
            **_safe_dict(direct_binding_hints.get("room_source")),
            **_safe_dict(merged.get("room_source")),
        }
    if room_source:
        merged["room_source"] = room_source

    if prefer_imported_remote:
        provider_origin_meta = {
            **_safe_dict(merged.get("provider_origin_meta")),
            **_safe_dict(provider_snapshot.get("provider_origin_meta")),
            **_safe_dict(imported_provider.get("provider_origin_meta")),
        }
    else:
        provider_origin_meta = {
            **_safe_dict(provider_snapshot.get("provider_origin_meta")),
            **_safe_dict(imported_provider.get("provider_origin_meta")),
            **_safe_dict(merged.get("provider_origin_meta")),
        }
    if provider_origin_meta:
        merged["provider_origin_meta"] = provider_origin_meta

    if prefer_imported_remote:
        federation = {
            **_safe_dict(merged.get("federation")),
            **_safe_dict(provider_snapshot.get("federation")),
            **_safe_dict(imported_provider.get("federation")),
        }
    else:
        federation = {
            **_safe_dict(provider_snapshot.get("federation")),
            **_safe_dict(imported_provider.get("federation")),
            **_safe_dict(merged.get("federation")),
        }
    if federation:
        merged["federation"] = federation

    if prefer_imported_remote:
        share_ref_payload = {
            **_safe_dict(merged.get("share_ref_payload")),
            **_safe_dict(provider_snapshot.get("share_ref_payload")),
            **_safe_dict(imported_provider.get("share_ref_payload")),
        }
    else:
        share_ref_payload = {
            **_safe_dict(provider_snapshot.get("share_ref_payload")),
            **_safe_dict(imported_provider.get("share_ref_payload")),
            **_safe_dict(merged.get("share_ref_payload")),
        }
    if share_ref_payload:
        merged["share_ref_payload"] = share_ref_payload

    grant_audience = _safe_dict(
        merged.get("grant_audience")
        or imported_provider.get("grant_audience")
        or provider_snapshot.get("grant_audience")
    )
    if grant_audience:
        merged["grant_audience"] = grant_audience

    for key in (
        "grant_id",
        "artifact_id",
        "grant_state",
        "grant_mode",
        "discovery_mode",
        "resolution_source",
        "visibility_source",
        "result_view",
        "external_result_view",
        "peer_id",
        "remote_peer_id",
        "target_peer_id",
        "source_peer_id",
        "federation_peer_id",
        "remote_user_id",
        "grant_peer_id",
        "grant_remote_user_id",
        "consumer_room_id",
        "source_room_id",
        "provider_id",
        "provider_type",
        "provider_label",
    ):
        if prefer_imported_remote:
            value = _pick_first_str(
                imported_provider.get(key),
                provider_snapshot.get(key),
                direct_binding_hints.get(key),
                merged.get(key),
            )
            if value:
                merged[key] = value
        else:
            if _safe_str(merged.get(key)):
                continue
            value = _pick_first_str(
                direct_binding_hints.get(key),
                provider_snapshot.get(key),
                imported_provider.get(key),
            )
            if value:
                merged[key] = value

    if "source_observation_allowed" not in merged:
        if "source_observation_allowed" in direct_binding_hints:
            merged["source_observation_allowed"] = bool(direct_binding_hints.get("source_observation_allowed"))
        elif isinstance(imported_provider.get("source_observation_allowed"), bool):
            merged["source_observation_allowed"] = bool(imported_provider.get("source_observation_allowed"))
        elif isinstance(provider_snapshot.get("source_observation_allowed"), bool):
            merged["source_observation_allowed"] = bool(provider_snapshot.get("source_observation_allowed"))

    if prefer_imported_remote:
        if ctx_boundary_hint:
            merged["boundary_hint"] = dict(ctx_boundary_hint)
        elif _safe_dict(merged.get("boundary_hint")):
            merged["boundary_hint"] = dict(_safe_dict(merged.get("boundary_hint")))
    else:
        boundary_hint = _safe_dict(
            merged.get("boundary_hint")
            or direct_binding_hints.get("boundary_hint")
            or provider_snapshot.get("boundary_hint")
            or imported_provider.get("boundary_hint")
        )
        if boundary_hint:
            merged["boundary_hint"] = boundary_hint

    source_room_id = _pick_first_str(
        merged.get("source_room_id"),
        imported_provider.get("source_room_id"),
        provider_snapshot.get("source_room_id"),
        _safe_dict(merged.get("room_source")).get("room_id"),
        imported_provider.get("room_id"),
        provider_snapshot.get("room_id"),
    )
    if source_room_id:
        merged["source_room_id"] = source_room_id
        room_source = dict(_safe_dict(merged.get("room_source")))
        room_source["room_id"] = source_room_id
        merged["room_source"] = room_source

    if prefer_imported_remote:
        if not _safe_str(merged.get("provider_type")):
            merged["provider_type"] = "room_shared_capability"
        if not _safe_str(merged.get("provider_origin")):
            merged["provider_origin"] = "imported_remote"

    label = _pick_first_str(
        merged.get("label"),
        merged.get("provider_label"),
        imported_provider.get("label"),
        imported_provider.get("provider_label"),
        provider_snapshot.get("label"),
        provider_snapshot.get("provider_label"),
    )
    if label:
        merged["label"] = label

    return merged


def _resolve_provider_meta_from_request_args(
    *,
    provider_id: str,
    request_args: Dict[str, Any],
    role: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    ctx = _collect_provider_request_context(
        request_args=request_args,
        role=role,
    )


    provider_snapshot = _safe_dict(ctx.get("provider_snapshot"))
    imported_provider = _safe_dict(ctx.get("imported_provider"))
    share_ref = _safe_str(ctx.get("share_ref"))
    provider_origin = _safe_str(ctx.get("provider_origin"))


    raw = {
        "provider_id": provider_id,
        "share_ref": share_ref,
        "provider_snapshot": provider_snapshot,
        "imported_provider": imported_provider,
        "provider_origin": provider_origin,
    }


    try:
        resolved = resolve_room_mcp_provider(
            provider_id=provider_id,
            share_ref=share_ref,
            provider_snapshot=provider_snapshot,
            imported_provider=imported_provider,
            raw=raw,
        )
    except Exception:
        resolved = {}


    if not resolved and (provider_snapshot or imported_provider or share_ref):
        resolved = {
            "provider_id": provider_id,
            "share_ref": share_ref,
        }


    merged = _merge_provider_meta_with_context(
        provider_meta=_safe_dict(resolved),
        context=ctx,
    )


    resolved_origin = _safe_str(
        _safe_dict(resolved).get("provider_origin")
        or merged.get("provider_origin")
        or provider_origin
    )


    context_wants_imported_remote = _context_prefers_imported_remote(ctx)
    resolved_is_local_room_shared = _origin_is_local_room_shared(resolved_origin)


    if context_wants_imported_remote and not resolved_is_local_room_shared:
        merged["provider_origin"] = _pick_first_str(
            merged.get("provider_origin"),
            provider_origin,
            imported_provider.get("provider_origin"),
            provider_snapshot.get("provider_origin"),
            "imported_remote",
        )
        merged["provider_type"] = _pick_first_str(
            merged.get("provider_type"),
            imported_provider.get("provider_type"),
            provider_snapshot.get("provider_type"),
            "room_shared_capability",
        )


        imported_provider_id = _pick_first_str(
            imported_provider.get("provider_id"),
            provider_snapshot.get("provider_id"),
            merged.get("provider_id"),
            provider_id,
        )
        if imported_provider_id:
            merged["provider_id"] = imported_provider_id


        remote_source_room_id = _pick_first_str(
            _room_id_from_room_provider_id(imported_provider_id),
            merged.get("source_room_id"),
            imported_provider.get("source_room_id"),
            provider_snapshot.get("source_room_id"),
            _safe_dict(imported_provider.get("room_source")).get("room_id"),
            _safe_dict(provider_snapshot.get("room_source")).get("room_id"),
        )
        if remote_source_room_id:
            merged["source_room_id"] = remote_source_room_id
            room_source = _safe_dict(merged.get("room_source"))
            room_source["room_id"] = remote_source_room_id
            merged["room_source"] = room_source


        provider_label = _pick_first_str(
            imported_provider.get("provider_label"),
            imported_provider.get("label"),
            provider_snapshot.get("provider_label"),
            provider_snapshot.get("label"),
            merged.get("provider_label"),
            merged.get("label"),
        )
        if provider_label:
            merged["provider_label"] = provider_label
            merged["label"] = provider_label


    merged = _normalize_room_provider_source_identity(merged)


    if not _origin_is_imported_remote(merged.get("provider_origin")):
        merged = _strip_external_grant_context_for_local_provider(merged)


    return merged


def _build_provider_dispatch_request_args(
    *,
    request_args: Dict[str, Any],
    provider_meta: Dict[str, Any],
) -> Dict[str, Any]:
    out = dict(request_args or {})
    meta = _normalize_room_provider_source_identity(_safe_dict(provider_meta))


    prefer_imported_remote = _normalize_provider_origin(
        meta.get("provider_origin")
        or _safe_dict(meta.get("imported_provider")).get("provider_origin")
        or _safe_dict(meta.get("provider_snapshot")).get("provider_origin")
    ).startswith("imported_remote")


    if not prefer_imported_remote:
        meta = _strip_external_grant_context_for_local_provider(meta)


    mcp_binding = _safe_dict(out.get("mcp_binding"))


    external_keys = (
        "mcp_share_ref",
        "share_ref",
        "descriptor_ref",
        "grant_meta",
        "grant",
        "_room_mcp_grant",
        "grant_id",
        "artifact_id",
        "grant_state",
        "grant_mode",
        "discovery_mode",
        "resolution_source",
        "visibility_source",
        "result_view",
        "external_result_view",
        "peer_id",
        "remote_peer_id",
        "target_peer_id",
        "source_peer_id",
        "federation_peer_id",
        "remote_user_id",
        "grant_peer_id",
        "grant_remote_user_id",
        "source_observation_allowed",
    )


    if not prefer_imported_remote:
        for key in (
            *external_keys,
            "provider_snapshot",
            "mcp_provider_snapshot",
            "imported_provider",
            "source_room_id",
            "_room_mcp_source_room_id",
        ):
            out.pop(key, None)


        cleaned_binding = dict(mcp_binding)
        for key in (
            *external_keys,
            "provider_snapshot",
            "imported_provider",
            "source_room_id",
            "room_source",
        ):
            cleaned_binding.pop(key, None)
        mcp_binding = cleaned_binding


    grant_meta = _safe_dict(
        meta.get("_grant_meta")
        or meta.get("grant_meta")
        or meta.get("grant")
    ) if prefer_imported_remote else {}


    if prefer_imported_remote:
        provider_snapshot = _safe_dict(
            meta.get("provider_snapshot")
            or out.get("mcp_provider_snapshot")
            or out.get("provider_snapshot")
            or mcp_binding.get("provider_snapshot")
        )
        imported_provider = _safe_dict(
            meta.get("imported_provider")
            or out.get("imported_provider")
            or mcp_binding.get("imported_provider")
        )
        share_ref = _safe_str(
            meta.get("share_ref")
            or grant_meta.get("descriptor_ref")
            or out.get("mcp_share_ref")
            or out.get("share_ref")
            or mcp_binding.get("share_ref")
        )
    else:
        provider_snapshot = {}
        imported_provider = {}
        share_ref = ""


    merged_binding = dict(mcp_binding)


    for key in (
        "provider_id",
        "provider_type",
        "provider_origin",
        "provider_label",
        "source_room_id",
        "consumer_room_id",
    ):
        if prefer_imported_remote:
            value = _pick_first_str(
                meta.get(key),
                grant_meta.get(key),
                merged_binding.get(key),
            )
        else:
            value = _pick_first_str(
                meta.get(key),
                merged_binding.get(key),
            )
        if value:
            merged_binding[key] = value


    if prefer_imported_remote:
        for key in (
            "grant_id",
            "artifact_id",
            "grant_state",
            "grant_mode",
            "discovery_mode",
            "resolution_source",
            "visibility_source",
            "result_view",
            "external_result_view",
            "peer_id",
            "remote_peer_id",
            "target_peer_id",
            "source_peer_id",
            "federation_peer_id",
            "remote_user_id",
            "grant_peer_id",
            "grant_remote_user_id",
        ):
            value = _pick_first_str(
                meta.get(key),
                grant_meta.get(key),
                merged_binding.get(key),
            )
            if value:
                merged_binding[key] = value


        if "source_observation_allowed" in meta and isinstance(meta.get("source_observation_allowed"), bool):
            merged_binding["source_observation_allowed"] = bool(meta.get("source_observation_allowed"))
        elif "source_observation_allowed" in grant_meta and isinstance(grant_meta.get("source_observation_allowed"), bool):
            merged_binding["source_observation_allowed"] = bool(grant_meta.get("source_observation_allowed"))


    if provider_snapshot:
        merged_binding["provider_snapshot"] = dict(provider_snapshot)
        out["mcp_provider_snapshot"] = dict(provider_snapshot)
        out["provider_snapshot"] = dict(provider_snapshot)
    else:
        out.pop("mcp_provider_snapshot", None)
        out.pop("provider_snapshot", None)


    if imported_provider:
        merged_binding["imported_provider"] = dict(imported_provider)
        out["imported_provider"] = dict(imported_provider)
    else:
        out.pop("imported_provider", None)


    if share_ref:
        merged_binding["share_ref"] = share_ref
        out["mcp_share_ref"] = share_ref
        out["share_ref"] = share_ref


    if grant_meta:
        merged_binding["grant_meta"] = dict(grant_meta)
        merged_binding["grant"] = dict(grant_meta)
        out["_room_mcp_grant"] = dict(grant_meta)
        out["grant_meta"] = dict(grant_meta)
        out["grant"] = dict(grant_meta)


    if prefer_imported_remote:
        room_source = _safe_dict(meta.get("room_source"))
        if not room_source:
            room_source = _safe_dict(
                merged_binding.get("room_source")
                or imported_provider.get("room_source")
                or provider_snapshot.get("room_source")
            )
    else:
        room_source = _safe_dict(meta.get("room_source"))


    if room_source:
        merged_binding["room_source"] = dict(room_source)


    if prefer_imported_remote:
        boundary_hint = _safe_dict(meta.get("boundary_hint"))
        if not boundary_hint:
            boundary_hint = _safe_dict(
                merged_binding.get("boundary_hint")
                or imported_provider.get("boundary_hint")
                or provider_snapshot.get("boundary_hint")
            )
    else:
        boundary_hint = _safe_dict(meta.get("boundary_hint"))


    if boundary_hint:
        merged_binding["boundary_hint"] = dict(boundary_hint)


    merged_binding = _normalize_room_provider_source_identity(merged_binding)


    source_room_id = _pick_first_str(
        merged_binding.get("source_room_id"),
        meta.get("source_room_id"),
        _safe_dict(merged_binding.get("room_source")).get("room_id"),
    )
    if source_room_id:
        merged_binding["source_room_id"] = source_room_id
        room_source = _safe_dict(merged_binding.get("room_source"))
        room_source["room_id"] = source_room_id
        merged_binding["room_source"] = room_source


    if not prefer_imported_remote:
        for key in external_keys:
            merged_binding.pop(key, None)


    out["mcp_binding"] = merged_binding


    for key in (
        "provider_id",
        "provider_type",
        "provider_origin",
        "provider_label",
        "source_room_id",
        "consumer_room_id",
    ):
        value = _safe_str(merged_binding.get(key))
        if value:
            out[key] = value


    if source_room_id:
        out["_room_mcp_source_room_id"] = source_room_id


    provider_id = _safe_str(merged_binding.get("provider_id") or meta.get("provider_id"))
    if provider_id:
        out["_room_mcp_provider_id"] = provider_id


    for key in (
        "grant_id",
        "artifact_id",
        "grant_state",
        "grant_mode",
        "discovery_mode",
        "resolution_source",
        "visibility_source",
        "result_view",
        "external_result_view",
        "peer_id",
        "remote_peer_id",
        "target_peer_id",
        "source_peer_id",
        "federation_peer_id",
        "remote_user_id",
        "grant_peer_id",
        "grant_remote_user_id",
    ):
        if not prefer_imported_remote:
            out.pop(key, None)
            continue


        value = _safe_str(merged_binding.get(key))
        if value:
            out[key] = value


    if prefer_imported_remote and isinstance(merged_binding.get("source_observation_allowed"), bool):
        out["source_observation_allowed"] = bool(merged_binding.get("source_observation_allowed"))
    else:
        out.pop("source_observation_allowed", None)


    out["_room_mcp_provider_meta"] = meta
    out["_room_mcp_provider_origin"] = _safe_str(meta.get("provider_origin"))
    out["_room_mcp_provider_id"] = _safe_str(meta.get("provider_id"))
    out["_room_mcp_provider_type"] = _safe_str(meta.get("provider_type"))


    return out


def _normalize_provider_request_args_for_validation(
    *,
    question: str,
    request_args: Dict[str, Any],
) -> tuple[Dict[str, Any], str]:
    out = dict(request_args or {})
    resolved_question = _normalize_question(question=question, request_args=out)
    resolved_question = _safe_str(resolved_question) or _safe_str(question)

    out = _apply_question_aliases(out, resolved_question)

    mcp_binding = _safe_dict(out.get("mcp_binding"))
    out["mcp_binding"] = _apply_mcp_binding_question_aliases(mcp_binding, resolved_question)

    return out, resolved_question


def _validate_provider_params(provider_meta: Dict[str, Any], request_args: Dict[str, Any], question: str) -> str:
    mcp_binding = _safe_dict(request_args.get("mcp_binding"))
    params = _safe_dict(mcp_binding.get("params"))
    schema = _safe_dict(provider_meta.get("params_schema"))
    properties = _safe_dict(schema.get("properties"))
    required = _safe_list(schema.get("required"))

    for key in required:
        name = _safe_str(key)
        if not name:
            continue
        value = _resolve_param_value(params.get(name), question)
        if value is None:
            return f"invalid_params:missing_required:{name}"
        if isinstance(value, str) and not value.strip():
            return f"invalid_params:missing_required:{name}"

    for key, raw_value in params.items():
        prop = _safe_dict(properties.get(key))
        if not prop:
            continue

        expected_type = _safe_str(prop.get("type"))
        value = _resolve_param_value(raw_value, question)

        if expected_type == "string":
            if value is None:
                continue
            if not isinstance(value, str):
                return f"invalid_params:type:{key}:string"
            enum_values = _safe_list(prop.get("enum"))
            if enum_values and value not in enum_values:
                return f"invalid_params:enum:{key}"

        elif expected_type == "integer":
            try:
                int_value = int(value)
            except Exception:
                return f"invalid_params:type:{key}:integer"
            minimum = prop.get("minimum")
            maximum = prop.get("maximum")
            if minimum is not None and int_value < int(minimum):
                return f"invalid_params:minimum:{key}"
            if maximum is not None and int_value > int(maximum):
                return f"invalid_params:maximum:{key}"

        elif expected_type == "array":
            if not isinstance(value, list):
                return f"invalid_params:type:{key}:array"
            item_schema = _safe_dict(prop.get("items"))
            item_type = _safe_str(item_schema.get("type"))
            if item_type == "string":
                for item in value:
                    if not isinstance(item, str):
                        return f"invalid_params:item_type:{key}:string"

        elif expected_type == "boolean":
            if not isinstance(value, bool):
                return f"invalid_params:type:{key}:boolean"

    return ""


def _normalize_provider_meta_shape(provider_meta: Dict[str, Any]) -> Dict[str, Any]:
    meta = _normalize_room_provider_source_identity(_safe_dict(provider_meta))
    provider_id = _safe_str(meta.get("provider_id")).lower()
    provider_origin = _safe_str(meta.get("provider_origin")).lower()
    provider_type = _safe_str(meta.get("provider_type"))
    provider_kind = _safe_str(meta.get("provider_kind"))


    preset_ids = {"exa", "serper", "arxiv", "pexels"}


    if provider_id in preset_ids:
        if (
            provider_origin == "local_registry"
            or provider_type == "preset"
            or provider_kind == "preset"
            or provider_type == "room_shared_capability"
            or provider_kind == "room_shared_capability"
        ):
            meta["provider_type"] = "preset"
            meta["provider_kind"] = "preset"
            meta.pop("source_room_id", None)
            meta["room_source"] = {}


    if not _origin_is_imported_remote(meta.get("provider_origin")):
        meta = _strip_external_grant_context_for_local_provider(meta)


    return meta


__all__ = [
    "_build_provider_dispatch_request_args",
    "_collect_provider_request_context",
    "_context_prefers_imported_remote",
    "_derive_provider_id_from_request_args",
    "_merge_provider_meta_with_context",
    "_normalize_provider_meta_shape",
    "_normalize_provider_origin",
    "_normalize_provider_request_args_for_validation",
    "_normalize_room_provider_source_identity",
    "_pick_first_str",
    "_resolve_param_value",
    "_resolve_provider_meta_from_request_args",
    "_room_id_from_room_provider_id",
    "_safe_list",
    "_strip_external_grant_context_for_local_provider",
    "_validate_provider_params",
]

