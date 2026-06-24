#!/usr/bin/env python3

import argparse
import os
import sqlite3
import time
import traceback
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from tools.search.backfill_recall_metadata import (
    TARGET_SOURCE_KINDS as META_TARGET_SOURCE_KINDS,
    _build_recall_text as _build_meta_recall_text,
)
from tools.search.backfill_recall_content import (
    TARGET_SOURCE_KINDS as CONTENT_TARGET_SOURCE_KINDS,
    _build_recall_text as _build_content_recall_text,
    _is_noise_path as _is_content_noise_path,
    _load_parent_map,
    _parent_for_content,
)
from tools.search.backfill_recall_tier2_fs import (
    DEFAULT_CHUNK_CHARS,
    DEFAULT_CHUNK_OVERLAP,
    DEFAULT_JSON_MAX_INDEXED_TEXT_BYTES,
    DEFAULT_LARGE_FILE_WINDOW_BYTES,
    DEFAULT_LARGE_FILE_WINDOWS,
    DEFAULT_MAX_CHUNKS_PER_FILE,
    DEFAULT_MAX_FILE_SIZE_FULL_READ,
    DEFAULT_MAX_HEADING_CHUNKS_PER_FILE,
    DEFAULT_MAX_HEADING_CONTEXT_CHARS,
    DEFAULT_MAX_HEADING_TOTAL_CHARS_PER_FILE,
    DEFAULT_MAX_CODE_SYMBOLS_PER_CHUNK,
    DEFAULT_MIN_CODE_SYMBOL_LEN,
    DEFAULT_MAX_CODE_TOTAL_CHARS_PER_FILE,
    DEFAULT_MAX_CODE_CONTEXT_CHARS,
    DEFAULT_MAX_CODE_CHUNKS_PER_FILE,
    DEFAULT_MAX_INDEXED_TEXT_BYTES,
    DEFAULT_MAX_RECALL_TEXT_BYTES_PER_ROW,
    DEFAULT_MAX_PATH_RECALL_TEXT_BYTES,
    DEFAULT_MAX_PATH_TERMS_PER_FILE,
    DEFAULT_MAX_LATIN_PARA_CHUNKS_PER_FILE,
    DEFAULT_MAX_LATIN_PARA_CHARS_PER_FILE,
    DEFAULT_MAX_LATIN_PARA_CONTEXT_CHARS,
    DEFAULT_MAX_SECTION_TAIL_CHUNKS_PER_FILE,
    DEFAULT_MAX_SECTION_TAIL_CHARS_PER_FILE,
    DEFAULT_MAX_SECTION_TAIL_CONTEXT_CHARS,
    SOURCE_KINDS_BY_MODULE,
    TEXT_EXTENSIONS,
    _build_docs_for_parent,
    _delete_tier2_for_parents,
    _text,
)
from tools.search.index_store import upsert_recall_docs


DEFAULT_ONLINE_BATCH = 120
DEFAULT_BOOTSTRAP_BATCH = 2000
DEFAULT_BASE_ONLINE_BATCH = 1000
DEFAULT_BASE_BOOTSTRAP_BATCH = 0
DEFAULT_WRITE_BATCH = 200

META_SOURCE_KIND_MODULE = {
    "dirs_dir": "dirs",
    "files_file": "files",
    "doc_file": "doc",
}

CONTENT_SOURCE_KIND_MODULE = {
    "files_content": "files",
    "doc_content": "doc",
    "chat_turn": "chat",
}


def _env_bool(name: str, default: bool = True) -> bool:
    raw = str(os.getenv(name, "")).strip()
    if not raw:
        return bool(default)
    return raw.lower() not in {"0", "false", "no", "off"}


def _env_int(name: str, default: int, min_value: int = 0, max_value: int = 100000) -> int:
    raw = str(os.getenv(name, "")).strip()
    if not raw:
        return int(default)
    try:
        value = int(raw)
    except Exception:
        return int(default)
    return max(min_value, min(max_value, value))


def _normalize_modules(modules: Optional[Sequence[str]]) -> List[str]:
    values = list(modules or ["files", "doc", "dirs", "chat"])
    out: List[str] = []
    for module in values:
        text = str(module or "").strip()
        if text in {"files", "doc", "dirs", "chat"} and text not in out:
            out.append(text)
    return out


def _filter_source_kinds(source_kinds: Sequence[str], modules: Sequence[str], mapping: Dict[str, str]) -> List[str]:
    module_set = set(modules)
    out: List[str] = []
    for source_kind in source_kinds:
        if mapping.get(source_kind) in module_set:
            out.append(source_kind)
    return out


def _chunked(values: Sequence[Any], size: int) -> Iterable[Sequence[Any]]:
    step = max(1, int(size))
    for idx in range(0, len(values), step):
        yield values[idx:idx + step]


def _count_recall_rows(conn: sqlite3.Connection, modules: Sequence[str], tiers: Sequence[int]) -> int:
    if not modules or not tiers:
        return 0
    module_placeholders = ",".join("?" for _ in modules)
    tier_placeholders = ",".join("?" for _ in tiers)
    row = conn.execute(
        f"""
        SELECT COUNT(1)
        FROM search_recall_docs
        WHERE module IN ({module_placeholders})
          AND tier IN ({tier_placeholders})
        """,
        list(modules) + [int(t) for t in tiers],
    ).fetchone()
    return int(row[0] or 0) if row else 0


def _iter_meta_rows(
    conn: sqlite3.Connection,
    source_kinds: Sequence[str],
    limit: int,
    force: bool,
) -> List[sqlite3.Row]:
    if not source_kinds:
        return []
    placeholders = ",".join("?" for _ in source_kinds)
    params: List[Any] = list(source_kinds)
    where = f"e.source_kind IN ({placeholders})"

    if not force:
        where += """
        AND (
          NOT EXISTS (
            SELECT 1
            FROM search_recall_docs d
            WHERE d.parent_item_key = e.item_key
              AND d.tier = 0
              AND d.chunk_index = 0
          )
          OR EXISTS (
            SELECT 1
            FROM search_recall_docs d
            WHERE d.parent_item_key = e.item_key
              AND d.tier = 0
              AND d.chunk_index = 0
              AND COALESCE(d.source_mtime_ns, 0) != COALESCE(e.mtime_ns, 0)
          )
        )
        """

    sql = f"""
    SELECT item_key, module, source_kind, group_key, path, filename, title,
           snippet, mtime_ns, size
    FROM search_entries e
    WHERE {where}
    ORDER BY e.updated_at DESC, e.item_key ASC
    """

    if limit > 0:
        sql += " LIMIT ?"
        params.append(int(limit))

    return conn.execute(sql, params).fetchall()


def _iter_content_rows(
    conn: sqlite3.Connection,
    source_kinds: Sequence[str],
    limit: int,
) -> List[sqlite3.Row]:
    if not source_kinds:
        return []
    placeholders = ",".join("?" for _ in source_kinds)
    params: List[Any] = list(source_kinds)
    sql = f"""
    SELECT item_key, module, source_kind, group_key, path, filename, title,
           snippet, mtime_ns, size
    FROM search_entries
    WHERE source_kind IN ({placeholders})
    ORDER BY updated_at DESC, item_key ASC
    """
    if limit > 0:
        sql += " LIMIT ?"
        params.append(int(limit))
    return conn.execute(sql, params).fetchall()


def ensure_recall_base(
    conn: sqlite3.Connection,
    modules: Optional[Sequence[str]] = None,
    *,
    online: bool = True,
    max_rows: Optional[int] = None,
    force: bool = False,
) -> Dict[str, Any]:
    started = time.time()
    selected_modules = _normalize_modules(modules)
    result: Dict[str, Any] = {
        "ok": False,
        "online": bool(online),
        "force": bool(force),
        "modules": selected_modules,
        "metadata_selected": 0,
        "metadata_upserted": 0,
        "content_selected": 0,
        "content_upserted": 0,
        "skipped_no_parent_key": 0,
        "skipped_parent_missing": 0,
        "skipped_noise_path": 0,
        "skipped_empty_text": 0,
    }

    if online and not _env_bool("NISB_SEARCH_AUTO_RECALL_BASE", True):
        result.update({"ok": True, "skipped_reason": "env_disabled", "elapsed_ms": 0})
        return result

    try:
        existing_base = _count_recall_rows(conn, selected_modules, [0, 1])

        if max_rows is None:
            if online:
                default_limit = DEFAULT_BASE_BOOTSTRAP_BATCH if existing_base <= 0 else DEFAULT_BASE_ONLINE_BATCH
                max_rows = _env_int(
                    "NISB_SEARCH_AUTO_RECALL_BASE_BATCH",
                    default_limit,
                    min_value=0,
                    max_value=50000,
                )
            else:
                max_rows = 0

        meta_source_kinds = _filter_source_kinds(META_TARGET_SOURCE_KINDS, selected_modules, META_SOURCE_KIND_MODULE)
        content_source_kinds = _filter_source_kinds(CONTENT_TARGET_SOURCE_KINDS, selected_modules, CONTENT_SOURCE_KIND_MODULE)

        meta_rows = _iter_meta_rows(conn, meta_source_kinds, int(max_rows or 0), force=bool(force))
        result["metadata_selected"] = len(meta_rows)

        for batch in _chunked(meta_rows, DEFAULT_WRITE_BATCH):
            docs: List[Dict[str, Any]] = []
            for row in batch:
                item = dict(row)
                recall_text = _build_meta_recall_text(item)
                if not recall_text:
                    continue
                docs.append({
                    "parent_item_key": _text(item.get("item_key")),
                    "module": _text(item.get("module")),
                    "source_kind": _text(item.get("source_kind")),
                    "parent_key": _text(item.get("group_key")) or _text(item.get("item_key")),
                    "parent_path": _text(item.get("path")),
                    "title": _text(item.get("title")) or _text(item.get("filename")),
                    "recall_text": recall_text,
                    "tier": 0,
                    "chunk_index": 0,
                    "source_mtime_ns": int(item.get("mtime_ns") or 0),
                    "source_size": int(item.get("size") or 0),
                })
            if docs:
                result["metadata_upserted"] += upsert_recall_docs(conn, docs)
                conn.commit()

        content_rows = _iter_content_rows(conn, content_source_kinds, int(max_rows or 0))
        result["content_selected"] = len(content_rows)

        for batch in _chunked(content_rows, DEFAULT_WRITE_BATCH):
            parsed: List[Tuple[Dict[str, Any], str, int]] = []
            parent_keys: List[str] = []

            for row in batch:
                item = dict(row)
                parent_payload = _parent_for_content(item)
                if not parent_payload:
                    result["skipped_no_parent_key"] += 1
                    continue
                parent_key, chunk_index = parent_payload
                parsed.append((item, parent_key, chunk_index))
                parent_keys.append(parent_key)

            parents = _load_parent_map(conn, parent_keys)
            docs = []

            for item, parent_key, chunk_index in parsed:
                parent = parents.get(parent_key)
                if not parent:
                    result["skipped_parent_missing"] += 1
                    continue

                parent_path = _text(parent.get("path")) or _text(item.get("path"))
                if _is_content_noise_path(parent_path):
                    result["skipped_noise_path"] += 1
                    continue

                recall_text = _build_content_recall_text(item, parent)
                if not recall_text:
                    result["skipped_empty_text"] += 1
                    continue

                docs.append({
                    "parent_item_key": parent_key,
                    "module": _text(parent.get("module")) or _text(item.get("module")),
                    "source_kind": _text(item.get("source_kind")),
                    "parent_key": _text(parent.get("group_key")) or parent_key,
                    "parent_path": parent_path,
                    "title": _text(parent.get("title")) or _text(item.get("title")),
                    "recall_text": recall_text,
                    "tier": 1,
                    "chunk_index": int(chunk_index),
                    "source_mtime_ns": int(item.get("mtime_ns") or parent.get("mtime_ns") or 0),
                    "source_size": int(item.get("size") or parent.get("size") or 0),
                })

            if docs:
                result["content_upserted"] += upsert_recall_docs(conn, docs)
                conn.commit()

        result["ok"] = True
        result["elapsed_ms"] = int((time.time() - started) * 1000)
        return result

    except Exception as exc:
        try:
            conn.rollback()
        except Exception:
            pass
        result["ok"] = False
        result["error"] = repr(exc)
        result["traceback"] = traceback.format_exc()
        result["elapsed_ms"] = int((time.time() - started) * 1000)
        return result


def _like_ext_conditions(column_expr: str) -> Tuple[str, List[str]]:
    parts: List[str] = []
    params: List[str] = []
    for ext in sorted(TEXT_EXTENSIONS):
        parts.append(f"{column_expr} LIKE ?")
        params.append(f"%{ext.lower()}")
    if not parts:
        return "1=0", []
    return "(" + " OR ".join(parts) + ")", params


def _noise_sql(column_expr: str) -> str:
    return f"""
      AND {column_expr} NOT LIKE 'agent_files/.trash/%'
      AND {column_expr} NOT LIKE '%/.trash/%'
      AND {column_expr} NOT LIKE 'agent_files/.history/%'
      AND {column_expr} NOT LIKE '%/.history/%'
      AND {column_expr} NOT LIKE '%/node_modules/%'
      AND {column_expr} NOT LIKE '%/.git/%'
      AND {column_expr} NOT LIKE '%/__pycache__/%'
    """


def _count_tier2_rows(conn: sqlite3.Connection, modules: Sequence[str]) -> int:
    if not modules:
        return 0
    placeholders = ",".join("?" for _ in modules)
    row = conn.execute(
        f"""
        SELECT COUNT(1)
        FROM search_recall_docs
        WHERE tier = 2
          AND module IN ({placeholders})
        """,
        list(modules),
    ).fetchone()
    return int(row[0] or 0) if row else 0


def _select_candidate_rows(
    conn: sqlite3.Connection,
    modules: Sequence[str],
    limit: int,
    force: bool,
) -> List[sqlite3.Row]:
    rows: List[sqlite3.Row] = []
    remaining = int(limit)

    for module in modules:
        source_kind = SOURCE_KINDS_BY_MODULE.get(module)
        if not source_kind:
            continue

        path_expr = "lower(COALESCE(e.path, e.filename, e.title, ''))"
        ext_sql, ext_params = _like_ext_conditions(path_expr)

        where = f"""
        e.module = ?
        AND e.source_kind = ?
        AND {ext_sql}
        {_noise_sql(path_expr)}
        """

        params: List[Any] = [module, source_kind] + ext_params

        if not force:
            where += """
            AND (
              NOT EXISTS (
                SELECT 1
                FROM search_recall_docs d
                WHERE d.parent_item_key = e.item_key
                  AND d.tier = 2
              )
              OR EXISTS (
                SELECT 1
                FROM search_recall_docs d
                WHERE d.parent_item_key = e.item_key
                  AND d.tier = 2
                  AND COALESCE(d.source_mtime_ns, 0) != COALESCE(e.mtime_ns, 0)
              )
            )
            """

        sql = f"""
        SELECT e.*
        FROM search_entries e
        WHERE {where}
        ORDER BY e.updated_at DESC, e.item_key ASC
        """

        if remaining > 0:
            sql += " LIMIT ?"
            params.append(remaining)

        part = conn.execute(sql, params).fetchall()
        rows.extend(part)

        if remaining > 0:
            remaining -= len(part)
            if remaining <= 0:
                break

    return rows


def _default_args() -> argparse.Namespace:
    return argparse.Namespace(
        max_indexed_text_bytes_per_file=DEFAULT_MAX_INDEXED_TEXT_BYTES,
        json_max_indexed_text_bytes=DEFAULT_JSON_MAX_INDEXED_TEXT_BYTES,
        max_chunks_per_file=DEFAULT_MAX_CHUNKS_PER_FILE,
        chunk_chars=DEFAULT_CHUNK_CHARS,
        chunk_overlap=DEFAULT_CHUNK_OVERLAP,
        max_file_size_full_read=DEFAULT_MAX_FILE_SIZE_FULL_READ,
        large_file_windows=DEFAULT_LARGE_FILE_WINDOWS,
        large_file_window_bytes=DEFAULT_LARGE_FILE_WINDOW_BYTES,
        max_recall_text_bytes_per_row=DEFAULT_MAX_RECALL_TEXT_BYTES_PER_ROW,
        max_heading_chunks_per_file=DEFAULT_MAX_HEADING_CHUNKS_PER_FILE,
        max_heading_context_chars=DEFAULT_MAX_HEADING_CONTEXT_CHARS,
        max_heading_total_chars_per_file=DEFAULT_MAX_HEADING_TOTAL_CHARS_PER_FILE,
        max_code_chunks_per_file=DEFAULT_MAX_CODE_CHUNKS_PER_FILE,
        max_code_context_chars=DEFAULT_MAX_CODE_CONTEXT_CHARS,
        max_code_total_chars_per_file=DEFAULT_MAX_CODE_TOTAL_CHARS_PER_FILE,
        min_code_symbol_len=DEFAULT_MIN_CODE_SYMBOL_LEN,
        max_code_symbols_per_chunk=DEFAULT_MAX_CODE_SYMBOLS_PER_CHUNK,
        max_path_terms_per_file=DEFAULT_MAX_PATH_TERMS_PER_FILE,
        max_path_recall_text_bytes=DEFAULT_MAX_PATH_RECALL_TEXT_BYTES,
        max_latin_para_chunks_per_file=DEFAULT_MAX_LATIN_PARA_CHUNKS_PER_FILE,
        max_latin_para_total_chars_per_file=DEFAULT_MAX_LATIN_PARA_CHARS_PER_FILE,
        max_latin_para_context_chars=DEFAULT_MAX_LATIN_PARA_CONTEXT_CHARS,
        max_section_tail_chunks_per_file=DEFAULT_MAX_SECTION_TAIL_CHUNKS_PER_FILE,
        max_section_tail_total_chars_per_file=DEFAULT_MAX_SECTION_TAIL_CHARS_PER_FILE,
        max_section_tail_context_chars=DEFAULT_MAX_SECTION_TAIL_CONTEXT_CHARS,
    )


def ensure_recall_tier2_fs(
    conn: sqlite3.Connection,
    base_path: Path,
    modules: Optional[Sequence[str]] = None,
    *,
    online: bool = True,
    max_parents: Optional[int] = None,
    force: bool = False,
) -> Dict[str, Any]:
    started = time.time()
    selected_modules = _normalize_modules(modules)
    tier2_modules = [m for m in selected_modules if m in SOURCE_KINDS_BY_MODULE]

    result: Dict[str, Any] = {
        "ok": False,
        "online": bool(online),
        "force": bool(force),
        "modules": selected_modules,
        "tier2_modules": tier2_modules,
        "base_recall": {},
        "selected_parents": 0,
        "processed_parents": 0,
        "indexed_parents": 0,
        "deleted_existing_tier2": 0,
        "upserted": 0,
        "tier2_recall_rows": 0,
        "heading_recall_rows": 0,
        "code_recall_rows": 0,
        "path_recall_rows": 0,
        "latin_para_recall_rows": 0,
        "section_tail_recall_rows": 0,
        "skipped": {},
    }

    if online and not _env_bool("NISB_SEARCH_AUTO_RECALL_TIER2", True):
        result["base_recall"] = ensure_recall_base(conn, selected_modules, online=online, force=force)
        result.update({"ok": True, "skipped_reason": "env_disabled", "elapsed_ms": int((time.time() - started) * 1000)})
        return result

    base_force = bool(force)
    base_max_rows = 0 if (not online or force) else None
    result["base_recall"] = ensure_recall_base(
        conn,
        selected_modules,
        online=online,
        max_rows=base_max_rows,
        force=base_force,
    )

    base_path = Path(str(base_path))

    if not tier2_modules:
        result.update({"ok": True, "elapsed_ms": int((time.time() - started) * 1000)})
        return result

    try:
        existing_tier2 = _count_tier2_rows(conn, tier2_modules)

        if max_parents is None:
            if online:
                default_limit = DEFAULT_BOOTSTRAP_BATCH if existing_tier2 <= 0 else DEFAULT_ONLINE_BATCH
                max_parents = _env_int(
                    "NISB_SEARCH_AUTO_RECALL_BATCH",
                    default_limit,
                    min_value=1,
                    max_value=5000,
                )
            else:
                max_parents = 0

        rows = _select_candidate_rows(
            conn,
            tier2_modules,
            limit=int(max_parents or 0),
            force=bool(force),
        )
        result["selected_parents"] = len(rows)

        if not rows:
            result.update({"ok": True, "elapsed_ms": int((time.time() - started) * 1000)})
            return result

        args = _default_args()
        skipped: Dict[str, int] = {}

        for batch in _chunked(rows, DEFAULT_WRITE_BATCH):
            batch_parent_keys = [_text(row["item_key"]) for row in batch if _text(row["item_key"])]
            batch_docs: List[Dict[str, Any]] = []

            for row in batch:
                result["processed_parents"] += 1
                docs, meta = _build_docs_for_parent(dict(row), base_path, args)

                if meta.get("skip_reason"):
                    reason = str(meta.get("skip_reason") or "unknown")
                    skipped[reason] = skipped.get(reason, 0) + 1

                if docs:
                    batch_docs.extend(docs)
                    result["indexed_parents"] += 1
                    result["tier2_recall_rows"] += len(docs)
                    result["heading_recall_rows"] += int(meta.get("heading_chunks") or 0)
                    result["code_recall_rows"] += int(meta.get("code_chunks") or 0)
                    result["path_recall_rows"] += int(meta.get("path_chunks") or 0)
                    result["latin_para_recall_rows"] += int(meta.get("latin_para_chunks") or 0)
                    result["section_tail_recall_rows"] += int(meta.get("section_tail_chunks") or 0)

            if batch_parent_keys:
                result["deleted_existing_tier2"] += _delete_tier2_for_parents(conn, batch_parent_keys)

            if batch_docs:
                result["upserted"] += upsert_recall_docs(conn, batch_docs)

            conn.commit()

        result["skipped"] = skipped
        result["ok"] = True
        result["elapsed_ms"] = int((time.time() - started) * 1000)
        return result

    except Exception as exc:
        try:
            conn.rollback()
        except Exception:
            pass
        result["ok"] = False
        result["error"] = repr(exc)
        result["traceback"] = traceback.format_exc()
        result["elapsed_ms"] = int((time.time() - started) * 1000)
        return result
