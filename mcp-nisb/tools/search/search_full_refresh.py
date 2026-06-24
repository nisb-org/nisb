#!/usr/bin/env python3

import argparse
import json
import sqlite3
import sys
import time
import traceback
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.search.index_sync import open_index
from tools.search.index_sync_chat import sync_chat
from tools.search.index_sync_fs import sync_dirs_module, sync_file_module
from tools.search.index_sync_library import sync_library


DEFAULT_MODULES = ["doc", "files", "dirs", "chat", "library"]


def _json_print(payload: Dict[str, Any]) -> None:
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True), flush=True)


def _db_path(base_path: Path) -> Path:
    return base_path / ".nisb_cache" / "search_index_v1.sqlite3"


def _db_bytes(db_path: Path) -> int:
    total = 0
    for suffix in ("", "-wal", "-shm"):
        path = Path(str(db_path) + suffix)
        if path.exists():
            total += path.stat().st_size
    return total


def _open_conn(base_path: Path) -> sqlite3.Connection:
    opened = open_index(base_path)
    if isinstance(opened, tuple):
        return opened[0]
    return opened


def _backup_db(db_path: Path, backup_path: Path) -> Dict[str, Any]:
    backup_path.parent.mkdir(parents=True, exist_ok=True)
    src = sqlite3.connect(str(db_path))
    dst = sqlite3.connect(str(backup_path))
    try:
        src.backup(dst)
    finally:
        dst.close()
        src.close()

    return {
        "backup_path": str(backup_path),
        "backup_bytes": backup_path.stat().st_size if backup_path.exists() else 0,
    }


def _table_counts(conn: sqlite3.Connection) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    out["search_entries_total"] = int(conn.execute("SELECT COUNT(*) FROM search_entries").fetchone()[0])
    out["modules"] = {
        str(module): int(count)
        for module, count in conn.execute(
            "SELECT module, COUNT(*) FROM search_entries GROUP BY module ORDER BY module"
        ).fetchall()
    }
    out["search_fts_title"] = int(conn.execute("SELECT COUNT(*) FROM search_fts_title").fetchone()[0])
    out["search_fts_content"] = int(conn.execute("SELECT COUNT(*) FROM search_fts_content").fetchone()[0])
    out["page_count"] = int(conn.execute("PRAGMA page_count").fetchone()[0])
    out["page_size"] = int(conn.execute("PRAGMA page_size").fetchone()[0])
    out["freelist_count"] = int(conn.execute("PRAGMA freelist_count").fetchone()[0])
    return out


def _module_runner(conn: sqlite3.Connection, base_path: Path, module: str) -> Callable[[], Dict[str, Any]]:
    if module == "doc":
        return lambda: sync_file_module(
            conn,
            base_path,
            "doc",
            base_path / "documents",
            recursive=False,
            metadata_only=False,
        )
    if module == "files":
        return lambda: sync_file_module(
            conn,
            base_path,
            "files",
            base_path / "agent_files",
            recursive=True,
            metadata_only=False,
        )
    if module == "dirs":
        return lambda: sync_dirs_module(conn, base_path)
    if module == "chat":
        return lambda: sync_chat(conn, base_path)
    if module == "library":
        return lambda: sync_library(conn, base_path)
    raise ValueError(f"unknown module: {module}")


def _normalize_modules(values: Iterable[str]) -> List[str]:
    modules: List[str] = []
    for value in values:
        if value == "all":
            modules.extend(DEFAULT_MODULES)
        else:
            modules.append(value)

    out: List[str] = []
    for module in modules:
        if module not in DEFAULT_MODULES:
            raise ValueError(f"unknown module: {module}")
        if module not in out:
            out.append(module)
    return out


def run_refresh(
    base_path: Path,
    modules: List[str],
    backup: bool,
    max_growth: float,
    backup_path: Optional[Path],
    ensure_recall_tier2: bool = True,
) -> Dict[str, Any]:
    started = time.time()
    db_path = _db_path(base_path)
    pre_bytes = _db_bytes(db_path)

    result: Dict[str, Any] = {
        "ok": False,
        "base_path": str(base_path),
        "db_path": str(db_path),
        "modules_requested": modules,
        "pre_db_bytes": pre_bytes,
        "module_results": {},
    }

    if not db_path.exists():
        raise FileNotFoundError(str(db_path))

    if backup:
        if backup_path is None:
            stamp = time.strftime("%Y%m%d_%H%M%S")
            backup_path = base_path / ".nisb_cache" / "backups" / f"search_index_v1.sqlite3.bak.full-refresh-{stamp}"
        result["backup"] = _backup_db(db_path, backup_path)
        _json_print({"event": "backup_done", **result["backup"]})

    conn: Optional[sqlite3.Connection] = None
    try:
        conn = _open_conn(base_path)
        conn.execute("PRAGMA busy_timeout=10000")
        result["pre_counts"] = _table_counts(conn)
        _json_print({"event": "pre_counts", "counts": result["pre_counts"], "db_bytes": pre_bytes})

        for module in modules:
            module_started = time.time()
            try:
                runner = _module_runner(conn, base_path, module)
                payload = runner()
                conn.commit()

                elapsed_ms = int((time.time() - module_started) * 1000)
                current_bytes = _db_bytes(db_path)
                module_result = {
                    "ok": True,
                    "elapsed_ms": elapsed_ms,
                    "db_bytes_after": current_bytes,
                    "payload": payload,
                }
                result["module_results"][module] = module_result
                _json_print({"event": "module_done", "module": module, **module_result})

                if pre_bytes > 0 and current_bytes > int(pre_bytes * max_growth):
                    raise RuntimeError(
                        f"db_size_guard_exceeded: module={module} current={current_bytes} limit={int(pre_bytes * max_growth)}"
                    )

            except Exception as exc:
                conn.rollback()
                module_result = {
                    "ok": False,
                    "elapsed_ms": int((time.time() - module_started) * 1000),
                    "error": repr(exc),
                    "traceback": traceback.format_exc(),
                }
                result["module_results"][module] = module_result
                _json_print({"event": "module_failed", "module": module, **module_result})
                raise

        if ensure_recall_tier2:
            recall_modules = [m for m in ("files", "doc", "dirs", "chat") if m in set(modules)]
            if recall_modules:
                recall_started = time.time()
                try:
                    from tools.search.search_recall_maintenance import ensure_recall_tier2_fs
                    recall_payload = ensure_recall_tier2_fs(
                        conn,
                        base_path,
                        modules=recall_modules,
                        online=False,
                        max_parents=0,
                        force=True,
                    )
                    conn.commit()
                    result["recall_tier2_fs"] = recall_payload
                    _json_print({
                        "event": "recall_tier2_fs_done",
                        "elapsed_ms": int((time.time() - recall_started) * 1000),
                        **recall_payload,
                    })
                except Exception as exc:
                    conn.rollback()
                    result["recall_tier2_fs"] = {
                        "ok": False,
                        "error": repr(exc),
                        "traceback": traceback.format_exc(),
                    }
                    _json_print({
                        "event": "recall_tier2_fs_failed",
                        **result["recall_tier2_fs"],
                    })
                    raise

        try:
            conn.execute("PRAGMA optimize")
            conn.commit()
            result["pragma_optimize"] = True
            _json_print({"event": "pragma_optimize_done"})
        except Exception as exc:
            result["pragma_optimize"] = False
            result["pragma_optimize_error"] = repr(exc)
            _json_print({"event": "pragma_optimize_failed", "error": repr(exc)})

        try:
            conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            conn.commit()
            result["wal_checkpoint_truncate"] = True
            _json_print({"event": "wal_checkpoint_truncate_done"})
        except Exception as exc:
            result["wal_checkpoint_truncate"] = False
            result["wal_checkpoint_truncate_error"] = repr(exc)
            _json_print({"event": "wal_checkpoint_truncate_failed", "error": repr(exc)})

        result["post_counts"] = _table_counts(conn)
        result["post_db_bytes"] = _db_bytes(db_path)
        result["elapsed_ms"] = int((time.time() - started) * 1000)
        result["ok"] = True
        return result

    except Exception as exc:
        result["ok"] = False
        result["error"] = repr(exc)
        result["traceback"] = traceback.format_exc()
        result["elapsed_ms"] = int((time.time() - started) * 1000)
        return result

    finally:
        if conn is not None:
            conn.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-path", required=True)
    parser.add_argument("--modules", nargs="+", default=["all"])
    parser.add_argument("--backup", action="store_true")
    parser.add_argument("--backup-path", default="")
    parser.add_argument("--max-growth", type=float, default=3.0)
    args = parser.parse_args()

    base_path = Path(args.base_path).resolve()
    modules = _normalize_modules(args.modules)
    backup_path = Path(args.backup_path).resolve() if args.backup_path else None

    result = run_refresh(
        base_path=base_path,
        modules=modules,
        backup=bool(args.backup),
        max_growth=float(args.max_growth),
        backup_path=backup_path,
    )

    print("FINAL_RESULT", flush=True)
    print(json.dumps(result, ensure_ascii=False, indent=2), flush=True)

    if not result.get("ok"):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
