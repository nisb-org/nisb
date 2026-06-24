"""
目录管理模块（符合NISB规范）
⭐⭐⭐ Phase 3.5.1: 添加storage/目录支持
"""

import os
import shutil
from pathlib import Path
from typing import Dict, Any

from .config import (
    get_agent_files_path,
    get_base_path,
    ensure_directories,
    ALLOWED_DIRECTORIES,
    FORBIDDEN_DIRECTORIES
)
from .security import validate_path_safety
from core.user_context import get_user_ctx
from ..i18n import normalize_backend_locale, text_i18n


def _backend_locale(args: dict | None) -> str:
    return normalize_backend_locale((args or {}).get("locale"))


def _ui_text(args: dict | None, mapping: dict[str, str], default: str = "") -> str:
    return text_i18n(_backend_locale(args), mapping, default)


def _resolve_user(args: dict) -> tuple[str, str | None, str | None]:
    """
    统一解析用户信息，优先使用调用方传入的 user_id/email/name，
    否则退回到 UserContext（如果已经初始化）。

    这样既兼容 HTTP/MCP 传参，也兼容内部 auto_user_context。
    """
    # 1. 优先从 args 中取（MCP/HTTP 通常会传这些隐藏字段）
    user_id = args.get("user_id") or args.get("_user_id")
    email = args.get("_librechat_email") or args.get("_email")
    name = args.get("_librechat_name") or args.get("_name")

    # 2. 如果没有显式传 user_id，则尝试从 UserContext 取
    if not user_id:
        try:
            ctx = get_user_ctx()
            user_id = ctx.user_id
            email = email or getattr(ctx, "email", None)
            name = name or getattr(ctx, "name", None)
        except Exception:
            raise RuntimeError(
                _ui_text(
                    args,
                    {
                        "en": "User context is not initialized and args.user_id was not provided.",
                        "zh-CN": "用户上下文未初始化，且未在 args 中提供 user_id",
                    },
                )
            )

    return user_id, email, name


def nisb_dir_create(args: dict) -> Dict[str, Any]:
    """创建目录（符合NISB规范，统一以用户根目录为基准）

    路径规范（path 参数）：
    - 针对 user 根目录的相对路径，例如：
      - "agent_files/projects/nisb-core/docs"
      - "storage/entities/concepts"
    - 不要在前面再手动加绝对路径或用户 ID
    """
    try:
        # ⭐ 解析当前用户
        user_id, email, name = _resolve_user(args)

        path = args.get("path")
        if not path:
            return {
                "success": False,
                "message": _ui_text(
                    args,
                    {
                        "en": "❌ path is required",
                        "zh-CN": "❌ path 不能为空",
                    },
                ),
            }

        # 统一：所有路径都基于 base_path（用户根目录）
        base_path = get_base_path(user_id, email, name)
        full_path = os.path.join(base_path, path)

        # 安全检查（防止越权访问）
        is_safe, error_msg, _ = validate_path_safety(full_path, user_id, email, name)
        if not is_safe:
            return {"success": False, "message": error_msg}

        # 创建目录（含中间层）
        os.makedirs(full_path, exist_ok=True)

        return {
            "success": True,
            "message": _ui_text(
                args,
                {
                    "en": f"✅ Directory created\n\n📁 {path}",
                    "zh-CN": f"✅ 目录创建成功\n\n📁 {path}",
                },
            ),
            "path": full_path,
        }

    except Exception as e:
        return {
            "success": False,
            "message": _ui_text(
                args,
                {
                    "en": f"❌ Create failed: {str(e)}",
                    "zh-CN": f"❌ 创建失败：{str(e)}",
                },
            ),
        }


def nisb_dir_list(args: dict) -> Dict[str, Any]:
    """
    列出目录内容
    ⭐⭐⭐ Phase 6.1.2: path 为空时返回用户根目录
    """
    try:
        user_id, email, name = _resolve_user(args)

        path = args.get("path", "")
        show_sizes = args.get("show_sizes", True)

        base_path = get_base_path(user_id, email, name)

        # ⭐ path 为空：返回用户根目录内容
        if not path:
            target_path = base_path
            display_name = f"~/"
        else:
            target_path = os.path.join(base_path, path)
            display_name = f"~/{path}/"

        # 安全检查
        is_safe, error_msg, _ = validate_path_safety(
            target_path, user_id, email, name
        )
        if not is_safe:
            return {"success": False, "message": error_msg}

        if not os.path.exists(target_path):
            return {"success": False, "message": f"❌ 目录不存在：{display_name}"}

        # 获取内容
        entries = []
        for item in sorted(os.listdir(target_path)):
            # ⭐ 跳过隐藏文件和系统目录
            if item.startswith("."):
                continue

            item_path = os.path.join(target_path, item)
            is_dir = os.path.isdir(item_path)

            entry = {
                "name": item,
                "type": "directory" if is_dir else "file",
            }

            if show_sizes and not is_dir:
                try:
                    size = os.path.getsize(item_path)
                    entry["size"] = size
                    entry["size_mb"] = round(size / 1024 / 1024, 2)
                except Exception:
                    entry["size"] = 0
                    entry["size_mb"] = 0.0

            entries.append(entry)

        # 构建输出
        lines = [f"📁 {display_name}\n"]

        dirs = [e for e in entries if e["type"] == "directory"]
        files = [e for e in entries if e["type"] == "file"]

        if dirs:
            lines.append(f"📂 子目录（{len(dirs)}个）：")
            for d in dirs:
                lines.append(f"  • {d['name']}/")

        if files:
            lines.append(f"\n📄 文件（{len(files)}个）：")
            for f in files:
                if show_sizes:
                    lines.append(
                        f"  • {f['name']} ({f.get('size_mb', 0)} MB)"
                    )
                else:
                    lines.append(f"  • {f['name']}")

        if not dirs and not files:
            lines.append("  （空目录）")

        return {
            "success": True,
            "message": "\n".join(lines),
            "entries": entries,
        }

    except Exception as e:
        import traceback

        return {
            "success": False,
            "message": f"❌ 列表获取失败：{str(e)}\n\n{traceback.format_exc()}",
        }


def nisb_dir_tree(args: dict) -> Dict[str, Any]:
    """
    显示目录树（符合NISB规范）
    ⭐ 支持 storage/ 目录
    """
    try:
        # ⭐ 解析当前用户
        user_id, email, name = _resolve_user(args)

        # ⭐ 调试：确认已经不再是 user_001
        print(
            f"[NISB-FS-DEBUG] dir_tree user_id={user_id} email={email} name={name}"
        )

        path = args.get("path", "")
        depth = args.get("depth", 3)

        # ⭐⭐⭐ 支持多种路径模式
        if not path:
            target_path = get_agent_files_path(user_id, email, name)
            display_name = "agent_files/"
        elif path == "storage":
            base_path = get_base_path(user_id, email, name)
            target_path = f"{base_path}/storage"
            display_name = "storage/"
        elif path.startswith("storage/"):
            base_path = get_base_path(user_id, email, name)
            target_path = f"{base_path}/{path}"
            display_name = f"{path}/"
        else:
            base_path = get_agent_files_path(user_id, email, name)
            target_path = os.path.join(base_path, path)
            display_name = f"agent_files/{path}/"

        # 安全检查
        is_safe, error_msg, _ = validate_path_safety(
            target_path, user_id, email, name
        )
        if not is_safe:
            return {"success": False, "message": error_msg}

        if not os.path.exists(target_path):
            return {"success": False, "message": f"❌ 目录不存在：{display_name}"}

        # 递归构建树
        def build_tree(dir_path: str, current_depth: int = 0, prefix: str = ""):
            if current_depth >= depth:
                return []

            lines = []
            try:
                items = sorted(os.listdir(dir_path))
                items = [i for i in items if not i.startswith(".")]  # 跳过隐藏文件

                for i, item in enumerate(items):
                    item_path = os.path.join(dir_path, item)
                    is_last = i == len(items) - 1

                    if is_last:
                        lines.append(f"{prefix}└── {item}")
                        new_prefix = f"{prefix}    "
                    else:
                        lines.append(f"{prefix}├── {item}")
                        new_prefix = f"{prefix}│   "

                    if os.path.isdir(item_path):
                        lines.extend(
                            build_tree(item_path, current_depth + 1, new_prefix)
                        )

            except PermissionError:
                pass

            return lines

        tree_lines = [f"📁 {display_name} (深度{depth})"]
        tree_lines.extend(build_tree(target_path))

        # ⭐ 添加提示
        if "storage" in display_name:
            tree_lines.append("\n🛡️ Storage目录：所有操作将自动备份")

        return {
            "success": True,
            "message": "\n".join(tree_lines),
            "depth": depth,
        }

    except Exception as e:
        import traceback

        return {
            "success": False,
            "message": f"❌ 树形图生成失败：{str(e)}\n\n{traceback.format_exc()}",
        }


def nisb_dir_delete_recursive(args: dict) -> Dict[str, Any]:
    """
    递归删除指定目录及其所有子目录和文件（危险操作）

    参数：
      - path: 基于用户根目录的相对路径，例如 "agent_files/projects/demo"
    """
    try:
        user_id, email, name = _resolve_user(args)

        path = args.get("path")
        if not path:
            return {"success": False, "message": "❌ path 不能为空"}

        base_path = get_base_path(user_id, email, name)
        full_path = os.path.join(base_path, path)

        # 安全检查
        is_safe, error_msg, _ = validate_path_safety(
            full_path, user_id, email, name
        )
        if not is_safe:
            return {"success": False, "message": error_msg}

        if not os.path.exists(full_path):
            return {"success": False, "message": f"❌ 目录不存在：{path}"}

        if not os.path.isdir(full_path):
            return {"success": False, "message": f"❌ 目标不是目录：{path}"}

        # 防止误删用户根目录
        if os.path.normpath(full_path) == os.path.normpath(base_path):
            return {"success": False, "message": "❌ 不允许递归删除用户根目录"}

        # 统计即将删除的条目数量（目录 + 文件）
        deleted_count = 0
        for _root, dirs, files in os.walk(full_path):
            deleted_count += len(dirs) + len(files)
        # 把自身目录也计入
        deleted_count += 1

        # 真正删除
        shutil.rmtree(full_path)

        return {
            "success": True,
            "message": f"✅ 已递归删除目录及其子内容：{path}",
            "deleted": deleted_count,
        }

    except Exception as e:
        import traceback

        return {
            "success": False,
            "message": f"❌ 递归删除失败：{str(e)}",
            "traceback": traceback.format_exc(),
        }


def nisb_file_list_allowed_directories(args: dict) -> Dict[str, Any]:
    """列出允许访问的目录（符合NISB规范）"""
    # ⭐ 解析当前用户
    user_id, email, name = _resolve_user(args)

    base_path = get_base_path(user_id, email, name)

    # 统计允许的目录
    allowed_info = []
    for dir_name in ALLOWED_DIRECTORIES:
        dir_path = f"{base_path}/{dir_name}"

        if os.path.exists(dir_path):
            total_files = sum(
                1 for _ in Path(dir_path).rglob("*") if _.is_file()
            )
            total_size = sum(
                _.stat().st_size
                for _ in Path(dir_path).rglob("*")
                if _.is_file()
            )
        else:
            total_files = 0
            total_size = 0

        allowed_info.append(
            {
                "directory": dir_name,
                "path": dir_path,
                "files": total_files,
                "size_mb": round(total_size / 1024 / 1024, 2),
                "permissions": "read_write_delete",
            }
        )

    # 禁止的目录
    forbidden_info = []
    for dir_name in FORBIDDEN_DIRECTORIES:
        forbidden_info.append(
            {
                "directory": dir_name,
                "reason": "系统保护目录，Agent无权限访问",
            }
        )

    # 构建消息
    msg = "🔒 NISB文件系统权限说明\n\n"
    msg += "✅ 允许访问的目录：\n"
    for info in allowed_info:
        msg += (
            f"  • {info['directory']}/ "
            f"({info['files']} 文件, {info['size_mb']} MB)\n"
        )
        msg += f"    权限：{info['permissions']}\n"

    msg += "\n❌ 禁止访问的目录：\n"
    for info in forbidden_info:
        msg += f"  • {info['directory']}/ - {info['reason']}\n"

    msg += "\n💡 使用提示：\n"
    msg += "  • agent_files/ - Agent创建的文件（脚本、配置等）\n"
    msg += "  • storage/ - NISB核心数据（🛡️ 自动备份保护）\n"
    msg += "  • .backups/ - 备份目录（只读，用于恢复）\n"
    msg += "  • .operation_logs/ - 操作日志（只读，用于审计）\n"

    msg += "\n📝 访问storage/示例：\n"
    msg += "  • nisb_file_list(path='storage')\n"
    msg += "  • nisb_dir_list(path='storage/entities')\n"
    msg += "  • nisb_dir_tree(path='storage', depth=2)\n"

    return {
        "success": True,
        "message": msg,
        "allowed": allowed_info,
        "forbidden": forbidden_info,
    }

