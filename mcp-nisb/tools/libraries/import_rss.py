from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple


def _utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_filename(seed: str) -> str:
    h = hashlib.sha256((seed or "").encode("utf-8")).hexdigest()[:16]
    return f"rss_import_{h}.md"


def _pick_str(d: Dict[str, Any], *keys: str, default: str = "") -> str:
    for k in keys:
        if k not in d:
            continue
        v = d.get(k)
        if v is None:
            continue
        s = str(v).strip()
        if s:
            return s
    return default


def _infer_userid_from_basepath(basepath: str) -> str:
    try:
        parts = (basepath or "").strip("/").split("/")
        if len(parts) >= 3 and parts[-2] == "users":
            return parts[-1]
    except Exception:
        pass
    return ""


def _get_basepath(args: Dict[str, Any]) -> str:
    return str(args.get("basepath") or args.get("base_path") or "").strip()


def _get_userid(args: Dict[str, Any], basepath: str) -> str:
    uid = _pick_str(args, "user_id", "userid", "uid")
    if uid:
        return uid
    return _infer_userid_from_basepath(basepath)


def _article_content_md_path(basepath: str, feed_id: str, article_id: str) -> str:
    return os.path.join(basepath, "rss", "feeds", feed_id, "articles", article_id, "content.md")


def _article_meta_json_path(basepath: str, feed_id: str, article_id: str) -> str:
    return os.path.join(basepath, "rss", "feeds", feed_id, "articles", article_id, "meta.json")


def _normalize_url_for_dedupe(url: str) -> str:
    u = str(url or "").strip()
    if not u:
        return ""
    u = u.split("#")[0]
    if len(u) > 1 and u.endswith("/"):
        u = u[:-1]
    return u


def _atomic_write_json(path: str, data: Dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix="tmp_", suffix=".json", dir=os.path.dirname(path))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, path)
    finally:
        try:
            if os.path.exists(tmp):
                os.remove(tmp)
        except Exception:
            pass


def _load_json_file(path: str) -> Dict[str, Any]:
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            obj = json.load(f)
        return obj if isinstance(obj, dict) else {}
    except Exception:
        return {}


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

    try:
        y = x.replace("Z", "+00:00")
        dt = datetime.fromisoformat(y)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        pass

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

    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y/%m/%d %H:%M:%S", "%Y-%m-%d", "%Y/%m/%d"):
        try:
            dt3 = datetime.strptime(x, fmt).replace(tzinfo=timezone.utc)
            return dt3.astimezone(timezone.utc)
        except Exception:
            continue

    return None


def _normalize_iso_or_none(v: Any) -> str:
    dt = _parse_dt_any(v)
    if dt is not None:
        return dt.astimezone(timezone.utc).isoformat()
    s = str(v or "").strip()
    return s if s else ""


def _pick_published_at_from_rss_meta(meta: Dict[str, Any]) -> str:
    if not isinstance(meta, dict):
        return ""
    for k in ("published_at", "publishedAt", "published", "pubDate", "date", "updated_at", "updatedAt", "updated"):
        dt = _parse_dt_any(meta.get(k))
        if dt is not None:
            return dt.astimezone(timezone.utc).isoformat()
    return ""


def _library_docs_dir(basepath: str, library_id: str) -> str:
    return os.path.join(basepath, "libraries", library_id, "docs")


def _doc_dir_from_res(basepath: str, library_id: str, res: Dict[str, Any]) -> Optional[str]:
    if not isinstance(res, dict):
        return None

    for k in ("doc_dir", "docdir", "doc_path", "docpath"):
        p = str(res.get(k) or "").strip()
        if p and os.path.isabs(p) and os.path.exists(p):
            return p

    doc_id = str(res.get("doc_id") or res.get("docid") or "").strip()
    if doc_id:
        p2 = os.path.join(_library_docs_dir(basepath, library_id), doc_id)
        if os.path.exists(p2):
            return p2

    return None


def _find_doc_dir_by_filename(basepath: str, library_id: str, filename: str, max_scan: int = 400) -> Optional[str]:
    fn = str(filename or "").strip()
    if not fn:
        return None

    docs_dir = _library_docs_dir(basepath, library_id)
    if not os.path.exists(docs_dir):
        return None

    entries: List[Tuple[float, str]] = []
    try:
        with os.scandir(docs_dir) as it:
            for e in it:
                if not e.is_dir():
                    continue
                name = e.name
                if not name.startswith("doc_"):
                    continue
                try:
                    st = e.stat()
                    entries.append((float(st.st_mtime), e.path))
                except Exception:
                    continue
    except Exception:
        return None

    entries.sort(key=lambda x: x[0], reverse=True)
    for _, p in entries[: max(1, int(max_scan))]:
        mp = os.path.join(p, "metadata.json")
        md = _load_json_file(mp)
        if not isinstance(md, dict):
            continue
        if str(md.get("filename") or "").strip() == fn:
            return p

    return None


def _patch_doc_metadata(
    basepath: str,
    library_id: str,
    doc_dir: str,
    *,
    feed_id: str,
    article_id: str,
    url: str,
    title: str,
    published_at: str,
    overwrite_published_at: bool,
) -> Tuple[bool, str]:
    mp = os.path.join(doc_dir, "metadata.json")
    if not os.path.exists(mp):
        return False, f"metadata.json not found: {mp}"

    md = _load_json_file(mp)
    if not isinstance(md, dict):
        return False, "metadata.json invalid"

    changed = False

    if not str(md.get("library_id") or "").strip():
        md["library_id"] = library_id
        changed = True

    cur_pub = str(md.get("published_at") or "").strip()
    rss_pub = _normalize_iso_or_none(published_at)
    fallback_pub = _normalize_iso_or_none(md.get("uploaded_at"))

    next_pub = rss_pub or fallback_pub

    if next_pub:
        should_set_pub = False

        if rss_pub:
            if cur_pub != rss_pub:
                should_set_pub = True
        else:
            if overwrite_published_at or (not cur_pub):
                if cur_pub != next_pub:
                    should_set_pub = True

        if should_set_pub:
            md["published_at"] = next_pub
            changed = True

    if not str(md.get("source") or "").strip():
        md["source"] = "rss_import"
        changed = True

    rss_obj = md.get("rss")
    if not isinstance(rss_obj, dict):
        rss_obj = {}
        md["rss"] = rss_obj
        changed = True

    if feed_id and str(rss_obj.get("feed_id") or "").strip() != feed_id:
        rss_obj["feed_id"] = feed_id
        changed = True
    if article_id and str(rss_obj.get("article_id") or "").strip() != article_id:
        rss_obj["article_id"] = article_id
        changed = True
    if url and str(rss_obj.get("url") or "").strip() != url:
        rss_obj["url"] = url
        changed = True
    if title and str(rss_obj.get("title") or "").strip() != title:
        rss_obj["title"] = title
        changed = True
    if rss_pub and str(rss_obj.get("published_at") or "").strip() != rss_pub:
        rss_obj["published_at"] = rss_pub
        changed = True

    rss_obj["imported_at"] = rss_obj.get("imported_at") or _utc_iso()

    if not changed:
        return True, "no_change"

    _atomic_write_json(mp, md)
    return True, "updated"

def _read_effective_doc_published_at(doc_dir: str) -> str:
    md = _load_json_file(os.path.join(doc_dir, "metadata.json"))
    if not isinstance(md, dict):
        return ""
    return (
        _normalize_iso_or_none(md.get("published_at"))
        or _normalize_iso_or_none(md.get("uploaded_at"))
        or ""
    )


def _sync_sqlite_published_at(basepath: str, library_id: str, doc_dir: str) -> Tuple[bool, str]:
    try:
        from tools.doc.doc_db_sqlite import get_doc_db_sqlite
    except Exception as e:
        return False, f"import get_doc_db_sqlite failed: {e}"

    doc_id = os.path.basename(str(doc_dir or "").rstrip("/"))
    if not doc_id:
        return False, "missing_doc_id_from_doc_dir"

    effective_published_at = _read_effective_doc_published_at(doc_dir)
    if not effective_published_at:
        return False, "effective_published_at_empty"

    try:
        db = get_doc_db_sqlite(basepath, library_id)
        res = db.update_document_published_at(doc_id, effective_published_at)
        if not bool(res.get("ok")):
            return False, str(res.get("reason") or res.get("error") or "sqlite_update_failed")
        return True, str(res.get("reason") or "updated")
    except Exception as e:
        return False, f"sqlite_update_exception: {e}"


def nisb_library_import_rss(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Import RSS articles into a library.

    This function keeps the existing Library import payload unchanged. When
    include_items is true, it also returns compact per-item results so callers
    can make URL-level decisions without guessing from aggregate counters.
    """
    basepath = _get_basepath(args)
    if not basepath:
        return {"success": False, "status": "error", "message": "missing basepath (injected)"}

    user_id = _get_userid(args, basepath)
    if not user_id:
        return {"success": False, "status": "error", "message": "missing user_id/userid (and cannot infer from basepath)"}

    library_id = _pick_str(args, "library_id", "libraryid")
    if not library_id:
        return {"success": False, "status": "error", "message": "missing library_id"}

    items = args.get("items")
    if not isinstance(items, list):
        items = args.get("rssitems")
    if not isinstance(items, list) or not items:
        return {"success": False, "status": "error", "message": "missing items"}

    mode = str(args.get("mode") or "copy").strip().lower()
    if mode not in ("copy", "move"):
        mode = "copy"

    dedupe_by_url = bool(args.get("dedupe_by_url", True))

    try:
        max_items = int(args.get("max_items", 5000))
    except Exception:
        max_items = 5000
    max_items = max(1, min(20000, max_items))

    overwrite_published_at = bool(args.get("overwrite_published_at") or False)
    include_items = bool(args.get("include_items") or False)

    from tools.filesystem.send_to_library_core import fs_send_to_library_core

    imported = 0
    skipped = 0
    failed = 0
    failures: List[Dict[str, Any]] = []
    warnings: List[Dict[str, Any]] = []
    item_results: List[Dict[str, Any]] = []

    meta_updated = 0
    meta_nochange = 0
    meta_failed = 0

    sqlite_updated = 0
    sqlite_nochange = 0
    sqlite_failed = 0

    seen_keys: set[Tuple[str, str]] = set()
    seen_urls: set[str] = set()

    target_dir_abs = os.path.join(basepath, "uploadsweb", "rss_import")
    os.makedirs(target_dir_abs, exist_ok=True)

    def _add_item_result(status: str, feed_id: str, article_id: str, raw_url: str, reason: str = "", doc_id: str = "") -> None:
        if not include_items:
            return
        item_results.append({
            "status": status,
            "feed_id": feed_id,
            "article_id": article_id,
            "url": _normalize_url_for_dedupe(raw_url) or raw_url,
            "doc_id": doc_id,
            "reason": str(reason or "")[:500],
        })

    for raw in items[:max_items]:
        it = dict(raw or {})

        feed_id = _pick_str(it, "feed_id", "feedid")
        article_id = _pick_str(it, "article_id", "articleid")
        raw_url = _pick_str(it, "url", "link")
        url = _normalize_url_for_dedupe(raw_url)
        title = _pick_str(it, "title", "name")

        if not feed_id or not article_id:
            failed += 1
            reason = "missing feed_id/article_id"
            failures.append({"feed_id": feed_id, "article_id": article_id, "url": raw_url, "reason": reason})
            _add_item_result("failed", feed_id, article_id, raw_url, reason)
            continue

        k = (feed_id, article_id)
        if k in seen_keys:
            skipped += 1
            _add_item_result("skipped", feed_id, article_id, raw_url, "duplicate feed_id/article_id in batch")
            continue
        seen_keys.add(k)

        if dedupe_by_url and url:
            if url in seen_urls:
                skipped += 1
                _add_item_result("skipped", feed_id, article_id, raw_url, "duplicate url in batch")
                continue
            seen_urls.add(url)

        src_md = _article_content_md_path(basepath, feed_id, article_id)
        if not os.path.exists(src_md):
            failed += 1
            reason = f"content.md not found: {src_md}"
            failures.append({"feed_id": feed_id, "article_id": article_id, "url": raw_url, "reason": reason})
            _add_item_result("failed", feed_id, article_id, raw_url, reason)
            continue

        rss_meta = _load_json_file(_article_meta_json_path(basepath, feed_id, article_id))
        published_at = _pick_published_at_from_rss_meta(rss_meta)

        seed = url or raw_url or f"{feed_id}/{article_id}/{title}"
        fname = _safe_filename(seed)
        dst_abs = os.path.join(target_dir_abs, fname)

        try:
            shutil.copyfile(src_md, dst_abs)
        except Exception as e:
            failed += 1
            reason = f"copy failed: {e}"
            failures.append({"feed_id": feed_id, "article_id": article_id, "url": raw_url, "reason": reason})
            _add_item_result("failed", feed_id, article_id, raw_url, reason)
            continue

        source_path = os.path.join("uploadsweb", "rss_import", fname)

        try:
            res = fs_send_to_library_core(
                base_path=basepath,
                user_id=user_id,
                source_path=source_path,
                library_id=library_id,
                mode=mode,
            )
        except Exception as e:
            failed += 1
            reason = f"send_to_library exception: {e}"
            failures.append({"feed_id": feed_id, "article_id": article_id, "url": raw_url, "reason": reason})
            _add_item_result("failed", feed_id, article_id, raw_url, reason)
            continue

        status = str((res or {}).get("status") or "").lower()
        ok = (status == "success") or (status == "warning")
        if not ok:
            failed += 1
            reason = str((res or {}).get("message") or "send_to_library failed")
            failures.append({
                "feed_id": feed_id,
                "article_id": article_id,
                "url": raw_url,
                "reason": reason,
            })
            _add_item_result("failed", feed_id, article_id, raw_url, reason)
            continue

        imported += 1

        doc_dir = _doc_dir_from_res(basepath, library_id, res if isinstance(res, dict) else {})
        if not doc_dir:
            doc_dir = _find_doc_dir_by_filename(basepath, library_id, filename=fname, max_scan=400)

        doc_id = os.path.basename(str(doc_dir or "").rstrip("/")) if doc_dir else ""
        item_warnings: List[str] = []

        if not doc_dir:
            meta_failed += 1
            sqlite_failed += 1
            item_warnings.append("import ok but cannot locate doc_dir to patch metadata/sqlite")
            warnings.append({
                "feed_id": feed_id,
                "article_id": article_id,
                "url": raw_url,
                "reason": item_warnings[-1],
            })
            _add_item_result("imported_warning", feed_id, article_id, url or raw_url, "; ".join(item_warnings), doc_id)
            continue

        ok2, reason2 = _patch_doc_metadata(
            basepath=basepath,
            library_id=library_id,
            doc_dir=doc_dir,
            feed_id=feed_id,
            article_id=article_id,
            url=url or raw_url,
            title=title,
            published_at=published_at,
            overwrite_published_at=overwrite_published_at,
        )

        if ok2 and reason2 == "updated":
            meta_updated += 1
        elif ok2 and reason2 == "no_change":
            meta_nochange += 1
        else:
            meta_failed += 1
            item_warnings.append(f"patch metadata failed: {reason2}")
            warnings.append({
                "feed_id": feed_id,
                "article_id": article_id,
                "url": raw_url,
                "reason": item_warnings[-1],
            })

        ok3, reason3 = _sync_sqlite_published_at(
            basepath=basepath,
            library_id=library_id,
            doc_dir=doc_dir,
        )
        if ok3 and reason3 == "updated":
            sqlite_updated += 1
        elif ok3 and reason3 == "no_change":
            sqlite_nochange += 1
        else:
            sqlite_failed += 1
            item_warnings.append(f"sync sqlite published_at failed: {reason3}")
            warnings.append({
                "feed_id": feed_id,
                "article_id": article_id,
                "url": raw_url,
                "reason": item_warnings[-1],
            })

        if item_warnings:
            _add_item_result("imported_warning", feed_id, article_id, url or raw_url, "; ".join(item_warnings), doc_id)
        else:
            _add_item_result("imported", feed_id, article_id, url or raw_url, "", doc_id)

    warning_count = len(warnings)
    if failed == 0 and warning_count == 0:
        final_status = "success"
    elif imported > 0:
        final_status = "warning"
    else:
        final_status = "error"

    out = {
        "success": final_status in ("success", "warning"),
        "status": final_status,
        "message": f"library {library_id}: imported {imported}, skipped {skipped}, failed {failed}",
        "library_id": library_id,
        "imported": imported,
        "skipped": skipped,
        "failed": failed,
        "failures": failures[:50],
        "warnings": warnings[:50],
        "meta_patch": {
            "updated": meta_updated,
            "no_change": meta_nochange,
            "failed": meta_failed,
        },
        "sqlite_patch": {
            "updated": sqlite_updated,
            "no_change": sqlite_nochange,
            "failed": sqlite_failed,
        },
        "ts": _utc_iso(),
    }

    if include_items:
        out["items"] = item_results[:max_items]

    return out
