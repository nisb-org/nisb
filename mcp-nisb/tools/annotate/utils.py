#!/usr/bin/env python3
"""
批注系统工具函数
Phase 2.9完整版：支持按日期分片的笔记文件
"""

import os
import json
import sys
sys.path.insert(0, '/srv')


def verify_target_exists(base_path: str, target_type: str, target_id: str) -> bool:
    """验证目标对象是否存在"""
    try:
        if target_type == "bookmark":
            file_path = f"{base_path}/storage/kb_bookmarks/bookmarks.jsonl"
            if not os.path.exists(file_path):
                return False
            with open(file_path, 'r', encoding='utf-8') as f:
                for line in f:
                    if line.strip():
                        item = json.loads(line)
                        if item.get("id") == target_id:
                            return True
            return False
            
        elif target_type == "case":
            # ⭐⭐⭐ 修复：正确查找案例文件
            cases_dir = f"{base_path}/storage/cases/by_date"
            if not os.path.exists(cases_dir):
                return False
            
            for date_folder in os.listdir(cases_dir):
                month_dir = f"{cases_dir}/{date_folder}"
                if os.path.isdir(month_dir):
                    # 遍历该月份下所有日期的案例文件
                    for filename in os.listdir(month_dir):
                        if filename.startswith("cases_") and filename.endswith(".jsonl"):
                            case_file = f"{month_dir}/{filename}"
                            with open(case_file, 'r', encoding='utf-8') as f:
                                for line in f:
                                    if line.strip():
                                        item = json.loads(line)
                                        if item.get("id") == target_id:
                                            return True
            return False
            
        else:  # note
            # ⭐⭐⭐ 修复：支持按日期分片的笔记文件
            notes_dir = f"{base_path}/storage/raw/quick_notes"
            if not os.path.exists(notes_dir):
                return False
            
            # 遍历所有日期文件（2025-10-17.jsonl等）
            for filename in os.listdir(notes_dir):
                if filename.endswith(".jsonl"):
                    note_file = f"{notes_dir}/{filename}"
                    with open(note_file, 'r', encoding='utf-8') as f:
                        for line in f:
                            if line.strip():
                                item = json.loads(line)
                                if item.get("id") == target_id:
                                    return True
            return False
        
    except Exception as e:
        print(f"[ERROR] verify_target_exists: {e}", file=sys.stderr)
        return False


def extract_concepts_from_target(base_path: str, target_type: str, target_id: str) -> list:
    """从目标对象自动提取概念"""
    try:
        if target_type == "bookmark":
            file_path = f"{base_path}/storage/kb_bookmarks/bookmarks.jsonl"
            if not os.path.exists(file_path):
                return []
            with open(file_path, 'r', encoding='utf-8') as f:
                for line in f:
                    if line.strip():
                        item = json.loads(line)
                        if item.get("id") == target_id:
                            return item.get("tags", []) or item.get("concepts", [])
            return []
            
        elif target_type == "case":
            # ⭐⭐⭐ 修复：正确查找案例文件
            cases_dir = f"{base_path}/storage/cases/by_date"
            if not os.path.exists(cases_dir):
                return []
            
            for date_folder in os.listdir(cases_dir):
                month_dir = f"{cases_dir}/{date_folder}"
                if os.path.isdir(month_dir):
                    for filename in os.listdir(month_dir):
                        if filename.startswith("cases_") and filename.endswith(".jsonl"):
                            case_file = f"{month_dir}/{filename}"
                            with open(case_file, 'r', encoding='utf-8') as f:
                                for line in f:
                                    if line.strip():
                                        item = json.loads(line)
                                        if item.get("id") == target_id:
                                            # 从mapped_concepts提取
                                            mapped_concepts = item.get("mapped_concepts", [])
                                            concepts = []
                                            for c in mapped_concepts:
                                                if isinstance(c, dict):
                                                    concept_name = c.get("concept_name", "")
                                                    if concept_name:
                                                        concepts.append(concept_name)
                                                else:
                                                    concepts.append(str(c))
                                            return concepts
            return []
            
        else:  # note
            # ⭐⭐⭐ 修复：支持按日期分片的笔记文件
            notes_dir = f"{base_path}/storage/raw/quick_notes"
            if not os.path.exists(notes_dir):
                return []
            
            for filename in os.listdir(notes_dir):
                if filename.endswith(".jsonl"):
                    note_file = f"{notes_dir}/{filename}"
                    with open(note_file, 'r', encoding='utf-8') as f:
                        for line in f:
                            if line.strip():
                                item = json.loads(line)
                                if item.get("id") == target_id:
                                    return item.get("tags", [])
            return []
        
    except Exception as e:
        print(f"[ERROR] extract_concepts_from_target: {e}", file=sys.stderr)
        return []


def update_target_reference(base_path: str, target_type: str, target_id: str, annotation_id: str):
    """更新目标对象的批注引用"""
    try:
        if target_type == "bookmark":
            file_path = f"{base_path}/storage/kb_bookmarks/bookmarks.jsonl"
            
        elif target_type == "case":
            # ⭐⭐⭐ 修复：正确定位案例文件
            cases_dir = f"{base_path}/storage/cases/by_date"
            file_path = None
            
            for date_folder in os.listdir(cases_dir):
                month_dir = f"{cases_dir}/{date_folder}"
                if os.path.isdir(month_dir):
                    for filename in os.listdir(month_dir):
                        if filename.startswith("cases_") and filename.endswith(".jsonl"):
                            case_file = f"{month_dir}/{filename}"
                            with open(case_file, 'r', encoding='utf-8') as f:
                                for line in f:
                                    if line.strip():
                                        item = json.loads(line)
                                        if item.get("id") == target_id:
                                            file_path = case_file
                                            break
                        if file_path:
                            break
                if file_path:
                    break
            
            if not file_path:
                print(f"[WARN] Case file not found for {target_id}", file=sys.stderr)
                return
                
        else:  # note
            # ⭐⭐⭐ 修复：支持按日期分片的笔记文件
            notes_dir = f"{base_path}/storage/raw/quick_notes"
            file_path = None
            
            # 找到包含目标笔记的文件
            for filename in os.listdir(notes_dir):
                if filename.endswith(".jsonl"):
                    note_file = f"{notes_dir}/{filename}"
                    with open(note_file, 'r', encoding='utf-8') as f:
                        for line in f:
                            if line.strip():
                                item = json.loads(line)
                                if item.get("id") == target_id:
                                    file_path = note_file
                                    break
                if file_path:
                    break
            
            if not file_path:
                print(f"[WARN] Note file not found for {target_id}", file=sys.stderr)
                return
        
        # 读取所有记录
        items = []
        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                if line.strip():
                    items.append(json.loads(line))
        
        # 更新目标对象
        for item in items:
            if item.get("id") == target_id:
                if "annotation_ids" not in item:
                    item["annotation_ids"] = []
                item["annotation_ids"].append(annotation_id)
                item["annotation_count"] = len(item["annotation_ids"])
                break
        
        # 写回文件
        with open(file_path, 'w', encoding='utf-8') as f:
            for item in items:
                f.write(json.dumps(item, ensure_ascii=False) + '\n')
                
    except Exception as e:
        print(f"[ERROR] 更新目标引用失败: {e}", file=sys.stderr)

