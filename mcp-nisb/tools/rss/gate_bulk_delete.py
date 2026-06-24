from __future__ import annotations

import os
import shutil
from datetime import datetime, timezone
from typing import Any, Dict, List

from .tools import _get_basepath, _article_content_md


def _utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _pick_items(args: Dict[str, Any]) -> List[Dict[str, Any]]:
    v = args.get("items")
    if not isinstance(v, list):
        v = args.get("rss_items")
    if not isinstance(v, list):
        v = args.get("rssItems")
    if not isinstance(v, list):
        return []
    out: List[Dict[str, Any]] = []
    for it in v:
        if isinstance(it, dict):
            out.append(dict(it))
    return out


def nisb_rss_gate_bulk_delete(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    args:
      - basepath injected
      - items: list[{feed_id/article_id}] required (兼容 feedid/articleid)
      - delete_files: bool default True
    """
    basepath = _get_basepath(args)

    items = _pick_items(args)
    if not items:
        return {"success": False, "message": "missing items"}

    delete_files = bool(args.get("delete_files", True))

    deleted = 0
    skipped = 0
    failed = 0
    out_items: List[Dict[str, Any]] = []

    for it in items:
        try:
            feed_id = str(it.get("feed_id") or it.get("feedid") or it.get("feedId") or "").strip()
            article_id = str(it.get("article_id") or it.get("articleid") or it.get("articleId") or "").strip()
            if not feed_id or not article_id:
                failed += 1
                out_items.append({"status": "failed", "reason": "missing feed_id/article_id", "item": it})
                continue

            md_path = _article_content_md(basepath, feed_id, article_id)
            article_dir = os.path.dirname(md_path)

            if not os.path.exists(article_dir):
                skipped += 1
                out_items.append({"status": "skipped", "reason": "already deleted", "item": it})
                continue

            if delete_files:
                shutil.rmtree(article_dir, ignore_errors=False)

            deleted += 1
            out_items.append({"status": "deleted", "ts": _utc_iso(), "item": it})

        except Exception as e:
            failed += 1
            out_items.append({"status": "failed", "reason": str(e), "item": it})

    return {
        "success": True,
        "stats": {"deleted": deleted, "skipped": skipped, "failed": failed, "total": len(items)},
        "items": out_items,
    }

