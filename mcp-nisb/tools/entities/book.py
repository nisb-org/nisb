#!/usr/bin/env python3
"""
书籍实体管理 (2个工具)
"""

from .base import Entity
from typing import Dict, Any
from core.user_context import auto_user_context, get_user_ctx

@auto_user_context
def nisb_book_create(args: Dict[str, Any]) -> Dict[str, str]:
    """创建书籍实体"""
    
    title = args.get('title', '').strip()
    author = args.get('author', '').strip()
    publisher = args.get('publisher', '').strip()
    year = args.get('year', 0)
    isbn = args.get('isbn', '').strip()
    description = args.get('description', '').strip()
    tags = args.get('tags', [])
    user_id = args.get('user_id', 'default')
    base_path = args.get('_base_path', '/data')
    
    if not title or not author:
        return {'message': '❌ 错误: 书籍标题和作者不能为空'}
    
    try:
        entity_manager = Entity('books', user_id, base_path)
        book_id = Entity.generate_id(f"{title}_{author}", 'book')
        
        book_data = {
            'title': title,
            'author': author,
            'publisher': publisher,
            'year': year,
            'isbn': isbn,
            'description': description,
            'tags': tags if isinstance(tags, list) else [tags],
            'key_concepts': [],
            'read_progress': 0
        }
        
        result = entity_manager.save_entity(book_id, book_data)
        
        return {
            'message': f"""✅ 书籍创建成功

📖 【书籍】{title}
作者: {author}
出版社: {publisher if publisher else '(未知)'}
年份: {year if year else '(未知)'}
ISBN: {isbn if isbn else '(未知)'}
ID: {book_id}
存储路径: {result['path']}
"""
        }
    
    except Exception as e:
        return {'message': f'❌ 创建失败: {str(e)}'}

@auto_user_context
def nisb_book_search(args: Dict[str, Any]) -> Dict[str, str]:
    """搜索书籍"""
    
    query = args.get('query', '').strip()
    user_id = args.get('user_id', 'default')
    base_path = args.get('_base_path', '/data')
    limit = args.get('limit', 10)
    
    if not query:
        return {'message': '❌ 错误: 搜索词不能为空'}
    
    try:
        entity_manager = Entity('books', user_id, base_path)
        results = entity_manager.search_entities(query, search_fields=['title', 'author', 'description'])
        
        if not results:
            return {'message': f'❌ 未找到匹配 "{query}" 的书籍'}
        
        display = f"📚 搜索书籍: {query}\n找到 {len(results[:limit])} 个结果\n\n"
        
        for i, book in enumerate(results[:limit], 1):
            display += f"{i}. 【{book.get('title')}】\n"
            display += f"   作者: {book.get('author')}\n"
            display += f"   出版: {book.get('publisher', 'N/A')} ({book.get('year', 'N/A')})\n"
            display += f"   ISBN: {book.get('isbn', 'N/A')}\n"
            display += f"   ID: {book.get('_id')}\n\n"
        
        return {'message': display}
    
    except Exception as e:
        return {'message': f'❌ 搜索失败: {str(e)}'}

