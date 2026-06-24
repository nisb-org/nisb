#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import json
import shutil
import traceback
from datetime import datetime
from typing import Any, Dict, List, Optional

from core.user_context import auto_user_context, get_user_ctx
from .chat_conversation_store import (
    create_conversation,
    find_conv_dir,
    iter_conversation_dirs,
    load_conversation_meta,
    normalize_labels,
    save_conversation_meta,
    read_turn_records,
)


def _match_label(meta: Dict[str, Any], label: Optional[str]) -> bool:
    labels = meta.get("labels", []) or []
    if not isinstance(labels, list):
        labels = []
    labels = [x for x in labels if isinstance(x, str)]
    meta["labels"] = labels

    if label is None:
        return True
    if label == "__UNLABELED__":
        return len(labels) == 0
    return label in labels


def _parse_sort_dt(value: Any) -> datetime:
    s = str(value or "").strip()
    if not s:
        return datetime.min

    if s.endswith("Z"):
        s = s[:-1] + "+00:00"

    try:
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is not None:
            dt = dt.astimezone().replace(tzinfo=None)
        return dt
    except Exception:
        pass

    for fmt in (
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M:%S.%f",
        "%Y-%m-%d",
    ):
        try:
            return datetime.strptime(s, fmt)
        except Exception:
            continue

    return datetime.min


def _conversation_activity_dt(meta: Dict[str, Any]) -> datetime:
    last_updated = _parse_sort_dt(meta.get("last_updated"))
    if last_updated != datetime.min:
        return last_updated

    created_at = _parse_sort_dt(meta.get("created_at"))
    if created_at != datetime.min:
        return created_at

    return datetime.min


def _conversation_sort_key(meta: Dict[str, Any]):
    activity_dt = _conversation_activity_dt(meta)
    created_dt = _parse_sort_dt(meta.get("created_at"))
    conv_id = str(meta.get("id") or "")
    return (activity_dt, created_dt, conv_id)


@auto_user_context
def nisb_chat_create(args: dict) -> dict:
    user_ctx = get_user_ctx()
    title = str(args.get("title") or "新对话").strip() or "新对话"

    created = create_conversation(user_ctx.base, title)

    return {
        "status": "success",
        "conv_id": created["conv_id"],
        "message": f"✅ 已创建对话: {created['conv_id']}",
    }


@auto_user_context
def nisb_chat_history(args: dict) -> dict:
    user_ctx = get_user_ctx()

    try:
        limit = int(args.get("limit", 50) or 50)
    except Exception:
        limit = 50
    if limit <= 0:
        limit = 50

    cursor = args.get("cursor")
    label = args.get("label")

    if isinstance(label, str):
        label = label.strip()
        if not label or label.upper() == "ALL":
            label = None
    else:
        label = None

    conv_dirs = iter_conversation_dirs(user_ctx.base, reverse=True)
    if not conv_dirs:
        return {
            "status": "success",
            "conversations": [],
            "total": 0,
            "has_more": False,
            "next_cursor": None,
            "message": "📝 暂无对话记录",
        }

    all_conversations: List[Dict[str, Any]] = []

    for conv_dir in conv_dirs:
        meta_file_meta = load_conversation_meta(conv_dir)
        conv_id = meta_file_meta.get("id") or conv_dir.name
        meta_file_meta["id"] = conv_id

        if not _match_label(meta_file_meta, label):
            continue

        all_conversations.append(meta_file_meta)

    if not all_conversations:
        return {
            "status": "success",
            "conversations": [],
            "total": 0,
            "has_more": False,
            "next_cursor": None,
            "message": "📝 暂无对话记录",
        }

    all_conversations.sort(key=_conversation_sort_key, reverse=True)

    conversations: List[Dict[str, Any]] = []
    seen_cursor = cursor is None
    has_more = False

    for meta in all_conversations:
        conv_id = meta.get("id")

        if not seen_cursor:
            if conv_id == cursor:
                seen_cursor = True
            continue

        if len(conversations) < limit:
            conversations.append(meta)
            continue

        has_more = True
        break

    next_cursor = conversations[-1].get("id") if conversations and has_more else None

    return {
        "status": "success",
        "conversations": conversations,
        "total": len(conversations),
        "has_more": bool(has_more),
        "next_cursor": next_cursor,
        "message": f"📝 本页 {len(conversations)} 条对话" + ("（可继续加载）" if has_more else "（已到最早）"),
    }


@auto_user_context
def nisb_chat_load(args: dict) -> dict:
    user_ctx = get_user_ctx()
    conv_id = str(args.get("conv_id") or "").strip()

    if not conv_id:
        return {
            "status": "error",
            "message": "❌ conv_id 不能为空",
        }

    conv_dir = find_conv_dir(user_ctx.base, conv_id)
    if not conv_dir:
        return {
            "status": "error",
            "message": f"❌ 对话不存在: {conv_id}",
        }

    turns: List[Dict[str, Any]] = []
    for turn in read_turn_records(conv_dir):
        if str(turn.get("turn_type") or "") not in ("user", "assistant"):
            continue

        turns.append(
            {
                "sequence": turn.get("sequence"),
                "role": turn.get("turn_type"),
                "content": turn.get("content"),
                "timestamp": turn.get("timestamp"),
                "model": turn.get("model"),
                "mode_used": turn.get("mode_used"),
                "citations": turn.get("citations") or [],
                "rss_evidence": turn.get("rss_evidence") or [],
                "market_evidence": turn.get("market_evidence") or [],
                "evidence_query": turn.get("evidence_query"),
                "evidence_tools": turn.get("evidence_tools") or [],
                "evidence_result": turn.get("evidence_result"),
            }
        )

    return {
        "status": "success",
        "conv_id": conv_id,
        "turns": turns,
        "total": len(turns),
        "message": f"✅ 已加载 {len(turns)} 条消息",
    }


@auto_user_context
def nisb_chat_rename(args: dict) -> dict:
    user_ctx = get_user_ctx()
    conv_id = str(args.get("conv_id") or "").strip()
    new_title = str(args.get("new_title") or "").strip()

    if not conv_id or not new_title:
        return {
            "status": "error",
            "message": "❌ conv_id 和 new_title 不能为空",
        }

    conv_dir = find_conv_dir(user_ctx.base, conv_id)
    if not conv_dir:
        return {
            "status": "error",
            "message": f"❌ 对话不存在: {conv_id}",
        }

    try:
        meta = load_conversation_meta(conv_dir)
        old_title = meta.get("title", "新对话")
        meta["title"] = new_title
        meta["last_updated"] = datetime.now().isoformat()
        save_conversation_meta(conv_dir, meta)

        return {
            "status": "success",
            "message": f"✅ 已重命名：{old_title} → {new_title}",
        }
    except Exception as e:
        traceback.print_exc()
        return {
            "status": "error",
            "message": f"❌ 重命名失败: {str(e)}",
        }


@auto_user_context
def nisb_chat_delete(args: dict) -> dict:
    user_ctx = get_user_ctx()
    conv_id = str(args.get("conv_id") or "").strip()

    if not conv_id:
        return {
            "status": "error",
            "message": "❌ conv_id 不能为空",
        }

    conv_dir = find_conv_dir(user_ctx.base, conv_id)
    if not conv_dir:
        return {
            "status": "error",
            "message": f"❌ 对话不存在: {conv_id}",
        }

    try:
        meta = load_conversation_meta(conv_dir)
        title = meta.get("title", "新对话")
        shutil.rmtree(conv_dir)

        return {
            "status": "success",
            "message": f"✅ 已删除对话：{title}",
        }
    except Exception as e:
        traceback.print_exc()
        return {
            "status": "error",
            "message": f"❌ 删除失败: {str(e)}",
        }


@auto_user_context
def nisb_chat_update_labels(args: dict) -> dict:
    user_ctx = get_user_ctx()
    conv_id = str(args.get("conv_id") or "").strip()
    raw_labels = args.get("labels", [])

    if not conv_id:
        return {
            "status": "error",
            "message": "❌ conv_id 不能为空",
        }

    conv_dir = find_conv_dir(user_ctx.base, conv_id)
    if not conv_dir:
        return {
            "status": "error",
            "message": f"❌ 对话不存在: {conv_id}",
        }

    try:
        labels = normalize_labels(raw_labels)
        meta = load_conversation_meta(conv_dir)
        meta["labels"] = labels
        meta["last_updated"] = datetime.now().isoformat()
        save_conversation_meta(conv_dir, meta)

        return {
            "status": "success",
            "conv_id": conv_id,
            "labels": labels,
            "message": "✅ 标签已更新",
        }
    except Exception as e:
        traceback.print_exc()
        return {
            "status": "error",
            "message": f"❌ 更新标签失败: {str(e)}",
        }


@auto_user_context
def nisb_chat_get_labels(args: dict) -> dict:
    user_ctx = get_user_ctx()
    conv_id = str(args.get("conv_id") or "").strip()

    if not conv_id:
        return {
            "status": "error",
            "message": "❌ conv_id 不能为空",
        }

    conv_dir = find_conv_dir(user_ctx.base, conv_id)
    if not conv_dir:
        return {
            "status": "error",
            "message": f"❌ 对话不存在: {conv_id}",
        }

    try:
        meta = load_conversation_meta(conv_dir)
        labels = meta.get("labels", []) or []

        return {
            "status": "success",
            "conv_id": conv_id,
            "labels": labels,
            "message": f"✅ 已获取 {len(labels)} 个标签",
        }
    except Exception as e:
        traceback.print_exc()
        return {
            "status": "error",
            "message": f"❌ 获取标签失败: {str(e)}",
        }


@auto_user_context
def nisb_chat_list_labels(args: dict) -> dict:
    user_ctx = get_user_ctx()
    conv_dirs = iter_conversation_dirs(user_ctx.base, reverse=True)

    if not conv_dirs:
        return {
            "status": "success",
            "labels": [],
            "unlabeled_count": 0,
            "total": 0,
            "message": "✅ 暂无标签",
        }

    label_map: Dict[str, Dict[str, Any]] = {}
    unlabeled_count = 0

    for conv_dir in conv_dirs:
        meta = load_conversation_meta(conv_dir)
        conv_id = meta.get("id") or conv_dir.name
        labels = meta.get("labels", []) or []
        if not isinstance(labels, list):
            labels = []
        labels = [x.strip() for x in labels if isinstance(x, str) and x.strip()]

        if not labels:
            unlabeled_count += 1
            continue

        for label in labels:
            entry = label_map.setdefault(
                label,
                {"label": label, "count": 0, "conv_ids": []},
            )
            entry["count"] += 1
            if conv_id not in entry["conv_ids"]:
                entry["conv_ids"].append(conv_id)

    label_list = list(label_map.values())
    label_list.sort(key=lambda x: (-x["count"], x["label"]))

    return {
        "status": "success",
        "labels": label_list,
        "unlabeled_count": unlabeled_count,
        "total": len(label_list),
        "message": f"✅ 共 {len(label_list)} 个标签",
    }
