from tools.rooms_shared import room_orchestrator as ro


def make_delegate_packet(role_id, role_name, content):
    return {
        "role_id": role_id,
        "role_name": role_name,
        "content": content,
        "citations": [],
        "rss_evidence": [],
        "market_evidence": [],
        "evidence_query": "边界之神意味着什么？",
        "evidence_tools": [],
        "evidence_result": {"citations": []},
        "tool_calls": [],
        "tool_results": [],
    }


def make_distinct_delegate_packets():
    return [
        make_delegate_packet(
            "historian",
            "历史学专家",
            (
                "边界之神常在历史转型期被重新解释。"
                "其功能是调停秩序与越界。"
                "这种象征变化往往出现在旧制度松动之后。"
            ),
        ),
        make_delegate_packet(
            "anthropologist",
            "人类学专家",
            (
                "仪式中的边界象征用于处理污秽与净化。"
                "共同体通过阈限仪式重建身份。"
                "边界并非静态墙壁，而是可被反复穿越的社会装置。"
            ),
        ),
    ]


def first_target_texts_by_role(novelty_guard):
    texts = []
    for row in novelty_guard.get("targets_by_role", []):
        targets = list(row.get("targets") or [])
        if targets:
            texts.append(str(targets[0].get("text") or "").strip())
    return [text for text in texts if text]


def test_needs_supervisor_repair_detects_delegate_dump_and_process_report():
    delegate_dump = (
        "下面是完整复述各worker的回答内容：\n"
        "## 历史学专家\n"
        "边界之神常在历史转型期被重新解释。"
    )
    process_report = (
        "我已完成本轮 supervisor 综合。\n"
        "综合回答：边界象征了原型迁移。"
    )
    normal_answer = (
        "边界象征了原型迁移，同时反映了共同体对阈限秩序的重新组织。"
    )

    assert ro._needs_supervisor_repair(delegate_dump) is True
    assert ro._needs_supervisor_repair(process_report) is True
    assert ro._needs_supervisor_repair(normal_answer) is False


def test_strip_trailing_ungrounded_disclaimer_removes_tail_note():
    raw = (
        "综合结论：边界象征了原型迁移。\n"
        "如果文件中有具体论述，请告诉我，我可以更精确地引用。"
    )

    assert ro._looks_like_ungrounded_tail_disclaimer(raw) is True

    trimmed = ro._strip_trailing_ungrounded_disclaimer(raw)

    assert trimmed == "综合结论：边界象征了原型迁移。"
    assert "更精确地引用" not in trimmed
    assert ro._looks_like_ungrounded_tail_disclaimer(trimmed) is False


def test_build_supervisor_synthesis_fallback_returns_non_empty_non_report_text():
    packets = make_distinct_delegate_packets()

    text = ro._build_supervisor_synthesis_fallback(
        question="边界之神意味着什么？",
        rows=packets,
    )

    assert text
    assert "边界之神意味着什么" in text
    assert ro._needs_supervisor_repair(text) is False
    assert "如果文件中有具体论述" not in text
    assert "我已完成本轮 supervisor 综合" not in text


def test_build_delegate_novelty_guard_generates_targets_for_multiple_roles():
    packets = make_distinct_delegate_packets()

    novelty_guard = ro._build_delegate_novelty_guard(
        question="边界之神意味着什么？",
        delegate_packets=packets,
        max_targets_per_role=2,
    )

    assert novelty_guard["type"] == "room_supervisor_novelty_guard"
    assert novelty_guard["summary"]["role_count"] == 2
    assert novelty_guard["summary"]["roles_with_targets"] == 2
    assert novelty_guard["summary"]["target_count"] >= 2
    assert len(novelty_guard["targets_by_role"]) == 2

    for row in novelty_guard["targets_by_role"]:
        assert row["role_id"]
        assert row["role_name"]
        assert len(list(row.get("targets") or [])) >= 1


def test_evaluate_supervisor_novelty_coverage_distinguishes_high_and_low_coverage():
    packets = make_distinct_delegate_packets()
    novelty_guard = ro._build_delegate_novelty_guard(
        question="边界之神意味着什么？",
        delegate_packets=packets,
        max_targets_per_role=2,
    )

    target_texts = first_target_texts_by_role(novelty_guard)
    assert len(target_texts) == 2

    high_coverage_text = f"{target_texts[0]}。{target_texts[1]}。"
    high_coverage = ro._evaluate_supervisor_novelty_coverage(
        final_text=high_coverage_text,
        novelty_guard=novelty_guard,
    )

    assert high_coverage["summary"]["covered_role_count"] == 2
    assert high_coverage["summary"]["matched_target_count"] >= 2
    assert ro._needs_supervisor_novelty_repair(
        novelty_guard=novelty_guard,
        coverage=high_coverage,
    ) is False



def test_build_supervisor_attribution_tool_result_links_sentences_to_roles():
    packets = make_distinct_delegate_packets()
    final_text = (
        "边界之神常在历史转型期被重新解释。"
        "仪式中的边界象征用于处理污秽与净化。"
    )

    result = ro._build_supervisor_attribution_tool_result(
        question="边界之神意味着什么？",
        final_text=final_text,
        delegate_packets=packets,
    )

    assert result["type"] == "room_supervisor_attribution"
    assert result["summary"]["sentence_count"] >= 2
    assert result["summary"]["attributable_sentence_count"] >= 2
    assert result["summary"]["attributed_sentence_count"] >= 2
    assert result["summary"]["role_count"] == 2

    role_names = {row["role_name"] for row in result["roles"]}
    assert "历史学专家" in role_names
    assert "人类学专家" in role_names

    body_rows = [row for row in result["sentences"] if row["kind"] == "body"]
    assert len(body_rows) >= 2
    assert body_rows[0]["attributed"] is True
    assert body_rows[1]["attributed"] is True
    assert body_rows[0]["top_sources"]
    assert body_rows[1]["top_sources"]


def test_select_best_supervisor_candidate_prefers_repair_when_structure_and_coverage_are_better():
    packets = make_distinct_delegate_packets()
    novelty_guard = ro._build_delegate_novelty_guard(
        question="边界之神意味着什么？",
        delegate_packets=packets,
        max_targets_per_role=2,
    )
    target_texts = first_target_texts_by_role(novelty_guard)

    initial_packet = {"response": "下面是完整复述各worker的回答内容：\n## 历史学专家\n边界之神常在历史转型期被重新解释。"}
    repair_packet = {"response": f"{target_texts[0]}。{target_texts[1]}。"}

    initial_text = initial_packet["response"]
    repair_text = repair_packet["response"]

    initial_coverage = ro._evaluate_supervisor_novelty_coverage(
        final_text=initial_text,
        novelty_guard=novelty_guard,
    )
    repair_coverage = ro._evaluate_supervisor_novelty_coverage(
        final_text=repair_text,
        novelty_guard=novelty_guard,
    )

    selected_packet, selected_text, selected_coverage, selected_source = ro._select_best_supervisor_candidate(
        initial_packet=initial_packet,
        initial_text=initial_text,
        initial_novelty_coverage=initial_coverage,
        repair_packet=repair_packet,
        repair_text=repair_text,
        repair_novelty_coverage=repair_coverage,
    )

    assert selected_source == "repair"
    assert selected_packet is repair_packet
    assert selected_text == repair_text
    assert selected_coverage == repair_coverage


def test_select_best_supervisor_candidate_keeps_initial_when_repair_is_worse():
    packets = make_distinct_delegate_packets()
    novelty_guard = ro._build_delegate_novelty_guard(
        question="边界之神意味着什么？",
        delegate_packets=packets,
        max_targets_per_role=2,
    )
    target_texts = first_target_texts_by_role(novelty_guard)

    initial_packet = {"response": f"{target_texts[0]}。{target_texts[1]}。"}
    repair_packet = {"response": "我已完成本轮 supervisor 综合。\n综合回答：边界象征了原型迁移。"}

    initial_text = initial_packet["response"]
    repair_text = repair_packet["response"]

    initial_coverage = ro._evaluate_supervisor_novelty_coverage(
        final_text=initial_text,
        novelty_guard=novelty_guard,
    )
    repair_coverage = ro._evaluate_supervisor_novelty_coverage(
        final_text=repair_text,
        novelty_guard=novelty_guard,
    )

    selected_packet, selected_text, selected_coverage, selected_source = ro._select_best_supervisor_candidate(
        initial_packet=initial_packet,
        initial_text=initial_text,
        initial_novelty_coverage=initial_coverage,
        repair_packet=repair_packet,
        repair_text=repair_text,
        repair_novelty_coverage=repair_coverage,
    )

    assert selected_source == "initial"
    assert selected_packet is initial_packet
    assert selected_text == initial_text
    assert selected_coverage == initial_coverage


def test_merge_tool_activity_groups_combines_all_normalized_activity(monkeypatch):
    monkeypatch.setattr(
        ro,
        "_normalize_tool_activity_lists",
        lambda tool_calls, tool_results: (list(tool_calls or []), list(tool_results or [])),
    )

    merged_tool_calls, merged_tool_results = ro._merge_tool_activity_groups(
        (
            [{"name": "nisb_search_web", "tool_call_id": "call-1"}],
            [{"name": "nisb_search_web", "tool_call_id": "call-1"}],
        ),
        (
            [{"name": "nisb_fs_read", "tool_call_id": "call-2"}],
            [{"name": "nisb_fs_read", "tool_call_id": "call-2"}],
        ),
        (
            [{"name": "nisb_notebook_write", "tool_call_id": "call-3"}],
            [{"name": "nisb_notebook_write", "tool_call_id": "call-3"}],
        ),
    )

    assert [row["name"] for row in merged_tool_calls] == [
        "nisb_search_web",
        "nisb_fs_read",
        "nisb_notebook_write",
    ]
    assert [row["name"] for row in merged_tool_results] == [
        "nisb_search_web",
        "nisb_fs_read",
        "nisb_notebook_write",
    ]
    assert len(merged_tool_calls) == 3
    assert len(merged_tool_results) == 3

