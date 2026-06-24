#!/usr/bin/env python3
"""
代码索引存储工具：读写 JSONL
"""

import json
from pathlib import Path
from typing import Iterable, Dict, Any, List

from core.user_context import get_user_ctx


def get_code_index_dir() -> Path:
    """
    返回当前用户的代码索引目录:
    {base}/indexes/code/
    """
    user_ctx = get_user_ctx()
    return Path(user_ctx.base) / "indexes" / "code"


def write_jsonl(path: Path, records: Iterable[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def read_jsonl(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    records = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return records

