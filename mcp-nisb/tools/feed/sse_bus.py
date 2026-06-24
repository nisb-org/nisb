#!/usr/bin/env python3
from __future__ import annotations

import time
import queue
from typing import Any, Dict, List

# user_id -> list[Queue]
_SUBS: Dict[str, List["queue.Queue"]] = {}


def subscribe(user_id: str) -> "queue.Queue":
    q: "queue.Queue" = queue.Queue(maxsize=200)
    _SUBS.setdefault(user_id, []).append(q)
    return q


def unsubscribe(user_id: str, q: "queue.Queue") -> None:
    arr = _SUBS.get(user_id) or []
    try:
        arr.remove(q)
    except Exception:
        pass
    if not arr and user_id in _SUBS:
        _SUBS.pop(user_id, None)


def publish(user_id: str, event: Dict[str, Any]) -> None:
    arr = _SUBS.get(user_id) or []
    if not arr:
        return
    dead = []
    for q in arr:
        try:
            q.put_nowait(event)
        except Exception:
            dead.append(q)
    for q in dead:
        unsubscribe(user_id, q)


def sse_encode(event: Dict[str, Any]) -> str:
    # SSE: data: <json>\n\n
    import json
    return f"data: {json.dumps(event, ensure_ascii=False)}\n\n"


def sse_ping() -> str:
    # comment line as ping
    return f": ping {int(time.time())}\n\n"

