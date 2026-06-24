from __future__ import annotations

from typing import Any, Dict

from .room_packet_builder import _normalize_qascope_packet
from .room_request_bridge import _safe_dict, _safe_str


def call_room_rag_qascope_packet(
    *,
    room_id: str,
    request_id: str,
    rag_mode: str,
    mcp_overrides: Dict[str, Any],
    base_args: Dict[str, Any],
    question: str,
    binding: Dict[str, Any],
    model_name: str,
) -> Dict[str, Any]:
    from .room_qascope import _call_qascope_reply, _extract_qascope_result

    rag_question = _safe_str(question)
    qares = _call_qascope_reply(
        base_args=base_args,
        question=rag_question,
        request_id=request_id,
        binding=binding,
        model_name=model_name,
    )

    extracted = _safe_dict(_extract_qascope_result(rag_question, qares))
    content = _safe_str(extracted.get("content") or extracted.get("response"))
    if not content:
        return {}

    extracted["evidence_query"] = rag_question
    evidence_result = _safe_dict(extracted.get("evidence_result"))
    evidence_result["evidence_query"] = rag_question
    extracted["evidence_result"] = evidence_result

    packet = _normalize_qascope_packet(
        room_id=room_id,
        request_id=request_id,
        rag_mode=rag_mode,
        mcp_overrides=mcp_overrides,
        binding=binding,
        question=rag_question,
        extracted=extracted,
    )

    packet["evidence_query"] = rag_question
    packet_evidence_result = _safe_dict(packet.get("evidence_result"))
    packet_evidence_result["evidence_query"] = rag_question
    packet["evidence_result"] = packet_evidence_result
    return packet
