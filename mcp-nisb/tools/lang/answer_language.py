from __future__ import annotations

import importlib
import os
import re
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

SAFE_DEFAULT_ANSWER_LANG = "en"

_LANG_ALIASES = {
    "zh": "zh",
    "zh-cn": "zh",
    "zh-hans": "zh",
    "zh-hant": "zh",
    "zh-tw": "zh",
    "zh-hk": "zh",
    "cmn": "zh",
    "yue": "zh",
    "en": "en",
    "en-us": "en",
    "en-gb": "en",
    "ja": "ja",
    "ja-jp": "ja",
    "ko": "ko",
    "ko-kr": "ko",
    "fr": "fr",
    "fr-fr": "fr",
    "de": "de",
    "de-de": "de",
    "es": "es",
    "es-es": "es",
    "es-419": "es",
    "pt": "pt",
    "pt-pt": "pt",
    "pt-br": "pt",
    "it": "it",
    "it-it": "it",
    "ru": "ru",
    "ru-ru": "ru",
    "uk": "uk",
    "uk-ua": "uk",
    "ar": "ar",
    "ar-sa": "ar",
    "ar-eg": "ar",
    "hi": "hi",
    "hi-in": "hi",
    "tr": "tr",
    "tr-tr": "tr",
    "vi": "vi",
    "vi-vn": "vi",
    "th": "th",
    "th-th": "th",
    "id": "id",
    "id-id": "id",
    "ms": "ms",
    "ms-my": "ms",
    "nl": "nl",
    "nl-nl": "nl",
    "pl": "pl",
    "pl-pl": "pl",
    "cs": "cs",
    "cs-cz": "cs",
    "sv": "sv",
    "sv-se": "sv",
    "da": "da",
    "da-dk": "da",
    "no": "no",
    "nb": "no",
    "nn": "no",
    "fi": "fi",
    "fi-fi": "fi",
    "el": "el",
    "el-gr": "el",
    "he": "he",
    "he-il": "he",
    "fa": "fa",
    "fa-ir": "fa",
    "ur": "ur",
    "ur-pk": "ur",
    "bn": "bn",
    "bn-bd": "bn",
    "ta": "ta",
    "ta-in": "ta",
    "te": "te",
    "te-in": "te",
    "ml": "ml",
    "ml-in": "ml",
    "mr": "mr",
    "mr-in": "mr",
    "gu": "gu",
    "gu-in": "gu",
    "pa": "pa",
    "pa-in": "pa",
    "ro": "ro",
    "ro-ro": "ro",
    "hu": "hu",
    "hu-hu": "hu",
    "bg": "bg",
    "bg-bg": "bg",
    "sr": "sr",
    "sr-rs": "sr",
    "hr": "hr",
    "hr-hr": "hr",
    "sk": "sk",
    "sk-sk": "sk",
    "sl": "sl",
    "sl-si": "sl",
    "lt": "lt",
    "lt-lt": "lt",
    "lv": "lv",
    "lv-lv": "lv",
    "et": "et",
    "et-ee": "et",
}

_LANGUAGE_NAMES = {
    "af": "Afrikaans",
    "ar": "Arabic",
    "bg": "Bulgarian",
    "bn": "Bengali",
    "cs": "Czech",
    "da": "Danish",
    "de": "German",
    "el": "Greek",
    "en": "English",
    "es": "Spanish",
    "et": "Estonian",
    "fa": "Persian",
    "fi": "Finnish",
    "fr": "French",
    "gu": "Gujarati",
    "he": "Hebrew",
    "hi": "Hindi",
    "hr": "Croatian",
    "hu": "Hungarian",
    "id": "Indonesian",
    "it": "Italian",
    "ja": "Japanese",
    "ko": "Korean",
    "lt": "Lithuanian",
    "lv": "Latvian",
    "ml": "Malayalam",
    "mr": "Marathi",
    "ms": "Malay",
    "nl": "Dutch",
    "no": "Norwegian",
    "pa": "Punjabi",
    "pl": "Polish",
    "pt": "Portuguese",
    "ro": "Romanian",
    "ru": "Russian",
    "sk": "Slovak",
    "sl": "Slovenian",
    "sr": "Serbian",
    "sv": "Swedish",
    "ta": "Tamil",
    "te": "Telugu",
    "th": "Thai",
    "tr": "Turkish",
    "uk": "Ukrainian",
    "ur": "Urdu",
    "vi": "Vietnamese",
    "zh": "Simplified Chinese",
}

_SCRIPT_RANGES: Sequence[Tuple[str, str]] = (
    ("ja", r"[\u3040-\u30ff]"),
    ("ko", r"[\uac00-\ud7af]"),
    ("th", r"[\u0e00-\u0e7f]"),
    ("hi", r"[\u0900-\u097f]"),
    ("bn", r"[\u0980-\u09ff]"),
    ("pa", r"[\u0a00-\u0a7f]"),
    ("gu", r"[\u0a80-\u0aff]"),
    ("ta", r"[\u0b80-\u0bff]"),
    ("te", r"[\u0c00-\u0c7f]"),
    ("ml", r"[\u0d00-\u0d7f]"),
    ("ar", r"[\u0600-\u06ff]"),
    ("he", r"[\u0590-\u05ff]"),
    ("ru", r"[\u0400-\u04ff]"),
    ("el", r"[\u0370-\u03ff]"),
)

_LATIN_HINTS = {
    "fr": {"bonjour", "merci", "pourquoi", "avec", "dans", "est", "une", "des", "les", "le", "la", "comme", "vous", "être"},
    "de": {"und", "ist", "nicht", "bitte", "danke", "mit", "für", "wie", "der", "die", "das", "ein", "eine", "was"},
    "es": {"hola", "gracias", "porque", "porqué", "cómo", "como", "para", "con", "una", "qué", "que", "el", "la", "los", "las"},
    "pt": {"olá", "obrigado", "obrigada", "porque", "porquê", "como", "para", "com", "uma", "você", "não", "que", "os", "as"},
    "it": {"ciao", "grazie", "perché", "come", "con", "una", "che", "per", "il", "la", "gli", "della", "sono"},
    "nl": {"hallo", "dank", "waarom", "hoe", "met", "een", "voor", "niet", "het", "de", "dat", "zijn"},
    "tr": {"merhaba", "teşekkür", "neden", "nasıl", "ile", "bir", "için", "ve", "değil", "olarak"},
    "vi": {"xin", "cảm", "ơn", "và", "không", "cho", "một", "là", "của", "người"},
    "id": {"halo", "terima", "kasih", "dan", "tidak", "untuk", "dengan", "yang", "adalah", "ini"},
    "ms": {"hai", "terima", "kasih", "dan", "tidak", "untuk", "dengan", "yang", "adalah", "ini"},
    "en": {"the", "and", "what", "why", "how", "with", "for", "please", "is", "are", "can", "explain"},
}

_DEFAULT_DETECTOR_ORDER = ("builtin", "lingua", "langdetect")


def normalize_answer_lang(value: Any) -> str:
    raw = str(value or "").strip().lower().replace("_", "-")
    if not raw:
        return ""

    if raw in _LANG_ALIASES:
        return _LANG_ALIASES[raw]

    if re.fullmatch(r"[a-z]{2,3}(?:-[a-z0-9]{2,8})?", raw):
        base = raw.split("-")[0]
        return _LANG_ALIASES.get(base, base)

    return ""


def language_name(lang: str) -> str:
    code = normalize_answer_lang(lang) or SAFE_DEFAULT_ANSWER_LANG
    return _LANGUAGE_NAMES.get(code, f"the language code '{code}'")


def _text_stats(text: str) -> Dict[str, Any]:
    s = str(text or "").strip()
    return {
        "length": len(s),
        "has_cjk": bool(re.search(r"[\u4e00-\u9fff]", s)),
        "has_kana": bool(re.search(r"[\u3040-\u30ff]", s)),
        "has_hangul": bool(re.search(r"[\uac00-\ud7af]", s)),
        "has_latin": bool(re.search(r"[A-Za-z]", s)),
        "has_arabic": bool(re.search(r"[\u0600-\u06ff]", s)),
        "has_cyrillic": bool(re.search(r"[\u0400-\u04ff]", s)),
        "has_devanagari": bool(re.search(r"[\u0900-\u097f]", s)),
        "has_greek": bool(re.search(r"[\u0370-\u03ff]", s)),
        "has_hebrew": bool(re.search(r"[\u0590-\u05ff]", s)),
        "has_thai": bool(re.search(r"[\u0e00-\u0e7f]", s)),
    }

def _detect_language_latin_hints(text: str) -> str:
    s = str(text or "").strip().lower()
    if not s:
        return ""

    tokens = set(re.findall(r"[a-zÀ-ÿĀ-ž]+", s, flags=re.IGNORECASE))
    if not tokens:
        return ""

    best_lang = ""
    best_score = 0

    for lang, words in _LATIN_HINTS.items():
        score = sum(1 for word in words if word in tokens)
        if score > best_score:
            best_score = score
            best_lang = lang

    if best_score >= 2:
        return best_lang

    return ""


def detect_language_builtin(text: str) -> str:
    s = str(text or "").strip()
    if not s:
        return ""

    stats = _text_stats(s)

    if stats["has_kana"]:
        return "ja"
    if stats["has_hangul"]:
        return "ko"
    if stats["has_thai"]:
        return "th"
    if stats["has_arabic"]:
        return "ar"
    if stats["has_hebrew"]:
        return "he"
    if stats["has_devanagari"]:
        return "hi"
    if stats["has_greek"]:
        return "el"
    if stats["has_cyrillic"]:
        return "ru"
    if stats["has_cjk"]:
        return "zh"

    for lang, pattern in _SCRIPT_RANGES:
        if re.search(pattern, s):
            return lang

    hinted = _detect_language_latin_hints(s)
    if hinted:
        return hinted

    return ""


def _detect_with_lingua(text: str) -> str:
    try:
        mod = importlib.import_module("lingua")
    except Exception:
        return ""

    try:
        Language = getattr(mod, "Language")
        LanguageDetectorBuilder = getattr(mod, "LanguageDetectorBuilder")
        detector = LanguageDetectorBuilder.from_all_languages().build()
        result = detector.detect_language_of(text)
        if not result:
            return ""
        iso = ""
        if hasattr(result, "iso_code_639_1") and result.iso_code_639_1 is not None:
            iso = str(result.iso_code_639_1.name).lower()
        elif hasattr(result, "name"):
            iso = str(result.name).lower()
        return normalize_answer_lang(iso)
    except Exception:
        return ""


def _detect_with_langdetect(text: str) -> str:
    try:
        mod = importlib.import_module("langdetect")
    except Exception:
        return ""

    try:
        detect = getattr(mod, "detect")
        code = detect(text)
        return normalize_answer_lang(code)
    except Exception:
        return ""


def detect_language(
    text: str,
    detector_order: Optional[Sequence[str]] = None,
) -> Tuple[str, Dict[str, Any]]:
    s = str(text or "").strip()
    dbg: Dict[str, Any] = {
        "text_length": len(s),
        "detector_order": list(detector_order or _DEFAULT_DETECTOR_ORDER),
        "used": "",
        "candidates": [],
    }
    if not s:
        return "", dbg

    order = tuple(detector_order or _DEFAULT_DETECTOR_ORDER)

    for detector_name in order:
        code = ""
        if detector_name == "builtin":
            code = detect_language_builtin(s)
        elif detector_name == "lingua":
            code = _detect_with_lingua(s)
        elif detector_name == "langdetect":
            code = _detect_with_langdetect(s)

        code = normalize_answer_lang(code)
        dbg["candidates"].append({"detector": detector_name, "lang": code})
        if code:
            dbg["used"] = detector_name
            dbg["resolved"] = code
            return code, dbg

    dbg["resolved"] = ""
    return "", dbg


def resolve_answer_lang(
    *,
    question: str,
    args: Optional[Dict[str, Any]] = None,
    default_lang: str = SAFE_DEFAULT_ANSWER_LANG,
    detector_order: Optional[Sequence[str]] = None,
) -> Tuple[str, Dict[str, Any]]:
    payload = args or {}

    from_question, detect_dbg = detect_language(question, detector_order=detector_order)

    metadata_lang = normalize_answer_lang(
        _get_first(
            payload,
            "_answer_lang",
            "answer_lang",
            "answerLang",
            "qa_answer_lang",
            "qaAnswerLang",
        )
    )
    ignored_locale = normalize_answer_lang(
        _get_first(
            payload,
            "locale",
            "ui_language",
            "uiLanguage",
            "ui_lang",
            "uiLang",
            "lang",
        )
    )
    fallback = normalize_answer_lang(default_lang) or SAFE_DEFAULT_ANSWER_LANG

    resolved = from_question or metadata_lang or fallback
    source = "question" if from_question else ("metadata" if metadata_lang else "default")

    dbg = {
        "question_detected": from_question or "",
        "metadata_lang": metadata_lang or "",
        "ignored_locale": ignored_locale or "",
        "default": fallback,
        "resolved": resolved,
        "source": source,
        "detector": detect_dbg,
    }
    return resolved, dbg


def answer_language_instruction(answer_lang: str) -> str:
    lang = normalize_answer_lang(answer_lang) or SAFE_DEFAULT_ANSWER_LANG
    lang_name = language_name(lang)

    return (
        f"Answer in {lang_name}. "
        "Keep source titles, URLs, code, tool names, and protocol fields unchanged."
    )


def english_labels() -> Dict[str, str]:
    return {
        "question_label": "Question",
        "highlights_title": "Key points:",
        "claim_prefix": "Key point",
        "fallback_intro": "Here are evidence-grounded key points based on the retrieved snippets:",
        "no_evidence": "No evidence snippets relevant to the question were retrieved, so a cited answer cannot be provided.",
        "empty_answer_with_evidence": "Relevant evidence was retrieved, but the final answer could not be generated. Please narrow the question to a more specific library, document, or subtopic and try again.",
        "empty_answer_no_evidence": "No usable evidence was retrieved within the current knowledge scope. Please check the library, group, or document scope, or make the question more specific.",
    }


def append_highlights(answer_text: str, highlights: Sequence[str], title: Optional[str] = None) -> str:
    text = str(answer_text or "").strip()
    items = [str(x).strip() for x in (highlights or []) if str(x).strip()]
    if not items:
        return text

    block_title = str(title or english_labels()["highlights_title"]).strip()
    block = block_title + "\n" + "\n".join([f"- {x}" for x in items])

    if text:
        return (text + "\n\n" + block).strip()
    return block.strip()


def build_fallback_answer(question: str, evidence: List[Dict[str, Any]], shortener=None) -> Dict[str, Any]:
    labels = english_labels()
    shrink = shortener or (lambda s, n: str(s or "")[:n])

    if not evidence:
        return {
            "answer": f"{labels['no_evidence']}\n{labels['question_label']}: {question}",
            "claims": [],
            "citations": [],
        }

    claims: List[str] = []
    citations: List[Dict[str, Any]] = []
    for i, ev in enumerate(evidence[:6], start=1):
        ex = ev.get("excerpt") or ""
        claims.append(f"{labels['claim_prefix']} {i}: {shrink(ex, 180)}")
        citations.append(
            {
                "library_id": ev.get("library_id"),
                "doc_id": ev.get("doc_id"),
                "span_index": ev.get("span_index"),
                "quote": shrink(ex, 220),
                "note": "evidence_excerpt",
            }
        )

    answer = labels["fallback_intro"] + "\n" + "\n".join(f"- {c}" for c in claims)
    return {"answer": answer, "claims": claims, "citations": citations}


def _get_first(payload: Dict[str, Any], *names: str) -> Any:
    for name in names:
        if name in payload:
            return payload.get(name)
    return None

