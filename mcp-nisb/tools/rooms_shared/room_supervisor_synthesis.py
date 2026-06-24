from __future__ import annotations

import re
from typing import Any, Dict, List, Tuple

from .room_packet_builder import _empty_evidence_result, _normalize_tool_activity_lists
from .room_role_runtime_request import (
    _collapse_inline_text,
    _safe_dict,
    _safe_list,
    _safe_str,
    _truncate_text,
)


def _split_text_lines(value: Any) -> List[str]:
    text = _safe_str(value).replace("\r", "\n")
    return [line.strip() for line in text.split("\n") if line.strip()]


def _looks_like_metadata_line(line: str) -> bool:
    lowered = _safe_str(line).lower()
    if not lowered:
        return True

    prefixes = (
        "evidence_query:",
        "citations_count:",
        "tool_activity:",
        "tool_calls_count:",
        "tool_results_count:",
        "evidence_tools_count:",
        "引用",
        "参考",
    )
    return lowered.startswith(prefixes)


def _extract_delegate_points(value: Any, limit: int = 3, point_limit: int = 220) -> List[str]:
    lines = _split_text_lines(value)
    points: List[str] = []
    seen = set()

    for raw_line in lines:
        line = raw_line.strip()
        if not line or _looks_like_metadata_line(line):
            continue

        normalized = line.replace("•", "-").strip()
        candidate = ""
        if normalized.startswith("-"):
            candidate = normalized.lstrip("- ").strip()
        elif not points:
            candidate = normalized

        if not candidate:
            continue

        key = _collapse_inline_text(candidate).lower()
        if not key or key in seen:
            continue

        seen.add(key)
        points.append(_truncate_text(candidate, point_limit))
        if len(points) >= max(1, int(limit or 1)):
            break

    if points:
        return points

    merged = _collapse_inline_text(value)
    if not merged:
        return []
    return [_truncate_text(merged, point_limit)]


def _derive_delegate_stance(value: Any) -> str:
    text = _safe_str(value)
    if not text:
        return "empty"

    if any(marker in text for marker in ("但", "然而", "不过", "另一方面", "相对", "冲突", "分歧")):
        return "qualified"
    if any(marker in text for marker in ("强调", "认为", "核心", "本质", "定义", "关注")):
        return "analytic"
    return "descriptive"


def _build_grounded_delegate_row(
    *,
    row: Dict[str, Any],
    question: str,
    source_excerpt_limit: int = 900,
) -> Dict[str, Any]:
    src = _safe_dict(row)
    content = _safe_str(src.get("content"))
    primary_points = _extract_delegate_points(content, limit=3, point_limit=220)
    source_excerpt = _truncate_text(content, source_excerpt_limit)

    return {
        **src,
        "role_id": _safe_str(src.get("role_id")),
        "role_name": _safe_str(src.get("role_name"), "Role"),
        "content": content,
        "primary_points": primary_points,
        "point_count": len(primary_points),
        "source_excerpt": source_excerpt,
        "stance": _derive_delegate_stance(content),
        "evidence_query": _safe_str(src.get("evidence_query"), question) or question,
        "citations": _safe_list(src.get("citations")),
        "rss_evidence": _safe_list(src.get("rss_evidence")),
        "market_evidence": _safe_list(src.get("market_evidence")),
        "evidence_tools": _safe_list(src.get("evidence_tools")),
        "evidence_result": src.get("evidence_result") or _empty_evidence_result(question),
        "tool_calls": _safe_list(src.get("tool_calls")),
        "tool_results": _safe_list(src.get("tool_results")),
    }


def _build_delegate_summary_tool_result(
    *,
    question: str,
    plan_summary: str,
    delegate_packets: List[Dict[str, Any]],
    delegate_events: List[Dict[str, Any]],
    role_message_events: List[Dict[str, Any]],
) -> Dict[str, Any]:
    items: List[Dict[str, Any]] = []
    for idx, item in enumerate(delegate_packets, start=1):
        grounded_row = _build_grounded_delegate_row(row=item, question=question)
        items.append(
            {
                "index": idx,
                "role_id": _safe_str(grounded_row.get("role_id")),
                "role_name": _safe_str(grounded_row.get("role_name")),
                "content": _safe_str(grounded_row.get("content")),
                "summary": _truncate_text(grounded_row.get("content"), 320),
                "primary_points": _safe_list(grounded_row.get("primary_points")),
                "point_count": int(grounded_row.get("point_count") or 0),
                "source_excerpt": _safe_str(grounded_row.get("source_excerpt")),
                "stance": _safe_str(grounded_row.get("stance")),
                "citations": _safe_list(grounded_row.get("citations")),
                "rss_evidence": _safe_list(grounded_row.get("rss_evidence")),
                "market_evidence": _safe_list(grounded_row.get("market_evidence")),
                "evidence_query": _safe_str(grounded_row.get("evidence_query"), question) or question,
                "evidence_tools": _safe_list(grounded_row.get("evidence_tools")),
                "evidence_result": grounded_row.get("evidence_result") or _empty_evidence_result(question),
                "tool_calls": _safe_list(grounded_row.get("tool_calls")),
                "tool_results": _safe_list(grounded_row.get("tool_results")),
            }
        )

    return {
        "type": "room_delegate_summary",
        "question": question,
        "plan_summary": plan_summary,
        "delegate_count": len(delegate_packets),
        "delegate_event_ids": [_safe_str(evt.get("id")) for evt in delegate_events],
        "role_message_event_ids": [_safe_str(evt.get("id")) for evt in role_message_events],
        "items": items,
    }


def _prepare_fs_context_for_synthesis(
    fs_context: Dict[str, Any],
    *,
    text_limit: int = 3600,
) -> Tuple[Dict[str, Any], int, int]:
    src = _safe_dict(fs_context)
    full_text = _safe_str(src.get("text"))
    prompt_text = _truncate_text(full_text, text_limit)
    prepared = {
        **src,
        "text": prompt_text,
    }
    return prepared, len(full_text), len(prompt_text)


def _prepare_delegate_packets_for_synthesis(
    delegate_packets: List[Dict[str, Any]],
    *,
    question: str,
    per_role_limit: int = 1800,
) -> Tuple[List[Dict[str, Any]], int]:
    prepared: List[Dict[str, Any]] = []
    non_empty = 0

    for item in delegate_packets:
        grounded = _build_grounded_delegate_row(
            row=_safe_dict(item),
            question=question,
            source_excerpt_limit=min(per_role_limit, 900),
        )
        content = _truncate_text(_safe_str(grounded.get("content")), per_role_limit)
        if content:
            non_empty += 1

        prepared.append(
            {
                **grounded,
                "content": content,
            }
        )

    return prepared, non_empty


def _looks_like_delegate_dump(text: str) -> bool:
    body = _safe_str(text)
    if not body:
        return False

    lowered = body.lower()
    markers = [
        "下面是完整的复述各worker的回答内容",
        "下面是完整复述各worker的回答内容",
        "完整的复述各worker的回答内容",
        "下面是完整的复述各 worker 的回答内容",
        "下面是完整复述各 worker 的回答内容",
        "各角色结论：",
        "各角色结论:",
        "worker回答内容",
        "worker 的回答内容",
        "完整复述",
        "角色结果摘要",
    ]

    if any(marker in body for marker in markers):
        return True

    if "worker" in lowered and "复述" in body:
        return True

    if body.count("## ") >= 3:
        return True

    return False


def _looks_like_process_report(text: str) -> bool:
    body = _safe_str(text)
    if not body:
        return False

    lowered = body.lower()
    markers = [
        "我已完成本轮 supervisor 综合",
        "我已完成本轮 supervisor 编排",
        "我已完成本轮 Supervisor 综合",
        "我已完成本轮 Supervisor 编排",
        "综合回答：",
        "综合回答:",
        "支撑判断的关键要点",
        "计划摘要",
        "角色结果摘要",
        "各角色结论",
    ]

    if any(marker in body for marker in markers):
        return True

    if "supervisor" in lowered and "计划" in body and "角色" in body:
        return True

    return False


def _ungrounded_tail_markers() -> List[str]:
    return [
        "注：由于您提供的文件内容未显示具体文字",
        "由于您提供的文件内容未显示具体文字",
        "如果文件中有具体论述，请告诉我",
        "如果你提供文件内容",
        "我可以更精确地引用",
        "我可以更准确地引用",
        "如果提供具体文本",
        "若有原文",
    ]


def _looks_like_ungrounded_tail_disclaimer(text: str) -> bool:
    lines = _split_text_lines(text)
    if not lines:
        return False

    markers = _ungrounded_tail_markers()
    tail_lines = lines[-2:] if len(lines) >= 2 else lines

    for line in tail_lines:
        if any(marker in line for marker in markers):
            return True
    return False


def _strip_trailing_ungrounded_disclaimer(text: str) -> str:
    lines = _split_text_lines(text)
    if not lines:
        return ""

    markers = _ungrounded_tail_markers()
    trimmed = list(lines)

    while trimmed:
        tail = trimmed[-1]
        if any(marker in tail for marker in markers):
            trimmed.pop()
            continue
        break

    return "\n".join(trimmed).strip() or _safe_str(text).strip()


def _needs_supervisor_repair(text: str) -> bool:
    body = _safe_str(text)
    if not body:
        return True
    if _looks_like_delegate_dump(body):
        return True
    if _looks_like_process_report(body):
        return True
    return False


def _build_supervisor_synthesis_fallback(
    *,
    question: str,
    rows: List[Dict[str, Any]],
) -> str:
    grounded_rows = [
        _build_grounded_delegate_row(row=_safe_dict(x), question=question)
        for x in _safe_list(rows)
        if _safe_str(_safe_dict(x).get("content"))
    ]

    short_points: List[str] = []
    seen = set()

    for item in grounded_rows:
        for point in _safe_list(item.get("primary_points")):
            point_text = _safe_str(point)
            key = _collapse_inline_text(point_text).lower()
            if not point_text or not key or key in seen:
                continue
            seen.add(key)
            short_points.append(point_text)
            if len(short_points) >= 2:
                break
        if len(short_points) >= 2:
            break

    if short_points:
        return (
            f"围绕“{question}”，当前已有一些相对稳定的判断。"
            f"较稳妥地说，{short_points[0]}"
            + (f"；同时，{short_points[1]}" if len(short_points) > 1 else "")
            + "。现阶段更适合先保留这一层级的综合结论，而不再做过度展开。"
        )

    return (
        f"围绕“{question}”，当前已经拿到部分角色材料，但还不足以形成一份高质量、细展开的统一综合。"
        "更稳妥的做法，是回到相关文本和上下文后再继续收紧判断。"
    )


def _merge_tool_activity_groups(
    *groups: Tuple[Any, Any],
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    merged_tool_calls: List[Dict[str, Any]] = []
    merged_tool_results: List[Dict[str, Any]] = []

    for tool_calls, tool_results in groups:
        norm_calls, norm_results = _normalize_tool_activity_lists(tool_calls, tool_results)
        merged_tool_calls.extend(norm_calls)
        merged_tool_results.extend(norm_results)

    return merged_tool_calls, merged_tool_results


def _looks_like_heading_line(text: str) -> bool:
    value = _safe_str(text)
    if not value:
        return False

    if value.startswith("#"):
        return True
    if len(value) <= 28 and value.endswith("："):
        return True
    if re.match(r"^[一二三四五六七八九十]+[、\.]", value):
        return True
    if re.match(r"^\d+[、\.]", value) and len(value) <= 28:
        return True
    return False


def _split_natural_sentences(value: Any, limit: int = 48) -> List[str]:
    text = _safe_str(value).replace("\r", "\n")
    if not text:
        return []

    rows: List[str] = []

    for raw_line in text.split("\n"):
        line = raw_line.strip()
        if not line:
            continue

        if _looks_like_heading_line(line):
            rows.append(line)
            if len(rows) >= limit:
                return rows[:limit]
            continue

        current = ""
        for ch in line:
            current += ch
            if ch in "。！？；!?;":
                piece = current.strip()
                if piece:
                    rows.append(piece)
                current = ""
                if len(rows) >= limit:
                    return rows[:limit]

        tail = current.strip()
        if tail:
            rows.append(tail)
            if len(rows) >= limit:
                return rows[:limit]

    return rows[:limit]


def _normalize_match_text(value: Any) -> str:
    text = _collapse_inline_text(value).lower()
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _tokenize_match_text(value: Any) -> List[str]:
    text = _normalize_match_text(value)
    if not text:
        return []

    tokens = set()

    for token in re.findall(r"[a-z0-9_]+", text):
        if len(token) >= 2:
            tokens.add(token)

    for token in re.findall(r"[\u4e00-\u9fff]{2,12}", text):
        tokens.add(token)

    chinese = "".join(re.findall(r"[\u4e00-\u9fff]", text))
    for n in (2, 3):
        if len(chinese) >= n:
            for idx in range(len(chinese) - n + 1):
                tokens.add(chinese[idx: idx + n])

    compact = re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "", text)
    if 2 <= len(compact) <= 24:
        tokens.add(compact)

    return list(tokens)


def _is_generic_match_candidate(text: str) -> bool:
    value = _safe_str(text)
    if not value:
        return True
    if len(value) <= 4:
        return True
    blocked = (
        "引用",
        "要点",
        "关键点",
        "总结",
        "结论",
        "分析",
        "用户问题",
    )
    return value in blocked


def _score_sentence_match(sentence: str, candidate: str) -> float:
    sentence_norm = _normalize_match_text(sentence)
    candidate_norm = _normalize_match_text(candidate)
    if not sentence_norm or not candidate_norm:
        return 0.0

    sentence_tokens = set(_tokenize_match_text(sentence_norm))
    candidate_tokens = set(_tokenize_match_text(candidate_norm))

    substring_bonus = 0.0
    if candidate_norm in sentence_norm or sentence_norm in candidate_norm:
        substring_bonus = 0.22

    if not sentence_tokens or not candidate_tokens:
        return min(1.0, substring_bonus)

    overlap = len(sentence_tokens & candidate_tokens)
    if overlap <= 0:
        return min(1.0, substring_bonus)

    precision = overlap / max(len(sentence_tokens), 1)
    recall = overlap / max(len(candidate_tokens), 1)
    score = precision * 0.68 + recall * 0.32 + substring_bonus

    if _collapse_inline_text(sentence) == _collapse_inline_text(candidate):
        score += 0.12

    return min(1.0, score)


def _build_role_attribution_sources(
    *,
    delegate_packets: List[Dict[str, Any]],
    question: str,
) -> List[Dict[str, Any]]:
    role_sources: List[Dict[str, Any]] = []

    for item in _safe_list(delegate_packets):
        grounded = _build_grounded_delegate_row(row=_safe_dict(item), question=question)
        role_id = _safe_str(grounded.get("role_id"))
        role_name = _safe_str(grounded.get("role_name"), "role")

        candidates: List[Dict[str, Any]] = []
        seen = set()

        for point in _safe_list(grounded.get("primary_points"))[:4]:
            point_text = _safe_str(point)
            key = _normalize_match_text(point_text)
            if not point_text or not key or key in seen or _is_generic_match_candidate(point_text):
                continue
            seen.add(key)
            candidates.append(
                {
                    "kind": "primary_point",
                    "text": point_text,
                    "excerpt": _truncate_text(point_text, 220),
                }
            )

        for sentence in _split_natural_sentences(grounded.get("content"), limit=10):
            key = _normalize_match_text(sentence)
            if not sentence or not key or key in seen or _is_generic_match_candidate(sentence):
                continue
            seen.add(key)
            candidates.append(
                {
                    "kind": "content_sentence",
                    "text": sentence,
                    "excerpt": _truncate_text(sentence, 220),
                }
            )

        source_excerpt = _safe_str(grounded.get("source_excerpt"))
        if source_excerpt:
            for sentence in _split_natural_sentences(source_excerpt, limit=6):
                key = _normalize_match_text(sentence)
                if not sentence or not key or key in seen or _is_generic_match_candidate(sentence):
                    continue
                seen.add(key)
                candidates.append(
                    {
                        "kind": "source_excerpt",
                        "text": sentence,
                        "excerpt": _truncate_text(sentence, 220),
                    }
                )

        role_sources.append(
            {
                "role_id": role_id,
                "role_name": role_name,
                "candidates": candidates[:12],
            }
        )

    return role_sources


def _match_sentence_to_role_sources(
    *,
    sentence: str,
    role_sources: List[Dict[str, Any]],
    top_k: int = 2,
) -> List[Dict[str, Any]]:
    sentence_text = _safe_str(sentence)
    if not sentence_text or _looks_like_heading_line(sentence_text):
        return []

    per_role_best: List[Dict[str, Any]] = []

    for role_row in role_sources:
        best_match: Dict[str, Any] = {}
        best_score = 0.0

        for idx, candidate in enumerate(_safe_list(role_row.get("candidates"))):
            candidate_row = _safe_dict(candidate)
            candidate_text = _safe_str(candidate_row.get("text"))
            score = _score_sentence_match(sentence_text, candidate_text)
            if score > best_score:
                best_score = score
                best_match = {
                    "role_id": _safe_str(role_row.get("role_id")),
                    "role_name": _safe_str(role_row.get("role_name")),
                    "score": round(score, 4),
                    "source_kind": _safe_str(candidate_row.get("kind")),
                    "source_index": idx + 1,
                    "matched_excerpt": _safe_str(candidate_row.get("excerpt")),
                }

        if best_match and best_score >= 0.18:
            per_role_best.append(best_match)

    per_role_best = sorted(per_role_best, key=lambda x: float(x.get("score") or 0.0), reverse=True)

    if not per_role_best:
        return []

    top_sources = per_role_best[: max(int(top_k or 1), 1)]
    if len(top_sources) >= 2:
        first_score = float(top_sources[0].get("score") or 0.0)
        top_sources = [
            row
            for row in top_sources
            if float(row.get("score") or 0.0) >= max(0.18, first_score - 0.16)
        ]

    return top_sources[: max(int(top_k or 1), 1)]


def _build_supervisor_attribution_tool_result(
    *,
    question: str,
    final_text: str,
    delegate_packets: List[Dict[str, Any]],
) -> Dict[str, Any]:
    sentences = _split_natural_sentences(final_text, limit=64)
    role_sources = _build_role_attribution_sources(
        delegate_packets=delegate_packets,
        question=question,
    )

    sentence_rows: List[Dict[str, Any]] = []
    role_summary_map: Dict[str, Dict[str, Any]] = {}
    attributable_sentence_count = 0
    attributed_sentence_count = 0

    for idx, sentence in enumerate(sentences, start=1):
        is_heading = _looks_like_heading_line(sentence)
        top_sources = _match_sentence_to_role_sources(
            sentence=sentence,
            role_sources=role_sources,
            top_k=2,
        )

        if not is_heading:
            attributable_sentence_count += 1
            if top_sources:
                attributed_sentence_count += 1

        sentence_rows.append(
            {
                "index": idx,
                "kind": "heading" if is_heading else "body",
                "text": sentence,
                "attributed": bool(top_sources),
                "top_sources": top_sources,
            }
        )

        for source in top_sources:
            role_key = _safe_str(source.get("role_id")) or _safe_str(source.get("role_name"))
            existing = role_summary_map.setdefault(
                role_key,
                {
                    "role_id": _safe_str(source.get("role_id")),
                    "role_name": _safe_str(source.get("role_name")),
                    "matched_sentence_count": 0,
                    "max_score": 0.0,
                    "sentence_indices": [],
                    "sample_supports": [],
                },
            )
            existing["matched_sentence_count"] = int(existing.get("matched_sentence_count") or 0) + 1
            existing["max_score"] = max(float(existing.get("max_score") or 0.0), float(source.get("score") or 0.0))
            existing["sentence_indices"] = list(existing.get("sentence_indices") or []) + [idx]

            sample_supports = list(existing.get("sample_supports") or [])
            if len(sample_supports) < 3:
                sample_supports.append(
                    {
                        "sentence_index": idx,
                        "sentence_text": _truncate_text(sentence, 180),
                        "matched_excerpt": _safe_str(source.get("matched_excerpt")),
                        "score": float(source.get("score") or 0.0),
                    }
                )
            existing["sample_supports"] = sample_supports

    role_summaries = sorted(
        [
            {
                **row,
                "max_score": round(float(row.get("max_score") or 0.0), 4),
                "sentence_indices": list(dict.fromkeys(_safe_list(row.get("sentence_indices")))),
            }
            for row in role_summary_map.values()
        ],
        key=lambda x: (
            int(x.get("matched_sentence_count") or 0),
            float(x.get("max_score") or 0.0),
        ),
        reverse=True,
    )

    unattributed_sentence_count = max(attributable_sentence_count - attributed_sentence_count, 0)
    summary = {
        "sentence_count": len(sentences),
        "attributable_sentence_count": attributable_sentence_count,
        "attributed_sentence_count": attributed_sentence_count,
        "unattributed_sentence_count": unattributed_sentence_count,
        "role_count": len(role_summaries),
        "top_roles": [
            {
                "role_id": _safe_str(item.get("role_id")),
                "role_name": _safe_str(item.get("role_name")),
                "matched_sentence_count": int(item.get("matched_sentence_count") or 0),
                "max_score": float(item.get("max_score") or 0.0),
            }
            for item in role_summaries[:5]
        ],
    }

    return {
        "type": "room_supervisor_attribution",
        "question": question,
        "summary": summary,
        "roles": role_summaries,
        "sentences": sentence_rows,
    }


def _candidate_priority(kind: str) -> float:
    if kind == "primary_point":
        return 0.18
    if kind == "content_sentence":
        return 0.08
    if kind == "source_excerpt":
        return 0.05
    return 0.0


def _build_role_novelty_candidates(
    *,
    grounded: Dict[str, Any],
) -> List[Dict[str, Any]]:
    candidates: List[Dict[str, Any]] = []
    seen = set()

    for point in _safe_list(grounded.get("primary_points"))[:4]:
        point_text = _safe_str(point)
        key = _normalize_match_text(point_text)
        if not point_text or not key or key in seen or _is_generic_match_candidate(point_text):
            continue
        seen.add(key)
        candidates.append(
            {
                "kind": "primary_point",
                "text": point_text,
                "excerpt": _truncate_text(point_text, 220),
            }
        )

    for sentence in _split_natural_sentences(grounded.get("content"), limit=8):
        key = _normalize_match_text(sentence)
        if not sentence or not key or key in seen or _is_generic_match_candidate(sentence):
            continue
        seen.add(key)
        candidates.append(
            {
                "kind": "content_sentence",
                "text": sentence,
                "excerpt": _truncate_text(sentence, 220),
            }
        )

    for sentence in _split_natural_sentences(grounded.get("source_excerpt"), limit=5):
        key = _normalize_match_text(sentence)
        if not sentence or not key or key in seen or _is_generic_match_candidate(sentence):
            continue
        seen.add(key)
        candidates.append(
            {
                "kind": "source_excerpt",
                "text": sentence,
                "excerpt": _truncate_text(sentence, 220),
            }
        )

    return candidates[:12]


def _build_delegate_novelty_guard(
    *,
    question: str,
    delegate_packets: List[Dict[str, Any]],
    max_targets_per_role: int = 2,
) -> Dict[str, Any]:
    grounded_rows = [
        _build_grounded_delegate_row(row=_safe_dict(item), question=question)
        for item in _safe_list(delegate_packets)
        if _safe_str(_safe_dict(item).get("content"))
    ]

    role_rows: List[Dict[str, Any]] = []
    for grounded in grounded_rows:
        role_rows.append(
            {
                "role_id": _safe_str(grounded.get("role_id")),
                "role_name": _safe_str(grounded.get("role_name"), "role"),
                "candidates": _build_role_novelty_candidates(grounded=grounded),
            }
        )

    all_candidates: List[Dict[str, Any]] = []
    for role_row in role_rows:
        for candidate in _safe_list(role_row.get("candidates")):
            all_candidates.append(
                {
                    "role_id": _safe_str(role_row.get("role_id")),
                    "role_name": _safe_str(role_row.get("role_name")),
                    "kind": _safe_str(_safe_dict(candidate).get("kind")),
                    "text": _safe_str(_safe_dict(candidate).get("text")),
                    "excerpt": _safe_str(_safe_dict(candidate).get("excerpt")),
                }
            )

    targets: List[Dict[str, Any]] = []
    targets_by_role: List[Dict[str, Any]] = []

    for role_row in role_rows:
        ranked: List[Dict[str, Any]] = []
        role_id = _safe_str(role_row.get("role_id"))
        role_name = _safe_str(role_row.get("role_name"), "role")

        for candidate in _safe_list(role_row.get("candidates")):
            candidate_row = _safe_dict(candidate)
            candidate_text = _safe_str(candidate_row.get("text"))
            if not candidate_text:
                continue

            max_other_similarity = 0.0
            closest_other: Dict[str, Any] = {}

            for other in all_candidates:
                if _safe_str(other.get("role_id")) == role_id:
                    continue
                sim = _score_sentence_match(candidate_text, _safe_str(other.get("text")))
                if sim > max_other_similarity:
                    max_other_similarity = sim
                    closest_other = other

            novelty_score = max(0.0, 1.0 - max_other_similarity) + _candidate_priority(
                _safe_str(candidate_row.get("kind"))
            )

            ranked.append(
                {
                    "role_id": role_id,
                    "role_name": role_name,
                    "kind": _safe_str(candidate_row.get("kind")),
                    "text": candidate_text,
                    "excerpt": _safe_str(candidate_row.get("excerpt")),
                    "novelty_score": round(min(1.5, novelty_score), 4),
                    "overlap_score": round(max_other_similarity, 4),
                    "closest_role_id": _safe_str(closest_other.get("role_id")),
                    "closest_role_name": _safe_str(closest_other.get("role_name")),
                    "closest_excerpt": _safe_str(closest_other.get("excerpt")),
                }
            )

        ranked = sorted(
            ranked,
            key=lambda item: (
                float(item.get("novelty_score") or 0.0),
                -float(item.get("overlap_score") or 0.0),
                len(_safe_str(item.get("text"))),
            ),
            reverse=True,
        )

        selected = ranked[: max(1, int(max_targets_per_role or 1))]
        targets.extend(selected)
        targets_by_role.append(
            {
                "role_id": role_id,
                "role_name": role_name,
                "target_count": len(selected),
                "targets": selected,
            }
        )

    roles_with_targets = sum(1 for row in targets_by_role if int(row.get("target_count") or 0) > 0)

    return {
        "type": "room_supervisor_novelty_guard",
        "question": question,
        "summary": {
            "role_count": len(role_rows),
            "roles_with_targets": roles_with_targets,
            "target_count": len(targets),
            "max_targets_per_role": max(1, int(max_targets_per_role or 1)),
        },
        "roles": targets_by_role,
        "targets_by_role": targets_by_role,
        "targets": targets,
    }


def _evaluate_supervisor_novelty_coverage(
    *,
    final_text: str,
    novelty_guard: Dict[str, Any],
) -> Dict[str, Any]:
    guard = _safe_dict(novelty_guard)
    targets = _safe_list(guard.get("targets"))
    sentences = _split_natural_sentences(final_text, limit=64)

    target_rows: List[Dict[str, Any]] = []
    matched_sentence_indices = set()
    covered_role_ids = set()

    for idx, target in enumerate(targets, start=1):
        target_row = _safe_dict(target)
        target_text = _safe_str(target_row.get("text"))
        best_sentence = ""
        best_sentence_index = 0
        best_score = 0.0

        for sent_idx, sentence in enumerate(sentences, start=1):
            if _looks_like_heading_line(sentence):
                continue
            score = _score_sentence_match(sentence, target_text)
            if score > best_score:
                best_score = score
                best_sentence = sentence
                best_sentence_index = sent_idx

        matched = best_score >= 0.18
        if matched:
            matched_sentence_indices.add(best_sentence_index)
            covered_role_ids.add(_safe_str(target_row.get("role_id")))

        target_rows.append(
            {
                "index": idx,
                "role_id": _safe_str(target_row.get("role_id")),
                "role_name": _safe_str(target_row.get("role_name")),
                "kind": _safe_str(target_row.get("kind")),
                "target_text": target_text,
                "target_excerpt": _safe_str(target_row.get("excerpt")),
                "matched": matched,
                "matched_sentence_index": best_sentence_index,
                "matched_sentence_text": _truncate_text(best_sentence, 220),
                "score": round(best_score, 4),
            }
        )

    sentence_rows: List[Dict[str, Any]] = []
    for sent_idx, sentence in enumerate(sentences, start=1):
        matched_targets = [
            {
                "index": int(row.get("index") or 0),
                "role_id": _safe_str(row.get("role_id")),
                "role_name": _safe_str(row.get("role_name")),
                "score": float(row.get("score") or 0.0),
            }
            for row in target_rows
            if bool(row.get("matched")) and int(row.get("matched_sentence_index") or 0) == sent_idx
        ]
        sentence_rows.append(
            {
                "index": sent_idx,
                "kind": "heading" if _looks_like_heading_line(sentence) else "body",
                "text": sentence,
                "matched_target_count": len(matched_targets),
                "matched_targets": matched_targets,
            }
        )

    matched_target_count = sum(1 for row in target_rows if bool(row.get("matched")))
    summary = {
        "sentence_count": len(sentences),
        "target_count": len(targets),
        "matched_target_count": matched_target_count,
        "covered_role_count": len(covered_role_ids),
        "matched_sentence_count": len(matched_sentence_indices),
    }

    return {
        "type": "room_supervisor_novelty_coverage",
        "summary": summary,
        "targets": target_rows,
        "sentences": sentence_rows,
    }


def _needs_supervisor_novelty_repair(
    *,
    novelty_guard: Dict[str, Any],
    coverage: Dict[str, Any],
) -> bool:
    novelty_summary = _safe_dict(novelty_guard.get("summary"))
    coverage_summary = _safe_dict(coverage.get("summary"))

    available_roles = int(novelty_summary.get("roles_with_targets") or novelty_summary.get("role_count") or 0)
    available_targets = int(novelty_summary.get("target_count") or 0)

    if available_roles <= 0 or available_targets <= 0:
        return False

    required_roles = 2 if available_roles >= 2 else 1
    required_targets = 2 if available_targets >= 2 else 1

    covered_roles = int(coverage_summary.get("covered_role_count") or 0)
    matched_targets = int(coverage_summary.get("matched_target_count") or 0)

    return covered_roles < required_roles or matched_targets < required_targets


def _candidate_quality_tuple(
    *,
    text: str,
    novelty_coverage: Dict[str, Any],
) -> Tuple[int, int, int, int, int]:
    novelty_summary = _safe_dict(novelty_coverage.get("summary"))
    good_structure = 0 if _needs_supervisor_repair(text) else 1
    covered_roles = int(novelty_summary.get("covered_role_count") or 0)
    matched_targets = int(novelty_summary.get("matched_target_count") or 0)
    matched_sentences = int(novelty_summary.get("matched_sentence_count") or 0)
    length_score = len(_safe_str(text))
    return (
        good_structure,
        covered_roles,
        matched_targets,
        matched_sentences,
        length_score,
    )


def _select_best_supervisor_candidate(
    *,
    initial_packet: Dict[str, Any],
    initial_text: str,
    initial_novelty_coverage: Dict[str, Any],
    repair_packet: Dict[str, Any],
    repair_text: str,
    repair_novelty_coverage: Dict[str, Any],
) -> Tuple[Dict[str, Any], str, Dict[str, Any], str]:
    initial_key = _candidate_quality_tuple(
        text=initial_text,
        novelty_coverage=initial_novelty_coverage,
    )
    repair_key = _candidate_quality_tuple(
        text=repair_text,
        novelty_coverage=repair_novelty_coverage,
    )

    if repair_key > initial_key:
        return repair_packet, repair_text, repair_novelty_coverage, "repair"
    return initial_packet, initial_text, initial_novelty_coverage, "initial"


__all__ = [
    "_build_delegate_summary_tool_result",
    "_prepare_fs_context_for_synthesis",
    "_prepare_delegate_packets_for_synthesis",
    "_needs_supervisor_repair",
    "_looks_like_ungrounded_tail_disclaimer",
    "_strip_trailing_ungrounded_disclaimer",
    "_build_supervisor_synthesis_fallback",
    "_merge_tool_activity_groups",
    "_build_supervisor_attribution_tool_result",
    "_build_delegate_novelty_guard",
    "_evaluate_supervisor_novelty_coverage",
    "_needs_supervisor_novelty_repair",
    "_select_best_supervisor_candidate",
]
