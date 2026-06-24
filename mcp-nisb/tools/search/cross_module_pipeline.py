#!/usr/bin/env python3

import time
import uuid
from pathlib import Path
from typing import Any, Dict, Mapping, Optional, Sequence

from .common import analyze_search_query
from .cross_module_helpers import (
    _coerce_bool,
    _coerce_int,
    _empty_payload,
    _expand_raw_modules,
    _extract_mapping,
    _first_non_empty,
    _is_path_like_query,
    _is_probable_filename_query,
    _normalize_modules,
)
from .index_sync_fs import quick_sync_file_module


class _TraceSpan:
    def __init__(self, trace: "SearchTrace", name: str):
        self.trace = trace
        self.name = str(name)
        self.started = 0.0

    def __enter__(self):
        self.started = time.time()
        return self

    def __exit__(self, exc_type, exc, tb):
        elapsed_ms = int((time.time() - self.started) * 1000)
        self.trace.add_ms(self.name, elapsed_ms)
        return False


class SearchTrace:
    def __init__(self):
        self.started = time.time()
        self.stage_ms: Dict[str, int] = {}

    def measure(self, name: str) -> _TraceSpan:
        return _TraceSpan(self, name)

    def set_ms(self, name: str, value: int) -> None:
        self.stage_ms[str(name)] = max(0, int(value or 0))

    def add_ms(self, name: str, value: int) -> None:
        key = str(name)
        self.stage_ms[key] = int(self.stage_ms.get(key, 0) or 0) + max(0, int(value or 0))

    def elapsed_ms(self) -> int:
        return int((time.time() - self.started) * 1000)

    def snapshot(self) -> Dict[str, Any]:
        open_ms = int(self.stage_ms.get("open", 0) or 0)
        sync_ms = int(self.stage_ms.get("sync", 0) or 0)
        query_ms = int(self.stage_ms.get("query", 0) or 0)
        merge_ms = int(self.stage_ms.get("merge", 0) or 0)
        finalize_ms = int(self.stage_ms.get("finalize", 0) or 0)
        total_ms = self.elapsed_ms()

        phase_elapsed_ms = {
            "open": open_ms,
            "sync": sync_ms,
            "query": query_ms,
            "merge": merge_ms,
            "finalize": finalize_ms,
            "total": total_ms,
        }

        return {
            "open_elapsed_ms": open_ms,
            "sync_elapsed_ms": sync_ms,
            "query_elapsed_ms": query_ms,
            "merge_elapsed_ms": merge_ms,
            "finalize_elapsed_ms": finalize_ms,
            "total_elapsed_ms": total_ms,
            "phase_elapsed_ms": phase_elapsed_ms,
        }


def _build_query_guard(raw_query: str) -> Dict[str, Any]:
    guard = analyze_search_query(raw_query)
    return {
        "raw_query": str(guard.get("raw_query") or raw_query or ""),
        "raw_query_used": str(guard.get("raw_query_used") or raw_query or ""),
        "query_norm": str(guard.get("query_norm") or ""),
        "query_compact": str(guard.get("query_compact") or ""),
        "query_tokens": list(guard.get("query_tokens") or []),
        "query_tokens_used": list(guard.get("query_tokens_used") or []),
        "query_tokens_score": list(guard.get("query_tokens_score") or []),
        "query_tokens_fts": list(guard.get("query_tokens_fts") or []),
        "query_chars_raw": int(guard.get("query_chars_raw") or 0),
        "query_chars_used": int(guard.get("query_chars_used") or 0),
        "compact_len_raw": int(guard.get("compact_len_raw") or 0),
        "compact_len_used": int(guard.get("compact_len_used") or 0),
        "token_count_raw": int(guard.get("token_count_raw") or 0),
        "token_count_used": int(guard.get("token_count_used") or 0),
        "token_count_score": int(guard.get("token_count_score") or 0),
        "token_count_fts": int(guard.get("token_count_fts") or 0),
        "symbol_ratio": float(guard.get("symbol_ratio") or 0.0),
        "symbol_heavy": bool(guard.get("symbol_heavy") or False),
        "natural_language": bool(guard.get("natural_language") or False),
        "filenameish": bool(guard.get("filenameish") or False),
        "path_like": bool(guard.get("path_like") or False),
        "oversized": bool(guard.get("oversized") or False),
        "truncated": bool(guard.get("truncated") or False),
        "token_capped": bool(guard.get("token_capped") or False),
        "compact_capped": bool(guard.get("compact_capped") or False),
        "query_class": str(guard.get("query_class") or ""),
        "allow_title_fts": bool(guard.get("allow_title_fts") or False),
        "allow_content_fts": bool(guard.get("allow_content_fts") or False),
        "allow_direct_content_like": bool(guard.get("allow_direct_content_like") or False),
        "degraded": bool(guard.get("degraded") or False),
        "degrade_reasons": list(guard.get("degrade_reasons") or []),
        "guard_reason": str(guard.get("guard_reason") or ""),
    }


def _build_evidence_query(
    raw_query: str,
    logical_modules,
    raw_modules,
    query_guard: Dict[str, Any],
) -> Dict[str, Any]:
    return {
        "raw_query": raw_query,
        "raw_query_used": str(query_guard.get("raw_query_used") or raw_query or ""),
        "query_norm": str(query_guard.get("query_norm") or ""),
        "query_compact": str(query_guard.get("query_compact") or ""),
        "query_tokens": list(query_guard.get("query_tokens_used") or []),
        "query_tokens_fts": list(query_guard.get("query_tokens_fts") or []),
        "query_class": str(query_guard.get("query_class") or ""),
        "query_chars_raw": int(query_guard.get("query_chars_raw") or 0),
        "query_chars_used": int(query_guard.get("query_chars_used") or 0),
        "compact_len_raw": int(query_guard.get("compact_len_raw") or 0),
        "compact_len_used": int(query_guard.get("compact_len_used") or 0),
        "token_count_raw": int(query_guard.get("token_count_raw") or 0),
        "token_count_used": int(query_guard.get("token_count_used") or 0),
        "token_count_fts": int(query_guard.get("token_count_fts") or 0),
        "symbol_ratio": float(query_guard.get("symbol_ratio") or 0.0),
        "symbol_heavy": bool(query_guard.get("symbol_heavy") or False),
        "natural_language": bool(query_guard.get("natural_language") or False),
        "filenameish": bool(query_guard.get("filenameish") or False),
        "path_like": bool(query_guard.get("path_like") or False),
        "oversized": bool(query_guard.get("oversized") or False),
        "truncated": bool(query_guard.get("truncated") or False),
        "token_capped": bool(query_guard.get("token_capped") or False),
        "compact_capped": bool(query_guard.get("compact_capped") or False),
        "degraded": bool(query_guard.get("degraded") or False),
        "degrade_reasons": list(query_guard.get("degrade_reasons") or []),
        "guard_reason": str(query_guard.get("guard_reason") or ""),
        "allow_title_fts": bool(query_guard.get("allow_title_fts") or False),
        "allow_content_fts": bool(query_guard.get("allow_content_fts") or False),
        "allow_direct_content_like": bool(query_guard.get("allow_direct_content_like") or False),
        "requested_modules": list(logical_modules),
        "raw_modules": list(raw_modules),
    }


def _build_empty_payload_with_guard(
    raw_query: str,
    logical_modules,
    raw_modules,
    query_guard: Dict[str, Any],
) -> Dict[str, Any]:
    payload = _empty_payload(raw_query, logical_modules)
    payload["query"] = raw_query
    payload["query_norm"] = str(query_guard.get("query_norm") or "")
    payload["query_compact"] = str(query_guard.get("query_compact") or "")
    payload["query_tokens"] = list(query_guard.get("query_tokens_used") or [])
    payload["requested_modules"] = list(logical_modules)
    payload["raw_modules"] = list(raw_modules)
    payload["sync"] = {
        "ok": True,
        "mode": "reuse_existing_index",
        "reason": "empty_payload",
        "query_class": str(query_guard.get("query_class") or ""),
        "degraded": bool(query_guard.get("degraded") or False),
        "guard_reason": str(query_guard.get("guard_reason") or ""),
    }
    return payload


def _resolve_search_strategy(filename_mode: bool, query_guard: Dict[str, Any]) -> str:
    if filename_mode:
        return "filename_sequential_fast_only"

    allow_title_fts = bool(query_guard.get("allow_title_fts") or False)
    allow_content_fts = bool(query_guard.get("allow_content_fts") or False)
    allow_direct_content_like = bool(query_guard.get("allow_direct_content_like") or False)

    if not allow_title_fts and not allow_content_fts and not allow_direct_content_like:
        return "metadata_only_guarded"
    if allow_title_fts and not allow_content_fts and not allow_direct_content_like:
        return "metadata_first_then_title_fts"
    return "metadata_first_then_fts_then_content_fallback_guarded"


def _group_payload_items(group_payload: Any) -> list:
    if not isinstance(group_payload, Mapping):
        return []

    for key in ("results", "items", "hits"):
        value = group_payload.get(key)
        if isinstance(value, list):
            return list(value)

    return []


def _normalize_group_payload(group_payload: Any) -> Dict[str, Any]:
    if isinstance(group_payload, Mapping):
        normalized = dict(group_payload)
    else:
        normalized = {}

    items = _group_payload_items(group_payload)

    existing_total = normalized.get("total", 0)
    try:
        existing_total = int(existing_total or 0)
    except Exception:
        existing_total = 0

    normalized["results"] = list(items)
    normalized["items"] = list(items)
    normalized["total"] = len(items) if items else existing_total
    return normalized


def _normalize_grouped_payload(grouped: Any) -> Dict[str, Dict[str, Any]]:
    if not isinstance(grouped, Mapping):
        return {}
    return {
        str(module): _normalize_group_payload(payload)
        for module, payload in grouped.items()
    }


def _group_totals(grouped: Mapping[str, Any]) -> Dict[str, int]:
    totals: Dict[str, int] = {}
    for module, payload in grouped.items():
        if isinstance(payload, Mapping):
            totals[str(module)] = int(payload.get("total") or 0)
        else:
            totals[str(module)] = 0
    return totals


def _should_refresh_chat_before_query(
    effective_raw_modules: Sequence[str],
    filename_mode: bool,
    path_mode: bool,
    query_guard: Dict[str, Any],
) -> bool:
    if "chat" not in effective_raw_modules:
        return False

    if filename_mode or path_mode:
        return False

    if bool(query_guard.get("oversized") or False):
        return False

    if bool(query_guard.get("symbol_heavy") or False):
        return False

    return True


def _selected_file_modules(raw_modules: Sequence[str]) -> list:
    return [m for m in raw_modules if m in ("doc", "files")]


def _should_use_content_aware_file_path(
    effective_raw_modules: Sequence[str],
    filename_mode: bool,
    path_mode: bool,
    query_guard: Dict[str, Any],
) -> bool:
    if filename_mode or path_mode:
        return False
    if not _selected_file_modules(effective_raw_modules):
        return False
    if not bool(query_guard.get("allow_direct_content_like") or False):
        return False
    if str(query_guard.get("query_class") or "") != "short_cjk":
        return False
    return True


def _merge_sync_module_stats(current: Any, incoming: Any) -> Dict[str, Any]:
    merged: Dict[str, Any] = {}
    if isinstance(current, Mapping):
        merged.update(dict(current))
    if isinstance(incoming, Mapping):
        for key, value in incoming.items():
            merged[str(key)] = value
    return merged


def _run_content_aware_file_sync(
    conn,
    base_path: Path,
    effective_raw_modules: Sequence[str],
    *,
    within_seconds: int,
    max_candidates: int,
) -> Dict[str, Any]:
    file_modules = _selected_file_modules(effective_raw_modules)
    meta: Dict[str, Any] = {
        "modules": {},
        "ok": True,
        "mode": "content_aware_quick_sync",
        "reason": "allow_direct_content_like",
    }

    for module in file_modules:
        root = (base_path / "documents") if module == "doc" else (base_path / "agent_files")
        recursive = (module == "files")
        try:
            meta["modules"][module] = quick_sync_file_module(
                conn=conn,
                base_path=base_path,
                module=module,
                root=root,
                recursive=recursive,
                within_seconds=within_seconds,
                max_candidates=max_candidates,
                name_hints=[],
                metadata_only=False,
            )
        except Exception as exc:
            meta["modules"][module] = {
                "ok": False,
                "error": str(exc),
            }
            meta["ok"] = False

    try:
        conn.commit()
    except Exception:
        pass

    return meta


def _apply_timing(
    trace: SearchTrace,
    *,
    payload: Optional[Dict[str, Any]] = None,
    sync_meta: Optional[Dict[str, Any]] = None,
    evidence_result: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    timing = trace.snapshot()

    if isinstance(sync_meta, dict):
        sync_meta["open_elapsed_ms"] = int(timing["open_elapsed_ms"] or 0)
        sync_meta["sync_elapsed_ms"] = int(timing["sync_elapsed_ms"] or 0)
        sync_meta["query_elapsed_ms"] = int(timing["query_elapsed_ms"] or 0)
        sync_meta["merge_elapsed_ms"] = int(timing["merge_elapsed_ms"] or 0)
        sync_meta["finalize_elapsed_ms"] = int(timing["finalize_elapsed_ms"] or 0)
        sync_meta["total_elapsed_ms"] = int(timing["total_elapsed_ms"] or 0)
        sync_meta["phase_elapsed_ms"] = dict(timing.get("phase_elapsed_ms") or {})

    if isinstance(evidence_result, dict):
        evidence_result["took_ms"] = int(timing["total_elapsed_ms"] or 0)
        evidence_result["open_elapsed_ms"] = int(timing["open_elapsed_ms"] or 0)
        evidence_result["sync_elapsed_ms"] = int(timing["sync_elapsed_ms"] or 0)
        evidence_result["query_elapsed_ms"] = int(timing["query_elapsed_ms"] or 0)
        evidence_result["merge_elapsed_ms"] = int(timing["merge_elapsed_ms"] or 0)
        evidence_result["finalize_elapsed_ms"] = int(timing["finalize_elapsed_ms"] or 0)
        evidence_result["phase_elapsed_ms"] = dict(timing.get("phase_elapsed_ms") or {})

    if isinstance(payload, dict):
        payload["took_ms"] = int(timing["total_elapsed_ms"] or 0)

    return timing


def _normalize_inbound_search_args(
    *,
    query: Any,
    base_path: Any = None,
    modules: Optional[Sequence[str]] = None,
    per_module_limit: int = 20,
    global_limit: int = 80,
    fuzzy_enabled: bool = True,
    sync_before_query: bool = False,
    sync_mode: str = "bootstrap_or_due",
    conv_id: str = "",
    request_id: str = "",
    rag_mode: str = "search",
    mcp_overrides: Optional[Dict[str, Any]] = None,
    limit: Optional[int] = None,
    fuzzy: Optional[bool] = None,
) -> Dict[str, Any]:
    mcp_overrides = dict(mcp_overrides or {})

    inbound = _extract_mapping(query)
    if inbound and (
        "query" in inbound
        or "modules" in inbound
        or "base_path" in inbound
        or "basepath" in inbound
    ):
        query = inbound.get("query", query)

        if inbound.get("modules") is not None:
            modules = inbound.get("modules")

        if inbound.get("per_module_limit") is not None:
            per_module_limit = _coerce_int(
                inbound.get("per_module_limit"),
                per_module_limit,
            )

        if inbound.get("limit") is not None:
            limit = inbound.get("limit")
        elif limit is None and inbound.get("global_limit") is not None:
            limit = inbound.get("global_limit")

        if inbound.get("fuzzy") is not None:
            fuzzy = inbound.get("fuzzy")
        elif fuzzy is None and inbound.get("fuzzy_enabled") is not None:
            fuzzy = inbound.get("fuzzy_enabled")

        if inbound.get("sync_before_query") is not None:
            sync_before_query = _coerce_bool(
                inbound.get("sync_before_query"),
                sync_before_query,
            )

        if inbound.get("sync_mode") is not None:
            sync_mode = _first_non_empty(
                inbound.get("sync_mode"),
                sync_mode,
            ) or sync_mode

        if not conv_id:
            conv_id = _first_non_empty(
                inbound.get("conv_id"),
                inbound.get("convid"),
            )

        inbound_request_id = _first_non_empty(
            inbound.get("request_id"),
            inbound.get("requestid"),
        )
        if not request_id and inbound_request_id:
            request_id = inbound_request_id

        inbound_rag_mode = _first_non_empty(
            inbound.get("rag_mode"),
            inbound.get("ragmode"),
        )
        if inbound_rag_mode and rag_mode in ("", "search", None):
            rag_mode = inbound_rag_mode

        inbound_mcp_overrides = inbound.get("mcp_overrides")
        if not mcp_overrides and isinstance(inbound_mcp_overrides, Mapping):
            mcp_overrides = dict(inbound_mcp_overrides)

        if not base_path:
            base_path = _first_non_empty(
                inbound.get("base_path"),
                inbound.get("_base_path"),
                inbound.get("basepath"),
            )

    request_id = request_id or str(uuid.uuid4())
    rag_mode = _first_non_empty(rag_mode, "search") or "search"

    modules_explicit = modules is not None

    if limit is not None:
        global_limit = _coerce_int(limit, global_limit)

    if fuzzy is not None:
        fuzzy_enabled = _coerce_bool(fuzzy, fuzzy_enabled)

    per_module_limit = max(1, _coerce_int(per_module_limit, 20))
    global_limit = max(1, _coerce_int(global_limit, 80))
    sync_before_query = _coerce_bool(sync_before_query, False)

    logical_modules = _normalize_modules(modules)
    raw_modules = _expand_raw_modules(logical_modules)

    raw_query = str(query or "").strip()
    query_guard = _build_query_guard(raw_query)

    guarded_raw_query = str(query_guard.get("raw_query_used") or raw_query or "").strip()
    query_norm = str(query_guard.get("query_norm") or "")
    query_compact = str(query_guard.get("query_compact") or "")
    query_tokens = list(query_guard.get("query_tokens_used") or [])
    query_class = str(query_guard.get("query_class") or "")

    filename_mode = _is_probable_filename_query(
        guarded_raw_query,
        query_tokens,
        query_compact,
    ) or bool(query_guard.get("filenameish") or False)

    path_mode = _is_path_like_query(guarded_raw_query) or bool(query_guard.get("path_like") or False)

    return {
        "query": query,
        "base_path": base_path,
        "modules": modules,
        "logical_modules": logical_modules,
        "raw_modules": raw_modules,
        "per_module_limit": per_module_limit,
        "global_limit": global_limit,
        "fuzzy_enabled": fuzzy_enabled,
        "sync_before_query": sync_before_query,
        "sync_mode": sync_mode,
        "conv_id": conv_id,
        "request_id": request_id,
        "rag_mode": rag_mode,
        "mcp_overrides": mcp_overrides,
        "modules_explicit": bool(modules_explicit),
        "raw_query": raw_query,
        "guarded_raw_query": guarded_raw_query,
        "query_norm": query_norm,
        "query_compact": query_compact,
        "query_tokens": query_tokens,
        "query_class": query_class,
        "query_guard": query_guard,
        "filename_mode": bool(filename_mode),
        "path_mode": bool(path_mode),
    }


__all__ = [
    "SearchTrace",
    "_apply_timing",
    "_build_empty_payload_with_guard",
    "_build_evidence_query",
    "_group_totals",
    "_merge_sync_module_stats",
    "_normalize_grouped_payload",
    "_normalize_inbound_search_args",
    "_resolve_search_strategy",
    "_run_content_aware_file_sync",
    "_should_refresh_chat_before_query",
    "_should_use_content_aware_file_path",
]
