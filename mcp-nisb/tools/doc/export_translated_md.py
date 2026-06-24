#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import base64
import json
import os
import re
import shutil
import tempfile
import zipfile
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
from tools.doc.markdown_asset_resolver import (
    split_markdown_with_nisb_images,
)
from tools.i18n.backend_i18n import i18n_text, normalize_backend_locale


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


def _read_json(path: str, default: Any) -> Any:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def _safe_export_filename(name: str) -> str:
    s = str(name or "").strip()
    if not s:
        s = "translated_export.md"
    s = s.replace("\\", "_").replace("/", "_")
    s = re.sub(r'[:*?"<>|]+', "_", s)
    s = re.sub(r"\s+", " ", s).strip()
    if not s.lower().endswith(".md"):
        s += ".md"
    return s


def _safe_package_filename(name: str) -> str:
    s = str(name or "").strip()
    if not s:
        s = "translated_export_md_images.zip"
    s = s.replace("\\", "_").replace("/", "_")
    s = re.sub(r'[:*?"<>|]+', "_", s)
    s = re.sub(r"\s+", " ", s).strip()
    if not s.lower().endswith(".zip"):
        s += ".zip"
    return s


def _make_export_filename(
    args: Dict[str, Any],
    original_filename: str,
    target_language: str,
    filename_override: str = "",
) -> str:
    if filename_override:
        return _safe_export_filename(filename_override)

    raw = str(original_filename or "").strip() or "document"
    base, _ext = os.path.splitext(raw)
    if not base:
        base = raw

    suffix = _txt(args, "full_translation", "完整译文")
    return _safe_export_filename(f"{base}_{suffix}_{target_language}.md")


def _make_package_filename(export_filename: str) -> str:
    base, _ext = os.path.splitext(str(export_filename or "").strip() or "translated_export.md")
    return _safe_package_filename(f"{base}_md_images.zip")


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

    if low in {"zh", "zh-cn", "zh-hans", "cn", "chinese", "中文", "简体中文"}:
        aliases.extend(["zh-CN", "zh", "zh-Hans"])
    elif low in {"zh-tw", "zh-hant", "traditional-chinese"}:
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


def _as_blockquote(text: str) -> str:
    lines = str(text or "").splitlines()
    if not lines:
        return "> "
    return "\n".join(["> " + ln if ln else ">" for ln in lines])


def _metadata_label(args: Dict[str, Any], key: str) -> str:
    labels = {
        "original_filename": ("original_filename", "原始文件名"),
        "library_id": ("library_id", "库 ID"),
        "doc_id": ("doc_id", "文档 ID"),
        "target_language": ("target_language", "目标语言"),
        "translated_spans": ("translated_spans", "已翻译片段"),
        "exported_at": ("exported_at", "导出时间"),
    }
    en, zh = labels.get(key, (key, key))
    return _txt(args, en, zh)


def _build_markdown(
    args: Dict[str, Any],
    export_title: str,
    original_filename: str,
    library_id: str,
    doc_id: str,
    target_language: str,
    spans: List[Dict[str, Any]],
    latest_map: Dict[Tuple[int, int], Dict[str, Any]],
    include_untranslated: bool,
) -> Tuple[str, int, int, List[int]]:
    translated_parts: List[str] = []
    translated_span_count = 0
    missing_span_indexes: List[int] = []

    for sp in spans:
        span_index = int(sp.get("span_index", 0) or 0)
        span_start = int(sp.get("span_start", 0) or 0)
        span_end = int(sp.get("span_end", 0) or 0)
        original_text = str(sp.get("text") or "").strip()

        latest = latest_map.get((span_start, span_end))
        translated_text = ""
        refused = False

        if latest:
            translated_text = str(latest.get("translated_text") or "").strip()
            refused = _to_bool(latest.get("refused"), default=False)

        if translated_text and not refused:
            translated_parts.append(translated_text)
            translated_span_count += 1
            continue

        missing_span_indexes.append(span_index)

        if include_untranslated and original_text:
            untranslated_label = _fmt(
                args,
                "[untranslated span_{span_index}]",
                "[未翻译 span_{span_index}]",
                span_index=span_index,
            )
            translated_parts.append(
                "\n".join(
                    [
                        f"> {untranslated_label}",
                        _as_blockquote(original_text),
                    ]
                )
            )

    try:
        from tools.doc.reading.common import _utc_now_iso_z

        exported_at = _utc_now_iso_z()
    except Exception:
        exported_at = ""

    header_lines = [
        f"# {export_title}",
        "",
        f"- {_metadata_label(args, 'original_filename')}: {original_filename}",
        f"- {_metadata_label(args, 'library_id')}: {library_id}",
        f"- {_metadata_label(args, 'doc_id')}: {doc_id}",
        f"- {_metadata_label(args, 'target_language')}: {target_language}",
        f"- {_metadata_label(args, 'translated_spans')}: {translated_span_count}/{len(spans)}",
    ]
    if exported_at:
        header_lines.append(f"- {_metadata_label(args, 'exported_at')}: {exported_at}")

    body = "\n\n".join([p for p in translated_parts if str(p).strip()]).strip()
    empty_body = _txt(args, "No exportable translation content.", "无可导出的译文内容。")
    markdown_text = "\n".join(header_lines).strip() + "\n\n---\n\n" + (body or empty_body) + "\n"

    return markdown_text, translated_span_count, len(spans), missing_span_indexes


def _atomic_write_text(path: str, content: str) -> None:
    parent = os.path.dirname(path)
    os.makedirs(parent, exist_ok=True)

    tmp = tempfile.NamedTemporaryFile(mode="w", delete=False, encoding="utf-8", dir=parent)
    try:
        tmp.write(content)
        tmp.flush()
        tmp.close()
        os.replace(tmp.name, path)
    finally:
        try:
            if os.path.exists(tmp.name):
                os.unlink(tmp.name)
        except Exception:
            pass


def _safe_local_image_name(index: int, source_path: str) -> str:
    raw_name = os.path.basename(str(source_path or "").strip()) or f"image_{index:05d}"
    stem, ext = os.path.splitext(raw_name)

    stem = re.sub(r"[^0-9A-Za-z._-]+", "_", stem).strip("._")
    if not stem:
        stem = f"image_{index:05d}"

    ext = str(ext or "").lower()
    if not ext or len(ext) > 10:
        ext = ".bin"

    return f"{index:05d}_{stem}{ext}"


def _rewrite_markdown_to_local_package(
    markdown_text: str,
    base_path: str,
) -> Tuple[str, List[Tuple[str, str]], int, int]:
    parts = split_markdown_with_nisb_images(markdown_text, base_path=base_path)
    if not parts:
        return markdown_text, [], 0, 0

    rewritten_parts: List[str] = []
    copied_assets: List[Tuple[str, str]] = []
    packaged_images_count = 0
    missing_packaged_images_count = 0
    used_names = set()

    for part in parts:
        if str(part.get("type") or "") != "image":
            rewritten_parts.append(str(part.get("content") or ""))
            continue

        alt = str(part.get("alt") or "")
        url = str(part.get("url") or "").strip()
        resolved_path = str(part.get("resolved_path") or "").strip()

        if resolved_path and os.path.isfile(resolved_path):
            packaged_images_count += 1
            local_name = _safe_local_image_name(packaged_images_count, resolved_path)
            while local_name in used_names:
                packaged_images_count += 1
                local_name = _safe_local_image_name(packaged_images_count, resolved_path)
            used_names.add(local_name)

            rel_path = f"images/{local_name}"
            rewritten_parts.append(f"![{alt}]({rel_path})")
            copied_assets.append((resolved_path, rel_path))
        else:
            missing_packaged_images_count += 1
            rewritten_parts.append(f"![{alt}]({url})")

    local_markdown_content = "".join(rewritten_parts)
    return local_markdown_content, copied_assets, packaged_images_count, missing_packaged_images_count


def _build_markdown_package_base64(
    markdown_text: str,
    base_path: str,
    export_filename: str,
) -> Tuple[str, str, str, int, int]:
    package_filename = _make_package_filename(export_filename)
    local_markdown_content, copied_assets, packaged_images_count, missing_packaged_images_count = _rewrite_markdown_to_local_package(
        markdown_text=markdown_text,
        base_path=base_path,
    )

    temp_root = tempfile.mkdtemp(prefix="nisb_md_pkg_")
    zip_fd = None
    zip_path = ""

    try:
        md_path = os.path.join(temp_root, export_filename)
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(local_markdown_content)

        for source_path, rel_path in copied_assets:
            target_path = os.path.join(temp_root, rel_path)
            os.makedirs(os.path.dirname(target_path), exist_ok=True)
            shutil.copy2(source_path, target_path)

        zip_fd, zip_path = tempfile.mkstemp(prefix="nisb_md_pkg_", suffix=".zip")
        os.close(zip_fd)
        zip_fd = None

        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for root, _dirs, files in os.walk(temp_root):
                for name in files:
                    abs_file = os.path.join(root, name)
                    arcname = os.path.relpath(abs_file, temp_root)
                    zf.write(abs_file, arcname)

        with open(zip_path, "rb") as f:
            package_base64 = base64.b64encode(f.read()).decode("ascii")

        return (
            package_filename,
            package_base64,
            local_markdown_content,
            packaged_images_count,
            missing_packaged_images_count,
        )
    finally:
        try:
            if zip_fd is not None:
                os.close(zip_fd)
        except Exception:
            pass
        try:
            if zip_path and os.path.exists(zip_path):
                os.remove(zip_path)
        except Exception:
            pass
        try:
            shutil.rmtree(temp_root, ignore_errors=True)
        except Exception:
            pass


def nisb_library_export_translated_md(args: Dict[str, Any]) -> Dict[str, Any]:
    args = _safe_args(args)
    kind = "nisb_library_export_translated_md"
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
    save_to_nisb = _to_bool(args.get("save_to_nisb"), default=True)
    return_content = _to_bool(args.get("return_content"), default=False)
    include_untranslated = _to_bool(args.get("include_untranslated"), default=False)

    max_chars = _get_optional_int(args, "max_chars", default=8000)
    if max_chars is None:
        max_chars = 8000
    try:
        max_chars = max(200, min(200000, int(max_chars)))
    except Exception:
        max_chars = 8000

    if not save_to_nisb and not return_content:
        return _err(
            args,
            kind,
            _txt(
                args,
                "save_to_nisb and return_content cannot both be false",
                "save_to_nisb 和 return_content 不能同时为 false",
            ),
            tool_data={"reason": "no_output_requested"},
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

        export_filename = _make_export_filename(args, original_filename, target_language, filename_override)
        export_title = os.path.splitext(export_filename)[0]

        markdown_text, translated_span_count, total_span_count, missing_span_indexes = _build_markdown(
            args=args,
            export_title=export_title,
            original_filename=original_filename,
            library_id=library_id,
            doc_id=doc_id,
            target_language=target_language,
            spans=spans,
            latest_map=latest_map,
            include_untranslated=include_untranslated,
        )

        export_path = ""
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
            _atomic_write_text(export_path, markdown_text)

        markdown_package_filename = ""
        markdown_package_base64 = ""
        local_markdown_content = ""
        packaged_images_count = 0
        missing_packaged_images_count = 0

        if return_content:
            (
                markdown_package_filename,
                markdown_package_base64,
                local_markdown_content,
                packaged_images_count,
                missing_packaged_images_count,
            ) = _build_markdown_package_base64(
                markdown_text=markdown_text,
                base_path=base_path,
                export_filename=export_filename,
            )

        try:
            event = _make_timeline_event(
                base_path=base_path,
                library_id=library_id,
                doc_id=doc_id,
                title=original_filename or doc_id,
                extra={
                    "kind": "library_doc_export_translated_md",
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
                    "return_content": bool(return_content),
                    "export_filename": export_filename,
                    "export_path": export_path,
                    "export_user_dir": export_dir_rel,
                    "export_scope": export_scope,
                    "export_format": "md",
                    "text_source": source_label,
                    "returned_package": bool(return_content),
                    "markdown_package_filename": markdown_package_filename,
                    "packaged_images_count": packaged_images_count,
                    "missing_packaged_images_count": missing_packaged_images_count,
                },
            )
            _append_timeline_safe(base_path, event)
        except Exception:
            pass

        message = (
            _fmt(
                args,
                "Full-translation Markdown export completed: {translated}/{total} spans",
                "完整译文 Markdown 导出完成：{translated}/{total} spans",
                translated=translated_span_count,
                total=total_span_count,
            )
            + (
                _fmt(args, ", saved to {path}", "，已保存到 {path}", path=export_path)
                if export_path
                else ""
            )
            + (
                _txt(args, ", generated local md+images package", "，已生成本机 md+images 包")
                if return_content
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
            "export_format": "md",
            "saved_to_nisb": bool(save_to_nisb),
            "returned_content": bool(return_content),
            "returned_package": bool(return_content),
            "translated_span_count": translated_span_count,
            "total_span_count": total_span_count,
            "missing_span_count": len(missing_span_indexes),
            "missing_span_indexes": missing_span_indexes[:200],
            "markdown_package_filename": markdown_package_filename,
            "packaged_images_count": packaged_images_count,
            "missing_packaged_images_count": missing_packaged_images_count,
        }

        if return_content:
            result_fields["markdown_content"] = markdown_text
            result_fields["local_markdown_content"] = local_markdown_content
            result_fields["markdown_package_base64"] = markdown_package_base64

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
                "Full-translation Markdown export failed: {error}",
                "完整译文 Markdown 导出失败：{error}",
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
