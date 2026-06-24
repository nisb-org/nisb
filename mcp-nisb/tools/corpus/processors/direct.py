#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
直接入库处理器
处理：用户直接提供L1+L2+L3数据进行入库
"""

import os
import json
from datetime import datetime
from .base import BaseProcessor


class DirectIngestProcessor(BaseProcessor):
    """
    直接入库处理器
    
    功能：
    - 接收L1字幕、L2模式、L3案例数据
    - 进行数据清洗和规范化
    - 保存到storage目录
    - 自动触发embeddings生成
    """
    
    def execute(self, args: dict) -> dict:
        """执行直接入库"""
        
        from core.storage import get_corpus_base_path, get_corpus_meta
        from tools.corpus.ingest import _enhance_pattern_for_future
        
        # ========== 参数验证 ==========
        brain_id = args.get("brain_id")
        episode_number = args.get("episode_number")
        L1_segments = args.get("L1_segments", [])
        L2_pattern = args.get("L2_pattern", {})
        L3_cases = args.get("L3_cases", [])
        
        if not brain_id:
            return {"status": "error", "message": "❌ brain_id不能为空"}
        
        if not episode_number:
            return {"status": "error", "message": "❌ episode_number不能为空"}
        
        if not L1_segments and not L2_pattern:
            return {"status": "error", "message": "❌ L1_segments和L2_pattern至少提供一个"}
        
        # ========== 获取paths ==========
        try:
            base_path = get_corpus_base_path(brain_id)
            storage_path = f"{base_path}/storage"
            meta = get_corpus_meta(brain_id)
        except FileNotFoundError:
            return {
                "status": "error",
                "message": f"❌ 大脑不存在：{brain_id}"
            }
        
        files_created = []
        
        # ========== 保存L1（字幕）==========
        if L1_segments:
            episodes_dir = f"{storage_path}/raw/episodes"
            os.makedirs(episodes_dir, exist_ok=True)
            
            episode_file = f"{episodes_dir}/ep{episode_number:03d}.jsonl"
            with open(episode_file, 'w', encoding='utf-8') as f:
                for idx, segment in enumerate(L1_segments, 1):
                    seg = segment if isinstance(segment, dict) else {"text": str(segment)}
                    if "id" not in seg:
                        seg["id"] = f"{brain_id}_ep{episode_number:03d}_seg{idx}"
                    f.write(json.dumps(seg, ensure_ascii=False) + '\n')
            files_created.append(episode_file)
        
        # ========== 保存L2+L3（模式+案例）==========
        if L2_pattern:
            patterns_dir = f"{storage_path}/entities/patterns/by_id"
            os.makedirs(patterns_dir, exist_ok=True)
            
            pattern_file = f"{patterns_dir}/pattern_ep{episode_number:03d}.json"
            
            # 增强和清洗
            enhanced_pattern = _enhance_pattern_for_future(L2_pattern, brain_id, episode_number)
            enhanced_pattern["L3_cases"] = L3_cases if L3_cases else []
            
            with open(pattern_file, 'w', encoding='utf-8') as f:
                json.dump(enhanced_pattern, f, ensure_ascii=False, indent=2)
            
            files_created.append(pattern_file)
        
        # ========== 保存L3副本 ==========
        if L3_cases:
            cases_dir = f"{storage_path}/cases/by_episode"
            os.makedirs(cases_dir, exist_ok=True)
            
            cases_file = f"{cases_dir}/cases_ep{episode_number:03d}.jsonl"
            with open(cases_file, 'w', encoding='utf-8') as f:
                for case in L3_cases:
                    f.write(json.dumps(case, ensure_ascii=False) + '\n')
            files_created.append(cases_file)
        
        # ========== 更新meta ==========
        meta["statistics"]["episode_count"] += 1
        meta["updated_at"] = datetime.now().isoformat()
        
        meta_path = f"/data/corpus/{brain_id}/meta.json"
        with open(meta_path, 'w', encoding='utf-8') as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)
        
        # ========== 自动生成embeddings ==========
        embeddings_info = ""
        try:
            from tools.corpus.embeddings_handler import generate_all_embeddings
            result = generate_all_embeddings(brain_id, episode_number)
            embeddings_info = f"\n   ✅ Embeddings：{result.get('total_embeddings', 0)}个"
        except Exception as e:
            embeddings_info = f"\n   ⚠️ Embeddings生成失败（可稍后手动运行）"
        
        # ========== 返回结果 ==========
        return {
            "status": "success",
            "brain_id": brain_id,
            "episode": episode_number,
            "files_created": files_created,
            "message": (
                f"✅ 已入库：{meta['display_name']} ep{episode_number:03d}\n"
                f"   L1字幕：{len(L1_segments)}个segments\n"
                f"   L2模式：{'是' if L2_pattern else '否'}\n"
                f"   L3案例：{len(L3_cases)}个\n"
                f"   文件：{len(files_created)}个"
                f"{embeddings_info}"
            )
        }

