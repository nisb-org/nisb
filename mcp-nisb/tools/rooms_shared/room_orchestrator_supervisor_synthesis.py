from __future__ import annotations

from typing import Any, Callable, Dict, List, Tuple

from .room_result_envelope import _formal_envelope
from .room_role_runtime_request import (
    _call_room_ai_reply_packet,
    _normalize_reply_packet,
    _safe_dict,
    _safe_list,
    _safe_str,
)
from .room_supervisor_prompt_builders import (
    _build_supervisor_repair_prompt,
    _build_supervisor_synthesis_prompt,
)
from .room_supervisor_runtime import _patch_supervisor_runtime_state
from .room_supervisor_skills import append_supervisor_skills_prompt_block
from .room_supervisor_synthesis import (
    _build_delegate_novelty_guard,
    _build_supervisor_attribution_tool_result,
    _build_supervisor_synthesis_fallback,
    _evaluate_supervisor_novelty_coverage,
    _needs_supervisor_novelty_repair,
    _needs_supervisor_repair,
    _prepare_delegate_packets_for_synthesis,
    _prepare_fs_context_for_synthesis,
    _select_best_supervisor_candidate,
    _strip_trailing_ungrounded_disclaimer,
)


def _apply_budget_to_request_args(
    request_args: Dict[str, Any],
    step_budget: Dict[str, Any],
) -> None:
    request_args["supervisor_step_budget_used"] = step_budget["step_budget_used"]
    request_args["supervisor_step_budget_remaining"] = step_budget["step_budget_remaining"]
    request_args["supervisor_budget_status"] = step_budget["budget_status"]
    request_args["supervisor_budget_exhausted"] = step_budget["budget_exhausted"]


def _normalize_supervisor_synthesis_packet(
    *,
    packet: Dict[str, Any],
    rid: str,
    room_id: str,
    question: str,
    mode_used: str,
    response_text: str,
    default_message: str = "supervisor synthesis completed",
) -> Dict[str, Any]:
    raw = _safe_dict(packet)
    safe_response_text = _safe_str(response_text) or _safe_str(
        raw.get("final_response") or raw.get("response") or raw.get("content")
    )

    effective_status = _safe_str(raw.get("status"), "success")
    effective_result_state = _safe_str(raw.get("result_state"))

    if safe_response_text:
        if not effective_result_state or effective_result_state == "error":
            effective_result_state = "success"
        if _safe_str(effective_status).lower() == "error":
            effective_status = "success"

    normalized = _formal_envelope(
        request_id=rid,
        conv_id=room_id,
        rag_mode=_safe_str(raw.get("rag_mode")),
        mcp_overrides=_safe_dict(raw.get("mcp_overrides")),
        mode_used=_safe_str(raw.get("mode_used"), mode_used),
        rss_evidence=_safe_list(raw.get("rss_evidence")),
        market_evidence=_safe_list(raw.get("market_evidence")),
        evidence_query=_safe_str(raw.get("evidence_query"), question),
        evidence_tools=_safe_list(raw.get("evidence_tools")),
        evidence_result=_safe_dict(raw.get("evidence_result")),
        qa_id=_safe_str(raw.get("qa_id")),
        group_id=_safe_str(raw.get("group_id")),
        citations=_safe_list(raw.get("citations")),
        response=safe_response_text,
        status=effective_status,
        result_state=effective_result_state,
        summary="",
        final_response=safe_response_text,
        error_code=_safe_str(raw.get("error_code")),
        result_view=_safe_str(raw.get("result_view"), "full_result"),
        visibility_source=_safe_str(raw.get("visibility_source")),
        source_observation_allowed=bool(raw.get("source_observation_allowed")),
        replay_recoverable=bool(raw.get("replay_recoverable")),
        remote_execution_may_have_completed=bool(raw.get("remote_execution_may_have_completed")),
        provider_trace=_safe_dict(raw.get("provider_trace")),
        grant_trace=_safe_dict(raw.get("grant_trace")),
        network_trace=_safe_dict(raw.get("network_trace")),
        consume_trace=_safe_dict(raw.get("consume_trace")),
        message=_safe_str(raw.get("message"), default_message),
        tool_calls=_safe_list(raw.get("tool_calls")),
        tool_results=_safe_list(raw.get("tool_results")),
        runtime_control_snapshot=_safe_dict(raw.get("runtime_control_snapshot")),
    )
    normalized["content"] = _safe_str(
        normalized.get("final_response") or normalized.get("response") or safe_response_text
    )
    return normalized


def _run_supervisor_synthesis_stage(
    *,
    room_id: str,
    question: str,
    model_name: str,
    mode_used: str,
    run_id: str,
    rid: str,
    plan_evt: Dict[str, Any],
    total: int,
    fs_context: Dict[str, Any],
    notebook_read_info: Dict[str, Any],
    memory_read_info: Dict[str, Any],
    memory_resume_info: Dict[str, Any],
    supervisor_request_args: Dict[str, Any],
    delegate_events: List[Dict[str, Any]],
    delegate_packets: List[Dict[str, Any]],
    plan_summary: str,
    step_budget: Dict[str, Any],
    supervisor_skill_strategy: str,
    supervisor_skills_info: Dict[str, Any],
    supervisor_skills_payload: Dict[str, Any],
    supervisor_notebook_read_payload: Dict[str, Any],
    supervisor_memory_read_payload: Dict[str, Any],
    supervisor_memory_resume_payload: Dict[str, Any],
    consume_step_budget_fn: Callable[[Dict[str, Any], int], Dict[str, Any]],
    budget_patch_fn: Callable[[Dict[str, Any]], Dict[str, Any]],
    interrupt_supervisor_run_fn: Callable[..., Tuple[Dict[str, Any], List[Dict[str, Any]], Dict[str, Any]]],
    append_room_event_fn: Callable[[str, Dict[str, Any]], Any],
    touch_room_updated_at_fn: Callable[[str], Any],
    update_room_last_message_fn: Callable[[str, str], Any],
    set_room_state_patch_fn: Callable[[str, Dict[str, Any]], Any],
    clear_run_state_fn: Callable[[str], Any],
    new_id_fn: Callable[[str], str],
    utc_iso_fn: Callable[[], str],
) -> Dict[str, Any]:
    if step_budget["budget_exhausted"]:
        checkpoint_summary = "budget exhausted before supervisor synthesis"
        return {
            "interrupted": True,
            "result": interrupt_supervisor_run_fn(
                room_id=room_id,
                rid=rid,
                run_id=run_id,
                trigger_event_id=plan_evt["id"],
                question=question,
                phase="synthesizing",
                plan_summary=plan_summary,
                checkpoint_summary=checkpoint_summary,
                supervisor_request_args=supervisor_request_args,
                fs_context=fs_context,
                notebook_read_info=notebook_read_info,
                memory_read_info=memory_read_info,
                memory_resume_info=memory_resume_info,
                budget=step_budget,
                mode_used=mode_used,
                append_room_event_fn=append_room_event_fn,
                touch_room_updated_at_fn=touch_room_updated_at_fn,
                update_room_last_message_fn=update_room_last_message_fn,
                set_room_state_patch_fn=set_room_state_patch_fn,
                patch_supervisor_runtime_state_fn=_patch_supervisor_runtime_state,
                clear_run_state_fn=clear_run_state_fn,
                new_id_fn=new_id_fn,
                utc_iso_fn=utc_iso_fn,
            ),
        }

    supervisor_model = _safe_str(supervisor_request_args.get("supervisor_model"), model_name) or model_name

    fs_prompt_limit = 6000 if int(fs_context.get("documents_count") or 0) > 0 else 3600
    synthesis_fs_context, fs_context_text_len, fs_context_prompt_text_len = _prepare_fs_context_for_synthesis(
        fs_context,
        text_limit=fs_prompt_limit,
    )

    prompt_per_role_limit = 3200 if total <= 4 else 2400 if total <= 8 else 1800
    prompt_delegate_packets, delegate_packets_non_empty = _prepare_delegate_packets_for_synthesis(
        delegate_packets,
        question=question,
        per_role_limit=prompt_per_role_limit,
    )
    audit_delegate_packets, _ = _prepare_delegate_packets_for_synthesis(
        delegate_packets,
        question=question,
        per_role_limit=1800,
    )

    delegate_role_names = [
        _safe_str(_safe_dict(item).get("role_name"))
        for item in prompt_delegate_packets
        if _safe_str(_safe_dict(item).get("role_name"))
    ]
    grounded_points_count = sum(
        len(_safe_list(_safe_dict(item).get("primary_points")))
        for item in audit_delegate_packets
    )

    novelty_guard = _build_delegate_novelty_guard(
        question=question,
        delegate_packets=audit_delegate_packets or prompt_delegate_packets or delegate_packets,
    )

    synthesis_prompt_base = _build_supervisor_synthesis_prompt(
        question=question,
        plan_summary=plan_summary,
        fs_context=synthesis_fs_context,
        delegate_packets=prompt_delegate_packets,
        supervisor_skill_strategy=supervisor_skill_strategy,
        request_args=supervisor_request_args,
    )
    synthesis_prompt = append_supervisor_skills_prompt_block(
        synthesis_prompt_base,
        supervisor_skills_info,
    )

    memory_checkpoint = _safe_dict(memory_read_info.get("checkpoint"))

    synthesis_audit = {
        "model": supervisor_model,
        "delegate_packets_total": len(delegate_packets),
        "delegate_packets_non_empty": delegate_packets_non_empty,
        "delegate_role_names": delegate_role_names,
        "grounded_points_count": grounded_points_count,
        "fs_context_text_len": fs_context_text_len,
        "fs_context_prompt_text_len": fs_context_prompt_text_len,
        "documents_count": int(fs_context.get("documents_count") or 0),
        "target_paths": _safe_list(fs_context.get("target_paths")),
        "content_status": _safe_str(fs_context.get("content_status")),
        "synthesis_prompt_len": len(_safe_str(synthesis_prompt)),
        "supervisor_skill_strategy": _safe_str(
            supervisor_skills_info.get("strategy") or supervisor_skill_strategy,
            "builtin_plus_custom",
        ),
        "supervisor_skills_status": _safe_str(supervisor_skills_info.get("status")),
        "supervisor_skills_enabled_ids": _safe_list(supervisor_skills_info.get("enabled_skill_ids")),
        "supervisor_skills_applied_ids": _safe_list(supervisor_skills_info.get("applied_skill_ids")),
        "supervisor_skills_builtin_ids": _safe_list(supervisor_skills_info.get("builtin_skill_ids")),
        "supervisor_skills_custom_ids": _safe_list(supervisor_skills_info.get("custom_skill_ids")),
        "supervisor_skills_applied_builtin_ids": _safe_list(
            supervisor_skills_info.get("applied_builtin_skill_ids")
        ),
        "supervisor_skills_applied_custom_ids": _safe_list(
            supervisor_skills_info.get("applied_custom_skill_ids")
        ),
        "supervisor_skills_prompt_len": len(_safe_str(supervisor_skills_info.get("prompt_block"))),
        "supervisor_skills_step_count": int(supervisor_skills_payload.get("step_count") or 0),
        "supervisor_skills_resolved_items_count": int(
            supervisor_skills_payload.get("resolved_items_count") or 0
        ),
        "supervisor_skills_applied_prompt_ids": _safe_list(
            supervisor_skills_payload.get("applied_prompt_skill_ids")
        ),
        "memory_read_status": _safe_str(memory_read_info.get("status")),
        "memory_resume_decision": _safe_str(memory_resume_info.get("decision")),
        "memory_resume_reason": _safe_str(memory_resume_info.get("reason")),
        "memory_checkpoint_stage": _safe_str(memory_checkpoint.get("stage")),
        "repair_attempted": False,
        "repair_succeeded": False,
        "fallback_used": False,
        "novelty_guard": _safe_dict(novelty_guard.get("summary")),
        "novelty_coverage": {},
        "attribution": {},
        "at": utc_iso_fn(),
    }

    _patch_supervisor_runtime_state(
        room_id,
        phase="synthesizing",
        status="running",
        plan_summary=plan_summary,
        fs_context=fs_context,
        notebook_read_result=notebook_read_info,
        memory_read_result=memory_read_info,
        memory_resume_result=memory_resume_info,
        request_args=supervisor_request_args,
        run_id=run_id,
        step_budget_total=step_budget["step_budget_total"],
        step_budget_used=step_budget["step_budget_used"],
        step_budget_remaining=step_budget["step_budget_remaining"],
        budget_status=step_budget["budget_status"],
        budget_exhausted=step_budget["budget_exhausted"],
    )

    supervisor_evt: Dict[str, Any] = {
        "id": new_id_fn("evt"),
        "ts": utc_iso_fn(),
        "type": "room.supervisor",
        "room_id": room_id,
        "request_id": rid,
        "run_id": run_id,
        "trigger_event_id": plan_evt["id"],
        "payload": {
            "question": question,
            "plan_summary": plan_summary,
            "delegate_count": len(delegate_packets),
            "delegate_non_empty_count": delegate_packets_non_empty,
            "delegate_event_ids": [_safe_str(evt.get("id")) for evt in delegate_events],
            "role_ids": [_safe_str(item.get("role_id")) for item in delegate_packets],
            "role_names": [_safe_str(item.get("role_name")) for item in delegate_packets],
            "supervisor_model": supervisor_model,
            "phase": "synthesizing",
            "status": "running",
            "supervisor_skill_strategy": _safe_str(
                supervisor_skills_info.get("strategy") or supervisor_skill_strategy,
                "builtin_plus_custom",
            ),
            "synthesis_audit": synthesis_audit,
            "supervisor_fs_read": {
                "enabled": bool(fs_context.get("enabled")),
                "status": _safe_str(fs_context.get("status")),
                "reason": _safe_str(fs_context.get("reason")),
                "focus_root": _safe_str(fs_context.get("focus_root")),
                "scope": _safe_str(fs_context.get("scope")),
                "documents_count": int(fs_context.get("documents_count") or 0),
                "target_paths": _safe_list(fs_context.get("target_paths")),
                "content_status": _safe_str(fs_context.get("content_status")),
            },
            "supervisor_notebook_read": dict(supervisor_notebook_read_payload),
            "supervisor_memory_read": dict(supervisor_memory_read_payload),
            "supervisor_memory_resume": dict(supervisor_memory_resume_payload),
            "supervisor_skills": dict(supervisor_skills_payload),
            **budget_patch_fn(step_budget),
            "checkpoint_stage": "synthesizing",
            "checkpoint_summary": "",
            "interruption_reason": "",
        },
    }
    append_room_event_fn(room_id, supervisor_evt)

    try:
        raw_supervisor_packet = _safe_dict(
            _call_room_ai_reply_packet(
                room_id=room_id,
                question=synthesis_prompt,
                model_name=supervisor_model,
                request_args=supervisor_request_args,
                role={"role_id": "supervisor", "name": "Supervisor", "slug": "supervisor"},
            )
        )
    except Exception:
        raw_supervisor_packet = _safe_dict(
            _normalize_reply_packet("", default_question=question, default_mode=mode_used)
        )

    initial_text = _strip_trailing_ungrounded_disclaimer(
        _safe_str(raw_supervisor_packet.get("response") or raw_supervisor_packet.get("content"))
    )
    supervisor_packet = _normalize_supervisor_synthesis_packet(
        packet=raw_supervisor_packet,
        rid=rid,
        room_id=room_id,
        question=question,
        mode_used=mode_used,
        response_text=initial_text,
    )
    initial_text = _safe_str(supervisor_packet.get("final_response") or supervisor_packet.get("response"))
    final_text = initial_text
    synthesis_audit["initial_response_len"] = len(final_text)

    initial_novelty_coverage = _evaluate_supervisor_novelty_coverage(
        final_text=final_text,
        novelty_guard=novelty_guard,
    )
    synthesis_audit["initial_novelty_coverage"] = _safe_dict(initial_novelty_coverage.get("summary"))

    repair_needed = _needs_supervisor_repair(final_text) or _needs_supervisor_novelty_repair(
        novelty_guard=novelty_guard,
        coverage=initial_novelty_coverage,
    )

    if repair_needed:
        synthesis_audit["repair_attempted"] = True

        step_budget = consume_step_budget_fn(step_budget, 1)
        _apply_budget_to_request_args(supervisor_request_args, step_budget)

        if step_budget["budget_exhausted"]:
            checkpoint_summary = "budget exhausted before supervisor repair"
            return {
                "interrupted": True,
                "result": interrupt_supervisor_run_fn(
                    room_id=room_id,
                    rid=rid,
                    run_id=run_id,
                    trigger_event_id=supervisor_evt["id"],
                    question=question,
                    phase="synthesizing",
                    plan_summary=plan_summary,
                    checkpoint_summary=checkpoint_summary,
                    supervisor_request_args=supervisor_request_args,
                    fs_context=fs_context,
                    notebook_read_info=notebook_read_info,
                    memory_read_info=memory_read_info,
                    memory_resume_info=memory_resume_info,
                    budget=step_budget,
                    mode_used=mode_used,
                    append_room_event_fn=append_room_event_fn,
                    touch_room_updated_at_fn=touch_room_updated_at_fn,
                    update_room_last_message_fn=update_room_last_message_fn,
                    set_room_state_patch_fn=set_room_state_patch_fn,
                    patch_supervisor_runtime_state_fn=_patch_supervisor_runtime_state,
                    clear_run_state_fn=clear_run_state_fn,
                    new_id_fn=new_id_fn,
                    utc_iso_fn=utc_iso_fn,
                ),
            }

        try:
            repair_prompt_base = _build_supervisor_repair_prompt(
                question=question,
                draft_answer=final_text,
                plan_summary=plan_summary,
                fs_context=synthesis_fs_context,
                delegate_packets=prompt_delegate_packets,
                supervisor_skill_strategy=supervisor_skill_strategy,
                request_args=supervisor_request_args,
            )
            repair_prompt = append_supervisor_skills_prompt_block(
                repair_prompt_base,
                supervisor_skills_info,
            )
            synthesis_audit["repair_prompt_len"] = len(_safe_str(repair_prompt))

            raw_repair_packet = _safe_dict(
                _call_room_ai_reply_packet(
                    room_id=room_id,
                    question=repair_prompt,
                    model_name=supervisor_model,
                    request_args=supervisor_request_args,
                    role={"role_id": "supervisor", "name": "Supervisor", "slug": "supervisor"},
                )
            )
            repair_text = _strip_trailing_ungrounded_disclaimer(
                _safe_str(raw_repair_packet.get("response") or raw_repair_packet.get("content"))
            )
            repair_packet = _normalize_supervisor_synthesis_packet(
                packet=raw_repair_packet,
                rid=rid,
                room_id=room_id,
                question=question,
                mode_used=mode_used,
                response_text=repair_text,
            )
            repair_text = _safe_str(repair_packet.get("final_response") or repair_packet.get("response"))
            synthesis_audit["repair_response_len"] = len(repair_text)

            repair_novelty_coverage = _evaluate_supervisor_novelty_coverage(
                final_text=repair_text,
                novelty_guard=novelty_guard,
            )
            synthesis_audit["repair_novelty_coverage"] = _safe_dict(repair_novelty_coverage.get("summary"))

            selected_packet, selected_text, selected_coverage, selected_source = _select_best_supervisor_candidate(
                initial_packet=supervisor_packet,
                initial_text=initial_text,
                initial_novelty_coverage=initial_novelty_coverage,
                repair_packet=repair_packet,
                repair_text=repair_text,
                repair_novelty_coverage=repair_novelty_coverage,
            )

            supervisor_packet = selected_packet
            final_text = selected_text
            synthesis_audit["selected_candidate"] = selected_source

            if (
                selected_source == "repair"
                and not _needs_supervisor_repair(final_text)
                and not _needs_supervisor_novelty_repair(
                    novelty_guard=novelty_guard,
                    coverage=selected_coverage,
                )
            ):
                synthesis_audit["repair_succeeded"] = True
            elif not final_text:
                synthesis_audit["repair_failed_reason"] = "empty_or_low_quality"
            elif _needs_supervisor_novelty_repair(
                novelty_guard=novelty_guard,
                coverage=selected_coverage,
            ):
                synthesis_audit["repair_failed_reason"] = "novelty_guard_unmet"
        except Exception as ex:
            synthesis_audit["repair_failed_reason"] = f"exception:{type(ex).__name__}"

    if not final_text:
        synthesis_audit["fallback_used"] = True
        final_text = _build_supervisor_synthesis_fallback(
            question=question,
            rows=prompt_delegate_packets or delegate_packets,
        )

    supervisor_packet = _normalize_supervisor_synthesis_packet(
        packet=supervisor_packet,
        rid=rid,
        room_id=room_id,
        question=question,
        mode_used=mode_used,
        response_text=final_text,
    )

    final_text = _safe_str(supervisor_packet.get("final_response") or supervisor_packet.get("response"))

    final_novelty_coverage = _evaluate_supervisor_novelty_coverage(
        final_text=final_text,
        novelty_guard=novelty_guard,
    )
    synthesis_audit["novelty_coverage"] = _safe_dict(final_novelty_coverage.get("summary"))

    attribution_result = _build_supervisor_attribution_tool_result(
        question=question,
        final_text=final_text,
        delegate_packets=prompt_delegate_packets or delegate_packets,
    )
    synthesis_audit["attribution"] = _safe_dict(attribution_result.get("summary"))

    return {
        "interrupted": False,
        "step_budget": step_budget,
        "supervisor_model": supervisor_model,
        "supervisor_evt": supervisor_evt,
        "supervisor_packet": supervisor_packet,
        "final_text": final_text,
        "synthesis_audit": synthesis_audit,
        "prompt_delegate_packets": prompt_delegate_packets,
        "audit_delegate_packets": audit_delegate_packets,
        "delegate_packets_non_empty": delegate_packets_non_empty,
        "novelty_guard": novelty_guard,
        "attribution_result": attribution_result,
    }


__all__ = [
    "_run_supervisor_synthesis_stage",
]

