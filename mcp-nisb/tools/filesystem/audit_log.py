from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any, Dict

from .config import get_base_path


def _audit_dir(base_path: str) -> str:
    return os.path.join(base_path, "storage", "audit")


def _audit_file(base_path: str) -> str:
    return os.path.join(_audit_dir(base_path), "filesystem_audit.jsonl")


def append_fs_audit_event(
    *,
    user_id: str,
    email: str,
    name: str,
    event: Dict[str, Any],
) -> None:
    """
    追加一条 JSONL 审计事件（append-only）。
    失败只打印，不影响主流程。

    约定：
    - event 内允许包含 request_id，用于与 turns.jsonl/rooms events 回链。
    """
    try:
        base_path = get_base_path(user_id, email, name)
        os.makedirs(_audit_dir(base_path), exist_ok=True)
        path = _audit_file(base_path)

        e = dict(event or {})
        e.setdefault("ts", datetime.now(timezone.utc).isoformat())
        e.setdefault("user_id", user_id)
        e.setdefault("source", "filesystem")

        line = json.dumps(e, ensure_ascii=False)
        with open(path, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception as ex:
        print(f"[FS-AUDIT] append failed: {ex}")

