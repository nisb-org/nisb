from __future__ import annotations

import uuid
from typing import Any, Dict, List

from .audit_log import append_fs_audit_event
from .delete_tool import nisb_file_delete  # 软删除优先（危险开关关着也可“删除”）

from .core import (
    nisb_file_create,
    nisb_file_update,
    nisb_file_move_path,
    nisb_file_rename,
)

from .directory import (
    nisb_dir_create,
)


def _ctx(args: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "user_id": args.get("user_id"),
        "_librechat_email": args.get("_librechat_email") or args.get("email"),
        "_librechat_name": args.get("_librechat_name") or args.get("name"),
        "email": args.get("email"),
        "name": args.get("name"),
        "fs_write_scope": args.get("fs_write_scope"),
        "fs_dangerous_enabled": args.get("fs_dangerous_enabled"),
        "confirm": args.get("confirm"),
    }


# ✅ 允许用户用“工具函数名”写 op（更直觉）
_OP_ALIASES = {
    "nisb_file_create": "file_create",
    "nisb_file_update": "file_update",
    "nisb_file_delete": "file_delete",
    "nisb_file_move_path": "file_move",
    "nisb_file_rename": "file_rename",
    "nisb_dir_create": "dir_create",
}


def _normalize_op(op: str) -> str:
    s = (op or "").strip()
    return _OP_ALIASES.get(s, s)


def nisb_fs_apply_batch(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    批量执行（P1 最小可用 + 直觉增强）：
    - ops 支持两套命名：
        file_create / file_update / file_delete / file_move / file_rename / dir_create
        nisb_file_create / nisb_file_update / ...（别名）
    - dry_run：只校验关键字段，不落盘
    - stop_on_error：遇错停止
    - 每步写 JSONL 审计
    """
    ops = args.get("ops")
    if not isinstance(ops, list) or not ops:
        return {"success": False, "message": "缺少参数：ops(list)"}
    if len(ops) > 50:
        return {"success": False, "message": "ops 数量过多（最多 50）"}

    dry_run = bool(args.get("dry_run", False))
    stop_on_error = bool(args.get("stop_on_error", True))
    batch_id = str(args.get("batch_id") or f"batch_{uuid.uuid4().hex[:10]}")

    ctx = _ctx(args)
    user_id = ctx.get("user_id")
    email = ctx.get("_librechat_email") or ctx.get("email")
    name = ctx.get("_librechat_name") or ctx.get("name")

    results: List[Dict[str, Any]] = []

    def audit(event: Dict[str, Any]) -> None:
        append_fs_audit_event(user_id=user_id, email=email, name=name, event=event)

    audit({"event": "batch_start", "batch_id": batch_id, "ops_count": len(ops), "dry_run": dry_run})

    supported = {"file_create", "file_update", "file_delete", "file_move", "file_rename", "dir_create"}

    for i, item in enumerate(ops):
        op_id = str(item.get("op_id") or f"op_{i}_{uuid.uuid4().hex[:6]}")
        op_raw = str(item.get("op") or "").strip()
        op = _normalize_op(op_raw)

        res: Dict[str, Any] = {"op_id": op_id, "op": op, "success": False}

        try:
            if op not in supported:
                raise ValueError(f"不支持的 op：{op_raw} -> {op}（当前可用：{sorted(list(supported))}）")

            # ---- dry-run 校验 ----
            if dry_run:
                if op in ("file_create", "file_update", "file_delete", "file_rename"):
                    if not item.get("filename"):
                        raise ValueError("缺少 filename")
                if op == "file_create" and item.get("content") is None:
                    # content 允许空字符串，但不允许缺字段导致误解
                    pass
                if op == "file_move":
                    if not item.get("src") or not item.get("dst"):
                        raise ValueError("缺少 src/dst")
                if op == "file_rename":
                    if not item.get("new_name"):
                        raise ValueError("缺少 new_name")
                if op == "dir_create" and not item.get("path"):
                    raise ValueError("缺少 path")

                res["success"] = True
                res["status"] = "planned"
                results.append(res)
                continue

            # ---- 执行 ----
            if op == "file_create":
                tool_res = nisb_file_create(
                    {
                        **ctx,
                        "filename": item["filename"],
                        "content": item.get("content", ""),
                        "description": item.get("description", ""),
                        "auto_categorize": bool(item.get("auto_categorize", False)),
                    }
                )
            elif op == "file_update":
                tool_res = nisb_file_update({**ctx, "filename": item["filename"], "content": item.get("content", "")})
            elif op == "file_delete":
                tool_res = nisb_file_delete(
                    {
                        **ctx,
                        "filename": item["filename"],
                        "file_id": item.get("file_id"),
                        "permanent": bool(item.get("permanent", True)),
                    }
                )
            elif op == "file_move":
                tool_res = nisb_file_move_path({**ctx, "src": item["src"], "dst": item["dst"]})
            elif op == "file_rename":
                tool_res = nisb_file_rename({**ctx, "filename": item["filename"], "new_name": item["new_name"]})
            elif op == "dir_create":
                tool_res = nisb_dir_create({**ctx, "path": item["path"]})
            else:
                tool_res = {"success": False, "message": "unreachable"}

            ok = bool(tool_res and isinstance(tool_res, dict) and tool_res.get("success"))
            res["success"] = ok
            res["status"] = "ok" if ok else "error"
            res["tool_result"] = tool_res
            results.append(res)

            path_hint = item.get("filename") or item.get("src") or item.get("path")
            audit(
                {
                    "event": "batch_op",
                    "batch_id": batch_id,
                    "op_id": op_id,
                    "operation": op,
                    "success": ok,
                    "paths": [path_hint] if path_hint else [],
                    "metadata": {
                        "op_raw": op_raw,
                        "item": item,
                        "tool_message": tool_res.get("message") if isinstance(tool_res, dict) else None,
                    },
                }
            )

            if stop_on_error and not ok:
                audit({"event": "batch_stop_on_error", "batch_id": batch_id, "op_id": op_id})
                break

        except Exception as e:
            res["success"] = False
            res["status"] = "exception"
            res["error"] = str(e)
            results.append(res)

            path_hint = item.get("filename") or item.get("src") or item.get("path")
            audit(
                {
                    "event": "batch_op",
                    "batch_id": batch_id,
                    "op_id": op_id,
                    "operation": op or "unknown",
                    "success": False,
                    "paths": [path_hint] if path_hint else [],
                    "metadata": {"op_raw": op_raw, "item": item, "error": str(e)},
                }
            )

            if stop_on_error:
                audit({"event": "batch_stop_on_exception", "batch_id": batch_id, "op_id": op_id})
                break

    audit(
        {
            "event": "batch_end",
            "batch_id": batch_id,
            "success": all(r.get("success") for r in results),
            "applied": (not dry_run),
            "count": len(results),
        }
    )
    return {"success": True, "batch_id": batch_id, "dry_run": dry_run, "results": results}

