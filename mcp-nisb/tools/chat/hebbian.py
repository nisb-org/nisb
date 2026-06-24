#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Hebbian Learning Pipeline (Chat)

Release gate:
- Before NISB has a user-facing Hebbian product outlet, chat-side automatic
  Hebbian data generation is disabled by default.
- Existing implementation is kept for future restoration.
- To explicitly re-enable, set:
    NISB_HEBBIAN_ENABLED=1
  Accepted truthy values: 1 / true / yes / on

对外接口：
    process_conversation_hebbian(base_path, user_content, ai_content,
                                 concept_language="auto", concept_backend="auto")
"""

import os
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple

sys.path.insert(0, '/srv')


def _hebbian_enabled() -> bool:
    return os.getenv("NISB_HEBBIAN_ENABLED", "0").strip().lower() in ("1", "true", "yes", "on")


def extract_concepts_from_content(
    content: str,
    base_path: str,
    top_k: int = 10,
    concept_language: str = "auto",
    concept_backend: str = "auto",
) -> List[str]:
    """从文本中提取候选概念"""
    try:
        from core.concept_extractor import get_concept_extractor
        extractor = get_concept_extractor(
            base_path=base_path,
            language=concept_language,
            backend=concept_backend,
        )
        concepts = extractor.extract(content, top_k=top_k)
        return concepts
    except Exception as e:
        print(f"[WARN hebbian] concept_extractor failed, fallback to storage: {e}", file=sys.stderr)
        try:
            from core.storage import _extract_concepts_from_text
            return _extract_concepts_from_text(content, top_k=top_k, base_path=base_path)
        except Exception as e2:
            print(f"[ERROR hebbian] fallback extract_concepts failed: {e2}", file=sys.stderr)
            return []


def detect_concept_cooccurrence(concepts: List[str], window: int = 6) -> List[Tuple[str, str]]:
    """滑动窗口共现检测"""
    pairs = set()
    for i, concept_a in enumerate(concepts):
        start = max(0, i - window // 2)
        end = min(len(concepts), i + window // 2 + 1)
        for j in range(start, end):
            if i != j:
                pair = tuple(sorted([concept_a, concepts[j]]))
                pairs.add(pair)
    return list(pairs)


def get_or_create_concept_id(base_path: str, concept_name: str) -> str:
    """根据概念名创建/返回概念实体"""
    from core.storage import _generate_concept_id, save_json
    concept_id = _generate_concept_id(concept_name)
    entity_file = Path(base_path) / f"storage/entities/concepts/by_id/{concept_id}.json"
    if entity_file.exists():
        return concept_id
    entity_data = {
        "id": concept_id,
        "name": concept_name,
        "name_zh": concept_name,
        "created_at": datetime.now().isoformat(),
        "last_active": datetime.now().isoformat(),
        "activation_weight": 0.1,
        "status": "cold",
        "discussion_count": 0,
        "related_records": [],
        "tags": [],
        "category": "auto_extracted_hebbian"
    }
    entity_file.parent.mkdir(parents=True, exist_ok=True)
    save_json(str(entity_file), entity_data)
    print(f"[DEBUG hebbian] New: {concept_name}", file=sys.stderr)
    return concept_id


def create_relation_from_pair(base_path: str, concept_a: str, concept_b: str) -> dict:
    """调用 core.relations.create_relation_or_synapse"""
    from core.relations import create_relation_or_synapse
    concept_a_id = get_or_create_concept_id(base_path, concept_a)
    concept_b_id = get_or_create_concept_id(base_path, concept_b)
    try:
        return create_relation_or_synapse(
            base_path=base_path,
            from_id=concept_a_id,
            to_id=concept_b_id,
            relation_type="associated_with",
            source="hebbian_chat",
            evidence="Cooccurred in conversation",
            strategy="hebbian_cooccurrence",
            bidirectional=True
        )
    except Exception as e:
        print(f"[ERROR hebbian] {e}", file=sys.stderr)
        return {"status": "error", "message": str(e)}


def _process_conversation_hebbian_enabled(
    base_path: str,
    user_content: str,
    ai_content: str,
    concept_language: str = "auto",
    concept_backend: str = "auto",
) -> Dict[str, Any] | None:
    """原 Chat Hebbian 实现：仅在 NISB_HEBBIAN_ENABLED 显式开启时执行"""
    concept_backend = "llm_gpt4o_mini"

    start_time = datetime.now()
    print("[INFO hebbian] Start", file=sys.stderr)

    concepts_user = extract_concepts_from_content(
        user_content,
        base_path,
        top_k=10,
        concept_language=concept_language,
        concept_backend=concept_backend,
    )
    concepts_ai = extract_concepts_from_content(
        ai_content,
        base_path,
        top_k=10,
        concept_language=concept_language,
        concept_backend=concept_backend,
    )
    all_concepts = concepts_user + concepts_ai

    if not all_concepts:
        print("[WARN hebbian] No concepts", file=sys.stderr)
        return None

    print(f"[DEBUG hebbian] U={len(concepts_user)} A={len(concepts_ai)}", file=sys.stderr)

    pairs = detect_concept_cooccurrence(all_concepts, 6)
    if not pairs:
        print("[WARN hebbian] No pairs", file=sys.stderr)
        return None

    print(f"[DEBUG hebbian] {len(pairs)} pairs", file=sys.stderr)

    created, skipped, failed = 0, 0, 0
    for ca, cb in pairs:
        result = create_relation_from_pair(base_path, ca, cb)
        if result.get("status") == "success":
            created += 1
        elif "exists" in result.get("message", "").lower():
            skipped += 1
        else:
            failed += 1

    duration = (datetime.now() - start_time).total_seconds()
    log_file = Path(base_path) / "logs" / f"hebbian_{datetime.now().strftime('%Y%m')}.log"
    log_file.parent.mkdir(parents=True, exist_ok=True)

    log_entry: Dict[str, Any] = {
        "timestamp": datetime.now().isoformat(),
        "source_type": "chat",
        "concepts": len(all_concepts),
        "pairs": len(pairs),
        "created": created,
        "skipped": skipped,
        "failed": failed,
        "seconds": duration
    }

    with open(log_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")

    print(f"[INFO hebbian] Done: +{created} ~{skipped} x{failed} {duration:.1f}s", file=sys.stderr)
    return log_entry


def process_conversation_hebbian(
    base_path: str,
    user_content: str,
    ai_content: str,
    concept_language: str = "auto",
    concept_backend: str = "auto",
) -> Dict[str, Any] | None:
    """Chat 入口函数：发布前默认禁用自动 Hebbian 数据生成"""
    if not _hebbian_enabled():
        return {
            "success": False,
            "disabled": True,
            "reason": "hebbian_disabled_for_release",
            "source": "chat",
        }

    return _process_conversation_hebbian_enabled(
        base_path=base_path,
        user_content=user_content,
        ai_content=ai_content,
        concept_language=concept_language,
        concept_backend=concept_backend,
    )


__all__ = ['process_conversation_hebbian']
