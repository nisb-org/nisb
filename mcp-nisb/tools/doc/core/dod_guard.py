from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List

_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$")


def require_safe_id(name: str, value: str) -> str:
    v = (value or "").strip()
    if not v:
        raise ValueError(f"{name} 不能为空")
    if not _ID_RE.match(v):
        raise ValueError(
            f"{name} 非法：{v!r}（仅允许字母数字、_、-，长度<=128，且不能包含 / 或 ..）"
        )
    return v


def safe_child_dir(root: Path, child: str) -> Path:
    """
    只允许 root/child 这种一级子路径，并确保 resolve 后仍在 root 内（防路径穿越）。
    """
    root_abs = root.resolve()
    p = (root_abs / child).resolve()
    if p == root_abs or root_abs not in p.parents:
        raise ValueError(f"unsafe path: {p}")
    return p


def normalize_doc_ids(value: Any) -> List[str]:
    """
    支持：
    - list[str]
    - "a,b,c"
    - "a\nb\nc"
    - 混合空白
    返回：去重（保序）
    """
    if value is None:
        return []

    if isinstance(value, list):
        raw = value
    elif isinstance(value, str):
        s = value.strip()
        if not s:
            return []
        parts: List[str] = []
        for line in s.splitlines():
            line = line.strip()
            if not line:
                continue
            parts.extend([p.strip() for p in line.split(",") if p.strip()])
        raw = parts
    else:
        return []

    seen = set()
    out: List[str] = []
    for x in raw:
        doc_id = str(x or "").strip()
        if not doc_id:
            continue
        if doc_id in seen:
            continue
        seen.add(doc_id)
        out.append(doc_id)
    return out


def chunk_list(items: List[str], chunk_size: int) -> List[List[str]]:
    if chunk_size <= 0:
        return [items]
    return [items[i : i + chunk_size] for i in range(0, len(items), chunk_size)]


def resolve_user_base_from_args(args: Dict[str, Any]) -> Path:
    """
    统一解析用户数据根目录（修复路径重复问题）
    
    优先级：
    1. basepath（前端注入的完整路径，如 /data/users/{uid}）
    2. _base_path + _mcp_mode（MCP 单用户模式）
    3. _base_path + user_id（HTTP 多用户模式）
    """
    import os
    
    # ✅ 优先使用前端注入的 basepath（已经是完整路径 /data/users/{uid}）
    basepath = args.get("basepath") or args.get("base_path") or args.get("user_base_path")
    if basepath:
        bp = str(basepath).strip()
        if bp:
            return Path(bp).resolve()
    
    # MCP 单用户模式（_base_path 就是用户根目录）
    base_path_raw = args.get("_base_path")
    if args.get("_mcp_mode"):
        if base_path_raw:
            return Path(str(base_path_raw)).resolve()
        # 如果没有 _base_path，使用环境变量
        data_root = os.environ.get("NISB_BASE_PATH", "/data")
        return Path(data_root).resolve()
    
    # HTTP 多用户模式（需要从 _base_path 和 user_id 构建）
    user_id = (args.get("user_id") or args.get("userid") or args.get("userId") or "").strip()
    if not user_id:
        raise ValueError("user_id 不能为空（HTTP 多用户模式下前端 callTool 应注入 user_id）")
    
    # ✅ 关键修复：_base_path 应该是数据根目录（如 /data），而不是用户目录
    # 如果 _base_path 已经包含 /users/{uid}，说明是前端注入的完整路径，直接返回
    if base_path_raw:
        bp = Path(str(base_path_raw)).resolve()
        # 检查路径是否已经包含 users/{user_id}
        if bp.name == user_id and bp.parent.name == "users":
            # 已经是完整路径，直接返回
            return bp
        # 否则，从 _base_path 拼接
        return bp / "users" / user_id
    
    # 如果没有 _base_path，使用环境变量
    data_root = os.environ.get("NISB_BASE_PATH", "/data")
    return Path(data_root) / "users" / user_id

