from __future__ import annotations

import os
import time
import hashlib
import sqlite3
import json
from contextlib import contextmanager
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Set, Tuple

from core.storage import load_json, save_json, append_jsonl
from .tools import _get_basepath, _uid_from_basepath


# ============================================================
# Utils
# ============================================================

def _utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha12(s: str) -> str:
    return hashlib.sha256((s or "").encode("utf-8")).hexdigest()[:12]


def _pick_str(d: Dict[str, Any], *keys: str, default: str = "") -> str:
    for k in keys:
        if k in d:
            v = d.get(k)
            if v is None:
                continue
            s = str(v).strip()
            if s:
                return s
    return default


def _pick_int(d: Dict[str, Any], *keys: str, default: int = 0) -> int:
    for k in keys:
        if k in d:
            try:
                return int(d.get(k))
            except Exception:
                return default
    return default


def _pick_float(d: Dict[str, Any], *keys: str, default: float = 0.0) -> float:
    for k in keys:
        if k in d:
            try:
                return float(d.get(k))
            except Exception:
                return default
    return default


def _pick_bool(d: Dict[str, Any], *keys: str, default: bool = False) -> bool:
    for k in keys:
        if k in d:
            return bool(d.get(k))
    return default


def _pick_list(d: Dict[str, Any], *keys: str) -> List[Any]:
    for k in keys:
        if k in d:
            v = d.get(k)
            if isinstance(v, list):
                return list(v)
    return []


def _split_terms(s: str) -> List[str]:
    return [x.strip() for x in str(s or "").split(",") if x.strip()]


def _split_lines_or_commas(s: str) -> List[str]:
    raw = str(s or "")
    parts = []
    for p in raw.replace(",", "\n").split("\n"):
        t = p.strip()
        if t:
            parts.append(t)
    return parts


def _pick_str_list(d: Dict[str, Any], *keys: str, max_items: int = 50) -> List[str]:
    out: List[str] = []
    seen: Set[str] = set()

    v_any: Any = None
    for k in keys:
        if k in d:
            v_any = d.get(k)
            break

    if v_any is None:
        return []

    cand: List[str] = []
    if isinstance(v_any, list):
        for x in v_any:
            s = str(x or "").strip()
            if s:
                cand.append(s)
    else:
        cand = _split_lines_or_commas(str(v_any))

    for s in cand:
        if s in seen:
            continue
        seen.add(s)
        out.append(s)
        if len(out) >= max_items:
            break
    return out


def _normalize_url_for_dedupe(url: str) -> str:
    u = str(url or "").strip()
    if not u:
        return ""
    u = u.split("#")[0]
    if len(u) > 1 and u.endswith("/"):
        u = u[:-1]
    return u


def _normalize_times_utc(times: List[str]) -> List[str]:
    out: List[str] = []
    seen: Set[str] = set()
    for t in (times or []):
        s = str(t or "").strip()
        if not s or ":" not in s:
            continue
        hh, mm = s.split(":", 1)
        try:
            h = int(hh.strip())
            m = int(mm.strip())
        except Exception:
            continue
        if h < 0 or h > 23 or m < 0 or m > 59:
            continue
        norm = f"{h:02d}:{m:02d}"
        if norm in seen:
            continue
        seen.add(norm)
        out.append(norm)
    out.sort()
    return out


def _parse_times_utc_any(v: Any) -> List[str]:
    if v is None:
        return []
    if isinstance(v, list):
        return _normalize_times_utc([str(x or "").strip() for x in v])
    if isinstance(v, str):
        parts = [x.strip() for x in v.split(",") if str(x or "").strip()]
        return _normalize_times_utc(parts)
    return []


def _parse_iso_ts(s: str) -> Optional[float]:
    ss = str(s or "").strip()
    if not ss:
        return None
    try:
        dt = datetime.fromisoformat(ss.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return float(dt.timestamp())
    except Exception:
        return None


def _calc_next_run_at_from_times(times_utc: List[str], *, now_ts: Optional[float] = None) -> str:
    times_utc = _normalize_times_utc(list(times_utc or []))
    if not times_utc:
        return ""
    if now_ts is None:
        now_ts = time.time()

    now = datetime.fromtimestamp(float(now_ts), tz=timezone.utc)
    today = now.date()

    cands: List[datetime] = []
    for t in times_utc:
        hh, mm = t.split(":")
        h = int(hh)
        m = int(mm)
        cands.append(datetime(today.year, today.month, today.day, h, m, tzinfo=timezone.utc))

    for dt in sorted(cands):
        if dt.timestamp() > float(now_ts):
            return dt.isoformat()

    tomorrow = now + timedelta(days=1)
    hh, mm = times_utc[0].split(":")
    dt0 = datetime(tomorrow.year, tomorrow.month, tomorrow.day, int(hh), int(mm), tzinfo=timezone.utc)
    return dt0.isoformat()


def _rule_signature(rule: Dict[str, Any]) -> str:
    expand_queries = _pick_str_list(rule, "expand_queries")
    expand_queries = [str(x).strip() for x in expand_queries if str(x).strip()]
    expand_queries.sort()

    sig_obj = {
        "query": _pick_str(rule, "query"),
        "expand_queries": expand_queries,
        "feed_ids": [str(x).strip() for x in (_pick_list(rule, "feed_ids") or []) if str(x).strip()],
        "days": _pick_int(rule, "days", default=30),
        "start_date": _pick_str(rule, "start_date"),
        "end_date": _pick_str(rule, "end_date"),
        "min_score": float(_pick_float(rule, "min_score", default=0.35)),
        "strict_lexical": bool(_pick_bool(rule, "strict_lexical", default=True)),
        "methods": [str(x).strip().lower() for x in (_pick_list(rule, "methods") or ["hybrid"]) if str(x).strip()],
        "exclude_spam": bool(_pick_bool(rule, "exclude_spam", default=True)),
        "exclude_terms": _pick_str(rule, "exclude_terms"),
        "match_mode": str(_pick_str(rule, "match_mode", default="any")).strip().lower() or "any",
        "sort_by": str(_pick_str(rule, "sort_by", default="relevance")).strip().lower() or "relevance",
    }
    sig_obj["feed_ids"].sort()
    sig_obj["methods"].sort()

    try:
        payload = json.dumps(sig_obj, ensure_ascii=False, sort_keys=True)
    except Exception:
        payload = str(sig_obj)
    return _sha12(payload)


# ============================================================
# Paths / storage
# ============================================================

def _rules_json_path(basepath: str) -> str:
    return os.path.join(basepath, "rss", "auto_import_rules.json")


def _events_log_path(basepath: str) -> str:
    return os.path.join(basepath, "logs", "rss_auto_import_events.jsonl")


def _import_log_path(basepath: str, library_id: str) -> str:
    return os.path.join(basepath, "rss", "auto_import_logs", f"{library_id}.jsonl")


def _rules_lock_path(basepath: str) -> str:
    return os.path.join(basepath, "rss", ".auto_import_rules.lock")


@contextmanager
def _rules_lock(basepath: str):
    os.makedirs(os.path.dirname(_rules_lock_path(basepath)), exist_ok=True)
    lockf = None
    try:
        lockf = open(_rules_lock_path(basepath), "a+", encoding="utf-8")
        try:
            import fcntl
            fcntl.flock(lockf.fileno(), fcntl.LOCK_EX)
        except Exception:
            pass
        yield
    finally:
        try:
            if lockf is not None:
                try:
                    import fcntl
                    fcntl.flock(lockf.fileno(), fcntl.LOCK_UN)
                except Exception:
                    pass
                lockf.close()
        except Exception:
            pass


def _dedupe_db_path(basepath: str) -> str:
    return os.path.join(basepath, "rss", "auto_import_dedupe.sqlite")


def _dedupe_db_connect(db_path: str) -> sqlite3.Connection:
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path, timeout=2.0)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        conn.execute("PRAGMA temp_store=MEMORY;")
    except Exception:
        pass
    return conn


def _dedupe_db_init(basepath: str) -> None:
    dbp = _dedupe_db_path(basepath)
    conn = _dedupe_db_connect(dbp)
    try:
        conn.execute("""
        CREATE TABLE IF NOT EXISTS imported_urls (
            library_id TEXT NOT NULL,
            url TEXT NOT NULL,
            ts TEXT NOT NULL,
            rule_id TEXT,
            feed_id TEXT,
            article_id TEXT,
            status TEXT,
            PRIMARY KEY (library_id, url)
        );
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_imported_urls_library_id ON imported_urls(library_id);")

        conn.execute("""
        CREATE TABLE IF NOT EXISTS pending_urls (
            library_id TEXT NOT NULL,
            rule_id TEXT NOT NULL,
            url TEXT NOT NULL,
            queued_at TEXT NOT NULL,
            feed_id TEXT,
            article_id TEXT,
            title TEXT,
            published_at TEXT,
            score REAL,
            fail_count INTEGER NOT NULL DEFAULT 0,
            last_error TEXT,
            last_attempt_at TEXT,
            rule_sig TEXT,
            PRIMARY KEY (library_id, rule_id, url)
        );
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_pending_urls_rule ON pending_urls(library_id, rule_id);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_pending_urls_queued ON pending_urls(library_id, rule_id, queued_at);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_pending_urls_sig ON pending_urls(library_id, rule_id, rule_sig);")

        try:
            conn.execute("ALTER TABLE pending_urls ADD COLUMN rule_sig TEXT;")
        except Exception:
            pass

        conn.commit()
    finally:
        conn.close()


def _dedupe_db_has(basepath: str, library_id: str, url: str) -> bool:
    if not library_id or not url:
        return False
    _dedupe_db_init(basepath)
    conn = _dedupe_db_connect(_dedupe_db_path(basepath))
    try:
        cur = conn.execute(
            "SELECT 1 FROM imported_urls WHERE library_id = ? AND url = ? LIMIT 1",
            (library_id, url),
        )
        return cur.fetchone() is not None
    except Exception:
        return False
    finally:
        conn.close()


def _dedupe_db_existing_set(basepath: str, library_id: str, urls: List[str]) -> Set[str]:
    if not library_id or not urls:
        return set()

    norm_urls: List[str] = []
    seen: Set[str] = set()
    for u0 in urls:
        u = _normalize_url_for_dedupe(str(u0 or ""))
        if not u or u in seen:
            continue
        seen.add(u)
        norm_urls.append(u)

    if not norm_urls:
        return set()

    _dedupe_db_init(basepath)
    conn = _dedupe_db_connect(_dedupe_db_path(basepath))
    found: Set[str] = set()
    try:
        chunk_size = 400
        for i in range(0, len(norm_urls), chunk_size):
            chunk = norm_urls[i:i + chunk_size]
            placeholders = ",".join(["?"] * len(chunk))
            cur = conn.execute(
                f"SELECT url FROM imported_urls WHERE library_id = ? AND url IN ({placeholders})",
                [library_id] + chunk,
            )
            for row in cur.fetchall() or []:
                u = str(row["url"] or "").strip()
                if u:
                    found.add(u)
        return found
    except Exception:
        return set()
    finally:
        conn.close()


def _dedupe_db_mark_many(
    basepath: str,
    library_id: str,
    rows: List[Tuple[str, str, str, str, str, str]],
) -> None:
    if not library_id or not rows:
        return
    _dedupe_db_init(basepath)
    conn = _dedupe_db_connect(_dedupe_db_path(basepath))
    try:
        conn.executemany(
            "INSERT OR REPLACE INTO imported_urls(library_id, url, ts, rule_id, feed_id, article_id, status) VALUES (?, ?, ?, ?, ?, ?, ?)",
            [(library_id, url, ts, rule_id, feed_id, article_id, status) for (url, ts, rule_id, feed_id, article_id, status) in rows],
        )
        conn.commit()
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
    finally:
        conn.close()


def _pending_db_purge_other_sig(basepath: str, library_id: str, rule_id: str, rule_sig: str) -> int:
    if not library_id or not rule_id:
        return 0
    _dedupe_db_init(basepath)
    conn = _dedupe_db_connect(_dedupe_db_path(basepath))
    try:
        cur = conn.execute(
            "DELETE FROM pending_urls WHERE library_id = ? AND rule_id = ? AND COALESCE(rule_sig,'') != ?",
            (library_id, rule_id, str(rule_sig or "")),
        )
        conn.commit()
        return int(cur.rowcount or 0)
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
        return 0
    finally:
        conn.close()


def _pending_db_count(basepath: str, library_id: str, rule_id: str, rule_sig: str) -> int:
    if not library_id or not rule_id:
        return 0
    _dedupe_db_init(basepath)
    conn = _dedupe_db_connect(_dedupe_db_path(basepath))
    try:
        cur = conn.execute(
            "SELECT COUNT(1) AS c FROM pending_urls WHERE library_id = ? AND rule_id = ? AND COALESCE(rule_sig,'') = ?",
            (library_id, rule_id, str(rule_sig or "")),
        )
        row = cur.fetchone()
        return int(row["c"]) if row and "c" in row.keys() else 0
    except Exception:
        return 0
    finally:
        conn.close()


def _pending_db_upsert_many(basepath: str, library_id: str, rule_id: str, rule_sig: str, rows: List[Dict[str, Any]]) -> int:
    if not library_id or not rule_id or not rows:
        return 0
    _dedupe_db_init(basepath)
    now_iso = _utc_iso()
    conn = _dedupe_db_connect(_dedupe_db_path(basepath))
    inserted = 0
    try:
        payload = []
        for r in rows:
            u = _normalize_url_for_dedupe(str(r.get("url") or ""))
            if not u:
                continue
            payload.append((
                library_id,
                rule_id,
                u,
                now_iso,
                str(r.get("feed_id") or r.get("feedid") or "").strip() or None,
                str(r.get("article_id") or r.get("articleid") or "").strip() or None,
                str(r.get("title") or "").strip() or None,
                str(r.get("published_at") or "").strip() or None,
                float(r.get("score") or 0.0),
                str(rule_sig or ""),
            ))

        if not payload:
            return 0

        cur = conn.executemany(
            "INSERT OR IGNORE INTO pending_urls(library_id, rule_id, url, queued_at, feed_id, article_id, title, published_at, score, rule_sig) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            payload,
        )
        inserted = int(cur.rowcount or 0)
        conn.commit()
        return inserted
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
        return 0
    finally:
        conn.close()


def _pending_db_pick(basepath: str, library_id: str, rule_id: str, rule_sig: str, limit: int) -> List[Dict[str, Any]]:
    if not library_id or not rule_id:
        return []
    limit = max(1, min(5000, int(limit or 0)))
    _dedupe_db_init(basepath)
    conn = _dedupe_db_connect(_dedupe_db_path(basepath))
    try:
        cur = conn.execute(
            "SELECT url, feed_id, article_id, title FROM pending_urls WHERE library_id = ? AND rule_id = ? AND COALESCE(rule_sig,'') = ? ORDER BY queued_at ASC LIMIT ?",
            (library_id, rule_id, str(rule_sig or ""), limit),
        )
        out: List[Dict[str, Any]] = []
        for row in cur.fetchall() or []:
            out.append({
                "url": str(row["url"] or "").strip(),
                "feed_id": str(row["feed_id"] or "").strip(),
                "article_id": str(row["article_id"] or "").strip(),
                "title": str(row["title"] or "").strip(),
            })
        return out
    except Exception:
        return []
    finally:
        conn.close()


def _pending_db_delete_many(basepath: str, library_id: str, rule_id: str, urls: List[str]) -> int:
    if not library_id or not rule_id or not urls:
        return 0
    _dedupe_db_init(basepath)
    conn = _dedupe_db_connect(_dedupe_db_path(basepath))
    try:
        norm = [(_normalize_url_for_dedupe(u),) for u in urls if _normalize_url_for_dedupe(u)]
        if not norm:
            return 0
        conn.executemany(
            "DELETE FROM pending_urls WHERE library_id = ? AND rule_id = ? AND url = ?",
            [(library_id, rule_id, u[0]) for u in norm],
        )
        conn.commit()
        return len(norm)
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
        return 0
    finally:
        conn.close()


def _pending_db_mark_fail(basepath: str, library_id: str, rule_id: str, rule_sig: str, url: str, err: str) -> None:
    u = _normalize_url_for_dedupe(url)
    if not library_id or not rule_id or not u:
        return
    _dedupe_db_init(basepath)
    conn = _dedupe_db_connect(_dedupe_db_path(basepath))
    try:
        now_iso = _utc_iso()
        conn.execute(
            "UPDATE pending_urls SET fail_count = fail_count + 1, last_error = ?, last_attempt_at = ? WHERE library_id = ? AND rule_id = ? AND COALESCE(rule_sig,'') = ? AND url = ?",
            (str(err or "")[:500], now_iso, library_id, rule_id, str(rule_sig or ""), u),
        )
        conn.execute(
            "DELETE FROM pending_urls WHERE library_id = ? AND rule_id = ? AND COALESCE(rule_sig,'') = ? AND url = ? AND fail_count >= 3",
            (library_id, rule_id, str(rule_sig or ""), u),
        )
        conn.commit()
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
    finally:
        conn.close()


def _pending_db_trim(basepath: str, library_id: str, rule_id: str, rule_sig: str, max_rows: int = 5000) -> None:
    if not library_id or not rule_id:
        return
    max_rows = max(100, min(20000, int(max_rows or 0)))
    _dedupe_db_init(basepath)
    conn = _dedupe_db_connect(_dedupe_db_path(basepath))
    try:
        cur = conn.execute(
            "SELECT COUNT(1) AS c FROM pending_urls WHERE library_id = ? AND rule_id = ? AND COALESCE(rule_sig,'') = ?",
            (library_id, rule_id, str(rule_sig or "")),
        )
        row = cur.fetchone()
        total = int(row["c"]) if row and "c" in row.keys() else 0
        if total <= max_rows:
            return

        to_del = total - max_rows
        conn.execute(
            """
            DELETE FROM pending_urls
            WHERE rowid IN (
                SELECT rowid FROM pending_urls
                WHERE library_id = ? AND rule_id = ? AND COALESCE(rule_sig,'') = ?
                ORDER BY queued_at ASC
                LIMIT ?
            )
            """,
            (library_id, rule_id, str(rule_sig or ""), to_del),
        )
        conn.commit()
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
    finally:
        conn.close()


def _gate_prefs_merge_imported_urls(basepath: str, imported_urls: List[str]) -> None:
    try:
        from .tools import nisb_rss_gate_prefs_get, nisb_rss_gate_prefs_set
    except Exception:
        return

    urls = [_normalize_url_for_dedupe(u) for u in (imported_urls or [])]
    urls = [u for u in urls if u]
    if not urls:
        return

    try:
        r = nisb_rss_gate_prefs_get({"basepath": basepath})
        if not isinstance(r, dict) or not r.get("success"):
            return
        prefs = r.get("prefs") or {}
        cur = prefs.get("imported_urls")
        if not isinstance(cur, list):
            cur = []
        merged = set(_normalize_url_for_dedupe(x) for x in cur if str(x or "").strip())
        for u in urls:
            merged.add(u)

        nisb_rss_gate_prefs_set({"basepath": basepath, "imported_urls": list(merged)})
    except Exception:
        return


# ============================================================
# Rule document
# ============================================================

def _load_rules_doc(basepath: str) -> Dict[str, Any]:
    path = _rules_json_path(basepath)
    if not os.path.exists(path):
        return {"version": 1, "updated_at": "", "rules": []}

    doc = load_json(path)
    if not isinstance(doc, dict):
        return {"version": 1, "updated_at": "", "rules": []}

    if not isinstance(doc.get("rules"), list):
        doc["rules"] = []

    return doc


def _save_rules_doc(basepath: str, doc: Dict[str, Any]) -> bool:
    path = _rules_json_path(basepath)
    os.makedirs(os.path.dirname(path), exist_ok=True)

    doc["version"] = 1
    doc["updated_at"] = _utc_iso()

    return save_json(path, doc)


def _log_event(basepath: str, event_type: str, payload: Dict[str, Any]):
    path = _events_log_path(basepath)
    os.makedirs(os.path.dirname(path), exist_ok=True)

    append_jsonl(path, {
        "ts": _utc_iso(),
        "type": event_type,
        **(payload or {}),
    })


# ============================================================
# Canonicalize (public + wrapper)
# ============================================================

def canonicalize_rule(raw: Dict[str, Any], existing: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    raw = dict(raw or {})
    base = dict(existing or {})

    rule_id = _pick_str(raw, "rule_id", default=_pick_str(base, "rule_id"))
    name = _pick_str(raw, "name", default=_pick_str(base, "name"))

    query = _pick_str(raw, "query", default=_pick_str(base, "query"))
    library_id = _pick_str(raw, "library_id", default=_pick_str(base, "library_id"))

    feed_ids = _pick_list(raw, "feed_ids")
    if not feed_ids:
        feed_ids = _pick_list(base, "feed_ids")

    expand_queries = _pick_str_list(raw, "expand_queries")
    if ("expand_queries" not in raw) and isinstance(base, dict):
        expand_queries = _pick_str_list(base, "expand_queries")

    cleaned_expand: List[str] = []
    seen: Set[str] = set()
    for q in expand_queries or []:
        s = str(q or "").strip()
        if not s:
            continue
        if s == query:
            continue
        if s in seen:
            continue
        seen.add(s)
        cleaned_expand.append(s)
        if len(cleaned_expand) >= 50:
            break

    days = _pick_int(raw, "days", default=_pick_int(base, "days", default=30))

    if "start_date" in raw:
        v = raw.get("start_date")
        start_date = "" if v is None else str(v).strip()
    else:
        start_date = _pick_str(base, "start_date")

    if "end_date" in raw:
        v = raw.get("end_date")
        end_date = "" if v is None else str(v).strip()
    else:
        end_date = _pick_str(base, "end_date")

    limit = _pick_int(raw, "limit", default=_pick_int(base, "limit", default=50))
    min_score = _pick_float(raw, "min_score", default=_pick_float(base, "min_score", default=0.35))
    strict_lexical = _pick_bool(raw, "strict_lexical", default=_pick_bool(base, "strict_lexical", default=True))
    methods = _pick_list(raw, "methods") or _pick_list(base, "methods") or ["hybrid"]
    exclude_spam = _pick_bool(raw, "exclude_spam", default=_pick_bool(base, "exclude_spam", default=True))

    exclude_terms = _pick_str(raw, "exclude_terms", default=_pick_str(base, "exclude_terms"))
    interval_minutes = _pick_int(raw, "interval_minutes", default=_pick_int(base, "interval_minutes", default=0))

    times_utc: List[str] = []
    if "times_utc" in raw:
        times_utc = _parse_times_utc_any(raw.get("times_utc"))
    else:
        times_utc = _parse_times_utc_any(base.get("times_utc"))

    max_per_run = _pick_int(raw, "max_per_run", default=_pick_int(base, "max_per_run", default=30))
    import_mode = _pick_str(raw, "import_mode", default=_pick_str(base, "import_mode", default="copy")).lower().strip() or "copy"
    if import_mode not in ("copy", "move"):
        import_mode = "copy"

    enabled = _pick_bool(raw, "enabled", default=_pick_bool(base, "enabled", default=True))

    created_at = _pick_str(raw, "created_at", default=_pick_str(base, "created_at"))
    last_run_at = _pick_str(raw, "last_run_at", default=_pick_str(base, "last_run_at"))
    next_run_at = _pick_str(raw, "next_run_at", default=_pick_str(base, "next_run_at"))

    scan_cursor = _pick_int(raw, "scan_cursor", default=_pick_int(base, "scan_cursor", default=0))
    scan_cursor = max(0, scan_cursor)

    match_mode = _pick_str(raw, "match_mode", default=_pick_str(base, "match_mode", default="any")).strip().lower() or "any"
    if match_mode not in ("any", "all"):
        match_mode = "any"

    sort_by = _pick_str(raw, "sort_by", default=_pick_str(base, "sort_by", default="relevance")).strip().lower() or "relevance"
    if sort_by not in ("relevance", "published_at"):
        sort_by = "relevance"

    out = {
        "rule_id": rule_id,
        "name": name,
        "enabled": enabled,

        "query": query,
        "expand_queries": cleaned_expand,
        "library_id": library_id,
        "feed_ids": feed_ids,

        "days": days,
        "start_date": start_date,
        "end_date": end_date,
        "limit": limit,
        "min_score": min_score,
        "strict_lexical": strict_lexical,
        "methods": methods,
        "exclude_spam": exclude_spam,

        "exclude_terms": exclude_terms,

        "times_utc": times_utc,
        "interval_minutes": interval_minutes,

        "max_per_run": max_per_run,
        "import_mode": import_mode,

        "created_at": created_at,
        "last_run_at": last_run_at,
        "next_run_at": next_run_at,

        "scan_cursor": scan_cursor,
        "match_mode": match_mode,
        "sort_by": sort_by,
        "rule_sig": _pick_str(raw, "rule_sig", default=_pick_str(base, "rule_sig")),
    }
    return out


def _canonicalize_rule(raw: Dict[str, Any], existing: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    return canonicalize_rule(raw, existing)


# ============================================================
# Scheduling (times_utc first; interval_minutes legacy)
# ============================================================

def _calc_next_run_at(interval_minutes: int, *, now_ts: Optional[float] = None) -> str:
    if interval_minutes <= 0:
        return ""
    if now_ts is None:
        now_ts = time.time()
    next_ts = float(now_ts) + (int(interval_minutes) * 60)
    return datetime.fromtimestamp(next_ts, tz=timezone.utc).isoformat()


def _calc_next_run_at_for_rule(rule: Dict[str, Any], *, now_ts: Optional[float] = None) -> str:
    if now_ts is None:
        now_ts = time.time()

    if not _pick_bool(rule, "enabled", default=True):
        return ""

    times_utc = _parse_times_utc_any(rule.get("times_utc"))
    if times_utc:
        return _calc_next_run_at_from_times(times_utc, now_ts=float(now_ts))

    interval = _pick_int(rule, "interval_minutes", default=0)
    if interval > 0:
        return _calc_next_run_at(interval, now_ts=float(now_ts))

    return ""


def _is_due(rule: Dict[str, Any], now_ts: float) -> bool:
    if not _pick_bool(rule, "enabled", default=True):
        return False

    times_utc = _parse_times_utc_any(rule.get("times_utc"))
    interval = _pick_int(rule, "interval_minutes", default=0)

    if not times_utc and interval <= 0:
        return False

    next_run_at = _pick_str(rule, "next_run_at")
    if not next_run_at:
        return True

    nxt = _parse_iso_ts(next_run_at)
    if nxt is None:
        return True
    return float(now_ts) >= float(nxt)


# ============================================================
# Import log (append-only audit)
# ============================================================

def _append_import_log(basepath: str, library_id: str, url: str, feed_id: str, article_id: str, rule_id: str, status: str):
    path = _import_log_path(basepath, library_id)
    os.makedirs(os.path.dirname(path), exist_ok=True)

    append_jsonl(path, {
        "ts": _utc_iso(),
        "type": "rss_auto_import",
        "status": str(status or "").strip().lower() or "ok",
        "rule_id": rule_id,
        "library_id": library_id,
        "url": url,
        "feed_id": feed_id,
        "article_id": article_id,
    })


# ============================================================
# Candidate normalization
# ============================================================

def _normalize_candidate_item(it: Dict[str, Any]) -> Dict[str, Any]:
    it = dict(it or {})

    feed_id = _pick_str(it, "feed_id", "feedid")
    article_id = _pick_str(it, "article_id", "articleid", "id")
    url = _normalize_url_for_dedupe(_pick_str(it, "url", "link"))
    title = _pick_str(it, "title", "name", default=url)
    published_at = _pick_str(it, "published_at", "publishedAt", default="")
    score = _pick_float(it, "score", default=0.0)

    return {
        "feed_id": feed_id,
        "article_id": article_id,
        "url": url,
        "title": title,
        "published_at": published_at,
        "score": score,
    }


def _batch_dedupe_by_url(items: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], int]:
    seen: Set[str] = set()
    out: List[Dict[str, Any]] = []
    skipped = 0
    for it in items:
        u = _normalize_url_for_dedupe(str(it.get("url") or ""))
        if not u:
            out.append(it)
            continue
        if u in seen:
            skipped += 1
            continue
        seen.add(u)
        it2 = dict(it)
        it2["url"] = u
        out.append(it2)
    return out, skipped


# ============================================================
# Pipeline
# ============================================================

def _execute_rule_pipeline(basepath: str, rule: Dict[str, Any]) -> Dict[str, Any]:
    rule_id = _pick_str(rule, "rule_id", default="")

    query = _pick_str(rule, "query")
    expand_queries = _pick_str_list(rule, "expand_queries")
    expand_queries = [str(x).strip() for x in expand_queries if str(x).strip()]

    if not query and expand_queries:
        query = expand_queries[0]
        expand_queries = [x for x in expand_queries[1:] if x != query]

    if not query:
        return {"success": False, "report": {"searched_total": 0, "searched_pages": 0, "queued_added": 0, "pending": 0, "picked": 0, "imported": 0, "skipped": 0, "failed": 0, "first_error": "missing query"}}

    library_id = _pick_str(rule, "library_id")
    if not library_id:
        return {"success": False, "report": {"searched_total": 0, "searched_pages": 0, "queued_added": 0, "pending": 0, "picked": 0, "imported": 0, "skipped": 0, "failed": 0, "first_error": "missing library_id"}}

    max_per_run = max(1, min(5000, _pick_int(rule, "max_per_run", default=30)))

    feed_ids = _pick_list(rule, "feed_ids")
    days = _pick_int(rule, "days", default=30)
    start_date = _pick_str(rule, "start_date")
    end_date = _pick_str(rule, "end_date")
    min_score = _pick_float(rule, "min_score", default=0.35)
    strict_lexical = _pick_bool(rule, "strict_lexical", default=True)
    methods = _pick_list(rule, "methods") or ["hybrid"]
    exclude_spam = _pick_bool(rule, "exclude_spam", default=True)

    exclude_terms = _split_terms(_pick_str(rule, "exclude_terms"))

    match_mode = str(_pick_str(rule, "match_mode", default="any")).strip().lower() or "any"
    if match_mode not in ("any", "all"):
        match_mode = "any"

    sort_by = str(_pick_str(rule, "sort_by", default="relevance")).strip().lower() or "relevance"
    if sort_by not in ("relevance", "published_at"):
        sort_by = "relevance"

    head_pages_each_run = _pick_int(rule, "head_pages_each_run", default=2)
    head_pages_each_run = max(0, min(10, head_pages_each_run))

    page_limit = 200
    max_pages_per_run = 8

    from .gate_candidates import nisb_rss_gate_candidates

    rule_sig = _rule_signature(rule)
    purged = _pending_db_purge_other_sig(basepath, library_id, rule_id, rule_sig)

    target_buffer = max(max_per_run * 3, 30)
    searched_total = 0
    searched_pages = 0
    queued_added_total = 0
    batch_skipped_total = 0
    pre_skipped_total = 0

    scan_cursor = max(0, _pick_int(rule, "scan_cursor", default=0))

    queries: List[str] = []
    seen_q: Set[str] = set()
    for q in [query] + (expand_queries or []):
        s = str(q or "").strip()
        if not s:
            continue
        if s in seen_q:
            continue
        seen_q.add(s)
        queries.append(s)
        if len(queries) >= 20:
            break

    def _fetch_one_page(q: str, cursor: int) -> Tuple[List[Dict[str, Any]], str, int]:
        nonlocal searched_total, searched_pages
        searched_pages += 1
        try:
            gate_scan_cap = int(os.getenv("NISB_RSS_AUTO_IMPORT_GATE_SCAN_CAP", "4000"))
        except Exception:
            gate_scan_cap = 4000
        gate_scan_cap = max(500, min(50000, gate_scan_cap))

        try:
            gate_candidate_cap = int(os.getenv("NISB_RSS_AUTO_IMPORT_GATE_CANDIDATE_CAP", "800"))
        except Exception:
            gate_candidate_cap = 800
        gate_candidate_cap = max(100, min(10000, gate_candidate_cap))

        res = nisb_rss_gate_candidates({
            "basepath": basepath,
            "query": q,
            "feed_ids": feed_ids,
            "days": days,
            "start_date": start_date,
            "end_date": end_date,
            "limit": page_limit,
            "cursor": str(max(0, int(cursor or 0))),
            "min_score": min_score,
            "strict_lexical": strict_lexical,
            "methods": methods,
            "exclude_spam": exclude_spam,
            "match_mode": match_mode,
            "sort_by": sort_by,
            "fast_mode": True,
            "scan_cap": gate_scan_cap,
            "candidate_cap": gate_candidate_cap,
        })
        raw_items = res.get("items") or []
        try:
            t = int(res.get("total") or 0)
            if t > searched_total:
                searched_total = t
        except Exception:
            searched_total = searched_total or 0
        next_cursor = str(res.get("next_cursor") or "").strip()
        return raw_items, next_cursor, searched_total

    def _enqueue_items(raw_items: List[Dict[str, Any]]) -> None:
        nonlocal queued_added_total, batch_skipped_total, pre_skipped_total
        norm_items: List[Dict[str, Any]] = []
        for r in raw_items:
            if not isinstance(r, dict):
                continue
            x = _normalize_candidate_item(r)
            if not x.get("feed_id") or not x.get("article_id") or not x.get("url"):
                continue
            norm_items.append(x)

        norm_items, batch_skipped = _batch_dedupe_by_url(norm_items)
        batch_skipped_total += batch_skipped

        if exclude_terms:
            filtered: List[Dict[str, Any]] = []
            for it in norm_items:
                title_l = str(it.get("title") or "").lower()
                url_l = str(it.get("url") or "").lower()
                text = f"{title_l} {url_l}"
                bad = False
                for term in exclude_terms:
                    if term.lower() in text:
                        bad = True
                        break
                if not bad:
                    filtered.append(it)
            norm_items = filtered

        urls_for_dedupe = [_normalize_url_for_dedupe(str(it.get("url") or "")) for it in norm_items]
        existing_urls = _dedupe_db_existing_set(basepath, library_id, urls_for_dedupe)

        to_enqueue: List[Dict[str, Any]] = []
        for it in norm_items:
            u = _normalize_url_for_dedupe(str(it.get("url") or ""))
            if u and u in existing_urls:
                pre_skipped_total += 1
                continue
            it2 = dict(it)
            it2["url"] = u
            to_enqueue.append(it2)

        queued_added_total += _pending_db_upsert_many(basepath, library_id, rule_id, rule_sig, to_enqueue)
        _pending_db_trim(basepath, library_id, rule_id, rule_sig, max_rows=5000)

    pending_before = _pending_db_count(basepath, library_id, rule_id, rule_sig)

    for q in queries:
        head_cursor = 0
        head_pages_done = 0
        while head_pages_done < head_pages_each_run and searched_pages < max_pages_per_run and _pending_db_count(basepath, library_id, rule_id, rule_sig) < target_buffer:
            try:
                raw_items, next_cursor, _ = _fetch_one_page(q, head_cursor)
            except Exception as e:
                return {"success": False, "report": {"searched_total": searched_total, "searched_pages": searched_pages, "queued_added": queued_added_total, "pending": _pending_db_count(basepath, library_id, rule_id, rule_sig), "picked": 0, "imported": 0, "skipped": pre_skipped_total + batch_skipped_total, "failed": 0, "first_error": f"gate_candidates failed: {e}", "purged_pending": purged, "pending_before": pending_before}}

            _enqueue_items(raw_items)
            head_pages_done += 1

            if not next_cursor:
                break
            try:
                head_cursor = max(0, int(next_cursor))
            except Exception:
                break

    while searched_pages < max_pages_per_run and _pending_db_count(basepath, library_id, rule_id, rule_sig) < target_buffer:
        try:
            raw_items, next_cursor, _ = _fetch_one_page(query, scan_cursor)
        except Exception as e:
            return {"success": False, "report": {"searched_total": searched_total, "searched_pages": searched_pages, "queued_added": queued_added_total, "pending": _pending_db_count(basepath, library_id, rule_id, rule_sig), "picked": 0, "imported": 0, "skipped": pre_skipped_total + batch_skipped_total, "failed": 0, "first_error": f"gate_candidates failed: {e}", "purged_pending": purged, "pending_before": pending_before}}

        _enqueue_items(raw_items)

        if not next_cursor:
            scan_cursor = 0
            break
        try:
            scan_cursor = max(0, int(next_cursor))
        except Exception:
            scan_cursor = 0
            break

    picked_items = _pending_db_pick(basepath, library_id, rule_id, rule_sig, max_per_run)
    picked = len(picked_items)

    if not picked_items:
        rule["scan_cursor"] = int(scan_cursor or 0)
        rule["rule_sig"] = rule_sig
        return {
            "success": True,
            "report": {
                "searched_total": searched_total,
                "searched_pages": searched_pages,
                "queued_added": queued_added_total,
                "pending": _pending_db_count(basepath, library_id, rule_id, rule_sig),
                "picked": 0,
                "imported": 0,
                "skipped": pre_skipped_total + batch_skipped_total,
                "failed": 0,
                "first_error": "",
                "purged_pending": purged,
                "pending_before": pending_before,
                "searched_queries": len(queries),
            },
        }

    from tools.libraries.import_rss import nisb_library_import_rss

    import_mode = _pick_str(rule, "import_mode", default="copy")
    try:
        items_for_import = [dict(it) for it in picked_items]

        import_res = nisb_library_import_rss({
            "basepath": basepath,
            "user_id": _uid_from_basepath(basepath),
            "library_id": library_id,
            "items": items_for_import,
            "mode": import_mode,
            "dedupe_by_url": True,
            "include_items": True,
        })
    except Exception as e:
        for it in picked_items:
            u = _normalize_url_for_dedupe(str(it.get("url") or ""))
            _append_import_log(
                basepath,
                library_id,
                u,
                str(it.get("feed_id") or ""),
                str(it.get("article_id") or ""),
                rule_id,
                status="fail",
            )
            _pending_db_mark_fail(
                basepath,
                library_id,
                rule_id,
                rule_sig,
                u,
                f"library_import exception: {e}",
            )

        rule["scan_cursor"] = int(scan_cursor or 0)
        rule["rule_sig"] = rule_sig
        return {
            "success": False,
            "report": {
                "searched_total": searched_total,
                "searched_pages": searched_pages,
                "queued_added": queued_added_total,
                "pending": _pending_db_count(basepath, library_id, rule_id, rule_sig),
                "picked": picked,
                "imported": 0,
                "skipped": pre_skipped_total + batch_skipped_total,
                "failed": picked,
                "first_error": f"library_import exception: {e}",
                "purged_pending": purged,
                "pending_before": pending_before,
                "searched_queries": len(queries),
            },
        }

    imported = int(import_res.get("imported") or 0)
    skipped_internal = int(import_res.get("skipped") or 0)
    failed = int(import_res.get("failed") or 0)

    item_results = import_res.get("items") or []
    failures = import_res.get("failures") or []

    success_urls: Set[str] = set()
    skipped_urls: Set[str] = set()
    failure_urls: Set[str] = set()
    reason_by_url: Dict[str, str] = {}
    first_error = ""

    if isinstance(item_results, list) and item_results:
        for ix in item_results:
            if not isinstance(ix, dict):
                continue

            u = _normalize_url_for_dedupe(str(ix.get("url") or ix.get("link") or ""))
            if not u:
                continue

            st = str(ix.get("status") or "").strip().lower()
            reason = str(ix.get("reason") or ix.get("message") or "").strip()
            if reason:
                reason_by_url[u] = reason[:500]

            if st in ("imported", "imported_warning", "ok", "success", "warning"):
                success_urls.add(u)
            elif st == "skipped":
                skipped_urls.add(u)
            elif st in ("failed", "fail", "error"):
                failure_urls.add(u)
                if not first_error:
                    first_error = reason or str(import_res.get("message") or "")
    else:
        if imported == picked and failed == 0:
            for it in picked_items:
                u = _normalize_url_for_dedupe(str(it.get("url") or ""))
                if u:
                    success_urls.add(u)
        else:
            if not first_error:
                first_error = "library import did not return per-item status"
            for it in picked_items:
                u = _normalize_url_for_dedupe(str(it.get("url") or ""))
                if u:
                    failure_urls.add(u)
                    reason_by_url[u] = first_error

    if isinstance(failures, list) and failures:
        f0 = failures[0] if isinstance(failures[0], dict) else {}
        if not first_error:
            first_error = str(f0.get("reason") or f0.get("message") or "") or str(import_res.get("message") or "")

        for fx in failures:
            if not isinstance(fx, dict):
                continue
            u = _normalize_url_for_dedupe(str(fx.get("url") or fx.get("link") or ""))
            if not u:
                continue

            if u in success_urls:
                continue

            failure_urls.add(u)
            skipped_urls.discard(u)
            reason_by_url[u] = str(fx.get("reason") or fx.get("message") or first_error or "import failed")[:500]

    now_iso = _utc_iso()
    mark_rows: List[Tuple[str, str, str, str, str, str]] = []
    ok_urls_for_gate_prefs: List[str] = []
    ok_urls_for_dequeue: List[str] = []
    skipped_urls_for_dequeue: List[str] = []

    for it in picked_items:
        u = _normalize_url_for_dedupe(str(it.get("url") or ""))
        fid = str(it.get("feed_id") or "").strip()
        aid = str(it.get("article_id") or "").strip()
        if not u:
            continue

        if u in success_urls:
            _append_import_log(basepath, library_id, u, fid, aid, rule_id, status="ok")
            mark_rows.append((u, now_iso, rule_id, fid, aid, "ok"))
            ok_urls_for_gate_prefs.append(u)
            ok_urls_for_dequeue.append(u)
        elif u in skipped_urls:
            _append_import_log(basepath, library_id, u, fid, aid, rule_id, status="skip")
            skipped_urls_for_dequeue.append(u)
        else:
            err_u = reason_by_url.get(u) or first_error or "import failed"
            _append_import_log(basepath, library_id, u, fid, aid, rule_id, status="fail")
            _pending_db_mark_fail(basepath, library_id, rule_id, rule_sig, u, err_u)
    _dedupe_db_mark_many(basepath, library_id, mark_rows)
    _pending_db_delete_many(basepath, library_id, rule_id, ok_urls_for_dequeue + skipped_urls_for_dequeue)
    _gate_prefs_merge_imported_urls(basepath, ok_urls_for_gate_prefs)

    rule["scan_cursor"] = int(scan_cursor or 0)
    rule["rule_sig"] = rule_sig

    return {
        "success": True,
        "report": {
            "searched_total": searched_total,
            "searched_pages": searched_pages,
            "queued_added": queued_added_total,
            "pending": _pending_db_count(basepath, library_id, rule_id, rule_sig),
            "picked": picked,
            "imported": imported,
            "skipped": pre_skipped_total + batch_skipped_total + skipped_internal,
            "failed": failed,
            "first_error": first_error,
            "purged_pending": purged,
            "pending_before": pending_before,
            "searched_queries": len(queries),
        },
    }


# ============================================================
# MCP Tools
# ============================================================

def nisb_rss_auto_import_rules_get(args: Dict[str, Any]) -> Dict[str, Any]:
    basepath = _get_basepath(args)
    with _rules_lock(basepath):
        doc = _load_rules_doc(basepath)
        rules = doc.get("rules") or []
        if not isinstance(rules, list):
            rules = []

        changed = False
        now_ts = time.time()

        for i, r in enumerate(list(rules)):
            if not isinstance(r, dict):
                continue

            rr = _canonicalize_rule(r, existing=r)

            if _pick_bool(rr, "enabled", default=True) and not _pick_str(rr, "next_run_at"):
                times_utc = _parse_times_utc_any(rr.get("times_utc"))
                interval_minutes = _pick_int(rr, "interval_minutes", default=0)

                if times_utc or interval_minutes > 0:
                    rr["next_run_at"] = _calc_next_run_at_for_rule(rr, now_ts=now_ts)
                    rules[i] = rr
                    changed = True

        if changed:
            doc["rules"] = rules
            _save_rules_doc(basepath, doc)

    return {
        "success": True,
        "rules": doc.get("rules") or [],
        "updated_at": doc.get("updated_at") or "",
    }

def nisb_rss_auto_import_rules_set(args: Dict[str, Any]) -> Dict[str, Any]:
    basepath = _get_basepath(args)

    upserts = _pick_list(args, "upserts")
    deletes = _pick_list(args, "deletes")

    with _rules_lock(basepath):
        doc = _load_rules_doc(basepath)
        rules = doc.get("rules") or []
        if not isinstance(rules, list):
            rules = []

        rules_map: Dict[str, Dict[str, Any]] = {}
        for r in rules:
            if not isinstance(r, dict):
                continue
            rid = _pick_str(r, "rule_id")
            if rid:
                rules_map[rid] = _canonicalize_rule(r, existing=r)

        upserted_ids: List[str] = []
        now_ts = time.time()

        for up in upserts:
            if not isinstance(up, dict):
                continue

            incoming_rule_id = _pick_str(up, "rule_id")
            existing = rules_map.get(incoming_rule_id) if incoming_rule_id else None

            if not incoming_rule_id:
                name_seed = _pick_str(up, "name", default="auto_rule")
                incoming_rule_id = f"rule_{_sha12(f'{name_seed}_{time.time()}')}"
                up["rule_id"] = incoming_rule_id

            new_rule = _canonicalize_rule(up, existing=existing or up)

            if not new_rule.get("name"):
                new_rule["name"] = f"auto_rule_{incoming_rule_id[-6:]}"

            if not new_rule.get("created_at"):
                new_rule["created_at"] = _utc_iso()

            old_sig = _pick_str(existing or {}, "rule_sig")
            new_sig = _rule_signature(new_rule)
            new_rule["rule_sig"] = new_sig
            if old_sig and old_sig != new_sig:
                new_rule["scan_cursor"] = 0

            old_enabled = _pick_bool(existing or {}, "enabled", default=True)
            new_enabled = _pick_bool(new_rule, "enabled", default=True)

            old_times = _parse_times_utc_any((existing or {}).get("times_utc"))
            new_times = _parse_times_utc_any(new_rule.get("times_utc"))

            old_interval = _pick_int(existing or {}, "interval_minutes", default=0)
            new_interval = _pick_int(new_rule, "interval_minutes", default=0)

            old_schedule_kind = "times_utc" if old_times else ("interval" if old_interval > 0 else "none")
            new_schedule_kind = "times_utc" if new_times else ("interval" if new_interval > 0 else "none")

            schedule_changed = False
            if old_enabled != new_enabled:
                schedule_changed = True
            elif old_schedule_kind != new_schedule_kind:
                schedule_changed = True
            elif new_schedule_kind == "times_utc" and old_times != new_times:
                schedule_changed = True
            elif new_schedule_kind == "interval" and old_interval != new_interval:
                schedule_changed = True

            if not new_enabled:
                new_rule["next_run_at"] = ""
            else:
                if existing is None or schedule_changed:
                    new_rule["next_run_at"] = _calc_next_run_at_for_rule(new_rule, now_ts=now_ts)
                else:
                    prev_next = _pick_str(existing or {}, "next_run_at")
                    new_rule["next_run_at"] = prev_next or _calc_next_run_at_for_rule(new_rule, now_ts=now_ts)

            rules_map[incoming_rule_id] = new_rule
            upserted_ids.append(incoming_rule_id)

            _log_event(basepath, "auto_import_rule.upsert", {
                "rule_id": incoming_rule_id,
                "name": new_rule.get("name") or "",
            })

        deleted_ids: List[str] = []
        for rid in deletes:
            rid_str = str(rid or "").strip()
            if rid_str and rid_str in rules_map:
                del rules_map[rid_str]
                deleted_ids.append(rid_str)
                _log_event(basepath, "auto_import_rule.delete", {"rule_id": rid_str})

        doc["rules"] = list(rules_map.values())
        _save_rules_doc(basepath, doc)

    return {
        "success": True,
        "upserted": upserted_ids,
        "deleted": deleted_ids,
        "updated_at": doc.get("updated_at") or "",
    }

def nisb_rss_auto_import_run_rule(args: Dict[str, Any]) -> Dict[str, Any]:
    basepath = _get_basepath(args)
    rule_id = _pick_str(args, "rule_id")
    if not rule_id:
        return {"success": False, "status": "error", "message": "missing rule_id", "error": "missing rule_id"}

    # 1) 只在锁内读取规则快照，不在锁内跑重活
    with _rules_lock(basepath):
        doc = _load_rules_doc(basepath)
        rules = doc.get("rules") or []
        if not isinstance(rules, list):
            rules = []

        rule = None
        for r in rules:
            if not isinstance(r, dict):
                continue
            if _pick_str(r, "rule_id") == rule_id:
                rule = _canonicalize_rule(r, existing=r)
                break

    if not rule:
        return {
            "success": False,
            "status": "error",
            "message": f"rule not found: {rule_id}",
            "error": f"rule not found: {rule_id}",
        }

    _log_event(basepath, "auto_import_rule.run.start", {
        "rule_id": rule_id,
        "query": _pick_str(rule, "query"),
        "library_id": _pick_str(rule, "library_id"),
        "max_per_run": _pick_int(rule, "max_per_run", default=30),
    })

    # 2) 锁外执行重活，且兜住异常，避免 HTTP 502
    start_ts = time.time()
    try:
        result = _execute_rule_pipeline(basepath, rule)
        if not isinstance(result, dict):
            result = {
                "success": False,
                "status": "error",
                "message": "invalid_rule_pipeline_result",
                "error": "invalid_rule_pipeline_result",
                "report": {
                    "searched_total": 0,
                    "searched_pages": 0,
                    "queued_added": 0,
                    "pending": 0,
                    "picked": 0,
                    "imported": 0,
                    "skipped": 0,
                    "failed": 1,
                    "first_error": "invalid_rule_pipeline_result",
                },
            }
    except Exception as e:
        err = f"_execute_rule_pipeline exception: {e}"
        result = {
            "success": False,
            "status": "exception",
            "message": err,
            "error": err,
            "report": {
                "searched_total": 0,
                "searched_pages": 0,
                "queued_added": 0,
                "pending": 0,
                "picked": 0,
                "imported": 0,
                "skipped": 0,
                "failed": 1,
                "first_error": err,
            },
        }
        _log_event(basepath, "auto_import_rule.run.exception", {
            "rule_id": rule_id,
            "error": err,
        })

    duration_ms = int((time.time() - start_ts) * 1000)

    report = result.get("report") or {}
    imported_i = int(report.get("imported") or 0)
    failed_i = int(report.get("failed") or 0)

    ok = bool(result.get("success", False))
    status = str(result.get("status") or ("ok" if ok else "error")).strip().lower()
    if ok and failed_i > 0:
        status = "partial_failure"
    had_failures = (status == "partial_failure") or (failed_i > 0)

    err_text = str(
        result.get("error")
        or result.get("message")
        or report.get("first_error")
        or ""
    ).strip()

    # 3) 锁内只做最终状态回写，避免长时间独占
    updated_at = ""
    with _rules_lock(basepath):
        doc = _load_rules_doc(basepath)
        rules = doc.get("rules") or []
        if not isinstance(rules, list):
            rules = []

        for idx, r in enumerate(rules):
            if not isinstance(r, dict):
                continue
            if _pick_str(r, "rule_id") != rule_id:
                continue

            current_rule = _canonicalize_rule(r, existing=r)

            # 把 pipeline 期间推进的游标状态带回规则
            try:
                current_rule["scan_cursor"] = max(0, int(rule.get("scan_cursor") or 0))
            except Exception:
                current_rule["scan_cursor"] = 0

            current_rule["rule_sig"] = _pick_str(rule, "rule_sig", default=_pick_str(current_rule, "rule_sig"))
            current_rule["last_run_at"] = _utc_iso()

            if _pick_bool(current_rule, "enabled", default=True):
                current_rule["next_run_at"] = _calc_next_run_at_for_rule(current_rule, now_ts=time.time())
            else:
                current_rule["next_run_at"] = ""

            rules[idx] = current_rule
            break

        doc["rules"] = rules
        _save_rules_doc(basepath, doc)
        updated_at = doc.get("updated_at") or ""

    _log_event(basepath, "auto_import_rule.run", {
        "rule_id": rule_id,
        "success": ok,
        "status": status,
        "had_failures": bool(had_failures),
        "duration_ms": duration_ms,
        "error": err_text,
        "report": report,
    })

    return {
        "success": ok,
        "status": status,
        "had_failures": bool(had_failures),
        "rule_id": rule_id,
        "report": report,
        "message": err_text,
        "error": err_text,
        "updated_at": updated_at,
    }


def nisb_rss_auto_import_run_due(args: Dict[str, Any]) -> Dict[str, Any]:
    basepath = _get_basepath(args)

    now_ts = args.get("now_ts")
    if now_ts is None:
        now_ts = time.time()
    else:
        now_ts = float(now_ts)

    try:
        max_rules = int(args.get("max_rules") or 999999)
    except Exception:
        max_rules = 999999
    max_rules = max(1, min(5000, max_rules))

    try:
        max_total_ms = int(args.get("max_total_ms") or 0)
    except Exception:
        max_total_ms = 0
    if max_total_ms > 0:
        deadline_ts = time.time() + (max_total_ms / 1000.0)
    else:
        deadline_ts = None

    ran = 0
    due_skipped = 0
    total_imported = 0
    total_failed = 0
    failed_rules = 0
    reports: List[Dict[str, Any]] = []

    first_scan_counted = False

    while ran < max_rules:
        if deadline_ts is not None and time.time() > deadline_ts:
            break

        selected_rule: Optional[Dict[str, Any]] = None
        selected_rule_id = ""
        next_run_at_before = ""
        next_run_at_after = ""

        # 1) 只在锁内选择一条 due rule，并立刻推进 next_run_at 落盘
        with _rules_lock(basepath):
            doc = _load_rules_doc(basepath)
            rules = doc.get("rules") or []
            if not isinstance(rules, list):
                rules = []

            found_idx = None
            found_rule = None
            local_skipped = 0

            for idx, raw_rule in enumerate(list(rules)):
                if not isinstance(raw_rule, dict):
                    local_skipped += 1
                    continue

                rule = _canonicalize_rule(raw_rule, existing=raw_rule)
                if not _is_due(rule, now_ts):
                    local_skipped += 1
                    continue

                found_idx = idx
                found_rule = rule
                break

            if not first_scan_counted:
                due_skipped = local_skipped
                first_scan_counted = True

            if found_idx is not None and isinstance(found_rule, dict):
                selected_rule = found_rule
                selected_rule_id = _pick_str(selected_rule, "rule_id")
                next_run_at_before = _pick_str(selected_rule, "next_run_at")
                next_run_at_after = _calc_next_run_at_for_rule(selected_rule, now_ts=now_ts)

                selected_rule["next_run_at"] = next_run_at_after
                rules[found_idx] = selected_rule
                doc["rules"] = rules
                _save_rules_doc(basepath, doc)

        if not selected_rule:
            break

        _log_event(basepath, "auto_import_rule.run_due.start", {
            "rule_id": selected_rule_id,
            "next_run_at_before": next_run_at_before,
            "next_run_at_after": next_run_at_after,
            "query": _pick_str(selected_rule, "query"),
            "library_id": _pick_str(selected_rule, "library_id"),
        })

        # 2) 锁外执行重活，确保不会长时间占用 rules lock
        try:
            result = _execute_rule_pipeline(basepath, selected_rule)
            if not isinstance(result, dict):
                result = {
                    "success": False,
                    "status": "error",
                    "message": "invalid_rule_pipeline_result",
                    "error": "invalid_rule_pipeline_result",
                    "report": {
                        "searched_total": 0,
                        "searched_pages": 0,
                        "queued_added": 0,
                        "pending": 0,
                        "picked": 0,
                        "imported": 0,
                        "skipped": 0,
                        "failed": 1,
                        "first_error": "invalid_rule_pipeline_result",
                    },
                }
        except Exception as e:
            err = f"_execute_rule_pipeline exception: {e}"
            result = {
                "success": False,
                "status": "exception",
                "message": err,
                "error": err,
                "report": {
                    "searched_total": 0,
                    "searched_pages": 0,
                    "queued_added": 0,
                    "pending": 0,
                    "picked": 0,
                    "imported": 0,
                    "skipped": 0,
                    "failed": 1,
                    "first_error": err,
                },
            }

        ran += 1

        report = result.get("report") or {}
        imported_i = int(report.get("imported") or 0)
        failed_i = int(report.get("failed") or 0)
        rule_ok = bool(result.get("success", False))

        rule_status = str(result.get("status") or ("ok" if rule_ok else "error")).strip().lower()
        if rule_ok and failed_i > 0:
            rule_status = "partial_failure"

        total_imported += imported_i
        total_failed += failed_i

        if (not rule_ok) or failed_i > 0:
            failed_rules += 1

        # 3) 锁内只做最终回写，不覆盖已推进的 next_run_at
        updated_at = ""
        with _rules_lock(basepath):
            doc = _load_rules_doc(basepath)
            rules = doc.get("rules") or []
            if not isinstance(rules, list):
                rules = []

            for idx, raw_rule in enumerate(list(rules)):
                if not isinstance(raw_rule, dict):
                    continue
                if _pick_str(raw_rule, "rule_id") != selected_rule_id:
                    continue

                current_rule = _canonicalize_rule(raw_rule, existing=raw_rule)

                try:
                    current_rule["scan_cursor"] = max(0, int(selected_rule.get("scan_cursor") or 0))
                except Exception:
                    current_rule["scan_cursor"] = 0

                current_rule["rule_sig"] = _pick_str(
                    selected_rule,
                    "rule_sig",
                    default=_pick_str(current_rule, "rule_sig"),
                )
                current_rule["last_run_at"] = _utc_iso()

                if not _pick_bool(current_rule, "enabled", default=True):
                    current_rule["next_run_at"] = ""
                else:
                    prev_next = _pick_str(current_rule, "next_run_at")
                    current_rule["next_run_at"] = prev_next or next_run_at_after or _calc_next_run_at_for_rule(
                        current_rule,
                        now_ts=time.time(),
                    )

                rules[idx] = current_rule
                break

            doc["rules"] = rules
            _save_rules_doc(basepath, doc)
            updated_at = doc.get("updated_at") or ""

        reports.append({
            "rule_id": selected_rule_id,
            "success": rule_ok,
            "status": rule_status,
            "next_run_at_before": next_run_at_before,
            "next_run_at_after": next_run_at_after,
            "report": report,
        })

        _log_event(basepath, "auto_import_rule.run_due", {
            "rule_id": selected_rule_id,
            "success": rule_ok,
            "status": rule_status,
            "next_run_at_before": next_run_at_before,
            "next_run_at_after": next_run_at_after,
            "report": report,
            "updated_at": updated_at,
        })

    if ran == 0:
        status = "skipped"
    elif failed_rules > 0:
        status = "partial_failure"
    else:
        status = "ok"

    return {
        "success": True,
        "status": status,
        "had_failures": bool(failed_rules > 0),
        "message": "" if failed_rules == 0 else "rss_auto_import_run_due_has_failed_rules",
        "stats": {
            "ran": ran,
            "skipped": due_skipped,
            "imported": total_imported,
            "failed": total_failed,
            "failed_rules": failed_rules,
            "max_rules": max_rules,
            "max_total_ms": max_total_ms,
        },
        "reports": reports,
    }

