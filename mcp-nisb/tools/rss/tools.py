# /opt/mcp-gateway/mcp-nisb/tools/rss/tools.py
from __future__ import annotations

import fcntl
import hashlib
import json
import os
import re
import shutil
import socket
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import feedparser  # pip: feedparser==6.0.10
from core.storage import load_json, append_jsonl, load_jsonl

from tools.doc.core.dod_guard import require_safe_id

# ✅ RSS 语义索引增量写入
from .semantic_index import upsert_one as _rss_index_upsert_one


# ---------------------------
# Utilities
# ---------------------------

def _utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha12(s: str) -> str:
    h = hashlib.sha256(s.encode("utf-8")).hexdigest()
    return h[:12]


def _safe_str(v: Any) -> str:
    return "" if v is None else str(v)


def _ensure_dir(p: str) -> None:
    os.makedirs(p, exist_ok=True)


def _atomic_write_json(path: str, data: Dict[str, Any]) -> None:
    _ensure_dir(os.path.dirname(path))
    tmp = f"{path}.tmp.{int(time.time() * 1000)}"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def _get_basepath(args: Dict[str, Any]) -> str:
    bp = args.get("basepath") or args.get("base_path") or args.get("basePath")
    bp = _safe_str(bp).strip()
    if not bp:
        raise ValueError("missing injected basepath in tool args")
    return bp


def _uid_from_basepath(basepath: str) -> str:
    bp = str(basepath or "").rstrip("/")
    return bp.split("/")[-1] if bp else ""


def _safe_feed_id(feed_id: str) -> str:
    return require_safe_id("feed_id", _safe_str(feed_id).strip())


def _safe_article_id(article_id: str) -> str:
    return require_safe_id("article_id", _safe_str(article_id).strip())


@contextmanager
def _socket_timeout(seconds: float):
    prev = socket.getdefaulttimeout()
    socket.setdefaulttimeout(seconds)
    try:
        yield
    finally:
        socket.setdefaulttimeout(prev)


def _rss_root(basepath: str) -> str:
    return os.path.join(basepath, "rss")


def _feeds_json(basepath: str) -> str:
    return os.path.join(_rss_root(basepath), "feeds.json")


def _feeds_lock_path(basepath: str) -> str:
    return os.path.join(_rss_root(basepath), "feeds.lock")


def _rss_events_jsonl(basepath: str) -> str:
    return os.path.join(basepath, "logs", "rss_events.jsonl")


def _feed_dir(basepath: str, feed_id: str) -> str:
    feed_id = _safe_feed_id(feed_id)
    return os.path.join(_rss_root(basepath), "feeds", feed_id)


def _feed_articles_jsonl(basepath: str, feed_id: str) -> str:
    feed_id = _safe_feed_id(feed_id)
    return os.path.join(_feed_dir(basepath, feed_id), "articles.jsonl")


def _feed_states_jsonl(basepath: str, feed_id: str) -> str:
    feed_id = _safe_feed_id(feed_id)
    return os.path.join(_feed_dir(basepath, feed_id), "states.jsonl")


def _article_dir(basepath: str, feed_id: str, article_id: str) -> str:
    feed_id = _safe_feed_id(feed_id)
    article_id = _safe_article_id(article_id)
    return os.path.join(_feed_dir(basepath, feed_id), "articles", article_id)


def _article_meta_json(basepath: str, feed_id: str, article_id: str) -> str:
    return os.path.join(_article_dir(basepath, feed_id, article_id), "meta.json")


def _article_content_md(basepath: str, feed_id: str, article_id: str) -> str:
    return os.path.join(_article_dir(basepath, feed_id, article_id), "content.md")


@contextmanager
def _feeds_lock(basepath: str):
    lock_path = _feeds_lock_path(basepath)
    _ensure_dir(os.path.dirname(lock_path))
    fp = open(lock_path, "a+", encoding="utf-8")
    try:
        fcntl.flock(fp.fileno(), fcntl.LOCK_EX)
        yield
    finally:
        try:
            fcntl.flock(fp.fileno(), fcntl.LOCK_UN)
        finally:
            fp.close()


def _read_json_file(path: str) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _read_feeds_strict(basepath: str) -> Dict[str, Any]:
    path = _feeds_json(basepath)
    if not os.path.exists(path):
        return {"version": 1, "updated_at": _utc_iso(), "feeds": []}

    try:
        data = _read_json_file(path)
    except Exception as e:
        raise ValueError(f"feeds.json read failed: {e}")

    if not isinstance(data, dict):
        raise ValueError("feeds.json invalid: root is not an object")
    feeds = data.get("feeds")
    if not isinstance(feeds, list):
        raise ValueError("feeds.json invalid: feeds is not a list")

    out = dict(data)
    out.setdefault("version", 1)
    out.setdefault("updated_at", _utc_iso())
    return out


def _write_feeds(basepath: str, feeds_doc: Dict[str, Any]) -> None:
    feeds_doc["updated_at"] = _utc_iso()
    _atomic_write_json(_feeds_json(basepath), feeds_doc)


def _find_feed(feeds_doc: Dict[str, Any], feed_id: str) -> Optional[Dict[str, Any]]:
    for f in feeds_doc.get("feeds", []):
        if isinstance(f, dict) and f.get("feed_id") == feed_id:
            return f
    return None


def _emit_event(basepath: str, event_type: str, payload: Dict[str, Any]) -> None:
    evt = {"ts": _utc_iso(), "type": event_type, "payload": payload}
    append_jsonl(_rss_events_jsonl(basepath), evt)


def _parse_time_struct(t) -> Optional[str]:
    try:
        if not t:
            return None
        dt = datetime.fromtimestamp(time.mktime(t), tz=timezone.utc)
        return dt.isoformat()
    except Exception:
        return None


def _pick_entry_html(entry: Any) -> str:
    try:
        if getattr(entry, "content", None):
            c0 = entry.content[0]
            v = getattr(c0, "value", "") or ""
            return str(v)
    except Exception:
        pass
    v = entry.get("summary") or entry.get("description") or ""
    return str(v)


_TAG_RE = re.compile(r"<[^>]+>")


def _html_to_text(html: str) -> str:
    s = _TAG_RE.sub("", html or "")
    s = re.sub(r"\s+\n", "\n", s)
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()


_MD_LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
_MD_IMG_RE = re.compile(r"!\[([^\]]*)\]\(([^)]+)\)")
_MD_CODE_FENCE_RE = re.compile(r"```[\s\S]*?```", re.MULTILINE)
_MD_INLINE_CODE_RE = re.compile(r"`([^`]+)`")


def _md_to_text(md: str) -> str:
    s = str(md or "")
    s = _MD_CODE_FENCE_RE.sub("", s)
    s = _MD_IMG_RE.sub(r"\1", s)
    s = _MD_LINK_RE.sub(r"\1", s)
    s = _MD_INLINE_CODE_RE.sub(r"\1", s)
    s = re.sub(r"^#{1,6}\s*", "", s, flags=re.MULTILINE)
    s = re.sub(r"^\s*[-*+]\s+", "", s, flags=re.MULTILINE)
    s = re.sub(r"^\s*\d+\.\s+", "", s, flags=re.MULTILINE)
    s = re.sub(r"\r", "", s)
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()


def _make_excerpt(text: str, n: int = 280) -> str:
    t = (text or "").strip().replace("\r", "")
    t = re.sub(r"\n{2,}", "\n", t)
    return t[:n]


# --- RSS evidence v2 helpers (keyword OR + scoring + fallback) ---

_WORD_RE = re.compile(r"[a-z0-9]{2,}", re.IGNORECASE)
_ZH_RE = re.compile(r"[\u4e00-\u9fff]{2,}")

_EN_STOPWORDS = {
    "what", "news", "there", "today", "yesterday", "this", "that", "in", "on", "at",
    "is", "are", "was", "were", "the", "a", "an", "of", "to", "for", "and", "or",
    "about", "from", "with", "latest", "recent", "update", "updates",
}

_EN_TO_ZH_HINTS = {
    "china": "中国",
    "chinese": "中国",
    "beijing": "北京",
    "shanghai": "上海",
    "hong": "香港",
    "kong": "香港",
    "taiwan": "台湾",
    "usa": "美国",
    "us": "美国",
    "america": "美国",
    "japan": "日本",
    "korea": "韩国",
    "russia": "俄罗斯",
    "europe": "欧洲",
}


def _rss_query_terms(query: str) -> List[str]:
    q = (query or "").strip()
    if not q:
        return []

    terms: List[str] = []

    for w in _WORD_RE.findall(q.lower()):
        if w in _EN_STOPWORDS:
            continue
        terms.append(w)
        if w in _EN_TO_ZH_HINTS:
            terms.append(_EN_TO_ZH_HINTS[w])

    for zh in _ZH_RE.findall(q):
        terms.append(zh)

    seen = set()
    out: List[str] = []
    for t in terms:
        t = str(t).strip()
        if not t or t in seen:
            continue
        seen.add(t)
        out.append(t)
    return out


def _rss_score_row(title: str, excerpt: str, terms: List[str]) -> int:
    t = (title or "").lower()
    e = (excerpt or "").lower()
    score = 0
    for term in terms:
        tl = term.lower()
        if not tl:
            continue
        if tl in t:
            score += 2
        if tl in e:
            score += 1
    return score


# ---------------------------
# States (append-only fold)
# ---------------------------

def _load_latest_states(basepath: str, feed_id: str) -> Dict[str, Dict[str, bool]]:
    feed_id = _safe_feed_id(feed_id)
    out: Dict[str, Dict[str, bool]] = {}
    path = _feed_states_jsonl(basepath, feed_id)
    rows = load_jsonl(path) or []
    for r in rows:
        if not isinstance(r, dict):
            continue
        aid = _safe_str(r.get("article_id")).strip()
        st = _safe_str(r.get("state")).strip()
        val = bool(r.get("value", True))
        if not aid or not st:
            continue
        if aid not in out:
            out[aid] = {"read": False, "starred": False, "archived": False, "deleted": False}
        if st in ("read", "starred", "archived", "deleted"):
            out[aid][st] = val
    return out


def _is_deleted_state(states: Dict[str, Dict[str, bool]], article_id: str) -> bool:
    st = states.get(article_id) or {}
    return bool(st.get("deleted", False))


# ---------------------------
# MCP tools
# ---------------------------

def nisb_rss_add_feed(args: Dict[str, Any]) -> Dict[str, Any]:
    basepath = _get_basepath(args)
    url = _safe_str(args.get("url")).strip()
    if not url:
        return {"success": False, "message": "missing url"}

    with _feeds_lock(basepath):
        try:
            feeds_doc = _read_feeds_strict(basepath)
        except Exception as e:
            return {"success": False, "message": f"feeds.json invalid/unreadable, refused to modify: {e}"}

        feed_id = _sha12(url)
        existed = _find_feed(feeds_doc, feed_id)
        if existed:
            existed["title"] = _safe_str(args.get("title") or existed.get("title") or "").strip()
            if "enabled" in args:
                existed["enabled"] = bool(args.get("enabled"))
            if isinstance(args.get("tags"), list):
                existed["tags"] = [str(x) for x in args.get("tags") if str(x).strip()]
            _write_feeds(basepath, feeds_doc)
            _emit_event(basepath, "rss.feed.update", {"feed_id": feed_id, "url": url})
            return {"success": True, "feed_id": feed_id, "status": "updated"}

        feed = {
            "feed_id": feed_id,
            "url": url,
            "title": _safe_str(args.get("title")).strip(),
            "enabled": bool(args.get("enabled", True)),
            "tags": [str(x) for x in (args.get("tags") or []) if str(x).strip()] if isinstance(args.get("tags"), list) else [],
            "added_at": _utc_iso(),
            "etag": None,
            "modified": None,
            "last_fetch_at": None,
            "last_status": None,
            "last_error": None,
        }
        feeds_doc["feeds"].append(feed)
        _write_feeds(basepath, feeds_doc)

    _ensure_dir(_feed_dir(basepath, feed_id))
    _emit_event(basepath, "rss.feed.add", {"feed_id": feed_id, "url": url})
    return {"success": True, "feed_id": feed_id, "status": "created"}


def nisb_rss_list_feeds(args: Dict[str, Any]) -> Dict[str, Any]:
    basepath = _get_basepath(args)
    with _feeds_lock(basepath):
        try:
            feeds_doc = _read_feeds_strict(basepath)
        except Exception as e:
            return {"success": False, "message": f"feeds.json invalid/unreadable: {e}"}

    feeds = feeds_doc.get("feeds", [])
    feeds = sorted(feeds, key=lambda x: str((x or {}).get("added_at") or ""), reverse=True)
    return {"success": True, "feeds": feeds, "updated_at": feeds_doc.get("updated_at")}


def nisb_rss_fetch(args: Dict[str, Any]) -> Dict[str, Any]:
    basepath = _get_basepath(args)

    feed_id_in = _safe_str(args.get("feed_id")).strip() or None
    if feed_id_in:
        try:
            feed_id_in = _safe_feed_id(feed_id_in)
        except Exception as e:
            return {"success": False, "message": str(e)}

    limit_entries = args.get("limit_entries", 50)
    try:
        limit_entries = int(limit_entries)
    except Exception:
        limit_entries = 50
    limit_entries = max(1, min(200, limit_entries))

    try:
        fetch_timeout = float(args.get("fetch_timeout_seconds") or os.environ.get("NISB_RSS_FETCH_TIMEOUT_SECONDS") or 15.0)
    except Exception:
        fetch_timeout = 15.0
    fetch_timeout = max(3.0, min(60.0, fetch_timeout))

    with _feeds_lock(basepath):
        try:
            feeds_doc_snapshot = _read_feeds_strict(basepath)
        except Exception as e:
            return {"success": False, "message": f"feeds.json invalid/unreadable, refused to fetch: {e}"}

        feeds_snapshot: List[Dict[str, Any]] = [f for f in (feeds_doc_snapshot.get("feeds") or []) if isinstance(f, dict)]

        if feed_id_in:
            f = _find_feed(feeds_doc_snapshot, feed_id_in)
            if not f:
                return {"success": False, "message": f"feed not found: {feed_id_in}"}
            targets = [dict(f)]
        else:
            targets = [dict(f) for f in feeds_snapshot if f.get("enabled", True)]

    total_new = 0
    per_feed: List[Dict[str, Any]] = []
    feed_patches: Dict[str, Dict[str, Any]] = {}

    for f in targets:
        fid = _safe_str(f.get("feed_id")).strip()
        url = _safe_str(f.get("url")).strip()
        if not fid or not url:
            continue

        try:
            fid = _safe_feed_id(fid)
        except Exception:
            continue

        etag = f.get("etag")
        modified = f.get("modified")

        try:
            with _socket_timeout(fetch_timeout):
                d = feedparser.parse(
                    url,
                    etag=etag,
                    modified=modified,
                    agent="NISB-RSS/1.0 (+https://nisb.local)",
                )
        except Exception as e:
            feed_patches[fid] = {
                "last_fetch_at": _utc_iso(),
                "last_status": "error",
                "last_error": str(e),
            }
            _emit_event(basepath, "rss.feed.fetch_error", {"feed_id": fid, "url": url, "error": str(e)})
            per_feed.append({"feed_id": fid, "new": 0, "status": "error", "error": str(e)})
            continue

        status = getattr(d, "status", None)
        patch: Dict[str, Any] = {"last_fetch_at": _utc_iso(), "last_status": status, "last_error": None}
        if getattr(d, "etag", None):
            patch["etag"] = d.etag
        if getattr(d, "modified", None):
            patch["modified"] = d.modified
        feed_patches[fid] = patch

        if getattr(d, "bozo", 0):
            bx = getattr(d, "bozo_exception", None)
            _emit_event(basepath, "rss.feed.bozo", {"feed_id": fid, "url": url, "error": _safe_str(bx)})

        if status == 304:
            _emit_event(basepath, "rss.feed.not_modified", {"feed_id": fid, "url": url})
            per_feed.append({"feed_id": fid, "new": 0, "status": 304})
            continue

        entries = list(getattr(d, "entries", []) or [])[:limit_entries]
        new_count = 0

        existing = set()
        for row in load_jsonl(_feed_articles_jsonl(basepath, fid)) or []:
            if isinstance(row, dict):
                aid = row.get("article_id")
                if aid:
                    existing.add(aid)

        for entry in entries:
            link = _safe_str(entry.get("link") or entry.get("id") or "").strip()
            title = _safe_str(entry.get("title")).strip()
            published_at = _parse_time_struct(entry.get("published_parsed")) or _parse_time_struct(entry.get("updated_parsed"))
            content_html = _pick_entry_html(entry)
            content_text = _html_to_text(content_html)

            key = link or f"{title}|{published_at or ''}"
            article_id = _sha12(key)

            if article_id in existing:
                continue

            adir = _article_dir(basepath, fid, article_id)
            _ensure_dir(adir)

            meta = {
                "feed_id": fid,
                "article_id": article_id,
                "title": title,
                "link": link,
                "published_at": published_at,
                "fetched_at": _utc_iso(),
                "source": "rss",
            }
            _atomic_write_json(_article_meta_json(basepath, fid, article_id), meta)

            md = "\n".join(
                [
                    f"# {title or 'Untitled'}",
                    "",
                    f"- Link: {link}" if link else "- Link: (missing)",
                    f"- Published: {published_at}" if published_at else "- Published: (unknown)",
                    "",
                    content_text.strip() or "(empty)",
                    "",
                ]
            )
            with open(_article_content_md(basepath, fid, article_id), "w", encoding="utf-8") as wf:
                wf.write(md)

            idx_row = {
                "ts": _utc_iso(),
                "feed_id": fid,
                "article_id": article_id,
                "title": title,
                "link": link,
                "published_at": published_at,
                "excerpt": _make_excerpt(content_text),
                "object_ref": f"rss:{fid}/{article_id}",
                "source": "rss",
            }
            append_jsonl(_feed_articles_jsonl(basepath, fid), idx_row)
            _emit_event(basepath, "rss.article.new", {"feed_id": fid, "article_id": article_id, "link": link})
            existing.add(article_id)
            new_count += 1

            try:
                uid = _uid_from_basepath(basepath)
                if uid:
                    _rss_index_upsert_one(
                        uid,
                        {
                            "article_id": article_id,
                            "feed_id": fid,
                            "title": title,
                            "url": link,
                            "link": link,
                            "published_at": published_at,
                            "summary": content_text,
                            "content": content_text,
                        },
                    )
            except Exception:
                pass

        total_new += new_count
        per_feed.append({"feed_id": fid, "new": new_count, "status": status})

    with _feeds_lock(basepath):
        try:
            feeds_doc = _read_feeds_strict(basepath)
        except Exception as e:
            return {
                "success": False,
                "message": f"feeds.json became invalid after fetch; refused to write back patches: {e}",
                "total_new": total_new,
                "feeds": per_feed,
            }

        for fid, patch in feed_patches.items():
            cur = _find_feed(feeds_doc, fid)
            if not cur:
                continue
            for k, v in patch.items():
                cur[k] = v

        _write_feeds(basepath, feeds_doc)

    return {"success": True, "total_new": total_new, "feeds": per_feed}


def nisb_rss_list_articles(args: Dict[str, Any]) -> Dict[str, Any]:
    basepath = _get_basepath(args)
    feed_id = _safe_str(args.get("feed_id")).strip()
    if not feed_id:
        return {"success": False, "message": "missing feed_id"}

    try:
        feed_id = _safe_feed_id(feed_id)
    except Exception as e:
        return {"success": False, "message": str(e)}

    limit = args.get("limit", 50)
    try:
        limit = int(limit)
    except Exception:
        limit = 50
    limit = max(1, min(200, limit))

    rows = load_jsonl(_feed_articles_jsonl(basepath, feed_id)) or []
    rows = [r for r in rows if isinstance(r, dict)]
    rows = sorted(rows, key=lambda x: str(x.get("ts") or ""), reverse=True)

    states = _load_latest_states(basepath, feed_id)

    seen: set[str] = set()
    uniq: List[Dict[str, Any]] = []
    for r in rows:
        aid = _safe_str(r.get("article_id")).strip()
        if not aid or aid in seen:
            continue
        seen.add(aid)

        if _is_deleted_state(states, aid):
            continue

        st = states.get(aid) or {}
        r["read"] = bool(st.get("read", False))
        r["starred"] = bool(st.get("starred", False))
        r["archived"] = bool(st.get("archived", False))
        r["deleted"] = bool(st.get("deleted", False))
        uniq.append(r)

        if len(uniq) >= limit:
            break

    return {"success": True, "feed_id": feed_id, "items": uniq}


def nisb_rss_get_article(args: Dict[str, Any]) -> Dict[str, Any]:
    basepath = _get_basepath(args)
    feed_id = _safe_str(args.get("feed_id")).strip()
    article_id = _safe_str(args.get("article_id")).strip()
    if not feed_id or not article_id:
        return {"success": False, "message": "missing feed_id/article_id"}

    try:
        feed_id = _safe_feed_id(feed_id)
        article_id = _safe_article_id(article_id)
    except Exception as e:
        return {"success": False, "message": str(e)}

    states = _load_latest_states(basepath, feed_id)
    if _is_deleted_state(states, article_id):
        return {"success": False, "message": "article deleted"}

    meta = load_json(_article_meta_json(basepath, feed_id, article_id)) or {}
    md_path = _article_content_md(basepath, feed_id, article_id)
    if not os.path.exists(md_path):
        return {"success": False, "message": "article content not found"}

    with open(md_path, "r", encoding="utf-8") as f:
        content_md = f.read()

    append_jsonl(
        _feed_states_jsonl(basepath, feed_id),
        {"ts": _utc_iso(), "feed_id": feed_id, "article_id": article_id, "state": "read", "value": True},
    )
    _emit_event(basepath, "rss.article.read", {"feed_id": feed_id, "article_id": article_id})

    return {"success": True, "meta": meta, "content_md": content_md}


def nisb_rss_set_state(args: Dict[str, Any]) -> Dict[str, Any]:
    basepath = _get_basepath(args)
    feed_id = _safe_str(args.get("feed_id")).strip()
    article_id = _safe_str(args.get("article_id")).strip()
    state = _safe_str(args.get("state")).strip()
    value = bool(args.get("value", True))

    if not feed_id or not article_id or not state:
        return {"success": False, "message": "missing feed_id/article_id/state"}

    try:
        feed_id = _safe_feed_id(feed_id)
        article_id = _safe_article_id(article_id)
    except Exception as e:
        return {"success": False, "message": str(e)}

    append_jsonl(
        _feed_states_jsonl(basepath, feed_id),
        {"ts": _utc_iso(), "feed_id": feed_id, "article_id": article_id, "state": state, "value": value},
    )
    _emit_event(basepath, "rss.article.state", {"feed_id": feed_id, "article_id": article_id, "state": state, "value": value})
    return {"success": True}


def nisb_rss_delete_article(args: Dict[str, Any]) -> Dict[str, Any]:
    basepath = _get_basepath(args)
    feed_id = _safe_str(args.get("feed_id")).strip()
    article_id = _safe_str(args.get("article_id")).strip()
    delete_files = bool(args.get("delete_files", True))

    if not feed_id or not article_id:
        return {"success": False, "message": "missing feed_id/article_id"}

    try:
        feed_id = _safe_feed_id(feed_id)
        article_id = _safe_article_id(article_id)
    except Exception as e:
        return {"success": False, "message": str(e)}

    append_jsonl(
        _feed_states_jsonl(basepath, feed_id),
        {"ts": _utc_iso(), "feed_id": feed_id, "article_id": article_id, "state": "deleted", "value": True},
    )

    deleted_files = False
    warning = ""
    if delete_files:
        adir = _article_dir(basepath, feed_id, article_id)
        try:
            if os.path.isdir(adir):
                shutil.rmtree(adir)
            deleted_files = True
        except Exception as e:
            warning = str(e)

    try:
        uid = _uid_from_basepath(basepath)
        if uid:
            _rss_index_upsert_one(
                uid,
                {
                    "article_id": article_id,
                    "feed_id": feed_id,
                    "title": "",
                    "url": "",
                    "published_at": "",
                    "summary": "",
                    "content": "",
                },
            )
    except Exception:
        pass

    _emit_event(basepath, "rss.article.delete", {"feed_id": feed_id, "article_id": article_id, "deleted_files": deleted_files})
    out: Dict[str, Any] = {"success": True, "feed_id": feed_id, "article_id": article_id, "deleted_files": deleted_files}
    if warning:
        out["warning"] = warning
    return out


def nisb_rss_override_article(args: Dict[str, Any]) -> Dict[str, Any]:
    basepath = _get_basepath(args)
    feed_id = _safe_str(args.get("feed_id")).strip()
    article_id = _safe_str(args.get("article_id")).strip()
    title_in = _safe_str(args.get("title")).strip()
    url_in = _safe_str(args.get("url")).strip()
    content_md_in = _safe_str(args.get("content_md") or args.get("contentmd") or args.get("content")).strip()

    if not feed_id or not article_id:
        return {"success": False, "message": "missing feed_id/article_id"}
    if not content_md_in or len(content_md_in) < 20:
        return {"success": False, "message": "missing/too_short content_md"}

    try:
        feed_id = _safe_feed_id(feed_id)
        article_id = _safe_article_id(article_id)
    except Exception as e:
        return {"success": False, "message": str(e)}

    states = _load_latest_states(basepath, feed_id)
    if _is_deleted_state(states, article_id):
        return {"success": False, "message": "article deleted"}

    meta_path = _article_meta_json(basepath, feed_id, article_id)
    meta = load_json(meta_path) or {}
    if not isinstance(meta, dict):
        meta = {}

    title = title_in or _safe_str(meta.get("title")).strip() or "Untitled"
    url = url_in or _safe_str(meta.get("link") or meta.get("url")).strip()
    published_at = _safe_str(meta.get("published_at")).strip() or None

    adir = _article_dir(basepath, feed_id, article_id)
    _ensure_dir(adir)

    header = "\n".join(
        [
            f"# {title}",
            "",
            f"- Link: {url}" if url else "- Link: (missing)",
            f"- Published: {published_at}" if published_at else "- Published: (unknown)",
            "",
        ]
    )
    content_md = header + content_md_in.strip() + "\n"

    with open(_article_content_md(basepath, feed_id, article_id), "w", encoding="utf-8") as wf:
        wf.write(content_md)

    meta2 = dict(meta)
    meta2["feed_id"] = feed_id
    meta2["article_id"] = article_id
    meta2["title"] = title
    if url:
        meta2["link"] = url
    if published_at:
        meta2["published_at"] = published_at
    meta2["override_at"] = _utc_iso()
    meta2["source"] = "override"
    _atomic_write_json(meta_path, meta2)

    content_text = _md_to_text(content_md_in)
    excerpt = _make_excerpt(content_text, n=360)

    idx_row = {
        "ts": _utc_iso(),
        "feed_id": feed_id,
        "article_id": article_id,
        "title": title,
        "link": url,
        "published_at": published_at,
        "excerpt": excerpt,
        "object_ref": f"rss:{feed_id}/{article_id}",
        "source": "override",
    }
    append_jsonl(_feed_articles_jsonl(basepath, feed_id), idx_row)

    try:
        uid = _uid_from_basepath(basepath)
        if uid:
            _rss_index_upsert_one(
                uid,
                {
                    "article_id": article_id,
                    "feed_id": feed_id,
                    "title": title,
                    "url": url,
                    "published_at": published_at,
                    "summary": content_text,
                    "content": content_text,
                },
            )
    except Exception:
        pass

    _emit_event(basepath, "rss.article.override", {"feed_id": feed_id, "article_id": article_id})

    return {"success": True, "feed_id": feed_id, "article_id": article_id, "title": title, "url": url, "excerpt": excerpt}


def nisb_rss_evidence_scope(args: Dict[str, Any]) -> Dict[str, Any]:
    basepath = _get_basepath(args)
    feed_id = _safe_str(args.get("feed_id")).strip()
    query = _safe_str(args.get("query")).strip()

    limit = args.get("limit", 8)
    try:
        limit = int(limit)
    except Exception:
        limit = 8
    limit = max(1, min(20, limit))

    if not feed_id:
        return {"success": False, "message": "missing feed_id"}

    try:
        feed_id = _safe_feed_id(feed_id)
    except Exception as e:
        return {"success": False, "message": str(e)}

    rows = load_jsonl(_feed_articles_jsonl(basepath, feed_id)) or []
    rows = [r for r in rows if isinstance(r, dict)]
    rows = sorted(rows, key=lambda x: str(x.get("ts") or ""), reverse=True)

    states = _load_latest_states(basepath, feed_id)

    seen: set[str] = set()
    filtered: List[Dict[str, Any]] = []
    for r in rows:
        aid = _safe_str(r.get("article_id")).strip()
        if not aid or aid in seen:
            continue
        seen.add(aid)
        if _is_deleted_state(states, aid):
            continue
        filtered.append(r)

    terms = _rss_query_terms(query)
    scored: List[Tuple[int, Dict[str, Any]]] = []

    if terms:
        for r in filtered:
            title = _safe_str(r.get("title"))
            excerpt = _safe_str(r.get("excerpt"))
            s = _rss_score_row(title, excerpt, terms)
            if s > 0:
                scored.append((s, r))
        scored.sort(key=lambda x: (x[0], str(x[1].get("ts") or "")), reverse=True)
        picked = [r for s, r in scored[:limit]]
        matched = True
    else:
        picked = filtered[:limit]
        matched = False

    if terms and not picked:
        picked = filtered[:limit]
        matched = False

    hits: List[Dict[str, Any]] = []
    for r in picked:
        title = _safe_str(r.get("title"))
        excerpt = _safe_str(r.get("excerpt"))
        link = _safe_str(r.get("link"))

        aid = _safe_str(r.get("article_id"))
        fid = _safe_str(r.get("feed_id")) or feed_id
        obj = _safe_str(r.get("object_ref")) or f"rss:{fid}/{aid}"

        quote = excerpt.strip()

        if not quote and aid:
            try:
                md_path = _article_content_md(basepath, feed_id, aid)
                if os.path.exists(md_path):
                    with open(md_path, "r", encoding="utf-8") as f:
                        quote = (f.read(800) or "").strip()
            except Exception:
                pass

        if not link:
            continue

        relevance = 0.15
        if terms and matched:
            raw_score = _rss_score_row(title, excerpt, terms)
            relevance = min(1.0, 0.6 + raw_score / max(6.0, 3.0 * len(terms)))

        item = {
            "relevance": relevance,
            "excerpt": quote,
            "charstart": 0,
            "charend": len(quote),
            "spanid": obj,
            "spanchars": len(quote),
            "object_ref": obj,
            "title": title,
            "url": link,
            "quote": quote,
            "matched": matched,
            "matched_terms": terms if matched else [],
            "published_at": r.get("published_at"),
            "feed_id": fid,
            "article_id": aid,
        }
        hits.append(item)

        if len(hits) >= limit:
            break

    return {"success": True, "items": hits}


def nisb_rss_update_feed(args: Dict[str, Any]) -> Dict[str, Any]:
    basepath = _get_basepath(args)
    feed_id = _safe_str(args.get("feed_id")).strip()
    if not feed_id:
        return {"success": False, "message": "missing feed_id"}

    try:
        feed_id = _safe_feed_id(feed_id)
    except Exception as e:
        return {"success": False, "message": str(e)}

    with _feeds_lock(basepath):
        try:
            feeds_doc = _read_feeds_strict(basepath)
        except Exception as e:
            return {"success": False, "message": f"feeds.json invalid/unreadable, refused to modify: {e}"}

        f = _find_feed(feeds_doc, feed_id)
        if not f:
            return {"success": False, "message": f"feed not found: {feed_id}"}

        if "custom_name" in args:
            f["custom_name"] = _safe_str(args.get("custom_name")).strip()
        if "title" in args:
            f["title"] = _safe_str(args.get("title")).strip()
        if "category" in args:
            f["category"] = _safe_str(args.get("category")).strip()
        if "enabled" in args:
            f["enabled"] = bool(args.get("enabled"))
        if isinstance(args.get("tags"), list):
            f["tags"] = [str(x).strip() for x in args.get("tags") if str(x).strip()]

        _write_feeds(basepath, feeds_doc)

    _emit_event(basepath, "rss.feed.update", {"feed_id": feed_id})
    return {"success": True, "feed_id": feed_id, "feed": f}


def nisb_rss_delete_feed(args: Dict[str, Any]) -> Dict[str, Any]:
    basepath = _get_basepath(args)
    feed_id = _safe_str(args.get("feed_id")).strip()
    delete_files = bool(args.get("delete_files", True))
    if not feed_id:
        return {"success": False, "message": "missing feed_id"}

    try:
        feed_id = _safe_feed_id(feed_id)
    except Exception as e:
        return {"success": False, "message": str(e)}

    with _feeds_lock(basepath):
        try:
            feeds_doc = _read_feeds_strict(basepath)
        except Exception as e:
            return {"success": False, "message": f"feeds.json invalid/unreadable, refused to modify: {e}"}

        feeds = feeds_doc.get("feeds", [])
        before = len(feeds)

        feeds_doc["feeds"] = [f for f in feeds if isinstance(f, dict) and f.get("feed_id") != feed_id]
        after = len(feeds_doc["feeds"])
        if before == after:
            return {"success": False, "message": f"feed not found: {feed_id}"}

        _write_feeds(basepath, feeds_doc)

    if delete_files:
        fdir = _feed_dir(basepath, feed_id)
        try:
            if os.path.isdir(fdir):
                shutil.rmtree(fdir)
        except Exception as e:
            _emit_event(basepath, "rss.feed.delete_files_error", {"feed_id": feed_id, "error": str(e)})
            return {
                "success": True,
                "feed_id": feed_id,
                "deleted_files": False,
                "warning": f"deleted from feeds.json but failed to delete files: {e}",
            }

    _emit_event(basepath, "rss.feed.delete", {"feed_id": feed_id, "delete_files": delete_files})
    return {"success": True, "feed_id": feed_id, "deleted_files": delete_files}


def nisb_rss_list_tags(args: Dict[str, Any]) -> Dict[str, Any]:
    basepath = _get_basepath(args)
    with _feeds_lock(basepath):
        try:
            feeds_doc = _read_feeds_strict(basepath)
        except Exception as e:
            return {"success": False, "message": f"feeds.json invalid/unreadable: {e}"}

    tag_count: Dict[str, int] = {}
    for f in (feeds_doc.get("feeds", []) or []):
        if not isinstance(f, dict):
            continue
        tags = f.get("tags") or []
        if not isinstance(tags, list):
            continue
        for t in tags:
            tt = str(t).strip()
            if not tt:
                continue
            tag_count[tt] = tag_count.get(tt, 0) + 1

    tags_sorted = sorted(
        [{"tag": k, "count": v} for k, v in tag_count.items()],
        key=lambda x: (-x["count"], x["tag"]),
    )
    return {"success": True, "tags": tags_sorted}


# --- Gate prefs (account-level persistence) ---

def _gate_prefs_json(basepath: str) -> str:
    return os.path.join(_rss_root(basepath), "gate_prefs.json")


def _normalize_str_list(v: Any, max_len: int) -> List[str]:
    if not isinstance(v, list):
        return []
    out: List[str] = []
    seen = set()
    for x in v:
        s = str(x).strip()
        if not s or s in seen:
            continue
        seen.add(s)
        out.append(s)
        if len(out) >= max_len:
            break
    return out


def _normalize_groups(v: Any, max_groups: int = 50, max_feed_ids: int = 500) -> List[Dict[str, Any]]:
    if not isinstance(v, list):
        return []
    out: List[Dict[str, Any]] = []
    seen = set()
    for g in v:
        if not isinstance(g, dict):
            continue
        group_id = _safe_str(g.get("group_id")).strip()
        group_name = _safe_str(g.get("group_name")).strip()
        feed_ids_raw = g.get("feed_ids") or []
        feed_ids = _normalize_str_list(feed_ids_raw, max_feed_ids)

        if not group_id:
            key = f"{group_name}|{','.join(feed_ids)}"
            group_id = f"group_{_sha12(key)}"

        if group_id in seen:
            continue
        seen.add(group_id)

        created_at = g.get("created_at")
        try:
            created_at = int(created_at) if created_at is not None else int(time.time() * 1000)
        except Exception:
            created_at = int(time.time() * 1000)

        out.append({"group_id": group_id, "group_name": group_name or group_id, "feed_ids": feed_ids, "created_at": created_at})
        if len(out) >= max_groups:
            break
    return out


def nisb_rss_gate_prefs_get(args: Dict[str, Any]) -> Dict[str, Any]:
    basepath = _get_basepath(args)
    path = _gate_prefs_json(basepath)

    doc = load_json(path) or {}
    if not isinstance(doc, dict):
        doc = {}

    prefs = doc.get("prefs")
    if not isinstance(prefs, dict):
        prefs = {}

    out = {
        "version": int(doc.get("version") or 1),
        "updated_at": _safe_str(doc.get("updated_at") or ""),
        "prefs": {
            "subscribe_groups": _normalize_groups(prefs.get("subscribe_groups")),
            "favorite_keywords": _normalize_str_list(prefs.get("favorite_keywords"), 200),
            "blocked_urls": _normalize_str_list(prefs.get("blocked_urls"), 5000),
            "deleted_urls": _normalize_str_list(prefs.get("deleted_urls"), 5000),
            "imported_urls": _normalize_str_list(prefs.get("imported_urls"), 5000),
            "last_library_id": _safe_str(prefs.get("last_library_id")).strip(),
        },
    }
    return {"success": True, **out}


def nisb_rss_gate_prefs_set(args: Dict[str, Any]) -> Dict[str, Any]:
    basepath = _get_basepath(args)
    path = _gate_prefs_json(basepath)

    cur = load_json(path) or {}
    if not isinstance(cur, dict):
        cur = {}
    prefs = cur.get("prefs")
    if not isinstance(prefs, dict):
        prefs = {}

    if "subscribe_groups" in args:
        prefs["subscribe_groups"] = _normalize_groups(args.get("subscribe_groups"))
    if "favorite_keywords" in args:
        prefs["favorite_keywords"] = _normalize_str_list(args.get("favorite_keywords"), 200)
    if "blocked_urls" in args:
        prefs["blocked_urls"] = _normalize_str_list(args.get("blocked_urls"), 5000)
    if "deleted_urls" in args:
        prefs["deleted_urls"] = _normalize_str_list(args.get("deleted_urls"), 5000)
    if "imported_urls" in args:
        prefs["imported_urls"] = _normalize_str_list(args.get("imported_urls"), 5000)
    if "last_library_id" in args:
        prefs["last_library_id"] = _safe_str(args.get("last_library_id")).strip()

    doc = {"version": 1, "updated_at": _utc_iso(), "prefs": prefs}
    _atomic_write_json(path, doc)
    _emit_event(basepath, "rss.gate.prefs.set", {"keys": list(args.keys())})

    return {"success": True, "updated_at": doc["updated_at"]}


