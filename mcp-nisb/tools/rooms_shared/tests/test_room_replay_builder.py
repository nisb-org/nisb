from tools.rooms_shared import room_replay_builder as rb


def make_event(
    event_id,
    event_type,
    run_id,
    ts,
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


def test_build_room_run_replay_builds_phases_relations_and_prefers_relation_audit(monkeypatch):
    monkeypatch.setattr(rb, "_load_room_state", lambda room_id: {"supervisor_audit_relations": [{"id": "rel-1"}]})
    monkeypatch.setattr(
        rb,
        "_find_supervisor_audit_relation",
        lambda room_id, run_id, supervisor_event_id, final_event_id: {
            "type": "room_supervisor_audit_relation",
            "room_id": room_id,
            "run_id": run_id,
            "supervisor_event_id": supervisor_event_id,
            "final_event_id": final_event_id,
        },
    )
    monkeypatch.setattr(
        rb,
        "_build_state_supervisor_audit_snapshot",
        lambda state, run_id, supervisor_event, final_event: {"type": "snapshot", "run_id": run_id},
    )

    rows = [
        make_event(
            "evt-plan",
            "room.plan",
            "run_1",
            "2026-03-29T20:10:00+00:00",
            payload={"plan_summary": "先分派三位专家。", "role_name": "Supervisor"},
        ),
        make_event(
            "evt-route",
            "room.route",
            "run_1",
            "2026-03-29T20:10:01+00:00",
            payload={"target_role_name": "历史学专家", "route_mode": "default_reply_role"},
            trigger_event_id="evt-plan",
        ),
        make_event(
            "evt-delegate",
            "room.delegate",
            "run_1",
            "2026-03-29T20:10:02+00:00",
            payload={"target_role_name": "历史学专家", "delegate_index": 1, "delegate_total": 3},
            trigger_event_id="evt-plan",
        ),
        make_event(
            "evt-worker",
            "room.message",
            "run_1",
            "2026-03-29T20:10:10+00:00",
            payload={
                "sender_type": "role",
                "sender": "historian",
                "role_name": "历史学专家",
                "content": "边界之神在历史转型期常被重新解释。",
                "citations": [{"id": "web:1"}],
                "evidence_query": "边界之神 原型转移",
                "evidence_tools": ["nisb_search_web"],
                "evidence_result": {"citations": [{"id": "web:1"}]},
                "tool_calls": [{"name": "nisb_search_web", "tool_call_id": "call-1"}],
                "tool_results": [{"name": "nisb_search_web", "tool_call_id": "call-1"}],
            },
            trigger_event_id="evt-delegate",
        ),
        make_event(
            "evt-supervisor",
            "room.supervisor",
            "run_1",
            "2026-03-29T20:10:20+00:00",
            payload={"summary": "准备综合三位专家结果。", "role_name": "Supervisor", "status": "running"},
            trigger_event_id="evt-worker",
        ),
        make_event(
            "evt-final",
            "room.final",
            "run_1",
            "2026-03-29T20:10:30+00:00",
            payload={"response": "综合结论：边界象征了原型迁移。", "role_name": "Supervisor"},
            trigger_event_id="evt-supervisor",
        ),
    ]

    replay = rb._build_room_run_replay(
        room_id="room_1",
        rows=rows,
        state={
            "current_run_id": "",
            "current_run_status": "",
            "last_plan_at": "2026-03-29T20:10:00+00:00",
            "last_run_finished_at": "2026-03-29T20:10:30+00:00",
            "last_message_id": "evt-final",
            "last_message_at": "2026-03-29T20:10:30+00:00",
        },
        requested_run_id="run_1",
        include_tool_activity=True,
        include_evidence=True,
    )

    assert replay["type"] == "room_run_replay"
    assert replay["room_id"] == "room_1"
    assert replay["requested_run_id"] == "run_1"
    assert replay["requested_run_found"] is True
    assert replay["derived_run_id"] == "run_1"
    assert replay["run_id"] == "run_1"
    assert replay["status"] == "finished"
    assert replay["plan_event_id"] == "evt-plan"
    assert replay["supervisor_event_id"] == "evt-supervisor"
    assert replay["final_event_id"] == "evt-final"
    assert replay["delegate_total"] == 1
    assert replay["delegate_roles"] == ["历史学专家"]
    assert replay["plan_summary"] == "先分派三位专家。"
    assert replay["final_summary"] == "综合结论：边界象征了原型迁移。"
    assert replay["final_response"] == "综合结论：边界象征了原型迁移。"
    assert replay["audit"]["type"] == "room_supervisor_audit_relation"

    phases = replay["phases"]
    assert [item["event_id"] for item in phases] == [
        "evt-plan",
        "evt-route",
        "evt-delegate",
        "evt-worker",
        "evt-supervisor",
        "evt-final",
    ]
    assert phases[0]["phase"] == "planning"
    assert phases[1]["phase"] == "route"
    assert phases[2]["phase"] == "delegate"
    assert phases[3]["phase"] == "worker"
    assert phases[4]["phase"] in {"supervisor", "synthesizing"}
    assert phases[5]["phase"] == "final"
    assert phases[1]["visible"] is False
    assert phases[2]["title"] == "Delegate · 历史学专家"
    assert phases[3]["actor_label"] == "历史学专家"
    assert phases[3]["has_tool_activity"] is True
    assert phases[3]["has_evidence"] is True
    assert replay["tool_activity"][0]["event_id"] == "evt-worker"
    assert replay["evidence"][0]["event_id"] == "evt-worker"

    relations = replay["relations"]
    assert relations[0]["event_id"] == "evt-route"
    assert relations[-1]["trigger_event_id"] == "evt-supervisor"

    snapshot = replay["room_state_snapshot"]
    assert snapshot["last_message_id"] == "evt-final"
    assert snapshot["supervisor_audit_relations_count"] == 1


def test_build_room_run_replay_falls_back_to_latest_run_and_can_hide_tool_activity_and_evidence(monkeypatch):
    monkeypatch.setattr(rb, "_load_room_state", lambda room_id: {})
    monkeypatch.setattr(rb, "_find_supervisor_audit_relation", lambda **kwargs: None)
    monkeypatch.setattr(
        rb,
        "_build_state_supervisor_audit_snapshot",
        lambda state, run_id, supervisor_event, final_event: {"type": "snapshot", "run_id": run_id},
    )

    rows = [
        make_event(
            "evt-run1-plan",
            "room.plan",
            "run_1",
            "2026-03-29T20:10:00+00:00",
            payload={"plan_summary": "run1"},
        ),
        make_event(
            "evt-run1-final",
            "room.final",
            "run_1",
            "2026-03-29T20:10:05+00:00",
            payload={"response": "run1 final"},
            trigger_event_id="evt-run1-plan",
        ),
        make_event(
            "evt-run2-plan",
            "room.plan",
            "run_2",
            "2026-03-29T20:11:00+00:00",
            payload={"plan_summary": "run2"},
        ),
        make_event(
            "evt-run2-final",
            "room.final",
            "run_2",
            "2026-03-29T20:11:08+00:00",
            payload={
                "response": "run2 final",
                "tool_calls": [{"name": "nisb_search_web"}],
                "tool_results": [{"name": "nisb_search_web"}],
                "citations": [{"id": "web:2"}],
                "evidence_query": "run2 evidence",
                "evidence_tools": ["nisb_search_web"],
                "evidence_result": {"citations": [{"id": "web:2"}]},
            },
            trigger_event_id="evt-run2-plan",
        ),
    ]

    replay = rb._build_room_run_replay(
        room_id="room_1",
        rows=rows,
        state={},
        requested_run_id="run_missing",
        include_tool_activity=False,
        include_evidence=False,
    )

    assert replay["requested_run_id"] == "run_missing"
    assert replay["requested_run_found"] is False
    assert replay["derived_run_id"] == "run_2"
    assert replay["run_id"] == "run_2"
    assert replay["status"] == "finished"
    assert replay["tool_activity"] == []
    assert replay["evidence"] == []
    assert replay["audit"] == {"type": "snapshot", "run_id": "run_2"}
    assert replay["available_runs"][0]["run_id"] == "run_2"
    assert replay["available_runs"][1]["run_id"] == "run_1"

def test_build_room_run_replay_includes_skill_strategy_and_enabled_ids_in_room_state_snapshot(monkeypatch):
    monkeypatch.setattr(
        rb,
        "_load_room_state",
        lambda room_id: {
            "supervisor_skill_strategy": "builtin_only",
            "enabled_supervisor_skill_ids": ["skill.alpha"],
            "supervisor_audit_relations": [],
        },
    )
    monkeypatch.setattr(rb, "_find_supervisor_audit_relation", lambda **kwargs: None)
    monkeypatch.setattr(
        rb,
        "_build_state_supervisor_audit_snapshot",
        lambda state, run_id, supervisor_event, final_event: {"type": "snapshot", "run_id": run_id},
    )

    rows = [
        make_event(
            "evt-plan",
            "room.plan",
            "run_1",
            "2026-03-29T20:10:00+00:00",
            payload={"plan_summary": "plan"},
        ),
        make_event(
            "evt-supervisor",
            "room.supervisor",
            "run_1",
            "2026-03-29T20:10:10+00:00",
            payload={"summary": "supervisor"},
            trigger_event_id="evt-plan",
        ),
        make_event(
            "evt-final",
            "room.final",
            "run_1",
            "2026-03-29T20:10:20+00:00",
            payload={"response": "final"},
            trigger_event_id="evt-supervisor",
        ),
    ]

    replay = rb._build_room_run_replay(
        room_id="room_1",
        rows=rows,
        state={},
        requested_run_id="run_1",
        include_tool_activity=True,
        include_evidence=True,
    )

    snapshot = replay["room_state_snapshot"]
    assert snapshot["supervisor_skill_strategy"] == "builtin_only"
    assert snapshot["enabled_supervisor_skill_ids"] == ["skill.alpha"]

