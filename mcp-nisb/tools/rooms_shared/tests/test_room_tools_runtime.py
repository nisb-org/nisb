from tools.rooms_shared import room_tools_runtime as rt


def make_event(
    event_id,
    event_type,
    run_id="",
    ts="2026-03-29T20:10:00+00:00",
    payload=None,
    trigger_event_id="",
):
    return {
        "id": event_id,
        "type": event_type,
        "run_id": run_id,
        "ts": ts,
        "trigger_event_id": trigger_event_id,
        "payload": payload or {},
    }


def patch_common_runtime(monkeypatch, rows=None, state=None):
    monkeypatch.setattr(rt, "get_basepath", lambda args: "/tmp/basepath")
    monkeypatch.setattr(rt, "uid_from_ctx_or_basepath", lambda basepath, args: "user_1")
    monkeypatch.setattr(rt, "ensure_room_exists", lambda room_id: {"room_id": room_id})
    monkeypatch.setattr(rt, "is_participant", lambda uid, meta: True)
    monkeypatch.setattr(rt, "load_room_events", lambda room_id: rows or [])
    monkeypatch.setattr(
        rt,
        "load_state_doc",
        lambda room_id: state or {"mcp_overrides": {"fs_read_enabled": False}},
    )
    monkeypatch.setattr(
        rt,
        "_normalize_room_state_for_output",
        lambda value: value if isinstance(value, dict) else {},
    )
    monkeypatch.setattr(rt, "_build_tool_result_item", lambda kind, **kwargs: {"type": kind, **kwargs})
    monkeypatch.setattr(rt, "_formal_envelope", lambda **kwargs: kwargs)


def test_nisb_room_events_recent_prefers_latest_runtime_run_when_requested_run_is_stale(monkeypatch):
    rows = [
        make_event(
            "evt-run1-plan",
            "room.plan",
            run_id="run_1",
            ts="2026-03-29T20:10:00+00:00",
        ),
        make_event(
            "evt-run1-final",
            "room.final",
            run_id="run_1",
            ts="2026-03-29T20:10:30+00:00",
        ),
        make_event(
            "evt-run2-plan",
            "room.plan",
            run_id="run_2",
            ts="2026-03-29T20:11:00+00:00",
        ),
    ]
    patch_common_runtime(monkeypatch, rows=rows)

    result = rt.nisb_room_events_recent(
        {
            "request_id": "req_1",
            "room_id": "room_1",
            "run_id": "run_1",
            "after_event_id": "evt-run1-final",
            "limit": 50,
        }
    )

    tool_result = result["tool_results"][0]

    assert result["request_id"] == "req_1"
    assert result["conv_id"] == "room_1"
    assert result["status"] == "success"
    assert result["message"] == "room runtime events loaded"
    assert tool_result["type"] == "room_runtime_events"
    assert tool_result["requested_run_id"] == "run_1"
    assert tool_result["derived_run_id"] == "run_2"
    assert tool_result["run_id"] == "run_1"
    assert tool_result["after_event_id"] == "evt-run1-final"
    assert tool_result["returned_count"] == 0
    assert tool_result["items"] == []


def test_nisb_room_events_recent_returns_empty_when_after_event_matches_latest(monkeypatch):
    rows = [
        make_event(
            "evt-plan",
            "room.plan",
            run_id="run_9",
            ts="2026-03-29T20:10:00+00:00",
        ),
        make_event(
            "evt-final",
            "room.final",
            run_id="run_9",
            ts="2026-03-29T20:10:30+00:00",
        ),
    ]
    patch_common_runtime(monkeypatch, rows=rows)

    result = rt.nisb_room_events_recent(
        {
            "request_id": "req_2",
            "room_id": "room_1",
            "run_id": "run_9",
            "after_event_id": "evt-final",
        }
    )

    tool_result = result["tool_results"][0]

    assert tool_result["run_id"] == "run_9"
    assert tool_result["after_event_found"] is True
    assert tool_result["latest_event_id"] == "evt-final"
    assert tool_result["returned_count"] == 0
    assert tool_result["has_more"] is False
    assert tool_result["items"] == []


def test_nisb_room_events_replay_wraps_replay_builder_output_in_formal_envelope(monkeypatch):
    patch_common_runtime(monkeypatch, rows=[])
    monkeypatch.setattr(
        rt,
        "_build_room_run_replay",
        lambda **kwargs: {
            "type": "room_run_replay",
            "room_id": kwargs["room_id"],
            "run_id": "run_7",
            "events": [{"id": "evt-1"}, {"id": "evt-2"}],
            "phases": [],
            "audit": {"type": "room_supervisor_audit_relation"},
        },
    )

    result = rt.nisb_room_events_replay(
        {
            "request_id": "req_3",
            "room_id": "room_1",
            "run_id": "run_7",
            "include_tool_activity": True,
            "include_evidence": True,
        }
    )

    tool_result = result["tool_results"][0]

    assert result["request_id"] == "req_3"
    assert result["conv_id"] == "room_1"
    assert result["status"] == "success"
    assert result["message"] == "room replay loaded"
    assert result["response"] == "Loaded room replay for run run_7 with 2 runtime events."
    assert tool_result["type"] == "room_run_replay"
    assert tool_result["room_id"] == "room_1"
    assert tool_result["run_id"] == "run_7"
    assert len(tool_result["events"]) == 2
    assert tool_result["audit"]["type"] == "room_supervisor_audit_relation"


def test_nisb_room_shared_recent_returns_room_items_contract(monkeypatch):
    monkeypatch.setattr(rt, "get_basepath", lambda args: "/tmp/basepath")
    monkeypatch.setattr(rt, "uid_from_ctx_or_basepath", lambda basepath, args: "user_1")
    monkeypatch.setattr(rt, "ensure_room_exists", lambda room_id: {"room_id": room_id})
    monkeypatch.setattr(rt, "is_participant", lambda uid, meta: True)
    monkeypatch.setattr(
        rt,
        "load_recent_room_events",
        lambda room_id, **kwargs: {
            "items": [{"id": "evt-1"}, {"id": "evt-2"}],
            "has_more": False,
            "next_cursor": {"before_event_id": "evt-1"},
            "source": "tail_window",
            "file_size": 2048,
            "window_start_offset": 0,
            "window_end_offset": 120,
            "selected_oldest_offset": 0,
            "selected_newest_offset": 120,
        },
    )
    monkeypatch.setattr(
        rt,
        "load_state_doc",
        lambda room_id: {"mcp_overrides": {"fs_read_enabled": False}},
    )
    monkeypatch.setattr(
        rt,
        "_normalize_room_state_for_output",
        lambda value: value if isinstance(value, dict) else {},
    )
    monkeypatch.setattr(rt, "_build_tool_result_item", lambda kind, **kwargs: {"type": kind, **kwargs})
    monkeypatch.setattr(rt, "_formal_envelope", lambda **kwargs: kwargs)

    result = rt.nisb_room_shared_recent(
        {
            "request_id": "req_4",
            "room_id": "room_1",
            "limit": 20,
            "order": "desc",
            "byte_budget": 409600,
            "relation_expand": True,
        }
    )

    tool_result = result["tool_results"][0]

    assert result["request_id"] == "req_4"
    assert result["conv_id"] == "room_1"
    assert result["status"] == "success"
    assert result["message"] == "room events loaded"
    assert result["response"] == "Loaded 2 room events."
    assert tool_result["type"] == "room_items"
    assert tool_result["returned_count"] == 2
    assert tool_result["limit"] == 20
    assert tool_result["order"] == "desc"
    assert tool_result["has_more"] is False
    assert tool_result["source"] == "tail_window"
    assert tool_result["items"][0]["id"] == "evt-1"
