from __future__ import annotations

import random

from robot_copilot.sim.simulator import simulate
from robot_copilot.validator import validate
from tests.helpers import load_ctx, plan_from_json
from tests.property.generators import constructive_valid_mission, fuzz_plan


def test_fuzz_deterministic_json():
    rng = random.Random(20261023)
    ctx = load_ctx()
    for _ in range(200):
        data = fuzz_plan(rng)
        try:
            plan = plan_from_json(data)
        except Exception:
            continue
        j1 = validate(plan, ctx).model_dump_json()
        j2 = validate(plan, ctx).model_dump_json()
        assert j1 == j2


def test_constructive_validates():
    rng = random.Random(20261024)
    ok_count = 0
    for _ in range(60):
        data = constructive_valid_mission(rng)
        plan = plan_from_json(data)
        ctx = load_ctx(battery_pct=rng.randint(50, 100))
        rep = validate(plan, ctx)
        if rep.ok:
            ok_count += 1
            sim = simulate(rep, ctx)
            assert sim.final_state.at_home
            assert sim.final_state.landed
    assert ok_count >= 50
