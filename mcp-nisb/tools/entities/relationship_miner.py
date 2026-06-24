#!/usr/bin/env python3
"""
关系挖掘引擎 (2个工具)
超轻量 - 无递归，只处理直接关系
"""

from .base import Entity
from typing import Dict, Any
from core.user_context import auto_user_context, get_user_ctx

@auto_user_context
def nisb_mine_implicit_relations(args: Dict[str, Any]) -> Dict[str, str]:
    """挖掘直接关系"""
    
    entity_id = args.get('entity_id', '').strip()
    user_id = args.get('user_id', 'default')
    base_path = args.get('_base_path', '/data')
    
    if not entity_id:
        return {'message': '❌ 错误: 实体ID不能为空'}
    
    entity_type = entity_id.split('_')[0] + 's'
    manager = Entity(entity_type, user_id, base_path)
    
    entity = manager.load_entity(entity_id)
    if not entity:
        return {'message': f'❌ 错误: 找不到实体 {entity_id}'}
    
    related_items = entity.get('related_concepts', []) or entity.get('related_books', []) or []
    
    display = f"""✅ 关系分析完成

🔍 主实体: {entity.get('name') or entity.get('title')}
直接关系: {len(related_items)} 个

📊 关联列表:
"""
    
    for i, item in enumerate(related_items[:10], 1):
        display += f"  {i}. {item}\n"
    
    if len(related_items) > 10:
        display += f"  ... 还有 {len(related_items) - 10} 个\n"
    
    return {'message': display}

@auto_user_context
def nisb_auto_link_entities(args: Dict[str, Any]) -> Dict[str, str]:
    """自动链接相似实体"""
    
    entity_id = args.get('entity_id', '').strip()
    user_id = args.get('user_id', 'default')
    base_path = args.get('_base_path', '/data')
    
    if not entity_id:
        return {'message': '❌ 错误: 实体ID不能为空'}
    
    entity_type = entity_id.split('_')[0] + 's'
    manager = Entity(entity_type, user_id, base_path)
    
    entity = manager.load_entity(entity_id)
    if not entity:
        return {'message': f'❌ 错误: 找不到实体 {entity_id}'}
    
    all_entities = manager.list_entities(limit=100)
    linked_count = 0
    
    entity_name = entity.get('name') or entity.get('title', '')
    
    for other_entity in all_entities:
        if other_entity.get('_id') == entity_id:
            continue
        
        other_name = other_entity.get('name') or other_entity.get('title', '')
        
        # 简单相似度：共同字符数
        common = len(set(entity_name) & set(other_name))
        if common > len(entity_name) * 0.3:  # 30%相似度阈值
            if 'related_concepts' not in entity:
                entity['related_concepts'] = []
            
            if other_entity.get('_id') not in entity['related_concepts']:
                entity['related_concepts'].append(other_entity.get('_id'))
                linked_count += 1
    
    manager.save_entity(entity_id, entity)
    
    display = f"""✅ 自动链接完成

🔗 主实体: {entity_name}
新增关联: {linked_count} 个
总关联数: {len(entity.get('related_concepts', []))}

💡 提示: 使用 nisb_entity_network(entity_id='{entity_id}') 查看网络
"""
    
    return {'message': display}

