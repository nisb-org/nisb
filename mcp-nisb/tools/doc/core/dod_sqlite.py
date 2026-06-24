from __future__ import annotations

from typing import Any

from tools.doc.doc_db_sqlite import connect_doc_db


def connect_doc_db_budgeted(db_path: str, *, readonly: bool, busy_timeout_ms: int = 10_000) -> Any:
    """
    统一 DB 连接预算：设置 busy_timeout，降低 SQLITE_BUSY 误伤概率。
    PRAGMA busy_timeout 是 SQLite 官方支持的连接级设置方式。 [web:1029]
    """
    conn = connect_doc_db(db_path, readonly=readonly)

    try:
        # 连接级生效
        conn.execute(f"PRAGMA busy_timeout = {int(busy_timeout_ms)};")
    except Exception:
        # 不阻断主流程，避免某些绑定/只读连接下执行失败导致功能不可用
        pass

    return conn

