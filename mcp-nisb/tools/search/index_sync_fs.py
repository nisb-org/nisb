#!/usr/bin/env python3

import hashlib
import os
import sqlite3
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from .common import read_text_cached
from .index_db import meta_get_float, meta_set
from .index_shared import (
    SNIPPET_EXCERPT_CHARS,
    build_content_blocks,
    is_textual_file,
    read_small_excerpt,
    safe_rel,
)
from .index_store import upsert_entries
from .index_sync_state import mark_synced, module_entry_count


INDEX_SYNC_FS_FORMAT_VERSION = 2.0

FILE_MODULE_ROOT_CANDIDATES: Dict[str, Tuple[str, ...]] = {
    "files": ("agent_files",),
    "doc": ("documents",),
}

DIRS_ROOT_CANDIDATES: Tuple[str, ...] = (
    "agent_files",
    "documents",
    "libraries",
)


def _compact_text(value: str) -> str:
    text = str(value or "").lower().strip()
    return "".join(ch for ch in text if ch.isalnum() or "\u4e00" <= ch <= "\u9fff")


def _format_version_key(module: str) -> str:
    return f"index_sync_fs_format:{module}"


def _format_version_stale(conn: sqlite3.Connection, module: str) -> bool:
    try:
        current = meta_get_float(conn, _format_version_key(module))
    except Exception:
        current = None
    return float(current or 0.0) < float(INDEX_SYNC_FS_FORMAT_VERSION)


def _mark_format_version(conn: sqlite3.Connection, module: str) -> None:
    meta_set(conn, _format_version_key(module), float(INDEX_SYNC_FS_FORMAT_VERSION))


def _delete_module_entries(conn: sqlite3.Connection, module: str) -> int:
    try:
        cur = conn.execute(
            "DELETE FROM search_entries WHERE module = ?",
            (module,),
        )
        return int(cur.rowcount or 0)
    except Exception:
        return 0


def _should_skip_path(path: Path) -> bool:
    try:
        parts = [str(part).lower() for part in path.parts]
    except Exception:
        parts = []

    if ".metadata" in parts:
        return True

    name = path.name.lower()
    if name in {".ds_store", ".gitkeep"}:
        return True

    return False


def _office_converted_markdown_sibling(path: Path) -> Optional[Path]:
    try:
        suffix = path.suffix.lower().lstrip(".")
        if not suffix or suffix in {"md", "markdown", "txt"}:
            return None
        if suffix not in {"doc", "docx", "ppt", "pptx", "xls", "xlsx", "odt", "odp", "ods"}:
            return None
        candidate = path.with_name(f"{path.stem}_{suffix}.md")
        if not candidate.exists() or not candidate.is_file():
            return None
        if _should_skip_path(candidate):
            return None
        return candidate
    except Exception:
        return None


def _expand_with_office_converted_markdown(paths: Sequence[Path]) -> List[Path]:
    out: List[Path] = []
    seen = set()
    for path in list(paths or []):
        key = str(path)
        if key not in seen:
            seen.add(key)
            out.append(path)

        sibling = _office_converted_markdown_sibling(path)
        if sibling is None:
            continue
        sibling_key = str(sibling)
        if sibling_key in seen:
            continue
        seen.add(sibling_key)
        out.append(sibling)
    return out




def _normalize_name_hints(name_hints: Optional[Sequence[str]]) -> List[Dict[str, str]]:
    hints: List[Dict[str, str]] = []
    seen = set()

    for value in list(name_hints or []):
        raw = str(value or "").strip()
        if not raw:
            continue

        norm = raw.lower()
        compact = _compact_text(raw)
        stem_norm = raw.rsplit(".", 1)[0].strip().lower() if "." in raw and not raw.startswith(".") else norm
        stem_compact = _compact_text(stem_norm)

        key = (norm, compact, stem_norm, stem_compact)
        if key in seen:
            continue
        seen.add(key)

        hints.append(
            {
                "raw": raw,
                "norm": norm,
                "compact": compact,
                "stem_norm": stem_norm,
                "stem_compact": stem_compact,
            }
        )

    return hints


def _path_match_score(path: Path, hints: Sequence[Dict[str, str]]) -> int:
    if not hints:
        return 0

    name = path.name.lower()
    stem = path.stem.lower()
    path_str = path.as_posix().lower()

    compact_name = _compact_text(path.name)
    compact_stem = _compact_text(path.stem)
    compact_path = _compact_text(path.as_posix())

    best = 0

    for hint in hints:
        norm = str(hint.get("norm", "") or "")
        compact = str(hint.get("compact", "") or "")
        stem_norm = str(hint.get("stem_norm", "") or "")
        stem_compact = str(hint.get("stem_compact", "") or "")

        if norm:
            if norm == name:
                best = max(best, 1200)
            elif norm == stem:
                best = max(best, 1100)
            elif name.startswith(norm):
                best = max(best, 960)
            elif stem.startswith(norm):
                best = max(best, 920)
            elif norm in name:
                best = max(best, 840)
            elif norm in stem:
                best = max(best, 820)
            elif norm in path_str:
                best = max(best, 700)

        if compact:
            if compact == compact_name:
                best = max(best, 1180)
            elif compact == compact_stem:
                best = max(best, 1080)
            elif compact_name.startswith(compact):
                best = max(best, 940)
            elif compact_stem.startswith(compact):
                best = max(best, 900)
            elif compact in compact_name:
                best = max(best, 830)
            elif compact in compact_stem:
                best = max(best, 800)
            elif compact in compact_path:
                best = max(best, 680)

        if stem_norm:
            if stem_norm == stem:
                best = max(best, 1060)
            elif stem.startswith(stem_norm):
                best = max(best, 900)
            elif stem_norm in stem:
                best = max(best, 790)

        if stem_compact:
            if stem_compact == compact_stem:
                best = max(best, 1040)
            elif compact_stem.startswith(stem_compact):
                best = max(best, 880)
            elif stem_compact in compact_stem:
                best = max(best, 780)

    return best


def _dir_match_score(path: Path, hints: Sequence[Dict[str, str]]) -> int:
    if not hints:
        return 0

    name = path.name.lower()
    path_str = path.as_posix().lower()
    compact_name = _compact_text(path.name)
    compact_path = _compact_text(path.as_posix())

    best = 0
    for hint in hints:
        norm = str(hint.get("norm", "") or "")
        compact = str(hint.get("compact", "") or "")
        stem_norm = str(hint.get("stem_norm", "") or "")
        stem_compact = str(hint.get("stem_compact", "") or "")

        for token in (norm, stem_norm):
            if token:
                if token == name:
                    best = max(best, 300)
                elif token in name:
                    best = max(best, 220)
                elif token in path_str:
                    best = max(best, 160)

        for token in (compact, stem_compact):
            if token:
                if token == compact_name:
                    best = max(best, 280)
                elif token in compact_name:
                    best = max(best, 210)
                elif token in compact_path:
                    best = max(best, 150)

    return best


def _existing_dir(path: Optional[Path]) -> bool:
    try:
        return bool(path and path.exists() and path.is_dir())
    except Exception:
        return False


def _dedupe_paths(paths: Sequence[Path]) -> List[Path]:
    out: List[Path] = []
    seen = set()
    for path in paths:
        try:
            key = str(Path(path).resolve())
        except Exception:
            key = str(Path(path))
        if key in seen:
            continue
        seen.add(key)
        out.append(Path(path))
    return out


def file_module_root_candidates(module: str) -> Tuple[str, ...]:
    return tuple(FILE_MODULE_ROOT_CANDIDATES.get(str(module or ""), ()))


def resolve_file_module_root(
    base_path: Path,
    module: str,
    root: Optional[Path] = None,
) -> Optional[Path]:
    base_path = Path(base_path)

    if root is not None:
        explicit_root = Path(root)
        if _existing_dir(explicit_root):
            return explicit_root

    candidates = file_module_root_candidates(module)
    for rel in candidates:
        candidate = base_path / rel
        if _existing_dir(candidate):
            return candidate

    if root is not None:
        return Path(root)

    if candidates:
        return base_path / candidates[0]

    return None


def resolve_dirs_roots(base_path: Path) -> List[Path]:
    base_path = Path(base_path)
    roots: List[Path] = []

    for rel in DIRS_ROOT_CANDIDATES:
        path = base_path / rel
        if _existing_dir(path):
            roots.append(path)

    return _dedupe_paths(roots)


def _walk_files(
    root: Path,
    recursive: bool,
    max_nodes: int = 0,
    dir_hints: Optional[Sequence[Dict[str, str]]] = None,
) -> Iterable[Path]:
    if not root.exists() or not root.is_dir():
        return

    visited = 0
    stack: List[Path] = [root]
    hint_objs = list(dir_hints or [])

    while stack:
        current = stack.pop()
        try:
            with os.scandir(current) as it:
                dirs: List[Tuple[int, str, Path]] = []
                files: List[Tuple[int, Path]] = []

                for entry in it:
                    visited += 1
                    if max_nodes > 0 and visited > max_nodes:
                        return

                    try:
                        path = Path(entry.path)
                    except Exception:
                        continue

                    if _should_skip_path(path):
                        continue

                    try:
                        if entry.is_dir(follow_symlinks=False):
                            if recursive:
                                dirs.append((_dir_match_score(path, hint_objs), path.name.lower(), path))
                            continue
                    except Exception:
                        continue

                    try:
                        if entry.is_file(follow_symlinks=False):
                            files.append((_path_match_score(path, hint_objs), path))
                    except Exception:
                        continue

                files.sort(key=lambda x: (x[0], x[1].name.lower()), reverse=True)
                for _, path in files:
                    yield path

                if recursive and dirs:
                    dirs.sort(key=lambda x: (x[0], x[1]), reverse=True)
                    for _, _, path in dirs:
                        stack.append(path)
        except Exception:
            continue


def _walk_dirs(root: Path, max_nodes: int = 0) -> Iterable[Path]:
    if not root.exists() or not root.is_dir():
        return

    visited = 0
    stack: List[Path] = [root]

    while stack:
        current = stack.pop()
        try:
            with os.scandir(current) as it:
                dirs: List[Tuple[str, Path]] = []
                for entry in it:
                    visited += 1
                    if max_nodes > 0 and visited > max_nodes:
                        return

                    try:
                        path = Path(entry.path)
                    except Exception:
                        continue

                    if _should_skip_path(path):
                        continue

                    try:
                        if entry.is_dir(follow_symlinks=False):
                            yield path
                            dirs.append((path.name.lower(), path))
                    except Exception:
                        continue

                if dirs:
                    dirs.sort(key=lambda x: x[0], reverse=True)
                    for _, path in dirs:
                        stack.append(path)
        except Exception:
            continue


def _iter_files(root: Path, recursive: bool) -> List[Path]:
    return list(_walk_files(root, recursive=recursive, max_nodes=0, dir_hints=None))


def _iter_dirs(root: Path) -> List[Path]:
    return list(_walk_dirs(root, max_nodes=0))


def _mtime_ns(path: Path) -> int:
    try:
        return int(path.stat().st_mtime_ns)
    except Exception:
        return 0


def _size(path: Path) -> int:
    try:
        return int(path.stat().st_size)
    except Exception:
        return 0


def _build_file_entry(
    module: str,
    rel_path: str,
    filename: str,
    mtime_ns: int,
    size: int,
) -> Dict[str, Any]:
    return {
        "item_key": f"{module}::{rel_path}",
        "module": module,
        "source_kind": f"{module}_file",
        "group_key": rel_path,
        "path": rel_path,
        "filename": filename,
        "title": filename,
        "library_id": "",
        "library_name": "",
        "doc_id": "",
        "conv_id": "",
        "created_at": "",
        "turn_count": 0,
        "snippet": "",
        "priority_hint": 20,
        "mtime_ns": mtime_ns,
        "size": size,
    }


def _build_dir_entry(
    rel_path: str,
    dirname: str,
    mtime_ns: int,
) -> Dict[str, Any]:
    return {
        "item_key": f"dirs::{rel_path}",
        "module": "dirs",
        "source_kind": "dirs_dir",
        "group_key": rel_path,
        "path": rel_path,
        "filename": dirname,
        "title": dirname,
        "library_id": "",
        "library_name": "",
        "doc_id": "",
        "conv_id": "",
        "created_at": "",
        "turn_count": 0,
        "snippet": f"目录名匹配: {dirname}",
        "priority_hint": 18,
        "mtime_ns": mtime_ns,
        "size": 0,
    }


def _build_file_content_entries(
    module: str,
    rel_path: str,
    filename: str,
    mtime_ns: int,
    size: int,
    raw_text: str,
) -> List[Dict[str, Any]]:
    text_len = len(str(raw_text or "").strip())

    if module == "files":
        if text_len <= 1200:
            block_chars = 420
            max_blocks = 6
        elif text_len <= 4000:
            block_chars = 360
            max_blocks = 10
        elif text_len <= 12000:
            block_chars = 320
            max_blocks = 14
        else:
            block_chars = 320
            max_blocks = 18
    else:
        if text_len <= 1200:
            block_chars = 420
            max_blocks = 4
        elif text_len <= 4000:
            block_chars = 360
            max_blocks = 8
        elif text_len <= 12000:
            block_chars = 320
            max_blocks = 10
        else:
            block_chars = 320
            max_blocks = 12

    blocks = build_content_blocks(
        raw_text,
        block_chars=block_chars,
        max_blocks=max_blocks,
    )

    out: List[Dict[str, Any]] = []
    for idx, block in enumerate(blocks):
        out.append(
            {
                "item_key": f"{module}_content::{rel_path}::{idx}",
                "module": module,
                "source_kind": f"{module}_content",
                "group_key": rel_path,
                "path": rel_path,
                "filename": filename,
                "title": filename,
                "library_id": "",
                "library_name": "",
                "doc_id": "",
                "conv_id": "",
                "created_at": "",
                "turn_count": 0,
                "snippet": block,
                "priority_hint": 14 if idx == 0 else 13,
                "mtime_ns": mtime_ns,
                "size": size,
            }
        )
    return out


def _delete_item_keys(conn: sqlite3.Connection, item_keys: List[str]) -> int:
    keys = [str(k) for k in item_keys if str(k)]
    if not keys:
        return 0

    deleted = 0
    chunk = 300
    for i in range(0, len(keys), chunk):
        batch = keys[i:i + chunk]
        placeholders = ",".join("?" for _ in batch)
        cur = conn.execute(
            f"DELETE FROM search_entries WHERE item_key IN ({placeholders})",
            batch,
        )
        try:
            deleted += int(cur.rowcount or 0)
        except Exception:
            pass
    return deleted


def _load_existing_subset(
    conn: sqlite3.Connection,
    item_keys: List[str],
) -> Dict[str, Tuple[int, int]]:
    if not item_keys:
        return {}

    out: Dict[str, Tuple[int, int]] = {}
    deduped = list(dict.fromkeys([str(k) for k in item_keys if str(k)]))

    chunk_size = 400
    for i in range(0, len(deduped), chunk_size):
        batch = deduped[i:i + chunk_size]
        placeholders = ",".join("?" for _ in batch)
        rows = conn.execute(
            f"""
            SELECT item_key, mtime_ns, size
            FROM search_entries
            WHERE item_key IN ({placeholders})
            """,
            batch,
        ).fetchall()
        for row in rows:
            out[str(row["item_key"])] = (
                int(row["mtime_ns"] or 0),
                int(row["size"] or 0),
            )
    return out


def _filter_changed_entries(
    candidate_entries: List[Dict[str, Any]],
    existing_subset: Dict[str, Tuple[int, int]],
) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for entry in candidate_entries:
        key = str(entry.get("item_key", ""))
        stamp = (
            int(entry.get("mtime_ns", 0) or 0),
            int(entry.get("size", 0) or 0),
        )
        if existing_subset.get(key) != stamp:
            out.append(entry)
    return out


def _collect_file_entries_for_path(
    module: str,
    base_path: Path,
    path: Path,
    st: Any,
    metadata_only: bool = False,
) -> List[Dict[str, Any]]:
    rel_path = safe_rel(path, base_path)
    mtime_ns = int(getattr(st, "st_mtime_ns", 0) or 0)
    size = int(getattr(st, "st_size", 0) or 0)

    entries: List[Dict[str, Any]] = [
        _build_file_entry(
            module=module,
            rel_path=rel_path,
            filename=path.name,
            mtime_ns=mtime_ns,
            size=size,
        )
    ]

    if metadata_only:
        return entries

    if not is_textual_file(path):
        return entries

    raw_text = read_text_cached(path)
    if raw_text:
        entries.extend(
            _build_file_content_entries(
                module=module,
                rel_path=rel_path,
                filename=path.name,
                mtime_ns=mtime_ns,
                size=size,
                raw_text=raw_text,
            )
        )
        return entries

    excerpt = read_small_excerpt(path, max_chars=SNIPPET_EXCERPT_CHARS)
    if excerpt:
        entries.append(
            {
                "item_key": f"{module}_content::{rel_path}::0",
                "module": module,
                "source_kind": f"{module}_content",
                "group_key": rel_path,
                "path": rel_path,
                "filename": path.name,
                "title": path.name,
                "library_id": "",
                "library_name": "",
                "doc_id": "",
                "conv_id": "",
                "created_at": "",
                "turn_count": 0,
                "snippet": excerpt,
                "priority_hint": 14,
                "mtime_ns": mtime_ns,
                "size": size,
            }
        )

    return entries


def _hint_cache_key(module: str, name_hints: Optional[Sequence[str]], metadata_only: bool) -> str:
    normalized = [str(v or "").strip().lower() for v in list(name_hints or []) if str(v or "").strip()]
    basis = f"{module}|{'meta' if metadata_only else 'full'}|" + "|".join(sorted(dict.fromkeys(normalized)))
    digest = hashlib.sha1(basis.encode("utf-8")).hexdigest()[:20]
    return f"quick_sync_hint:{module}:{digest}"


def _hint_sync_due(
    conn: sqlite3.Connection,
    module: str,
    name_hints: Optional[Sequence[str]],
    metadata_only: bool,
    min_interval_seconds: float = 12.0,
) -> bool:
    key = _hint_cache_key(module, name_hints, metadata_only)
    last = meta_get_float(conn, key)
    if last is None:
        return True
    return (time.time() - float(last)) >= float(min_interval_seconds)


def _mark_hint_synced(
    conn: sqlite3.Connection,
    module: str,
    name_hints: Optional[Sequence[str]],
    metadata_only: bool,
) -> None:
    key = _hint_cache_key(module, name_hints, metadata_only)
    meta_set(conn, key, time.time())


def _has_explicit_extension(name_hints: Optional[Sequence[str]]) -> bool:
    for value in list(name_hints or []):
        text = str(value or "").strip().lower()
        if text and "." in text and not text.startswith("."):
            return True
    return False


def _candidate_files(
    root: Path,
    recursive: bool,
    within_seconds: Optional[int] = None,
    max_candidates: int = 200,
    name_hints: Optional[Sequence[str]] = None,
) -> Tuple[List[Path], Dict[str, int]]:
    now_ns = time.time_ns()
    cutoff_ns = 0
    if within_seconds and within_seconds > 0:
        cutoff_ns = now_ns - int(within_seconds) * 1_000_000_000

    hint_objs = _normalize_name_hints(name_hints)
    max_candidates = max(1, int(max_candidates))
    explicit_ext = _has_explicit_extension(name_hints)

    if recursive:
        if hint_objs and explicit_ext:
            walk_budget = max(2500, max_candidates * 80)
        elif hint_objs:
            walk_budget = max(5000, max_candidates * 140)
        else:
            walk_budget = 12000
    else:
        if hint_objs and explicit_ext:
            walk_budget = max(800, max_candidates * 40)
        elif hint_objs:
            walk_budget = max(1500, max_candidates * 60)
        else:
            walk_budget = 2000

    strong_hit_threshold = 1080 if explicit_ext else 980
    exact_name_threshold = 1180

    matched_by_hint: List[Tuple[int, int, Path]] = []
    matched_by_time: List[Tuple[int, Path]] = []
    scanned = 0
    strong_hint_hits = 0
    exact_name_hits = 0
    early_stop = 0

    for path in _walk_files(
        root=root,
        recursive=recursive,
        max_nodes=walk_budget,
        dir_hints=hint_objs,
    ):
        scanned += 1

        try:
            st = path.stat()
        except Exception:
            continue

        mtime_ns = int(st.st_mtime_ns or 0)
        score = _path_match_score(path, hint_objs)

        if score > 0:
            matched_by_hint.append((score, mtime_ns, path))
            if score >= strong_hit_threshold:
                strong_hint_hits += 1
            if score >= exact_name_threshold:
                exact_name_hits += 1

            if exact_name_hits >= 1:
                early_stop = 1
                break
            if strong_hint_hits >= min(max_candidates, 4):
                early_stop = 1
                break
            continue

        if cutoff_ns and mtime_ns >= cutoff_ns:
            matched_by_time.append((mtime_ns, path))

    matched_by_hint.sort(key=lambda x: (x[0], x[1]), reverse=True)
    matched_by_time.sort(key=lambda x: x[0], reverse=True)

    out: List[Path] = []
    seen = set()

    for _, _, path in matched_by_hint:
        key = str(path)
        if key in seen:
            continue
        seen.add(key)
        out.append(path)
        if len(out) >= max_candidates:
            return out, {
                "scanned": scanned,
                "walk_budget": walk_budget,
                "hint_hits": len(matched_by_hint),
                "recent_hits": len(matched_by_time),
                "strong_hint_hits": strong_hint_hits,
                "exact_name_hits": exact_name_hits,
                "early_stop": early_stop,
            }

    for _, path in matched_by_time:
        key = str(path)
        if key in seen:
            continue
        seen.add(key)
        out.append(path)
        if len(out) >= max_candidates:
            break

    return out, {
        "scanned": scanned,
        "walk_budget": walk_budget,
        "hint_hits": len(matched_by_hint),
        "recent_hits": len(matched_by_time),
        "strong_hint_hits": strong_hint_hits,
        "exact_name_hits": exact_name_hits,
        "early_stop": early_stop,
    }


def _candidate_dirs(
    roots: Sequence[Path],
    within_seconds: Optional[int] = None,
    max_candidates: int = 100,
) -> Tuple[List[Path], Dict[str, int]]:
    now_ns = time.time_ns()
    cutoff_ns = 0
    if within_seconds and within_seconds > 0:
        cutoff_ns = now_ns - int(within_seconds) * 1_000_000_000

    entries: List[Tuple[int, Path]] = []
    scanned = 0
    walk_budget_per_root = max(1500, int(max_candidates) * 40)

    for root in roots:
        for path in _walk_dirs(root, max_nodes=walk_budget_per_root):
            scanned += 1
            if _should_skip_path(path):
                continue

            mtime_ns = _mtime_ns(path)
            if cutoff_ns and mtime_ns < cutoff_ns:
                continue
            entries.append((mtime_ns, path))

    entries.sort(key=lambda x: x[0], reverse=True)

    out: List[Path] = []
    seen = set()
    for _, path in entries:
        key = str(path)
        if key in seen:
            continue
        seen.add(key)
        out.append(path)
        if len(out) >= max(1, int(max_candidates)):
            break

    return out, {
        "scanned": scanned,
        "walk_budget_per_root": walk_budget_per_root,
    }


def _existing_keys_for_prefix(conn: sqlite3.Connection, module: str, rel_prefix: str) -> List[str]:
    prefix = str(rel_prefix or "").strip()
    if not prefix:
        return []

    rows = conn.execute(
        """
        SELECT item_key
        FROM search_entries
        WHERE module = ?
          AND path = ?
        """,
        (module, prefix),
    ).fetchall()

    return [str(row["item_key"]) for row in rows]


def _existing_keys_for_module_roots(
    conn: sqlite3.Connection,
    module: str,
    rel_roots: Sequence[str],
) -> Dict[str, List[str]]:
    out: Dict[str, List[str]] = {}
    rel_roots = [str(p or "").strip() for p in rel_roots if str(p or "").strip()]
    if not rel_roots:
        return out

    for rel_root in rel_roots:
        like_prefix = f"{rel_root}/%"
        rows = conn.execute(
            """
            SELECT item_key, path
            FROM search_entries
            WHERE module = ?
              AND (path = ? OR path LIKE ?)
            """,
            (module, rel_root, like_prefix),
        ).fetchall()

        keys = [str(row["item_key"]) for row in rows]
        out[rel_root] = keys

    return out


def quick_sync_file_module(
    conn: sqlite3.Connection,
    base_path: Path,
    module: str,
    root: Optional[Path] = None,
    recursive: bool = False,
    within_seconds: int = 300,
    max_candidates: int = 200,
    name_hints: Optional[Sequence[str]] = None,
    metadata_only: bool = False,
) -> Dict[str, Any]:
    base_path = Path(base_path)
    resolved_root = resolve_file_module_root(base_path, module, root=root)
    if resolved_root is None or not resolved_root.exists() or not resolved_root.is_dir():
        return {
            "indexed": 0,
            "deleted": 0,
            "total": int(module_entry_count(conn, module) or 0),
            "skipped": 1,
            "reason": "root_missing",
            "candidates": 0,
            "metadata_only": bool(metadata_only),
            "format_stale": False,
        }

    root = resolved_root
    format_stale = _format_version_stale(conn, module)

    if (
        metadata_only
        and name_hints
        and not format_stale
        and not _hint_sync_due(conn, module, name_hints, metadata_only)
    ):
        return {
            "indexed": 0,
            "deleted": 0,
            "total": int(module_entry_count(conn, module) or 0),
            "skipped": 1,
            "reason": "hint_recent_skip",
            "candidates": 0,
            "metadata_only": bool(metadata_only),
            "format_stale": bool(format_stale),
            "name_hints": list(name_hints or []),
            "scanned": 0,
            "walk_budget": 0,
            "hint_hits": 0,
            "recent_hits": 0,
            "strong_hint_hits": 0,
            "exact_name_hits": 0,
            "early_stop": 0,
        }

    candidates, scan_stats = _candidate_files(
        root=root,
        recursive=recursive,
        within_seconds=within_seconds,
        max_candidates=max_candidates,
        name_hints=name_hints,
    )
    candidates = _expand_with_office_converted_markdown(candidates)

    candidate_entries: List[Dict[str, Any]] = []
    deleted = 0

    for path in candidates:
        try:
            st = path.stat()
        except FileNotFoundError:
            rel_path = safe_rel(path, base_path)
            stale_keys = _existing_keys_for_prefix(conn, module, rel_path)
            if stale_keys:
                deleted += _delete_item_keys(conn, stale_keys)
            continue
        except Exception:
            continue

        entries = _collect_file_entries_for_path(
            module=module,
            base_path=base_path,
            path=path,
            st=st,
            metadata_only=metadata_only,
        )
        candidate_entries.extend(entries)

        rel_path = safe_rel(path, base_path)
        if not metadata_only:
            prefix = f"{module}_content::{rel_path}::"
            existing_content = conn.execute(
                """
                SELECT item_key
                FROM search_entries
                WHERE module = ?
                  AND item_key LIKE ?
                """,
                (module, f"{prefix}%"),
            ).fetchall()
            existing_content_keys = {str(row["item_key"]) for row in existing_content}
            new_content_keys = {
                str(entry["item_key"])
                for entry in entries
                if str(entry.get("item_key", "")).startswith(prefix)
            }
            stale_content_keys = list(existing_content_keys - new_content_keys)
            if stale_content_keys:
                deleted += _delete_item_keys(conn, stale_content_keys)

    if format_stale:
        changed_entries = list(candidate_entries)
    else:
        existing_subset = _load_existing_subset(
            conn,
            [str(entry["item_key"]) for entry in candidate_entries],
        )
        changed_entries = _filter_changed_entries(candidate_entries, existing_subset)

    indexed = int(upsert_entries(conn, changed_entries) or 0) if changed_entries else 0

    if metadata_only and name_hints:
        try:
            _mark_hint_synced(conn, module, name_hints, metadata_only)
        except Exception:
            pass

    try:
        mark_synced(conn, module)
    except Exception:
        pass

    try:
        conn.commit()
    except Exception:
        pass

    return {
        "indexed": indexed,
        "deleted": deleted,
        "total": int(module_entry_count(conn, module) or 0),
        "skipped": 0,
        "reason": "quick_sync",
        "candidates": len(candidates),
        "metadata_only": bool(metadata_only),
        "format_stale": bool(format_stale),
        "name_hints": list(name_hints or []),
        "scanned": int(scan_stats.get("scanned", 0) or 0),
        "walk_budget": int(scan_stats.get("walk_budget", 0) or 0),
        "hint_hits": int(scan_stats.get("hint_hits", 0) or 0),
        "recent_hits": int(scan_stats.get("recent_hits", 0) or 0),
        "strong_hint_hits": int(scan_stats.get("strong_hint_hits", 0) or 0),
        "exact_name_hits": int(scan_stats.get("exact_name_hits", 0) or 0),
        "early_stop": int(scan_stats.get("early_stop", 0) or 0),
    }


def sync_file_module(
    conn: sqlite3.Connection,
    base_path: Path,
    module: str,
    root: Optional[Path] = None,
    recursive: bool = False,
    metadata_only: bool = False,
) -> Dict[str, Any]:
    base_path = Path(base_path)
    resolved_root = resolve_file_module_root(base_path, module, root=root)
    if resolved_root is None or not resolved_root.exists() or not resolved_root.is_dir():
        return {
            "indexed": 0,
            "deleted": 0,
            "total": int(module_entry_count(conn, module) or 0),
            "skipped": 1,
            "reason": "root_missing",
            "candidates": 0,
            "metadata_only": bool(metadata_only),
            "format_rebuilt": False,
        }

    root = resolved_root
    format_stale = _format_version_stale(conn, module)

    all_files = []
    for path in _iter_files(root, recursive=recursive):
        if _should_skip_path(path):
            continue
        all_files.append(path)

    all_files.sort(key=lambda p: _mtime_ns(p), reverse=True)

    entries: List[Dict[str, Any]] = []
    current_item_keys = set()
    rel_root = safe_rel(root, base_path)

    for path in all_files:
        try:
            st = path.stat()
        except Exception:
            continue

        one_entries = _collect_file_entries_for_path(
            module=module,
            base_path=base_path,
            path=path,
            st=st,
            metadata_only=metadata_only,
        )
        for entry in one_entries:
            item_key = str(entry.get("item_key", ""))
            if item_key:
                current_item_keys.add(item_key)
        entries.extend(one_entries)

    if format_stale:
        deleted = _delete_module_entries(conn, module)
        changed_entries = list(entries)
    else:
        existing_map = _existing_keys_for_module_roots(conn, module, [rel_root])
        existing_keys = set(existing_map.get(rel_root, []))
        stale_keys = list(existing_keys - current_item_keys)
        deleted = _delete_item_keys(conn, stale_keys) if stale_keys else 0

        existing_subset = _load_existing_subset(
            conn,
            [str(entry["item_key"]) for entry in entries],
        )
        changed_entries = _filter_changed_entries(entries, existing_subset)

    indexed = int(upsert_entries(conn, changed_entries) or 0) if changed_entries else 0

    try:
        _mark_format_version(conn, module)
    except Exception:
        pass

    try:
        mark_synced(conn, module)
    except Exception:
        pass

    try:
        conn.commit()
    except Exception:
        pass

    return {
        "indexed": indexed,
        "deleted": deleted,
        "total": int(module_entry_count(conn, module) or 0),
        "skipped": 0,
        "reason": "full_sync",
        "candidates": len(all_files),
        "metadata_only": bool(metadata_only),
        "format_rebuilt": bool(format_stale),
    }


def quick_sync_dirs_module(
    conn: sqlite3.Connection,
    base_path: Path,
    within_seconds: int = 300,
    max_candidates: int = 100,
) -> Dict[str, Any]:
    base_path = Path(base_path)
    roots = resolve_dirs_roots(base_path)
    if not roots:
        return {
            "indexed": 0,
            "deleted": 0,
            "total": int(module_entry_count(conn, "dirs") or 0),
            "skipped": 1,
            "reason": "no_dirs_roots",
            "candidates": 0,
        }

    candidates, scan_stats = _candidate_dirs(
        roots=roots,
        within_seconds=within_seconds,
        max_candidates=max_candidates,
    )

    entries: List[Dict[str, Any]] = []
    deleted = 0

    for path in candidates:
        if not path.exists() or not path.is_dir():
            rel_path = safe_rel(path, base_path)
            stale_keys = _existing_keys_for_prefix(conn, "dirs", rel_path)
            if stale_keys:
                deleted += _delete_item_keys(conn, stale_keys)
            continue

        rel_path = safe_rel(path, base_path)
        entry = _build_dir_entry(
            rel_path=rel_path,
            dirname=path.name,
            mtime_ns=_mtime_ns(path),
        )
        entries.append(entry)

    existing_subset = _load_existing_subset(
        conn,
        [str(entry["item_key"]) for entry in entries],
    )
    changed_entries = _filter_changed_entries(entries, existing_subset)
    indexed = int(upsert_entries(conn, changed_entries) or 0) if changed_entries else 0

    try:
        mark_synced(conn, "dirs")
    except Exception:
        pass

    try:
        conn.commit()
    except Exception:
        pass

    return {
        "indexed": indexed,
        "deleted": deleted,
        "total": int(module_entry_count(conn, "dirs") or 0),
        "skipped": 0,
        "reason": "quick_sync",
        "candidates": len(candidates),
        "scanned": int(scan_stats.get("scanned", 0) or 0),
        "walk_budget_per_root": int(scan_stats.get("walk_budget_per_root", 0) or 0),
    }


def sync_dirs_module(
    conn: sqlite3.Connection,
    base_path: Path,
) -> Dict[str, Any]:
    base_path = Path(base_path)
    roots = resolve_dirs_roots(base_path)
    if not roots:
        return {
            "indexed": 0,
            "deleted": 0,
            "total": int(module_entry_count(conn, "dirs") or 0),
            "skipped": 1,
            "reason": "no_dirs_roots",
            "candidates": 0,
        }

    entries: List[Dict[str, Any]] = []
    current_keys = set()

    rel_roots = [safe_rel(root, base_path) for root in roots]

    for root in roots:
        for path in _iter_dirs(root):
            if _should_skip_path(path):
                continue

            rel_path = safe_rel(path, base_path)
            entry = _build_dir_entry(
                rel_path=rel_path,
                dirname=path.name,
                mtime_ns=_mtime_ns(path),
            )
            entries.append(entry)
            current_keys.add(str(entry["item_key"]))

    existing_map = _existing_keys_for_module_roots(conn, "dirs", rel_roots)
    existing_keys = set()
    for keys in existing_map.values():
        existing_keys.update(keys)

    stale_keys = list(existing_keys - current_keys)
    deleted = _delete_item_keys(conn, stale_keys) if stale_keys else 0

    existing_subset = _load_existing_subset(
        conn,
        [str(entry["item_key"]) for entry in entries],
    )
    changed_entries = _filter_changed_entries(entries, existing_subset)
    indexed = int(upsert_entries(conn, changed_entries) or 0) if changed_entries else 0

    try:
        mark_synced(conn, "dirs")
    except Exception:
        pass

    try:
        conn.commit()
    except Exception:
        pass

    return {
        "indexed": indexed,
        "deleted": deleted,
        "total": int(module_entry_count(conn, "dirs") or 0),
        "skipped": 0,
        "reason": "full_sync",
        "candidates": len(entries),
    }


__all__ = [
    "FILE_MODULE_ROOT_CANDIDATES",
    "DIRS_ROOT_CANDIDATES",
    "resolve_file_module_root",
    "resolve_dirs_roots",
    "quick_sync_file_module",
    "sync_file_module",
    "quick_sync_dirs_module",
    "sync_dirs_module",
    "_build_file_content_entries",
]
