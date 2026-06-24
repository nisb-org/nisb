#!/usr/bin/env python3
"""
路径识别和解析 - 统一处理旧路径和新路径
Phase 7.0 核心组件【修复】路径冗余
"""
import os
import json
from enum import Enum
from typing import Dict, Tuple, List, Optional

class StorageMode(Enum):
    """存储模式枚举"""
    LEGACY = "legacy"      # 旧路径：/documents/storage/doc_*
    LIBRARY = "library"    # 新路径：/libraries/{lib_id}/docs/doc_*
    UNKNOWN = "unknown"

class PathResolver:
    """路径解析器 - 自动识别存储模式"""
    
    def __init__(self, base_path: str, user_id: str):
        """初始化路径解析器"""
        self.base_path = base_path  # /opt/nisb-data/users/{user_id}
        self.user_id = user_id
        # 【修复】不再需要额外拼接 /users/{user_id}
        self.user_base = base_path
    
    def detect_doc_mode(self, doc_id: str) -> Tuple[Tuple[StorageMode, Optional[str]], Optional[str]]:
        """
        【核心方法】自动检测文档的存储模式和路径
        
        返回：((模式, 文档完整路径), 库ID或None)
        """
        
        # 优先检查新路径（library 模式）
        libraries_dir = f"{self.user_base}/libraries"
        if os.path.exists(libraries_dir):
            for lib_id in os.listdir(libraries_dir):
                lib_path = os.path.join(libraries_dir, lib_id)
                if lib_id not in ["_config", "cross_library", "archive"]:
                    docs_dir = os.path.join(lib_path, "docs")
                    doc_path = os.path.join(docs_dir, doc_id)
                    if os.path.exists(doc_path):
                        return ((StorageMode.LIBRARY, doc_path), lib_id)
        
        # 其次检查旧路径（legacy 模式）
        legacy_path = f"{self.user_base}/documents/storage/{doc_id}"
        if os.path.exists(legacy_path):
            return ((StorageMode.LEGACY, legacy_path), None)
        
        # 未找到
        return ((StorageMode.UNKNOWN, None), None)
    
    def resolve_doc_path(self, doc_id: str, library_id: Optional[str] = None) -> Dict:
        """
        【通用方法】根据参数和自动检测，获取完整的路径信息
        
        参数：
          doc_id: 文档 ID
          library_id: 库 ID（可选）
        
        返回：路径信息字典
        """
        
        # 如果指定了库 ID，直接在库中查找
        if library_id:
            lib_path = f"{self.user_base}/libraries/{library_id}"
            doc_path = f"{lib_path}/docs/{doc_id}"
            
            if os.path.exists(doc_path):
                return {
                    "mode": "library",
                    "doc_path": doc_path,
                    "index_path": f"{lib_path}/index",
                    "chunks_file": f"{lib_path}/index/chunks.jsonl",
                    "faiss_file": f"{lib_path}/index/faiss_index.bin",
                    "metadata_file": f"{doc_path}/metadata.json",
                    "library_id": library_id,
                    "status": "found"
                }
        
        # 否则自动检测
        (mode, doc_path), detected_lib_id = self.detect_doc_mode(doc_id)
        
        if mode == StorageMode.LEGACY:
            return {
                "mode": "legacy",
                "doc_path": doc_path,
                "index_path": f"{self.user_base}/documents/storage",
                "chunks_file": f"{self.user_base}/documents/storage/chunks.jsonl",
                "faiss_file": f"{self.user_base}/documents/storage/faiss_index.bin",
                "metadata_file": f"{doc_path}/metadata.json",
                "library_id": None,
                "status": "found"
            }
        
        elif mode == StorageMode.LIBRARY:
            lib_path = f"{self.user_base}/libraries/{detected_lib_id}"
            return {
                "mode": "library",
                "doc_path": doc_path,
                "index_path": f"{lib_path}/index",
                "chunks_file": f"{lib_path}/index/chunks.jsonl",
                "faiss_file": f"{lib_path}/index/faiss_index.bin",
                "metadata_file": f"{doc_path}/metadata.json",
                "library_id": detected_lib_id,
                "status": "found"
            }
        
        else:
            return {
                "mode": "unknown",
                "status": "not_found",
                "message": f"文档未找到：{doc_id}"
            }
    
    def list_all_docs(self, library_id: Optional[str] = None) -> List[Dict]:
        """列出所有文档"""
        docs = []
        
        if library_id:
            # 只列出指定库的文档
            lib_path = f"{self.user_base}/libraries/{library_id}/docs"
            if os.path.exists(lib_path):
                for doc_id in os.listdir(lib_path):
                    if os.path.isdir(os.path.join(lib_path, doc_id)):
                        docs.append({
                            "doc_id": doc_id,
                            "library_id": library_id,
                            "mode": "library"
                        })
        else:
            # 列出所有文档（旧 + 新）
            
            # 旧路径
            legacy_dir = f"{self.user_base}/documents/storage"
            if os.path.exists(legacy_dir):
                for doc_id in os.listdir(legacy_dir):
                    doc_path = os.path.join(legacy_dir, doc_id)
                    if os.path.isdir(doc_path) and doc_id.startswith("doc_"):
                        docs.append({
                            "doc_id": doc_id,
                            "library_id": None,
                            "mode": "legacy"
                        })
            
            # 新路径
            libraries_dir = f"{self.user_base}/libraries"
            if os.path.exists(libraries_dir):
                for lib_id in os.listdir(libraries_dir):
                    lib_path = os.path.join(libraries_dir, lib_id)
                    if lib_id not in ["_config", "cross_library", "archive"]:
                        docs_dir = os.path.join(lib_path, "docs")
                        if os.path.exists(docs_dir):
                            for doc_id in os.listdir(docs_dir):
                                if os.path.isdir(os.path.join(docs_dir, doc_id)):
                                    docs.append({
                                        "doc_id": doc_id,
                                        "library_id": lib_id,
                                        "mode": "library"
                                    })
        
        return docs
    
    def create_library_storage(self, library_id: str) -> str:
        """为库创建存储目录结构"""
        # 【修复】不再重复 /users/{user_id}
        lib_path = f"{self.user_base}/libraries/{library_id}"
        
        directories = [
            f"{lib_path}",
            f"{lib_path}/docs",
            f"{lib_path}/index",
            f"{lib_path}/entities",
            f"{lib_path}/relations",
            f"{lib_path}/metadata",
            f"{lib_path}/analytics"
        ]
        
        for dir_path in directories:
            os.makedirs(dir_path, exist_ok=True)
        
        return lib_path

