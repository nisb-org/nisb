#!/usr/bin/env python3
"""
NISB Code Agent v0.1（阶段 1）

- 不依赖文件系统写入
- 只做代码索引构建 & 搜索
- 默认针对代码镜像目录：
  {user_ctx.base}/agent_files/projects/nisb-core/
"""

from typing import Dict

from core.user_context import auto_user_context
from core.code_indexer.scanner import build_code_index
from core.code_indexer.search import search_code_by_text, search_code_by_symbol


@auto_user_context
def nisb_code_build_index(args: Dict) -> Dict:
    """
    构建代码索引

    可选参数：
    - source_root: 源码根目录（默认使用代码镜像目录）
    - verbose: 是否输出详细日志（默认 True）
    """
    source_root = args.get("source_root")  # 默认 None → 使用镜像目录
    verbose = bool(args.get("verbose", True))
    return build_code_index(source_root=source_root, verbose=verbose)


@auto_user_context
def nisb_code_search(args: Dict) -> Dict:
    """
    根据自然语言在代码索引中检索文件/符号

    参数：
    - query: 查询文本（必填）
    - top_k: 返回数量（默认 8）
    """
    query = args.get("query")
    if not query:
        return {"status": "error", "message": "query 不能为空"}

    top_k = int(args.get("top_k", 8))
    result = search_code_by_text(query, top_k=top_k)
    return result

