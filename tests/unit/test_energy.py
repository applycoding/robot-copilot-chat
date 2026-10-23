from robot_copilot.validator import validate
from robot_copilot.validator.energy import climb_wh, move_wh, rth_wh
from robot_copilot.validator.issues import XYZ
from tests.helpers import load_ctx, north_fence_plan_json, plan_from_json


def test_move_wh_formula():
    ctx = load_ctx()
    d, v = 100.0, 8.0
    expected = (d / v) * ctx.vehicle.cruise_power_w / 3600
    assert abs(move_wh(d, v, ctx.vehicle) - expected) < 1e-9


def test_climb_wh_formula():
    ctx = load_ctx()
    dz = 30.0
    drone = ctx.vehicle
    expected = (
        drone.climb_wh_per_m * dz + drone.hover_power_w * (dz / drone.vertical_speed_mps) / 3600
    )
    assert abs(climb_wh(dz, drone) - expected) < 1e-9


def test_rth_wh_zero_at_home():
    ctx = load_ctx()
    home = XYZ(x_m=0, y_m=0, alt_m=0)
    assert rth_wh(home, "ground_home", ctx.vehicle, ctx.site.home) == 0.0


def test_north_fence_stats_oracle():
    ctx = load_ctx()
    plan = plan_from_json(north_fence_plan_json())
    rep = validate(plan, ctx)
    assert rep.resolved
    st = rep.resolved.stats
    assert abs(st.distance_m - 1105.342) < 1e-3
    assert abs(st.duration_s - 180.168) < 1e-3
    assert abs(st.energy_wh - 10.305) < 1e-3


def test_start_below_reserve():
    ctx = load_ctx(battery_pct=15)
    plan = plan_from_json(north_fence_plan_json())
    rep = validate(plan, ctx)
    assert not rep.ok
    assert any(i.code.value == "battery_insufficient" for i in rep.issues)
