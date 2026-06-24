from __future__ import annotations

import gc
import time
import threading
from typing import Any, Dict, Optional


_CACHE_LOCK = threading.Lock()


def _safe_int(v: Any, default: int = 0) -> int:
    try:
        return int(v)
    except Exception:
        return default


def nisb_rss_cache_stats(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Get RSS in-process cache stats (semantic index cache, spam rules cache).
    Safe tool: no filesystem mutations, no privileged operations.
    """
    with _CACHE_LOCK:
        try:
            from . import semantic_search as sem
        except Exception:
            sem = None

        try:
            from . import gate_candidates as gate
        except Exception:
            gate = None

        sem_uids = []
        sem_rows_total = 0
        if sem is not None:
            cache = getattr(sem, "_INDEX_CACHE", None)
            if isinstance(cache, dict):
                for uid, ent in cache.items():
                    sem_uids.append(str(uid))
                    rows = ent.get("rows") if isinstance(ent, dict) else None
                    if isinstance(rows, list):
                        sem_rows_total += len(rows)

        spam_basepaths = []
        spam_rules_total = 0
        if gate is not None:
            sc = getattr(gate, "_SPAM_CACHE", None)
            if isinstance(sc, dict):
                for bp, ent in sc.items():
                    spam_basepaths.append(str(bp))
                    active = ent.get("active") if isinstance(ent, dict) else None
                    if isinstance(active, dict):
                        spam_rules_total += len(active)

        return {
            "success": True,
            "ts": time.time(),
            "semantic_index_cache": {
                "uids": sem_uids,
                "uids_count": len(sem_uids),
                "rows_total": sem_rows_total,
            },
            "spam_cache": {
                "basepaths": spam_basepaths,
                "basepaths_count": len(spam_basepaths),
                "active_rules_total": spam_rules_total,
            },
        }


def nisb_rss_cache_clear(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Clear RSS in-process caches to reduce RSS creep on small VPS.
    Optional:
      - uid: only clear semantic cache for specific uid
      - gc_collect: bool (default true)
    """
    uid: Optional[str] = args.get("uid")
    uid = str(uid).strip() if uid is not None and str(uid).strip() else None
    gc_collect = bool(args.get("gc_collect", True))

    cleared_sem_uids = []
    cleared_spam_basepaths = 0

    with _CACHE_LOCK:
        try:
            from . import semantic_search as sem
        except Exception:
            sem = None

        try:
            from . import gate_candidates as gate
        except Exception:
            gate = None

        if sem is not None:
            cache = getattr(sem, "_INDEX_CACHE", None)
            if isinstance(cache, dict):
                if uid:
                    if uid in cache:
                        try:
                            del cache[uid]
                            cleared_sem_uids.append(uid)
                        except Exception:
                            pass
                else:
                    cleared_sem_uids = [str(x) for x in list(cache.keys())]
                    try:
                        cache.clear()
                    except Exception:
                        pass

        if gate is not None:
            sc = getattr(gate, "_SPAM_CACHE", None)
            if isinstance(sc, dict):
                cleared_spam_basepaths = len(sc.keys())
                try:
                    sc.clear()
                except Exception:
                    pass

    gc_n = 0
    if gc_collect:
        try:
            gc_n = _safe_int(gc.collect(), 0)
        except Exception:
            gc_n = 0

    return {
        "success": True,
        "ts": time.time(),
        "cleared": {
            "semantic_uids": cleared_sem_uids,
            "spam_basepaths_count": cleared_spam_basepaths,
        },
        "gc": {
            "collect_called": bool(gc_collect),
            "unreachable_collected": gc_n,
        },
    }

