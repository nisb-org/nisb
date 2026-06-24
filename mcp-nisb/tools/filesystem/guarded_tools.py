from __future__ import annotations

from typing import Any, Dict

from .capability_gate import enforce_fs_capability_gate
from .formal_response import ensure_formal_response

from .core import (
    nisb_file_create as _nisb_file_create,
    nisb_file_read as _nisb_file_read,
    nisb_file_update as _nisb_file_update,
    nisb_file_delete as _nisb_file_delete,
    nisb_file_move_path as _nisb_file_move_path,
    nisb_file_rename as _nisb_file_rename,
    nisb_dir_delete as _nisb_dir_delete,
)

from .directory import (
    nisb_dir_create as _nisb_dir_create,
    nisb_dir_list as _nisb_dir_list,
    nisb_dir_tree as _nisb_dir_tree,
    nisb_file_list_allowed_directories as _nisb_file_list_allowed_directories,
    nisb_dir_delete_recursive as _nisb_dir_delete_recursive,
)

from .dir_move_path import nisb_dir_move_path as _nisb_dir_move_path

from .bulk_trash import (
    nisb_fs_bulk_delete as _nisb_fs_bulk_delete,
    nisb_fs_bulk_restore as _nisb_fs_bulk_restore,
)

from .snapshot_tools import (
    nisb_fs_snapshot as _nisb_fs_snapshot,
    nisb_fs_trash_list as _nisb_fs_trash_list,
    nisb_fs_trash_restore as _nisb_fs_trash_restore,
)


def _tool_entry(kind: str, data: Dict[str, Any]) -> Dict[str, Any]:
    return {"kind": kind, "data": data or {}}


def _formalize(args: Dict[str, Any], payload: Dict[str, Any], kind: str) -> Dict[str, Any]:
    data = dict(payload or {})
    status = str(data.get("status") or "").strip().lower()
    if not status:
        if data.get("success") is True:
            status = "success"
        elif data.get("success") is False:
            status = "error"
        else:
            status = "success"

    response = str(data.get("response") or "").strip()
    message = str(data.get("message") or "").strip()

    if not response:
        if status == "success":
            response = message or "✅ 操作成功"
        elif status == "warning":
            response = message or "⚠️ 操作完成，但存在警告"
        else:
            response = message or "❌ 操作失败"

    if not message:
        message = response

    tool_calls = data.get("tool_calls")
    if not isinstance(tool_calls, list):
        tool_calls = []

    tool_results = data.get("tool_results")
    if not isinstance(tool_results, list):
        tool_results = []

    data["status"] = status
    data["response"] = response
    data["message"] = message
    data["tool_calls"] = tool_calls
    data["tool_results"] = tool_results

    return ensure_formal_response(
        args,
        data,
        default_kind=kind,
        keep_compat_fields=True,
    )


def _deny(args: Dict[str, Any], msg: str, reason_code: str, operation: str) -> Dict[str, Any]:
    return _formalize(
        args,
        {
            "success": False,
            "status": "error",
            "message": msg,
            "response": msg,
            "reason_code": reason_code,
            "operation": operation,
            "tool_results": [
                _tool_entry(
                    "capability_gate",
                    {
                        "operation": operation,
                        "reason_code": reason_code,
                        "allowed": False,
                    },
                )
            ],
        },
        operation,
    )


def _wrap(args: Dict[str, Any], op: str, res: Dict[str, Any]) -> Dict[str, Any]:
    return _formalize(args, res or {}, op)


def nisb_file_list_allowed_directories(args: Dict[str, Any]) -> Dict[str, Any]:
    op = "nisb_file_list_allowed_directories"
    ok, msg, reason, _ = enforce_fs_capability_gate(
        args=args,
        operation=op,
        paths=["agent_files"],
        is_read=True,
    )
    if not ok:
        return _deny(args, msg, reason, op)
    return _wrap(args, op, _nisb_file_list_allowed_directories(args))


def nisb_dir_list(args: Dict[str, Any]) -> Dict[str, Any]:
    op = "nisb_dir_list"
    ok, msg, reason, _ = enforce_fs_capability_gate(
        args=args,
        operation=op,
        paths=[str(args.get("path") or "agent_files")],
        is_read=True,
    )
    if not ok:
        return _deny(args, msg, reason, op)
    return _wrap(args, op, _nisb_dir_list(args))


def nisb_dir_tree(args: Dict[str, Any]) -> Dict[str, Any]:
    op = "nisb_dir_tree"
    ok, msg, reason, _ = enforce_fs_capability_gate(
        args=args,
        operation=op,
        paths=[str(args.get("path") or "agent_files")],
        is_read=True,
    )
    if not ok:
        return _deny(args, msg, reason, op)
    return _wrap(args, op, _nisb_dir_tree(args))


def nisb_fs_snapshot(args: Dict[str, Any]) -> Dict[str, Any]:
    op = "nisb_fs_snapshot"
    ok, msg, reason, _ = enforce_fs_capability_gate(
        args=args,
        operation=op,
        paths=[str(args.get("path") or "agent_files")],
        is_read=True,
    )
    if not ok:
        return _deny(args, msg, reason, op)
    return _wrap(args, op, _nisb_fs_snapshot(args))


def nisb_fs_trash_list(args: Dict[str, Any]) -> Dict[str, Any]:
    op = "nisb_fs_trash_list"
    ok, msg, reason, _ = enforce_fs_capability_gate(
        args=args,
        operation=op,
        paths=["agent_files/.trash"],
        is_read=True,
    )
    if not ok:
        return _deny(args, msg, reason, op)
    return _wrap(args, op, _nisb_fs_trash_list(args))


def nisb_file_read(args: Dict[str, Any]) -> Dict[str, Any]:
    op = "nisb_file_read"
    filename = str(args.get("filename") or "").strip()
    paths = [filename] if filename else ["agent_files"]
    ok, msg, reason, _ = enforce_fs_capability_gate(
        args=args,
        operation=op,
        paths=paths,
        is_read=True,
    )
    if not ok:
        return _deny(args, msg, reason, op)
    return _wrap(args, op, _nisb_file_read(args))


def nisb_file_create(args: Dict[str, Any]) -> Dict[str, Any]:
    op = "nisb_file_create"
    ok, msg, reason, _ = enforce_fs_capability_gate(
        args=args,
        operation=op,
        paths=[str(args.get("filename") or "")],
        is_write=True,
        is_dangerous=False,
    )
    if not ok:
        return _deny(args, msg, reason, op)
    return _wrap(args, op, _nisb_file_create(args))


def nisb_dir_create(args: Dict[str, Any]) -> Dict[str, Any]:
    op = "nisb_dir_create"
    ok, msg, reason, _ = enforce_fs_capability_gate(
        args=args,
        operation=op,
        paths=[str(args.get("path") or "")],
        is_write=True,
        is_dangerous=False,
    )
    if not ok:
        return _deny(args, msg, reason, op)
    return _wrap(args, op, _nisb_dir_create(args))


def nisb_file_update(args: Dict[str, Any]) -> Dict[str, Any]:
    op = "nisb_file_update"
    filename = str(args.get("filename") or "").strip()
    paths = [filename] if filename else []
    ok, msg, reason, _ = enforce_fs_capability_gate(
        args=args,
        operation=op,
        paths=paths,
        is_write=True,
        is_dangerous=False,
    )
    if not ok:
        return _deny(args, msg, reason, op)
    return _wrap(args, op, _nisb_file_update(args))


def nisb_file_delete(args: Dict[str, Any]) -> Dict[str, Any]:
    op = "nisb_file_delete"
    filename = str(args.get("filename") or "").strip()
    paths = [filename] if filename else []
    ok, msg, reason, _ = enforce_fs_capability_gate(
        args=args,
        operation=op,
        paths=paths,
        is_write=True,
        is_dangerous=False,
    )
    if not ok:
        return _deny(args, msg, reason, op)
    return _wrap(args, op, _nisb_file_delete(args))


def nisb_dir_delete(args: Dict[str, Any]) -> Dict[str, Any]:
    op = "nisb_dir_delete"
    ok, msg, reason, _ = enforce_fs_capability_gate(
        args=args,
        operation=op,
        paths=[str(args.get("path") or "")],
        is_write=True,
        is_dangerous=False,
    )
    if not ok:
        return _deny(args, msg, reason, op)
    return _wrap(args, op, _nisb_dir_delete(args))


def nisb_file_move_path(args: Dict[str, Any]) -> Dict[str, Any]:
    op = "nisb_file_move_path"
    ok, msg, reason, _ = enforce_fs_capability_gate(
        args=args,
        operation=op,
        paths=[str(args.get("old_path") or ""), str(args.get("new_path") or "")],
        is_write=True,
        is_dangerous=False,
    )
    if not ok:
        return _deny(args, msg, reason, op)
    return _wrap(args, op, _nisb_file_move_path(args))


def nisb_dir_move_path(args: Dict[str, Any]) -> Dict[str, Any]:
    op = "nisb_dir_move_path"
    ok, msg, reason, _ = enforce_fs_capability_gate(
        args=args,
        operation=op,
        paths=[str(args.get("old_path") or ""), str(args.get("new_path") or "")],
        is_write=True,
        is_dangerous=False,
    )
    if not ok:
        return _deny(args, msg, reason, op)
    return _wrap(args, op, _nisb_dir_move_path(args))


def nisb_file_rename(args: Dict[str, Any]) -> Dict[str, Any]:
    op = "nisb_file_rename"
    ok, msg, reason, _ = enforce_fs_capability_gate(
        args=args,
        operation=op,
        paths=[str(args.get("old_path") or "")],
        is_write=True,
        is_dangerous=False,
    )
    if not ok:
        return _deny(args, msg, reason, op)
    return _wrap(args, op, _nisb_file_rename(args))


def nisb_dir_delete_recursive(args: Dict[str, Any]) -> Dict[str, Any]:
    op = "nisb_dir_delete_recursive"
    ok, msg, reason, _ = enforce_fs_capability_gate(
        args=args,
        operation=op,
        paths=[str(args.get("path") or "")],
        is_write=True,
        is_dangerous=True,
    )
    if not ok:
        return _deny(args, msg, reason, op)
    return _wrap(args, op, _nisb_dir_delete_recursive(args))


def nisb_fs_bulk_delete(args: Dict[str, Any]) -> Dict[str, Any]:
    op = "nisb_fs_bulk_delete"
    paths = args.get("paths")
    if not isinstance(paths, list):
        paths = []
    ok, msg, reason, _ = enforce_fs_capability_gate(
        args=args,
        operation=op,
        paths=[str(p) for p in paths],
        is_write=True,
        is_dangerous=True,
    )
    if not ok:
        return _deny(args, msg, reason, op)
    return _wrap(args, op, _nisb_fs_bulk_delete(args))


def nisb_fs_bulk_restore(args: Dict[str, Any]) -> Dict[str, Any]:
    op = "nisb_fs_bulk_restore"
    ok, msg, reason, _ = enforce_fs_capability_gate(
        args=args,
        operation=op,
        paths=["agent_files/.trash"],
        is_write=True,
        is_dangerous=False,
    )
    if not ok:
        return _deny(args, msg, reason, op)
    return _wrap(args, op, _nisb_fs_bulk_restore(args))


def nisb_fs_trash_restore(args: Dict[str, Any]) -> Dict[str, Any]:
    op = "nisb_fs_trash_restore"
    ok, msg, reason, _ = enforce_fs_capability_gate(
        args=args,
        operation=op,
        paths=["agent_files/.trash"],
        is_write=True,
        is_dangerous=False,
    )
    if not ok:
        return _deny(args, msg, reason, op)
    return _wrap(args, op, _nisb_fs_trash_restore(args))

