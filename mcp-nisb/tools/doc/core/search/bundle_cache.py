from __future__ import annotations

import json
import os
import threading
from collections import OrderedDict
from typing import Any, Dict, List, Optional, Tuple

from tools.doc.doc_db_sqlite import get_doc_db_sqlite
from tools.doc.core.span_constants import SPAN_CHARS
from tools.doc.reading.common import _read_doc_full_text, _build_full_text_from_chunks
from tools.doc.core.chunk_offset_cache import get_offsets_map, save_cache, build_offsets_sequential_v2

from .common import _int_or_none, _parse_iso_dt

_METADATA_CACHE_LOCK = threading.RLock()
_METADATA_CACHE: "OrderedDict[str, Dict[str, Any]]" = OrderedDict()
_METADATA_CACHE_MAX = 4096

_DOC_BUNDLE_CACHE_LOCK = threading.RLock()
_DOC_BUNDLE_CACHE: "OrderedDict[str, Dict[str, Any]]" = OrderedDict()
_DOC_BUNDLE_CACHE_MAX = 96


def _doc_dir(base_path: str, library_id: str, doc_id: str) -> str:
    return os.path.join(base_path, "libraries", library_id, "docs", doc_id)


def _metadata_fp(base_path: str, library_id: str, doc_id: str) -> str:
    return os.path.join(_doc_dir(base_path, library_id, doc_id), "metadata.json")


def _read_doc_metadata_cached(metadata_fp: str) -> Dict[str, Any]:
    if not metadata_fp or not os.path.exists(metadata_fp):
        return {}

    try:
        mtime = os.path.getmtime(metadata_fp)
    except Exception:
        return {}

    with _METADATA_CACHE_LOCK:
        cached = _METADATA_CACHE.get(metadata_fp)
        if cached and float(cached.get("mtime") or -1.0) == float(mtime):
            _METADATA_CACHE.move_to_end(metadata_fp)
            return dict(cached.get("value") or {})

    try:
        with open(metadata_fp, "r", encoding="utf-8") as f:
            meta = json.load(f)
        if not isinstance(meta, dict):
            meta = {}
    except Exception:
        meta = {}

    with _METADATA_CACHE_LOCK:
        _METADATA_CACHE[metadata_fp] = {"mtime": float(mtime), "value": dict(meta)}
        _METADATA_CACHE.move_to_end(metadata_fp)
        while len(_METADATA_CACHE) > _METADATA_CACHE_MAX:
            _METADATA_CACHE.popitem(last=False)

    return meta


def _read_doc_published_at(metadata_fp: str):
    meta = _read_doc_metadata_cached(metadata_fp)
    if not isinstance(meta, dict):
        return None
    return _parse_iso_dt(str(meta.get("published_at") or "").strip())


def _load_doc_full_text_for_search(base_path: str, library_id: str, doc_id: str, chunks: List[Dict[str, Any]]) -> str:
    full_text, _source_label = _read_doc_full_text(base_path, library_id, doc_id)
    if full_text.strip():
        return full_text
    return _build_full_text_from_chunks(chunks)


def _span_fields_from_char_start(char_start: Optional[int], full_text_len: Optional[int]) -> Dict[str, Optional[int]]:
    if char_start is None:
        return {
            "span_index": None,
            "span_start": None,
            "span_end": None,
        }

    span_chars = max(1, int(SPAN_CHARS or 8000))
    span_index = max(0, int(char_start)) // span_chars
    span_start = span_index * span_chars
    span_end = span_start + span_chars

    if full_text_len is not None and full_text_len >= 0:
        span_end = min(full_text_len, span_end)

    return {
        "span_index": int(span_index),
        "span_start": int(span_start),
        "span_end": int(span_end),
    }


def _enrich_chunks_with_positions(
    *,
    base_path: str,
    library_id: str,
    doc_id: str,
    db: Any,
    chunks: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    if not chunks:
        return []

    all_have_ranges = True
    for c in chunks:
        if _int_or_none(c.get("char_start")) is None:
            all_have_ranges = False
            break

    full_text_len: Optional[int] = None

    if all_have_ranges:
        out: List[Dict[str, Any]] = []
        for c in chunks:
            char_start = _int_or_none(c.get("char_start"))
            char_end = _int_or_none(c.get("char_end"))
            if char_start is not None and char_end is None:
                char_end = char_start + len(str(c.get("text") or ""))

            span_meta = _span_fields_from_char_start(char_start, None)
            out.append(
                {
                    "chunk_id": c.get("chunk_id"),
                    "text": c.get("text"),
                    "char_start": char_start,
                    "char_end": char_end,
                    "span_index": span_meta["span_index"],
                    "span_start": span_meta["span_start"],
                    "span_end": span_meta["span_end"],
                }
            )
        return out

    full_text = _load_doc_full_text_for_search(base_path, library_id, doc_id, chunks)
    full_text_len = len(full_text) if full_text else None

    doc_dir = _doc_dir(base_path, library_id, doc_id)
    offsets_map = get_offsets_map(doc_dir, full_text) if full_text else {}

    need_build = False
    for c in chunks:
        if _int_or_none(c.get("char_start")) is not None:
            continue
        ck = str(c.get("chunk_id"))
        if ck not in offsets_map:
            need_build = True
            break

    if need_build and full_text:
        built_offsets, _methods = build_offsets_sequential_v2(full_text, chunks)
        if built_offsets:
            merged = dict(offsets_map)
            merged.update({str(k): int(v) for k, v in built_offsets.items()})
            offsets_map = merged
            try:
                save_cache(doc_dir, full_text, offsets_map)
            except Exception:
                pass

    to_persist: List[Tuple[int, int, int]] = []
    out = []

    for c in chunks:
        chunk_id = _int_or_none(c.get("chunk_id"))
        text = str(c.get("text") or "")
        char_start = _int_or_none(c.get("char_start"))
        char_end = _int_or_none(c.get("char_end"))

        if char_start is None:
            off = offsets_map.get(str(c.get("chunk_id")))
            char_start = _int_or_none(off)
            if char_start is not None:
                if full_text_len is not None:
                    char_end = min(full_text_len, char_start + len(text))
                else:
                    char_end = char_start + len(text)

                if chunk_id is not None:
                    to_persist.append((chunk_id, char_start, int(char_end)))

        elif char_end is None:
            if full_text_len is not None:
                char_end = min(full_text_len, char_start + len(text))
            else:
                char_end = char_start + len(text)

        span_meta = _span_fields_from_char_start(char_start, full_text_len)

        out.append(
            {
                "chunk_id": c.get("chunk_id"),
                "text": c.get("text"),
                "char_start": char_start,
                "char_end": char_end,
                "span_index": span_meta["span_index"],
                "span_start": span_meta["span_start"],
                "span_end": span_meta["span_end"],
            }
        )

    if to_persist:
        try:
            db.update_chunk_char_ranges_bulk(doc_id=doc_id, chunk_ranges=to_persist)
        except Exception as e:
            print(f"[HYBRID_DEBUG] persist chunk char ranges failed doc_id={doc_id}: {e}")

    return out


def _db_mtime(db_path: str) -> float:
    try:
        return float(os.path.getmtime(db_path))
    except Exception:
        return 0.0


def _lru_put(cache: OrderedDict, key: str, value: Dict[str, Any], max_size: int) -> None:
    cache[key] = value
    cache.move_to_end(key)
    while len(cache) > max_size:
        cache.popitem(last=False)


def _get_doc_bundle_cached(base_path: str, library_id: str, doc_id: str) -> Dict[str, Any]:
    db = get_doc_db_sqlite(base_path, library_id)
    db_path = str(db.db_path)
    cache_key = f"{db_path}::{doc_id}"
    current_mtime = _db_mtime(db_path)

    with _DOC_BUNDLE_CACHE_LOCK:
        cached = _DOC_BUNDLE_CACHE.get(cache_key)
        if cached and float(cached.get("db_mtime") or -1.0) == current_mtime:
            _DOC_BUNDLE_CACHE.move_to_end(cache_key)
            return cached

    embeddings_matrix, _chunk_ids = db.get_all_embeddings_as_matrix(doc_id)
    raw_chunks = db.get_chunks(doc_id)
    chunks = _enrich_chunks_with_positions(
        base_path=base_path,
        library_id=library_id,
        doc_id=doc_id,
        db=db,
        chunks=raw_chunks,
    )

    bundle: Dict[str, Any] = {
        "db_mtime": current_mtime,
        "embeddings_matrix": embeddings_matrix,
        "chunks": chunks,
        "chunk_map": {int(c["chunk_id"]): c for c in chunks if _int_or_none(c.get("chunk_id")) is not None},
    }

    with _DOC_BUNDLE_CACHE_LOCK:
        _lru_put(_DOC_BUNDLE_CACHE, cache_key, bundle, _DOC_BUNDLE_CACHE_MAX)

    return bundle


def _lookup_chunk_from_bundle(base_path: str, library_id: str, doc_id: str, chunk_id: int) -> Optional[Dict[str, Any]]:
    try:
        bundle = _get_doc_bundle_cached(base_path, library_id, doc_id)
        chunk_map = bundle.get("chunk_map") or {}
        return chunk_map.get(int(chunk_id))
    except Exception:
        return None
