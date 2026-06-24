from __future__ import annotations

import os
import time
from typing import Any, Dict, List, Optional, Tuple


def _user_base(args: Dict[str, Any]) -> str:
    base = args.get("base_path") or args.get("_base_path")
    if not base or not isinstance(base, str):
        raise ValueError("缺少 base_path/_base_path（网关应注入）")
    return base


def _norm_rel(p: str) -> str:
    p = (p or "").strip().lstrip("/")
    p = os.path.normpath(p).replace("\\", "/")
    return p


def _ensure_agent_files(rel: str) -> str:
    rel = _norm_rel(rel)
    if rel == "agent_files":
        return rel
    if not rel.startswith("agent_files/"):
        raise ValueError("WRITE_DENIED: 只允许访问 agent_files/ 目录")
    if ".." in rel.split("/"):
        raise ValueError("非法路径：包含 ..")
    return rel


def _abs(base: str, rel: str) -> str:
    rel = _ensure_agent_files(rel)
    return os.path.join(base, rel)


def _walk_tree(root_abs: str, root_rel: str, depth: int, include_hidden: bool) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    root_depth = root_abs.rstrip(os.sep).count(os.sep)

    for dirpath, dirnames, filenames in os.walk(root_abs):
        d = dirpath.rstrip(os.sep).count(os.sep) - root_depth
        if d > depth:
            dirnames[:] = []
            continue

        # 过滤隐藏目录
        if not include_hidden:
            dirnames[:] = [n for n in dirnames if not n.startswith(".")]

        # 目录项
        rel_dir = os.path.relpath(dirpath, root_abs).replace("\\", "/")
        rel_dir = "" if rel_dir == "." else rel_dir
        items.append(
            {
                "path": f"{root_rel}/{rel_dir}".rstrip("/"),
                "type": "dir",
            }
        )

        # 文件项
        for fn in filenames:
            if (not include_hidden) and fn.startswith("."):
                continue
            fp = os.path.join(dirpath, fn)
            try:
                st = os.stat(fp)
                size = int(st.st_size)
                mtime = int(st.st_mtime)
            except Exception:
                size = None
                mtime = None

            rel_file = os.path.relpath(fp, root_abs).replace("\\", "/")
            items.append(
                {
                    "path": f"{root_rel}/{rel_file}".rstrip("/"),
                    "type": "file",
                    "size": size,
                    "mtime": mtime,
                }
            )

    # 排序：目录在前
    items.sort(key=lambda x: (0 if x["type"] == "dir" else 1, x["path"]))
    return items


def _tree_text(items: List[Dict[str, Any]], root_rel: str) -> str:
    # 简易 tree：按 path 分层打印（够用，前端也可以自己渲染）
    lines: List[str] = [f"📁 {root_rel}/"]
    for it in items:
        if it["path"] == root_rel:
            continue
        rel = it["path"][len(root_rel):].lstrip("/")
        indent = "  " * (rel.count("/"))
        name = rel.split("/")[-1]
        prefix = "📁" if it["type"] == "dir" else "📄"
        lines.append(f"{indent}{prefix} {name}")
    return "\n".join(lines)


def nisb_fs_snapshot(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    返回 agent_files 的“当前状态快照”（用于 UI 实时显示，不依赖审计事件）。
    args:
      - path: 默认 agent_files
      - depth: 默认 2
      - include_hidden: 默认 False（不显示 .trash 等）
      - include_trash: 默认 False（若 True，则 include_hidden 强制 True）
    """
    base = _user_base(args)

    path = args.get("path") or "agent_files"
    depth = int(args.get("depth", 2))
    include_trash = bool(args.get("include_trash", False))
    include_hidden = bool(args.get("include_hidden", False)) or include_trash

    root_rel = _ensure_agent_files(path)
    root_abs = _abs(base, root_rel)

    if not os.path.isdir(root_abs):
        return {"success": True, "root": root_rel, "depth": depth, "items": [], "tree_text": f"📁 {root_rel}/ (empty or missing)"}

    items = _walk_tree(root_abs=root_abs, root_rel=root_rel, depth=depth, include_hidden=include_hidden)
    return {
        "success": True,
        "root": root_rel,
        "depth": depth,
        "include_hidden": include_hidden,
        "items": items,
        "tree_text": _tree_text(items, root_rel=root_rel),
        "ts": int(time.time()),
    }


def _trash_root(base: str) -> Tuple[str, str]:
    trash_rel = "agent_files/.trash"
    return trash_rel, _abs(base, trash_rel)


def _derive_original_rel(trash_rel: str) -> Optional[str]:
    # 期望结构：agent_files/.trash/<bucket>/<original_rel_under_agent_files>
    # 如果无法解析，返回 None
    marker = "agent_files/.trash/"
    if not trash_rel.startswith(marker):
        return None
    rest = trash_rel[len(marker):]  # <bucket>/...
    parts = rest.split("/", 1)
    if len(parts) != 2:
        return None
    suffix = parts[1]  # 这里应当是原始相对路径（通常仍以 agent_files/... 开头或不包含）
    suffix = _norm_rel(suffix)
    # 允许两种：suffix 已经是 agent_files/xxx 或只是 xxx
    if suffix.startswith("agent_files/"):
        return suffix
    return f"agent_files/{suffix}"


def nisb_fs_trash_list(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    列出回收站文件（用于 UI “回收站”Tab）。
    args:
      - limit: 默认 200
      - query: 可选，子串过滤（匹配 trash_rel/original_rel）
    """
    base = _user_base(args)
    limit = int(args.get("limit", 200))
    query = (args.get("query") or "").strip()

    trash_rel, trash_abs = _trash_root(base)
    if not os.path.isdir(trash_abs):
        return {"success": True, "trash_root": trash_rel, "items": [], "total": 0}

    out: List[Dict[str, Any]] = []
    for dirpath, _, filenames in os.walk(trash_abs):
        for fn in filenames:
            fp = os.path.join(dirpath, fn)
            rel = os.path.relpath(fp, base).replace("\\", "/")  # agent_files/.trash/...
            rel = _norm_rel(rel)
            if not rel.startswith("agent_files/.trash/"):
                continue

            original_rel = _derive_original_rel(rel)

            if query:
                hay = (rel + " " + (original_rel or "")).lower()
                if query.lower() not in hay:
                    continue

            try:
                st = os.stat(fp)
                size = int(st.st_size)
                mtime = int(st.st_mtime)
            except Exception:
                size = None
                mtime = None

            out.append(
                {
                    "trash_rel": rel,
                    "trash_path": os.path.join(base, rel),
                    "original_rel": original_rel,
                    "size": size,
                    "mtime": mtime,
                }
            )
            if len(out) >= limit:
                break
        if len(out) >= limit:
            break

    out.sort(key=lambda x: (x.get("mtime") is None, -(x.get("mtime") or 0)))
    return {"success": True, "trash_root": trash_rel, "items": out, "total": len(out)}


def nisb_fs_trash_restore(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    从回收站恢复文件。
    args:
      - trash_rel 或 trash_path（二选一）
      - restore_to: 可选，默认恢复到 original_rel（若无法推导则必须提供）
      - overwrite: 默认 False
    """
    base = _user_base(args)
    overwrite = bool(args.get("overwrite", False))

    trash_rel = args.get("trash_rel")
    trash_path = args.get("trash_path")

    if trash_rel:
        trash_rel = _norm_rel(str(trash_rel))
        if not trash_rel.startswith("agent_files/.trash/"):
            return {"success": False, "message": "trash_rel 必须在 agent_files/.trash/ 下"}
        src = os.path.join(base, trash_rel)
    elif trash_path:
        src = str(trash_path)
        # 防止越界：必须在 base/agent_files/.trash 下
        src_norm = os.path.normpath(src)
        allowed = os.path.normpath(os.path.join(base, "agent_files", ".trash"))
        if not src_norm.startswith(allowed):
            return {"success": False, "message": "trash_path 不在回收站目录下"}
    else:
        return {"success": False, "message": "缺少 trash_rel 或 trash_path"}

    if not os.path.exists(src):
        return {"success": False, "message": f"回收站文件不存在：{src}"}

    restore_to = args.get("restore_to")
    if restore_to:
        dst_rel = _ensure_agent_files(str(restore_to))
    else:
        if trash_rel:
            derived = _derive_original_rel(trash_rel)
        else:
            rel_guess = _norm_rel(os.path.relpath(src, base).replace("\\", "/"))
            derived = _derive_original_rel(rel_guess)
        if not derived:
            return {"success": False, "message": "无法推导原始路径，请提供 restore_to"}
        dst_rel = _ensure_agent_files(derived)

    dst = os.path.join(base, dst_rel)
    os.makedirs(os.path.dirname(dst), exist_ok=True)

    if os.path.exists(dst) and not overwrite:
        return {"success": False, "message": f"目标已存在（overwrite=false）：{dst_rel}"}

    os.replace(src, dst)
    return {"success": True, "message": f"✅ 已从回收站恢复：{dst_rel}", "restored_rel": dst_rel, "restored_path": dst}

