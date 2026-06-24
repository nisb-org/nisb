#!/usr/bin/env python3

import re
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from .common import build_snippet, dedupe_keep_order, score_text_field

_TITLEISH_MATCH_TYPES = {
    "filename",
    "title",
    "dirname",
    "dirpath",
    "library_name",
    "library_doc",
}

_FILE_FAMILY_EXT_RE = re.compile(r"\.[a-z0-9]{1,10}$")
_FILE_FAMILY_SAFE_TOKEN_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{2,95}$")
_SIMPLE_KEYWORD_RE = re.compile(r"^[a-z0-9]{3,48}$")

_CODE_EXT_TOKENS = {
    "js", "jsx", "ts", "tsx", "vue", "py", "go", "rs", "java", "kt",
    "php", "rb", "c", "cc", "cpp", "h", "hpp", "cs", "swift", "mjs",
    "cjs", "json", "yaml", "yml", "css", "scss", "html", "svelte",
}


def _row_get(row: sqlite3.Row, key: str, default: Any = None) -> Any:
    try:
        return row[key]
    except Exception:
        return default


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return default


def _recall_code_ext_bonus(query_tokens: List[str], text: str) -> float:
    tokens = {str(t or "").strip().lower() for t in query_tokens if str(t or "").strip()}
    exts = [t for t in tokens if t in _CODE_EXT_TOKENS]
    if not exts:
        return 0.0

    lower = str(text or "").lower()
    for ext in exts:
        if f".{ext}" in lower:
            return 4.0
    return 0.0


def _recall_full_code_name_score(query_tokens: List[str], text: str, recall_tier: int) -> float:
    tokens = [str(t or "").strip().lower() for t in query_tokens if str(t or "").strip()]
    if not tokens:
        return 0.0

    exts = [t for t in tokens if t in _CODE_EXT_TOKENS]
    if not exts:
        return 0.0

    bases = [
        t for t in tokens
        if t not in _CODE_EXT_TOKENS
        and 2 <= len(t) <= 64
        and re.match(r"^[a-z0-9][a-z0-9_-]*$", t)
    ]
    if not bases:
        return 0.0

    lower = str(text or "").lower()
    for base in bases:
        for ext in exts:
            if f"{base}.{ext}" in lower:
                return 118.0 if int(recall_tier or 0) >= 2 else 114.0

    return 0.0


def _fts_rank_val(row: sqlite3.Row) -> float:
    try:
        v = row["fts_rank"]
        return float(v) if v is not None else 0.0
    except Exception:
        return 0.0


def _reason_rank(reason: Any) -> int:
    value = str(reason or "").strip().lower()
    if value == "exact":
        return 7
    if value == "prefix":
        return 6
    if value == "substring":
        return 5
    if value == "compact":
        return 4
    if value == "all_tokens":
        return 3
    if value == "tokens":
        return 2
    if value == "fuzzy":
        return 1
    return 0


def _fts_present(item: Dict[str, Any]) -> int:
    return 1 if float(item.get("fts_rank", 0.0) or 0.0) != 0.0 else 0


def _fts_sort_val(item: Dict[str, Any]) -> float:
    rank = float(item.get("fts_rank", 0.0) or 0.0)
    if rank == 0.0:
        return float("-inf")
    return -rank


def _filename_exact_intent_rank(item: Dict[str, Any]) -> int:
    match_type = str(item.get("match_type", "") or "")
    if match_type not in {"filename", "title", "dirname", "dirpath"}:
        return 0

    reason = str(item.get("match_reason", "") or "").strip().lower()
    priority = float(item.get("best_priority", item.get("priority", 0.0)) or 0.0)

    if reason == "exact" and priority >= 34:
        return 4
    if reason == "exact" and priority >= 28:
        return 3
    if reason == "prefix" and priority >= 34:
        return 3
    if reason in {"prefix", "substring", "compact"} and priority >= 30:
        return 2
    if priority >= 34:
        return 1
    return 0


def _parent_match_rank(item: Dict[str, Any]) -> int:
    match_type = str(item.get("match_type", "") or "")
    priority = float(item.get("priority", 0.0) or 0.0)

    if match_type in {"filename", "title", "dirname", "library_name"} and priority >= 30:
        return 5

    if match_type in {"filename", "title", "dirname", "dirpath", "library_name", "library_doc"}:
        if priority >= 28:
            return 4
        return 3

    if match_type == "content":
        if bool(item.get("recall_evidence", False)) and priority >= 30:
            return 4
        if bool(item.get("recall_evidence", False)) and priority >= 24:
            return 3
        return 2

    return 1


def _candidate_repr_key(item: Dict[str, Any]) -> Tuple[int, int, float, float, int, float]:
    return (
        _parent_match_rank(item),
        _reason_rank(item.get("match_reason")),
        float(item.get("priority", 0.0) or 0.0),
        float(item.get("score", 0.0) or 0.0),
        _fts_present(item),
        _fts_sort_val(item),
    )


def _parent_sort_key(item: Dict[str, Any]) -> Tuple[int, int, int, int, float, int, int, int, float, float, str]:
    return (
        _parent_match_rank(item),
        _filename_exact_intent_rank(item),
        1 if bool(item.get("has_title_hit", False) and item.get("has_content_hit", False)) else 0,
        1 if bool(item.get("has_title_hit", False)) else 0,
        float(item.get("best_score", item.get("score", 0.0)) or 0.0),
        _reason_rank(item.get("match_reason")),
        min(int(item.get("hit_count", 1) or 1), 8),
        _fts_present(item),
        _fts_sort_val(item),
        float(item.get("best_priority", item.get("priority", 0.0)) or 0.0),
        str(item.get("created_at", "") or ""),
    )


def _better(a: Optional[Dict[str, Any]], b: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not a:
        return b
    if not b:
        return a

    ka = _candidate_repr_key(a)
    kb = _candidate_repr_key(b)
    if kb > ka:
        return b
    return a


def _is_noise_row(row: sqlite3.Row) -> bool:
    path = str(row["path"] or "")
    filename = str(row["filename"] or "")
    source_kind = str(row["source_kind"] or "")
    normalized_path = path.replace("\\", "/").lower()

    if "/.metadata/" in f"/{normalized_path}" or normalized_path.startswith(".metadata/"):
        return True

    if normalized_path.endswith(".json") and "/.metadata/" in f"/{normalized_path}":
        return True

    if filename.startswith("file_") and filename.endswith(".json") and ".metadata" in normalized_path:
        return True

    if source_kind.endswith("_content") and ".metadata" in normalized_path:
        return True

    return False


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


def _compact_token(value: str) -> str:
    s = str(value or "").strip().lower()
    if not s:
        return ""
    return re.sub(r"[^a-z0-9\u3400-\u9fff]+", "", s)


def _safe_lower(value: str) -> str:
    return str(value or "").strip().lower()


def _basename(value: str) -> str:
    raw = str(value or "").strip().replace("\\", "/").rstrip("/")
    if not raw:
        return ""
    return Path(raw).name.lower().strip()


def _stemish(value: str) -> str:
    base = _basename(value) or _safe_lower(value).rstrip(".")
    if not base:
        return ""
    return Path(base.rstrip(".")).stem.lower().strip()


def _canonical_path_key(value: str) -> str:
    raw = str(value or "").strip().replace("\\", "/")
    if not raw:
        return ""
    raw = re.sub(r"/+", "/", raw).rstrip("/")
    return raw.lower().strip()


def _path_fold_role(item: Dict[str, Any]) -> str:
    match_type = str(item.get("match_type", "") or "")
    if match_type == "content":
        return "content"
    if match_type in _TITLEISH_MATCH_TYPES:
        return "titleish"
    if bool(item.get("has_content_hit", False)) and not bool(item.get("has_title_hit", False)):
        return "content"
    if bool(item.get("has_title_hit", False)):
        return "titleish"
    return "other"


def _looks_like_file_family_query(query_norm: str, query_compact: str, query_tokens: List[str]) -> bool:
    q = _safe_lower(query_norm)
    compact = _compact_token(query_compact or query_norm)
    tokens = [str(t or "").strip().lower() for t in query_tokens if str(t or "").strip()]

    if not q and tokens:
        q = tokens[0]

    if not q:
        return False
    if len(q) < 3 or len(q) > 96:
        return False
    if any(ch.isspace() for ch in q):
        return False
    if _contains_cjk(q):
        return False
    if len(tokens) > 2:
        return False

    if "/" in q or "\\" in q:
        return True
    if "." in q or q.endswith("."):
        return True
    if "_" in q or "-" in q:
        return True
    if _FILE_FAMILY_EXT_RE.search(q):
        return True
    if compact and compact != q:
        return True
    if len(tokens) == 2 and len(tokens[1]) <= 6:
        return True
    if len(tokens) == 1 and _FILE_FAMILY_SAFE_TOKEN_RE.match(q):
        return True

    return False


def _build_file_family_aliases(query_norm: str, query_compact: str, query_tokens: List[str]) -> Tuple[List[str], List[str]]:
    q = _safe_lower(query_norm)
    compact = _compact_token(query_compact or query_norm)
    tokens = [str(t or "").strip().lower() for t in query_tokens if str(t or "").strip()]

    if not q and tokens:
        q = tokens[0]

    aliases: List[str] = []
    seen = set()

    def _push(value: str) -> None:
        v = _safe_lower(value)
        if not v or v in seen:
            return
        seen.add(v)
        aliases.append(v)

    trimmed = q.rstrip(".").strip()
    base = _basename(q)
    stem = _stemish(q)

    _push(q)
    _push(trimmed)
    _push(base)
    _push(stem)

    if trimmed and "." not in trimmed:
        _push(trimmed + ".")

    if len(tokens) >= 1:
        _push(tokens[0])

    if len(tokens) == 2 and len(tokens[1]) <= 10:
        _push(f"{tokens[0]}.{tokens[1]}")
        _push(tokens[0])

    compact_aliases = dedupe_keep_order([_compact_token(v) for v in aliases] + ([compact] if compact else []))
    compact_aliases = [v for v in compact_aliases if v]

    return aliases[:8], compact_aliases[:8]


def _build_query_profile(
    query_norm: str,
    query_compact: str,
    query_tokens: List[str],
) -> Dict[str, Any]:
    safe_query_norm = _safe_lower(query_norm)
    normalized_tokens = [str(t or "").strip().lower() for t in query_tokens if str(t or "").strip()]
    compact = _compact_token(query_compact or query_norm)

    primary = safe_query_norm
    if not primary and normalized_tokens:
        primary = normalized_tokens[0]

    contains_cjk = _contains_cjk(primary) or any(_contains_cjk(t) for t in normalized_tokens)

    simple_keyword = False
    if len(normalized_tokens) == 1:
        token0 = normalized_tokens[0]
        if (
            token0
            and not contains_cjk
            and _SIMPLE_KEYWORD_RE.match(token0)
            and "/" not in token0
            and "\\" not in token0
            and "." not in token0
            and "_" not in token0
            and "-" not in token0
        ):
            simple_keyword = True

    file_familyish = _looks_like_file_family_query(
        query_norm=safe_query_norm or primary,
        query_compact=compact,
        query_tokens=normalized_tokens,
    )

    family_aliases: List[str] = []
    family_compacts: List[str] = []
    if file_familyish:
        family_aliases, family_compacts = _build_file_family_aliases(
            query_norm=safe_query_norm or primary,
            query_compact=compact,
            query_tokens=normalized_tokens,
        )

    return {
        "query_norm": safe_query_norm or primary,
        "query_compact": compact,
        "query_tokens": normalized_tokens,
        "contains_cjk": bool(contains_cjk),
        "simple_keyword": bool(simple_keyword),
        "file_familyish": bool(file_familyish),
        "family_aliases": family_aliases,
        "family_compacts": family_compacts,
    }


def _family_match_score(field: str, aliases: List[str], compact_aliases: List[str], field_name: str) -> Optional[Dict[str, Any]]:
    raw = str(field or "").strip()
    if not raw or not aliases:
        return None

    lower = raw.lower()
    base = _basename(raw)
    stem = _stemish(raw)
    compact = _compact_token(raw)

    views = dedupe_keep_order([
        lower,
        lower.rstrip("."),
        base,
        base.rstrip("."),
        stem,
    ])
    views = [v for v in views if v]

    field_base = {
        "filename": 66.0,
        "title": 60.0,
        "dirname": 60.0,
        "path": 50.0,
        "dirpath": 46.0,
        "doc_title": 58.0,
    }.get(field_name, 52.0)

    best: Optional[Dict[str, Any]] = None

    def _take(score: float, reason: str, term: str) -> None:
        nonlocal best
        candidate = {
            "score": score,
            "match_reason": reason,
            "matched_terms": [term] if term else [],
        }
        if best is None or (
            float(candidate["score"]) > float(best["score"])
            or (
                float(candidate["score"]) == float(best["score"])
                and _reason_rank(candidate["match_reason"]) > _reason_rank(best["match_reason"])
            )
        ):
            best = candidate

    for alias in aliases:
        a = _safe_lower(alias)
        if not a or len(a) < 2:
            continue

        for view in views:
            if not view:
                continue
            if view == a:
                bonus = 4.0 if view == base else 0.0
                _take(field_base + bonus, "exact", a)
            elif len(a) >= 3 and view.startswith(a):
                bonus = 2.0 if view == base or view == stem else 0.0
                _take(field_base - 6.0 + bonus, "prefix", a)
            elif len(a) >= 4 and a in view:
                _take(field_base - 12.0, "substring", a)

    for alias in compact_aliases:
        a = _compact_token(alias)
        if not a or len(a) < 3 or not compact:
            continue
        if compact == a:
            _take(field_base - 8.0, "compact", a)
        elif compact.startswith(a):
            _take(field_base - 12.0, "compact", a)
        elif len(a) >= 5 and a in compact:
            _take(field_base - 16.0, "compact", a)

    return best


def _best_text_match(
    field: str,
    query_norm: str,
    query_compact: str,
    query_tokens: List[str],
    field_name: str,
    fuzzy: bool,
    allow_fuzzy: bool,
    family_aliases: Optional[List[str]] = None,
    family_compacts: Optional[List[str]] = None,
) -> Optional[Dict[str, Any]]:
    best = score_text_field(
        field,
        query_norm,
        query_compact,
        query_tokens,
        field_name,
        fuzzy=fuzzy,
        allow_fuzzy=allow_fuzzy,
    )

    if family_aliases:
        family_match = _family_match_score(
            field=field,
            aliases=family_aliases,
            compact_aliases=family_compacts or [],
            field_name=field_name,
        )
        if family_match and (
            not best
            or float(family_match.get("score", 0.0) or 0.0) > float(best.get("score", 0.0) or 0.0)
            or (
                float(family_match.get("score", 0.0) or 0.0) == float(best.get("score", 0.0) or 0.0)
                and _reason_rank(family_match.get("match_reason")) > _reason_rank(best.get("match_reason"))
            )
        ):
            best = family_match

    return best


def _is_strong_titleish_candidate(item: Optional[Dict[str, Any]]) -> bool:
    if not item:
        return False

    match_type = str(item.get("match_type", "") or "")
    if match_type not in _TITLEISH_MATCH_TYPES:
        return False

    score = float(item.get("score", 0.0) or 0.0)
    priority = float(item.get("priority", 0.0) or 0.0)
    reason_rank = _reason_rank(item.get("match_reason"))

    if score >= 60.0:
        return True
    if priority >= 30.0 and reason_rank >= 5:
        return True
    if score >= 56.0 and reason_rank >= 6:
        return True
    return False


def _should_skip_low_value_field_scoring(
    module: str,
    source_kind: str,
    current_best: Optional[Dict[str, Any]],
    query_profile: Dict[str, Any],
) -> bool:
    if not bool(query_profile.get("simple_keyword", False)):
        return False

    if bool(query_profile.get("file_familyish", False)):
        return False

    if _contains_cjk(str(query_profile.get("query_norm", "") or "")):
        return False

    if module not in {"doc", "files", "dirs", "library"}:
        return False

    if str(source_kind or "").endswith("_content"):
        return False

    return _is_strong_titleish_candidate(current_best)


def score_row(
    row: sqlite3.Row,
    query_norm: str,
    query_compact: str,
    query_tokens: List[str],
    fuzzy_enabled: bool,
    query_profile: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    if _is_noise_row(row):
        return None

    module = str(row["module"])
    source_kind = str(row["source_kind"] or "")
    item_key = str(row["item_key"] or "")
    fts_rank = _fts_rank_val(row)

    matched_source_kind = str(_row_get(row, "matched_source_kind", "") or "")
    recall_tier_raw = _row_get(row, "recall_tier", None)
    recall_tier = _safe_int(recall_tier_raw, 0)
    is_recall_row = bool(matched_source_kind or recall_tier_raw is not None)

    recall_text = str(_row_get(row, "matched_recall_text", "") or "")
    if not recall_text and is_recall_row:
        recall_text = str(_row_get(row, "snippet", "") or "")

    matched_recall_content = bool(
        is_recall_row
        and recall_text
        and (
            matched_source_kind.endswith("_content")
            or recall_tier >= 2
        )
    )
    weak_tier0_file_recall = bool(
        is_recall_row
        and recall_tier == 0
        and matched_source_kind.endswith("_file")
    )

    profile = query_profile or _build_query_profile(
        query_norm=query_norm,
        query_compact=query_compact,
        query_tokens=query_tokens,
    )

    profile_query_norm = str(profile.get("query_norm", "") or query_norm or "")
    profile_query_compact = str(profile.get("query_compact", "") or query_compact or "")
    profile_query_tokens = list(profile.get("query_tokens", []) or query_tokens or [])

    family_aliases: List[str] = []
    family_compacts: List[str] = []
    file_familyish = False

    if module in {"doc", "files", "dirs"}:
        file_familyish = bool(profile.get("file_familyish", False))
        if file_familyish:
            family_aliases = list(profile.get("family_aliases", []) or [])
            family_compacts = list(profile.get("family_compacts", []) or [])

    def mk(match: Dict[str, Any], payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if not match or float(match.get("score", 0.0)) <= 0:
            return None
        payload.update(
            {
                "match_reason": match.get("match_reason"),
                "matched_terms": match.get("matched_terms", []),
                "score": float(match.get("score", 0.0)),
                "fts_rank": fts_rank,
            }
        )
        return payload

    if module == "chat":
        best = None

        m = score_text_field(
            row["title"],
            profile_query_norm,
            profile_query_compact,
            profile_query_tokens,
            "title",
            fuzzy=fuzzy_enabled,
            allow_fuzzy=True,
        )
        best = _better(
            best,
            mk(
                m,
                {
                    "conv_id": row["conv_id"],
                    "title": row["title"],
                    "created_at": row["created_at"],
                    "turn_count": int(row["turn_count"] or 0),
                    "match_type": "title",
                    "priority": 30 if source_kind == "chat_meta" else 26,
                    "source_kind": source_kind,
                },
            ),
        )

        if row["snippet"]:
            m = score_text_field(
                row["snippet"],
                profile_query_norm,
                profile_query_compact,
                profile_query_tokens,
                "content",
                fuzzy=False,
                allow_fuzzy=False,
            )
            best = _better(
                best,
                mk(
                    m,
                    {
                        "conv_id": row["conv_id"],
                        "title": row["title"],
                        "created_at": row["created_at"],
                        "turn_count": int(row["turn_count"] or 0),
                        "snippet": build_snippet(row["snippet"] or "", profile_query_norm, profile_query_tokens),
                        "match_type": "content",
                        "priority": 18 if source_kind == "chat_turn" else 14,
                        "source_kind": source_kind,
                    },
                ),
            )

        return best

    if module in ("doc", "files"):
        best = None

        filename_priority = 38 if file_familyish else 34
        title_priority = 34 if file_familyish else 30
        path_priority = 28 if file_familyish else 22

        if weak_tier0_file_recall:
            filename_priority = min(filename_priority, 24)
            title_priority = min(title_priority, 22)
            path_priority = min(path_priority, 14)

        for field, field_name, match_type, priority, snippet_prefix in [
            (row["filename"], "filename", "filename", filename_priority, "文件名匹配"),
            (row["title"], "title", "filename", title_priority, "标题匹配"),
        ]:
            m = _best_text_match(
                field=field,
                query_norm=profile_query_norm,
                query_compact=profile_query_compact,
                query_tokens=profile_query_tokens,
                field_name=field_name,
                fuzzy=fuzzy_enabled,
                allow_fuzzy=(field_name in {"filename", "title"}),
                family_aliases=family_aliases if file_familyish else None,
                family_compacts=family_compacts if file_familyish else None,
            )
            best = _better(
                best,
                mk(
                    m,
                    {
                        "filename": row["filename"],
                        "title": row["title"] or row["filename"],
                        "path": row["path"],
                        "snippet": f"{snippet_prefix}: {field or row['title'] or row['filename']}",
                        "match_type": match_type,
                        "priority": priority,
                        "source_kind": source_kind,
                    },
                ),
            )

        skip_low_value_fields = _should_skip_low_value_field_scoring(
            module=module,
            source_kind=source_kind,
            current_best=best,
            query_profile=profile,
        )

        if not skip_low_value_fields:
            m = _best_text_match(
                field=row["path"],
                query_norm=profile_query_norm,
                query_compact=profile_query_compact,
                query_tokens=profile_query_tokens,
                field_name="path",
                fuzzy=False,
                allow_fuzzy=False,
                family_aliases=family_aliases if file_familyish else None,
                family_compacts=family_compacts if file_familyish else None,
            )
            best = _better(
                best,
                mk(
                    m,
                    {
                        "filename": row["filename"],
                        "title": row["title"] or row["filename"],
                        "path": row["path"],
                        "snippet": f"路径匹配: {row['path'] or row['title'] or row['filename']}",
                        "match_type": "filename",
                        "priority": path_priority,
                        "source_kind": source_kind,
                    },
                ),
            )

        content_text = recall_text if matched_recall_content else str(row["snippet"] or "")
        should_score_snippet = bool(content_text)
        if (
            skip_low_value_fields
            and not str(source_kind or "").endswith("_content")
            and not matched_recall_content
        ):
            should_score_snippet = False

        if should_score_snippet:
            if matched_recall_content:
                base_priority = 30
                if matched_source_kind.endswith("_content"):
                    base_priority += 2
                if recall_tier >= 2:
                    base_priority += 2
                base_priority += _recall_code_ext_bonus(profile_query_tokens, content_text)
                base_priority = min(base_priority, 38)
            else:
                base_priority = 16 if file_familyish else (18 if item_key.endswith("::0") else 15)

            m = score_text_field(
                content_text,
                profile_query_norm,
                profile_query_compact,
                profile_query_tokens,
                "content",
                fuzzy=False,
                allow_fuzzy=False,
            )
            if matched_recall_content and m and float(m.get("score", 0.0) or 0.0) > 0:
                full_code_score = _recall_full_code_name_score(
                    profile_query_tokens,
                    content_text,
                    recall_tier,
                )
                if full_code_score > 0:
                    boosted = dict(m)
                    boosted["score"] = max(float(boosted.get("score", 0.0) or 0.0), full_code_score)
                    if _reason_rank(boosted.get("match_reason")) < 3:
                        boosted["match_reason"] = "all_tokens"
                    m = boosted

            best = _better(
                best,
                mk(
                    m,
                    {
                        "filename": row["filename"],
                        "title": row["title"] or row["filename"],
                        "path": row["path"],
                        "snippet": build_snippet(content_text or "", profile_query_norm, profile_query_tokens),
                        "match_type": "content",
                        "priority": base_priority,
                        "source_kind": source_kind,
                        "matched_source_kind": matched_source_kind,
                        "recall_tier": recall_tier,
                        "recall_evidence": bool(matched_recall_content),
                    },
                ),
            )

        return best

    if module == "dirs":
        best = None
        dirname = row["filename"] or row["title"]

        dirname_priority = 34 if file_familyish else 30
        dirpath_priority = 24 if file_familyish else 20

        m = _best_text_match(
            dirname,
            profile_query_norm,
            profile_query_compact,
            profile_query_tokens,
            "dirname",
            fuzzy=fuzzy_enabled,
            allow_fuzzy=True,
            family_aliases=family_aliases if file_familyish else None,
            family_compacts=family_compacts if file_familyish else None,
        )
        best = _better(
            best,
            mk(
                m,
                {
                    "dirname": dirname,
                    "title": dirname,
                    "path": row["path"],
                    "snippet": f"目录名匹配: {dirname}",
                    "match_type": "dirname",
                    "priority": dirname_priority,
                    "source_kind": source_kind,
                },
            ),
        )

        if not _should_skip_low_value_field_scoring(
            module=module,
            source_kind=source_kind,
            current_best=best,
            query_profile=profile,
        ):
            m = _best_text_match(
                row["path"],
                profile_query_norm,
                profile_query_compact,
                profile_query_tokens,
                "dirpath",
                fuzzy=False,
                allow_fuzzy=False,
                family_aliases=family_aliases if file_familyish else None,
                family_compacts=family_compacts if file_familyish else None,
            )
            best = _better(
                best,
                mk(
                    m,
                    {
                        "dirname": dirname,
                        "title": dirname,
                        "path": row["path"],
                        "snippet": f"目录路径匹配: {row['path']}",
                        "match_type": "dirpath",
                        "priority": dirpath_priority,
                        "source_kind": source_kind,
                    },
                ),
            )

        return best

    if module == "library":
        if source_kind == "library_meta":
            m = score_text_field(
                row["library_name"],
                profile_query_norm,
                profile_query_compact,
                profile_query_tokens,
                "library_name",
                fuzzy=fuzzy_enabled,
                allow_fuzzy=True,
            )
            return mk(
                m,
                {
                    "library_id": row["library_id"],
                    "library_name": row["library_name"],
                    "title": row["library_name"],
                    "match_type": "library_name",
                    "priority": 30,
                    "source_kind": source_kind,
                },
            )

        best = None

        for field, field_name, priority, snippet_prefix in [
            (row["title"], "doc_title", 34, "馆藏标题匹配"),
            (row["filename"], "filename", 28, "馆藏文件名匹配"),
        ]:
            m = score_text_field(
                field,
                profile_query_norm,
                profile_query_compact,
                profile_query_tokens,
                field_name,
                fuzzy=fuzzy_enabled,
                allow_fuzzy=(field_name in {"doc_title", "filename"}),
            )
            best = _better(
                best,
                mk(
                    m,
                    {
                        "library_id": row["library_id"],
                        "library_name": row["library_name"],
                        "doc_id": row["doc_id"],
                        "title": row["title"] or row["filename"],
                        "file_path": row["path"],
                        "snippet": f"{snippet_prefix}: {field or row['title'] or row['filename']}",
                        "match_type": "library_doc",
                        "priority": priority,
                        "source_kind": source_kind,
                    },
                ),
            )

        skip_low_value_fields = _should_skip_low_value_field_scoring(
            module=module,
            source_kind=source_kind,
            current_best=best,
            query_profile=profile,
        )

        if not skip_low_value_fields:
            m = score_text_field(
                row["path"],
                profile_query_norm,
                profile_query_compact,
                profile_query_tokens,
                "path",
                fuzzy=False,
                allow_fuzzy=False,
            )
            best = _better(
                best,
                mk(
                    m,
                    {
                        "library_id": row["library_id"],
                        "library_name": row["library_name"],
                        "doc_id": row["doc_id"],
                        "title": row["title"] or row["filename"],
                        "file_path": row["path"],
                        "snippet": f"馆藏路径匹配: {row['path'] or row['title'] or row['filename']}",
                        "match_type": "library_doc",
                        "priority": 18,
                        "source_kind": source_kind,
                    },
                ),
            )

        should_score_snippet = bool(row["snippet"])
        if skip_low_value_fields and not str(source_kind or "").endswith("_content"):
            should_score_snippet = False

        if should_score_snippet:
            base_priority = 18 if item_key.endswith("::0") else 15
            m = score_text_field(
                row["snippet"],
                profile_query_norm,
                profile_query_compact,
                profile_query_tokens,
                "content",
                fuzzy=False,
                allow_fuzzy=False,
            )
            best = _better(
                best,
                mk(
                    m,
                    {
                        "library_id": row["library_id"],
                        "library_name": row["library_name"],
                        "doc_id": row["doc_id"],
                        "title": row["title"] or row["filename"],
                        "file_path": row["path"],
                        "snippet": build_snippet(row["snippet"] or "", profile_query_norm, profile_query_tokens),
                        "match_type": "content",
                        "priority": base_priority,
                        "source_kind": source_kind,
                    },
                ),
            )

        return best

    return None


def _row_key(module: str, item: Dict[str, Any]) -> str:
    if module == "chat":
        return str(item.get("conv_id", ""))

    if module == "dirs":
        return str(item.get("path", "")) or str(item.get("title", ""))

    if module in ("doc", "files"):
        path_key = _canonical_path_key(item.get("path", ""))
        if path_key:
            role = _path_fold_role(item)
            if role == "content":
                return f"{path_key}::content"
            return f"{path_key}::titleish"
        return str(item.get("title", "")) or str(item.get("filename", ""))

    if module == "library":
        library_id = str(item.get("library_id", "") or "")
        doc_id = str(item.get("doc_id", "") or "")
        file_path = str(item.get("file_path", "") or "")
        title = str(item.get("title", "") or "")
        if doc_id:
            return f"{library_id}|{doc_id}"
        if file_path:
            return f"{library_id}|{file_path}"
        return f"{library_id}|{title}"

    return str(item.get("title", "") or "")


def _choose_better_parent_repr(current: Dict[str, Any], candidate: Dict[str, Any]) -> Dict[str, Any]:
    current_key = _candidate_repr_key(current)
    candidate_key = _candidate_repr_key(candidate)
    if candidate_key > current_key:
        return candidate
    return current


def _enrich_parent_candidate(item: Dict[str, Any], parent_key: str) -> Dict[str, Any]:
    enriched = dict(item)
    enriched["parent_key"] = parent_key
    enriched["hit_count"] = int(enriched.get("hit_count", 1) or 1)
    enriched["best_score"] = float(enriched.get("score", 0.0) or 0.0)
    enriched["best_priority"] = float(enriched.get("priority", 0.0) or 0.0)
    enriched["best_fts_rank"] = float(enriched.get("fts_rank", 0.0) or 0.0)
    enriched["has_title_hit"] = str(enriched.get("match_type", "") or "") in _TITLEISH_MATCH_TYPES
    enriched["has_content_hit"] = str(enriched.get("match_type", "") or "") == "content"

    path_key = _canonical_path_key(enriched.get("path", ""))
    if path_key and ("::titleish" in parent_key or "::content" in parent_key):
        enriched["path_fold_key"] = path_key
        enriched["path_fold_role"] = _path_fold_role(enriched)
    else:
        enriched["path_fold_key"] = ""
        enriched["path_fold_role"] = ""

    return enriched


def _evidence_rank(item: Dict[str, Any]) -> Tuple[int, int, float, int, float]:
    recall_evidence = 1 if bool(item.get("recall_evidence", False)) else 0
    matched_source_kind = str(item.get("matched_source_kind", "") or "")
    has_source = 1 if matched_source_kind else 0
    snippet_len = len(str(item.get("snippet", "") or "").strip())
    priority = float(item.get("priority", 0.0) or 0.0)
    score = float(item.get("score", 0.0) or 0.0)
    return (
        recall_evidence,
        has_source,
        priority,
        min(snippet_len, 240),
        score,
    )


def _pick_best_evidence(parent: Dict[str, Any], child: Dict[str, Any]) -> Dict[str, Any]:
    if _evidence_rank(child) > _evidence_rank(parent):
        return child
    return parent


def _copy_evidence_fields(keep: Dict[str, Any], evidence: Dict[str, Any]) -> None:
    for key in (
        "matched_source_kind",
        "recall_tier",
        "recall_chunk_index",
        "recall_evidence",
        "matched_recall_text",
        "fts_rank",
        "best_fts_rank",
    ):
        value = evidence.get(key)
        if value is None:
            continue
        if isinstance(value, str) and not value.strip():
            continue
        if key == "recall_evidence" and not bool(value):
            continue
        keep[key] = value


def _merge_parent_item(module: str, parent: Dict[str, Any], child: Dict[str, Any]) -> Dict[str, Any]:
    chosen = _choose_better_parent_repr(parent, child)
    keep = dict(chosen)

    hit_count = int(parent.get("hit_count", 1) or 1) + int(child.get("hit_count", 1) or 1)
    keep["hit_count"] = hit_count

    keep["matched_terms"] = dedupe_keep_order(
        list(parent.get("matched_terms", []) or []) +
        list(child.get("matched_terms", []) or [])
    )

    parent_best_score = float(parent.get("best_score", parent.get("score", 0.0)) or 0.0)
    child_best_score = float(child.get("best_score", child.get("score", 0.0)) or 0.0)
    keep["best_score"] = max(parent_best_score, child_best_score)
    keep["score"] = keep["best_score"]

    parent_best_priority = float(parent.get("best_priority", parent.get("priority", 0.0)) or 0.0)
    child_best_priority = float(child.get("best_priority", child.get("priority", 0.0)) or 0.0)
    keep["best_priority"] = max(parent_best_priority, child_best_priority)
    keep["priority"] = keep["best_priority"]

    parent_best_fts = float(parent.get("best_fts_rank", parent.get("fts_rank", 0.0)) or 0.0)
    child_best_fts = float(child.get("best_fts_rank", child.get("fts_rank", 0.0)) or 0.0)
    if parent_best_fts == 0.0:
        keep["best_fts_rank"] = child_best_fts
    elif child_best_fts == 0.0:
        keep["best_fts_rank"] = parent_best_fts
    else:
        keep["best_fts_rank"] = min(parent_best_fts, child_best_fts)
    keep["fts_rank"] = keep["best_fts_rank"]

    keep["has_title_hit"] = bool(parent.get("has_title_hit", False) or child.get("has_title_hit", False))
    keep["has_content_hit"] = bool(parent.get("has_content_hit", False) or child.get("has_content_hit", False))

    evidence_candidate = _pick_best_evidence(parent, child)
    _copy_evidence_fields(keep, evidence_candidate)

    if keep.get("has_content_hit"):
        content_candidate = None
        if str(child.get("match_type", "") or "") == "content" and str(child.get("snippet", "") or "").strip():
            content_candidate = child
        elif str(parent.get("match_type", "") or "") == "content" and str(parent.get("snippet", "") or "").strip():
            content_candidate = parent
        if content_candidate is not None:
            keep["snippet"] = str(content_candidate.get("snippet", "") or keep.get("snippet", "") or "")
            if bool(content_candidate.get("recall_evidence", False)) or str(content_candidate.get("matched_source_kind", "") or ""):
                _copy_evidence_fields(keep, content_candidate)

    if module == "chat":
        keep["turn_count"] = max(
            int(parent.get("turn_count", 0) or 0),
            int(child.get("turn_count", 0) or 0),
        )

    if keep.get("path_fold_key") or parent.get("path_fold_key") or child.get("path_fold_key"):
        keep["path_fold_key"] = str(
            keep.get("path_fold_key")
            or parent.get("path_fold_key")
            or child.get("path_fold_key")
            or ""
        )
        keep["path_fold_role"] = str(
            keep.get("path_fold_role")
            or parent.get("path_fold_role")
            or child.get("path_fold_role")
            or ""
        )

    return keep


def _final_sort(items: List[Dict[str, Any]]) -> None:
    items.sort(key=_parent_sort_key, reverse=True)


def summarize_parent_hits(parent_map: Dict[str, Dict[str, Any]]) -> Dict[str, int]:
    grouped: Dict[str, Dict[str, Any]] = {}

    for item in parent_map.values():
        group_key = str(item.get("path_fold_key", "") or item.get("parent_key", "") or "")
        if not group_key:
            continue

        has_title_hit = bool(item.get("has_title_hit", False)) or str(item.get("match_type", "") or "") in _TITLEISH_MATCH_TYPES
        has_content_hit = bool(item.get("has_content_hit", False)) or str(item.get("match_type", "") or "") == "content"
        best_priority = float(item.get("best_priority", item.get("priority", 0.0)) or 0.0)
        reason_rank = _reason_rank(item.get("match_reason"))

        current = grouped.get(group_key)
        if current is None:
            grouped[group_key] = {
                "has_title_hit": has_title_hit,
                "has_content_hit": has_content_hit,
                "best_priority": best_priority,
                "reason_rank": reason_rank,
            }
        else:
            current["has_title_hit"] = bool(current.get("has_title_hit", False) or has_title_hit)
            current["has_content_hit"] = bool(current.get("has_content_hit", False) or has_content_hit)
            current["best_priority"] = max(float(current.get("best_priority", 0.0) or 0.0), best_priority)
            current["reason_rank"] = max(int(current.get("reason_rank", 0) or 0), reason_rank)

    total = 0
    titleish = 0
    strong_titleish = 0
    content = 0
    exactish = 0

    for item in grouped.values():
        total += 1

        has_title_hit = bool(item.get("has_title_hit", False))
        has_content_hit = bool(item.get("has_content_hit", False))
        best_priority = float(item.get("best_priority", 0.0) or 0.0)
        reason_rank = int(item.get("reason_rank", 0) or 0)

        if has_title_hit:
            titleish += 1
        if has_content_hit:
            content += 1
        if reason_rank >= 6:
            exactish += 1
        if has_title_hit and (best_priority >= 28 or reason_rank >= 6):
            strong_titleish += 1

    return {
        "total": int(total),
        "titleish": int(titleish),
        "strong_titleish": int(strong_titleish),
        "content": int(content),
        "exactish": int(exactish),
    }


def merge_parent_batch(
    module: str,
    rows: List[sqlite3.Row],
    query_norm: str,
    query_compact: str,
    query_tokens: List[str],
    fuzzy_enabled: bool,
    existing: Optional[Dict[str, Dict[str, Any]]] = None,
    seen_row_keys: Optional[Set[str]] = None,
    batch_parent_limit: int = 0,
) -> Dict[str, Dict[str, Any]]:
    parent_map: Dict[str, Dict[str, Any]] = existing if existing is not None else {}
    seen_keys: Set[str] = seen_row_keys if seen_row_keys is not None else set()

    local_grouped: Dict[str, Dict[str, Any]] = {}
    query_profile = _build_query_profile(
        query_norm=query_norm,
        query_compact=query_compact,
        query_tokens=query_tokens,
    )

    for row in rows:
        row_key = str(row["item_key"] or "")
        if row_key and row_key in seen_keys:
            continue
        if row_key:
            seen_keys.add(row_key)

        item = score_row(
            row=row,
            query_norm=query_norm,
            query_compact=query_compact,
            query_tokens=query_tokens,
            fuzzy_enabled=fuzzy_enabled,
            query_profile=query_profile,
        )
        if not item:
            continue

        parent_key = _row_key(module, item)
        if not parent_key:
            continue

        enriched = _enrich_parent_candidate(item, parent_key)
        if parent_key not in local_grouped:
            local_grouped[parent_key] = enriched
        else:
            local_grouped[parent_key] = _merge_parent_item(module, local_grouped[parent_key], enriched)

    batch_items = list(local_grouped.values())
    _final_sort(batch_items)

    if batch_parent_limit > 0:
        batch_items = batch_items[:batch_parent_limit]

    for item in batch_items:
        parent_key = str(item.get("parent_key", "") or "")
        if not parent_key:
            continue
        if parent_key not in parent_map:
            parent_map[parent_key] = item
        else:
            parent_map[parent_key] = _merge_parent_item(module, parent_map[parent_key], item)

    return parent_map


def _pick_secondary_path_repr(primary: Dict[str, Any], items: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    primary_role = str(primary.get("path_fold_role", "") or "")
    if primary_role not in {"titleish", "content"}:
        return None

    desired_role = "content" if primary_role == "titleish" else "titleish"

    candidates = [
        item for item in items
        if item is not primary and str(item.get("path_fold_role", "") or "") == desired_role
    ]
    if not candidates:
        return None

    candidates.sort(key=_parent_sort_key, reverse=True)
    return candidates[0]


def _apply_files_path_fold(items: List[Dict[str, Any]], per_module_limit: int) -> List[Dict[str, Any]]:
    if not items:
        return []

    if not any(str(item.get("path_fold_key", "") or "") for item in items):
        return items[:per_module_limit]

    passthrough: List[Dict[str, Any]] = []
    path_groups: Dict[str, List[Dict[str, Any]]] = {}

    for item in items:
        path_key = str(item.get("path_fold_key", "") or "")
        if not path_key:
            passthrough.append(item)
            continue
        path_groups.setdefault(path_key, []).append(item)

    kept: List[Dict[str, Any]] = list(passthrough)

    for group_items in path_groups.values():
        _final_sort(group_items)
        primary = group_items[0]
        kept.append(primary)

        secondary = _pick_secondary_path_repr(primary, group_items)
        if secondary is not None:
            kept.append(secondary)

    _final_sort(kept)
    return kept[:per_module_limit]


def finalize_parent_results(
    parent_map: Dict[str, Dict[str, Any]],
    per_module_limit: int,
) -> List[Dict[str, Any]]:
    out = list(parent_map.values())
    _final_sort(out)
    out = _apply_files_path_fold(out, per_module_limit)
    _final_sort(out)
    return out[:per_module_limit]


__all__ = [
    "score_row",
    "summarize_parent_hits",
    "merge_parent_batch",
    "finalize_parent_results",
]
