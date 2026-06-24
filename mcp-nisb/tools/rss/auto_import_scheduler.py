from __future__ import annotations

import os
import time
import json
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from .auto_import_rules import nisb_rss_auto_import_run_due


def _utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _rules_path(basepath: str) -> str:
    return os.path.join(basepath, "rss", "auto_import_rules.json")


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


def _user_next_due_ts(basepath: str, *, now_ts: float) -> Optional[float]:
    rp = _rules_path(basepath)
    doc = _read_json_small(rp)
    if not isinstance(doc, dict):
        return None

    rules = doc.get("rules")
    if not isinstance(rules, list) or not rules:
        return None

    best: Optional[float] = None
    for r in rules:
        if not isinstance(r, dict):
            continue
        if not bool(r.get("enabled", True)):
            continue

        times_utc = r.get("times_utc")
        try:
            interval_minutes = int(r.get("interval_minutes") or 0)
        except Exception:
            interval_minutes = 0

        has_schedule = False
        if isinstance(times_utc, list) and len(times_utc) > 0:
            has_schedule = True
        elif interval_minutes > 0:
            has_schedule = True
        if not has_schedule:
            continue

        nxt = _parse_iso_ts(str(r.get("next_run_at") or ""))
        if nxt is None:
            nxt = float(now_ts)

        if best is None or nxt < best:
            best = nxt

    return best


def _user_has_due(basepath: str, *, now_ts: float) -> bool:
    rp = _rules_path(basepath)
    doc = _read_json_small(rp)
    if not isinstance(doc, dict):
        return False

    rules = doc.get("rules")
    if not isinstance(rules, list) or not rules:
        return False

    for r in rules:
        if not isinstance(r, dict):
            continue
        if not bool(r.get("enabled", True)):
            continue

        times_utc = r.get("times_utc")
        try:
            interval_minutes = int(r.get("interval_minutes") or 0)
        except Exception:
            interval_minutes = 0

        has_schedule = False
        if isinstance(times_utc, list) and len(times_utc) > 0:
            has_schedule = True
        elif interval_minutes > 0:
            has_schedule = True
        if not has_schedule:
            continue

        nxt = _parse_iso_ts(str(r.get("next_run_at") or ""))
        if nxt is None:
            return True
        if float(now_ts) >= float(nxt):
            return True

    return False


def nisb_rss_auto_import_scheduler_next_run_ts_all_users(
    users_root: str = "/data/users",
    *,
    now_ts: Optional[float] = None
) -> Dict[str, Any]:
    if now_ts is None:
        now_ts = time.time()
    now_ts = float(now_ts)

    try:
        max_scan_users = int(
            os.getenv(
                "NISB_RSS_AUTO_IMPORT_MAX_USERS_SCAN_FOR_TICK",
                os.getenv("NISB_RSS_AUTO_IMPORT_MAX_USERS_SCAN", "5000"),
            )
        )
    except Exception:
        max_scan_users = 5000
    max_scan_users = max(1, min(200000, max_scan_users))

    try:
        uids = [d for d in os.listdir(users_root) if d and not d.startswith(".")]
    except Exception:
        uids = []

    best: Optional[float] = None
    scanned = 0
    for uid in uids:
        if scanned >= max_scan_users:
            break
        scanned += 1

        basepath = os.path.join(users_root, uid)
        if not os.path.isdir(basepath):
            continue
        if not os.path.isdir(os.path.join(basepath, "rss")):
            continue

        nxt = _user_next_due_ts(basepath, now_ts=now_ts)
        if nxt is None:
            continue
        if best is None or nxt < best:
            best = nxt

    return {"success": True, "next_run_ts": best, "scanned_users": scanned}


def nisb_rss_auto_import_scheduler_tick_all_users(users_root: str = "/data/users") -> Dict[str, Any]:
    started = _utc_iso()
    ran_users = 0
    skipped_users = 0
    failed_users = 0

    try:
        max_users_per_tick = int(os.getenv("NISB_RSS_AUTO_IMPORT_MAX_USERS_PER_TICK", "2"))
    except Exception:
        max_users_per_tick = 2
    max_users_per_tick = max(1, min(2000, max_users_per_tick))

    try:
        max_seconds_per_tick = int(os.getenv("NISB_RSS_AUTO_IMPORT_MAX_SECONDS_PER_TICK", "40"))
    except Exception:
        max_seconds_per_tick = 40
    max_seconds_per_tick = max(5, min(600, max_seconds_per_tick))

    try:
        max_rules_per_user = int(os.getenv("NISB_RSS_AUTO_IMPORT_MAX_RULES_PER_USER", "1"))
    except Exception:
        max_rules_per_user = 1
    max_rules_per_user = max(1, min(50, max_rules_per_user))

    now_ts = float(time.time())
    deadline_ts = now_ts + float(max_seconds_per_tick)
    attempted_users = 0

    try:
        uids = [d for d in os.listdir(users_root) if d and not d.startswith(".")]
    except Exception:
        uids = []

    for uid in uids:
        if attempted_users >= max_users_per_tick:
            break
        if time.time() > deadline_ts:
            break

        basepath = os.path.join(users_root, uid)
        if not os.path.isdir(basepath):
            continue
        if not os.path.isdir(os.path.join(basepath, "rss")):
            continue

        rp = _rules_path(basepath)
        if not os.path.exists(rp):
            skipped_users += 1
            continue
        try:
            if os.path.getsize(rp) < 5:
                skipped_users += 1
                continue
        except Exception:
            skipped_users += 1
            continue

        if not _user_has_due(basepath, now_ts=now_ts):
            skipped_users += 1
            continue

        attempted_users += 1
        try:
            r = nisb_rss_auto_import_run_due({
                "basepath": basepath,
                "now_ts": now_ts,
                "max_rules": max_rules_per_user,
                "max_total_ms": int(max(1000, (deadline_ts - time.time()) * 1000)),
            })

            status = str((r or {}).get("status") or "").strip().lower()
            stats = (r or {}).get("stats") or {}
            ran_i = int(stats.get("ran") or 0)
            failed_i = int(stats.get("failed") or 0)
            failed_rules_i = int(stats.get("failed_rules") or 0)

            if status == "partial_failure" or failed_i > 0 or failed_rules_i > 0:
                if ran_i > 0:
                    ran_users += 1
                else:
                    skipped_users += 1
                failed_users += 1
            elif ran_i > 0:
                ran_users += 1
            else:
                skipped_users += 1

        except Exception:
            failed_users += 1

    if attempted_users == 0 and ran_users == 0 and failed_users == 0:
        overall_status = "skipped"
    elif failed_users > 0:
        overall_status = "partial_failure"
    else:
        overall_status = "ok"

    return {
        "success": True,
        "status": overall_status,
        "message": "" if failed_users == 0 else "rss_auto_import_tick_has_failed_users",
        "had_failures": bool(failed_users > 0),
        "started_at": started,
        "stats": {
            "ran_users": ran_users,
            "skipped_users": skipped_users,
            "failed_users": failed_users,
            "max_users_per_tick": max_users_per_tick,
            "max_seconds_per_tick": max_seconds_per_tick,
            "attempted_users": attempted_users,
        },
    }

