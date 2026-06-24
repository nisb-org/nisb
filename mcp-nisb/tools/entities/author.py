#!/usr/bin/env python3
"""
作者实体管理 (2个工具)
"""

from .base import Entity
from typing import Dict, Any
from core.user_context import auto_user_context, get_user_ctx

@auto_user_context
def nisb_author_create(args: Dict[str, Any]) -> Dict[str, str]:
    """创建作者实体"""
    
    name = args.get('name', '').strip()
    nationality = args.get('nationality', '').strip()
    birth_year = args.get('birth_year', 0)
    death_year = args.get('death_year', 0)
    fields = args.get('fields', [])
    major_works = args.get('major_works', [])
    biography = args.get('biography', '').strip()
    user_id = args.get('user_id', 'default')
    base_path = args.get('_base_path', '/data')
    
    if not name:
        return {'message': '❌ 错误: 作者名称不能为空'}
    
    try:
        entity_manager = Entity('authors', user_id, base_path)
        author_id = Entity.generate_id(name, 'author')
        
        author_data = {
            'name': name,
            'nationality': nationality,
            'birth_year': birth_year,
            'death_year': death_year,
            'fields': fields if isinstance(fields, list) else [fields],
            'major_works': major_works if isinstance(major_works, list) else [major_works],
            'biography': biography,
            'books': []
        }
        
        result = entity_manager.save_entity(author_id, author_data)
        
        return {
            'message': f"""✅ 作者创建成功

✍️  【作者】{name}
国籍: {nationality if nationality else '(未知)'}
生卒: {birth_year if birth_year else '?'}-{death_year if death_year else '?'}
领域: {', '.join(author_data['fields']) if author_data['fields'] else '(未知)'}
代表作: {', '.join(author_data['major_works']) if author_data['major_works'] else '(未知)'}
ID: {author_id}
"""
        }
    
    except Exception as e:
        return {'message': f'❌ 创建失败: {str(e)}'}

@auto_user_context
def nisb_author_search(args: Dict[str, Any]) -> Dict[str, str]:
    """搜索作者"""
    
    query = args.get('query', '').strip()
    user_id = args.get('user_id', 'default')
    base_path = args.get('_base_path', '/data')
    limit = args.get('limit', 10)
    
    if not query:
        return {'message': '❌ 错误: 搜索词不能为空'}
    
    try:
        entity_manager = Entity('authors', user_id, base_path)
        results = entity_manager.search_entities(query, search_fields=['name', 'fields', 'biography'])
        
        if not results:
            return {'message': f'❌ 未找到匹配 "{query}" 的作者'}
        
        display = f"👥 搜索作者: {query}\n找到 {len(results[:limit])} 个结果\n\n"
        
        for i, author in enumerate(results[:limit], 1):
            display += f"{i}. 【{author.get('name')}】\n"
            display += f"   国籍: {author.get('nationality', 'N/A')}\n"
            display += f"   生卒: {author.get('birth_year', '?')}-{author.get('death_year', '?')}\n"
            fields = author.get('fields', [])
            display += f"   领域: {', '.join(fields) if fields else 'N/A'}\n"
            display += f"   ID: {author.get('_id')}\n\n"
        
        return {'message': display}
    
    except Exception as e:
        return {'message': f'❌ 搜索失败: {str(e)}'}

