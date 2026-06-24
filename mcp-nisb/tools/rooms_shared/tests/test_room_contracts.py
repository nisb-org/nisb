import pytest

from tools.rooms_shared import room_contracts as rc


def test_ensure_request_id_preserves_existing_value():
    args = {"request_id": "req_existing_123"}
    rid = rc.ensure_request_id(args)

    assert rid == "req_existing_123"
    assert args["request_id"] == "req_existing_123"


def test_ensure_request_id_populates_missing_request_id():
    args = {}
    rid = rc.ensure_request_id(args)

    assert rid == args["request_id"]
    assert rid.startswith("req_")
    assert len(rid) > 8


def test_require_safe_id_accepts_safe_value_and_rejects_invalid_values():
    assert rc.require_safe_id("room_id", "room_123.safe-value") == "room_123.safe-value"

    with pytest.raises(ValueError, match="room_id is required"):
        rc.require_safe_id("room_id", "")

    with pytest.raises(ValueError, match="room_id is unsafe"):
        rc.require_safe_id("room_id", "../room_1")


def test_normalize_focus_root_normalizes_slashes_and_rejects_parent_traversal():
    normalized = rc.normalize_focus_root(r"//agent_files\\books///信息论/测试//")
    assert normalized == "agent_files/books/信息论/测试"

    with pytest.raises(ValueError, match="focus_root is unsafe"):
        rc.normalize_focus_root("agent_files/../secrets")


def test_as_bool_supports_common_boolean_spellings():
    assert rc.as_bool(True) is True
    assert rc.as_bool("true") is True
    assert rc.as_bool("on") is True
    assert rc.as_bool("0", True) is False
    assert rc.as_bool("off", True) is False
    assert rc.as_bool("unknown", True) is True


def test_normalize_role_slug_and_default_trigger_policy_are_stable():
    slug = rc.normalize_role_slug("历史学 专家!!")
    policy = rc.default_trigger_policy(name="历史学专家", slug=slug)

    assert slug == "role"
    assert policy["mention_names"] == ["@role", "@历史学专家"]
    assert policy["respond_on_plain_message"] is False
    assert policy["participate_in_orchestration"] is True


def test_default_room_state_contains_runtime_and_workspace_boundary_defaults():
    state = rc.default_room_state()

    assert state["inherit_workspace_context"] is True
    assert state["inherit_focus_root"] is True
    assert state["current_run_id"] == ""
    assert state["current_run_status"] == ""
    assert state["last_supervisor_fs_read_scope"] == "minimal"
    assert state["mcp_overrides"]["fs_read_enabled"] is False
    assert state["mcp_overrides"]["notebook_write_enabled"] is False
    assert state["mcp_overrides"]["notebook_dir"] == "_room_supervisor_notebooks"
    assert isinstance(state["updated_at"], str)
    assert "T" in state["updated_at"]


