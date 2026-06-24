from __future__ import annotations

import json
import os
import time
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from tools.i18n.backend_i18n import i18n_text, normalize_backend_locale

from .audit_log import append_fs_audit_event


def _safe_args(args: Dict[str, Any] | None) -> Dict[str, Any]:
    return args if isinstance(args, dict) else {}


def _locale(args: Dict[str, Any] | None) -> str:
    return normalize_backend_locale(_safe_args(args).get("locale"))


def _txt(args: Dict[str, Any] | None, en: str, zh: str) -> str:
    return i18n_text(_locale(args), {"en": en, "zh-CN": zh}, en)


def _fmt(args: Dict[str, Any] | None, en: str, zh: str, **kwargs: Any) -> str:
    return _txt(args, en, zh).format(**kwargs)


def _tool_entry(kind: str, data: Dict[str, Any]) -> Dict[str, Any]:
    return {"kind": kind, "data": data or {}}


def _ok(
    args: Dict[str, Any],
    kind: str,
    message: str,
    *,
    tool_data: Dict[str, Any] | None = None,
    **fields: Any,
) -> Dict[str, Any]:
    out = {
        "success": True,
        "status": "success",
        "message": message,
        "response": message,
        "tool_results": [_tool_entry(kind, tool_data or {})],
    }
    out.update(fields)
    return out


def _err(
    args: Dict[str, Any],
    kind: str,
    message: str,
    *,
    tool_data: Dict[str, Any] | None = None,
    **fields: Any,
) -> Dict[str, Any]:
    out = {
        "success": False,
        "status": "error",
        "message": message,
        "response": message,
        "tool_results": [_tool_entry(kind, tool_data or {})],
    }
    out.update(fields)
    return out


def _ctx(args: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "user_id": args.get("user_id"),
        "email": args.get("_librechat_email") or args.get("email"),
        "name": args.get("_librechat_name") or args.get("name"),
    }


def _base(args: Dict[str, Any]) -> str:
    base = args.get("base_path") or args.get("_base_path")
    if not base or not isinstance(base, str):
        raise ValueError("missing_base_path")
    return base.rstrip("/")


def _norm_rel(p: str) -> str:
    p = (p or "").strip().lstrip("/").replace("\\", "/")
    p = os.path.normpath(p).replace("\\", "/")
    return p


def _as_agent_rel(p: str) -> str:
    rel = _norm_rel(p)
    if rel in ("", "."):
        raise ValueError("empty_path")
    if ".." in rel.split("/"):
        raise ValueError("path_contains_parent_reference")
    if rel == "agent_files" or rel.startswith("agent_files/"):
        return rel
    return f"agent_files/{rel}"


def _abs(base: str, rel: str) -> str:
    rel = _as_agent_rel(rel)
    abs_path = os.path.normpath(os.path.join(base, rel))
    base_norm = os.path.normpath(base)
    if abs_path != base_norm and not abs_path.startswith(base_norm + os.sep):
        raise ValueError("path_outside_base")
    return abs_path


def _trash_root_abs(base: str) -> str:
    return os.path.join(base, "agent_files", ".trash")


def _write_manifest(path: str, data: Dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _read_manifest(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _error_label(args: Dict[str, Any], reason: str) -> str:
    labels = {
        "missing_base_path": {
            "en": "Missing base_path/_base_path. The gateway should inject it.",
            "zh-CN": "缺少 base_path/_base_path（网关应注入）",
        },
        "empty_path": {
            "en": "Invalid path: empty",
            "zh-CN": "非法路径：空",
        },
        "path_contains_parent_reference": {
            "en": "Invalid path: contains ..",
            "zh-CN": "非法路径：包含 ..",
        },
        "path_outside_base": {
            "en": "Invalid path: outside base directory",
            "zh-CN": "非法路径：超出 base 目录",
        },
        "illegal_trash_rel": {
            "en": "Invalid trash_rel",
            "zh-CN": "非法 trash_rel",
        },
    }
    mapping = labels.get(str(reason), {"en": str(reason), "zh-CN": str(reason)})
    return i18n_text(_locale(args), mapping, str(reason))


def nisb_fs_bulk_delete(args: Dict[str, Any]) -> Dict[str, Any]:
    args = _safe_args(args)
    kind = "nisb_fs_bulk_delete"
    ctx = _ctx(args)
    user_id = ctx.get("user_id")
    email = ctx.get("email")
    name = ctx.get("name")

    paths = args.get("paths")
    if not isinstance(paths, list) or not paths:
        return _err(
            args,
            kind,
            _txt(args, "Missing argument: paths(list)", "缺少参数：paths(list)"),
            tool_data={"paths": paths, "reason": "missing_paths"},
        )

    try:
        base = _base(args)
    except Exception as e:
        reason = str(e)
        return _err(
            args,
            kind,
            _error_label(args, reason),
            tool_data={"reason": reason},
        )

    bulk_id = str(args.get("bulk_id") or f"bulk_{uuid.uuid4().hex[:10]}")
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    bucket_rel = f"agent_files/.trash/{ts}__{bulk_id}"
    bucket_abs = os.path.join(base, bucket_rel)

    items: List[Dict[str, Any]] = []
    moved_paths: List[str] = []
    skipped: List[Dict[str, Any]] = []

    for raw in paths:
        try:
            original_rel = _as_agent_rel(str(raw))
            src_abs = _abs(base, original_rel)

            if not os.path.exists(src_abs):
                skipped.append({"path": original_rel, "reason": "not_exists"})
                continue

            dst_abs = os.path.join(bucket_abs, original_rel)
            os.makedirs(os.path.dirname(dst_abs), exist_ok=True)

            if os.path.exists(dst_abs):
                suffix = uuid.uuid4().hex[:6]
                dst_abs = dst_abs + f".dup_{suffix}"

            os.replace(src_abs, dst_abs)

            trash_rel = os.path.relpath(dst_abs, base).replace("\\", "/")
            items.append(
                {
                    "original_rel": original_rel,
                    "trash_rel": trash_rel,
                    "type": "directory" if os.path.isdir(dst_abs) else "file",
                }
            )
            moved_paths.append(original_rel)
        except Exception as e:
            skipped.append({"path": str(raw), "reason": str(e)})

    manifest = {
        "bulk_id": bulk_id,
        "ts": int(time.time()),
        "bucket_rel": bucket_rel,
        "items": items,
        "skipped": skipped,
    }
    manifest_path = os.path.join(base, bucket_rel, ".nisb_manifest.json")
    _write_manifest(manifest_path, manifest)

    try:
        append_fs_audit_event(
            user_id=user_id,
            email=email,
            name=name,
            event={
                "event": "bulk_delete",
                "operation": "bulk_delete",
                "batch_id": bulk_id,
                "paths": moved_paths,
                "metadata": {
                    "bucket_rel": bucket_rel,
                    "items_count": len(items),
                    "skipped": skipped[:50],
                    "reason": args.get("reason"),
                },
            },
        )
    except Exception as e:
        print(f"[WARN] audit bulk_delete failed: {e}")

    message = _fmt(
        args,
        "✅ Moved to trash (batch {bulk_id}): {count} item(s)",
        "✅ 已移入回收站（批次 {bulk_id}）：{count} 项",
        bulk_id=bulk_id,
        count=len(items),
    )

    return _ok(
        args,
        kind,
        message,
        tool_data={
            "bulk_id": bulk_id,
            "trash_bucket_rel": bucket_rel,
            "items": items,
            "skipped": skipped,
        },
        bulk_id=bulk_id,
        trash_bucket_rel=bucket_rel,
        items=items,
        skipped=skipped,
    )


def nisb_fs_bulk_restore(args: Dict[str, Any]) -> Dict[str, Any]:
    args = _safe_args(args)
    kind = "nisb_fs_bulk_restore"
    ctx = _ctx(args)
    user_id = ctx.get("user_id")
    email = ctx.get("email")
    name = ctx.get("name")

    bulk_id = str(args.get("bulk_id") or "").strip()
    if not bulk_id:
        return _err(
            args,
            kind,
            _txt(args, "Missing argument: bulk_id", "缺少参数：bulk_id"),
            tool_data={"bulk_id": bulk_id, "reason": "missing_bulk_id"},
        )

    overwrite = bool(args.get("overwrite", False))

    try:
        base = _base(args)
    except Exception as e:
        reason = str(e)
        return _err(
            args,
            kind,
            _error_label(args, reason),
            tool_data={"bulk_id": bulk_id, "reason": reason},
        )

    trash_root = _trash_root_abs(base)
    if not os.path.isdir(trash_root):
        return _err(
            args,
            kind,
            _txt(args, "Trash directory does not exist", "回收站目录不存在"),
            tool_data={"bulk_id": bulk_id, "trash_root": trash_root, "reason": "trash_root_missing"},
        )

    found_manifest: Optional[str] = None
    for dirpath, _, filenames in os.walk(trash_root):
        if ".nisb_manifest.json" in filenames:
            mp = os.path.join(dirpath, ".nisb_manifest.json")
            try:
                data = _read_manifest(mp)
                if str(data.get("bulk_id")) == bulk_id:
                    found_manifest = mp
                    break
            except Exception:
                continue

    if not found_manifest:
        return _err(
            args,
            kind,
            _fmt(args, "Batch not found: {bulk_id}", "未找到该批次：{bulk_id}", bulk_id=bulk_id),
            tool_data={"bulk_id": bulk_id, "reason": "manifest_not_found"},
        )

    manifest = _read_manifest(found_manifest)
    items = manifest.get("items") or []
    if not isinstance(items, list) or not items:
        return _err(
            args,
            kind,
            _txt(args, "This batch has no restorable items", "该批次无可恢复项"),
            tool_data={"bulk_id": bulk_id, "manifest": os.path.relpath(found_manifest, base).replace("\\", "/"), "reason": "empty_batch"},
        )

    restored: List[str] = []
    skipped: List[Dict[str, Any]] = []

    for it in items:
        try:
            original_rel = _as_agent_rel(str(it.get("original_rel") or ""))
            trash_rel = _norm_rel(str(it.get("trash_rel") or ""))
            if not trash_rel.startswith("agent_files/.trash/"):
                raise ValueError("illegal_trash_rel")

            src_abs = os.path.join(base, trash_rel)
            dst_abs = _abs(base, original_rel)

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
                "event": "bulk_restore",
                "operation": "bulk_restore",
                "batch_id": bulk_id,
                "paths": restored,
                "metadata": {
                    "restored_count": len(restored),
                    "skipped": skipped[:50],
                    "manifest": os.path.relpath(found_manifest, base).replace("\\", "/"),
                },
            },
        )
    except Exception as e:
        print(f"[WARN] audit bulk_restore failed: {e}")

    message = _fmt(
        args,
        "✅ Batch restore completed ({bulk_id}): restored {count} item(s)",
        "✅ 批次恢复完成（{bulk_id}）：恢复 {count} 项",
        bulk_id=bulk_id,
        count=len(restored),
    )

    return _ok(
        args,
        kind,
        message,
        tool_data={
            "bulk_id": bulk_id,
            "restored": restored,
            "skipped": skipped,
        },
        bulk_id=bulk_id,
        restored=restored,
        skipped=skipped,
    )
