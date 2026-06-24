#!/usr/bin/env python3
"""
NISB Libraries Manager.

This module manages user libraries, keeps legacy metadata compatible, and
localizes only user-visible tool envelope text. User data, IDs, paths, protocol
fields, and statistics remain unchanged.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

sys.path.insert(0, "/srv")

from core.user_context import auto_user_context, get_user_ctx
from tools.doc.doc_db_sqlite import get_doc_db_sqlite
from tools.i18n.backend_i18n import i18n_text, normalize_backend_locale


def _now_iso() -> str:
    return datetime.now().isoformat()


def _safe_args(args: Dict[str, Any] | None) -> Dict[str, Any]:
    return args if isinstance(args, dict) else {}


def _arg_str(args: Dict[str, Any], key: str, default: str = "") -> str:
    return str(args.get(key, default) or "").strip()


def _locale(args: Dict[str, Any] | None) -> str:
    return normalize_backend_locale(_safe_args(args).get("locale"))


def _txt(args: Dict[str, Any] | None, en: str, zh: str) -> str:
    return i18n_text(_locale(args), {"en": en, "zh-CN": zh}, en)


def _txt_locale(locale: Any, en: str, zh: str) -> str:
    return i18n_text(normalize_backend_locale(locale), {"en": en, "zh-CN": zh}, en)


def _fmt(args: Dict[str, Any] | None, en: str, zh: str, **kwargs: Any) -> str:
    return _txt(args, en, zh).format(**kwargs)


def _tool_entry(kind: str, data: Dict[str, Any] | None = None) -> Dict[str, Any]:
    return {"kind": kind, "data": data or {}}


def _ok(
    kind: str,
    message: str = "",
    *,
    tool_data: Dict[str, Any] | None = None,
    **fields: Any,
) -> Dict[str, Any]:
    out: Dict[str, Any] = {
        "status": "success",
        "success": True,
    }

    if message:
        out["message"] = message
        out["response"] = message
        out["tool_results"] = [_tool_entry(kind, tool_data or {})]

    out.update(fields)
    return out


def _err(
    kind: str,
    message: str,
    *,
    tool_data: Dict[str, Any] | None = None,
    **fields: Any,
) -> Dict[str, Any]:
    out: Dict[str, Any] = {
        "status": "error",
        "success": False,
        "message": message,
        "response": message,
        "tool_results": [_tool_entry(kind, tool_data or {})],
    }
    out.update(fields)
    return out


def _safe_write_json(path: Path, data: dict) -> None:
    import tempfile

    path.parent.mkdir(parents=True, exist_ok=True)

    tmp = tempfile.NamedTemporaryFile(
        mode="w",
        delete=False,
        encoding="utf-8",
        dir=str(path.parent),
        prefix=f".{path.name}.tmp.",
    )
    try:
        json.dump(data, tmp, ensure_ascii=False, indent=2)
        tmp.flush()
        os.fsync(tmp.fileno())
        tmp.close()
        os.replace(tmp.name, str(path))
    except Exception:
        try:
            tmp.close()
        except Exception:
            pass
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    finally:
        try:
            if os.path.exists(tmp.name):
                os.remove(tmp.name)
        except Exception:
            pass


def _default_library_name_from_id(library_id: str, locale: Any = None) -> str:
    s = str(library_id or "").strip()
    if s:
        return s
    return _txt_locale(locale, "Untitled library", "未命名库")


def _pick_library_name(meta: dict, library_id: str, locale: Any = None) -> str:
    if not isinstance(meta, dict):
        return _default_library_name_from_id(library_id, locale)

    for key in (
        "library_name",
        "name",
        "title",
        "display_name",
        "displayName",
        "lib_name",
    ):
        value = meta.get(key)
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text

    return _default_library_name_from_id(library_id, locale)


def _fallback_doc_count_from_dir(library_path: Path) -> int:
    docs_dir = library_path / "docs"
    if not docs_dir.exists():
        return 0
    try:
        return sum(1 for p in docs_dir.iterdir() if p.is_dir() and p.name.startswith("doc_"))
    except Exception:
        return 0


def _ensure_library_meta_shape(meta: dict, *, library_id: str, locale: Any = None) -> dict:
    if not isinstance(meta, dict):
        meta = {}

    if meta.get("library_id") != library_id:
        meta["library_id"] = library_id

    resolved_name = _pick_library_name(meta, library_id, locale)
    meta["library_name"] = resolved_name

    meta.setdefault("description", "")
    meta.setdefault("icon", "📚")
    meta.setdefault("color", "#3B82F6")
    meta.setdefault("created_at", _now_iso())
    meta.setdefault("last_updated", meta.get("updated_at") or meta.get("created_at") or _now_iso())
    meta.setdefault("doc_count", 0)
    meta.setdefault("concept_count", 0)
    meta.setdefault("relation_count", 0)

    stats = meta.get("stats")
    if not isinstance(stats, dict):
        stats = {}

    stats.setdefault("doc_count", int(meta.get("doc_count", 0) or 0))
    stats.setdefault("total_chunks", 0)
    stats.setdefault("total_size_mb", 0)
    stats.setdefault("embedding_coverage", "0/0")
    stats.setdefault("embedding_pct", 0)
    stats.setdefault("embedded_docs", 0)
    stats.setdefault("concept_count", int(meta.get("concept_count", 0) or 0))
    stats.setdefault("relation_count", int(meta.get("relation_count", 0) or 0))

    meta["stats"] = stats
    return meta


def _load_library_meta(library_path: Path, library_id: str, locale: Any = None) -> dict:
    meta_file = library_path / "library.json"
    meta: Dict[str, Any] = {}

    if meta_file.exists():
        try:
            with open(meta_file, "r", encoding="utf-8") as f:
                loaded = json.load(f)
                if isinstance(loaded, dict):
                    meta = loaded
        except Exception:
            meta = {}

    return _ensure_library_meta_shape(meta, library_id=library_id, locale=locale)


def _count_relations(relations_dir: Path) -> int:
    relation_count = 0
    if relations_dir.exists():
        for rel_file in relations_dir.glob("*.jsonl"):
            try:
                with open(rel_file, "r", encoding="utf-8") as f:
                    relation_count += sum(1 for _ in f)
            except Exception:
                continue
    return relation_count


def _sqlite_library_stats(base_path: str, library_id: str) -> dict:
    db = get_doc_db_sqlite(base_path, library_id)
    compat = db.ensure_schema_compatible()
    db_stats = db.get_statistics()
    return {
        "compat": compat,
        "doc_count": int(db_stats.get("total_docs", 0) or 0),
        "total_chunks": int(db_stats.get("total_chunks", 0) or 0),
        "embedded_docs": int(db_stats.get("embedded_docs", 0) or 0),
        "embedding_coverage": db_stats.get("embedding_coverage", "0/0"),
        "embedding_pct": db_stats.get("embedding_pct", 0),
    }


@auto_user_context
def nisb_library_create(args: dict) -> dict:
    args = _safe_args(args)
    kind = "nisb_library_create"
    user_ctx = get_user_ctx()

    library_id = _arg_str(args, "library_id")
    library_name = _arg_str(args, "library_name")
    description = args.get("description", "")
    icon = args.get("icon", "📚")
    color = args.get("color", "#3B82F6")

    if not library_id or not library_name:
        return _err(
            kind,
            _txt(args, "❌ library_id and library_name cannot be empty", "❌ library_id 和 library_name 不能为空"),
            tool_data={"library_id": library_id, "library_name": library_name, "reason": "missing_required_fields"},
        )

    library_path = Path(user_ctx.base) / "libraries" / library_id

    if library_path.exists():
        return _err(
            kind,
            _fmt(args, "❌ Library already exists: {library_id}", "❌ 库已存在：{library_id}", library_id=library_id),
            tool_data={"library_id": library_id, "reason": "library_exists"},
            library_id=library_id,
        )

    (library_path / "docs").mkdir(parents=True, exist_ok=True)
    (library_path / "entities").mkdir(exist_ok=True)
    (library_path / "relations").mkdir(exist_ok=True)
    (library_path / "index").mkdir(exist_ok=True)
    (library_path / "metadata").mkdir(exist_ok=True)
    (library_path / "analytics").mkdir(exist_ok=True)

    now = _now_iso()

    library_meta = {
        "library_id": library_id,
        "library_name": library_name,
        "description": description,
        "icon": icon,
        "color": color,
        "created_at": now,
        "last_updated": now,
        "doc_count": 0,
        "concept_count": 0,
        "relation_count": 0,
        "stats": {
            "doc_count": 0,
            "total_chunks": 0,
            "total_size_mb": 0,
            "embedding_coverage": "0/0",
            "embedding_pct": 0,
            "embedded_docs": 0,
            "concept_count": 0,
            "relation_count": 0,
        },
    }

    _safe_write_json(library_path / "library.json", library_meta)

    message = _fmt(args, "✅ Library created: {library_name}", "✅ 库创建成功：{library_name}", library_name=library_name)
    return _ok(
        kind,
        message,
        tool_data={"library_id": library_id, "library_path": str(library_path)},
        library_id=library_id,
        library_path=str(library_path),
    )


@auto_user_context
def nisb_library_list(args: dict) -> dict:
    args = _safe_args(args)
    user_ctx = get_user_ctx()
    libraries_root = Path(user_ctx.base) / "libraries"

    if not libraries_root.exists():
        return _ok("nisb_library_list", libraries=[], total=0)

    libraries = []

    for lib_dir in libraries_root.iterdir():
        if not lib_dir.is_dir():
            continue

        library_id = lib_dir.name
        meta_file = lib_dir / "library.json"

        try:
            meta = _load_library_meta(lib_dir, library_id, _locale(args))

            doc_count = int(meta.get("doc_count", 0) or 0)
            concept_count = int(meta.get("concept_count", 0) or 0)
            stats = meta.get("stats", {})
            if isinstance(stats, dict):
                doc_count = int(stats.get("doc_count", doc_count) or doc_count)
                concept_count = int(stats.get("concept_count", concept_count) or concept_count)

            if doc_count <= 0:
                doc_count = _fallback_doc_count_from_dir(lib_dir)

            meta["doc_count"] = doc_count
            meta["concept_count"] = concept_count
            if isinstance(meta.get("stats"), dict):
                meta["stats"]["doc_count"] = doc_count
                meta["stats"]["concept_count"] = concept_count

            _safe_write_json(meta_file, meta)

            libraries.append(
                {
                    "library_id": library_id,
                    "library_name": _pick_library_name(meta, library_id, _locale(args)),
                    "description": meta.get("description", ""),
                    "icon": meta.get("icon", "📚"),
                    "color": meta.get("color", "#3B82F6"),
                    "created_at": meta.get("created_at"),
                    "last_updated": meta.get("last_updated") or meta.get("updated_at"),
                    "doc_count": doc_count,
                    "concept_count": concept_count,
                }
            )

        except Exception as e:
            print(f"[WARN] Failed to read library metadata: {lib_dir.name} - {e}", file=sys.stderr)
            libraries.append(
                {
                    "library_id": library_id,
                    "library_name": _default_library_name_from_id(library_id, _locale(args)),
                    "description": "",
                    "icon": "📚",
                    "color": "#3B82F6",
                    "created_at": None,
                    "last_updated": None,
                    "doc_count": _fallback_doc_count_from_dir(lib_dir),
                    "concept_count": 0,
                }
            )

    libraries.sort(key=lambda x: str(x.get("last_updated") or ""), reverse=True)
    return _ok("nisb_library_list", libraries=libraries, total=len(libraries))


@auto_user_context
def nisb_library_delete(args: dict) -> dict:
    args = _safe_args(args)
    kind = "nisb_library_delete"
    user_ctx = get_user_ctx()

    library_id = _arg_str(args, "library_id")

    if not library_id:
        return _err(
            kind,
            _txt(args, "❌ library_id cannot be empty", "❌ library_id 不能为空"),
            tool_data={"library_id": library_id, "reason": "missing_library_id"},
        )

    library_path = Path(user_ctx.base) / "libraries" / library_id

    if not library_path.exists():
        return _err(
            kind,
            _fmt(args, "❌ Library does not exist: {library_id}", "❌ 库不存在：{library_id}", library_id=library_id),
            tool_data={"library_id": library_id, "reason": "library_not_found"},
            library_id=library_id,
        )

    meta_file = library_path / "library.json"
    library_name = library_id

    if meta_file.exists():
        try:
            with open(meta_file, "r", encoding="utf-8") as f:
                meta = json.load(f)
            library_name = _pick_library_name(meta, library_id, _locale(args))
        except Exception:
            pass

    import shutil

    shutil.rmtree(library_path)

    message = _fmt(args, "✅ Library deleted: {library_name}", "✅ 已删除库：{library_name}", library_name=library_name)
    return _ok(
        kind,
        message,
        tool_data={"library_id": library_id, "library_name": library_name},
        library_id=library_id,
        library_name=library_name,
    )


@auto_user_context
def nisb_library_stats(args: dict) -> dict:
    args = _safe_args(args)
    kind = "nisb_library_stats"
    user_ctx = get_user_ctx()

    library_id = _arg_str(args, "library_id")

    if not library_id:
        return _err(
            kind,
            _txt(args, "❌ library_id cannot be empty", "❌ library_id 不能为空"),
            tool_data={"library_id": library_id, "reason": "missing_library_id"},
        )

    library_path = Path(user_ctx.base) / "libraries" / library_id

    if not library_path.exists():
        return _err(
            kind,
            _fmt(args, "❌ Library does not exist: {library_id}", "❌ 库不存在：{library_id}", library_id=library_id),
            tool_data={"library_id": library_id, "reason": "library_not_found"},
            library_id=library_id,
        )

    meta_file = library_path / "library.json"
    meta = _load_library_meta(library_path, library_id, _locale(args))

    entities_dir = library_path / "entities"
    relations_dir = library_path / "relations"

    concept_count = len(list(entities_dir.glob("*.json"))) if entities_dir.exists() else 0
    relation_count = _count_relations(relations_dir)

    sqlite_stats = {
        "doc_count": 0,
        "total_chunks": 0,
        "embedded_docs": 0,
        "embedding_coverage": "0/0",
        "embedding_pct": 0,
    }
    sqlite_error = None

    try:
        docs_db_path = library_path / "docs" / "doc_db.sqlite"
        if docs_db_path.exists():
            sqlite_stats = _sqlite_library_stats(str(user_ctx.base), library_id)
        else:
            sqlite_stats["doc_count"] = _fallback_doc_count_from_dir(library_path)
    except Exception as e:
        sqlite_error = str(e)
        sqlite_stats["doc_count"] = _fallback_doc_count_from_dir(library_path)

    meta["doc_count"] = int(sqlite_stats.get("doc_count", 0) or 0)
    meta["concept_count"] = concept_count
    meta["relation_count"] = relation_count
    meta["last_updated"] = meta.get("last_updated") or meta.get("updated_at") or meta.get("created_at")
    meta["library_name"] = _pick_library_name(meta, library_id, _locale(args))

    meta["stats"] = {
        **meta.get("stats", {}),
        **{
            "doc_count": int(sqlite_stats.get("doc_count", 0) or 0),
            "total_chunks": int(sqlite_stats.get("total_chunks", 0) or 0),
            "embedded_docs": int(sqlite_stats.get("embedded_docs", 0) or 0),
            "embedding_coverage": sqlite_stats.get("embedding_coverage", "0/0"),
            "embedding_pct": sqlite_stats.get("embedding_pct", 0),
            "concept_count": concept_count,
            "relation_count": relation_count,
        },
    }

    _safe_write_json(meta_file, meta)

    return _ok(
        kind,
        stats={
            "library_id": library_id,
            "library_name": _pick_library_name(meta, library_id, _locale(args)),
            "doc_count": meta["stats"].get("doc_count", 0),
            "total_chunks": meta["stats"].get("total_chunks", 0),
            "embedded_docs": meta["stats"].get("embedded_docs", 0),
            "embedding_coverage": meta["stats"].get("embedding_coverage", "0/0"),
            "embedding_pct": meta["stats"].get("embedding_pct", 0),
            "concept_count": concept_count,
            "relation_count": relation_count,
            "created_at": meta.get("created_at"),
            "last_updated": meta.get("last_updated"),
            "sqlite_error": sqlite_error,
        },
    )


@auto_user_context
def nisb_library_get_info(args: dict) -> dict:
    args = _safe_args(args)
    kind = "nisb_library_get_info"
    user_ctx = get_user_ctx()

    library_id = _arg_str(args, "library_id")

    if not library_id:
        return _err(
            kind,
            _txt(args, "❌ library_id cannot be empty", "❌ library_id 不能为空"),
            tool_data={"library_id": library_id, "reason": "missing_library_id"},
        )

    library_path = Path(user_ctx.base) / "libraries" / library_id

    if not library_path.exists():
        return _err(
            kind,
            _fmt(args, "❌ Library does not exist: {library_id}", "❌ 库不存在：{library_id}", library_id=library_id),
            tool_data={"library_id": library_id, "reason": "library_not_found"},
            library_id=library_id,
        )

    meta_file = library_path / "library.json"
    meta = _load_library_meta(library_path, library_id, _locale(args))

    stats_args = dict(args)
    stats_args["library_id"] = library_id
    stats_args["locale"] = _locale(args)

    stats_result = nisb_library_stats(stats_args)
    stats = stats_result.get("stats", {}) if isinstance(stats_result, dict) else {}

    meta["library_name"] = _pick_library_name(meta, library_id, _locale(args))
    meta["doc_count"] = stats.get("doc_count", meta.get("doc_count", 0))
    meta["concept_count"] = stats.get("concept_count", meta.get("concept_count", 0))
    meta["relation_count"] = stats.get("relation_count", meta.get("relation_count", 0))
    meta["stats"] = {
        **meta.get("stats", {}),
        **{
            "doc_count": stats.get("doc_count", 0),
            "total_chunks": stats.get("total_chunks", 0),
            "embedded_docs": stats.get("embedded_docs", 0),
            "embedding_coverage": stats.get("embedding_coverage", "0/0"),
            "embedding_pct": stats.get("embedding_pct", 0),
            "concept_count": stats.get("concept_count", 0),
            "relation_count": stats.get("relation_count", 0),
        },
    }

    _safe_write_json(meta_file, meta)

    return _ok(kind, info=meta)


@auto_user_context
def nisb_library_rename(args: dict) -> dict:
    args = _safe_args(args)
    kind = "nisb_library_rename"
    user_ctx = get_user_ctx()

    library_id = _arg_str(args, "library_id")
    new_name = _arg_str(args, "new_name")

    if not library_id or not new_name:
        return _err(
            kind,
            _txt(args, "❌ library_id and new_name cannot be empty", "❌ library_id 和 new_name 不能为空"),
            tool_data={"library_id": library_id, "new_name": new_name, "reason": "missing_required_fields"},
        )

    library_path = Path(user_ctx.base) / "libraries" / library_id

    if not library_path.exists():
        return _err(
            kind,
            _fmt(args, "❌ Library does not exist: {library_id}", "❌ 库不存在：{library_id}", library_id=library_id),
            tool_data={"library_id": library_id, "reason": "library_not_found"},
            library_id=library_id,
        )

    meta_file = library_path / "library.json"
    meta = _load_library_meta(library_path, library_id, _locale(args))

    old_name = _pick_library_name(meta, library_id, _locale(args))
    meta["library_name"] = new_name
    meta["last_updated"] = _now_iso()

    _safe_write_json(meta_file, meta)

    message = _fmt(args, "✅ Renamed: {old_name} → {new_name}", "✅ 已重命名：{old_name} → {new_name}", old_name=old_name, new_name=new_name)
    return _ok(
        kind,
        message,
        tool_data={"library_id": library_id, "old_name": old_name, "new_name": new_name},
        library_id=library_id,
        old_name=old_name,
        new_name=new_name,
    )


class LibraryManager:
    """
    Backward-compatible library manager.

    Supported historical constructor forms:
    - LibraryManager(base_path, user_id)
    - LibraryManager(user_id, base_path)
    """

    def __init__(self, base_path: str = "/data", user_id: str = "", locale: str = "en"):
        base_candidate = str(base_path or "")
        user_candidate = str(user_id or "")

        if base_candidate and not os.path.isabs(base_candidate) and user_candidate and os.path.isabs(user_candidate):
            base_candidate, user_candidate = user_candidate, base_candidate

        self.base_path = Path(base_candidate or "/data")
        self.libraries_root = self.base_path / "libraries"
        self.user_id = user_candidate
        self.locale = normalize_backend_locale(locale)

    def library_exists(self, library_id: str) -> bool:
        lib_path = self.libraries_root / library_id
        return lib_path.exists() and lib_path.is_dir()

    def get_library_path(self, library_id: str) -> Path:
        return self.libraries_root / library_id

    def get_library_meta(self, library_id: str) -> dict:
        lib_path = self.get_library_path(library_id)
        if not lib_path.exists() or not lib_path.is_dir():
            return {}
        try:
            return _load_library_meta(lib_path, library_id=library_id, locale=self.locale)
        except Exception as e:
            print(f"[WARN] Failed to read metadata for library {library_id}: {e}", file=sys.stderr)
            return {}

    def update_library_stats(self, library_id: str, stats: dict) -> bool:
        lib_path = self.get_library_path(library_id)
        if not lib_path.exists() or not lib_path.is_dir():
            return False

        meta_file = lib_path / "library.json"

        try:
            meta = _load_library_meta(lib_path, library_id=library_id, locale=self.locale)

            if "doc_count" in stats:
                meta["doc_count"] = stats["doc_count"]
            if "concept_count" in stats:
                meta["concept_count"] = stats["concept_count"]
            if "relation_count" in stats:
                meta["relation_count"] = stats["relation_count"]

            meta["stats"].update(stats)
            meta["last_updated"] = _now_iso()

            _safe_write_json(meta_file, meta)

            return True
        except Exception as e:
            print(f"[WARN] Failed to update statistics for library {library_id}: {e}", file=sys.stderr)
            return False

    def get_library_info(self, library_id: str, locale: str | None = None) -> dict:
        selected_locale = normalize_backend_locale(locale or self.locale)
        args = {"locale": selected_locale}

        if not self.library_exists(library_id):
            return _err(
                "nisb_library_get_info",
                _txt_locale(selected_locale, "❌ Library does not exist: {library_id}", "❌ 库不存在：{library_id}").format(library_id=library_id),
                tool_data={"library_id": library_id, "reason": "library_not_found"},
            )

        meta = self.get_library_meta(library_id)
        if not meta:
            return _err(
                "nisb_library_get_info",
                _txt(args, "❌ Library metadata file does not exist or is corrupted", "❌ 库元信息文件不存在或损坏"),
                tool_data={"library_id": library_id, "reason": "metadata_missing_or_corrupted"},
            )

        return _ok("nisb_library_get_info", info=meta)

    def _update_global_config(self):
        pass
