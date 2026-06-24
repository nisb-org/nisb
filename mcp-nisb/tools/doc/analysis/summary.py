#!/usr/bin/env python3
"""
Document summary generation.

This module supports multi-library document resolution, hybrid retrieval,
language-aware generation, and persistent JSON artifacts.
"""

from __future__ import annotations

import json
import os
import traceback
from datetime import datetime

from openai import OpenAI

from core.user_context import auto_user_context, get_user_ctx
from tools.doc.core.path_resolver import PathResolver
from tools.doc.core.search_sqlite import _hybrid_search_internal
from tools.doc.helpers import DOC_LLM_MODEL
from tools.doc.i18n import (
    can_reuse_analysis_artifact,
    doc_message,
    get_output_language,
    get_ui_locale,
    language_instruction,
    output_language_code,
)


_SEARCH_QUERY = "main idea argument conclusion theory key points"


def _ensure_analysis_dir(doc_path: str) -> str:
    analysis_dir = os.path.join(doc_path, "analysis")
    os.makedirs(analysis_dir, exist_ok=True)
    return analysis_dir


def _build_summary_prompt(context: str, level: str, output_language: str) -> str:
    return (
        f"{language_instruction(output_language)}\n\n"
        "You are a rigorous reading assistant. Based on the document passages below, "
        "generate a whole-document summary.\n\n"
        f"{context}\n\n"
        "Output requirements:\n"
        f"- Summary length level: {level}.\n"
        "- Use clear sections.\n"
        "- Explain the central thesis or main claim.\n"
        "- Explain the main evidence, reasoning path, or development structure.\n"
        "- Explain the conclusion, implication, or practical takeaway for the reader.\n"
        "- Keep important source terms, names, and technical expressions when helpful.\n"
        "- Do not invent claims that are not supported by the passages."
    )


@auto_user_context
def nisb_doc_generate_summary(args: dict) -> dict:
    """Generate a document summary with hybrid retrieval."""
    args = args or {}
    user_ctx = get_user_ctx()
    base_path = user_ctx.base
    doc_id = str(args.get("doc_id", "")).strip()
    library_id_arg = str(args.get("library_id", "")).strip() or None
    level = str(args.get("level") or args.get("summary_level") or "medium").strip()
    force = bool(args.get("force", False))
    output_language = get_output_language(args)
    ui_locale = get_ui_locale(args)

    if not doc_id:
        return {"status": "error", "message": doc_message(args, "doc_id_required")}

    try:
        resolver = PathResolver(base_path, user_ctx.user_id)
        paths = resolver.resolve_doc_path(doc_id, library_id_arg)

        if paths.get("status") != "found":
            return {"status": "error", "message": doc_message(args, "doc_not_found")}

        library_id = paths.get("library_id") or library_id_arg
        doc_path = paths["doc_path"]
        analysis_dir = _ensure_analysis_dir(doc_path)
        artifact_path = os.path.join(analysis_dir, "summary.json")

        if not force and os.path.exists(artifact_path):
            try:
                with open(artifact_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if can_reuse_analysis_artifact(
                    data,
                    model=DOC_LLM_MODEL,
                    strategy="hybrid",
                    output_language=output_language,
                ):
                    return {
                        "status": "success",
                        "text": data.get("text", ""),
                        "raw": data,
                    }
            except Exception:
                pass

        results = _hybrid_search_internal(
            base_path=base_path,
            user_ctx=user_ctx,
            query=_SEARCH_QUERY,
            doc_id=doc_id,
            library_id=library_id,
            top_k=40,
            weights={"dense": 0.7, "sparse": 0.3},
        )

        if not results:
            text = doc_message(args, "summary_no_results")
            artifact = {
                "doc_id": doc_id,
                "library_id": library_id,
                "type": "summary",
                "level": level,
                "model": DOC_LLM_MODEL,
                "strategy": "hybrid",
                "ui_locale": ui_locale,
                "output_language": output_language,
                "language_code": output_language_code(output_language),
                "created_at": datetime.now().isoformat(),
                "text": text,
                "source": {
                    "query": _SEARCH_QUERY,
                    "results": 0,
                },
            }
            with open(artifact_path, "w", encoding="utf-8") as f:
                json.dump(artifact, f, ensure_ascii=False, indent=2)
            return {"status": "success", "text": text, "raw": artifact}

        context = "\n\n".join(str(r.get("text", "")) for r in results)

        client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
        completion = client.chat.completions.create(
            model=DOC_LLM_MODEL,
            messages=[
                {
                    "role": "user",
                    "content": _build_summary_prompt(context, level, output_language),
                }
            ],
            temperature=0.3,
            max_tokens=1200,
        )
        summary = completion.choices[0].message.content or ""

        artifact = {
            "doc_id": doc_id,
            "library_id": library_id,
            "type": "summary",
            "level": level,
            "model": DOC_LLM_MODEL,
            "strategy": "hybrid",
            "ui_locale": ui_locale,
            "output_language": output_language,
            "language_code": output_language_code(output_language),
            "created_at": datetime.now().isoformat(),
            "text": summary,
            "source": {
                "query": _SEARCH_QUERY,
                "results": len(results),
            },
        }
        with open(artifact_path, "w", encoding="utf-8") as f:
            json.dump(artifact, f, ensure_ascii=False, indent=2)

        return {"status": "success", "text": summary, "raw": artifact}

    except Exception as exc:
        traceback.print_exc()
        return {
            "status": "error",
            "message": doc_message(args, "summary_failed", error=str(exc)),
        }
