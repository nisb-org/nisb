#!/usr/bin/env python3

import argparse
import inspect
import json
import sqlite3
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Mapping

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.search.cross_module import nisb_search_cross_module


DEFAULT_QUERIES = [
    "nisb",
    "\u65b0\u5bf9\u8bdd",
    "\u6709\u8da3\u77ed\u6587",
    "LibraryDetail.vue",
    "\u62d3\u8865",
    "What topics are discussed in this conversation?",
]

SYNC_MODULE_FIELDS = (
    "ok",
    "mode",
    "reason",
    "indexed",
    "total",
    "deleted",
    "skipped",
    "candidates",
    "scanned",
    "walk_budget",
    "walk_budget_per_root",
    "hint_hits",
    "strong_hint_hits",
    "exact_name_hits",
    "metadata_only",
    "elapsed_ms",
)



def _safe_file_size(path: Path) -> int:
    try:
        return int(path.stat().st_size) if path.exists() else 0
    except OSError:
        return 0


def _search_db_path(base_path: str) -> Path:
    return Path(base_path) / ".nisb_cache" / "search_index_v1.sqlite3"


def _table_exists(conn: sqlite3.Connection, name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE name = ? LIMIT 1",
        (name,),
    ).fetchone()
    return row is not None


def _safe_table_count(conn: sqlite3.Connection, table: str) -> int:
    try:
        if not _table_exists(conn, table):
            return 0
        row = conn.execute(f"SELECT COUNT(1) AS n FROM {table}").fetchone()
        return int(row["n"] or 0) if row else 0
    except Exception:
        return 0


def _fetch_db_stats(base_path: str) -> Dict[str, Any]:
    db_path = _search_db_path(base_path)
    stats: Dict[str, Any] = {
        "db_path": str(db_path),
        "db_size_bytes": _safe_file_size(db_path),
        "db_wal_size_bytes": _safe_file_size(Path(str(db_path) + "-wal")),
        "db_shm_size_bytes": _safe_file_size(Path(str(db_path) + "-shm")),
        "search_entries_rows": 0,
        "search_entries_by_module_source_kind": [],
        "recall_docs_rows": 0,
        "recall_fts_rows": 0,
        "recall_tier_counts": [],
        "db_stats_error": "",
    }

    if not db_path.exists():
        stats["db_stats_error"] = "db_not_found"
        return stats

    conn = None
    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, timeout=0.2)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA query_only = ON")

        stats["search_entries_rows"] = _safe_table_count(conn, "search_entries")
        stats["recall_docs_rows"] = _safe_table_count(conn, "search_recall_docs")
        stats["recall_fts_rows"] = _safe_table_count(conn, "search_fts_recall")

        if _table_exists(conn, "search_entries"):
            rows = conn.execute(
                """
                SELECT module, source_kind, COUNT(1) AS rows
                FROM search_entries
                GROUP BY module, source_kind
                ORDER BY module, source_kind
                """
            ).fetchall()
            stats["search_entries_by_module_source_kind"] = [
                {
                    "module": str(row["module"] or ""),
                    "source_kind": str(row["source_kind"] or ""),
                    "rows": int(row["rows"] or 0),
                }
                for row in rows
            ]

        if _table_exists(conn, "search_recall_docs"):
            rows = conn.execute(
                """
                SELECT tier, module, COUNT(1) AS rows
                FROM search_recall_docs
                GROUP BY tier, module
                ORDER BY tier, module
                """
            ).fetchall()
            stats["recall_tier_counts"] = [
                {
                    "tier": int(row["tier"] or 0),
                    "module": str(row["module"] or ""),
                    "rows": int(row["rows"] or 0),
                }
                for row in rows
            ]

    except Exception as exc:
        stats["db_stats_error"] = str(exc)[:200]
    finally:
        if conn is not None:
            conn.close()

    return stats


def _extract_grouped_items(data: Dict[str, Any]) -> Dict[str, List[Dict[str, Any]]]:
    grouped = data.get("grouped") or data.get("grouped_results") or {}
    out: Dict[str, List[Dict[str, Any]]] = {}

    if not isinstance(grouped, dict):
        return out

    for module, value in grouped.items():
        items: Any = []
        if isinstance(value, dict):
            items = value.get("items") or value.get("results") or []
        elif isinstance(value, list):
            items = value

        if not isinstance(items, list):
            continue

        out[str(module)] = [item for item in items if isinstance(item, dict)]

    return out


def _normalized_item_path(item: Dict[str, Any]) -> str:
    value = item.get("path") or item.get("file_path") or ""
    return str(value or "").replace("\\", "/").strip().rstrip("/").lower()


def _duplicate_paths_by_module(data: Dict[str, Any]) -> Dict[str, Any]:
    grouped_items = _extract_grouped_items(data)
    out: Dict[str, Any] = {}

    for module, items in grouped_items.items():
        counts: Dict[str, int] = {}
        for item in items:
            path = _normalized_item_path(item)
            if not path:
                continue
            counts[path] = counts.get(path, 0) + 1

        duplicate_examples = [
            {"path": path, "count": count}
            for path, count in counts.items()
            if count > 1
        ]
        duplicate_examples.sort(key=lambda x: (-int(x["count"]), str(x["path"])))

        out[module] = {
            "items": len(items),
            "path_items": sum(counts.values()),
            "unique_paths": len(counts),
            "duplicate_paths": sum(max(0, count - 1) for count in counts.values()),
            "duplicate_examples": duplicate_examples[:5],
        }

    return out


def _is_marker_path(path: str, marker: str) -> bool:
    normalized = str(path or "").replace("\\", "/").strip().strip("/").lower()
    if not normalized:
        return False
    wrapped = f"/{normalized}/"
    return f"/{marker.strip('/').lower()}/" in wrapped


def _top_items_have_marker(data: Dict[str, Any], marker: str) -> bool:
    for item in _extract_top_items(data, limit=3):
        if _is_marker_path(str(item.get("path") or ""), marker):
            return True
    return False



def _call_search(query: str, base_path: str, limit: int, per_module_limit: int) -> Dict[str, Any]:
    kwargs = {
        "query": query,
        "base_path": base_path,
        "modules": ["chat", "dirs", "files", "library"],
        "per_module_limit": int(per_module_limit),
        "limit": int(limit),
        "fuzzy": True,
        "sync_before_query": False,
    }

    sig = inspect.signature(nisb_search_cross_module)
    accepts_kwargs = any(
        p.kind == inspect.Parameter.VAR_KEYWORD
        for p in sig.parameters.values()
    )

    if accepts_kwargs:
        return nisb_search_cross_module(**kwargs)

    filtered = {
        key: value
        for key, value in kwargs.items()
        if key in sig.parameters
    }
    return nisb_search_cross_module(**filtered)


def _extract_data(resp: Dict[str, Any]) -> Dict[str, Any]:
    try:
        results = resp.get("tool_results") or []
        if results and isinstance(results[0], dict):
            data = results[0].get("data") or {}
            if isinstance(data, dict):
                return data
    except Exception:
        pass
    return {}


def _extract_grouped_counts(data: Dict[str, Any]) -> Dict[str, int]:
    grouped = data.get("grouped") or data.get("grouped_results") or {}
    out: Dict[str, int] = {}

    if isinstance(grouped, dict):
        for key, value in grouped.items():
            if isinstance(value, dict):
                items = value.get("items") or value.get("results") or []
                out[str(key)] = len(items) if isinstance(items, list) else 0
            elif isinstance(value, list):
                out[str(key)] = len(value)

    return out


def _snippet_head(value: Any, limit: int = 180) -> str:
    text = str(value or "").replace("\n", " ").replace("\r", " ")
    text = " ".join(text.split())
    return text[:limit]


def _evidence_item(item: Dict[str, Any]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for key in (
        "module",
        "source_kind",
        "matched_source_kind",
        "recall_tier",
        "recall_chunk_index",
        "recall_evidence",
        "match_type",
        "match_reason",
        "matched_terms",
        "score",
        "priority",
        "fts_rank",
        "best_fts_rank",
        "title",
        "path",
        "item_key",
        "key",
        "parent_key",
        "group_key",
        "source_module",
    ):
        if key in item:
            out[key] = item.get(key)

    snippet = item.get("snippet")
    if snippet is None:
        snippet = item.get("content") or item.get("description") or ""
    out["snippet_head"] = _snippet_head(snippet)

    if "filename" in item and "title" not in out:
        out["title"] = item.get("filename")
    return out


def _extract_top_raw_items(data: Dict[str, Any], limit: int = 3) -> List[Dict[str, Any]]:
    rows = data.get("results") or data.get("items") or []
    if not isinstance(rows, list):
        return []
    out: List[Dict[str, Any]] = []
    for item in rows[:limit]:
        if isinstance(item, dict):
            out.append(item)
    return out


def _extract_top_evidence(data: Dict[str, Any], limit: int = 3) -> List[Dict[str, Any]]:
    raw_items = _extract_top_raw_items(data, limit=limit)
    if raw_items:
        return [_evidence_item(item) for item in raw_items]
    return [_evidence_item(item) for item in _extract_top_items(data, limit=limit)]


def _evidence_by_module(data: Dict[str, Any], limit: int = 3) -> Dict[str, List[Dict[str, Any]]]:
    grouped_items = _extract_grouped_items(data)
    out: Dict[str, List[Dict[str, Any]]] = {}
    for module, items in grouped_items.items():
        out[str(module)] = [_evidence_item(item) for item in items[:limit]]
    return out


def _extract_top_items(data: Dict[str, Any], limit: int = 3) -> List[Dict[str, Any]]:
    rows = data.get("results") or data.get("items") or []
    if not isinstance(rows, list):
        return []

    out: List[Dict[str, Any]] = []
    for item in rows[:limit]:
        if not isinstance(item, dict):
            continue
        out.append(
            {
                "title": item.get("title") or item.get("filename") or "",
                "path": item.get("path") or item.get("file_path") or "",
                "module": item.get("module") or item.get("source") or "",
                "source_kind": item.get("source_kind") or "",
                "score": item.get("score"),
            }
        )

    return out


def _extract_sync(data: Dict[str, Any], evidence: Dict[str, Any]) -> Dict[str, Any]:
    sync = data.get("sync") or evidence.get("sync") or {}
    return sync if isinstance(sync, dict) else {}


def _plain_value(value: Any) -> Any:
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, list):
        return len(value)
    if isinstance(value, tuple):
        return len(value)
    if isinstance(value, set):
        return len(value)
    if isinstance(value, dict):
        return {
            str(k): _plain_value(v)
            for k, v in value.items()
            if isinstance(k, (str, int, float, bool))
        }
    return str(value)


def _compact_module_stats(stats: Any) -> Dict[str, Any]:
    if not isinstance(stats, Mapping):
        return {}

    out: Dict[str, Any] = {}
    for key in SYNC_MODULE_FIELDS:
        if key in stats:
            out[key] = _plain_value(stats.get(key))

    payload = stats.get("payload")
    if isinstance(payload, Mapping):
        for key in SYNC_MODULE_FIELDS:
            if key not in out and key in payload:
                out[key] = _plain_value(payload.get(key))

    return out


def _extract_sync_modules_summary(sync: Dict[str, Any]) -> Dict[str, Any]:
    modules = sync.get("modules") or {}
    if not isinstance(modules, Mapping):
        return {}

    summary: Dict[str, Any] = {}
    for module, stats in modules.items():
        compact = _compact_module_stats(stats)
        if compact:
            summary[str(module)] = compact

    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-path", required=True)
    parser.add_argument("--query", action="append", default=[])
    parser.add_argument("--limit", type=int, default=80)
    parser.add_argument("--per-module-limit", type=int, default=20)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--debug-evidence", action="store_true")
    args = parser.parse_args()

    queries = args.query or DEFAULT_QUERIES
    rows: List[Dict[str, Any]] = []
    db_stats = _fetch_db_stats(str(Path(args.base_path)))

    for query in queries:
        started = time.time()
        resp = _call_search(
            query=query,
            base_path=str(Path(args.base_path)),
            limit=int(args.limit),
            per_module_limit=int(args.per_module_limit),
        )
        wall_ms = int((time.time() - started) * 1000)

        data = _extract_data(resp)
        evidence = resp.get("evidence_result") or {}
        if not isinstance(evidence, dict):
            evidence = {}

        sync = _extract_sync(data, evidence)

        rows.append(
            {
                "query": query,
                "status": resp.get("status"),
                "total": data.get("total", evidence.get("total", 0)),
                "totals": data.get("totals", evidence.get("totals", {})),
                "grouped_counts": _extract_grouped_counts(data),
                "took_ms": data.get("took_ms", evidence.get("took_ms", 0)),
                "wall_ms": wall_ms,
                "open_elapsed_ms": evidence.get("open_elapsed_ms", data.get("open_elapsed_ms", 0)),
                "sync_elapsed_ms": evidence.get("sync_elapsed_ms", data.get("sync_elapsed_ms", 0)),
                "query_elapsed_ms": evidence.get("query_elapsed_ms", data.get("query_elapsed_ms", 0)),
                "sync_mode": sync.get("mode", data.get("sync_mode", "")),
                "query_class": sync.get("query_class", evidence.get("query_class", data.get("query_class", ""))),
                "sync_modules_elapsed_ms": sync.get("sync_modules_elapsed_ms", {}),
                "sync_modules_summary": _extract_sync_modules_summary(sync),
                "lane_counts": data.get("lane_counts", evidence.get("lane_counts", {})),
                "skipped_lanes": data.get("skipped_lanes", evidence.get("skipped_lanes", [])),
                "parent_merge_before": data.get("parent_merge_before", evidence.get("parent_merge_before", None)),
                "parent_merge_after": data.get("parent_merge_after", evidence.get("parent_merge_after", None)),
                "db_size_bytes": db_stats.get("db_size_bytes", 0),
                "db_wal_size_bytes": db_stats.get("db_wal_size_bytes", 0),
                "db_shm_size_bytes": db_stats.get("db_shm_size_bytes", 0),
                "search_entries_rows": db_stats.get("search_entries_rows", 0),
                "search_entries_by_module_source_kind": db_stats.get("search_entries_by_module_source_kind", []),
                "recall_docs_rows": db_stats.get("recall_docs_rows", 0),
                "recall_fts_rows": db_stats.get("recall_fts_rows", 0),
                "recall_tier_counts": db_stats.get("recall_tier_counts", []),
                "db_stats_error": db_stats.get("db_stats_error", ""),
                "duplicate_paths_by_module": _duplicate_paths_by_module(data),
                "top3_has_trash": _top_items_have_marker(data, ".trash"),
                "top3_has_history": _top_items_have_marker(data, ".history"),
                "top3": _extract_top_items(data),
                **({
                    "top3_evidence": _extract_top_evidence(data),
                    "evidence_by_module": _evidence_by_module(data),
                } if getattr(args, "debug_evidence", False) else {}),
            }
        )

    if args.json:
        print(json.dumps(rows, ensure_ascii=False, indent=2))
        return

    for row in rows:
        print(json.dumps(row, ensure_ascii=False))


if __name__ == "__main__":
    main()
