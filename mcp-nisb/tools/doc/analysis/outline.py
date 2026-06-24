#!/usr/bin/env python3
"""
Document outline generation.

This module supports multi-library document resolution, hybrid retrieval,
language-aware generation, and persistent JSON artifacts.
"""

from __future__ import annotations

import json
import os
import sys
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


_SEARCH_QUERY = "structure chapter section main topic headings table of contents"


def _ensure_analysis_dir(doc_path: str) -> str:
    analysis_dir = os.path.join(doc_path, "analysis")
    os.makedirs(analysis_dir, exist_ok=True)
    return analysis_dir


def _build_outline_prompt(context: str, output_language: str) -> str:
    return (
        f"{language_instruction(output_language)}\n\n"
        "You are a rigorous reading assistant. Based on the document passages below, "
        "generate a hierarchical outline for the whole document.\n\n"
        f"{context}\n\n"
        "Output requirements:\n"
        "- Use Markdown headings and bullet points.\n"
        "- Start with the overall theme.\n"
        "- Group the content into major parts, sections, and subtopics when possible.\n"
        "- Keep important source terms, names, and technical expressions when helpful.\n"
        "- Do not invent chapters that are not supported by the passages.\n\n"
        "Suggested structure:\n"
        "# Overall theme\n"
        "## Part or major section\n"
        "### Subtopic\n"
        "- Key point"
    )


@auto_user_context
def nisb_doc_generate_outline(args: dict) -> dict:
    """Generate a document outline with hybrid retrieval."""
    args = args or {}
    user_ctx = get_user_ctx()
    base_path = user_ctx.base
    doc_id = str(args.get("doc_id", "")).strip()
    library_id_arg = str(args.get("library_id", "")).strip() or None
    force = bool(args.get("force", False))
    output_language = get_output_language(args)
    ui_locale = get_ui_locale(args)

    print("[OUTLINE_DEBUG] Start outline generation", file=sys.stderr)
    print(f"[OUTLINE_DEBUG] doc_id={doc_id}", file=sys.stderr)
    print(f"[OUTLINE_DEBUG] library_id_arg={library_id_arg}", file=sys.stderr)
    print(f"[OUTLINE_DEBUG] base_path={base_path}", file=sys.stderr)
    print(f"[OUTLINE_DEBUG] output_language={output_language}", file=sys.stderr)

    if not doc_id:
        print("[OUTLINE_DEBUG] Empty doc_id", file=sys.stderr)
        return {"status": "error", "message": doc_message(args, "doc_id_required")}

    try:
        resolver = PathResolver(base_path, user_ctx.user_id)
        paths = resolver.resolve_doc_path(doc_id, library_id_arg)

        print(f"[OUTLINE_DEBUG] paths status={paths.get('status')}", file=sys.stderr)

        if paths.get("status") != "found":
            print("[OUTLINE_DEBUG] Document not found", file=sys.stderr)
            return {"status": "error", "message": doc_message(args, "doc_not_found")}

        library_id = paths.get("library_id") or library_id_arg
        print(f"[OUTLINE_DEBUG] resolved library_id={library_id}", file=sys.stderr)

        doc_path = paths["doc_path"]
        analysis_dir = _ensure_analysis_dir(doc_path)
        artifact_path = os.path.join(analysis_dir, "outline.json")

        if not force and os.path.exists(artifact_path):
            print("[OUTLINE_DEBUG] Existing outline artifact found", file=sys.stderr)
            try:
                with open(artifact_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if can_reuse_analysis_artifact(
                    data,
                    model=DOC_LLM_MODEL,
                    strategy="hybrid",
                    output_language=output_language,
                ):
                    print("[OUTLINE_DEBUG] Reusing existing outline artifact", file=sys.stderr)
                    return {
                        "status": "success",
                        "text": data.get("text", ""),
                        "raw": data,
                    }
            except Exception:
                pass

        print("[OUTLINE_DEBUG] Running hybrid retrieval", file=sys.stderr)

        results = _hybrid_search_internal(
            base_path=base_path,
            user_ctx=user_ctx,
            query=_SEARCH_QUERY,
            doc_id=doc_id,
            library_id=library_id,
            top_k=40,
            weights={"dense": 0.7, "sparse": 0.3},
        )

        print(f"[OUTLINE_DEBUG] hybrid returned {len(results)} results", file=sys.stderr)

        if not results:
            text = doc_message(args, "outline_no_results")
            artifact = {
                "doc_id": doc_id,
                "library_id": library_id,
                "type": "outline",
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

        context = "\n\n".join(
            f"[Snippet {i + 1}]\n{r.get('text', '')}"
            for i, r in enumerate(results)
        )

        client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
        completion = client.chat.completions.create(
            model=DOC_LLM_MODEL,
            messages=[
                {
                    "role": "user",
                    "content": _build_outline_prompt(context, output_language),
                }
            ],
            temperature=0.3,
            max_tokens=2000,
        )
        outline = completion.choices[0].message.content or ""

        artifact = {
            "doc_id": doc_id,
            "library_id": library_id,
            "type": "outline",
            "model": DOC_LLM_MODEL,
            "strategy": "hybrid",
            "ui_locale": ui_locale,
            "output_language": output_language,
            "language_code": output_language_code(output_language),
            "created_at": datetime.now().isoformat(),
            "text": outline,
            "source": {
                "query": _SEARCH_QUERY,
                "results": len(results),
            },
        }
        with open(artifact_path, "w", encoding="utf-8") as f:
            json.dump(artifact, f, ensure_ascii=False, indent=2)

        return {"status": "success", "text": outline, "raw": artifact}

    except Exception as exc:
        traceback.print_exc()
        return {
            "status": "error",
            "message": doc_message(args, "outline_failed", error=str(exc)),
        }
