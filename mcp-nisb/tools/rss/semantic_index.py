from __future__ import annotations

import json
import math
import os
import re
import hashlib
import time
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional

_WORD_RE = re.compile(r"[A-Za-z0-9_]+", re.UNICODE)
DATA_ROOT = os.environ.get("NISBBASEPATH", "/data").rstrip("/")
USERS_ROOT = os.path.join(DATA_ROOT, "users")


def _safe_mkdir(p: str) -> None:
    os.makedirs(p, exist_ok=True)


def _read_jsonl(path: str) -> Iterable[Dict[str, Any]]:
    if not os.path.exists(path):
        return []

    def _iter():
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

    return _iter()


def _write_jsonl(path: str, rows: Iterable[Dict[str, Any]]) -> None:
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    os.replace(tmp, path)


def _append_jsonl(path: str, row: Dict[str, Any]) -> None:
    _safe_mkdir(os.path.dirname(path))
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def _tokenize(text: str) -> List[str]:
    t = (text or "").strip().lower()
    if not t:
        return []
    tokens: List[str] = []
    tokens.extend(_WORD_RE.findall(t))
    for ch in t:
        o = ord(ch)
        if 0x4E00 <= o <= 0x9FFF:
            tokens.append(ch)
    return tokens


def _hash_vec(tokens: List[str], dim: int = 512) -> List[float]:
    if not tokens:
        return [0.0] * dim
    vec = [0.0] * dim
    for tok in tokens:
        h = hashlib.md5(tok.encode("utf-8")).hexdigest()
        idx = int(h[:8], 16) % dim
        sign = -1.0 if (int(h[8:10], 16) % 2 == 1) else 1.0
        vec[idx] += sign
    norm = math.sqrt(sum(x * x for x in vec)) or 1.0
    return [x / norm for x in vec]


def cosine(a: List[float], b: List[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    return float(sum(x * y for x, y in zip(a, b)))


def build_item_text(item: Dict[str, Any]) -> str:
    title = str(item.get("title") or "")
    summary = str(item.get("summary") or item.get("content") or "")
    summary = summary.strip()
    if len(summary) > 2000:
        summary = summary[:2000]
    return (title + "\n" + summary).strip()


def rss_user_dir(uid: str) -> str:
    return os.path.join(USERS_ROOT, uid, "rss")


def rss_index_path(uid: str) -> str:
    return os.path.join(rss_user_dir(uid), "embeddings.jsonl")


def _pick_first(item: Dict[str, Any], *keys: str) -> Any:
    for k in keys:
        if k in item:
            v = item.get(k)
            if v is None:
                continue
            s = str(v).strip()
            if s:
                return v
    return None


def _parse_ts_any(v: Any) -> Optional[float]:
    s = str(v or "").strip()
    if not s:
        return None
    # ISO
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.timestamp()
    except Exception:
        pass
    # numeric seconds/ms
    try:
        x = float(s)
        if x > 10_000_000_000:
            x = x / 1000.0
        return x
    except Exception:
        return None


def _iso_utc_from_any(v: Any) -> str:
    ts = _parse_ts_any(v)
    if ts is None:
        return ""
    try:
        return datetime.fromtimestamp(float(ts), tz=timezone.utc).isoformat()
    except Exception:
        return ""


def _utc_iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize_published_and_fetched(item: Dict[str, Any]) -> Dict[str, str]:
    """
    目标：保证返回的 published_at / fetched_at 均为非空 ISO(UTC) 字符串。
    published_at 缺失时回退到 fetched_at。
    """
    pub_raw = _pick_first(
        item,
        "published_at", "publishedAt", "published", "pubDate", "date", "updated", "updated_at",
    )
    fet_raw = _pick_first(
        item,
        "fetched_at", "fetchedAt", "fetched", "fetched_time", "fetch_time", "ts", "timestamp",
    )

    fetched_iso = _iso_utc_from_any(fet_raw)
    if not fetched_iso:
        fetched_iso = _utc_iso_now()

    published_iso = _iso_utc_from_any(pub_raw)
    if not published_iso:
        published_iso = fetched_iso

    return {"published_at": published_iso, "fetched_at": fetched_iso}


def _load_deleted_set(uid: str, feed_id: str) -> set[str]:
    """
    Fold states.jsonl to get deleted=true set.
    """
    base = rss_user_dir(uid)
    st_path = os.path.join(base, "feeds", feed_id, "states.jsonl")
    deleted: Dict[str, bool] = {}
    for r in _read_jsonl(st_path):
        if not isinstance(r, dict):
            continue
        aid = str(r.get("article_id") or "").strip()
        st = str(r.get("state") or "").strip()
        val = bool(r.get("value", True))
        if not aid or st != "deleted":
            continue
        deleted[aid] = val
    return {aid for aid, v in deleted.items() if v is True}


def _iter_all_articles(uid: str) -> Iterable[Dict[str, Any]]:
    base = rss_user_dir(uid)
    feeds_dir = os.path.join(base, "feeds")
    if not os.path.isdir(feeds_dir):
        return []

    def _iter():
        for feed_id in sorted(os.listdir(feeds_dir)):
            fdir = os.path.join(feeds_dir, feed_id)
            if not os.path.isdir(fdir):
                continue
            apath = os.path.join(fdir, "articles.jsonl")
            if not os.path.exists(apath):
                continue

            deleted_set = _load_deleted_set(uid, feed_id)

            # 同一 article_id 取最新一条（jsonl 后写为新）
            last_by_id: Dict[str, Dict[str, Any]] = {}
            for row in _read_jsonl(apath):
                if not isinstance(row, dict):
                    continue
                rid = str(row.get("article_id") or row.get("articleId") or "").strip()
                if not rid:
                    rid = str(row.get("id") or row.get("guid") or row.get("url") or row.get("link") or "").strip()
                if not rid:
                    continue
                if rid in deleted_set:
                    continue
                row2 = dict(row)
                if "feed_id" not in row2 and "feedId" not in row2:
                    row2["feed_id"] = feed_id
                last_by_id[rid] = row2

            for _, row2 in last_by_id.items():
                yield row2

    return _iter()


def get_uid_from_ctx(ctx: Any, uid_param: Optional[str]) -> str:
    # 1) explicit uid
    if uid_param and str(uid_param).strip():
        return str(uid_param).strip()

    # 2) common injected keys
    for key in ("uid", "user_id", "userid", "userId"):
        v = None
        try:
            v = getattr(ctx, key, None)
        except Exception:
            v = None
        if v:
            return str(v).strip()
        try:
            if isinstance(ctx, dict):
                v = ctx.get(key)
                if v:
                    return str(v).strip()
        except Exception:
            pass

    # 3) fallback: parse from basepath like /data/users/{uid}
    basepath = None
    try:
        basepath = getattr(ctx, "basepath", None) or getattr(ctx, "basePath", None)
    except Exception:
        basepath = None
    if not basepath and isinstance(ctx, dict):
        basepath = ctx.get("basepath") or ctx.get("basePath") or ctx.get("base_path")
    if basepath:
        bp = str(basepath).rstrip("/")
        parts = bp.split("/")
        if len(parts) >= 1:
            return parts[-1]

    raise ValueError("Cannot resolve uid from ctx; pass uid explicitly.")


def rebuild_index(uid: str) -> Dict[str, Any]:
    udir = rss_user_dir(uid)
    _safe_mkdir(udir)

    out_p = rss_index_path(uid)
    rows: List[Dict[str, Any]] = []
    seen_ids: set[str] = set()

    for it in _iter_all_articles(uid):
        rid = str(it.get("article_id") or it.get("articleId") or "").strip()
        if not rid:
            rid = str(it.get("id") or it.get("guid") or it.get("url") or it.get("link") or "").strip()
        if not rid or rid in seen_ids:
            continue
        seen_ids.add(rid)

        text = build_item_text(it)
        emb = _hash_vec(_tokenize(text), dim=512)

        norm_dt = _normalize_published_and_fetched(it)

        rows.append(
            {
                "id": rid,
                "feed_id": str(it.get("feed_id") or it.get("feedId") or "").strip(),
                "title": it.get("title") or "",
                "url": it.get("url") or it.get("link") or "",
                "published_at": norm_dt["published_at"],
                "fetched_at": norm_dt["fetched_at"],
                "embedding": emb,
                "text": text,
            }
        )

    _write_jsonl(out_p, rows)
    return {"success": True, "count": len(rows), "index_path": out_p}


def upsert_one(uid: str, item: Dict[str, Any]) -> None:
    udir = rss_user_dir(uid)
    _safe_mkdir(udir)
    out_p = rss_index_path(uid)

    rid = str(item.get("article_id") or item.get("articleId") or "").strip()
    if not rid:
        rid = str(item.get("id") or item.get("guid") or item.get("url") or item.get("link") or "").strip()
    if not rid:
        return

    text = build_item_text(item)
    emb = _hash_vec(_tokenize(text), dim=512)

    norm_dt = _normalize_published_and_fetched(item)

    _append_jsonl(
        out_p,
        {
            "id": rid,
            "feed_id": str(item.get("feed_id") or item.get("feedId") or "").strip(),
            "title": item.get("title") or "",
            "url": item.get("url") or item.get("link") or "",
            "published_at": norm_dt["published_at"],
            "fetched_at": norm_dt["fetched_at"],
            "embedding": emb,
            "text": text,
        },
    )

