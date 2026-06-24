#!/usr/bin/env python3

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.search.search_smoke import (
    _call_search,
    _duplicate_paths_by_module,
    _evidence_by_module,
    _extract_data,
    _extract_grouped_counts,
    _extract_sync,
    _extract_sync_modules_summary,
    _extract_top_evidence,
    _extract_top_items,
    _fetch_db_stats,
    _top_items_have_marker,
)

P15_QUERIES = [
    "nisb",
    "新对话",
    "有趣短文",
    "LibraryDetail.vue",
    "RoomRolesDrawer.vue",
    "拓补",
    "病毒",
    "尼帕病毒",
    "四源搜索",
    "前端接线",
    "搜索闸门",
    "从自然语言到本体论的转化",
    "自然语言 本体论",
    "可以，现在已经形成一个足够小的可执行闭环：先把 main.js",
    "Add Explain in context button.",
    "nisb_room_shared_delete",
    "What topics are discussed in this conversation?",
    "how to fix rss import cpu qos issue",
    "what is the current search recall architecture",
    "defineProps",
    "rss_import_0812fb36edee283d",
]

CORE_NO_REGRESS = {
    "nisb",
    "新对话",
    "有趣短文",
    "LibraryDetail.vue",
    "RoomRolesDrawer.vue",
    "拓补",
    "病毒",
    "尼帕病毒",
    "四源搜索",
    "前端接线",
    "从自然语言到本体论的转化",
    "自然语言 本体论",
    "可以，现在已经形成一个足够小的可执行闭环：先把 main.js",
    "Add Explain in context button.",
    "nisb_room_shared_delete",
    "What topics are discussed in this conversation?",
    "defineProps",
    "rss_import_0812fb36edee283d",
}

ZERO_ACCEPTED = {
    "搜索闸门",
}

ORDINARY_CLASSES = {
    "keyword",
    "short",
    "short_cjk",
    "phrase",
    "symbol_heavy",
}

COMPLEX_CLASSES = {
    "filename",
    "long_nl",
    "long_phrase",
}

DB_SOFT_LIMIT_BYTES = 1_400_000_000
DB_HARD_LIMIT_BYTES = 1_600_000_000


def _read_json_records(path: str) -> List[Dict[str, Any]]:
    if not path:
        return []

    p = Path(path)
    if not p.exists():
        raise SystemExit(f"compare file not found: {path}")

    text = p.read_text().strip()
    if not text:
        return []

    try:
        parsed = json.loads(text)
        if isinstance(parsed, list):
            return [x for x in parsed if isinstance(x, dict)]
        if isinstance(parsed, dict):
            return [parsed]
    except Exception:
        pass

    out: List[Dict[str, Any]] = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except Exception:
            continue
        if isinstance(row, list):
            out.extend([x for x in row if isinstance(x, dict)])
        elif isinstance(row, dict):
            out.append(row)
    return out


def _compare_map(path: str) -> Dict[str, Dict[str, Any]]:
    rows = _read_json_records(path)
    out: Dict[str, Dict[str, Any]] = {}
    for row in rows:
        q = str(row.get("query", "") or "")
        if q:
            out[q] = row
    return out


def _files_dup_count(row: Dict[str, Any]) -> int:
    dup = row.get("duplicate_paths_by_module") or {}
    if not isinstance(dup, Mapping):
        return 0
    files = dup.get("files") or {}
    if isinstance(files, Mapping):
        return int(files.get("duplicate_paths", 0) or 0)
    return 0


def _top_titles(row: Dict[str, Any]) -> List[str]:
    return [
        str(x.get("title", "") or "")
        for x in (row.get("top3") or [])[:3]
        if isinstance(x, dict)
    ]


def _top_sources(row: Dict[str, Any]) -> List[Any]:
    return [
        x.get("matched_source_kind")
        for x in (row.get("top3_evidence") or [])[:3]
        if isinstance(x, dict)
    ]


def _latency_bucket(row: Dict[str, Any]) -> str:
    qclass = str(row.get("query_class", "") or "")
    took = int(row.get("took_ms", 0) or 0)

    if took > 1100:
        return "fail_over_1100ms"

    if qclass in ORDINARY_CLASSES:
        if took > 500:
            return "warn_ordinary_over_500ms"
        if took > 350:
            return "note_ordinary_over_350ms"
        return "ok"

    if qclass in COMPLEX_CLASSES:
        if took > 1000:
            return "warn_complex_over_1000ms"
        return "ok"

    if took > 700:
        return "warn_unknown_class_over_700ms"
    return "ok"


def _evaluate_row(
    row: Dict[str, Any],
    baseline: Optional[Dict[str, Any]],
    db_stats: Dict[str, Any],
) -> Tuple[List[str], List[str]]:
    failures: List[str] = []
    warnings: List[str] = []

    query = str(row.get("query", "") or "")
    total = int(row.get("total", 0) or 0)
    if _files_dup_count(row) > 0:
        failures.append("duplicate_paths_files")

    if bool(row.get("top3_has_trash", False)):
        failures.append("top3_has_trash")

    if bool(row.get("top3_has_history", False)):
        failures.append("top3_has_history")

    if query not in ZERO_ACCEPTED and total <= 0:
        warnings.append("zero_total")

    bucket = _latency_bucket(row)
    if bucket.startswith("fail_"):
        failures.append(bucket)
    elif bucket.startswith("warn_"):
        warnings.append(bucket)

    if baseline:
        old_total = int(baseline.get("total", 0) or 0)
        old_took = int(baseline.get("took_ms", 0) or 0)

        if query in CORE_NO_REGRESS and total < old_total:
            failures.append(f"total_regression:{old_total}->{total}")
        elif total < old_total:
            warnings.append(f"total_drop:{old_total}->{total}")

        if old_took > 0 and int(row.get("took_ms", 0) or 0) > max(1100, old_took * 2):
            warnings.append(f"latency_doubled:{old_took}->{row.get('took_ms')}")

        old_titles = [
            str(x.get("title", "") or "")
            for x in (baseline.get("top3") or [])[:3]
            if isinstance(x, dict)
        ]
        new_titles = _top_titles(row)
        if query in CORE_NO_REGRESS and old_titles and new_titles:
            overlap = len(set(old_titles[:3]) & set(new_titles[:3]))
            if overlap == 0 and query not in {"nisb"}:
                warnings.append("top3_no_overlap_with_baseline")

    return failures, warnings


def _run_one(
    query: str,
    base_path: str,
    limit: int,
    per_module_limit: int,
    db_stats: Dict[str, Any],
    baseline: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    started = time.time()
    resp = _call_search(
        query=query,
        base_path=base_path,
        limit=limit,
        per_module_limit=per_module_limit,
    )
    wall_ms = int((time.time() - started) * 1000)

    data = _extract_data(resp)
    evidence = resp.get("evidence_result") or {}
    if not isinstance(evidence, dict):
        evidence = {}

    sync = _extract_sync(data, evidence)

    row: Dict[str, Any] = {
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
        "recall_docs_rows": db_stats.get("recall_docs_rows", 0),
        "recall_fts_rows": db_stats.get("recall_fts_rows", 0),
        "recall_tier_counts": db_stats.get("recall_tier_counts", []),
        "db_stats_error": db_stats.get("db_stats_error", ""),
        "duplicate_paths_by_module": _duplicate_paths_by_module(data),
        "top3_has_trash": _top_items_have_marker(data, ".trash"),
        "top3_has_history": _top_items_have_marker(data, ".history"),
        "top3": _extract_top_items(data),
        "top3_evidence": _extract_top_evidence(data),
        "evidence_by_module": _evidence_by_module(data),
    }

    failures, warnings = _evaluate_row(row, baseline, db_stats)
    row["eval_failures"] = failures
    row["eval_warnings"] = warnings
    row["eval_status"] = "fail" if failures else ("warn" if warnings else "pass")
    row["top3_titles"] = _top_titles(row)
    row["top3_matched_source_kind"] = _top_sources(row)
    return row


def _summary(rows: List[Dict[str, Any]], db_stats: Dict[str, Any]) -> Dict[str, Any]:
    failures = [r for r in rows if r.get("eval_status") == "fail"]
    warnings = [r for r in rows if r.get("eval_status") == "warn"]

    global_failures: List[str] = []
    global_warnings: List[str] = []
    db_size = int(db_stats.get("db_size_bytes", 0) or 0)
    if db_size > DB_HARD_LIMIT_BYTES:
        global_failures.append(f"db_size_over_hard_limit:{db_size}")
    elif db_size > DB_SOFT_LIMIT_BYTES:
        global_warnings.append(f"db_size_over_soft_limit:{db_size}")

    ordinary = [
        int(r.get("took_ms", 0) or 0)
        for r in rows
        if str(r.get("query_class", "") or "") in ORDINARY_CLASSES
    ]
    ordinary_under_300 = len([x for x in ordinary if x <= 300])

    return {
        "type": "summary",
        "eval_status": "fail" if (failures or global_failures) else ("warn" if (warnings or global_warnings) else "pass"),
        "queries": len(rows),
        "failures": len(failures),
        "warnings": len(warnings),
        "global_failures": global_failures,
        "global_warnings": global_warnings,
        "failed_queries": [r.get("query") for r in failures],
        "warn_queries": [r.get("query") for r in warnings],
        "db_size_bytes": db_stats.get("db_size_bytes", 0),
        "db_soft_limit_bytes": DB_SOFT_LIMIT_BYTES,
        "db_hard_limit_bytes": DB_HARD_LIMIT_BYTES,
        "ordinary_queries": len(ordinary),
        "ordinary_under_300ms": ordinary_under_300,
        "ordinary_under_300ms_ratio": round(ordinary_under_300 / len(ordinary), 4) if ordinary else None,
        "max_took_ms": max([int(r.get("took_ms", 0) or 0) for r in rows], default=0),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-path", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--compare", default="")
    parser.add_argument("--query", action="append", default=[])
    parser.add_argument("--limit", type=int, default=80)
    parser.add_argument("--per-module-limit", type=int, default=20)
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--print-summary", action="store_true")
    args = parser.parse_args()

    queries = args.query or P15_QUERIES
    base_path = str(Path(args.base_path))
    db_stats = _fetch_db_stats(base_path)
    baseline_by_query = _compare_map(args.compare) if args.compare else {}

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    rows: List[Dict[str, Any]] = []
    with out_path.open("w", encoding="utf-8") as f:
        for query in queries:
            row = _run_one(
                query=query,
                base_path=base_path,
                limit=int(args.limit),
                per_module_limit=int(args.per_module_limit),
                db_stats=db_stats,
                baseline=baseline_by_query.get(query),
            )
            rows.append(row)
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
            f.flush()

        summary = _summary(rows, db_stats)
        f.write(json.dumps(summary, ensure_ascii=False) + "\n")

    if args.print_summary:
        print(json.dumps(summary, ensure_ascii=False, indent=2))

    if args.strict and summary.get("eval_status") == "fail":
        raise SystemExit(2)


if __name__ == "__main__":
    main()

