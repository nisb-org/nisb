from tools.rooms_shared import room_runtime_reader as rr


def make_event(
    event_id,
    event_type,
    run_id="",
    ts="2026-03-29T20:10:00+00:00",
    payload=None,
):
    return {
        "id": event_id,
        "type": event_type,
        "run_id": run_id,
        "ts": ts,
        "payload": payload or {},
    }


def test_is_runtime_event_excludes_user_messages_and_accepts_generated_runtime_events():
    user_message = make_event(
        "evt-user",
        "room.message",
        run_id="run_1",
        payload={"sender_type": "user", "content": "hello"},
    )
    role_message = make_event(
        "evt-role",
        "room.message",
        run_id="run_1",
        payload={"sender_type": "role", "content": "reply"},
    )
    final_event = make_event("evt-final", "room.final", run_id="run_1")

    assert rr._is_runtime_event(user_message) is False
    assert rr._is_runtime_event(role_message) is True
    assert rr._is_runtime_event(final_event) is True


def test_collect_runtime_run_ids_and_derive_latest_run_id_ignore_non_runtime_items():
    rows = [
        make_event(
            "evt-user",
            "room.message",
            run_id="run_user",
            ts="2026-03-29T20:09:00+00:00",
            payload={"sender_type": "user"},
        ),
        make_event(
            "evt-plan-1",
            "room.plan",
            run_id="run_1",
            ts="2026-03-29T20:10:00+00:00",
        ),
        make_event(
            "evt-final-1",
            "room.final",
            run_id="run_1",
            ts="2026-03-29T20:10:59+00:00",
        ),
        make_event(
            "evt-plan-2",
            "room.plan",
            run_id="run_2",
            ts="2026-03-29T20:11:00+00:00",
        ),
    ]

    assert rr._collect_runtime_run_ids(rows) == ["run_2", "run_1"]
    assert rr._derive_latest_runtime_run_id(rows) == "run_2"


def test_filter_runtime_items_sorts_ascending_and_filters_by_run_id():
    rows = [
        make_event("evt-b", "room.final", run_id="run_1", ts="2026-03-29T20:11:00+00:00"),
        make_event("evt-a", "room.plan", run_id="run_1", ts="2026-03-29T20:10:00+00:00"),
        make_event("evt-c", "room.plan", run_id="run_2", ts="2026-03-29T20:12:00+00:00"),
    ]

    filtered = rr._filter_runtime_items(rows, run_id="run_1")

    assert [item["id"] for item in filtered] == ["evt-a", "evt-b"]
    assert all(item["run_id"] == "run_1" for item in filtered)


def test_slice_after_event_id_returns_items_after_match_and_reports_missing_marker():
    rows = [
        make_event("evt-1", "room.plan", run_id="run_1", ts="2026-03-29T20:10:00+00:00"),
        make_event("evt-2", "room.delegate", run_id="run_1", ts="2026-03-29T20:10:01+00:00"),
        make_event("evt-3", "room.final", run_id="run_1", ts="2026-03-29T20:10:02+00:00"),
    ]

    sliced = rr._slice_after_event_id(rows, after_event_id="evt-2")
    missing = rr._slice_after_event_id(rows, after_event_id="evt-missing")

    assert sliced["after_event_found"] is True
    assert [item["id"] for item in sliced["items"]] == ["evt-3"]

    assert missing["after_event_found"] is False
    assert [item["id"] for item in missing["items"]] == ["evt-1", "evt-2", "evt-3"]

def test_build_recent_runtime_summary_prefers_delegate_target_role_name_and_plan_event_summary():
    rows = [
        make_event(
            "evt-plan",
            "room.plan",
            run_id="run_1",
            ts="2026-03-29T20:10:00+00:00",
            payload={"plan_summary": "先分派三位专家。"},
        ),
        make_event(
            "evt-delegate",
            "room.delegate",
            run_id="run_1",
            ts="2026-03-29T20:10:01+00:00",
            payload={"target_role_name": "历史学专家"},
        ),
        make_event(
            "evt-supervisor",
            "room.supervisor",
            run_id="run_1",
            ts="2026-03-29T20:10:10+00:00",
            payload={"phase": "synthesizing", "summary": "准备综合结果。"},
        ),
        make_event(
            "evt-final",
            "room.final",
            run_id="run_1",
            ts="2026-03-29T20:10:20+00:00",
            payload={"response": "综合结论。"},
        ),
    ]

    summary = rr._build_recent_runtime_summary(rows, run_id="run_1")

    assert summary["run_id"] == "run_1"
    assert summary["current_stage"] == "final"
    assert summary["supervisor_phase"] == "synthesizing"
    assert summary["delegate_count"] == 1
    assert summary["role_names"] == ["历史学专家"]
    assert summary["plan_summary"] == "先分派三位专家。"
    assert summary["final_response"] == "综合结论。"
    assert summary["latest_message"] == "综合结论。"


def test_flatten_supervisor_nested_tool_activity_collects_all_nested_sections():
    evt = make_event(
        "evt-supervisor",
        "room.supervisor",
        run_id="run_1",
        ts="2026-03-29T20:10:00+00:00",
        payload={
            "supervisor_fs_read": {
                "status": "success",
                "tool_calls": [{"tool_call_id": "call-fs-read"}],
                "tool_results": [{"tool_call_id": "call-fs-read"}],
            },
            "supervisor_notebook_write": {
                "status": "disabled",
                "tool_calls": [{"tool_call_id": "call-notebook"}],
                "tool_results": [{"tool_call_id": "call-notebook"}],
            },
            "supervisor_fs_actions": [
                {
                    "tool_calls": [{"tool_call_id": "call-fs-action"}],
                    "tool_results": [{"tool_call_id": "call-fs-action"}],
                }
            ],
        },
    )

    flattened = rr._flatten_supervisor_nested_tool_activity(evt)
    sections = rr._extract_supervisor_audit_sections(evt)

    assert rr._event_has_supervisor_nested_audit(evt) is True
    assert sections["supervisor_fs_read"]["status"] == "success"
    assert sections["supervisor_notebook_write"]["status"] == "disabled"
    assert len(sections["supervisor_fs_actions"]) == 1
    assert [row["tool_call_id"] for row in flattened["tool_calls"]] == [
        "call-fs-read",
        "call-notebook",
        "call-fs-action",
    ]
    assert [row["tool_call_id"] for row in flattened["tool_results"]] == [
        "call-fs-read",
        "call-notebook",
        "call-fs-action",
    ]

