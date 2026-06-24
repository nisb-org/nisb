from __future__ import annotations

from typing import Any, Dict, List, Optional

from .room_contracts import (
    as_bool,
    ensure_request_id,
    normalize_focus_root,
    require_safe_id,
    utc_iso,
)
from .room_store import (
    append_room_event,
    ensure_room_exists,
    get_basepath,
    is_participant,
    load_state_doc,
    save_state_doc,
    touch_room_updated_at,
    uid_from_ctx_or_basepath,
)


_ALLOWED_BOUNDARY_MODES = {"read", "write", "dangerous"}


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


def _parent_dir_of(path: str) -> str:
    normalized = _normalize_logical_path(path)
    if not normalized or "/" not in normalized:
        return ""
    return normalized.rsplit("/", 1)[0].strip("/")


def _path_within(root: str, target: str) -> bool:
    normalized_root = _normalize_logical_path(root)
    normalized_target = _normalize_logical_path(target)
    if not normalized_root or not normalized_target:
        return False
    return normalized_target == normalized_root or normalized_target.startswith(normalized_root + "/")


def _logical_common_ancestor(paths: List[str]) -> str:
    normalized = [p.split("/") for p in _unique_paths(paths) if _normalize_logical_path(p)]
    if not normalized:
        return ""

    prefix = normalized[0]
    for parts in normalized[1:]:
        max_len = min(len(prefix), len(parts))
        idx = 0
        while idx < max_len and prefix[idx] == parts[idx]:
            idx += 1
        prefix = prefix[:idx]
        if not prefix:
            return ""

    return "/".join(prefix).strip("/")


def _normalize_fs_read_scope(value: Any, fallback: str = "minimal") -> str:
    scope = _safe_str(value).lower()
    if scope in {"minimal", "user_ro"}:
        return scope
    return fallback if fallback in {"minimal", "user_ro"} else "minimal"


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


def _normalize_room_mcp_overrides(value: Any) -> Dict[str, Any]:
    src = _safe_dict(value)
    notebook_dir = _normalize_logical_path(
        src.get("notebook_dir")
        or src.get("notebookDir")
        or src.get("notebookdir")
    ) or "_room_supervisor_notebooks"
    return {
        "fs_read_enabled": as_bool(
            src.get("fs_read_enabled")
            if "fs_read_enabled" in src
            else src.get("fsReadEnabled", src.get("fsreadenabled")),
            False,
        ),
        "fs_read_scope": _normalize_fs_read_scope(
            src.get("fs_read_scope")
            if "fs_read_scope" in src
            else src.get("fsReadScope", src.get("fsreadscope")),
            "minimal",
        ),
        "notebook_write_enabled": as_bool(
            src.get("notebook_write_enabled")
            if "notebook_write_enabled" in src
            else src.get("notebookWriteEnabled", src.get("notebookwriteenabled")),
            False,
        ),
        "fs_dangerous_enabled": as_bool(
            src.get("fs_dangerous_enabled")
            if "fs_dangerous_enabled" in src
            else src.get("fsDangerousEnabled", src.get("fsdangerousenabled")),
            False,
        ),
        "notebook_dir": notebook_dir,
        "notebook_filename": _normalize_filename(
            src.get("notebook_filename")
            if "notebook_filename" in src
            else src.get("notebookFilename", src.get("notebookfilename")),
            "supervisor.md",
        ),
        "notebook_title": _safe_str(
            src.get("notebook_title")
            if "notebook_title" in src
            else src.get("notebookTitle", src.get("notebooktitle")),
            "Supervisor notebook",
        ),
        "notebook_section_title": _safe_str(
            src.get("notebook_section_title")
            if "notebook_section_title" in src
            else src.get("notebookSectionTitle", src.get("notebooksectiontitle")),
            "latest",
        ),
    }


def _normalize_boundary_mode(value: Any) -> str:
    mode = _safe_str(value).lower()
    return mode if mode in _ALLOWED_BOUNDARY_MODES else "read"


def _first_non_empty_text(*values: Any) -> str:
    for value in values:
        text = _safe_str(value)
        if text:
            return text
    return ""


def _first_non_empty_path(*values: Any) -> str:
    for value in values:
        path = _normalize_logical_path(value)
        if path:
            return path
    return ""


def _first_present_bool(src: Dict[str, Any], keys: List[str], default: bool) -> bool:
    for key in keys:
        if key in src:
            return as_bool(src.get(key), default)
    return default


def _workspace_context_from_state(state: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "workspace_id": _first_non_empty_text(
            state.get("workspace_id"),
            state.get("workspaceId"),
            state.get("workspaceid"),
        ),
        "workspace_name": _first_non_empty_text(
            state.get("workspace_name"),
            state.get("workspaceName"),
            state.get("workspacename"),
        ),
        "focus_root": _first_non_empty_path(
            state.get("focus_root"),
            state.get("focusRoot"),
            state.get("focusroot"),
        ),
        "focus_label": _first_non_empty_text(
            state.get("focus_label"),
            state.get("focusLabel"),
            state.get("focuslabel"),
        ),
        "workspace_context_updated_at": _first_non_empty_text(
            state.get("workspace_context_updated_at"),
            state.get("workspaceContextUpdatedAt"),
            state.get("workspacecontextupdatedat"),
        ),
    }


def _extract_context_focus_root(obj: Any) -> str:
    ctx = _safe_dict(obj)
    return _first_non_empty_path(
        ctx.get("focus_root"),
        ctx.get("focusRoot"),
        ctx.get("focusroot"),
        ctx.get("effective_focus_root"),
        ctx.get("effectiveFocusRoot"),
        ctx.get("resolved_focus_root"),
        ctx.get("resolvedFocusRoot"),
        ctx.get("write_focus_root"),
        ctx.get("writeFocusRoot"),
    )


def _extract_context_workspace_id(obj: Any) -> str:
    ctx = _safe_dict(obj)
    return _first_non_empty_text(
        ctx.get("workspace_id"),
        ctx.get("workspaceId"),
        ctx.get("workspaceid"),
    )


def _extract_context_workspace_name(obj: Any) -> str:
    ctx = _safe_dict(obj)
    return _first_non_empty_text(
        ctx.get("workspace_name"),
        ctx.get("workspaceName"),
        ctx.get("workspacename"),
    )


def _extract_context_focus_label(obj: Any) -> str:
    ctx = _safe_dict(obj)
    return _first_non_empty_text(
        ctx.get("focus_label"),
        ctx.get("focusLabel"),
        ctx.get("focuslabel"),
    )


def _extract_requested_focus_root(request_args: Dict[str, Any]) -> str:
    args = _safe_dict(request_args)
    capability_gate = _safe_dict(args.get("capability_gate"))
    room_workspace_context = _safe_dict(args.get("room_workspace_context") or args.get("roomWorkspaceContext"))
    room_supervisor_context = _safe_dict(args.get("room_supervisor_context") or args.get("roomSupervisorContext"))
    workspace_context = _safe_dict(args.get("workspace_context") or args.get("workspaceContext"))

    return _first_non_empty_path(
        capability_gate.get("focus_root"),
        capability_gate.get("focusRoot"),
        args.get("focus_root"),
        args.get("focusRoot"),
        args.get("focusroot"),
        args.get("effective_focus_root"),
        args.get("effectiveFocusRoot"),
        args.get("resolved_focus_root"),
        args.get("resolvedFocusRoot"),
        args.get("write_focus_root"),
        args.get("writeFocusRoot"),
        _extract_context_focus_root(room_workspace_context),
        _extract_context_focus_root(room_supervisor_context),
        _extract_context_focus_root(workspace_context),
    )


def _extract_requested_workspace_id(request_args: Dict[str, Any]) -> str:
    args = _safe_dict(request_args)
    capability_gate = _safe_dict(args.get("capability_gate"))
    room_workspace_context = _safe_dict(args.get("room_workspace_context") or args.get("roomWorkspaceContext"))
    room_supervisor_context = _safe_dict(args.get("room_supervisor_context") or args.get("roomSupervisorContext"))
    workspace_context = _safe_dict(args.get("workspace_context") or args.get("workspaceContext"))

    return _first_non_empty_text(
        capability_gate.get("workspace_id"),
        capability_gate.get("workspaceId"),
        args.get("workspace_id"),
        args.get("workspaceId"),
        args.get("workspaceid"),
        _extract_context_workspace_id(room_workspace_context),
        _extract_context_workspace_id(room_supervisor_context),
        _extract_context_workspace_id(workspace_context),
    )


def _extract_requested_workspace_name(request_args: Dict[str, Any]) -> str:
    args = _safe_dict(request_args)
    capability_gate = _safe_dict(args.get("capability_gate"))
    room_workspace_context = _safe_dict(args.get("room_workspace_context") or args.get("roomWorkspaceContext"))
    room_supervisor_context = _safe_dict(args.get("room_supervisor_context") or args.get("roomSupervisorContext"))
    workspace_context = _safe_dict(args.get("workspace_context") or args.get("workspaceContext"))

    return _first_non_empty_text(
        capability_gate.get("workspace_name"),
        capability_gate.get("workspaceName"),
        args.get("workspace_name"),
        args.get("workspaceName"),
        args.get("workspacename"),
        _extract_context_workspace_name(room_workspace_context),
        _extract_context_workspace_name(room_supervisor_context),
        _extract_context_workspace_name(workspace_context),
    )


def _extract_requested_focus_label(request_args: Dict[str, Any]) -> str:
    args = _safe_dict(request_args)
    room_workspace_context = _safe_dict(args.get("room_workspace_context") or args.get("roomWorkspaceContext"))
    room_supervisor_context = _safe_dict(args.get("room_supervisor_context") or args.get("roomSupervisorContext"))
    workspace_context = _safe_dict(args.get("workspace_context") or args.get("workspaceContext"))

    return _first_non_empty_text(
        args.get("focus_label"),
        args.get("focusLabel"),
        args.get("focuslabel"),
        _extract_context_focus_label(room_workspace_context),
        _extract_context_focus_label(room_supervisor_context),
        _extract_context_focus_label(workspace_context),
    )


def _resolve_effective_room_focus_root(
    *,
    state: Dict[str, Any],
    request_args: Dict[str, Any],
) -> Dict[str, Any]:
    state_focus_root = normalize_focus_root(
        _first_non_empty_path(
            state.get("focus_root"),
            state.get("focusRoot"),
            state.get("focusroot"),
        )
    )
    requested_focus_root = _extract_requested_focus_root(request_args)
    inherit_focus_root = _first_present_bool(
        _safe_dict(state),
        ["inherit_focus_root", "inheritFocusRoot", "inheritfocusroot"],
        bool(state_focus_root),
    )

    effective_focus_root = _normalize_logical_path(state_focus_root) if inherit_focus_root else ""

    if requested_focus_root:
        if effective_focus_root and not _path_within(effective_focus_root, requested_focus_root):
            return {
                "allowed": False,
                "reason_code": "REQUESTED_FOCUS_ROOT_OUTSIDE_ROOM_BOUNDARY",
                "message": "requested focus_root widened room boundary",
                "effective_focus_root": effective_focus_root,
                "requested_focus_root": requested_focus_root,
            }
        effective_focus_root = requested_focus_root

    return {
        "allowed": True,
        "reason_code": "",
        "message": "",
        "effective_focus_root": effective_focus_root,
        "requested_focus_root": requested_focus_root,
    }


def _deny_boundary(
    *,
    mode: str,
    basepath: str,
    workspace_id: str,
    workspace_name: str,
    focus_label: str,
    room_focus_root: str,
    effective_focus_root: str,
    requested_focus_root: str,
    derived_target_focus_root: str,
    target_paths: List[str],
    target_parents: List[str],
    mcp_overrides: Dict[str, Any],
    reason_code: str,
    message: str,
) -> Dict[str, Any]:
    notebook_root = (
        _normalize_logical_path("/".join([effective_focus_root, _safe_str(mcp_overrides.get("notebook_dir"))]).strip("/"))
        if effective_focus_root
        else ""
    )
    return {
        "allowed": False,
        "status": "denied",
        "reason_code": _safe_str(reason_code),
        "message": _safe_str(message) or "boundary denied",
        "mode": mode,
        "basepath": basepath,
        "workspace_id": workspace_id,
        "workspace_name": workspace_name,
        "focus_label": focus_label,
        "room_focus_root": room_focus_root,
        "effective_focus_root": effective_focus_root,
        "requested_focus_root": requested_focus_root,
        "resolved_focus_root": "",
        "derived_target_focus_root": derived_target_focus_root,
        "target_paths": target_paths,
        "target_parents": target_parents,
        "allowed_read_roots": [],
        "allowed_write_roots": [],
        "dangerous_enabled": as_bool(mcp_overrides.get("fs_dangerous_enabled"), False),
        "mcp_overrides": mcp_overrides,
        "notebook_root": notebook_root,
    }


def _build_room_effective_fs_boundary(
    *,
    state: Dict[str, Any],
    request_args: Dict[str, Any],
    target_paths: Optional[List[str]] = None,
    mode: str = "read",
    require_focus_root: bool = True,
) -> Dict[str, Any]:
    mode = _normalize_boundary_mode(mode)
    args = _safe_dict(request_args)
    basepath = _safe_str(get_basepath(args))
    workspace_id = _first_non_empty_text(
        state.get("workspace_id"),
        state.get("workspaceId"),
        state.get("workspaceid"),
        _extract_requested_workspace_id(args),
    )
    workspace_name = _first_non_empty_text(
        state.get("workspace_name"),
        state.get("workspaceName"),
        state.get("workspacename"),
        _extract_requested_workspace_name(args),
    )
    focus_label = _first_non_empty_text(
        state.get("focus_label"),
        state.get("focusLabel"),
        state.get("focuslabel"),
        _extract_requested_focus_label(args),
    )
    room_focus_root = _first_non_empty_path(
        state.get("focus_root"),
        state.get("focusRoot"),
        state.get("focusroot"),
    )
    mcp_overrides = _normalize_room_mcp_overrides(
        state.get("mcp_overrides")
        if "mcp_overrides" in state
        else state.get("mcpOverrides", state.get("mcpoverrides"))
    )

    focus_resolution = _resolve_effective_room_focus_root(state=state, request_args=args)
    effective_focus_root = _normalize_logical_path(focus_resolution.get("effective_focus_root"))
    requested_focus_root = _normalize_logical_path(focus_resolution.get("requested_focus_root"))

    normalized_targets = _unique_paths(_safe_list(target_paths))
    target_parents = _unique_paths([_parent_dir_of(path) for path in normalized_targets if _parent_dir_of(path)])
    derived_target_focus_root = _logical_common_ancestor(target_parents)

    if not focus_resolution.get("allowed"):
        return _deny_boundary(
            mode=mode,
            basepath=basepath,
            workspace_id=workspace_id,
            workspace_name=workspace_name,
            focus_label=focus_label,
            room_focus_root=room_focus_root,
            effective_focus_root=effective_focus_root,
            requested_focus_root=requested_focus_root,
            derived_target_focus_root=derived_target_focus_root,
            target_paths=normalized_targets,
            target_parents=target_parents,
            mcp_overrides=mcp_overrides,
            reason_code=_safe_str(focus_resolution.get("reason_code")),
            message=_safe_str(focus_resolution.get("message")),
        )

    if mode == "dangerous" and not as_bool(mcp_overrides.get("fs_dangerous_enabled"), False):
        return _deny_boundary(
            mode=mode,
            basepath=basepath,
            workspace_id=workspace_id,
            workspace_name=workspace_name,
            focus_label=focus_label,
            room_focus_root=room_focus_root,
            effective_focus_root=effective_focus_root,
            requested_focus_root=requested_focus_root,
            derived_target_focus_root=derived_target_focus_root,
            target_paths=normalized_targets,
            target_parents=target_parents,
            mcp_overrides=mcp_overrides,
            reason_code="FS_DANGEROUS_DISABLED",
            message="dangerous filesystem operations are disabled",
        )

    if require_focus_root and not effective_focus_root:
        return _deny_boundary(
            mode=mode,
            basepath=basepath,
            workspace_id=workspace_id,
            workspace_name=workspace_name,
            focus_label=focus_label,
            room_focus_root=room_focus_root,
            effective_focus_root=effective_focus_root,
            requested_focus_root=requested_focus_root,
            derived_target_focus_root=derived_target_focus_root,
            target_paths=normalized_targets,
            target_parents=target_parents,
            mcp_overrides=mcp_overrides,
            reason_code="MISSING_FOCUS_ROOT",
            message="room focus_root is required",
        )

    resolved_focus_root = effective_focus_root

    if derived_target_focus_root:
        if not _path_within(effective_focus_root, derived_target_focus_root):
            return _deny_boundary(
                mode=mode,
                basepath=basepath,
                workspace_id=workspace_id,
                workspace_name=workspace_name,
                focus_label=focus_label,
                room_focus_root=room_focus_root,
                effective_focus_root=effective_focus_root,
                requested_focus_root=requested_focus_root,
                derived_target_focus_root=derived_target_focus_root,
                target_paths=normalized_targets,
                target_parents=target_parents,
                mcp_overrides=mcp_overrides,
                reason_code="FOCUS_ROOT_MISMATCH",
                message="target paths are outside room focus_root",
            )
        resolved_focus_root = derived_target_focus_root

    resolved_focus_root = _normalize_logical_path(resolved_focus_root)
    notebook_root = _normalize_logical_path(
        "/".join([effective_focus_root, _safe_str(mcp_overrides.get("notebook_dir"))]).strip("/")
    )

    allowed_read_roots = [resolved_focus_root] if resolved_focus_root else []
    allowed_write_roots = [resolved_focus_root] if mode in {"write", "dangerous"} and resolved_focus_root else []

    return {
        "allowed": True,
        "status": "success",
        "reason_code": "",
        "message": "ok",
        "mode": mode,
        "basepath": basepath,
        "workspace_id": workspace_id,
        "workspace_name": workspace_name,
        "focus_label": focus_label,
        "room_focus_root": room_focus_root,
        "effective_focus_root": effective_focus_root,
        "requested_focus_root": requested_focus_root,
        "resolved_focus_root": resolved_focus_root,
        "derived_target_focus_root": derived_target_focus_root,
        "target_paths": normalized_targets,
        "target_parents": target_parents,
        "allowed_read_roots": allowed_read_roots,
        "allowed_write_roots": allowed_write_roots,
        "dangerous_enabled": as_bool(mcp_overrides.get("fs_dangerous_enabled"), False),
        "mcp_overrides": mcp_overrides,
        "notebook_root": notebook_root,
    }


def resolve_room_supervisor_fs_boundary(
    *,
    room_id: str,
    request_args: Dict[str, Any],
    target_paths: Optional[List[str]] = None,
    mode: str = "read",
    require_focus_root: bool = True,
) -> Dict[str, Any]:
    state = _safe_dict(load_state_doc(room_id))
    boundary = _build_room_effective_fs_boundary(
        state=state,
        request_args=request_args,
        target_paths=target_paths,
        mode=mode,
        require_focus_root=require_focus_root,
    )
    boundary["room_id"] = _safe_str(room_id)
    boundary["request_id"] = _safe_str(_safe_dict(request_args).get("request_id"))
    return boundary


def nisb_room_workspace_get(args: Dict[str, Any]) -> Dict[str, Any]:
    basepath = get_basepath(args)
    uid = uid_from_ctx_or_basepath(basepath, args)
    rid = ensure_request_id(args)

    room_id = require_safe_id("room_id", args.get("room_id"))
    meta = ensure_room_exists(room_id)
    if meta and not is_participant(uid, meta):
        return {"success": False, "message": "permission denied", "request_id": rid}

    state = load_state_doc(room_id)
    return {
        "success": True,
        "room_id": room_id,
        "workspace_context": _workspace_context_from_state(state),
        "request_id": rid,
    }


def nisb_room_workspace_set(args: Dict[str, Any]) -> Dict[str, Any]:
    basepath = get_basepath(args)
    uid = uid_from_ctx_or_basepath(basepath, args)
    rid = ensure_request_id(args)

    room_id = require_safe_id("room_id", args.get("room_id"))
    meta = ensure_room_exists(room_id)
    if meta and not is_participant(uid, meta):
        return {"success": False, "message": "permission denied", "request_id": rid}

    workspace_id_raw = _safe_str(args.get("workspace_id"))
    workspace_id = require_safe_id("workspace_id", workspace_id_raw) if workspace_id_raw else ""
    workspace_name = _safe_str(args.get("workspace_name"))
    focus_root = normalize_focus_root(args.get("focus_root"))
    focus_label = _safe_str(args.get("focus_label"))

    state = load_state_doc(room_id)
    state["workspace_id"] = workspace_id
    state["workspace_name"] = workspace_name
    state["focus_root"] = focus_root
    state["focus_label"] = focus_label
    state["workspace_context_updated_at"] = utc_iso()

    save_state_doc(room_id, state)
    touch_room_updated_at(room_id)

    evt = {
        "id": f"evt_room_workspace_set_{rid}",
        "ts": utc_iso(),
        "type": "room.workspace_context_set",
        "room_id": room_id,
        "request_id": rid,
        "payload": {
            "sender": uid,
            "workspace_id": workspace_id,
            "workspace_name": workspace_name,
            "focus_root": focus_root,
            "focus_label": focus_label,
        },
    }
    append_room_event(room_id, evt)

    return {
        "success": True,
        "room_id": room_id,
        "workspace_context": _workspace_context_from_state(state),
        "request_id": rid,
    }


def nisb_room_workspace_clear(args: Dict[str, Any]) -> Dict[str, Any]:
    basepath = get_basepath(args)
    uid = uid_from_ctx_or_basepath(basepath, args)
    rid = ensure_request_id(args)

    room_id = require_safe_id("room_id", args.get("room_id"))
    meta = ensure_room_exists(room_id)
    if meta and not is_participant(uid, meta):
        return {"success": False, "message": "permission denied", "request_id": rid}

    clear_workspace = as_bool(args.get("clear_workspace"), False)
    clear_focus_root = as_bool(args.get("clear_focus_root"), clear_workspace or True)

    state = load_state_doc(room_id)

    if clear_workspace:
        state["workspace_id"] = ""
        state["workspace_name"] = ""

    if clear_focus_root:
        state["focus_root"] = ""
        state["focus_label"] = ""

    state["workspace_context_updated_at"] = utc_iso()

    save_state_doc(room_id, state)
    touch_room_updated_at(room_id)

    evt = {
        "id": f"evt_room_workspace_clear_{rid}",
        "ts": utc_iso(),
        "type": "room.workspace_context_clear",
        "room_id": room_id,
        "request_id": rid,
        "payload": {
            "sender": uid,
            "clear_workspace": clear_workspace,
            "clear_focus_root": clear_focus_root,
        },
    }
    append_room_event(room_id, evt)

    return {
        "success": True,
        "room_id": room_id,
        "workspace_context": _workspace_context_from_state(state),
        "request_id": rid,
    }


__all__ = [
    "_build_room_effective_fs_boundary",
    "resolve_room_supervisor_fs_boundary",
    "nisb_room_workspace_get",
    "nisb_room_workspace_set",
    "nisb_room_workspace_clear",
]
