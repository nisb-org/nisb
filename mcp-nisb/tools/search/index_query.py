#!/usr/bin/env python3

import re
import sqlite3
from pathlib import Path
from typing import Any, Dict, List

from .index_query_fetchers import (
    analyze_search_query,
    build_content_fts_exprs,
    build_recall_fts_exprs,
    build_title_fts_exprs,
    classify_query,
    fetch_chat_title_fast,
    fetch_direct_title,
    fetch_filename_fast,
    fetch_fts_content,
    fetch_fts_content_like,
    fetch_fts_recall,
    fetch_fts_title,
    recall_fts_available,
    is_filenameish,
)
from .index_query_scoring import (
    finalize_parent_results,
    merge_parent_batch,
    summarize_parent_hits,
)

_FILE_FAMILY_CAMEL_RE = re.compile(
    r"^(?:[A-Z][a-z0-9]+|[a-z][a-z0-9]+)(?:[A-Z][a-z0-9]+){1,}$"
)
_FILE_FAMILY_EXT_RE = re.compile(r"\.[A-Za-z0-9]{1,10}$")
_RELAXED_SEP_RE = re.compile(r"[\/\\._-]+")
_MULTI_SPACE_RE = re.compile(r"\s+")

_LAST_QUERY_OBSERVABILITY: Dict[str, Dict[str, Any]] = {}


def clear_query_observability() -> None:
    _LAST_QUERY_OBSERVABILITY.clear()


def get_query_observability_snapshot() -> Dict[str, Dict[str, Any]]:
    out: Dict[str, Dict[str, Any]] = {}
    for module, payload in _LAST_QUERY_OBSERVABILITY.items():
        if not isinstance(payload, dict):
            continue
        out[str(module)] = {
            "query_class": str(payload.get("query_class") or ""),
            "lane_counts": dict(payload.get("lane_counts") or {}),
            "skipped_lanes": list(payload.get("skipped_lanes") or []),
            "parent_merge_before": int(payload.get("parent_merge_before") or 0),
            "parent_merge_after": int(payload.get("parent_merge_after") or 0),
            "flags": dict(payload.get("flags") or {}),
        }
    return out


def _new_query_observability(module: str, query_kind: str) -> Dict[str, Any]:
    return {
        "module": str(module or ""),
        "query_class": str(query_kind or ""),
        "lane_counts": {},
        "skipped_lanes": [],
        "parent_merge_before": 0,
        "parent_merge_after": 0,
        "flags": {},
    }


def _record_lane_count(obs: Dict[str, Any], lane: str, rows: Any = None, count: Any = None) -> None:
    if not isinstance(obs, dict):
        return
    lane_counts = obs.setdefault("lane_counts", {})
    if not isinstance(lane_counts, dict):
        lane_counts = {}
        obs["lane_counts"] = lane_counts
    if count is None:
        try:
            value = len(rows or [])
        except Exception:
            value = 0
    else:
        try:
            value = int(count or 0)
        except Exception:
            value = 0
    lane_counts[str(lane or "")] = int(value)


def _record_skipped_lane(obs: Dict[str, Any], lane: str, reason: str) -> None:
    if not isinstance(obs, dict):
        return
    skipped = obs.setdefault("skipped_lanes", [])
    if not isinstance(skipped, list):
        skipped = []
        obs["skipped_lanes"] = skipped
    value = f"{str(lane or '').strip()}:{str(reason or '').strip()}"
    if value and value not in skipped:
        skipped.append(value)


def _store_query_observability(module: str, obs: Dict[str, Any]) -> None:
    if isinstance(obs, dict):
        _LAST_QUERY_OBSERVABILITY[str(module or "")] = obs


def _finalize_observed_results(
    module: str,
    parent_map: Dict[str, Dict[str, Any]],
    per_module_limit: int,
    obs: Dict[str, Any],
) -> List[Dict[str, Any]]:
    before = len(parent_map or {})
    results = finalize_parent_results(parent_map, per_module_limit)
    if isinstance(obs, dict):
        obs["parent_merge_before"] = int(before)
        obs["parent_merge_after"] = int(len(results or []))
        _store_query_observability(module, obs)
    return results



def _ceil_ratio(value: int, ratio: float, minimum: int = 1) -> int:
    if value <= 0:
        return int(minimum)
    scaled = int((float(value) * float(ratio)) + 0.9999)
    return max(int(minimum), scaled)


def _is_recall_sensitive_module(module: str) -> bool:
    return module in {"doc", "files"}


def _recall_stage_module_enabled(module: str, query_kind: str) -> bool:
    if module in {"doc", "files", "dirs"}:
        return True
    if module == "chat" and query_kind == "short_cjk":
        return True
    return False


def _short_cjk_direct_stop_limit(module: str, per_module_limit: int) -> int:
    if module in {"doc", "files"}:
        return max(6, _ceil_ratio(per_module_limit, 0.4, minimum=6))
    if module == "library":
        return max(5, _ceil_ratio(per_module_limit, 0.35, minimum=5))
    return max(4, _ceil_ratio(per_module_limit, 0.3, minimum=4))


def _short_cjk_direct_content_trigger_limit(module: str, per_module_limit: int) -> int:
    if module in {"doc", "files"}:
        return max(4, _ceil_ratio(per_module_limit, 0.3, minimum=4))
    if module == "library":
        return max(3, _ceil_ratio(per_module_limit, 0.25, minimum=3))
    if module == "chat":
        return max(3, _ceil_ratio(per_module_limit, 0.25, minimum=3))
    return max(2, _ceil_ratio(per_module_limit, 0.2, minimum=2))


def _compute_stage_limits(
    per_module_limit: int,
    query_kind: str,
    allow_title_fts: bool,
    allow_content_fts: bool,
    allow_direct_content_like: bool,
) -> Dict[str, int]:
    if query_kind == "long_nl":
        return {
            "direct_title_limit": max(per_module_limit * 8, 32),
            "title_limit": 0,
            "content_limit": 0,
            "direct_content_limit": 0,
        }

    if query_kind == "long_phrase":
        return {
            "direct_title_limit": max(per_module_limit * 6, 24),
            "title_limit": max(per_module_limit * 4, 16) if allow_title_fts else 0,
            "content_limit": 0,
            "direct_content_limit": 0,
        }

    if query_kind == "short_cjk":
        return {
            "direct_title_limit": max(per_module_limit * 6, 24),
            "title_limit": 0,
            "content_limit": 0,
            "direct_content_limit": max(per_module_limit * 6, 24) if allow_direct_content_like else 0,
        }

    if query_kind == "filename":
        return {
            "direct_title_limit": max(per_module_limit * 8, 32),
            "title_limit": max(per_module_limit * 4, 16) if allow_title_fts else 0,
            "content_limit": 0,
            "direct_content_limit": max(per_module_limit * 6, 24) if allow_direct_content_like else 0,
        }

    if query_kind in {"short", "symbol_heavy"}:
        return {
            "direct_title_limit": max(per_module_limit * 6, 24),
            "title_limit": 0,
            "content_limit": 0,
            "direct_content_limit": 0,
        }

    if query_kind == "phrase":
        return {
            "direct_title_limit": max(per_module_limit * 5, 24),
            "title_limit": max(per_module_limit * 4, 16) if allow_title_fts else 0,
            "content_limit": max(per_module_limit * 4, 16) if allow_content_fts else 0,
            "direct_content_limit": max(per_module_limit * 3, 12) if allow_direct_content_like else 0,
        }

    return {
        "direct_title_limit": max(per_module_limit * 5, 24),
        "title_limit": max(per_module_limit * 4, 16) if allow_title_fts else 0,
        "content_limit": max(per_module_limit * 4, 16) if allow_content_fts else 0,
        "direct_content_limit": max(per_module_limit * 3, 12) if allow_direct_content_like else 0,
    }


def _batch_parent_limit(per_module_limit: int) -> int:
    return max(per_module_limit * 2, 10)


def _contains_cjk(value: str) -> bool:
    for ch in str(value or ""):
        code = ord(ch)
        if (
            0x4E00 <= code <= 0x9FFF
            or 0x3400 <= code <= 0x4DBF
            or 0x20000 <= code <= 0x2A6DF
            or 0x2A700 <= code <= 0x2B73F
            or 0xF900 <= code <= 0xFAFF
        ):
            return True
    return False


def _detect_file_family_mode(
    module: str,
    raw_query: str,
    query_kind: str,
    query_tokens: List[str],
    query_compact: str,
) -> str:
    if module not in {"doc", "files", "dirs"}:
        return ""

    q = str(raw_query or "").strip()
    compact = str(query_compact or "").strip()

    if not q:
        return ""
    if len(q) < 3 or len(q) > 96:
        return ""
    if len(query_tokens) > 2:
        return ""
    if query_kind in {"long_nl", "long_phrase", "short_cjk", "symbol_heavy"}:
        return ""
    if any(ch.isspace() for ch in q):
        return ""
    if _contains_cjk(q):
        return ""

    normalized = q.replace("\\", "/").strip()
    trimmed = normalized.rstrip(". ").strip()
    basename = Path(trimmed.rstrip("/")).name.strip() if trimmed else ""
    candidate = basename or trimmed or normalized

    if "/" in normalized:
        return "strong"
    if normalized.endswith("."):
        return "strong"
    if "." in candidate and _FILE_FAMILY_EXT_RE.search(candidate):
        return "strong"

    if _FILE_FAMILY_CAMEL_RE.match(q):
        return "weak"

    if compact and compact != q and len(compact) >= 3 and "." in q:
        return "strong"

    return ""


def _is_dotted_filename_query(raw_query: str) -> bool:
    q = str(raw_query or "").strip()
    if not q:
        return False
    if any(ch.isspace() for ch in q):
        return False
    if "/" in q or "\\" in q:
        return False
    if q.endswith("."):
        return True
    if "." in q and len(q) >= 4:
        return True
    return False


def _should_relax_filename_recall(
    module: str,
    raw_query: str,
    query_tokens: List[str],
    query_compact: str,
) -> bool:
    if module not in {"doc", "files", "library"}:
        return False

    q = str(raw_query or "").strip()
    compact = str(query_compact or "").strip()
    tokens = [str(t or "").strip() for t in query_tokens if str(t or "").strip()]

    if not q:
        return False
    if _contains_cjk(q):
        return False
    if not _is_dotted_filename_query(q):
        return False
    if len(tokens) > 3:
        return False
    if compact and len(compact) > 64:
        return False

    return True


def _build_file_family_aliases(
    raw_query: str,
    query_norm: str,
    query_compact: str,
) -> List[str]:
    q = str(raw_query or "").strip()
    norm = str(query_norm or "").strip()
    compact = str(query_compact or "").strip()

    aliases: List[str] = []
    seen = set()

    def _push(value: str) -> None:
        v = str(value or "").strip()
        if not v or v in seen:
            return
        seen.add(v)
        aliases.append(v)

    trimmed = q.rstrip(". ").strip()
    pathish = q.replace("\\", "/").rstrip("/")
    basename = Path(pathish).name.strip() if pathish else ""
    stem_source = trimmed or basename or q
    stem = Path(stem_source.rstrip(".")).stem.strip() if stem_source else ""

    _push(q)
    _push(trimmed)
    _push(basename)
    _push(stem)

    if trimmed and "." not in trimmed:
        _push(trimmed + ".")

    _push(norm)
    _push(compact)

    return aliases[:6]


def _build_relaxed_separator_query(raw_query: str) -> str:
    q = str(raw_query or "").strip()
    if not q:
        return ""
    if _contains_cjk(q):
        return ""
    replaced = _RELAXED_SEP_RE.sub(" ", q)
    replaced = _MULTI_SPACE_RE.sub(" ", replaced).strip(" ._-\\/")

    if not replaced:
        return ""
    if replaced == q:
        return ""
    if len(replaced) < 2 or len(replaced) > 96:
        return ""
    return replaced



_CODE_QUERY_EXTS = {
    "js", "jsx", "ts", "tsx", "vue", "py", "go", "rs", "java", "kt",
    "php", "rb", "c", "cc", "cpp", "h", "hpp", "cs", "swift", "mjs",
    "cjs", "json", "yaml", "yml", "css", "scss", "html", "svelte",
}

_RECALL_MEDIA_NOISE_EXTS = {
    "png", "jpg", "jpeg", "gif", "webp", "svg", "ico", "bmp", "tif",
    "tiff", "avif", "heic", "mp4", "mov", "avi", "mkv", "webm", "mp3",
    "wav", "flac", "ogg",
}


def _query_code_exts(raw_query: str) -> set:
    q = str(raw_query or "").lower()
    return {
        m.group(1)
        for m in re.finditer(r"\.([a-z0-9]{1,8})(?=$|[^a-z0-9])", q)
        if m.group(1) in _CODE_QUERY_EXTS
    }


def _row_text_for_noise_filter(row: sqlite3.Row) -> str:
    parts: List[str] = []
    for key in ("title", "path", "parent_path"):
        try:
            value = row[key]
        except Exception:
            value = ""
        if value:
            parts.append(str(value))
    return " ".join(parts).lower()


def _path_ext_from_row_text(text: str) -> str:
    text = str(text or "").split("?", 1)[0].split("#", 1)[0].rstrip(" .")
    name = Path(text.replace("\\", "/")).name.lower()
    if "." not in name:
        return ""
    ext = name.rsplit(".", 1)[-1]
    if 1 <= len(ext) <= 8 and ext.isalnum():
        return ext
    return ""


def _is_tier0_file_recall_row(row: sqlite3.Row) -> bool:
    try:
        tier = int(row["recall_tier"] or 0)
    except Exception:
        tier = 0
    try:
        matched_source_kind = str(row["matched_source_kind"] or "")
    except Exception:
        matched_source_kind = ""
    try:
        source_kind = str(row["source_kind"] or "")
    except Exception:
        source_kind = ""
    return tier == 0 and matched_source_kind == "files_file" and source_kind == "files_file"


def _filter_filename_fallback_recall_rows(
    rows: List[sqlite3.Row],
    raw_query: str,
) -> List[sqlite3.Row]:
    code_exts = _query_code_exts(raw_query)
    if not code_exts:
        return rows

    out: List[sqlite3.Row] = []
    for row in rows:
        text = _row_text_for_noise_filter(row)
        row_ext = _path_ext_from_row_text(text)
        has_requested_ext = any(f".{ext}" in text for ext in code_exts)

        if (
            _is_tier0_file_recall_row(row)
            and row_ext in _RECALL_MEDIA_NOISE_EXTS
            and not has_requested_ext
        ):
            continue

        out.append(row)

    return out



def _merge_row_lists(primary: List[sqlite3.Row], secondary: List[sqlite3.Row], limit: int) -> List[sqlite3.Row]:
    out: List[sqlite3.Row] = []
    seen = set()

    for row in list(primary) + list(secondary):
        key = str(row["item_key"] or "")
        uniq = key or str(id(row))
        if uniq in seen:
            continue
        seen.add(uniq)
        out.append(row)
        if len(out) >= limit:
            break

    return out


def _merge_stage_rows(
    module: str,
    parent_map: Dict[str, Dict[str, Any]],
    seen_row_keys: set,
    rows: List[sqlite3.Row],
    query_norm: str,
    query_compact: str,
    query_tokens: List[str],
    fuzzy_enabled: bool,
    per_module_limit: int,
) -> Dict[str, Dict[str, Any]]:
    return merge_parent_batch(
        module=module,
        rows=rows,
        query_norm=query_norm,
        query_compact=query_compact,
        query_tokens=query_tokens,
        fuzzy_enabled=fuzzy_enabled,
        existing=parent_map,
        seen_row_keys=seen_row_keys,
        batch_parent_limit=_batch_parent_limit(per_module_limit),
    )


def _seed_chat_title_candidates(
    conn: sqlite3.Connection,
    parent_map: Dict[str, Dict[str, Any]],
    seen_row_keys: set,
    guarded_raw_query: str,
    guarded_query_norm: str,
    guarded_query_compact: str,
    guarded_query_tokens: List[str],
    per_module_limit: int,
) -> Dict[str, Dict[str, Any]]:
    exact_rows = fetch_chat_title_fast(
        conn=conn,
        raw_query=guarded_raw_query,
        query_norm=guarded_query_norm,
        query_compact=guarded_query_compact,
        limit=max(per_module_limit * 8, 32),
        exact_only=True,
    )
    parent_map = _merge_stage_rows(
        module="chat",
        parent_map=parent_map,
        seen_row_keys=seen_row_keys,
        rows=list(exact_rows),
        query_norm=guarded_query_norm,
        query_compact=guarded_query_compact,
        query_tokens=guarded_query_tokens,
        fuzzy_enabled=False,
        per_module_limit=per_module_limit,
    )

    if len(parent_map) < max(2, min(per_module_limit, 6)):
        fallback_rows = fetch_chat_title_fast(
            conn=conn,
            raw_query=guarded_raw_query,
            query_norm=guarded_query_norm,
            query_compact=guarded_query_compact,
            limit=max(per_module_limit * 10, 40),
            exact_only=False,
        )
        parent_map = _merge_stage_rows(
            module="chat",
            parent_map=parent_map,
            seen_row_keys=seen_row_keys,
            rows=list(fallback_rows),
            query_norm=guarded_query_norm,
            query_compact=guarded_query_compact,
            query_tokens=guarded_query_tokens,
            fuzzy_enabled=False,
            per_module_limit=per_module_limit,
        )

    return parent_map


def _should_stop_after_direct_stage(
    module: str,
    query_kind: str,
    filenameish: bool,
    parent_map: Dict[str, Dict[str, Any]],
    per_module_limit: int,
) -> bool:
    stats = summarize_parent_hits(parent_map)
    total = int(stats.get("total", 0) or 0)
    titleish = int(stats.get("titleish", 0) or 0)
    strong_titleish = int(stats.get("strong_titleish", 0) or 0)

    if total <= 0:
        return False

    if filenameish:
        return strong_titleish >= max(2, min(per_module_limit, 4))

    if module == "chat":
        if query_kind in {"short", "short_cjk", "symbol_heavy"}:
            return strong_titleish >= _ceil_ratio(per_module_limit, 0.5, minimum=2)
        if query_kind in {"long_nl", "long_phrase"}:
            return titleish >= _ceil_ratio(per_module_limit, 0.5, minimum=2)
        return (
            total >= per_module_limit
            and strong_titleish >= _ceil_ratio(per_module_limit, 0.4, minimum=2)
        )

    if module == "dirs":
        if query_kind in {"short", "short_cjk", "symbol_heavy"}:
            return strong_titleish >= _ceil_ratio(per_module_limit, 0.6, minimum=2)
        return (
            total >= per_module_limit
            and strong_titleish >= _ceil_ratio(per_module_limit, 0.5, minimum=2)
        )

    if _is_recall_sensitive_module(module):
        if query_kind == "short_cjk":
            return (
                total >= _short_cjk_direct_stop_limit(module, per_module_limit)
                and (
                    strong_titleish >= _ceil_ratio(per_module_limit, 0.2, minimum=2)
                    or titleish >= _ceil_ratio(per_module_limit, 0.3, minimum=3)
                )
            )
        return False

    if query_kind in {"short", "short_cjk", "symbol_heavy"}:
        return strong_titleish >= _ceil_ratio(per_module_limit, 0.5, minimum=2)

    if query_kind in {"long_nl", "long_phrase"}:
        return titleish >= _ceil_ratio(per_module_limit, 0.5, minimum=2)

    return (
        total >= per_module_limit
        and strong_titleish >= _ceil_ratio(per_module_limit, 0.4, minimum=2)
    )


def _should_stop_after_title_stage(
    module: str,
    query_kind: str,
    parent_map: Dict[str, Dict[str, Any]],
    per_module_limit: int,
) -> bool:
    stats = summarize_parent_hits(parent_map)
    total = int(stats.get("total", 0) or 0)
    titleish = int(stats.get("titleish", 0) or 0)
    strong_titleish = int(stats.get("strong_titleish", 0) or 0)

    if total >= per_module_limit:
        return True

    if _is_recall_sensitive_module(module):
        if query_kind == "short_cjk":
            return (
                total >= _ceil_ratio(per_module_limit, 0.5, minimum=8)
                and titleish >= _ceil_ratio(per_module_limit, 0.25, minimum=3)
            )
        if query_kind in {"phrase", "filename"}:
            return (
                total >= _ceil_ratio(per_module_limit, 0.8, minimum=6)
                and strong_titleish >= _ceil_ratio(per_module_limit, 0.3, minimum=2)
            )
        return False

    if module == "chat" and query_kind in {"long_nl", "long_phrase"}:
        return titleish >= _ceil_ratio(per_module_limit, 0.6, minimum=2)

    if query_kind in {"long_nl", "long_phrase"}:
        return titleish >= _ceil_ratio(per_module_limit, 0.6, minimum=2)

    return strong_titleish >= _ceil_ratio(per_module_limit, 0.6, minimum=2)


def _should_run_content_stage(
    module: str,
    query_kind: str,
    filenameish: bool,
    parent_map: Dict[str, Dict[str, Any]],
    per_module_limit: int,
) -> bool:
    stats = summarize_parent_hits(parent_map)
    total = int(stats.get("total", 0) or 0)
    strong_titleish = int(stats.get("strong_titleish", 0) or 0)

    if filenameish:
        return False

    if query_kind == "symbol_heavy":
        return False

    if _is_recall_sensitive_module(module):
        if query_kind in {"short", "short_cjk"}:
            return total < per_module_limit
        if query_kind in {"long_nl", "long_phrase"}:
            return total < per_module_limit
        return total < per_module_limit or strong_titleish < per_module_limit

    if query_kind in {"short", "short_cjk"}:
        return total < _ceil_ratio(per_module_limit, 0.5, minimum=2)

    if query_kind in {"long_nl", "long_phrase"}:
        return module == "chat" and total < _ceil_ratio(per_module_limit, 0.6, minimum=2)

    return (
        total < per_module_limit
        and strong_titleish < _ceil_ratio(per_module_limit, 0.6, minimum=2)
    )


def _should_run_recall_stage(
    module: str,
    query_kind: str,
    filenameish: bool,
    parent_map: Dict[str, Dict[str, Any]],
    per_module_limit: int,
) -> bool:
    if filenameish:
        return False

    if not _recall_stage_module_enabled(module, query_kind):
        return False

    if query_kind in {"symbol_heavy", "filename"}:
        return module in {"doc", "files"} and filenameish and not parent_map

    stats = summarize_parent_hits(parent_map)
    total = int(stats.get("total", 0) or 0)
    strong_titleish = int(stats.get("strong_titleish", 0) or 0)

    if module == "chat" and query_kind == "short_cjk":
        return total <= 0
    
    if query_kind == "short_cjk":
        return total < _ceil_ratio(per_module_limit, 0.4, minimum=4)

    if query_kind in {"long_nl", "long_phrase"}:
        return total < _ceil_ratio(per_module_limit, 0.8, minimum=4)

    if query_kind in {"keyword", "phrase", "short"}:
        return (
            total < _ceil_ratio(per_module_limit, 0.5, minimum=4)
            or strong_titleish < _ceil_ratio(per_module_limit, 0.35, minimum=2)
        )

    return False



def _should_run_direct_content_like_stage(
    module: str,
    query_kind: str,
    filenameish: bool,
    allow_direct_content_like: bool,
    parent_map: Dict[str, Dict[str, Any]],
    per_module_limit: int,
) -> bool:
    if not allow_direct_content_like:
        return False

    stats = summarize_parent_hits(parent_map)
    total = int(stats.get("total", 0) or 0)

    if filenameish:
        return total < max(2, min(per_module_limit, 4))

    if _is_recall_sensitive_module(module):
        if query_kind == "short_cjk":
            return total < _short_cjk_direct_content_trigger_limit(module, per_module_limit)
        if query_kind == "short":
            return total < _ceil_ratio(per_module_limit, 0.5, minimum=4)
        if query_kind in {"filename", "phrase"}:
            return total < _ceil_ratio(per_module_limit, 0.7, minimum=4)
        if query_kind in {"long_nl", "long_phrase"}:
            return total < _ceil_ratio(per_module_limit, 0.8, minimum=4)
        return total < _ceil_ratio(per_module_limit, 0.8, minimum=4)

    if query_kind == "short_cjk":
        return total < _ceil_ratio(per_module_limit, 0.35, minimum=3)

    if query_kind in {"short", "symbol_heavy", "filename"}:
        return total < _ceil_ratio(per_module_limit, 0.4, minimum=2)

    if query_kind in {"long_nl", "long_phrase"}:
        return module == "chat" and total < _ceil_ratio(per_module_limit, 0.6, minimum=2)

    return total < _ceil_ratio(per_module_limit, 0.8, minimum=2)


def _run_relaxed_keyword_fallback(
    conn: sqlite3.Connection,
    module: str,
    raw_query: str,
    per_module_limit: int,
    fuzzy_enabled: bool,
    parent_map: Dict[str, Dict[str, Any]],
    seen_row_keys: set,
) -> Dict[str, Dict[str, Any]]:
    if module not in {"doc", "files", "library"}:
        return parent_map

    relaxed_raw = _build_relaxed_separator_query(raw_query)
    if not relaxed_raw:
        return parent_map

    relaxed_guard = analyze_search_query(relaxed_raw)
    relaxed_raw_query = str(relaxed_guard.get("raw_query_used") or relaxed_raw or "").strip()
    relaxed_query_norm = str(relaxed_guard.get("query_norm") or "").strip()
    relaxed_query_compact = str(relaxed_guard.get("query_compact") or "").strip()
    relaxed_query_tokens = list(relaxed_guard.get("query_tokens_used") or [])
    relaxed_fts_tokens = list(relaxed_guard.get("query_tokens_fts") or relaxed_query_tokens)

    if not relaxed_raw_query and not relaxed_query_norm and not relaxed_query_compact:
        return parent_map

    relaxed_query_kind = str(
        relaxed_guard.get("query_class")
        or classify_query(relaxed_raw_query, relaxed_query_compact, relaxed_query_tokens)
        or "keyword"
    )

    relaxed_allow_title_fts = True
    relaxed_allow_content_fts = True
    relaxed_allow_direct_content_like = True

    relaxed_limits = _compute_stage_limits(
        per_module_limit=per_module_limit,
        query_kind=relaxed_query_kind,
        allow_title_fts=relaxed_allow_title_fts,
        allow_content_fts=relaxed_allow_content_fts,
        allow_direct_content_like=relaxed_allow_direct_content_like,
    )

    relaxed_limits["direct_title_limit"] = max(relaxed_limits["direct_title_limit"], max(per_module_limit * 6, 24))
    relaxed_limits["title_limit"] = max(relaxed_limits["title_limit"], max(per_module_limit * 6, 24))
    relaxed_limits["content_limit"] = max(relaxed_limits["content_limit"], max(per_module_limit * 8, 32))
    relaxed_limits["direct_content_limit"] = max(relaxed_limits["direct_content_limit"], max(per_module_limit * 6, 24))

    local_fuzzy_enabled = bool(fuzzy_enabled)
    if relaxed_query_kind in {"short", "short_cjk", "long_nl", "filename"}:
        local_fuzzy_enabled = False

    direct_title_rows = fetch_direct_title(
        conn=conn,
        module=module,
        raw_query=relaxed_raw_query,
        query_norm=relaxed_query_norm,
        query_compact=relaxed_query_compact,
        limit=relaxed_limits["direct_title_limit"],
        explicit_filename=False,
    )
    parent_map = _merge_stage_rows(
        module=module,
        parent_map=parent_map,
        seen_row_keys=seen_row_keys,
        rows=list(direct_title_rows),
        query_norm=relaxed_query_norm,
        query_compact=relaxed_query_compact,
        query_tokens=relaxed_query_tokens,
        fuzzy_enabled=local_fuzzy_enabled,
        per_module_limit=per_module_limit,
    )

    if relaxed_allow_title_fts and relaxed_limits["title_limit"] > 0:
        title_exprs = build_title_fts_exprs(
            relaxed_query_norm,
            relaxed_query_compact,
            relaxed_fts_tokens or relaxed_query_tokens,
            relaxed_query_kind,
        )
        if title_exprs:
            title_rows = fetch_fts_title(conn, module, title_exprs, relaxed_limits["title_limit"])
            parent_map = _merge_stage_rows(
                module=module,
                parent_map=parent_map,
                seen_row_keys=seen_row_keys,
                rows=list(title_rows),
                query_norm=relaxed_query_norm,
                query_compact=relaxed_query_compact,
                query_tokens=relaxed_query_tokens,
                fuzzy_enabled=local_fuzzy_enabled,
                per_module_limit=per_module_limit,
            )

    if relaxed_allow_content_fts and relaxed_limits["content_limit"] > 0 and _should_run_content_stage(
        module=module,
        query_kind=relaxed_query_kind,
        filenameish=False,
        parent_map=parent_map,
        per_module_limit=per_module_limit,
    ):
        content_exprs = build_content_fts_exprs(
            relaxed_query_norm,
            relaxed_query_compact,
            relaxed_fts_tokens or relaxed_query_tokens,
            relaxed_query_kind,
        )
        if content_exprs:
            content_rows = fetch_fts_content(conn, module, content_exprs, relaxed_limits["content_limit"])
            parent_map = _merge_stage_rows(
                module=module,
                parent_map=parent_map,
                seen_row_keys=seen_row_keys,
                rows=list(content_rows),
                query_norm=relaxed_query_norm,
                query_compact=relaxed_query_compact,
                query_tokens=relaxed_query_tokens,
                fuzzy_enabled=local_fuzzy_enabled,
                per_module_limit=per_module_limit,
            )

    if relaxed_allow_direct_content_like and relaxed_limits["direct_content_limit"] > 0 and _should_run_direct_content_like_stage(
        module=module,
        query_kind=relaxed_query_kind,
        filenameish=False,
        allow_direct_content_like=True,
        parent_map=parent_map,
        per_module_limit=per_module_limit,
    ):
        direct_content_rows = fetch_fts_content_like(
            conn=conn,
            module=module,
            raw_query=relaxed_raw_query,
            query_norm=relaxed_query_norm,
            query_compact=relaxed_query_compact,
            limit=relaxed_limits["direct_content_limit"],
        )
        parent_map = _merge_stage_rows(
            module=module,
            parent_map=parent_map,
            seen_row_keys=seen_row_keys,
            rows=list(direct_content_rows),
            query_norm=relaxed_query_norm,
            query_compact=relaxed_query_compact,
            query_tokens=relaxed_query_tokens,
            fuzzy_enabled=False,
            per_module_limit=per_module_limit,
        )

    return parent_map


def query_module_results(
    conn: sqlite3.Connection,
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
    del base_path
    del query_norm
    del query_compact
    del query_tokens

    guard = analyze_search_query(raw_query)

    guarded_raw_query = str(guard.get("raw_query_used") or raw_query or "").strip()
    guarded_query_norm = str(guard.get("query_norm") or "").strip()
    guarded_query_compact = str(guard.get("query_compact") or "").strip()
    guarded_query_tokens = list(guard.get("query_tokens_used") or [])
    fts_tokens = list(guard.get("query_tokens_fts") or guarded_query_tokens)

    if not guarded_raw_query and not guarded_query_norm and not guarded_query_compact:
        return []

    query_kind = str(
        guard.get("query_class")
        or classify_query(guarded_raw_query, guarded_query_compact, guarded_query_tokens)
    )
    obs = _new_query_observability(module, query_kind)

    filenameish = bool(guard.get("filenameish")) or query_kind == "filename" or is_filenameish(
        guarded_raw_query,
        query_tokens=guarded_query_tokens,
        query_compact=guarded_query_compact,
    )

    family_mode = _detect_file_family_mode(
        module=module,
        raw_query=guarded_raw_query,
        query_kind=query_kind,
        query_tokens=guarded_query_tokens,
        query_compact=guarded_query_compact,
    )
    strong_file_familyish = family_mode == "strong"
    weak_file_familyish = family_mode == "weak"

    relaxed_filename_recall = _should_relax_filename_recall(
        module=module,
        raw_query=guarded_raw_query,
        query_tokens=guarded_query_tokens,
        query_compact=guarded_query_compact,
    )

    allow_title_fts = bool(guard.get("allow_title_fts", False))
    allow_content_fts = bool(guard.get("allow_content_fts", False))
    allow_direct_content_like = bool(guard.get("allow_direct_content_like", False))

    if query_kind == "short_cjk" and module in {"doc", "files"}:
        allow_direct_content_like = True

    if query_kind == "short_cjk" and module in {"chat", "library"}:
        allow_direct_content_like = False

    if strong_file_familyish and not filenameish:
        filenameish = True
        query_kind = "filename"
        if relaxed_filename_recall:
            allow_title_fts = True
            allow_content_fts = False
            allow_direct_content_like = True
        else:
            allow_title_fts = False
            allow_content_fts = False
            allow_direct_content_like = 4 <= len(guarded_query_compact) <= 48

    if filenameish:
        query_kind = "filename"
        if relaxed_filename_recall:
            allow_title_fts = True
            allow_content_fts = False
            allow_direct_content_like = True
        else:
            allow_title_fts = False
            allow_content_fts = False
            allow_direct_content_like = 4 <= len(guarded_query_compact) <= 48

    if query_kind == "symbol_heavy" and not filenameish and not guarded_query_compact:
        _record_skipped_lane(obs, "all", "symbol_heavy_without_compact_query")
        _store_query_observability(module, obs)
        return []

    obs["flags"] = {
        "filenameish": bool(filenameish),
        "allow_title_fts": bool(allow_title_fts),
        "allow_content_fts": bool(allow_content_fts),
        "allow_direct_content_like": bool(allow_direct_content_like),
        "strong_file_familyish": bool(strong_file_familyish),
        "weak_file_familyish": bool(weak_file_familyish),
        "relaxed_filename_recall": bool(relaxed_filename_recall),
        "suppress_recall_fts": bool(suppress_recall_fts),
        "suppress_recall_fts_reason": str(suppress_recall_fts_reason or ""),
    }

    local_fuzzy_enabled = bool(fuzzy_enabled)
    if query_kind in {"short", "short_cjk", "long_nl", "filename"}:
        local_fuzzy_enabled = False

    parent_map: Dict[str, Dict[str, Any]] = {}
    seen_row_keys = set()

    if module == "chat" and query_kind in {"short", "short_cjk", "long_nl"} and not filenameish:
        before_chat_seed = len(parent_map)
        parent_map = _seed_chat_title_candidates(
            conn=conn,
            parent_map=parent_map,
            seen_row_keys=seen_row_keys,
            guarded_raw_query=guarded_raw_query,
            guarded_query_norm=guarded_query_norm,
            guarded_query_compact=guarded_query_compact,
            guarded_query_tokens=guarded_query_tokens,
            per_module_limit=per_module_limit,
        )
        _record_lane_count(obs, "chat_title_seed", count=max(0, len(parent_map) - before_chat_seed))
        if _should_stop_after_direct_stage(
            module=module,
            query_kind=query_kind,
            filenameish=filenameish,
            parent_map=parent_map,
            per_module_limit=per_module_limit,
        ):
            return _finalize_observed_results(module, parent_map, per_module_limit, obs)

    limits = _compute_stage_limits(
        per_module_limit=per_module_limit,
        query_kind=query_kind,
        allow_title_fts=allow_title_fts,
        allow_content_fts=allow_content_fts,
        allow_direct_content_like=allow_direct_content_like,
    )

    if weak_file_familyish and module in {"doc", "files", "dirs"}:
        limits["direct_title_limit"] = max(limits["direct_title_limit"], max(per_module_limit * 8, 32))

    if _is_recall_sensitive_module(module) and not filenameish:
        if allow_title_fts:
            limits["title_limit"] = max(limits["title_limit"], max(per_module_limit * 6, 24))
        if allow_content_fts:
            limits["content_limit"] = max(limits["content_limit"], max(per_module_limit * 8, 32))
        if allow_direct_content_like:
            limits["direct_content_limit"] = max(limits["direct_content_limit"], max(per_module_limit * 4, 24))

    if relaxed_filename_recall and module in {"doc", "files", "library"}:
        limits["title_limit"] = max(limits["title_limit"], max(per_module_limit * 6, 24))
        limits["direct_content_limit"] = max(limits["direct_content_limit"], max(per_module_limit * 6, 24))

    if module == "chat" and not filenameish:
        if query_kind == "short":
            if allow_title_fts:
                limits["title_limit"] = max(limits["title_limit"], max(per_module_limit * 4, 16))
            if allow_direct_content_like:
                limits["direct_content_limit"] = max(limits["direct_content_limit"], max(per_module_limit * 6, 24))

        if query_kind == "long_nl":
            if allow_title_fts:
                limits["title_limit"] = max(limits["title_limit"], max(per_module_limit * 4, 16))
            if allow_content_fts:
                limits["content_limit"] = max(limits["content_limit"], max(per_module_limit * 4, 16))
            if allow_direct_content_like:
                limits["direct_content_limit"] = max(limits["direct_content_limit"], max(per_module_limit * 4, 16))

    if module in {"doc", "files"} and query_kind == "short_cjk" and allow_direct_content_like:
        limits["direct_content_limit"] = max(limits["direct_content_limit"], max(per_module_limit * 4, 24))

    limits["recall_limit"] = 0
    if module == "chat" and query_kind == "short_cjk" and not filenameish:
        limits["recall_limit"] = max(4, min(max(per_module_limit, 8), 12))
    elif module in {"doc", "files"} and filenameish and query_kind in {"filename", "symbol_heavy"}:
        limits["recall_limit"] = max(8, min(max(per_module_limit, 12), 24))
    elif module in {"doc", "files", "dirs"} and not filenameish:
        if query_kind == "short_cjk":
            limits["recall_limit"] = max(8, min(max(per_module_limit * 2, 16), 32))
        elif query_kind in {"long_nl", "long_phrase"}:
            limits["recall_limit"] = max(8, min(max(per_module_limit * 2, 16), 32))
        elif query_kind in {"keyword", "phrase", "short"}:
            limits["recall_limit"] = max(8, min(max(per_module_limit, 12), 24))

    if strong_file_familyish and module in {"doc", "files", "dirs"}:
        family_rows = []
        for alias in _build_file_family_aliases(
            guarded_raw_query,
            guarded_query_norm,
            guarded_query_compact,
        ):
            alias_guard = analyze_search_query(alias)
            alias_raw = str(alias_guard.get("raw_query_used") or alias or "").strip()
            alias_norm = str(alias_guard.get("query_norm") or alias or "").strip()
            alias_compact = str(alias_guard.get("query_compact") or alias or "").strip()
            rows = fetch_filename_fast(
                conn=conn,
                module=module,
                raw_query=alias_raw,
                query_norm=alias_norm,
                query_compact=alias_compact,
                limit=max(12, min(limits["direct_title_limit"], 24)),
            )
            family_rows = _merge_row_lists(family_rows, list(rows), limits["direct_title_limit"])
            if len(family_rows) >= limits["direct_title_limit"]:
                break
        direct_title_rows = family_rows
    elif weak_file_familyish and module in {"doc", "files", "dirs"}:
        family_rows = []
        for alias in _build_file_family_aliases(
            guarded_raw_query,
            guarded_query_norm,
            guarded_query_compact,
        ):
            alias_guard = analyze_search_query(alias)
            alias_raw = str(alias_guard.get("raw_query_used") or alias or "").strip()
            alias_norm = str(alias_guard.get("query_norm") or alias or "").strip()
            alias_compact = str(alias_guard.get("query_compact") or alias or "").strip()
            rows = fetch_filename_fast(
                conn=conn,
                module=module,
                raw_query=alias_raw,
                query_norm=alias_norm,
                query_compact=alias_compact,
                limit=max(12, min(limits["direct_title_limit"], 24)),
            )
            family_rows = _merge_row_lists(family_rows, list(rows), limits["direct_title_limit"])
            if len(family_rows) >= limits["direct_title_limit"]:
                break

        regular_rows = fetch_direct_title(
            conn=conn,
            module=module,
            raw_query=guarded_raw_query,
            query_norm=guarded_query_norm,
            query_compact=guarded_query_compact,
            limit=limits["direct_title_limit"],
            explicit_filename=False,
        )
        direct_title_rows = _merge_row_lists(list(family_rows), list(regular_rows), limits["direct_title_limit"])
    elif filenameish:
        direct_title_rows = fetch_filename_fast(
            conn=conn,
            module=module,
            raw_query=guarded_raw_query,
            query_norm=guarded_query_norm,
            query_compact=guarded_query_compact,
            limit=limits["direct_title_limit"],
        )
    else:
        direct_title_rows = fetch_direct_title(
            conn=conn,
            module=module,
            raw_query=guarded_raw_query,
            query_norm=guarded_query_norm,
            query_compact=guarded_query_compact,
            limit=limits["direct_title_limit"],
            explicit_filename=False,
        )

    direct_title_rows = list(direct_title_rows)
    _record_lane_count(obs, "direct_title", rows=direct_title_rows)

    parent_map = _merge_stage_rows(
        module=module,
        parent_map=parent_map,
        seen_row_keys=seen_row_keys,
        rows=direct_title_rows,
        query_norm=guarded_query_norm,
        query_compact=guarded_query_compact,
        query_tokens=guarded_query_tokens,
        fuzzy_enabled=local_fuzzy_enabled,
        per_module_limit=per_module_limit,
    )

    if _should_stop_after_direct_stage(
        module=module,
        query_kind=query_kind,
        filenameish=filenameish,
        parent_map=parent_map,
        per_module_limit=per_module_limit,
    ):
        return _finalize_observed_results(module, parent_map, per_module_limit, obs)

    if not allow_title_fts:
        _record_skipped_lane(obs, "title_fts", "disabled")
    elif limits["title_limit"] <= 0:
        _record_skipped_lane(obs, "title_fts", "limit_zero")
    else:
        title_exprs = build_title_fts_exprs(
            guarded_query_norm,
            guarded_query_compact,
            fts_tokens or guarded_query_tokens,
            query_kind,
        )
        if title_exprs:
            title_rows = list(fetch_fts_title(conn, module, title_exprs, limits["title_limit"]))
            _record_lane_count(obs, "title_fts", rows=title_rows)
            parent_map = _merge_stage_rows(
                module=module,
                parent_map=parent_map,
                seen_row_keys=seen_row_keys,
                rows=title_rows,
                query_norm=guarded_query_norm,
                query_compact=guarded_query_compact,
                query_tokens=guarded_query_tokens,
                fuzzy_enabled=local_fuzzy_enabled,
                per_module_limit=per_module_limit,
            )

            if _should_stop_after_title_stage(
                module=module,
                query_kind=query_kind,
                parent_map=parent_map,
                per_module_limit=per_module_limit,
            ):
                return _finalize_observed_results(module, parent_map, per_module_limit, obs)
        else:
            _record_skipped_lane(obs, "title_fts", "empty_expr")

    if not allow_content_fts:
        _record_skipped_lane(obs, "content_fts", "disabled")
    elif limits["content_limit"] <= 0:
        _record_skipped_lane(obs, "content_fts", "limit_zero")
    elif not _should_run_content_stage(
        module=module,
        query_kind=query_kind,
        filenameish=filenameish,
        parent_map=parent_map,
        per_module_limit=per_module_limit,
    ):
        _record_skipped_lane(obs, "content_fts", "stage_guard")
    else:
        content_exprs = build_content_fts_exprs(
            guarded_query_norm,
            guarded_query_compact,
            fts_tokens or guarded_query_tokens,
            query_kind,
        )
        if content_exprs:
            content_rows = list(fetch_fts_content(conn, module, content_exprs, limits["content_limit"]))
            _record_lane_count(obs, "content_fts", rows=content_rows)
            parent_map = _merge_stage_rows(
                module=module,
                parent_map=parent_map,
                seen_row_keys=seen_row_keys,
                rows=content_rows,
                query_norm=guarded_query_norm,
                query_compact=guarded_query_compact,
                query_tokens=guarded_query_tokens,
                fuzzy_enabled=local_fuzzy_enabled,
                per_module_limit=per_module_limit,
            )
        else:
            _record_skipped_lane(obs, "content_fts", "empty_expr")

    allow_filename_recall_fallback = (
        module in {"doc", "files"}
        and filenameish
        and query_kind in {"filename", "symbol_heavy"}
        and not parent_map
        and int(limits.get("recall_limit", 0) or 0) > 0
    )

    if not _recall_stage_module_enabled(module, query_kind):
        _record_skipped_lane(obs, "recall_fts", "module_disabled")
    elif suppress_recall_fts:
        _record_skipped_lane(obs, "recall_fts", str(suppress_recall_fts_reason or "suppressed"))
    elif filenameish and not (
        module in {"doc", "files"}
        and query_kind in {"filename", "symbol_heavy"}
        and not parent_map
    ):
        _record_skipped_lane(obs, "recall_fts", "filename_query")
    elif int(limits.get("recall_limit", 0) or 0) <= 0:
        _record_skipped_lane(obs, "recall_fts", "limit_zero")
    elif not recall_fts_available(conn):
        _record_skipped_lane(obs, "recall_fts", "no_table")
    elif not allow_filename_recall_fallback and not _should_run_recall_stage(
        module=module,
        query_kind=query_kind,
        filenameish=filenameish,
        parent_map=parent_map,
        per_module_limit=per_module_limit,
    ):
        _record_skipped_lane(obs, "recall_fts", "stage_guard")
    else:
        recall_exprs = build_recall_fts_exprs(
            guarded_query_norm,
            guarded_query_compact,
            fts_tokens or guarded_query_tokens,
            query_kind,
        )
        if recall_exprs:
            recall_rows = list(fetch_fts_recall(conn, module, recall_exprs, int(limits["recall_limit"])))
            if allow_filename_recall_fallback and module == "files":
                recall_rows = _filter_filename_fallback_recall_rows(
                    recall_rows,
                    guarded_raw_query,
                )
            _record_lane_count(obs, "recall_fts", rows=recall_rows)
            parent_map = _merge_stage_rows(
                module=module,
                parent_map=parent_map,
                seen_row_keys=seen_row_keys,
                rows=recall_rows,
                query_norm=guarded_query_norm,
                query_compact=guarded_query_compact,
                query_tokens=guarded_query_tokens,
                fuzzy_enabled=False,
                per_module_limit=per_module_limit,
            )
        else:
            _record_skipped_lane(obs, "recall_fts", "empty_expr")

    if not allow_direct_content_like:
        _record_skipped_lane(obs, "direct_content_like", "disabled")
    elif limits["direct_content_limit"] <= 0:
        _record_skipped_lane(obs, "direct_content_like", "limit_zero")
    elif not _should_run_direct_content_like_stage(
        module=module,
        query_kind=query_kind,
        filenameish=filenameish,
        allow_direct_content_like=allow_direct_content_like,
        parent_map=parent_map,
        per_module_limit=per_module_limit,
    ):
        _record_skipped_lane(obs, "direct_content_like", "stage_guard")
    else:
        direct_content_rows = list(fetch_fts_content_like(
            conn=conn,
            module=module,
            raw_query=guarded_raw_query,
            query_norm=guarded_query_norm,
            query_compact=guarded_query_compact,
            limit=limits["direct_content_limit"],
        ))
        _record_lane_count(obs, "direct_content_like", rows=direct_content_rows)
        parent_map = _merge_stage_rows(
            module=module,
            parent_map=parent_map,
            seen_row_keys=seen_row_keys,
            rows=direct_content_rows,
            query_norm=guarded_query_norm,
            query_compact=guarded_query_compact,
            query_tokens=guarded_query_tokens,
            fuzzy_enabled=False,
            per_module_limit=per_module_limit,
        )

    if (
        filenameish
        and _is_recall_sensitive_module(module)
        and len(parent_map) == 0
    ):
        before_relaxed = len(parent_map)
        parent_map = _run_relaxed_keyword_fallback(
            conn=conn,
            module=module,
            raw_query=guarded_raw_query,
            per_module_limit=per_module_limit,
            fuzzy_enabled=fuzzy_enabled,
            parent_map=parent_map,
            seen_row_keys=seen_row_keys,
        )
        _record_lane_count(obs, "relaxed_keyword", count=max(0, len(parent_map) - before_relaxed))
    else:
        _record_skipped_lane(obs, "relaxed_keyword", "not_applicable")

    return _finalize_observed_results(module, parent_map, per_module_limit, obs)


__all__ = ["query_module_results", "clear_query_observability", "get_query_observability_snapshot"]

