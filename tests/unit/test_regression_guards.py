from __future__ import annotations

from robot_copilot.validator import validate
from robot_copilot.validator.explain import describe_plan
from tests.helpers import load_ctx, plan_from_json


def test_rover_fly_to_pond_at_altitude_issues(client):
    r = client.post(
        "/api/chat",
        json={"message": "fly to the pond at 30 m", "vehicle": "rover"},
    )
    assert r.status_code == 200
    mission = r.json()["mission"]
    assert mission["status"] == "invalid"
    codes = {i["code"] for i in mission["issues"]}
    assert "unsupported_action_for_vehicle" in codes
    assert "altitude_on_ground_vehicle" in codes


def test_battery_insufficient_includes_end_wh_param(client):
    r = client.post(
        "/api/chat",
        json={"message": "patrol the perimeter four times", "battery_pct": 40},
    )
    assert r.status_code == 200
    mission = r.json()["mission"]
    assert mission["status"] == "invalid"
    batt = [i for i in mission["issues"] if i["code"] == "battery_insufficient"]
    assert batt
    assert "projected end" in batt[0]["message"]
    assert any(p[0] == "end_wh" for p in batt[0].get("params", []))


def test_rover_summary_wording():
    ctx = load_ctx("rover", 100)
    plan = plan_from_json(
        {
            "vehicle": "rover",
            "summary": "pond",
            "actions": [{"type": "goto", "place": "Pond"}, {"type": "return_home"}],
        }
    )
    rep = validate(plan, ctx)
    assert rep.ok and rep.resolved
    text = describe_plan(rep.resolved, ctx.site)
    assert "Visit Pond" in text
    assert "dock" in text
    assert "return home and land" not in text
