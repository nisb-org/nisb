#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
NISB Corpus Ingest Tool - Phase 4.2
统一入库工具
"""

import os
from tools.corpus.processors import auto_detect_processor


def nisb_corpus_ingest(args: dict) -> dict:
    """
    统一入库工具 - Phase 4.2 (修复LibreChat参数转换问题)
    """
    
    # ========== Phase 4.2：处理LibreChat的action参数转换 ==========
    action = args.get("action")
    
    if action:
        if action == "guide":
            args["guide"] = True
        elif action == "validate":
            args["validate"] = True
        elif action == "list_staging":
            args["list_staging"] = True
        elif action == "from_staging":
            # ⭐ 关键修复：LibreChat会把from_staging转成action="from_staging"
            args["from_staging"] = True
            # 如果没有selected_files，立刻在这里扫描
            if not args.get("selected_files"):
                brain_id = args.get("brain_id", "brain_utopia")
                pending_dir = f"/opt/nisb-data/corpus/{brain_id}/staging/pending"
                selected_files = []
                try:
                    if os.path.exists(pending_dir):
                        for filename in os.listdir(pending_dir):
                            if filename.endswith('.json'):
                                file_type = "L4" if "_l4.json" in filename else "L2"
                                selected_files.append({"filename": filename, "type": file_type})
                    if selected_files:
                        args["selected_files"] = selected_files
                        print(f"🔍 自动发现{len(selected_files)}个文件")
                except Exception as e:
                    print(f"⚠️ 扫描失败: {e}")
        elif action == "auto":
            args["from_staging"] = True
            args["auto_enrich"] = True
    
    # ========== 原有逻辑：从staging自动扫描 ==========
    if args.get("from_staging") and not args.get("selected_files"):
        brain_id = args.get("brain_id", "brain_utopia")
        pending_dir = f"/opt/nisb-data/corpus/{brain_id}/staging/pending"
        
        selected_files = []
        try:
            if os.path.exists(pending_dir):
                for filename in os.listdir(pending_dir):
                    if filename.endswith('.json'):
                        file_type = "L4" if "_l4.json" in filename else "L2"
                        selected_files.append({"filename": filename, "type": file_type})
                
                if selected_files:
                    args["selected_files"] = selected_files
                    print(f"🔍 自动发现{len(selected_files)}个待处理文件")
        except Exception as e:
            print(f"⚠️ 扫描pending目录失败：{e}")
    
    # ========== 自动检测用户意图 ==========
    processor = auto_detect_processor(args)
    
    # ========== 执行处理 ==========
    return processor.execute(args)


def _enhance_pattern_for_future(pattern: dict, brain_id: str, episode_number: int) -> dict:
    """原有的模式增强函数"""
    import re
    from datetime import datetime
    
    enhanced = pattern.copy() if isinstance(pattern, dict) else {}
    
    if "L2_pattern" in enhanced and isinstance(enhanced["L2_pattern"], dict):
        l2 = enhanced.pop("L2_pattern")
        for key in ["opening_hooks", "transition_phrases", "rhetorical_devices", "explanation_patterns"]:
            if key in l2:
                enhanced[key] = l2[key]
    
    for noisy in ["L1_segments", "metadata"]:
        enhanced.pop(noisy, None)
    
    for kind in ["opening_hooks", "transition_phrases", "rhetorical_devices", "explanation_patterns"]:
        enhanced[kind] = _clean_templates_list(enhanced.get(kind, []), kind)
    
    if "id" not in enhanced:
        enhanced["id"] = f"pattern_ep{episode_number:03d}"
    enhanced["brain_id"] = brain_id
    enhanced["episode_number"] = episode_number
    if "extracted_at" not in enhanced:
        enhanced["extracted_at"] = datetime.now().isoformat()
    
    if "concept_mapping" not in enhanced:
        enhanced["concept_mapping"] = {"_comment": "Phase 3.0", "_placeholder": True}
    
    if "neuroplasticity_metadata" not in enhanced:
        enhanced["neuroplasticity_metadata"] = {
            "exposure_count": 0,
            "internalization_score": 0.0,
            "last_exposed": None,
            "usage_count": 0
        }
    
    if "weight" not in enhanced:
        enhanced["weight"] = 0.5
    
    if "related_episodes" not in enhanced:
        enhanced["related_episodes"] = []
    
    return enhanced


def _clean_templates_list(items, kind: str):
    """原有的清洗函数"""
    import re
    
    if not isinstance(items, list):
        return []
    
    _CN_KEY_MAP = {"文本": "text", "时间戳": "timestamp", "类型": "type"}
    _VARIANT_KEY_MAP = {" text ": "text", " text": "text", "text ": "text"}
    _TIME_RE = re.compile(r"^\s*(\d{1,2})\s*:\s*(\d{2})\s*$")
    
    def _norm_key(key: str) -> str:
        if not isinstance(key, str):
            return key
        k = key.strip()
        return _CN_KEY_MAP.get(k) or _VARIANT_KEY_MAP.get(k) or k
    
    def _norm_ts(ts: str) -> str:
        if not ts or not isinstance(ts, str):
            return "N/A"
        ts = ts.strip()
        m = _TIME_RE.match(ts)
        if m:
            return f"{int(m.group(1)):02d}:{int(m.group(2)):02d}"
        return ts
    
    def _default_score_for(kind: str) -> float:
        return 0.90 if kind == "opening_hooks" else 0.85
    
    clean = []
    seen = set()
    
    for it in items:
        if not isinstance(it, dict):
            continue
        
        it = {_norm_key(k): v for k, v in it.items()}
        
        if kind in ("opening_hooks", "transition_phrases"):
            text_field = "text"
        elif kind == "rhetorical_devices":
            text_field = "example"
        elif kind == "explanation_patterns":
            text_field = "simple_explanation"
        else:
            text_field = "text"
        
        key_text = it.get(text_field) or it.get("text") or it.get("example")
        if not (isinstance(key_text, str) and key_text.strip()):
            continue
        
        key_text_norm = key_text.strip()
        
        if "timestamp" in it:
            it["timestamp"] = _norm_ts(str(it["timestamp"]))
        else:
            it["timestamp"] = "N/A"
        
        if "effectiveness_score" not in it:
            it["effectiveness_score"] = _default_score_for(kind)
        else:
            try:
                it["effectiveness_score"] = float(it["effectiveness_score"])
            except:
                it["effectiveness_score"] = _default_score_for(kind)
        
        dedup_key = (kind, key_text_norm)
        if dedup_key in seen:
            continue
        seen.add(dedup_key)
        
        clean.append(it)
    
    return clean


__all__ = ['nisb_corpus_ingest']
