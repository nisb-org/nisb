#!/usr/bin/env python3
"""
NISB Tools - Case Layer (案例层)
Phase 2.8版本 - 拆分query/recall到独立模块

提供功能:
  1. nisb_case_save - 保存案例（保留在本文件，核心逻辑）⭐⭐⭐
  2. nisb_case_query - 查询案例（已拆分到 tools/query/）
  3. nisb_unified_query - 三层统一查询（已拆分到 tools/query/）⭐⭐⭐
  4. nisb_case_recall - 回溯案例（已拆分到 tools/recall/）

更新日期: 2025-10-18
"""

import os
import json
import hashlib
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from collections import Counter
import sys
sys.path.insert(0, '/srv')

from core.storage import (
    ensure_directories,
    load_json,
    save_json,
    append_jsonl,
    load_jsonl,
    load_concepts_index,
    search_concepts_simple,
    load_hot_cache,
    _load_concept_blacklist,
    _apply_synonym_mapping,
    _extract_concepts_from_text
)

# ⭐⭐⭐ Phase 2.8新增：导入拆分的函数
from tools.recall.case_recall import nisb_case_recall
from tools.query.case_query import nisb_case_query
from tools.query.unified_query import nisb_unified_query

from core.user_context import auto_user_context, get_user_ctx

# 尝试导入newspaper3k
try:
    from newspaper import Article
    NEWSPAPER_AVAILABLE = True
except ImportError:
    NEWSPAPER_AVAILABLE = False
    print("[WARN] newspaper3k未安装，完整正文提取将被禁用")

# 尝试导入httpx
try:
    import httpx
    HTTPX_AVAILABLE = True
except ImportError:
    HTTPX_AVAILABLE = False
    print("[WARN] httpx未安装，Serper集成将被禁用")


# =====================================================================
# ⭐ Phase 2.8：删除以下3个函数定义（已拆分到独立模块）：
# - nisb_case_query → tools/query/case_query.py
# - nisb_unified_query → tools/query/unified_query.py ⭐⭐⭐
# - nisb_case_recall → tools/recall/case_recall.py
# =====================================================================


# =====================================================================
# Phase 2.5：内部函数（不注册为MCP工具）
# =====================================================================

def _is_english_text(text: str) -> bool:
    """检测是否为英文文本"""
    if not text:
        return False
    ascii_count = sum(1 for c in text if ord(c) < 128)
    total = len(text)
    return (ascii_count / total) > 0.7 if total > 0 else False


def _is_chinese(text: str) -> bool:
    """判断是否为中文"""
    if not text:
        return False
    chinese_count = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
    return chinese_count / len(text) > 0.5


def _internal_detect_useless_concepts(concepts: list) -> list:
    """
    自动检测无用概念（启发式规则）
    
    Phase 2.5：AI自动检测无意义词
    """
    useless = []
    
    be_verbs = {'is', 'am', 'are', 'was', 'were', 'be', 'been', 'being'}
    common_verbs = {
        'doing', 'making', 'taking', 'having', 'getting', 'going', 'coming',
        'seeing', 'knowing', 'thinking', 'looking', 'wanting', 'using',
        'finding', 'telling', 'asking', 'working', 'calling', 'trying',
        'done', 'made', 'taken', 'got', 'gone', 'seen', 'known'
    }
    generic_words = {
        'model', 'system', 'data', 'thing', 'way', 'time', 'work',
        'use', 'make', 'get', 'take', 'give', 'find', 'know'
    }
    pronouns = {
        'it', 'its', 'itself', 'themselves', 'himself', 'herself',
        'ourselves', 'yourself', 'yourselves'
    }
    chinese_particles = {'的', '了', '是', '在', '和', '与', '或', '但', '着', '过', '得'}
    
    for concept in concepts:
        concept_lower = concept.lower()
        if (concept_lower in be_verbs or 
            concept_lower in common_verbs or
            concept_lower in generic_words or
            concept_lower in pronouns or
            concept in chinese_particles):
            useless.append(concept_lower)
    
    return useless


def _internal_blacklist_add(base_path: str, words: list, auto: bool = True) -> dict:
    """
    自动添加词到黑名单（内部函数）
    
    Phase 2.5：AI自动学习
    """
    if not words:
        return {"success": False, "added_count": 0}
    
    blacklist_file = f"{base_path}/storage/config/concept_blacklist.txt"
    os.makedirs(os.path.dirname(blacklist_file), exist_ok=True)
    
    # 读取现有
    existing = set()
    if os.path.exists(blacklist_file):
        try:
            with open(blacklist_file, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        existing.add(line.lower())
        except:
            pass
    
    # 准备添加
    to_add = []
    for word in words:
        word_clean = word.strip().lower()
        if word_clean and word_clean not in existing:
            to_add.append(word_clean)
            existing.add(word_clean)
    
    # 追加
    if to_add:
        try:
            with open(blacklist_file, 'a', encoding='utf-8') as f:
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
                f.write(f"\n# AI自动优化 ({timestamp})\n")
                for word in to_add:
                    f.write(f"{word}\n")
            
            # 清除缓存
            import core.storage
            core.storage._CONCEPT_BLACKLIST = None
            
            print(f"[AI优化] 黑名单自学习：+{len(to_add)}词 {to_add}")
            return {"success": True, "added_count": len(to_add)}
        except Exception as e:
            print(f"[ERROR] 添加黑名单失败: {e}")
            return {"success": False, "added_count": 0}
    
    return {"success": True, "added_count": 0}


def _learn_synonyms_from_kb(base_path: str) -> dict:
    """
    从KB书签自动学习双语映射
    
    Phase 2.5：AI从用户KB学习
    """
    learned = {}
    bookmarks_file = f"{base_path}/storage/kb_bookmarks/bookmarks.jsonl"
    
    if not os.path.exists(bookmarks_file):
        return learned
    
    bookmarks = load_jsonl(bookmarks_file)
    
    for bm in bookmarks:
        filename = bm.get("filename", "")
        tags = bm.get("tags", [])
        
        # 提取英文词
        import re
        en_words = re.findall(r'\b[A-Z][a-z]{2,}\b', filename)
        
        # 中文tags
        zh_tags = [t for t in tags if _is_chinese(t)]
        
        # 简单配对：如果只有1个英文词和1个中文tag，很可能对应
        if len(en_words) == 1 and len(zh_tags) == 1:
            en_word = en_words[0].lower()
            zh_word = zh_tags[0]
            if en_word not in learned:
                learned[en_word] = zh_word
                print(f"[学习] {en_word} → {zh_word} (来源: {filename})")
    
    return learned


def _auto_learn_and_append_synonyms(base_path: str):
    """
    自动学习并追加到映射文件
    
    Phase 2.5：AI自动学习同义词
    """
    synonyms_file = f"{base_path}/storage/config/concept_synonyms.txt"
    learned = _learn_synonyms_from_kb(base_path)
    
    if not learned:
        return
    
    # 读取现有
    existing = set()
    if os.path.exists(synonyms_file):
        try:
            with open(synonyms_file, 'r', encoding='utf-8') as f:
                for line in f:
                    if '=' in line and not line.strip().startswith('#'):
                        en_word = line.split('=')[0].strip().lower()
                        existing.add(en_word)
        except:
            pass
    
    # 追加新映射
    new_mappings = {k: v for k, v in learned.items() if k not in existing}
    
    if new_mappings:
        try:
            with open(synonyms_file, 'a', encoding='utf-8') as f:
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
                f.write(f"\n# AI自动学习 ({timestamp})\n")
                for en, zh in new_mappings.items():
                    f.write(f"{en} = {zh}\n")
            
            print(f"[AI学习] 同义词映射自学习：+{len(new_mappings)}个")
            
            # 清除缓存
            import core.storage
            core.storage._CONCEPT_SYNONYMS = None
        except Exception as e:
            print(f"[ERROR] 自动学习失败: {e}")


# =====================================================================
# 辅助函数
# =====================================================================

def _generate_case_id() -> str:
    """生成案例ID"""
    now = datetime.now()
    random_part = hashlib.md5(str(now.timestamp()).encode()).hexdigest()[:4]
    return f"case_{now.strftime('%Y%m%d_%H%M%S')}_{random_part}"


def _parse_relative_date(date_str: str, now: datetime = None) -> str:
    """转换相对时间为ISO格式"""
    if not date_str:
        return (now or datetime.now()).isoformat() + 'Z'
    
    if not now:
        now = datetime.now()
    
    try:
        parts = date_str.lower().split()
        if len(parts) < 2:
            return now.isoformat() + 'Z'
        
        num = int(parts[0])
        unit = parts[1]
        
        if 'month' in unit:
            target = now - timedelta(days=num * 30)
        elif 'day' in unit:
            target = now - timedelta(days=num)
        elif 'hour' in unit:
            target = now - timedelta(hours=num)
        elif 'week' in unit:
            target = now - timedelta(weeks=num)
        elif 'year' in unit:
            target = now - timedelta(days=num * 365)
        else:
            return now.isoformat() + 'Z'
        
        return target.isoformat() + 'Z'
    
    except Exception as e:
        print(f"[WARN] 日期解析失败 '{date_str}': {e}")
        return now.isoformat() + 'Z'


def _fetch_full_article(url: str) -> str:
    """使用newspaper3k提取完整正文"""
    if not NEWSPAPER_AVAILABLE:
        print("[WARN] newspaper3k未安装，跳过正文提取")
        return ""
    
    try:
        article = Article(url)
        article.download()
        article.parse()
        return article.text or ""
    except Exception as e:
        print(f"[ERROR] 正文提取失败 {url}: {e}")
        return ""


def _assess_quality(title: str, snippet: str, full_text: str) -> float:
    """评估内容质量（0.0-1.0）"""
    score = 0.5
    
    text_length = len(full_text) if full_text else len(snippet)
    if text_length > 1000:
        score += 0.2
    elif text_length > 500:
        score += 0.1
    elif text_length < 100:
        score -= 0.2
    
    spam_keywords = ['buy', 'sale', 'discount', 'ads', '广告', '促销']
    if any(kw in title.lower() for kw in spam_keywords):
        score -= 0.3
    
    academic_keywords = ['research', 'study', 'analysis', '研究', '分析', '探讨']
    if any(kw in snippet.lower() for kw in academic_keywords):
        score += 0.1
    
    return max(0.0, min(1.0, score))


# =====================================================================
# 策略B：手动指定概念（优先级最高）⭐⭐⭐
# =====================================================================

def _build_manual_mappings(base_path: str, manual_concepts: list) -> Dict:
    """
    基于用户手动指定的概念，构建映射并自动关联
    
    Phase 2.5：用户主导模式（95%+质量）
    """
    print(f"[用户指定] 概念: {manual_concepts}")
    
    # 构建概念列表
    concept_list = []
    for concept_name in manual_concepts:
        concept_list.append({
            "concept_name": concept_name,
            "relevance": 1.0,
            "context": "用户手动指定"
        })
    
    # 自动查找相关书签
    related_bookmarks = []
    bookmarks_file = f"{base_path}/storage/kb_bookmarks/bookmarks.jsonl"
    if os.path.exists(bookmarks_file):
        try:
            bookmarks = load_jsonl(bookmarks_file)
            for bm in bookmarks:
                bm_tags = [str(t).lower() for t in bm.get("tags", [])]
                for concept in manual_concepts:
                    if concept.lower() in bm_tags:
                        if bm["id"] not in related_bookmarks:
                            related_bookmarks.append(bm["id"])
                            print(f"[关联] 书签 {bm['id']} ← 概念 {concept}")
                        break
        except Exception as e:
            print(f"[WARN] 查找书签失败: {e}")
    
    # 自动查找相关笔记
    related_notes = []
    notes_dir = f"{base_path}/storage/raw/quick_notes"
    if os.path.exists(notes_dir):
        try:
            for filename in os.listdir(notes_dir):
                if filename.endswith('.jsonl'):
                    notes = load_jsonl(f"{notes_dir}/{filename}")
                    for note in notes:
                        note_content = note.get("content", "").lower()
                        for concept in manual_concepts:
                            if concept.lower() in note_content:
                                if note["id"] not in related_notes:
                                    related_notes.append(note["id"])
                                    print(f"[关联] 笔记 {note['id']} ← 概念 {concept}")
                                break
        except Exception as e:
            print(f"[WARN] 查找笔记失败: {e}")
    
    return {
        "concepts": concept_list,
        "related_bookmarks": related_bookmarks,
        "related_notes": related_notes,
        "abstract_theories": []
    }


# =====================================================================
# 策略A：自动提取（优化版，85%+质量）
# =====================================================================

def _auto_map_concepts(base_path: str, title: str, content: str) -> Dict:
    """
    自动映射概念（Phase 2.5优化版：智能提取 + 黑名单过滤 + 双语映射 + 去重 + 自动关联）⭐⭐⭐
    """
    import re
    
    # 检测语言
    is_english = _is_english_text(content[:500])
    
    # ⭐⭐⭐ Phase 2.5改进：英文从内容中智能提取（带黑名单过滤）
    if is_english:
        # 加载黑名单
        blacklist = _load_concept_blacklist(base_path)
        
        # 方法1: 专有名词（首字母大写）
        proper_nouns = re.findall(r'\b[A-Z][a-z]{3,}\b', content)
        noun_counter = Counter(proper_nouns)
        
        # 方法2: 高频词（小写，长度>=5）
        common_words = re.findall(r'\b[a-z]{5,}\b', content.lower())
        word_counter = Counter(common_words)
        
        # 合并：专有名词优先，高频词补充
        concepts = []
        
        # 添加专有名词（出现>=2次，不在黑名单）
        for word, count in noun_counter.most_common(10):
            if count >= 2 and word.lower() not in blacklist:
                concepts.append(word.lower())
        
        # 添加高频词（出现>=8次，不在黑名单，不重复）
        for word, count in word_counter.most_common(15):
            if count >= 8 and word not in blacklist and word not in concepts:
                concepts.append(word)
        
        # 限制数量
        concepts = concepts[:10]
        
        print(f"[DEBUG] 英文智能提取: {concepts}")
    else:
        # 中文：jieba提取（已包含黑名单过滤）
        combined_text = f"{title} {content[:1000]}"
        concepts = _extract_concepts_from_text(combined_text, top_k=10, base_path=base_path)
    
    # ⭐ 应用双语映射并去重
    if is_english and concepts:
        concepts = _apply_synonym_mapping(concepts, base_path)
        # 去重（保持顺序）
        seen = set()
        deduped = []
        for c in concepts:
            if c not in seen:
                seen.add(c)
                deduped.append(c)
        concepts = deduped
        print(f"[DEBUG] 映射并去重后: {concepts}")
    
    # ⭐⭐⭐ 自动查找相关KB书签和笔记
    related_bookmarks = []
    related_notes = []
    
    if concepts:
        # 查找相关KB书签
        bookmarks_file = f"{base_path}/storage/kb_bookmarks/bookmarks.jsonl"
        if os.path.exists(bookmarks_file):
            try:
                bookmarks = load_jsonl(bookmarks_file)
                for bm in bookmarks:
                    bm_tags = [str(t).lower() for t in bm.get("tags", [])]
                    for concept in concepts:
                        if concept.lower() in bm_tags:
                            if bm["id"] not in related_bookmarks:
                                related_bookmarks.append(bm["id"])
                                print(f"[关联] 书签 {bm['id']} ← 概念 {concept}")
                            break
            except Exception as e:
                print(f"[WARN] 查找相关书签失败: {e}")
        
        # 查找相关笔记
        notes_dir = f"{base_path}/storage/raw/quick_notes"
        if os.path.exists(notes_dir):
            try:
                for filename in os.listdir(notes_dir):
                    if filename.endswith('.jsonl'):
                        notes = load_jsonl(f"{notes_dir}/{filename}")
                        for note in notes:
                            note_content = note.get("content", "").lower()
                            for concept in concepts:
                                if concept.lower() in note_content:
                                    if note["id"] not in related_notes:
                                        related_notes.append(note["id"])
                                        print(f"[关联] 笔记 {note['id']} ← 概念 {concept}")
                                    break
            except Exception as e:
                print(f"[WARN] 查找相关笔记失败: {e}")
    
    # 构建概念列表
    concept_list = []
    for concept_name in concepts:
        concept_list.append({
            "concept_name": concept_name,
            "relevance": 0.8,
            "context": "在标题或内容中提及"
        })
    
    return {
        "concepts": concept_list,
        "related_bookmarks": related_bookmarks,
        "related_notes": related_notes,
        "abstract_theories": []
    }


# =====================================================================
# 工具1: nisb_case_save（Phase 2.5双策略完整版）⭐⭐⭐
# 保留在本文件（核心逻辑，复杂度高，拆分收益低）
# =====================================================================

@auto_user_context
def nisb_case_save(args: dict) -> dict:
    """
    保存案例（Phase 2.5双策略完整版 + query全能语法）⭐⭐⭐
    
    Phase 6.0修复：多用户隔离
    
    策略A（自动提取85%+）:
      - 黑名单自学习
      - 同义词自学习
      - 自动关联KB书签和笔记
    
    策略B（手动指定95%+）:
      - 用户通过query参数指定：标题|概念1,概念2,概念3
      - 自动关联KB书签和笔记
      - 质量最高
    """
    
    # ✅ Phase 6.0修复：从context获取user数据
    user_ctx = get_user_ctx()
    base_path = user_ctx.base
    
    url = args.get("url", "")
    manual_concepts = args.get("concepts", [])
    
    # ⭐⭐⭐ 兼容LibreChat字符串格式（Phase 2.5 workaround）
    if isinstance(manual_concepts, str) and manual_concepts.strip():
        manual_concepts = [c.strip() for c in manual_concepts.split(",") if c.strip()]
    elif not isinstance(manual_concepts, list):
        manual_concepts = []
    
    query = args.get("query", "")
    manual_title = ""
    
    # ⭐⭐⭐ Phase 2.5 workaround：query全能模式
    if not manual_concepts and query:
        if "|" in query or "｜" in query:
            separator = "|" if "|" in query else "｜"
            parts = query.split(separator, 1)
            
            if len(parts) == 2:
                manual_title = parts[0].strip()
                concepts_str = parts[1].strip()
                manual_concepts = [c.strip() for c in concepts_str.replace("，", ",").split(",") if c.strip()]
            else:
                manual_title = query.strip()
        elif "," in query or "，" in query:
            manual_concepts = [c.strip() for c in query.replace("，", ",").split(",") if c.strip()]
        else:
            if len(query.strip()) > 0:
                manual_concepts = [query.strip()]
        
        query = ""
    
    manual_snippet = args.get("snippet", "")
    auto_map = args.get("auto_map", True)
    
    if not url.strip():
        return {
            "status": "error",
            "message": "❌ URL不能为空"
        }
    
    # 确保目录存在
    ensure_directories(base_path)
    os.makedirs(f"{base_path}/storage/cases/by_date", exist_ok=True)
    os.makedirs(f"{base_path}/storage/cases/index", exist_ok=True)
    
    # Step 1: 提取正文
    full_text = _fetch_full_article(url) if NEWSPAPER_AVAILABLE else ""
    
    # Step 2: 构建元数据
    if manual_title:
        title = manual_title[:100]
    elif full_text and len(full_text) > 50:
        text = full_text[:300]
        title = None
        for sep in ['。', '！', '？', '.', '!', '?']:
            if sep in text:
                idx = text.find(sep)
                if idx > 20:
                    title = text[:idx+1].strip()
                    break
        if not title:
            title = text[:80].strip() + "..."
    else:
        url_path = url.rstrip('/').split('/')[-1]
        url_path = url_path.split('?')[0].split('#')[0]
        if '.' in url_path and len(url_path.split('.')[-1]) < 6:
            url_path = url_path.rsplit('.', 1)[0]
        title = url_path.replace('-', ' ').replace('_', ' ')
        title = ' '.join(word.capitalize() for word in title.split())
        if len(title) > 100:
            title = title[:97] + "..."
    
    snippet = manual_snippet or full_text[:500] if full_text else ""
    
    # Step 3: 质量评估
    quality_score = _assess_quality(title, snippet, full_text)
    
    # Step 4: 概念映射（Phase 2.5双策略）
    mappings = {}
    useless_concepts = []
    
    if manual_concepts:
        # 策略B：用户手动指定
        mappings = _build_manual_mappings(base_path, manual_concepts)
        
    elif auto_map and (full_text or snippet):
        # 策略A：自动提取
        try:
            mappings = _auto_map_concepts(base_path, title, full_text or snippet)
            
            extracted_concepts = [c["concept_name"] for c in mappings.get("concepts", [])]
            useless_concepts = _internal_detect_useless_concepts(extracted_concepts)
            
            if useless_concepts:
                result = _internal_blacklist_add(base_path, useless_concepts, auto=True)
                if result["added_count"] > 0:
                    print(f"[AI优化] 黑名单自学习完成")
                
                mappings["concepts"] = [
                    c for c in mappings["concepts"] 
                    if c["concept_name"].lower() not in useless_concepts
                ]
            
            if _is_english_text(full_text or snippet):
                try:
                    _auto_learn_and_append_synonyms(base_path)
                except Exception as e:
                    print(f"[WARN] 同义词自学习失败: {e}")
        
        except Exception as e:
            print(f"[ERROR] 概念映射失败: {e}")
            mappings = {"concepts": [], "related_bookmarks": [], "related_notes": [], "abstract_theories": []}
    
    # Step 5: 生成案例数据
    case_id = _generate_case_id()
    now = datetime.now()
    
    case_data = {
        "id": case_id,
        "source_engine": "manual",
        "title": title,
        "summary": title,
        "url": url,
        "published_at": now.isoformat() + 'Z',
        "source_name": url.split('/')[2] if '/' in url else "Unknown",
        "snippet": snippet,
        "full_text": full_text,
        "mapped_concepts": mappings.get("concepts", []),
        "related_bookmarks": mappings.get("related_bookmarks", []),
        "related_notes": mappings.get("related_notes", []),
        "abstract_theories": mappings.get("abstract_theories", []),
        "quality_score": quality_score,
        "created_at": now.isoformat() + 'Z'
    }
    
    # Step 6: 保存到JSONL（按日期）
    date_str = now.strftime("%Y-%m")
    month_dir = f"{base_path}/storage/cases/by_date/{date_str}"
    os.makedirs(month_dir, exist_ok=True)
    
    cases_file = f"{month_dir}/cases_{now.strftime('%Y%m%d')}.jsonl"
    append_jsonl(cases_file, case_data)
    
    # Step 7: 更新索引
    _update_cases_index(base_path, case_data)
    
    # Step 8: 格式化输出
    optimized_count = len(useless_concepts)
    bookmark_count = len(mappings.get("related_bookmarks", []))
    note_count = len(mappings.get("related_notes", []))
    
    if manual_concepts:
        strategy_hint = "💎 用户主导模式（质量95%+）"
    else:
        strategy_hint = "💡 已自动优化概念质量并建立知识网络" if (optimized_count > 0 or bookmark_count > 0) else "💡 已自动映射到概念网络"
    
    message = f"""✅ 已保存案例：{case_id}

标题：{title[:50]}{'...' if len(title) > 50 else ''}
URL：{url}
质量评分：{quality_score:.2f}
提取概念：{len(mappings.get('concepts', []))}个
关联书签：{bookmark_count}个
关联笔记：{note_count}个
正文长度：{len(full_text)}字符

{strategy_hint}"""
    
    return {
        "status": "success",
        "case_id": case_id,
        "title": title,
        "mapped_concepts": [c["concept_name"] for c in mappings.get("concepts", [])],
        "related_bookmarks": mappings.get("related_bookmarks", []),
        "related_notes": mappings.get("related_notes", []),
        "quality_score": quality_score,
        "optimized": optimized_count > 0,
        "manual_mode": len(manual_concepts) > 0,
        "message": message
    }

def _update_cases_index(base_path: str, case_data: dict):
    """更新案例索引"""
    index_file = f"{base_path}/storage/cases/index/cases.index.json"
    
    index = load_json(index_file) or {
        "version": "1.0",
        "total": 0,
        "last_updated": datetime.now().isoformat() + 'Z',
        "cases": {}
    }
    
    case_id = case_data["id"]
    index["cases"][case_id] = {
        "id": case_id,
        "title": case_data["title"],
        "url": case_data["url"],
        "published_at": case_data["published_at"],
        "source_name": case_data["source_name"],
        "quality_score": case_data["quality_score"],
        "concepts": [c["concept_name"] for c in case_data.get("mapped_concepts", [])]
    }
    
    index["total"] = len(index["cases"])
    index["last_updated"] = datetime.now().isoformat() + 'Z'
    
    save_json(index_file, index)


