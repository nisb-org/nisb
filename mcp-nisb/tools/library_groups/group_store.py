#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import os
from typing import Any, Dict, List, Set, Tuple

from core.storage import load_jsonl
from tools.doc.core.dod_guard import require_safe_id


def _groups_jsonl_path(base_path: str) -> str:
    return os.path.join(base_path, "libraries", "library_groups.jsonl")


def fold_library_groups(rows: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """
    按 ID 折叠：以最后一条记录为准。
    - 最后一条是 tombstone => 删除
    - 最后一条是 library_group => 存在
    允许：tombstone 之后再次 upsert 复活（符合“按 ID 取最后状态”契约）
    """
    last_by_gid: Dict[str, Dict[str, Any]] = {}

    for it in rows:
        if not isinstance(it, dict):
            continue

        gid = str(it.get("group_id") or "").strip()
        if not gid:
            continue

        t = str(it.get("type") or "").strip()
        is_tombstone = (t == "library_group_tombstone") or bool(it.get("tombstone"))

        if is_tombstone:
            last_by_gid[gid] = {
                "type": "library_group_tombstone",
                "group_id": gid,
                "tombstone": True,
                "updated_at": it.get("updated_at"),
            }
            continue

        if t != "library_group":
            continue

        last_by_gid[gid] = it

    state: Dict[str, Dict[str, Any]] = {}
    for gid, rec in last_by_gid.items():
        if bool(rec.get("tombstone")) or str(rec.get("type") or "") == "library_group_tombstone":
            continue
        state[gid] = rec

    return state


def list_library_groups(base_path: str) -> List[Dict[str, Any]]:
    path = _groups_jsonl_path(base_path)
    rows = load_jsonl(path)
    mp = fold_library_groups(rows)

    out = list(mp.values())
    out.sort(key=lambda x: str(x.get("updated_at") or x.get("created_at") or ""), reverse=True)
    return out


def resolve_group_filter(base_path: str, group_id: str) -> Tuple[Set[str], Set[Tuple[str, str]]]:
    """
    返回：
    - allowed_libraries: set(library_id)          —— 该库全量 doc 允许
    - allowed_pairs: set((library_id, doc_id))   —— 仅允许这些 doc
    """
    gid = require_safe_id("group_id", group_id)

    groups = list_library_groups(base_path)
    g = next((x for x in groups if str(x.get("group_id") or "") == gid), None)
    if not g:
        raise ValueError(f"group_id 不存在: {gid}")

    members = g.get("members")
    if not isinstance(members, list) or not members:
        raise ValueError(f"group_id 成员为空: {gid}")

    allowed_libraries: Set[str] = set()
    allowed_pairs: Set[Tuple[str, str]] = set()

    for m in members:
        if not isinstance(m, dict):
            continue

        lid_raw = str(m.get("library_id") or "").strip()
        if not lid_raw:
            continue
        lid = require_safe_id("library_id", lid_raw)

        did_raw = m.get("doc_id")
        did = str(did_raw or "").strip() if did_raw is not None else ""

        if not did:
            allowed_libraries.add(lid)
            continue

        did = require_safe_id("doc_id", did)
        allowed_pairs.add((lid, did))

    if not allowed_libraries and not allowed_pairs:
        raise ValueError(f"group_id 成员解析为空: {gid}")

    return allowed_libraries, allowed_pairs

