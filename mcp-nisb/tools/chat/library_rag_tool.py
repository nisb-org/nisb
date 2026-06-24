#!/usr/bin/env python3
"""
MCP 工具：nisb_chat_with_library_context

在对话时，从指定库中检索上下文并调用 LLM 生成回答。
（修复版：签名统一为 tool(args)->dict，兼容 auto_user_context）
"""

from typing import Any, Dict, List

from core.user_context import auto_user_context, get_user_ctx
from .library_rag_core import answer_with_library_context


@auto_user_context
def nisb_chat_with_library_context(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    参数：
    - message: str，必填
    - library_ids: List[str]，可选
    - top_k: int，可选
    - model: str，可选
    """
    user_ctx = get_user_ctx()
    base_path = user_ctx.base
    user_id = str(user_ctx.user_id)

    message = str(args.get("message") or "").strip()
    if not message:
        return {"status": "error", "message": "参数 message 不能为空。"}

    library_ids: List[str] = args.get("library_ids") or []
    if not isinstance(library_ids, list):
        return {"status": "error", "message": "参数 library_ids 必须是字符串数组。"}

    top_k = int(args.get("top_k", 8) or 8)
    model = str(args.get("model") or "").strip() or None

    rag_result = answer_with_library_context(
        base_path=base_path,
        conversation_meta={"user_id": user_id, "conversation_id": args.get("conversation_id")},
        user_message=message,
        library_ids=library_ids,
        top_k=top_k,
        model=model,
    )

    return {
        "status": "success",
        "response": rag_result.get("answer") or "",
        "contexts": rag_result.get("contexts") or [],
        "model": rag_result.get("model") or (model or "gpt-4o-mini"),
    }

