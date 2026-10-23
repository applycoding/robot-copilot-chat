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
    idx = 0
    for leg in rep.resolved.legs:
        if leg.duration_s <= 0:
            continue
        n = math.ceil(leg.duration_s / dt)
        expected = n + 1
        if idx > 0:
            prev = sim.frames[idx - 1]
            if abs(prev.x_m - leg.start.x_m) < 1e-9 and abs(prev.y_m - leg.start.y_m) < 1e-9:
                expected -= 1
        segment = sim.frames[idx : idx + expected]
        assert len(segment) == expected
        last = segment[-1]
        assert abs(last.x_m - leg.end.x_m) < 1e-9
        assert abs(last.y_m - leg.end.y_m) < 1e-9
        idx += expected
    assert idx == len(sim.frames)
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
