#!/usr/bin/env python3
"""
NISB HTTP API Gateway
FastAPI HTTP 网关：
- /api/mcp/call & /mcp/call
- /api/mcp/stream & /mcp/stream  (SSE)

职责：
- 校验 Authorization: Bearer <token>
- 注入 user_id/token/basepath 等到工具 arguments
- 注入 request_id（可回放/可审计链路关键键）
- streaming 断开检测：client disconnect -> aborted 真源落盘

兼容策略：
- chat/qa 主链（nisb_chat_send / nisb_chat_orchestrate）继续走正式字段统一
- 非 chat 工具在 /mcp/call 上保持原始结果返回，避免前端旧消费方全部失效
"""

import sys
sys.path.insert(0, "/srv")

import os
import json
import queue
import threading
import traceback
import mimetypes
import time
import subprocess
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List

import anyio
from fastapi import FastAPI, HTTPException, Header, Body, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, FileResponse
from pydantic import BaseModel
from starlette.concurrency import run_in_threadpool
from starlette.types import ASGIApp, Scope, Receive, Send

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.events import (
    EVENT_JOB_ERROR,
    EVENT_JOB_MISSED,
    EVENT_JOB_MAX_INSTANCES,
)

from core.user_system import UserAuthManager
from nisb_mcp import TOOLS

from tools.rss.auto_fetch_scheduler import nisb_rss_auto_fetch_scheduler_tick_all_users
from tools.rss.auto_import_scheduler import (
    nisb_rss_auto_import_scheduler_tick_all_users,
    nisb_rss_auto_import_scheduler_next_run_ts_all_users,
)
from tools.rss.auto_cleanup_scheduler import nisb_rss_auto_cleanup_scheduler_tick_all_users

from tools.rss.cache_control import nisb_rss_cache_clear
from api_gateway_auth import (
    auth_and_inject as _auth_and_inject,
    build_tool_kwargs as _build_tool_kwargs,
)
from api_gateway_chat_stream import (
    CHAT_ALLOWED_EVENTS as _CHAT_ALLOWED_EVENTS,
    CHAT_STREAM_TOOLS as _CHAT_STREAM_TOOLS,
    build_done_payload as _build_done_payload,
    maybe_pseudo_stream_delay as _maybe_pseudo_stream_delay,
    normalize_chat_call_result as _normalize_chat_call_result,
    normalize_chat_event_name as _normalize_chat_event_name,
    normalize_chat_payload as _normalize_chat_payload,
    read_array as _read_array,
    read_object as _read_object,
    read_std_conv_id as _read_std_conv_id,
    read_std_mcp_overrides as _read_std_mcp_overrides,
    read_std_rag_mode as _read_std_rag_mode,
    read_std_request_id as _read_std_request_id,
    read_string as _read_string,
)

app = FastAPI(title="NISB HTTP API Gateway")


class AttachUseridASGIMiddleware:
    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        state = scope.setdefault("state", {})
        state["userid"] = None
        state["token"] = None

        auth = ""
        for k, v in scope.get("headers") or []:
            if k.lower() == b"authorization":
                try:
                    auth = v.decode("utf-8", errors="ignore")
                except Exception:
                    auth = ""
                break

        if auth.startswith("Bearer "):
            token = auth.replace("Bearer ", "", 1).strip()
            try:
                is_valid, user_id = UserAuthManager().verify_token(token)
                if is_valid and user_id:
                    state["userid"] = user_id
                    state["token"] = token
            except Exception:
                pass

        await self.app(scope, receive, send)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(AttachUseridASGIMiddleware)

WHITELIST_TOOLS = [
    "nisb_user_register",
    "nisb_user_login",
]

DATA_ROOT = os.environ.get("NISB_BASE_PATH", "/data").rstrip("/")
USERS_ROOT = f"{DATA_ROOT}/users"

NISB_LLM_CONCURRENCY = int(os.getenv("NISB_LLM_CONCURRENCY", "2"))
_LLM_GUARD = anyio.Semaphore(NISB_LLM_CONCURRENCY)

NISB_RSS_SEARCH_CONCURRENCY = int(os.getenv("NISB_RSS_SEARCH_CONCURRENCY", "1"))
_RSS_SEARCH_GUARD = anyio.Semaphore(max(1, int(NISB_RSS_SEARCH_CONCURRENCY or 1)))

_RSS_SEARCH_TOOLS = {
    "nisb_rss_gate_candidates",
    "nisb_rss_semantic_search",
}

NISB_RSS_PRESSURE_CONCURRENCY = int(os.getenv("NISB_RSS_PRESSURE_CONCURRENCY", "1"))
_RSS_PRESSURE_GUARD = anyio.Semaphore(max(1, int(NISB_RSS_PRESSURE_CONCURRENCY or 1)))

_RSS_PRESSURE_TOOLS = {
    "nisb_rss_gate_candidates",
    "nisb_rss_semantic_search",
    "nisb_rss_fetch",
    "nisb_rss_fetch_due",
    "nisb_rss_auto_fetch_run_now",
    "nisb_rss_auto_import_run_rule",
    "nisb_rss_auto_import_run_due",
    "nisb_rss_gate_import_to_library",
    "nisb_rss_gate_bulk_delete",
    "nisb_rss_data_cleanup",
    "nisb_rss_auto_cleanup_run_now",
}

_RSS_HEAVY_RSS_JOBS = {
    "nisb_rss_fetch",
    "nisb_rss_fetch_due",
    "nisb_rss_auto_fetch_run_now",
    "nisb_rss_auto_import_run_rule",
    "nisb_rss_auto_import_run_due",
    "nisb_rss_gate_import_to_library",
    "nisb_rss_gate_bulk_delete",
    "nisb_rss_data_cleanup",
    "nisb_rss_auto_cleanup_run_now",
}

_RSS_PRESSURE_LOCK_PATH = os.getenv("NISB_RSS_PRESSURE_LOCK_PATH", "/tmp/nisb_rss_pressure.lock")

NISB_CHAT_PSEUDO_STREAM_ENABLED = str(os.getenv("NISB_CHAT_PSEUDO_STREAM_ENABLED", "1")).strip() not in ("0", "false", "False")
NISB_CHAT_PSEUDO_STREAM_DELAY_MS = max(0, int(os.getenv("NISB_CHAT_PSEUDO_STREAM_DELAY_MS", "18")))
NISB_CHAT_PSEUDO_STREAM_META_DELAY_MS = max(0, int(os.getenv("NISB_CHAT_PSEUDO_STREAM_META_DELAY_MS", "0")))


def _rss_pressure_lock_acquire() -> Any:
    try:
        os.makedirs(os.path.dirname(_RSS_PRESSURE_LOCK_PATH), exist_ok=True)
    except Exception:
        pass

    f = open(_RSS_PRESSURE_LOCK_PATH, "a+", encoding="utf-8")
    try:
        import fcntl
        fcntl.flock(f.fileno(), fcntl.LOCK_EX)
    except Exception:
        pass
    return f


def _rss_pressure_lock_release(f: Any) -> None:
    if f is None:
        return
    try:
        import fcntl
        try:
            fcntl.flock(f.fileno(), fcntl.LOCK_UN)
        except Exception:
            pass
    except Exception:
        pass
    try:
        f.close()
    except Exception:
        pass


async def _rss_pressure_lock_acquire_async() -> Any:
    return await anyio.to_thread.run_sync(_rss_pressure_lock_acquire)


async def _rss_pressure_lock_release_async(f: Any) -> None:
    await anyio.to_thread.run_sync(lambda: _rss_pressure_lock_release(f))


_RSS_SCHEDULER: Optional[BackgroundScheduler] = None

_RSS_AUTO_FETCH_ENABLED = str(os.getenv("NISB_RSS_AUTO_FETCH_ENABLED", "1")).strip() not in ("0", "false", "False")
_RSS_AUTO_FETCH_USERS_ROOT = os.getenv("NISB_RSS_AUTO_FETCH_USERS_ROOT", USERS_ROOT)

_RSS_AUTO_IMPORT_ENABLED = str(os.getenv("NISB_RSS_AUTO_IMPORT_ENABLED", "1")).strip() not in ("0", "false", "False")
_RSS_AUTO_IMPORT_USERS_ROOT = os.getenv("NISB_RSS_AUTO_IMPORT_USERS_ROOT", _RSS_AUTO_FETCH_USERS_ROOT)
_RSS_AUTO_CLEANUP_ENABLED = str(os.getenv("NISB_RSS_AUTO_CLEANUP_ENABLED", "1")).strip() not in ("0", "false", "False")
_RSS_AUTO_CLEANUP_USERS_ROOT = os.getenv("NISB_RSS_AUTO_CLEANUP_USERS_ROOT", _RSS_AUTO_FETCH_USERS_ROOT)

try:
    _RSS_AUTO_CLEANUP_INTERVAL_MINUTES = int(os.getenv("NISB_RSS_AUTO_CLEANUP_INTERVAL_MINUTES", "30"))
except Exception:
    _RSS_AUTO_CLEANUP_INTERVAL_MINUTES = 30
_RSS_AUTO_CLEANUP_INTERVAL_MINUTES = max(10, min(1440, int(_RSS_AUTO_CLEANUP_INTERVAL_MINUTES or 30)))

try:
    _RSS_AUTO_CLEANUP_TIMEOUT_SECONDS = int(os.getenv("NISB_RSS_AUTO_CLEANUP_TIMEOUT_SECONDS", "600"))
except Exception:
    _RSS_AUTO_CLEANUP_TIMEOUT_SECONDS = 600
_RSS_AUTO_CLEANUP_TIMEOUT_SECONDS = max(60, min(3600, int(_RSS_AUTO_CLEANUP_TIMEOUT_SECONDS or 600)))

_RSS_SCHEDULER_LOCK_FD = None
_RSS_SCHEDULER_LOCK_PATH = os.getenv("NISB_RSS_SCHEDULER_LOCK_PATH", "/tmp/nisb_rss_scheduler.lock")

_RSS_SCHEDULER_LOG_PATH = os.getenv("NISB_RSS_SCHEDULER_LOG_PATH", f"{DATA_ROOT}/logs/rss_scheduler.log")

_RSS_SCHEDULER_START_DELAY_SECONDS = int(os.getenv("NISB_RSS_SCHEDULER_START_DELAY_SECONDS", "12"))
_RSS_JOB_BACKOFF_SECONDS = max(0, int(os.getenv("NISB_RSS_JOB_BACKOFF_SECONDS", "0")))
_RSS_SCHEDULER_SUBPROCESS = str(os.getenv("NISB_RSS_SCHEDULER_SUBPROCESS", "1")).strip() not in ("0", "false", "False")
_RSS_AUTO_FETCH_TIMEOUT_SECONDS = int(os.getenv("NISB_RSS_AUTO_FETCH_TIMEOUT_SECONDS", "55"))
_RSS_AUTO_IMPORT_TIMEOUT_SECONDS = int(os.getenv("NISB_RSS_AUTO_IMPORT_TIMEOUT_SECONDS", "55"))

_RSS_JOB_BACKOFF_UNTIL: Dict[str, float] = {}
_RSS_JOB_LAST_BACKOFF_LOG_TS: Dict[str, float] = {}

_JOB_LOCKS: Dict[str, threading.Lock] = {
    "rss_auto_fetch_tick": threading.Lock(),
    "rss_auto_import_tick": threading.Lock(),
}

_RSS_GLOBAL_BUSY_LOCK = threading.Lock()


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _rss_log(line: str) -> None:
    try:
        os.makedirs(os.path.dirname(_RSS_SCHEDULER_LOG_PATH), exist_ok=True)
        ts = datetime.now(timezone.utc).isoformat()
        with open(_RSS_SCHEDULER_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(f"[{ts}] {line}\n")
    except Exception:
        pass


def _try_acquire_scheduler_lock() -> bool:
    global _RSS_SCHEDULER_LOCK_FD
    try:
        import fcntl
        os.makedirs(os.path.dirname(_RSS_SCHEDULER_LOCK_PATH), exist_ok=True)
        fd = open(_RSS_SCHEDULER_LOCK_PATH, "a+")
        fcntl.flock(fd.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        _RSS_SCHEDULER_LOCK_FD = fd
        return True
    except Exception:
        try:
            if _RSS_SCHEDULER_LOCK_FD:
                _RSS_SCHEDULER_LOCK_FD.close()
        except Exception:
            pass
        _RSS_SCHEDULER_LOCK_FD = None
        return False


def _release_scheduler_lock() -> None:
    global _RSS_SCHEDULER_LOCK_FD
    try:
        if _RSS_SCHEDULER_LOCK_FD is not None:
            try:
                import fcntl
                fcntl.flock(_RSS_SCHEDULER_LOCK_FD.fileno(), fcntl.LOCK_UN)
            except Exception:
                pass
            try:
                _RSS_SCHEDULER_LOCK_FD.close()
            except Exception:
                pass
    finally:
        _RSS_SCHEDULER_LOCK_FD = None


def _backoff_active(job_id: str) -> bool:
    if int(_RSS_JOB_BACKOFF_SECONDS or 0) <= 0:
        return False

    until_ts = float(_RSS_JOB_BACKOFF_UNTIL.get(job_id, 0.0) or 0.0)
    if time.time() < until_ts:
        last_log = float(_RSS_JOB_LAST_BACKOFF_LOG_TS.get(job_id, 0.0) or 0.0)
        if time.time() - last_log > 60:
            _RSS_JOB_LAST_BACKOFF_LOG_TS[job_id] = time.time()
            left = int(max(0, until_ts - time.time()))
            print(f"[INFO] {job_id} backoff active: {left}s remaining")
        return True
    return False


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


def _read_json_small(path: str, *, max_bytes: int = 2_000_000) -> Optional[Dict[str, Any]]:
    try:
        if not os.path.exists(path):
            return None
        sz = os.path.getsize(path)
        if sz < 5 or sz > max_bytes:
            return None
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def _scan_next_fetch_due_ts(users_root: str, *, now_ts: Optional[float] = None) -> Optional[float]:
    if now_ts is None:
        now_ts = time.time()
    now_ts = float(now_ts)

    try:
        uids = [d for d in os.listdir(users_root) if d and not d.startswith(".")]
    except Exception:
        uids = []

    best: Optional[float] = None
    for uid in uids:
        basepath = os.path.join(users_root, uid)
        if not os.path.isdir(basepath):
            continue
        if not os.path.isdir(os.path.join(basepath, "rss")):
            continue

        p = os.path.join(basepath, "rss", "auto_fetch_config.json")
        doc = _read_json_small(p)
        if not isinstance(doc, dict):
            continue
        if not bool(doc.get("enabled", False)):
            continue

        nxt = _parse_iso_ts(str(doc.get("next_run_at") or ""))
        if nxt is None:
            nxt = now_ts

        if best is None or nxt < best:
            best = nxt

    return best


def _scan_next_import_due_ts(users_root: str, *, now_ts: Optional[float] = None) -> Optional[float]:
    if now_ts is None:
        now_ts = time.time()
    now_ts = float(now_ts)
    try:
        info = nisb_rss_auto_import_scheduler_next_run_ts_all_users(users_root, now_ts=now_ts)
        if isinstance(info, dict) and info.get("success") is True:
            ts = info.get("next_run_ts", None)
            if ts is None:
                return None
            return float(ts)
    except Exception:
        pass
    return None


def _schedule_date_job(job_id: str, run_at_ts: float, func) -> None:
    global _RSS_SCHEDULER
    if _RSS_SCHEDULER is None:
        return

    ts = float(run_at_ts)
    now_ts = time.time()
    if ts < now_ts + 1.0:
        ts = now_ts + 2.0
    dt = datetime.fromtimestamp(ts, tz=timezone.utc)

    try:
        existing = _RSS_SCHEDULER.get_job(job_id)
        if existing is not None:
            nrt = getattr(existing, "next_run_time", None)
            if nrt is not None:
                try:
                    if abs(nrt.timestamp() - ts) < 0.5:
                        return
                except Exception:
                    pass
    except Exception:
        pass

    _RSS_SCHEDULER.add_job(
        func=func,
        trigger="date",
        run_date=dt,
        id=job_id,
        replace_existing=True,
        max_instances=1,
        coalesce=True,
        misfire_grace_time=600,
    )
    print(f"[INFO] {job_id} scheduled(date) at {dt.isoformat()}")


def _unschedule_job(job_id: str) -> None:
    global _RSS_SCHEDULER
    if _RSS_SCHEDULER is None:
        return
    try:
        _RSS_SCHEDULER.remove_job(job_id)
    except Exception:
        pass


def _delay_job_next_run(job_id: str, reason: str) -> None:
    global _RSS_SCHEDULER
    if _RSS_SCHEDULER is None:
        return

    backoff_seconds = max(0, int(_RSS_JOB_BACKOFF_SECONDS or 0))

    if backoff_seconds <= 0:
        try:
            _RSS_JOB_BACKOFF_UNTIL.pop(job_id, None)
            _RSS_JOB_LAST_BACKOFF_LOG_TS.pop(job_id, None)
        except Exception:
            pass

        _rss_log(f"{job_id} natural_reschedule reason={reason}")
        print(f"[WARN] {job_id} natural_reschedule reason={reason}")

        try:
            if job_id == "rss_auto_fetch_tick":
                _reschedule_fetch_next(f"natural:{reason}")
            elif job_id == "rss_auto_import_tick":
                _reschedule_import_next(f"natural:{reason}")
        except Exception as e:
            print(f"[WARN] natural reschedule failed: job_id={job_id} err={e!r}")
        return

    try:
        until_ts = time.time() + backoff_seconds
        prev = float(_RSS_JOB_BACKOFF_UNTIL.get(job_id, 0.0) or 0.0)
        if until_ts < prev:
            until_ts = prev
        _RSS_JOB_BACKOFF_UNTIL[job_id] = until_ts

        _schedule_date_job(
            job_id,
            until_ts,
            _run_rss_auto_fetch_tick if job_id == "rss_auto_fetch_tick" else _run_rss_auto_import_tick,
        )
        print(f"[WARN] {job_id} delayed {backoff_seconds}s reason={reason}")
        _rss_log(f"{job_id} delayed {backoff_seconds}s reason={reason}")
    except Exception as e:
        print(f"[WARN] delay job failed: job_id={job_id} err={e!r}")

def _to_int(value: Any, default: int = 0) -> int:
    try:
        return int(value or 0)
    except Exception:
        return int(default)


def _scheduler_result_summary(job_kind: str, result: Any) -> Dict[str, Any]:
    r = result if isinstance(result, dict) else {}
    success = bool(r.get("success", False))
    status = str(r.get("status") or ("ok" if success else "error")).strip().lower()
    if not status:
        status = "ok" if success else "error"

    stats = r.get("stats") if isinstance(r.get("stats"), dict) else {}
    failed = _to_int(stats.get("failed"), 0)
    failed_rules = _to_int(stats.get("failed_rules"), 0)

    had_failures = bool(r.get("had_failures", False))
    if job_kind == "import":
        had_failures = had_failures or failed > 0 or failed_rules > 0
    else:
        had_failures = had_failures or failed > 0

    terminal_error = status in ("error", "exception", "timeout")

    return {
        "ok": bool(success) and not terminal_error,
        "status": status,
        "stats": stats,
        "had_failures": had_failures,
        "error": str(r.get("error") or r.get("message") or status or "error"),
    }


def _run_tick_in_subprocess(*, job_name: str, users_root: str, timeout_seconds: int) -> Dict[str, Any]:
    code = r"""
import sys, os, json, time
sys.path.insert(0, "/srv")

job = (sys.argv[1] if len(sys.argv) > 1 else "").strip()
users_root = (sys.argv[2] if len(sys.argv) > 2 else "").rstrip("/")
t0 = time.time()

out = {"ok": False, "job": job, "users_root": users_root, "elapsed_s": 0.0}

try:
    if not users_root:
        raise RuntimeError("missing users_root")

    if job in ("fetch", "rss_auto_fetch_tick"):
        from tools.rss.auto_fetch_scheduler import nisb_rss_auto_fetch_scheduler_tick_all_users
        r = nisb_rss_auto_fetch_scheduler_tick_all_users(users_root)
    elif job in ("import", "rss_auto_import_tick"):
        from tools.rss.auto_import_scheduler import nisb_rss_auto_import_scheduler_tick_all_users
        r = nisb_rss_auto_import_scheduler_tick_all_users(users_root)
    elif job in ("cleanup", "rss_auto_cleanup_tick"):
        from tools.rss.auto_cleanup_scheduler import nisb_rss_auto_cleanup_scheduler_tick_all_users
        r = nisb_rss_auto_cleanup_scheduler_tick_all_users(users_root)
    else:
        raise RuntimeError("invalid job")

    if not isinstance(r, dict):
        r = {"success": False, "status": "error", "error": "invalid_scheduler_result"}

    stats = r.get("stats") if isinstance(r.get("stats"), dict) else {}
    if not stats and job in ("cleanup", "rss_auto_cleanup_tick"):
        stats = {
            "checked": int(r.get("checked") or 0),
            "ran": int(r.get("ran") or 0),
            "skipped": int(r.get("skipped") or 0),
            "errors": int(r.get("errors") or 0),
        }

    try:
        failed = int(stats.get("failed") or 0)
    except Exception:
        failed = 0
    try:
        failed_rules = int(stats.get("failed_rules") or 0)
    except Exception:
        failed_rules = 0
    try:
        errors = int(stats.get("errors") or 0)
    except Exception:
        errors = 0

    had_failures = bool(r.get("had_failures", False))
    if job in ("import", "rss_auto_import_tick"):
        had_failures = had_failures or failed > 0 or failed_rules > 0
    elif job in ("cleanup", "rss_auto_cleanup_tick"):
        had_failures = had_failures or errors > 0
    else:
        had_failures = had_failures or failed > 0

    status = str(r.get("status") or ("ok" if bool(r.get("success", False)) else "error")).strip().lower()
    if not status:
        status = "ok" if bool(r.get("success", False)) else "error"

    terminal_error = status in ("error", "exception", "timeout")

    out["result"] = r
    out["stats"] = stats
    out["status"] = status
    out["had_failures"] = had_failures
    out["ok"] = bool(r.get("success", False)) and not terminal_error
    if not out["ok"]:
        out["error"] = r.get("error") or r.get("message") or status

except Exception as e:
    out["ok"] = False
    out["status"] = "exception"
    out["error"] = repr(e)

out["elapsed_s"] = time.time() - t0
print(json.dumps(out, ensure_ascii=False))
""".strip()

    job_kind = str(job_name or "").strip()
    if not job_kind:
        job_kind = "fetch"

    if job_kind == "fetch":
        job_kind = "rss_auto_fetch_tick"
    elif job_kind == "import":
        job_kind = "rss_auto_import_tick"
    elif job_kind == "cleanup":
        job_kind = "rss_auto_cleanup_tick"

    valid_jobs = {
        "rss_auto_fetch_tick",
        "rss_auto_import_tick",
        "rss_auto_cleanup_tick",
    }
    if job_kind not in valid_jobs:
        return {
            "ok": False,
            "status": "error",
            "elapsed_s": 0.0,
            "job": job_kind,
            "error": f"invalid_scheduler_job:{job_kind}",
        }

    t0 = time.time()
    try:
        p = subprocess.run(
            ["python3", "-c", code, job_kind, str(users_root or "").rstrip("/")],
            capture_output=True,
            text=True,
            timeout=max(5, int(timeout_seconds)),
            check=False,
        )
        elapsed = time.time() - t0

        if p.returncode != 0:
            return {
                "ok": False,
                "status": "error",
                "elapsed_s": elapsed,
                "rc": p.returncode,
                "job": job_kind,
                "stderr_tail": (p.stderr or "")[-2000:],
                "stdout_tail": (p.stdout or "")[-2000:],
            }

        try:
            obj = json.loads((p.stdout or "").strip().splitlines()[-1])
        except Exception:
            obj = {
                "ok": False,
                "status": "error",
                "elapsed_s": elapsed,
                "error": "invalid_subprocess_json_output",
                "stdout_tail": (p.stdout or "")[-2000:],
                "stderr_tail": (p.stderr or "")[-2000:],
            }

        ok = bool(obj.get("ok", False))
        status = str(obj.get("status") or ("ok" if ok else "error"))
        out = {
            "ok": ok,
            "status": status,
            "elapsed_s": float(obj.get("elapsed_s") or elapsed),
            "job": str(obj.get("job") or job_kind),
            "stats": obj.get("stats") or {},
            "had_failures": bool(obj.get("had_failures", False)),
            "stdout_tail": (p.stdout or "")[-2000:],
            "stderr_tail": (p.stderr or "")[-2000:],
        }

        if not ok:
            out["error"] = obj.get("error") or "unknown"

        return out

    except subprocess.TimeoutExpired:
        elapsed = time.time() - t0
        return {
            "ok": False,
            "status": "timeout",
            "elapsed_s": elapsed,
            "job": job_kind,
            "error": "subprocess_timeout",
        }


def _reschedule_fetch_next(reason: str) -> None:
    if _RSS_SCHEDULER is None:
        return
    job_id = "rss_auto_fetch_tick"

    if not _RSS_AUTO_FETCH_ENABLED:
        _unschedule_job(job_id)
        return

    now_ts = time.time()

    bo = float(_RSS_JOB_BACKOFF_UNTIL.get(job_id, 0.0) or 0.0)
    if bo > now_ts + 1.0:
        _schedule_date_job(job_id, bo, _run_rss_auto_fetch_tick)
        return

    users_root = str(_RSS_AUTO_FETCH_USERS_ROOT or USERS_ROOT).rstrip("/")
    nxt = _scan_next_fetch_due_ts(users_root, now_ts=now_ts)

    if nxt is None:
        _unschedule_job(job_id)
        print(f"[INFO] {job_id} unscheduled reason={reason} (no enabled configs)")
        return

    _schedule_date_job(job_id, float(nxt), _run_rss_auto_fetch_tick)


def _reschedule_import_next(reason: str) -> None:
    if _RSS_SCHEDULER is None:
        return
    job_id = "rss_auto_import_tick"

    if not _RSS_AUTO_IMPORT_ENABLED:
        _unschedule_job(job_id)
        return

    now_ts = time.time()

    bo = float(_RSS_JOB_BACKOFF_UNTIL.get(job_id, 0.0) or 0.0)
    if bo > now_ts + 1.0:
        _schedule_date_job(job_id, bo, _run_rss_auto_import_tick)
        return

    users_root = str(_RSS_AUTO_IMPORT_USERS_ROOT or USERS_ROOT).rstrip("/")
    nxt = _scan_next_import_due_ts(users_root, now_ts=now_ts)

    if nxt is None:
        _unschedule_job(job_id)
        print(f"[INFO] {job_id} unscheduled reason={reason} (no enabled rules)")
        return

    _schedule_date_job(job_id, float(nxt), _run_rss_auto_import_tick)


def _reschedule_async(which: str, reason: str) -> None:
    def _runner():
        try:
            if which == "fetch":
                _reschedule_fetch_next(reason)
            elif which == "import":
                _reschedule_import_next(reason)
        except Exception as e:
            print(f"[WARN] reschedule failed which={which} err={e!r}")

    threading.Thread(target=_runner, daemon=True).start()


def _run_rss_auto_fetch_tick() -> None:
    job_id = "rss_auto_fetch_tick"

    if _backoff_active(job_id):
        _reschedule_fetch_next("backoff_active")
        return

    pressure_lock_f = None
    next_action = "completed"

    try:
        pressure_lock_f = _rss_pressure_lock_acquire()
    except Exception:
        pressure_lock_f = None

    try:
        if not _RSS_GLOBAL_BUSY_LOCK.acquire(blocking=False):
            _delay_job_next_run(job_id, reason="global_busy")
            return

        lock = _JOB_LOCKS[job_id]
        if not lock.acquire(blocking=False):
            try:
                _delay_job_next_run(job_id, reason="reentry_lock")
            finally:
                _RSS_GLOBAL_BUSY_LOCK.release()
            return

        try:
            users_root = str(_RSS_AUTO_FETCH_USERS_ROOT or USERS_ROOT).rstrip("/")
            if _RSS_SCHEDULER_SUBPROCESS:
                r = _run_tick_in_subprocess(
                    job_name=job_id,
                    users_root=users_root,
                    timeout_seconds=int(_RSS_AUTO_FETCH_TIMEOUT_SECONDS or 55),
                )
                _rss_log(
                    f"{job_id} subprocess status={r.get('status')} elapsed_s={r.get('elapsed_s')} "
                    f"had_failures={r.get('had_failures')} stats={r.get('stats')} "
                    f"error={r.get('error')} stdout_tail={r.get('stdout_tail')} stderr_tail={r.get('stderr_tail')}"
                )
                if not r.get("ok"):
                    next_action = "backoff"
                    _delay_job_next_run(job_id, reason=str(r.get("status") or "error"))
                else:
                    if r.get("had_failures"):
                        print(f"[WARN] {job_id} completed_with_failures elapsed_s={float(r.get('elapsed_s') or 0):.2f}")
                    else:
                        print(f"[INFO] {job_id} ok elapsed_s={float(r.get('elapsed_s') or 0):.2f}")
            else:
                t0 = time.time()
                r = nisb_rss_auto_fetch_scheduler_tick_all_users(users_root)
                dt = time.time() - t0
                summary = _scheduler_result_summary("fetch", r)
                _rss_log(
                    f"{job_id} inline status={summary.get('status')} elapsed_s={dt} "
                    f"had_failures={summary.get('had_failures')} stats={summary.get('stats')} "
                    f"error={summary.get('error')}"
                )
                if not summary.get("ok"):
                    next_action = "backoff"
                    _delay_job_next_run(job_id, reason=str(summary.get("status") or "error"))
                else:
                    if summary.get("had_failures"):
                        print(f"[WARN] {job_id} completed_with_failures elapsed_s={dt:.2f}")
                    else:
                        print(f"[INFO] {job_id} ok elapsed_s={dt:.2f}")

        except Exception as e:
            next_action = "backoff"
            _delay_job_next_run(job_id, reason=f"exception:{e!r}")

        finally:
            try:
                lock.release()
            except Exception:
                pass
            try:
                _RSS_GLOBAL_BUSY_LOCK.release()
            except Exception:
                pass

            if next_action == "completed":
                _reschedule_fetch_next("completed")

    finally:
        try:
            _rss_pressure_lock_release(pressure_lock_f)
        except Exception:
            pass


def _run_rss_auto_import_tick() -> None:
    job_id = "rss_auto_import_tick"

    if _backoff_active(job_id):
        _reschedule_import_next("backoff_active")
        return

    pressure_lock_f = None
    next_action = "completed"

    try:
        pressure_lock_f = _rss_pressure_lock_acquire()
    except Exception:
        pressure_lock_f = None

    try:
        if not _RSS_GLOBAL_BUSY_LOCK.acquire(blocking=False):
            _delay_job_next_run(job_id, reason="global_busy")
            return

        lock = _JOB_LOCKS[job_id]
        if not lock.acquire(blocking=False):
            try:
                _delay_job_next_run(job_id, reason="reentry_lock")
            finally:
                _RSS_GLOBAL_BUSY_LOCK.release()
            return

        try:
            users_root = str(_RSS_AUTO_IMPORT_USERS_ROOT or USERS_ROOT).rstrip("/")
            if _RSS_SCHEDULER_SUBPROCESS:
                r = _run_tick_in_subprocess(
                    job_name=job_id,
                    users_root=users_root,
                    timeout_seconds=int(_RSS_AUTO_IMPORT_TIMEOUT_SECONDS or 55),
                )
                _rss_log(
                    f"{job_id} subprocess status={r.get('status')} elapsed_s={r.get('elapsed_s')} "
                    f"had_failures={r.get('had_failures')} stats={r.get('stats')} "
                    f"error={r.get('error')} stdout_tail={r.get('stdout_tail')} stderr_tail={r.get('stderr_tail')}"
                )
                if not r.get("ok"):
                    next_action = "backoff"
                    _delay_job_next_run(job_id, reason=str(r.get("status") or "error"))
                else:
                    if r.get("had_failures"):
                        print(f"[WARN] {job_id} completed_with_failures elapsed_s={float(r.get('elapsed_s') or 0):.2f}")
                    else:
                        print(f"[INFO] {job_id} ok elapsed_s={float(r.get('elapsed_s') or 0):.2f}")
            else:
                t0 = time.time()
                r = nisb_rss_auto_import_scheduler_tick_all_users(users_root)
                dt = time.time() - t0
                summary = _scheduler_result_summary("import", r)
                _rss_log(
                    f"{job_id} inline status={summary.get('status')} elapsed_s={dt} "
                    f"had_failures={summary.get('had_failures')} stats={summary.get('stats')} "
                    f"error={summary.get('error')}"
                )
                if not summary.get("ok"):
                    next_action = "backoff"
                    _delay_job_next_run(job_id, reason=str(summary.get("status") or "error"))
                else:
                    if summary.get("had_failures"):
                        print(f"[WARN] {job_id} completed_with_failures elapsed_s={dt:.2f}")
                    else:
                        print(f"[INFO] {job_id} ok elapsed_s={dt:.2f}")

        except Exception as e:
            next_action = "backoff"
            _delay_job_next_run(job_id, reason=f"exception:{e!r}")

        finally:
            try:
                lock.release()
            except Exception:
                pass
            try:
                _RSS_GLOBAL_BUSY_LOCK.release()
            except Exception:
                pass

            if next_action == "completed":
                _reschedule_import_next("completed")

    finally:
        try:
            _rss_pressure_lock_release(pressure_lock_f)
        except Exception:
            pass


def _run_rss_auto_cleanup_tick() -> None:
    job_id = "rss_auto_cleanup_tick"

    if _backoff_active(job_id):
        return

    pressure_lock_f = None

    try:
        pressure_lock_f = _rss_pressure_lock_acquire()
    except Exception:
        pressure_lock_f = None

    try:
        if not _RSS_GLOBAL_BUSY_LOCK.acquire(blocking=False):
            _delay_job_next_run(job_id, reason="global_busy")
            return

        lock = _JOB_LOCKS.setdefault(job_id, threading.Lock())
        if not lock.acquire(blocking=False):
            try:
                _delay_job_next_run(job_id, reason="reentry_lock")
            finally:
                _RSS_GLOBAL_BUSY_LOCK.release()
            return

        try:
            users_root = str(_RSS_AUTO_CLEANUP_USERS_ROOT or USERS_ROOT).rstrip("/")

            if _RSS_SCHEDULER_SUBPROCESS:
                r = _run_tick_in_subprocess(
                    job_name=job_id,
                    users_root=users_root,
                    timeout_seconds=int(_RSS_AUTO_CLEANUP_TIMEOUT_SECONDS or 600),
                )
                _rss_log(
                    f"{job_id} subprocess status={r.get('status')} elapsed_s={r.get('elapsed_s')} "
                    f"had_failures={r.get('had_failures')} stats={r.get('stats')} "
                    f"error={r.get('error')} stdout_tail={r.get('stdout_tail')} stderr_tail={r.get('stderr_tail')}"
                )

                if not r.get("ok"):
                    _delay_job_next_run(job_id, reason=str(r.get("status") or "error"))
                else:
                    if r.get("had_failures"):
                        print(f"[WARN] {job_id} completed_with_failures elapsed_s={float(r.get('elapsed_s') or 0):.2f}")
                    else:
                        print(f"[INFO] {job_id} ok elapsed_s={float(r.get('elapsed_s') or 0):.2f}")
            else:
                t0 = time.time()
                r = nisb_rss_auto_cleanup_scheduler_tick_all_users(users_root)
                dt = time.time() - t0

                if not isinstance(r, dict):
                    r = {"success": False, "errors": 1, "message": "invalid_cleanup_scheduler_result"}

                try:
                    errors = int(r.get("errors") or 0)
                except Exception:
                    errors = 0

                stats = {
                    "checked": int(r.get("checked") or 0),
                    "ran": int(r.get("ran") or 0),
                    "skipped": int(r.get("skipped") or 0),
                    "errors": errors,
                }
                ok = bool(r.get("success", False))
                had_failures = errors > 0
                status = "ok" if ok else "error"

                _rss_log(
                    f"{job_id} inline status={status} elapsed_s={dt} "
                    f"had_failures={had_failures} stats={stats} "
                    f"error={r.get('error') or r.get('message') or ''}"
                )

                if not ok:
                    _delay_job_next_run(job_id, reason=status)
                else:
                    if had_failures:
                        print(f"[WARN] {job_id} completed_with_failures elapsed_s={dt:.2f}")
                    else:
                        print(f"[INFO] {job_id} ok elapsed_s={dt:.2f}")

        except Exception as e:
            _delay_job_next_run(job_id, reason=f"exception:{e!r}")

        finally:
            try:
                lock.release()
            except Exception:
                pass
            try:
                _RSS_GLOBAL_BUSY_LOCK.release()
            except Exception:
                pass

    finally:
        try:
            _rss_pressure_lock_release(pressure_lock_f)
        except Exception:
            pass


def _rss_scheduler_listener(event):
    try:
        job_id = getattr(event, "job_id", None)
        if not job_id:
            return

        if event.code == EVENT_JOB_MAX_INSTANCES:
            _delay_job_next_run(str(job_id), reason="max_instances")
            return

        if event.code == EVENT_JOB_MISSED:
            _delay_job_next_run(str(job_id), reason="misfire_missed")
            return

        if event.code == EVENT_JOB_ERROR:
            _delay_job_next_run(str(job_id), reason="job_error")
            return
    except Exception:
        pass


def _start_rss_scheduler() -> None:
    global _RSS_SCHEDULER

    if (not _RSS_AUTO_FETCH_ENABLED) and (not _RSS_AUTO_IMPORT_ENABLED) and (not _RSS_AUTO_CLEANUP_ENABLED):
        print("[INFO] rss_scheduler disabled: auto_fetch, auto_import, and auto_cleanup are disabled")
        return

    if _RSS_SCHEDULER is not None:
        return

    if not _try_acquire_scheduler_lock():
        print("[INFO] rss_scheduler not started: lock not acquired (another worker owns it)")
        return

    sch = BackgroundScheduler(timezone="UTC")
    sch.add_listener(
        _rss_scheduler_listener,
        EVENT_JOB_ERROR | EVENT_JOB_MISSED | EVENT_JOB_MAX_INSTANCES,
    )

    sch.start()
    _RSS_SCHEDULER = sch

    try:
        _reschedule_fetch_next("startup")
    except Exception as e:
        print(f"[WARN] reschedule fetch on startup failed: {e!r}")
    try:
        _reschedule_import_next("startup")
    except Exception as e:
        print(f"[WARN] reschedule import on startup failed: {e!r}")
    if _RSS_AUTO_CLEANUP_ENABLED:
        try:
            sch.add_job(
                _run_rss_auto_cleanup_tick,
                "interval",
                minutes=int(_RSS_AUTO_CLEANUP_INTERVAL_MINUTES or 30),
                id="rss_auto_cleanup_tick",
                replace_existing=True,
                coalesce=True,
                max_instances=1,
                next_run_time=datetime.fromtimestamp(time.time() + 90.0, tz=timezone.utc),
            )
            print(
                f"[INFO] rss_auto_cleanup_tick scheduled interval_minutes="
                f"{int(_RSS_AUTO_CLEANUP_INTERVAL_MINUTES or 30)}"
            )
        except Exception as e:
            print(f"[WARN] schedule cleanup on startup failed: {e!r}")


def _stop_rss_scheduler() -> None:
    global _RSS_SCHEDULER
    try:
        if _RSS_SCHEDULER is not None:
            _RSS_SCHEDULER.shutdown(wait=False)
            print("[INFO] rss_scheduler stopped")
    except Exception as e:
        print(f"[WARN] rss_scheduler stop failed: {e!r}")
    finally:
        _RSS_SCHEDULER = None
        _release_scheduler_lock()


@app.on_event("startup")
async def _on_startup():
    delay = max(0, int(_RSS_SCHEDULER_START_DELAY_SECONDS or 0))

    def _delayed_start():
        try:
            if delay > 0:
                time.sleep(delay)
            _start_rss_scheduler()
        except Exception as e:
            print(f"[WARN] rss_scheduler delayed start failed: {e!r}")

    threading.Thread(target=_delayed_start, daemon=True).start()


@app.on_event("shutdown")
async def _on_shutdown():
    _stop_rss_scheduler()


class ToolCallRequest(BaseModel):
    tool: str
    arguments: Dict[str, Any] = {}


@app.get("/")
async def root():
    return {
        "service": "NISB HTTP API Gateway",
        "version": "1.1",
        "data_root": DATA_ROOT,
        "endpoints": {
            "mcp_call_primary": "/api/mcp/call",
            "mcp_call_compat": "/mcp/call",
            "mcp_stream_primary": "/api/mcp/stream",
            "mcp_stream_compat": "/mcp/stream",
            "tools_list": "/tools/list",
            "feed_notifications_sse": "/api/feed/notifications/stream",
        },
        "rss_scheduler": {
            "mode": "date_trigger_next_run_at",
            "subprocess": _RSS_SCHEDULER_SUBPROCESS,
            "start_delay_seconds": _RSS_SCHEDULER_START_DELAY_SECONDS,
            "backoff_seconds_fixed": _RSS_JOB_BACKOFF_SECONDS,
            "lock_path": _RSS_SCHEDULER_LOCK_PATH,
            "auto_fetch_enabled": _RSS_AUTO_FETCH_ENABLED,
            "auto_import_enabled": _RSS_AUTO_IMPORT_ENABLED,
        },
        "rss_pressure_lock": {
            "lock_path": _RSS_PRESSURE_LOCK_PATH,
            "pressure_concurrency": int(NISB_RSS_PRESSURE_CONCURRENCY),
        },
        "chat_pseudo_stream": {
            "enabled": NISB_CHAT_PSEUDO_STREAM_ENABLED,
            "delay_ms": NISB_CHAT_PSEUDO_STREAM_DELAY_MS,
            "meta_delay_ms": NISB_CHAT_PSEUDO_STREAM_META_DELAY_MS,
        },
    }


@app.api_route("/api/feed/avatars/{user_id}", methods=["GET", "HEAD"])
@app.api_route("/feed/avatars/{user_id}", methods=["GET", "HEAD"])
async def feed_avatar(user_id: str):
    base = f"{DATA_ROOT}/shared/feed/avatars"
    for ext, mt in (("png", "image/png"), ("jpg", "image/jpeg"), ("webp", "image/webp")):
        p = os.path.join(base, f"{user_id}.{ext}")
        if os.path.exists(p):
            return FileResponse(p, media_type=mt)
    raise HTTPException(status_code=404, detail="avatar not found")


@app.api_route("/api/feed/assets/{asset_path:path}", methods=["GET", "HEAD"])
@app.api_route("/feed/assets/{asset_path:path}", methods=["GET", "HEAD"])
async def feed_assets(asset_path: str):
    base = f"{DATA_ROOT}/shared/feed/assets"

    rel = str(asset_path or "").lstrip("/").replace("\\", "/")
    norm = os.path.normpath(rel).replace("\\", "/")
    if norm.startswith("../") or norm == "..":
        raise HTTPException(status_code=400, detail="invalid asset path")

    p = os.path.join(base, norm)
    if not os.path.exists(p) or not os.path.isfile(p):
        raise HTTPException(status_code=404, detail="asset not found")

    mt, _ = mimetypes.guess_type(p)
    return FileResponse(p, media_type=mt or "application/octet-stream")


def _jsonable(obj: Any) -> Any:
    try:
        json.dumps(obj, ensure_ascii=False)
        return obj
    except Exception:
        return str(obj)


def _sse_pack(event: str, data_obj: Any) -> bytes:
    data_str = json.dumps(_jsonable(data_obj), ensure_ascii=False)
    return (f"event: {event}\n" f"data: {data_str}\n\n").encode("utf-8")


def _first_text(*values: Any) -> str:
    for value in values:
        text = str(value or "").strip()
        if text:
            return text
    return ""


def _clip_text(value: Any, limit: int = 4000) -> str:
    text = str(value or "")
    if len(text) <= limit:
        return text
    return text[:limit] + "\n...[truncated]"


def _safe_list(value: Any) -> List[Any]:
    return value if isinstance(value, list) else []


def _safe_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _looks_like_formal_payload(obj: Any) -> bool:
    if not isinstance(obj, dict):
        return False
    required = {"status", "response", "tool_calls", "tool_results"}
    return required.issubset(set(obj.keys()))


def _tool_call_record(tool_name: str, arguments: Dict[str, Any]) -> List[Dict[str, Any]]:
    return [
        {
            "id": "tool_call_1",
            "name": str(tool_name or "").strip() or "unknown_tool",
            "arguments": arguments if isinstance(arguments, dict) else {},
            "arguments_preview": _clip_text(json.dumps(_jsonable(arguments), ensure_ascii=False), 2000),
            "status": "done",
            "reason": "",
            "note": "",
        }
    ]


def _tool_result_record(tool_name: str, result: Any, *, status: str = "done") -> List[Dict[str, Any]]:
    preview = _clip_text(json.dumps(_jsonable(result), ensure_ascii=False), 4000)
    return [
        {
            "id": "tool_call_1",
            "name": str(tool_name or "").strip() or "unknown_tool",
            "result": _jsonable(result),
            "preview": preview,
            "status": str(status or "done"),
        }
    ]


def _is_chat_call_tool(tool_name: str) -> bool:
    return str(tool_name or "").strip() in _CHAT_STREAM_TOOLS


def _build_formal_call_result(tool_name: str, arguments: Dict[str, Any], result: Any) -> Dict[str, Any]:
    request_id = _read_std_request_id(arguments)
    conv_id = _read_std_conv_id(arguments)
    rag_mode = _read_std_rag_mode(arguments)
    mcp_overrides = _read_std_mcp_overrides(arguments)

    if tool_name in _CHAT_STREAM_TOOLS:
        out = _normalize_chat_call_result(
            result,
            request_id=request_id,
            conv_id=conv_id,
        )
        if not _read_string(out, "response"):
            out["response"] = _read_string(out, "message") or "已完成请求"
        return out

    if _looks_like_formal_payload(result):
        out = dict(result or {})
        if not _read_string(out, "request_id"):
            out["request_id"] = request_id
        if not _read_string(out, "conv_id"):
            out["conv_id"] = conv_id
        if not _read_string(out, "rag_mode"):
            out["rag_mode"] = rag_mode
        if not isinstance(out.get("mcp_overrides"), dict):
            out["mcp_overrides"] = mcp_overrides
        if not _read_string(out, "mode_used"):
            out["mode_used"] = _read_string(out, "rag_mode") or rag_mode or "off"
        if not isinstance(out.get("rss_evidence"), list):
            out["rss_evidence"] = []
        if not isinstance(out.get("market_evidence"), list):
            out["market_evidence"] = []
        if "evidence_query" not in out:
            out["evidence_query"] = ""
        if not isinstance(out.get("evidence_tools"), list):
            out["evidence_tools"] = [tool_name]
        if not isinstance(out.get("evidence_result"), dict):
            out["evidence_result"] = {}
        if "qa_id" not in out:
            out["qa_id"] = ""
        if "group_id" not in out:
            out["group_id"] = ""
        if not isinstance(out.get("citations"), list):
            out["citations"] = []
        if not isinstance(out.get("tool_calls"), list):
            out["tool_calls"] = _tool_call_record(tool_name, arguments)
        if not isinstance(out.get("tool_results"), list):
            out["tool_results"] = _tool_result_record(tool_name, result)
        if not _read_string(out, "response"):
            out["response"] = _read_string(out, "message") or f"已执行工具 {tool_name}"
        if not _read_string(out, "status"):
            out["status"] = "success"
        if "message" not in out:
            out["message"] = ""
        return out

    raw_dict = result if isinstance(result, dict) else {}
    raw_status = _first_text(raw_dict.get("status")) if raw_dict else ""
    if not raw_status:
        if isinstance(raw_dict, dict) and raw_dict.get("success") is False:
            raw_status = "error"
        else:
            raw_status = "success"

    raw_message = _first_text(raw_dict.get("message")) if raw_dict else ""
    raw_response = _first_text(
        raw_dict.get("response") if raw_dict else "",
        raw_dict.get("content") if raw_dict else "",
        raw_message,
    )
    if not raw_response and raw_status == "success":
        raw_response = f"已执行工具 {tool_name}"
    if not raw_response and raw_status == "error":
        raw_response = raw_message or f"工具执行失败: {tool_name}"

    evidence_result = raw_dict if isinstance(raw_dict, dict) else {"value": _jsonable(result)}

    return {
        "request_id": request_id,
        "conv_id": conv_id,
        "rag_mode": rag_mode or "",
        "mcp_overrides": mcp_overrides,
        "mode_used": rag_mode or "off",
        "rss_evidence": [],
        "market_evidence": [],
        "evidence_query": "",
        "evidence_tools": [tool_name],
        "evidence_result": evidence_result,
        "qa_id": "",
        "group_id": "",
        "citations": _safe_list(raw_dict.get("citations")) if isinstance(raw_dict, dict) else [],
        "response": raw_response,
        "status": raw_status,
        "message": raw_message,
        "tool_calls": _tool_call_record(tool_name, arguments),
        "tool_results": _tool_result_record(tool_name, result, status="done" if raw_status != "error" else "error"),
    }


def _build_formal_chat_error(tool_name: str, arguments: Dict[str, Any], e: Exception) -> Dict[str, Any]:
    request_id = _read_std_request_id(arguments)
    conv_id = _read_std_conv_id(arguments)
    rag_mode = _read_std_rag_mode(arguments)
    mcp_overrides = _read_std_mcp_overrides(arguments)
    return {
        "request_id": request_id,
        "conv_id": conv_id,
        "rag_mode": rag_mode or "",
        "mcp_overrides": mcp_overrides,
        "mode_used": rag_mode or "off",
        "rss_evidence": [],
        "market_evidence": [],
        "evidence_query": "",
        "evidence_tools": [tool_name],
        "evidence_result": {"error": repr(e)},
        "qa_id": "",
        "group_id": "",
        "citations": [],
        "response": f"工具执行失败: {tool_name}",
        "status": "error",
        "message": f"工具执行失败: {str(e)}",
        "tool_calls": _tool_call_record(tool_name, arguments),
        "tool_results": _tool_result_record(tool_name, {"error": repr(e)}, status="error"),
    }


def _build_legacy_tool_error(tool_name: str, e: Exception) -> Dict[str, Any]:
    return {
        "success": False,
        "status": "error",
        "message": f"工具执行失败: {str(e)}",
        "tool": str(tool_name or "").strip(),
    }


async def _run_tool_with_guards(tool_name: str, tool_func, arguments: Dict[str, Any]) -> Any:
    long_running = tool_name in {
        "nisb_library_translate_span",
        "nisb_util_translate",
        "nisb_util_translate_chunks",
    }

    tool_kwargs = _build_tool_kwargs(tool_func, arguments)

    def _clear_rss_caches_best_effort() -> None:
        try:
            uid = str(arguments.get("user_id") or arguments.get("_user_id") or "").strip()
            nisb_rss_cache_clear({"uid": uid or None, "gc_collect": True})
        except Exception:
            pass

    pressure_lock_f = None
    try:
        if tool_name in _RSS_PRESSURE_TOOLS:
            pressure_lock_f = await _rss_pressure_lock_acquire_async()

        if tool_name in _RSS_PRESSURE_TOOLS:
            async with _RSS_PRESSURE_GUARD:
                if tool_name in _RSS_HEAVY_RSS_JOBS:
                    _clear_rss_caches_best_effort()
                result = await run_in_threadpool(tool_func, arguments, **tool_kwargs)
                if tool_name in _RSS_HEAVY_RSS_JOBS:
                    _clear_rss_caches_best_effort()

        elif tool_name in _RSS_SEARCH_TOOLS:
            async with _RSS_SEARCH_GUARD:
                result = await run_in_threadpool(tool_func, arguments, **tool_kwargs)

        elif long_running:
            async with _LLM_GUARD:
                result = await run_in_threadpool(tool_func, arguments, **tool_kwargs)

        else:
            result = await run_in_threadpool(tool_func, arguments, **tool_kwargs)

        if tool_name in {"nisb_rss_auto_fetch_config_set", "nisb_rss_auto_fetch_config_delete"}:
            _reschedule_async("fetch", f"tool:{tool_name}")
        if tool_name in {"nisb_rss_auto_import_rules_set"}:
            _reschedule_async("import", f"tool:{tool_name}")
        if tool_name in {"nisb_rss_auto_import_run_rule", "nisb_rss_auto_import_run_due"}:
            _reschedule_async("import", f"tool:{tool_name}")

        return result
    finally:
        try:
            if pressure_lock_f is not None:
                await _rss_pressure_lock_release_async(pressure_lock_f)
        except Exception:
            pass


async def _handle_tool_call(request: ToolCallRequest, authorization: Optional[str]) -> Any:
    tool_name = request.tool
    arguments = dict(request.arguments or {})

    if tool_name not in TOOLS:
        raise HTTPException(status_code=404, detail=f"工具不存在: {tool_name}")

    arguments = _auth_and_inject(
        tool_name,
        arguments,
        authorization,
        users_root=USERS_ROOT,
        whitelist_tools=WHITELIST_TOOLS,
    )

    tool_func = TOOLS[tool_name]

    try:
        result = await _run_tool_with_guards(tool_name, tool_func, arguments)

        if _is_chat_call_tool(tool_name):
            return _build_formal_call_result(tool_name, arguments, result)

        return result

    except HTTPException:
        raise
    except Exception as e:
        print(f"[ERROR] 工具执行失败: {tool_name}")
        print(traceback.format_exc())

        if _is_chat_call_tool(tool_name):
            return _build_formal_chat_error(tool_name, arguments, e)

        return _build_legacy_tool_error(tool_name, e)


@app.post("/mcp/call")
async def mcp_call(request: ToolCallRequest, authorization: Optional[str] = Header(None)):
    return await _handle_tool_call(request, authorization)


@app.post("/api/mcp/call")
async def api_mcp_call(request: ToolCallRequest, authorization: Optional[str] = Header(None)):
    return await _handle_tool_call(request, authorization)


@app.get("/tools/list")
async def tools_list():
    tools = []
    for name, func in TOOLS.items():
        tools.append({"name": name, "description": func.__doc__ or ""})
    return {"status": "success", "tools": tools, "total": len(tools)}


@app.post("/mcp/stream")
@app.post("/api/mcp/stream")
async def mcp_stream(
    request: Request,
    payload: Dict[str, Any] = Body(...),
    authorization: Optional[str] = Header(default=None),
):
    tool = str((payload or {}).get("tool") or "").strip()
    arguments = (payload or {}).get("arguments") or {}
    if not isinstance(arguments, dict):
        arguments = {}

    if tool not in _CHAT_STREAM_TOOLS:
        raise HTTPException(status_code=400, detail=f"stream not supported for tool={tool}")

    if tool not in TOOLS:
        raise HTTPException(status_code=404, detail=f"{tool} not found")

    arguments = _auth_and_inject(
        tool,
        dict(arguments),
        authorization,
        users_root=USERS_ROOT,
        whitelist_tools=WHITELIST_TOOLS,
    )
    request_id = _read_std_request_id(arguments)
    initial_conv_id = _read_std_conv_id(arguments)
    initial_rag_mode = _read_std_rag_mode(arguments)
    initial_mcp_overrides = _read_std_mcp_overrides(arguments)

    q: "queue.Queue[Optional[Dict[str, Any]]]" = queue.Queue()
    abort_event = threading.Event()

    def _producer():
        local_conv_id = initial_conv_id
        try:
            from tools.chat.stream_runtime import stream_chat_tool

            for item in stream_chat_tool(tool, arguments, abort_event=abort_event):
                if not isinstance(item, dict):
                    continue

                raw_event_name = str(item.get("event") or "delta")
                raw_data = item.get("data") or {}
                if not isinstance(raw_data, dict):
                    raw_data = {"response": str(raw_data or "")}

                event_name = _normalize_chat_event_name(raw_event_name)
                if event_name not in _CHAT_ALLOWED_EVENTS:
                    event_name = "meta"

                data = _normalize_chat_payload(
                    raw_data,
                    request_id=request_id,
                    conv_id=local_conv_id or initial_conv_id,
                    event_name=event_name,
                )

                next_conv_id = str(data.get("conv_id") or local_conv_id or "").strip()
                if next_conv_id:
                    data["conv_id"] = next_conv_id
                    local_conv_id = next_conv_id

                q.put({
                    "event": event_name,
                    "data": data,
                })
        except Exception as e:
            q.put({
                "event": "error",
                "data": _normalize_chat_payload(
                    {
                        "message": f"stream failed: {e!r}",
                        "status": "error",
                        "response": f"stream failed: {e!r}",
                    },
                    request_id=request_id,
                    conv_id=local_conv_id or initial_conv_id or "",
                    event_name="error",
                ),
            })
        finally:
            q.put(None)

    threading.Thread(target=_producer, daemon=True).start()

    async def _event_iter():
        nonlocal initial_conv_id
        idle_deadline = time.time() + 90.0

        initial_meta = {
            "request_id": request_id,
            "conv_id": initial_conv_id,
            "rag_mode": initial_rag_mode,
            "mcp_overrides": initial_mcp_overrides,
            "mode_used": "",
            "rss_evidence": [],
            "market_evidence": [],
            "evidence_query": "",
            "evidence_tools": [],
            "evidence_result": {},
            "qa_id": "",
            "group_id": "",
            "citations": [],
            "response": "stream_started",
            "status": "running",
            "message": "",
            "tool_calls": [],
            "tool_results": [],
        }
        yield _sse_pack("meta", initial_meta)
        await _maybe_pseudo_stream_delay(
            "meta",
            initial_meta,
            enabled=NISB_CHAT_PSEUDO_STREAM_ENABLED,
            delta_delay_ms=NISB_CHAT_PSEUDO_STREAM_DELAY_MS,
            meta_delay_ms=NISB_CHAT_PSEUDO_STREAM_META_DELAY_MS,
        )

        final_seen = False
        final_data: Dict[str, Any] = {}
        terminal_event = ""

        while True:
            try:
                if await request.is_disconnected():
                    abort_event.set()
                    break

                item = await anyio.to_thread.run_sync(lambda: q.get(timeout=1.0))
                idle_deadline = time.time() + 90.0
            except Exception:
                if await request.is_disconnected():
                    abort_event.set()
                    break

                if time.time() >= idle_deadline:
                    abort_event.set()
                    timeout_error = {
                        "request_id": request_id,
                        "conv_id": initial_conv_id,
                        "rag_mode": initial_rag_mode,
                        "mcp_overrides": initial_mcp_overrides,
                        "mode_used": "",
                        "rss_evidence": [],
                        "market_evidence": [],
                        "evidence_query": "",
                        "evidence_tools": [],
                        "evidence_result": {},
                        "qa_id": "",
                        "group_id": "",
                        "citations": [],
                        "response": "stream idle timeout",
                        "status": "error",
                        "message": "stream idle timeout",
                        "tool_calls": [],
                        "tool_results": [],
                    }
                    yield _sse_pack("error", timeout_error)
                    final_seen = True
                    final_data = timeout_error
                    terminal_event = "error"
                    break

                yield b": ping\n\n"
                continue

            if item is None:
                break

            ev = _normalize_chat_event_name(str((item or {}).get("event") or "delta"))
            if ev not in _CHAT_ALLOWED_EVENTS:
                ev = "meta"

            data = _normalize_chat_payload(
                (item or {}).get("data") or {},
                request_id=request_id,
                conv_id=initial_conv_id,
                event_name=ev,
            )

            next_conv_id = str(data.get("conv_id") or initial_conv_id or "").strip()
            if next_conv_id:
                data["conv_id"] = next_conv_id
                initial_conv_id = next_conv_id

            yield _sse_pack(ev, data)
            await _maybe_pseudo_stream_delay(
                ev,
                data,
                enabled=NISB_CHAT_PSEUDO_STREAM_ENABLED,
                delta_delay_ms=NISB_CHAT_PSEUDO_STREAM_DELAY_MS,
                meta_delay_ms=NISB_CHAT_PSEUDO_STREAM_META_DELAY_MS,
            )

            if ev in {"final", "error"}:
                final_seen = True
                final_data = data
                terminal_event = ev
                break

        if not await request.is_disconnected():
            if final_seen:
                done_payload = _build_done_payload(
                    request_id=str(final_data.get("request_id") or request_id),
                    conv_id=str(final_data.get("conv_id") or initial_conv_id or ""),
                    rag_mode=str(final_data.get("rag_mode") or initial_rag_mode or ""),
                    mcp_overrides=_read_object(final_data, "mcp_overrides"),
                    mode_used=str(final_data.get("mode_used") or ""),
                    response=str(final_data.get("response") or ""),
                    status="error" if terminal_event == "error" else str(final_data.get("status") or "success"),
                    message="done",
                    citations=_read_array(final_data, "citations"),
                    rss_evidence=_read_array(final_data, "rss_evidence"),
                    market_evidence=_read_array(final_data, "market_evidence"),
                    evidence_query=_read_string(final_data, "evidence_query"),
                    evidence_tools=_read_array(final_data, "evidence_tools"),
                    evidence_result=_read_object(final_data, "evidence_result"),
                    qa_id=_read_string(final_data, "qa_id"),
                    group_id=_read_string(final_data, "group_id"),
                    tool_calls=_read_array(final_data, "tool_calls"),
                    tool_results=_read_array(final_data, "tool_results"),
                )
            else:
                done_payload = _build_done_payload(
                    request_id=request_id,
                    conv_id=initial_conv_id,
                    rag_mode=initial_rag_mode,
                    mcp_overrides=initial_mcp_overrides,
                    response="done",
                    status="success",
                    message="done",
                )

            yield _sse_pack("done", done_payload)

    return StreamingResponse(
        _event_iter(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


try:
    from api.feed_notifications_sse import router as feed_notifications_sse_router
    app.include_router(feed_notifications_sse_router)
except Exception as e:
    print(f"[WARN] feed_notifications_sse router not loaded: {e!r}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8006)

