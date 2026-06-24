#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Staging入库处理器
处理：从staging目录批量入库L2和L4数据
"""

import os
import json
import shutil
from pathlib import Path
from .base import BaseProcessor


class StagingIngestProcessor(BaseProcessor):
    """
    Staging入库处理器
    
    功能：
    - 列出pending目录中待处理的文件
    - 支持选择性入库
    - 自动生成embeddings
    - 入库成功后移到processed目录
    """
    
    def execute(self, args: dict) -> dict:
        """执行staging入库"""
        
        brain_id = args.get("brain_id", "brain_utopia")
        
        # ========== 判断操作类型 ==========
        if args.get("list_staging"):
            return self._list_files(brain_id)
        
        elif args.get("from_staging") or args.get("staging"):
            return self._process_staging(brain_id, args)
        
        else:
            return self._list_files(brain_id)
    
    
    def _list_files(self, brain_id: str) -> dict:
        """列出待处理的文件"""
        
        pending_dir = f"/opt/nisb-data/corpus/{brain_id}/staging/pending"
        os.makedirs(pending_dir, exist_ok=True)
        
        files = {
            "l2_files": [],
            "l4_files": []
        }
        
        try:
            for filename in os.listdir(pending_dir):
                filepath = os.path.join(pending_dir, filename)
                
                if not filename.endswith('.json'):
                    continue
                
                filesize_kb = os.path.getsize(filepath) / 1024
                
                if '_l2.json' in filename:
                    ep_num = int(filename.split('_')[0].replace('ep', ''))
                    files["l2_files"].append({
                        "filename": filename,
                        "episode": ep_num,
                        "type": "L2",
                        "size_kb": round(filesize_kb, 2)
                    })
                
                elif '_l4.json' in filename:
                    ep_num = int(filename.split('_')[0].replace('ep', ''))
                    files["l4_files"].append({
                        "filename": filename,
                        "episode": ep_num,
                        "type": "L4",
                        "size_kb": round(filesize_kb, 2)
                    })
        
        except Exception as e:
            return {"status": "error", "message": f"❌ 列表失败：{e}"}
        
        total = len(files["l2_files"]) + len(files["l4_files"])
        
        if total == 0:
            return {
                "status": "success",
                "action": "list_staging",
                "message": "✅ 没有待处理文件"
            }
        
        message = f"""
【待处理文件】

L2文件：{len(files['l2_files'])}个
{chr(10).join([f"  - {f['filename']} (ep{f['episode']}, {f['size_kb']}KB)" for f in files['l2_files'][:10]])}
{"  ..." if len(files['l2_files']) > 10 else ""}

L4文件：{len(files['l4_files'])}个
{chr(10).join([f"  - {f['filename']} (ep{f['episode']}, {f['size_kb']}KB)" for f in files['l4_files'][:10]])}
{"  ..." if len(files['l4_files']) > 10 else ""}

【下一步】
运行: nisb_corpus_ingest({{
  "from_staging": true,
  "brain_id": "{brain_id}",
  "selected_files": [
    {{"filename": "ep311_l2.json", "type": "L2"}},
    {{"filename": "ep311_l4.json", "type": "L4"}}
  ],
  "auto_enrich": true
}})
"""
        
        return {
            "status": "success",
            "action": "list_staging",
            "available_files": files,
            "total_count": total,
            "message": message
        }
    
    
    def _process_staging(self, brain_id: str, args: dict) -> dict:
        """处理staging中的文件"""
        
        pending_dir = f"/opt/nisb-data/corpus/{brain_id}/staging/pending"
        processed_dir = f"/opt/nisb-data/corpus/{brain_id}/staging/processed"
        os.makedirs(processed_dir, exist_ok=True)
        
        selected_files = args.get("selected_files", [])
        auto_enrich = args.get("auto_enrich", True)
        
        if not selected_files:
            return {"status": "error", "message": "❌ 未选择任何文件"}
        
        results = {
            "processed": [],
            "failed": [],
            "total": len(selected_files)
        }
        
        # ========== 处理每个文件 ==========
        for file_info in selected_files:
            filename = file_info.get("filename")
            file_type = file_info.get("type")  # "L2" or "L4"
            
            try:
                source_file = os.path.join(pending_dir, filename)
                
                if not os.path.exists(source_file):
                    results["failed"].append({
                        "file": filename,
                        "reason": "文件不存在"
                    })
                    continue
                
                # 读取和验证JSON
                with open(source_file, 'r', encoding='utf-8', errors='ignore') as f:
                    data = json.load(f)
                
                # 确定目标目录
                if file_type == "L2":
                    dest_dir = f"/opt/nisb-data/corpus/{brain_id}/storage/entities/patterns/by_id"
                    # 改名为标准格式
                    ep_num = int(filename.split('_')[0].replace('ep', ''))
                    dest_filename = f"pattern_ep{ep_num:03d}.json"
                else:  # L4
                    dest_dir = f"/opt/nisb-data/corpus/{brain_id}/storage/entities/l4_methods/by_episode"
                    dest_filename = filename
                
                os.makedirs(dest_dir, exist_ok=True)
                dest_file = os.path.join(dest_dir, dest_filename)
                
                # 复制文件
                shutil.copy(source_file, dest_file)
                
                results["processed"].append({
                    "file": filename,
                    "type": file_type,
                    "destination": dest_file,
                    "status": "✅ 成功"
                })
                
                # 移到processed目录
                shutil.move(source_file, os.path.join(processed_dir, filename))
            
            except Exception as e:
                results["failed"].append({
                    "file": filename,
                    "reason": str(e)[:100]
                })
        
        # ========== 生成embeddings ==========
        if auto_enrich and len(results["processed"]) > 0:
            try:
                from tools.corpus.embeddings_handler import generate_all_embeddings
                emb_result = generate_all_embeddings(brain_id)
                results["embeddings"] = emb_result
            except Exception as e:
                results["embeddings_error"] = str(e)
        
        # ========== 返回结果 ==========
        return {
            "status": "success" if len(results["failed"]) == 0 else "partial_success",
            "action": "process_staging",
            "results": results,
            "summary": f"✅ {len(results['processed'])}个成功 | ❌ {len(results['failed'])}个失败",
            "message": (
                f"处理完成\n"
                f"  成功：{len(results['processed'])}个\n"
                f"  失败：{len(results['failed'])}个\n"
                f"  Embeddings：{'已生成' if auto_enrich else '跳过'}"
            )
        }

