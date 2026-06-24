#!/usr/bin/env python3
"""
批注编辑功能（修改、删除、元批注）
Phase 2.9.7 多用户版本
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
def nisb_edit_annotation(args: dict) -> dict:
    """修改批注（保留修改历史）"""
    
    # ✅ Phase 6.0修复：从context获取user数据
    user_ctx = get_user_ctx()
    base_path = user_ctx.base
    user_id = user_ctx.user_id
    
    annotation_id = args.get("annotation_id", "")
    new_content = args.get("new_content", None)
    new_mood = args.get("new_mood", None)
    new_tags = args.get("new_tags", None)
    new_concepts = args.get("new_concepts", None)
    
    if not annotation_id:
        return {"status": "error", "message": "❌ 必须指定annotation_id"}
    
    if not any([new_content, new_mood, new_tags, new_concepts]):
        return {"status": "error", "message": "❌ 至少需要修改一个字段"}
    
    try:
        anno_dir = f"{base_path}/storage/annotations/by_date"
        target_file = None
        target_line_idx = -1
        all_annotations = []
        
        for year_month in os.listdir(anno_dir):
            anno_file = f"{anno_dir}/{year_month}/annotations.jsonl"
            if os.path.exists(anno_file):
                with open(anno_file, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                    for idx, line in enumerate(lines):
                        if line.strip():
                            anno = json.loads(line)
                            if anno["annotation_id"] == annotation_id:
                                target_file = anno_file
                                target_line_idx = idx
                                all_annotations = [json.loads(l) for l in lines if l.strip()]
                                break
                if target_file:
                    break
        
        if not target_file:
            return {"status": "error", "message": f"❌ 未找到批注：{annotation_id}"}
        
        original_anno = all_annotations[target_line_idx]
        
        edit_record = {
            "edit_timestamp": datetime.now().isoformat(),
            "old_content": original_anno.get("content", ""),
            "old_mood": original_anno.get("mood", ""),
            "old_tags": original_anno.get("tags", []),
            "old_concepts": original_anno.get("concepts", [])
        }
        
        if "edit_history" not in original_anno:
            original_anno["edit_history"] = []
        
        original_anno["edit_history"].append(edit_record)
        
        changes = []
        if new_content is not None:
            original_anno["content"] = new_content
            changes.append(f"内容")
        if new_mood is not None:
            original_anno["mood"] = new_mood
            changes.append(f"情绪")
        if new_tags is not None:
            original_anno["tags"] = new_tags
            changes.append(f"标签")
        if new_concepts is not None:
            original_anno["concepts"] = new_concepts
            changes.append(f"概念")
        
        original_anno["last_edited"] = datetime.now().isoformat()
        
        all_annotations[target_line_idx] = original_anno
        
        with open(target_file, 'w', encoding='utf-8') as f:
            for anno in all_annotations:
                f.write(json.dumps(anno, ensure_ascii=False) + '\n')
        
        if new_concepts is not None:
            from .index import rebuild_annotation_index
            rebuild_annotation_index({"user_id": user_id, "_librechat_email": args.get("_librechat_email"), "_librechat_name": args.get("_librechat_name")})
        
        return {
            "status": "success",
            "annotation_id": annotation_id,
            "changes": changes,
            "edit_count": len(original_anno["edit_history"]),
            "message": f"✅ 已修改批注\n"
                       f"   批注ID：{annotation_id}\n"
                       f"   修改内容：{', '.join(changes)}\n"
                       f"   这是第{len(original_anno['edit_history'])}次修改\n"
                       f"   修改历史已保存"
        }
        
    except Exception as e:
        import traceback
        return {
            "status": "error",
            "message": f"❌ 修改失败：{str(e)}\n{traceback.format_exc()}"
        }

@auto_user_context
def nisb_delete_annotation(args: dict) -> dict:
    """删除批注（软删除，标记为已删除）"""
    
    # ✅ Phase 6.0修复：从context获取user数据
    user_ctx = get_user_ctx()
    base_path = user_ctx.base
    user_id = user_ctx.user_id
    
    annotation_id = args.get("annotation_id", "")
    reason = args.get("reason", "用户删除")
    
    if not annotation_id:
        return {"status": "error", "message": "❌ 必须指定annotation_id"}
    
    try:
        anno_dir = f"{base_path}/storage/annotations/by_date"
        target_file = None
        target_line_idx = -1
        all_annotations = []
        
        for year_month in os.listdir(anno_dir):
            anno_file = f"{anno_dir}/{year_month}/annotations.jsonl"
            if os.path.exists(anno_file):
                with open(anno_file, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                    for idx, line in enumerate(lines):
                        if line.strip():
                            anno = json.loads(line)
                            if anno["annotation_id"] == annotation_id:
                                target_file = anno_file
                                target_line_idx = idx
                                all_annotations = [json.loads(l) for l in lines if l.strip()]
                                break
                if target_file:
                    break
        
        if not target_file:
            return {"status": "error", "message": f"❌ 未找到批注：{annotation_id}"}
        
        original_anno = all_annotations[target_line_idx]
        original_anno["deleted"] = True
        original_anno["deleted_at"] = datetime.now().isoformat()
        original_anno["delete_reason"] = reason
        
        all_annotations[target_line_idx] = original_anno
        
        with open(target_file, 'w', encoding='utf-8') as f:
            for anno in all_annotations:
                f.write(json.dumps(anno, ensure_ascii=False) + '\n')
        
        from .index import rebuild_annotation_index
        rebuild_annotation_index({"user_id": user_id, "_librechat_email": args.get("_librechat_email"), "_librechat_name": args.get("_librechat_name")})
        
        return {
            "status": "success",
            "annotation_id": annotation_id,
            "message": f"✅ 已删除批注\n"
                       f"   批注ID：{annotation_id}\n"
                       f"   删除原因：{reason}\n"
                       f"   （软删除，数据仍保留，可恢复）"
        }
        
    except Exception as e:
        import traceback
        return {
            "status": "error",
            "message": f"❌ 删除失败：{str(e)}\n{traceback.format_exc()}"
        }

@auto_user_context
def nisb_annotate_annotation(args: dict) -> dict:
    """为批注添加元批注（批注的批注）"""
    
    # ✅ Phase 6.0修复：从context获取user数据
    user_ctx = get_user_ctx()
    base_path = user_ctx.base
       
    annotation_id = args.get("annotation_id", "")
    content = args.get("content", "")
    mood = args.get("mood", "自我反思")
    tags = args.get("tags", [])
    
    if not annotation_id or not content:
        return {"status": "error", "message": "❌ annotation_id和content不能为空"}
    
    try:
        anno_dir = f"{base_path}/storage/annotations/by_date"
        target_file = None
        target_line_idx = -1
        all_annotations = []
        
        for year_month in os.listdir(anno_dir):
            anno_file = f"{anno_dir}/{year_month}/annotations.jsonl"
            if os.path.exists(anno_file):
                with open(anno_file, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                    for idx, line in enumerate(lines):
                        if line.strip():
                            anno = json.loads(line)
                            if anno["annotation_id"] == annotation_id:
                                target_file = anno_file
                                target_line_idx = idx
                                all_annotations = [json.loads(l) for l in lines if l.strip()]
                                break
                if target_file:
                    break
        
        if not target_file:
            return {"status": "error", "message": f"❌ 未找到原批注：{annotation_id}"}
        
        meta_anno_id = f"meta_{generate_annotation_id()}"
        meta_annotation = {
            "meta_annotation_id": meta_anno_id,
            "timestamp": datetime.now().isoformat(),
            "content": content,
            "mood": mood,
            "tags": tags
        }
        
        original_anno = all_annotations[target_line_idx]
        if "meta_annotations" not in original_anno:
            original_anno["meta_annotations"] = []
        
        original_anno["meta_annotations"].append(meta_annotation)
        
        all_annotations[target_line_idx] = original_anno
        
        with open(target_file, 'w', encoding='utf-8') as f:
            for anno in all_annotations:
                f.write(json.dumps(anno, ensure_ascii=False) + '\n')
        
        from datetime import datetime as dt
        original_time = dt.fromisoformat(original_anno["timestamp"])
        meta_time = dt.fromisoformat(meta_annotation["timestamp"])
        days_diff = (meta_time - original_time).days
        
        if days_diff < 30:
            time_span = f"{days_diff}天"
        elif days_diff < 365:
            time_span = f"{days_diff // 30}个月"
        else:
            time_span = f"{days_diff // 365}年{(days_diff % 365) // 30}个月"
        
        return {
            "status": "success",
            "meta_annotation_id": meta_anno_id,
            "original_annotation_id": annotation_id,
            "time_span": time_span,
            "message": f"✅ 已添加元批注\n"
                       f"   原批注：{annotation_id}\n"
                       f"   元批注ID：{meta_anno_id}\n"
                       f"   时间跨度：{time_span}后\n"
                       f"   内容：{content[:50]}{'...' if len(content) > 50 else ''}"
        }
        
    except Exception as e:
        import traceback
        return {
            "status": "error",
            "message": f"❌ 添加元批注失败：{str(e)}\n{traceback.format_exc()}"
        }

