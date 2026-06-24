#!/usr/bin/env python3

import sqlite3
import time
from pathlib import Path
from typing import Any, Optional, Tuple

from .common import INDEX_DB_NAME, INDEX_DIRNAME
from .index_shared import SCHEMA_VERSION


FTS_LAYOUT_VERSION = "title_content_v2_path"
FTS_CHECK_THROTTLE_SECONDS = 120
OPTIMIZE_THROTTLE_SECONDS = 21600


def get_index_db_path(base_path: Path) -> Path:
    cache_dir = base_path / INDEX_DIRNAME
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir / INDEX_DB_NAME


def _apply_pragmas(conn: sqlite3.Connection) -> None:
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.execute("PRAGMA temp_store=MEMORY;")
    conn.execute("PRAGMA cache_size=-8192;")
    conn.execute("PRAGMA mmap_size=67108864;")
    conn.execute("PRAGMA busy_timeout=10000;")


def table_exists(conn: sqlite3.Connection, name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type IN ('table', 'view') AND name = ? LIMIT 1",
        (name,),
    ).fetchone()
    return bool(row)


def ensure_meta_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS search_meta (
            k TEXT PRIMARY KEY,
            v TEXT
        )
        """
    )
    conn.commit()


def meta_get(conn: sqlite3.Connection, key: str) -> Optional[str]:
    if not table_exists(conn, "search_meta"):
        return None
    row = conn.execute("SELECT v FROM search_meta WHERE k = ?", (key,)).fetchone()
    if not row:
        return None
    return str(row["v"])


def meta_get_float(conn: sqlite3.Connection, key: str) -> Optional[float]:
    raw = meta_get(conn, key)
    if raw is None:
        return None
    try:
        return float(raw)
    except Exception:
        return None


def meta_set(conn: sqlite3.Connection, key: str, value: Any) -> None:
    conn.execute(
        """
        INSERT INTO search_meta(k, v) VALUES(?, ?)
        ON CONFLICT(k) DO UPDATE SET v = excluded.v
        """,
        (key, str(value)),
    )


def schema_ready(conn: sqlite3.Connection) -> bool:
    return (
        table_exists(conn, "search_meta")
        and table_exists(conn, "search_entries")
        and table_exists(conn, "search_fts_title")
        and table_exists(conn, "search_fts_content")
    )


def drop_search_structures(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        DROP TRIGGER IF EXISTS srd_ai;
        DROP TRIGGER IF EXISTS srd_ad;
        DROP TRIGGER IF EXISTS srd_au;
        DROP TRIGGER IF EXISTS se_ai;
        DROP TRIGGER IF EXISTS se_ad;
        DROP TRIGGER IF EXISTS se_au;

        DROP TABLE IF EXISTS search_fts_recall;
        DROP TABLE IF EXISTS search_recall_docs;
        DROP TABLE IF EXISTS search_entries_tri;
        DROP TABLE IF EXISTS search_fts_title;
        DROP TABLE IF EXISTS search_fts_content;
        DROP TABLE IF EXISTS search_entries;

        DELETE FROM search_meta WHERE k LIKE 'sync:%';
        DELETE FROM search_meta WHERE k LIKE 'count:%';
        DELETE FROM search_meta WHERE k LIKE 'quick_sync:%';
        DELETE FROM search_meta WHERE k = 'fts_layout_version';
        DELETE FROM search_meta WHERE k = 'fts_title_rowcount';
        DELETE FROM search_meta WHERE k = 'fts_content_rowcount';
        DELETE FROM search_meta WHERE k = 'fts_checked_at';
        DELETE FROM search_meta WHERE k = 'optimize_checked_at';
        """
    )
    conn.commit()


def _normalize_existing_text_columns(conn: sqlite3.Connection) -> None:
    if not table_exists(conn, "search_entries"):
        return

    conn.execute(
        """
        UPDATE search_entries
        SET
            group_key = COALESCE(group_key, ''),
            path = COALESCE(path, ''),
            filename = COALESCE(filename, ''),
            title = COALESCE(title, ''),
            library_id = COALESCE(library_id, ''),
            library_name = COALESCE(library_name, ''),
            doc_id = COALESCE(doc_id, ''),
            conv_id = COALESCE(conv_id, ''),
            created_at = COALESCE(created_at, ''),
            snippet = COALESCE(snippet, ''),
            filename_norm = COALESCE(filename_norm, ''),
            title_norm = COALESCE(title_norm, ''),
            library_name_norm = COALESCE(library_name_norm, ''),
            path_norm = COALESCE(path_norm, ''),
            snippet_norm = COALESCE(snippet_norm, ''),
            filename_compact = COALESCE(filename_compact, ''),
            title_compact = COALESCE(title_compact, ''),
            library_name_compact = COALESCE(library_name_compact, ''),
            path_compact = COALESCE(path_compact, ''),
            snippet_compact = COALESCE(snippet_compact, '')
        WHERE
            group_key IS NULL
            OR path IS NULL
            OR filename IS NULL
            OR title IS NULL
            OR library_id IS NULL
            OR library_name IS NULL
            OR doc_id IS NULL
            OR conv_id IS NULL
            OR created_at IS NULL
            OR snippet IS NULL
            OR filename_norm IS NULL
            OR title_norm IS NULL
            OR library_name_norm IS NULL
            OR path_norm IS NULL
            OR snippet_norm IS NULL
            OR filename_compact IS NULL
            OR title_compact IS NULL
            OR library_name_compact IS NULL
            OR path_compact IS NULL
            OR snippet_compact IS NULL
        """
    )


def _maybe_optimize(conn: sqlite3.Connection, force: bool = False) -> None:
    ensure_meta_table(conn)

    last = meta_get_float(conn, "optimize_checked_at")
    now_ts = time.time()

    if (not force) and last is not None and (now_ts - last) < float(OPTIMIZE_THROTTLE_SECONDS):
        return

    try:
        conn.execute("PRAGMA optimize;")
    except Exception:
        pass

    meta_set(conn, "optimize_checked_at", now_ts)
    conn.commit()


def create_recall_structures(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS search_recall_docs (
            recall_id INTEGER PRIMARY KEY,
            parent_item_key TEXT NOT NULL,
            module TEXT NOT NULL,
            source_kind TEXT NOT NULL,
            parent_key TEXT NOT NULL,
            parent_path TEXT NOT NULL DEFAULT '',
            title TEXT NOT NULL DEFAULT '',
            recall_text TEXT NOT NULL,
            tier INTEGER NOT NULL DEFAULT 0,
            chunk_index INTEGER NOT NULL DEFAULT 0,
            source_mtime_ns INTEGER NOT NULL DEFAULT 0,
            source_size INTEGER NOT NULL DEFAULT 0,
            indexed_at REAL NOT NULL
        );

        CREATE UNIQUE INDEX IF NOT EXISTS idx_search_recall_docs_parent_chunk
            ON search_recall_docs(parent_item_key, tier, chunk_index);

        CREATE INDEX IF NOT EXISTS idx_search_recall_docs_parent
            ON search_recall_docs(parent_item_key);

        CREATE INDEX IF NOT EXISTS idx_search_recall_docs_module_parent
            ON search_recall_docs(module, parent_key);

        CREATE INDEX IF NOT EXISTS idx_search_recall_docs_module_tier
            ON search_recall_docs(module, tier);
        """
    )

    conn.execute(
        """
        CREATE VIRTUAL TABLE IF NOT EXISTS search_fts_recall USING fts5(
            module UNINDEXED,
            source_kind UNINDEXED,
            recall_text,
            content='search_recall_docs',
            content_rowid='recall_id',
            tokenize='unicode61 remove_diacritics 1',
            prefix='2 3 4'
        );
        """
    )

    conn.executescript(
        """
        CREATE TRIGGER IF NOT EXISTS srd_ai AFTER INSERT ON search_recall_docs BEGIN
            INSERT INTO search_fts_recall(rowid, module, source_kind, recall_text)
            VALUES (new.recall_id, new.module, new.source_kind, new.recall_text);
        END;

        CREATE TRIGGER IF NOT EXISTS srd_ad AFTER DELETE ON search_recall_docs BEGIN
            INSERT INTO search_fts_recall(search_fts_recall, rowid, module, source_kind, recall_text)
            VALUES ('delete', old.recall_id, old.module, old.source_kind, old.recall_text);
        END;

        CREATE TRIGGER IF NOT EXISTS srd_au AFTER UPDATE ON search_recall_docs BEGIN
            INSERT INTO search_fts_recall(search_fts_recall, rowid, module, source_kind, recall_text)
            VALUES ('delete', old.recall_id, old.module, old.source_kind, old.recall_text);

            INSERT INTO search_fts_recall(rowid, module, source_kind, recall_text)
            VALUES (new.recall_id, new.module, new.source_kind, new.recall_text);
        END;
        """
    )

    conn.commit()


def create_structures(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS search_entries (
            item_key TEXT PRIMARY KEY,
            module TEXT NOT NULL,
            source_kind TEXT NOT NULL,
            group_key TEXT,
            path TEXT,
            filename TEXT,
            title TEXT,
            library_id TEXT,
            library_name TEXT,
            doc_id TEXT,
            conv_id TEXT,
            created_at TEXT,
            turn_count INTEGER DEFAULT 0,
            snippet TEXT,
            priority_hint INTEGER DEFAULT 0,
            filename_norm TEXT,
            title_norm TEXT,
            library_name_norm TEXT,
            path_norm TEXT,
            snippet_norm TEXT,
            filename_compact TEXT,
            title_compact TEXT,
            library_name_compact TEXT,
            path_compact TEXT,
            snippet_compact TEXT,
            mtime_ns INTEGER DEFAULT 0,
            size INTEGER DEFAULT 0,
            updated_at INTEGER DEFAULT 0
        );

        CREATE INDEX IF NOT EXISTS idx_search_entries_module ON search_entries(module);
        CREATE INDEX IF NOT EXISTS idx_search_entries_updated_at ON search_entries(updated_at);
        CREATE INDEX IF NOT EXISTS idx_search_entries_library_id ON search_entries(library_id);
        CREATE INDEX IF NOT EXISTS idx_search_entries_conv_id ON search_entries(conv_id);
        CREATE INDEX IF NOT EXISTS idx_search_entries_group_key ON search_entries(group_key);
        CREATE INDEX IF NOT EXISTS idx_search_entries_module_priority_updated
            ON search_entries(module, priority_hint DESC, updated_at DESC);

        CREATE INDEX IF NOT EXISTS idx_search_entries_module_filename
            ON search_entries(module, filename);
        CREATE INDEX IF NOT EXISTS idx_search_entries_module_title
            ON search_entries(module, title);
        CREATE INDEX IF NOT EXISTS idx_search_entries_module_library_name
            ON search_entries(module, library_name);
        CREATE INDEX IF NOT EXISTS idx_search_entries_module_path
            ON search_entries(module, path);

        CREATE INDEX IF NOT EXISTS idx_search_entries_module_filename_norm
            ON search_entries(module, filename_norm);
        CREATE INDEX IF NOT EXISTS idx_search_entries_module_title_norm
            ON search_entries(module, title_norm);
        CREATE INDEX IF NOT EXISTS idx_search_entries_module_library_name_norm
            ON search_entries(module, library_name_norm);
        CREATE INDEX IF NOT EXISTS idx_search_entries_module_path_norm
            ON search_entries(module, path_norm);
        CREATE INDEX IF NOT EXISTS idx_search_entries_module_snippet_norm
            ON search_entries(module, snippet_norm);

        CREATE INDEX IF NOT EXISTS idx_search_entries_module_filename_compact
            ON search_entries(module, filename_compact);
        CREATE INDEX IF NOT EXISTS idx_search_entries_module_title_compact
            ON search_entries(module, title_compact);
        CREATE INDEX IF NOT EXISTS idx_search_entries_module_library_name_compact
            ON search_entries(module, library_name_compact);
        CREATE INDEX IF NOT EXISTS idx_search_entries_module_path_compact
            ON search_entries(module, path_compact);
        CREATE INDEX IF NOT EXISTS idx_search_entries_module_snippet_compact
            ON search_entries(module, snippet_compact);
        """
    )

    try:
        conn.execute(
            """
            CREATE VIRTUAL TABLE IF NOT EXISTS search_entries_tri USING fts5(
                item_key UNINDEXED,
                module UNINDEXED,
                filename,
                title,
                library_name,
                path,
                snippet,
                tokenize='trigram'
            );
            """
        )
    except Exception:
        pass

    conn.execute(
        """
        CREATE VIRTUAL TABLE IF NOT EXISTS search_fts_title USING fts5(
            module UNINDEXED,
            source_kind UNINDEXED,
            title,
            filename,
            library_name,
            path,
            content='search_entries',
            content_rowid='rowid',
            tokenize='unicode61 remove_diacritics 1',
            prefix='2 3 4'
        );
        """
    )

    conn.execute(
        """
        CREATE VIRTUAL TABLE IF NOT EXISTS search_fts_content USING fts5(
            module UNINDEXED,
            source_kind UNINDEXED,
            snippet,
            content='search_entries',
            content_rowid='rowid',
            tokenize='trigram'
        );
        """
    )

    conn.executescript(
        """
        CREATE TRIGGER IF NOT EXISTS se_ai AFTER INSERT ON search_entries BEGIN
            INSERT INTO search_fts_title(rowid, module, source_kind, title, filename, library_name, path)
            VALUES (new.rowid, new.module, new.source_kind, new.title, new.filename, new.library_name, new.path);

            INSERT INTO search_fts_content(rowid, module, source_kind, snippet)
            VALUES (new.rowid, new.module, new.source_kind, new.snippet);
        END;

        CREATE TRIGGER IF NOT EXISTS se_ad AFTER DELETE ON search_entries BEGIN
            INSERT INTO search_fts_title(search_fts_title, rowid, module, source_kind, title, filename, library_name, path)
            VALUES ('delete', old.rowid, old.module, old.source_kind, old.title, old.filename, old.library_name, old.path);

            INSERT INTO search_fts_content(search_fts_content, rowid, module, source_kind, snippet)
            VALUES ('delete', old.rowid, old.module, old.source_kind, old.snippet);
        END;

        CREATE TRIGGER IF NOT EXISTS se_au AFTER UPDATE ON search_entries BEGIN
            INSERT INTO search_fts_title(search_fts_title, rowid, module, source_kind, title, filename, library_name, path)
            VALUES ('delete', old.rowid, old.module, old.source_kind, old.title, old.filename, old.library_name, old.path);

            INSERT INTO search_fts_title(rowid, module, source_kind, title, filename, library_name, path)
            VALUES (new.rowid, new.module, new.source_kind, new.title, new.filename, new.library_name, new.path);

            INSERT INTO search_fts_content(search_fts_content, rowid, module, source_kind, snippet)
            VALUES ('delete', old.rowid, old.module, old.source_kind, old.snippet);

            INSERT INTO search_fts_content(rowid, module, source_kind, snippet)
            VALUES (new.rowid, new.module, new.source_kind, new.snippet);
        END;
        """
    )

    _normalize_existing_text_columns(conn)
    conn.commit()


def ensure_schema(conn: sqlite3.Connection) -> None:
    ensure_meta_table(conn)

    version = meta_get(conn, "schema_version")
    ready = schema_ready(conn)

    if version != SCHEMA_VERSION:
        drop_search_structures(conn)
        ready = False

    create_structures(conn)
    create_recall_structures(conn)

    meta_set(conn, "schema_version", SCHEMA_VERSION)
    meta_set(conn, "fts_layout_version", FTS_LAYOUT_VERSION)

    if meta_get(conn, "fts_checked_at") is None:
        meta_set(conn, "fts_checked_at", 0)

    conn.commit()

    if not ready and version != SCHEMA_VERSION:
        try:
            conn.execute("VACUUM")
        except Exception:
            pass

    _maybe_optimize(conn, force=(version != SCHEMA_VERSION or not ready))


def open_index(
    base_path: Path,
    check_fts: bool = False,
    ensure_ready: bool = False,
    fts_check_throttle_seconds: int = FTS_CHECK_THROTTLE_SECONDS,
) -> Tuple[sqlite3.Connection, Path]:
    db_path = get_index_db_path(base_path)
    conn = sqlite3.connect(str(db_path), timeout=10)
    conn.row_factory = sqlite3.Row
    _apply_pragmas(conn)

    ensure_meta_table(conn)

    version = meta_get(conn, "schema_version")
    if ensure_ready or version != SCHEMA_VERSION or not schema_ready(conn):
        ensure_schema(conn)
    else:
        create_structures(conn)
        create_recall_structures(conn)
        _maybe_optimize(conn, force=False)

    if check_fts:
        rebuild_fts_if_needed(conn, force=False, throttle_seconds=fts_check_throttle_seconds)

    return conn, db_path


def open_index_maintained(
    base_path: Path,
    force_fts_check: bool = False,
    fts_check_throttle_seconds: int = FTS_CHECK_THROTTLE_SECONDS,
) -> Tuple[sqlite3.Connection, Path]:
    return open_index(
        base_path=base_path,
        check_fts=bool(force_fts_check),
        ensure_ready=True,
        fts_check_throttle_seconds=fts_check_throttle_seconds,
    )


def trigram_available(conn: sqlite3.Connection) -> bool:
    return table_exists(conn, "search_entries_tri")


def fts_title_available(conn: sqlite3.Connection) -> bool:
    return table_exists(conn, "search_fts_title")


def fts_content_available(conn: sqlite3.Connection) -> bool:
    return table_exists(conn, "search_fts_content")


def _safe_count(conn: sqlite3.Connection, sql: str) -> int:
    try:
        row = conn.execute(sql).fetchone()
        if not row:
            return 0
        if isinstance(row, sqlite3.Row):
            return int(row[0] or 0)
        return int(row[0] or 0)
    except Exception:
        return 0


def _rebuild_fts_table(conn: sqlite3.Connection, table_name: str) -> None:
    conn.execute(f"INSERT INTO {table_name}({table_name}) VALUES('rebuild')")


def _refresh_fts_meta_counts(conn: sqlite3.Connection) -> None:
    title_count = _safe_count(conn, "SELECT COUNT(1) FROM search_fts_title")
    content_count = _safe_count(conn, "SELECT COUNT(1) FROM search_fts_content")
    meta_set(conn, "fts_layout_version", FTS_LAYOUT_VERSION)
    meta_set(conn, "fts_title_rowcount", title_count)
    meta_set(conn, "fts_content_rowcount", content_count)
    meta_set(conn, "fts_checked_at", time.time())
    conn.commit()


def rebuild_fts_if_needed(
    conn: sqlite3.Connection,
    force: bool = False,
    throttle_seconds: int = FTS_CHECK_THROTTLE_SECONDS,
) -> None:
    if not fts_title_available(conn) or not fts_content_available(conn):
        return

    now_ts = time.time()
    last_checked = meta_get_float(conn, "fts_checked_at")

    if not force and throttle_seconds > 0 and last_checked is not None:
        if (now_ts - last_checked) < float(throttle_seconds):
            return

    main_count = _safe_count(conn, "SELECT COUNT(1) FROM search_entries")
    title_count = _safe_count(conn, "SELECT COUNT(1) FROM search_fts_title")
    content_count = _safe_count(conn, "SELECT COUNT(1) FROM search_fts_content")

    layout_version = meta_get(conn, "fts_layout_version")
    last_title_count = meta_get(conn, "fts_title_rowcount")
    last_content_count = meta_get(conn, "fts_content_rowcount")

    needs_rebuild = False

    if force:
        needs_rebuild = True
    elif layout_version != FTS_LAYOUT_VERSION:
        needs_rebuild = True
    elif main_count != title_count:
        needs_rebuild = True
    elif main_count != content_count:
        needs_rebuild = True
    elif last_title_count is None or last_content_count is None:
        needs_rebuild = True

    if needs_rebuild:
        _rebuild_fts_table(conn, "search_fts_title")
        _rebuild_fts_table(conn, "search_fts_content")
        conn.commit()
        _refresh_fts_meta_counts(conn)
        _maybe_optimize(conn, force=False)
        return

    meta_set(conn, "fts_layout_version", FTS_LAYOUT_VERSION)
    meta_set(conn, "fts_title_rowcount", title_count)
    meta_set(conn, "fts_content_rowcount", content_count)
    meta_set(conn, "fts_checked_at", now_ts)
    conn.commit()


__all__ = [
    "FTS_LAYOUT_VERSION",
    "FTS_CHECK_THROTTLE_SECONDS",
    "OPTIMIZE_THROTTLE_SECONDS",
    "get_index_db_path",
    "open_index",
    "open_index_maintained",
    "table_exists",
    "ensure_meta_table",
    "meta_get",
    "meta_get_float",
    "meta_set",
    "schema_ready",
    "drop_search_structures",
    "create_structures",
    "create_recall_structures",
    "ensure_schema",
    "trigram_available",
    "fts_title_available",
    "fts_content_available",
    "rebuild_fts_if_needed",
]

