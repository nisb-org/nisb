#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Embeddings处理模块 - Phase 4.0
统一处理L2和L4的embeddings生成

集中所有embedding逻辑，供enrich.py和各处理器调用
"""

import os
import json
import numpy as np
from glob import glob
from openai import OpenAI


EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIMENSIONS = 1536


def generate_l2_embeddings(brain_id: str, episode_number: int = None) -> dict:
    """
    生成L2 embeddings
    
    功能：从storage/entities/patterns读取L2数据，生成embeddings
    """
    
    base_path = f"/data/corpus/{brain_id}/documents"
    patterns_dir = f"{base_path}/storage/entities/patterns/by_id"
    embeddings_dir = f"{base_path}/storage/entities/patterns/embeddings"
    
    if not os.path.exists(patterns_dir):
        return {"status": "error", "message": "❌ patterns目录不存在"}
    
    os.makedirs(embeddings_dir, exist_ok=True)
    
    # 获取pattern文件
    if episode_number:
        pattern_files = [f"{patterns_dir}/pattern_ep{episode_number:03d}.json"]
    else:
        pattern_files = sorted(glob(f"{patterns_dir}/pattern_ep*.json"))
    
    if not pattern_files:
        return {"status": "error", "message": "❌ 未找到pattern文件"}
    
    # 提取文本
    all_texts = []
    all_metadata = []
    
    for pattern_file in pattern_files:
        try:
            with open(pattern_file, 'r', encoding='utf-8') as f:
                pattern_data = json.load(f)
        except Exception as e:
            print(f"⚠️ 跳过文件 {pattern_file}: {e}")
            continue
        
        episode_num = pattern_data.get("episode_number", 0)
        
        # 兼容两种格式
        if "L2_pattern" in pattern_data:
            l2_data = pattern_data["L2_pattern"]
        else:
            l2_data = pattern_data
        
        # 提取各类模板
        for pattern_type in ["opening_hooks", "transition_phrases", "rhetorical_devices", "explanation_patterns"]:
            items = l2_data.get(pattern_type, [])
            
            if pattern_type == "rhetorical_devices":
                text_field = "example"
            elif pattern_type == "explanation_patterns":
                text_field = "simple_explanation"
            else:
                text_field = "text"
            
            for item in items:
                if not isinstance(item, dict):
                    continue
                
                text = item.get(text_field) or item.get("text", "")
                if text and isinstance(text, str) and text.strip():
                    all_texts.append(text)
                    all_metadata.append({
                        "episode": episode_num,
                        "pattern_type": pattern_type,
                        "text": text,
                        "timestamp": item.get("timestamp", "N/A"),
                        "effectiveness_score": item.get("effectiveness_score", 0.85)
                    })
    
    if not all_texts:
        return {"status": "error", "message": "❌ 未找到任何L2文本"}
    
    # 生成embeddings
    try:
        client = OpenAI(api_key=os.environ.get('OPENAI_API_KEY'))
        embeddings_list = []
        
        for i in range(0, len(all_texts), 100):
            batch = all_texts[i:i+100]
            response = client.embeddings.create(
                model=EMBEDDING_MODEL,
                input=batch,
                dimensions=EMBEDDING_DIMENSIONS
            )
            embeddings_list.extend([item.embedding for item in response.data])
        
        # 保存
        embeddings_array = np.array(embeddings_list)
        np.save(f"{embeddings_dir}/embeddings.npy", embeddings_array)
        
        with open(f"{embeddings_dir}/metadata.json", 'w', encoding='utf-8') as f:
            json.dump(all_metadata, f, ensure_ascii=False, indent=2)
        
        return {
            "status": "success",
            "type": "l2",
            "embeddings_count": len(embeddings_list),
            "message": f"✅ L2 embeddings: {len(embeddings_list)}个"
        }
    
    except Exception as e:
        return {"status": "error", "message": f"❌ L2 embeddings生成失败：{e}"}


def generate_l4_embeddings(brain_id: str) -> dict:
    """
    生成L4 embeddings
    
    功能：从storage/entities/l4_methods读取L4数据，生成embeddings
    """
    
    l4_dir = f"/opt/nisb-data/corpus/{brain_id}/storage/entities/l4_methods/by_episode"
    embeddings_dir = f"/opt/nisb-data/corpus/{brain_id}/storage/entities/l4_methods/embeddings"
    
    if not os.path.exists(l4_dir):
        return {"status": "success", "message": "ⓘ L4目录不存在（跳过）"}
    
    os.makedirs(embeddings_dir, exist_ok=True)
    
    # 获取L4文件
    l4_files = sorted([f for f in os.listdir(l4_dir) if f.endswith('_l4.json')])
    
    if not l4_files:
        return {"status": "success", "message": "ⓘ 未找到L4文件（跳过）"}
    
    # 提取文本
    all_texts = []
    all_metadata = []
    
    for l4_file in l4_files:
        try:
            with open(os.path.join(l4_dir, l4_file), 'r', encoding='utf-8', errors='ignore') as f:
                data = json.load(f)
            
            ep_num = int(l4_file.split('ep')[1].split('_')[0])
            
            for pattern in data.get('l4_patterns_extracted', []):
                l4_name = pattern.get('l4_name', '')
                rule = pattern.get('rule', '')
                
                if l4_name and rule:
                    text = f"{l4_name}。{rule}"
                    all_texts.append(text)
                    all_metadata.append({
                        "episode": ep_num,
                        "l4_name": l4_name,
                        "l4_id": pattern.get('l4_id', ''),
                        "confidence": pattern.get('frequency_score', 0.85)
                    })
        
        except Exception as e:
            print(f"⚠️ 跳过L4文件 {l4_file}: {e}")
            continue
    
    if not all_texts:
        return {"status": "success", "message": "ⓘ 未找到L4文本（跳过）"}
    
    # 生成embeddings
    try:
        client = OpenAI(api_key=os.environ.get('OPENAI_API_KEY'))
        embeddings_list = []
        
        for i in range(0, len(all_texts), 50):
            batch = all_texts[i:i+50]
            response = client.embeddings.create(
                model=EMBEDDING_MODEL,
                input=batch,
                dimensions=EMBEDDING_DIMENSIONS
            )
            embeddings_list.extend([item.embedding for item in response.data])
        
        # 保存
        embeddings_array = np.array(embeddings_list)
        np.save(f"{embeddings_dir}/l4_embeddings.npy", embeddings_array)
        
        with open(f"{embeddings_dir}/l4_metadata.json", 'w', encoding='utf-8') as f:
            json.dump(all_metadata, f, ensure_ascii=False, indent=2)
        
        return {
            "status": "success",
            "type": "l4",
            "embeddings_count": len(embeddings_list),
            "message": f"✅ L4 embeddings: {len(embeddings_list)}个"
        }
    
    except Exception as e:
        return {"status": "error", "message": f"❌ L4 embeddings生成失败：{e}"}


def generate_all_embeddings(brain_id: str, episode_number: int = None) -> dict:
    """
    同时生成L2和L4 embeddings
    
    使用场景：入库完成后，一次性生成所有embeddings
    """
    
    results = {
        "l2": None,
        "l4": None,
        "total_embeddings": 0,
        "status": "success"
    }
    
    # 生成L2
    l2_result = generate_l2_embeddings(brain_id, episode_number)
    results["l2"] = l2_result
    if l2_result.get("status") == "success":
        results["total_embeddings"] += l2_result.get("embeddings_count", 0)
    
    # 生成L4
    l4_result = generate_l4_embeddings(brain_id)
    results["l4"] = l4_result
    if l4_result.get("status") == "success":
        results["total_embeddings"] += l4_result.get("embeddings_count", 0)
    
    results["message"] = f"✅ 总embeddings: {results['total_embeddings']}个"
    
    return results


__all__ = [
    'generate_l2_embeddings',
    'generate_l4_embeddings',
    'generate_all_embeddings'
]

