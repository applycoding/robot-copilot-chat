from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal

from robot_copilot.sim.telemetry import FinalState, Frame, PhotoEvent
from robot_copilot.validator import plan_hash
from robot_copilot.validator.context import ValidationContext
from robot_copilot.validator.issues import XYZ, Leg, ValidationReport
from robot_copilot.validator.spatial import segment_hits_keepout, segment_outside_fence
from robot_copilot.vehicles import DroneProfile


class NotValidatedError(Exception):
    pass


class SafetyInvariantError(Exception):
    pass


@dataclass
class SimResult:
    status: str
    frames: tuple[Frame, ...]
    photos: tuple[PhotoEvent, ...]
    final_state: FinalState
    abort_reason: str | None = None


def simulate(
    report: ValidationReport,
    ctx: ValidationContext,
    *,
    dt_s: float = 0.5,
    max_frames: int = 4000,
) -> SimResult:
    if not report.ok or report.resolved is None or report.plan_hash is None:
        raise NotValidatedError("report not validated")
    resolved = report.resolved
    if report.plan_hash != plan_hash(resolved.plan, ctx):
        raise NotValidatedError("plan hash mismatch")

    dt = dt_s
    while True:
        frames, photos = _build_frames(resolved.legs, dt, ctx)
        if len(frames) <= max_frames:
            break
        dt *= 2

    try:
        _check_frames(frames, ctx)
    except SafetyInvariantError as exc:
        fs = _final_from_frames(frames, ctx)
        return SimResult(
            status="aborted",
            frames=tuple(frames),
            photos=tuple(photos),
            final_state=fs,
            abort_reason=str(exc),
        )

    fs = _final_from_frames(frames, ctx)
    return SimResult(
        status="executed",
        frames=tuple(frames),
        photos=tuple(photos),
        final_state=fs,
    )


def _lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def _build_frames(
    legs: tuple[Leg, ...] | list[Leg], dt: float, ctx: ValidationContext
) -> tuple[list[Frame], list[PhotoEvent]]:
    frames: list[Frame] = []
    photos: list[PhotoEvent] = []
    t0 = 0.0
    is_drone = isinstance(ctx.vehicle, DroneProfile)

    for leg in legs:
        d = leg.duration_s
        n = math.ceil(d / dt) if d > 0 else 0
        if d <= 0:
            continue
        for k in range(n + 1):
            if k == 0 and frames and _same_xyz(frames[-1], leg.start):
                continue
            frac = k / n if n else 0.0
            t = t0 + d * frac
            x = _lerp(leg.start.x_m, leg.end.x_m, frac)
            y = _lerp(leg.start.y_m, leg.end.y_m, frac)
            alt = _lerp(leg.start.alt_m, leg.end.alt_m, frac)
            bat = _lerp(
                leg.start.alt_m * 0 + (leg.battery_after_wh + leg.energy_wh),
                leg.battery_after_wh,
                frac,
            )
            # battery linear in time across leg
            bat_start = leg.battery_after_wh + leg.energy_wh
            bat = _lerp(bat_start, leg.battery_after_wh, frac)

            event: Literal["takeoff", "waypoint", "hover_start", "photo", "land", "home"] | None = (
                None
            )
            if leg.kind == "hover" and k == 0:
                event = "hover_start"
            if k == n:
                if leg.kind == "photo":
                    event = "photo"
                elif leg.kind == "climb" and leg.end.alt_m > leg.start.alt_m:
                    event = "takeoff"
                elif leg.kind == "descend" and leg.end.alt_m == 0:
                    event = "land"
                elif leg.kind == "move" and leg.end.alt_m == 0:
                    event = "waypoint"

            frames.append(
                Frame(
                    t_s=t,
                    x_m=x if k != n else leg.end.x_m,
                    y_m=y if k != n else leg.end.y_m,
                    alt_m=0.0 if not is_drone else (leg.end.alt_m if k == n else alt),
                    battery_wh=leg.battery_after_wh if k == n else bat,
                    action_index=leg.action_index,
                    event=event,
                )
            )
            if k == n and leg.kind == "photo":
                photos.append(
                    PhotoEvent(
                        t_s=t,
                        x_m=leg.end.x_m,
                        y_m=leg.end.y_m,
                        alt_m=0.0 if not is_drone else leg.end.alt_m,
                        label=None,
                        action_index=leg.action_index,
                    )
                )
        t0 += d

    if not is_drone:
        for f in frames:
            object.__setattr__(f, "alt_m", 0.0)

    return frames, photos


def _same_xyz(frame: Frame, xyz: XYZ) -> bool:
    return frame.x_m == xyz.x_m and frame.y_m == xyz.y_m and frame.alt_m == xyz.alt_m


def _check_frames(frames: list[Frame], ctx: ValidationContext) -> None:
    isinstance(ctx.vehicle, DroneProfile)
    reserve = ctx.vehicle.battery_capacity_wh * ctx.vehicle.reserve_pct / 100
    for f in frames:
        start = type("X", (), {"x_m": f.x_m, "y_m": f.y_m, "alt_m": f.alt_m})()
        if segment_outside_fence(ctx.geometry, start, start):
            raise SafetyInvariantError("outside geofence")
        if segment_hits_keepout(ctx.geometry, start, start):
            raise SafetyInvariantError("keep-out")
        if isinstance(ctx.vehicle, DroneProfile) and (
            f.alt_m < 0 or f.alt_m > ctx.vehicle.max_altitude_m
        ):
            raise SafetyInvariantError("altitude")
        if f.battery_wh < reserve:
            raise SafetyInvariantError("battery below reserve")


def _final_from_frames(frames: list[Frame], ctx: ValidationContext) -> FinalState:
    if not frames:
        hx, hy = ctx.site.home
        return FinalState(x_m=hx, y_m=hy, alt_m=0.0, battery_wh=0.0, landed=True, at_home=True)
    last = frames[-1]
    hx, hy = ctx.site.home
    at_home = math.hypot(last.x_m - hx, last.y_m - hy) <= 2.0
    landed = last.alt_m <= 0.01
    return FinalState(
        x_m=last.x_m,
        y_m=last.y_m,
        alt_m=last.alt_m,
        battery_wh=last.battery_wh,
        landed=landed,
        at_home=at_home,
    )
