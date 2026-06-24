#!/usr/bin/env python3
"""
Doc 系统导出（对外稳定入口）
- 这里负责“对外导出/聚合”，避免外部模块到处 import 内部细节。
- 重点：qa_scope 工具来自 tools.doc.analysis.qa_scope，不属于 tools.doc.doc（doc.py）。
"""

from tools.doc.doc_parser import (
    parse_document,
    get_supported_formats,
    validate_extracted_content,
)
from tools.doc.core.path_resolver import PathResolver, StorageMode

# 新增：Evidence scope（你已实现）
from .doc_evidence_scope import nisb_doc_evidence_scope

# ✅ 新增：QA scope（按三域落盘）
from .analysis.qa_scope import nisb_qa_scope_ask, nisb_qa_scope_list

# 统一从 tools.doc.doc 导出（doc.py 对外稳定）
from tools.doc.doc import (
    # 库管理
    nisb_library_create,
    nisb_library_list,
    nisb_library_delete,
    nisb_library_stats,
    nisb_library_get_info,
    nisb_doc_upload_to_library,

    # 库内文档管理
    nisb_library_doc_delete,
    nisb_library_doc_delete_batch,
    nisb_library_doc_rename,

    # 核心功能
    nisb_doc_upload,
    nisb_doc_search,
    nisb_doc_bookmark,
    nisb_doc_recall,
    nisb_doc_embedding,
    nisb_doc_annotate,
    nisb_doc_network,
    nisb_doc_stats,
    nisb_doc_search_hybrid,
    nisb_doc_search_with_filter,
    nisb_doc_expand_enhanced,
    nisb_doc_generate_outline,
    nisb_doc_generate_summary,
    nisb_doc_analyze_concepts,

    # 库级连续阅读 + 翻译缓存
    nisb_library_continuous_read,
    nisb_library_translate_span,
    nisb_library_doc_evidence,
    nisb_doc_outline_get,
    nisb_doc_outline_expand,
    nisb_doc_outline_translate,

    # Topic QA（doc 级，旧功能保留）
    nisb_doc_qa_ask,
    nisb_doc_qa_list,
)

# Web 一键“上传→向量化”适配工具
from tools.doc.lib_upload import nisb_doc_upload_to_library_web
from .export_translated_md import nisb_library_export_translated_md
from .export_translated_pdf import nisb_library_export_translated_pdf

__all__ = [
    # 库管理
    'nisb_library_create',
    'nisb_library_list',
    'nisb_library_delete',
    'nisb_library_stats',
    'nisb_library_get_info',
    'nisb_doc_upload_to_library',
    'nisb_doc_upload_to_library_web',

    # 库内文档管理
    'nisb_library_doc_delete',
    'nisb_library_doc_delete_batch',
    'nisb_library_doc_rename',

    # 核心功能
    'nisb_doc_upload',
    'nisb_doc_search',
    'nisb_doc_bookmark',
    'nisb_doc_recall',
    'nisb_doc_embedding',
    'nisb_doc_annotate',
    'nisb_doc_network',
    'nisb_doc_stats',
    'nisb_doc_search_hybrid',
    'nisb_doc_search_with_filter',
    'nisb_doc_expand_enhanced',
    'nisb_doc_generate_outline',
    'nisb_doc_generate_summary',
    'nisb_doc_analyze_concepts',

    # 库级连续阅读 + 翻译缓存
    'nisb_library_continuous_read',
    'nisb_library_translate_span',
    'nisb_library_doc_evidence',
    'nisb_doc_outline_get',
    'nisb_doc_outline_expand',
    'nisb_doc_outline_translate',
    'nisb_library_export_translated_md',
    'nisb_library_export_translated_pdf',
    # ✅ Evidence（跨范围）
    'nisb_doc_evidence_scope',

    # ✅ Topic QA：doc 级（旧）
    'nisb_doc_qa_ask',
    'nisb_doc_qa_list',

    # ✅ Topic QA：三域落盘（新）
    'nisb_qa_scope_ask',
    'nisb_qa_scope_list',

    # 工具类
    'parse_document',
    'get_supported_formats',
    'validate_extracted_content',
    'PathResolver',
    'StorageMode',
]



