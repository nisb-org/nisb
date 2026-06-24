#!/usr/bin/env python3
"""
一键补建/修复 doc_db.sqlite（T2 FTS5 版，零额外依赖）

目标：
- schema 以 tools/doc/doc_db_sqlite.py 为唯一真相
- published_at 从 metadata.json 回灌到 SQLite documents.published_at
- 不经过 tools.doc.__init__，不依赖 search_sqlite/openai/helpers/psutil
- 全量导入完成后显式重建 FTS5 索引，修复旧库 sparse 缺失或漂移
"""

from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
from types import ModuleType
from typing import List, Optional


_THIS_FILE = Path(__file__).resolve()
_THIS_DIR = _THIS_FILE.parent

DEFAULT_CHUNK_SIZE = 1200
DEFAULT_CHUNK_OVERLAP = 200


def _load_module_from_file(module_name: str, file_path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(module_name, str(file_path))
    if spec is None or spec.loader is None:
        raise ImportError(f"无法加载模块：{file_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_doc_db_sqlite = _load_module_from_file("_doc_db_sqlite_local", _THIS_DIR / "doc_db_sqlite.py")
get_doc_db_sqlite = _doc_db_sqlite.get_doc_db_sqlite


def _load_meta(meta_file: Path) -> dict:
    with meta_file.open("r", encoding="utf-8") as f:
        data = json.load(f)
    return data if isinstance(data, dict) else {}


def _load_text(text_file: Path) -> str:
    with text_file.open("r", encoding="utf-8") as f:
        return f.read()


def _normalize_text(v: object) -> Optional[str]:
    s = str(v or "").strip()
    return s or None


def _chunk_text_local(text: str, chunk_size: int, chunk_overlap: int) -> List[str]:
    raw = str(text or "")
    if not raw.strip():
        return []

    size = max(1, int(chunk_size or DEFAULT_CHUNK_SIZE))
    overlap = max(0, int(chunk_overlap or 0))
    if overlap >= size:
        overlap = max(0, size // 4)

    step = max(1, size - overlap)
    n = len(raw)
    chunks: List[str] = []

    start = 0
    while start < n:
        end = min(n, start + size)

        if end < n:
            tail = raw[start:end]
            split_positions = [
                tail.rfind("\n\n"),
                tail.rfind("\n"),
                tail.rfind("。"),
                tail.rfind("！"),
                tail.rfind("？"),
                tail.rfind(". "),
                tail.rfind("! "),
                tail.rfind("? "),
                tail.rfind("；"),
                tail.rfind(";"),
                tail.rfind("，"),
                tail.rfind(", "),
                tail.rfind(" "),
            ]
            best = max(split_positions)
            if best >= max(0, int(size * 0.55)):
                end = start + best + 1

        piece = raw[start:end].strip()
        if piece:
            chunks.append(piece)

        if end >= n:
            break

        next_start = max(start + 1, end - overlap)
        if next_start <= start:
            next_start = end
        start = next_start

    if not chunks and raw.strip():
        return [raw.strip()]
    return chunks


def rebuild_library_sqlite(
    *,
    user_base_path: str,
    library_id: str,
    rechunk: bool,
    limit: int,
    chunk_size: int,
    chunk_overlap: int,
) -> None:
    base = Path(user_base_path)
    library_path = base / "libraries" / library_id
    docs_dir = library_path / "docs"

    if not library_path.exists():
        raise SystemExit(f"❌ 库不存在：{library_path}")
    if not docs_dir.exists():
        raise SystemExit(f"❌ docs 目录不存在：{docs_dir}")

    db = get_doc_db_sqlite(user_base_path, library_id)

    doc_dirs = sorted([p for p in docs_dir.glob("doc_*") if p.is_dir()])
    if limit > 0:
        doc_dirs = doc_dirs[:limit]

    imported = 0
    skipped = 0
    failed = 0

    print(
        f"[INFO] 开始重建：library_id={library_id}, docs={len(doc_dirs)}, "
        f"rechunk={rechunk}, chunk_size={chunk_size}, chunk_overlap={chunk_overlap}"
    )

    for idx, doc_dir in enumerate(doc_dirs, start=1):
        meta_file = doc_dir / "metadata.json"
        content_file = doc_dir / "content.txt"

        if not meta_file.exists() or not content_file.exists():
            skipped += 1
            print(f"[WARN] 跳过：缺少 metadata/content：{doc_dir.name}")
            continue

        try:
            meta = _load_meta(meta_file)

            doc_id = _normalize_text(meta.get("doc_id")) or doc_dir.name
            filename = _normalize_text(meta.get("filename")) or doc_dir.name
            filetype = _normalize_text(meta.get("filetype")) or "txt"
            uploaded_at = _normalize_text(meta.get("uploaded_at"))
            published_at = _normalize_text(meta.get("published_at")) or uploaded_at
            language = _normalize_text(meta.get("language")) or "auto"

            text = _load_text(content_file)
            file_size = content_file.stat().st_size

            if rechunk:
                chunk_texts = _chunk_text_local(text, chunk_size, chunk_overlap)
            else:
                chunk_texts = _chunk_text_local(text, chunk_size, chunk_overlap)

            if not chunk_texts:
                fallback = text.strip()
                chunk_texts = [fallback[:2000]] if fallback else []

            db.upsert_document_with_chunks(
                doc_id=doc_id,
                library_id=library_id,
                filename=filename,
                filetype=filetype,
                file_size=file_size,
                chunk_texts=chunk_texts,
                uploaded_at=uploaded_at,
                published_at=published_at,
                language=language,
            )

            imported += 1
            if imported % 10 == 0 or idx == len(doc_dirs):
                print(
                    f"[INFO] 进度：{idx}/{len(doc_dirs)}，"
                    f"已导入={imported}，跳过={skipped}，失败={failed}"
                )

        except Exception as e:
            failed += 1
            print(f"[ERROR] 导入失败：{doc_dir.name}：{e}")

    print("[INFO] 开始重建 FTS5 索引 ...")
    rebuild_result = db.rebuild_fts_index()
    if not rebuild_result.get("ok"):
        raise SystemExit(f"❌ FTS5 重建失败：{rebuild_result.get('error') or 'unknown_error'}")

    print(
        "[INFO] FTS5 重建完成："
        f"indexed_docs={int(rebuild_result.get('indexed_docs') or 0)}, "
        f"indexed_chunks={int(rebuild_result.get('indexed_chunks') or 0)}"
    )

    print(
        f"✅ 重建完成：已导入={imported}，跳过={skipped}，失败={failed}，"
        f"FTS文档={int(rebuild_result.get('indexed_docs') or 0)}，"
        f"FTS块={int(rebuild_result.get('indexed_chunks') or 0)}"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Rebuild doc_db.sqlite for one library (T2 FTS5 version, standalone).")
    parser.add_argument("--user-base", required=True, help="用户根目录，例如 /opt/nisb-data/users/{uid}")
    parser.add_argument("--library", required=True, help="library_id，例如 philosophy")
    parser.add_argument(
        "--rechunk",
        action="store_true",
        help="从 content.txt 重新分块并覆盖 chunks（推荐开启）",
    )
    parser.add_argument("--limit", type=int, default=0, help="只处理前 N 本（0 表示不限制）")
    parser.add_argument("--chunk-size", type=int, default=DEFAULT_CHUNK_SIZE, help="分块大小，默认 1200")
    parser.add_argument("--chunk-overlap", type=int, default=DEFAULT_CHUNK_OVERLAP, help="分块重叠，默认 200")
    args = parser.parse_args()

    rebuild_library_sqlite(
        user_base_path=args.user_base,
        library_id=args.library,
        rechunk=bool(args.rechunk),
        limit=int(args.limit),
        chunk_size=int(args.chunk_size),
        chunk_overlap=int(args.chunk_overlap),
    )


if __name__ == "__main__":
    main()
