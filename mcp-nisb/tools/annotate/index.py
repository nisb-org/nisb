#!/usr/bin/env python3
"""
批注索引管理
Phase 2.9.7 多用户版本
"""

import os
import json
import sys
from core.user_context import auto_user_context, get_user_ctx
sys.path.insert(0, '/srv')


def load_index(base_path: str, index_name: str) -> dict:
    """加载索引（工具函数，不需要改）"""
    index_dir = f"{base_path}/storage/annotations/index"
    index_file = f"{index_dir}/{index_name}.json"
    
    if os.path.exists(index_file):
        try:
            with open(index_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"[ERROR] 加载索引失败: {e}", file=sys.stderr)
            return {}
    else:
        return {}


def save_index(base_path: str, index_name: str, index_data: dict):
    """保存索引（工具函数，不需要改）"""
    index_dir = f"{base_path}/storage/annotations/index"
    os.makedirs(index_dir, exist_ok=True)
    index_file = f"{index_dir}/{index_name}.json"
    
    try:
        with open(index_file, 'w', encoding='utf-8') as f:
            json.dump(index_data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[ERROR] 保存索引失败: {e}", file=sys.stderr)


def update_annotation_index(base_path: str, annotation: dict):
    """更新批注索引（工具函数，不需要改）"""
    try:
        annotation_id = annotation["annotation_id"]
        target_id = annotation["target_id"]
        mood = annotation["mood"]
        tags = annotation.get("tags", [])
        concepts = annotation.get("concepts", [])
        
        by_target = load_index(base_path, "by_target")
        by_mood = load_index(base_path, "by_mood")
        by_tag = load_index(base_path, "by_tag")
        by_concept = load_index(base_path, "by_concept")
        
        if target_id not in by_target:
            by_target[target_id] = []
        if annotation_id not in by_target[target_id]:
            by_target[target_id].append(annotation_id)
        
        if mood not in by_mood:
            by_mood[mood] = []
        if annotation_id not in by_mood[mood]:
            by_mood[mood].append(annotation_id)
        
        for tag in tags:
            if tag not in by_tag:
                by_tag[tag] = []
            if annotation_id not in by_tag[tag]:
                by_tag[tag].append(annotation_id)
        
        for concept in concepts:
            if concept not in by_concept:
                by_concept[concept] = []
            if annotation_id not in by_concept[concept]:
                by_concept[concept].append(annotation_id)
        
        save_index(base_path, "by_target", by_target)
        save_index(base_path, "by_mood", by_mood)
        save_index(base_path, "by_tag", by_tag)
        save_index(base_path, "by_concept", by_concept)
        
    except Exception as e:
        print(f"[ERROR] 更新索引失败: {e}", file=sys.stderr)

@auto_user_context
def rebuild_annotation_index(args: dict) -> dict:
    """重建批注索引（修复索引损坏或初始化）"""

    try:
        by_target = {}
        by_mood = {}
        by_tag = {}
        by_concept = {}
        total_count = 0
        deleted_count = 0
        
        anno_dir = f"{base_path}/storage/annotations/by_date"
        
        if not os.path.exists(anno_dir):
            return {
                "status": "success",
                "message": "📊 批注目录不存在，无需重建索引"
            }
        
        for year_month in sorted(os.listdir(anno_dir)):
            anno_file = f"{anno_dir}/{year_month}/annotations.jsonl"
            if os.path.exists(anno_file):
                with open(anno_file, 'r', encoding='utf-8') as f:
                    for line in f:
                        if line.strip():
                            anno = json.loads(line)
                            annotation_id = anno["annotation_id"]
                            
                            if anno.get("deleted", False):
                                deleted_count += 1
                                continue
                            
                            target_id = anno["target_id"]
                            mood = anno["mood"]
                            tags = anno.get("tags", [])
                            concepts = anno.get("concepts", [])
                            
                            if target_id not in by_target:
                                by_target[target_id] = []
                            by_target[target_id].append(annotation_id)
                            
                            if mood not in by_mood:
                                by_mood[mood] = []
                            by_mood[mood].append(annotation_id)
                            
                            for tag in tags:
                                if tag not in by_tag:
                                    by_tag[tag] = []
                                by_tag[tag].append(annotation_id)
                            
                            for concept in concepts:
                                if concept not in by_concept:
                                    by_concept[concept] = []
                                by_concept[concept].append(annotation_id)
                            
                            total_count += 1
        
        save_index(base_path, "by_target", by_target)
        save_index(base_path, "by_mood", by_mood)
        save_index(base_path, "by_tag", by_tag)
        save_index(base_path, "by_concept", by_concept)
        
        return {
            "status": "success",
            "stats": {
                "total_annotations": total_count,
                "deleted_annotations": deleted_count,
                "targets": len(by_target),
                "moods": len(by_mood),
                "tags": len(by_tag),
                "concepts": len(by_concept)
            },
            "message": f"✅ 索引重建完成\n"
                       f"   有效批注数：{total_count}\n"
                       f"   已删除批注：{deleted_count}\n"
                       f"   涉及目标：{len(by_target)}个\n"
                       f"   情绪类型：{len(by_mood)}种\n"
                       f"   标签类型：{len(by_tag)}个\n"
                       f"   概念类型：{len(by_concept)}个"
        }
        
    except Exception as e:
        import traceback
        return {
            "status": "error",
            "message": f"❌ 重建索引失败：{str(e)}\n{traceback.format_exc()}"
        }

