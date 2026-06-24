from __future__ import annotations

from typing import Any, Dict, List


def _safe_str(v: Any, default: str = "") -> str:
    if v is None:
        return default
    s = str(v).strip()
    return s if s else default


def _safe_list(v: Any) -> List[Any]:
    return v if isinstance(v, list) else []


def _safe_dict(v: Any) -> Dict[str, Any]:
    return v if isinstance(v, dict) else {}


def _safe_int(v: Any, default: int = 0) -> int:
    try:
        if v is None or v == "":
            return default
        return int(v)
    except Exception:
        return default


def _normalize_rel_path(value: Any) -> str:
    raw = _safe_str(value).replace("\\", "/")
    while "//" in raw:
        raw = raw.replace("//", "/")
    raw = raw.strip("/")
    if not raw:
        return ""
    parts = [p.strip() for p in raw.split("/") if p and p not in {".", ".."}]
    return "/".join(parts)


def _truncate_text(value: Any, limit: int = 280) -> str:
    text = _safe_str(value)
    if not text:
        return ""
    compact = " ".join(text.split())
    if len(compact) <= limit:
        return compact
    return compact[: max(0, limit - 1)].rstrip() + "…"


__all__ = [
    "_normalize_rel_path",
    "_safe_dict",
    "_safe_int",
    "_safe_list",
    "_safe_str",
    "_truncate_text",
]
