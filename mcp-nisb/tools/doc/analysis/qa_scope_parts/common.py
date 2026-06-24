from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional


def clean_id(x: Any) -> str:
    return str(x or "").strip()


def safe_int_or_none(v: Any) -> Optional[int]:
    try:
        if v in (None, ""):
            return None
        return int(v)
    except Exception:
        return None


def safe_float_or_none(v: Any) -> Optional[float]:
    try:
        if v in (None, ""):
            return None
        return float(v)
    except Exception:
        return None


def safe_bool_or_none(v: Any) -> Optional[bool]:
    if isinstance(v, bool):
        return v
    if v in (None, ""):
        return None

    s = str(v).strip().lower()
    if s in ("true", "1", "yes", "on"):
        return True
    if s in ("false", "0", "no", "off"):
        return False
    return None


def parse_iso_dt_any(v: Any) -> Optional[datetime]:
    try:
        s = str(v or "").strip()
        if not s:
            return None

        s = s.replace("Z", "+00:00")
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None

