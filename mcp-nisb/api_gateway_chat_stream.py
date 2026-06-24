#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

from typing import Any, Dict, List, Optional

import anyio


CHAT_STREAM_TOOLS = {"nisb_chat_send", "nisb_chat_orchestrate"}
CHAT_ALLOWED_EVENTS = {"meta", "delta", "tool_call", "tool_result", "final", "error", "done"}

_STANDARD_CHAT_KEYS = {
    "request_id",
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
    "response",
    "status",
    "message",
    "tool_calls",
    "tool_results",
}


def read_std_request_id(arguments: Dict[str, Any]) -> str:
    return str((arguments or {}).get("request_id") or (arguments or {}).get("requestid") or "").strip()


def read_std_conv_id(arguments: Dict[str, Any]) -> str:
    return str((arguments or {}).get("conv_id") or (arguments or {}).get("convid") or "").strip()


def read_std_rag_mode(arguments: Dict[str, Any]) -> str:
    return str((arguments or {}).get("rag_mode") or (arguments or {}).get("ragmode") or "").strip()


def read_std_mcp_overrides(arguments: Dict[str, Any]) -> Dict[str, Any]:
    obj = (arguments or {}).get("mcp_overrides")
    if isinstance(obj, dict):
        return obj
    obj = (arguments or {}).get("mcpoverrides")
    if isinstance(obj, dict):
        return obj
    return {}


def read_string(obj: Dict[str, Any], *keys: str) -> str:
    if not isinstance(obj, dict):
        return ""
    for key in keys:
        value = obj.get(key)
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return ""


def read_array(obj: Dict[str, Any], *keys: str) -> List[Any]:
    if not isinstance(obj, dict):
        return []
    for key in keys:
        value = obj.get(key)
        if isinstance(value, list):
            return value
    return []


def read_object(obj: Dict[str, Any], *keys: str) -> Dict[str, Any]:
    if not isinstance(obj, dict):
        return {}
    for key in keys:
        value = obj.get(key)
        if isinstance(value, dict):
            return value
    return {}


def normalize_chat_event_name(event_name: str) -> str:
    raw = str(event_name or "").strip().lower()
    if raw == "toolcall":
        return "tool_call"
    if raw == "toolresult":
        return "tool_result"
    if raw == "status":
        return "meta"
    if raw in CHAT_ALLOWED_EVENTS:
        return raw
    if raw in {"message", "chunk"}:
        return "delta"
    if not raw:
        return "delta"
    return "meta"


def _default_response_for_event(ev: str, src: Dict[str, Any]) -> str:
    response = read_string(src, "response", "content", "text", "delta")
    if response:
        return response
    if ev == "meta":
        return "stream_started"
    if ev == "done":
        return read_string(src, "final_response") or "done"
    if ev == "error":
        return read_string(src, "message", "error") or "stream failed"
    if ev == "final":
        return read_string(src, "message") or "已生成最终回答"
    if ev in {"tool_call", "tool_result"}:
        return read_string(src, "message") or ev
    return ""


def normalize_chat_payload(
    data: Dict[str, Any],
    *,
    request_id: str = "",
    conv_id: str = "",
    event_name: str = "",
) -> Dict[str, Any]:
    src = data if isinstance(data, dict) else {}
    ev = normalize_chat_event_name(event_name)

    out: Dict[str, Any] = {
        "request_id": read_string(src, "request_id", "requestid") or str(request_id or ""),
        "conv_id": read_string(src, "conv_id", "convid") or str(conv_id or ""),
        "rag_mode": read_string(src, "rag_mode", "ragmode"),
        "mcp_overrides": read_object(src, "mcp_overrides", "mcpoverrides"),
        "mode_used": read_string(src, "mode_used", "modeused"),
        "rss_evidence": read_array(src, "rss_evidence", "rssevidence"),
        "market_evidence": read_array(src, "market_evidence", "marketevidence"),
        "evidence_query": read_string(src, "evidence_query", "evidencequery"),
        "evidence_tools": read_array(src, "evidence_tools", "evidencetools"),
        "evidence_result": read_object(src, "evidence_result", "evidenceresult"),
        "qa_id": read_string(src, "qa_id", "qaid"),
        "group_id": read_string(src, "group_id", "groupid"),
        "citations": read_array(src, "citations"),
        "response": read_string(src, "response", "content", "text", "delta"),
        "status": read_string(src, "status"),
        "message": read_string(src, "message", "error"),
        "tool_calls": read_array(src, "tool_calls", "toolcalls"),
        "tool_results": read_array(src, "tool_results", "toolresults"),
    }

    if ev == "meta" and not out["status"]:
        out["status"] = "running"
    if ev == "done" and not out["status"]:
        out["status"] = "success"
    if ev == "final" and not out["status"]:
        out["status"] = "success"
    if ev == "error":
        out["status"] = "error"
        if not out["message"]:
            out["message"] = "stream failed"

    if not out["response"]:
        out["response"] = _default_response_for_event(ev, src)

    if out["status"] == "success" and not out["response"]:
        out["response"] = out["message"] or "已完成请求"

    if out["status"] == "error" and not out["response"]:
        out["response"] = out["message"] or "请求失败"

    for key in _STANDARD_CHAT_KEYS:
        if key not in out:
            if key in {"rss_evidence", "market_evidence", "evidence_tools", "citations", "tool_calls", "tool_results"}:
                out[key] = []
            elif key in {"mcp_overrides", "evidence_result"}:
                out[key] = {}
            else:
                out[key] = ""

    return out


def normalize_chat_call_result(result: Any, *, request_id: str = "", conv_id: str = "") -> Dict[str, Any]:
    if isinstance(result, dict):
        out = normalize_chat_payload(result, request_id=request_id, conv_id=conv_id, event_name="final")
    else:
        out = normalize_chat_payload(
            {"response": str(result or "")},
            request_id=request_id,
            conv_id=conv_id,
            event_name="final",
        )

    if not out.get("status"):
        out["status"] = "success"
    if out.get("status") == "success" and not read_string(out, "response"):
        out["response"] = read_string(out, "message") or "已完成请求"
    return out


def build_done_payload(
    *,
    request_id: str,
    conv_id: str,
    rag_mode: str,
    mcp_overrides: Dict[str, Any],
    mode_used: str = "",
    response: str = "",
    status: str = "success",
    message: str = "done",
    citations: Optional[List[Any]] = None,
    rss_evidence: Optional[List[Any]] = None,
    market_evidence: Optional[List[Any]] = None,
    evidence_query: str = "",
    evidence_tools: Optional[List[Any]] = None,
    evidence_result: Optional[Dict[str, Any]] = None,
    qa_id: str = "",
    group_id: str = "",
    tool_calls: Optional[List[Any]] = None,
    tool_results: Optional[List[Any]] = None,
) -> Dict[str, Any]:
    final_response = str(response or "").strip()
    final_status = str(status or "success").strip() or "success"
    final_message = str(message or "").strip()

    if final_status == "success" and not final_response:
        final_response = final_message or "done"
    if final_status == "error" and not final_response:
        final_response = final_message or "stream failed"

    return {
        "request_id": str(request_id or ""),
        "conv_id": str(conv_id or ""),
        "rag_mode": str(rag_mode or ""),
        "mcp_overrides": mcp_overrides if isinstance(mcp_overrides, dict) else {},
        "mode_used": str(mode_used or ""),
        "rss_evidence": rss_evidence if isinstance(rss_evidence, list) else [],
        "market_evidence": market_evidence if isinstance(market_evidence, list) else [],
        "evidence_query": str(evidence_query or ""),
        "evidence_tools": evidence_tools if isinstance(evidence_tools, list) else [],
        "evidence_result": evidence_result if isinstance(evidence_result, dict) else {},
        "qa_id": str(qa_id or ""),
        "group_id": str(group_id or ""),
        "citations": citations if isinstance(citations, list) else [],
        "response": final_response,
        "status": final_status,
        "message": final_message,
        "tool_calls": tool_calls if isinstance(tool_calls, list) else [],
        "tool_results": tool_results if isinstance(tool_results, list) else [],
    }


async def maybe_pseudo_stream_delay(
    event_name: str,
    data: Dict[str, Any],
    *,
    enabled: bool,
    delta_delay_ms: int,
    meta_delay_ms: int,
) -> None:
    if not enabled:
        return

    ev = normalize_chat_event_name(event_name)
    delay_ms = 0

    if ev == "delta" and read_string(data, "response", "content", "text", "delta"):
        delay_ms = int(delta_delay_ms or 0)
    elif ev in {"meta", "tool_call", "tool_result"}:
        delay_ms = int(meta_delay_ms or 0)

    if delay_ms > 0:
        await anyio.sleep(delay_ms / 1000.0)


__all__ = [
    "CHAT_STREAM_TOOLS",
    "CHAT_ALLOWED_EVENTS",
    "read_std_request_id",
    "read_std_conv_id",
    "read_std_rag_mode",
    "read_std_mcp_overrides",
    "read_string",
    "read_array",
    "read_object",
    "normalize_chat_event_name",
    "normalize_chat_payload",
    "normalize_chat_call_result",
    "build_done_payload",
    "maybe_pseudo_stream_delay",
]
