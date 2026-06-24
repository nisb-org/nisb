#!/usr/bin/env python3
"""
NISB Core - Storage Operations
存储操作模块 - Phase 2.5完整版 + Phase 5.1路径修复

提供文件读写、索引管理、概念提取、黑名单过滤、同义词映射等功能
"""

import json
import os
import numpy as np
import hashlib
from datetime import datetime
from typing import Dict, List, Optional

# Phase 2: 概念提取
try:
    import jieba
    import jieba.analyse
    JIEBA_AVAILABLE = True
except ImportError:
    JIEBA_AVAILABLE = False
    print("[WARN] jieba未安装，概念提取功能将被禁用")

# ========== Phase 2.5：全局缓存 ==========
_CONCEPT_BLACKLIST = None
_CONCEPT_SYNONYMS = None


def ensure_directories(base_path: str):
    """Ensure all required user directories exist."""
    dirs = [
        "agent_files",
        "storage/raw/daily",
        "storage/raw/quick_notes",
        "storage/entities/concepts/by_id",
        "storage/entities/concepts/meta",
        "storage/entities/relations/by_type",
        "storage/config",
        "indexes/primary",
        "indexes/temporal",
        "cache",
        "analytics"
    ]
    for d in dirs:
        os.makedirs(os.path.join(base_path, d), exist_ok=True)


def save_json(file_path: str, data: Dict) -> bool:
    """保存JSON文件"""
    try:
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"Error saving JSON to {file_path}: {e}")
        return False


def load_json(file_path: str) -> Optional[Dict]:
    """加载JSON文件"""
    try:
        if not os.path.exists(file_path):
            return None
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading JSON from {file_path}: {e}")
        return None


def append_jsonl(file_path: str, data: Dict) -> bool:
    """追加到JSONL文件"""
    try:
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, 'a', encoding='utf-8') as f:
            f.write(json.dumps(data, ensure_ascii=False) + '\n')
        return True
    except Exception as e:
        print(f"Error appending to JSONL {file_path}: {e}")
        return False


def load_jsonl(file_path: str) -> List[Dict]:
    """加载JSONL文件"""
    try:
        if not os.path.exists(file_path):
            return []
        lines = []
        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line:
                    lines.append(json.loads(line))
        return lines
    except Exception as e:
        print(f"Error loading JSONL from {file_path}: {e}")
        return []


def save_raw_record(base_path: str, raw_data: Dict) -> str:
    """保存原始记录到daily目录"""
    date_str = datetime.now().strftime("%Y-%m-%d")
    daily_dir = os.path.join(base_path, "storage/raw/daily", date_str)
    os.makedirs(daily_dir, exist_ok=True)
    
    file_path = os.path.join(daily_dir, f"{raw_data['id']}.json")
    save_json(file_path, raw_data)
    return file_path


def save_quick_note(base_path: str, note_data: Dict) -> str:
    """保存快速笔记"""
    date_str = datetime.now().strftime("%Y-%m-%d")
    file_path = os.path.join(base_path, "storage/raw/quick_notes", f"{date_str}.jsonl")
    append_jsonl(file_path, note_data)
    return file_path


def load_hot_cache(base_path: str) -> Dict:
    """加载热缓存"""
    cache_file = os.path.join(base_path, "cache/hot_concepts.json")
    data = load_json(cache_file)
    if data:
        return data
    
    return {
        "generated_at": datetime.now().isoformat(),
        "period": "last_30_days",
        "concepts": [],
        "relations": [],
        "stats": {
            "total_hot_concepts": 0,
            "avg_activation": 0.0
        }
    }


def save_hot_cache(base_path: str, cache_data: Dict) -> bool:
    """保存热缓存"""
    cache_file = os.path.join(base_path, "cache/hot_concepts.json")
    return save_json(cache_file, cache_data)


def load_concepts_index(base_path: str) -> Dict:
    """加载概念索引"""
    index_file = os.path.join(base_path, "indexes/primary/concepts.index.json")
    data = load_json(index_file)
    if data:
        return data
    
    return {
        "version": "1.0",
        "total": 0,
        "last_updated": datetime.now().isoformat(),
        "concepts": {},
        "by_category": {},
        "by_status": {"hot": [], "warm": [], "cold": []}
    }


def save_concepts_index(base_path: str, index_data: Dict) -> bool:
    """保存概念索引"""
    index_file = os.path.join(base_path, "indexes/primary/concepts.index.json")
    index_data["last_updated"] = datetime.now().isoformat()
    return save_json(index_file, index_data)


def search_concepts_simple(base_path: str, query: str, limit: int = 10) -> List[Dict]:
    """简单的概念搜索（关键词匹配）"""
    index = load_concepts_index(base_path)
    concepts = index.get("concepts", {})
    
    query_lower = query.lower()
    results = []
    
    for concept_id, concept_data in concepts.items():
        name = concept_data.get("name", "").lower()
        name_zh = concept_data.get("name_zh", "").lower()
        tags = [t.lower() for t in concept_data.get("tags", [])]
        
        if (query_lower in name or 
            query_lower in name_zh or 
            any(query_lower in tag for tag in tags)):
            results.append({
                "id": concept_id,
                "name": concept_data.get("name"),
                "name_zh": concept_data.get("name_zh"),
                "activation_weight": concept_data.get("activation_weight", 0),
                "last_active": concept_data.get("last_active"),
                "relevance": 1.0
            })
    
    results.sort(key=lambda x: x["activation_weight"], reverse=True)
    return results[:limit]


def get_system_stats(base_path: str) -> Dict:
    """获取系统统计信息"""
    hot_cache = load_hot_cache(base_path)
    concepts_index = load_concepts_index(base_path)
    
    raw_daily_dir = os.path.join(base_path, "storage/raw/daily")
    daily_count = 0
    if os.path.exists(raw_daily_dir):
        for date_dir in os.listdir(raw_daily_dir):
            date_path = os.path.join(raw_daily_dir, date_dir)
            if os.path.isdir(date_path):
                daily_count += len([f for f in os.listdir(date_path) if f.endswith('.json')])
    
    quick_notes_dir = os.path.join(base_path, "storage/raw/quick_notes")
    quick_count = 0
    if os.path.exists(quick_notes_dir):
        for filename in os.listdir(quick_notes_dir):
            if filename.endswith('.jsonl'):
                file_path = os.path.join(quick_notes_dir, filename)
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        quick_count += sum(1 for line in f if line.strip())
                except Exception as e:
                    print(f"[WARN] Error reading {file_path}: {e}")
    
    total_raw_records = daily_count + quick_count
    
    return {
        "total_concepts": concepts_index.get("total", 0),
        "hot_concepts_count": len(hot_cache.get("concepts", [])),
        "total_raw_records": total_raw_records,
        "daily_records": daily_count,
        "quick_notes": quick_count,
        "cache_updated": hot_cache.get("generated_at"),
        "index_updated": concepts_index.get("last_updated")
    }


# ============================================================
# Phase 2.5：黑名单加载
# ============================================================

def _load_concept_blacklist(base_path: str) -> set:
    """
    加载概念黑名单（Phase 2.5）
    
    返回: set of lowercase words
    """
    global _CONCEPT_BLACKLIST
    
    if _CONCEPT_BLACKLIST is not None:
        return _CONCEPT_BLACKLIST
    
    blacklist_file = f"{base_path}/storage/config/concept_blacklist.txt"
    
    if not os.path.exists(blacklist_file):
        print(f"[WARN] 概念黑名单文件不存在: {blacklist_file}")
        print(f"[INFO] 系统将不过滤任何概念。请创建该文件以启用过滤。")
        _CONCEPT_BLACKLIST = set()
        return _CONCEPT_BLACKLIST
    
    blacklist = set()
    try:
        with open(blacklist_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                blacklist.add(line.lower())
        print(f"[INFO] 加载概念黑名单: {len(blacklist)}个词")
    except Exception as e:
        print(f"[ERROR] 加载黑名单失败: {e}")
        blacklist = set()
    
    _CONCEPT_BLACKLIST = blacklist
    return blacklist


# ============================================================
# Phase 2.5：同义词映射加载
# ============================================================

def _load_concept_synonyms(base_path: str) -> dict:
    """
    加载概念同义词映射（Phase 2.5）
    
    返回: dict {english_word: chinese_word, ...}
    """
    global _CONCEPT_SYNONYMS
    
    if _CONCEPT_SYNONYMS is not None:
        return _CONCEPT_SYNONYMS
    
    synonyms_file = f"{base_path}/storage/config/concept_synonyms.txt"
    
    if not os.path.exists(synonyms_file):
        print(f"[WARN] 同义词映射文件不存在: {synonyms_file}")
        print(f"[INFO] 英文概念将保留原样。创建该文件以启用双语映射。")
        _CONCEPT_SYNONYMS = {}
        return _CONCEPT_SYNONYMS
    
    synonyms = {}
    try:
        with open(synonyms_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                if '=' in line:
                    parts = line.split('=', 1)
                    if len(parts) == 2:
                        en_word = parts[0].strip().lower()
                        zh_word = parts[1].strip()
                        if en_word and zh_word:
                            synonyms[en_word] = zh_word
        print(f"[INFO] 加载同义词映射: {len(synonyms)}个")
    except Exception as e:
        print(f"[ERROR] 加载同义词映射失败: {e}")
        synonyms = {}
    
    _CONCEPT_SYNONYMS = synonyms
    return synonyms


# ============================================================
# Phase 2.5：应用同义词映射
# ============================================================

def _apply_synonym_mapping(concepts: list, base_path: str) -> list:
    """
    将英文概念映射为中文概念（Phase 2.5）
    
    返回: 映射后的概念列表
    """
    synonyms = _load_concept_synonyms(base_path)
    
    if not synonyms:
        return concepts
    
    mapped = []
    for concept in concepts:
        concept_lower = concept.lower()
        if concept_lower in synonyms:
            zh_concept = synonyms[concept_lower]
            mapped.append(zh_concept)
            print(f"[DEBUG] 映射: {concept} → {zh_concept}")
        else:
            mapped.append(concept)
    
    # 去重（保持顺序）
    seen = set()
    deduped = []
    for c in mapped:
        if c not in seen:
            seen.add(c)
            deduped.append(c)
    
    return deduped


# ============================================================
# Phase 2: 概念提取功能（Phase 2.5改进：黑名单过滤）
# ============================================================

def _extract_concepts_from_text(text: str, top_k: int = 10, base_path: str = None) -> List[str]:
    """
    从文本中提取候选概念（Phase 2.5：黑名单过滤）
    
    ✅ Phase 5.1修复：base_path改为可选参数，默认动态获取
    
    改进:
      - 提取3倍候选词（避免过滤后数量不足）
      - 使用黑名单过滤无意义词
      - 返回高质量概念
    """
    # ✅ 修复：base_path为None时动态获取
    if base_path is None:
        from core.user_context import get_user_ctx
        base_path = get_user_ctx().base
    
    if not JIEBA_AVAILABLE:
        print("[WARN] jieba未安装，返回空概念列表")
        return []
    
    if not text or len(text.strip()) < 5:
        return []
    
    try:
        # Phase 2.5改进：提取3倍候选（确保过滤后仍有足够概念）
        candidate_count = top_k * 3
        keywords = jieba.analyse.extract_tags(text, topK=candidate_count, withWeight=False)
        
        # Phase 2.5新增：加载黑名单
        blacklist = _load_concept_blacklist(base_path)
        
        # 过滤：长度>=2，不全是数字，不在黑名单中
        filtered = []
        for kw in keywords:
            kw_lower = kw.lower()
            
            # 基本过滤
            if len(kw) < 2 or kw.isdigit():
                continue
            
            # 黑名单过滤（如果黑名单为空，则不过滤）
            if blacklist and kw_lower in blacklist:
                continue
            
            filtered.append(kw)
        
        print(f"[DEBUG] 概念提取: 原始{len(keywords)}个 → 黑名单过滤 → 最终{len(filtered[:top_k])}个")
        
        return filtered[:top_k]
    
    except Exception as e:
        print(f"[ERROR] 概念提取失败: {e}")
        return []


def _generate_concept_id(concept_name: str) -> str:
    """生成概念ID"""
    hash_obj = hashlib.md5(concept_name.encode('utf-8'))
    return f"concept_{hash_obj.hexdigest()[:12]}"


def update_concept_entity(base_path: str, concept_name: str, source_id: str, source_type: str) -> str:
    """
    创建或更新概念实体
    
    返回: concept_id
    """
    concept_id = _generate_concept_id(concept_name)
    entity_file = os.path.join(base_path, f"storage/entities/concepts/by_id/{concept_id}.json")
    
    now = datetime.now().isoformat()
    
    if os.path.exists(entity_file):
        entity_data = load_json(entity_file)
        if entity_data:
            old_weight = entity_data.get("activation_weight", 0.1)
            new_weight = min(1.0, old_weight + 0.1)
            entity_data["activation_weight"] = new_weight
            entity_data["last_active"] = now
            entity_data["discussion_count"] = entity_data.get("discussion_count", 0) + 1
            
            if source_id not in entity_data.get("related_records", []):
                entity_data.setdefault("related_records", []).append(source_id)
            
            if new_weight >= 0.7:
                entity_data["status"] = "hot"
            elif new_weight >= 0.4:
                entity_data["status"] = "warm"
            else:
                entity_data["status"] = "cold"
            
            save_json(entity_file, entity_data)
            print(f"[DEBUG concept_update] 更新概念: {concept_name} (权重: {old_weight:.2f}→{new_weight:.2f})")
            return concept_id
    
    entity_data = {
        "id": concept_id,
        "name": concept_name,
        "name_zh": concept_name,
        "created_at": now,
        "last_active": now,
        "activation_weight": 0.1,
        "status": "cold",
        "discussion_count": 1,
        "related_records": [source_id],
        "tags": [],
        "category": "auto_extracted"
    }
    
    save_json(entity_file, entity_data)
    print(f"[DEBUG concept_create] 新建概念: {concept_name}")
    return concept_id


def rebuild_hot_cache(base_path: str):
    """重建热概念缓存"""
    index = load_concepts_index(base_path)
    concepts = index.get("concepts", {})
    
    hot_list = []
    for cid, cdata in concepts.items():
        weight = cdata.get("activation_weight", 0)
        if weight >= 0.05:
            hot_list.append({
                "id": cid,
                "name": cdata.get("name"),
                "name_zh": cdata.get("name_zh"),
                "activation_weight": weight,
                "rank": 0
            })
    
    hot_list.sort(key=lambda x: x["activation_weight"], reverse=True)
    
    for i, c in enumerate(hot_list, 1):
        c["rank"] = i
    
    cache_data = {
        "generated_at": datetime.now().isoformat(),
        "period": "realtime",
        "concepts": hot_list[:50],
        "stats": {
            "total_hot_concepts": len(hot_list),
            "avg_activation": sum(c["activation_weight"] for c in hot_list) / len(hot_list) if hot_list else 0
        }
    }
    
    save_hot_cache(base_path, cache_data)
    print(f"[DEBUG cache_rebuild] 热缓存已更新: {len(hot_list)}个概念")


def process_new_record(base_path: str, record_id: str, record_content: str, record_type: str):
    """
    处理新记录：提取概念 → 更新索引 → 更新缓存
    """
    if not JIEBA_AVAILABLE:
        print("[WARN] jieba未安装，跳过概念提取")
        return
    
    print(f"[DEBUG process_record] 开始处理: {record_id} (类型: {record_type})")
    
    concepts = _extract_concepts_from_text(record_content, top_k=10, base_path=base_path)
    
    if not concepts:
        print(f"[DEBUG process_record] 未提取到概念")
        return
    
    print(f"[DEBUG process_record] 提取到 {len(concepts)} 个概念: {concepts[:5]}")
    
    updated_concept_ids = []
    for concept_name in concepts:
        try:
            cid = update_concept_entity(base_path, concept_name, record_id, record_type)
            updated_concept_ids.append(cid)
        except Exception as e:
            print(f"[ERROR process_record] 更新概念失败 {concept_name}: {e}")
    
    index = load_concepts_index(base_path)
    
    concepts_dir = os.path.join(base_path, "storage/entities/concepts/by_id")
    if os.path.exists(concepts_dir):
        index["concepts"] = {}
        for filename in os.listdir(concepts_dir):
            if filename.endswith('.json'):
                entity_file = os.path.join(concepts_dir, filename)
                entity_data = load_json(entity_file)
                if entity_data:
                    cid = entity_data.get("id")
                    index["concepts"][cid] = entity_data
        
        index["total"] = len(index["concepts"])
        save_concepts_index(base_path, index)
        print(f"[DEBUG process_record] 索引已更新: {index['total']}个概念")
    
    rebuild_hot_cache(base_path)
    
    print(f"[DEBUG process_record] 处理完成: {record_id}")

# ============================================================
# Phase 2.6: 笔记查询辅助函数 ⭐⭐⭐⭐⭐
# ============================================================

def list_quick_notes(base_path: str, limit: int = 10, date_filter: str = None) -> List[Dict]:
    """
    列出最近的笔记
    
    参数：
        base_path: 数据根目录
        limit: 返回数量
        date_filter: 日期过滤（如"2025-10-14"），可选
    
    返回：
        [{id, timestamp, content, tags}, ...]（按时间倒序）
    """
    quick_notes_dir = os.path.join(base_path, "storage/raw/quick_notes")
    
    if not os.path.exists(quick_notes_dir):
        return []
    
    all_notes = []
    
    # 遍历所有JSONL文件
    for filename in sorted(os.listdir(quick_notes_dir), reverse=True):
        if not filename.endswith('.jsonl'):
            continue
        
        # 日期过滤
        if date_filter and not filename.startswith(date_filter):
            continue
        
        file_path = os.path.join(quick_notes_dir, filename)
        notes_in_file = load_jsonl(file_path)
        
        # 反转（最新的在前）
        all_notes.extend(reversed(notes_in_file))
        
        # 达到限制则停止
        if len(all_notes) >= limit:
            break
    
    return all_notes[:limit]

def recall_note(base_path: str, note_id: str) -> Optional[Dict]:
    """
    通过note_id回溯笔记完整内容
    
    参数：
        base_path: 数据根目录
        note_id: 笔记ID
    
    返回：
        {id, timestamp, content, tags} 或 None
    """
    quick_notes_dir = os.path.join(base_path, "storage/raw/quick_notes")
    
    if not os.path.exists(quick_notes_dir):
        return None
    
    # 遍历所有JSONL文件
    for filename in os.listdir(quick_notes_dir):
        if not filename.endswith('.jsonl'):
            continue
        
        file_path = os.path.join(quick_notes_dir, filename)
        notes = load_jsonl(file_path)
        
        for note in notes:
            if note.get("id") == note_id:
                return note
    
    return None

def search_notes(base_path: str, query: str, limit: int = 5) -> List[Dict]:
    """
    搜索笔记内容（简单字符串匹配）
    
    参数：
        base_path: 数据根目录
        query: 搜索关键词
        limit: 返回数量
    
    返回：
        [{id, timestamp, content, tags, snippet}, ...]
    """
    quick_notes_dir = os.path.join(base_path, "storage/raw/quick_notes")
    
    if not os.path.exists(quick_notes_dir):
        return []
    
    results = []
    query_lower = query.lower()
    
    # 遍历所有JSONL文件（倒序，最新的优先）
    for filename in sorted(os.listdir(quick_notes_dir), reverse=True):
        if not filename.endswith('.jsonl'):
            continue
        
        file_path = os.path.join(quick_notes_dir, filename)
        notes = load_jsonl(file_path)
        
        for note in reversed(notes):  # 最新的在前
            content = note.get("content", "")
            
            if query_lower in content.lower():
                # 提取匹配片段（前后各50字符）
                match_pos = content.lower().find(query_lower)
                start = max(0, match_pos - 50)
                end = min(len(content), match_pos + len(query) + 50)
                snippet = content[start:end].replace("\n", " ")
                
                results.append({
                    "id": note.get("id"),
                    "timestamp": note.get("timestamp"),
                    "content": content,
                    "tags": note.get("tags", []),
                    "snippet": snippet
                })
                
                if len(results) >= limit:
                    return results
    
    return results


# ===== Phase 2.9.5 新增函数（多用户路由）=====
# 新增日期：2025-10-19
# 功能：支持多用户架构和corpus数据层

def get_user_base_path(user_id: str) -> str:
    """
    获取用户的base_path（Phase 2.9.5新增 + Phase 5.1修复）
    
    ✅ Phase 5.1修复：移除了多余的/documents层级
    
    Args:
        user_id: 用户ID（如：user_001, user_002, user_003）
    
    Returns:
        /data/users/{user_id}
    
    Examples:
        >>> get_user_base_path("user_001")
        "/data/users/user_001"
    """
    return f"/data/users/{user_id}"


def get_corpus_base_path(brain_id: str) -> str:
    """
    获取corpus的base_path（Phase 2.9.5新增）
    
    Args:
        brain_id: 大脑ID（如：brain_utopia, laozhou, CEO）
    
    Returns:
        /data/corpus/{brain_id}/documents
    
    Examples:
        >>> get_corpus_base_path("brain_utopia")
        "/data/corpus/brain_utopia/documents"
    """
    return f"/data/corpus/{brain_id}/documents"


def get_user_meta(user_id: str) -> dict:
    """
    读取用户的meta.json（Phase 2.9.5新增）
    
    Args:
        user_id: 用户ID
    
    Returns:
        meta.json的内容（字典）
    
    Raises:
        FileNotFoundError: 如果meta.json不存在
    """
    import json
    meta_path = f"/data/users/{user_id}/meta.json"
    
    with open(meta_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def get_corpus_meta(brain_id: str) -> dict:
    """
    读取corpus的meta.json（Phase 2.9.5新增）
    
    Args:
        brain_id: 大脑ID
    
    Returns:
        meta.json的内容（字典）
    
    Raises:
        FileNotFoundError: 如果meta.json不存在
    """
    import json
    meta_path = f"/data/corpus/{brain_id}/meta.json"
    
    with open(meta_path, 'r', encoding='utf-8') as f:
        return json.load(f)

# ===== Phase 2.9.5 新增函数结束 =====
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Phase 2.9.7: 多用户支持（LibreChat集成）
# Phase 5.1: 路径修复
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def ensure_user_directory(user_id: str, email: str = None, name: str = None):
    """
    确保用户目录存在（首次使用时自动创建）
    
    ✅ Phase 5.1修复：使用正确的base_path（不含/documents）
    
    Args:
        user_id: NISB用户ID
        email: 用户邮箱（可选）
        name: 用户名（可选）
    """
    base_path = get_user_base_path(user_id)

    os.makedirs(os.path.join(base_path, "agent_files"), exist_ok=True)

    meta_file = os.path.join(os.path.dirname(base_path), "meta.json")
    if os.path.exists(meta_file):
        return

    print(f"[INFO] Creating user directory: {user_id}")
    
    # Create the full user directory structure.
    dirs = [
        "agent_files",
        "storage/raw/daily",
        "storage/raw/quick_notes",
        "storage/raw/highlights",
        "storage/entities/concepts/by_id",
        "storage/entities/concepts/meta",
        "storage/entities/relations/by_type",
        "storage/kb_bookmarks",
        "storage/cases/by_date",
        "storage/cases/index",
        "storage/annotations/by_date",
        "storage/annotations/index",
        "storage/config",
        "storage/temp",
        "indexes/primary",
        "indexes/temporal",
        "cache",
        "analytics"
    ]
    
    for d in dirs:
        os.makedirs(os.path.join(base_path, d), exist_ok=True)
    
    # 创建用户meta.json
    user_meta = {
        "user_id": user_id,
        "email": email or "unknown",
        "name": name or "unknown",
        "source": "librechat" if user_id.startswith("lc_") else "manual",
        "created_at": datetime.now().isoformat(),
        "last_active": datetime.now().isoformat()
    }
    
    meta_file = os.path.join(os.path.dirname(base_path), "meta.json")
    with open(meta_file, 'w', encoding='utf-8') as f:
        json.dump(user_meta, f, ensure_ascii=False, indent=2)
    
    # 复制默认黑名单和同义词配置
    default_config = "/data/users/user_001/storage/config"  # ✅ 修复：不含/documents
    user_config = f"{base_path}/storage/config"
    
    if os.path.exists(f"{default_config}/concept_blacklist.txt"):
        import shutil
        shutil.copy(f"{default_config}/concept_blacklist.txt", f"{user_config}/concept_blacklist.txt")
        shutil.copy(f"{default_config}/concept_synonyms.txt", f"{user_config}/concept_synonyms.txt")
    
    print(f"[INFO] 用户目录创建完成: {base_path}")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Phase 3.0: Corpus Embeddings存储（新增）
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def get_corpus_embeddings_path(brain_id: str) -> str:
    """获取corpus embeddings目录路径"""
    from core.storage import get_corpus_base_path
    base_path = get_corpus_base_path(brain_id)
    embeddings_dir = f"{base_path}/storage/entities/patterns/embeddings"
    os.makedirs(embeddings_dir, exist_ok=True)
    return embeddings_dir


def save_corpus_embeddings(brain_id: str, embeddings: np.ndarray, metadata: list):
    """
    保存corpus embeddings到磁盘

    Args:
        brain_id: 大脑ID
        embeddings: (n, 768)的numpy数组
        metadata: 元数据列表（与embeddings对应）
    """
    import numpy as np
    import json

    embeddings_dir = get_corpus_embeddings_path(brain_id)

    # 保存embeddings矩阵（npy格式，高效）
    np.save(f"{embeddings_dir}/embeddings.npy", embeddings)

    # 保存元数据（json格式，可读）
    with open(f"{embeddings_dir}/metadata.json", 'w', encoding='utf-8') as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)

    print(f"✅ Corpus embeddings已保存：{len(embeddings)}个")


def load_corpus_embeddings(brain_id: str) -> tuple:
    """
    加载corpus embeddings

    Returns:
        (embeddings, metadata): embeddings矩阵和元数据列表
    """
    import numpy as np
    import json

    embeddings_dir = get_corpus_embeddings_path(brain_id)
    embeddings_file = f"{embeddings_dir}/embeddings.npy"
    metadata_file = f"{embeddings_dir}/metadata.json"

    if not os.path.exists(embeddings_file):
        return None, None

    embeddings = np.load(embeddings_file)

    with open(metadata_file, 'r', encoding='utf-8') as f:
        metadata = json.load(f)

    return embeddings, metadata

