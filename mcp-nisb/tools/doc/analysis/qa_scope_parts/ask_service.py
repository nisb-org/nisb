from __future__ import annotations

import importlib
import os
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from tools.doc.analysis import doc_qa as dq  # type: ignore
from tools.lang.answer_language import (
    answer_language_instruction,
    append_highlights,
    build_fallback_answer,
    english_labels,
    resolve_answer_lang,
)

try:
    from tools.doc.core.span_constants import SPAN_CHARS
except Exception:
    SPAN_CHARS = 1200

from .common import clean_id
from .evidence import (
    build_public_evidence_items,
    build_shared_citation_pool,
    ev_doc_key,
    ev_span_key,
    normalize_evidence_items,
)
from .published_at import attach_evidence_published_at
from .r3_selection import (
    annotate_evidence_time_bucket,
    build_two_phase_half_windows,
    fetch_half_window_evidence,
    merge_evidence_lists,
    needs_two_phase_backfill,
    pick_doc_time_fetch_params,
    r3_min_from_args,
    time_bucket_evidence,
)
from .storage import (
    QA_SEG_ROTATE_BYTES,
    append_jsonl_segmented,
    delete_tombstone_append,
    evidence_scope_from_args,
    find_qa_anywhere_segmented,
    manifest_path,
    qa_path_for_doc,
    resolve_store_dir,
    store_scope_from_args,
)
from .time_filters import (
    doc_time_scope_from_args,
    extract_search_time_scope_debug,
    filter_evidence_by_doc_time_scope,
)

_TIMELINE_APPEND_CANDIDATES = (
    ("tools.timeline.activity_store", "_append_timeline_activity"),
    ("tools.timeline.store", "_append_timeline_activity"),
    ("tools.doc.timeline.activity_store", "_append_timeline_activity"),
    ("tools.doc.timeline.store", "_append_timeline_activity"),
)

_TIMELINE_APPEND_FN = None
_TIMELINE_APPEND_RESOLVED = False


def _get_timeline_append_fn():
    global _TIMELINE_APPEND_FN, _TIMELINE_APPEND_RESOLVED

    if _TIMELINE_APPEND_RESOLVED:
        return _TIMELINE_APPEND_FN

    _TIMELINE_APPEND_RESOLVED = True
    for mod_name, fn_name in _TIMELINE_APPEND_CANDIDATES:
        try:
            mod = importlib.import_module(mod_name)
            fn = getattr(mod, fn_name, None)
            if callable(fn):
                _TIMELINE_APPEND_FN = fn
                return _TIMELINE_APPEND_FN
        except Exception:
            continue

    _TIMELINE_APPEND_FN = None
    return None


def _append_timeline_activity_safe(*, base_path: str, event: Dict[str, Any]) -> bool:
    fn = _get_timeline_append_fn()
    if not callable(fn):
        return False

    try:
        fn(base_path=base_path, event=event)
        return True
    except TypeError:
        try:
            fn(base_path, event)
            return True
        except Exception:
            return False
    except Exception:
        return False


def fallback_answer(question: str, evidence: List[Dict[str, Any]], answer_lang: str = "en") -> Dict[str, Any]:
    return build_fallback_answer(question, evidence, shortener=dq._short)


def dedupe_citations(citations: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    seen: Set[Tuple[str, str, int, str]] = set()

    for c in citations or []:
        if not isinstance(c, dict):
            continue

        lib_id = clean_id(c.get("library_id"))
        doc_id = clean_id(c.get("doc_id"))

        try:
            span_index = int(c.get("span_index"))
        except Exception:
            span_index = -1

        quote = clean_id(c.get("quote"))
        key = (lib_id, doc_id, span_index, quote)

        if not doc_id:
            continue
        if key in seen:
            continue

        seen.add(key)
        out.append(c)

    return out


def dedupe_by_doc_id(
    citations: List[Dict[str, Any]],
    *,
    max_per_doc: int = 1,
) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    per_doc: Dict[Tuple[str, str], int] = {}

    for c in citations or []:
        if not isinstance(c, dict):
            continue

        lib_id = clean_id(c.get("library_id"))
        doc_id = clean_id(c.get("doc_id"))
        if not doc_id:
            continue

        dk = (lib_id, doc_id)
        used = int(per_doc.get(dk, 0))
        if used >= int(max_per_doc):
            continue

        per_doc[dk] = used + 1
        out.append(c)

    return out


def _backfill_citations_from_pool(
    citations: List[Dict[str, Any]],
    *,
    citation_pool: List[Dict[str, Any]],
    min_citations: int,
    max_citations: int,
    dedupe_doc: bool,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    out: List[Dict[str, Any]] = [x for x in (citations or []) if isinstance(x, dict)]

    max_allowed = max(1, int(max_citations or 1))
    min_required = max(0, min(int(min_citations or 0), max_allowed))

    trimmed_before_backfill = False
    if len(out) > max_allowed:
        out = out[:max_allowed]
        trimmed_before_backfill = True

    existing_span_keys: Set[Tuple[str, str, int]] = set()
    per_doc: Dict[Tuple[str, str], int] = {}

    for c in out:
        sk = ev_span_key(c)
        dk = ev_doc_key(c)
        existing_span_keys.add(sk)
        if dk[1]:
            per_doc[dk] = int(per_doc.get(dk, 0)) + 1

    triggered = len(out) < min_required and bool(citation_pool)
    added = 0
    skipped_dup = 0
    skipped_doc_cap = 0

    if triggered:
        for cand in citation_pool:
            if len(out) >= min_required:
                break
            if not isinstance(cand, dict):
                continue

            sk = ev_span_key(cand)
            dk = ev_doc_key(cand)

            if not dk[1]:
                continue
            if sk in existing_span_keys:
                skipped_dup += 1
                continue
            if dedupe_doc and int(per_doc.get(dk, 0)) >= 1:
                skipped_doc_cap += 1
                continue

            out.append(dict(cand))
            existing_span_keys.add(sk)
            per_doc[dk] = int(per_doc.get(dk, 0)) + 1
            added += 1

    if len(out) > max_allowed:
        out = out[:max_allowed]

    dbg = {
        "triggered": bool(triggered),
        "min_required": int(min_required),
        "max_allowed": int(max_allowed),
        "added": int(added),
        "final_count": len(out),
        "trimmed_before_backfill": bool(trimmed_before_backfill),
        "skipped_duplicate_span": int(skipped_dup),
        "skipped_doc_cap": int(skipped_doc_cap),
        "dedupe_doc": bool(dedupe_doc),
        "source": "shared_evidence_pool",
    }
    return out, dbg


def delete_append_event(
    qa_path: Path,
    *,
    user_base: Path,
    store_scope: str,
    library_id: Optional[str],
    doc_id: Optional[str],
    target_qa: dict,
    scope: str,
    store_dir: Path,
) -> Dict[str, Any]:
    created_at = dq._utc_now_iso()
    target_id = clean_id(target_qa.get("qa_id"))
    thread_id = clean_id(target_qa.get("thread_id") or target_qa.get("qa_id")) or target_id

    ev = {
        "type": "qa_delete",
        "version": 2,
        "created_at": created_at,
        "store_scope": store_scope,
        "library_id": library_id,
        "doc_id": doc_id,
        "target_qa_id": target_id,
        "thread_id": thread_id,
        "scope": scope,
    }

    if store_scope == "doc":
        dq._append_jsonl(qa_path, ev)
    else:
        append_jsonl_segmented(store_dir, ev)
        delete_tombstone_append(store_dir, ev)

    _append_timeline_activity_safe(
        base_path=str(user_base),
        event={
            "type": "document",
            "library_id": library_id,
            "doc_id": doc_id,
            "path": str(store_dir),
            "date": created_at,
            "extra": {
                "kind": "qa_scope_delete",
                "store_scope": store_scope,
                "target_qa_id": target_id,
                "thread_id": thread_id,
                "scope": scope,
            },
        },
    )

    return ev


def load_followup_chain_segmented(
    store_dir: Path,
    parent_qa_id: str,
    max_turns: int,
    max_chars: int,
) -> Tuple[str, Dict[str, Any]]:
    dbg: Dict[str, Any] = {"segmented_chain": True, "visited": 0, "hits": 0}
    qa_map: Dict[str, dict] = {}

    cur = clean_id(parent_qa_id)
    turns = 0
    while cur and turns < max_turns:
        dbg["visited"] += 1
        node = find_qa_anywhere_segmented(store_dir, cur)
        if not node:
            break
        dbg["hits"] += 1
        qa_map[clean_id(node.get("qa_id"))] = node
        cur = clean_id(node.get("parent_qa_id"))
        turns += 1

    try:
        ctx, ctx_dbg = dq._build_followup_context_chain(
            qa_map=qa_map,
            parent_qa_id=clean_id(parent_qa_id),
            max_turns=max_turns,
            max_chars=max_chars,
        )
        dbg["dq_dbg"] = ctx_dbg
        return ctx, dbg
    except Exception as e:
        dbg["error"] = str(e)
        return "", dbg


def nisb_qa_scope_ask(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Unified QA with three storage scopes:
    - store_scope=doc: requires library_id + doc_id
    - store_scope=library: requires library_id
    - store_scope=global: requires neither library_id nor doc_id
    """
    action = clean_id(args.get("action") or "ask").lower()

    store_scope = store_scope_from_args(args)
    evidence_scope = evidence_scope_from_args(args, fallback=store_scope)

    library_id = clean_id(args.get("library_id") or args.get("libraryid")) or None
    doc_id = clean_id(args.get("doc_id") or args.get("docid")) or None

    if store_scope == "doc" and not (library_id and doc_id):
        return {"status": "error", "message": "store_scope=doc requires library_id/doc_id"}
    if store_scope == "library" and not library_id:
        return {"status": "error", "message": "store_scope=library requires library_id"}

    store_dir, dbg = resolve_store_dir(args, store_scope=store_scope, library_id=library_id, doc_id=doc_id)
    user_base = dq._resolve_user_base(args)

    qa_path_doc = qa_path_for_doc(store_dir)

    if action == "delete":
        qa_id = clean_id(args.get("qa_id") or args.get("target_qa_id") or args.get("qaid"))
        if not qa_id:
            return {"status": "error", "message": "missing qa_id for delete"}

        if store_scope == "doc":
            rows_all = dq._safe_read_jsonl(qa_path_doc, max_rows=20000)
            qa_map = dq._build_qa_index(rows_all)
            deleted_set = dq._compute_deleted_set(rows_all, qa_map)
            if qa_id in deleted_set:
                return {"status": "error", "message": "qa already deleted"}
            target_qa = dq._find_qa_by_id(qa_map, qa_id)
            if not target_qa:
                return {"status": "error", "message": f"qa_id not found: {qa_id}"}
        else:
            target_qa = find_qa_anywhere_segmented(store_dir, qa_id)
            if not target_qa:
                return {"status": "error", "message": f"qa_id not found: {qa_id}"}

        scope_del = clean_id(args.get("scope") or "auto").lower()
        if scope_del == "auto":
            is_followup = bool(clean_id(target_qa.get("parent_qa_id")))
            scope_del = "subtree" if is_followup else "thread"
        if scope_del not in ("single", "subtree", "thread"):
            return {"status": "error", "message": f"invalid scope: {scope_del}"}

        ev = delete_append_event(
            qa_path=qa_path_doc,
            user_base=user_base,
            store_scope=store_scope,
            library_id=library_id,
            doc_id=doc_id,
            target_qa=target_qa,
            scope=scope_del,
            store_dir=store_dir,
        )

        return {
            "status": "success",
            "action": "delete",
            "store_scope": store_scope,
            "deleted": {"qa_id": qa_id, "scope": scope_del},
            "qa_path": str(qa_path_doc if store_scope == "doc" else manifest_path(store_dir)),
            "debug": dbg,
            "event": ev,
        }

    question = clean_id(args.get("question"))
    if not question:
        return {"status": "error", "message": "missing question"}

    handoff_context = str(args.get("handoff_context") or args.get("handoffContext") or "").strip()
    linked_from = args.get("linked_from") or args.get("linkedFrom") or None
    if linked_from is not None and not isinstance(linked_from, dict):
        linked_from = {"raw": str(linked_from)}

    parent_qa_id = clean_id(
        args.get("parent_qa_id")
        or args.get("parentQaId")
        or args.get("parentqaid")
        or args.get("parent_qaid")
    )

    followup_ctx = ""
    followup_dbg: Dict[str, Any] = {}
    thread_id = ""
    depth = 0

    if parent_qa_id:
        if store_scope == "doc":
            rows_all = dq._safe_read_jsonl(qa_path_doc, max_rows=20000)
            qa_map = dq._build_qa_index(rows_all)
            deleted_set = dq._compute_deleted_set(rows_all, qa_map)
            if parent_qa_id in deleted_set:
                return {"status": "error", "message": "parent QA is deleted; cannot follow up"}
            parent_qa = dq._find_qa_by_id(qa_map, parent_qa_id)
            if not parent_qa:
                return {"status": "error", "message": f"parent QA not found: {parent_qa_id}"}

            thread_id = clean_id(parent_qa.get("thread_id") or parent_qa.get("qa_id"))
            try:
                depth = int(parent_qa.get("depth") or 0) + 1
            except Exception:
                depth = 1

            followup_ctx, followup_dbg = dq._build_followup_context_chain(
                qa_map=qa_map,
                parent_qa_id=parent_qa_id,
                max_turns=dq._get_int(args, "memory_turns", "memoryturns", default=dq.FOLLOWUP_TURNS_DEFAULT),
                max_chars=dq._get_int(args, "memory_max_chars", "memorymaxchars", default=dq.FOLLOWUP_CTX_MAX_CHARS),
            )
        else:
            parent_qa = find_qa_anywhere_segmented(store_dir, parent_qa_id)
            if not parent_qa:
                return {"status": "error", "message": f"parent QA not found: {parent_qa_id}"}

            thread_id = clean_id(parent_qa.get("thread_id") or parent_qa.get("qa_id"))
            try:
                depth = int(parent_qa.get("depth") or 0) + 1
            except Exception:
                depth = 1

            followup_ctx, followup_dbg = load_followup_chain_segmented(
                store_dir=store_dir,
                parent_qa_id=parent_qa_id,
                max_turns=dq._get_int(args, "memory_turns", "memoryturns", default=dq.FOLLOWUP_TURNS_DEFAULT),
                max_chars=dq._get_int(args, "memory_max_chars", "memorymaxchars", default=dq.FOLLOWUP_CTX_MAX_CHARS),
            )

    merged_ctx = followup_ctx
    if handoff_context:
        merged_ctx = (handoff_context + "\n\n" + (followup_ctx or "")).strip()

    top_k = dq._get_int(args, "top_k", "topk", default=18)
    max_evidence = dq._get_int(args, "max_evidence", "maxevidence", default=14)

    context_max_chars = dq._get_int(args, "max_chars", "maxchars", default=14000)
    evidence_span_chars = int(SPAN_CHARS)

    llm_model = clean_id(args.get("model") or os.getenv("OPENAI_QA_MODEL", "gpt-4o-mini")) or "gpt-4o-mini"
    force_fallback = bool(args.get("force_fallback") or False)

    answer_lang, _ = resolve_answer_lang(
        question=question,
        args=args,
        default_lang="en",
    )

    req_answer_mode = clean_id(
        dq._get_arg(args, "answer_mode", "answerMode", default="llm_rich") or "llm_rich"
    ) or "llm_rich"

    min_citations = dq._get_int(args, "min_citations", "minCitations", default=4)
    max_citations = dq._get_int(args, "max_citations", "maxCitations", default=12)
    max_output_tokens = dq._get_int(args, "max_output_tokens", "maxOutputTokens", default=2200)

    doc_time_scope = doc_time_scope_from_args(args)
    single_doc_bypass = bool(evidence_scope == "doc" and doc_id)
    r3_min_cfg = r3_min_from_args(args)

    time_filter_enabled_effective = bool(doc_time_scope.get("enabled")) and not single_doc_bypass

    plan, plan_dbg = dq._build_search_plan(question, llm_model=llm_model, extra_context=merged_ctx)
    search_query, compile_dbg = dq._compile_search_query(question, plan)

    try:
        from tools.doc.doc_evidence_scope import nisb_doc_evidence_scope  # type: ignore
        evidence_tool = nisb_doc_evidence_scope
    except Exception as e:
        return {"status": "error", "message": f"qa_scope_ask: evidence tool import failed: {e}", "debug": dbg}

    top_k_fetch, max_evidence_fetch = pick_doc_time_fetch_params(
        top_k,
        max_evidence,
        time_filter_enabled=time_filter_enabled_effective,
        r3_min_enabled=bool(r3_min_cfg.get("enabled")),
    )

    ev_args: Dict[str, Any] = {
        **args,
        "scope": evidence_scope,
        "query": search_query,
        "top_k": top_k_fetch,
        "max_chars": evidence_span_chars,
        "include_text": True,
    }

    if library_id:
        ev_args["library_id"] = library_id
    if doc_id:
        ev_args["doc_id"] = doc_id

    if single_doc_bypass:
        for k in (
            "time_filter_days",
            "timeFilterDays",
            "time_start",
            "timeStart",
            "time_end",
            "timeEnd",
        ):
            ev_args.pop(k, None)
    else:
        ev_args.pop("timeFilterDays", None)
        ev_args.pop("timeStart", None)
        ev_args.pop("timeEnd", None)

        if int(doc_time_scope.get("days") or 0) > 0:
            ev_args["time_filter_days"] = int(doc_time_scope.get("days") or 0)
        else:
            ev_args.pop("time_filter_days", None)

        if str(doc_time_scope.get("time_start") or "").strip():
            ev_args["time_start"] = str(doc_time_scope.get("time_start") or "").strip()
        else:
            ev_args.pop("time_start", None)

        if str(doc_time_scope.get("time_end") or "").strip():
            ev_args["time_end"] = str(doc_time_scope.get("time_end") or "").strip()
        else:
            ev_args.pop("time_end", None)

    ev_res = evidence_tool(ev_args)
    ev_debug = ev_res.get("debug") if isinstance(ev_res, dict) and isinstance(ev_res.get("debug"), dict) else {}
    retrieval_time_scope_dbg = extract_search_time_scope_debug(ev_debug)

    evidence = normalize_evidence_items(ev_res if isinstance(ev_res, dict) else {}, max_evidence=max_evidence_fetch)
    evidence, evidence_pub_dbg = attach_evidence_published_at(
        evidence,
        user_base=user_base,
    )

    doc_time_filter_dbg: Dict[str, Any] = {
        "enabled": False,
        "bypassed": single_doc_bypass,
        "days": int(doc_time_scope.get("days") or 0),
        "time_start": str(doc_time_scope.get("time_start") or ""),
        "time_end": str(doc_time_scope.get("time_end") or ""),
        "mode": "disabled",
        "retrieval_time_filter_applied": bool(retrieval_time_scope_dbg.get("time_filter_applied")),
    }

    fallback_filter_used = False

    if time_filter_enabled_effective:
        fallback_filter_used = not bool(retrieval_time_scope_dbg.get("time_filter_applied"))
        evidence, doc_time_filter_dbg = filter_evidence_by_doc_time_scope(
            evidence,
            user_base=user_base,
            days=int(doc_time_scope.get("days") or 0),
            start_dt=doc_time_scope.get("start_dt"),
            end_dt=doc_time_scope.get("end_dt"),
            fallback_filter=fallback_filter_used,
        )
        doc_time_filter_dbg["bypassed"] = False
        doc_time_filter_dbg["retrieval_time_filter_applied"] = bool(retrieval_time_scope_dbg.get("time_filter_applied"))
        doc_time_filter_dbg["effective_source"] = (
            "qa_scope_fallback"
            if fallback_filter_used
            else "search_candidate_scope_assert_only"
        )
    elif single_doc_bypass:
        doc_time_filter_dbg["reason"] = "single_doc_bypass"
        doc_time_filter_dbg["mode"] = "single_doc_bypass"
        doc_time_filter_dbg["effective_source"] = "single_doc_bypass"
    else:
        doc_time_filter_dbg["effective_source"] = "disabled"

    evidence, r3_selection_dbg = time_bucket_evidence(
        evidence,
        max_evidence=max_evidence,
        dedupe_by_doc_id=bool(r3_min_cfg.get("dedupe_by_doc_id")),
        time_bucket_mode=str(r3_min_cfg.get("time_bucket_mode") or "off"),
        days=int(doc_time_scope.get("days") or 0),
        start_dt=doc_time_scope.get("start_dt"),
        end_dt=doc_time_scope.get("end_dt"),
    )

    r3_backfill_dbg: Dict[str, Any] = {
        "enabled": bool(
            bool(r3_min_cfg.get("enabled"))
            and str(r3_min_cfg.get("time_bucket_mode") or "off") == "two_phase"
            and bool(doc_time_scope.get("enabled"))
            and (not single_doc_bypass)
        ),
        "trigger_condition": {
            "older_candidates_before": int(r3_selection_dbg.get("older_candidates") or 0),
            "newer_candidates_before": int(r3_selection_dbg.get("newer_candidates") or 0),
        },
        "triggered": False,
        "reason": "",
        "older_half_fetch": {
            "called": False,
            "time_start": "",
            "time_end": "",
            "items": 0,
        },
    }

    if needs_two_phase_backfill(
        r3_min_cfg=r3_min_cfg,
        doc_time_scope=doc_time_scope,
        r3_selection_dbg=r3_selection_dbg,
        single_doc_bypass=single_doc_bypass,
    ):
        halves = build_two_phase_half_windows(
            days=int(doc_time_scope.get("days") or 0),
            start_dt=doc_time_scope.get("start_dt"),
            end_dt=doc_time_scope.get("end_dt"),
        )

        r3_backfill_dbg = {
            "enabled": True,
            "triggered": True,
            "reason": "older_bucket_empty",
            "trigger_condition": {
                "older_candidates_before": int(r3_selection_dbg.get("older_candidates") or 0),
                "newer_candidates_before": int(r3_selection_dbg.get("newer_candidates") or 0),
            },
            "boundary": halves["boundary"].isoformat() if halves.get("boundary") else "",
            "boundary_source": halves.get("boundary_source") or "",
            "older_start": halves["older_start"].isoformat() if halves.get("older_start") else "",
            "older_end": halves["older_end"].isoformat() if halves.get("older_end") else "",
        }

        older_half_items, older_half_dbg = fetch_half_window_evidence(
            evidence_tool=evidence_tool,
            base_args=ev_args,
            half_start=halves.get("older_start"),
            half_end=halves.get("older_end"),
            user_base=user_base,
            fetch_limit=min(12, max_evidence_fetch),
        )

        r3_backfill_dbg["older_half_fetch"] = older_half_dbg
        r3_backfill_dbg["reason"] = "older_bucket_empty"

        merged_evidence = merge_evidence_lists(
            evidence,
            older_half_items,
            limit=max(max_evidence_fetch * 2, max_evidence + 12),
        )

        evidence, r3_selection_dbg = time_bucket_evidence(
            merged_evidence,
            max_evidence=max_evidence,
            dedupe_by_doc_id=bool(r3_min_cfg.get("dedupe_by_doc_id")),
            time_bucket_mode=str(r3_min_cfg.get("time_bucket_mode") or "off"),
            days=int(doc_time_scope.get("days") or 0),
            start_dt=doc_time_scope.get("start_dt"),
            end_dt=doc_time_scope.get("end_dt"),
        )

        r3_backfill_dbg["merged_evidence_count"] = len(merged_evidence)
        r3_backfill_dbg["older_half_items"] = len(older_half_items)
        r3_backfill_dbg["selected_after_rerun"] = len(evidence)
        r3_backfill_dbg["rerun_done"] = True

    evidence, r3_visible_bucket_dbg = annotate_evidence_time_bucket(
        evidence,
        days=int(doc_time_scope.get("days") or 0),
        start_dt=doc_time_scope.get("start_dt"),
        end_dt=doc_time_scope.get("end_dt"),
        mode=str(r3_min_cfg.get("time_bucket_mode") or "off"),
    )

    evidence_key_set: Set[Tuple[str, str, int]] = set(
        (str(x.get("library_id") or ""), str(x.get("doc_id") or ""), int(x.get("span_index")))
        for x in evidence
        if isinstance(x.get("span_index"), int)
    )

    citation_pool, citation_pool_dbg = build_shared_citation_pool(
        evidence,
        max_pool=max(max_citations * 3, max_evidence, 12),
        per_doc_soft_cap=2,
    )

    llm_ok = False
    llm_error: Optional[str] = None
    llm_raw_preview: str = ""
    answer_mode_used = "fallback_template_v1"

    if force_fallback or (not evidence):
        answer_pack = fallback_answer(question, evidence, answer_lang=answer_lang)
    else:
        try:
            mode = req_answer_mode.lower()
            if mode in ("llm_json_structured_v2", "structured", "json_structured"):
                mode = "llm_rich"

            sys, user = dq._llm_prompt_rich(
                question=question,
                evidence=evidence,
                extra_context=merged_ctx,
                min_citations=min_citations,
                max_citations=max_citations,
                answer_lang=answer_lang,
            )
            sys = (sys + "\n\n" + answer_language_instruction(answer_lang)).strip()

            llm_json_raw = dq._call_llm_compat(
                model=llm_model,
                system_prompt=sys,
                user_prompt=user,
                response_format="json",
                max_output_tokens=max_output_tokens,
            )
            llm_json = llm_json_raw if isinstance(llm_json_raw, dict) else {}

            answer_text = str(llm_json.get("answer") or "").strip()
            highlights = llm_json.get("highlights") if isinstance(llm_json.get("highlights"), list) else []
            highlights = [str(x).strip() for x in highlights if str(x).strip()]

            if highlights:
                answer_text = append_highlights(
                    answer_text,
                    highlights,
                    title=english_labels()["highlights_title"],
                )

            answer_pack = {
                "answer": answer_text,
                "claims": highlights,
                "citations": llm_json.get("citations") if isinstance(llm_json.get("citations"), list) else [],
            }

            citations_norm_tmp = dq._normalize_citations(
                answer_pack,
                evidence_key_set=evidence_key_set,
                default_library_id=library_id or "",
                default_doc_id=doc_id or "",
            )

            if len(citations_norm_tmp) == 0:
                sys2 = (
                    sys
                    + "\n\nIMPORTANT: You MUST return non-empty citations array, each citation must include library_id, doc_id, span_index, quote."
                )
                llm_json2_raw = dq._call_llm_compat(
                    model=llm_model,
                    system_prompt=sys2,
                    user_prompt=user,
                    response_format="json",
                    max_output_tokens=max_output_tokens,
                )
                llm_json2 = llm_json2_raw if isinstance(llm_json2_raw, dict) else {}

                answer_text2 = str(llm_json2.get("answer") or "").strip()
                highlights2 = llm_json2.get("highlights") if isinstance(llm_json2.get("highlights"), list) else []
                highlights2 = [str(x).strip() for x in highlights2 if str(x).strip()]
                if highlights2:
                    answer_text2 = append_highlights(
                        answer_text2,
                        highlights2,
                        title=english_labels()["highlights_title"],
                    )

                answer_pack2 = {
                    "answer": answer_text2,
                    "claims": highlights2,
                    "citations": llm_json2.get("citations") if isinstance(llm_json2.get("citations"), list) else [],
                }
                citations_norm_tmp = dq._normalize_citations(
                    answer_pack2,
                    evidence_key_set=evidence_key_set,
                    default_library_id=library_id or "",
                    default_doc_id=doc_id or "",
                )
                if citations_norm_tmp:
                    answer_pack = answer_pack2

            if len(citations_norm_tmp) == 0:
                fb = fallback_answer(question, evidence, answer_lang=answer_lang)
                fb_citations = fb.get("citations") if isinstance(fb.get("citations"), list) else []
                if fb_citations:
                    answer_pack["citations"] = fb_citations

            llm_ok = True
            answer_mode_used = "llm_rich"
        except Exception as e:
            llm_ok = False
            llm_error = str(e)
            llm_raw_preview = dq._short(llm_error, 900)
            answer_pack = fallback_answer(question, evidence, answer_lang=answer_lang)
            answer_mode_used = "fallback_template_v1"

    llm_citations_raw = answer_pack.get("citations") if isinstance(answer_pack.get("citations"), list) else []

    citations_norm = dq._normalize_citations(
        answer_pack,
        evidence_key_set=evidence_key_set,
        default_library_id=library_id or "",
        default_doc_id=doc_id or "",
    )
    citations_after_normalize = len(citations_norm)

    citations_norm = dedupe_citations(citations_norm)
    citations_after_dedupe = len(citations_norm)

    citations_after_doc_dedupe = citations_after_dedupe
    if bool(r3_min_cfg.get("dedupe_by_doc_id")):
        citations_norm = dedupe_by_doc_id(citations_norm, max_per_doc=1)
        citations_after_doc_dedupe = len(citations_norm)

    citations_norm, citation_backfill_dbg = _backfill_citations_from_pool(
        citations_norm,
        citation_pool=citation_pool,
        min_citations=min_citations,
        max_citations=max_citations,
        dedupe_doc=bool(r3_min_cfg.get("dedupe_by_doc_id")),
    )

    answer_text_final = str(answer_pack.get("answer") or "").strip()
    if not answer_text_final:
        labels = english_labels()
        if evidence:
            answer_text_final = labels["empty_answer_with_evidence"]
        else:
            answer_text_final = labels["empty_answer_no_evidence"]
        answer_pack["answer"] = answer_text_final

    created_at = dq._utc_now_iso()
    qa_id = f"qa_{created_at.replace(':', '').replace('-', '').replace('.', '')}_{uuid.uuid4().hex[:8]}"
    if not thread_id:
        thread_id = qa_id

    memory_turns = dq._get_int(args, "memory_turns", "memoryturns", default=dq.FOLLOWUP_TURNS_DEFAULT)
    memory_max_chars = dq._get_int(args, "memory_max_chars", "memorymaxchars", default=dq.FOLLOWUP_CTX_MAX_CHARS)

    if single_doc_bypass:
        effective_time_filter_source = "single_doc_bypass"
    elif not time_filter_enabled_effective:
        effective_time_filter_source = "disabled"
    else:
        effective_time_filter_source = (
            "qa_scope_fallback" if fallback_filter_used else "search_candidate_scope_assert_only"
        )

    citation_assembly_dbg = {
        "citation_from_shared_evidence_pool": True,
        "llm_citations_raw_count": len(llm_citations_raw),
        "citations_after_normalize": int(citations_after_normalize),
        "citations_after_dedupe": int(citations_after_dedupe),
        "citations_after_doc_dedupe": int(citations_after_doc_dedupe),
        "citation_pool_before_dedupe": int(citation_pool_dbg.get("candidate_total") or 0),
        "citation_pool_after_dedupe": int(citation_pool_dbg.get("pool_count") or 0),
        "citation_pool_unique_docs": int(citation_pool_dbg.get("pool_unique_docs") or 0),
        "citation_pool_per_doc_soft_cap": int(citation_pool_dbg.get("per_doc_soft_cap") or 0),
        "citation_selected_count": len(citations_norm),
        "citation_trim_reason": (
            "doc_id_dedupe_and_or_backfill"
            if bool(r3_min_cfg.get("dedupe_by_doc_id"))
            else "span_dedupe_and_or_backfill"
        ),
        "citation_doc_cap": (1 if bool(r3_min_cfg.get("dedupe_by_doc_id")) else 0),
        "citation_backfill": citation_backfill_dbg,
        "min_citations": int(min_citations),
        "max_citations": int(max_citations),
    }

    params = {
        "store_scope": store_scope,
        "evidence_scope": evidence_scope,
        "top_k": top_k,
        "max_evidence": max_evidence,
        "max_chars": context_max_chars,
        "span_chars": evidence_span_chars,
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
        "handoff": bool(handoff_context),
        "linked_from": linked_from,
        "segmented_storage": (store_scope != "doc"),
        "rotate_bytes": QA_SEG_ROTATE_BYTES,
        "time_filter_days": int(doc_time_scope.get("days") or 0),
        "time_start": str(doc_time_scope.get("time_start") or ""),
        "time_end": str(doc_time_scope.get("time_end") or ""),
        "time_filter_effective": bool(time_filter_enabled_effective),
        "time_filter_single_doc_bypass": bool(single_doc_bypass),
        "time_filter_source": effective_time_filter_source,
        "r3_min_enabled": bool(r3_min_cfg.get("enabled")),
        "r3_min_dedupe_by_doc_id": bool(r3_min_cfg.get("dedupe_by_doc_id")),
        "r3_min_time_bucket_mode": str(r3_min_cfg.get("time_bucket_mode") or "off"),
    }

    rec = {
        "type": "qa",
        "qa_id": qa_id,
        "version": 1,
        "created_at": created_at,
        "store_scope": store_scope,
        "evidence_scope": evidence_scope,
        "library_id": library_id,
        "doc_id": doc_id,
        "thread_id": thread_id,
        "parent_qa_id": parent_qa_id or None,
        "depth": depth,
        "linked_from": linked_from,
        "question": question,
        "answer": answer_text_final,
        "claims": answer_pack.get("claims") if isinstance(answer_pack.get("claims"), list) else [],
        "citations": citations_norm,
        "evidence": evidence,
        "params": params,
        "params_hash": dq._hash_params(params),
        "llm": {
            "ok": llm_ok,
            "error": llm_error,
            "raw_preview": llm_raw_preview,
            "model": llm_model,
        },
        "debug": {
            "evidence_count": len(evidence),
            "evidence_fetch_top_k": top_k_fetch,
            "evidence_fetch_max_evidence": max_evidence_fetch,
            "doc_time_scope_args": {
                "enabled": bool(doc_time_scope.get("enabled")),
                "days": int(doc_time_scope.get("days") or 0),
                "time_start": str(doc_time_scope.get("time_start") or ""),
                "time_end": str(doc_time_scope.get("time_end") or ""),
            },
            "doc_time_scope_effective": {
                "enabled": bool(time_filter_enabled_effective),
                "single_doc_bypass": bool(single_doc_bypass),
                "source": effective_time_filter_source,
            },
            "retrieval_time_scope": retrieval_time_scope_dbg,
            "doc_time_filter": doc_time_filter_dbg,
            "evidence_scope_args": {
                "scope": evidence_scope,
                "top_k": top_k_fetch,
                "max_chars": evidence_span_chars,
                "time_filter_days": ev_args.get("time_filter_days"),
                "time_start": ev_args.get("time_start"),
                "time_end": ev_args.get("time_end"),
                "library_id": ev_args.get("library_id"),
                "doc_id": ev_args.get("doc_id"),
                "group_id": ev_args.get("group_id"),
            },
            "evidence_scope_debug": ev_debug,
            "evidence_published_at": evidence_pub_dbg,
            "r3_min_selection": r3_selection_dbg,
            "r3_min_backfill": r3_backfill_dbg,
            "r3_visible_bucket": r3_visible_bucket_dbg,
            "citation_assembly": citation_assembly_dbg,
            "citations_count": len(citations_norm),
            "query_dbg": {"plan_dbg": plan_dbg, "compile_dbg": compile_dbg},
            "followup_dbg": followup_dbg,
            "picked_store_dir": str(store_dir),
        },
    }

    write_dbg: Dict[str, Any] = {}
    if store_scope == "doc":
        dq._append_jsonl(qa_path_doc, rec)
        qa_path_out = qa_path_doc
        write_dbg["storage"] = "single_jsonl_doc"
    else:
        fp, wdbg = append_jsonl_segmented(store_dir, rec)
        qa_path_out = fp
        write_dbg = {"storage": "segmented_jsonl", **wdbg}

    _append_timeline_activity_safe(
        base_path=str(user_base),
        event={
            "type": "document",
            "library_id": library_id,
            "doc_id": doc_id,
            "path": str(store_dir),
            "date": created_at,
            "extra": {
                "kind": "qa_scope",
                "store_scope": store_scope,
                "evidence_scope": evidence_scope,
                "qa_id": qa_id,
                "thread_id": thread_id,
                "parent_qa_id": parent_qa_id or None,
                "depth": depth,
                "question_preview": question[:80],
                "answer_mode": answer_mode_used,
                "model": llm_model,
                "llm_ok": llm_ok,
                "linked_from": linked_from,
                "time_filter_days": int(doc_time_scope.get("days") or 0),
                "time_start": str(doc_time_scope.get("time_start") or ""),
                "time_end": str(doc_time_scope.get("time_end") or ""),
                "time_filter_effective": bool(time_filter_enabled_effective),
                "single_doc_bypass": bool(single_doc_bypass),
                "time_filter_source": effective_time_filter_source,
                "r3_min_enabled": bool(r3_min_cfg.get("enabled")),
                "r3_min_dedupe_by_doc_id": bool(r3_min_cfg.get("dedupe_by_doc_id")),
                "r3_min_time_bucket_mode": str(r3_min_cfg.get("time_bucket_mode") or "off"),
                "citation_keys": [
                    {"library_id": x.get("library_id"), "doc_id": x.get("doc_id"), "span_index": x.get("span_index")}
                    for x in citations_norm
                ],
            },
        },
    )

    orchestrator_time_scope = {
        "enabled": bool(time_filter_enabled_effective),
        "time_filter_days": int(doc_time_scope.get("days") or 0) if int(doc_time_scope.get("days") or 0) > 0 else "",
        "time_start": "" if int(doc_time_scope.get("days") or 0) > 0 else str(doc_time_scope.get("time_start") or ""),
        "time_end": "" if int(doc_time_scope.get("days") or 0) > 0 else str(doc_time_scope.get("time_end") or ""),
        "single_doc_bypass": bool(single_doc_bypass),
        "source": effective_time_filter_source,
    }

    evidence_result = {
        "citations": citations_norm,
        "rss_evidence": [],
        "market_evidence": [],
        "evidence_query": question,
        "evidence_tools": ["nisb_doc_evidence_scope"],
        "orchestrator_time_scope": orchestrator_time_scope,
        "retrieval_time_scope": retrieval_time_scope_dbg,
        "effective_source": effective_time_filter_source,
        "candidate_docs_after_time": retrieval_time_scope_dbg.get("candidate_docs_after_time"),
    }

    qa_meta = {
        "qa_id": qa_id,
        "thread_id": thread_id,
        "store_scope": store_scope,
        "evidence_scope": evidence_scope,
        "library_id": library_id,
        "doc_id": doc_id,
        "evidence_count": len(evidence),
        "citations_count": len(citations_norm),
        "time_filter_days": orchestrator_time_scope.get("time_filter_days"),
        "time_start": orchestrator_time_scope.get("time_start"),
        "time_end": orchestrator_time_scope.get("time_end"),
    }

    qa_evidence_public = build_public_evidence_items(
        evidence if isinstance(evidence, list) else []
    )

    top_params = {
        "r3_min_enabled": params.get("r3_min_enabled"),
        "r3_min_dedupe_by_doc_id": params.get("r3_min_dedupe_by_doc_id"),
        "r3_min_time_bucket_mode": params.get("r3_min_time_bucket_mode"),
        "time_filter_days": params.get("time_filter_days"),
        "time_start": params.get("time_start"),
        "time_end": params.get("time_end"),
    }

    top_debug = {
        **dbg,
        **write_dbg,
        "doc_time_scope_args": rec.get("debug", {}).get("doc_time_scope_args"),
        "doc_time_filter": rec.get("debug", {}).get("doc_time_filter"),
        "retrieval_time_scope": rec.get("debug", {}).get("retrieval_time_scope"),
        "orchestrator_time_scope": orchestrator_time_scope,
        "effective_source": effective_time_filter_source,
        "evidence_result": evidence_result,
        "evidence_published_at": rec.get("debug", {}).get("evidence_published_at"),
        "r3_min_selection": rec.get("debug", {}).get("r3_min_selection"),
        "r3_min_backfill": rec.get("debug", {}).get("r3_min_backfill"),
        "r3_visible_bucket": rec.get("debug", {}).get("r3_visible_bucket"),
        "citation_assembly": rec.get("debug", {}).get("citation_assembly"),
        "r3_min_params": {
            "enabled": params.get("r3_min_enabled"),
            "dedupe_by_doc_id": params.get("r3_min_dedupe_by_doc_id"),
            "time_bucket_mode": params.get("r3_min_time_bucket_mode"),
        },
        "qa_evidence_preview": qa_evidence_public[: min(len(qa_evidence_public), max_evidence)]
        if isinstance(qa_evidence_public, list)
        else [],
        "citations_count": len(citations_norm),
        "evidence_count": len(evidence),
    }

    return {
        "status": "success",
        "qa": rec,
        "qa_meta": qa_meta,
        "response": answer_text_final,
        "answer": answer_text_final,
        "citations": citations_norm,
        "qa_path": str(qa_path_out),
        "params": top_params,
        "time_filter_days": orchestrator_time_scope.get("time_filter_days"),
        "time_start": orchestrator_time_scope.get("time_start"),
        "time_end": orchestrator_time_scope.get("time_end"),
        "orchestrator_time_scope": orchestrator_time_scope,
        "effective_source": effective_time_filter_source,
        "evidence_result": evidence_result,
        "qa_debug": rec.get("debug", {}),
        "qa_evidence": qa_evidence_public,
        "r3_min_selection": rec.get("debug", {}).get("r3_min_selection"),
        "r3_min_backfill": rec.get("debug", {}).get("r3_min_backfill"),
        "r3_visible_bucket": rec.get("debug", {}).get("r3_visible_bucket"),
        "doc_time_filter": rec.get("debug", {}).get("doc_time_filter"),
        "retrieval_time_scope": rec.get("debug", {}).get("retrieval_time_scope"),
        "citation_assembly": rec.get("debug", {}).get("citation_assembly"),
        "evidence_published_at": rec.get("debug", {}).get("evidence_published_at"),
        "debug": top_debug,
    }
