#!/usr/bin/env python3
"""
Filesystem favorites for pinned files and directories.

Compatibility behavior:
- If args include workspace_id, favorites are stored in:
  {base}/storage/workspaces/{workspace_id}.json
  under state.files_state.current.favorites.
- On the first workspace read, legacy bookmarks are migrated from:
  {base}/storage/fs_bookmarks/bookmarks.jsonl
- If workspace_id is not provided, the legacy JSONL store is still used.
"""

from __future__ import annotations

import json
import os
import re
import tempfile
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, List, Tuple, Dict, Any

from core.user_context import auto_user_context, get_user_ctx


BOOKMARKS_DIR_NAME = "fs_bookmarks"
BOOKMARKS_FILE_NAME = "bookmarks.jsonl"

_WORKSPACE_ID_RE = re.compile(r"^workspace_[a-z0-9_]+$")

_ALLOWED_HIGHLIGHT_COLORS = {
    "",
    "amber",
    "blue",
    "emerald",
    "violet",
    "rose",
    "cyan",
    "slate",
}


@dataclass
class FsBookmark:
    path: str
    type: str
    pinned_at: str
    highlight_color: str = ""
    highlighted_at: str = ""

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "FsBookmark":
        return cls(
            path=str(data.get("path", "")).strip(),
            type=str(data.get("type", "file")).strip() or "file",
            pinned_at=str(data.get("pinned_at", "")).strip(),
            highlight_color=str(data.get("highlight_color", "")).strip(),
            highlighted_at=str(data.get("highlighted_at", "")).strip(),
        )


def _now_iso_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize_rel_path(p: str) -> str:
    s = str(p or "").strip().replace("\\", "/")
    s = s.lstrip("/")
    parts = [x for x in s.split("/") if x not in ("", ".")]
    if any(x == ".." for x in parts):
        raise ValueError("invalid path")
    return "/".join(parts)


def _normalize_type(t: str) -> str:
    tt = str(t or "").strip().lower()
    if tt in ("directory", "dir", "folder"):
        return "directory"
    return "file"


def _normalize_highlight_color(color: str) -> str:
    c = str(color or "").strip().lower()
    if c not in _ALLOWED_HIGHLIGHT_COLORS:
        raise ValueError("invalid highlight color")
    return c


def _require_workspace_id(workspace_id: str) -> str:
    wid = str(workspace_id or "").strip()
    if not wid:
        raise ValueError("workspace_id is required")
    if not _WORKSPACE_ID_RE.match(wid):
        raise ValueError("invalid workspace_id")
    return wid


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


def _get_legacy_bookmarks_path(base_path: Path) -> Path:
    storage_dir = base_path / "storage"
    bookmarks_dir = storage_dir / BOOKMARKS_DIR_NAME
    bookmarks_dir.mkdir(parents=True, exist_ok=True)
    return bookmarks_dir / BOOKMARKS_FILE_NAME


def _read_all_legacy_bookmarks(base_path: Path) -> List[FsBookmark]:
    path = _get_legacy_bookmarks_path(base_path)
    if not path.exists():
        return []

    items: List[FsBookmark] = []
    try:
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    b = FsBookmark.from_dict(data)
                    if not b.path:
                        continue
                    try:
                        b.path = _normalize_rel_path(b.path)
                    except Exception:
                        continue
                    b.type = _normalize_type(b.type)
                    b.highlight_color = _normalize_highlight_color(b.highlight_color)
                    if not b.pinned_at:
                        b.pinned_at = _now_iso_utc()
                    if not b.highlight_color:
                        b.highlighted_at = ""
                    items.append(b)
                except Exception:
                    continue
    except Exception:
        return []

    return items


def _write_all_legacy_bookmarks(base_path: Path, items: Iterable[FsBookmark]) -> None:
    path = _get_legacy_bookmarks_path(base_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for item in items:
            f.write(json.dumps(asdict(item), ensure_ascii=False))
            f.write("\n")


def _list_legacy(base_path: Path) -> List[Dict[str, Any]]:
    items = _read_all_legacy_bookmarks(base_path)
    items_sorted = sorted(items, key=lambda b: b.pinned_at or "", reverse=True)
    return [asdict(b) for b in items_sorted]


def _toggle_legacy(base_path: Path, path: str, type_: str = "file") -> Tuple[Dict[str, Any], bool]:
    rel = _normalize_rel_path(path)
    tt = _normalize_type(type_)

    items = _read_all_legacy_bookmarks(base_path)
    existing_idx = None
    for i, b in enumerate(items):
        if b.path == rel:
            existing_idx = i
            break

    if existing_idx is not None:
        removed = items.pop(existing_idx)
        _write_all_legacy_bookmarks(base_path, items)
        return asdict(removed), False

    bookmark = FsBookmark(path=rel, type=tt, pinned_at=_now_iso_utc())
    items.append(bookmark)
    _write_all_legacy_bookmarks(base_path, items)
    return asdict(bookmark), True


def _set_highlight_legacy(base_path: Path, path: str, type_: str = "file", color: str = "amber") -> Dict[str, Any]:
    rel = _normalize_rel_path(path)
    tt = _normalize_type(type_)
    cc = _normalize_highlight_color(color or "amber")
    if not cc:
        cc = "amber"

    items = _read_all_legacy_bookmarks(base_path)
    for b in items:
        if b.path == rel:
            b.type = tt
            b.highlight_color = cc
            b.highlighted_at = _now_iso_utc()
            _write_all_legacy_bookmarks(base_path, items)
            return asdict(b)

    bookmark = FsBookmark(
        path=rel,
        type=tt,
        pinned_at=_now_iso_utc(),
        highlight_color=cc,
        highlighted_at=_now_iso_utc(),
    )
    items.append(bookmark)
    _write_all_legacy_bookmarks(base_path, items)
    return asdict(bookmark)


def _clear_highlight_legacy(base_path: Path, path: str) -> Dict[str, Any]:
    rel = _normalize_rel_path(path)

    items = _read_all_legacy_bookmarks(base_path)
    for b in items:
        if b.path == rel:
            b.highlight_color = ""
            b.highlighted_at = ""
            _write_all_legacy_bookmarks(base_path, items)
            return asdict(b)

    raise ValueError("favorite not found")


def _get_workspace_file(base_path: Path, workspace_id: str) -> Path:
    wid = _require_workspace_id(workspace_id)
    return base_path / "storage" / "workspaces" / f"{wid}.json"


def _load_workspace_or_create(base_path: Path, workspace_id: str) -> dict:
    ws_path = _get_workspace_file(base_path, workspace_id)
    if ws_path.exists():
        try:
            with ws_path.open("r", encoding="utf-8") as f:
                return json.load(f) or {}
        except Exception:
            pass

    data = {
        "id": workspace_id,
        "name": workspace_id,
        "description": "",
        "is_default": False,
        "created_at": _now_iso_utc(),
        "last_updated": _now_iso_utc(),
        "state": {"libraries": [], "conversations": [], "files": [], "files_state": {}},
    }
    _atomic_write_json(ws_path, data)
    return data


def _get_state(ws: dict) -> dict:
    st = ws.get("state") if isinstance(ws.get("state"), dict) else {}
    return st if isinstance(st, dict) else {}


def _normalize_favorite_dict(item: Dict[str, Any]) -> Dict[str, Any]:
    b = FsBookmark.from_dict(item)
    b.path = _normalize_rel_path(b.path)
    b.type = _normalize_type(b.type)
    b.highlight_color = _normalize_highlight_color(b.highlight_color)
    if not b.pinned_at:
        b.pinned_at = _now_iso_utc()
    if not b.highlight_color:
        b.highlighted_at = ""
    return asdict(b)


def _ensure_files_state_schema(ws: dict) -> Dict[str, Any]:
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

        normalized_favs = []
        for item in favs:
            if not isinstance(item, dict):
                continue
            try:
                normalized_favs.append(_normalize_favorite_dict(item))
            except Exception:
                continue

        fs[k] = {"focused_root_path": focused, "favorites": normalized_favs}

    if "legacy_favorites_migrated" not in fs:
        fs["legacy_favorites_migrated"] = False

    st["files_state"] = fs
    ws["state"] = st
    return fs


def _extract_current_favorites(fs: dict) -> List[FsBookmark]:
    cur = fs.get("current") if isinstance(fs.get("current"), dict) else {}
    favs = cur.get("favorites")
    if not isinstance(favs, list):
        return []

    out: List[FsBookmark] = []
    for item in favs:
        if not isinstance(item, dict):
            continue
        b = FsBookmark.from_dict(item)
        if not b.path:
            continue
        try:
            b.path = _normalize_rel_path(b.path)
            b.type = _normalize_type(b.type)
            b.highlight_color = _normalize_highlight_color(b.highlight_color)
        except Exception:
            continue
        if not b.pinned_at:
            b.pinned_at = _now_iso_utc()
        if not b.highlight_color:
            b.highlighted_at = ""
        out.append(b)
    return out


def _write_workspace_files_state(base_path: Path, workspace_id: str, ws: dict) -> None:
    ws_path = _get_workspace_file(base_path, workspace_id)
    ws["last_updated"] = _now_iso_utc()
    _atomic_write_json(ws_path, ws)


def _maybe_migrate_legacy_to_workspace(base_path: Path, workspace_id: str, ws: dict) -> None:
    fs = _ensure_files_state_schema(ws)
    if bool(fs.get("legacy_favorites_migrated")):
        return

    cur_items = _extract_current_favorites(fs)
    if cur_items:
        fs["legacy_favorites_migrated"] = True
        _write_workspace_files_state(base_path, workspace_id, ws)
        return

    legacy = _read_all_legacy_bookmarks(base_path)
    legacy_dicts = [asdict(x) for x in sorted(legacy, key=lambda b: b.pinned_at or "", reverse=True)]

    fs["saved"]["favorites"] = legacy_dicts
    fs["current"]["favorites"] = legacy_dicts
    fs["saved_at"] = _now_iso_utc()
    fs["legacy_favorites_migrated"] = True

    _write_workspace_files_state(base_path, workspace_id, ws)


def _list_workspace(base_path: Path, workspace_id: str) -> List[Dict[str, Any]]:
    ws = _load_workspace_or_create(base_path, workspace_id)
    _maybe_migrate_legacy_to_workspace(base_path, workspace_id, ws)

    fs = _ensure_files_state_schema(ws)
    items = _extract_current_favorites(fs)
    items_sorted = sorted(items, key=lambda b: b.pinned_at or "", reverse=True)
    return [asdict(b) for b in items_sorted]


def _toggle_workspace(base_path: Path, workspace_id: str, path: str, type_: str = "file") -> Tuple[Dict[str, Any], bool]:
    rel = _normalize_rel_path(path)
    tt = _normalize_type(type_)

    ws = _load_workspace_or_create(base_path, workspace_id)
    fs = _ensure_files_state_schema(ws)

    items = _extract_current_favorites(fs)

    existing_idx = None
    for i, b in enumerate(items):
        if b.path == rel:
            existing_idx = i
            break

    if existing_idx is not None:
        removed = items.pop(existing_idx)
        fs["current"]["favorites"] = [asdict(x) for x in sorted(items, key=lambda b: b.pinned_at or "", reverse=True)]
        _write_workspace_files_state(base_path, workspace_id, ws)
        return asdict(removed), False

    bookmark = FsBookmark(path=rel, type=tt, pinned_at=_now_iso_utc())
    items.append(bookmark)
    fs["current"]["favorites"] = [asdict(x) for x in sorted(items, key=lambda b: b.pinned_at or "", reverse=True)]
    _write_workspace_files_state(base_path, workspace_id, ws)
    return asdict(bookmark), True


def _set_highlight_workspace(base_path: Path, workspace_id: str, path: str, type_: str = "file", color: str = "amber") -> Dict[str, Any]:
    rel = _normalize_rel_path(path)
    tt = _normalize_type(type_)
    cc = _normalize_highlight_color(color or "amber")
    if not cc:
        cc = "amber"

    ws = _load_workspace_or_create(base_path, workspace_id)
    fs = _ensure_files_state_schema(ws)

    items = _extract_current_favorites(fs)
    for b in items:
        if b.path == rel:
            b.type = tt
            b.highlight_color = cc
            b.highlighted_at = _now_iso_utc()
            fs["current"]["favorites"] = [asdict(x) for x in sorted(items, key=lambda item: item.pinned_at or "", reverse=True)]
            _write_workspace_files_state(base_path, workspace_id, ws)
            return asdict(b)

    bookmark = FsBookmark(
        path=rel,
        type=tt,
        pinned_at=_now_iso_utc(),
        highlight_color=cc,
        highlighted_at=_now_iso_utc(),
    )
    items.append(bookmark)
    fs["current"]["favorites"] = [asdict(x) for x in sorted(items, key=lambda item: item.pinned_at or "", reverse=True)]
    _write_workspace_files_state(base_path, workspace_id, ws)
    return asdict(bookmark)


def _clear_highlight_workspace(base_path: Path, workspace_id: str, path: str) -> Dict[str, Any]:
    rel = _normalize_rel_path(path)

    ws = _load_workspace_or_create(base_path, workspace_id)
    fs = _ensure_files_state_schema(ws)

    items = _extract_current_favorites(fs)
    for b in items:
        if b.path == rel:
            b.highlight_color = ""
            b.highlighted_at = ""
            fs["current"]["favorites"] = [asdict(x) for x in sorted(items, key=lambda item: item.pinned_at or "", reverse=True)]
            _write_workspace_files_state(base_path, workspace_id, ws)
            return asdict(b)

    raise ValueError("favorite not found")


@auto_user_context
def nisb_favorites_list_files(args: dict) -> dict:
    user_ctx = get_user_ctx()
    base_path = Path(user_ctx.base)

    workspace_id = str(args.get("workspace_id", "") or "").strip()
    if workspace_id:
        try:
            items = _list_workspace(base_path, workspace_id)
            return {"success": True, "items": items, "workspace_id": workspace_id}
        except Exception as e:
            return {"success": False, "message": f"list failed: {e}", "workspace_id": workspace_id}

    items = _list_legacy(base_path)
    return {"success": True, "items": items, "workspace_id": ""}


@auto_user_context
def nisb_favorites_toggle_file(args: dict) -> dict:
    user_ctx = get_user_ctx()
    base_path = Path(user_ctx.base)

    path = str(args.get("path", "")).strip()
    type_ = str(args.get("type", "file") or "file")
    workspace_id = str(args.get("workspace_id", "") or "").strip()

    if not path:
        return {"success": False, "message": "path is required"}

    try:
        if workspace_id:
            item, pinned = _toggle_workspace(base_path, workspace_id, path=path, type_=type_)
            return {"success": True, "item": item, "pinned": pinned, "workspace_id": workspace_id}

        item, pinned = _toggle_legacy(base_path, path=path, type_=type_)
        return {"success": True, "item": item, "pinned": pinned, "workspace_id": ""}
    except Exception as e:
        return {"success": False, "message": f"toggle failed: {e}", "workspace_id": workspace_id}


@auto_user_context
def nisb_favorites_set_highlight(args: dict) -> dict:
    user_ctx = get_user_ctx()
    base_path = Path(user_ctx.base)

    path = str(args.get("path", "")).strip()
    type_ = str(args.get("type", "file") or "file")
    color = str(args.get("color", "amber") or "amber")
    workspace_id = str(args.get("workspace_id", "") or "").strip()

    if not path:
        return {"success": False, "message": "path is required", "workspace_id": workspace_id}

    try:
        if workspace_id:
            item = _set_highlight_workspace(
                base_path,
                workspace_id=workspace_id,
                path=path,
                type_=type_,
                color=color,
            )
            return {"success": True, "item": item, "highlighted": True, "workspace_id": workspace_id}

        item = _set_highlight_legacy(base_path, path=path, type_=type_, color=color)
        return {"success": True, "item": item, "highlighted": True, "workspace_id": ""}
    except Exception as e:
        return {"success": False, "message": f"set highlight failed: {e}", "workspace_id": workspace_id}


@auto_user_context
def nisb_favorites_clear_highlight(args: dict) -> dict:
    user_ctx = get_user_ctx()
    base_path = Path(user_ctx.base)

    path = str(args.get("path", "")).strip()
    workspace_id = str(args.get("workspace_id", "") or "").strip()

    if not path:
        return {"success": False, "message": "path is required", "workspace_id": workspace_id}

    try:
        if workspace_id:
            item = _clear_highlight_workspace(base_path, workspace_id=workspace_id, path=path)
            return {"success": True, "item": item, "highlighted": False, "workspace_id": workspace_id}

        item = _clear_highlight_legacy(base_path, path=path)
        return {"success": True, "item": item, "highlighted": False, "workspace_id": ""}
    except Exception as e:
        return {"success": False, "message": f"clear highlight failed: {e}", "workspace_id": workspace_id}
