from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


DOC_EVENTS_REL_PATH = Path("storage") / "logs" / "doc_operations.jsonl"


def append_jsonl_line(path: Path, record: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(record, ensure_ascii=False)
    with open(path, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def append_doc_event(
    *,
    user_base: Path,
    request_id: str,
    action: str,
    library_id: str,
    doc_ids: List[str],
    status: str,
    payload: Optional[Dict[str, Any]] = None,
) -> None:
    """
    append-only JSONL event（失败不影响主流程，只打到 stdout 以便 docker logs 可见）
    """
    event_path = user_base / DOC_EVENTS_REL_PATH
    safe_payload = dict(payload or {})

    if "error" in safe_payload and isinstance(safe_payload["error"], str):
        safe_payload["error"] = safe_payload["error"][:300]

    record = {
        "created_at": datetime.now().isoformat(),
        "source_type": "doc",
        "source_id": library_id,
        "action": action,
        "request_id": request_id,
        "doc_ids": doc_ids,
        "status": status,
        "payload": safe_payload,
    }

    try:
        append_jsonl_line(event_path, record)
    except Exception as e:
        print(
            "[doc_event_append_failed]"
            f" request_id={request_id}"
            f" library_id={library_id}"
            f" action={action}"
            f" error={str(e)}"
            f" path={str(event_path)}"
        )

