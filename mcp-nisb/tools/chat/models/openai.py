#!/usr/bin/env python3
"""
OpenAI 模型封装（支持所有模型 + 工具调用 + Streaming）
"""

import os
from typing import Any, Dict, Iterator, List, Optional
from openai import OpenAI


class OpenAIModel:
    def __init__(self, model: str = "gpt-4o-mini"):
        self.model = model
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

        self.model_map = {
            "gpt-4": "gpt-4o",
            "gpt-4o": "gpt-4o",
            "gpt-4-mini": "gpt-4o-mini",
            "gpt-4o-mini": "gpt-4o-mini",
            "gpt-3.5": "gpt-3.5-turbo",
            "gpt-3.5-turbo": "gpt-3.5-turbo",
            "o1-preview": "o1-preview",
            "o1-mini": "o1-mini",
        }
        self.actual_model = self.model_map.get(model, model)

    def chat(self, messages, temperature: float = 0.7, max_tokens: int = 4000, tools=None):
        try:
            params: Dict[str, Any] = {"model": self.actual_model, "messages": messages}

            # o1 系列不支持 temperature/max_tokens/tools
            if self.actual_model.startswith("o1"):
                pass
            else:
                params["temperature"] = float(temperature)
                params["max_tokens"] = int(max_tokens)
                if tools:
                    params["tools"] = tools
                    params["tool_choice"] = "auto"

            response = self.client.chat.completions.create(**params)
            message = response.choices[0].message

            if message.tool_calls:
                return message
            return message.content
        except Exception as e:
            raise Exception(f"OpenAI API 调用失败: {str(e)}")

    def chat_stream(
        self,
        messages: List[Dict[str, Any]],
        temperature: float = 0.7,
        max_tokens: int = 4000,
    ) -> Iterator[str]:
        if self.actual_model.startswith("o1"):
            raise Exception("o1 models do not support streaming in this wrapper")

        params: Dict[str, Any] = {
            "model": self.actual_model,
            "messages": messages,
            "temperature": float(temperature),
            "max_tokens": int(max_tokens),
            "stream": True,
        }

        try:
            stream = self.client.chat.completions.create(**params)
            for chunk in stream:
                try:
                    delta = chunk.choices[0].delta
                    text = getattr(delta, "content", None)
                    if text:
                        yield text
                except Exception:
                    continue
        except Exception as e:
            raise Exception(f"OpenAI streaming 调用失败: {str(e)}")


__all__ = ["OpenAIModel"]


