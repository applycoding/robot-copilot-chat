from __future__ import annotations

import math

from robot_copilot.validator.issues import XYZ
from robot_copilot.vehicles import DroneProfile, RoverProfile

HOME_RADIUS_M = 2.0


def reserve_wh(veh: DroneProfile | RoverProfile) -> float:
    return veh.battery_capacity_wh * veh.reserve_pct / 100.0


def move_wh(d: float, v_speed: float, veh: DroneProfile | RoverProfile) -> float:
    if d <= 0 or v_speed <= 0:
        return 0.0
    p = veh.cruise_power_w if isinstance(veh, DroneProfile) else veh.drive_power_w
    return (d / v_speed) * p / 3600.0


def climb_wh(dz: float, drone: DroneProfile) -> float:
    if dz <= 0:
        return 0.0
    return (
        drone.climb_wh_per_m * dz + drone.hover_power_w * (dz / drone.vertical_speed_mps) / 3600.0
    )


def descend_wh(dz: float, drone: DroneProfile) -> float:
    if dz <= 0:
        return 0.0
    return drone.hover_power_w * (dz / drone.vertical_speed_mps) / 3600.0


def hover_wh(s: float, veh: DroneProfile | RoverProfile) -> float:
    if s <= 0:
        return 0.0
    p = veh.hover_power_w if isinstance(veh, DroneProfile) else veh.idle_power_w
    return s * p / 3600.0


def photo_leg_wh(veh: DroneProfile | RoverProfile) -> tuple[float, float]:
    return hover_wh(veh.photo_s, veh) + veh.photo_wh, veh.photo_s


def at_home(pos: XYZ, home: tuple[float, float]) -> bool:
    return math.hypot(pos.x_m - home[0], pos.y_m - home[1]) <= HOME_RADIUS_M


def rth_legs(
    pos: XYZ,
    state: str,
    veh: DroneProfile | RoverProfile,
    home: tuple[float, float],
) -> list[tuple[str, XYZ, XYZ, float, float, float]]:
    """Returns list of (kind, start, end, speed, distance, duration)."""
    if state in ("ground_home", "at_home"):
        return []
    legs: list[tuple[str, XYZ, XYZ, float, float, float]] = []
    x, y, alt = pos.x_m, pos.y_m, pos.alt_m
    hx, hy = home
    if isinstance(veh, DroneProfile):
        rth_alt = max(alt, veh.rth_altitude_m)
        if state == "ground_away" or alt < rth_alt:
            target = XYZ(x_m=x, y_m=y, alt_m=rth_alt)
            dz = abs(rth_alt - alt)
            dur = dz / veh.vertical_speed_mps if dz > 0 else 0.0
            legs.append(("climb", pos, target, veh.vertical_speed_mps, dz, dur))
            pos = target
            alt = rth_alt
        dist = math.hypot(hx - x, hy - y)
        end = XYZ(x_m=hx, y_m=hy, alt_m=alt)
        dur = dist / veh.cruise_speed_mps if dist > 0 else 0.0
        legs.append(("move", pos, end, veh.cruise_speed_mps, dist, dur))
        pos = end
        if alt > 0:
            target = XYZ(x_m=hx, y_m=hy, alt_m=0.0)
            dz = alt
            dur = dz / veh.vertical_speed_mps
            legs.append(("descend", pos, target, veh.vertical_speed_mps, dz, dur))
    else:
        dist = math.hypot(hx - x, hy - y)
        end = XYZ(x_m=hx, y_m=hy, alt_m=0.0)
        dur = dist / veh.cruise_speed_mps if dist > 0 else 0.0
        legs.append(("move", pos, end, veh.cruise_speed_mps, dist, dur))
    return legs


def rth_wh(
    pos: XYZ, state: str, veh: DroneProfile | RoverProfile, home: tuple[float, float]
) -> float:
    if state in ("ground_home", "at_home"):
        return 0.0
    total = 0.0
    for kind, start, end, speed, dist, _dur in rth_legs(pos, state, veh, home):
        if kind == "move":
            total += move_wh(dist, speed, veh)
        elif kind == "climb" and isinstance(veh, DroneProfile):
            total += climb_wh(end.alt_m - start.alt_m, veh)
        elif kind == "descend" and isinstance(veh, DroneProfile):
            total += descend_wh(start.alt_m - end.alt_m, veh)
    return total
