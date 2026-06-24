from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from .config import get_base_path

# ✅ 只复用你们已经稳定的“对外工具函数”（它们自带安全校验 + 自动备份 + 日志）
from .core import (
    nisb_file_read,
    nisb_file_create,
    nisb_file_update,
)
from .audit_log import append_fs_audit_event


def _ctx(args: Dict[str, Any]) -> Dict[str, Any]:
    # 兼容你们当前的 user ctx 透传方式
    return {
        "user_id": args.get("user_id"),
        "_librechat_email": args.get("_librechat_email") or args.get("email"),
        "_librechat_name": args.get("_librechat_name") or args.get("name"),
        "email": args.get("email"),
        "name": args.get("name"),
    }


def _operation_from_backup_id(backup_id: str) -> str:
    bid = (backup_id or "").strip()
    parts = bid.split("_", 2)
    if len(parts) == 3 and parts[2]:
        return parts[2]
    return ""


def _normalize_event(e: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(e or {})
    backup_id = str(out.get("backup_id") or "").strip()
    out["backup_id"] = backup_id

    op = (
        out.get("operation")
        or out.get("op")
        or out.get("action")
        or out.get("operation_name")
        or _operation_from_backup_id(backup_id)
        or str(out.get("event") or "").strip()
        or "unknown"
    )
    out["operation"] = op

    paths = out.get("paths")
    if isinstance(paths, str):
        paths = [paths]
    if not isinstance(paths, list):
        paths = []

    if not paths:
        md = out.get("metadata") or {}
        if isinstance(md, dict) and md.get("filename"):
            paths = [str(md["filename"])]

    out["paths"] = [str(p).lstrip("/").replace("\\", "/") for p in paths if str(p).strip()]

    if not out.get("ts") and out.get("timestamp"):
        out["ts"] = out.get("timestamp")

    if not isinstance(out.get("metadata"), dict):
        out["metadata"] = out.get("metadata") if out.get("metadata") else {}

    return out


def _backups_root(base_path: str) -> str:
    return os.path.join(base_path, ".backups")


def _parse_backup_id(backup_id: str) -> Tuple[Optional[str], str]:
    """
    backup_id 示例：20251229_205120_file_delete
    返回：(ts_iso, action)
    """
    bid = (backup_id or "").strip()
    parts = bid.split("_", 2)
    if len(parts) < 3:
        return None, ""
    dt_raw = f"{parts[0]}_{parts[1]}"
    action = parts[2]
    try:
        dt = datetime.strptime(dt_raw, "%Y%m%d_%H%M%S")
        return dt.isoformat(), action
    except Exception:
        return None, action


def _read_json(path: str) -> Optional[dict]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def _list_backup_dirs(backups_dir: str) -> List[str]:
    if not os.path.isdir(backups_dir):
        return []
    names: List[str] = []
    for name in os.listdir(backups_dir):
        p = os.path.join(backups_dir, name)
        if os.path.isdir(p):
            names.append(name)
    # 目录名按时间前缀排序：越大越新
    names.sort(reverse=True)
    return names


def _walk_files(root_dir: str, *, max_files: int = 200) -> List[str]:
    out: List[str] = []
    for r, _, files in os.walk(root_dir):
        for fn in files:
            rel = os.path.relpath(os.path.join(r, fn), root_dir)
            rel = rel.replace("\\", "/")
            out.append(rel)
            if len(out) >= max_files:
                return out
    return out


def _infer_paths_from_backup_dir(backup_dir: str) -> List[str]:
    """
    根据备份目录内容推断被备份的相对路径：
    .backups/<backup_id>/agent_files/xxx.txt -> agent_files/xxx.txt
    """
    files = _walk_files(backup_dir, max_files=600)
    files = [f for f in files if not f.endswith("backup_metadata.json")]

    paths: List[str] = []
    for f in files:
        if f.startswith("agent_files/") or f.startswith("storage/"):
            paths.append(f)
        # 其它未知结构也记录（但 restore 时会限制 agent_files）
        else:
            paths.append(f)

    # 去重
    seen = set()
    uniq: List[str] = []
    for p in paths:
        if p not in seen:
            seen.add(p)
            uniq.append(p)
    return uniq


def nisb_fs_audit_tail(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    优先读取 storage/audit/filesystem_audit.jsonl；
    若不存在或为空，则 fallback 扫描 .backups（兼容历史数据）。
    """
    user_id = args.get("user_id")
    email = args.get("_librechat_email") or args.get("email")
    name = args.get("_librechat_name") or args.get("name")

    limit = args.get("limit", 50)
    prefix = (args.get("prefix") or "").strip()

    try:
        limit_i = int(limit)
    except Exception:
        limit_i = 50
    limit_i = max(1, min(200, limit_i))

    base_path = get_base_path(user_id, email, name)

    # 1) JSONL 优先
    audit_path = os.path.join(base_path, "storage", "audit", "filesystem_audit.jsonl")
    events: List[Dict[str, Any]] = []
    try:
        if os.path.isfile(audit_path):
            with open(audit_path, "r", encoding="utf-8") as f:
                lines = f.read().splitlines()
            # 从后往前取
            for line in reversed(lines[-5000:]):
                if len(events) >= limit_i:
                    break
                if not line.strip():
                    continue
                try:
                    e = json.loads(line)
                except Exception:
                    continue

                paths = e.get("paths")
                if isinstance(paths, str):
                    paths = [paths]
                if not isinstance(paths, list):
                    paths = []

                if prefix:
                    if not any(str(p).startswith(prefix) for p in paths):
                        continue

                e2 = _normalize_event(e)
                bid = str(e2.get("backup_id") or "").strip()
                if bid:
                    e2["restorable"] = os.path.isdir(os.path.join(_backups_root(base_path), bid))
                events.append(e2)

            return {"success": True, "events": events, "count": len(events), "source": "jsonl"}
    except Exception:
        # JSONL 读取失败则 fallback
        pass

    # 2) fallback：扫描 .backups（你原有逻辑）
    backups_dir = _backups_root(base_path)
    for backup_id in _list_backup_dirs(backups_dir):
        if len(events) >= limit_i:
            break

        bdir = os.path.join(backups_dir, backup_id)
        meta_path = os.path.join(bdir, "backup_metadata.json")
        meta = _read_json(meta_path) or {}

        ts_iso, action = _parse_backup_id(backup_id)
        if not action:
            action = str(meta.get("operation") or meta.get("action") or meta.get("op") or "").strip() or "unknown"

        paths: List[str] = []
        # 兼容你现在的 metadata 结构：files[].backup/ original
        if isinstance(meta.get("files"), list):
            base = get_base_path(user_id, email, name)
            for it in meta["files"]:
                if isinstance(it, dict) and it.get("original"):
                    try:
                        rp = os.path.relpath(str(it["original"]), base).replace("\\", "/")
                        paths.append(rp)
                    except Exception:
                        pass

        if not paths:
            paths = _infer_paths_from_backup_dir(bdir)

        if prefix:
            paths2 = [p for p in paths if p.startswith(prefix)]
            if not paths2:
                continue
            paths = paths2

        events.append(
            {
                "event": "backup_created",
                "backup_id": backup_id,
                "ts": ts_iso or meta.get("timestamp"),
                "operation": action,
                "paths": paths[:200],
                "metadata": meta,
            }
        )

    return {"success": True, "events": events, "count": len(events), "source": "backups_scan"}


def nisb_fs_restore_backup(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    从指定 backup_id 恢复一个文件到原路径（仅允许 agent_files/ 下）。
    注意：覆盖恢复会调用 nisb_file_update，而它会自动触发“修改前备份”，所以无需额外手写 backup_file_or_dir。
    输入：
      - backup_id: 例如 20251229_205120_file_delete
      - path: 例如 agent_files/test2.txt
    """
    backup_id = str(args.get("backup_id") or "").strip()
    path = str(args.get("path") or "").strip().lstrip("/").replace("\\", "/")
    if not backup_id:
        return {"success": False, "message": "缺少参数：backup_id"}
    if not path:
        return {"success": False, "message": "缺少参数：path"}

    # ✅ 强制只允许 agent_files
    if not path.startswith("agent_files/") and path != "agent_files":
        return {"success": False, "message": "RESTORE_DENIED: 仅允许恢复 agent_files/ 下路径"}

    user_id = args.get("user_id")
    email = args.get("_librechat_email") or args.get("email")
    name = args.get("_librechat_name") or args.get("name")

    base_path = get_base_path(user_id, email, name)
    bdir = os.path.join(_backups_root(base_path), backup_id)
    if not os.path.isdir(bdir):
        return {"success": False, "message": f"备份不存在：{backup_id}"}

    src_file = os.path.join(bdir, path)
    if not os.path.isfile(src_file):
        return {"success": False, "message": f"该备份中没有此文件：{path}"}

    try:
        with open(src_file, "rb") as f:
            raw = f.read()

        # 目前你的使用场景是文本文件（hello2），优先按 utf-8
        try:
            content = raw.decode("utf-8")
        except Exception:
            # 最弱兜底：latin-1 不会报错（但二进制恢复不保证可用）
            content = raw.decode("latin-1")

        ctx = _ctx(args)

        # 判断目标是否存在：成功 read 则认为存在
        exists = False
        try:
            r = nisb_file_read({**ctx, "filename": path})
            exists = bool(r and r.get("success"))
        except Exception:
            exists = False

        if exists:
            # ✅ update 内部会自动做“修改前备份”
            u = nisb_file_update({**ctx, "filename": path, "content": content})
            if u and u.get("success"):
                # 追加审计事件
                append_fs_audit_event(
                    user_id=user_id,
                    email=email,
                    name=name,
                    event={
                        "event": "backup_restored",
                        "backup_id": backup_id,
                        "paths": [path],
                    },
                )
                return {"success": True, "message": f"✅ 已恢复（覆盖）：{path}", "backup_id": backup_id, "path": path}
            return {"success": False, "message": u.get("message") if isinstance(u, dict) else "恢复失败：update 返回异常"}

        c = nisb_file_create(
            {
                **ctx,
                "filename": path,
                "content": content,
                "description": f"restore from backup {backup_id}",
                "auto_categorize": False,
            }
        )
        if c and c.get("success"):
            # 追加审计事件
            append_fs_audit_event(
                user_id=user_id,
                email=email,
                name=name,
                event={
                    "event": "backup_restored",
                    "backup_id": backup_id,
                    "paths": [path],
                },
            )
            return {"success": True, "message": f"✅ 已恢复（创建）：{path}", "backup_id": backup_id, "path": path}
        return {"success": False, "message": c.get("message") if isinstance(c, dict) else "恢复失败：create 返回异常"}

    except Exception as e:
        return {"success": False, "message": f"恢复失败：{e}"}


def nisb_fs_audit_search(args: Dict[str, Any]) -> Dict[str, Any]:
    user_id = args.get("user_id")
    email = args.get("_librechat_email") or args.get("email")
    name = args.get("_librechat_name") or args.get("name")

    q = str(args.get("q") or "").strip().lower()
    prefix = str(args.get("prefix") or "").strip()
    op_filter = str(args.get("operation") or "").strip()
    since_ts = str(args.get("since_ts") or "").strip()
    cursor = args.get("cursor")

    try:
        limit = int(args.get("limit", 50))
    except Exception:
        limit = 50
    limit = max(1, min(200, limit))

    base_path = get_base_path(user_id, email, name)
    audit_path = os.path.join(base_path, "storage", "audit", "filesystem_audit.jsonl")
    if not os.path.isfile(audit_path):
        return {"success": True, "events": [], "count": 0, "next_cursor": None}

    with open(audit_path, "r", encoding="utf-8") as f:
        lines = f.read().splitlines()

    idx = len(lines) - 1
    if cursor is not None:
        try:
            idx = int(cursor)
        except Exception:
            idx = len(lines) - 1
    idx = min(idx, len(lines) - 1)

    events: List[Dict[str, Any]] = []
    next_cursor = None
    scanned = 0

    while idx >= 0 and len(events) < limit and scanned < 8000:
        scanned += 1
        line = lines[idx].strip()
        idx -= 1
        if not line:
            continue
        try:
            e = json.loads(line)
        except Exception:
            continue

        e = _normalize_event(e)

        if since_ts:
            ts = str(e.get("ts") or "")
            if ts and ts < since_ts:
                break

        if op_filter and str(e.get("operation") or "") != op_filter:
            continue

        if prefix and not any(str(p).startswith(prefix) for p in (e.get("paths") or [])):
            continue

        if q:
            blob = (
                str(e.get("operation") or "")
                + " "
                + " ".join([str(p) for p in (e.get("paths") or [])])
                + " "
                + json.dumps(e.get("metadata") or {}, ensure_ascii=False)
            ).lower()
            if q not in blob:
                continue

        bid = str(e.get("backup_id") or "").strip()
        if bid:
            e["restorable"] = os.path.isdir(os.path.join(_backups_root(base_path), bid))

        events.append(e)

    if idx >= 0:
        next_cursor = idx

    return {"success": True, "events": events, "count": len(events), "next_cursor": next_cursor}

