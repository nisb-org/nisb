#!/usr/bin/env python3

import sqlite3
from typing import Any, Dict, List, Tuple

from .common import compact_text, normalize_text, now_ts
from .index_db import trigram_available


def load_existing_map(conn: sqlite3.Connection, module: str) -> Dict[str, Tuple[int, int]]:
    rows = conn.execute(
        "SELECT item_key, mtime_ns, size FROM search_entries WHERE module = ?",
        (module,),
    ).fetchall()
    out: Dict[str, Tuple[int, int]] = {}
    for row in rows:
        out[str(row["item_key"])] = (int(row["mtime_ns"] or 0), int(row["size"] or 0))
    return out


def delete_trigram_keys(conn: sqlite3.Connection, keys: List[str]) -> None:
    if not keys or not trigram_available(conn):
        return
    conn.executemany(
        "DELETE FROM search_entries_tri WHERE item_key = ?",
        [(k,) for k in keys],
    )


def delete_stale(
    conn: sqlite3.Connection,
    module: str,
    current_keys: set,
    existing_map: Dict[str, Tuple[int, int]],
) -> int:
    stale = [k for k in existing_map.keys() if k not in current_keys]
    if not stale:
        return 0
    conn.executemany("DELETE FROM search_entries WHERE item_key = ?", [(k,) for k in stale])
    delete_trigram_keys(conn, stale)
    return len(stale)


def _as_text(value: Any) -> str:
    return str(value or "")


def prepare_entry(entry: Dict[str, Any]) -> Dict[str, Any]:
    item_key = _as_text(entry.get("item_key"))
    module = _as_text(entry.get("module"))
    source_kind = _as_text(entry.get("source_kind"))
    group_key = _as_text(entry.get("group_key"))
    path = _as_text(entry.get("path"))
    filename = _as_text(entry.get("filename"))
    title = _as_text(entry.get("title"))
    library_id = _as_text(entry.get("library_id"))
    library_name = _as_text(entry.get("library_name"))
    doc_id = _as_text(entry.get("doc_id"))
    conv_id = _as_text(entry.get("conv_id"))
    created_at = _as_text(entry.get("created_at"))
    snippet = _as_text(entry.get("snippet"))

    if not title and filename:
        title = filename

    if not group_key:
        if path:
            group_key = path
        elif conv_id:
            group_key = conv_id
        elif item_key:
            group_key = item_key

    prepared = dict(entry)
    prepared["item_key"] = item_key
    prepared["module"] = module
    prepared["source_kind"] = source_kind
    prepared["group_key"] = group_key
    prepared["path"] = path
    prepared["filename"] = filename
    prepared["title"] = title
    prepared["library_id"] = library_id
    prepared["library_name"] = library_name
    prepared["doc_id"] = doc_id
    prepared["conv_id"] = conv_id
    prepared["created_at"] = created_at
    prepared["snippet"] = snippet
    prepared["turn_count"] = int(prepared.get("turn_count", 0) or 0)
    prepared["priority_hint"] = int(prepared.get("priority_hint", 0) or 0)
    prepared["mtime_ns"] = int(prepared.get("mtime_ns", 0) or 0)
    prepared["size"] = int(prepared.get("size", 0) or 0)

    prepared["filename_norm"] = normalize_text(filename)
    prepared["title_norm"] = normalize_text(title)
    prepared["library_name_norm"] = normalize_text(library_name)
    prepared["path_norm"] = normalize_text(path)
    prepared["snippet_norm"] = normalize_text(snippet)

    prepared["filename_compact"] = compact_text(filename)
    prepared["title_compact"] = compact_text(title)
    prepared["library_name_compact"] = compact_text(library_name)
    prepared["path_compact"] = compact_text(path)
    prepared["snippet_compact"] = compact_text(snippet)

    prepared["updated_at"] = int(now_ts())
    return prepared


def sync_trigram_entries(conn: sqlite3.Connection, entries: List[Dict[str, Any]]) -> None:
    if not entries or not trigram_available(conn):
        return

    keys = [str(e.get("item_key", "")) for e in entries if str(e.get("item_key", ""))]
    if keys:
        conn.executemany(
            "DELETE FROM search_entries_tri WHERE item_key = ?",
            [(k,) for k in keys],
        )

    rows = []
    for e in entries:
        rows.append(
            (
                str(e.get("item_key", "") or ""),
                str(e.get("module", "") or ""),
                str(e.get("filename", "") or ""),
                str(e.get("title", "") or ""),
                str(e.get("library_name", "") or ""),
                str(e.get("path", "") or ""),
                str(e.get("snippet", "") or ""),
            )
        )

    conn.executemany(
        """
        INSERT INTO search_entries_tri(
            item_key, module, filename, title, library_name, path, snippet
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        rows,
    )


def upsert_entries(conn: sqlite3.Connection, entries: List[Dict[str, Any]]) -> int:
    if not entries:
        return 0

    prepared: List[Dict[str, Any]] = []
    rows = []

    for entry in entries:
        e = prepare_entry(entry)
        prepared.append(e)
        rows.append(
            (
                e["item_key"],
                e["module"],
                e["source_kind"],
                e["group_key"],
                e["path"],
                e["filename"],
                e["title"],
                e["library_id"],
                e["library_name"],
                e["doc_id"],
                e["conv_id"],
                e["created_at"],
                int(e["turn_count"]),
                e["snippet"],
                int(e["priority_hint"]),
                e["filename_norm"],
                e["title_norm"],
                e["library_name_norm"],
                e["path_norm"],
                e["snippet_norm"],
                e["filename_compact"],
                e["title_compact"],
                e["library_name_compact"],
                e["path_compact"],
                e["snippet_compact"],
                int(e["mtime_ns"]),
                int(e["size"]),
                int(e["updated_at"]),
            )
        )

    conn.executemany(
        """
        INSERT INTO search_entries(
            item_key, module, source_kind, group_key, path, filename, title,
            library_id, library_name, doc_id, conv_id, created_at, turn_count,
            snippet, priority_hint,
            filename_norm, title_norm, library_name_norm, path_norm, snippet_norm,
            filename_compact, title_compact, library_name_compact, path_compact, snippet_compact,
            mtime_ns, size, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(item_key) DO UPDATE SET
            module = excluded.module,
            source_kind = excluded.source_kind,
            group_key = excluded.group_key,
            path = excluded.path,
            filename = excluded.filename,
            title = excluded.title,
            library_id = excluded.library_id,
            library_name = excluded.library_name,
            doc_id = excluded.doc_id,
            conv_id = excluded.conv_id,
            created_at = excluded.created_at,
            turn_count = excluded.turn_count,
            snippet = excluded.snippet,
            priority_hint = excluded.priority_hint,
            filename_norm = excluded.filename_norm,
            title_norm = excluded.title_norm,
            library_name_norm = excluded.library_name_norm,
            path_norm = excluded.path_norm,
            snippet_norm = excluded.snippet_norm,
            filename_compact = excluded.filename_compact,
            title_compact = excluded.title_compact,
            library_name_compact = excluded.library_name_compact,
            path_compact = excluded.path_compact,
            snippet_compact = excluded.snippet_compact,
            mtime_ns = excluded.mtime_ns,
            size = excluded.size,
            updated_at = excluded.updated_at
        """,
        rows,
    )

    sync_trigram_entries(conn, prepared)
    return len(rows)


def recall_tables_available(conn: sqlite3.Connection) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type IN ('table', 'view') AND name = ? LIMIT 1",
        ("search_recall_docs",),
    ).fetchone()
    return bool(row)


def delete_recall_docs_for_parent(conn: sqlite3.Connection, parent_item_keys: List[str]) -> int:
    keys = list(dict.fromkeys([str(k) for k in parent_item_keys if str(k)]))
    if not keys or not recall_tables_available(conn):
        return 0

    placeholders = ",".join(["?"] * len(keys))
    before = conn.execute(
        f"SELECT COUNT(1) FROM search_recall_docs WHERE parent_item_key IN ({placeholders})",
        keys,
    ).fetchone()[0]

    conn.execute(
        f"DELETE FROM search_recall_docs WHERE parent_item_key IN ({placeholders})",
        keys,
    )

    return int(before or 0)


def prepare_recall_doc(doc: Dict[str, Any]) -> Dict[str, Any]:
    prepared = dict(doc)
    prepared["parent_item_key"] = _as_text(doc.get("parent_item_key"))
    prepared["module"] = _as_text(doc.get("module"))
    prepared["source_kind"] = _as_text(doc.get("source_kind"))
    prepared["parent_key"] = _as_text(doc.get("parent_key")) or prepared["parent_item_key"]
    prepared["parent_path"] = _as_text(doc.get("parent_path"))
    prepared["title"] = _as_text(doc.get("title"))
    prepared["recall_text"] = _as_text(doc.get("recall_text")).strip()
    prepared["tier"] = int(doc.get("tier", 0) or 0)
    prepared["chunk_index"] = int(doc.get("chunk_index", 0) or 0)
    prepared["source_mtime_ns"] = int(doc.get("source_mtime_ns", 0) or 0)
    prepared["source_size"] = int(doc.get("source_size", 0) or 0)
    prepared["indexed_at"] = int(now_ts())
    return prepared


def upsert_recall_docs(conn: sqlite3.Connection, docs: List[Dict[str, Any]]) -> int:
    if not docs or not recall_tables_available(conn):
        return 0

    rows = []
    for doc in docs:
        d = prepare_recall_doc(doc)
        if not d["parent_item_key"] or not d["module"] or not d["recall_text"]:
            continue
        rows.append(
            (
                d["parent_item_key"],
                d["module"],
                d["source_kind"],
                d["parent_key"],
                d["parent_path"],
                d["title"],
                d["recall_text"],
                int(d["tier"]),
                int(d["chunk_index"]),
                int(d["source_mtime_ns"]),
                int(d["source_size"]),
                int(d["indexed_at"]),
            )
        )

    if not rows:
        return 0

    conn.executemany(
        """
        INSERT INTO search_recall_docs(
            parent_item_key, module, source_kind, parent_key, parent_path, title,
            recall_text, tier, chunk_index, source_mtime_ns, source_size, indexed_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(parent_item_key, tier, chunk_index) DO UPDATE SET
            module = excluded.module,
            source_kind = excluded.source_kind,
            parent_key = excluded.parent_key,
            parent_path = excluded.parent_path,
            title = excluded.title,
            recall_text = excluded.recall_text,
            source_mtime_ns = excluded.source_mtime_ns,
            source_size = excluded.source_size,
            indexed_at = excluded.indexed_at
        """,
        rows,
    )
    return len(rows)


def count_recall_docs(conn: sqlite3.Connection) -> Dict[str, int]:
    if not recall_tables_available(conn):
        return {}

    rows = conn.execute(
        """
        SELECT module, COUNT(1) AS n
        FROM search_recall_docs
        GROUP BY module
        ORDER BY module
        """
    ).fetchall()

    out: Dict[str, int] = {"total": 0}
    for row in rows:
        module = str(row["module"])
        count = int(row["n"] or 0)
        out[module] = count
        out["total"] += count
    return out


__all__ = [
    "load_existing_map",
    "delete_trigram_keys",
    "delete_stale",
    "prepare_entry",
    "sync_trigram_entries",
    "upsert_entries",
    "recall_tables_available",
    "delete_recall_docs_for_parent",
    "prepare_recall_doc",
    "upsert_recall_docs",
    "count_recall_docs",
]

