from __future__ import annotations

import os
import json
from typing import Any, Dict, List, Optional, Tuple


def _base(args: Dict[str, Any]) -> str:
    base = args.get("base_path") or args.get("_base_path")
    if not base or not isinstance(base, str):
        raise ValueError("缺少 base_path/_base_path（网关应注入）")
    return base.rstrip("/")


def _trash_root(base: str) -> str:
    return os.path.join(base, "agent_files", ".trash")


def _safe_int(x: Any, default: int = 0) -> int:
    try:
        return int(x)
    except Exception:
        return default


def _read_json(path: str) -> Optional[Dict[str, Any]]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def _rel(base: str, abs_path: str) -> str:
    return os.path.relpath(abs_path, base).replace("\\", "/")


def nisb_fs_trash_batches_list(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    列出回收站中“批次删除”（bulk_trash 产生）的批次列表（按 ts 倒序）。
    扫描 agent_files/.trash/**/.nisb_manifest.json
    args:
      - limit: 默认 60
      - query: 可选（匹配 bulk_id / bucket_rel / 任意 original_rel 子串）
      - include_items_preview: 默认 True（返回前 8 条 original_rel 预览）
      - preview_limit: 默认 8
    """
    base = _base(args)
    limit = _safe_int(args.get("limit", 60), 60)
    limit = max(1, min(limit, 200))

    query = str(args.get("query") or "").strip().lower()

    include_preview = bool(args.get("include_items_preview", True))
    preview_limit = _safe_int(args.get("preview_limit", 8), 8)
    preview_limit = max(0, min(preview_limit, 50))

    root = _trash_root(base)
    if not os.path.isdir(root):
        return {"success": True, "items": [], "total": 0}

    batches: List[Dict[str, Any]] = []

    for dirpath, _, filenames in os.walk(root):
        if ".nisb_manifest.json" not in filenames:
            continue

        mp = os.path.join(dirpath, ".nisb_manifest.json")
        data = _read_json(mp)
        if not data:
            continue

        bulk_id = str(data.get("bulk_id") or "").strip()
        if not bulk_id:
            continue

        bucket_rel = str(data.get("bucket_rel") or _rel(base, dirpath)).replace("\\", "/")
        ts = _safe_int(data.get("ts", 0), 0)

        items = data.get("items") or []
        if not isinstance(items, list):
            items = []
        items_count = len(items)

        # 预览（用于 UI 列表）
        preview: List[str] = []
        if include_preview and preview_limit > 0:
            for it in items[:preview_limit]:
                p = str((it or {}).get("original_rel") or "").strip()
                if p:
                    preview.append(p)

        # query 过滤：bulk_id / bucket_rel / 任意 original_rel
        if query:
            hit = (query in bulk_id.lower()) or (query in bucket_rel.lower())
            if not hit:
                for it in items:
                    p = str((it or {}).get("original_rel") or "").lower()
                    if query in p:
                        hit = True
                        break
            if not hit:
                continue

        batches.append(
            {
                "bulk_id": bulk_id,
                "bucket_rel": bucket_rel,
                "ts": ts,
                "items_count": items_count,
                "items_preview": preview,
                "manifest_rel": _rel(base, mp),
            }
        )

    batches.sort(key=lambda x: (int(x.get("ts") or 0), x.get("bucket_rel") or ""), reverse=True)
    total = len(batches)
    return {"success": True, "items": batches[:limit], "total": total}

