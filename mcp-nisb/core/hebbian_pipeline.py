#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Hebbian Pipeline - 通用文本事件处理入口

接口：
    process_text_event(
        base_path: str,
        source_type: str,   # "chat" | "note" | "doc" | "corpus" | "library" ...
        source_id: str,     # conv_id / doc_id / note_path ...
        text: str,
        concept_language: str = "auto",
        concept_backend: str  = "auto",
        top_k: int = 10,
    )

内部流程：
1. 调用 concept_extractor 获取概念列表
2. 共现检测
3. 创建/强化 Relations 或 Synapses
4. 写入日志
"""

import sys
import json
from datetime import datetime
from pathlib import Path
from typing import List, Tuple, Dict, Any

sys.path.insert(0, '/srv')

from core.concept_extractor import get_concept_extractor
from core.storage import _generate_concept_id, save_json
from core.relations import create_relation_or_synapse


def _detect_pairs(concepts: List[str], window: int = 6) -> List[Tuple[str, str]]:
    """滑动窗口共现检测"""
    pairs = set()
    for i, a in enumerate(concepts):
        start = max(0, i - window // 2)
        end = min(len(concepts), i + window // 2 + 1)
        for j in range(start, end):
            if i == j:
                continue
            b = concepts[j]
            pair = tuple(sorted([a, b]))
            pairs.add(pair)
    return list(pairs)


def _get_or_create_concept_id(base_path: str, name: str) -> str:
    """根据名称获取或创建概念实体"""
    cid = _generate_concept_id(name)
    entity_file = Path(base_path) / f"storage/entities/concepts/by_id/{cid}.json"
    if entity_file.exists():
        return cid

    now = datetime.now().isoformat()
    entity = {
        "id": cid,
        "name": name,
        "name_zh": name,
        "created_at": now,
        "last_active": now,
        "activation_weight": 0.1,
        "status": "cold",
        "discussion_count": 0,
        "related_records": [],
        "tags": [],
        "category": "auto_extracted_hebbian",
    }
    entity_file.parent.mkdir(parents=True, exist_ok=True)
    save_json(str(entity_file), entity)
    print(f"[DEBUG hebbian] New concept: {name} -> {cid}", file=sys.stderr)
    return cid


def process_text_event(
    base_path: str,
    source_type: str,
    source_id: str,
    text: str,
    concept_language: str = "auto",
    concept_backend: str  = "auto",
    top_k: int = 10,
) -> Dict[str, Any] | None:
    """通用文本事件 Hebbian 处理入口
    
    返回:
        - 成功时: log_entry 字典
          {
            "timestamp": ...,
            "source_type": ...,
            "source_id": ...,
            "concepts": int,
            "pairs": int,
            "created": int,
            "skipped": int,
            "failed": int,
            "seconds": float,
          }
        - 失败/早退时: None
    """
    start_time = datetime.now()
    print(f"[INFO hebbian] Start for {source_type}:{source_id}", file=sys.stderr)

    # 1. 概念抽取（⭐ 修复：显式传 base_path）
    extractor = get_concept_extractor(
        base_path=base_path,
        language=concept_language,
        backend=concept_backend,
    )
    concepts = extractor.extract(text, top_k=top_k)
    
    if not concepts:
        print("[WARN hebbian] No concepts extracted, skip", file=sys.stderr)
        return None

    print(f"[DEBUG hebbian] Concepts: {len(concepts)}", file=sys.stderr)

    # 2. 共现检测
    pairs = _detect_pairs(concepts, window=6)
    if not pairs:
        print("[WARN hebbian] No co-occurrence pairs, skip", file=sys.stderr)
        return None

    print(f"[DEBUG hebbian] Pairs: {len(pairs)}", file=sys.stderr)

    # 3. 创建关系/突触
    created, skipped, failed = 0, 0, 0
    for a, b in pairs:
        try:
            ca = _get_or_create_concept_id(base_path, a)
            cb = _get_or_create_concept_id(base_path, b)
            result = create_relation_or_synapse(
                base_path=base_path,
                from_id=ca,
                to_id=cb,
                relation_type="associated_with",
                source=f"hebbian_{source_type}",
                evidence=f"{source_type}:{source_id} 中共现",
                strategy="hebbian_cooccurrence",
                bidirectional=True,
            )
            if result.get("status") == "success":
                created += 1
            elif "已存在" in result.get("message", "") or "exists" in result.get("message", "").lower():
                skipped += 1
            else:
                failed += 1
        except Exception as e:
            failed += 1
            print(f"[ERROR hebbian] {a} <-> {b}: {e}", file=sys.stderr)

    # 4. 写日志
    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()
    log_entry: Dict[str, Any] = {
        "timestamp": end_time.isoformat(),
        "source_type": source_type,
        "source_id": source_id,
        "concepts": len(concepts),
        "pairs": len(pairs),
        "created": created,
        "skipped": skipped,
        "failed": failed,
        "seconds": duration,
    }

    log_file = Path(base_path) / "logs" / f"hebbian_{datetime.now().strftime('%Y%m')}.log"
    log_file.parent.mkdir(parents=True, exist_ok=True)
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")

    print(f"[INFO hebbian] Done: +{created} ~{skipped} x{failed} {duration:.2f}s", file=sys.stderr)

    # ⭐ 新增：把本次统计信息返回给调用方（chat/文件/库/语料都可以用）
    return log_entry

