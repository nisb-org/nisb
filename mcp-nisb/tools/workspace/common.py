#!/usr/bin/env python3
from __future__ import annotations

import os
import json
import re
import copy
import shutil
import tempfile
import hashlib
from pathlib import Path
from datetime import datetime, timezone
from typing import Any, Dict, List, Tuple, Optional

import sys
sys.path.insert(0, '/srv')

from core.user_context import auto_user_context, get_user_ctx


DEFAULT_WORKSPACES = [
    {
        "name": "💼 Work",
        "id": "workspace_work",
        "description": "Projects + collaboration",
        "libraries": [],
        "conversations": [],
        "files": [],
        "is_default": True
    },
    {
        "name": "📚 Study",
        "id": "workspace_study",
        "description": "Reading notes + knowledge building",
        "libraries": [],
        "conversations": [],
        "files": [],
        "is_default": True
    },
    {
        "name": "🎨 Creative",
        "id": "workspace_creative",
        "description": "Writing + creative work",
        "libraries": [],
        "conversations": [],
        "files": [],
        "is_default": True
    }
]

_DEFAULT_WORKSPACE_IDS = {w["id"] for w in DEFAULT_WORKSPACES}

_DEFAULT_WORKSPACE_CANONICAL = {
    "workspace_work": {
        "name": "💼 Work",
        "description": "Projects + collaboration",
        "legacy_names": {"💼 工作", "工作"},
        "legacy_descriptions": {"项目管理 + 团队协作"},
    },
    "workspace_study": {
        "name": "📚 Study",
        "description": "Reading notes + knowledge building",
        "legacy_names": {"📚 学习", "学习"},
        "legacy_descriptions": {"读书笔记 + 知识沉淀"},
    },
    "workspace_creative": {
        "name": "🎨 Creative",
        "description": "Writing + creative work",
        "legacy_names": {"🎨 创作", "创作"},
        "legacy_descriptions": {"写作 + 创意孵化"},
    },
}

_WORKSPACE_ID_RE = re.compile(r"^workspace_[a-z0-9_]+$")
_SLUG_RE_NON_ALNUM = re.compile(r"[^a-z0-9_]+$|[^a-z0-9_]+")
TEXT_EXTS = {
    ".txt", ".md", ".markdown", ".json", ".jsonl", ".py", ".js", ".ts", ".tsx",
    ".jsx", ".html", ".css", ".scss", ".sass", ".yaml", ".yml", ".sh", ".env",
    ".ini", ".toml", ".csv", ".sql", ".xml", ".vue"
}
BINARY_EXTS = {
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".ico", ".pdf", ".doc",
    ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".zip", ".tar", ".gz", ".7z",
    ".mp3", ".wav", ".mp4", ".mov", ".avi", ".mkv", ".bin"
}


def _now_iso_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ok(**kwargs: Any) -> Dict[str, Any]:
    out = {"status": "success"}
    out.update(kwargs)
    return out


def _err(message: str, **kwargs: Any) -> Dict[str, Any]:
    out = {"status": "error", "message": str(message)}
    out.update(kwargs)
    return out


def _get_workspace_path(user_ctx) -> Path:
    workspace_dir = Path(user_ctx.base) / "storage" / "workspaces"
    workspace_dir.mkdir(parents=True, exist_ok=True)
    return workspace_dir


def _get_workspace_meta_file(user_ctx, workspace_id: str) -> Path:
    workspace_dir = _get_workspace_path(user_ctx)
    wid = _require_workspace_id(workspace_id)
    return workspace_dir / f"{wid}.json"


def _get_workspace_root_dir(user_ctx, workspace_id: str, create: bool = True) -> Path:
    workspace_dir = _get_workspace_path(user_ctx)
    wid = _require_workspace_id(workspace_id)
    root_dir = workspace_dir / wid
    if create:
        root_dir.mkdir(parents=True, exist_ok=True)
    return root_dir


def _require_workspace_id(workspace_id: str) -> str:
    wid = str(workspace_id or "").strip()
    if not wid:
        raise ValueError("workspace_id is required")
    if not _WORKSPACE_ID_RE.match(wid):
        raise ValueError("invalid workspace_id")
    return wid


def _require_safe_agent_id(agent_id: str) -> str:
    s = str(agent_id or "").strip()
    if not s:
        raise ValueError("agent_id is required")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,127}", s):
        raise ValueError("invalid agent_id")
    return s


def _atomic_write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = tempfile.NamedTemporaryFile(mode="w", delete=False, encoding="utf-8", dir=str(path.parent))
    try:
        json.dump(data, tmp, ensure_ascii=False, indent=2)
        tmp.flush()
        os.fsync(tmp.fileno())
        tmp.close()
        os.replace(tmp.name, str(path))
    finally:
        try:
            if os.path.exists(tmp.name):
                os.unlink(tmp.name)
        except Exception:
            pass


def _atomic_write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = tempfile.NamedTemporaryFile(mode="w", delete=False, encoding="utf-8", dir=str(path.parent))
    try:
        tmp.write(str(content or ""))
        tmp.flush()
        os.fsync(tmp.fileno())
        tmp.close()
        os.replace(tmp.name, str(path))
    finally:
        try:
            if os.path.exists(tmp.name):
                os.unlink(tmp.name)
        except Exception:
            pass


def _read_json_file(path: Path, default: Optional[dict] = None) -> dict:
    if default is None:
        default = {}
    try:
        if not path.exists():
            return dict(default)
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f) or {}
        return data if isinstance(data, dict) else dict(default)
    except Exception:
        return dict(default)


def _write_jsonl(path: Path, rows: List[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = "\n".join(json.dumps(r, ensure_ascii=False) for r in rows)
    if text:
        text += "\n"
    _atomic_write_text(path, text)


def _load_jsonl(path: Path) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    if not path.exists():
        return out
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            s = line.strip()
            if not s:
                continue
            try:
                row = json.loads(s)
                if isinstance(row, dict):
                    out.append(row)
            except Exception:
                continue
    return out


def _migrate_default_workspace_labels_if_needed(workspace_id: str, data: dict) -> tuple[dict, bool]:
    wid = str(workspace_id or "").strip()
    spec = _DEFAULT_WORKSPACE_CANONICAL.get(wid)
    if not spec or not isinstance(data, dict):
        return data, False

    changed = False

    current_name = str(data.get("name", "") or "").strip()
    if current_name in spec["legacy_names"] or not current_name:
        data["name"] = spec["name"]
        changed = True

    current_description = str(data.get("description", "") or "").strip()
    if current_description in spec["legacy_descriptions"] or not current_description:
        data["description"] = spec["description"]
        changed = True

    if data.get("is_default") is not True:
        data["is_default"] = True
        changed = True

    if changed:
        data["last_updated"] = _now_iso_utc()
        data["default_label_migrated_at"] = _now_iso_utc()

    return data, changed


def _load_workspace_file_or_create(user_ctx, workspace_id: str) -> tuple[Path, dict]:
    workspace_file = _get_workspace_meta_file(user_ctx, workspace_id)
    wid = _require_workspace_id(workspace_id)
    _get_workspace_root_dir(user_ctx, wid, create=True)

    if workspace_file.exists():
        try:
            with open(workspace_file, "r", encoding="utf-8") as f:
                data = json.load(f) or {}
            if not isinstance(data, dict):
                raise ValueError("invalid workspace json")
            data, migrated = _migrate_default_workspace_labels_if_needed(wid, data)
            if migrated:
                _atomic_write_json(workspace_file, data)
            return workspace_file, data
        except Exception:
            default_spec = _DEFAULT_WORKSPACE_CANONICAL.get(wid)
            data = {
                "id": wid,
                "name": default_spec["name"] if default_spec else wid,
                "description": default_spec["description"] if default_spec else "",
                "is_default": bool(default_spec),
                "created_at": _now_iso_utc(),
                "last_updated": _now_iso_utc(),
                "state": {"libraries": [], "conversations": [], "files": [], "files_state": {}},
            }
            _atomic_write_json(workspace_file, data)
            return workspace_file, data

    default_spec = _DEFAULT_WORKSPACE_CANONICAL.get(wid)
    data = {
        "id": wid,
        "name": default_spec["name"] if default_spec else wid,
        "description": default_spec["description"] if default_spec else "",
        "is_default": bool(default_spec),
        "created_at": _now_iso_utc(),
        "last_updated": _now_iso_utc(),
        "state": {"libraries": [], "conversations": [], "files": [], "files_state": {}},
    }
    _atomic_write_json(workspace_file, data)
    return workspace_file, data


def _load_workspace_file_strict(user_ctx, workspace_id: str) -> tuple[Path, dict]:
    workspace_file = _get_workspace_meta_file(user_ctx, workspace_id)
    wid = _require_workspace_id(workspace_id)
    if not workspace_file.exists():
        raise FileNotFoundError(f"workspace not found: {wid}")
    with open(workspace_file, "r", encoding="utf-8") as f:
        data = json.load(f) or {}
    if not isinstance(data, dict):
        raise ValueError(f"invalid workspace data: {wid}")
    _get_workspace_root_dir(user_ctx, wid, create=True)
    return workspace_file, data


def _get_state(ws: dict) -> dict:
    st = ws.get("state") if isinstance(ws.get("state"), dict) else {}
    return st if isinstance(st, dict) else {}


def _ensure_files_state_schema(ws: dict) -> dict:
    st = _get_state(ws)
    fs = st.get("files_state") if isinstance(st.get("files_state"), dict) else {}
    if not isinstance(fs, dict):
        fs = {}

    if "saved" not in fs and "current" not in fs:
        old_focused = str(fs.get("focused_root_path", "") or "").strip().lstrip("/")
        old_favs = fs.get("favorites")
        if not isinstance(old_favs, list):
            old_favs = []
        fs = {
            "saved": {"focused_root_path": old_focused, "favorites": old_favs},
            "current": {"focused_root_path": old_focused, "favorites": old_favs},
            "saved_at": _now_iso_utc(),
            "legacy_favorites_migrated": bool(fs.get("legacy_favorites_migrated", False)),
        }

    if not isinstance(fs.get("saved"), dict):
        fs["saved"] = {"focused_root_path": "", "favorites": []}
    if not isinstance(fs.get("current"), dict):
        fs["current"] = {"focused_root_path": "", "favorites": []}

    for k in ("saved", "current"):
        box = fs.get(k) if isinstance(fs.get(k), dict) else {}
        focused = str(box.get("focused_root_path", "") or "").strip().lstrip("/")
        favs = box.get("favorites")
        if not isinstance(favs, list):
            favs = []
        fs[k] = {"focused_root_path": focused, "favorites": favs}

    if "legacy_favorites_migrated" not in fs:
        fs["legacy_favorites_migrated"] = False

    st["files_state"] = fs
    ws["state"] = st
    return fs


def _parse_iso8601_any(s: str):
    if not s:
        return None
    t = str(s).strip()
    if not t:
        return None
    if t.endswith("Z"):
        t = t[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(t)
    except Exception:
        return None


def _normalize_rel_path(p: str) -> str:
    s = str(p or "").strip().replace("\\", "/")
    s = re.sub(r"/+", "/", s)
    s = s.lstrip("/")
    if not s:
        return ""
    parts = s.split("/")
    for seg in parts:
        if seg == "..":
            return ""
    return s


def _normalize_rel_path_strict(p: str) -> str:
    s = _normalize_rel_path(p)
    if str(p or "").strip() and not s:
        raise ValueError("unsafe relative path")
    return s


def _normalize_md_filename(filename: str, default_name: str) -> str:
    s = str(filename or "").strip().replace("\\", "/")
    s = s.split("/")[-1].strip()
    if not s:
        s = default_name
    s = re.sub(r"[^A-Za-z0-9._-]+", "_", s)
    if not s.lower().endswith(".md"):
        s = f"{s}.md"
    if s in {".md", "..md"}:
        s = default_name
    return s


def _resolve_under_root(root_dir: Path, rel_path: str, require_exists: bool = False) -> Path:
    rel = _normalize_rel_path_strict(rel_path)
    target = (root_dir / rel).resolve()
    root_resolved = root_dir.resolve()
    if target != root_resolved and root_resolved not in target.parents:
        raise ValueError("path out of workspace scope")
    if require_exists and not target.exists():
        raise FileNotFoundError(f"path not found: {rel}")
    return target


def _is_in_scope_agent_files(rel_path: str) -> bool:
    s = str(rel_path or "")
    return s == "agent_files" or s.startswith("agent_files/")


def _resolve_user_base_dir(user_ctx) -> Path:
    base_raw = str(getattr(user_ctx, "base", "") or "").strip()
    if not base_raw:
        raise ValueError("user base not found")
    return Path(base_raw).resolve()


def _resolve_focus_root_scope(
    user_ctx,
    workspace_id: str,
    focus_root: str = "",
    require_exists: bool = True,
) -> tuple[str, dict, Path, str, Path, str]:
    wid = _require_workspace_id(workspace_id)
    _, ws = _load_workspace_file_or_create(user_ctx, wid)
    workspace_root = _get_workspace_root_dir(user_ctx, wid, create=True)
    focus = _normalize_rel_path(focus_root)

    if not focus:
        scope_root = workspace_root
        scope_kind = "workspace_root"
    elif _is_in_scope_agent_files(focus):
        user_base = _resolve_user_base_dir(user_ctx)
        scope_root = (user_base / focus).resolve()
        if scope_root != user_base and user_base not in scope_root.parents:
            raise ValueError("focus_root 越界")
        scope_kind = "agent_files"
    else:
        scope_root = _resolve_under_root(workspace_root, focus, require_exists=False)
        scope_kind = "workspace_relative"

    if scope_root.exists() and not scope_root.is_dir():
        raise NotADirectoryError(f"focus_root is not a directory: {focus}")

    if require_exists and not scope_root.exists():
        raise FileNotFoundError(f"focus_root not found: {focus}")

    return wid, ws, workspace_root, focus, scope_root, scope_kind


def _audit_file_path(user_ctx) -> Path:
    return Path(user_ctx.base) / "storage/audit/filesystem_audit.jsonl"


def _load_fs_audit_events_between(user_ctx, start_dt, end_dt) -> list:
    audit_path = _audit_file_path(user_ctx)
    if not audit_path.exists():
        return []

    ops_allow = {"file_move_path", "file_rename", "file_delete", "dir_delete", "dir_move_path"}
    out = []

    with open(audit_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                ev = json.loads(line)
            except Exception:
                continue

            op = str(ev.get("operation", "") or "").strip()
            if op not in ops_allow:
                continue

            ts = _parse_iso8601_any(ev.get("ts", ""))
            if ts is None:
                continue
            if start_dt is not None and ts < start_dt:
                continue
            if end_dt is not None and ts > end_dt:
                continue

            md = ev.get("metadata") if isinstance(ev.get("metadata"), dict) else {}
            paths = ev.get("paths")
            if not isinstance(paths, list):
                paths = []

            old_path = ""
            new_path = ""

            if op == "file_move_path":
                old_path = _normalize_rel_path(md.get("old_path", ""))
                new_path = _normalize_rel_path(md.get("new_path", ""))

            elif op == "file_rename":
                old_path = _normalize_rel_path(paths[0] if paths else "")
                new_name = str(md.get("new_name", "") or "").strip().replace("\\", "/")
                new_name = new_name.split("/")[-1] if new_name else ""
                if old_path and new_name:
                    d = os.path.dirname(old_path).replace("\\", "/").strip("/")
                    new_path = _normalize_rel_path(f"{d}/{new_name}" if d else new_name)

            elif op == "file_delete":
                old_path = _normalize_rel_path(paths[0] if paths else "") or _normalize_rel_path(md.get("filename", ""))

            elif op == "dir_delete":
                old_path = _normalize_rel_path(paths[0] if paths else "")

            elif op == "dir_move_path":
                old_path = _normalize_rel_path(md.get("old_path", ""))
                new_path = _normalize_rel_path(md.get("new_path", ""))

            if op in ("file_move_path", "file_rename", "dir_move_path"):
                if not old_path or not new_path:
                    continue
            else:
                if not old_path:
                    continue

            out.append({
                "ts": ts,
                "operation": op,
                "old_path": old_path,
                "new_path": new_path,
            })

    out.sort(key=lambda x: x["ts"])
    return out


def _apply_path_events_to_path(rel_path: str, events: list) -> tuple[str, list]:
    p = _normalize_rel_path(rel_path)
    trace = []
    if not p:
        return "", [{"reason": "unsafe_path", "path": rel_path}]

    for ev in events:
        op = ev["operation"]
        oldp = ev["old_path"]
        newp = ev.get("new_path", "")

        if op in ("file_move_path", "file_rename"):
            if p == oldp:
                p = newp
                trace.append({"op": op, "old_path": oldp, "new_path": newp})
                continue

        if op == "dir_move_path":
            if p == oldp:
                p = newp
                trace.append({"op": op, "old_path": oldp, "new_path": newp})
                continue
            prefix = oldp.rstrip("/") + "/"
            if p.startswith(prefix):
                suffix = p[len(prefix):]
                p = re.sub(r"/+", "/", newp.rstrip("/") + "/" + suffix)
                trace.append({"op": op, "old_path": oldp, "new_path": newp})
                continue

        if op == "file_delete":
            if p == oldp:
                trace.append({"op": op, "old_path": oldp, "reason": "deleted"})
                return "", trace

        if op == "dir_delete":
            if p == oldp or p.startswith(oldp.rstrip("/") + "/"):
                trace.append({"op": op, "old_path": oldp, "reason": "dir_deleted"})
                return "", trace

    return _normalize_rel_path(p), trace


def _map_favorites_from_saved_with_audit(user_ctx, favorites: list, saved_at_iso: str) -> tuple[list, dict]:
    base = Path(user_ctx.base).resolve()
    now_dt = datetime.now(timezone.utc)
    start_dt = _parse_iso8601_any(saved_at_iso)
    events = _load_fs_audit_events_between(user_ctx, start_dt, now_dt)

    migrated = []
    pruned = []
    out = []
    seen = set()

    if not isinstance(favorites, list):
        favorites = []

    for it in favorites:
        if not isinstance(it, dict):
            pruned.append({"reason": "invalid_item", "item": it})
            continue

        raw_path = it.get("path", "")
        fav_type = "directory" if str(it.get("type", "file") or "file").strip().lower() == "directory" else "file"

        p0 = _normalize_rel_path(raw_path)
        if not p0:
            pruned.append({"reason": "unsafe_path", "path": raw_path})
            continue

        if not _is_in_scope_agent_files(p0):
            pruned.append({"reason": "out_of_scope", "path": p0})
            continue

        p1, trace = _apply_path_events_to_path(p0, events)
        if not p1:
            pruned.append({"reason": "deleted_by_audit", "path": p0, "trace": trace[-3:]})
            continue

        if not _is_in_scope_agent_files(p1):
            pruned.append({"reason": "out_of_scope_after_migrate", "path": p1, "from": p0})
            continue

        target = (base / p1).resolve()
        base_prefix = str(base) + os.sep
        if not (str(target) == str(base) or str(target).startswith(base_prefix)):
            pruned.append({"reason": "unsafe_after_migrate", "path": p1, "from": p0})
            continue

        exists_ok = target.is_dir() if fav_type == "directory" else target.exists()
        if not exists_ok:
            pruned.append({"reason": "missing_after_migrate", "path": p1, "from": p0})
            continue

        key = f"{fav_type}::{p1}"
        if key in seen:
            continue
        seen.add(key)

        new_it = dict(it)
        new_it["path"] = p1
        new_it["type"] = fav_type
        out.append(new_it)

        if p1 != p0:
            migrated.append({"old_path": p0, "new_path": p1, "type": fav_type})

    stats = {
        "migrated_count": len(migrated),
        "pruned_count": len(pruned),
        "audit_events_used": len(events),
        "migrated_samples": migrated[:20],
        "pruned_samples": pruned[:20],
        "window_start": saved_at_iso or "",
        "window_end": now_dt.isoformat(),
    }
    return out, stats


def _slugify_workspace_name(name: str) -> str:
    s = str(name or "").strip().lower()
    s = re.sub(r"\s+", "_", s)
    s = re.sub(r"[^a-z0-9_]+", "_", s)
    s = re.sub(r"_+", "_", s).strip("_")
    return s


def _pick_unique_workspace_id(workspace_dir: Path, base_slug: str) -> str:
    slug = str(base_slug or "").strip().lower() or "custom"
    reserved = {"work", "study", "creative"}
    if slug in reserved:
        slug = f"{slug}_custom"

    for i in range(1, 500):
        wid = f"workspace_{slug}" if i == 1 else f"workspace_{slug}_{i}"
        _require_workspace_id(wid)
        f = workspace_dir / f"{wid}.json"
        if not f.exists():
            return wid
    raise ValueError("cannot allocate workspace_id (too many conflicts)")


def _coerce_bool(v: Any, default: bool = False) -> bool:
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return bool(v)
    if isinstance(v, str):
        return v.strip().lower() in {"1", "true", "yes", "on"}
    return default


def _coerce_int(v: Any, default: int, low: Optional[int] = None, high: Optional[int] = None) -> int:
    try:
        n = int(v)
    except Exception:
        n = int(default)
    if low is not None and n < low:
        n = low
    if high is not None and n > high:
        n = high
    return n


def _is_text_file(path: Path) -> bool:
    if path.suffix.lower() in BINARY_EXTS:
        return False
    if path.suffix.lower() in TEXT_EXTS:
        return True
    try:
        with open(path, "rb") as f:
            sample = f.read(1024)
        sample.decode("utf-8")
        return True
    except Exception:
        return False


def _read_text_file(path: Path, max_chars: int = 12000) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except Exception:
        text = path.read_text(encoding="utf-8", errors="ignore")
    if max_chars > 0:
        return text[:max_chars]
    return text


def _chunk_text(text: str, chunk_size: int = 900, overlap: int = 120) -> List[str]:
    src = str(text or "").strip()
    if not src:
        return []
    if len(src) <= chunk_size:
        return [src]

    chunks: List[str] = []
    start = 0
    n = len(src)
    while start < n:
        end = min(n, start + chunk_size)
        part = src[start:end].strip()
        if part:
            chunks.append(part)
        if end >= n:
            break
        start = max(end - overlap, start + 1)
    return chunks


def _query_terms(query: str) -> List[str]:
    raw = re.findall(r"[A-Za-z0-9_.\-/]+|[\u4e00-\u9fff]+", str(query or "").lower())
    out = []
    seen = set()
    for t in raw:
        if t in seen:
            continue
        seen.add(t)
        out.append(t)
    return out


def _score_text_match(query: str, rel_path: str, text: str) -> float:
    q = str(query or "").strip().lower()
    rp = str(rel_path or "").lower()
    tx = str(text or "").lower()
    if not q:
        return 0.0

    terms = _query_terms(q)
    score = 0.0

    if q in rp:
        score += 8.0
    if q in tx:
        score += 10.0

    for term in terms:
        if term in rp:
            score += 3.5
        c = tx.count(term)
        if c > 0:
            score += min(8.0, 1.2 * c)

    score += min(3.0, len(text) / 1200.0)
    return score


def _index_dir(content_root: Path) -> Path:
    return content_root / ".nisb_index"


def _scope_key(focus_root: str) -> str:
    raw = focus_root or "__workspace_root__"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:12]


def _upsert_md_section(existing: str, section_title: str, body_md: str) -> str:
    title = str(section_title or "").strip() or "latest"
    block = f"## {title}\n\n{body_md.strip()}\n"
    if not existing.strip():
        return block

    pattern = re.compile(
        rf"(^##\s+{re.escape(title)}\s*\n.*?)(?=^##\s+|\Z)",
        re.MULTILINE | re.DOTALL,
    )

    if pattern.search(existing):
        updated = pattern.sub(block + "\n", existing, count=1)
        return updated.strip() + "\n"

    return existing.rstrip() + "\n\n" + block + "\n"

