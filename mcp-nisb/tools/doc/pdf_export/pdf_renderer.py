#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from typing import Any, Dict, List, Optional, Tuple

try:
    from reportlab.lib.units import mm
    from reportlab.pdfgen import canvas
    from reportlab.pdfbase import pdfmetrics
    from reportlab.lib.utils import ImageReader

    REPORTLAB_AVAILABLE = True
except Exception:
    REPORTLAB_AVAILABLE = False

try:
    from PIL import Image

    PIL_AVAILABLE = True
except Exception:
    PIL_AVAILABLE = False

from .pdf_style_config import PDFStyleConfig


def _wrap_text_block_to_lines(
    text: str,
    font_name: str,
    font_size: float,
    usable_width: float,
) -> List[str]:
    text = str(text or "").replace("\r\n", "\n").replace("\r", "\n")
    if text == "":
        return []

    out: List[str] = []
    raw_lines = text.split("\n")

    for raw in raw_lines:
        if not raw.strip():
            out.append("")
            continue

        current = ""
        for ch in raw:
            trial = current + ch
            try:
                width = pdfmetrics.stringWidth(trial, font_name, font_size)
            except Exception:
                width = len(trial) * font_size

            if current and width > usable_width:
                out.append(current)
                current = ch
            else:
                current = trial

        if current:
            out.append(current)

    return out


def _get_image_size_px(path: str) -> Tuple[int, int]:
    if not PIL_AVAILABLE:
        raise RuntimeError("Pillow is not installed; image processing is unavailable")

    with Image.open(path) as img:
        w, h = img.size
    return int(w), int(h)


def _fit_image_box(
    img_w_px: int,
    img_h_px: int,
    usable_width_pt: float,
    usable_height_pt: float,
) -> Tuple[float, float]:
    if img_w_px <= 0 or img_h_px <= 0:
        raise ValueError("invalid image size")

    scale = min(
        usable_width_pt / float(img_w_px),
        usable_height_pt / float(img_h_px),
        1.0,
    )
    return float(img_w_px) * scale, float(img_h_px) * scale


class PDFRenderer:
    def __init__(
        self,
        canvas_obj: canvas.Canvas,
        page_size: Tuple[float, float],
        margin_left_right: float,
        margin_top_bottom: float,
        font_name: str,
        font_size: float,
        header_font_size: float,
        style_config: PDFStyleConfig,
        locale: str = "en",
        labels: Optional[Dict[str, str]] = None,
    ):
        self.c = canvas_obj
        self.page_width, self.page_height = page_size
        self.margin_left = margin_left_right
        self.margin_right = margin_left_right
        self.margin_top = margin_top_bottom
        self.margin_bottom = margin_top_bottom
        self.font_name = font_name
        self.font_size = font_size
        self.header_font_size = header_font_size
        self.style = style_config
        self.locale = str(locale or "en").strip() or "en"
        self.labels = labels if isinstance(labels, dict) else {}

        self.usable_width = self.page_width - 2 * margin_left_right
        self.body_line_height = font_size * 1.45
        self.header_line_height = header_font_size * 1.35

        self.page_no = 1
        self.y = self.page_height - self.margin_top

        self.header_line_top_gap = 1.2 * mm
        self.content_gap_below_header_line = 6.2 * mm
        self.annotation_bar_top_inset = 0.4 * mm
        self.annotation_bar_bottom_inset = 3.6 * mm

    def _label(self, key: str, fallback: str) -> str:
        value = self.labels.get(key)
        if value is None:
            return fallback
        text = str(value).strip()
        return text or fallback

    def _format_label(self, key: str, fallback: str, **kwargs: Any) -> str:
        template = self._label(key, fallback)
        try:
            return template.format(**kwargs)
        except Exception:
            try:
                return fallback.format(**kwargs)
            except Exception:
                return fallback

    def _annotation_note_word(self, count: int) -> str:
        if int(count) == 1:
            return self._label("annotation_note_singular", "note")
        return self._label("annotation_note_plural", "notes")

    def _format_annotation_title(self, span_index: int, count: int) -> str:
        note_word = self._annotation_note_word(count)
        return self._format_label(
            "annotation_title_template",
            "Annotations · Span {span_index} · {count} {note_word}",
            span_index=span_index,
            count=count,
            note_word=note_word,
        )

    def _format_image_load_failed(self, alt_text: str) -> str:
        return self._format_label(
            "image_load_failed_template",
            "[Image failed to load: {alt_text}]",
            alt_text=alt_text,
        )

    def _content_start_y(self) -> float:
        line_y = self.page_height - self.header_line_top_gap
        return line_y - self.content_gap_below_header_line

    def start_page(self):
        self.fill_page_background()
        self.draw_header_decoration()
        self.y = self._content_start_y()
        self.c.setFillColorRGB(*self.style.body_text_color)
        self.c.setFont(self.font_name, self.font_size)

    def fill_page_background(self):
        if not self.style.enable_page_background:
            return
        self.c.setFillColorRGB(*self.style.page_bg_color)
        self.c.rect(0, 0, self.page_width, self.page_height, fill=1, stroke=0)
        self.c.setFillColorRGB(*self.style.body_text_color)

    def draw_header_decoration(self):
        if not self.style.enable_header_decoration:
            return
        deco_y = self.page_height - self.header_line_top_gap
        self.c.setStrokeColorRGB(*self.style.header_decoration_color)
        self.c.setLineWidth(self.style.header_decoration_width)
        self.c.line(self.margin_left, deco_y, self.page_width - self.margin_right, deco_y)
        self.c.setStrokeColorRGB(0, 0, 0)
        self.c.setLineWidth(1)

    def draw_footer(self):
        footer_font = max(7.0, min(9.0, self.header_font_size))
        self.c.setFont(self.font_name, footer_font)
        self.c.setFillColorRGB(*self.style.footer_text_color)
        self.c.drawRightString(
            self.page_width - self.margin_right,
            max(4 * mm, self.margin_bottom * 0.65),
            str(self.page_no),
        )
        self.c.setFillColorRGB(*self.style.body_text_color)

    def new_page(self):
        self.draw_footer()
        self.c.showPage()
        self.page_no += 1
        self.start_page()

    def draw_text_lines(self, lines: List[str], font_size: float):
        self.c.setFont(self.font_name, font_size)
        self.c.setFillColorRGB(*self.style.body_text_color)
        line_height = font_size * 1.45

        for ln in lines:
            if self.y < self.margin_bottom + line_height:
                self.new_page()
                self.c.setFont(self.font_name, font_size)
                self.c.setFillColorRGB(*self.style.body_text_color)

            if ln.strip():
                self.c.drawString(self.margin_left, self.y, ln)

            self.y -= line_height

    def _draw_annotation_section_background(
        self,
        card_x: float,
        card_width: float,
        bar_width: float,
        top_y: float,
        bottom_y: float,
    ):
        if not self.style.enable_annotation_card_style:
            return

        section_height = top_y - bottom_y
        if section_height <= 0:
            return

        self.c.setFillColorRGB(*self.style.annotation_card_bg)
        self.c.roundRect(card_x, bottom_y, card_width, section_height, 2.6 * mm, fill=1, stroke=0)

        bar_top = top_y - min(self.annotation_bar_top_inset, max(0.2 * mm, section_height * 0.06))
        bar_bottom = bottom_y + min(self.annotation_bar_bottom_inset, max(1.2 * mm, section_height * 0.22))
        bar_height = bar_top - bar_bottom

        if bar_height > 1.2 * mm:
            self.c.setFillColorRGB(*self.style.annotation_bar_color)
            self.c.rect(card_x, bar_bottom, bar_width, bar_height, fill=1, stroke=0)

        self.c.setFillColorRGB(*self.style.body_text_color)

    def _build_annotation_items(
        self,
        span_index: int,
        annotations: List[Dict[str, Any]],
        content_width: float,
        title_font_size: float,
        note_font_size: float,
    ) -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []

        title_text = self._format_annotation_title(span_index, len(annotations))
        title_lines = _wrap_text_block_to_lines(
            text=title_text,
            font_name=self.font_name,
            font_size=title_font_size,
            usable_width=content_width,
        )
        for ln in title_lines:
            items.append(
                {
                    "kind": "title",
                    "text": ln,
                    "font_size": title_font_size,
                    "line_height": title_font_size * 1.35,
                    "color": self.style.annotation_title_color,
                }
            )

        items.append(
            {
                "kind": "gap",
                "text": "",
                "font_size": note_font_size,
                "line_height": 1.0 * mm,
                "color": self.style.annotation_body_color,
            }
        )

        for idx, ann in enumerate(annotations, start=1):
            ann_text = str(ann.get("content") or "").strip()
            if not ann_text:
                continue

            bullet_text = f"{idx}. {ann_text}"
            wrapped = _wrap_text_block_to_lines(
                text=bullet_text,
                font_name=self.font_name,
                font_size=note_font_size,
                usable_width=content_width,
            )

            for ln in wrapped:
                items.append(
                    {
                        "kind": "body",
                        "text": ln,
                        "font_size": note_font_size,
                        "line_height": note_font_size * 1.42,
                        "color": self.style.annotation_body_color,
                    }
                )

            if idx < len(annotations):
                items.append(
                    {
                        "kind": "gap",
                        "text": "",
                        "font_size": note_font_size,
                        "line_height": note_font_size * 0.55,
                        "color": self.style.annotation_body_color,
                    }
                )

        return items

    def draw_annotation_card(self, span_index: int, annotations: List[Dict[str, Any]]):
        if not annotations:
            return

        title_font_size = max(8.0, min(11.0, self.font_size * 0.82))
        note_font_size = max(8.0, min(10.8, self.font_size * 0.88))

        card_x = self.margin_left
        card_width = self.usable_width
        bar_width = 1.3 * mm

        inner_pad_x = 3.2 * mm
        inner_pad_y = 2.2 * mm

        content_x = card_x + bar_width + inner_pad_x + 1.2 * mm
        content_width = card_width - (content_x - card_x) - inner_pad_x

        items = self._build_annotation_items(
            span_index=span_index,
            annotations=annotations,
            content_width=content_width,
            title_font_size=title_font_size,
            note_font_size=note_font_size,
        )

        self.y -= 1.4 * mm

        idx = 0
        total = len(items)

        while idx < total:
            available_height = self.y - self.margin_bottom
            min_required = inner_pad_y * 2 + max(title_font_size * 1.35, note_font_size * 1.42)

            if available_height < min_required:
                self.new_page()
                available_height = self.y - self.margin_bottom

            section_items: List[Dict[str, Any]] = []
            used_height = inner_pad_y * 2

            while idx < total:
                item = items[idx]
                next_height = float(item.get("line_height", 0.0) or 0.0)

                if section_items and used_height + next_height > available_height:
                    break

                if not section_items and used_height + next_height > available_height:
                    self.new_page()
                    available_height = self.y - self.margin_bottom
                    used_height = inner_pad_y * 2
                    continue

                section_items.append(item)
                used_height += next_height
                idx += 1

            if not section_items:
                self.new_page()
                continue

            section_top_y = self.y
            section_bottom_y = self.y - used_height

            self._draw_annotation_section_background(
                card_x=card_x,
                card_width=card_width,
                bar_width=bar_width,
                top_y=section_top_y,
                bottom_y=section_bottom_y,
            )

            cursor_y = section_top_y - inner_pad_y

            for item in section_items:
                kind = str(item.get("kind") or "")
                line_height = float(item.get("line_height", 0.0) or 0.0)

                if kind == "gap":
                    cursor_y -= line_height
                    continue

                self.c.setFont(self.font_name, float(item.get("font_size", note_font_size)))
                self.c.setFillColorRGB(*item.get("color", self.style.annotation_body_color))

                text = str(item.get("text") or "")
                if text.strip():
                    self.c.drawString(content_x, cursor_y, text)

                cursor_y -= line_height

            self.c.setFillColorRGB(*self.style.body_text_color)
            self.c.setFont(self.font_name, self.font_size)
            self.y = section_bottom_y

        self.y -= 3.0 * mm

    def draw_endnotes_section(self, endnotes: List[Dict[str, Any]]):
        if not endnotes:
            return

        if self.y < self.page_height * 0.35:
            self.new_page()
            self.c.setFont(self.font_name, self.font_size)

        heading_font_size = max(10.0, min(14.0, self.font_size * 1.04))
        note_font_size = max(8.0, min(10.8, self.font_size * 0.92))

        archive_title = self._label("annotation_archive_title", "Annotation archive")
        self.draw_text_lines(["", archive_title, ""], heading_font_size)

        for row in endnotes:
            note_no = int(row.get("note_no", 0) or 0)
            span_index = int(row.get("span_index", 0) or 0)
            content = str(row.get("content") or "").strip()
            if not content:
                continue

            head = f"[{note_no}] Span {span_index}"
            head_lines = _wrap_text_block_to_lines(
                text=head,
                font_name=self.font_name,
                font_size=note_font_size,
                usable_width=self.usable_width,
            )
            body_lines = _wrap_text_block_to_lines(
                text=content,
                font_name=self.font_name,
                font_size=note_font_size,
                usable_width=max(30 * mm, self.usable_width - 6 * mm),
            )

            self.draw_text_lines(head_lines, note_font_size)
            indented_lines = [("  " + ln) if ln.strip() else "" for ln in body_lines]
            self.draw_text_lines(indented_lines, note_font_size)
            self.draw_text_lines([""], note_font_size)

        self.c.setFont(self.font_name, self.font_size)

    def draw_image(self, resolved_path: str, alt_text: str, max_width: float, max_height: float):
        try:
            img_w_px, img_h_px = _get_image_size_px(resolved_path)
            draw_w, draw_h = _fit_image_box(
                img_w_px=img_w_px,
                img_h_px=img_h_px,
                usable_width_pt=max_width,
                usable_height_pt=max_height,
            )

            required_height = draw_h + self.body_line_height * 0.8
            if self.y < self.margin_bottom + required_height:
                self.new_page()
                self.c.setFont(self.font_name, self.font_size)

            x = self.margin_left + (self.usable_width - draw_w) / 2.0
            image_y = self.y - draw_h

            self.c.drawImage(
                ImageReader(resolved_path),
                x,
                image_y,
                width=draw_w,
                height=draw_h,
                preserveAspectRatio=True,
                anchor="c",
            )

            self.y = image_y - self.body_line_height * 0.8

        except Exception:
            placeholder_lines = _wrap_text_block_to_lines(
                text=self._format_image_load_failed(alt_text),
                font_name=self.font_name,
                font_size=self.font_size,
                usable_width=self.usable_width,
            )
            self.draw_text_lines(placeholder_lines, self.font_size)
            self.y -= self.body_line_height * 0.3
