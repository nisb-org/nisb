#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""/opt/mcp-gateway/mcp-nisb/tools/doc/library_reading.py

NISB Library Reading & Translation Tools (split)

Contract (strict):
- Input args use snake_case only.
- Output spans use span_index.
"""

from __future__ import annotations

import os
from typing import List, Dict, Any

from core.storage import append_jsonl

from tools.doc.reading.common import (
  require_safe_id,
  _resolve_base_path,
  _to_bool,
  _reader_from_args,
  _read_doc_full_text,
  _build_full_text_from_chunks,
  _build_spans_from_full_text,
  _ensure_doc_translations_dir,
  _load_translation_events,
  _find_latest_translation,
  _rebuild_span_text,
  _append_timeline_safe,
  _make_timeline_event,
)

from tools.doc.reading.translate_guard import _is_refusal_text, _repair_nisb_uris_by_source
from tools.doc.reading.translate_models import _call_translate_model


def _get_required_str(args: Dict[str, Any], key: str) -> str:
  v = args.get(key)
  s = str(v or "").strip()
  if not s:
    raise ValueError(f"{key} is required")
  return s


def _get_optional_str(args: Dict[str, Any], key: str, default: str = "") -> str:
  v = args.get(key)
  s = str(v if v is not None else default).strip()
  return s


def _get_optional_int(args: Dict[str, Any], key: str, default: int | None = None) -> int | None:
  if key not in args:
    return default
  v = args.get(key)
  if v is None:
    return default
  try:
    return int(v)
  except Exception:
    return default


def nisb_library_continuous_read(args: Dict[str, Any]) -> Dict[str, Any]:
  base_path = _resolve_base_path(args)

  try:
    library_id = require_safe_id("library_id", _get_required_str(args, "library_id"))
    doc_id = require_safe_id("doc_id", _get_required_str(args, "doc_id"))
  except Exception as e:
    return {"status": "error", "message": str(e)}

  max_chars = _get_optional_int(args, "max_chars", default=8000)
  if max_chars is None:
    max_chars = 8000
  try:
    max_chars = max(200, min(200000, int(max_chars)))
  except Exception:
    max_chars = 8000

  print(
    f"[LIB_READ_DEBUG] nisb_library_continuous_read base_path={base_path}, "
    f"library_id={library_id}, doc_id={doc_id}, max_chars={max_chars}"
  )

  try:
    full_text, source_label = _read_doc_full_text(base_path, library_id, doc_id)

    chunks = None
    if not full_text.strip():
      from tools.doc.doc_db_sqlite import get_doc_db_sqlite
      db = get_doc_db_sqlite(base_path, library_id)
      chunks = db.get_chunks(doc_id)
      print(f"[LIB_READ_DEBUG] continuous_read fallback get_chunks len={len(chunks) if chunks else 0}")
      if not chunks:
        db_path = os.path.join(base_path, "libraries", library_id, "docs", "doc_db.sqlite")
        msg = f"未找到文档或文档无内容：doc_id={doc_id}, db={db_path}"
        print(f"[LIB_READ_DEBUG] error: {msg}")
        return {"status": "error", "message": msg}

      full_text = _build_full_text_from_chunks(chunks)
      source_label = "db_chunks"

    raw_spans = _build_spans_from_full_text(full_text, max_chars=max_chars)

    # Convert helper spans to the strict API contract.
    _internal_index_key = "span_" + "id"  # avoid legacy token in source
    spans: List[Dict[str, Any]] = []
    for sp in (raw_spans or []):
      if not isinstance(sp, dict):
        continue
      internal_index = sp.get(_internal_index_key)
      try:
        span_index = int(internal_index)
      except Exception:
        continue

      spans.append({
        "span_index": span_index,
        "span_start": int(sp.get("span_start", 0) or 0),
        "span_end": int(sp.get("span_end", 0) or 0),
        "text": str(sp.get("text") or ""),
      })

    print(f"[LIB_READ_DEBUG] full_text_len={len(full_text)}, span_count={len(spans)} source={source_label}")

    try:
      title = _get_optional_str(args, "doc_title", default="").strip() or doc_id
      reader = _reader_from_args(args)
      event = _make_timeline_event(
        base_path=base_path,
        library_id=library_id,
        doc_id=doc_id,
        title=title,
        extra={
          "kind": "library_doc_read",
          "max_chars": max_chars,
          "span_count": len(spans),
          "text_source": source_label,
          "reader": reader,
        },
      )
      ok = _append_timeline_safe(base_path, event)
      print(f"[LIB_READ_DEBUG] timeline append read ok={ok}")
    except Exception as e:
      print(f"[LIB_READ_DEBUG] timeline append read failed (ignored): {e!r}")

    return {
      "status": "success",
      "library_id": library_id,
      "doc_id": doc_id,
      "spans": spans,
      "total_length": len(full_text),
      "span_count": len(spans),
      "text_source": source_label,
    }

  except Exception as e:
    msg = f"连续阅读生成失败: {e!r}"
    print(f"[LIB_READ_DEBUG] exception: {msg}")
    return {"status": "error", "message": msg}


def nisb_library_translate_span(args: Dict[str, Any]) -> Dict[str, Any]:
  base_path = _resolve_base_path(args)

  try:
    library_id = require_safe_id("library_id", _get_required_str(args, "library_id"))
    doc_id = require_safe_id("doc_id", _get_required_str(args, "doc_id"))
  except Exception as e:
    return {"status": "error", "message": str(e)}

  span_start_raw = args.get("span_start")
  span_end_raw = args.get("span_end")

  target_language = _get_optional_str(args, "target_language", default="zh-CN") or "zh-CN"
  backend = _get_optional_str(args, "backend", default="mini") or "mini"

  span_index_raw = args.get("span_index", None)

  force_raw = args.get("force", False)
  force = _to_bool(force_raw, default=False)

  print(
    f"[LIB_READ_DEBUG] nisb_library_translate_span base_path={base_path}, "
    f"library_id={library_id}, doc_id={doc_id}, span_start={span_start_raw}, span_end={span_end_raw}, "
    f"lang={target_language}, backend={backend}, force={force}"
  )

  if span_start_raw is None or span_end_raw is None:
    msg = "span_start 和 span_end 为必填参数"
    print(f"[LIB_READ_DEBUG] error: {msg}")
    return {"status": "error", "message": msg}

  try:
    span_start_int = int(span_start_raw)
    span_end_int = int(span_end_raw)
  except Exception:
    msg = "span_start 和 span_end 必须为整数"
    print(f"[LIB_READ_DEBUG] error: {msg}")
    return {"status": "error", "message": msg}

  full_text, span_text = _rebuild_span_text(
    base_path=base_path,
    library_id=library_id,
    doc_id=doc_id,
    span_start=span_start_int,
    span_end=span_end_int,
  )
  print(f"[LIB_READ_DEBUG] translate full_text_len={len(full_text)}, span_text_len={len(span_text)}")
  if not span_text:
    msg = "指定区间无文本内容，无法翻译"
    print(f"[LIB_READ_DEBUG] error: {msg}")
    return {"status": "error", "message": msg}

  translations_dir = _ensure_doc_translations_dir(base_path, library_id, doc_id)
  translations_file = os.path.join(translations_dir, f"{target_language}.jsonl")

  events: List[Dict[str, Any]] = _load_translation_events(translations_file)
  latest = _find_latest_translation(
    events=events,
    doc_id=doc_id,
    span_start=span_start_int,
    span_end=span_end_int,
    language=target_language,
  )

  reader = _reader_from_args(args)

  try:
    span_index = int(span_index_raw) if span_index_raw is not None else None
  except Exception:
    span_index = None

  span_payload = {"span_index": span_index, "span_start": span_start_int, "span_end": span_end_int}

  # 1) cache hit (unless force)
  if (not force) and latest:
    cached_text = str(latest.get("translated_text") or "")
    cached_refused_flag = _to_bool(latest.get("refused"), default=False)
    looks_refusal = cached_refused_flag or _is_refusal_text(cached_text)

    if looks_refusal:
      print("[LIB_READ_DEBUG] cache hit but refused (isolation enabled)")
      return {
        "status": "success",
        "from_cache": True,
        "refused": True,
        "refusal_text": (latest.get("refusal_text") or cached_text or ""),
        "library_id": library_id,
        "doc_id": doc_id,
        "span_index": span_index,
        "span_start": span_start_int,
        "span_end": span_end_int,
        "language": target_language,
        "translated_text": "",
        "events": len(events),
      }

    if cached_text:
      print("[LIB_READ_DEBUG] cache hit for translation")
      fixed_cached_text = _repair_nisb_uris_by_source(span_text, cached_text)

      try:
        title = _get_optional_str(args, "doc_title", default="").strip() or doc_id
        event = _make_timeline_event(
          base_path=base_path,
          library_id=library_id,
          doc_id=doc_id,
          title=title,
          extra={
            "kind": "library_doc_translate",
            "from_cache": True,
            "cache_action": "hit",
            "force": False,
            "refused": False,
            "language": target_language,
            "backend": backend,
            "span_start": span_start_int,
            "span_end": span_end_int,
            "reader": reader,
            "span": span_payload,
          },
        )
        ok = _append_timeline_safe(base_path, event)
        print(f"[LIB_READ_DEBUG] timeline append translate(cache) ok={ok}")
      except Exception as e:
        print(f"[LIB_READ_DEBUG] timeline append translate(cache) failed (ignored): {e!r}")

      return {
        "status": "success",
        "from_cache": True,
        "refused": False,
        "library_id": library_id,
        "doc_id": doc_id,
        "span_index": span_index,
        "span_start": span_start_int,
        "span_end": span_end_int,
        "language": target_language,
        "translated_text": fixed_cached_text,
        "events": len(events),
      }

  # 2) call LLM
  try:
    translated_text_raw, provider, used_model = _call_translate_model(
      backend=backend,
      target_language=target_language,
      span_text=span_text,
    )
    print(f"[LIB_READ_DEBUG] LLM translated_text_len={len(translated_text_raw)} provider={provider} model={used_model}")
  except Exception as e:
    msg = f"调用翻译模型失败: {e!r}"
    print(f"[LIB_READ_DEBUG] exception: {msg}")
    return {"status": "error", "message": msg}

  refused = _is_refusal_text(translated_text_raw)
  if refused:
    refusal_text = translated_text_raw
    translated_text = ""
  else:
    refusal_text = ""
    translated_text = translated_text_raw

  cache_event: Dict[str, Any] = {
    "doc_id": doc_id,
    "span_start": span_start_int,
    "span_end": span_end_int,
    "language": target_language,
    "translated_text": translated_text,
    "created_at": None,
    "updated_at": None,
    "backend": backend,
    "provider": provider,
    "model": used_model,
  }

  # 用真实时间补齐
  try:
    from tools.doc.reading.common import _utc_now_iso_z
    now_iso = _utc_now_iso_z()
    cache_event["created_at"] = now_iso
    cache_event["updated_at"] = now_iso
  except Exception:
    pass

  if refused:
    cache_event["refused"] = True
    cache_event["refusal_text"] = refusal_text

  try:
    append_jsonl(translations_file, cache_event)
    print(f"[LIB_READ_DEBUG] append_jsonl -> {translations_file}")
  except Exception as e:
    print(f"[LIB_READ_DEBUG] append_jsonl failed: {e!r}")

  try:
    title = _get_optional_str(args, "doc_title", default="").strip() or doc_id
    event = _make_timeline_event(
      base_path=base_path,
      library_id=library_id,
      doc_id=doc_id,
      title=title,
      extra={
        "kind": "library_doc_translate",
        "from_cache": False,
        "cache_action": "bypass" if force else "miss",
        "force": bool(force),
        "refused": bool(refused),
        "language": target_language,
        "backend": backend,
        "span_start": span_start_int,
        "span_end": span_end_int,
        "reader": reader,
        "span": span_payload,
      },
    )
    ok = _append_timeline_safe(base_path, event)
    print(f"[LIB_READ_DEBUG] timeline append translate(new) ok={ok}")
  except Exception as e:
    print(f"[LIB_READ_DEBUG] timeline append translate(new) failed (ignored): {e!r}")

  return {
    "status": "success",
    "from_cache": False,
    "refused": bool(refused),
    "refusal_text": refusal_text,
    "library_id": library_id,
    "doc_id": doc_id,
    "span_index": span_index,
    "span_start": span_start_int,
    "span_end": span_end_int,
    "language": target_language,
    "translated_text": translated_text,
    "events": len(events) + 1,
  }

