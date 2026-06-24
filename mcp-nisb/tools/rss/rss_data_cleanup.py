# /opt/mcp-gateway/mcp-nisb/tools/rss/rss_data_cleanup.py
from __future__ import annotations

import json
import os
import shutil
import time
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, Iterator, List, Optional, Set, Tuple

from tools.doc.core.dod_guard import require_safe_id

from .semantic_index import _hash_vec, _tokenize
from .tools import _rss_root, _feed_articles_jsonl, _feed_states_jsonl, _article_dir, _article_meta_json, _article_content_md

try:
    from .cache_control import nisb_rss_cache_clear  # best effort
except Exception:
    nisb_rss_cache_clear = None


def _utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _get_basepath_strict(args: Dict[str, Any]) -> str:
    bp = str(args.get("basepath") or "").strip()
    if not bp:
        raise ValueError("missing injected basepath in tool args")
    return bp


def _uid_from_basepath(basepath: str) -> str:
    bp = str(basepath or "").rstrip("/")
    uid = bp.split("/")[-1] if bp else ""
    if not uid:
        raise ValueError("cannot resolve uid from basepath")
    return uid


def _safe_feed_id(feed_id: str) -> str:
    return require_safe_id("feed_id", str(feed_id or "").strip())


def _safe_article_id(article_id: str) -> str:
    return require_safe_id("article_id", str(article_id or "").strip())


def _parse_ts_any(v: Any) -> Optional[float]:
    s = str(v or "").strip()
    if not s:
        return None
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return float(dt.timestamp())
    except Exception:
        pass
    try:
        x = float(s)
        if x > 10_000_000_000:
            x = x / 1000.0
        return float(x)
    except Exception:
        return None


def _article_ts_from_meta(meta: Dict[str, Any]) -> Optional[float]:
    return _parse_ts_any(meta.get("published_at")) or _parse_ts_any(meta.get("fetched_at"))


def _iter_jsonl_lines(path: str) -> Iterator[Dict[str, Any]]:
    if not path or not os.path.exists(path):
        return
        yield  # pragma: no cover
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                s = line.strip()
                if not s:
                    continue
                try:
                    obj = json.loads(s)
                except Exception:
                    continue
                if isinstance(obj, dict):
                    yield obj
    except Exception:
        return


def _atomic_write_jsonl(path: str, rows: Iterable[Dict[str, Any]]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = f"{path}.tmp.{int(time.time() * 1000)}"
    with open(tmp, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    os.replace(tmp, path)


def _dir_size_bytes(root: str) -> int:
    total = 0
    if not root or not os.path.exists(root):
        return 0
    for base, _dirs, files in os.walk(root):
        for fn in files:
            p = os.path.join(base, fn)
            try:
                total += int(os.path.getsize(p))
            except Exception:
                continue
    return int(total)


def _count_tree(root: str) -> Tuple[int, int]:
    files = 0
    dirs = 0
    if not root or not os.path.exists(root):
        return (0, 0)
    for _base, subdirs, fns in os.walk(root):
        dirs += len(subdirs)
        files += len(fns)
    return (files, dirs)


def _compact_articles_jsonl(
    basepath: str,
    feed_id: str,
    kept_ids: Set[str],
    *,
    dry_run: bool,
    warnings: List[str],
) -> Dict[str, Any]:
    apath = _feed_articles_jsonl(basepath, feed_id)
    if not os.path.exists(apath):
        return {"compacted": False, "kept": 0, "dropped": 0}

    latest: Dict[str, Dict[str, Any]] = {}
    dropped_lines = 0

    for row in _iter_jsonl_lines(apath):
        aid = str(row.get("article_id") or "").strip()
        if not aid:
            dropped_lines += 1
            continue
        try:
            aid = _safe_article_id(aid)
        except Exception:
            dropped_lines += 1
            continue

        if aid not in kept_ids:
            dropped_lines += 1
            continue

        ts = _parse_ts_any(row.get("published_at")) or _parse_ts_any(row.get("ts")) or _parse_ts_any(row.get("fetched_at")) or 0.0
        prev = latest.get(aid)
        prev_ts = (
            _parse_ts_any(prev.get("published_at")) or _parse_ts_any(prev.get("ts")) or _parse_ts_any(prev.get("fetched_at")) or 0.0
            if isinstance(prev, dict)
            else 0.0
        )
        if prev is None or float(ts) >= float(prev_ts):
            latest[aid] = row

    out_rows = list(latest.values())
    out_rows.sort(
        key=lambda r: float(_parse_ts_any(r.get("published_at")) or _parse_ts_any(r.get("ts")) or _parse_ts_any(r.get("fetched_at")) or 0.0)
    )

    if not dry_run:
        try:
            _atomic_write_jsonl(apath, out_rows)
        except Exception as e:
            warnings.append(f"articles.jsonl compact failed feed_id={feed_id}: {e!r}")
            return {"compacted": False, "kept": len(out_rows), "dropped": dropped_lines}

    return {"compacted": True, "kept": len(out_rows), "dropped": dropped_lines}


def _compact_states_jsonl(
    basepath: str,
    feed_id: str,
    kept_ids: Set[str],
    *,
    dry_run: bool,
    warnings: List[str],
) -> Dict[str, Any]:
    spath = _feed_states_jsonl(basepath, feed_id)
    if not os.path.exists(spath):
        return {"compacted": False, "kept": 0, "dropped": 0}

    last: Dict[Tuple[str, str], Dict[str, Any]] = {}
    dropped = 0

    for row in _iter_jsonl_lines(spath):
        aid = str(row.get("article_id") or "").strip()
        st = str(row.get("state") or "").strip()
        if not aid or not st:
            dropped += 1
            continue
        try:
            aid = _safe_article_id(aid)
        except Exception:
            dropped += 1
            continue
        if aid not in kept_ids:
            dropped += 1
            continue
        if st not in ("read", "starred", "archived", "deleted"):
            dropped += 1
            continue
        last[(aid, st)] = row

    out_rows: List[Dict[str, Any]] = []
    for (aid, st), r in last.items():
        out_rows.append(
            {
                "ts": str(r.get("ts") or _utc_iso()),
                "feed_id": feed_id,
                "article_id": aid,
                "state": st,
                "value": bool(r.get("value", True)),
            }
        )

    if not dry_run:
        try:
            _atomic_write_jsonl(spath, out_rows)
        except Exception as e:
            warnings.append(f"states.jsonl compact failed feed_id={feed_id}: {e!r}")
            return {"compacted": False, "kept": len(out_rows), "dropped": dropped}

    return {"compacted": True, "kept": len(out_rows), "dropped": dropped}


def _rebuild_embeddings_streaming(
    basepath: str,
    *,
    kept_by_feed: Dict[str, Set[str]],
    cutoff_ts: float,
    dry_run: bool,
    warnings: List[str],
) -> Dict[str, Any]:
    idx_path = os.path.join(_rss_root(basepath), "embeddings.jsonl")

    if dry_run:
        est = 0
        for _fid, ids in kept_by_feed.items():
            est += len(ids)
        return {"done": False, "count": est, "index_path": idx_path, "message": "dry_run: rebuild skipped"}

    os.makedirs(os.path.dirname(idx_path), exist_ok=True)
    tmp = f"{idx_path}.tmp.{int(time.time() * 1000)}"

    wrote = 0
    try:
        with open(tmp, "w", encoding="utf-8") as wf:
            for feed_id, aids in kept_by_feed.items():
                if not aids:
                    continue
                for aid in aids:
                    adir = _article_dir(basepath, feed_id, aid)
                    meta_p = _article_meta_json(basepath, feed_id, aid)
                    md_p = _article_content_md(basepath, feed_id, aid)
                    if not os.path.exists(adir) or not os.path.exists(meta_p) or not os.path.exists(md_p):
                        continue

                    meta: Dict[str, Any] = {}
                    try:
                        with open(meta_p, "r", encoding="utf-8") as f:
                            meta = json.load(f)
                        if not isinstance(meta, dict):
                            meta = {}
                    except Exception:
                        meta = {}

                    ts = _article_ts_from_meta(meta)
                    if ts is None:
                        continue
                    if float(ts) < float(cutoff_ts):
                        continue

                    title = str(meta.get("title") or "").strip()
                    url = str(meta.get("link") or meta.get("url") or "").strip()
                    published_at = str(meta.get("published_at") or "").strip()
                    fetched_at = str(meta.get("fetched_at") or "").strip()
                    if not url:
                        continue

                    try:
                        with open(md_p, "r", encoding="utf-8") as rf:
                            content_md = (rf.read() or "").strip()
                    except Exception:
                        content_md = ""

                    text_body = content_md.strip()
                    if len(text_body) > 2000:
                        text_body = text_body[:2000]
                    text = (title + "\n" + text_body).strip()

                    emb = _hash_vec(_tokenize(text), dim=512)

                    row = {
                        "id": aid,
                        "feed_id": feed_id,
                        "title": title,
                        "url": url,
                        "published_at": published_at or fetched_at or _utc_iso(),
                        "fetched_at": fetched_at or _utc_iso(),
                        "embedding": emb,
                        "text": text,
                    }
                    wf.write(json.dumps(row, ensure_ascii=False) + "\n")
                    wrote += 1

        os.replace(tmp, idx_path)
        return {"done": True, "count": wrote, "index_path": idx_path, "message": "rebuilt streaming"}
    except Exception as e:
        warnings.append(f"rebuild embeddings failed: {e!r}")
        try:
            if os.path.exists(tmp):
                os.remove(tmp)
        except Exception:
            pass
        return {"done": False, "count": wrote, "index_path": idx_path, "message": f"failed: {e!r}"}


def _cleanup_auto_import_logs(rss_dir: str, *, cutoff_ts: float, dry_run: bool) -> Dict[str, Any]:
    logs_dir = os.path.join(rss_dir, "auto_import_logs")
    if not os.path.isdir(logs_dir):
        return {"deleted_files": 0, "deleted_bytes": 0}

    deleted_files = 0
    deleted_bytes = 0
    for fn in os.listdir(logs_dir):
        p = os.path.join(logs_dir, fn)
        if not os.path.isfile(p):
            continue
        try:
            mt = float(os.path.getmtime(p))
        except Exception:
            mt = 0.0
        if mt <= 0.0:
            continue
        if mt < float(cutoff_ts):
            try:
                sz = int(os.path.getsize(p))
            except Exception:
                sz = 0
            if not dry_run:
                try:
                    os.remove(p)
                except Exception:
                    continue
            deleted_files += 1
            deleted_bytes += max(0, sz)
    return {"deleted_files": deleted_files, "deleted_bytes": deleted_bytes}


def nisb_rss_data_cleanup(args: Dict[str, Any]) -> Dict[str, Any]:
    basepath = _get_basepath_strict(args)
    _uid = _uid_from_basepath(basepath)
    rss_dir = _rss_root(basepath)

    keep_days_raw = args.get("keep_days", None)
    if keep_days_raw is None:
        return {"success": False, "message": "missing keep_days"}
    try:
        keep_days = int(keep_days_raw)
    except Exception:
        return {"success": False, "message": "keep_days must be int"}
    keep_days = max(1, min(365, keep_days))

    dry_run = bool(args.get("dry_run", False))
    rebuild_index = bool(args.get("rebuild_index", True))

    try:
        delete_logs_before_days = int(args.get("delete_logs_before_days", 0) or 0)
    except Exception:
        delete_logs_before_days = 0
    delete_logs_before_days = max(0, min(3650, delete_logs_before_days))

    warnings: List[str] = []

    before_bytes = _dir_size_bytes(rss_dir)
    before_files, before_dirs = _count_tree(rss_dir)

    now_ts = time.time()
    cutoff_ts = float(now_ts - (keep_days * 86400))

    feeds_dir = os.path.join(rss_dir, "feeds")
    deleted_dirs = 0
    deleted_bytes = 0

    compacted_jsonl_files: List[str] = []
    kept_lines_total = 0
    dropped_lines_total = 0

    kept_by_feed: Dict[str, Set[str]] = {}

    if os.path.isdir(feeds_dir):
        for feed_id_raw in os.listdir(feeds_dir):
            try:
                feed_id = _safe_feed_id(feed_id_raw)
            except Exception:
                warnings.append(f"skip invalid feed_id dir: {feed_id_raw!r}")
                continue

            fdir = os.path.join(feeds_dir, feed_id)
            if not os.path.isdir(fdir):
                continue

            ads_dir = os.path.join(fdir, "articles")
            kept_ids: Set[str] = set()

            if os.path.isdir(ads_dir):
                for aid_raw in os.listdir(ads_dir):
                    try:
                        aid = _safe_article_id(aid_raw)
                    except Exception:
                        warnings.append(f"skip invalid article_id dir feed_id={feed_id}: {aid_raw!r}")
                        continue

                    adir = os.path.join(ads_dir, aid)
                    if not os.path.isdir(adir):
                        continue

                    meta_p = _article_meta_json(basepath, feed_id, aid)
                    meta: Dict[str, Any] = {}
                    try:
                        if os.path.exists(meta_p):
                            with open(meta_p, "r", encoding="utf-8") as f:
                                meta = json.load(f)
                        if not isinstance(meta, dict):
                            meta = {}
                    except Exception:
                        meta = {}

                    ts = _article_ts_from_meta(meta) or 0.0

                    if float(ts) < float(cutoff_ts):
                        try:
                            sz = _dir_size_bytes(adir)
                        except Exception:
                            sz = 0
                        if not dry_run:
                            try:
                                shutil.rmtree(adir)
                            except Exception as e:
                                warnings.append(f"delete article dir failed feed_id={feed_id} article_id={aid}: {e!r}")
                                continue
                        deleted_dirs += 1
                        deleted_bytes += max(0, int(sz))
                    else:
                        md_p = _article_content_md(basepath, feed_id, aid)
                        if os.path.exists(md_p):
                            kept_ids.add(aid)

            kept_by_feed[feed_id] = kept_ids

            ares = _compact_articles_jsonl(basepath, feed_id, kept_ids, dry_run=dry_run, warnings=warnings)
            if bool(ares.get("compacted", False)) is True:
                compacted_jsonl_files.append(_feed_articles_jsonl(basepath, feed_id))
            kept_lines_total += int(ares.get("kept", 0) or 0)
            dropped_lines_total += int(ares.get("dropped", 0) or 0)

            sres = _compact_states_jsonl(basepath, feed_id, kept_ids, dry_run=dry_run, warnings=warnings)
            if bool(sres.get("compacted", False)) is True:
                compacted_jsonl_files.append(_feed_states_jsonl(basepath, feed_id))
            kept_lines_total += int(sres.get("kept", 0) or 0)
            dropped_lines_total += int(sres.get("dropped", 0) or 0)

    rebuild_index_done = False
    rebuild_index_message = ""

    if rebuild_index:
        rr = _rebuild_embeddings_streaming(
            basepath=basepath,
            kept_by_feed=kept_by_feed,
            cutoff_ts=cutoff_ts,
            dry_run=dry_run,
            warnings=warnings,
        )
        rebuild_index_done = bool(rr.get("done", False))
        rebuild_index_message = str(rr.get("message") or "")
    else:
        rebuild_index_done = True
        rebuild_index_message = "skip rebuild_index"

    logs_deleted = {"deleted_files": 0, "deleted_bytes": 0}
    if delete_logs_before_days > 0:
        logs_cutoff_ts = float(now_ts - (delete_logs_before_days * 86400))
        logs_deleted = _cleanup_auto_import_logs(rss_dir, cutoff_ts=logs_cutoff_ts, dry_run=dry_run)

    if nisb_rss_cache_clear is not None:
        try:
            nisb_rss_cache_clear({"uid": _uid, "gc_collect": True})
        except Exception:
            pass

    after_bytes = _dir_size_bytes(rss_dir)
    after_files, after_dirs = _count_tree(rss_dir)

    return {
        "success": True,
        "keep_days": keep_days,
        "dry_run": dry_run,
        "rebuild_index": rebuild_index,
        "delete_logs_before_days": delete_logs_before_days,
        "before_bytes": int(before_bytes),
        "after_bytes": int(after_bytes),
        "before_files": int(before_files),
        "before_dirs": int(before_dirs),
        "after_files": int(after_files),
        "after_dirs": int(after_dirs),
        "deleted_dirs": int(deleted_dirs),
        "deleted_bytes": int(deleted_bytes),
        "compacted_jsonl_files": compacted_jsonl_files,
        "kept_lines_total": int(kept_lines_total),
        "dropped_lines_total": int(dropped_lines_total),
        "rebuild_index_done": bool(rebuild_index_done),
        "rebuild_index_message": rebuild_index_message,
        "auto_import_logs_deleted_files": int(logs_deleted.get("deleted_files", 0) or 0),
        "auto_import_logs_deleted_bytes": int(logs_deleted.get("deleted_bytes", 0) or 0),
        "warnings": warnings,
        "ts": _utc_iso(),
    }

