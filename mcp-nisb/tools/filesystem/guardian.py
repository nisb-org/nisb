"""
NISB Guardian - 自动备份与操作日志系统
"""

import os
import json
import shutil
from datetime import datetime
from typing import List, Optional, Callable, Any
from .config import get_base_path, get_backup_path, get_log_path


class NISBGuardian:
    """NISB守护者：自动备份+操作日志"""
    
    def __init__(self, user_id: str, email: str = None, name: str = None):
        """
        初始化守护者
        
        Args:
            user_id: 用户ID
            email: LibreChat邮箱
            name: LibreChat用户名
        """
        self.user_id = user_id
        self.email = email
        self.name = name
        self.base_path = get_base_path(user_id, email, name)
        self.backup_path = get_backup_path(user_id, email, name)
        self.log_path = get_log_path(user_id, email, name)
        
        # 确保目录存在
        os.makedirs(self.backup_path, exist_ok=True)
        os.makedirs(self.log_path, exist_ok=True)
    
    
    def protect(
        self, 
        operation_name: str, 
        affected_paths: Optional[List[str]] = None,
        backup_type: str = "incremental"
    ):
        """
        装饰器：保护操作
        
        Args:
            operation_name: 操作名称
            affected_paths: 受影响的文件路径列表（相对于documents/）
            backup_type: 备份类型（incremental/full）
        """
        def decorator(func: Callable) -> Callable:
            def wrapper(*args, **kwargs):
                # 1. 创建备份
                backup_id = self._create_backup(
                    operation_name, 
                    affected_paths, 
                    backup_type
                )
                
                # 2. 记录操作开始
                operation_id = self._log_start(
                    operation_name,
                    args,
                    kwargs,
                    backup_id
                )
                
                try:
                    # 3. 执行操作
                    result = func(*args, **kwargs)
                    
                    # 4. 记录成功
                    self._log_success(operation_id, result)
                    
                    return result
                
                except Exception as e:
                    # 5. 记录失败
                    self._log_failure(operation_id, str(e))
                    
                    # 6. 不自动回滚（由用户决定）
                    raise
            
            return wrapper
        return decorator
    
    
    def _create_backup(
        self,
        operation_name: str,
        affected_paths: Optional[List[str]],
        backup_type: str
    ) -> str:
        """创建备份"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_id = f"{timestamp}_{operation_name}"
        backup_dir = f"{self.backup_path}/{backup_id}"
        
        os.makedirs(backup_dir, exist_ok=True)
        
        if backup_type == "incremental" and affected_paths:
            # 增量备份
            for rel_path in affected_paths:
                src = f"{self.base_path}/{rel_path}"
                if os.path.exists(src):
                    dst = f"{backup_dir}/{rel_path}"
                    os.makedirs(os.path.dirname(dst), exist_ok=True)
                    
                    if os.path.isdir(src):
                        shutil.copytree(src, dst, symlinks=True)
                    else:
                        shutil.copy2(src, dst)
        
        elif backup_type == "full":
            # 完整备份storage目录
            src = f"{self.base_path}/storage"
            dst = f"{backup_dir}/storage"
            if os.path.exists(src):
                shutil.copytree(src, dst, symlinks=True)
        
        # 保存元数据
        metadata = {
            "backup_id": backup_id,
            "operation_name": operation_name,
            "timestamp": datetime.now().isoformat(),
            "backup_type": backup_type,
            "affected_paths": affected_paths or ["全部"],
            "user_id": self.user_id
        }
        
        with open(f"{backup_dir}/metadata.json", 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)
        
        return backup_id
    
    
    def _log_start(self, operation_name: str, args: tuple, kwargs: dict, backup_id: str) -> str:
        """记录操作开始"""
        operation_id = f"op_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"
        
        log_entry = {
            "operation_id": operation_id,
            "backup_id": backup_id,
            "operation_name": operation_name,
            "timestamp": datetime.now().isoformat(),
            "status": "started",
            "user_id": self.user_id
        }
        
        self._append_log(log_entry)
        return operation_id
    
    
    def _log_success(self, operation_id: str, result: Any):
        """记录操作成功"""
        log_entry = {
            "operation_id": operation_id,
            "timestamp": datetime.now().isoformat(),
            "status": "success"
        }
        self._append_log(log_entry)
    
    
    def _log_failure(self, operation_id: str, error: str):
        """记录操作失败"""
        log_entry = {
            "operation_id": operation_id,
            "timestamp": datetime.now().isoformat(),
            "status": "failed",
            "error": error
        }
        self._append_log(log_entry)
    
    
    def _append_log(self, log_entry: dict):
        """追加日志"""
        today = datetime.now().strftime('%Y-%m-%d')
        log_file = f"{self.log_path}/{today}.jsonl"
        
        with open(log_file, 'a', encoding='utf-8') as f:
            f.write(json.dumps(log_entry, ensure_ascii=False) + '\n')
    
    
    def rollback(self, backup_id: str):
        """回滚到指定备份"""
        backup_dir = f"{self.backup_path}/{backup_id}"
        
        if not os.path.exists(backup_dir):
            raise FileNotFoundError(f"备份不存在：{backup_id}")
        
        # 读取元数据
        with open(f"{backup_dir}/metadata.json", 'r') as f:
            metadata = json.load(f)
        
        if metadata['backup_type'] == 'full':
            # 完整恢复
            target = f"{self.base_path}/storage"
            if os.path.exists(target):
                shutil.rmtree(target)
            shutil.copytree(f"{backup_dir}/storage", target)
        
        else:
            # 增量恢复
            for rel_path in metadata['affected_paths']:
                src = f"{backup_dir}/{rel_path}"
                dst = f"{self.base_path}/{rel_path}"
                if os.path.exists(src):
                    if os.path.isdir(src):
                        if os.path.exists(dst):
                            shutil.rmtree(dst)
                        shutil.copytree(src, dst)
                    else:
                        shutil.copy2(src, dst)

