from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional

from ..filesystem import (
    nisb_dir_tree,
    nisb_file_create,
    nisb_file_read,
    nisb_file_update,
    nisb_fs_snapshot,
)
from ..filesystem.audit_log import append_fs_audit_event
from .room_contracts import as_bool, utc_iso
from .room_workspace import resolve_room_supervisor_fs_boundary


def _safe_str(value: Any, default: str = "") -> str:
    if value is None:
        return default
    text = str(value).strip()
    return text if text else default


def _safe_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _safe_list(value: Any) -> List[Any]:
    return value if isinstance(value, list) else []


def _normalize_logical_path(value: Any) -> str:
    raw = _safe_str(value).replace("\\", "/")
    while "//" in raw:
        raw = raw.replace("//", "/")
    if raw in {".", "./"}:
        return "."
    raw = raw.strip("/")
    if not raw:
        return ""
    parts = [part.strip() for part in raw.split("/") if part and part not in {".", ".."}]
    return "/".join(parts)


def _normalize_relative_payload_path(value: Any) -> str:
    raw = _safe_str(value).replace("\\", "/").strip()
    while "//" in raw:
        raw = raw.replace("//", "/")
    if raw in {".", "./"}:
        return "."
    return _normalize_logical_path(raw)


def _normalize_filename(value: Any, fallback: str = "supervisor.md") -> str:
    raw = _safe_str(value).replace("\\", "/").strip()
    if not raw:
        return fallback
    base = raw.split("/")[-1].strip()
    if not base or base in {".", ".."}:
        return fallback
    if not base.lower().endswith(".md"):
        base = f"{base}.md"
    return base


def _unique_paths(values: List[str]) -> List[str]:
    out: List[str] = []
    seen = set()
    for item in values:
        value = _normalize_logical_path(item)
        if not value or value in seen:
            continue
        seen.add(value)
        out.append(value)
    return out


def _normalize_status(value: Any) -> str:
    token = _safe_str(value).lower()
    if token in {"success", "ok", "succeeded"}:
        return "success"
    if token in {"warning", "partial_success", "partial_error"}:
        return "warning"
    if token in {"error", "failed", "fail"}:
        return "error"
    if token in {"disabled", "denied"}:
        return token
    return token or ""


def _relative_to_root(root: Any, target: Any) -> str:
    normalized_root = _normalize_logical_path(root)
    normalized_target = _normalize_logical_path(target)
    if not normalized_target:
        return ""
    if not normalized_root:
        return normalized_target
    if normalized_target == normalized_root:
        return "."
    prefix = normalized_root + "/"
    if normalized_target.startswith(prefix):
        rel = normalized_target[len(prefix):].strip("/")
        return rel or "."
    return normalized_target


def _join_under_root(root: Any, target: Any) -> str:
    normalized_root = _normalize_logical_path(root)
    normalized_target = _normalize_logical_path(target)
    if not normalized_target or normalized_target == ".":
        return normalized_root
    if not normalized_root:
        return normalized_target
    if normalized_target == normalized_root:
        return normalized_root
    prefix = normalized_root + "/"
    if normalized_target.startswith(prefix):
        return normalized_target
    return f"{normalized_root}/{normalized_target}"


def _candidate_objects(record: Any) -> List[Dict[str, Any]]:
    root = _safe_dict(record)
    if not root:
        return []

    out: List[Dict[str, Any]] = []

    def push(value: Any) -> None:
        obj = _safe_dict(value)
        if obj:
            out.append(obj)

    push(root.get("data"))
    push(root.get("result"))
    push(root.get("payload"))
    push(root.get("value"))
    push(root)

    for row in _safe_list(root.get("tool_results")):
        row_obj = _safe_dict(row)
        push(row_obj.get("data"))
        push(row_obj.get("result"))
        push(row_obj.get("payload"))
        push(row_obj.get("value"))
        push(row_obj)

    return out


def _unwrap_primary(record: Any) -> Dict[str, Any]:
    candidates = _candidate_objects(record)

    for obj in candidates:
        for key in ("documents", "files", "items"):
            rows = obj.get(key)
            if isinstance(rows, list) and rows:
                return obj

    for obj in candidates:
        for key in ("data", "result", "payload", "value"):
            candidate = _safe_dict(obj.get(key))
            if candidate:
                return candidate

    for obj in candidates:
        if obj:
            return obj

    return {}


def _extract_message(record: Any, fallback: str = "") -> str:
    candidates: List[Any] = []
    for obj in _candidate_objects(record):
        candidates.extend(
            [
                obj.get("message"),
                obj.get("response"),
                obj.get("content"),
                obj.get("text"),
                obj.get("error"),
            ]
        )

    for item in candidates:
        value = _safe_str(item)
        if value:
            return value
    return fallback


def _extract_text_payload(record: Any) -> str:
    candidates = _candidate_objects(record)
    preferred_keys = ("content", "text", "file_content", "body", "response")
    for key in preferred_keys:
        for obj in candidates:
            value = _safe_str(obj.get(key))
            if value:
                return value
    return ""


def _extract_entries(record: Any) -> List[Dict[str, Any]]:
    for obj in _candidate_objects(record):
        for key in ("entries", "items", "children"):
            rows = obj.get(key)
            if isinstance(rows, list):
                return [row for row in rows if isinstance(row, dict)]
    return []


def _extract_previews(record: Any) -> List[Dict[str, Any]]:
    for obj in _candidate_objects(record):
        for key in ("previews", "preview_files", "excerpts"):
            rows = obj.get(key)
            if isinstance(rows, list):
                return [row for row in rows if isinstance(row, dict)]
    return []


def _result_success(record: Any) -> bool:
    status = _normalize_status(_safe_dict(record).get("status"))
    if status in {"success", "warning"}:
        return True
    if status in {"error", "denied", "disabled"}:
        return False

    root = _safe_dict(record)
    for candidate in (
        root.get("success"),
        _safe_dict(root.get("data")).get("success"),
        _safe_dict(root.get("result")).get("success"),
        _safe_dict(root.get("payload")).get("success"),
        _safe_dict(root.get("value")).get("success"),
    ):
        if candidate is True:
            return True
        if candidate is False:
            return False

    return False


def _request_identity(request_args: Dict[str, Any]) -> Dict[str, str]:
    args = _safe_dict(request_args)
    return {
        "user_id": _safe_str(args.get("user_id")),
        "email": _safe_str(args.get("_librechat_email") or args.get("email")),
        "name": _safe_str(args.get("_librechat_name") or args.get("name")),
    }


def _room_actor_context(request_args: Dict[str, Any]) -> Dict[str, Any]:
    args = _safe_dict(request_args)
    actor = _safe_dict(args.get("room_actor_context"))
    supervisor_ctx = _safe_dict(args.get("room_supervisor_context"))

    actor_type = _safe_str(
        actor.get("actor_type") or supervisor_ctx.get("actor_type"),
        "supervisor",
    )
    actor_id = _safe_str(
        actor.get("actor_id") or supervisor_ctx.get("actor_id"),
        actor_type,
    )

    return {
        "actor_type": actor_type,
        "actor_id": actor_id or actor_type,
        "skill_id": _safe_str(actor.get("skill_id") or supervisor_ctx.get("skill_id")),
        "delegated_from": _safe_str(actor.get("delegated_from") or supervisor_ctx.get("delegated_from")),
    }


def _is_write_like_operation(operation: str) -> bool:
    op = _safe_str(operation).lower()
    return any(token in op for token in ("write", "update", "create", "delete", "dangerous"))


def _normalize_fs_read_scope(value: Any, fallback: str = "user_ro") -> str:
    token = _safe_str(value).lower()
    if token == "minimal":
        return "minimal"
    if token == "user_ro":
        return "user_ro"
    return fallback if fallback in {"minimal", "user_ro"} else "user_ro"


def _fs_read_scope_from_boundary(boundary: Dict[str, Any]) -> str:
    mcp = _safe_dict(boundary.get("mcp_overrides"))
    return _normalize_fs_read_scope(mcp.get("fs_read_scope"), "user_ro")


def _with_forced_fs_read_scope(boundary: Dict[str, Any], scope: str) -> Dict[str, Any]:
    out = dict(_safe_dict(boundary))
    mcp = dict(_safe_dict(out.get("mcp_overrides")))
    mcp["fs_read_scope"] = _normalize_fs_read_scope(scope, "user_ro")
    out["mcp_overrides"] = mcp
    return out


def _with_forced_focus_root(boundary: Dict[str, Any], focus_root: str) -> Dict[str, Any]:
    normalized_focus_root = _normalize_logical_path(focus_root)
    out = dict(_safe_dict(boundary))
    if not normalized_focus_root:
        return out

    out["effective_focus_root"] = normalized_focus_root
    out["resolved_focus_root"] = normalized_focus_root

    allowed_read_roots = _unique_paths(
        _safe_list(out.get("allowed_read_roots")) + [normalized_focus_root]
    )
    if allowed_read_roots:
        out["allowed_read_roots"] = allowed_read_roots

    return out


def _fs_write_scope_for_operation(boundary: Dict[str, Any], operation: str) -> str:
    if not _is_write_like_operation(operation):
        return "none"
    root = _safe_str(boundary.get("effective_focus_root") or boundary.get("resolved_focus_root"))
    return "agent_files" if root else "none"


def _capability_gate_focus_root(boundary: Dict[str, Any], operation: str) -> str:
    effective_focus_root = _safe_str(boundary.get("effective_focus_root"))
    resolved_focus_root = _safe_str(boundary.get("resolved_focus_root"))
    if _is_write_like_operation(operation):
        return resolved_focus_root or effective_focus_root
    return effective_focus_root or resolved_focus_root


def _capability_gate_allowed_write_roots(boundary: Dict[str, Any], operation: str) -> List[str]:
    existing = _unique_paths(_safe_list(boundary.get("allowed_write_roots")))
    effective_focus_root = _safe_str(boundary.get("effective_focus_root"))
    resolved_focus_root = _safe_str(boundary.get("resolved_focus_root"))

    if not _is_write_like_operation(operation):
        return existing

    merged = _unique_paths(existing + [resolved_focus_root or effective_focus_root])
    return merged


def _build_capability_gate(
    *,
    boundary: Dict[str, Any],
    room_id: str,
    request_args: Dict[str, Any],
    operation: str,
    run_id: str = "",
    supervisor_event_id: str = "",
    final_event_id: str = "",
) -> Dict[str, Any]:
    args = _safe_dict(request_args)
    gate_focus_root = _capability_gate_focus_root(boundary, operation)
    return {
        "policy_version": 1,
        "workspace_id": _safe_str(boundary.get("workspace_id")),
        "focus_root": gate_focus_root,
        "fs_read_scope": _fs_read_scope_from_boundary(boundary),
        "fs_write_scope": _fs_write_scope_for_operation(boundary, operation),
        "fs_dangerous_enabled": as_bool(boundary.get("dangerous_enabled"), False),
        "allowed_read_roots": _safe_list(boundary.get("allowed_read_roots")),
        "allowed_write_roots": _capability_gate_allowed_write_roots(boundary, operation),
        "room_id": _safe_str(room_id),
        "request_id": _safe_str(args.get("request_id")),
        "run_id": _safe_str(run_id),
        "supervisor_event_id": _safe_str(supervisor_event_id),
        "final_event_id": _safe_str(final_event_id),
        "workspace_name": _safe_str(boundary.get("workspace_name")),
        "effective_focus_root": _safe_str(boundary.get("effective_focus_root")),
        "resolved_focus_root": _safe_str(boundary.get("resolved_focus_root")),
        "source": "room_supervisor",
        "operation": _safe_str(operation),
    }


def _normalize_user_ro_payload(
    *,
    boundary: Dict[str, Any],
    operation: str,
    payload: Dict[str, Any],
) -> Dict[str, Any]:
    out = dict(_safe_dict(payload))
    if _fs_read_scope_from_boundary(boundary) != "user_ro":
        return out

    focus_root = _safe_str(boundary.get("effective_focus_root"))
    if not focus_root:
        return out

    if operation == "room_supervisor_fs_probe":
        out["path"] = "."
        out["relative_path"] = "."
        out["focus_root"] = focus_root
        return out

    if operation == "room_supervisor_skills_probe":
        rel = _normalize_relative_payload_path(
            out.get("relative_path") or out.get("path")
        ) or "_room_supervisor_skills"
        out["path"] = rel
        out["relative_path"] = rel
        out["focus_root"] = focus_root
        return out

    if operation not in {
        "room_supervisor_fs_read",
        "room_supervisor_notebook_read_existing",
    }:
        return out

    filename = _safe_str(out.get("filename"))
    path_value = _safe_str(out.get("path"))
    relative_path = _safe_str(out.get("relative_path"))

    if filename:
        out["filename"] = _relative_to_root(focus_root, filename) or "."
    if path_value:
        out["path"] = _relative_to_root(focus_root, path_value) or "."
    if relative_path:
        out["relative_path"] = _relative_to_root(focus_root, relative_path) or "."

    filenames = out.get("filenames")
    if isinstance(filenames, list):
        normalized_filenames = []
        for item in filenames:
            rel = _relative_to_root(focus_root, item)
            if rel:
                normalized_filenames.append(rel)
        if normalized_filenames:
            out["filenames"] = normalized_filenames

    paths = out.get("paths")
    if isinstance(paths, list):
        normalized_paths = []
        for item in paths:
            rel = _relative_to_root(focus_root, item)
            if rel:
                normalized_paths.append(rel)
        if normalized_paths:
            out["paths"] = normalized_paths

    out["focus_root"] = focus_root
    return out


def _merge_request_args(
    *,
    request_args: Dict[str, Any],
    boundary: Dict[str, Any],
    operation: str,
    payload: Dict[str, Any],
    run_id: str = "",
    supervisor_event_id: str = "",
    final_event_id: str = "",
) -> Dict[str, Any]:
    out = dict(_safe_dict(request_args))
    clean_payload = _normalize_user_ro_payload(
        boundary=boundary,
        operation=operation,
        payload=_safe_dict(payload),
    )

    gate = _build_capability_gate(
        boundary=boundary,
        room_id=_safe_str(boundary.get("room_id")),
        request_args=request_args,
        operation=operation,
        run_id=run_id,
        supervisor_event_id=supervisor_event_id,
        final_event_id=final_event_id,
    )
    gate_focus_root = _safe_str(gate.get("focus_root"))
    effective_focus_root = _safe_str(boundary.get("effective_focus_root"))
    resolved_focus_root = _safe_str(boundary.get("resolved_focus_root"))

    out.update(clean_payload)
    out["capability_gate"] = gate

    if gate_focus_root:
        out["focus_root"] = gate_focus_root
    if effective_focus_root:
        out["effective_focus_root"] = effective_focus_root
    if resolved_focus_root:
        out["resolved_focus_root"] = resolved_focus_root
        out["write_focus_root"] = resolved_focus_root

    allowed_read_roots = _safe_list(gate.get("allowed_read_roots"))
    allowed_write_roots = _safe_list(gate.get("allowed_write_roots"))
    if allowed_read_roots:
        out["allowed_read_roots"] = allowed_read_roots
    if allowed_write_roots:
        out["allowed_write_roots"] = allowed_write_roots

    filename = _normalize_logical_path(clean_payload.get("filename"))
    path_value = _normalize_relative_payload_path(clean_payload.get("path"))
    relative_path = _normalize_relative_payload_path(clean_payload.get("relative_path"))

    if filename:
        out["filename"] = filename
        if not path_value:
            out["path"] = filename
        if not relative_path:
            out["relative_path"] = filename

    if path_value:
        out["path"] = path_value
    if relative_path:
        out["relative_path"] = relative_path

    filenames = clean_payload.get("filenames")
    if isinstance(filenames, list):
        normalized_filenames = _unique_paths([_safe_str(x) for x in filenames])
        if normalized_filenames:
            out["filenames"] = normalized_filenames
            out["paths"] = normalized_filenames

    paths = clean_payload.get("paths")
    if isinstance(paths, list):
        normalized_paths = [_normalize_relative_payload_path(x) for x in paths]
        normalized_paths = [x for x in normalized_paths if x]
        if normalized_paths:
            out["paths"] = normalized_paths
            if "filenames" not in out:
                out["filenames"] = normalized_paths

    return out


def _tool_call_item(
    name: str,
    *,
    source_tool_name: str,
    args: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    return {
        "tool_name": _safe_str(name),
        "name": _safe_str(name),
        "source_tool_name": _safe_str(source_tool_name),
        "args": _safe_dict(args),
        "ts": utc_iso(),
    }


def _tool_result_item(
    type_name: str,
    *,
    tool_name: str,
    source_tool_name: str,
    **payload: Any,
) -> Dict[str, Any]:
    row = {
        "type": _safe_str(type_name),
        "tool_name": _safe_str(tool_name),
        "name": _safe_str(tool_name),
        "source_tool_name": _safe_str(source_tool_name),
    }
    row.update(payload)
    return row


def _append_room_fs_audit(
    *,
    request_args: Dict[str, Any],
    event: Dict[str, Any],
) -> None:
    identity = _request_identity(request_args)
    if not identity.get("user_id"):
        return
    try:
        append_fs_audit_event(
            user_id=identity["user_id"],
            email=identity["email"],
            name=identity["name"],
            event=event,
        )
    except Exception:
        return


def _call_guarded_tool(
    *,
    fn: Callable[[Dict[str, Any]], Dict[str, Any]],
    request_args: Dict[str, Any],
    boundary: Dict[str, Any],
    operation: str,
    payload: Dict[str, Any],
    run_id: str = "",
    supervisor_event_id: str = "",
    final_event_id: str = "",
) -> Dict[str, Any]:
    merged = _merge_request_args(
        request_args=request_args,
        boundary=boundary,
        operation=operation,
        payload=payload,
        run_id=run_id,
        supervisor_event_id=supervisor_event_id,
        final_event_id=final_event_id,
    )
    result = fn(merged)
    return _safe_dict(result)


def _normalize_output_path(
    *,
    scope: str,
    focus_root: str,
    candidate_path: Any,
    fallback_path: str = "",
) -> str:
    candidate = _normalize_logical_path(candidate_path)
    fallback = _normalize_logical_path(fallback_path)

    if scope == "user_ro":
        if candidate:
            full = _join_under_root(focus_root, candidate)
            if full:
                return full
        if fallback:
            return fallback
        return _normalize_logical_path(focus_root)

    return candidate or fallback


def _normalize_rows_for_output(
    *,
    rows: List[Dict[str, Any]],
    scope: str,
    focus_root: str,
) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for row in rows:
        obj = dict(_safe_dict(row))
        if not obj:
            continue
        candidate = obj.get("path") or obj.get("relative_path") or obj.get("filename")
        normalized = _normalize_output_path(
            scope=scope,
            focus_root=focus_root,
            candidate_path=candidate,
            fallback_path="",
        )
        if normalized:
            obj["path"] = normalized
        out.append(obj)
    return out


def _single_document_from_read_packet(
    *,
    packet: Dict[str, Any],
    requested_display_path: str,
    focus_root: str,
    scope: str,
) -> Dict[str, Any]:
    primary = _unwrap_primary(packet)
    rows = primary.get("documents") or primary.get("files") or primary.get("items")

    base: Dict[str, Any] = {}
    if isinstance(rows, list) and rows:
        base = dict(_safe_dict(rows[0]))

    read_text = _extract_text_payload(packet)
    message = _extract_message(packet, "filesystem read completed")
    status = "success" if _result_success(packet) else _normalize_status(packet.get("status")) or "error"

    logical_path = _normalize_output_path(
        scope=scope,
        focus_root=focus_root,
        candidate_path=base.get("path") or base.get("relative_path") or base.get("filename"),
        fallback_path=requested_display_path,
    )

    if logical_path:
        base["path"] = logical_path
    if "content" not in base and read_text:
        base["content"] = read_text
    if "status" not in base and status:
        base["status"] = status
    if "message" not in base and message:
        base["message"] = message

    if not base:
        base = {
            "path": requested_display_path,
            "content": read_text,
            "status": status,
            "message": message,
        }

    return base

def _looks_like_fs_error_text(text: Any) -> bool:
    raw = _safe_str(text)
    if not raw:
        return False

    lowered = raw.lower()
    return (
        raw.startswith("❌")
        or "文件不存在" in raw
        or "文件路径不存在" in raw
        or "file not found" in lowered
        or "path not found" in lowered
        or "permission denied" in lowered
        or "如果要访问storage目录" in raw
        or "not allowed" in lowered
        or "读取失败" in raw
    )

def _room_fs_dispatch(
    *,
    fn: Callable[[Dict[str, Any]], Dict[str, Any]],
    source_tool_name: str,
    request_args: Dict[str, Any],
    boundary: Dict[str, Any],
    operation: str,
    payload: Dict[str, Any],
    run_id: str = "",
    supervisor_event_id: str = "",
    final_event_id: str = "",
) -> Dict[str, Any]:
    packet = _call_guarded_tool(
        fn=fn,
        request_args=request_args,
        boundary=boundary,
        operation=operation,
        payload=payload,
        run_id=run_id,
        supervisor_event_id=supervisor_event_id,
        final_event_id=final_event_id,
    )

    return {
        "packet": _safe_dict(packet),
        "dispatch": {
            "mode": "local_guarded_tool",
            "source_tool_name": _safe_str(source_tool_name),
            "boundary_workspace_id": _safe_str(boundary.get("workspace_id")),
            "boundary_effective_focus_root": _safe_str(boundary.get("effective_focus_root")),
            "boundary_resolved_focus_root": _safe_str(boundary.get("resolved_focus_root")),
            "room_id": _safe_str(boundary.get("room_id")),
            "request_id": _safe_str(boundary.get("request_id")),
            "operation": _safe_str(operation),
        },
    }

def room_supervisor_fs_probe(
    *,
    room_id: str,
    request_args: Dict[str, Any],
    scope: str = "",
    run_id: str = "",
    supervisor_event_id: str = "",
    final_event_id: str = "",
) -> Dict[str, Any]:
    boundary = resolve_room_supervisor_fs_boundary(
        room_id=room_id,
        request_args=request_args,
        target_paths=[],
        mode="read",
        require_focus_root=True,
    )
    mcp = _safe_dict(boundary.get("mcp_overrides"))
    effective_scope = _safe_str(scope or mcp.get("fs_read_scope") or "minimal").lower()
    if effective_scope not in {"minimal", "user_ro"}:
        effective_scope = "minimal"

    if not as_bool(mcp.get("fs_read_enabled"), False):
        return {
            "enabled": False,
            "status": "disabled",
            "message": "fs_read not enabled",
            "reason_code": "FS_READ_DISABLED",
            "focus_root": _safe_str(boundary.get("effective_focus_root")),
            "scope": effective_scope,
            "tool_calls": [],
            "tool_results": [],
            "entries": [],
            "entries_count": 0,
            "previews": [],
            "text": "",
            "boundary": boundary,
            "recorded_at": utc_iso(),
        }

    if not boundary.get("allowed"):
        return {
            "enabled": True,
            "status": "denied",
            "message": _safe_str(boundary.get("message"), "boundary denied"),
            "reason_code": _safe_str(boundary.get("reason_code"), "BOUNDARY_DENIED"),
            "focus_root": _safe_str(boundary.get("effective_focus_root")),
            "scope": effective_scope,
            "tool_calls": [],
            "tool_results": [],
            "entries": [],
            "entries_count": 0,
            "previews": [],
            "text": "",
            "boundary": boundary,
            "recorded_at": utc_iso(),
        }

    focus_root = _safe_str(boundary.get("effective_focus_root"))
    source_tool_name = "nisb_fs_snapshot" if effective_scope == "minimal" else "nisb_dir_tree"
    source_tool = nisb_fs_snapshot if effective_scope == "minimal" else nisb_dir_tree

    if effective_scope == "minimal":
        payload = {
            "path": focus_root,
            "relative_path": focus_root,
            "focus_root": focus_root,
        }
    else:
        payload = {
            "path": ".",
            "relative_path": ".",
            "focus_root": focus_root,
        }

    raw = _call_guarded_tool(
        fn=source_tool,
        request_args=request_args,
        boundary=boundary,
        operation="room_supervisor_fs_probe",
        payload=payload,
        run_id=run_id,
        supervisor_event_id=supervisor_event_id,
        final_event_id=final_event_id,
    )

    status = "success" if _result_success(raw) else _normalize_status(raw.get("status")) or "error"
    entries = _normalize_rows_for_output(
        rows=_extract_entries(raw),
        scope=effective_scope,
        focus_root=focus_root,
    )
    previews = _normalize_rows_for_output(
        rows=_extract_previews(raw),
        scope=effective_scope,
        focus_root=focus_root,
    )
    text = _extract_text_payload(raw)
    message = _extract_message(raw, "filesystem probe completed")

    tool_calls = [
        _tool_call_item(
            "nisb_supervisor_fs_read",
            source_tool_name=source_tool_name,
            args={
                "path": focus_root,
                "focus_root": focus_root,
                "scope": effective_scope,
                "mode": "room_supervisor_controlled_read",
            },
        )
    ]
    tool_results = [
        _tool_result_item(
            "room_supervisor_fs_probe",
            tool_name="nisb_supervisor_fs_read",
            source_tool_name=source_tool_name,
            status=status,
            focus_root=focus_root,
            scope=effective_scope,
            entries_count=len(entries),
            entries=entries,
            previews=previews,
            text=text,
            message=message,
        )
    ]

    _append_room_fs_audit(
        request_args=request_args,
        event={
            "event": "room_supervisor_fs_probe",
            "operation": "room_supervisor_fs_probe",
            "request_id": _safe_str(request_args.get("request_id")),
            "room_id": _safe_str(room_id),
            "run_id": _safe_str(run_id),
            "supervisor_event_id": _safe_str(supervisor_event_id),
            "final_event_id": _safe_str(final_event_id),
            "paths": [focus_root],
            "metadata": {
                "scope": effective_scope,
                "status": status,
                "entries_count": len(entries),
                "source_tool_name": source_tool_name,
            },
        },
    )

    return {
        "enabled": True,
        "status": status,
        "message": message,
        "reason_code": "",
        "focus_root": focus_root,
        "scope": effective_scope,
        "tool_calls": tool_calls,
        "tool_results": tool_results,
        "entries": entries,
        "entries_count": len(entries),
        "previews": previews,
        "text": text,
        "boundary": boundary,
        "raw_result": raw,
        "recorded_at": utc_iso(),
    }


def _collect_markdown_skill_paths(
    *,
    rows: List[Dict[str, Any]],
    room_focus_root: str,
    skills_root_relative: str,
) -> List[str]:
    out: List[str] = []
    seen = set()

    skills_root = _join_under_root(room_focus_root, skills_root_relative)

    for row in rows:
        obj = _safe_dict(row)
        candidate = _normalize_logical_path(
            obj.get("path") or obj.get("relative_path") or obj.get("filename")
        )
        if not candidate or not candidate.lower().endswith(".md"):
            continue

        full_path = candidate
        if candidate == skills_root or candidate.startswith(skills_root + "/"):
            full_path = candidate
        elif candidate == skills_root_relative or candidate.startswith(skills_root_relative + "/"):
            full_path = _join_under_root(room_focus_root, candidate)
        else:
            continue

        if not full_path or full_path in seen:
            continue

        seen.add(full_path)
        out.append(full_path)

    return out

def _tag_content_source_kind(
    rows: List[Dict[str, Any]],
    default_kind: str,
) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for row in _safe_list(rows):
        obj = dict(_safe_dict(row))
        if not obj:
            continue

        kind = _safe_str(
            obj.get("content_source_kind")
            or obj.get("preview_source_kind")
            or obj.get("source_kind"),
            default_kind,
        )

        obj["preview_source_kind"] = kind
        obj["content_source_kind"] = kind
        out.append(obj)

    return out

def _merge_preview_rows(
    base_rows: List[Dict[str, Any]],
    extra_rows: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    out_by_key: Dict[str, Dict[str, Any]] = {}
    order: List[str] = []

    def _row_key(obj: Dict[str, Any]) -> str:
        key = _normalize_logical_path(
            obj.get("path") or obj.get("relative_path") or obj.get("filename")
        )
        return key or ""

    def _row_text(obj: Dict[str, Any]) -> str:
        for key in (
            "content",
            "text",
            "preview",
            "markdown",
            "raw_text",
            "full_text",
            "response",
            "body",
        ):
            text = _safe_str(obj.get(key))
            if text:
                return text
        return ""

    def _source_rank(obj: Dict[str, Any]) -> int:
        kind = _safe_str(
            obj.get("content_source_kind")
            or obj.get("preview_source_kind")
            or obj.get("source_kind")
        ).lower()

        if kind in {"file_read", "preview_read", "skill_file_read"}:
            return 300
        if kind in {"entry", "snapshot_entry", "fs_entry"}:
            return 200
        if kind in {"snapshot_preview", "preview", "fs_preview"}:
            return 100
        return 0

    def _score(obj: Dict[str, Any]) -> tuple:
        text = _row_text(obj)
        return (
            _source_rank(obj),
            1 if text else 0,
            len(text),
            1 if _safe_str(obj.get("relative_path")) else 0,
            1 if _safe_str(obj.get("path")) else 0,
        )

    def push(row: Dict[str, Any], default_kind: str) -> None:
        obj = dict(_safe_dict(row))
        if not obj:
            return

        if not _safe_str(obj.get("preview_source_kind")):
            obj["preview_source_kind"] = default_kind
        if not _safe_str(obj.get("content_source_kind")):
            obj["content_source_kind"] = _safe_str(obj.get("preview_source_kind"), default_kind)

        key = _row_key(obj)
        if not key:
            key = f"row_{len(order)}"

        current = out_by_key.get(key)
        if current is None:
            out_by_key[key] = obj
            order.append(key)
            return

        better = obj if _score(obj) > _score(current) else current
        other = current if better is obj else obj

        merged = dict(other)
        merged.update(
            {
                k: v
                for k, v in better.items()
                if v not in (None, "", [], {})
            }
        )

        if not _safe_str(merged.get("preview_source_kind")):
            merged["preview_source_kind"] = default_kind
        if not _safe_str(merged.get("content_source_kind")):
            merged["content_source_kind"] = _safe_str(
                merged.get("preview_source_kind"),
                default_kind,
            )

        out_by_key[key] = merged

    for row in _safe_list(base_rows):
        push(row, "snapshot_preview")
    for row in _safe_list(extra_rows):
        push(row, "file_read")

    return [out_by_key[key] for key in order]


def _read_skill_preview_rows(
    *,
    room_id: str,
    request_args: Dict[str, Any],
    boundary: Dict[str, Any],
    room_focus_root: str,
    skill_paths: List[str],
    run_id: str = "",
    supervisor_event_id: str = "",
    final_event_id: str = "",
) -> Dict[str, Any]:
    preview_rows: List[Dict[str, Any]] = []
    packets: List[Dict[str, Any]] = []
    packet_rows: List[Dict[str, Any]] = []

    for skill_path in skill_paths:
        dispatched = _room_fs_dispatch(
            fn=nisb_file_read,
            source_tool_name="nisb_file_read",
            request_args=request_args,
            boundary=boundary,
            operation="room_supervisor_skills_preview_read",
            payload={
                "filename": skill_path,
                "path": skill_path,
                "relative_path": skill_path,
                "focus_root": room_focus_root,
            },
            run_id=run_id,
            supervisor_event_id=supervisor_event_id,
            final_event_id=final_event_id,
        )

        packet = _safe_dict(dispatched.get("packet"))
        dispatch = _safe_dict(dispatched.get("dispatch"))
        packets.append(packet)

        packet_ok = _result_success(packet)
        packet_status = "success" if packet_ok else (_normalize_status(packet.get("status")) or "error")
        packet_text = _extract_text_payload(packet)
        packet_message = _extract_message(packet, "")

        packet_rows.append(
            {
                "requested_skill_path": skill_path,
                "status": packet_status,
                "success": packet_ok,
                "message": packet_message,
                "text_preview": _safe_str(packet_text)[:160],
                "dispatch_mode": _safe_str(dispatch.get("mode")),
                "source_tool_name": _safe_str(dispatch.get("source_tool_name")),
                "focus_root": room_focus_root,
                "boundary_workspace_id": _safe_str(dispatch.get("boundary_workspace_id")),
                "boundary_effective_focus_root": _safe_str(dispatch.get("boundary_effective_focus_root")),
                "boundary_resolved_focus_root": _safe_str(dispatch.get("boundary_resolved_focus_root")),
            }
        )

        if not packet_ok:
            continue

        row = _single_document_from_read_packet(
            packet=packet,
            requested_display_path=skill_path,
            focus_root=room_focus_root,
            scope="minimal",
        )
        if not row:
            continue

        row = dict(_safe_dict(row))

        text = _safe_str(row.get("content"))
        if not text:
            text = _extract_text_payload(packet)
            if text:
                row["content"] = text

        text = _safe_str(row.get("content"))
        if not text or _looks_like_fs_error_text(text):
            continue

        if not _safe_str(row.get("relative_path")):
            row["relative_path"] = _relative_to_root(
                room_focus_root,
                row.get("path") or skill_path,
            )

        if not _safe_str(row.get("path")):
            row["path"] = skill_path

        row["preview_source_kind"] = "file_read"
        row["content_source_kind"] = "file_read"
        row["requested_skill_path"] = skill_path
        row["dispatch_mode"] = _safe_str(dispatch.get("mode"))
        row["boundary_workspace_id"] = _safe_str(dispatch.get("boundary_workspace_id"))
        row["boundary_effective_focus_root"] = _safe_str(dispatch.get("boundary_effective_focus_root"))
        row["boundary_resolved_focus_root"] = _safe_str(dispatch.get("boundary_resolved_focus_root"))

        preview_rows.append(row)

    success_count = sum(1 for packet in packets if _result_success(packet))
    if packets and success_count == len(packets):
        status = "success"
    elif success_count > 0:
        status = "warning"
    elif packets:
        status = "error"
    else:
        status = "success"

    return {
        "status": status,
        "packets": packets,
        "packet_rows": packet_rows,
        "previews": preview_rows,
    }


def room_supervisor_skills_probe(
    *,
    room_id: str,
    request_args: Dict[str, Any],
    skills_dirname: str = "_room_supervisor_skills",
    run_id: str = "",
    supervisor_event_id: str = "",
    final_event_id: str = "",
) -> Dict[str, Any]:
    boundary = resolve_room_supervisor_fs_boundary(
        room_id=room_id,
        request_args=request_args,
        target_paths=[],
        mode="read",
        require_focus_root=True,
    )

    if not boundary.get("allowed"):
        return {
            "enabled": False,
            "status": "denied",
            "message": _safe_str(boundary.get("message"), "boundary denied"),
            "reason_code": _safe_str(boundary.get("reason_code"), "BOUNDARY_DENIED"),
            "focus_root": _safe_str(boundary.get("effective_focus_root")),
            "skills_root_relative": _normalize_logical_path(skills_dirname),
            "tool_calls": [],
            "tool_results": [],
            "entries": [],
            "entries_count": 0,
            "previews": [],
            "text": "",
            "boundary": boundary,
            "recorded_at": utc_iso(),
        }

    room_focus_root = _safe_str(boundary.get("effective_focus_root"))
    skills_root_relative = _normalize_logical_path(skills_dirname) or "_room_supervisor_skills"
    skills_root = _join_under_root(room_focus_root, skills_root_relative)

    probe_boundary = _with_forced_fs_read_scope(boundary, "minimal")

    dispatched = _room_fs_dispatch(
        fn=nisb_fs_snapshot,
        source_tool_name="nisb_fs_snapshot",
        request_args=request_args,
        boundary=probe_boundary,
        operation="room_supervisor_skills_probe",
        payload={
            "path": skills_root,
            "relative_path": skills_root,
            "focus_root": room_focus_root,
        },
        run_id=run_id,
        supervisor_event_id=supervisor_event_id,
        final_event_id=final_event_id,
    )
    raw = _safe_dict(dispatched.get("packet"))
    probe_dispatch = _safe_dict(dispatched.get("dispatch"))

    status = "success" if _result_success(raw) else _normalize_status(raw.get("status")) or "error"
    entries = _tag_content_source_kind(
        _normalize_rows_for_output(
            rows=_extract_entries(raw),
            scope="minimal",
            focus_root=room_focus_root,
        ),
        "entry",
    )
    snapshot_previews = _tag_content_source_kind(
        _normalize_rows_for_output(
            rows=_extract_previews(raw),
            scope="minimal",
            focus_root=room_focus_root,
        ),
        "snapshot_preview",
    )
    text = _extract_text_payload(raw)
    message = _extract_message(raw, "skills probe completed")

    skill_paths = _collect_markdown_skill_paths(
        rows=entries or snapshot_previews,
        room_focus_root=room_focus_root,
        skills_root_relative=skills_root_relative,
    )

    preview_read = _read_skill_preview_rows(
        room_id=room_id,
        request_args=request_args,
        boundary=probe_boundary,
        room_focus_root=room_focus_root,
        skill_paths=skill_paths,
        run_id=run_id,
        supervisor_event_id=supervisor_event_id,
        final_event_id=final_event_id,
    )
    preview_rows = _safe_list(preview_read.get("previews"))
    preview_packet_rows = _safe_list(preview_read.get("packet_rows"))
    previews = _merge_preview_rows(snapshot_previews, preview_rows)

    tool_calls = [
        _tool_call_item(
            "nisb_room_supervisor_skills_probe",
            source_tool_name="nisb_fs_snapshot",
            args={
                "path": skills_root,
                "focus_root": room_focus_root,
                "room_focus_root": room_focus_root,
                "mode": "room_supervisor_controlled_skills_probe",
                "fs_read_scope": "minimal",
                "dispatch_mode": _safe_str(probe_dispatch.get("mode")),
            },
        )
    ]

    if skill_paths:
        tool_calls.append(
            _tool_call_item(
                "nisb_room_supervisor_skill_preview_read",
                source_tool_name="nisb_file_read",
                args={
                    "paths": skill_paths,
                    "focus_root": room_focus_root,
                    "room_focus_root": room_focus_root,
                    "mode": "room_supervisor_controlled_skills_preview_read",
                    "fs_read_scope": "minimal",
                    "dispatch_mode": "local_guarded_tool",
                },
            )
        )

    tool_results = [
        _tool_result_item(
            "room_supervisor_skills_probe",
            tool_name="nisb_room_supervisor_skills_probe",
            source_tool_name="nisb_fs_snapshot",
            status=status,
            focus_root=room_focus_root,
            skills_root=skills_root,
            skills_root_relative=skills_root_relative,
            entries_count=len(entries),
            entries=entries,
            previews=previews,
            text=text,
            message=message,
            dispatch_mode=_safe_str(probe_dispatch.get("mode")),
            boundary_workspace_id=_safe_str(probe_dispatch.get("boundary_workspace_id")),
            boundary_effective_focus_root=_safe_str(probe_dispatch.get("boundary_effective_focus_root")),
            boundary_resolved_focus_root=_safe_str(probe_dispatch.get("boundary_resolved_focus_root")),
        )
    ]

    if skill_paths:
        tool_results.append(
            _tool_result_item(
                "room_supervisor_skill_preview_read",
                tool_name="nisb_room_supervisor_skill_preview_read",
                source_tool_name="nisb_file_read",
                status=_safe_str(preview_read.get("status"), "success"),
                focus_root=room_focus_root,
                skills_root=skills_root,
                skills_root_relative=skills_root_relative,
                paths=skill_paths,
                previews_count=len(preview_rows),
                previews=preview_rows,
                packet_rows=preview_packet_rows,
                boundary_workspace_id=_safe_str(probe_boundary.get("workspace_id")),
                boundary_effective_focus_root=_safe_str(probe_boundary.get("effective_focus_root")),
                boundary_resolved_focus_root=_safe_str(probe_boundary.get("resolved_focus_root")),
                message="skill preview read completed",
            )
        )

    _append_room_fs_audit(
        request_args=request_args,
        event={
            "event": "room_supervisor_skills_probe",
            "operation": "room_supervisor_skills_probe",
            "request_id": _safe_str(request_args.get("request_id")),
            "room_id": _safe_str(room_id),
            "run_id": _safe_str(run_id),
            "supervisor_event_id": _safe_str(supervisor_event_id),
            "final_event_id": _safe_str(final_event_id),
            "paths": [skills_root],
            "metadata": {
                "status": status,
                "entries_count": len(entries),
                "source_tool_name": "nisb_fs_snapshot",
                "skills_root_relative": skills_root_relative,
                "fs_read_scope": "minimal",
                "preview_reads_count": len(skill_paths),
                "preview_rows_count": len(preview_rows),
                "dispatch_mode": _safe_str(probe_dispatch.get("mode")),
                "boundary_workspace_id": _safe_str(probe_boundary.get("workspace_id")),
                "boundary_effective_focus_root": _safe_str(probe_boundary.get("effective_focus_root")),
                "boundary_resolved_focus_root": _safe_str(probe_boundary.get("resolved_focus_root")),
            },
        },
    )

    return {
        "enabled": True,
        "status": status,
        "message": message,
        "reason_code": "",
        "focus_root": room_focus_root,
        "skills_root": skills_root,
        "skills_root_relative": skills_root_relative,
        "tool_calls": tool_calls,
        "tool_results": tool_results,
        "entries": entries,
        "entries_count": len(entries),
        "previews": previews,
        "text": text,
        "boundary": boundary,
        "raw_result": raw,
        "recorded_at": utc_iso(),
    }


def room_supervisor_fs_read(
    *,
    room_id: str,
    request_args: Dict[str, Any],
    target_paths: List[str],
    run_id: str = "",
    supervisor_event_id: str = "",
    final_event_id: str = "",
) -> Dict[str, Any]:
    normalized_targets = _unique_paths(target_paths)
    boundary = resolve_room_supervisor_fs_boundary(
        room_id=room_id,
        request_args=request_args,
        target_paths=normalized_targets,
        mode="read",
        require_focus_root=True,
    )

    if not normalized_targets:
        return {
            "enabled": True,
            "status": "denied",
            "message": "missing target paths",
            "reason_code": "MISSING_TARGET_PATHS",
            "target_paths": [],
            "tool_calls": [],
            "tool_results": [],
            "documents": [],
            "text": "",
            "boundary": boundary,
            "recorded_at": utc_iso(),
        }

    if not boundary.get("allowed"):
        return {
            "enabled": True,
            "status": "denied",
            "message": _safe_str(boundary.get("message"), "boundary denied"),
            "reason_code": _safe_str(boundary.get("reason_code"), "BOUNDARY_DENIED"),
            "target_paths": normalized_targets,
            "tool_calls": [],
            "tool_results": [],
            "documents": [],
            "text": "",
            "boundary": boundary,
            "recorded_at": utc_iso(),
        }

    focus_root = _safe_str(boundary.get("effective_focus_root"))
    mcp = _safe_dict(boundary.get("mcp_overrides"))
    effective_scope = _normalize_fs_read_scope(mcp.get("fs_read_scope"), "minimal")

    actual_targets = normalized_targets
    if effective_scope == "user_ro":
        actual_targets = [_relative_to_root(focus_root, item) for item in normalized_targets]
        actual_targets = [item for item in actual_targets if item]

    source_tool_name = "nisb_file_read"
    packets: List[Dict[str, Any]] = []
    packet_rows: List[Dict[str, Any]] = []
    documents: List[Dict[str, Any]] = []
    text_blocks: List[str] = []

    for idx, target_path in enumerate(actual_targets):
        display_path = normalized_targets[idx] if idx < len(normalized_targets) else target_path

        dispatched = _room_fs_dispatch(
            fn=nisb_file_read,
            source_tool_name=source_tool_name,
            request_args=request_args,
            boundary=boundary,
            operation="room_supervisor_fs_read",
            payload={
                "filename": target_path,
                "path": target_path,
                "relative_path": target_path,
                "focus_root": focus_root,
            },
            run_id=run_id,
            supervisor_event_id=supervisor_event_id,
            final_event_id=final_event_id,
        )

        packet = _safe_dict(dispatched.get("packet"))
        dispatch = _safe_dict(dispatched.get("dispatch"))
        packets.append(packet)

        packet_text = _extract_text_payload(packet)
        packet_rows.append(
            {
                "requested_target_path": target_path,
                "display_path": display_path,
                "status": "success" if _result_success(packet) else (_normalize_status(packet.get("status")) or "error"),
                "success": _result_success(packet),
                "message": _extract_message(packet, ""),
                "text_preview": _safe_str(packet_text)[:160],
                "dispatch_mode": _safe_str(dispatch.get("mode")),
                "source_tool_name": _safe_str(dispatch.get("source_tool_name")),
                "boundary_workspace_id": _safe_str(dispatch.get("boundary_workspace_id")),
                "boundary_effective_focus_root": _safe_str(dispatch.get("boundary_effective_focus_root")),
                "boundary_resolved_focus_root": _safe_str(dispatch.get("boundary_resolved_focus_root")),
            }
        )

        row = _single_document_from_read_packet(
            packet=packet,
            requested_display_path=display_path,
            focus_root=focus_root,
            scope=effective_scope,
        )
        if row and _result_success(packet):
            documents.append(row)

        row_text = _safe_str(row.get("content")) if row else ""
        if not row_text and _result_success(packet):
            row_text = _extract_text_payload(packet)
        if row_text and not _looks_like_fs_error_text(row_text):
            text_blocks.append(row_text)

    success_count = sum(1 for packet in packets if _result_success(packet))
    if packets and success_count == len(packets):
        status = "success"
    elif success_count > 0:
        status = "warning"
    else:
        status = "error"

    read_text = "\n\n".join([block for block in text_blocks if _safe_str(block)])

    message = "filesystem read completed"
    if len(packets) == 1:
        message = _extract_message(packets[0], message)
    elif packets:
        message = f"filesystem read completed ({success_count}/{len(packets)})"

    tool_calls = [
        _tool_call_item(
            "nisb_supervisor_fs_read",
            source_tool_name=source_tool_name,
            args={
                "targets": normalized_targets,
                "focus_root": focus_root,
                "mode": "room_supervisor_controlled_read",
                "dispatch_mode": "local_guarded_tool",
            },
        )
    ]
    tool_results = [
        _tool_result_item(
            "room_supervisor_fs_read",
            tool_name="nisb_supervisor_fs_read",
            source_tool_name=source_tool_name,
            status=status,
            target_paths=normalized_targets,
            focus_root=focus_root,
            documents_count=len(documents),
            documents=documents,
            packet_rows=packet_rows,
            text=read_text,
            message=message,
            boundary_workspace_id=_safe_str(boundary.get("workspace_id")),
            boundary_effective_focus_root=_safe_str(boundary.get("effective_focus_root")),
            boundary_resolved_focus_root=_safe_str(boundary.get("resolved_focus_root")),
        )
    ]

    _append_room_fs_audit(
        request_args=request_args,
        event={
            "event": "room_supervisor_fs_read",
            "operation": "room_supervisor_fs_read",
            "request_id": _safe_str(request_args.get("request_id")),
            "room_id": _safe_str(room_id),
            "run_id": _safe_str(run_id),
            "supervisor_event_id": _safe_str(supervisor_event_id),
            "final_event_id": _safe_str(final_event_id),
            "paths": normalized_targets,
            "metadata": {
                "status": status,
                "documents_count": len(documents),
                "source_tool_name": source_tool_name,
                "scope": effective_scope,
                "boundary_workspace_id": _safe_str(boundary.get("workspace_id")),
                "boundary_effective_focus_root": _safe_str(boundary.get("effective_focus_root")),
                "boundary_resolved_focus_root": _safe_str(boundary.get("resolved_focus_root")),
            },
        },
    )

    return {
        "enabled": True,
        "status": status,
        "message": message,
        "reason_code": "",
        "target_paths": normalized_targets,
        "focus_root": focus_root,
        "scope": effective_scope,
        "tool_calls": tool_calls,
        "tool_results": tool_results,
        "documents": documents,
        "text": read_text,
        "boundary": boundary,
        "raw_result": {
            "status": status,
            "message": message,
            "results": packets,
            "documents": documents,
            "packet_rows": packet_rows,
        },
        "recorded_at": utc_iso(),
    }


def _resolve_supervisor_notebook_write_policy(
    *,
    request_args: Dict[str, Any],
    mcp_overrides: Dict[str, Any],
) -> Dict[str, Any]:
    actor = _room_actor_context(request_args)
    actor_type = _safe_str(actor.get("actor_type"), "supervisor")
    actor_id = _safe_str(actor.get("actor_id"), actor_type)

    notebook_write_enabled = as_bool(mcp_overrides.get("notebook_write_enabled"), False)

    if not notebook_write_enabled:
        return {
            "allowed": False,
            "status": "disabled",
            "reason_code": "SUPERVISOR_NOTEBOOK_WRITE_DISABLED",
            "message": "supervisor notebook write disabled by room policy",
            "actor_type": actor_type,
            "actor_id": actor_id,
            "skill_id": _safe_str(actor.get("skill_id")),
            "delegated_from": _safe_str(actor.get("delegated_from")),
        }

    if actor_type == "supervisor":
        return {
            "allowed": True,
            "status": "success",
            "reason_code": "",
            "message": "ok",
            "actor_type": actor_type,
            "actor_id": actor_id,
            "skill_id": _safe_str(actor.get("skill_id")),
            "delegated_from": _safe_str(actor.get("delegated_from")),
        }

    if actor_type == "worker":
        return {
            "allowed": False,
            "status": "denied",
            "reason_code": "WORKER_NOTEBOOK_WRITE_DENIED",
            "message": "worker cannot write supervisor notebook by default",
            "actor_type": actor_type,
            "actor_id": actor_id,
            "skill_id": _safe_str(actor.get("skill_id")),
            "delegated_from": _safe_str(actor.get("delegated_from")),
        }

    if actor_type == "skill":
        return {
            "allowed": False,
            "status": "denied",
            "reason_code": "SKILL_NOTEBOOK_WRITE_DENIED",
            "message": "skill cannot write supervisor notebook by default",
            "actor_type": actor_type,
            "actor_id": actor_id,
            "skill_id": _safe_str(actor.get("skill_id")),
            "delegated_from": _safe_str(actor.get("delegated_from")),
        }

    return {
        "allowed": False,
        "status": "denied",
        "reason_code": "UNKNOWN_ACTOR_TYPE",
        "message": "unknown room actor type",
        "actor_type": actor_type,
        "actor_id": actor_id,
        "skill_id": _safe_str(actor.get("skill_id")),
        "delegated_from": _safe_str(actor.get("delegated_from")),
    }


def _supervisor_notebook_policy_tool_result(
    *,
    policy: Dict[str, Any],
) -> Dict[str, Any]:
    row = _safe_dict(policy)
    return _tool_result_item(
        "room_supervisor_notebook_policy",
        tool_name="nisb_supervisor_notebook_write",
        source_tool_name="room_policy",
        status=_safe_str(row.get("status"), "denied"),
        allowed=as_bool(row.get("allowed"), False),
        actor_type=_safe_str(row.get("actor_type")),
        actor_id=_safe_str(row.get("actor_id")),
        skill_id=_safe_str(row.get("skill_id")),
        delegated_from=_safe_str(row.get("delegated_from")),
        reason_code=_safe_str(row.get("reason_code")),
        message=_safe_str(row.get("message")),
    )

def _looks_like_escaped_supervisor_notebook_markdown(text: str) -> bool:
    value = _safe_str(text)
    if "\\n" not in value and "\\r\\n" not in value:
        return False

    sample = value[:20000]
    markers = (
        "\\n# ",
        "\\n## ",
        "\\n### ",
        "\\n#### ",
        "\\n- ",
        "\\n* ",
        "\\n1. ",
        "\\n2. ",
        "\\n> ",
        "\\n```",
        "\\nSupervisor notebook",
        "\\n用户问题",
        "\\n问题",
        "\\n计划",
        "\\n结论",
        "\\n相关链接",
    )

    if any(marker in sample for marker in markers):
        return True

    escaped_newline_count = sample.count("\\n") + sample.count("\\r\\n")
    if escaped_newline_count < 3:
        return False

    markdown_hints = (
        "Supervisor notebook",
        "###",
        "##",
        "- ",
        "1. ",
        "final",
        "summary",
        "问题",
        "结论",
        "计划",
        "分析",
    )

    return any(hint in sample for hint in markdown_hints)


def _normalize_supervisor_notebook_markdown_content(content: Any) -> str:
    text = _safe_str(content)
    if not text:
        return ""

    if not _looks_like_escaped_supervisor_notebook_markdown(text):
        return text

    return (
        text
        .replace("\\r\\n", "\n")
        .replace("\\n", "\n")
        .replace("\\r", "\n")
    )

def room_supervisor_notebook_write(
    *,
    room_id: str,
    request_args: Dict[str, Any],
    content: str,
    run_id: str = "",
    supervisor_event_id: str = "",
    final_event_id: str = "",
) -> Dict[str, Any]:
    base_boundary = resolve_room_supervisor_fs_boundary(
        room_id=room_id,
        request_args=request_args,
        target_paths=[],
        mode="write",
        require_focus_root=True,
    )
    mcp = _safe_dict(base_boundary.get("mcp_overrides"))

    actor = _room_actor_context(request_args)
    policy = _resolve_supervisor_notebook_write_policy(
        request_args=request_args,
        mcp_overrides=mcp,
    )
    policy_tool_result = _supervisor_notebook_policy_tool_result(policy=policy)

    if not as_bool(policy.get("allowed"), False):
        result = {
            "enabled": False if _safe_str(policy.get("status")) == "disabled" else True,
            "status": _safe_str(policy.get("status"), "denied"),
            "message": _safe_str(policy.get("message"), "notebook write denied"),
            "reason_code": _safe_str(policy.get("reason_code"), "NOTEBOOK_WRITE_DENIED"),
            "policy_allowed": False,
            "policy_status": _safe_str(policy.get("status"), "denied"),
            "policy_reason_code": _safe_str(policy.get("reason_code"), "NOTEBOOK_WRITE_DENIED"),
            "policy_message": _safe_str(policy.get("message"), "notebook write denied"),
            "actor_type": _safe_str(actor.get("actor_type"), "supervisor"),
            "actor_id": _safe_str(actor.get("actor_id"), "supervisor"),
            "skill_id": _safe_str(actor.get("skill_id")),
            "delegated_from": _safe_str(actor.get("delegated_from")),
            "focus_root": _safe_str(base_boundary.get("effective_focus_root")),
            "relative_path": "",
            "bytes_written": 0,
            "bytes_appended": 0,
            "tool_calls": [],
            "tool_results": [policy_tool_result],
            "boundary": base_boundary,
            "recorded_at": utc_iso(),
        }

        _append_room_fs_audit(
            request_args=request_args,
            event={
                "event": "room_supervisor_notebook_write_denied",
                "operation": "room_supervisor_notebook_write",
                "request_id": _safe_str(request_args.get("request_id")),
                "room_id": _safe_str(room_id),
                "run_id": _safe_str(run_id),
                "supervisor_event_id": _safe_str(supervisor_event_id),
                "final_event_id": _safe_str(final_event_id),
                "paths": [],
                "metadata": {
                    "status": _safe_str(policy.get("status"), "denied"),
                    "reason_code": _safe_str(policy.get("reason_code")),
                    "actor_type": _safe_str(actor.get("actor_type"), "supervisor"),
                    "actor_id": _safe_str(actor.get("actor_id"), "supervisor"),
                    "skill_id": _safe_str(actor.get("skill_id")),
                    "delegated_from": _safe_str(actor.get("delegated_from")),
                },
            },
        )
        return result

    if not base_boundary.get("allowed"):
        return {
            "enabled": True,
            "status": "denied",
            "message": _safe_str(base_boundary.get("message"), "boundary denied"),
            "reason_code": _safe_str(base_boundary.get("reason_code"), "BOUNDARY_DENIED"),
            "policy_allowed": True,
            "policy_status": _safe_str(policy.get("status"), "success"),
            "policy_reason_code": _safe_str(policy.get("reason_code")),
            "policy_message": _safe_str(policy.get("message"), "ok"),
            "actor_type": _safe_str(actor.get("actor_type"), "supervisor"),
            "actor_id": _safe_str(actor.get("actor_id"), "supervisor"),
            "skill_id": _safe_str(actor.get("skill_id")),
            "delegated_from": _safe_str(actor.get("delegated_from")),
            "focus_root": _safe_str(base_boundary.get("effective_focus_root")),
            "relative_path": "",
            "bytes_written": 0,
            "bytes_appended": 0,
            "tool_calls": [],
            "tool_results": [policy_tool_result],
            "boundary": base_boundary,
            "recorded_at": utc_iso(),
        }

    effective_focus_root = _safe_str(base_boundary.get("effective_focus_root"))
    notebook_root = _safe_str(base_boundary.get("notebook_root"))
    notebook_filename = _normalize_filename(mcp.get("notebook_filename"), "supervisor.md")
    relative_path = _normalize_logical_path("/".join([notebook_root, notebook_filename]).strip("/"))

    if not effective_focus_root or not notebook_root or not relative_path:
        return {
            "enabled": True,
            "status": "denied",
            "message": "room focus_root is required",
            "reason_code": "MISSING_FOCUS_ROOT",
            "policy_allowed": True,
            "policy_status": _safe_str(policy.get("status"), "success"),
            "policy_reason_code": _safe_str(policy.get("reason_code")),
            "policy_message": _safe_str(policy.get("message"), "ok"),
            "actor_type": _safe_str(actor.get("actor_type"), "supervisor"),
            "actor_id": _safe_str(actor.get("actor_id"), "supervisor"),
            "skill_id": _safe_str(actor.get("skill_id")),
            "delegated_from": _safe_str(actor.get("delegated_from")),
            "focus_root": effective_focus_root,
            "relative_path": "",
            "bytes_written": 0,
            "bytes_appended": 0,
            "tool_calls": [],
            "tool_results": [policy_tool_result],
            "boundary": base_boundary,
            "recorded_at": utc_iso(),
        }

    write_boundary = resolve_room_supervisor_fs_boundary(
        room_id=room_id,
        request_args=request_args,
        target_paths=[relative_path],
        mode="write",
        require_focus_root=True,
    )
    if not write_boundary.get("allowed"):
        return {
            "enabled": True,
            "status": "denied",
            "message": _safe_str(write_boundary.get("message"), "boundary denied"),
            "reason_code": _safe_str(write_boundary.get("reason_code"), "BOUNDARY_DENIED"),
            "policy_allowed": True,
            "policy_status": _safe_str(policy.get("status"), "success"),
            "policy_reason_code": _safe_str(policy.get("reason_code")),
            "policy_message": _safe_str(policy.get("message"), "ok"),
            "actor_type": _safe_str(actor.get("actor_type"), "supervisor"),
            "actor_id": _safe_str(actor.get("actor_id"), "supervisor"),
            "skill_id": _safe_str(actor.get("skill_id")),
            "delegated_from": _safe_str(actor.get("delegated_from")),
            "focus_root": effective_focus_root,
            "relative_path": relative_path,
            "bytes_written": 0,
            "bytes_appended": 0,
            "tool_calls": [],
            "tool_results": [policy_tool_result],
            "boundary": write_boundary,
            "recorded_at": utc_iso(),
        }

    existing_text = ""
    read_boundary = resolve_room_supervisor_fs_boundary(
        room_id=room_id,
        request_args=request_args,
        target_paths=[relative_path],
        mode="read",
        require_focus_root=True,
    )
    if read_boundary.get("allowed"):
        read_packet = _call_guarded_tool(
            fn=nisb_file_read,
            request_args=request_args,
            boundary=read_boundary,
            operation="room_supervisor_notebook_read_existing",
            payload={
                "filename": relative_path,
                "path": relative_path,
                "relative_path": relative_path,
                "focus_root": effective_focus_root,
            },
            run_id=run_id,
            supervisor_event_id=supervisor_event_id,
            final_event_id=final_event_id,
        )
        if _result_success(read_packet):
            existing_text = _extract_text_payload(read_packet)

    block = _normalize_supervisor_notebook_markdown_content(content)
    merged_content = existing_text.rstrip() + "\n\n" + block if existing_text.strip() and block else (existing_text or block)
    bytes_written = len(merged_content.encode("utf-8"))
    bytes_appended = len(block.encode("utf-8"))

    update_packet = _call_guarded_tool(
        fn=nisb_file_update,
        request_args=request_args,
        boundary=write_boundary,
        operation="room_supervisor_notebook_write",
        payload={
            "filename": relative_path,
            "path": relative_path,
            "relative_path": relative_path,
            "focus_root": _safe_str(write_boundary.get("resolved_focus_root")),
            "content": merged_content,
        },
        run_id=run_id,
        supervisor_event_id=supervisor_event_id,
        final_event_id=final_event_id,
    )

    source_tool_name = "nisb_file_update"
    raw = update_packet
    if not _result_success(update_packet):
        create_packet = _call_guarded_tool(
            fn=nisb_file_create,
            request_args=request_args,
            boundary=write_boundary,
            operation="room_supervisor_notebook_write",
            payload={
                "filename": relative_path,
                "path": relative_path,
                "relative_path": relative_path,
                "focus_root": _safe_str(write_boundary.get("resolved_focus_root")),
                "content": merged_content,
            },
            run_id=run_id,
            supervisor_event_id=supervisor_event_id,
            final_event_id=final_event_id,
        )
        if _result_success(create_packet):
            source_tool_name = "nisb_file_create"
            raw = create_packet

    status = "success" if _result_success(raw) else _normalize_status(raw.get("status")) or "error"
    message = _extract_message(raw, "notebook write completed")

    tool_calls = [
        _tool_call_item(
            "nisb_supervisor_notebook_write",
            source_tool_name=source_tool_name,
            args={
                "relative_path": relative_path,
                "focus_root": effective_focus_root,
                "write_focus_root": _safe_str(write_boundary.get("resolved_focus_root")),
                "notebook_root": notebook_root,
                "notebook_title": _safe_str(mcp.get("notebook_title"), "Supervisor notebook"),
                "notebook_section_title": _safe_str(mcp.get("notebook_section_title"), "latest"),
                "mode": "room_supervisor_controlled_notebook_write",
            },
        )
    ]
    tool_results = [
        policy_tool_result,
        _tool_result_item(
            "room_supervisor_notebook_write",
            tool_name="nisb_supervisor_notebook_write",
            source_tool_name=source_tool_name,
            status=status,
            relative_path=relative_path,
            focus_root=effective_focus_root,
            write_focus_root=_safe_str(write_boundary.get("resolved_focus_root")),
            bytes_written=bytes_written,
            bytes_appended=bytes_appended,
            appended=bool(existing_text.strip()),
            policy_allowed=True,
            policy_status=_safe_str(policy.get("status"), "success"),
            actor_type=_safe_str(actor.get("actor_type"), "supervisor"),
            actor_id=_safe_str(actor.get("actor_id"), "supervisor"),
            skill_id=_safe_str(actor.get("skill_id")),
            delegated_from=_safe_str(actor.get("delegated_from")),
            message=message,
        )
    ]

    _append_room_fs_audit(
        request_args=request_args,
        event={
            "event": "room_supervisor_notebook_write",
            "operation": "room_supervisor_notebook_write",
            "request_id": _safe_str(request_args.get("request_id")),
            "room_id": _safe_str(room_id),
            "run_id": _safe_str(run_id),
            "supervisor_event_id": _safe_str(supervisor_event_id),
            "final_event_id": _safe_str(final_event_id),
            "paths": [relative_path],
            "metadata": {
                "status": status,
                "focus_root": effective_focus_root,
                "write_focus_root": _safe_str(write_boundary.get("resolved_focus_root")),
                "bytes_written": bytes_written,
                "bytes_appended": bytes_appended,
                "appended": bool(existing_text.strip()),
                "source_tool_name": source_tool_name,
                "policy_allowed": True,
                "policy_status": _safe_str(policy.get("status"), "success"),
                "actor_type": _safe_str(actor.get("actor_type"), "supervisor"),
                "actor_id": _safe_str(actor.get("actor_id"), "supervisor"),
                "skill_id": _safe_str(actor.get("skill_id")),
                "delegated_from": _safe_str(actor.get("delegated_from")),
            },
        },
    )

    return {
        "enabled": True,
        "status": status,
        "message": message,
        "reason_code": "",
        "policy_allowed": True,
        "policy_status": _safe_str(policy.get("status"), "success"),
        "policy_reason_code": _safe_str(policy.get("reason_code")),
        "policy_message": _safe_str(policy.get("message"), "ok"),
        "actor_type": _safe_str(actor.get("actor_type"), "supervisor"),
        "actor_id": _safe_str(actor.get("actor_id"), "supervisor"),
        "skill_id": _safe_str(actor.get("skill_id")),
        "delegated_from": _safe_str(actor.get("delegated_from")),
        "focus_root": effective_focus_root,
        "relative_path": relative_path,
        "bytes_written": bytes_written,
        "bytes_appended": bytes_appended,
        "tool_calls": tool_calls,
        "tool_results": tool_results,
        "boundary": write_boundary,
        "raw_result": raw,
        "recorded_at": utc_iso(),
    }


def room_supervisor_fs_audit_payload(result: Dict[str, Any]) -> Dict[str, Any]:
    row = _safe_dict(result)
    return {
        "enabled": bool(row.get("enabled")),
        "status": _safe_str(row.get("status")),
        "message": _safe_str(row.get("message")),
        "reason_code": _safe_str(row.get("reason_code")),
        "focus_root": _safe_str(row.get("focus_root") or _safe_dict(row.get("boundary")).get("effective_focus_root")),
        "scope": _safe_str(row.get("scope")),
        "relative_path": _safe_str(row.get("relative_path")),
        "target_paths": _safe_list(row.get("target_paths")),
        "entries_count": int(row.get("entries_count") or 0),
        "entries": _safe_list(row.get("entries")),
        "previews": _safe_list(row.get("previews")),
        "bytes_written": int(row.get("bytes_written") or 0),
        "bytes_appended": int(row.get("bytes_appended") or 0),
        "actor_type": _safe_str(row.get("actor_type")),
        "actor_id": _safe_str(row.get("actor_id")),
        "skill_id": _safe_str(row.get("skill_id")),
        "delegated_from": _safe_str(row.get("delegated_from")),
        "policy_allowed": as_bool(row.get("policy_allowed"), False),
        "policy_status": _safe_str(row.get("policy_status")),
        "policy_reason_code": _safe_str(row.get("policy_reason_code")),
        "policy_message": _safe_str(row.get("policy_message")),
        "tool_calls": _safe_list(row.get("tool_calls")),
        "tool_results": _safe_list(row.get("tool_results")),
        "recorded_at": _safe_str(row.get("recorded_at")),
    }


__all__ = [
    "room_supervisor_fs_audit_payload",
    "room_supervisor_fs_probe",
    "room_supervisor_fs_read",
    "room_supervisor_notebook_write",
]

