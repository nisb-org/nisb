from __future__ import annotations

from tools.doc.analysis.qa_scope_parts import ask_service as _qa_ask
from tools.doc.analysis.qa_scope_parts import common as _qa_common
from tools.doc.analysis.qa_scope_parts import evidence as _qa_evidence
from tools.doc.analysis.qa_scope_parts import list_service as _qa_list
from tools.doc.analysis.qa_scope_parts import published_at as _qa_published_at
from tools.doc.analysis.qa_scope_parts import r3_selection as _qa_r3
from tools.doc.analysis.qa_scope_parts import storage as _qa_storage
from tools.doc.analysis.qa_scope_parts import time_filters as _qa_time_filters


# ---- common aliases ----
_clean_id = _qa_common.clean_id
_safe_int_or_none = _qa_common.safe_int_or_none
_safe_float_or_none = _qa_common.safe_float_or_none
_safe_bool_or_none = _qa_common.safe_bool_or_none
_parse_iso_dt_any = _qa_common.parse_iso_dt_any


# ---- storage aliases ----
QA_JSONL = _qa_storage.QA_JSONL
QA_MANIFEST_JSON = _qa_storage.QA_MANIFEST_JSON
QA_TOMBSTONES_JSONL = _qa_storage.QA_TOMBSTONES_JSONL
QA_SEG_PREFIX = _qa_storage.QA_SEG_PREFIX
QA_SEG_EXT = _qa_storage.QA_SEG_EXT
QA_SEG_ROTATE_BYTES = _qa_storage.QA_SEG_ROTATE_BYTES
QA_LIST_MAX_SEGMENTS = _qa_storage.QA_LIST_MAX_SEGMENTS
QA_FIND_MAX_SEGMENTS = _qa_storage.QA_FIND_MAX_SEGMENTS

_store_scope_from_args = _qa_storage.store_scope_from_args
_evidence_scope_from_args = _qa_storage.evidence_scope_from_args
_resolve_store_dir = _qa_storage.resolve_store_dir
_qa_path_for_doc = _qa_storage.qa_path_for_doc
_analysis_dir = _qa_storage.analysis_dir
_manifest_path = _qa_storage.manifest_path
_tombstones_path = _qa_storage.tombstones_path
_ensure_analysis_dir = _qa_storage.ensure_analysis_dir
_load_manifest = _qa_storage.load_manifest
_save_manifest = _qa_storage.save_manifest
_segment_filename = _qa_storage.segment_filename
_list_existing_segments_from_disk = _qa_storage.list_existing_segments_from_disk
_maybe_bootstrap_manifest = _qa_storage.maybe_bootstrap_manifest
_rotate_if_needed = _qa_storage.rotate_if_needed
_append_jsonl_segmented = _qa_storage.append_jsonl_segmented
_read_jsonl_lines = _qa_storage.read_jsonl_lines
_list_segment_files_for_read = _qa_storage.list_segment_files_for_read
_load_deleted_set_fast = _qa_storage.load_deleted_set_fast
_delete_tombstone_append = _qa_storage.delete_tombstone_append
_find_qa_anywhere_segmented = _qa_storage.find_qa_anywhere_segmented


# ---- published_at aliases ----
_read_doc_published_at_from_sqlite = _qa_published_at.read_doc_published_at_from_sqlite
_read_doc_published_at_with_source = _qa_published_at.read_doc_published_at_with_source
_attach_evidence_published_at = _qa_published_at.attach_evidence_published_at


# ---- time filter aliases ----
_within_last_days = _qa_time_filters.within_last_days
_extract_search_time_scope_debug = _qa_time_filters.extract_search_time_scope_debug
_doc_time_scope_from_args = _qa_time_filters.doc_time_scope_from_args
_within_doc_time_scope = _qa_time_filters.within_doc_time_scope
_filter_evidence_by_doc_time_scope = _qa_time_filters.filter_evidence_by_doc_time_scope


# ---- evidence aliases ----
_normalize_evidence_items = _qa_evidence.normalize_evidence_items


# ---- r3 aliases ----
_r3_min_from_args = _qa_r3.r3_min_from_args
_ev_doc_key = _qa_r3.ev_doc_key
_ev_span_key = _qa_r3.ev_span_key
_resolve_r3_window_bounds = _qa_r3.resolve_r3_window_bounds
_pick_r3_boundary = _qa_r3.pick_r3_boundary
_merge_evidence_lists = _qa_r3.merge_evidence_lists
_needs_two_phase_backfill = _qa_r3.needs_two_phase_backfill
_build_two_phase_half_windows = _qa_r3.build_two_phase_half_windows
_fetch_half_window_evidence = _qa_r3.fetch_half_window_evidence
_time_bucket_evidence = _qa_r3.time_bucket_evidence
_annotate_evidence_time_bucket = _qa_r3.annotate_evidence_time_bucket
_pick_doc_time_fetch_params = _qa_r3.pick_doc_time_fetch_params


# ---- ask helpers aliases ----
_fallback_answer = _qa_ask.fallback_answer
_dedupe_citations = _qa_ask.dedupe_citations
_dedupe_by_doc_id = _qa_ask.dedupe_by_doc_id
_delete_append_event = _qa_ask.delete_append_event
_load_followup_chain_segmented = _qa_ask.load_followup_chain_segmented


# ---- public entrypoints ----
nisb_qa_scope_list = _qa_list.nisb_qa_scope_list
nisb_qa_scope_ask = _qa_ask.nisb_qa_scope_ask


__all__ = [
    "nisb_qa_scope_list",
    "nisb_qa_scope_ask",
    "QA_JSONL",
    "QA_MANIFEST_JSON",
    "QA_TOMBSTONES_JSONL",
    "QA_SEG_PREFIX",
    "QA_SEG_EXT",
    "QA_SEG_ROTATE_BYTES",
    "QA_LIST_MAX_SEGMENTS",
    "QA_FIND_MAX_SEGMENTS",
]

