#!/usr/bin/env python3
"""
NISB Core - Schema Definitions
数据模型定义

定义NISB的核心数据结构：
- Concept（概念）
- Relation（关系）
- RawRecord（原始记录）
- Case（案例）⭐ Phase 2.5新增
- Annotation（批注）⭐ Phase 2.9新增
"""

from datetime import datetime
from typing import Dict, List, Optional, Any


class Concept:
    """概念实体"""

    def __init__(self, concept_id: str, name: str, name_zh: str, category: str):
        self.id = concept_id
        self.name = name
        self.name_zh = name_zh
        self.category = category
        self.tags = []
        self.activation_weight = 0.5
        self.last_active = datetime.now().isoformat()
        self.discussion_count = 0
        self.status = "warm"
        self.user_insights = []
        self.user_questions = []
        self.sources = []
        self.created_at = datetime.now().isoformat()
        self.updated_at = datetime.now().isoformat()

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "name": self.name,
            "name_zh": self.name_zh,
            "category": self.category,
            "tags": self.tags,
            "activation_weight": self.activation_weight,
            "last_active": self.last_active,
            "discussion_count": self.discussion_count,
            "status": self.status,
            "user_insights": self.user_insights,
            "user_questions": self.user_questions,
            "sources": self.sources,
            "created_at": self.created_at,
            "updated_at": self.updated_at
        }

    @staticmethod
    def from_dict(data: Dict) -> 'Concept':
        c = Concept(
            concept_id=data["id"],
            name=data["name"],
            name_zh=data["name_zh"],
            category=data["category"]
        )
        c.tags = data.get("tags", [])
        c.activation_weight = data.get("activation_weight", 0.5)
        c.last_active = data.get("last_active", datetime.now().isoformat())
        c.discussion_count = data.get("discussion_count", 0)
        c.status = data.get("status", "warm")
        c.user_insights = data.get("user_insights", [])
        c.user_questions = data.get("user_questions", [])
        c.sources = data.get("sources", [])
        c.created_at = data.get("created_at", datetime.now().isoformat())
        c.updated_at = data.get("updated_at", datetime.now().isoformat())
        return c


class Relation:
    """关系实体"""

    def __init__(self, from_id: str, to_id: str, relation_type: str, strength: float):
        self.from_id = from_id
        self.to_id = to_id
        self.type = relation_type
        self.strength = strength
        self.co_activation_count = 0
        self.last_activated = datetime.now().isoformat()
        self.created_at = datetime.now().isoformat()

    def to_dict(self) -> Dict:
        return {
            "from_id": self.from_id,
            "to_id": self.to_id,
            "type": self.type,
            "strength": self.strength,
            "co_activation_count": self.co_activation_count,
            "last_activated": self.last_activated,
            "created_at": self.created_at
        }

    @staticmethod
    def from_dict(data: Dict) -> 'Relation':
        r = Relation(
            from_id=data["from_id"],
            to_id=data["to_id"],
            relation_type=data["type"],
            strength=data["strength"]
        )
        r.co_activation_count = data.get("co_activation_count", 0)
        r.last_activated = data.get("last_activated", datetime.now().isoformat())
        r.created_at = data.get("created_at", datetime.now().isoformat())
        return r


class RawRecord:
    """原始记录（L1层）"""

    def __init__(self, raw_id: str, conversation: List[Dict]):
        self.id = raw_id
        self.timestamp = datetime.now().isoformat()
        self.conversation = conversation
        self.keywords = []
        self.session_context = {}
        self.processing_status = "pending"
        self.version = "1.0"

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "timestamp": self.timestamp,
            "conversation": self.conversation,
            "keywords": self.keywords,
            "session_context": self.session_context,
            "processing_status": self.processing_status,
            "version": self.version
        }

    @staticmethod
    def from_dict(data: Dict) -> 'RawRecord':
        r = RawRecord(
            raw_id=data["id"],
            conversation=data["conversation"]
        )
        r.timestamp = data.get("timestamp", datetime.now().isoformat())
        r.keywords = data.get("keywords", [])
        r.session_context = data.get("session_context", {})
        r.processing_status = data.get("processing_status", "pending")
        r.version = data.get("version", "1.0")
        return r


class Case:
    """
    案例实体（新闻/事件）
    Phase 2.5新增
    """
    
    def __init__(self, case_id: str, title: str, url: str):
        self.id = case_id
        self.title = title
        self.url = url
        self.published_at = datetime.now().isoformat() + 'Z'
        self.source_name = ""
        self.source_engine = "manual"
        self.snippet = ""
        self.full_text = ""
        self.mapped_concepts = []
        self.related_bookmarks = []
        self.abstract_theories = []
        self.quality_score = 0.5
        self.created_at = datetime.now().isoformat() + 'Z'
    
    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "title": self.title,
            "url": self.url,
            "published_at": self.published_at,
            "source_name": self.source_name,
            "source_engine": self.source_engine,
            "snippet": self.snippet,
            "full_text": self.full_text,
            "mapped_concepts": self.mapped_concepts,
            "related_bookmarks": self.related_bookmarks,
            "abstract_theories": self.abstract_theories,
            "quality_score": self.quality_score,
            "created_at": self.created_at
        }
    
    @staticmethod
    def from_dict(data: Dict) -> 'Case':
        c = Case(
            case_id=data["id"],
            title=data["title"],
            url=data["url"]
        )
        c.published_at = data.get("published_at", datetime.now().isoformat() + 'Z')
        c.source_name = data.get("source_name", "")
        c.source_engine = data.get("source_engine", "manual")
        c.snippet = data.get("snippet", "")
        c.full_text = data.get("full_text", "")
        c.mapped_concepts = data.get("mapped_concepts", [])
        c.related_bookmarks = data.get("related_bookmarks", [])
        c.abstract_theories = data.get("abstract_theories", [])
        c.quality_score = data.get("quality_score", 0.5)
        c.created_at = data.get("created_at", datetime.now().isoformat() + 'Z')
        return c


# ============ 辅助函数 ============

def generate_concept_id() -> str:
    """生成概念ID（格式：c + YYYYMMDD + NNN）"""
    now = datetime.now()
    date_str = now.strftime("%Y%m%d")
    seq = str(int(now.timestamp()))[-3:]
    return f"c{date_str}{seq}"


def generate_raw_id() -> str:
    """生成原始记录ID（格式：raw_YYYYMMDD_HHMMSS）"""
    return f"raw_{datetime.now().strftime('%Y%m%d_%H%M%S')}"


def generate_note_id() -> str:
    """生成笔记ID（格式：note_YYYYMMDD_HHMMSS）"""
    return f"note_{datetime.now().strftime('%Y%m%d_%H%M%S')}"


def generate_case_id() -> str:
    """生成案例ID（格式：case_YYYYMMDD_HHMMSS_4位随机）"""
    import hashlib
    now = datetime.now()
    random_part = hashlib.md5(str(now.timestamp()).encode()).hexdigest()[:4]
    return f"case_{now.strftime('%Y%m%d_%H%M%S')}_{random_part}"


def generate_annotation_id() -> str:
    """
    生成批注ID（格式：anno_YYYYMMDD_HHMMSS_RANDOM）
    ⭐ Phase 2.9新增
    
    示例：anno_20251019_095400_a1b2c3
    """
    import random
    import string
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    random_suffix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=6))
    
    return f"anno_{timestamp}_{random_suffix}"

