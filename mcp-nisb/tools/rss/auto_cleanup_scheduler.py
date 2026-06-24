# /opt/mcp-gateway/mcp-nisb/tools/rss/auto_cleanup_scheduler.py
from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from .rss_data_cleanup import nisb_rss_data_cleanup


def _utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


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


def _rss_root_local(basepath: str) -> str:
    return os.path.join(str(basepath or "").rstrip("/"), "rss")


def _cfg_path(basepath: str) -> str:
    return os.path.join(_rss_root_local(basepath), "auto_cleanup_config.json")


def _lock_path(basepath: str) -> str:
    return os.path.join(_rss_root_local(basepath), ".auto_cleanup.lock")


def _atomic_write_json(path: str, doc: Dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = f"{path}.tmp.{int(time.time() * 1000)}"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def _bool_arg(args: Dict[str, Any], key: str, default: bool = False) -> bool:
    if key not in args:
        return bool(default)
    v = args.get(key)
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return bool(v)
    s = str(v or "").strip().lower()
    if s in ("1", "true", "yes", "on", "enabled"):
        return True
    if s in ("0", "false", "no", "off", "disabled", "none", "null", ""):
        return False
    return bool(default)


def _int_arg(args: Dict[str, Any], keys: list[str], default: int) -> int:
    for key in keys:
        if key not in args:
            continue
        try:
            return int(args.get(key))
        except Exception:
            return int(default)
    return int(default)


def _cleanup_default_cfg() -> Dict[str, Any]:
    return {
        "success": True,
        "enabled": False,
        "keep_days": 7,
        "interval_hours": 24,
        "rebuild_index": True,
        "delete_logs_before_days": 0,
        "last_run_at": None,
        "next_run_at": None,
        "updated_at": None,
        "last_error": "",
    }


def _normalize_cfg(doc: Dict[str, Any]) -> Dict[str, Any]:
    out = _cleanup_default_cfg()
    if isinstance(doc, dict):
        out.update(doc)

    try:
        out["enabled"] = _bool_arg(out, "enabled", default=False)
    except Exception:
        out["enabled"] = False

    try:
        out["keep_days"] = max(1, min(365, int(out.get("keep_days") or 7)))
    except Exception:
        out["keep_days"] = 7

    try:
        out["interval_hours"] = max(1, min(168, int(out.get("interval_hours") or 24)))
    except Exception:
        out["interval_hours"] = 24

    if "rebuild_embeddings" in out and "rebuild_index" not in out:
        out["rebuild_index"] = out.get("rebuild_embeddings")

    try:
        out["rebuild_index"] = _bool_arg(out, "rebuild_index", default=True)
    except Exception:
        out["rebuild_index"] = True

    if "log_keep_days" in out and "delete_logs_before_days" not in out:
        out["delete_logs_before_days"] = out.get("log_keep_days")

    try:
        out["delete_logs_before_days"] = max(0, min(3650, int(out.get("delete_logs_before_days") or 0)))
    except Exception:
        out["delete_logs_before_days"] = 0

    out["success"] = True
    out["last_run_at"] = out.get("last_run_at") or None
    out["next_run_at"] = out.get("next_run_at") or None
    out["updated_at"] = out.get("updated_at") or None
    out["last_error"] = str(out.get("last_error") or "")[:500]
    return out


def _load_cfg(basepath: str) -> Dict[str, Any]:
    p = _cfg_path(basepath)
    if not os.path.exists(p):
        return _cleanup_default_cfg()

    try:
        with open(p, "r", encoding="utf-8") as f:
            doc = json.load(f)
        if not isinstance(doc, dict):
            doc = {}
    except Exception:
        doc = {}

    return _normalize_cfg(doc)


def _acquire_cleanup_lock(basepath: str, stale_seconds: int = 6 * 3600) -> Optional[int]:
    lp = _lock_path(basepath)
    os.makedirs(os.path.dirname(lp), exist_ok=True)

    try:
        if os.path.exists(lp):
            st = os.stat(lp)
            if time.time() - float(st.st_mtime) > float(stale_seconds):
                try:
                    os.remove(lp)
                except Exception:
                    pass
    except Exception:
        pass

    try:
        fd = os.open(lp, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
        os.write(fd, str(os.getpid()).encode("utf-8"))
        return fd
    except FileExistsError:
        return None
    except Exception:
        return None


def _release_cleanup_lock(basepath: str, fd: Optional[int]) -> None:
    try:
        if fd is not None:
            os.close(fd)
    except Exception:
        pass

    try:
        lp = _lock_path(basepath)
        if os.path.exists(lp):
            os.remove(lp)
    except Exception:
        pass


def nisb_rss_auto_cleanup_config_get(args: Dict[str, Any]) -> Dict[str, Any]:
    basepath = str(args.get("basepath") or "").strip()
    if not basepath:
        return {"success": False, "message": "missing injected basepath"}
    return _load_cfg(basepath)


def nisb_rss_auto_cleanup_config_set(args: Dict[str, Any]) -> Dict[str, Any]:
    basepath = str(args.get("basepath") or "").strip()
    if not basepath:
        return {"success": False, "message": "missing injected basepath"}

    cur = _load_cfg(basepath)

    enabled = _bool_arg(args, "enabled", default=bool(cur.get("enabled", False)))

    keep_days = _int_arg(args, ["keep_days", "keepDays"], int(cur.get("keep_days") or 7))
    keep_days = max(1, min(365, keep_days))

    interval_hours = _int_arg(args, ["interval_hours", "intervalHours"], int(cur.get("interval_hours") or 24))
    interval_hours = max(1, min(168, interval_hours))

    if "rebuild_index" in args:
        rebuild_index = _bool_arg(args, "rebuild_index", default=True)
    elif "rebuild_embeddings" in args:
        rebuild_index = _bool_arg(args, "rebuild_embeddings", default=True)
    else:
        rebuild_index = bool(cur.get("rebuild_index", True))

    delete_logs_before_days = _int_arg(
        args,
        ["delete_logs_before_days", "log_keep_days", "logKeepDays"],
        int(cur.get("delete_logs_before_days") or 0),
    )
    delete_logs_before_days = max(0, min(3650, delete_logs_before_days))

    now_iso = _utc_iso()
    now_ts = time.time()

    next_run_at = None
    if enabled:
        nxt = _parse_iso_ts(str(cur.get("next_run_at") or ""))
        if nxt is None or nxt < now_ts + 5:
            nxt = now_ts + 60.0
        next_run_at = datetime.fromtimestamp(float(nxt), tz=timezone.utc).isoformat()

    doc = {
        "success": True,
        "enabled": bool(enabled),
        "keep_days": int(keep_days),
        "interval_hours": int(interval_hours),
        "rebuild_index": bool(rebuild_index),
        "delete_logs_before_days": int(delete_logs_before_days),
        "last_run_at": cur.get("last_run_at"),
        "next_run_at": next_run_at,
        "updated_at": now_iso,
        "last_error": "" if enabled else str(cur.get("last_error") or "")[:500],
    }

    _atomic_write_json(_cfg_path(basepath), doc)
    return doc


def nisb_rss_auto_cleanup_config_delete(args: Dict[str, Any]) -> Dict[str, Any]:
    basepath = str(args.get("basepath") or "").strip()
    if not basepath:
        return {"success": False, "message": "missing injected basepath"}

    p = _cfg_path(basepath)
    try:
        if os.path.exists(p):
            os.remove(p)
        return {"success": True, "deleted": True}
    except Exception as e:
        return {"success": False, "message": repr(e)}


def nisb_rss_auto_cleanup_run_now(args: Dict[str, Any]) -> Dict[str, Any]:
    basepath = str(args.get("basepath") or "").strip()
    if not basepath:
        return {"success": False, "message": "missing injected basepath"}

    cfg = _load_cfg(basepath)

    keep_days = _int_arg(args, ["keep_days", "keepDays"], int(cfg.get("keep_days") or 7))
    interval_hours = _int_arg(args, ["interval_hours", "intervalHours"], int(cfg.get("interval_hours") or 24))

    if "rebuild_index" in args:
        rebuild_index = _bool_arg(args, "rebuild_index", default=bool(cfg.get("rebuild_index", True)))
    elif "rebuild_embeddings" in args:
        rebuild_index = _bool_arg(args, "rebuild_embeddings", default=bool(cfg.get("rebuild_index", True)))
    else:
        rebuild_index = bool(cfg.get("rebuild_index", True))

    delete_logs_before_days = _int_arg(
        args,
        ["delete_logs_before_days", "log_keep_days", "logKeepDays"],
        int(cfg.get("delete_logs_before_days") or 0),
    )

    keep_days = max(1, min(365, keep_days))
    interval_hours = max(1, min(168, interval_hours))
    delete_logs_before_days = max(0, min(3650, delete_logs_before_days))

    persist = _bool_arg(args, "persist", default=False)

    lock_fd = _acquire_cleanup_lock(basepath)
    if lock_fd is None:
        r_busy = {
            "success": False,
            "status": "busy",
            "message": "rss_auto_cleanup_already_running",
            "auto_cleanup": True,
            "persisted": False,
        }
        if persist:
            cfg["last_error"] = "rss_auto_cleanup_already_running"
            cfg["updated_at"] = _utc_iso()
            _atomic_write_json(_cfg_path(basepath), cfg)
        return r_busy

    try:
        r = nisb_rss_data_cleanup(
            {
                "basepath": basepath,
                "keep_days": keep_days,
                "dry_run": False,
                "rebuild_index": rebuild_index,
                "delete_logs_before_days": delete_logs_before_days,
            }
        )
        if not isinstance(r, dict):
            r = {"success": False, "message": "invalid cleanup result"}
    except Exception as e:
        r = {"success": False, "message": f"rss_data_cleanup exception: {e}"}
    finally:
        _release_cleanup_lock(basepath, lock_fd)

    if not persist:
        r.update({"auto_cleanup": True, "persisted": False})
        return r

    now_ts = time.time()
    enabled = bool(cfg.get("enabled", False))
    next_run_at = cfg.get("next_run_at")

    if enabled:
        next_ts = now_ts + float(interval_hours) * 3600.0
        next_run_at = datetime.fromtimestamp(next_ts, tz=timezone.utc).isoformat()

    ok = bool(r.get("success", False))
    err_text = "" if ok else str(r.get("message") or r.get("error") or "rss_auto_cleanup_failed")[:500]

    cfg["enabled"] = enabled
    cfg["keep_days"] = keep_days
    cfg["interval_hours"] = interval_hours
    cfg["rebuild_index"] = rebuild_index
    cfg["delete_logs_before_days"] = delete_logs_before_days
    cfg["last_run_at"] = _utc_iso()
    cfg["next_run_at"] = next_run_at
    cfg["updated_at"] = _utc_iso()
    cfg["last_error"] = err_text
    _atomic_write_json(_cfg_path(basepath), cfg)

    r.update({
        "auto_cleanup": True,
        "persisted": True,
        "next_run_at": cfg.get("next_run_at"),
        "last_error": cfg.get("last_error") or "",
    })
    return r


def nisb_rss_auto_cleanup_scheduler_tick_all_users(users_root: str) -> Dict[str, Any]:
    users_root = str(users_root or "").rstrip("/")
    if not users_root or not os.path.isdir(users_root):
        return {"success": False, "message": "invalid users_root"}

    now_ts = time.time()
    ran = 0
    skipped = 0
    errors = 0
    checked = 0

    try:
        uids = [d for d in os.listdir(users_root) if d and not d.startswith(".")]
    except Exception:
        uids = []

    for uid in uids:
        basepath = os.path.join(users_root, uid)
        if not os.path.isdir(os.path.join(basepath, "rss")):
            skipped += 1
            continue

        checked += 1
        cfg = _load_cfg(basepath)
        if not bool(cfg.get("enabled", False)):
            skipped += 1
            continue

        nxt = _parse_iso_ts(str(cfg.get("next_run_at") or ""))
        if nxt is None:
            cfg["next_run_at"] = datetime.fromtimestamp(
                now_ts + 60.0,
                tz=timezone.utc,
            ).isoformat()
            cfg["updated_at"] = _utc_iso()
            cfg["last_error"] = ""
            try:
                _atomic_write_json(_cfg_path(basepath), cfg)
            except Exception:
                errors += 1
            skipped += 1
            continue

        if float(nxt) > float(now_ts):
            skipped += 1
            continue

        try:
            r = nisb_rss_auto_cleanup_run_now({
                "basepath": basepath,
                "persist": True,
            })
            if isinstance(r, dict) and bool(r.get("success", False)):
                ran += 1
            elif isinstance(r, dict) and str(r.get("status") or "") == "busy":
                skipped += 1
            else:
                errors += 1
        except Exception:
            errors += 1

    return {
        "success": True,
        "checked": checked,
        "ran": ran,
        "skipped": skipped,
        "errors": errors,
    }
