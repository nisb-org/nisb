#!/usr/bin/env python3
"""
Chat Tools Runtime

Responsibilities:
- Define tools available to chat conversations, such as execute_code,
  read_file, list_files, serper_search, and controlled filesystem tools.
- Execute backend tool logic and return LLM-readable text results.

Production-ready additions:
- Enhanced filesystem read capabilities: tree_files, search_files,
  read_file_range.
- Write capabilities, disabled by default: update_file, delete_file,
  move_path, rename_file, delete_dir.
- Layered permission gates:
  - fs_read_scope: user_ro by default, or minimal for agent_files only.
  - fs_write_scope: none by default, or agent_files for agent_files only.
  - fs_dangerous_enabled: false by default. When true, recursive directory
    deletion is allowed, still limited by fs_write_scope.
"""

from __future__ import annotations

import json
import sys
from typing import List, Dict, Any, Tuple
from urllib.parse import urlparse, parse_qs, unquote

from integrations.serper_client import serper_search


# -----------------------------
# Basic compatibility helpers
# -----------------------------

def _coerce_bool_local(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    s = str(value or "").strip().lower()
    return s in ("1", "true", "yes", "on", "y")


def _normalize_mcp_overrides(mcp_overrides: Dict[str, Any] | None) -> Dict[str, Any]:
    raw = mcp_overrides or {}
    if not isinstance(raw, dict):
        raw = {}

    out = dict(raw)

    if "serper_enabled" not in out and "serperEnabled" in out:
        out["serper_enabled"] = out.get("serperEnabled")

    if "code_network_enabled" not in out and "codeNetworkEnabled" in out:
        out["code_network_enabled"] = out.get("codeNetworkEnabled")

    if "fs_read_scope" not in out and "fsReadScope" in out:
        out["fs_read_scope"] = out.get("fsReadScope")

    if "fs_write_scope" not in out and "fsWriteScope" in out:
        out["fs_write_scope"] = out.get("fsWriteScope")

    if "fs_dangerous_enabled" not in out and "fsDangerousEnabled" in out:
        out["fs_dangerous_enabled"] = out.get("fsDangerousEnabled")

    return out


# -----------------------------
# Policy gate
# -----------------------------

def _norm_rel(p: str) -> str:
    p = (p or "").strip()
    p = p.lstrip("/")
    p = p.replace("\\", "/")
    while "//" in p:
        p = p.replace("//", "/")
    return p


def _is_under(rel_path: str, root: str) -> bool:
    rel_path = _norm_rel(rel_path)
    root = _norm_rel(root).rstrip("/")
    return rel_path == root or rel_path.startswith(root + "/")


def _policy_from_overrides(mcp_overrides: Dict[str, Any] | None) -> Dict[str, Any]:
    mcp_overrides = _normalize_mcp_overrides(mcp_overrides)
    return {
        "read_scope": str(mcp_overrides.get("fs_read_scope", "user_ro")).strip() or "user_ro",
        "write_scope": str(mcp_overrides.get("fs_write_scope", "none")).strip() or "none",
        "dangerous_enabled": _coerce_bool_local(mcp_overrides.get("fs_dangerous_enabled", False)),
    }


def _check_read_allowed(path: str, policy: Dict[str, Any]) -> Tuple[bool, str]:
    rel = _norm_rel(path)

    if policy["read_scope"] == "minimal":
        if rel == "":
            return True, ""
        if not _is_under(rel, "agent_files"):
            return False, "READ_DENIED: The current read scope is minimal. Only agent_files/ can be read."

    return True, ""


def _check_write_allowed(path: str, policy: Dict[str, Any]) -> Tuple[bool, str]:
    rel = _norm_rel(path)
    if policy["write_scope"] == "none":
        return False, "WRITE_DENIED: Filesystem write access is disabled. fs_write_scope=none."
    if policy["write_scope"] == "agent_files":
        if not _is_under(rel, "agent_files"):
            return False, "WRITE_DENIED: Write access is limited to agent_files/."
    return True, ""


def _ctx_fs_args(user_ctx) -> Dict[str, Any]:
    return {
        "user_id": getattr(user_ctx, "user_id", None),
        "_librechat_email": getattr(user_ctx, "email", None),
        "_librechat_name": getattr(user_ctx, "name", None),
        "email": getattr(user_ctx, "email", None),
        "name": getattr(user_ctx, "name", None),
    }


def _resolve_nisb_uri(s: str) -> str:
    s = (s or "").strip()
    if not s:
        return ""
    if s.startswith("nisb://"):
        u = urlparse(s)
        qs = parse_qs(u.query or "")
        path = ""
        if qs.get("path"):
            path = qs["path"][0]
        elif qs.get("filename"):
            path = qs["filename"][0]
        return _norm_rel(unquote(path))
    return _norm_rel(s)


def _strip_agent_files_prefix(p: str) -> str:
    p = _norm_rel(p)
    if p == "agent_files":
        return ""
    if p.startswith("agent_files/"):
        return p[len("agent_files/"):]
    return p


# -----------------------------
# Tool schema
# -----------------------------

def build_tools_for_model(model: str, serper_enabled: bool, mcp_overrides: Dict[str, Any] | None = None) -> List[dict] | None:
    if model.startswith("deepseek") or model.startswith("o1"):
        print(f"[DEBUG chat-tools] Tool calls are not supported by model: {model}", file=sys.stderr)
        return None

    mcp_overrides = _normalize_mcp_overrides(mcp_overrides)
    policy = _policy_from_overrides(mcp_overrides)

    final_serper_enabled = bool(serper_enabled) or _coerce_bool_local(mcp_overrides.get("serper_enabled", False))
    code_network_enabled = _coerce_bool_local(mcp_overrides.get("code_network_enabled", False))

    tools: List[dict] = []

    # Controlled minimum capability surface:
    # 1. Normal chat does not expose execute_code by default.
    # 2. Normal chat does not expose filesystem read/write tools by default.
    # 3. serper_search is exposed only when serper_enabled=true.
    #
    # This avoids the degraded behavior where enabling a simple web search
    # accidentally exposes a full heavy-tool surface to the model.
    if final_serper_enabled:
        tools.append(
            {
                "type": "function",
                "function": {
                    "name": "serper_search",
                    "description": "Use Serper for web search and return relevant web results with real URLs.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string", "description": "Search query."},
                            "num": {"type": "integer", "default": 5},
                            "num_results": {"type": "integer", "default": 5},
                            "search_type": {"type": "string", "default": "search"},
                        },
                        "required": ["query"],
                    },
                },
            }
        )

    # execute_code is exposed only when code network mode is explicitly enabled.
    # For the current release, execute_code is not part of the default normal-chat
    # capability surface.
    if code_network_enabled:
        tools.append(
            {
                "type": "function",
                "function": {
                    "name": "execute_code",
                    "description": (
                        "Execute Python code for data analysis, math, plotting, and similar tasks. "
                        "If plt.savefig() is used, the image must be saved under /tmp/, "
                        "for example plt.savefig('/tmp/chart.png')."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "code": {
                                "type": "string",
                                "description": "Python code to execute. If plt.savefig() is used, save to /tmp/file.png.",
                            },
                            "timeout": {"type": "integer", "default": 30},
                            "network": {
                                "type": "boolean",
                                "description": "Whether network access is allowed. Default is false and controlled by the current MCP code-network toggle.",
                                "default": False,
                            },
                        },
                        "required": ["code"],
                    },
                },
            }
        )

    # Write tools keep the existing permission policy and are exposed only when
    # write access is explicitly enabled.
    if policy["write_scope"] != "none":
        tools.extend(
            [
                {
                    "type": "function",
                    "function": {
                        "name": "update_file",
                        "description": "Update a text file. By default, writing is limited to agent_files/. Backup and audit logging are handled by the filesystem layer.",
                        "parameters": {
                            "type": "object",
                            "properties": {"filename": {"type": "string"}, "content": {"type": "string"}},
                            "required": ["filename", "content"],
                        },
                    },
                },
                {
                    "type": "function",
                    "function": {
                        "name": "delete_file",
                        "description": "Delete a file. By default, deletion is limited to agent_files/.",
                        "parameters": {"type": "object", "properties": {"filename": {"type": "string"}}, "required": ["filename"]},
                    },
                },
                {
                    "type": "function",
                    "function": {
                        "name": "move_path",
                        "description": "Move a file or directory by path. By default, moving is limited to agent_files/.",
                        "parameters": {
                            "type": "object",
                            "properties": {"old_path": {"type": "string"}, "new_path": {"type": "string"}},
                            "required": ["old_path", "new_path"],
                        },
                    },
                },
                {
                    "type": "function",
                    "function": {
                        "name": "rename_file",
                        "description": "Rename a file. By default, renaming is limited to agent_files/.",
                        "parameters": {
                            "type": "object",
                            "properties": {"old_path": {"type": "string"}, "new_name": {"type": "string"}},
                            "required": ["old_path", "new_name"],
                        },
                    },
                },
                {
                    "type": "function",
                    "function": {
                        "name": "delete_dir",
                        "description": "Delete a directory. recursive=true requires fs_dangerous_enabled=true and remains limited by fs_write_scope.",
                        "parameters": {
                            "type": "object",
                            "properties": {"path": {"type": "string"}, "recursive": {"type": "boolean", "default": False}},
                            "required": ["path"],
                        },
                    },
                },
            ]
        )

    print(
        f"[DEBUG chat-tools] Tool calls enabled: count={len(tools)}, serper_enabled={final_serper_enabled}, "
        f"code_network_enabled={code_network_enabled}, "
        f"fs_read_scope={policy['read_scope']}, fs_write_scope={policy['write_scope']}, fs_dangerous_enabled={policy['dangerous_enabled']}",
        file=sys.stderr,
    )
    return tools


# -----------------------------
# Helpers
# -----------------------------

def _truncate(s: str, n: int = 240) -> str:
    s = (s or "").strip()
    if len(s) <= n:
        return s
    return s[:n].rstrip() + "..."


def _format_serper_markdown(data: Dict[str, Any], *, query: str, search_type: str, num: int) -> str:
    lines: List[str] = []
    lines.append(f"Serper query: {query}")
    lines.append(f"Type: {search_type}; result count: {num}")
    lines.append("")

    items: List[Dict[str, Any]] = []
    if isinstance(data.get("organic"), list):
        items = data["organic"]
    elif isinstance(data.get("news"), list):
        items = data["news"]
    elif isinstance(data.get("results"), list):
        items = data["results"]

    if not items:
        md = data.get("markdown")
        if isinstance(md, str) and md.strip():
            return (
                "Serper returned raw markdown:\n\n"
                + md.strip()
                + "\n\n"
                "Note: When answering, use only real links that appear in the content above."
            )
        return "Serper search completed, but no usable results were returned. Missing organic/news/results/markdown fields."

    for i, it in enumerate(items[: max(1, min(10, int(num)))]):
        if not isinstance(it, dict):
            continue
        title = str(it.get("title") or it.get("name") or "").strip() or f"Result {i + 1}"
        url = str(it.get("link") or it.get("url") or it.get("source") or "").strip()
        snippet = str(it.get("snippet") or it.get("description") or it.get("summary") or "").strip()

        if url:
            lines.append(f"{i + 1}. [{title}]({url})")
        else:
            lines.append(f"{i + 1}. {title}")
        if snippet:
            lines.append(f"   - Summary: {_truncate(snippet, 260)}")
        if url:
            lines.append(f"   - URL: {url}")
        lines.append("")

    lines.append("Requirement: When answering, cite only the URLs listed above. Do not invent or add links.")
    return "\n".join(lines).strip()


def _format_entries(entries: list, limit: int = 40) -> str:
    lines: List[str] = []
    for e in entries[: max(0, int(limit))]:
        if not isinstance(e, dict):
            continue
        t = e.get("type") or e.get("kind") or ""
        name = e.get("name") or e.get("path") or ""
        icon = "📁" if t in ("directory", "dir", "folder") else "📄"
        lines.append(f"{icon} {name}")
    if len(entries) > limit:
        lines.append(f"... {len(entries) - limit} more entries")
    return "\n".join(lines).strip()


def _format_range_text(text: str, start_line: int, end_line: int) -> str:
    lines = (text or "").splitlines()
    n = len(lines)
    start_line = max(1, int(start_line))
    end_line = max(start_line, int(end_line))
    end_line = min(end_line, n if n > 0 else end_line)
    if n == 0:
        return ""
    out: List[str] = []
    for i in range(start_line, end_line + 1):
        if 1 <= i <= n:
            out.append(f"{i:>5}: {lines[i - 1]}")
    head = f"Showing lines {start_line}-{end_line} of {n}"
    return head + "\n" + "\n".join(out)


def _json_result(result: Any) -> str:
    return json.dumps(result, ensure_ascii=False, indent=2)


# -----------------------------
# Tool execution
# -----------------------------

def run_tool(
    tool_name: str,
    tool_args_json: str,
    *,
    user_ctx,
    user_content: str,
    mcp_overrides: Dict[str, Any] | None = None,
) -> str:
    try:
        tool_args: Dict[str, Any] = json.loads(tool_args_json or "{}")
    except Exception as e:
        return f"Tool argument parsing failed: {e}"

    mcp_overrides = _normalize_mcp_overrides(mcp_overrides)
    serper_enabled = _coerce_bool_local(mcp_overrides.get("serper_enabled", False))
    code_network = _coerce_bool_local(mcp_overrides.get("code_network_enabled", False))
    policy = _policy_from_overrides(mcp_overrides)

    print(
        f"[DEBUG chat-tools] Running tool: {tool_name}({tool_args}), "
        f"serper_enabled={serper_enabled}, code_network_enabled={code_network}, "
        f"fs_read_scope={policy['read_scope']}, fs_write_scope={policy['write_scope']}, fs_dangerous_enabled={policy['dangerous_enabled']}",
        file=sys.stderr,
    )

    if tool_name == "execute_code":
        from tools.interpreter import nisb_execute_code
        import re

        code = tool_args.get("code", "")
        code = code.replace("\\n", "\n").replace("\\t", "\t").replace("\\'", "'").replace('\\"', '"')

        def fix_savefig_path(match: re.Match) -> str:
            original_path = match.group(1)
            if not original_path.startswith("/tmp/"):
                filename = original_path.split("/")[-1]
                fixed_path = f"/tmp/{filename}"
                print(f"[INFO chat-tools] Auto-fixed image path: {original_path} -> {fixed_path}", file=sys.stderr)
                return f"plt.savefig('{fixed_path}'"
            return match.group(0)

        original_code = code
        code = re.sub(r"plt\.savefig\(['\"](.+?)['\"]", fix_savefig_path, code)
        if code != original_code:
            print(f"[DEBUG chat-tools] Fixed code:\n{code}", file=sys.stderr)

        result = nisb_execute_code(
            {
                "code": code,
                "timeout": tool_args.get("timeout", 30),
                "user_id": getattr(user_ctx, "user_id", None),
                "email": getattr(user_ctx, "email", None),
                "name": getattr(user_ctx, "name", None),
                "network": code_network,
            }
        )

        output = result.get("output")
        if isinstance(output, str) and output.strip():
            return output
        if result.get("success") is False:
            err = result.get("error")
            return f"Code execution failed: {err}" if err else "Code execution failed."
        return "Execution completed."

    if tool_name in ("read_file", "read_file_range"):
        from tools.filesystem import nisb_file_read

        filename = _resolve_nisb_uri(tool_args.get("filename"))
        ok, msg = _check_read_allowed(filename, policy)
        if not ok:
            return msg

        result = nisb_file_read({**_ctx_fs_args(user_ctx), "filename": filename})
        if not result.get("success"):
            return "Read failed."

        if result.get("metadata", {}).get("type") == "image":
            size = len(result.get("content", "") or "")
            return f"Image file: {filename}. Base64 encoded, {size} bytes."

        text = result.get("content", "") or ""
        if tool_name == "read_file_range":
            return _format_range_text(text, tool_args.get("start_line", 1), tool_args.get("end_line", 200))
        return text

    if tool_name == "list_files":
        from tools.filesystem import nisb_dir_list

        path = _strip_agent_files_prefix(_resolve_nisb_uri(tool_args.get("path", "")))
        ok, msg = _check_read_allowed(path, policy)
        if not ok:
            return msg

        result = nisb_dir_list({**_ctx_fs_args(user_ctx), "path": path})
        if result.get("success"):
            entries = result.get("entries", [])
            if isinstance(entries, list) and entries:
                return _format_entries(entries, limit=60)
            return "No entries found."
        return "Directory listing failed."

    if tool_name == "tree_files":
        from tools.filesystem import nisb_dir_tree

        path = _strip_agent_files_prefix(_resolve_nisb_uri(tool_args.get("path", "")))
        ok, msg = _check_read_allowed(path, policy)
        if not ok:
            return msg

        depth = int(tool_args.get("depth", 2))
        depth = max(1, min(6, depth))

        result = nisb_dir_tree({**_ctx_fs_args(user_ctx), "path": path, "depth": depth})
        if not result.get("success"):
            return "Directory tree failed."

        if isinstance(result.get("tree"), str) and result["tree"].strip():
            return result["tree"].strip()
        if isinstance(result.get("entries"), list):
            return _format_entries(result.get("entries", []), limit=200)
        return "No tree entries found."

    if tool_name == "search_files":
        from tools.filesystem import nisb_file_search

        path = _strip_agent_files_prefix(_resolve_nisb_uri(tool_args.get("path", "")))
        ok, msg = _check_read_allowed(path, policy)
        if not ok:
            return msg

        keyword = str(tool_args.get("keyword", "") or "").strip()
        if not keyword:
            return "Invalid arguments: keyword cannot be empty."

        limit = int(tool_args.get("limit", 50))
        limit = max(1, min(200, limit))

        result = nisb_file_search({**_ctx_fs_args(user_ctx), "path": path, "keyword": keyword, "limit": limit})
        if not result.get("success"):
            return "File search failed."

        hits = result.get("results")
        if not isinstance(hits, list):
            hits = result.get("entries")
        if not isinstance(hits, list):
            hits = result.get("files")

        if isinstance(hits, list) and hits:
            lines: List[str] = []
            for h in hits[:limit]:
                if isinstance(h, dict):
                    p = h.get("path") or h.get("filename") or h.get("name") or ""
                    lines.append(f"📄 {p}".strip())
                else:
                    lines.append(f"📄 {str(h)}")
            if len(hits) > limit:
                lines.append(f"... {len(hits) - limit} more matches")
            return "\n".join(lines).strip()

        return "No matching files found."

    if tool_name == "update_file":
        from tools.filesystem import nisb_file_update, nisb_file_create, nisb_file_read

        filename = _resolve_nisb_uri(tool_args.get("filename", ""))
        ok, msg = _check_write_allowed(filename, policy)
        if not ok:
            return msg

        content = tool_args.get("content", "")

        try:
            probe = nisb_file_read({**_ctx_fs_args(user_ctx), "filename": filename})
            exists = bool(probe and probe.get("success"))
        except Exception:
            exists = False

        if not exists:
            create_res = nisb_file_create(
                {
                    **_ctx_fs_args(user_ctx),
                    "filename": filename,
                    "content": content,
                    "description": "chat-tool auto create",
                    "auto_categorize": False,
                }
            )
            if create_res.get("success") is False:
                return "File creation failed."
            return f"File created: {filename}"

        result = nisb_file_update({**_ctx_fs_args(user_ctx), "filename": filename, "content": content})
        if result.get("success") is False:
            return "File update failed."
        return f"File updated: {filename}"

    if tool_name == "delete_file":
        from tools.filesystem import nisb_file_delete

        filename = _resolve_nisb_uri(tool_args.get("filename", ""))
        ok, msg = _check_write_allowed(filename, policy)
        if not ok:
            return msg

        result = nisb_file_delete({**_ctx_fs_args(user_ctx), "filename": filename, "permanent": True})
        if result.get("success") is False:
            return "File deletion failed."
        return f"File deleted: {filename}"

    if tool_name == "move_path":
        from tools.filesystem import nisb_file_move_path

        old_path = _resolve_nisb_uri(tool_args.get("old_path", ""))
        new_path = _resolve_nisb_uri(tool_args.get("new_path", ""))
        ok1, msg1 = _check_write_allowed(old_path, policy)
        ok2, msg2 = _check_write_allowed(new_path, policy)
        if not ok1:
            return msg1
        if not ok2:
            return msg2

        result = nisb_file_move_path({**_ctx_fs_args(user_ctx), "old_path": old_path, "new_path": new_path})
        if result.get("success") is False:
            return "Move operation failed."
        return f"Path moved: {old_path} -> {new_path}"

    if tool_name == "rename_file":
        from tools.filesystem import nisb_file_rename

        old_path = _resolve_nisb_uri(tool_args.get("old_path", ""))
        new_name = str(tool_args.get("new_name", "") or "").strip()
        ok, msg = _check_write_allowed(old_path, policy)
        if not ok:
            return msg
        if not new_name:
            return "Invalid arguments: new_name cannot be empty."

        result = nisb_file_rename({**_ctx_fs_args(user_ctx), "old_path": old_path, "new_name": new_name})
        if result.get("success") is False:
            return "Rename operation failed."
        return f"File renamed: {old_path} -> {new_name}"

    if tool_name == "delete_dir":
        from tools.filesystem import nisb_dir_delete

        path = _resolve_nisb_uri(tool_args.get("path", ""))
        recursive = bool(tool_args.get("recursive", False))
        ok, msg = _check_write_allowed(path, policy)
        if not ok:
            return msg
        if recursive and not policy["dangerous_enabled"]:
            return "DANGEROUS_DENIED: Recursive directory deletion requires fs_dangerous_enabled=true."

        result = nisb_dir_delete({**_ctx_fs_args(user_ctx), "path": path, "recursive": recursive})
        if result.get("success") is False:
            return "Directory deletion failed."
        return f"Directory deleted: {path}"

    if tool_name == "serper_search":
        if not serper_enabled:
            return "Serper search is disabled for the current conversation. The serper_search call was blocked."

        try:
            q = str(tool_args.get("query") or user_content or "").strip()
            num = tool_args.get("num", None)
            if num is None:
                num = tool_args.get("num_results", 5)
            try:
                num_i = int(num)
            except Exception:
                num_i = 5
            num_i = max(1, min(10, num_i))

            st = str(tool_args.get("search_type", "search") or "search").strip()
            if st not in ("search", "news"):
                st = "search"

            serper_data = serper_search(query=q, num=num_i, search_type=st) or {}
            if not isinstance(serper_data, dict):
                return "Serper search completed, but the returned payload format is invalid. Expected dict."

            return _format_serper_markdown(serper_data, query=q, search_type=st, num=num_i)
        except Exception as se:
            return f"Serper search failed: {se}"

    return f"Unknown tool: {tool_name}"
