#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
OpenAI工具类（Phase 3.x-5.x）
提供：
- Embedding API 调用和批处理
- LLM 调用（用于概念抽取、索引生成等非对话场景）
"""

import os
import json
import openai
import numpy as np
from typing import List, Union, Optional, Dict, Any

# 从环境变量读取配置
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
EMBEDDING_MODEL = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")
EMBEDDING_DIMENSIONS = int(os.getenv("OPENAI_EMBEDDING_DIMENSIONS", 1536))  # ⭐ 默认1536

# 初始化OpenAI客户端（兼容旧版 openai 库用法）
if OPENAI_API_KEY:
    openai.api_key = OPENAI_API_KEY
else:
    print("⚠️  警告：OPENAI_API_KEY未设置，LLM/Embedding 功能将不可用")

def get_embedding(text: str) -> List[float]:
    if not OPENAI_API_KEY:
        raise Exception("❌ OPENAI_API_KEY未配置")

    try:
        response = openai.embeddings.create(
            model=EMBEDDING_MODEL,
            input=text,
            dimensions=EMBEDDING_DIMENSIONS
        )
        return response.data[0].embedding
    except Exception as e:
        print(f"❌ OpenAI Embedding API调用失败：{e}")
        raise

def get_embeddings_batch(texts: List[str]) -> np.ndarray:
    if not OPENAI_API_KEY:
        raise Exception("❌ OPENAI_API_KEY未配置")

    if len(texts) > 2048:
        raise ValueError(f"❌ 批量上限2048个，当前{len(texts)}个")

    try:
        response = openai.embeddings.create(
            model=EMBEDDING_MODEL,
            input=texts,
            dimensions=EMBEDDING_DIMENSIONS
        )
        embeddings = [item.embedding for item in sorted(response.data, key=lambda x: x.index)]
        return np.array(embeddings)
    except Exception as e:
        print(f"❌ OpenAI Embedding API批量调用失败：{e}")
        raise

def test_openai_connection() -> bool:
    try:
        test_text = "测试文本"
        embedding = get_embedding(test_text)
        print("✅ OpenAI连接成功")
        print(f"   模型：{EMBEDDING_MODEL}")
        print(f"   维度：{len(embedding)}")
        print(f"   API Key前缀：{OPENAI_API_KEY[:10]}..." if OPENAI_API_KEY else "   未配置")
        return True
    except Exception as e:
        print(f"❌ OpenAI连接失败：{e}")
        return False

def call_llm(
    model: str,
    prompt: Optional[str] = None,
    system_prompt: Optional[str] = None,
    user_prompt: Optional[str] = None,
    response_format: str = "text",
) -> Union[str, dict]:
    """
    - response_format="text": 返回 str
    - response_format="json": 返回 dict（解析失败会 raise；自动重试1次）
    """
    if not OPENAI_API_KEY:
        raise Exception("❌ OPENAI_API_KEY未配置")

    # messages：兼容新旧用法
    if user_prompt is not None or system_prompt is not None:
        sys_msg = system_prompt or "You are a helpful assistant."
        usr_msg = user_prompt or ""
    else:
        sys_msg = "You are a helpful assistant."
        usr_msg = prompt or ""

    want_json = response_format == "json"

    # JSON mode: response_format={"type":"json_object"} [web:626][web:620]
    req_response_format: Optional[Dict[str, Any]] = {"type": "json_object"} if want_json else None

    max_retries = 1 if want_json else 0
    last_preview = ""
    last_err: Optional[Exception] = None

    for attempt in range(max_retries + 1):
        try:
            sys2 = sys_msg
            if want_json and attempt > 0:
                sys2 += "\nIMPORTANT: Return STRICT valid JSON object only. No markdown. No code fences."

            kwargs: Dict[str, Any] = {
                "model": model,
                "messages": [
                    {"role": "system", "content": sys2},
                    {"role": "user", "content": usr_msg},
                ],
                "temperature": 0.2,
            }
            if req_response_format is not None:
                kwargs["response_format"] = req_response_format

            # 兼容：老 openai python 客户端可能不支持 response_format 参数
            try:
                resp = openai.chat.completions.create(**kwargs)
            except TypeError:
                kwargs.pop("response_format", None)
                resp = openai.chat.completions.create(**kwargs)

            content = resp.choices[0].message.content or ""
            last_preview = content[:900]

            if not want_json:
                return content

            try:
                parsed = json.loads(content)
            except Exception as e:
                raise ValueError(f"JSON_PARSE_FAILED: {e}; preview={last_preview}")

            if not isinstance(parsed, dict):
                raise ValueError(f"JSON_NOT_OBJECT: got {type(parsed).__name__}; preview={last_preview}")

            return parsed

        except Exception as e:
            last_err = e
            if attempt >= max_retries:
                raise Exception(f"❌ OpenAI call_llm failed: model={model}; error={e}") from e

    raise Exception(f"❌ OpenAI call_llm failed: model={model}; error={last_err}; preview={last_preview}")

__all__ = [
    'get_embedding',
    'get_embeddings_batch',
    'test_openai_connection',
    'call_llm',
    'EMBEDDING_DIMENSIONS',
]

