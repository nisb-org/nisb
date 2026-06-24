#!/usr/bin/env python3
"""
Document concept analysis.

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


_SEARCH_QUERY = "definition concept meaning theory principle key term"


def _ensure_analysis_dir(doc_path: str) -> str:
    analysis_dir = os.path.join(doc_path, "analysis")
    os.makedirs(analysis_dir, exist_ok=True)
    return analysis_dir


def _build_concepts_prompt(context: str, output_language: str) -> str:
    return (
        f"{language_instruction(output_language)}\n\n"
        "You are a rigorous reading assistant. Based on the document passages below, "
        "analyze the core concepts in the document and their relationships.\n\n"
        f"{context}\n\n"
        "Output requirements:\n"
        "1. List the important concepts. Prefer original source terms when useful.\n"
        "2. Explain each concept in one or two concise sentences.\n"
        "3. Explain key relationships among the concepts, such as cause and effect, "
        "containment, contrast, dependency, premise and conclusion, or historical sequence.\n"
        "4. Do not invent concepts that are not supported by the passages.\n"
        "5. Use Markdown headings and bullet points."
    )


@auto_user_context
def nisb_doc_analyze_concepts(args: dict) -> dict:
    """Analyze core document concepts with hybrid retrieval."""
    args = args or {}
    user_ctx = get_user_ctx()
    base_path = user_ctx.base
    doc_id = str(args.get("doc_id", "")).strip()
    library_id_arg = str(args.get("library_id", "")).strip() or None
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
        artifact_path = os.path.join(analysis_dir, "concepts.json")

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
            text = doc_message(args, "concepts_no_results")
            artifact = {
                "doc_id": doc_id,
                "library_id": library_id,
                "type": "concepts",
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
                    "content": _build_concepts_prompt(context, output_language),
                }
            ],
            temperature=0.3,
            max_tokens=2000,
        )
        analysis = completion.choices[0].message.content or ""

        artifact = {
            "doc_id": doc_id,
            "library_id": library_id,
            "type": "concepts",
            "model": DOC_LLM_MODEL,
            "strategy": "hybrid",
            "ui_locale": ui_locale,
            "output_language": output_language,
            "language_code": output_language_code(output_language),
            "created_at": datetime.now().isoformat(),
            "text": analysis,
            "source": {
                "query": _SEARCH_QUERY,
                "results": len(results),
            },
        }
        with open(artifact_path, "w", encoding="utf-8") as f:
            json.dump(artifact, f, ensure_ascii=False, indent=2)

        return {"status": "success", "text": analysis, "raw": artifact}

    except Exception as exc:
        traceback.print_exc()
        return {
            "status": "error",
            "message": doc_message(args, "concepts_failed", error=str(exc)),
        }
