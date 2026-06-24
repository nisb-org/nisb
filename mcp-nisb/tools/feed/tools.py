#!/usr/bin/env python3
from __future__ import annotations

import os
import re
import uuid
import json
import tempfile
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
from collections import Counter, deque, defaultdict

from core.storage import append_jsonl
from tools.feed.sse_bus import publish as sse_publish

FEED_DIR = "/data/shared/feed"
CACHE_DIR = os.path.join(FEED_DIR, "cache")

POSTS_FILE = os.path.join(FEED_DIR, "posts.jsonl")
EVENTS_FILE = os.path.join(FEED_DIR, "events.jsonl")
DELETIONS_FILE = os.path.join(FEED_DIR, "deletions.jsonl")

COMMENTS_FILE = os.path.join(FEED_DIR, "comments.jsonl")
COMMENT_DELETIONS_FILE = os.path.join(FEED_DIR, "comment_deletions.jsonl")

COMMENT_EVENTS_FILE = os.path.join(FEED_DIR, "comment_events.jsonl")
COMMENT_SCORES_FILE = os.path.join(CACHE_DIR, "comment_scores.json")

NOTIFICATIONS_FILE = os.path.join(FEED_DIR, "notifications.jsonl")
NOTIFICATIONS_READ_FILE = os.path.join(FEED_DIR, "notifications_read.jsonl")

FOLLOWS_FILE = os.path.join(FEED_DIR, "follows.jsonl")

POST_SCORES_FILE = os.path.join(CACHE_DIR, "post_scores.json")
TAGS_INDEX_FILE = os.path.join(FEED_DIR, "tags_index.json")
TRENDING_TAGS_FILE = os.path.join(CACHE_DIR, "trending_tags.json")
FOLLOW_GRAPH_FILE = os.path.join(CACHE_DIR, "follow_graph.json")

PUBLIC_NOTES_DIR = os.path.join(FEED_DIR, "notes")

# ---------- helpers ----------

def _now_iso() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def _parse_iso(ts: str) -> Optional[datetime]:
    if not ts:
        return None
    try:
        t = ts.strip()
        if t.endswith("Z"):
            t = t[:-1]
        return datetime.fromisoformat(t)
    except Exception:
        return None


def _safe_title_from_path(note_path: str) -> str:
    name = os.path.basename(note_path or "").strip()
    if not name:
        return "Untitled"
    name = re.sub(r"\.(md|markdown)$", "", name, flags=re.IGNORECASE)
    return name or "Untitled"


def _make_excerpt(md: str, max_len: int = 200) -> str:
    s = (md or "").strip()
    s = re.sub(r"`{1,3}.*?`{1,3}", "", s, flags=re.DOTALL)
    s = re.sub(r"!\[.*?\]\(.*?\)", "", s)
    s = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", s)
    s = re.sub(r"[#>*_>-]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    if len(s) <= max_len:
        return s
    return s[: max_len - 1].rstrip() + "…"


def _atomic_write_text(path: str, content: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(prefix=".tmp_", dir=os.path.dirname(path))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content or "")
        os.replace(tmp_path, path)
    finally:
        try:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
        except Exception:
            pass


def _atomic_write_json(path: str, obj: Any) -> None:
    _atomic_write_text(path, json.dumps(obj, ensure_ascii=False, indent=2))


def _load_json(path: str, default: Any) -> Any:
    if not os.path.exists(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def _read_jsonl(path: str) -> List[Dict[str, Any]]:
    if not os.path.exists(path):
        return []
    out: List[Dict[str, Any]] = []
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    out.append(json.loads(line))
                except Exception:
                    continue
    except Exception:
        return out
    return out


def _load_deleted_set() -> set:
    deleted = set()
    for it in _read_jsonl(DELETIONS_FILE):
        fid = str(it.get("feed_id") or it.get("id") or "").strip()
        if fid:
            deleted.add(fid)
    return deleted


def _load_deleted_comment_set() -> set:
    deleted = set()
    for it in _read_jsonl(COMMENT_DELETIONS_FILE):
        cid = str(it.get("comment_id") or "").strip()
        if cid:
            deleted.add(cid)
    return deleted


def _find_post(feed_id: str) -> Optional[Dict[str, Any]]:
    if not feed_id or not os.path.exists(POSTS_FILE):
        return None
    found = None
    try:
        with open(POSTS_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    it = json.loads(line)
                except Exception:
                    continue
                if str(it.get("id") or "") == feed_id:
                    found = it
    except Exception:
        return None
    return found


def _find_comment(comment_id: str) -> Optional[Dict[str, Any]]:
    if not comment_id or not os.path.exists(COMMENTS_FILE):
        return None
    found = None
    try:
        with open(COMMENTS_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    it = json.loads(line)
                except Exception:
                    continue
                if str(it.get("id") or "") == comment_id:
                    found = it
    except Exception:
        return None
    return found


def _clean_tag(t: str) -> str:
    t = re.sub(r"^[#\s]+", "", str(t or "").strip())
    t = re.sub(r"\s+", " ", t).strip()
    t = re.sub(r"[^\w\u4e00-\u9fa5\-\+\. ]+", "", t).strip()
    if not t:
        return ""
    if len(t) > 32:
        t = t[:32].strip()
    return t


def _fallback_tags_cn(md: str, k: int = 5) -> List[str]:
    text = re.sub(r"`{1,3}.*?`{1,3}", " ", md or "", flags=re.DOTALL)
    text = re.sub(r"!\[.*?\]\(.*?\)", " ", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"\s+", " ", text).strip()

    chunks = re.findall(r"[\u4e00-\u9fa5]{2,6}", text)
    if not chunks:
        return []
    cnt = Counter(chunks)
    tags = [w for (w, _) in cnt.most_common(k)]
    return [_clean_tag(t) for t in tags if _clean_tag(t)]


def _fallback_tags_en(md: str, k: int = 5) -> List[str]:
    text = re.sub(r"`{1,3}.*?`{1,3}", " ", md or "", flags=re.DOTALL)
    text = re.sub(r"!\[.*?\]\(.*?\)", " ", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"[#>*_>-]+", " ", text)
    text = re.sub(r"[^0-9A-Za-z\u4e00-\u9fa5 ]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip().lower()

    words = [w for w in text.split(" ") if 2 <= len(w) <= 18]
    stop = {"the", "and", "for", "with", "this", "that", "from", "into", "your", "you", "are", "was", "were"}
    words = [w for w in words if w not in stop and not w.isdigit()]
    cnt = Counter(words)
    tags = [w for (w, _) in cnt.most_common(k)]
    return [_clean_tag(t) for t in tags if _clean_tag(t)]


def _generate_tags(md: str) -> List[str]:
    tags: List[str] = []
    tags.extend(_fallback_tags_cn(md, k=5))
    for t in _fallback_tags_en(md, k=5):
        if t not in tags:
            tags.append(t)

    tags = [t for t in tags if t]
    if len(tags) < 3:
        for extra in ["nisb", "feed", "note", "knowledge", "ideas"]:
            if len(tags) >= 3:
                break
            if extra not in tags:
                tags.append(extra)
    return tags[:5]


def _matches_before_cursor(item_ts: Optional[datetime], before: Optional[datetime]) -> bool:
    if before is None:
        return True
    if item_ts is None:
        return False
    return item_ts < before


def _get_score_cache() -> Dict[str, Any]:
    return _load_json(POST_SCORES_FILE, {})

# ---------- Profile cache (P0: author decorate) ----------
_PROFILE_CACHE = {}  # uid -> (mtime, profile_dict)


def _public_profile_path_fast(user_id: str) -> str:
    # 不依赖 PROFILES_DIR，避免定义顺序导致装饰失效
    return os.path.join(FEED_DIR, "profiles", str(user_id), "profile.json")


def _load_public_profile_cached(user_id: str) -> Dict[str, Any]:
    uid = str(user_id or "").strip()
    if not uid:
        return {}

    try:
        p = _public_profile_path_fast(uid)
        if not os.path.exists(p):
            return {}

        mtime = os.path.getmtime(p)
        hit = _PROFILE_CACHE.get(uid)
        if hit and isinstance(hit, tuple) and len(hit) == 2 and hit[0] == mtime:
            return hit[1] or {}

        it = _load_json(p, {})
        if not isinstance(it, dict):
            it = {}

        _PROFILE_CACHE[uid] = (mtime, it)
        return it
    except Exception:
        return {}


def _pick_author_uid(obj: Any) -> str:
    if not obj:
        return ""
    if isinstance(obj, str):
        return obj.strip()
    if isinstance(obj, dict):
        v = obj.get("user_id") or obj.get("userId") or obj.get("id")
        return str(v or "").strip()
    return ""

def _decorate_author_fields(out: Dict[str, Any]) -> None:
    # out: post card / comment / notification item
    author = out.get("author")
    uid = _pick_author_uid(author)

    # 兼容某些记录可能直接用 author_user_id
    if not uid:
        uid = str(out.get("author_user_id") or out.get("authorUserId") or "").strip()
        if uid:
            out["author"] = {"user_id": uid}
            author = out["author"]

    if not uid:
        return

    prof = _load_public_profile_cached(uid)
    if not prof:
        return

    dn = str(prof.get("display_name") or "").strip()
    av = str(prof.get("avatar_url") or "").strip()

    # 兼容前端两种读取方式（你现有的 FeedItemCard/Detail/Comments 都能吃到）
    out["author_display_name"] = dn
    out["author_avatar_url"] = av

    if isinstance(out.get("author"), dict):
        out["author"]["display_name"] = dn
        out["author"]["avatar_url"] = av

def _decorate_item(it: Dict[str, Any], score_cache: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(it)
    pid = str(out.get("id") or "")
    sc = score_cache.get(pid) or {}
    out["score"] = sc.get("score", 10)
    out["status"] = sc.get("status", out.get("status", "visible"))
    out["counts"] = sc.get(
        "counts",
        {"like": 0, "bookmark": 0, "boost": 0, "downvote_24h": 0, "spam_7d": 0, "comment": 0},
    )

    # ✅ 作者昵称/头像装饰：我的feed / 广场 / ForYou / 标签筛选 / 书签列表（只要走 _decorate_item 都会全局生效）
    try:
        _decorate_author_fields(out)
    except Exception:
        pass

    out.pop("content_md", None)
    return out

def _append_notification(target_user_id: str, actor_user_id: str, ntype: str, feed_id: str = "", comment_id: str = "") -> None:
    if not target_user_id or target_user_id == actor_user_id:
        return
    created_at = _now_iso()
    nid = f"ntf_{created_at.replace(':','').replace('-','')}_{uuid.uuid4().hex[:8]}"
    item = {
        "id": nid,
        "created_at": created_at,
        "user_id": target_user_id,
        "actor_user_id": actor_user_id,
        "type": ntype,
        "feed_id": feed_id,
        "comment_id": comment_id,
    }
    os.makedirs(FEED_DIR, exist_ok=True)
    append_jsonl(NOTIFICATIONS_FILE, item)
    try:
        sse_publish(target_user_id, {"type": "notification", "item": item})
    except Exception:
        pass


# ---------- tools (publish/list/recommend/tag) ----------

def nisb_feed_publish(arguments: Dict[str, Any]) -> Dict[str, Any]:
    user_id = str(arguments.get("user_id") or "").strip()
    basepath = str(arguments.get("basepath") or "").strip()
    if not user_id:
        return {"success": False, "message": "Missing user_id."}
    if not basepath:
        return {"success": False, "message": "Missing basepath."}

    content_md = str(arguments.get("content_md") or "").strip()
    if not content_md:
        return {"success": False, "message": "content_md is empty."}

    note_path = str(arguments.get("note_path") or "").strip()
    title = str(arguments.get("title") or "").strip() or _safe_title_from_path(note_path)

    created_at = _now_iso()
    feed_id = f"feed_{created_at.replace(':', '').replace('-', '')}_{uuid.uuid4().hex[:8]}"

    # 1) ✅ 发布晋升：把 nisb://file?path=agent_files/feed_images/... 拷贝到 shared/feed/assets/images/{uid}/{feed_id}/
    #    并把 markdown 内图片 url 重写成 /api/feed/assets/images/{uid}/{feed_id}/{filename}?v=...
    try:
        content_md = _feed_promote_images_in_markdown(
            content_md, basepath=basepath, user_id=user_id, feed_id=feed_id
        )
    except Exception:
        # 不因为图片晋升失败而阻断发布
        pass

    # 2) 生成标签（保持你原来的逻辑）
    tags = _generate_tags(content_md)
    tags = [t for t in [_clean_tag(x) for x in tags] if t]
    tags = list(dict.fromkeys(tags))[:5]

    # 3) 写公开快照：/data/shared/feed/notes/{author_uid}/{feed_id}.md
    public_snapshot_path = os.path.join(PUBLIC_NOTES_DIR, user_id, f"{feed_id}.md")
    os.makedirs(os.path.dirname(public_snapshot_path), exist_ok=True)
    _atomic_write_text(public_snapshot_path, content_md)

    # 4) 确保 shared/feed 目录存在（保持原行为）
    os.makedirs(FEED_DIR, exist_ok=True)
    os.makedirs(CACHE_DIR, exist_ok=True)

    post_item: Dict[str, Any] = {
        "id": feed_id,
        "type": "note_post",
        "created_at": created_at,
        "author": {"user_id": user_id},
        "title": title,
        "excerpt": _make_excerpt(content_md),
        "tags": tags,
        "note_path": note_path,
        "visibility": "public",
        "status": "visible",
        "public_snapshot_path": public_snapshot_path,
    }

    ok = append_jsonl(POSTS_FILE, post_item)
    if not ok:
        return {"success": False, "message": "Failed to append posts.jsonl."}

    # 5) 写入用户侧 my_posts.jsonl（保持原行为）
    my_posts_file = os.path.join(basepath, "feed", "my_posts.jsonl")
    os.makedirs(os.path.dirname(my_posts_file), exist_ok=True)
    append_jsonl(my_posts_file, {"id": feed_id, "created_at": created_at})

    # 6) ✅ 原子更新 tags_index.json（不影响发布主流程）
    try:
        tags_index_path = os.path.join(FEED_DIR, "tags_index.json")
        os.makedirs(os.path.dirname(tags_index_path), exist_ok=True)

        idx = {}
        try:
            if os.path.exists(tags_index_path):
                with open(tags_index_path, "r", encoding="utf-8") as f:
                    idx = json.load(f) or {}
        except Exception:
            idx = {}

        for t in tags:
            k = str(t).strip()
            if not k:
                continue
            cur = idx.get(k) or {}
            count = int(cur.get("count") or 0)
            feed_ids = cur.get("feed_ids") or []
            if not isinstance(feed_ids, list):
                feed_ids = []
            if feed_id not in feed_ids:
                feed_ids.append(feed_id)
                count += 1
            idx[k] = {"count": count, "feed_ids": feed_ids}

        tmp = tags_index_path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(idx, f, ensure_ascii=False)
        os.replace(tmp, tags_index_path)
    except Exception:
        pass

    return {"success": True, "item": post_item, "tags": tags}

def nisb_feed_list(arguments: Dict[str, Any]) -> Dict[str, Any]:
    mode = str(arguments.get("mode") or "latest").strip()
    tag = _clean_tag(arguments.get("tag") or "")
    user_id = str(arguments.get("user_id") or "").strip()

    limit_raw = arguments.get("limit", 50)
    try:
        limit = int(limit_raw)
    except Exception:
        limit = 50
    limit = max(1, min(200, limit))

    cursor = str(arguments.get("cursor") or "").strip() or None
    before_dt = _parse_iso(cursor) if cursor else None

    if not os.path.exists(POSTS_FILE):
        return {"success": True, "items": [], "next_cursor": None, "has_more": False}

    deleted = _load_deleted_set()
    score_cache = _get_score_cache()
    buf: deque = deque(maxlen=limit + 1)

    def allow_by_status(item0: Dict[str, Any]) -> bool:
        pid = str(item0.get("id") or "")
        sc = score_cache.get(pid) or {}
        status = str(sc.get("status") or item0.get("status") or "visible")
        if mode == "mine":
            return status != "hidden"
        return status in ("visible", "visible_low")

    try:
        with open(POSTS_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    item = json.loads(line)
                except Exception:
                    continue

                pid = str(item.get("id") or "").strip()
                if not pid or pid in deleted:
                    continue

                ts = _parse_iso(str(item.get("created_at") or ""))
                if not _matches_before_cursor(ts, before_dt):
                    continue

                if mode == "mine":
                    if str((item.get("author") or {}).get("user_id") or "") != user_id:
                        continue

                if mode == "tag_filter":
                    tags = item.get("tags") or []
                    tags = [str(x) for x in tags] if isinstance(tags, list) else []
                    if not tag or tag not in tags:
                        continue

                if not allow_by_status(item):
                    continue

                buf.append(_decorate_item(item, score_cache))
    except Exception as e:
        return {"success": False, "message": f"Failed to read feed: {e!r}"}

    items = list(buf)[-limit:]
    if mode == "recommended":
        def keyfn(x: Dict[str, Any]) -> Tuple[int, str]:
            return (int(x.get("score") or 0), str(x.get("created_at") or ""))
        items.sort(key=keyfn, reverse=True)
    else:
        items.reverse()

    has_more = len(buf) > limit
    next_cursor = str(items[-1].get("created_at") or "") if items else None

    return {"success": True, "items": items, "next_cursor": next_cursor, "has_more": has_more}


def nisb_feed_list_by_tag(arguments: Dict[str, Any]) -> Dict[str, Any]:
    args = dict(arguments)
    args["mode"] = "tag_filter"
    args["tag"] = _clean_tag(arguments.get("tag") or "")
    return nisb_feed_list(args)


def nisb_feed_recommend(arguments: Dict[str, Any]) -> Dict[str, Any]:
    args = dict(arguments)
    args["mode"] = "recommended"
    return nisb_feed_list(args)


# ---------- tools (p2p content) ----------

def nisb_feed_fetch_content(arguments: Dict[str, Any]) -> Dict[str, Any]:
    user_id = str(arguments.get("user_id") or "").strip()
    basepath = str(arguments.get("basepath") or "").strip()
    feed_id = str(arguments.get("feed_id") or "").strip()

    if not user_id:
        return {"success": False, "message": "Missing user_id."}
    if not basepath:
        return {"success": False, "message": "Missing basepath."}
    if not feed_id:
        return {"success": False, "message": "Missing feed_id."}

    deleted = feed_id in _load_deleted_set()

    cache_dir = os.path.join(basepath, "feed", "cache")
    cache_path = os.path.join(cache_dir, f"{feed_id}.md")
    cache_meta_path = os.path.join(cache_dir, f"{feed_id}.meta.json")
    os.makedirs(cache_dir, exist_ok=True)

    # 1) local cache
    if os.path.exists(cache_path):
        try:
            with open(cache_path, "r", encoding="utf-8") as f:
                return {"success": True, "feed_id": feed_id, "content_md": f.read(), "cached": True, "deleted": deleted}
        except Exception as e:
            return {"success": False, "message": f"Failed to read local cache: {e!r}"}

    # 2) public snapshot
    post = _find_post(feed_id)
    if not post:
        return {"success": False, "message": f"Feed not found: {feed_id}"}

    author_uid = str((post.get("author") or {}).get("user_id") or "").strip()
    public_snapshot_path = str(post.get("public_snapshot_path") or "").strip()
    if not public_snapshot_path and author_uid:
        public_snapshot_path = os.path.join(PUBLIC_NOTES_DIR, author_uid, f"{feed_id}.md")

    if not public_snapshot_path or not os.path.exists(public_snapshot_path):
        if deleted:
            return {"success": False, "message": "Post deleted and no cached snapshot available.", "deleted": True}
        return {"success": False, "message": f"Public snapshot missing: {public_snapshot_path or '—'}"}

    try:
        with open(public_snapshot_path, "r", encoding="utf-8") as f:
            content_md = f.read()
    except Exception as e:
        return {"success": False, "message": f"Failed to read public snapshot: {e!r}"}

    # 3) write cache
    try:
        _atomic_write_text(cache_path, content_md)
        _atomic_write_json(
            cache_meta_path,
            {
                "feed_id": feed_id,
                "author_user_id": author_uid,
                "cached_at": _now_iso(),
                "deleted": deleted,
                "source": "public_snapshot",
            },
        )
    except Exception:
        return {"success": True, "feed_id": feed_id, "content_md": content_md, "cached": False, "deleted": deleted}

    return {"success": True, "feed_id": feed_id, "content_md": content_md, "cached": False, "deleted": deleted}


# ---------- tools (votes) ----------
def nisb_feed_vote(arguments: Dict[str, Any]) -> Dict[str, Any]:
    user_id = str(arguments.get("user_id") or "").strip()
    basepath = str(arguments.get("basepath") or arguments.get("base_path") or "").strip()
    feed_id = str(arguments.get("feed_id") or "").strip()
    vote_type = str(arguments.get("vote_type") or "").strip().lower()

    if not user_id:
        return {"success": False, "message": "Missing user_id."}
    if not basepath:
        return {"success": False, "message": "Missing basepath."}
    if not feed_id:
        return {"success": False, "message": "Missing feed_id."}

    # ✅ 增加 unbookmark
    if vote_type not in ("like", "bookmark", "unbookmark", "boost", "downvote", "spam"):
        return {"success": False, "message": "Invalid vote_type."}

    if feed_id in _load_deleted_set():
        return {"success": False, "message": "Post deleted."}

    created_at = _now_iso()
    ev = {
        "id": f"ev_{created_at.replace(':','').replace('-','')}_{uuid.uuid4().hex[:8]}",
        "created_at": created_at,
        "feed_id": feed_id,
        "user_id": user_id,
        "type": vote_type,
    }

    os.makedirs(FEED_DIR, exist_ok=True)
    append_jsonl(EVENTS_FILE, ev)

    interactions_file = os.path.join(basepath, "feed", "interactions.jsonl")
    os.makedirs(os.path.dirname(interactions_file), exist_ok=True)
    append_jsonl(interactions_file, ev)

    # notification（取消收藏不通知）
    if vote_type in ("like", "bookmark", "boost"):
        post = _find_post(feed_id)
        if post:
            author_uid = str((post.get("author") or {}).get("user_id") or "").strip()
            _append_notification(author_uid, user_id, vote_type, feed_id=feed_id)

    return {"success": True, "event": ev}

def nisb_feed_comment_vote(arguments: Dict[str, Any]) -> Dict[str, Any]:
    user_id = str(arguments.get("user_id") or "").strip()
    comment_id = str(arguments.get("comment_id") or "").strip()
    vote_type = str(arguments.get("vote_type") or "").strip().lower()

    if not user_id:
        return {"success": False, "message": "Missing user_id."}
    if not comment_id:
        return {"success": False, "message": "Missing comment_id."}
    if vote_type not in ("like", "downvote", "spam"):
        return {"success": False, "message": "Invalid vote_type. Use like/downvote/spam."}

    deleted_comments = _load_deleted_comment_set()
    if comment_id in deleted_comments:
        return {"success": False, "message": "Comment deleted."}

    c = _find_comment(comment_id)
    if not c:
        return {"success": False, "message": "Comment not found."}

    created_at = _now_iso()
    ev = {
        "id": f"cev_{created_at.replace(':','').replace('-','')}_{uuid.uuid4().hex[:8]}",
        "created_at": created_at,
        "comment_id": comment_id,
        "feed_id": str(c.get("feed_id") or "").strip(),
        "user_id": user_id,
        "type": vote_type,
    }

    os.makedirs(FEED_DIR, exist_ok=True)
    ok = append_jsonl(COMMENT_EVENTS_FILE, ev)
    if not ok:
        return {"success": False, "message": "Failed to append comment_events.jsonl."}

    return {"success": True, "event": ev}

# ---------- tools (comments) ----------

def nisb_feed_comment_add(arguments: Dict[str, Any]) -> Dict[str, Any]:
    user_id = str(arguments.get("user_id") or "").strip()
    feed_id = str(arguments.get("feed_id") or "").strip()
    content_md = str(arguments.get("content_md") or "").strip()
    parent_id = str(arguments.get("parent_id") or "").strip() or None

    if not user_id:
        return {"success": False, "message": "Missing user_id."}
    if not feed_id:
        return {"success": False, "message": "Missing feed_id."}
    if not content_md:
        return {"success": False, "message": "content_md is empty."}

    if feed_id in _load_deleted_set():
        return {"success": False, "message": "Post deleted."}

    post = _find_post(feed_id)
    if not post:
        return {"success": False, "message": "Post not found."}

    created_at = _now_iso()
    cid = f"cmt_{created_at.replace(':','').replace('-','')}_{uuid.uuid4().hex[:8]}"

    item = {
        "id": cid,
        "feed_id": feed_id,
        "created_at": created_at,
        "author": {"user_id": user_id},
        "parent_id": parent_id,
        "content_md": content_md,
        "excerpt": _make_excerpt(content_md, max_len=140),
    }

    os.makedirs(FEED_DIR, exist_ok=True)
    append_jsonl(COMMENTS_FILE, item)

    # notify post author
    author_uid = str((post.get("author") or {}).get("user_id") or "").strip()
    _append_notification(author_uid, user_id, "comment", feed_id=feed_id, comment_id=cid)

    # notify parent comment author (reply)
    if parent_id:
        parent = _find_comment(parent_id)
        if parent:
            parent_author = str((parent.get("author") or {}).get("user_id") or "").strip()
            _append_notification(parent_author, user_id, "reply", feed_id=feed_id, comment_id=cid)

    return {"success": True, "item": item}

def nisb_feed_comment_list(arguments: Dict[str, Any]) -> Dict[str, Any]:
    feed_id = str(arguments.get("feed_id") or "").strip()
    if not feed_id:
        return {"success": False, "message": "Missing feed_id."}

    limit_raw = arguments.get("limit", 100)
    try:
        limit = int(limit_raw)
    except Exception:
        limit = 100
    limit = max(1, min(300, limit))

    cursor = str(arguments.get("cursor") or "").strip() or None
    before_dt = _parse_iso(cursor) if cursor else None

    deleted_comments = _load_deleted_comment_set()

    buf: List[Tuple[datetime, Dict[str, Any]]] = []

    for it in _read_jsonl(COMMENTS_FILE):
        try:
            if str(it.get("feed_id") or "") != feed_id:
                continue

            cid = str(it.get("id") or "").strip()
            if not cid or cid in deleted_comments:
                continue

            ts = _parse_iso(str(it.get("created_at") or "").strip())
            if ts is None:
                continue

            if before_dt is not None and not (ts < before_dt):
                continue

            buf.append((ts, it))
        except Exception:
            continue

    buf.sort(key=lambda x: x[0], reverse=True)

    page_pairs = buf[:limit]
    items = [dict(x[1]) for x in page_pairs]

    # ✅ 评论作者昵称/头像装饰：详情页评论区全局生效
    viewer_id = str(arguments.get("user_id") or "").strip()
    cscore = _load_json(COMMENT_SCORES_FILE, {})
    out_items = []
    for c in items:
        try:
            _decorate_author_fields(c)
        except Exception:
            pass

        cid = str(c.get("id") or "").strip()
        rec = (cscore or {}).get(cid) if isinstance(cscore, dict) else None
        if not isinstance(rec, dict):
            rec = {"score": 0, "status": "visible", "counts": {"like": 0, "downvote_24h": 0, "spam_7d": 0}}

        c["score"] = int(rec.get("score") or 0)
        c["status"] = str(rec.get("status") or "visible")
        c["counts"] = rec.get("counts") or {"like": 0, "downvote_24h": 0, "spam_7d": 0}

        # visibility gate
        author_uid = str((c.get("author") or {}).get("user_id") or "").strip()
        if c["status"] in ("hidden", "quarantine") and viewer_id and author_uid != viewer_id:
            continue

        out_items.append(c)

    items = out_items

    next_cursor = None
    if page_pairs:
        last_ts = page_pairs[-1][0]
        next_cursor = last_ts.replace(microsecond=0).isoformat() + "Z"

    has_more = len(buf) > len(items)

    return {
        "success": True,
        "items": items,
        "next_cursor": next_cursor,
        "has_more": has_more,
        "nextcursor": next_cursor,
        "hasmore": has_more,
    }

def nisb_feed_comment_delete(arguments: Dict[str, Any]) -> Dict[str, Any]:
    user_id = str(arguments.get("user_id") or "").strip()
    comment_id = str(arguments.get("comment_id") or "").strip()
    if not user_id:
        return {"success": False, "message": "Missing user_id."}
    if not comment_id:
        return {"success": False, "message": "Missing comment_id."}

    c = _find_comment(comment_id)
    if not c:
        return {"success": False, "message": "Comment not found."}

    author_uid = str((c.get("author") or {}).get("user_id") or "").strip()
    if author_uid != user_id:
        return {"success": False, "message": "Forbidden: not comment author."}

    deleted_at = _now_iso()
    tomb = {
        "id": f"cdel_{deleted_at.replace(':','').replace('-','')}_{uuid.uuid4().hex[:8]}",
        "comment_id": comment_id,
        "feed_id": str(c.get("feed_id") or ""),
        "author_user_id": user_id,
        "deleted_at": deleted_at,
    }
    os.makedirs(FEED_DIR, exist_ok=True)
    append_jsonl(COMMENT_DELETIONS_FILE, tomb)
    return {"success": True, "tombstone": tomb}

# ---------- notifications actor decorate (P0) ----------
_NTF_PROFILE_CACHE: Dict[str, Tuple[float, Dict[str, Any]]] = {}


def _ntf_load_public_profile_cached(user_id: str) -> Dict[str, Any]:
    uid = str(user_id or "").strip()
    if not uid:
        return {}
    try:
        p = os.path.join(FEED_DIR, "profiles", uid, "profile.json")
        if not os.path.exists(p):
            return {}
        mtime = os.path.getmtime(p)
        hit = _NTF_PROFILE_CACHE.get(uid)
        if hit and hit[0] == mtime:
            return hit[1] or {}
        it = _load_json(p, {})
        if not isinstance(it, dict):
            it = {}
        _NTF_PROFILE_CACHE[uid] = (mtime, it)
        return it
    except Exception:
        return {}


def _decorate_notification_actor_fields(x: Dict[str, Any]) -> None:
    uid = str(x.get("actor_user_id") or "").strip()
    if not uid:
        return
    prof = _ntf_load_public_profile_cached(uid)
    dn = str((prof or {}).get("display_name") or "").strip()
    av = str((prof or {}).get("avatar_url") or "").strip()

    # 兼容两种前端读取方式
    x["actor_display_name"] = dn
    x["actor_avatar_url"] = av
    x["actor"] = {"user_id": uid, "display_name": dn, "avatar_url": av}

# ---------- tools (notifications) ----------

def nisb_feed_notifications(arguments: Dict[str, Any]) -> Dict[str, Any]:
    user_id = str(arguments.get("user_id") or "").strip()
    if not user_id:
        return {"success": False, "message": "Missing user_id."}

    limit_raw = arguments.get("limit", 50)
    try:
        limit = int(limit_raw)
    except Exception:
        limit = 50
    limit = max(1, min(200, limit))

    cursor = str(arguments.get("cursor") or "").strip() or None
    before_dt = _parse_iso(cursor) if cursor else None  # strict before

    read_ids = set()
    all_read_at: Optional[datetime] = None

    for r in _read_jsonl(NOTIFICATIONS_READ_FILE):
        if str(r.get("user_id") or "") != user_id:
            continue
        rid = str(r.get("notification_id") or "").strip()
        if rid:
            read_ids.add(rid)
        ara = r.get("all_read_at")
        if ara:
            t = _parse_iso(str(ara))
            if t and (all_read_at is None or t > all_read_at):
                all_read_at = t

    all_items: List[Dict[str, Any]] = []
    for it in _read_jsonl(NOTIFICATIONS_FILE):
        if str(it.get("user_id") or "") != user_id:
            continue
        ts = _parse_iso(str(it.get("created_at") or ""))
        if before_dt and ts and ts >= before_dt:
            continue
        all_items.append(it)

    unread_total = 0
    for it in all_items:
        nid = str(it.get("id") or "")
        ts = _parse_iso(str(it.get("created_at") or ""))
        is_read = False
        if nid in read_ids:
            is_read = True
        elif all_read_at and ts and ts <= all_read_at:
            is_read = True
        if not is_read:
            unread_total += 1

    all_items.sort(key=lambda x: str(x.get("created_at") or ""), reverse=True)
    page = all_items[:limit]

    out = []
    for it in page:
        nid = str(it.get("id") or "")
        ts = _parse_iso(str(it.get("created_at") or ""))
        is_read = False
        if nid in read_ids:
            is_read = True
        elif all_read_at and ts and ts <= all_read_at:
            is_read = True

        x = dict(it)
        x["read"] = is_read

        # ✅ P0：通知 actor 昵称/头像装饰
        try:
            _decorate_notification_actor_fields(x)
        except Exception:
            pass

        out.append(x)

    next_cursor = str(out[-1].get("created_at") or "") if out else None
    has_more = len(all_items) > len(out)

    return {
        "success": True,
        "items": out,
        "next_cursor": next_cursor,
        "has_more": has_more,
        "unread_count": int(unread_total),
    }

def nisb_feed_mark_read(arguments: Dict[str, Any]) -> Dict[str, Any]:
    user_id = str(arguments.get("user_id") or "").strip()
    notification_id = str(arguments.get("notification_id") or "").strip()
    if not user_id:
        return {"success": False, "message": "Missing user_id."}
    if not notification_id:
        return {"success": False, "message": "Missing notification_id."}

    item = {
        "id": f"nread_{_now_iso().replace(':','').replace('-','')}_{uuid.uuid4().hex[:8]}",
        "created_at": _now_iso(),
        "user_id": user_id,
        "notification_id": notification_id,
    }
    os.makedirs(FEED_DIR, exist_ok=True)
    append_jsonl(NOTIFICATIONS_READ_FILE, item)
    return {"success": True, "item": item}

def nisb_feed_mark_all_read(arguments: Dict[str, Any]) -> Dict[str, Any]:
    """
    通知：一键全部已读（通过 all_read_at 时间戳实现，不逐条写入）
    """
    user_id = str(arguments.get("user_id") or "").strip()
    if not user_id:
        return {"success": False, "message": "Missing user_id."}

    now = _now_iso()
    item = {
        "id": f"nreadall_{now.replace(':','').replace('-','')}_{uuid.uuid4().hex[:8]}",
        "created_at": now,
        "user_id": user_id,
        "all_read_at": now,
    }
    os.makedirs(FEED_DIR, exist_ok=True)
    append_jsonl(NOTIFICATIONS_READ_FILE, item)
    return {"success": True, "item": item}

# ---------- tools (follow) ----------

def nisb_feed_follow(arguments: Dict[str, Any]) -> Dict[str, Any]:
    user_id = str(arguments.get("user_id") or "").strip()
    target_user_id = str(arguments.get("target_user_id") or "").strip()
    if not user_id:
        return {"success": False, "message": "Missing user_id."}
    if not target_user_id:
        return {"success": False, "message": "Missing target_user_id."}
    if target_user_id == user_id:
        return {"success": False, "message": "Cannot follow yourself."}

    created_at = _now_iso()
    ev = {
        "id": f"fol_{created_at.replace(':','').replace('-','')}_{uuid.uuid4().hex[:8]}",
        "created_at": created_at,
        "type": "follow",
        "user_id": user_id,
        "target_user_id": target_user_id,
    }
    os.makedirs(FEED_DIR, exist_ok=True)
    append_jsonl(FOLLOWS_FILE, ev)

    _append_notification(target_user_id, user_id, "follow")
    return {"success": True, "event": ev}


def nisb_feed_unfollow(arguments: Dict[str, Any]) -> Dict[str, Any]:
    user_id = str(arguments.get("user_id") or "").strip()
    target_user_id = str(arguments.get("target_user_id") or "").strip()
    if not user_id:
        return {"success": False, "message": "Missing user_id."}
    if not target_user_id:
        return {"success": False, "message": "Missing target_user_id."}
    if target_user_id == user_id:
        return {"success": False, "message": "Cannot unfollow yourself."}

    created_at = _now_iso()
    ev = {
        "id": f"unf_{created_at.replace(':','').replace('-','')}_{uuid.uuid4().hex[:8]}",
        "created_at": created_at,
        "type": "unfollow",
        "user_id": user_id,
        "target_user_id": target_user_id,
    }
    os.makedirs(FEED_DIR, exist_ok=True)
    append_jsonl(FOLLOWS_FILE, ev)
    return {"success": True, "event": ev}


def _build_follow_graph_from_events(events: List[Dict[str, Any]]) -> Dict[str, Any]:
    # last-write-wins: follower->target
    state: Dict[Tuple[str, str], str] = {}
    for ev in events:
        tp = str(ev.get("type") or "")
        follower = str(ev.get("user_id") or "").strip()
        target = str(ev.get("target_user_id") or "").strip()
        if not follower or not target:
            continue
        if tp not in ("follow", "unfollow"):
            continue
        state[(follower, target)] = tp

    following: Dict[str, set] = defaultdict(set)
    followers: Dict[str, set] = defaultdict(set)

    for (follower, target), tp in state.items():
        if tp == "follow":
            following[follower].add(target)
            followers[target].add(follower)

    out = {}
    users = set(list(following.keys()) + list(followers.keys()))
    for u in users:
        out[u] = {
            "following": sorted(list(following.get(u, set()))),
            "followers": sorted(list(followers.get(u, set()))),
        }
    return out


def nisb_feed_following_list(arguments: Dict[str, Any]) -> Dict[str, Any]:
    user_id = str(arguments.get("user_id") or "").strip()
    if not user_id:
        return {"success": False, "message": "Missing user_id."}

    g = _load_json(FOLLOW_GRAPH_FILE, {})
    if isinstance(g, dict) and user_id in g:
        return {"success": True, "items": list(g.get(user_id, {}).get("following") or [])}

    evs = _read_jsonl(FOLLOWS_FILE)
    g2 = _build_follow_graph_from_events(evs)
    items = list(g2.get(user_id, {}).get("following") or [])
    return {"success": True, "items": items}


def nisb_feed_followers_list(arguments: Dict[str, Any]) -> Dict[str, Any]:
    user_id = str(arguments.get("user_id") or "").strip()
    if not user_id:
        return {"success": False, "message": "Missing user_id."}

    g = _load_json(FOLLOW_GRAPH_FILE, {})
    if isinstance(g, dict) and user_id in g:
        return {"success": True, "items": list(g.get(user_id, {}).get("followers") or [])}

    evs = _read_jsonl(FOLLOWS_FILE)
    g2 = _build_follow_graph_from_events(evs)
    items = list(g2.get(user_id, {}).get("followers") or [])
    return {"success": True, "items": items}

def _decorate_user_id(uid: str) -> Dict[str, Any]:
    u = str(uid or "").strip()
    prof = _load_public_profile_cached(u) if u else {}
    dn = str((prof or {}).get("display_name") or "").strip()
    av = str((prof or {}).get("avatar_url") or "").strip()
    return {"user_id": u, "display_name": dn, "avatar_url": av}


def nisb_feed_following_list_v2(arguments: Dict[str, Any]) -> Dict[str, Any]:
    """
    返回装饰后的 following 列表：[{user_id, display_name, avatar_url}, ...]
    """
    user_id = str(arguments.get("user_id") or "").strip()
    if not user_id:
        return {"success": False, "message": "Missing user_id."}

    # 复用现有 follow_graph（优先 cache）
    g = _load_json(FOLLOW_GRAPH_FILE, {})
    if isinstance(g, dict) and user_id in g:
        raw = list((g.get(user_id) or {}).get("following") or [])
    else:
        evs = _read_jsonl(FOLLOWS_FILE)
        g2 = _build_follow_graph_from_events(evs)
        raw = list((g2.get(user_id) or {}).get("following") or [])

    raw = [str(x).strip() for x in raw if str(x).strip()]
    items = [_decorate_user_id(x) for x in raw]
    return {"success": True, "items": items}


def nisb_feed_followers_list_v2(arguments: Dict[str, Any]) -> Dict[str, Any]:
    """
    返回装饰后的 followers 列表：[{user_id, display_name, avatar_url}, ...]
    """
    user_id = str(arguments.get("user_id") or "").strip()
    if not user_id:
        return {"success": False, "message": "Missing user_id."}

    g = _load_json(FOLLOW_GRAPH_FILE, {})
    if isinstance(g, dict) and user_id in g:
        raw = list((g.get(user_id) or {}).get("followers") or [])
    else:
        evs = _read_jsonl(FOLLOWS_FILE)
        g2 = _build_follow_graph_from_events(evs)
        raw = list((g2.get(user_id) or {}).get("followers") or [])

    raw = [str(x).strip() for x in raw if str(x).strip()]
    items = [_decorate_user_id(x) for x in raw]
    return {"success": True, "items": items}

# ---------- tools (delete post) ----------

def nisb_feed_delete_post(arguments: Dict[str, Any]) -> Dict[str, Any]:
    user_id = str(arguments.get("user_id") or "").strip()
    feed_id = str(arguments.get("feed_id") or "").strip()
    if not user_id:
        return {"success": False, "message": "Missing user_id."}
    if not feed_id:
        return {"success": False, "message": "Missing feed_id."}

    post = _find_post(feed_id)
    if not post:
        return {"success": False, "message": "Post not found."}

    author_uid = str((post.get("author") or {}).get("user_id") or "").strip()
    if author_uid != user_id:
        return {"success": False, "message": "Forbidden: not author."}

    deleted_at = _now_iso()
    tomb = {
        "id": f"del_{deleted_at.replace(':','').replace('-','')}_{uuid.uuid4().hex[:8]}",
        "feed_id": feed_id,
        "author_user_id": user_id,
        "deleted_at": deleted_at,
    }
    os.makedirs(FEED_DIR, exist_ok=True)
    append_jsonl(DELETIONS_FILE, tomb)

    snap = str(post.get("public_snapshot_path") or "").strip()
    if snap and os.path.exists(snap):
        try:
            os.remove(snap)
        except Exception:
            pass

    return {"success": True, "tombstone": tomb}


# ---------- tools (compact + tags) ----------

def nisb_feed_compact(arguments: Dict[str, Any]) -> Dict[str, Any]:
    os.makedirs(CACHE_DIR, exist_ok=True)
    deleted_posts = _load_deleted_set()
    deleted_comments = _load_deleted_comment_set()

    posts = _read_jsonl(POSTS_FILE)
    events = _read_jsonl(EVENTS_FILE)
    comments = _read_jsonl(COMMENTS_FILE)
    follow_events = _read_jsonl(FOLLOWS_FILE)
    comment_events = _read_jsonl(COMMENT_EVENTS_FILE)

    now = datetime.utcnow()
    win_24h = now - timedelta(hours=24)
    win_48h = now - timedelta(hours=48)
    win_7d = now - timedelta(days=7)

    like_cnt = Counter()
    bookmark_cnt = Counter()
    boost_cnt = Counter()
    downvote_24h_cnt = Counter()
    spam_7d_cnt = Counter()

    # 新增的状态字典
    bm_state: Dict[Tuple[str, str], bool] = {}

    for ev in events:
        pid = str(ev.get("feed_id") or "").strip()
        if not pid or pid in deleted_posts:
            continue
        tp = str(ev.get("type") or "").strip().lower()
        ts = _parse_iso(str(ev.get("created_at") or "")) or now

        if tp == "like":
            like_cnt[pid] += 1
        elif tp in ("bookmark", "unbookmark"):
            uid = str(ev.get("user_id") or "").strip()
            if not uid:
                continue
            key = (uid, pid)
            prev = bm_state.get(key, False)
            cur = (tp == "bookmark")
            if prev != cur:
                bm_state[key] = cur
                bookmark_cnt[pid] += (1 if cur else -1)
                if bookmark_cnt[pid] < 0:
                    bookmark_cnt[pid] = 0
        elif tp == "boost":
            boost_cnt[pid] += 1
        elif tp == "downvote":
            if ts >= win_24h:
                downvote_24h_cnt[pid] += 1
        elif tp == "spam":
            if ts >= win_7d:
                spam_7d_cnt[pid] += 1

    # 下面的代码保持不变
    comment_cnt = Counter()
    for c in comments:
        cid = str(c.get("id") or "").strip()
        if not cid or cid in deleted_comments:
            continue
        pid = str(c.get("feed_id") or "").strip()
        if not pid or pid in deleted_posts:
            continue
        comment_cnt[pid] += 1

    # 评论投票计数
    c_like = Counter()
    c_downvote_24h = Counter()
    c_spam_7d = Counter()

    for ev in comment_events:
        cid = str(ev.get("comment_id") or "").strip()
        if not cid or cid in deleted_comments:
            continue
        tp = str(ev.get("type") or "").strip().lower()
        ts = _parse_iso(str(ev.get("created_at") or "")) or now

        if tp == "like":
            c_like[cid] += 1
        elif tp == "downvote":
            if ts >= win_24h:
                c_downvote_24h[cid] += 1
        elif tp == "spam":
            if ts >= win_7d:
                c_spam_7d[cid] += 1

    comment_scores: Dict[str, Any] = {}
    for c in comments:
        cid = str(c.get("id") or "").strip()
        if not cid or cid in deleted_comments:
            continue

        score = 0
        score += 3 * c_like[cid]
        score -= 5 * c_downvote_24h[cid]
        score -= 10 * c_spam_7d[cid]

        if score >= 0:
            status = "visible"
        elif -10 < score < 0:
            status = "visible_low"
        elif -30 < score <= -10:
            status = "quarantine"
        else:
            status = "hidden"

        comment_scores[cid] = {
            "score": int(score),
            "status": status,
            "counts": {
                "like": int(c_like[cid]),
                "downvote_24h": int(c_downvote_24h[cid]),
                "spam_7d": int(c_spam_7d[cid]),
            },
        }

    _atomic_write_json(COMMENT_SCORES_FILE, comment_scores)

    post_scores: Dict[str, Any] = {}
    tags_index: Dict[str, Any] = {}
    trending = Counter()

    for p in posts:
        pid = str(p.get("id") or "").strip()
        if not pid or pid in deleted_posts:
            continue

        score = 10
        score += 3 * like_cnt[pid]
        score += 5 * bookmark_cnt[pid]
        score += 8 * boost_cnt[pid]
        score -= 5 * downvote_24h_cnt[pid]
        score -= 10 * spam_7d_cnt[pid]

        if score > 0:
            status = "visible"
        elif -20 < score <= 0:
            status = "visible_low"
        elif -50 < score <= -20:
            status = "quarantine"
        else:
            status = "hidden"

        post_scores[pid] = {
            "score": int(score),
            "status": status,
            "counts": {
                "like": int(like_cnt[pid]),
                "bookmark": int(bookmark_cnt[pid]),
                "boost": int(boost_cnt[pid]),
                "downvote_24h": int(downvote_24h_cnt[pid]),
                "spam_7d": int(spam_7d_cnt[pid]),
                "comment": int(comment_cnt[pid]),
            },
        }

        tags = p.get("tags") or []
        tags = [str(x) for x in tags] if isinstance(tags, list) else []
        tags = [t for t in [_clean_tag(x) for x in tags] if t]

        # tags_index: tag -> {count, feed_ids}
        for t in tags:
            rec = tags_index.get(t)
            if not rec:
                rec = {"count": 0, "feed_ids": []}
                tags_index[t] = rec
            rec["count"] = int(rec.get("count") or 0) + 1
            rec["feed_ids"].append(pid)

        # trending_tags: 48h
        ts = _parse_iso(str(p.get("created_at") or ""))
        if ts and ts >= win_48h:
            for t in tags:
                trending[t] += 1

    # 去重 feed_ids（防止重复 tag）
    for t, rec in list(tags_index.items()):
        try:
            ids = rec.get("feed_ids") or []
            if isinstance(ids, list):
                # 保持顺序去重
                seen = set()
                out = []
                for x in ids:
                    xs = str(x)
                    if xs and xs not in seen:
                        seen.add(xs)
                        out.append(xs)
                rec["feed_ids"] = out
                rec["count"] = int(rec.get("count") or len(out) or 0)
        except Exception:
            continue

    # follow graph cache
    follow_graph = _build_follow_graph_from_events(follow_events)

    # 原子写缓存（score/tags/trending/follow_graph）
    _atomic_write_json(POST_SCORES_FILE, post_scores)
    _atomic_write_json(TAGS_INDEX_FILE, tags_index)
    trending_out = [{"tag": k, "count": int(v)} for (k, v) in trending.most_common(80)]
    _atomic_write_json(TRENDING_TAGS_FILE, trending_out)
    _atomic_write_json(FOLLOW_GRAPH_FILE, follow_graph)

    return {
        "success": True,
        "posts": len([p for p in posts if str(p.get("id") or "").strip() and str(p.get("id") or "").strip() not in deleted_posts]),
        "events": len(events),
        "comments": len([c for c in comments if str(c.get("id") or "").strip() and str(c.get("id") or "").strip() not in deleted_comments]),
        "deleted_posts": len(deleted_posts),
        "deleted_comments": len(deleted_comments),
        "tags": len(tags_index),
        "trending": len(trending_out),
        "follow_users": len(follow_graph) if isinstance(follow_graph, dict) else 0,
        "comment_votes": len(comment_events),
        "comment_score_users": len(comment_scores),
    }

def nisb_feed_get_tags(arguments: Dict[str, Any]) -> Dict[str, Any]:
    """
    标签云：优先读取 trending_tags.json（48h），否则退化到 tags_index.json 的 count
    """
    os.makedirs(CACHE_DIR, exist_ok=True)

    if os.path.exists(TRENDING_TAGS_FILE):
        data = _load_json(TRENDING_TAGS_FILE, [])
        if isinstance(data, list):
            return {"success": True, "items": data}

    idx = _load_json(TAGS_INDEX_FILE, {})
    items = []
    if isinstance(idx, dict):
        for k, v in idx.items():
            try:
                items.append({"tag": str(k), "count": int((v or {}).get("count") or 0)})
            except Exception:
                continue
        items.sort(key=lambda x: x["count"], reverse=True)
        items = items[:80]
    return {"success": True, "items": items}

# --- Web Clipper: paste HTML -> Markdown + download images to CURRENT NOTE images/ ---
import re
import time
import hashlib
import urllib.request
import urllib.parse
from html.parser import HTMLParser
from typing import List, Tuple, Dict, Any, Optional

_IMG_EXT_RE = re.compile(r"\.(png|jpg|jpeg|webp|gif|bmp|svg)(\?.*)?$", re.IGNORECASE)


def _atomic_write_bytes(path: str, data: bytes) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "wb") as f:
        f.write(data)
    os.replace(tmp, path)


def _guess_ext_from_content_type(ct: str) -> str:
    c = (ct or "").lower().split(";")[0].strip()
    if c in ("image/png",):
        return ".png"
    if c in ("image/jpeg", "image/jpg"):
        return ".jpg"
    if c in ("image/webp",):
        return ".webp"
    if c in ("image/gif",):
        return ".gif"
    if c in ("image/bmp",):
        return ".bmp"
    if c in ("image/svg+xml", "image/svg"):
        return ".svg"
    return ""


def _guess_ext_from_url(url: str) -> str:
    p = urllib.parse.urlparse(url or "")
    ext = os.path.splitext(p.path)[1].lower()
    if ext in (".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".svg"):
        return ".jpg" if ext == ".jpeg" else ext
    return ""


def _clip_safe_filename(name: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9_\-\.]+", "_", str(name or "")).strip("_")
    return s[:180] if s else "img"


def _pick_best_from_srcset(srcset: str) -> str:
    """
    解析 srcset，优先挑最大的 width / 最大的 x。
    格式示例：
      url1 320w, url2 640w
      url1 1x, url2 2x
    """
    s = (srcset or "").strip()
    if not s:
        return ""
    parts = [p.strip() for p in s.split(",") if p.strip()]
    best_url = ""
    best_score = -1.0
    for part in parts:
        toks = part.split()
        if not toks:
            continue
        u = toks[0].strip()
        score = 0.0
        if len(toks) >= 2:
            d = toks[1].strip().lower()
            if d.endswith("w"):
                try:
                    score = float(d[:-1])
                except Exception:
                    score = 0.0
            elif d.endswith("x"):
                try:
                    score = float(d[:-1]) * 10000.0
                except Exception:
                    score = 0.0
        if score > best_score:
            best_score = score
            best_url = u
    return best_url


def _is_probably_image_url(u: str) -> bool:
    if not u:
        return False
    if u.startswith("data:") or u.startswith("blob:"):
        return False
    return bool(_IMG_EXT_RE.search(u)) or "/image" in u.lower()


def _extract_fragment(html_text: str) -> str:
    h = html_text or ""
    m1 = re.search(r"<!--\s*StartFragment\s*-->", h, re.IGNORECASE)
    m2 = re.search(r"<!--\s*EndFragment\s*-->", h, re.IGNORECASE)
    if m1 and m2 and m2.start() > m1.end():
        return h[m1.end() : m2.start()].strip()
    return h.strip()


class _ClipNode:
    __slots__ = ("tag", "attrs", "children", "text")

    def __init__(self, tag: str, attrs: Dict[str, str] = None, text: str = ""):
        self.tag = tag
        self.attrs = attrs or {}
        self.children: List["_ClipNode"] = []
        self.text = text


class _ClipHTMLParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = _ClipNode("root")
        self.stack = [self.root]

    def handle_starttag(self, tag, attrs):
        tag = (tag or "").lower()
        a = {}
        for k, v in (attrs or []):
            if not k:
                continue
            a[str(k).lower()] = "" if v is None else str(v)
        node = _ClipNode(tag, a)
        self.stack[-1].children.append(node)
        # 自闭合类不入栈
        if tag in ("br", "img", "hr", "meta", "link", "input"):
            return
        self.stack.append(node)

    def handle_endtag(self, tag):
        tag = (tag or "").lower()
        for i in range(len(self.stack) - 1, 0, -1):
            if self.stack[i].tag == tag:
                self.stack = self.stack[:i]
                return

    def handle_data(self, data):
        t = str(data or "")
        if not t:
            return
        self.stack[-1].children.append(_ClipNode("#text", text=t))


def _md_escape_text(s: str) -> str:
    # 只做最基础的转义，避免破坏 Markdown 结构
    return (s or "").replace("\r", "")


def _normalize_url(u: str, base_url: str) -> str:
    u = (u or "").strip()
    if not u:
        return ""
    if u.startswith("data:") or u.startswith("blob:"):
        return ""
    if base_url:
        try:
            return urllib.parse.urljoin(base_url, u)
        except Exception:
            return u
    return u


def _norm_rel_path(p: str) -> str:
    s = str(p or "").strip().replace("\\", "/")
    s = s.lstrip("/")
    s = re.sub(r"/+", "/", s)
    return s


def _ensure_safe_under_basepath(basepath: str, rel_path: str) -> str:
    """
    rel_path: 相对 basepath 的相对路径（不允许以 / 开头）
    返回：规范化后的 abs_path
    """
    base_abs = os.path.normpath(str(basepath or "").rstrip("/"))
    rel_norm = _norm_rel_path(rel_path)

    if not base_abs:
        raise ValueError("empty basepath")

    # 禁止空 / 目录穿越
    if not rel_norm:
        raise ValueError("empty path")
    if rel_norm.startswith("..") or "/../" in rel_norm or rel_norm.endswith("/.."):
        raise ValueError("path traversal")

    abs_path = os.path.normpath(os.path.join(base_abs, rel_norm))

    # 必须仍在 basepath 内
    if abs_path != base_abs and not abs_path.startswith(base_abs + os.sep):
        raise ValueError("outside basepath")

    return abs_path


def _note_images_rel_dir(note_path: str) -> str:
    """
    note_path: 相对 basepath 的 md 路径，如 agent_files/docs/markdown/a.md
    返回：同目录 images/ 的相对目录，如 agent_files/docs/markdown/images
    """
    np = _norm_rel_path(note_path)
    if not np:
        raise ValueError("Missing note_path.")
    if not np.lower().endswith(".md"):
        raise ValueError("note_path must be a .md file.")
    note_dir = os.path.dirname(np).replace("\\", "/").strip("/")
    if note_dir:
        return f"{note_dir}/images"
    return "images"


def _download_image_to_note_images(
    url: str,
    basepath: str,
    note_path: str,
    timeout: float = 15.0,
    max_bytes: int = 25 * 1024 * 1024,
) -> Tuple[str, Dict[str, Any]]:
    """
    下载远程图片 -> /data/users/{uid}/<note_dir>/images/
    返回：(rel_path, meta)
      rel_path: <note_dir>/images/xxx.png
    """
    u = (url or "").strip()
    if not u:
        return "", {"url": url, "ok": False, "reason": "empty url"}

    try:
        rel_dir = _note_images_rel_dir(note_path)
    except Exception as e:
        return "", {"url": url, "ok": False, "reason": str(e)}

    req = urllib.request.Request(
        u,
        headers={
            "User-Agent": "NISB-FeedClipper/1.0",
            "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
        },
        method="GET",
    )

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            ct = resp.headers.get("Content-Type") or ""
            data = resp.read(max_bytes + 1)
            if len(data) > max_bytes:
                return "", {"url": url, "ok": False, "reason": "image too large"}

            ext = _guess_ext_from_content_type(ct) or _guess_ext_from_url(u) or ".png"
            ts = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
            h = hashlib.sha1((u + str(len(data))).encode("utf-8")).hexdigest()[:10]
            fn = _clip_safe_filename(f"img_{ts}_{h}{ext}")

            rel = f"{rel_dir}/{fn}".replace("\\", "/").lstrip("/")
            abs_path = _ensure_safe_under_basepath(basepath, rel)

            os.makedirs(os.path.dirname(abs_path), exist_ok=True)
            _atomic_write_bytes(abs_path, data)

            return rel, {
                "url": url,
                "ok": True,
                "filename": fn,
                "bytes": len(data),
                "content_type": ct,
            }
    except Exception as e:
        return "", {"url": url, "ok": False, "reason": str(e)}


def _convert_node_to_md(
    node: _ClipNode,
    base_url: str,
    basepath: str,
    note_path: str,
    link_stack: List[str],
    saved: List[Dict[str, Any]],
) -> str:
    tag = node.tag

    if tag == "#text":
        return _md_escape_text(node.text)

    if tag in ("script", "style"):
        return ""

    if tag in ("br",):
        return "  \n"

    if tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
        level = int(tag[1]) if len(tag) == 2 and tag[1].isdigit() else 2
        inner = "".join(
            _convert_node_to_md(c, base_url, basepath, note_path, link_stack, saved)
            for c in node.children
        ).strip()
        if not inner:
            return ""
        return "\n\n" + ("#" * level) + " " + inner + "\n\n"

    if tag in ("p", "div", "section", "article"):
        inner = "".join(
            _convert_node_to_md(c, base_url, basepath, note_path, link_stack, saved)
            for c in node.children
        ).strip()
        if not inner:
            return ""
        return "\n\n" + inner + "\n\n"

    if tag in ("strong", "b"):
        inner = "".join(
            _convert_node_to_md(c, base_url, basepath, note_path, link_stack, saved)
            for c in node.children
        ).strip()
        return f"**{inner}**" if inner else ""

    if tag in ("em", "i"):
        inner = "".join(
            _convert_node_to_md(c, base_url, basepath, note_path, link_stack, saved)
            for c in node.children
        ).strip()
        return f"*{inner}*" if inner else ""

    if tag == "a":
        href = (node.attrs.get("href") or "").strip()
        href = _normalize_url(href, base_url)
        link_stack.append(href)
        inner = "".join(
            _convert_node_to_md(c, base_url, basepath, note_path, link_stack, saved)
            for c in node.children
        ).strip()
        link_stack.pop()
        if not inner:
            inner = href
        if href:
            return f"[{inner}]({href})"
        return inner

    if tag == "ul":
        lines = []
        for c in node.children:
            if c.tag == "li":
                li = _convert_node_to_md(c, base_url, basepath, note_path, link_stack, saved).strip()
                if li:
                    lines.append(f"- {li}")
        return "\n\n" + "\n".join(lines) + "\n\n" if lines else ""

    if tag == "ol":
        lines = []
        for c in node.children:
            if c.tag == "li":
                li = _convert_node_to_md(c, base_url, basepath, note_path, link_stack, saved).strip()
                if li:
                    lines.append(f"1. {li}")
        return "\n\n" + "\n".join(lines) + "\n\n" if lines else ""

    if tag == "li":
        inner = "".join(
            _convert_node_to_md(c, base_url, basepath, note_path, link_stack, saved)
            for c in node.children
        ).strip()
        return inner

    if tag == "img":
        alt = (node.attrs.get("alt") or "image").strip() or "image"

        # 选“更大图”的启发式顺序：
        # 1) 外层 a[href]（最近的链接）且看起来像图片
        # 2) data-original / data-src / data-lazy-src
        # 3) srcset 最大候选
        # 4) src
        a_href = ""
        for u in reversed(link_stack):
            if _is_probably_image_url(u):
                a_href = u
                break

        data_src = (
            (node.attrs.get("data-original") or "").strip()
            or (node.attrs.get("data-src") or "").strip()
            or (node.attrs.get("data-lazy-src") or "").strip()
        )
        srcset_best = _pick_best_from_srcset(node.attrs.get("srcset") or "")
        src = (node.attrs.get("src") or "").strip()

        cand = a_href or data_src or srcset_best or src
        cand = _normalize_url(cand, base_url)

        if not cand:
            return ""

        rel, meta = _download_image_to_note_images(cand, basepath=basepath, note_path=note_path)
        saved.append(meta)

        if rel:
            return f"\n\n![{alt}](nisb://file?path={rel})\n\n"
        return ""

    # 兜底：递归拼接子节点文本
    return "".join(
        _convert_node_to_md(c, base_url, basepath, note_path, link_stack, saved) for c in node.children
    )


def _html_clip_to_markdown(html_text: str, base_url: str, basepath: str, note_path: str) -> Tuple[str, List[Dict[str, Any]]]:
    fragment = _extract_fragment(html_text)
    parser = _ClipHTMLParser()
    try:
        parser.feed(fragment)
    except Exception:
        # 如果 HTML 解析失败，退回纯文本（尽量不阻断）
        txt = re.sub(r"<[^>]+>", " ", fragment)
        return txt.strip(), []

    saved: List[Dict[str, Any]] = []
    md = "".join(_convert_node_to_md(c, base_url, basepath, note_path, [], saved) for c in parser.root.children)

    # 清理多余空行
    md = re.sub(r"\n{4,}", "\n\n\n", md).strip()
    return md, saved


def nisb_feed_clipboard_import(arguments: Dict[str, Any]) -> Dict[str, Any]:
    """
    Web clipper: convert pasted HTML to Markdown and download images to <note_dir>/images.
    - Input: html (required), note_path (required), base_url (optional)
    - Output: markdown (md), saved_images (meta list)
    """
    user_id = str(arguments.get("user_id") or "").strip()
    basepath = str(arguments.get("basepath") or "").strip()
    if not user_id:
        return {"success": False, "message": "Missing user_id."}
    if not basepath:
        return {"success": False, "message": "Missing basepath."}

    note_path = str(arguments.get("note_path") or "").strip()
    if not note_path:
        return {"success": False, "message": "Missing note_path. Please save the note first."}

    html_text = str(arguments.get("html") or "").strip()
    if not html_text:
        return {"success": False, "message": "Missing html."}

    base_url = str(arguments.get("base_url") or "").strip()

    # ensure images dir exists
    try:
        rel_dir = _note_images_rel_dir(note_path)
        abs_dir = _ensure_safe_under_basepath(basepath, rel_dir)
        os.makedirs(abs_dir, exist_ok=True)
    except Exception as e:
        return {"success": False, "message": f"Invalid note_path: {e}"}

    md, saved = _html_clip_to_markdown(html_text, base_url=base_url, basepath=basepath, note_path=note_path)
    if not md:
        return {"success": False, "message": "No content extracted."}

    ok_saved = [x for x in saved if isinstance(x, dict) and x.get("ok")]

    return {
        "success": True,
        "markdown": md,
        "saved_images": saved,
        "saved_ok": len(ok_saved),
        "saved_total": len(saved),
    }


# ---------- Profile & Bookmarks (P0) ----------

PROFILES_DIR = os.path.join(FEED_DIR, "profiles")

# ---------- Profile cache (P0: author decorate) ----------
_PROFILE_CACHE: Dict[str, Tuple[float, Dict[str, Any]]] = {}


def _load_public_profile_cached(user_id: str) -> Dict[str, Any]:
    uid = str(user_id or "").strip()
    if not uid:
        return {}

    try:
        p = _public_profile_path(uid)  # 你指南01里已定义：PROFILES_DIR/{uid}/profile.json
        if not os.path.exists(p):
            return {}

        mtime = os.path.getmtime(p)
        hit = _PROFILE_CACHE.get(uid)
        if hit and hit[0] == mtime:
            return hit[1] or {}

        it = _load_json(p, {})
        if not isinstance(it, dict):
            it = {}

        _PROFILE_CACHE[uid] = (mtime, it)
        return it
    except Exception:
        return {}


def _decorate_author_fields(out: Dict[str, Any]) -> None:
    author = out.get("author")
    uid = ""
    if isinstance(author, str):
        uid = author.strip()
        author_obj: Dict[str, Any] = {"user_id": uid} if uid else {}
        out["author"] = author_obj
        author = author_obj
    elif isinstance(author, dict):
        uid = str(author.get("user_id") or author.get("userId") or author.get("id") or "").strip()
    else:
        uid = ""

    if not uid:
        return

    prof = _load_public_profile_cached(uid)
    if not prof:
        return

    dn = str(prof.get("display_name") or "").strip()
    av = str(prof.get("avatar_url") or "").strip()

    # 兼容前端两种读取方式
    out["author_display_name"] = dn
    out["author_avatar_url"] = av

    if isinstance(out.get("author"), dict):
        out["author"]["display_name"] = dn
        out["author"]["avatar_url"] = av


def _clean_display_name(s: str) -> str:
    s = str(s or "").strip()
    s = re.sub(r"\s+", " ", s)
    # 允许中英文、数字、空格、-_.
    s = re.sub(r"[^\w\u4e00-\u9fa5\-\._ ]+", "", s).strip()
    if not s:
        return ""
    if len(s) > 32:
        s = s[:32].strip()
    return s


def _clean_bio(s: str) -> str:
    s = str(s or "").strip()
    s = re.sub(r"\s+", " ", s).strip()
    if len(s) > 160:
        s = s[:160].strip()
    return s


def _private_profile_path(basepath: str) -> str:
    return os.path.join(str(basepath).rstrip("/"), "profile.json")


def _public_profile_path(user_id: str) -> str:
    return os.path.join(PROFILES_DIR, str(user_id), "profile.json")


def nisb_feed_get_profile(arguments: Dict[str, Any]) -> Dict[str, Any]:
    """
    获取个人资料：
    - target_user_id 为空：返回自己的（优先私有 profile.json）
    - target_user_id 非空：返回对方的（读 public snapshot）
    """
    user_id = str(arguments.get("user_id") or "").strip()
    basepath = str(arguments.get("basepath") or "").strip()
    target = str(arguments.get("target_user_id") or "").strip() or user_id
    if not user_id:
        return {"success": False, "message": "Missing user_id."}
    if not target:
        return {"success": False, "message": "Missing target_user_id."}

    # 自己：优先私有
    if target == user_id and basepath:
        pvt = _private_profile_path(basepath)
        if os.path.exists(pvt):
            it = _load_json(pvt, {})
            if isinstance(it, dict) and it.get("user_id"):
                return {"success": True, "item": it, "scope": "private"}

    # 公开：读 public snapshot
    pub = _public_profile_path(target)
    if os.path.exists(pub):
        it = _load_json(pub, {})
        if isinstance(it, dict) and it.get("user_id"):
            return {"success": True, "item": it, "scope": "public"}

    # fallback：最小信息
    return {
        "success": True,
        "item": {
            "user_id": target,
            "display_name": "",
            "bio": "",
            "avatar_url": "",
            "updated_at": "",
        },
        "scope": "fallback",
    }


def nisb_feed_update_profile(arguments: Dict[str, Any]) -> Dict[str, Any]:
    """
    更新自己的个人资料（写私有 + 写公开快照）
    """
    user_id = str(arguments.get("user_id") or "").strip()
    basepath = str(arguments.get("basepath") or "").strip()
    if not user_id:
        return {"success": False, "message": "Missing user_id."}
    if not basepath:
        return {"success": False, "message": "Missing basepath."}

    display_name = _clean_display_name(arguments.get("display_name") or "")
    bio = _clean_bio(arguments.get("bio") or "")
    avatar_url = str(arguments.get("avatar_url") or "").strip()
    if len(avatar_url) > 400:
        avatar_url = avatar_url[:400].strip()

    now = _now_iso()
    item = {
        "user_id": user_id,
        "display_name": display_name,
        "bio": bio,
        "avatar_url": avatar_url,
        "updated_at": now,
    }

    # 私有
    pvt = _private_profile_path(basepath)
    os.makedirs(os.path.dirname(pvt), exist_ok=True)
    _atomic_write_json(pvt, item)

    # 公开快照
    pub = _public_profile_path(user_id)
    os.makedirs(os.path.dirname(pub), exist_ok=True)
    _atomic_write_json(pub, item)

    return {"success": True, "item": item}


def nisb_feed_list_bookmarks(arguments: Dict[str, Any]) -> Dict[str, Any]:
    user_id = str(arguments.get("user_id") or "").strip()
    basepath = str(arguments.get("basepath") or "").strip()
    if not user_id:
        return {"success": False, "message": "Missing user_id."}
    if not basepath:
        return {"success": False, "message": "Missing basepath."}

    limit_raw = arguments.get("limit", 50)
    try:
        limit = int(limit_raw)
    except Exception:
        limit = 50
    limit = max(1, min(200, limit))

    cursor = str(arguments.get("cursor") or "").strip() or None
    before_dt = _parse_iso(cursor) if cursor else None  # bookmark_at strict before

    interactions_file = os.path.join(basepath, "feed", "interactions.jsonl")
    if not os.path.exists(interactions_file):
        return {"success": True, "items": [], "next_cursor": None, "has_more": False}

    deleted_posts = _load_deleted_set()

    # ✅ last-write-wins：bookmark / unbookmark
    state: Dict[str, Tuple[bool, datetime]] = {}  # feed_id -> (bookmarked?, ts)
    for ev in _read_jsonl(interactions_file):
        tp = str(ev.get("type") or "").strip().lower()
        if tp not in ("bookmark", "unbookmark"):
            continue
        fid = str(ev.get("feed_id") or "").strip()
        if not fid or fid in deleted_posts:
            continue
        ts = _parse_iso(str(ev.get("created_at") or ""))
        if not ts:
            continue
        state[fid] = (tp == "bookmark", ts)

    pairs: List[Tuple[datetime, str]] = []
    for fid, (on, ts) in state.items():
        if on:
            pairs.append((ts, fid))

    pairs.sort(key=lambda x: x[0], reverse=True)
    if before_dt:
        pairs = [(ts, fid) for (ts, fid) in pairs if ts < before_dt]

    page_pairs = pairs[:limit]
    has_more = len(pairs) > len(page_pairs)

    need_ids = set([fid for (_, fid) in page_pairs])
    if not need_ids:
        return {"success": True, "items": [], "next_cursor": None, "has_more": False}

    posts_map: Dict[str, Dict[str, Any]] = {}
    for p in _read_jsonl(POSTS_FILE):
        pid = str(p.get("id") or "").strip()
        if pid and pid in need_ids and pid not in deleted_posts:
            posts_map[pid] = p

    score_cache = _get_score_cache()
    items: List[Dict[str, Any]] = []
    for (ts, fid) in page_pairs:
        p = posts_map.get(fid)
        if not p:
            continue
        it = _decorate_item(p, score_cache)
        it["bookmark_at"] = ts.replace(microsecond=0).isoformat() + "Z"
        it["bookmarked"] = True
        items.append(it)

    items.sort(key=lambda x: str(x.get("bookmark_at") or ""), reverse=True)
    next_cursor = str(items[-1].get("bookmark_at") or "") if items else None
    return {"success": True, "items": items, "next_cursor": next_cursor, "has_more": has_more}


import base64

AVATARS_DIR = os.path.join(FEED_DIR, "avatars")


def _guess_ext(data: bytes) -> Optional[str]:
    if len(data) >= 12 and data[:8] == b"\x89PNG\r\n\x1a\n":
        return "png"
    if len(data) >= 3 and data[:3] == b"\xff\xd8\xff":
        return "jpg"
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "webp"
    return None


def nisb_feed_avatar_upload(arguments: Dict[str, Any]) -> Dict[str, Any]:
    """
    Avatar 上传（MVP）：
    - 输入：image_base64（允许 data:image/...;base64, 前缀）
    - 输出：avatar_url = /api/feed/avatars/{uid}?v=...
    """
    user_id = str(arguments.get("user_id") or "").strip()
    if not user_id:
        return {"success": False, "message": "Missing user_id."}

    image_base64 = str(arguments.get("image_base64") or "").strip()
    if not image_base64:
        return {"success": False, "message": "Missing image_base64."}

    if "," in image_base64 and "base64" in image_base64.split(",")[0]:
        image_base64 = image_base64.split(",", 1)[1].strip()

    try:
        raw = base64.b64decode(image_base64, validate=True)
    except Exception:
        return {"success": False, "message": "Invalid base64."}

    if len(raw) > 2 * 1024 * 1024:
        return {"success": False, "message": "Image too large (>2MB)."}

    ext = _guess_ext(raw)
    if ext not in ("png", "jpg", "webp"):
        return {"success": False, "message": "Unsupported image type (png/jpg/webp only)."}

    os.makedirs(AVATARS_DIR, exist_ok=True)

    # 清理旧文件（不同 ext）
    try:
        for e in ("png", "jpg", "webp"):
            p = os.path.join(AVATARS_DIR, f"{user_id}.{e}")
            if os.path.exists(p):
                os.remove(p)
    except Exception:
        pass

    path = os.path.join(AVATARS_DIR, f"{user_id}.{ext}")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(prefix=".tmp_", dir=os.path.dirname(path))
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(raw)
        os.replace(tmp_path, path)
    finally:
        try:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
        except Exception:
            pass

    v = _now_iso()
    avatar_url = f"/api/feed/avatars/{user_id}?v={v}"
    return {"success": True, "user_id": user_id, "avatar_url": avatar_url, "updated_at": v}


# ---------- Feed Image Pipeline (P0) ----------
import tempfile as _tmp2  # avoid shadow
import uuid as _uuid2

# 旧常量保留：用于历史内容（agent_files/feed_images）
USER_STAGE_REL_DIR = os.path.join("agent_files", "feed_images")
FEED_ASSETS_DIR = os.path.join(FEED_DIR, "assets", "images")  # /data/shared/feed/assets/images


def _guess_img_ext(data: bytes) -> Optional[str]:
    if len(data) >= 12 and data[:8] == b"\x89PNG\r\n\x1a\n":
        return "png"
    if len(data) >= 3 and data[:3] == b"\xff\xd8\xff":
        return "jpg"
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "webp"
    return None


def _feed_safe_filename(name: str) -> str:
    s = str(name or "").strip()
    s = re.sub(r"\s+", "_", s)
    s = re.sub(r"[^a-zA-Z0-9_\-\.]+", "", s)
    if len(s) > 80:
        s = s[:80]
    return s


def _parse_nisb_file_url(src: str) -> str:
    """
    支持：
    - nisb://file?path=...
    - nisb://file/<path>
    返回相对路径（相对 basepath）
    """
    h = str(src or "").strip()
    if not h.lower().startswith("nisb://"):
        return ""
    try:
        u = __import__("urllib.parse", fromlist=["urlparse", "parse_qs"]).urlparse(h)
        if str(u.netloc or "").lower() != "file":
            return ""
        qs = __import__("urllib.parse", fromlist=["parse_qs"]).parse_qs(u.query or "")
        if "path" in qs and qs["path"]:
            return str(qs["path"][0] or "").lstrip("/")
        p = str(u.path or "").lstrip("/")
        return p
    except Exception:
        return ""


def nisb_feed_image_stage_upload(arguments: Dict[str, Any]) -> Dict[str, Any]:
    """
    Note/Feed: 上传图片到“当前 Markdown 文档同目录的 images/”
    - 输入：note_path（必填，当前 md 相对 basepath 的路径），image_base64（必填），filename/alt 可选
    - 输出：markdown = ![alt](nisb://file?path=<note_dir>/images/xxx.png)
    """
    user_id = str(arguments.get("user_id") or "").strip()
    basepath = str(arguments.get("basepath") or "").strip()
    if not user_id:
        return {"success": False, "message": "Missing user_id."}
    if not basepath:
        return {"success": False, "message": "Missing basepath."}

    note_path = str(arguments.get("note_path") or "").strip()
    if not note_path:
        return {"success": False, "message": "Missing note_path. Please save the note first."}

    image_base64 = str(arguments.get("image_base64") or "").strip()
    if not image_base64:
        return {"success": False, "message": "Missing image_base64."}

    filename = _feed_safe_filename(arguments.get("filename") or "")
    alt = str(arguments.get("alt") or "image").strip() or "image"
    if len(alt) > 60:
        alt = alt[:60].strip()

    if "," in image_base64 and "base64" in image_base64.split(",", 1)[0]:
        image_base64 = image_base64.split(",", 1)[1].strip()

    try:
        raw = base64.b64decode(image_base64, validate=True)
    except Exception:
        return {"success": False, "message": "Invalid base64."}

    if len(raw) > 6 * 1024 * 1024:
        return {"success": False, "message": "Image too large (>6MB)."}

    ext = _guess_img_ext(raw)
    if ext not in ("png", "jpg", "webp"):
        return {"success": False, "message": "Unsupported image type (png/jpg/webp only)."}

    created_at = _now_iso()
    img_id = f"img_{created_at.replace(':','').replace('-','')}_{_uuid2.uuid4().hex[:10]}"

    if filename and "." in filename:
        filename = filename.rsplit(".", 1)[0]
    if filename:
        out_name = f"{img_id}_{filename}.{ext}"
    else:
        out_name = f"{img_id}.{ext}"

    try:
        rel_dir = _note_images_rel_dir(note_path)
        rel_path = f"{rel_dir}/{out_name}".replace("\\", "/").lstrip("/")
        abs_dir = _ensure_safe_under_basepath(basepath, rel_dir)
        abs_path = _ensure_safe_under_basepath(basepath, rel_path)
    except Exception as e:
        return {"success": False, "message": f"Invalid note_path: {e}"}

    os.makedirs(abs_dir, exist_ok=True)

    fd, tmp_path = _tmp2.mkstemp(prefix=".tmp_", dir=abs_dir)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(raw)
        os.replace(tmp_path, abs_path)
    finally:
        try:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
        except Exception:
            pass

    src = f"nisb://file?path={rel_path}"
    md = f"![{alt}]({src})"
    return {
        "success": True,
        "user_id": user_id,
        "note_path": _norm_rel_path(note_path),
        "rel_path": rel_path,
        "src": src,
        "markdown": md,
        "created_at": created_at,
    }

def _path_is_allowed_note_image(rel_norm: str) -> bool:
    """
    allow:
      - agent_files/feed_images/...           (legacy)
      - images/...                            (note at root)
      - agent_files/**/images/**              (common)
      - agent_files/**/<stem>_images/**       (epub/pdf book-specific images dir)
      - agent_files/**/images/**/<...>        (split mode subdirs)
    """
    s = _norm_rel_path(rel_norm)

    # legacy: agent_files/feed_images/...
    allow_legacy = USER_STAGE_REL_DIR.replace("\\", "/").rstrip("/") + "/"
    if s.startswith(allow_legacy):
        return True

    # root images/
    if s.startswith("images/"):
        return True

    # must be under agent_files/ for the rest
    if not s.startswith("agent_files/"):
        return False

    # 1) allow any ".../images/..." (existing behavior)
    if "/images/" in ("/" + s):
        return True

    # 2) allow any path segment that ends with "_images"
    #    e.g. agent_files/tese_epub/epub/ceshi_images/00001.jpg
    parts = [p for p in s.split("/") if p]
    for p in parts[:-1]:  # ignore filename part
        if p.endswith("_images"):
            return True

    return False

def nisb_feed_user_file_base64(arguments: Dict[str, Any]) -> Dict[str, Any]:
    """
    Note/Feed: 读取用户图片并返回 data_url（用于前端渲染 img）
    安全限制：
    - 允许 agent_files/feed_images/...
    - 允许 agent_files/**/images/** 以及 images/**
    输入：path（相对 basepath），也允许传 src=nisb://file?path=...
    """
    user_id = str(arguments.get("user_id") or "").strip()
    basepath = str(arguments.get("basepath") or "").strip()
    if not user_id:
        return {"success": False, "message": "Missing user_id."}
    if not basepath:
        return {"success": False, "message": "Missing basepath."}

    src = str(arguments.get("src") or "").strip()
    rel = str(arguments.get("path") or "").strip().lstrip("/")
    if src and not rel:
        rel = _parse_nisb_file_url(src)

    if not rel:
        return {"success": False, "message": "Missing path."}

    rel_norm = _norm_rel_path(rel)
    if not _path_is_allowed_note_image(rel_norm):
        return {"success": False, "message": "Forbidden path."}

    try:
        abs_path = _ensure_safe_under_basepath(basepath, rel_norm)
    except Exception:
        return {"success": False, "message": "Forbidden path."}

    if not os.path.exists(abs_path):
        return {"success": False, "message": "File not found."}

    try:
        with open(abs_path, "rb") as f:
            raw = f.read()
    except Exception as e:
        return {"success": False, "message": f"Read failed: {e!r}"}

    if len(raw) > 8 * 1024 * 1024:
        return {"success": False, "message": "File too large (>8MB)."}

    ext = (os.path.splitext(abs_path)[1] or "").lower().lstrip(".")
    mime = "application/octet-stream"
    if ext == "png":
        mime = "image/png"
    elif ext in ("jpg", "jpeg"):
        mime = "image/jpeg"
    elif ext == "webp":
        mime = "image/webp"
    elif ext == "gif":
        mime = "image/gif"
    elif ext == "svg":
        mime = "image/svg+xml"

    b64 = base64.b64encode(raw).decode("ascii")
    data_url = f"data:{mime};base64,{b64}"
    return {"success": True, "mime": mime, "data_url": data_url, "path": rel_norm}


def _feed_promote_images_in_markdown(content_md: str, basepath: str, user_id: str, feed_id: str) -> str:
    """
    发布时晋升：
    - 允许晋升 agent_files/feed_images/...
    - 允许晋升 agent_files/**/images/** 以及 images/**
    """
    text = str(content_md or "")
    if "nisb://file" not in text:
        return text

    pattern = re.compile(r"!\[([^\]]*)\]\(([^)]+)\)")
    matches = list(pattern.finditer(text))
    if not matches:
        return text

    out_text = text
    created_at = _now_iso()

    for m in matches[::-1]:
        url = str(m.group(2) or "").strip()
        rel = _parse_nisb_file_url(url)
        if not rel:
            continue

        rel_norm = _norm_rel_path(rel)
        if not _path_is_allowed_note_image(rel_norm):
            continue

        try:
            src_abs = _ensure_safe_under_basepath(basepath, rel_norm)
        except Exception:
            continue

        if not os.path.exists(src_abs):
            continue

        filename = os.path.basename(rel_norm)
        dst_dir = os.path.join(FEED_ASSETS_DIR, user_id, feed_id)
        os.makedirs(dst_dir, exist_ok=True)
        dst_abs = os.path.join(dst_dir, filename)

        fd, tmp_path = _tmp2.mkstemp(prefix=".tmp_", dir=dst_dir)
        try:
            with open(src_abs, "rb") as fsrc, os.fdopen(fd, "wb") as fdst:
                fdst.write(fsrc.read())
            os.replace(tmp_path, dst_abs)
        finally:
            try:
                if os.path.exists(tmp_path):
                    os.unlink(tmp_path)
            except Exception:
                pass

        new_url = f"/api/feed/assets/images/{user_id}/{feed_id}/{filename}?v={created_at}"
        start, end = m.span(2)
        out_text = out_text[:start] + new_url + out_text[end:]

    return out_text
