"""
配置模块（符合NISB多用户规范）
⭐⭐⭐ Phase 6.1.2: 允许访问整个用户根目录
"""

import os
from pathlib import Path

# ============================================================
# 全局配置
# ============================================================

AGENT_FILES_ROOT = "agent_files"

# ⭐⭐⭐ 允许访问的目录（白名单）- 改为允许整个用户根
# 特殊值 "__ROOT__" 表示用户根目录本身
ALLOWED_DIRECTORIES = ["__ROOT__"]

# 禁止访问的目录（黑名单）- 只保留真正危险的系统目录
FORBIDDEN_DIRECTORIES = []

# 需要自动保护的目录（操作前自动备份）
PROTECTED_DIRECTORIES = ["storage"]

# 自动分类规则（保持不变）
CATEGORY_MAP = {
    '.py': 'scripts/python',
    '.js': 'scripts/javascript',
    '.mjs': 'scripts/javascript',
    '.sh': 'scripts/shell',
    '.bash': 'scripts/shell',
    '.json': 'configs/json',
    '.yaml': 'configs/yaml',
    '.yml': 'configs/yaml',
    '.env': 'configs/env',
    '.csv': 'data/csv',
    '.tsv': 'data/csv',
    '.md': 'docs/markdown',
    '.txt': 'docs/text',
}

# 子目录结构
SUBDIRECTORIES = [
    "agent_files",
    "agent_files/scripts/python",
    "agent_files/scripts/javascript",
    "agent_files/scripts/shell",
    "agent_files/configs/json",
    "agent_files/configs/yaml",
    "agent_files/configs/env",
    "agent_files/data/csv",
    "agent_files/data/json",
    "agent_files/data/other",
    "agent_files/docs/markdown",
    "agent_files/docs/text",
    "agent_files/.metadata",
    "agent_files/.history"
]

# 路径工具（保持不变）
def get_base_path(user_id: str, email: str = None, name: str = None) -> str:
    """获取用户基础路径"""
    user_id = (user_id or "").strip()
    if not user_id:
        raise ValueError("get_base_path 需要有效的 user_id")
    return f"/data/users/{user_id}"

def get_agent_files_path(user_id: str, email: str = None, name: str = None) -> str:
    """获取 agent_files 路径"""
    base_path = get_base_path(user_id, email, name)
    return f"{base_path}/{AGENT_FILES_ROOT}"

def get_backup_path(user_id: str, email: str = None, name: str = None) -> str:
    """获取备份路径"""
    base_path = get_base_path(user_id, email, name)
    return f"{base_path}/.backups"

def get_log_path(user_id: str, email: str = None, name: str = None) -> str:
    """获取日志路径"""
    base_path = get_base_path(user_id, email, name)
    return f"{base_path}/.operation_logs"

def ensure_directories(user_id: str, email: str = None, name: str = None):
    """确保所有必需目录存在"""
    base_path = get_base_path(user_id, email, name)
    
    # 创建 agent_files 子目录
    for subdir in SUBDIRECTORIES:
        os.makedirs(f"{base_path}/{subdir}", exist_ok=True)
    
    # 创建备份和日志目录
    os.makedirs(get_backup_path(user_id, email, name), exist_ok=True)
    os.makedirs(get_log_path(user_id, email, name), exist_ok=True)

def detect_category(filename: str) -> str:
    """自动检测文件分类"""
    ext = Path(filename).suffix.lower()
    
    if ext == '.json':
        if any(kw in filename.lower() for kw in ['config', 'settings', 'setup']):
            return 'configs/json'
        else:
            return 'data/json'
    
    return CATEGORY_MAP.get(ext, 'data/other')

