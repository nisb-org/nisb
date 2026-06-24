from __future__ import annotations

import os
import json
import shutil
from typing import Any, Dict, List, Optional, Tuple

from .audit_log import append_fs_audit_event


def _ctx(args: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "user_id": args.get("user_id"),
        "email": args.get("_librechat_email") or args.get("email"),
        "name": args.get("_librechat_name") or args.get("name"),
    }


def _base(args: Dict[str, Any]) -> str:
    base = args.get("base_path") or args.get("_base_path")
    if not base or not isinstance(base, str):
        raise ValueError("缺少 base_path/_base_path（网关应注入）")
    return base.rstrip("/")


def _trash_root_abs(base: str) -> str:
    return os.path.join(base, "agent_files", ".trash")


def _rel(base: str, abs_path: str) -> str:
    return os.path.relpath(abs_path, base).replace("\\", "/")


def _read_json(path: str) -> Optional[Dict[str, Any]]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def _find_manifest_by_bulk_id(base: str, bulk_id: str) -> Tuple[Optional[str], Optional[Dict[str, Any]]]:
    trash_root = _trash_root_abs(base)
    if not os.path.isdir(trash_root):
        return None, None

    for dirpath, _, filenames in os.walk(trash_root):
        if ".nisb_manifest.json" not in filenames:
            continue
        mp = os.path.join(dirpath, ".nisb_manifest.json")
        data = _read_json(mp)
        if not data:
            continue
        if str(data.get("bulk_id") or "").strip() == bulk_id:
            return mp, data
    return None, None


def _safe_under(base_dir: str, path: str) -> bool:
    try:
        base_real = os.path.realpath(base_dir)
        path_real = os.path.realpath(path)
        return os.path.commonpath([base_real, path_real]) == base_real
    except Exception:
        return False

def nisb_fs_trash_batch_get(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    获取某个批次（bulk_id）的真实目录树条目（支持 query/分页）。
    关键修复：
    - 只展示本批次删除的根路径（manifest.items[*].original_rel）下面的内容
    - 不再展示 bucket 内的容器目录（比如 agent_files 本身）
    """
    base = _base(args)

    bulk_id = str(args.get("bulk_id") or "").strip()
    if not bulk_id:
        return {"success": False, "message": "缺少参数：bulk_id"}

    query = str(args.get("query") or "").strip().lower()
    offset = int(args.get("offset", 0) or 0)
    limit = int(args.get("limit", 200) or 200)

    offset = max(0, offset)
    limit = max(1, min(limit, 2000))

    mp, manifest = _find_manifest_by_bulk_id(base, bulk_id)
    if not mp or not manifest:
        return {"success": False, "message": f"未找到批次：{bulk_id}"}

    bucket_abs = os.path.dirname(mp)
    bucket_rel = str(manifest.get("bucket_rel") or _rel(base, bucket_abs)).replace("\\", "/")

    # 本批次“删除根路径”（可能多项）
    raw_items = manifest.get("items") or []
    roots: List[str] = []
    if isinstance(raw_items, list):
        for it in raw_items:
            if not isinstance(it, dict):
                continue
            r = str(it.get("original_rel") or "").strip().replace("\\", "/")
            if r:
                roots.append(r)

    # 去重 + 按长度长的优先（便于过滤）
    roots = sorted(list(set(roots)), key=lambda x: len(x), reverse=True)

    scan_root = os.path.join(bucket_abs, "agent_files")
    items: List[Dict[str, Any]] = []

    def should_include(original_rel: str, trash_rel: str) -> bool:
        if not original_rel or original_rel == "agent_files":
            return False
        # 过滤 manifest 文件本身
        if original_rel.endswith("/.nisb_manifest.json") or trash_rel.endswith("/.nisb_manifest.json"):
            return False
        # 只展示 roots 子树
        if roots:
            hit = False
            for r in roots:
                if original_rel == r or original_rel.startswith(r + "/"):
                    hit = True
                    break
            if not hit:
                return False
        # query
        if query:
            hay = (original_rel + " " + trash_rel).lower()
            if query not in hay:
                return False
        return True

    def add_item(abs_path: str, typ: str) -> None:
        tr = _rel(base, abs_path)  # agent_files/.trash/.../agent_files/xxx
        rel_inside = os.path.relpath(abs_path, bucket_abs).replace("\\", "/")  # agent_files/xxx
        original_rel = rel_inside

        if not should_include(original_rel, tr):
            return

        try:
            st = os.stat(abs_path)
            size = int(st.st_size) if typ == "file" else None
            mtime = int(st.st_mtime)
        except Exception:
            size = None
            mtime = None

        items.append(
            {
                "original_rel": original_rel,
                "trash_rel": tr,
                "type": typ,
                "size": size,
                "mtime": mtime,
            }
        )

    if os.path.isdir(scan_root):
        for dirpath, dirnames, filenames in os.walk(scan_root):
            # 不把 scan_root(容器)当条目加入
            if os.path.realpath(dirpath) != os.path.realpath(scan_root):
                add_item(dirpath, "directory")
            for fn in filenames:
                add_item(os.path.join(dirpath, fn), "file")

    items.sort(key=lambda x: (0 if x.get("type") == "directory" else 1, x.get("original_rel") or ""))
    total = len(items)
    page_items = items[offset : offset + limit]

    return {
        "success": True,
        "bulk_id": bulk_id,
        "bucket_rel": bucket_rel,
        "manifest_rel": _rel(base, mp),
        "roots": roots,
        "total": total,
        "offset": offset,
        "limit": limit,
        "items": page_items,
    }

def nisb_fs_trash_batch_purge(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    永久清空某个批次：删除该批次 bucket 目录（包含 .nisb_manifest.json 与所有回收站内容）。
    args:
      - bulk_id: string (required)
    """
    ctx = _ctx(args)
    user_id = ctx.get("user_id")
    email = ctx.get("email")
    name = ctx.get("name")

    base = _base(args)

    bulk_id = str(args.get("bulk_id") or "").strip()
    if not bulk_id:
        return {"success": False, "message": "缺少参数：bulk_id"}

    mp, manifest = _find_manifest_by_bulk_id(base, bulk_id)
    if not mp or not manifest:
        return {"success": False, "message": f"未找到批次：{bulk_id}"}

    bucket_abs = os.path.dirname(mp)
    trash_root = _trash_root_abs(base)

    # 强校验：必须在 agent_files/.trash 下，防止路径穿越/误删 [web:689][web:700]
    if not _safe_under(trash_root, bucket_abs):
        return {"success": False, "message": "PURGE_DENIED: 非法 bucket 路径"}

    # 递归删除整个 bucket（永久不可恢复）[web:686]
    shutil.rmtree(bucket_abs, ignore_errors=False)

    try:
        append_fs_audit_event(
            user_id=user_id,
            email=email,
            name=name,
            event={
                "event": "trash_batch_purge",
                "operation": "trash_batch_purge",
                "batch_id": bulk_id,
                "paths": [],
                "metadata": {
                    "bucket_rel": _rel(base, bucket_abs),
                    "manifest_rel": _rel(base, mp),
                },
            },
        )
    except Exception as e:
        print(f"[WARN] audit trash_batch_purge failed: {e}")

    return {
        "success": True,
        "bulk_id": bulk_id,
        "message": f"🧹 已永久清空批次：{bulk_id}",
    }

