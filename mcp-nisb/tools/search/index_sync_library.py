#!/usr/bin/env python3

import json
import sqlite3
import time
from pathlib import Path
from typing import Any, Dict, List, Tuple

from .common import (
    JSON_EXTENSIONS,
    LIBRARY_SCAN_SUBDIRS,
    TEXT_EXTENSIONS_NO_JSON,
    build_index_excerpt,
    read_text_cached,
    scan_dir_files,
)
from .index_shared import (
    SNIPPET_EXCERPT_CHARS,
    build_content_blocks,
    derive_title_aliases,
    read_small_excerpt,
    safe_rel,
)
from .index_store import delete_stale, load_existing_map, upsert_entries
from .index_sync_state import mark_synced, module_entry_count


def _build_library_content_entries(
    library_id: str,
    library_name: str,
    doc_id: str,
    rel_path: str,
    filename: str,
    title: str,
    mtime_ns: int,
    size: int,
    raw_text: str,
    max_blocks: int = 12,
    block_chars: int = 320,
) -> List[Dict[str, Any]]:
    text = str(raw_text or "").strip()
    if not text:
        return []

    blocks = build_content_blocks(
        text,
        block_chars=block_chars,
        max_blocks=max_blocks,
    )

    out: List[Dict[str, Any]] = []
    doc_key = doc_id or rel_path or filename or title
    display_title = title or filename or doc_key

    for idx, block in enumerate(blocks):
        out.append(
            {
                "item_key": f"library_content::{library_id}::{doc_key}::{idx}",
                "module": "library",
                "source_kind": "library_content",
                "group_key": library_id,
                "path": rel_path,
                "filename": filename,
                "title": display_title,
                "library_id": library_id,
                "library_name": library_name,
                "doc_id": doc_id or doc_key,
                "conv_id": "",
                "created_at": "",
                "turn_count": 0,
                "snippet": block,
                "priority_hint": 18 if idx == 0 else 17,
                "mtime_ns": mtime_ns,
                "size": size,
            }
        )
    return out


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
            out[str(row["item_key"])] = (int(row["mtime_ns"] or 0), int(row["size"] or 0))
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


def _append_full_sync_entries(
    entries: List[Dict[str, Any]],
    existing: Dict[str, Tuple[int, int]],
    current_keys: set,
    candidate_entries: List[Dict[str, Any]],
) -> None:
    for entry in candidate_entries:
        key = str(entry.get("item_key", ""))
        current_keys.add(key)
        stamp = (
            int(entry.get("mtime_ns", 0) or 0),
            int(entry.get("size", 0) or 0),
        )
        if existing.get(key) == stamp:
            continue
        entries.append(entry)


def _read_library_meta(lib_dir: Path) -> Dict[str, Any]:
    library_id = lib_dir.name
    meta_file = lib_dir / "library.json"
    meta: Dict[str, Any] = {}
    meta_mtime = 0
    meta_size = 0

    if meta_file.exists():
        try:
            st = meta_file.stat()
            meta_mtime = int(st.st_mtime_ns)
            meta_size = int(st.st_size)
            with open(meta_file, "r", encoding="utf-8") as f:
                meta = json.load(f)
        except Exception:
            meta = {}

    library_name = str(meta.get("library_name", library_id) or library_id)
    description = str(meta.get("description", "") or "")

    return {
        "library_id": library_id,
        "library_name": library_name,
        "description": description,
        "meta_file": meta_file,
        "meta_mtime": meta_mtime,
        "meta_size": meta_size,
    }


def _build_library_meta_entry(
    base_path: Path,
    lib_dir: Path,
    meta_info: Dict[str, Any],
) -> Dict[str, Any]:
    meta_file = meta_info["meta_file"]
    return {
        "item_key": f"library_meta::{meta_info['library_id']}",
        "module": "library",
        "source_kind": "library_meta",
        "group_key": meta_info["library_id"],
        "path": safe_rel(meta_file, base_path) if meta_file.exists() else safe_rel(lib_dir, base_path),
        "filename": meta_file.name if meta_file.exists() else "",
        "title": meta_info["library_name"],
        "library_id": meta_info["library_id"],
        "library_name": meta_info["library_name"],
        "doc_id": "",
        "conv_id": "",
        "created_at": "",
        "turn_count": 0,
        "snippet": build_index_excerpt(meta_info["description"], max_chars=500),
        "priority_hint": 30,
        "mtime_ns": int(meta_info["meta_mtime"] or 0),
        "size": int(meta_info["meta_size"] or 0),
    }


def _collect_library_doc_dir_entries(
    base_path: Path,
    library_id: str,
    library_name: str,
    doc_dir: Path,
) -> List[Dict[str, Any]]:
    metadata_file = doc_dir / "metadata.json"
    content_file = doc_dir / "content.txt"
    if not metadata_file.exists():
        return []

    try:
        meta_stat = metadata_file.stat()
    except Exception:
        return []

    content_mtime = 0
    content_size = 0
    if content_file.exists():
        try:
            cst = content_file.stat()
            content_mtime = int(cst.st_mtime_ns)
            content_size = int(cst.st_size)
        except Exception:
            content_mtime = 0
            content_size = 0

    mtime_ns = max(int(meta_stat.st_mtime_ns), content_mtime)
    size = int(meta_stat.st_size) + content_size

    try:
        with open(metadata_file, "r", encoding="utf-8") as f:
            meta = json.load(f)
    except Exception:
        meta = {}

    doc_id = str(meta.get("doc_id", "") or doc_dir.name)
    filename = str(meta.get("filename", "") or "")
    title = str(meta.get("title", "") or "")
    display_title = str(meta.get("display_title", "") or "")
    book_title = str(meta.get("book_title", "") or "")
    name = str(meta.get("name", "") or "")

    aliases = derive_title_aliases(
        title,
        display_title,
        book_title,
        name,
        filename,
        doc_id,
        doc_dir.name,
    )

    best_title = ""
    for candidate in aliases:
        if candidate and not candidate.startswith("doc_") and candidate.lower() not in {"metadata", "content"}:
            best_title = candidate
            break
    if not best_title:
        best_title = filename or doc_id

    raw_text = ""
    if content_file.exists():
        raw_text = read_text_cached(content_file) or ""

    content_excerpt = ""
    if content_file.exists():
        content_excerpt = read_small_excerpt(content_file, max_chars=SNIPPET_EXCERPT_CHARS) or ""

    snippet_parts = []
    if aliases:
        snippet_parts.append(" ".join(aliases[:8]))
    if content_excerpt:
        snippet_parts.append(content_excerpt)
    snippet = build_index_excerpt(" ".join(snippet_parts), max_chars=SNIPPET_EXCERPT_CHARS)

    rel_path = safe_rel(doc_dir, base_path)
    entries: List[Dict[str, Any]] = [
        {
            "item_key": f"library_doc_dir::{library_id}::{doc_id}",
            "module": "library",
            "source_kind": "library_doc_dir",
            "group_key": library_id,
            "path": rel_path,
            "filename": filename or doc_dir.name,
            "title": best_title,
            "library_id": library_id,
            "library_name": library_name,
            "doc_id": doc_id,
            "conv_id": "",
            "created_at": "",
            "turn_count": 0,
            "snippet": snippet,
            "priority_hint": 28,
            "mtime_ns": mtime_ns,
            "size": size,
        }
    ]

    entries.extend(
        _build_library_content_entries(
            library_id=library_id,
            library_name=library_name,
            doc_id=doc_id,
            rel_path=rel_path,
            filename=filename or doc_dir.name,
            title=best_title,
            mtime_ns=mtime_ns,
            size=size,
            raw_text=raw_text,
            max_blocks=12,
            block_chars=320,
        )
    )
    return entries


def _collect_library_doc_json_entries(
    base_path: Path,
    library_id: str,
    library_name: str,
    lib_dir: Path,
    path: Path,
) -> List[Dict[str, Any]]:
    try:
        st = path.stat()
    except Exception:
        return []

    rel_path = safe_rel(path, base_path)
    rel_in_lib = safe_rel(path, lib_dir)
    mtime_ns = int(st.st_mtime_ns)
    size = int(st.st_size)

    raw = read_text_cached(path)
    title = path.stem
    content = ""

    if raw:
        try:
            doc = json.loads(raw)
            title = str(doc.get("title", "") or path.stem)
            content = str(doc.get("content", "") or "")
        except Exception:
            content = raw[:SNIPPET_EXCERPT_CHARS]

    aliases = derive_title_aliases(title, path.name, path.stem)
    best_title = aliases[0] if aliases else title
    snippet = build_index_excerpt((" ".join(aliases[:6]) + " " + content).strip(), max_chars=SNIPPET_EXCERPT_CHARS)

    entries: List[Dict[str, Any]] = [
        {
            "item_key": f"library_doc_json::{library_id}::{rel_in_lib}",
            "module": "library",
            "source_kind": "library_doc_json",
            "group_key": library_id,
            "path": rel_path,
            "filename": path.name,
            "title": best_title,
            "library_id": library_id,
            "library_name": library_name,
            "doc_id": best_title,
            "conv_id": "",
            "created_at": "",
            "turn_count": 0,
            "snippet": snippet,
            "priority_hint": 24,
            "mtime_ns": mtime_ns,
            "size": size,
        }
    ]

    entries.extend(
        _build_library_content_entries(
            library_id=library_id,
            library_name=library_name,
            doc_id=best_title,
            rel_path=rel_path,
            filename=path.name,
            title=best_title,
            mtime_ns=mtime_ns,
            size=size,
            raw_text=content,
            max_blocks=10,
            block_chars=320,
        )
    )
    return entries


def _collect_library_file_entries(
    base_path: Path,
    library_id: str,
    library_name: str,
    lib_dir: Path,
    path: Path,
) -> List[Dict[str, Any]]:
    try:
        st = path.stat()
    except Exception:
        return []

    rel_path = safe_rel(path, base_path)
    rel_in_lib = safe_rel(path, lib_dir)
    mtime_ns = int(st.st_mtime_ns)
    size = int(st.st_size)

    aliases = derive_title_aliases(path.name, path.stem)
    best_title = aliases[0] if aliases else path.name
    raw_text = read_text_cached(path) or ""
    excerpt = ""
    if raw_text:
        excerpt = build_index_excerpt(raw_text, max_chars=SNIPPET_EXCERPT_CHARS)
    else:
        excerpt = read_small_excerpt(path, max_chars=SNIPPET_EXCERPT_CHARS) or ""

    entries: List[Dict[str, Any]] = [
        {
            "item_key": f"library_file::{library_id}::{rel_in_lib}",
            "module": "library",
            "source_kind": "library_file",
            "group_key": library_id,
            "path": rel_path,
            "filename": path.name,
            "title": best_title,
            "library_id": library_id,
            "library_name": library_name,
            "doc_id": rel_in_lib,
            "conv_id": "",
            "created_at": "",
            "turn_count": 0,
            "snippet": (" ".join(aliases[:6]) + " " + excerpt).strip(),
            "priority_hint": 22,
            "mtime_ns": mtime_ns,
            "size": size,
        }
    ]

    entries.extend(
        _build_library_content_entries(
            library_id=library_id,
            library_name=library_name,
            doc_id=rel_in_lib,
            rel_path=rel_path,
            filename=path.name,
            title=best_title,
            mtime_ns=mtime_ns,
            size=size,
            raw_text=raw_text,
            max_blocks=10,
            block_chars=320,
        )
    )
    return entries


def sync_library_doc_dirs(
    entries: List[Dict[str, Any]],
    existing: Dict[str, Tuple[int, int]],
    current_keys: set,
    base_path: Path,
    library_id: str,
    library_name: str,
    docs_dir: Path,
) -> None:
    for doc_dir in docs_dir.iterdir():
        if not doc_dir.is_dir():
            continue
        candidate_entries = _collect_library_doc_dir_entries(
            base_path=base_path,
            library_id=library_id,
            library_name=library_name,
            doc_dir=doc_dir,
        )
        _append_full_sync_entries(entries, existing, current_keys, candidate_entries)


def sync_library_loose_files(
    entries: List[Dict[str, Any]],
    existing: Dict[str, Tuple[int, int]],
    current_keys: set,
    base_path: Path,
    library_id: str,
    library_name: str,
    lib_dir: Path,
) -> None:
    docs_dir = lib_dir / "docs"
    if docs_dir.exists():
        for path in scan_dir_files(docs_dir, recursive=True, suffixes=JSON_EXTENSIONS):
            if path.name == "metadata.json" and path.parent.name.startswith("doc_"):
                continue
            candidate_entries = _collect_library_doc_json_entries(
                base_path=base_path,
                library_id=library_id,
                library_name=library_name,
                lib_dir=lib_dir,
                path=path,
            )
            _append_full_sync_entries(entries, existing, current_keys, candidate_entries)

    for subdir_name in LIBRARY_SCAN_SUBDIRS:
        subdir = lib_dir / subdir_name
        if not subdir.exists():
            continue

        for path in scan_dir_files(subdir, recursive=True, suffixes=TEXT_EXTENSIONS_NO_JSON):
            if path.parent.name.startswith("doc_") and path.name == "content.txt":
                continue
            candidate_entries = _collect_library_file_entries(
                base_path=base_path,
                library_id=library_id,
                library_name=library_name,
                lib_dir=lib_dir,
                path=path,
            )
            _append_full_sync_entries(entries, existing, current_keys, candidate_entries)


def sync_library(conn: sqlite3.Connection, base_path: Path) -> Dict[str, int]:
    module = "library"
    existing = load_existing_map(conn, module)
    current_keys = set()
    entries: List[Dict[str, Any]] = []

    libraries_root = base_path / "libraries"
    if libraries_root.exists():
        for lib_dir in libraries_root.iterdir():
            if not lib_dir.is_dir():
                continue

            meta_info = _read_library_meta(lib_dir)
            meta_entry = _build_library_meta_entry(base_path, lib_dir, meta_info)
            _append_full_sync_entries(entries, existing, current_keys, [meta_entry])

            docs_dir = lib_dir / "docs"
            if docs_dir.exists():
                sync_library_doc_dirs(
                    entries=entries,
                    existing=existing,
                    current_keys=current_keys,
                    base_path=base_path,
                    library_id=meta_info["library_id"],
                    library_name=meta_info["library_name"],
                    docs_dir=docs_dir,
                )

            sync_library_loose_files(
                entries=entries,
                existing=existing,
                current_keys=current_keys,
                base_path=base_path,
                library_id=meta_info["library_id"],
                library_name=meta_info["library_name"],
                lib_dir=lib_dir,
            )

    updated = upsert_entries(conn, entries)
    deleted = delete_stale(conn, module, current_keys, existing)
    total = len(current_keys)
    mark_synced(conn, module, total=total)
    return {"indexed": updated, "deleted": deleted, "total": total}


def quick_sync_library(
    conn: sqlite3.Connection,
    base_path: Path,
    within_seconds: int = 300,
    max_candidates: int = 200,
) -> Dict[str, int]:
    cutoff_ns = int((time.time() - max(1, int(within_seconds))) * 1_000_000_000)
    candidate_entries: List[Dict[str, Any]] = []
    candidate_units = 0

    libraries_root = base_path / "libraries"
    if libraries_root.exists():
        for lib_dir in libraries_root.iterdir():
            if candidate_units >= max(1, int(max_candidates)):
                break
            if not lib_dir.is_dir():
                continue

            meta_info = _read_library_meta(lib_dir)

            if int(meta_info["meta_mtime"] or 0) >= cutoff_ns:
                candidate_entries.append(_build_library_meta_entry(base_path, lib_dir, meta_info))
                candidate_units += 1
                if candidate_units >= max(1, int(max_candidates)):
                    break

            docs_dir = lib_dir / "docs"
            if docs_dir.exists():
                for doc_dir in docs_dir.iterdir():
                    if candidate_units >= max(1, int(max_candidates)):
                        break
                    if not doc_dir.is_dir():
                        continue

                    metadata_file = doc_dir / "metadata.json"
                    content_file = doc_dir / "content.txt"

                    recent = False
                    if metadata_file.exists():
                        try:
                            if int(metadata_file.stat().st_mtime_ns) >= cutoff_ns:
                                recent = True
                        except Exception:
                            pass
                    if not recent and content_file.exists():
                        try:
                            if int(content_file.stat().st_mtime_ns) >= cutoff_ns:
                                recent = True
                        except Exception:
                            pass
                    if not recent:
                        continue

                    candidate_entries.extend(
                        _collect_library_doc_dir_entries(
                            base_path=base_path,
                            library_id=meta_info["library_id"],
                            library_name=meta_info["library_name"],
                            doc_dir=doc_dir,
                        )
                    )
                    candidate_units += 1

                if candidate_units < max(1, int(max_candidates)):
                    for path in scan_dir_files(docs_dir, recursive=True, suffixes=JSON_EXTENSIONS):
                        if candidate_units >= max(1, int(max_candidates)):
                            break
                        if path.name == "metadata.json" and path.parent.name.startswith("doc_"):
                            continue
                        try:
                            st = path.stat()
                        except Exception:
                            continue
                        if int(st.st_mtime_ns) < cutoff_ns:
                            continue

                        candidate_entries.extend(
                            _collect_library_doc_json_entries(
                                base_path=base_path,
                                library_id=meta_info["library_id"],
                                library_name=meta_info["library_name"],
                                lib_dir=lib_dir,
                                path=path,
                            )
                        )
                        candidate_units += 1

            for subdir_name in LIBRARY_SCAN_SUBDIRS:
                if candidate_units >= max(1, int(max_candidates)):
                    break
                subdir = lib_dir / subdir_name
                if not subdir.exists():
                    continue

                for path in scan_dir_files(subdir, recursive=True, suffixes=TEXT_EXTENSIONS_NO_JSON):
                    if candidate_units >= max(1, int(max_candidates)):
                        break
                    if path.parent.name.startswith("doc_") and path.name == "content.txt":
                        continue
                    try:
                        st = path.stat()
                    except Exception:
                        continue
                    if int(st.st_mtime_ns) < cutoff_ns:
                        continue

                    candidate_entries.extend(
                        _collect_library_file_entries(
                            base_path=base_path,
                            library_id=meta_info["library_id"],
                            library_name=meta_info["library_name"],
                            lib_dir=lib_dir,
                            path=path,
                        )
                    )
                    candidate_units += 1

    existing_subset = _load_existing_subset(
        conn,
        [str(entry.get("item_key", "")) for entry in candidate_entries],
    )
    changed_entries = _filter_changed_entries(candidate_entries, existing_subset)
    updated = upsert_entries(conn, changed_entries)
    total = module_entry_count(conn, "library")
    return {
        "indexed": updated,
        "deleted": 0,
        "total": total,
        "candidates": candidate_units,
    }


__all__ = [
    "_build_library_content_entries",
    "sync_library_doc_dirs",
    "sync_library_loose_files",
    "sync_library",
    "quick_sync_library",
]

