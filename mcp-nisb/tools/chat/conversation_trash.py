from __future__ import annotations

import os
import json
import time
import uuid
import shutil
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from tools.filesystem.audit_log import append_fs_audit_event


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


def _conv_root(base: str) -> str:
    return os.path.join(base, "web_interactions", "conversations")


def _trash_root(base: str) -> str:
    return os.path.join(base, "web_interactions", ".trash_conversations")


def _rel(base: str, abs_path: str) -> str:
    return os.path.relpath(abs_path, base).replace("\\", "/")


def _read_json(path: str) -> Optional[Dict[str, Any]]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def _write_json(path: str, data: Dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _safe_under(base_dir: str, path: str) -> bool:
    try:
        base_real = os.path.realpath(base_dir)
        path_real = os.path.realpath(path)
        return os.path.commonpath([base_real, path_real]) == base_real
    except Exception:
        return False


def _find_conv_dir_by_id(base: str, conv_id: str) -> Optional[str]:
    """
    在 web_interactions/conversations/YYYY/MM/ 下定位 conv_id 目录。
    只扫描两级（年/月），符合你当前真实树结构。
    """
    root = _conv_root(base)
    if not os.path.isdir(root):
        return None

    for year in sorted(os.listdir(root)):
        ydir = os.path.join(root, year)
        if not (os.path.isdir(ydir) and year.isdigit()):
            continue
        for month in sorted(os.listdir(ydir)):
            mdir = os.path.join(ydir, month)
            if not (os.path.isdir(mdir) and month.isdigit()):
                continue
            cand = os.path.join(mdir, conv_id)
            if os.path.isdir(cand):
                return cand
    return None


def _find_manifest_by_bulk_id(base: str, bulk_id: str) -> Tuple[Optional[str], Optional[Dict[str, Any]]]:
    root = _trash_root(base)
    if not os.path.isdir(root):
        return None, None

    for dirpath, _, filenames in os.walk(root):
        if ".nisb_manifest.json" not in filenames:
            continue
        mp = os.path.join(dirpath, ".nisb_manifest.json")
        data = _read_json(mp)
        if not data:
            continue
        if str(data.get("bulk_id") or "").strip() == bulk_id:
            return mp, data
    return None, None


def _extract_conversation_display_name(conv_dir_abs: str, conv_id: str) -> str:
    """
    从 conversation.json 提取对话展示名。
    兼容字段：title/name/label/conversation_name；拿不到就回退 conv_id。
    """
    p = os.path.join(conv_dir_abs, "conversation.json")
    data = _read_json(p) or {}
    if not isinstance(data, dict):
        return conv_id

    # 常见字段（尽量不“发明结构”，只做安全兜底）
    for k in ("title", "name", "label", "conversation_name"):
        v = data.get(k)
        if isinstance(v, str) and v.strip():
            return v.strip()

    # 某些实现会把 meta 放在对象里
    for parent_key in ("conversation", "meta", "metadata"):
        parent = data.get(parent_key)
        if isinstance(parent, dict):
            for k in ("title", "name", "label"):
                v = parent.get(k)
                if isinstance(v, str) and v.strip():
                    return v.strip()

    return conv_id


def nisb_chat_conversation_trash_delete(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    软删除对话：把整个 conv_xxx 目录移入 web_interactions/.trash_conversations/<ts>__<bulk_id>/...
    args:
      - conv_id: string (required) 例：conv_20251117_004437
      - reason: string optional
    """
    ctx = _ctx(args)
    user_id, email, name = ctx.get("user_id"), ctx.get("email"), ctx.get("name")

    conv_id = str(args.get("conv_id") or "").strip()
    if not conv_id:
        return {"success": False, "message": "缺少参数：conv_id"}

    base = _base(args)
    src_abs = _find_conv_dir_by_id(base, conv_id)
    if not src_abs:
        return {"success": False, "message": f"未找到对话目录：{conv_id}"}

    bulk_id = f"conv_{uuid.uuid4().hex[:10]}"
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    bucket_abs = os.path.join(_trash_root(base), f"{ts}__{bulk_id}")

    # 保留原始相对路径层级，便于恢复到原位置
    original_rel = _rel(base, src_abs)  # web_interactions/conversations/2025/11/conv_xxx
    dst_abs = os.path.join(bucket_abs, original_rel)
    os.makedirs(os.path.dirname(dst_abs), exist_ok=True)

    # 提取展示名称
    display_name = _extract_conversation_display_name(src_abs, conv_id)

    os.replace(src_abs, dst_abs)

    manifest = {
        "bulk_id": bulk_id,
        "ts": int(time.time()),
        "bucket_rel": _rel(base, bucket_abs),
        "roots": [original_rel],
        "items": [
            {
                "original_rel": original_rel,
                "trash_rel": _rel(base, dst_abs),
                "type": "directory",
            }
        ],
        "metadata": {"conv_id": conv_id, "display_name": display_name, "reason": args.get("reason")},
    }
    _write_json(os.path.join(bucket_abs, ".nisb_manifest.json"), manifest)

    try:
        append_fs_audit_event(
            user_id=user_id,
            email=email,
            name=name,
            event={
                "event": "conversation_trash_delete",
                "operation": "conversation_trash_delete",
                "batch_id": bulk_id,
                "paths": [original_rel],
                "metadata": {"conv_id": conv_id, "bucket_rel": manifest["bucket_rel"], "display_name": display_name},
            },
        )
    except Exception:
        pass

    return {
        "success": True,
        "bulk_id": bulk_id,
        "conv_id": conv_id,
        "original_rel": original_rel,
        "trash_bucket_rel": manifest["bucket_rel"],
        "display_name": display_name,
        "message": f"✅ 对话已移入回收站：{conv_id}（批次 {bulk_id}）",
    }


def nisb_chat_conversation_trash_restore(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    按 bulk_id 恢复对话（批次恢复）。
    args:
      - bulk_id: string required
      - overwrite: bool default false
    """
    ctx = _ctx(args)
    user_id, email, name = ctx.get("user_id"), ctx.get("email"), ctx.get("name")

    bulk_id = str(args.get("bulk_id") or "").strip()
    if not bulk_id:
        return {"success": False, "message": "缺少参数：bulk_id"}

    overwrite = bool(args.get("overwrite", False))
    base = _base(args)

    mp, manifest = _find_manifest_by_bulk_id(base, bulk_id)
    if not mp or not manifest:
        return {"success": False, "message": f"未找到批次：{bulk_id}"}

    items = manifest.get("items") or []
    if not isinstance(items, list) or not items:
        return {"success": False, "message": "该批次无可恢复项"}

    restored: List[str] = []
    skipped: List[Dict[str, Any]] = []

    for it in items:
        try:
            original_rel = str(it.get("original_rel") or "").strip()
            trash_rel = str(it.get("trash_rel") or "").strip()
            if not original_rel or not trash_rel:
                continue

            src_abs = os.path.join(base, trash_rel)
            dst_abs = os.path.join(base, original_rel)

            # 安全：仅允许恢复到 web_interactions/conversations 下
            conv_root = _conv_root(base)
            if not _safe_under(conv_root, dst_abs):
                skipped.append({"path": original_rel, "reason": "restore_outside_conversations"})
                continue

            if not os.path.exists(src_abs):
                skipped.append({"path": original_rel, "reason": "trash_missing"})
                continue

            os.makedirs(os.path.dirname(dst_abs), exist_ok=True)

            if os.path.exists(dst_abs) and not overwrite:
                skipped.append({"path": original_rel, "reason": "target_exists"})
                continue

            os.replace(src_abs, dst_abs)
            restored.append(original_rel)
        except Exception as e:
            skipped.append({"item": it, "reason": str(e)})

    try:
        append_fs_audit_event(
            user_id=user_id,
            email=email,
            name=name,
            event={
                "event": "conversation_trash_restore",
                "operation": "conversation_trash_restore",
                "batch_id": bulk_id,
                "paths": restored,
                "metadata": {"skipped": skipped[:50], "manifest_rel": _rel(base, mp)},
            },
        )
    except Exception:
        pass

    return {
        "success": True,
        "bulk_id": bulk_id,
        "restored": restored,
        "skipped": skipped,
        "message": f"✅ 对话恢复完成：{bulk_id}（恢复 {len(restored)} 项）",
    }


def nisb_chat_conversation_trash_batches_list(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    列出对话回收站批次（按 ts 倒序）。
    args:
      - limit: int default 60
      - query: string optional（匹配 bulk_id/conv_id/original_rel/display_name）
    """
    base = _base(args)
    root = _trash_root(base)
    limit = int(args.get("limit", 60) or 60)
    limit = max(1, min(limit, 200))
    query = str(args.get("query") or "").strip().lower()

    if not os.path.isdir(root):
        return {"success": True, "items": [], "total": 0}

    batches: List[Dict[str, Any]] = []
    for dirpath, _, filenames in os.walk(root):
        if ".nisb_manifest.json" not in filenames:
            continue
        mp = os.path.join(dirpath, ".nisb_manifest.json")
        data = _read_json(mp)
        if not data:
            continue

        bulk_id = str(data.get("bulk_id") or "").strip()
        if not bulk_id:
            continue

        meta = data.get("metadata") or {}
        conv_id = str(meta.get("conv_id") or "")
        display_name = str(meta.get("display_name") or "").strip()
        bucket_rel = str(data.get("bucket_rel") or _rel(base, dirpath)).replace("\\", "/")
        ts = int(data.get("ts") or 0)
        roots = data.get("roots") or []
        if not isinstance(roots, list):
            roots = []

        if query:
            hay = (bulk_id + " " + conv_id + " " + display_name + " " + bucket_rel + " " + " ".join(map(str, roots))).lower()
            if query not in hay:
                continue

        batches.append(
            {
                "bulk_id": bulk_id,
                "conv_id": conv_id,
                "display_name": display_name,
                "bucket_rel": bucket_rel,
                "ts": ts,
                "roots": roots,
                "items_count": len(data.get("items") or []),
                "manifest_rel": _rel(base, mp),
            }
        )

    batches.sort(key=lambda x: int(x.get("ts") or 0), reverse=True)
    return {"success": True, "items": batches[:limit], "total": len(batches)}


def nisb_chat_conversation_trash_batch_purge(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    永久清空一个对话批次（删 bucket）。需要 confirm_token=delete/删除
    """
    ctx = _ctx(args)
    user_id, email, name = ctx.get("user_id"), ctx.get("email"), ctx.get("name")

    bulk_id = str(args.get("bulk_id") or "").strip()
    if not bulk_id:
        return {"success": False, "message": "缺少参数：bulk_id"}

    token = str(args.get("confirm_token") or "").strip().lower()
    if token not in ("delete", "删除"):
        return {"success": False, "message": "CONFIRM_REQUIRED: 请输入 delete（或 删除）以确认永久清空该批次"}

    base = _base(args)
    mp, manifest = _find_manifest_by_bulk_id(base, bulk_id)
    if not mp:
        return {"success": False, "message": f"未找到批次：{bulk_id}"}

    bucket_abs = os.path.dirname(mp)
    trash_root = _trash_root(base)
    if not _safe_under(trash_root, bucket_abs):
        return {"success": False, "message": "PURGE_DENIED: 非法 bucket 路径"}

    shutil.rmtree(bucket_abs, ignore_errors=False)

    try:
        append_fs_audit_event(
            user_id=user_id,
            email=email,
            name=name,
            event={
                "event": "conversation_trash_batch_purge",
                "operation": "conversation_trash_batch_purge",
                "batch_id": bulk_id,
                "paths": [],
                "metadata": {"bucket_rel": _rel(base, bucket_abs)},
            },
        )
    except Exception:
        pass

    return {"success": True, "bulk_id": bulk_id, "message": f"🧹 已永久清空对话批次：{bulk_id}"}


def nisb_chat_conversation_trash_purge_all(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    永久清空所有对话回收站批次。需要 confirm_token=delete/删除
    """
    ctx = _ctx(args)
    user_id, email, name = ctx.get("user_id"), ctx.get("email"), ctx.get("name")

    token = str(args.get("confirm_token") or "").strip().lower()
    if token not in ("delete", "删除"):
        return {"success": False, "message": "CONFIRM_REQUIRED: 请输入 delete（或 删除）以确认清空对话回收站"}

    base = _base(args)
    root = _trash_root(base)
    if not os.path.isdir(root):
        return {"success": True, "purged": 0, "message": "对话回收站为空"}

    purged = 0
    failed: List[str] = []
    for entry in os.listdir(root):
        p = os.path.join(root, entry)
        if not os.path.isdir(p):
            continue
        try:
            shutil.rmtree(p, ignore_errors=False)
            purged += 1
        except Exception as e:
            failed.append(f"{entry}: {e}")

    try:
        append_fs_audit_event(
            user_id=user_id,
            email=email,
            name=name,
            event={
                "event": "conversation_trash_purge_all",
                "operation": "conversation_trash_purge_all",
                "batch_id": None,
                "paths": [],
                "metadata": {"purged": purged, "failed": failed[:50]},
            },
        )
    except Exception:
        pass

    msg = f"🧹 已清空对话回收站：删除 {purged} 个批次"
    if failed:
        msg += f"（失败 {len(failed)} 个）"
    return {"success": True, "purged": purged, "failed": failed, "message": msg}

