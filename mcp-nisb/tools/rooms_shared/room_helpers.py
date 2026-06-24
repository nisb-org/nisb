from __future__ import annotations

from typing import Any, Optional

from .room_audit_helpers import (
    _append_aborted_event,
    _append_room_event,
    _build_dialog_lines,
    _build_run_id,
    _clear_run_state,
    _load_room_state,
    _set_room_state_patch,
    _update_room_last_message,
)
from .room_binding_policy import (
    _binding_has_target,
    _get_active_role_objects,
    _normalize_mode_used,
    _normalize_scope,
    _resolve_default_reply_role,
    _resolve_effective_binding,
    _role_kb,
    _role_tool_policy,
    _safe_dict,
    _safe_list,
    _safe_optional_id,
    _safe_str,
    resolve_role_for_content,
)
from .room_contracts import as_bool as _contract_as_bool
from .room_packet_builder import _build_room_message_payload, _empty_evidence_result
from .room_request_bridge import (
    MissingAnthropicDependencyError,
    MissingLLMDependencyError,
    _bridge_chat_result,
    _build_orchestrate_args,
    _call_llm_json,
    _call_role_reply,
    _call_role_reply_packet,
    _call_role_reply_with_meta,
    _call_role_reply_with_runtime,
    _call_room_ai_reply,
    _call_room_ai_reply_packet,
    _call_room_ai_reply_with_meta,
    _call_room_plain_reply,
    _call_room_reply_packet,
    _call_room_reply_with_meta,
    _call_supervisor_final,
    _call_supervisor_plan,
    _coerce_dict_list,
    _coerce_str_list,
    _ensure_formal_packet,
    _extract_user_question,
    _get_int,
    _get_str,
    _merge_delegate_ids_with_all_active,
    _merge_role_binding,
    _normalize_qascope_packet,
)


def _as_bool(v: Any, default: bool = False) -> bool:
    return _contract_as_bool(v, default)


def _safe_text(v: Any, default: str = "") -> str:
    return _safe_str(v, default)


def _parse_optional_float(value: Any) -> Optional[float]:
    s = _safe_str(value)
    if not s:
        return None
    try:
        return float(s)
    except Exception:
        return None


def _parse_optional_int(value: Any) -> Optional[int]:
    s = _safe_str(value)
    if not s:
        return None
    try:
        return max(1, int(s))
    except Exception:
        return None


__all__ = [
    "MissingLLMDependencyError",
    "MissingAnthropicDependencyError",
    "_append_aborted_event",
    "_binding_has_target",
    "_build_dialog_lines",
    "_build_room_message_payload",
    "_build_run_id",
    "_call_llm_json",
    "_call_role_reply",
    "_call_role_reply_packet",
    "_call_role_reply_with_meta",
    "_call_role_reply_with_runtime",
    "_call_room_ai_reply",
    "_call_room_ai_reply_packet",
    "_call_room_ai_reply_with_meta",
    "_call_room_plain_reply",
    "_call_room_reply_packet",
    "_call_room_reply_with_meta",
    "_call_supervisor_final",
    "_call_supervisor_plan",
    "_clear_run_state",
    "_coerce_dict_list",
    "_coerce_str_list",
    "_empty_evidence_result",
    "_get_active_role_objects",
    "_get_int",
    "_get_str",
    "_merge_delegate_ids_with_all_active",
    "_normalize_mode_used",
    "_resolve_default_reply_role",
    "_resolve_effective_binding",
    "_role_tool_policy",
    "_set_room_state_patch",
    "_update_room_last_message",
    "resolve_role_for_content",
]
