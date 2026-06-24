from __future__ import annotations

import json
import os
import re
import shutil
import tempfile
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from .common import (
    auto_user_context as autousercontext,
    get_user_ctx as getuserctx,
    _load_workspace_file_or_create,
    _resolve_focus_root_scope,
    _resolve_under_root,
    _normalize_rel_path,
    _coerce_bool,
    _coerce_int,
    _require_safe_agent_id,
)

SAFE_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$")
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


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_text(value: Any, default: str = "") -> str:
    return str(value if value is not None else default).strip()


def _safe_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _safe_list(value: Any) -> List[Any]:
    return value if isinstance(value, list) else []


def _ok(
    response: str,
    *,
    message: str = "",
    tool_results: List[Dict[str, Any]] | None = None,
    **compat: Any,
) -> Dict[str, Any]:
    return {
        "status": "success",
        "response": _safe_text(response) or _safe_text(message) or "操作完成",
        "message": _safe_text(message) or _safe_text(response) or "操作完成",
        "citations": [],
        "tool_calls": [],
        "tool_results": tool_results or [],
        "success": True,
        **compat,
    }


def _err(message: str, *, response: str = "", **compat: Any) -> Dict[str, Any]:
    return {
        "status": "error",
        "response": _safe_text(response),
        "message": _safe_text(message) or "操作失败",
        "citations": [],
        "tool_calls": [],
        "tool_results": [],
        "success": False,
        **compat,
    }


def _require_safe_id(field: str, value: Any) -> str:
    s = str(value or "").strip()
    if not s:
        raise ValueError(f"{field} 不能为空")
    if not SAFE_ID_RE.fullmatch(s):
        raise ValueError(f"{field} 非法：仅允许 a-z/A-Z/0-9/_/-，且不能以符号开头")
    return s


def _safe_rel_markdown_filename(value: Any, default_name: str) -> str:
    s = str(value or "").strip().replace("\\", "/")
    s = s.split("/")[-1].strip()
    if not s:
        s = default_name
    s = re.sub(r"[^A-Za-z0-9._-]+", "_", s)
    if not s.lower().endswith(".md"):
        s = f"{s}.md"
    if s in {".md", "..md"}:
        s = default_name
    return s


def _atomic_write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", delete=False, dir=str(path.parent))
    try:
        tmp.write(content)
        tmp.flush()
        os.fsync(tmp.fileno())
        tmp.close()
        os.replace(tmp.name, path)
    finally:
        try:
            if os.path.exists(tmp.name):
                os.unlink(tmp.name)
        except Exception:
            pass


def _atomic_write_json(path: Path, obj: Any) -> None:
    _atomic_write_text(path, json.dumps(obj, ensure_ascii=False, indent=2))


def _write_jsonl(path: Path, rows: List[Dict[str, Any]]) -> None:
    text = "\n".join(json.dumps(r, ensure_ascii=False) for r in rows)
    if text:
        text += "\n"
    _atomic_write_text(path, text)


def _read_json(path: Path) -> Dict[str, Any]:
    try:
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
    except Exception:
        pass
    return {}


def _is_text_file(path: Path) -> bool:
    if path.suffix.lower() in BINARY_EXTS:
        return False
    if path.suffix.lower() in TEXT_EXTS:
        return True
    try:
        with path.open("rb") as f:
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
    src = _safe_text(text)
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
    raw = re.findall(r"[A-Za-z0-9_.\\-/]+|[\\u4e00-\\u9fff]+", _safe_text(query).lower())
    seen = set()
    out = []
    for t in raw:
        if t in seen:
            continue
        seen.add(t)
        out.append(t)
    return out


def _score_text_match(query: str, rel_path: str, text: str) -> float:
    q = _safe_text(query).lower()
    rp = _safe_text(rel_path).lower()
    tx = _safe_text(text).lower()
    terms = _query_terms(q)
    if not q:
        return 0.0

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


def _index_dir(workspace_dir: Path) -> Path:
    return workspace_dir / ".nisb_index"


def _scope_key(focus_root: str) -> str:
    raw = focus_root or "__workspace_root__"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:12]


def _rebuild_workspace_index(workspace_dir: Path, focus_root: str, scope_root: Path, max_files: int = 800) -> Dict[str, Any]:
    index_dir = _index_dir(workspace_dir)
    index_dir.mkdir(parents=True, exist_ok=True)

    key = _scope_key(focus_root)
    entries_path = index_dir / f"entries_{key}.jsonl"
    chunks_path = index_dir / f"chunks_{key}.jsonl"
    meta_path = index_dir / f"metadata_{key}.json"

    entry_rows: List[Dict[str, Any]] = []
    chunk_rows: List[Dict[str, Any]] = []

    count_files = 0
    count_dirs = 0
    chunk_id = 0

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
        "workspace_id": workspace_dir.name,
        "focus_root": focus_root,
        "indexed_at": _now_iso(),
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


def _load_jsonl(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    out: List[Dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
                if isinstance(row, dict):
                    out.append(row)
            except Exception:
                continue
    return out


def _load_or_rebuild_index(workspace_dir: Path, focus_root: str, scope_root: Path, rebuild: bool = False) -> Dict[str, Any]:
    index_dir = _index_dir(workspace_dir)
    key = _scope_key(focus_root)
    entries_path = index_dir / f"entries_{key}.jsonl"
    chunks_path = index_dir / f"chunks_{key}.jsonl"
    meta_path = index_dir / f"metadata_{key}.json"

    if rebuild or not entries_path.exists() or not chunks_path.exists() or not meta_path.exists():
        return _rebuild_workspace_index(workspace_dir, focus_root, scope_root)

    return {
        "entries_path": str(entries_path),
        "chunks_path": str(chunks_path),
        "meta_path": str(meta_path),
        "meta": _read_json(meta_path),
        "entries": _load_jsonl(entries_path),
        "chunks": _load_jsonl(chunks_path),
    }


def _build_tree(scope_root: Path, max_depth: int, max_entries: int, include_files: bool) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
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


def _upsert_md_section(existing: str, section_title: str, body_md: str) -> str:
    title = _safe_text(section_title) or "latest"
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


def _snapshot_row(
    *,
    workspace_id: str,
    workspace_name: str,
    workspace_root: str,
    focus_root: str,
    focus_label: str,
    scope_root: str,
    scope_kind: str,
    scope_exists: bool,
    top_level_files: int,
    top_level_directories: int,
) -> Dict[str, Any]:
    return {
        "type": "workspace_snapshot",
        "workspace_id": workspace_id,
        "workspace_name": workspace_name,
        "workspace_root": workspace_root,
        "focus_root": focus_root,
        "focus_label": focus_label,
        "scope_root": scope_root,
        "scope_kind": scope_kind,
        "scope_exists": bool(scope_exists),
        "top_level_files": int(top_level_files),
        "top_level_directories": int(top_level_directories),
    }


def _tree_row(
    *,
    workspace_id: str,
    focus_root: str,
    scope_root: str,
    scope_kind: str,
    max_depth: int,
    max_entries: int,
    items: List[Dict[str, Any]],
) -> Dict[str, Any]:
    return {
        "type": "workspace_tree",
        "workspace_id": workspace_id,
        "focus_root": focus_root,
        "scope_root": scope_root,
        "scope_kind": scope_kind,
        "max_depth": max_depth,
        "max_entries": max_entries,
        "items": items,
        "count": len(items),
    }


def _entry_row(
    *,
    workspace_id: str,
    focus_root: str,
    scope_kind: str,
    relative_path: str,
    entry_type: str,
    filetype: str = "",
    size: int | None = None,
    max_chars: int | None = None,
    content: str = "",
    children: List[Dict[str, Any]] | None = None,
) -> Dict[str, Any]:
    row: Dict[str, Any] = {
        "type": "workspace_entry",
        "workspace_id": workspace_id,
        "focus_root": focus_root,
        "scope_kind": scope_kind,
        "relative_path": relative_path,
        "entry_type": entry_type,
    }
    if filetype:
        row["filetype"] = filetype
    if size is not None:
        row["size"] = size
    if max_chars is not None:
        row["max_chars"] = max_chars
    if content != "":
        row["content"] = content
    if children is not None:
        row["children"] = children
        row["count"] = len(children)
    return row


def _search_row(
    *,
    workspace_id: str,
    focus_root: str,
    scope_kind: str,
    query: str,
    top_k: int,
    items: List[Dict[str, Any]],
    index_meta: Dict[str, Any],
) -> Dict[str, Any]:
    return {
        "type": "workspace_search",
        "workspace_id": workspace_id,
        "focus_root": focus_root,
        "scope_kind": scope_kind,
        "query": query,
        "top_k": top_k,
        "items": items,
        "count": len(items),
        "index_meta": index_meta,
    }


def _entry_mutation_row(
    *,
    row_type: str,
    workspace_id: str,
    focus_root: str,
    scope_kind: str,
    relative_path: str = "",
    old_relative_path: str = "",
    new_relative_path: str = "",
    entry_type: str = "",
    deleted_type: str = "",
    mode: str = "",
    bytes_count: int | None = None,
) -> Dict[str, Any]:
    row: Dict[str, Any] = {
        "type": row_type,
        "workspace_id": workspace_id,
        "focus_root": focus_root,
        "scope_kind": scope_kind,
    }
    if relative_path:
        row["relative_path"] = relative_path
    if old_relative_path:
        row["old_relative_path"] = old_relative_path
    if new_relative_path:
        row["new_relative_path"] = new_relative_path
    if entry_type:
        row["entry_type"] = entry_type
    if deleted_type:
        row["deleted_type"] = deleted_type
    if mode:
        row["mode"] = mode
    if bytes_count is not None:
        row["bytes"] = bytes_count
    return row


def _agent_notebook_row(
    *,
    workspace_id: str,
    focus_root: str,
    scope_kind: str,
    notebook_dir: str,
    relative_path: str,
    agent_id: str,
    section_title: str,
) -> Dict[str, Any]:
    return {
        "type": "workspace_agent_notebook",
        "workspace_id": workspace_id,
        "focus_root": focus_root,
        "scope_kind": scope_kind,
        "notebook_dir": notebook_dir,
        "relative_path": relative_path,
        "agent_id": agent_id,
        "section_title": section_title,
    }


def _resolve_scope_root(args: Dict[str, Any], require_exists: bool = True):
    user_ctx = getuserctx()
    workspace_id = _require_safe_id("workspace_id", args.get("workspace_id"))
    wid, ws, workspace_dir, focus_root, scope_root, scope_kind = _resolve_focus_root_scope(
        user_ctx=user_ctx,
        workspace_id=workspace_id,
        focus_root=_safe_text(args.get("focus_root")),
        require_exists=require_exists,
    )
    return user_ctx, wid, ws, workspace_dir, focus_root, scope_root, scope_kind


def _resolve_entry_path(args: Dict[str, Any], require_exists: bool = True):
    _, workspace_id, _, workspace_dir, focus_root, scope_root, scope_kind = _resolve_scope_root(
        args,
        require_exists=True,
    )
    rel_path = _normalize_rel_path(args.get("relative_path"))
    if not rel_path:
        raise ValueError("relative_path 不能为空")
    target = _resolve_under_root(scope_root, rel_path, require_exists=require_exists)
    return workspace_id, workspace_dir, focus_root, scope_root, rel_path, target, scope_kind


@autousercontext
def nisb_workspace_snapshot_get(args: Dict[str, Any]) -> Dict[str, Any]:
    try:
        _, workspace_id, ws, workspace_dir, focus_root, scope_root, scope_kind = _resolve_scope_root(
            args,
            require_exists=False,
        )

        workspace_name = _safe_text(args.get("workspace_name")) or _safe_text(ws.get("name")) or workspace_id
        focus_label = _safe_text(args.get("focus_label"))

        items = list(scope_root.iterdir()) if scope_root.exists() and scope_root.is_dir() else []
        file_count = sum(1 for p in items if p.is_file())
        dir_count = sum(1 for p in items if p.is_dir())

        row = _snapshot_row(
            workspace_id=workspace_id,
            workspace_name=workspace_name,
            workspace_root=str(workspace_dir),
            focus_root=focus_root,
            focus_label=focus_label,
            scope_root=str(scope_root),
            scope_kind=scope_kind,
            scope_exists=scope_root.exists(),
            top_level_files=file_count,
            top_level_directories=dir_count,
        )

        return _ok(
            f"已获取工作空间快照：{workspace_name}",
            message=f"已获取工作空间快照：{workspace_name}",
            tool_results=[row],
            workspace_id=workspace_id,
            workspace_name=workspace_name,
            workspace_root=str(workspace_dir),
            focus_root=focus_root,
            focus_label=focus_label,
            scope_root=str(scope_root),
            scope_kind=scope_kind,
            scope_exists=scope_root.exists(),
            top_level_files=file_count,
            top_level_directories=dir_count,
        )
    except Exception as e:
        return _err(str(e))


@autousercontext
def nisb_workspace_tree(args: Dict[str, Any]) -> Dict[str, Any]:
    try:
        _, workspace_id, _, _, focus_root, scope_root, scope_kind = _resolve_scope_root(
            args,
            require_exists=True,
        )
        max_depth = _coerce_int(args.get("max_depth"), default=2, low=0, high=8)
        max_entries = _coerce_int(args.get("max_entries"), default=200, low=1, high=2000)
        include_files = _coerce_bool(args.get("include_files"), default=True)

        items = _build_tree(scope_root, max_depth=max_depth, max_entries=max_entries, include_files=include_files)
        row = _tree_row(
            workspace_id=workspace_id,
            focus_root=focus_root,
            scope_root=str(scope_root),
            scope_kind=scope_kind,
            max_depth=max_depth,
            max_entries=max_entries,
            items=items,
        )

        return _ok(
            f"已获取工作空间树，共 {len(items)} 项",
            message=f"已获取工作空间树，共 {len(items)} 项",
            tool_results=[row],
            workspace_id=workspace_id,
            focus_root=focus_root,
            scope_root=str(scope_root),
            scope_kind=scope_kind,
            max_depth=max_depth,
            max_entries=max_entries,
            items=items,
            count=len(items),
        )
    except Exception as e:
        return _err(str(e))


@autousercontext
def nisb_workspace_read_entry(args: Dict[str, Any]) -> Dict[str, Any]:
    try:
        workspace_id, _, focus_root, scope_root, rel_path, target, scope_kind = _resolve_entry_path(
            args,
            require_exists=True,
        )

        if target.is_dir():
            children = []
            for child in sorted(target.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))[:300]:
                children.append({
                    "type": "directory" if child.is_dir() else "file",
                    "name": child.name,
                    "relative_path": child.relative_to(scope_root).as_posix(),
                    "size": child.stat().st_size if child.is_file() else None,
                    "suffix": child.suffix.lower() if child.is_file() else "",
                })

            row = _entry_row(
                workspace_id=workspace_id,
                focus_root=focus_root,
                scope_kind=scope_kind,
                relative_path=rel_path,
                entry_type="directory",
                children=children,
            )

            return _ok(
                f"已读取目录：{rel_path}",
                message=f"已读取目录：{rel_path}",
                tool_results=[row],
                workspace_id=workspace_id,
                focus_root=focus_root,
                scope_kind=scope_kind,
                relative_path=rel_path,
                entry_type="directory",
                children=children,
                count=len(children),
            )

        max_chars = _coerce_int(args.get("max_chars"), default=12000, low=100, high=200000)

        if not _is_text_file(target):
            row = _entry_row(
                workspace_id=workspace_id,
                focus_root=focus_root,
                scope_kind=scope_kind,
                relative_path=rel_path,
                entry_type="file",
                filetype="binary",
                size=target.stat().st_size,
                content="",
            )

            return _ok(
                f"已读取二进制文件信息：{rel_path}",
                message="二进制文件，未返回文本内容",
                tool_results=[row],
                workspace_id=workspace_id,
                focus_root=focus_root,
                scope_kind=scope_kind,
                relative_path=rel_path,
                entry_type="file",
                filetype="binary",
                size=target.stat().st_size,
                content="",
            )

        content = _read_text_file(target, max_chars=max_chars)
        row = _entry_row(
            workspace_id=workspace_id,
            focus_root=focus_root,
            scope_kind=scope_kind,
            relative_path=rel_path,
            entry_type="file",
            filetype="text",
            size=target.stat().st_size,
            max_chars=max_chars,
            content=content,
        )

        return _ok(
            f"已读取文件：{rel_path}",
            message=f"已读取文件：{rel_path}",
            tool_results=[row],
            workspace_id=workspace_id,
            focus_root=focus_root,
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


@autousercontext
def nisb_workspace_search_hybrid(args: Dict[str, Any]) -> Dict[str, Any]:
    try:
        query = _safe_text(args.get("query"))
        if not query:
            return _err("query 不能为空")

        _, workspace_id, _, workspace_dir, focus_root, scope_root, scope_kind = _resolve_scope_root(
            args,
            require_exists=True,
        )
        top_k = _coerce_int(args.get("top_k"), default=8, low=1, high=50)
        excerpt_chars = _coerce_int(args.get("excerpt_chars"), default=320, low=80, high=2000)
        rebuild_index = _coerce_bool(args.get("rebuild_index"), default=False)

        idx = _load_or_rebuild_index(workspace_dir, focus_root, scope_root, rebuild=rebuild_index)

        results: List[Dict[str, Any]] = []
        for chunk in idx.get("chunks", []):
            rel_path = _safe_text(chunk.get("relative_path"))
            text = _safe_text(chunk.get("text"))
            score = _score_text_match(query, rel_path, text)
            if score <= 0:
                continue
            excerpt = text[:excerpt_chars]
            results.append({
                "workspace_id": workspace_id,
                "focus_root": focus_root,
                "scope_kind": scope_kind,
                "relative_path": rel_path,
                "chunk_id": chunk.get("chunk_id"),
                "chunk_index": chunk.get("chunk_index"),
                "score": round(score, 4),
                "relevance": round(score, 4),
                "excerpt": excerpt,
                "text": excerpt,
            })

        path_hits: List[Dict[str, Any]] = []
        existing_paths = {_safe_text(r.get("relative_path")) for r in results}
        for entry in idx.get("entries", []):
            if _safe_text(entry.get("type")) != "file":
                continue
            rel_path = _safe_text(entry.get("relative_path"))
            if rel_path in existing_paths:
                continue
            score = _score_text_match(query, rel_path, "")
            if score <= 0:
                continue
            path_hits.append({
                "workspace_id": workspace_id,
                "focus_root": focus_root,
                "scope_kind": scope_kind,
                "relative_path": rel_path,
                "chunk_id": None,
                "chunk_index": None,
                "score": round(score, 4),
                "relevance": round(score, 4),
                "excerpt": rel_path,
                "text": rel_path,
            })

        merged = sorted(results + path_hits, key=lambda x: float(x.get("score") or 0), reverse=True)[:top_k]
        index_meta = _safe_dict(idx.get("meta"))

        row = _search_row(
            workspace_id=workspace_id,
            focus_root=focus_root,
            scope_kind=scope_kind,
            query=query,
            top_k=top_k,
            items=merged,
            index_meta=index_meta,
        )

        return _ok(
            f"已完成工作空间搜索，共 {len(merged)} 条结果",
            message=f"已完成工作空间搜索，共 {len(merged)} 条结果",
            tool_results=[row],
            workspace_id=workspace_id,
            focus_root=focus_root,
            scope_kind=scope_kind,
            query=query,
            top_k=top_k,
            count=len(merged),
            items=merged,
            index_meta=index_meta,
        )
    except Exception as e:
        return _err(str(e))


@autousercontext
def nisb_workspace_write_entry(args: Dict[str, Any]) -> Dict[str, Any]:
    try:
        workspace_id, workspace_dir, focus_root, scope_root, rel_path, target, scope_kind = _resolve_entry_path(
            args,
            require_exists=False,
        )

        content = str(args.get("content") or "")
        mode = _safe_text(args.get("mode") or "overwrite").lower()
        if mode not in {"overwrite", "append"}:
            return _err("mode 仅允许 overwrite / append")

        target.parent.mkdir(parents=True, exist_ok=True)

        if mode == "append" and target.exists():
            old = _read_text_file(target, max_chars=0) if _is_text_file(target) else ""
            new_content = old + content
        else:
            new_content = content

        _atomic_write_text(target, new_content)

        if _coerce_bool(args.get("rebuild_index"), default=True):
            _load_or_rebuild_index(workspace_dir, focus_root, scope_root, rebuild=True)

        bytes_count = len(new_content.encode("utf-8"))
        row = _entry_mutation_row(
            row_type="workspace_entry_write",
            workspace_id=workspace_id,
            focus_root=focus_root,
            scope_kind=scope_kind,
            relative_path=rel_path,
            mode=mode,
            bytes_count=bytes_count,
        )

        return _ok(
            f"已写入文件：{rel_path}",
            message="写入成功",
            tool_results=[row],
            workspace_id=workspace_id,
            focus_root=focus_root,
            scope_kind=scope_kind,
            relative_path=rel_path,
            bytes=bytes_count,
            mode=mode,
        )
    except Exception as e:
        return _err(str(e))


@autousercontext
def nisb_workspace_create_entry(args: Dict[str, Any]) -> Dict[str, Any]:
    try:
        workspace_id, workspace_dir, focus_root, scope_root, rel_path, target, scope_kind = _resolve_entry_path(
            args,
            require_exists=False,
        )

        entry_type = _safe_text(args.get("entry_type") or "file").lower()
        if entry_type not in {"file", "directory"}:
            return _err("entry_type 仅允许 file / directory")

        if target.exists():
            return _err(f"条目已存在: {rel_path}")

        if entry_type == "directory":
            target.mkdir(parents=True, exist_ok=False)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            _atomic_write_text(target, str(args.get("content") or ""))

        if _coerce_bool(args.get("rebuild_index"), default=True):
            _load_or_rebuild_index(workspace_dir, focus_root, scope_root, rebuild=True)

        row = _entry_mutation_row(
            row_type="workspace_entry_create",
            workspace_id=workspace_id,
            focus_root=focus_root,
            scope_kind=scope_kind,
            relative_path=rel_path,
            entry_type=entry_type,
        )

        return _ok(
            f"已创建{ '目录' if entry_type == 'directory' else '文件' }：{rel_path}",
            message="创建成功",
            tool_results=[row],
            workspace_id=workspace_id,
            focus_root=focus_root,
            scope_kind=scope_kind,
            relative_path=rel_path,
            entry_type=entry_type,
        )
    except Exception as e:
        return _err(str(e))


@autousercontext
def nisb_workspace_delete_entry(args: Dict[str, Any]) -> Dict[str, Any]:
    try:
        workspace_id, workspace_dir, focus_root, scope_root, rel_path, target, scope_kind = _resolve_entry_path(
            args,
            require_exists=True,
        )

        recursive = _coerce_bool(args.get("recursive"), default=False)

        if target.is_dir():
            if not recursive:
                children = list(target.iterdir())
                if children:
                    return _err("目录非空，删除目录请传 recursive=true")
            shutil.rmtree(target)
            deleted_type = "directory"
        else:
            target.unlink()
            deleted_type = "file"

        if _coerce_bool(args.get("rebuild_index"), default=True):
            _load_or_rebuild_index(workspace_dir, focus_root, scope_root, rebuild=True)

        row = _entry_mutation_row(
            row_type="workspace_entry_delete",
            workspace_id=workspace_id,
            focus_root=focus_root,
            scope_kind=scope_kind,
            relative_path=rel_path,
            deleted_type=deleted_type,
        )

        return _ok(
            f"已删除{ '目录' if deleted_type == 'directory' else '文件' }：{rel_path}",
            message="删除成功",
            tool_results=[row],
            workspace_id=workspace_id,
            focus_root=focus_root,
            scope_kind=scope_kind,
            relative_path=rel_path,
            deleted_type=deleted_type,
        )
    except Exception as e:
        return _err(str(e))


@autousercontext
def nisb_workspace_rename_entry(args: Dict[str, Any]) -> Dict[str, Any]:
    try:
        workspace_id, workspace_dir, focus_root, scope_root, rel_path, target, scope_kind = _resolve_entry_path(
            args,
            require_exists=True,
        )

        new_name = _safe_text(args.get("new_name"))
        if not new_name or "/" in new_name or "\\" in new_name or new_name in {".", ".."}:
            return _err("new_name 非法")

        new_target = (target.parent / new_name).resolve()
        if scope_root not in [new_target] and scope_root not in new_target.parents:
            return _err("new_name 越界")
        if new_target.exists():
            return _err(f"目标已存在: {new_name}")

        target.rename(new_target)

        if _coerce_bool(args.get("rebuild_index"), default=True):
            _load_or_rebuild_index(workspace_dir, focus_root, scope_root, rebuild=True)

        new_relative_path = new_target.relative_to(scope_root).as_posix()
        row = _entry_mutation_row(
            row_type="workspace_entry_rename",
            workspace_id=workspace_id,
            focus_root=focus_root,
            scope_kind=scope_kind,
            old_relative_path=rel_path,
            new_relative_path=new_relative_path,
        )

        return _ok(
            f"已重命名条目：{rel_path} -> {new_relative_path}",
            message="改名成功",
            tool_results=[row],
            workspace_id=workspace_id,
            focus_root=focus_root,
            scope_kind=scope_kind,
            old_relative_path=rel_path,
            new_relative_path=new_relative_path,
        )
    except Exception as e:
        return _err(str(e))


@autousercontext
def nisb_workspace_agent_notebook_upsert(args: Dict[str, Any]) -> Dict[str, Any]:
    try:
        _, workspace_id, _, workspace_dir, focus_root, scope_root, scope_kind = _resolve_scope_root(
            args,
            require_exists=True,
        )

        agent_id = _require_safe_agent_id("agent_id", args.get("agent_id") or args.get("role_id") or "agent")
        notebook_dir_rel = _normalize_rel_path(args.get("notebook_dir") or "_room_notebooks")
        notebook_dir = _resolve_under_root(scope_root, notebook_dir_rel, require_exists=False) if notebook_dir_rel else scope_root

        filename = _safe_rel_markdown_filename(args.get("filename"), f"{agent_id}.md")
        file_path = notebook_dir / filename
        file_path.parent.mkdir(parents=True, exist_ok=True)

        title = _safe_text(args.get("title") or f"{agent_id} notebook")
        section_title = _safe_text(args.get("section_title") or "latest") or "latest"
        summary_md = _safe_text(args.get("summary_md") or args.get("content"))
        if not summary_md:
            return _err("summary_md 不能为空")

        existing = ""
        if file_path.exists():
            existing = _read_text_file(file_path, max_chars=0)

        if not existing.strip():
            existing = f"# {title}\n\n"

        stamped_body = f"_updated_at: {_now_iso()}_\n\n{summary_md}"
        merged = _upsert_md_section(existing, section_title, stamped_body)
        _atomic_write_text(file_path, merged)

        if _coerce_bool(args.get("rebuild_index"), default=True):
            _load_or_rebuild_index(workspace_dir, focus_root, scope_root, rebuild=True)

        notebook_dir_rel_out = notebook_dir.relative_to(scope_root).as_posix() if notebook_dir != scope_root else ""
        relative_path = file_path.relative_to(scope_root).as_posix()

        row = _agent_notebook_row(
            workspace_id=workspace_id,
            focus_root=focus_root,
            scope_kind=scope_kind,
            notebook_dir=notebook_dir_rel_out,
            relative_path=relative_path,
            agent_id=agent_id,
            section_title=section_title,
        )

        return _ok(
            f"已更新 agent notebook：{relative_path}",
            message="agent notebook 已更新",
            tool_results=[row],
            workspace_id=workspace_id,
            focus_root=focus_root,
            scope_kind=scope_kind,
            notebook_dir=notebook_dir_rel_out,
            relative_path=relative_path,
            agent_id=agent_id,
            section_title=section_title,
        )
    except Exception as e:
        return _err(str(e))

