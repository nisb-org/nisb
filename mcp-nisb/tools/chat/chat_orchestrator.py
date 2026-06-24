#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
nisb_chat_orchestrate
统一对话编排入口(off/cite/ground/web/auto)

兼容目标：
- 保留新的拆分结构（mode/rss/market/agent/conversation）
- 同时兼容旧代码对本模块私有 helper 的直接 import：
  _should_use_web / _pick_rss_opts / _run_agent_tools / _update_conv_meta ...
- 同时兼容新旧参数命名读取：
  conv_id/convid, request_id/requestid, rag_mode/ragmode, mcp_overrides/mcpoverrides
- direct chat(off/web) 路径只输出正式字段；legacy 字段仅保留输入兼容
- 避免 stream_runtime / 其它旧链路在 import 阶段报 ImportError
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from core.user_context import auto_user_context, get_user_ctx
from tools.chat import nisb_chat_create, nisb_chat_send
from tools.doc.analysis.qa_scope import nisb_qa_scope_ask
from tools.doc.core.dod_guard import require_safe_id

from .chat_conversation_store import (
    append_turn_record,
    find_conv_dir,
    load_conversation_meta,
    read_turn_records,
    save_conversation_meta,
)
from .chat_orchestrator_conversation import (
    _async_hebbian,
    persist_cite_ground_turns,
)
from .chat_orchestrator_mode import (
    coerce_bool as _coerce_bool,
    defaults_for_mode as _defaults_for_mode,
    ensure_request_id as _ensure_request_id,
    new_request_id as _new_request_id,
    should_use_web as _should_use_web,
)
from .chat_orchestrator_rss import (
    build_rss_evidence_items as _rss_build_evidence_items,
    build_rss_outputs as _rss_build_outputs,
    build_rss_web_citations as _rss_build_web_citations,
    is_non_english as _is_non_english,
    parse_iso_dt_rss as _parse_iso_dt_rss,
    passes_lexical_gate as _passes_lexical_gate,
    pick_rss_opts as _pick_rss_opts,
    query_terms as _query_terms,
    resolve_rss_settings as _rss_resolve_settings,
    rrf_fuse_by_url as _rrf_fuse_by_url,
    rss_feeds_json as _rss_feeds_json,
    rss_filter_items_by_days as _rss_filter_items_by_days,
    rss_pick_default_feed_ids as _rss_pick_default_feed_ids,
    rss_semantic_search_once as _rss_semantic_search_once,
    rss_within_days as _rss_within_days,
    translate_to_english_for_search as _translate_to_english_for_search,
    uid_from_user_base as _uid_from_user_base,
)
from .chat_orchestrator_market import (
    build_market_evidence_items as _market_build_evidence_items,
    market_has_any as _market_has_any,
    market_listings_jsonl as _market_listings_jsonl,
    resolve_market_settings as _market_resolve_settings,
)
from .chat_orchestrator_agent import (
    agent_answer_use_planner as _agent_answer_use_planner,
    agent_debug_enabled as _agent_debug_enabled,
    agent_enabled as _agent_enabled,
    build_agent_plan as _build_agent_plan,
    call_tool_by_name as _call_tool_by_name,
    load_mcp_tools_registry as _load_mcp_tools_registry,
    pick_answer_model as _pick_answer_model,
    run_agent_tools as _run_agent_tools,
    safe_json_dump as _safe_json_dump,
)
from . import chat_orchestrator_agent as _agent_mod


_AGENT_TOOL_ALLOWLIST = _agent_mod._AGENT_TOOL_ALLOWLIST
_AGENT_TOOL_DENYLIST = _agent_mod._AGENT_TOOL_DENYLIST
_MCP_ENTRY_FILE = _agent_mod._MCP_ENTRY_FILE
_MCP_TOOLS_CACHE = _agent_mod._MCP_TOOLS_CACHE


_LEGACY_OUTPUT_KEYS = {
    "convid",
    "requestid",
    "ragmode",
    "mcpoverrides",
    "modeused",
    "rssevidence",
    "marketevidence",
    "evidencequery",
    "evidencetools",
    "evidenceresult",
    "qaid",
    "groupid",
    "toolcalls",
    "toolresults",
    "conversation_id",
    "content",
}

_ALLOWED_RAG_MODES = {"off", "cite", "ground", "web", "auto"}


def _first_text(*values: Any) -> str:
    for value in values:
        text = str(value or "").strip()
        if text:
            return text
    return ""


def _safe_list(value: Any) -> List[Any]:
    return value if isinstance(value, list) else []


def _safe_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _looks_like_room_id(value: Any) -> bool:
    text = _first_text(value)
    return bool(text) and text.startswith("room_")


def _sanitize_conv_id_value(value: Any) -> str:
    text = _first_text(value)
    if not text:
        return ""
    if _looks_like_room_id(text):
        return ""
    return text


def _strip_invalid_conv_aliases(args: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(args or {})
    for key in ("conv_id", "convid", "conversation_id"):
        if _looks_like_room_id(out.get(key)):
            out.pop(key, None)
    return out


def _set_internal_conv_aliases(payload: Dict[str, Any], conv_id: str) -> Dict[str, Any]:
    out = dict(payload or {})
    if conv_id:
        out["conv_id"] = conv_id
        out["convid"] = conv_id
        out["conversation_id"] = conv_id
    else:
        out.pop("conv_id", None)
        out.pop("convid", None)
        out.pop("conversation_id", None)
    return out


def _get_request_id(args: Dict[str, Any]) -> str:
    if not isinstance(args, dict):
        args = {}

    try:
        _ensure_request_id(args)
    except Exception:
        pass

    request_id = _first_text(args.get("request_id"), args.get("requestid"))
    if not request_id:
        request_id = _new_request_id()

    args["request_id"] = request_id
    return request_id


def _get_conv_id(args: Dict[str, Any]) -> str:
    return _first_text(
        _sanitize_conv_id_value(args.get("conv_id")),
        _sanitize_conv_id_value(args.get("convid")),
        _sanitize_conv_id_value(args.get("conversation_id")),
    )


def _get_rag_mode(args: Dict[str, Any]) -> str:
    mode = _first_text(args.get("rag_mode"), args.get("ragmode"), "off").lower()
    if mode not in _ALLOWED_RAG_MODES:
        return "off"
    return mode


def _get_concept_language(args: Dict[str, Any]) -> str:
    return _first_text(args.get("concept_language"), args.get("conceptlanguage"), "auto")


def _get_concept_backend(args: Dict[str, Any]) -> str:
    return _first_text(args.get("concept_backend"), args.get("conceptbackend"), "auto")


def _get_dict_arg(args: Dict[str, Any], *keys: str) -> Dict[str, Any]:
    for key in keys:
        value = args.get(key)
        if isinstance(value, dict):
            return dict(value)
    return {}


def _get_str_arg(args: Dict[str, Any], keys: List[str], default: str = "") -> str:
    for key in keys:
        text = _first_text(args.get(key))
        if text:
            return text
    return str(default or "").strip()


def _get_int_arg(args: Dict[str, Any], keys: List[str], default: int) -> int:
    for key in keys:
        value = args.get(key)
        if value is None or value == "":
            continue
        try:
            return int(value)
        except Exception:
            continue
    return int(default)


def _get_optional_int_arg(args: Dict[str, Any], keys: List[str]) -> Optional[int]:
    for key in keys:
        value = args.get(key)
        if value is None or value == "":
            continue
        try:
            return int(value)
        except Exception:
            continue
    return None


def _get_optional_bool_arg(args: Dict[str, Any], keys: List[str]) -> Optional[bool]:
    for key in keys:
        if key not in args:
            continue
        value = args.get(key)
        if isinstance(value, bool):
            return value
        text = str(value or "").strip().lower()
        if text in ("true", "1", "yes", "on"):
            return True
        if text in ("false", "0", "no", "off"):
            return False
    return None


def _normalize_time_filter_days(value: Any) -> Optional[int]:
    if value is None or value == "":
        return None
    try:
        n = int(value)
    except Exception:
        return None
    return max(0, min(3650, n))


def _normalize_time_boundary(value: Any) -> Optional[str]:
    text = _first_text(value)
    if not text:
        return None

    try:
        dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except Exception:
        return None

    iso = dt.isoformat()
    if iso.endswith("+00:00"):
        iso = iso[:-6] + "Z"
    return iso


def _resolve_time_protocol(args: Dict[str, Any]) -> Dict[str, Any]:
    raw_days = _get_optional_int_arg(args, ["time_filter_days", "timefilterdays"])
    raw_start = _get_str_arg(args, ["time_start", "timestart"], "")
    raw_end = _get_str_arg(args, ["time_end", "timeend"], "")

    time_filter_days = _normalize_time_filter_days(raw_days)
    time_start = _normalize_time_boundary(raw_start)
    time_end = _normalize_time_boundary(raw_end)

    if time_start is not None or time_end is not None:
        if time_start and time_end and time_start > time_end:
            time_start, time_end = time_end, time_start
        return {
            "mode": "relative",
            "time_filter_days": None,
            "time_start": time_start,
            "time_end": time_end,
        }

    if time_filter_days is not None:
        return {
            "mode": "days",
            "time_filter_days": time_filter_days,
            "time_start": None,
            "time_end": None,
        }

    return {
        "mode": "disabled",
        "time_filter_days": None,
        "time_start": None,
        "time_end": None,
    }


def _apply_time_protocol_to_args(args: Dict[str, Any], resolved_time_scope: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(args or {})
    mode = str(resolved_time_scope.get("mode") or "").strip().lower()

    if mode == "relative":
        out.pop("time_filter_days", None)
        out.pop("timefilterdays", None)
        out["time_start"] = resolved_time_scope.get("time_start")
        out["time_end"] = resolved_time_scope.get("time_end")
        return out

    if mode == "days":
        out["time_filter_days"] = resolved_time_scope.get("time_filter_days")
        out.pop("time_start", None)
        out.pop("timestart", None)
        out.pop("time_end", None)
        out.pop("timeend", None)
        return out

    out.pop("time_filter_days", None)
    out.pop("timefilterdays", None)
    out.pop("time_start", None)
    out.pop("timestart", None)
    out.pop("time_end", None)
    out.pop("timeend", None)
    return out


def _public_time_scope_payload(resolved_time_scope: Dict[str, Any]) -> Dict[str, Any]:
    mode = str(resolved_time_scope.get("mode") or "disabled").strip().lower()
    if mode not in ("disabled", "days", "relative"):
        mode = "disabled"

    return {
        "mode": mode,
        "time_filter_days": resolved_time_scope.get("time_filter_days"),
        "time_start": resolved_time_scope.get("time_start"),
        "time_end": resolved_time_scope.get("time_end"),
    }


def _resolve_r3_min_defaults(
    *,
    effective_mode: str,
    dedupe_by_doc_id: Optional[bool],
    time_bucket_mode: str,
) -> Tuple[bool, str]:
    if effective_mode not in ("cite", "ground"):
        return bool(dedupe_by_doc_id or False), time_bucket_mode or "off"

    final_dedupe = bool(dedupe_by_doc_id) if dedupe_by_doc_id is not None else True

    final_mode = str(time_bucket_mode or "").strip().lower()
    if final_mode not in ("off", "two_phase"):
        final_mode = ""
    if not final_mode:
        final_mode = "two_phase"

    return final_dedupe, final_mode


def _get_user_id(args: Dict[str, Any], user_ctx: Any) -> str:
    return _first_text(
        args.get("user_id"),
        args.get("_user_id"),
        getattr(user_ctx, "user_id", ""),
        getattr(user_ctx, "uid", ""),
    )


def _get_user_base(args: Dict[str, Any], user_ctx: Any) -> str:
    return _first_text(
        args.get("base_path"),
        args.get("basepath"),
        args.get("_base_path"),
        getattr(user_ctx, "base", ""),
    )


def _get_token(args: Dict[str, Any], user_ctx: Any) -> str:
    return _first_text(
        args.get("token"),
        getattr(user_ctx, "token", ""),
    )


def _build_create_conv_args(args: Dict[str, Any], user_ctx: Any, request_id: str) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "title": "新对话",
        "request_id": request_id,
    }

    user_id = _get_user_id(args, user_ctx)
    user_base = _get_user_base(args, user_ctx)
    token = _get_token(args, user_ctx)

    if user_id:
        payload["user_id"] = user_id
        payload["_user_id"] = user_id

    if user_base:
        payload["base_path"] = user_base
        payload["basepath"] = user_base
        payload["_base_path"] = user_base

    if token:
        payload["token"] = token

    return payload


def _drop_legacy_output_fields(payload: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(payload or {})
    for key in _LEGACY_OUTPUT_KEYS:
        out.pop(key, None)
    return out


def _inject_ids(payload: Dict[str, Any], conv_id: str, request_id: str) -> Dict[str, Any]:
    out = dict(payload or {})
    out["conv_id"] = conv_id
    out["request_id"] = request_id
    return out


def _inject_mode(payload: Dict[str, Any], mode_used: str) -> Dict[str, Any]:
    out = dict(payload or {})
    out["mode_used"] = mode_used
    return out


def _normalize_tool_activity(payload: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(payload or {})

    tool_calls = out.get("tool_calls")
    if not isinstance(tool_calls, list):
        tool_calls = out.get("toolcalls")
    out["tool_calls"] = tool_calls if isinstance(tool_calls, list) else []

    tool_results = out.get("tool_results")
    if not isinstance(tool_results, list):
        tool_results = out.get("toolresults")
    out["tool_results"] = tool_results if isinstance(tool_results, list) else []

    return out


def _inject_evidence_aliases(payload: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(payload or {})

    citations = out.get("citations")
    if not isinstance(citations, list):
        out["citations"] = []

    rss_evidence = out.get("rss_evidence")
    if not isinstance(rss_evidence, list):
        rss_evidence = out.get("rssevidence")
    if not isinstance(rss_evidence, list):
        rss_evidence = []
    out["rss_evidence"] = rss_evidence

    market_evidence = out.get("market_evidence")
    if not isinstance(market_evidence, list):
        market_evidence = out.get("marketevidence")
    if not isinstance(market_evidence, list):
        market_evidence = []
    out["market_evidence"] = market_evidence

    evidence_query = _first_text(out.get("evidence_query"), out.get("evidencequery"))
    out["evidence_query"] = evidence_query

    evidence_tools = out.get("evidence_tools")
    if not isinstance(evidence_tools, list):
        evidence_tools = out.get("evidencetools")
    if not isinstance(evidence_tools, list):
        evidence_tools = []
    out["evidence_tools"] = evidence_tools

    evidence_result = out.get("evidence_result")
    if not isinstance(evidence_result, dict):
        evidence_result = out.get("evidenceresult")
    if not isinstance(evidence_result, dict):
        evidence_result = {}
    out["evidence_result"] = evidence_result

    qa_id = _first_text(out.get("qa_id"), out.get("qaid"))
    out["qa_id"] = qa_id

    group_id = _first_text(out.get("group_id"), out.get("groupid"))
    out["group_id"] = group_id

    return out


def _normalize_success_response(status: str, response: str, message: str) -> str:
    res = str(response or "").strip()
    if res:
        return res
    if str(status or "").strip().lower() == "success":
        msg = str(message or "").strip()
        if msg:
            return msg
        return "已完成请求，但未生成可展示回复。"
    return ""


def _normalize_result(
    payload: Dict[str, Any],
    conv_id: str,
    request_id: str,
    mode_used: str,
    *,
    rag_mode: str = "",
    mcp_overrides: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    out = dict(payload or {})

    original_params = out.get("params")
    original_qa_params = out.get("qa_params")

    if not _first_text(out.get("response")):
        out["response"] = _first_text(out.get("content"))

    out = _inject_ids(out, conv_id, request_id)
    out = _inject_mode(out, mode_used)
    out = _inject_evidence_aliases(out)
    out = _normalize_tool_activity(out)

    if rag_mode:
        out["rag_mode"] = rag_mode
    elif not _first_text(out.get("rag_mode"), out.get("ragmode")):
        out["rag_mode"] = mode_used or "off"
    else:
        out["rag_mode"] = _first_text(out.get("rag_mode"), out.get("ragmode")).lower()

    if out["rag_mode"] not in _ALLOWED_RAG_MODES:
        out["rag_mode"] = "off"

    if isinstance(mcp_overrides, dict):
        out["mcp_overrides"] = dict(mcp_overrides)
    elif not isinstance(out.get("mcp_overrides"), dict):
        legacy = out.get("mcpoverrides")
        out["mcp_overrides"] = dict(legacy) if isinstance(legacy, dict) else {}

    if "status" not in out:
        out["status"] = "success"
    if "message" not in out:
        out["message"] = ""
    if "qa_id" not in out:
        out["qa_id"] = ""
    if "group_id" not in out:
        out["group_id"] = ""
    if "citations" not in out or not isinstance(out.get("citations"), list):
        out["citations"] = []
    if "rss_evidence" not in out or not isinstance(out.get("rss_evidence"), list):
        out["rss_evidence"] = []
    if "market_evidence" not in out or not isinstance(out.get("market_evidence"), list):
        out["market_evidence"] = []
    if "evidence_query" not in out:
        out["evidence_query"] = ""
    if "evidence_tools" not in out or not isinstance(out.get("evidence_tools"), list):
        out["evidence_tools"] = []
    if "evidence_result" not in out or not isinstance(out.get("evidence_result"), dict):
        out["evidence_result"] = {}
    if not isinstance(out.get("tool_calls"), list):
        out["tool_calls"] = []
    if not isinstance(out.get("tool_results"), list):
        out["tool_results"] = []
    if not isinstance(out.get("mcp_overrides"), dict):
        out["mcp_overrides"] = {}

    out["response"] = _normalize_success_response(
        str(out.get("status") or ""),
        _first_text(out.get("response")),
        _first_text(out.get("message")),
    )

    normalized = _drop_legacy_output_fields(out)

    if not isinstance(normalized, dict):
        normalized = {}

    final_params = normalized.get("params")
    final_qa_params = normalized.get("qa_params")

    if not isinstance(final_params, dict):
        if isinstance(original_params, dict):
            normalized["params"] = original_params
        elif isinstance(final_qa_params, dict):
            normalized["params"] = final_qa_params
        elif isinstance(original_qa_params, dict):
            normalized["params"] = original_qa_params

    if not isinstance(final_qa_params, dict):
        if isinstance(original_qa_params, dict):
            normalized["qa_params"] = original_qa_params
        elif isinstance(normalized.get("params"), dict):
            normalized["qa_params"] = normalized["params"]
        elif isinstance(original_params, dict):
            normalized["qa_params"] = original_params

    return normalized


def _find_conv_dir(user_base: str, conv_id: str) -> Optional[Path]:
    return find_conv_dir(user_base, conv_id)


def _read_turns(conv_dir: Path) -> List[dict]:
    return read_turn_records(conv_dir)


def _append_turn(conv_dir: Path, turn: dict) -> None:
    append_turn_record(conv_dir, turn)


def _update_conv_meta(conv_dir: Path, turn_count: int) -> None:
    meta = load_conversation_meta(conv_dir)
    meta["turn_count"] = int(turn_count)
    meta["last_updated"] = datetime.now().isoformat()
    if "labels" not in meta or not isinstance(meta.get("labels"), list):
        meta["labels"] = []
    save_conversation_meta(conv_dir, meta)


def _normalize_rss_payload(
    args: Dict[str, Any],
    *,
    enabled: bool,
    resolved_time_scope: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    rss_payload = args.get("rss")
    rss_opts = _pick_rss_opts(args)
    out = dict(rss_payload) if isinstance(rss_payload, dict) else {}

    out["enabled"] = bool(out.get("enabled", enabled))
    out["limit"] = int(rss_opts.get("limit") or out.get("limit") or 8)
    out["minscore"] = float(rss_opts.get("minscore") or out.get("minscore") or 0.28)
    out["strict_lexical"] = bool(rss_opts.get("strict_lexical", out.get("strict_lexical", True)))

    rss_days = None
    raw_rss_days = args.get("rss_days")
    if raw_rss_days is None:
        raw_rss_days = args.get("rssdays")
    if raw_rss_days is None:
        raw_rss_days = out.get("days")
    if raw_rss_days is not None and raw_rss_days != "":
        try:
            rss_days = max(0, min(3650, int(raw_rss_days)))
        except Exception:
            rss_days = None

    if rss_days is not None:
        out["days"] = rss_days
        out.pop("start_date", None)
        out.pop("end_date", None)
        out.pop("date_from", None)
        out.pop("date_to", None)
        return out

    start_date = _first_text(rss_opts.get("start_date"), out.get("start_date"), out.get("date_from"))
    end_date = _first_text(rss_opts.get("end_date"), out.get("end_date"), out.get("date_to"))

    if start_date:
        out["start_date"] = start_date
        out["date_from"] = start_date
    else:
        out.pop("start_date", None)
        out.pop("date_from", None)

    if end_date:
        out["end_date"] = end_date
        out["date_to"] = end_date
    else:
        out.pop("end_date", None)
        out.pop("date_to", None)

    out["days"] = int(rss_opts.get("days") or out.get("days") or 0)
    return out

def _build_rss_outputs_safe(
    *,
    user_base: str,
    feed_ids: List[str],
    query_text: str,
    rss_max_citations: int,
    payload: Dict[str, Any],
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    try:
        bundle = _rss_build_outputs(
            user_base=user_base,
            feed_ids=feed_ids,
            query_text=query_text,
            citations_limit_total=rss_max_citations,
            evidence_limit_total=max(6, rss_max_citations),
            payload=payload,
        )
    except Exception as ex:
        print("RSS_LIVE_BUILD_ERROR", f"{type(ex).__name__}: {ex}")
        return [], []

    citations = bundle.get("citations")
    if not isinstance(citations, list):
        citations = []

    rss_evidence = bundle.get("rss_evidence")
    if not isinstance(rss_evidence, list):
        rss_evidence = []

    return list(citations), list(rss_evidence)


def _should_attach_live_rss_outputs(
    *,
    effective_mode: str,
    library_id: Optional[str],
    doc_id: Optional[str],
    group_id: Optional[str],
) -> bool:
    if effective_mode in ("off", "web", "cite", "ground"):
        return True
    return False


def _build_qa_debug_payload(
    qa: Dict[str, Any],
    qa_res: Dict[str, Any],
    *,
    orchestrator_time_scope: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    qa_debug = qa.get("debug")
    if not isinstance(qa_debug, dict):
        qa_debug = {}

    qa_res_debug = qa_res.get("debug")
    if not isinstance(qa_res_debug, dict):
        qa_res_debug = {}

    def _pick_dict(key: str) -> Dict[str, Any]:
        v = qa_debug.get(key)
        if isinstance(v, dict):
            return v
        v = qa_res_debug.get(key)
        if isinstance(v, dict):
            return v
        return {}

    citations_count = qa_debug.get("citations_count")
    if citations_count is None:
        citations_count = qa_res_debug.get("citations_count")
    try:
        citations_count = int(citations_count or 0)
    except Exception:
        citations_count = 0

    return {
        "orchestrator_time_scope": _public_time_scope_payload(orchestrator_time_scope or {}),
        "doc_time_scope_args": _pick_dict("doc_time_scope_args"),
        "retrieval_time_scope": _pick_dict("retrieval_time_scope"),
        "doc_time_filter": _pick_dict("doc_time_filter"),
        "evidence_scope_args": _pick_dict("evidence_scope_args"),
        "evidence_scope_debug": _pick_dict("evidence_scope_debug"),
        "r3_min_selection": _pick_dict("r3_min_selection"),
        "r3_min_backfill": _pick_dict("r3_min_backfill"),
        "r3_visible_bucket": _pick_dict("r3_visible_bucket"),
        "evidence_published_at": _pick_dict("evidence_published_at"),
        "citations_count": citations_count,
        "qa_has_debug": bool(qa_debug),
        "qa_res_has_debug": bool(qa_res_debug),
    }


def _build_qa_params_payload(qa: Dict[str, Any], qa_res: Dict[str, Any]) -> Dict[str, Any]:
    src = qa_res.get("params")
    if not isinstance(src, dict):
        src = qa.get("params")
    if not isinstance(src, dict):
        src = {}

    return {
        "r3_min_enabled": bool(src.get("r3_min_enabled")),
        "r3_min_dedupe_by_doc_id": bool(src.get("r3_min_dedupe_by_doc_id")),
        "r3_min_time_bucket_mode": str(src.get("r3_min_time_bucket_mode") or ""),
        "time_filter_days": src.get("time_filter_days"),
        "time_start": src.get("time_start"),
        "time_end": src.get("time_end"),
    }


def _build_qa_evidence_public(qa: Dict[str, Any], qa_res: Dict[str, Any]) -> List[Dict[str, Any]]:
    items = qa_res.get("qa_evidence")
    if not isinstance(items, list):
        items = qa.get("evidence")
    if not isinstance(items, list):
        items = []

    out: List[Dict[str, Any]] = []
    for it in items:
        if not isinstance(it, dict):
            continue
        out.append(
            {
                "library_id": it.get("library_id"),
                "doc_id": it.get("doc_id"),
                "span_index": it.get("span_index"),
                "relevance": it.get("relevance"),
                "published_at": it.get("published_at"),
                "published_at_source": it.get("published_at_source"),
                "doc_title": it.get("doc_title"),
                "time_bucket": it.get("time_bucket"),
                "time_bucket_boundary": it.get("time_bucket_boundary"),
            }
        )
    return out


@auto_user_context
def nisb_chat_orchestrate(args: Dict[str, Any]) -> Dict[str, Any]:
    args = _strip_invalid_conv_aliases(dict(args or {}))
    user_ctx = get_user_ctx()
    request_id = _get_request_id(args)

    resolved_time_scope = _resolve_time_protocol(args)
    args = _apply_time_protocol_to_args(args, resolved_time_scope)

    user_id = _get_user_id(args, user_ctx)
    user_base = _get_user_base(args, user_ctx)
    token = _get_token(args, user_ctx)

    if user_id:
        args["user_id"] = user_id
        args["_user_id"] = user_id

    if user_base:
        args["base_path"] = user_base
        args["basepath"] = user_base
        args["_base_path"] = user_base

    if token:
        args["token"] = token

    tool_policy_snapshot = {
        "capability_gate": _get_dict_arg(args, "capability_gate", "capabilitygate"),
        "mcp_overrides": _get_dict_arg(args, "mcp_overrides", "mcpoverrides"),
    }

    conv_id = _get_conv_id(args)
    if conv_id and user_base:
        try:
            if _find_conv_dir(user_base, conv_id) is None:
                conv_id = ""
        except Exception:
            conv_id = ""

    base_user_content = _first_text(args.get("content"))
    content = base_user_content

    top_model = _first_text(args.get("model"), "gpt-4o-mini") or "gpt-4o-mini"
    qa_model = "gpt-4o-mini" if top_model.startswith("claude") else top_model

    rag_mode = _get_rag_mode(args)
    concept_language = _get_concept_language(args)
    concept_backend = _get_concept_backend(args)

    if not content:
        return _normalize_result(
            {
                "status": "error",
                "message": "content 不能为空",
            },
            conv_id,
            request_id,
            rag_mode or "off",
            rag_mode=rag_mode,
            mcp_overrides=tool_policy_snapshot["mcp_overrides"],
        )

    if not conv_id:
        created = nisb_chat_create(_build_create_conv_args(args, user_ctx, request_id))
        if not isinstance(created, dict) or created.get("status") != "success":
            return _normalize_result(
                {
                    "status": "error",
                    "message": (created.get("message") if isinstance(created, dict) else "create conversation failed"),
                },
                "",
                request_id,
                rag_mode,
                rag_mode=rag_mode,
                mcp_overrides=tool_policy_snapshot["mcp_overrides"],
            )

        conv_id = _first_text(
            created.get("conv_id") if isinstance(created, dict) else "",
            created.get("convid") if isinstance(created, dict) else "",
            created.get("conversation_id") if isinstance(created, dict) else "",
        )

        if not conv_id:
            return _normalize_result(
                {
                    "status": "error",
                    "message": "create conversation succeeded but conv_id missing",
                },
                "",
                request_id,
                rag_mode,
                rag_mode=rag_mode,
                mcp_overrides=tool_policy_snapshot["mcp_overrides"],
            )

    args = _set_internal_conv_aliases(args, conv_id)
    args["request_id"] = request_id
    args["rag_mode"] = rag_mode
    args["mcp_overrides"] = tool_policy_snapshot["mcp_overrides"]

    effective_mode = rag_mode
    if rag_mode == "auto":
        effective_mode = "web" if _should_use_web(content) else "off"

    context_library_id = _get_str_arg(args, ["library_id", "libraryid"], "") or None
    context_doc_id = _get_str_arg(args, ["doc_id", "docid"], "") or None
    context_group_id = _get_str_arg(args, ["group_id", "groupid"], "") or None

    attach_live_rss_outputs = _should_attach_live_rss_outputs(
        effective_mode=effective_mode,
        library_id=context_library_id,
        doc_id=context_doc_id,
        group_id=context_group_id,
    )

    print(
        f"[RSS_ATTACH_DEBUG] mode={effective_mode} library_id={context_library_id or ''} "
        f"doc_id={context_doc_id or ''} group_id={context_group_id or ''} "
        f"attach_live_rss_outputs={attach_live_rss_outputs}"
    )
    print(
        f"[TIME_SCOPE_DEBUG] mode={resolved_time_scope.get('mode')} "
        f"time_filter_days={resolved_time_scope.get('time_filter_days')} "
        f"time_start={resolved_time_scope.get('time_start')} "
        f"time_end={resolved_time_scope.get('time_end')}"
    )

    rss_enabled, rss_feed_ids, rss_max_citations = _rss_resolve_settings(
        args=args,
        effective_mode=effective_mode,
        user_base=user_ctx.base,
    )
    normalized_rss_payload = _normalize_rss_payload(
        args,
        enabled=bool(rss_enabled),
        resolved_time_scope=resolved_time_scope,
    )

    market_enabled, peer_targets, market_max_evidence = _market_resolve_settings(
        args=args,
        effective_mode=effective_mode,
        user_base=user_ctx.base,
    )

    agent_trace: Optional[Dict[str, Any]] = None
    if _agent_enabled(args):
        obs_text, trace = _run_agent_tools(
            args={**args, "content": content},
            effective_mode=effective_mode,
        )
        agent_trace = trace
        obs_text = str(obs_text or "").strip()
        if obs_text:
            content = f"{content}\n\n{obs_text}".strip()

    if effective_mode in ("off", "web"):
        mcp_overrides = _get_dict_arg(args, "mcp_overrides", "mcpoverrides")
        if effective_mode == "web":
            mcp_overrides = {**mcp_overrides, "serper_enabled": True}

        answer_model = _pick_answer_model(
            top_model=top_model,
            effective_mode=effective_mode,
            args=args,
        )

        send_args = _set_internal_conv_aliases(
            {
                **args,
                "request_id": request_id,
                "content": content,
                "model": answer_model,
                "rag_mode": effective_mode,
                "mcp_overrides": mcp_overrides,
                "attachments": list(args.get("attachments")) if isinstance(args.get("attachments"), list) else [],
            },
            conv_id,
        )

        res = nisb_chat_send(send_args)

        if isinstance(res, dict) and res.get("status") == "success":
            base_citations = res.get("citations")
            citations: List[Dict[str, Any]] = list(base_citations) if isinstance(base_citations, list) else []
            rss_evidence: List[Dict[str, Any]] = []
            market_evidence: List[Dict[str, Any]] = []

            if rss_enabled and attach_live_rss_outputs:
                rss_citations, rss_evidence = _build_rss_outputs_safe(
                    user_base=user_ctx.base,
                    feed_ids=rss_feed_ids,
                    query_text=base_user_content,
                    rss_max_citations=rss_max_citations,
                    payload={**args, "rss": normalized_rss_payload},
                )
                citations.extend(rss_citations)

            if market_enabled:
                try:
                    market_evidence.extend(
                        _market_build_evidence_items(
                            user_base=user_ctx.base,
                            query_text=base_user_content,
                            limit_total=market_max_evidence,
                            peer_targets=peer_targets,
                        )
                    )
                except Exception:
                    pass

            out = _normalize_result(
                {
                    "status": "success",
                    "response": str(res.get("response") or res.get("content") or ""),
                    "message": "✅ Web 模式:已强制开启 Serper 搜索" if effective_mode == "web" else "✅ Off 模式:已走 nisb_chat_send",
                    "citations": citations,
                    "rss_evidence": rss_evidence,
                    "market_evidence": market_evidence,
                    "evidence_query": base_user_content,
                    "evidence_tools": res.get("evidence_tools") if isinstance(res.get("evidence_tools"), list) else [],
                    "evidence_result": res.get("evidence_result") if isinstance(res.get("evidence_result"), dict) else {},
                    "qa_id": _first_text(res.get("qa_id"), res.get("qaid")),
                    "group_id": _first_text(res.get("group_id"), res.get("groupid")),
                    "tool_calls": res.get("tool_calls") if isinstance(res.get("tool_calls"), list) else res.get("toolcalls"),
                    "tool_results": res.get("tool_results") if isinstance(res.get("tool_results"), list) else res.get("toolresults"),
                },
                conv_id,
                request_id,
                effective_mode,
                rag_mode=rag_mode,
                mcp_overrides=mcp_overrides,
            )
            if _agent_debug_enabled(args) and agent_trace is not None:
                out["agent_trace"] = agent_trace
            return out

        if isinstance(res, dict):
            out = _normalize_result(
                res,
                conv_id,
                request_id,
                effective_mode,
                rag_mode=rag_mode,
                mcp_overrides=mcp_overrides,
            )
            if _agent_debug_enabled(args) and agent_trace is not None and "agent_trace" not in out:
                out["agent_trace"] = agent_trace
            return out

        out = _normalize_result(
            {
                "status": "error",
                "message": str(res),
            },
            conv_id,
            request_id,
            effective_mode,
            rag_mode=rag_mode,
            mcp_overrides=mcp_overrides,
        )
        if _agent_debug_enabled(args) and agent_trace is not None:
            out["agent_trace"] = agent_trace
        return out

    qa_store_scope = _get_str_arg(args, ["qa_store_scope", "qastorescope"], "global").lower()
    qa_evidence_scope = _get_str_arg(args, ["qa_evidence_scope", "qaevidencescope"], "global").lower()

    if qa_store_scope not in ("doc", "library", "global"):
        qa_store_scope = "global"
    if qa_evidence_scope not in ("doc", "library", "global"):
        qa_evidence_scope = "global"

    library_id = context_library_id
    doc_id = context_doc_id

    group_id = context_group_id
    if group_id:
        try:
            group_id = require_safe_id("group_id", group_id)
        except Exception as e:
            out_err = _normalize_result(
                {
                    "status": "error",
                    "message": f"group_id 非法: {e}",
                },
                conv_id,
                request_id,
                effective_mode,
                rag_mode=rag_mode,
                mcp_overrides=tool_policy_snapshot["mcp_overrides"],
            )
            if _agent_debug_enabled(args) and agent_trace is not None:
                out_err["agent_trace"] = agent_trace
            return out_err

    defaults = _defaults_for_mode(effective_mode)
    top_k = _get_int_arg(args, ["qa_top_k", "qatopk"], int(defaults.get("top_k") or 18))
    max_evidence = _get_int_arg(args, ["qa_max_evidence", "qamaxevidence"], int(defaults.get("max_evidence") or 14))
    min_citations = _get_int_arg(args, ["qa_min_citations", "qamincitations"], int(defaults.get("min_citations") or 4))
    max_citations = _get_int_arg(args, ["qa_max_citations", "qamaxcitations"], int(defaults.get("max_citations") or 12))
    max_output_tokens = _get_int_arg(args, ["qa_max_output_tokens", "qamaxoutputtokens"], int(defaults.get("max_output_tokens") or 2200))
    answer_lang = _get_str_arg(args, ["qa_answer_lang", "qaanswerlang"], "zh") or "zh"

    raw_dedupe_by_doc_id = _get_optional_bool_arg(
        args,
        ["dedupe_by_doc_id", "dedupeByDocId", "qa_dedupe_by_doc_id", "qadedupebydocid"],
    )
    raw_time_bucket_mode = _get_str_arg(
        args,
        ["time_bucket_mode", "timeBucketMode", "qa_time_bucket_mode", "qatimebucketmode"],
        "",
    ).lower()

    dedupe_by_doc_id, time_bucket_mode = _resolve_r3_min_defaults(
        effective_mode=effective_mode,
        dedupe_by_doc_id=raw_dedupe_by_doc_id,
        time_bucket_mode=raw_time_bucket_mode,
    )

    qa_args: Dict[str, Any] = {
        "question": content,
        "store_scope": qa_store_scope,
        "evidence_scope": qa_evidence_scope,
        "top_k": top_k,
        "max_evidence": max_evidence,
        "min_citations": min_citations,
        "max_citations": max_citations,
        "max_output_tokens": max_output_tokens,
        "model": qa_model,
        "answer_lang": answer_lang,
        "dedupe_by_doc_id": dedupe_by_doc_id,
        "time_bucket_mode": time_bucket_mode,
    }

    if library_id:
        qa_args["library_id"] = library_id
    if doc_id:
        qa_args["doc_id"] = doc_id
    if group_id:
        qa_args["group_id"] = group_id

    if resolved_time_scope.get("mode") == "days":
        qa_args["time_filter_days"] = resolved_time_scope.get("time_filter_days")
    elif resolved_time_scope.get("mode") == "relative":
        if resolved_time_scope.get("time_start"):
            qa_args["time_start"] = resolved_time_scope.get("time_start")
        if resolved_time_scope.get("time_end"):
            qa_args["time_end"] = resolved_time_scope.get("time_end")

    qa_args["rss"] = normalized_rss_payload

    qa_call_args = _set_internal_conv_aliases(
        {
            **args,
            **qa_args,
            "request_id": request_id,
        },
        conv_id,
    )

    qa_res = nisb_qa_scope_ask(qa_call_args)

    if not isinstance(qa_res, dict) or qa_res.get("status") != "success":
        out_err = _normalize_result(
            {
                "status": "error",
                "message": (qa_res.get("message") if isinstance(qa_res, dict) else "qa_scope_ask failed"),
            },
            conv_id,
            request_id,
            effective_mode,
            rag_mode=rag_mode,
            mcp_overrides=tool_policy_snapshot["mcp_overrides"],
        )
        if _agent_debug_enabled(args) and agent_trace is not None:
            out_err["agent_trace"] = agent_trace
        return out_err

    qa = qa_res.get("qa") or {}
    if not isinstance(qa, dict):
        qa = {}

    answer = _first_text(
        qa.get("answer"),
        qa.get("response"),
        qa.get("final_answer"),
        qa_res.get("response"),
        qa_res.get("answer"),
        qa_res.get("final_answer"),
    )

    qa_citations = qa.get("citations")
    if not isinstance(qa_citations, list):
        qa_citations = qa_res.get("citations")
    citations: List[Dict[str, Any]] = list(qa_citations) if isinstance(qa_citations, list) else []

    qa_evidence = qa.get("evidence")
    qa_evidence_count = len(qa_evidence) if isinstance(qa_evidence, list) else 0

    rss_evidence: List[Dict[str, Any]] = []
    market_evidence: List[Dict[str, Any]] = []

    if rss_enabled and attach_live_rss_outputs:
        rss_citations, rss_evidence = _build_rss_outputs_safe(
            user_base=user_ctx.base,
            feed_ids=rss_feed_ids,
            query_text=base_user_content,
            rss_max_citations=rss_max_citations,
            payload={**args, "rss": normalized_rss_payload},
        )
        citations.extend(rss_citations)

    if market_enabled:
        try:
            market_evidence.extend(
                _market_build_evidence_items(
                    user_base=user_ctx.base,
                    query_text=base_user_content,
                    limit_total=market_max_evidence,
                    peer_targets=peer_targets,
                )
            )
        except Exception:
            pass

    if not answer:
        if qa_evidence_count > 0 or citations or rss_evidence or market_evidence:
            answer = (
                "已检索到相关证据，但当前未成功生成最终回答。"
                "请缩小到更具体的库、分组或文档后重试。"
            )
        else:
            answer = (
                "当前知识范围内未检索到可用证据。"
                "请检查库/分组/文档范围，或把问题描述得更具体一些。"
            )

    persist_res = persist_cite_ground_turns(
        user_base=user_ctx.base,
        conv_id=conv_id,
        request_id=request_id,
        effective_mode=effective_mode,
        base_user_content=base_user_content,
        answer=answer,
        qa_model=qa_model,
        citations=citations,
        rss_evidence=rss_evidence,
        market_evidence=market_evidence,
        qa=qa,
        tool_policy_snapshot=tool_policy_snapshot,
        agent_trace=agent_trace,
        concept_language=concept_language,
        concept_backend=concept_backend,
    )

    if not isinstance(persist_res, dict) or persist_res.get("status") != "success":
        out_err = _normalize_result(
            {
                "status": "error",
                "message": (
                    persist_res.get("message")
                    if isinstance(persist_res, dict)
                    else "persist conversation failed"
                ),
            },
            conv_id,
            request_id,
            effective_mode,
            rag_mode=rag_mode,
            mcp_overrides=tool_policy_snapshot["mcp_overrides"],
        )
        if _agent_debug_enabled(args) and agent_trace is not None:
            out_err["agent_trace"] = agent_trace
        return out_err

    evidence_result = persist_res.get("evidence_result")
    if not isinstance(evidence_result, dict):
        evidence_result = {}

    qa_id = _first_text(
        qa.get("qa_id"),
        qa.get("qaid"),
        qa_res.get("qa_id"),
        qa_res.get("qaid"),
    )

    qa_meta = qa_res.get("qa_meta")
    if not isinstance(qa_meta, dict):
        qa_meta = {
            "qa_id": qa_id,
            "thread_id": _first_text(qa.get("thread_id")),
            "store_scope": _first_text(qa.get("store_scope"), qa_args.get("store_scope")),
            "evidence_scope": _first_text(qa.get("evidence_scope"), qa_args.get("evidence_scope")),
            "library_id": _first_text(qa.get("library_id"), library_id or ""),
            "doc_id": _first_text(qa.get("doc_id"), doc_id or ""),
            "evidence_count": qa_evidence_count,
            "citations_count": len(citations),
        }

    qa_debug_payload = _build_qa_debug_payload(
        qa,
        qa_res,
        orchestrator_time_scope=resolved_time_scope,
    )
    qa_params_payload = _build_qa_params_payload(qa, qa_res)
    qa_evidence_public = _build_qa_evidence_public(qa, qa_res)

    evidence_result = {
        **evidence_result,
        "qa_meta": qa_meta,
        "qa_response_empty": not bool(str(answer or "").strip()),
        "qa_debug": qa_debug_payload,
        "qa_params": qa_params_payload,
        "qa_evidence": qa_evidence_public,
    }

    success_message = "✅ 已生成带引用回答,并写入对话记录"
    if not citations:
        if qa_evidence_count > 0 or rss_evidence or market_evidence:
            success_message = "⚠️ 已生成回答，但当前未形成正式 citations；已写入对话记录"
        else:
            success_message = "⚠️ 当前知识范围内未检索到可用证据，已返回范围提示并写入对话记录"

    out_ok = _normalize_result(
        {
            "status": "success",
            "response": answer,
            "citations": citations,
            "rss_evidence": rss_evidence,
            "market_evidence": market_evidence,
            "qa_id": qa_id,
            "qa_meta": qa_meta,
            "qa_debug": qa_debug_payload,
            "qa_evidence": qa_evidence_public,
            "params": qa_params_payload,
            "qa_params": qa_params_payload,
            "group_id": group_id or "",
            "message": success_message,
            "evidence_query": base_user_content,
            "evidence_tools": ["nisb_qa_scope_ask"],
            "evidence_result": evidence_result,
            "tool_calls": [],
            "tool_results": [],
        },
        conv_id,
        request_id,
        effective_mode,
        rag_mode=rag_mode,
        mcp_overrides=tool_policy_snapshot["mcp_overrides"],
    )
    if _agent_debug_enabled(args) and agent_trace is not None:
        out_ok["agent_trace"] = agent_trace

    print("FINAL_OUT_KEYS", sorted(list(out_ok.keys())))
    print("FINAL_OUT_HAS_PARAMS", "params" in out_ok, "qa_params" in out_ok)

    return out_ok


__all__ = [
    "nisb_chat_orchestrate",
    "_AGENT_TOOL_ALLOWLIST",
    "_AGENT_TOOL_DENYLIST",
    "_MCP_ENTRY_FILE",
    "_MCP_TOOLS_CACHE",
    "_find_conv_dir",
    "_read_turns",
    "_append_turn",
    "_update_conv_meta",
    "_should_use_web",
    "_pick_rss_opts",
    "_run_agent_tools",
    "_coerce_bool",
    "_defaults_for_mode",
    "_ensure_request_id",
    "_new_request_id",
    "_rss_build_evidence_items",
    "_rss_build_web_citations",
    "_is_non_english",
    "_parse_iso_dt_rss",
    "_passes_lexical_gate",
    "_query_terms",
    "_rss_resolve_settings",
    "_rrf_fuse_by_url",
    "_rss_feeds_json",
    "_rss_filter_items_by_days",
    "_rss_pick_default_feed_ids",
    "_rss_semantic_search_once",
    "_rss_within_days",
    "_translate_to_english_for_search",
    "_uid_from_user_base",
    "_market_build_evidence_items",
    "_market_has_any",
    "_market_listings_jsonl",
    "_market_resolve_settings",
    "_agent_answer_use_planner",
    "_agent_debug_enabled",
    "_agent_enabled",
    "_build_agent_plan",
    "_call_tool_by_name",
    "_load_mcp_tools_registry",
    "_pick_answer_model",
    "_safe_json_dump",
    "_async_hebbian",
]

