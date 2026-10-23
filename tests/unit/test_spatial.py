from __future__ import annotations

from robot_copilot.validator import validate
from robot_copilot.validator.issues import IssueCode
from tests.helpers import plan_from_json


def test_substation_keepout(ctx):
    p = plan_from_json(
        {
            "vehicle": "drone",
            "summary": "s",
            "actions": [
                {"type": "takeoff", "altitude_m": 30},
                {"type": "goto", "xy": {"x_m": -140, "y_m": 120}, "altitude_m": 30},
                {"type": "return_home"},
            ],
        }
    )
    rep = validate(p, ctx)
    codes = {i.code for i in rep.issues}
    assert IssueCode.ENTERS_KEEP_OUT in codes or IssueCode.RTH_PATH_BLOCKED in codes


def test_valid_barn_goto(ctx):
    p = plan_from_json(
        {
            "vehicle": "drone",
            "summary": "s",
            "actions": [
                {"type": "takeoff", "altitude_m": 30},
                {"type": "goto", "place": "Barn"},
                {"type": "return_home"},
            ],
        }
    )
    rep = validate(p, ctx)
    assert rep.ok


def test_rover_stays_ground(ctx_rover):
    p = plan_from_json(
        {
            "vehicle": "rover",
            "summary": "s",
            "actions": [{"type": "goto", "place": "Barn"}, {"type": "return_home"}],
        }
    )
    rep = validate(p, ctx_rover)
    assert rep.ok
    assert rep.resolved
    assert all(leg.start.alt_m == 0 and leg.end.alt_m == 0 for leg in rep.resolved.legs)
