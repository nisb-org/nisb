#!/usr/bin/env python3

import json
import sqlite3
import time
from pathlib import Path
from typing import Any, Dict, List, Tuple

from .common import build_index_excerpt, now_ts
from .index_db import meta_get_float, meta_set
from .index_shared import (
    CHAT_PREVIEW_EXCERPT_CHARS,
    chat_preview_fast,
    build_content_blocks,
    derive_title_aliases,
    load_chat_turns,
    safe_rel,
)
from .index_store import delete_stale, load_existing_map, upsert_entries
from .index_sync_state import mark_synced


INDEX_SYNC_CHAT_FORMAT_VERSION = 2.0

DEFAULT_CHAT_TITLE_ALIASES = (
    "新对话",
    "未命名对话",
    "未命名聊天",
    "new chat",
    "untitled",
)
DEFAULT_CHAT_TITLE_ALIASES_SET = {alias.lower() for alias in DEFAULT_CHAT_TITLE_ALIASES}

CHAT_REFRESH_MIN_INTERVAL_SECONDS = 20.0
CHAT_REFRESH_LAST_TS_KEY = "chat_refresh:last_ts"
CHAT_REFRESH_LAST_INDEXED_KEY = "chat_refresh:last_indexed"
CHAT_REFRESH_LAST_DELETED_KEY = "chat_refresh:last_deleted"
CHAT_REFRESH_LAST_TOTAL_KEY = "chat_refresh:last_total"

EXPLICIT_CHAT_TERMS = {
    "chat",
    "conversation",
    "assistant",
    "user",
    "system",
    "prompt",
    "prompts",
    "turn",
    "turns",
    "message",
    "messages",
    "dialog",
    "dialogue",
    "对话",
    "聊天",
    "会话",
    "提示词",
    "消息",
    "提问",
    "回答",
}
STRONG_CHAT_INTENT_MIN_TOKENS = 4
STRONG_CHAT_INTENT_MIN_CHARS = 12


def _unique_keep_order(values: List[str]) -> List[str]:
    out: List[str] = []
    seen = set()
    for value in values:
        text = str(value or "").strip()
        if not text:
            continue
        key = text.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(text)
    return out


def _format_version_key(module: str) -> str:
    return f"index_sync_chat_format:{module}"


def _format_version_stale(conn: sqlite3.Connection, module: str) -> bool:
    try:
        current = meta_get_float(conn, _format_version_key(module))
    except Exception:
        current = None
    return float(current or 0.0) < float(INDEX_SYNC_CHAT_FORMAT_VERSION)


def _mark_format_version(conn: sqlite3.Connection, module: str) -> None:
    meta_set(conn, _format_version_key(module), float(INDEX_SYNC_CHAT_FORMAT_VERSION))


def _delete_module_entries(conn: sqlite3.Connection, module: str) -> int:
    try:
        cur = conn.execute(
            "DELETE FROM search_entries WHERE module = ?",
            (module,),
        )
        return int(cur.rowcount or 0)
    except Exception:
        return 0


def _safe_file_sig(path: Path) -> Tuple[int, int]:
    if not path.exists():
        return 0, 0
    try:
        st = path.stat()
        return int(st.st_mtime_ns), int(st.st_size)
    except Exception:
        return 0, 0


def _combine_sig(paths: List[Path]) -> Tuple[int, int]:
    max_mtime_ns = 0
    total_size = 0
    for path in paths:
        mtime_ns, size = _safe_file_sig(path)
        if mtime_ns > max_mtime_ns:
            max_mtime_ns = mtime_ns
        total_size += size
    return max_mtime_ns, total_size


def _read_level1_titles(level1_file: Path) -> List[str]:
    titles: List[str] = []
    if not level1_file.exists():
        return titles

    try:
        with open(level1_file, "r", encoding="utf-8") as f:
            for line in f:
                text = str(line or "").strip()
                if not text:
                    continue
                try:
                    obj = json.loads(text)
                except Exception:
                    continue
                title = str(obj.get("title", "") or "").strip()
                if title:
                    titles.append(title)
    except Exception:
        return []

    return _unique_keep_order(titles)


def _is_generic_title(title: str, conv_dir_name: str) -> bool:
    text = str(title or "").strip()
    if not text:
        return True

    lowered = text.lower()
    conv_name = str(conv_dir_name or "").strip().lower()

    if lowered in DEFAULT_CHAT_TITLE_ALIASES_SET:
        return True
    if lowered == conv_name:
        return True
    if lowered.startswith("conv_"):
        return True
    return False


def _build_title_candidates(conv_dir: Path, conv_meta: Dict[str, Any]) -> Tuple[str, List[str]]:
    conv_dir_name = conv_dir.name
    conv_title = str(conv_meta.get("title", "") or "").strip()

    level1_file = conv_dir / "turns_index_level1.jsonl"
    level1_titles = _read_level1_titles(level1_file)

    derived_aliases = derive_title_aliases(conv_dir_name)

    meaningful: List[str] = []
    generic: List[str] = []

    def add_title(value: str) -> None:
        title = str(value or "").strip()
        if not title:
            return
        if _is_generic_title(title, conv_dir_name):
            generic.append(title)
        else:
            meaningful.append(title)

    add_title(conv_title)
    for title in level1_titles:
        add_title(title)
    for alias in derived_aliases:
        add_title(alias)

    ordered = _unique_keep_order(meaningful + generic)
    if not ordered:
        ordered = ["新对话"]

    primary = ordered[0]
    aliases = [t for t in ordered[1:] if t.strip() and t.strip() != primary.strip()]
    return primary, aliases


def _turn_block_params(content: str) -> Tuple[int, int]:
    text_len = len(str(content or "").strip())
    if text_len <= 1200:
        return 420, 3
    if text_len <= 4000:
        return 360, 6
    if text_len <= 12000:
        return 320, 10
    return 320, 14


def _iter_conversation_dirs(conversations_root: Path):
    if not conversations_root.exists() or not conversations_root.is_dir():
        return

    for year_dir in conversations_root.iterdir():
        if not year_dir.is_dir():
            continue
        for month_dir in year_dir.iterdir():
            if not month_dir.is_dir():
                continue
            for conv_dir in month_dir.iterdir():
                if not conv_dir.is_dir() or not conv_dir.name.startswith("conv_"):
                    continue
                yield conv_dir


def get_chat_refresh_snapshot(conn: sqlite3.Connection) -> Dict[str, Any]:
    try:
        last_ts = float(meta_get_float(conn, CHAT_REFRESH_LAST_TS_KEY) or 0.0)
    except Exception:
        last_ts = 0.0

    now = float(now_ts())
    age_seconds = max(0.0, now - last_ts) if last_ts > 0 else None

    try:
        last_indexed = int(meta_get_float(conn, CHAT_REFRESH_LAST_INDEXED_KEY) or 0)
    except Exception:
        last_indexed = 0

    try:
        last_deleted = int(meta_get_float(conn, CHAT_REFRESH_LAST_DELETED_KEY) or 0)
    except Exception:
        last_deleted = 0

    try:
        last_total = int(meta_get_float(conn, CHAT_REFRESH_LAST_TOTAL_KEY) or 0)
    except Exception:
        last_total = 0

    return {
        "last_ts": last_ts,
        "age_seconds": age_seconds,
        "last_indexed": last_indexed,
        "last_deleted": last_deleted,
        "last_total": last_total,
    }


def chat_refresh_due(
    conn: sqlite3.Connection,
    min_interval_seconds: float = CHAT_REFRESH_MIN_INTERVAL_SECONDS,
) -> Tuple[bool, Dict[str, Any]]:
    snapshot = get_chat_refresh_snapshot(conn)
    age_seconds = snapshot.get("age_seconds")

    if age_seconds is None:
        return True, {
            **snapshot,
            "due": True,
            "reason": "never_refreshed",
            "min_interval_seconds": float(min_interval_seconds),
        }

    due = float(age_seconds) >= float(min_interval_seconds)
    return bool(due), {
        **snapshot,
        "due": bool(due),
        "reason": "interval_due" if due else "recent_chat_refresh",
        "min_interval_seconds": float(min_interval_seconds),
    }


def _has_explicit_chat_term(raw_query: str, query_tokens: List[str]) -> bool:
    lowered_query = str(raw_query or "").lower()
    normalized_tokens = [
        str(token or "").strip().lower()
        for token in list(query_tokens or [])
        if str(token or "").strip()
    ]

    for token in normalized_tokens:
        if token in EXPLICIT_CHAT_TERMS:
            return True

    for term in EXPLICIT_CHAT_TERMS:
        if term and term in lowered_query:
            return True

    return False


def decide_chat_refresh(
    conn: sqlite3.Connection,
    *,
    effective_raw_modules: List[str],
    raw_query: str,
    query_tokens: List[str],
    query_guard: Dict[str, Any],
    filename_mode: bool,
    path_mode: bool,
    min_interval_seconds: float = CHAT_REFRESH_MIN_INTERVAL_SECONDS,
) -> Dict[str, Any]:
    query_class = str(query_guard.get("query_class") or "")
    natural_language = bool(query_guard.get("natural_language") or False)
    oversized = bool(query_guard.get("oversized") or False)
    symbol_heavy = bool(query_guard.get("symbol_heavy") or False)
    token_count_used = int(query_guard.get("token_count_used") or 0)
    query_chars_used = int(query_guard.get("query_chars_used") or 0)

    base = {
        "should_refresh": False,
        "reason": "",
        "chat_intent": False,
        "chat_intent_reason": "",
        "query_class": query_class,
        "natural_language": natural_language,
        "token_count_used": token_count_used,
        "query_chars_used": query_chars_used,
        "min_interval_seconds": float(min_interval_seconds),
    }

    if "chat" not in list(effective_raw_modules or []):
        return {
            **base,
            "reason": "no_chat_module_selected",
        }

    if filename_mode or path_mode:
        return {
            **base,
            "reason": "filename_or_path_query",
        }

    if oversized or symbol_heavy:
        return {
            **base,
            "reason": "guarded_query_shape",
        }

    explicit_chat_intent = _has_explicit_chat_term(raw_query, list(query_tokens or []))
    strong_nl_chat_intent = (
        natural_language
        and token_count_used >= STRONG_CHAT_INTENT_MIN_TOKENS
        and query_chars_used >= STRONG_CHAT_INTENT_MIN_CHARS
    )

    if explicit_chat_intent:
        chat_intent = True
        chat_intent_reason = "explicit_chat_term"
    elif strong_nl_chat_intent:
        chat_intent = True
        chat_intent_reason = "natural_language_phrase"
    else:
        chat_intent = False
        chat_intent_reason = "low_chat_intent"

    due, due_info = chat_refresh_due(
        conn,
        min_interval_seconds=min_interval_seconds,
    )

    if not chat_intent:
        return {
            **base,
            "reason": "low_chat_intent",
            "chat_intent": False,
            "chat_intent_reason": chat_intent_reason,
            **due_info,
        }

    if not due:
        return {
            **base,
            "reason": "recent_chat_refresh",
            "chat_intent": True,
            "chat_intent_reason": chat_intent_reason,
            **due_info,
        }

    return {
        **base,
        "should_refresh": True,
        "reason": "chat_intent_due",
        "chat_intent": True,
        "chat_intent_reason": chat_intent_reason,
        **due_info,
    }


def sync_chat(conn: sqlite3.Connection, base_path: Path) -> Dict[str, int]:
    started = time.time()

    module = "chat"
    format_stale = _format_version_stale(conn, module)

    if format_stale:
        _delete_module_entries(conn, module)
        existing: Dict[str, Tuple[int, int]] = {}
    else:
        existing = load_existing_map(conn, module)

    current_keys = set()
    entries: List[Dict[str, Any]] = []

    conversations_root = base_path / "web_interactions" / "conversations"
    for conv_dir in _iter_conversation_dirs(conversations_root) or []:
        conv_file = conv_dir / "conversation.json"
        turns_file = conv_dir / "turns.jsonl"
        turns_level1_file = conv_dir / "turns_index_level1.jsonl"
        turns_level2_file = conv_dir / "turns_index_level2.jsonl"

        if not conv_file.exists():
            continue

        sig_paths = [
            conv_file,
            turns_file,
            turns_level1_file,
            turns_level2_file,
        ]
        mtime_ns, size = _combine_sig(sig_paths)
        if mtime_ns <= 0:
            continue

        try:
            with open(conv_file, "r", encoding="utf-8") as f:
                conv_meta = json.load(f)
        except Exception:
            continue

        conv_id = str(conv_meta.get("id", conv_dir.name))
        conv_created_at = str(conv_meta.get("created_at", "") or "")
        rel_path = safe_rel(conv_dir, base_path)
        preview = chat_preview_fast(conv_dir)
        preview = build_index_excerpt(preview, max_chars=CHAT_PREVIEW_EXCERPT_CHARS)

        primary_title, title_aliases = _build_title_candidates(conv_dir, conv_meta)

        meta_item_key = f"chat::{conv_id}"
        current_keys.add(meta_item_key)

        meta_turn_count = int(conv_meta.get("turn_count", 0) or 0)

        if existing.get(meta_item_key) != (mtime_ns, size):
            entries.append(
                {
                    "item_key": meta_item_key,
                    "module": module,
                    "source_kind": "chat_meta",
                    "group_key": conv_id,
                    "path": rel_path,
                    "filename": "",
                    "title": primary_title,
                    "library_id": "",
                    "library_name": "",
                    "doc_id": "",
                    "conv_id": conv_id,
                    "created_at": conv_created_at,
                    "turn_count": meta_turn_count,
                    "snippet": preview,
                    "priority_hint": 30,
                    "mtime_ns": mtime_ns,
                    "size": size,
                }
            )

        for idx, alias in enumerate(title_aliases, start=1):
            alias_item_key = f"chat_alias::{conv_id}::{idx}"
            current_keys.add(alias_item_key)

            if existing.get(alias_item_key) == (mtime_ns, size):
                continue

            entries.append(
                {
                    "item_key": alias_item_key,
                    "module": module,
                    "source_kind": "chat_meta",
                    "group_key": conv_id,
                    "path": rel_path,
                    "filename": "",
                    "title": alias,
                    "library_id": "",
                    "library_name": "",
                    "doc_id": "",
                    "conv_id": conv_id,
                    "created_at": conv_created_at,
                    "turn_count": meta_turn_count,
                    "snippet": preview,
                    "priority_hint": 28,
                    "mtime_ns": mtime_ns,
                    "size": size,
                }
            )

        if not turns_file.exists():
            continue

        turns = load_chat_turns(turns_file)
        effective_turn_count = max(meta_turn_count, len(turns))

        for turn in turns:
            sequence = int(turn.get("sequence", 0) or 0)
            content = str(turn.get("content", "") or "").strip()
            if not content:
                continue

            role = str(turn.get("turn_type", "") or "").strip()
            created_at = str(turn.get("timestamp", "") or conv_created_at)

            block_chars, max_blocks = _turn_block_params(content)
            blocks = build_content_blocks(
                content,
                block_chars=block_chars,
                max_blocks=max_blocks,
            )
            if not blocks:
                blocks = [build_index_excerpt(content, max_chars=block_chars)]

            base_priority = 18 if role == "user" else 16

            for block_idx, block in enumerate(blocks):
                if not block:
                    continue

                turn_item_key = f"chat_turn::{conv_id}::{sequence}::{block_idx}"
                current_keys.add(turn_item_key)

                if existing.get(turn_item_key) == (mtime_ns, size):
                    continue

                snippet = f"{role}: {block}" if role else block
                priority_hint = max(12, base_priority - min(block_idx, 4))

                entries.append(
                    {
                        "item_key": turn_item_key,
                        "module": module,
                        "source_kind": "chat_turn",
                        "group_key": conv_id,
                        "path": rel_path,
                        "filename": "",
                        "title": primary_title,
                        "library_id": "",
                        "library_name": "",
                        "doc_id": "",
                        "conv_id": conv_id,
                        "created_at": created_at,
                        "turn_count": effective_turn_count,
                        "snippet": snippet,
                        "priority_hint": priority_hint,
                        "mtime_ns": mtime_ns,
                        "size": size,
                    }
                )

    updated = int(upsert_entries(conn, entries) or 0)
    deleted = int(delete_stale(conn, module, current_keys, existing) or 0)
    total = len(current_keys)

    try:
        _mark_format_version(conn, module)
    except Exception:
        pass

    try:
        mark_synced(conn, module, total=total)
    except Exception:
        pass

    try:
        meta_set(conn, CHAT_REFRESH_LAST_TS_KEY, float(now_ts()))
        meta_set(conn, CHAT_REFRESH_LAST_INDEXED_KEY, int(updated))
        meta_set(conn, CHAT_REFRESH_LAST_DELETED_KEY, int(deleted))
        meta_set(conn, CHAT_REFRESH_LAST_TOTAL_KEY, int(total))
    except Exception:
        pass

    try:
        conn.commit()
    except Exception:
        pass

    elapsed_ms = int((time.time() - started) * 1000)
    return {
        "indexed": updated,
        "deleted": deleted,
        "total": total,
        "elapsed_ms": elapsed_ms,
    }


__all__ = [
    "CHAT_REFRESH_MIN_INTERVAL_SECONDS",
    "chat_refresh_due",
    "decide_chat_refresh",
    "get_chat_refresh_snapshot",
    "sync_chat",
]
