#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Chat 系统导出（对外稳定入口）
- 这里负责对外稳定导出，避免包导入时触发整条 chat/doc/tool 运行链。
- 仅在访问具体导出符号时再延迟加载对应模块，降低测试 collection 阶段副作用。
"""

from importlib import import_module

_EXPORTS = {
    "nisb_chat_create": (".chat_history_tools", "nisb_chat_create"),
    "nisb_chat_history": (".chat_history_tools", "nisb_chat_history"),
    "nisb_chat_load": (".chat_history_tools", "nisb_chat_load"),
    "nisb_chat_rename": (".chat_history_tools", "nisb_chat_rename"),
    "nisb_chat_delete": (".chat_history_tools", "nisb_chat_delete"),
    "nisb_chat_update_labels": (".chat_history_tools", "nisb_chat_update_labels"),
    "nisb_chat_get_labels": (".chat_history_tools", "nisb_chat_get_labels"),
    "nisb_chat_list_labels": (".chat_history_tools", "nisb_chat_list_labels"),
    "nisb_chat_models": (".chat_models_tool", "nisb_chat_models"),
    "nisb_chat_send": (".chat_send_tool", "nisb_chat_send"),
    "nisb_chat_with_library_context": (".library_rag_tool", "nisb_chat_with_library_context"),
}

__all__ = [
    "nisb_chat_create",
    "nisb_chat_send",
    "nisb_chat_history",
    "nisb_chat_load",
    "nisb_chat_models",
    "nisb_chat_rename",
    "nisb_chat_delete",
    "nisb_chat_update_labels",
    "nisb_chat_get_labels",
    "nisb_chat_list_labels",
    "nisb_chat_with_library_context",
]


def __getattr__(name):
    export = _EXPORTS.get(name)
    if export:
        mod_name, attr_name = export
        value = getattr(import_module(mod_name, __name__), attr_name)
        globals()[name] = value
        return value
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__():
    return sorted(set(globals().keys()) | set(__all__))

