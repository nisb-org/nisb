#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
import os
import sqlite3
from typing import List, Tuple, Optional


def _norm_ws(s: str) -> str:
    return " ".join((s or "").replace("\r", "\n").split())


def _table_columns(con: sqlite3.Connection, table: str) -> List[str]:
    cur = con.execute(f"PRAGMA table_info('{table}')")
    cols = []
    for row in cur.fetchall():
        # (cid, name, type, notnull, dflt_value, pk)
        if len(row) >= 2 and row[1]:
            cols.append(str(row[1]))
    return cols


def _has_column(con: sqlite3.Connection, table: str, col: str) -> bool:
    return col in set(_table_columns(con, table))


def _documents_order_clause(con: sqlite3.Connection) -> str:
    cols = set(_table_columns(con, "documents"))
    # 常见时间列名（按优先级）
    for c in ["created_at", "uploaded_at", "updated_at", "timestamp", "ts", "time", "created", "updated"]:
        if c in cols:
            return f"ORDER BY {c} DESC"
    # rowid 一般可用（除非 WITHOUT ROWID）
    try:
        con.execute("SELECT rowid FROM documents LIMIT 1").fetchall()
        return "ORDER BY rowid DESC"
    except Exception:
        return "ORDER BY doc_id DESC"


def _load_full_text(doc_dir: str) -> Tuple[str, str]:
    """
    返回 (full_text, source_path)
    """
    p1 = os.path.join(doc_dir, "content.txt")
    p2 = os.path.join(doc_dir, "full_text.txt")
    if os.path.exists(p1):
        return open(p1, "r", encoding="utf-8", errors="ignore").read(), p1
    if os.path.exists(p2):
        return open(p2, "r", encoding="utf-8", errors="ignore").read(), p2
    return "", ""


def _anchored_find(full_text: str, chunk_text: str, anchor: int, window: int = 90000, back: int = 4000) -> int:
    n = len(full_text)
    anchor = max(0, min(int(anchor or 0), n))
    s0 = max(0, anchor - int(back))
    e0 = min(n, anchor + int(window))
    sub = full_text[s0:e0]

    t = (chunk_text or "").strip()
    if not t:
        return -1

    # 1) exact in window
    p = sub.find(t)
    if p >= 0:
        return s0 + p

    # 2) normalized whitespace in window (approx)
    ns = _norm_ws(sub)
    nt = _norm_ws(t)
    if ns and nt:
        p2 = ns.find(nt)
        if p2 >= 0:
            return s0 + p2

    # 3) prefix fallback
    pref = t[:260]
    if len(pref) >= 80:
        p3 = sub.find(pref)
        if p3 >= 0:
            return s0 + p3

    return -1


def _ensure_pragmas(con: sqlite3.Connection) -> None:
    con.execute("PRAGMA journal_mode=WAL;")
    con.execute("PRAGMA synchronous=NORMAL;")


def _list_doc_ids(con: sqlite3.Connection) -> List[str]:
    clause = _documents_order_clause(con)
    rows = con.execute(f"SELECT doc_id FROM documents {clause}").fetchall()
    out = []
    for r in rows:
        if r and r[0]:
            out.append(str(r[0]))
    return out


def _chunks_select_sql(con: sqlite3.Connection) -> str:
    cols = set(_table_columns(con, "chunks"))
    need = ["chunk_id", "text", "char_start", "char_end"]
    for c in need:
        if c not in cols:
            raise RuntimeError(f"chunks 表缺列：{c}（请先运行 migrate_chunks_add_char_range.py）")
    return "SELECT chunk_id, text, char_start, char_end FROM chunks WHERE doc_id=? ORDER BY chunk_id ASC"


def _backfill_one_doc(
    con: sqlite3.Connection,
    docs_root_dir: str,
    doc_id: str,
    *,
    commit_every: int = 400,
) -> Tuple[int, int, int]:
    """
    返回 (ok, total, updated)
    """
    doc_dir = os.path.join(docs_root_dir, doc_id)
    if not os.path.isdir(doc_dir):
        return 0, 0, 0

    full_text, src = _load_full_text(doc_dir)
    if not full_text:
        return 0, 0, 0

    sel = _chunks_select_sql(con)
    rows = con.execute(sel, (doc_id,)).fetchall()

    cursor = 0
    ok = 0
    total = 0
    updated = 0
    batch = 0

    cur = con.cursor()

    for chunk_id, text, cs, ce in rows:
        total += 1

        # 已有则跳过，但推进 cursor，保证单调
        if cs is not None and ce is not None:
            try:
                cursor = max(cursor, int(cs))
                ok += 1
            except Exception:
                pass
            continue

        pos = _anchored_find(full_text, text, cursor)
        if pos < 0:
            continue

        char_start = int(pos)
        # char_end 用“chunk 存储文本长度”直接推，足够用于 span/跳转
        char_end = int(min(len(full_text), pos + len(text or "")))

        cur.execute(
            "UPDATE chunks SET char_start=?, char_end=? WHERE doc_id=? AND chunk_id=?",
            (char_start, char_end, doc_id, int(chunk_id)),
        )

        updated += 1
        ok += 1
        cursor = char_start + max(1, len(text or "") - 16)

        batch += 1
        if batch >= commit_every:
            con.commit()
            batch = 0

    if batch > 0:
        con.commit()

    # 打印最关键的信息，方便你肉眼排查
    print(f"[backfill] doc={doc_id} ok={ok}/{total} updated={updated} full_text={len(full_text)} src={os.path.basename(src) or 'N/A'}")
    return ok, total, updated


def _scan_doc_dbs(base_users: str, uid: Optional[str], library: Optional[str]) -> List[str]:
    dbs = []
    if uid and library:
        p = os.path.join(base_users, uid, "libraries", library, "docs", "doc_db.sqlite")
        if os.path.exists(p):
            return [p]
        return []
    # 全盘扫描
    for root, dirs, files in os.walk(base_users):
        if "doc_db.sqlite" in files and root.endswith(os.path.join("docs")):
            dbs.append(os.path.join(root, "doc_db.sqlite"))
    dbs.sort()
    return dbs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-users", default="/opt/nisb-data/users")
    ap.add_argument("--uid", default=None)
    ap.add_argument("--library", default=None)
    ap.add_argument("--doc-id", default=None)
    ap.add_argument("--limit", type=int, default=0, help="每个 DB 最多处理多少本书（0=不限制）")
    args = ap.parse_args()

    db_paths = _scan_doc_dbs(args.base_users, args.uid, args.library)
    if not db_paths:
        print("[backfill] no doc_db.sqlite found")
        return

    for db_path in db_paths:
        docs_root_dir = os.path.dirname(db_path)  # .../docs
        print(f"[db] {db_path}")

        con = sqlite3.connect(db_path)
        try:
            _ensure_pragmas(con)

            # 基础检查
            if not _has_column(con, "chunks", "char_start") or not _has_column(con, "chunks", "char_end"):
                print("[skip] chunks missing char_start/char_end (run migrate first)")
                continue

            doc_ids = _list_doc_ids(con)
            if args.doc_id:
                doc_ids = [args.doc_id] if args.doc_id in set(doc_ids) else [args.doc_id]

            if args.limit and args.limit > 0:
                doc_ids = doc_ids[: args.limit]

            for doc_id in doc_ids:
                _backfill_one_doc(con, docs_root_dir, doc_id)
        finally:
            con.close()


if __name__ == "__main__":
    main()

