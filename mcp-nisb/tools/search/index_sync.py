#!/usr/bin/env python3

import sqlite3
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Tuple

from .common import now_ts
from .index_db import (
    ensure_schema,
    fts_content_available,
    fts_title_available,
    get_index_db_path,
    meta_get,
    meta_get_float,
    meta_set,
    open_index as db_open_index,
    rebuild_fts_if_needed,
    table_exists,
    trigram_available,
)
from .index_shared import SCHEMA_VERSION
from .index_store import (
    delete_stale,
    delete_trigram_keys,
    load_existing_map,
    prepare_entry,
    sync_trigram_entries,
    upsert_entries,
)
from .index_sync_chat import (
    chat_refresh_due,
    decide_chat_refresh,
    get_chat_refresh_snapshot,
    sync_chat,
)
from .index_sync_fs import (
    _build_file_content_entries,
    quick_sync_dirs_module,
    quick_sync_file_module,
    sync_dirs_module,
    sync_file_module,
)
from .index_sync_library import (
    _build_library_content_entries,
    quick_sync_library,
    sync_library,
    sync_library_doc_dirs,
    sync_library_loose_files,
)
from .index_sync_state import (
    mark_synced,
    module_entry_count,
    module_min_sync_interval,
    should_sync_module,
    sync_due,
)

_OPEN_RUNTIME_BY_CONN_ID: Dict[int, Dict[str, Any]] = {}
_WARM_STATE_BY_DB_PATH: Dict[str, Dict[str, Any]] = {}
_WARM_STATE_LOCK = threading.Lock()

SEARCH_WARM_TTL_SECONDS = 90.0
SEARCH_WARM_PROGRESS_LIMIT_MS = 180
SEARCH_WARM_PROGRESS_STEPS = 1200
SEARCH_WARM_ROW_SAMPLE = 24


def _apply_fast_pragmas(conn: sqlite3.Connection) -> None:
    for sql in (
        "PRAGMA journal_mode=WAL;",
        "PRAGMA synchronous=NORMAL;",
        "PRAGMA temp_store=MEMORY;",
        "PRAGMA cache_size=-32768;",
        "PRAGMA mmap_size=134217728;",
        "PRAGMA wal_autocheckpoint=1000;",
        "PRAGMA busy_timeout=10000;",
    ):
        try:
            conn.execute(sql)
        except Exception:
            continue


def _pragma_scalar(conn: sqlite3.Connection, pragma_sql: str, fallback: Any = "") -> Any:
    try:
        row = conn.execute(pragma_sql).fetchone()
        if row is None:
            return fallback
        if isinstance(row, sqlite3.Row):
            try:
                return row[0]
            except Exception:
                return fallback
        if isinstance(row, tuple):
            return row[0] if row else fallback
        try:
            return row[0]
        except Exception:
            return fallback
    except Exception:
        return fallback


def get_runtime_pragma_snapshot(conn: sqlite3.Connection) -> Dict[str, Any]:
    return {
        "journal_mode": str(_pragma_scalar(conn, "PRAGMA journal_mode;", "")),
        "synchronous": int(_pragma_scalar(conn, "PRAGMA synchronous;", 0) or 0),
        "temp_store": int(_pragma_scalar(conn, "PRAGMA temp_store;", 0) or 0),
        "cache_size": int(_pragma_scalar(conn, "PRAGMA cache_size;", 0) or 0),
        "mmap_size": int(_pragma_scalar(conn, "PRAGMA mmap_size;", 0) or 0),
        "busy_timeout": int(_pragma_scalar(conn, "PRAGMA busy_timeout;", 0) or 0),
        "wal_autocheckpoint": int(_pragma_scalar(conn, "PRAGMA wal_autocheckpoint;", 0) or 0),
        "page_count": int(_pragma_scalar(conn, "PRAGMA page_count;", 0) or 0),
        "freelist_count": int(_pragma_scalar(conn, "PRAGMA freelist_count;", 0) or 0),
        "page_size": int(_pragma_scalar(conn, "PRAGMA page_size;", 0) or 0),
    }


def _remember_open_runtime(conn: sqlite3.Connection, info: Dict[str, Any]) -> None:
    try:
        _OPEN_RUNTIME_BY_CONN_ID[id(conn)] = dict(info)
    except Exception:
        pass


def get_open_runtime_snapshot(conn: sqlite3.Connection) -> Dict[str, Any]:
    try:
        return dict(_OPEN_RUNTIME_BY_CONN_ID.get(id(conn), {}))
    except Exception:
        return {}


def clear_open_runtime_snapshot(conn: sqlite3.Connection) -> None:
    try:
        _OPEN_RUNTIME_BY_CONN_ID.pop(id(conn), None)
    except Exception:
        pass


def _db_warm_key(db_path: Path) -> str:
    return str(Path(str(db_path)).resolve())


def _get_db_warm_state(db_path: Path) -> Dict[str, Any]:
    key = _db_warm_key(db_path)
    with _WARM_STATE_LOCK:
        return dict(_WARM_STATE_BY_DB_PATH.get(key, {}))


def _mark_db_warm(
    db_path: Path,
    warmed: bool,
    reason: str,
    elapsed_ms: int = 0,
    statements: int = 0,
) -> None:
    key = _db_warm_key(db_path)
    with _WARM_STATE_LOCK:
        _WARM_STATE_BY_DB_PATH[key] = {
            "warmed": bool(warmed),
            "reason": str(reason or ""),
            "elapsed_ms": int(elapsed_ms or 0),
            "statements": int(statements or 0),
            "ts": float(now_ts()),
        }


def _invalidate_db_warm_state(base_path: Path) -> None:
    db_path = get_index_db_path(Path(str(base_path)))
    key = _db_warm_key(db_path)
    with _WARM_STATE_LOCK:
        _WARM_STATE_BY_DB_PATH.pop(key, None)


def _warm_state_due(db_path: Path) -> bool:
    state = _get_db_warm_state(db_path)
    if not state:
        return True
    ts = float(state.get("ts") or 0.0)
    if (now_ts() - ts) > SEARCH_WARM_TTL_SECONDS:
        return True
    return not bool(state.get("warmed"))


def _safe_warm_fetch(
    conn: sqlite3.Connection,
    sql: str,
    params: tuple = (),
    timeout_ms: int = SEARCH_WARM_PROGRESS_LIMIT_MS,
    progress_steps: int = SEARCH_WARM_PROGRESS_STEPS,
) -> None:
    callbacks_limit = max(1, int(timeout_ms))
    callback_count = {"n": 0}

    def _progress() -> int:
        callback_count["n"] += 1
        if callback_count["n"] >= callbacks_limit:
            return 1
        return 0

    conn.set_progress_handler(_progress, progress_steps)
    try:
        cur = conn.execute(sql, params)
        cur.fetchall()
    except Exception:
        pass
    finally:
        conn.set_progress_handler(None, 0)


def _prime_search_read_path(conn: sqlite3.Connection, db_path: Path) -> Dict[str, Any]:
    if not _warm_state_due(db_path):
        state = _get_db_warm_state(db_path)
        return {
            "read_path_primed": bool(state.get("warmed", False)),
            "prime_reason": str(state.get("reason") or "warm_cache_recent"),
            "prime_elapsed_ms": 0,
            "prime_statements": 0,
            "prime_skipped": True,
        }

    started = time.time()
    statements = 0

    warm_sqls = [
        ("SELECT name FROM sqlite_master WHERE type='table' LIMIT 8", ()),
        ("SELECT value FROM search_meta WHERE key='schema_version' LIMIT 1", ()),
        ("SELECT rowid FROM search_entries ORDER BY rowid DESC LIMIT ?", (SEARCH_WARM_ROW_SAMPLE,)),
        ("SELECT rowid FROM search_entries WHERE module='chat' ORDER BY rowid DESC LIMIT ?", (SEARCH_WARM_ROW_SAMPLE,)),
        ("SELECT rowid FROM search_entries WHERE module='doc' ORDER BY rowid DESC LIMIT 8", ()),
        ("SELECT rowid FROM search_entries WHERE module='files' ORDER BY rowid DESC LIMIT 8", ()),
        ("SELECT rowid FROM search_entries WHERE module='library' ORDER BY rowid DESC LIMIT 8", ()),
        ("SELECT rowid FROM search_fts_title LIMIT 8", ()),
        ("SELECT rowid FROM search_fts_content LIMIT 8", ()),
    ]

    for sql, params in warm_sqls:
        _safe_warm_fetch(conn, sql, params=params)
        statements += 1

    try:
        conn.execute("PRAGMA optimize;")
    except Exception:
        pass

    elapsed_ms = int((time.time() - started) * 1000)
    _mark_db_warm(
        db_path=db_path,
        warmed=True,
        reason="cold_open_prewarm",
        elapsed_ms=elapsed_ms,
        statements=statements,
    )
    return {
        "read_path_primed": True,
        "prime_reason": "cold_open_prewarm",
        "prime_elapsed_ms": elapsed_ms,
        "prime_statements": statements,
        "prime_skipped": False,
    }


def _fast_schema_ready(conn: sqlite3.Connection) -> bool:
    try:
        if not table_exists(conn, "search_meta"):
            return False
        if not table_exists(conn, "search_entries"):
            return False
        if not table_exists(conn, "search_fts_title"):
            return False
        if not table_exists(conn, "search_fts_content"):
            return False
        version = meta_get(conn, "schema_version")
        if str(version or "") != str(SCHEMA_VERSION):
            return False
        return True
    except Exception:
        return False


def open_index(
    base_path: Path,
    check_fts: bool = False,
    ensure_ready: bool = False,
    fts_check_throttle_seconds: int = 120,
) -> Tuple[sqlite3.Connection, Path]:
    base_path = Path(str(base_path))

    if ensure_ready or check_fts:
        conn, db_path = db_open_index(
            base_path=base_path,
            check_fts=bool(check_fts),
            ensure_ready=bool(ensure_ready),
            fts_check_throttle_seconds=fts_check_throttle_seconds,
        )
        _apply_fast_pragmas(conn)
        prime_info = _prime_search_read_path(conn, db_path)
        _remember_open_runtime(
            conn,
            {
                "entrypoint": "index_sync.open_index",
                "used_fast_path": False,
                "fallback_to_db_open": False,
                "schema_ready_on_probe": None,
                "ensure_ready_requested": bool(ensure_ready),
                "check_fts_requested": bool(check_fts),
                "pragmas_reapplied": True,
                "db_path": str(db_path),
                **prime_info,
            },
        )
        return conn, db_path

    db_path = get_index_db_path(base_path)
    conn = sqlite3.connect(str(db_path), timeout=10)
    conn.row_factory = sqlite3.Row
    _apply_fast_pragmas(conn)

    schema_ready_on_probe = _fast_schema_ready(conn)
    if not schema_ready_on_probe:
        try:
            conn.close()
        except Exception:
            pass

        conn, db_path = db_open_index(
            base_path=base_path,
            check_fts=False,
            ensure_ready=True,
            fts_check_throttle_seconds=fts_check_throttle_seconds,
        )
        _apply_fast_pragmas(conn)
        prime_info = _prime_search_read_path(conn, db_path)
        _remember_open_runtime(
            conn,
            {
                "entrypoint": "index_sync.open_index",
                "used_fast_path": False,
                "fallback_to_db_open": True,
                "schema_ready_on_probe": False,
                "ensure_ready_requested": False,
                "check_fts_requested": False,
                "pragmas_reapplied": True,
                "db_path": str(db_path),
                **prime_info,
            },
        )
        return conn, db_path

    prime_info = _prime_search_read_path(conn, db_path)
    _remember_open_runtime(
        conn,
        {
            "entrypoint": "index_sync.open_index",
            "used_fast_path": True,
            "fallback_to_db_open": False,
            "schema_ready_on_probe": True,
            "ensure_ready_requested": False,
            "check_fts_requested": False,
            "pragmas_reapplied": True,
            "db_path": str(db_path),
            **prime_info,
        },
    )
    return conn, db_path


def open_index_maintained(
    base_path: Path,
    force_fts_check: bool = False,
    fts_check_throttle_seconds: int = 120,
) -> Tuple[sqlite3.Connection, Path]:
    conn, db_path = db_open_index(
        base_path=Path(str(base_path)),
        check_fts=bool(force_fts_check),
        ensure_ready=True,
        fts_check_throttle_seconds=fts_check_throttle_seconds,
    )
    _apply_fast_pragmas(conn)
    prime_info = _prime_search_read_path(conn, db_path)
    _remember_open_runtime(
        conn,
        {
            "entrypoint": "index_sync.open_index_maintained",
            "used_fast_path": False,
            "fallback_to_db_open": False,
            "schema_ready_on_probe": None,
            "ensure_ready_requested": True,
            "check_fts_requested": bool(force_fts_check),
            "pragmas_reapplied": True,
            "db_path": str(db_path),
            **prime_info,
        },
    )
    return conn, db_path


def quick_sync_min_interval(module: str) -> float:
    if module in {"files", "doc", "dirs"}:
        return 8.0
    if module == "library":
        return 15.0
    if module == "chat":
        return 999999.0
    return 10.0


def quick_sync_due(conn: sqlite3.Connection, module: str) -> bool:
    last = meta_get_float(conn, f"quick_sync:{module}")
    if last is None:
        return True
    return (now_ts() - last) >= quick_sync_min_interval(module)


def mark_quick_synced(conn: sqlite3.Connection, module: str, payload: Dict[str, Any]) -> None:
    meta_set(conn, f"quick_sync:{module}", now_ts())
    meta_set(conn, f"quick_sync:indexed:{module}", int(payload.get("indexed", 0) or 0))
    meta_set(conn, f"quick_sync:candidates:{module}", int(payload.get("candidates", 0) or 0))


def _timed_sync_payload(sync_fn, *args, **kwargs) -> Dict[str, Any]:
    started = time.time()
    payload = sync_fn(*args, **kwargs)
    elapsed_ms = int((time.time() - started) * 1000)

    if isinstance(payload, dict):
        out = dict(payload)
    else:
        out = {}

    out["elapsed_ms"] = int(out.get("elapsed_ms") or elapsed_ms)
    return out


def sync_modules(
    conn: sqlite3.Connection,
    base_path: Path,
    modules: List[str],
    mode: str = "bootstrap_if_empty",
) -> Dict[str, Dict[str, Any]]:
    stats: Dict[str, Dict[str, Any]] = {}

    for module in modules:
        should_run, reason = should_sync_module(conn, module, mode)
        if not should_run:
            stats[module] = {
                "indexed": 0,
                "deleted": 0,
                "total": int(module_entry_count(conn, module) or 0),
                "skipped": 1,
                "reason": reason,
                "elapsed_ms": 0,
            }
            continue

        if module == "chat":
            stats[module] = _timed_sync_payload(sync_chat, conn, base_path)
        elif module == "doc":
            stats[module] = _timed_sync_payload(
                sync_file_module,
                conn=conn,
                base_path=base_path,
                module="doc",
                root=base_path / "documents",
                recursive=False,
            )
        elif module == "files":
            stats[module] = _timed_sync_payload(
                sync_file_module,
                conn=conn,
                base_path=base_path,
                module="files",
                root=base_path / "agent_files",
                recursive=True,
            )
        elif module == "dirs":
            stats[module] = _timed_sync_payload(sync_dirs_module, conn, base_path)
        elif module == "library":
            stats[module] = _timed_sync_payload(sync_library, conn, base_path)
        else:
            stats[module] = {
                "indexed": 0,
                "deleted": 0,
                "total": 0,
                "skipped": 1,
                "reason": "unsupported",
                "elapsed_ms": 0,
            }
            continue

        stats[module]["reason"] = reason

    conn.commit()
    _invalidate_db_warm_state(base_path)
    return stats


def quick_sync_modules(
    conn: sqlite3.Connection,
    base_path: Path,
    modules: List[str],
    within_seconds: int = 300,
    max_candidates_per_module: int = 200,
) -> Dict[str, Dict[str, Any]]:
    stats: Dict[str, Dict[str, Any]] = {}

    for module in modules:
        if module == "chat":
            stats[module] = {
                "indexed": 0,
                "deleted": 0,
                "total": int(module_entry_count(conn, module) or 0),
                "skipped": 1,
                "reason": "quick_sync_unsupported",
                "candidates": 0,
                "elapsed_ms": 0,
            }
            continue

        if not quick_sync_due(conn, module):
            stats[module] = {
                "indexed": 0,
                "deleted": 0,
                "total": int(module_entry_count(conn, module) or 0),
                "skipped": 1,
                "reason": "quick_recent_skip",
                "candidates": 0,
                "elapsed_ms": 0,
            }
            continue

        if module == "doc":
            payload = _timed_sync_payload(
                quick_sync_file_module,
                conn=conn,
                base_path=base_path,
                module="doc",
                root=base_path / "documents",
                recursive=False,
                within_seconds=within_seconds,
                max_candidates=max_candidates_per_module,
            )
        elif module == "files":
            payload = _timed_sync_payload(
                quick_sync_file_module,
                conn=conn,
                base_path=base_path,
                module="files",
                root=base_path / "agent_files",
                recursive=True,
                within_seconds=within_seconds,
                max_candidates=max_candidates_per_module,
            )
        elif module == "dirs":
            payload = _timed_sync_payload(
                quick_sync_dirs_module,
                conn=conn,
                base_path=base_path,
                within_seconds=within_seconds,
                max_candidates=max_candidates_per_module,
            )
        elif module == "library":
            payload = _timed_sync_payload(
                quick_sync_library,
                conn=conn,
                base_path=base_path,
                within_seconds=within_seconds,
                max_candidates=max_candidates_per_module,
            )
        else:
            payload = {
                "indexed": 0,
                "deleted": 0,
                "total": 0,
                "skipped": 1,
                "reason": "unsupported",
                "candidates": 0,
                "elapsed_ms": 0,
            }
            stats[module] = payload
            continue

        payload["reason"] = "quick_mtime_scan"
        stats[module] = payload
        mark_quick_synced(conn, module, payload)

    conn.commit()
    _invalidate_db_warm_state(base_path)
    return stats

    
__all__ = [
    "get_index_db_path",
    "open_index",
    "open_index_maintained",
    "get_runtime_pragma_snapshot",
    "get_open_runtime_snapshot",
    "clear_open_runtime_snapshot",
    "sync_modules",
    "quick_sync_modules",
    "ensure_schema",
    "table_exists",
    "trigram_available",
    "fts_title_available",
    "fts_content_available",
    "rebuild_fts_if_needed",
    "module_entry_count",
    "module_min_sync_interval",
    "sync_due",
    "should_sync_module",
    "mark_synced",
    "quick_sync_min_interval",
    "quick_sync_due",
    "mark_quick_synced",
    "load_existing_map",
    "delete_trigram_keys",
    "delete_stale",
    "prepare_entry",
    "sync_trigram_entries",
    "upsert_entries",
    "sync_chat",
    "chat_refresh_due",
    "decide_chat_refresh",
    "get_chat_refresh_snapshot",
    "sync_file_module",
    "sync_dirs_module",
    "sync_library",
    "_build_file_content_entries",
    "_build_library_content_entries",
    "sync_library_doc_dirs",
    "sync_library_loose_files",
]

