from __future__ import annotations

import json
import os
import secrets
import tempfile
import time
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Generator, Iterable, List, Optional, Tuple

from tools.chat.chat_orchestrator import nisb_chat_orchestrate

try:
    from tools.chat import nisb_chat_create
except Exception:
    nisb_chat_create = None

try:
    from tools.chat.models.openai import OpenAIModel
except Exception:
    OpenAIModel = None

try:
    from tools.chat.models.anthropic import AnthropicModel
except Exception:
    AnthropicModel = None


_ALLOWED_RAG_MODES = {"off", "web", "auto", "cite", "ground"}


def _now_iso() -> str:
    return datetime.now().isoformat()


def _new_request_id() -> str:
    return f"req_{int(time.time() * 1000)}_{secrets.token_hex(4)}"


def _safe_str(v: Any, default: str = "") -> str:
    if v is None:
        return default
    return str(v)


def _safe_list(v: Any) -> List[Any]:
    return v if isinstance(v, list) else []


def _safe_dict(v: Any) -> Dict[str, Any]:
    return v if isinstance(v, dict) else {}


def _safe_bool(v: Any, default: bool = False) -> bool:
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return bool(v)
    if isinstance(v, str):
        s = v.strip().lower()
        if s in {"1", "true", "yes", "on"}:
            return True
        if s in {"0", "false", "no", "off"}:
            return False
    return default


def _normalize_arguments_inplace(arguments: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(arguments, dict):
        return {}

    if not _safe_str(arguments.get("request_id")).strip():
        legacy = _safe_str(arguments.get("requestid")).strip()
        if legacy:
            arguments["request_id"] = legacy

    if not _safe_str(arguments.get("conv_id")).strip():
        legacy = _safe_str(arguments.get("convid")).strip()
        if legacy:
            arguments["conv_id"] = legacy

    if not _safe_str(arguments.get("rag_mode")).strip():
        legacy = _safe_str(arguments.get("ragmode")).strip()
        if legacy:
            arguments["rag_mode"] = legacy

    if not isinstance(arguments.get("mcp_overrides"), dict):
        legacy = arguments.get("mcpoverrides")
        if isinstance(legacy, dict):
            arguments["mcp_overrides"] = dict(legacy)

    return arguments


def _chunk_text(text: str, size: int = 24) -> Iterable[str]:
    s = _safe_str(text, "")
    if not s:
        return []
    return [s[i:i + size] for i in range(0, len(s), size)]


def _short_json(value: Any, limit: int = 2200) -> str:
    try:
        s = json.dumps(value, ensure_ascii=False, indent=2)
    except Exception:
        s = _safe_str(value)
    if len(s) <= limit:
        return s
    return s[:limit] + "\n...truncated"


def _atomic_write_json(path: Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = tempfile.NamedTemporaryFile(mode="w", delete=False, encoding="utf-8", dir=str(path.parent))
    try:
        json.dump(data, tmp, ensure_ascii=False, indent=2)
        tmp.flush()
        os.fsync(tmp.fileno())
        tmp.close()
        os.replace(tmp.name, str(path))
    finally:
        try:
            if os.path.exists(tmp.name):
                os.unlink(tmp.name)
        except Exception:
            pass


def _append_jsonl(path: Path, row: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def _find_conv_dir(base_path: str, conv_id: str) -> Optional[Path]:
    if not base_path or not conv_id:
        return None
    root = Path(base_path) / "web_interactions" / "conversations"
    if not root.exists():
        return None
    for year_dir in root.glob("*"):
        if not year_dir.is_dir():
            continue
        for month_dir in year_dir.glob("*"):
            if not month_dir.is_dir():
                continue
            test_dir = month_dir / conv_id
            if test_dir.exists() and test_dir.is_dir():
                return test_dir
    return None


def _read_turns(conv_dir: Path) -> List[Dict[str, Any]]:
    turns_file = conv_dir / "turns.jsonl"
    out: List[Dict[str, Any]] = []
    if not turns_file.exists():
        return out
    with turns_file.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except Exception:
                continue
            if isinstance(row, dict):
                out.append(row)
    return out


def _update_conv_meta(conv_dir: Path, turn_count: int) -> None:
    meta_file = conv_dir / "conversation.json"
    if not meta_file.exists():
        return
    try:
        meta = json.loads(meta_file.read_text(encoding="utf-8"))
        if not isinstance(meta, dict):
            meta = {}
    except Exception:
        meta = {}
    meta["id"] = _safe_str(meta.get("id") or conv_dir.name)
    meta["title"] = _safe_str(meta.get("title"))
    meta["turn_count"] = int(turn_count)
    meta["last_updated"] = _now_iso()
    if "labels" not in meta or not isinstance(meta.get("labels"), list):
        meta["labels"] = []
    _atomic_write_json(meta_file, meta)


def _ensure_request_id(arguments: Dict[str, Any]) -> str:
    rid = _safe_str(arguments.get("request_id") or arguments.get("requestid") or "").strip()
    if rid:
        arguments["request_id"] = rid
        return rid
    rid = _new_request_id()
    arguments["request_id"] = rid
    return rid


def _ensure_conv_id(arguments: Dict[str, Any], request_id: str) -> str:
    conv_id = _safe_str(arguments.get("conv_id") or arguments.get("convid") or "").strip()
    if conv_id:
        arguments["conv_id"] = conv_id
        return conv_id

    if callable(nisb_chat_create):
        created = nisb_chat_create({
            "title": "",
            "request_id": request_id,
            "user_id": arguments.get("user_id") or arguments.get("_user_id"),
            "_user_id": arguments.get("_user_id") or arguments.get("user_id"),
            "base_path": arguments.get("base_path") or arguments.get("basepath") or "",
            "basepath": arguments.get("basepath") or arguments.get("base_path") or "",
            "token": arguments.get("token") or "",
        })
        if isinstance(created, dict):
            created_id = _safe_str(created.get("conv_id") or created.get("convid") or "").strip()
            if created_id:
                arguments["conv_id"] = created_id
                return created_id

    raise RuntimeError("create conversation failed")


def _build_history_messages(base_path: str, conv_id: str, user_content: str, max_history_turns: int = 12) -> List[Dict[str, str]]:
    messages: List[Dict[str, str]] = []
    conv_dir = _find_conv_dir(base_path, conv_id)
    if conv_dir is not None:
        turns = _read_turns(conv_dir)
        for turn in turns[-max_history_turns:]:
            turn_type = _safe_str(turn.get("turn_type") or turn.get("role") or "")
            content = _safe_str(turn.get("content") or "")
            if not content:
                continue
            if turn_type == "user":
                messages.append({"role": "user", "content": content})
            elif turn_type == "assistant":
                messages.append({"role": "assistant", "content": content})
    messages.append({"role": "user", "content": user_content})
    return messages


def _persist_stream_turns(
    base_path: str,
    conv_id: str,
    user_content: str,
    assistant_content: str,
    model: str,
    mode_used: str,
    request_id: str,
    final_payload: Dict[str, Any],
) -> None:
    conv_dir = _find_conv_dir(base_path, conv_id)
    if conv_dir is None:
        return

    turns = _read_turns(conv_dir)
    next_seq_user = len(turns) + 1
    next_seq_assistant = len(turns) + 2
    now_iso = _now_iso()

    citations = _safe_list(final_payload.get("citations"))
    rss_evidence = _safe_list(final_payload.get("rss_evidence"))
    market_evidence = _safe_list(final_payload.get("market_evidence"))
    evidence_query = _safe_str(final_payload.get("evidence_query"))
    evidence_tools = _safe_list(final_payload.get("evidence_tools"))
    evidence_result = _safe_dict(final_payload.get("evidence_result"))
    qa_debug = _safe_dict(final_payload.get("qa_debug"))
    qa_evidence = _safe_list(final_payload.get("qa_evidence"))
    tool_calls = _safe_list(final_payload.get("tool_calls"))
    tool_results = _safe_list(final_payload.get("tool_results"))

    user_turn = {
        "sequence": next_seq_user,
        "turn_type": "user",
        "content": user_content,
        "timestamp": now_iso,
        "mode_used": mode_used,
        "request_id": request_id,
        "conv_id": conv_id,
    }

    assistant_turn = {
        "sequence": next_seq_assistant,
        "turn_type": "assistant",
        "content": assistant_content,
        "timestamp": now_iso,
        "model": model,
        "mode_used": mode_used,
        "request_id": request_id,
        "conv_id": conv_id,
        "citations": citations,
        "rss_evidence": rss_evidence,
        "market_evidence": market_evidence,
        "evidence_query": evidence_query,
        "evidence_tools": evidence_tools,
        "evidence_result": evidence_result,
        "qa_debug": qa_debug,
        "qa_evidence": qa_evidence,
        "tool_calls": tool_calls,
        "tool_results": tool_results,
    }

    _append_jsonl(conv_dir / "turns.jsonl", user_turn)
    _append_jsonl(conv_dir / "turns.jsonl", assistant_turn)
    _update_conv_meta(conv_dir, next_seq_assistant)


def _resolve_effective_mode(arguments: Dict[str, Any]) -> str:
    rag_mode = _safe_str(arguments.get("rag_mode") or arguments.get("ragmode") or "off").strip().lower()
    if rag_mode not in _ALLOWED_RAG_MODES:
        rag_mode = "off"
    return rag_mode


def _read_path(obj: Any, *path: str) -> Any:
    cur = obj
    for key in path:
      if not isinstance(cur, dict):
          return None
      cur = cur.get(key)
    return cur


def _read_first_string(obj: Dict[str, Any], paths: List[Tuple[str, ...]]) -> str:
    for path in paths:
        value = _read_path(obj, *path)
        text = _safe_str(value).strip()
        if text:
            return text
    return ""


def _read_first_list(obj: Dict[str, Any], paths: List[Tuple[str, ...]]) -> List[Any]:
    for path in paths:
        value = _read_path(obj, *path)
        if isinstance(value, list):
            return value
    return []


def _read_first_dict(obj: Dict[str, Any], paths: List[Tuple[str, ...]]) -> Dict[str, Any]:
    for path in paths:
        value = _read_path(obj, *path)
        if isinstance(value, dict):
            return value
    return {}


def _extract_final_response(result: Dict[str, Any]) -> str:
    return _read_first_string(
        result,
        [
            ("response",),
            ("content",),
            ("answer",),
            ("text",),
            ("final_text",),
            ("assistant_response",),
            ("assistant", "response"),
            ("assistant", "content"),
            ("assistant", "answer"),
            ("data", "response"),
            ("data", "content"),
            ("data", "answer"),
            ("data", "text"),
            ("data", "final_text"),
            ("payload", "response"),
            ("payload", "content"),
            ("payload", "answer"),
            ("payload", "text"),
            ("result", "response"),
            ("result", "content"),
            ("result", "answer"),
            ("result", "text"),
        ],
    )


def _build_chat_payload(
    *,
    request_id: str,
    conv_id: str,
    rag_mode: str = "",
    mcp_overrides: Optional[Dict[str, Any]] = None,
    mode_used: str = "",
    rss_evidence: Optional[List[Any]] = None,
    market_evidence: Optional[List[Any]] = None,
    evidence_query: str = "",
    evidence_tools: Optional[List[Any]] = None,
    evidence_result: Optional[Dict[str, Any]] = None,
    qa_id: str = "",
    group_id: str = "",
    qa_debug: Optional[Dict[str, Any]] = None,
    qa_evidence: Optional[List[Any]] = None,
    params: Optional[Dict[str, Any]] = None,
    qa_params: Optional[Dict[str, Any]] = None,
    citations: Optional[List[Any]] = None,
    response: str = "",
    status: str = "",
    message: str = "",
    tool_calls: Optional[List[Any]] = None,
    tool_results: Optional[List[Any]] = None,
    **extra: Any,
) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "request_id": _safe_str(request_id).strip(),
        "conv_id": _safe_str(conv_id).strip(),
        "rag_mode": _safe_str(rag_mode).strip().lower(),
        "mcp_overrides": _safe_dict(mcp_overrides),
        "mode_used": _safe_str(mode_used).strip(),
        "rss_evidence": _safe_list(rss_evidence),
        "market_evidence": _safe_list(market_evidence),
        "evidence_query": _safe_str(evidence_query),
        "evidence_tools": _safe_list(evidence_tools),
        "evidence_result": _safe_dict(evidence_result),
        "qa_id": _safe_str(qa_id),
        "group_id": _safe_str(group_id),
        "qa_debug": _safe_dict(qa_debug),
        "qa_evidence": _safe_list(qa_evidence),
        "params": _safe_dict(params),
        "qa_params": _safe_dict(qa_params),
        "citations": _safe_list(citations),
        "response": _safe_str(response),
        "status": _safe_str(status),
        "message": _safe_str(message),
        "tool_calls": _safe_list(tool_calls),
        "tool_results": _safe_list(tool_results),
    }
    if payload["rag_mode"] not in _ALLOWED_RAG_MODES:
        payload["rag_mode"] = "off" if payload["rag_mode"] else ""
    for key, value in extra.items():
        payload[key] = value
    return payload


def _emit_meta(event: str, data: Dict[str, Any]) -> Dict[str, Any]:
    return {"event": event, "data": data}


def _emit_status(
    request_id: str,
    conv_id: str,
    message: str,
    *,
    rag_mode: str = "",
    mcp_overrides: Optional[Dict[str, Any]] = None,
    mode_used: str = "",
    status: str = "progress",
) -> Dict[str, Any]:
    return _emit_meta(
        "meta",
        _build_chat_payload(
            request_id=request_id,
            conv_id=conv_id,
            rag_mode=rag_mode,
            mcp_overrides=mcp_overrides,
            mode_used=mode_used,
            status=status,
            message=message,
        ),
    )


def _emit_delta(
    request_id: str,
    conv_id: str,
    text: str,
    *,
    rag_mode: str = "",
    mcp_overrides: Optional[Dict[str, Any]] = None,
    mode_used: str = "",
) -> Dict[str, Any]:
    return _emit_meta(
        "delta",
        _build_chat_payload(
            request_id=request_id,
            conv_id=conv_id,
            rag_mode=rag_mode,
            mcp_overrides=mcp_overrides,
            mode_used=mode_used,
            response=text,
            status="streaming",
            message="",
        ),
    )


def _emit_tool_call(
    request_id: str,
    conv_id: str,
    tool_call_id: str,
    name: str,
    arguments: Any,
    *,
    rag_mode: str = "",
    mcp_overrides: Optional[Dict[str, Any]] = None,
    mode_used: str = "",
    status: str = "running",
    reason: str = "",
    note: str = "",
) -> Dict[str, Any]:
    return _emit_meta(
        "tool_call",
        _build_chat_payload(
            request_id=request_id,
            conv_id=conv_id,
            rag_mode=rag_mode,
            mcp_overrides=mcp_overrides,
            mode_used=mode_used,
            status=status,
            message="",
            id=_safe_str(tool_call_id),
            name=_safe_str(name),
            arguments=arguments if isinstance(arguments, (dict, list, str, int, float, bool)) or arguments is None else _safe_str(arguments),
            arguments_preview=_short_json(arguments, limit=1600),
            reason=_safe_str(reason),
            note=_safe_str(note),
        ),
    )


def _emit_tool_result(
    request_id: str,
    conv_id: str,
    tool_call_id: str,
    name: str,
    result: Any,
    *,
    rag_mode: str = "",
    mcp_overrides: Optional[Dict[str, Any]] = None,
    mode_used: str = "",
    preview: str = "",
    status: str = "done",
) -> Dict[str, Any]:
    return _emit_meta(
        "tool_result",
        _build_chat_payload(
            request_id=request_id,
            conv_id=conv_id,
            rag_mode=rag_mode,
            mcp_overrides=mcp_overrides,
            mode_used=mode_used,
            status=status,
            message="",
            id=_safe_str(tool_call_id),
            name=_safe_str(name),
            result=result if isinstance(result, (dict, list, str, int, float, bool)) or result is None else _safe_str(result),
            preview=preview or _short_json(result, limit=1800),
        ),
    )


def _emit_error(
    request_id: str,
    conv_id: str,
    message: str,
    *,
    rag_mode: str = "",
    mcp_overrides: Optional[Dict[str, Any]] = None,
    mode_used: str = "",
) -> Dict[str, Any]:
    return _emit_meta(
        "error",
        _build_chat_payload(
            request_id=request_id,
            conv_id=conv_id,
            rag_mode=rag_mode,
            mcp_overrides=mcp_overrides,
            mode_used=mode_used,
            status="error",
            message=message,
        ),
    )


def _emit_final(payload: Dict[str, Any]) -> Dict[str, Any]:
    return _emit_meta("final", payload)


def _model_supports_true_stream(model_name: str, rag_mode: str) -> bool:
    m = _safe_str(model_name).lower()
    if rag_mode != "off":
        return False
    if m.startswith("deepseek") or m.startswith("o1"):
        return False
    if m.startswith("claude"):
        return AnthropicModel is not None
    return OpenAIModel is not None


def _build_model(model_name: str):
    m = _safe_str(model_name).lower()
    if m.startswith("claude"):
        if AnthropicModel is None:
            raise RuntimeError("AnthropicModel unavailable")
        return AnthropicModel(model=model_name)
    if OpenAIModel is None:
        raise RuntimeError("OpenAIModel unavailable")
    return OpenAIModel(model=model_name)


def _extract_stream_text_chunk(item: Any) -> str:
    if item is None:
        return ""
    if isinstance(item, str):
        return item
    if isinstance(item, dict):
        for key in ("response", "text", "delta", "content"):
            if item.get(key):
                return _safe_str(item.get(key))
        return ""
    if hasattr(item, "response") and getattr(item, "response"):
        return _safe_str(getattr(item, "response"))
    if hasattr(item, "text") and getattr(item, "text"):
        return _safe_str(getattr(item, "text"))
    if hasattr(item, "delta") and getattr(item, "delta"):
        return _safe_str(getattr(item, "delta"))
    if hasattr(item, "content") and getattr(item, "content"):
        return _safe_str(getattr(item, "content"))
    return ""


def _iter_wrapper_stream(wrapper: Any, messages: List[Dict[str, str]]) -> Generator[str, None, str]:
    full_text = ""

    if hasattr(wrapper, "chat_stream"):
        stream = wrapper.chat_stream(messages)
        for item in stream:
            chunk = _extract_stream_text_chunk(item)
            if chunk:
                full_text += chunk
                yield chunk
        return full_text

    if hasattr(wrapper, "stream_chat"):
        stream = wrapper.stream_chat(messages)
        for item in stream:
            chunk = _extract_stream_text_chunk(item)
            if chunk:
                full_text += chunk
                yield chunk
        return full_text

    if hasattr(wrapper, "chat"):
        resp = wrapper.chat(messages)
        if isinstance(resp, str):
            full_text = resp
        elif hasattr(resp, "content"):
            full_text = _safe_str(resp.content)
        else:
            full_text = _safe_str(resp)
        if full_text:
            yield full_text
        return full_text

    raise RuntimeError("model wrapper has no chat_stream/stream_chat/chat")


def _normalize_explicit_tool_calls(raw_calls: Any) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for idx, item in enumerate(_safe_list(raw_calls), start=1):
        if not isinstance(item, dict):
            continue
        out.append({
            "id": _safe_str(item.get("id") or f"tool_call_{idx}"),
            "name": _safe_str(item.get("name") or item.get("tool_name") or "unknown_tool"),
            "arguments": item.get("arguments") or item.get("args") or {},
            "status": _safe_str(item.get("status") or "done"),
            "reason": _safe_str(item.get("reason") or ""),
            "note": _safe_str(item.get("note") or ""),
        })
    return out


def _normalize_explicit_tool_results(raw_results: Any) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for idx, item in enumerate(_safe_list(raw_results), start=1):
        if not isinstance(item, dict):
            continue
        result_data = item.get("result")
        if result_data is None:
            result_data = item.get("output")
        out.append({
            "id": _safe_str(item.get("id") or f"tool_call_{idx}"),
            "name": _safe_str(item.get("name") or item.get("tool_name") or "unknown_tool"),
            "result": result_data,
            "preview": _safe_str(item.get("preview") or item.get("result_preview") or item.get("resultpreview") or ""),
            "status": _safe_str(item.get("status") or "done"),
        })
    return out


def _normalize_final_payload(result: Dict[str, Any], request_id: str, conv_id: str) -> Dict[str, Any]:
    rag_mode = _read_first_string(
        result,
        [
            ("rag_mode",),
            ("ragmode",),
            ("data", "rag_mode"),
            ("data", "ragmode"),
        ],
    ).lower()
    if rag_mode not in _ALLOWED_RAG_MODES:
        rag_mode = _resolve_effective_mode(result)

    mcp_overrides = _read_first_dict(
        result,
        [
            ("mcp_overrides",),
            ("mcpoverrides",),
            ("data", "mcp_overrides"),
            ("data", "mcpoverrides"),
        ],
    )

    explicit_tool_calls = _normalize_explicit_tool_calls(
        _read_path(result, "tool_calls")
        or _read_path(result, "toolcalls")
        or _read_path(result, "data", "tool_calls")
        or _read_path(result, "data", "toolcalls")
    )
    explicit_tool_results = _normalize_explicit_tool_results(
        _read_path(result, "tool_results")
        or _read_path(result, "toolresults")
        or _read_path(result, "data", "tool_results")
        or _read_path(result, "data", "toolresults")
    )

    params_payload = _read_first_dict(
        result,
        [
            ("params",),
            ("data", "params"),
        ],
    )
    qa_params_payload = _read_first_dict(
        result,
        [
            ("qa_params",),
            ("qaparams",),
            ("data", "qa_params"),
            ("data", "qaparams"),
        ],
    )

    if not params_payload and qa_params_payload:
        params_payload = dict(qa_params_payload)
    if not qa_params_payload and params_payload:
        qa_params_payload = dict(params_payload)

    return _build_chat_payload(
        status=_read_first_string(result, [("status",), ("data", "status")]) or "success",
        request_id=_read_first_string(
            result,
            [("request_id",), ("requestid",), ("data", "request_id"), ("data", "requestid")],
        ) or request_id,
        conv_id=_read_first_string(
            result,
            [("conv_id",), ("convid",), ("data", "conv_id"), ("data", "convid")],
        ) or conv_id,
        rag_mode=rag_mode,
        mcp_overrides=_safe_dict(mcp_overrides),
        response=_extract_final_response(result),
        message=_read_first_string(result, [("message",), ("data", "message")]),
        mode_used=_read_first_string(
            result,
            [("mode_used",), ("modeused",), ("data", "mode_used"), ("data", "modeused")],
        ),
        citations=_read_first_list(result, [("citations",), ("data", "citations")]),
        rss_evidence=_read_first_list(
            result,
            [("rss_evidence",), ("rssevidence",), ("data", "rss_evidence"), ("data", "rssevidence")],
        ),
        market_evidence=_read_first_list(
            result,
            [("market_evidence",), ("marketevidence",), ("data", "market_evidence"), ("data", "marketevidence")],
        ),
        evidence_query=_read_first_string(
            result,
            [("evidence_query",), ("evidencequery",), ("data", "evidence_query"), ("data", "evidencequery")],
        ),
        evidence_tools=_read_first_list(
            result,
            [("evidence_tools",), ("evidencetools",), ("data", "evidence_tools"), ("data", "evidencetools")],
        ),
        evidence_result=_read_first_dict(
            result,
            [("evidence_result",), ("evidenceresult",), ("data", "evidence_result"), ("data", "evidenceresult")],
        ),
        qa_id=_read_first_string(result, [("qa_id",), ("qaid",), ("data", "qa_id"), ("data", "qaid")]),
        group_id=_read_first_string(result, [("group_id",), ("groupid",), ("data", "group_id"), ("data", "groupid")]),
        qa_debug=_read_first_dict(
            result,
            [("qa_debug",), ("qadebug",), ("data", "qa_debug"), ("data", "qadebug")],
        ),
        qa_evidence=_read_first_list(
            result,
            [("qa_evidence",), ("qaevidence",), ("data", "qa_evidence"), ("data", "qaevidence")],
        ),
        params=params_payload,
        qa_params=qa_params_payload,
        tool_calls=explicit_tool_calls,
        tool_results=explicit_tool_results,
    )


def _abort_requested(abort_event: Any) -> bool:
    try:
        return bool(abort_event is not None and getattr(abort_event, "is_set", lambda: False)())
    except Exception:
        return False


def _build_agent_trace_tool_activity(agent_trace: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    tool_calls: List[Dict[str, Any]] = []
    tool_results: List[Dict[str, Any]] = []

    if not isinstance(agent_trace, dict) or not agent_trace:
        return tool_calls, tool_results

    plan = _safe_dict(agent_trace.get("plan"))
    planned_calls = _safe_list(plan.get("tool_calls") or plan.get("toolcalls"))
    trace_results = _safe_list(agent_trace.get("tool_results") or agent_trace.get("toolresults"))

    for idx, call in enumerate(planned_calls, start=1):
        if not isinstance(call, dict):
            continue
        tool_call_id = _safe_str(call.get("id") or f"agent_tool_call_{idx}")
        tool_name = _safe_str(call.get("name") or call.get("tool_name") or "unknown_tool").strip() or "unknown_tool"
        tool_args = call.get("arguments") or call.get("args") or {}
        tool_calls.append({
            "id": tool_call_id,
            "name": tool_name,
            "arguments": tool_args,
            "status": "done" if idx <= len(trace_results) else "running",
            "reason": _safe_str(call.get("reason")),
            "note": _safe_str(call.get("note")),
        })

    for idx, item in enumerate(trace_results, start=1):
        if not isinstance(item, dict):
            continue
        tool_call_id = _safe_str(item.get("id") or f"agent_tool_call_{idx}")
        tool_name = _safe_str(item.get("name") or item.get("tool_name") or "unknown_tool").strip() or "unknown_tool"
        result_preview = _safe_str(item.get("result_preview") or item.get("resultpreview") or "")
        result_data = item.get("result")
        if result_data is None:
            result_data = {
                "ok": _safe_bool(item.get("ok"), default=True),
                "status": _safe_str(item.get("status") or ""),
                "arguments": item.get("arguments") or {},
                "result_preview": result_preview,
            }
        tool_results.append({
            "id": tool_call_id,
            "name": tool_name,
            "result": result_data,
            "preview": result_preview,
            "status": "done" if _safe_bool(item.get("ok"), default=True) else "error",
        })

    if not tool_calls and tool_results:
        for idx, item in enumerate(tool_results, start=1):
            tool_calls.append({
                "id": _safe_str(item.get("id") or f"agent_tool_call_{idx}"),
                "name": _safe_str(item.get("name") or "unknown_tool"),
                "arguments": {},
                "status": "done",
                "reason": "",
                "note": "",
            })

    return tool_calls, tool_results


def _build_synthetic_evidence_tool_activity(
    normalized_payload: Dict[str, Any],
    arguments: Dict[str, Any],
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    tool_calls: List[Dict[str, Any]] = []
    tool_results: List[Dict[str, Any]] = []

    evidence_tools = [
        _safe_str(x).strip()
        for x in _safe_list(normalized_payload.get("evidence_tools"))
        if _safe_str(x).strip()
    ]
    if not evidence_tools:
        return tool_calls, tool_results

    arguments_hint = {
        "library_id": _safe_str(arguments.get("library_id") or arguments.get("libraryid") or ""),
        "doc_id": _safe_str(arguments.get("doc_id") or arguments.get("docid") or ""),
        "qa_store_scope": _safe_str(arguments.get("qa_store_scope") or arguments.get("qastorescope") or ""),
        "qa_evidence_scope": _safe_str(arguments.get("qa_evidence_scope") or arguments.get("qaevidencescope") or ""),
        "rag_mode": _safe_str(arguments.get("rag_mode") or arguments.get("ragmode") or ""),
    }
    arguments_hint = {k: v for k, v in arguments_hint.items() if v}

    evidence_result = _safe_dict(normalized_payload.get("evidence_result"))
    citations = _safe_list(normalized_payload.get("citations"))
    rss_evidence = _safe_list(normalized_payload.get("rss_evidence"))
    market_evidence = _safe_list(normalized_payload.get("market_evidence"))

    preview_lines = [
        f"citations={len(citations)}",
        f"rss_evidence={len(rss_evidence)}",
        f"market_evidence={len(market_evidence)}",
    ]
    if evidence_result:
        preview_lines.append(_short_json(evidence_result, limit=1200))

    for idx, tool_name in enumerate(evidence_tools, start=1):
        tool_call_id = f"evidence_tool_call_{idx}"
        tool_calls.append({
            "id": tool_call_id,
            "name": tool_name,
            "arguments": arguments_hint,
            "status": "done",
            "reason": "derived_from_final_payload",
            "note": "",
        })
        tool_results.append({
            "id": tool_call_id,
            "name": tool_name,
            "result": {
                "citations_count": len(citations),
                "rss_evidence_count": len(rss_evidence),
                "market_evidence_count": len(market_evidence),
                "evidence_result": evidence_result,
            },
            "preview": "\n".join(preview_lines),
            "status": "done",
        })

    return tool_calls, tool_results


def _build_tool_activity(
    result: Dict[str, Any],
    normalized_payload: Dict[str, Any],
    arguments: Dict[str, Any],
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    explicit_tool_calls = _normalize_explicit_tool_calls(result.get("tool_calls") or result.get("toolcalls"))
    explicit_tool_results = _normalize_explicit_tool_results(result.get("tool_results") or result.get("toolresults"))

    if explicit_tool_calls or explicit_tool_results:
        return explicit_tool_calls, explicit_tool_results

    payload_tool_calls = _normalize_explicit_tool_calls(normalized_payload.get("tool_calls"))
    payload_tool_results = _normalize_explicit_tool_results(normalized_payload.get("tool_results"))
    if payload_tool_calls or payload_tool_results:
        return payload_tool_calls, payload_tool_results

    agent_trace = _safe_dict(result.get("agent_trace") or result.get("agenttrace"))
    tool_calls, tool_results = _build_agent_trace_tool_activity(agent_trace)

    if tool_calls or tool_results:
        return tool_calls, tool_results

    return _build_synthetic_evidence_tool_activity(normalized_payload, arguments)


def _has_nonempty_arg(arguments: Dict[str, Any], key: str) -> bool:
    value = arguments.get(key)
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, tuple, set, dict)):
        return len(value) > 0
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    return True


def _is_true_flag(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on", "enable", "enabled"}
    return False


def _has_explicit_attachment_selection(arguments: Dict[str, Any]) -> bool:
    keys = [
        "doc_id",
        "docid",
        "doc_ids",
        "docids",
        "selected_doc_ids",
        "selecteddocids",
        "attachment_id",
        "attachmentid",
        "attachment_ids",
        "attachmentids",
        "selected_attachments",
        "selectedattachments",
        "file_id",
        "fileid",
        "file_ids",
        "fileids",
        "selected_files",
        "selectedfiles",
        "asset_id",
        "assetid",
        "asset_ids",
        "assetids",
        "attachments",
    ]
    for key in keys:
        if _has_nonempty_arg(arguments, key):
            return True
    return False


def _has_explicit_serper_request(arguments: Dict[str, Any]) -> bool:
    overrides = arguments.get("mcp_overrides")
    if not isinstance(overrides, dict):
        overrides = arguments.get("mcpoverrides")
    overrides = _safe_dict(overrides)

    top_level_flags = [
        "serper_enabled",
        "enable_serper",
        "use_serper",
    ]
    override_flags = [
        "serper_enabled",
        "enable_serper",
        "use_serper",
    ]
    provider_keys = [
        "search_provider",
        "web_search_provider",
    ]

    for key in top_level_flags:
        if _is_true_flag(arguments.get(key)):
            return True

    for key in override_flags:
        if _is_true_flag(overrides.get(key)):
            return True

    for key in provider_keys:
        if _safe_str(overrides.get(key)).strip().lower() == "serper":
            return True

    return False


def _should_force_orchestrator(arguments: Dict[str, Any]) -> bool:
    if _has_explicit_serper_request(arguments):
        return True
    if _has_explicit_attachment_selection(arguments):
        return True
    return False


def _stream_off_mode_direct(arguments: Dict[str, Any], abort_event: Any) -> Generator[Dict[str, Any], None, None]:
    request_id = _ensure_request_id(arguments)
    base_path = _safe_str(arguments.get("base_path") or arguments.get("basepath") or "")
    content = _safe_str(arguments.get("content") or "").strip()
    model_name = _safe_str(arguments.get("model") or "gpt-4o-mini").strip() or "gpt-4o-mini"
    mode_used = "off"
    rag_mode = "off"
    mcp_overrides = _safe_dict(arguments.get("mcp_overrides"))

    if not content:
        yield _emit_error(request_id, "", "content is required", rag_mode=rag_mode, mcp_overrides=mcp_overrides, mode_used=mode_used)
        return

    conv_id = _ensure_conv_id(arguments, request_id)

    yield _emit_status(
        request_id,
        conv_id,
        "正在生成回答...",
        rag_mode=rag_mode,
        mcp_overrides=mcp_overrides,
        mode_used=mode_used,
    )

    messages = _build_history_messages(base_path=base_path, conv_id=conv_id, user_content=content)
    wrapper = _build_model(model_name)
    response_text = ""

    for chunk in _iter_wrapper_stream(wrapper, messages):
        if _abort_requested(abort_event):
            return
        if not chunk:
            continue
        response_text += chunk
        yield _emit_delta(
            request_id,
            conv_id,
            chunk,
            rag_mode=rag_mode,
            mcp_overrides=mcp_overrides,
            mode_used=mode_used,
        )

    final_payload = _build_chat_payload(
        status="success",
        request_id=request_id,
        conv_id=conv_id,
        rag_mode=rag_mode,
        mcp_overrides=mcp_overrides,
        response=response_text,
        message="",
        mode_used=mode_used,
        citations=[],
        rss_evidence=[],
        market_evidence=[],
        evidence_query="",
        evidence_tools=[],
        evidence_result={},
        qa_id="",
        group_id="",
        tool_calls=[],
        tool_results=[],
    )

    _persist_stream_turns(
        base_path=base_path,
        conv_id=conv_id,
        user_content=content,
        assistant_content=response_text,
        model=model_name,
        mode_used=mode_used,
        request_id=request_id,
        final_payload=final_payload,
    )

    yield _emit_final(final_payload)


def _pseudo_stream_sync_result(
    result: Dict[str, Any],
    request_id: str,
    conv_id: str,
    abort_event: Any,
    arguments: Optional[Dict[str, Any]] = None,
) -> Generator[Dict[str, Any], None, None]:
    args = arguments if isinstance(arguments, dict) else {}
    normalized_payload = _normalize_final_payload(result, request_id, conv_id)
    final_request_id = _safe_str(normalized_payload.get("request_id") or request_id)
    final_conv_id = _safe_str(normalized_payload.get("conv_id") or conv_id)
    final_rag_mode = _safe_str(normalized_payload.get("rag_mode") or _resolve_effective_mode(args))
    final_mcp_overrides = _safe_dict(normalized_payload.get("mcp_overrides"))
    mode_used = _safe_str(normalized_payload.get("mode_used") or "")

    tool_calls, tool_results = _build_tool_activity(result, normalized_payload, args)
    normalized_payload["tool_calls"] = tool_calls
    normalized_payload["tool_results"] = tool_results

    yield _emit_status(
        final_request_id,
        final_conv_id,
        "正在整理工具结果...",
        rag_mode=final_rag_mode,
        mcp_overrides=final_mcp_overrides,
        mode_used=mode_used,
    )

    for item in tool_calls:
        if _abort_requested(abort_event):
            return
        yield _emit_tool_call(
            request_id=final_request_id,
            conv_id=final_conv_id,
            tool_call_id=_safe_str(item.get("id") or ""),
            name=_safe_str(item.get("name") or "unknown_tool"),
            arguments=item.get("arguments") or {},
            rag_mode=final_rag_mode,
            mcp_overrides=final_mcp_overrides,
            mode_used=mode_used,
            status=_safe_str(item.get("status") or "done"),
            reason=_safe_str(item.get("reason") or ""),
            note=_safe_str(item.get("note") or ""),
        )

    for item in tool_results:
        if _abort_requested(abort_event):
            return
        yield _emit_tool_result(
            request_id=final_request_id,
            conv_id=final_conv_id,
            tool_call_id=_safe_str(item.get("id") or ""),
            name=_safe_str(item.get("name") or "unknown_tool"),
            result=item.get("result"),
            rag_mode=final_rag_mode,
            mcp_overrides=final_mcp_overrides,
            mode_used=mode_used,
            preview=_safe_str(item.get("preview") or ""),
            status=_safe_str(item.get("status") or "done"),
        )

    yield _emit_status(
        final_request_id,
        final_conv_id,
        "正在输出回答...",
        rag_mode=final_rag_mode,
        mcp_overrides=final_mcp_overrides,
        mode_used=mode_used,
    )

    response = _safe_str(normalized_payload.get("response") or "")
    for chunk in _chunk_text(response, size=24):
        if _abort_requested(abort_event):
            return
        yield _emit_delta(
            final_request_id,
            final_conv_id,
            chunk,
            rag_mode=final_rag_mode,
            mcp_overrides=final_mcp_overrides,
            mode_used=mode_used,
        )

    yield _emit_final(normalized_payload)


def stream_chat_tool(tool: str, arguments: Dict[str, Any], abort_event: Any = None) -> Generator[Dict[str, Any], None, None]:
    arguments = _normalize_arguments_inplace(dict(arguments or {}))
    request_id = _ensure_request_id(arguments)
    conv_id = _safe_str(arguments.get("conv_id") or arguments.get("convid") or "")
    rag_mode = _resolve_effective_mode(arguments)
    mcp_overrides = _safe_dict(arguments.get("mcp_overrides"))

    try:
        if tool not in {"nisb_chat_send", "nisb_chat_orchestrate"}:
            yield _emit_error(request_id, conv_id, f"stream not supported for tool: {tool}", rag_mode=rag_mode, mcp_overrides=mcp_overrides)
            return

        orchestrate_args = dict(arguments)

        if tool == "nisb_chat_send":
            orchestrate_args["rag_mode"] = "off"

        effective_mode = _resolve_effective_mode(orchestrate_args)
        model_name = _safe_str(orchestrate_args.get("model") or "gpt-4o-mini").strip() or "gpt-4o-mini"
        effective_overrides = _safe_dict(orchestrate_args.get("mcp_overrides"))

        if effective_mode == "off" and _model_supports_true_stream(model_name, effective_mode):
            if not _should_force_orchestrator(orchestrate_args):
                yield from _stream_off_mode_direct(orchestrate_args, abort_event)
                return

        yield _emit_status(
            request_id=request_id,
            conv_id=conv_id,
            message="正在执行编排与检索...",
            rag_mode=effective_mode or rag_mode,
            mcp_overrides=effective_overrides,
            mode_used=effective_mode or rag_mode,
        )

        if "agent_debug" not in orchestrate_args and "agentdebug" not in orchestrate_args:
            orchestrate_args["agent_debug"] = True

        result = nisb_chat_orchestrate(orchestrate_args)
        if not isinstance(result, dict):
            yield _emit_error(request_id, conv_id, f"unexpected result: {result}", rag_mode=effective_mode or rag_mode, mcp_overrides=effective_overrides)
            return

        if result.get("status") != "success":
            yield _emit_error(
                request_id=_safe_str(result.get("request_id") or result.get("requestid") or request_id),
                conv_id=_safe_str(result.get("conv_id") or result.get("convid") or conv_id),
                message=_safe_str(result.get("message") or "unknown error"),
                rag_mode=_safe_str(result.get("rag_mode") or result.get("ragmode") or effective_mode or rag_mode),
                mcp_overrides=_safe_dict(result.get("mcp_overrides") or result.get("mcpoverrides") or effective_overrides),
                mode_used=_safe_str(result.get("mode_used") or result.get("modeused") or effective_mode or rag_mode),
            )
            return

        final_conv_id = _safe_str(result.get("conv_id") or result.get("convid") or conv_id)
        final_request_id = _safe_str(result.get("request_id") or result.get("requestid") or request_id)

        yield from _pseudo_stream_sync_result(
            result=result,
            request_id=final_request_id,
            conv_id=final_conv_id,
            abort_event=abort_event,
            arguments=orchestrate_args,
        )

    except Exception as e:
        traceback.print_exc()
        yield _emit_error(request_id, conv_id, f"stream runtime failed: {e!r}", rag_mode=rag_mode, mcp_overrides=mcp_overrides)

