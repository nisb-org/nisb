# /opt/mcp-gateway/mcp-nisb/tools/rss/spam_blacklist.py
from __future__ import annotations

import os
import time
import json
import hashlib
from datetime import datetime, timezone
from typing import Any, Dict, List

from core.storage import load_jsonl, append_jsonl
from .tools import _get_basepath, _rss_root


def _utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _path(basepath: str) -> str:
    return os.path.join(_rss_root(basepath), "rss_spam_blacklist.jsonl")


def _rid(scope: str, payload: str) -> str:
    h = hashlib.sha256(f"{scope}:{payload}".encode("utf-8")).hexdigest()
    return h[:16]


def _fold_latest(rows: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    latest: Dict[str, Dict[str, Any]] = {}
    for r in rows:
        if not isinstance(r, dict):
            continue
        rid = str(r.get("rule_id") or "").strip()
        if not rid:
            continue
        latest[rid] = r
    return latest


def nisb_rss_spam_add(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    args:
      - basepath injected
      - scope: "article" | "domain" | "feed"
      - url: (article)
      - article_id: (article, optional)
      - feed_id: (feed/article optional)
      - domain: (domain)
      - reason: optional
    """
    basepath = _get_basepath(args)
    scope = str(args.get("scope") or "article").strip().lower()

    url = str(args.get("url") or "").strip()
    article_id = str(args.get("article_id") or "").strip()
    feed_id = str(args.get("feed_id") or "").strip()
    domain = str(args.get("domain") or "").strip().lower()
    reason = str(args.get("reason") or "").strip()

    if scope == "article" and not (url or article_id):
        return {"success": False, "message": "missing url/article_id for article spam rule"}
    if scope == "domain" and not domain:
        return {"success": False, "message": "missing domain for domain spam rule"}
    if scope == "feed" and not feed_id:
        return {"success": False, "message": "missing feed_id for feed spam rule"}

    payload = url or article_id or domain or feed_id
    rule_id = _rid(scope, payload)

    row = {
        "type": "rss_spam_rule",
        "ts": _utc_iso(),
        "rule_id": rule_id,
        "scope": scope,
        "url": url,
        "article_id": article_id,
        "feed_id": feed_id,
        "domain": domain,
        "reason": reason,
        "tombstone": False,
    }
    append_jsonl(_path(basepath), row)
    return {"success": True, "rule_id": rule_id, "rule": row}


def nisb_rss_spam_delete(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    args:
      - basepath injected
      - rule_id: str
    """
    basepath = _get_basepath(args)
    rule_id = str(args.get("rule_id") or "").strip()
    if not rule_id:
        return {"success": False, "message": "missing rule_id"}

    row = {
        "type": "rss_spam_tombstone",
        "ts": _utc_iso(),
        "rule_id": rule_id,
        "tombstone": True,
    }
    append_jsonl(_path(basepath), row)
    return {"success": True, "rule_id": rule_id}


def nisb_rss_spam_list(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    args:
      - basepath injected
      - include_tombstone: bool (default False)
    """
    basepath = _get_basepath(args)
    include_tombstone = bool(args.get("include_tombstone", False))

    rows = load_jsonl(_path(basepath)) or []
    latest = _fold_latest(rows)

    items: List[Dict[str, Any]] = []
    for rid, r in latest.items():
        if not include_tombstone and bool(r.get("tombstone", False)) is True:
            continue
        if str(r.get("type") or "") == "rss_spam_tombstone" and not include_tombstone:
            continue
        items.append(r)

    items.sort(key=lambda x: str(x.get("ts") or ""), reverse=True)
    return {"success": True, "items": items}

