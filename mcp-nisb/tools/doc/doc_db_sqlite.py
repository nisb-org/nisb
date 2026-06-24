from __future__ import annotations

import os
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

_DB_LOCKS: Dict[str, threading.Lock] = {}
_DB_LOCKS_GUARD = threading.Lock()
_db_instances: Dict[str, "DocDBSQLite"] = {}


def _get_db_lock(db_path: str) -> threading.Lock:
    normalized = str(Path(db_path).resolve())
    with _DB_LOCKS_GUARD:
        lock = _DB_LOCKS.get(normalized)
        if lock is None:
            lock = threading.Lock()
            _DB_LOCKS[normalized] = lock
        return lock


def _apply_connection_pragmas(conn: sqlite3.Connection, *, readonly: bool) -> None:
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA busy_timeout = 10000;")
    if not readonly:
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute("PRAGMA synchronous = NORMAL;")
        conn.execute("PRAGMA temp_store = MEMORY;")
    else:
        conn.execute("PRAGMA temp_store = MEMORY;")


def connect_doc_db(db_path: str, *, readonly: bool = False) -> sqlite3.Connection:
    resolved = str(Path(db_path).resolve())
    if readonly:
        uri = Path(resolved).as_uri().replace("file://", "file:")
        conn = sqlite3.connect(f"{uri}?mode=ro", uri=True, timeout=30, isolation_level=None)
    else:
        parent = os.path.dirname(resolved)
        if parent:
            os.makedirs(parent, exist_ok=True)
        conn = sqlite3.connect(resolved, timeout=30, isolation_level=None)

    _apply_connection_pragmas(conn, readonly=readonly)
    return conn


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize_iso_or_none(v: Any) -> Optional[str]:
    if v is None:
        return None
    s = str(v).strip()
    if not s:
        return None
    try:
        x = s.replace("Z", "+00:00")
        dt = datetime.fromisoformat(x)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).isoformat()
    except Exception:
        return s


def _coerce_int_or_none(v: Any) -> Optional[int]:
    if v is None:
        return None
    if isinstance(v, bool):
        return int(v)
    s = str(v).strip()
    if not s:
        return None
    try:
        return int(s)
    except Exception:
        return None


def _normalize_chunk_rows(doc_id: str, chunk_texts: List[Any]) -> List[Tuple[str, int, str, Optional[int], Optional[int]]]:
    rows: List[Tuple[str, int, str, Optional[int], Optional[int]]] = []
    for idx, item in enumerate(chunk_texts or []):
        if isinstance(item, dict):
            text = str(item.get("text") or "")
            char_start = _coerce_int_or_none(item.get("char_start"))
            char_end = _coerce_int_or_none(item.get("char_end"))
        else:
            text = str(item or "")
            char_start = None
            char_end = None

        if not text:
            continue

        if char_start is not None and char_end is None:
            char_end = char_start + len(text)
        if char_start is not None and char_end is not None and char_end < char_start:
            char_end = char_start + len(text)

        rows.append((doc_id, idx, text, char_start, char_end))
    return rows


class DocDBSQLite:
    """SQLite 版本的文档数据库（库级 doc_db.sqlite）"""

    def __init__(self, user_base_path: str, db_path: Optional[str] = None):
        self.user_base = user_base_path

        if db_path:
            self.db_path = str(Path(db_path).resolve())
            parent = os.path.dirname(self.db_path)
            if parent:
                os.makedirs(parent, exist_ok=True)
        else:
            storage_dir = Path(user_base_path) / "storage"
            storage_dir.mkdir(parents=True, exist_ok=True)
            self.db_path = str((storage_dir / "doc_index.db").resolve())

        self._lock = _get_db_lock(self.db_path)
        self.init_db()

    def _get_table_columns(self, cur: sqlite3.Cursor, table_name: str) -> set[str]:
        try:
            cur.execute(f"PRAGMA table_info({table_name})")
            rows = cur.fetchall()
            cols: set[str] = set()
            for row in rows:
                try:
                    cols.add(str(row["name"]))
                except Exception:
                    try:
                        cols.add(str(row[1]))
                    except Exception:
                        continue
            return cols
        except Exception:
            return set()

    def _ensure_schema_migrations(self, cur: sqlite3.Cursor) -> None:
        cols = self._get_table_columns(cur, "documents")
        if cols and "published_at" not in cols:
            cur.execute("ALTER TABLE documents ADD COLUMN published_at TEXT")

        cur.execute("CREATE INDEX IF NOT EXISTS idx_documents_library ON documents(library_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_documents_published_at ON documents(published_at)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_chunks_doc ON chunks(doc_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_embeddings_doc ON embeddings(doc_id)")

    def ensure_schema_compatible(self) -> Dict[str, Any]:
        result: Dict[str, Any] = {
            "ok": True,
            "db_path": self.db_path,
            "documents_columns": [],
            "purged_orphan_embeddings": 0,
        }

        with self._lock:
            conn = connect_doc_db(self.db_path, readonly=False)
            cur = conn.cursor()
            try:
                cur.execute("BEGIN IMMEDIATE;")
                self._ensure_schema_migrations(cur)
                result["purged_orphan_embeddings"] = self._purge_orphan_embeddings_locked(cur)
                result["documents_columns"] = sorted(self._get_table_columns(cur, "documents"))
                cur.execute("COMMIT;")
                return result
            except Exception as e:
                try:
                    cur.execute("ROLLBACK;")
                except Exception:
                    pass
                result["ok"] = False
                result["error"] = str(e)
                return result
            finally:
                conn.close()

    def _documents_published_expr(self, cur: sqlite3.Cursor) -> str:
        cols = self._get_table_columns(cur, "documents")
        return "published_at" if "published_at" in cols else "uploaded_at"
    
    def _purge_orphan_embeddings_locked(self, cur: sqlite3.Cursor) -> int:
        cur.execute(
            """
            DELETE FROM embeddings
            WHERE NOT EXISTS (
                SELECT 1
                FROM chunks
                WHERE chunks.doc_id = embeddings.doc_id
                  AND chunks.chunk_id = embeddings.chunk_id
            )
            """
        )
        return int(cur.rowcount or 0)
    
    def init_db(self) -> None:
        parent = os.path.dirname(self.db_path)
        if parent:
            os.makedirs(parent, exist_ok=True)

        with self._lock:
            conn = connect_doc_db(self.db_path, readonly=False)
            cur = conn.cursor()
            try:
                cur.execute("BEGIN IMMEDIATE;")

                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS documents (
                        doc_id TEXT PRIMARY KEY,
                        library_id TEXT,
                        filename TEXT NOT NULL,
                        filetype TEXT,
                        file_size INTEGER,
                        total_chunks INTEGER DEFAULT 0,
                        embedding_status TEXT DEFAULT 'pending',
                        uploaded_at TEXT,
                        published_at TEXT,
                        last_accessed TEXT,
                        access_count INTEGER DEFAULT 0,
                        language TEXT DEFAULT 'auto'
                    )
                    """
                )

                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS chunks (
                        doc_id TEXT,
                        chunk_id INTEGER,
                        text TEXT,
                        char_start INTEGER,
                        char_end INTEGER,
                        PRIMARY KEY (doc_id, chunk_id),
                        FOREIGN KEY (doc_id) REFERENCES documents(doc_id)
                    )
                    """
                )

                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS embeddings (
                        doc_id TEXT,
                        chunk_id INTEGER,
                        embedding BLOB,
                        embedding_model TEXT DEFAULT 'text-embedding-3-small',
                        embedding_dim INTEGER DEFAULT 1536,
                        PRIMARY KEY (doc_id, chunk_id),
                        FOREIGN KEY (doc_id) REFERENCES documents(doc_id)
                    )
                    """
                )

                self._ensure_schema_migrations(cur)
                cur.execute("COMMIT;")
            except Exception:
                try:
                    cur.execute("ROLLBACK;")
                except Exception:
                    pass
                raise
            finally:
                conn.close()

    def upsert_document(
        self,
        *,
        doc_id: str,
        library_id: str,
        filename: str,
        filetype: str,
        file_size: int,
        total_chunks: int,
        uploaded_at: Optional[str] = None,
        published_at: Optional[str] = None,
        language: str = "auto",
    ) -> None:
        uploaded_at = _normalize_iso_or_none(uploaded_at) or _utc_now_iso()
        published_at = _normalize_iso_or_none(published_at) or uploaded_at

        with self._lock:
            conn = connect_doc_db(self.db_path, readonly=False)
            cur = conn.cursor()
            try:
                cur.execute("BEGIN IMMEDIATE;")
                self._ensure_schema_migrations(cur)
                cur.execute(
                    """
                    INSERT INTO documents
                    (doc_id, library_id, filename, filetype, file_size, total_chunks, embedding_status, uploaded_at, published_at, last_accessed, access_count, language)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(doc_id) DO UPDATE SET
                      library_id=excluded.library_id,
                      filename=excluded.filename,
                      filetype=excluded.filetype,
                      file_size=excluded.file_size,
                      total_chunks=excluded.total_chunks,
                      uploaded_at=excluded.uploaded_at,
                      published_at=excluded.published_at,
                      language=excluded.language
                    ;
                    """,
                    (
                        doc_id,
                        library_id,
                        filename,
                        filetype,
                        int(file_size),
                        int(total_chunks),
                        "pending",
                        uploaded_at,
                        published_at,
                        uploaded_at,
                        0,
                        language,
                    ),
                )
                cur.execute("COMMIT;")
            except Exception:
                try:
                    cur.execute("ROLLBACK;")
                except Exception:
                    pass
                raise
            finally:
                conn.close()

    def replace_chunks_bulk(self, *, doc_id: str, chunk_texts: List[Any]) -> None:
        rows = _normalize_chunk_rows(doc_id, chunk_texts)

        with self._lock:
            conn = connect_doc_db(self.db_path, readonly=False)
            cur = conn.cursor()
            try:
                cur.execute("BEGIN IMMEDIATE;")
                self._ensure_schema_migrations(cur)

                cur.execute("DELETE FROM embeddings WHERE doc_id = ?", (doc_id,))
                cur.execute("DELETE FROM chunks WHERE doc_id = ?", (doc_id,))

                if rows:
                    cur.executemany(
                        "INSERT INTO chunks (doc_id, chunk_id, text, char_start, char_end) VALUES (?, ?, ?, ?, ?)",
                        rows,
                    )

                cur.execute(
                    """
                    UPDATE documents
                    SET total_chunks = ?, embedding_status = 'pending'
                    WHERE doc_id = ?
                    """,
                    (int(len(rows)), doc_id),
                )

                cur.execute("COMMIT;")
            except Exception:
                try:
                    cur.execute("ROLLBACK;")
                except Exception:
                    pass
                raise
            finally:
                conn.close()

    def upsert_document_with_chunks(
        self,
        *,
        doc_id: str,
        library_id: str,
        filename: str,
        filetype: str,
        file_size: int,
        chunk_texts: List[Any],
        uploaded_at: Optional[str] = None,
        published_at: Optional[str] = None,
        language: str = "auto",
    ) -> None:
        uploaded_at = _normalize_iso_or_none(uploaded_at) or _utc_now_iso()
        published_at = _normalize_iso_or_none(published_at) or uploaded_at
        rows = _normalize_chunk_rows(doc_id, chunk_texts)

        with self._lock:
            conn = connect_doc_db(self.db_path, readonly=False)
            cur = conn.cursor()
            try:
                cur.execute("BEGIN IMMEDIATE;")
                self._ensure_schema_migrations(cur)

                cur.execute(
                    """
                    INSERT INTO documents
                    (doc_id, library_id, filename, filetype, file_size, total_chunks, embedding_status, uploaded_at, published_at, last_accessed, access_count, language)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(doc_id) DO UPDATE SET
                      library_id=excluded.library_id,
                      filename=excluded.filename,
                      filetype=excluded.filetype,
                      file_size=excluded.file_size,
                      total_chunks=excluded.total_chunks,
                      embedding_status='pending',
                      uploaded_at=excluded.uploaded_at,
                      published_at=excluded.published_at,
                      language=excluded.language
                    ;
                    """,
                    (
                        doc_id,
                        library_id,
                        filename,
                        filetype,
                        int(file_size),
                        int(len(rows)),
                        "pending",
                        uploaded_at,
                        published_at,
                        uploaded_at,
                        0,
                        language,
                    ),
                )

                cur.execute("DELETE FROM embeddings WHERE doc_id = ?", (doc_id,))
                cur.execute("DELETE FROM chunks WHERE doc_id = ?", (doc_id,))

                if rows:
                    cur.executemany(
                        "INSERT INTO chunks (doc_id, chunk_id, text, char_start, char_end) VALUES (?, ?, ?, ?, ?)",
                        rows,
                    )

                cur.execute("COMMIT;")
            except Exception:
                try:
                    cur.execute("ROLLBACK;")
                except Exception:
                    pass
                raise
            finally:
                conn.close()

    def update_chunk_char_ranges_bulk(
        self,
        *,
        doc_id: str,
        chunk_ranges: List[Tuple[int, int, int]],
    ) -> None:
        rows = []
        seen = set()

        for item in chunk_ranges or []:
            if not isinstance(item, (list, tuple)) or len(item) < 3:
                continue
            chunk_id = _coerce_int_or_none(item[0])
            char_start = _coerce_int_or_none(item[1])
            char_end = _coerce_int_or_none(item[2])

            if chunk_id is None or char_start is None or char_end is None:
                continue
            if char_end < char_start:
                continue
            if chunk_id in seen:
                continue

            seen.add(chunk_id)
            rows.append((char_start, char_end, doc_id, chunk_id))

        if not rows:
            return

        with self._lock:
            conn = connect_doc_db(self.db_path, readonly=False)
            cur = conn.cursor()
            try:
                cur.execute("BEGIN IMMEDIATE;")
                cur.executemany(
                    """
                    UPDATE chunks
                    SET char_start = ?, char_end = ?
                    WHERE doc_id = ? AND chunk_id = ?
                    """,
                    rows,
                )
                cur.execute("COMMIT;")
            except Exception:
                try:
                    cur.execute("ROLLBACK;")
                except Exception:
                    pass
                raise
            finally:
                conn.close()

    def add_embeddings_bulk(
        self,
        *,
        doc_id: str,
        chunk_ids: List[int],
        embeddings: List[np.ndarray],
        model: str,
        dim: int,
    ) -> None:
        if len(chunk_ids) != len(embeddings):
            raise ValueError("chunk_ids 与 embeddings 长度不一致")

        rows = []
        for cid, emb in zip(chunk_ids, embeddings):
            emb_bytes = np.asarray(emb, dtype="float32").tobytes()
            rows.append((doc_id, int(cid), emb_bytes, model, int(dim)))

        with self._lock:
            conn = connect_doc_db(self.db_path, readonly=False)
            cur = conn.cursor()
            try:
                cur.execute("BEGIN IMMEDIATE;")
                if rows:
                    cur.executemany(
                        """
                        INSERT OR REPLACE INTO embeddings
                        (doc_id, chunk_id, embedding, embedding_model, embedding_dim)
                        VALUES (?, ?, ?, ?, ?)
                        """,
                        rows,
                    )
                cur.execute("COMMIT;")
            except Exception:
                try:
                    cur.execute("ROLLBACK;")
                except Exception:
                    pass
                raise
            finally:
                conn.close()

    def update_embedding_status(self, doc_id: str, status: str) -> None:
        with self._lock:
            conn = connect_doc_db(self.db_path, readonly=False)
            cur = conn.cursor()
            try:
                cur.execute("BEGIN IMMEDIATE;")
                cur.execute("UPDATE documents SET embedding_status = ? WHERE doc_id = ?", (status, doc_id))
                cur.execute("COMMIT;")
            except Exception:
                try:
                    cur.execute("ROLLBACK;")
                except Exception:
                    pass
                raise
            finally:
                conn.close()

    def update_document_published_at(self, doc_id: str, published_at: Optional[str]) -> Dict[str, Any]:
        result: Dict[str, Any] = {
            "ok": True,
            "doc_id": doc_id,
            "published_at": _normalize_iso_or_none(published_at),
            "updated_documents": 0,
            "reason": "no_change",
        }

        normalized = _normalize_iso_or_none(published_at)
        if not doc_id:
            result["ok"] = False
            result["reason"] = "missing_doc_id"
            return result
        if not normalized:
            result["reason"] = "missing_published_at"
            return result

        with self._lock:
            conn = connect_doc_db(self.db_path, readonly=False)
            cur = conn.cursor()
            try:
                cur.execute("BEGIN IMMEDIATE;")
                self._ensure_schema_migrations(cur)

                cur.execute("SELECT published_at FROM documents WHERE doc_id = ?", (doc_id,))
                row = cur.fetchone()
                if row is None:
                    result["ok"] = False
                    result["reason"] = "doc_not_found"
                    cur.execute("COMMIT;")
                    return result

                current = _normalize_iso_or_none(row["published_at"]) if row["published_at"] is not None else None
                if current == normalized:
                    cur.execute("COMMIT;")
                    result["reason"] = "no_change"
                    return result

                cur.execute(
                    """
                    UPDATE documents
                    SET published_at = ?
                    WHERE doc_id = ?
                    """,
                    (normalized, doc_id),
                )
                result["updated_documents"] = cur.rowcount if cur.rowcount is not None else 0
                result["reason"] = "updated" if result["updated_documents"] > 0 else "no_change"
                cur.execute("COMMIT;")
                return result
            except Exception as e:
                try:
                    cur.execute("ROLLBACK;")
                except Exception:
                    pass
                result["ok"] = False
                result["reason"] = "error"
                result["error"] = str(e)
                return result
            finally:
                conn.close()

    def rename_document(self, doc_id: str, new_filename: str) -> Dict[str, Any]:
        result: Dict[str, Any] = {
            "ok": True,
            "doc_id": doc_id,
            "new_filename": new_filename,
            "updated_documents": 0,
        }

        with self._lock:
            conn = connect_doc_db(self.db_path, readonly=False)
            cur = conn.cursor()
            try:
                cur.execute("BEGIN IMMEDIATE;")
                cur.execute("UPDATE documents SET filename = ? WHERE doc_id = ?", (new_filename, doc_id))
                result["updated_documents"] = cur.rowcount if cur.rowcount is not None else 0
                cur.execute("COMMIT;")
                return result
            except Exception as e:
                try:
                    cur.execute("ROLLBACK;")
                except Exception:
                    pass
                result["ok"] = False
                result["error"] = str(e)
                return result
            finally:
                conn.close()

    def delete_document(self, doc_id: str) -> Dict[str, Any]:
        result: Dict[str, Any] = {
            "ok": True,
            "doc_id": doc_id,
            "deleted_embeddings": 0,
            "deleted_chunks": 0,
            "deleted_documents": 0,
        }

        with self._lock:
            conn = connect_doc_db(self.db_path, readonly=False)
            cur = conn.cursor()
            try:
                cur.execute("BEGIN IMMEDIATE;")
                cur.execute("DELETE FROM embeddings WHERE doc_id = ?", (doc_id,))
                result["deleted_embeddings"] = cur.rowcount if cur.rowcount is not None else 0

                cur.execute("DELETE FROM chunks WHERE doc_id = ?", (doc_id,))
                result["deleted_chunks"] = cur.rowcount if cur.rowcount is not None else 0

                cur.execute("DELETE FROM documents WHERE doc_id = ?", (doc_id,))
                result["deleted_documents"] = cur.rowcount if cur.rowcount is not None else 0

                cur.execute("COMMIT;")
                return result
            except Exception as e:
                try:
                    cur.execute("ROLLBACK;")
                except Exception:
                    pass
                result["ok"] = False
                result["error"] = str(e)
                return result
            finally:
                conn.close()

    def get_chunks(self, doc_id: str) -> List[Dict[str, Any]]:
        conn: Optional[sqlite3.Connection] = None
        try:
            conn = connect_doc_db(self.db_path, readonly=True)
            cur = conn.cursor()
            cur.execute(
                "SELECT chunk_id, text, char_start, char_end FROM chunks WHERE doc_id = ? ORDER BY chunk_id",
                (doc_id,),
            )
            rows = cur.fetchall()
            return [
                {
                    "chunk_id": int(r["chunk_id"]),
                    "text": r["text"],
                    "char_start": int(r["char_start"]) if r["char_start"] is not None else None,
                    "char_end": int(r["char_end"]) if r["char_end"] is not None else None,
                }
                for r in rows
            ]
        except Exception as e:
            print(f"[ERROR] 获取 chunks 失败：{e}")
            return []
        finally:
            if conn is not None:
                try:
                    conn.close()
                except Exception:
                    pass

    def get_embeddings(self, doc_id: str) -> Dict[int, np.ndarray]:
        conn: Optional[sqlite3.Connection] = None
        try:
            conn = connect_doc_db(self.db_path, readonly=True)
            cur = conn.cursor()
            cur.execute(
                "SELECT chunk_id, embedding, embedding_dim FROM embeddings WHERE doc_id = ? ORDER BY chunk_id",
                (doc_id,),
            )
            rows = cur.fetchall()
            result: Dict[int, np.ndarray] = {}
            for r in rows:
                cid = int(r["chunk_id"])
                result[cid] = np.frombuffer(r["embedding"], dtype="float32")
            return result
        except Exception as e:
            print(f"[ERROR] 获取 embeddings 失败：{e}")
            return {}
        finally:
            if conn is not None:
                try:
                    conn.close()
                except Exception:
                    pass

    def get_all_embeddings_as_matrix(self, doc_id: str) -> Tuple[np.ndarray, List[int]]:
        conn: Optional[sqlite3.Connection] = None
        try:
            conn = connect_doc_db(self.db_path, readonly=True)
            cur = conn.cursor()
            cur.execute(
                "SELECT chunk_id, embedding, embedding_dim FROM embeddings WHERE doc_id = ? ORDER BY chunk_id",
                (doc_id,),
            )
            rows = cur.fetchall()
            if not rows:
                return np.array([], dtype="float32").reshape(0, 1536), []

            embeddings: List[np.ndarray] = []
            chunk_ids: List[int] = []
            for r in rows:
                chunk_ids.append(int(r["chunk_id"]))
                embeddings.append(np.frombuffer(r["embedding"], dtype="float32"))

            return np.array(embeddings, dtype="float32"), chunk_ids
        except Exception as e:
            print(f"[ERROR] 获取 embeddings 矩阵失败：{e}")
            return np.array([], dtype="float32").reshape(0, 1536), []
        finally:
            if conn is not None:
                try:
                    conn.close()
                except Exception:
                    pass

    def list_documents(
        self,
        *,
        library_id: Optional[str] = None,
        limit: Optional[int] = None,
        order_by: str = "uploaded_at_desc",
    ) -> List[Dict[str, Any]]:
        conn = None
        try:
            conn = connect_doc_db(self.db_path, readonly=True)
            cur = conn.cursor()

            allowed_order = {
                "uploaded_at_desc": "uploaded_at DESC",
                "uploaded_at_asc": "uploaded_at ASC",
                "published_at_desc": "published_at DESC",
                "published_at_asc": "published_at ASC",
                "filename_asc": "filename ASC",
                "filename_desc": "filename DESC",
            }

            published_expr = self._documents_published_expr(cur)
            requested_order = str(order_by or "").strip()
            if requested_order == "published_at_desc":
                order_sql = f"{published_expr} DESC"
            elif requested_order == "published_at_asc":
                order_sql = f"{published_expr} ASC"
            else:
                order_sql = allowed_order.get(requested_order, "uploaded_at DESC")

            sql = f"""
                SELECT
                    doc_id,
                    library_id,
                    filename,
                    filetype,
                    file_size,
                    total_chunks,
                    embedding_status,
                    uploaded_at,
                    {published_expr} AS published_at,
                    last_accessed,
                    access_count,
                    language
                FROM documents
            """
            params: List[Any] = []

            if library_id:
                sql += " WHERE library_id = ?"
                params.append(str(library_id))

            sql += f" ORDER BY {order_sql}"

            if limit is not None:
                try:
                    safe_limit = max(1, int(limit))
                    sql += " LIMIT ?"
                    params.append(safe_limit)
                except Exception:
                    pass

            cur.execute(sql, params)
            rows = cur.fetchall()

            out: List[Dict[str, Any]] = []
            for row in rows:
                uploaded_at = row["uploaded_at"] if row["uploaded_at"] is not None else ""
                published_at = row["published_at"] if row["published_at"] is not None else uploaded_at
                out.append(
                    {
                        "doc_id": str(row["doc_id"] or ""),
                        "library_id": str(row["library_id"] or ""),
                        "filename": str(row["filename"] or ""),
                        "filetype": str(row["filetype"] or ""),
                        "file_size": int(row["file_size"] or 0),
                        "total_chunks": int(row["total_chunks"] or 0),
                        "embedding_status": str(row["embedding_status"] or ""),
                        "uploaded_at": str(uploaded_at or ""),
                        "published_at": str(published_at or ""),
                        "last_accessed": str(row["last_accessed"] or ""),
                        "access_count": int(row["access_count"] or 0),
                        "language": str(row["language"] or "auto"),
                    }
                )
            return out
        except Exception as e:
            print(f"[ERROR] list_documents 失败：{str(e)}")
            return []
        finally:
            try:
                if conn:
                    conn.close()
            except Exception:
                pass

    def get_statistics(self) -> Dict[str, Any]:
        conn: Optional[sqlite3.Connection] = None
        try:
            conn = connect_doc_db(self.db_path, readonly=True)
            cur = conn.cursor()

            cur.execute("SELECT COUNT(*) AS c FROM documents")
            total_docs = int(cur.fetchone()["c"])

            cur.execute("SELECT COUNT(*) AS c FROM chunks")
            total_chunks = int(cur.fetchone()["c"])

            cur.execute(
                """
                SELECT COUNT(*) AS c
                FROM embeddings e
                INNER JOIN chunks c
                  ON c.doc_id = e.doc_id
                 AND c.chunk_id = e.chunk_id
                """
            )
            embedded_chunks = int(cur.fetchone()["c"])

            cur.execute(
                """
                SELECT COUNT(DISTINCT e.doc_id) AS c
                FROM embeddings e
                INNER JOIN chunks c
                  ON c.doc_id = e.doc_id
                 AND c.chunk_id = e.chunk_id
                """
            )
            embedded_docs = int(cur.fetchone()["c"])

            return {
                "total_docs": total_docs,
                "total_chunks": total_chunks,
                "embedded_docs": embedded_docs,
                "embedding_coverage": f"{embedded_chunks}/{total_chunks}",
                "embedding_pct": (embedded_chunks / total_chunks * 100) if total_chunks > 0 else 0,
                "total_bookmarks": 0,
            }
        except Exception as e:
            print(f"[ERROR] 获取统计信息失败：{e}")
            return {
                "total_docs": 0,
                "total_chunks": 0,
                "embedded_docs": 0,
                "embedding_coverage": "0/0",
                "embedding_pct": 0,
                "total_bookmarks": 0,
            }
        finally:
            if conn is not None:
                try:
                    conn.close()
                except Exception:
                    pass

def get_doc_db_sqlite(user_base_path: str, library_id: Optional[str] = None) -> DocDBSQLite:
    base_key = str(Path(user_base_path).resolve())
    if library_id:
        db_path = Path(user_base_path) / "libraries" / library_id / "docs" / "doc_db.sqlite"
        db_path.parent.mkdir(parents=True, exist_ok=True)
        key = f"{base_key}::{library_id}"
        if key not in _db_instances:
            _db_instances[key] = DocDBSQLite(user_base_path, db_path=str(db_path))
        return _db_instances[key]

    key = base_key
    if key not in _db_instances:
        _db_instances[key] = DocDBSQLite(user_base_path)
    return _db_instances[key]

