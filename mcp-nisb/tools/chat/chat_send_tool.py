#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import json
import re
import sys
import threading
from datetime import datetime
from math import sqrt
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from core.openai_utils import get_embedding
from core.user_context import auto_user_context, get_user_ctx
from tools.chat.hebbian import process_conversation_hebbian
from tools.chat.indexing import build_turn_index_level1, build_turn_index_level2
from tools.chat.models.anthropic import AnthropicModel
from tools.chat.models.deepseek import DeepSeekModel
from tools.chat.models.openai import OpenAIModel
from tools.chat.tools_runtime import build_tools_for_model, run_tool
from .chat_conversation_store import (
    append_turn_record,
    find_conv_dir,
    load_conversation_meta,
    read_turn_records,
    save_conversation_meta,
)

_URL_RE = re.compile(r"https?://\S+")
_ALLOWED_RAG_MODES = {"off", "web", "auto", "cite", "ground"}

_TEXT_ATTACHMENT_SUFFIXES = {
    ".txt",
    ".md",
    ".json",
    ".py",
    ".js",
    ".ts",
    ".tsx",
    ".jsx",
    ".html",
    ".css",
    ".yaml",
    ".yml",
    ".sh",
    ".env",
    ".csv",
    ".log",
    ".xml",
}
_BINARY_ATTACHMENT_SUFFIXES = {
    ".pdf",
    ".doc",
    ".docx",
    ".ppt",
    ".pptx",
    ".xls",
    ".xlsx",
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".webp",
    ".bmp",
    ".ico",
    ".zip",
    ".rar",
    ".7z",
    ".mp3",
    ".wav",
    ".mp4",
    ".mov",
    ".avi",
}


def _extract_urls(text: str) -> List[str]:
    if not text:
        return []

    raw = _URL_RE.findall(text)
    cleaned: List[str] = []
    for u in raw:
        u2 = u.rstrip(").,;:!?]}'\\\"")
        if u2:
            cleaned.append(u2)

    seen = set()
    out: List[str] = []
    for u in cleaned:
        if u in seen:
            continue
        seen.add(u)
        out.append(u)
    return out


def _normalize_url(url: str) -> str:
    try:
        p = urlparse(url)
        scheme = (p.scheme or "https").lower()
        netloc = (p.netloc or "").lower()
        path = p.path or "/"
        if path != "/" and path.endswith("/"):
            path = path[:-1]
        return f"{scheme}://{netloc}{path}"
    except Exception:
        return url


def _safe_list_dict(v: Any) -> List[Dict[str, Any]]:
    if isinstance(v, list):
        return [x for x in v if isinstance(x, dict)]
    return []


def _safe_dict(v: Any) -> Dict[str, Any]:
    if isinstance(v, dict):
        return dict(v)
    return {}


def _safe_list_str(v: Any) -> List[str]:
    if not isinstance(v, list):
        return []
    out: List[str] = []
    for item in v:
        s = str(item or "").strip()
        if s:
            out.append(s)
    return out


def _first_text(*values: Any) -> str:
    for value in values:
        text = str(value or "").strip()
        if text:
            return text
    return ""


def _coerce_bool_local(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    s = str(value or "").strip().lower()
    return s in ("1", "true", "yes", "on", "y")


def _normalize_rag_mode(args: Dict[str, Any]) -> str:
    rag_mode = _first_text(args.get("rag_mode"), args.get("ragmode"), "off").lower()
    if rag_mode not in _ALLOWED_RAG_MODES:
        return "off"
    return rag_mode


def _normalize_mode_used(args: Dict[str, Any], rag_mode: str) -> str:
    mode_used = _first_text(args.get("mode_used"), args.get("modeused"), rag_mode, "off").lower()
    if mode_used not in _ALLOWED_RAG_MODES:
        return rag_mode if rag_mode in _ALLOWED_RAG_MODES else "off"
    return mode_used


def _merge_alias_field(dst: Dict[str, Any], sources: List[Dict[str, Any]], target_key: str, aliases: List[str]) -> None:
    if target_key in dst:
        return
    for src in sources:
        if not isinstance(src, dict):
            continue
        for key in [target_key, *aliases]:
            if key in src and src.get(key) is not None and src.get(key) != "":
                dst[target_key] = src.get(key)
                return


def _normalize_capability_gate(args: Dict[str, Any]) -> Dict[str, Any]:
    gate = args.get("capability_gate")
    if not isinstance(gate, dict):
        gate = args.get("capabilitygate")
    if not isinstance(gate, dict):
        gate = {}

    out = dict(gate)
    sources = [gate, args]

    _merge_alias_field(out, sources, "policy_version", ["policyVersion"])
    _merge_alias_field(out, sources, "workspace_id", ["workspaceId"])
    _merge_alias_field(out, sources, "focus_root", ["focusRoot"])
    _merge_alias_field(out, sources, "fs_read_scope", ["fsReadScope"])
    _merge_alias_field(out, sources, "fs_write_scope", ["fsWriteScope"])
    _merge_alias_field(out, sources, "fs_dangerous_enabled", ["fsDangerousEnabled"])
    _merge_alias_field(out, sources, "inherit_workspace_context", ["inheritWorkspaceContext"])
    _merge_alias_field(out, sources, "inherit_focus_root", ["inheritFocusRoot"])

    return out


def _normalize_mcp_overrides(args: Dict[str, Any]) -> Dict[str, Any]:
    raw = args.get("mcp_overrides")
    if not isinstance(raw, dict):
        raw = args.get("mcpoverrides")
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

    cap_gate = _normalize_capability_gate(args)
    for key in (
        "policy_version",
        "workspace_id",
        "focus_root",
        "fs_read_scope",
        "fs_write_scope",
        "fs_dangerous_enabled",
        "inherit_workspace_context",
        "inherit_focus_root",
    ):
        if key not in out and key in cap_gate:
            out[key] = cap_gate.get(key)

    if "focus_root" not in out:
        focus_root = _first_text(args.get("focus_root"), args.get("focusRoot"))
        if focus_root:
            out["focus_root"] = focus_root

    if "workspace_id" not in out:
        workspace_id = _first_text(args.get("workspace_id"), args.get("workspaceId"))
        if workspace_id:
            out["workspace_id"] = workspace_id

    return out


def _normalize_attachments(args: Dict[str, Any]) -> List[Dict[str, Any]]:
    raw = args.get("attachments")
    if not isinstance(raw, list):
        raw = args.get("selected_attachments")
    if not isinstance(raw, list):
        return []

    out: List[Dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue

        path = _first_text(item.get("path"), item.get("relative_path"), item.get("relativePath"))
        if not path:
            continue

        name = _first_text(item.get("name"), Path(path).name)
        att_type = _first_text(item.get("type"))
        try:
            size = int(item.get("size") or 0)
        except Exception:
            size = 0

        out.append(
            {
                "name": name,
                "path": path,
                "type": att_type,
                "size": size,
            }
        )
    return out


def _resolve_attachment_file(base_path: str, relative_path: str) -> Optional[Path]:
    try:
        rel = str(relative_path or "").strip()
        if not rel:
            return None

        base = Path(base_path).resolve()
        candidate = (base / rel).resolve()

        if candidate == base or base not in candidate.parents:
            return None
        if not candidate.exists() or not candidate.is_file():
            return None
        return candidate
    except Exception:
        return None


def _clip_text(text: Any, limit: int) -> str:
    s = str(text or "")
    if len(s) <= limit:
        return s
    return s[:limit] + "\n...[truncated]"


def _read_attachment_preview(file_path: Path, max_chars: int) -> str:
    if max_chars <= 0:
        return ""

    try:
        text = file_path.read_text(encoding="utf-8")
    except Exception:
        try:
            text = file_path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            return ""

    text = str(text or "").strip()
    if not text:
        return ""

    return _clip_text(text, max_chars)


def _build_attachment_context(base_path: str, attachments: List[Dict[str, Any]]) -> str:
    normalized = _safe_list_dict(attachments)
    if not normalized:
        return ""

    manifest: List[str] = []
    blocks: List[str] = []
    remaining = 24000
    per_file_limit = 8000

    for idx, item in enumerate(normalized, start=1):
        name = _first_text(item.get("name"), "attachment")
        rel_path = _first_text(item.get("path"))
        att_type = _first_text(item.get("type"))
        manifest.append(f"- {name} ({rel_path})")

        resolved = _resolve_attachment_file(base_path, rel_path)
        if not resolved:
            blocks.append(
                f"【附件{idx}】{name}\n"
                f"路径：{rel_path}\n"
                "说明：文件不存在、不可访问或路径不安全。"
            )
            continue

        suffix = resolved.suffix.lower()
        if suffix in _BINARY_ATTACHMENT_SUFFIXES:
            blocks.append(
                f"【附件{idx}】{name}\n"
                f"路径：{rel_path}\n"
                f"类型：{att_type or suffix or 'binary'}\n"
                "说明：该附件为二进制或富文档文件，当前轮不会自动抽取全文；回答时可结合文件名与路径理解其上下文。"
            )
            continue

        preview_limit = min(per_file_limit, remaining)
        preview = _read_attachment_preview(resolved, preview_limit)

        if preview:
            blocks.append(
                f"【附件{idx}】{name}\n"
                f"路径：{rel_path}\n"
                "内容摘录：\n"
                f"{preview}"
            )
            remaining -= len(preview)
        else:
            fallback_type = att_type or suffix or "unknown"
            blocks.append(
                f"【附件{idx}】{name}\n"
                f"路径：{rel_path}\n"
                f"类型：{fallback_type}\n"
                "说明：未能读取文本内容，但该附件已被附带到本轮上下文。"
            )

        if remaining <= 0:
            break

    if not blocks:
        return ""

    return (
        "用户本轮附带了以下附件，请优先结合这些附件回答；若附件内容已提供，就不要忽略它们。\n"
        + "\n".join(manifest)
        + "\n\n"
        + "\n\n".join(blocks)
    )


def _tool_names(tools: Any) -> List[str]:
    out: List[str] = []
    if not isinstance(tools, list):
        return out

    for item in tools:
        if not isinstance(item, dict):
            continue
        if item.get("type") == "function":
            fn = item.get("function")
            if isinstance(fn, dict):
                name = str(fn.get("name") or "").strip()
                if name:
                    out.append(name)
    return out


def _normalize_tool_calls(tool_calls: Any) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for idx, item in enumerate(tool_calls if isinstance(tool_calls, list) else [], start=1):
        if not isinstance(item, dict):
            continue
        args_value = item.get("arguments")
        if args_value is None:
            args_value = item.get("args")
        if args_value is None:
            args_value = item.get("arguments_json")
        out.append(
            {
                "id": _first_text(item.get("id"), f"tool_call_{idx}"),
                "name": _first_text(item.get("name"), item.get("tool_name"), "unknown_tool"),
                "arguments": args_value if isinstance(args_value, (dict, list, str, int, float, bool)) or args_value is None else str(args_value),
                "arguments_preview": _first_text(item.get("arguments_preview"), item.get("preview"), _clip_text(args_value, 2000)),
                "status": _first_text(item.get("status"), "done"),
                "reason": _first_text(item.get("reason")),
                "note": _first_text(item.get("note")),
            }
        )
    return out


def _normalize_tool_results(tool_results: Any) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for idx, item in enumerate(tool_results if isinstance(tool_results, list) else [], start=1):
        if not isinstance(item, dict):
            continue
        result_value = item.get("result")
        if result_value is None:
            result_value = item.get("output")
        if result_value is None:
            result_value = item.get("result_json")
        out.append(
            {
                "id": _first_text(item.get("id"), f"tool_call_{idx}"),
                "name": _first_text(item.get("name"), item.get("tool_name"), "unknown_tool"),
                "result": result_value if isinstance(result_value, (dict, list, str, int, float, bool)) or result_value is None else str(result_value),
                "preview": _first_text(item.get("preview"), item.get("result_preview"), _clip_text(result_value, 4000)),
                "status": _first_text(item.get("status"), "done"),
            }
        )
    return out


def _append_tool_call_activity(
    tool_calls: List[Dict[str, Any]],
    tool_name: str,
    arguments_json: str,
    *,
    status: str = "done",
    call_id: str = "",
) -> None:
    name = str(tool_name or "").strip() or "unknown_tool"
    args_text = str(arguments_json or "")
    stable_id = str(call_id or f"tool_call_{len(tool_calls) + 1}")
    preview = _clip_text(args_text, 2000)

    parsed_arguments: Any = args_text
    try:
        parsed = json.loads(args_text)
        if isinstance(parsed, (dict, list, str, int, float, bool)) or parsed is None:
            parsed_arguments = parsed
    except Exception:
        pass

    tool_calls.append(
        {
            "id": stable_id,
            "name": name,
            "arguments": parsed_arguments,
            "arguments_preview": preview,
            "status": str(status or "done"),
            "reason": "",
            "note": "",
        }
    )


def _append_tool_result_activity(
    tool_results: List[Dict[str, Any]],
    tool_name: str,
    result_text: str,
    *,
    status: str = "done",
    result_id: str = "",
) -> None:
    name = str(tool_name or "").strip() or "unknown_tool"
    raw = str(result_text or "")
    stable_id = str(result_id or f"tool_call_{len(tool_results) + 1}")
    preview = _clip_text(raw, 4000)

    parsed_result: Any = raw
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, (dict, list, str, int, float, bool)) or parsed is None:
            parsed_result = parsed
    except Exception:
        pass

    tool_results.append(
        {
            "id": stable_id,
            "name": name,
            "result": parsed_result,
            "preview": preview,
            "status": str(status or "done"),
        }
    )


def _finalize_response_text(status: str, response: str, message: str) -> str:
    res = str(response or "").strip()
    if res:
        return res
    if str(status or "").strip().lower() == "success":
        msg = str(message or "").strip()
        if msg:
            return msg
        return "已完成本轮对话处理，但未生成可展示回复。"
    return ""


def _build_standard_result(
    *,
    status: str,
    request_id: str,
    conv_id: str,
    rag_mode: str,
    mcp_overrides: Dict[str, Any],
    mode_used: str,
    response: str = "",
    citations: Optional[List[Dict[str, Any]]] = None,
    rss_evidence: Optional[List[Dict[str, Any]]] = None,
    market_evidence: Optional[List[Dict[str, Any]]] = None,
    evidence_query: str = "",
    evidence_tools: Optional[List[str]] = None,
    evidence_result: Optional[Dict[str, Any]] = None,
    qa_id: str = "",
    group_id: str = "",
    message: str = "",
    tool_calls: Optional[List[Dict[str, Any]]] = None,
    tool_results: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    final_status = str(status or "success")
    final_message = str(message or "")
    final_response = _finalize_response_text(final_status, str(response or ""), final_message)

    return {
        "status": final_status,
        "request_id": str(request_id or ""),
        "conv_id": str(conv_id or ""),
        "rag_mode": rag_mode if rag_mode in _ALLOWED_RAG_MODES else "off",
        "mcp_overrides": _safe_dict(mcp_overrides),
        "mode_used": mode_used if mode_used in _ALLOWED_RAG_MODES else "off",
        "response": final_response,
        "citations": _safe_list_dict(citations),
        "rss_evidence": _safe_list_dict(rss_evidence),
        "market_evidence": _safe_list_dict(market_evidence),
        "evidence_query": str(evidence_query or ""),
        "evidence_tools": _safe_list_str(evidence_tools),
        "evidence_result": _safe_dict(evidence_result),
        "qa_id": str(qa_id or ""),
        "group_id": str(group_id or ""),
        "message": final_message,
        "tool_calls": _normalize_tool_calls(tool_calls),
        "tool_results": _normalize_tool_results(tool_results),
    }


def _async_indexing_and_hebbian(
    conv_dir: Path,
    turn_index: int,
    user_text: str,
    ai_text: str,
    index_model: str,
    base_path: str,
    concept_language: str,
    concept_backend: str,
) -> None:
    try:
        build_turn_index_level1(
            conv_dir=conv_dir,
            turn_index=turn_index,
            user_text=user_text,
            ai_text=ai_text,
            model=index_model,
        )
        build_turn_index_level2(
            conv_dir=conv_dir,
            turn_index=turn_index,
            user_text=user_text,
            ai_text=ai_text,
            model=index_model,
        )
        print(f"[INFO chat] Indexing done with model={index_model}", file=sys.stderr)
    except Exception as e:
        print(f"[WARN chat] Indexing failed: {e}", file=sys.stderr)

    try:
        process_conversation_hebbian(
            base_path=base_path,
            user_content=user_text,
            ai_content=ai_text,
            concept_language=concept_language,
            concept_backend=concept_backend,
        )
        print("[INFO chat] Hebbian triggered", file=sys.stderr)
    except Exception as e:
        print(f"[WARN chat] Hebbian failed: {e}", file=sys.stderr)


def _load_turn_index_level2(conv_dir: Path) -> List[Dict[str, Any]]:
    index_file = conv_dir / "turns_index_level2.jsonl"
    items: List[Dict[str, Any]] = []
    if not index_file.exists():
        return items

    try:
        with index_file.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except Exception:
                    continue

                if (
                    isinstance(rec, dict)
                    and "turn_index" in rec
                    and "key_points" in rec
                    and "embedding" in rec
                ):
                    items.append(rec)
    except Exception as e:
        print(f"[WARN chat] load level2 index failed: {e}", file=sys.stderr)

    return items


def _cosine_sim(a: List[float], b: List[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0

    dot = 0.0
    na = 0.0
    nb = 0.0
    for x, y in zip(a, b):
        dot += x * y
        na += x * x
        nb += y * y

    if na <= 0 or nb <= 0:
        return 0.0

    return dot / (sqrt(na) * sqrt(nb))


def _build_index_context(conv_dir: Path, query_text: str, top_k: int = 3) -> str:
    try:
        query_vec = get_embedding(query_text)
    except Exception as e:
        print(f"[WARN chat] query embedding failed: {e}", file=sys.stderr)
        return ""

    index_items = _load_turn_index_level2(conv_dir)
    if not index_items:
        return ""

    scored = []
    for rec in index_items:
        emb = rec.get("embedding") or []
        sim = _cosine_sim(query_vec, emb)
        scored.append((sim, rec))

    scored.sort(key=lambda x: x[0], reverse=True)
    top = [rec for sim, rec in scored[:top_k] if sim > 0]

    if not top:
        return ""

    parts = []
    for rec in top:
        turn_idx = rec.get("turn_index")
        key_points = rec.get("key_points") or []
        lines = [f"【第 {turn_idx} 轮要点】"]
        for kp in key_points:
            lines.append(f"- {kp}")
        parts.append("\n".join(lines))

    return "\n\n".join(parts)


def _append_serper_prefetch_message(messages: List[Dict[str, Any]], tool_result: str, mode_used: str) -> None:
    if not str(tool_result or "").strip():
        return

    messages.append(
        {
            "role": "system",
            "content": (
                f"当前回答模式为 {mode_used}。\n"
                "以下是本轮联网搜索（Serper）返回的结果。\n"
                "请优先基于这些结果回答；若结果已提供，就不要声称自己无法实时搜索互联网。\n"
                "回答中只能引用这些结果里真实出现过的链接。\n\n"
                + tool_result
            ),
        }
    )


def _should_fast_serper_prefetch(*, serper_enabled: bool, code_network_enabled: bool, mode_used: str) -> bool:
    return (
        bool(serper_enabled)
        and (not bool(code_network_enabled))
        and str(mode_used or "").strip().lower() in {"web", "off", "auto"}
    )


def _run_serper_prefetch(*, content: str, user_ctx, mcp_overrides: Dict[str, Any]) -> tuple[str, str]:
    clean_q = content.split("【Agent 工具观察", 1)[0].strip() or content.strip()
    tool_args_json = json.dumps(
        {
            "query": clean_q,
            "num": 5,
            "num_results": 5,
        },
        ensure_ascii=False,
    )
    tool_result = run_tool(
        "serper_search",
        tool_args_json,
        user_ctx=user_ctx,
        user_content=content,
        mcp_overrides=mcp_overrides,
    ) or ""
    return tool_args_json, str(tool_result or "")


@auto_user_context
def nisb_chat_send(args: dict) -> dict:
    user_ctx = get_user_ctx()
    args = dict(args or {})

    request_id = _first_text(args.get("request_id"), args.get("requestid"))
    conv_id = _first_text(args.get("conv_id"), args.get("convid"))
    content = str(args.get("content") or "")
    model = _first_text(args.get("model"), "gpt-4o-mini") or "gpt-4o-mini"

    rag_mode = _normalize_rag_mode(args)
    mode_used = _normalize_mode_used(args, rag_mode)

    citations = _safe_list_dict(args.get("citations"))
    rss_evidence = _safe_list_dict(args.get("rss_evidence") or args.get("rssevidence"))
    market_evidence = _safe_list_dict(args.get("market_evidence") or args.get("marketevidence"))

    evidence_query = _first_text(args.get("evidence_query"), args.get("evidencequery"), content.strip())
    evidence_tools = _safe_list_str(args.get("evidence_tools") or args.get("evidencetools"))

    evidence_result = args.get("evidence_result")
    if not isinstance(evidence_result, dict):
        evidence_result = args.get("evidenceresult")
    if not isinstance(evidence_result, dict):
        evidence_result = {
            "citations": citations,
            "rss_evidence": rss_evidence,
            "market_evidence": market_evidence,
        }

    qa_id = _first_text(args.get("qa_id"), args.get("qaid"))
    group_id = _first_text(args.get("group_id"), args.get("groupid"))

    concept_language = str(args.get("concept_language") or args.get("conceptlanguage") or "auto")
    concept_backend = str(args.get("concept_backend") or args.get("conceptbackend") or "auto")
    context_mode = str(args.get("context_mode") or "index").strip().lower()

    capability_gate = _normalize_capability_gate(args)
    mcp_overrides = _normalize_mcp_overrides(args)
    attachments = _normalize_attachments(args)

    serper_enabled = _coerce_bool_local(mcp_overrides.get("serper_enabled"))
    code_network_enabled = _coerce_bool_local(mcp_overrides.get("code_network_enabled"))

    if mode_used == "web":
        serper_enabled = True
        mcp_overrides["serper_enabled"] = True

    print(
        f"[DEBUG chat] MCP overrides: serper_enabled={serper_enabled}, "
        f"code_network_enabled={code_network_enabled}, mode_used={mode_used}, "
        f"fs_read_scope={mcp_overrides.get('fs_read_scope')}, "
        f"fs_write_scope={mcp_overrides.get('fs_write_scope')}, "
        f"focus_root={mcp_overrides.get('focus_root')}",
        file=sys.stderr,
    )

    tool_calls: List[Dict[str, Any]] = []
    tool_results: List[Dict[str, Any]] = []

    if not conv_id or not content:
        return _build_standard_result(
            status="error",
            request_id=request_id,
            conv_id=conv_id,
            rag_mode=rag_mode,
            mcp_overrides=mcp_overrides,
            mode_used=mode_used,
            citations=citations,
            rss_evidence=rss_evidence,
            market_evidence=market_evidence,
            evidence_query=evidence_query,
            evidence_tools=evidence_tools,
            evidence_result=evidence_result,
            qa_id=qa_id,
            group_id=group_id,
            tool_calls=tool_calls,
            tool_results=tool_results,
            message="❌ conv_id 和 content 不能为空",
        )

    conv_dir = find_conv_dir(user_ctx.base, conv_id)
    if not conv_dir:
        return _build_standard_result(
            status="error",
            request_id=request_id,
            conv_id=conv_id,
            rag_mode=rag_mode,
            mcp_overrides=mcp_overrides,
            mode_used=mode_used,
            citations=citations,
            rss_evidence=rss_evidence,
            market_evidence=market_evidence,
            evidence_query=evidence_query,
            evidence_tools=evidence_tools,
            evidence_result=evidence_result,
            qa_id=qa_id,
            group_id=group_id,
            tool_calls=tool_calls,
            tool_results=tool_results,
            message=f"❌ 对话不存在: {conv_id}",
        )

    turn_records = read_turn_records(conv_dir)
    history_messages: List[Dict[str, Any]] = []
    for turn in turn_records:
        if str(turn.get("turn_type") or "") not in ("user", "assistant"):
            continue
        history_messages.append(
            {
                "role": turn.get("turn_type"),
                "content": turn.get("content"),
            }
        )

    user_turn = {
        "sequence": len(history_messages) + 1,
        "turn_type": "user",
        "content": content,
        "timestamp": datetime.now().isoformat(),
        "mode_used": mode_used,
        "request_id": request_id,
        "conv_id": conv_id,
        "rag_mode": rag_mode,
        "mcp_overrides": mcp_overrides,
        "capability_gate": capability_gate,
    }
    try:
        user_turn["embedding"] = get_embedding(content)
        print("[DEBUG chat] 用户消息向量化成功", file=sys.stderr)
    except Exception as e:
        print(f"[WARN chat] 用户消息向量化失败: {e}", file=sys.stderr)

    append_turn_record(conv_dir, user_turn)

    attachment_context = _build_attachment_context(user_ctx.base, attachments)
    if attachment_context:
        print(f"[INFO chat] attachments injected: {len(attachments)}", file=sys.stderr)

    if context_mode == "index":
        try:
            index_context = _build_index_context(conv_dir, content, top_k=3)
        except Exception as e:
            print(f"[WARN chat] build index context failed: {e}", file=sys.stderr)
            index_context = ""

        sys_msg = (
            "You are the user's long-term conversation partner. "
            "The system may provide historical memory, attachment context, and web search results. "
            "If attachment content is provided below, treat it as user-supplied source material for this turn. "
            "If web search results are provided below, treat them as current external evidence. "
            "Do not say you cannot access real-time information when current search results are already provided. "
            "If the current mode is web, you should prioritize search evidence before answering. "
            "You may use tools such as 'serper_search' for web search and filesystem/code tools when allowed by runtime policy. "
            "When a task requires up-to-date information plus analysis, first call 'serper_search' to collect data, "
            "then call suitable analysis tools if they are available."
        )
        messages: List[Dict[str, Any]] = [{"role": "system", "content": sys_msg}]

        if index_context:
            messages.append(
                {
                    "role": "system",
                    "content": "以下是与当前问题最相关的历史对话要点，请作为背景记忆参考：\n\n" + index_context,
                }
            )

        if attachment_context:
            messages.append(
                {
                    "role": "system",
                    "content": attachment_context,
                }
            )

        for h in history_messages[-4:]:
            messages.append(h)

        messages.append({"role": "user", "content": content})
        print("[DEBUG chat] 使用索引增强上下文 (context_mode=index)", file=sys.stderr)
    else:
        messages = list(history_messages)
        if attachment_context:
            messages.append(
                {
                    "role": "system",
                    "content": attachment_context,
                }
            )
        messages.append({"role": "user", "content": content})
        print("[DEBUG chat] 使用原始上下文 (context_mode=raw)", file=sys.stderr)

    available_tools = build_tools_for_model(model, serper_enabled, mcp_overrides=mcp_overrides)
    print(f"[DEBUG chat] available_tools={_tool_names(available_tools)}", file=sys.stderr)

    last_serper_tool_text = ""
    serper_called_this_turn = False

    fast_serper_prefetch = _should_fast_serper_prefetch(
        serper_enabled=serper_enabled,
        code_network_enabled=code_network_enabled,
        mode_used=mode_used,
    )

    if fast_serper_prefetch:
        try:
            tool_args_json, tool_result = _run_serper_prefetch(
                content=content,
                user_ctx=user_ctx,
                mcp_overrides=mcp_overrides,
            )

            if str(tool_result).strip():
                serper_called_this_turn = True
                last_serper_tool_text = tool_result
                if "serper_search" not in evidence_tools:
                    evidence_tools.append("serper_search")
                evidence_result = {
                    **_safe_dict(evidence_result),
                    "serper_prefetch": True,
                    "serper_prefetch_mode": "fast_chat",
                    "serper_result": tool_result,
                }
                prefetch_id = f"prefetch_serper_{len(tool_calls) + 1}"
                _append_tool_call_activity(
                    tool_calls,
                    "serper_search",
                    tool_args_json,
                    status="done",
                    call_id=prefetch_id,
                )
                _append_tool_result_activity(
                    tool_results,
                    "serper_search",
                    tool_result,
                    status="done",
                    result_id=prefetch_id,
                )
                _append_serper_prefetch_message(messages, tool_result, mode_used)
                available_tools = []
                print("[INFO chat] fast serper prefetch injected", file=sys.stderr)
        except Exception as e:
            print(f"[WARN chat] fast serper prefetch failed: {e}", file=sys.stderr)

    model_no_tools = model.startswith("deepseek") or model.startswith("o1")
    if serper_enabled and model_no_tools and (not last_serper_tool_text):
        try:
            tool_args_json, tool_result = _run_serper_prefetch(
                content=content,
                user_ctx=user_ctx,
                mcp_overrides=mcp_overrides,
            )

            if str(tool_result).strip():
                serper_called_this_turn = True
                last_serper_tool_text = tool_result
                if "serper_search" not in evidence_tools:
                    evidence_tools.append("serper_search")
                evidence_result = {
                    **_safe_dict(evidence_result),
                    "serper_prefetch": True,
                    "serper_prefetch_mode": "model_no_tools",
                    "serper_result": tool_result,
                }
                prefetch_id = f"prefetch_serper_{len(tool_calls) + 1}"
                _append_tool_call_activity(
                    tool_calls,
                    "serper_search",
                    tool_args_json,
                    status="done",
                    call_id=prefetch_id,
                )
                _append_tool_result_activity(
                    tool_results,
                    "serper_search",
                    tool_result,
                    status="done",
                    result_id=prefetch_id,
                )
                _append_serper_prefetch_message(messages, tool_result, mode_used)
                print("[INFO chat] serper prefetch injected (model truly has no tools)", file=sys.stderr)

            available_tools = []
        except Exception as e:
            print(f"[WARN chat] serper prefetch failed: {e}", file=sys.stderr)

    try:
        if model.startswith("claude"):
            ai_model = AnthropicModel(model=model)
            print(f"[DEBUG chat] 使用 Anthropic: {model}", file=sys.stderr)
        elif model.startswith("deepseek"):
            ai_model = DeepSeekModel(model=model)
            print(f"[DEBUG chat] 使用 DeepSeek: {model}", file=sys.stderr)
        else:
            ai_model = OpenAIModel(model=model)
            print(f"[DEBUG chat] 使用 OpenAI: {model}", file=sys.stderr)

        if model.startswith("deepseek") or model.startswith("o1") or not available_tools:
            response = ai_model.chat(messages)
        else:
            response = ai_model.chat(messages, tools=available_tools)

        final_response = response

        if hasattr(response, "tool_calls") and response.tool_calls:
            print(f"[DEBUG chat] AI 请求调用 {len(response.tool_calls)} 个工具", file=sys.stderr)

            messages.append(
                {
                    "role": "assistant",
                    "content": getattr(response, "content", ""),
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments,
                            },
                        }
                        for tc in response.tool_calls
                    ],
                }
            )

            for tool_call in response.tool_calls:
                tool_name = tool_call.function.name
                tool_args_json = tool_call.function.arguments
                tool_call_id = _first_text(tool_call.id, f"tool_call_{len(tool_calls) + 1}")

                tool_result = run_tool(
                    tool_name,
                    tool_args_json,
                    user_ctx=user_ctx,
                    user_content=content,
                    mcp_overrides=mcp_overrides,
                ) or ""

                _append_tool_call_activity(
                    tool_calls,
                    tool_name,
                    tool_args_json,
                    status="done",
                    call_id=tool_call_id,
                )
                _append_tool_result_activity(
                    tool_results,
                    tool_name,
                    tool_result,
                    status="done",
                    result_id=tool_call_id,
                )

                if tool_name == "serper_search":
                    serper_called_this_turn = True
                    last_serper_tool_text = tool_result
                    if "serper_search" not in evidence_tools:
                        evidence_tools.append("serper_search")
                    evidence_result = {
                        **_safe_dict(evidence_result),
                        "serper_tool_call": True,
                        "serper_result": tool_result,
                    }

                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": tool_result,
                    }
                )
                print(f"[DEBUG chat] 工具结果: {tool_result[:120]}...", file=sys.stderr)

            print("[DEBUG chat] 将工具结果返回给 AI", file=sys.stderr)
            final_response = ai_model.chat(messages)

        response_text = (
            final_response
            if isinstance(final_response, str)
            else (final_response.content if hasattr(final_response, "content") else str(final_response))
        )
        response_text = _finalize_response_text("success", response_text, "")

        if serper_enabled and serper_called_this_turn and last_serper_tool_text:
            allowed_urls = _extract_urls(last_serper_tool_text)
            allowed_norm = set(_normalize_url(u) for u in allowed_urls)

            if allowed_norm:
                out_urls = _extract_urls(response_text)
                bad = [u for u in out_urls if _normalize_url(u) not in allowed_norm]

                if bad:
                    for u in bad:
                        response_text = response_text.replace(u, "[blocked]")

                    allow_lines = [f"- {u}" for u in allowed_urls[:12]]
                    allow_block = "\n".join(allow_lines).strip()

                    response_text = (
                        response_text.rstrip()
                        + "\n\n"
                        + "（链接审计）检测到回答中包含未出现在本次 Serper 结果里的链接，已自动屏蔽。\n"
                        + "本次允许引用的真实链接如下：\n"
                        + allow_block
                    )
                    print(f"[WARN chat] URL whitelist soft-blocked: {bad}", file=sys.stderr)

        ai_turn = {
            "sequence": len(history_messages) + 2,
            "turn_type": "assistant",
            "content": response_text,
            "timestamp": datetime.now().isoformat(),
            "model": model,
            "request_id": request_id,
            "conv_id": conv_id,
            "rag_mode": rag_mode,
            "mode_used": mode_used,
            "mcp_overrides": mcp_overrides,
            "capability_gate": capability_gate,
            "citations": citations,
            "rss_evidence": rss_evidence,
            "market_evidence": market_evidence,
            "evidence_query": evidence_query,
            "evidence_tools": evidence_tools,
            "evidence_result": evidence_result,
            "qa_id": qa_id,
            "group_id": group_id,
            "tool_calls": _normalize_tool_calls(tool_calls),
            "tool_results": _normalize_tool_results(tool_results),
        }

        try:
            ai_turn["embedding"] = get_embedding(response_text)
            print("[DEBUG chat] AI 响应向量化成功", file=sys.stderr)
        except Exception as e:
            print(f"[WARN chat] AI 响应向量化失败: {e}", file=sys.stderr)

        append_turn_record(conv_dir, ai_turn)

        meta = load_conversation_meta(conv_dir)
        meta["turn_count"] = len(history_messages) + 2
        meta["last_updated"] = datetime.now().isoformat()
        save_conversation_meta(conv_dir, meta)

        turn_index = int(meta.get("turn_count") or 0) // 2
        index_model = "gpt-4o-mini"

        thread = threading.Thread(
            target=_async_indexing_and_hebbian,
            args=(
                conv_dir,
                turn_index,
                content,
                response_text,
                index_model,
                user_ctx.base,
                concept_language,
                concept_backend,
            ),
            daemon=True,
        )
        thread.start()
        print("[INFO chat] 索引和 Hebbian 已提交到后台", file=sys.stderr)

        return _build_standard_result(
            status="success",
            request_id=request_id,
            conv_id=conv_id,
            rag_mode=rag_mode,
            mcp_overrides=mcp_overrides,
            mode_used=mode_used,
            response=response_text,
            citations=citations,
            rss_evidence=rss_evidence,
            market_evidence=market_evidence,
            evidence_query=evidence_query,
            evidence_tools=evidence_tools,
            evidence_result=evidence_result,
            qa_id=qa_id,
            group_id=group_id,
            tool_calls=tool_calls,
            tool_results=tool_results,
            message="✅ 对话已保存并向量化（索引与进脑在后台执行）",
        )

    except Exception as e:
        import traceback
        traceback.print_exc()
        return _build_standard_result(
            status="error",
            request_id=request_id,
            conv_id=conv_id,
            rag_mode=rag_mode,
            mcp_overrides=mcp_overrides,
            mode_used=mode_used,
            citations=citations,
            rss_evidence=rss_evidence,
            market_evidence=market_evidence,
            evidence_query=evidence_query,
            evidence_tools=evidence_tools,
            evidence_result=evidence_result,
            qa_id=qa_id,
            group_id=group_id,
            tool_calls=tool_calls,
            tool_results=tool_results,
            message=f"❌ AI 调用失败: {str(e)}",
        )

