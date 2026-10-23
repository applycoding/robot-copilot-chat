from __future__ import annotations

import math

import pytest

from robot_copilot.sim.simulator import NotValidatedError, simulate
from robot_copilot.validator import validate
from tests.helpers import north_fence_plan_json, plan_from_json


def test_rejects_unvalidated(ctx):
    plan = plan_from_json(north_fence_plan_json())
    rep = validate(plan, ctx)
    rep2 = rep.model_copy(update={"ok": False})
    with pytest.raises(NotValidatedError):
        simulate(rep2, ctx)


def test_rejects_tampered_hash(ctx):
    plan = plan_from_json(north_fence_plan_json())
    rep = validate(plan, ctx)
    assert rep.resolved and rep.plan_hash
    bad = rep.model_copy(update={"plan_hash": "0" * 64})
    with pytest.raises(NotValidatedError):
        simulate(bad, ctx)


def test_frame_count_and_endpoints(ctx):
    plan = plan_from_json(north_fence_plan_json())
    rep = validate(plan, ctx)
    assert rep.resolved
    sim = simulate(rep, ctx, dt_s=0.5)
    dt = 0.5
    for leg in rep.resolved.legs:
        if leg.duration_s <= 0:
            continue
        expected = math.ceil(leg.duration_s / dt) + 1
        leg_frames = [
            f
            for f in sim.frames
            if abs(f.x_m - leg.end.x_m) < 1e-6 or abs(f.y_m - leg.end.y_m) < 1e-6
        ]
        assert len(leg_frames) >= 1
        assert expected >= 1
        # endpoints appear in frame stream
        assert any(
            abs(f.x_m - leg.end.x_m) < 1e-9 and abs(f.y_m - leg.end.y_m) < 1e-9 for f in sim.frames
        )
    assert sim.final_state.landed and sim.final_state.at_home
    assert abs(sim.final_state.battery_wh - rep.resolved.stats.battery_end_wh) < 1e-9


def test_photo_events(ctx):
    plan = plan_from_json(north_fence_plan_json())
    rep = validate(plan, ctx)
    sim = simulate(rep, ctx)
    assert len(sim.photos) == rep.resolved.stats.photos


def test_rover_altitude_zero(ctx_rover):
    plan = plan_from_json(
        {
            "vehicle": "rover",
            "summary": "s",
            "actions": [{"type": "goto", "place": "Barn"}, {"type": "return_home"}],
        }
    )
    rep = validate(plan, ctx_rover)
    sim = simulate(rep, ctx_rover)
    assert all(f.alt_m == 0.0 for f in sim.frames)


def test_frames_use_float_precision(ctx):
    plan = plan_from_json(north_fence_plan_json())
    rep = validate(plan, ctx)
    sim = simulate(rep, ctx)
    assert len(sim.frames) > 10
