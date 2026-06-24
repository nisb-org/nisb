#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, Optional


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha256_text(s: str) -> str:
    h = hashlib.sha256()
    h.update((s or "").encode("utf-8", errors="ignore"))
    return h.hexdigest()


def cache_path(doc_dir: str) -> str:
    # 放 index 下：更像“可再生索引/缓存”
    idx_dir = os.path.join(doc_dir, "index")
    os.makedirs(idx_dir, exist_ok=True)
    return os.path.join(idx_dir, "chunk_offsets.json")


def load_cache(doc_dir: str, full_text: str) -> Optional[Dict[str, Any]]:
    fp = cache_path(doc_dir)
    if not os.path.exists(fp):
        return None
    try:
        obj = json.load(open(fp, "r", encoding="utf-8"))
        if not isinstance(obj, dict):
            return None
        if obj.get("full_text_sha256") != _sha256_text(full_text):
            return None
        offsets = obj.get("offsets")
        if not isinstance(offsets, dict):
            return None
        return obj
    except Exception:
        return None


def save_cache(doc_dir: str, full_text: str, offsets: Dict[str, int]) -> bool:
    fp = cache_path(doc_dir)
    tmp = fp + ".tmp"

    payload = {
        "version": 1,
        "generated_at": _utc_now_iso(),
        "full_text_sha256": _sha256_text(full_text),
        "offsets": {str(k): int(v) for k, v in (offsets or {}).items() if v is not None and int(v) >= 0},
    }

    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        os.replace(tmp, fp)
        return True
    except Exception:
        try:
            if os.path.exists(tmp):
                os.remove(tmp)
        except Exception:
            pass
        return False


def get_offsets_map(doc_dir: str, full_text: str) -> Dict[str, int]:
    obj = load_cache(doc_dir, full_text)
    if obj and isinstance(obj.get("offsets"), dict):
        return {str(k): int(v) for k, v in obj["offsets"].items()}
    return {}

def build_offsets_sequential(full_text: str, chunks: list[dict]) -> dict[str, int]:
    """
    生产级：按 chunk_id 顺序从前往后找，避免“重复文本被匹配到更早位置”。
    只使用 .find(needle, cursor)；找不到时退化为“归一化空白后”再找一次。
    """
    def norm(s: str) -> str:
        return " ".join((s or "").replace("\r", "\n").split())

    offsets: dict[str, int] = {}
    if not full_text:
        return offsets

    cursor = 0
    n = len(full_text)

    for c in (chunks or []):
        ck = str(c.get("chunk_id"))
        txt = str(c.get("text") or "").strip()
        if not ck or not txt:
            continue

        # 1) exact forward find
        pos = full_text.find(txt, cursor)

        # 2) normalized forward find（仅在 exact 失败时）
        if pos < 0:
            nf = norm(full_text[cursor:])  # 只对剩余部分做归一化
            nt = norm(txt)
            if nf and nt:
                p2 = nf.find(nt)
                if p2 >= 0:
                    # 把“归一化后的位置”近似映射回 raw：用 cursor 作为锚，保守回退
                    # 这里不追求 100% 精确到字符（因为我们最终是 span 级别）
                    pos = cursor + max(0, p2)

        if pos < 0:
            # 找不到：不写入（后续 evidence 可回退，但不会污染缓存）
            continue

        offsets[ck] = int(pos)

        # cursor 前进：强制单调递增，避免后续 chunk 匹配到更早位置
        cursor = min(n, pos + max(1, len(txt) - 16))

    return offsets

def _norm_ws(s: str) -> str:
    return " ".join((s or "").replace("\r", "\n").split())


def verify_offset(full_text: str, chunk_text: str, offset: int) -> bool:
    """
    验证 offset 是否合理：
    - 不要求 raw 完全一致（因为 chunk 可能有空白差异）
    - 用归一化后的前缀做校验，降低误判
    """
    if offset is None or offset < 0:
        return False
    if not full_text or not chunk_text:
        return False
    a = full_text[offset : offset + min(600, len(full_text) - offset)]
    na = _norm_ws(a)
    nb = _norm_ws(chunk_text)
    if not na or not nb:
        return False
    return na.startswith(nb[:200])


def find_with_anchor(
    full_text: str,
    chunk_text: str,
    *,
    anchor: int,
    window: int = 60000,
    backtrack: int = 2000,
) -> tuple[int, str]:
    """
    在 anchor 附近窗口内找 chunk：
    返回 (offset, method)，找不到则 (-1,"miss")
    """
    if not full_text:
        return -1, "miss"
    t = (chunk_text or "").strip()
    if not t:
        return -1, "miss"

    n = len(full_text)
    anchor = max(0, min(int(anchor or 0), n))
    s0 = max(0, anchor - int(backtrack))
    e0 = min(n, anchor + int(window))
    sub = full_text[s0:e0]

    # 1) window exact
    pos = sub.find(t)
    if pos >= 0:
        return s0 + pos, "window_exact"

    # 2) window normalized
    ns = _norm_ws(sub)
    nt = _norm_ws(t)
    if ns and nt:
        p2 = ns.find(nt)
        if p2 >= 0:
            # 归一化位置近似映射回 raw：用 s0 作为锚点
            return s0 + p2, "window_norm"

    # 3) prefix-only（更稳：避免整段因少量差异找不到）
    pref = t[:240]
    if len(pref) >= 80:
        p3 = sub.find(pref)
        if p3 >= 0:
            return s0 + p3, "window_prefix"

    return -1, "miss"


def build_offsets_sequential_v2(full_text: str, chunks: list[dict]) -> tuple[dict[str, int], dict[str, str]]:
    """
    生产级：按 chunk_id 顺序构建 offset，且保证 offset 单调递增。
    同时返回 methods（用于 debug/排查）。
    """
    offsets: dict[str, int] = {}
    methods: dict[str, str] = {}
    if not full_text:
        return offsets, methods

    cursor = 0
    for c in (chunks or []):
        ck = str(c.get("chunk_id"))
        txt = str(c.get("text") or "")
        if not ck or not txt.strip():
            continue

        off, method = find_with_anchor(full_text, txt, anchor=cursor)

        # 找到了但验证失败：视为 miss（避免污染缓存）
        if off >= 0 and (not verify_offset(full_text, txt, off)):
            off = -1
            method = "verify_fail"

        if off < 0:
            continue

        offsets[ck] = int(off)
        methods[ck] = method

        # cursor 单调前进：避免后续 chunk 匹配到更早位置
        cursor = min(len(full_text), off + max(1, len(txt) - 16))

    return offsets, methods

