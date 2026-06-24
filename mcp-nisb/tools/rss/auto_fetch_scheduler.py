from __future__ import annotations

import os
import time
from contextlib import contextmanager
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, Optional, Tuple, List

from core.storage import load_json, save_json
from .fetch_due import nisb_rss_fetch_due


def _utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _get_basepath(args: Dict[str, Any]) -> str:
    bp = (
        args.get("base_path")
        or args.get("_base_path")
        or args.get("basepath")
    )
    bp = str(bp or "").strip()
    if bp:
        return bp
    return "/data/users/unknown"


def _conf_path(basepath: str) -> str:
    return os.path.join(basepath, "rss", "auto_fetch_config.json")


def _conf_lock_path(basepath: str) -> str:
    return os.path.join(basepath, "rss", ".auto_fetch_config.lock")


@contextmanager
def _conf_lock(basepath: str):
    os.makedirs(os.path.dirname(_conf_lock_path(basepath)), exist_ok=True)
    lockf = None
    try:
        lockf = open(_conf_lock_path(basepath), "a+", encoding="utf-8")
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


def _events_path(basepath: str) -> str:
    return os.path.join(basepath, "logs", "rss_auto_fetch_events.jsonl")


def _append_event(basepath: str, row: Dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(_events_path(basepath)), exist_ok=True)
    path = _events_path(basepath)
    line = dict(row or {})
    line["ts"] = _utc_iso()
    try:
        import json
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(line, ensure_ascii=False) + "\n")
    except Exception:
        pass


def _normalize_times_utc(times: List[str]) -> List[str]:
    out: List[str] = []
    seen = set()
    for t in times or []:
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


def _default_conf() -> Dict[str, Any]:
    return {
        "version": 2,
        "enabled": False,
        "times_utc": [],
        "interval_minutes": 1440,
        "limit_entries": 50,
        "last_run_at": "",
        "next_run_at": "",
        "updated_at": "",
    }


def _load_conf(basepath: str) -> Dict[str, Any]:
    path = _conf_path(basepath)
    if not os.path.exists(path):
        return _default_conf()

    doc = load_json(path)
    if not isinstance(doc, dict):
        return _default_conf()

    out = _default_conf()
    out.update(doc)

    out["enabled"] = bool(out.get("enabled", False))

    times = out.get("times_utc")
    if isinstance(times, str):
        times = [x.strip() for x in times.split(",") if str(x or "").strip()]
    if not isinstance(times, list):
        times = []
    out["times_utc"] = _normalize_times_utc([str(x or "").strip() for x in times])

    try:
        out["interval_minutes"] = int(out.get("interval_minutes") or 0)
    except Exception:
        out["interval_minutes"] = 1440
    out["interval_minutes"] = max(0, min(43200, out["interval_minutes"]))

    try:
        out["limit_entries"] = int(out.get("limit_entries") or 50)
    except Exception:
        out["limit_entries"] = 50
    out["limit_entries"] = max(1, min(200, out["limit_entries"]))

    out["last_run_at"] = str(out.get("last_run_at") or "").strip()
    out["next_run_at"] = str(out.get("next_run_at") or "").strip()
    out["updated_at"] = str(out.get("updated_at") or "").strip()

    out["version"] = 2
    return out


def _save_conf(basepath: str, doc: Dict[str, Any]) -> bool:
    path = _conf_path(basepath)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    d = dict(doc or {})
    d["version"] = 2
    d["updated_at"] = _utc_iso()
    return save_json(path, d)


def _parse_iso_ts(s: str) -> Optional[float]:
    ss = str(s or "").strip()
    if not ss:
        return None
    try:
        dt = datetime.fromisoformat(ss.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.timestamp()
    except Exception:
        return None


def _calc_next_run_at_from_times(times_utc: List[str], *, now_ts: Optional[float] = None) -> str:
    times_utc = _normalize_times_utc(list(times_utc or []))
    if not times_utc:
        return ""
    if now_ts is None:
        now_ts = time.time()

    now = datetime.fromtimestamp(now_ts, tz=timezone.utc)
    today = now.date()

    cands: List[datetime] = []
    for t in times_utc:
        hh, mm = t.split(":")
        h = int(hh)
        m = int(mm)
        cands.append(datetime(today.year, today.month, today.day, h, m, tzinfo=timezone.utc))

    for dt in sorted(cands):
        if dt.timestamp() > now_ts:
            return dt.isoformat()

    tomorrow = now + timedelta(days=1)
    hh, mm = times_utc[0].split(":")
    dt0 = datetime(tomorrow.year, tomorrow.month, tomorrow.day, int(hh), int(mm), tzinfo=timezone.utc)
    return dt0.isoformat()


def _calc_next_run_at_interval(interval_minutes: int, *, now_ts: Optional[float] = None) -> str:
    if interval_minutes <= 0:
        return ""
    if now_ts is None:
        now_ts = time.time()
    nxt = now_ts + (interval_minutes * 60)
    return datetime.fromtimestamp(nxt, tz=timezone.utc).isoformat()


def _due(conf: Dict[str, Any], *, now_ts: float) -> bool:
    if not bool(conf.get("enabled", False)):
        return False

    times_utc = conf.get("times_utc") or []
    if isinstance(times_utc, list) and len(times_utc) > 0:
        nxt = _parse_iso_ts(str(conf.get("next_run_at") or ""))
        if nxt is None:
            return True
        return now_ts >= nxt

    interval_minutes = int(conf.get("interval_minutes") or 0)
    if interval_minutes <= 0:
        return False
    nxt = _parse_iso_ts(str(conf.get("next_run_at") or ""))
    if nxt is None:
        return True
    return now_ts >= nxt


def _peek_conf_for_tick(basepath: str) -> Optional[Tuple[bool, List[str], int, Optional[float]]]:
    path = _conf_path(basepath)
    if not os.path.exists(path):
        return None

    try:
        import json
        with open(path, "r", encoding="utf-8") as f:
            doc = json.load(f)
    except Exception:
        return None

    if not isinstance(doc, dict):
        return None

    enabled = bool(doc.get("enabled", False))

    times = doc.get("times_utc") or []
    if isinstance(times, str):
        times = [x.strip() for x in times.split(",") if str(x or "").strip()]
    if not isinstance(times, list):
        times = []
    times_utc = _normalize_times_utc([str(x or "").strip() for x in times])

    try:
        limit_entries = int(doc.get("limit_entries") or 50)
    except Exception:
        limit_entries = 50
    limit_entries = max(1, min(200, limit_entries))

    next_run_ts = _parse_iso_ts(str(doc.get("next_run_at") or "").strip())
    return (enabled, times_utc, limit_entries, next_run_ts)


def _run_fetch_due_for_basepath(basepath: str, *, force: bool = False, scheduler_run: bool = False) -> Dict[str, Any]:
    with _conf_lock(basepath):
        now_ts = time.time()
        conf = _load_conf(basepath)

        if (not force) and (not _due(conf, now_ts=now_ts)):
            return {"success": True, "status": "skipped", "reason": "not_due_or_disabled", "config": conf}

        times_utc = conf.get("times_utc") or []
        if not isinstance(times_utc, list):
            times_utc = []
        times_utc = _normalize_times_utc([str(x or "").strip() for x in times_utc])

        interval_minutes = int(conf.get("interval_minutes") or 0)
        limit_entries = int(conf.get("limit_entries") or 50)

        r: Dict[str, Any]
        ok = False
        run_status = "error"
        had_failures = False
        error_text = ""

        try:
            r = nisb_rss_fetch_due({
                "base_path": basepath,
                "default_interval_minutes": interval_minutes,
                "limit_entries": limit_entries,
                "now_ts": now_ts,
                "force": bool(force),
            })
            if not isinstance(r, dict):
                r = {"success": False, "status": "error", "error": "invalid_fetch_due_result"}

            ok = bool((r or {}).get("success", False))
            run_status = str((r or {}).get("status") or ("ok" if ok else "error")).strip().lower()
            had_failures = bool((r or {}).get("had_failures", False))
            error_text = str((r or {}).get("error") or (r or {}).get("message") or "").strip()
        except Exception as e:
            error_text = str(e)
            r = {"success": False, "status": "exception", "error": error_text}
            ok = False
            run_status = "exception"
            had_failures = True

        if scheduler_run:
            conf["last_run_at"] = _utc_iso()

            if bool(conf.get("enabled", False)):
                if times_utc:
                    conf["times_utc"] = times_utc
                    conf["next_run_at"] = _calc_next_run_at_from_times(times_utc, now_ts=now_ts)
                elif interval_minutes > 0:
                    conf["next_run_at"] = _calc_next_run_at_interval(interval_minutes, now_ts=now_ts)
                else:
                    conf["next_run_at"] = ""
            else:
                conf["next_run_at"] = ""

            _save_conf(basepath, conf)

        _append_event(basepath, {
            "type": "rss_auto_fetch.run",
            "status": run_status if ok else "error",
            "run_status": run_status,
            "error": error_text,
            "times_utc": times_utc,
            "interval_minutes": interval_minutes,
            "limit_entries": limit_entries,
            "stats": (r or {}).get("stats"),
            "force": bool(force),
            "scheduler_run": bool(scheduler_run),
        })

        if not ok:
            return {
                "success": True if scheduler_run else False,
                "status": "error",
                "had_failures": True,
                "forced": bool(force),
                "scheduler_run": bool(scheduler_run),
                "error": error_text or "fetch_due_failed",
                "result": r,
                "config": conf,
            }

        if run_status == "partial_failure" or had_failures:
            return {
                "success": True,
                "status": "partial_failure",
                "had_failures": True,
                "forced": bool(force),
                "scheduler_run": bool(scheduler_run),
                "result": r,
                "config": conf,
            }

        return {
            "success": True,
            "status": "ran" if run_status == "ok" else "skipped",
            "had_failures": False,
            "forced": bool(force),
            "scheduler_run": bool(scheduler_run),
            "result": r,
            "config": conf,
        }

# ============================================================
# MCP tools
# ============================================================

def nisb_rss_auto_fetch_config_get(args: Dict[str, Any]) -> Dict[str, Any]:
    basepath = _get_basepath(args)
    with _conf_lock(basepath):
        conf = _load_conf(basepath)
        if bool(conf.get("enabled")) and conf.get("times_utc") and not str(conf.get("next_run_at") or "").strip():
            conf["next_run_at"] = _calc_next_run_at_from_times(list(conf.get("times_utc") or []))
            _save_conf(basepath, conf)
    return {"success": True, "config": conf}


def nisb_rss_auto_fetch_config_set(args: Dict[str, Any]) -> Dict[str, Any]:
    basepath = _get_basepath(args)

    with _conf_lock(basepath):
        conf = _load_conf(basepath)
        prev_enabled = bool(conf.get("enabled", False))

        if "enabled" in args:
            conf["enabled"] = bool(args.get("enabled"))

        if "times_utc" in args:
            v = args.get("times_utc")
            if isinstance(v, str):
                times = [x.strip() for x in v.split(",") if str(x or "").strip()]
            elif isinstance(v, list):
                times = [str(x or "").strip() for x in v]
            else:
                times = []
            conf["times_utc"] = _normalize_times_utc(times)

        if "interval_minutes" in args:
            try:
                conf["interval_minutes"] = int(args.get("interval_minutes") or 0)
            except Exception:
                conf["interval_minutes"] = int(conf.get("interval_minutes") or 1440)

        if "limit_entries" in args:
            try:
                conf["limit_entries"] = int(args.get("limit_entries") or 50)
            except Exception:
                conf["limit_entries"] = int(conf.get("limit_entries") or 50)

        conf["interval_minutes"] = max(0, min(43200, int(conf.get("interval_minutes") or 0)))
        conf["limit_entries"] = max(1, min(200, int(conf.get("limit_entries") or 50)))

        if bool(conf.get("enabled")):
            if conf.get("times_utc"):
                conf["next_run_at"] = _calc_next_run_at_from_times(list(conf.get("times_utc") or []))
            else:
                if (not prev_enabled) and (not str(conf.get("last_run_at") or "").strip()):
                    conf["next_run_at"] = ""
                else:
                    if not str(conf.get("next_run_at") or "").strip():
                        conf["next_run_at"] = _calc_next_run_at_interval(int(conf["interval_minutes"]))
        else:
            conf["next_run_at"] = ""

        _save_conf(basepath, conf)

    _append_event(basepath, {
        "type": "rss_auto_fetch.config_set",
        "enabled": conf.get("enabled"),
        "times_utc": conf.get("times_utc"),
        "interval_minutes": conf.get("interval_minutes"),
        "limit_entries": conf.get("limit_entries"),
    })

    return {"success": True, "config": conf}


def nisb_rss_auto_fetch_run_now(args: Dict[str, Any]) -> Dict[str, Any]:
    basepath = _get_basepath(args)
    return _run_fetch_due_for_basepath(basepath, force=True, scheduler_run=False)


def nisb_rss_auto_fetch_config_delete(args: Dict[str, Any]) -> Dict[str, Any]:
    basepath = _get_basepath(args)
    path = _conf_path(basepath)

    existed = os.path.exists(path)
    deleted = False
    err = ""

    try:
        with _conf_lock(basepath):
            if os.path.exists(path):
                os.remove(path)
                deleted = True
    except Exception as e:
        err = str(e)

    _append_event(basepath, {
        "type": "rss_auto_fetch.config_delete",
        "existed": bool(existed),
        "deleted": bool(deleted),
        "error": err,
    })

    out: Dict[str, Any] = {"success": True, "existed": existed, "deleted": deleted}
    if err:
        out["warning"] = err
    return out


# ============================================================
# Scheduler entry (import in api_gateway.py)
# ============================================================

def nisb_rss_auto_fetch_scheduler_tick_all_users(users_root: str = "/data/users") -> Dict[str, Any]:
    started = _utc_iso()
    ran = 0
    skipped = 0
    failed = 0

    try:
        max_users_per_tick = int(os.getenv("NISB_RSS_AUTO_FETCH_MAX_USERS_PER_TICK", "3"))
    except Exception:
        max_users_per_tick = 3
    max_users_per_tick = max(1, min(50, max_users_per_tick))

    now_ts = time.time()
    attempted = 0

    try:
        uids = [d for d in os.listdir(users_root) if d and not d.startswith(".")]
    except Exception:
        uids = []

    for uid in uids:
        if attempted >= max_users_per_tick:
            break

        basepath = os.path.join(users_root, uid)
        if not os.path.isdir(basepath):
            continue
        if not os.path.isdir(os.path.join(basepath, "rss")):
            continue

        peek = _peek_conf_for_tick(basepath)
        if not peek:
            skipped += 1
            continue

        enabled, _times_utc, _limit_entries, next_run_ts = peek
        if not enabled:
            skipped += 1
            continue

        if next_run_ts is not None and now_ts < next_run_ts:
            skipped += 1
            continue

        try:
            attempted += 1
            rr = _run_fetch_due_for_basepath(basepath, force=False, scheduler_run=True)
            rr_status = str(rr.get("status") or "").strip().lower()

            if rr_status == "ran":
                ran += 1
            elif rr_status == "skipped":
                skipped += 1
            elif rr_status in ("partial_failure", "error"):
                ran += 1
                failed += 1
            else:
                failed += 1
        except Exception:
            failed += 1

    if attempted == 0 and ran == 0 and failed == 0:
        overall_status = "skipped"
    elif failed > 0:
        overall_status = "partial_failure"
    else:
        overall_status = "ok"

    return {
        "success": True,
        "status": overall_status,
        "message": "" if failed == 0 else "rss_auto_fetch_tick_has_failed_users",
        "had_failures": bool(failed > 0),
        "started_at": started,
        "stats": {
            "ran": ran,
            "skipped": skipped,
            "failed": failed,
            "max_users_per_tick": max_users_per_tick,
            "attempted": attempted,
        },
    }
