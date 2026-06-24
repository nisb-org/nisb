"""
工具函数模块
文件分析、元数据管理、历史记录
"""

import os
import json
import re
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List
from .config import get_agent_files_path


# ============================================================
# 文件分析
# ============================================================

def analyze_file(content: str, filename: str) -> Dict[str, Any]:
    """
    轻量级文件分析
    
    Args:
        content: 文件内容
        filename: 文件名
    
    Returns:
        {
            'type': str,
            'functions': List[str],
            'imports': List[str]
        }
    """
    ext = Path(filename).suffix.lower()
    
    result = {
        'type': _get_file_type(ext),
        'functions': [],
        'imports': []
    }
    
    # Python文件分析
    if ext == '.py':
        result['functions'] = re.findall(r'def\s+(\w+)\s*\(', content)
        result['imports'] = re.findall(r'(?:import|from)\s+(\w+)', content)
    
    # JavaScript文件分析
    elif ext in ['.js', '.mjs']:
        result['functions'] = re.findall(r'function\s+(\w+)\s*\(', content)
        result['functions'] += re.findall(r'const\s+(\w+)\s*=\s*\(.*?\)\s*=>', content)
        result['imports'] = re.findall(r'import\s+.*?from\s+[\'"](.+?)[\'"]', content)
    
    # 去重并限制数量
    result['functions'] = list(set(result['functions']))[:20]
    result['imports'] = list(set(result['imports']))[:20]
    
    return result


def _get_file_type(ext: str) -> str:
    """根据扩展名判断文件类型"""
    type_map = {
        '.py': 'python',
        '.js': 'javascript',
        '.mjs': 'javascript',
        '.sh': 'shell',
        '.bash': 'shell',
        '.json': 'json',
        '.yaml': 'yaml',
        '.yml': 'yaml',
        '.env': 'env',
        '.csv': 'csv',
        '.tsv': 'csv',
        '.md': 'markdown',
        '.txt': 'text',
        '.rst': 'text'
    }
    return type_map.get(ext, 'unknown')


# ============================================================
# ID生成
# ============================================================

def generate_file_id(filename: str) -> str:
    """
    生成唯一文件ID
    
    格式：file_YYYYMMDD_HHMMSS_hash
    """
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    name_hash = hashlib.md5(filename.encode()).hexdigest()[:8]
    return f"file_{timestamp}_{name_hash}"


# ============================================================
# 元数据管理
# ============================================================

def save_metadata(
    user_id: str,
    file_id: str,
    metadata: dict,
    email: str = None,
    name: str = None
):
    """保存文件元数据"""
    base_path = get_agent_files_path(user_id, email, name)
    meta_path = f"{base_path}/.metadata/{file_id}.json"
    
    os.makedirs(os.path.dirname(meta_path), exist_ok=True)
    
    with open(meta_path, 'w', encoding='utf-8') as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)


def load_metadata(
    user_id: str,
    file_id: str,
    email: str = None,
    name: str = None
) -> Optional[dict]:
    """加载文件元数据"""
    base_path = get_agent_files_path(user_id, email, name)
    meta_path = f"{base_path}/.metadata/{file_id}.json"
    
    if not os.path.exists(meta_path):
        return None
    
    try:
        with open(meta_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return None


def find_metadata_by_filename(
    user_id: str,
    filename: str,
    email: str = None,
    name: str = None
) -> Optional[dict]:
    """通过文件名查找元数据"""
    base_path = get_agent_files_path(user_id, email, name)
    meta_dir = f"{base_path}/.metadata"
    
    if not os.path.exists(meta_dir):
        return None
    
    for meta_file in os.listdir(meta_dir):
        if not meta_file.endswith('.json'):
            continue
        
        try:
            with open(f"{meta_dir}/{meta_file}", 'r', encoding='utf-8') as f:
                metadata = json.load(f)
            
            if metadata.get('filename') == filename and not metadata.get('deleted'):
                return metadata
        except:
            continue
    
    return None


# ============================================================
# 历史记录
# ============================================================

def save_history(
    user_id: str,
    file_id: str,
    content: str,
    email: str = None,
    name: str = None
):
    """保存文件历史版本"""
    base_path = get_agent_files_path(user_id, email, name)
    history_dir = f"{base_path}/.history/{file_id}"
    os.makedirs(history_dir, exist_ok=True)
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    history_file = f"{history_dir}/{timestamp}.txt"
    
    with open(history_file, 'w', encoding='utf-8') as f:
        f.write(content)


def get_history(
    user_id: str,
    file_id: str,
    limit: int = 10,
    email: str = None,
    name: str = None
) -> List[Dict[str, Any]]:
    """获取文件历史版本列表"""
    base_path = get_agent_files_path(user_id, email, name)
    history_dir = f"{base_path}/.history/{file_id}"
    
    if not os.path.exists(history_dir):
        return []
    
    history_files = sorted(os.listdir(history_dir), reverse=True)[:limit]
    
    history = []
    for hf in history_files:
        timestamp = hf.replace('.txt', '')
        file_path = f"{history_dir}/{hf}"
        
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        history.append({
            'timestamp': timestamp,
            'size': len(content),
            'path': file_path
        })
    
    return history

