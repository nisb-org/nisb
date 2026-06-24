#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


def get_conversations_root(base_path: str) -> Path:
    return Path(base_path) / "web_interactions" / "conversations"


def atomic_write_json(path: Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    tmp = tempfile.NamedTemporaryFile(
        mode="w",
        delete=False,
        encoding="utf-8",
        dir=str(path.parent),
        prefix=f".tmp_{path.name}_",
    )
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


def ensure_labels_list(meta: Dict[str, Any]) -> Dict[str, Any]:
    labels = meta.get("labels", [])
    if not isinstance(labels, list):
        labels = []
    labels = [x for x in labels if isinstance(x, str)]
    meta["labels"] = labels
    return meta


def create_conversation(base_path: str, title: str) -> Dict[str, Any]:
    now = datetime.now()
    conv_id = f"conv_{now.strftime('%Y%m%d_%H%M%S')}"
    conv_dir = get_conversations_root(base_path) / now.strftime("%Y/%m") / conv_id
    conv_dir.mkdir(parents=True, exist_ok=True)

    meta = {
        "id": conv_id,
        "title": title or "新对话",
        "created_at": now.isoformat(),
        "turn_count": 0,
        "labels": [],
    }

    atomic_write_json(conv_dir / "conversation.json", meta)
    (conv_dir / "turns.jsonl").touch()

    return {
        "conv_id": conv_id,
        "conv_dir": conv_dir,
        "meta": meta,
    }


def iter_conversation_dirs(base_path: str, reverse: bool = True) -> List[Path]:
    root = get_conversations_root(base_path)
    out: List[Path] = []
    if not root.exists():
        return out

    for year_dir in sorted(root.glob("*"), reverse=reverse):
        for month_dir in sorted(year_dir.glob("*"), reverse=reverse):
            for conv_dir in sorted(month_dir.glob("conv_*"), reverse=reverse):
                if conv_dir.is_dir():
                    out.append(conv_dir)
    return out


def find_conv_dir(base_path: str, conv_id: str) -> Optional[Path]:
    if not conv_id:
        return None

    root = get_conversations_root(base_path)
    if not root.exists():
        return None

    for year_dir in root.glob("*"):
        for month_dir in year_dir.glob("*"):
            test_dir = month_dir / conv_id
            if test_dir.exists():
                return test_dir
    return None


def load_conversation_meta(conv_dir: Path) -> Dict[str, Any]:
    meta_file = conv_dir / "conversation.json"
    if not meta_file.exists():
        return {"id": conv_dir.name, "title": "新对话", "turn_count": 0, "labels": []}

    try:
        meta = json.loads(meta_file.read_text(encoding="utf-8"))
    except Exception:
        meta = {"id": conv_dir.name, "title": "新对话", "turn_count": 0, "labels": []}

    meta["id"] = meta.get("id") or conv_dir.name
    return ensure_labels_list(meta)


def save_conversation_meta(conv_dir: Path, meta: Dict[str, Any]) -> None:
    meta = dict(meta or {})
    meta["id"] = meta.get("id") or conv_dir.name
    ensure_labels_list(meta)
    atomic_write_json(conv_dir / "conversation.json", meta)


def read_turn_records(conv_dir: Path) -> List[Dict[str, Any]]:
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
                rec = json.loads(line)
            except Exception:
                continue
            if isinstance(rec, dict):
                out.append(rec)

    return out


def append_turn_record(conv_dir: Path, turn: Dict[str, Any]) -> None:
    turns_file = conv_dir / "turns.jsonl"
    with turns_file.open("a", encoding="utf-8") as f:
        f.write(json.dumps(turn, ensure_ascii=False) + "\n")


def normalize_labels(raw_labels: Any) -> List[str]:
    labels: List[str] = []

    if isinstance(raw_labels, str):
        for part in raw_labels.split(","):
            lab = part.strip()
            if lab:
                labels.append(lab)
    elif isinstance(raw_labels, list):
        for item in raw_labels:
            lab = str(item).strip()
            if lab:
                labels.append(lab)

    seen = set()
    cleaned: List[str] = []
    for lab in labels:
        if lab in seen:
            continue
        seen.add(lab)
        cleaned.append(lab)

    return cleaned

