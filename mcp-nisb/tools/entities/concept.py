#!/usr/bin/env python3
"""
概念实体管理 (4个工具)
✅ 零依赖 - 纯JSON
"""

from .base import Entity
from typing import Dict, Any
from core.user_context import auto_user_context, get_user_ctx

@auto_user_context
def nisb_concept_create(args: Dict[str, Any]) -> Dict[str, str]:
    """创建新概念实体"""
    
    name = args.get('name', '').strip()
    definition = args.get('definition', '').strip()
    source = args.get('source', 'user_input')
    tags = args.get('tags', [])
    user_id = args.get('user_id', 'default')
    base_path = args.get('_base_path', '/data')
    
    if not name:
        return {'message': '❌ 错误: 概念名称不能为空'}
    
    try:
        entity_manager = Entity('concepts', user_id, base_path)
        concept_id = Entity.generate_id(name, 'concept')
        
        # 检查是否已存在
        existing = entity_manager.load_entity(concept_id)
        if existing:
            return {'message': f'⚠️  概念已存在: {name} (ID: {concept_id})'}
        
        concept_data = {
            'name': name,
            'definition': definition,
            'source': source,
            'tags': tags if isinstance(tags, list) else [tags],
            'related_concepts': [],
            'appearance_count': 1,
            'annotations': []
        }
        
        result = entity_manager.save_entity(concept_id, concept_data)
        
        return {
            'message': f"""✅ 概念创建成功

📚 【概念】{name}
ID: {concept_id}
定义: {definition if definition else '(未设定)'}
标签: {', '.join(concept_data['tags']) if concept_data['tags'] else '无'}
存储路径: {result['path']}

💡 下一步命令：
  • nisb_concept_search(query='{name}')
  • nisb_concept_relate(concept_id='{concept_id}', related_concepts=[...])
  • nisb_concept_annotate(concept_id='{concept_id}', annotation='...')
"""
        }
    
    except Exception as e:
        return {'message': f'❌ 创建失败: {str(e)}'}

@auto_user_context
def nisb_concept_search(args: Dict[str, Any]) -> Dict[str, str]:
    """搜索概念"""
    
    query = args.get('query', '').strip()
    user_id = args.get('user_id', 'default')
    base_path = args.get('_base_path', '/data')
    limit = args.get('limit', 10)
    
    if not query:
        return {'message': '❌ 错误: 搜索词不能为空'}
    
    try:
        entity_manager = Entity('concepts', user_id, base_path)
        results = entity_manager.search_entities(query, search_fields=['name', 'definition', 'tags'])
        
        if not results:
            return {'message': f'❌ 未找到匹配 "{query}" 的概念'}
        
        display = f"🔍 搜索概念: {query}\n找到 {len(results[:limit])} 个结果\n\n"
        
        for i, concept in enumerate(results[:limit], 1):
            display += f"{i}. 【{concept.get('name')}】\n"
            display += f"   ID: {concept.get('_id')}\n"
            definition = concept.get('definition', 'N/A')
            display += f"   定义: {definition[:60] if definition else 'N/A'}{'...' if len(definition) > 60 else ''}\n"
            tags = concept.get('tags', [])
            display += f"   标签: {', '.join(tags) if tags else '无'}\n"
            display += f"   创建: {concept.get('_created', 'N/A')[:10]}\n\n"
        
        return {'message': display}
    
    except Exception as e:
        return {'message': f'❌ 搜索失败: {str(e)}'}

@auto_user_context
def nisb_concept_annotate(args: Dict[str, Any]) -> Dict[str, str]:
    """为概念添加批注"""
    
    concept_id = args.get('concept_id', '').strip()
    annotation = args.get('annotation', '').strip()
    annotation_type = args.get('annotation_type', 'note')
    user_id = args.get('user_id', 'default')
    base_path = args.get('_base_path', '/data')
    
    if not concept_id or not annotation:
        return {'message': '❌ 错误: 概念ID和批注内容不能为空'}
    
    try:
        entity_manager = Entity('concepts', user_id, base_path)
        concept = entity_manager.load_entity(concept_id)
        
        if not concept:
            return {'message': f'❌ 错误: 找不到概念 {concept_id}'}
        
        if 'annotations' not in concept:
            concept['annotations'] = []
        
        concept['annotations'].append({
            'type': annotation_type,
            'text': annotation,
            'timestamp': datetime.now().isoformat()
        })
        
        entity_manager.save_entity(concept_id, concept)
        
        return {
            'message': f"""✅ 批注添加成功

📝 概念: {concept.get('name')}
类型: {annotation_type}
内容: {annotation[:100]}{'...' if len(annotation) > 100 else ''}
总批注数: {len(concept['annotations'])}
"""
        }
    
    except Exception as e:
        return {'message': f'❌ 添加批注失败: {str(e)}'}

@auto_user_context
def nisb_concept_relate(args: Dict[str, Any]) -> Dict[str, str]:
    """关联多个概念"""
    
    concept_id = args.get('concept_id', '').strip()
    related_concepts = args.get('related_concepts', [])
    user_id = args.get('user_id', 'default')
    base_path = args.get('_base_path', '/data')
    
    if not concept_id or not related_concepts:
        return {'message': '❌ 错误: 概念ID和关联概念列表不能为空'}
    
    try:
        entity_manager = Entity('concepts', user_id, base_path)
        concept = entity_manager.load_entity(concept_id)
        
        if not concept:
            return {'message': f'❌ 错误: 找不到概念 {concept_id}'}
        
        if 'related_concepts' not in concept:
            concept['related_concepts'] = []
        
        # 去重并合并
        concept['related_concepts'].extend(related_concepts)
        concept['related_concepts'] = list(dict.fromkeys(concept['related_concepts']))
        
        entity_manager.save_entity(concept_id, concept)
        
        return {
            'message': f"""✅ 关联创建成功

🔗 主概念: {concept.get('name')} (ID: {concept_id})
新增关联: {len(related_concepts)} 个
总关联数: {len(concept['related_concepts'])} 个
关联列表: {', '.join(concept['related_concepts'][:5])}{'...' if len(concept['related_concepts']) > 5 else ''}
"""
        }
    
    except Exception as e:
        return {'message': f'❌ 创建关联失败: {str(e)}'}


# 导入datetime（用于timestamp）
from datetime import datetime

