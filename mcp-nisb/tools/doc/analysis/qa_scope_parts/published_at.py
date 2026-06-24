from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from tools.doc.doc_db_sqlite import connect_doc_db, get_doc_db_sqlite
from .common import clean_id, parse_iso_dt_any


_PUBLISHED_RE = re.compile(r"(?im)^\s*Published\s*:\s*(.+?)\s*$")


def read_doc_published_at_from_sqlite(
    user_base: Path,
    library_id: str,
    doc_id: str,
) -> Optional[datetime]:
    lib = clean_id(library_id)
    doc = clean_id(doc_id)
    if not lib or not doc:
        return None

    try:
        db = get_doc_db_sqlite(str(user_base), lib)
        conn = connect_doc_db(str(db.db_path), readonly=True)
    except Exception:
        return None

    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT published_at
            FROM documents
            WHERE library_id = ? AND doc_id = ?
            LIMIT 1
            """,
            (lib, doc),
        )
        row = cur.fetchone()
        if not row:
            return None

        raw = row["published_at"] if hasattr(row, "keys") else row[0]
        return parse_iso_dt_any(raw)
    except Exception:
        return None
    finally:
        try:
            conn.close()
        except Exception:
            pass


def read_doc_published_at_with_source(
    user_base: Path,
    library_id: str,
    doc_id: str,
) -> Tuple[Optional[datetime], str]:
    lib = clean_id(library_id)
    doc = clean_id(doc_id)
    if not lib or not doc:
        return None, "missing"

    dt_sqlite = read_doc_published_at_from_sqlite(user_base, lib, doc)
    if dt_sqlite is not None:
        return dt_sqlite, "sqlite"

    doc_dir = user_base / "libraries" / lib / "docs" / doc

    mp = doc_dir / "metadata.json"
    if mp.exists():
        try:
            md = json.loads(mp.read_text(encoding="utf-8"))
            if isinstance(md, dict):
                dt_meta = (
                    parse_iso_dt_any(md.get("published_at"))
                    or parse_iso_dt_any(md.get("publishedAt"))
                    or parse_iso_dt_any(md.get("published"))
                )
                if dt_meta is not None:
                    return dt_meta, "metadata"
        except Exception:
            pass

    cp = doc_dir / "content.txt"
    if cp.exists():
        try:
            head = cp.read_text(encoding="utf-8", errors="ignore")[:6000]
            m = _PUBLISHED_RE.search(head)
            if m:
                dt_head = parse_iso_dt_any(m.group(1))
                if dt_head is not None:
                    return dt_head, "content_header"
        except Exception:
            pass

    return None, "missing"


def attach_evidence_published_at(
    evidence: List[Dict[str, object]],
    *,
    user_base: Path,
) -> Tuple[List[Dict[str, object]], Dict[str, object]]:
    cache: Dict[Tuple[str, str], Tuple[Optional[datetime], str]] = {}
    out: List[Dict[str, object]] = []
    source_counts: Dict[str, int] = {}

    for ev in evidence or []:
        if not isinstance(ev, dict):
            continue

        lib_id = clean_id(ev.get("library_id"))
        doc_id = clean_id(ev.get("doc_id"))
        if not lib_id or not doc_id:
            continue

        key = (lib_id, doc_id)
        if key not in cache:
            dt0 = parse_iso_dt_any(ev.get("published_at"))
            src0 = clean_id(ev.get("published_at_source")) or "evidence"
            if dt0 is not None:
                cache[key] = (dt0, src0)
            else:
                cache[key] = read_doc_published_at_with_source(user_base, lib_id, doc_id)

        dt, src = cache[key]
        source_counts[src] = int(source_counts.get(src, 0)) + 1

        ev2 = dict(ev)
        ev2["published_at"] = dt.isoformat() if dt is not None else ""
        ev2["published_at_source"] = src
        out.append(ev2)

    dbg = {
        "attached": True,
        "before": len(evidence or []),
        "after": len(out),
        "published_at_source_counts": source_counts,
    }
    return out, dbg

