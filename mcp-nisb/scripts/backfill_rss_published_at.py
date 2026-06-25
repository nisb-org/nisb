#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional, Tuple


_PUBLISHED_LINE_RE = re.compile(r"(?im)^\s*Published\s*:\s*(.+?)\s*$")
_RSS_IMPORT_NAME_RE = re.compile(r"(?i)\brss_import_([a-z0-9_-]+)\b")


def _atomic_write_json(path: Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(str(tmp), str(path))


def _parse_dt_any(s: Any) -> Optional[datetime]:
    if s is None:
        return None
    if isinstance(s, (int, float)):
        try:
            v = float(s)
            if v > 1e12:
                v = v / 1000.0
            return datetime.fromtimestamp(v, tz=timezone.utc).astimezone(timezone.utc)
        except Exception:
            return None

    x = str(s or "").strip()
    if not x:
        return None

    # ISO8601
    try:
        y = x.replace("Z", "+00:00")
        dt = datetime.fromisoformat(y)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        pass

    # RFC822 (RSS pubDate)
    try:
        import email.utils

        dt2 = email.utils.parsedate_to_datetime(x)
        if dt2 is None:
            return None
        if dt2.tzinfo is None:
            dt2 = dt2.replace(tzinfo=timezone.utc)
        return dt2.astimezone(timezone.utc)
    except Exception:
        pass

    # Common formats
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y/%m/%d %H:%M:%S", "%Y-%m-%d", "%Y/%m/%d"):
        try:
            dt3 = datetime.strptime(x, fmt).replace(tzinfo=timezone.utc)
            return dt3.astimezone(timezone.utc)
        except Exception:
            continue

    return None


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat()


def _read_text_head(p: Path, max_chars: int = 12000) -> str:
    try:
        return p.read_text(encoding="utf-8", errors="ignore")[:max_chars]
    except Exception:
        return ""


def _extract_published_from_content(doc_dir: Path) -> Optional[datetime]:
    # NISB 文档契约通常是 content.txt，但 RSS 也可能是 content.md
    for name in ("content.txt", "content.md", "content.mdx"):
        p = doc_dir / name
        if not p.exists():
            continue
        head = _read_text_head(p)
        m = _PUBLISHED_LINE_RE.search(head)
        if not m:
            continue
        return _parse_dt_any(m.group(1))
    return None


def _infer_article_id_from_filename(filename: str) -> Optional[str]:
    fn = str(filename or "").strip()
    if not fn:
        return None
    m = _RSS_IMPORT_NAME_RE.search(fn)
    if not m:
        return None
    return m.group(1).strip() or None


def _read_rss_meta(user_base: Path, feed_id: Optional[str], article_id: Optional[str]) -> Dict[str, Any]:
    if not feed_id or not article_id:
        return {}
    p = user_base / "rss" / "feeds" / feed_id / "articles" / article_id / "meta.json"
    if not p.exists():
        return {}
    try:
        obj = json.loads(p.read_text(encoding="utf-8"))
        return obj if isinstance(obj, dict) else {}
    except Exception:
        return {}


def _pick_feed_id_from_library(library_id: str) -> Optional[str]:
    # 你的日志里 feed_id 是 '9131d75918d7'；这里无法从库名可靠推断
    # 因此 backfill 默认不强推 feed_id，除非你显式传入 --feed_id
    _ = library_id
    return None


def _update_doc_metadata(
    user_base: Path,
    library_id: str,
    doc_dir: Path,
    *,
    feed_id: Optional[str],
) -> Tuple[bool, str]:
    mp = doc_dir / "metadata.json"
    if not mp.exists():
        return False, "metadata_missing"

    try:
        md = json.loads(mp.read_text(encoding="utf-8"))
        if not isinstance(md, dict):
            return False, "metadata_not_object"
    except Exception:
        return False, "metadata_parse_failed"

    if str(md.get("published_at") or "").strip():
        return False, "already_has_published_at"

    filename = str(md.get("filename") or "").strip()
    article_id = _infer_article_id_from_filename(filename)
    rss_meta = _read_rss_meta(user_base, feed_id, article_id)

    dt = None
    # 1) RSS meta 优先（若提供）
    for key in ("published_at", "published", "pubDate", "date"):
        if dt is None and rss_meta.get(key) is not None:
            dt = _parse_dt_any(rss_meta.get(key))

    # 2) 否则从 content 头部解析
    if dt is None:
        dt = _extract_published_from_content(doc_dir)

    if dt is None:
        return False, "published_at_not_found"

    md["published_at"] = _iso(dt)
    md["source"] = md.get("source") or "rss_import"
    md["library_id"] = md.get("library_id") or library_id

    rss_obj = md.get("rss")
    if not isinstance(rss_obj, dict):
        rss_obj = {}
    if feed_id:
        rss_obj["feed_id"] = rss_obj.get("feed_id") or feed_id
    if article_id:
        rss_obj["article_id"] = rss_obj.get("article_id") or article_id
    if isinstance(rss_meta, dict) and rss_meta.get("url"):
        rss_obj["url"] = rss_obj.get("url") or rss_meta.get("url")
    rss_obj["published_at"] = rss_obj.get("published_at") or md["published_at"]
    md["rss"] = rss_obj

    _atomic_write_json(mp, md)
    return True, "updated"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--uid", required=True, help="用户 uid（对应 /data/users/{uid}/ ）")
    ap.add_argument("--library_id", required=True, help="库 id（对应 /data/users/{uid}/libraries/{library_id}/ ）")
    ap.add_argument("--feed_id", default="", help="可选：RSS feed_id（用于从 /rss/feeds/{feed_id}/articles/*/meta.json 取 published_at）")
    ap.add_argument("--limit", type=int, default=0, help="可选：最多处理多少个 doc（0=不限制）")
    args = ap.parse_args()

    uid = str(args.uid).strip()
    library_id = str(args.library_id).strip()
    feed_id = str(args.feed_id or "").strip() or None
    limit = int(args.limit or 0)

    user_base = Path("/data/users") / uid
    lib_dir = user_base / "libraries" / library_id
    docs_dir = lib_dir / "docs"

    if not user_base.exists():
        raise SystemExit(f"user_base not found: {user_base}")
    if not lib_dir.exists():
        raise SystemExit(f"library not found: {lib_dir}")
    if not docs_dir.exists():
        raise SystemExit(f"docs dir not found: {docs_dir}")

    if not feed_id:
        feed_id = _pick_feed_id_from_library(library_id)

    total = 0
    updated = 0
    skipped = 0
    failed = 0

    for doc_folder in sorted(docs_dir.iterdir()):
        if not doc_folder.is_dir():
            continue
        if not doc_folder.name.startswith("doc_"):
            continue

        total += 1
        ok, reason = _update_doc_metadata(user_base, library_id, doc_folder, feed_id=feed_id)
        if ok:
            updated += 1
        else:
            if reason in ("already_has_published_at", "metadata_missing", "metadata_not_object"):
                skipped += 1
            else:
                failed += 1

        if limit > 0 and total >= limit:
            break

    print(json.dumps({
        "status": "success",
        "uid": uid,
        "library_id": library_id,
        "feed_id": feed_id or "",
        "total_scanned": total,
        "updated": updated,
        "skipped": skipped,
        "failed": failed,
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

