#!/usr/bin/env python3
"""
NISB 统一用户上下文管理 v6.0
- 统一数据根：NISB_BASE_PATH（默认 /data）
- 多用户目录：{NISB_BASE_PATH}/users/{user_id}
- 兼容 HTTP API 与 MCP
"""

from __future__ import annotations

import os
import threading
from functools import wraps
from typing import Dict, Optional

_thread_local = threading.local()

NISB_USER_SYSTEM_ENABLED = os.environ.get("NISB_USER_SYSTEM_ENABLED", "true").lower() == "true"
DATA_ROOT = os.environ.get("NISB_BASE_PATH", "/data").rstrip("/")
USERS_ROOT = f"{DATA_ROOT}/users"


class UserContext:
    """用户上下文（仅负责路径与基础信息，不负责工具逻辑）"""

    def __init__(self, user_id: str, email: str = "", name: str = "", base_path: str = ""):
        self.user_id = user_id
        self.email = email
        self.name = name

        # base_path 语义：如果传了，认为它就是 “用户根目录”（= .../users/{uid}）
        # 否则统一落在 USERS_ROOT 下
        self.base = base_path.strip() if str(base_path or "").strip() else f"{USERS_ROOT}/{user_id}"

        self.storage = f"{self.base}/storage"
        self.entities = f"{self.storage}/entities"
        self.concepts = f"{self.entities}/concepts/by_id"
        self.authors = f"{self.entities}/authors/by_id"
        self.books = f"{self.entities}/books/by_id"
        self.topics = f"{self.entities}/topics/by_id"
        self.relations = f"{self.storage}/relations/by_type"
        self.kb_bookmarks = f"{self.storage}/kb_bookmarks"
        self.raw = f"{self.storage}/raw"
        self.cache = f"{self.base}/cache"

    def ensure_dirs(self):
        import os as _os

        for path in [
            self.concepts,
            self.authors,
            self.books,
            self.topics,
            self.relations,
            self.kb_bookmarks,
            self.raw,
            self.cache,
        ]:
            _os.makedirs(path, exist_ok=True)


def set_user_ctx(ctx: UserContext):
    ctx.ensure_dirs()
    _thread_local.user_ctx = ctx


def get_user_ctx() -> UserContext:
    if not hasattr(_thread_local, "user_ctx"):
        raise RuntimeError("用户上下文未初始化")
    return _thread_local.user_ctx


def clear_user_ctx():
    if hasattr(_thread_local, "user_ctx"):
        delattr(_thread_local, "user_ctx")


def auto_user_context(func):
    """
    装饰器：自动注入用户上下文

    支持：
    1) HTTP API：args 内应包含 token（由 api_gateway 注入）
    2) MCP：args['_mcp_mode']=True，且可用环境变量 NISB_USER_ID 指定用户
    3) 无 token 退化：使用 nisb_default_user（仍使用 USERS_ROOT 结构）
    """

    @wraps(func)
    def wrapper(args: Dict):
        try:
            args = args or {}
            is_mcp_mode = bool(args.get("_mcp_mode", False))

            user_ctx: Optional[UserContext] = None

            if is_mcp_mode:
                user_id_env = os.getenv("NISB_USER_ID")
                if user_id_env:
                    user_ctx = UserContext(
                        user_id=user_id_env,
                        email="",
                        name=f"MCP User ({user_id_env})",
                    )
                else:
                    # 没指定用户就用一个固定 uid，依然走 USERS_ROOT
                    user_ctx = UserContext(
                        user_id="mcp_user",
                        email="",
                        name="MCP User",
                    )
            else:
                token = args.get("token")
                if not token:
                    user_ctx = UserContext(
                        user_id="nisb_default_user",
                        email="",
                        name="HTTP Default User",
                    )
                else:
                    if not NISB_USER_SYSTEM_ENABLED:
                        return {"status": "error", "message": "用户系统未启用"}

                    from core.user_system import UserAuthManager

                    auth = UserAuthManager()
                    is_valid, user_id = auth.verify_token(token)
                    if not is_valid or not user_id:
                        return {"status": "error", "message": "Token 无效或已过期"}

                    user = auth.db.execute(
                        "SELECT * FROM users WHERE user_id = ?",
                        (user_id,),
                    ).fetchone()
                    if not user:
                        return {"status": "error", "message": "用户不存在"}

                    user_ctx = UserContext(
                        user_id=user["user_id"],
                        email=user["email"],
                        name=user["username"],
                    )

            if user_ctx is None:
                return {"status": "error", "message": "用户上下文错误: 无法初始化用户上下文"}

            set_user_ctx(user_ctx)
            result = func(args)
            clear_user_ctx()
            return result

        except Exception as e:
            import traceback

            traceback.print_exc()
            clear_user_ctx()
            return {"status": "error", "message": f"用户上下文错误: {str(e)}"}

    return wrapper


def get_user_base_path(user_id: str | None = None) -> str:
    """兼容旧接口：返回用户根目录（.../users/{uid}）"""
    if user_id:
        return f"{USERS_ROOT}/{user_id}"
    return get_user_ctx().base

