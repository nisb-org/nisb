#!/usr/bin/env python3
"""
NISB Timeline Tools - Phase 7.6+
时间线视图 + 日历热力图 + 显式活动日志（JSONL）
+ 去重 + 过滤已删除文件 + 清理失效
+ 可删除/批量删除：
  - activity_log：真实删除 activities.jsonl 行（原子替换）
  - 其他来源：写入 tombstones.jsonl（隐藏）
  - 统一：额外写入 resource_key tombstone，防同资源"换 event_id / 多来源复活"

本文件修复点（2025-12-20）：
- 库文档事件识别：library_id/doc_id 允许在顶层或 extra 中
- 库文档去重：按 (library_id, doc_id, extra.kind) 去重，避免 evidence/read/translate 互相覆盖
- resource_key 对库文档同样兼容 extra 中的 library_id/doc_id

新增（2026-02-04）：
- ✅ RSS 导入噪声过滤：rss_import_*.md / extra.source=rss_import 的活动不写入、不展示、整理时清除
- ✅ 按模式批量真删除：nisb_timeline_hard_delete_by_pattern（原子重写 activities.jsonl + 写 tombstone 防复活）
"""

import os
import json
import hashlib
import tempfile
from pathlib import Path
from datetime import datetime, timedelta, timezone
from collections import defaultdict
import sys
import re
import fnmatch

sys.path.insert(0, "/srv")

from core.user_context import auto_user_context, get_user_ctx

ACTIVITY_LOG_FILENAME = "activities.jsonl"
TOMBSTONE_FILENAME = "tombstones.jsonl"

_RSS_IMPORT_NAME_RE = re.compile(r"(?i)^rss_import_[a-z0-9_-]+\.(md|markdown)$")

# ========= 新增：内部路径/库目录过滤 + doc_title 读取 =========

_INTERNAL_ABS_PREFIXES = (
    "/data/users/",
    "/opt/mcp-gateway/",
)

_INTERNAL_REL_PREFIXES = (
    "libraries/",
    "timeline/",
    "annotations/",
    "bookmarks/",
    "storage/",
)

_ID_SAFE_RE = re.compile(r"^[a-zA-Z0-9_-]{1,128}$")


def _to_user_rel_path(user_base: Path, path_str: str) -> str:
    """
    把绝对路径（若位于 user_base 内）转成相对路径，避免 /data/users/... 进入前端时间线。
    """
    try:
        p = str(path_str or "").strip()
        if not p:
            return ""
        p = p.replace("\\", "/")
        pp = Path(p)
        if not pp.is_absolute():
            return p

        base = user_base.resolve()
        real = pp.resolve(strict=False)
        try:
            rel = real.relative_to(base)
            return str(rel).replace("\\", "/")
        except Exception:
            return str(real).replace("\\", "/")
    except Exception:
        return str(path_str or "").strip()


def _is_internal_comm_path(user_base: Path, path_str: str) -> bool:
    """
    判定后端/程序内部通讯路径，前端无意义：
    - 绝对路径 /data/users/... 或 /opt/mcp-gateway/...
    - 相对路径 libraries/ timeline/ annotations/ bookmarks/ storage/...
    """
    try:
        p = str(path_str or "").strip()
        if not p:
            return False
        p = p.replace("\\", "/")

        # 绝对路径：若在 user_base 内，转相对再判；否则按绝对前缀判
        if p.startswith("/"):
            for ap in _INTERNAL_ABS_PREFIXES:
                if p.startswith(ap):
                    rel = _to_user_rel_path(user_base, p)
                    rel = str(rel or "").strip().replace("\\", "/")
                    return any(rel.startswith(rp) for rp in _INTERNAL_REL_PREFIXES)
            return False

        # 相对路径：直接判
        return any(p.startswith(rp) for rp in _INTERNAL_REL_PREFIXES)
    except Exception:
        return True


def _is_library_only_event(ev: dict) -> bool:
    """
    只有 library_id 没有 doc_id 的“库级伪 document 活动”会导致点击报错（库目录当文件打开）。
    必须彻底过滤。
    """
    try:
        if not isinstance(ev, dict):
            return False
        if str(ev.get("type", "") or "").strip() != "document":
            return False
        extra = _get_extra(ev)
        lib = str(ev.get("library_id") or extra.get("library_id") or "").strip()
        doc = str(ev.get("doc_id") or extra.get("doc_id") or "").strip()
        return bool(lib and not doc)
    except Exception:
        return False


def _library_doc_metadata_path(user_base: Path, library_id: str, doc_id: str) -> Path | None:
    """
    按库目录契约推断 metadata.json 路径：
    /data/users/{uid}/libraries/{library_id}/docs/{doc_id}/metadata.json
    """
    try:
        lib = str(library_id or "").strip()
        doc = str(doc_id or "").strip()
        if not lib or not doc:
            return None
        if not _ID_SAFE_RE.match(lib):
            return None
        if not _ID_SAFE_RE.match(doc):
            return None
        return user_base / "libraries" / lib / "docs" / doc / "metadata.json"
    except Exception:
        return None


def _load_library_doc_title(user_base: Path, library_id: str, doc_id: str) -> str:
    """
    尽量从 metadata.json 取一个更友好的名称，返回给前端用于显示（doc_title）。
    """
    try:
        mp = _library_doc_metadata_path(user_base, library_id, doc_id)
        if mp is None or (not mp.exists()):
            return ""
        with open(mp, "r", encoding="utf-8", errors="replace") as f:
            meta = json.load(f)
        if not isinstance(meta, dict):
            return ""
        for k in ("filename", "original_filename", "title", "name", "display_name"):
            v = str(meta.get(k) or "").strip()
            if v:
                return v
        return ""
    except Exception:
        return ""


def _sanitize_event_for_timeline(user_base: Path, ev: dict) -> dict | None:
    """
    后端统一清洗（recent_activities / compact / hard_delete 都可用）：
    - 只允许 document / conversation / hebbian 三类（避免前端出现“• 圆点(活动)”空条目）
    - 过滤：库级伪 document（只有 library_id 没 doc_id）
    - path：绝对转相对；内部通讯目录直接丢弃；目录 path 直接丢弃
    - 库文档：补 doc_title
    """
    try:
        if not isinstance(ev, dict):
            return None

        ev_type = str(ev.get("type", "") or "").strip()
        if ev_type not in ("document", "conversation", "hebbian"):
            return None

        if ev_type == "conversation":
            cid = str(ev.get("id", "") or "").strip()
            if not cid:
                return None
            return ev

        if ev_type == "hebbian":
            return ev

        # document
        extra = _get_extra(ev)
        if extra:
            ev["library_id"] = ev.get("library_id") or extra.get("library_id")
            ev["doc_id"] = ev.get("doc_id") or extra.get("doc_id")

        if _is_library_only_event(ev):
            return None

        lib, doc = _get_library_doc_ids(ev)
        if lib and doc:
            t = _load_library_doc_title(user_base, lib, doc)
            if t:
                ev["doc_title"] = t
            # 库文档可以没有 path
            return ev

        # 普通文件：必须有可打开 path
        ev["path"] = _to_user_rel_path(user_base, ev.get("path", ""))
        p = str(ev.get("path", "") or "").strip()
        if not p:
            return None

        if _is_internal_comm_path(user_base, p):
            return None

        real = _resolve_user_path(user_base, p)
        if real is None or (not real.exists()) or (not real.is_file()):
            return None

        # title 若是绝对路径，改为 basename，避免泄露 /data/users/...
        title = str(ev.get("title", "") or "").strip()
        if title.startswith("/"):
            ev["title"] = _basename_any(title)

        return ev
    except Exception:
        return None


# ========= 原有函数（保留） =========

def _safe_parse_iso(dt_str: str) -> datetime:
    """解析 ISO 日期字符串，统一返回 UTC aware datetime"""
    try:
        if not dt_str:
            return datetime.min.replace(tzinfo=timezone.utc)
        s = str(dt_str).strip()
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return datetime.min.replace(tzinfo=timezone.utc)


def _get_extra(ev: dict) -> dict:
    extra = ev.get("extra") if isinstance(ev, dict) else None
    return extra if isinstance(extra, dict) else {}


def _get_library_doc_ids(ev: dict) -> tuple[str, str]:
    """
    从顶层或 extra 提取 (library_id, doc_id)。
    """
    if not isinstance(ev, dict):
        return "", ""
    extra = _get_extra(ev)
    lib = str(ev.get("library_id") or extra.get("library_id") or "").strip()
    doc = str(ev.get("doc_id") or extra.get("doc_id") or "").strip()
    return lib, doc


def _get_kind(ev: dict) -> str:
    """
    提取 extra.kind（用于库文档去重分组）。
    """
    extra = _get_extra(ev)
    return str(extra.get("kind") or "").strip()


def _canonical_event_payload(ev: dict) -> dict:
    """
    生成稳定的 event_id 计算材料（不要包含 event_id 自身）。
    """
    extra = _get_extra(ev)
    lib, doc = _get_library_doc_ids(ev)
    return {
        "type": ev.get("type", ""),
        "date": ev.get("date", ""),
        "title": ev.get("title", ""),
        "path": ev.get("path", ""),
        "library_id": lib,
        "doc_id": doc,
        "id": ev.get("id", ""),
        "extra": extra,
    }


def _compute_event_id(ev: dict) -> str:
    payload = _canonical_event_payload(ev)
    s = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha1(s.encode("utf-8")).hexdigest()


def _atomic_rewrite_text_file(target: Path, new_lines: list[str]) -> None:
    """原子重写：写到同目录临时文件，再 os.replace 覆盖，避免写一半损坏。"""
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(prefix=target.name + ".", suffix=".tmp", dir=str(target.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            for line in new_lines:
                f.write(line)
        os.replace(tmp_path, target)
    finally:
        try:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        except Exception:
            pass


def _resolve_user_path(user_base: Path, maybe_rel_path: str) -> Path | None:
    """
    把时间线里记录的 path 转成真实文件系统路径用于 exists() 判断。
    - 绝对路径：直接使用
    - 相对路径：视为相对 user_base
    防止 '..' 逃逸。
    """
    try:
        if not maybe_rel_path:
            return None
        p = str(maybe_rel_path).strip()
        if not p:
            return None

        base = user_base.resolve()

        if p.startswith("/"):
            return Path(p)

        cand = (base / p).resolve(strict=False)
        if not str(cand).startswith(str(base)):
            return None
        return cand
    except Exception:
        return None


def _normalize_doc_path(user_base: Path, path_str: str) -> str:
    """统一 document 的路径表示，避免相对/绝对混用导致去重、tombstone 失效。"""
    try:
        p = str(path_str or "").strip()
        if not p:
            return ""
        real = _resolve_user_path(user_base, p)
        if real is None:
            return p
        return str(real)
    except Exception:
        return str(path_str or "").strip()


def _basename_any(s: str) -> str:
    try:
        if not s:
            return ""
        return os.path.basename(str(s).replace("\\", "/"))
    except Exception:
        return ""


def _is_rss_import_name(name: str) -> bool:
    try:
        n = str(name or "").strip()
        if not n:
            return False
        b = _basename_any(n)
        if not b:
            b = n
        return bool(_RSS_IMPORT_NAME_RE.match(b))
    except Exception:
        return False


def _is_rss_import_event(ev: dict) -> bool:
    """
    RSS 导入噪声识别：
    - 文件名命中 rss_import_*.md / *.markdown
    - extra.source == rss_import
    - title/path 命中 rss_import_*.md
    """
    try:
        if not isinstance(ev, dict):
            return False

        extra = _get_extra(ev)
        src = str(extra.get("source") or ev.get("source") or "").strip().lower()
        if src == "rss_import":
            return True

        t = str(ev.get("title", "") or "").strip()
        p = str(ev.get("path", "") or "").strip()
        d = str(ev.get("doc_id", "") or "").strip()

        if _is_rss_import_name(t) or _is_rss_import_name(p) or _is_rss_import_name(d):
            return True

        et = str(extra.get("title") or "").strip()
        ep = str(extra.get("path") or "").strip()
        ed = str(extra.get("doc_id") or "").strip()
        if _is_rss_import_name(et) or _is_rss_import_name(ep) or _is_rss_import_name(ed):
            return True

        return False
    except Exception:
        return False


def _resource_key(user_base: Path, ev: dict) -> str:
    """生成资源级别稳定 key，用于 tombstone / 跨来源隐藏。"""
    try:
        if not isinstance(ev, dict):
            return ""

        ev_type = str(ev.get("type", "") or "").strip()

        if ev_type == "conversation":
            cid = str(ev.get("id", "") or "").strip()
            return f"conversation:{cid}" if cid else ""

        if ev_type == "document":
            lib, doc = _get_library_doc_ids(ev)
            if lib and doc:
                kind = _get_kind(ev)
                return f"document-lib:{lib}:{doc}:{kind or 'generic'}"

            p = _normalize_doc_path(user_base, str(ev.get("path", "") or ""))
            if p:
                return f"document:{p}"
            t = str(ev.get("title", "") or "").strip()
            return f"document_title:{t}" if t else ""

        if ev_type == "hebbian":
            d = str(ev.get("date", "") or "").strip()
            return f"hebbian:{d}" if d else ""

        p = str(ev.get("path", "") or "").strip()
        if p:
            norm = _normalize_doc_path(user_base, p)
            return f"{ev_type}:path:{norm}" if ev_type else norm

        t = str(ev.get("title", "") or "").strip()
        return f"{ev_type}:title:{t}" if (ev_type and t) else ""
    except Exception:
        return ""


def _activity_path_exists(user_base: Path, ev: dict) -> bool:
    """
    过滤已删除/不可打开文件：
    - type=document 且有 path：必须存在且是文件 -> True，否则 False
    - path 为空（库文档等逻辑资源）→ True
    - 其他类型：True
    """
    try:
        if not isinstance(ev, dict):
            return False
        if ev.get("type") != "document":
            return True

        p = str(ev.get("path", "") or "").strip()
        if not p:
            return True

        # ✅ 统一：绝对转相对，并拒绝内部通讯目录
        p = _to_user_rel_path(user_base, p)
        if not p:
            return False
        if _is_internal_comm_path(user_base, p):
            return False

        real = _resolve_user_path(user_base, p)
        if real is None:
            return False

        return real.exists() and real.is_file()
    except Exception:
        return False


def _load_tombstones(user_base: Path) -> tuple[set[str], set[str]]:
    """返回 (hidden_event_ids, hidden_resource_keys)，兼容老格式纯字符串行（视为 event_id）。"""
    tomb = user_base / "timeline" / TOMBSTONE_FILENAME
    if not tomb.exists():
        return set(), set()

    ids: set[str] = set()
    keys: set[str] = set()

    try:
        with open(tomb, "r", encoding="utf-8") as f:
            for line in f:
                s = line.strip()
                if not s:
                    continue
                try:
                    obj = json.loads(s)
                    eid = str(obj.get("event_id", "")).strip()
                    rkey = str(obj.get("resource_key", "")).strip()
                    if eid:
                        ids.add(eid)
                    if rkey:
                        keys.add(rkey)
                except Exception:
                    ids.add(s)
    except Exception:
        return ids, keys

    return ids, keys


def _append_tombstones(user_base: Path, event_ids: set[str], resource_keys: set[str]) -> dict:
    """追加 tombstone（去重），返回 {"event_ids_added": x, "resource_keys_added": y}"""
    tomb = user_base / "timeline" / TOMBSTONE_FILENAME
    tomb.parent.mkdir(parents=True, exist_ok=True)

    existing_ids, existing_keys = _load_tombstones(user_base)

    add_ids = [eid for eid in event_ids if eid and eid not in existing_ids]
    add_keys = [k for k in resource_keys if k and k not in existing_keys]

    if not add_ids and not add_keys:
        return {"event_ids_added": 0, "resource_keys_added": 0}

    try:
        with open(tomb, "a", encoding="utf-8") as f:
            for eid in add_ids:
                f.write(json.dumps({"event_id": eid}, ensure_ascii=False) + "\n")
            for rk in add_keys:
                f.write(json.dumps({"resource_key": rk}, ensure_ascii=False) + "\n")
    except Exception:
        return {"event_ids_added": 0, "resource_keys_added": 0}

    return {"event_ids_added": len(add_ids), "resource_keys_added": len(add_keys)}


def _append_timeline_activity(base_path: str, event: dict) -> None:
    """
    【内部函数】追加一条时间线活动记录（文档/库/文件操作等）
    不抛异常，失败只打日志。
    ✅ RSS 导入噪声：rss_import_* 直接跳过，不写入 activities.jsonl。
    ✅ 新增：内部通讯路径/库级伪活动/目录 path 一律不写入。
    """
    try:
        user_base = Path(base_path)
        timeline_dir = user_base / "timeline"
        timeline_dir.mkdir(parents=True, exist_ok=True)
        log_file = timeline_dir / ACTIVITY_LOG_FILENAME

        extra = event.get("extra", {}) if isinstance(event.get("extra", {}), dict) else {}
        lib = str(event.get("library_id") or extra.get("library_id") or "").strip()
        doc = str(event.get("doc_id") or extra.get("doc_id") or "").strip()

        payload = {
            "type": event.get("type", "document"),
            "date": event.get("date", datetime.now(timezone.utc).isoformat()),
            "title": event.get("title", ""),
            "path": event.get("path", ""),
            "library_id": lib,
            "doc_id": doc,
            "extra": extra,
        }
        payload["event_id"] = event.get("event_id") or _compute_event_id(payload)

        # ✅ 写入端过滤：从源头阻止 rss_import 噪声膨胀
        if _is_rss_import_event(payload):
            return

        # ✅ 写入端过滤：库级伪活动不写（避免库名/库目录进入时间线）
        if payload.get("type") == "document":
            if lib and not doc:
                return

            # 绝对路径转相对，避免 /data/users/... 泄露到前端
            payload["path"] = _to_user_rel_path(user_base, payload.get("path", ""))

            # 内部通讯目录不写
            if _is_internal_comm_path(user_base, payload.get("path", "")):
                return

            # 若 path 指向目录，不写（避免 libraries/psychology）
            p = str(payload.get("path", "") or "").strip()
            if p:
                real = _resolve_user_path(user_base, p)
                if real is not None and real.exists() and real.is_dir():
                    return

        with open(log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=False) + "\n")
    except Exception:
        import traceback
        print("[WARN timeline] append activity failed:", file=sys.stderr)
        traceback.print_exc()


def _dedup_activities_keep_latest(activities: list[dict]) -> list[dict]:
    """
    时间线去重：同一资源只保留最新一条（但库文档按 kind 分组保留）。
    """
    latest_by_key: dict[tuple, dict] = {}

    for ev in activities:
        if not isinstance(ev, dict):
            continue

        ev_type = str(ev.get("type", "") or "").strip()

        if ev_type == "hebbian":
            continue

        if ev_type == "conversation":
            key = ("conversation", str(ev.get("id", "") or "").strip())

        elif ev_type == "document":
            lib, doc = _get_library_doc_ids(ev)
            if lib and doc:
                kind = _get_kind(ev) or "generic"
                key = ("document-lib", lib, doc, kind)
            else:
                p = str(ev.get("path", "") or "").strip()
                if p:
                    key = ("document-path", p)
                else:
                    t = str(ev.get("title", "") or "").strip()
                    key = ("document-title", t)

        else:
            p = str(ev.get("path", "") or "").strip()
            t = str(ev.get("title", "") or "").strip()
            key = (ev_type, p) if p else (ev_type, t)

        if len(key) < 2 or not str(key[1] or "").strip():
            key = (ev_type, str(ev.get("id", "") or "").strip())

        prev = latest_by_key.get(key)
        if prev is None:
            latest_by_key[key] = ev
            continue

        cur_ts = _safe_parse_iso(ev.get("date", ""))
        prev_ts = _safe_parse_iso(prev.get("date", ""))
        if cur_ts >= prev_ts:
            latest_by_key[key] = ev

    hebbian_events = [e for e in activities if isinstance(e, dict) and e.get("type") == "hebbian"]
    return list(latest_by_key.values()) + hebbian_events


@auto_user_context
def nisb_timeline_recent_activities(args: dict) -> dict:
    """
    获取最近活动（对话 + 文档 + Hebbian + 显式活动日志）
    - ✅ 新增：统一清洗，彻底避免库名/库目录/内部路径进入时间线
    - ✅ 新增：库文档补 doc_title（更友好）
    """
    user_ctx = get_user_ctx()
    days = int(args.get("days", 30))
    debug_on = bool(args.get("debug") or args.get("debug_on") or False)

    cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)
    activities: list[dict] = []

    def _is_library_doc(ev: dict) -> bool:
        try:
            if not isinstance(ev, dict):
                return False
            if str(ev.get("type", "") or "").strip() != "document":
                return False
            lib, doc = _get_library_doc_ids(ev)
            return bool(lib and doc)
        except Exception:
            return False

    dbg = {
        "read_conversation": 0,
        "read_legacy_documents": 0,
        "read_hebbian": 0,
        "read_activity_log": 0,
        "read_activity_log_library_doc": 0,
        "skip_rss_import": 0,
        "skip_sanitized": 0,
        "after_dedup_total": 0,
        "after_missing_filter_total": 0,
        "after_tombstone_filter_total": 0,
        "after_tombstone_filter_library_doc": 0,
    }

    user_base = Path(user_ctx.base)

    # 1) 对话
    conversations_root = Path(user_ctx.base) / "web_interactions/conversations"
    if conversations_root.exists():
        for year_dir in conversations_root.iterdir():
            if not year_dir.is_dir():
                continue
            if not year_dir.name.isdigit():
                continue
            for month_dir in year_dir.iterdir():
                if not month_dir.is_dir():
                    continue
                for conv_dir in month_dir.iterdir():
                    if not conv_dir.is_dir() or not conv_dir.name.startswith("conv_"):
                        continue

                    conv_file = conv_dir / "conversation.json"
                    if not conv_file.exists():
                        continue

                    try:
                        with open(conv_file, "r", encoding="utf-8") as f:
                            conv_meta = json.load(f)

                        created_at = _safe_parse_iso(conv_meta.get("created_at", ""))
                        if created_at >= cutoff_date:
                            ev = {
                                "type": "conversation",
                                "origin": "conversation",
                                "date": created_at.isoformat(),
                                "title": conv_meta.get("title", "新对话"),
                                "id": conv_meta.get("id"),
                                "turn_count": conv_meta.get("turn_count", 0),
                            }
                            ev["event_id"] = _compute_event_id(ev)
                            activities.append(ev)
                            dbg["read_conversation"] += 1
                    except Exception:
                        continue

    # 2) 旧 documents 目录
    docs_dir = Path(user_ctx.base) / "documents"
    if docs_dir.exists():
        for doc_file in docs_dir.glob("*"):
            if not doc_file.is_file():
                continue
            try:
                stat = doc_file.stat()
                created_at = datetime.fromtimestamp(stat.st_ctime, tz=timezone.utc)
                if created_at >= cutoff_date:
                    ev = {
                        "type": "document",
                        "origin": "legacy_documents",
                        "date": created_at.isoformat(),
                        "title": doc_file.name,
                        "path": _to_user_rel_path(user_base, str(doc_file)),
                    }
                    ev["event_id"] = _compute_event_id(ev)
                    if _is_rss_import_event(ev):
                        dbg["skip_rss_import"] += 1
                        continue
                    activities.append(ev)
                    dbg["read_legacy_documents"] += 1
            except Exception:
                continue

    # 3) Hebbian 日志
    logs_dir = Path(user_ctx.base) / "storage/logs"
    if logs_dir.exists():
        for log_file in logs_dir.glob("hebbian_*.log"):
            try:
                with open(log_file, "r", encoding="utf-8") as f:
                    for line in f:
                        try:
                            log = json.loads(line)
                            timestamp = _safe_parse_iso(log.get("timestamp", ""))
                            if timestamp >= cutoff_date:
                                ev = {
                                    "type": "hebbian",
                                    "origin": "hebbian_log",
                                    "date": timestamp.isoformat(),
                                    "concepts": log.get("concepts", 0),
                                    "synapses": log.get("created", 0) + log.get("updated", 0),
                                }
                                ev["event_id"] = _compute_event_id(ev)
                                activities.append(ev)
                                dbg["read_hebbian"] += 1
                        except Exception:
                            continue
            except Exception:
                continue

    # 4) 显式活动日志 activities.jsonl
    timeline_log = Path(user_ctx.base) / "timeline" / ACTIVITY_LOG_FILENAME
    if timeline_log.exists():
        try:
            with open(timeline_log, "r", encoding="utf-8", errors="replace") as f:
                for line in f:
                    raw = line.strip()
                    if not raw:
                        continue
                    try:
                        ev = json.loads(raw)
                        ts = _safe_parse_iso(ev.get("date", ""))
                        if ts < cutoff_date:
                            continue

                        ev["origin"] = "activity_log"
                        ev["event_id"] = str(ev.get("event_id", "") or "").strip() or _compute_event_id(ev)

                        extra = _get_extra(ev)
                        if extra:
                            ev["library_id"] = ev.get("library_id") or extra.get("library_id")
                            ev["doc_id"] = ev.get("doc_id") or extra.get("doc_id")

                        if _is_rss_import_event(ev):
                            dbg["skip_rss_import"] += 1
                            continue

                        activities.append(ev)
                        dbg["read_activity_log"] += 1
                        if _is_library_doc(ev):
                            dbg["read_activity_log_library_doc"] += 1
                    except Exception:
                        continue
        except Exception:
            if debug_on:
                return {"status": "error", "message": "读取 activities.jsonl 失败（recent_activities）", "debug": dbg}

    # ✅ 统一清洗（关键：彻底去掉库目录/内部路径，并补 doc_title）
    cleaned: list[dict] = []
    for ev in activities:
        sev = _sanitize_event_for_timeline(user_base, ev)
        if sev is None:
            dbg["skip_sanitized"] += 1
            continue
        cleaned.append(sev)
    activities = cleaned

    activities = _dedup_activities_keep_latest(activities)
    dbg["after_dedup_total"] = len(activities)

    activities = [ev for ev in activities if (_is_library_doc(ev) or _activity_path_exists(user_base, ev))]
    dbg["after_missing_filter_total"] = len(activities)

    hidden_ids, hidden_keys = _load_tombstones(user_base)
    if hidden_ids or hidden_keys:
        filtered: list[dict] = []
        for ev in activities:
            eid = str(ev.get("event_id", "") or "").strip()
            rk = _resource_key(user_base, ev)
            if eid and eid in hidden_ids:
                continue
            if rk and rk in hidden_keys:
                continue
            filtered.append(ev)
        activities = filtered

    dbg["after_tombstone_filter_total"] = len(activities)
    dbg["after_tombstone_filter_library_doc"] = sum(1 for ev in activities if _is_library_doc(ev))

    activities.sort(key=lambda x: _safe_parse_iso(x.get("date", "")), reverse=True)

    grouped: dict[str, list[dict]] = defaultdict(list)
    for activity in activities:
        date_str = str(activity.get("date", ""))[:10]
        grouped[date_str].append(activity)

    today = datetime.now(timezone.utc).date()
    yesterday = today - timedelta(days=1)
    week_start = today - timedelta(days=today.weekday())

    categorized = {
        "today": grouped.get(str(today), []),
        "yesterday": grouped.get(str(yesterday), []),
        "this_week": [],
        "older": [],
    }

    for date_str, items in grouped.items():
        try:
            date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
        except Exception:
            categorized["older"].extend(items)
            continue

        if date_obj == today or date_obj == yesterday:
            continue
        if date_obj >= week_start:
            categorized["this_week"].extend(items)
        else:
            categorized["older"].extend(items)

    res = {"status": "success", "activities": categorized, "total": len(activities)}
    if debug_on:
        res["debug"] = dbg
    return res


@auto_user_context
def nisb_timeline_heatmap_data(args: dict) -> dict:
    """生成日历热力图数据（GitHub 风格）"""
    user_ctx = get_user_ctx()
    year = int(args.get("year", datetime.now().year))

    daily_counts = defaultdict(int)

    conversations_root = Path(user_ctx.base) / "web_interactions/conversations"
    if conversations_root.exists():
        for year_dir in conversations_root.iterdir():
            if not year_dir.is_dir() or year_dir.name != str(year):
                continue
            for month_dir in year_dir.iterdir():
                if not month_dir.is_dir():
                    continue
                for conv_dir in month_dir.iterdir():
                    if not conv_dir.is_dir() or not conv_dir.name.startswith("conv_"):
                        continue
                    conv_file = conv_dir / "conversation.json"
                    if not conv_file.exists():
                        continue
                    try:
                        with open(conv_file, "r", encoding="utf-8") as f:
                            conv_meta = json.load(f)
                        created_at = _safe_parse_iso(conv_meta.get("created_at", ""))
                        date_str = created_at.strftime("%Y-%m-%d")
                        daily_counts[date_str] += conv_meta.get("turn_count", 1)
                    except Exception:
                        continue

    docs_dir = Path(user_ctx.base) / "documents"
    if docs_dir.exists():
        for doc_file in docs_dir.glob("*"):
            if not doc_file.is_file():
                continue
            try:
                stat = doc_file.stat()
                created_at = datetime.fromtimestamp(stat.st_ctime, tz=timezone.utc)
                if created_at.year == year:
                    date_str = created_at.strftime("%Y-%m-%d")
                    daily_counts[date_str] += 1
            except Exception:
                continue

    logs_dir = Path(user_ctx.base) / "storage/logs"
    if logs_dir.exists():
        for log_file in logs_dir.glob(f"hebbian_{year}*.log"):
            try:
                with open(log_file, "r", encoding="utf-8") as f:
                    for line in f:
                        try:
                            log = json.loads(line)
                            timestamp = _safe_parse_iso(log.get("timestamp", ""))
                            date_str = timestamp.strftime("%Y-%m-%d")
                            daily_counts[date_str] += log.get("concepts", 0) // 10
                        except Exception:
                            continue
            except Exception:
                continue

    return {"status": "success", "year": year, "heatmap": dict(daily_counts), "total_days": len(daily_counts)}


@auto_user_context
def nisb_timeline_delete_items(args: dict) -> dict:
    """
    删除/移除时间线条目：
    - origin=activity_log：真实从 activities.jsonl 删除（并写 tombstone 防复活）
    - 其他 origin：只写 tombstone（隐藏）
    """
    user_ctx = get_user_ctx()
    user_base = Path(user_ctx.base)

    items = args.get("items", [])
    if not isinstance(items, list) or not items:
        return {"status": "error", "message": "items 不能为空数组"}

    tomb_event_ids: set[str] = set()
    tomb_resource_keys: set[str] = set()

    delete_event_ids: set[str] = set()
    delete_fallback: set[tuple] = set()

    for it in items:
        if not isinstance(it, dict):
            continue

        eid = str(it.get("event_id", "") or "").strip()
        origin = str(it.get("origin", "") or "").strip()

        if eid:
            tomb_event_ids.add(eid)

        rk = _resource_key(user_base, it)
        if rk:
            tomb_resource_keys.add(rk)

        if origin == "activity_log":
            if eid:
                delete_event_ids.add(eid)
            else:
                delete_fallback.add((
                    (it.get("type") or "").strip(),
                    (it.get("date") or "").strip(),
                    (it.get("path") or "").strip(),
                    (it.get("doc_id") or "").strip(),
                    (it.get("library_id") or "").strip(),
                    (it.get("title") or "").strip(),
                ))

    tomb_added = _append_tombstones(user_base, tomb_event_ids, tomb_resource_keys)

    timeline_log = user_base / "timeline" / ACTIVITY_LOG_FILENAME
    removed = 0
    remaining = 0

    if timeline_log.exists() and (delete_event_ids or delete_fallback):
        kept_lines: list[str] = []

        with open(timeline_log, "r", encoding="utf-8") as f:
            for line in f:
                raw = line.rstrip("\n")
                if not raw.strip():
                    continue
                try:
                    ev = json.loads(raw)
                except Exception:
                    kept_lines.append(raw + "\n")
                    continue

                ev_eid = str(ev.get("event_id", "") or "").strip() or _compute_event_id(ev)

                hit = False
                if ev_eid in delete_event_ids:
                    hit = True
                else:
                    fb = (
                        (ev.get("type") or "").strip(),
                        (ev.get("date") or "").strip(),
                        (ev.get("path") or "").strip(),
                        (ev.get("doc_id") or "").strip(),
                        (ev.get("library_id") or "").strip(),
                        (ev.get("title") or "").strip(),
                    )
                    if fb in delete_fallback:
                        hit = True

                if hit:
                    removed += 1
                else:
                    kept_lines.append(raw + "\n")

        _atomic_rewrite_text_file(timeline_log, kept_lines)

    if timeline_log.exists():
        try:
            with open(timeline_log, "r", encoding="utf-8") as f:
                for _ in f:
                    remaining += 1
        except Exception:
            pass

    return {"status": "success", "removed": removed, "tombstone_added": tomb_added, "remaining": remaining}


@auto_user_context
def nisb_timeline_prune_missing_documents(args: dict) -> dict:
    """
    清理 activities.jsonl 里指向不存在文件的 document 记录（仅作用于显式活动日志）。
    """
    user_ctx = get_user_ctx()
    days = int(args.get("days", 3650))
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    timeline_log = Path(user_ctx.base) / "timeline" / ACTIVITY_LOG_FILENAME
    if not timeline_log.exists():
        return {"status": "success", "removed": 0, "remaining": 0}

    user_base = Path(user_ctx.base)
    removed = 0
    kept_lines: list[str] = []

    with open(timeline_log, "r", encoding="utf-8") as f:
        for line in f:
            raw = line.rstrip("\n")
            if not raw.strip():
                continue
            try:
                ev = json.loads(raw)
            except Exception:
                kept_lines.append(raw + "\n")
                continue

            ts = _safe_parse_iso(ev.get("date", ""))
            if ts != datetime.min and ts < cutoff:
                kept_lines.append(raw + "\n")
                continue

            if ev.get("type") == "document":
                check_ev = dict(ev)
                check_ev["type"] = "document"
                if not _activity_path_exists(user_base, check_ev):
                    removed += 1
                    continue

            kept_lines.append(raw + "\n")

    _atomic_rewrite_text_file(timeline_log, kept_lines)

    remaining = 0
    try:
        with open(timeline_log, "r", encoding="utf-8") as f:
            for _ in f:
                remaining += 1
    except Exception:
        pass

    return {"status": "success", "removed": removed, "remaining": remaining}


@auto_user_context
def nisb_timeline_activity_log_raw(args: dict) -> dict:
    """
    返回 activities.jsonl 最近明细（不去重）。
    可选筛选：type、library_id、doc_id；limit 默认 200。
    """
    user_ctx = get_user_ctx()

    limit = int(args.get("limit", 200))
    if limit <= 0:
        limit = 200
    if limit > 5000:
        limit = 5000

    type_f = str(args.get("type", "") or "").strip()
    lib_f = str(args.get("library_id", "") or "").strip()
    doc_f = str(args.get("doc_id", "") or "").strip()

    log_file = Path(user_ctx.base) / "timeline" / ACTIVITY_LOG_FILENAME
    items: list[dict] = []

    if not log_file.exists():
        return {"status": "success", "items": [], "count": 0}

    try:
        with open(log_file, "r", encoding="utf-8") as f:
            lines = f.readlines()

        for raw in reversed(lines):
            s = raw.strip()
            if not s:
                continue
            try:
                ev = json.loads(s)
            except Exception:
                continue

            extra = _get_extra(ev)
            if extra:
                ev["library_id"] = ev.get("library_id") or extra.get("library_id")
                ev["doc_id"] = ev.get("doc_id") or extra.get("doc_id")

            if type_f and str(ev.get("type", "") or "").strip() != type_f:
                continue
            if lib_f and str(ev.get("library_id", "") or "").strip() != lib_f:
                continue
            if doc_f and str(ev.get("doc_id", "") or "").strip() != doc_f:
                continue

            ev["origin"] = "activity_log_raw"
            ev["event_id"] = str(ev.get("event_id", "") or "").strip() or _compute_event_id(ev)
            items.append(ev)

            if len(items) >= limit:
                break

    except Exception:
        import traceback
        print("[WARN timeline] read activity_log_raw failed:", file=sys.stderr)
        traceback.print_exc()

    return {"status": "success", "items": items, "count": len(items)}


@auto_user_context
def nisb_timeline_compact_activity_log(args: dict) -> dict:
    """
    压缩/整理 activities.jsonl（显式活动日志）：
    - 按资源维度去重：同一资源仅保留最新一条（库文档按 kind 分组）
    - 过滤已删除文件（仅 path 非空的 document；path 为空仍保留）
    - 过滤 tombstone（按 event_id + resource_key）
    - ✅ 过滤 rss_import 噪声
    - ✅ 新增：清洗内部路径/库级伪活动/目录 path，并补 doc_title
    - 原子重写 activities.jsonl
    """
    user_ctx = get_user_ctx()
    user_base = Path(user_ctx.base)

    days = int(args.get("days", 3650))
    if days <= 0:
        days = 3650
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    log_file = user_base / "timeline" / ACTIVITY_LOG_FILENAME
    if not log_file.exists():
        return {"status": "success", "message": "activities.jsonl 不存在，无需整理", "removed": 0, "kept": 0}

    hidden_ids, hidden_keys = _load_tombstones(user_base)

    raw_events: list[dict] = []
    total_lines = 0
    bad_json = 0
    skip_rss = 0
    skip_sanitized = 0

    try:
        with open(log_file, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                total_lines += 1
                s = line.strip()
                if not s:
                    continue
                try:
                    ev = json.loads(s)
                except Exception:
                    bad_json += 1
                    continue

                if not isinstance(ev, dict):
                    continue

                ev["origin"] = "activity_log"
                ev["event_id"] = str(ev.get("event_id", "") or "").strip() or _compute_event_id(ev)

                extra = _get_extra(ev)
                if extra:
                    ev["library_id"] = ev.get("library_id") or extra.get("library_id")
                    ev["doc_id"] = ev.get("doc_id") or extra.get("doc_id")

                if _is_rss_import_event(ev):
                    skip_rss += 1
                    continue

                ts = _safe_parse_iso(ev.get("date", ""))
                if ts != datetime.min and ts < cutoff:
                    continue

                eid = str(ev.get("event_id", "") or "").strip()
                if eid and eid in hidden_ids:
                    continue
                rk = _resource_key(user_base, ev)
                if rk and rk in hidden_keys:
                    continue

                # ✅ 清洗（会过滤库目录/内部路径/目录 path，并补 doc_title）
                sev = _sanitize_event_for_timeline(user_base, ev)
                if sev is None:
                    skip_sanitized += 1
                    continue

                if not _activity_path_exists(user_base, sev):
                    continue

                raw_events.append(sev)

    except Exception as e:
        import traceback
        print("[WARN timeline] compact read failed:", file=sys.stderr)
        traceback.print_exc()
        return {
            "status": "error",
            "message": f"读取 activities.jsonl 失败: {e!r}",
            "debug": {"file": str(log_file), "total_lines_seen": total_lines, "bad_json": bad_json},
        }

    deduped = _dedup_activities_keep_latest(raw_events)
    deduped.sort(key=lambda x: _safe_parse_iso(x.get("date", "")), reverse=False)

    new_lines = [json.dumps(ev, ensure_ascii=False) + "\n" for ev in deduped]
    _atomic_rewrite_text_file(log_file, new_lines)

    kept = len(deduped)
    removed = max(0, total_lines - kept)
    return {
        "status": "success",
        "message": "activities.jsonl 已整理（去重/过滤/原子重写）",
        "removed": removed,
        "kept": kept,
        "before_lines": total_lines,
        "bad_json_skipped": bad_json,
        "rss_import_skipped": skip_rss,
        "sanitized_skipped": skip_sanitized,
    }


def _match_glob(pattern: str, value: str, case_insensitive: bool = True) -> bool:
    try:
        p = str(pattern or "").strip()
        v = str(value or "").strip()
        if not p or not v:
            return False
        if case_insensitive:
            return fnmatch.fnmatch(v.lower(), p.lower())
        return fnmatch.fnmatch(v, p)
    except Exception:
        return False


@auto_user_context
def nisb_timeline_hard_delete_by_pattern(args: dict) -> dict:
    """
    按模式批量真删除 activities.jsonl 中的记录（原子重写）：
    - 同步写入 tombstones.jsonl（event_id + resource_key）防复活
    - ✅ 新增：扫描前清洗（绝对路径转相对），避免用 /data/users/... 模式误伤或泄露
    """
    user_ctx = get_user_ctx()
    user_base = Path(user_ctx.base)

    pattern = str(args.get("pattern", "") or "").strip()
    if not pattern:
        return {"status": "error", "message": "pattern 不能为空，例如 doc_20260129*"}

    days = int(args.get("days", 3650))
    if days <= 0:
        days = 3650
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    match_fields = args.get("match_fields", None)
    if not isinstance(match_fields, list) or not match_fields:
        match_fields = ["title", "path", "doc_id", "library_id"]

    dry_run = bool(args.get("dry_run", True))
    case_insensitive = bool(args.get("case_insensitive", True))

    log_file = user_base / "timeline" / ACTIVITY_LOG_FILENAME
    if not log_file.exists():
        return {"status": "success", "matched": 0, "removed": 0, "remaining": 0, "message": "activities.jsonl 不存在"}

    total_lines = 0
    matched = 0
    bad_json = 0

    tomb_event_ids: set[str] = set()
    tomb_resource_keys: set[str] = set()

    kept_lines: list[str] = []
    samples: list[dict] = []

    def _field_values(ev: dict) -> list[str]:
        vals: list[str] = []
        extra = _get_extra(ev)
        for f in match_fields:
            if f == "title":
                vals.append(str(ev.get("title", "") or ""))
                vals.append(str(extra.get("title", "") or ""))
            elif f == "path":
                vals.append(str(ev.get("path", "") or ""))
                vals.append(str(extra.get("path", "") or ""))
            elif f == "doc_id":
                vals.append(str(ev.get("doc_id", "") or ""))
                vals.append(str(extra.get("doc_id", "") or ""))
            elif f == "library_id":
                vals.append(str(ev.get("library_id", "") or ""))
                vals.append(str(extra.get("library_id", "") or ""))
            elif f == "id":
                vals.append(str(ev.get("id", "") or ""))
                vals.append(str(extra.get("id", "") or ""))
            elif f == "type":
                vals.append(str(ev.get("type", "") or ""))
            elif f == "origin":
                vals.append(str(ev.get("origin", "") or ""))
            else:
                vals.append(str(ev.get(f, "") or ""))
                vals.append(str(extra.get(f, "") or ""))
        more: list[str] = []
        for v in vals:
            b = _basename_any(v)
            if b and b != v:
                more.append(b)
        return vals + more

    try:
        with open(log_file, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                total_lines += 1
                raw = line.rstrip("\n")
                if not raw.strip():
                    continue

                try:
                    ev = json.loads(raw)
                except Exception:
                    bad_json += 1
                    kept_lines.append(raw + "\n")
                    continue

                if not isinstance(ev, dict):
                    kept_lines.append(raw + "\n")
                    continue

                ts = _safe_parse_iso(ev.get("date", ""))
                if ts != datetime.min and ts < cutoff:
                    kept_lines.append(raw + "\n")
                    continue

                extra = _get_extra(ev)
                if extra:
                    ev["library_id"] = ev.get("library_id") or extra.get("library_id")
                    ev["doc_id"] = ev.get("doc_id") or extra.get("doc_id")

                # ✅ 清洗：保证 path 不带 /data/users/... 且过滤库级伪活动（但 hard_delete 的 kept_lines 要保留原 raw）
                # 这里为了匹配更直觉：用清洗后的字段来匹配，但删除/保留仍基于 raw 行
                ev_match = dict(ev)
                ev_match["path"] = _to_user_rel_path(user_base, ev_match.get("path", ""))

                values = _field_values(ev_match)
                hit = any(_match_glob(pattern, v, case_insensitive=case_insensitive) for v in values)

                if not hit:
                    kept_lines.append(raw + "\n")
                    continue

                matched += 1

                eid = str(ev.get("event_id", "") or "").strip() or _compute_event_id(ev)
                if eid:
                    tomb_event_ids.add(eid)
                rk = _resource_key(user_base, ev)
                if rk:
                    tomb_resource_keys.add(rk)

                if len(samples) < 20:
                    samples.append({
                        "event_id": eid,
                        "type": ev.get("type", ""),
                        "date": ev.get("date", ""),
                        "title": ev.get("title", ""),
                        "path": ev.get("path", ""),
                        "library_id": ev.get("library_id", ""),
                        "doc_id": ev.get("doc_id", ""),
                    })

    except Exception as e:
        return {
            "status": "error",
            "message": f"扫描 activities.jsonl 失败: {e!r}",
            "debug": {"file": str(log_file), "total_lines_seen": total_lines, "bad_json": bad_json},
        }

    if dry_run:
        remaining_guess = max(0, total_lines - matched)
        return {
            "status": "success",
            "dry_run": True,
            "pattern": pattern,
            "days": days,
            "matched": matched,
            "removed": 0,
            "remaining_guess": remaining_guess,
            "samples": samples,
            "debug": {"total_lines_seen": total_lines, "bad_json": bad_json},
        }

    if matched <= 0:
        remaining = 0
        try:
            with open(log_file, "r", encoding="utf-8") as f:
                for _ in f:
                    remaining += 1
        except Exception:
            pass
        return {
            "status": "success",
            "dry_run": False,
            "pattern": pattern,
            "days": days,
            "matched": 0,
            "removed": 0,
            "remaining": remaining,
            "message": "未匹配到任何记录，无需改写",
        }

    tomb_added = _append_tombstones(user_base, tomb_event_ids, tomb_resource_keys)
    _atomic_rewrite_text_file(log_file, kept_lines)

    remaining = 0
    try:
        with open(log_file, "r", encoding="utf-8") as f:
            for _ in f:
                remaining += 1
    except Exception:
        pass

    return {
        "status": "success",
        "dry_run": False,
        "pattern": pattern,
        "days": days,
        "matched": matched,
        "removed": matched,
        "remaining": remaining,
        "tombstone_added": tomb_added,
        "samples": samples,
        "debug": {"total_lines_seen": total_lines, "bad_json": bad_json},
    }


__all__ = [
    "nisb_timeline_recent_activities",
    "nisb_timeline_heatmap_data",
    "nisb_timeline_delete_items",
    "nisb_timeline_prune_missing_documents",
    "nisb_timeline_activity_log_raw",
    "nisb_timeline_compact_activity_log",
    "nisb_timeline_hard_delete_by_pattern",
    "_append_timeline_activity",
]


