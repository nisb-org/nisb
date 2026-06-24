from __future__ import annotations

import importlib
from typing import Any, Callable, Dict, List, Optional, Tuple

from .room_helpers import (
    _coerce_dict_list,
    _get_int,
    _get_str,
)

_QASCOPE_CALLABLE: Optional[Callable[..., Any]] = None


def _load_qascope_callable() -> Optional[Callable[..., Any]]:
    global _QASCOPE_CALLABLE
    if callable(_QASCOPE_CALLABLE):
        return _QASCOPE_CALLABLE

    candidates: List[Tuple[str, str]] = [
        ("tools.doc.analysis.qascope", "nisb_qascope_ask"),
        ("tools.doc.analysis.qascope", "nisb_qascopeask"),
        ("tools.doc.analysis.qascope", "nisb_qa_scope_ask"),
        ("tools.doc.analysis.qa_scope", "nisb_qascope_ask"),
        ("tools.doc.analysis.qa_scope", "nisb_qascopeask"),
        ("tools.doc.analysis.qa_scope", "nisb_qa_scope_ask"),
    ]

    for module_name, attr_name in candidates:
        try:
            mod = importlib.import_module(module_name)
        except Exception:
            continue
        fn = getattr(mod, attr_name, None)
        if callable(fn):
            _QASCOPE_CALLABLE = fn
            return fn
    return None


def _safe_str(value: Any, default: str = "") -> str:
    if value is None:
        return default
    s = str(value).strip()
    return s if s else default


def _normalize_positive_int(value: Any) -> int:
    try:
        if value is None or value == "":
            return 0
        return max(0, int(float(value)))
    except Exception:
        return 0


def _normalize_bool_or_none(value: Any) -> Optional[bool]:
    if isinstance(value, bool):
        return value
    if value is None or value == "":
        return None
    s = str(value).strip().lower()
    if s in ("true", "1", "yes", "on"):
        return True
    if s in ("false", "0", "no", "off"):
        return False
    return None


def _first_dict(*values: Any) -> Dict[str, Any]:
    for value in values:
        if isinstance(value, dict) and value:
            return value
    return {}


def _first_dict_list(*values: Any) -> List[Dict[str, Any]]:
    for value in values:
        items = _coerce_dict_list(value)
        if items:
            return items
    return []


def _is_room_shared_scope(base_args: Dict[str, Any]) -> bool:
    return _safe_str(base_args.get("effective_execution_scope")).lower() == "room_shared"


def _drop_binding_scope_keys(payload: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(payload or {})
    for key in (
        "library_id", "libraryId",
        "doc_id", "docId",
        "group_id", "groupId",
        "store_scope", "storeScope", "storescope",
        "qa_store_scope", "qastorescope",
        "evidence_scope", "evidenceScope", "evidencescope",
        "qa_evidence_scope", "qaevidencescope",
        "time_filter_days", "timeFilterDays",
        "time_start", "timeStart",
        "time_end", "timeEnd",
        "rag_context",
        "rag_store_scope",
        "rag_evidence_scope",
    ):
        out.pop(key, None)
    return out


def _extract_time_payload(binding: Dict[str, Any], base_args: Dict[str, Any]) -> Dict[str, Any]:
    shared_scope = _is_room_shared_scope(base_args)

    raw_days = (
        binding.get("time_filter_days")
        or binding.get("timeFilterDays")
        or (None if shared_scope else base_args.get("time_filter_days"))
        or (None if shared_scope else base_args.get("timeFilterDays"))
    )
    time_filter_days = _normalize_positive_int(raw_days)

    time_start = _safe_str(
        binding.get("time_start")
        or binding.get("timeStart")
        or ("" if shared_scope else base_args.get("time_start"))
        or ("" if shared_scope else base_args.get("timeStart"))
    )
    time_end = _safe_str(
        binding.get("time_end")
        or binding.get("timeEnd")
        or ("" if shared_scope else base_args.get("time_end"))
        or ("" if shared_scope else base_args.get("timeEnd"))
    )

    if time_filter_days > 0:
        return {
            "time_filter_days": time_filter_days,
            "time_start": "",
            "time_end": "",
        }

    return {
        "time_filter_days": "",
        "time_start": time_start,
        "time_end": time_end,
    }


def _extract_r3_payload(base_args: Dict[str, Any]) -> Dict[str, Any]:
    raw_dedupe = (
        base_args.get("dedupe_by_doc_id")
        if base_args.get("dedupe_by_doc_id") not in (None, "")
        else base_args.get("dedupeByDocId")
    )
    dedupe_by_doc_id = _normalize_bool_or_none(raw_dedupe)

    raw_bucket_mode = (
        base_args.get("time_bucket_mode")
        if base_args.get("time_bucket_mode") not in (None, "")
        else base_args.get("timeBucketMode")
    )
    time_bucket_mode = _safe_str(raw_bucket_mode).lower()

    if time_bucket_mode not in ("", "off", "two_phase"):
        time_bucket_mode = "off"

    out: Dict[str, Any] = {}
    if dedupe_by_doc_id is not None:
        out["dedupe_by_doc_id"] = bool(dedupe_by_doc_id)
        out["dedupeByDocId"] = bool(dedupe_by_doc_id)

    if time_bucket_mode:
        out["time_bucket_mode"] = time_bucket_mode
        out["timeBucketMode"] = time_bucket_mode

    return out


def _call_qascope_reply(
    *,
    base_args: Dict[str, Any],
    question: str,
    request_id: str,
    binding: Dict[str, Any],
    model_name: str,
) -> Dict[str, Any]:
    fn = _load_qascope_callable()
    if not callable(fn):
        raise RuntimeError("nisb_qascope_ask not found")

    time_payload = _extract_time_payload(binding, base_args)
    r3_payload = _extract_r3_payload(base_args)

    qa_payload: Dict[str, Any] = {
        "question": question,
        "content": question,
        "request_id": request_id,
        "store_scope": binding["store_scope"],
        "storescope": binding["store_scope"],
        "qa_store_scope": binding["store_scope"],
        "qastorescope": binding["store_scope"],
        "evidence_scope": binding["evidence_scope"],
        "evidencescope": binding["evidence_scope"],
        "qa_evidence_scope": binding["evidence_scope"],
        "qaevidencescope": binding["evidence_scope"],
        "model": model_name,
        "answer_lang": _get_str(base_args, ["qa_answer_lang", "answer_lang"], "zh") or "zh",
        "top_k": _get_int(base_args, ["qa_top_k", "top_k"], 12, 1, 50),
        "max_evidence": _get_int(base_args, ["qa_max_evidence", "max_evidence"], 10, 1, 30),
        "min_citations": _get_int(base_args, ["qa_min_citations", "min_citations"], 1, 0, 20),
        "max_citations": _get_int(base_args, ["qa_max_citations", "max_citations"], 8, 1, 20),
        "max_output_tokens": _get_int(base_args, ["qa_max_output_tokens", "max_output_tokens"], 1800, 256, 8000),
        "time_filter_days": time_payload.get("time_filter_days") or "",
        "time_start": time_payload.get("time_start") or "",
        "time_end": time_payload.get("time_end") or "",
        **r3_payload,
    }

    if binding.get("library_id"):
        qa_payload["library_id"] = binding["library_id"]
    if binding.get("group_id"):
        qa_payload["group_id"] = binding["group_id"]
    if binding.get("doc_id"):
        qa_payload["doc_id"] = binding["doc_id"]

    merged = (
        _drop_binding_scope_keys(base_args)
        if _is_room_shared_scope(base_args)
        else dict(base_args or {})
    )
    merged.update(qa_payload)
    merged["request_id"] = request_id

    attempts = [
        lambda: fn(merged),
        lambda: fn(base_args, qa_payload, request_id=request_id),
        lambda: fn(base_args, qa_payload),
        lambda: fn(qa_payload, request_id=request_id),
        lambda: fn(qa_payload),
    ]

    last_error: Optional[Exception] = None
    for attempt in attempts:
        try:
            res = attempt()
            if isinstance(res, dict):
                return res
            return {
                "status": "success",
                "qa": {
                    "answer": str(res or "").strip(),
                    "citations": [],
                    "storescope": binding["store_scope"],
                    "evidencescope": binding["evidence_scope"],
                },
            }
        except TypeError as ex:
            last_error = ex
            continue

    if last_error is not None:
        raise last_error
    raise RuntimeError("nisb_qascope_ask call failed")


def _extract_qascope_result(question: str, qares: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(qares, dict):
        raise ValueError("qares is not dict")

    success_flag = qares.get("success")
    status = str(qares.get("status") or "").strip().lower()
    if success_flag is False or (status and status not in ("success", "ok")):
        raise ValueError(str(qares.get("message") or "qares failed"))

    qa = qares.get("qa") if isinstance(qares.get("qa"), dict) else {}

    answer = str(
        qa.get("answer")
        or qares.get("answer")
        or qares.get("response")
        or ""
    ).strip()

    citations = qa.get("citations") if isinstance(qa.get("citations"), list) else qares.get("citations")
    rss_evidence = qares.get("rss_evidence") if isinstance(qares.get("rss_evidence"), list) else qa.get("rss_evidence")
    market_evidence = qares.get("market_evidence") if isinstance(qares.get("market_evidence"), list) else qa.get("market_evidence")

    citations = _coerce_dict_list(citations)
    rss_evidence = _coerce_dict_list(rss_evidence)
    market_evidence = _coerce_dict_list(market_evidence)

    qa_evidence_result = qa.get("evidence_result") if isinstance(qa.get("evidence_result"), dict) else {}
    root_evidence_result = qares.get("evidence_result") if isinstance(qares.get("evidence_result"), dict) else {}

    merged_evidence_result = {
        **root_evidence_result,
        **qa_evidence_result,
    }

    existing_qa_meta = (
        merged_evidence_result.get("qa_meta")
        if isinstance(merged_evidence_result.get("qa_meta"), dict)
        else {}
    )

    qa_meta = {
        **existing_qa_meta,
        "qa_id": str(qa.get("qa_id") or qa.get("qaid") or qares.get("qa_id") or qares.get("qaid") or "").strip(),
        "thread_id": str(qa.get("thread_id") or qa.get("threadid") or "").strip(),
        "store_scope": str(
            qa.get("store_scope")
            or qa.get("storescope")
            or qares.get("store_scope")
            or qares.get("storescope")
            or existing_qa_meta.get("store_scope")
            or ""
        ).strip(),
        "evidence_scope": str(
            qa.get("evidence_scope")
            or qa.get("evidencescope")
            or qares.get("evidence_scope")
            or qares.get("evidencescope")
            or existing_qa_meta.get("evidence_scope")
            or ""
        ).strip(),
        "time_filter_days": str(
            qa.get("time_filter_days")
            or qa.get("timeFilterDays")
            or qares.get("time_filter_days")
            or qares.get("timeFilterDays")
            or existing_qa_meta.get("time_filter_days")
            or ""
        ).strip(),
        "time_start": str(
            qa.get("time_start")
            or qa.get("timeStart")
            or qares.get("time_start")
            or qares.get("timeStart")
            or existing_qa_meta.get("time_start")
            or ""
        ).strip(),
        "time_end": str(
            qa.get("time_end")
            or qa.get("timeEnd")
            or qares.get("time_end")
            or qares.get("timeEnd")
            or existing_qa_meta.get("time_end")
            or ""
        ).strip(),
    }

    evidence_query = str(
        qares.get("evidence_query")
        or qares.get("evidencequery")
        or merged_evidence_result.get("evidence_query")
        or question
    ).strip() or question

    orchestrator_time_scope = _first_dict(
        qa.get("orchestrator_time_scope"),
        qares.get("orchestrator_time_scope"),
        merged_evidence_result.get("orchestrator_time_scope"),
    )

    retrieval_time_scope = _first_dict(
        qa.get("retrieval_time_scope"),
        qares.get("retrieval_time_scope"),
        merged_evidence_result.get("retrieval_time_scope"),
    )

    effective_source = str(
        qa.get("effective_source")
        or qares.get("effective_source")
        or merged_evidence_result.get("effective_source")
        or ""
    ).strip()

    candidate_docs_after_time = (
        retrieval_time_scope.get("candidate_docs_after_time")
        if isinstance(retrieval_time_scope, dict) and retrieval_time_scope.get("candidate_docs_after_time") is not None
        else merged_evidence_result.get("candidate_docs_after_time")
    )

    qa_debug = _first_dict(
        qa.get("qa_debug"),
        qares.get("qa_debug"),
        merged_evidence_result.get("qa_debug"),
    )
    qa_params = _first_dict(
        qa.get("qa_params"),
        qares.get("qa_params"),
        merged_evidence_result.get("qa_params"),
    )
    qa_evidence = _first_dict_list(
        qa.get("qa_evidence"),
        qares.get("qa_evidence"),
        merged_evidence_result.get("qa_evidence"),
    )
    r3_min_selection = _first_dict(
        qa.get("r3_min_selection"),
        qares.get("r3_min_selection"),
        merged_evidence_result.get("r3_min_selection"),
    )
    r3_min_backfill = _first_dict(
        qa.get("r3_min_backfill"),
        qares.get("r3_min_backfill"),
        merged_evidence_result.get("r3_min_backfill"),
    )
    r3_visible_bucket = _first_dict(
        qa.get("r3_visible_bucket"),
        qares.get("r3_visible_bucket"),
        merged_evidence_result.get("r3_visible_bucket"),
    )

    evidence_result = {
        **merged_evidence_result,
        "citations": citations,
        "rss_evidence": rss_evidence,
        "market_evidence": market_evidence,
        "evidence_query": evidence_query,
        "evidence_tools": ["nisb_qascope_ask"],
        "qa_meta": qa_meta,
        "orchestrator_time_scope": orchestrator_time_scope,
        "retrieval_time_scope": retrieval_time_scope,
        "effective_source": effective_source,
        "candidate_docs_after_time": candidate_docs_after_time,
    }

    if qa_debug:
        evidence_result["qa_debug"] = qa_debug
    if qa_params:
        evidence_result["qa_params"] = qa_params
    if qa_evidence:
        evidence_result["qa_evidence"] = qa_evidence
    if r3_min_selection:
        evidence_result["r3_min_selection"] = r3_min_selection
    if r3_min_backfill:
        evidence_result["r3_min_backfill"] = r3_min_backfill
    if r3_visible_bucket:
        evidence_result["r3_visible_bucket"] = r3_visible_bucket

    return {
        "content": answer,
        "citations": citations,
        "rss_evidence": rss_evidence,
        "market_evidence": market_evidence,
        "evidence_query": evidence_query,
        "evidence_tools": ["nisb_qascope_ask"],
        "evidence_result": evidence_result,
        "qa_meta": qa_meta,
        "orchestrator_time_scope": orchestrator_time_scope,
        "retrieval_time_scope": retrieval_time_scope,
        "effective_source": effective_source,
        "candidate_docs_after_time": candidate_docs_after_time,
    }
