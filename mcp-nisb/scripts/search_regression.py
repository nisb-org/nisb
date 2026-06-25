#!/usr/bin/env python3

import argparse
import csv
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Sequence

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tools.search.cross_module import nisb_search_cross_module


DEFAULT_QUERIES = [
    "nisb",
    "新对话",
    "有趣短文",
    "LibraryDetail.vue",
    "拓补",
    "What topics are discussed in this conversation?",
]


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run NISB four-source search regression.")
    parser.add_argument("--base-path", required=True, help="User base path, e.g. /opt/nisb-data/users/xxx")
    parser.add_argument("--query-file", default="", help="Plain text or JSON query file")
    parser.add_argument("--output-dir", default="", help="Directory for JSON/CSV outputs")
    parser.add_argument("--modules", default="chat,dirs,files,library", help="Comma-separated logical modules")
    parser.add_argument("--per-module-limit", type=int, default=20)
    parser.add_argument("--global-limit", type=int, default=80)
    parser.add_argument("--fuzzy", action="store_true", help="Enable fuzzy search")
    parser.add_argument("--request-prefix", default="search-regression")
    return parser.parse_args()


def _load_queries(query_file: str) -> List[str]:
    if not query_file:
        return list(DEFAULT_QUERIES)

    path = Path(query_file)
    if not path.exists():
        raise FileNotFoundError(f"query file not found: {path}")

    text = path.read_text(encoding="utf-8").strip()
    if not text:
        return list(DEFAULT_QUERIES)

    if path.suffix.lower() == ".json":
        data = json.loads(text)
        if not isinstance(data, list):
            raise ValueError("JSON query file must be a list of strings")
        queries = [str(item).strip() for item in data if str(item).strip()]
        return queries or list(DEFAULT_QUERIES)

    queries = [line.strip() for line in text.splitlines() if line.strip() and not line.strip().startswith("#")]
    return queries or list(DEFAULT_QUERIES)


def _safe_get(payload: Dict[str, Any], *keys: str, default: Any = None) -> Any:
    node: Any = payload
    for key in keys:
        if not isinstance(node, dict):
            return default
        node = node.get(key)
    return default if node is None else node


def _extract_group_totals(data: Dict[str, Any]) -> Dict[str, int]:
    grouped = data.get("grouped") or {}
    out = {}
    for module in ("chat", "dirs", "files", "library"):
        payload = grouped.get(module) or {}
        out[module] = int(payload.get("total") or 0)
    return out


def _extract_top3(data: Dict[str, Any]) -> List[str]:
    results = data.get("results") or data.get("items") or []
    top: List[str] = []
    for item in results[:3]:
        if not isinstance(item, dict):
            continue
        text = (
            str(item.get("path") or "").strip()
            or str(item.get("file_path") or "").strip()
            or str(item.get("title") or "").strip()
            or str(item.get("filename") or "").strip()
            or str(item.get("dirname") or "").strip()
            or str(item.get("conv_id") or "").strip()
        )
        if text:
            top.append(text)
    while len(top) < 3:
        top.append("")
    return top[:3]


def _run_one_query(
    base_path: str,
    modules: Sequence[str],
    per_module_limit: int,
    global_limit: int,
    fuzzy: bool,
    query: str,
    request_prefix: str,
    index: int,
) -> Dict[str, Any]:
    response = nisb_search_cross_module(
        query=query,
        base_path=base_path,
        modules=list(modules),
        per_module_limit=per_module_limit,
        global_limit=global_limit,
        fuzzy_enabled=fuzzy,
        request_id=f"{request_prefix}-{index + 1}",
    )

    data = _safe_get(response, "tool_results", default=[])
    if isinstance(data, list) and data:
        tool_data = data[0].get("data") or {}
    else:
        tool_data = {}

    evidence_result = response.get("evidence_result") or {}
    sync = tool_data.get("sync") or {}
    grouped_totals = _extract_group_totals(tool_data)
    top1, top2, top3 = _extract_top3(tool_data)

    return {
        "query": query,
        "status": str(response.get("status") or ""),
        "message": str(response.get("message") or ""),
        "total": int(tool_data.get("total") or 0),
        "took_ms": int(tool_data.get("took_ms") or evidence_result.get("took_ms") or 0),
        "open_elapsed_ms": int(evidence_result.get("open_elapsed_ms") or 0),
        "sync_elapsed_ms": int(evidence_result.get("sync_elapsed_ms") or 0),
        "query_elapsed_ms": int(evidence_result.get("query_elapsed_ms") or 0),
        "sync_mode": str(sync.get("mode") or ""),
        "group_chat": grouped_totals.get("chat", 0),
        "group_dirs": grouped_totals.get("dirs", 0),
        "group_files": grouped_totals.get("files", 0),
        "group_library": grouped_totals.get("library", 0),
        "top1": top1,
        "top2": top2,
        "top3": top3,
        "response": response,
    }


def _write_json(path: Path, rows: List[Dict[str, Any]]) -> None:
    serializable = []
    for row in rows:
        row_copy = dict(row)
        serializable.append(row_copy)
    path.write_text(
        json.dumps(
            {
                "generated_at": datetime.now().isoformat(),
                "rows": serializable,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def _write_csv(path: Path, rows: List[Dict[str, Any]]) -> None:
    columns = [
        "query",
        "status",
        "message",
        "total",
        "took_ms",
        "open_elapsed_ms",
        "sync_elapsed_ms",
        "query_elapsed_ms",
        "sync_mode",
        "group_chat",
        "group_dirs",
        "group_files",
        "group_library",
        "top1",
        "top2",
        "top3",
    ]
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in columns})


def main() -> int:
    args = _parse_args()
    queries = _load_queries(args.query_file)
    modules = [part.strip() for part in str(args.modules).split(",") if part.strip()]

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = Path(args.output_dir).resolve() if args.output_dir else Path.cwd()
    output_dir.mkdir(parents=True, exist_ok=True)

    json_path = output_dir / f"search_regression_{timestamp}.json"
    csv_path = output_dir / f"search_regression_{timestamp}.csv"

    rows: List[Dict[str, Any]] = []
    for idx, query in enumerate(queries):
        row = _run_one_query(
            base_path=args.base_path,
            modules=modules,
            per_module_limit=args.per_module_limit,
            global_limit=args.global_limit,
            fuzzy=args.fuzzy,
            query=query,
            request_prefix=args.request_prefix,
            index=idx,
        )
        rows.append(row)

    _write_json(json_path, rows)
    _write_csv(csv_path, rows)

    print(f"JSON={json_path}")
    print(f"CSV={csv_path}")
    print("SUMMARY")
    for row in rows:
        print(
            f"- query={row['query']} "
            f"status={row['status']} "
            f"total={row['total']} "
            f"took_ms={row['took_ms']} "
            f"sync_mode={row['sync_mode']} "
            f"top1={row['top1']}"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

