from __future__ import annotations

import inspect
from typing import Any, Callable, Dict

from .room_request_bridge import _safe_dict, _safe_str
from .room_mcp_provider_arxiv import execute_room_mcp_provider_arxiv
from .room_mcp_provider_exa import execute_room_mcp_provider_exa
from .room_mcp_provider_pexels import execute_room_mcp_provider_pexels
from .room_mcp_provider_serper import execute_room_mcp_provider_serper
from .room_mcp_provider_invoke_contract import hydrate_provider_invoke_contract
from .room_mcp_adapter_provider_context import (
    _build_provider_dispatch_request_args,
    _collect_provider_request_context,
    _context_prefers_imported_remote,
    _derive_provider_id_from_request_args,
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

ProviderExecutor = Callable[..., Dict[str, Any]]

_DESCRIPTOR_VERSION_FALLBACK = "v1"
_SERVER_TOOL_FALLBACK = "nisb_room_mcp_provider_call"
_REQUESTED_MODE_FALLBACK = "mcp"
_PROVIDER_KIND_FALLBACK = "builtin_external_mcp"


def _hydrate_provider_executor_meta(
    provider_id: str,
    executor: ProviderExecutor,
) -> Dict[str, Any]:
    return {
        "provider_id": _safe_str(provider_id).lower(),
        "provider_kind": _PROVIDER_KIND_FALLBACK,
        "descriptor_version": _DESCRIPTOR_VERSION_FALLBACK,
        "server_tool": _SERVER_TOOL_FALLBACK,
        "executor_name": getattr(executor, "__name__", ""),
    }


def _get_room_mcp_provider_executors() -> Dict[str, ProviderExecutor]:
    return {
        "serper": execute_room_mcp_provider_serper,
        "arxiv": execute_room_mcp_provider_arxiv,
        "pexels": execute_room_mcp_provider_pexels,
        "exa": execute_room_mcp_provider_exa,
    }


def _get_room_mcp_provider_executor_registry() -> Dict[str, Dict[str, Any]]:
    executors = _get_room_mcp_provider_executors()
    out: Dict[str, Dict[str, Any]] = {}
    for provider_id, executor in executors.items():
        out[provider_id] = {
            "executor": executor,
            **_hydrate_provider_executor_meta(provider_id, executor),
        }
    return out


def _executor_accepts_kwarg(executor: ProviderExecutor, name: str) -> bool:
    try:
        sig = inspect.signature(executor)
    except Exception:
        return True

    for param in sig.parameters.values():
        if param.kind == inspect.Parameter.VAR_KEYWORD:
            return True

    return name in sig.parameters


def _resolve_executor_entry(provider_id: Any) -> Dict[str, Any]:
    key = _safe_str(provider_id).lower()
    if not key:
        return {}

    return _safe_dict(_get_room_mcp_provider_executor_registry().get(key))


def _call_provider_executor_compat(
    *,
    executor: ProviderExecutor,
    room_id: str,
    request_id: str,
    question: str,
    requested_mode: str,
    mcp_overrides: Dict[str, Any],
    request_args: Dict[str, Any],
    role: Dict[str, Any],
    provider_meta: Dict[str, Any],
) -> Dict[str, Any]:
    hydrated_provider_meta = hydrate_provider_invoke_contract(provider_meta)

    exec_request_args = dict(request_args or {})
    exec_request_args.setdefault("_room_mcp_provider_meta", _safe_dict(hydrated_provider_meta))

    call_kwargs: Dict[str, Any] = {
        "room_id": room_id,
        "request_id": request_id,
        "question": question,
        "requested_mode": _safe_str(
            requested_mode,
            _safe_str(hydrated_provider_meta.get("requested_mode"), _REQUESTED_MODE_FALLBACK),
        ) or _REQUESTED_MODE_FALLBACK,
        "mcp_overrides": mcp_overrides,
        "request_args": exec_request_args,
        "role": role,
    }

    if _executor_accepts_kwarg(executor, "provider_meta"):
        call_kwargs["provider_meta"] = hydrated_provider_meta

    return executor(**call_kwargs)


__all__ = [
    "ProviderExecutor",
    "_build_provider_dispatch_request_args",
    "_call_provider_executor_compat",
    "_collect_provider_request_context",
    "_context_prefers_imported_remote",
    "_derive_provider_id_from_request_args",
    "_executor_accepts_kwarg",
    "_get_room_mcp_provider_executor_registry",
    "_get_room_mcp_provider_executors",
    "_hydrate_provider_executor_meta",
    "_merge_provider_meta_with_context",
    "_normalize_provider_meta_shape",
    "_normalize_provider_origin",
    "_normalize_provider_request_args_for_validation",
    "_pick_first_str",
    "_resolve_executor_entry",
    "_resolve_param_value",
    "_resolve_provider_meta_from_request_args",
    "_safe_list",
    "_validate_provider_params",
]
