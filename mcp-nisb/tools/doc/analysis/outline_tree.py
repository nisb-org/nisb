from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from core.openai_utils import call_llm

try:
    from tools.timeline import _append_timeline_activity
except Exception:
    _append_timeline_activity = None


OUTLINE_JSONL = "outline.jsonl"
OUTLINE_JSON = "outline.json"

DEFAULT_DATA_ROOT = Path(os.environ.get("NISB_BASE_PATH", "/data")).resolve()

# ✅ 与前端连续阅读一致：Span 0 = 0-8000
SPAN_SIZE = 8000

# LLM Outline 默认配置（可用环境变量覆盖）
OUTLINE_LLM_MODEL_DEFAULT = os.getenv("OPENAI_OUTLINE_MODEL", "gpt-4o-mini")
OUTLINE_LLM_MAX_CHARS = int(os.getenv("OPENAI_OUTLINE_MAX_CHARS", "24000"))
OUTLINE_LLM_MAX_CHILDREN_DEFAULT = int(os.getenv("OPENAI_OUTLINE_MAX_CHILDREN", "24"))
OUTLINE_LLM_PROMPT_VERSION = "outline_llm_v1"

# Outline Translate 默认配置（默认 mini）
OUTLINE_TRANSLATE_MODEL_DEFAULT = os.getenv("OPENAI_OUTLINE_TRANSLATE_MODEL", "gpt-4o-mini")
OUTLINE_TRANSLATE_PROMPT_VERSION = "outline_translate_zh_v1"
OUTLINE_TRANSLATE_MAX_ITEMS_PER_BATCH = int(os.getenv("OPENAI_OUTLINE_TRANSLATE_MAX_ITEMS", "60"))
OUTLINE_TRANSLATE_MAX_CHARS_PER_BATCH = int(os.getenv("OPENAI_OUTLINE_TRANSLATE_MAX_CHARS", "12000"))


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _flag(v: Any) -> bool:
    """
    兼容 ensure/force_rebuild 可能来自 0/1、"0"/"1"、true/false 等。
    注意：Python 中任何非空字符串都 truthy（bool("0") == True），所以必须手动解析。[web:1058]
    """
    if v is None:
        return False
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return bool(int(v))
    s = str(v).strip().lower()
    if s in ("1", "true", "yes", "y", "on"):
        return True
    if s in ("0", "false", "no", "n", "off", ""):
        return False
    return True


def _timeline_append(base_path: str, event: dict) -> None:
    """
    timeline 可选：可用就写，不可用就忽略，不能影响 outline 主流程。
    """
    if not _append_timeline_activity:
        return
    try:
        _append_timeline_activity(base_path=base_path, event=event)
    except TypeError:
        # 兼容不同签名
        try:
            _append_timeline_activity(base_path, event)  # type: ignore
        except Exception:
            return
    except Exception:
        return


def _hash_params(d: dict) -> str:
    payload = json.dumps(d, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()[:16]


def _estimate_tokens_from_chars(n_chars: int) -> int:
    # 粗估：1 token ≈ 4 English chars（仅用于提示/记录）
    return max(1, n_chars // 4)


def _safe_read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows: list[dict] = []
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            raw = line.strip()
            if not raw:
                continue
            try:
                rows.append(json.loads(raw))
            except Exception:
                continue
    return rows


def _safe_read_json(path: Path) -> Optional[dict]:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return None


def _append_jsonl(path: Path, obj: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")


def _resolve_user_base(args: dict) -> Path:
    """
    统一走容器内数据根（/data）。
    """
    base = str(args.get("_base_path") or "").strip()
    if base:
        return Path(base)

    uid = str(args.get("user_id") or args.get("uid") or "default").strip() or "default"
    return DEFAULT_DATA_ROOT / "users" / uid


def _candidate_doc_dirs(user_base: Path, library_id: str, doc_id: str) -> list[Path]:
    cands: list[Path] = [
        user_base / "libraries" / library_id / "docs" / doc_id,
        user_base / library_id / "docs" / doc_id,
        user_base / "docs" / doc_id,
        user_base,
    ]
    seen = set()
    out: list[Path] = []
    for p in cands:
        s = str(p)
        if s not in seen:
            seen.add(s)
            out.append(p)
    return out


def _resolve_doc_dir(args: dict, library_id: str, doc_id: str) -> tuple[Path, dict]:
    user_base = _resolve_user_base(args)
    cands = _candidate_doc_dirs(user_base, library_id, doc_id)
    for p in cands:
        if p.exists() and p.is_dir():
            return p, {
                "data_root": str(DEFAULT_DATA_ROOT),
                "user_base": str(user_base),
                "picked": str(p),
                "candidates": [str(x) for x in cands],
            }
    return cands[0], {
        "data_root": str(DEFAULT_DATA_ROOT),
        "user_base": str(user_base),
        "picked": str(cands[0]),
        "candidates": [str(x) for x in cands],
    }


def _list_dir_filenames(p: Path) -> list[str]:
    try:
        if not p.exists() or not p.is_dir():
            return []
        return sorted([x.name for x in p.iterdir() if x.is_file()])
    except Exception:
        return []


def _read_full_text(doc_dir: Path) -> tuple[str, str]:
    """
    ✅ 统一全文来源：优先 content.txt（与你的连续阅读对齐）
    """
    candidates = [
        "content.txt",
        "full_text.txt",
        "text.txt",
        "raw.txt",
        "source.txt",
        "original.txt",
        "document.txt",
    ]
    for name in candidates:
        p = doc_dir / name
        if p.exists():
            t = p.read_text(encoding="utf-8", errors="replace")
            if t.strip():
                return t, name
    return "", ""


def _is_heading_line(s: str) -> bool:
    t = s.strip()
    if not t:
        return False

    tl = t.lower()
    if tl.startswith("chapter "):
        return True
    if tl.startswith("book "):
        return True
    if t.startswith("第") and ("章" in t or "节" in t):
        return True

    # 全大写短行
    if len(t) <= 80 and t.upper() == t and re.search(r"[A-Z]", t):
        return True

    # 数字开头短行
    if len(t) <= 80 and re.match(r"^\d+(\.|、)\s*\S+", t):
        return True

    return False


def _build_children_headings(full_text: str, start_offset: int, end_offset: int, max_nodes: int = 80) -> list[dict]:
    if start_offset < 0:
        start_offset = 0
    if end_offset <= 0 or end_offset > len(full_text):
        end_offset = len(full_text)
    if end_offset <= start_offset:
        return []

    slice_text = full_text[start_offset:end_offset]
    lines = slice_text.splitlines()

    offsets: list[int] = []
    cur = start_offset
    for ln in lines:
        offsets.append(cur)
        cur += len(ln) + 1

    hits: list[tuple[int, str]] = []
    for i, ln in enumerate(lines):
        if _is_heading_line(ln):
            title = ln.strip()
            hits.append((i, title))
            if len(hits) >= max_nodes:
                break

    if not hits:
        return []

    children: list[dict] = []
    for idx, (line_i, title) in enumerate(hits):
        so = offsets[line_i]
        eo = end_offset
        if idx + 1 < len(hits):
            eo = offsets[hits[idx + 1][0]]

        node_id = f"h_{so}"
        children.append(
            {
                "node_id": node_id,
                "title": title,
                "span_hint": {
                    "start_offset": so,
                    "end_offset": eo,
                    "span_index": max(0, so // SPAN_SIZE),
                },
                "children": [],
            }
        )

    return children


def _llm_outline_prompt(section_title: str, text: str, max_children: int) -> tuple[str, str]:
    sys = (
        "You generate document outlines.\n"
        "Return STRICT JSON only.\n"
        "Schema:\n"
        "{\n"
        '  "headings": [\n'
        '    {"title": "string"}\n'
        "  ]\n"
        "}\n"
        f"Rules:\n- Generate up to {max_children} headings.\n"
        "- Headings should be concise.\n"
        "- Do NOT invent numbering; keep numbering only if it appears in the text.\n"
        "- Avoid duplicates.\n"
    )
    user = (
        f"Section title:\n{section_title}\n\n"
        f"Section text:\n{text}\n\n"
        "Now return the JSON."
    )
    return sys, user


def _parse_llm_headings(llm_json: Any, max_children: int) -> list[str]:
    if not isinstance(llm_json, dict):
        return []
    hs = llm_json.get("headings")
    if not isinstance(hs, list):
        return []
    out: list[str] = []
    seen = set()
    for h in hs:
        if not isinstance(h, dict):
            continue
        t = str(h.get("title") or "").strip()
        if not t:
            continue
        if t in seen:
            continue
        seen.add(t)
        out.append(t)
        if len(out) >= max_children:
            break
    return out


def _build_children_llm(
    full_text: str,
    start_offset: int,
    end_offset: int,
    section_title: str,
    model: str,
    max_children: int,
) -> tuple[list[dict], dict]:
    if start_offset < 0:
        start_offset = 0
    if end_offset <= 0 or end_offset > len(full_text):
        end_offset = len(full_text)
    if end_offset <= start_offset:
        return [], {"ok": False, "error": "bad offsets", "model": model}

    slice_text = full_text[start_offset:end_offset]
    if len(slice_text) > OUTLINE_LLM_MAX_CHARS:
        slice_text = slice_text[:OUTLINE_LLM_MAX_CHARS]

    sys, user = _llm_outline_prompt(section_title=section_title, text=slice_text, max_children=max_children)

    llm_ok = False
    llm_error: Optional[str] = None
    llm_json: Any = None
    try:
        llm_json = call_llm(model=model, system_prompt=sys, user_prompt=user, response_format="json")
        llm_ok = isinstance(llm_json, (dict, list))
    except Exception as e:
        llm_error = str(e)
        llm_ok = False

    titles = _parse_llm_headings(llm_json, max_children=max_children) if llm_ok else []

    children: list[dict] = []
    if titles:
        span_len = max(1, end_offset - start_offset)
        step = max(1, span_len // max(len(titles), 1))

        for i, title in enumerate(titles):
            so = start_offset + i * step
            eo = start_offset + (i + 1) * step if i + 1 < len(titles) else end_offset
            node_id = f"llm_{start_offset}_{i:03d}"
            children.append(
                {
                    "node_id": node_id,
                    "title": title,
                    "span_hint": {
                        "start_offset": so,
                        "end_offset": eo,
                        "span_index": max(0, so // SPAN_SIZE),
                    },
                    "children": [],
                }
            )

    llm_meta = {
        "ok": llm_ok,
        "error": llm_error,
        "model": model,
        "prompt_version": OUTLINE_LLM_PROMPT_VERSION,
        "input_chars": len(slice_text),
        "input_tokens_est": _estimate_tokens_from_chars(len(slice_text)),
        "headings_count": len(children),
    }
    return children, llm_meta


def _build_minimal_chapter_tree(full_text: str) -> dict:
    lines = full_text.splitlines()
    offsets: list[int] = []
    cur = 0
    for ln in lines:
        offsets.append(cur)
        cur += len(ln) + 1

    headings: list[tuple[int, str]] = []
    for i, ln in enumerate(lines):
        if _is_heading_line(ln):
            headings.append((i, ln.strip()))

    if not headings:
        return {
            "root": {
                "node_id": "root",
                "title": "全文",
                "span_hint": {"start_offset": 0, "end_offset": len(full_text), "span_index": 0},
                "children": [],
            }
        }

    nodes: list[dict] = []
    for idx, (line_i, title) in enumerate(headings):
        start_offset = offsets[line_i]
        end_offset = len(full_text)
        if idx + 1 < len(headings):
            end_offset = offsets[headings[idx + 1][0]]

        node_id = f"ch_{idx + 1:03d}"
        nodes.append(
            {
                "node_id": node_id,
                "title": title,
                "span_hint": {
                    "start_offset": start_offset,
                    "end_offset": end_offset,
                    "span_index": max(0, start_offset // SPAN_SIZE),
                },
                "children": [],
            }
        )

    return {
        "root": {
            "node_id": "root",
            "title": "目录",
            "span_hint": {"start_offset": 0, "end_offset": len(full_text), "span_index": 0},
            "children": nodes,
        }
    }


def _find_node(tree_root: dict, node_id: str) -> Optional[dict]:
    if not isinstance(tree_root, dict):
        return None
    if tree_root.get("node_id") == node_id:
        return tree_root
    for ch in tree_root.get("children", []) or []:
        found = _find_node(ch, node_id)
        if found:
            return found
    return None


def _has_same_children(existing_children: list[dict], new_children: list[dict]) -> bool:
    try:
        a = {str(x.get("node_id")) for x in existing_children if isinstance(x, dict)}
        b = {str(x.get("node_id")) for x in new_children if isinstance(x, dict)}
        return bool(a) and a == b
    except Exception:
        return False


def _walk_outline_nodes(root: dict) -> list[dict]:
    out: list[dict] = []

    def walk(n: Any) -> None:
        if not isinstance(n, dict):
            return
        out.append(n)
        ch = n.get("children")
        if isinstance(ch, list):
            for c in ch:
                walk(c)

    walk(root)
    return out


def _translate_prompt_zh(items: list[dict]) -> tuple[str, str]:
    sys = (
        "You are a translation engine.\n"
        "Translate headings into Simplified Chinese.\n"
        "Return STRICT JSON only.\n"
        "Schema:\n"
        "{\n"
        '  "items": [\n'
        '    {"node_id":"string","title_zh":"string"}\n'
        "  ]\n"
        "}\n"
        "Rules:\n"
        "- Keep numbering like '1.2.3' unchanged.\n"
        "- Keep proper nouns if appropriate.\n"
        "- Headings should be concise.\n"
        "- Do not add extra commentary.\n"
    )

    payload = json.dumps({"items": items}, ensure_ascii=False)
    user = (
        "Translate the following outline headings to Simplified Chinese.\n"
        "Input JSON:\n"
        f"{payload}\n\n"
        "Now return the output JSON."
    )
    return sys, user


def _parse_translate_items(llm_json: Any) -> dict[str, str]:
    if not isinstance(llm_json, dict):
        return {}
    items = llm_json.get("items")
    if not isinstance(items, list):
        return {}
    out: dict[str, str] = {}
    for it in items:
        if not isinstance(it, dict):
            continue
        nid = str(it.get("node_id") or "").strip()
        tz = str(it.get("title_zh") or "").strip()
        if not nid or not tz:
            continue
        out[nid] = tz
    return out


def _chunk_translate_items(items: list[dict]) -> list[list[dict]]:
    batches: list[list[dict]] = []
    cur: list[dict] = []
    cur_chars = 0

    for it in items:
        s = json.dumps(it, ensure_ascii=False)
        if cur and (
            len(cur) >= OUTLINE_TRANSLATE_MAX_ITEMS_PER_BATCH
            or (cur_chars + len(s) > OUTLINE_TRANSLATE_MAX_CHARS_PER_BATCH)
        ):
            batches.append(cur)
            cur = []
            cur_chars = 0

        cur.append(it)
        cur_chars += len(s)

    if cur:
        batches.append(cur)

    return batches


def nisb_doc_outline_get(args: dict) -> dict:
    library_id = str(args.get("library_id") or "").strip()
    doc_id = str(args.get("doc_id") or "").strip()
    ensure = _flag(args.get("ensure"))

    if not library_id or not doc_id:
        return {"status": "error", "message": "missing library_id/doc_id"}

    doc_dir, dbg = _resolve_doc_dir(args, library_id=library_id, doc_id=doc_id)
    analysis_dir = doc_dir / "analysis"

    dbg["doc_dir_exists"] = bool(doc_dir.exists())
    dbg["doc_dir_files"] = _list_dir_filenames(doc_dir)
    dbg["analysis_dir_exists"] = bool(analysis_dir.exists())
    dbg["analysis_dir_files"] = _list_dir_filenames(analysis_dir)

    outline_jsonl_path = analysis_dir / OUTLINE_JSONL
    outline_json_path = analysis_dir / OUTLINE_JSON

    rows = _safe_read_jsonl(outline_jsonl_path)
    latest = rows[-1] if rows else None

    # legacy outline.json：只有当含 tree/root 时才复用
    if (not latest) and outline_json_path.exists():
        old = _safe_read_json(outline_json_path)
        root = None
        if isinstance(old, dict) and isinstance(old.get("root"), dict):
            root = old.get("root")
        if isinstance(old, dict) and isinstance(old.get("tree"), dict) and isinstance(old["tree"].get("root"), dict):
            root = old["tree"]["root"]
        if root:
            latest = {
                "type": "outline_legacy_json",
                "artifact_id": "outline_legacy_json",
                "version": 0,
                "created_at": old.get("created_at"),
                "library_id": library_id,
                "doc_id": doc_id,
                "params": {"source": "analysis/outline.json"},
                "params_hash": _hash_params({"source": "analysis/outline.json"}),
                "tree": {"root": root},
            }

    if (not latest) and ensure:
        full_text, source_label = _read_full_text(doc_dir)
        if not full_text.strip():
            return {
                "status": "error",
                "message": f"full_text not found/empty: {str(doc_dir)} (expected content.txt/full_text.txt/text.txt...)",
                "debug": dbg,
            }

        tree = _build_minimal_chapter_tree(full_text)
        created_at = _utc_now_iso()
        artifact_id = f"outline_{created_at.replace(':','').replace('-','').replace('.','')}"

        rec = {
            "type": "outline",
            "artifact_id": artifact_id,
            "version": len(rows) + 1,
            "created_at": created_at,
            "library_id": library_id,
            "doc_id": doc_id,
            "params": {
                "ensure": True,
                "mode": "minimal_chapter_tree",
                "generator": {"type": "rules", "model": None, "prompt_version": None},
                "text_source": source_label,
                "span_size": SPAN_SIZE,
            },
            "params_hash": _hash_params(
                {
                    "mode": "minimal_chapter_tree",
                    "text_source": source_label,
                    "span_size": SPAN_SIZE,
                    "generator": {"type": "rules", "model": None, "prompt_version": None},
                }
            ),
            "tree": tree,
        }
        _append_jsonl(outline_jsonl_path, rec)
        rows.append(rec)
        latest = rec

        user_base = _resolve_user_base(args)
        _timeline_append(
            base_path=str(user_base),
            event={
                "type": "document",
                "library_id": library_id,
                "doc_id": doc_id,
                "path": str(doc_dir),
                "date": created_at,
                "extra": {
                    "kind": "outline_generated",
                    "artifact_id": artifact_id,
                    "summary": f"Outline 生成（source={source_label}）",
                    "mode": "minimal_chapter_tree",
                },
            },
        )

    versions = [
        {
            "artifact_id": r.get("artifact_id"),
            "version": r.get("version"),
            "created_at": r.get("created_at"),
            "params": r.get("params", {}),
        }
        for r in rows[-20:]
    ]

    return {
        "status": "success",
        "library_id": library_id,
        "doc_id": doc_id,
        "latest": latest,
        "versions": versions,
        "outline_path": str(outline_jsonl_path),
        "debug": dbg,
    }


def nisb_doc_outline_expand(args: dict) -> dict:
    library_id = str(args.get("library_id") or "").strip()
    doc_id = str(args.get("doc_id") or "").strip()
    node_id = str(args.get("node_id") or "").strip()

    mode = str(args.get("mode") or "headings").strip().lower()

    llm_model = str(args.get("model") or OUTLINE_LLM_MODEL_DEFAULT).strip()
    max_children = int(args.get("max_children") or OUTLINE_LLM_MAX_CHILDREN_DEFAULT)
    force_rebuild = _flag(args.get("force_rebuild"))

    if not library_id or not doc_id or not node_id:
        return {"status": "error", "message": "missing library_id/doc_id/node_id"}

    doc_dir, dbg = _resolve_doc_dir(args, library_id=library_id, doc_id=doc_id)
    analysis_dir = doc_dir / "analysis"
    outline_jsonl_path = analysis_dir / OUTLINE_JSONL

    dbg["doc_dir_exists"] = bool(doc_dir.exists())
    dbg["doc_dir_files"] = _list_dir_filenames(doc_dir)
    dbg["analysis_dir_exists"] = bool(analysis_dir.exists())
    dbg["analysis_dir_files"] = _list_dir_filenames(analysis_dir)

    rows = _safe_read_jsonl(outline_jsonl_path)
    latest = rows[-1] if rows else None

    if not latest:
        gen = nisb_doc_outline_get({**args, "library_id": library_id, "doc_id": doc_id, "ensure": 1})
        if gen.get("status") != "success":
            return gen
        rows = _safe_read_jsonl(outline_jsonl_path)
        latest = rows[-1] if rows else None

    if not latest:
        return {"status": "error", "message": "outline not available", "debug": dbg}

    tree = latest.get("tree") or {}
    root = tree.get("root") if isinstance(tree, dict) else None
    if not isinstance(root, dict):
        return {"status": "error", "message": "bad outline tree", "debug": dbg}

    target = _find_node(root, node_id)
    if not target:
        return {"status": "error", "message": f"node not found: {node_id}", "debug": dbg}

    existing_children = target.get("children") if isinstance(target.get("children"), list) else []
    if existing_children and (not force_rebuild):
        return {"status": "success", "message": "already expanded", "latest": latest, "debug": dbg}

    hint = target.get("span_hint") if isinstance(target.get("span_hint"), dict) else {}
    start_offset = int(hint.get("start_offset") or 0)
    end_offset = int(hint.get("end_offset") or start_offset)

    full_text, source_label = _read_full_text(doc_dir)
    if not full_text.strip():
        return {"status": "error", "message": "full_text empty while expanding", "debug": dbg}

    if mode not in ("headings", "llm", "auto"):
        mode = "headings"
    if mode == "auto":
        mode = "headings"

    section_title = str(target.get("title") or node_id)

    llm_meta: dict = {
        "ok": False,
        "error": None,
        "model": None,
        "prompt_version": None,
        "input_chars": 0,
        "input_tokens_est": 0,
        "headings_count": 0,
    }
    new_children: list[dict] = []

    if mode == "llm":
        new_children, llm_meta = _build_children_llm(
            full_text=full_text,
            start_offset=start_offset,
            end_offset=end_offset,
            section_title=section_title,
            model=llm_model,
            max_children=max(1, min(max_children, 80)),
        )
    else:
        new_children = _build_children_headings(full_text, start_offset=start_offset, end_offset=end_offset, max_nodes=80)

    if not new_children:
        return {"status": "success", "message": "no headings found in this section", "latest": latest, "debug": dbg}

    if mode != "llm" and _has_same_children(existing_children, new_children):
        return {"status": "success", "message": "already expanded", "latest": latest, "debug": dbg}

    target["children"] = new_children if force_rebuild else (existing_children + new_children)

    created_at = _utc_now_iso()
    suffix = created_at.replace(":", "").replace("-", "").replace(".", "")
    artifact_id = f"outline_expand_{node_id}_{suffix}"

    params = {
        "node_id": node_id,
        "mode": mode,
        "max_children": max_children,
        "force_rebuild": force_rebuild,
        "span_size": SPAN_SIZE,
        "text_source": source_label,
        "generator": {
            "type": "llm" if mode == "llm" else "rules",
            "model": llm_model if mode == "llm" else None,
            "prompt_version": OUTLINE_LLM_PROMPT_VERSION if mode == "llm" else None,
        },
    }

    rec = {
        "type": "outline_expand",
        "artifact_id": artifact_id,
        "version": int(latest.get("version") or len(rows)) + 1,
        "created_at": created_at,
        "library_id": library_id,
        "doc_id": doc_id,
        "params": params,
        "params_hash": _hash_params(params),
        "llm": llm_meta if mode == "llm" else {"ok": False, "error": None, "model": None},
        "tree": {"root": root},
    }
    _append_jsonl(outline_jsonl_path, rec)

    user_base = _resolve_user_base(args)
    _timeline_append(
        base_path=str(user_base),
        event={
            "type": "document",
            "library_id": library_id,
            "doc_id": doc_id,
            "path": str(doc_dir),
            "date": created_at,
            "extra": {
                "kind": "outline_expanded",
                "artifact_id": artifact_id,
                "node_id": node_id,
                "summary": f"Outline expand: {node_id}",
                "mode": mode,
                "model": llm_model if mode == "llm" else None,
                "input_tokens_est": (llm_meta or {}).get("input_tokens_est") if mode == "llm" else None,
            },
        },
    )

    return {"status": "success", "artifact_id": artifact_id, "latest": rec, "debug": dbg}


def nisb_doc_outline_translate(args: dict) -> dict:
    library_id = str(args.get("library_id") or "").strip()
    doc_id = str(args.get("doc_id") or "").strip()

    target_lang = str(args.get("target_lang") or "zh").strip().lower()
    model = str(args.get("model") or OUTLINE_TRANSLATE_MODEL_DEFAULT).strip()
    force_rebuild = _flag(args.get("force_rebuild"))

    if not library_id or not doc_id:
        return {"status": "error", "message": "missing library_id/doc_id"}

    if target_lang not in ("zh", "zh-cn", "zh-hans"):
        return {"status": "error", "message": f"unsupported target_lang: {target_lang}"}

    doc_dir, dbg = _resolve_doc_dir(args, library_id=library_id, doc_id=doc_id)
    analysis_dir = doc_dir / "analysis"
    outline_jsonl_path = analysis_dir / OUTLINE_JSONL

    dbg["doc_dir_exists"] = bool(doc_dir.exists())
    dbg["doc_dir_files"] = _list_dir_filenames(doc_dir)
    dbg["analysis_dir_exists"] = bool(analysis_dir.exists())
    dbg["analysis_dir_files"] = _list_dir_filenames(analysis_dir)

    rows = _safe_read_jsonl(outline_jsonl_path)
    latest = rows[-1] if rows else None

    if not latest:
        gen = nisb_doc_outline_get({**args, "library_id": library_id, "doc_id": doc_id, "ensure": 1})
        if gen.get("status") != "success":
            return gen
        rows = _safe_read_jsonl(outline_jsonl_path)
        latest = rows[-1] if rows else None

    if not latest:
        return {"status": "error", "message": "outline not available", "debug": dbg}

    tree = latest.get("tree") or {}
    root = tree.get("root") if isinstance(tree, dict) else None
    if not isinstance(root, dict):
        return {"status": "error", "message": "bad outline tree", "debug": dbg}

    nodes = _walk_outline_nodes(root)
    total_nodes = len(nodes)

    items: list[dict] = []
    for n in nodes:
        nid = str(n.get("node_id") or "").strip()
        title = str(n.get("title") or "").strip()
        if not nid or not title:
            continue
        if (not force_rebuild) and str(n.get("title_zh") or "").strip():
            continue
        items.append({"node_id": nid, "title": title})

    if (not items) and (not force_rebuild):
        return {"status": "success", "message": "already translated", "latest": latest, "debug": dbg}

    batches = _chunk_translate_items(items)

    llm_batches: list[dict] = []
    ok_all = True
    err_all: Optional[str] = None
    translated_map: dict[str, str] = {}

    for bi, batch in enumerate(batches):
        sys, user = _translate_prompt_zh(batch)

        llm_ok = False
        llm_error: Optional[str] = None
        llm_json: Any = None
        try:
            llm_json = call_llm(model=model, system_prompt=sys, user_prompt=user, response_format="json")
            llm_ok = isinstance(llm_json, (dict, list))
        except Exception as e:
            llm_error = str(e)
            llm_ok = False

        m = _parse_translate_items(llm_json) if llm_ok else {}
        if not m:
            ok_all = False
            if not err_all:
                err_all = llm_error or f"translate batch {bi} empty/invalid json"
        translated_map.update(m)

        payload_chars = len(json.dumps({"items": batch}, ensure_ascii=False))
        llm_batches.append(
            {
                "batch_index": bi,
                "ok": llm_ok and bool(m),
                "error": llm_error,
                "items_in": len(batch),
                "items_out": len(m),
                "input_chars_est": payload_chars,
                "input_tokens_est": _estimate_tokens_from_chars(payload_chars),
            }
        )

    applied = 0
    for n in nodes:
        nid = str(n.get("node_id") or "").strip()
        if not nid:
            continue
        if nid in translated_map:
            n["title_zh"] = translated_map[nid]
            applied += 1

    created_at = _utc_now_iso()
    suffix = created_at.replace(":", "").replace("-", "").replace(".", "")
    artifact_id = f"outline_translate_{suffix}"

    params = {
        "mode": "translate_title_zh",
        "target_lang": "zh",
        "force_rebuild": force_rebuild,
        "model": model,
        "prompt_version": OUTLINE_TRANSLATE_PROMPT_VERSION,
        "translated_nodes": applied,
        "total_nodes": total_nodes,
    }

    rec = {
        "type": "outline_translate",
        "artifact_id": artifact_id,
        "version": int(latest.get("version") or len(rows)) + 1,
        "created_at": created_at,
        "library_id": library_id,
        "doc_id": doc_id,
        "params": params,
        "params_hash": _hash_params(params),
        "llm": {
            "ok": ok_all,
            "error": err_all,
            "model": model,
            "prompt_version": OUTLINE_TRANSLATE_PROMPT_VERSION,
            "batches": llm_batches,
            "input_tokens_est_total": sum(int(b.get("input_tokens_est") or 0) for b in llm_batches),
        },
        "tree": {"root": root},
    }

    _append_jsonl(outline_jsonl_path, rec)

    user_base = _resolve_user_base(args)
    _timeline_append(
        base_path=str(user_base),
        event={
            "type": "document",
            "library_id": library_id,
            "doc_id": doc_id,
            "path": str(doc_dir),
            "date": created_at,
            "extra": {
                "kind": "outline_translated",
                "artifact_id": artifact_id,
                "summary": f"Outline 翻译为中文（nodes={applied}/{total_nodes}）",
                "model": model,
            },
        },
    )

    return {"status": "success", "artifact_id": artifact_id, "latest": rec, "debug": dbg}

