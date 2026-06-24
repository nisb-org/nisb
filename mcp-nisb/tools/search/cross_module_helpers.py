#!/usr/bin/env python3

import ast
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from .index_query import query_module_results
from .index_sync import module_entry_count, sync_modules
from .index_sync_fs import quick_sync_dirs_module, quick_sync_file_module


DEFAULT_LOGICAL_MODULES: Tuple[str, ...] = ("chat", "dirs", "files", "library")
LOGICAL_TO_RAW: Dict[str, List[str]] = {
    "chat": ["chat"],
    "dirs": ["dirs"],
    "files": ["doc", "files"],
    "library": ["library"],
}
RAW_TO_LOGICAL: Dict[str, str] = {
    "chat": "chat",
    "dirs": "dirs",
    "doc": "files",
    "files": "files",
    "agent_files": "files",
    "library": "library",
}

HOT_QUERY_QUICK_SYNC_SECONDS = 180
HOT_QUERY_QUICK_SYNC_MAX_CANDIDATES = 64
FILENAME_QUERY_MAX_CANDIDATES = 200

FILE_LIKE_SUFFIXES = (
    ".md", ".txt", ".json", ".vue", ".ts", ".js", ".py", ".yml", ".yaml",
    ".toml", ".ini", ".csv", ".log", ".pdf", ".doc", ".docx", ".ppt", ".pptx",
    ".xls", ".xlsx", ".html", ".css", ".scss", ".xml",
)

TITLEISH_MATCH_TYPES = {
    "filename",
    "title",
    "dirname",
    "dirpath",
    "library_name",
    "library_doc",
}


def _compact_text(value: str) -> str:
    text = str(value or "").lower().strip()
    return "".join(
        ch for ch in text
        if ("a" <= ch <= "z") or ("0" <= ch <= "9") or ("\u4e00" <= ch <= "\u9fff")
    )


def _contains_cjk_text(value: str) -> bool:
    for ch in str(value or ""):
        if "\u4e00" <= ch <= "\u9fff":
            return True
    return False


def _strong_chat_title_satisfied(
    raw_query: str,
    query_compact: str,
    query_tokens: Sequence[str],
    chat_items: Sequence[Mapping[str, Any]],
) -> bool:
    compact = _compact_text(query_compact or raw_query)
    if not compact and query_tokens:
        compact = _compact_text(str(query_tokens[0] or ""))

    if len(compact) < 2 or len(compact) > 8:
        return False

    if not _contains_cjk_text(compact):
        return False

    for item in chat_items:
        if not isinstance(item, Mapping):
            continue

        source_kind = str(item.get("source_kind") or "")
        match_type = str(item.get("match_type") or "")
        title_compact = _compact_text(str(item.get("title") or item.get("filename") or ""))

        if not title_compact:
            continue

        if source_kind == "chat_meta" and title_compact == compact:
            return True

        if match_type == "title" and title_compact == compact:
            return True

    return False


def _split_tokens(query_norm: str, query_compact: str) -> List[str]:
    text = str(query_norm or "").strip().lower()
    parts = re.findall(r"[a-z0-9_]+|[\u4e00-\u9fff]+", text)
    parts = [p for p in parts if p]
    if not parts and query_compact:
        parts = [query_compact]

    deduped: List[str] = []
    seen = set()
    for part in parts:
        if part not in seen:
            seen.add(part)
            deduped.append(part)
    return deduped


def _unique_keep_order(values: Sequence[str]) -> List[str]:
    out: List[str] = []
    seen = set()
    for value in values:
        text = str(value or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        out.append(text)
    return out


def _normalize_modules(modules: Optional[Sequence[str]]) -> List[str]:
    if not modules:
        return list(DEFAULT_LOGICAL_MODULES)

    if isinstance(modules, str):
        modules = [modules]

    raw_parts: List[str] = []
    for item in modules:
        if item is None:
            continue
        if isinstance(item, str):
            raw_parts.extend([p.strip().lower() for p in item.split(",") if p.strip()])

    logical: List[str] = []
    seen = set()
    for part in raw_parts:
        if part in LOGICAL_TO_RAW:
            key = part
        elif part in ("doc", "files", "agent_files"):
            key = "files"
        elif part in ("chat", "dirs", "library"):
            key = part
        else:
            continue
        if key not in seen:
            seen.add(key)
            logical.append(key)

    return logical or list(DEFAULT_LOGICAL_MODULES)


def _expand_raw_modules(logical_modules: Sequence[str]) -> List[str]:
    raw: List[str] = []
    seen = set()
    for logical in logical_modules:
        for module in LOGICAL_TO_RAW.get(logical, []):
            if module not in seen:
                seen.add(module)
                raw.append(module)
    return raw


def _stable_key(raw_module: str, item: Dict[str, Any]) -> str:
    logical_module = RAW_TO_LOGICAL.get(raw_module, raw_module)
    parent_key = str(item.get("parent_key", "") or "").strip()
    if parent_key:
        return f"{logical_module}:{parent_key}"

    if item.get("conv_id"):
        return f"{logical_module}:chat:{item['conv_id']}"

    if item.get("path"):
        return f"{logical_module}:path:{item['path']}"

    if item.get("file_path"):
        return f"{logical_module}:file:{item['file_path']}"

    if item.get("library_id") or item.get("doc_id"):
        return (
            f"{logical_module}:lib:{item.get('library_id', '')}"
            f"|doc:{item.get('doc_id', '')}"
            f"|title:{item.get('title', '')}"
        )

    return f"{logical_module}:title:{item.get('title', '')}|snippet:{item.get('snippet', '')}"


def _match_rank(item: Dict[str, Any]) -> int:
    match_type = str(item.get("match_type", "") or "")
    if match_type in TITLEISH_MATCH_TYPES:
        return 3
    if match_type == "content":
        return 2
    return 1


def _is_trash_path(item: Dict[str, Any]) -> bool:
    raw_path = str(item.get("path") or item.get("file_path") or "").replace("\\", "/").lower()
    return raw_path.startswith(".trash/") or "/.trash/" in raw_path or raw_path.startswith("agent_files/.trash/")


def _effective_score(item: Dict[str, Any]) -> float:
    score = float(item.get("score", 0.0) or 0.0)
    if _is_trash_path(item):
        return score - 40.0
    return score


def _sort_tuple(item: Dict[str, Any]) -> Tuple[float, int, int, float, float]:
    fts_rank = float(item.get("fts_rank", 0.0) or 0.0)
    return (
        _effective_score(item),
        1 if bool(item.get("has_title_hit", False)) else 0,
        int(item.get("hit_count", 1) or 1),
        -fts_rank,
        float(item.get("priority_hint", item.get("priority", 0.0)) or 0.0),
    )


def _sort_items(items: List[Dict[str, Any]]) -> None:
    items.sort(key=_sort_tuple, reverse=True)


def _choose_better_item(current: Dict[str, Any], candidate: Dict[str, Any]) -> Dict[str, Any]:
    c_rank = _match_rank(current)
    n_rank = _match_rank(candidate)

    if n_rank > c_rank:
        return candidate
    if n_rank < c_rank:
        return current

    c_sort = _sort_tuple(current)
    n_sort = _sort_tuple(candidate)
    if n_sort > c_sort:
        return candidate
    return current


def _merge_output_items(current: Dict[str, Any], candidate: Dict[str, Any]) -> Dict[str, Any]:
    chosen = _choose_better_item(current, candidate)
    merged = dict(chosen)

    merged["parent_key"] = str(
        chosen.get("parent_key")
        or current.get("parent_key")
        or candidate.get("parent_key")
        or ""
    )

    merged["matched_terms"] = _unique_keep_order(
        list(current.get("matched_terms", []) or []) +
        list(candidate.get("matched_terms", []) or [])
    )

    merged["has_title_hit"] = bool(current.get("has_title_hit", False) or candidate.get("has_title_hit", False))
    merged["has_content_hit"] = bool(current.get("has_content_hit", False) or candidate.get("has_content_hit", False))

    merged["hit_count"] = max(
        int(current.get("hit_count", 1) or 1),
        int(candidate.get("hit_count", 1) or 1),
    )

    merged["best_score"] = max(
        float(current.get("best_score", current.get("score", 0.0)) or 0.0),
        float(candidate.get("best_score", candidate.get("score", 0.0)) or 0.0),
    )
    merged["score"] = float(merged["best_score"])

    merged["best_priority"] = max(
        float(current.get("best_priority", current.get("priority", 0.0)) or 0.0),
        float(candidate.get("best_priority", candidate.get("priority", 0.0)) or 0.0),
    )
    merged["priority"] = float(merged["best_priority"])

    current_fts = float(current.get("best_fts_rank", current.get("fts_rank", 0.0)) or 0.0)
    candidate_fts = float(candidate.get("best_fts_rank", candidate.get("fts_rank", 0.0)) or 0.0)
    if current_fts == 0.0:
        merged["best_fts_rank"] = candidate_fts
    elif candidate_fts == 0.0:
        merged["best_fts_rank"] = current_fts
    else:
        merged["best_fts_rank"] = min(current_fts, candidate_fts)
    merged["fts_rank"] = float(merged["best_fts_rank"])

    source_modules = _unique_keep_order(
        list(current.get("source_modules", []) or []) +
        ([str(current.get("source_module", "") or "")] if str(current.get("source_module", "") or "") else []) +
        list(candidate.get("source_modules", []) or []) +
        ([str(candidate.get("source_module", "") or "")] if str(candidate.get("source_module", "") or "") else [])
    )
    if source_modules:
        merged["source_modules"] = source_modules

    if merged["has_content_hit"]:
        content_current = (
            str(current.get("match_type", "") or "") == "content" and
            str(current.get("snippet", "") or "").strip()
        )
        content_candidate = (
            str(candidate.get("match_type", "") or "") == "content" and
            str(candidate.get("snippet", "") or "").strip()
        )

        if content_current and content_candidate:
            better_content = _choose_better_item(current, candidate)
            merged["snippet"] = str(better_content.get("snippet", "") or merged.get("snippet", "") or "")
        elif content_candidate:
            merged["snippet"] = str(candidate.get("snippet", "") or merged.get("snippet", "") or "")
        elif content_current:
            merged["snippet"] = str(current.get("snippet", "") or merged.get("snippet", "") or "")

    merged["key"] = str(chosen.get("key") or current.get("key") or candidate.get("key") or "")
    merged["module"] = str(chosen.get("module") or current.get("module") or candidate.get("module") or "")
    merged["group"] = str(chosen.get("group") or current.get("group") or candidate.get("group") or "")
    merged["source_module"] = str(chosen.get("source_module") or current.get("source_module") or candidate.get("source_module") or "")

    return merged


def _normalize_item_for_output(raw_module: str, item: Dict[str, Any]) -> Dict[str, Any]:
    logical_module = RAW_TO_LOGICAL.get(raw_module, raw_module)
    out = dict(item)
    out["source_module"] = raw_module
    out["module"] = logical_module
    out["group"] = logical_module
    out["key"] = _stable_key(raw_module, out)

    if "hit_count" not in out:
        out["hit_count"] = 1

    if "has_title_hit" not in out:
        out["has_title_hit"] = str(out.get("match_type", "") or "") in TITLEISH_MATCH_TYPES

    if "has_content_hit" not in out:
        out["has_content_hit"] = str(out.get("match_type", "") or "") == "content"

    if "best_score" not in out:
        out["best_score"] = float(out.get("score", 0.0) or 0.0)

    if "best_priority" not in out:
        out["best_priority"] = float(out.get("priority", 0.0) or 0.0)

    if "best_fts_rank" not in out:
        out["best_fts_rank"] = float(out.get("fts_rank", 0.0) or 0.0)

    return out


def _merge_grouped(raw_grouped: Dict[str, List[Dict[str, Any]]], per_module_limit: int) -> Dict[str, Dict[str, Any]]:
    grouped_lists: Dict[str, List[Dict[str, Any]]] = {
        "chat": [],
        "dirs": [],
        "files": [],
        "library": [],
    }

    for raw_module, items in raw_grouped.items():
        logical = RAW_TO_LOGICAL.get(raw_module, raw_module)
        bucket = grouped_lists.setdefault(logical, [])
        for item in items:
            bucket.append(_normalize_item_for_output(raw_module, item))

    merged: Dict[str, Dict[str, Any]] = {}
    for logical, items in grouped_lists.items():
        uniq: Dict[str, Dict[str, Any]] = {}
        for item in items:
            key = item["key"]
            old = uniq.get(key)
            if old is None:
                uniq[key] = item
            else:
                uniq[key] = _merge_output_items(old, item)

        final_items = list(uniq.values())
        _sort_items(final_items)
        final_items = final_items[:per_module_limit]

        merged[logical] = {
            "module": logical,
            "items": final_items,
            "total": len(final_items),
            "raw_modules": list(LOGICAL_TO_RAW.get(logical, [logical])),
        }

    return merged


def _build_grouped_compat(grouped: Dict[str, Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    return {module: payload.get("items", []) for module, payload in grouped.items()}


def _flatten_grouped(grouped: Dict[str, Dict[str, Any]], limit: int) -> List[Dict[str, Any]]:
    flat: List[Dict[str, Any]] = []
    for payload in grouped.values():
        flat.extend(payload.get("items", []))

    uniq: Dict[str, Dict[str, Any]] = {}
    for item in flat:
        key = str(item.get("key", "") or "")
        old = uniq.get(key)
        if old is None:
            uniq[key] = item
        else:
            uniq[key] = _merge_output_items(old, item)

    results = list(uniq.values())
    _sort_items(results)
    return results[:limit]


def _empty_payload(query: str, logical_modules: Sequence[str]) -> Dict[str, Any]:
    grouped = {
        module: {
            "module": module,
            "items": [],
            "total": 0,
            "raw_modules": list(LOGICAL_TO_RAW.get(module, [module])),
        }
        for module in logical_modules
    }
    grouped_compat = _build_grouped_compat(grouped)
    return {
        "query": query,
        "query_norm": "",
        "query_compact": "",
        "query_tokens": [],
        "requested_modules": list(logical_modules),
        "raw_modules": _expand_raw_modules(logical_modules),
        "grouped": grouped,
        "grouped_results": grouped_compat,
        "results": [],
        "items": [],
        "totals": {module: 0 for module in grouped},
        "total": 0,
        "took_ms": 0,
        "sync": {
            "ok": True,
            "mode": "empty_query",
            "modules": {},
        },
    }


def _selected_index_total(conn, raw_modules: Sequence[str]) -> int:
    total = 0
    for module in raw_modules:
        try:
            total += int(module_entry_count(conn, module) or 0)
        except Exception:
            continue
    return total


def _sync_selected_modules(
    conn,
    base_path: Path,
    raw_modules: Sequence[str],
    mode: str,
) -> Dict[str, Any]:
    try:
        stats = sync_modules(conn, base_path, list(raw_modules), mode=mode)
        return {
            "modules": stats,
            "ok": True,
            "mode": mode,
        }
    except Exception as exc:
        return {
            "modules": {},
            "ok": False,
            "mode": mode,
            "error": str(exc),
        }


def _is_explicit_filename_query(raw_query: str) -> bool:
    q = str(raw_query or "").strip()
    if not q:
        return False

    lower = q.lower()

    if any(lower.endswith(suffix) for suffix in FILE_LIKE_SUFFIXES):
        return True
    if "/" in q or "\\" in q:
        return True
    if re.search(r"\.[a-z0-9]{1,8}$", lower):
        return True
    if "." in q and len(q) >= 4:
        return True
    if "_" in q or "-" in q:
        return True
    return False


def _is_probable_filename_query(raw_query: str, query_tokens: List[str], query_compact: str) -> bool:
    if _is_explicit_filename_query(raw_query):
        return True

    q = str(raw_query or "").strip()
    compact = str(query_compact or "").strip()

    if not q or not compact:
        return False
    if len(query_tokens) != 1:
        return False
    if " " in q or "\t" in q or "\n" in q:
        return False
    if len(compact) < 6:
        return False

    if any(ch.isdigit() for ch in q):
        return True

    for marker in ("文件", "文档", "笔记", "短文", "草稿", "说明", "报告", "拓扑"):
        if marker in q:
            return True

    return False


def _is_path_like_query(raw_query: str) -> bool:
    q = str(raw_query or "").strip()
    return "/" in q or "\\" in q


def _derive_filename_hints(raw_query: str, query_norm: str) -> List[str]:
    raw_q = str(raw_query or "").strip()
    norm_q = str(query_norm or "").strip()

    base_raw = re.split(r"[\\/]", raw_q)[-1].strip() if raw_q else ""
    base_norm = re.split(r"[\\/]", norm_q)[-1].strip() if norm_q else ""

    hints: List[str] = []
    if base_raw:
        hints.append(base_raw)
    if base_norm and base_norm != base_raw:
        hints.append(base_norm)

    primary = base_raw or base_norm
    if primary:
        if "." in primary and not primary.startswith("."):
            stem = primary.rsplit(".", 1)[0].strip()
            ext = primary.rsplit(".", 1)[1].strip().lower()
            if stem:
                hints.append(stem)
            if stem and ext:
                hints.append(f"{stem}.{ext}")
        else:
            hints.append(primary)

    compact = _compact_text(primary)
    if compact and compact != primary:
        hints.append(compact)

    return _unique_keep_order(hints)[:8]


def _derive_hot_sync_hints(
    raw_query: str,
    query_norm: str,
    query_compact: str,
    query_tokens: Sequence[str],
) -> List[str]:
    hints: List[str] = []
    raw = str(raw_query or "").strip()
    norm = str(query_norm or "").strip()
    compact = str(query_compact or "").strip()

    if raw:
        hints.append(raw)
    if norm and norm != raw:
        hints.append(norm)
    if compact and compact not in {raw, norm}:
        hints.append(compact)

    for token in query_tokens:
        token_text = str(token or "").strip()
        if len(token_text) >= 4:
            hints.append(token_text)

    return _unique_keep_order(hints)[:8]


def _effective_raw_modules_for_query(
    raw_modules: Sequence[str],
    filename_mode: bool,
    path_mode: bool,
    modules_explicit: bool,
) -> List[str]:
    if modules_explicit or not filename_mode:
        return list(raw_modules)

    narrowed: List[str] = []
    if path_mode and "dirs" in raw_modules:
        narrowed.append("dirs")

    for module in ("doc", "files"):
        if module in raw_modules:
            narrowed.append(module)

    return narrowed or list(raw_modules)


def _filename_module_priority(module: str, raw_query: str, path_mode: bool) -> int:
    lower = str(raw_query or "").strip().lower()

    if module == "files":
        score = 300
    elif module == "doc":
        score = 260
    elif module == "dirs":
        score = 160 if path_mode else 20
    elif module == "library":
        score = 40
    elif module == "chat":
        score = 10
    else:
        score = 0

    if "documents/" in lower or "\\documents\\" in lower or lower.startswith("documents/") or lower.startswith("documents\\"):
        if module == "doc":
            score += 500
        elif module == "files":
            score -= 80

    if "agent_files/" in lower or "\\agent_files\\" in lower or lower.startswith("agent_files/") or lower.startswith("agent_files\\"):
        if module == "files":
            score += 500
        elif module == "doc":
            score -= 80

    if any(lower.endswith(suffix) for suffix in FILE_LIKE_SUFFIXES):
        if module == "files":
            score += 40
        elif module == "doc":
            score += 20

    if path_mode and module == "dirs":
        score += 120

    return score


def _order_filename_modules(raw_modules: Sequence[str], raw_query: str, path_mode: bool) -> List[str]:
    enumerated = list(enumerate(list(raw_modules)))
    enumerated.sort(
        key=lambda pair: (
            _filename_module_priority(pair[1], raw_query, path_mode),
            -pair[0],
        ),
        reverse=True,
    )
    return [module for _, module in enumerated]


def _quick_sync_filename_module(
    conn,
    base_path: Path,
    module: str,
    filename_hints: Sequence[str],
    path_mode: bool,
    within_seconds: int,
    max_candidates: int,
) -> Dict[str, Any]:
    if module == "doc":
        return quick_sync_file_module(
            conn=conn,
            base_path=base_path,
            module="doc",
            root=base_path / "documents",
            recursive=True,
            within_seconds=within_seconds,
            max_candidates=max_candidates,
            name_hints=list(filename_hints),
            metadata_only=False,
        )

    if module == "files":
        return quick_sync_file_module(
            conn=conn,
            base_path=base_path,
            module="files",
            root=base_path / "agent_files",
            recursive=True,
            within_seconds=within_seconds,
            max_candidates=max_candidates,
            name_hints=list(filename_hints),
            metadata_only=False,
        )

    if module == "dirs":
        if path_mode:
            return quick_sync_dirs_module(
                conn=conn,
                base_path=base_path,
                within_seconds=within_seconds,
                max_candidates=max(16, max_candidates // 2),
            )
        return {
            "indexed": 0,
            "deleted": 0,
            "total": int(module_entry_count(conn, "dirs") or 0),
            "skipped": 1,
            "reason": "filename_query_skip_dirs",
            "candidates": 0,
        }

    return {
        "indexed": 0,
        "deleted": 0,
        "total": int(module_entry_count(conn, module) or 0),
        "skipped": 1,
        "reason": "filename_query_skip_module",
        "candidates": 0,
    }


def _query_one_module(
    conn,
    base_path: Path,
    module: str,
    raw_query: str,
    query_norm: str,
    query_compact: str,
    query_tokens: List[str],
    per_module_limit: int,
    fuzzy_enabled: bool,
    suppress_recall_fts: bool = False,
    suppress_recall_fts_reason: str = "",
) -> List[Dict[str, Any]]:
    try:
        return query_module_results(
            conn=conn,
            base_path=base_path,
            module=module,
            raw_query=raw_query,
            query_norm=query_norm,
            query_compact=query_compact,
            query_tokens=query_tokens,
            per_module_limit=per_module_limit,
            fuzzy_enabled=fuzzy_enabled,
            suppress_recall_fts=suppress_recall_fts,
            suppress_recall_fts_reason=suppress_recall_fts_reason,
        )
    except Exception:
        return []


def _run_filename_sequence(
    conn,
    base_path: Path,
    raw_modules: Sequence[str],
    raw_query: str,
    query_norm: str,
    query_compact: str,
    query_tokens: List[str],
    filename_hints: Sequence[str],
    path_mode: bool,
    per_module_limit: int,
    fuzzy_enabled: bool,
    within_seconds: int,
    max_candidates: int,
    stop_on_first_hit: bool,
) -> Tuple[Dict[str, List[Dict[str, Any]]], Dict[str, Any], int, int]:
    attempt_order = _order_filename_modules(raw_modules, raw_query, path_mode)
    raw_grouped: Dict[str, List[Dict[str, Any]]] = {module: [] for module in raw_modules}
    stats: Dict[str, Dict[str, Any]] = {}
    attempted_modules: List[str] = []
    module_query_hits: Dict[str, int] = {}
    stopped_after_module = ""
    stop_reason = "exhausted_attempt_order"

    sync_elapsed_ms = 0
    query_elapsed_ms = 0

    for idx, module in enumerate(attempt_order):
        attempted_modules.append(module)

        one_sync_started = time.time()
        stats[module] = _quick_sync_filename_module(
            conn=conn,
            base_path=base_path,
            module=module,
            filename_hints=filename_hints,
            path_mode=path_mode,
            within_seconds=within_seconds,
            max_candidates=max_candidates,
        )
        sync_elapsed_ms += int((time.time() - one_sync_started) * 1000)

        one_query_started = time.time()
        items = _query_one_module(
            conn=conn,
            base_path=base_path,
            module=module,
            raw_query=raw_query,
            query_norm=query_norm,
            query_compact=query_compact,
            query_tokens=query_tokens,
            per_module_limit=per_module_limit,
            fuzzy_enabled=fuzzy_enabled,
        )
        query_elapsed_ms += int((time.time() - one_query_started) * 1000)

        raw_grouped[module] = items
        module_query_hits[module] = len(items)

        if stop_on_first_hit and items:
            stopped_after_module = module
            stop_reason = "first_hit_stop"

            for rest in attempt_order[idx + 1:]:
                if rest not in stats:
                    stats[rest] = {
                        "indexed": 0,
                        "deleted": 0,
                        "total": int(module_entry_count(conn, rest) or 0),
                        "skipped": 1,
                        "reason": "sequence_early_stop",
                        "candidates": 0,
                    }
            break

    if not stopped_after_module and stop_on_first_hit:
        stop_reason = "no_hit_continue_exhausted"

    try:
        conn.commit()
    except Exception:
        pass

    sync_meta = {
        "modules": stats,
        "ok": True,
        "mode": "filename_hint_sequence",
        "reason": "filename_query_incremental_sequential",
        "filename_hints": list(filename_hints),
        "within_seconds": int(within_seconds),
        "max_candidates_per_module": int(max_candidates),
        "attempt_order": list(attempt_order),
        "attempted_modules": list(attempted_modules),
        "stopped_after_module": stopped_after_module,
        "stop_reason": stop_reason,
        "module_query_hits": module_query_hits,
    }
    return raw_grouped, sync_meta, sync_elapsed_ms, query_elapsed_ms


def _should_run_hot_quick_sync(raw_query: str, query_tokens: List[str]) -> bool:
    q = str(raw_query or "").strip().lower()
    if not q:
        return False

    if _is_explicit_filename_query(q):
        return False

    if len(query_tokens) != 1:
        return False

    token = str(query_tokens[0] or "").strip()
    if len(token) < 10:
        return False

    if any(ch.isdigit() for ch in token):
        return True

    return False


def _query_selected_modules(
    conn,
    base_path: Path,
    raw_modules: Sequence[str],
    raw_query: str,
    query_norm: str,
    query_compact: str,
    query_tokens: List[str],
    per_module_limit: int,
    fuzzy_enabled: bool,
    suppress_recall_after_chat_title: bool = True,
) -> Dict[str, List[Dict[str, Any]]]:
    grouped: Dict[str, List[Dict[str, Any]]] = {str(module): [] for module in raw_modules}
    ordered_modules = [str(module) for module in raw_modules]

    if suppress_recall_after_chat_title and "chat" in ordered_modules:
        query_order = ["chat"] + [module for module in ordered_modules if module != "chat"]
    else:
        query_order = list(ordered_modules)

    recall_suppressed_modules = set()

    for module in query_order:
        suppress_recall = str(module or "") in recall_suppressed_modules
        grouped[module] = _query_one_module(
            conn=conn,
            base_path=base_path,
            module=module,
            raw_query=raw_query,
            query_norm=query_norm,
            query_compact=query_compact,
            query_tokens=query_tokens,
            per_module_limit=per_module_limit,
            fuzzy_enabled=fuzzy_enabled,
            suppress_recall_fts=suppress_recall,
            suppress_recall_fts_reason="chat_title_satisfied" if suppress_recall else "",
        )

        if (
            module == "chat"
            and suppress_recall_after_chat_title
            and _strong_chat_title_satisfied(
                raw_query=raw_query,
                query_compact=query_compact,
                query_tokens=query_tokens,
                chat_items=grouped.get("chat", []),
            )
        ):
            recall_suppressed_modules.update({"dirs", "doc", "files", "agent_files"})

    return grouped

def _coerce_int(value: Any, fallback: int) -> int:
    try:
        return int(value)
    except Exception:
        return int(fallback)


def _coerce_bool(value: Any, fallback: bool) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return fallback

    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "on"}:
        return True
    if text in {"0", "false", "no", "off"}:
        return False
    return fallback


def _extract_mapping(value: Any) -> Optional[Dict[str, Any]]:
    if isinstance(value, Mapping):
        return dict(value)

    if isinstance(value, str):
        text = value.strip()
        if text.startswith("{") and text.endswith("}"):
            try:
                parsed = ast.literal_eval(text)
                if isinstance(parsed, Mapping):
                    return dict(parsed)
            except Exception:
                return None

    return None


def _first_non_empty(*values: Any) -> str:
    for value in values:
        text = str(value or "").strip()
        if text:
            return text
    return ""


__all__ = [
    "DEFAULT_LOGICAL_MODULES",
    "LOGICAL_TO_RAW",
    "RAW_TO_LOGICAL",
    "HOT_QUERY_QUICK_SYNC_SECONDS",
    "HOT_QUERY_QUICK_SYNC_MAX_CANDIDATES",
    "FILENAME_QUERY_MAX_CANDIDATES",
    "_compact_text",
    "_split_tokens",
    "_normalize_modules",
    "_expand_raw_modules",
    "_merge_grouped",
    "_build_grouped_compat",
    "_flatten_grouped",
    "_empty_payload",
    "_selected_index_total",
    "_sync_selected_modules",
    "_is_probable_filename_query",
    "_is_path_like_query",
    "_derive_filename_hints",
    "_derive_hot_sync_hints",
    "_effective_raw_modules_for_query",
    "_run_filename_sequence",
    "_should_run_hot_quick_sync",
    "_query_selected_modules",
    "_coerce_int",
    "_coerce_bool",
    "_extract_mapping",
    "_first_non_empty",
]

