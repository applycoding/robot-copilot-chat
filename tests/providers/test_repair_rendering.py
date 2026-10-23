from robot_copilot.llm.base import IssueBrief, RepairContext, render_repair_message


def test_render_repair_message_includes_plan_and_issues():
    repair = RepairContext(
        attempt=1,
        previous_plan={"vehicle": "drone", "summary": "s", "actions": []},
        issues=[IssueBrief(code="altitude_high", action_index=0, message="too high")],
    )
    msg = render_repair_message(repair)
    assert "Previous plan JSON" in msg
    assert "altitude_high" in msg
    assert "too high" in msg
    assert "step 1" in msg
