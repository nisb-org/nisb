# /opt/mcp-gateway/mcp-nisb/tools/chat/indexing.py
"""
对话索引生成：
- 一级索引：这一轮的标题（Topic Title）
- 二级索引：这一轮的关键要点列表（Key Points）+ embedding
"""

import json
from datetime import datetime
from pathlib import Path
from typing import List

from core.openai_utils import call_llm, get_embedding


def _append_jsonl(path: Path, record: dict) -> None:
  path.parent.mkdir(parents=True, exist_ok=True)
  with path.open("a", encoding="utf-8") as f:
    f.write(json.dumps(record, ensure_ascii=False) + "\n")


def build_turn_index_level1(
    conv_dir: Path,
    turn_index: int,
    user_text: str,
    ai_text: str,
    model: str,
) -> None:
  """
  一级索引：标题级摘要
  """
  text = f"用户：{user_text}\n助手：{ai_text}"
  prompt = (
      "请用一句话为这轮对话生成一个简洁但信息密度高的标题，"
      "要求：\n"
      "1. 长度在15-30个汉字之间；\n"
      "2. 包含这轮对话的核心对象和问题；\n"
      "3. 避免使用'一些问题'、'继续上文'等空泛描述。"
  )

  title = call_llm(
      model=model,
      system_prompt="你是对话索引生成器，负责为对话生成清晰的中文标题。",
      user_prompt=f"{prompt}\n\n对话内容：\n{text}",
      response_format="text",
  ).strip()

  record = {
      "turn_index": turn_index,
      "title": title,
      "model": model,
      "timestamp": datetime.utcnow().isoformat(),
  }
  _append_jsonl(conv_dir / "turns_index_level1.jsonl", record)


def build_turn_index_level2(
    conv_dir: Path,
    turn_index: int,
    user_text: str,
    ai_text: str,
    model: str,
) -> None:
  """
  二级索引：关键要点列表 + embedding
  """
  text = f"用户：{user_text}\n助手：{ai_text}"
  prompt = (
      "请为下面这轮对话提炼3-5条关键要点。要求：\n"
      "1. 每条用一句完整的话；\n"
      "2. 覆盖用户的核心问题和助手的核心回应；\n"
      "3. 避免过于细节的句子，只保留真正重要的思想和结论。\n"
      "请直接返回一个JSON数组，每个元素是一个字符串。"
  )

  points: List[str] = call_llm(
      model=model,
      system_prompt="你是对话要点提炼器，返回JSON数组。",
      user_prompt=f"{prompt}\n\n对话内容：\n{text}",
      response_format="json_list",
  )

  # 为要点整体生成一个 embedding，便于后续检索
  summary_text = "；".join(points)
  vec = get_embedding(summary_text)

  record = {
      "turn_index": turn_index,
      "key_points": points,
      "embedding": vec,
      "model": model,
      "timestamp": datetime.utcnow().isoformat(),
  }
  _append_jsonl(conv_dir / "turns_index_level2.jsonl", record)

