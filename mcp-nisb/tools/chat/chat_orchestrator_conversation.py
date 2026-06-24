#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import sys
import threading
from datetime import datetime
from typing import Any, Dict, Optional

from core.openai_utils import get_embedding
from .chat_conversation_store import (
    append_turn_record,
    find_conv_dir,
    load_conversation_meta,
    read_turn_records,
    save_conversation_meta,
)


def _async_hebbian(
    base_path: str,
    user_text: str,
    ai_text: str,
    concept_language: str,
    concept_backend: str,
) -> None:
    try:
        from tools.chat.hebbian import process_conversation_hebbian

        process_conversation_hebbian(
            base_path=base_path,
            user_content=user_text,
            ai_content=ai_text,
            concept_language=concept_language or "auto",
            concept_backend=concept_backend or "auto",
        )
        print("[INFO orchestrate] Hebbian triggered", file=sys.stderr)
    except Exception as e:
        print(f"[WARN orchestrate] Hebbian failed: {e}", file=sys.stderr)


def persist_cite_ground_turns(
    *,
    user_base: str,
    conv_id: str,
    request_id: str,
    effective_mode: str,
    base_user_content: str,
    answer: str,
    qa_model: str,
    citations: list,
    rss_evidence: list,
    market_evidence: list,
    qa: Dict[str, Any],
    tool_policy_snapshot: Dict[str, Any],
    agent_trace: Optional[Dict[str, Any]],
    concept_language: str,
    concept_backend: str,
) -> Dict[str, Any]:
    conv_dir = find_conv_dir(user_base, conv_id)
    if not conv_dir:
        return {
            "status": "error",
            "message": f"对话不存在: {conv_id}",
        }

    history = read_turn_records(conv_dir)
    now_iso = datetime.now().isoformat()

    user_turn = {
        "sequence": len(history) + 1,
        "turn_type": "user",
        "content": base_user_content,
        "timestamp": now_iso,
        "mode_used": effective_mode,
        "request_id": request_id,
    }
    try:
        user_turn["embedding"] = get_embedding(base_user_content)
    except Exception:
        pass
    append_turn_record(conv_dir, user_turn)

    evidence_result = {
        "citations": citations,
        "rss_evidence": rss_evidence,
        "market_evidence": market_evidence,
        "qa_meta": {
            "qa_id": qa.get("qa_id"),
            "thread_id": qa.get("thread_id"),
            "store_scope": qa.get("store_scope"),
            "evidence_scope": qa.get("evidence_scope"),
        },
    }

    ai_turn = {
        "sequence": len(history) + 2,
        "turn_type": "assistant",
        "content": answer,
        "timestamp": now_iso,
        "model": qa_model,
        "mode_used": effective_mode,
        "tool_policy_snapshot": tool_policy_snapshot,
        "citations": citations,
        "rss_evidence": rss_evidence,
        "market_evidence": market_evidence,
        "qa_meta": evidence_result["qa_meta"],
        "request_id": request_id,
        "evidence_query": base_user_content,
        "evidence_tools": ["nisb_qa_scope_ask"],
        "evidence_result": evidence_result,
    }

    if agent_trace is not None:
        ai_turn["agent_meta"] = {
            "enabled": True,
            "planner_model": agent_trace.get("planner_model"),
            "mode_used": agent_trace.get("mode_used"),
            "tool_count": len(agent_trace.get("tool_results") or []),
        }

    try:
        ai_turn["embedding"] = get_embedding(answer)
    except Exception:
        pass

    append_turn_record(conv_dir, ai_turn)

    meta = load_conversation_meta(conv_dir)
    meta["turn_count"] = len(history) + 2
    meta["last_updated"] = datetime.now().isoformat()
    save_conversation_meta(conv_dir, meta)

    t = threading.Thread(
        target=_async_hebbian,
        args=(user_base, base_user_content, answer, concept_language, concept_backend),
        daemon=True,
    )
    t.start()

    return {
        "status": "success",
        "evidence_result": evidence_result,
    }

