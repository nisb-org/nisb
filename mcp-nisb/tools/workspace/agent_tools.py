#!/usr/bin/env python3
from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any, Dict, List, Tuple

from tools.filesystem.guarded_tools import (
    nisb_file_create as fs_file_create,
    nisb_file_read as fs_file_read,
    nisb_file_update as fs_file_update,
    nisb_file_delete as fs_file_delete,
    nisb_file_rename as fs_file_rename,
    nisb_dir_create as fs_dir_create,
    nisb_dir_delete as fs_dir_delete,
    nisb_dir_delete_recursive as fs_dir_delete_recursive,
    nisb_dir_move_path as fs_dir_move_path,
)

from .common import (
    auto_user_context,
    get_user_ctx,
    _ok,
    _err,
    _coerce_bool,
    _coerce_int,
    _normalize_rel_path,
    _normalize_rel_path_strict,
    _normalize_md_filename,
    _require_safe_agent_id,
    _load_workspace_file_or_create,
    _ensure_files_state_schema,
    _resolve_focus_root_scope,
    _resolve_under_root,
    _is_text_file,
    _read_text_file,
    _chunk_text,
    _score_text_match,
    _write_jsonl,
    _load_jsonl,
    _atomic_write_json,
    _upsert_md_section,
    _now_iso_utc,
)


def _user_hidden_args(user_ctx) -> Dict[str, Any]:
    user_id = (
        getattr(user_ctx, "user_id", None)
        or getattr(user_ctx, "userid", None)
        or getattr(user_ctx, "uid", None)
        or ""
    )
    email = getattr(user_ctx, "email", None) or ""
    name = getattr(user_ctx, "name", None) or ""
    return {
        "user_id": str(user_id or "").strip(),
        "_user_id": str(user_id or "").strip(),
        "_librechat_email": str(email or "").strip(),
        "_librechat_name": str(name or "").strip(),
    }


def _workspace_effective_focus_root(ws: dict, explicit_focus_root: Any) -> Tuple[str, str]:
    explicit = _normalize_rel_path(str(explicit_focus_root or "").strip())
    if explicit:
        return explicit, "explicit"

    files_state = _ensure_files_state_schema(ws)

    current_box = files_state.get("current") if isinstance(files_state.get("current"), dict) else {}
    saved_box = files_state.get("saved") if isinstance(files_state.get("saved"), dict) else {}

    current_focus = _normalize_rel_path(str(current_box.get("focused_root_path") or "").strip())
    if current_focus:
        return current_focus, "current"

    saved_focus = _normalize_rel_path(str(saved_box.get("focused_root_path") or "").strip())
    if saved_focus:
        return saved_focus, "saved"

    return "", "workspace_root"


def _resolve_room_scope(
    user_ctx,
    workspace_id: str,
    focus_root: Any,
    require_exists: bool = True,
) -> Tuple[str, dict, Path, str, Path, str, str]:
    _, ws = _load_workspace_file_or_create(user_ctx, workspace_id)
    effective_focus_root, focus_source = _workspace_effective_focus_root(ws, focus_root)

    wid, ws2, workspace_root, normalized_focus_root, scope_root, scope_kind = _resolve_focus_root_scope(
        user_ctx=user_ctx,
        workspace_id=workspace_id,
        focus_root=effective_focus_root,
        require_exists=require_exists,
    )
    return wid, ws2, workspace_root, normalized_focus_root, scope_root, scope_kind, focus_source


def _scope_index_dir(workspace_root: Path) -> Path:
    return workspace_root / ".nisb_index"


def _scope_key_local(focus_root: str) -> str:
    import hashlib
    raw = focus_root or "__workspace_root__"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:12]


def _scoped_global_rel_path(focus_root: str, relative_path: Any, allow_empty: bool = False) -> str:
    rel = _normalize_rel_path_strict(relative_path)
    if not rel and not allow_empty:
        raise ValueError("relative_path 不能为空")
    if focus_root and rel:
        return _normalize_rel_path(f"{focus_root}/{rel}")
    if focus_root and not rel:
        return focus_root
    return rel


def _local_parent_rel(rel_path: str) -> str:
    p = Path(rel_path)
    parent = p.parent.as_posix()
    return "" if parent == "." else parent


def _build_capability_gate(args: Dict[str, Any], workspace_id: str, focus_root: str) -> Dict[str, Any]:
    raw = args.get("capability_gate")
    gate = dict(raw) if isinstance(raw, dict) else {}

    return {
        "policy_version": int(gate.get("policy_version") or 1),
        "workspace_id": workspace_id,
        "focus_root": focus_root,
        "fs_read_scope": str(gate.get("fs_read_scope") or "minimal").strip(),
        "fs_write_scope": str(gate.get("fs_write_scope") or "agent_files").strip(),
        "fs_dangerous_enabled": bool(
            gate["fs_dangerous_enabled"] if "fs_dangerous_enabled" in gate else True
        ),
    }


def _fs_args(
    *,
    base_args: Dict[str, Any],
    user_ctx,
    capability_gate: Dict[str, Any],
    updates: Dict[str, Any],
) -> Dict[str, Any]:
    out = {}
    out.update(_user_hidden_args(user_ctx))
    out["request_id"] = str(base_args.get("request_id") or "").strip()
    out["capability_gate"] = capability_gate
    out.update(updates)
    return out


def _safe_token(value: Any, default_value: str) -> str:
    s = str(value or "").strip()
    if not s:
        s = default_value
    s = re.sub(r"[^A-Za-z0-9_-]+", "_", s).strip("_")
    return s or default_value


def _default_timestamp_title() -> str:
    iso = _now_iso_utc().replace("T", " ")
    return iso[:16]


def _ensure_markdown_rel_path(raw_value: Any, default_dir: str, default_filename: str) -> str:
    raw = str(raw_value or "").strip().replace("\\", "/").lstrip("/")
    if not raw:
        filename = _normalize_md_filename("", default_filename)
        return f"{default_dir}/{filename}" if default_dir else filename

    if "/" not in raw:
        filename = _normalize_md_filename(raw, default_filename)
        return f"{default_dir}/{filename}" if default_dir else filename

    norm = _normalize_rel_path_strict(raw)
    p = Path(norm)
    parent = p.parent.as_posix()
    if parent == ".":
        parent = ""
    filename = _normalize_md_filename(p.name, default_filename)
    return f"{parent}/{filename}" if parent else filename


def _room_note_local_rel(args: Dict[str, Any]) -> str:
    room_token = _safe_token(args.get("room_id"), "room")
    save_as = args.get("save_as") or args.get("filename") or args.get("relative_path")
    return _ensure_markdown_rel_path(save_as, "_room_notes", f"{room_token}.md")


def _agent_notebook_local_rel(args: Dict[str, Any]) -> str:
    agent_id = _require_safe_agent_id(str(args.get("agent_id") or args.get("role_id") or "agent").strip())
    notebook_dir_rel = _normalize_rel_path(str(args.get("notebook_dir") or "_room_notebooks").strip())
    filename = _normalize_md_filename(str(args.get("filename") or "").strip(), f"{agent_id}.md")
    return f"{notebook_dir_rel}/{filename}" if notebook_dir_rel else filename


def _note_title(args: Dict[str, Any], default_value: str) -> str:
    title = str(args.get("title") or "").strip()
    if title:
        return title
    return default_value


def _note_section_title(args: Dict[str, Any], default_value: str = "") -> str:
    section_title = str(args.get("section_title") or "").strip()
    if section_title:
        return section_title
    return default_value or _default_timestamp_title()


def _ensure_parent_dir(
    *,
    base_args: Dict[str, Any],
    user_ctx,
    gate: Dict[str, Any],
    local_file_rel: str,
    focus_root: str,
) -> None:
    parent = _local_parent_rel(local_file_rel)
    if not parent:
        return

    global_parent = _scoped_global_rel_path(focus_root, parent)
    result = fs_dir_create(_fs_args(
        base_args=base_args,
        user_ctx=user_ctx,
        capability_gate=gate,
        updates={"path": global_parent},
    ))
    if not result.get("success"):
        raise RuntimeError(result.get("message") or "创建父目录失败")


def _render_room_note(existing: str, title: str, section_title: str, body_md: str, mode: str) -> str:
    body_clean = str(body_md or "").strip()
    stamped_body = f"_updated_at: {_now_iso_utc()}_\n\n{body_clean}" if body_clean else f"_updated_at: {_now_iso_utc()}_"

    if mode == "overwrite":
        parts = [f"# {title}", ""]
        if section_title:
            parts.extend([f"## {section_title}", "", stamped_body, ""])
        else:
            parts.extend([stamped_body, ""])
        return "\n".join(parts).rstrip() + "\n"

    seed = str(existing or "")
    if not seed.strip():
        seed = f"# {title}\n\n"

    sec = section_title or _default_timestamp_title()
    merged = _upsert_md_section(seed, sec, stamped_body)
    return merged.rstrip() + "\n"


def _rebuild_scope_index(
    workspace_root: Path,
    workspace_id: str,
    focus_root: str,
    scope_root: Path,
    max_files: int = 800,
) -> Dict[str, Any]:
    index_dir = _scope_index_dir(workspace_root)
    index_dir.mkdir(parents=True, exist_ok=True)

    key = _scope_key_local(focus_root)
    entries_path = index_dir / f"entries_{key}.jsonl"
    chunks_path = index_dir / f"chunks_{key}.jsonl"
    meta_path = index_dir / f"metadata_{key}.json"

    entry_rows: List[Dict[str, Any]] = []
    chunk_rows: List[Dict[str, Any]] = []

    count_files = 0
    count_dirs = 0
    chunk_id = 0

    if not scope_root.exists():
        meta = {
            "workspace_id": workspace_id,
            "focus_root": focus_root,
            "indexed_at": _now_iso_utc(),
            "file_count": 0,
            "directory_count": 0,
            "chunk_count": 0,
            "max_files": max_files,
        }
        _write_jsonl(entries_path, [])
        _write_jsonl(chunks_path, [])
        _atomic_write_json(meta_path, meta)
        return {
            "entries_path": str(entries_path),
            "chunks_path": str(chunks_path),
            "meta_path": str(meta_path),
            "meta": meta,
            "entries": [],
            "chunks": [],
        }

    for root, dirnames, filenames in os.walk(scope_root):
        dirnames[:] = sorted(d for d in dirnames if d != ".nisb_index")
        filenames[:] = sorted(filenames)

        root_path = Path(root)
        rel_dir = "" if root_path == scope_root else root_path.relative_to(scope_root).as_posix()

        entry_rows.append({
            "type": "directory",
            "relative_path": rel_dir,
            "name": root_path.name if rel_dir else "",
            "mtime": root_path.stat().st_mtime if root_path.exists() else 0,
        })
        count_dirs += 1

        for fn in filenames:
            if count_files >= max_files:
                break

            file_path = root_path / fn
            rel_path = file_path.relative_to(scope_root).as_posix()
            stat = file_path.stat()

            entry_rows.append({
                "type": "file",
                "relative_path": rel_path,
                "name": file_path.name,
                "size": stat.st_size,
                "mtime": stat.st_mtime,
                "suffix": file_path.suffix.lower(),
            })
            count_files += 1

            if not _is_text_file(file_path):
                continue

            text = _read_text_file(file_path, max_chars=120000)
            chunks = _chunk_text(text)
            for idx, part in enumerate(chunks):
                chunk_rows.append({
                    "chunk_id": chunk_id,
                    "relative_path": rel_path,
                    "chunk_index": idx,
                    "text": part,
                })
                chunk_id += 1

        if count_files >= max_files:
            break

    meta = {
        "workspace_id": workspace_id,
        "focus_root": focus_root,
        "indexed_at": _now_iso_utc(),
        "file_count": count_files,
        "directory_count": count_dirs,
        "chunk_count": len(chunk_rows),
        "max_files": max_files,
    }

    _write_jsonl(entries_path, entry_rows)
    _write_jsonl(chunks_path, chunk_rows)
    _atomic_write_json(meta_path, meta)

    return {
        "entries_path": str(entries_path),
        "chunks_path": str(chunks_path),
        "meta_path": str(meta_path),
        "meta": meta,
        "entries": entry_rows,
        "chunks": chunk_rows,
    }


def _load_or_rebuild_index(
    workspace_root: Path,
    workspace_id: str,
    focus_root: str,
    scope_root: Path,
    rebuild: bool = False,
) -> Dict[str, Any]:
    index_dir = _scope_index_dir(workspace_root)
    key = _scope_key_local(focus_root)
    entries_path = index_dir / f"entries_{key}.jsonl"
    chunks_path = index_dir / f"chunks_{key}.jsonl"
    meta_path = index_dir / f"metadata_{key}.json"

    if rebuild or not entries_path.exists() or not chunks_path.exists() or not meta_path.exists():
        return _rebuild_scope_index(workspace_root, workspace_id, focus_root, scope_root)

    return {
        "entries_path": str(entries_path),
        "chunks_path": str(chunks_path),
        "meta_path": str(meta_path),
        "meta": {},
        "entries": _load_jsonl(entries_path),
        "chunks": _load_jsonl(chunks_path),
    }


def _build_tree(scope_root: Path, max_depth: int, max_entries: int, include_files: bool) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    if not scope_root.exists():
        return out

    base_depth = len(scope_root.parts)

    for root, dirnames, filenames in os.walk(scope_root):
        root_path = Path(root)
        depth = len(root_path.parts) - base_depth
        if depth > max_depth:
            dirnames[:] = []
            continue

        dirnames[:] = sorted(d for d in dirnames if d != ".nisb_index")
        filenames[:] = sorted(filenames)

        if root_path != scope_root:
            rel_dir = root_path.relative_to(scope_root).as_posix()
            out.append({
                "type": "directory",
                "name": root_path.name,
                "relative_path": rel_dir,
                "depth": depth,
            })
            if len(out) >= max_entries:
                break

        if include_files:
            for fn in filenames:
                file_path = root_path / fn
                rel_file = file_path.relative_to(scope_root).as_posix()
                out.append({
                    "type": "file",
                    "name": file_path.name,
                    "relative_path": rel_file,
                    "depth": depth + 1,
                    "size": file_path.stat().st_size,
                    "suffix": file_path.suffix.lower(),
                })
                if len(out) >= max_entries:
                    break

        if len(out) >= max_entries:
            break

    return out


@auto_user_context
def nisb_workspace_snapshot_get(args: dict) -> dict:
    user_ctx = get_user_ctx()
    try:
        workspace_id = str(args.get("workspace_id") or "").strip()
        wid, ws, workspace_root, focus_root, scope_root, scope_kind, focus_source = _resolve_room_scope(
            user_ctx=user_ctx,
            workspace_id=workspace_id,
            focus_root=args.get("focus_root"),
            require_exists=False,
        )

        workspace_name = str(ws.get("name") or wid).strip() or wid
        focus_label = str(args.get("focus_label") or "").strip()
        room_token = _safe_token(args.get("room_id"), "room")
        agent_token = _safe_token(args.get("agent_id") or args.get("role_id"), "agent")
        room_id = str(args.get("room_id") or "").strip()

        top_level_files = 0
        top_level_directories = 0
        if scope_root.exists() and scope_root.is_dir():
            for item in scope_root.iterdir():
                if item.name.startswith("."):
                    continue
                if item.is_dir():
                    top_level_directories += 1
                elif item.is_file():
                    top_level_files += 1

        suggested_room_note_relative_path = f"_room_notes/{room_token}.md"

        if room_id:
            suggested_agent_notebook_relative_path = ""
            suggested_agent_notebook_scoped_path = ""
        else:
            suggested_agent_notebook_relative_path = f"_room_notebooks/{agent_token}.md"
            suggested_agent_notebook_scoped_path = _scoped_global_rel_path(
                focus_root,
                suggested_agent_notebook_relative_path,
            )

        return _ok(
            workspace_id=wid,
            workspace_name=workspace_name,
            workspace_root=str(workspace_root),
            focus_root=focus_root,
            focus_label=focus_label,
            focus_source=focus_source,
            scope_root=str(scope_root),
            scope_kind=scope_kind,
            scope_exists=scope_root.exists(),
            top_level_files=top_level_files,
            top_level_directories=top_level_directories,
            suggested_room_note_relative_path=suggested_room_note_relative_path,
            suggested_agent_notebook_relative_path=suggested_agent_notebook_relative_path,
            suggested_room_note_scoped_path=_scoped_global_rel_path(focus_root, suggested_room_note_relative_path),
            suggested_agent_notebook_scoped_path=suggested_agent_notebook_scoped_path,
        )
    except Exception as e:
        return _err(str(e))


@auto_user_context
def nisb_workspace_tree(args: dict) -> dict:
    user_ctx = get_user_ctx()
    try:
        workspace_id = str(args.get("workspace_id") or "").strip()
        max_depth = _coerce_int(args.get("max_depth"), default=2, low=0, high=8)
        max_entries = _coerce_int(args.get("max_entries"), default=200, low=1, high=2000)
        include_files = _coerce_bool(args.get("include_files"), default=True)

        wid, _, _, focus_root, scope_root, scope_kind, focus_source = _resolve_room_scope(
            user_ctx=user_ctx,
            workspace_id=workspace_id,
            focus_root=args.get("focus_root"),
            require_exists=True,
        )

        items = _build_tree(scope_root, max_depth=max_depth, max_entries=max_entries, include_files=include_files)

        return _ok(
            workspace_id=wid,
            focus_root=focus_root,
            focus_source=focus_source,
            scope_root=str(scope_root),
            scope_kind=scope_kind,
            max_depth=max_depth,
            max_entries=max_entries,
            count=len(items),
            items=items,
        )
    except Exception as e:
        return _err(str(e))


@auto_user_context
def nisb_workspace_read_entry(args: dict) -> dict:
    user_ctx = get_user_ctx()
    try:
        workspace_id = str(args.get("workspace_id") or "").strip()
        max_chars = _coerce_int(args.get("max_chars"), default=12000, low=100, high=300000)

        wid, _, _, focus_root, scope_root, scope_kind, focus_source = _resolve_room_scope(
            user_ctx=user_ctx,
            workspace_id=workspace_id,
            focus_root=args.get("focus_root"),
            require_exists=True,
        )

        rel_path = _normalize_rel_path(args.get("relative_path"))
        target = scope_root if not rel_path else _resolve_under_root(scope_root, rel_path, require_exists=True)

        if target.is_dir():
            children = []
            for child in sorted(target.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))[:300]:
                if child.name.startswith("."):
                    continue
                children.append({
                    "type": "directory" if child.is_dir() else "file",
                    "name": child.name,
                    "relative_path": child.relative_to(scope_root).as_posix(),
                    "size": child.stat().st_size if child.is_file() else None,
                    "suffix": child.suffix.lower() if child.is_file() else "",
                })

            return _ok(
                workspace_id=wid,
                focus_root=focus_root,
                focus_source=focus_source,
                scope_kind=scope_kind,
                relative_path=rel_path,
                entry_type="directory",
                count=len(children),
                children=children,
            )

        if not _is_text_file(target):
            global_rel_path = _scoped_global_rel_path(focus_root, rel_path) if rel_path else focus_root
            gate = _build_capability_gate(args, wid, focus_root)
            read_result = fs_file_read(_fs_args(
                base_args=args,
                user_ctx=user_ctx,
                capability_gate=gate,
                updates={"filename": global_rel_path},
            ))
            if read_result.get("success"):
                return _ok(
                    workspace_id=wid,
                    focus_root=focus_root,
                    focus_source=focus_source,
                    scope_kind=scope_kind,
                    relative_path=rel_path,
                    entry_type="file",
                    filetype=str(read_result.get("metadata", {}).get("type") or "binary"),
                    size=target.stat().st_size,
                    raw=read_result,
                )

            return _ok(
                workspace_id=wid,
                focus_root=focus_root,
                focus_source=focus_source,
                scope_kind=scope_kind,
                relative_path=rel_path,
                entry_type="file",
                filetype="binary",
                size=target.stat().st_size,
                content="",
                message="binary file not returned as text",
            )

        content = _read_text_file(target, max_chars=max_chars)
        return _ok(
            workspace_id=wid,
            focus_root=focus_root,
            focus_source=focus_source,
            scope_kind=scope_kind,
            relative_path=rel_path,
            entry_type="file",
            filetype="text",
            size=target.stat().st_size,
            max_chars=max_chars,
            content=content,
        )
    except Exception as e:
        return _err(str(e))


@auto_user_context
def nisb_workspace_search_hybrid(args: dict) -> dict:
    user_ctx = get_user_ctx()
    try:
        query = str(args.get("query") or "").strip()
        if not query:
            return _err("query 不能为空")

        workspace_id = str(args.get("workspace_id") or "").strip()
        top_k = _coerce_int(args.get("top_k"), default=8, low=1, high=50)
        excerpt_chars = _coerce_int(args.get("excerpt_chars"), default=320, low=80, high=2000)
        rebuild_index = _coerce_bool(args.get("rebuild_index"), default=False)

        wid, _, workspace_root, focus_root, scope_root, scope_kind, focus_source = _resolve_room_scope(
            user_ctx=user_ctx,
            workspace_id=workspace_id,
            focus_root=args.get("focus_root"),
            require_exists=True,
        )

        idx = _load_or_rebuild_index(workspace_root, wid, focus_root, scope_root, rebuild=rebuild_index)

        results: List[Dict[str, Any]] = []
        for chunk in idx.get("chunks", []):
            rel_path = str(chunk.get("relative_path") or "")
            text = str(chunk.get("text") or "")
            score = _score_text_match(query, rel_path, text)
            if score <= 0:
                continue
            excerpt = text[:excerpt_chars]
            results.append({
                "workspace_id": wid,
                "focus_root": focus_root,
                "focus_source": focus_source,
                "scope_kind": scope_kind,
                "relative_path": rel_path,
                "chunk_id": chunk.get("chunk_id"),
                "chunk_index": chunk.get("chunk_index"),
                "score": round(score, 4),
                "relevance": round(score, 4),
                "excerpt": excerpt,
                "text": excerpt,
            })

        existing_paths = {str(r.get("relative_path") or "") for r in results}
        for entry in idx.get("entries", []):
            if str(entry.get("type") or "") != "file":
                continue
            rel_path = str(entry.get("relative_path") or "")
            if rel_path in existing_paths:
                continue
            score = _score_text_match(query, rel_path, "")
            if score <= 0:
                continue
            results.append({
                "workspace_id": wid,
                "focus_root": focus_root,
                "focus_source": focus_source,
                "scope_kind": scope_kind,
                "relative_path": rel_path,
                "chunk_id": None,
                "chunk_index": None,
                "score": round(score, 4),
                "relevance": round(score, 4),
                "excerpt": rel_path,
                "text": rel_path,
            })

        merged = sorted(results, key=lambda x: float(x.get("score") or 0), reverse=True)[:top_k]

        return _ok(
            workspace_id=wid,
            focus_root=focus_root,
            focus_source=focus_source,
            scope_kind=scope_kind,
            query=query,
            top_k=top_k,
            count=len(merged),
            items=merged,
            index_meta=idx.get("meta") or {},
        )
    except Exception as e:
        return _err(str(e))


@auto_user_context
def nisb_workspace_create_entry(args: dict) -> dict:
    user_ctx = get_user_ctx()
    try:
        workspace_id = str(args.get("workspace_id") or "").strip()
        relative_path = str(args.get("relative_path") or "").strip()
        entry_type = str(args.get("entry_type") or "file").strip().lower()
        content = str(args.get("content") or "")
        rebuild_index = _coerce_bool(args.get("rebuild_index"), default=True)

        if entry_type not in {"file", "directory"}:
            return _err("entry_type 仅允许 file / directory")

        wid, _, workspace_root, focus_root, scope_root, scope_kind, focus_source = _resolve_room_scope(
            user_ctx=user_ctx,
            workspace_id=workspace_id,
            focus_root=args.get("focus_root"),
            require_exists=True,
        )

        rel_path = _normalize_rel_path_strict(relative_path)
        if not rel_path:
            return _err("relative_path 不能为空")

        target = _resolve_under_root(scope_root, rel_path, require_exists=False)
        if target.exists():
            return _err(f"条目已存在: {rel_path}")

        global_rel_path = _scoped_global_rel_path(focus_root, rel_path)
        gate = _build_capability_gate(args, wid, focus_root)

        if entry_type == "directory":
            result = fs_dir_create(_fs_args(
                base_args=args,
                user_ctx=user_ctx,
                capability_gate=gate,
                updates={"path": global_rel_path},
            ))
        else:
            _ensure_parent_dir(
                base_args=args,
                user_ctx=user_ctx,
                gate=gate,
                local_file_rel=rel_path,
                focus_root=focus_root,
            )
            result = fs_file_create(_fs_args(
                base_args=args,
                user_ctx=user_ctx,
                capability_gate=gate,
                updates={"filename": global_rel_path, "content": content},
            ))

        if not result.get("success"):
            return _err(result.get("message") or "创建失败", raw=result)

        if rebuild_index:
            _load_or_rebuild_index(workspace_root, wid, focus_root, scope_root, rebuild=True)

        return _ok(
            workspace_id=wid,
            focus_root=focus_root,
            focus_source=focus_source,
            scope_kind=scope_kind,
            relative_path=rel_path,
            scoped_path=global_rel_path,
            entry_type=entry_type,
            message="创建成功",
        )
    except Exception as e:
        return _err(str(e))


@auto_user_context
def nisb_workspace_write_entry(args: dict) -> dict:
    user_ctx = get_user_ctx()
    try:
        workspace_id = str(args.get("workspace_id") or "").strip()
        content = str(args.get("content") or "")
        mode = str(args.get("mode") or "overwrite").strip().lower()
        target_kind = str(args.get("target_kind") or "file").strip().lower()
        rebuild_index = _coerce_bool(args.get("rebuild_index"), default=True)

        if mode not in {"overwrite", "append"}:
            return _err("mode 仅允许 overwrite / append")

        if target_kind not in {"file", "room_note", "agent_notebook"}:
            return _err("target_kind 仅允许 file / room_note / agent_notebook")

        room_id = str(args.get("room_id") or "").strip()
        allow_room_legacy_agent_notebook = _coerce_bool(args.get("allow_room_legacy_agent_notebook"), default=False)
        if room_id and target_kind == "agent_notebook" and not allow_room_legacy_agent_notebook:
            return _err("Room 内 legacy agent_notebook 保存已停用，请改用 Supervisor notebook 正式链")

        wid, _, workspace_root, focus_root, scope_root, scope_kind, focus_source = _resolve_room_scope(
            user_ctx=user_ctx,
            workspace_id=workspace_id,
            focus_root=args.get("focus_root"),
            require_exists=True,
        )

        if target_kind == "agent_notebook":
            notebook_args = dict(args)
            notebook_args["workspace_id"] = wid
            notebook_args["focus_root"] = focus_root
            notebook_args["summary_md"] = content
            result = nisb_workspace_agent_notebook_upsert(notebook_args)
            if result.get("status") == "success" and rebuild_index:
                _load_or_rebuild_index(workspace_root, wid, focus_root, scope_root, rebuild=True)
            return result

        gate = _build_capability_gate(args, wid, focus_root)

        if target_kind == "room_note":
            local_file_rel = _room_note_local_rel(args)
            local_target = _resolve_under_root(scope_root, local_file_rel, require_exists=False)
            _ensure_parent_dir(
                base_args=args,
                user_ctx=user_ctx,
                gate=gate,
                local_file_rel=local_file_rel,
                focus_root=focus_root,
            )

            existing = ""
            if local_target.exists():
                if local_target.is_dir():
                    return _err("room_note 目标不能是目录")
                if _is_text_file(local_target):
                    existing = _read_text_file(local_target, max_chars=0)

            default_title = _note_title(args, f"{_safe_token(args.get('room_id'), 'room')} notes")
            section_title = _note_section_title(args)
            merged = _render_room_note(existing, default_title, section_title, content, mode)
            global_rel_path = _scoped_global_rel_path(focus_root, local_file_rel)

            if local_target.exists():
                result = fs_file_update(_fs_args(
                    base_args=args,
                    user_ctx=user_ctx,
                    capability_gate=gate,
                    updates={"filename": global_rel_path, "content": merged},
                ))
            else:
                result = fs_file_create(_fs_args(
                    base_args=args,
                    user_ctx=user_ctx,
                    capability_gate=gate,
                    updates={"filename": global_rel_path, "content": merged},
                ))

            if not result.get("success"):
                return _err(result.get("message") or "room_note 写入失败", raw=result)

            if rebuild_index:
                _load_or_rebuild_index(workspace_root, wid, focus_root, scope_root, rebuild=True)

            return _ok(
                workspace_id=wid,
                focus_root=focus_root,
                focus_source=focus_source,
                scope_kind=scope_kind,
                target_kind=target_kind,
                mode=mode,
                relative_path=local_file_rel,
                scoped_path=global_rel_path,
                section_title=section_title,
                message="room_note 写入成功",
            )

        relative_path = str(args.get("relative_path") or "").strip()
        rel_path = _normalize_rel_path_strict(relative_path)
        if not rel_path:
            return _err("relative_path 不能为空")

        target = _resolve_under_root(scope_root, rel_path, require_exists=False)
        if target.exists() and target.is_dir():
            return _err("不能向目录写入内容")

        if mode == "append" and target.exists():
            if not _is_text_file(target):
                return _err("append 仅支持文本文件")
            existing = _read_text_file(target, max_chars=0)
            new_content = existing + content
        else:
            new_content = content

        global_rel_path = _scoped_global_rel_path(focus_root, rel_path)
        _ensure_parent_dir(
            base_args=args,
            user_ctx=user_ctx,
            gate=gate,
            local_file_rel=rel_path,
            focus_root=focus_root,
        )

        if target.exists():
            result = fs_file_update(_fs_args(
                base_args=args,
                user_ctx=user_ctx,
                capability_gate=gate,
                updates={"filename": global_rel_path, "content": new_content},
            ))
        else:
            result = fs_file_create(_fs_args(
                base_args=args,
                user_ctx=user_ctx,
                capability_gate=gate,
                updates={"filename": global_rel_path, "content": new_content},
            ))

        if not result.get("success"):
            return _err(result.get("message") or "写入失败", raw=result)

        if rebuild_index:
            _load_or_rebuild_index(workspace_root, wid, focus_root, scope_root, rebuild=True)

        return _ok(
            workspace_id=wid,
            focus_root=focus_root,
            focus_source=focus_source,
            scope_kind=scope_kind,
            target_kind=target_kind,
            relative_path=rel_path,
            scoped_path=global_rel_path,
            bytes=len(new_content.encode("utf-8")),
            mode=mode,
            message="写入成功",
        )
    except Exception as e:
        return _err(str(e))


@auto_user_context
def nisb_workspace_delete_entry(args: dict) -> dict:
    user_ctx = get_user_ctx()
    try:
        workspace_id = str(args.get("workspace_id") or "").strip()
        relative_path = str(args.get("relative_path") or "").strip()
        recursive = _coerce_bool(args.get("recursive"), default=False)
        rebuild_index = _coerce_bool(args.get("rebuild_index"), default=True)

        wid, _, workspace_root, focus_root, scope_root, scope_kind, focus_source = _resolve_room_scope(
            user_ctx=user_ctx,
            workspace_id=workspace_id,
            focus_root=args.get("focus_root"),
            require_exists=True,
        )

        rel_path = _normalize_rel_path_strict(relative_path)
        if not rel_path:
            return _err("relative_path 不能为空")

        target = _resolve_under_root(scope_root, rel_path, require_exists=True)
        global_rel_path = _scoped_global_rel_path(focus_root, rel_path)
        gate = _build_capability_gate(args, wid, focus_root)

        if target.is_dir():
            if recursive:
                result = fs_dir_delete_recursive(_fs_args(
                    base_args=args,
                    user_ctx=user_ctx,
                    capability_gate=gate,
                    updates={"path": global_rel_path},
                ))
            else:
                result = fs_dir_delete(_fs_args(
                    base_args=args,
                    user_ctx=user_ctx,
                    capability_gate=gate,
                    updates={"path": global_rel_path},
                ))
            deleted_type = "directory"
        else:
            result = fs_file_delete(_fs_args(
                base_args=args,
                user_ctx=user_ctx,
                capability_gate=gate,
                updates={"filename": global_rel_path, "permanent": True},
            ))
            deleted_type = "file"

        if not result.get("success"):
            return _err(result.get("message") or "删除失败", raw=result)

        if rebuild_index:
            _load_or_rebuild_index(workspace_root, wid, focus_root, scope_root, rebuild=True)

        return _ok(
            workspace_id=wid,
            focus_root=focus_root,
            focus_source=focus_source,
            scope_kind=scope_kind,
            relative_path=rel_path,
            scoped_path=global_rel_path,
            deleted_type=deleted_type,
            message="删除成功",
        )
    except Exception as e:
        return _err(str(e))


@auto_user_context
def nisb_workspace_rename_entry(args: dict) -> dict:
    user_ctx = get_user_ctx()
    try:
        workspace_id = str(args.get("workspace_id") or "").strip()
        relative_path = str(args.get("relative_path") or "").strip()
        new_name = str(args.get("new_name") or "").strip()
        rebuild_index = _coerce_bool(args.get("rebuild_index"), default=True)

        if not new_name or "/" in new_name or "\\" in new_name or new_name in {".", ".."}:
            return _err("new_name 非法")

        wid, _, workspace_root, focus_root, scope_root, scope_kind, focus_source = _resolve_room_scope(
            user_ctx=user_ctx,
            workspace_id=workspace_id,
            focus_root=args.get("focus_root"),
            require_exists=True,
        )

        rel_path = _normalize_rel_path_strict(relative_path)
        if not rel_path:
            return _err("relative_path 不能为空")

        target = _resolve_under_root(scope_root, rel_path, require_exists=True)
        global_old_rel = _scoped_global_rel_path(focus_root, rel_path)
        local_parent = _local_parent_rel(rel_path)
        local_new_rel = f"{local_parent}/{new_name}" if local_parent else new_name
        global_new_rel = _scoped_global_rel_path(focus_root, local_new_rel)
        gate = _build_capability_gate(args, wid, focus_root)

        if target.is_dir():
            result = fs_dir_move_path(_fs_args(
                base_args=args,
                user_ctx=user_ctx,
                capability_gate=gate,
                updates={"old_path": global_old_rel, "new_path": global_new_rel},
            ))
        else:
            result = fs_file_rename(_fs_args(
                base_args=args,
                user_ctx=user_ctx,
                capability_gate=gate,
                updates={"old_path": global_old_rel, "new_name": new_name},
            ))

        if not result.get("success"):
            return _err(result.get("message") or "改名失败", raw=result)

        if rebuild_index:
            _load_or_rebuild_index(workspace_root, wid, focus_root, scope_root, rebuild=True)

        return _ok(
            workspace_id=wid,
            focus_root=focus_root,
            focus_source=focus_source,
            scope_kind=scope_kind,
            old_relative_path=rel_path,
            new_relative_path=local_new_rel,
            old_scoped_path=global_old_rel,
            new_scoped_path=global_new_rel,
            message="改名成功",
        )
    except Exception as e:
        return _err(str(e))


@auto_user_context
def nisb_workspace_agent_notebook_upsert(args: dict) -> dict:
    user_ctx = get_user_ctx()
    try:
        room_id = str(args.get("room_id") or "").strip()
        allow_room_legacy_agent_notebook = _coerce_bool(args.get("allow_room_legacy_agent_notebook"), default=False)
        if room_id and not allow_room_legacy_agent_notebook:
            return _err("Room 内 legacy agent_notebook 保存已停用，请改用 Supervisor notebook 正式链")

        workspace_id = str(args.get("workspace_id") or "").strip()
        agent_id = _require_safe_agent_id(str(args.get("agent_id") or args.get("role_id") or "agent").strip())
        title = str(args.get("title") or f"{agent_id} notebook").strip()
        section_title = str(args.get("section_title") or "").strip() or _default_timestamp_title()
        summary_md = str(args.get("summary_md") or args.get("content") or "").strip()
        rebuild_index = _coerce_bool(args.get("rebuild_index"), default=True)

        if not summary_md:
            return _err("summary_md 不能为空")

        wid, _, workspace_root, focus_root, scope_root, scope_kind, focus_source = _resolve_room_scope(
            user_ctx=user_ctx,
            workspace_id=workspace_id,
            focus_root=args.get("focus_root"),
            require_exists=True,
        )

        local_file_rel = _agent_notebook_local_rel(args)
        global_file_rel = _scoped_global_rel_path(focus_root, local_file_rel)
        gate = _build_capability_gate(args, wid, focus_root)

        _ensure_parent_dir(
            base_args=args,
            user_ctx=user_ctx,
            gate=gate,
            local_file_rel=local_file_rel,
            focus_root=focus_root,
        )

        local_target = _resolve_under_root(scope_root, local_file_rel, require_exists=False)

        existing = ""
        if local_target.exists():
            existing = _read_text_file(local_target, max_chars=0)

        if not existing.strip():
            existing = f"# {title}\n\n"

        stamped_body = f"_updated_at: {_now_iso_utc()}_\n\n{summary_md}"
        merged = _upsert_md_section(existing, section_title, stamped_body)

        if local_target.exists():
            result = fs_file_update(_fs_args(
                base_args=args,
                user_ctx=user_ctx,
                capability_gate=gate,
                updates={"filename": global_file_rel, "content": merged},
            ))
        else:
            result = fs_file_create(_fs_args(
                base_args=args,
                user_ctx=user_ctx,
                capability_gate=gate,
                updates={"filename": global_file_rel, "content": merged},
            ))

        if not result.get("success"):
            return _err(result.get("message") or "agent_notebook 更新失败", raw=result)

        if rebuild_index:
            _load_or_rebuild_index(workspace_root, wid, focus_root, scope_root, rebuild=True)

        return _ok(
            workspace_id=wid,
            focus_root=focus_root,
            focus_source=focus_source,
            scope_kind=scope_kind,
            notebook_dir=_local_parent_rel(local_file_rel),
            relative_path=local_file_rel,
            scoped_path=global_file_rel,
            agent_id=agent_id,
            section_title=section_title,
            message="agent_notebook 已更新",
        )
    except Exception as e:
        return _err(str(e))


