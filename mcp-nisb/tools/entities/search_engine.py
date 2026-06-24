#!/usr/bin/env python3
"""
实体搜索引擎 (3个工具)
轻量化版本 - 零依赖
"""

from .base import Entity
from typing import Dict, Any
from core.user_context import auto_user_context, get_user_ctx

@auto_user_context
def nisb_entity_search(args: Dict[str, Any]) -> Dict[str, str]:
    """统一实体搜索（跨所有实体类型）"""
    
    query = args.get('query', '').strip()
    user_id = args.get('user_id', 'default')
    base_path = args.get('_base_path', '/data')
    limit = args.get('limit', 5)
    
    if not query:
        return {'message': '❌ 错误: 搜索词不能为空'}
    
    entity_types = ['concepts', 'books', 'authors', 'topics']
    results = {}
    total = 0
    
    for entity_type in entity_types:
        try:
            manager = Entity(entity_type, user_id, base_path)
            entities = manager.search_entities(query)
            if entities:
                results[entity_type] = entities[:limit]
                total += len(entities[:limit])
        except:
            pass
    
    if not results:
        return {'message': f'❌ 未找到与 "{query}" 相关的任何实体'}
    
    display = f"🔍 统一实体搜索: {query}\n\n"
    
    for entity_type, entities in results.items():
        display += f"{'='*50}\n"
        display += f"📂 {entity_type.upper()} ({len(entities)} 个)\n"
        display += f"{'='*50}\n"
        
        for i, entity in enumerate(entities[:limit], 1):
            name = entity.get('name') or entity.get('title', 'N/A')
            entity_id = entity.get('_id', 'N/A')
            display += f"  {i}. {name} (ID: {entity_id})\n"
        
        display += "\n"
    
    display += f"总计: {total} 个结果"
    
    return {'message': display}

@auto_user_context
def nisb_entity_network(args: Dict[str, Any]) -> Dict[str, str]:
    """生成实体关系网络图"""
    
    entity_id = args.get('entity_id', '').strip()
    user_id = args.get('user_id', 'default')
    base_path = args.get('_base_path', '/data')
    
    if not entity_id:
        return {'message': '❌ 错误: 实体ID不能为空'}
    
    # 推断实体类型
    entity_type = entity_id.split('_')[0] + 's'
    
    try:
        manager = Entity(entity_type, user_id, base_path)
    except:
        return {'message': f'❌ 错误: 无法识别实体类型'}
    
    entity = manager.load_entity(entity_id)
    if not entity:
        return {'message': f'❌ 错误: 找不到实体 {entity_id}'}
    
    # 构建网络数据（Cytoscape格式）
    nodes = [entity_id]
    edges = []
    
    related_items = entity.get('related_concepts', []) or entity.get('related_books', []) or []
    
    for related_id in related_items[:10]:
        nodes.append(related_id)
        edges.append({'source': entity_id, 'target': related_id})
    
    display = f"""✅ 关系网络生成成功

📊 网络统计:
   中心实体: {entity.get('name') or entity.get('title')}
   节点数: {len(nodes)}
   边数: {len(edges)}
   
🔗 关联项目:
"""
    
    for item in related_items[:10]:
        display += f"   • {item}\n"
    
    display += f"\n💡 提示: 这个网络数据可用于Gephi或D3.js可视化"
    
    return {'message': display}

@auto_user_context
def nisb_entity_search_personalized(args: Dict[str, Any]) -> Dict[str, str]:
    """个性化搜索（简化版 - 基于常用类型）"""
    
    query = args.get('query', '').strip()
    user_id = args.get('user_id', 'default')
    base_path = args.get('_base_path', '/data')
    
    if not query:
        return {'message': '❌ 错误: 搜索词不能为空'}
    
    # 默认优先搜索：概念 > 书籍 > 主题 > 作者
    preferred_order = ['concepts', 'books', 'topics', 'authors']
    
    display = f"🎯 个性化搜索: {query}\n\n"
    found = False
    
    for entity_type in preferred_order:
        try:
            manager = Entity(entity_type, user_id, base_path)
            entities = manager.search_entities(query)
            
            if entities:
                found = True
                display += f"📂 {entity_type.upper()}: {len(entities)} 个结果\n"
                for entity in entities[:3]:
                    name = entity.get('name') or entity.get('title')
                    display += f"   • {name}\n"
                display += "\n"
        except:
            pass
    
    if not found:
        return {'message': f'❌ 未找到与 "{query}" 相关的内容'}
    
    return {'message': display}

