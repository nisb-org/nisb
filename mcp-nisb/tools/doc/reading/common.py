#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import os
import json
import uuid
from datetime import datetime, timezone
from typing import List, Dict, Any, Tuple, Optional

from tools.doc.doc_db_sqlite import get_doc_db_sqlite
from core.storage import load_jsonl

# --- Timeline integration (optional) ---
try:
  from tools.timeline import _append_timeline_activity  # type: ignore
except Exception:
  _append_timeline_activity = None


def require_safe_id(field: str, value: str) -> str:
  """
  防止路径穿越：只允许 [a-zA-Z0-9_-]，且不能为空。
  """
  s = str(value or "").strip()
  if not s:
    raise ValueError(f"{field} is required")
  for ch in s:
    ok = ("a" <= ch <= "z") or ("A" <= ch <= "Z") or ("0" <= ch <= "9") or (ch in ("_", "-"))
    if not ok:
      raise ValueError(f"{field} has unsafe char: {ch!r}")
  return s


def _utc_now_iso_z() -> str:
  return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _resolve_base_path(args: Dict[str, Any]) -> str:
  if args.get("_base_path"):
    return str(args["_base_path"])
  if args.get("user_base_path"):
    return str(args["user_base_path"])
  if args.get("basepath"):
    return str(args["basepath"])

  user_id = args.get("user_id")
  root = os.environ.get("NISB_BASE_PATH", "/data")
  if user_id:
    return os.path.join(root, "users", str(user_id))
  return root


def _get_arg_any(args: Dict[str, Any], *names: str, default=None):
  for n in names:
    if n in args:
      v = args.get(n)
      if v is None:
        continue
      if isinstance(v, str) and not v.strip():
        continue
      return v
  return default


def _to_bool(v: Any, default: bool = False) -> bool:
  if v is None:
    return default
  if isinstance(v, bool):
    return v
  if isinstance(v, (int, float)):
    return bool(v)
  s = str(v).strip().lower()
  if s in ("1", "true", "t", "yes", "y", "on"):
    return True
  if s in ("0", "false", "f", "no", "n", "off"):
    return False
  return default


def _append_timeline_jsonl_fallback(base_path: str, event: Dict[str, Any]) -> bool:
  try:
    timeline_dir = os.path.join(base_path, "timeline")
    os.makedirs(timeline_dir, exist_ok=True)
    fp = os.path.join(timeline_dir, "activities.jsonl")
    with open(fp, "a", encoding="utf-8") as f:
      f.write(json.dumps(event, ensure_ascii=False) + "\n")
    return True
  except Exception as e:
    print(f"[LIB_READ_DEBUG] timeline append failed (jsonl fallback): {e!r}")
    return False


def _append_timeline_safe(base_path: str, event: Dict[str, Any]) -> bool:
  if _append_timeline_activity:
    fn = _append_timeline_activity

    try:
      fn(base_path, event)
      return True
    except TypeError:
      pass
    except Exception as e:
      print(f"[LIB_READ_DEBUG] timeline append failed (positional): {e!r}")

    try:
      fn(base_path=base_path, event=event)
      return True
    except TypeError:
      pass
    except Exception as e:
      print(f"[LIB_READ_DEBUG] timeline append failed (kw base_path/event): {e!r}")

    try:
      fn(base_path=base_path, activity=event)
      return True
    except TypeError:
      pass
    except Exception as e:
      print(f"[LIB_READ_DEBUG] timeline append failed (kw base_path/activity): {e!r}")

    try:
      fn({"_base_path": base_path, "event": event})
      return True
    except TypeError:
      pass
    except Exception as e:
      print(f"[LIB_READ_DEBUG] timeline append failed (dict event): {e!r}")

    try:
      fn({"_base_path": base_path, "activity": event})
      return True
    except Exception as e:
      print(f"[LIB_READ_DEBUG] timeline append failed (dict activity): {e!r}")

  return _append_timeline_jsonl_fallback(base_path, event)


def _library_doc_dir(base_path: str, library_id: str, doc_id: str) -> str:
  return os.path.join(base_path, "libraries", library_id, "docs", doc_id)


def _read_text_file(path: str) -> str:
  try:
    if not os.path.exists(path):
      return ""
    with open(path, "r", encoding="utf-8", errors="replace") as f:
      t = f.read()
    return str(t or "")
  except Exception:
    return ""


def _read_doc_full_text(base_path: str, library_id: str, doc_id: str) -> Tuple[str, str]:
  doc_dir = _library_doc_dir(base_path, library_id, doc_id)
  candidates = [
    ("content.txt", os.path.join(doc_dir, "content.txt")),
    ("full_text.txt", os.path.join(doc_dir, "full_text.txt")),
  ]
  for label, fp in candidates:
    t = _read_text_file(fp)
    if t.strip():
      return t, label
  return "", ""


def _build_full_text_from_chunks(chunks: List[Dict[str, Any]]) -> str:
  parts: List[str] = []
  for item in chunks:
    text = item.get("text") or ""
    if not text:
      continue
    text = str(text).strip("\n")
    if text:
      parts.append(text)
  return "\n\n".join(parts)


def _build_spans_from_full_text(full_text: str, max_chars: int) -> List[Dict[str, Any]]:
  spans: List[Dict[str, Any]] = []
  n = len(full_text)
  if n <= 0:
    return spans
  if max_chars <= 0:
    max_chars = n

  span_id = 0
  start = 0
  while start < n:
    end = min(start + max_chars, n)
    spans.append({
      "span_id": span_id,
      "span_start": start,
      "span_end": end,
      "text": full_text[start:end],
    })
    span_id += 1
    start = end

  return spans


def _ensure_doc_translations_dir(base_path: str, library_id: str, doc_id: str) -> str:
  translations_dir = os.path.join(base_path, "libraries", library_id, "docs", doc_id, "translations")
  os.makedirs(translations_dir, exist_ok=True)
  return translations_dir


def _load_translation_events(translations_file: str) -> List[Dict[str, Any]]:
  if not os.path.exists(translations_file):
    return []
  try:
    events = load_jsonl(translations_file)
    return events if isinstance(events, list) else []
  except Exception:
    return []


def _find_latest_translation(
  events: List[Dict[str, Any]],
  doc_id: str,
  span_start: int,
  span_end: int,
  language: str
) -> Optional[Dict[str, Any]]:
  latest: Optional[Dict[str, Any]] = None
  for ev in events:
    if (
      ev.get("doc_id") == doc_id
      and int(ev.get("span_start", -1)) == int(span_start)
      and int(ev.get("span_end", -1)) == int(span_end)
      and ev.get("language") == language
    ):
      latest = ev
  return latest


def _rebuild_span_text(
  base_path: str,
  library_id: str,
  doc_id: str,
  span_start: int,
  span_end: int
) -> Tuple[str, str]:
  print(f"[LIB_READ_DEBUG] _rebuild_span_text base_path={base_path}, library_id={library_id}, doc_id={doc_id}, span_start={span_start}, span_end={span_end}")

  full_text, source_label = _read_doc_full_text(base_path, library_id, doc_id)
  if not full_text.strip():
    db = get_doc_db_sqlite(base_path, library_id)
    chunks = db.get_chunks(doc_id)
    print(f"[LIB_READ_DEBUG] _rebuild_span_text fallback db chunks_len={len(chunks) if chunks else 0}")
    if not chunks:
      return "", ""
    full_text = _build_full_text_from_chunks(chunks)
    source_label = "db_chunks"

  text_len = len(full_text)
  print(f"[LIB_READ_DEBUG] _rebuild_span_text full_text_len={text_len} source={source_label}")
  if text_len == 0:
    return full_text, ""

  s = max(0, int(span_start))
  e = max(0, int(span_end))
  if s >= text_len:
    s = max(text_len - 1, 0)
  if e > text_len:
    e = text_len
  if e <= s:
    e = min(s + 1, text_len)

  return full_text, full_text[s:e]


def _reader_from_args(args: Dict[str, Any]) -> Dict[str, Any]:
  r = args.get("reader") or {}
  if not isinstance(r, dict):
    r = {}
  smart = r.get("smartPretranslate", r.get("smart_pretranslate", args.get("smart_pretranslate", False)))
  show_tr = r.get("showTranslation", r.get("show_translation", args.get("show_translation", False)))
  cont = r.get("continuous", args.get("continuous", False))
  lang = r.get("lang", r.get("targetLanguage", r.get("target_language", args.get("lang", "zh-CN"))))
  spans = r.get("pretranslateSpans", r.get("pretranslate_spans", args.get("pretranslate_spans", 2)))

  try:
    spans = int(spans)
  except Exception:
    spans = 2

  lang = str(lang or "zh-CN")
  if lang.lower().startswith("en"):
    lang = "en"

  return {
    "continuous": bool(cont),
    "showTranslation": bool(show_tr),
    "smartPretranslate": bool(smart),
    "pretranslateSpans": spans,
    "lang": lang,
  }


def _make_timeline_event(
  base_path: str,
  library_id: str,
  doc_id: str,
  title: str,
  extra: Dict[str, Any],
) -> Dict[str, Any]:
  return {
    "type": "document",
    "origin": "activity_log",
    "event_id": uuid.uuid4().hex,
    "date": _utc_now_iso_z(),
    "title": title,
    "path": _library_doc_dir(base_path, library_id, doc_id),
    "library_id": library_id,
    "doc_id": doc_id,
    "extra": extra,
  }

