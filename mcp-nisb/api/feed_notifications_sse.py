#!/usr/bin/env python3
from __future__ import annotations

import time
from typing import Iterator

from fastapi import APIRouter, Request
from starlette.responses import StreamingResponse

from tools.feed.sse_bus import subscribe, unsubscribe, sse_encode, sse_ping

router = APIRouter()

@router.get("/api/feed/notifications/stream")
def feed_notifications_stream(request: Request) -> StreamingResponse:
    userid = getattr(request.state, "userid", None)
    if not userid:
        def gen_empty() -> Iterator[str]:
            yield sse_encode({"type": "error", "message": "unauthorized"})
        return StreamingResponse(gen_empty(), media_type="text/event-stream")

    q = subscribe(str(userid))

    def gen() -> Iterator[str]:
        last_ping = 0.0
        try:
            while True:
                now = time.time()
                if now - last_ping >= 15:
                    last_ping = now
                    yield sse_ping()

                try:
                    ev = q.get(timeout=1.0)
                    yield sse_encode(ev)
                except Exception:
                    continue
        finally:
            unsubscribe(str(userid), q)

    return StreamingResponse(gen(), media_type="text/event-stream")

