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


def _safe_bool(v: Any, default: bool = False) -> bool:
    if isinstance(v, bool):
        return v
    if v is None:
        return default
    if isinstance(v, (int, float)):
        return bool(v)
    s = str(v).strip().lower()
    if not s:
        return default
    return s in {"1", "true", "yes", "on", "y"}


def _truncate_text(value: Any, limit: int = 400) -> str:
    text = _safe_str(value)
    if limit <= 0 or len(text) <= limit:
        return text
    return text[:limit].rstrip() + "…"


def _collapse_inline_text(value: Any) -> str:
    text = _safe_str(value).replace("\\r", "\n")
    lines = [line.strip() for line in text.split("\n") if line.strip()]
    return " ".join(lines).strip()


def _normalize_scope(value: Any, default: str = "global") -> str:
    s = _safe_str(value, default).lower()
    if s == "doc":
        return "doc"
    if s == "library":
        return "library"
    return "global"


def _scope_rank(value: Any) -> int:
    s = _normalize_scope(value)
    if s == "doc":
        return 2
    if s == "library":
        return 1
    return 0


def _max_scope(a: Any, b: Any) -> str:
    return _normalize_scope(a if _scope_rank(a) >= _scope_rank(b) else b)


def _normalize_fs_read_scope(value: Any) -> str:
    s = _safe_str(value, "user_ro").lower()
    return "minimal" if s == "minimal" else "user_ro"


def _normalize_fs_write_scope(value: Any) -> str:
    s = _safe_str(value, "agent_files").lower()
    if s in {"none"}:
        return "none"
    if s in {"agent_files", "agentfiles"}:
        return "agent_files"
    return "agent_files"


def _normalize_requested_mode(value: Any, default: str = "off") -> str:
    s = _safe_str(value, default).lower()
    if s in {"off", "cite", "ground", "auto", "web", "mcp"}:
        return s
    return default


def _normalize_positive_int(value: Any) -> int:
    try:
        if value is None or value == "":
            return 0
        return max(0, int(float(value)))
    except Exception:
        return 0


def _normalize_id_list(value: Any) -> List[str]:
    out: List[str] = []
    seen = set()
    if not isinstance(value, list):
        return out
    for item in value:
        s = _safe_str(item)
        if not s or s in seen:
            continue
        seen.add(s)
        out.append(s)
    return out


def _first_non_empty_str(*values: Any) -> str:
    for value in values:
        s = _safe_str(value)
        if s:
            return s
    return ""


__all__ = [
    "_safe_str",
    "_safe_list",
    "_safe_dict",
    "_safe_bool",
    "_truncate_text",
    "_collapse_inline_text",
    "_normalize_scope",
    "_scope_rank",
    "_max_scope",
    "_normalize_fs_read_scope",
    "_normalize_fs_write_scope",
    "_normalize_requested_mode",
    "_normalize_positive_int",
    "_normalize_id_list",
    "_first_non_empty_str",
]
