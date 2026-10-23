from __future__ import annotations

import math

from robot_copilot.plan import (
    Goto,
    Hover,
    Land,
    MissionPlan,
    Photo,
    ReturnHome,
    Takeoff,
)
from robot_copilot.validator.context import ValidationContext
from robot_copilot.validator.energy import (
    climb_wh,
    descend_wh,
    hover_wh,
    move_wh,
    photo_leg_wh,
    reserve_wh,
    rth_wh,
)
from robot_copilot.validator.issues import XYZ, Leg, PlanStats, ResolvedPlan, ValidationIssue
from robot_copilot.validator.spatial import (
    rth_segment_blocked,
    segment_hits_keepout,
    segment_outside_fence,
)
from robot_copilot.validator.structure import _resolve_target
from robot_copilot.vehicles import DroneProfile


def build_resolved(plan: MissionPlan, ctx: ValidationContext) -> ResolvedPlan:
    veh = ctx.vehicle
    is_drone = isinstance(veh, DroneProfile)
    home = ctx.site.home
    hx, hy = home

    legs: list[Leg] = []
    state = "ground_home" if is_drone else "at_home"
    pos = XYZ(x_m=hx, y_m=hy, alt_m=0.0)
    cur_alt = 0.0
    battery = veh.battery_capacity_wh * ctx.battery_pct / 100.0
    reserve = reserve_wh(veh)
    total_dist = 0.0
    total_vert = 0.0
    total_dur = 0.0
    total_energy = 0.0
    photos = 0
    min_rth_margin = float("inf")

    def add_leg(
        action_index: int,
        kind: str,
        start: XYZ,
        end: XYZ,
        speed: float,
        dist: float,
        dur: float,
        energy: float,
    ) -> None:
        nonlocal \
            battery, \
            total_dist, \
            total_vert, \
            total_dur, \
            total_energy, \
            min_rth_margin, \
            pos, \
            cur_alt
        battery -= energy
        total_dist += dist if kind == "move" else 0.0
        total_vert += abs(end.alt_m - start.alt_m)
        total_dur += dur
        total_energy += energy
        rwh = rth_wh(end, state_after(kind, end, is_drone, home), veh, home)
        margin = battery - rwh - reserve
        min_rth_margin = min(min_rth_margin, margin)
        legs.append(
            Leg(
                action_index=action_index,
                kind=kind,  # type: ignore[arg-type]
                start=start,
                end=end,
                speed_mps=speed,
                distance_m=dist,
                duration_s=dur,
                energy_wh=energy,
                battery_after_wh=battery,
                rth_wh=rwh,
                rth_margin_wh=margin,
            )
        )
        pos = end
        cur_alt = end.alt_m

    def state_after(kind: str, end: XYZ, is_dr: bool, hm: tuple[float, float]) -> str:
        if is_dr:
            if end.alt_m <= 0 and math.hypot(end.x_m - hm[0], end.y_m - hm[1]) <= 2.0:
                return "ground_home"
            if end.alt_m <= 0:
                return "ground_away"
            return "air"
        if math.hypot(end.x_m - hm[0], end.y_m - hm[1]) <= 2.0:
            return "at_home"
        return "away"

    for idx, action in enumerate(plan.actions):
        if isinstance(action, Takeoff):
            assert is_drone
            drone = veh
            assert isinstance(drone, DroneProfile)
            target = XYZ(x_m=pos.x_m, y_m=pos.y_m, alt_m=action.altitude_m)
            dz = action.altitude_m - cur_alt
            dur = dz / drone.vertical_speed_mps if dz > 0 else 0.0
            e = climb_wh(dz, drone) if dz > 0 else 0.0
            add_leg(idx, "climb", pos, target, drone.vertical_speed_mps, abs(dz), dur, e)
            state = "air"
        elif isinstance(action, Goto):
            x, y, alt = _resolve_target(action, ctx, cur_alt, is_drone)
            speed = action.speed_mps if action.speed_mps is not None else veh.cruise_speed_mps
            if is_drone:
                drone = veh
                assert isinstance(drone, DroneProfile)
                if alt != cur_alt:
                    target = XYZ(x_m=pos.x_m, y_m=pos.y_m, alt_m=alt)
                    dz = abs(alt - cur_alt)
                    dur = dz / drone.vertical_speed_mps
                    if alt > cur_alt:
                        e = climb_wh(dz, drone)
                        add_leg(idx, "climb", pos, target, drone.vertical_speed_mps, dz, dur, e)
                    else:
                        e = descend_wh(dz, drone)
                        add_leg(idx, "descend", pos, target, drone.vertical_speed_mps, dz, dur, e)
                end = XYZ(x_m=x, y_m=y, alt_m=alt)
                dist = math.hypot(x - pos.x_m, y - pos.y_m)
                dur = dist / speed if dist > 0 else 0.0
                e = move_wh(dist, speed, veh)
                add_leg(idx, "move", pos, end, speed, dist, dur, e)
                state = "air"
            else:
                end = XYZ(x_m=x, y_m=y, alt_m=0.0)
                dist = math.hypot(x - pos.x_m, y - pos.y_m)
                dur = dist / speed if dist > 0 else 0.0
                e = move_wh(dist, speed, veh)
                add_leg(idx, "move", pos, end, speed, dist, dur, e)
                state = "at_home" if math.hypot(x - hx, y - hy) <= 2.0 else "away"
        elif isinstance(action, Hover):
            end = pos
            dur = action.seconds
            e = hover_wh(dur, veh)
            add_leg(idx, "hover", pos, end, 0.0, 0.0, dur, e)
        elif isinstance(action, Photo):
            e, dur = photo_leg_wh(veh)
            add_leg(idx, "photo", pos, pos, 0.0, 0.0, dur, e)
            photos += 1
        elif isinstance(action, Land):
            assert is_drone
            drone = veh
            assert isinstance(drone, DroneProfile)
            target = XYZ(x_m=pos.x_m, y_m=pos.y_m, alt_m=0.0)
            dz = cur_alt
            dur = dz / drone.vertical_speed_mps if dz > 0 else 0.0
            e = descend_wh(dz, drone) if dz > 0 else 0.0
            add_leg(idx, "descend", pos, target, drone.vertical_speed_mps, dz, dur, e)
            state = (
                "ground_home" if math.hypot(pos.x_m - hx, pos.y_m - hy) <= 2.0 else "ground_away"
            )
        elif isinstance(action, ReturnHome):
            from robot_copilot.validator.energy import rth_legs

            for kind, start, end, speed, dist, dur in rth_legs(pos, state, veh, home):
                if kind == "move":
                    e = move_wh(dist, speed, veh)
                elif kind == "climb" and is_drone:
                    e = climb_wh(end.alt_m - start.alt_m, veh)  # type: ignore[arg-type]
                elif kind == "descend" and is_drone:
                    e = descend_wh(start.alt_m - end.alt_m, veh)  # type: ignore[arg-type]
                else:
                    e = 0.0
                add_leg(idx, kind, start, end, speed, dist, dur, e)
            state = "ground_home" if is_drone else "at_home"

    stats = PlanStats(
        distance_m=total_dist,
        vertical_m=total_vert,
        duration_s=total_dur,
        energy_wh=total_energy,
        battery_start_wh=veh.battery_capacity_wh * ctx.battery_pct / 100.0,
        battery_end_wh=battery,
        reserve_wh=reserve,
        photos=photos,
        min_rth_margin_wh=min_rth_margin if min_rth_margin != float("inf") else 0.0,
    )
    return ResolvedPlan(plan=plan, legs=tuple(legs), stats=stats)


def check_spatial_and_energy(
    resolved: ResolvedPlan,
    ctx: ValidationContext,
    state_end: str,
) -> list[ValidationIssue]:
    from robot_copilot.validator.explain import explain_issue
    from robot_copilot.validator.issues import IssueCode, ValidationIssue

    issues: list[ValidationIssue] = []
    veh = ctx.vehicle
    reserve = reserve_wh(veh)
    battery_start = veh.battery_capacity_wh * ctx.battery_pct / 100.0

    if battery_start < reserve:
        msg, hint = explain_issue(
            IssueCode.BATTERY_INSUFFICIENT,
            None,
            {
                "start_wh": round(battery_start, 1),
                "reserve_wh": round(reserve, 1),
                "pct": ctx.battery_pct,
            },
        )
        issues.append(
            ValidationIssue(
                code=IssueCode.BATTERY_INSUFFICIENT,
                severity="error",
                action_index=None,
                params=(
                    ("pct", ctx.battery_pct),
                    ("start_wh", battery_start),
                    ("reserve_wh", reserve),
                ),
                message=msg,
                hint=hint,
            )
        )
        return issues

    rth_blocked_reported = False
    rth_reserve_reported = False
    is_drone = isinstance(veh, DroneProfile)
    home = ctx.site.home

    for leg in resolved.legs:
        if segment_outside_fence(ctx.geometry, leg.start, leg.end):
            msg, hint = explain_issue(IssueCode.OUTSIDE_GEOFENCE, leg.action_index, {})
            issues.append(
                ValidationIssue(
                    code=IssueCode.OUTSIDE_GEOFENCE,
                    severity="error",
                    action_index=leg.action_index,
                    params=(),
                    message=msg,
                    hint=hint,
                )
            )
        ko = segment_hits_keepout(ctx.geometry, leg.start, leg.end)
        if ko:
            msg, hint = explain_issue(IssueCode.ENTERS_KEEP_OUT, leg.action_index, {"keep_out": ko})
            issues.append(
                ValidationIssue(
                    code=IssueCode.ENTERS_KEEP_OUT,
                    severity="error",
                    action_index=leg.action_index,
                    params=(("keep_out", ko),),
                    message=msg,
                    hint=hint,
                )
            )

        st = _leg_state_at_end(leg, is_drone, home)
        if st not in ("ground_home", "at_home"):
            if not rth_blocked_reported and rth_segment_blocked(
                ctx.geometry, leg.end.x_m, leg.end.y_m, home
            ):
                msg, hint = explain_issue(IssueCode.RTH_PATH_BLOCKED, leg.action_index, {})
                issues.append(
                    ValidationIssue(
                        code=IssueCode.RTH_PATH_BLOCKED,
                        severity="error",
                        action_index=leg.action_index,
                        params=(),
                        message=msg,
                        hint=hint,
                    )
                )
                rth_blocked_reported = True
            if not rth_reserve_reported and leg.battery_after_wh - leg.rth_wh < reserve:
                msg, hint = explain_issue(IssueCode.RTH_RESERVE_VIOLATED, leg.action_index, {})
                issues.append(
                    ValidationIssue(
                        code=IssueCode.RTH_RESERVE_VIOLATED,
                        severity="error",
                        action_index=leg.action_index,
                        params=(),
                        message=msg,
                        hint=hint,
                    )
                )
                rth_reserve_reported = True

    stats = resolved.stats
    if stats.distance_m > veh.max_distance_m:
        msg, hint = explain_issue(
            IssueCode.TOO_LONG_DISTANCE,
            None,
            {"distance_m": stats.distance_m, "max": veh.max_distance_m},
        )
        issues.append(
            ValidationIssue(
                code=IssueCode.TOO_LONG_DISTANCE,
                severity="error",
                action_index=None,
                params=(("distance_m", stats.distance_m),),
                message=msg,
                hint=hint,
            )
        )
    if stats.duration_s > veh.max_duration_s:
        msg, hint = explain_issue(
            IssueCode.TOO_LONG_DURATION,
            None,
            {"duration_s": stats.duration_s, "max": veh.max_duration_s},
        )
        issues.append(
            ValidationIssue(
                code=IssueCode.TOO_LONG_DURATION,
                severity="error",
                action_index=None,
                params=(("duration_s", stats.duration_s),),
                message=msg,
                hint=hint,
            )
        )
    if stats.battery_end_wh < reserve:
        batt_params = {
            "pct": ctx.battery_pct,
            "start_wh": round(battery_start, 1),
            "end_wh": round(stats.battery_end_wh, 1),
            "reserve_wh": round(reserve, 1),
        }
        msg, hint = explain_issue(IssueCode.BATTERY_INSUFFICIENT, None, batt_params)
        issues.append(
            ValidationIssue(
                code=IssueCode.BATTERY_INSUFFICIENT,
                severity="error",
                action_index=None,
                params=(
                    ("pct", ctx.battery_pct),
                    ("start_wh", battery_start),
                    ("end_wh", stats.battery_end_wh),
                    ("reserve_wh", reserve),
                ),
                message=msg,
                hint=hint,
            )
        )

    final_ok = state_end in ("ground_home", "at_home")
    if not final_ok:
        msg, hint = explain_issue(IssueCode.MUST_END_AT_HOME, None, {})
        issues.append(
            ValidationIssue(
                code=IssueCode.MUST_END_AT_HOME,
                severity="error",
                action_index=None,
                params=(),
                message=msg,
                hint=hint,
            )
        )
    return issues


def _leg_state_at_end(leg: Leg, is_drone: bool, home: tuple[float, float]) -> str:
    end = leg.end
    if is_drone:
        if end.alt_m <= 0 and math.hypot(end.x_m - home[0], end.y_m - home[1]) <= 2.0:
            return "ground_home"
        if end.alt_m <= 0:
            return "ground_away"
        return "air"
    if math.hypot(end.x_m - home[0], end.y_m - home[1]) <= 2.0:
        return "at_home"
    return "away"


def final_state_after_plan(plan: MissionPlan, ctx: ValidationContext) -> str:
    from robot_copilot.validator.structure import _transition

    is_drone = isinstance(ctx.vehicle, DroneProfile)
    state = "ground_home" if is_drone else "at_home"
    cur_alt = 0.0
    dummy: list[ValidationIssue] = []
    for idx, action in enumerate(plan.actions):
        state, cur_alt = _transition(action, idx, ctx, state, cur_alt, is_drone, dummy)
    return state
