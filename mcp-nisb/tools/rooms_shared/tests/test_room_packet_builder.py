from tools.rooms_shared import room_packet_builder as pb


FORMAL_KEYS = {
    "conv_id",
    "request_id",
    "rag_mode",
    "mcp_overrides",
    "mode_used",
    "rss_evidence",
    "market_evidence",
    "evidence_query",
    "evidence_tools",
    "evidence_result",
    "qa_id",
    "group_id",
    "citations",
    "response",
    "status",
    "message",
    "tool_calls",
    "tool_results",
}


def test_ensure_formal_packet_enforces_formal_keys_and_non_empty_success_response():
    packet = pb._ensure_formal_packet(
        conv_id="room_1",
        request_id="req_1",
        rag_mode="invalid-mode",
        response="",
        status="success",
        message="room post processed",
        tool_calls=[],
        tool_results=[],
    )

    assert set(packet.keys()) == FORMAL_KEYS
    assert packet["conv_id"] == "room_1"
    assert packet["request_id"] == "req_1"
    assert packet["rag_mode"] == "off"
    assert packet["mode_used"] == "off"
    assert packet["status"] == "success"
    assert packet["message"] == "room post processed"
    assert packet["response"] == "room post processed"
    assert packet["evidence_query"] == "room post processed"
    assert packet["evidence_result"]["evidence_query"] == "room post processed"
    assert "result" not in packet


def test_normalize_tool_activity_lists_backfills_tool_names_from_calls():
    tool_calls = [
        {
            "function": {"name": "supervisor_fs_read"},
            "toolCallId": "call-1",
        }
    ]
    tool_results = [
        {
            "tool_call_id": "call-1",
            "payload": {"status": "success"},
        }
    ]

    calls, results = pb._normalize_tool_activity_lists(tool_calls, tool_results)

    assert calls[0]["name"] == "nisb_supervisor_fs_read"
    assert calls[0]["tool_name"] == "nisb_supervisor_fs_read"
    assert calls[0]["tool_call_id"] == "call-1"
    assert results[0]["name"] == "nisb_supervisor_fs_read"
    assert results[0]["tool_name"] == "nisb_supervisor_fs_read"
    assert results[0]["tool_call_id"] == "call-1"


def test_bridge_chat_result_preserves_tool_results_and_appends_room_bridge_result():
    chat_res = {
        "conv_id": "chat_conv_9",
        "request_id": "req_inner",
        "rag_mode": "cite",
        "mode_used": "web",
        "response": "inner answer",
        "status": "success",
        "message": "ok",
        "tool_calls": [{"name": "nisb_search_web"}],
        "tool_results": [{"type": "search_result", "count": 2}],
        "citations": [{"id": "web:1"}],
    }

    packet = pb._bridge_chat_result(
        room_id="room_1",
        question="什么是边界之神？",
        request_id="req_outer",
        fallback_mode="off",
        mcp_overrides={},
        chat_res=chat_res,
    )

    assert set(packet.keys()) == FORMAL_KEYS
    assert packet["conv_id"] == "room_1"
    assert packet["request_id"] == "req_inner"
    assert packet["rag_mode"] == "cite"
    assert packet["mode_used"] == "web"
    assert packet["response"] == "inner answer"
    assert packet["evidence_query"] == "什么是边界之神？"
    assert packet["evidence_tools"] == ["nisb_chat_orchestrate"]
    assert packet["evidence_result"]["chat_conv_id"] == "chat_conv_9"
    assert packet["tool_results"][0]["type"] == "search_result"
    assert packet["tool_results"][-1]["type"] == "room_chat_bridge"
    assert packet["tool_results"][-1]["bridge"] == "nisb_chat_orchestrate"
    assert packet["tool_results"][-1]["chat_conv_id"] == "chat_conv_9"


def test_build_room_message_payload_normalizes_response_and_tool_activity():
    payload = pb._build_room_message_payload(
        sender="historian",
        sender_type="role",
        content="历史维度下的解释。",
        model="gpt-4o-mini",
        mode_used="ground",
        role_id="role_hist",
        role_name="历史学专家",
        avatar="📚",
        evidence_query="边界之神",
        tool_calls=[{"name": "fs_read", "id": "call-7"}],
        tool_results=[{"tool_call_id": "call-7", "status": "success"}],
    )

    assert payload["sender"] == "historian"
    assert payload["sender_type"] == "role"
    assert payload["content"] == "历史维度下的解释。"
    assert payload["response"] == "历史维度下的解释。"
    assert payload["mode_used"] == "ground"
    assert payload["role_id"] == "role_hist"
    assert payload["role_name"] == "历史学专家"
    assert payload["avatar"] == "📚"
    assert payload["evidence_query"] == "边界之神"
    assert payload["tool_calls"][0]["name"] == "nisb_supervisor_fs_read"
    assert payload["tool_results"][0]["name"] == "nisb_supervisor_fs_read"


