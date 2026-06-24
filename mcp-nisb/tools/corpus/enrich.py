#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Corpus Enrich工具 - Phase 4.0（简化版）

简化设计：
- 所有embedding逻辑迁移到embeddings_handler.py
- 此文件只负责API入口和参数处理
"""

import os
from tools.corpus.embeddings_handler import generate_l2_embeddings, generate_l4_embeddings, generate_all_embeddings


def nisb_corpus_enrich(args: dict) -> dict:
    """
    Enrich API - 为corpus生成embeddings
    
    参数：
    - brain_id: 大脑ID（必填）
    - episode_number: 指定episode（可选，不填则全量）
    - type: "l2" | "l4" | "all"（默认all）
    - force: 是否强制重新生成（默认False，暂未实现）
    
    使用：
    nisb_corpus_enrich({"brain_id": "brain_utopia"})
    """
    
    brain_id = args.get("brain_id")
    episode_number = args.get("episode_number")
    enrich_type = args.get("type", "all")
    
    if not brain_id:
        return {"status": "error", "message": "❌ brain_id不能为空"}
    
    # 检查brain是否存在
    if not os.path.exists(f"/data/corpus/{brain_id}"):
        return {"status": "error", "message": f"❌ 大脑不存在：{brain_id}"}
    
    # ========== 分别生成 ==========
    if enrich_type == "l2":
        result = generate_l2_embeddings(brain_id, episode_number)
    
    elif enrich_type == "l4":
        result = generate_l4_embeddings(brain_id)
    
    elif enrich_type == "all":
        result = generate_all_embeddings(brain_id, episode_number)
    
    else:
        return {"status": "error", "message": f"❌ 未知的type：{enrich_type}"}
    
    return result


__all__ = ['nisb_corpus_enrich']

