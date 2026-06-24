from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional

from .room_audit_helpers import _append_aborted_event
from .room_packet_builder import (
    _build_room_message_payload,
    _empty_evidence_result,
    _normalize_tool_activity_lists,
)
from .room_role_runtime_request import (
    _generate_role_reply_packet,
    _safe_list,
    _safe_str,
    _sanitize_room_worker_request_args,
)
from .room_supervisor_runtime import _patch_supervisor_runtime_state
from .room_worker_concurrency import (
    _get_worker_concurrency,
    _get_worker_stagger_seconds,
    _run_bounded_worker_pool,
)


def _safe_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _apply_budget_to_request_args(
    request_args: Dict[str, Any],
    step_budget: Dict[str, Any],
) -> None:
    request_args["supervisor_step_budget_used"] = step_budget["step_budget_used"]
    request_args["supervisor_step_budget_remaining"] = step_budget["step_budget_remaining"]
    request_args["supervisor_budget_status"] = step_budget["budget_status"]
    request_args["supervisor_budget_exhausted"] = step_budget["budget_exhausted"]


def _make_delegate_entry(
    *,
    room_id: str,
    question: str,
    role: Dict[str, Any],
    idx: int,
    total: int,
    run_id: str,
    trigger_event_id: str,
    rid: str,
    plan_summary: str = "",
    new_id_fn: Callable[[str], str],
    utc_iso_fn: Callable[[], str],
) -> Dict[str, Any]:
    role_obj = dict(role or {})
    role_id = _safe_str(role_obj.get("role_id"))
    role_name = _safe_str(role_obj.get("name") or role_obj.get("slug") or role_id, "role")

    payload = {
        "delegate_index": idx,
        "delegate_total": total,
        "role_id": role_id,
        "role_name": role_name,
        "question": question,
    }
    if plan_summary:
        payload["plan_summary"] = plan_summary

    delegate_evt = {
        "id": new_id_fn("evt"),
        "ts": utc_iso_fn(),
        "type": "room.delegate",
        "room_id": room_id,
        "request_id": rid,
        "run_id": run_id,
        "trigger_event_id": trigger_event_id,
        "payload": payload,
    }

    return {
        "idx": idx,
        "role": role_obj,
        "role_id": role_id,
        "role_name": role_name,
        "delegate_evt": delegate_evt,
    }


def _generate_delegate_packet_result(
    *,
    room_id: str,
    question: str,
    role: Dict[str, Any],
    role_id: str,
    role_name: str,
    model_name: str,
    request_args: Dict[str, Any],
) -> Dict[str, Any]:
    packet = _generate_role_reply_packet(
        room_id=room_id,
        question=question,
        role=dict(role or {}),
        model_name=model_name,
        request_args=dict(request_args or {}),
    )
    content = _safe_str(packet.get("content"))
    role_tool_calls, role_tool_results = _normalize_tool_activity_lists(
        packet.get("tool_calls"),
        packet.get("tool_results"),
    )
    return {
        "ok": True,
        "role": dict(role or {}),
        "role_id": role_id,
        "role_name": role_name,
        "packet": packet,
        "content": content,
        "tool_calls": role_tool_calls,
        "tool_results": role_tool_results,
    }


def _delegate_error_result(entry: Dict[str, Any], ex: Exception) -> Dict[str, Any]:
    return {
        "ok": False,
        "idx": entry["idx"],
        "role": entry["role"],
        "role_id": entry["role_id"],
        "role_name": entry["role_name"],
        "delegate_evt": entry["delegate_evt"],
        "error_type": type(ex).__name__,
    }


def _run_delegate_packet_single(
    *,
    entry: Dict[str, Any],
    room_id: str,
    question: str,
    model_name: str,
    request_args: Dict[str, Any],
) -> Dict[str, Any]:
    try:
        result = _generate_delegate_packet_result(
            room_id=room_id,
            question=question,
            role=entry["role"],
            role_id=entry["role_id"],
            role_name=entry["role_name"],
            model_name=model_name,
            request_args=request_args,
        )
        result["idx"] = entry["idx"]
        result["delegate_evt"] = entry["delegate_evt"]
        return result
    except Exception as ex:
        return _delegate_error_result(entry, ex)


def _run_delegate_packet_pool(
    *,
    entries: List[Dict[str, Any]],
    room_id: str,
    question: str,
    model_name: str,
    request_args: Dict[str, Any],
    max_workers: int,
    stagger_seconds: float,
    on_result_fn: Optional[Callable[[Dict[str, Any]], Any]] = None,
) -> List[Dict[str, Any]]:
    def worker_fn(entry: Dict[str, Any]) -> Dict[str, Any]:
        result = _generate_delegate_packet_result(
            room_id=room_id,
            question=question,
            role=entry["role"],
            role_id=entry["role_id"],
            role_name=entry["role_name"],
            model_name=model_name,
            request_args=request_args,
        )
        result["idx"] = entry["idx"]
        result["delegate_evt"] = entry["delegate_evt"]
        return result

    return _run_bounded_worker_pool(
        items=entries,
        worker_fn=worker_fn,
        error_result_fn=_delegate_error_result,
        index_key="idx",
        max_workers=max_workers,
        stagger_seconds=stagger_seconds,
        on_result_fn=on_result_fn,
    )


def _load_room_state_for_runtime_stop(room_id: str) -> Dict[str, Any]:
    try:
        from .room_store import load_state_doc

        return _safe_dict(load_state_doc(room_id))
    except Exception:
        return {}


def _runtime_stop_requested(
    *,
    room_id: str,
    run_id: str,
    state: Optional[Dict[str, Any]] = None,
) -> bool:
    target_run_id = _safe_str(run_id)
    if not target_run_id:
        return False

    row = _safe_dict(state) or _load_room_state_for_runtime_stop(room_id)
    current_run_id = _safe_str(row.get("current_run_id"))
    runtime_control_run_id = _safe_str(row.get("runtime_control_run_id"))

    def _truthy_stop(value: Any) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return value != 0
        text = _safe_str(value).strip().lower()
        return text in {
            "1",
            "true",
            "yes",
            "y",
            "on",
            "stop",
            "stopped",
            "abort",
            "aborted",
            "cancel",
            "cancelled",
            "canceled",
        }

    explicit_stop_requested = any(
        _truthy_stop(row.get(key))
        for key in (
            "stop_requested",
            "abort_requested",
            "cancel_requested",
            "runtime_stop_requested",
            "runtime_abort_requested",
            "runtime_cancel_requested",
        )
    )

    control_action = _safe_str(
        row.get("runtime_control_action")
        or row.get("runtime_control_command")
        or row.get("runtime_action")
        or row.get("control_action")
    ).strip().lower()

    if control_action in {"stop", "stopped", "abort", "aborted", "cancel", "cancelled", "canceled"}:
        explicit_stop_requested = True

    stop_run_id = _safe_str(
        row.get("stop_run_id")
        or row.get("abort_run_id")
        or row.get("cancel_run_id")
        or row.get("runtime_stop_run_id")
        or row.get("runtime_abort_run_id")
        or row.get("runtime_cancel_run_id")
        or runtime_control_run_id
    )

    if current_run_id and current_run_id != target_run_id:
        return True

    if not explicit_stop_requested:
        return False

    if stop_run_id and stop_run_id != target_run_id:
        return False

    if current_run_id == target_run_id:
        return True

    if stop_run_id == target_run_id:
        return True

    return False


def _mark_runtime_stop_observed(
    *,
    room_id: str,
    run_id: str,
    set_room_state_patch_fn: Callable[[str, Dict[str, Any]], Any],
    utc_iso_fn: Callable[[], str],
) -> None:
    try:
        set_room_state_patch_fn(
            room_id,
            {
                "current_run_id": "",
                "current_request_id": "",
                "current_run_status": "aborted",
                "current_delegate_role_id": "",
                "current_delegate_role_name": "",
                "current_delegate_index": 0,
                "current_delegate_total": 0,
                "runtime_control_run_id": _safe_str(run_id),
                "runtime_state_hint": "idle",
                "runtime_phase_hint": "idle",
                "continuation_status": "aborted",
                "last_run_finished_at": utc_iso_fn(),
            },
        )
    except Exception:
        pass


def _append_role_message_from_delegate_result(
    *,
    result: Dict[str, Any],
    room_id: str,
    question: str,
    rid: str,
    run_id: str,
    mode_used: str,
    model_name: str,
    append_room_event_fn: Callable[[str, Dict[str, Any]], Any],
    touch_room_updated_at_fn: Callable[[str], Any],
    update_room_last_message_fn: Callable[[str, str], Any],
    new_id_fn: Callable[[str], str],
    utc_iso_fn: Callable[[], str],
) -> Optional[Dict[str, Any]]:
    delegate_evt = result["delegate_evt"]
    role = result.get("role") or {}
    role_id = _safe_str(result.get("role_id"))
    role_name = _safe_str(result.get("role_name"), "role")

    if not result.get("ok"):
        _append_aborted_event(
            room_id=room_id,
            request_id=rid,
            trigger_event_id=delegate_evt["id"],
            sender=_safe_str(role.get("slug") or role_name, role_name),
            role_id=role_id,
            reason=f"exception:{_safe_str(result.get('error_type'), 'Exception')}",
            run_id=run_id,
        )
        return None

    content = _safe_str(result.get("content"))
    if not content:
        return None

    packet = result.get("packet") or {}
    role_tool_calls = result.get("tool_calls") or []
    role_tool_results = result.get("tool_results") or []

    role_msg_evt = {
        "id": new_id_fn("evt"),
        "ts": utc_iso_fn(),
        "type": "room.message",
        "room_id": room_id,
        "request_id": rid,
        "run_id": run_id,
        "trigger_event_id": delegate_evt["id"],
        "payload": _build_room_message_payload(
            sender=_safe_str(role.get("slug") or role_name, role_name),
            sender_type="role",
            content=content,
            model=_safe_str(packet.get("model") or role.get("model") or model_name, model_name),
            mode_used=_safe_str(packet.get("mode_used"), mode_used),
            role_id=role_id,
            role_name=role_name,
            avatar=_safe_str(role.get("avatar"), "🤖"),
            citations=packet.get("citations"),
            rss_evidence=packet.get("rss_evidence"),
            market_evidence=packet.get("market_evidence"),
            evidence_query=_safe_str(packet.get("evidence_query"), question),
            evidence_tools=packet.get("evidence_tools"),
            evidence_result=packet.get("evidence_result"),
            tool_calls=role_tool_calls,
            tool_results=role_tool_results,
        ),
    }
    append_room_event_fn(room_id, role_msg_evt)
    touch_room_updated_at_fn(room_id)
    update_room_last_message_fn(room_id, role_msg_evt["id"])
    return role_msg_evt


def _build_delegate_packet_from_result(
    *,
    result: Dict[str, Any],
    question: str,
) -> Dict[str, Any]:
    role_id = _safe_str(result.get("role_id"))
    role_name = _safe_str(result.get("role_name"), "role")

    if not result.get("ok"):
        return {
            "role_id": role_id,
            "role_name": role_name,
            "content": f"{role_name} execution failed: exception:{_safe_str(result.get('error_type'), 'Exception')}",
            "citations": [],
            "rss_evidence": [],
            "market_evidence": [],
            "evidence_query": question,
            "evidence_tools": [],
            "evidence_result": _empty_evidence_result(question),
            "tool_calls": [],
            "tool_results": [],
        }

    packet = result.get("packet") or {}
    return {
        "role_id": role_id,
        "role_name": role_name,
        "content": _safe_str(result.get("content")),
        "citations": _safe_list(packet.get("citations")),
        "rss_evidence": _safe_list(packet.get("rss_evidence")),
        "market_evidence": _safe_list(packet.get("market_evidence")),
        "evidence_query": _safe_str(packet.get("evidence_query"), question),
        "evidence_tools": _safe_list(packet.get("evidence_tools")),
        "evidence_result": packet.get("evidence_result") or _empty_evidence_result(question),
        "tool_calls": result.get("tool_calls") or [],
        "tool_results": result.get("tool_results") or [],
    }


def _run_sequential_delegate_flow(
    *,
    room_id: str,
    question: str,
    active_roles: List[Dict[str, Any]],
    model_name: str,
    mode_used: str,
    run_id: str,
    trigger_event_id: str,
    rid: str,
    request_args: Dict[str, Any],
    set_room_state_patch_fn: Callable[[str, Dict[str, Any]], Any],
    append_room_event_fn: Callable[[str, Dict[str, Any]], Any],
    touch_room_updated_at_fn: Callable[[str], Any],
    update_room_last_message_fn: Callable[[str, str], Any],
    clear_run_state_fn: Callable[[str], Any],
    new_id_fn: Callable[[str], str],
    utc_iso_fn: Callable[[], str],
) -> List[Dict[str, Any]]:
    generated_events: List[Dict[str, Any]] = []
    total = len(active_roles)
    local_request_args = _sanitize_room_worker_request_args(request_args, room_id)
    worker_concurrency = _get_worker_concurrency(request_args, local_request_args, total=total)
    stagger_seconds = _get_worker_stagger_seconds(request_args, local_request_args)

    if worker_concurrency <= 1:
        for idx, role in enumerate(active_roles, start=1):
            if _runtime_stop_requested(room_id=room_id, run_id=run_id):
                _mark_runtime_stop_observed(
                    room_id=room_id,
                    run_id=run_id,
                    set_room_state_patch_fn=set_room_state_patch_fn,
                    utc_iso_fn=utc_iso_fn,
                )
                break

            entry = _make_delegate_entry(
                room_id=room_id,
                question=question,
                role=role,
                idx=idx,
                total=total,
                run_id=run_id,
                trigger_event_id=trigger_event_id,
                rid=rid,
                new_id_fn=new_id_fn,
                utc_iso_fn=utc_iso_fn,
            )

            set_room_state_patch_fn(
                room_id,
                {
                    "current_run_id": run_id,
                    "current_run_status": "running",
                    "current_delegate_role_id": entry["role_id"],
                    "current_delegate_role_name": entry["role_name"],
                    "current_delegate_index": idx,
                    "current_delegate_total": total,
                },
            )

            append_room_event_fn(room_id, entry["delegate_evt"])

            result = _run_delegate_packet_single(
                entry=entry,
                room_id=room_id,
                question=question,
                model_name=model_name,
                request_args=local_request_args,
            )

            if _runtime_stop_requested(room_id=room_id, run_id=run_id):
                _mark_runtime_stop_observed(
                    room_id=room_id,
                    run_id=run_id,
                    set_room_state_patch_fn=set_room_state_patch_fn,
                    utc_iso_fn=utc_iso_fn,
                )
                break

            generated_evt = _append_role_message_from_delegate_result(
                result=result,
                room_id=room_id,
                question=question,
                rid=rid,
                run_id=run_id,
                mode_used=mode_used,
                model_name=model_name,
                append_room_event_fn=append_room_event_fn,
                touch_room_updated_at_fn=touch_room_updated_at_fn,
                update_room_last_message_fn=update_room_last_message_fn,
                new_id_fn=new_id_fn,
                utc_iso_fn=utc_iso_fn,
            )
            if generated_evt:
                generated_events.append(generated_evt)

        clear_run_state_fn(room_id)
        return generated_events

    entries: List[Dict[str, Any]] = []
    for idx, role in enumerate(active_roles, start=1):
        entry = _make_delegate_entry(
            room_id=room_id,
            question=question,
            role=role,
            idx=idx,
            total=total,
            run_id=run_id,
            trigger_event_id=trigger_event_id,
            rid=rid,
            new_id_fn=new_id_fn,
            utc_iso_fn=utc_iso_fn,
        )

        set_room_state_patch_fn(
            room_id,
            {
                "current_run_id": run_id,
                "current_run_status": "running",
                "current_delegate_role_id": entry["role_id"],
                "current_delegate_role_name": entry["role_name"],
                "current_delegate_index": idx,
                "current_delegate_total": total,
            },
        )

        append_room_event_fn(room_id, entry["delegate_evt"])
        entries.append(entry)

    results = _run_delegate_packet_pool(
        entries=entries,
        room_id=room_id,
        question=question,
        model_name=model_name,
        request_args=local_request_args,
        max_workers=worker_concurrency,
        stagger_seconds=stagger_seconds,
    )

    for result in results:
        generated_evt = _append_role_message_from_delegate_result(
            result=result,
            room_id=room_id,
            question=question,
            rid=rid,
            run_id=run_id,
            mode_used=mode_used,
            model_name=model_name,
            append_room_event_fn=append_room_event_fn,
            touch_room_updated_at_fn=touch_room_updated_at_fn,
            update_room_last_message_fn=update_room_last_message_fn,
            new_id_fn=new_id_fn,
            utc_iso_fn=utc_iso_fn,
        )
        if generated_evt:
            generated_events.append(generated_evt)

    clear_run_state_fn(room_id)
    return generated_events


def _run_supervisor_delegate_flow(
    *,
    room_id: str,
    question: str,
    active_roles: List[Dict[str, Any]],
    model_name: str,
    mode_used: str,
    run_id: str,
    plan_evt_id: str,
    rid: str,
    plan_summary: str,
    worker_request_args: Dict[str, Any],
    supervisor_request_args: Dict[str, Any],
    step_budget: Dict[str, Any],
    total: int,
    fs_context: Dict[str, Any],
    notebook_read_info: Dict[str, Any],
    memory_read_info: Dict[str, Any],
    memory_resume_info: Dict[str, Any],
    consume_step_budget_fn: Callable[[Dict[str, Any], int], Dict[str, Any]],
    budget_patch_fn: Callable[[Dict[str, Any]], Dict[str, Any]],
    interrupt_supervisor_run_fn: Callable[..., Any],
    set_room_state_patch_fn: Callable[[str, Dict[str, Any]], Any],
    append_room_event_fn: Callable[[str, Dict[str, Any]], Any],
    touch_room_updated_at_fn: Callable[[str], Any],
    update_room_last_message_fn: Callable[[str, str], Any],
    new_id_fn: Callable[[str], str],
    utc_iso_fn: Callable[[], str],
) -> Dict[str, Any]:
    delegate_events: List[Dict[str, Any]] = []
    role_message_events: List[Dict[str, Any]] = []
    delegate_packets: List[Dict[str, Any]] = []

    worker_concurrency = _get_worker_concurrency(
        worker_request_args,
        supervisor_request_args,
        total=len(active_roles),
    )
    stagger_seconds = _get_worker_stagger_seconds(worker_request_args, supervisor_request_args)

    if worker_concurrency <= 1:
        for idx, role in enumerate(active_roles, start=1):
            if _runtime_stop_requested(room_id=room_id, run_id=run_id):
                _mark_runtime_stop_observed(
                    room_id=room_id,
                    run_id=run_id,
                    set_room_state_patch_fn=set_room_state_patch_fn,
                    utc_iso_fn=utc_iso_fn,
                )
                return {
                    "interrupted": True,
                    "result": {
                        "status": "aborted",
                        "message": "room runtime stopped",
                        "run_id": run_id,
                        "delegate_events": delegate_events,
                        "role_message_events": role_message_events,
                        "delegate_packets": delegate_packets,
                        "step_budget": step_budget,
                    },
                }

            step_budget = consume_step_budget_fn(step_budget, 1)
            _apply_budget_to_request_args(supervisor_request_args, step_budget)

            if step_budget["budget_exhausted"]:
                checkpoint_summary = f"budget exhausted before delegate {idx} of {total}"
                interrupted = interrupt_supervisor_run_fn(
                    room_id=room_id,
                    rid=rid,
                    run_id=run_id,
                    trigger_event_id=plan_evt_id,
                    question=question,
                    phase="delegating",
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
                    clear_run_state_fn=lambda rid_: set_room_state_patch_fn(
                        rid_,
                        {
                            "current_delegate_role_id": "",
                            "current_delegate_role_name": "",
                            "current_delegate_index": 0,
                            "current_delegate_total": 0,
                        },
                    ),
                    new_id_fn=new_id_fn,
                    utc_iso_fn=utc_iso_fn,
                )
                return {"interrupted": True, "result": interrupted}

            entry = _make_delegate_entry(
                room_id=room_id,
                question=question,
                role=role,
                idx=idx,
                total=total,
                run_id=run_id,
                trigger_event_id=plan_evt_id,
                rid=rid,
                plan_summary=plan_summary,
                new_id_fn=new_id_fn,
                utc_iso_fn=utc_iso_fn,
            )

            set_room_state_patch_fn(
                room_id,
                {
                    "current_run_id": run_id,
                    "current_run_status": "running",
                    "current_delegate_role_id": entry["role_id"],
                    "current_delegate_role_name": entry["role_name"],
                    "current_delegate_index": idx,
                    "current_delegate_total": total,
                    **budget_patch_fn(step_budget),
                },
            )

            append_room_event_fn(room_id, entry["delegate_evt"])
            delegate_events.append(entry["delegate_evt"])

            result = _run_delegate_packet_single(
                entry=entry,
                room_id=room_id,
                question=question,
                model_name=model_name,
                request_args=worker_request_args,
            )

            if _runtime_stop_requested(room_id=room_id, run_id=run_id):
                _mark_runtime_stop_observed(
                    room_id=room_id,
                    run_id=run_id,
                    set_room_state_patch_fn=set_room_state_patch_fn,
                    utc_iso_fn=utc_iso_fn,
                )
                return {
                    "interrupted": True,
                    "result": {
                        "status": "aborted",
                        "message": "room runtime stopped",
                        "run_id": run_id,
                        "delegate_events": delegate_events,
                        "role_message_events": role_message_events,
                        "delegate_packets": delegate_packets,
                        "step_budget": step_budget,
                    },
                }
            
            role_msg_evt = _append_role_message_from_delegate_result(
                result=result,
                room_id=room_id,
                question=question,
                rid=rid,
                run_id=run_id,
                mode_used=mode_used,
                model_name=model_name,
                append_room_event_fn=append_room_event_fn,
                touch_room_updated_at_fn=touch_room_updated_at_fn,
                update_room_last_message_fn=update_room_last_message_fn,
                new_id_fn=new_id_fn,
                utc_iso_fn=utc_iso_fn,
            )
            if role_msg_evt:
                role_message_events.append(role_msg_evt)

            delegate_packets.append(_build_delegate_packet_from_result(result=result, question=question))

        set_room_state_patch_fn(
            room_id,
            {
                "current_run_id": run_id,
                "current_run_status": "running",
                "current_delegate_role_id": "",
                "current_delegate_role_name": "",
                "current_delegate_index": 0,
                "current_delegate_total": 0,
                **budget_patch_fn(step_budget),
            },
        )

        return {
            "interrupted": False,
            "delegate_events": delegate_events,
            "role_message_events": role_message_events,
            "delegate_packets": delegate_packets,
            "step_budget": step_budget,
        }

    entries: List[Dict[str, Any]] = []
    interrupted_idx: Optional[int] = None

    for idx, role in enumerate(active_roles, start=1):
        step_budget = consume_step_budget_fn(step_budget, 1)
        _apply_budget_to_request_args(supervisor_request_args, step_budget)

        if step_budget["budget_exhausted"]:
            interrupted_idx = idx
            break

        entry = _make_delegate_entry(
            room_id=room_id,
            question=question,
            role=role,
            idx=idx,
            total=total,
            run_id=run_id,
            trigger_event_id=plan_evt_id,
            rid=rid,
            plan_summary=plan_summary,
            new_id_fn=new_id_fn,
            utc_iso_fn=utc_iso_fn,
        )

        set_room_state_patch_fn(
            room_id,
            {
                "current_run_id": run_id,
                "current_run_status": "running",
                "current_delegate_role_id": entry["role_id"],
                "current_delegate_role_name": entry["role_name"],
                "current_delegate_index": idx,
                "current_delegate_total": total,
                **budget_patch_fn(step_budget),
            },
        )

        append_room_event_fn(room_id, entry["delegate_evt"])
        delegate_events.append(entry["delegate_evt"])
        entries.append(entry)

    if _runtime_stop_requested(room_id=room_id, run_id=run_id):
        _mark_runtime_stop_observed(
            room_id=room_id,
            run_id=run_id,
            set_room_state_patch_fn=set_room_state_patch_fn,
            utc_iso_fn=utc_iso_fn,
        )
        return {
            "interrupted": True,
            "result": {
                "status": "aborted",
                "message": "room runtime stopped",
                "run_id": run_id,
                "delegate_events": delegate_events,
                "role_message_events": role_message_events,
                "delegate_packets": delegate_packets,
                "step_budget": step_budget,
            },
        }

    role_message_events_by_idx: Dict[int, Dict[str, Any]] = {}
    stop_observed_during_results = {"value": False}

    def _append_worker_result_when_ready(result: Dict[str, Any]) -> None:
        if _runtime_stop_requested(room_id=room_id, run_id=run_id):
            stop_observed_during_results["value"] = True
            _mark_runtime_stop_observed(
                room_id=room_id,
                run_id=run_id,
                set_room_state_patch_fn=set_room_state_patch_fn,
                utc_iso_fn=utc_iso_fn,
            )
            return

        role_msg_evt = _append_role_message_from_delegate_result(
            result=result,
            room_id=room_id,
            question=question,
            rid=rid,
            run_id=run_id,
            mode_used=mode_used,
            model_name=model_name,
            append_room_event_fn=append_room_event_fn,
            touch_room_updated_at_fn=touch_room_updated_at_fn,
            update_room_last_message_fn=update_room_last_message_fn,
            new_id_fn=new_id_fn,
            utc_iso_fn=utc_iso_fn,
        )
        if role_msg_evt:
            idx_value = result.get("idx")
            try:
                idx_key = int(idx_value or 0)
            except Exception:
                idx_key = 0
            if idx_key > 0:
                role_message_events_by_idx[idx_key] = role_msg_evt

    results = _run_delegate_packet_pool(
        entries=entries,
        room_id=room_id,
        question=question,
        model_name=model_name,
        request_args=worker_request_args,
        max_workers=worker_concurrency,
        stagger_seconds=stagger_seconds,
        on_result_fn=_append_worker_result_when_ready,
    )

    if stop_observed_during_results["value"] or _runtime_stop_requested(room_id=room_id, run_id=run_id):
        _mark_runtime_stop_observed(
            room_id=room_id,
            run_id=run_id,
            set_room_state_patch_fn=set_room_state_patch_fn,
            utc_iso_fn=utc_iso_fn,
        )
        return {
            "interrupted": True,
            "result": {
                "status": "aborted",
                "message": "room runtime stopped",
                "run_id": run_id,
                "delegate_events": delegate_events,
                "role_message_events": [
                    role_message_events_by_idx[idx]
                    for idx in sorted(role_message_events_by_idx.keys())
                ],
                "delegate_packets": [
                    _build_delegate_packet_from_result(result=result, question=question)
                    for result in results
                ],
                "step_budget": step_budget,
            },
        }

    role_message_events = [
        role_message_events_by_idx[idx]
        for idx in sorted(role_message_events_by_idx.keys())
    ]

    delegate_packets = [
        _build_delegate_packet_from_result(result=result, question=question)
        for result in results
    ]

    if interrupted_idx is not None:
        checkpoint_summary = f"budget exhausted before delegate {interrupted_idx} of {total}"
        interrupted = interrupt_supervisor_run_fn(
            room_id=room_id,
            rid=rid,
            run_id=run_id,
            trigger_event_id=plan_evt_id,
            question=question,
            phase="delegating",
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
            clear_run_state_fn=lambda rid_: set_room_state_patch_fn(
                rid_,
                {
                    "current_delegate_role_id": "",
                    "current_delegate_role_name": "",
                    "current_delegate_index": 0,
                    "current_delegate_total": 0,
                },
            ),
            new_id_fn=new_id_fn,
            utc_iso_fn=utc_iso_fn,
        )
        return {"interrupted": True, "result": interrupted}

    set_room_state_patch_fn(
        room_id,
        {
            "current_run_id": run_id,
            "current_run_status": "running",
            "current_delegate_role_id": "",
            "current_delegate_role_name": "",
            "current_delegate_index": 0,
            "current_delegate_total": 0,
            **budget_patch_fn(step_budget),
        },
    )

    return {
        "interrupted": False,
        "delegate_events": delegate_events,
        "role_message_events": role_message_events,
        "delegate_packets": delegate_packets,
        "step_budget": step_budget,
    }


__all__ = [
    "_run_sequential_delegate_flow",
    "_run_supervisor_delegate_flow",
]

