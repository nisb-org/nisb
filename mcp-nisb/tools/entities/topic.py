#!/usr/bin/env python3
"""
主题实体管理 (2个工具)
"""

from .base import Entity
from typing import Dict, Any
from core.user_context import auto_user_context, get_user_ctx

@auto_user_context
def nisb_topic_create(args: Dict[str, Any]) -> Dict[str, str]:
    """创建主题实体"""
    
    name = args.get('name', '').strip()
    description = args.get('description', '').strip()
    category = args.get('category', '').strip()
    related_concepts = args.get('related_concepts', [])
    related_books = args.get('related_books', [])
    user_id = args.get('user_id', 'default')
    base_path = args.get('_base_path', '/data')
    
    if not name:
        return {'message': '❌ 错误: 主题名称不能为空'}
    
    try:
        entity_manager = Entity('topics', user_id, base_path)
        topic_id = Entity.generate_id(name, 'topic')
        
        topic_data = {
            'name': name,
            'description': description,
            'category': category,
            'related_concepts': related_concepts if isinstance(related_concepts, list) else [related_concepts],
            'related_books': related_books if isinstance(related_books, list) else [related_books],
            'subtopics': []
        }
        
        result = entity_manager.save_entity(topic_id, topic_data)
        
        return {
            'message': f"""✅ 主题创建成功

🏷️  【主题】{name}
分类: {category if category else '(未分类)'}
描述: {description[:50] if description else '(无)'}{'...' if len(description) > 50 else ''}
相关概念: {len(topic_data['related_concepts'])} 个
相关书籍: {len(topic_data['related_books'])} 个
ID: {topic_id}
"""
        }
    
    except Exception as e:
        return {'message': f'❌ 创建失败: {str(e)}'}

@auto_user_context
def nisb_topic_search(args: Dict[str, Any]) -> Dict[str, str]:
    """搜索主题"""
    
    query = args.get('query', '').strip()
    user_id = args.get('user_id', 'default')
    base_path = args.get('_base_path', '/data')
    limit = args.get('limit', 10)
    
    if not query:
        return {'message': '❌ 错误: 搜索词不能为空'}
    
    try:
        entity_manager = Entity('topics', user_id, base_path)
        results = entity_manager.search_entities(query, search_fields=['name', 'description', 'category'])
        
        if not results:
            return {'message': f'❌ 未找到匹配 "{query}" 的主题'}
        
        display = f"🔍 搜索主题: {query}\n找到 {len(results[:limit])} 个结果\n\n"
        
        for i, topic in enumerate(results[:limit], 1):
            display += f"{i}. 【{topic.get('name')}】\n"
            display += f"   分类: {topic.get('category', 'N/A')}\n"
            description = topic.get('description', 'N/A')
            display += f"   描述: {description[:40] if description else 'N/A'}{'...' if len(description) > 40 else ''}\n"
            display += f"   相关概念: {len(topic.get('related_concepts', []))} 个\n"
            display += f"   ID: {topic.get('_id')}\n\n"
        
        return {'message': display}
    
    except Exception as e:
        return {'message': f'❌ 搜索失败: {str(e)}'}

