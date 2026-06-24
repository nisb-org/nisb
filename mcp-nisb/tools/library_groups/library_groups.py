#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any, Dict, List

from core.user_context import auto_user_context, get_user_ctx
from core.storage import append_jsonl, load_jsonl
from tools.doc.core.dod_guard import require_safe_id

from tools.library_groups.group_store import list_library_groups


def _groups_jsonl_path(base_path: str) -> str:
    return os.path.join(base_path, "libraries", "library_groups.jsonl")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clean_members(members: Any) -> List[Dict[str, Any]]:
    arr = members if isinstance(members, list) else []
    out: List[Dict[str, Any]] = []

    for it in arr:
        if not isinstance(it, dict):
            continue

        lid_raw = str(it.get("library_id") or "").strip()
        if not lid_raw:
            continue
        lid = require_safe_id("library_id", lid_raw)

        did_raw = it.get("doc_id")
        did = str(did_raw or "").strip() if did_raw is not None else ""

        if not did:
            out.append({"library_id": lid, "doc_id": None})
            continue

        did = require_safe_id("doc_id", did)
        out.append({"library_id": lid, "doc_id": did})

    seen = set()
    library_all = set(m["library_id"] for m in out if m.get("doc_id") is None)

    dedup: List[Dict[str, Any]] = []
    for m in out:
        lid = m.get("library_id")
        did = m.get("doc_id")
        if lid in library_all and did is not None:
            continue
        k = f"{lid}::{did or ''}"
        if k in seen:
            continue
        seen.add(k)
        dedup.append(m)

    return dedup


def _debug_groups_file(base_path: str) -> Dict[str, Any]:
    p = _groups_jsonl_path(base_path)
    exists = os.path.exists(p)
    size = os.path.getsize(p) if exists else 0
    try:
        rows = load_jsonl(p) if exists else []
        rows_count = len(rows) if isinstance(rows, list) else 0
    except Exception as e:
        rows_count = 0
        return {
            "base_path": base_path,
            "groups_jsonl_path": p,
            "exists": exists,
            "size_bytes": size,
            "rows_count": rows_count,
            "load_error": str(e),
        }

    return {
        "base_path": base_path,
        "groups_jsonl_path": p,
        "exists": exists,
        "size_bytes": size,
        "rows_count": rows_count,
    }


@auto_user_context
def nisb_library_group_upsert(args: Dict[str, Any]) -> Dict[str, Any]:
    user_ctx = get_user_ctx()
    base_path = user_ctx.base

    group_id = require_safe_id("group_id", str(args.get("group_id") or "").strip())
    group_name = str(args.get("group_name") or "").strip()
    if not group_name:
        return {"status": "error", "message": "group_name 不能为空"}

    members = _clean_members(args.get("members"))
    if not members:
        return {"status": "error", "message": "members 不能为空"}

    icon = str(args.get("icon") or "").strip() or "📚"
    color = str(args.get("color") or "").strip() or "#3B82F6"
    note = str(args.get("note") or "").strip()

    now = _now_iso()

    created_at = now
    try:
        existing = list_library_groups(base_path)
        found = next((x for x in existing if str(x.get("group_id") or "") == group_id), None)
        if found and str(found.get("created_at") or "").strip():
            created_at = str(found.get("created_at") or "").strip()
    except Exception:
        pass

    record = {
        "type": "library_group",
        "group_id": group_id,
        "group_name": group_name,
        "members": members,
        "icon": icon,
        "color": color,
        "note": note,
        "created_at": created_at,
        "updated_at": now,
    }

    ok = append_jsonl(_groups_jsonl_path(base_path), record)
    if not ok:
        return {"status": "error", "message": "append_jsonl 写入失败"}

    resp: Dict[str, Any] = {"status": "success", "message": f"upsert group: {group_id}", "group": record}
    if bool(args.get("debug")):
        resp["debug"] = _debug_groups_file(base_path)
    return resp


@auto_user_context
def nisb_library_group_list(args: Dict[str, Any]) -> Dict[str, Any]:
    user_ctx = get_user_ctx()
    base_path = user_ctx.base

    try:
        groups = list_library_groups(base_path)
        resp: Dict[str, Any] = {"status": "success", "groups": groups, "total": len(groups)}
        if bool(args.get("debug")):
            resp["debug"] = _debug_groups_file(base_path)
        return resp
    except Exception as e:
        resp = {"status": "error", "message": str(e), "groups": [], "total": 0}
        if bool(args.get("debug")):
            resp["debug"] = _debug_groups_file(base_path)
        return resp


@auto_user_context
def nisb_library_group_delete(args: Dict[str, Any]) -> Dict[str, Any]:
    user_ctx = get_user_ctx()
    base_path = user_ctx.base

    group_id = require_safe_id("group_id", str(args.get("group_id") or "").strip())
    now = _now_iso()

    record = {
        "type": "library_group_tombstone",
        "group_id": group_id,
        "tombstone": True,
        "updated_at": now,
    }

    ok = append_jsonl(_groups_jsonl_path(base_path), record)
    if not ok:
        return {"status": "error", "message": "append_jsonl 写入失败"}

    resp: Dict[str, Any] = {"status": "success", "message": f"deleted group: {group_id}"}
    if bool(args.get("debug")):
        resp["debug"] = _debug_groups_file(base_path)
    return resp

