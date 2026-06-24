"""
安全验证模块
⭐⭐⭐ Phase 6.1.2: 允许访问整个用户根目录 + 放宽文件名字符限制
"""

import os
import re
from typing import Tuple
from pathlib import Path
from .config import (
    get_base_path,
    ALLOWED_DIRECTORIES,
    FORBIDDEN_DIRECTORIES,
    PROTECTED_DIRECTORIES
)


def validate_path_safety(
    file_path: str,
    user_id: str,
    email: str = None,
    name: str = None
) -> Tuple[bool, str, bool]:
    """
    验证路径安全性
    ⭐⭐⭐ Phase 6.1.2: 允许整个用户根目录
    """
    base_path = get_base_path(user_id, email, name)

    # 1. 规范化路径
    try:
      normalized_path = os.path.normpath(os.path.abspath(file_path))
      normalized_base = os.path.normpath(os.path.abspath(base_path))
    except Exception as e:
      return False, f"❌ 路径无效：{str(e)}", False

    # 2. ⭐⭐⭐ 核心改动：只要在用户根目录内就允许
    if not normalized_path.startswith(normalized_base + os.sep) and normalized_path != normalized_base:
      return False, (
          f"❌ 安全限制：只允许访问您的用户目录\n\n"
          f"💡 当前路径：{normalized_path}\n"
          f"💡 允许范围：{normalized_base}/*"
      ), False

    # 3. 检查是否需要自动保护（storage/目录）
    needs_protection = "storage" in normalized_path

    return True, "", needs_protection


def validate_filename(filename: str) -> Tuple[bool, str]:
    """
    验证文件名合法性（放宽到几乎允许所有常见字符，仅禁止极少数危险字符）

    规则：
    - 不允许为空
    - 不允许包含: < > : " \\ | ? * 或 NUL
    - 不允许以 / 开头（绝对路径）
    - 不允许出现目录穿越片段 ".."
    - 不允许出现连续的 //
    - 长度 <= 500
    """
    if not filename:
        return False, "❌ 文件名不能为空"

    # NUL 字符（极少见，但明确拒绝）
    if "\0" in filename:
        return False, "❌ 文件名包含无效控制字符"

    # 禁止的危险字符集合（跨平台参考）
    # Linux 只禁止 / 和 NUL，[web:324]
    # Windows 额外禁止 < > : \" \\ | ? * 等，[web:323][web:336]
    forbidden_chars = set('<>:"\\|?*')

    found = sorted({ch for ch in filename if ch in forbidden_chars})
    if found:
        return False, f"❌ 文件名包含非法字符：{', '.join(found)}"

    # 禁止绝对路径
    if filename.startswith("/"):
        return False, "❌ 文件名不能以 / 开头"

    # 禁止目录穿越：任意路径片段等于 ".."
    parts = filename.split("/")
    if any(part == ".." for part in parts):
        return False, "❌ 文件名不能包含目录穿越片段 .."

    # 禁止多个连续斜杠
    if "//" in filename:
        return False, "❌ 文件名不能包含连续的 //"

    if len(filename) > 500:
        return False, "❌ 文件名过长（最大500字符）"

    return True, ""

