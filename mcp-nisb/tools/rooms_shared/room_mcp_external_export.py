from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Callable, Dict, List, Tuple

from .room_tools_mcp_providers import (
    nisb_room_mcp_provider_call,
    nisb_room_mcp_provider_list,
)


ROOM_PROVIDER_ID_PREFIX = "room_provider"
ROOM_PROVIDER_ID_STRICT_PREFIX = "room_provider__"


def _safe_dict(v: Any) -> Dict[str, Any]:
    return v if isinstance(v, dict) else {}


def _safe_list(v: Any) -> List[Any]:
    return v if isinstance(v, list) else []


def _safe_str(v: Any, default: str = "") -> str:
    if v is None:
        return default
    s = str(v).strip()
    return s if s else default


def _safe_bool(v: Any, default: bool = False) -> bool:
    if isinstance(v, bool):
        return v
    if isinstance(v, str):
        s = v.strip().lower()
        if s in {"1", "true", "yes", "on"}:
            return True
        if s in {"0", "false", "no", "off"}:
            return False
    return default


def _json_text(v: Any, *, max_chars: int = 4000) -> str:
    try:
        text = json.dumps(v, ensure_ascii=False, indent=2)
    except Exception:
        text = str(v)
    if len(text) > max_chars:
        return text[:max_chars] + "\n...<truncated>"
    return text


def _resolve_external_base_path(args: Dict[str, Any]) -> str:
    explicit = _safe_str(
        args.get("_base_path")
        or args.get("base_path")
        or args.get("basepath")
        or args.get("basePath")
    )
    if explicit:
        return explicit

    env_value = _safe_str(os.environ.get("NISB_EXTERNAL_MCP_BASE_PATH"))
    if env_value:
        return env_value

    users_root = Path("/data/users")
    try:
        if users_root.exists():
            candidates = []
            for child in users_root.iterdir():
                if child.is_dir() and _safe_str(child.name) and not child.name.startswith("."):
                    candidates.append(child)
            candidates.sort(key=lambda p: p.name)
            if candidates:
                return str(candidates[0])
    except Exception:
        pass

    return ""


def _extract_rows(result: Any) -> List[Dict[str, Any]]:
    if isinstance(result, list):
        return [x for x in result if isinstance(x, dict)]

    obj = _safe_dict(result)
    data = _safe_dict(obj.get("data"))
    result_obj = _safe_dict(obj.get("result"))

    candidates = [
        obj.get("providers"),
        obj.get("items"),
        obj.get("rows"),
        obj.get("results"),
        obj.get("schemas"),
        data.get("providers"),
        data.get("items"),
        data.get("rows"),
        data.get("schemas"),
        result_obj.get("providers"),
        result_obj.get("items"),
        result_obj.get("rows"),
        result_obj.get("schemas"),
    ]

    for c in candidates:
        rows = [x for x in _safe_list(c) if isinstance(x, dict)]
        if rows:
            return rows

    return []


def _provider_id(row: Dict[str, Any]) -> str:
    return _safe_str(row.get("provider_id") or row.get("id") or row.get("name"))


def _provider_origin(row: Dict[str, Any]) -> str:
    return _safe_str(row.get("provider_origin") or row.get("origin") or row.get("visibility_source"))


def _provider_kind(row: Dict[str, Any]) -> str:
    return _safe_str(row.get("provider_kind") or row.get("provider_type") or row.get("type"))


def _provider_source_room_id_from_id(provider_id: str) -> str:
    provider_id = _safe_str(provider_id)
    if provider_id.startswith(ROOM_PROVIDER_ID_STRICT_PREFIX):
        return provider_id[len(ROOM_PROVIDER_ID_STRICT_PREFIX):].strip()
    if provider_id.startswith("room_provider_"):
        return provider_id[len("room_provider_"):].strip()
    return ""


def _is_room_provider(row: Dict[str, Any]) -> bool:
    pid = _provider_id(row)
    kind = _provider_kind(row)
    ptype = _safe_str(row.get("provider_type"))
    return (
        pid.startswith(ROOM_PROVIDER_ID_PREFIX)
        or kind == "room_shared_capability"
        or ptype == "room_shared_capability"
    )


def _is_builtin_or_preset(row: Dict[str, Any]) -> bool:
    origin = _provider_origin(row)
    kind = _provider_kind(row)
    return (
        origin in {"builtin_external", "preset", "builtin"}
        or kind in {"preset", "builtin_external_mcp"}
    )


def _is_imported_remote(row: Dict[str, Any]) -> bool:
    return _provider_origin(row) in {
        "imported_remote",
        "federation",
        "federated_remote",
    }


def _owner_private_scope_exposed(row: Dict[str, Any]) -> bool:
    boundary = _safe_dict(row.get("shared_boundary"))
    return bool(
        boundary.get("owner_private_scope_exposed", False)
        or row.get("owner_private_scope_exposed", False)
    )


def _compact_provider(row: Dict[str, Any]) -> Dict[str, Any]:
    boundary = _safe_dict(row.get("shared_boundary"))
    source = _safe_dict(row.get("room_source"))
    invoke_contract = _safe_dict(row.get("invoke_contract"))

    return {
        "provider_id": _provider_id(row),
        "label": _safe_str(
            row.get("label")
            or row.get("provider_label")
            or row.get("title")
            or source.get("title")
        ),
        "description": _safe_str(
            row.get("description")
            or row.get("summary")
            or source.get("summary")
        ),
        "provider_type": _safe_str(row.get("provider_type") or _provider_kind(row)),
        "provider_kind": _provider_kind(row),
        "provider_origin": _provider_origin(row),
        "visibility_source": _safe_str(row.get("visibility_source")),
        "source_room_id": _safe_str(
            row.get("source_room_id")
            or source.get("room_id")
            or row.get("room_id")
        ),
        "server_tool": _safe_str(row.get("server_tool") or invoke_contract.get("server_tool")),
        "tool_name": _safe_str(row.get("tool_name") or invoke_contract.get("tool_name")),
        "requested_mode": _safe_str(row.get("requested_mode") or invoke_contract.get("requested_mode")),
        "owner_private_scope_exposed": bool(
            boundary.get("owner_private_scope_exposed", False)
            or row.get("owner_private_scope_exposed", False)
        ),
    }


def _result_text(result: Any) -> str:
    if isinstance(result, dict):
        for key in ("final_response", "answer", "message", "text", "content"):
            value = result.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()

        nested = result.get("result")
        if isinstance(nested, str) and nested.strip():
            return nested.strip()
        if isinstance(nested, dict):
            return _result_text(nested)

        return _json_text(result)

    if isinstance(result, str):
        return result

    return _json_text(result)


def _external_scope(args: Dict[str, Any]) -> Dict[str, Any]:
    for key in (
        "_external_mcp_publish_scope",
        "external_mcp_publish_scope",
        "_external_publish_scope",
    ):
        scope = _safe_dict(args.get(key))
        if scope.get("external_mcp_publish_scope") or scope.get("provider_id"):
            return scope
    return {}


def _scope_error(error: str, message: str = "", **extra: Any) -> Dict[str, Any]:
    text = message or error
    return {
        "ok": False,
        "external_export": True,
        "external_mcp_publish": True,
        "error": error,
        "message": text,
        "text": text,
        **extra,
    }


def _scope_provider_row(scope: Dict[str, Any]) -> Dict[str, Any]:
    provider_id = _safe_str(scope.get("provider_id"))
    source_room_id = _safe_str(scope.get("source_room_id"))
    provider_origin = _safe_str(scope.get("provider_origin"), "local_room_shared")

    row: Dict[str, Any] = {
        "provider_id": provider_id,
        "label": _safe_str(scope.get("label") or scope.get("client_label") or provider_id),
        "description": "Room-scoped external MCP provider",
        "provider_type": "room_shared_capability",
        "provider_kind": "room_shared_capability",
        "provider_origin": provider_origin,
        "visibility_source": "external_mcp_publish_scope",
        "source_room_id": source_room_id,
        "requested_mode": _safe_str(scope.get("requested_mode") or scope.get("allowed_mode") or "supervisor_direct"),
        "owner_private_scope_exposed": False,
    }

    try:
        from .room_mcp_provider_registry import get_room_mcp_provider

        meta = _safe_dict(get_room_mcp_provider(provider_id))
        if meta:
            merged = {**meta, **row}
            if not row.get("label"):
                merged["label"] = _safe_str(meta.get("label") or meta.get("provider_label") or provider_id)
            return merged
    except Exception:
        pass

    return row


def _call_registry_func(
    fn: Callable[..., Any],
    args: Dict[str, Any],
) -> Tuple[List[Dict[str, Any]], str]:
    room_id = _safe_str(args.get("room_id") or args.get("consumer_room_id"))
    attempts: List[Tuple[Tuple[Any, ...], Dict[str, Any]]] = []

    if room_id:
        attempts.extend([
            ((room_id,), {}),
            (({"room_id": room_id, **args},), {}),
            ((), {"room_id": room_id}),
        ])

    attempts.extend([
        ((args,), {}),
        ((), {}),
    ])

    last_error = ""

    for pos_args, kw_args in attempts:
        try:
            raw = fn(*pos_args, **kw_args)
            rows = _extract_rows(raw)
            if rows:
                return rows, ""
        except TypeError as ex:
            last_error = f"{type(ex).__name__}:{str(ex)[:160]}"
            continue
        except Exception as ex:
            last_error = f"{type(ex).__name__}:{str(ex)[:160]}"
            continue

    return [], last_error


def _registry_fallback_provider_rows(args: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], List[str]]:
    warnings: List[str] = []
    rows: List[Dict[str, Any]] = []
    room_id = _safe_str(args.get("room_id") or args.get("consumer_room_id"))

    try:
        from .room_mcp_provider_room_registry import (
            list_all_visible_room_provider_schemas,
            list_published_room_provider_schemas,
            list_room_visible_published_room_provider_schemas,
        )
    except Exception as ex:
        return [], [f"registry_import_failed:{type(ex).__name__}:{str(ex)[:160]}"]

    candidates: List[Tuple[str, Callable[..., Any]]] = []

    if room_id:
        candidates.append(("room_visible", list_room_visible_published_room_provider_schemas))
        candidates.append(("all_visible", list_all_visible_room_provider_schemas))

    candidates.append(("published", list_published_room_provider_schemas))

    for label, fn in candidates:
        got, err = _call_registry_func(fn, args)
        if got:
            rows.extend(got)
            warnings.append(f"registry_fallback_hit:{label}:{len(got)}")
            break
        warnings.append(f"registry_fallback_miss:{label}:{err}" if err else f"registry_fallback_empty:{label}")

    return rows, warnings


def _dedupe_rows(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    seen = set()

    for row in rows:
        pid = _provider_id(row)
        if not pid or pid in seen:
            continue
        seen.add(pid)
        out.append(row)

    return out


def _filter_external_rows(
    rows: List[Dict[str, Any]],
    *,
    include_imported_remote: bool,
    include_builtin: bool,
) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []

    for row in rows:
        if _owner_private_scope_exposed(row):
            continue

        if _is_imported_remote(row) and not include_imported_remote:
            continue

        if _is_room_provider(row):
            out.append(row)
            continue

        if include_builtin and _is_builtin_or_preset(row):
            out.append(row)
            continue

    return _dedupe_rows(out)


def nisb_room_mcp_external_provider_list(args: Dict[str, Any]) -> Dict[str, Any]:
    args = _safe_dict(args).copy()
    scope = _external_scope(args)

    if scope:
        provider = _compact_provider(_scope_provider_row(scope))
        provider["provider_id"] = _safe_str(scope.get("provider_id"))
        provider["source_room_id"] = _safe_str(scope.get("source_room_id"))
        provider["provider_origin"] = _safe_str(scope.get("provider_origin"), "local_room_shared")
        provider["owner_private_scope_exposed"] = False
        provider["source_observation_allowed"] = False
        provider["result_view"] = "final_result_only"

        lines = [
            "NISB Room MCP external providers:",
            "count=1",
            "result_view=final_result_only",
            "source_observation_allowed=false",
            "owner_private_scope_exposed=false",
            f"- {provider.get('provider_id')} | {provider.get('label') or provider.get('provider_id')} | origin={provider.get('provider_origin')} | source_room={provider.get('source_room_id')}",
        ]

        return {
            "ok": True,
            "external_export": True,
            "external_mcp_publish": True,
            "external_mcp_publish_scope": True,
            "count": 1,
            "providers": [provider],
            "result_view": "final_result_only",
            "source_observation_allowed": False,
            "owner_private_scope_exposed": False,
            "message": "\n".join(lines),
            "text": "\n".join(lines),
        }

    if _safe_bool(args.get("_external_mcp_publish_required"), False):
        return _scope_error("external_publish_token_missing")

    include_imported_remote = _safe_bool(args.get("include_imported_remote"), False)
    include_builtin = _safe_bool(args.get("include_builtin"), False)
    include_raw = _safe_bool(args.get("include_raw"), False)
    debug = _safe_bool(args.get("debug"), False)

    raw_primary: Any = None
    primary_rows: List[Dict[str, Any]] = []
    fallback_rows: List[Dict[str, Any]] = []
    diagnostics: List[str] = []

    try:
        raw_primary = nisb_room_mcp_provider_list(args)
        primary_rows = _extract_rows(raw_primary)
        diagnostics.append(f"primary_provider_list_rows:{len(primary_rows)}")
    except Exception as ex:
        diagnostics.append(f"primary_provider_list_error:{type(ex).__name__}:{str(ex)[:160]}")

    filtered_primary = _filter_external_rows(
        primary_rows,
        include_imported_remote=include_imported_remote,
        include_builtin=include_builtin,
    )

    if filtered_primary:
        rows = filtered_primary
        diagnostics.append(f"selected_source:primary:{len(rows)}")
    else:
        fallback_rows, fallback_warnings = _registry_fallback_provider_rows(args)
        diagnostics.extend(fallback_warnings)
        rows = _filter_external_rows(
            fallback_rows,
            include_imported_remote=include_imported_remote,
            include_builtin=include_builtin,
        )
        diagnostics.append(f"selected_source:registry_fallback:{len(rows)}")

    providers = [_compact_provider(row) for row in rows]

    lines = [
        "NISB Room MCP external providers:",
        f"count={len(providers)}",
    ]

    for p in providers:
        label = p.get("label") or p.get("provider_id")
        origin = p.get("provider_origin") or "unknown"
        source_room_id = p.get("source_room_id") or "unknown"
        lines.append(
            f"- {p.get('provider_id')} | {label} | origin={origin} | source_room={source_room_id}"
        )

    if debug and diagnostics:
        lines.append("")
        lines.append("diagnostics:")
        for item in diagnostics:
            lines.append(f"- {item}")

    out: Dict[str, Any] = {
        "ok": True,
        "external_export": True,
        "count": len(providers),
        "providers": providers,
        "message": "\n".join(lines),
        "text": "\n".join(lines),
    }

    if debug:
        out["diagnostics"] = diagnostics

    if include_raw:
        out["raw"] = {
            "primary": raw_primary,
            "primary_rows": primary_rows,
            "fallback_rows": fallback_rows,
        }

    return out


def nisb_room_mcp_external_provider_call(args: Dict[str, Any]) -> Dict[str, Any]:
    import uuid

    args = _safe_dict(args).copy()
    scope = _external_scope(args)

    provider_id_arg = _safe_str(args.get("provider_id"))
    question = _safe_str(args.get("question") or args.get("content") or args.get("text"))

    if not question:
        return _scope_error("missing_question", "question is required")

    if scope:
        scope_provider_id = _safe_str(scope.get("provider_id"))
        if not scope_provider_id:
            return _scope_error("external_publish_provider_mismatch", "external publish scope has no provider_id")

        if provider_id_arg and provider_id_arg != scope_provider_id:
            return _scope_error(
                "external_publish_provider_mismatch",
                "provider_id does not match external_mcp_publish_scope",
                provider_id=provider_id_arg,
                expected_provider_id=scope_provider_id,
            )

        provider_id = scope_provider_id
        source_room_id = _safe_str(scope.get("source_room_id"))
        provider_origin = _safe_str(scope.get("provider_origin"), "local_room_shared")
    else:
        provider_id = provider_id_arg
        source_room_id = ""
        provider_origin = ""

    if not provider_id:
        return {
            "ok": False,
            "external_export": True,
            "error": "missing_provider_id",
            "message": "provider_id is required",
            "text": "provider_id is required",
        }

    allow_non_room_provider = _safe_bool(args.get("allow_non_room_provider"), False)
    if not allow_non_room_provider and not provider_id.startswith(ROOM_PROVIDER_ID_PREFIX):
        return {
            "ok": False,
            "external_export": True,
            "error": "provider_not_room_provider",
            "provider_id": provider_id,
            "message": "external provider call only accepts room provider ids by default",
            "text": "external provider call only accepts room provider ids by default",
        }

    provider_meta: Dict[str, Any] = {}
    provider_resolve_error = ""

    try:
        from .room_mcp_provider_registry import get_room_mcp_provider

        provider_meta = _safe_dict(get_room_mcp_provider(provider_id))
    except Exception as ex:
        provider_resolve_error = f"{type(ex).__name__}:{str(ex)[:240]}"

    if not source_room_id:
        source_room_id = _safe_str(
            args.get("source_room_id")
            or _safe_dict(provider_meta.get("room_source")).get("room_id")
            or provider_meta.get("source_room_id")
        )

    if not source_room_id and provider_id.startswith(ROOM_PROVIDER_ID_PREFIX):
        source_room_id = _provider_source_room_id_from_id(provider_id)

    if not source_room_id:
        text = "unable to resolve source_room_id for external provider call"
        if provider_resolve_error:
            text += f"; provider_resolve_error={provider_resolve_error}"
        return {
            "ok": False,
            "external_export": True,
            "provider_id": provider_id,
            "error": "missing_source_room_id",
            "message": text,
            "text": text,
        }

    if not provider_origin:
        provider_origin = _safe_str(
            args.get("provider_origin")
            or provider_meta.get("provider_origin")
            or "local_room_shared"
        )

    if provider_origin in {"imported_remote", "federation", "federated_remote"} and not _safe_bool(
        args.get("allow_imported_remote"),
        False,
    ):
        return {
            "ok": False,
            "external_export": True,
            "provider_id": provider_id,
            "source_room_id": source_room_id,
            "provider_origin": provider_origin,
            "error": "imported_remote_not_exported",
            "message": "external MCP export does not call imported_remote/federation adapters by default",
            "text": "external MCP export does not call imported_remote/federation adapters by default",
        }

    request_id = _safe_str(
        args.get("request_id")
        or args.get("rid")
        or f"external_mcp_{uuid.uuid4().hex}"
    )

    if scope:
        room_id = source_room_id
    else:
        room_id = _safe_str(
            args.get("room_id")
            or args.get("consumer_room_id")
            or source_room_id
        )

    requested_mode = _safe_str(
        args.get("requested_mode")
        or provider_meta.get("requested_mode")
        or _safe_dict(provider_meta.get("invoke_contract")).get("requested_mode")
        or "supervisor_direct"
    )

    mcp_overrides = _safe_dict(args.get("mcp_overrides"))
    base_path = _resolve_external_base_path(args)

    call_args = args.copy()
    call_args["provider_id"] = provider_id
    call_args["question"] = question
    call_args.setdefault("content", question)
    call_args.setdefault("text", question)

    call_args["request_id"] = request_id
    call_args["room_id"] = room_id
    call_args.setdefault("consumer_room_id", room_id)
    call_args["source_room_id"] = source_room_id
    call_args["provider_origin"] = provider_origin or "local_room_shared"
    call_args["requested_mode"] = requested_mode
    call_args["mcp_overrides"] = mcp_overrides

    if base_path:
        call_args["base_path"] = base_path
        call_args["basepath"] = base_path
        call_args["basePath"] = base_path

    if provider_meta:
        call_args.setdefault("provider_meta", provider_meta)
        call_args.setdefault("provider_snapshot", provider_meta)
        call_args.setdefault("room_mcp_provider_snapshot", provider_meta)
        call_args.setdefault("room_mcp_binding", {
            "provider_id": provider_id,
            "provider_origin": provider_origin,
            "source_room_id": source_room_id,
            "provider_snapshot": provider_meta,
            "requested_mode": requested_mode,
        })
        call_args.setdefault("provider_type", _safe_str(provider_meta.get("provider_type")))
        call_args.setdefault("provider_kind", _safe_str(provider_meta.get("provider_kind")))
        call_args.setdefault("server_tool", _safe_str(provider_meta.get("server_tool")))
        call_args.setdefault("tool_name", _safe_str(provider_meta.get("tool_name")))
        call_args.setdefault("requested_mode", requested_mode)

    call_args["_room_mcp_external_export"] = True
    call_args["_room_mcp_provider_call"] = True
    call_args["_mcp_mode"] = True
    call_args["result_view"] = "final_result_only"
    call_args["source_observation_allowed"] = False
    call_args["owner_private_scope_exposed"] = False

    if scope:
        call_args["_external_mcp_publish_scope"] = scope
        call_args["_external_mcp_publish_required"] = True

    role = _safe_dict(args.get("role"))
    if not role:
        role = {
            "role_id": "external_mcp_client",
            "name": "External MCP Client",
            "type": "mcp_external_client",
        }

    role = {
        **role,
        "role_id": _safe_str(role.get("role_id"), "external_mcp_client"),
        "name": _safe_str(role.get("name"), "External MCP Client"),
        "provider_id": provider_id,
        "provider_origin": provider_origin,
        "source_room_id": source_room_id,
        "requested_mode": requested_mode,
        "mcp_binding": {
            **_safe_dict(role.get("mcp_binding")),
            "provider_id": provider_id,
            "provider_origin": provider_origin,
            "source_room_id": source_room_id,
            "provider_snapshot": provider_meta,
            "requested_mode": requested_mode,
        },
        "room_mcp_binding": {
            **_safe_dict(role.get("room_mcp_binding")),
            "provider_id": provider_id,
            "provider_origin": provider_origin,
            "source_room_id": source_room_id,
            "provider_snapshot": provider_meta,
            "requested_mode": requested_mode,
        },
        "room_mcp_provider_snapshot": provider_meta,
    }

    try:
        from .room_mcp_provider_adapter import dispatch_room_mcp_provider

        raw = dispatch_room_mcp_provider(
            room_id=room_id,
            request_id=request_id,
            question=question,
            requested_mode=requested_mode,
            mcp_overrides=mcp_overrides,
            request_args=call_args,
            role=role,
            provider_id=provider_id,
        )

        text = _result_text(raw)

        if scope:
            try:
                from .room_mcp_external_grant_resolver import mark_external_mcp_publish_used

                mark_external_mcp_publish_used(scope)
            except Exception:
                pass

            return {
                "ok": True,
                "external_export": True,
                "external_mcp_publish": True,
                "external_mcp_publish_scope": True,
                "provider_id": provider_id,
                "source_room_id": source_room_id,
                "room_id": room_id,
                "request_id": request_id,
                "provider_origin": provider_origin,
                "requested_mode": requested_mode,
                "result_view": "final_result_only",
                "source_observation_allowed": False,
                "owner_private_scope_exposed": False,
                "message": text,
                "text": text,
            }

        return {
            "ok": True,
            "external_export": True,
            "provider_id": provider_id,
            "source_room_id": source_room_id,
            "room_id": room_id,
            "request_id": request_id,
            "provider_origin": provider_origin,
            "requested_mode": requested_mode,
            "base_path_injected": bool(base_path),
            "result": raw,
            "message": text,
            "text": text,
        }
    except Exception as ex:
        text = f"external provider call failed: {type(ex).__name__}: {str(ex)[:300]}"
        return {
            "ok": False,
            "external_export": True,
            "external_mcp_publish": bool(scope),
            "provider_id": provider_id,
            "source_room_id": source_room_id,
            "room_id": room_id,
            "request_id": request_id,
            "provider_origin": provider_origin,
            "requested_mode": requested_mode,
            "error": "external_provider_call_failed",
            "base_path_injected": bool(base_path),
            "error_type": type(ex).__name__,
            "message": text,
            "text": text,
        }


__all__ = [
    "nisb_room_mcp_external_provider_call",
    "nisb_room_mcp_external_provider_list",
]


