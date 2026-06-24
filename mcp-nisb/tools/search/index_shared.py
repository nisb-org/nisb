#!/usr/bin/env python3

import json
import os
import re
from pathlib import Path
from typing import Any, Dict, List

from .common import (
    JSON_EXTENSIONS,
    MIN_SYNC_INTERVAL,
    TEXT_EXTENSIONS_NO_JSON,
    build_index_excerpt,
    dedupe_keep_order,
    read_text_cached,
)

SCHEMA_VERSION = "search_index_v9_shared_budgeted_blocks"
CONTENT_FALLBACK_SCAN_LIMIT = 80
SNIPPET_EXCERPT_CHARS = 640
CHAT_TURN_EXCERPT_CHARS = 720
CHAT_PREVIEW_EXCERPT_CHARS = 860

TEXTUAL_SUFFIXES = tuple(sorted(set(TEXT_EXTENSIONS_NO_JSON + JSON_EXTENSIONS)))
TEXTUAL_SUFFIX_SET = set(TEXTUAL_SUFFIXES)
FTS_RESERVED = {"and", "or", "not", "near"}
LOCAL_MIN_SYNC_INTERVAL = max(float(MIN_SYNC_INTERVAL), 0.5)

CONTENT_BLOCK_FULL_COVER_MAX_CHARS = 1800
CONTENT_BLOCK_TOTAL_BUDGET_CHARS = 2600
CONTENT_BLOCK_MIN_CHUNK_CHARS = 220
CONTENT_BLOCK_MAX_CHUNK_CHARS = 360


def safe_rel(path: Path, base_path: Path) -> str:
    try:
        return path.relative_to(base_path).as_posix()
    except Exception:
        return path.as_posix()


def read_small_excerpt(path: Path, max_chars: int = SNIPPET_EXCERPT_CHARS) -> str:
    try:
        if not path.exists() or not path.is_file():
            return ""

        text = read_text_cached(path)
        if text:
            return build_index_excerpt(text, max_chars=max_chars)

        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            text = f.read(max_chars * 2)
        return build_index_excerpt(text, max_chars=max_chars)
    except Exception:
        return ""


def strip_book_suffix(text: str) -> str:
    s = str(text or "").strip()
    if not s:
        return ""
    s = re.sub(r"\.[A-Za-z0-9]+$", "", s)
    s = re.sub(r"(?:[pc]\d{2,6}_\d{2,6})$", "", s, flags=re.IGNORECASE)
    s = re.sub(r"(?:[_\-]?\d{2,6})$", "", s)
    s = re.sub(r"\s+", " ", s).strip(" _-")
    return s.strip()


def derive_title_aliases(*values: str) -> List[str]:
    aliases: List[str] = []
    for value in values:
        raw = str(value or "").strip()
        if not raw:
            continue

        aliases.append(raw)

        if "." in raw:
            aliases.append(Path(raw).stem)

        stripped = strip_book_suffix(raw)
        if stripped:
            aliases.append(stripped)

        if "." in raw:
            stem = Path(raw).stem
            stem_stripped = strip_book_suffix(stem)
            if stem_stripped:
                aliases.append(stem_stripped)

    aliases = [a.strip() for a in aliases if str(a or "").strip()]
    return dedupe_keep_order(aliases)


def is_textual_file(path: Path) -> bool:
    return path.suffix.lower() in TEXTUAL_SUFFIX_SET


def _normalize_block_text(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()


def _clamp_int(value: int, low: int, high: int) -> int:
    return max(int(low), min(int(high), int(value)))


def _slice_chunk(cleaned: str, start: int, chunk_len: int) -> str:
    if not cleaned:
        return ""
    max_start = max(0, len(cleaned) - chunk_len)
    start = max(0, min(max_start, int(start)))
    return cleaned[start:start + chunk_len].strip()


def _contiguous_positions(text_len: int, chunk_len: int, count: int, start_at: int = 0) -> List[int]:
    if text_len <= 0 or chunk_len <= 0 or count <= 0:
        return []

    out: List[int] = []
    max_start = max(0, text_len - chunk_len)
    start = max(0, min(max_start, int(start_at)))

    for _ in range(count):
        out.append(start)
        start += chunk_len
        if start > max_start:
            break

    return dedupe_keep_order(out)


def _budgeted_positions(text_len: int, chunk_len: int, max_blocks: int) -> List[int]:
    if text_len <= 0 or chunk_len <= 0 or max_blocks <= 0:
        return []

    if text_len <= chunk_len * max_blocks:
        return _contiguous_positions(text_len, chunk_len, max_blocks, start_at=0)

    if max_blocks == 1:
        return [0]

    if max_blocks == 2:
        return dedupe_keep_order([0, max(0, text_len - chunk_len)])

    head_blocks = 2 if max_blocks <= 4 else 3
    tail_blocks = 1 if max_blocks <= 4 else 2
    if head_blocks + tail_blocks > max_blocks:
        head_blocks = max(1, max_blocks - 1)
        tail_blocks = 1

    middle_blocks = max(0, max_blocks - head_blocks - tail_blocks)
    max_start = max(0, text_len - chunk_len)

    positions: List[int] = []

    positions.extend(_contiguous_positions(text_len, chunk_len, head_blocks, start_at=0))

    if middle_blocks > 0:
        interior_start = min(max_start, head_blocks * chunk_len)
        tail_start = max(0, text_len - tail_blocks * chunk_len)
        interior_end = max(interior_start, tail_start - chunk_len)

        if interior_end > interior_start:
            span = interior_end - interior_start
            step = span / float(middle_blocks + 1)
            for i in range(middle_blocks):
                raw_pos = interior_start + int(round((i + 1) * step))
                raw_pos = max(0, min(max_start, raw_pos))
                positions.append(raw_pos)

    tail_start = max(0, text_len - tail_blocks * chunk_len)
    positions.extend(_contiguous_positions(text_len, chunk_len, tail_blocks, start_at=tail_start))

    return dedupe_keep_order([max(0, min(max_start, p)) for p in positions])


def build_content_blocks(
    text: str,
    block_chars: int = 420,
    max_blocks: int = 6,
) -> List[str]:
    cleaned = _normalize_block_text(text)
    if not cleaned:
        return []

    block_chars = max(120, int(block_chars or 420))
    max_blocks = max(1, int(max_blocks or 1))

    chunk_len = _clamp_int(
        block_chars,
        CONTENT_BLOCK_MIN_CHUNK_CHARS,
        CONTENT_BLOCK_MAX_CHUNK_CHARS,
    )

    full_cover_limit = min(
        chunk_len * max_blocks,
        CONTENT_BLOCK_FULL_COVER_MAX_CHARS,
    )

    if len(cleaned) <= full_cover_limit:
        need_blocks = max(1, min(max_blocks, (len(cleaned) + chunk_len - 1) // chunk_len))
        positions = _contiguous_positions(len(cleaned), chunk_len, need_blocks, start_at=0)
    else:
        budget_chars = min(
            chunk_len * max_blocks,
            CONTENT_BLOCK_TOTAL_BUDGET_CHARS,
        )
        budget_blocks = max(1, budget_chars // chunk_len)
        budget_blocks = max(3, min(max_blocks, budget_blocks))
        positions = _budgeted_positions(len(cleaned), chunk_len, budget_blocks)

    blocks: List[str] = []
    for pos in positions[:max_blocks]:
        chunk = _slice_chunk(cleaned, pos, chunk_len)
        if chunk:
            blocks.append(chunk)

    if not blocks:
        blocks.append(cleaned[:chunk_len])

    return dedupe_keep_order(blocks[:max_blocks])


def load_chat_turns(turns_file: Path) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    if not turns_file.exists():
        return out

    try:
        with open(turns_file, "r", encoding="utf-8") as f:
            for line in f:
                line = str(line or "").strip()
                if not line:
                    continue
                try:
                    item = json.loads(line)
                except Exception:
                    continue

                content = str(item.get("content", "") or "").strip()
                if not content:
                    continue

                out.append(
                    {
                        "sequence": int(item.get("sequence", 0) or 0),
                        "turn_type": str(item.get("turn_type", "") or ""),
                        "timestamp": str(item.get("timestamp", "") or ""),
                        "content": content,
                    }
                )
    except Exception:
        return []

    return out


def chat_preview_fast(conv_dir: Path) -> str:
    conv_file = conv_dir / "conversation.json"
    turns_file = conv_dir / "turns.jsonl"

    title = ""
    if conv_file.exists():
        try:
            with open(conv_file, "r", encoding="utf-8") as f:
                meta = json.load(f)
            title = str(meta.get("title", "") or "")
        except Exception:
            title = ""

    turn_texts: List[str] = []
    for turn in load_chat_turns(turns_file)[:8]:
        role = str(turn.get("turn_type", "") or "").strip()
        content = str(turn.get("content", "") or "").strip()
        if not content:
            continue
        if role:
            turn_texts.append(f"{role}: {content}")
        else:
            turn_texts.append(content)

    joined = " ".join([title] + turn_texts)
    return build_index_excerpt(joined, max_chars=CHAT_PREVIEW_EXCERPT_CHARS)


def scan_dir_paths(root: Path, recursive: bool = True) -> List[Path]:
    if not root.exists() or not root.is_dir():
        return []

    out: List[Path] = []
    stack = [root]

    while stack:
        current = stack.pop()
        try:
            with os.scandir(current) as it:
                for entry in it:
                    try:
                        if not entry.is_dir(follow_symlinks=False):
                            continue
                        p = Path(entry.path)
                        out.append(p)
                        if recursive:
                            stack.append(p)
                    except Exception:
                        continue
        except Exception:
            continue

    return out
