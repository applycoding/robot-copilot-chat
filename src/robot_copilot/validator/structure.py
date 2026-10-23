from __future__ import annotations

import math
from typing import Any

from robot_copilot.plan import (
    Action,
    Goto,
    Hover,
    Land,
    MissionPlan,
    Photo,
    ReturnHome,
    Takeoff,
)
from robot_copilot.site import resolve_place, suggest_places
from robot_copilot.validator.context import ValidationContext
from robot_copilot.validator.energy import HOME_RADIUS_M
from robot_copilot.validator.issues import IssueCode, ValidationIssue
from robot_copilot.vehicles import DroneProfile


def _issue(
    code: IssueCode,
    action_index: int | None,
    params: dict[str, Any],
    message: str = "",
    hint: str = "",
) -> ValidationIssue:
    from robot_copilot.validator.explain import explain_issue

    msg, h = explain_issue(code, action_index, params) if not message else (message, hint)
    return ValidationIssue(
        code=code,
        severity="error",
        action_index=action_index,
        params=tuple(sorted(params.items())),
        message=msg,
        hint=h,
    )


def validate_structure(plan: MissionPlan, ctx: ValidationContext) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    veh = ctx.vehicle
    is_drone = isinstance(veh, DroneProfile)

    if plan.vehicle != veh.kind:
        issues.append(
            _issue(IssueCode.VEHICLE_MISMATCH, None, {"expected": veh.kind, "got": plan.vehicle})
        )

    if len(plan.actions) > veh.max_actions:
        issues.append(
            _issue(
                IssueCode.TOO_MANY_ACTIONS,
                None,
                {"count": len(plan.actions), "max": veh.max_actions},
            )
        )

    state = "ground_home" if is_drone else "at_home"
    cur_alt = 0.0
    _hx, _hy = ctx.site.home

    for idx, action in enumerate(plan.actions):
        issues.extend(_check_action_structure(action, idx, ctx, state, cur_alt, is_drone))
        state, cur_alt = _transition(action, idx, ctx, state, cur_alt, is_drone, issues)

    return issues


def _check_action_structure(
    action: Action,
    idx: int,
    ctx: ValidationContext,
    state: str,
    cur_alt: float,
    is_drone: bool,
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    veh = ctx.vehicle

    if isinstance(action, Takeoff):
        if not is_drone:
            issues.append(
                _issue(IssueCode.UNSUPPORTED_ACTION_FOR_VEHICLE, idx, {"action": "takeoff"})
            )
        else:
            drone = veh
            assert isinstance(drone, DroneProfile)
            alt = action.altitude_m
            if alt < drone.min_altitude_m:
                issues.append(
                    _issue(
                        IssueCode.ALTITUDE_LOW,
                        idx,
                        {"altitude_m": alt, "min": drone.min_altitude_m},
                    )
                )
            if alt > drone.max_altitude_m:
                issues.append(
                    _issue(
                        IssueCode.ALTITUDE_HIGH,
                        idx,
                        {"altitude_m": alt, "max": drone.max_altitude_m},
                    )
                )

    if isinstance(action, Land) and not is_drone:
        issues.append(_issue(IssueCode.UNSUPPORTED_ACTION_FOR_VEHICLE, idx, {"action": "land"}))

    if isinstance(action, Goto):
        if (
            not is_drone
            and action.altitude_m is not None
            and action.altitude_m not in (0, None)
            and action.altitude_m != 0
        ):
            issues.append(
                _issue(
                    IssueCode.ALTITUDE_ON_GROUND_VEHICLE,
                    idx,
                    {"altitude_m": action.altitude_m},
                )
            )
        speed = action.speed_mps if action.speed_mps is not None else veh.cruise_speed_mps
        if speed <= 0:
            issues.append(_issue(IssueCode.SPEED_NONPOSITIVE, idx, {"speed_mps": speed}))
        elif speed > veh.max_speed_mps:
            issues.append(
                _issue(IssueCode.SPEED_HIGH, idx, {"speed_mps": speed, "max": veh.max_speed_mps})
            )

        if is_drone and action.altitude_m is not None:
            drone = veh
            assert isinstance(drone, DroneProfile)
            alt = action.altitude_m
            if alt < drone.min_altitude_m:
                issues.append(
                    _issue(
                        IssueCode.ALTITUDE_LOW,
                        idx,
                        {"altitude_m": alt, "min": drone.min_altitude_m},
                    )
                )
            if alt > drone.max_altitude_m:
                issues.append(
                    _issue(
                        IssueCode.ALTITUDE_HIGH,
                        idx,
                        {"altitude_m": alt, "max": drone.max_altitude_m},
                    )
                )

        if action.place is not None:
            place = resolve_place(ctx.site, action.place)
            if place is None:
                suggestions = suggest_places(ctx.site, action.place)
                issues.append(
                    _issue(
                        IssueCode.UNKNOWN_PLACE,
                        idx,
                        {"place": action.place, "suggestions": ",".join(suggestions)},
                    )
                )
            elif place.kind == "path":
                if (
                    action.point_index is None
                    or action.point_index < 0
                    or action.point_index >= len(place.points)
                ):
                    issues.append(
                        _issue(
                            IssueCode.BAD_POINT_INDEX,
                            idx,
                            {"min": 0, "max": len(place.points) - 1},
                        )
                    )
            elif action.point_index is not None and action.point_index not in (0, None):
                if action.point_index != 0:
                    issues.append(
                        _issue(
                            IssueCode.BAD_POINT_INDEX,
                            idx,
                            {"min": 0, "max": 0},
                        )
                    )

    if isinstance(action, Hover):
        if action.seconds <= 0:
            issues.append(_issue(IssueCode.HOVER_INVALID, idx, {"seconds": action.seconds}))
        elif action.seconds > veh.max_hover_s:
            issues.append(
                _issue(
                    IssueCode.HOVER_TOO_LONG,
                    idx,
                    {"seconds": action.seconds, "max": veh.max_hover_s},
                )
            )

    return issues


def _sequence_issue(idx: int) -> ValidationIssue:
    return _issue(IssueCode.SEQUENCE, idx, {})


def _transition(
    action: Action,
    idx: int,
    ctx: ValidationContext,
    state: str,
    cur_alt: float,
    is_drone: bool,
    issues: list[ValidationIssue],
) -> tuple[str, float]:
    hx, hy = ctx.site.home

    if isinstance(action, Takeoff):
        if not is_drone:
            return state, cur_alt
        if state == "air":
            issues.append(_sequence_issue(idx))
            return state, cur_alt
        return "air", action.altitude_m

    if isinstance(action, Land):
        if not is_drone:
            return state, cur_alt
        if state != "air":
            issues.append(_sequence_issue(idx))
            return state, cur_alt
        x, y = _end_xy(action, idx, ctx, state, cur_alt)
        if math.hypot(x - hx, y - hy) <= HOME_RADIUS_M:
            return "ground_home", 0.0
        return "ground_away", 0.0

    if isinstance(action, ReturnHome):
        if is_drone:
            if state == "ground_home":
                issues.append(_sequence_issue(idx))
                return state, cur_alt
            return "ground_home", 0.0
        if state == "at_home":
            issues.append(_sequence_issue(idx))
            return state, cur_alt
        return "at_home", 0.0

    if isinstance(action, Goto):
        if is_drone and state == "ground_home":
            issues.append(_sequence_issue(idx))
            return state, cur_alt
        if not is_drone and state == "ground_home":
            issues.append(_sequence_issue(idx))
            return state, cur_alt
        x, y, alt = _resolve_target(action, ctx, cur_alt, is_drone)
        if is_drone:
            if state == "ground_away":
                issues.append(_sequence_issue(idx))
                return state, cur_alt
            return "air", alt
        if math.hypot(x - hx, y - hy) <= HOME_RADIUS_M:
            return "at_home", 0.0
        return "away", 0.0

    if isinstance(action, (Hover, Photo)):
        if is_drone:
            if state in ("ground_home", "ground_away"):
                issues.append(_sequence_issue(idx))
            return state, cur_alt
        return state, cur_alt

    return state, cur_alt


def _end_xy(
    action: Action, idx: int, ctx: ValidationContext, state: str, cur_alt: float
) -> tuple[float, float]:
    if isinstance(action, Goto):
        x, y, _ = _resolve_target(action, ctx, cur_alt, isinstance(ctx.vehicle, DroneProfile))
        return x, y
    return ctx.site.home


def _resolve_target(
    action: Goto,
    ctx: ValidationContext,
    cur_alt: float,
    is_drone: bool,
) -> tuple[float, float, float]:
    veh = ctx.vehicle
    if action.xy is not None:
        x, y = action.xy.x_m, action.xy.y_m
    else:
        place = resolve_place(ctx.site, action.place or "")
        if place is None:
            return ctx.site.home[0], ctx.site.home[1], cur_alt
        if place.kind == "path":
            pi = action.point_index or 0
            if pi < 0 or pi >= len(place.points):
                return ctx.site.home[0], ctx.site.home[1], cur_alt
            x, y = place.points[pi]
        else:
            x, y = place.points[0]
    if is_drone:
        drone = veh
        assert isinstance(drone, DroneProfile)
        alt = (
            action.altitude_m
            if action.altitude_m is not None
            else max(cur_alt, drone.default_altitude_m)
        )
    else:
        alt = 0.0
    return x, y, alt
