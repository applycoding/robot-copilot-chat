from robot_copilot.validator import validate
from robot_copilot.validator.explain import TEMPLATES, describe_plan, explain_issue
from robot_copilot.validator.issues import IssueCode
from tests.helpers import load_ctx, north_fence_plan_json, plan_from_json

NORTH_FENCE_GOLDEN = (
    "Take off to 30 m, visit North Fence (3 points) taking 3 photos, "
    "then return home and land. 1.11 km, 3 min 0 s, uses 10.3 Wh of 90.0 Wh; "
    "ends with 79.7 Wh (reserve 18.0 Wh)."
)


def test_every_issue_code_has_template():
    for code in IssueCode:
        assert code in TEMPLATES
        msg, hint = explain_issue(code, None, {})
        assert msg
        assert hint


def test_step_wording():
    msg, _ = explain_issue(IssueCode.ALTITUDE_HIGH, 0, {"altitude_m": 150, "max": 120})
    assert "Step 1:" in msg


def test_describe_plan_north_fence():
    ctx = load_ctx()
    plan = plan_from_json(north_fence_plan_json())
    rep = validate(plan, ctx)
    assert rep.ok and rep.resolved
    text = describe_plan(rep.resolved, ctx.site)
    assert text == NORTH_FENCE_GOLDEN
