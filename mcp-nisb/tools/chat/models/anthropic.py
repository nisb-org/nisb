#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Anthropic Claude 模型封装（支持工具调用 + 流式输出）

- 输入：沿用本项目 OpenAI 风格 messages + tools（function calling schema）
- 内部：转换为 Claude Messages API 的 tools/tool_use/tool_result 结构
- 输出：
  - chat(): 无 tool_use 返回 str；有 tool_use 返回 message-like（含 .content/.tool_calls）
  - chat_stream(): 返回一个迭代器，持续 yield 文本增量（仅文本，不包含 tool_use 增量）
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Tuple, Union

from anthropic import Anthropic


@dataclass
class _Fn:
    name: str
    arguments: str


@dataclass
class _ToolCall:
    id: str
    function: _Fn


class _Msg:
    def __init__(self, content: str = "", tool_calls: Optional[List[_ToolCall]] = None):
        self.content = content
        self.tool_calls = tool_calls or []


def _openai_tools_to_anthropic(tools: List[dict]) -> List[dict]:
    """
    OpenAI tools schema:
      {"type":"function","function":{"name","description","parameters":{...}}}

    Anthropic tools schema:
      {"name","description","input_schema":{...}}
    """
    out: List[dict] = []
    for t in tools or []:
        if not isinstance(t, dict):
            continue
        if t.get("type") != "function":
            continue
        fn = t.get("function") or {}
        if not isinstance(fn, dict):
            continue
        name = str(fn.get("name") or "").strip()
        if not name:
            continue
        desc = str(fn.get("description") or "").strip()
        params = fn.get("parameters") or {}
        if not isinstance(params, dict):
            params = {"type": "object", "properties": {}}
        out.append({"name": name, "description": desc, "input_schema": params})
    return out


def _split_system(messages: List[dict]) -> Tuple[str, List[dict]]:
    # Claude API 的 system 是 top-level string；把多个 system 拼起来
    sys_parts: List[str] = []
    rest: List[dict] = []
    for m in messages or []:
        role = m.get("role")
        if role == "system":
            c = m.get("content")
            if isinstance(c, str) and c.strip():
                sys_parts.append(c.strip())
        else:
            rest.append(m)
    return ("\n\n".join(sys_parts).strip(), rest)


def _to_claude_messages(openai_messages: List[dict]) -> List[dict]:
    """
    把项目里的 messages（含 role=tool, 以及 assistant.tool_calls）转换成 Claude Messages API 结构。

    规则要点：
    - tool_use 出现在 assistant content blocks
    - tool_result 必须出现在紧随其后的 user content blocks，且 user content 中不能在 tool_result 前放 text
    """
    out: List[dict] = []

    def _append_user_text(text: str) -> None:
        text = (text or "").strip()
        if not text:
            return
        out.append({"role": "user", "content": [{"type": "text", "text": text}]})

    def _append_assistant_text_and_tool_uses(text: str, tool_calls: List[dict]) -> None:
        blocks: List[dict] = []
        text = (text or "").strip()
        if text:
            blocks.append({"type": "text", "text": text})

        for tc in tool_calls or []:
            fn = (tc or {}).get("function") or {}
            tool_id = str((tc or {}).get("id") or "").strip()
            name = str(fn.get("name") or "").strip()
            args_raw = fn.get("arguments")
            if isinstance(args_raw, dict):
                tool_input = args_raw
            else:
                try:
                    tool_input = json.loads(args_raw or "{}")
                except Exception:
                    tool_input = {}
            if tool_id and name:
                blocks.append({"type": "tool_use", "id": tool_id, "name": name, "input": tool_input})

        out.append({"role": "assistant", "content": blocks})

    def _append_tool_result(tool_use_id: str, result_text: str) -> None:
        out.append(
            {
                "role": "user",
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": tool_use_id,
                        "content": (result_text or ""),
                    }
                ],
            }
        )

    for m in openai_messages or []:
        role = m.get("role")
        if role == "user":
            c = m.get("content")
            _append_user_text(c if isinstance(c, str) else str(c))
            continue

        if role == "assistant":
            c = m.get("content")
            tool_calls = m.get("tool_calls") or []
            _append_assistant_text_and_tool_uses(c if isinstance(c, str) else str(c), tool_calls)
            continue

        if role == "tool":
            tool_call_id = str(m.get("tool_call_id") or "").strip()
            content = m.get("content")
            _append_tool_result(tool_call_id, content if isinstance(content, str) else str(content))
            continue

        c = m.get("content")
        _append_user_text(c if isinstance(c, str) else str(c))

    return out


def _parse_claude_response(resp) -> _Msg:
    """
    resp.content 是一组 block：
    - {"type":"text","text":...}
    - {"type":"tool_use","id":...,"name":...,"input":{...}}
    """
    text_parts: List[str] = []
    tool_calls: List[_ToolCall] = []

    for b in getattr(resp, "content", []) or []:
        b_type = getattr(b, "type", None) or (b.get("type") if isinstance(b, dict) else None)
        if b_type == "text":
            t = getattr(b, "text", None) if not isinstance(b, dict) else b.get("text")
            if isinstance(t, str) and t.strip():
                text_parts.append(t)
        elif b_type == "tool_use":
            tool_id = getattr(b, "id", None) if not isinstance(b, dict) else b.get("id")
            name = getattr(b, "name", None) if not isinstance(b, dict) else b.get("name")
            tool_input = getattr(b, "input", None) if not isinstance(b, dict) else b.get("input")
            if tool_input is None:
                tool_input = {}
            args_str = json.dumps(tool_input, ensure_ascii=False)
            tool_calls.append(_ToolCall(id=str(tool_id), function=_Fn(name=str(name), arguments=args_str)))

    return _Msg(content="".join(text_parts).strip(), tool_calls=tool_calls)


class AnthropicModel:
    def __init__(self, model: str = "claude-3-5-sonnet-20241022"):
        self.model = model
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise RuntimeError("缺少环境变量 ANTHROPIC_API_KEY")
        self.client = Anthropic(api_key=api_key)

        self.model_map = {
            "claude-3": "claude-3-5-sonnet-20241022",
            "claude-3.5": "claude-3-5-sonnet-20241022",
            "claude-3-sonnet": "claude-3-5-sonnet-20241022",
            "claude-3-5-sonnet": "claude-3-5-sonnet-20241022",
            "claude-3-haiku": "claude-3-5-haiku-20241022",
            "claude-3-5-haiku": "claude-3-5-haiku-20241022",
            "claude-3-opus": "claude-3-opus-20240229",
        }
        self.actual_model = self.model_map.get(model, model)

    def _build_params(
        self,
        messages: List[dict],
        temperature: float,
        max_tokens: int,
        tools: Optional[List[dict]],
    ) -> Dict[str, Any]:
        system_str, rest = _split_system(messages)
        claude_messages = _to_claude_messages(rest)

        params: Dict[str, Any] = {
            "model": self.actual_model,
            "max_tokens": int(max_tokens),
            "messages": claude_messages,
            "temperature": float(temperature),
        }
        if system_str:
            params["system"] = system_str
        if tools:
            params["tools"] = _openai_tools_to_anthropic(tools)
            params["tool_choice"] = {"type": "auto"}
        return params

    def chat(
        self,
        messages: List[dict],
        temperature: float = 0.7,
        max_tokens: int = 4000,
        tools: Optional[List[dict]] = None,
    ) -> Union[str, _Msg]:
        """
        与 OpenAIModel.chat 对齐：
        - 无 tool_use：返回 str
        - 有 tool_use：返回 message-like（带 .tool_calls）
        """
        try:
            params = self._build_params(messages, temperature=temperature, max_tokens=max_tokens, tools=tools)
            resp = self.client.messages.create(**params)
            msg = _parse_claude_response(resp)
            if msg.tool_calls:
                return msg
            return msg.content
        except Exception as e:
            raise Exception(f"Anthropic API 调用失败: {str(e)}")

    def chat_stream(
        self,
        messages: List[dict],
        temperature: float = 0.7,
        max_tokens: int = 4000,
        tools: Optional[List[dict]] = None,
    ) -> Iterable[str]:
        """
        流式输出：持续 yield 文本增量（text deltas）。[web:304][web:308]

        约束：
        - 本项目的“最终回答流式”通常发生在 tool loop 之后，所以这里按“只吐 text”设计。
        - 若 Claude 在流式中产出 tool_use 增量（input_json_delta），这里会忽略（因为最终回答阶段不应再调用工具）。[web:304]
        """
        params = self._build_params(messages, temperature=temperature, max_tokens=max_tokens, tools=tools)

        try:
            # 优先走 SDK 的 stream helper（它提供 text_stream 迭代器）[web:304][web:305]
            with self.client.messages.stream(**params) as stream:
                for t in stream.text_stream:
                    if t:
                        yield t
            return

        except Exception:
            # 兼容：退化到 create(stream=True) 的事件流（更底层）[web:308]
            stream_iter = self.client.messages.create(stream=True, **params)
            for ev in stream_iter:
                ev_type = getattr(ev, "type", None)
                if ev_type != "content_block_delta":
                    continue
                delta = getattr(ev, "delta", None)
                delta_type = getattr(delta, "type", None)
                if delta_type == "text_delta":
                    text = getattr(delta, "text", None)
                    if text:
                        yield text


__all__ = ["AnthropicModel"]

