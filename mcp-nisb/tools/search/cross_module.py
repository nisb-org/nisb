#!/usr/bin/env python3

import time
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence

from .cross_module_helpers import (
    FILENAME_QUERY_MAX_CANDIDATES,
    HOT_QUERY_QUICK_SYNC_MAX_CANDIDATES,
    HOT_QUERY_QUICK_SYNC_SECONDS,
    _build_grouped_compat,
    _derive_filename_hints,
    _derive_hot_sync_hints,
    _effective_raw_modules_for_query,
    _flatten_grouped,
    _merge_grouped,
    _query_selected_modules,
    _run_filename_sequence,
    _selected_index_total,
    _should_run_hot_quick_sync,
    _sync_selected_modules,
)
from .cross_module_pipeline import (
    SearchTrace,
    _apply_timing,
    _build_empty_payload_with_guard,
    _build_evidence_query,
    _group_totals,
    _merge_sync_module_stats,
    _normalize_grouped_payload,
    _normalize_inbound_search_args,
    _resolve_search_strategy,
    _run_content_aware_file_sync,
    _should_use_content_aware_file_path,
)
from .index_query import clear_query_observability, get_query_observability_snapshot
from .index_sync import (
    clear_open_runtime_snapshot,
    get_open_runtime_snapshot,
    get_runtime_pragma_snapshot,
    open_index,
)
from .index_sync_chat import decide_chat_refresh, sync_chat
from .index_sync_fs import quick_sync_file_module


_RECALL_RESCUE_RAW_MODULES = {"doc", "files", "library"}


def _extract_sync_module_elapsed_ms(modules_payload: Any) -> Dict[str, int]:
    if not isinstance(modules_payload, Mapping):
        return {}

    out: Dict[str, int] = {}
    for module, payload in modules_payload.items():
        if isinstance(payload, Mapping):
            try:
                out[str(module)] = int(payload.get("elapsed_ms") or 0)
            except Exception:
                out[str(module)] = 0
        else:
            out[str(module)] = 0
    return out


def _logical_group_for_raw_module(raw_module: str) -> str:
    value = str(raw_module or "")
    if value == "chat":
        return "chat"
    if value == "dirs":
        return "dirs"
    if value in {"doc", "files", "agent_files"}:
        return "files"
    if value == "library":
        return "library"
    return value


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value or 0)
    except Exception:
        return int(default)


def _count_nonzero_totals(totals: Mapping[str, Any]) -> int:
    count = 0
    for value in totals.values():
        if _safe_int(value) > 0:
            count += 1
    return count


def _compact_query_text(value: Any) -> str:
    text = str(value or "").strip().lower()
    return "".join(
        ch for ch in text
        if ("a" <= ch <= "z") or ("0" <= ch <= "9") or ("\u4e00" <= ch <= "\u9fff")
    )


def _contains_cjk_text(value: Any) -> bool:
    for ch in str(value or ""):
        if "\u4e00" <= ch <= "\u9fff":
            return True
    return False


def _chat_title_satisfied_for_short_cjk(
    *,
    query_class: str,
    raw_query: str,
    query_compact: str,
    query_tokens: Sequence[str],
    raw_grouped: Mapping[str, Any],
    totals: Mapping[str, Any],
    per_module_limit: int,
) -> bool:
    if str(query_class or "") != "short_cjk":
        return False

    compact = _compact_query_text(query_compact or raw_query)
    if not compact and query_tokens:
        compact = _compact_query_text(str(query_tokens[0] or ""))

    if len(compact) < 2 or len(compact) > 8:
        return False

    if not _contains_cjk_text(compact):
        return False

    chat_total = _safe_int(totals.get("chat"))
    if chat_total >= max(3, min(int(per_module_limit or 20), 8)):
        return True

    chat_items = []
    if isinstance(raw_grouped, Mapping):
        value = raw_grouped.get("chat") or []
        if isinstance(value, list):
            chat_items = value

    for item in chat_items:
        if not isinstance(item, Mapping):
            continue

        source_kind = str(item.get("source_kind") or "")
        match_type = str(item.get("match_type") or "")
        title_compact = _compact_query_text(item.get("title") or item.get("filename") or "")

        if not title_compact:
            continue

        if source_kind == "chat_meta" and title_compact == compact:
            return True

        if match_type == "title" and title_compact == compact:
            return True

    return False


def _collect_query_observability() -> Dict[str, Any]:
    try:
        modules = get_query_observability_snapshot()
    except Exception:
        modules = {}

    if not isinstance(modules, Mapping):
        modules = {}

    lane_counts: Dict[str, Any] = {}
    skipped_lanes: Dict[str, Any] = {}
    parent_merge_before: Dict[str, int] = {}
    parent_merge_after: Dict[str, int] = {}

    for module, payload in modules.items():
        if not isinstance(payload, Mapping):
            continue
        module_key = str(module or "")
        lane_counts[module_key] = dict(payload.get("lane_counts") or {})
        skipped_lanes[module_key] = list(payload.get("skipped_lanes") or [])
        parent_merge_before[module_key] = _safe_int(payload.get("parent_merge_before"))
        parent_merge_after[module_key] = _safe_int(payload.get("parent_merge_after"))

    return {
        "modules": dict(modules),
        "lane_counts": lane_counts,
        "skipped_lanes": skipped_lanes,
        "parent_merge_before": parent_merge_before,
        "parent_merge_after": parent_merge_after,
    }


def _item_dedupe_key(item: Any) -> str:
    if not isinstance(item, Mapping):
        return str(item)

    for key in (
        "item_key",
        "parent_key",
        "conv_id",
        "path",
        "file_path",
        "doc_id",
        "library_id",
        "title",
        "filename",
        "dirname",
    ):
        value = str(item.get(key, "") or "").strip()
        if value:
            return f"{key}:{value}"

    return str(sorted(item.items()))


def _merge_raw_grouped(
    primary: Mapping[str, Any],
    secondary: Mapping[str, Any],
) -> Dict[str, Any]:
    merged: Dict[str, Any] = {}

    all_modules = set()
    if isinstance(primary, Mapping):
        all_modules.update(str(k) for k in primary.keys())
    if isinstance(secondary, Mapping):
        all_modules.update(str(k) for k in secondary.keys())

    for module in all_modules:
        left = primary.get(module, []) if isinstance(primary, Mapping) else []
        right = secondary.get(module, []) if isinstance(secondary, Mapping) else []

        if not isinstance(left, list):
            left = list(left) if isinstance(left, Sequence) else []
        if not isinstance(right, list):
            right = list(right) if isinstance(right, Sequence) else []

        seen = set()
        items: List[Any] = []

        for item in list(left) + list(right):
            key = _item_dedupe_key(item)
            if key in seen:
                continue
            seen.add(key)
            items.append(item)

        merged[module] = items

    return merged


def _rescue_candidate_raw_modules(
    effective_raw_modules: Sequence[str],
    totals: Mapping[str, Any],
) -> List[str]:
    files_total = _safe_int(totals.get("files"))
    library_total = _safe_int(totals.get("library"))

    out: List[str] = []

    for raw_module in effective_raw_modules:
        module = str(raw_module or "")
        if module not in _RECALL_RESCUE_RAW_MODULES:
            continue

        logical_group = _logical_group_for_raw_module(module)
        if logical_group == "files" and files_total <= 0:
            out.append(module)
        elif logical_group == "library" and library_total <= 0:
            out.append(module)

    if out:
        deduped: List[str] = []
        seen = set()
        for module in out:
            if module in seen:
                continue
            seen.add(module)
            deduped.append(module)
        return deduped

    deduped = []
    seen = set()
    for raw_module in effective_raw_modules:
        module = str(raw_module or "")
        if module in _RECALL_RESCUE_RAW_MODULES and module not in seen:
            seen.add(module)
            deduped.append(module)
    return deduped


def _should_run_recall_rescue(
    *,
    effective_raw_modules: Sequence[str],
    query_class: str,
    query_guard: Mapping[str, Any],
    filename_mode: bool,
    path_mode: bool,
    totals: Mapping[str, Any],
    total: int,
    per_module_limit: int,
) -> bool:
    if filename_mode or path_mode:
        return False

    if str(query_class or "") in {"empty", "long_nl", "long_phrase", "symbol_heavy"}:
        return False

    if bool(query_guard.get("degraded") or False):
        return False

    if bool(query_guard.get("truncated") or False):
        return False

    if bool(query_guard.get("token_capped") or False):
        return False

    rescue_modules = _rescue_candidate_raw_modules(effective_raw_modules, totals)
    if not rescue_modules:
        return False

    files_total = _safe_int(totals.get("files"))
    library_total = _safe_int(totals.get("library"))
    nonzero_groups = _count_nonzero_totals(totals)
    weak_total_threshold = max(3, min(8, int(per_module_limit or 20) // 2 or 3))
    query_class_value = str(query_class or "")

    if query_class_value == "short_cjk":
        if files_total <= 0 and total <= weak_total_threshold:
            return True
        return False

    if files_total <= 0:
        return True

    if library_total <= 0 and total <= max(4, weak_total_threshold):
        return True

    if total <= weak_total_threshold:
        return True

    if nonzero_groups <= 1 and total <= max(10, int(per_module_limit or 20)):
        return True

    return False


def _rescue_per_module_limit(
    *,
    per_module_limit: int,
    query_class: str,
) -> int:
    base = int(per_module_limit or 20)
    if str(query_class or "") == "short_cjk":
        return min(max(base + 8, base * 2), 36)
    return min(max(base + 12, base * 2), 48)


def nisb_search_cross_module(
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
    normalize_query: Optional[bool] = None,
    rerank: Optional[bool] = None,
) -> Dict[str, Any]:
    del normalize_query
    del rerank

    trace = SearchTrace()
    try:
        clear_query_observability()
    except Exception:
        pass
    query_observability: Dict[str, Any] = {
        "modules": {},
        "lane_counts": {},
        "skipped_lanes": {},
        "parent_merge_before": {},
        "parent_merge_after": {},
    }
    conn = None
    db_path = None

    normalized = _normalize_inbound_search_args(
        query=query,
        base_path=base_path,
        modules=modules,
        per_module_limit=per_module_limit,
        global_limit=global_limit,
        fuzzy_enabled=fuzzy_enabled,
        sync_before_query=sync_before_query,
        sync_mode=sync_mode,
        conv_id=conv_id,
        request_id=request_id,
        rag_mode=rag_mode,
        mcp_overrides=mcp_overrides,
        limit=limit,
        fuzzy=fuzzy,
    )

    raw_query = str(normalized["raw_query"] or "")
    logical_modules = list(normalized["logical_modules"] or [])
    raw_modules = list(normalized["raw_modules"] or [])
    query_guard = dict(normalized["query_guard"] or {})
    query_class = str(normalized["query_class"] or "")
    request_id = str(normalized["request_id"] or "")
    conv_id = str(normalized["conv_id"] or "")
    rag_mode = str(normalized["rag_mode"] or "search")
    mcp_overrides = dict(normalized["mcp_overrides"] or {})
    query_norm = str(normalized["query_norm"] or "")
    query_compact = str(normalized["query_compact"] or "")
    query_tokens = list(normalized["query_tokens"] or [])
    guarded_raw_query = str(normalized["guarded_raw_query"] or "")
    modules_explicit = bool(normalized["modules_explicit"])
    filename_mode = bool(normalized["filename_mode"])
    path_mode = bool(normalized["path_mode"])
    per_module_limit = int(normalized["per_module_limit"] or 20)
    global_limit = int(normalized["global_limit"] or 80)
    fuzzy_enabled = bool(normalized["fuzzy_enabled"])
    sync_before_query = bool(normalized["sync_before_query"])
    sync_mode = str(normalized["sync_mode"] or "bootstrap_or_due")
    base_path_value = normalized["base_path"]

    if not raw_query:
        payload = _build_empty_payload_with_guard(
            raw_query=raw_query,
            logical_modules=logical_modules,
            raw_modules=raw_modules,
            query_guard=query_guard,
        )
        evidence_result = {
            "total": 0,
            "totals": {m: 0 for m in logical_modules},
            "took_ms": 0,
            "open_elapsed_ms": 0,
            "sync_elapsed_ms": 0,
            "query_elapsed_ms": 0,
            "merge_elapsed_ms": 0,
            "finalize_elapsed_ms": 0,
            "degraded": bool(query_guard.get("degraded") or False),
            "degrade_reason": str(query_guard.get("guard_reason") or ""),
            "degrade_reasons": list(query_guard.get("degrade_reasons") or []),
            "query_class": query_class,
            "query_observability": query_observability.get("modules", {}),
            "lane_counts": query_observability.get("lane_counts", {}),
            "skipped_lanes": query_observability.get("skipped_lanes", {}),
            "parent_merge_before": query_observability.get("parent_merge_before", {}),
            "parent_merge_after": query_observability.get("parent_merge_after", {}),
        }

        response = {
            "conv_id": conv_id,
            "request_id": request_id,
            "rag_mode": rag_mode,
            "mcp_overrides": mcp_overrides,
            "mode_used": "cross_module_search",
            "evidence_query": _build_evidence_query(
                raw_query=raw_query,
                logical_modules=logical_modules,
                raw_modules=raw_modules,
                query_guard=query_guard,
            ),
            "evidence_tools": [
                {"name": "cross_module_search", "modules": logical_modules},
            ],
            "evidence_result": evidence_result,
            "citations": [],
            "response": "搜索词为空，已返回空结果。",
            "status": "ok",
            "message": "empty_query",
            "tool_calls": [
                {
                    "name": "cross_module_search",
                    "status": "ok",
                    "modules": logical_modules,
                    "elapsed_ms": 0,
                }
            ],
            "tool_results": [
                {
                    "tool_name": "nisb_search_cross_module",
                    "status": "ok",
                    "data": payload,
                }
            ],
        }

        _apply_timing(
            trace,
            payload=payload,
            sync_meta=payload.get("sync"),
            evidence_result=evidence_result,
        )
        return response

    if not base_path_value:
        payload = _build_empty_payload_with_guard(
            raw_query=raw_query,
            logical_modules=logical_modules,
            raw_modules=raw_modules,
            query_guard=query_guard,
        )
        evidence_result = {
            "total": 0,
            "totals": {m: 0 for m in logical_modules},
            "took_ms": 0,
            "open_elapsed_ms": 0,
            "sync_elapsed_ms": 0,
            "query_elapsed_ms": 0,
            "merge_elapsed_ms": 0,
            "finalize_elapsed_ms": 0,
            "degraded": bool(query_guard.get("degraded") or False),
            "degrade_reason": str(query_guard.get("guard_reason") or ""),
            "degrade_reasons": list(query_guard.get("degrade_reasons") or []),
            "query_class": query_class,
            "error": "missing_base_path",
        }

        response = {
            "conv_id": conv_id,
            "request_id": request_id,
            "rag_mode": rag_mode,
            "mcp_overrides": mcp_overrides,
            "mode_used": "cross_module_search",
            "evidence_query": _build_evidence_query(
                raw_query=raw_query,
                logical_modules=logical_modules,
                raw_modules=raw_modules,
                query_guard=query_guard,
            ),
            "evidence_tools": [
                {
                    "name": "cross_module_search",
                    "modules": raw_modules,
                }
            ],
            "evidence_result": evidence_result,
            "citations": [],
            "response": "搜索失败。",
            "status": "error",
            "message": "missing_base_path",
            "tool_calls": [
                {
                    "name": "cross_module_search",
                    "status": "error",
                    "modules": raw_modules,
                    "elapsed_ms": 0,
                }
            ],
            "tool_results": [
                {
                    "tool_name": "nisb_search_cross_module",
                    "status": "error",
                    "data": payload,
                }
            ],
        }

        timing = _apply_timing(
            trace,
            payload=payload,
            sync_meta=payload.get("sync"),
            evidence_result=evidence_result,
        )
        response["tool_calls"][0]["elapsed_ms"] = int(timing["total_elapsed_ms"] or 0)
        return response

    base_path = Path(str(base_path_value))
    effective_raw_modules = _effective_raw_modules_for_query(
        raw_modules=raw_modules,
        filename_mode=filename_mode,
        path_mode=path_mode,
        modules_explicit=modules_explicit,
    )

    filename_hints = _derive_filename_hints(guarded_raw_query, query_norm)
    hot_sync_hints = _derive_hot_sync_hints(
        guarded_raw_query,
        query_norm,
        query_compact,
        query_tokens,
    )

    try:
        with trace.measure("open"):
            conn, db_path = open_index(base_path)

        runtime_pragmas = get_runtime_pragma_snapshot(conn)
        open_runtime = get_open_runtime_snapshot(conn)

        indexed_total_before_query = _selected_index_total(conn, effective_raw_modules)

        guard_blocks_hot_sync = (
            query_class in {"empty", "long_nl", "symbol_heavy"}
            or bool(query_guard.get("truncated") or False)
            or bool(query_guard.get("token_capped") or False)
            or bool(query_guard.get("compact_capped") or False)
        )

        should_quick_sync = (
            not guard_blocks_hot_sync
            and _should_run_hot_quick_sync(guarded_raw_query, query_tokens)
        )

        chat_refresh_decision = decide_chat_refresh(
            conn,
            effective_raw_modules=list(effective_raw_modules),
            raw_query=guarded_raw_query,
            query_tokens=list(query_tokens),
            query_guard=query_guard,
            filename_mode=filename_mode,
            path_mode=path_mode,
        )
        should_refresh_chat = bool(chat_refresh_decision.get("should_refresh") or False)

        can_defer_chat_refresh = (
            should_refresh_chat
            and not sync_before_query
            and not filename_mode
            and not path_mode
            and "chat" in set(effective_raw_modules)
            and indexed_total_before_query > 0
        )
        defer_chat_refresh_reason = ""
        if (
            can_defer_chat_refresh
            and query_class == "short_cjk"
            and len(str(query_compact or guarded_raw_query or "")) >= 2
        ):
            defer_chat_refresh_reason = "short_cjk_query_first"
        elif can_defer_chat_refresh and query_class == "long_nl":
            defer_chat_refresh_reason = "long_nl_direct_title_only_query_first"

        if defer_chat_refresh_reason:
            should_refresh_chat = False
            chat_refresh_decision = dict(chat_refresh_decision)
            chat_refresh_decision["should_refresh"] = False
            chat_refresh_decision["deferred"] = True
            chat_refresh_decision["defer_reason"] = defer_chat_refresh_reason

        sync_meta: Dict[str, Any]
        raw_grouped: Dict[str, Any]

        if sync_before_query:
            with trace.measure("sync"):
                sync_meta = _sync_selected_modules(
                    conn,
                    base_path,
                    effective_raw_modules,
                    mode=sync_mode,
                )

            sync_meta["sync_modules_elapsed_ms"] = _extract_sync_module_elapsed_ms(sync_meta.get("modules"))

            try:
                recall_modules = [m for m in ("files", "doc", "dirs", "chat") if m in set(effective_raw_modules)]
                if recall_modules:
                    from tools.search.search_recall_maintenance import ensure_recall_tier2_fs
                    with trace.measure("recall_tier2"):
                        sync_meta["recall_tier2_fs"] = ensure_recall_tier2_fs(
                            conn,
                            base_path,
                            modules=recall_modules,
                            online=True,
                            force=False,
                        )
            except Exception as exc:
                sync_meta["recall_tier2_fs"] = {
                    "ok": False,
                    "error": repr(exc),
                }

            with trace.measure("query"):
                raw_grouped = _query_selected_modules(
                    conn=conn,
                    base_path=base_path,
                    raw_modules=effective_raw_modules,
                    raw_query=guarded_raw_query,
                    query_norm=query_norm,
                    query_compact=query_compact,
                    query_tokens=query_tokens,
                    per_module_limit=per_module_limit,
                    fuzzy_enabled=fuzzy_enabled,
                )

        elif indexed_total_before_query <= 0:
            with trace.measure("sync"):
                sync_meta = _sync_selected_modules(
                    conn,
                    base_path,
                    effective_raw_modules,
                    mode="bootstrap_if_empty",
                )

            sync_meta["sync_modules_elapsed_ms"] = _extract_sync_module_elapsed_ms(sync_meta.get("modules"))

            try:
                recall_modules = [m for m in ("files", "doc", "dirs", "chat") if m in set(effective_raw_modules)]
                if recall_modules:
                    from tools.search.search_recall_maintenance import ensure_recall_tier2_fs
                    with trace.measure("recall_tier2"):
                        sync_meta["recall_tier2_fs"] = ensure_recall_tier2_fs(
                            conn,
                            base_path,
                            modules=recall_modules,
                            online=True,
                            force=False,
                        )
            except Exception as exc:
                sync_meta["recall_tier2_fs"] = {
                    "ok": False,
                    "error": repr(exc),
                }

            with trace.measure("query"):
                raw_grouped = _query_selected_modules(
                    conn=conn,
                    base_path=base_path,
                    raw_modules=effective_raw_modules,
                    raw_query=guarded_raw_query,
                    query_norm=query_norm,
                    query_compact=query_compact,
                    query_tokens=query_tokens,
                    per_module_limit=per_module_limit,
                    fuzzy_enabled=fuzzy_enabled,
                )

        elif filename_mode:
            raw_grouped, sync_meta, filename_sync_ms, filename_query_ms = _run_filename_sequence(
                conn=conn,
                base_path=base_path,
                raw_modules=effective_raw_modules,
                raw_query=guarded_raw_query,
                query_norm=query_norm,
                query_compact=query_compact,
                query_tokens=query_tokens,
                filename_hints=filename_hints,
                path_mode=path_mode,
                per_module_limit=per_module_limit,
                fuzzy_enabled=fuzzy_enabled,
                within_seconds=HOT_QUERY_QUICK_SYNC_SECONDS,
                max_candidates=FILENAME_QUERY_MAX_CANDIDATES,
                stop_on_first_hit=not modules_explicit,
            )
            trace.add_ms("sync", int(filename_sync_ms or 0))
            trace.add_ms("query", int(filename_query_ms or 0))
            sync_meta["sync_modules_elapsed_ms"] = _extract_sync_module_elapsed_ms(sync_meta.get("modules"))

        elif should_quick_sync:
            sync_module_elapsed_ms: Dict[str, int] = {}

            with trace.measure("sync"):
                hot_modules = [m for m in effective_raw_modules if m in ("doc", "files")]
                content_aware_hot_sync = _should_use_content_aware_file_path(
                    effective_raw_modules=effective_raw_modules,
                    filename_mode=filename_mode,
                    path_mode=path_mode,
                    query_guard=query_guard,
                )

                if hot_modules:
                    sync_meta = {
                        "modules": {},
                        "ok": True,
                        "mode": "hot_query_content_scan" if content_aware_hot_sync else "hot_query_hint_scan",
                        "reason": "allow_direct_content_like" if content_aware_hot_sync else "high_confidence_single_token_incremental",
                        "target_modules": hot_modules,
                        "filename_hints": [] if content_aware_hot_sync else list(hot_sync_hints),
                        "within_seconds": int(HOT_QUERY_QUICK_SYNC_SECONDS),
                        "max_candidates_per_module": int(HOT_QUERY_QUICK_SYNC_MAX_CANDIDATES),
                    }

                    for module in hot_modules:
                        module_started = time.time()
                        sync_meta["modules"][module] = quick_sync_file_module(
                            conn=conn,
                            base_path=base_path,
                            module=module,
                            root=(base_path / "documents") if module == "doc" else (base_path / "agent_files"),
                            recursive=(module == "files"),
                            within_seconds=HOT_QUERY_QUICK_SYNC_SECONDS,
                            max_candidates=HOT_QUERY_QUICK_SYNC_MAX_CANDIDATES,
                            name_hints=[] if content_aware_hot_sync else list(hot_sync_hints),
                            metadata_only=(not content_aware_hot_sync),
                        )
                        module_elapsed_ms = int((time.time() - module_started) * 1000)
                        sync_module_elapsed_ms[module] = module_elapsed_ms
                        if isinstance(sync_meta["modules"][module], Mapping):
                            sync_meta["modules"][module] = dict(sync_meta["modules"][module])
                            sync_meta["modules"][module]["elapsed_ms"] = module_elapsed_ms

                    try:
                        conn.commit()
                    except Exception:
                        pass
                else:
                    sync_meta = {
                        "modules": {},
                        "ok": True,
                        "mode": "reuse_existing_index",
                        "reason": "no_file_modules_for_hot_query_sync",
                    }

            sync_meta["sync_modules_elapsed_ms"] = dict(sync_module_elapsed_ms)

            with trace.measure("query"):
                raw_grouped = _query_selected_modules(
                    conn=conn,
                    base_path=base_path,
                    raw_modules=effective_raw_modules,
                    raw_query=guarded_raw_query,
                    query_norm=query_norm,
                    query_compact=query_compact,
                    query_tokens=query_tokens,
                    per_module_limit=per_module_limit,
                    fuzzy_enabled=fuzzy_enabled,
                )

        else:
            if should_refresh_chat:
                with trace.measure("sync"):
                    try:
                        chat_stats = sync_chat(conn, base_path)
                        try:
                            conn.commit()
                        except Exception:
                            pass
                        sync_meta = {
                            "modules": {"chat": chat_stats},
                            "ok": True,
                            "mode": "chat_incremental_refresh",
                            "reason": "chat_intent_due",
                            "sync_modules_elapsed_ms": {
                                "chat": int(chat_stats.get("elapsed_ms") or 0),
                            },
                        }
                    except Exception as sync_exc:
                        sync_meta = {
                            "modules": {},
                            "ok": False,
                            "mode": "chat_incremental_refresh",
                            "reason": "refresh_chat_before_query_failed",
                            "error": str(sync_exc),
                            "sync_modules_elapsed_ms": {},
                        }
            else:
                sync_meta = {
                    "modules": {},
                    "ok": True,
                    "mode": "reuse_existing_index",
                    "reason": str(chat_refresh_decision.get("reason") or "skip_chat_refresh"),
                    "sync_modules_elapsed_ms": {},
                }

            with trace.measure("query"):
                raw_grouped = _query_selected_modules(
                    conn=conn,
                    base_path=base_path,
                    raw_modules=effective_raw_modules,
                    raw_query=guarded_raw_query,
                    query_norm=query_norm,
                    query_compact=query_compact,
                    query_tokens=query_tokens,
                    per_module_limit=per_module_limit,
                    fuzzy_enabled=fuzzy_enabled,
                )

        with trace.measure("merge"):
            merged_grouped = _merge_grouped(raw_grouped, per_module_limit=per_module_limit)
            grouped = _normalize_grouped_payload(merged_grouped)
            grouped_compat = _build_grouped_compat(grouped)
            results = _flatten_grouped(grouped, limit=global_limit)
            totals = _group_totals(grouped)
            total = sum(totals.values())

        chat_total_for_retry = int(totals.get("chat") or 0)
        chat_satisfied_for_short_cjk = _chat_title_satisfied_for_short_cjk(
            query_class=query_class,
            raw_query=guarded_raw_query,
            query_compact=query_compact,
            query_tokens=query_tokens,
            raw_grouped=raw_grouped,
            totals=totals,
            per_module_limit=per_module_limit,
        )

        should_retry_files_content = (
            int(total or 0) <= 0
            and not chat_satisfied_for_short_cjk
            and _should_use_content_aware_file_path(
                effective_raw_modules=effective_raw_modules,
                filename_mode=filename_mode,
                path_mode=path_mode,
                query_guard=query_guard,
            )
            and int(totals.get("files") or 0) <= 0
        )

        if chat_satisfied_for_short_cjk:
            sync_meta["content_retry_skipped"] = True
            sync_meta["content_retry_skip_reason"] = "chat_satisfied_for_short_cjk"
            sync_meta["content_retry_chat_total"] = chat_total_for_retry

        if int(total or 0) > 0 and _should_use_content_aware_file_path(
            effective_raw_modules=effective_raw_modules,
            filename_mode=filename_mode,
            path_mode=path_mode,
            query_guard=query_guard,
        ) and int(totals.get("files") or 0) <= 0:
            sync_meta["content_retry_skipped"] = True
            sync_meta["content_retry_skip_reason"] = "total_satisfied_before_content_retry"
            sync_meta["content_retry_total"] = int(total or 0)

        if should_retry_files_content:
            with trace.measure("sync"):
                retry_meta = _run_content_aware_file_sync(
                    conn=conn,
                    base_path=base_path,
                    effective_raw_modules=effective_raw_modules,
                    within_seconds=HOT_QUERY_QUICK_SYNC_SECONDS,
                    max_candidates=HOT_QUERY_QUICK_SYNC_MAX_CANDIDATES,
                )

            sync_meta["modules"] = _merge_sync_module_stats(
                sync_meta.get("modules"),
                retry_meta.get("modules"),
            )
            sync_meta["ok"] = bool(sync_meta.get("ok", True)) and bool(retry_meta.get("ok", True))
            sync_meta["mode"] = "short_cjk_content_retry"
            sync_meta["reason"] = "allow_direct_content_like_zero_files_retry"
            sync_meta["sync_modules_elapsed_ms"] = _extract_sync_module_elapsed_ms(sync_meta.get("modules"))

            try:
                recall_modules = [m for m in ("files", "doc", "dirs", "chat") if m in set(effective_raw_modules)]
                if recall_modules:
                    from tools.search.search_recall_maintenance import ensure_recall_tier2_fs
                    with trace.measure("recall_tier2"):
                        sync_meta["recall_tier2_fs"] = ensure_recall_tier2_fs(
                            conn,
                            base_path,
                            modules=recall_modules,
                            online=True,
                            force=False,
                        )
            except Exception as exc:
                sync_meta["recall_tier2_fs"] = {
                    "ok": False,
                    "error": repr(exc),
                }

            with trace.measure("query"):
                raw_grouped = _query_selected_modules(
                    conn=conn,
                    base_path=base_path,
                    raw_modules=effective_raw_modules,
                    raw_query=guarded_raw_query,
                    query_norm=query_norm,
                    query_compact=query_compact,
                    query_tokens=query_tokens,
                    per_module_limit=per_module_limit,
                    fuzzy_enabled=fuzzy_enabled,
                )

            with trace.measure("merge"):
                merged_grouped = _merge_grouped(raw_grouped, per_module_limit=per_module_limit)
                grouped = _normalize_grouped_payload(merged_grouped)
                grouped_compat = _build_grouped_compat(grouped)
                results = _flatten_grouped(grouped, limit=global_limit)
                totals = _group_totals(grouped)
                total = sum(totals.values())

        should_run_rescue = False
        if chat_satisfied_for_short_cjk:
            sync_meta["recall_rescue_skipped"] = True
            sync_meta["recall_rescue_skip_reason"] = "chat_satisfied_for_short_cjk"
            sync_meta["recall_rescue_chat_total"] = chat_total_for_retry
        else:
            should_run_rescue = _should_run_recall_rescue(
                effective_raw_modules=effective_raw_modules,
                query_class=query_class,
                query_guard=query_guard,
                filename_mode=filename_mode,
                path_mode=path_mode,
                totals=totals,
                total=total,
                per_module_limit=per_module_limit,
            )

        if should_run_rescue:
            rescue_modules = _rescue_candidate_raw_modules(effective_raw_modules, totals)
            rescue_limit = _rescue_per_module_limit(
                per_module_limit=per_module_limit,
                query_class=query_class,
            )

            with trace.measure("query"):
                rescue_raw_grouped = _query_selected_modules(
                    conn=conn,
                    base_path=base_path,
                    raw_modules=rescue_modules,
                    raw_query=guarded_raw_query,
                    query_norm=query_norm,
                    query_compact=query_compact,
                    query_tokens=query_tokens,
                    per_module_limit=rescue_limit,
                    fuzzy_enabled=fuzzy_enabled,
                )

            with trace.measure("merge"):
                raw_grouped = _merge_raw_grouped(raw_grouped, rescue_raw_grouped)
                merged_grouped = _merge_grouped(raw_grouped, per_module_limit=per_module_limit)
                grouped = _normalize_grouped_payload(merged_grouped)
                grouped_compat = _build_grouped_compat(grouped)
                results = _flatten_grouped(grouped, limit=global_limit)
                totals = _group_totals(grouped)
                total = sum(totals.values())

        indexed_total_after_query = _selected_index_total(conn, effective_raw_modules)

        sync_meta["runtime_pragmas"] = runtime_pragmas
        sync_meta["open_runtime"] = open_runtime
        sync_meta["selected_index_total_before_query"] = int(indexed_total_before_query)
        sync_meta["selected_index_total"] = int(indexed_total_after_query)
        sync_meta["filename_mode"] = bool(filename_mode)
        sync_meta["path_mode"] = bool(path_mode)
        sync_meta["modules_explicit"] = bool(modules_explicit)
        sync_meta["query_class"] = query_class
        sync_meta["degraded"] = bool(query_guard.get("degraded") or False)
        sync_meta["guard_reason"] = str(query_guard.get("guard_reason") or "")
        sync_meta["degrade_reasons"] = list(query_guard.get("degrade_reasons") or [])
        sync_meta["chat_refresh_decision"] = dict(chat_refresh_decision)
        sync_meta["query_guard"] = {
            "query_class": query_class,
            "degraded": bool(query_guard.get("degraded") or False),
            "guard_reason": str(query_guard.get("guard_reason") or ""),
            "degrade_reasons": list(query_guard.get("degrade_reasons") or []),
            "allow_title_fts": bool(query_guard.get("allow_title_fts") or False),
            "allow_content_fts": bool(query_guard.get("allow_content_fts") or False),
            "allow_direct_content_like": bool(query_guard.get("allow_direct_content_like") or False),
            "token_count_raw": int(query_guard.get("token_count_raw") or 0),
            "token_count_used": int(query_guard.get("token_count_used") or 0),
            "token_count_fts": int(query_guard.get("token_count_fts") or 0),
            "query_chars_raw": int(query_guard.get("query_chars_raw") or 0),
            "query_chars_used": int(query_guard.get("query_chars_used") or 0),
            "symbol_ratio": float(query_guard.get("symbol_ratio") or 0.0),
        }

        query_observability = _collect_query_observability()

        payload = {
            "query": raw_query,
            "query_norm": query_norm,
            "query_compact": query_compact,
            "query_tokens": query_tokens,
            "requested_modules": list(logical_modules),
            "raw_modules": list(effective_raw_modules),
            "grouped": grouped,
            "grouped_results": grouped_compat,
            "results": results,
            "items": results,
            "totals": totals,
            "total": total,
            "took_ms": 0,
            "db_path": str(db_path) if db_path else "",
            "sync": sync_meta,
            "query_observability": query_observability.get("modules", {}),
            "lane_counts": query_observability.get("lane_counts", {}),
            "skipped_lanes": query_observability.get("skipped_lanes", {}),
            "parent_merge_before": query_observability.get("parent_merge_before", {}),
            "parent_merge_after": query_observability.get("parent_merge_after", {}),
        }

        search_strategy = _resolve_search_strategy(filename_mode, query_guard)

        evidence_result = {
            "total": total,
            "totals": totals,
            "took_ms": 0,
            "open_elapsed_ms": 0,
            "sync_elapsed_ms": 0,
            "query_elapsed_ms": 0,
            "merge_elapsed_ms": 0,
            "finalize_elapsed_ms": 0,
            "degraded": bool(query_guard.get("degraded") or False),
            "degrade_reason": str(query_guard.get("guard_reason") or ""),
            "degrade_reasons": list(query_guard.get("degrade_reasons") or []),
            "query_class": query_class,
        }

        response = {
            "conv_id": conv_id,
            "request_id": request_id,
            "rag_mode": rag_mode,
            "mcp_overrides": mcp_overrides,
            "mode_used": "cross_module_search",
            "evidence_query": _build_evidence_query(
                raw_query=raw_query,
                logical_modules=logical_modules,
                raw_modules=effective_raw_modules,
                query_guard=query_guard,
            ),
            "evidence_tools": [
                {
                    "name": "index_sync",
                    "modules": effective_raw_modules,
                    "enabled": bool(
                        sync_before_query
                        or indexed_total_before_query <= 0
                        or filename_mode
                        or should_quick_sync
                        or should_refresh_chat
                        or should_retry_files_content
                    ),
                    "mode": sync_meta.get("mode", ""),
                },
                {
                    "name": "index_query",
                    "modules": effective_raw_modules,
                    "strategy": search_strategy,
                    "query_class": query_class,
                    "degraded": bool(query_guard.get("degraded") or False),
                },
            ],
            "evidence_result": evidence_result,
            "citations": [],
            "response": f"已找到 {total} 条结果，并按模块返回。",
            "status": "ok",
            "message": "search_ok",
            "tool_calls": [
                {
                    "name": "index_sync",
                    "status": "ok" if sync_meta.get("ok", True) else "partial_error",
                    "modules": effective_raw_modules,
                    "elapsed_ms": 0,
                },
                {
                    "name": "index_query",
                    "status": "ok",
                    "modules": effective_raw_modules,
                    "elapsed_ms": 0,
                },
            ],
            "tool_results": [
                {
                    "tool_name": "nisb_search_cross_module",
                    "status": "ok",
                    "data": payload,
                }
            ],
        }

        timing = _apply_timing(
            trace,
            payload=payload,
            sync_meta=sync_meta,
            evidence_result=evidence_result,
        )

        response["tool_calls"][0]["elapsed_ms"] = int(timing["sync_elapsed_ms"] or 0)
        response["tool_calls"][1]["elapsed_ms"] = int(timing["query_elapsed_ms"] or 0)
        return response

    except Exception as exc:
        fallback_raw_modules = effective_raw_modules if "effective_raw_modules" in locals() else raw_modules

        payload = _build_empty_payload_with_guard(
            raw_query=raw_query,
            logical_modules=logical_modules,
            raw_modules=fallback_raw_modules,
            query_guard=query_guard,
        )

        evidence_result = {
            "total": 0,
            "totals": {m: 0 for m in logical_modules},
            "took_ms": 0,
            "open_elapsed_ms": 0,
            "sync_elapsed_ms": 0,
            "query_elapsed_ms": 0,
            "merge_elapsed_ms": 0,
            "finalize_elapsed_ms": 0,
            "degraded": bool(query_guard.get("degraded") or False),
            "degrade_reason": str(query_guard.get("guard_reason") or ""),
            "degrade_reasons": list(query_guard.get("degrade_reasons") or []),
            "query_class": query_class,
            "error": str(exc),
        }

        response = {
            "conv_id": conv_id,
            "request_id": request_id,
            "rag_mode": rag_mode,
            "mcp_overrides": mcp_overrides,
            "mode_used": "cross_module_search",
            "evidence_query": _build_evidence_query(
                raw_query=raw_query,
                logical_modules=logical_modules,
                raw_modules=fallback_raw_modules,
                query_guard=query_guard,
            ),
            "evidence_tools": [
                {
                    "name": "cross_module_search",
                    "modules": fallback_raw_modules,
                }
            ],
            "evidence_result": evidence_result,
            "citations": [],
            "response": "搜索失败。",
            "status": "error",
            "message": str(exc),
            "tool_calls": [
                {
                    "name": "cross_module_search",
                    "status": "error",
                    "modules": fallback_raw_modules,
                    "elapsed_ms": 0,
                }
            ],
            "tool_results": [
                {
                    "tool_name": "nisb_search_cross_module",
                    "status": "error",
                    "data": payload,
                }
            ],
        }

        timing = _apply_timing(
            trace,
            payload=payload,
            sync_meta=payload.get("sync"),
            evidence_result=evidence_result,
        )
        response["tool_calls"][0]["elapsed_ms"] = int(timing["total_elapsed_ms"] or 0)
        return response

    finally:
        if conn is not None:
            try:
                clear_open_runtime_snapshot(conn)
            except Exception:
                pass
            try:
                conn.close()
            except Exception:
                pass

