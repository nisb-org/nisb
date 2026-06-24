from __future__ import annotations

import os
import shutil
import hashlib
from datetime import datetime, timezone
from typing import Any, Dict, List, Set

from core.storage import load_jsonl, append_jsonl
from .tools import _get_basepath, _uid_from_basepath, _article_content_md
from ..filesystem.send_to_library_core import fs_send_to_library_core


def _utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _import_log_path(basepath: str) -> str:
    return os.path.join(basepath, "rss", "rss_gate_imported_urls.jsonl")


def _load_imported_urls(basepath: str) -> Set[str]:
    rows = load_jsonl(_import_log_path(basepath)) or []
    out: Set[str] = set()
    for r in rows:
        if not isinstance(r, dict):
            continue
        url = str(r.get("url") or "").strip()
        if url:
            out.add(url)
    return out


def _safe_filename(s: str) -> str:
    h = hashlib.sha256((s or "").encode("utf-8")).hexdigest()[:16]
    return f"rss_gate_{h}.md"


def _pick_items(args: Dict[str, Any]) -> List[Dict[str, Any]]:
    v = args.get("items")
    if not isinstance(v, list):
        v = args.get("rss_items")
    if not isinstance(v, list):
        v = args.get("rssItems")
    if not isinstance(v, list):
        v = args.get("rssitems")
    if not isinstance(v, list):
        return []
    out: List[Dict[str, Any]] = []
    for it in v:
        if isinstance(it, dict):
            out.append(dict(it))
    return out


def nisb_rss_gate_import_to_library(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    RSS Gate → Library 批量入库工具。
    
    args:
      - basepath: injected
      - library_id / libraryid: target library
      - items: list[{feed_id, article_id, url, ...}]
      - mode: "copy" | "move" (default: "copy")
    
    return:
      {
        "success": true,
        "imported": int,
        "skipped": int,
        "failed": int,
        "items": [{status, url, reason, ...}]
      }
    """
    basepath = _get_basepath(args)
    uid = _uid_from_basepath(basepath)

    # 兼容 libraryid / library_id
    libraryid = str(args.get("libraryid") or "").strip()
    library_id = str(args.get("library_id") or "").strip()
    target_library_id = libraryid or library_id
    if not target_library_id:
        return {"success": False, "message": "missing libraryid/library_id"}

    items = _pick_items(args)
    if not items:
        return {"success": False, "message": "missing items/rssitems"}

    mode = str(args.get("mode") or "copy").strip().lower()
    if mode not in ("copy", "move"):
        mode = "copy"

    os.makedirs(os.path.dirname(_import_log_path(basepath)), exist_ok=True)

    imported_urls = _load_imported_urls(basepath)

    out_items: List[Dict[str, Any]] = []
    imported = 0
    skipped = 0
    failed = 0

    for it in items:
        try:
            feed_id = str(it.get("feed_id") or it.get("feedid") or it.get("feedId") or "").strip()
            article_id = str(it.get("article_id") or it.get("articleid") or it.get("articleId") or "").strip()
            url = str(it.get("url") or it.get("link") or "").strip()

            if not feed_id or not article_id:
                failed += 1
                out_items.append({"status": "failed", "reason": "missing feed_id/article_id", "item": it})
                continue

            if url and url in imported_urls:
                skipped += 1
                out_items.append({"status": "skipped", "reason": "url already imported", "url": url, "item": it})
                continue

            src_md = _article_content_md(basepath, feed_id, article_id)
            if not os.path.exists(src_md):
                failed += 1
                out_items.append({"status": "failed", "reason": "content.md not found", "url": url, "item": it})
                continue

            target_dir = os.path.join(basepath, "uploadsweb", "rss_gate")
            os.makedirs(target_dir, exist_ok=True)

            fname = _safe_filename(url or f"{feed_id}/{article_id}")
            dst_abs = os.path.join(target_dir, fname)
            shutil.copyfile(src_md, dst_abs)

            sourcepath_rel = os.path.join("uploadsweb", "rss_gate", fname)

            # ✅ 修复：移除 basepath 参数，fs_send_to_library_core 只需要 userid
            try:
                res = fs_send_to_library_core(
                    userid=uid,
                    sourcepath=sourcepath_rel,
                    libraryid=target_library_id,
                    mode=mode,
                )
            except TypeError as e:
                # 兼容：如果还是报错，尝试不传 mode
                if "mode" in str(e):
                    res = fs_send_to_library_core(
                        userid=uid,
                        sourcepath=sourcepath_rel,
                        libraryid=target_library_id,
                    )
                else:
                    raise

            status = str(res.get("status") or "").lower()
            is_success = (status == "success") or (res.get("success") is True)

            if not is_success:
                failed += 1
                out_items.append(
                    {
                        "status": "failed",
                        "reason": res.get("message") or res.get("detail") or "send_to_library failed",
                        "url": url,
                        "raw": res,
                        "item": it,
                    }
                )
                continue

            imported += 1
            if url:
                imported_urls.add(url)

            append_jsonl(
                _import_log_path(basepath),
                {
                    "ts": _utc_iso(),
                    "type": "rss_gate_import",
                    "url": url,
                    "feed_id": feed_id,
                    "article_id": article_id,
                    "library_id": target_library_id,
                },
            )

            out_items.append({"status": "imported", "url": url, "raw": res, "item": it})

        except Exception as e:
            failed += 1
            out_items.append({"status": "failed", "reason": str(e), "item": it})

    return {
        "success": True,
        "library_id": target_library_id,
        "imported": imported,
        "skipped": skipped,
        "failed": failed,
        "total": len(items),
        "stats": {"imported": imported, "skipped": skipped, "failed": failed, "total": len(items)},
        "items": out_items,
    }
