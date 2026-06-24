#!/usr/bin/env python3

import re
import sqlite3
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from .common import (
    FTS_QUERY_RESERVED,
    analyze_search_query,
    dedupe_keep_order,
    is_filenameish_query,
)

SELECT_TIMEOUT_MS = 1200
FTS_TIMEOUT_MS = 1800
RECALL_SENSITIVE_MODULES = {"doc", "files"}

ALLOWED_SEARCH_FIELDS = {
    "filename",
    "title",
    "path",
    "library_name",
    "filename_norm",
    "title_norm",
    "path_norm",
    "library_name_norm",
    "filename_compact",
    "title_compact",
    "path_compact",
    "library_name_compact",
    "snippet",
    "snippet_norm",
    "snippet_compact",
}

_SIMPLE_KEYWORD_RE = re.compile(r"^[a-z0-9]{3,48}$")


def _table_exists(conn: sqlite3.Connection, table_name: str) -> bool:
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type IN ('table', 'view') AND name = ?",
        (table_name,),
    ).fetchone()
    return row is not None


def _is_recall_sensitive_module(module: str) -> bool:
    return str(module or "") in RECALL_SENSITIVE_MODULES


def _dynamic_limit(
    limit: int,
    floor: int,
    default_cap: int,
    recall_cap: Optional[int] = None,
    module: str = "",
) -> int:
    value = int(limit or 0)
    if value <= 0:
        return 0

    cap = int(default_cap)
    if recall_cap is not None and _is_recall_sensitive_module(module):
        cap = int(recall_cap)

    return max(int(floor), min(value, cap))


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


def _is_explicit_filename_query(raw_query: str) -> bool:
    q = str(raw_query or "").strip()
    if not q:
        return False

    lower = q.lower()
    if "/" in q or "\\" in q:
        return True
    if re.search(r"\.[a-z0-9]{1,12}$", lower):
        return True
    if q.endswith("."):
        return True
    if "." in q and len(q) >= 4:
        return True
    if "_" in q or "-" in q:
        return True
    return False


def _is_simple_keyword_query(raw_query: str, query_norm: str, query_compact: str) -> bool:
    raw_value = str(raw_query or "").strip()
    norm_value = str(query_norm or "").strip().lower()
    compact_value = str(query_compact or "").strip().lower()

    candidate = compact_value or norm_value or raw_value.lower()
    if not candidate:
        return False
    if len(candidate) < 3 or len(candidate) > 48:
        return False
    if _contains_cjk(candidate):
        return False
    if not _SIMPLE_KEYWORD_RE.match(candidate):
        return False

    for value in (raw_value, norm_value, compact_value):
        if not value:
            continue
        if any(ch.isspace() for ch in value):
            return False
        if "/" in value or "\\" in value or "." in value or "_" in value or "-" in value:
            return False

    return True


def is_filenameish(raw_query: str, query_tokens: Optional[List[str]] = None, query_compact: str = "") -> bool:
    return is_filenameish_query(raw_query, query_tokens=query_tokens, query_compact=query_compact)


def classify_query(raw_query: str, query_compact: str, query_tokens: List[str]) -> str:
    guard = analyze_search_query(raw_query)
    if not guard.get("query_class") and is_filenameish(
        raw_query,
        query_tokens=query_tokens,
        query_compact=query_compact,
    ):
        return "filename"
    return str(guard.get("query_class") or "keyword")


def _is_fts_bareword(value: str) -> bool:
    s = str(value or "").strip()
    if not s:
        return False
    return all(ch.isalnum() or ch == "_" for ch in s)


def _fts_escape(value: str) -> str:
    s = str(value or "").strip()
    return '"' + s.replace('"', '""') + '"'


def _fts_term(value: str, prefix: bool = False) -> str:
    s = str(value or "").strip()
    if not s:
        return ""
    if _is_fts_bareword(s):
        return f"{s}*" if prefix else s
    return _fts_escape(s)


def _cjk_chars(value: str) -> List[str]:
    return [ch for ch in str(value or "").strip() if not ch.isspace()]


def _is_cjk_char(ch: str) -> bool:
    if not ch:
        return False
    code = ord(ch)
    return (
        0x4E00 <= code <= 0x9FFF
        or 0x3400 <= code <= 0x4DBF
        or 0x20000 <= code <= 0x2A6DF
        or 0x2A700 <= code <= 0x2B73F
        or 0xF900 <= code <= 0xFAFF
    )


def _is_all_cjk(value: str, min_len: int = 1, max_len: int = 8) -> bool:
    chars = _cjk_chars(value)
    if not chars:
        return False
    if len(chars) < min_len or len(chars) > max_len:
        return False
    return all(_is_cjk_char(ch) for ch in chars)


def _is_short_cjk(value: str) -> bool:
    return _is_all_cjk(value, min_len=1, max_len=4)


def _cjk_bigrams(value: str, limit: int = 4) -> List[str]:
    chars = [ch for ch in str(value or "").strip() if _is_cjk_char(ch)]
    out: List[str] = []
    for idx in range(0, max(0, len(chars) - 1)):
        gram = "".join(chars[idx:idx + 2])
        if gram:
            out.append(gram)
        if len(out) >= int(limit):
            break
    return dedupe_keep_order(out)


def _is_cjk_phrase_candidate(value: str) -> bool:
    chars = [ch for ch in str(value or "").strip() if _is_cjk_char(ch)]
    if len(chars) < 5 or len(chars) > 24:
        return False
    return True


def _normalize_pathish(value: str) -> str:
    return str(value or "").strip().replace("\\", "/")


def _basename_of(value: str) -> str:
    raw = _normalize_pathish(value).rstrip("/")
    if not raw:
        return ""
    return Path(raw).name.strip()


def _stem_of(value: str) -> str:
    raw = str(value or "").strip().rstrip(".")
    if not raw:
        return ""
    return Path(raw).stem.strip()


def _build_filename_alias_payloads(
    raw_query: str,
    query_norm: str,
    query_compact: str,
) -> List[Dict[str, str]]:
    q = str(raw_query or "").strip()
    norm = str(query_norm or "").strip()
    compact = str(query_compact or "").strip()

    if _is_simple_keyword_query(q, norm, compact) and not _is_explicit_filename_query(q):
        guard = analyze_search_query(q or norm or compact)
        return [
            {
                "raw": str(guard.get("raw_query_used") or q or "").strip(),
                "norm": str(guard.get("query_norm") or norm or "").strip(),
                "compact": str(guard.get("query_compact") or compact or "").strip(),
            }
        ]

    aliases: List[str] = []
    seen = set()

    def _push(value: str) -> None:
        v = str(value or "").strip()
        if not v or v in seen:
            return
        seen.add(v)
        aliases.append(v)

    normalized = _normalize_pathish(q)
    trimmed = normalized.rstrip(". ").strip()
    basename = _basename_of(normalized)
    basename_trimmed = str(basename or "").rstrip(". ").strip()
    stem_source = basename_trimmed or trimmed or normalized
    stem = _stem_of(stem_source)

    _push(q)
    _push(normalized)
    _push(trimmed)
    _push(basename)
    _push(basename_trimmed)
    _push(stem)
    _push(norm)
    _push(compact)

    payloads: List[Dict[str, str]] = []
    seen_payload = set()

    for alias in aliases:
        guard = analyze_search_query(alias)
        alias_raw = str(guard.get("raw_query_used") or alias or "").strip()
        alias_norm = str(guard.get("query_norm") or alias or "").strip()
        alias_compact = str(guard.get("query_compact") or alias or "").strip()

        key = (alias_raw, alias_norm, alias_compact)
        if key in seen_payload:
            continue
        seen_payload.add(key)

        payloads.append(
            {
                "raw": alias_raw,
                "norm": alias_norm,
                "compact": alias_compact,
            }
        )

    return payloads


def build_title_fts_exprs(
    query_norm: str,
    query_compact: str,
    query_tokens: List[str],
    query_kind: str,
) -> List[str]:
    exprs: List[str] = []
    compact = str(query_compact or "").strip()
    norm = str(query_norm or "").strip()

    tokens = [t for t in query_tokens if len(t) >= 2 and t.lower() not in FTS_QUERY_RESERVED]
    tokens = dedupe_keep_order(tokens)

    if query_kind in {"long_phrase", "long_nl"}:
        strong = sorted(tokens, key=lambda x: (-len(x), x))[:3]
        if query_kind == "long_phrase" and 4 <= len(norm) <= 80:
            exprs.append(_fts_term(norm, prefix=False))
        if strong:
            exprs.append(" AND ".join(_fts_term(t, prefix=False) for t in strong))
        return dedupe_keep_order([e for e in exprs if e])

    if compact and 3 <= len(compact) <= 24:
        exprs.append(_fts_term(compact, prefix=False))

    if norm and norm != compact and 3 <= len(norm) <= 64 and query_kind not in {"short", "short_cjk"}:
        exprs.append(_fts_term(norm, prefix=False))

    if len(tokens) >= 2:
        strong = sorted(tokens, key=lambda x: (-len(x), x))[:3]
        exprs.append(" AND ".join(_fts_term(t, prefix=False) for t in strong))
    elif len(tokens) == 1 and 3 <= len(tokens[0]) <= 24 and query_kind == "keyword":
        exprs.append(_fts_term(tokens[0], prefix=False))

    return dedupe_keep_order([e for e in exprs if e])


def build_content_fts_exprs(
    query_norm: str,
    query_compact: str,
    query_tokens: List[str],
    query_kind: str,
) -> List[str]:
    if query_kind in {"symbol_heavy", "filename", "short", "short_cjk"}:
        return []

    exprs: List[str] = []
    compact = str(query_compact or "").strip()
    norm = str(query_norm or "").strip()

    if query_kind in {"long_nl", "long_phrase"}:
        tokens = [t for t in query_tokens if len(t) >= 4 and t.lower() not in FTS_QUERY_RESERVED]
        tokens = dedupe_keep_order(tokens)
        strong = sorted(tokens, key=lambda x: (-len(x), x))[:3]
        if strong:
            exprs.append(" AND ".join(_fts_term(t, prefix=False) for t in strong))
        return dedupe_keep_order([e for e in exprs if e])

    if 4 <= len(compact) <= 20:
        exprs.append(_fts_term(compact, prefix=False))
    if norm and norm != compact and 4 <= len(norm) <= 64:
        exprs.append(_fts_term(norm, prefix=False))

    tokens = [t for t in query_tokens if len(t) >= 3 and t.lower() not in FTS_QUERY_RESERVED]
    tokens = dedupe_keep_order(tokens)

    if len(tokens) >= 2:
        strong = sorted(tokens, key=lambda x: (-len(x), x))[:3]
        exprs.append(" AND ".join(_fts_term(t, prefix=False) for t in strong))
    elif len(tokens) == 1 and 4 <= len(tokens[0]) <= 20:
        exprs.append(_fts_term(tokens[0], prefix=False))

    return dedupe_keep_order([e for e in exprs if e])



def recall_fts_available(conn: sqlite3.Connection) -> bool:
    return _table_exists(conn, "search_recall_docs") and _table_exists(conn, "search_fts_recall")


def _split_symbolish_recall_terms(values: List[str]) -> List[str]:
    out: List[str] = []
    for value in values:
        text = str(value or "").strip()
        if not text:
            continue
        out.append(text)
        for token in re.split(r"[\\/\s._\-:()\[\]{}'\"`，。！？；：、]+", text):
            token = token.strip()
            if token:
                out.append(token)
    return dedupe_keep_order(out)


def build_recall_fts_exprs(
    query_norm: str,
    query_compact: str,
    query_tokens: List[str],
    query_kind: str,
) -> List[str]:

    exprs: List[str] = []
    compact = str(query_compact or "").strip()
    norm = str(query_norm or "").strip()
    tokens = dedupe_keep_order([str(t or "").strip() for t in query_tokens if str(t or "").strip()])

    if query_kind in {"symbol_heavy", "filename"}:
        candidates = _split_symbolish_recall_terms([compact, norm] + tokens)
        strong = [
            t for t in candidates
            if 2 <= len(t) <= 40 and t.lower() not in FTS_QUERY_RESERVED
        ]
        strong = sorted(dedupe_keep_order(strong), key=lambda x: (-len(x), x))[:5]

        if len(strong) >= 3:
            exprs.append(" AND ".join(_fts_term(t, prefix=False) for t in strong[:3]))
        if len(strong) >= 2:
            exprs.append(" AND ".join(_fts_term(t, prefix=False) for t in strong[:2]))
        if len(strong) == 1:
            exprs.append(_fts_term(strong[0], prefix=False))

        for token in strong[:4]:
            if 2 <= len(token) <= 24:
                exprs.append(_fts_term(token, prefix=True))

        return dedupe_keep_order([e for e in exprs if e])

    if query_kind == "short_cjk":
        candidates: List[str] = []
        if 2 <= len(compact) <= 16 and _contains_cjk(compact):
            candidates.append(compact)
        if norm and norm != compact and 2 <= len(norm) <= 16 and _contains_cjk(norm):
            candidates.append(norm)
        for token in tokens:
            if 2 <= len(token) <= 16 and _contains_cjk(token):
                candidates.append(token)
        for value in dedupe_keep_order(candidates):
            exprs.append(_fts_term(value, prefix=False))
            if 2 <= len(value) <= 8:
                exprs.append(_fts_term(value, prefix=True))
        return dedupe_keep_order([e for e in exprs if e])

    if query_kind not in {"short_cjk", "filename", "symbol_heavy"} and (
        _is_cjk_phrase_candidate(compact) or _is_cjk_phrase_candidate(norm)
    ):
        cjk_exprs: List[str] = []
        if 5 <= len(compact) <= 32 and _contains_cjk(compact):
            cjk_exprs.append(_fts_term(compact, prefix=False))
        if norm and norm != compact and 5 <= len(norm) <= 64 and _contains_cjk(norm):
            cjk_exprs.append(_fts_term(norm, prefix=False))

        cjk_tokens = [
            t for t in tokens
            if 2 <= len(t) <= 16 and _contains_cjk(t) and t.lower() not in FTS_QUERY_RESERVED
        ]
        cjk_tokens = sorted(dedupe_keep_order(cjk_tokens), key=lambda x: (-len(x), x))[:4]
        if len(cjk_tokens) >= 2:
            cjk_exprs.append(" AND ".join(_fts_term(t, prefix=False) for t in cjk_tokens[:3]))
        elif len(cjk_tokens) == 1:
            cjk_exprs.append(_fts_term(cjk_tokens[0], prefix=False))

        grams_source = compact if _is_cjk_phrase_candidate(compact) else norm
        grams = _cjk_bigrams(grams_source, limit=4)
        if len(grams) >= 2:
            cjk_exprs.append(" AND ".join(_fts_term(g, prefix=False) for g in grams[:3]))

        exprs.extend(cjk_exprs[:4])
        return dedupe_keep_order([e for e in exprs if e])

    if query_kind in {"long_nl", "long_phrase"}:
        strong = [
            t for t in tokens
            if 3 <= len(t) <= 32 and t.lower() not in FTS_QUERY_RESERVED
        ]
        strong = sorted(dedupe_keep_order(strong), key=lambda x: (-len(x), x))[:4]

        if len(strong) >= 3:
            exprs.append(" AND ".join(_fts_term(t, prefix=False) for t in strong[:3]))
        if len(strong) >= 2:
            exprs.append(" AND ".join(_fts_term(t, prefix=False) for t in strong[:2]))
        if len(strong) == 1:
            exprs.append(_fts_term(strong[0], prefix=False))

        if query_kind == "long_phrase" and 8 <= len(norm) <= 96 and _contains_cjk(norm):
            exprs.insert(0, _fts_term(norm, prefix=False))

        return dedupe_keep_order([e for e in exprs if e])[:3]

    if 3 <= len(compact) <= 48:
        exprs.append(_fts_term(compact, prefix=False))
    if norm and norm != compact and 3 <= len(norm) <= 64:
        exprs.append(_fts_term(norm, prefix=False))

    strong = [
        t for t in tokens
        if 3 <= len(t) <= 32 and t.lower() not in FTS_QUERY_RESERVED
    ]
    strong = sorted(dedupe_keep_order(strong), key=lambda x: (-len(x), x))[:3]
    if len(strong) >= 2:
        exprs.append(" AND ".join(_fts_term(t, prefix=False) for t in strong))
    elif len(strong) == 1:
        exprs.append(_fts_term(strong[0], prefix=False))

    return dedupe_keep_order([e for e in exprs if e])


def fetch_fts_recall(
    conn: sqlite3.Connection,
    module: str,
    exprs: List[str],
    limit: int,
) -> List[sqlite3.Row]:
    if not recall_fts_available(conn) or not exprs or limit <= 0:
        return []

    merged: Dict[str, sqlite3.Row] = {}
    row_limit = _dynamic_limit(limit, floor=12, default_cap=48, recall_cap=64, module=module)

    for expr in exprs:
        if len(merged) >= limit:
            break
        rows = _safe_fetchall(
            conn,
            """
            SELECT
              d.recall_text AS snippet,
              d.source_kind AS matched_source_kind,
              d.tier AS recall_tier,
              d.chunk_index AS recall_chunk_index,
              d.recall_text AS matched_recall_text,
              e.*,
              bm25(search_fts_recall) AS fts_rank
            FROM search_fts_recall
            JOIN search_recall_docs d ON d.recall_id = search_fts_recall.rowid
            JOIN search_entries e ON e.item_key = d.parent_item_key
            WHERE d.module = ?
              AND e.module = ?
              AND search_fts_recall MATCH ?
              AND lower(COALESCE(d.parent_path, '')) NOT IN ('agent_files/.trash', 'agent_files/.history')
              AND lower(COALESCE(d.parent_path, '')) NOT LIKE 'agent_files/.trash/%'
              AND lower(COALESCE(d.parent_path, '')) NOT LIKE '%/.trash/%'
              AND lower(COALESCE(d.parent_path, '')) NOT LIKE 'agent_files/.history/%'
              AND lower(COALESCE(d.parent_path, '')) NOT LIKE '%/.history/%'
            ORDER BY
              d.tier ASC,
              bm25(search_fts_recall),
              e.priority_hint DESC,
              e.updated_at DESC
            LIMIT ?
            """,
            (module, module, expr, row_limit),
            timeout_ms=900,
            progress_steps=1500,
        )
        _merge_rows(merged, rows, limit)

    return list(merged.values())[:limit]


def _safe_fetchall(
    conn: sqlite3.Connection,
    sql: str,
    params: tuple,
    timeout_ms: int,
    progress_steps: int = 1000,
) -> List[sqlite3.Row]:
    callbacks_limit = max(1, int(timeout_ms))
    callback_count = {"n": 0}

    def _progress() -> int:
        callback_count["n"] += 1
        if callback_count["n"] >= callbacks_limit:
            return 1
        return 0

    conn.set_progress_handler(_progress, progress_steps)
    try:
        return conn.execute(sql, params).fetchall()
    except Exception:
        return []
    finally:
        conn.set_progress_handler(None, 0)


def _merge_rows(merged: Dict[str, sqlite3.Row], rows: List[sqlite3.Row], limit: int) -> None:
    for row in rows:
        key = str(row["item_key"])
        if key not in merged:
            merged[key] = row
        if len(merged) >= limit:
            break


def _escape_like(value: str) -> str:
    return str(value or "").replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _prefix_bounds(value: str) -> Optional[Tuple[str, str]]:
    prefix = str(value or "").strip()
    if not prefix:
        return None
    return prefix, prefix + "\uffff"


def _select_entries_exact(
    conn: sqlite3.Connection,
    module: str,
    field: str,
    value: str,
    limit: int,
    timeout_ms: int = SELECT_TIMEOUT_MS,
) -> List[sqlite3.Row]:
    if field not in ALLOWED_SEARCH_FIELDS:
        return []

    val = str(value or "").strip()
    if not val or limit <= 0:
        return []

    sql = f"""
        SELECT *, 0.0 AS fts_rank
        FROM search_entries
        WHERE module = ?
          AND {field} = ?
        ORDER BY
          CASE
            WHEN lower(COALESCE(path, '')) LIKE '%.trash/%'
              OR lower(COALESCE(path, '')) LIKE '.trash/%'
            THEN 1 ELSE 0
          END ASC,
          priority_hint DESC, updated_at DESC
        LIMIT ?
    """
    return _safe_fetchall(conn, sql, (module, val, int(limit)), timeout_ms=timeout_ms)


def _select_entries_prefix(
    conn: sqlite3.Connection,
    module: str,
    field: str,
    prefix: str,
    limit: int,
    timeout_ms: int = SELECT_TIMEOUT_MS,
) -> List[sqlite3.Row]:
    if field not in ALLOWED_SEARCH_FIELDS:
        return []

    bounds = _prefix_bounds(prefix)
    if not bounds or limit <= 0:
        return []

    lower, upper = bounds
    sql = f"""
        SELECT *, 0.0 AS fts_rank
        FROM search_entries
        WHERE module = ?
          AND {field} >= ?
          AND {field} < ?
        ORDER BY
          CASE
            WHEN lower(COALESCE(path, '')) LIKE '%.trash/%'
              OR lower(COALESCE(path, '')) LIKE '.trash/%'
            THEN 1 ELSE 0
          END ASC,
          priority_hint DESC, updated_at DESC
        LIMIT ?
    """
    return _safe_fetchall(conn, sql, (module, lower, upper, int(limit)), timeout_ms=timeout_ms)


def _select_entries_contains(
    conn: sqlite3.Connection,
    module: str,
    field: str,
    value: str,
    limit: int,
    timeout_ms: int = SELECT_TIMEOUT_MS,
) -> List[sqlite3.Row]:
    if field not in ALLOWED_SEARCH_FIELDS:
        return []

    val = str(value or "").strip()
    if not val or limit <= 0:
        return []

    sql = f"""
        SELECT *, 0.0 AS fts_rank
        FROM search_entries
        WHERE module = ?
          AND {field} <> ''
          AND {field} LIKE ? ESCAPE '\\'
        ORDER BY
          CASE
            WHEN lower(COALESCE(path, '')) LIKE '%.trash/%'
              OR lower(COALESCE(path, '')) LIKE '.trash/%'
            THEN 1 ELSE 0
          END ASC,
          priority_hint DESC, updated_at DESC
        LIMIT ?
    """
    return _safe_fetchall(
        conn,
        sql,
        (module, f"%{_escape_like(val)}%", int(limit)),
        timeout_ms=timeout_ms,
        progress_steps=250,
    )


def _select_chat_meta_exact(
    conn: sqlite3.Connection,
    field: str,
    value: str,
    limit: int,
    timeout_ms: int = SELECT_TIMEOUT_MS,
) -> List[sqlite3.Row]:
    if field not in ALLOWED_SEARCH_FIELDS:
        return []

    val = str(value or "").strip()
    if not val or limit <= 0:
        return []

    sql = f"""
        SELECT *, 0.0 AS fts_rank
        FROM search_entries
        WHERE module = 'chat'
          AND source_kind = 'chat_meta'
          AND {field} = ?
        ORDER BY updated_at DESC
        LIMIT ?
    """
    return _safe_fetchall(conn, sql, (val, int(limit)), timeout_ms=timeout_ms)


def _select_chat_meta_prefix(
    conn: sqlite3.Connection,
    field: str,
    prefix: str,
    limit: int,
    timeout_ms: int = 320,
) -> List[sqlite3.Row]:
    if field not in ALLOWED_SEARCH_FIELDS:
        return []

    bounds = _prefix_bounds(prefix)
    if not bounds or limit <= 0:
        return []

    lower, upper = bounds
    sql = f"""
        SELECT *, 0.0 AS fts_rank
        FROM search_entries
        WHERE module = 'chat'
          AND source_kind = 'chat_meta'
          AND {field} >= ?
          AND {field} < ?
        ORDER BY updated_at DESC
        LIMIT ?
    """
    return _safe_fetchall(conn, sql, (lower, upper, int(limit)), timeout_ms=timeout_ms)


def fetch_chat_title_fast(
    conn: sqlite3.Connection,
    raw_query: str,
    query_norm: str,
    query_compact: str,
    limit: int,
    exact_only: bool = False,
) -> List[sqlite3.Row]:
    merged: Dict[str, sqlite3.Row] = {}

    row_limit = _dynamic_limit(limit, floor=8, default_cap=32, recall_cap=32, module="chat")
    if row_limit <= 0:
        return []

    raw_value = str(raw_query or "").strip()
    norm_value = str(query_norm or "").strip()
    compact_value = str(query_compact or "").strip()

    for field, value in [
        ("title", raw_value),
        ("title_norm", norm_value),
        ("title_compact", compact_value),
    ]:
        if value:
            _merge_rows(merged, _select_chat_meta_exact(conn, field, value, row_limit, timeout_ms=260), limit)

    if merged:
        return list(merged.values())[:limit]

    if exact_only:
        return []

    raw_prefix_min = 2 if _is_short_cjk(raw_value) else 3
    norm_prefix_min = 2 if _is_short_cjk(norm_value) else 3
    compact_prefix_min = 2 if _is_short_cjk(compact_value) else 4

    if len(raw_value) >= raw_prefix_min:
        _merge_rows(merged, _select_chat_meta_prefix(conn, "title", raw_value, row_limit), limit)
        if len(merged) >= limit:
            return list(merged.values())[:limit]

    if len(norm_value) >= norm_prefix_min:
        _merge_rows(merged, _select_chat_meta_prefix(conn, "title_norm", norm_value, row_limit), limit)
        if len(merged) >= limit:
            return list(merged.values())[:limit]

    if len(compact_value) >= compact_prefix_min:
        _merge_rows(merged, _select_chat_meta_prefix(conn, "title_compact", compact_value, row_limit), limit)

    return list(merged.values())[:limit]


def fetch_fts_title(
    conn: sqlite3.Connection,
    module: str,
    exprs: List[str],
    limit: int,
) -> List[sqlite3.Row]:
    if not _table_exists(conn, "search_fts_title") or not exprs or limit <= 0:
        return []

    merged: Dict[str, sqlite3.Row] = {}
    row_limit = _dynamic_limit(limit, floor=24, default_cap=64, recall_cap=160, module=module)

    for expr in exprs:
        if len(merged) >= limit:
            break
        rows = _safe_fetchall(
            conn,
            """
            SELECT e.*, bm25(search_fts_title) AS fts_rank
            FROM search_fts_title
            JOIN search_entries e ON e.rowid = search_fts_title.rowid
            WHERE e.module = ?
              AND search_fts_title MATCH ?
            ORDER BY
              CASE
                WHEN lower(COALESCE(e.path, '')) LIKE '%.trash/%'
                  OR lower(COALESCE(e.path, '')) LIKE '.trash/%'
                THEN 1 ELSE 0
              END ASC,
              bm25(search_fts_title), e.priority_hint DESC, e.updated_at DESC
            LIMIT ?
            """,
            (module, expr, row_limit),
            timeout_ms=FTS_TIMEOUT_MS,
            progress_steps=2000,
        )
        _merge_rows(merged, rows, limit)

    return list(merged.values())[:limit]


def fetch_fts_content(
    conn: sqlite3.Connection,
    module: str,
    exprs: List[str],
    limit: int,
) -> List[sqlite3.Row]:
    if not _table_exists(conn, "search_fts_content") or not exprs or limit <= 0:
        return []

    merged: Dict[str, sqlite3.Row] = {}
    row_limit = _dynamic_limit(limit, floor=24, default_cap=64, recall_cap=160, module=module)

    for expr in exprs:
        if len(merged) >= limit:
            break
        rows = _safe_fetchall(
            conn,
            """
            SELECT e.*, bm25(search_fts_content) AS fts_rank
            FROM search_fts_content
            JOIN search_entries e ON e.rowid = search_fts_content.rowid
            WHERE e.module = ?
              AND search_fts_content MATCH ?
            ORDER BY
              CASE
                WHEN lower(COALESCE(e.path, '')) LIKE '%.trash/%'
                  OR lower(COALESCE(e.path, '')) LIKE '.trash/%'
                THEN 1 ELSE 0
              END ASC,
              bm25(search_fts_content), e.priority_hint DESC, e.updated_at DESC
            LIMIT ?
            """,
            (module, expr, row_limit),
            timeout_ms=FTS_TIMEOUT_MS,
            progress_steps=2000,
        )
        _merge_rows(merged, rows, limit)

    return list(merged.values())[:limit]


def fetch_filename_fast(
    conn: sqlite3.Connection,
    module: str,
    raw_query: str,
    query_norm: str,
    query_compact: str,
    limit: int,
) -> List[sqlite3.Row]:
    merged: Dict[str, sqlite3.Row] = {}
    row_limit = _dynamic_limit(limit, floor=16, default_cap=48, recall_cap=160, module=module)
    if row_limit <= 0:
        return []

    raw_value = str(raw_query or "").strip()
    explicit_filename = _is_explicit_filename_query(raw_value)
    path_like = "/" in raw_value or "\\" in raw_value

    alias_payloads = _build_filename_alias_payloads(
        raw_query=raw_query,
        query_norm=query_norm,
        query_compact=query_compact,
    )

    if not alias_payloads:
        return []

    for payload in alias_payloads:
        raw_alias = str(payload.get("raw") or "").strip()
        norm_alias = str(payload.get("norm") or "").strip()
        compact_alias = str(payload.get("compact") or "").strip()

        raw_exact_fields = ["filename", "title"] + (["path"] if path_like else [])
        norm_exact_fields = ["filename_norm", "title_norm"] + (["path_norm"] if path_like else [])
        compact_exact_fields = ["filename_compact", "title_compact"] + (["path_compact"] if path_like else [])

        for field in raw_exact_fields:
            if raw_alias:
                _merge_rows(merged, _select_entries_exact(conn, module, field, raw_alias, row_limit), limit)
                if len(merged) >= limit:
                    return list(merged.values())[:limit]

        for field in norm_exact_fields:
            if norm_alias:
                _merge_rows(merged, _select_entries_exact(conn, module, field, norm_alias, row_limit), limit)
                if len(merged) >= limit:
                    return list(merged.values())[:limit]

        for field in compact_exact_fields:
            if compact_alias:
                _merge_rows(merged, _select_entries_exact(conn, module, field, compact_alias, row_limit), limit)
                if len(merged) >= limit:
                    return list(merged.values())[:limit]

    for payload in alias_payloads:
        raw_alias = str(payload.get("raw") or "").strip()
        norm_alias = str(payload.get("norm") or "").strip()
        compact_alias = str(payload.get("compact") or "").strip()

        if len(raw_alias) >= 2:
            raw_prefix_fields = ["filename", "title"] + (["path"] if path_like else [])
            for field in raw_prefix_fields:
                _merge_rows(
                    merged,
                    _select_entries_prefix(conn, module, field, raw_alias, row_limit, timeout_ms=450),
                    limit,
                )
                if len(merged) >= limit:
                    return list(merged.values())[:limit]

        if len(norm_alias) >= 2:
            norm_prefix_fields = ["filename_norm", "title_norm"] + (["path_norm"] if path_like else [])
            for field in norm_prefix_fields:
                _merge_rows(
                    merged,
                    _select_entries_prefix(conn, module, field, norm_alias, row_limit, timeout_ms=450),
                    limit,
                )
                if len(merged) >= limit:
                    return list(merged.values())[:limit]

        if len(compact_alias) >= 2:
            compact_prefix_fields = ["filename_compact", "title_compact"] + (["path_compact"] if path_like else [])
            for field in compact_prefix_fields:
                _merge_rows(
                    merged,
                    _select_entries_prefix(conn, module, field, compact_alias, row_limit, timeout_ms=450),
                    limit,
                )
                if len(merged) >= limit:
                    return list(merged.values())[:limit]

    if (not merged or len(merged) < max(6, min(limit, 24))) and explicit_filename:
        contain_limit = _dynamic_limit(limit, floor=12, default_cap=32, recall_cap=96, module=module)

        for payload in alias_payloads:
            raw_alias = str(payload.get("raw") or "").strip()
            norm_alias = str(payload.get("norm") or "").strip()
            compact_alias = str(payload.get("compact") or "").strip()

            contain_specs = [
                ("filename", raw_alias),
                ("title", raw_alias),
                ("path", raw_alias),
                ("filename_norm", norm_alias),
                ("title_norm", norm_alias),
                ("path_norm", norm_alias),
                ("filename_compact", compact_alias),
                ("title_compact", compact_alias),
                ("path_compact", compact_alias),
            ]

            for field, value in contain_specs:
                val = str(value or "").strip()
                if len(val) < 2:
                    continue
                _merge_rows(
                    merged,
                    _select_entries_contains(conn, module, field, val, contain_limit, timeout_ms=260),
                    limit,
                )
                if len(merged) >= limit:
                    break

            if len(merged) >= limit:
                break

    return list(merged.values())[:limit]


def fetch_direct_title(
    conn: sqlite3.Connection,
    module: str,
    raw_query: str,
    query_norm: str,
    query_compact: str,
    limit: int,
    explicit_filename: bool = False,
) -> List[sqlite3.Row]:
    if module == "chat":
        return fetch_chat_title_fast(
            conn=conn,
            raw_query=raw_query,
            query_norm=query_norm,
            query_compact=query_compact,
            limit=limit,
            exact_only=False,
        )

    merged: Dict[str, sqlite3.Row] = {}
    row_limit = _dynamic_limit(limit, floor=16, default_cap=48, recall_cap=160, module=module)
    contain_limit = _dynamic_limit(limit, floor=12, default_cap=24, recall_cap=96, module=module)
    if row_limit <= 0:
        return []

    raw_value = str(raw_query or "").strip()
    explicit_filename = bool(explicit_filename or _is_explicit_filename_query(raw_value))
    path_like = "/" in raw_value or "\\" in raw_value
    simple_keyword = _is_simple_keyword_query(raw_value, query_norm, query_compact)

    alias_payloads = _build_filename_alias_payloads(
        raw_query=raw_query,
        query_norm=query_norm,
        query_compact=query_compact,
    )
    if not alias_payloads:
        return []

    if explicit_filename:
        fast_rows = fetch_filename_fast(
            conn=conn,
            module=module,
            raw_query=raw_query,
            query_norm=query_norm,
            query_compact=query_compact,
            limit=min(limit, row_limit),
        )
        _merge_rows(merged, fast_rows, limit)
        if len(merged) >= limit:
            return list(merged.values())[:limit]

    for payload in alias_payloads:
        raw_alias = str(payload.get("raw") or "").strip()
        norm_alias = str(payload.get("norm") or "").strip()
        compact_alias = str(payload.get("compact") or "").strip()

        exact_specs: List[Tuple[str, str]] = [
            ("title", raw_alias),
            ("title_norm", norm_alias),
            ("title_compact", compact_alias),
        ]

        if module == "library":
            exact_specs = [
                ("library_name", raw_alias),
                ("library_name_norm", norm_alias),
                ("library_name_compact", compact_alias),
                ("title", raw_alias),
                ("title_norm", norm_alias),
                ("title_compact", compact_alias),
            ]

        if explicit_filename and module in {"doc", "files", "dirs", "library"}:
            exact_specs.extend(
                [
                    ("filename", raw_alias),
                    ("filename_norm", norm_alias),
                    ("filename_compact", compact_alias),
                ]
            )
            if path_like:
                exact_specs.extend(
                    [
                        ("path", raw_alias),
                        ("path_norm", norm_alias),
                        ("path_compact", compact_alias),
                    ]
                )

        for field, value in exact_specs:
            val = str(value or "").strip()
            if not val:
                continue
            _merge_rows(merged, _select_entries_exact(conn, module, field, val, row_limit), limit)
            if len(merged) >= limit:
                return list(merged.values())[:limit]

    for payload in alias_payloads:
        raw_alias = str(payload.get("raw") or "").strip()
        norm_alias = str(payload.get("norm") or "").strip()
        compact_alias = str(payload.get("compact") or "").strip()

        prefix_specs: List[Tuple[str, str]] = [
            ("title", raw_alias),
            ("title_norm", norm_alias),
            ("title_compact", compact_alias),
        ]

        if module == "library":
            prefix_specs = [
                ("library_name", raw_alias),
                ("library_name_norm", norm_alias),
                ("library_name_compact", compact_alias),
                ("title", raw_alias),
                ("title_norm", norm_alias),
                ("title_compact", compact_alias),
            ]

        for field, value in prefix_specs:
            val = str(value or "").strip()
            if len(val) < 2:
                continue
            _merge_rows(
                merged,
                _select_entries_prefix(conn, module, field, val, row_limit, timeout_ms=450),
                limit,
            )
            if len(merged) >= limit:
                return list(merged.values())[:limit]

    filename_prefix_threshold = max(2, min(limit, 8)) if simple_keyword else max(4, min(limit, 20))
    if len(merged) < filename_prefix_threshold and module in {"doc", "files", "dirs", "library"}:
        for payload in alias_payloads:
            for field, value in [
                ("filename", payload.get("raw")),
                ("filename_norm", payload.get("norm")),
                ("filename_compact", payload.get("compact")),
            ]:
                val = str(value or "").strip()
                if len(val) < 2:
                    continue
                _merge_rows(
                    merged,
                    _select_entries_prefix(conn, module, field, val, row_limit, timeout_ms=450),
                    limit,
                )
                if len(merged) >= limit:
                    return list(merged.values())[:limit]

    if not simple_keyword and (explicit_filename or path_like or len(merged) < max(4, min(limit, 20))):
        for payload in alias_payloads:
            for field, value in [
                ("path", payload.get("raw")),
                ("path_norm", payload.get("norm")),
                ("path_compact", payload.get("compact")),
            ]:
                val = str(value or "").strip()
                if len(val) < 2:
                    continue
                _merge_rows(
                    merged,
                    _select_entries_prefix(conn, module, field, val, row_limit, timeout_ms=450),
                    limit,
                )
                if len(merged) >= limit:
                    return list(merged.values())[:limit]

    if len(merged) < max(4, min(limit, 16)):
        for payload in alias_payloads:
            compact_alias = str(payload.get("compact") or "").strip()
            raw_alias = str(payload.get("raw") or "").strip()
            norm_alias = str(payload.get("norm") or "").strip()

            if simple_keyword:
                contain_fields: List[Tuple[str, str]] = [
                    ("title_compact", compact_alias),
                    ("title_norm", norm_alias),
                    ("title", raw_alias),
                ]
                if module == "library":
                    contain_fields = [
                        ("library_name_compact", compact_alias),
                        ("library_name_norm", norm_alias),
                        ("library_name", raw_alias),
                    ] + contain_fields
            else:
                contain_fields = [
                    ("title_compact", compact_alias),
                    ("title_norm", norm_alias),
                    ("title", raw_alias),
                ]

                if module in {"doc", "files", "dirs", "library"}:
                    contain_fields.extend(
                        [
                            ("filename_compact", compact_alias),
                            ("filename_norm", norm_alias),
                            ("filename", raw_alias),
                        ]
                    )

                if module == "library":
                    contain_fields = [
                        ("library_name_compact", compact_alias),
                        ("library_name_norm", norm_alias),
                        ("library_name", raw_alias),
                    ] + contain_fields

                if explicit_filename or path_like:
                    contain_fields.extend(
                        [
                            ("path_compact", compact_alias),
                            ("path_norm", norm_alias),
                            ("path", raw_alias),
                        ]
                    )

            contain_timeout = 180 if simple_keyword else 220

            for field, value in contain_fields:
                val = str(value or "").strip()
                if len(val) < 2:
                    continue
                _merge_rows(
                    merged,
                    _select_entries_contains(conn, module, field, val, contain_limit, timeout_ms=contain_timeout),
                    limit,
                )
                if len(merged) >= limit:
                    break

            if len(merged) >= limit:
                break

    return list(merged.values())[:limit]


def fetch_direct_content_entries(
    conn: sqlite3.Connection,
    module: str,
    raw_query: str,
    query_norm: str,
    query_compact: str,
    limit: int,
) -> List[sqlite3.Row]:
    merged: Dict[str, sqlite3.Row] = {}

    raw_value = str(raw_query or "").strip()
    norm_value = str(query_norm or "").strip()
    compact_value = str(query_compact or "").strip()
    simple_keyword = _is_simple_keyword_query(raw_value, norm_value, compact_value)

    row_limit = _dynamic_limit(
        limit,
        floor=12 if simple_keyword else 16,
        default_cap=24 if simple_keyword else 32,
        recall_cap=96 if simple_keyword else 128,
        module=module,
    )
    if row_limit <= 0:
        return []

    short_cjk = _is_short_cjk(raw_value) or _is_short_cjk(norm_value) or _is_short_cjk(compact_value)
    cjkish = (
        _is_all_cjk(raw_value, min_len=1, max_len=8)
        or _is_all_cjk(norm_value, min_len=1, max_len=8)
        or _is_all_cjk(compact_value, min_len=1, max_len=8)
    )

    if short_cjk:
        contain_specs = [
            ("snippet_compact", compact_value),
            ("snippet_norm", norm_value),
            ("snippet", raw_value or norm_value),
        ]
        for field, value in contain_specs:
            val = str(value or "").strip()
            if not val:
                continue
            _merge_rows(
                merged,
                _select_entries_contains(conn, module, field, val, row_limit, timeout_ms=320),
                limit,
            )
            if len(merged) >= limit:
                break
        return list(merged.values())[:limit]

    if simple_keyword:
        if 3 <= len(compact_value) <= 48:
            _merge_rows(
                merged,
                _select_entries_contains(conn, module, "snippet_compact", compact_value, row_limit, timeout_ms=180),
                limit,
            )

        if len(merged) < max(4, min(limit, 12)) and norm_value and norm_value != compact_value and 3 <= len(norm_value) <= 64:
            _merge_rows(
                merged,
                _select_entries_contains(conn, module, "snippet_norm", norm_value, row_limit, timeout_ms=180),
                limit,
            )

        raw_lower = raw_value.lower()
        if (
            len(merged) < max(2, min(limit, 6))
            and raw_value
            and 3 <= len(raw_value) <= 64
            and raw_lower != norm_value
        ):
            _merge_rows(
                merged,
                _select_entries_contains(conn, module, "snippet", raw_value, row_limit, timeout_ms=180),
                limit,
            )

        return list(merged.values())[:limit]

    compact_min = 2 if cjkish else 4
    norm_min = 2 if cjkish else 4
    raw_min = 2 if cjkish else 4

    if compact_min <= len(compact_value) <= 48:
        _merge_rows(
            merged,
            _select_entries_contains(conn, module, "snippet_compact", compact_value, row_limit, timeout_ms=220),
            limit,
        )

    if len(merged) < limit and norm_min <= len(norm_value) <= 64:
        _merge_rows(
            merged,
            _select_entries_contains(conn, module, "snippet_norm", norm_value, row_limit, timeout_ms=220),
            limit,
        )

    if len(merged) < limit and raw_min <= len(raw_value) <= 64:
        _merge_rows(
            merged,
            _select_entries_contains(conn, module, "snippet", raw_value, row_limit, timeout_ms=220),
            limit,
        )

    if len(merged) < limit and norm_min <= len(norm_value) <= 64:
        _merge_rows(
            merged,
            _select_entries_contains(conn, module, "snippet", norm_value, row_limit, timeout_ms=220),
            limit,
        )

    return list(merged.values())[:limit]


def fetch_fts_content_like(
    conn: sqlite3.Connection,
    module: str,
    raw_query: str,
    query_norm: str,
    query_compact: str,
    limit: int,
) -> List[sqlite3.Row]:
    return fetch_direct_content_entries(
        conn=conn,
        module=module,
        raw_query=raw_query,
        query_norm=query_norm,
        query_compact=query_compact,
        limit=limit,
    )


__all__ = [
    "analyze_search_query",
    "classify_query",
    "is_filenameish",
    "build_title_fts_exprs",
    "build_content_fts_exprs",
    "build_recall_fts_exprs",
    "recall_fts_available",
    "fetch_chat_title_fast",
    "fetch_fts_title",
    "fetch_fts_content",
    "fetch_fts_recall",
    "fetch_filename_fast",
    "fetch_direct_title",
    "fetch_direct_content_entries",
    "fetch_fts_content_like",
]

