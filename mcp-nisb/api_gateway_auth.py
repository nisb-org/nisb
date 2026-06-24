#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import inspect
import secrets
import time
from typing import Any, Dict, Optional, List

from fastapi import HTTPException

from core.user_system import UserAuthManager


def new_request_id() -> str:
    return f"req_{int(time.time()*1000)}_{secrets.token_hex(4)}"


def ensure_request_id(arguments: Dict[str, Any]) -> Dict[str, Any]:
    rid = str((arguments or {}).get("request_id") or "").strip()
    if not rid:
        arguments["request_id"] = new_request_id()
    return arguments


def inject_user_context(arguments: Dict[str, Any], token: str, user_id: str, *, users_root: str) -> Dict[str, Any]:
    user_base = f"{str(users_root).rstrip('/')}/{user_id}"

    arguments["token"] = token
    arguments["user_id"] = user_id
    arguments["_user_id"] = user_id

    arguments["_base_path"] = user_base
    arguments["base_path"] = user_base
    arguments["basepath"] = user_base

    ensure_request_id(arguments)
    return arguments


def auth_and_inject(
    tool_name: str,
    arguments: Dict[str, Any],
    authorization: Optional[str],
    *,
    users_root: str,
    whitelist_tools: Optional[List[str]] = None,
) -> Dict[str, Any]:
    whitelist = whitelist_tools or []

    if tool_name in whitelist:
        return ensure_request_id(arguments)

    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="未提供 Token")

    token = authorization.replace("Bearer ", "").strip()
    auth_manager = UserAuthManager()
    is_valid, user_id = auth_manager.verify_token(token)

    if not is_valid or not user_id:
        raise HTTPException(status_code=401, detail="Token 无效或已过期")

    return inject_user_context(arguments, token=token, user_id=user_id, users_root=users_root)


def build_tool_kwargs(tool_func, arguments: Dict[str, Any]) -> Dict[str, Any]:
    try:
        sig = inspect.signature(tool_func)
        params = set(sig.parameters.keys())
    except Exception:
        params = set()

    uid = arguments.get("user_id") or arguments.get("_user_id")
    bp = arguments.get("basepath") or arguments.get("base_path") or arguments.get("_base_path")
    tok = arguments.get("token")

    kwargs: Dict[str, Any] = {}

    if "user_id" in params:
        kwargs["user_id"] = uid
    if "userid" in params:
        kwargs["userid"] = uid
    if "token" in params:
        kwargs["token"] = tok

    if "basepath" in params:
        kwargs["basepath"] = bp
    if "base_path" in params:
        kwargs["base_path"] = bp
    if "_base_path" in params:
        kwargs["_base_path"] = bp

    return kwargs


__all__ = [
    "new_request_id",
    "ensure_request_id",
    "inject_user_context",
    "auth_and_inject",
    "build_tool_kwargs",
]

