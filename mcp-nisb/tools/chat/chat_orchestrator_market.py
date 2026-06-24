#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Tuple

from core.storage import load_jsonl
from tools.federation import nisb_fed_call
from tools.market import nisb_market_search
from .chat_orchestrator_mode import coerce_bool


def market_listings_jsonl(user_base: str) -> str:
    return str(Path(user_base) / "market" / "listings.jsonl")


def market_has_any(user_base: str) -> bool:
    try:
        rows = load_jsonl(market_listings_jsonl(user_base))
        for row in rows:
            if isinstance(row, dict) and row.get("tombstone") is not True:
                return True
        return False
    except Exception:
        return False


def resolve_market_settings(*, args: Dict[str, Any], effective_mode: str, user_base: str) -> Tuple[bool, List[str], int]:
    peer_targets_raw = args.get("peer_targets")
    peer_targets: List[str] = []
    if isinstance(peer_targets_raw, list):
        peer_targets = [str(x).strip() for x in peer_targets_raw if str(x).strip()]

    if "market_enabled" in args:
        enabled = coerce_bool(args.get("market_enabled"), default=False)
    else:
        enabled = (effective_mode in ("cite", "ground") and market_has_any(user_base)) or bool(peer_targets)

    max_items = args.get("market_max_evidence", 4)
    try:
        max_items = int(max_items)
    except Exception:
        max_items = 4
    max_items = max(1, min(12, max_items))

    return enabled, peer_targets, max_items


def build_market_evidence_items(
    *,
    user_base: str,
    query_text: str,
    limit_total: int,
    peer_targets: List[str],
) -> List[Dict[str, Any]]:
    query = str(query_text or "").strip()
    if not query:
        return []

    out: List[Dict[str, Any]] = []
    limit_total = max(1, min(20, int(limit_total)))

    try:
        res = nisb_market_search({"basepath": user_base, "query": query, "limit": min(10, limit_total)})
        items = (res or {}).get("items") if isinstance(res, dict) else None
        if isinstance(items, list):
            for it in items:
                if len(out) >= limit_total:
                    break
                if not isinstance(it, dict):
                    continue
                out.append(
                    {
                        "source": "market",
                        "relevance": 0.25,
                        "title": str(it.get("title") or it.get("object_ref") or "").strip(),
                        "quote": str((it.get("payload") or {}).get("note") or it.get("object_ref") or "").strip(),
                        "object_ref": it.get("object_ref"),
                        "listing_id": it.get("id"),
                        "peer_id": None,
                    }
                )
    except Exception:
        pass

    for peer_id in peer_targets:
        if len(out) >= limit_total:
            break
        try:
            rr = nisb_fed_call(
                {
                    "basepath": user_base,
                    "peer_id": peer_id,
                    "tool": "nisb_market_search",
                    "tool_args": {"query": query, "limit": min(6, limit_total)},
                    "timeout_ms": 8000,
                }
            )
            remote = (rr or {}).get("result") if isinstance(rr, dict) else None
            items2 = (remote or {}).get("items") if isinstance(remote, dict) else None
            if not isinstance(items2, list):
                continue

            for it in items2:
                if len(out) >= limit_total:
                    break
                if not isinstance(it, dict):
                    continue
                out.append(
                    {
                        "source": "market",
                        "relevance": 0.22,
                        "title": str(it.get("title") or it.get("object_ref") or "").strip(),
                        "quote": str((it.get("payload") or {}).get("note") or it.get("object_ref") or "").strip(),
                        "object_ref": it.get("object_ref"),
                        "listing_id": it.get("id"),
                        "peer_id": peer_id,
                    }
                )
        except Exception:
            continue

    return out

