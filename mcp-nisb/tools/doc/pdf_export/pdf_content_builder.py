#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from typing import Dict, Any, List, Tuple

from tools.doc.reading.common import _to_bool
from tools.doc.markdown_asset_resolver import (
    split_markdown_with_nisb_images,
    strip_markdown_images,
)


def _read_jsonl_rows(path: str) -> List[Dict[str, Any]]:
    import json
    import os

    rows: List[Dict[str, Any]] = []
    if not path or not os.path.exists(path):
        return rows

    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                raw = str(line or "").strip()
                if not raw:
                    continue
                try:
                    row = json.loads(raw)
                except Exception:
                    continue
                if isinstance(row, dict):
                    rows.append(row)
    except Exception:
        return []

    return rows


def load_active_span_annotations(
    base_path: str,
    library_id: str,
    doc_id: str,
) -> Dict[int, List[Dict[str, Any]]]:
    """加载有效的 Span 批注"""
    import os

    annotations_file = os.path.join(base_path, "annotations", "library_doc_span_annotations.jsonl")
    rows = _read_jsonl_rows(annotations_file)

    latest_by_id: Dict[str, Dict[str, Any]] = {}
    for row in rows:
        annotation_id = str(row.get("annotation_id") or "").strip()
        if not annotation_id:
            continue
        latest_by_id[annotation_id] = row

    active_rows: List[Dict[str, Any]] = []
    for row in latest_by_id.values():
        if _to_bool(row.get("tombstone"), default=False):
            continue
        if str(row.get("library_id") or "").strip() != str(library_id or "").strip():
            continue
        if str(row.get("doc_id") or "").strip() != str(doc_id or "").strip():
            continue

        try:
            span_index = int(row.get("span_index"))
        except Exception:
            continue

        content = str(row.get("content") or "").strip()
        if not content:
            continue

        active_rows.append({
            "annotation_id": str(row.get("annotation_id") or "").strip(),
            "library_id": str(row.get("library_id") or "").strip(),
            "doc_id": str(row.get("doc_id") or "").strip(),
            "span_index": span_index,
            "content": content,
            "created_at": str(row.get("created_at") or "").strip(),
            "updated_at": str(row.get("updated_at") or "").strip(),
            "reader": row.get("reader"),
        })

    active_rows.sort(key=lambda x: (x.get("created_at") or "", x.get("annotation_id") or ""))

    grouped: Dict[int, List[Dict[str, Any]]] = {}
    for row in active_rows:
        span_index = int(row["span_index"])
        grouped.setdefault(span_index, []).append(row)

    return grouped


def build_export_span_records(
    spans: List[Dict[str, Any]],
    latest_map: Dict[Tuple[int, int], Dict[str, Any]],
    include_untranslated: bool,
    annotations_by_span: Dict[int, List[Dict[str, Any]]],
    include_span_annotations: bool,
    annotation_style: str,
) -> Tuple[
    List[Dict[str, Any]],
    int,
    int,
    List[int],
    str,
    List[Dict[str, Any]],
    int,
    int,
]:
    """构建导出用的 Span 记录"""
    records: List[Dict[str, Any]] = []
    translated_span_count = 0
    missing_span_indexes: List[int] = []
    merged_text_parts: List[str] = []
    endnotes: List[Dict[str, Any]] = []

    next_note_no = 1
    total_annotation_count = 0
    annotated_span_count = 0

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

        export_text = ""
        if translated_text and not refused:
            export_text = translated_text
            translated_span_count += 1
        else:
            missing_span_indexes.append(span_index)
            if include_untranslated and original_text:
                export_text = f"[未翻译 span_{span_index}]\n{original_text}"

        raw_annotations = []
        if include_span_annotations:
            raw_annotations = list(annotations_by_span.get(span_index) or [])

        if raw_annotations:
            annotated_span_count += 1
            total_annotation_count += len(raw_annotations)

        if not export_text.strip():
            continue

        if include_span_annotations and raw_annotations and annotation_style == "endnotes":
            note_numbers: List[int] = []
            for ann in raw_annotations:
                note_no = next_note_no
                next_note_no += 1
                note_numbers.append(note_no)
                endnotes.append({
                    "note_no": note_no,
                    "span_index": span_index,
                    "content": str(ann.get("content") or "").strip(),
                    "annotation_id": str(ann.get("annotation_id") or "").strip(),
                })

            marker = "〔注" + ",".join([str(x) for x in note_numbers]) + "〕"
            export_text = export_text.rstrip() + "\n" + marker

        records.append({
            "span_index": span_index,
            "text": export_text,
            "annotations": raw_annotations if (include_span_annotations and annotation_style == "below_card") else [],
        })
        merged_text_parts.append(export_text)

    merged_text = "\n".join([x for x in merged_text_parts if str(x or "").strip()]).strip()

    return (
        records,
        translated_span_count,
        len(spans),
        missing_span_indexes,
        merged_text,
        endnotes,
        total_annotation_count,
        annotated_span_count,
    )


def build_render_blocks(
    base_path: str,
    text_blocks: List[str],
    embed_nisb_images: bool,
) -> Tuple[List[Dict[str, Any]], str, int, int]:
    """构建渲染块（文本 + 图片）"""
    render_blocks: List[Dict[str, Any]] = []
    merged_text_parts: List[str] = []
    embedded_images_count = 0
    missing_images_count = 0

    for idx, block in enumerate(text_blocks):
        block_text = str(block or "")

        if idx > 0:
            render_blocks.append({
                "type": "text",
                "content": "\n\n",
            })
            merged_text_parts.append("")

        if not block_text.strip():
            continue

        if not embed_nisb_images:
            render_blocks.append({
                "type": "text",
                "content": block_text,
            })
            merged_text_parts.append(strip_markdown_images(block_text))
            continue

        parts = split_markdown_with_nisb_images(block_text, base_path=base_path)
        if not parts:
            render_blocks.append({
                "type": "text",
                "content": block_text,
            })
            merged_text_parts.append(strip_markdown_images(block_text))
            continue

        for part in parts:
            if part.get("type") == "image":
                if part.get("resolved_path"):
                    embedded_images_count += 1
                else:
                    missing_images_count += 1
                render_blocks.append(part)
                merged_text_parts.append(str(part.get("alt") or ""))
            else:
                txt = str(part.get("content") or "")
                if txt:
                    render_blocks.append({
                        "type": "text",
                        "content": txt,
                    })
                    merged_text_parts.append(strip_markdown_images(txt))

    merged_text = "\n".join(merged_text_parts).strip()
    return render_blocks, merged_text, embedded_images_count, missing_images_count


def build_export_content(
    base_path: str,
    span_records: List[Dict[str, Any]],
    embed_nisb_images: bool,
) -> Tuple[List[Dict[str, Any]], str, int, int]:
    """构建完整导出内容（含图片处理）"""
    prepared_records: List[Dict[str, Any]] = []
    embedded_images_count = 0
    missing_images_count = 0
    render_plain_text_parts: List[str] = []

    for rec in span_records:
        render_blocks, render_plain_text, emb_count, miss_count = build_render_blocks(
            base_path=base_path,
            text_blocks=[str(rec.get("text") or "")],
            embed_nisb_images=embed_nisb_images,
        )
        embedded_images_count += emb_count
        missing_images_count += miss_count
        if render_plain_text.strip():
            render_plain_text_parts.append(render_plain_text.strip())

        prepared_records.append({
            "span_index": int(rec.get("span_index", 0) or 0),
            "render_blocks": render_blocks,
            "annotations": list(rec.get("annotations") or []),
        })

    render_plain_text = "\n".join(render_plain_text_parts).strip()

    return prepared_records, render_plain_text, embedded_images_count, missing_images_count

