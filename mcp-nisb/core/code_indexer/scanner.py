#!/usr/bin/env python3
"""
扫描 NISB 代码镜像目录，生成代码索引 JSONL

- 镜像目录默认约定：
  {user_ctx.base}/agent_files/projects/nisb-core/

- 索引文件：
  {base}/indexes/code/code_index_files.jsonl
  {base}/indexes/code/code_index_symbols.jsonl
"""

import ast
import os
from pathlib import Path
from typing import List, Dict, Any, Optional

from core.user_context import get_user_ctx
from core.openai_utils import get_embedding, call_llm
from .index_store import (
    get_code_index_dir,
    write_jsonl,
)


def iter_py_files(root: Path) -> List[Path]:
    for dirpath, dirnames, filenames in os.walk(root):
        # 排除常见无关目录
        dirnames[:] = [
            d for d in dirnames
            if d not in ("__pycache__", ".git", ".venv", "node_modules", ".idea", ".vscode")
        ]
        for fn in filenames:
            if fn.endswith(".py"):
                yield Path(dirpath) / fn


def summarize_file(path: Path) -> str:
    """
    用 mini 为文件写简短职责说明
    """
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return f"Python 文件 {path.name}"

    head = text[:4000]

    system_prompt = (
        "你在帮用户为一个 Python 源码文件写简短说明。\n"
        "用一句简短的话描述这个文件在整个 NISB 系统中的主要职责，中文。\n"
        "不要输出代码，只输出一句话描述。"
    )
    user_prompt = f"文件路径：{path.name}\n\n部分代码内容：\n{head}\n\n请用一句话描述该文件的职责。"

    try:
        summary = call_llm(
            model="gpt-4o-mini",
            system_prompt=system_prompt,
            user_prompt=user_prompt,
        )
        if isinstance(summary, str):
            return summary.strip()
        return str(summary)
    except Exception:
        return f"Python 文件 {path.name}"


def extract_symbols(path: Path) -> List[Dict[str, Any]]:
    """
    用 ast 提取函数/类名称、签名和 docstring
    """
    try:
        src = path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return []

    try:
        tree = ast.parse(src)
    except SyntaxError:
        return []

    symbols = []

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            name = node.name
            kind = "class" if isinstance(node, ast.ClassDef) else "function"
            doc = ast.get_docstring(node) or ""
            start_line = getattr(node, "lineno", None)
            end_line = getattr(node, "end_lineno", None)

            if isinstance(node, ast.ClassDef):
                signature = f"class {name}(...)"
            else:
                signature = f"def {name}(...)"

            symbols.append({
                "kind": kind,
                "name": name,
                "signature": signature,
                "docstring": doc,
                "start_line": start_line,
                "end_line": end_line,
            })

    return symbols


def summarize_symbol(file_path: Path, symbol: Dict[str, Any]) -> str:
    """
    用 mini 为函数/类写一句话说明
    """
    name = symbol["name"]
    kind = symbol["kind"]
    doc = symbol.get("docstring") or ""

    system_prompt = (
        "你在帮用户为一个 Python 函数或类写简短说明。\n"
        "用一句简短的话描述它在整个 NISB 系统中的职责，中文。"
    )
    user_prompt = (
        f"文件：{file_path.name}\n"
        f"类型：{kind}\n"
        f"名称：{name}\n"
        f"Docstring：{doc}\n\n"
        "请用一句话描述它在系统中的职责。"
    )

    try:
        summary = call_llm(
            model="gpt-4o-mini",
            system_prompt=system_prompt,
            user_prompt=user_prompt,
        )
        if isinstance(summary, str):
            return summary.strip()
        return str(summary)
    except Exception:
        return f"{kind} {name}（无详细说明）"


def get_default_source_root() -> Path:
    """
    默认代码镜像目录：
    {base}/agent_files/projects/nisb-core/
    """
    user_ctx = get_user_ctx()
    return Path(user_ctx.base) / "agent_files" / "projects" / "nisb-core"


def build_code_index(
    source_root: Optional[str] = None,
    verbose: bool = True,
) -> Dict[str, Any]:
    """
    构建代码镜像目录的索引：
    - 文件级索引：code_index_files.jsonl
    - 符号级索引：code_index_symbols.jsonl

    默认扫描：
    {user_ctx.base}/agent_files/projects/nisb-core/
    """
    user_ctx = get_user_ctx()
    root = Path(source_root) if source_root else get_default_source_root()
    index_dir = get_code_index_dir()
    index_dir.mkdir(parents=True, exist_ok=True)

    if not root.exists():
        return {
            "status": "error",
            "message": f"代码镜像目录不存在: {root}\n"
                       f"请先通过文件系统工具创建目录并将代码复制到此处。",
            "index_dir": str(index_dir),
            "source_root": str(root),
        }

    file_index_path = index_dir / "code_index_files.jsonl"
    symbol_index_path = index_dir / "code_index_symbols.jsonl"

    file_records = []
    symbol_records = []

    if verbose:
        print(f"[code_indexer] 扫描代码镜像目录: {root}")

    for py_path in iter_py_files(root):
        rel_path = py_path.relative_to(root)
        rel_str = str(rel_path)

        if verbose:
            print(f"[code_indexer] 处理文件: {rel_str}")

        # 文件级
        file_summary = summarize_file(py_path)
        file_emb = get_embedding(file_summary)

        file_records.append({
            "path": rel_str,            # 相对镜像根目录的路径
            "summary": file_summary,
            "embedding": file_emb,
        })

        # 符号级
        symbols = extract_symbols(py_path)
        for sym in symbols:
            sym_summary = summarize_symbol(py_path, sym)
            sym_emb = get_embedding(sym_summary + " " + sym["signature"])

            symbol_records.append({
                "path": rel_str,
                "kind": sym["kind"],
                "name": sym["name"],
                "signature": sym["signature"],
                "summary": sym_summary,
                "start_line": sym.get("start_line"),
                "end_line": sym.get("end_line"),
                "embedding": sym_emb,
            })

    write_jsonl(file_index_path, file_records)
    write_jsonl(symbol_index_path, symbol_records)

    if verbose:
        print(f"[code_indexer] 文件索引写入: {file_index_path} ({len(file_records)} 条)")
        print(f"[code_indexer] 符号索引写入: {symbol_index_path} ({len(symbol_records)} 条)")

    return {
        "status": "success",
        "message": "代码索引构建完成",
        "files": len(file_records),
        "symbols": len(symbol_records),
        "index_dir": str(index_dir),
        "source_root": str(root),
        "user_base": user_ctx.base,
    }

