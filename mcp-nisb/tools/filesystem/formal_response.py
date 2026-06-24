from __future__ import annotations

import uuid
from typing import Any, Dict, Optional, List

FORMAL_KEYS = {
    "conv_id",
    "request_id",
    "rag_mode",
    "mcp_overrides",
    "mode_used",
    "rss_evidence",
    "market_evidence",
    "evidence_query",
    "evidence_tools",
    "evidence_result",
    "qa_id",
    "group_id",
    "citations",
    "response",
    "status",
    "message",
    "tool_calls",
    "tool_results",
    "success",
}


def _new_request_id() -> str:
    return uuid.uuid4().hex[:10]


def _normalize_status(status: Any, success: Any) -> str:
    s = str(status or "").strip().lower()
    if s in {"success", "warning", "error"}:
        return s
    if success is True:
        return "success"
    if success is False:
        return "error"
    return "success"


def ensure_formal_response(
    args: Optional[Dict[str, Any]],
    result: Optional[Dict[str, Any]],
    *,
    default_kind: str,
    default_response: str = "",
    keep_compat_fields: bool = True,
) -> Dict[str, Any]:
    raw = dict(result or {})
    arg_map = dict(args or {})

    request_id = str(raw.get("request_id") or arg_map.get("request_id") or "").strip() or _new_request_id()
    status = _normalize_status(raw.get("status"), raw.get("success"))
    message = str(raw.get("message") or "").strip()
    response = str(raw.get("response") or "").strip() or message or default_response
    tool_calls = raw.get("tool_calls")
    if not isinstance(tool_calls, list):
        tool_calls = []

    tool_results = raw.get("tool_results")
    if not isinstance(tool_results, list):
        tool_results = []

    compat_data: Dict[str, Any] = {}
    for k, v in raw.items():
        if k in FORMAL_KEYS:
            continue
        compat_data[k] = v

    if compat_data and not tool_results:
        tool_results = [{"kind": default_kind, "data": compat_data}]

    out: Dict[str, Any] = {
        "request_id": request_id,
        "status": status,
        "message": message or response,
        "response": response or message or default_response,
        "tool_calls": tool_calls,
        "tool_results": tool_results,
        "success": raw["success"] if isinstance(raw.get("success"), bool) else (status != "error"),
    }

    for k in (
        "conv_id",
        "rag_mode",
        "mcp_overrides",
        "mode_used",
        "rss_evidence",
        "market_evidence",
        "evidence_query",
        "evidence_tools",
        "evidence_result",
        "qa_id",
        "group_id",
        "citations",
    ):
        if k in raw:
            out[k] = raw[k]

    if keep_compat_fields:
        out.update(compat_data)

    return out

