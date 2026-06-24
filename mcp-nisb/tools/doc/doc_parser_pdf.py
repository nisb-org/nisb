#!/usr/bin/env python3
"""
PDF文档解析模块 - Phase 6.1.2（增强版）
目标：
- 稳定抽取文本入库（即使部分页面/对象损坏）
- pdfplumber 优先，失败自动 fallback 到 pypdf
- 捕获 pdfminer 的 Data-loss 警告，避免刷屏，并把统计写入 metadata
"""

from __future__ import annotations

from typing import Dict, Any, List, Optional
import logging

PDFPLUMBER_AVAILABLE = False
PYPDF_AVAILABLE = False

try:
    import pdfplumber  # noqa
    PDFPLUMBER_AVAILABLE = True
except ImportError:
    pass

try:
    import pypdf  # noqa
    PYPDF_AVAILABLE = True
except ImportError:
    pass

PDF_MAX_PAGES = 500


class _CountHandler(logging.Handler):
    def __init__(self, level=logging.WARNING):
        super().__init__(level)
        self.count = 0
        self.messages: List[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.count += 1
        msg = record.getMessage()
        if msg and len(self.messages) < 10:
            self.messages.append(msg)


def _page_separator(i: int) -> str:
    # i: 1-based
    return f"\n\n----- page {i} -----\n\n"


def _extract_page_text_pdfplumber(page) -> str:
    """
    尽量用 layout 模式提取（更接近阅读顺序/列排版），不支持则回退默认。
    """
    try:
        # 新版 pdfplumber 支持 layout 参数
        return page.extract_text(layout=True) or ""
    except TypeError:
        return page.extract_text() or ""
    except Exception:
        # 单页失败不应中断整本
        return ""


def parse_pdf_pdfplumber(file_path: str) -> Dict[str, Any]:
    """使用 pdfplumber（底层 pdfminer）提取文本。"""
    if not PDFPLUMBER_AVAILABLE:
        raise Exception("pdfplumber 不可用")

    import pdfplumber as _pdfplumber

    # 捕获并压制 pdfminer 的 warning 刷屏（尤其是 Data-loss...）
    pdfminer_logger = logging.getLogger("pdfminer")
    old_level = pdfminer_logger.level
    handler = _CountHandler(level=logging.WARNING)
    pdfminer_logger.addHandler(handler)
    pdfminer_logger.setLevel(logging.ERROR)  # 不刷屏，但我们仍统计 warning（通过 handler）

    full_text_parts: List[str] = []
    all_tables: List[dict] = []
    metadata: dict = {}
    page_count = 0
    pages_to_process = 0

    try:
        with _pdfplumber.open(file_path) as pdf:
            metadata = pdf.metadata or {}
            page_count = len(pdf.pages)
            pages_to_process = min(page_count, PDF_MAX_PAGES)

            for idx, page in enumerate(pdf.pages[:pages_to_process], start=1):
                full_text_parts.append(_page_separator(idx))
                text = _extract_page_text_pdfplumber(page)
                if text:
                    full_text_parts.append(text.strip() + "\n")

                # table（尽力而为，失败不影响主流程）
                try:
                    if getattr(page, "tables", None):
                        for table in page.tables:
                            table_data = {"page": idx, "rows": []}
                            for row in table:
                                if any(cell for cell in row if cell):
                                    table_data["rows"].append(row)
                            if len(table_data["rows"]) > 1:
                                all_tables.append(table_data)
                except Exception:
                    pass

        text_out = "".join(full_text_parts).strip()

        # 简单扫描件判断：前 3 页有效文本很少
        is_scanned = True
        try:
            preview = text_out[:4000].strip()
            if len(preview) >= 300:
                is_scanned = False
        except Exception:
            pass

        confidence = min(0.95, max(0.5, len(text_out) / 5000))

        return {
            "text": text_out,
            "tables": all_tables,
            "metadata": {
                "title": metadata.get("Title", "") if isinstance(metadata, dict) else "",
                "author": metadata.get("Author", "") if isinstance(metadata, dict) else "",
                "subject": metadata.get("Subject", "") if isinstance(metadata, dict) else "",
                "pages": page_count,
                "pages_processed": pages_to_process,
                "pdfminer_warnings": handler.count,
                "pdfminer_warning_samples": handler.messages,
            },
            "quality": {
                "has_tables": len(all_tables) > 0,
                "is_scanned": is_scanned,
                "confidence": confidence,
                "method": "pdfplumber",
            },
        }

    except Exception as e:
        raise Exception(f"pdfplumber提取失败：{str(e)}")
    finally:
        pdfminer_logger.removeHandler(handler)
        pdfminer_logger.setLevel(old_level)


def parse_pdf_pypdf(file_path: str) -> Dict[str, Any]:
    """使用 pypdf 提取文本（作为 fallback）。"""
    if not PYPDF_AVAILABLE:
        raise Exception("pypdf 不可用")

    import pypdf as _pypdf

    full_text_parts: List[str] = []
    page_count = 0
    pages_to_process = 0

    try:
        with open(file_path, "rb") as f:
            pdf_reader = _pypdf.PdfReader(f)
            page_count = len(pdf_reader.pages)
            pages_to_process = min(page_count, PDF_MAX_PAGES)

            for idx, page in enumerate(pdf_reader.pages[:pages_to_process], start=1):
                full_text_parts.append(_page_separator(idx))
                try:
                    text = page.extract_text() or ""
                except Exception:
                    text = ""
                if text:
                    full_text_parts.append(text.strip() + "\n")

        text_out = "".join(full_text_parts).strip()
        confidence = min(0.85, max(0.5, len(text_out) / 5000))

        return {
            "text": text_out,
            "tables": [],
            "metadata": {
                "pages": page_count,
                "pages_processed": pages_to_process,
            },
            "quality": {
                "has_tables": False,
                "is_scanned": len(text_out) < 500,
                "confidence": confidence,
                "method": "pypdf",
            },
        }

    except Exception as e:
        raise Exception(f"pypdf提取失败：{str(e)}")


def parse_pdf(file_path: str) -> Dict[str, Any]:
    """
    自动选择最优PDF提取方案：
    1) pdfplumber（优先）
    2) 失败则 pypdf（fallback）
    """
    last_err: Optional[Exception] = None

    if PDFPLUMBER_AVAILABLE:
        try:
            return parse_pdf_pdfplumber(file_path)
        except Exception as e:
            last_err = e

    if PYPDF_AVAILABLE:
        try:
            return parse_pdf_pypdf(file_path)
        except Exception as e:
            last_err = e

    if not (PDFPLUMBER_AVAILABLE or PYPDF_AVAILABLE):
        raise Exception("❌ 缺少PDF库：需要安装 pdfplumber 或 pypdf")

    raise Exception(f"❌ PDF解析失败：{str(last_err)}")

