from __future__ import annotations

import json
import os
import re
import uuid
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Set

from tools.timeline import _append_timeline_activity
from core.openai_utils import call_llm

DEFAULT_DATA_ROOT = Path(os.environ.get("NISB_BASE_PATH", "/data")).resolve()
QA_JSONL = "qa.jsonl"

EVIDENCE_SNIPPET_CHARS = int(os.getenv("NISB_QA_EVIDENCE_SNIPPET_CHARS", "1600"))
FOLLOWUP_TURNS_DEFAULT = 5
FOLLOWUP_CTX_MAX_CHARS = int(os.getenv("NISB_QA_FOLLOWUP_CTX_MAX_CHARS", "4500"))


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clean_id(x: Any) -> str:
    return str(x or "").strip()


def _clean(s: str) -> str:
    return re.sub(r"\s+", " ", str(s or "").strip())


def _short(s: str, n: int) -> str:
    t = _clean(s)
    return t[:n] + ("…" if len(t) > n else "")


def _hash_params(d: dict) -> str:
    payload = json.dumps(d, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()[:16]


def _append_jsonl(path: Path, obj: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")


def _safe_read_jsonl(path: Path, max_rows: int = 12000) -> List[dict]:
    if not path.exists():
        return []
    rows: List[dict] = []
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            raw = line.strip()
            if not raw:
                continue
            try:
                rows.append(json.loads(raw))
            except Exception:
                continue
            if len(rows) >= max_rows:
                break
    return rows


def _resolve_user_base(args: dict) -> Path:
    base = str(args.get("_base_path") or "").strip()
    if base:
        return Path(base)

    uid = str(args.get("user_id") or args.get("uid") or "default").strip() or "default"
    return DEFAULT_DATA_ROOT / "users" / uid


def _candidate_doc_dirs(user_base: Path, library_id: str, doc_id: str) -> List[Path]:
    return [
        user_base / "libraries" / library_id / "docs" / doc_id,
        user_base / library_id / "docs" / doc_id,
        user_base / "docs" / doc_id,
    ]


def _resolve_doc_dir(args: dict, library_id: str, doc_id: str) -> Tuple[Path, dict]:
    user_base = _resolve_user_base(args)
    cands = _candidate_doc_dirs(user_base, library_id, doc_id)

    dbg = {
        "data_root": str(DEFAULT_DATA_ROOT),
        "user_base": str(user_base),
        "candidates": [str(x) for x in cands],
        "picked": str(cands[0]),
    }
    for p in cands:
        if p.exists() and p.is_dir():
            dbg["picked"] = str(p)
            return p, dbg
    return cands[0], dbg


def _import_evidence_tool() -> Any:
    from tools.doc.doc_evidence_scope import nisb_doc_evidence_scope  # type: ignore

    return nisb_doc_evidence_scope


def _get_arg(args: Dict[str, Any], *names: str, default: Any = None) -> Any:
    for n in names:
        if n in args:
            return args.get(n)
    return default


def _get_int(args: Dict[str, Any], *names: str, default: int) -> int:
    v = _get_arg(args, *names, default=default)
    try:
        return int(v)
    except Exception:
        return int(default)


def _get_bool(args: Dict[str, Any], *names: str, default: bool = False) -> bool:
    v = _get_arg(args, *names, default=default)
    if isinstance(v, bool):
        return v
    s = str(v).strip().lower()
    if s in ("1", "true", "yes", "y", "on"):
        return True
    if s in ("0", "false", "no", "n", "off"):
        return False
    return bool(default)


def _json_safe(x: Any) -> Any:
    if x is None or isinstance(x, (str, int, float, bool)):
        return x
    if isinstance(x, dict):
        return {str(k): _json_safe(v) for k, v in x.items()}
    if isinstance(x, (list, tuple, set)):
        return [_json_safe(v) for v in x]
    return str(x)


def _std_conv_id(args: Dict[str, Any]) -> Optional[str]:
    v = _clean_id(
        _get_arg(
            args,
            "conv_id",
            "convId",
            "conversation_id",
            "conversationId",
            "chat_id",
            default="",
        )
    )
    return v or None


def _std_request_id(args: Dict[str, Any]) -> str:
    v = _clean_id(_get_arg(args, "request_id", "requestId", "rid", default=""))
    return v or f"req_{uuid.uuid4().hex[:16]}"


def _std_mcp_overrides(args: Dict[str, Any]) -> Any:
    v = _get_arg(args, "mcp_overrides", "mcpOverrides", default=None)
    return _json_safe(v)


def _build_standard_result(
    *,
    args: Dict[str, Any],
    status: str,
    message: str,
    mode_used: Optional[str],
    response: Any,
    qa_id: Optional[str] = None,
    group_id: Optional[str] = None,
    citations: Optional[List[Dict[str, Any]]] = None,
    rag_mode: Optional[str] = None,
    rss_evidence: Any = None,
    market_evidence: Any = None,
    evidence_query: Any = None,
    evidence_tools: Optional[List[Any]] = None,
    evidence_result: Any = None,
    tool_calls: Optional[List[Any]] = None,
    tool_results: Optional[List[Any]] = None,
) -> Dict[str, Any]:
    out = {
        "conv_id": _std_conv_id(args),
        "request_id": _std_request_id(args),
        "rag_mode": rag_mode,
        "mcp_overrides": _std_mcp_overrides(args),
        "mode_used": mode_used,
        "rss_evidence": _json_safe(rss_evidence if rss_evidence is not None else []),
        "market_evidence": _json_safe(market_evidence if market_evidence is not None else []),
        "evidence_query": _json_safe(evidence_query),
        "evidence_tools": _json_safe(evidence_tools or []),
        "evidence_result": _json_safe(evidence_result if evidence_result is not None else {}),
        "qa_id": qa_id,
        "group_id": group_id,
        "citations": _json_safe(citations or []),
        "response": _json_safe(response),
        "status": _clean_id(status) or "success",
        "message": str(message or ""),
        "tool_calls": _json_safe(tool_calls or []),
        "tool_results": _json_safe(tool_results or []),
    }
    return out


def _qa_record_to_standard_item(qa: Dict[str, Any]) -> Dict[str, Any]:
    params = qa.get("params") if isinstance(qa.get("params"), dict) else {}
    dbg = qa.get("debug") if isinstance(qa.get("debug"), dict) else {}
    rag_mode = _clean_id(
        qa.get("rag_mode")
        or qa.get("evidence_scope")
        or params.get("evidence_scope")
        or qa.get("store_scope")
        or "doc"
    ) or "doc"
    group_id = _clean_id(qa.get("group_id") or qa.get("thread_id") or qa.get("qa_id")) or None
    response = str(qa.get("response") or qa.get("answer") or "")
    mode_used = _clean_id(qa.get("mode_used") or params.get("answer_mode") or "qa")
    evidence_query = _clean_id(qa.get("evidence_query") or params.get("search_query") or "") or None
    citations = qa.get("citations") if isinstance(qa.get("citations"), list) else []
    evidence_tools = qa.get("evidence_tools")
    if not isinstance(evidence_tools, list):
        evidence_tools = ["nisb_doc_evidence_scope"]

    return {
        "conv_id": None,
        "request_id": None,
        "rag_mode": rag_mode,
        "mcp_overrides": None,
        "mode_used": mode_used,
        "rss_evidence": _json_safe(dbg.get("rss_days_args") or []),
        "market_evidence": [],
        "evidence_query": evidence_query,
        "evidence_tools": evidence_tools,
        "evidence_result": {
            "record_meta": {
                "library_id": qa.get("library_id"),
                "doc_id": qa.get("doc_id"),
                "parent_qa_id": qa.get("parent_qa_id"),
                "depth": qa.get("depth"),
                "created_at": qa.get("created_at"),
            },
            "evidence": _json_safe(qa.get("evidence") or []),
        },
        "qa_id": _clean_id(qa.get("qa_id")) or None,
        "group_id": group_id,
        "citations": _json_safe(citations),
        "response": response,
        "status": "success",
        "message": "",
        "tool_calls": [],
        "tool_results": [],
    }


def _call_llm_compat(
    *,
    model: str,
    system_prompt: str,
    user_prompt: str,
    response_format: str,
    max_output_tokens: Optional[int] = None,
) -> Any:
    if max_output_tokens is None:
        return call_llm(model=model, system_prompt=system_prompt, user_prompt=user_prompt, response_format=response_format)

    max_output_tokens = int(max(200, min(int(max_output_tokens), 8000)))

    try:
        return call_llm(
            model=model,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            response_format=response_format,
            max_output_tokens=max_output_tokens,
        )
    except TypeError:
        try:
            return call_llm(
                model=model,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                response_format=response_format,
                max_tokens=max_output_tokens,
            )
        except TypeError:
            return call_llm(model=model, system_prompt=system_prompt, user_prompt=user_prompt, response_format=response_format)


def _build_qa_index(rows: List[dict]) -> Dict[str, dict]:
    qa_map: Dict[str, dict] = {}
    for r in rows:
        if not isinstance(r, dict):
            continue
        if r.get("type") != "qa":
            continue
        qa_id = str(r.get("qa_id") or "").strip()
        if not qa_id:
            continue
        qa_map[qa_id] = r
    return qa_map


def _build_children_map(qa_map: Dict[str, dict]) -> Dict[str, List[str]]:
    children: Dict[str, List[str]] = {}
    for qa_id, qa in qa_map.items():
        pid = str(qa.get("parent_qa_id") or "").strip()
        if not pid:
            continue
        children.setdefault(pid, []).append(qa_id)
    return children


def _collect_descendants(children_map: Dict[str, List[str]], root_id: str) -> Set[str]:
    out: Set[str] = set()
    stack = [root_id]
    while stack:
        cur = stack.pop()
        kids = children_map.get(cur) or []
        for k in kids:
            if k in out:
                continue
            out.add(k)
            stack.append(k)
    return out


def _compute_deleted_set(rows: List[dict], qa_map: Dict[str, dict]) -> Set[str]:
    children_map = _build_children_map(qa_map)
    deleted: Set[str] = set()

    for r in rows:
        if not isinstance(r, dict):
            continue
        if r.get("type") != "qa_delete":
            continue
        target = str(r.get("target_qa_id") or "").strip()
        if not target:
            continue
        scope = str(r.get("scope") or "single").strip()
        thread_id = str(r.get("thread_id") or "").strip()

        deleted.add(target)

        if scope == "single":
            continue

        if scope == "subtree":
            deleted |= _collect_descendants(children_map, target)
            continue

        if scope == "thread":
            if not thread_id:
                tqa = qa_map.get(target) or {}
                thread_id = str(tqa.get("thread_id") or tqa.get("qa_id") or target).strip()

            for qa_id, qa in qa_map.items():
                tid = str(qa.get("thread_id") or qa.get("qa_id") or "").strip()
                if tid == thread_id:
                    deleted.add(qa_id)

            continue

    return deleted


def _find_qa_by_id(qa_map: Dict[str, dict], qa_id: str) -> Optional[dict]:
    qa_id = str(qa_id or "").strip()
    if not qa_id:
        return None
    qa = qa_map.get(qa_id)
    return qa if isinstance(qa, dict) else None


def _build_followup_context_chain(
    qa_map: Dict[str, dict],
    parent_qa_id: str,
    max_turns: int = FOLLOWUP_TURNS_DEFAULT,
    max_chars: int = FOLLOWUP_CTX_MAX_CHARS,
) -> Tuple[str, Dict[str, Any]]:
    dbg: Dict[str, Any] = {"max_turns": max_turns, "max_chars": max_chars, "picked": []}
    parent_qa_id = str(parent_qa_id or "").strip()
    if not parent_qa_id:
        return "", dbg

    chain: List[dict] = []
    cur_id = parent_qa_id
    steps = 0

    while cur_id and steps < max_turns:
        qa = _find_qa_by_id(qa_map, cur_id)
        if not qa:
            break
        chain.append(qa)
        dbg["picked"].append(str(qa.get("qa_id") or cur_id))
        cur_id = str(qa.get("parent_qa_id") or "").strip()
        steps += 1

    chain.reverse()

    lines: List[str] = ["Follow-up context (last turns, for reference only):"]
    total = len(lines[0]) + 1

    for i, qa in enumerate(chain, start=1):
        q = _short(str(qa.get("question") or ""), 240)
        a = _short(str(qa.get("answer") or qa.get("response") or ""), 420)
        chunk = f"[Turn -{len(chain)-i+1}] Q: {q}\nA: {a}\n"
        if total + len(chunk) > max_chars:
            break
        lines.append(chunk)
        total += len(chunk)

    return "\n".join(lines).strip(), dbg


def _normalize_answer_lang(value: Any) -> str:
    raw = str(value or "").strip().lower().replace("_", "-")
    if not raw:
        return ""
    base = raw.split("-")[0]
    if re.fullmatch(r"[a-z]{2,3}", base):
        return base
    return ""


def _detect_question_answer_lang(question: str) -> str:
    text = str(question or "").strip()
    if not text:
        return ""

    has_kana = bool(re.search(r"[\u3040-\u30ff]", text))
    has_cjk = bool(re.search(r"[\u4e00-\u9fff]", text))
    has_hangul = bool(re.search(r"[\uac00-\ud7af]", text))
    has_latin = bool(re.search(r"[A-Za-zÀ-ÖØ-öø-ÿ]", text))
    has_cyrillic = bool(re.search(r"[\u0400-\u04ff]", text))
    has_arabic = bool(re.search(r"[\u0600-\u06ff]", text))

    if has_kana:
        return "ja"
    if has_hangul:
        return "ko"
    if has_cjk:
        return "zh"
    if has_latin and not has_cyrillic and not has_arabic:
        return "en"
    return ""


def _resolve_answer_lang(args: Dict[str, Any], question: str = "") -> str:
    from_question = _detect_question_answer_lang(question)
    if from_question:
        return from_question

    from_explicit = _normalize_answer_lang(
        _get_arg(
            args,
            "qa_answer_lang",
            "qaAnswerLang",
            "answer_lang",
            "answerLang",
            default="",
        )
    )
    if from_explicit:
        return from_explicit

    from_locale = _normalize_answer_lang(
        _get_arg(args, "locale", "ui_locale", "uiLocale", default="")
    )
    if from_locale:
        return from_locale

    return "en"


def _pick_lang_text(answer_lang: str, mapping: Dict[str, str]) -> str:
    lang = _normalize_answer_lang(answer_lang) or "en"
    if lang in mapping:
        return mapping[lang]
    base = lang.split("-")[0]
    if base in mapping:
        return mapping[base]
    return mapping.get("en") or next(iter(mapping.values()))


def _answer_language_instruction(answer_lang: str) -> str:
    lang = _normalize_answer_lang(answer_lang) or "en"
    if lang == "zh":
        return "Simplified Chinese"
    if lang == "en":
        return "English"
    if lang == "ja":
        return "Japanese"
    if lang == "it":
        return "Italian"
    if lang == "ko":
        return "Korean"
    return f"Prefer language code '{lang}'. If that is unreliable, use natural English."


def _highlights_heading(answer_lang: str) -> str:
    # Unified English heading to avoid scattered language hard-coding.
    return "Key points:"


def _fallback_no_evidence_answer(question: str, answer_lang: str) -> str:
    # Single natural-English fallback; no per-language hard-coded templates.
    return (
        "No evidence spans directly relevant to this question were retrieved, so a citation-backed "
        "answer cannot be provided at the moment.\n"
        f"Question: {question}"
    )


def _fallback_claim_prefix(answer_lang: str, idx: int) -> str:
    # Single natural-English prefix; no per-language hard-coded variants.
    return f"Key point {idx}: "


def _fallback_answer_intro(answer_lang: str) -> str:
    # Single natural-English intro; no per-language hard-coded variants.
    return "Based on the retrieved evidence spans, these are the most supportable points:"


def _build_search_plan(question: str, llm_model: str, extra_context: str = "") -> Tuple[Dict[str, Any], Dict[str, Any]]:
    sys = (
        "You are a retrieval planner for document QA.\n"
        "Return a STRICT JSON object with keys: query_en, terms, avoid.\n"
        "Compatibility note: query_en is a legacy field name. Populate it with the best concise retrieval query "
        "in the language most useful for finding evidence. Do not force English when another language is better.\n"
        "Rules:\n"
        "- query_en: a short, high-signal retrieval query.\n"
        "- terms: 3-10 keywords or short phrases that should improve retrieval.\n"
        "- avoid: optional words or notes to avoid; can be empty.\n"
        "- If extra context is provided, use it to resolve references.\n"
        "- Output JSON only.\n"
    )
    user = f"Question:\n{question}\n\n{extra_context}\n\nReturn JSON now."

    try:
        j = _call_llm_compat(model=llm_model, system_prompt=sys, user_prompt=user, response_format="json")
        plan = {
            "query_en": str((j or {}).get("query_en") or "").strip(),
            "terms": (j or {}).get("terms") if isinstance((j or {}).get("terms"), list) else [],
            "avoid": (j or {}).get("avoid") if isinstance((j or {}).get("avoid"), list) else [],
        }
        if not plan["query_en"]:
            plan["query_en"] = question
        return plan, {"used": "llm_plan", "plan": plan}
    except Exception as e:
        plan = {"query_en": question, "terms": [], "avoid": []}
        return plan, {"used": "fallback_plan", "error": str(e)[:300], "plan": plan}


def _compile_search_query(question: str, plan: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
    base = str(plan.get("query_en") or "").strip() or question.strip()
    terms = plan.get("terms") if isinstance(plan.get("terms"), list) else []

    merged = " ".join([base] + [str(x) for x in terms])
    merged_low = merged.lower()  # kept for debug parity

    # Domain-specific triggers removed; rely on general retrieval planning.
    need_confess = False

    if need_confess and ("confess" not in merged_low):
        terms = list(terms)

    uniq_terms: List[str] = []
    seen = set()
    for t in terms:
        tt = str(t).strip()
        if not tt:
            continue
        k = tt.lower()
        if k in seen:
            continue
        seen.add(k)
        uniq_terms.append(tt)

    query = (base + " " + " ".join(uniq_terms)).strip() if uniq_terms else base
    dbg = {
        "base": base,
        "terms": uniq_terms,
        "need_confess_guardrail": need_confess,
    }
    return query, dbg


def _normalize_evidence_items(
    ev_res: dict,
    max_evidence: int,
    *,
    default_library_id: str,
    default_doc_id: str,
) -> List[Dict[str, Any]]:
    raw: List[Any] = []
    if isinstance(ev_res, dict) and ev_res.get("status") == "success":
        raw = list(ev_res.get("items") or [])

    out: List[Dict[str, Any]] = []
    for it in raw:
        if not isinstance(it, dict):
            continue

        lib_id = str(it.get("library_id") or default_library_id or "").strip()
        doc_id = str(it.get("doc_id") or default_doc_id or "").strip()
        if not lib_id or not doc_id:
            continue

        span_raw = it.get("span_index")
        try:
            span_i = int(span_raw) if span_raw is not None else None
        except Exception:
            span_i = None
        if span_i is None:
            continue

        evidence_id = it.get("evidence_id") or it.get("id")

        offset = it.get("char_start")
        if offset is None:
            offset = it.get("offset")
        if offset is not None:
            try:
                offset = int(offset)
            except Exception:
                pass

        excerpt = it.get("quote")
        if not excerpt:
            excerpt = it.get("excerpt")
        if not excerpt:
            excerpt = it.get("text")
        excerpt = str(excerpt or "")

        out.append(
            {
                "evidence_id": evidence_id,
                "source_type": str(it.get("source_type") or "library_doc"),
                "library_id": lib_id,
                "doc_id": doc_id,
                "doc_title": str(it.get("doc_title") or ""),
                "span_index": span_i,
                "relevance": it.get("relevance"),
                "offset": offset,
                "excerpt": excerpt,
                "chunk_text": str(it.get("chunk_text") or ""),
            }
        )
        if len(out) >= int(max_evidence or 0):
            break

    return out


def _build_evidence_lines(evidence: List[Dict[str, Any]]) -> str:
    ev_lines = []
    for idx, ev in enumerate(evidence, start=1):
        lib_id = str(ev.get("library_id") or "")
        doc_id = str(ev.get("doc_id") or "")
        span = ev.get("span_index")

        excerpt = str(ev.get("excerpt") or "").strip()
        chunk_text = str(ev.get("chunk_text") or "").strip()

        payload = excerpt or chunk_text
        payload = payload[:EVIDENCE_SNIPPET_CHARS]

        ev_lines.append(f"[E{idx}] library_id={lib_id} doc_id={doc_id} span_index={span}\n{payload}")

    return "\n\n".join(ev_lines)


def _llm_prompt_rich(
    question: str,
    evidence: List[Dict[str, Any]],
    extra_context: str = "",
    min_citations: int = 4,
    max_citations: int = 12,
    answer_lang: str = "en",
) -> Tuple[str, str]:
    min_citations = max(1, min(int(min_citations or 4), 20))
    max_citations = max(min_citations, min(int(max_citations or 12), 30))
    lang_hint = _answer_language_instruction(answer_lang)

    sys = (
        "You are a careful research assistant.\n"
        "You must ONLY use the provided evidence spans.\n"
        "Return a STRICT JSON object only.\n"
        "Schema:\n"
        "{\n"
        '  "answer": string,\n'
        '  "highlights": string[],\n'
        '  "citations": [{"library_id": string, "doc_id": string, "span_index": number, "quote": string, "note": string}]\n'
        "}\n"
        "Rules:\n"
        f"- Output language: {lang_hint}.\n"
        "- answer: natural paragraphs, not a rigid template.\n"
        "- highlights: 3-8 short takeaways in the same output language.\n"
        f"- citations MUST be non-empty; produce {min_citations}-{max_citations} items.\n"
        "- Every citation MUST use (library_id, doc_id, span_index) that appears in evidence.\n"
        "- quote MUST be a short exact excerpt from evidence (<= 220 chars).\n"
        "- If evidence is insufficient, say so explicitly in the answer.\n"
        "- Do not output markdown or code fences. JSON only.\n"
    )

    user = (
        f"Question:\n{question}\n\n"
        f"{extra_context}\n\n"
        "Evidence spans:\n\n"
        f"{_build_evidence_lines(evidence)}\n\n"
        "Now return the JSON object."
    )
    return sys, user


def _fallback_answer(
    question: str,
    evidence: List[Dict[str, Any]],
    *,
    default_library_id: str,
    default_doc_id: str,
    answer_lang: str = "en",
) -> Dict[str, Any]:
    if not evidence:
        return {
            "answer": _fallback_no_evidence_answer(question, answer_lang),
            "claims": [],
            "citations": [],
        }

    claims = []
    citations = []
    for i, ev in enumerate(evidence[:6], start=1):
        lib = str(ev.get("library_id") or default_library_id)
        doc = str(ev.get("doc_id") or default_doc_id)
        span = ev.get("span_index")

        ex = ev.get("excerpt") or ev.get("chunk_text") or ""
        claims.append(f"{_fallback_claim_prefix(answer_lang, i)}{_short(ex, 180)}")
        citations.append(
            {
                "library_id": lib,
                "doc_id": doc,
                "span_index": span,
                "quote": _short(ex, 220),
                "note": "evidence_excerpt",
            }
        )

    answer = _fallback_answer_intro(answer_lang) + "\n" + "\n".join(f"- {c}" for c in claims)
    return {"answer": answer, "claims": claims, "citations": citations}


def _normalize_citations(
    answer_pack: Dict[str, Any],
    evidence_key_set: Optional[Set[Tuple[str, str, int]]] = None,
    *,
    default_library_id: str,
    default_doc_id: str,
) -> List[Dict[str, Any]]:
    citations_norm: List[Dict[str, Any]] = []

    for c in (answer_pack.get("citations") or []):
        if not isinstance(c, dict):
            continue

        lib_id = str(c.get("library_id") or default_library_id or "").strip()
        doc_id = str(c.get("doc_id") or default_doc_id or "").strip()

        span = c.get("span_index")
        try:
            span_i = int(span) if span is not None else None
        except Exception:
            span_i = None

        if not lib_id or not doc_id or span_i is None:
            continue

        if evidence_key_set is not None and (lib_id, doc_id, span_i) not in evidence_key_set:
            continue

        item: Dict[str, Any] = {
            "library_id": lib_id,
            "doc_id": doc_id,
            "span_index": span_i,
            "quote": str(c.get("quote") or ""),
            "note": str(c.get("note") or ""),
        }

        doc_title = str(c.get("doc_title") or c.get("title") or "").strip()
        published_at = str(c.get("published_at") or c.get("doc_published_at") or "").strip()
        source_type = str(c.get("source_type") or "").strip()

        if doc_title:
            item["doc_title"] = doc_title
        if published_at:
            item["published_at"] = published_at
        if source_type:
            item["source_type"] = source_type

        citations_norm.append(item)

    return citations_norm


def _delete_qa_append_event(
    qa_path: Path,
    user_base: Path,
    library_id: str,
    doc_id: str,
    target_qa: dict,
    scope: str,
) -> Dict[str, Any]:
    created_at = _utc_now_iso()
    target_id = str(target_qa.get("qa_id") or "").strip()
    thread_id = str(target_qa.get("thread_id") or target_qa.get("qa_id") or "").strip() or target_id

    ev = {
        "type": "qa_delete",
        "version": 1,
        "created_at": created_at,
        "library_id": library_id,
        "doc_id": doc_id,
        "target_qa_id": target_id,
        "thread_id": thread_id,
        "scope": scope,
    }
    _append_jsonl(qa_path, ev)

    _append_timeline_activity(
        base_path=str(user_base),
        event={
            "type": "document",
            "library_id": library_id,
            "doc_id": doc_id,
            "path": str(qa_path.parent.parent),
            "date": created_at,
            "extra": {
                "kind": "library_doc_qa_delete",
                "target_qa_id": target_id,
                "thread_id": thread_id,
                "scope": scope,
            },
        },
    )

    return ev


def nisb_doc_qa_ask(args: Dict[str, Any]) -> Dict[str, Any]:
    action = str(args.get("action") or "ask").strip().lower()

    library_id = str(args.get("library_id") or args.get("libraryid") or "").strip()
    doc_id = str(args.get("doc_id") or args.get("docid") or "").strip()

    if not library_id or not doc_id:
        return _build_standard_result(
            args=args,
            status="error",
            message="missing library_id/doc_id",
            mode_used="qa_doc",
            response="",
            rag_mode="doc",
        )

    doc_dir, dbg = _resolve_doc_dir(args, library_id=library_id, doc_id=doc_id)
    qa_path = doc_dir / "analysis" / QA_JSONL
    user_base = _resolve_user_base(args)

    rows_all = _safe_read_jsonl(qa_path, max_rows=12000)
    qa_map = _build_qa_index(rows_all)
    deleted_set = _compute_deleted_set(rows_all, qa_map)

    if action == "delete":
        qa_id = str(args.get("qa_id") or args.get("target_qa_id") or args.get("qaid") or "").strip()
        if not qa_id:
            return _build_standard_result(
                args=args,
                status="error",
                message="missing qa_id for delete",
                mode_used="qa_delete",
                response="",
                rag_mode="doc",
            )

        target_qa = _find_qa_by_id(qa_map, qa_id)
        if not target_qa:
            return _build_standard_result(
                args=args,
                status="error",
                message=f"qa_id not found: {qa_id}",
                mode_used="qa_delete",
                response="",
                rag_mode="doc",
                qa_id=qa_id,
            )

        scope_del = str(args.get("scope") or "auto").strip().lower()
        if scope_del == "auto":
            is_followup = bool(str(target_qa.get("parent_qa_id") or "").strip())
            scope_del = "subtree" if is_followup else "thread"

        if scope_del not in ("single", "subtree", "thread"):
            return _build_standard_result(
                args=args,
                status="error",
                message=f"invalid scope: {scope_del}",
                mode_used="qa_delete",
                response="",
                rag_mode="doc",
                qa_id=qa_id,
            )

        ev = _delete_qa_append_event(
            qa_path=qa_path,
            user_base=user_base,
            library_id=library_id,
            doc_id=doc_id,
            target_qa=target_qa,
            scope=scope_del,
        )

        rows2 = rows_all + [ev]
        qa_map2 = _build_qa_index(rows2)
        deleted2 = _compute_deleted_set(rows2, qa_map2)
        group_id = _clean_id(target_qa.get("thread_id") or target_qa.get("qa_id")) or qa_id

        return _build_standard_result(
            args=args,
            status="success",
            message="success",
            mode_used="qa_delete",
            response={"action": "delete", "deleted": {"qa_id": qa_id, "scope": scope_del}},
            qa_id=qa_id,
            group_id=group_id,
            rag_mode="doc",
            evidence_query=None,
            evidence_tools=[],
            evidence_result={
                "deleted_count": len(deleted2) - len(deleted_set) if len(deleted2) >= len(deleted_set) else len(deleted2),
                "qa_path": str(qa_path),
                "event": ev,
                "debug": dbg,
            },
            tool_calls=[],
            tool_results=[],
        )

    question = str(args.get("question") or "").strip()
    parent_qa_id = str(
        args.get("parent_qa_id")
        or args.get("parentQaId")
        or args.get("parentqaid")
        or args.get("parent_qaid")
        or ""
    ).strip()

    if not question:
        return _build_standard_result(
            args=args,
            status="error",
            message="missing question",
            mode_used="qa_doc",
            response="",
            rag_mode="doc",
        )

    if parent_qa_id:
        if parent_qa_id in deleted_set:
            return _build_standard_result(
                args=args,
                status="error",
                message="parent QA is deleted; cannot follow up",
                mode_used="qa_doc",
                response="",
                rag_mode="doc",
                qa_id=parent_qa_id,
            )
        parent_qa = _find_qa_by_id(qa_map, parent_qa_id)
        if not parent_qa:
            return _build_standard_result(
                args=args,
                status="error",
                message=f"parent QA not found: {parent_qa_id}",
                mode_used="qa_doc",
                response="",
                rag_mode="doc",
                qa_id=parent_qa_id,
            )

    top_k = _get_int(args, "top_k", "topk", default=18)
    max_evidence = _get_int(args, "max_evidence", "maxevidence", default=14)
    max_chars = _get_int(args, "max_chars", "maxchars", default=14000)

    llm_model = str(args.get("model") or os.getenv("OPENAI_QA_MODEL", "gpt-4o-mini")).strip()
    force_fallback = bool(args.get("force_fallback") or False)

    answer_lang = _resolve_answer_lang(args, question=question)
    req_answer_mode = str(_get_arg(args, "answer_mode", "answerMode", default="llm_rich") or "llm_rich").strip()

    min_citations = _get_int(args, "min_citations", "minCitations", default=4)
    max_citations = _get_int(args, "max_citations", "maxCitations", default=12)
    max_output_tokens = _get_int(args, "max_output_tokens", "maxOutputTokens", default=2200)

    evidence_scope = str(
        args.get("evidence_scope")
        or args.get("evidenceScope")
        or args.get("scope")
        or "doc"
    ).strip().lower()
    if evidence_scope not in ("doc", "library", "global"):
        evidence_scope = "doc"

    followup_ctx = ""
    followup_dbg: Dict[str, Any] = {}
    thread_id = ""
    depth = 0

    if parent_qa_id:
        parent_qa = _find_qa_by_id(qa_map, parent_qa_id) or {}
        thread_id = str(parent_qa.get("thread_id") or parent_qa.get("qa_id") or "").strip()
        try:
            depth = int(parent_qa.get("depth") or 0) + 1
        except Exception:
            depth = 1

        followup_ctx, followup_dbg = _build_followup_context_chain(
            qa_map=qa_map,
            parent_qa_id=parent_qa_id,
            max_turns=_get_int(args, "memory_turns", "memoryturns", default=FOLLOWUP_TURNS_DEFAULT),
            max_chars=_get_int(args, "memory_max_chars", "memorymaxchars", default=FOLLOWUP_CTX_MAX_CHARS),
        )

    plan, plan_dbg = _build_search_plan(question, llm_model=llm_model, extra_context=followup_ctx)
    search_query, compile_dbg = _compile_search_query(question, plan)

    try:
        evidence_tool = _import_evidence_tool()
    except Exception as e:
        return _build_standard_result(
            args=args,
            status="error",
            message=f"qa_ask: evidence tool import failed: {e}",
            mode_used="qa_doc",
            response="",
            rag_mode=evidence_scope,
            evidence_query=search_query,
            evidence_tools=["nisb_doc_evidence_scope"],
            evidence_result={"debug": dbg},
            tool_calls=[{"tool_name": "nisb_doc_evidence_scope", "status": "import_error"}],
            tool_results=[],
        )

    tool_calls = [
        {
            "tool_name": "nisb_doc_evidence_scope",
            "args": {
                "scope": evidence_scope,
                "library_id": library_id,
                "doc_id": doc_id,
                "query": search_query,
                "top_k": top_k,
                "max_chars": max_chars,
                "include_text": True,
            },
        }
    ]

    ev_res = evidence_tool(
        {
            **args,
            "scope": evidence_scope,
            "library_id": library_id,
            "doc_id": doc_id,
            "query": search_query,
            "top_k": top_k,
            "max_chars": max_chars,
            "include_text": True,
        }
    )

    evidence = _normalize_evidence_items(
        ev_res if isinstance(ev_res, dict) else {},
        max_evidence=max_evidence,
        default_library_id=library_id,
        default_doc_id=doc_id,
    )

    tool_results = [
        {
            "tool_name": "nisb_doc_evidence_scope",
            "status": str((ev_res or {}).get("status") if isinstance(ev_res, dict) else "unknown"),
            "count": len(evidence),
        }
    ]

    evidence_key_set = set(
        (str(x.get("library_id") or ""), str(x.get("doc_id") or ""), int(x.get("span_index")))
        for x in evidence
        if isinstance(x.get("span_index"), int)
    )

    llm_ok = False
    llm_error: Optional[str] = None
    llm_raw_preview: str = ""
    answer_mode_used = "fallback_template_v2"

    if force_fallback or (not evidence):
        answer_pack = _fallback_answer(
            question,
            evidence,
            default_library_id=library_id,
            default_doc_id=doc_id,
            answer_lang=answer_lang,
        )
    else:
        try:
            mode = req_answer_mode.lower()
            if mode in ("llm_json_structured_v2", "structured", "json_structured"):
                mode = "llm_rich"

            sys, user = _llm_prompt_rich(
                question=question,
                evidence=evidence,
                extra_context=followup_ctx,
                min_citations=min_citations,
                max_citations=max_citations,
                answer_lang=answer_lang,
            )

            llm_json = _call_llm_compat(
                model=llm_model,
                system_prompt=sys,
                user_prompt=user,
                response_format="json",
                max_output_tokens=max_output_tokens,
            )

            answer_text = str((llm_json or {}).get("answer") or "").strip()
            highlights = (llm_json or {}).get("highlights") if isinstance((llm_json or {}).get("highlights"), list) else []
            highlights = [str(x).strip() for x in highlights if str(x).strip()]

            if highlights:
                answer_text = (
                    answer_text
                    + "\n\n"
                    + _highlights_heading(answer_lang)
                    + "\n"
                    + "\n".join([f"- {x}" for x in highlights])
                ).strip()

            answer_pack = {
                "answer": answer_text,
                "claims": highlights,
                "citations": (llm_json or {}).get("citations") if isinstance((llm_json or {}).get("citations"), list) else [],
            }

            citations_norm_tmp = _normalize_citations(
                answer_pack,
                evidence_key_set=evidence_key_set,
                default_library_id=library_id,
                default_doc_id=doc_id,
            )
            if len(citations_norm_tmp) == 0:
                raise ValueError("CITATION_GATE_FAILED: citations empty")

            llm_ok = True
            answer_mode_used = "llm_rich"

        except Exception as e:
            llm_ok = False
            llm_error = str(e)
            llm_raw_preview = _short(llm_error, 900)
            answer_pack = _fallback_answer(
                question,
                evidence,
                default_library_id=library_id,
                default_doc_id=doc_id,
                answer_lang=answer_lang,
            )
            answer_mode_used = "fallback_template_v2"

    citations_norm = _normalize_citations(
        answer_pack,
        evidence_key_set=evidence_key_set,
        default_library_id=library_id,
        default_doc_id=doc_id,
    )

    created_at = _utc_now_iso()
    qa_id = f"qa_{created_at.replace(':','').replace('-','').replace('.','')}_{uuid.uuid4().hex[:8]}"

    if not thread_id:
        thread_id = qa_id

    memory_turns = _get_int(args, "memory_turns", "memoryturns", default=FOLLOWUP_TURNS_DEFAULT)
    memory_max_chars = _get_int(args, "memory_max_chars", "memorymaxchars", default=FOLLOWUP_CTX_MAX_CHARS)

    params = {
        "top_k": top_k,
        "max_evidence": max_evidence,
        "max_chars": max_chars,
        "model": llm_model,
        "answer_mode": answer_mode_used,
        "answer_mode_req": req_answer_mode,
        "force_fallback": force_fallback,
        "search_query": search_query,
        "search_query_used": str(plan_dbg.get("used") or "unknown"),
        "search_plan": plan,
        "followup": bool(parent_qa_id),
        "parent_qa_id": parent_qa_id or None,
        "memory_turns": memory_turns,
        "memory_max_chars": memory_max_chars,
        "answer_lang": answer_lang,
        "min_citations": min_citations,
        "max_citations": max_citations,
        "max_output_tokens": max_output_tokens,
        "evidence_scope": evidence_scope,
    }

    compact_evidence = [
        {
            "evidence_id": e.get("evidence_id"),
            "source_type": e.get("source_type"),
            "library_id": e.get("library_id"),
            "doc_id": e.get("doc_id"),
            "span_index": e.get("span_index"),
            "relevance": e.get("relevance"),
            "offset": e.get("offset"),
            "excerpt": e.get("excerpt"),
        }
        for e in evidence
    ]

    rec = {
        "type": "qa",
        "qa_id": qa_id,
        "group_id": thread_id,
        "version": 10,
        "created_at": created_at,
        "library_id": library_id,
        "doc_id": doc_id,
        "thread_id": thread_id,
        "parent_qa_id": parent_qa_id or None,
        "depth": depth,
        "question": question,
        "answer": str(answer_pack.get("answer") or ""),
        "response": str(answer_pack.get("answer") or ""),
        "claims": answer_pack.get("claims") if isinstance(answer_pack.get("claims"), list) else [],
        "citations": citations_norm,
        "evidence": compact_evidence,
        "evidence_query": search_query,
        "evidence_tools": ["nisb_doc_evidence_scope"],
        "mode_used": answer_mode_used,
        "rag_mode": evidence_scope,
        "params": params,
        "params_hash": _hash_params(params),
        "llm": {
            "ok": llm_ok,
            "error": llm_error,
            "raw_preview": llm_raw_preview,
            "model": llm_model,
        },
        "debug": {
            "evidence_count": len(evidence),
            "citations_count": len(citations_norm),
            "query_dbg": {"plan_dbg": plan_dbg, "compile_dbg": compile_dbg},
            "followup_dbg": followup_dbg,
            "picked_doc_dir": str(doc_dir),
        },
    }
    _append_jsonl(qa_path, rec)

    _append_timeline_activity(
        base_path=str(user_base),
        event={
            "type": "document",
            "library_id": library_id,
            "doc_id": doc_id,
            "path": str(doc_dir),
            "date": created_at,
            "extra": {
                "kind": "library_doc_qa",
                "qa_id": qa_id,
                "thread_id": thread_id,
                "parent_qa_id": parent_qa_id or None,
                "depth": depth,
                "question_preview": question[:80],
                "answer_mode": answer_mode_used,
                "model": llm_model,
                "llm_ok": llm_ok,
                "citation_spans": [x.get("span_index") for x in citations_norm],
                "citation_keys": [
                    {"library_id": x.get("library_id"), "doc_id": x.get("doc_id"), "span_index": x.get("span_index")}
                    for x in citations_norm
                ],
                "evidence_scope": evidence_scope,
            },
        },
    )

    return _build_standard_result(
        args=args,
        status="success",
        message="success",
        mode_used=answer_mode_used,
        response=rec["response"],
        qa_id=qa_id,
        group_id=thread_id,
        citations=citations_norm,
        rag_mode=evidence_scope,
        rss_evidence=[],
        market_evidence=[],
        evidence_query=search_query,
        evidence_tools=["nisb_doc_evidence_scope"],
        evidence_result={
            "qa_path": str(qa_path),
            "record": rec,
            "debug": dbg,
        },
        tool_calls=tool_calls,
        tool_results=tool_results,
    )


def nisb_doc_qa_list(args: Dict[str, Any]) -> Dict[str, Any]:
    library_id = str(args.get("library_id") or args.get("libraryid") or "").strip()
    doc_id = str(args.get("doc_id") or args.get("docid") or "").strip()
    limit = int(args.get("limit") or 40)

    if not library_id or not doc_id:
        return _build_standard_result(
            args=args,
            status="error",
            message="missing library_id/doc_id",
            mode_used="qa_list",
            response={"items": [], "count": 0, "limit": limit},
            rag_mode="doc",
        )

    doc_dir, dbg = _resolve_doc_dir(args, library_id=library_id, doc_id=doc_id)
    qa_path = doc_dir / "analysis" / QA_JSONL

    rows_all = _safe_read_jsonl(qa_path, max_rows=12000)
    qa_map = _build_qa_index(rows_all)
    deleted_set = _compute_deleted_set(rows_all, qa_map)

    items = []
    for qa_id, qa in qa_map.items():
        if qa_id in deleted_set:
            continue
        if qa.get("library_id") != library_id or qa.get("doc_id") != doc_id:
            continue
        items.append(qa)

    items.sort(key=lambda x: str(x.get("created_at") or ""))

    if limit > 0 and len(items) > limit:
        items = items[-limit:]

    formal_items = [_qa_record_to_standard_item(x) for x in items]

    return _build_standard_result(
        args=args,
        status="success",
        message="success",
        mode_used="qa_list",
        response={"items": formal_items, "count": len(formal_items), "limit": limit},
        rag_mode="doc",
        evidence_query=None,
        evidence_tools=[],
        evidence_result={
            "qa_path": str(qa_path),
            "debug": {
                **dbg,
                "total_rows": len(rows_all),
                "qa_count": len(qa_map),
                "deleted_count": len(deleted_set),
            },
            "records": items,
        },
        tool_calls=[],
        tool_results=[],
    )
