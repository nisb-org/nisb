#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import base64
import errno
import inspect
import json
import os
import re
import shutil
import tempfile
from typing import Any, Dict, List, Tuple

from tools.doc.reading.common import (
    require_safe_id,
    _resolve_base_path,
    _to_bool,
    _read_doc_full_text,
    _build_full_text_from_chunks,
    _build_spans_from_full_text,
    _ensure_doc_translations_dir,
    _load_translation_events,
    _find_latest_translation,
    _append_timeline_safe,
    _make_timeline_event,
)
from tools.i18n.backend_i18n import i18n_text, normalize_backend_locale

try:
    from reportlab.lib.units import mm
    from reportlab.pdfgen import canvas
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.pdfbase.cidfonts import UnicodeCIDFont

    REPORTLAB_AVAILABLE = True
except Exception:
    REPORTLAB_AVAILABLE = False

from .pdf_export.pdf_renderer import PDFRenderer
from .pdf_export.pdf_content_builder import (
    load_active_span_annotations,
    build_export_span_records,
    build_export_content,
)
from .pdf_export.pdf_style_config import PDFStyleConfig


AUTO_TARGET_LANGUAGE_TOKENS = {
    "",
    "auto",
    "default",
    "current",
    "latest",
    "detect",
    "detected",
    "available",
    "__auto__",
}


def _safe_args(args: Dict[str, Any] | None) -> Dict[str, Any]:
    return args if isinstance(args, dict) else {}


def _locale(args: Dict[str, Any] | None) -> str:
    return normalize_backend_locale(_safe_args(args).get("locale"))


def _txt(args: Dict[str, Any] | None, en: str, zh: str) -> str:
    return i18n_text(_locale(args), {"en": en, "zh-CN": zh}, en)


def _fmt(args: Dict[str, Any] | None, en: str, zh: str, **kwargs: Any) -> str:
    return _txt(args, en, zh).format(**kwargs)


def _tool_entry(kind: str, data: Dict[str, Any] | None = None) -> Dict[str, Any]:
    return {"kind": kind, "data": data or {}}


def _ok(
    kind: str,
    message: str,
    *,
    tool_data: Dict[str, Any] | None = None,
    **fields: Any,
) -> Dict[str, Any]:
    out: Dict[str, Any] = {
        "status": "success",
        "success": True,
        "message": message,
        "response": message,
        "tool_results": [_tool_entry(kind, tool_data or {})],
    }
    out.update(fields)
    return out


def _err(
    args: Dict[str, Any],
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


def _get_required_str(args: Dict[str, Any], key: str) -> str:
    v = args.get(key)
    s = str(v or "").strip()
    if not s:
        raise ValueError(f"{key} is required")
    return s


def _get_optional_str(args: Dict[str, Any], key: str, default: str = "") -> str:
    v = args.get(key)
    return str(v if v is not None else default).strip()


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


def _get_optional_float(args: Dict[str, Any], key: str, default: float | None = None) -> float | None:
    if key not in args:
        return default
    v = args.get(key)
    if v is None or str(v).strip() == "":
        return default
    try:
        return float(v)
    except Exception:
        return default


def _read_json(path: str, default: Any) -> Any:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def _safe_export_filename(name: str) -> str:
    s = str(name or "").strip()
    if not s:
        s = "translated_export.pdf"
    s = s.replace("\\", "_").replace("/", "_")
    s = re.sub(r'[:*?"<>|]+', "_", s)
    s = re.sub(r"\s+", " ", s).strip()
    if not s.lower().endswith(".pdf"):
        s += ".pdf"
    return s


def _make_export_filename(args: Dict[str, Any], original_filename: str, target_language: str, filename_override: str = "") -> str:
    if filename_override:
        return _safe_export_filename(filename_override)

    raw = str(original_filename or "").strip() or "document"
    base, _ext = os.path.splitext(raw)
    if not base:
        base = raw

    suffix = _txt(args, "full_translation", "完整译文")
    return _safe_export_filename(f"{base}_{suffix}_{target_language}.pdf")


def _doc_dir(base_path: str, library_id: str, doc_id: str) -> str:
    return os.path.join(base_path, "libraries", library_id, "docs", doc_id)


def _normalize_user_rel_dir(rel_dir: str) -> str:
    v = str(rel_dir or "").strip().replace("\\", "/")
    while "//" in v:
        v = v.replace("//", "/")
    while v.startswith("/"):
        v = v[1:]
    while v.endswith("/"):
        v = v[:-1]

    parts = []
    for part in v.split("/"):
        part = str(part or "").strip()
        if not part or part == ".":
            continue
        if part == "..":
            raise ValueError("export_user_dir contains invalid path segment '..'")
        parts.append(part)

    return "/".join(parts)


def _resolve_export_dir(base_path: str, library_id: str, doc_id: str, export_user_dir: str) -> tuple[str, str, str]:
    rel_dir = _normalize_user_rel_dir(export_user_dir or "")

    if rel_dir:
        user_root = os.path.realpath(base_path)
        export_dir = os.path.realpath(os.path.join(base_path, rel_dir))
        if not (export_dir == user_root or export_dir.startswith(user_root + os.sep)):
            raise ValueError("export_user_dir escapes user root")
        os.makedirs(export_dir, exist_ok=True)
        return export_dir, rel_dir, "user_dir"

    default_rel_dir = f"agent_files/library_translated_exports/{library_id}/{doc_id}"
    export_dir = os.path.join(base_path, default_rel_dir)
    os.makedirs(export_dir, exist_ok=True)
    return export_dir, default_rel_dir, "agent_files"


def _load_doc_filename(base_path: str, library_id: str, doc_id: str) -> str:
    meta_path = os.path.join(_doc_dir(base_path, library_id, doc_id), "metadata.json")
    meta = _read_json(meta_path, {})
    filename = str(meta.get("filename") or "").strip()
    return filename or doc_id


def _load_doc_text_and_spans(
    args: Dict[str, Any],
    base_path: str,
    library_id: str,
    doc_id: str,
    max_chars: int,
) -> Tuple[str, List[Dict[str, Any]], str]:
    full_text, source_label = _read_doc_full_text(base_path, library_id, doc_id)

    if not str(full_text or "").strip():
        from tools.doc.doc_db_sqlite import get_doc_db_sqlite

        db = get_doc_db_sqlite(base_path, library_id)
        chunks = db.get_chunks(doc_id)
        if not chunks:
            raise ValueError(
                _fmt(
                    args,
                    "Document text not found: library_id={library_id}, doc_id={doc_id}",
                    "未找到文档正文：library_id={library_id}, doc_id={doc_id}",
                    library_id=library_id,
                    doc_id=doc_id,
                )
            )
        full_text = _build_full_text_from_chunks(chunks)
        source_label = "db_chunks"

    raw_spans = _build_spans_from_full_text(full_text, max_chars=max_chars)
    internal_index_key = "span_" + "id"

    spans: List[Dict[str, Any]] = []
    for sp in raw_spans or []:
        if not isinstance(sp, dict):
            continue
        try:
            span_index = int(sp.get(internal_index_key))
        except Exception:
            continue
        spans.append(
            {
                "span_index": span_index,
                "span_start": int(sp.get("span_start", 0) or 0),
                "span_end": int(sp.get("span_end", 0) or 0),
                "text": str(sp.get("text") or ""),
            }
        )

    return full_text, spans, source_label


def _latest_translation_map(
    translations_file: str,
    doc_id: str,
    target_language: str,
    spans: List[Dict[str, Any]],
) -> Dict[Tuple[int, int], Dict[str, Any]]:
    events = _load_translation_events(translations_file)
    latest_map: Dict[Tuple[int, int], Dict[str, Any]] = {}

    for sp in spans:
        span_start = int(sp.get("span_start", 0) or 0)
        span_end = int(sp.get("span_end", 0) or 0)
        latest = _find_latest_translation(
            events=events,
            doc_id=doc_id,
            span_start=span_start,
            span_end=span_end,
            language=target_language,
        )
        if latest:
            latest_map[(span_start, span_end)] = latest

    return latest_map


def _translation_file_for(translations_dir: str, language: str) -> str:
    return os.path.join(translations_dir, f"{str(language or '').strip()}.jsonl")


def _list_available_translation_languages(translations_dir: str) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    if not os.path.isdir(translations_dir):
        return out

    try:
        names = sorted(os.listdir(translations_dir))
    except Exception:
        names = []

    for name in names:
        if not name.endswith(".jsonl"):
            continue

        language = name[:-6].strip()
        if not language:
            continue

        path = os.path.join(translations_dir, name)
        try:
            stat = os.stat(path)
            size = int(stat.st_size)
            mtime = float(stat.st_mtime)
        except Exception:
            size = 0
            mtime = 0.0

        if size <= 0:
            continue

        out.append(
            {
                "language": language,
                "path": path,
                "size_bytes": size,
                "mtime": mtime,
            }
        )

    out.sort(key=lambda row: (float(row.get("mtime") or 0), str(row.get("language") or "")), reverse=True)
    return out


def _language_aliases(language: str) -> List[str]:
    raw = str(language or "").strip()
    if not raw:
        return []

    low = raw.lower().replace("_", "-")
    aliases = [raw]

    if low in {"zh", "zh-cn", "zh-hans", "cn", "chinese", "chinese-simplified", "中文", "简体中文"}:
        aliases.extend(["zh-CN", "zh", "zh-Hans"])
    elif low in {"zh-tw", "zh-hant", "traditional-chinese", "chinese-traditional"}:
        aliases.extend(["zh-TW", "zh-Hant"])
    elif low in {"en", "en-us", "en-gb", "english"}:
        aliases.extend(["en", "en-US", "en-GB"])
    elif low in {"ja", "jp", "japanese"}:
        aliases.extend(["ja", "ja-JP"])
    elif low in {"ko", "kr", "korean"}:
        aliases.extend(["ko", "ko-KR"])
    elif low in {"de", "de-de", "german", "deutsch"}:
        aliases.extend(["de", "de-DE"])
    elif low in {"fr", "fr-fr", "french"}:
        aliases.extend(["fr", "fr-FR"])
    elif low in {"es", "es-es", "spanish"}:
        aliases.extend(["es", "es-ES"])
    elif low in {"pt", "pt-br", "portuguese", "portuguese-brazil"}:
        aliases.extend(["pt-BR", "pt"])
    elif low in {"it", "it-it", "italian"}:
        aliases.extend(["it", "it-IT"])
    elif low in {"ru", "ru-ru", "russian"}:
        aliases.extend(["ru", "ru-RU"])
    elif low in {"ar", "arabic"}:
        aliases.extend(["ar"])
    elif low in {"hi", "hindi"}:
        aliases.extend(["hi"])
    elif low in {"vi", "vietnamese"}:
        aliases.extend(["vi"])
    elif low in {"th", "thai"}:
        aliases.extend(["th"])
    elif low in {"id", "indonesian"}:
        aliases.extend(["id"])
    else:
        if "-" in low:
            aliases.append(low.split("-", 1)[0])
        aliases.append(low)

    seen = set()
    result = []
    for item in aliases:
        token = str(item or "").strip()
        if not token:
            continue
        key = token.lower()
        if key in seen:
            continue
        seen.add(key)
        result.append(token)
    return result


def _find_language_record(available: List[Dict[str, Any]], language: str) -> Dict[str, Any] | None:
    if not available:
        return None

    by_lower = {
        str(row.get("language") or "").strip().lower(): row
        for row in available
        if str(row.get("language") or "").strip()
    }

    for alias in _language_aliases(language):
        hit = by_lower.get(alias.lower())
        if hit:
            return hit

    raw = str(language or "").strip().lower().replace("_", "-")
    if raw and "-" in raw:
        root = raw.split("-", 1)[0]
        for row in available:
            candidate = str(row.get("language") or "").strip().lower().replace("_", "-")
            if candidate == root or candidate.startswith(root + "-"):
                return row

    return None


def _requested_target_language(args: Dict[str, Any]) -> tuple[str, bool]:
    raw = _get_optional_str(args, "target_language", "")
    if not raw:
        raw = _get_optional_str(args, "translation_language", "")
    if not raw:
        raw = _get_optional_str(args, "language", "")

    token = raw.strip()
    is_auto = token.lower() in AUTO_TARGET_LANGUAGE_TOKENS
    return token, is_auto


def _resolve_target_language_file(
    args: Dict[str, Any],
    translations_dir: str,
) -> tuple[str, str, str, List[Dict[str, Any]], str]:
    requested_language, requested_is_auto = _requested_target_language(args)
    available = _list_available_translation_languages(translations_dir)
    locale = _locale(args)

    if requested_language and not requested_is_auto:
        requested_path = _translation_file_for(translations_dir, requested_language)
        if os.path.exists(requested_path):
            return requested_language, requested_path, "requested", available, requested_language

        requested_hit = _find_language_record(available, requested_language)
        if requested_hit:
            return (
                str(requested_hit.get("language") or requested_language),
                str(requested_hit.get("path") or requested_path),
                "requested_alias",
                available,
                requested_language,
            )

    locale_hit = _find_language_record(available, locale)
    if locale_hit:
        return (
            str(locale_hit.get("language") or locale),
            str(locale_hit.get("path") or ""),
            "locale_match",
            available,
            requested_language,
        )

    if available:
        first = available[0]
        return (
            str(first.get("language") or ""),
            str(first.get("path") or ""),
            "latest_available",
            available,
            requested_language,
        )

    fallback_language = requested_language if requested_language and not requested_is_auto else locale
    if not fallback_language:
        fallback_language = "en"
    return fallback_language, _translation_file_for(translations_dir, fallback_language), "missing", available, requested_language


def _available_language_names(available: List[Dict[str, Any]]) -> List[str]:
    return [
        str(row.get("language") or "").strip()
        for row in available
        if str(row.get("language") or "").strip()
    ]


def _count_cjk_chars(text: str) -> int:
    count = 0
    for ch in str(text or ""):
        code = ord(ch)
        if (
            0x4E00 <= code <= 0x9FFF
            or 0x3400 <= code <= 0x4DBF
            or 0x20000 <= code <= 0x2A6DF
            or 0x3040 <= code <= 0x309F
            or 0x30A0 <= code <= 0x30FF
            or 0xAC00 <= code <= 0xD7AF
        ):
            count += 1
    return count


def _is_cjk_dominant(text: str) -> bool:
    t = str(text or "")
    if not t:
        return True
    cjk = _count_cjk_chars(t)
    return cjk / max(len(t), 1) >= 0.30


def _derive_default_words_from_cjk(line_chars_cjk: int) -> int:
    return max(6, min(14, round(max(10, line_chars_cjk) * 0.4)))


def _register_pdf_font(font_path: str = "", prefer_cjk: bool = True) -> str:
    if font_path and os.path.exists(font_path):
        try:
            font_name = "nisb_pdf_font_custom"
            pdfmetrics.registerFont(TTFont(font_name, font_path))
            return font_name
        except Exception:
            pass

    if prefer_cjk:
        try:
            font_name = "STSong-Light"
            pdfmetrics.registerFont(UnicodeCIDFont(font_name))
            return font_name
        except Exception:
            pass

    for p in [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    ]:
        if not os.path.exists(p):
            continue
        try:
            font_name = "nisb_pdf_font_latin"
            pdfmetrics.registerFont(TTFont(font_name, p))
            return font_name
        except Exception:
            continue

    if prefer_cjk:
        try:
            font_name = "STSong-Light"
            pdfmetrics.registerFont(UnicodeCIDFont(font_name))
            return font_name
        except Exception:
            pass

    return "Helvetica"


def _normalize_annotation_style(value: Any) -> str:
    s = str(value or "").strip().lower()
    if s in {"endnotes", "archive", "appendix", "chapter_end"}:
        return "endnotes"
    return "below_card"


def _resolve_default_font_size(
    layout_mode: str,
    line_chars_cjk: int,
    line_words_en: int,
    font_size_pt: float | None,
) -> float:
    if font_size_pt is not None and float(font_size_pt) > 0:
        return max(8.0, min(28.0, float(font_size_pt)))

    if layout_mode == "en_words":
        if line_words_en <= 6:
            return 11.8
        if line_words_en <= 8:
            return 10.8
        if line_words_en <= 10:
            return 10.0
        return 9.4

    if line_chars_cjk <= 16:
        return 16.0
    if line_chars_cjk <= 20:
        return 14.2
    if line_chars_cjk <= 24:
        return 13.0
    if line_chars_cjk <= 28:
        return 12.0
    return 11.0


def _measure_target_line_width_pt(
    font_name: str,
    font_size: float,
    layout_mode: str,
    line_chars_cjk: int,
    line_words_en: int,
) -> float:
    if layout_mode == "en_words":
        sample = " ".join(["example"] * max(3, int(line_words_en)))
    else:
        sample = "汉" * max(8, int(line_chars_cjk))
    return pdfmetrics.stringWidth(sample, font_name, font_size)


def _resolve_page_size(
    auto_fit_page_width: bool,
    page_width_mm: float | None,
    page_height_mm: float | None,
    margin_left_right_mm: float,
    margin_top_bottom_mm: float,
    font_name: str,
    font_size: float,
    layout_mode: str,
    line_chars_cjk: int,
    line_words_en: int,
) -> Tuple[tuple[float, float], str]:
    if auto_fit_page_width:
        usable_line_width_pt = _measure_target_line_width_pt(
            font_name=font_name,
            font_size=font_size,
            layout_mode=layout_mode,
            line_chars_cjk=line_chars_cjk,
            line_words_en=line_words_en,
        )
        width_fill_ratio = 0.985
        page_width_pt = usable_line_width_pt / width_fill_ratio + 2 * margin_left_right_mm * mm
        page_width_pt = max(55 * mm, min(210 * mm, page_width_pt))
        page_height_pt = max(100 * mm, min(297 * mm, (page_height_mm or 170) * mm))
        return (page_width_pt, page_height_pt), "adaptive"

    w_mm = page_width_mm if page_width_mm and page_width_mm > 0 else 210
    h_mm = page_height_mm if page_height_mm and page_height_mm > 0 else 297
    return (w_mm * mm, h_mm * mm), "fixed"


def _wrap_to_measured_width(text: str, font_name: str, font_size: float, usable_width: float) -> List[str]:
    s = str(text or "").strip()
    if not s:
        return [""]
    out: List[str] = []
    buf = ""
    for ch in s:
        trial = buf + ch
        try:
            w = pdfmetrics.stringWidth(trial, font_name, font_size)
        except Exception:
            w = len(trial) * font_size
        if buf and w > usable_width:
            out.append(buf)
            buf = ch
        else:
            buf = trial
    if buf:
        out.append(buf)
    return out or [""]


def _atomic_move_or_copy(tmp_path: str, target_path: str) -> None:
    parent = os.path.dirname(target_path)
    os.makedirs(parent, exist_ok=True)

    try:
        os.replace(tmp_path, target_path)
        return
    except OSError as e:
        if e.errno != errno.EXDEV:
            raise

    tmp_target = tempfile.NamedTemporaryFile(delete=False, dir=parent, suffix=".pdf")
    tmp_target.close()

    try:
        with open(tmp_path, "rb") as src, open(tmp_target.name, "wb") as dst:
            shutil.copyfileobj(src, dst)
        os.replace(tmp_target.name, target_path)
    finally:
        try:
            if os.path.exists(tmp_target.name):
                os.unlink(tmp_target.name)
        except Exception:
            pass
        try:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
        except Exception:
            pass


def _header_label(args: Dict[str, Any], key: str) -> str:
    labels = {
        "target_language": ("Target language", "目标语言"),
        "translated_spans": ("Translated spans", "已翻译片段"),
        "span_annotations": ("Span annotations", "片段批注"),
        "annotation_style": ("Annotation style", "批注样式"),
    }
    en, zh = labels.get(key, (key, key))
    return _txt(args, en, zh)


def _append_header_line(
    args: Dict[str, Any],
    header_lines: List[str],
    font_name: str,
    header_font_size: float,
    usable_width: float,
    key: str,
    value: str,
) -> None:
    text = f"{_header_label(args, key)}: {value}"
    header_lines.extend(_wrap_to_measured_width(text, font_name, header_font_size, usable_width))


def _renderer_accepts_i18n_labels() -> bool:
    try:
        params = inspect.signature(PDFRenderer.__init__).parameters
        return "locale" in params and "labels" in params
    except Exception:
        return False


def _pdf_renderer_labels(args: Dict[str, Any]) -> Dict[str, str]:
    return {
        "annotation_title_template": _txt(
            args,
            "Annotations · Span {span_index} · {count} {note_word}",
            "批注 · Span {span_index} · {count} 条",
        ),
        "annotation_note_singular": _txt(args, "note", "条"),
        "annotation_note_plural": _txt(args, "notes", "条"),
        "annotation_archive_title": _txt(args, "Annotation archive", "批注档案"),
        "image_load_failed_template": _txt(
            args,
            "[Image failed to load: {alt_text}]",
            "[图片加载失败: {alt_text}]",
        ),
    }


def _make_pdf_renderer(
    args: Dict[str, Any],
    canvas_obj: canvas.Canvas,
    page_size: Tuple[float, float],
    margin_left_right: float,
    margin_top_bottom: float,
    font_name: str,
    font_size: float,
    header_font_size: float,
    style_config: PDFStyleConfig,
) -> PDFRenderer:
    kwargs: Dict[str, Any] = {
        "canvas_obj": canvas_obj,
        "page_size": page_size,
        "margin_left_right": margin_left_right,
        "margin_top_bottom": margin_top_bottom,
        "font_name": font_name,
        "font_size": font_size,
        "header_font_size": header_font_size,
        "style_config": style_config,
    }

    if _renderer_accepts_i18n_labels():
        kwargs["locale"] = _locale(args)
        kwargs["labels"] = _pdf_renderer_labels(args)

    return PDFRenderer(**kwargs)


def nisb_library_export_translated_pdf(args: Dict[str, Any]) -> Dict[str, Any]:
    args = _safe_args(args)
    kind = "nisb_library_export_translated_pdf"

    if not REPORTLAB_AVAILABLE:
        return _err(
            args,
            kind,
            _txt(
                args,
                "reportlab is not installed. Please run: pip install reportlab",
                "reportlab 未安装，请先执行: pip install reportlab",
            ),
            tool_data={"reason": "reportlab_missing"},
        )

    base_path = _resolve_base_path(args)

    try:
        library_id = require_safe_id("library_id", _get_required_str(args, "library_id"))
        doc_id = require_safe_id("doc_id", _get_required_str(args, "doc_id"))
    except Exception as e:
        return _err(
            args,
            kind,
            str(e),
            tool_data={"reason": "invalid_required_id", "error": str(e)},
        )

    filename_override = _get_optional_str(args, "export_filename", "")
    export_user_dir = _get_optional_str(args, "export_user_dir", "")
    font_path = _get_optional_str(args, "font_path", "")
    layout_mode = _get_optional_str(args, "layout_mode", "auto").lower()

    save_to_nisb = _to_bool(args.get("save_to_nisb"), default=True)
    return_base64 = _to_bool(args.get("return_base64"), default=False)
    include_untranslated = _to_bool(args.get("include_untranslated"), default=False)
    auto_fit_page_width = _to_bool(args.get("auto_fit_page_width"), default=True)
    embed_nisb_images = _to_bool(args.get("embed_nisb_images"), default=True)
    include_span_annotations = _to_bool(args.get("include_span_annotations"), default=False)
    annotation_style = _normalize_annotation_style(args.get("annotation_style"))

    style_config = PDFStyleConfig(
        enable_page_background=_to_bool(args.get("enable_page_background"), default=True),
        enable_header_decoration=_to_bool(args.get("enable_header_decoration"), default=True),
        enable_paragraph_spacing=_to_bool(args.get("enable_paragraph_spacing"), default=True),
        enable_annotation_card_style=_to_bool(args.get("enable_annotation_card_style"), default=True),
    )

    max_chars = _get_optional_int(args, "max_chars", default=8000)
    if max_chars is None:
        max_chars = 8000
    max_chars = max(200, min(200000, int(max_chars)))

    line_chars_cjk = _get_optional_int(args, "line_chars_cjk", default=20)
    if line_chars_cjk is None:
        line_chars_cjk = 20
    line_chars_cjk = max(8, min(60, int(line_chars_cjk)))

    line_words_en = _get_optional_int(args, "line_words_en", default=None)
    if line_words_en is None:
        line_words_en = _derive_default_words_from_cjk(line_chars_cjk)
    line_words_en = max(3, min(20, int(line_words_en)))

    page_width_mm = _get_optional_float(args, "page_width_mm", default=None)
    page_height_mm = _get_optional_float(args, "page_height_mm", default=170.0 if auto_fit_page_width else 297.0)
    margin_left_right_mm = _get_optional_float(args, "margin_left_right_mm", default=4.0)
    margin_top_bottom_mm = _get_optional_float(args, "margin_top_bottom_mm", default=6.0)
    font_size_pt = _get_optional_float(args, "font_size_pt", default=None)

    margin_left_right_mm = max(1.0, min(40.0, float(margin_left_right_mm or 4.0)))
    margin_top_bottom_mm = max(2.0, min(40.0, float(margin_top_bottom_mm or 6.0)))
    if page_width_mm is not None:
        page_width_mm = max(55.0, min(210.0, float(page_width_mm)))
    if page_height_mm is not None:
        page_height_mm = max(100.0, min(297.0, float(page_height_mm)))

    if not save_to_nisb and not return_base64:
        return _err(
            args,
            kind,
            _txt(
                args,
                "save_to_nisb and return_base64 cannot both be false",
                "save_to_nisb 和 return_base64 不能同时为 false",
            ),
            tool_data={
                "library_id": library_id,
                "doc_id": doc_id,
                "reason": "no_output_requested",
            },
            library_id=library_id,
            doc_id=doc_id,
        )

    try:
        original_filename = _load_doc_filename(base_path, library_id, doc_id)
        _full_text, spans, source_label = _load_doc_text_and_spans(
            args,
            base_path,
            library_id,
            doc_id,
            max_chars=max_chars,
        )

        translations_dir = _ensure_doc_translations_dir(base_path, library_id, doc_id)
        (
            target_language,
            translations_file,
            target_language_source,
            available_translation_records,
            requested_target_language,
        ) = _resolve_target_language_file(args, translations_dir)

        available_target_languages = _available_language_names(available_translation_records)

        if not os.path.exists(translations_file):
            return _err(
                args,
                kind,
                _fmt(
                    args,
                    "No translation file is available for this document. Run document translation first, then export again. Requested target_language={requested}; available={available}",
                    "当前文档没有可用译文文件。请先执行文档翻译，再重新导出。请求的 target_language={requested}；可用译文={available}",
                    requested=requested_target_language or target_language or "auto",
                    available=", ".join(available_target_languages) if available_target_languages else "none",
                ),
                tool_data={
                    "library_id": library_id,
                    "doc_id": doc_id,
                    "requested_target_language": requested_target_language,
                    "target_language": target_language,
                    "target_language_source": target_language_source,
                    "available_target_languages": available_target_languages,
                    "translations_dir": translations_dir,
                    "translations_file": translations_file,
                    "reason": "translation_file_not_found",
                },
                library_id=library_id,
                doc_id=doc_id,
                requested_target_language=requested_target_language,
                target_language=target_language,
                target_language_source=target_language_source,
                available_target_languages=available_target_languages,
            )

        latest_map = _latest_translation_map(
            translations_file=translations_file,
            doc_id=doc_id,
            target_language=target_language,
            spans=spans,
        )

        annotations_by_span: Dict[int, List[Dict[str, Any]]] = {}
        if include_span_annotations:
            annotations_by_span = load_active_span_annotations(
                base_path=base_path,
                library_id=library_id,
                doc_id=doc_id,
            )

        (
            span_records,
            translated_span_count,
            total_span_count,
            missing_span_indexes,
            merged_text,
            endnotes,
            total_annotation_count,
            annotated_span_count,
        ) = build_export_span_records(
            spans=spans,
            latest_map=latest_map,
            include_untranslated=include_untranslated,
            annotations_by_span=annotations_by_span,
            include_span_annotations=include_span_annotations,
            annotation_style=annotation_style,
        )

        prepared_records, render_plain_text, embedded_images_count, missing_images_count = build_export_content(
            base_path=base_path,
            span_records=span_records,
            embed_nisb_images=embed_nisb_images,
        )

        if layout_mode not in {"auto", "cjk_chars", "en_words"}:
            layout_mode = "auto"

        layout_probe_text = render_plain_text or merged_text or target_language

        if layout_mode == "auto":
            final_layout_mode = "cjk_chars" if _is_cjk_dominant(layout_probe_text) else "en_words"
        else:
            final_layout_mode = layout_mode

        export_filename = _make_export_filename(args, original_filename, target_language, filename_override)
        export_title = os.path.splitext(export_filename)[0]

        renderer_label_probe_text = " ".join(str(v or "") for v in _pdf_renderer_labels(args).values())
        header_label_probe_text = " ".join(
            [
                _header_label(args, "target_language"),
                _header_label(args, "translated_spans"),
                _header_label(args, "span_annotations"),
                _header_label(args, "annotation_style"),
                _txt(args, "Untitled image", "未命名图片"),
                _txt(args, "[Image not found: {alt_text}]", "[图片未找到: {alt_text}]"),
            ]
        )
        font_probe_text = " ".join(
            [
                str(target_language or ""),
                str(layout_probe_text or ""),
                renderer_label_probe_text,
                header_label_probe_text,
            ]
        )
        prefer_cjk_font = target_language.lower().startswith(("zh", "ja", "ko")) or _count_cjk_chars(font_probe_text) > 0
        font_name = _register_pdf_font(font_path=font_path, prefer_cjk=prefer_cjk_font)

        final_font_size = _resolve_default_font_size(
            layout_mode=final_layout_mode,
            line_chars_cjk=line_chars_cjk,
            line_words_en=line_words_en,
            font_size_pt=font_size_pt,
        )

        page_size, page_mode = _resolve_page_size(
            auto_fit_page_width=auto_fit_page_width,
            page_width_mm=page_width_mm,
            page_height_mm=page_height_mm,
            margin_left_right_mm=margin_left_right_mm,
            margin_top_bottom_mm=margin_top_bottom_mm,
            font_name=font_name,
            font_size=final_font_size,
            layout_mode=final_layout_mode,
            line_chars_cjk=line_chars_cjk,
            line_words_en=line_words_en,
        )

        page_width, page_height = page_size
        margin_left_right = margin_left_right_mm * mm
        margin_top_bottom = margin_top_bottom_mm * mm
        usable_width = page_width - 2 * margin_left_right

        header_font_size = max(8.0, min(final_font_size, 11.0))
        header_lines: List[str] = []
        header_lines.extend(_wrap_to_measured_width(export_title, font_name, header_font_size, usable_width))
        _append_header_line(args, header_lines, font_name, header_font_size, usable_width, "target_language", target_language)
        _append_header_line(
            args,
            header_lines,
            font_name,
            header_font_size,
            usable_width,
            "translated_spans",
            f"{translated_span_count}/{total_span_count}",
        )

        if include_span_annotations:
            _append_header_line(
                args,
                header_lines,
                font_name,
                header_font_size,
                usable_width,
                "span_annotations",
                f"{total_annotation_count} / spans: {annotated_span_count}",
            )
            _append_header_line(
                args,
                header_lines,
                font_name,
                header_font_size,
                usable_width,
                "annotation_style",
                annotation_style,
            )

        header_lines.append("")

        tmp_fd, tmp_path = tempfile.mkstemp(prefix="nisb_export_", suffix=".pdf")
        os.close(tmp_fd)

        c = canvas.Canvas(tmp_path, pagesize=page_size)
        c.setTitle(export_title)
        c.setAuthor("NISB")
        c.setSubject("translated pdf export")

        renderer = _make_pdf_renderer(
            args=args,
            canvas_obj=c,
            page_size=page_size,
            margin_left_right=margin_left_right,
            margin_top_bottom=margin_top_bottom,
            font_name=font_name,
            font_size=final_font_size,
            header_font_size=header_font_size,
            style_config=style_config,
        )

        renderer.start_page()

        renderer.c.setFont(font_name, header_font_size)
        renderer.draw_text_lines(header_lines, header_font_size)

        renderer.y -= 4.5 * mm

        renderer.c.setFont(font_name, final_font_size)

        max_image_width = usable_width
        max_image_height = max(40 * mm, (page_height - 2 * margin_top_bottom) * 0.58)

        for rec in prepared_records:
            rec_span_index = int(rec.get("span_index", 0) or 0)
            rec_blocks = list(rec.get("render_blocks") or [])
            rec_annotations = list(rec.get("annotations") or [])

            for block in rec_blocks:
                block_type = str(block.get("type") or "")

                if block_type == "text":
                    from .pdf_export.pdf_renderer import _wrap_text_block_to_lines

                    lines = _wrap_text_block_to_lines(
                        text=str(block.get("content") or ""),
                        font_name=font_name,
                        font_size=final_font_size,
                        usable_width=usable_width,
                    )
                    if not lines:
                        continue
                    renderer.draw_text_lines(lines, final_font_size)
                    continue

                if block_type == "image":
                    resolved_path = str(block.get("resolved_path") or "").strip()
                    alt_text = str(block.get("alt") or "").strip() or _txt(args, "Untitled image", "未命名图片")

                    if not resolved_path:
                        from .pdf_export.pdf_renderer import _wrap_text_block_to_lines

                        placeholder_lines = _wrap_text_block_to_lines(
                            text=_fmt(args, "[Image not found: {alt_text}]", "[图片未找到: {alt_text}]", alt_text=alt_text),
                            font_name=font_name,
                            font_size=final_font_size,
                            usable_width=usable_width,
                        )
                        renderer.draw_text_lines(placeholder_lines, final_font_size)
                        renderer.y -= renderer.body_line_height * 0.3
                        continue

                    renderer.draw_image(resolved_path, alt_text, max_image_width, max_image_height)

            if include_span_annotations and annotation_style == "below_card" and rec_annotations:
                renderer.draw_annotation_card(rec_span_index, rec_annotations)
            else:
                if style_config.enable_paragraph_spacing:
                    renderer.y -= renderer.body_line_height * 0.55

        if include_span_annotations and annotation_style == "endnotes" and endnotes:
            renderer.draw_endnotes_section(endnotes)

        renderer.draw_footer()
        c.save()

        export_path = ""
        pdf_base64 = ""
        pdf_size_bytes = os.path.getsize(tmp_path) if os.path.exists(tmp_path) else 0

        export_dir_rel = ""
        export_scope = "doc_exports"

        if save_to_nisb:
            export_dir, export_dir_rel, export_scope = _resolve_export_dir(
                base_path=base_path,
                library_id=library_id,
                doc_id=doc_id,
                export_user_dir=export_user_dir,
            )
            export_path = os.path.join(export_dir, export_filename)
            _atomic_move_or_copy(tmp_path, export_path)
            source_pdf_path = export_path
        else:
            source_pdf_path = tmp_path

        if return_base64:
            with open(source_pdf_path, "rb") as f:
                pdf_base64 = base64.b64encode(f.read()).decode("ascii")

        if not save_to_nisb and os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except Exception:
                pass

        try:
            event = _make_timeline_event(
                base_path=base_path,
                library_id=library_id,
                doc_id=doc_id,
                title=original_filename or doc_id,
                extra={
                    "kind": "library_doc_export_translated_pdf",
                    "requested_target_language": requested_target_language,
                    "target_language": target_language,
                    "target_language_source": target_language_source,
                    "available_target_languages": available_target_languages,
                    "translations_file": translations_file,
                    "translated_span_count": translated_span_count,
                    "total_span_count": total_span_count,
                    "missing_span_count": len(missing_span_indexes),
                    "include_untranslated": bool(include_untranslated),
                    "save_to_nisb": bool(save_to_nisb),
                    "return_base64": bool(return_base64),
                    "export_filename": export_filename,
                    "export_path": export_path,
                    "export_user_dir": export_dir_rel,
                    "export_scope": export_scope,
                    "export_format": "pdf",
                    "embed_nisb_images": bool(embed_nisb_images),
                    "embedded_images_count": embedded_images_count,
                    "missing_images_count": missing_images_count,
                    "text_source": source_label,
                    "layout_mode": final_layout_mode,
                    "page_mode": page_mode,
                    "auto_fit_page_width": bool(auto_fit_page_width),
                    "line_chars_cjk": line_chars_cjk,
                    "line_words_en": line_words_en,
                    "font_name": font_name,
                    "font_size": final_font_size,
                    "pdf_size_bytes": pdf_size_bytes,
                    "page_width_mm": round(page_width / mm, 2),
                    "page_height_mm": round(page_height / mm, 2),
                    "margin_left_right_mm": margin_left_right_mm,
                    "margin_top_bottom_mm": margin_top_bottom_mm,
                    "include_span_annotations": bool(include_span_annotations),
                    "annotation_style": annotation_style,
                    "span_annotations_count": int(total_annotation_count),
                    "annotated_span_count": int(annotated_span_count),
                    "enable_page_background": bool(style_config.enable_page_background),
                    "enable_header_decoration": bool(style_config.enable_header_decoration),
                    "enable_paragraph_spacing": bool(style_config.enable_paragraph_spacing),
                    "enable_annotation_card_style": bool(style_config.enable_annotation_card_style),
                },
            )
            _append_timeline_safe(base_path, event)
        except Exception:
            pass

        message = (
            _fmt(
                args,
                "Full-translation PDF export completed: {translated}/{total} spans",
                "完整译文 PDF 导出完成：{translated}/{total} spans",
                translated=translated_span_count,
                total=total_span_count,
            )
            + (
                _fmt(args, ", saved to {path}", "，已保存到 {path}", path=export_path)
                if export_path
                else ""
            )
        )

        if target_language_source in {"locale_match", "latest_available", "requested_alias"}:
            message += _fmt(
                args,
                " (target language resolved to {target_language})",
                "（目标语言已解析为 {target_language}）",
                target_language=target_language,
            )

        result_fields = {
            "library_id": library_id,
            "doc_id": doc_id,
            "requested_target_language": requested_target_language,
            "target_language": target_language,
            "target_language_source": target_language_source,
            "available_target_languages": available_target_languages,
            "translations_file": translations_file,
            "original_filename": original_filename,
            "export_filename": export_filename,
            "export_path": export_path,
            "export_user_dir": export_dir_rel,
            "export_scope": export_scope,
            "export_format": "pdf",
            "saved_to_nisb": bool(save_to_nisb),
            "returned_base64": bool(return_base64),
            "embed_nisb_images": bool(embed_nisb_images),
            "embedded_images_count": embedded_images_count,
            "missing_images_count": missing_images_count,
            "translated_span_count": translated_span_count,
            "total_span_count": total_span_count,
            "missing_span_count": len(missing_span_indexes),
            "missing_span_indexes": missing_span_indexes[:200],
            "layout_mode": final_layout_mode,
            "page_mode": page_mode,
            "auto_fit_page_width": bool(auto_fit_page_width),
            "line_chars_cjk": line_chars_cjk,
            "line_words_en": line_words_en,
            "font_name": font_name,
            "font_size": round(final_font_size, 2),
            "pdf_size_bytes": pdf_size_bytes,
            "page_width_mm": round(page_width / mm, 2),
            "page_height_mm": round(page_height / mm, 2),
            "margin_left_right_mm": margin_left_right_mm,
            "margin_top_bottom_mm": margin_top_bottom_mm,
            "recommended_line_chars_cjk": 20,
            "recommended_line_words_en": _derive_default_words_from_cjk(20),
            "include_span_annotations": bool(include_span_annotations),
            "annotation_style": annotation_style,
            "span_annotations_count": int(total_annotation_count),
            "annotated_span_count": int(annotated_span_count),
            "enable_page_background": bool(style_config.enable_page_background),
            "enable_header_decoration": bool(style_config.enable_header_decoration),
            "enable_paragraph_spacing": bool(style_config.enable_paragraph_spacing),
            "enable_annotation_card_style": bool(style_config.enable_annotation_card_style),
        }

        if return_base64:
            result_fields["pdf_base64"] = pdf_base64

        return _ok(
            kind,
            message,
            tool_data={
                "library_id": library_id,
                "doc_id": doc_id,
                "requested_target_language": requested_target_language,
                "target_language": target_language,
                "target_language_source": target_language_source,
                "available_target_languages": available_target_languages,
                "export_filename": export_filename,
                "export_path": export_path,
                "translated_span_count": translated_span_count,
                "total_span_count": total_span_count,
            },
            **result_fields,
        )

    except Exception as e:
        return _err(
            args,
            kind,
            _fmt(
                args,
                "Full-translation PDF export failed: {error}",
                "完整译文 PDF 导出失败：{error}",
                error=repr(e),
            ),
            tool_data={
                "library_id": library_id,
                "doc_id": doc_id,
                "error": repr(e),
            },
            library_id=library_id,
            doc_id=doc_id,
        )
