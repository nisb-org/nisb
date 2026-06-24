#!/usr/bin/env python3

import sqlite3
from typing import Tuple

from .common import now_ts
from .index_db import meta_get_float, meta_set
from .index_shared import LOCAL_MIN_SYNC_INTERVAL


def module_min_sync_interval(module: str) -> float:
    if module in {"files", "doc", "dirs"}:
        return max(LOCAL_MIN_SYNC_INTERVAL, 0.5)
    if module == "chat":
        return 2.0
    if module == "library":
        return 4.0
    return LOCAL_MIN_SYNC_INTERVAL


def sync_due(conn: sqlite3.Connection, module: str) -> bool:
    last = meta_get_float(conn, f"sync:{module}")
    if last is None:
        return True
    return (now_ts() - last) >= module_min_sync_interval(module)


def mark_synced(conn: sqlite3.Connection, module: str, total: int = 0) -> None:
    meta_set(conn, f"sync:{module}", now_ts())
    meta_set(conn, f"count:{module}", int(total))


def module_entry_count(conn: sqlite3.Connection, module: str) -> int:
    row = conn.execute(
        "SELECT COUNT(1) AS c FROM search_entries WHERE module = ?",
        (module,),
    ).fetchone()
    if not row:
        return 0
    try:
        return int(row["c"] or 0)
    except Exception:
        return 0


def should_sync_module(conn: sqlite3.Connection, module: str, mode: str) -> Tuple[bool, str]:
    mode = str(mode or "bootstrap_if_empty").strip() or "bootstrap_if_empty"
    indexed_count = module_entry_count(conn, module)

    if mode == "never":
        return False, "mode_never"
    if mode == "force":
        return True, "mode_force"
    if mode == "bootstrap_or_due":
        if indexed_count <= 0:
            return True, "bootstrap_empty"
        if sync_due(conn, module):
            return True, "due"
        return False, "warm_skip"
    if mode == "due":
        if sync_due(conn, module):
            return True, "due"
        return False, "warm_skip"

    if indexed_count <= 0:
        return True, "bootstrap_empty"
    return False, "warm_skip"


__all__ = [
    "module_min_sync_interval",
    "sync_due",
    "mark_synced",
    "module_entry_count",
    "should_sync_module",
]

