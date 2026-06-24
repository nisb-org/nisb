from __future__ import annotations

from typing import Any, Mapping


class _SafeFormatDict(dict):
    def __missing__(self, key: str) -> str:
        return "{" + key + "}"


def string_value(value: Any) -> str:
    return str(value or "").strip()


def normalize_ui_locale(value: Any) -> str:
    raw = string_value(value).replace("_", "-")
    lowered = raw.lower()

    if lowered in {"zh", "zh-cn", "zh-hans"}:
        return "zh-CN"
    if lowered.startswith("zh-"):
        return "zh-CN"
    if lowered in {"en", "en-us", "en-gb"}:
        return "en"
    if lowered.startswith("en-"):
        return "en"

    return "en"


def get_ui_locale(args: Mapping[str, Any] | None) -> str:
    args = args or {}

    for key in ("ui_locale", "locale", "language"):
        value = string_value(args.get(key))
        if value:
            return normalize_ui_locale(value)

    return "en"


def normalize_output_language(value: Any) -> str:
    raw = string_value(value)
    lowered = raw.replace("_", "-").lower()

    if not lowered:
        return ""

    if lowered in {"zh", "zh-cn", "zh-hans", "chinese", "chinese simplified", "simplified chinese"}:
        return "Chinese (Simplified)"
    if lowered.startswith("zh-"):
        return "Chinese (Simplified)"
    if "chinese" in lowered and "simplified" in lowered:
        return "Chinese (Simplified)"

    if lowered in {"en", "en-us", "en-gb", "english"}:
        return "English"
    if lowered.startswith("en-"):
        return "English"

    return "English"


def get_output_language(args: Mapping[str, Any] | None) -> str:
    args = args or {}

    for key in ("output_language", "target_language", "language"):
        value = normalize_output_language(args.get(key))
        if value:
            return value

    ui_locale = get_ui_locale(args)
    if ui_locale == "zh-CN":
        return "Chinese (Simplified)"

    return "English"


def output_language_code(output_language: Any) -> str:
    normalized = normalize_output_language(output_language)
    if normalized == "Chinese (Simplified)":
        return "zh-CN"
    return "en"


def language_instruction(output_language: Any) -> str:
    normalized = normalize_output_language(output_language) or "English"
    return (
        f"Write the final output in {normalized}. "
        "Do not switch to another language except when quoting original source terms, names, or titles."
    )


def can_reuse_analysis_artifact(
    data: Mapping[str, Any] | None,
    *,
    model: str,
    strategy: str,
    output_language: str,
) -> bool:
    if not isinstance(data, Mapping):
        return False

    return (
        data.get("model") == model
        and data.get("strategy") == strategy
        and data.get("output_language") == output_language
    )


_MESSAGES = {
    "doc_id_required": {
        "en": "doc_id cannot be empty.",
        "zh-CN": "doc_id \u4e0d\u80fd\u4e3a\u7a7a\u3002",
    },
    "doc_and_chunk_required": {
        "en": "doc_id and chunk_id are required.",
        "zh-CN": "doc_id \u548c chunk_id \u5fc5\u586b\u3002",
    },
    "library_id_required": {
        "en": "library_id is required.",
        "zh-CN": "library_id \u5fc5\u586b\u3002",
    },
    "doc_not_found": {
        "en": "Document not found.",
        "zh-CN": "\u6587\u6863\u4e0d\u5b58\u5728\u3002",
    },
    "doc_chunks_not_found": {
        "en": "Document was not found or has no chunks.",
        "zh-CN": "\u6587\u6863\u672a\u627e\u5230\u6216\u65e0 chunks\u3002",
    },
    "chunk_not_found": {
        "en": "chunk_id does not exist.",
        "zh-CN": "chunk_id \u4e0d\u5b58\u5728\u3002",
    },
    "chunk_out_of_range": {
        "en": "chunk_id {chunk_id} is out of range (0-{max_chunk}).",
        "zh-CN": "chunk_id {chunk_id} \u8d85\u51fa\u8303\u56f4 (0-{max_chunk})\u3002",
    },
    "outline_no_results": {
        "en": "Unable to generate an outline because not enough structure-related passages were found.",
        "zh-CN": "\u65e0\u6cd5\u751f\u6210\u7eb2\u8981\uff08\u672a\u627e\u5230\u8db3\u591f\u7684\u7ed3\u6784\u76f8\u5173\u6bb5\u843d\uff09\u3002",
    },
    "summary_no_results": {
        "en": "Unable to generate a summary because not enough core passages were found.",
        "zh-CN": "\u65e0\u6cd5\u751f\u6210\u6458\u8981\uff08\u672a\u627e\u5230\u8db3\u591f\u7684\u6838\u5fc3\u6bb5\u843d\uff09\u3002",
    },
    "concepts_no_results": {
        "en": "Unable to analyze concepts because not enough relevant passages were found.",
        "zh-CN": "\u65e0\u6cd5\u5206\u6790\u6982\u5ff5\uff08\u672a\u627e\u5230\u8db3\u591f\u7684\u76f8\u5173\u6bb5\u843d\uff09\u3002",
    },
    "outline_failed": {
        "en": "Outline generation failed: {error}",
        "zh-CN": "\u751f\u6210\u7eb2\u8981\u5931\u8d25\uff1a{error}",
    },
    "summary_failed": {
        "en": "Summary generation failed: {error}",
        "zh-CN": "\u751f\u6210\u6458\u8981\u5931\u8d25\uff1a{error}",
    },
    "concepts_failed": {
        "en": "Concept analysis failed: {error}",
        "zh-CN": "\u6982\u5ff5\u5206\u6790\u5931\u8d25\uff1a{error}",
    },
    "context_expand_title": {
        "en": "Context expansion",
        "zh-CN": "\u4e0a\u4e0b\u6587\u6269\u5c55",
    },
    "context_center_label": {
        "en": "Center",
        "zh-CN": "\u4e2d\u5fc3",
    },
    "context_range_label": {
        "en": "Range",
        "zh-CN": "\u8303\u56f4",
    },
    "context_expand_failed": {
        "en": "Context expansion failed: {error}",
        "zh-CN": "\u6269\u5c55\u5931\u8d25\uff1a{error}",
    },
    "bookmark_added": {
        "en": "Bookmark added at chunk {chunk_id}.",
        "zh-CN": "\u5df2\u5728 chunk {chunk_id} \u6dfb\u52a0\u4e66\u7b7e\u3002",
    },
    "bookmark_failed": {
        "en": "Bookmark failed: {error}",
        "zh-CN": "\u4e66\u7b7e\u5931\u8d25\uff1a{error}",
    },
    "annotation_empty": {
        "en": "Annotation content cannot be empty.",
        "zh-CN": "\u6279\u6ce8\u5185\u5bb9\u4e0d\u80fd\u4e3a\u7a7a\u3002",
    },
    "annotation_added": {
        "en": "Annotation added at chunk {chunk_id}: {content}",
        "zh-CN": "\u5df2\u5728 chunk {chunk_id} \u6dfb\u52a0\u6279\u6ce8\uff1a{content}",
    },
    "annotation_failed": {
        "en": "Annotation failed: {error}",
        "zh-CN": "\u6279\u6ce8\u5931\u8d25\uff1a{error}",
    },
    "unknown_error": {
        "en": "Unknown error",
        "zh-CN": "\u672a\u77e5\u9519\u8bef",
    },
    "network_reserved": {
        "en": "Network feature is reserved.",
        "zh-CN": "\u7f51\u7edc\u529f\u80fd\uff08\u9884\u7559\uff09\u3002",
    },
}


def doc_message(args: Mapping[str, Any] | None, key: str, **params: Any) -> str:
    locale = get_ui_locale(args)
    item = _MESSAGES.get(key) or {}
    text = item.get(locale) or item.get("en") or key
    return text.format_map(_SafeFormatDict(params))
