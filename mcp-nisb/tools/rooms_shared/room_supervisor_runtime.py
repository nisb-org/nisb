from __future__ import annotations

from typing import Any, Dict, List

from .room_contracts import as_bool, utc_iso
from .room_filesystem_bridge import (
    room_supervisor_fs_probe,
    room_supervisor_notebook_write,
)
from .room_helpers import _call_room_ai_reply_packet
from .room_packet_builder import _empty_evidence_result
from .room_state_normalizer import _normalize_supervisor_skill_strategy
from .room_store import load_state_doc
from .room_supervisor_prompt_builders import (
    get_builtin_supervisor_skill_ids_for_prompt,
    _build_supervisor_direct_answer_prompt,
    _build_supervisor_direct_plan_summary,
    _build_supervisor_notebook_block,
)
from .room_supervisor_skills import (
    append_supervisor_skills_prompt_block,
    build_enabled_supervisor_skills_prompt_block,
    build_supervisor_skills_payload,
    build_supervisor_skills_tool_result,
)
from .room_supervisor_runtime_patch import _patch_supervisor_runtime_state
from .room_supervisor_runtime_projection import (
    _augment_plan_summary_with_notebook_read,
    _build_supervisor_memory_read_tool_result,
    _build_supervisor_memory_resume_tool_result,
    _build_supervisor_memory_write_tool_result,
    _build_supervisor_role,
    _build_supervisor_runtime_request_args,
    _dedupe_records,
    _derive_supervisor_notebook_read_result,
    _merge_items,
    _normalize_room_mcp_overrides,
    _tool_result_item,
)
from .room_supervisor_runtime_status import (
    _build_runtime_control_snapshot,
    _normalize_rel_path,
    _safe_dict,
    _safe_list,
    _safe_str,
)
from .supervisor_runtime.fs_context import (
    _augment_fs_context_with_file_read,
    _maybe_run_supervisor_file_read,
)
from .supervisor_runtime.memory_resume import (
    augment_plan_summary_with_memory_resume,
    decide_supervisor_memory_resume,
    load_supervisor_memory_sidecar,
    write_supervisor_memory_sidecar,
)


def _disabled_notebook_result(message: str = "notebook write skipped") -> Dict[str, Any]:
    return {
        "enabled": False,
        "status": "disabled",
        "message": _safe_str(message),
        "reason_code": "NOTEBOOK_WRITE_SKIPPED",
        "relative_path": "",
        "bytes_written": 0,
        "bytes_appended": 0,
        "tool_calls": [],
        "tool_results": [],
        "recorded_at": utc_iso(),
    }


def _build_supervisor_continuation_context(
    *,
    question: str,
    memory_read_result: Dict[str, Any],
    memory_resume_result: Dict[str, Any],
) -> Dict[str, Any]:
    read_row = _safe_dict(memory_read_result)
    resume_row = _safe_dict(memory_resume_result)

    payload = _safe_dict(
        read_row.get("payload")
        or read_row.get("sidecar")
        or read_row.get("memory")
    )
    checkpoint = _safe_dict(
        resume_row.get("checkpoint")
        or read_row.get("checkpoint")
        or read_row.get("latest_checkpoint")
        or payload.get("checkpoint")
        or payload.get("latest_checkpoint")
    )

    decision = _safe_str(resume_row.get("decision"))
    reason = _safe_str(resume_row.get("reason") or resume_row.get("resume_reason"))
    checkpoint_summary = _safe_str(
        resume_row.get("checkpoint_summary")
        or checkpoint.get("summary")
    )
    checkpoint_question = _safe_str(
        resume_row.get("checkpoint_question")
        or checkpoint.get("question")
    )
    topic_anchor = _safe_str(
        resume_row.get("topic_anchor")
        or checkpoint.get("topic_anchor")
        or checkpoint_question
    )

    enabled = bool(
        decision in {
            "continue_from_checkpoint",
            "resume_from_checkpoint",
            "continue",
            "resume",
        }
        or (checkpoint_summary and (topic_anchor or checkpoint_question))
    )

    return {
        "enabled": enabled,
        "decision": decision,
        "reason": reason,
        "checkpoint_summary": checkpoint_summary,
        "checkpoint_question": checkpoint_question,
        "topic_anchor": topic_anchor,
        "current_question": _safe_str(question),
    }


def _build_direct_runtime_control_snapshot(
    *,
    room_id: str,
    request_args: Dict[str, Any],
    run_id: str = "",
    final_status: str = "success",
    final_phase: str = "completed",
) -> Dict[str, Any]:
    raw_state = _safe_dict(load_state_doc(room_id))

    request_row = dict(_safe_dict(request_args))
    request_row["room_id"] = room_id
    request_row["current_run_id"] = _safe_str(raw_state.get("current_run_id") or run_id)
    request_row["current_run_status"] = (
        "completed" if _safe_str(final_status).lower() == "success" else "error"
    )
    request_row["last_supervisor_phase"] = _safe_str(
        raw_state.get("last_supervisor_phase") or final_phase,
        final_phase,
    )
    request_row["continuation"] = _safe_dict(request_row.get("continuation"))

    memory_resume_row = {
        "resume_ready": as_bool(raw_state.get("resume_ready"), False),
        "resume_token": _safe_str(raw_state.get("resume_token")),
        "resume_reason": _safe_str(raw_state.get("resume_reason")),
    }

    status = _safe_str(request_row.get("current_run_status"), "completed").lower()
    phase = _safe_str(request_row.get("last_supervisor_phase"), final_phase)

    return _build_runtime_control_snapshot(
        prev_state=raw_state,
        request_row=request_row,
        phase=phase,
        status=status,
        finished=True,
        memory_resume_row=memory_resume_row,
    )


def _run_supervisor_fs_read(
    *,
    room_id: str,
    request_args: Dict[str, Any],
    run_id: str = "",
    supervisor_event_id: str = "",
    final_event_id: str = "",
) -> Dict[str, Any]:
    state = _safe_dict(load_state_doc(room_id))
    runtime_request_args = _build_supervisor_runtime_request_args(
        state=state,
        request_args=request_args,
    )
    mcp = _normalize_room_mcp_overrides(
        runtime_request_args.get("mcp_overrides") or state.get("mcp_overrides")
    )
    fs_context = room_supervisor_fs_probe(
        room_id=room_id,
        request_args=runtime_request_args,
        scope=_safe_str(mcp.get("fs_read_scope"), "minimal"),
        run_id=run_id,
        supervisor_event_id=supervisor_event_id,
        final_event_id=final_event_id,
    )
    _patch_supervisor_runtime_state(
        room_id,
        phase="grounding",
        status=_safe_str(fs_context.get("status"), "running"),
        fs_context=fs_context,
        request_args=runtime_request_args,
        run_id=run_id,
    )
    return fs_context


def _run_supervisor_notebook_write(
    *,
    room_id: str,
    request_args: Dict[str, Any],
    question: str,
    plan_summary: str,
    fs_context: Dict[str, Any],
    notebook_read_result: Dict[str, Any],
    delegate_packets: List[Dict[str, Any]],
    final_text: str,
    run_id: str = "",
    supervisor_event_id: str = "",
    final_event_id: str = "",
) -> Dict[str, Any]:
    state = _safe_dict(load_state_doc(room_id))
    runtime_request_args = _build_supervisor_runtime_request_args(
        state=state,
        request_args=request_args,
    )
    mcp = _normalize_room_mcp_overrides(
        runtime_request_args.get("mcp_overrides") or state.get("mcp_overrides")
    )

    if not as_bool(mcp.get("notebook_write_enabled"), False):
        notebook_result = _disabled_notebook_result("notebook_write not enabled")
        _patch_supervisor_runtime_state(
            room_id,
            phase="writeback",
            status=_safe_str(notebook_result.get("status"), "disabled"),
            plan_summary=plan_summary,
            fs_context=fs_context,
            notebook_read_result=notebook_read_result,
            notebook_result=notebook_result,
            request_args=runtime_request_args,
            run_id=run_id,
        )
        return notebook_result

    if not _safe_str(final_text):
        notebook_result = _disabled_notebook_result("missing final supervisor text")
        _patch_supervisor_runtime_state(
            room_id,
            phase="writeback",
            status=_safe_str(notebook_result.get("status"), "disabled"),
            plan_summary=plan_summary,
            fs_context=fs_context,
            notebook_read_result=notebook_read_result,
            notebook_result=notebook_result,
            request_args=runtime_request_args,
            run_id=run_id,
        )
        return notebook_result

    block = _build_supervisor_notebook_block(
        notebook_title=_safe_str(mcp.get("notebook_title"), "Supervisor notebook"),
        notebook_section_title=_safe_str(mcp.get("notebook_section_title"), "latest"),
        question=question,
        plan_summary=plan_summary,
        fs_context=_safe_dict(fs_context),
        delegate_packets=_safe_list(delegate_packets),
        final_text=final_text,
    )

    notebook_result = room_supervisor_notebook_write(
        room_id=room_id,
        request_args=runtime_request_args,
        content=block,
        run_id=run_id,
        supervisor_event_id=supervisor_event_id,
        final_event_id=final_event_id,
    )
    _patch_supervisor_runtime_state(
        room_id,
        phase="writeback",
        status=_safe_str(notebook_result.get("status"), "running"),
        plan_summary=plan_summary,
        fs_context=fs_context,
        notebook_read_result=notebook_read_result,
        notebook_result=notebook_result,
        request_args=runtime_request_args,
        run_id=run_id,
    )
    return notebook_result


def _run_supervisor_direct_answer(
    *,
    room_id: str,
    question: str,
    model_name: str,
    mode_used: str,
    request_args: Dict[str, Any],
) -> Dict[str, Any]:
    state = _safe_dict(load_state_doc(room_id))
    runtime_request_args = _build_supervisor_runtime_request_args(
        state=state,
        request_args=request_args,
    )
    supervisor_model = (
        _safe_str(runtime_request_args.get("supervisor_model"))
        or _safe_str(state.get("supervisor_model"))
        or _safe_str(model_name)
    )
    supervisor_skill_strategy = _normalize_supervisor_skill_strategy(
        state.get("supervisor_skill_strategy")
        or runtime_request_args.get("supervisor_skill_strategy")
        or runtime_request_args.get("supervisor_skills_strategy"),
        "builtin_plus_custom",
    )
    applied_builtin_skill_ids = get_builtin_supervisor_skill_ids_for_prompt(
        "direct",
        supervisor_skill_strategy,
    )

    run_id = _safe_str(runtime_request_args.get("run_id"))
    supervisor_event_id = _safe_str(runtime_request_args.get("supervisor_event_id"))
    final_event_id = _safe_str(runtime_request_args.get("final_event_id"))
    mcp = _normalize_room_mcp_overrides(
        runtime_request_args.get("mcp_overrides") or state.get("mcp_overrides")
    )
    runtime_request_args["mcp_overrides"] = dict(mcp)

    _patch_supervisor_runtime_state(
        room_id,
        phase="planning",
        status="running",
        request_args=runtime_request_args,
        run_id=run_id,
    )

    fs_context = _run_supervisor_fs_read(
        room_id=room_id,
        request_args=runtime_request_args,
        run_id=run_id,
        supervisor_event_id=supervisor_event_id,
        final_event_id=final_event_id,
    )

    notebook_read_result: Dict[str, Any] = {}
    memory_read_result: Dict[str, Any] = {}
    memory_resume_result: Dict[str, Any] = {}
    memory_result: Dict[str, Any] = {}
    continuation_context: Dict[str, Any] = {}

    file_read_result = _maybe_run_supervisor_file_read(
        room_id=room_id,
        question=question,
        request_args=runtime_request_args,
        fs_context=fs_context,
        run_id=run_id,
        supervisor_event_id=supervisor_event_id,
        final_event_id=final_event_id,
    )
    if file_read_result:
        fs_context = _augment_fs_context_with_file_read(
            fs_context=fs_context,
            file_read_result=file_read_result,
        )
        notebook_read_result = _derive_supervisor_notebook_read_result(
            file_read_result=file_read_result,
            mcp=mcp,
        )
        _patch_supervisor_runtime_state(
            room_id,
            phase="grounding",
            status=_safe_str(file_read_result.get("status") or fs_context.get("status"), "running"),
            fs_context=fs_context,
            notebook_read_result=notebook_read_result,
            request_args=runtime_request_args,
            run_id=run_id,
        )

    memory_read_result = load_supervisor_memory_sidecar(
        room_id=room_id,
        mcp=mcp,
    )
    memory_resume_result = decide_supervisor_memory_resume(
        question=question,
        memory_read_result=memory_read_result,
    )
    continuation_context = _build_supervisor_continuation_context(
        question=question,
        memory_read_result=memory_read_result,
        memory_resume_result=memory_resume_result,
    )

    runtime_request_args["supervisor_memory_read"] = dict(memory_read_result)
    runtime_request_args["supervisor_memory_resume"] = dict(memory_resume_result)
    runtime_request_args["supervisor_continuation_context"] = dict(continuation_context)
    runtime_request_args["continuation"] = dict(continuation_context)
    runtime_request_args["last_checkpoint_summary"] = _safe_str(continuation_context.get("checkpoint_summary"))
    runtime_request_args["last_checkpoint_question"] = _safe_str(continuation_context.get("checkpoint_question"))
    runtime_request_args["last_topic_anchor"] = _safe_str(continuation_context.get("topic_anchor"))

    plan_summary = _build_supervisor_direct_plan_summary(question=question, fs_context=fs_context)
    plan_summary = _augment_plan_summary_with_notebook_read(plan_summary, notebook_read_result)
    plan_summary = augment_plan_summary_with_memory_resume(
        plan_summary,
        memory_read_result,
        memory_resume_result,
    )

    supervisor_skills_info = build_enabled_supervisor_skills_prompt_block(
        room_id=room_id,
        state=state,
        request_args=runtime_request_args,
        enabled_skill_ids=state.get("enabled_supervisor_skill_ids"),
        strategy=supervisor_skill_strategy,
    )
    supervisor_skills_info = dict(_safe_dict(supervisor_skills_info))
    supervisor_skills_info["strategy"] = _safe_str(
        supervisor_skills_info.get("strategy") or supervisor_skill_strategy,
        "builtin_plus_custom",
    )
    supervisor_skills_info["supervisor_skill_strategy"] = supervisor_skills_info["strategy"]
    supervisor_skills_info["builtin_skill_ids"] = list(applied_builtin_skill_ids)
    supervisor_skills_info["applied_builtin_skill_ids"] = list(applied_builtin_skill_ids)
    supervisor_skills_info["custom_skill_ids"] = _safe_list(supervisor_skills_info.get("custom_skill_ids"))
    supervisor_skills_info["applied_custom_skill_ids"] = _safe_list(
        supervisor_skills_info.get("applied_custom_skill_ids") or supervisor_skills_info.get("applied_skill_ids")
    )
    supervisor_skills_info["applied_prompt_skill_ids"] = _safe_list(
        supervisor_skills_info.get("applied_prompt_skill_ids") or supervisor_skills_info.get("applied_skill_ids")
    )
    supervisor_skills_payload = build_supervisor_skills_payload(supervisor_skills_info)

    _patch_supervisor_runtime_state(
        room_id,
        phase="synthesizing",
        status="running",
        plan_summary=plan_summary,
        fs_context=fs_context,
        notebook_read_result=notebook_read_result,
        memory_read_result=memory_read_result,
        memory_resume_result=memory_resume_result,
        request_args=runtime_request_args,
        run_id=run_id,
    )

    direct_prompt_base = _build_supervisor_direct_answer_prompt(
        question=question,
        room_state=state,
        fs_context=fs_context,
        supervisor_skill_strategy=supervisor_skill_strategy,
        memory_read_result=memory_read_result,
        memory_resume_result=memory_resume_result,
        continuation_context=continuation_context,
        request_args=runtime_request_args,
    )
    direct_prompt = append_supervisor_skills_prompt_block(
        direct_prompt_base,
        supervisor_skills_info,
    )

    reply_args = dict(runtime_request_args)
    fs_text = _safe_str(fs_context.get("text"))
    fs_documents = _safe_list(fs_context.get("documents"))
    fs_tool_results = _safe_list(fs_context.get("tool_results"))

    reply_args["_supervisor_fs_read_text"] = fs_text
    reply_args["supervisor_fs_read_text"] = fs_text
    reply_args["last_supervisor_fs_read_text"] = fs_text
    reply_args["room_supervisor_fs_read_text"] = fs_text
    reply_args["fs_context_text"] = fs_text

    reply_args["_supervisor_direct_prompt"] = direct_prompt
    reply_args["supervisor_direct_prompt"] = direct_prompt
    reply_args["supervisor_skills_prompt_block"] = _safe_str(supervisor_skills_info.get("prompt_block"))
    reply_args["supervisor_skills_enabled_ids"] = _safe_list(supervisor_skills_info.get("enabled_skill_ids"))
    reply_args["supervisor_skills_applied_ids"] = _safe_list(supervisor_skills_info.get("applied_skill_ids"))
    reply_args["supervisor_skills_applied_prompt_ids"] = _safe_list(
        supervisor_skills_payload.get("applied_prompt_skill_ids")
    )
    reply_args["supervisor_skill_strategy"] = _safe_str(
        supervisor_skills_info.get("strategy") or supervisor_skill_strategy,
        "builtin_plus_custom",
    )
    reply_args["supervisor_skills_strategy"] = reply_args["supervisor_skill_strategy"]
    reply_args["supervisor_skills_builtin_ids"] = _safe_list(supervisor_skills_info.get("builtin_skill_ids"))
    reply_args["supervisor_skills_custom_ids"] = _safe_list(supervisor_skills_info.get("custom_skill_ids"))
    reply_args["supervisor_skills_applied_builtin_ids"] = _safe_list(
        supervisor_skills_info.get("applied_builtin_skill_ids")
    )
    reply_args["supervisor_skills_applied_custom_ids"] = _safe_list(
        supervisor_skills_info.get("applied_custom_skill_ids")
    )
    reply_args["supervisor_skills_payload"] = dict(supervisor_skills_payload)

    reply_args["fs_context"] = dict(fs_context)
    reply_args["supervisor_fs_context"] = dict(fs_context)
    reply_args["room_supervisor_fs_context"] = dict(fs_context)
    reply_args["last_supervisor_fs_context"] = dict(fs_context)
    reply_args["room_fs_context"] = dict(fs_context)

    reply_args["documents"] = list(fs_documents)
    reply_args["fs_documents"] = list(fs_documents)
    reply_args["supervisor_fs_documents"] = list(fs_documents)
    reply_args["room_supervisor_fs_documents"] = list(fs_documents)

    reply_args["last_supervisor_tool_results"] = list(fs_tool_results)
    reply_args["last_supervisor_fs_tool_results"] = list(fs_tool_results)
    reply_args["supervisor_tool_results"] = list(fs_tool_results)
    reply_args["supervisor_fs_tool_results"] = list(fs_tool_results)

    reply_args["supervisor_memory_read"] = dict(memory_read_result)
    reply_args["supervisor_memory_resume"] = dict(memory_resume_result)
    reply_args["supervisor_continuation_context"] = dict(continuation_context)
    reply_args["continuation"] = dict(continuation_context)
    reply_args["last_checkpoint_summary"] = _safe_str(continuation_context.get("checkpoint_summary"))
    reply_args["last_checkpoint_question"] = _safe_str(continuation_context.get("checkpoint_question"))
    reply_args["last_topic_anchor"] = _safe_str(continuation_context.get("topic_anchor"))

    reply_args["_supervisor_direct_answer"] = True
    reply_args["_supervisor_direct_plan_summary"] = plan_summary
    reply_args["model"] = supervisor_model
    reply_args["_supervisor_user_question"] = question
    reply_args["supervisor_user_question"] = question
    direct_prompt_input = _safe_str(direct_prompt).strip() or question
    reply_args["supervisor_direct_prompt_primary_input"] = True
    reply_args["supervisor_direct_prompt_chars"] = len(direct_prompt_input)

    ai_tool_calls: List[Any] = []
    ai_tool_results: List[Any] = []
    notebook_result: Dict[str, Any] = {}
    response = ""
    citations: List[Any] = []
    rss_evidence: List[Any] = []
    market_evidence: List[Any] = []
    evidence_query = question
    evidence_tools: List[Any] = []
    evidence_result: Dict[str, Any] = _empty_evidence_result(question)
    actual_mode_used = _safe_str(mode_used, "off")

    try:
        packet = _safe_dict(
            _call_room_ai_reply_packet(
                room_id=room_id,
                question=direct_prompt_input,
                model_name=supervisor_model,
                request_args=reply_args,
                role=_build_supervisor_role(supervisor_model),
            )
        )

        content = _safe_str(packet.get("content") or packet.get("response") or packet.get("message"))
        response = content or _safe_str(packet.get("message"), "Supervisor 未返回正文")
        citations = _safe_list(packet.get("citations"))
        rss_evidence = _safe_list(packet.get("rss_evidence"))
        market_evidence = _safe_list(packet.get("market_evidence"))
        evidence_query = _safe_str(packet.get("evidence_query"), question) or question
        evidence_tools = _safe_list(packet.get("evidence_tools"))
        evidence_result = _safe_dict(packet.get("evidence_result")) or _empty_evidence_result(evidence_query)
        actual_mode_used = _safe_str(packet.get("mode_used"), actual_mode_used)
        ai_tool_calls = _safe_list(packet.get("tool_calls"))
        ai_tool_results = _safe_list(packet.get("tool_results"))

        notebook_result = _run_supervisor_notebook_write(
            room_id=room_id,
            request_args=runtime_request_args,
            question=question,
            plan_summary=plan_summary,
            fs_context=fs_context,
            notebook_read_result=notebook_read_result,
            delegate_packets=[],
            final_text=response,
            run_id=run_id,
            supervisor_event_id=supervisor_event_id,
            final_event_id=final_event_id,
        )

        memory_result = write_supervisor_memory_sidecar(
            room_id=room_id,
            mcp=mcp,
            question=question,
            plan_summary=plan_summary,
            fs_context=fs_context,
            memory_read_result=memory_read_result,
            memory_resume_result=memory_resume_result,
            delegate_packets=[],
            final_text=response,
            run_id=run_id,
            supervisor_event_id=supervisor_event_id,
            final_event_id=final_event_id,
        )

        supervisor_skills_result = build_supervisor_skills_tool_result(supervisor_skills_info)

        notebook_read_tool_result = (
            _tool_result_item(
                "supervisor_notebook_read",
                status=_safe_str(notebook_read_result.get("status"), "success"),
                relative_path=_normalize_rel_path(notebook_read_result.get("relative_path")),
                documents_count=int(notebook_read_result.get("documents_count") or 0),
                source_kind=_safe_str(notebook_read_result.get("source_kind"), "fs_read"),
            )
            if notebook_read_result else None
        )

        memory_read_tool_result = _build_supervisor_memory_read_tool_result(memory_read_result)
        memory_resume_tool_result = _build_supervisor_memory_resume_tool_result(memory_resume_result)
        memory_write_tool_result = _build_supervisor_memory_write_tool_result(memory_result)

        runtime_result = _tool_result_item(
            "supervisor_direct_answer",
            status="success" if response else "error",
            model=supervisor_model,
            provider=_safe_str(runtime_request_args.get("supervisor_provider") or state.get("supervisor_provider")),
            reply_mode="supervisor_direct",
            question=question,
            plan_summary=plan_summary,
            target_paths=_safe_list(fs_context.get("target_paths")),
            documents_count=int(fs_context.get("documents_count") or 0),
            supervisor_skills_status=_safe_str(supervisor_skills_info.get("status")),
            supervisor_skills_enabled_ids=_safe_list(supervisor_skills_info.get("enabled_skill_ids")),
            supervisor_skills_applied_ids=_safe_list(supervisor_skills_info.get("applied_skill_ids")),
            supervisor_skills_applied_prompt_ids=_safe_list(
                supervisor_skills_payload.get("applied_prompt_skill_ids")
            ),
            supervisor_skill_strategy=_safe_str(
                supervisor_skills_info.get("strategy") or supervisor_skill_strategy,
                "builtin_plus_custom",
            ),
            supervisor_skills_builtin_ids=_safe_list(supervisor_skills_info.get("builtin_skill_ids")),
            supervisor_skills_custom_ids=_safe_list(supervisor_skills_info.get("custom_skill_ids")),
            supervisor_skills_applied_builtin_ids=_safe_list(
                supervisor_skills_info.get("applied_builtin_skill_ids")
            ),
            supervisor_skills_applied_custom_ids=_safe_list(
                supervisor_skills_info.get("applied_custom_skill_ids")
            ),
            supervisor_skills_step_count=int(supervisor_skills_payload.get("step_count") or 0),
            supervisor_skills_resolved_items_count=int(
                supervisor_skills_payload.get("resolved_items_count") or 0
            ),
            supervisor_skills_prompt_block_chars=int(
                supervisor_skills_payload.get("prompt_block_chars") or 0
            ),
            supervisor_direct_prompt_primary_input=True,
            supervisor_direct_prompt_chars=len(direct_prompt_input),
            memory_read_status=_safe_str(memory_read_result.get("status")),
            memory_resume_decision=_safe_str(memory_resume_result.get("decision")),
            memory_write_status=_safe_str(memory_result.get("status")),
            continuation_enabled=as_bool(continuation_context.get("enabled"), False),
            continuation_checkpoint_question=_safe_str(continuation_context.get("checkpoint_question")),
            continuation_topic_anchor=_safe_str(continuation_context.get("topic_anchor")),
        )

        combined_tool_calls = _dedupe_records(
            _merge_items(
                fs_context.get("tool_calls"),
                ai_tool_calls,
                notebook_result.get("tool_calls"),
            )
        )
        combined_tool_results = _dedupe_records(
            _merge_items(
                fs_context.get("tool_results"),
                ai_tool_results,
                [runtime_result, supervisor_skills_result],
                [notebook_read_tool_result] if notebook_read_tool_result else [],
                [memory_read_tool_result] if memory_read_tool_result else [],
                [memory_resume_tool_result] if memory_resume_tool_result else [],
                [memory_write_tool_result] if memory_write_tool_result else [],
                notebook_result.get("tool_results"),
            )
        )

        _patch_supervisor_runtime_state(
            room_id,
            phase="completed",
            status="success" if response else "error",
            plan_summary=plan_summary,
            fs_context=fs_context,
            notebook_read_result=notebook_read_result,
            notebook_result=notebook_result,
            memory_read_result=memory_read_result,
            memory_resume_result=memory_resume_result,
            memory_result=memory_result,
            request_args=runtime_request_args,
            run_id=run_id,
            finished=True,
        )

        runtime_control_snapshot = _build_direct_runtime_control_snapshot(
            room_id=room_id,
            request_args=runtime_request_args,
            run_id=run_id,
            final_status="success" if response else "error",
            final_phase="completed",
        )

        return {
            "status": "success" if response else "error",
            "content": response,
            "response": response,
            "model": supervisor_model,
            "mode_used": actual_mode_used,
            "citations": citations,
            "rss_evidence": rss_evidence,
            "market_evidence": market_evidence,
            "evidence_query": evidence_query,
            "evidence_tools": evidence_tools,
            "evidence_result": evidence_result,
            "tool_calls": combined_tool_calls,
            "tool_results": combined_tool_results,
            "runtime_control_snapshot": runtime_control_snapshot,
            "fs_context": fs_context,
            "supervisor_notebook_read": notebook_read_result,
            "supervisor_memory_read": memory_read_result,
            "supervisor_memory_resume": memory_resume_result,
            "supervisor_memory_write": memory_result,
            "supervisor_continuation_context": continuation_context,
            "notebook_result": notebook_result,
            "plan_summary": plan_summary,
            "supervisor_skill_strategy": _safe_str(
                supervisor_skills_info.get("strategy") or supervisor_skill_strategy,
                "builtin_plus_custom",
            ),
            "supervisor_skills": dict(supervisor_skills_payload),
        }
    except Exception as ex:
        error_message = f"{type(ex).__name__}: {ex}"
        supervisor_skills_result = build_supervisor_skills_tool_result(supervisor_skills_info)

        notebook_read_tool_result = (
            _tool_result_item(
                "supervisor_notebook_read",
                status=_safe_str(notebook_read_result.get("status"), "success"),
                relative_path=_normalize_rel_path(notebook_read_result.get("relative_path")),
                documents_count=int(notebook_read_result.get("documents_count") or 0),
                source_kind=_safe_str(notebook_read_result.get("source_kind"), "fs_read"),
            )
            if notebook_read_result else None
        )
        memory_read_tool_result = _build_supervisor_memory_read_tool_result(memory_read_result)
        memory_resume_tool_result = _build_supervisor_memory_resume_tool_result(memory_resume_result)

        runtime_result = _tool_result_item(
            "supervisor_direct_answer",
            status="error",
            model=supervisor_model,
            provider=_safe_str(runtime_request_args.get("supervisor_provider") or state.get("supervisor_provider")),
            reply_mode="supervisor_direct",
            question=question,
            plan_summary=plan_summary,
            error=error_message,
            target_paths=_safe_list(fs_context.get("target_paths")),
            documents_count=int(fs_context.get("documents_count") or 0),
            supervisor_skills_status=_safe_str(supervisor_skills_info.get("status")),
            supervisor_skills_enabled_ids=_safe_list(supervisor_skills_info.get("enabled_skill_ids")),
            supervisor_skills_applied_ids=_safe_list(supervisor_skills_info.get("applied_skill_ids")),
            supervisor_skills_applied_prompt_ids=_safe_list(
                supervisor_skills_payload.get("applied_prompt_skill_ids")
            ),
            supervisor_skill_strategy=_safe_str(
                supervisor_skills_info.get("strategy") or supervisor_skill_strategy,
                "builtin_plus_custom",
            ),
            supervisor_skills_builtin_ids=_safe_list(supervisor_skills_info.get("builtin_skill_ids")),
            supervisor_skills_custom_ids=_safe_list(supervisor_skills_info.get("custom_skill_ids")),
            supervisor_skills_applied_builtin_ids=_safe_list(
                supervisor_skills_info.get("applied_builtin_skill_ids")
            ),
            supervisor_skills_applied_custom_ids=_safe_list(
                supervisor_skills_info.get("applied_custom_skill_ids")
            ),
            supervisor_skills_step_count=int(supervisor_skills_payload.get("step_count") or 0),
            supervisor_skills_resolved_items_count=int(
                supervisor_skills_payload.get("resolved_items_count") or 0
            ),
            supervisor_skills_prompt_block_chars=int(
                supervisor_skills_payload.get("prompt_block_chars") or 0
            ),
            supervisor_direct_prompt_primary_input=True,
            supervisor_direct_prompt_chars=len(direct_prompt_input),
            memory_read_status=_safe_str(memory_read_result.get("status")),
            memory_resume_decision=_safe_str(memory_resume_result.get("decision")),
            continuation_enabled=as_bool(continuation_context.get("enabled"), False),
            continuation_checkpoint_question=_safe_str(continuation_context.get("checkpoint_question")),
            continuation_topic_anchor=_safe_str(continuation_context.get("topic_anchor")),
        )
        combined_tool_calls = _dedupe_records(_merge_items(fs_context.get("tool_calls")))
        combined_tool_results = _dedupe_records(
            _merge_items(
                fs_context.get("tool_results"),
                [runtime_result, supervisor_skills_result],
                [notebook_read_tool_result] if notebook_read_tool_result else [],
                [memory_read_tool_result] if memory_read_tool_result else [],
                [memory_resume_tool_result] if memory_resume_tool_result else [],
            )
        )

        _patch_supervisor_runtime_state(
            room_id,
            phase="completed",
            status="error",
            plan_summary=plan_summary,
            fs_context=fs_context,
            notebook_read_result=notebook_read_result,
            notebook_result={},
            memory_read_result=memory_read_result,
            memory_resume_result=memory_resume_result,
            memory_result={},
            request_args=runtime_request_args,
            run_id=run_id,
            finished=True,
        )

        runtime_control_snapshot = _build_direct_runtime_control_snapshot(
            room_id=room_id,
            request_args=runtime_request_args,
            run_id=run_id,
            final_status="error",
            final_phase="completed",
        )

        return {
            "status": "error",
            "content": error_message,
            "response": error_message,
            "model": supervisor_model,
            "mode_used": _safe_str(mode_used, "off"),
            "citations": [],
            "rss_evidence": [],
            "market_evidence": [],
            "evidence_query": question,
            "evidence_tools": [],
            "evidence_result": _empty_evidence_result(question),
            "tool_calls": combined_tool_calls,
            "tool_results": combined_tool_results,
            "runtime_control_snapshot": runtime_control_snapshot,
            "fs_context": fs_context,
            "supervisor_notebook_read": notebook_read_result,
            "supervisor_memory_read": memory_read_result,
            "supervisor_memory_resume": memory_resume_result,
            "supervisor_memory_write": {},
            "supervisor_continuation_context": continuation_context,
            "notebook_result": {},
            "plan_summary": plan_summary,
            "supervisor_skill_strategy": _safe_str(
                supervisor_skills_info.get("strategy") or supervisor_skill_strategy,
                "builtin_plus_custom",
            ),
            "supervisor_skills": dict(supervisor_skills_payload),
        }


__all__ = [
    "_augment_fs_context_with_file_read",
    "_augment_plan_summary_with_notebook_read",
    "_build_supervisor_runtime_request_args",
    "_derive_supervisor_notebook_read_result",
    "_maybe_run_supervisor_file_read",
    "_normalize_room_mcp_overrides",
    "_patch_supervisor_runtime_state",
    "_run_supervisor_direct_answer",
    "_run_supervisor_fs_read",
    "_run_supervisor_notebook_write",
]

