#!/usr/bin/env python3

import json
import os
import re
import time
import unicodedata
from copy import deepcopy
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import numpy as np

TEXT_EXTENSIONS = {
    ".txt", ".md", ".markdown", ".json", ".yaml", ".yml",
    ".py", ".js", ".ts", ".tsx", ".jsx", ".css", ".html",
    ".sh", ".env", ".toml", ".ini", ".csv",
    ".vue", ".svelte", ".mjs", ".cjs"
}
TEXT_EXTENSIONS_NO_JSON = tuple(sorted(TEXT_EXTENSIONS - {".json"}))
JSON_EXTENSIONS = (".json",)

MAX_TEXT_FILE_SIZE = 2 * 1024 * 1024
INDEX_EXCERPT_CHARS = 2400
MAX_SNIPPET = 180

DEFAULT_LIMIT = 20
SAFE_MAX_LIMIT = 60

FUZZY_THRESHOLD = 0.84
MAX_FUZZY_TEXT_TOKENS = 64

QUERY_CACHE_TTL = 0.0
PATH_CACHE_TTL = 1.0
TEXT_CACHE_TTL = 90.0

MAX_QUERY_CACHE = 64
MAX_PATH_CACHE = 128
MAX_TEXT_CACHE = 256

INDEX_DIRNAME = ".nisb_cache"
INDEX_DB_NAME = "search_index_v1.sqlite3"
MIN_SYNC_INTERVAL = 0.5

LIBRARY_SCAN_SUBDIRS = ("docs", "analysis")
SUPPORTED_SEARCH_MODULES = ("chat", "doc", "library", "files", "dirs")
SEARCH_SAMPLE_BYTES = 24 * 1024

FTS_QUERY_RESERVED = {"and", "or", "not", "near"}
MAX_QUERY_CHARS = 256
MAX_QUERY_TOKENS = 12
MAX_FTS_TOKENS = 8
MAX_COMPACT_CHARS = 64
SYMBOL_HEAVY_RATIO = 0.35
LONG_NL_WORDS = 6

EN_NL_STARTERS = {
    "what", "why", "how", "when", "where", "who", "which",
    "is", "are", "was", "were", "do", "does", "did",
    "can", "could", "would", "should", "tell", "show",
    "find", "list", "summarize", "summarise", "explain",
}

EN_STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "been", "being", "but", "by",
    "can", "could", "did", "do", "does", "for", "from", "had", "has", "have",
    "how", "i", "in", "into", "is", "it", "its", "of", "on", "or", "our",
    "should", "that", "the", "their", "them", "there", "these", "this",
    "those", "to", "was", "we", "were", "what", "when", "where", "which",
    "who", "why", "with", "would", "you", "your", "conversation", "discussed",
    "discuss", "topics", "topic", "about", "please", "me", "us", "they",
}

QUERY_CACHE: Dict[str, Tuple[float, Dict[str, Any]]] = {}
PATH_CACHE: Dict[str, Tuple[float, List[str]]] = {}
TEXT_CACHE: Dict[str, Tuple[float, str]] = {}


def now_ts() -> float:
    return time.time()


def cosine_similarity(a, b):
    denom = (np.linalg.norm(a) * np.linalg.norm(b))
    if denom == 0:
        return 0.0
    return float(np.dot(a, b) / denom)


def empty_grouped_results() -> Dict[str, List[Dict[str, Any]]]:
    return {
        "chat": [],
        "doc": [],
        "library": [],
        "files": [],
        "dirs": [],
    }


def ok_response(
    response_text: str,
    data: Dict[str, Any],
    legacy_query: Optional[str] = None,
    legacy_results: Optional[Any] = None,
    legacy_total: Optional[int] = None
) -> Dict[str, Any]:
    payload = {
        "status": "success",
        "response": response_text,
        "message": response_text,
        "tool_calls": [],
        "tool_results": [
            {
                "type": "search_results",
                "data": data
            }
        ]
    }
    if legacy_query is not None:
        payload["query"] = legacy_query
    if legacy_results is not None:
        payload["results"] = legacy_results
    if legacy_total is not None:
        payload["total"] = legacy_total
    return payload


def error_response(message: str) -> Dict[str, Any]:
    return {
        "status": "error",
        "response": message,
        "message": message,
        "tool_calls": [],
        "tool_results": []
    }


def clone_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    return deepcopy(payload)


def prune_cache(cache: Dict[str, Tuple[float, Any]], max_items: int) -> None:
    if len(cache) <= max_items:
        return
    keep = sorted(cache.items(), key=lambda kv: kv[1][0], reverse=True)[:max_items]
    cache.clear()
    cache.update(dict(keep))


def cache_get(cache: Dict[str, Tuple[float, Any]], key: str, ttl: float) -> Optional[Any]:
    item = cache.get(key)
    if not item:
        return None
    ts, value = item
    if (now_ts() - ts) > ttl:
        cache.pop(key, None)
        return None
    return value


def cache_set(cache: Dict[str, Tuple[float, Any]], key: str, value: Any, max_items: int) -> None:
    cache[key] = (now_ts(), value)
    prune_cache(cache, max_items)


def normalize_text(value: Any) -> str:
    s = unicodedata.normalize("NFKC", str(value or ""))
    s = s.replace("\u3000", " ")
    s = s.lower()
    s = re.sub(r"[_/\\|:;,.，。；、()\[\]{}<>《》“”\"'`~!@#$%^&*+=?-]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def compact_text(value: Any) -> str:
    norm = normalize_text(value)
    if not norm:
        return ""
    return "".join(ch for ch in norm if not ch.isspace())


def split_tokens(value: Any) -> List[str]:
    norm = normalize_text(value)
    if not norm:
        return []
    parts = re.findall(r"[a-z0-9_]+|[\u4e00-\u9fff]+", norm)
    return dedupe_keep_order([p for p in parts if p])


def dedupe_keep_order(items: Iterable[str]) -> List[str]:
    seen = set()
    out = []
    for x in items:
        if not x or x in seen:
            continue
        seen.add(x)
        out.append(x)
    return out


def clamp_limit(value: Any, default: int = DEFAULT_LIMIT) -> int:
    try:
        n = int(value or default)
    except Exception:
        n = default
    if n < 1:
        n = 1
    if n > SAFE_MAX_LIMIT:
        n = SAFE_MAX_LIMIT
    return n


def sort_key(item: Dict[str, Any]) -> Tuple[float, float, str]:
    return (
        float(item.get("score", 0.0)),
        float(item.get("priority", 0.0)),
        str(item.get("created_at", "") or "")
    )


def finalize_group(items: List[Dict[str, Any]], limit: int, key_fn=None) -> List[Dict[str, Any]]:
    items.sort(key=sort_key, reverse=True)
    seen = set()
    out: List[Dict[str, Any]] = []
    for item in items:
        key = ""
        if key_fn:
            try:
                key = str(key_fn(item) or "").strip()
            except Exception:
                key = ""
        if not key:
            key = json.dumps(item, ensure_ascii=False, sort_keys=True)
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
        if len(out) >= limit:
            break
    return out


def scan_dir_files(root: Path, recursive: bool = True, suffixes: Optional[Tuple[str, ...]] = None) -> List[Path]:
    if not root.exists():
        return []

    suffixes = tuple(sorted({str(s).lower() for s in (suffixes or tuple())}))
    use_cache = not recursive

    if use_cache:
        cache_key = f"{root.as_posix()}|{int(recursive)}|{'|'.join(suffixes)}"
        cached = cache_get(PATH_CACHE, cache_key, PATH_CACHE_TTL)
        if cached is not None:
            return [Path(p) for p in cached]

    out: List[str] = []
    stack = [root]

    while stack:
        current = stack.pop()
        try:
            with os.scandir(current) as it:
                for entry in it:
                    try:
                        if entry.is_dir(follow_symlinks=False):
                            if recursive:
                                stack.append(Path(entry.path))
                            continue
                        if not entry.is_file(follow_symlinks=False):
                            continue
                        if suffixes:
                            suffix = Path(entry.name).suffix.lower()
                            if suffix not in suffixes:
                                continue
                        out.append(entry.path)
                    except Exception:
                        continue
        except Exception:
            continue

    if use_cache:
        cache_set(PATH_CACHE, cache_key, out, MAX_PATH_CACHE)
    return [Path(p) for p in out]


def read_text_cached(path: Path) -> str:
    try:
        if not path.is_file():
            return ""
        st = path.stat()
        if st.st_size > MAX_TEXT_FILE_SIZE:
            return ""
        cache_key = f"{path.as_posix()}|{st.st_mtime_ns}|{st.st_size}"
        cached = cache_get(TEXT_CACHE, cache_key, TEXT_CACHE_TTL)
        if cached is not None:
            return cached
        text = path.read_text(encoding="utf-8", errors="ignore")
        cache_set(TEXT_CACHE, cache_key, text, MAX_TEXT_CACHE)
        return text
    except Exception:
        return ""


def build_index_excerpt(content: str, max_chars: int = INDEX_EXCERPT_CHARS) -> str:
    text = re.sub(r"\s+", " ", str(content or "")).strip()
    if not text:
        return ""
    if len(text) <= max_chars:
        return text
    head = text[: min(900, max_chars)]
    middle_start = max(0, (len(text) // 2) - min(220, max_chars // 6))
    middle = text[middle_start: middle_start + min(440, max_chars // 3)]
    tail = text[-min(700, max_chars):]
    joined = f"{head} {middle} {tail}"
    return joined[:max_chars]


def build_snippet(content: str, query: str, query_tokens: List[str]) -> str:
    raw = str(content or "")
    if not raw:
        return ""
    lower = raw.lower()
    q = str(query or "").strip().lower()

    idx = -1
    if q:
        idx = lower.find(q)

    if idx == -1:
        for token in query_tokens:
            idx = lower.find(token.lower())
            if idx != -1:
                break

    if idx == -1:
        return re.sub(r"\s+", " ", raw).strip()[:MAX_SNIPPET]

    start = max(0, idx - 60)
    end = min(len(raw), idx + max(len(q), 12) + 60)
    return re.sub(r"\s+", " ", raw[start:end]).strip()[:MAX_SNIPPET]


def fuzzy_token_hits(query_tokens: List[str], text_tokens: List[str]) -> Tuple[List[str], float]:
    if not query_tokens or not text_tokens:
        return [], 0.0

    candidates = dedupe_keep_order(text_tokens[:MAX_FUZZY_TEXT_TOKENS])
    hits = []
    score_sum = 0.0

    for qt in query_tokens:
        best_ratio = 0.0
        best_token = ""
        for tt in candidates:
            if not tt:
                continue
            if abs(len(tt) - len(qt)) > max(3, len(qt)):
                continue
            ratio = SequenceMatcher(None, qt, tt).ratio()
            if ratio > best_ratio:
                best_ratio = ratio
                best_token = tt
        if best_ratio >= FUZZY_THRESHOLD:
            hits.append(best_token or qt)
            score_sum += best_ratio

    return dedupe_keep_order(hits), score_sum


def score_text_field(
    text: str,
    query_norm: str,
    query_compact: str,
    query_tokens: List[str],
    field: str,
    fuzzy: bool = True,
    allow_fuzzy: bool = True
) -> Dict[str, Any]:
    raw_text = str(text or "")
    text_norm = normalize_text(raw_text)
    if not text_norm:
        return {
            "score": 0.0,
            "match_reason": None,
            "matched_terms": []
        }

    text_compact = text_norm.replace(" ", "")
    field_bonus = {
        "filename": 28.0,
        "path": 18.0,
        "title": 24.0,
        "library_name": 22.0,
        "doc_title": 22.0,
        "content": 8.0,
        "description": 6.0
    }.get(field, 0.0)

    score = 0.0
    reason = None
    matched_terms: List[str] = []

    if query_norm and text_norm == query_norm:
        score = 140.0 + field_bonus
        reason = "exact"
    elif query_compact and text_compact == query_compact:
        score = 138.0 + field_bonus
        reason = "exact"
    elif query_norm and text_norm.startswith(query_norm):
        score = 126.0 + field_bonus
        reason = "prefix"
    elif query_norm and query_norm in text_norm:
        score = 112.0 + field_bonus
        reason = "substring"
    elif query_compact and len(query_compact) >= 2 and query_compact in text_compact:
        score = 108.0 + field_bonus
        reason = "compact"

    token_hits = [t for t in query_tokens if t and t in text_norm]
    token_hits = dedupe_keep_order(token_hits)
    if token_hits:
        coverage = len(token_hits) / max(len(query_tokens), 1)
        token_score = 72.0 + (coverage * 26.0) + field_bonus
        if token_score > score:
            score = token_score
            reason = "all_tokens" if coverage >= 0.999 else "tokens"
        matched_terms.extend(token_hits)

    if fuzzy and allow_fuzzy and score < 100.0 and query_tokens:
        text_tokens = split_tokens(text_norm)
        fuzzy_hits, fuzzy_score_sum = fuzzy_token_hits(query_tokens, text_tokens)
        if fuzzy_hits:
            hit_ratio = len(fuzzy_hits) / max(len(query_tokens), 1)
            fuzzy_score = 58.0 + (hit_ratio * 24.0) + ((fuzzy_score_sum / max(len(query_tokens), 1)) * 10.0) + field_bonus
            if fuzzy_score > score:
                score = fuzzy_score
                reason = "fuzzy"
            matched_terms.extend(fuzzy_hits)

    return {
        "score": round(score, 4),
        "match_reason": reason,
        "matched_terms": dedupe_keep_order(matched_terms)
    }


def pick_better(a: Optional[Dict[str, Any]], b: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not a:
        return b
    if not b:
        return a
    if float(b.get("score", 0.0)) > float(a.get("score", 0.0)):
        return b
    return a


def _is_cjk_char(ch: str) -> bool:
    if not ch:
        return False
    code = ord(ch)
    return (
        0x4E00 <= code <= 0x9FFF
        or 0x3400 <= code <= 0x4DBF
        or 0x20000 <= code <= 0x2A6DF
        or 0x2A700 <= code <= 0x2B73F
        or 0xF900 <= code <= 0xFAFF
    )


def is_cjk_text(value: Any) -> bool:
    s = str(value or "").strip()
    if not s:
        return False
    chars = [ch for ch in s if not ch.isspace()]
    if not chars:
        return False
    return all(_is_cjk_char(ch) for ch in chars)


def query_symbol_ratio(value: Any) -> float:
    s = str(value or "")
    chars = [ch for ch in s if not ch.isspace()]
    if not chars:
        return 0.0

    symbol_count = 0
    for ch in chars:
        if ch.isalnum() or _is_cjk_char(ch):
            continue
        symbol_count += 1

    return round(symbol_count / max(len(chars), 1), 4)


def is_explicit_filename_query(raw_query: Any) -> bool:
    q = str(raw_query or "").strip()
    if not q:
        return False
    lower = q.lower()

    if "/" in q or "\\" in q:
        return True
    if re.search(r"\.[a-z0-9]{1,8}$", lower):
        return True
    if "." in q and len(q) >= 4:
        return True
    if "_" in q or "-" in q:
        return True
    return False


def is_filenameish_query(raw_query: Any, query_tokens: Optional[List[str]] = None, query_compact: str = "") -> bool:
    q = str(raw_query or "").strip()
    compact = str(query_compact or "").strip()
    tokens = list(query_tokens or [])

    if is_explicit_filename_query(q):
        return True
    if not q or not compact:
        return False
    if len(tokens) != 1:
        return False
    if " " in q or "\t" in q or "\n" in q:
        return False
    if len(compact) < 6:
        return False
    if any(ch.isdigit() for ch in q):
        return True

    for marker in ("文件", "文档", "笔记", "短文", "草稿", "说明", "报告", "拓扑"):
        if marker in q:
            return True
    return False


def is_probable_natural_language(raw_query: Any, query_norm: str, query_tokens: List[str]) -> bool:
    raw = str(raw_query or "").strip().lower()
    tokens = [str(t or "").strip().lower() for t in query_tokens if str(t or "").strip()]
    if len(tokens) < LONG_NL_WORDS:
        return False

    ascii_words = [t for t in tokens if re.fullmatch(r"[a-z]+", t)]
    if len(ascii_words) < max(5, int(len(tokens) * 0.6)):
        return False

    starter_hit = bool(tokens and tokens[0] in EN_NL_STARTERS)
    question_mark = "?" in raw
    stop_hits = sum(1 for t in ascii_words if t in EN_STOPWORDS)
    connective_hits = sum(1 for t in ascii_words if t in {"what", "how", "why", "where", "which", "who", "when", "this", "that", "with", "into", "about"})

    if question_mark:
        return True
    if starter_hit and stop_hits >= 2:
        return True
    if stop_hits >= max(3, len(ascii_words) // 3) and connective_hits >= 2:
        return True
    if len(query_norm) >= 40 and stop_hits >= 4:
        return True
    return False


def _score_tokens_for_query(query_tokens_used: List[str], natural_language: bool) -> List[str]:
    tokens = dedupe_keep_order([str(t or "").strip() for t in query_tokens_used if str(t or "").strip()])
    if not natural_language:
        return tokens[:MAX_QUERY_TOKENS]

    filtered = [
        t for t in tokens
        if len(t) >= 3 and t not in EN_STOPWORDS and t not in FTS_QUERY_RESERVED
    ]
    if not filtered:
        filtered = [t for t in tokens if len(t) >= 4]
    if not filtered:
        filtered = tokens
    return dedupe_keep_order(filtered)[:MAX_QUERY_TOKENS]


def analyze_search_query(raw_query: Any) -> Dict[str, Any]:
    raw = str(raw_query or "").strip()
    raw_query_used = raw[:MAX_QUERY_CHARS].strip()
    raw_query_full_norm = normalize_text(raw)
    raw_query_used_norm = normalize_text(raw_query_used)

    query_tokens_raw = split_tokens(raw_query_full_norm)
    query_tokens_used = split_tokens(raw_query_used_norm)
    query_compact_full = compact_text(raw_query_full_norm)
    query_compact_used = compact_text(raw_query_used_norm)

    truncated = len(raw) > len(raw_query_used)
    if len(query_tokens_used) > MAX_QUERY_TOKENS:
        query_tokens_used = query_tokens_used[:MAX_QUERY_TOKENS]

    if len(query_compact_used) > MAX_COMPACT_CHARS:
        query_compact_used = query_compact_used[:MAX_COMPACT_CHARS]

    query_norm_used = raw_query_used_norm
    query_chars_raw = len(raw)
    query_chars_used = len(raw_query_used)
    compact_len_raw = len(query_compact_full)
    compact_len_used = len(query_compact_used)
    token_count_raw = len(query_tokens_raw)
    token_count_used = len(query_tokens_used)

    symbol_ratio = query_symbol_ratio(raw)
    symbol_heavy = symbol_ratio >= SYMBOL_HEAVY_RATIO and compact_len_used <= 16
    path_like = "/" in raw_query_used or "\\" in raw_query_used
    filenameish = is_filenameish_query(raw_query_used, query_tokens_used, query_compact_used)
    natural_language = is_probable_natural_language(raw_query_used, query_norm_used, query_tokens_used)

    score_tokens = _score_tokens_for_query(query_tokens_used, natural_language)
    fts_tokens = [
        t for t in score_tokens
        if len(t) >= 2 and t not in FTS_QUERY_RESERVED
    ]
    fts_tokens = dedupe_keep_order(fts_tokens)[:MAX_FTS_TOKENS]

    oversized = (
        query_chars_raw > MAX_QUERY_CHARS
        or token_count_raw > MAX_QUERY_TOKENS
        or compact_len_raw > MAX_COMPACT_CHARS
    )

    if not raw_query_used:
        query_class = "empty"
    elif not query_norm_used and not query_compact_used:
        query_class = "symbol_heavy"
    elif symbol_heavy and compact_len_used <= 6 and token_count_used <= 1:
        query_class = "symbol_heavy"
    elif filenameish:
        query_class = "filename"
    elif natural_language:
        query_class = "long_nl"
    elif compact_len_used <= 4 and is_cjk_text(query_compact_used):
        query_class = "short_cjk"
    elif compact_len_used <= 2 or (token_count_used <= 1 and compact_len_used <= 2):
        query_class = "short"
    elif token_count_used >= 7 or compact_len_used >= 40:
        query_class = "long_phrase"
    elif token_count_used >= 4 or compact_len_used >= 24:
        query_class = "phrase"
    else:
        query_class = "keyword"

    allow_title_fts = False
    allow_content_fts = False
    allow_direct_content_like = False

    if query_class == "keyword":
        allow_title_fts = bool(query_compact_used) and 3 <= compact_len_used <= 24 and bool(fts_tokens)
        allow_content_fts = bool(query_compact_used) and 4 <= compact_len_used <= 20 and bool(fts_tokens)
        allow_direct_content_like = 4 <= compact_len_used <= 18

    elif query_class == "phrase":
        allow_title_fts = bool(query_compact_used) and 4 <= compact_len_used <= 32 and bool(fts_tokens)
        allow_content_fts = bool(query_compact_used) and 4 <= compact_len_used <= 20 and bool(fts_tokens)
        allow_direct_content_like = 4 <= compact_len_used <= 18

    elif query_class == "short_cjk":
        if compact_len_used <= 1:
            allow_title_fts = False
            allow_content_fts = False
            allow_direct_content_like = False
        elif 2 <= compact_len_used <= 3:
            allow_title_fts = False
            allow_content_fts = False
            allow_direct_content_like = True
        else:
            allow_title_fts = bool(fts_tokens)
            allow_content_fts = bool(fts_tokens) and 4 <= compact_len_used <= 8
            allow_direct_content_like = 2 <= compact_len_used <= 8

    elif query_class == "filename":
        allow_title_fts = False
        allow_content_fts = False
        allow_direct_content_like = 4 <= compact_len_used <= 48

    elif query_class == "long_phrase":
        allow_title_fts = bool(fts_tokens) and 4 <= compact_len_used <= 80
        allow_content_fts = bool(fts_tokens)
        allow_direct_content_like = False

    elif query_class == "long_nl":
        allow_title_fts = bool(fts_tokens)
        allow_content_fts = bool(fts_tokens)
        allow_direct_content_like = False

    elif query_class in {"short", "symbol_heavy", "empty"}:
        allow_title_fts = False
        allow_content_fts = False
        allow_direct_content_like = False

    degrade_reasons: List[str] = []

    if truncated:
        degrade_reasons.append("query_chars_capped")
    if token_count_raw > MAX_QUERY_TOKENS:
        degrade_reasons.append("query_tokens_capped")
    if compact_len_raw > MAX_COMPACT_CHARS:
        degrade_reasons.append("query_compact_capped")
    if query_class == "symbol_heavy":
        degrade_reasons.append("symbol_heavy_guard")
    if query_class == "long_nl":
        degrade_reasons.append("long_nl_limited_fts")
    if query_class == "long_phrase":
        degrade_reasons.append("long_phrase_limited_fts")
    if query_class == "short_cjk" and compact_len_used <= 1:
        degrade_reasons.append("short_cjk_direct_title_only")
        allow_title_fts = False
        allow_content_fts = False
        allow_direct_content_like = False
    if query_class == "short":
        degrade_reasons.append("short_query_direct_title_only")
    if query_class == "filename":
        degrade_reasons.append("filename_query_title_first_then_content_like")
    if truncated or token_count_raw > MAX_QUERY_TOKENS or compact_len_raw > MAX_COMPACT_CHARS:
        allow_content_fts = False
        allow_direct_content_like = False

    if query_class == "empty":
        allow_title_fts = False
        allow_content_fts = False
        allow_direct_content_like = False

    deduped_degrade_reasons = dedupe_keep_order(degrade_reasons)
    degraded = bool(deduped_degrade_reasons)

    return {
        "raw_query": raw,
        "raw_query_used": raw_query_used,
        "query_norm": query_norm_used,
        "query_compact": query_compact_used,
        "query_tokens": list(query_tokens_used),
        "query_tokens_used": list(query_tokens_used),
        "query_tokens_score": list(score_tokens),
        "query_tokens_fts": list(fts_tokens),
        "query_chars_raw": int(query_chars_raw),
        "query_chars_used": int(query_chars_used),
        "compact_len_raw": int(compact_len_raw),
        "compact_len_used": int(compact_len_used),
        "token_count_raw": int(token_count_raw),
        "token_count_used": int(token_count_used),
        "token_count_score": int(len(score_tokens)),
        "token_count_fts": int(len(fts_tokens)),
        "symbol_ratio": float(symbol_ratio),
        "symbol_heavy": bool(symbol_heavy),
        "natural_language": bool(natural_language),
        "filenameish": bool(filenameish),
        "path_like": bool(path_like),
        "oversized": bool(oversized),
        "truncated": bool(truncated),
        "token_capped": bool(token_count_raw > MAX_QUERY_TOKENS),
        "compact_capped": bool(compact_len_raw > MAX_COMPACT_CHARS),
        "query_class": str(query_class),
        "allow_title_fts": bool(allow_title_fts),
        "allow_content_fts": bool(allow_content_fts),
        "allow_direct_content_like": bool(allow_direct_content_like),
        "degraded": bool(degraded),
        "degrade_reasons": list(deduped_degrade_reasons),
        "guard_reason": str(deduped_degrade_reasons[0]) if deduped_degrade_reasons else "",
    }
