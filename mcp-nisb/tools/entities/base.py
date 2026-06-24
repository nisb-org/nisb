#!/usr/bin/env python3
"""
实体管理基础类 - 轻量化版本
✅ 零外部依赖（仅使用Python标准库）
✅ 纯JSON存储
"""

import json
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional


class Entity:
    """基础实体类 - 极简设计"""
    
    def __init__(self, entity_type: str, user_id: str, base_path: str = "/data"):
        self.entity_type = entity_type  # concept, book, author, topic
        self.user_id = user_id
        self.base_path = Path(base_path)
        self.storage_path = self.base_path / "users" / user_id / "documents" / "storage" / "entities" / entity_type
        
        # 创建存储目录
        self.storage_path.mkdir(parents=True, exist_ok=True)
    
    @staticmethod
    def generate_id(name: str, entity_type: str) -> str:
        """生成实体ID（基于名称哈希，8个字符）"""
        hash_obj = hashlib.md5(f"{entity_type}_{name}".encode())
        return f"{entity_type}_{hash_obj.hexdigest()[:8]}"
    
    def save_entity(self, entity_id: str, data: Dict[str, Any], subdirs: List[str] = None) -> Dict:
        """保存实体到JSON文件"""
        if subdirs:
            path = self.storage_path.joinpath(*subdirs)
        else:
            path = self.storage_path / "by_id"
        
        path.mkdir(parents=True, exist_ok=True)
        file_path = path / f"{entity_id}.json"
        
        # 添加元数据
        data['_id'] = entity_id
        data['_created'] = data.get('_created', datetime.now().isoformat())
        data['_updated'] = datetime.now().isoformat()
        data['_type'] = self.entity_type.rstrip('s')  # concepts → concept
        
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        return {
            'id': entity_id,
            'path': str(file_path),
            'created': data['_created']
        }
    
    def load_entity(self, entity_id: str, subdirs: List[str] = None) -> Optional[Dict]:
        """加载实体"""
        if subdirs:
            file_path = self.storage_path.joinpath(*subdirs) / f"{entity_id}.json"
        else:
            file_path = self.storage_path / "by_id" / f"{entity_id}.json"
        
        if not file_path.exists():
            return None
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return None
    
    def list_entities(self, subdirs: List[str] = None, limit: int = 50) -> List[Dict]:
        """列表实体"""
        if subdirs:
            path = self.storage_path.joinpath(*subdirs)
        else:
            path = self.storage_path / "by_id"
        
        if not path.exists():
            return []
        
        entities = []
        try:
            for file_path in sorted(path.glob("*.json"))[:limit]:
                with open(file_path, 'r', encoding='utf-8') as f:
                    entities.append(json.load(f))
        except:
            pass
        
        return entities
    
    def search_entities(self, query: str, search_fields: List[str] = None) -> List[Dict]:
        """搜索实体（全文搜索）"""
        if not search_fields:
            search_fields = ['name', 'title', 'definition']
        
        results = []
        query_lower = query.lower()
        
        for entity in self.list_entities(limit=1000):
            for field in search_fields:
                if field in entity:
                    field_value = str(entity[field]).lower()
                    if query_lower in field_value:
                        results.append(entity)
                        break
        
        return results
    
    def delete_entity(self, entity_id: str, subdirs: List[str] = None) -> bool:
        """删除实体"""
        if subdirs:
            file_path = self.storage_path.joinpath(*subdirs) / f"{entity_id}.json"
        else:
            file_path = self.storage_path / "by_id" / f"{entity_id}.json"
        
        try:
            if file_path.exists():
                file_path.unlink()
                return True
        except:
            pass
        
        return False

