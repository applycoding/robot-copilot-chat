from __future__ import annotations

from robot_copilot.validator import validate
from robot_copilot.validator.issues import IssueCode, XYZ
from robot_copilot.validator.spatial import segment_keepouts_hit
from tests.helpers import plan_from_json


def test_segment_keepouts_hit_lists_every_zone_on_one_leg(ctx):
    start = XYZ(x_m=-140.0, y_m=120.0, alt_m=30.0)
    end = XYZ(x_m=150.0, y_m=90.0, alt_m=30.0)
    hits = segment_keepouts_hit(ctx.geometry, start, end)
    assert hits == ["Substation", "Beehives"]


def test_crossing_two_keepouts_yields_two_issue_codes(ctx):
    p = plan_from_json(
        {
            "vehicle": "drone",
            "summary": "s",
            "actions": [
                {"type": "takeoff", "altitude_m": 30},
                {"type": "goto", "xy": {"x_m": -140.0, "y_m": 120.0}, "altitude_m": 30},
                {"type": "goto", "xy": {"x_m": 150.0, "y_m": 90.0}, "altitude_m": 30},
                {"type": "return_home"},
            ],
        }
    )
    rep = validate(p, ctx)
    ko_codes = [i for i in rep.issues if i.code == IssueCode.ENTERS_KEEP_OUT]
    zones = {i.params[0][1] for i in ko_codes if i.params}
    assert zones == {"Substation", "Beehives"}


def test_substation_keepout_dedupes_keepout_code(ctx):
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
    ko_issues = [i for i in rep.issues if i.code == IssueCode.ENTERS_KEEP_OUT]
    assert len(ko_issues) == 1
    codes = {i.code for i in rep.issues}
    assert IssueCode.RTH_PATH_BLOCKED in codes


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
