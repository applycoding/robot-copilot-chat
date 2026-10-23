from __future__ import annotations

import pytest

from robot_copilot.validator import validate
from robot_copilot.validator.issues import IssueCode
from tests.helpers import plan_from_json


def _plan(actions, vehicle="drone"):
    return plan_from_json({"vehicle": vehicle, "summary": "t", "actions": actions})


def test_vehicle_mismatch(ctx):
    p = _plan([{"type": "takeoff", "altitude_m": 30}, {"type": "return_home"}], vehicle="rover")
    rep = validate(p, ctx)
    assert any(i.code == IssueCode.VEHICLE_MISMATCH for i in rep.issues)


def test_takeoff_before_goto_sequence(ctx):
    p = _plan([{"type": "goto", "place": "Barn"}, {"type": "return_home"}])
    rep = validate(p, ctx)
    assert any(i.code == IssueCode.SEQUENCE for i in rep.issues)


def test_altitude_boundaries(ctx):
    for alt, code in [(9.9, IssueCode.ALTITUDE_LOW), (120.1, IssueCode.ALTITUDE_HIGH)]:
        p = _plan([{"type": "takeoff", "altitude_m": alt}, {"type": "return_home"}])
        rep = validate(p, ctx)
        assert any(i.code == code for i in rep.issues)
    p = _plan([{"type": "takeoff", "altitude_m": 10}, {"type": "return_home"}])
    assert validate(p, ctx).ok or not any(
        i.code == IssueCode.ALTITUDE_LOW for i in validate(p, ctx).issues
    )


def test_speed_and_hover_bounds(ctx):
    p = _plan(
        [
            {"type": "takeoff", "altitude_m": 30},
            {"type": "goto", "place": "Barn", "speed_mps": 15.01},
            {"type": "return_home"},
        ]
    )
    assert any(i.code == IssueCode.SPEED_HIGH for i in validate(p, ctx).issues)
    p2 = _plan(
        [
            {"type": "takeoff", "altitude_m": 30},
            {"type": "goto", "place": "Pond"},
            {"type": "hover", "seconds": 120.01},
            {"type": "return_home"},
        ]
    )
    assert any(i.code == IssueCode.HOVER_TOO_LONG for i in validate(p2, ctx).issues)


def test_too_many_actions(ctx):
    acts = [{"type": "takeoff", "altitude_m": 30}]
    acts += [{"type": "goto", "place": "Barn"}] * 39
    acts.append({"type": "return_home"})
    rep = validate(_plan(acts), ctx)
    assert any(i.code == IssueCode.TOO_MANY_ACTIONS for i in rep.issues)


def test_unknown_place_and_bad_index(ctx):
    p = _plan(
        [
            {"type": "takeoff", "altitude_m": 30},
            {"type": "goto", "place": "Nowhere"},
            {"type": "return_home"},
        ]
    )
    assert any(i.code == IssueCode.UNKNOWN_PLACE for i in validate(p, ctx).issues)
    p2 = _plan(
        [
            {"type": "takeoff", "altitude_m": 30},
            {"type": "goto", "place": "North Fence", "point_index": 99},
            {"type": "return_home"},
        ]
    )
    assert any(i.code == IssueCode.BAD_POINT_INDEX for i in validate(p2, ctx).issues)


def test_rover_takeoff_rejected(ctx_rover):
    p = _plan([{"type": "takeoff", "altitude_m": 30}, {"type": "return_home"}], vehicle="rover")
    rep = validate(p, ctx_rover)
    assert any(i.code == IssueCode.UNSUPPORTED_ACTION_FOR_VEHICLE for i in rep.issues)


@pytest.mark.parametrize(
    "state_action",
    [
        (
            [{"type": "takeoff", "altitude_m": 30}, {"type": "takeoff", "altitude_m": 20}],
            IssueCode.SEQUENCE,
        ),
        ([{"type": "takeoff", "altitude_m": 30}, {"type": "land"}], IssueCode.SEQUENCE),
    ],
)
def test_transition_violations(ctx, state_action):
    acts, code = state_action
    acts = [*list(acts), {"type": "return_home"}]
    rep = validate(_plan(acts), ctx)
    assert any(i.code == code for i in rep.issues)
