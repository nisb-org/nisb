#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import json
import argparse
import inspect
import asyncio
import importlib.util
from typing import Any, Dict, Optional, Tuple


BASE_BACKEND = "/opt/mcp-gateway/mcp-nisb"
USERS_ROOT = "/data/users"
TOOLS_ROOT = os.path.join(BASE_BACKEND, "tools")

if BASE_BACKEND not in sys.path:
    sys.path.insert(0, BASE_BACKEND)


def _list_dir(p: str):
    try:
        return sorted(os.listdir(p))
    except Exception:
        return []


def _auto_pick_library_and_doc(uid: str) -> Tuple[Optional[str], Optional[str]]:
    libs_root = os.path.join(USERS_ROOT, uid, "libraries")
    lib_ids = [x for x in _list_dir(libs_root) if os.path.isdir(os.path.join(libs_root, x))]
    if not lib_ids:
        return None, None

    for library_id in lib_ids:
        docs_root = os.path.join(libs_root, library_id, "docs")
        if not os.path.isdir(docs_root):
            continue
        doc_dirs = [
            x for x in _list_dir(docs_root)
            if x.startswith("doc_") and os.path.isdir(os.path.join(docs_root, x))
        ]
        if doc_dirs:
            return library_id, doc_dirs[0]

    return lib_ids[0], None


def _ensure_dir(p: str):
    os.makedirs(p, exist_ok=True)


def _write_json(path: str, obj: Any):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def _find_tool_file(tool_name: str) -> Optional[str]:
    if not os.path.isdir(TOOLS_ROOT):
        return None

    needle = f"def {tool_name}"
    for root, _, files in os.walk(TOOLS_ROOT):
        for fn in files:
            if not fn.endswith(".py"):
                continue
            if fn.startswith("__init__"):
                continue
            path = os.path.join(root, fn)
            try:
                with open(path, "r", encoding="utf-8") as f:
                    s = f.read()
                if needle in s:
                    return path
            except Exception:
                continue
    return None


def _load_tool_from_file(tool_name: str, file_path: str):
    mod_name = f"_dump_b2_{tool_name}"
    spec = importlib.util.spec_from_file_location(mod_name, file_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Failed to create spec for {tool_name} from {file_path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    fn = getattr(mod, tool_name, None)
    if fn is None:
        raise RuntimeError(f"{tool_name} not found after loading {file_path}")
    return fn


async def _call_tool_any(fn, args: Dict[str, Any], uid: Optional[str]):
    ctx = {"uid": uid} if uid else {}
    is_async = asyncio.iscoroutinefunction(fn)

    def _arity(f):
        try:
            return len(inspect.signature(f).parameters)
        except Exception:
            return None

    ar = _arity(fn)

    async def _call(*a):
        if is_async:
            return await fn(*a)
        return fn(*a)

    last_err = None
    candidates = []

    if ar == 1:
        candidates = [(args,)]
    elif ar == 2:
        candidates = [(args, ctx), (args,)]
    elif ar == 3:
        candidates = [(args, ctx, None), (args, ctx), (args,)]
    else:
        candidates = [(args, ctx), (args,)]

    for c in candidates:
        try:
            return await _call(*c)
        except Exception as e:
            last_err = e
            continue

    raise last_err or RuntimeError("Unknown tool call failure")


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--uid", required=True)
    ap.add_argument("--library_id", default="")
    ap.add_argument("--doc_id", default="")
    ap.add_argument("--query", default="test query")
    ap.add_argument("--top_k", type=int, default=5)

    ap.add_argument("--scope", default="library", choices=["doc", "library", "global"])
    ap.add_argument("--group_id", default="")

    ap.add_argument("--rss_scope", default="global")
    ap.add_argument("--feed_id", default="")
    ap.add_argument("--article_id", default="")

    ap.add_argument("--out_dir", default=os.path.join(BASE_BACKEND, "_b2_samples"))
    args = ap.parse_args()

    uid = args.uid.strip()
    library_id = args.library_id.strip() or None
    doc_id = args.doc_id.strip() or None

    if not library_id:
        library_id, auto_doc = _auto_pick_library_and_doc(uid)
        if not doc_id:
            doc_id = auto_doc

    if library_id and not doc_id:
        docs_root = os.path.join(USERS_ROOT, uid, "libraries", library_id, "docs")
        doc_dirs = [
            x for x in _list_dir(docs_root)
            if x.startswith("doc_") and os.path.isdir(os.path.join(docs_root, x))
        ]
        if doc_dirs:
            doc_id = doc_dirs[0]

    _ensure_dir(args.out_dir)

    tool_names = [
        "nisb_library_doc_evidence",
        "nisb_doc_evidence_scope",
        "nisb_rss_evidence_scope",
    ]

    tools = {}
    tool_locations = {}
    tool_load_errors = {}

    for name in tool_names:
        p = _find_tool_file(name)
        tool_locations[name] = p
        if not p:
            tool_load_errors[name] = f"not found under {TOOLS_ROOT}"
            continue
        try:
            tools[name] = _load_tool_from_file(name, p)
        except Exception as e:
            tool_load_errors[name] = f"load failed: {repr(e)}"

    # 1) nisb_library_doc_evidence
    if "nisb_library_doc_evidence" in tools and library_id and doc_id:
        tool_args = {"query": args.query, "library_id": library_id, "doc_id": doc_id, "top_k": args.top_k}
        try:
            res = await _call_tool_any(tools["nisb_library_doc_evidence"], tool_args, uid)
        except Exception as e:
            res = {"status": "error", "error": repr(e), "tool_args": tool_args}
    else:
        res = {
            "status": "error",
            "error": "tool missing or library/doc not found",
            "library_id": library_id,
            "doc_id": doc_id,
            "tool_location": tool_locations.get("nisb_library_doc_evidence"),
            "tool_load_error": tool_load_errors.get("nisb_library_doc_evidence"),
        }
    _write_json(os.path.join(args.out_dir, "nisb_library_doc_evidence.sample.json"), res)

    # 2) nisb_doc_evidence_scope
    if "nisb_doc_evidence_scope" in tools:
        tool_args = {
            "query": args.query,
            "scope": args.scope,
            "library_id": library_id if args.scope in ("doc", "library") else None,
            "doc_id": doc_id if args.scope == "doc" else None,
            "top_k": args.top_k,
        }
        if args.group_id.strip():
            tool_args["group_id"] = args.group_id.strip()
        try:
            res = await _call_tool_any(tools["nisb_doc_evidence_scope"], tool_args, uid)
        except Exception as e:
            res = {"status": "error", "error": repr(e), "tool_args": tool_args}
    else:
        res = {
            "status": "error",
            "error": "tool missing",
            "tool_location": tool_locations.get("nisb_doc_evidence_scope"),
            "tool_load_error": tool_load_errors.get("nisb_doc_evidence_scope"),
        }
    _write_json(os.path.join(args.out_dir, "nisb_doc_evidence_scope.sample.json"), res)

    # 3) nisb_rss_evidence_scope
    if "nisb_rss_evidence_scope" in tools:
        tool_args = {"query": args.query, "scope": args.rss_scope, "top_k": args.top_k}
        if args.feed_id.strip():
            tool_args["feed_id"] = args.feed_id.strip()
        if args.article_id.strip():
            tool_args["article_id"] = args.article_id.strip()
        try:
            res = await _call_tool_any(tools["nisb_rss_evidence_scope"], tool_args, uid)
        except Exception as e:
            res = {"success": False, "error": repr(e), "tool_args": tool_args}
    else:
        res = {
            "success": False,
            "error": "tool missing",
            "tool_location": tool_locations.get("nisb_rss_evidence_scope"),
            "tool_load_error": tool_load_errors.get("nisb_rss_evidence_scope"),
        }
    _write_json(os.path.join(args.out_dir, "nisb_rss_evidence_scope.sample.json"), res)

    manifest = {
        "uid": uid,
        "library_id": library_id,
        "doc_id": doc_id,
        "query": args.query,
        "top_k": args.top_k,
        "scope": args.scope,
        "group_id": args.group_id.strip() or None,
        "rss_scope": args.rss_scope,
        "feed_id": args.feed_id.strip() or None,
        "article_id": args.article_id.strip() or None,
        "out_dir": args.out_dir,
        "tools_root": TOOLS_ROOT,
        "tool_locations": tool_locations,
        "tool_load_errors": tool_load_errors,
        "files": [
            "nisb_library_doc_evidence.sample.json",
            "nisb_doc_evidence_scope.sample.json",
            "nisb_rss_evidence_scope.sample.json",
        ],
    }
    _write_json(os.path.join(args.out_dir, "manifest.json"), manifest)


if __name__ == "__main__":
    asyncio.run(main())
