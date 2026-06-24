#!/usr/bin/env python3
"""
文件空间 → 文档库 发送事件索引（fs_library_index_core）

设计目标：
- 记录「某个文件从文件空间发送到某个库」这一事实（事件增量，而不是覆盖状态）
- 为前端提供「单文件是否已入库」「目录下文件入库覆盖率」「已入哪些库」等查询能力
- 不改动库内 SQLite / metadata.json 结构，完全独立在 storage 目录下工作

存储位置（按用户隔离）：
  {base_path}/storage/library_index/fs_send_index.jsonl

在 NISB 中，base_path 通常为：
  /opt/nisb-data/users/{uid}
因此单用户的实际落盘路径形如：
  /opt/nisb-data/users/{uid}/storage/library_index/fs_send_index.jsonl

每行一条 JSON 事件：
  {
    "ts": "2025-12-09T19:30:36.643547",
    "user_id": "nisb_xxx",
    "source_path": "agent_files/notes/xxx.md",
    "library_id": "ceshi",
    "doc_id": "doc_20251209_193036_147564",
    "mode": "copy" | "move"
  }

查询策略（简化版，适合当前 1 核 1G 部署）：
- 每次查询按需从 JSONL 读一遍并构建内存索引（path -> set(library_id)）
- 仅统计「是否至少入过一个库」「目录下多少文件入库」「文件具体入过哪些库」
- 如果后续规模变大，可演进为增量缓存或独立 SQLite，但不影响现有事件格式
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Set


# ========== 基础路径工具 ==========


def _get_index_file(base_path: str) -> Path:
  """
  返回当前用户下索引文件路径：
    {base_path}/storage/library_index/fs_send_index.jsonl

  例如：
    base_path = "/opt/nisb-data/users/nisb_default_user"
    → /opt/nisb-data/users/nisb_default_user/storage/library_index/fs_send_index.jsonl
  """
  base = Path(base_path or "/data")
  idx_dir = base / "storage" / "library_index"
  idx_dir.mkdir(parents=True, exist_ok=True)
  return idx_dir / "fs_send_index.jsonl"


def _safe_read_lines(path: Path) -> List[str]:
  """读取 JSONL 文件的所有行（文件不存在则返回空列表）"""
  if not path.exists() or not path.is_file():
    return []
  try:
    with path.open("r", encoding="utf-8") as f:
      return f.readlines()
  except Exception:
    # 索引损坏时不抛异常，交给调用方兜底
    return []


# ========== 事件模型 ==========


@dataclass
class FsSendEvent:
  """文件空间 → 文档库 发送事件"""

  ts: str
  user_id: str
  source_path: str
  library_id: str
  doc_id: str
  mode: str

  def to_dict(self) -> Dict[str, Any]:
    return {
      "ts": self.ts,
      "user_id": self.user_id,
      "source_path": self.source_path,
      "library_id": self.library_id,
      "doc_id": self.doc_id,
      "mode": self.mode,
    }


# ========== 写入事件 ==========


def record_fs_send_event(
  *,
  base_path: str,
  user_id: str,
  source_path: str,
  library_id: str,
  doc_id: str,
  mode: str = "copy",
) -> Dict[str, Any]:
  """
  记录一条「文件从文件空间发送到库」的事件。

  说明：
  - 不做复杂校验，假设上游 fs_send_to_library_core 已经保证成功上传 + 有 doc_id
  - 失败时不会影响主流程（调用方可选择忽略返回值）
  """
  try:
    idx_file = _get_index_file(base_path)
    evt = FsSendEvent(
      ts=datetime.now().isoformat(),
      user_id=str(user_id or "").strip(),
      source_path=str(source_path or "").strip(),
      library_id=str(library_id or "").strip(),
      doc_id=str(doc_id or "").strip(),
      mode=(mode or "copy").strip().lower() or "copy",
    )

    with idx_file.open("a", encoding="utf-8") as f:
      f.write(json.dumps(evt.to_dict(), ensure_ascii=False))
      f.write("\n")

    return {
      "status": "success",
      "message": "✅ 发送事件已记录",
    }
  except Exception as e:
    # 索引写入失败不阻断主流程
    return {
      "status": "error",
      "message": f"❌ 发送事件记录失败：{e}",
    }


# ========== 查询结构 ==========


@dataclass
class PathLibraryStatus:
  """
  单个路径的「入库状态」摘要。

  kind:
    - "file": 直接是文件
    - "directory": 目录
    - "unknown": 索引中未见过该路径（可能从未发送）
  sent:
    - 对文件：是否至少被发送过一次
    - 对目录：是否有子文件被发送过
  coverage:
    - 对文件：sent=True 时为 1.0，sent=False 为 0.0
    - 对目录：0.0~1.0 之间，表示「已入库文件数 / 该目录下出现过的文件总数」
      （这里仅基于索引中出现过的子文件，不扫描真实文件系统）
  libraries:
    - 对文件：去重后的 library_id 列表（按字典序排序）
    - 对目录/unknown：当前版本返回空列表（前端仅用于文件 tooltip）
  """

  path: str
  kind: str
  sent: bool
  coverage: float
  libraries: List[str]

  def to_dict(self) -> Dict[str, Any]:
    return {
      "path": self.path,
      "kind": self.kind,
      "sent": self.sent,
      "coverage": self.coverage,
      "libraries": self.libraries,
    }


# ========== 查询核心 ==========


def _build_path_index(base_path: str) -> Dict[str, Set[str]]:
  """
  从 JSONL 构建一个简单索引：
    path_index[path] = {library_id1, library_id2, ...}

  只关心「某个路径是否曾被发送到任意库」以及「具体是哪些库」。
  """
  idx_file = _get_index_file(base_path)
  lines = _safe_read_lines(idx_file)

  path_index: Dict[str, Set[str]] = {}
  for line in lines:
    line = line.strip()
    if not line:
      continue
    try:
      obj = json.loads(line)
    except Exception:
      continue

    src = str(obj.get("source_path") or "").strip()
    lib = str(obj.get("library_id") or "").strip()
    if not src:
      continue

    if src not in path_index:
      path_index[src] = set()
    if lib:
      path_index[src].add(lib)

  return path_index


def _infer_directory_coverage(
  dir_path: str,
  path_index: Dict[str, Set[str]],
) -> float:
  """
  基于 path_index 粗略估算某个目录的入库覆盖率。

  逻辑：
    - 找到所有以「dir_path + '/'」为前缀的记录（认为是该目录及其子目录下的文件）
    - 总文件数 = 去重后的这些 path 数量
    - 已入库文件数 = 其中 library_id 集合非空的 path 数量
  """
  prefix = dir_path.rstrip("/") + "/"
  total = 0
  sent = 0

  for p, libs in path_index.items():
    if not p.startswith(prefix):
      continue
    total += 1
    if libs:
      sent += 1

  if total == 0:
    return 0.0

  return sent / float(total)


def get_path_library_status(
  base_path: str,
  path: str,
) -> PathLibraryStatus:
  """
  查询单个路径的入库状态。

  - 若 path 恰好在索引中出现过，认为它是文件：
      sent = 是否至少入过某个库
      coverage = 1.0 or 0.0
      libraries = 去重后的库 ID 列表
  - 若 path 未出现，但它是其它 path 的前缀，则认为是目录：
      coverage = 根据子路径估算（0.0~1.0），libraries 为空
  - 否则 kind="unknown"，sent=False, coverage=0.0, libraries=[]
  """
  norm_path = str(path or "").strip()
  if not norm_path:
    return PathLibraryStatus(
      path="",
      kind="unknown",
      sent=False,
      coverage=0.0,
      libraries=[],
    )

  path_index = _build_path_index(base_path)

  # 1) 直接命中：按文件处理
  if norm_path in path_index:
    libs = path_index.get(norm_path) or set()
    sent = bool(libs)
    libraries = sorted(libs) if libs else []
    return PathLibraryStatus(
      path=norm_path,
      kind="file",
      sent=sent,
      coverage=1.0 if sent else 0.0,
      libraries=libraries,
    )

  # 2) 作为目录前缀出现：按目录处理
  prefix = norm_path.rstrip("/") + "/"
  has_child = any(p.startswith(prefix) for p in path_index.keys())
  if has_child:
    cov = _infer_directory_coverage(norm_path, path_index)
    return PathLibraryStatus(
      path=norm_path,
      kind="directory",
      sent=cov > 0.0,
      coverage=cov,
      libraries=[],
    )

  # 3) 索引中完全未知
  return PathLibraryStatus(
    path=norm_path,
    kind="unknown",
    sent=False,
    coverage=0.0,
    libraries=[],
  )


def get_paths_library_status_batch(
  base_path: str,
  paths: List[str],
) -> Dict[str, Any]:
  """
  批量查询多个路径的入库状态。

  返回结构：
    {
      "status": "success",
      "items": [
        {
          "path": "...",
          "kind": "file|directory|unknown",
          "sent": true/false,
          "coverage": 0.0~1.0,
          "libraries": ["lib_a", "lib_b", ...]  # 仅文件会有，目录/unknown 为空数组
        },
        ...
      ]
    }
  """
  try:
    norm_paths = [str(p or "").strip() for p in paths or [] if str(p or "").strip()]
    if not norm_paths:
      return {
        "status": "success",
        "items": [],
      }

    path_index = _build_path_index(base_path)

    items: List[Dict[str, Any]] = []
    for p in norm_paths:
      # 展开 get_path_library_status 逻辑，以避免重复构建索引
      if p in path_index:
        libs = path_index.get(p) or set()
        sent = bool(libs)
        libraries = sorted(libs) if libs else []
        status = PathLibraryStatus(
          path=p,
          kind="file",
          sent=sent,
          coverage=1.0 if sent else 0.0,
          libraries=libraries,
        )
      else:
        prefix = p.rstrip("/") + "/"
        has_child = any(k.startswith(prefix) for k in path_index.keys())
        if has_child:
          cov = _infer_directory_coverage(p, path_index)
          status = PathLibraryStatus(
            path=p,
            kind="directory",
            sent=cov > 0.0,
            coverage=cov,
            libraries=[],
          )
        else:
          status = PathLibraryStatus(
            path=p,
            kind="unknown",
            sent=False,
            coverage=0.0,
            libraries=[],
          )

      items.append(status.to_dict())

    return {
      "status": "success",
      "items": items,
    }
  except Exception as e:
    return {
      "status": "error",
      "message": f"❌ 批量查询入库状态失败：{e}",
      "items": [],
    }

