#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from core.openai_utils import call_llm
from .chat_orchestrator_mode import coerce_bool
from .models.registry import ModelRegistry


_AGENT_TOOL_ALLOWLIST: Dict[str, str] = {
    "nisb_smart_search": "跨模块智能检索(只读)",
    "nisb_unified_query": "统一查询(只读)",
    "nisb_search_cross_module": "跨模块语义搜索(只读)",
    "nisb_search_semantic": "语义搜索(只读)",
    "nisb_library_list": "列出所有库(只读)",
    "nisb_library_get_info": "获取库信息(只读)",
    "nisb_library_stats": "库统计(只读)",
    "nisb_doc_stats": "库内文档统计/列表(只读)",
    "nisb_doc_search": "文档搜索(只读)",
    "nisb_doc_search_hybrid": "混合搜索(只读)",
    "nisb_doc_search_with_filter": "带过滤的文档搜索(只读)",
    "nisb_doc_expand_enhanced": "扩展证据片段(只读)",
    "nisb_doc_recall": "文档召回(只读)",
    "nisb_library_doc_evidence": "库文档证据(只读)",
    "nisb_timeline_recent_activities": "最近活动(只读)",
    "nisb_timeline_heatmap_data": "热力图数据(只读)",
    "nisb_chat_history": "对话列表/历史(只读)",
    "nisb_chat_load": "加载对话(只读)",
}

_AGENT_TOOL_DENYLIST = {
    "nisb_chat_orchestrate",
    "nisb_chat_send",
    "nisb_chat_create",
    "nisb_execute_code",
    "nisb_dir_delete_recursive",
    "nisb_library_delete",
    "nisb_library_doc_delete",
    "nisb_library_doc_delete_batch",
    "nisb_fs_send_to_library",
    "nisb_fs_send_dir_to_library",
}

_MCP_ENTRY_FILE = Path(__file__).resolve().parents[2] / "nisb_mcp.py"
_MCP_TOOLS_CACHE: Optional[Dict[str, Any]] = None


def agent_enabled(args: Dict[str, Any]) -> bool:
    return coerce_bool(args.get("agent_enabled", False), default=False)


def agent_debug_enabled(args: Dict[str, Any]) -> bool:
    return coerce_bool(args.get("agent_debug", False), default=False)


def agent_answer_use_planner(args: Dict[str, Any]) -> bool:
    return coerce_bool(args.get("agent_answer_use_planner", False), default=False)


def _normalize_provider(value: Any) -> str:
    s = str(value or "").strip().lower()
    if s in {"openai", "anthropic", "deepseek"}:
        return s
    return ""


def _normalize_optional_float(value: Any) -> Optional[float]:
    s = str(value or "").strip()
    if not s:
        return None
    try:
        return float(s)
    except Exception:
        return None


def _normalize_optional_int(value: Any) -> Optional[int]:
    s = str(value or "").strip()
    if not s:
        return None
    try:
        return max(1, int(s))
    except Exception:
        return None


def pick_answer_model(*, top_model: str, effective_mode: str, args: Dict[str, Any]) -> str:
    if effective_mode not in ("off", "web"):
        return top_model
    if not agent_enabled(args):
        return top_model
    if not agent_answer_use_planner(args):
        return top_model
    planner_model = str(args.get("agent_planner_model") or "gpt-4o-mini").strip()
    return planner_model or top_model


def safe_json_dump(obj: Any, limit: int = 4000) -> str:
    try:
        text = json.dumps(obj, ensure_ascii=False, indent=2)
    except Exception:
        text = str(obj)
    if len(text) > limit:
        return text[:limit] + "\n...[truncated]"
    return text


def _extract_llm_text(result: Any) -> str:
    if result is None:
        return ""
    if isinstance(result, str):
        return result.strip()
    if isinstance(result, dict):
        for key in ("response", "answer", "content", "text", "output", "message"):
            value = result.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return str(result).strip()


def _extract_json_from_text(text: str) -> Dict[str, Any]:
    s = str(text or "").strip()
    if not s:
        raise ValueError("empty llm json text")

    if s.startswith("```"):
        lines = s.splitlines()
        if len(lines) >= 3:
            s = "\n".join(lines[1:-1]).strip()

    try:
        obj = json.loads(s)
        if isinstance(obj, dict):
            return obj
    except Exception:
        pass

    start = s.find("{")
    end = s.rfind("}")
    if start >= 0 and end > start:
        obj = json.loads(s[start:end + 1])
        if isinstance(obj, dict):
            return obj

    raise ValueError("llm json parse failed")


def _call_openai_json(
    *,
    model_name: str,
    user_prompt: str,
    system_prompt: str = "",
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
) -> Dict[str, Any]:
    kwargs: Dict[str, Any] = {
        "model": model_name,
        "user_prompt": user_prompt,
        "system_prompt": system_prompt,
        "response_format": "json",
    }
    if temperature is not None:
        kwargs["temperature"] = temperature
    if max_tokens is not None:
        kwargs["max_tokens"] = max_tokens

    try:
        result = call_llm(**kwargs)
    except TypeError:
        kwargs.pop("temperature", None)
        kwargs.pop("max_tokens", None)
        result = call_llm(**kwargs)

    if isinstance(result, dict):
        return result
    return _extract_json_from_text(_extract_llm_text(result))


def _call_anthropic_json(
    *,
    model_name: str,
    user_prompt: str,
    system_prompt: str = "",
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
) -> Dict[str, Any]:
    try:
        from anthropic import Anthropic
    except Exception as e:
        raise RuntimeError(f"anthropic_sdk_unavailable: {e}") from e

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("anthropic_api_key_missing")

    client = Anthropic(api_key=api_key)
    kwargs: Dict[str, Any] = {
        "model": model_name,
        "messages": [{"role": "user", "content": user_prompt}],
        "max_tokens": max_tokens or 2048,
    }
    if system_prompt:
        kwargs["system"] = system_prompt
    if temperature is not None:
        kwargs["temperature"] = max(0.0, min(1.0, float(temperature)))

    result = client.messages.create(**kwargs)

    text_blocks: List[str] = []
    for block in getattr(result, "content", []) or []:
        if getattr(block, "type", "") == "text":
            txt = getattr(block, "text", "")
            if txt:
                text_blocks.append(str(txt))
    text = "\n".join(text_blocks).strip()
    return _extract_json_from_text(text)


def _resolve_planner_runtime(
    *,
    planner_provider: str,
    planner_model: str,
    planner_temperature: Optional[float],
    planner_max_tokens: Optional[int],
) -> Dict[str, Any]:
    registry = ModelRegistry()
    resolved = registry.resolve_model_selection(
        requested_provider=planner_provider,
        requested_model=planner_model,
        default_provider="openai",
        default_model="gpt-4o-mini",
    )
    return {
        "requested_provider": planner_provider or resolved.get("requested_provider") or "",
        "requested_model": planner_model or resolved.get("requested_model") or "",
        "applied_provider": str(resolved.get("applied_provider") or "openai").strip() or "openai",
        "applied_model": str(resolved.get("applied_model") or "gpt-4o-mini").strip() or "gpt-4o-mini",
        "fallback_reason": str(resolved.get("fallback_reason") or "").strip(),
        "temperature": planner_temperature,
        "max_tokens": planner_max_tokens,
    }


def load_mcp_tools_registry() -> Dict[str, Any]:
    global _MCP_TOOLS_CACHE

    if isinstance(_MCP_TOOLS_CACHE, dict) and _MCP_TOOLS_CACHE:
        return _MCP_TOOLS_CACHE

    if not _MCP_ENTRY_FILE.exists():
        raise FileNotFoundError(f"MCP entry not found: {_MCP_ENTRY_FILE}")

    import importlib.util

    module_name = "_nisb_mcp_dynamic_registry"
    spec = importlib.util.spec_from_file_location(module_name, str(_MCP_ENTRY_FILE))
    if spec is None or spec.loader is None:
        raise RuntimeError(f"spec_from_file_location failed: {_MCP_ENTRY_FILE}")

    mod = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = mod
    spec.loader.exec_module(mod)  # type: ignore[attr-defined]

    tools = getattr(mod, "TOOLS", None)
    if not isinstance(tools, dict):
        raise RuntimeError("TOOLS not found in nisb_mcp.py or not a dict")

    _MCP_TOOLS_CACHE = tools
    return tools


def call_tool_by_name(tool_name: str, tool_args: Dict[str, Any], base_args: Dict[str, Any]) -> Tuple[bool, Any, str]:
    if tool_name in _AGENT_TOOL_DENYLIST:
        return False, None, f"tool_denied: {tool_name}"
    if tool_name not in _AGENT_TOOL_ALLOWLIST:
        return False, None, f"tool_not_allowed: {tool_name}"

    try:
        registry = load_mcp_tools_registry()
        func = registry.get(tool_name)
        if not func:
            return False, None, f"tool_not_found_in_registry: {tool_name}"

        call_args = dict(tool_args or {})
        call_args["_mcp_mode"] = True
        call_args["_base_path"] = base_args.get("_base_path")

        res = func(call_args)
        return True, res, "ok"
    except Exception as e:
        return False, None, f"tool_call_failed: {tool_name}: {e}"


def build_agent_plan(
    *,
    question: str,
    rag_mode: str,
    qa_store_scope: str,
    qa_evidence_scope: str,
    library_id: Optional[str],
    doc_id: Optional[str],
    planner_model: str,
    planner_provider: str,
    planner_temperature: Optional[float],
    planner_max_tokens: Optional[int],
    max_steps: int,
) -> Dict[str, Any]:
    tool_list_lines = [f"- {name}: {desc}" for name, desc in _AGENT_TOOL_ALLOWLIST.items()]

    sys_prompt = (
        "You are NISB Agent Planner.\n"
        "Return STRICT JSON object only.\n"
        "Goal: decide whether to call some read-only tools to help answer the user's question.\n"
        "Constraints:\n"
        f"- You may call up to {max_steps} tools.\n"
        "- Only call tools from the provided allowlist.\n"
        "- Tool arguments must be a JSON object.\n"
        "- Prefer fewer tool calls.\n"
        "- If not needed, return empty tool_calls.\n"
    )

    user_prompt = (
        "Context:\n"
        f"- rag_mode: {rag_mode}\n"
        f"- qa_store_scope: {qa_store_scope}\n"
        f"- qa_evidence_scope: {qa_evidence_scope}\n"
        f"- library_id: {library_id or ''}\n"
        f"- doc_id: {doc_id or ''}\n\n"
        "Allowed tools:\n"
        + "\n".join(tool_list_lines)
        + "\n\nUser question:\n"
        + (question or "")
        + "\n\nReturn JSON with this schema:\n"
        "{\n"
        '  "tool_calls": [\n'
        '    {"name": "tool_name", "arguments": { }, "reason": "why"}\n'
        "  ],\n"
        '  "note": "optional short note"\n'
        "}\n"
    )

    runtime = _resolve_planner_runtime(
        planner_provider=planner_provider,
        planner_model=planner_model,
        planner_temperature=planner_temperature,
        planner_max_tokens=planner_max_tokens,
    )

    try:
        if runtime["applied_provider"] == "anthropic":
            plan = _call_anthropic_json(
                model_name=runtime["applied_model"],
                user_prompt=user_prompt,
                system_prompt=sys_prompt,
                temperature=runtime["temperature"],
                max_tokens=runtime["max_tokens"],
            )
        else:
            plan = _call_openai_json(
                model_name=runtime["applied_model"],
                user_prompt=user_prompt,
                system_prompt=sys_prompt,
                temperature=runtime["temperature"],
                max_tokens=runtime["max_tokens"],
            )
    except Exception as e:
        if runtime["applied_provider"] != "openai":
            fallback_runtime = _resolve_planner_runtime(
                planner_provider="openai",
                planner_model="gpt-4o-mini",
                planner_temperature=planner_temperature,
                planner_max_tokens=planner_max_tokens,
            )
            fallback_runtime["fallback_reason"] = runtime.get("fallback_reason") or f"planner_call_failed:{type(e).__name__}"
            plan = _call_openai_json(
                model_name=fallback_runtime["applied_model"],
                user_prompt=user_prompt,
                system_prompt=sys_prompt,
                temperature=fallback_runtime["temperature"],
                max_tokens=fallback_runtime["max_tokens"],
            )
            runtime = fallback_runtime
        else:
            raise

    if not isinstance(plan, dict):
        return {"tool_calls": [], "note": "planner_return_not_object", "_runtime": runtime}

    tool_calls = plan.get("tool_calls")
    if not isinstance(tool_calls, list):
        tool_calls = []
    plan["tool_calls"] = tool_calls[: max(0, int(max_steps))]
    plan["_runtime"] = runtime
    return plan


def run_agent_tools(*, args: Dict[str, Any], effective_mode: str) -> Tuple[str, Dict[str, Any]]:
    question = str(args.get("content") or "").strip()
    planner_model = str(args.get("agent_planner_model") or "gpt-4o-mini").strip()
    planner_provider = _normalize_provider(args.get("agent_planner_provider"))
    planner_temperature = _normalize_optional_float(args.get("agent_planner_temperature"))
    planner_max_tokens = _normalize_optional_int(args.get("agent_planner_max_tokens"))

    max_steps = int(args.get("agent_max_steps") or 3)
    max_steps = max(0, min(8, max_steps))

    qa_store_scope = str(args.get("qa_store_scope") or "global").strip().lower()
    qa_evidence_scope = str(args.get("qa_evidence_scope") or "global").strip().lower()
    library_id = str(args.get("library_id") or "").strip() or None
    doc_id = str(args.get("doc_id") or "").strip() or None

    trace: Dict[str, Any] = {
        "planner_provider": planner_provider,
        "planner_model": planner_model,
        "planner_temperature": planner_temperature,
        "planner_max_tokens": planner_max_tokens,
        "planner_runtime": {},
        "max_steps": max_steps,
        "mode_used": effective_mode,
        "plan": None,
        "tool_results": [],
    }

    try:
        plan = build_agent_plan(
            question=question,
            rag_mode=effective_mode,
            qa_store_scope=qa_store_scope,
            qa_evidence_scope=qa_evidence_scope,
            library_id=library_id,
            doc_id=doc_id,
            planner_model=planner_model,
            planner_provider=planner_provider,
            planner_temperature=planner_temperature,
            planner_max_tokens=planner_max_tokens,
            max_steps=max_steps,
        )
        trace["planner_runtime"] = plan.get("_runtime") or {}
        plan.pop("_runtime", None)
        trace["plan"] = plan
    except Exception as e:
        trace["plan"] = {"tool_calls": [], "note": f"planner_failed: {e}"}
        return "", trace

    tool_calls = (trace["plan"] or {}).get("tool_calls") or []
    if not isinstance(tool_calls, list) or not tool_calls:
        return "", trace

    obs_lines: List[str] = []

    for i, call in enumerate(tool_calls[:max_steps]):
        if not isinstance(call, dict):
            continue

        name = str(call.get("name") or "").strip()
        arguments = call.get("arguments") or {}
        if not isinstance(arguments, dict):
            arguments = {}

        ok, res, status = call_tool_by_name(name, arguments, base_args=args)

        item = {
            "i": i + 1,
            "name": name,
            "arguments": arguments,
            "ok": ok,
            "status": status,
        }
        if ok:
            item["result_preview"] = safe_json_dump(res, limit=2000)
        trace["tool_results"].append(item)

        if ok:
            obs_lines.append(f"[{i + 1}] tool={name} args={safe_json_dump(arguments, limit=400)}")
            obs_lines.append(item.get("result_preview") or "")
        else:
            obs_lines.append(f"[{i + 1}] tool={name} FAILED: {status}")

    observations = "\n".join([x for x in obs_lines if str(x).strip()]).strip()
    if not observations:
        return "", trace

    return ("\n\n【Agent 工具观察(只读工具输出)】\n" + observations + "\n"), trace
