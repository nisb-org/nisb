#!/usr/bin/env python3
"""
NISB MCP Server.

This file is the HTTP JSON-RPC entrypoint for the NISB MCP server.
It keeps the legacy full-tool MCP mode intact, and adds a thin
room-scoped external MCP publish gate for third-party MCP clients.

External publish mode is activated only when the request carries:

    Authorization: Bearer <external_mcp_publish_token>

In that mode:
- tools/list returns only the static external room provider tools.
- tools/call can only call those external room provider tools.
- The Bearer token is resolved into a sanitized room scope.
- The sanitized scope is injected into tool arguments.
- The raw token is never logged or forwarded to room/runtime code.

This is intentionally not a federation rewrite, not a global room catalog,
and not a runtime policy change.
"""

from __future__ import annotations

import json
import http.server
import socketserver
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import sys
sys.path.insert(0, "/srv")


from tools.sense import (
    nisb_sense_record,
    nisb_sense_quick_note,
    nisb_sense_mark_important,
    nisb_sense_quick_note_segment,
    nisb_sense_list_notes,
    nisb_sense_search_notes,
)

from tools.recall import (
    nisb_case_recall,
    nisb_sense_recall_note,
)

from tools.work import (
    nisb_work_query,
    nisb_work_hot,
    nisb_work_stats,
    nisb_work_activate,
    nisb_list_concepts,
)


from tools.query import (
    nisb_case_query,
    nisb_unified_query,
    nisb_smart_search,
)

from tools.cases import (
    nisb_case_save,
)

from tools.annotate import (
    nisb_annotate,
    nisb_edit_annotation,
    nisb_delete_annotation,
    nisb_annotate_annotation,
    nisb_search_annotations,
    nisb_concept_timeline,
    nisb_annotation_stats,
    rebuild_annotation_index,
)

from tools.corpus import (
    nisb_corpus_ingest,
    nisb_corpus_query,
    nisb_corpus_semantic_search,
    nisb_corpus_enrich,
    nisb_corpus_batch_ingest,
    nisb_corpus_stats,
    nisb_corpus_doctor,
    nisb_corpus_recall,
    nisb_corpus_recommend,
    nisb_corpus_export,
    nisb_corpus_test_creation,
    nisb_corpus_compare_baseline,
)

from tools.relations import (
    nisb_relation_create,
    nisb_relation_query,
    nisb_relation_delete,
    nisb_relation_stats,
    nisb_discover_relations,
    nisb_discover_relations_batch,
    nisb_export_relation_network,
    nisb_relation_recommend,
    nisb_relation_path,
    nisb_relation_context,
    nisb_relation_analyze,
    nisb_relation_evolve,
)

from tools.relations.unified import (
    nisb_query_all,
    nisb_create_unified,
    nisb_migrate_to_hybrid,
)

from core.synapses import (
    batch_decay_synapses,
)

from tools.filesystem import (
    nisb_file_create,
    nisb_file_read,
    nisb_file_update,
    nisb_file_delete,
    nisb_file_move,
    nisb_file_move_path,
    nisb_file_copy,
    nisb_file_rename,
    nisb_file_list,
    nisb_file_search,
    nisb_file_info,
    nisb_dir_create,
    nisb_dir_list,
    nisb_dir_tree,
    nisb_file_list_allowed_directories,
    nisb_file_read_multiple,
    nisb_file_batch_delete,
    nisb_file_batch_tag,
    nisb_dir_delete,
    nisb_dir_delete_recursive,
    nisb_note_to_brain,
    nisb_batch_notes_to_brain,
    nisb_favorites_list_files,
    nisb_favorites_toggle_file,
    nisb_favorites_set_highlight,
    nisb_favorites_clear_highlight,
    nisb_fs_send_to_library,
    nisb_fs_send_dir_to_library,
    nisb_fs_library_status_batch,
    nisb_fs_audit_tail,
    nisb_fs_restore_backup,
    nisb_fs_apply_batch,
    nisb_fs_audit_search,
    nisb_dir_move_path,
    nisb_file_read_base64,
    nisb_file_write_base64,
    nisb_file_write_base64_chunk,
)

from tools.admin import (
    nisb_admin_list_backups,
    nisb_admin_rollback,
    nisb_admin_view_logs,
)

from tools.entities import (
    nisb_concept_create,
    nisb_concept_search,
    nisb_concept_annotate,
    nisb_concept_relate,
    nisb_author_create,
    nisb_author_search,
    nisb_book_create,
    nisb_book_search,
    nisb_topic_create,
    nisb_topic_search,
    nisb_entity_search,
    nisb_entity_network,
    nisb_entity_search_personalized,
    nisb_mine_implicit_relations,
    nisb_auto_link_entities,
)

from tools.doc import (
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
    nisb_doc_upload_to_library,
    nisb_doc_upload_to_library_web,
    nisb_library_doc_delete,
    nisb_library_doc_delete_batch,
    nisb_library_doc_rename,
    nisb_library_continuous_read,
    nisb_library_translate_span,
    nisb_library_doc_evidence,
    nisb_library_export_translated_md,
    nisb_library_export_translated_pdf,
    nisb_doc_qa_ask,
    nisb_doc_qa_list,
    nisb_doc_evidence_scope,
)

from tools.doc.analysis.qa_scope import nisb_qa_scope_ask, nisb_qa_scope_list

from tools.library_groups import (
    nisb_library_group_upsert,
    nisb_library_group_list,
    nisb_library_group_delete,
)

from tools.filesystem.bulk_trash import nisb_fs_bulk_delete, nisb_fs_bulk_restore
from tools.filesystem.trash_batches import nisb_fs_trash_batches_list
from tools.filesystem.trash_batch_detail import nisb_fs_trash_batch_get, nisb_fs_trash_batch_purge
from tools.filesystem.trash_purge_all import nisb_fs_trash_purge_all
from tools.filesystem.backups_tools import nisb_fs_backups_stats, nisb_fs_backups_purge_all

from tools.bookmarks import (
    nisb_bookmark_add,
    nisb_bookmark_list,
    nisb_bookmark_delete,
)

from tools.annotations import (
    nisb_library_annotation_add,
    nisb_library_annotation_list,
    nisb_library_annotation_delete,
)

from tools.annotations import (
    nisb_span_annotation_add,
    nisb_span_annotation_list,
    nisb_span_annotation_delete,
)

from tools.libraries import (
    nisb_library_create,
    nisb_library_list,
    nisb_library_delete,
    nisb_library_stats,
    nisb_library_get_info,
    nisb_library_rename,
    nisb_library_import_rss,
)

from tools.util_translate import nisb_util_translate
from tools.tts import nisb_tts_speak
from tools.util_phonetics import nisb_util_phonetics
from tools.util_translate_chunks import nisb_util_translate_chunks
from tools.doc import nisb_doc_outline_get, nisb_doc_outline_expand, nisb_doc_outline_translate

from tools.user import (
    nisb_user_register,
    nisb_user_login,
    nisb_user_preferences_get,
    nisb_user_preferences_set,
)
from tools.chat import (
    nisb_chat_create,
    nisb_chat_send,
    nisb_chat_history,
    nisb_chat_load,
    nisb_chat_models,
    nisb_chat_rename,
    nisb_chat_delete,
    nisb_chat_update_labels,
    nisb_chat_get_labels,
    nisb_chat_list_labels,
    nisb_chat_with_library_context,
)
from tools.chat.chat_orchestrator import nisb_chat_orchestrate

from tools.chat.conversation_trash import (
    nisb_chat_conversation_trash_delete,
    nisb_chat_conversation_trash_restore,
    nisb_chat_conversation_trash_batches_list,
    nisb_chat_conversation_trash_batch_purge,
    nisb_chat_conversation_trash_purge_all,
)

from tools.market import (
    nisb_market_publish,
    nisb_market_search,
    nisb_market_get,
    nisb_market_event,
)

from tools.federation import (
    nisb_fed_accept_room_invite,
    nisb_fed_add_peer,
    nisb_fed_call,
    nisb_fed_extend_room_invite,
    nisb_fed_issue_room_invite,
    nisb_fed_list_joined_rooms,
    nisb_fed_list_peers,
    nisb_fed_list_room_invites,
    nisb_fed_peer_health_check,
    nisb_fed_remote_room_join,
    nisb_fed_revoke_room_invite,
)

from tools.feed import (
    nisb_feed_publish,
    nisb_feed_list,
    nisb_feed_list_by_tag,
    nisb_feed_recommend,
    nisb_feed_fetch_content,
    nisb_feed_vote,
    nisb_feed_delete_post,
    nisb_feed_compact,
    nisb_feed_get_tags,
    nisb_feed_comment_add,
    nisb_feed_comment_list,
    nisb_feed_comment_delete,
    nisb_feed_notifications,
    nisb_feed_mark_read,
    nisb_feed_follow,
    nisb_feed_unfollow,
    nisb_feed_following_list,
    nisb_feed_followers_list,
    nisb_feed_mark_all_read,
    nisb_feed_get_profile,
    nisb_feed_update_profile,
    nisb_feed_list_bookmarks,
    nisb_feed_avatar_upload,
    nisb_feed_image_stage_upload,
    nisb_feed_user_file_base64,
    nisb_feed_clipboard_import,
    nisb_feed_following_list_v2,
    nisb_feed_followers_list_v2,
    nisb_feed_comment_vote,
)

from tools.rss import (
    nisb_rss_semantic_search,
    nisb_rss_cache_stats,
    nisb_rss_cache_clear,
    nisb_rss_index_rebuild,
    nisb_rss_data_cleanup,
    nisb_rss_auto_cleanup_config_get,
    nisb_rss_auto_cleanup_config_set,
    nisb_rss_auto_cleanup_run_now,
    nisb_rss_auto_cleanup_config_delete,
    nisb_rss_gate_prefs_get,
    nisb_rss_gate_prefs_set,
    nisb_rss_delete_article,
    nisb_rss_override_article,
    nisb_rss_fetch_due,
    nisb_rss_auto_fetch_config_get,
    nisb_rss_auto_fetch_config_set,
    nisb_rss_auto_fetch_run_now,
    nisb_rss_auto_fetch_config_delete,
    nisb_rss_add_feed,
    nisb_rss_list_feeds,
    nisb_rss_fetch,
    nisb_rss_list_articles,
    nisb_rss_get_article,
    nisb_rss_set_state,
    nisb_rss_evidence_scope,
    nisb_rss_update_feed,
    nisb_rss_delete_feed,
    nisb_rss_list_tags,
    nisb_rss_gate_candidates,
    nisb_rss_gate_import_to_library,
    nisb_rss_spam_add,
    nisb_rss_spam_list,
    nisb_rss_spam_delete,
    nisb_rss_gate_bulk_delete,
    nisb_rss_auto_import_rules_get,
    nisb_rss_auto_import_rules_set,
    nisb_rss_auto_import_run_rule,
    nisb_rss_auto_import_run_due,
)

from tools.search import (
    nisb_search_semantic,
    nisb_search_cross_module,
)

from tools.code_agent import nisb_code_build_index, nisb_code_search
from tools.interpreter import nisb_execute_code

from tools.timeline import (
    nisb_timeline_recent_activities,
    nisb_timeline_heatmap_data,
    nisb_timeline_delete_items,
    nisb_timeline_prune_missing_documents,
    nisb_timeline_compact_activity_log,
    nisb_timeline_hard_delete_by_pattern,
)

from tools.workspace import (
    nisb_workspace_save,
    nisb_workspace_load,
    nisb_workspace_list,
    nisb_workspace_create,
    nisb_workspace_rename,
    nisb_workspace_delete,
    nisb_workspace_files_state_get,
    nisb_workspace_files_state_set,
    nisb_workspace_files_state_clear,
    nisb_workspace_files_state_save,
    nisb_workspace_files_state_apply,
    nisb_workspace_snapshot_get,
    nisb_workspace_tree,
    nisb_workspace_read_entry,
    nisb_workspace_search_hybrid,
    nisb_workspace_write_entry,
    nisb_workspace_create_entry,
    nisb_workspace_delete_entry,
    nisb_workspace_rename_entry,
    nisb_workspace_agent_notebook_upsert,
)

from tools.user_workspace import (
    nisb_user_workspace_get_current,
    nisb_user_workspace_set_current,
)

from tools.filesystem.snapshot_tools import (
    nisb_fs_snapshot,
    nisb_fs_trash_list,
    nisb_fs_trash_restore,
)

from tools.rooms_shared import (
    nisb_room_shared_whoami,
    nisb_room_shared_create,
    nisb_room_shared_list,
    nisb_room_shared_post,
    nisb_room_runtime_stop_current,
    nisb_room_shared_provider_post,
    nisb_room_runtime_pause_current,
    nisb_room_runtime_resume_from_checkpoint,
    nisb_room_shared_recent,
    nisb_room_events_recent,
    nisb_room_shared_join,
    nisb_room_get_info,
    nisb_room_update_info,
    nisb_room_get_state,
    nisb_room_update_state,
    nisb_room_revoke_federated_member_access,
    nisb_room_role_list,
    nisb_room_role_create,
    nisb_room_role_update,
    nisb_room_role_delete,
    nisb_room_mcp_share_ref_issue,
    nisb_room_mcp_provider_share_ref_resolve,
    nisb_room_workspace_get,
    nisb_room_workspace_set,
    nisb_room_workspace_clear,
    nisb_room_save_intent_parse,
    nisb_room_save_from_text,
    nisb_room_events_replay,
    nisb_room_mcp_provider_list,
    nisb_room_mcp_provider_call,
    nisb_room_mcp_external_provider_list,
    nisb_room_mcp_external_provider_call,
    nisb_room_mcp_external_publish_get,
    nisb_room_mcp_external_publish_enable,
    nisb_room_mcp_external_publish_revoke,
    nisb_room_mcp_external_publish_regenerate,
    nisb_room_supervisor_skills_list,
    nisb_room_mcp_publication_get,
    nisb_room_mcp_grant_list,
    nisb_room_mcp_grant_revoke,
)

from tools.reading_optimizer.tools import (
    nisb_readopt_get_default_preset,
    nisb_readopt_set_default_preset,
    nisb_readopt_clear_default_preset,
    nisb_readopt_get_custom_presets,
    nisb_readopt_save_custom_preset,
    nisb_readopt_delete_custom_preset,
)

from tools.pdf import nisb_pdf_convert_to_note
from tools.epub import nisb_epub_convert_to_note

from tools.office import (
    nisb_docx_convert_to_note,
    nisb_pptx_convert_to_note,
    nisb_doc_convert_to_note,
    nisb_ppt_convert_to_note,
    nisb_txt_convert_to_structured_md,
)

from tools.bookmarks.bookmark_list_all import nisb_bookmark_list_all
from tools.annotations.span_annotation_list_all import nisb_annotation_list_all
from tools.llm import nisb_llm_call


SESSION_ID = os.environ.get("MCP_SESSION_ID") or uuid.uuid4().hex
BASE_PATH = os.environ.get("NISB_BASE_PATH", "/data")
SCHEMA_FILE = Path("/srv/schema.json")


TOOLS = {
    "nisb_sense_record": nisb_sense_record,
    "nisb_sense_quick_note": nisb_sense_quick_note,
    "nisb_sense_mark_important": nisb_sense_mark_important,
    "nisb_sense_quick_note_segment": nisb_sense_quick_note_segment,
    "nisb_sense_list_notes": nisb_sense_list_notes,
    "nisb_sense_search_notes": nisb_sense_search_notes,

    "nisb_sense_recall_note": nisb_sense_recall_note,
    "nisb_case_recall": nisb_case_recall,

    "nisb_work_query": nisb_work_query,
    "nisb_work_hot": nisb_work_hot,
    "nisb_work_stats": nisb_work_stats,
    "nisb_work_activate": nisb_work_activate,
    "nisb_list_concepts": nisb_list_concepts,


    "nisb_smart_search": nisb_smart_search,
    "nisb_case_query": nisb_case_query,
    "nisb_unified_query": nisb_unified_query,

    "nisb_case_save": nisb_case_save,

    "nisb_annotate": nisb_annotate,
    "nisb_edit_annotation": nisb_edit_annotation,
    "nisb_delete_annotation": nisb_delete_annotation,
    "nisb_annotate_annotation": nisb_annotate_annotation,
    "nisb_search_annotations": nisb_search_annotations,
    "nisb_concept_timeline": nisb_concept_timeline,
    "nisb_annotation_stats": nisb_annotation_stats,
    "nisb_rebuild_annotation_index": rebuild_annotation_index,

    "nisb_corpus_ingest": nisb_corpus_ingest,
    "nisb_corpus_query": nisb_corpus_query,
    "nisb_corpus_semantic_search": nisb_corpus_semantic_search,
    "nisb_corpus_enrich": nisb_corpus_enrich,
    "nisb_corpus_batch_ingest": nisb_corpus_batch_ingest,
    "nisb_corpus_stats": nisb_corpus_stats,
    "nisb_corpus_doctor": nisb_corpus_doctor,
    "nisb_corpus_recall": nisb_corpus_recall,
    "nisb_corpus_recommend": nisb_corpus_recommend,
    "nisb_corpus_export": nisb_corpus_export,
    "nisb_corpus_test_creation": nisb_corpus_test_creation,
    "nisb_corpus_compare_baseline": nisb_corpus_compare_baseline,

    "nisb_relation_create": nisb_relation_create,
    "nisb_relation_query": nisb_relation_query,
    "nisb_relation_delete": nisb_relation_delete,
    "nisb_relation_stats": nisb_relation_stats,
    "nisb_discover_relations": nisb_discover_relations,
    "nisb_discover_relations_batch": nisb_discover_relations_batch,
    "nisb_export_relation_network": nisb_export_relation_network,
    "nisb_relation_recommend": nisb_relation_recommend,
    "nisb_relation_path": nisb_relation_path,
    "nisb_relation_context": nisb_relation_context,
    "nisb_relation_analyze": nisb_relation_analyze,
    "nisb_relation_evolve": nisb_relation_evolve,

    "nisb_query_all": nisb_query_all,
    "nisb_create_unified": nisb_create_unified,
    "nisb_migrate_to_hybrid": nisb_migrate_to_hybrid,
    "nisb_synapse_decay": lambda args: batch_decay_synapses(
        args.get("_base_path", BASE_PATH),
        int(args.get("days_threshold", 30)),
    ),

    "nisb_file_create": nisb_file_create,
    "nisb_file_read": nisb_file_read,
    "nisb_file_update": nisb_file_update,
    "nisb_file_delete": nisb_file_delete,
    "nisb_file_move": nisb_file_move,
    "nisb_file_move_path": nisb_file_move_path,
    "nisb_file_copy": nisb_file_copy,
    "nisb_file_rename": nisb_file_rename,
    "nisb_file_list": nisb_file_list,
    "nisb_file_search": nisb_file_search,
    "nisb_file_info": nisb_file_info,
    "nisb_dir_create": nisb_dir_create,
    "nisb_dir_list": nisb_dir_list,
    "nisb_dir_tree": nisb_dir_tree,
    "nisb_file_list_allowed_directories": nisb_file_list_allowed_directories,
    "nisb_file_read_multiple": nisb_file_read_multiple,
    "nisb_file_batch_delete": nisb_file_batch_delete,
    "nisb_file_batch_tag": nisb_file_batch_tag,
    "nisb_dir_delete": nisb_dir_delete,
    "nisb_dir_delete_recursive": nisb_dir_delete_recursive,
    "nisb_note_to_brain": nisb_note_to_brain,
    "nisb_batch_notes_to_brain": nisb_batch_notes_to_brain,
    "nisb_favorites_list_files": nisb_favorites_list_files,
    "nisb_favorites_toggle_file": nisb_favorites_toggle_file,
    "nisb_favorites_set_highlight": nisb_favorites_set_highlight,
    "nisb_favorites_clear_highlight": nisb_favorites_clear_highlight,
    "nisb_fs_send_to_library": nisb_fs_send_to_library,
    "nisb_fs_send_dir_to_library": nisb_fs_send_dir_to_library,
    "nisb_fs_library_status_batch": nisb_fs_library_status_batch,
    "nisb_fs_audit_tail": nisb_fs_audit_tail,
    "nisb_fs_restore_backup": nisb_fs_restore_backup,
    "nisb_fs_apply_batch": nisb_fs_apply_batch,
    "nisb_fs_audit_search": nisb_fs_audit_search,
    "nisb_fs_snapshot": nisb_fs_snapshot,
    "nisb_fs_trash_list": nisb_fs_trash_list,
    "nisb_fs_trash_restore": nisb_fs_trash_restore,
    "nisb_fs_bulk_delete": nisb_fs_bulk_delete,
    "nisb_fs_bulk_restore": nisb_fs_bulk_restore,
    "nisb_fs_trash_batches_list": nisb_fs_trash_batches_list,
    "nisb_fs_trash_batch_get": nisb_fs_trash_batch_get,
    "nisb_fs_trash_batch_purge": nisb_fs_trash_batch_purge,
    "nisb_fs_trash_purge_all": nisb_fs_trash_purge_all,
    "nisb_fs_backups_stats": nisb_fs_backups_stats,
    "nisb_fs_backups_purge_all": nisb_fs_backups_purge_all,
    "nisb_dir_move_path": nisb_dir_move_path,
    "nisb_file_read_base64": nisb_file_read_base64,
    "nisb_pdf_convert_to_note": nisb_pdf_convert_to_note,
    "nisb_epub_convert_to_note": nisb_epub_convert_to_note,
    "nisb_docx_convert_to_note": nisb_docx_convert_to_note,
    "nisb_pptx_convert_to_note": nisb_pptx_convert_to_note,
    "nisb_doc_convert_to_note": nisb_doc_convert_to_note,
    "nisb_ppt_convert_to_note": nisb_ppt_convert_to_note,
    "nisb_txt_convert_to_structured_md": nisb_txt_convert_to_structured_md,
    "nisb_file_write_base64": nisb_file_write_base64,
    "nisb_file_write_base64_chunk": nisb_file_write_base64_chunk,

    "nisb_admin_list_backups": nisb_admin_list_backups,
    "nisb_admin_rollback": nisb_admin_rollback,
    "nisb_admin_view_logs": nisb_admin_view_logs,

    "nisb_execute_code": nisb_execute_code,

    "nisb_concept_create": nisb_concept_create,
    "nisb_concept_search": nisb_concept_search,
    "nisb_concept_annotate": nisb_concept_annotate,
    "nisb_concept_relate": nisb_concept_relate,
    "nisb_author_create": nisb_author_create,
    "nisb_author_search": nisb_author_search,
    "nisb_book_create": nisb_book_create,
    "nisb_book_search": nisb_book_search,
    "nisb_topic_create": nisb_topic_create,
    "nisb_topic_search": nisb_topic_search,
    "nisb_entity_search": nisb_entity_search,
    "nisb_entity_network": nisb_entity_network,
    "nisb_entity_search_personalized": nisb_entity_search_personalized,
    "nisb_mine_implicit_relations": nisb_mine_implicit_relations,
    "nisb_auto_link_entities": nisb_auto_link_entities,

    "nisb_doc_upload": nisb_doc_upload,
    "nisb_doc_search": nisb_doc_search,
    "nisb_doc_bookmark": nisb_doc_bookmark,
    "nisb_doc_recall": nisb_doc_recall,
    "nisb_doc_embedding": nisb_doc_embedding,
    "nisb_doc_annotate": nisb_doc_annotate,
    "nisb_doc_network": nisb_doc_network,
    "nisb_doc_stats": nisb_doc_stats,
    "nisb_library_annotation_add": nisb_library_annotation_add,
    "nisb_library_annotation_list": nisb_library_annotation_list,
    "nisb_library_annotation_delete": nisb_library_annotation_delete,
    "nisb_span_annotation_add": nisb_span_annotation_add,
    "nisb_span_annotation_list": nisb_span_annotation_list,
    "nisb_span_annotation_delete": nisb_span_annotation_delete,
    "nisb_doc_search_hybrid": nisb_doc_search_hybrid,
    "nisb_doc_search_with_filter": nisb_doc_search_with_filter,
    "nisb_doc_expand_enhanced": nisb_doc_expand_enhanced,
    "nisb_doc_generate_outline": nisb_doc_generate_outline,
    "nisb_doc_generate_summary": nisb_doc_generate_summary,
    "nisb_doc_analyze_concepts": nisb_doc_analyze_concepts,
    "nisb_doc_upload_to_library": nisb_doc_upload_to_library,
    "nisb_doc_upload_to_library_web": nisb_doc_upload_to_library_web,
    "nisb_library_doc_delete": nisb_library_doc_delete,
    "nisb_library_doc_delete_batch": nisb_library_doc_delete_batch,
    "nisb_library_doc_rename": nisb_library_doc_rename,
    "nisb_library_continuous_read": nisb_library_continuous_read,
    "nisb_library_translate_span": nisb_library_translate_span,
    "nisb_library_doc_evidence": nisb_library_doc_evidence,
    "nisb_library_export_translated_md": nisb_library_export_translated_md,
    "nisb_library_export_translated_pdf": nisb_library_export_translated_pdf,
    "nisb_doc_qa_ask": nisb_doc_qa_ask,
    "nisb_doc_qa_list": nisb_doc_qa_list,
    "nisb_doc_evidence_scope": nisb_doc_evidence_scope,
    "nisb_qa_scope_ask": nisb_qa_scope_ask,
    "nisb_qa_scope_list": nisb_qa_scope_list,
    "nisb_library_group_upsert": nisb_library_group_upsert,
    "nisb_library_group_list": nisb_library_group_list,
    "nisb_library_group_delete": nisb_library_group_delete,

    "nisb_library_create": nisb_library_create,
    "nisb_library_list": nisb_library_list,
    "nisb_library_delete": nisb_library_delete,
    "nisb_library_stats": nisb_library_stats,
    "nisb_library_get_info": nisb_library_get_info,
    "nisb_library_rename": nisb_library_rename,
    "nisb_library_import_rss": nisb_library_import_rss,

    "nisb_bookmark_add": nisb_bookmark_add,
    "nisb_bookmark_list": nisb_bookmark_list,
    "nisb_bookmark_delete": nisb_bookmark_delete,

    "nisb_user_register": nisb_user_register,
    "nisb_user_login": nisb_user_login,
    "nisb_user_preferences_get": nisb_user_preferences_get,
    "nisb_user_preferences_set": nisb_user_preferences_set,

    "nisb_chat_create": nisb_chat_create,
    "nisb_chat_send": nisb_chat_send,
    "nisb_chat_history": nisb_chat_history,
    "nisb_chat_load": nisb_chat_load,
    "nisb_chat_models": nisb_chat_models,
    "nisb_chat_rename": nisb_chat_rename,
    "nisb_chat_delete": nisb_chat_delete,
    "nisb_chat_update_labels": nisb_chat_update_labels,
    "nisb_chat_get_labels": nisb_chat_get_labels,
    "nisb_chat_list_labels": nisb_chat_list_labels,
    "nisb_chat_with_library_context": nisb_chat_with_library_context,
    "nisb_chat_orchestrate": nisb_chat_orchestrate,
    "nisb_chat_conversation_trash_delete": nisb_chat_conversation_trash_delete,
    "nisb_chat_conversation_trash_restore": nisb_chat_conversation_trash_restore,
    "nisb_chat_conversation_trash_batches_list": nisb_chat_conversation_trash_batches_list,
    "nisb_chat_conversation_trash_batch_purge": nisb_chat_conversation_trash_batch_purge,
    "nisb_chat_conversation_trash_purge_all": nisb_chat_conversation_trash_purge_all,

    "nisb_market_publish": nisb_market_publish,
    "nisb_market_search": nisb_market_search,
    "nisb_market_get": nisb_market_get,
    "nisb_market_event": nisb_market_event,

    "nisb_fed_add_peer": nisb_fed_add_peer,
    "nisb_fed_issue_room_invite": nisb_fed_issue_room_invite,
    "nisb_fed_list_peers": nisb_fed_list_peers,
    "nisb_fed_list_room_invites": nisb_fed_list_room_invites,
    "nisb_fed_remote_room_join": nisb_fed_remote_room_join,
    "nisb_fed_accept_room_invite": nisb_fed_accept_room_invite,
    "nisb_fed_call": nisb_fed_call,
    "nisb_fed_list_joined_rooms": nisb_fed_list_joined_rooms,
    "nisb_fed_peer_health_check": nisb_fed_peer_health_check,
    "nisb_fed_revoke_room_invite": nisb_fed_revoke_room_invite,
    "nisb_fed_extend_room_invite": nisb_fed_extend_room_invite,

    "nisb_feed_publish": nisb_feed_publish,
    "nisb_feed_list": nisb_feed_list,
    "nisb_feed_fetch_content": nisb_feed_fetch_content,
    "nisb_feed_vote": nisb_feed_vote,
    "nisb_feed_delete_post": nisb_feed_delete_post,
    "nisb_feed_compact": nisb_feed_compact,
    "nisb_feed_get_tags": nisb_feed_get_tags,
    "nisb_feed_list_by_tag": nisb_feed_list_by_tag,
    "nisb_feed_recommend": nisb_feed_recommend,
    "nisb_feed_comment_add": nisb_feed_comment_add,
    "nisb_feed_comment_list": nisb_feed_comment_list,
    "nisb_feed_comment_delete": nisb_feed_comment_delete,
    "nisb_feed_notifications": nisb_feed_notifications,
    "nisb_feed_mark_read": nisb_feed_mark_read,
    "nisb_feed_follow": nisb_feed_follow,
    "nisb_feed_unfollow": nisb_feed_unfollow,
    "nisb_feed_following_list": nisb_feed_following_list,
    "nisb_feed_followers_list": nisb_feed_followers_list,
    "nisb_feed_mark_all_read": nisb_feed_mark_all_read,
    "nisb_feed_get_profile": nisb_feed_get_profile,
    "nisb_feed_update_profile": nisb_feed_update_profile,
    "nisb_feed_list_bookmarks": nisb_feed_list_bookmarks,
    "nisb_feed_avatar_upload": nisb_feed_avatar_upload,
    "nisb_feed_image_stage_upload": nisb_feed_image_stage_upload,
    "nisb_feed_user_file_base64": nisb_feed_user_file_base64,
    "nisb_feed_clipboard_import": nisb_feed_clipboard_import,
    "nisb_feed_following_list_v2": nisb_feed_following_list_v2,
    "nisb_feed_followers_list_v2": nisb_feed_followers_list_v2,
    "nisb_feed_comment_vote": nisb_feed_comment_vote,

    "nisb_rss_semantic_search": nisb_rss_semantic_search,
    "nisb_rss_cache_stats": nisb_rss_cache_stats,
    "nisb_rss_cache_clear": nisb_rss_cache_clear,
    "nisb_rss_index_rebuild": nisb_rss_index_rebuild,
    "nisb_rss_data_cleanup": nisb_rss_data_cleanup,
    "nisb_rss_auto_cleanup_config_get": nisb_rss_auto_cleanup_config_get,
    "nisb_rss_auto_cleanup_config_set": nisb_rss_auto_cleanup_config_set,
    "nisb_rss_auto_cleanup_run_now": nisb_rss_auto_cleanup_run_now,
    "nisb_rss_auto_cleanup_config_delete": nisb_rss_auto_cleanup_config_delete,
    "nisb_rss_gate_prefs_get": nisb_rss_gate_prefs_get,
    "nisb_rss_gate_prefs_set": nisb_rss_gate_prefs_set,
    "nisb_rss_delete_article": nisb_rss_delete_article,
    "nisb_rss_override_article": nisb_rss_override_article,
    "nisb_rss_add_feed": nisb_rss_add_feed,
    "nisb_rss_list_feeds": nisb_rss_list_feeds,
    "nisb_rss_fetch": nisb_rss_fetch,
    "nisb_rss_list_articles": nisb_rss_list_articles,
    "nisb_rss_get_article": nisb_rss_get_article,
    "nisb_rss_set_state": nisb_rss_set_state,
    "nisb_rss_evidence_scope": nisb_rss_evidence_scope,
    "nisb_rss_update_feed": nisb_rss_update_feed,
    "nisb_rss_delete_feed": nisb_rss_delete_feed,
    "nisb_rss_list_tags": nisb_rss_list_tags,
    "nisb_rss_gate_candidates": nisb_rss_gate_candidates,
    "nisb_rss_gate_import_to_library": nisb_rss_gate_import_to_library,
    "nisb_rss_spam_add": nisb_rss_spam_add,
    "nisb_rss_spam_list": nisb_rss_spam_list,
    "nisb_rss_spam_delete": nisb_rss_spam_delete,
    "nisb_rss_gate_bulk_delete": nisb_rss_gate_bulk_delete,
    "nisb_rss_auto_import_rules_get": nisb_rss_auto_import_rules_get,
    "nisb_rss_auto_import_rules_set": nisb_rss_auto_import_rules_set,
    "nisb_rss_auto_import_run_rule": nisb_rss_auto_import_run_rule,
    "nisb_rss_auto_import_run_due": nisb_rss_auto_import_run_due,
    "nisb_rss_fetch_due": nisb_rss_fetch_due,
    "nisb_rss_auto_fetch_config_get": nisb_rss_auto_fetch_config_get,
    "nisb_rss_auto_fetch_config_set": nisb_rss_auto_fetch_config_set,
    "nisb_rss_auto_fetch_run_now": nisb_rss_auto_fetch_run_now,
    "nisb_rss_auto_fetch_config_delete": nisb_rss_auto_fetch_config_delete,

    "nisb_util_translate": nisb_util_translate,
    "nisb_tts_speak": nisb_tts_speak,
    "nisb_util_phonetics": nisb_util_phonetics,
    "nisb_util_translate_chunks": nisb_util_translate_chunks,

    "nisb_doc_outline_get": nisb_doc_outline_get,
    "nisb_doc_outline_expand": nisb_doc_outline_expand,
    "nisb_doc_outline_translate": nisb_doc_outline_translate,

    "nisb_search_semantic": nisb_search_semantic,
    "nisb_search_cross_module": nisb_search_cross_module,

    "nisb_timeline_recent_activities": nisb_timeline_recent_activities,
    "nisb_timeline_heatmap_data": nisb_timeline_heatmap_data,
    "nisb_timeline_delete_items": nisb_timeline_delete_items,
    "nisb_timeline_prune_missing_documents": nisb_timeline_prune_missing_documents,
    "nisb_timeline_compact_activity_log": nisb_timeline_compact_activity_log,
    "nisb_timeline_hard_delete_by_pattern": nisb_timeline_hard_delete_by_pattern,

    "nisb_workspace_save": nisb_workspace_save,
    "nisb_workspace_load": nisb_workspace_load,
    "nisb_workspace_list": nisb_workspace_list,
    "nisb_workspace_files_state_get": nisb_workspace_files_state_get,
    "nisb_workspace_files_state_set": nisb_workspace_files_state_set,
    "nisb_workspace_files_state_clear": nisb_workspace_files_state_clear,
    "nisb_workspace_files_state_save": nisb_workspace_files_state_save,
    "nisb_workspace_files_state_apply": nisb_workspace_files_state_apply,
    "nisb_workspace_create": nisb_workspace_create,
    "nisb_workspace_rename": nisb_workspace_rename,
    "nisb_workspace_delete": nisb_workspace_delete,
    "nisb_workspace_snapshot_get": nisb_workspace_snapshot_get,
    "nisb_workspace_tree": nisb_workspace_tree,
    "nisb_workspace_read_entry": nisb_workspace_read_entry,
    "nisb_workspace_search_hybrid": nisb_workspace_search_hybrid,
    "nisb_workspace_write_entry": nisb_workspace_write_entry,
    "nisb_workspace_create_entry": nisb_workspace_create_entry,
    "nisb_workspace_delete_entry": nisb_workspace_delete_entry,
    "nisb_workspace_rename_entry": nisb_workspace_rename_entry,
    "nisb_workspace_agent_notebook_upsert": nisb_workspace_agent_notebook_upsert,

    "nisb_user_workspace_get_current": nisb_user_workspace_get_current,
    "nisb_user_workspace_set_current": nisb_user_workspace_set_current,

    "nisb_code_build_index": nisb_code_build_index,
    "nisb_code_search": nisb_code_search,

    "nisb_room_shared_whoami": nisb_room_shared_whoami,
    "nisb_room_shared_create": nisb_room_shared_create,
    "nisb_room_shared_list": nisb_room_shared_list,
    "nisb_room_shared_post": nisb_room_shared_post,
    "nisb_room_shared_provider_post": nisb_room_shared_provider_post,
    "nisb_room_runtime_stop_current": nisb_room_runtime_stop_current,
    "nisb_room_runtime_pause_current": nisb_room_runtime_pause_current,
    "nisb_room_runtime_resume_from_checkpoint": nisb_room_runtime_resume_from_checkpoint,
    "nisb_room_shared_recent": nisb_room_shared_recent,
    "nisb_room_events_recent": nisb_room_events_recent,
    "nisb_room_shared_join": nisb_room_shared_join,
    "nisb_room_get_info": nisb_room_get_info,
    "nisb_room_update_info": nisb_room_update_info,
    "nisb_room_get_state": nisb_room_get_state,
    "nisb_room_update_state": nisb_room_update_state,
    "nisb_room_revoke_federated_member_access": nisb_room_revoke_federated_member_access,
    "nisb_room_role_list": nisb_room_role_list,
    "nisb_room_mcp_share_ref_issue": nisb_room_mcp_share_ref_issue,
    "nisb_room_mcp_provider_share_ref_resolve": nisb_room_mcp_provider_share_ref_resolve,
    "nisb_room_role_create": nisb_room_role_create,
    "nisb_room_role_update": nisb_room_role_update,
    "nisb_room_role_delete": nisb_room_role_delete,
    "nisb_room_workspace_get": nisb_room_workspace_get,
    "nisb_room_workspace_set": nisb_room_workspace_set,
    "nisb_room_workspace_clear": nisb_room_workspace_clear,
    "nisb_room_save_intent_parse": nisb_room_save_intent_parse,
    "nisb_room_save_from_text": nisb_room_save_from_text,
    "nisb_room_events_replay": nisb_room_events_replay,
    "nisb_room_mcp_provider_list": nisb_room_mcp_provider_list,
    "nisb_room_mcp_provider_call": nisb_room_mcp_provider_call,
    "nisb_room_mcp_external_publish_get": nisb_room_mcp_external_publish_get,
    "nisb_room_mcp_external_publish_enable": nisb_room_mcp_external_publish_enable,
    "nisb_room_mcp_external_publish_revoke": nisb_room_mcp_external_publish_revoke,
    "nisb_room_mcp_external_publish_regenerate": nisb_room_mcp_external_publish_regenerate,
    "nisb_room_mcp_external_provider_list": nisb_room_mcp_external_provider_list,
    "nisb_room_mcp_external_provider_call": nisb_room_mcp_external_provider_call,
    "nisb_room_supervisor_skills_list": nisb_room_supervisor_skills_list,
    "nisb_room_mcp_publication_get": nisb_room_mcp_publication_get,
    "nisb_room_mcp_grant_list": nisb_room_mcp_grant_list,
    "nisb_room_mcp_grant_revoke": nisb_room_mcp_grant_revoke,

    "nisb_readopt_get_default_preset": nisb_readopt_get_default_preset,
    "nisb_readopt_set_default_preset": nisb_readopt_set_default_preset,
    "nisb_readopt_clear_default_preset": nisb_readopt_clear_default_preset,
    "nisb_readopt_get_custom_presets": nisb_readopt_get_custom_presets,
    "nisb_readopt_save_custom_preset": nisb_readopt_save_custom_preset,
    "nisb_readopt_delete_custom_preset": nisb_readopt_delete_custom_preset,

    "nisb_bookmark_list_all": nisb_bookmark_list_all,
    "nisb_annotation_list_all": nisb_annotation_list_all,
    "nisb_llm_call": nisb_llm_call,
}


def _count_tools(prefix: str) -> int:
    """Count registered tools by name prefix for the startup banner."""
    try:
        return sum(1 for name in TOOLS.keys() if str(name).startswith(prefix))
    except Exception:
        return 0


_SCHEMA_PATCHES: Dict[str, Dict[str, Any]] = {
    "nisb_timeline_compact_activity_log": {
        "name": "nisb_timeline_compact_activity_log",
        "description": "Compact timeline activities.jsonl by deduplicating resources, filtering tombstones or missing files, and rewriting the log atomically.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "days": {
                    "type": "integer",
                    "description": "Keep only the latest N days. Default: 3650.",
                }
            },
            "required": [],
        },
    },
    "nisb_util_translate_chunks": {
        "name": "nisb_util_translate_chunks",
        "description": "Translate long text faithfully by splitting it into chunks and merging the translated result.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "text": {
                    "type": "string",
                    "description": "Text to translate.",
                },
                "target_language": {
                    "type": "string",
                    "description": "Target language. Default: zh-CN.",
                },
                "backend": {
                    "type": "string",
                    "description": "Model alias, such as mini, gpt-4o-mini, gpt-4o, or o1-mini.",
                },
                "chunk_chars": {
                    "type": "integer",
                    "description": "Maximum characters per chunk. Default: 900.",
                },
                "max_chars": {
                    "type": "integer",
                    "description": "Maximum input characters. Default: 12000.",
                },
            },
            "required": ["text"],
        },
    },
}


_EXTERNAL_MCP_SCHEMA_PATCHES: Dict[str, Dict[str, Any]] = {
    "nisb_room_mcp_external_provider_list": {
        "name": "nisb_room_mcp_external_provider_list",
        "description": "List the room provider available through a room-scoped external MCP publish token.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "debug": {
                    "type": "boolean",
                    "description": "Include diagnostics when available.",
                }
            },
            "required": [],
        },
    },
    "nisb_room_mcp_external_provider_call": {
        "name": "nisb_room_mcp_external_provider_call",
        "description": "Ask the room provider exposed by a room-scoped external MCP publish token.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "question": {
                    "type": "string",
                    "description": "Question to ask the published room.",
                },
                "provider_id": {
                    "type": "string",
                    "description": "Optional provider id. With an external publish token, it must match the scoped provider.",
                },
            },
            "required": ["question"],
        },
    },
    "nisb_room_mcp_external_publish_get": {
        "name": "nisb_room_mcp_external_publish_get",
        "description": "Get owner-facing external MCP publish status for a room.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "room_id": {
                    "type": "string",
                    "description": "Source room id.",
                }
            },
            "required": ["room_id"],
        },
    },
    "nisb_room_mcp_external_publish_enable": {
        "name": "nisb_room_mcp_external_publish_enable",
        "description": "Enable room-scoped external MCP publish and return the plaintext token once.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "room_id": {
                    "type": "string",
                    "description": "Source room id.",
                },
                "expires_in_days": {
                    "type": "integer",
                    "description": "Optional validity period in days.",
                },
                "max_calls": {
                    "type": "integer",
                    "description": "Optional maximum total calls.",
                },
                "daily_call_limit": {
                    "type": "integer",
                    "description": "Optional daily call limit.",
                },
                "client_label": {
                    "type": "string",
                    "description": "Optional client label.",
                },
                "endpoint_url": {
                    "type": "string",
                    "description": "External MCP endpoint URL.",
                },
            },
            "required": ["room_id"],
        },
    },
    "nisb_room_mcp_external_publish_revoke": {
        "name": "nisb_room_mcp_external_publish_revoke",
        "description": "Revoke the current external MCP publish token for a room.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "room_id": {
                    "type": "string",
                    "description": "Source room id.",
                }
            },
            "required": ["room_id"],
        },
    },
    "nisb_room_mcp_external_publish_regenerate": {
        "name": "nisb_room_mcp_external_publish_regenerate",
        "description": "Regenerate the external MCP publish token and return the new plaintext token once.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "room_id": {
                    "type": "string",
                    "description": "Source room id.",
                },
                "expires_in_days": {
                    "type": "integer",
                    "description": "Optional validity period in days.",
                },
                "max_calls": {
                    "type": "integer",
                    "description": "Optional maximum total calls.",
                },
                "daily_call_limit": {
                    "type": "integer",
                    "description": "Optional daily call limit.",
                },
                "client_label": {
                    "type": "string",
                    "description": "Optional client label.",
                },
                "endpoint_url": {
                    "type": "string",
                    "description": "External MCP endpoint URL.",
                },
            },
            "required": ["room_id"],
        },
    },
}

_SCHEMA_PATCHES.update(_EXTERNAL_MCP_SCHEMA_PATCHES)


EXTERNAL_MCP_PUBLIC_TOOL_NAMES = {
    "nisb_room_mcp_external_provider_list",
    "nisb_room_mcp_external_provider_call",
}

EXTERNAL_MCP_PUBLIC_ALIAS_TO_CANONICAL = {
    "room_provider_list": "nisb_room_mcp_external_provider_list",
    "room_provider_call": "nisb_room_mcp_external_provider_call",
}

EXTERNAL_MCP_PUBLIC_CANONICAL_TO_ALIAS = {
    canonical: alias
    for alias, canonical in EXTERNAL_MCP_PUBLIC_ALIAS_TO_CANONICAL.items()
}

EXTERNAL_MCP_CLIENT_TOOL_ALIASES = {}

for alias, canonical in EXTERNAL_MCP_PUBLIC_ALIAS_TO_CANONICAL.items():
    EXTERNAL_MCP_CLIENT_TOOL_ALIASES[alias] = canonical
    EXTERNAL_MCP_CLIENT_TOOL_ALIASES[f"{alias}_mcp_nisb"] = canonical
    EXTERNAL_MCP_CLIENT_TOOL_ALIASES[f"{alias}_mcp_nisb_room"] = canonical

for canonical in EXTERNAL_MCP_PUBLIC_TOOL_NAMES:
    EXTERNAL_MCP_CLIENT_TOOL_ALIASES[canonical] = canonical
    EXTERNAL_MCP_CLIENT_TOOL_ALIASES[f"{canonical}_mcp_nisb"] = canonical
    EXTERNAL_MCP_CLIENT_TOOL_ALIASES[f"{canonical}_mcp_nisb_room"] = canonical


def _normalize_external_mcp_tool_name(tool_name: Any) -> tuple[str, bool]:
    """Normalize external MCP client-facing tool names to canonical NISB tool names.

    Returns:
        (canonical_tool_name, external_alias_used)
    """
    name = str(tool_name or "").strip()
    mapped = EXTERNAL_MCP_CLIENT_TOOL_ALIASES.get(name)
    if mapped:
        if mapped != name:
            print(f"[INFO] External MCP tool alias normalized: {name} -> {mapped}")
            return mapped, True
        return mapped, False

    return name, False


def _apply_schema_patches(data: dict) -> tuple[dict, bool]:
    """Merge local schema patches into schema.json simplified/full sections."""
    changed = False
    if not isinstance(data, dict):
        return data, False

    simplified = data.get("simplified")
    full = data.get("full")

    if not isinstance(simplified, list) or not isinstance(full, dict):
        return data, False

    simplified_index = {}
    for i, item in enumerate(simplified):
        name = (item or {}).get("name")
        if name:
            simplified_index[name] = i

    for name, tool in _SCHEMA_PATCHES.items():
        if name not in full:
            full[name] = tool
            changed = True
        else:
            if tool.get("description") and full[name].get("description") != tool.get("description"):
                full[name]["description"] = tool.get("description")
                changed = True
            if "inputSchema" not in full[name] and tool.get("inputSchema"):
                full[name]["inputSchema"] = tool.get("inputSchema")
                changed = True

        simp = {
            "name": name,
            "description": tool.get("description", name),
            "inputSchema": {
                "type": "object",
                "required": [],
                "properties": {},
            },
        }

        schema = tool.get("inputSchema") or {}
        required = schema.get("required")
        if isinstance(required, list):
            simp["inputSchema"]["required"] = required

        props = schema.get("properties") or {}
        for k, v in props.items():
            simp["inputSchema"]["properties"][k] = {
                "type": (v or {}).get("type", "string"),
                "description": (v or {}).get("description", ""),
            }

        if name not in simplified_index:
            simplified.append(simp)
            changed = True
        else:
            idx = simplified_index[name]
            cur = simplified[idx] if idx < len(simplified) else None
            if isinstance(cur, dict):
                if cur.get("description") != simp.get("description"):
                    cur["description"] = simp.get("description")
                    changed = True

                if "inputSchema" not in cur or not isinstance(cur.get("inputSchema"), dict):
                    cur["inputSchema"] = simp.get("inputSchema")
                    changed = True
                    continue

                cur_schema = cur["inputSchema"]
                if "required" not in cur_schema and simp["inputSchema"].get("required") is not None:
                    cur_schema["required"] = simp["inputSchema"].get("required", [])
                    changed = True

                cur_props = cur_schema.get("properties")
                if not isinstance(cur_props, dict):
                    cur_props = {}
                    cur_schema["properties"] = cur_props
                    changed = True

                for pk, pv in (simp.get("inputSchema") or {}).get("properties", {}).items():
                    if pk not in cur_props:
                        cur_props[pk] = pv
                        changed = True

    data["simplified"] = simplified
    data["full"] = full
    return data, changed


def load_schemas():
    """Load schema.json and normalize supported schema layouts."""
    if not SCHEMA_FILE.exists():
        print(f"[ERROR] schema.json not found: {SCHEMA_FILE}")
        return {"simplified": [], "full": {}}

    try:
        with open(SCHEMA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)

        if isinstance(data, list):
            print("[WARN] Detected list-style schema.json. Converting to {simplified, full}.")
            converted = {"simplified": [], "full": {}}

            for item in data:
                if not isinstance(item, dict):
                    continue

                if "simplified" in item and "full" in item:
                    converted["simplified"].extend(item.get("simplified", []))
                    converted["full"].update(item.get("full", {}))
                elif "name" in item:
                    tool_name = item.get("name", "")
                    tool = {
                        "name": tool_name,
                        "description": item.get("description", tool_name),
                        "inputSchema": item.get("inputSchema", {"type": "object", "properties": {}}),
                    }

                    simplified = {
                        "name": tool_name,
                        "description": item.get("description", tool_name),
                        "inputSchema": {
                            "type": "object",
                            "required": item.get("inputSchema", {}).get("required", []),
                            "properties": {},
                        },
                    }

                    props = item.get("inputSchema", {}).get("properties", {})
                    for key in item.get("inputSchema", {}).get("required", []):
                        if key in props:
                            simplified["inputSchema"]["properties"][key] = {
                                "type": props[key].get("type", "string"),
                                "description": props[key].get("description", ""),
                            }

                    converted["simplified"].append(simplified)
                    converted["full"][tool_name] = tool

            with open(SCHEMA_FILE, "w", encoding="utf-8") as f:
                json.dump(converted, f, ensure_ascii=False, indent=2)

            data = converted

        elif isinstance(data, dict):
            pass
        else:
            print(f"[ERROR] Unsupported schema.json format: {type(data)}")
            return {"simplified": [], "full": {}}

        if not isinstance(data.get("simplified"), list):
            print("[ERROR] schema.json is missing simplified list.")
            return {"simplified": [], "full": {}}

        if not isinstance(data.get("full"), dict):
            print("[ERROR] schema.json is missing full map.")
            return {"simplified": [], "full": {}}

        data, patched = _apply_schema_patches(data)
        if patched:
            try:
                with open(SCHEMA_FILE, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                print("[OK] schema.json updated with local schema patches.")
            except Exception as e:
                print(f"[WARN] Failed to write schema.json patches. tools/call still works: {e}")

        print("[OK] schema.json loaded.")
        print(f"     simplified tools: {len(data.get('simplified', []))}")
        print(f"     full schemas: {len(data.get('full', {}))}")

        return data

    except json.JSONDecodeError as e:
        print(f"[ERROR] Failed to load schema.json: invalid JSON - {e}")
        return {"simplified": [], "full": {}}
    except KeyError as e:
        print(f"[ERROR] Failed to load schema.json: missing required key - {e}")
        return {"simplified": [], "full": {}}
    except Exception as e:
        print(f"[ERROR] Failed to load schema.json: {e}")
        import traceback
        traceback.print_exc()
        return {"simplified": [], "full": {}}


SCHEMAS = load_schemas()
TOOLS_LIST_SIMPLIFIED = SCHEMAS.get("simplified", [])
SCHEMA_MAP = SCHEMAS.get("full", {})


def _schema_simplified_for_tool(name: str) -> dict:
    """Build a simplified schema entry for tools/list."""
    full = SCHEMA_MAP.get(name)
    if isinstance(full, dict):
        schema = full.get("inputSchema") or {"type": "object", "properties": {}}
        props = schema.get("properties") if isinstance(schema, dict) else {}
        required = schema.get("required") if isinstance(schema, dict) else []
        return {
            "name": name,
            "description": full.get("description", name),
            "inputSchema": {
                "type": "object",
                "required": required if isinstance(required, list) else [],
                "properties": props if isinstance(props, dict) else {},
            },
        }

    patch = _SCHEMA_PATCHES.get(name)
    if isinstance(patch, dict):
        schema = patch.get("inputSchema", {"type": "object", "properties": {}})
        if not isinstance(schema, dict):
            schema = {"type": "object", "properties": {}}
        schema.setdefault("type", "object")
        schema.setdefault("properties", {})
        schema.setdefault("required", [])
        return {
            "name": name,
            "description": patch.get("description", name),
            "inputSchema": schema,
        }

    return {
        "name": name,
        "description": name,
        "inputSchema": {"type": "object", "required": [], "properties": {}},
    }


def _external_mcp_tools_list() -> list:
    """Return only the public external MCP tools allowed for Bearer-token clients."""
    tools = []
    seen = set()

    for item in TOOLS_LIST_SIMPLIFIED:
        if not isinstance(item, dict):
            continue
        name = item.get("name")
        if name in EXTERNAL_MCP_PUBLIC_TOOL_NAMES:
            alias = EXTERNAL_MCP_PUBLIC_CANONICAL_TO_ALIAS.get(name, name)
            aliased_item = dict(item)
            aliased_item["name"] = alias
            tools.append(aliased_item)
            seen.add(alias)

    for canonical in sorted(EXTERNAL_MCP_PUBLIC_TOOL_NAMES):
        alias = EXTERNAL_MCP_PUBLIC_CANONICAL_TO_ALIAS.get(canonical, canonical)
        if alias not in seen:
            item = _schema_simplified_for_tool(canonical)
            item = dict(item)
            item["name"] = alias
            tools.append(item)

    return tools


def _has_bearer_authorization(headers: Any) -> bool:
    """Return True when the request uses Authorization: Bearer."""
    try:
        value = headers.get("Authorization")
    except Exception:
        value = ""
    value = str(value or "").strip()
    return value.lower().startswith("bearer ")


def _resolve_external_publish_request(headers: Any, path: str) -> dict:
    """Resolve an external MCP publish token into a sanitized room scope."""
    try:
        from tools.rooms_shared.room_mcp_external_grant_resolver import (
            resolve_external_mcp_publish_scope,
        )

        return resolve_external_mcp_publish_scope(
            headers,
            path=path,
            base_path=BASE_PATH,
        )
    except Exception as ex:
        return {
            "ok": False,
            "external": True,
            "error": "external_publish_token_invalid",
            "message": f"external publish resolver failed: {type(ex).__name__}: {str(ex)[:240]}",
        }


class NISBHandler(http.server.BaseHTTPRequestHandler):
    """HTTP JSON-RPC handler for the NISB MCP server."""

    def _send_json(self, obj: dict, code: int = 200):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-cache, no-store, no-transform")
        self.send_header("Mcp-Session-Id", SESSION_ID)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.end_headers()
        self.wfile.write(body)

    def _send_plain_ok(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(b"OK")

    def _jsonrpc_error(
        self,
        msg_id: Any,
        code: int,
        message: str,
        data: Optional[dict] = None,
    ):
        err = {"code": code, "message": message}
        if data:
            err["data"] = data
        return self._send_json({"jsonrpc": "2.0", "id": msg_id, "error": err})

    def _tool_error_result(self, msg_id: Any, message: str, *, error: str = ""):
        text = message or error or "Tool call failed"
        return self._send_json(
            {
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {
                    "content": [{"type": "text", "text": text}],
                    "isError": True,
                },
            }
        )

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.end_headers()

    def do_GET(self):
        """Handle health checks and lazy schema expansion."""
        path = self.path

        if path == "/health/hebbian":
            return self._send_json(check_hebbian_health())

        if path.startswith("/tools/expand_schema/"):
            tool_name = path.replace("/tools/expand_schema/", "").strip()
            schema = SCHEMA_MAP.get(tool_name)
            if not schema:
                return self._send_json(
                    {
                        "error": {
                            "code": -32601,
                            "message": f"Tool not found: {tool_name}",
                        }
                    },
                    code=404,
                )
            return self._send_json({"tool": schema})

        return self._send_json(
            {
                "jsonrpc": "2.0",
                "error": {"code": -32601, "message": "GET not supported"},
            },
            code=405,
        )

    def do_POST(self):
        """Handle MCP JSON-RPC requests."""
        try:
            content_length = int(self.headers.get("Content-Length", 0))
            if content_length == 0:
                return self._send_plain_ok()

            body = self.rfile.read(content_length).decode("utf-8")
            if not body.strip():
                return self._send_plain_ok()

            req = json.loads(body)
        except json.JSONDecodeError as e:
            return self._send_json(
                {
                    "jsonrpc": "2.0",
                    "error": {"code": -32700, "message": f"Parse error: {str(e)}"},
                }
            )
        except Exception as e:
            return self._send_json(
                {
                    "jsonrpc": "2.0",
                    "error": {
                        "code": -32603,
                        "message": f"Internal error: {str(e)}",
                    },
                }
            )

        msg_id = req.get("id")
        method = req.get("method")
        params = req.get("params") or {}

        if method == "initialize":
            return self._send_json(
                {
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "result": {
                        "protocolVersion": params.get("protocolVersion", "2024-11-05"),
                        "capabilities": {"tools": {"lazyLoading": True}},
                        "serverInfo": {
                            "name": "nisb-mcp",
                            "version": "8.5.4-external-publish",
                        },
                    },
                }
            )

        if method == "notifications/initialized":
            return self._send_json(
                {
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "result": {"ack": True},
                }
            )

        if method == "ping":
            return self._send_json({"jsonrpc": "2.0", "id": msg_id, "result": {}})

        bearer_mode = _has_bearer_authorization(self.headers)

        if method == "tools/list":
            if bearer_mode:
                external_state = _resolve_external_publish_request(self.headers, self.path)
                if not external_state.get("ok"):
                    error = external_state.get("error") or "external_publish_token_invalid"
                    message = external_state.get("message") or error
                    return self._jsonrpc_error(
                        msg_id,
                        -32001,
                        message,
                        {"error": error},
                    )

                return self._send_json(
                    {
                        "jsonrpc": "2.0",
                        "id": msg_id,
                        "result": {"tools": _external_mcp_tools_list()},
                    }
                )

            return self._send_json(
                {
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "result": {"tools": TOOLS_LIST_SIMPLIFIED},
                }
            )

        if method == "tools/call":
            raw_tool_name = params.get("name")
            tool_name, external_alias_used = _normalize_external_mcp_tool_name(raw_tool_name)

            tool_args = params.get("arguments") or {}
            if not isinstance(tool_args, dict):
                tool_args = {}

            print(
                f"[INFO] tools/call raw_tool={raw_tool_name} "
                f"tool={tool_name} external_alias={external_alias_used} "
                f"bearer_mode={bearer_mode} path={self.path}"
            )

            if external_alias_used and not bearer_mode:
                return self._tool_error_result(
                    msg_id,
                    "external MCP alias call requires Authorization: Bearer token",
                    error="external_publish_bearer_missing",
                )

            external_scope = None
            if bearer_mode:
                external_state = _resolve_external_publish_request(self.headers, self.path)
                if not external_state.get("ok"):
                    error = external_state.get("error") or "external_publish_token_invalid"
                    message = external_state.get("message") or error
                    return self._tool_error_result(msg_id, message, error=error)

                external_scope = external_state.get("scope")

                if tool_name not in EXTERNAL_MCP_PUBLIC_TOOL_NAMES:
                    return self._tool_error_result(
                        msg_id,
                        "external publish token can only call room external provider tools",
                        error="external_publish_tool_not_allowed",
                    )

            tool_args["_mcp_mode"] = True
            tool_args["_base_path"] = BASE_PATH

            if external_scope:
                tool_args["_external_mcp_publish_scope"] = external_scope
                tool_args["external_mcp_publish_scope"] = external_scope
                tool_args["_external_mcp_publish_required"] = True
                tool_args["result_view"] = "final_result_only"
                tool_args["source_observation_allowed"] = False
                tool_args["owner_private_scope_exposed"] = False

            print(f"[INFO] Tool call: {tool_name} (MCP mode)")
            print(f"[INFO] Base path: {BASE_PATH}")
            if external_scope:
                print("[INFO] External MCP publish scope: enabled")

            tool_func = TOOLS.get(tool_name)
            if not tool_func:
                error_msg = f"Tool not found: {tool_name}"
                print(f"[ERROR] {error_msg}")
                return self._tool_error_result(msg_id, error_msg, error="tool_not_found")

            try:
                result = tool_func(tool_args)
                print(f"[DEBUG] Tool completed: {tool_name}")

                if isinstance(result, dict):
                    text = result.get("message") or result.get("text") or str(result)
                    is_error = not bool(result.get("ok", True)) if "ok" in result else False
                else:
                    text = str(result)
                    is_error = False

                return self._send_json(
                    {
                        "jsonrpc": "2.0",
                        "id": msg_id,
                        "result": {
                            "content": [{"type": "text", "text": text}],
                            "isError": is_error,
                        },
                    }
                )
            except Exception as e:
                import traceback

                error_detail = traceback.format_exc()
                error_msg = f"Error: {tool_name}: {str(e)}\n{error_detail}"
                print(f"[ERROR] Tool execution failed: {error_msg}")
                return self._tool_error_result(
                    msg_id,
                    error_msg,
                    error="tool_execution_failed",
                )

        return self._send_json(
            {
                "jsonrpc": "2.0",
                "id": msg_id,
                "error": {
                    "code": -32601,
                    "message": f"Method not found: {method}",
                },
            }
        )

    def log_message(self, format, *args):
        print(
            f"[{datetime.now().isoformat()}] {self.address_string()} - {format % args}"
        )


def check_hebbian_health():
    """
    Run a lightweight Hebbian pipeline health check.

    Returns:
        {"status": "ok" | "degraded" | "error", "message": "...", "details": {...}}
    """
    import os

    try:
        from core.concept_extractor import get_concept_extractor
        from core.hebbian_pipeline import process_text_event

        test_base_path = "/tmp/health_check_hebbian"
        os.makedirs(test_base_path, exist_ok=True)
        os.makedirs(
            f"{test_base_path}/storage/entities/concepts/by_id",
            exist_ok=True,
        )
        os.makedirs(
            f"{test_base_path}/storage/entities/synapses/by_type",
            exist_ok=True,
        )
        os.makedirs(f"{test_base_path}/logs", exist_ok=True)

        extractor = get_concept_extractor(
            test_base_path,
            language="auto",
            backend="llm_gpt4o_mini",
        )

        test_text = "Health check text: Hebbian learning and neural plasticity support learning."
        concepts = extractor.extract(test_text, top_k=3)

        if not concepts:
            return {
                "status": "degraded",
                "message": "LLM concept extraction returned no concepts. Fallback may still be available.",
                "details": {"llm_working": False, "fallback_available": True},
            }

        result = process_text_event(
            base_path=test_base_path,
            source_type="health_check",
            source_id="test_001",
            text=test_text,
            concept_backend="llm_gpt4o_mini",
            top_k=3,
        )

        return {
            "status": "ok",
            "message": f"Hebbian pipeline is healthy. Extracted {len(concepts)} concepts.",
            "details": {
                "llm_working": True,
                "concepts_extracted": len(concepts),
                "sample_concepts": concepts[:3],
                "pipeline_result": {
                    "concepts": result.get("concepts", 0) if result else 0,
                    "pairs": result.get("pairs", 0) if result else 0,
                },
            },
        }

    except Exception as e:
        import traceback

        return {
            "status": "error",
            "message": f"Hebbian pipeline error: {str(e)}",
            "details": {
                "error_type": type(e).__name__,
                "traceback": traceback.format_exc(),
            },
        }


def main():
    PORT = int(os.environ.get("NISB_MCP_PORT", "8005"))

    stats = {
        "timeline": _count_tools("nisb_timeline_"),
        "chat": _count_tools("nisb_chat_"),
        "doc": (
            _count_tools("nisb_doc_")
            + _count_tools("nisb_library_doc_")
            + _count_tools("nisb_library_continuous_")
            + _count_tools("nisb_library_translate_")
        ),
        "filesystem": (
            _count_tools("nisb_file_")
            + _count_tools("nisb_dir_")
            + _count_tools("nisb_fs_")
            + _count_tools("nisb_favorites_")
            + _count_tools("nisb_note_")
            + _count_tools("nisb_batch_notes_")
        ),
        "library": _count_tools("nisb_library_"),
        "search": _count_tools("nisb_search_"),
        "entities": (
            _count_tools("nisb_concept_")
            + _count_tools("nisb_author_")
            + _count_tools("nisb_book_")
            + _count_tools("nisb_topic_")
            + _count_tools("nisb_entity_")
        ),
        "rooms": _count_tools("nisb_room_"),
    }

    print(
        f"""
╔════════════════════════════════════════════════════════════════╗
║  NISB MCP Server                                              ║
║  Full MCP mode + room-scoped external MCP publish             ║
╚════════════════════════════════════════════════════════════════╝

Port: {PORT}
Base Path: {BASE_PATH}
Schema File: {SCHEMA_FILE}
Registered Tools: {len(TOOLS)}

Tool groups:
  timeline:   {stats["timeline"]}
  chat:       {stats["chat"]}
  doc:        {stats["doc"]}
  filesystem: {stats["filesystem"]}
  library:    {stats["library"]}
  search:     {stats["search"]}
  entities:   {stats["entities"]}
  rooms:      {stats["rooms"]}

Modes:
  - Default MCP mode: full registered tool list.
  - External publish mode: Authorization Bearer token restricts tools/list and tools/call to one room-scoped provider.

External publish guarantees:
  - No raw token logging.
  - Bearer token is resolved into a sanitized scope.
  - Third-party clients only see external provider list/call tools.
  - Provider calls are final-result-only at the external boundary.

Starting server...
"""
    )

    os.makedirs(BASE_PATH, exist_ok=True)
    for dir_path in [
        f"{BASE_PATH}/storage/raw/daily",
        f"{BASE_PATH}/storage/raw/quick_notes",
        f"{BASE_PATH}/storage/raw/highlights",
        f"{BASE_PATH}/storage/kb_bookmarks",
        f"{BASE_PATH}/storage/relations",
        f"{BASE_PATH}/storage/entities/synapses",
        f"{BASE_PATH}/storage/config",
        f"{BASE_PATH}/storage/temp",
        f"{BASE_PATH}/cache",
        f"{BASE_PATH}/indexes/primary",
        f"{BASE_PATH}/storage/cases/by_date",
        f"{BASE_PATH}/storage/cases/index",
        f"{BASE_PATH}/storage/annotations/by_date",
        f"{BASE_PATH}/storage/annotations/index",
    ]:
        os.makedirs(dir_path, exist_ok=True)

    with socketserver.TCPServer(("0.0.0.0", PORT), NISBHandler) as httpd:
        print(f"[OK] Server running on http://0.0.0.0:{PORT}")
        print("[OK] Default MCP mode is available.")
        print("[OK] Room-scoped external MCP publish gate is available.")
        print("[OK] Lazy schema loading is available.")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n[STOP] Server stopped.")


if __name__ == "__main__":
    main()

