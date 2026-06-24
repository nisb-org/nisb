#!/usr/bin/env python3
"""
批注添加功能（独立式架构）
Phase 2.9.7 多用户版本
Phase 3.8 修复：支持bookmark_id和annotation参数（向后兼容）
Phase 6.0 修复：多用户隔离完善
"""

from datetime import datetime
import os
import json
import sys
sys.path.insert(0, '/srv')

from core.schema import generate_annotation_id
from core.user_context import auto_user_context, get_user_ctx

@auto_user_context
def nisb_annotate(args: dict) -> dict:
    """为KB书签/案例/笔记添加批注（智能版本）"""
    
    # ✅ Phase 6.0修复：从context获取user数据
    user_ctx = get_user_ctx()
    base_path = user_ctx.base
   
    # ⭐⭐⭐ 修复：兼容多种参数名（bookmark_id/target_id, annotation/content）
    target_id = args.get("target_id") or args.get("bookmark_id", "")
    content = args.get("content") or args.get("annotation", "")
    
    if not target_id or not content:
        return {"status": "error", "message": "❌ target_id/bookmark_id和content/annotation不能为空"}
    
    MAX_LENGTH = 2000
    if len(content) > MAX_LENGTH:
        return {
            "status": "error",
            "message": f"❌ 批注过长（{len(content)}字符），请控制在{MAX_LENGTH}字符内"
        }
    
    try:
        target_type = args.get("target_type", None)
        if not target_type:
            target_type = _infer_target_type(target_id)
            if not target_type:
                return {"status": "error", "message": f"❌ 无法识别目标类型：{target_id}"}
        
        if target_type not in ["bookmark", "case", "note"]:
            return {"status": "error", "message": "❌ target_type必须是bookmark/case/note"}
        
        from .utils import verify_target_exists, extract_concepts_from_target
        
        if not verify_target_exists(base_path, target_type, target_id):
            return {"status": "error", "message": f"❌ 目标不存在：{target_id}"}
        
        mood = args.get("mood", None)
        if not mood:
            mood = _extract_mood_from_content(content)
        
        concepts = args.get("concepts", None)
        if not concepts:
            target_concepts = extract_concepts_from_target(base_path, target_type, target_id)
            content_concepts = _extract_concepts_from_content(content)
            concepts = list(set(target_concepts + content_concepts))[:5]
        
        tags = args.get("tags", None)
        if not tags:
            tags = _auto_generate_tags(content, concepts)
        
        context = args.get("context", "")
        
        annotation_id = generate_annotation_id()
        annotation = {
            "annotation_id": annotation_id,
            "timestamp": datetime.now().isoformat(),
            "target_type": target_type,
            "target_id": target_id,
            "content": content,
            "mood": mood,
            "tags": tags,
            "context": context,
            "concepts": concepts,
            "meta_annotations": [],
            "edit_history": []
        }
        
        year_month = datetime.now().strftime("%Y-%m")
        anno_dir = f"{base_path}/storage/annotations/by_date/{year_month}"
        os.makedirs(anno_dir, exist_ok=True)
        anno_file = f"{anno_dir}/annotations.jsonl"
        
        with open(anno_file, 'a', encoding='utf-8') as f:
            f.write(json.dumps(annotation, ensure_ascii=False) + '\n')
        
        from .utils import update_target_reference
        update_target_reference(base_path, target_type, target_id, annotation_id)
        
        from .index import update_annotation_index
        update_annotation_index(base_path, annotation)
        
        concepts_str = ", ".join(concepts) if concepts else "无"
        tags_str = ", ".join(tags) if tags else "无"
        
        auto_notes = []
        if not args.get("target_type"):
            auto_notes.append(f"类型（自动）：{target_type}")
        if not args.get("mood"):
            auto_notes.append(f"情绪（自动）：{mood}")
        if not args.get("concepts"):
            auto_notes.append(f"概念（自动）：{concepts_str}")
        if not args.get("tags"):
            auto_notes.append(f"标签（自动）：{tags_str}")
        
        message = f"✅ 已添加批注\n" \
                  f"   目标：{target_id}\n" \
                  f"   内容：{content[:50]}{'...' if len(content) > 50 else ''}\n" \
                  f"   情绪：{mood}\n" \
                  f"   关联概念：{concepts_str}\n" \
                  f"   批注ID：{annotation_id}"
        
        if auto_notes:
            message += f"\n\n   🤖 AI自动补全：\n   " + "\n   ".join(auto_notes)
        
        return {
            "status": "success",
            "annotation_id": annotation_id,
            "timestamp": annotation["timestamp"],
            "target_type": target_type,
            "target_id": target_id,
            "mood": mood,
            "concepts": concepts,
            "tags": tags,
            "auto_generated": auto_notes,
            "message": message
        }
        
    except Exception as e:
        import traceback
        return {
            "status": "error",
            "message": f"❌ 添加批注失败：{str(e)}\n{traceback.format_exc()}"
        }


def _infer_target_type(target_id: str) -> str:
    """从target_id推断类型"""
    if target_id.startswith("bookmark_"):
        return "bookmark"
    elif target_id.startswith("case_"):
        return "case"
    elif target_id.startswith("note_"):
        return "note"
    else:
        return None


def _extract_mood_from_content(content: str) -> str:
    """从内容提取情绪"""
    content_lower = content.lower()
    
    mood_keywords = {
        "担忧": ["担心", "担忧", "忧虑", "焦虑", "害怕", "恐惧", "不安"],
        "质疑": ["质疑", "怀疑", "不确定", "真的吗", "吗？", "可疑"],
        "顿悟": ["原来", "理解了", "明白了", "恍然大悟", "突然懂了", "豁然开朗"],
        "困惑": ["困惑", "不懂", "疑惑", "为什么", "？？", "不理解"],
        "兴奋": ["激动", "兴奋", "太棒了", "厉害", "！！", "amazing", "great", "棒"],
        "高兴": ["高兴", "开心", "愉快", "快乐", "😊", "哈哈"],
        "新洞察": ["发现", "新的", "洞察", "原创", "首次", "意外"],
        "验证": ["验证", "证实", "果然", "确实", "没错", "正确"],
        "预测": ["预测", "将来", "未来", "可能", "会", "大概"]
    }
    
    for mood, keywords in mood_keywords.items():
        for keyword in keywords:
            if keyword in content_lower:
                return mood
    
    return "中性"


def _extract_concepts_from_content(content: str) -> list:
    """从内容提取概念"""
    common_concepts = [
        "认知", "AI", "偏差", "康德", "胡塞尔", "意识", "现象学",
        "先验", "NISB", "个人AGI", "认知暴政", "元认知", "批判性思维",
        "自我", "存在", "本真性", "涌现", "长期主义", "开源",
        "萨特", "海德格尔", "笛卡尔", "柏拉图", "亚里士多德",
        "自由", "真理", "知识", "信念", "理性", "感性",
        "哲学", "心理学", "神经科学", "佛学", "禅宗"
    ]
    
    concepts = []
    for concept in common_concepts:
        if concept in content:
            concepts.append(concept)
    
    return concepts[:3]


def _auto_generate_tags(content: str, concepts: list) -> list:
    """自动生成标签"""
    tags = []
    
    tags.extend(concepts[:2])
    
    keywords = ["Nature", "论文", "研究", "预测", "发现", "思考", "分析", "工程", "进度"]
    for kw in keywords:
        if kw in content:
            tags.append(kw)
    
    return list(set(tags))[:3]

